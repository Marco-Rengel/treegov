"""Motor C&RT (Classification and Regression Trees) - (TreeGov, backend_v3, Paso 7).

Particion binaria guiada por la reduccion de impureza, sin inferencia
estadistica (sin p-valores: SplitConfig con p_value=None, tal como exige
types.py para method="CRT").

  - Clasificacion (binaria y multiclase): impureza de Gini
        I(t) = 1 - sum_k p_k^2
  - Regresion: impureza por varianza
        I(t) = (1/n) sum_i (y_i - media)^2 = E[y^2] - E[y]^2
  - Criterio: dI = I(padre) - (n_L/N)*I(L) - (n_R/N)*I(R); se acepta solo si
    dI > min_impurity_decrease.
  - Predictor CONTINUOUS / ORDINAL: umbrales en puntos medios entre valores
    distintos consecutivos del orden natural (ORDINAL se trata como continuo
    discreto: NUNCA se fusionan categorias no adyacentes). Si el ordinal es
    simbolico (etiquetas no numericas), el corte se reporta como dos grupos
    de etiquetas (branches), porque un threshold numerico careceria de
    significado para el aplicador del modelo.
  - Predictor NOMINAL:
        K <= max_exhaustive_cardinality: exhaustivo, 2^(K-1) - 1 particiones
            (categoria 0 fija a la izquierda -> mascara por bits vectorizada).
        K > max: heuristica por tasa/media de la categoria y cortes entre
            adyacentes del orden inducido (Breiman 1984, §4).
  - Surrogate splits (Breiman 1984, §5.3): replica de la asignacion izq/der
    del primario sobre los casos NO NULOS de ambos predictores, con filtro de
    asociacion positiva agreement > majority y tope max_surrogates.

Cita canonica:
  Breiman, L., Friedman, J.H., Olshen, R.A. & Stone, C.J. (1984).
  "Classification and Regression Trees". Wadsworth & Brooks/Cole,
  Monterey, CA. (Impurezas: caps. 2-4; surrogates: §5.3.)
  Heeringa, S.G., West, B.T. & Berglund, P.A. (2010). Applied Survey
    Data Analysis. Chapman & Hall/CRC, seccion 5.3 (estadisticos con
    conteos ponderados; proporciones y varianzas ponderadas).

Ponderacion por muestra (Fase 3.2.c): evaluate() y best_split() admiten un
parametro keyword-only `weights` (vector paralelo a x e y, estrictamente
positivo y finito). Internamente, con weights=None el motor trabaja con un
vector local de unos, de modo que el camino es unico: los "conteos" por
clase y los suficientes (n, sum, sumsq) se acumulan ponderando por el
vector local. Gini y varianza son invariantes a escala (proporciones y
cocientes), por lo que la escala global de los pesos no afecta al corte.
SplitConfig.child_ns y parent_n siguen siendo conteos FISICOS de filas.
Con weights=None el comportamiento es identico bit a bit al pre-3.2.

Politica NaN: x con NaN se EXCLUYE del calculo del corte (C&RT puro; los
NaN se enrutan en operacion via surrogates). parent_n = casos no nulos de
(x, y), por lo que sum(child_ns) == parent_n.

Dependencias permitidas: numpy, pandas, stdlib. No se usa scipy aqui.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from numbers import Integral

import numpy as np
import pandas as pd

from .log_config import get_logger
from .types import PredictorType, SplitConfig, TargetType

__all__ = ["CrtEngine", "SurrogateSplit"]


@dataclass(frozen=True)
class SurrogateSplit:
    """Replica de asignacion de un split primario (Breiman 1984, §5.3).

    split           : SplitConfig CRT del predictor surrogate; statistic e
                      impurity_gain son la ganancia GENUINA sobre y evaluada
                      en los casos no nulos del surrogate (el agreement no es
                      una impureza y por tanto no cabe en SplitConfig).
    agreement       : max(n_LL + n_RR, n_LR + n_RL) / n_used entre el
                      primario y este corte (mejor orientacion).
    majority_to_beat: max(n_L, n_R) / n_used sobre los casos usados (regla
                      trivial a batir: asociacion positiva estricta).
    n_used          : filas con primario Y surrogate no nulos.
    flipped         : True si la mejor orientacion invierte izq/der del
                      primario (el hijo izquierdo del surrogate replica al
                      hijo derecho del primario).
    """

    split: SplitConfig
    agreement: float
    majority_to_beat: float
    n_used: int
    flipped: bool


# ---------------------------------------------------------------------------
# kernels vectorizados de impureza (formulas explicitas, Breiman 1984)
# ---------------------------------------------------------------------------


def _gini_dI(
    c_l: np.ndarray, c_r: np.ndarray, i_parent: float, n_total: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """dI(corte) = I_padre - (nL/N) I_L - (nR/N) I_R con I = 1 - sum p_k^2.

    c_l, c_r: (P, K) conteos por clase a cada lado de P cortes candidatos.
    Devuelve (dI, nL, nR) por corte. Nunca hay lados vacios por construccion
    (cortes solo entre valores distintos / mascaras propias).
    """
    n_l = c_l.sum(axis=1)
    n_r = c_r.sum(axis=1)
    imp_l = 1.0 - (c_l * c_l).sum(axis=1) / (n_l * n_l)
    imp_r = 1.0 - (c_r * c_r).sum(axis=1) / (n_r * n_r)
    d_i = i_parent - (n_l / n_total) * imp_l - (n_r / n_total) * imp_r
    return d_i, n_l, n_r


def _var_dI(
    n_l: np.ndarray, s_l: np.ndarray, q_l: np.ndarray,
    n_r: np.ndarray, s_r: np.ndarray, q_r: np.ndarray,
    i_parent: float, n_total: float,
) -> np.ndarray:
    """dI de varianza: I = E[y^2] - E[y]^2 (clip a 0 por redondeo)."""
    v_l = np.maximum(q_l / n_l - (s_l / n_l) ** 2, 0.0)
    v_r = np.maximum(q_r / n_r - (s_r / n_r) ** 2, 0.0)
    return i_parent - (n_l / n_total) * v_l - (n_r / n_total) * v_r


def _masks_exhaustivas(k_cats: int) -> np.ndarray:
    """(2^(k-1)-1, k) bool: True = la categoria va al grupo DERECHO.

    La categoria 0 queda fija a la izquierda (elimina particiones
    complementarias duplicadas). La mascara 0...0 se excluye (derecha vacia).
    """
    m = (1 << (k_cats - 1)) - 1
    idx = np.arange(1, m + 1, dtype=np.uint64)
    bits = ((idx[:, None] >> np.arange(k_cats - 1, dtype=np.uint64)[None, :]) & 1)
    return np.concatenate(
        [np.zeros((m, 1), dtype=bool), bits.astype(bool)], axis=1
    )


class CrtEngine:
    """Motor C&RT: un predictor -> mejor corte binario (o None).

    Determinista: argsort estable, argmax con primera ocurrencia, mascaras
    ordenadas por entero ascendente y empates de surrogates por orden de spec.
    """

    def __init__(
        self,
        *,
        min_impurity_decrease: float = 1e-9,
        max_exhaustive_cardinality: int = 10,
        max_surrogates: int = 3,
        logger: logging.Logger | None = None,
    ) -> None:
        if isinstance(min_impurity_decrease, bool) or not (
            math.isfinite(float(min_impurity_decrease))
            and float(min_impurity_decrease) >= 0.0
        ):
            raise ValueError(
                "min_impurity_decrease debe ser float >= 0 "
                f"(recibido {min_impurity_decrease!r})"
            )
        if (
            isinstance(max_exhaustive_cardinality, bool)
            or not isinstance(max_exhaustive_cardinality, Integral)
            or int(max_exhaustive_cardinality) < 2
        ):
            raise ValueError(
                "max_exhaustive_cardinality debe ser entero >= 2 "
                f"(recibido {max_exhaustive_cardinality!r})"
            )
        if (
            isinstance(max_surrogates, bool)
            or not isinstance(max_surrogates, Integral)
            or int(max_surrogates) < 0
        ):
            raise ValueError(
                f"max_surrogates debe ser entero >= 0 (recibido {max_surrogates!r})"
            )
        self.min_impurity_decrease = float(min_impurity_decrease)
        self.max_exhaustive_cardinality = int(max_exhaustive_cardinality)
        self.max_surrogates = int(max_surrogates)
        self._log = logger if logger is not None else get_logger("crt")

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
        """Mejor corte binario de UN predictor en UN nodo (o None).

        Convencion de hijos: izquierda = x <= threshold (o branches[0]);
        derecha = el resto.

        `weights` (keyword-only, default None): vector de pesos paralelo a
        `x` e `y`; array 1D de la misma longitud, valores finitos y
        estrictamente positivos. Con weights=None el motor usa un vector
        local de unos y el comportamiento es identico al pre-3.2.
        Cita: Heeringa, West & Berglund (2010), sec. 5.3.
        """
        if not isinstance(predictor_type, PredictorType):
            raise TypeError(f"predictor_type invalido: {predictor_type!r}")
        if not isinstance(target_type, TargetType):
            raise TypeError(f"target_type invalido: {target_type!r}")

        xs = pd.Series(x) if not isinstance(x, pd.Series) else x
        ys = pd.Series(y) if not isinstance(y, pd.Series) else y
        if len(xs) != len(ys):
            raise ValueError(
                f"[CRT|{predictor!r}] x (n={len(xs)}) e y (n={len(ys)}) "
                "deben tener la misma longitud"
            )

        # -- validacion de pesos (paralelos a x e y) --
        if weights is not None:
            try:
                w_in = np.asarray(weights, dtype=float)
            except (TypeError, ValueError) as e:
                raise ValueError(
                    f"[CRT|{predictor!r}] weights no convertible a vector "
                    f"numerico: {e}"
                ) from e
            if w_in.ndim != 1 or w_in.size != len(xs):
                raise ValueError(
                    f"[CRT|{predictor!r}] weights debe ser un vector 1D de "
                    f"longitud {len(xs)} (shape={w_in.shape})"
                )
            if not np.all(np.isfinite(w_in)):
                raise ValueError(
                    f"[CRT|{predictor!r}] weights contiene NaN o infinitos"
                )
            if np.any(w_in <= 0.0):
                raise ValueError(
                    f"[CRT|{predictor!r}] weights contiene pesos no "
                    "estrictamente positivos"
                )

        mask = (xs.notna() & ys.notna()).to_numpy()
        n_dropped = int((~mask).sum())
        xd = xs[mask]
        yd = ys[mask]
        n_total = int(len(xd))
        if n_dropped:
            self._log.info(
                "[CRT|%r] %d filas excluidas por NaN (los surrogates las enrutan)",
                predictor, n_dropped,
            )
        if n_total == 0:
            self._log.warning("[CRT|%r] 0 casos validos tras dropna", predictor)
            return None

        # -- vector local de pesos (unos si weights=None): camino interno unico --
        w = w_in[mask] if weights is not None else np.ones(n_total)
        w_total = float(w.sum())
        self._log.debug(
            "[CRT|%r] ponderacion: %s",
            predictor,
            "sin pesos" if weights is None
            else f"con pesos (suma total={w_total:.6g})",
        )

        # -- impureza del padre y estructura del target --
        continuo_y = target_type == TargetType.CONTINUOUS
        if continuo_y:
            yv = yd.to_numpy(dtype=float)
            if not np.all(np.isfinite(yv)):
                raise ValueError(f"[CRT|{predictor!r}] y contiene no finitos")
            mean = float((w * yv).sum()) / w_total
            i_parent = max(
                float((w * yv * yv).sum()) / w_total - mean * mean, 0.0
            )
            ydata: tuple = ("reg", yv, 0, i_parent, n_total)
        else:
            codes, classes = pd.factorize(yd, sort=True)
            k_classes = len(classes)
            if k_classes < 2:
                self._log.warning(
                    "[CRT|%r] target constante (K=%d): sin impureza que reducir",
                    predictor, k_classes,
                )
                return None
            yint = codes.astype(np.int64)
            counts = np.bincount(yint, weights=w, minlength=k_classes)
            p = counts / w_total
            i_parent = max(float(1.0 - (p * p).sum()), 0.0)
            ydata = ("cls", yint, k_classes, i_parent, n_total)

        if i_parent <= 0.0:
            self._log.info("[CRT|%r] impureza del padre nula -> nodo puro", predictor)
            return None

        # -- mejor corte segun escala del predictor --
        if predictor_type == PredictorType.NOMINAL:
            cut = self._best_subset_split(xd, ydata, predictor, w)
        else:
            cut = self._best_threshold_split(xd, ydata, predictor, w)

        if cut is None:
            self._log.info("[CRT|%r] sin corte valido (constante o trivial)",
                           predictor)
            return None

        threshold, branches, d_imax, n_left, n_right = cut
        if d_imax <= self.min_impurity_decrease:
            self._log.info(
                "[CRT|%r] dI_max=%.6g <= min_impurity_decrease=%.6g -> sin split",
                predictor, d_imax, self.min_impurity_decrease,
            )
            return None

        config = SplitConfig(
            predictor=predictor,
            method="CRT",
            statistic=d_imax,
            statistic_name="variance_gain" if continuo_y else "gini_gain",
            df=(),
            parent_n=n_total,
            child_ns=(int(n_left), int(n_right)),
            threshold=threshold,
            branches=branches,
            impurity_gain=d_imax,
        )
        self._log.info(
            "[CRT|%r] split: %s=%.6g forma=%s n=(%d, %d)",
            predictor, config.statistic_name, d_imax,
            f"thr={threshold:.6g}" if threshold is not None else "branches",
            n_left, n_right,
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
        """Maximo impurity_gain entre predictores; empate -> primero de spec.

        `weights` (keyword-only) se propaga a cada llamada a evaluate().
        """
        best: SplitConfig | None = None
        for nombre, ptype in spec.items():
            if nombre not in X.columns:
                raise ValueError(f"[best_split] predictor ausente en X: {nombre!r}")
            cfg = self.evaluate(
                X[nombre], y, predictor=nombre, predictor_type=ptype,
                target_type=target_type, weights=weights,
            )
            if cfg is not None and (
                best is None or float(cfg.statistic) > float(best.statistic)
            ):
                best = cfg
        self._log.info("[best_split] ganador: %r",
                       None if best is None else best.predictor)
        return best

    def surrogate_splits(
        self,
        primary: SplitConfig,
        X: pd.DataFrame,
        y: pd.Series,
        spec: dict[str, PredictorType],
        *,
        target_type: TargetType,
        weights: np.ndarray | None = None,
    ) -> tuple[SurrogateSplit, ...]:
        """Hasta max_surrogates replicas del primario sobre otros predictores.

        Casos validos por candidato: filas con PRIMARIO y candidato no nulos.
        Convencion izquierda del primario: x <= threshold, o branches[0].
        Regla de Breiman (1984, §5.3): se retiene solo si agreement estricto
        mayor que la regla trivial "todo al hijo mayoritario" del primario.
        El SplitConfig embebido evalua el MISMO corte fisico sobre y real
        (ganancia de impureza genuina; los invariantes de types.py intactos).

        `weights` (keyword-only, default None): vector de pesos paralelo a
        las filas de X / y. El agreement NO se pondera (es coincidencia
        pura de etiquetas binarias izquierda/derecha); solo la ganancia de
        impureza del SplitConfig embebido se calcula con pesos.
        Cita: Heeringa, West & Berglund (2010), sec. 5.3.
        """
        if primary.predictor not in X.columns:
            raise ValueError(
                f"[surrogates] predictor del primario ausente: {primary.predictor!r}"
            )
        if weights is not None:
            try:
                w_in = np.asarray(weights, dtype=float)
            except (TypeError, ValueError) as e:
                raise ValueError(
                    f"[surrogates] weights no convertible a vector "
                    f"numerico: {e}"
                ) from e
            if w_in.ndim != 1 or w_in.size != len(y):
                raise ValueError(
                    f"[surrogates] weights debe ser un vector 1D de "
                    f"longitud {len(y)} (shape={w_in.shape})"
                )
            if not np.all(np.isfinite(w_in)):
                raise ValueError(
                    "[surrogates] weights contiene NaN o infinitos"
                )
            if np.any(w_in <= 0.0):
                raise ValueError(
                    "[surrogates] weights contiene pesos no "
                    "estrictamente positivos"
                )
            self._log.debug(
                "[surrogates|%r] ponderacion: con pesos (suma total=%.6g)",
                primary.predictor, float(w_in.sum()),
            )
        xp = X[primary.predictor]
        mask_p = xp.notna().to_numpy()
        if primary.threshold is not None:
            left_p = (xp.to_numpy(dtype=float) <= float(primary.threshold)) & mask_p
        elif primary.branches is not None and len(primary.branches) == 2:
            izq0 = set(primary.branches[0])
            left_p = xp.isin(list(izq0)).to_numpy() & mask_p
        else:
            raise ValueError(
                "[surrogates] el primario debe tener threshold o 2 branches"
            )

        hallados: list[tuple[float, int, SurrogateSplit]] = []
        for orden, (nombre, ptype) in enumerate(spec.items()):
            if nombre == primary.predictor:
                continue
            if nombre not in X.columns:
                raise ValueError(f"[surrogates] predictor ausente en X: {nombre!r}")
            cand = X[nombre]
            mask = mask_p & cand.notna().to_numpy()
            n_used = int(mask.sum())
            if n_used == 0:
                self._log.debug(
                    "[surrogates|%r] sin solape no nulo con el primario", nombre
                )
                continue
            left_sub = left_p[mask]
            n_lprim = int(left_sub.sum())
            majority = max(n_lprim, n_used - n_lprim) / n_used

            mejor = self._best_agreement(cand[mask], left_sub, ptype, nombre)
            if mejor is None:
                continue
            thr_c, br_c, agreement, flipped = mejor
            if agreement <= majority:
                self._log.debug(
                    "[surrogates|%r] agreement=%.6g <= mayoria=%.6g: descartado",
                    nombre, agreement, majority,
                )
                continue
            embebido = self._embedded_split(
                nombre, cand, y, ptype, target_type, thr_c, br_c,
                weights=weights,
            )
            if embebido is None:
                continue
            hallados.append((agreement, orden, SurrogateSplit(
                split=embebido,
                agreement=float(agreement),
                majority_to_beat=float(majority),
                n_used=n_used,
                flipped=bool(flipped),
            )))

        # mayor agreement primero; empate -> orden de spec (estable)
        hallados.sort(key=lambda t: (-t[0], t[1]))
        resultado = tuple(s for _, _, s in hallados[: self.max_surrogates])
        self._log.info(
            "[surrogates|%r] %d surrogates aceptados de %d candidatos",
            primary.predictor, len(resultado), max(len(spec) - 1, 0),
        )
        return resultado

    # ------------------------------------------------------------------
    # cortes continuos / ordinales (puntos medios entre valores distintos)
    # ------------------------------------------------------------------

    def _best_threshold_split(
        self, xd: pd.Series, ydata: tuple, predictor: str,
        weights: np.ndarray,
    ) -> tuple[float | None, tuple | None, float, int, int] | None:
        """Barrido vectorizado de puntos medios entre valores distintos.

        Ordinal simbolico: se trabaja sobre los codigos del orden natural
        (factorize sort=True) y el corte se traduce a branches de etiquetas.
        Umbral: t = v_i + (v_{i+1} - v_i)/2 (forma estable ante overflow).

        `weights`: vector local de pesos (unos si el llamador no paso
        pesos); alimenta los acumulados de la formula de dI. Los n por
        lado devueltos son CONTEOS FISICOS de filas.
        """
        etiquetas: tuple | None = None
        if pd.api.types.is_numeric_dtype(xd):
            xv = xd.to_numpy(dtype=float)
            if not np.all(np.isfinite(xv)):
                raise ValueError(f"[CRT|{predictor!r}] x contiene no finitos")
        else:
            try:
                codes, uniques = pd.factorize(xd, sort=True)
            except TypeError as e:
                raise ValueError(
                    f"[CRT|{predictor!r}] categorias no factorizables: {e}"
                ) from e
            self._require_hashable(tuple(uniques), predictor)
            xv = codes.astype(float)
            etiquetas = tuple(uniques)

        n = xv.size
        orden = np.argsort(xv, kind="mergesort")
        xs = xv[orden]
        bordes = np.flatnonzero(xs[1:] != xs[:-1])  # corte entre i y i+1
        if bordes.size == 0:
            return None  # x constante

        d_i, n_l, n_r = self._sweep_values(xs, bordes, orden, ydata, weights)
        bpos = int(np.argmax(d_i))  # primer maximo -> determinista
        n_left = int(n_l[bpos])
        n_right = int(n_r[bpos])

        if etiquetas is None:
            v_low = float(xs[bordes[bpos]])
            v_high = float(xs[bordes[bpos] + 1])
            threshold = v_low + (v_high - v_low) / 2.0
            return threshold, None, float(d_i[bpos]), n_left, n_right

        # ordinal simbolico: codigos 0..K-1 <-> etiquetas ordenadas; el indice
        # de categoria del corte es el CODIGO del valor en el borde elegido
        codigo_corte = int(xs[bordes[bpos]])  # 0..K-2
        izq = tuple(etiquetas[: codigo_corte + 1])
        der = tuple(etiquetas[codigo_corte + 1 :])
        return None, (izq, der), float(d_i[bpos]), n_left, n_right

    def _sweep_values(
        self, xs: np.ndarray, bordes: np.ndarray, orden: np.ndarray,
        ydata: tuple, weights: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """dI de todos los bordes sobre valores ya ordenados.

        Los acumulados de la formula (conteos por clase / suficientes) se
        ponderan por `weights`; los vectores n_l / n_r devueltos son
        CONTEOS FISICOS de filas a cada lado del corte. Las firmas de
        _gini_dI / _var_dI no cambian: reciben sumas de pesos como
        "conteos" y el total de pesos W como n_total.
        """
        kind, yvals, k_cls, i_parent, n = ydata
        w_sorted = weights[orden]
        w_total = float(w_sorted.sum())
        n_l = (bordes + 1).astype(float)
        n_r = n - n_l
        if kind == "cls":
            y_sorted = yvals[orden]
            one_hot = (
                y_sorted[:, None] == np.arange(k_cls)[None, :]
            ).astype(np.float64)
            cum = np.cumsum(one_hot * w_sorted[:, None], axis=0)
            c_l = cum[bordes]
            c_r = cum[-1][None, :] - c_l
            d_i, _, _ = _gini_dI(c_l, c_r, i_parent, w_total)
            return d_i, n_l, n_r
        y_sorted = yvals[orden]
        wys = w_sorted * y_sorted
        cumw = np.cumsum(w_sorted)
        cum1 = np.cumsum(wys)
        cum2 = np.cumsum(wys * y_sorted)
        w_l = cumw[bordes]
        d_i = _var_dI(
            w_l, cum1[bordes], cum2[bordes],
            w_total - w_l, cum1[-1] - cum1[bordes], cum2[-1] - cum2[bordes],
            i_parent, w_total,
        )
        return d_i, n_l, n_r

    # ------------------------------------------------------------------
    # cortes nominales (subconjuntos)
    # ------------------------------------------------------------------

    def _best_subset_split(
        self, xd: pd.Series, ydata: tuple, predictor: str,
        weights: np.ndarray,
    ) -> tuple | None:
        """Exhaustivo (K <= max) o heuristico por tasa (K > max).

        Convencion de ramas de la heuristica (coherente con el umbral del
        continuo, izquierda = x <= t): ordenadas por tasa DESCendente y
        cortadas en el borde optimo, el tramo de TASAS ALTAS va a la
        DERECHA (branches[1]) y el de tasas bajas a la IZQUIERDA (branches[0]).

        `weights`: vector local de pesos (unos si el llamador no paso
        pesos). La matriz categoria x clase (o los suficientes) acumula
        sumas de pesos; los n por lado devueltos son CONTEOS FISICOS.
        """
        try:
            codes, uniques = pd.factorize(xd, sort=True)
        except TypeError as e:
            raise ValueError(
                f"[CRT|{predictor!r}] categorias no factorizables: {e}"
            ) from e
        labels = tuple(uniques)
        self._require_hashable(labels, predictor)
        k_cats = len(labels)
        if k_cats < 2:
            return None

        kind, yvals, k_cls, i_parent, n = ydata
        cnt_fis = np.bincount(codes, minlength=k_cats).astype(float)
        w_total = float(weights.sum())
        if kind == "cls":
            idx = codes.astype(np.int64) * k_cls + yvals
            counts = np.bincount(idx, weights=weights,
                                 minlength=k_cats * k_cls)
            counts = counts.reshape(k_cats, k_cls)
            tasas, aviso = self._rates_cls(counts, predictor, k_cats)
        else:
            n_i = np.bincount(codes, weights=weights, minlength=k_cats)
            s_i = np.bincount(codes, weights=weights * yvals, minlength=k_cats)
            q_i = np.bincount(codes, weights=weights * yvals * yvals,
                              minlength=k_cats)
            counts = np.column_stack([n_i, s_i, q_i])
            tasas, aviso = s_i / n_i, False

        if aviso:
            self._log.warning(
                "[CRT|%r] heurística pragmática activada; se pierde "
                "optimalidad en multiclase; considere discretizar el predictor",
                predictor,
            )

        # el "n" que alimenta las formulas de dI es la masa de pesos W;
        # los conteos fisicos por lado se derivan de cnt_fis y la mascara
        if k_cats <= self.max_exhaustive_cardinality:
            mejor = self._subset_exhaustivo(counts, kind, i_parent, w_total, k_cls)
        else:
            mejor = self._subset_por_tasa(counts, tasas, kind, i_parent,
                                          w_total, k_cls)
        if mejor is None:
            return None
        mask_der, d_imax, _, _ = mejor
        izq = tuple(labels[g] for g in range(k_cats) if not mask_der[g])
        der = tuple(labels[g] for g in range(k_cats) if mask_der[g])
        n_left = int(cnt_fis[~mask_der].sum())
        n_right = int(cnt_fis[mask_der].sum())
        return None, (izq, der), float(d_imax), n_left, n_right

    def _rates_cls(
        self, counts: np.ndarray, predictor: str, k_cats: int
    ) -> tuple[np.ndarray, bool]:
        """Tasa por categoria para el orden inducido.

        Binario: tasa de la clase 1 (indice 1). Multiclase: tasa de la clase
        modal global; devuelve (tasas, aviso_heuristica_multiclase).
        """
        totales = counts.sum(axis=0)
        k_cls = counts.shape[1]
        aviso = False
        if k_cls == 2:
            clase = 1
        else:
            clase = int(np.argmax(totales))  # clase modal global
            aviso = k_cats > self.max_exhaustive_cardinality
        n_g = counts.sum(axis=1)
        return counts[:, clase] / n_g, aviso

    def _subset_exhaustivo(
        self, counts: np.ndarray, kind: str, i_parent: float, n: int, k_cls: int
    ) -> tuple[np.ndarray, float, float, float] | None:
        """2^(K-1)-1 particiones por mascara binaria, vectorizado."""
        masks = _masks_exhaustivas(counts.shape[0])  # (M, k) True = derecha
        mf = masks.astype(float)
        if kind == "cls":
            c_r = mf @ counts                       # (M, K)
            c_l = counts.sum(axis=0)[None, :] - c_r
            d_i, n_l, n_r = _gini_dI(c_l, c_r, i_parent, n)
        else:
            n_r = mf @ counts[:, 0]
            s_r = mf @ counts[:, 1]
            q_r = mf @ counts[:, 2]
            n_l = n - n_r
            d_i = _var_dI(
                n_l, counts[:, 1].sum() - s_r, counts[:, 2].sum() - q_r,
                n_r, s_r, q_r,
                i_parent, n,
            )
        best = int(np.argmax(d_i))  # mascara de menor entero en empate
        return masks[best], float(d_i[best]), float(n_l[best]), float(n_r[best])

    def _subset_por_tasa(
        self, counts: np.ndarray, tasas: np.ndarray, kind: str,
        i_parent: float, n: int, k_cls: int,
    ) -> tuple[np.ndarray, float, float, float] | None:
        """Orden por tasa/media descendente + cortes entre adyacentes."""
        orden = np.argsort(-tasas, kind="stable")
        mask = np.zeros(counts.shape[0], dtype=bool)
        # barrido sobre la tabla reordenada
        if kind == "cls":
            co = counts[orden]
            cum = np.cumsum(co, axis=0)
            c_l = cum[:-1]
            c_r = cum[-1][None, :] - c_l
            d_i, n_l, n_r = _gini_dI(c_l, c_r, i_parent, n)
        else:
            co = counts[orden]
            cum = np.cumsum(co, axis=0)  # (k, 3) acumulado de (n, s, q)
            n_l = cum[:-1, 0]
            s_l = cum[:-1, 1]
            q_l = cum[:-1, 2]
            d_i = _var_dI(
                n_l, s_l, q_l,
                n - n_l, counts[:, 1].sum() - s_l, counts[:, 2].sum() - q_l,
                i_parent, n,
            )
            n_r = n - n_l
        bpos = int(np.argmax(d_i))
        mask[orden[: bpos + 1]] = True
        return mask, float(d_i[bpos]), float(n_l[bpos]), float(n_r[bpos])

    # ------------------------------------------------------------------
    # surrogates: agreement contra la asignacion del primario
    # ------------------------------------------------------------------

    def _best_agreement(
        self,
        cand: pd.Series,
        left_sub: np.ndarray,
        ptype: PredictorType,
        nombre: str,
    ) -> tuple | None:
        """(threshold|None, branches|None, agreement, flipped) del corte que
        mejor replica left_sub. None si el candidato es constante."""
        n_used = left_sub.size
        l_total = int(left_sub.sum())
        if ptype == PredictorType.NOMINAL:
            try:
                codes, uniques = pd.factorize(cand, sort=True)
            except TypeError as e:
                raise ValueError(
                    f"[surrogates|{nombre}] categorias no factorizables: {e}"
                ) from e
            labels = tuple(uniques)
            self._require_hashable(labels, nombre)
            k_cats = len(labels)
            if k_cats < 2:
                return None
            n_g = np.bincount(codes, minlength=k_cats).astype(float)
            l_g = np.bincount(codes, weights=left_sub.astype(float),
                              minlength=k_cats)
            mejor = self._agreement_nominal(
                k_cats, n_g, l_g, l_total, n_used
            )
            if mejor is None:
                return None
            mask_der, agreement, flipped = mejor
            izq = tuple(labels[g] for g in range(k_cats) if not mask_der[g])
            der = tuple(labels[g] for g in range(k_cats) if mask_der[g])
            return None, (izq, der), agreement, flipped

        # continuo / ordinal (simbolico -> codigos y branches)
        etiquetas: tuple | None = None
        if pd.api.types.is_numeric_dtype(cand):
            xv = cand.to_numpy(dtype=float)
        else:
            try:
                codes, uniques = pd.factorize(cand, sort=True)
            except TypeError as e:
                raise ValueError(
                    f"[surrogates|{nombre}] categorias no factorizables: {e}"
                ) from e
            self._require_hashable(tuple(uniques), nombre)
            xv = codes.astype(float)
            etiquetas = tuple(uniques)
        orden = np.argsort(xv, kind="mergesort")
        xs = xv[orden]
        left_ord = left_sub[orden]
        bordes = np.flatnonzero(xs[1:] != xs[:-1])
        if bordes.size == 0:
            return None

        # Cuadrantes 2x2: primario (P_L/P_R) x candidato (C_L=izq, C_R=der).
        # Identidad obligatoria: q_ll + q_lr + q_rl + q_rr == n_used.
        # convencion: q_ab = |P_<a> ∩ C_<b>|.
        cum_l = np.cumsum(left_ord.astype(float))
        n_izq = (bordes + 1).astype(float)        # |C_L|
        q_ll = cum_l[bordes]                      # |P_L ∩ C_L|
        q_rl = n_izq - q_ll                       # |P_R ∩ C_L|
        q_lr = l_total - q_ll                     # |P_L ∩ C_R|
        q_rr = (n_used - l_total) - q_rl          # |P_R ∩ C_R|
        same = q_ll + q_rr
        flip = q_lr + q_rl
        agr = np.maximum(same, flip)
        bpos = int(np.argmax(agr))
        flipped = bool(flip[bpos] > same[bpos])
        agreement = float(agr[bpos]) / n_used

        if etiquetas is None:
            v_low = float(xs[bordes[bpos]])
            v_high = float(xs[bordes[bpos] + 1])
            return v_low + (v_high - v_low) / 2.0, None, agreement, flipped
        codigo_corte = int(xs[bordes[bpos]])  # 0..K-2 (codigo en el borde)
        return (None,
                (tuple(etiquetas[: codigo_corte + 1]),
                 tuple(etiquetas[codigo_corte + 1 :])),
                agreement, flipped)

    def _agreement_nominal(
        self, k_cats: int, n_g: np.ndarray, l_g: np.ndarray,
        l_total: int, n_used: int,
    ) -> tuple[np.ndarray, float, bool] | None:
        """Agreement por particion binaria del nominal (exhaustivo K<=10,
        orden por tasa si K>10; aqui el objetivo es BINARIO por construccion,
        luego la heuristica por tasa es la exacta de Breiman 1984, §4)."""
        def _metricas(mask_der: np.ndarray) -> tuple[float, float]:
            # mascara True = grupo DERECHO del candidato (C_R).
            # cuadrantes: q_ll + q_lr + q_rl + q_rr == n_used (obligatorio)
            mf = mask_der.astype(float)
            n_der = float(mf @ n_g)                 # |C_R|
            q_lr = float(mf @ l_g)                  # |P_L ∩ C_R|
            q_rr = n_der - q_lr                     # |P_R ∩ C_R|
            q_ll = l_total - q_lr                   # |P_L ∩ C_L|
            q_rl = (n_used - n_der) - q_ll          # |P_R ∩ C_L|
            same = q_ll + q_rr
            flip = q_lr + q_rl
            return same, flip

        if k_cats <= self.max_exhaustive_cardinality:
            masks = _masks_exhaustivas(k_cats)
            mf = masks.astype(float)
            n_der = mf @ n_g                        # (M,) |C_R|
            q_lr = mf @ l_g                         # (M,) |P_L ∩ C_R|
            q_rr = n_der - q_lr                     # |P_R ∩ C_R|
            q_ll = l_total - q_lr                   # |P_L ∩ C_L|
            q_rl = (n_used - n_der) - q_ll          # |P_R ∩ C_L|
            same = q_ll + q_rr
            flip = q_lr + q_rl
            agr = np.maximum(same, flip)
            best = int(np.argmax(agr))
            return masks[best], float(agr[best]) / n_used, bool(flip[best] > same[best])

        tasas = l_g / n_g  # tasa de "cayo a la izquierda del primario"
        orden = np.argsort(-tasas, kind="stable")
        mejor: tuple[float, int, bool] | None = None
        acum_mask = np.zeros(k_cats, dtype=bool)
        for b in range(k_cats - 1):
            acum_mask[orden[b]] = True
            same, flip = _metricas(acum_mask)
            agr = max(same, flip)
            if mejor is None or agr > mejor[0]:
                mejor = (agr, b, flip > same)
        assert mejor is not None
        agr, b, flipped = mejor
        mask = np.zeros(k_cats, dtype=bool)
        mask[orden[: b + 1]] = True
        return mask, agr / n_used, flipped

    # ------------------------------------------------------------------
    # SplitConfig embebido de un surrogate (ganancia genuina sobre y)
    # ------------------------------------------------------------------

    def _embedded_split(
        self,
        nombre: str,
        cand: pd.Series,
        y: pd.Series,
        ptype: PredictorType,
        target_type: TargetType,
        threshold: float | None,
        branches: tuple | None,
        weights: np.ndarray | None = None,
    ) -> SplitConfig | None:
        """SplitConfig CRT del surrogate: el MISMO corte fisico detectado por
        agreement, evaluado sobre y real en los casos no nulos del surrogate
        (statistic = impurity_gain genuino).

        `weights` (keyword-only, default None): vector de pesos paralelo a
        las filas originales de `cand` / `y`; se enmascara con el mismo
        dropna conjunto. La ganancia se calcula con pesos (medias,
        varianzas y proporciones ponderadas); `child_ns` sigue siendo el
        conteo FISICO de filas a cada lado. Con weights=None el
        comportamiento es identico al pre-3.2.
        Cita: Heeringa, West & Berglund (2010), sec. 5.3.
        """
        ys = y if isinstance(y, pd.Series) else pd.Series(y)
        mask = (cand.notna() & ys.notna()).to_numpy()
        xd = cand[mask]
        yd = ys[mask]
        n = int(len(xd))
        if n == 0:
            return None
        # vector local de pesos (unos si weights=None)
        if weights is not None:
            w = np.asarray(weights, dtype=float)[mask]
        else:
            w = np.ones(n)
        w_total = float(w.sum())
        if threshold is not None:
            izq = xd.to_numpy(dtype=float) <= float(threshold)
        else:
            izq = xd.isin(list(branches[0])).to_numpy()  # type: ignore[index]
        n_l = int(izq.sum())
        n_r = n - n_l
        if n_l == 0 or n_r == 0:
            return None

        continuo_y = target_type == TargetType.CONTINUOUS
        if continuo_y:
            yv = yd.to_numpy(dtype=float)
            wl = w[izq]
            yl = yv[izq]
            w_l = float(wl.sum())
            s_l = float((wl * yl).sum())
            q_l = float((wl * yl * yl).sum())
            s_all = float((w * yv).sum())
            q_all = float((w * yv * yv).sum())
            mean = s_all / w_total
            i_parent = max(q_all / w_total - mean * mean, 0.0)
            d_i = float(_var_dI(
                np.array([w_l]), np.array([s_l]), np.array([q_l]),
                np.array([w_total - w_l]), np.array([s_all - s_l]),
                np.array([q_all - q_l]),
                i_parent, w_total,
            )[0])
            stat_name: str = "variance_gain"
        else:
            codes, classes = pd.factorize(yd, sort=True)
            k_cls = len(classes)
            if k_cls < 2:
                return None
            counts = np.bincount(codes, weights=w, minlength=k_cls)
            p = counts / w_total
            i_parent = float(1.0 - (p * p).sum())
            c_l = np.bincount(
                codes[izq], weights=w[izq], minlength=k_cls
            )[None, :]
            c_r = (counts - c_l[0])[None, :]
            d_i = float(_gini_dI(c_l, c_r, i_parent, w_total)[0][0])
            stat_name = "gini_gain"

        d_i = max(d_i, 0.0)
        return SplitConfig(
            predictor=nombre,
            method="CRT",
            statistic=d_i,
            statistic_name=stat_name,
            df=(),
            parent_n=n,
            child_ns=(n_l, n_r),
            threshold=threshold,
            branches=branches,
            impurity_gain=d_i,
        )

    # ------------------------------------------------------------------
    # utilidades
    # ------------------------------------------------------------------

    @staticmethod
    def _require_hashable(labels: tuple, predictor: str) -> None:
        for v in labels:
            try:
                hash(v)
            except TypeError:
                raise ValueError(
                    f"[CRT|{predictor!r}] categoria no hashable {v!r}: "
                    "no admitida en branches de SplitConfig"
                ) from None
