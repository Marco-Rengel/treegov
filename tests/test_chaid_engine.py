"""Tests de backend_v3/chaid_engine.py (Fase 0, Paso 6).

Valores de referencia verificados a mano (calculos en la aprobacion del
diseno) y referencias cruzadas contra backend_v3.statistics (ya auditado).

Ejecutable de DOS formas (pytest NO es dependencia del proyecto):

    .venv\\Scripts\\python -m pytest tests/test_chaid_engine.py -v
    .venv\\Scripts\\python tests\\test_chaid_engine.py
"""

import logging
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_v3.chaid_engine import ChaidEngine  # noqa: E402
from backend_v3.statistics import (  # noqa: E402
    bonferroni_adjust,
    kass_multiplier,
    pearson_chi2,
)
from backend_v3.types import PredictorType, SplitConfig, TargetType  # noqa: E402

_NOMINAL = PredictorType.NOMINAL
_ORDINAL = PredictorType.ORDINAL
_BINARY = TargetType.BINARY
_CATEGORICAL = TargetType.CATEGORICAL
_CONTINUOUS = TargetType.CONTINUOUS


def _engine(**kwargs) -> ChaidEngine:
    """ChaidEngine con logging silenciado (los WARNINGs se prueban indirectos)."""
    quiet = logging.getLogger("treegov.chaid.tests")
    if not quiet.handlers:
        quiet.addHandler(logging.NullHandler())
    quiet.propagate = False
    return ChaidEngine(logger=quiet, **kwargs)


def _assert_raises(exc_type, fn, *args, **kwargs):
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
# fixtures verificados a mano
# ---------------------------------------------------------------------------


def _fixture_binario():
    """a=[30,10] b=[31,9] c=[2,18] (filas cols y=0,1).

    Par a-b: chi2=0.069, p=0.793 > 0.05  -> fusion.
    (ab) vs c: chi2=30.1267, gl=1, M=S(3,2)=3.
    """
    x = pd.Series(["a"] * 40 + ["b"] * 40 + ["c"] * 20)
    y = pd.Series(
        [0] * 30 + [1] * 10 + [0] * 31 + [1] * 9 + [0] * 2 + [1] * 18
    )
    return x, y


def _fixture_exhaustive():
    """a=[2,8] b=[1,9] c=[5,5] d=[9,1] (cols y=0,1).

    Historial exhaustive esperado:
      r=4: chi2=15.857, gl=3, M=S(4,4)=1
      r=3: fusiona a-b (max p_par=0.531); chi2=15.652, gl=2, M=S(4,3)=6
      r=2: fusiona c-d (max p_par=0.051); chi2=12.378, gl=1, M=S(4,2)=7
    """
    x = pd.Series(["a"] * 10 + ["b"] * 10 + ["c"] * 10 + ["d"] * 10)
    y = pd.Series(
        [0] * 2 + [1] * 8 + [0] * 1 + [1] * 9 + [0] * 5 + [1] * 5 + [0] * 9 + [1] * 1
    )
    return x, y


# ---------------------------------------------------------------------------
# 1. CHAID clasico, target binario: fusion, M de Kass, p_adj
# ---------------------------------------------------------------------------


def test_clasico_binario_fusion():
    x, y = _fixture_binario()
    eng = _engine()
    cfg = eng.evaluate(
        x, y, predictor="x_bin", predictor_type=_NOMINAL, target_type=_BINARY
    )
    assert cfg is not None
    # fusion a-b -> ramas
    assert cfg.branches == (("a", "b"), ("c",))
    assert cfg.child_ns == (80, 20)
    assert cfg.parent_n == 100
    assert cfg.n_merges == 1
    # evaluacion global identica a statistics.pearson_chi2 de la tabla final
    final = pearson_chi2([[61, 19], [2, 18]])
    assert cfg.statistic == final.statistic
    assert cfg.p_value == final.p_value
    assert cfg.df == (1,)
    assert math.isclose(cfg.statistic, 30.126555126555125, rel_tol=1e-12)
    # Kass: M = S(3,2) = 3 (nominal); p_adj = min(1, 3*p)
    assert cfg.bonferroni_multiplier == 3
    assert cfg.bonferroni_multiplier == kass_multiplier(3, 2, ordinal=False)
    assert cfg.p_value_adjusted == bonferroni_adjust(final.p_value, 3)
    assert cfg.p_value_adjusted >= cfg.p_value
    # diagnostico
    d = eng.diagnostics
    assert d.n_categories == 3 and d.n_final_groups == 2
    assert d.n_forced_merges == 0 and d.cochran_ok is True
    assert d.exhaustive_steps == ()


# ---------------------------------------------------------------------------
# 2. CHAID clasico, target multiclase K=3 (tabla c x K)
# ---------------------------------------------------------------------------


def test_clasico_multiclase_k3():
    # p=[10,10,10] r=[10,9,11] q=[27,2,1] (cols y=0,1,2)
    x = pd.Series(["p"] * 30 + ["r"] * 30 + ["q"] * 30)
    y = pd.Series(
        [0] * 10 + [1] * 10 + [2] * 10
        + [0] * 10 + [1] * 9 + [2] * 11
        + [0] * 27 + [1] * 2 + [2] * 1
    )
    eng = _engine()
    cfg = eng.evaluate(
        x, y, predictor="x_k3", predictor_type=_NOMINAL, target_type=_CATEGORICAL
    )
    assert cfg is not None
    # par p-r: chi2=0.1003, p=0.951 -> fusion; gl global = (2-1)*(3-1) = 2
    assert cfg.branches == (("p", "r"), ("q",))
    assert cfg.df == (2,)
    assert cfg.child_ns == (60, 30)
    final = pearson_chi2([[20, 19, 21], [27, 2, 1]])
    assert cfg.statistic == final.statistic
    assert math.isclose(cfg.statistic, 25.859560652113846, rel_tol=1e-12)
    assert cfg.bonferroni_multiplier == kass_multiplier(3, 2, ordinal=False) == 3
    assert cfg.p_value_adjusted == bonferroni_adjust(final.p_value, 3)


# ---------------------------------------------------------------------------
# 3. CHAID clasico, target continuo: F-test en lugar de chi2
# ---------------------------------------------------------------------------


def test_clasico_continuo_f():
    # a=[1,2,3,2] b=[1,3,2,2] c=[20,21,19,20]
    # par a-b: medias 2 y 2 -> SSB=0 -> p=1 -> fusion
    # global (ab) vs c: SSW=6, SSB=864, F=864/(6/10)=1440, df=(1,10)
    x = pd.Series(["a"] * 4 + ["b"] * 4 + ["c"] * 4)
    y = pd.Series(
        [1.0, 2.0, 3.0, 2.0, 1.0, 3.0, 2.0, 2.0, 20.0, 21.0, 19.0, 20.0]
    )
    eng = _engine()
    cfg = eng.evaluate(
        x, y, predictor="x_cont", predictor_type=_NOMINAL, target_type=_CONTINUOUS
    )
    assert cfg is not None
    assert cfg.statistic_name == "f"
    assert cfg.branches == (("a", "b"), ("c",))
    assert cfg.child_ns == (8, 4)
    assert cfg.parent_n == 12
    assert cfg.df == (1, 10)
    assert math.isclose(cfg.statistic, 1440.0, rel_tol=1e-12)
    from scipy.stats import f as f_dist

    assert cfg.p_value == float(f_dist.sf(1440.0, 1, 10))
    assert cfg.bonferroni_multiplier == 3
    assert cfg.p_value_adjusted == bonferroni_adjust(cfg.p_value, 3)


# ---------------------------------------------------------------------------
# 4. Exhaustive CHAID: historial completo y argmin de p ajustado
# ---------------------------------------------------------------------------


def test_exhaustive_historial_y_argmin():
    x, y = _fixture_exhaustive()
    eng = _engine(exhaustive=True)
    cfg = eng.evaluate(
        x, y, predictor="x_exh", predictor_type=_NOMINAL, target_type=_BINARY
    )
    assert cfg is not None
    steps = eng.diagnostics.exhaustive_steps
    assert len(steps) == 3
    assert [s.n_groups for s in steps] == [4, 3, 2]

    # paso 0: estado inicial, sin fusion
    assert steps[0].merged_pair == ()
    assert math.isnan(steps[0].pair_p_value)
    p4 = pearson_chi2([[2, 8], [1, 9], [5, 5], [9, 1]]).p_value
    assert steps[0].global_p_value == p4
    assert steps[0].adjusted_p_value == bonferroni_adjust(p4, 1)

    # paso 1: fusiona a-b (par de mayor p = 0.531); M = S(4,3) = 6
    assert steps[1].merged_pair == (0, 1)
    assert steps[1].pair_p_value == pearson_chi2([[2, 8], [1, 9]]).p_value
    p3 = pearson_chi2([[3, 17], [5, 5], [9, 1]]).p_value
    assert steps[1].global_p_value == p3
    assert steps[1].adjusted_p_value == bonferroni_adjust(p3, 6)

    # paso 2: fusiona c-d (mayor p restante = 0.051); M = S(4,2) = 7
    assert steps[2].merged_pair == (1, 2)
    assert steps[2].pair_p_value == pearson_chi2([[5, 5], [9, 1]]).p_value
    p2 = pearson_chi2([[3, 17], [14, 6]]).p_value
    assert steps[2].global_p_value == p2
    assert steps[2].adjusted_p_value == bonferroni_adjust(p2, 7)

    # argmin de p_adj corresponde al paso 0 (0.0012 < 0.0024 < 0.0030):
    # el exhaustivo retiene las 4 categorias originales
    assert steps[0].adjusted_p_value < steps[1].adjusted_p_value
    assert steps[0].adjusted_p_value < steps[2].adjusted_p_value
    assert cfg.n_merges == 0
    assert len(cfg.branches) == 4
    assert cfg.bonferroni_multiplier == 1
    assert cfg.p_value_adjusted == cfg.p_value

    # contraste: el clasico con los mismos datos SI fusiona hasta r=2
    cfg_clasico = _engine().evaluate(
        x, y, predictor="x_exh", predictor_type=_NOMINAL, target_type=_BINARY
    )
    assert cfg_clasico is not None
    assert cfg_clasico.n_merges == 2
    assert len(cfg_clasico.branches) == 2
    assert cfg_clasico.bonferroni_multiplier == 7


def _fixture_exhaustive_limpio():
    """FIX 3 (hallazgo de auditoria): fixture exhaustive sin violacion Cochran.

    a=[32,8] b=[31,9] c=[8,12] d=[9,11] (filas x, cols y=0,1); N=120.
    E por fila: [26.67, 13.33] (40 obs) y [13.33, 6.67] (20 obs): todas >= 5
    -> la regla de Cochran NO se activa en ningun paso (n_forced=0).

    Fusiones: par a-b p=0.7847 (max) -> fusion; r=3: par c-d p=0.7491 (max)
    -> fusion. El camino clasico y el historial exhaustivo coinciden:
    merged_pairs (0,1) y (1,2). p_adj global: r=4: chi2=15.938, gl=3, p_adj~1.16e-3;
    r=3: chi2=15.881, gl=2, p_adj~2.15e-3; r=2: chi2=15.769, gl=1, p_adj~5.01e-4.
    argmin -> r=2: el exhaustivo CIERRA EN LA MISMA PARTICION que el clasico.
    """
    x = pd.Series(["a"] * 40 + ["b"] * 40 + ["c"] * 20 + ["d"] * 20)
    y = pd.Series(
        [0] * 32 + [1] * 8 + [0] * 31 + [1] * 9 + [0] * 8 + [1] * 12 + [0] * 9 + [1] * 11
    )
    return x, y


def test_exhaustive_fixture_limpio_mismo_camino_clasico():
    x, y = _fixture_exhaustive_limpio()

    # --- camino clasico: dos fusiones (a-b, c-d) y termina en r=2 ---
    eng_c = _engine()
    cfg_c = eng_c.evaluate(
        x, y, predictor="limpio", predictor_type=_NOMINAL, target_type=_BINARY
    )
    assert cfg_c is not None
    assert eng_c.diagnostics.n_forced_merges == 0
    assert eng_c.diagnostics.cochran_ok is True
    assert cfg_c.n_merges == 2
    assert cfg_c.branches == (("a", "b"), ("c", "d"))
    assert cfg_c.child_ns == (80, 40)
    assert cfg_c.bonferroni_multiplier == kass_multiplier(4, 2, ordinal=False) == 7
    final_c = pearson_chi2([[63, 17], [17, 23]])
    assert cfg_c.statistic == final_c.statistic
    assert math.isclose(cfg_c.statistic, 15.76875, rel_tol=1e-12)
    assert cfg_c.p_value_adjusted == bonferroni_adjust(final_c.p_value, 7)

    # --- exhaustivo: historial identico al camino clasico, paso 0 gana ---
    eng_e = _engine(exhaustive=True)
    cfg_e = eng_e.evaluate(
        x, y, predictor="limpio", predictor_type=_NOMINAL, target_type=_BINARY
    )
    assert cfg_e is not None
    assert eng_e.diagnostics.n_forced_merges == 0
    assert eng_e.diagnostics.cochran_ok is True
    steps = eng_e.diagnostics.exhaustive_steps
    assert [s.n_groups for s in steps] == [4, 3, 2]
    assert steps[0].merged_pair == () and math.isnan(steps[0].pair_p_value)
    assert steps[1].merged_pair == (0, 1)   # a-b (igual que el clasico)
    assert steps[2].merged_pair == (1, 2)   # c-d (igual que el clasico)
    assert steps[1].pair_p_value == pearson_chi2([[32, 8], [31, 9]]).p_value
    assert math.isclose(steps[1].pair_p_value, 0.7847, rel_tol=1e-3)
    assert steps[2].pair_p_value == pearson_chi2([[8, 12], [9, 11]]).p_value
    assert math.isclose(steps[2].pair_p_value, 0.7491, rel_tol=1e-3)
    # p_adj por paso (cruzado con statistics)
    p4 = pearson_chi2([[32, 8], [31, 9], [8, 12], [9, 11]]).p_value
    p3 = pearson_chi2([[63, 17], [8, 12], [9, 11]]).p_value
    p2 = pearson_chi2([[63, 17], [17, 23]]).p_value
    assert steps[0].adjusted_p_value == bonferroni_adjust(p4, 1)
    assert steps[1].adjusted_p_value == bonferroni_adjust(p3, 6)
    assert steps[2].adjusted_p_value == bonferroni_adjust(p2, 7)
    # argmin: r=2 -> exhaustivo y clasico coinciden en la particion final
    assert cfg_e.branches == (("a", "b"), ("c", "d"))
    assert cfg_e.n_merges == 2
    assert cfg_e.bonferroni_multiplier == 7
    assert cfg_e.p_value_adjusted == bonferroni_adjust(p2, 7)
    # mismo SplitConfig de particion que el clasico (campos relevantes)
    assert cfg_e.statistic == cfg_c.statistic
    assert cfg_e.p_value_adjusted == cfg_c.p_value_adjusted


# ---------------------------------------------------------------------------
# 5. Ordinal vs nominal: adyacencia y multiplicador de Kass
# ---------------------------------------------------------------------------


def test_ordinal_vs_nominal():
    # 0: [0, 20]  1: [20, 0]  2: [2, 18] (cols y=0,1)
    # nominal: el par no adyacente (0, 2) tiene el mayor p (0.147) -> fusiona
    # ordinal: solo adyacentes (0,1) y (1,2), ambos p << 0.05 -> NO fusiona
    x = pd.Series([0] * 20 + [1] * 20 + [2] * 20)
    y = pd.Series([1] * 20 + [0] * 20 + [1] * 18 + [0] * 2)

    cfg_nom = _engine().evaluate(
        x, y, predictor="x_o", predictor_type=_NOMINAL, target_type=_BINARY
    )
    assert cfg_nom is not None
    assert cfg_nom.branches == ((0, 2), (1,))
    assert cfg_nom.bonferroni_multiplier == kass_multiplier(3, 2, ordinal=False) == 3

    cfg_ord = _engine().evaluate(
        x, y, predictor="x_o", predictor_type=_ORDINAL, target_type=_BINARY
    )
    assert cfg_ord is not None
    assert cfg_ord.branches == ((0,), (1,), (2,))
    assert cfg_ord.bonferroni_multiplier == kass_multiplier(3, 3, ordinal=True) == 1
    assert cfg_ord.n_merges == 0
    assert cfg_ord.df == (2,)


# ---------------------------------------------------------------------------
# 6. Cochran (1954): fusion forzada activa
# ---------------------------------------------------------------------------


def test_cochran_fusion_forzada():
    # a=[10,90] b=[40,60] c=[0,3] (cols y=0,1); E_c0 = 0.739 < 1 -> viola
    x = pd.Series(["a"] * 100 + ["b"] * 100 + ["c"] * 3)
    y = pd.Series([1] * 90 + [0] * 10 + [1] * 60 + [0] * 40 + [1] * 3)
    eng = _engine()
    cfg = eng.evaluate(
        x, y, predictor="x_coch", predictor_type=_NOMINAL, target_type=_BINARY
    )
    d = eng.diagnostics
    # la fila minima (c) se fusiona con el par de mayor p (a: p=0.567 > b: 0.161)
    assert d.n_forced_merges == 1
    assert cfg is not None
    assert cfg.branches == (("a", "c"), ("b",))
    assert cfg.child_ns == (103, 100)
    assert d.cochran_ok is True  # tabla final [[10,93],[40,60]] ya no viola
    final = pearson_chi2([[10, 93], [40, 60]])
    assert cfg.statistic == final.statistic
    assert math.isclose(cfg.statistic, 25.078789263278132, rel_tol=1e-12)
    assert cfg.bonferroni_multiplier == 3
    assert cfg.p_value_adjusted == bonferroni_adjust(final.p_value, 3)


# ---------------------------------------------------------------------------
# 7. Casos borde
# ---------------------------------------------------------------------------


def test_borde_nan_dropna():
    x, y = _fixture_binario()
    x2 = pd.concat([x, pd.Series([np.nan, np.nan, "a"])], ignore_index=True)
    y2 = pd.concat([y, pd.Series([0.0, 1.0, np.nan])], ignore_index=True)
    eng = _engine()
    cfg = eng.evaluate(
        x2, y2, predictor="x_nan", predictor_type=_NOMINAL, target_type=_BINARY
    )
    assert eng.diagnostics.n_rows_dropped_nan == 3
    # resultado identico al limpio
    clean = _engine().evaluate(
        x, y, predictor="x_nan", predictor_type=_NOMINAL, target_type=_BINARY
    )
    assert cfg is not None and clean is not None
    assert cfg.branches == clean.branches
    assert cfg.statistic == clean.statistic


def test_borde_c1_predictor_constante():
    eng = _engine()
    cfg = eng.evaluate(
        pd.Series(["z"] * 50), pd.Series([0] * 25 + [1] * 25),
        predictor="const", predictor_type=_NOMINAL, target_type=_BINARY,
    )
    assert cfg is None
    assert eng.diagnostics.n_categories == 1
    assert eng.diagnostics.n_final_groups == 1


def test_borde_k1_target_constante():
    eng = _engine()
    cfg = eng.evaluate(
        pd.Series(["a", "b", "a", "b"]), pd.Series([1, 1, 1, 1]),
        predictor="yk1", predictor_type=_NOMINAL, target_type=_BINARY,
    )
    assert cfg is None


def test_borde_n_insuficiente():
    eng = _engine()
    cfg = eng.evaluate(
        pd.Series(["a", "a", "b"]), pd.Series([0, 1, 1]),
        predictor="nsmall", predictor_type=_NOMINAL, target_type=_BINARY,
    )
    assert cfg is None  # N=3 < 2*K=4


def test_borde_r1_sin_asociacion():
    # tres categorias identicas -> todo par con p=1 -> fusion total -> r=1
    x = pd.Series(["a"] * 10 + ["b"] * 10 + ["c"] * 10)
    y = pd.Series(([1] * 5 + [0] * 5) * 3)
    eng = _engine()
    cfg = eng.evaluate(
        x, y, predictor="plano", predictor_type=_NOMINAL, target_type=_BINARY
    )
    assert cfg is None
    assert eng.diagnostics.n_final_groups == 1


def test_borde_padj_supera_alpha_split():
    # a=[20,10] b=[22,8] c=[10,14]: fusion a-b, luego p_adj = 3*p = 0.0189
    x = pd.Series(["a"] * 30 + ["b"] * 30 + ["c"] * 24)
    y = pd.Series(
        [0] * 20 + [1] * 10 + [0] * 22 + [1] * 8 + [0] * 10 + [1] * 14
    )
    strict = _engine(alpha_split=0.01)
    assert strict.evaluate(
        x, y, predictor="x_umbral", predictor_type=_NOMINAL, target_type=_BINARY
    ) is None
    assert strict.diagnostics.n_final_groups == 2  # la fusion si ocurrio
    lax = _engine()  # alpha_split = 0.05
    assert lax.evaluate(
        x, y, predictor="x_umbral", predictor_type=_NOMINAL, target_type=_BINARY
    ) is not None


def test_borde_continuo_separacion_perfecta():
    # categorias internamente constantes -> SSW=0, SSB>0 -> F infinito -> None
    eng = _engine()
    cfg = eng.evaluate(
        pd.Series(["a"] * 2 + ["b"] * 2 + ["c"] * 2),
        pd.Series([1.0, 1.0, 2.0, 2.0, 3.0, 3.0]),
        predictor="perf", predictor_type=_NOMINAL, target_type=_CONTINUOUS,
    )
    assert cfg is None
    assert eng.diagnostics.n_final_groups == 3


def test_borde_continuo_sin_senal():
    # todas las observaciones iguales -> F = 0, p = 1 -> None
    eng = _engine()
    cfg = eng.evaluate(
        pd.Series(["a"] * 4 + ["b"] * 4),
        pd.Series([7.0] * 8),
        predictor="plano_c", predictor_type=_NOMINAL, target_type=_CONTINUOUS,
    )
    assert cfg is None


# ---------------------------------------------------------------------------
# 8. Coherencia exhaustiva con SplitConfig (types.py)
# ---------------------------------------------------------------------------


def test_coherencia_splitconfig():
    x, y = _fixture_binario()
    cfg = _engine().evaluate(
        x, y, predictor="x_bin", predictor_type=_NOMINAL, target_type=_BINARY
    )
    assert isinstance(cfg, SplitConfig)
    assert cfg.method == "CHAID"
    assert cfg.statistic_name == "chi2"
    assert cfg.threshold is None
    assert cfg.impurity_gain is None
    assert cfg.p_value is not None and 0.0 <= cfg.p_value <= 1.0
    assert cfg.p_value_adjusted >= cfg.p_value
    assert cfg.bonferroni_multiplier >= 1
    assert cfg.n_merges >= 0
    # branches: particion real (disjuntas, cubren todas las categorias)
    flat = [v for g in cfg.branches for v in g]
    assert sorted(flat) == ["a", "b", "c"]
    assert len(set(flat)) == len(flat)
    # tamanios
    assert sum(cfg.child_ns) == cfg.parent_n
    assert len(cfg.child_ns) == len(cfg.branches)
    # exhaustive reporta el method correcto
    cfg_exh = _engine(exhaustive=True).evaluate(
        x, y, predictor="x_bin", predictor_type=_NOMINAL, target_type=_BINARY
    )
    assert cfg_exh is not None and cfg_exh.method == "CHAID_EXHAUSTIVE"


# ---------------------------------------------------------------------------
# 9. best_split: seleccion determinista por p_adj
# ---------------------------------------------------------------------------


def test_best_split():
    x, y = _fixture_binario()
    # predictor debil alineado con y neutral: u=v=[25,25] -> chi2=0, r=1 -> None
    debil = pd.Series(["u"] * 50 + ["v"] * 50)
    y_neutral = pd.Series([0] * 25 + [1] * 25 + [0] * 25 + [1] * 25)
    X = pd.DataFrame({"fuerte": x, "debil": debil})
    assert len(X) == len(y) == 100
    eng = _engine()
    best = eng.best_split(
        X, y, {"fuerte": _NOMINAL, "debil": _NOMINAL}, target_type=_BINARY
    )
    assert best is not None
    assert best.predictor == "fuerte"  # p_adj mucho menor que el del debil
    # ningun predictor valido -> None
    assert _engine().best_split(
        pd.DataFrame({"debil": debil}), y_neutral, {"debil": _NOMINAL},
        target_type=_BINARY,
    ) is None


# ---------------------------------------------------------------------------
# 10. Guardas de entrada
# ---------------------------------------------------------------------------


def test_guards():
    eng = _engine()
    _assert_raises(
        ValueError, eng.evaluate,
        pd.Series([1, 2, 3, 4]), pd.Series([0, 1, 0, 1]),
        predictor="pc", predictor_type=PredictorType.CONTINUOUS,
        target_type=_BINARY,
    )
    _assert_raises(
        ValueError, eng.evaluate,
        pd.Series(["a", "b"]), pd.Series([0, 1, 0]),
        predictor="len", predictor_type=_NOMINAL, target_type=_BINARY,
    )
    _assert_raises(ValueError, ChaidEngine, alpha_merge=0.0)
    _assert_raises(ValueError, ChaidEngine, alpha_split=1.0)
    _assert_raises(TypeError, ChaidEngine, exhaustive=1)
    _assert_raises(
        ValueError, eng.evaluate,
        pd.Series([["x"], ["y"], ["x"], ["y"]]), pd.Series([0, 1, 0, 1]),
        predictor="nohash", predictor_type=_NOMINAL, target_type=_BINARY,
    )


# ---------------------------------------------------------------------------
# 11. Humo de rendimiento: N = 200k (objetivo global del paso: <1.5 s @1M)
# ---------------------------------------------------------------------------


def test_humo_n200k():
    rng = np.random.default_rng(42)
    n = 200_000
    cats = np.array([f"cat{i:02d}" for i in range(10)], dtype=object)
    rates = np.array(
        [0.02, 0.03, 0.05, 0.08, 0.12, 0.18, 0.25, 0.33, 0.42, 0.50]
    )
    idx = rng.integers(0, 10, n)
    x = pd.Series(cats[idx])
    y = pd.Series((rng.random(n) < rates[idx]).astype(np.int8))
    eng = _engine()
    t0 = time.perf_counter()
    cfg = eng.evaluate(
        x, y, predictor="humo", predictor_type=_NOMINAL, target_type=_BINARY
    )
    dt = time.perf_counter() - t0
    assert cfg is not None
    assert isinstance(cfg, SplitConfig)
    assert cfg.parent_n == n
    assert sum(cfg.child_ns) == n
    assert dt < 10.0, f"humo 200k demasiado lento: {dt:.2f}s"
    print(f"[humo] N=200k, c=10 -> {dt:.3f}s, r={len(cfg.branches)}, "
          f"p_adj={cfg.p_value_adjusted:.3g}")


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
