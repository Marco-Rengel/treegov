"""Pruebas estadisticas y multiplicadores combinatorios de Kass (Fase 0, Paso 5).

Nucleo inferencial de backend_v3: chi-cuadrado de Pearson, ANOVA unifactorial
(F de Fisher), Brown-Forsythe (Levene con centro en la mediana) y los
multiplicadores de Bonferroni de Kass (1980) para el control del error de
tipo I por familia (FWER) en la fusion de categorias de CHAID.

Extension de ponderacion por muestra (Fase 3.2.a): f_oneway y
brown_forsythe admiten un parametro keyword-only opcional `weights`
(secuencia paralela de pesos estrictamente positivos por grupo). Con
`weights=None` el comportamiento es identico bit a bit al original. Con
pesos, las medias son medias ponderadas, los tamanos de grupo son sumas
de pesos W_i, y los grados de libertad siguen la convencion de muestras
complejas: df1 = k - 1 y df2 = N_filas - k (filas fisicas, no pesos).

Politica de caja blanca: las formulas estan escritas explicitamente en el
cuerpo de cada funcion; scipy.stats se usa SOLO para evaluar las funciones de
supervivencia (sf) de las distribuciones de referencia (chi2, F). Prohibido
sklearn / statsmodels (bloqueado por backend_v3.import_guard).

Dependencias: numpy, scipy.stats y stdlib. No se usa pandas.

Referencias:
  Pearson, K. (1900). "On the criterion that a given system of deviations
    from the probable in the case of a correlated system of variables is
    such that it can be reasonably supposed to have arisen from random
    sampling". Philosophical Magazine, Ser. 5, 50(302), 157-175.
  Fisher, R.A. (1925). Statistical Methods for Research Workers.
    Oliver & Boyd, Edinburgh.
  Brown, M.B. & Forsythe, A.B. (1974). "Robust Tests for the Equality of
    Variances". Journal of the American Statistical Association 69(346),
    364-367.
  Levene, H. (1960). "Robust tests for equality of variances". En I. Olkin
    (ed.), Contributions to Probability and Statistics, 278-292.
    Stanford University Press.
  Kass, G.V. (1980). "An Exploratory Technique for Investigating Large
    Quantities of Categorical Data". Applied Statistics 29(2), 119-127.
  Heeringa, S.G., West, B.T. & Berglund, P.A. (2010). Applied Survey
    Data Analysis. Chapman & Hall/CRC, seccion 5.3 (ANOVA ponderado en
    muestras complejas: medias ponderadas, W_i = suma de pesos por
    grupo, df residual basado en filas fisicas).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Integral

import numpy as np
from numpy.typing import ArrayLike
from scipy.stats import chi2, f

__all__ = [
    "TestResult",
    "pearson_chi2",
    "f_oneway",
    "brown_forsythe",
    "stirling_second_kind",
    "kass_multiplier",
    "bonferroni_adjust",
]


@dataclass(frozen=True)
class TestResult:
    """Salida canonica de una prueba estadistica.

    statistic : valor observado del estadistico (chi2, F o W).
    df        : grados de libertad; (gl,) para chi2, (df1, df2) para F/W.
                Coincide con la aridad de SplitConfig.df en types.py.
    p_value   : P(T >= statistic) bajo H0, calculado con la funcion de
                supervivencia (sf), no con 1 - cdf, por precision en cola.
    """

    statistic: float
    df: tuple[int, ...]
    p_value: float


# ---------------------------------------------------------------------------
# utilidades internas de validacion
# ---------------------------------------------------------------------------


def _as_int(name: str, value: int) -> int:
    """Exige entero (rechaza bool y no integrales) y devuelve int puro."""
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(
            f"{name} debe ser entero (recibido {type(value).__name__}: {value!r})"
        )
    return int(value)


def _validate_groups(
    groups: tuple[ArrayLike, ...],
    who: str,
    weights: ArrayLike | None = None,
) -> list[np.ndarray]:
    """Convierte y valida los grupos: >= 2 vectores 1D no vacios, finitos, N > k.

    Si `weights` no es None, tambien valida que sea una secuencia paralela
    a `groups`: misma cantidad de arrays, cada uno de la misma longitud que
    su grupo, con pesos finitos y estrictamente positivos.
    """
    if len(groups) < 2:
        raise ValueError(
            f"[{who}] se requieren >= 2 grupos (recibidos {len(groups)})"
        )
    arrays: list[np.ndarray] = []
    for i, g in enumerate(groups):
        try:
            a = np.asarray(g, dtype=float)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"[{who}] grupo {i} no convertible a vector numerico: {e}"
            ) from e
        if a.ndim != 1 or a.size == 0:
            raise ValueError(
                f"[{who}] grupo {i} debe ser un vector 1D no vacio (shape={a.shape})"
            )
        if not np.all(np.isfinite(a)):
            raise ValueError(f"[{who}] grupo {i} contiene NaN o infinitos")
        arrays.append(a)
    if weights is not None:
        if len(weights) != len(arrays):
            raise ValueError(
                f"[{who}] weights tiene {len(weights)} arrays pero hay "
                f"{len(arrays)} grupos"
            )
        for i, (a, w) in enumerate(zip(arrays, weights)):
            try:
                wa = np.asarray(w, dtype=float)
            except (TypeError, ValueError) as e:
                raise ValueError(
                    f"[{who}] weights del grupo {i} no convertible a vector "
                    f"numerico: {e}"
                ) from e
            if wa.ndim != 1 or wa.size != a.size:
                raise ValueError(
                    f"[{who}] weights del grupo {i} debe ser un vector 1D de "
                    f"longitud {a.size} (shape={wa.shape})"
                )
            if not np.all(np.isfinite(wa)):
                raise ValueError(
                    f"[{who}] weights del grupo {i} contiene NaN o infinitos"
                )
            if np.any(wa <= 0.0):
                raise ValueError(
                    f"[{who}] weights del grupo {i} contiene pesos no "
                    f"estrictamente positivos"
                )
    k = len(arrays)
    n_total = sum(a.size for a in arrays)
    if n_total <= k:
        raise ValueError(
            f"[{who}] N={n_total} <= k={k}: sin grados de libertad residuales (df2 <= 0)"
        )
    return arrays


def _weighted_median(a: np.ndarray, w: np.ndarray) -> float:
    """Mediana ponderada: primera observacion ordenada cuyo peso acumulado
    alcanza la mitad del peso total del grupo. Si el peso acumulado coincide
    exactamente con la mitad, se promedian esa observacion y la siguiente
    (convencion que reproduce exactamente la mediana clasica cuando todos
    los pesos son iguales, incluidos los grupos de tamano par)."""
    order = np.argsort(a, kind="stable")
    cum_w = np.cumsum(w[order])
    half = float(w.sum()) / 2.0
    idx = int(np.searchsorted(cum_w, half, side="left"))
    if idx + 1 < a.size and cum_w[idx] == half:
        return float((a[order[idx]] + a[order[idx + 1]]) / 2.0)
    return float(a[order[idx]])


def _anova_summaries(
    arrays: list[np.ndarray],
    weights: ArrayLike | None = None,
) -> tuple[float, float, int, int]:
    """Sumas de cuadrados del ANOVA unifactorial y grados de libertad.

    Sin pesos (weights=None):

        SSB = sum_i n_i (media_i - media_global)^2     (entre grupos)
        SSW = sum_i sum_j (x_ij - media_i)^2           (dentro de grupos)
        df1 = k - 1 ;  df2 = N - k

    Con pesos (muestras complejas; Heeringa, West & Berglund 2010, sec. 5.3):

        W_i = sum_j w_ij ;  media_i^w = sum_j w_ij x_ij / W_i
        SSB = sum_i W_i (media_i^w - media_global^w)^2
        SSW = sum_i sum_j w_ij (x_ij - media_i^w)^2
        df1 = k - 1 ;  df2 = N_filas - k   (filas fisicas, no suma de pesos)
    """
    k = len(arrays)
    n_total = sum(a.size for a in arrays)
    if weights is None:
        grand = sum(float(a.sum()) for a in arrays) / n_total
        ss_between = float(
            sum(a.size * (float(a.mean()) - grand) ** 2 for a in arrays)
        )
        ss_within = float(
            sum(float(((a - a.mean()) ** 2).sum()) for a in arrays)
        )
        return ss_between, ss_within, k - 1, n_total - k
    w_arrays = [np.asarray(w, dtype=float) for w in weights]
    w_sums = [float(w.sum()) for w in w_arrays]
    means = [float((a * w).sum()) / w_i for a, w, w_i in zip(arrays, w_arrays, w_sums)]
    grand = sum(w_i * m for w_i, m in zip(w_sums, means)) / sum(w_sums)
    ss_between = float(
        sum(w_i * (m - grand) ** 2 for w_i, m in zip(w_sums, means))
    )
    ss_within = float(
        sum(float((w * (a - m) ** 2).sum()) for a, w, m in zip(arrays, w_arrays, means))
    )
    return ss_between, ss_within, k - 1, n_total - k


def _f_ratio(ss_between: float, ss_within: float, df1: int, df2: int) -> TestResult:
    """F = (SSB/df1) / (SSW/df2) con los dos casos degenerados explicitos.

    SSW = 0 y SSB > 0  -> varianza interna nula con medias distintas:
                          separacion perfecta, F = inf y p = 0.
    SSW = 0 y SSB = 0  -> todas las observaciones (o todos los z_ij) son
                          identicas: sin senal, convencion F = 0 y p = 1.
    La comparacion exacta a 0.0 es deliberada: valores literales constantes
    producen desviaciones exactamente cero en binario; cualquier otra cifra
    deja SSW > 0 y el cociente regular es el resultado matematico correcto.
    """
    if ss_within <= 0.0:
        if ss_between > 0.0:
            return TestResult(math.inf, (df1, df2), 0.0)
        return TestResult(0.0, (df1, df2), 1.0)
    stat = (ss_between / df1) / (ss_within / df2)
    return TestResult(float(stat), (df1, df2), float(f.sf(stat, df1, df2)))


# ---------------------------------------------------------------------------
# pruebas estadisticas
# ---------------------------------------------------------------------------


def pearson_chi2(table: ArrayLike) -> TestResult:
    """Chi-cuadrado de Pearson sobre una tabla de contingencia observada I x J.

    Formula explicita (SIN correccion de continuidad de Yates; convencion
    CHAID / Kass 1980):

        N    = sum_ij O_ij ;  R_i = sum_j O_ij ;  C_j = sum_i O_ij
        E_ij = R_i * C_j / N
        chi2 = sum_ij (O_ij - E_ij)^2 / E_ij
        gl   = (I - 1) * (J - 1)
        p    = P(Chi2_gl >= chi2) = scipy.stats.chi2.sf(chi2, gl)

    Se aceptan frecuencias reales >= 0: con conteos enteros el calculo es
    exacto; con pesos reales (tablas ponderadas MRM) es la aproximacion
    estandar de Pearson. Exige tabla de al menos 2x2 y marginales de fila y
    columna estrictamente positivos (un marginal nulo produciria E_ij = 0).

    Cita: Pearson (1900), Philosophical Magazine Ser. 5, 50(302):157-175.
    """
    try:
        obs = np.asarray(table, dtype=float)
    except (TypeError, ValueError) as e:
        raise ValueError(
            f"[pearson_chi2] tabla no convertible a matriz numerica: {e}"
        ) from e
    if obs.ndim != 2 or obs.shape[0] < 2 or obs.shape[1] < 2:
        raise ValueError(
            f"[pearson_chi2] se exige una tabla 2D de al menos 2x2 (shape={obs.shape})"
        )
    if not np.all(np.isfinite(obs)):
        raise ValueError("[pearson_chi2] la tabla contiene NaN o infinitos")
    if np.any(obs < 0.0):
        raise ValueError("[pearson_chi2] frecuencias negativas no permitidas")

    row = obs.sum(axis=1)
    col = obs.sum(axis=0)
    if np.any(row <= 0.0) or np.any(col <= 0.0):
        raise ValueError(
            "[pearson_chi2] marginales nulos (fila o columna vacia): E_ij seria 0"
        )

    n_total = float(row.sum())
    expected = np.outer(row, col) / n_total
    stat = float(np.sum((obs - expected) ** 2 / expected))
    gl = (obs.shape[0] - 1) * (obs.shape[1] - 1)
    return TestResult(stat, (gl,), float(chi2.sf(stat, gl)))


def f_oneway(*groups: ArrayLike, weights: ArrayLike | None = None) -> TestResult:
    """ANOVA unifactorial (prueba F de Fisher) sobre k >= 2 grupos.

    Formula explicita:

        SSB = sum_i n_i (media_i - media_global)^2   (entre grupos)
        SSW = sum_i sum_j (x_ij - media_i)^2         (dentro de grupos)
        df1 = k - 1 ;  df2 = N - k ;  N = sum_i n_i
        F   = (SSB / df1) / (SSW / df2)
        p   = P(F_{df1,df2} >= F) = scipy.stats.f.sf(F, df1, df2)

    Con el parametro keyword-only `weights` (secuencia paralela a
    `groups`, pesos finitos y estrictamente positivos por observacion),
    las medias son medias ponderadas, los tamanos de grupo son las sumas
    de pesos W_i, y los grados de libertad siguen la convencion de
    muestras complejas: df2 = N_filas - k (filas fisicas, no pesos). Con
    weights=None el calculo es identico al original.

    Es la prueba de CHAID con TargetType.CONTINUOUS (ver types.py).
    Casos degenerados (SSW = 0): separacion perfecta -> (inf, p=0);
    todas las observaciones identicas -> (0, p=1). Ver _f_ratio.

    Citas: Fisher (1925), Statistical Methods for Research Workers.
           Heeringa, West & Berglund (2010), Applied Survey Data
           Analysis, seccion 5.3 (formula ponderada).
    """
    arrays = _validate_groups(groups, "f_oneway", weights)
    ss_between, ss_within, df1, df2 = _anova_summaries(arrays, weights)
    return _f_ratio(ss_between, ss_within, df1, df2)


def brown_forsythe(*groups: ArrayLike, weights: ArrayLike | None = None) -> TestResult:
    """Levene con centro en la mediana (Brown-Forsythe) sobre k >= 2 grupos.

    Formula explicita: se reemplazan los datos por sus desviaciones
    absolutas a la mediana de su grupo y se aplica el ANOVA unifactorial
    sobre ellas:

        z_ij = |x_ij - mediana_i|
        W    = [(N - k)/(k - 1)] * [sum_i n_i (zbar_i - zbar)^2]
                                 / [sum_i sum_j (z_ij - zbar_i)^2]
        p    = scipy.stats.f.sf(W, k - 1, N - k)

    Con el parametro keyword-only `weights`, la mediana de cada grupo es
    la mediana ponderada (primera observacion ordenada cuyo peso
    acumulado alcanza la mitad del peso total del grupo) y el ANOVA
    sobre las desviaciones es el ANOVA ponderado (ver f_oneway), con
    df2 = N_filas - k. Con weights=None el calculo es identico al
    original.

    Notese que W es exactamente el cociente F de _f_ratio aplicado a los
    z_ij. Robusta ante asimetria y colas pesadas (la mediana, a diferencia
    de la media del Levene original, no exige simetria). Numericamente
    equivalente a scipy.stats.levene(*groups, center="median").

    Citas: Brown & Forsythe (1974), JASA 69(346):364-367;
           Levene (1960), version original con centro en la media;
           Heeringa, West & Berglund (2010), Applied Survey Data
           Analysis, seccion 5.3 (formula ponderada).
    """
    arrays = _validate_groups(groups, "brown_forsythe", weights)
    if weights is None:
        zs = [np.abs(a - float(np.median(a))) for a in arrays]
    else:
        w_arrays = [np.asarray(w, dtype=float) for w in weights]
        zs = [
            np.abs(a - _weighted_median(a, w))
            for a, w in zip(arrays, w_arrays)
        ]
    ss_between, ss_within, df1, df2 = _anova_summaries(zs, weights)
    return _f_ratio(ss_between, ss_within, df1, df2)


# ---------------------------------------------------------------------------
# multiplicadores combinatorios de Kass (1980)
# ---------------------------------------------------------------------------


def stirling_second_kind(c: int, r: int) -> int:
    """S(c, r): numero de particiones de c elementos en r bloques no vacios.

    Recurrencia entera exacta (aritmetica entera de precision arbitraria,
    programacion dinamica bottom-up con una fila, memoria O(r)):

        S(0, 0) = 1
        S(c, 0) = S(0, r) = 0                  (c, r > 0)
        S(c, r) = 0                            si r > c
        S(c, r) = r * S(c-1, r) + S(c-1, r-1)

    Equivalente a la forma cerrada de inclusion-exclusion

        S(c, r) = (1/r!) * sum_{i=0}^{r} (-1)^i C(r, i) (r - i)^c

    documentada en docs/model_risk_assessment.md (ALG-01); la recurrencia se
    prefiere como implementacion auditada por evitar la cancelacion de
    signos y la division de la forma cerrada. La forma cerrada se usa como
    referencia cruzada en tests/test_statistics.py.

    Cita: Kass (1980), Applied Statistics 29(2):119-127.
    """
    c = _as_int("c", c)
    r = _as_int("r", r)
    if c < 0 or r < 0:
        raise ValueError(
            f"[stirling_second_kind] c y r deben ser >= 0 (c={c}, r={r})"
        )
    prev = [1] + [0] * r  # fila n = 0: S(0, 0) = 1, S(0, k) = 0 para k > 0
    for n in range(1, c + 1):
        cur = [0] * (r + 1)
        for k in range(1, min(n, r) + 1):
            cur[k] = k * prev[k] + prev[k - 1]
        prev = cur
    return prev[r]


def kass_multiplier(c: int, r: int, *, ordinal: bool) -> int:
    """Multiplicador de Bonferroni de Kass (1980) para el ajuste FWER en CHAID.

        ordinal=True : M = C(c-1, r-1) -- formas de elegir r-1 cortes entre
                       los c-1 separadores de c categorias ordenadas (solo
                       fusiones de categorias adyacentes).
        ordinal=False: M = S(c, r)     -- Stirling de segunda especie: formas
                       de repartir c categorias libres en r grupos no vacios
                       (cualquier par de grupos es fusionable).

    Dominio CHAID: 1 <= r <= c. Si r == 1 (la fusion no retuvo ninguna
    particion) M = 1 en ambas escalas: no hay busqueda multiple que corregir.

    Cita: Kass (1980), Applied Statistics 29(2):119-127. Corrige el riesgo
    ALG-01 de docs/model_risk_assessment.md (p. ej. c=20 -> r=3: el motor
    heredado usaba C(r,2)=3; el ajuste formal exige C(19,2)=171 en ordinal
    y S(20,3) = 580606446 en nominal).
    """
    c = _as_int("c", c)
    r = _as_int("r", r)
    if c < 1 or r < 1 or r > c:
        raise ValueError(
            f"[kass_multiplier] se exige 1 <= r <= c (c={c}, r={r})"
        )
    if ordinal:
        return math.comb(c - 1, r - 1)
    return stirling_second_kind(c, r)


def bonferroni_adjust(p: float, m: int) -> float:
    """p_adj = min(1.0, p * m)   (Kass 1980; Bonferroni nunca reduce p).

    Garantiza por construccion el invariante p_adj >= p que SplitConfig
    exige en backend_v3.types.
    """
    p = float(p)
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"[bonferroni_adjust] p fuera de [0, 1]: {p!r}")
    m = _as_int("m", m)
    if m < 1:
        raise ValueError(f"[bonferroni_adjust] m debe ser entero >= 1 (m={m})")
    return min(1.0, p * m)
