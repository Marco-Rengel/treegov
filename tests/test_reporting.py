"""Tests para backend_v3.reporting.build_oos_oot_report (Fase 2.3.d).

Verifican el contrato del DTO plano OOS/OOT sin invocar Session ni ejecutar
ninguna corrida real. Todas las estructuras se construyen a mano (valores
verificados, no autoreferencias).
"""

from __future__ import annotations

from backend_v3.reporting import build_oos_oot_report
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
        n=100, n_events=10,
        pd_jeffreys=0.104, pd_final=0.104,
        is_leaf=True, split=None, child_ids=(),
        leaf_reason="sin_split",
    )
    return TreeModel(
        root_id=0, nodes=(leaf,), method="CRT",
        params_fingerprint="test0000000000",
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