"""Tests para backend_v3.reporting.build_oos_oot_report (Fase 2.3.d).

Verifican el contrato del DTO plano OOS/OOT sin invocar Session ni ejecutar
ninguna corrida real. Todas las estructuras se construyen a mano (valores
verificados, no autoreferencias).

Incluye además tests para build_gains_table y build_classification_matrix
sobre un fixture sintético de 3 hojas (PDs 0.1/0.3/0.6, 250 filas, 95 bads).
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from backend_v3.reporting import (
    build_classification_matrix,
    build_gains_table,
    build_oos_oot_report,
)
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
    assert dto["oot"]["n_excluded"] == 0


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
