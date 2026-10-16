"""Tests para backend_v3.reporting.build_oos_oot_report (Fase 2.3.d).

Verifican el contrato del DTO plano OOS/OOT sin invocar Session ni ejecutar
ninguna corrida real. Todas las estructuras se construyen a mano (valores
verificados, no autoreferencias).

Incluye además tests para build_gains_table y build_classification_matrix
sobre un fixture sintético de 3 hojas (PDs 0.1/0.3/0.6, 250 filas, 95 bads).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_v3.reporting import (  # noqa: E402
    _validated_routed,
    build_classification_matrix,
    build_classification_matrix_multiclass,
    build_gains_table,
    build_oos_oot_report,
)
from backend_v3.types import SplitConfig  # noqa: E402
from backend_v3.session_state import SessionState
from backend_v3.stability import (
    CSIReport,
    GiniDropReport,
    OOTReport,
    PSIReport,
)
from backend_v3.tree_builder import TreeModel, TreeNode
from backend_v3.validation import OOSMetrics


def _tree_stub() -> TreeModel:
    """Modelo mínimo válido: raíz hoja única (para el guard `st.tree is None`)."""
    leaf = TreeNode(
        node_id=0, depth=0, parent_id=None,
        n=100, n_events=(10, 90),
        pd_jeffreys=(0.104, 0.896), pd_final=(0.104, 0.896),
        class_labels=("Event", "Non-event"),
        is_leaf=True, split=None, child_ids=(),
        leaf_reason="sin_split",
    )
    return TreeModel(
        root_id=0, nodes=(leaf,), method="CRT",
        params_fingerprint="test0000000000",
        class_labels=("Event", "Non-event"),
        target_class=1,
        target_class_index=0,
    )


def _oos_stub() -> OOSMetrics:
    return OOSMetrics(
        n_test=300, n_events=30,
        auc=0.75, gini=0.50, ks=0.40, pr_auc=0.30,
        hl_stat=5.0, hl_df=8, hl_p=0.76, hl_groups=10,
        brier=0.10, brier_ref=0.09, brier_skill=-0.11,
        roc_points=((0.0, 0.0, float("inf")), (1.0, 1.0, float("-inf"))),
    )


def _oot_stub() -> OOTReport:
    drop = GiniDropReport(
        gini_train=0.50, gini_oos=0.48, gini_oot=0.45,
        drop_oos=0.04, drop_oot=0.10,
        alert_oos="NONE", alert_oot="NONE",
        temporal_verified=False,
    )
    psi = PSIReport(psi=0.05, flag="STABLE", per_bin=())
    csi = (CSIReport(predictor="x1", csi=0.03, flag="STABLE", per_bin=()),)
    return OOTReport(
        metrics=None, drop=drop, psi=psi, csi=csi,
        n_oot=200, n_excluded=0,
    )


def _leaf(node_id: int, pd: float, n_bad: int, n_good: int) -> TreeNode:
    """Hoja aislada con PD y conteos bad/good fijados a mano.

    Fase 3.1: n_events, pd_jeffreys y pd_final son tuples de K=2 en orden
    canónico (index 0 = clase de interés). Por convención del fixture,
    la clase de interés es la "bad" (n_bad), así que:
      n_events = (n_bad, n_good)
      pd_final = (pd, 1 - pd)
    """
    n = n_bad + n_good
    return TreeNode(
        node_id=node_id, depth=0, parent_id=None,
        n=n, n_events=(n_bad, n_good),
        pd_jeffreys=(pd, 1.0 - pd), pd_final=(pd, 1.0 - pd),
        class_labels=("Bad", "Good"),
        is_leaf=True, split=None, child_ids=(),
        leaf_reason="sin_split",
    )


def _model_3_leaves() -> SimpleNamespace:
    """Modelo simulado de 3 hojas con PDs crecientes: 0.1, 0.3 y 0.6.

    Fase 3.1: el mock incluye class_labels con K=2 (Bad, Good) porque
    build_gains_table comprueba len(model.class_labels) == 2 antes de
    procesar.
    """
    return SimpleNamespace(
        nodes=(
            _leaf(0, 0.1, n_bad=5, n_good=45),
            _leaf(1, 0.3, n_bad=30, n_good=70),
            _leaf(2, 0.6, n_bad=60, n_good=40),
        ),
        class_labels=("Bad", "Good"),
    )


def _standard_assign() -> np.ndarray:
    """Asignación de 250 filas: 50 a la hoja 0, 100 a la 1 y 100 a la 2."""
    return np.array([0] * 50 + [1] * 100 + [2] * 100)


def _standard_y() -> np.ndarray:
    """Target con 95 bads repartidos 5/30/60 entre las hojas 0/1/2."""
    y = np.zeros(250, dtype=int)
    y[0:5] = 1
    y[50:80] = 1
    y[150:210] = 1
    return y


def test_returns_none_when_no_tree() -> None:
    assert build_oos_oot_report(SessionState()) is None


def test_tree_only_returns_both_subkeys_none() -> None:
    st = SessionState(tree=_tree_stub())
    dto = build_oos_oot_report(st)
    assert dto is not None
    assert dto["oos"] is None
    assert dto["oot"] is None


def test_with_oos_only() -> None:
    st = SessionState(tree=_tree_stub(), oos_metrics=_oos_stub())
    dto = build_oos_oot_report(st)
    assert dto is not None
    assert dto["oos"] is not None
    assert dto["oos"]["n_test"] == 300
    assert dto["oos"]["gini"] == 0.50
    assert dto["oot"] is None


def test_with_oot_only() -> None:
    st = SessionState(tree=_tree_stub(), oot_report=_oot_stub())
    dto = build_oos_oot_report(st)
    assert dto is not None
    assert dto["oos"] is None
    assert dto["oot"] is not None
    assert dto["oot"]["n_oot"] == 200
    assert dto["oot"]["n_excluded_routing"] == 0


def test_with_all_filled() -> None:
    st = SessionState(
        tree=_tree_stub(),
        oos_metrics=_oos_stub(),
        oot_report=_oot_stub(),
    )
    dto = build_oos_oot_report(st)
    assert dto is not None
    assert dto["oos"] is not None
    assert dto["oot"] is not None


def test_asdict_is_recursive() -> None:
    """Verifica que los dataclasses anidados se propagan como dicts.

    Invariante crítico de 2.3.e: el frontend consumirá
    dto['oot']['drop']['alert_oot'], dto['oot']['psi']['flag'], etc.
    """
    st = SessionState(tree=_tree_stub(), oot_report=_oot_stub())
    dto = build_oos_oot_report(st)
    assert dto is not None
    oot = dto["oot"]
    assert isinstance(oot["drop"], dict)
    assert oot["drop"]["alert_oot"] == "NONE"
    assert isinstance(oot["psi"], dict)
    assert oot["psi"]["flag"] == "STABLE"
    assert isinstance(oot["csi"], tuple)
    assert oot["csi"][0]["predictor"] == "x1"
    assert oot["csi"][0]["flag"] == "STABLE"


def test_gains_table_by_leaf() -> None:
    """Gains por hoja: conteos, acumulados, desacumulados y métricas a mano.

    Fixture: 250 filas, 95 bads, 155 goods, bad_rate_global = 0.38.
    KS = 60/95 - 40/155 = 220/589; AUC = 10612.5/14725; Gini = 2*AUC - 1.
    """
    result = build_gains_table(_model_3_leaves(), _standard_assign(), _standard_y())
    assert result.by == "leaf"
    assert result.n_excluded == 0
    assert result.n_total == 250
    assert result.n_good == 155
    assert result.n_bad == 95
    assert result.bad_rate_global == pytest.approx(0.38, rel=1e-9)

    rows = result.rows
    assert len(rows) == 3
    assert [r.label for r in rows] == ["L0", "L1", "L2"]
    assert [r.pd for r in rows] == [0.1, 0.3, 0.6]

    r0 = rows[0]
    assert r0.n == 50
    assert r0.n_good == 45
    assert r0.n_bad == 5
    assert r0.bad_rate == pytest.approx(0.1, rel=1e-9)
    assert r0.n_cum == 50
    assert r0.n_bad_cum == 5
    assert r0.n_good_cum == 45
    assert r0.bad_rate_cum == pytest.approx(0.1, rel=1e-9)
    assert r0.lift_cum == pytest.approx(0.1 / 0.38, rel=1e-9)
    assert r0.n_decum == 250
    assert r0.n_bad_decum == 95
    assert r0.n_good_decum == 155
    assert r0.bad_rate_decum == pytest.approx(0.38, rel=1e-9)

    r1 = rows[1]
    assert r1.n == 100
    assert r1.n_good == 70
    assert r1.n_bad == 30
    assert r1.n_cum == 150
    assert r1.n_bad_cum == 35
    assert r1.n_good_cum == 115
    assert r1.bad_rate_cum == pytest.approx(35 / 150, rel=1e-9)
    assert r1.n_decum == 200
    assert r1.n_bad_decum == 90
    assert r1.n_good_decum == 110
    assert r1.bad_rate_decum == pytest.approx(0.45, rel=1e-9)

    r2 = rows[2]
    assert r2.n == 100
    assert r2.n_good == 40
    assert r2.n_bad == 60
    assert r2.n_cum == 250
    assert r2.n_bad_cum == 95
    assert r2.n_good_cum == 155
    assert r2.bad_rate_cum == pytest.approx(0.38, rel=1e-9)
    assert r2.n_decum == 100
    assert r2.n_bad_decum == 60
    assert r2.n_good_decum == 40
    assert r2.bad_rate_decum == pytest.approx(0.6, rel=1e-9)

    assert result.ks == pytest.approx(0.373514, abs=1e-6)
    assert result.auc == pytest.approx(0.720713, abs=1e-6)
    assert result.gini == pytest.approx(0.441426, abs=1e-6)


def test_gains_table_by_bucket_preserve() -> None:
    """Buckets con tie='preserve': la frontera no parte hojas (150/100)."""
    result = build_gains_table(
        _model_3_leaves(), _standard_assign(), _standard_y(),
        by="bucket", n_buckets=2, tie="preserve",
    )
    rows = result.rows
    assert len(rows) == 2
    assert [r.label for r in rows] == ["B01", "B02"]

    b1, b2 = rows
    assert b1.n == 150
    assert b1.n_bad == 35
    assert b1.n_good == 115
    assert b1.pd == pytest.approx(35 / 150, rel=1e-9)
    assert b2.n == 100
    assert b2.n_bad == 60
    assert b2.n_good == 40
    assert b2.pd == pytest.approx(0.6, rel=1e-9)

    assert result.n_total == 250
    assert result.n_excluded == 0


def test_gains_table_by_bucket_random_seed_reproducible() -> None:
    """tie='random' con seed=42: dos llamadas producen filas idénticas."""
    r1 = build_gains_table(
        _model_3_leaves(), _standard_assign(), _standard_y(),
        by="bucket", n_buckets=10, tie="random", seed=42,
    )
    r2 = build_gains_table(
        _model_3_leaves(), _standard_assign(), _standard_y(),
        by="bucket", n_buckets=10, tie="random", seed=42,
    )
    assert r1.rows == r2.rows
    assert len(r1.rows) == 10
    assert sum(row.n for row in r1.rows) == 250
    assert all(row.n == 25 for row in r1.rows)


def test_classification_matrix_thresholds() -> None:
    """Matriz de clasificación en umbrales 0.5 y 0.2; métricas a mano.

    threshold=0.5: solo la hoja 2 predice bad -> tp=60, fp=40, fn=35, tn=115.
    threshold=0.2: hojas 1 y 2 predicen bad -> tp=90, fp=110, fn=5, tn=45.
    """
    pd_per_leaf = {0: 0.1, 1: 0.3, 2: 0.6}
    assign = _standard_assign()
    y = _standard_y()

    m5 = build_classification_matrix(assign, y, pd_per_leaf, threshold=0.5)
    assert m5.tp == 60
    assert m5.tn == 115
    assert m5.fp == 40
    assert m5.fn == 35
    assert m5.n_total == 250
    assert m5.n_good == 155
    assert m5.n_bad == 95
    assert m5.n_excluded == 0
    assert m5.precision == pytest.approx(0.6, rel=1e-9)
    assert m5.recall == pytest.approx(60 / 95, rel=1e-9)
    assert m5.f1 == pytest.approx(0.615385, abs=1e-6)
    assert m5.bad_capture_rate == m5.recall

    m2 = build_classification_matrix(assign, y, pd_per_leaf, threshold=0.2)
    assert m2.tp == 90
    assert m2.tn == 45
    assert m2.fp == 110
    assert m2.fn == 5
    assert m2.precision == pytest.approx(0.45, rel=1e-9)
    assert m2.recall == pytest.approx(90 / 95, rel=1e-9)
    assert m2.f1 == pytest.approx(0.610169, abs=1e-6)
    assert m2.bad_capture_rate == m2.recall


def test_excluded_rows_are_not_counted() -> None:
    """Filas con assign negativo se excluyen del cómputo y se cuentan aparte.

    Se excluye la posición 0 (bad de la hoja 0) y la 100 (good de la hoja 1):
    quedan 248 filas, 94 bads y 154 goods, con las 3 hojas aún pobladas.
    """
    assign = _standard_assign()
    assign[0] = -1
    assign[100] = -1
    result = build_gains_table(_model_3_leaves(), assign, _standard_y())
    assert result.n_excluded == 2
    assert result.n_total == 248
    assert result.n_bad == 94
    assert result.n_good == 154
    assert len(result.rows) == 3


# ---------------------------------------------------------------------------
# 3.2.g - Ponderacion por muestra
# ---------------------------------------------------------------------------


def test_weighted_reporting_gains_w_star_equals_star_no_weights() -> None:
    """weights=None: columnas w_* exactamente iguales a las de conteo."""
    result = build_gains_table(_model_3_leaves(), _standard_assign(), _standard_y())
    for r in result.rows:
        assert r.w_n == float(r.n)
        assert r.w_good == float(r.n_good)
        assert r.w_bad == float(r.n_bad)
        assert r.w_bad_rate == r.bad_rate
        assert r.w_n_cum == float(r.n_cum)
        assert r.w_bad_cum == float(r.n_bad_cum)
        assert r.w_bad_rate_cum == r.bad_rate_cum
        assert r.w_lift_cum == r.lift_cum
        assert r.w_n_decum == float(r.n_decum)
        assert r.w_bad_decum == float(r.n_bad_decum)
        assert r.w_bad_rate_decum == r.bad_rate_decum
    assert result.w_total == float(result.n_total)
    assert result.w_bad == float(result.n_bad)
    assert result.w_bad_rate_global == result.bad_rate_global


def test_weighted_reporting_gains_w_star_equals_star_uniform_weights() -> None:
    """weights=ones: misma igualdad exacta."""
    result = build_gains_table(
        _model_3_leaves(), _standard_assign(), _standard_y(),
        weights=np.ones(250),
    )
    for r in result.rows:
        assert r.w_n == float(r.n)
        assert r.w_bad == float(r.n_bad)
        assert r.w_bad_rate_cum == r.bad_rate_cum
        assert r.w_lift_cum == r.lift_cum
    assert result.w_total == float(result.n_total)
    assert result.w_bad_rate_global == result.bad_rate_global


def test_weighted_reporting_gains_with_nontrivial_weights() -> None:
    """Pesos 2.0 en las filas de la hoja 2, 1.0 en el resto.

    w_n por fila: L0=50, L1=100, L2=200. w_bad: 5, 30, 120.
    w_total = 350, w_bad = 155, w_bad_rate_global = 155/350 = 31/70.
    """
    w = np.array([1.0] * 150 + [2.0] * 100)
    result = build_gains_table(
        _model_3_leaves(), _standard_assign(), _standard_y(), weights=w,
    )
    r0, r1, r2 = result.rows
    assert r0.w_n == pytest.approx(50.0, rel=1e-12)
    assert r1.w_n == pytest.approx(100.0, rel=1e-12)
    assert r2.w_n == pytest.approx(200.0, rel=1e-12)
    assert r2.w_bad == pytest.approx(120.0, rel=1e-12)
    assert r2.w_good == pytest.approx(80.0, rel=1e-12)
    assert r2.w_bad_rate == pytest.approx(0.6, rel=1e-12)
    assert r2.w_bad_rate_cum == pytest.approx(155.0 / 350.0, rel=1e-12)
    assert r2.w_n_cum == pytest.approx(350.0, rel=1e-12)
    assert r2.w_bad_cum == pytest.approx(155.0, rel=1e-12)
    assert result.w_total == pytest.approx(350.0, rel=1e-12)
    assert result.w_bad == pytest.approx(155.0, rel=1e-12)
    assert result.w_bad_rate_global == pytest.approx(31.0 / 70.0, rel=1e-12)
    # lift_cum de la primera fila: 0.1 / (31/70)
    assert r0.w_lift_cum == pytest.approx(0.1 / (31.0 / 70.0), rel=1e-12)


def test_weighted_reporting_classification_w_star_equals_star_no_weights() -> None:
    """weights=None: w_tp == tp, etc., con igualdad exacta."""
    pd_per_leaf = {0: 0.1, 1: 0.3, 2: 0.6}
    m = build_classification_matrix(
        _standard_assign(), _standard_y(), pd_per_leaf, threshold=0.5,
    )
    assert m.w_tp == float(m.tp)
    assert m.w_tn == float(m.tn)
    assert m.w_fp == float(m.fp)
    assert m.w_fn == float(m.fn)
    assert m.w_precision == m.precision
    assert m.w_recall == m.recall
    assert m.w_f1 == m.f1
    assert m.w_bad_capture_rate == m.bad_capture_rate


def test_weighted_reporting_classification_with_nontrivial_weights() -> None:
    """Pesos 2.0 en la hoja 2, threshold=0.5 (solo la hoja 2 predice bad).

    w_tp = 60*2 = 120 ; w_fp = 40*2 = 80 ; w_fn = 35 ; w_tn = 115.
    w_precision = 120/200 = 0.6 ; w_recall = 120/155 = 24/31.
    """
    pd_per_leaf = {0: 0.1, 1: 0.3, 2: 0.6}
    w = np.array([1.0] * 150 + [2.0] * 100)
    m = build_classification_matrix(
        _standard_assign(), _standard_y(), pd_per_leaf, threshold=0.5,
        weights=w,
    )
    assert m.w_tp == pytest.approx(120.0, rel=1e-12)
    assert m.w_fp == pytest.approx(80.0, rel=1e-12)
    assert m.w_fn == pytest.approx(35.0, rel=1e-12)
    assert m.w_tn == pytest.approx(115.0, rel=1e-12)
    assert m.w_precision == pytest.approx(0.6, rel=1e-12)
    assert m.w_recall == pytest.approx(24.0 / 31.0, rel=1e-12)
    assert m.w_bad_capture_rate == m.w_recall
    f1 = 2.0 * 0.6 * (24.0 / 31.0) / (0.6 + 24.0 / 31.0)
    assert m.w_f1 == pytest.approx(f1, rel=1e-12)


def test_weighted_reporting_rejects_wrong_length_weights() -> None:
    """Pesos de longitud incorrecta -> ValueError en ambas funciones."""
    pd_per_leaf = {0: 0.1, 1: 0.3, 2: 0.6}
    w_bad = np.ones(249)
    with pytest.raises(ValueError):
        build_gains_table(
            _model_3_leaves(), _standard_assign(), _standard_y(),
            weights=w_bad,
        )
    with pytest.raises(ValueError):
        build_classification_matrix(
            _standard_assign(), _standard_y(), pd_per_leaf, threshold=0.5,
            weights=w_bad,
        )


# ---------------------------------------------------------------------------
# 3.5.b - Reportes multiclase (D18, D19, D20)
# ---------------------------------------------------------------------------


def _model_k3() -> TreeModel:
    """Modelo K=3 real: raiz CHAID con 3 ramas y 3 hojas puras.

    PDs por hoja en orden canonico (indice 0 = clase de interes, "Low"):
      hoja 1 (filas de clase 0): (0.90, 0.05, 0.05)
      hoja 2 (filas de clase 1): (0.05, 0.90, 0.05)
      hoja 3 (filas de clase 2): (0.05, 0.05, 0.90)
    Separacion perfecta: cada hoja concentra su clase en su columna.
    """
    labels = ("Low", "Mid", "High")
    split = SplitConfig(
        predictor="seg", method="CHAID",
        statistic=5000.0, statistic_name="chi2", df=(2,),
        parent_n=90, child_ns=(30, 30, 30),
        p_value=1e-300, p_value_adjusted=1e-290,
        bonferroni_multiplier=100, n_merges=0,
        branches=((0,), (1,), (2,)),
    )
    root = TreeNode(
        node_id=0, depth=0, parent_id=None,
        n=90, n_events=(30, 30, 30),
        pd_jeffreys=(1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
        pd_final=(1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
        class_labels=labels,
        is_leaf=False, split=split, child_ids=(1, 2, 3), leaf_reason=None,
    )
    pds = ((0.90, 0.05, 0.05), (0.05, 0.90, 0.05), (0.05, 0.05, 0.90))
    leaves = [
        TreeNode(
            node_id=i, depth=1, parent_id=0,
            n=30, n_events=tuple(30 if k == i - 1 else 0 for k in range(3)),
            pd_jeffreys=pds[i - 1], pd_final=pds[i - 1],
            class_labels=labels,
            is_leaf=True, split=None, child_ids=(), leaf_reason="test",
        )
        for i in (1, 2, 3)
    ]
    return TreeModel(
        root_id=0, nodes=(root, *leaves), method="CHAID",
        params_fingerprint="test0000000000",
        class_labels=labels, target_class=0, target_class_index=0,
    )


def _assign_k3() -> np.ndarray:
    """90 filas enrutables: 30 a la hoja 1, 30 a la 2, 30 a la 3."""
    return np.array([1] * 30 + [2] * 30 + [3] * 30)


def _y_k3() -> np.ndarray:
    """90 filas: 30 por clase en orden canonico."""
    return np.array([0] * 30 + [1] * 30 + [2] * 30)


def test_binary_accuracy_populated() -> None:
    """Fase 3.5.b (D19): accuracy se puebla tambien en el path binario.

    Fixture de test_classification_matrix_thresholds (PDs 0.1/0.3/0.6,
    threshold=0.5): tp=60, tn=115, n=250 -> accuracy = (60+115)/250 = 0.7.
    El resto de campos nuevos queda vacio en el path binario.
    """
    pd_per_leaf = {0: 0.1, 1: 0.3, 2: 0.6}
    m = build_classification_matrix(
        _standard_assign(), _standard_y(), pd_per_leaf, threshold=0.5,
    )
    assert m.accuracy == pytest.approx(0.7, rel=1e-12)
    assert m.confusion_matrix == ()
    assert m.n_per_class == ()
    assert m.precision_per_class == ()
    assert m.recall_per_class == ()
    assert m.f1_per_class == ()
    assert m.w_confusion_matrix == ()
    assert m.w_n_per_class == ()
    assert m.w_precision_per_class == ()
    assert m.w_recall_per_class == ()
    assert m.w_f1_per_class == ()
    assert m.w_accuracy is None


def test_multiclass_classification_matrix_k3() -> None:
    """Matriz K=3 perfecta (diagonal 30); clase de interes = indice 0 (D19).

    Fixture: 90 filas enrutables, 30 por clase. argmax por hoja:
    hoja 0 -> 0, hoja 1 -> 1, hoja 2 -> 2. Matriz diagonal perfecta.
    Campos heredados con la clase 0 como "positivo": tp=30, fp=0, fn=0,
    tn=60.
    """
    pd_per_leaf = {0: (0.7, 0.2, 0.1), 1: (0.1, 0.7, 0.2), 2: (0.2, 0.1, 0.7)}
    assign = np.array([0] * 30 + [1] * 30 + [2] * 30)
    y = np.array([0] * 30 + [1] * 30 + [2] * 30)
    m = build_classification_matrix_multiclass(assign, y, pd_per_leaf)
    assert m.confusion_matrix == ((30, 0, 0), (0, 30, 0), (0, 0, 30))
    assert m.n_per_class == (30, 30, 30)
    assert m.accuracy == pytest.approx(1.0, rel=1e-12)
    assert m.precision_per_class == (1.0, 1.0, 1.0)
    assert m.recall_per_class == (1.0, 1.0, 1.0)
    assert m.f1_per_class == (1.0, 1.0, 1.0)
    assert (m.tp, m.fp, m.fn, m.tn) == (30, 0, 0, 60)
    assert m.precision == 1.0 and m.recall == 1.0 and m.f1 == 1.0
    assert m.bad_capture_rate == 1.0
    assert m.n_good == 60 and m.n_bad == 30
    assert np.isnan(m.threshold)


def test_multiclass_classification_matrix_k3_errors() -> None:
    """Matriz K=3 con errores controlados, verificada a mano.

    Fixture: 90 filas enrutables, 30 por clase. argmax: hoja 0 -> 0,
    hoja 1 -> 1, hoja 2 -> 2. Asignacion:
      clase 0 (30): 25 a hoja 0, 5 a hoja 1  -> fila 0 = (25, 5, 0)
      clase 1 (30): 30 a hoja 1              -> fila 1 = (0, 30, 0)
      clase 2 (30): 10 a hoja 0, 20 a hoja 2 -> fila 2 = (10, 0, 20)

    precision clase 0 = 25 / (25+0+10) = 25/35 = 5/7.
    recall clase 0 = 25/30 = 5/6.
    f1 clase 0 = 2*(5/7)*(5/6) / (5/7 + 5/6) = 10/13.
    accuracy = (25+30+20)/90 = 75/90 = 5/6.
    Heredados (clase 0 = positivo): tp=25, fp=10, fn=5, tn=50.
    """
    pd_per_leaf = {0: (0.7, 0.2, 0.1), 1: (0.1, 0.7, 0.2), 2: (0.2, 0.1, 0.7)}
    assign = np.array(
        [0] * 25 + [1] * 5      # 30 filas de clase 0
        + [1] * 30              # 30 filas de clase 1
        + [0] * 10 + [2] * 20   # 30 filas de clase 2
    )
    y = np.array([0] * 30 + [1] * 30 + [2] * 30)
    m = build_classification_matrix_multiclass(assign, y, pd_per_leaf)
    assert m.confusion_matrix == ((25, 5, 0), (0, 30, 0), (10, 0, 20))
    assert m.n_per_class == (30, 30, 30)
    p0, r0 = 25.0 / 35.0, 25.0 / 30.0
    assert m.precision_per_class[0] == pytest.approx(p0, rel=1e-12)
    assert m.recall_per_class[0] == pytest.approx(r0, rel=1e-12)
    assert m.f1_per_class[0] == pytest.approx(
        2.0 * p0 * r0 / (p0 + r0), rel=1e-12
    )
    assert m.f1_per_class[0] == pytest.approx(10.0 / 13.0, rel=1e-12)
    assert m.accuracy == pytest.approx(75.0 / 90.0, rel=1e-12)
    assert (m.tp, m.fp, m.fn, m.tn) == (25, 10, 5, 50)
    assert m.precision == pytest.approx(p0, rel=1e-12)
    assert m.recall == pytest.approx(r0, rel=1e-12)


def test_multiclass_classification_matrix_weighted() -> None:
    """Matriz K=3 ponderada: pesos 2.0 en la clase 0, 1.0 en el resto.

    Mismo fixture que test_multiclass_classification_matrix_k3_errors.
    Las celdas de la fila verdadera 0 se duplican; el resto no cambia:
      w_confusion_matrix = ((50, 10, 0), (0, 30, 0), (10, 0, 20)).
    Masa total: w_total = 30*2 + 60*1 = 120.
    Heredados ponderados (clase 0 = positivo):
      w_tp = 50 (cm[0,0] x 2).
      w_fp = verdadera != 0 predicha clase 0: cm[1,0]*1 + cm[2,0]*1 = 10
           (esas filas pesan 1.0, NO 2.0: solo la fila verdadera 0 se
           duplica).
      w_fn = verdadera 0 predicha != 0: (cm[0,1] + cm[0,2]) * 2 = 10.
      w_tn = 120 - 50 - 10 - 10 = 50.
      w_accuracy = traza ponderada / w_total = (50+30+20)/120 = 5/6.
    """
    pd_per_leaf = {0: (0.7, 0.2, 0.1), 1: (0.1, 0.7, 0.2), 2: (0.2, 0.1, 0.7)}
    assign = np.array(
        [0] * 25 + [1] * 5 + [1] * 30 + [0] * 10 + [2] * 20
    )
    y = np.array([0] * 30 + [1] * 30 + [2] * 30)
    w = np.array([2.0] * 30 + [1.0] * 60)
    m = build_classification_matrix_multiclass(
        assign, y, pd_per_leaf, weights=w
    )
    assert m.w_confusion_matrix == (
        (50.0, 10.0, 0.0), (0.0, 30.0, 0.0), (10.0, 0.0, 20.0)
    )
    assert m.w_n_per_class == (60.0, 30.0, 30.0)
    assert m.w_tp == pytest.approx(50.0, rel=1e-12)
    assert m.w_fp == pytest.approx(10.0, rel=1e-12)
    assert m.w_fn == pytest.approx(10.0, rel=1e-12)
    assert m.w_tn == pytest.approx(50.0, rel=1e-12)
    assert m.w_accuracy == pytest.approx(100.0 / 120.0, rel=1e-12)


def test_multiclass_gains_table_k3() -> None:
    """Gains table K=3: per-class por hoja, globales y metricas D20.

    Fixture: modelo K=3 real (_model_k3), 90 filas enrutables, 30 por
    clase, separacion perfecta. Orden por PD de la clase de interes
    (col 0) ascendente: L2 (0.05), L3 (0.05), L1 (0.90) — desempate
    por node_id ascendente entre L2 y L3.
    n_groups_eff = min(10, max(3, 90 // 5)) = min(10, 18) = 10 (D20).
    Separacion perfecta: ks = auc = gini = 1.0.
    """
    result = build_gains_table(_model_k3(), _assign_k3(), _y_k3())
    assert result.class_labels == ("Low", "Mid", "High")
    assert result.n_per_class_global == (30, 30, 30)
    assert [r.label for r in result.rows] == ["L2", "L3", "L1"]
    assert result.rows[0].n_per_class == (0, 30, 0)
    assert result.rows[1].n_per_class == (0, 0, 30)
    assert result.rows[2].n_per_class == (30, 0, 0)
    assert result.rows[0].n_per_class_cum == (0, 30, 0)
    assert result.rows[2].n_per_class_cum == (30, 30, 30)
    assert result.rows[0].n_per_class_decum == (30, 30, 30)
    assert result.rows[2].n_per_class_decum == (30, 0, 0)
    assert result.ks == 1.0 and result.auc == 1.0 and result.gini == 1.0
    assert [(i, j) for i, j, _ in result.ks_pairs] == [(0, 1), (0, 2), (1, 2)]
    assert [(i, j) for i, j, _ in result.auc_pairs] == [(0, 1), (0, 2), (1, 2)]
    assert all(v == 1.0 for _, _, v in result.auc_pairs)


def test_multiclass_gains_table_small_n() -> None:
    """D20: con menos de 15 filas enrutables no hay metricas (None).

    Fixture: mismo modelo K=3, 10 filas enrutables (4/3/3). No lanza;
    los conteos por clase si se pueblan.
    """
    assign = np.array([1] * 4 + [2] * 3 + [3] * 3)
    y = np.array([0] * 4 + [1] * 3 + [2] * 3)
    result = build_gains_table(_model_k3(), assign, y)
    assert result.n_total == 10
    assert result.ks is None and result.auc is None and result.gini is None
    assert result.ks_pairs == () and result.auc_pairs == ()
    assert result.n_per_class_global == (4, 3, 3)
    assert sum(result.n_per_class_global) == 10


def test_multiclass_gains_table_weighted() -> None:
    """Ponderado x multiclase: w_* por clase y ratios invariantes a escala.

    Mismo fixture que test_multiclass_gains_table_k3, pesos todos 2.0
    (uniformes): los conteos ponderados duplican a los fisicos y los
    ratios (ks, auc, gini) son identicos al caso sin pesos (invarianza
    de escala global de los pesos en metricas-ratio).
    """
    r0 = build_gains_table(_model_k3(), _assign_k3(), _y_k3())
    r1 = build_gains_table(
        _model_k3(), _assign_k3(), _y_k3(), weights=np.full(90, 2.0)
    )
    assert r1.w_n_per_class_global == (60.0, 60.0, 60.0)
    assert r1.n_per_class_global == r0.n_per_class_global
    assert r1.ks == r0.ks and r1.auc == r0.auc and r1.gini == r0.gini
    assert r1.ks_pairs == r0.ks_pairs and r1.auc_pairs == r0.auc_pairs


def test_binary_gains_table_parity_after_3_5_b() -> None:
    """Invariante no negociable: el path binario queda bit a bit igual.

    Fixture de test_gains_table_by_leaf (250 filas, 95 bads): mismos
    valores en los campos existentes y campos nuevos vacios.
    KS = 60/95 - 40/155 = 220/589; AUC = 10612.5/14725; Gini = 2*AUC-1.
    """
    result = build_gains_table(
        _model_3_leaves(), _standard_assign(), _standard_y()
    )
    assert result.n_total == 250
    assert result.n_good == 155
    assert result.n_bad == 95
    assert result.bad_rate_global == pytest.approx(0.38, rel=1e-12)
    assert result.ks == pytest.approx(220.0 / 589.0, rel=1e-12)
    assert result.auc == pytest.approx(10612.5 / 14725.0, rel=1e-12)
    assert result.gini == pytest.approx(
        2.0 * (10612.5 / 14725.0) - 1.0, rel=1e-12
    )
    assert result.w_total == pytest.approx(250.0, rel=1e-12)
    assert result.w_bad == pytest.approx(95.0, rel=1e-12)
    assert result.w_bad_rate_global == result.bad_rate_global
    assert result.class_labels == ()
    assert result.n_per_class_global == ()
    assert result.w_n_per_class_global == ()
    assert result.ks_pairs == ()
    assert result.auc_pairs == ()
    assert all(r.n_per_class == () for r in result.rows)


def test_binary_gains_table_weights_do_not_affect_ks_auc_gini() -> None:
    """D13 literal: el path binario NO pondera los ratios de cabecera.

    Con pesos uniformes de valor 3, ks/auc/gini son identicos al caso
    sin pesos (se computan por conteos), mientras que las columnas w_*
    si reflejan los pesos (w_n x 3).
    """
    r0 = build_gains_table(_model_3_leaves(), _standard_assign(), _standard_y())
    r1 = build_gains_table(
        _model_3_leaves(), _standard_assign(), _standard_y(),
        weights=np.full(250, 3.0),
    )
    assert r1.ks == r0.ks and r1.auc == r0.auc and r1.gini == r0.gini
    assert r1.rows[0].w_n == pytest.approx(3.0 * r0.rows[0].w_n, rel=1e-12)
    assert r1.w_total == pytest.approx(3.0 * r0.w_total, rel=1e-12)


def test_validated_routed_with_n_classes() -> None:
    """D18: _validated_routed exige binario por defecto; n_classes=K amplia.

    - n_classes=3 acepta etiquetas {0, 1, 2}.
    - sin n_classes (default) exige y binario y rechaza un 2.
    - n_classes=3 rechaza una etiqueta 3 (fuera de rango).
    """
    assign = np.array([0, 0, 1, 1, 2, 2])
    y_ok = np.array([0, 1, 2, 0, 1, 2])
    routed, leaf_ids, y_r = _validated_routed(assign, y_ok, "x", n_classes=3)
    assert routed.all() and len(leaf_ids) == 6
    with pytest.raises(ValueError):
        _validated_routed(assign, y_ok, "x")  # default: exige binario
    y_out = np.array([0, 1, 3, 0, 1, 2])
    with pytest.raises(ValueError):
        _validated_routed(assign, y_out, "x", n_classes=3)


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
