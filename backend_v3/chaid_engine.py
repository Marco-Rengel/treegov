"""Motor CHAID / Exhaustive CHAID (TreeGov, backend_v3, Fase 0, Paso 6).

Fusion iterativa de categorias guiada por significancia, con ajuste de
Bonferroni mediante los multiplicadores combinatorios de Kass (1980) y la
variante exhaustiva de Biggs, de Ville & Suen (1991).

Escala del predictor:
  - NOMINAL: cualquier par de grupos es fusionable; M = S(c, r)   (Stirling).
  - ORDINAL: solo pares de grupos ADYACENTES en el orden natural de las
    etiquetas observadas; M = C(c-1, r-1).
  - CONTINUOUS (Fase 3.10.b, H14): binning automatico por deciles
    (10 cortes de np.quantile -> 11 bins; np.digitize asigna cada fila a
    un bin 0..10). Los bins tienen orden natural: la fusion sigue la
    regla ORDINAL (adyacentes, M = C(c-1, r-1)) y los cortes viajan en
    SplitConfig.bin_edges para routing por rangos (tree_builder).

Naturaleza del target:
  - BINARY / CATEGORICAL: chi2 de Pearson sobre tabla c x K
    (gl del par = K-1; gl global = (r-1)(K-1)); sin correccion de Yates.
  - CONTINUOUS: F de ANOVA unifactorial (el p del par es el F-test entre las
    DOS submuestras del par, equivalente a t^2; F global sobre los r grupos).

Convencion del p-valor del par (criterio interno de fusion): se calcula SOLO
sobre las DOS categorias del par (subtabla 2 x K / F de 2 grupos), y en cada
paso se fusiona el par con MAYOR p (el menos significativo). Convencion de
Kass (1980), replicada por implementaciones clásicas de CHAID.

El multiplicador de Kass se aplica DESPUES de la fusion, sobre el p-valor
GLOBAL de la particion (c categorias originales -> r grupos); en Exhaustive
CHAID se evalua en CADA paso del historial y se retiene el paso con MENOR
p-valor ajustado (incluido el paso 0 sin fusiones, M=1). Esto corrige el
riesgo ALG-01 documentado en docs/model_risk_assessment.md.

Regla de frecuencias esperadas de Cochran (1954) integrada (riesgo ALG-03):
fusion forzosa ACTIVA de la categoria de menor total cuando la tabla viola
la regla; si es irreductible (r=2), se reporta cochran_ok=False + WARNING.
Las fusiones forzadas CUENTAN dentro de c -> r para el multiplicador.

Ponderacion por muestra (Fase 3.2.b): evaluate() y best_split() admiten un
parametro keyword-only `weights` (vector paralelo a x e y, estrictamente
positivo y finito). Con pesos, las celdas de la tabla c x K y los
suficientes (n, sum, sumsq) se pueblan sumando pesos en lugar de contar
filas; chi2, F, merging y Cochran operan sobre la matriz ponderada sin
cambios estructurales (sus formulas son identicas con sumas de pesos).
Los grados de libertad residuales siguen la convencion de muestras
complejas (N_filas - k, filas fisicas) y SplitConfig.child_ns reporta
siempre el CONTEO FISICO de filas por rama. Con weights=None el
comportamiento es identico bit a bit al pre-3.2.

Citas bibliograficas:
  Kass, G.V. (1980). "An Exploratory Technique for Investigating Large
    Quantities of Categorical Data". Applied Statistics 29(2), 119-127.
  Biggs, D., de Ville, B. & Suen, E. (1991). "A Method of Choosing Multiway
    Partitions for Classification and Decision Trees". Journal of Applied
    Statistics 18(1), 49-62.
  Cochran, W.G. (1954). "Some Methods for Strengthening the Common Chi-2
    Tests". Biometrics 10(4), 417-451.
  Heeringa, S.G., West, B.T. & Berglund, P.A. (2010). Applied Survey
    Data Analysis. Chapman & Hall/CRC, seccion 5.3 (estadisticos con
    conteos ponderados; df residual basado en filas fisicas).

Dependencias permitidas: numpy, pandas, scipy.stats (y log_config/statistics/
types de backend_v3). Datos crudos tocados UNA sola vez O(N) (crosstab /
bincount); todo el bucle opera sobre la tabla (c, K) o sobre los tres
suficientes estadisticos por categoria (n, suma, suma de cuadrados).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import chi2 as _chi2_dist
from scipy.stats import f as _f_dist

from .log_config import get_logger
from .statistics import TestResult, bonferroni_adjust, kass_multiplier, pearson_chi2
from .types import PredictorType, SplitConfig, TargetType

__all__ = ["ChaidEngine", "MergeDiagnostics", "MergeStep"]

_COCHRAN_MIN_E: float = 1.0    # ninguna frecuencia esperada puede ser < 1
_COCHRAN_FRAC_LT5: float = 0.20  # a lo sumo el 20% de celdas con E < 5


@dataclass(frozen=True)
class MergeStep:
    """Un paso del historial de fusion (auditoria de Exhaustive CHAID).

    merged_pair   : indices (i, j) de los grupos fusionados EN el estado
                    previo; () en el paso inicial (r = c).
    pair_p_value  : p del par fusionado (chi2 2xK / F de 2 grupos);
                    NaN en el paso inicial.
    global_p_value: p de la evaluacion global tras el paso (crudo).
    adjusted_p_value: global * M(c, r) truncado a 1 (Bonferroni de Kass).
    """

    n_groups: int
    merged_pair: tuple[int, ...]
    pair_p_value: float
    global_p_value: float
    adjusted_p_value: float


@dataclass(frozen=True)
class MergeDiagnostics:
    """Diagnostico auditable del ultimo evaluate() del motor."""

    n_categories: int
    n_final_groups: int
    n_forced_merges: int
    cochran_ok: bool
    n_rows_dropped_nan: int
    exhaustive_steps: tuple[MergeStep, ...]


class ChaidEngine:
    """Motor CHAID clasico y Exhaustive CHAID sobre un predictor por nodo.

    Convenciones canonicas implementadas (ver docstring del modulo):
      - p del par sobre la subtabla/par aislado (Kass 1980; Biggs et al. 1991);
      - fusion del par con MAYOR p (el menos significativo), empates por
        orden lexicografico: determinismo total;
      - clasico: detiene cuando max p_par <= alpha_merge;
      - exhaustivo: fusiona hasta r=2, registra historial y retiene el paso
        de MENOR p ajustado de Kass (incluido el paso 0); empate -> menor r;
      - Cochran (1954) activo: fusion forzosa de la categoria de menor total.
    """

    def __init__(
        self,
        *,
        alpha_merge: float = 0.05,
        alpha_split: float = 0.05,
        exhaustive: bool = False,
        logger: logging.Logger | None = None,
    ) -> None:
        for nombre, a in (("alpha_merge", alpha_merge), ("alpha_split", alpha_split)):
            if isinstance(a, bool) or not (0.0 < float(a) < 1.0):
                raise ValueError(f"{nombre} debe estar en (0, 1) (recibido {a!r})")
        if not isinstance(exhaustive, bool):
            raise TypeError(f"exhaustive debe ser bool (recibido {exhaustive!r})")
        self.alpha_merge = float(alpha_merge)
        self.alpha_split = float(alpha_split)
        self.exhaustive = exhaustive
        self._log = logger if logger is not None else get_logger("chaid")
        self._diagnostics: MergeDiagnostics | None = None

    @property
    def diagnostics(self) -> MergeDiagnostics:
        """Diagnostico del ultimo evaluate() (error si nunca se llamo)."""
        if self._diagnostics is None:
            raise RuntimeError("ChaidEngine aun no ha evaluado ningun predictor")
        return self._diagnostics

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------

    def evaluate(
        self,
        x: pd.Series,
        y: pd.Series,
        *,
        predictor: str,
        predictor_type: PredictorType,
        target_type: TargetType,
        weights: np.ndarray | None = None,
    ) -> SplitConfig | None:
        """Evalua UN predictor en UN nodo.

        Devuelve el SplitConfig candidato, o None si no procede dividir
        (c < 2, K < 2, N insuficiente, la fusion converge a r = 1,
        p_adj > alpha_split, o separacion perfecta con F global infinito).

        `weights` (keyword-only, default None): vector de pesos paralelo a
        `x` e `y`; array 1D de la misma longitud, valores finitos y
        estrictamente positivos. Con pesos, las celdas de las tablas y los
        suficientes se pueblan sumando pesos (ver docstring del modulo).
        Con weights=None el comportamiento es identico al pre-3.2.
        Cita: Heeringa, West & Berglund (2010), sec. 5.3.

        Fase 3.10.b (H14): predictor_type=CONTINUOUS se admite via
        binning automatico por deciles (ver _reduce_continuous_predictor).
        """
        if not isinstance(predictor_type, PredictorType):
            raise TypeError(f"predictor_type invalido: {predictor_type!r}")
        if not isinstance(target_type, TargetType):
            raise TypeError(f"target_type invalido: {target_type!r}")

        xs = pd.Series(x) if not isinstance(x, pd.Series) else x
        ys = pd.Series(y) if not isinstance(y, pd.Series) else y
        if len(xs) != len(ys):
            raise ValueError(
                f"[CHAID|{predictor!r}] x (n={len(xs)}) e y (n={len(ys)}) "
                "deben tener la misma longitud"
            )

        # -- validacion de pesos (paralelos a x e y) --
        if weights is not None:
            try:
                w = np.asarray(weights, dtype=float)
            except (TypeError, ValueError) as e:
                raise ValueError(
                    f"[CHAID|{predictor!r}] weights no convertible a vector "
                    f"numerico: {e}"
                ) from e
            if w.ndim != 1 or w.size != len(xs):
                raise ValueError(
                    f"[CHAID|{predictor!r}] weights debe ser un vector 1D de "
                    f"longitud {len(xs)} (shape={w.shape})"
                )
            if not np.all(np.isfinite(w)):
                raise ValueError(
                    f"[CHAID|{predictor!r}] weights contiene NaN o infinitos"
                )
            if np.any(w <= 0.0):
                raise ValueError(
                    f"[CHAID|{predictor!r}] weights contiene pesos no "
                    "estrictamente positivos"
                )

        # -- dropna conjunto: la decision sobre MISSING es del llamador (ALG-04) --
        mask = xs.notna().to_numpy() & ys.notna().to_numpy()
        n_dropped = int((~mask).sum())
        xd = xs[mask]
        yd = ys[mask]
        wd = w[mask] if weights is not None else None
        n_total = int(len(xd))

        # TODO(zona_gris): un predictor CONTINUOUS binnado se trata como
        # ORDINAL (bins con orden natural: fusiones solo adyacentes y
        # Kass = C(c-1, r-1), convencion de Kass 1980 para categorias
        # ordenadas). Resolver si se prefiere tratamiento NOMINAL.
        ordinal = predictor_type in (PredictorType.ORDINAL, PredictorType.CONTINUOUS)
        continuo = target_type == TargetType.CONTINUOUS

        # -- reduccion O(N) unica: tabla (c, K) o sumas suficientes por categoria --
        bin_edges: tuple[float, ...] = ()
        if predictor_type == PredictorType.CONTINUOUS:
            base_b = self._reduce_continuous_predictor(
                xd, yd, predictor, wd, target_continuo=continuo
            )
            if base_b is None:
                return self._finish_none(predictor, 0, 0, 0, True, n_dropped, ())
            labels, matrix, counts, bin_edges = base_b
        else:
            if continuo:
                base = self._reduce_continuous(xd, yd, predictor, wd)
            else:
                base = self._reduce_categorical(xd, yd, predictor, wd)
            if base is None:
                return self._finish_none(predictor, 0, 0, 0, True, n_dropped, ())
            # labels: categorias ordenadas; matrix: (c, K) o (c, 3);
            # counts: conteo FISICO de filas por categoria (para child_ns y df).
            labels, matrix, counts = base
        c = len(labels)
        self._require_hashable(labels, predictor)

        if c < 2:
            self._log.debug(
                "[CHAID|%r] c=%d < 2: predictor constante, sin particion posible",
                predictor, c,
            )
            return self._finish_none(predictor, c, c, 0, True, n_dropped, ())
        if not continuo:
            k_classes = matrix.shape[1]
            if k_classes < 2:
                self._log.warning(
                    "[CHAID|%r] target constante en el nodo (K=%d): sin asociacion posible",
                    predictor, k_classes,
                )
                return self._finish_none(predictor, c, c, 0, True, n_dropped, ())
            if n_total < 2 * k_classes:
                self._log.warning(
                    "[CHAID|%r] N=%d < 2K=%d: muestra insuficiente",
                    predictor, n_total, 2 * k_classes,
                )
                return self._finish_none(predictor, c, c, 0, True, n_dropped, ())
        else:
            if n_total <= c:
                self._log.warning(
                    "[CHAID|%r] N=%d <= c=%d: sin grados de libertad residuales",
                    predictor, n_total, c,
                )
                return self._finish_none(predictor, c, c, 0, True, n_dropped, ())

        self._log.debug(
            "[CHAID|%r] inicio: N=%d c=%d modo=%s exhaustive=%s dropped=%d",
            predictor, n_total, c, "continuo" if continuo else "categorico",
            self.exhaustive, n_dropped,
        )
        self._log.debug(
            "[CHAID|%r] ponderacion: %s",
            predictor,
            "sin pesos" if wd is None
            else f"con pesos (suma total={float(wd.sum()):.6g})",
        )

        # -- bucle de fusion --
        if predictor_type == PredictorType.CONTINUOUS:
            # Bins vacios (empates en los cuantiles): se pre-fusionan con el
            # bin no vacio superior mas cercano. Garantiza child_ns > 0 y
            # que las ramas cubren TODOS los bins (routing por bin_edges).
            groups: list[tuple[int, ...]] = self._premerge_empty_bins(counts)
        else:
            groups = [(i,) for i in range(c)]
        steps: list[MergeStep] = []
        states: list[tuple[tuple[int, ...], ...]] = [tuple(groups)]
        n_forced = 0

        if self.exhaustive:
            steps.append(self._record_step(groups, c, matrix, continuo, ordinal, (), math.nan, counts))

        while len(groups) > 1:
            r = len(groups)

            # -- Cochran (1954): fusion forzosa activa, solo target categorico --
            if not continuo and r > 2:
                tabla = self._groups_table(matrix, groups)
                expected = self._expected(tabla)
                violada, n_lt1, frac_lt5 = _cochran_status(expected)
                if violada:
                    i_sel, j_sel = self._forced_pair(matrix, groups, ordinal)
                    self._log.warning(
                        "[CHAID|%r][Cochran] fusion forzada de grupos %d y %d "
                        "(E<1: %d celdas, E<5: %.1f%% > 20%%)",
                        predictor, i_sel, j_sel, n_lt1, 100.0 * frac_lt5,
                    )
                    p_forced = self._pair_p_value(matrix, groups, i_sel, j_sel)
                    groups = self._fuse(groups, i_sel, j_sel)
                    n_forced += 1
                    if self.exhaustive:
                        steps.append(
                            self._record_step(groups, c, matrix, continuo, ordinal,
                                              (i_sel, j_sel), p_forced, counts)
                        )
                        states.append(tuple(groups))
                    continue

            # -- paso de significancia: fusionar el par con MAYOR p --
            pv = self._pair_pvalues(matrix, groups, ordinal, continuo, counts)
            idx = int(np.argmax(pv, axis=None))  # -inf en no elegibles
            i_sel, j_sel = np.unravel_index(idx, pv.shape)
            p_max = float(pv[i_sel, j_sel])

            if self.exhaustive:
                if r == 2:
                    break  # nunca se converge a r = 1
                groups = self._fuse(groups, i_sel, j_sel)
                steps.append(
                    self._record_step(groups, c, matrix, continuo, ordinal,
                                      (i_sel, j_sel), p_max, counts)
                )
                states.append(tuple(groups))
                continue
            if p_max > self.alpha_merge:
                groups = self._fuse(groups, i_sel, j_sel)
                continue
            break

        # -- seleccion del estado final --
        if self.exhaustive:
            best = min(
                range(len(steps)),
                key=lambda t: (steps[t].adjusted_p_value, steps[t].n_groups),
            )
            groups = list(states[best])
        r = len(groups)
        if r < 2:
            self._log.info(
                "[CHAID|%r] la fusion convergio a r=1: predictor sin split", predictor
            )
            return self._finish_none(
                predictor, c, 1, n_forced, True, n_dropped, tuple(steps)
            )

        # -- evaluacion global de la particion elegida + ajuste de Kass --
        res = self._global_test(matrix, groups, continuo, counts)
        if math.isinf(res.statistic):
            # Separacion perfecta con varianza interna nula: F no es finito y
            # SplitConfig exige statistic finito; se reporta como no split.
            self._log.warning(
                "[CHAID|%r] F global infinito (separacion perfecta, SSW=0): "
                "no representable en SplitConfig; se reporta None",
                predictor,
            )
            return self._finish_none(
                predictor, c, r, n_forced, True, n_dropped, tuple(steps)
            )
        m_kass = kass_multiplier(c, r, ordinal=ordinal)
        p_adj = bonferroni_adjust(res.p_value, m_kass)

        # -- Cochran de la tabla final (flag de auditoria; el r=2 irreductible) --
        if continuo:
            cochran_ok = True  # la regla de Cochran solo aplica a tablas
        else:
            tabla_fin = self._groups_table(matrix, groups)
            cochran_ok = not _cochran_status(self._expected(tabla_fin))[0]
            if not cochran_ok:
                self._log.warning(
                    "[CHAID|%r][Cochran] violacion irreductible en la tabla FINAL "
                    "(r=2); p-valores asintoticos cuestionables",
                    predictor,
                )

        if p_adj > self.alpha_split:
            self._log.info(
                "[CHAID|%r] descartado: p_adj=%.6g > alpha_split=%.6g",
                predictor, p_adj, self.alpha_split,
            )
            return self._finish_none(
                predictor, c, r, n_forced, cochran_ok, n_dropped, tuple(steps)
            )

        branches_labels = tuple(tuple(labels[i] for i in g) for g in groups)
        # child_ns es SIEMPRE el conteo fisico de filas por rama (nunca
        # sumas de pesos): sus valores son enteros y suman N filas del nodo.
        child_ns = tuple(int(counts[list(g)].sum()) for g in groups)

        config = SplitConfig(
            predictor=predictor,
            method="CHAID_EXHAUSTIVE" if self.exhaustive else "CHAID",
            statistic=res.statistic,
            statistic_name="f" if continuo else "chi2",
            df=res.df,
            parent_n=n_total,
            child_ns=child_ns,
            p_value=res.p_value,
            p_value_adjusted=p_adj,
            bonferroni_multiplier=m_kass,
            n_merges=c - r,
            branches=branches_labels,
            bin_edges=bin_edges,
        )
        self._diagnostics = MergeDiagnostics(
            n_categories=c,
            n_final_groups=r,
            n_forced_merges=n_forced,
            cochran_ok=cochran_ok,
            n_rows_dropped_nan=n_dropped,
            exhaustive_steps=tuple(steps),
        )
        self._log.info(
            "[CHAID|%r] split: r=%d %s=%.6g p=%.6g M=%d p_adj=%.6g merges=%d "
            "(forzadas=%d) cochran_ok=%s",
            predictor, r, config.statistic_name, config.statistic, res.p_value,
            m_kass, p_adj, c - r, n_forced, cochran_ok,
        )
        return config

    def best_split(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        spec: dict[str, PredictorType],
        *,
        target_type: TargetType,
        weights: np.ndarray | None = None,
    ) -> SplitConfig | None:
        """Mejor predictor del nodo: evaluate() sobre spec y min p_adj.

        Criterio deterministico: menor p_value_adjusted; empate -> menor
        p_value crudo; persiste -> mayor statistic; el orden de spec fija
        el ultimo desempate. `weights` (keyword-only) se propaga a cada
        llamada a evaluate().
        """
        candidatos: list[SplitConfig] = []
        for nombre, ptype in spec.items():
            if nombre not in X.columns:
                raise ValueError(f"[best_split] predictor ausente en X: {nombre!r}")
            cfg = self.evaluate(
                X[nombre], y, predictor=nombre, predictor_type=ptype,
                target_type=target_type, weights=weights,
            )
            if cfg is not None:
                candidatos.append(cfg)
        if not candidatos:
            self._log.info("[best_split] ningun predictor supero alpha_split=%.6g",
                           self.alpha_split)
            return None
        best = min(
            candidatos,
            key=lambda s: (
                float(s.p_value_adjusted),
                float(s.p_value),
                -float(s.statistic),
            ),
        )
        self._log.info(
            "[best_split] ganador: %r (p_adj=%.6g) entre %d candidatos",
            best.predictor, best.p_value_adjusted, len(candidatos),
        )
        return best

    # ------------------------------------------------------------------
    # reduccion O(N) de datos crudos
    # ------------------------------------------------------------------

    def _reduce_categorical(
        self, xd: pd.Series, yd: pd.Series, predictor: str,
        weights: np.ndarray | None = None,
    ) -> tuple[tuple, np.ndarray, np.ndarray] | None:
        """(etiquetas ordenadas, tabla (c, K) de floats, conteos fisicos (c,)).

        Sin pesos: pd.crosstab(x, y); los conteos fisicos son las sumas de
        fila de la tabla. Con pesos: la celda (i, j) acumula la SUMA DE
        PESOS de las filas con esa combinacion (via factorize + bincount
        ponderado, mismo orden de categorias que pd.factorize(sort=True)),
        y los conteos fisicos se calculan aparte con bincount sin pesos.
        """
        if weights is None:
            try:
                tab = pd.crosstab(xd, yd)
            except TypeError as e:
                raise ValueError(
                    f"[CHAID|{predictor!r}] valores no tabulables en x/y: {e}"
                ) from e
            matrix = tab.to_numpy(dtype=float)
            return tuple(tab.index), matrix, matrix.sum(axis=1)
        try:
            codes_x, uniques_x = pd.factorize(xd, sort=True)
            codes_y, uniques_y = pd.factorize(yd, sort=True)
        except TypeError as e:
            raise ValueError(
                f"[CHAID|{predictor!r}] valores no tabulables en x/y: {e}"
            ) from e
        c, k = len(uniques_x), len(uniques_y)
        matrix = np.bincount(
            codes_x * k + codes_y, weights=weights, minlength=c * k
        ).reshape(c, k)
        counts = np.bincount(codes_x, minlength=c).astype(float)
        return tuple(uniques_x), matrix, counts

    def _reduce_continuous(
        self, xd: pd.Series, yd: pd.Series, predictor: str,
        weights: np.ndarray | None = None,
    ) -> tuple[tuple, np.ndarray, np.ndarray] | None:
        """Suficientes estadisticos por categoria: matrix[:, 0:3] = (n, sum, sumsq).

        Sin pesos: n_i = conteo de filas. Con pesos: n_i = SUMA DE PESOS
        (W_i), s_i = sum w*y, q_i = sum w*y^2 (Heeringa et al. 2010,
        sec. 5.3); el conteo fisico de filas viaja aparte en `counts`.
        """
        yv = yd.to_numpy(dtype=float)
        try:
            codes, uniques = pd.factorize(xd, sort=True)
        except TypeError as e:
            raise ValueError(
                f"[CHAID|{predictor!r}] valores no factorizables en x: {e}"
            ) from e
        c = len(uniques)
        counts = np.bincount(codes, minlength=c).astype(float)
        if weights is None:
            n_i = counts
            s_i = np.bincount(codes, weights=yv, minlength=c)
            q_i = np.bincount(codes, weights=yv * yv, minlength=c)
        else:
            n_i = np.bincount(codes, weights=weights, minlength=c)
            s_i = np.bincount(codes, weights=weights * yv, minlength=c)
            q_i = np.bincount(codes, weights=weights * yv * yv, minlength=c)
        matrix = np.column_stack([n_i, s_i, q_i])
        return tuple(uniques), matrix, counts

    def _reduce_continuous_predictor(
        self, xd: pd.Series, yd: pd.Series, predictor: str,
        weights: np.ndarray | None = None,
        target_continuo: bool = False,
    ) -> tuple[tuple, np.ndarray, np.ndarray, tuple[float, ...]] | None:
        """Binning automatico por deciles de un predictor CONTINUOUS (H14).

        10 cortes internos (cuantiles 1/11..10/11 via np.quantile,
        deduplicados) -> hasta 11 bins; np.digitize asigna cada fila a un
        bin 0..len(edges). Devuelve (labels, matrix, counts, bin_edges)
        con la misma convencion que _reduce_categorical/_reduce_continuous:
          - labels: ("bin_0", ..., "bin_c"), una por bin POSIBLE. Los bins
            vacios (empates en los cuantiles) se CONSERVAN con fila de
            ceros: las ramas deben cubrir todos los bins para que el
            routing por rangos (bin_edges) sea exhaustivo en OOS; el
            bucle de fusion los absorbe via _premerge_empty_bins.
          - matrix: tabla (bins, K) de floats (target categorico; celdas
            ponderadas si `weights` no es None) o suficientes
            (n, sum, sumsq) por bin (target continuo).
          - counts: conteo FISICO de filas por bin.
          - bin_edges: cortes usados (tupla creciente de floats).
        """
        try:
            xv = xd.to_numpy(dtype=float)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"[CHAID|{predictor!r}] predictor CONTINUOUS no numerico: {e}"
            ) from e
        if xv.size == 0:
            return None
        edges = np.unique(np.quantile(xv, np.linspace(0.0, 1.0, 12)[1:-1]))
        codes = np.digitize(xv, edges)                       # 0..len(edges)
        c = int(edges.size) + 1
        labels = tuple(f"bin_{i}" for i in range(c))
        counts = np.bincount(codes, minlength=c).astype(float)
        if target_continuo:
            yv = yd.to_numpy(dtype=float)
            if weights is None:
                n_i = counts
                s_i = np.bincount(codes, weights=yv, minlength=c)
                q_i = np.bincount(codes, weights=yv * yv, minlength=c)
            else:
                n_i = np.bincount(codes, weights=weights, minlength=c)
                s_i = np.bincount(codes, weights=weights * yv, minlength=c)
                q_i = np.bincount(codes, weights=weights * yv * yv, minlength=c)
            matrix = np.column_stack([n_i, s_i, q_i])
        else:
            try:
                codes_y, _uniques_y = pd.factorize(yd, sort=True)
            except TypeError as e:
                raise ValueError(
                    f"[CHAID|{predictor!r}] valores no tabulables en y: {e}"
                ) from e
            k = len(_uniques_y)
            if weights is None:
                matrix = np.bincount(
                    codes * k + codes_y, minlength=c * k
                ).reshape(c, k).astype(float)
            else:
                matrix = np.bincount(
                    codes * k + codes_y, weights=weights, minlength=c * k
                ).reshape(c, k)
        return labels, matrix, counts, tuple(float(e) for e in edges)

    @staticmethod
    def _premerge_empty_bins(counts: np.ndarray) -> list[tuple[int, ...]]:
        """Grupos iniciales para un predictor CONTINUOUS binnado.

        Cada bin vacio se pre-fusiona con el bin no vacio inmediatamente
        superior (el bin mas alto nunca esta vacio: contiene el maximo de
        x). Determinista y respeta el orden natural de los bins; estas
        fusiones estructurales CUENTAN dentro de c -> r para el
        multiplicador de Kass (c es el nº total de bins).
        """
        c = len(counts)
        grupos: list[list[int]] = []
        pendientes: list[int] = []   # bins vacios a la espera de absorcion
        for i in range(c):
            if counts[i] > 0:
                grupos.append([*pendientes, i])
                pendientes = []
            else:
                pendientes.append(i)
        if pendientes:               # salvaguarda (no alcanzable: ver docstring)
            grupos[-1].extend(pendientes)
        return [tuple(g) for g in grupos]

    # ------------------------------------------------------------------
    # algebra sobre grupos (todo opera sobre tabla/suficientes, nunca O(N))
    # ------------------------------------------------------------------

    @staticmethod
    def _groups_table(base: np.ndarray, groups: list[tuple[int, ...]]) -> np.ndarray:
        """Tabla (r, K) sumando filas de las categorias de cada grupo."""
        return np.stack([base[list(g), :].sum(axis=0) for g in groups], axis=0)

    @staticmethod
    def _groups_stats(base: np.ndarray, groups: list[tuple[int, ...]]) -> np.ndarray:
        """Suficientes (n, sum, sumsq) por grupo: (r, 3)."""
        return np.stack([base[list(g), :].sum(axis=0) for g in groups], axis=0)

    @staticmethod
    def _expected(tabla: np.ndarray) -> np.ndarray:
        """E_ij = R_i * C_j / N (marginales estrictamente positivos aqui)."""
        row = tabla.sum(axis=1, keepdims=True)
        col = tabla.sum(axis=0, keepdims=True)
        return row * col / float(tabla.sum())

    @staticmethod
    def _group_sizes(
        matrix: np.ndarray, groups: list[tuple[int, ...]], continuo: bool
    ) -> np.ndarray:
        """n por grupo. continuo=True: columna 0 de los suficientes (n, sum,
        sumsq); continuo=False: suma total de la fila de la tabla c x K.
        (El flag es explicito: una tabla categorica con K=3 clases tambien
        tiene 3 columnas; NO es seguro inferir el layout por la forma.)"""
        if continuo:
            return np.array([matrix[list(g), 0].sum() for g in groups], dtype=float)
        return np.array([matrix[list(g), :].sum() for g in groups], dtype=float)

    # ------------------------------------------------------------------
    # p-valores de par vectorizados
    # ------------------------------------------------------------------

    @staticmethod
    def _eligible_mask(groups: list[tuple[int, ...]], ordinal: bool) -> np.ndarray:
        """Matriz (r, r) bool: pares elegibles. Nominal: todos i != j.
        Ordinal: grupos cuyos intervalos de categorias originales son
        contiguos (hi_a + 1 == lo_b o viceversa). Diagonal: False."""
        r = len(groups)
        if not ordinal:
            mask = np.ones((r, r), dtype=bool)
            np.fill_diagonal(mask, False)
            return mask
        lo = np.array([min(g) for g in groups], dtype=int)
        hi = np.array([max(g) for g in groups], dtype=int)
        return (hi[:, None] + 1 == lo[None, :]) | (hi[None, :] + 1 == lo[:, None])

    def _pair_pvalues(
        self, matrix: np.ndarray, groups: list[tuple[int, ...]],
        ordinal: bool, continuo: bool,
        counts: np.ndarray | None = None,
    ) -> np.ndarray:
        """Matriz (r, r) de p-valores de par; -inf donde no elegible."""
        r = len(groups)
        eligible = self._eligible_mask(groups, ordinal)
        if continuo:
            p = self._pair_pvalues_f(matrix, groups, counts)
        else:
            p = self._pair_pvalues_chi2(matrix, groups)
        return np.where(eligible, p, -np.inf)

    def _pair_pvalues_chi2(
        self, matrix: np.ndarray, groups: list[tuple[int, ...]]
    ) -> np.ndarray:
        """p del par (i, j) = chi2 de la subtabla 2xK del par, gl = K - 1.

        Vectorizado por triu_indices: todas las subtablas a la vez.
        Celdas con E = 0 (clase ausente en AMBAS categorias del par)
        aportan 0 por convencion 0/0 -> 0. gl se mantiene K-1 (las clases
        del problema son fijas).
        """
        tabla = self._groups_table(matrix, groups)
        r, k = tabla.shape
        i0, i1 = np.triu_indices(r, k=1)
        obs = np.stack([tabla[i0], tabla[i1]], axis=1)        # (P, 2, K)
        row_tot = obs.sum(axis=2)                             # (P, 2)
        col_tot = obs.sum(axis=1)                             # (P, K)
        n_tot = row_tot.sum(axis=1)                           # (P,)
        expected = row_tot[:, :, None] * col_tot[:, None, :] / n_tot[:, None, None]
        diff2 = (obs - expected) ** 2
        term = np.divide(diff2, expected, out=np.zeros_like(diff2),
                         where=expected > 0.0)
        stat = term.sum(axis=(1, 2))
        p = _chi2_dist.sf(stat, k - 1)
        out = np.full((r, r), -np.inf)
        out[i0, i1] = p
        out[i1, i0] = p
        return out

    def _pair_pvalues_f(
        self, matrix: np.ndarray, groups: list[tuple[int, ...]],
        counts: np.ndarray | None = None,
    ) -> np.ndarray:
        """p del par (i, j) = F-test entre las DOS submuestras (F = t^2).

        Formas cerradas sobre suficientes (n, sum, sumsq):
            SSB = n_i n_j (media_i - media_j)^2 / (n_i + n_j)       (>= 0)
            SSW = (q_i - s_i^2/n_i) + (q_j - s_j^2/n_j)             (clip 0)
            F   = SSB / (SSW / (n-2)),  df = (1, n-2)
        Casos degenerados (misma convencion que statistics._f_ratio):
            SSW=0 & SSB>0 -> F=inf, p=0 ; SSW=0 & SSB=0 -> p=1.
        n_par < 3 (df2 < 1): p = 1  (sin evidencia: el par es infusionable).

        Con `counts` (camino ponderado): n_i/n_j de las formulas son sumas
        de pesos (W_i, W_j), pero df2 usa el conteo FISICO de filas del
        par (convencion de muestras complejas, Heeringa et al. 2010).
        """
        st = self._groups_stats(matrix, groups)
        r = st.shape[0]
        n_i, s_i, q_i = st[:, 0], st[:, 1], st[:, 2]
        i0, i1 = np.triu_indices(r, k=1)
        na, nb = n_i[i0], n_i[i1]
        sa, sb = s_i[i0], s_i[i1]
        qa, qb = q_i[i0], q_i[i1]
        n_par = na + nb
        mean_a = sa / na
        mean_b = sb / nb
        ss_between = na * nb * (mean_a - mean_b) ** 2 / n_par
        ss_within = np.maximum(
            (qa - sa * sa / na) + (qb - sb * sb / nb), 0.0
        )
        if counts is None:
            df2 = n_par - 2.0
        else:
            cnt_g = np.array([counts[list(g)].sum() for g in groups])
            df2 = cnt_g[i0] + cnt_g[i1] - 2.0

        p = np.ones_like(n_par)                    # default: p = 1
        ssw_pos = ss_within > 0.0
        ok = df2 >= 1.0
        sel = ok & ssw_pos
        fvals = np.zeros_like(n_par)
        fvals[sel] = ss_between[sel] * df2[sel] / ss_within[sel]
        p[sel] = _f_dist.sf(fvals[sel], 1, df2[sel])
        p[ok & ~ssw_pos & (ss_between > 0.0)] = 0.0  # separacion perfecta del par

        out = np.full((r, r), -np.inf)
        out[i0, i1] = p
        out[i1, i0] = p
        return out

    # ------------------------------------------------------------------
    # fusion y evaluacion global
    # ------------------------------------------------------------------

    @staticmethod
    def _fuse(
        groups: list[tuple[int, ...]], i: int, j: int
    ) -> list[tuple[int, ...]]:
        """Fusiona los grupos i y j (union ordenada); conserva posiciones:
        el grupo fusionado ocupa el indice menor y se elimina el mayor."""
        a, b = (i, j) if i < j else (j, i)
        merged = tuple(sorted(groups[a] + groups[b]))
        new = list(groups)
        new[a] = merged
        del new[b]
        return new

    def _global_test(
        self, matrix: np.ndarray, groups: list[tuple[int, ...]],
        continuo: bool, counts: np.ndarray | None = None,
    ) -> TestResult:
        """Evaluacion global de la particion actual (statistics.py).

        `counts`: conteos fisicos de filas por categoria; se usan para los
        grados de libertad cuando la matriz contiene sumas de pesos.
        """
        if not continuo:
            return pearson_chi2(self._groups_table(matrix, groups))
        return self._f_from_sufficients(matrix, groups, counts)

    @staticmethod
    def _f_from_sufficients(
        matrix: np.ndarray, groups: list[tuple[int, ...]],
        counts: np.ndarray | None = None,
    ) -> TestResult:
        """F global one-way desde suficientes (n, sum, sumsq) por grupo.

            SSB = sum_g s_g^2/n_g - (sum s_g)^2/N        (clip a 0)
            SSW = sum_g (q_g - s_g^2/n_g)                (clip a 0)
            F = (SSB/(r-1)) / (SSW/(N-r))
        Misma convencion degenerada que statistics._f_ratio:
        SSW=0&SSB>0 -> F=inf, p=0 ; SSW=0&SSB=0 -> F=0, p=1.
        (df2 = N-r > 0 garantizado por la guarda N > c de evaluate().)

        Con `counts` (camino ponderado): n_g/N de las formulas son sumas
        de pesos (W_g, W_total), pero df2 sigue la convencion de muestras
        complejas: N_filas - r, con N_filas = suma de conteos fisicos.
        """
        st = ChaidEngine._groups_stats(matrix, groups)
        n_g, s_g, q_g = st[:, 0], st[:, 1], st[:, 2]
        r = st.shape[0]
        n_total = float(n_g.sum())
        total = float(s_g.sum())
        ss_between = max(float((s_g * s_g / n_g).sum()) - total * total / n_total, 0.0)
        ss_within = max(float((q_g - s_g * s_g / n_g).sum()), 0.0)
        df1 = r - 1
        if counts is None:
            df2 = int(n_total) - r
        else:
            df2 = int(float(counts.sum())) - r
        if ss_within <= 0.0:
            if ss_between > 0.0:
                return TestResult(math.inf, (df1, df2), 0.0)
            return TestResult(0.0, (df1, df2), 1.0)
        stat = (ss_between / df1) / (ss_within / df2)
        return TestResult(float(stat), (df1, df2), float(_f_dist.sf(stat, df1, df2)))

    def _record_step(
        self,
        groups: list[tuple[int, ...]],
        c: int,
        matrix: np.ndarray,
        continuo: bool,
        ordinal: bool,
        merged_pair: tuple[int, ...],
        pair_p: float,
        counts: np.ndarray | None = None,
    ) -> MergeStep:
        """Evaluacion global + Kass del estado actual (historial exhaustive)."""
        res = self._global_test(matrix, groups, continuo, counts)
        stat_inf = math.isinf(res.statistic)
        p_global = res.p_value
        m = kass_multiplier(c, len(groups), ordinal=ordinal)
        p_adj = bonferroni_adjust(p_global, m)
        if stat_inf:
            # F infinito: p = 0 exacto, p_adj = 0 (coherente con evaluate())
            p_global = 0.0
            p_adj = 0.0
        return MergeStep(
            n_groups=len(groups),
            merged_pair=merged_pair,
            pair_p_value=pair_p,
            global_p_value=p_global,
            adjusted_p_value=p_adj,
        )

    # ------------------------------------------------------------------
    # Cochran (1954): regla y fusion forzosa
    # ------------------------------------------------------------------

    def _forced_pair(
        self,
        matrix: np.ndarray,
        groups: list[tuple[int, ...]],
        ordinal: bool,
    ) -> tuple[int, int]:
        """Par a fusionar por Cochran: el grupo (fila) de MENOR total con el
        grupo elegible de MAYOR p del par (criterio CHAID habitual).
        Determinista: argmin/argmax toman la primera ocurrencia."""
        tabla = self._groups_table(matrix, groups)
        i_min = int(np.argmin(tabla.sum(axis=1)))
        eligible = self._eligible_mask(groups, ordinal)
        pvals = np.where(eligible, self._pair_pvalues_chi2(matrix, groups), -np.inf)
        fila = pvals[i_min].copy()
        fila[i_min] = -np.inf
        j_sel = int(np.argmax(fila))
        return (i_min, j_sel) if i_min < j_sel else (j_sel, i_min)

    # ------------------------------------------------------------------
    # utilidades
    # ------------------------------------------------------------------

    def _pair_p_value(
        self,
        matrix: np.ndarray,
        groups: list[tuple[int, ...]],
        i: int,
        j: int,
    ) -> float:
        """p del par concreto (solo para registro en la fusion forzada chi2)."""
        return float(self._pair_pvalues_chi2(matrix, groups)[i, j])

    @staticmethod
    def _require_hashable(labels: tuple, predictor: str) -> None:
        for v in labels:
            try:
                hash(v)
            except TypeError:
                raise ValueError(
                    f"[CHAID|{predictor!r}] categoria no hashable {v!r}: "
                    "no admitida en branches de SplitConfig"
                ) from None

    def _finish_none(
        self,
        predictor: str,
        c: int,
        r: int,
        n_forced: int,
        cochran_ok: bool,
        n_dropped: int,
        steps: tuple[MergeStep, ...],
    ) -> None:
        """Salida None con diagnostico actualizado."""
        self._diagnostics = MergeDiagnostics(
            n_categories=c,
            n_final_groups=r,
            n_forced_merges=n_forced,
            cochran_ok=cochran_ok,
            n_rows_dropped_nan=n_dropped,
            exhaustive_steps=steps,
        )
        return None


def _cochran_status(expected: np.ndarray) -> tuple[bool, int, float]:
    """Regla de Cochran (1954) sobre la matriz de frecuencias esperadas.

    Devuelve (violada, n_celdas_con_E<1, fraccion_celdas_con_E<5):

        violada  <=>  existe E_ij < 1   O   frac(E_ij < 5) > 0.20

    Cita: Cochran, W.G. (1954). "Some Methods for Strengthening the Common
    Chi-2 Tests". Biometrics 10(4), 417-451. Riesgo ALG-03 de
    docs/model_risk_assessment.md.
    """
    n_lt1 = int((expected < _COCHRAN_MIN_E).sum())
    frac_lt5 = float((expected < 5.0).mean())
    violada = (n_lt1 > 0) or (frac_lt5 > _COCHRAN_FRAC_LT5)
    return violada, n_lt1, frac_lt5
