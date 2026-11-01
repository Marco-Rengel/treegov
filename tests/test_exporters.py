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
