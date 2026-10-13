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


def test_target_multiclase_k3_accepted():
    """Fase 3.4.b: evaluate acepta K=3 sin error (el bloqueo interno
    del motor se retiró). Reemplaza al pre-3.4
    test_target_multiclase_valueerror.

    NOTA (corrección empírica 12/10/2026): el fixture original del
    prompt (x = [1..6], medias 1.5/3.5/5.5) produce F = 16 con
    p = 0.0250946, JUSTO por encima del umbral Bonferroni 0.025
    (alpha/(2J), J=1), así que evaluate devolvía None y el assert
    `cfg is not None` fallaba. El fixture se amplía a medias
    1.5/10.5/20.5 (F = 361.33), que sí supera el umbral. df y
    statistic_name no dependen del fixture."""
    X = pd.DataFrame({"v": pd.Series([1.0, 2.0, 10.0, 11.0, 20.0, 21.0])})
    y3 = pd.Series([0, 0, 1, 1, 2, 2])
    cfg = _engine().evaluate(X, y3, {"v": _CONTINUOUS})
    # Hay señal (medias 1.5 / 10.5 / 20.5 bien separadas): devuelve un
    # SplitConfig válido.
    assert cfg is not None
    assert isinstance(cfg, SplitConfig)
    assert cfg.predictor == "v"
    assert cfg.statistic_name == "f"
    assert cfg.df == (2, 3)  # K-1=2, N-K=3
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
# 3.2.d - Ponderación por muestra (weights keyword-only)
#
# Contrato verificado aqui:
#   * F es invariante a escala (cociente SSB/SSW).
#   * chi2 de Pearson escala linealmente con la masa total de pesos
#     (design_decisions.md §13.2; Heeringa et al. 2010 §5.4).
#   * child_ns y parent_n son siempre conteos FISICOS de filas (enteros).
#   * La varianza ponderada del QDA usa divisor W - 1 (Bessel ponderado).
# ---------------------------------------------------------------------------


def _fixture_weighted_nominal():
    # a: y0=2, y1=18 ; b: y0=3, y1=17 ; c: y0=18, y1=2
    x = pd.Series(["a"] * 20 + ["b"] * 20 + ["c"] * 20)
    y = pd.Series(
        [1] * 18 + [0] * 2 + [1] * 17 + [0] * 3 + [1] * 2 + [0] * 18
    )
    return pd.DataFrame({"cat": x}), y, {"cat": _NOMINAL}


def _fixture_weighted_continuous():
    X = pd.DataFrame({
        "fuerte": pd.Series([1.0, 2.0, 3.0, 7.0, 8.0, 9.0]),
        "plano1": pd.Series([1.0, 2.0, 3.0, 1.0, 2.0, 3.0]),
    })
    y = pd.Series([0, 0, 0, 1, 1, 1])
    return X, y, {"fuerte": _CONTINUOUS, "plano1": _CONTINUOUS}


def _assert_configs_iguales(a: SplitConfig, b: SplitConfig) -> None:
    assert a.predictor == b.predictor
    assert a.method == b.method
    assert math.isclose(a.statistic, b.statistic, rel_tol=1e-12)
    assert a.statistic_name == b.statistic_name
    assert a.df == b.df
    assert math.isclose(a.p_value, b.p_value, rel_tol=1e-12)
    assert math.isclose(a.p_value_adjusted, b.p_value_adjusted, rel_tol=1e-12)
    assert a.bonferroni_multiplier == b.bonferroni_multiplier
    assert a.parent_n == b.parent_n
    assert a.child_ns == b.child_ns
    assert a.branches == b.branches
    if a.threshold is None or b.threshold is None:
        assert a.threshold is b.threshold
    else:
        assert math.isclose(a.threshold, b.threshold, rel_tol=1e-12)


def _qda_ponderado_manual(xv, yc, w, divisor_bessel=True):
    """Replica manual del QDA ponderado (Etapa 2): medias, priors y
    varianzas ponderadas. divisor_bessel=True -> W - 1; False -> W."""
    y1 = yc == 1
    x0, x1 = xv[~y1], xv[y1]
    w0, w1 = w[~y1], w[y1]
    W0, W1 = float(w0.sum()), float(w1.sum())
    m0 = float((w0 * x0).sum()) / W0
    m1 = float((w1 * x1).sum()) / W1
    d0 = W0 - 1.0 if divisor_bessel else W0
    d1 = W1 - 1.0 if divisor_bessel else W1
    v0 = float((w0 * (x0 - m0) ** 2).sum()) / d0
    v1 = float((w1 * (x1 - m1) ** 2).sum()) / d1
    x_bar = (W0 * m0 + W1 * m1) / (W0 + W1)
    if v0 <= 0.0 or v1 <= 0.0:
        return x_bar
    pi0, pi1 = W0 / (W0 + W1), W1 / (W0 + W1)
    log_odds = math.log(pi1 / pi0)
    if math.isclose(v0, v1, rel_tol=1e-12):
        if m0 == m1:
            return x_bar
        return (m0 + m1) / 2.0 - v1 * log_odds / (m1 - m0)
    a = 1.0 / v0 - 1.0 / v1
    b = 2.0 * (m1 / v1 - m0 / v0)
    c = m0 * m0 / v0 - m1 * m1 / v1 + 2.0 * log_odds - math.log(v1 / v0)
    disc = b * b - 4.0 * a * c
    if disc < 0.0:
        return x_bar
    sq = math.sqrt(disc)
    r1 = (-b + sq) / (2.0 * a)
    r2 = (-b - sq) / (2.0 * a)
    lo, hi = (m0, m1) if m0 <= m1 else (m1, m0)
    dentro = [r for r in (r1, r2) if lo <= r <= hi]
    if not dentro:
        return x_bar
    if len(dentro) == 2 and abs(dentro[1] - x_bar) < abs(dentro[0] - x_bar):
        return dentro[1]
    return dentro[0]


def test_weighted_quest_parity_nominal():
    X, y, spec = _fixture_weighted_nominal()
    eng = _engine()
    sin = eng.evaluate(X, y, spec)
    con = eng.evaluate(X, y, spec, weights=np.ones(len(X)))
    assert sin is not None and con is not None
    _assert_configs_iguales(sin, con)


def test_weighted_quest_parity_continuous():
    X, y, spec = _fixture_weighted_continuous()
    eng = _engine()
    sin = eng.evaluate(X, y, spec)
    con = eng.evaluate(X, y, spec, weights=np.ones(len(X)))
    assert sin is not None and con is not None
    assert con.statistic_name == "f"
    _assert_configs_iguales(sin, con)


def test_weighted_quest_child_ns_physical_continuous():
    X, y, spec = _fixture_weighted_continuous()
    rng = np.random.default_rng(2026)
    w = rng.uniform(0.5, 2.0, len(X))
    cfg = _engine().evaluate(X, y, spec, weights=w)
    assert cfg is not None
    assert cfg.parent_n == len(X)
    assert sum(cfg.child_ns) == len(X)
    assert all(isinstance(n, int) for n in cfg.child_ns)


def test_weighted_quest_child_ns_physical_nominal():
    # cubre _subset_cut con el bincount paralelo de conteo fisico
    X, y, spec = _fixture_weighted_nominal()
    rng = np.random.default_rng(7)
    w = rng.uniform(0.5, 2.0, len(X))
    cfg = _engine().evaluate(X, y, spec, weights=w)
    assert cfg is not None
    assert cfg.parent_n == len(X)
    assert sum(cfg.child_ns) == len(X)
    assert all(isinstance(n, int) for n in cfg.child_ns)


def test_weighted_quest_f_is_scale_invariant():
    X, y, spec = _fixture_weighted_continuous()
    rng = np.random.default_rng(3)
    w = rng.uniform(0.5, 2.0, len(X))
    eng = _engine()
    cfg_w = eng.evaluate(X, y, spec, weights=w)
    cfg_k = eng.evaluate(X, y, spec, weights=w * 7.5)
    assert cfg_w is not None and cfg_k is not None
    assert math.isclose(cfg_w.statistic, cfg_k.statistic, rel_tol=1e-12)
    # campos estrictamente invariantes a escala
    assert cfg_w.predictor == cfg_k.predictor
    assert cfg_w.statistic_name == cfg_k.statistic_name
    assert cfg_w.df == cfg_k.df
    assert math.isclose(cfg_w.p_value, cfg_k.p_value, rel_tol=1e-12)
    assert cfg_w.child_ns == cfg_k.child_ns
    assert cfg_w.parent_n == cfg_k.parent_n
    assert cfg_w.branches == cfg_k.branches
    # NOTA: el threshold QDA NO es invariante a escala porque la varianza
    # ponderada usa divisor W - 1 (Bessel): escalar los pesos cambia el
    # factor (W - 1)/W. Es la convencion documentada en Fase 3.2.d.


def test_weighted_quest_chi2_scales_linearly():
    # hallazgo documentado en design_decisions.md §13.2: chi2 de Pearson es
    # sensible a la escala de la masa total de pesos (NO es un bug)
    X, y, spec = _fixture_weighted_nominal()
    rng = np.random.default_rng(5)
    w = rng.uniform(0.5, 2.0, len(X))
    eng = _engine()
    cfg_w = eng.evaluate(X, y, spec, weights=w)
    k = 3.0
    cfg_k = eng.evaluate(X, y, spec, weights=w * k)
    assert cfg_w is not None and cfg_k is not None
    assert cfg_w.statistic_name == "chi2"
    assert math.isclose(cfg_k.statistic, k * cfg_w.statistic, rel_tol=1e-12)
    # chi2 crece -> p-value baja (no identico)
    assert not math.isclose(cfg_k.p_value, cfg_w.p_value, rel_tol=1e-12)
    assert cfg_k.p_value < cfg_w.p_value


def test_weighted_quest_chi2_matches_manual():
    # tabla ponderada calculada a mano: A -> {y0: 1.0, y1: 5.0};
    # B -> {y0: 2.0, y1: 2.0}. alpha alto para que la Etapa 1 pase.
    x = pd.Series(["A", "A", "A", "B", "B", "B"])
    y = pd.Series([0, 1, 1, 0, 0, 1])
    w = np.array([1.0, 2.0, 3.0, 1.0, 1.0, 2.0])
    X = pd.DataFrame({"cat": x})
    cfg = _engine(alpha=0.9).evaluate(X, y, {"cat": _NOMINAL}, weights=w)
    assert cfg is not None
    assert cfg.statistic_name == "chi2"
    tab = np.array([[1.0, 5.0], [2.0, 2.0]])
    row = tab.sum(axis=1)
    col = tab.sum(axis=0)
    n_tot = float(tab.sum())
    expected = np.outer(row, col) / n_tot
    chi2_manual = float(((tab - expected) ** 2 / expected).sum())
    assert math.isclose(cfg.statistic, chi2_manual, rel_tol=1e-12)


def test_weighted_quest_qda_uses_weighted_means_and_priors():
    # pesos elegidos para que la media ponderada difiera claramente de la
    # simple: m0_simple = 2.0 vs m0_pond = 1.6 ; m1_simple = 8.0 vs 8.5
    X = pd.DataFrame({"v": pd.Series([1.0, 2.0, 3.0, 7.0, 8.0, 9.0])})
    y = pd.Series([0, 0, 0, 1, 1, 1])
    w = np.array([3.0, 1.0, 1.0, 1.0, 1.0, 4.0])
    cfg = _engine().evaluate(X, y, {"v": _CONTINUOUS}, weights=w)
    assert cfg is not None
    esperado = _qda_ponderado_manual(
        X["v"].to_numpy(), y.to_numpy(), w, divisor_bessel=True
    )
    assert math.isclose(cfg.threshold, esperado, rel_tol=1e-12)
    # y difiere del umbral NO ponderado (t = 5.0, ver test_seleccion_anova_f54)
    assert not math.isclose(cfg.threshold, 5.0, rel_tol=1e-9)


def test_weighted_quest_qda_variance_uses_w_minus_one():
    # Convencion documentada (Fase 3.2.d): la varianza ponderada del QDA
    # usa divisor W - 1 (generalizacion del n - 1 de Bessel cuando los pesos
    # actuan como frecuencias), NO el divisor W del estimador de maxima
    # verosimilitud.
    X = pd.DataFrame({"v": pd.Series([1.0, 2.0, 3.0, 7.0, 8.0, 9.0])})
    y = pd.Series([0, 0, 0, 1, 1, 1])
    w = np.array([3.0, 1.0, 1.0, 1.0, 1.0, 4.0])  # no todos iguales
    cfg = _engine().evaluate(X, y, {"v": _CONTINUOUS}, weights=w)
    assert cfg is not None
    xv, yc = X["v"].to_numpy(), y.to_numpy()
    t_wmenos1 = _qda_ponderado_manual(xv, yc, w, divisor_bessel=True)
    t_w = _qda_ponderado_manual(xv, yc, w, divisor_bessel=False)
    assert math.isclose(cfg.threshold, t_wmenos1, rel_tol=1e-12)
    # con pesos no uniformes los dos divisores dan umbrales distintos
    assert not math.isclose(t_wmenos1, t_w, rel_tol=1e-9)
    assert not math.isclose(cfg.threshold, t_w, rel_tol=1e-9)


def test_weighted_quest_rejects_wrong_length():
    X, y, spec = _fixture_weighted_continuous()
    eng = _engine()
    _assert_raises(
        ValueError, eng.evaluate, X, y, spec, weights=np.ones(len(X) + 1)
    )
    _assert_raises(
        ValueError, eng.evaluate, X, y, spec, weights=np.ones((len(X), 1))
    )


def test_weighted_quest_rejects_nonpositive():
    X, y, spec = _fixture_weighted_continuous()
    eng = _engine()
    w_cero = np.ones(len(X))
    w_cero[2] = 0.0
    _assert_raises(ValueError, eng.evaluate, X, y, spec, weights=w_cero)
    w_neg = np.ones(len(X))
    w_neg[4] = -0.5
    _assert_raises(ValueError, eng.evaluate, X, y, spec, weights=w_neg)


def test_weighted_quest_rejects_non_finite():
    X, y, spec = _fixture_weighted_continuous()
    eng = _engine()
    w_nan = np.ones(len(X))
    w_nan[0] = np.nan
    _assert_raises(ValueError, eng.evaluate, X, y, spec, weights=w_nan)
    w_inf = np.ones(len(X))
    w_inf[1] = np.inf
    _assert_raises(ValueError, eng.evaluate, X, y, spec, weights=w_inf)


def test_weighted_quest_best_split_propagates_weights():
    # chi2 escala con la masa total y F es invariante a escala: con pesos
    # uniformes k>1 el nominal gana aunque sin pesos gane el continuo.
    # (a) weights=ones reproduce exactamente la seleccion sin pesos;
    # (b) con pesos no triviales el ganador cambia de "cont" a "nom".
    n0, n1 = 30, 30
    rng = np.random.default_rng(42)
    cont = np.concatenate(
        [rng.normal(0.0, 1.0, n0), rng.normal(0.8, 1.0, n1)]
    )
    nom = np.array(
        ["a"] * (n0 - 9) + ["b"] * 9 + ["a"] * 9 + ["b"] * (n1 - 9),
        dtype=object,
    )
    X = pd.DataFrame({"cont": pd.Series(cont), "nom": pd.Series(nom)})
    y = pd.Series([0] * n0 + [1] * n1)
    spec = {"cont": _CONTINUOUS, "nom": _NOMINAL}
    eng = _engine()
    sin = eng.best_split(X, y, spec)
    ones = eng.best_split(X, y, spec, weights=np.ones(len(X)))
    assert sin is not None and ones is not None
    # (a) paridad estricta con weights=ones
    _assert_configs_iguales(sin, ones)
    assert sin.predictor == "cont"
    # (b) masa total k=8: chi2 x8 (p baja), F identico -> gana "nom"
    pesados = eng.best_split(X, y, spec, weights=np.full(len(X), 8.0))
    assert pesados is not None
    assert pesados.predictor == "nom"
    assert pesados.predictor != sin.predictor


# ---------------------------------------------------------------------------
# Fase 3.4.b: QUEST multiclase (K >= 3) + paridad binaria
# ---------------------------------------------------------------------------


def test_quest_multiclass_stage1_f_k3():
    # F de ANOVA con K=3 grupos: SSB=70, SSW=12.5, N=10, K=3
    # -> F = (70/2) / (12.5/7) = 19.6, df = (K-1, N-K) = (2, 7).
    x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    y = pd.Series([0] * 5 + [1] * 2 + [2] * 3)
    X = pd.DataFrame({"v": pd.Series(x, dtype=float)})
    cfg = _engine().evaluate(X, y, {"v": _CONTINUOUS})
    assert cfg is not None
    assert cfg.predictor == "v"
    assert cfg.statistic_name == "f"
    assert cfg.df == (2, 7)
    assert math.isclose(cfg.statistic, 19.6, rel_tol=1e-12)
    assert cfg.bonferroni_multiplier == 2  # J=1, family=2


def test_quest_multiclass_stage2_gini_k3():
    # Misma fixture: el corte optimo de Gini cae entre 5 y 6 (5.5),
    # separando la clase 0 de las clases 1+2.
    x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    y = pd.Series([0] * 5 + [1] * 2 + [2] * 3)
    X = pd.DataFrame({"v": pd.Series(x, dtype=float)})
    cfg = _engine().evaluate(X, y, {"v": _CONTINUOUS})
    assert cfg is not None
    assert cfg.threshold == 5.5
    assert cfg.branches is None  # predictor continuo
    assert cfg.child_ns == (5, 5)


def test_quest_multiclass_k3_builds():
    from backend_v3.tree_builder import TreeBuilder
    from backend_v3.types import TargetType
    x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    y = pd.Series([0] * 5 + [1] * 2 + [2] * 3)
    X = pd.DataFrame({"v": pd.Series(x)})
    model = TreeBuilder(_engine(), target_type=TargetType.CATEGORICAL,
                        target_class=0,
                        class_labels=("Low", "Mid", "High"),
                        max_depth=3, min_child_size=2).build(
        X, y, {"v": _CONTINUOUS})
    assert model.method == "QUEST"
    for nd in model.nodes:
        assert len(nd.pd_final) == 3
        assert abs(sum(nd.pd_final) - 1.0) <= 1e-12
    raiz = model.nodes[model.root_id]
    assert raiz.split is not None
    assert raiz.split.predictor == "v"


def test_quest_binary_parity_after_3_4():
    # Fixture donde QDA y el barrido de Gini divergen: si el dispatch K=2
    # tomara el camino Gini por error, el threshold seria 1.5 (primer
    # corte perfecto) y la asercion de paridad fallaria.
    # QDA: m0=0.5, m1=11.5, v0=0.5, v1=5/3, priors 1/3 y 2/3 -> raiz en el
    # intervalo inter-medias [0.5, 11.5]: t = 4.3852...
    x = [0, 1, 10, 11, 12, 13]
    y = pd.Series([0, 0, 1, 1, 1, 1])
    X = pd.DataFrame({"v": pd.Series(x, dtype=float)})
    cfg = _engine().evaluate(X, y, {"v": _CONTINUOUS})
    assert cfg is not None
    assert math.isclose(cfg.threshold, 4.3852, abs_tol=1e-4)
    assert not math.isclose(cfg.threshold, 1.5, abs_tol=1e-3)
    assert cfg.statistic_name == "f"
    assert cfg.child_ns == (2, 4)


def test_quest_multiclass_brown_forsythe_k3():
    # F-test de medias NO dispara (las tres medias son 5.0); Brown-Forsythe
    # sobre desviaciones a la mediana SI: z0=z1=0, z2=|x-5|.
    # SSB=9.6, SSW=5.6, K=3, N=30 -> W = (9.6/2) / (5.6/27) = 23.142857.
    # NOTA (correccion empirica 12/10/2026): el fixture es simetrico alre-
    # dedor de 5, asi que el barrido de Gini de la Etapa 2 empata de forma
    # EXACTA (bit a bit) entre los cortes 4.5 y 5.5 (dI = 52/507 en ambos);
    # np.argmax devuelve el primero -> threshold 4.5 y child_ns (4, 26).
    # El prompt original esperaba 5.5 y (24, 6); los valores se corrigieron
    # tras verificar el comportamiento real del motor.
    x = [5.0] * 10 + [5.0] * 10 + [3.0, 4.0, 5.0, 6.0, 7.0] * 2
    y = pd.Series([0] * 10 + [1] * 10 + [2] * 10)
    X = pd.DataFrame({"v": pd.Series(x)})
    cfg = _engine().evaluate(X, y, {"v": _CONTINUOUS})
    assert cfg is not None
    assert cfg.predictor == "v"
    assert cfg.statistic_name == "f"  # W de Brown-Forsythe es F-distribuido
    assert math.isclose(cfg.statistic, 23.142857, rel_tol=1e-5)
    assert math.isclose(cfg.threshold, 4.5, abs_tol=1e-9)
    assert cfg.child_ns == (4, 26)


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
