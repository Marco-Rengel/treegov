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
        se ejecuta Brown-Forsythe (Brown & Forsythe 1974; Levene 1960 con
        mediana, via statistics.py) sobre las variables ordinales/continuas
        (deteccion de discriminacion por VARIANZA); gana si su p < alpha/(2J).
        Las categoricas no participan.
  ETAPA 2 - Punto de corte sobre la variable seleccionada:
      * continua/ordinal -> QDA UNIVARIANTE (raiz de las log-verosimilitudes
        condicionales gaussianas con priors empiricos pi_k = n_k/N, resuelta
        via Citardauq estable: Press et al. 2007, §5.6), con fallback al punto
        medio PONDERADO x_bar = (n0 m0 + n1 m1)/N si no hay raiz real unica en
        el rango entre medias (forma operativa, no optima; documentado).
      * nominal -> particion binaria por ganancia de Gini (Breiman, Friedman,
        Olshen & Stone 1984, caps. 2-4), EXACTAMENTE como C&RT: exhaustiva
        2^(K-1)-1 si K <= max_exhaustive_cardinality; orden por tasa
        supervisada si K > 10 (Breiman et al. 1984, §4).
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

Citas canonicas:
  Loh, W.-Y. & Shih, Y.-S. (1997). "Split Selection Methods for
    Classification Trees". Statistica Sinica 7(4), 815-840.
  Brown, M.B. & Forsythe, A.B. (1974). "Robust Tests for the Equality of
    Variances". JASA 69(346), 364-367.
  Levene, H. (1960). "Robust tests for equality of variances". In
    Contributions to Probability and Statistics, Stanford Univ. Press, 278-292.
  Breiman, L., Friedman, J.H., Olshen, R.A. & Stone, C.J. (1984).
    Classification and Regression Trees. Wadsworth (corte nominal por tasa
    y barrido de Gini multiclase).
  Kish, L. (1965). Survey Sampling. Wiley (varianza ponderada de confiabilidad).
  Press, W.H., Teukolsky, S.A., Vetterling, W.T. & Flannery, B.P. (2007).
    Numerical Recipes (3rd ed.), §5.6. Cambridge Univ. Press (raices
    cuadraticas estables de Citardauq).
  Heeringa, S.G., West, B.T. & Berglund, P.A. (2010). Applied Survey Data
    Analysis. Chapman & Hall/CRC, §§5.3-5.4 (tablas y momentos con masa
    ponderada directa; SIN correccion de diseno complejo Rao-Scott ni DEFF).

Pesos por muestra (Fase 3.2.d): `evaluate`/`best_split` aceptan
`weights` keyword-only (1D, finitos, >0). Con pesos, las "cuentas" del
ANOVA, la chi-cuadrado y el QDA pasan a ser sumas directas de masa de pesos
(sin ajuste de Rao-Scott ni reescalado por efecto de diseno DEFF):
  * ANOVA ponderado: Heeringa, West & Berglund (2010), §5.3 (masa directa).
  * chi2 de Pearson es sensible a la escala de la masa total de pesos
    (ibid., §5.4): comportamiento correcto, NO se normaliza.
  * varianza ponderada de confiabilidad de Kish (Kish 1965, "Survey Sampling";
    Heeringa, West & Berglund 2010) con divisor W_k - sum(w_i^2) / W_k:
    invariante a escala de pesos, estrictamente positivo para n_k >= 2 y
    exactamente igual a n_k - 1 cuando todos los pesos son iguales.
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
        estrictamente positivos, longitud = len(X). Con pesos, el ANOVA y el
        desempate de varianzas (Brown & Forsythe 1974; Levene 1960) aplican
        masa ponderada directa sin correccion Rao-Scott/DEFF (Heeringa, West
        & Berglund 2010, §5.3) y la chi2 de Pearson recibe una tabla con sumas
        de pesos (sensible a la escala, ibid. §5.4: comportamiento correcto,
        no se normaliza). La varianza ponderada del QDA usa el divisor
        insesgado de pesos de confiabilidad de Kish W_k - sum(w_i^2)/W_k
        (Kish 1965, Survey Sampling), invariante a escala y seguro para pesos
        normalizados. Con weights=None, el comportamiento es identico bit a
        bit al previo.
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
        # Priorizamos candidatos con estadistico finito para que un predictor
        # degenerado (F = inf por SSW = 0) no secuestre la Etapa 1 bloqueando
        # a otros predictores validos y representables en SplitConfig.
        preparado: dict[str, tuple] = {}
        mejor_media: tuple[float, str, str, TestResult] | None = None
        mejor_media_inf: tuple[float, str, str, TestResult] | None = None
        for orden, (nombre, ptype) in enumerate(spec.items()):
            pre = self._prepare(X[nombre], y_full, ptype, nombre, weights=w_full)
            if pre is None:
                continue
            xd, yc, info = pre
            preparado[nombre] = (xd, yc, info)
            res = info["test"]
            if math.isfinite(float(res.statistic)):
                if mejor_media is None or res.p_value < mejor_media[0]:
                    mejor_media = (res.p_value, nombre, info["source"], res)
            else:
                if mejor_media_inf is None or res.p_value < mejor_media_inf[0]:
                    mejor_media_inf = (res.p_value, nombre, info["source"], res)

        seleccion: QuestSelection | None = None
        if mejor_media is not None and mejor_media[0] < umbral:
            _, nombre, source, res = mejor_media
            seleccion = self._mk_selection(nombre, source, res, j_total)
        else:
            # --- Etapa 1, familia 2: desempate robusto (Brown & Forsythe 1974; Levene 1960) ---
            mejor_var: tuple[float, str, TestResult] | None = None
            mejor_var_inf: tuple[float, str, TestResult] | None = None
            for nombre, ptype in spec.items():
                if ptype == PredictorType.NOMINAL or nombre not in preparado:
                    continue
                xd, yc, info = preparado[nombre]
                xs_k = info["xs_k"]
                ws_k = info["ws_k"]
                if any(x.size == 0 for x in xs_k):
                    continue
                bf = brown_forsythe(*xs_k, weights=tuple(ws_k))
                if math.isfinite(float(bf.statistic)):
                    if mejor_var is None or bf.p_value < mejor_var[0]:
                        mejor_var = (bf.p_value, nombre, bf)
                else:
                    if mejor_var_inf is None or bf.p_value < mejor_var_inf[0]:
                        mejor_var_inf = (bf.p_value, nombre, bf)
            if mejor_var is not None and mejor_var[0] < umbral:
                _, nombre, bf = mejor_var
                seleccion = self._mk_selection(nombre, "levene", bf, j_total)
            elif mejor_media_inf is not None and mejor_media_inf[0] < umbral:
                _, nombre, source, res = mejor_media_inf
                seleccion = self._mk_selection(nombre, source, res, j_total)
            elif mejor_var_inf is not None and mejor_var_inf[0] < umbral:
                _, nombre, bf = mejor_var_inf
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
            if threshold is None and branches is None:
                return None
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

        target_type se ignora (QUEST deriva la naturaleza del target de y).
        Acepta K >= 2 desde la Fase 3.4.b. weights se propaga a evaluate
        (Fase 3.2.d).
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
        if n <= K:
            self._log.info(
                "[QUEST|%r] n=%d <= K=%d: sin grados de libertad residuales",
                nombre, n, K,
            )
            return None

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
    ) -> float | None:
        """Raiz de las log-verosimilitudes condicionales gaussianas.

            A x^2 + B x + C = 0
            A = 1/s0^2 - 1/s1^2
            B = 2 (m1/s1^2 - m0/s0^2)
            C = m0^2/s0^2 - m1^2/s1^2 + 2 ln(pi1/pi0) - ln(s1^2/s0^2)

        La cuadratica se resuelve con la formula numericamente estable de
        Citardauq (Press et al. 2007, Numerical Recipes, 3rd ed., §5.6) para
        evitar cancelacion catastrofica cuando s0^2 ≈ s1^2:
            q = -0.5 * (B + sign(B) * sqrt(B^2 - 4AC)),  r1 = q/A,  r2 = C/q.

        Root-selection modes (self.qda_root_restriction):
          - True (default, documented Fase 0 restriction): only roots (and
            linear LDA cutpoints) inside the inter-means range
            [min(m0, m1), max(m0, m1)] are accepted; external values fall
            back to the WEIGHTED midpoint x_bar = (W0 m0 + W1 m1)/(W0+W1).
          - False (canonical): any real root is accepted; with two real
            roots, the one closest to the weighted mean x_bar is returned
            (operational determinism, same tie-break criterion as the
            restricted path).

        Si s0^2 == s1^2: forma lineal (LDA con priors):
            t = (m0+m1)/2 - s^2 ln(pi1/pi0) / (m1 - m0)
        Si xv es constante (min == max) devuelve None. En cualquier caso no
        constante, una guarda de dominio garantiza que el umbral devuelto es
        finito y pertenece a [min(xv), max(xv)) para evitar ramas vacias.

        Pesos (remediado en Bloque 2E; design_decisions.md §13.4 y §31):
        con `weights`, las medias son medias ponderadas, los priors empiricos
        son pi_k = W_k / (W0 + W1) y las varianzas usan el estimador insesgado
        de pesos de confiabilidad de Kish (Kish 1965, Survey Sampling;
        Heeringa, West & Berglund 2010, §5.3, masa ponderada directa sin
        correccion Rao-Scott ni DEFF):

            v_k = sum_{i in k} w_i (x_i - m_k)^2 / (W_k - sum_{i in k} w_i^2 / W_k)

        Este divisor es estrictamente invariante a la escala de pesos
        (w -> c * w), estrictamente positivo para todo vector positivo con
        n_k >= 2 (incluidos pesos normalizados sum w_i = 1) y exactamente igual
        a n_k - 1 cuando todos los pesos son iguales (paridad exacta con
        Bessel clasico).
        """
        xmin = float(xv.min())
        xmax = float(xv.max())
        if xmin == xmax:
            self._log.info("[QUEST|%r] predictor constante: sin corte QDA", nombre)
            return None

        def _bound_cut(cand: float, fallback: float) -> float:
            out = float(cand)
            if not math.isfinite(out) or out < xmin or out >= xmax:
                out = float(fallback)
            if not math.isfinite(out) or out < xmin or out >= xmax:
                out = xmin + (xmax - xmin) / 2.0
                if not math.isfinite(out) or out < xmin or out >= xmax:
                    out = xmin
            return float(out)

        y1 = yc == 1
        x0 = xv[~y1]
        x1 = xv[y1]
        n0, n1 = int(x0.size), int(x1.size)
        w = weights if weights is not None else np.ones(xv.size)
        w0 = w[~y1]
        w1 = w[y1]
        if n0 < 2 or n1 < 2:
            self._log.info("[QUEST|%r] clase con <2 obs: fallback a media", nombre)
            x_bar = float(np.average(xv, weights=w))
            return _bound_cut(x_bar, x_bar)
        w_tot0 = float(w0.sum())
        w_tot1 = float(w1.sum())
        m0 = float((w0 * x0).sum()) / w_tot0
        m1 = float((w1 * x1).sum()) / w_tot1
        w_tot = w_tot0 + w_tot1
        x_bar = (w_tot0 * m0 + w_tot1 * m1) / w_tot

        w2_0 = float((w0 * w0).sum())
        w2_1 = float((w1 * w1).sum())
        denom0 = (
            w_tot0 - w2_0 / w_tot0
            if math.isfinite(w2_0) and w2_0 > 0.0
            else w_tot0 * (1.0 - float(((w0 / w_tot0) ** 2).sum()))
        )
        denom1 = (
            w_tot1 - w2_1 / w_tot1
            if math.isfinite(w2_1) and w2_1 > 0.0
            else w_tot1 * (1.0 - float(((w1 / w_tot1) ** 2).sum()))
        )
        if (
            denom0 <= 0.0
            or denom1 <= 0.0
            or not math.isfinite(denom0)
            or not math.isfinite(denom1)
        ):
            self._log.info(
                "[QUEST|%r] denominador Kish degenerado: corte operativo x_bar",
                nombre,
            )
            return _bound_cut(x_bar, x_bar)

        v0 = float((w0 * (x0 - m0) ** 2).sum()) / denom0
        v1 = float((w1 * (x1 - m1) ** 2).sum()) / denom1

        if v0 <= 0.0 or v1 <= 0.0 or not math.isfinite(v0) or not math.isfinite(v1):
            self._log.info(
                "[QUEST|%r] varianza nula de clase: corte operativo x_bar",
                nombre,
            )
            return _bound_cut(x_bar, x_bar)

        pi1 = w_tot1 / w_tot
        pi0 = w_tot0 / w_tot
        log_odds = math.log(pi1 / pi0)

        if math.isclose(v0, v1, rel_tol=1e-12):
            if m0 == m1:
                return _bound_cut(x_bar, x_bar)
            t = (m0 + m1) / 2.0 - v1 * log_odds / (m1 - m0)
            if self.qda_root_restriction:
                lo, hi = (m0, m1) if m0 <= m1 else (m1, m0)
                if not (lo <= t <= hi):
                    self._log.info(
                        "[QUEST|%r] corte LDA fuera del rango inter-medias: fallback a x_bar",
                        nombre,
                    )
                    return _bound_cut(x_bar, x_bar)
            return _bound_cut(t, x_bar)

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
            return _bound_cut(x_bar, x_bar)
        sq = math.sqrt(disc)
        q = -0.5 * (b_coef + (sq if b_coef >= 0.0 else -sq))
        if q == 0.0:
            r1 = r2 = 0.0
        else:
            r1 = q / a_coef
            r2 = c_coef / q
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
                return _bound_cut(x_bar, x_bar)
            if len(dentro) == 2 and abs(dentro[1] - x_bar) < abs(dentro[0] - x_bar):
                t_sel = float(dentro[1])  # closest to the weighted total mean
            else:
                t_sel = float(dentro[0])
            return _bound_cut(t_sel, x_bar)
        # canonical mode: accept any real root; with two real roots pick the
        # one closest to the weighted mean (operational determinism, same
        # tie-break criterion as the restricted path)
        t_sel = float(r2) if abs(r2 - x_bar) < abs(r1 - x_bar) else float(r1)
        return _bound_cut(t_sel, x_bar)

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
        w_oh = one_hot * ws[:, None]
        cum = np.cumsum(w_oh, axis=0)
        cum_rev = np.cumsum(w_oh[::-1], axis=0)[::-1]
        c_l = cum[bordes]
        c_r = cum_rev[bordes + 1]
        counts_parent = cum[-1]
        p_parent = counts_parent / w_total
        i_parent = max(1.0 - float((p_parent * p_parent).sum()), 0.0)
        d_i, _, _ = _gini_dI(c_l, c_r, i_parent, w_total)
        d_i = np.where(np.isfinite(d_i), d_i, -np.inf)
        best = int(np.argmax(d_i))
        if not math.isfinite(float(d_i[best])):
            return None
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
        """Particion binaria por ganancia de Gini (Breiman, Friedman, Olshen &
        Stone 1984, caps. 2-4: K<=10 exhaustiva; K>10 por tasa supervisada,
        §4). NOTA: la via K>10 es estilo Breiman et al. (1984) / C&RT, no el
        trato de dummies+LDA de Loh & Shih (1997) (decision documentada).

        Con `weights` (Fase 3.2.d) la matriz categoria x clase acumula
        SUMAS DE PESOS (masa directa sin correccion Rao-Scott/DEFF; Heeringa,
        West & Berglund 2010, §5.3), pero `child_ns` devuelto sigue siendo el
        CONTEO FISICO de filas por lado.
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
            mf_left = (~masks).astype(float)
            c_r = mf @ counts
            c_l = mf_left @ counts
            d_i, n_l, n_r = _gini_dI(c_l, c_r, i_parent, n_tot)
            d_i = np.where(np.isfinite(d_i), d_i, -np.inf)
            best = int(np.argmax(d_i))
            if not math.isfinite(float(d_i[best])):
                return None
            mask_der = masks[best]
        else:
            if counts.shape[1] == 2:
                clase = 0
            else:
                clase = int(np.argmax(counts.sum(axis=0)))
                self._log.warning(
                    "[QUEST|%r] heurística pragmática activada; se pierde "
                    "optimalidad en multiclase; considere discretizar el "
                    "predictor", nombre,
                )
            tasas = counts[:, clase] / counts.sum(axis=1)
            orden = np.argsort(-tasas, kind="stable")
            co = counts[orden]
            cum = np.cumsum(co, axis=0)
            cum_rev = np.cumsum(co[::-1], axis=0)[::-1]
            c_l = cum[:-1]
            c_r = cum_rev[1:]
            d_i, n_l, n_r = _gini_dI(c_l, c_r, i_parent, n_tot)
            d_i = np.where(np.isfinite(d_i), d_i, -np.inf)
            bpos = int(np.argmax(d_i))
            if not math.isfinite(float(d_i[bpos])):
                return None
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
