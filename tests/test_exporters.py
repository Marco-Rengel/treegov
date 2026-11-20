"""Tests for the Phase 4.0 production exporters (SQL / Python).

The fixture builds a real, frozen :class:`TreeModel` with the canonical
constructor of the analytical layer, so these tests exercise the exporters
against the same objects the session state produces: three nodes, one binary
split on ``edad`` at 40.0 and two leaves with ``pd_final`` (0.1, 0.9) and
(0.8, 0.2).

The parity tests run the generated Python module in memory and assert that the
exported rule returns exactly the leaf ``pd_final[0]`` the backend would return
for the same row, which is invariant §3 of ``docs/4.0_design_exports.md``.
"""

import math
import sqlite3
from typing import NamedTuple

import pandas as pd
import pytest

from backend_v3.exporters import (
    export_to_markdown,
    export_to_python,
    export_to_sql,
)
from backend_v3.imputation import ImputationSpec
from backend_v3.tree_builder import TreeModel, TreeNode
from backend_v3.types import PredictorType, SplitConfig, TargetType  # noqa: F401
from backend_v3.validation import (
    predict_leaf_assignment,
    predict_pd,
    select_majority_leaf,
)

# PredictorType and TargetType are imported for contract completeness: the 4.0
# brief fixes them as the vocabulary of the exporter surface. The exporters read
# only the split geometry, so those members are intentionally unused here.

CLASS_LABELS = ("0", "1")


class ExportCase(NamedTuple):
    """Bundle returned by the fixture: the model and its imputation spec."""

    model: TreeModel
    imputer: ImputationSpec


@pytest.fixture()
def export_case() -> ExportCase:
    """Build the reference tree and the reference imputation spec.

    The split is a CRT numeric split (``threshold``), which is the only split
    kind that the analytical layer allows to carry a ``threshold``: CHAID cuts
    by groups and rejects a threshold in its ``__post_init__``.
    """
    split = SplitConfig(
        predictor="edad",
        method="CRT",
        statistic=0.05,
        statistic_name="gini_gain",
        df=(),
        parent_n=100,
        child_ns=(60, 40),
        threshold=40.0,
        impurity_gain=0.05,
    )

    root = TreeNode(
        node_id=0,
        depth=0,
        parent_id=None,
        n=100,
        n_events=(38, 62),
        pd_jeffreys=(0.38, 0.62),
        pd_final=(0.38, 0.62),
        class_labels=CLASS_LABELS,
        is_leaf=False,
        split=split,
        child_ids=(1, 2),
        leaf_reason=None,
    )
    left = TreeNode(
        node_id=1,
        depth=1,
        parent_id=0,
        n=60,
        n_events=(6, 54),
        pd_jeffreys=(0.1, 0.9),
        pd_final=(0.1, 0.9),
        class_labels=CLASS_LABELS,
        is_leaf=True,
        split=None,
        child_ids=(),
        leaf_reason="max_depth",
    )
    right = TreeNode(
        node_id=2,
        depth=1,
        parent_id=0,
        n=40,
        n_events=(32, 8),
        pd_jeffreys=(0.8, 0.2),
        pd_final=(0.8, 0.2),
        class_labels=CLASS_LABELS,
        is_leaf=True,
        split=None,
        child_ids=(),
        leaf_reason="max_depth",
    )

    model = TreeModel(
        root_id=0,
        nodes=(root, left, right),
        method="CRT",
        params_fingerprint="fp-exporters-test",
        class_labels=CLASS_LABELS,
        target_class=1,
        target_class_index=0,
    )
    imputer = ImputationSpec(
        means={"edad": 35.5},
        modes={"seg": "A"},
        fitted_n=100,
    )
    return ExportCase(model=model, imputer=imputer)


def _load_python_export(source: str) -> dict:
    """Execute an exported Python module and return its namespace.

    A single namespace dict is used on purpose. With ``exec(source, {}, ns)``
    the two module-level functions end up in different dicts, so
    ``predict.__globals__`` would not contain ``_eval_tree`` and the first call
    would raise ``NameError``.
    """
    local_vars: dict = {}
    exec(compile(source, "<exported>", "exec"), local_vars)
    return local_vars


def test_export_sql_runs(export_case: ExportCase) -> None:
    """The SQL export is a non-empty string with SELECT, COALESCE and the fingerprint."""
    sql = export_to_sql(export_case.model, export_case.imputer)

    assert isinstance(sql, str)
    assert sql.strip()
    assert "SELECT" in sql
    assert "COALESCE" in sql
    assert export_case.model.params_fingerprint in sql


def test_export_python_runs(export_case: ExportCase) -> None:
    """The Python export is a non-empty string with predict, row.get and the fingerprint."""
    source = export_to_python(export_case.model, export_case.imputer)

    assert isinstance(source, str)
    assert source.strip()
    assert "def predict" in source
    assert "row.get" in source
    assert export_case.model.params_fingerprint in source


def test_python_parity_row_1(export_case: ExportCase) -> None:
    """A row below the threshold returns the left leaf probability (0.1)."""
    source = export_to_python(export_case.model, export_case.imputer)
    namespace = _load_python_export(source)
    predict = namespace["predict"]

    assert predict({"edad": 30, "seg": "A"}) == 0.1


def test_python_parity_row_2(export_case: ExportCase) -> None:
    """A row above the threshold returns the right leaf probability (0.8)."""
    source = export_to_python(export_case.model, export_case.imputer)
    namespace = _load_python_export(source)
    predict = namespace["predict"]

    assert predict({"edad": 50, "seg": "A"}) == 0.8


def test_export_markdown_runs(export_case: ExportCase) -> None:
    """The Markdown export is a non-empty string with the header,
    fingerprint and method.
    """
    md = export_to_markdown(export_case.model)
    assert isinstance(md, str)
    assert md.strip()
    assert md.startswith("# TreeGov Decision Tree")
    assert f"**Fingerprint:** {export_case.model.params_fingerprint}" in md
    assert f"**Method:** {export_case.model.method}" in md
    assert "## Decision Rules" in md


def test_export_markdown_threshold_branch(export_case: ExportCase) -> None:
    """The threshold split on ``edad`` renders as If <= 40.0 / Else."""
    md = export_to_markdown(export_case.model)
    assert "Node 0" in md
    assert "`edad`" in md
    assert "If <= 40.0" in md
    assert "Else" in md


def test_export_markdown_leaf_probabilities(export_case: ExportCase) -> None:
    """Both leaf probabilities appear with 4-decimal formatting."""
    md = export_to_markdown(export_case.model)
    assert "Probability = 0.1000" in md
    assert "Probability = 0.8000" in md
    assert "Leaf 1" in md
    assert "Leaf 2" in md


def test_export_markdown_signature_is_model_only(export_case: ExportCase) -> None:
    """The Markdown exporter takes only the model (no imputer): it is a
    descriptive artefact, not a scoring artefact. Calling it must work
    without an ImputationSpec.
    """
    md = export_to_markdown(export_case.model)
    assert md


# ---------------------------------------------------------------------------
# H-5.0.c-1: CHAID continuous splits with consolidated (merged) bin branches
# ---------------------------------------------------------------------------


def _merged_chaid_case() -> ExportCase:
    """CHAID continuous split whose engine merged adjacent bins.

    ``bin_edges`` (10, 20, 30) define 4 bins (bin_0..bin_3), but bin_0 and
    bin_1 were consolidated into one branch, so the tree has 3 children for
    4 bins. Before the H-5.0.c-1 fix, ``export_to_python`` and
    ``export_to_markdown`` raised ``ValueError`` and ``export_to_sql``
    emitted one predicate per individual bin, silently mis-scoring every
    row of the merged branch (see docs/audit_log.md, 01/11/2026).
    """
    split = SplitConfig(
        predictor="edad",
        method="CHAID",
        statistic=25.0,
        statistic_name="chi2",
        df=(2,),
        parent_n=100,
        child_ns=(50, 20, 30),
        p_value=0.000001,
        p_value_adjusted=0.000055,
        bonferroni_multiplier=55,
        n_merges=1,
        branches=(("bin_0", "bin_1"), ("bin_2",), ("bin_3",)),
        bin_edges=(10.0, 20.0, 30.0),
    )
    root = TreeNode(
        node_id=0,
        depth=0,
        parent_id=None,
        n=100,
        n_events=(42, 58),
        pd_jeffreys=(0.42, 0.58),
        pd_final=(0.42, 0.58),
        class_labels=CLASS_LABELS,
        is_leaf=False,
        split=split,
        child_ids=(1, 2, 3),
        leaf_reason=None,
    )
    leaves = tuple(
        TreeNode(
            node_id=i + 1,
            depth=1,
            parent_id=0,
            n=n,
            n_events=events,
            pd_jeffreys=pd,
            pd_final=pd,
            class_labels=CLASS_LABELS,
            is_leaf=True,
            split=None,
            child_ids=(),
            leaf_reason="max_depth",
        )
        for i, (n, events, pd) in enumerate(
            (
                (50, (5, 45), (0.1, 0.9)),
                (20, (10, 10), (0.5, 0.5)),
                (30, (27, 3), (0.9, 0.1)),
            )
        )
    )
    model = TreeModel(
        root_id=0,
        nodes=(root, *leaves),
        method="CHAID",
        params_fingerprint="fp-merged-chaid",
        class_labels=CLASS_LABELS,
        target_class=1,
        target_class_index=0,
    )
    imputer = ImputationSpec(means={"edad": 35.5}, modes={}, fitted_n=100)
    return ExportCase(model=model, imputer=imputer)


def test_export_sql_merged_chaid_branches() -> None:
    """One WHEN per consolidated branch, closing with policy-governed ELSE."""
    case = _merged_chaid_case()
    sql = export_to_sql(case.model, case.imputer)

    # Branch 0 = bins 0+1 (edad <= 20.0), branch 1 = bin 2 (<= 30.0), branch 2 (> 30.0).
    assert 'WHEN COALESCE("edad", 35.5) <= 20.0 THEN' in sql
    assert 'WHEN COALESCE("edad", 35.5) <= 30.0 THEN' in sql
    assert 'WHEN COALESCE("edad", 35.5) > 30.0 THEN' in sql
    # No per-bin predicate may survive: bin_0/bin_1 are not separate arms.
    assert "<= 10.0" not in sql
    # Residual ELSE is governed by unseen_policy (default: exclude -> NULL).
    assert "ELSE NULL\nEND" in sql
    assert case.model.params_fingerprint in sql


def test_export_python_merged_chaid_parity() -> None:
    """Scoring parity of the exported module on merged-bin boundaries."""
    case = _merged_chaid_case()
    namespace = _load_python_export(export_to_python(case.model, case.imputer))
    predict = namespace["predict"]

    # Branch 0 (bins 0+1): includes bin_1 rows, mis-scored before the fix.
    assert predict({"edad": 5}) == 0.1
    assert predict({"edad": 10}) == 0.1  # digitize(right=True): bin_0 edge
    assert predict({"edad": 15}) == 0.1  # merged bin_1
    assert predict({"edad": 20}) == 0.1  # bin_1 edge
    # Branch 1 (bin_2).
    assert predict({"edad": 25}) == 0.5
    assert predict({"edad": 30}) == 0.5  # bin_2 edge
    # Branch 2 (bin_3): residual else.
    assert predict({"edad": 35}) == 0.9
    # Training-time imputation follows the same consolidated routing.
    assert predict({}) == 0.9  # mean 35.5 -> top branch


def test_export_markdown_merged_chaid_branches() -> None:
    """The report renders one rule per consolidated branch, without raising."""
    case = _merged_chaid_case()
    md = export_to_markdown(case.model)

    assert "- If <= 20.0:" in md
    assert "- Elif <= 30.0:" in md
    assert "- Else:" in md
    assert "<= 10.0" not in md
    assert "Probability = 0.1000" in md
    assert "Probability = 0.5000" in md
    assert "Probability = 0.9000" in md
    assert case.model.params_fingerprint in md


# ------------------------------------------------------------------
# Fase 4.0.1.a — unseen_policy en los exportadores (bloque aditivo;
# referente: docs/4.0.1_design_categorical_exporters.md D1-D7).
# ------------------------------------------------------------------


def _categorical_case_two_branches() -> ExportCase:
    """CHAID categorical split on ``seg`` with two branch value sets.

    Branch 0 = ``("A", "B")`` -> leaf ``pd_final[0] = 0.1``; branch 1 =
    ``("C",)`` -> leaf ``pd_final[0] = 0.8``. The imputation mode of
    ``seg`` is ``"A"``, so a row with a missing value routes to
    branch 0. Geometry mirrors ``_merged_chaid_case`` but with a
    ``branches`` tuple (one value set per child, contract D4).
    """
    split = SplitConfig(
        predictor="seg",
        method="CHAID",
        statistic=9.0,
        statistic_name="chi2",
        df=(1,),
        parent_n=100,
        child_ns=(50, 50),
        p_value=0.0001,
        p_value_adjusted=0.0005,
        bonferroni_multiplier=5,
        n_merges=1,
        branches=(("A", "B"), ("C",)),
    )
    root = TreeNode(
        node_id=0,
        depth=0,
        parent_id=None,
        n=100,
        n_events=(38, 62),
        pd_jeffreys=(0.38, 0.62),
        pd_final=(0.38, 0.62),
        class_labels=CLASS_LABELS,
        is_leaf=False,
        split=split,
        child_ids=(1, 2),
        leaf_reason=None,
    )
    leaf_0 = TreeNode(
        node_id=1,
        depth=1,
        parent_id=0,
        n=50,
        n_events=(5, 45),
        pd_jeffreys=(0.1, 0.9),
        pd_final=(0.1, 0.9),
        class_labels=CLASS_LABELS,
        is_leaf=True,
        split=None,
        child_ids=(),
        leaf_reason="max_depth",
    )
    leaf_1 = TreeNode(
        node_id=2,
        depth=1,
        parent_id=0,
        n=50,
        n_events=(40, 10),
        pd_jeffreys=(0.8, 0.2),
        pd_final=(0.8, 0.2),
        class_labels=CLASS_LABELS,
        is_leaf=True,
        split=None,
        child_ids=(),
        leaf_reason="max_depth",
    )
    model = TreeModel(
        root_id=0,
        nodes=(root, leaf_0, leaf_1),
        method="CHAID",
        params_fingerprint="fp-categorical-two",
        class_labels=CLASS_LABELS,
        target_class=1,
        target_class_index=0,
    )
    imputer = ImputationSpec(means={}, modes={"seg": "A"}, fitted_n=100)
    return ExportCase(model=model, imputer=imputer)


def test_export_unseen_policy_invalid_value() -> None:
    """A value outside the vocabulary raises ``ValueError`` naming all
    three admissible values; matching is case-sensitive.
    """
    case = _categorical_case_two_branches()
    for bad in ("invalid", "EXCLUDE"):
        with pytest.raises(
            ValueError, match=r"valores admitidos: 'error', 'exclude', 'majority'"
        ):
            export_to_sql(case.model, case.imputer, unseen_policy=bad)
        with pytest.raises(
            ValueError, match=r"valores admitidos: 'error', 'exclude', 'majority'"
        ):
            export_to_python(case.model, case.imputer, unseen_policy=bad)
        with pytest.raises(
            ValueError, match=r"valores admitidos: 'error', 'exclude', 'majority'"
        ):
            export_to_markdown(case.model, unseen_policy=bad)


def test_export_python_exclude_categorical_routing() -> None:
    """Mode ``"exclude"``: unseen category -> ``None``, last-set member
    -> the last branch's own leaf (the divergent routing fixed here).
    """
    case = _categorical_case_two_branches()
    namespace = _load_python_export(export_to_python(case.model, case.imputer))
    predict = namespace["predict"]

    assert predict({"seg": "A"}) == 0.1
    assert predict({"seg": "B"}) == 0.1
    # The final branch renders from its own value set (parity back-end).
    assert predict({"seg": "C"}) == 0.8
    # Unseen category: not scored — SQL returns NULL, Python None, backend
    # excludes the row (invariant I-2 of the 4.0.1 design note).
    assert predict({"seg": "Z"}) is None
    # Missing value imputes mode "A" and keeps routing to branch 0.
    assert predict({}) == 0.1

    # Artifact shape: one explicit set per branch plus residual fallback.
    source = export_to_python(case.model, case.imputer)
    assert "if val_seg in ('A', 'B'):" in source
    assert "elif val_seg in ('C',):" in source
    assert "else:\n        return None" in source
    assert "def predict(row: dict) -> float | None:" in source


def test_export_artifact_headers_declare_policy() -> None:
    """Every artefact declares the active policy next to the fingerprint."""
    case = _categorical_case_two_branches()
    fp = case.model.params_fingerprint

    # Mode "exclude": the original header contract remains unchanged.
    sql = export_to_sql(case.model, case.imputer)
    assert sql.splitlines()[0] == f"-- TreeGov Model Fingerprint: {fp}"
    assert sql.splitlines()[1] == (
        "-- Unseen policy: exclude (unseen categories return NULL; caller must filter)"
    )

    source = export_to_python(case.model, case.imputer)
    assert source.splitlines()[0] == f"# TreeGov Model Fingerprint: {fp}"
    assert source.splitlines()[1] == (
        "# Unseen policy: exclude (unseen categories return None; caller must filter)"
    )

    md = export_to_markdown(case.model)
    assert (
        "**Unseen policy:** exclude (unseen categories are not scored;"
        " caller must filter NULL/None)."
    ) in md

    # Mode "error": SQL adds its portability warning to the policy line.
    sql = export_to_sql(case.model, case.imputer, unseen_policy="error")
    assert sql.splitlines()[0] == f"-- TreeGov Model Fingerprint: {fp}"
    assert sql.splitlines()[1] == (
        "-- Unseen policy: error (unseen categories abort the scoring)"
    )
    assert sql.splitlines()[2].startswith(
        "-- WARNING: one or more predictors below use ELSE 1/0"
    )

    source = export_to_python(case.model, case.imputer, unseen_policy="error")
    assert source.splitlines()[0] == f"# TreeGov Model Fingerprint: {fp}"
    assert source.splitlines()[1] == (
        "# Unseen policy: error (unseen categories raise ValueError; "
        "caller sees the exception)"
    )

    md = export_to_markdown(case.model, unseen_policy="error")
    assert (
        "**Unseen policy:** error (unseen categories abort the scoring; "
        "caller sees the exception)."
    ) in md

    # Mode "majority": all three headers expose the frozen majority-leaf PD.
    # Equal-n tie (n=50 vs n=50) breaks deterministically by minimum node_id (node 1, pd=0.1).
    sql = export_to_sql(case.model, case.imputer, unseen_policy="majority")
    assert sql.splitlines()[0] == f"-- TreeGov Model Fingerprint: {fp}"
    assert sql.splitlines()[1] == (
        "-- Unseen policy: majority (unseen categories route to the majority "
        "leaf, pd=0.1000)"
    )

    source = export_to_python(case.model, case.imputer, unseen_policy="majority")
    assert source.splitlines()[0] == f"# TreeGov Model Fingerprint: {fp}"
    assert source.splitlines()[1] == (
        "# Unseen policy: majority (unseen categories route to the majority "
        "leaf, pd=0.1000)"
    )

    md = export_to_markdown(case.model, unseen_policy="majority")
    assert (
        "**Unseen policy:** majority (unseen categories route to the majority "
        "leaf, pd=0.1000)."
    ) in md


def test_sql_body_idempotent_in_exclude(export_case: ExportCase) -> None:
    """Explicit ``exclude`` reproduces the default SQL byte for byte."""
    default_sql = export_to_sql(export_case.model, export_case.imputer)
    exclude_sql = export_to_sql(
        export_case.model, export_case.imputer, unseen_policy="exclude"
    )

    assert exclude_sql == default_sql
    lines = default_sql.splitlines()
    assert lines[0] == (
        f"-- TreeGov Model Fingerprint: {export_case.model.params_fingerprint}"
    )
    assert lines[1] == (
        "-- Unseen policy: exclude (unseen categories return NULL; caller must filter)"
    )
    assert lines[2].startswith("SELECT CASE")


def test_export_categorical_d4_cardinality_mismatch() -> None:
    """Every exporter rejects a categorical branch/child count mismatch."""
    from dataclasses import replace

    case = _categorical_case_two_branches()
    root = replace(case.model.nodes[0], child_ids=(1, 2, 3))
    extra_leaf = replace(case.model.nodes[2], node_id=3)
    model = replace(
        case.model, nodes=(root, *case.model.nodes[1:], extra_leaf)
    )

    with pytest.raises(ValueError, match="needs exactly one branch value set per child"):
        export_to_sql(model, case.imputer)
    with pytest.raises(ValueError, match="needs exactly one branch value set per child"):
        export_to_python(model, case.imputer)
    with pytest.raises(ValueError, match="needs exactly one branch value set per child"):
        export_to_markdown(model)


def test_export_unseen_policy_error_sql() -> None:
    """Mode ``error`` emits warnings and a division-by-zero fallback."""
    case = _categorical_case_two_branches()
    sql = export_to_sql(case.model, case.imputer, unseen_policy="error")

    assert "-- Unseen policy: error (unseen categories abort the scoring)" in sql
    assert "-- WARNING: one or more predictors below use ELSE 1/0" in sql
    assert "-- WARNING: unseen category in predictor 'seg' -> division by zero" in sql
    assert "ELSE 1/0" in sql
    assert "ELSE NULL" not in sql
    assert case.model.params_fingerprint in sql


def test_export_unseen_policy_error_python() -> None:
    """Mode ``error`` aborts only rows carrying an unseen category."""
    case = _categorical_case_two_branches()
    source = export_to_python(case.model, case.imputer, unseen_policy="error")

    assert "# Unseen policy: error (unseen categories raise ValueError" in source
    assert "def predict(row: dict) -> float:" in source
    assert "raise ValueError(" in source
    assert "Unseen category in predictor 'seg'" in source
    assert "return None" not in source

    namespace = _load_python_export(source)
    predict = namespace["predict"]
    assert predict({"seg": "A"}) == 0.1
    assert predict({"seg": "C"}) == 0.8
    with pytest.raises(ValueError, match="Unseen category in predictor"):
        predict({"seg": "Z"})


def test_export_unseen_policy_error_markdown() -> None:
    """Mode ``error`` labels the residual Markdown bullet explicitly."""
    case = _categorical_case_two_branches()
    md = export_to_markdown(case.model, unseen_policy="error")

    assert (
        "**Unseen policy:** error (unseen categories abort the scoring; "
        "caller sees the exception)."
    ) in md
    assert "- Else (unseen category → ValueError raised; policy = error):" in md


def test_export_unseen_policy_majority_sql() -> None:
    """Mode ``majority`` freezes the selected leaf PD in the SQL fallback."""
    case = _categorical_case_two_branches()
    sql = export_to_sql(case.model, case.imputer, unseen_policy="majority")

    # Equal-n tie (n=50 vs n=50) selects minimum node_id (node 1, pd=0.1).
    assert (
        "-- Unseen policy: majority (unseen categories route to the majority "
        "leaf, pd=0.1000)"
    ) in sql
    assert "ELSE 0.1" in sql
    assert "ELSE 1/0" not in sql
    assert "ELSE NULL" not in sql


def test_export_unseen_policy_majority_python() -> None:
    """Mode ``majority`` scores unseen rows with the selected leaf PD."""
    case = _categorical_case_two_branches()
    source = export_to_python(case.model, case.imputer, unseen_policy="majority")

    assert (
        "# Unseen policy: majority (unseen categories route to the majority "
        "leaf, pd="
    ) in source
    assert "def predict(row: dict) -> float:" in source
    assert "return None" not in source

    namespace = _load_python_export(source)
    predict = namespace["predict"]
    majority_prediction = predict({"seg": "Z"})
    assert isinstance(majority_prediction, float)
    assert majority_prediction == 0.1
    assert predict({"seg": "A"}) == 0.1
    assert predict({"seg": "C"}) == 0.8


def test_export_unseen_policy_majority_markdown() -> None:
    """Mode ``majority`` reports the frozen PD in header and bullet."""
    case = _categorical_case_two_branches()
    md = export_to_markdown(case.model, unseen_policy="majority")

    assert (
        "**Unseen policy:** majority (unseen categories route to the majority "
        "leaf, pd="
    ) in md
    assert "- Else (unseen category → routed to majority leaf pd=" in md
    assert "; policy = majority):" in md
    assert "pd=0.1000" in md


# ---------------------------------------------------------------------------
# Fase 3.12.a: filtro por nodo (node_id) en los tres exportadores
# ---------------------------------------------------------------------------


def _deep_case() -> ExportCase:
    """Build a three-level tree so node 1 is an INTERNAL node.

    Node 0 splits ``edad`` at 40.0. Its left child (node 1, internal)
    splits ``importe`` at 10.0 into leaves 3 (pd 0.2) and 4 (pd 0.7);
    the right child (node 2) is the leaf with pd 0.8. Filtering by node 1
    therefore drops the root split and leaf 2, which is exactly the
    sub-tree export contract of Phase 3.12.a.
    """
    root_split = SplitConfig(
        predictor="edad",
        method="CRT",
        statistic=0.05,
        statistic_name="gini_gain",
        df=(),
        parent_n=100,
        child_ns=(60, 40),
        threshold=40.0,
        impurity_gain=0.05,
    )
    left_split = SplitConfig(
        predictor="importe",
        method="CRT",
        statistic=0.04,
        statistic_name="gini_gain",
        df=(),
        parent_n=60,
        child_ns=(30, 30),
        threshold=10.0,
        impurity_gain=0.04,
    )

    def _node(node_id: int, depth: int, parent_id: int | None, n: int,
              pd: tuple[float, float], *, split=None, child_ids=(),
              leaf_reason=None) -> TreeNode:
        return TreeNode(
            node_id=node_id,
            depth=depth,
            parent_id=parent_id,
            n=n,
            n_events=(int(round(n * pd[0])), n - int(round(n * pd[0]))),
            pd_jeffreys=pd,
            pd_final=pd,
            class_labels=CLASS_LABELS,
            is_leaf=split is None,
            split=split,
            child_ids=tuple(child_ids),
            leaf_reason=leaf_reason,
        )

    root = _node(0, 0, None, 100, (0.38, 0.62),
                 split=root_split, child_ids=(1, 2))
    left = _node(1, 1, 0, 60, (0.30, 0.70),
                 split=left_split, child_ids=(3, 4))
    right = _node(2, 1, 0, 40, (0.80, 0.20), leaf_reason="max_depth")
    leaf_a = _node(3, 2, 1, 30, (0.20, 0.80), leaf_reason="max_depth")
    leaf_b = _node(4, 2, 1, 30, (0.70, 0.30), leaf_reason="max_depth")

    model = TreeModel(
        root_id=0,
        nodes=(root, left, right, leaf_a, leaf_b),
        method="CRT",
        params_fingerprint="fp-deep-case",
        class_labels=CLASS_LABELS,
        target_class=1,
        target_class_index=0,
    )
    imputer = ImputationSpec(
        means={"edad": 35.5, "importe": 12.0},
        modes={"seg": "A"},
        fitted_n=100,
    )
    return ExportCase(model=model, imputer=imputer)


def test_export_node_id_none_is_byte_identical(export_case: ExportCase) -> None:
    """Default ``node_id=None`` and explicit ``root_id`` match the 4.0 output."""
    model, imputer = export_case.model, export_case.imputer

    assert export_to_sql(model, imputer) == export_to_sql(
        model, imputer, node_id=None
    )
    assert export_to_python(model, imputer) == export_to_python(
        model, imputer, node_id=None
    )
    assert export_to_markdown(model) == export_to_markdown(model, node_id=None)

    assert export_to_sql(model, imputer) == export_to_sql(
        model, imputer, node_id=model.root_id
    )
    assert export_to_python(model, imputer) == export_to_python(
        model, imputer, node_id=model.root_id
    )
    assert export_to_markdown(model) == export_to_markdown(
        model, node_id=model.root_id
    )


def test_export_sql_node_filter_renders_subtree_only() -> None:
    """Filtering by internal node 1 drops the root split and leaf 2."""
    case = _deep_case()
    full = export_to_sql(case.model, case.imputer)
    sub = export_to_sql(case.model, case.imputer, node_id=1)

    assert len(sub) < len(full)
    assert 'COALESCE("importe", 12.0) <= 10.0' in sub
    assert 'COALESCE("edad"' not in sub
    assert "40.0" not in sub
    assert "0.2" in sub and "0.7" in sub
    assert sub.startswith("-- TreeGov Model Fingerprint: fp-deep-case")
    assert sub.strip().endswith("AS prediction_score;")


def test_export_python_node_filter_scores_subtree() -> None:
    """The sub-tree module ignores the path that reaches the new root."""
    case = _deep_case()
    full = export_to_python(case.model, case.imputer)
    sub = export_to_python(case.model, case.imputer, node_id=1)

    assert len(sub) < len(full)
    assert "edad" not in sub
    assert "row.get('importe', 12.0)" in sub

    predict = _load_python_export(sub)["predict"]
    assert predict({"importe": 5}) == 0.2
    assert predict({"importe": 20}) == 0.7
    # A row that never reaches node 1 in the full model is still scored:
    # the exported rule treats node 1 as root by contract (3.12.a).
    assert predict({"importe": 5, "edad": 99}) == 0.2


def test_export_markdown_node_filter_renders_subtree_only() -> None:
    """The Markdown report starts at node 1 and omits nodes 0 and 2."""
    case = _deep_case()
    full = export_to_markdown(case.model)
    sub = export_to_markdown(case.model, node_id=1)

    assert len(sub) < len(full)
    assert sub.startswith("# TreeGov Decision Tree")
    assert "## Decision Rules" in sub
    assert "- **Node 1** (Split on `importe`):" in sub
    assert "Node 0" not in sub
    assert "Leaf 2" not in sub
    assert "Leaf 3" in sub and "Leaf 4" in sub
    assert "If <= 10.0" in sub


def test_export_unknown_node_id_raises_keyerror() -> None:
    """A missing node aborts the export instead of silently using the root."""
    case = _deep_case()
    with pytest.raises(KeyError):
        export_to_sql(case.model, case.imputer, node_id=99)
    with pytest.raises(KeyError):
        export_to_python(case.model, case.imputer, node_id=99)
    with pytest.raises(KeyError):
        export_to_markdown(case.model, node_id=99)


# ---------------------------------------------------------------------------
# Block 2A regressions: CRIT-01 (majority leaf) & CRIT-04 (SQL/Python parity)
# ---------------------------------------------------------------------------


def _eval_sql_in_sqlite(
    sql: str, rows: list[dict], schema: list[tuple[str, str]]
) -> list[float | None]:
    """Execute an exported ANSI SQL SELECT against an in-memory SQLite table."""
    conn = sqlite3.connect(":memory:")
    try:
        cols_ddl = ", ".join(
            f'"{name.replace(chr(34), chr(34) * 2)}" {col_type}'
            for name, col_type in schema
        )
        conn.execute(f"CREATE TABLE scoring_input (_rid INTEGER PRIMARY KEY, {cols_ddl})")
        col_names = [name for name, _ in schema]
        quoted_cols = ", ".join(
            f'"{name.replace(chr(34), chr(34) * 2)}"' for name in col_names
        )
        placeholders = ", ".join(["?"] * (len(col_names) + 1))
        for rid, row in enumerate(rows):
            vals = [rid]
            for name in col_names:
                val = row.get(name)
                if isinstance(val, float) and math.isnan(val):
                    val = None
                vals.append(val)
            conn.execute(
                f"INSERT INTO scoring_input (_rid, {quoted_cols}) VALUES ({placeholders})",
                vals,
            )
        sql_clean = sql.rstrip()
        assert sql_clean.endswith(";")
        query = sql_clean[:-1] + " FROM scoring_input ORDER BY _rid;"
        return [r[0] for r in conn.execute(query).fetchall()]
    finally:
        conn.close()


def _assert_scores_equal(actual: object, expected: object) -> None:
    """Compare SQL/Python/backend scalar outputs treating None and NaN as missing."""
    actual_missing = actual is None or (isinstance(actual, float) and math.isnan(actual))
    expected_missing = expected is None or (
        isinstance(expected, float) and math.isnan(expected)
    )
    if expected_missing:
        assert actual_missing, f"Expected missing score, got {actual!r}"
    else:
        assert not actual_missing, f"Expected {expected!r}, got missing"
        assert math.isclose(float(actual), float(expected), rel_tol=1e-12)


def test_export_majority_unequal_leaf_sizes() -> None:
    """CRIT-01: all exporters and backend select the largest physical-n leaf."""
    split = SplitConfig(
        predictor="seg",
        method="CHAID",
        statistic=12.0,
        statistic_name="chi2",
        df=(1,),
        parent_n=100,
        child_ns=(20, 80),
        p_value=0.0001,
        p_value_adjusted=0.0005,
        bonferroni_multiplier=5,
        n_merges=0,
        branches=(("A",), ("B",)),
    )
    root = TreeNode(
        node_id=0, depth=0, parent_id=None, n=100, n_events=(24, 76),
        pd_jeffreys=(0.24, 0.76), pd_final=(0.24, 0.76), class_labels=CLASS_LABELS,
        is_leaf=False, split=split, child_ids=(1, 2), leaf_reason=None,
    )
    small_leaf = TreeNode(
        node_id=1, depth=1, parent_id=0, n=20, n_events=(16, 4),
        pd_jeffreys=(0.8, 0.2), pd_final=(0.8, 0.2), class_labels=CLASS_LABELS,
        is_leaf=True, split=None, child_ids=(), leaf_reason="max_depth",
    )
    large_leaf = TreeNode(
        node_id=2, depth=1, parent_id=0, n=80, n_events=(8, 72),
        pd_jeffreys=(0.1, 0.9), pd_final=(0.1, 0.9), class_labels=CLASS_LABELS,
        is_leaf=True, split=None, child_ids=(), leaf_reason="max_depth",
    )
    model = TreeModel(
        root_id=0, nodes=(root, small_leaf, large_leaf), method="CHAID",
        params_fingerprint="fp-unequal-majority", class_labels=CLASS_LABELS,
        target_class=1, target_class_index=0,
    )
    imputer = ImputationSpec(means={}, modes={"seg": "B"}, fitted_n=100)

    assert select_majority_leaf(model).node_id == 2
    df_unseen = pd.DataFrame({"seg": ["Z"]})
    assert list(predict_leaf_assignment(model, df_unseen, unseen_policy="majority")) == [2]

    sql = export_to_sql(model, imputer, unseen_policy="majority")
    assert "pd=0.1000" in sql
    assert "ELSE 0.1" in sql
    assert _eval_sql_in_sqlite(sql, [{"seg": "Z"}], [("seg", "TEXT")]) == [0.1]

    py_src = export_to_python(model, imputer, unseen_policy="majority")
    assert "pd=0.1000" in py_src
    predict = _load_python_export(py_src)["predict"]
    assert predict({"seg": "Z"}) == 0.1

    md = export_to_markdown(model, unseen_policy="majority")
    assert "pd=0.1000" in md


def test_sqlite_parity_threshold_with_and_without_imputation(
    export_case: ExportCase,
) -> None:
    """Exact SQL == Python == predict_pd parity on threshold splits, NaN and boundaries."""
    model = export_case.model
    rows = [
        {"edad": 30.0},
        {"edad": 40.0},
        {"edad": 40.0001},
        {"edad": None},
        {"edad": float("nan")},
    ]

    # 1) With training-time imputation (mean = 35.5 <= 40.0 -> 0.1)
    sql_imp = export_to_sql(model, export_case.imputer, unseen_policy="exclude")
    py_imp = _load_python_export(
        export_to_python(model, export_case.imputer, unseen_policy="exclude")
    )["predict"]
    sql_res_imp = _eval_sql_in_sqlite(sql_imp, rows, [("edad", "REAL")])
    py_res_imp = [py_imp(r) for r in rows]
    df_imp = pd.DataFrame({"edad": [30.0, 40.0, 40.0001, 35.5, 35.5]})
    backend_imp = predict_pd(model, df_imp, unseen_policy="exclude")[:, 0]
    for s_val, p_val, b_val in zip(sql_res_imp, py_res_imp, backend_imp):
        _assert_scores_equal(s_val, b_val)
        _assert_scores_equal(p_val, b_val)

    # 2) Without imputation: None and float('nan') obey unseen_policy
    empty_imputer = ImputationSpec(means={}, modes={}, fitted_n=100)
    df_raw = pd.DataFrame({"edad": [30.0, 40.0, 40.0001, None, float("nan")]})
    for policy in ("exclude", "majority"):
        sql = export_to_sql(model, empty_imputer, unseen_policy=policy)
        predict = _load_python_export(
            export_to_python(model, empty_imputer, unseen_policy=policy)
        )["predict"]
        sql_vals = _eval_sql_in_sqlite(sql, rows, [("edad", "REAL")])
        py_vals = [predict(r) for r in rows]
        backend_vals = predict_pd(model, df_raw, unseen_policy=policy)[:, 0]
        for s_val, p_val, b_val in zip(sql_vals, py_vals, backend_vals):
            _assert_scores_equal(s_val, b_val)
            _assert_scores_equal(p_val, b_val)

    # 3) Without imputation under unseen_policy="error": Python raises ValueError on None/NaN
    predict_err = _load_python_export(
        export_to_python(model, empty_imputer, unseen_policy="error")
    )["predict"]
    assert predict_err({"edad": 40.0}) == 0.1
    with pytest.raises(ValueError, match="Missing value in predictor 'edad'"):
        predict_err({"edad": None})
    with pytest.raises(ValueError, match="Missing value in predictor 'edad'"):
        predict_err({"edad": float("nan")})


def test_sqlite_parity_merged_chaid_without_imputation() -> None:
    """Merged CHAID SQL/Python never route NULL/NaN silently into the top bin."""
    case = _merged_chaid_case()
    empty_imputer = ImputationSpec(means={}, modes={}, fitted_n=100)
    rows = [
        {"edad": 5.0},
        {"edad": 10.0},
        {"edad": 15.0},
        {"edad": 20.0},
        {"edad": 25.0},
        {"edad": 30.0},
        {"edad": 35.0},
        {"edad": None},
        {"edad": float("nan")},
    ]
    df_raw = pd.DataFrame({"edad": [r["edad"] for r in rows]})

    for policy in ("exclude", "majority"):
        sql = export_to_sql(case.model, empty_imputer, unseen_policy=policy)
        predict = _load_python_export(
            export_to_python(case.model, empty_imputer, unseen_policy=policy)
        )["predict"]
        sql_vals = _eval_sql_in_sqlite(sql, rows, [("edad", "REAL")])
        py_vals = [predict(r) for r in rows]
        backend_vals = predict_pd(case.model, df_raw, unseen_policy=policy)[:, 0]
        for s_val, p_val, b_val in zip(sql_vals, py_vals, backend_vals):
            _assert_scores_equal(s_val, b_val)
            _assert_scores_equal(p_val, b_val)

    # Specifically confirm NULL/NaN in exclude -> missing (NOT top branch 0.9)
    sql_ex = export_to_sql(case.model, empty_imputer, unseen_policy="exclude")
    assert _eval_sql_in_sqlite(sql_ex, [{"edad": None}], [("edad", "REAL")]) == [None]
    # Majority leaf is node 1 (n=50, pd=0.1), NOT top branch 0.9
    sql_maj = export_to_sql(case.model, empty_imputer, unseen_policy="majority")
    assert _eval_sql_in_sqlite(sql_maj, [{"edad": None}], [("edad", "REAL")]) == [0.1]


def test_sqlite_parity_categorical_quotes_and_integer_categories() -> None:
    """Single-quoted text categories and integer categories achieve 100% parity."""
    # A) Text categorical with single quotes ("O'Connor")
    split_txt = SplitConfig(
        predictor="apellido",
        method="CHAID",
        statistic=8.0,
        statistic_name="chi2",
        df=(1,),
        parent_n=100,
        child_ns=(70, 30),
        p_value=0.001,
        p_value_adjusted=0.003,
        bonferroni_multiplier=3,
        n_merges=0,
        branches=(("O'Connor", "D'Angelo"), ("Smith",)),
    )
    root_txt = TreeNode(
        node_id=0, depth=0, parent_id=None, n=100, n_events=(31, 69),
        pd_jeffreys=(0.31, 0.69), pd_final=(0.31, 0.69), class_labels=CLASS_LABELS,
        is_leaf=False, split=split_txt, child_ids=(1, 2), leaf_reason=None,
    )
    l1 = TreeNode(
        node_id=1, depth=1, parent_id=0, n=70, n_events=(7, 63),
        pd_jeffreys=(0.1, 0.9), pd_final=(0.1, 0.9), class_labels=CLASS_LABELS,
        is_leaf=True, split=None, child_ids=(), leaf_reason="max_depth",
    )
    l2 = TreeNode(
        node_id=2, depth=1, parent_id=0, n=30, n_events=(24, 6),
        pd_jeffreys=(0.8, 0.2), pd_final=(0.8, 0.2), class_labels=CLASS_LABELS,
        is_leaf=True, split=None, child_ids=(), leaf_reason="max_depth",
    )
    model_txt = TreeModel(
        root_id=0, nodes=(root_txt, l1, l2), method="CHAID",
        params_fingerprint="fp-quotes", class_labels=CLASS_LABELS,
        target_class=1, target_class_index=0,
    )
    imp_txt = ImputationSpec(means={}, modes={"apellido": "O'Connor"}, fitted_n=100)
    rows_txt = [
        {"apellido": "O'Connor"},
        {"apellido": "D'Angelo"},
        {"apellido": "Smith"},
        {"apellido": "Other"},
        {"apellido": None},
    ]
    sql_txt = export_to_sql(model_txt, imp_txt, unseen_policy="exclude")
    py_txt = _load_python_export(
        export_to_python(model_txt, imp_txt, unseen_policy="exclude")
    )["predict"]
    sql_vals = _eval_sql_in_sqlite(sql_txt, rows_txt, [("apellido", "TEXT")])
    py_vals = [py_txt(r) for r in rows_txt]
    df_txt = pd.DataFrame(
        {"apellido": ["O'Connor", "D'Angelo", "Smith", "Other", "O'Connor"]}
    )
    backend_vals = predict_pd(model_txt, df_txt, unseen_policy="exclude")[:, 0]
    for s_val, p_val, b_val in zip(sql_vals, py_vals, backend_vals):
        _assert_scores_equal(s_val, b_val)
        _assert_scores_equal(p_val, b_val)

    # B) Integer categorical/ordinal split (1, 2, 3) -> numeric literals, no '1' strings
    split_int = SplitConfig(
        predictor="nivel",
        method="CHAID",
        statistic=9.5,
        statistic_name="chi2",
        df=(1,),
        parent_n=100,
        child_ns=(70, 30),
        p_value=0.001,
        p_value_adjusted=0.003,
        bonferroni_multiplier=3,
        n_merges=0,
        branches=((1, 2), (3,)),
    )
    root_int = TreeNode(
        node_id=0, depth=0, parent_id=None, n=100, n_events=(31, 69),
        pd_jeffreys=(0.31, 0.69), pd_final=(0.31, 0.69), class_labels=CLASS_LABELS,
        is_leaf=False, split=split_int, child_ids=(1, 2), leaf_reason=None,
    )
    model_int = TreeModel(
        root_id=0, nodes=(root_int, l1, l2), method="CHAID",
        params_fingerprint="fp-int-cats", class_labels=CLASS_LABELS,
        target_class=1, target_class_index=0,
    )
    imp_int = ImputationSpec(means={}, modes={"nivel": 1}, fitted_n=100)
    sql_int = export_to_sql(model_int, imp_int, unseen_policy="exclude")
    py_int_src = export_to_python(model_int, imp_int, unseen_policy="exclude")
    assert "IN (1, 2)" in sql_int
    assert "IN (3)" in sql_int
    assert "'1'" not in sql_int
    assert "in (1, 2):" in py_int_src
    assert "in (3,):" in py_int_src
    assert "'1'" not in py_int_src

    rows_int = [
        {"nivel": 1},
        {"nivel": 2},
        {"nivel": 3},
        {"nivel": 99},
        {"nivel": None},
        {"nivel": float("nan")},
    ]
    py_int = _load_python_export(py_int_src)["predict"]
    sql_int_vals = _eval_sql_in_sqlite(sql_int, rows_int, [("nivel", "INTEGER")])
    py_int_vals = [py_int(r) for r in rows_int]
    df_int = pd.DataFrame({"nivel": [1, 2, 3, 99, 1, 1]})
    backend_int_vals = predict_pd(model_int, df_int, unseen_policy="exclude")[:, 0]
    for s_val, p_val, b_val in zip(sql_int_vals, py_int_vals, backend_int_vals):
        _assert_scores_equal(s_val, b_val)
        _assert_scores_equal(p_val, b_val)


@pytest.mark.parametrize(
    "col_name",
    ["order", "default", "credit score", 'a"b', "col_{x}"],
)
def test_sqlite_and_python_dangerous_column_names(col_name: str) -> None:
    """SQL reserved words, spaces, quotes and Python braces export and execute safely."""
    split = SplitConfig(
        predictor=col_name,
        method="CHAID",
        statistic=9.0,
        statistic_name="chi2",
        df=(1,),
        parent_n=100,
        child_ns=(60, 40),
        p_value=0.001,
        p_value_adjusted=0.002,
        bonferroni_multiplier=2,
        n_merges=0,
        branches=(("A",), ("B",)),
    )
    root = TreeNode(
        node_id=0, depth=0, parent_id=None, n=100, n_events=(38, 62),
        pd_jeffreys=(0.38, 0.62), pd_final=(0.38, 0.62), class_labels=CLASS_LABELS,
        is_leaf=False, split=split, child_ids=(1, 2), leaf_reason=None,
    )
    l1 = TreeNode(
        node_id=1, depth=1, parent_id=0, n=60, n_events=(6, 54),
        pd_jeffreys=(0.1, 0.9), pd_final=(0.1, 0.9), class_labels=CLASS_LABELS,
        is_leaf=True, split=None, child_ids=(), leaf_reason="max_depth",
    )
    l2 = TreeNode(
        node_id=2, depth=1, parent_id=0, n=40, n_events=(32, 8),
        pd_jeffreys=(0.8, 0.2), pd_final=(0.8, 0.2), class_labels=CLASS_LABELS,
        is_leaf=True, split=None, child_ids=(), leaf_reason="max_depth",
    )
    model = TreeModel(
        root_id=0, nodes=(root, l1, l2), method="CHAID",
        params_fingerprint="fp-danger\ninjection", class_labels=CLASS_LABELS,
        target_class=1, target_class_index=0,
    )
    imputer = ImputationSpec(means={}, modes={col_name: "A"}, fitted_n=100)
    rows = [{col_name: "A"}, {col_name: "B"}, {col_name: "Z"}, {col_name: None}]

    # Mode "exclude": SQLite and Python match predict_pd
    sql_ex = export_to_sql(model, imputer, unseen_policy="exclude")
    assert "\ninjection" not in sql_ex
    py_ex_src = export_to_python(model, imputer, unseen_policy="exclude")
    assert "\ninjection" not in py_ex_src
    py_ex = _load_python_export(py_ex_src)["predict"]
    sql_vals = _eval_sql_in_sqlite(sql_ex, rows, [(col_name, "TEXT")])
    py_vals = [py_ex(r) for r in rows]
    df_eval = pd.DataFrame({col_name: ["A", "B", "Z", "A"]})
    backend_vals = predict_pd(model, df_eval, unseen_policy="exclude")[:, 0]
    for s_val, p_val, b_val in zip(sql_vals, py_vals, backend_vals):
        _assert_scores_equal(s_val, b_val)
        _assert_scores_equal(p_val, b_val)

    # Mode "error": Python compiles cleanly (no f-string breakage) and raises ValueError
    sql_err = export_to_sql(model, imputer, unseen_policy="error")
    assert _eval_sql_in_sqlite(sql_err, [{col_name: "A"}, {col_name: "B"}], [(col_name, "TEXT")]) == [0.1, 0.8]
    py_err = _load_python_export(
        export_to_python(model, imputer, unseen_policy="error")
    )["predict"]
    assert py_err({col_name: "A"}) == 0.1
    assert py_err({col_name: "B"}) == 0.8
    with pytest.raises(ValueError, match="Unseen category in predictor"):
        py_err({col_name: "Z"})


def test_export_fail_fast_non_finite_constants_and_cycles(
    export_case: ExportCase,
) -> None:
    """NaN/Inf in imputation means or leaf pd_final and graph cycles fail fast."""
    from dataclasses import replace

    for bad_val in (float("nan"), float("inf"), float("-inf")):
        bad_imputer = ImputationSpec(means={"edad": bad_val}, modes={}, fitted_n=100)
        with pytest.raises(ValueError, match="non-finite"):
            export_to_sql(export_case.model, bad_imputer)
        with pytest.raises(ValueError, match="non-finite"):
            export_to_python(export_case.model, bad_imputer)

        bad_leaf = replace(export_case.model.nodes[1], pd_final=(bad_val, 0.0))
        bad_nodes = {
            0: export_case.model.nodes[0],
            1: bad_leaf,
            2: export_case.model.nodes[2],
        }

        class _FakeModel:
            root_id = 0
            nodes = bad_nodes
            method = "CRT"
            params_fingerprint = "fp-bad"
            class_labels = CLASS_LABELS

        with pytest.raises(ValueError, match="non-finite"):
            export_to_sql(_FakeModel(), export_case.imputer)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="non-finite"):
            export_to_python(_FakeModel(), export_case.imputer)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="non-finite"):
            export_to_markdown(_FakeModel())  # type: ignore[arg-type]

    # Cycle detection in child_ids
    cyclic_root = replace(export_case.model.nodes[0], child_ids=(0, 2))
    cyclic_nodes = {
        0: cyclic_root,
        1: export_case.model.nodes[1],
        2: export_case.model.nodes[2],
    }

    class _CyclicModel:
        root_id = 0
        nodes = cyclic_nodes
        method = "CRT"
        params_fingerprint = "fp-cycle"
        class_labels = CLASS_LABELS

    with pytest.raises(ValueError, match="cycle detected"):
        export_to_sql(_CyclicModel(), export_case.imputer)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="cycle detected"):
        export_to_python(_CyclicModel(), export_case.imputer)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="cycle detected"):
        export_to_markdown(_CyclicModel())  # type: ignore[arg-type]


def test_export_multiclass_k3_transparency() -> None:
    """K=3 models emit explicit multiclass headers in SQL/Python and full vector in Markdown."""
    labels_k3 = ("Alto", "Medio", "Bajo")
    split = SplitConfig(
        predictor="edad",
        method="CRT",
        statistic=0.05,
        statistic_name="gini_gain",
        df=(),
        parent_n=100,
        child_ns=(60, 40),
        threshold=40.0,
        impurity_gain=0.05,
    )
    root = TreeNode(
        node_id=0, depth=0, parent_id=None, n=100, n_events=(40, 26, 34),
        pd_jeffreys=(0.4, 0.26, 0.34), pd_final=(0.4, 0.26, 0.34),
        class_labels=labels_k3, is_leaf=False, split=split,
        child_ids=(1, 2), leaf_reason=None,
    )
    left = TreeNode(
        node_id=1, depth=1, parent_id=0, n=60, n_events=(36, 18, 6),
        pd_jeffreys=(0.6, 0.3, 0.1), pd_final=(0.6, 0.3, 0.1),
        class_labels=labels_k3, is_leaf=True, split=None,
        child_ids=(), leaf_reason="max_depth",
    )
    right = TreeNode(
        node_id=2, depth=1, parent_id=0, n=40, n_events=(4, 8, 28),
        pd_jeffreys=(0.1, 0.2, 0.7), pd_final=(0.1, 0.2, 0.7),
        class_labels=labels_k3, is_leaf=True, split=None,
        child_ids=(), leaf_reason="max_depth",
    )
    model = TreeModel(
        root_id=0, nodes=(root, left, right), method="CRT",
        params_fingerprint="fp-multiclass-k3", class_labels=labels_k3,
        target_class=0, target_class_index=0,
    )
    imputer = ImputationSpec(means={"edad": 35.0}, modes={}, fitted_n=100)

    sql = export_to_sql(model, imputer)
    sql_lines = sql.splitlines()
    assert sql_lines[2] == (
        "-- Multiclass note (K=3): exports class of interest 'Alto' (index 0); "
        "classes 1..2 omitted"
    )
    assert _eval_sql_in_sqlite(sql, [{"edad": 30.0}, {"edad": 50.0}], [("edad", "REAL")]) == [0.6, 0.1]

    py_src = export_to_python(model, imputer)
    py_lines = py_src.splitlines()
    assert py_lines[2] == (
        "# Multiclass note (K=3): exports class of interest 'Alto' (index 0); "
        "classes 1..2 omitted"
    )
    predict = _load_python_export(py_src)["predict"]
    res_left = predict({"edad": 30.0})
    assert isinstance(res_left, float)
    assert res_left == 0.6
    assert predict({"edad": 50.0}) == 0.1

    md = export_to_markdown(model)
    assert (
        "**Multiclass note (K=3):** primary score is class of interest 'Alto' "
        "(index 0); full class probability vector shown per leaf."
    ) in md
    assert (
        "- **Leaf 1**: Probability (Alto) = 0.6000 | "
        "Vector = (Alto: 0.6000, Medio: 0.3000, Bajo: 0.1000)"
    ) in md
    assert (
        "- **Leaf 2**: Probability (Alto) = 0.1000 | "
        "Vector = (Alto: 0.1000, Medio: 0.2000, Bajo: 0.7000)"
    ) in md
