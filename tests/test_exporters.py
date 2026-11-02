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

from typing import NamedTuple

import pytest

from backend_v3.exporters import (
    export_to_markdown,
    export_to_python,
    export_to_sql,
)
from backend_v3.imputation import ImputationSpec
from backend_v3.tree_builder import TreeModel, TreeNode
from backend_v3.types import PredictorType, SplitConfig, TargetType  # noqa: F401

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
    """One WHEN per consolidated branch; the top branch is the CASE ELSE."""
    case = _merged_chaid_case()
    sql = export_to_sql(case.model, case.imputer)

    # Branch 0 = bins 0+1 (edad <= 20.0), branch 1 = bin 2 (<= 30.0).
    assert "WHEN COALESCE(edad, 35.5) <= 20.0 THEN" in sql
    assert "WHEN COALESCE(edad, 35.5) <= 30.0 THEN" in sql
    # No per-bin predicate may survive: bin_0/bin_1 are not separate arms.
    assert "<= 10.0" not in sql
    # The top consolidated branch covers the residual domain via ELSE.
    assert "ELSE\n 0.9\nEND" in sql
    assert "ELSE NULL" not in sql
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
    sql = export_to_sql(case.model, case.imputer, unseen_policy="majority")
    assert sql.splitlines()[0] == f"-- TreeGov Model Fingerprint: {fp}"
    assert sql.splitlines()[1] == (
        "-- Unseen policy: majority (unseen categories route to the majority "
        "leaf, pd=0.8000)"
    )

    source = export_to_python(case.model, case.imputer, unseen_policy="majority")
    assert source.splitlines()[0] == f"# TreeGov Model Fingerprint: {fp}"
    assert source.splitlines()[1] == (
        "# Unseen policy: majority (unseen categories route to the majority "
        "leaf, pd=0.8000)"
    )

    md = export_to_markdown(case.model, unseen_policy="majority")
    assert (
        "**Unseen policy:** majority (unseen categories route to the majority "
        "leaf, pd=0.8000)."
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

    # Empirical backend parity check: predict_leaf_assignment selects node 2,
    # whose pd_final[0] is 0.8 for this equal-n fixture.
    assert (
        "-- Unseen policy: majority (unseen categories route to the majority "
        "leaf, pd=0.8000)"
    ) in sql
    assert "ELSE 0.8" in sql
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
    assert majority_prediction == 0.8
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
    assert "pd=0.8000" in md
