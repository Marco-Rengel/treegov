"""Tests de backend_v3/statistics.py (Fase 0, Paso 5).

Valores de referencia verificados a mano (aprobados en la auditoria del
diseno) y referencias cruzadas contra scipy.stats (dependencia permitida).

Ejecutable de DOS formas, sin dependencia obligatoria de pytest
(pytest NO forma parte de requirements.txt):

    .venv\\Scripts\\python -m pytest tests/test_statistics.py -v
    .venv\\Scripts\\python tests\\test_statistics.py
"""

import math
import sys
from pathlib import Path

import numpy as np
from scipy.stats import chi2
from scipy.stats import chi2_contingency
from scipy.stats import f as f_dist
from scipy.stats import f_oneway as sp_f_oneway
from scipy.stats import levene as sp_levene

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_v3.statistics import (  # noqa: E402
    bonferroni_adjust,
    brown_forsythe,
    f_oneway,
    kass_multiplier,
    pearson_chi2,
    stirling_second_kind,
)


def _assert_raises(exc_type, fn, *args, **kwargs):
    """Mini-contexto de excepcion (sustituye a pytest.raises)."""
    try:
        fn(*args, **kwargs)
    except exc_type:
        return
    except Exception as e:  # pragma: no cover - diagnostico
        raise AssertionError(
            f"{fn.__name__} lanzo {type(e).__name__} en vez de {exc_type.__name__}: {e}"
        ) from e
    raise AssertionError(f"{fn.__name__} no lanzo {exc_type.__name__}")


# ---------------------------------------------------------------------------
# Stirling de segunda especie y multiplicadores de Kass (1980)
# ---------------------------------------------------------------------------


def test_stirling_hand():
    # Valores aprobados en la auditoria del diseno:
    assert stirling_second_kind(4, 2) == 7
    assert stirling_second_kind(5, 2) == 15
    assert stirling_second_kind(5, 3) == 25
    # Bordes de la definicion:
    assert stirling_second_kind(0, 0) == 1
    assert stirling_second_kind(5, 0) == 0
    assert stirling_second_kind(5, 1) == 1
    assert stirling_second_kind(5, 5) == 1
    assert stirling_second_kind(5, 6) == 0  # r > c -> 0
    # Magnitud del riesgo ALG-01 (model_risk_assessment.md):
    # S(20,3) = (3^20 - 3*2^20 + 3)/6 = 3483638676/6
    assert stirling_second_kind(20, 3) == 580_606_446


def test_stirling_vs_closed_form():
    # Referencia cruzada: la recurrencia debe coincidir con la forma cerrada
    # de inclusion-exclusion (aritmetica entera exacta; el dividendo es
    # divisible por r! por definicion de S(c, r)).
    for c in range(1, 9):
        for r in range(0, c + 1):
            numerador = sum(
                ((-1) ** i) * math.comb(r, i) * (r - i) ** c
                for i in range(r + 1)
            )
            denominador = math.factorial(r)
            assert numerador % denominador == 0
            assert stirling_second_kind(c, r) == numerador // denominador


def test_kass_ordinal():
    # M = C(c-1, r-1); valores aprobados en la auditoria del diseno:
    assert kass_multiplier(4, 2, ordinal=True) == 3   # C(3,1) = 3
    assert kass_multiplier(5, 3, ordinal=True) == 6   # C(4,2) = 6
    assert kass_multiplier(10, 1, ordinal=True) == 1  # C(9,0) = 1
    assert kass_multiplier(7, 7, ordinal=True) == 1   # C(6,6) = 1
    # Ejemplo ALG-01: 20 percentiles -> r=3 intervalos exige C(19,2)=171
    assert kass_multiplier(20, 3, ordinal=True) == 171


def test_kass_nominal():
    # M = S(c, r): identico a la recurrencia en todo el dominio barrido
    for c in range(1, 9):
        for r in range(1, c + 1):
            assert kass_multiplier(c, r, ordinal=False) == stirling_second_kind(c, r)
    # ALG-01: el motor heredado aplicaba C(r,2)=3 donde Kass exige 580606446
    assert kass_multiplier(20, 3, ordinal=False) == 580_606_446
    assert kass_multiplier(6, 1, ordinal=False) == 1  # S(6,1) = 1
    assert kass_multiplier(6, 6, ordinal=False) == 1  # S(6,6) = 1


def test_bonferroni_adjust():
    assert bonferroni_adjust(0.002, 3) == 0.006
    assert bonferroni_adjust(0.25, 6) == 1.0          # saturacion al techo
    # El ejemplo extremo de ALG-01 satura por completo cualquier p razonable
    assert bonferroni_adjust(0.001, 580_606_446) == 1.0
    # Monotonia: el ajuste nunca reduce el p-valor (invariante SplitConfig)
    for p in (0.0, 1e-9, 0.05, 0.5, 1.0):
        for m in (1, 2, 171):
            assert bonferroni_adjust(p, m) >= p


# ---------------------------------------------------------------------------
# Chi-cuadrado de Pearson
# ---------------------------------------------------------------------------


def test_pearson_hand():
    # Tabla [[20,10],[10,20]]: marginales 30/30, E_ij = 15 en toda celda ->
    # chi2 = 4 * (5^2)/15 = 20/3 ; gl = 1
    tabla = [[20, 10], [10, 20]]
    res = pearson_chi2(tabla)
    assert res.df == (1,)
    assert math.isclose(res.statistic, 20.0 / 3.0, rel_tol=1e-12)
    assert math.isclose(res.p_value, float(chi2.sf(20.0 / 3.0, 1)), rel_tol=1e-12)
    # Referencia cruzada con scipy (sin correccion de Yates)
    ref = chi2_contingency(np.array(tabla), correction=False)
    assert math.isclose(res.statistic, ref.statistic, rel_tol=1e-12)
    assert math.isclose(res.p_value, ref.pvalue, rel_tol=1e-12)


def test_pearson_independence():
    # Filas exactamente proporcionales -> independencia perfecta:
    # E = [[6,4],[9,6]] coincide con O; chi2 = 0 y p = 1 exactos.
    res = pearson_chi2([[6, 4], [9, 6]])
    assert res.df == (1,)
    assert res.statistic == 0.0
    assert res.p_value == 1.0


def test_pearson_guards():
    _assert_raises(ValueError, pearson_chi2, [1, 2, 3])                 # no 2D
    _assert_raises(ValueError, pearson_chi2, [[1, 2, 3]])               # < 2x2
    _assert_raises(ValueError, pearson_chi2, [[1.0, 0.0], [2.0, 0.0]])  # columna nula
    _assert_raises(ValueError, pearson_chi2, [[1.0, 2.0], [0.0, 0.0]])  # fila nula
    _assert_raises(ValueError, pearson_chi2, [[1.0, 2.0], [3.0, -1.0]])  # negativo
    _assert_raises(ValueError, pearson_chi2, [[1.0, float("nan")], [2.0, 3.0]])
    _assert_raises(ValueError, pearson_chi2, [[1.0, 2.0], [3.0, float("inf")]])


# ---------------------------------------------------------------------------
# ANOVA unifactorial (F) y Brown-Forsythe (Levene con mediana)
# ---------------------------------------------------------------------------


def test_anova_hand():
    # [1,2,3],[4,5,6],[7,8,9]: medias 2/5/8, gran media 5
    # SSB = 3*9 + 0 + 3*9 = 54 ; SSW = 2 + 2 + 2 = 6 ; F = 27/1 = 27
    res = f_oneway([1, 2, 3], [4, 5, 6], [7, 8, 9])
    assert res.df == (2, 6)
    assert math.isclose(res.statistic, 27.0, rel_tol=1e-12)
    assert math.isclose(res.p_value, float(f_dist.sf(27.0, 2, 6)), rel_tol=1e-12)
    ref = sp_f_oneway([1, 2, 3], [4, 5, 6], [7, 8, 9])
    assert math.isclose(res.statistic, ref.statistic, rel_tol=1e-12)
    assert math.isclose(res.p_value, ref.pvalue, rel_tol=1e-12)


def test_brown_forsythe_hand():
    # [1,2,3] vs [4,5,6]: z identicos [1,0,1] -> W = 0 y p = 1 exactos
    res_id = brown_forsythe([1, 2, 3], [4, 5, 6])
    assert res_id.df == (1, 4)
    assert res_id.statistic == 0.0
    assert res_id.p_value == 1.0

    # [0,1,2] vs [0,2,4]: medianas 1 y 2; z = [1,0,1] y [2,0,2]
    # SSB = 2/3 ; SSW = 2/3 + 8/3 = 10/3 ; W = (2/3)/(10/12) = 4/5 = 0.8
    res = brown_forsythe([0, 1, 2], [0, 2, 4])
    assert res.df == (1, 4)
    assert math.isclose(res.statistic, 0.8, rel_tol=1e-12)
    assert math.isclose(res.p_value, float(f_dist.sf(0.8, 1, 4)), rel_tol=1e-12)
    ref = sp_levene([0, 1, 2], [0, 2, 4], center="median")
    assert math.isclose(res.statistic, ref.statistic, rel_tol=1e-12)
    assert math.isclose(res.p_value, ref.pvalue, rel_tol=1e-12)

    # Caso heterocedastico claro: solamente referencia cruzada con scipy
    low = [1.0, 1.2, 0.8, 1.1, 0.9, 1.05]
    high = [1.0, 5.0, 9.0, 2.0, 8.0, 4.5]
    res_h = brown_forsythe(low, high)
    ref_h = sp_levene(low, high, center="median")
    assert math.isclose(res_h.statistic, ref_h.statistic, rel_tol=1e-12)
    assert math.isclose(res_h.p_value, ref_h.pvalue, rel_tol=1e-12)


def test_degenerate_f():
    # Varianza interna nula con medias distintas -> separacion perfecta
    sep = f_oneway([1.0, 1.0, 1.0], [2.0, 2.0, 2.0], [3.0, 3.0, 3.0])
    assert math.isinf(sep.statistic)
    assert sep.p_value == 0.0
    # Todas las observaciones identicas -> sin senal
    flat = f_oneway([5.0, 5.0], [5.0, 5.0, 5.0])
    assert flat.statistic == 0.0
    assert flat.p_value == 1.0
    # Brown-Forsythe con ambos grupos constantes: todos los z_ij = 0
    bf_flat = brown_forsythe([3.0, 3.0], [7.0, 7.0, 7.0])
    assert bf_flat.statistic == 0.0
    assert bf_flat.p_value == 1.0


def test_anova_bf_guards():
    _assert_raises(ValueError, f_oneway, [1, 2, 3])            # un solo grupo
    _assert_raises(ValueError, f_oneway, [1, 2, 3], [])        # grupo vacio
    _assert_raises(ValueError, f_oneway, [[1, 2], [3, 4]])     # no 1D
    _assert_raises(ValueError, f_oneway, [1, 2], [float("nan"), 3.0])
    _assert_raises(ValueError, f_oneway, [1, 2], [3.0, float("inf")])
    _assert_raises(ValueError, f_oneway, [1], [2])             # N = k -> df2 = 0
    _assert_raises(ValueError, brown_forsythe, [1, 2, 3])      # un solo grupo
    _assert_raises(ValueError, brown_forsythe, [1, 2], [])     # grupo vacio


def test_kass_guards():
    _assert_raises(TypeError, stirling_second_kind, 3.5, 2)    # no entero
    _assert_raises(TypeError, stirling_second_kind, True, 2)   # bool no es int
    _assert_raises(ValueError, stirling_second_kind, -1, 2)    # negativo
    _assert_raises(ValueError, stirling_second_kind, 3, -2)
    _assert_raises(ValueError, kass_multiplier, 3, 5, ordinal=True)    # r > c
    _assert_raises(ValueError, kass_multiplier, 0, 1, ordinal=True)    # c < 1
    _assert_raises(ValueError, kass_multiplier, 5, 0, ordinal=False)   # r < 1
    _assert_raises(ValueError, bonferroni_adjust, -0.1, 2)     # p fuera de [0,1]
    _assert_raises(ValueError, bonferroni_adjust, 1.5, 2)
    _assert_raises(ValueError, bonferroni_adjust, float("nan"), 2)
    _assert_raises(ValueError, bonferroni_adjust, 0.5, 0)      # m < 1
    _assert_raises(TypeError, bonferroni_adjust, 0.5, 2.5)     # m no entero


# ---------------------------------------------------------------------------
# 3.2.a - Ponderacion por muestra (weights en f_oneway y brown_forsythe)
# ---------------------------------------------------------------------------

from backend_v3.statistics import _weighted_median  # noqa: E402


def test_weighted_f_oneway_parity_without_weights():
    # Pesos todos iguales a uno -> resultado identico al de la llamada sin
    # pesos (invariante no negociable de 3.2.a).
    g1, g2 = [1.0, 2.0, 3.0, 4.0], [2.5, 3.5, 4.5]
    ref = f_oneway(g1, g2)
    res = f_oneway(g1, g2, weights=[np.ones(4), np.ones(3)])
    assert res.statistic == ref.statistic
    assert res.df == ref.df
    assert res.p_value == ref.p_value


def test_weighted_brown_forsythe_parity_without_weights():
    # Incluye un grupo de longitud par: la mediana ponderada debe
    # reproducir exactamente numpy.median por la convencion de
    # interpolacion cuando el acumulado coincide con la mitad.
    g1, g2 = [1.0, 2.0, 3.0, 4.0], [2.5, 3.5, 4.5, 9.0]
    ref = brown_forsythe(g1, g2)
    res = brown_forsythe(g1, g2, weights=[np.ones(4), np.ones(4)])
    assert res.statistic == ref.statistic
    assert res.df == ref.df
    assert res.p_value == ref.p_value


def test_weighted_f_oneway_matches_manual_weighted_anova():
    # Calculo manual (Heeringa, West & Berglund 2010, sec. 5.3):
    #   g1 = [1,2,3], w1 = [1,2,1] -> W1 = 4, media1 = (1+4+3)/4 = 2
    #   g2 = [4,5,6,7], w2 = [1,1,2,2] -> W2 = 6, media2 = 35/6
    #   grand = (8 + 35)/10 = 4.3
    #   SSB = 4*(2-4.3)^2 + 6*(35/6-4.3)^2 = 21.16 + 6*(23/15)^2
    #   SSW = (1*1 + 2*0 + 1*1) + (121+25+2+98)/36 = 2 + 41/6 = 53/6
    #   df1 = 1, df2 = 7 - 2 = 5
    g1, w1 = [1.0, 2.0, 3.0], [1.0, 2.0, 1.0]
    g2, w2 = [4.0, 5.0, 6.0, 7.0], [1.0, 1.0, 2.0, 2.0]
    ssb = 4 * (2.0 - 4.3) ** 2 + 6 * (35.0 / 6.0 - 4.3) ** 2
    ssw = 2.0 + 41.0 / 6.0
    f_manual = (ssb / 1) / (ssw / 5)
    res = f_oneway(g1, g2, weights=[w1, w2])
    assert res.df == (1, 5)
    assert math.isclose(res.statistic, f_manual, rel_tol=1e-12)
    assert math.isclose(
        res.p_value, float(f_dist.sf(f_manual, 1, 5)), rel_tol=1e-12
    )


def test_weighted_brown_forsythe_matches_manual_weighted_anova():
    # Medianas ponderadas: g1 -> 2.0 ; g2 -> 6.0 (cum = [1,2,4,6],
    # mitad = 3, primera que la alcanza es el valor 6.0).
    #   z1 = |g1 - 2| = [1,0,1] ; z2 = |g2 - 6| = [2,1,0,1]
    #   media1^w = 2/4 = 0.5 ; media2^w = 5/6 ; grand = 0.7
    #   SSB = 4*0.04 + 6*(5/6 - 0.7)^2 ; SSW = 1 + 17/6 = 23/6
    #   df1 = 1, df2 = 7 - 2 = 5
    g1, w1 = [1.0, 2.0, 3.0], [1.0, 2.0, 1.0]
    g2, w2 = [4.0, 5.0, 6.0, 7.0], [1.0, 1.0, 2.0, 2.0]
    ssb = 4 * (0.5 - 0.7) ** 2 + 6 * (5.0 / 6.0 - 0.7) ** 2
    ssw = 1.0 + 17.0 / 6.0
    f_manual = (ssb / 1) / (ssw / 5)
    res = brown_forsythe(g1, g2, weights=[w1, w2])
    assert res.df == (1, 5)
    assert math.isclose(res.statistic, f_manual, rel_tol=1e-12)
    assert math.isclose(
        res.p_value, float(f_dist.sf(f_manual, 1, 5)), rel_tol=1e-12
    )


def test_weighted_f_oneway_scale_invariance():
    # F y p dependen solo de las proporciones relativas de los pesos,
    # no de su escala global.
    g1, g2 = [1.0, 2.0, 3.0, 4.0], [2.5, 3.5, 4.5]
    w = [[1.0, 2.0, 1.0, 3.0], [0.5, 1.5, 2.5]]
    a = f_oneway(g1, g2, weights=w)
    b = f_oneway(g1, g2, weights=[[x * 7.5 for x in wi] for wi in w])
    assert a.df == b.df
    assert math.isclose(a.statistic, b.statistic, rel_tol=1e-12)
    assert math.isclose(a.p_value, b.p_value, rel_tol=1e-12)


def test_weighted_brown_forsythe_scale_invariance():
    g1, g2 = [1.0, 2.0, 3.0, 4.0], [2.5, 3.5, 4.5]
    w = [[1.0, 2.0, 1.0, 3.0], [0.5, 1.5, 2.5]]
    a = brown_forsythe(g1, g2, weights=w)
    b = brown_forsythe(g1, g2, weights=[[x * 7.5 for x in wi] for wi in w])
    assert a.df == b.df
    assert math.isclose(a.statistic, b.statistic, rel_tol=1e-12)
    assert math.isclose(a.p_value, b.p_value, rel_tol=1e-12)


def test_weighted_f_oneway_rejects_wrong_number_of_groups():
    try:
        f_oneway([1.0, 2.0], [3.0, 4.0], [5.0, 6.0],
                 weights=[[1.0, 1.0], [1.0, 1.0]])
    except ValueError as e:
        assert "3" in str(e) and "2" in str(e)
    else:
        raise AssertionError("no lanzo ValueError")


def test_weighted_f_oneway_rejects_wrong_length_per_group():
    try:
        f_oneway([1.0, 2.0, 3.0], [4.0, 5.0, 6.0],
                 weights=[[1.0, 1.0, 1.0], [1.0, 1.0]])
    except ValueError as e:
        assert "grupo 1" in str(e)
    else:
        raise AssertionError("no lanzo ValueError")


def test_weighted_f_oneway_rejects_nonpositive_weights():
    for bad in ([1.0, 0.0], [1.0, -2.0]):
        try:
            f_oneway([1.0, 2.0], [3.0, 4.0],
                     weights=[[1.0, 1.0], bad])
        except ValueError as e:
            assert "positivos" in str(e)
        else:
            raise AssertionError("no lanzo ValueError")


def test_weighted_f_oneway_rejects_non_finite_weights():
    for bad in ([1.0, float("nan")], [1.0, float("inf")]):
        _assert_raises(
            ValueError, f_oneway, [1.0, 2.0], [3.0, 4.0],
            weights=[[1.0, 1.0], bad],
        )


def test_weighted_median_equal_weights_odd_length():
    a = np.array([5.0, 1.0, 3.0, 2.0, 4.0])
    assert _weighted_median(a, np.ones(5)) == float(np.median(a)) == 3.0


def test_weighted_median_equal_weights_even_length():
    a = np.array([4.0, 1.0, 3.0, 2.0])
    assert _weighted_median(a, np.ones(4)) == float(np.median(a)) == 2.5


def test_weighted_median_concentrated_weight():
    # Un valor con mas de la mitad del peso total ES la mediana ponderada.
    a = np.array([1.0, 2.0, 3.0])
    w = np.array([1.0, 5.0, 1.0])
    assert _weighted_median(a, w) == 2.0


def test_weighted_median_exact_half_tie():
    # Acumulado exactamente igual a la mitad -> interpola con la siguiente.
    a = np.array([1.0, 2.0])
    w = np.array([1.0, 1.0])
    assert _weighted_median(a, w) == 1.5


def test_weighted_brown_forsythe_uses_weighted_median():
    # La mediana clasica de g1 es 2.0, pero la ponderada es 1.0 (peso
    # concentrado en el primer valor). El resultado debe coincidir con el
    # calculo manual que usa la mediana ponderada, no numpy.median.
    g1, w1 = [1.0, 2.0, 3.0], [4.0, 1.0, 1.0]
    g2, w2 = [5.0, 6.0, 7.0, 8.0], [1.0, 1.0, 1.0, 1.0]
    assert float(np.median(g1)) == 2.0
    assert _weighted_median(np.array(g1), np.array(w1)) == 1.0
    # z1 = |g1 - 1| = [0,1,2] ; z2 = |g2 - 6.5| = [1.5,0.5,0.5,1.5]
    # media1^w = 3/6 = 0.5 ; media2^w = 1.0 ; grand = 0.7
    # SSB = 6*0.04 + 4*0.09 = 0.6 ; SSW = 3.5 + 1.0 = 4.5
    f_manual = (0.6 / 1) / (4.5 / 5)
    res = brown_forsythe(g1, g2, weights=[w1, w2])
    assert res.df == (1, 5)
    assert math.isclose(res.statistic, f_manual, rel_tol=1e-12)
    assert math.isclose(
        res.p_value, float(f_dist.sf(f_manual, 1, 5)), rel_tol=1e-12
    )
    # Contrast: con la mediana clasica (2.0) el F seria distinto.
    z1_classic = [abs(x - 2.0) for x in g1]
    assert not math.isclose(
        f_manual,
        _manual_weighted_anova_f(z1_classic, w1, [1.5, 0.5, 0.5, 1.5], w2),
        rel_tol=1e-9,
    )


def _manual_weighted_anova_f(z1, w1, z2, w2):
    """F del ANOVA ponderado sobre dos grupos de desviaciones (auxiliar)."""
    groups = [(np.asarray(z1), np.asarray(w1)), (np.asarray(z2), np.asarray(w2))]
    ws = [w.sum() for _, w in groups]
    means = [(a * w).sum() / w.sum() for a, w in groups]
    grand = sum(wi * m for wi, m in zip(ws, means)) / sum(ws)
    ssb = sum(wi * (m - grand) ** 2 for wi, m in zip(ws, means))
    ssw = sum((w * (a - m) ** 2).sum() for (a, w), m in zip(groups, means))
    n_rows = sum(a.size for a, _ in groups)
    return (ssb / (len(groups) - 1)) / (ssw / (n_rows - len(groups)))


# ---------------------------------------------------------------------------
# ejecucion directa sin pytest
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        obj
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nOK - {len(tests)} tests superados")
