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

Restricciones regulatorias activas:
  * MRM-INTERPRETABILIDAD: PROHIBIDO ACP/rotaciones; QDA estrictamente
    univariante -> la regla exportada es un "x <= t" o un "x in {...}"
    directamente traducible a CASE WHEN.
  * Fase 0: target EXCLUSIVAMENTE binario -> ValueError si hay mas de 2 clases.
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
    """Motor QUEST binario: seleccion insesgada + corte QDA univariante."""

    def __init__(
        self,
        *,
        alpha: float = 0.05,
        max_exhaustive_cardinality: int = 10,
        logger: logging.Logger | None = None,
    ) -> None:
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
        self.alpha = float(alpha)
        self.max_exhaustive_cardinality = int(max_exhaustive_cardinality)
        self._log = logger if logger is not None else get_logger("quest")

    # ------------------------------------------------------------------
    # API publica: etapas 1 + 2
    # ------------------------------------------------------------------

    def evaluate(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        spec: dict[str, PredictorType],
    ) -> SplitConfig | None:
        """QUEST completo en un nodo: seleccion de variable + corte.

        Nota Bonferroni: J = len(spec) = TODOS los predictores declarados por
        el llamador, incluidos los descartados por datos insuficientes
        (criterio conservador: la correccion cubre la familia de tests que se
        INTENTARON, no solo los computados).
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

        # --- target: EXCLUSIVAMENTE binario (restriccion Fase 0) ---
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
        if len(classes) > 2:
            raise ValueError(
                f"[QUEST] target no binario ({len(classes)} clases): "
                "Fase 0 soporta solo 2 clases"
            )
        if len(classes) < 2:
            self._log.warning("[QUEST] target constante: nodo puro, sin split")
            return None
        codes = yd.map({classes[0]: 0, classes[1]: 1}).to_numpy(dtype=np.int64)
        y_full = pd.Series(np.nan, index=ys.index)  # alinear con dropna por variable
        y_full.loc[yd.index] = codes

        j_total = len(spec)
        umbral = self.alpha / (2 * j_total)  # doble familia: medias + varianzas
        self._log.debug(
            "[QUEST] Etapa 1: J=%d, umbral Bonferroni=%.6g", j_total, umbral
        )

        # --- Etapa 1, familia 1: medias / asociacion ---
        preparado: dict[str, tuple] = {}
        mejor_media: tuple[float, str, str, TestResult] | None = None
        for orden, (nombre, ptype) in enumerate(spec.items()):
            pre = self._prepare(X[nombre], y_full, ptype, nombre)
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
                if info["x0"].size == 0 or info["x1"].size == 0:
                    continue
                bf = brown_forsythe(info["x0"], info["x1"])
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
            corte = self._subset_cut(xd, yc, seleccion.predictor)
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
    ) -> SplitConfig | None:
        """Alias de evaluate() para paridad de API con ChaidEngine/CrtEngine.

        QUEST siempre exige target binario (Fase 0); target_type se ignora.
        """
        return self.evaluate(X, y, spec)

    # ------------------------------------------------------------------
    # preparacion por variable (dropna defensivo; imputacion vive fuera)
    # ------------------------------------------------------------------

    def _prepare(self, x: pd.Series, y_full: pd.Series, ptype: PredictorType, nombre: str):
        """dropna conjunto por variable + TestResult de la Etapa 1."""
        mask = x.notna().to_numpy() & y_full.notna().to_numpy()
        xd = x[mask]
        yc = y_full[mask].to_numpy(dtype=np.int64)
        n = int(len(xd))
        n_drop = int((~mask).sum())
        if n_drop:
            self._log.info("[QUEST|%r] %d filas excluidas por NaN", nombre, n_drop)
        if n < 3:
            self._log.info("[QUEST|%r] <3 casos validos: excluido", nombre)
            return None

        y1 = yc == 1
        if not y1.any() or y1.all():
            # una sola clase tras dropna: sin asociacion evaluable
            return None

        if ptype == PredictorType.NOMINAL:
            tab = pd.crosstab(xd, yc)
            if tab.shape[0] < 2 or tab.shape[1] < 2:
                return None
            test = pearson_chi2(tab)
            return xd, yc, {"source": "chi2", "test": test}

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
        x0 = xv[~y1]
        x1 = xv[y1]
        if x0.size == 0 or x1.size == 0 or x0.size + x1.size <= 2:
            test = TestResult(0.0, (1, 1), 1.0)
        else:
            test = f_oneway(x0, x1)
        return xd, yc, {"source": "anova", "test": test, "x0": x0, "x1": x1,
                        "xv": xv, "labels": labels}

    def _mk_selection(
        self, nombre: str, source: str, res: TestResult, j_total: int
    ) -> QuestSelection:
        m = 2 * j_total
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

    def _qda_cutpoint(self, xv: np.ndarray, yc: np.ndarray, nombre: str) -> float:
        """Raiz de las log-verosimilitudes condicionales gaussianas.

            A x^2 + B x + C = 0
            A = 1/s0^2 - 1/s1^2
            B = 2 (m1/s1^2 - m0/s0^2)
            C = m0^2/s0^2 - m1^2/s1^2 + 2 ln(pi1/pi0) - ln(s1^2/s0^2)

        Restriccion documentada: solo se acepta raiz en el rango entre las
        medias de clase [min(m0,m1), max(m0,m1)]; puede descartar raices
        externas (decision Fase 0). Si no hay raiz valida -> fallback
        al punto medio PONDERADO x̄ = (n0 m0 + n1 m1)/N.
        Si s0^2 == s1^2: forma lineal (LDA con priors):
            t = (m0+m1)/2 - s^2 ln(pi1/pi0) / (m1 - m0)
        Varianza nula de alguna clase: fallback directo (operativo, no optimo).
        """
        y1 = yc == 1
        x0 = xv[~y1]
        x1 = xv[y1]
        n0, n1 = int(x0.size), int(x1.size)
        if n0 < 2 or n1 < 2:
            self._log.info("[QUEST|%r] clase con <2 obs: fallback a media", nombre)
            return float(xv.mean())
        m0 = float(x0.mean())
        m1 = float(x1.mean())
        v0 = float(x0.var(ddof=1))
        v1 = float(x1.var(ddof=1))
        n_tot = n0 + n1
        x_bar = (n0 * m0 + n1 * m1) / n_tot

        if v0 <= 0.0 or v1 <= 0.0:
            self._log.info(
                "[QUEST|%r] varianza nula de clase: corte operativo x_bar",
                nombre,
            )
            return float(x_bar)

        pi1 = n1 / n_tot
        pi0 = n0 / n_tot
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
        lo, hi = (m0, m1) if m0 <= m1 else (m1, m0)
        dentro = [r for r in (r1, r2) if lo <= r <= hi]
        if not dentro:
            self._log.info(
                "[QUEST|%r] raices fuera del rango inter-medias: fallback a x_bar",
                nombre,
            )
            return float(x_bar)
        if len(dentro) == 2 and abs(dentro[1] - x_bar) < abs(dentro[0] - x_bar):
            return float(dentro[1])  # la mas cercana a la media total ponderada
        return float(dentro[0])

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
        t = self._qda_cutpoint(xv, yc, nombre)
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
        self, xd: pd.Series, yc: np.ndarray, nombre: str
    ) -> tuple[tuple, tuple[int, int]] | None:
        """Particion binaria por ganancia de Gini (K<=10 exhaustiva; K>10 por
        tasa supervisada). NOTA: la via K>10 es estilo Breiman/C&RT, no el
        trato de dummies+LDA de Loh & Shih 1997 (decision documentada)."""
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
        counts = np.bincount(
            codes * 2 + yc, minlength=2 * k_cats
        ).reshape(k_cats, 2).astype(float)
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
            tasas = counts[:, 1] / counts.sum(axis=1)
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
        n_l = int(counts[~mask_der].sum())
        n_r = int(counts[mask_der].sum())
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
