"""Tests de backend_v3/validation.py (Fase 1.2). Dual: pytest o python directo.

Valores de referencia verificados a mano (replicacion identica de filas no
altera AUC/KS/PR-AUC/Brier y escala HL exactamente por el factor de copias):

  - AUC puros: p=[0.1..0.5], y=[0,0,0,1,1] x4 -> AUC=1, Gini=1. ROC:
    (0,0,+inf) inicial, (1,1,-inf) final, existe punto (fpr=0, tpr=1).
  - AUC empate: p=[0.2,0.2,0.4], y=[0,1,1] x5 -> AUC=0.75, Gini=0.5.
  - KS: p=[0.1,0.2 | y=0, 0.3,0.4,0.5 | y=1] x4 -> KS = 2/3 (umbral 0.3).
  - HL: p=[0.1..0.9], y=[0,0,0,0,0,1,1,1] x5, G=4 -> H = 5 * 1.980607...
        = 9.9030357, df=2, p = chi2.sf(H, 2) = exp(-H/2).
  - Brier: mismo par x2 -> BS=0.1, BS_ref=0.234375, BSS=0.573333.
  - PR-AUC: y=[0,1,0,1,1], p=[0.1..0.5] x3 -> AP = 1/3+1/3+1/4 = 11/12.

Regla Cochran-5 (OBS 5): n_groups * 5 <= N -> las fixtures se replican.
"""

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2 as _chi2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_v3.validation import (  # noqa: E402
    compute_oos_metrics,
    predict_pd,
)
from backend_v3.crt_engine import CrtEngine  # noqa: E402
from backend_v3.tree_builder import TreeBuilder  # noqa: E402
from backend_v3.types import PredictorType, TargetType  # noqa: E402


def _assert_raises(exc_type, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc_type:
        return
    except Exception as e:
        raise AssertionError(
            f"{fn.__name__} lanzo {type(e).__name__} en vez de {exc_type.__name__}: {e}"
        ) from e
    raise AssertionError(f"{fn.__name__} no lanzo {exc_type.__name__}")


def _rep(p, y, k):
    return np.tile(np.asarray(p, dtype=float), k), np.tile(np.asarray(y), k)


# ---------------------------------------------------------------------------
# metricas base (valores exactos)
# ---------------------------------------------------------------------------


def test_auc_gini_puros_y_roc():
    p, y = _rep([0.1, 0.2, 0.3, 0.4, 0.5], [0, 0, 0, 1, 1], 4)
    m = compute_oos_metrics(p, y, n_groups=4)
    assert m.auc == 1.0 and m.gini == 1.0
    assert m.roc_points[0] == (0.0, 0.0, math.inf)
    assert m.roc_points[-1][:2] == (1.0, 1.0)
    assert any(fpr == 0.0 and tpr == 1.0 for fpr, tpr, _ in m.roc_points)


def test_auc_empate_midrank():
    p, y = _rep([0.2, 0.2, 0.4], [0, 1, 1], 5)
    m = compute_oos_metrics(p, y, n_groups=3)
    assert math.isclose(m.auc, 0.75, rel_tol=1e-12)
    assert math.isclose(m.gini, 0.5, rel_tol=1e-12)


def test_ks_manual():
    # y = [0,0,1,0,1] (un evento en el medio): orden desc por score ->
    # F_bad=[1/2,1/2,1,1,1], F_good=[0,1/3,1/3,2/3,1]; max diff = 2/3 (p=0.3)
    p, y = _rep([0.1, 0.2, 0.3, 0.4, 0.5], [0, 0, 1, 0, 1], 4)
    m = compute_oos_metrics(p, y, n_groups=3)
    assert math.isclose(m.ks, 2.0 / 3.0, rel_tol=1e-12)


def test_hosmer_lemeshow_manual():
    p, y = _rep([0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9],
                [0, 0, 0, 0, 0, 1, 1, 1], 5)
    m = compute_oos_metrics(p, y, n_groups=4)
    assert m.hl_groups == 4 and m.hl_df == 2
    # exacto racional: 2*(6/17) + 18/91 + 98/91 = 3064/1547 (por grupo original)
    # x5 por la replicacion identica -> 15320/1547
    h_esperado = 15320.0 / 1547.0
    assert math.isclose(m.hl_stat, h_esperado, rel_tol=1e-12)
    assert math.isclose(m.hl_p, math.exp(-h_esperado / 2.0), rel_tol=1e-9)


def test_brier_manual():
    p, y = _rep([0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9],
                [0, 0, 0, 0, 0, 1, 1, 1], 2)
    m = compute_oos_metrics(p, y, n_groups=3)
    assert math.isclose(m.brier, 0.1, rel_tol=1e-12)
    assert math.isclose(m.brier_ref, 0.234375, rel_tol=1e-12)
    assert math.isclose(m.brier_skill, 0.5733333333333, rel_tol=1e-9)


def test_pr_auc_manual():
    p, y = _rep([0.1, 0.2, 0.3, 0.4, 0.5], [0, 1, 0, 1, 1], 3)
    m = compute_oos_metrics(p, y, n_groups=3)
    assert math.isclose(m.pr_auc, 11.0 / 12.0, rel_tol=1e-12)


def test_monoclase_none_y_guards():
    y = np.array([1] * 24)
    p = np.tile(np.linspace(0.1, 0.9, 8), 3)
    m = compute_oos_metrics(p, y, n_groups=3)
    assert m.auc is None and m.gini is None and m.ks is None
    assert m.pr_auc is None
    assert math.isnan(m.brier_skill)  # BS_ref = 0
    _assert_raises(ValueError, compute_oos_metrics, p, y, n_groups=2)
    _assert_raises(ValueError, compute_oos_metrics, p, y, n_groups=5)


def test_predict_pd_y_fila_huerfana():
    x = pd.Series([float(i) for i in range(1, 11)])
    X = pd.DataFrame({"x": x})
    y = pd.Series([0] * 5 + [1] * 5)
    m = TreeBuilder(
        CrtEngine(), target_type=TargetType.BINARY, target_class=1,
        max_depth=4, min_child_size=2,
    ).build(X, y, {"x": PredictorType.CONTINUOUS})
    p = predict_pd(m, X)
    assert p.shape == (10,)
    assert p[0] < p[-1]
    assert math.isclose(p[0], 0.5 / 6.0, rel_tol=1e-12)
    # NaN en el predictor del split -> fila huerfana -> ValueError
    Xbad = pd.DataFrame({"x": [1.0, np.nan]})
    _assert_raises(ValueError, predict_pd, m, Xbad)


# ---------------------------------------------------------------------------
# ejecucion directa
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        obj for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nOK - {len(tests)} tests superados")
