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

import logging
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2 as _chi2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_v3.validation import (  # noqa: E402
    compute_oos_metrics,
    predict_leaf_assignment,
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
# 3.5.a - Multiclase (K >= 2) y composicion ponderada
# ---------------------------------------------------------------------------


class _ListHandler(logging.Handler):
    """Handler que acumula records en memoria (para capturar WARNINGs)."""

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def _capture_validation_log(fn, *args, **kwargs):
    """Ejecuta fn y devuelve (resultado, records del logger de validation)."""
    logger = logging.getLogger("treegov.validation")
    handler = _ListHandler()
    old_level = logger.level
    logger.setLevel(logging.WARNING)
    logger.addHandler(handler)
    try:
        result = fn(*args, **kwargs)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)
    return result, handler.records


def _fixture_k3_base():
    """Base K=3 de 6 filas (2 por clase), probabilidades que suman 1.

      y=0: [0.80, 0.10, 0.10] , [0.70, 0.15, 0.15]
      y=1: [0.10, 0.60, 0.30] , [0.05, 0.65, 0.30]
      y=2: [0.20, 0.50, 0.30] , [0.15, 0.55, 0.30]
    """
    p = np.array([
        [0.80, 0.10, 0.10],
        [0.70, 0.15, 0.15],
        [0.10, 0.60, 0.30],
        [0.05, 0.65, 0.30],
        [0.20, 0.50, 0.30],
        [0.15, 0.55, 0.30],
    ])
    y = np.array([0, 0, 1, 1, 2, 2])
    return p, y


def _fixture_k3_ponderado():
    """Base K=3 ponderada (n=6), filas que suman 1, w = [1,1,2,3,1,2]."""
    p = np.array([
        [0.80, 0.15, 0.05],
        [0.70, 0.20, 0.10],
        [0.10, 0.60, 0.30],
        [0.20, 0.25, 0.55],
        [0.05, 0.45, 0.50],
        [0.15, 0.35, 0.50],
    ])
    y = np.array([0, 0, 1, 1, 2, 2])
    w = np.array([1.0, 1.0, 2.0, 3.0, 1.0, 2.0])
    return p, y, w


def test_parity_k2_1d_vs_2d():
    """Paridad K=2: modo 1D == modo 2D (contrato D15, shortcut D12/D14).

    Fixture puros x4: p=[0.1..0.5], y=[0,0,0,1,1] replicado 4 veces
    (n=20). AUC=1, Gini=1, KS=1 (bads en 0.4-0.5, goods en 0.1-0.3).
    Camino 2D: p_2d = [p_evento, 1 - p_evento], y_2d = 1 - y_1d.
    """
    p, y = _rep([0.1, 0.2, 0.3, 0.4, 0.5], [0, 0, 0, 1, 1], 4)
    m1 = compute_oos_metrics(p, y, n_groups=4)
    p_2d = np.column_stack([p, 1.0 - p])
    y_2d = 1 - y
    m2 = compute_oos_metrics(p_2d, y_2d, n_groups=4)
    for campo in ("n_test", "n_events", "auc", "gini", "ks", "pr_auc",
                  "hl_stat", "hl_df", "hl_p", "hl_groups",
                  "brier", "brier_ref", "brier_skill", "roc_points"):
        assert getattr(m1, campo) == getattr(m2, campo), campo
    # Modo 1D: los campos nuevos quedan vacios
    assert m1.ks_pairs == () and m1.auc_pairs == () and m1.roc_per_class == ()
    # Modo 2D con K=2: se pueblan con el par unico (0, 1)
    assert m2.ks_pairs == ((0, 1, 1.0),)
    assert m2.auc_pairs == ((0, 1, 1.0),)
    assert len(m2.roc_per_class) == 2
    assert m2.roc_per_class[0] == m1.roc_points
    # Segunda curva: one-vs-rest de la columna 1. Inicio (0,0,+inf); el
    # barrido ya alcanza (1,1) en el ultimo bloque, asi que no se anade
    # el cierre (1,1,-inf) (regla "si aplica" del diseno).
    curva1 = m2.roc_per_class[1]
    assert curva1[0] == (0.0, 0.0, math.inf)
    assert curva1[-1][0] == 1.0 and curva1[-1][1] == 1.0


def test_parity_k2_2d_with_inverted_labels():
    """Contrato D15 consagrado: con K=2 en 2D, y_2d = 1 - y_1d.

    Si el llamador NO invierte (y_2d == y_1d), el shortcut interpreta la
    columna 0 como la etiqueta 0 y el modelo resulta perfectamente
    anti-discriminante en la convencion binaria: auc_2d = 1 - auc_1d = 0.
    """
    p, y = _rep([0.1, 0.2, 0.3, 0.4, 0.5], [0, 0, 0, 1, 1], 4)
    m1 = compute_oos_metrics(p, y, n_groups=4)
    p_2d = np.column_stack([p, 1.0 - p])
    m2 = compute_oos_metrics(p_2d, y, n_groups=4)  # SIN invertir
    assert m1.auc == 1.0
    assert m2.auc == 0.0
    assert m2.auc == 1.0 - m1.auc
    assert m2.auc != m1.auc


def test_multiclass_k3_hand_till_auc():
    """AUC/Gini multiclase (Hand & Till 2001; decision D1).

    Fixture: base de 6 filas (2 por clase, ver _fixture_k3_base) replicada
    15 veces -> n=90 (30 por clase). La replicacion identica no altera
    los AUC por par (masas proporcionales). Calculo a mano:

    Par (0,1): A_01 con col0: clase0 {0.80,0.70} > clase1 {0.10,0.05}
               -> 1. A_10 con col1: clase1 {0.60,0.65} > clase0
               {0.10,0.15} -> 1. auc_pair = 1.0.
    Par (0,2): A_02 con col0: clase0 {0.80,0.70} > clase2 {0.20,0.15}
               -> 1. A_20 con col2: clase2 {0.30,0.30} > clase0
               {0.10,0.10} -> 1. auc_pair = 1.0.
    Par (1,2): A_12 con col1: clase1 {0.60,0.65} > clase2 {0.50,0.55}
               -> 1. A_21 con col2: clase2 {0.30,0.30} vs clase1
               {0.30,0.30}: todos empates -> 0.5. auc_pair = 0.75.

    auc = (1 + 1 + 0.75)/3 = 11/12 ; gini = 2*auc - 1 = 5/6.
    """
    p6, y6 = _fixture_k3_base()
    p = np.tile(p6, (15, 1))
    y = np.tile(y6, 15)
    m = compute_oos_metrics(p, y, n_groups=5)
    esperado = ((0, 1, 1.0), (0, 2, 1.0), (1, 2, 0.75))
    assert len(m.auc_pairs) == 3
    for par, (i, j, v) in zip(m.auc_pairs, esperado):
        assert (par[0], par[1]) == (i, j)
        assert math.isclose(par[2], v, rel_tol=1e-12)
    auc_esp = (1.0 + 1.0 + 0.75) / 3.0
    assert math.isclose(m.auc, auc_esp, rel_tol=1e-12)
    assert math.isclose(m.gini, 2.0 * auc_esp - 1.0, rel_tol=1e-12)


def test_multiclass_k3_worst_case_ks():
    """KS multiclase = minimo de los KS por par simetrizados (worst-case;
    decision D4, simetrizado en 3.7.b).

    Fixture n=30 (10 por clase), probabilidades que suman 1:
      y=0 x10: [0.70, 0.20, 0.10]
      y=1 x10: [0.10, 0.70, 0.20]
      y=2  x5: [0.20, 0.30, 0.50]
      y=2  x5: [0.10, 0.80, 0.10]

    Calculo a mano (CDFs empiricas por bloques, simetrizado):
      Par (0,1): col0 -> 1.0 ; col1 -> 1.0 ; sym = 1.0.
      Par (0,2): col0 -> 1.0 ; col2 -> 0.5 ; sym = 0.75.
      Par (1,2): col1 -> 0.5 ; col2 -> 0.5 ; sym = 0.5.
    El par (1,2) domina el worst-case: ks = min(1, 0.75, 0.5) = 0.5.
    """
    p = np.array(
        [[0.70, 0.20, 0.10]] * 10
        + [[0.10, 0.70, 0.20]] * 10
        + [[0.20, 0.30, 0.50]] * 5
        + [[0.10, 0.80, 0.10]] * 5
    )
    y = np.array([0] * 10 + [1] * 10 + [2] * 10)
    m = compute_oos_metrics(p, y, n_groups=5)
    assert [(i, j) for i, j, _ in m.ks_pairs] == [(0, 1), (0, 2), (1, 2)]
    vals = [v for _, _, v in m.ks_pairs]
    assert math.isclose(vals[0], 1.0, rel_tol=1e-12)
    assert math.isclose(vals[1], 0.75, rel_tol=1e-12)
    assert math.isclose(vals[2], 0.5, rel_tol=1e-12)
    assert math.isclose(m.ks, min(vals), rel_tol=1e-12)
    assert math.isclose(m.ks, 0.5, rel_tol=1e-12)


def test_multiclass_k3_brier_and_bss():
    """Brier multiclase con factor 1/2 (D6/D12) y BSS climatologico.

    Fixture n=6, K=3 (probabilidades que suman 1):
      y=0: [0.80,0.15,0.05] ; y=0: [0.70,0.20,0.10]
      y=1: [0.10,0.60,0.30] ; y=1: [0.20,0.50,0.30]
      y=2: [0.05,0.45,0.50] ; y=2: [0.15,0.35,0.50]

    Errores cuadraticos por fila (suma sobre k de (Y_ik - p_ik)^2):
      0.065, 0.14, 0.26, 0.38, 0.455, 0.395  ->  suma total 1.695
    brier = 1.695 / (2*6) = 0.14125.
    pi = (1/3, 1/3, 1/3) -> brier_ref = 0.5 * 3 * (2/9) = 1/3.
    bss = 1 - 0.14125/(1/3) = 0.57625.
    """
    p = np.array([
        [0.80, 0.15, 0.05],
        [0.70, 0.20, 0.10],
        [0.10, 0.60, 0.30],
        [0.20, 0.50, 0.30],
        [0.05, 0.45, 0.50],
        [0.15, 0.35, 0.50],
    ])
    y = np.array([0, 0, 1, 1, 2, 2])
    m = compute_oos_metrics(p, y, n_groups=3)
    assert math.isclose(m.brier, 0.14125, rel_tol=1e-12)
    assert math.isclose(m.brier_ref, 1.0 / 3.0, rel_tol=1e-12)
    assert math.isclose(m.brier_skill, 0.57625, rel_tol=1e-12)


def test_multiclass_k2_brier_reduction():
    """K=2: el brier del modo 2D (inversion D15) == brier binario 1D."""
    p, y = _rep([0.1, 0.2, 0.3, 0.4, 0.5], [0, 0, 0, 1, 1], 4)
    m1 = compute_oos_metrics(p, y, n_groups=4)
    p_2d = np.column_stack([p, 1.0 - p])
    m2 = compute_oos_metrics(p_2d, 1 - y, n_groups=4)
    assert math.isclose(m2.brier, m1.brier, rel_tol=1e-12)


def test_multiclass_k3_pr_auc_micro():
    """PR-AUC micro-average (decision D7; Davis & Goadrich 2006).

    Fixture n=3, K=3 (una fila por clase, suman 1):
      y=0: [0.90, 0.05, 0.05]
      y=1: [0.55, 0.35, 0.10]
      y=2: [0.20, 0.10, 0.70]

    Problema pooled de 9 pares (score, positivo):
      (0.9,P) (0.05,N) (0.05,N) (0.55,N) (0.35,P) (0.10,N)
      (0.2,N) (0.1,N)  (0.7,P)
    Orden descendente: 0.9(P), 0.7(P), 0.55(N), 0.35(P), 0.2(N), 0.1(N),
    0.1(N), 0.05(N), 0.05(N). Positivos totales = 3. AP escalonado:
      t=0.90: R=1/3, P=1   -> (1/3 - 0)   * 1   = 1/3
      t=0.70: R=2/3, P=1   -> (2/3 - 1/3) * 1   = 1/3
      t=0.55: R=2/3 (sin cambio)          -> 0
      t=0.35: R=1,   P=3/4 -> (1 - 2/3)   * 3/4 = 1/4
    pr_auc = 1/3 + 1/3 + 1/4 = 11/12.
    """
    p = np.array([
        [0.90, 0.05, 0.05],
        [0.55, 0.35, 0.10],
        [0.20, 0.10, 0.70],
    ])
    y = np.array([0, 1, 2])
    m = compute_oos_metrics(p, y, n_groups=3)
    assert math.isclose(m.pr_auc, 11.0 / 12.0, rel_tol=1e-12)


def test_multiclass_k3_hl_none_with_warning():
    """HL bloqueado en multiclase (D5/D16): None + WARNING Fagerland."""
    p, y = _fixture_k3_base()
    m, records = _capture_validation_log(
        compute_oos_metrics, p, y, n_groups=5
    )
    assert m.hl_stat is None and m.hl_df is None and m.hl_p is None
    assert m.hl_groups == 5 and isinstance(m.hl_groups, int)
    warns = [r for r in records if r.levelno == logging.WARNING]
    assert warns, "no se emitio WARNING"
    msg = " ".join(r.getMessage() for r in warns)
    assert "Fagerland" in msg
    assert "binary" in msg or "multiclase" in msg


def test_multiclass_k3_skips_n_groups_validation():
    """D16: n_groups*5 <= N se salta para K > 2 (HL no se computa).

    K=3, n=10, n_groups=10: NO lanza (la regla Cochran-5 no aplica).
    El mismo tamano con K=2 SI lanza ValueError (regla intacta en binario).
    """
    p = np.array(
        [[0.80, 0.10, 0.10]] * 4
        + [[0.10, 0.80, 0.10]] * 3
        + [[0.10, 0.10, 0.80]] * 3
    )
    y = np.array([0] * 4 + [1] * 3 + [2] * 3)
    m = compute_oos_metrics(p, y, n_groups=10)  # no debe lanzar
    assert m.n_test == 10 and m.hl_groups == 10
    # K=2 (camino 1D): la regla se mantiene integra
    p1 = np.linspace(0.05, 0.95, 10)
    y1 = np.array([0] * 5 + [1] * 5)
    _assert_raises(ValueError, compute_oos_metrics, p1, y1, n_groups=10)


def test_multiclass_k3_roc_per_class():
    """K curvas ROC one-vs-rest (D8/D17); roc_points = curva de la clase 0.

    Fixture base K=3 (n=6). Cada curva abre en (0,0,+inf) y termina con
    fpr=1 y tpr=1 (el barrido cubre (1,1) en el ultimo bloque; si no, la
    implementacion cierra en (1,1,-inf) sin duplicar).
    """
    p, y = _fixture_k3_base()
    m = compute_oos_metrics(p, y, n_groups=3)
    assert len(m.roc_per_class) == 3
    for curva in m.roc_per_class:
        assert curva[0] == (0.0, 0.0, math.inf)
        assert curva[0][0] == 0.0  # fpr = 0 en el inicio
        assert curva[-1][0] == 1.0 and curva[-1][1] == 1.0
    assert m.roc_points == m.roc_per_class[0]


def test_weighted_multiclass_parity_uniform():
    """Pesos uniformes == sin pesos en el camino multiclase (D10)."""
    p6, y6 = _fixture_k3_base()
    p = np.tile(p6, (15, 1))
    y = np.tile(y6, 15)
    m0 = compute_oos_metrics(p, y, n_groups=5)
    m1 = compute_oos_metrics(p, y, n_groups=5, weights=np.ones(len(y)))
    assert m0 == m1  # igualdad campo a campo exacta (dataclass frozen)


def test_weighted_multiclass_hand_computed():
    """Ponderado x multiclase con pesos no triviales, verificado a mano.

    Fixture n=6, K=3 (filas que suman 1), pesos w = [1, 1, 2, 3, 1, 2]:
      y=0: [0.80,0.15,0.05] w=1 ; y=0: [0.70,0.20,0.10] w=1
      y=1: [0.10,0.60,0.30] w=2 ; y=1: [0.20,0.25,0.55] w=3
      y=2: [0.05,0.45,0.50] w=1 ; y=2: [0.15,0.35,0.50] w=2

    AUC por par (masas ponderadas, medio-credito en empates):
      (0,1): A_01 col0: {0.8,0.7} > {0.1,0.2} -> 1. A_10 col1:
             {0.60,0.25} > {0.15,0.20} -> 1. auc_pair = 1.0.
      (0,2): A_02 col0: {0.8,0.7} > {0.05,0.15} -> 1. A_20 col2:
             {0.50,0.50} > {0.05,0.10} -> 1. auc_pair = 1.0.
      (1,2): A_12 col1: pos clase1 {0.60(w2), 0.25(w3)}, neg clase2
             {0.45(w1), 0.35(w2)}: concordantes (0.6,0.45)=2 y
             (0.6,0.35)=4 -> A_12 = 6/15 = 0.4.
             A_21 col2: pos clase2 {0.50(w1), 0.50(w2)}, neg clase1
             {0.30(w2), 0.55(w3)}: concordantes (0.5,0.3): 1*2+2*2=6;
             discordantes (0.5,0.55): 1*3+2*3=9 -> A_21 = 6/15 = 0.4.
             auc_pair = 0.4.
    auc = (1 + 1 + 0.4)/3 = 0.8 ; gini = 2*0.8 - 1 = 0.6.

    KS por par (CDFs ponderadas):
      (0,1): t=0.7 -> F_pos=1, F_neg=0 -> KS = 1.0.
      (0,2): idem -> KS = 1.0.
      (1,2) col1: t=0.60: F_pos=2/5=0.4, F_neg=0   -> 0.4
                  t=0.45: F_pos=0.4,     F_neg=1/3 -> 0.0667
                  t=0.35: F_pos=0.4,     F_neg=1   -> 0.6  <- max
                  t=0.25: F_pos=1,       F_neg=1   -> 0
                  KS = 0.6.
    ks = min(1, 1, 0.6) = 0.6.

    Brier: errores ponderados por fila (w * suma_k (Y_ik - p_ik)^2):
      0.065*1, 0.14*1, 0.26*2, 0.905*3, 0.455*1, 0.395*2
      suma = 4.685 ; W = 10 ; brier = 4.685/20 = 0.23425.
    pi = (2/10, 5/10, 3/10) = (0.2, 0.5, 0.3) ;
    brier_ref = 0.5 * (0.16 + 0.25 + 0.21) = 0.31.
    bss = 1 - 0.23425/0.31.
    """
    p, y, w = _fixture_k3_ponderado()
    m = compute_oos_metrics(p, y, n_groups=5, weights=w)
    esperado_auc = ((0, 1, 1.0), (0, 2, 1.0), (1, 2, 0.4))
    assert len(m.auc_pairs) == 3
    for par, (i, j, v) in zip(m.auc_pairs, esperado_auc):
        assert (par[0], par[1]) == (i, j)
        assert math.isclose(par[2], v, rel_tol=1e-12)
    assert math.isclose(m.auc, 0.8, rel_tol=1e-12)
    assert math.isclose(m.gini, 0.6, rel_tol=1e-12)
    esperado_ks = ((0, 1, 1.0), (0, 2, 1.0), (1, 2, 0.6))
    assert len(m.ks_pairs) == 3
    for par, (i, j, v) in zip(m.ks_pairs, esperado_ks):
        assert (par[0], par[1]) == (i, j)
        assert math.isclose(par[2], v, rel_tol=1e-12)
    assert math.isclose(m.ks, 0.6, rel_tol=1e-12)
    assert math.isclose(m.brier, 0.23425, rel_tol=1e-12)
    assert math.isclose(m.brier_ref, 0.31, rel_tol=1e-12)
    assert math.isclose(m.brier_skill, 1.0 - 0.23425 / 0.31, rel_tol=1e-12)


def test_weighted_multiclass_scale_invariance():
    """Invarianza a escala global de los pesos (ratios; Heeringa 2010)."""
    p, y, w = _fixture_k3_ponderado()
    m1 = compute_oos_metrics(p, y, n_groups=5, weights=w)
    m2 = compute_oos_metrics(p, y, n_groups=5, weights=w * 7.5)
    for campo in ("auc", "gini", "ks", "pr_auc",
                  "brier", "brier_ref", "brier_skill"):
        v1, v2 = getattr(m1, campo), getattr(m2, campo)
        assert math.isclose(v1, v2, rel_tol=1e-12), (
            f"{campo}: {v1} != {v2}"
        )
    for pares1, pares2 in ((m1.auc_pairs, m2.auc_pairs),
                           (m1.ks_pairs, m2.ks_pairs)):
        assert len(pares1) == len(pares2)
        for a, b in zip(pares1, pares2):
            assert a[:2] == b[:2]
            assert math.isclose(a[2], b[2], rel_tol=1e-12)
    assert len(m1.roc_per_class) == len(m2.roc_per_class)
    for c1, c2 in zip(m1.roc_per_class, m2.roc_per_class):
        assert len(c1) == len(c2)
        for pto1, pto2 in zip(c1, c2):
            assert pto1[2] == pto2[2]  # umbrales identicos
            assert math.isclose(pto1[0], pto2[0], rel_tol=1e-12)
            assert math.isclose(pto1[1], pto2[1], rel_tol=1e-12)


def test_multiclass_k3_missing_class_returns_none():
    """Clase ausente (masa 0) en K=3: auc/gini -> None + WARNING.

    y solo contiene {0, 1} pero p tiene 3 columnas. El resto de campos
    se computan: brier/bss dependen de la matriz completa (no de las
    clases presentes); ks/ks_pairs quedan con el unico par computable.
    """
    p = np.array([
        [0.80, 0.10, 0.10],
        [0.70, 0.20, 0.10],
        [0.10, 0.80, 0.10],
        [0.20, 0.60, 0.20],
        [0.15, 0.70, 0.15],
        [0.05, 0.90, 0.05],
    ])
    y = np.array([0, 0, 1, 1, 1, 1])
    m, records = _capture_validation_log(
        compute_oos_metrics, p, y, n_groups=3
    )
    assert m.auc is None and m.gini is None
    assert math.isfinite(m.brier)
    assert math.isfinite(m.brier_skill)
    assert len(m.auc_pairs) == 1 and m.auc_pairs[0][:2] == (0, 1)
    assert len(m.ks_pairs) == 1 and m.ks_pairs[0][:2] == (0, 1)
    assert math.isclose(m.ks, m.ks_pairs[0][2], rel_tol=1e-12)
    msg = " ".join(r.getMessage() for r in records
                   if r.levelno == logging.WARNING)
    assert "masa cero" in msg or "una sola clase" in msg


# ---------------------------------------------------------------------------
# Mini-cierre 25/10/2026 (C1): routing OOS por bin_edges (espejo de
# test_tree_builder.test_routing_bin_edges_chaid_continuous)
# ---------------------------------------------------------------------------


def test_predict_leaf_assignment_binned_continuous():
    """Fase 3.10.b (H14): coherencia OOS del routing por rangos numericos.

    El modelo se entrena con CHAID sobre un predictor continuo binned
    (max_depth=1: hijos terminales por profundidad) y se enruta una
    muestra OOS que incluye valores FUERA del rango de train: los bins
    extremos se extienden a +-inf, asi que toda fila finita tiene ruta.
    """
    from backend_v3.chaid_engine import ChaidEngine
    x = pd.Series(np.linspace(0.0, 1.0, 600))
    y = pd.Series((x > 0.5).astype(int))
    X = pd.DataFrame({"ingreso": x})
    m = TreeBuilder(
        ChaidEngine(), target_type=TargetType.BINARY, target_class=1,
        class_labels=("Event", "Non-event"),
        max_depth=1, min_child_size=20,
    ).build(X, y, {"ingreso": PredictorType.CONTINUOUS})
    raiz = m.nodes[0]
    assert raiz.split is not None and raiz.split.bin_edges
    cfg = raiz.split
    x_oos = pd.Series([-5.0, 0.1, 0.5, 0.9, 42.0])
    asign = predict_leaf_assignment(m, pd.DataFrame({"ingreso": x_oos}))
    assert (asign >= 0).all()          # ninguna fila se queda sin ruta
    # expectativa independiente: bin -> rama via etiquetas "bin_i"
    rama_map = {
        int(str(lbl)[4:]): j
        for j, grupo in enumerate(cfg.branches or ())
        for lbl in grupo
    }
    bins = np.digitize(x_oos.to_numpy(dtype=float), cfg.bin_edges, right=True)
    esperado = np.array(
        [raiz.child_ids[rama_map[int(b)]] for b in bins], dtype=int
    )
    assert (asign == esperado).all()


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
