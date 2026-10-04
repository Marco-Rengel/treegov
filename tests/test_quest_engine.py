"""Tests de backend_v3/quest_engine.py (Fase 0, Paso 8).

Valores de referencia verificados a mano (aprobados en la auditoria del
diseno, con las correcciones de fixture integradas):

  Test 1: F = 54 (seleccion por ANOVA; threshold QDA = 5.0).
  Test 2: Levene W = 72/7 (medianas exactas 5 y 5); ANOVA p = 1.
  Test 3: QDA varianzas iguales, priores iguales -> t = 0.0 exacto.
  Test 4: QDA priores desiguales -> t = -ln(5/3)/2 = -0.2554128...
  Test 5: QDA varianzas distintas -> t = (2/3)(sqrt(4 + 3 ln 4) - 1).
  Test 6: raices fuera del rango inter-medias -> fallback x̄ = 0.25.

Ejecutable de DOS formas (pytest NO es dependencia del proyecto):

    .venv\\Scripts\\python -m pytest tests/test_quest_engine.py -v
    .venv\\Scripts\\python tests\\test_quest_engine.py
"""

import logging
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import f as f_dist
from scipy.stats import levene as sp_levene

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_v3.quest_engine import QuestEngine  # noqa: E402
from backend_v3.statistics import pearson_chi2  # noqa: E402
from backend_v3.types import PredictorType, SplitConfig  # noqa: E402

_NOMINAL = PredictorType.NOMINAL
_ORDINAL = PredictorType.ORDINAL
_CONTINUOUS = PredictorType.CONTINUOUS


def _engine(**kwargs) -> QuestEngine:
    quiet = logging.getLogger("treegov.quest.tests")
    if not quiet.handlers:
        quiet.addHandler(logging.NullHandler())
    quiet.propagate = False
    return QuestEngine(logger=quiet, **kwargs)


def _assert_raises(exc_type, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc_type:
        return
    except Exception as e:  # pragma: no cover
        raise AssertionError(
            f"{fn.__name__} lanzo {type(e).__name__} en vez de {exc_type.__name__}: {e}"
        ) from e
    raise AssertionError(f"{fn.__name__} no lanzo {exc_type.__name__}")


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.mensajes: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.mensajes.append(record.getMessage())


# ---------------------------------------------------------------------------
# 1. Etapa 1: seleccion por ANOVA (F = 54 exacto) + QDA t = 5.0
# ---------------------------------------------------------------------------


def test_seleccion_anova_f54():
    # fuerte: [1,2,3]|[7,8,9] -> SSB=54, SSW=4 -> F=54, p~1.75e-3 < 0.05/6
    X = pd.DataFrame({
        "fuerte": pd.Series([1.0, 2.0, 3.0, 7.0, 8.0, 9.0]),
        "plano1": pd.Series([1.0, 2.0, 3.0, 1.0, 2.0, 3.0]),
        "plano2": pd.Series([5.0, 5.0, 5.0, 5.0, 5.0, 5.0]),
    })
    y = pd.Series([0, 0, 0, 1, 1, 1])
    cfg = _engine().evaluate(
        X, y, {"fuerte": _CONTINUOUS, "plano1": _CONTINUOUS, "plano2": _CONTINUOUS}
    )
    assert cfg is not None
    assert cfg.predictor == "fuerte"
    assert cfg.statistic_name == "f"
    assert cfg.statistic == 54.0
    assert cfg.df == (1, 4)
    assert cfg.p_value == float(f_dist.sf(54.0, 1, 4))
    assert cfg.bonferroni_multiplier == 6              # 2J
    assert cfg.p_value_adjusted == min(1.0, 6 * cfg.p_value)
    # Etapa 2: m0=2, m1=8, s0=s1=1, priores iguales -> t = (2+8)/2 = 5.0
    assert cfg.threshold == 5.0
    assert cfg.branches is None
    assert cfg.child_ns == (3, 3)
    assert cfg.parent_n == 6
    assert cfg.impurity_gain is None
    assert cfg.n_merges == 0
    assert cfg.method == "QUEST"


# ---------------------------------------------------------------------------
# 2. Desempate robusto Levene (Brown-Forsythe): W = 72/7
# ---------------------------------------------------------------------------


def test_seleccion_levene_w72_7():
    # clase0=[4,4,5,5,5,5,5,5,6,6] (media 5, mediana 5)
    # clase1=[1,2,3,4,5,5,6,7,8,9] (media 5, mediana 5)
    # ANOVA: medias iguales -> p = 1.0 (no pasa)
    # Levene: z0=[1,1,0,0,0,0,0,0,1,1] (med 0.4, SSW0=2.4)
    #         z1=[4,3,2,1,0,0,1,2,3,4] (med 2.0, SSW1=20)
    #   SSB=12.8, SSW=22.4 -> W = 12.8/(22.4/18) = 72/7; p~0.0048 < 0.025
    x = pd.Series(
        [4.0, 4.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 6.0, 6.0]
        + [1.0, 2.0, 3.0, 4.0, 5.0, 5.0, 6.0, 7.0, 8.0, 9.0]
    )
    y = pd.Series([0] * 10 + [1] * 10)
    X = pd.DataFrame({"var": x})
    cfg = _engine().evaluate(X, y, {"var": _CONTINUOUS})
    assert cfg is not None
    assert cfg.statistic_name == "f"
    assert math.isclose(cfg.statistic, 72.0 / 7.0, rel_tol=1e-12)
    assert cfg.df == (1, 18)
    ref = sp_levene(x.iloc[:10], x.iloc[10:], center="median")
    assert math.isclose(cfg.statistic, ref.statistic, rel_tol=1e-12)
    assert 0.0 <= cfg.p_value <= 1.0
    assert math.isclose(cfg.p_value, ref.pvalue, rel_tol=1e-12)
    assert cfg.bonferroni_multiplier == 2
    # Etapa 2 con m0 == m1 = 5: rango inter-medias degenera -> fallback x̄=5.0
    assert cfg.threshold == 5.0
    assert cfg.child_ns == (14, 6)


# ---------------------------------------------------------------------------
# 3. QDA varianzas iguales, priores iguales: t = 0 exacto (e2e)
# ---------------------------------------------------------------------------


def test_qda_varianzas_iguales_e2e():
    # [-4,-3,-2]|[2,3,4]: SSB=54, SSW=4 -> F=54 (pasa Etapa 1)
    # QDA: m0=-3, m1=3, v0=v1=1, priores 1/2 -> t = 0.0
    X = pd.DataFrame({"v": pd.Series([-4.0, -3.0, -2.0, 2.0, 3.0, 4.0])})
    y = pd.Series([0, 0, 0, 1, 1, 1])
    cfg = _engine().evaluate(X, y, {"v": _CONTINUOUS})
    assert cfg is not None
    assert cfg.threshold == 0.0
    assert cfg.statistic == 54.0
    assert cfg.child_ns == (3, 3)


# ---------------------------------------------------------------------------
# 4-6. QDA unidad interna (valores exactos verificados a mano)
# ---------------------------------------------------------------------------


def test_qda_priors_desiguales_unidad():
    # clase0=[-2,-1,0] (m=-1, s2=1, n=3); clase1=[0,1,2,0,2] (m=1, s2=1, n=5)
    # LDA: t = (m0+m1)/2 - s2 ln(pi1/pi0)/(m1-m0) = -ln(5/3)/2
    eng = _engine()
    xv = np.array([-2.0, -1.0, 0.0, 0.0, 1.0, 2.0, 0.0, 2.0])
    yc = np.array([0, 0, 0, 1, 1, 1, 1, 1])
    t = eng._qda_cutpoint(xv, yc, "priors")
    esperado = -math.log(5.0 / 3.0) / 2.0
    assert math.isclose(t, esperado, rel_tol=1e-12)


def test_qda_varianzas_distintas_unidad():
    # clase0=[-1,0,1] (m=0, s2=1); clase1=[0,2,4] (m=2, s2=4); priores iguales
    # A=3/4, B=1, C=-1-ln4 -> disc = 4 + 3 ln 4 ; t = (-1+sqrt(disc))/1.5
    eng = _engine()
    xv = np.array([-1.0, 0.0, 1.0, 0.0, 2.0, 4.0])
    yc = np.array([0, 0, 0, 1, 1, 1])
    t = eng._qda_cutpoint(xv, yc, "vardist")
    esperado = (2.0 / 3.0) * (math.sqrt(4.0 + 3.0 * math.log(4.0)) - 1.0)
    assert math.isclose(t, esperado, rel_tol=1e-12)
    # la otra raiz (-B - sqrt)/2A = -2.5709 queda fuera de [0, 2]


def test_qda_fallback_unidad():
    # clase0=[-1,0,1] (m=0, s2=1); clase1=[-3.5,0.5,4.5] (m=0.5, s2=16)
    # raices 1.6915 y -1.7582: fuera de [0, 0.5] -> fallback x̄ = 1.5/6 = 0.25
    eng = _engine()
    xv = np.array([-1.0, 0.0, 1.0, -3.5, 0.5, 4.5])
    yc = np.array([0, 0, 0, 1, 1, 1])
    t = eng._qda_cutpoint(xv, yc, "fallback")
    assert t == 0.25


# ---------------------------------------------------------------------------
# 7. Nominal gana: Etapa 1 chi2 + Etapa 2 subset exhaustivo (estilo C&RT)
# ---------------------------------------------------------------------------


def test_categorica_gana_subset():
    # a: y0=2, y1=18 ; b: y0=3, y1=17 ; c: y0=18, y1=2
    x = pd.Series(["a"] * 20 + ["b"] * 20 + ["c"] * 20)
    y = pd.Series(
        [1] * 18 + [0] * 2 + [1] * 17 + [0] * 3 + [1] * 2 + [0] * 18
    )
    X = pd.DataFrame({"cat": x})
    cfg = _engine().evaluate(X, y, {"cat": _NOMINAL})
    assert cfg is not None
    assert cfg.statistic_name == "chi2"
    assert cfg.df == (2,)
    # cruce con statistics sobre la tabla EXACTA del pipeline (int64 vía
    # crosstab; la ruta float puede differir en 1 ulp por orden de suma)
    tabla_ref = pd.crosstab(x, y)
    assert math.isclose(
        cfg.statistic, pearson_chi2(tabla_ref).statistic, rel_tol=1e-12
    )
    assert cfg.bonferroni_multiplier == 2
    assert cfg.threshold is None
    # particion por dGini maximo: {a,b} | {c}   (dI = 961/3600)
    assert cfg.branches == (("a", "b"), ("c",))
    assert cfg.child_ns == (40, 20)
    assert cfg.impurity_gain is None
    assert cfg.n_merges == 0
    assert cfg.method == "QUEST"


# ---------------------------------------------------------------------------
# 8. Target multiclase -> ValueError (restriccion Fase 0)
# ---------------------------------------------------------------------------


def test_target_multiclase_valueerror():
    X = pd.DataFrame({"v": pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])})
    y3 = pd.Series([0, 0, 1, 1, 2, 2])
    _assert_raises(
        ValueError, _engine().evaluate, X, y3, {"v": _CONTINUOUS}
    )
    # una sola clase -> None (nodo puro, sin error)
    y1 = pd.Series([1, 1, 1, 1, 1, 1])
    assert _engine().evaluate(X, y1, {"v": _CONTINUOUS}) is None


# ---------------------------------------------------------------------------
# 9. Separacion perfecta (SSW=0 -> F=inf) -> None + WARNING
# ---------------------------------------------------------------------------


def test_separacion_perfecta_no_representable():
    capt = _ListHandler()
    log = logging.getLogger("treegov.quest.perf")
    log.handlers = [capt]
    log.propagate = False
    log.setLevel(logging.DEBUG)
    eng = QuestEngine(logger=log)
    X = pd.DataFrame({"v": pd.Series([1.0, 1.0, 1.0, 3.0, 3.0, 3.0])})
    y = pd.Series([0, 0, 0, 1, 1, 1])
    assert eng.evaluate(X, y, {"v": _CONTINUOUS}) is None
    assert any("no representable" in m for m in capt.mensajes)


# ---------------------------------------------------------------------------
# 10. Guards, empate, ordinal simbolico y humo
# ---------------------------------------------------------------------------


def test_guards_quest():
    _assert_raises(ValueError, QuestEngine, alpha=0.0)
    _assert_raises(ValueError, QuestEngine, alpha=1.0)
    _assert_raises(ValueError, QuestEngine, max_exhaustive_cardinality=1)
    eng = _engine()
    X = pd.DataFrame({"v": pd.Series([1.0, 2.0, 3.0, 4.0])})
    y = pd.Series([0, 0, 1, 1])
    _assert_raises(ValueError, eng.evaluate, X, y, {})                 # spec vacio
    _assert_raises(ValueError, eng.evaluate, X, y, {"zz": _CONTINUOUS})  # ausente
    Xl = pd.DataFrame({"v": pd.Series([1.0, 2.0, 3.0])})
    _assert_raises(
        ValueError, eng.evaluate, Xl, pd.Series([0, 1]), {"v": _CONTINUOUS}
    )  # longitudes distintas (3 vs 2)


def test_empate_determinista_primera_del_spec():
    v = pd.Series([1.0, 2.0, 3.0, 7.0, 8.0, 9.0])
    X = pd.DataFrame({"p1": v, "p2": v.copy()})
    y = pd.Series([0, 0, 0, 1, 1, 1])
    cfg = _engine().evaluate(X, y, {"p1": _CONTINUOUS, "p2": _CONTINUOUS})
    assert cfg is not None and cfg.predictor == "p1"


def test_ordinal_simbolico_e2e():
    # low/high con solape 19/75: F pasa; QDA sobre codigos -> t=0.5 -> grupos
    x = pd.Series(["1_low"] * 75 + ["2_high"] * 75)
    y = pd.Series([0] * 56 + [1] * 19 + [0] * 19 + [1] * 56)
    cfg = _engine().evaluate(
        pd.DataFrame({"ord": x}), y, {"ord": _ORDINAL}
    )
    assert cfg is not None
    assert cfg.threshold is None
    assert cfg.branches == (("1_low",), ("2_high",))
    assert cfg.child_ns == (75, 75)
    assert cfg.statistic_name == "f"
    assert cfg.df == (1, 148)


def test_humo_n200k():
    rng = np.random.default_rng(11)
    n = 200_000
    z = rng.normal(0.0, 1.0, n)
    p1 = 1.0 / (1.0 + np.exp(-0.8 * z))
    y = pd.Series((rng.random(n) < p1).astype(np.int8))
    cats = np.array([f"c{i:02d}" for i in range(8)], dtype=object)
    X = pd.DataFrame({
        "senial": pd.Series(z),
        "ruido1": pd.Series(rng.normal(0, 1, n)),
        "ruido2": pd.Series(rng.normal(0, 1, n)),
        "cat1": pd.Series(cats[rng.integers(0, 8, n)]),
        "cat2": pd.Series(cats[rng.integers(0, 8, n)]),
    })
    spec = {"senial": _CONTINUOUS, "ruido1": _CONTINUOUS, "ruido2": _CONTINUOUS,
            "cat1": _NOMINAL, "cat2": _NOMINAL}
    eng = _engine()
    t0 = time.perf_counter()
    cfg = eng.evaluate(X, y, spec)
    dt = time.perf_counter() - t0
    assert cfg is not None and isinstance(cfg, SplitConfig)
    assert cfg.predictor == "senial"
    assert cfg.parent_n == n
    assert sum(cfg.child_ns) == n
    assert dt < 10.0, f"humo QUEST 200k demasiado lento: {dt:.2f}s"
    print(f"[humo] QUEST N=200k, J=5 -> {dt:.3f}s "
          f"(gana {cfg.predictor!r}, p_adj={cfg.p_value_adjusted:.3g})")


# ---------------------------------------------------------------------------
# 11. Fase 3.0.g: parámetros configurables (bonferroni_family,
#     nominal_high_card, qda_root_restriction)
# ---------------------------------------------------------------------------


def test_bonferroni_family_canonical():
    """bonferroni_family=1: umbral canonico Loh & Shih alpha/J (multiplier J)."""
    # mismo fixture que test_seleccion_anova_f54: F = 54 exacto
    X = pd.DataFrame({
        "fuerte": pd.Series([1.0, 2.0, 3.0, 7.0, 8.0, 9.0]),
        "plano1": pd.Series([1.0, 2.0, 3.0, 1.0, 2.0, 3.0]),
        "plano2": pd.Series([5.0, 5.0, 5.0, 5.0, 5.0, 5.0]),
    })
    y = pd.Series([0, 0, 0, 1, 1, 1])
    cfg = _engine(bonferroni_family=1).evaluate(
        X, y, {"fuerte": _CONTINUOUS, "plano1": _CONTINUOUS, "plano2": _CONTINUOUS}
    )
    assert cfg is not None
    assert cfg.bonferroni_multiplier == 3              # J (no 2J)
    assert cfg.p_value_adjusted == min(1.0, 3 * cfg.p_value)
    # la seleccion no cambia respecto al default conservador
    assert cfg.predictor == "fuerte"
    assert cfg.statistic == 54.0


def test_bonferroni_family_invalid():
    """Guards de bonferroni_family: entero >= 1; bool rechazado."""
    _assert_raises(ValueError, _engine, bonferroni_family=0)
    _assert_raises(ValueError, _engine, bonferroni_family=-1)
    _assert_raises(ValueError, _engine, bonferroni_family=True)


def test_qda_root_restriction_canonical():
    """qda_root_restriction=False: raiz mas cercana a x_bar, sin fallback."""
    # mismo fixture que test_qda_fallback_unidad: raices reales 1.6915 y
    # -1.7582, ambas fuera del rango inter-medias [0, 0.5]
    xv = np.array([-1.0, 0.0, 1.0, -3.5, 0.5, 4.5])
    yc = np.array([0, 0, 0, 1, 1, 1])
    # modo restringido (default): fallback x_bar = 0.25
    assert _engine()._qda_cutpoint(xv, yc, "restringido") == 0.25
    # modo canonico: raiz mas cercana a x_bar=0.25 -> 1.6915 (no fallback)
    eng_canonical = _engine(qda_root_restriction=False)
    t_canonical = eng_canonical._qda_cutpoint(xv, yc, "canonical")
    assert math.isclose(t_canonical, 1.6915, abs_tol=1e-3)
    assert t_canonical != 0.25


def test_nominal_high_card_dummies_lda_not_implemented():
    """nominal_high_card: 'dummies_lda' reservado; defaults del engine."""
    _assert_raises(NotImplementedError, _engine, nominal_high_card="dummies_lda")
    _assert_raises(ValueError, _engine, nominal_high_card="invalido")
    _assert_raises(ValueError, _engine, nominal_high_card=123)
    # defaults que preservan el comportamiento Fase 0
    eng = _engine()
    assert eng.nominal_high_card == "rate"
    assert eng.bonferroni_family == 2
    assert eng.qda_root_restriction is True


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
