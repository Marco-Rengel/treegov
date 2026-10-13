"""Motor QUEST (Loh & Shih 1997) - (TreeGov, backend_v3, Fase 0, Paso 8).

Dos etapas:
  ETAPA 1 - Seleccion INSESGADA de variable (independiente del punto de corte):
      * predictor continuo/ordinal  -> F de ANOVA unifactorial (medias).
      * predictor nominal           -> chi2 de Pearson (tabla c x 2).
      * Ajuste de Bonferroni SOLO en esta fase: umbral alpha/(2J), donde J es
        el numero de predictores. DESVIACION DOCUMENTADA respecto a Loh & Shih
        (que usan alpha/J): se controla el FWER sobre DOS familias de pruebas
        (medias y varianzas) -> criterio deliberadamente mas conservador.
      * Desempate robusto: si ningun p de medias/asociacion supera el umbral,
        se ejecuta Brown-Forsythe (Levene con mediana, via statistics.py) so-
        bre las variables ordinales/continuas (deteccion de discriminacion por
        VARIANZA); gana si su p < alpha/(2J). Las categoricas no participan.
  ETAPA 2 - Punto de corte sobre la variable seleccionada:
      * continua/ordinal -> QDA UNIVARIANTE (raiz de las log-verosimilitudes
        condicionales gaussianas con priors empiricos pi_k = n_k/N), con
        fallback al punto medio PONDERADO x_bar = (n0 m0 + n1 m1)/N si no hay
        raiz real unica en el rango entre medias (forma operativa, no optima;
        documentado).
      * nominal -> particion binaria por ganancia de Gini, EXACTAMENTE como
        C&RT: exhaustiva 2^(K-1)-1 si K <= max_exhaustive_cardinality; orden
        por tasa supervisada si K > 10.
      Con K > 2 se sustituye la QDA univariante por un barrido de Gini
      sobre el predictor seleccionado (extension documentada en
      methodology.md §3.8, coherente con C&RT). K=2 conserva el camino
      QDA original (paridad invariante).

Restricciones regulatorias activas:
  * MRM-INTERPRETABILIDAD: PROHIBIDO ACP/rotaciones; QDA estrictamente
    univariante -> la regla exportada es un "x <= t" o un "x in {...}"
    directamente traducible a CASE WHEN.
  * Multiclase (Fase 3.4.b): Etapa 1 admite K >= 2; Etapa 2 sigue el
    camino binario QDA cuando K=2 y el barrido de Gini cuando K > 2
    (extension documentada, ver §3.8 de methodology.md).
  * DATA LEAKAGE: la imputacion NO vive aqui; corresponde a
    backend_v3/imputation.py (TrainOnlyImputer, solo train). Este motor aplica
    dropna defensivo por variable con conteo en el log.

NOTA de fidelidad bibliografica: la via K>10 por tasa es estilo
Breiman/C&RT (1984), NO el procedimiento de dummies+LDA de Loh & Shih
(1997). Se adopta por coherencia interna con crt_engine.py y queda
asentado aqui.

NOTA de acoplamiento (deuda conocida): reutiliza los kernels _gini_dI y
_masks_exhaustivas de backend_v3.crt_engine (mismo paquete). Si un tercer
motor los necesitara, extraerlos a backend_v3/tree_kernels.py.

Cita canonica:
  Loh, W.-Y. & Shih, Y.-S. (1997). "Split Selection Methods for
  Classification Trees". Statistica Sinica 7(4), 815-840.

Pesos por muestra (Fase 3.2.d): `evaluate`/`best_split` aceptan
`weights` keyword-only (1D, finitos, >0). Con pesos, las "cuentas" del
ANOVA, la chi-cuadrado y el QDA pasan a ser sumas de pesos:
  * ANOVA ponderado: Heeringa, West & Berglund (2010), "Applied Survey
    Data Analysis", §5.3.
  * chi2 de Pearson es sensible a la escala de la masa total de pesos
    (ibid., §5.4): comportamiento correcto, NO se normaliza.
  * varianza ponderada con divisor W - 1 (generalizacion natural del
    n - 1 clasico cuando los pesos actuan como frecuencias).
Con `weights=None` el comportamiento es identico bit a bit al previo.
`SplitConfig.child_ns` y `parent_n` siguen siendo CONTEO FISICO DE
FILAS (enteros).

Dependencias permitidas: numpy, pandas, scipy.stats (via statistics.py).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .crt_engine import _gini_dI, _masks_exhaustivas  # acoplamiento documentado
from .log_config import get_logger
from .statistics import TestResult, bonferroni_adjust, brown_forsythe, f_oneway, pearson_chi2
from .types import PredictorType, SplitConfig

__all__ = ["QuestEngine", "QuestSelection"]


@dataclass(frozen=True)
class QuestSelection:
    """Evidencia auditable de la Etapa 1 (seleccion de variable)."""

    predictor: str
    source: str            # "anova" | "chi2" | "levene"
    test: TestResult       # estadistico crudo de seleccion
    p_value_adjusted: float
    bonferroni_multiplier: int


class QuestEngine:
    """Motor QUEST binario: seleccion insesgada + corte QDA univariante.

    Configurable knobs (defaults preserve the legacy Fase 0 behavior with
    zero numeric change; see design_decisions.md sections 4.1-4.3):

      - bonferroni_family (int >= 1, default 2): family multiplier in the
        Stage-1 Bonferroni threshold alpha / (bonferroni_family * J).
        2 = documented conservative deviation controlling the FWER over
        BOTH test families (means + variance); 1 = canonical Loh & Shih
        (1997) single-family threshold alpha / J.
      - nominal_high_card (str, default "rate"): strategy for nominal
        predictors with cardinality > max_exhaustive_cardinality in
        Stage 2. "rate" = supervised-rate ordering (Breiman/C&RT style).
        "dummies_lda" (canonical Loh & Shih 1997) is reserved for
        Fase 3.4 and raises NotImplementedError.
      - qda_root_restriction (bool, default True): Stage-2 QDA root
        selection. True = accept only roots inside the inter-means range
        (documented Fase 0 restriction); False = canonical mode accepting
        any real root, tie-broken by closeness to the weighted mean.
    """

    def __init__(
        self,
        *,
        alpha: float = 0.05,
        max_exhaustive_cardinality: int = 10,
        bonferroni_family: int = 2,
        nominal_high_card: str = "rate",
        qda_root_restriction: bool = True,
        logger: logging.Logger | None = None,
    ) -> None:
        """Build the engine (all knobs keyword-only).

        Parameters
        ----------
        alpha:
            Family-wise significance level for Stage 1, in (0, 1).
        max_exhaustive_cardinality:
            Maximum cardinality for the exhaustive nominal subset search.
        bonferroni_family:
            Bonferroni family multiplier (integer >= 1); the Stage-1
            threshold is alpha / (bonferroni_family * J). Default 2 (two
            families: means + variance); 1 reproduces the canonical
            Loh & Shih (1997) threshold.
        nominal_high_card:
            "rate" (default) orders high-cardinality nominal categories by
            supervised rate; "dummies_lda" is reserved for Fase 3.4 and
            raises NotImplementedError immediately.
        qda_root_restriction:
            True (default) restricts the QDA cutpoint to the inter-means
            range; False accepts any real root (canonical mode).
        logger:
            Optional logger; defaults to the "quest" logger.
        """
        if isinstance(alpha, bool) or not (0.0 < float(alpha) < 1.0):
            raise ValueError(f"alpha debe estar en (0, 1) (recibido {alpha!r})")
        from numbers import Integral
        if (isinstance(max_exhaustive_cardinality, bool)
                or not isinstance(max_exhaustive_cardinality, Integral)
                or int(max_exhaustive_cardinality) < 2):
            raise ValueError(
                "max_exhaustive_cardinality debe ser entero >= 2 "
                f"(recibido {max_exhaustive_cardinality!r})"
            )
        if (isinstance(bonferroni_family, bool)
                or not isinstance(bonferroni_family, Integral)
                or int(bonferroni_family) < 1):
            raise ValueError(
                "bonferroni_family debe ser entero >= 1 "
                f"(recibido {bonferroni_family!r})"
            )
        if (not isinstance(nominal_high_card, str)
                or nominal_high_card not in {"rate", "dummies_lda"}):
            raise ValueError(
                "nominal_high_card debe ser 'rate' o 'dummies_lda' "
                f"(recibido {nominal_high_card!r})"
            )
        if nominal_high_card == "dummies_lda":
            raise NotImplementedError(
                "nominal_high_card='dummies_lda' reservado para Fase 3.4 "
                "(requiere LDA + dummies; ver design_decisions.md §4.2)"
            )
        if not isinstance(qda_root_restriction, bool):
            raise ValueError(
                "qda_root_restriction debe ser bool "
                f"(recibido {qda_root_restriction!r})"
            )
        self.alpha = float(alpha)
        self.max_exhaustive_cardinality = int(max_exhaustive_cardinality)
        self.bonferroni_family = int(bonferroni_family)
        self.nominal_high_card = str(nominal_high_card)
        self.qda_root_restriction = bool(qda_root_restriction)
        self._log = logger if logger is not None else get_logger("quest")

    # ------------------------------------------------------------------
    # API publica: etapas 1 + 2
    # ------------------------------------------------------------------

    def evaluate(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        spec: dict[str, PredictorType],
        *,
        weights: np.ndarray | None = None,
    ) -> SplitConfig | None:
        """QUEST completo en un nodo: seleccion de variable + corte.

        Nota Bonferroni: J = len(spec) = TODOS los predictores declarados por
        el llamador, incluidos los descartados por datos insuficientes
        (criterio conservador: la correccion cubre la familia de tests que se
        INTENTARON, no solo los computados).

        weights (keyword-only, Fase 3.2.d): pesos por muestra 1D, finitos,
        estrictamente positivos, longitud = len(X). Con pesos, el ANOVA es
        ponderado (Heeringa, West & Berglund 2010, §5.3) y la chi2 de
        Pearson recibe una tabla con sumas de pesos (sensible a la escala,
        ibid. §5.4: comportamiento correcto, no se normaliza). La varianza
        ponderada del QDA usa divisor W - 1. Con weights=None, el
        comportamiento es identico bit a bit al previo.
        """
        if not spec:
            raise ValueError("[QUEST] spec vacio: nada que evaluar")
        for nombre in spec:
            if nombre not in X.columns:
                raise ValueError(f"[QUEST] predictor ausente en X: {nombre!r}")

        ys = y if isinstance(y, pd.Series) else pd.Series(y)
        if len(ys) != len(X):
            raise ValueError(
                f"[QUEST] X (n={len(X)}) e y (n={len(ys)}) difieren en longitud"
            )

        w_full: np.ndarray | None = None
        if weights is not None:
            w_full = np.asarray(weights, dtype=float)
            if w_full.ndim != 1 or w_full.size != len(X):
                raise ValueError(
                    f"[QUEST] weights debe ser 1D de longitud len(X)={len(X)} "
                    f"(recibido shape={w_full.shape})"
                )
            if not np.all(np.isfinite(w_full)) or not np.all(w_full > 0.0):
                raise ValueError(
                    "[QUEST] weights deben ser finitos y estrictamente positivos"
                )

        # --- target: K >= 2 clases (binario o multiclase) ---
        yd = ys.dropna()
        if len(yd) == 0:
            self._log.warning("[QUEST] target totalmente NaN")
            return None
        # clases ORDENADAS (reproducibilidad MRM: el codigo 0/1 no depende del
        # orden de aparicion en los datos; exige etiquetas comparables)
        try:
            classes = sorted(pd.unique(yd))
        except TypeError as e:
            raise ValueError(
                "[QUEST] target con etiquetas no comparables: no se puede "
                "asignar codigos 0/1 de forma determinista "
                f"(clases={list(pd.unique(yd))!r})"
            ) from e
        if len(classes) < 2:
            self._log.warning("[QUEST] target constante: nodo puro, sin split")
            return None
        codes = yd.map({c: i for i, c in enumerate(classes)}).to_numpy(dtype=np.int64)
        y_full = pd.Series(np.nan, index=ys.index)  # alinear con dropna por variable
        y_full.loc[yd.index] = codes

        j_total = len(spec)
        # self.bonferroni_family (default 2 = doble familia; canonical Loh & Shih = 1)
        umbral = self.alpha / (self.bonferroni_family * j_total)
        self._log.debug(
            "[QUEST] Etapa 1: J=%d, umbral Bonferroni=%.6g", j_total, umbral
        )

        # --- Etapa 1, familia 1: medias / asociacion ---
        preparado: dict[str, tuple] = {}
        mejor_media: tuple[float, str, str, TestResult] | None = None
        for orden, (nombre, ptype) in enumerate(spec.items()):
            pre = self._prepare(X[nombre], y_full, ptype, nombre, weights=w_full)
            if pre is None:
                continue
            xd, yc, info = pre
            preparado[nombre] = (xd, yc, info)
            res = info["test"]
            if mejor_media is None or res.p_value < mejor_media[0]:
                mejor_media = (res.p_value, nombre, info["source"], res)

        seleccion: QuestSelection | None = None
        if mejor_media is not None and mejor_media[0] < umbral:
            _, nombre, source, res = mejor_media
            seleccion = self._mk_selection(nombre, source, res, j_total)
        else:
            # --- Etapa 1, familia 2: desempate robusto Levene/Brown-Forsythe ---
            mejor_var: tuple[float, str, TestResult] | None = None
            for nombre, ptype in spec.items():
                if ptype == PredictorType.NOMINAL or nombre not in preparado:
                    continue
                xd, yc, info = preparado[nombre]
                xs_k = info["xs_k"]
                ws_k = info["ws_k"]
                if any(x.size == 0 for x in xs_k):
                    continue
                bf = brown_forsythe(*xs_k, weights=tuple(ws_k))
                if mejor_var is None or bf.p_value < mejor_var[0]:
                    mejor_var = (bf.p_value, nombre, bf)
            if mejor_var is not None and mejor_var[0] < umbral:
                _, nombre, bf = mejor_var
                seleccion = self._mk_selection(nombre, "levene", bf, j_total)

        if seleccion is None:
            self._log.info(
                "[QUEST] Etapa 1 sin ganador (umbral=%.6g): nodo hoja", umbral
            )
            return None

        xd, yc, info = preparado[seleccion.predictor]
        self._log.info(
            "[QUEST] Etapa 1: gana %r via %s (p=%.6g, p_adj=%.6g, M=%d)",
            seleccion.predictor, seleccion.source, seleccion.test.p_value,
            seleccion.p_value_adjusted, seleccion.bonferroni_multiplier,
        )

        # --- guardia de representabilidad (SplitConfig exige statistic finito) ---
        if not math.isfinite(float(seleccion.test.statistic)):
            self._log.warning(
                "[QUEST|%r] estadistico de seleccion infinito (separacion "
                "perfecta, SSW=0): no representable en SplitConfig -> None",
                seleccion.predictor,
            )
            return None

        # --- Etapa 2 ---
        if spec[seleccion.predictor] == PredictorType.NOMINAL:
            corte = self._subset_cut(xd, yc, seleccion.predictor, weights=info["w"])
            if corte is None:
                return None
            (branches, child_ns), threshold = corte, None
        else:
            threshold, branches = self._numeric_cut(xd, yc, info, seleccion.predictor)
            if branches is not None:       # ordinal simbolico -> grupos
                child_ns = (
                    int((np.isin(xd, list(branches[0]))).sum()),
                    int((np.isin(xd, list(branches[1]))).sum()),
                )
            else:
                xv = info["xv"]
                child_ns = (int((xv <= threshold).sum()), int((xv > threshold).sum()))

        config = SplitConfig(
            predictor=seleccion.predictor,
            method="QUEST",
            statistic=float(seleccion.test.statistic),
            statistic_name="chi2" if spec[seleccion.predictor] == PredictorType.NOMINAL else "f",
            df=seleccion.test.df,
            parent_n=int(len(yc)),
            child_ns=child_ns,
            p_value=seleccion.test.p_value,
            p_value_adjusted=seleccion.p_value_adjusted,
            bonferroni_multiplier=seleccion.bonferroni_multiplier,
            n_merges=0,
            threshold=threshold,
            branches=branches,
        )
        self._log.info(
            "[QUEST|%r] split: %s=%.6g p_adj=%.6g %s n=(%d, %d)",
            config.predictor, config.statistic_name, config.statistic,
            config.p_value_adjusted,
            f"thr={threshold:.6g}" if threshold is not None else "branches",
            child_ns[0], child_ns[1],
        )
        return config

    def best_split(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        spec: dict[str, PredictorType],
        *,
        target_type=None,
        weights: np.ndarray | None = None,
    ) -> SplitConfig | None:
        """Alias de evaluate() para paridad de API con ChaidEngine/CrtEngine.

        QUEST siempre exige target binario (Fase 0); target_type se ignora.
        weights se propaga a evaluate (Fase 3.2.d).
        """
        return self.evaluate(X, y, spec, weights=weights)

    # ------------------------------------------------------------------
    # preparacion por variable (dropna defensivo; imputacion vive fuera)
    # ------------------------------------------------------------------

    def _prepare(
        self,
        x: pd.Series,
        y_full: pd.Series,
        ptype: PredictorType,
        nombre: str,
        *,
        weights: np.ndarray | None = None,
    ):
        """dropna conjunto por variable + TestResult de la Etapa 1.

        Con `weights` (Fase 3.2.d), el sub-vector `w` se extrae con la
        misma mascara dropna; si weights es None, w = np.ones(n): a partir
        de aqui todo el motor opera sobre `w`, unificando el camino.
        """
        mask = x.notna().to_numpy() & y_full.notna().to_numpy()
        xd = x[mask]
        yc = y_full[mask].to_numpy(dtype=np.int64)
        n = int(len(xd))
        w = weights[mask] if weights is not None else np.ones(n)
        n_drop = int((~mask).sum())
        if n_drop:
            self._log.info("[QUEST|%r] %d filas excluidas por NaN", nombre, n_drop)
        if n < 3:
            self._log.info("[QUEST|%r] <3 casos validos: excluido", nombre)
            return None

        # Fase 3.4.b: relabel local de clases. Un subnodo puede contener
        # un subconjunto de las clases globales; relabelar a 0..local_K-1
        # garantiza que la tabla c x K y los sub-vectores por clase no
        # contengan columnas vacias (que pearson_chi2 rechaza).
        present = np.unique(yc)
        if present.size < 2:
            # una sola clase tras dropna: sin asociacion evaluable
            return None
        yc = np.searchsorted(present, yc)  # relabel a 0..local_K-1
        K = int(present.size)  # K local, no global

        if ptype == PredictorType.NOMINAL:
            # tabla (c, K) de contingencia con sumas de pesos (np.bincount
            # ponderado; sustituye al pd.crosstab original en Fase 3.2.d)
            try:
                cat_codes, _uniques = pd.factorize(xd, sort=True)
            except TypeError as e:
                raise ValueError(
                    f"[QUEST|{nombre!r}] categorias no factorizables: {e}"
                ) from e
            k_cats = int(cat_codes.max()) + 1
            if k_cats < 2:
                return None
            tab = np.bincount(
                cat_codes * K + yc, weights=w, minlength=K * k_cats
            ).reshape(k_cats, K)
            test = pearson_chi2(tab)
            return xd, yc, {"source": "chi2", "test": test, "w": w}

        # continuo u ordinal: ordinal simbolico se mide sobre los CODIGOS
        # del orden natural (factorize sort=True), que es lo que luego corta
        # la Etapa 2; los dos comparten la misma representacion xv.
        labels: tuple | None = None
        if pd.api.types.is_numeric_dtype(xd):
            xv = xd.to_numpy(dtype=float)
        else:
            try:
                codes, uniques = pd.factorize(xd, sort=True)
            except TypeError as e:
                raise ValueError(
                    f"[QUEST|{nombre!r}] categorias no factorizables: {e}"
                ) from e
            labels = tuple(uniques)
            xv = codes.astype(float)
        if not np.all(np.isfinite(xv)):
            raise ValueError(f"[QUEST|{nombre!r}] x contiene no finitos")
        xs_k = [xv[yc == k] for k in range(K)]
        ws_k = [w[yc == k] for k in range(K)]
        if any(x.size == 0 for x in xs_k):
            # alguna clase sin filas tras el dropna defensivo
            test = TestResult(0.0, (1, 1), 1.0)
        else:
            test = f_oneway(*xs_k, weights=tuple(ws_k))
        return xd, yc, {"source": "anova", "test": test, "xs_k": xs_k,
                        "ws_k": ws_k, "w": w, "xv": xv, "labels": labels}

    def _mk_selection(
        self, nombre: str, source: str, res: TestResult, j_total: int
    ) -> QuestSelection:
        m = self.bonferroni_family * j_total
        return QuestSelection(
            predictor=nombre,
            source=source,
            test=res,
            p_value_adjusted=bonferroni_adjust(res.p_value, m),
            bonferroni_multiplier=m,
        )

    # ------------------------------------------------------------------
    # Etapa 2: QDA univariante (continuo / ordinal)
    # ------------------------------------------------------------------

    def _qda_cutpoint(
        self,
        xv: np.ndarray,
        yc: np.ndarray,
        nombre: str,
        *,
        weights: np.ndarray | None = None,
    ) -> float:
        """Raiz de las log-verosimilitudes condicionales gaussianas.

            A x^2 + B x + C = 0
            A = 1/s0^2 - 1/s1^2
            B = 2 (m1/s1^2 - m0/s0^2)
            C = m0^2/s0^2 - m1^2/s1^2 + 2 ln(pi1/pi0) - ln(s1^2/s0^2)

        Root-selection modes (self.qda_root_restriction):
          - True (default, documented Fase 0 restriction): only roots inside
            the inter-means range [min(m0, m1), max(m0, m1)] are accepted;
            external roots are discarded and, if none qualifies, the
            fallback is the WEIGHTED midpoint x_bar = (W0 m0 + W1 m1)/(W0+W1).
          - False (canonical): any real root is accepted; with two real
            roots, the one closest to the weighted mean x_bar is returned
            (operational determinism, same tie-break criterion as the
            restricted path).

        Si s0^2 == s1^2: forma lineal (LDA con priors):
            t = (m0+m1)/2 - s^2 ln(pi1/pi0) / (m1 - m0)
        Varianza nula de alguna clase: fallback directo (operativo, no optimo).

        Pesos (Fase 3.2.d): con `weights`, las medias son medias
        ponderadas, los priors empiricos son pi_k = W_k / (W0 + W1) y las
        varianzas son ponderadas con correccion de Bessel ponderada

            v_k = sum_k w (x - m_k)^2 / (W_k - 1),

        donde el divisor W_k - 1 es la generalizacion natural del n - 1
        clasico cuando los pesos actuan como frecuencias. Los checks de
        tamano ("clase con < 2 obs") se evaluan sobre FILAS FISICAS
        (n0, n1); el check de varianza nula, sobre las varianzas
        ponderadas. Con weights=None (equivale a todos unos) el calculo
        reproduce el original.
        """
        y1 = yc == 1
        x0 = xv[~y1]
        x1 = xv[y1]
        n0, n1 = int(x0.size), int(x1.size)
        w = weights if weights is not None else np.ones(xv.size)
        w0 = w[~y1]
        w1 = w[y1]
        if n0 < 2 or n1 < 2:
            self._log.info("[QUEST|%r] clase con <2 obs: fallback a media", nombre)
            return float(np.average(xv, weights=w))
        w_tot0 = float(w0.sum())
        w_tot1 = float(w1.sum())
        m0 = float((w0 * x0).sum()) / w_tot0
        m1 = float((w1 * x1).sum()) / w_tot1
        v0 = float((w0 * (x0 - m0) ** 2).sum()) / (w_tot0 - 1.0)
        v1 = float((w1 * (x1 - m1) ** 2).sum()) / (w_tot1 - 1.0)
        w_tot = w_tot0 + w_tot1
        x_bar = (w_tot0 * m0 + w_tot1 * m1) / w_tot

        if v0 <= 0.0 or v1 <= 0.0:
            self._log.info(
                "[QUEST|%r] varianza nula de clase: corte operativo x_bar",
                nombre,
            )
            return float(x_bar)

        pi1 = w_tot1 / w_tot
        pi0 = w_tot0 / w_tot
        log_odds = math.log(pi1 / pi0)

        if math.isclose(v0, v1, rel_tol=1e-12):
            if m0 == m1:
                return float(x_bar)
            t = (m0 + m1) / 2.0 - v1 * log_odds / (m1 - m0)
            return float(t)

        a_coef = 1.0 / v0 - 1.0 / v1
        b_coef = 2.0 * (m1 / v1 - m0 / v0)
        c_coef = (
            m0 * m0 / v0 - m1 * m1 / v1 + 2.0 * log_odds - math.log(v1 / v0)
        )
        disc = b_coef * b_coef - 4.0 * a_coef * c_coef
        if disc < 0.0:
            self._log.info(
                "[QUEST|%r] QDA sin raices reales: fallback a x_bar", nombre
            )
            return float(x_bar)
        sq = math.sqrt(disc)
        r1 = (-b_coef + sq) / (2.0 * a_coef)
        r2 = (-b_coef - sq) / (2.0 * a_coef)
        if self.qda_root_restriction:
            # restricted mode (default): keep only roots inside the
            # inter-means range [min(m0, m1), max(m0, m1)]
            lo, hi = (m0, m1) if m0 <= m1 else (m1, m0)
            dentro = [r for r in (r1, r2) if lo <= r <= hi]
            if not dentro:
                self._log.info(
                    "[QUEST|%r] raices fuera del rango inter-medias: fallback a x_bar",
                    nombre,
                )
                return float(x_bar)
            if len(dentro) == 2 and abs(dentro[1] - x_bar) < abs(dentro[0] - x_bar):
                return float(dentro[1])  # closest to the weighted total mean
            return float(dentro[0])
        # canonical mode: accept any real root; with two real roots pick the
        # one closest to the weighted mean (operational determinism, same
        # tie-break criterion as the restricted path)
        if abs(r2 - x_bar) < abs(r1 - x_bar):
            return float(r2)
        return float(r1)

    def _gini_sweep_numeric(
        self,
        xv: np.ndarray,
        yc: np.ndarray,
        w: np.ndarray,
        nombre: str,
    ) -> float | None:
        """Barrido de Gini multiclase sobre el predictor ordenado.

        Recorre los bordes entre valores distintos de xv y devuelve el
        punto medio del borde que maximiza la ganancia de Gini sobre las
        K clases (yc ya relabelado localmente por _prepare). Devuelve
        None si todos los valores son iguales (sin corte valido).

        Duplicacion deliberada (~12 lineas) del kernel de barrido de
        CrtEngine._sweep_values: la extraccion a tree_kernels.py queda
        diferida y solo se hara si un tercer motor lo necesita (misma
        deuda ya documentada en la cabecera del modulo).
        """
        K = int(np.max(yc)) + 1
        orden = np.argsort(xv, kind="mergesort")
        xs = xv[orden]
        bordes = np.flatnonzero(xs[1:] != xs[:-1])
        if bordes.size == 0:
            self._log.info("[QUEST|%r] predictor constante: sin corte", nombre)
            return None
        ys = yc[orden]
        ws = w[orden]
        w_total = float(ws.sum())
        one_hot = (ys[:, None] == np.arange(K)[None, :]).astype(np.float64)
        cum = np.cumsum(one_hot * ws[:, None], axis=0)
        c_l = cum[bordes]
        c_r = cum[-1][None, :] - c_l
        counts_parent = cum[-1]
        p_parent = counts_parent / w_total
        i_parent = 1.0 - float((p_parent * p_parent).sum())
        d_i, _, _ = _gini_dI(c_l, c_r, i_parent, w_total)
        best = int(np.argmax(d_i))
        v_low = float(xs[bordes[best]])
        v_high = float(xs[bordes[best] + 1])
        return v_low + (v_high - v_low) / 2.0

    def _numeric_cut(
        self, xd: pd.Series, yc: np.ndarray, info: dict, nombre: str
    ) -> tuple[float | None, tuple | None]:
        """QDA sobre los valores reales (continuo / ordinal numerico -> umbral)
        o sobre los codigos del orden natural (ordinal simbolico -> branches).
        Reutiliza el xv ya calculado en _prepare (misma representacion que la
        Etapa 1)."""
        xv = info["xv"]
        labels = info.get("labels")
        if labels is not None and len(labels) < 2:
            return None, None
        K = int(np.max(yc)) + 1
        # Fase 3.4.b: K=2 -> QDA univariante (paridad). K>2 -> barrido
        # de Gini sobre el predictor seleccionado (extension documentada,
        # ver methodology.md §3.8).
        if K == 2:
            t = self._qda_cutpoint(xv, yc, nombre, weights=info["w"])
        else:
            t = self._gini_sweep_numeric(xv, yc, info["w"], nombre)
            if t is None:
                return None, None
        if labels is None:
            return t, None
        k = int(math.floor(t))
        k = min(max(k, 0), len(labels) - 2)  # ambos lados no vacios
        branches = (tuple(labels[: k + 1]), tuple(labels[k + 1 :]))
        return None, branches

    # ------------------------------------------------------------------
    # Etapa 2: particion de subconjuntos (nominal), estilo C&RT
    # ------------------------------------------------------------------

    def _subset_cut(
        self,
        xd: pd.Series,
        yc: np.ndarray,
        nombre: str,
        *,
        weights: np.ndarray | None = None,
    ) -> tuple[tuple, tuple[int, int]] | None:
        """Particion binaria por ganancia de Gini (K<=10 exhaustiva; K>10 por
        tasa supervisada). NOTA: la via K>10 es estilo Breiman/C&RT, no el
        trato de dummies+LDA de Loh & Shih 1997 (decision documentada).

        Con `weights` (Fase 3.2.d) la matriz categoria x clase acumula
        SUMAS DE PESOS, pero `child_ns` devuelto sigue siendo el CONTEO
        FISICO de filas por lado.
        """
        # defense in depth: __init__ already rejects values != "rate", but
        # the public attribute could be mutated at runtime
        if self.nominal_high_card != "rate":
            raise NotImplementedError(
                f"[QUEST|{nombre!r}] nominal_high_card={self.nominal_high_card!r} "
                "no implementado en Fase 0: reservado para Fase 3.4 "
                "(LDA + dummies; ver design_decisions.md §4.2)"
            )
        try:
            codes, uniques = pd.factorize(xd, sort=True)
        except TypeError as e:
            raise ValueError(
                f"[QUEST|{nombre!r}] categorias no factorizables: {e}"
            ) from e
        labels = tuple(uniques)
        self._require_hashable(labels, nombre)
        k_cats = len(labels)
        if k_cats < 2:
            return None
        w = weights if weights is not None else np.ones(len(xd))
        K = int(np.max(yc)) + 1
        counts = np.bincount(
            codes * K + yc, weights=w, minlength=K * k_cats
        ).reshape(k_cats, K).astype(float)
        rows_per_cat = np.bincount(codes, minlength=k_cats)  # conteo FISICO
        n_tot = float(counts.sum())
        p = counts.sum(axis=0) / n_tot
        i_parent = float(1.0 - (p * p).sum())

        if k_cats <= self.max_exhaustive_cardinality:
            masks = _masks_exhaustivas(k_cats)
            mf = masks.astype(float)
            c_r = mf @ counts
            c_l = counts.sum(axis=0)[None, :] - c_r
            d_i, n_l, n_r = _gini_dI(c_l, c_r, i_parent, n_tot)
            best = int(np.argmax(d_i))
            mask_der = masks[best]
        else:
            if counts.shape[1] == 2:
                clase = 1
            else:
                clase = int(np.argmax(counts.sum(axis=0)))
                self._log.warning(
                    "[QUEST|%r] heurística pragmática activada; se pierde "
                    "optimalidad en multiclase; considere discretizar el "
                    "predictor", nombre,
                )
            tasas = counts[:, clase] / counts.sum(axis=1)
            orden = np.argsort(-tasas, kind="stable")
            cum = np.cumsum(counts[orden], axis=0)
            c_l = cum[:-1]
            c_r = cum[-1][None, :] - c_l
            d_i, n_l, n_r = _gini_dI(c_l, c_r, i_parent, n_tot)
            bpos = int(np.argmax(d_i))
            mask_der = np.zeros(k_cats, dtype=bool)
            mask_der[orden[: bpos + 1]] = True  # derecha = tasas ALTAS

        izq = tuple(labels[g] for g in range(k_cats) if not mask_der[g])
        der = tuple(labels[g] for g in range(k_cats) if mask_der[g])
        # child_ns = CONTEO FISICO de filas por lado (no suma de pesos)
        n_l = int(rows_per_cat[~mask_der].sum())
        n_r = int(rows_per_cat[mask_der].sum())
        return (izq, der), (n_l, n_r)

    @staticmethod
    def _require_hashable(labels: tuple, predictor: str) -> None:
        for v in labels:
            try:
                hash(v)
            except TypeError:
                raise ValueError(
                    f"[QUEST|{predictor!r}] categoria no hashable {v!r}"
                ) from None
