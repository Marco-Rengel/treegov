"""Production exporters for TreeGov models (Phase 4.0).

This module belongs to the clean-room analytical layer (``backend_v3``). It
contains no Qt/PySide6 imports and performs no I/O: it only translates an
already-trained :class:`TreeModel` into source code that can be pasted into a
legacy scoring system.

Design notes (see ``docs/4.0_design_exports.md``):

* The generated SQL is **ANSI SQL** on purpose. The whole decision tree is
  expressed with nested ``CASE WHEN ... THEN ... ELSE ... END`` expressions,
  which every mainstream engine (Oracle, SQL Server, PostgreSQL, SQLite)
  understands. No vendor-specific functions or syntax are emitted.
* Missing values are handled with ``COALESCE``. The imputation statistics come
  from the :class:`ImputationSpec` that was fitted on the training partition,
  never from the scoring partition. Injecting them at export time is what keeps
  the exported rule free of leakage: the production system imputes with the
  exact same constants the model saw during training.
* The model ``params_fingerprint`` is written as a leading comment so an MRM
  auditor can trace a deployed rule back to the exact artefact that produced it.

Invariants (see ``docs/4.0_design_exports.md`` §3):

* Prediction parity: the exported code must return the same ``pd_final`` as the
  backend for the same input rows.
* Zero external dependencies in the generated code.
* The generated code must stay human-readable and auditable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import only for static type checking
    # TODO(zona_gris): the exact module paths of TreeModel/ImputationSpec were
    # not provided in the brief. The imports are guarded by TYPE_CHECKING so the
    # runtime behaviour of this module never depends on them; if a type checker
    # reports them as unresolved, point them at the canonical modules.
    from backend_v3.imputation import ImputationSpec
    from backend_v3.session_state import TreeModel

__all__ = ["export_to_sql"]


def _sql_literal(value: object) -> str:
    """Render a numeric value as a SQL literal without losing precision.

    ``repr`` is used instead of ``str`` so that the exported literal keeps every
    significant digit of the threshold stored in the model. Truncating it would
    silently move rows across a split and break prediction parity.
    """
    return repr(float(value))


def _sql_string(value: object) -> str:
    """Render a text value as a single-quoted ANSI SQL string literal.

    Embedded single quotes are doubled, which is the ANSI standard escape and is
    accepted by every mainstream engine.
    """
    return "'" + str(value).replace("'", "''") + "'"


def _imputed_predictor(split: object, imputer: object) -> str:
    """Return the predictor expression with the training-time imputation baked in.

    The statistics in the :class:`ImputationSpec` were fitted on the training
    partition only. Wrapping the predictor in ``COALESCE`` guarantees that the
    exported rule sees the very same value the model saw during training when a
    row contains a missing value, which is what prevents imputation leakage.
    """
    predictor = split.predictor
    means = getattr(imputer, "means", None) or {}
    modes = getattr(imputer, "modes", None) or {}

    if predictor in means:
        return f"COALESCE({predictor}, {_sql_literal(means[predictor])})"
    if predictor in modes:
        return f"COALESCE({predictor}, {_sql_string(modes[predictor])})"
    return predictor


def _sql_condition(split: object, index: int, imputer: object) -> str:
    """Build the ``WHEN`` predicate for the branch ``index`` of a split.

    Three split encodings are supported, in this priority order:

    * ``threshold``: binary numeric split, branch 0 is ``<=``, branch 1 is ``>``.
    * ``bin_edges``: CHAID continuous split with ``k`` cut points and ``k + 1``
      branches; branch 0 is ``<= edge[0]``, the last one is ``> edge[-1]`` and
      the intermediate ones are ``> edge[i-1] AND <= edge[i]``.
    * ``branches``: categorical split, rendered as ``IN ('a', 'b')``.
    """
    expression = _imputed_predictor(split, imputer)

    if split.threshold is not None:
        threshold = _sql_literal(split.threshold)
        if index == 0:
            return f"{expression} <= {threshold}"
        if index == 1:
            return f"{expression} > {threshold}"
        raise ValueError(
            f"Threshold split on {split.predictor!r} has at most 2 branches, "
            f"got index {index}."
        )

    if split.bin_edges is not None:
        edges = tuple(split.bin_edges)
        if not edges:
            raise ValueError(
                f"Split on {split.predictor!r} declares empty bin_edges."
            )
        if index == 0:
            return f"{expression} <= {_sql_literal(edges[0])}"
        if index == len(edges):
            return f"{expression} > {_sql_literal(edges[-1])}"
        if 1 <= index < len(edges):
            lower = _sql_literal(edges[index - 1])
            upper = _sql_literal(edges[index])
            return f"{expression} > {lower} AND {expression} <= {upper}"
        raise ValueError(
            f"CHAID split on {split.predictor!r} with {len(edges)} edges has "
            f"{len(edges) + 1} branches, got index {index}."
        )

    if split.branches is not None:
        values = tuple(split.branches[index])
        literals = ", ".join(_sql_string(value) for value in values)
        return f"{expression} IN ({literals})"

    raise ValueError(
        f"Split on {split.predictor!r} has neither threshold, bin_edges nor "
        f"branches; it cannot be exported to SQL."
    )


def export_to_sql(model: "TreeModel", imputer: "ImputationSpec") -> str:
    """Export ``model`` as an ANSI SQL expression against ``imputer``.

    The returned statement is a single ``SELECT`` whose projection is a nested
    ``CASE WHEN`` expression ending in ``AS prediction_score``. It is pure ANSI
    SQL: no vendor-specific functions, no CTEs, no temporary tables. The
    ``COALESCE`` calls that wrap every predictor embed the training-time
    imputation statistics, which is what keeps the exported rule free of
    leakage and prediction-parity preserving.

    The first line of the output is a comment carrying
    ``model.params_fingerprint``, so the artefact can be traced back to the
    exact model that generated it (MRM requirement).

    Args:
        model: Trained decision tree. Only ``root_id``, ``nodes`` and
            ``params_fingerprint`` are read; the model is never mutated.
        imputer: Imputation specification fitted on the training partition.
            ``means`` is used for numeric predictors and ``modes`` for
            categorical ones.

    Returns:
        A ready-to-paste SQL statement terminated with a semicolon.

    Raises:
        ValueError: if a split cannot be expressed in ANSI SQL or the tree is
            structurally inconsistent.
        KeyError: if a child references a ``node_id`` absent from ``model.nodes``.
    """
    raw_nodes = model.nodes
    if isinstance(raw_nodes, dict):
        nodes_by_id = dict(raw_nodes)
    else:
        nodes_by_id = {node.node_id: node for node in raw_nodes}

    def _sql_node(node_id: int, indent: int) -> str:
        """Render one node as a SQL fragment, padded by ``indent`` spaces.

        Leaves render as the class-of-interest probability (index 0 of
        ``pd_final``). Internal nodes render as a self-contained ``CASE`` block
        whose branches recurse into the children; unmatched rows fall through to
        ``ELSE NULL`` rather than to an arbitrary branch, so an unexpected input
        is visibly missing instead of silently mis-scored.
        """
        try:
            node = nodes_by_id[node_id]
        except KeyError as exc:
            raise KeyError(
                f"node_id {node_id} is not present in model.nodes."
            ) from exc

        pad = " " * indent

        if node.is_leaf:
            return str(node.pd_final[0])

        split = node.split
        if split is None:
            raise ValueError(
                f"Internal node {node_id} has no SplitConfig; it cannot be exported."
            )

        # TODO(zona_gris): the brief lists node_id/is_leaf/pd_final/split as the
        # TreeNode attributes and then iterates over `child_ids`. Direct access
        # is kept on purpose: a missing attribute must fail loudly instead of
        # silently emitting an empty CASE block.
        child_ids = tuple(node.child_ids)

        lines = ["CASE"]
        for index, child_id in enumerate(child_ids):
            condition = _sql_condition(split, index, imputer)
            child_sql = _sql_node(child_id, indent + 1)
            lines.append(f"{pad}WHEN {condition} THEN")
            lines.append(f"{pad} {child_sql}")
        lines.append(f"{pad}ELSE NULL")
        lines.append(f"{pad}END")
        return "\n".join(lines)

    body = _sql_node(model.root_id, 0)
    return (
        f"-- TreeGov Model Fingerprint: {model.params_fingerprint}\n"
        f"SELECT {body} AS prediction_score;"
    )
