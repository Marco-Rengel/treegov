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

import math
import numbers

from backend_v3.imputation import ImputationSpec
from backend_v3.tree_builder import TreeModel
from backend_v3.validation import select_majority_leaf

__all__ = ["export_to_markdown", "export_to_python", "export_to_sql"]


def _ensure_unseen_policy(unseen_policy: str) -> None:
    """Validate the governed ``unseen_policy`` vocabulary.

    The vocabulary mirrors the backend parameter of the same name in
    ``backend_v3.validation.predict_leaf_assignment`` (design_decisions.md §7.6):
    ``"error"``, ``"exclude"`` and ``"majority"``. Anything else raises
    ``ValueError`` naming the three admissible values. All three policies are
    implemented in sub-phase 4.0.1.b of
    ``docs/4.0.1_design_categorical_exporters.md``.
    """
    if unseen_policy not in ("error", "exclude", "majority"):
        raise ValueError(
            f"[exporters] unseen_policy invalida: {unseen_policy!r} "
            "(valores admitidos: 'error', 'exclude', 'majority')"
        )


def _validate_finite_float(value: object, context: str) -> float:
    """Convert ``value`` to a finite builtin float, rejecting booleans."""
    if isinstance(value, bool) or type(value).__name__ == "bool_":
        raise ValueError(
            f"[exporters] boolean value {value!r} is not valid for {context}."
        )
    num = float(value)
    if not math.isfinite(num):
        raise ValueError(
            f"[exporters] non-finite numeric value {value!r} for {context}."
        )
    return num


def _is_numeric_scalar(value: object) -> bool:
    """Return True for real numeric scalars (int/float/numpy scalars), excluding bool."""
    return isinstance(value, numbers.Real) and not isinstance(value, bool)


def _sql_ident(name: str) -> str:
    """Quote a column identifier using ANSI SQL double quotes."""
    return '"' + str(name).replace('"', '""') + '"'


def _sanitize_comment(text: object) -> str:
    """Replace CR/LF with spaces so single-line comments cannot be broken."""
    return str(text).replace("\r", " ").replace("\n", " ")


def _sql_literal(value: object) -> str:
    """Render a numeric value as a SQL literal without losing precision.

    ``repr`` is used instead of ``str`` so that the exported literal keeps every
    significant digit of the threshold stored in the model. Truncating it would
    silently move rows across a split and break prediction parity.
    """
    return repr(_validate_finite_float(value, "SQL numeric literal"))


def _sql_string(value: object) -> str:
    """Render a text value as a single-quoted ANSI SQL string literal.

    Embedded single quotes are doubled, which is the ANSI standard escape and is
    accepted by every mainstream engine.
    """
    return "'" + str(value).replace("'", "''") + "'"


def _sql_value(value: object) -> str:
    """Render a categorical or mode value preserving numeric vs. text type."""
    if isinstance(value, numbers.Integral) and not isinstance(value, bool):
        return str(int(value))
    if _is_numeric_scalar(value):
        return _sql_literal(value)
    return _sql_string(value)


def _imputed_predictor(split: object, imputer: object) -> str:
    """Return the predictor expression with the training-time imputation baked in.

    The statistics in the :class:`ImputationSpec` were fitted on the training
    partition only. Wrapping the predictor in ``COALESCE`` guarantees that the
    exported rule sees the very same value the model saw during training when a
    row contains a missing value, which is what prevents imputation leakage.
    """
    predictor = split.predictor
    col_sql = _sql_ident(predictor)
    means = getattr(imputer, "means", None) or {}
    modes = getattr(imputer, "modes", None) or {}

    if predictor in means:
        return f"COALESCE({col_sql}, {_sql_literal(means[predictor])})"
    if predictor in modes:
        return f"COALESCE({col_sql}, {_sql_value(modes[predictor])})"
    return col_sql


def _merged_bin_branches(split: object) -> list[tuple[int, int]] | None:
    """Return ``(min_bin, max_bin)`` per branch of a CHAID continuous split.

    Applies only when ``bin_edges`` and ``branches`` are both populated;
    returns ``None`` otherwise, so callers fall back to the legacy unmerged
    bin-per-branch encoding.

    The engine labels bins ``"bin_i"`` (``chaid_engine``
    ``_reduce_continuous_predictor``) and merges only ADJACENT groups (bins
    are ORDINAL, ``chaid_engine.py:234-237``; design_decisions.md §16.1), so
    every branch is a contiguous bin interval and the branches partition
    bins ``0..len(edges)`` in order. Export conditions are therefore built
    per consolidated branch, mirroring the branch-based routing of
    ``tree_builder._partition`` (design_decisions.md §16.3) instead of one
    condition per individual bin (H-5.0.c-1).

    Raises:
        ValueError: if the branches are not an ordered, contiguous and
            exhaustive partition of the bins (structurally inconsistent
            model): silently exporting a different routing is worse than
            failing loudly.
    """
    if not split.bin_edges or not split.branches:
        return None
    n_edges = len(split.bin_edges)
    bounds: list[tuple[int, int]] = []
    expected = 0
    for group in split.branches:
        bins = sorted(int(str(label).split("_")[1]) for label in group)
        if bins[0] != expected or bins[-1] > n_edges:
            raise ValueError(
                f"CHAID split on {split.predictor!r}: bin branches do not "
                "form an ordered partition of the bins; the model is "
                "inconsistent (design_decisions.md §16.1/§16.3)."
            )
        if bins != list(range(bins[0], bins[-1] + 1)):
            raise ValueError(
                f"CHAID split on {split.predictor!r}: non-contiguous bin "
                "branch; the engine only merges adjacent bins "
                "(design_decisions.md §16.1)."
            )
        bounds.append((bins[0], bins[-1]))
        expected = bins[-1] + 1
    if expected != n_edges + 1:
        raise ValueError(
            f"CHAID split on {split.predictor!r}: bin branches do not cover "
            "all bins; the model is inconsistent."
        )
    return bounds


def _majority_leaf_pd(model: "TreeModel") -> float:
    """Return the majority-leaf PD for ``unseen_policy="majority"``.

    Delegates directly to :func:`backend_v3.validation.select_majority_leaf`
    (maximum physical ``n``, tie-break by minimum ``node_id``) and validates
    that ``pd_final[0]`` (class of interest, index 0) is a finite float.

    The choice is model-wide on purpose: a sub-tree export (``node_id``) keeps
    the same fallback constant as the full export (Phase 3.12.a). Redefining
    the majority leaf per segment would silently change the governed
    ``unseen_policy`` semantics.
    """
    destino = select_majority_leaf(model)
    return _validate_finite_float(
        destino.pd_final[0], f"majority leaf {destino.node_id} pd_final[0]"
    )


def _sql_condition(split: object, index: int, imputer: object) -> str:
    """Build the ``WHEN`` predicate for the branch ``index`` of a split.

    Three split encodings are supported, in this priority order:

    * ``threshold``: binary numeric split, branch 0 is ``<=``, branch 1 is ``>``.
    * ``bin_edges``: CHAID continuous split. With consolidated ``branches``
      (the general case; only adjacent bins merge, design_decisions.md
      §16.1) each branch is rendered from its own bin interval —
      ``<= edge[hi]``, or ``> edge[lo-1]`` for the top branch — mirroring
      the branch-based routing of ``tree_builder._partition`` (§16.3).
      Without ``branches`` (legacy encoding) one predicate per bin is
      emitted: branch 0 is ``<= edge[0]``, the last one is ``> edge[-1]``
      and the intermediate ones are ``> edge[i-1] AND <= edge[i]``.
    * ``branches``: categorical split, rendered as ``IN (...)`` preserving
      numeric vs. text scalar types.
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

    if split.bin_edges:
        edges = tuple(split.bin_edges)
        merged = _merged_bin_branches(split)
        if merged is not None:
            # CHAID continuo con ramas fusionadas (H-5.0.c-1): una condicion
            # por RAMA consolidada, no por bin individual.
            lo, hi = merged[index]
            if hi == len(edges):
                if lo == 0:
                    raise ValueError(
                        f"CHAID split on {split.predictor!r}: merged top "
                        "branch starts at bin 0 and has no lower boundary."
                    )
                # Rama superior (sin corte por encima): predicado explicito >
                # para que NULL/faltantes sin imputacion caigan en ELSE.
                return f"{expression} > {_sql_literal(edges[lo - 1])}"
            return f"{expression} <= {_sql_literal(edges[hi])}"
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
        literals = ", ".join(_sql_value(value) for value in values)
        return f"{expression} IN ({literals})"

    raise ValueError(
        f"Split on {split.predictor!r} has neither threshold, bin_edges nor "
        f"branches; it cannot be exported to SQL."
    )


def export_to_sql(
    model: TreeModel,
    imputer: ImputationSpec,
    *,
    unseen_policy: str = "exclude",
    node_id: int | None = None,
) -> str:
    """Export ``model`` as an ANSI SQL expression against ``imputer``.

    The returned statement is a single ``SELECT`` whose projection is a nested
    ``CASE WHEN`` expression ending in ``AS prediction_score``. It is pure ANSI
    SQL: no vendor-specific functions, no CTEs, no temporary tables. The
    ``COALESCE`` calls that wrap every predictor embed the training-time
    imputation statistics, which is what keeps the exported rule free of
    leakage and prediction-parity preserving.

    The first line of the output is a comment carrying
    ``model.params_fingerprint``, so the artefact can be traced back to the
    exact model that generated it (MRM requirement). The following lines
    declare the ``unseen_policy`` in force and, for ``"error"``, its database
    portability warning. Under ``"exclude"``, an unseen category returns
    ``NULL``; under ``"majority"``, it receives the majority leaf's PD.

    In SQL mode ``"error"``, ``ELSE 1/0`` makes PostgreSQL, SQL Server and
    Oracle abort the query. MySQL and SQLite instead return ``NULL`` with a
    warning, so the receiver must filter those rows explicitly.

    Node traversal reads ``node.child_ids`` directly instead of iterating over
    a pre-declared attribute list: a node missing that attribute raises
    ``AttributeError`` at export time. This is deliberate (fail-loud): an
    incomplete node must abort the export rather than silently emitting an
    empty ``CASE`` block that would mis-score rows at scoring time.

    Args:
        model: Trained decision tree. Only ``root_id``, ``nodes`` and
            ``params_fingerprint`` are read; the model is never mutated.
        imputer: Imputation specification fitted on the training partition.
            ``means`` is used for numeric predictors and ``modes`` for
            categorical ones.
        unseen_policy: Behavior for rows carrying unseen categorical values.
            ``"exclude"`` (default) falls through to ``ELSE NULL`` and leaves
            the row unscored. ``"error"`` uses ``ELSE 1/0`` to abort scoring
            on strict databases, subject to the portability caveat above.
            ``"majority"`` returns the PD of the leaf with maximum physical
            ``n``, breaking ties by minimum ``node_id``.
        node_id: Node that becomes the root of the exported rule. ``None``
            (default) exports the whole tree from ``model.root_id``, keeping
            the Phase 4.0 output byte-for-byte. Any other value exports only
            that node and its descendants. The emitted ``CASE`` block does
            **not** carry the path condition that reaches the node, so the
            caller is responsible for applying that filter upstream.

    Returns:
        A ready-to-paste SQL statement terminated with a semicolon.

    Raises:
        ValueError: if a split cannot be expressed in ANSI SQL or the tree is
            structurally inconsistent.
        KeyError: if a child references a ``node_id`` absent from
            ``model.nodes``, or if ``node_id`` itself is not present.
    """
    _ensure_unseen_policy(unseen_policy)
    majority_pd = _majority_leaf_pd(model) if unseen_policy == "majority" else None
    nodes_by_id = _index_nodes(model)

    def _sql_node(node_id: int, indent: int, visiting: frozenset[int]) -> str:
        """Render one node as a SQL fragment, padded by ``indent`` spaces.

        Leaves render as the class-of-interest probability (index 0 of
        ``pd_final``). Internal nodes render as a self-contained ``CASE`` block
        whose branches recurse into the children. The residual branch returns
        ``NULL``, raises via division by zero, or returns the majority-leaf PD
        according to ``unseen_policy``; it never routes to an arbitrary child.
        """
        if node_id in visiting:
            raise ValueError(
                f"[exporters] cycle detected in SQL export at node_id {node_id}."
            )
        try:
            node = nodes_by_id[node_id]
        except KeyError as exc:
            raise KeyError(
                f"node_id {node_id} is not present in model.nodes."
            ) from exc

        pad = " " * indent

        if node.is_leaf:
            return _sql_literal(node.pd_final[0])

        split = node.split
        if split is None:
            raise ValueError(
                f"Internal node {node_id} has no SplitConfig; it cannot be exported."
            )

        child_ids = tuple(node.child_ids)
        # Design D4 (docs/4.0.1_design_categorical_exporters.md): one branch
        # value set per child. A split-tuple geometry mismatch must abort the
        # export with a clear ValueError here rather than surface later as an
        # uninformative IndexError inside _sql_condition.
        if split.branches is not None and len(split.branches) != len(child_ids):
            raise ValueError(
                f"Categorical split on {split.predictor!r} needs exactly one "
                f"branch value set per child ({len(child_ids)} children), got "
                f"{len(split.branches)} value sets."
            )

        merged = _merged_bin_branches(split)
        if merged is not None and len(child_ids) != len(merged):
            raise ValueError(
                f"CHAID split on {split.predictor!r} has {len(merged)} "
                f"consolidated branches, got {len(child_ids)} children."
            )

        next_visiting = visiting | {node_id}
        lines = ["CASE"]
        for index, child_id in enumerate(child_ids):
            child_sql = _sql_node(child_id, indent + 1, next_visiting)
            condition = _sql_condition(split, index, imputer)
            lines.append(f"{pad}WHEN {condition} THEN")
            lines.append(f"{pad} {child_sql}")
        if unseen_policy == "error":
            lines.append(
                f"{pad}-- WARNING: unseen category in predictor "
                f"{_sanitize_comment(repr(split.predictor))} -> division by zero"
            )
            lines.append(f"{pad}ELSE 1/0")
        elif unseen_policy == "majority":
            lines.append(f"{pad}ELSE {_sql_literal(majority_pd)}")
        else:
            lines.append(f"{pad}ELSE NULL")
        lines.append(f"{pad}END")
        return "\n".join(lines)

    body = _sql_node(model.root_id if node_id is None else node_id, 0, frozenset())
    if unseen_policy == "error":
        policy_header = (
            "-- Unseen policy: error (unseen categories abort the scoring)\n"
            "-- WARNING: one or more predictors below use ELSE 1/0; query MUST "
            "fail on strict DBs (PostgreSQL/Oracle/SQL Server) and returns NULL "
            "with warning on permissive DBs (MySQL/SQLite)"
        )
    elif unseen_policy == "majority":
        policy_header = (
            "-- Unseen policy: majority (unseen categories route to the majority "
            f"leaf, pd={majority_pd:.4f})"
        )
    else:
        policy_header = (
            "-- Unseen policy: exclude (unseen categories return NULL; caller must filter)"
        )
    class_labels = tuple(getattr(model, "class_labels", ()))
    header_lines = [
        f"-- TreeGov Model Fingerprint: {_sanitize_comment(model.params_fingerprint)}",
        policy_header,
    ]
    if len(class_labels) > 2:
        k_classes = len(class_labels)
        label_0 = _sanitize_comment(repr(class_labels[0]))
        header_lines.append(
            f"-- Multiclass note (K={k_classes}): exports class of interest "
            f"{label_0} (index 0); classes 1..{k_classes - 1} omitted"
        )
    header_lines.append(f"SELECT {body} AS prediction_score;")
    return "\n".join(header_lines)


# --------------------------------------------------------------------------- #
# Python exporter
# --------------------------------------------------------------------------- #


def _index_nodes(model: "TreeModel") -> dict:
    """Index ``model.nodes`` by ``node_id``.

    The public contract exposes ``nodes`` as a tuple, but a mapping keyed by
    ``node_id`` is also accepted so the exporter keeps working if the session
    state is serialised as a dict. Nothing is assumed about the position of a
    node inside the sequence: the ``node_id`` attribute is the only key used.
    """
    raw_nodes = model.nodes
    if isinstance(raw_nodes, dict):
        return dict(raw_nodes)
    return {node.node_id: node for node in raw_nodes}


def _python_variable(predictor: str) -> str:
    """Derive a valid Python identifier for a predictor column.

    Column names may contain spaces, accents, dashes or leading digits, none of
    which are legal in a Python identifier. Every other character is replaced by
    an underscore and a leading underscore is added when the result would start
    with a digit. The mapping is deterministic, which keeps the generated script
    stable across exports of the same model.
    """
    cleaned = "".join(
        char if (char.isalnum() or char == "_") else "_" for char in predictor
    )
    if not cleaned or cleaned[0].isdigit():
        cleaned = "_" + cleaned
    return "val_" + cleaned


def _python_number(value: object) -> str:
    """Render a numeric value as a Python literal without losing precision.

    ``float`` is applied first so numpy scalars are converted to builtin floats:
    ``repr`` on a ``numpy.float64`` would emit ``np.float64(0.1)`` and the
    exported script must stay free of third-party dependencies.
    """
    return repr(_validate_finite_float(value, "Python numeric literal"))


def _python_literal(value: object) -> str:
    """Render a categorical or mode value preserving numeric vs. text type."""
    if isinstance(value, numbers.Integral) and not isinstance(value, bool):
        return repr(int(value))
    if _is_numeric_scalar(value):
        return _python_number(value)
    return repr(str(value))


def _python_tuple(values: object) -> str:
    """Render a tuple of category values as a Python tuple literal.

    Preserves integer/real types for numeric categories and quotes text values
    via ``repr``. A single element keeps its trailing comma so the literal
    stays a tuple instead of collapsing into a parenthesised scalar.
    """
    items = [_python_literal(value) for value in values]
    if len(items) == 1:
        return "(" + items[0] + ",)"
    return "(" + ", ".join(items) + ")"


def _python_imputation(predictor: str, variable: str, imputer: object) -> list:
    """Build the ``row.get`` lines that impute one predictor.

    The constants come from the :class:`ImputationSpec` fitted on the training
    partition, so the exported script imputes with exactly the values the model
    saw during training. This is the same anti-leakage guarantee that
    ``COALESCE`` provides in the SQL exporter.

    The returned lines are relative to the body of ``_eval_tree``; the caller
    adds the base indentation.

    The guard checks both ``None`` and ``NaN`` (via ``val != val``, zero
    imports, works for builtin ``float('nan')`` and ``numpy.nan``) so both
    exporters treat missing values identically.
    """
    means = getattr(imputer, "means", None) or {}
    modes = getattr(imputer, "modes", None) or {}
    key = repr(predictor)

    if predictor in means:
        default = _python_number(means[predictor])
    elif predictor in modes:
        default = _python_literal(modes[predictor])
    else:
        return [f"{variable} = row.get({key})"]

    return [
        f"{variable} = row.get({key}, {default})",
        f"if {variable} is None or {variable} != {variable}:",
        f"    {variable} = {default}",
    ]


def _python_predictors(root_id: int, nodes_by_id: dict) -> list:
    """List the predictors used by the tree, in depth-first appearance order.

    Only columns that actually appear in a split are collected, so the exported
    script never contains dead imputation lines. The traversal is iterative and
    left-to-right, which makes the emitted order deterministic.
    """
    ordered = []
    seen = set()
    visited: set[int] = set()
    stack = [root_id]

    while stack:
        node_id = stack.pop()
        if node_id in visited:
            raise ValueError(
                f"[exporters] cycle detected in Python export at node_id {node_id}."
            )
        visited.add(node_id)
        try:
            node = nodes_by_id[node_id]
        except KeyError as exc:
            raise KeyError(
                f"node_id {node_id} is not present in model.nodes."
            ) from exc

        if node.is_leaf:
            continue

        split = node.split
        if split is None:
            raise ValueError(
                f"Internal node {node_id} has no SplitConfig; it cannot be exported."
            )

        if split.predictor not in seen:
            seen.add(split.predictor)
            ordered.append(split.predictor)

        stack.extend(reversed(tuple(node.child_ids)))

    return ordered


def _python_unseen_fallback(
    pad: str,
    predictor: str,
    variable: str,
    *,
    unseen_policy: str,
    majority_pd: float | None,
    reason: str,
) -> list[str]:
    """Emit the policy-governed fallback statement without f-string interpolation."""
    if unseen_policy == "error":
        prefix_lit = repr(f"{reason} in predictor {str(predictor)!r}: ")
        return [f"{pad}raise ValueError({prefix_lit} + repr({variable}))"]
    if unseen_policy == "majority":
        assert majority_pd is not None
        return [f"{pad}return {_python_number(majority_pd)}"]
    return [f"{pad}return None"]


def _python_node(
    node_id: int,
    depth: int,
    nodes_by_id: dict,
    *,
    unseen_policy: str,
    majority_pd: float | None,
    visiting: frozenset[int] = frozenset(),
) -> list:
    """Render one node as a list of Python source lines indented by ``depth``.

    ``depth`` counts indentation levels of four spaces, so the generated script
    always keeps strict Python indentation. Leaves emit ``return`` with the
    class-of-interest probability (index 0 of ``pd_final``); internal nodes emit
    an ``if`` / ``elif`` / ``else`` chain whose arms recurse into the children.
    Missing/NaN numeric values (when not imputed) and unseen categorical values
    apply ``unseen_policy`` identically to the backend.
    """
    if node_id in visiting:
        raise ValueError(
            f"[exporters] cycle detected in Python export at node_id {node_id}."
        )
    pad = "    " * depth

    try:
        node = nodes_by_id[node_id]
    except KeyError as exc:
        raise KeyError(
            f"node_id {node_id} is not present in model.nodes."
        ) from exc

    if node.is_leaf:
        return [f"{pad}return {_python_number(node.pd_final[0])}"]

    split = node.split
    if split is None:
        raise ValueError(
            f"Internal node {node_id} has no SplitConfig; it cannot be exported."
        )

    variable = _python_variable(split.predictor)
    child_ids = tuple(node.child_ids)
    next_visiting = visiting | {node_id}

    if len(child_ids) < 2:
        raise ValueError(
            f"Internal node {node_id} must have at least 2 children, "
            f"got {len(child_ids)}."
        )

    if split.threshold is not None:
        if len(child_ids) != 2:
            raise ValueError(
                f"Threshold split on {split.predictor!r} has exactly 2 branches, "
                f"got {len(child_ids)} children."
            )
        lines = [f"{pad}if {variable} is None or {variable} != {variable}:"]
        lines.extend(
            _python_unseen_fallback(
                pad + "    ",
                split.predictor,
                variable,
                unseen_policy=unseen_policy,
                majority_pd=majority_pd,
                reason="Missing value",
            )
        )
        lines.append(f"{pad}if {variable} <= {_python_number(split.threshold)}:")
        lines.extend(
            _python_node(
                child_ids[0],
                depth + 1,
                nodes_by_id,
                unseen_policy=unseen_policy,
                majority_pd=majority_pd,
                visiting=next_visiting,
            )
        )
        lines.append(f"{pad}else:")
        lines.extend(
            _python_node(
                child_ids[1],
                depth + 1,
                nodes_by_id,
                unseen_policy=unseen_policy,
                majority_pd=majority_pd,
                visiting=next_visiting,
            )
        )
        return lines

    if split.bin_edges:
        edges = tuple(split.bin_edges)
        merged = _merged_bin_branches(split)
        if merged is not None:
            # CHAID continuo con ramas fusionadas (H-5.0.c-1): if/elif por
            # corte superior de cada RAMA consolidada; la rama que contiene
            # el bin superior es el else residual (tras proteger None/NaN).
            if len(child_ids) != len(merged):
                raise ValueError(
                    f"CHAID split on {split.predictor!r} has {len(merged)} "
                    f"consolidated branches, got {len(child_ids)} children."
                )
            lines = [f"{pad}if {variable} is None or {variable} != {variable}:"]
            lines.extend(
                _python_unseen_fallback(
                    pad + "    ",
                    split.predictor,
                    variable,
                    unseen_policy=unseen_policy,
                    majority_pd=majority_pd,
                    reason="Missing value",
                )
            )
            for index, (_lo, hi) in enumerate(merged):
                if hi == len(edges):
                    lines.append(f"{pad}else:")
                else:
                    keyword = "if" if index == 0 else "elif"
                    lines.append(
                        f"{pad}{keyword} {variable} <= {_python_number(edges[hi])}:"
                    )
                lines.extend(
                    _python_node(
                        child_ids[index],
                        depth + 1,
                        nodes_by_id,
                        unseen_policy=unseen_policy,
                        majority_pd=majority_pd,
                        visiting=next_visiting,
                    )
                )
            return lines
        if len(child_ids) != len(edges) + 1:
            raise ValueError(
                f"CHAID split on {split.predictor!r} with {len(edges)} edges needs "
                f"{len(edges) + 1} children, got {len(child_ids)}."
            )
        lines = [f"{pad}if {variable} is None or {variable} != {variable}:"]
        lines.extend(
            _python_unseen_fallback(
                pad + "    ",
                split.predictor,
                variable,
                unseen_policy=unseen_policy,
                majority_pd=majority_pd,
                reason="Missing value",
            )
        )
        for index, edge in enumerate(edges):
            keyword = "if" if index == 0 else "elif"
            lines.append(f"{pad}{keyword} {variable} <= {_python_number(edge)}:")
            lines.extend(
                _python_node(
                    child_ids[index],
                    depth + 1,
                    nodes_by_id,
                    unseen_policy=unseen_policy,
                    majority_pd=majority_pd,
                    visiting=next_visiting,
                )
            )
        lines.append(f"{pad}else:")
        lines.extend(
            _python_node(
                child_ids[-1],
                depth + 1,
                nodes_by_id,
                unseen_policy=unseen_policy,
                majority_pd=majority_pd,
                visiting=next_visiting,
            )
        )
        return lines

    if split.branches is not None:
        branch_values = tuple(split.branches)
        if len(branch_values) != len(child_ids):
            raise ValueError(
                f"Categorical split on {split.predictor!r} needs exactly one "
                f"branch value set per child ({len(child_ids)} children), got "
                f"{len(branch_values)} value sets."
            )
        lines = []
        for index in range(len(child_ids)):
            keyword = "if" if index == 0 else "elif"
            values = _python_tuple(branch_values[index])
            lines.append(f"{pad}{keyword} {variable} in {values}:")
            lines.extend(
                _python_node(
                    child_ids[index],
                    depth + 1,
                    nodes_by_id,
                    unseen_policy=unseen_policy,
                    majority_pd=majority_pd,
                    visiting=next_visiting,
                )
            )
        # An unseen categorical value matches no branch set; apply the same
        # residual policy as the backend and the other scoring exporters.
        lines.append(f"{pad}else:")
        lines.extend(
            _python_unseen_fallback(
                pad + "    ",
                split.predictor,
                variable,
                unseen_policy=unseen_policy,
                majority_pd=majority_pd,
                reason="Unseen category",
            )
        )
        return lines

    raise ValueError(
        f"Split on {split.predictor!r} has neither threshold, bin_edges nor "
        f"branches; it cannot be exported to Python."
    )


def export_to_python(
    model: TreeModel,
    imputer: ImputationSpec,
    *,
    unseen_policy: str = "exclude",
    node_id: int | None = None,
) -> str:
    """Export ``model`` as a self-contained, dependency-free Python script.

    The generated module contains exactly two functions: ``predict(row)``, the
    public entry point, and ``_eval_tree(row)``, which holds the unrolled tree
    and the imputation constants. Only the standard library is used (``dict.get``
    and builtin floats), so the file can be pasted into a legacy scoring system
    that has no numpy or pandas installed.

    The imputation assignments are emitted inside ``_eval_tree`` rather than in
    ``predict``: ``predict`` is a thin wrapper, and a local variable created in
    one function is not visible in another, so placing them in ``predict`` would
    make the generated script raise ``NameError`` on the first split. The
    constants still come from the training-time :class:`ImputationSpec`, which
    preserves the anti-leakage guarantee.

    The first line is a comment carrying ``model.params_fingerprint`` so the
    artefact can be traced back to the model that generated it (MRM). The
    second line declares the ``unseen_policy`` in force. Under ``"exclude"``,
    an unseen category returns ``None``; under ``"majority"``, it receives the
    majority leaf's PD. Under ``"error"``, the row aborts with ``ValueError``
    identifying both the predictor and the unseen value, and the generated
    functions return ``float`` rather than ``float | None``.

    Args:
        model: Trained decision tree. ``root_id``, ``nodes`` and
            ``params_fingerprint`` are read; the model is never mutated.
        imputer: Imputation specification fitted on the training partition.
        unseen_policy: Behavior for rows carrying unseen categorical values.
            ``"exclude"`` (default) returns ``None`` from the categorical
            fallback. ``"error"`` aborts the row with ``ValueError`` naming
            the predictor and value. ``"majority"`` returns the PD of the leaf
            with maximum physical ``n``, breaking ties by minimum ``node_id``.
        node_id: Node that becomes the root of the exported rule. ``None``
            (default) exports the whole tree from ``model.root_id``, keeping
            the Phase 4.0 output byte-for-byte. Any other value exports only
            that node and its descendants: only the predictors used inside
            that sub-tree get imputation lines. The emitted ``if`` chain does
            **not** carry the path condition that reaches the node, so the
            caller is responsible for applying that filter upstream.

    Returns:
        The source of a Python module, terminated by a newline. Under
        ``"exclude"``, ``predict``/``_eval_tree`` are declared as
        ``float | None``; under ``"error"`` and ``"majority"``, as ``float``.

    Raises:
        ValueError: if a split cannot be expressed as an ``if`` chain, or the
            tree is structurally inconsistent.
        KeyError: if a child references a ``node_id`` absent from
            ``model.nodes``, or if ``node_id`` itself is not present.
    """
    _ensure_unseen_policy(unseen_policy)
    nodes_by_id = _index_nodes(model)
    root = model.root_id if node_id is None else node_id
    predictors = _python_predictors(root, nodes_by_id)

    variables = {}
    for predictor in predictors:
        variable = _python_variable(predictor)
        for other, taken in variables.items():
            if taken == variable:
                raise ValueError(
                    f"Predictors {other!r} and {predictor!r} both map to the "
                    f"variable {variable!r}; rename one of them before exporting."
                )
        variables[predictor] = variable

    majority_pd = _majority_leaf_pd(model) if unseen_policy == "majority" else None
    if unseen_policy == "error":
        policy_header = (
            "# Unseen policy: error (unseen categories raise ValueError; caller sees the exception)"
        )
    elif unseen_policy == "majority":
        policy_header = (
            "# Unseen policy: majority (unseen categories route to the majority "
            f"leaf, pd={majority_pd:.4f})"
        )
    else:
        policy_header = (
            "# Unseen policy: exclude (unseen categories return None; caller must filter)"
        )
    return_type = "float | None" if unseen_policy == "exclude" else "float"

    class_labels = tuple(getattr(model, "class_labels", ()))
    lines = [
        f"# TreeGov Model Fingerprint: {_sanitize_comment(model.params_fingerprint)}",
        policy_header,
    ]
    if len(class_labels) > 2:
        k_classes = len(class_labels)
        label_0 = _sanitize_comment(repr(class_labels[0]))
        lines.append(
            f"# Multiclass note (K={k_classes}): exports class of interest "
            f"{label_0} (index 0); classes 1..{k_classes - 1} omitted"
        )
    lines.extend([
        "",
        f"def predict(row: dict) -> {return_type}:",
        "    return _eval_tree(row)",
        "",
        "",
        f"def _eval_tree(row: dict) -> {return_type}:",
    ])

    for predictor in predictors:
        for line in _python_imputation(predictor, variables[predictor], imputer):
            lines.append("    " + line)

    lines.extend(
        _python_node(
            root,
            1,
            nodes_by_id,
            unseen_policy=unseen_policy,
            majority_pd=majority_pd,
        )
    )

    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Markdown exporter
# --------------------------------------------------------------------------- #


def export_to_markdown(
    model: TreeModel,
    *,
    unseen_policy: str = "exclude",
    node_id: int | None = None,
) -> str:
    """Export ``model`` as a human-readable Markdown report.

    The report reproduces the tree structure as nested bullet points: every
    internal node states the predictor it splits on, and every leaf states the
    class-of-interest probability (index 0 of ``pd_final``, rendered with four
    decimals). Its purpose is documentation and audit review, not machine
    consumption: prediction parity is guaranteed by :func:`export_to_sql` and
    :func:`export_to_python`, while this exporter only renders what is already
    stored in the model.

    The header carries ``model.params_fingerprint``, ``model.method`` and the
    ``unseen_policy`` in force, so a reviewer can trace the report back to the
    exact artefact that produced it (MRM requirement). Categorical splits list
    one sub-bullet per branch value set and close with a residual ``Else``
    bullet that changes by mode: exclusion, a raised ``ValueError``, or routing
    to the majority leaf with its PD.

    The module performs no I/O: the return value is a plain ``str`` the caller
    is free to write to disk or embed elsewhere.

    Args:
        model: Trained decision tree. ``root_id``, ``method``, ``nodes`` and
            ``params_fingerprint`` are read; the model is never mutated.
        unseen_policy: Governs how the report labels rows carrying unseen
            categorical values. ``"exclude"`` (default) renders the residual
            bullet as "not scored"; ``"error"`` labels the raised
            ``ValueError``; ``"majority"`` labels routing to the majority leaf
            and includes its PD with four decimals.
        node_id: Node that becomes the root of the rendered sub-tree. ``None``
            (default) renders the whole tree from ``model.root_id``, keeping
            the Phase 4.0 output byte-for-byte. Any other value renders only
            that node and its descendants. The rendered section does **not**
            carry the path condition that reaches the node, so a reader must
            be told which segment the report covers.

    Returns:
        A Markdown document terminated by a newline.

    Raises:
        ValueError: if the tree is structurally inconsistent (an internal node
            without ``SplitConfig``, fewer than two children, or a branch count
            that does not match the split encoding).
        KeyError: if a child references a ``node_id`` absent from
            ``model.nodes``, or if ``node_id`` itself is not present.
    """
    _ensure_unseen_policy(unseen_policy)
    majority_pd = _majority_leaf_pd(model) if unseen_policy == "majority" else None
    nodes_by_id = _index_nodes(model)
    class_labels = tuple(getattr(model, "class_labels", ()))
    is_multiclass = len(class_labels) > 2

    def _md_node(node_id: int, depth: int, visiting: frozenset[int]) -> str:
        """Render one node and its descendants as a nested Markdown list.

        ``depth`` counts indentation levels of two spaces. Leaves render as a
        single bullet with the leaf probability (and the full class vector when
        ``K > 2``); internal nodes render as a bullet naming the split
        predictor followed by one indented sub-bullet per branch, whose bodies
        recurse into the children.
        """
        if node_id in visiting:
            raise ValueError(
                f"[exporters] cycle detected in Markdown export at node_id {node_id}."
            )
        try:
            node = nodes_by_id[node_id]
        except KeyError as exc:
            raise KeyError(
                f"node_id {node_id} is not present in model.nodes."
            ) from exc

        indent = "  " * depth

        if node.is_leaf:
            pd_0 = _validate_finite_float(
                node.pd_final[0], f"leaf {node.node_id} pd_final[0]"
            )
            if is_multiclass:
                labels = (
                    tuple(node.class_labels)
                    if len(node.class_labels) == len(node.pd_final)
                    else class_labels
                )
                if len(labels) != len(node.pd_final):
                    raise ValueError(
                        f"[exporters] leaf {node.node_id} pd_final length "
                        f"{len(node.pd_final)} != class_labels length {len(labels)}."
                    )
                vec = ", ".join(
                    f"{lbl}: {_validate_finite_float(prob, f'leaf {node.node_id} pd_final[{idx}]'):.4f}"
                    for idx, (lbl, prob) in enumerate(zip(labels, node.pd_final))
                )
                return (
                    f"{indent}- **Leaf {node.node_id}**: "
                    f"Probability ({labels[0]}) = {pd_0:.4f} | Vector = ({vec})\n"
                )
            return (
                f"{indent}- **Leaf {node.node_id}**: "
                f"Probability = {pd_0:.4f}\n"
            )

        split = node.split
        if split is None:
            raise ValueError(
                f"Internal node {node_id} has no SplitConfig; it cannot be exported."
            )

        child_ids = tuple(node.child_ids)
        if len(child_ids) < 2:
            raise ValueError(
                f"Internal node {node_id} must have at least 2 children, "
                f"got {len(child_ids)}."
            )

        next_visiting = visiting | {node_id}
        lines = [
            f"{indent}- **Node {node.node_id}** (Split on `{split.predictor}`):\n"
        ]

        if split.threshold is not None:
            if len(child_ids) != 2:
                raise ValueError(
                    f"Threshold split on {split.predictor!r} has exactly 2 "
                    f"branches, got {len(child_ids)} children."
                )
            _validate_finite_float(split.threshold, f"node {node_id} threshold")
            lines.append(
                f"{indent}  - If <= {split.threshold}:\n"
                + _md_node(child_ids[0], depth + 1, next_visiting)
            )
            lines.append(
                f"{indent}  - Else:\n"
                + _md_node(child_ids[1], depth + 1, next_visiting)
            )
            return "".join(lines)

        if split.bin_edges:
            edges = tuple(split.bin_edges)
            for idx, edge in enumerate(edges):
                _validate_finite_float(edge, f"node {node_id} bin_edges[{idx}]")
            merged = _merged_bin_branches(split)
            if merged is not None:
                # CHAID continuo con ramas fusionadas (H-5.0.c-1): reglas por
                # RAMA consolidada, espejo del routing de tree_builder (§16.3).
                if len(child_ids) != len(merged):
                    raise ValueError(
                        f"CHAID split on {split.predictor!r} has {len(merged)} "
                        f"consolidated branches, got {len(child_ids)} children."
                    )
                for index, (_lo, hi) in enumerate(merged):
                    if hi == len(edges):
                        lines.append(
                            f"{indent}  - Else:\n"
                            + _md_node(child_ids[index], depth + 1, next_visiting)
                        )
                        continue
                    keyword = "If" if index == 0 else "Elif"
                    lines.append(
                        f"{indent}  - {keyword} <= {edges[hi]}:\n"
                        + _md_node(child_ids[index], depth + 1, next_visiting)
                    )
                return "".join(lines)
            if len(child_ids) != len(edges) + 1:
                raise ValueError(
                    f"CHAID split on {split.predictor!r} with {len(edges)} edges "
                    f"needs {len(edges) + 1} children, got {len(child_ids)}."
                )
            for index, edge in enumerate(edges):
                keyword = "If" if index == 0 else "Elif"
                lines.append(
                    f"{indent}  - {keyword} <= {edge}:\n"
                    + _md_node(child_ids[index], depth + 1, next_visiting)
                )
            lines.append(
                f"{indent}  - Else:\n"
                + _md_node(child_ids[-1], depth + 1, next_visiting)
            )
            return "".join(lines)

        if split.branches:
            branch_values = tuple(split.branches)
            if len(branch_values) != len(child_ids):
                raise ValueError(
                    f"Categorical split on {split.predictor!r} needs exactly "
                    f"one branch value set per child ({len(child_ids)} "
                    f"children), got {len(branch_values)} value sets."
                )
            # One rule per branch value set (CHAID emits exactly one set per
            # child), followed by a residual bullet describing the active
            # policy for values unseen at training time.
            for index in range(len(child_ids)):
                keyword = "If" if index == 0 else "Elif"
                lines.append(
                    f"{indent}  - {keyword} in {branch_values[index]}:\n"
                    + _md_node(child_ids[index], depth + 1, next_visiting)
                )
            if unseen_policy == "error":
                lines.append(
                    f"{indent}  - Else (unseen category → ValueError raised; policy = error):\n"
                )
            elif unseen_policy == "majority":
                lines.append(
                    f"{indent}  - Else (unseen category → routed to majority leaf "
                    f"pd={majority_pd:.4f}; policy = majority):\n"
                )
            else:
                lines.append(
                    f"{indent}  - Else (unseen category → not scored; policy = exclude):\n"
                )
            return "".join(lines)

        raise ValueError(
            f"Split on {split.predictor!r} has neither threshold, bin_edges nor "
            f"branches; it cannot be exported to Markdown."
        )

    if unseen_policy == "error":
        policy_header = (
            "**Unseen policy:** error (unseen categories abort the scoring; "
            "caller sees the exception)."
        )
    elif unseen_policy == "majority":
        policy_header = (
            "**Unseen policy:** majority (unseen categories route to the "
            f"majority leaf, pd={majority_pd:.4f})."
        )
    else:
        policy_header = (
            "**Unseen policy:** exclude (unseen categories are not scored; "
            "caller must filter NULL/None)."
        )
    header_lines = [
        "# TreeGov Decision Tree",
        "",
        f"**Fingerprint:** {_sanitize_comment(model.params_fingerprint)}",
        f"**Method:** {_sanitize_comment(model.method)}",
        policy_header,
    ]
    if is_multiclass:
        header_lines.append(
            f"**Multiclass note (K={len(class_labels)}):** primary score is "
            f"class of interest {class_labels[0]!r} (index 0); full class "
            "probability vector shown per leaf."
        )
    header_lines.extend(["", "## Decision Rules", "", ""])
    header = "\n".join(header_lines)
    return header + _md_node(
        model.root_id if node_id is None else node_id, 0, frozenset()
    )
