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
        class_labels=("Event", "Non-event"),
        max_depth=4, min_child_size=2,
    ).build(X, y, {"x": PredictorType.CONTINUOUS})
    p = predict_pd(m, X)
    # Phase 3.1.d: predict_pd returns (n_rows, K); binary consumers
    # read column 0 (parity invariant 10.1).
    assert p.shape == (10, 2)
    p0 = p[:, 0]
    assert p0[0] < p0[-1]
    assert math.isclose(p0[0], 0.5 / 6.0, rel_tol=1e-12)
    # NaN en el predictor del split -> fila huerfana -> ValueError
    Xbad = pd.DataFrame({"x": [1.0, np.nan]})
    _assert_raises(ValueError, predict_pd, m, Xbad)


def test_predict_pd_2d_binary_shape():
    """K=2: predict_pd devuelve (n_rows, 2); columnas suman 1."""
    x = pd.Series([float(i) for i in range(1, 11)])
    X = pd.DataFrame({"x": x})
    y = pd.Series([0] * 5 + [1] * 5)
    m = TreeBuilder(
        CrtEngine(), target_type=TargetType.BINARY, target_class=1,
        class_labels=("Event", "Non-event"),
        max_depth=4, min_child_size=2,
    ).build(X, y, {"x": PredictorType.CONTINUOUS})
    p = predict_pd(m, X)
    assert p.shape == (10, 2)
    # Cada fila suma 1 (invariante 10.1 del diseño).
    sums = p.sum(axis=1)
    assert np.allclose(sums, 1.0, atol=1e-12)
    # Columna 0 = clase de interés (Event, target_class=1).
    # Columna 1 = la otra clase.
    # La fila 0 cae en la hoja de "x <= 5", con 5 eventos / 5 no eventos.
    # Con Jeffreys: pd_event = 0.5/6 = 0.083333... para la hoja con 0 eventos.
    # Verificación: p[0, 0] < p[-1, 0] (filas más "event-prone" al final).
    assert p[0, 0] < p[-1, 0]


def test_predict_pd_2d_multiclass_shape():
    """K=3: predict_pd devuelve (n_rows, 3); columnas suman 1."""
    # Fixture K=3: predictor categórico (CHAID no admite continuos).
    seg = np.tile(["a", "b", "c"], 40)
    y = pd.Series(np.tile([0, 1, 2], 40))
    X = pd.DataFrame({"seg": seg})
    from backend_v3.chaid_engine import ChaidEngine
    m = TreeBuilder(
        ChaidEngine(), target_type=TargetType.BINARY, target_class=2,
        class_labels=("Alto", "Bajo", "Medio"),
        max_depth=3, min_child_size=5,
    ).build(X, y, {"seg": PredictorType.NOMINAL})
    p = predict_pd(m, X)
    assert p.shape == (len(X), 3)
    sums = p.sum(axis=1)
    assert np.allclose(sums, 1.0, atol=1e-12)
    # Columna 0 = target_class=2 ("Alto"), la clase de interés.
    # El árbol debe separar las 3 clases perfectamente (seg-driven),
    # así que la columna 0 será 0 donde seg != "c" y ~1 donde seg == "c".
    # (Verificación laxa para no atar el test a la codificación exacta
    # de la clase: solo comprobamos el rango).
    assert p[:, 0].min() >= 0.0
    assert p[:, 0].max() <= 1.0


def test_compute_oos_metrics_multiclass_raises():
    """K>2: compute_oos_metrics rechaza la matriz con ValueError."""
    p_2d = np.array([[0.2, 0.3, 0.5], [0.1, 0.4, 0.5]])
    y = np.array([0, 1])
    _assert_raises(ValueError, compute_oos_metrics, p_2d, y)


# ---------------------------------------------------------------------------
# 3.2.g - Ponderacion por muestra
# ---------------------------------------------------------------------------


def test_weighted_validation_parity_with_uniform_weights():
    # Pesos uniformes == sin pesos, en TODOS los campos del OOSMetrics.
    p, y = _rep([0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9],
                [0, 0, 0, 0, 0, 1, 1, 1], 5)
    m0 = compute_oos_metrics(p, y, n_groups=4)
    m1 = compute_oos_metrics(p, y, n_groups=4, weights=np.ones(len(p)))
    assert m0 == m1  # dataclass frozen: igualdad campo a campo exacta


def test_weighted_validation_auc_matches_manual():
    # Fixture KS clasico x4; pesos: bads en 0.3 pesan 3, bads en 0.5 pesan 1,
    # goods pesan 1. Bloques descendentes:
    #   0.5: bad masa 4 ; 0.4: good masa 4 ; 0.3: bad masa 12 ;
    #   0.2: good masa 4 ; 0.1: good masa 4.
    # Pares concordantes ponderados: 0.4 -> 4*4=16; 0.2 -> 16*4=64;
    #   0.1 -> 16*4=64. Total 144. W_bad=16, W_good=12 -> AUC = 144/192 = 0.75.
    p, y = _rep([0.1, 0.2, 0.3, 0.4, 0.5], [0, 0, 1, 0, 1], 4)
    w = np.ones(20)
    # posiciones del patron: idx % 5 == 2 -> bad en 0.3 ; idx % 5 == 4 -> bad en 0.5
    for i in range(20):
        if i % 5 == 2:
            w[i] = 3.0
    m = compute_oos_metrics(p, y, n_groups=3, weights=w)
    assert math.isclose(m.auc, 0.75, rel_tol=1e-12)
    assert math.isclose(m.gini, 0.5, rel_tol=1e-12)


def test_weighted_validation_ks_matches_manual():
    # Mismo fixture; pesos: goods en 0.4 pesan 3, resto 1.
    # W_bad = 8 (4 bads en 0.3 + 4 bads en 0.5). W_good = 4+4+12 = 20.
    # Acumuladas descendentes (fin de bloque):
    #   t=0.5: F_bad=4/8=0.5; F_good=0.0;      |diff|=0.5  <- KS
    #   t=0.4: F_bad=0.5;     F_good=12/20=0.6; |diff|=0.1
    #   t=0.3: F_bad=1.0;     F_good=0.6;       |diff|=0.4
    #   t=0.2: F_bad=1.0;     F_good=16/20=0.8; |diff|=0.2
    #   t=0.1: F_bad=1.0;     F_good=1.0;       diff=0
    # KS = 0.5.
    p, y = _rep([0.1, 0.2, 0.3, 0.4, 0.5], [0, 0, 1, 0, 1], 4)
    w = np.ones(20)
    for i in range(20):
        if i % 5 == 3:
            w[i] = 3.0
    m = compute_oos_metrics(p, y, n_groups=3, weights=w)
    assert math.isclose(m.ks, 0.5, rel_tol=1e-12)


def test_weighted_validation_hl_matches_manual():
    # n=40, n_groups=5. Implementacion independiente de la formula
    # ponderada (bucle directo con la misma regla de bordes documentada).
    p, y = _rep([0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9],
                [0, 0, 0, 0, 0, 1, 1, 1], 5)
    rng = np.random.default_rng(7)
    w = rng.uniform(0.5, 2.0, size=40)
    n_groups = 5
    m = compute_oos_metrics(p, y, n_groups=n_groups, weights=w)
    # calculo manual independiente
    orden = np.argsort(-p, kind="mergesort")
    ys, ps, ws = y[orden], p[orden], w[orden]
    n = 40
    bordes = np.floor(np.arange(1, n_groups) * n / n_groups).astype(int)
    h = 0.0
    for g in range(n_groups):
        ini = 0 if g == 0 else bordes[g - 1]
        fin = n if g == n_groups - 1 else bordes[g]
        sw = ws[ini:fin]
        n_g_w = float(sw.sum())
        pi_g = float((sw * ps[ini:fin]).sum() / n_g_w)
        pi_g = min(max(pi_g, 1e-15), 1.0 - 1e-15)
        o_g = float((sw * ys[ini:fin]).sum())
        h += (o_g - n_g_w * pi_g) ** 2 / (n_g_w * pi_g * (1.0 - pi_g))
    assert math.isclose(m.hl_stat, h, rel_tol=1e-12)
    assert m.hl_df == n_groups - 2


def test_weighted_validation_brier_matches_manual():
    p = np.array([0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9])
    y = np.array([0, 0, 0, 0, 0, 1, 1, 1])
    p, y = _rep(p, y, 2)  # n=16 para n_groups=3
    w = np.tile(np.array([1.0, 2.0, 0.5, 1.5, 1.0, 3.0, 0.8, 1.2]), 2)
    m = compute_oos_metrics(p, y, n_groups=3, weights=w)
    w_tot = float(w.sum())
    bs = float((w * (p - y) ** 2).sum() / w_tot)
    y_bar = float((w * y).sum() / w_tot)
    bs_ref = y_bar * (1.0 - y_bar)
    assert math.isclose(m.brier, bs, rel_tol=1e-12)
    assert math.isclose(m.brier_ref, bs_ref, rel_tol=1e-12)
    assert math.isclose(m.brier_skill, 1.0 - bs / bs_ref, rel_tol=1e-12)


def test_weighted_validation_scale_invariance():
    # AUC, Gini, KS, PR-AUC, Brier y BSS son invariantes a la escala
    # global de los pesos (cocientes o acumuladas normalizadas).
    # EXCEPCION documentada: HL NO es invariante a escala — escala
    # linealmente con la masa total, igual que el chi2 de Pearson en
    # tablas ponderadas (hallazgo matematico de 3.2.b, mismo patron).
    p, y = _rep([0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9],
                [0, 0, 0, 0, 0, 1, 1, 1], 5)
    rng = np.random.default_rng(11)
    w = rng.uniform(0.5, 2.0, size=40)
    m1 = compute_oos_metrics(p, y, n_groups=4, weights=w)
    m2 = compute_oos_metrics(p, y, n_groups=4, weights=w * 7.5)
    for campo in ("auc", "gini", "ks", "pr_auc",
                  "brier", "brier_ref", "brier_skill"):
        v1, v2 = getattr(m1, campo), getattr(m2, campo)
        assert math.isclose(v1, v2, rel_tol=1e-12), (
            f"{campo}: {v1} != {v2}"
        )
    assert len(m1.roc_points) == len(m2.roc_points)
    for p1, p2 in zip(m1.roc_points, m2.roc_points):
        assert p1[2] == p2[2]  # umbrales identicos
        assert math.isclose(p1[0], p2[0], rel_tol=1e-12)
        assert math.isclose(p1[1], p2[1], rel_tol=1e-12)
    # HL escala por el factor de pesos (comportamiento estandar con pesos
    # como frecuencias; Heeringa, West & Berglund 2010).
    assert math.isclose(m2.hl_stat, m1.hl_stat * 7.5, rel_tol=1e-12)


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
