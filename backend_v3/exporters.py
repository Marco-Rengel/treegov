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

__all__ = ["export_to_markdown", "export_to_python", "export_to_sql"]


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

    if split.bin_edges:
        edges = tuple(split.bin_edges)
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
    return repr(float(value))


def _python_tuple(values: object) -> str:
    """Render a tuple of text values as a Python tuple literal.

    ``repr`` is used for the elements because it already escapes quotes and
    backslashes correctly. A single element keeps its trailing comma so the
    literal stays a tuple instead of collapsing into a parenthesised string.
    """
    items = [repr(str(value)) for value in values]
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

    TODO(zona_gris): the brief specifies a single ``row.get(col, default)``
    line. That covers an absent key but not a key that is present with a
    ``None`` value, while ``COALESCE`` in the SQL exporter covers both. A
    ``None`` would reach the comparison and raise ``TypeError``, breaking the
    prediction-parity invariant (§3 of the design note). The specified line is
    emitted unchanged and a two-line guard is appended after it so both
    exporters treat missing values identically.
    """
    means = getattr(imputer, "means", None) or {}
    modes = getattr(imputer, "modes", None) or {}
    key = repr(predictor)

    if predictor in means:
        default = _python_number(means[predictor])
    elif predictor in modes:
        default = repr(str(modes[predictor]))
    else:
        return [f"{variable} = row.get({key})"]

    return [
        f"{variable} = row.get({key}, {default})",
        f"if {variable} is None:",
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
    stack = [root_id]

    while stack:
        node_id = stack.pop()
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


def _python_node(node_id: int, depth: int, nodes_by_id: dict) -> list:
    """Render one node as a list of Python source lines indented by ``depth``.

    ``depth`` counts indentation levels of four spaces, so the generated script
    always keeps strict Python indentation. Leaves emit ``return`` with the
    class-of-interest probability (index 0 of ``pd_final``); internal nodes emit
    an ``if`` / ``elif`` / ``else`` chain whose arms recurse into the children.
    """
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
        lines = [f"{pad}if {variable} <= {_python_number(split.threshold)}:"]
        lines.extend(_python_node(child_ids[0], depth + 1, nodes_by_id))
        lines.append(f"{pad}else:")
        lines.extend(_python_node(child_ids[1], depth + 1, nodes_by_id))
        return lines

    if split.bin_edges:
        edges = tuple(split.bin_edges)
        if len(child_ids) != len(edges) + 1:
            raise ValueError(
                f"CHAID split on {split.predictor!r} with {len(edges)} edges needs "
                f"{len(edges) + 1} children, got {len(child_ids)}."
            )
        lines = []
        for index, edge in enumerate(edges):
            keyword = "if" if index == 0 else "elif"
            lines.append(f"{pad}{keyword} {variable} <= {_python_number(edge)}:")
            lines.extend(_python_node(child_ids[index], depth + 1, nodes_by_id))
        lines.append(f"{pad}else:")
        lines.extend(_python_node(child_ids[-1], depth + 1, nodes_by_id))
        return lines

    if split.branches is not None:
        branch_values = tuple(split.branches)
        if len(branch_values) < len(child_ids) - 1:
            raise ValueError(
                f"Categorical split on {split.predictor!r} needs at least "
                f"{len(child_ids) - 1} branch value sets, got {len(branch_values)}."
            )
        lines = []
        for index in range(len(child_ids) - 1):
            keyword = "if" if index == 0 else "elif"
            values = _python_tuple(branch_values[index])
            lines.append(f"{pad}{keyword} {variable} in {values}:")
            lines.extend(_python_node(child_ids[index], depth + 1, nodes_by_id))
        # TODO(zona_gris): the brief asks for `else:` on the last categorical
        # branch, while export_to_sql emits `ELSE NULL`. For a category unseen
        # at scoring time the two exporters therefore disagree: SQL returns
        # NULL, Python falls into the last branch. Followed the brief here;
        # reconcile both backends in a later turn.
        lines.append(f"{pad}else:")
        lines.extend(_python_node(child_ids[-1], depth + 1, nodes_by_id))
        return lines

    raise ValueError(
        f"Split on {split.predictor!r} has neither threshold, bin_edges nor "
        f"branches; it cannot be exported to Python."
    )


def export_to_python(model: "TreeModel", imputer: "ImputationSpec") -> str:
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
    artefact can be traced back to the model that generated it (MRM).

    Args:
        model: Trained decision tree. ``root_id``, ``nodes`` and
            ``params_fingerprint`` are read; the model is never mutated.
        imputer: Imputation specification fitted on the training partition.

    Returns:
        The source of a Python module, terminated by a newline.

    Raises:
        ValueError: if a split cannot be expressed as an ``if`` chain, or the
            tree is structurally inconsistent.
        KeyError: if a child references a ``node_id`` absent from ``model.nodes``.
    """
    nodes_by_id = _index_nodes(model)
    predictors = _python_predictors(model.root_id, nodes_by_id)

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

    lines = [
        f"# TreeGov Model Fingerprint: {model.params_fingerprint}",
        "",
        "def predict(row: dict) -> float:",
        "    return _eval_tree(row)",
        "",
        "",
        "def _eval_tree(row: dict) -> float:",
    ]

    for predictor in predictors:
        for line in _python_imputation(predictor, variables[predictor], imputer):
            lines.append("    " + line)

    lines.extend(_python_node(model.root_id, 1, nodes_by_id))

    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Markdown exporter
# --------------------------------------------------------------------------- #


def export_to_markdown(model: "TreeModel") -> str:
    """Export ``model`` as a human-readable Markdown report.

    The report reproduces the tree structure as nested bullet points: every
    internal node states the predictor it splits on, and every leaf states the
    class-of-interest probability (index 0 of ``pd_final``, rendered with four
    decimals). Its purpose is documentation and audit review, not machine
    consumption: prediction parity is guaranteed by :func:`export_to_sql` and
    :func:`export_to_python`, while this exporter only renders what is already
    stored in the model.

    The header carries ``model.params_fingerprint`` and ``model.method`` so a
    reviewer can trace the report back to the exact artefact that produced it
    (MRM requirement).

    The module performs no I/O and imports nothing at runtime: the return value
    is a plain ``str`` the caller is free to write to disk or embed elsewhere.

    Args:
        model: Trained decision tree. ``root_id``, ``method``, ``nodes`` and
            ``params_fingerprint`` are read; the model is never mutated.

    Returns:
        A Markdown document terminated by a newline.

    Raises:
        ValueError: if the tree is structurally inconsistent (an internal node
            without ``SplitConfig``, fewer than two children, or a branch count
            that does not match the split encoding).
        KeyError: if a child references a ``node_id`` absent from
            ``model.nodes``.
    """
    nodes_by_id = _index_nodes(model)

    def _md_node(node_id: int, depth: int) -> str:
        """Render one node and its descendants as a nested Markdown list.

        ``depth`` counts indentation levels of two spaces. Leaves render as a
        single bullet with the leaf probability; internal nodes render as a
        bullet naming the split predictor followed by one indented sub-bullet
        per branch, whose bodies recurse into the children.
        """
        try:
            node = nodes_by_id[node_id]
        except KeyError as exc:
            raise KeyError(
                f"node_id {node_id} is not present in model.nodes."
            ) from exc

        indent = "  " * depth

        if node.is_leaf:
            return (
                f"{indent}- **Leaf {node.node_id}**: "
                f"Probability = {node.pd_final[0]:.4f}\n"
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

        lines = [
            f"{indent}- **Node {node.node_id}** (Split on `{split.predictor}`):\n"
        ]

        if split.threshold is not None:
            if len(child_ids) != 2:
                raise ValueError(
                    f"Threshold split on {split.predictor!r} has exactly 2 "
                    f"branches, got {len(child_ids)} children."
                )
            lines.append(
                f"{indent}  - If <= {split.threshold}:\n"
                + _md_node(child_ids[0], depth + 1)
            )
            lines.append(
                f"{indent}  - Else:\n"
                + _md_node(child_ids[1], depth + 1)
            )
            return "".join(lines)

        if split.bin_edges:
            edges = tuple(split.bin_edges)
            if len(child_ids) != len(edges) + 1:
                raise ValueError(
                    f"CHAID split on {split.predictor!r} with {len(edges)} edges "
                    f"needs {len(edges) + 1} children, got {len(child_ids)}."
                )
            for index, edge in enumerate(edges):
                keyword = "If" if index == 0 else "Elif"
                lines.append(
                    f"{indent}  - {keyword} <= {edge}:\n"
                    + _md_node(child_ids[index], depth + 1)
                )
            lines.append(
                f"{indent}  - Else:\n" + _md_node(child_ids[-1], depth + 1)
            )
            return "".join(lines)

        if split.branches:
            branch_values = tuple(split.branches)
            if len(branch_values) < len(child_ids) - 1:
                raise ValueError(
                    f"Categorical split on {split.predictor!r} needs at least "
                    f"{len(child_ids) - 1} branch value sets, got "
                    f"{len(branch_values)}."
                )
            # TODO(zona_gris): the brief renders categorical splits with exactly
            # two branches ("If in {branches[0]}" / "Else"). If a categorical
            # split ever carries more than two children, emitting only two of
            # them would silently drop whole subtrees from the report, so any
            # intermediate child is rendered as "Elif in {branches[i]}".
            # In the binary case (one branch value set plus one Else) the
            # output is exactly the one specified by the brief.
            for index in range(len(child_ids) - 1):
                keyword = "If" if index == 0 else "Elif"
                lines.append(
                    f"{indent}  - {keyword} in {branch_values[index]}:\n"
                    + _md_node(child_ids[index], depth + 1)
                )
            lines.append(
                f"{indent}  - Else:\n" + _md_node(child_ids[-1], depth + 1)
            )
            return "".join(lines)

        raise ValueError(
            f"Split on {split.predictor!r} has neither threshold, bin_edges nor "
            f"branches; it cannot be exported to Markdown."
        )

    header = (
        "# TreeGov Decision Tree\n\n"
        f"**Fingerprint:** {model.params_fingerprint}\n"
        f"**Method:** {model.method}\n\n"
        "## Decision Rules\n\n"
    )
    return header + _md_node(model.root_id, 0)
