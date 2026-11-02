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

from backend_v3.imputation import ImputationSpec
from backend_v3.tree_builder import TreeModel

__all__ = ["export_to_markdown", "export_to_python", "export_to_sql"]


def _ensure_unseen_policy(unseen_policy: str) -> None:
    """Validate ``unseen_policy`` and gate not-yet-implemented policies.

    The vocabulary mirrors the backend parameter of the same name in
    ``backend_v3.validation._assign_leaves`` (design_decisions.md §7.6):
    ``"error"``, ``"exclude"`` and ``"majority"``. Anything else raises
    ``ValueError`` naming the three admissible values. Only ``"exclude"`` is
    implemented in sub-phase 4.0.1.a of
    ``docs/4.0.1_design_categorical_exporters.md``; the other two are accepted
    by the vocabulary but raise ``NotImplementedError`` so they never silently
    alias the default behaviour (implementation lands in sub-phase 4.0.1.b).
    """
    if unseen_policy not in ("error", "exclude", "majority"):
        raise ValueError(
            f"[exporters] unseen_policy invalida: {unseen_policy!r} "
            "(valores admitidos: 'error', 'exclude', 'majority')"
        )
    if unseen_policy != "exclude":
        raise NotImplementedError(
            f"[exporters] unseen_policy='{unseen_policy}' se implementa "
            "en la sub-fase 4.0.1.b"
        )


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
        merged = _merged_bin_branches(split)
        if merged is not None:
            # CHAID continuo con ramas fusionadas (H-5.0.c-1): una condicion
            # por RAMA consolidada, no por bin individual.
            lo, hi = merged[index]
            if hi == len(edges):
                # Rama superior (sin corte por encima): dominio residual.
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
        literals = ", ".join(_sql_string(value) for value in values)
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
    exact model that generated it (MRM requirement). The second line declares
    the ``unseen_policy`` in force: with the current ``"exclude"`` policy a
    categorical value unseen at training time matches no branch, so the
    exported statement returns ``NULL`` for that row and the caller must
    filter or escalate it.

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
            ``"exclude"`` (default, the only implemented policy): the row
            falls through to ``ELSE NULL`` and is not scored. ``"error"`` and
            ``"majority"`` are part of the governed vocabulary but not
            implemented yet; they raise ``NotImplementedError``
            (sub-phase 4.0.1.b).

    Returns:
        A ready-to-paste SQL statement terminated with a semicolon.

    Raises:
        ValueError: if a split cannot be expressed in ANSI SQL or the tree is
            structurally inconsistent.
        KeyError: if a child references a ``node_id`` absent from ``model.nodes``.
        NotImplementedError: if ``unseen_policy`` is not ``"exclude"``
            (``"error"`` and ``"majority"`` land in sub-phase 4.0.1.b).
    """
    _ensure_unseen_policy(unseen_policy)
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

        lines = ["CASE"]
        has_else = False
        for index, child_id in enumerate(child_ids):
            child_sql = _sql_node(child_id, indent + 1)
            if merged is not None and merged[index][1] == len(split.bin_edges):
                # Rama superior de un split CHAID fusionado (H-5.0.c-1): cubre
                # el dominio residual completo, se renderiza como ELSE.
                lines.append(f"{pad}ELSE")
                lines.append(f"{pad} {child_sql}")
                has_else = True
                continue
            condition = _sql_condition(split, index, imputer)
            lines.append(f"{pad}WHEN {condition} THEN")
            lines.append(f"{pad} {child_sql}")
        if not has_else:
            lines.append(f"{pad}ELSE NULL")
        lines.append(f"{pad}END")
        return "\n".join(lines)

    body = _sql_node(model.root_id, 0)
    return (
        f"-- TreeGov Model Fingerprint: {model.params_fingerprint}\n"
        "-- Unseen policy: exclude (unseen categories return NULL; caller must filter)\n"
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

    The specified ``row.get(col, default)`` line covers an absent key but not
    a key that is present with a ``None`` value, while ``COALESCE`` in the SQL
    exporter covers both: a ``None`` reaching the comparison would raise
    ``TypeError``. The line is therefore emitted unchanged and a two-line
    guard is appended after it so both exporters treat missing values
    identically (resolved in design_decisions.md §19.2, 01/11/2026).
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
    an ``if`` / ``elif`` / ``else`` chain whose arms recurse into the children,
    except that under the ``"exclude"`` unseen policy a categorical split ends
    with ``else: return None`` (an unseen category is not routed anywhere).
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
        merged = _merged_bin_branches(split)
        if merged is not None:
            # CHAID continuo con ramas fusionadas (H-5.0.c-1): if/elif por
            # corte superior de cada RAMA consolidada; la rama que contiene
            # el bin superior es el else residual. La guarda bins+1 solo
            # aplica a la codificacion antigua sin ramas fusionadas.
            if len(child_ids) != len(merged):
                raise ValueError(
                    f"CHAID split on {split.predictor!r} has {len(merged)} "
                    f"consolidated branches, got {len(child_ids)} children."
                )
            lines = []
            for index, (_lo, hi) in enumerate(merged):
                if hi == len(edges):
                    lines.append(f"{pad}else:")
                else:
                    keyword = "if" if index == 0 else "elif"
                    lines.append(
                        f"{pad}{keyword} {variable} <= {_python_number(edges[hi])}:"
                    )
                lines.extend(_python_node(child_ids[index], depth + 1, nodes_by_id))
            return lines
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
            lines.extend(_python_node(child_ids[index], depth + 1, nodes_by_id))
        # unseen_policy="exclude": an unseen categorical value matches no
        # branch set. The backend leaves those rows unrouted (validation.py)
        # and SQL falls through to ELSE NULL, so the artefact returns None.
        lines.append(f"{pad}else:")
        lines.append(f"{pad}    return None")
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
    second line declares the ``unseen_policy`` in force: with the current
    ``"exclude"`` policy a categorical value unseen at training time matches
    no branch, so ``predict`` returns ``None`` for that row and the caller
    must filter or escalate it.

    Args:
        model: Trained decision tree. ``root_id``, ``nodes`` and
            ``params_fingerprint`` are read; the model is never mutated.
        imputer: Imputation specification fitted on the training partition.
        unseen_policy: Behavior for rows carrying unseen categorical values.
            ``"exclude"`` (default, the only implemented policy): the final
            categorical fallback returns ``None``. ``"error"`` and
            ``"majority"`` are part of the governed vocabulary but not
            implemented yet; they raise ``NotImplementedError``
            (sub-phase 4.0.1.b).

    Returns:
        The source of a Python module, terminated by a newline. Under
        ``"exclude"``, ``predict``/``_eval_tree`` are declared as
        ``float | None``.

    Raises:
        ValueError: if a split cannot be expressed as an ``if`` chain, or the
            tree is structurally inconsistent.
        KeyError: if a child references a ``node_id`` absent from ``model.nodes``.
        NotImplementedError: if ``unseen_policy`` is not ``"exclude"``
            (``"error"`` and ``"majority"`` land in sub-phase 4.0.1.b).
    """
    _ensure_unseen_policy(unseen_policy)
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
        "# Unseen policy: exclude (unseen categories return None; caller must filter)",
        "",
        "def predict(row: dict) -> float | None:",
        "    return _eval_tree(row)",
        "",
        "",
        "def _eval_tree(row: dict) -> float | None:",
    ]

    for predictor in predictors:
        for line in _python_imputation(predictor, variables[predictor], imputer):
            lines.append("    " + line)

    lines.extend(_python_node(model.root_id, 1, nodes_by_id))

    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Markdown exporter
# --------------------------------------------------------------------------- #


def export_to_markdown(
    model: TreeModel,
    *,
    unseen_policy: str = "exclude",
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
    bullet that marks rows carrying unseen categories: they are not scored,
    mirroring the ``NULL`` (SQL) / ``None`` (Python) routing of the scoring
    exporters under the same policy.

    The module performs no I/O: the return value is a plain ``str`` the caller
    is free to write to disk or embed elsewhere.

    Args:
        model: Trained decision tree. ``root_id``, ``method``, ``nodes`` and
            ``params_fingerprint`` are read; the model is never mutated.
        unseen_policy: Governs how the report labels rows carrying unseen
            categorical values. ``"exclude"`` (default, the only implemented
            policy) renders the residual bullet as "not scored".
            ``"error"`` and ``"majority"`` are part of the governed vocabulary
            but not implemented yet; they raise ``NotImplementedError``
            (sub-phase 4.0.1.b).

    Returns:
        A Markdown document terminated by a newline.

    Raises:
        ValueError: if the tree is structurally inconsistent (an internal node
            without ``SplitConfig``, fewer than two children, or a branch count
            that does not match the split encoding).
        KeyError: if a child references a ``node_id`` absent from
            ``model.nodes``.
        NotImplementedError: if ``unseen_policy`` is not ``"exclude"``
            (``"error"`` and ``"majority"`` land in sub-phase 4.0.1.b).
    """
    _ensure_unseen_policy(unseen_policy)
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
                            + _md_node(child_ids[index], depth + 1)
                        )
                        continue
                    keyword = "If" if index == 0 else "Elif"
                    lines.append(
                        f"{indent}  - {keyword} <= {edges[hi]}:\n"
                        + _md_node(child_ids[index], depth + 1)
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
                    + _md_node(child_ids[index], depth + 1)
                )
            lines.append(
                f"{indent}  - Else:\n" + _md_node(child_ids[-1], depth + 1)
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
            # child), followed by a residual bullet for rows carrying values
            # unseen at training time (not scored; policy = exclude).
            for index in range(len(child_ids)):
                keyword = "If" if index == 0 else "Elif"
                lines.append(
                    f"{indent}  - {keyword} in {branch_values[index]}:\n"
                    + _md_node(child_ids[index], depth + 1)
                )
            lines.append(
                f"{indent}  - Else (unseen category → not scored; policy = exclude):\n"
            )
            return "".join(lines)

        raise ValueError(
            f"Split on {split.predictor!r} has neither threshold, bin_edges nor "
            f"branches; it cannot be exported to Markdown."
        )

    header = (
        "# TreeGov Decision Tree\n\n"
        f"**Fingerprint:** {model.params_fingerprint}\n"
        f"**Method:** {model.method}\n"
        "**Unseen policy:** exclude (unseen categories are not scored; caller must filter NULL/None).\n\n"
        "## Decision Rules\n\n"
    )
    return header + _md_node(model.root_id, 0)
