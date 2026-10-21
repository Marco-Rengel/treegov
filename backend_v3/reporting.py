"""Reporting layer (TreeGov, backend_v3): flat report DTOs, Qt-free.

White-box (numpy only) and deterministic. Two report families:

  * OOS/OOT flat DTO (Phase 2.3.d): ``build_oos_oot_report``.
  * Gains table and classification matrix over a fitted ``TreeModel``:
    ``build_gains_table`` and ``build_classification_matrix``.

KS / AUC / Gini delegate to ``backend_v3.validation``: the binary
header metrics come from ``validation._pair_auc_ks`` (weighted pair
kernel; Gini = 2*AUC - 1), and the multiclass header metrics from
``validation.compute_oos_metrics``. The Hosmer-Lemeshow ``n_groups``
logic of ``compute_oos_metrics`` does not apply to gains tables, which
is why the binary path uses the pair kernel directly.

Phase 3.5.b (multiclass reports, D13/D18/D19/D20):
``build_gains_table`` dispatches on K = len(model.class_labels). The
binary path (K = 2) computes its header metrics through
``validation._pair_auc_ks`` with the routed weights (D13 resolved:
they are weighted; with uniform weights they match the unweighted
values exactly). The multiclass path
(K > 2) adds per-class count columns and computes the header
discrimination metrics by calling ``validation.compute_oos_metrics``
with the adaptive ``n_groups`` rule of D20 (None when fewer than 15
rows are routed). ``build_classification_matrix`` remains binary; the
K x K matrix is served by ``build_classification_matrix_multiclass``
(D19), which treats the class of interest (index 0) as "positive".

Phase 3.2.g (sample weighting): both report builders accept a
keyword-only ``weights`` vector and expose parallel ``w_*`` columns
with weighted mass (Heeringa, West & Berglund 2010, §5.3). With
``weights=None`` the ``w_*`` values match their integer counterparts
exactly (parity invariant).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from .validation import _pair_auc_ks, compute_oos_metrics

if TYPE_CHECKING:  # type-checkers only; no runtime imports from these modules
    from .session_state import SessionState
    from .tree_builder import TreeModel

__all__ = [
    "build_oos_oot_report",
    "GainsRow",
    "GainsTableResult",
    "ClassificationMatrix",
    "build_gains_table",
    "build_classification_matrix",
    "build_classification_matrix_multiclass",
]


def build_oos_oot_report(st: SessionState) -> dict[str, Any] | None:
    """Devuelve None si no hay modelo; si no, DTO con claves 'oos'/'oot'.

    Fase 3.3.c: el sub-dict 'oot' ahora distingue los dos tipos de
    exclusion posibles en la cohorte OOT:
      - 'n_excluded_routing' (antes 'n_excluded'): filas que no se
        pudieron enrutar por el arbol (categorias no vistas en train).
      - 'n_excluded_population': filas excluidas por la columna de
        poblacion declarada en fix_spec.
    Tambien expone 'population_breakdown', el desglose por valor no-OK
    de esas filas excluidas por poblacion.
    """
    if st.tree is None:
        return None
    oot_dto: dict[str, Any] | None = None
    if st.oot_report is not None:
        oot_dto = asdict(st.oot_report)
        # Fase 3.3.c: rename n_excluded -> n_excluded_routing
        oot_dto["n_excluded_routing"] = oot_dto.pop("n_excluded")
        # Fase 3.3.c: contadores de filtro de poblacion
        oot_dto["n_excluded_population"] = st.n_excluded_population_oot
        oot_dto["population_breakdown"] = st.population_breakdown_oot
    return {
        "oos": None if st.oos_metrics is None else asdict(st.oos_metrics),
        "oot": oot_dto,
    }


@dataclass(frozen=True)
class GainsRow:
    """One immutable gains-table line (leaf or bucket).

    ``*_cum`` accumulates from the best (lowest-PD) row downwards;
    ``*_decum`` accumulates from the worst row upwards, current row included.
    ``lift_cum = bad_rate_cum / bad_rate_global`` (NaN when the global bad
    rate is 0, i.e. no events among the routed rows).

    Phase 3.5.b (D19): the per-class tuples carry K components in
    canonical class order (index 0 = class of interest) in the
    multiclass path; they stay empty in the binary path.
    """

    label: str
    pd: float
    n: int
    n_good: int
    n_bad: int
    bad_rate: float
    n_cum: int
    n_good_cum: int
    n_bad_cum: int
    bad_rate_cum: float
    lift_cum: float
    n_decum: int
    n_good_decum: int
    n_bad_decum: int
    bad_rate_decum: float
    # Fase 3.2.g: columnas paralelas ponderadas. Con weights=None,
    # coinciden exactamente con sus contrapartes de conteo (paridad).
    w_n: float = 0.0
    w_good: float = 0.0
    w_bad: float = 0.0
    w_bad_rate: float = 0.0
    w_n_cum: float = 0.0
    w_bad_cum: float = 0.0
    w_bad_rate_cum: float = 0.0
    w_lift_cum: float = 0.0
    w_n_decum: float = 0.0
    w_bad_decum: float = 0.0
    w_bad_rate_decum: float = 0.0
    # Fase 3.5.b (D19): per-class columns, aditivas. Vacías en el path
    # binario; pobladas con K componentes en el path multiclase.
    n_per_class: tuple[int, ...] = ()
    n_per_class_cum: tuple[int, ...] = ()
    n_per_class_decum: tuple[int, ...] = ()
    w_n_per_class: tuple[float, ...] = ()
    w_n_per_class_cum: tuple[float, ...] = ()
    w_n_per_class_decum: tuple[float, ...] = ()


@dataclass(frozen=True)
class GainsTableResult:
    """Gains table over the routed rows of a scored sample.

    ``n_total`` / ``n_good`` / ``n_bad`` count routed rows only; unrouted rows
    (``leaf_assignment == -1``) appear solely in ``n_excluded``.
    ``ks`` / ``auc`` / ``gini`` are recomputed on per-row PD with the
    ``backend_v3.validation`` formulas; ``None`` when a class is absent.

    Phase 3.5.b (D19, D20): ``class_labels`` in canonical order, the
    per-class global totals and ``ks_pairs`` / ``auc_pairs`` are
    populated only in the multiclass path (the binary path keeps them
    empty by D13 literal). In the multiclass path, ``ks`` is the
    worst-case pairwise KS, ``auc`` / ``gini`` the Hand & Till values,
    and all three are ``None`` when fewer than 15 rows are routed (D20).
    """

    by: str
    rows: tuple[GainsRow, ...]
    n_total: int
    n_good: int
    n_bad: int
    bad_rate_global: float
    ks: float | None
    auc: float | None
    gini: float | None
    n_excluded: int
    # Fase 3.2.g: totales ponderados (paridad con conteos si weights=None).
    w_total: float = 0.0
    w_bad: float = 0.0
    w_bad_rate_global: float = 0.0
    # Fase 3.5.b (D19, D20): per-class totals y metricas por par.
    class_labels: tuple[str, ...] = ()
    n_per_class_global: tuple[int, ...] = ()
    w_n_per_class_global: tuple[float, ...] = ()
    ks_pairs: tuple[tuple[int, int, float], ...] = ()
    auc_pairs: tuple[tuple[int, int, float], ...] = ()


@dataclass(frozen=True)
class ClassificationMatrix:
    """Confusion matrix (credit-scoring naming).

    ``bad_capture_rate`` is an explicit alias of ``recall`` (same value).
    Ratio fields are ``None`` when their denominator is 0. Counts cover
    routed rows only; unrouted rows appear solely in ``n_excluded``.

    ``threshold`` only has meaning in the binary path (K=2); in the
    multiclass path it is recorded as NaN for traceability (the
    assignment is argmax, not thresholded).

    Fase 3.5.b (D19): additive fields. In the binary path (K=2) only
    ``accuracy`` is populated (trace of the 2x2 matrix divided by
    n_total; never None when n_total > 0); the rest keep their empty
    defaults. In the multiclass path (K > 2,
    ``build_classification_matrix_multiclass``) all of them are
    populated, and the inherited binary fields (tp, tn, fp, fn,
    precision, recall, f1, bad_capture_rate, n_good, n_bad) are computed
    with the class of interest (index 0) as "positive" and all other
    classes grouped as "negative", preserving the semantics the binary
    panel consumer already reads.
    """

    threshold: float
    n_total: int
    n_good: int
    n_bad: int
    tp: int
    tn: int
    fp: int
    fn: int
    precision: float | None
    recall: float | None
    f1: float | None
    bad_capture_rate: float | None
    n_excluded: int
    # Fase 3.2.g: celdas y ratios ponderados (paridad con conteos si
    # weights=None).
    w_tp: float = 0.0
    w_tn: float = 0.0
    w_fp: float = 0.0
    w_fn: float = 0.0
    w_precision: float | None = None
    w_recall: float | None = None
    w_f1: float | None = None
    w_bad_capture_rate: float | None = None
    # Fase 3.5.b (D19): campos aditivos. En el path binario (K=2) solo
    # accuracy se puebla; el resto queda vacio. En K>2 se pueblan todos.
    confusion_matrix: tuple[tuple[int, ...], ...] = ()
    n_per_class: tuple[int, ...] = ()
    precision_per_class: tuple[float | None, ...] = ()
    recall_per_class: tuple[float | None, ...] = ()
    f1_per_class: tuple[float | None, ...] = ()
    accuracy: float | None = None
    w_confusion_matrix: tuple[tuple[float, ...], ...] = ()
    w_n_per_class: tuple[float, ...] = ()
    w_precision_per_class: tuple[float | None, ...] = ()
    w_recall_per_class: tuple[float | None, ...] = ()
    w_f1_per_class: tuple[float | None, ...] = ()
    w_accuracy: float | None = None


def _validated_routed(
    leaf_assignment: np.ndarray,
    y: np.ndarray,
    who: str,
    *,
    n_classes: int | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return ``(routed_mask, leaf_ids_routed, y_routed)`` after basic checks.

    Phase 3.5.b (D18): ``n_classes=None`` (default, pre-3.5 behaviour)
    requires binary y (0/1); ``n_classes=K`` requires y labels in
    {0, 1, ..., K-1}. The binary path keeps the strict validation; the
    multiclass path extends it without duplicating the helper.
    """
    assign = np.asarray(leaf_assignment, dtype=int)
    yv = np.asarray(y, dtype=int)
    if assign.shape != yv.shape or assign.ndim != 1:
        raise ValueError(
            f"[reporting] {who}: leaf_assignment and y must be 1-D vectors "
            "of equal length"
        )
    if n_classes is None:
        if not np.isin(yv, (0, 1)).all():
            raise ValueError(f"[reporting] {who}: y must be binary (0/1)")
    else:
        if n_classes < 2:
            raise ValueError(
                f"[reporting] {who}: n_classes must be >= 2; got {n_classes}"
            )
        if ((yv < 0) | (yv >= n_classes)).any():
            raise ValueError(
                f"[reporting] {who}: y must carry labels in "
                f"{{0, 1, ..., {n_classes - 1}}} (n_classes={n_classes})"
            )
    routed = assign >= 0
    return routed, assign[routed], yv[routed]


def _validated_weights(
    weights: np.ndarray | None, n: int, who: str
) -> np.ndarray | None:
    """Validate the optional weight vector (Phase 3.2.g); None passthrough."""
    if weights is None:
        return None
    w = np.asarray(weights, dtype=float)
    if w.ndim != 1:
        raise ValueError(f"[reporting] {who}: weights must be 1-D")
    if len(w) != n:
        raise ValueError(
            f"[reporting] {who}: weights length {len(w)} != {n}"
        )
    if not np.isfinite(w).all():
        raise ValueError(f"[reporting] {who}: weights contain non-finite values")
    if not (w > 0).all():
        raise ValueError(
            f"[reporting] {who}: weights must be strictly positive"
        )
    return w


def build_gains_table(
    model: TreeModel,
    leaf_assignment: np.ndarray,
    y: np.ndarray,
    *,
    by: str = "leaf",
    n_buckets: int = 10,
    tie: str = "preserve",
    seed: int | None = None,
    weights: np.ndarray | None = None,
) -> GainsTableResult:
    """Build a gains table by leaf or by PD bucket (deterministic).

    Ordering convention: ascending PD (best first, bureau convention).

    by="leaf": one row per leaf holding at least one routed observation,
    ordered by ``pd_final`` ascending (ties break by ascending ``node_id``);
    labels "L<node_id>".

    by="bucket": rows grouped into up to ``n_buckets`` PD-ordered buckets,
    labels "B01".."BNN". tie="preserve" keeps equal-PD rows together in the
    same bucket (deterministic; may yield fewer than ``n_buckets`` buckets).
    tie="random" breaks ties at random and requires an explicit ``seed``
    (``ValueError`` when ``seed is None``).

    Rows with ``leaf_assignment == -1`` join no group; they only count in
    ``n_excluded``. Raises ``ValueError`` when no row is routed.

    Phase 3.2.g: ``weights`` (keyword-only, default None) adds the
    parallel ``w_*`` columns with weighted mass per row
    (Heeringa, West & Berglund 2010, §5.3). With ``weights=None`` the
    ``w_*`` columns match their integer counterparts exactly (parity).
    The header ``ks`` / ``auc`` / ``gini`` are computed by
    ``validation._pair_auc_ks`` over the routed weights (D13 resolved:
    they are weighted; with uniform weights they match the unweighted
    values exactly, and ``None`` when a class mass is zero).

    Phase 3.5.b: dispatch on K = len(model.class_labels). With K = 2,
    the classic binary path. With K > 2, the multiclass path: each row
    gains per-class count columns (``n_per_class`` with their
    cumulative/decumulative and ``w_*`` counterparts, in canonical
    class order); the "bad" semantics maps to the class of interest
    (index 0); and the header metrics come from
    ``validation.compute_oos_metrics`` (Hand & Till AUC/Gini,
    worst-case pairwise KS) with the adaptive ``n_groups`` rule of D20:
    n_groups = min(10, max(3, n_routed // 5)), and
    ks = auc = gini = None (without calling compute_oos_metrics) when
    fewer than 15 rows are routed.
    """
    if by not in ("leaf", "bucket"):
        raise ValueError(f"[reporting] invalid by={by!r} ('leaf'/'bucket')")
    if tie not in ("preserve", "random"):
        raise ValueError(f"[reporting] invalid tie={tie!r} ('preserve'/'random')")
    if n_buckets < 1:
        raise ValueError(f"[reporting] n_buckets must be >= 1; got {n_buckets}")
    if tie == "random" and seed is None:
        raise ValueError("[reporting] tie='random' requires an explicit seed")

    K = len(model.class_labels)
    multiclass = K > 2

    routed, leaf_ids, y_r = _validated_routed(
        leaf_assignment, y, "gains_table", n_classes=K
    )
    n_excluded = int((~routed).sum())
    n_total = int(leaf_ids.size)
    if n_total == 0:
        raise ValueError("[reporting] gains table undefined: no routed rows")
    w = _validated_weights(weights, len(np.asarray(leaf_assignment)), "gains_table")
    w_r = w[routed] if w is not None else np.ones(n_total, dtype=float)

    # PD de la clase de interes (columna 0 del pd_final canonico): ordena
    # filas y buckets en ambos paths. En multiclase, la matriz completa
    # (node_pd) alimenta las metricas por par via compute_oos_metrics.
    node_pd = np.array([nd.pd_final for nd in model.nodes], dtype=float)
    pd_per_node = node_pd[:, 0]
    pd_row = pd_per_node[leaf_ids]

    # Indicador de evento: binario y==1 (convencion pre-3.5); multiclase
    # y==0 (clase de interes, indice 0 del orden canonico; D19).
    bad_ind = (y_r == 0).astype(int) if multiclass else y_r

    n_bad = int(bad_ind.sum())
    n_good = n_total - n_bad
    bad_rate_global = n_bad / n_total

    # Masa ponderada global (con weights=None, w_r son unos: paridad).
    w_total = float(w_r.sum())
    w_bad_global = float((w_r * bad_ind).sum())
    w_bad_rate_global = w_bad_global / w_total if w_total > 0.0 else 0.0

    # ---- grouping: list of (label, pd_value, routed-row indices) ---------
    if by == "leaf":
        uniq = np.unique(leaf_ids)
        ordered = sorted(uniq, key=lambda lid: (float(pd_per_node[lid]), int(lid)))
        groups = [
            (f"L{int(lid)}", float(pd_per_node[lid]), np.flatnonzero(leaf_ids == lid))
            for lid in ordered
        ]
    else:
        if tie == "preserve":
            order = np.argsort(pd_row, kind="mergesort")
        else:
            rng = np.random.default_rng(seed)
            # lexsort: primary key pd_row, ties broken by random keys.
            order = np.lexsort((rng.random(n_total), pd_row))
        pd_s = pd_row[order]
        cuts: list[int] = []
        for k in range(1, n_buckets):
            b = int(np.floor(k * n_total / n_buckets))
            if tie == "preserve":
                # snap the border forward, out of any tie block (clean cut)
                while 0 < b < n_total and pd_s[b] == pd_s[b - 1]:
                    b += 1
            if 0 < b < n_total and (not cuts or b > cuts[-1]):
                cuts.append(b)
        bounds = [0, *cuts, n_total]
        groups = []
        for g in range(len(bounds) - 1):
            seg = order[bounds[g]:bounds[g + 1]]
            groups.append((f"B{g + 1:02d}", float(pd_row[seg].mean()), seg))

    # ---- per-group counts -------------------------------------------------
    # n_pc / w_n_pc: conteos por clase en orden canonico (se emiten solo en
    # el path multiclase; en binario se calculan pero no se usan).
    stats: list[tuple[str, float, int, int, int, float, float,
                      np.ndarray, np.ndarray]] = []
    for label, pd_val, idx in groups:
        n_g = int(idx.size)
        bad_g = int(bad_ind[idx].sum())
        w_n_g = float(w_r[idx].sum())
        w_bad_g = float((w_r[idx] * bad_ind[idx]).sum())
        n_pc = np.array(
            [np.count_nonzero(y_r[idx] == k) for k in range(K)], dtype=int
        )
        w_n_pc = np.array(
            [(w_r[idx] * (y_r[idx] == k)).sum() for k in range(K)],
            dtype=float,
        )
        stats.append((label, pd_val, n_g, n_g - bad_g, bad_g,
                      w_n_g, w_bad_g, n_pc, w_n_pc))

    # suffix totals (current row included) for the decumulative columns
    suffix_n = suffix_good = suffix_bad = 0
    suffix_wn = suffix_wbad = 0.0
    suffix_npc = np.zeros(K, dtype=int)
    suffix_wnpc = np.zeros(K, dtype=float)
    suffixes: list[tuple[int, int, int, float, float,
                         np.ndarray, np.ndarray]] = []
    for (_, _, n_g, good_g, bad_g, w_n_g, w_bad_g,
         n_pc, w_n_pc) in reversed(stats):
        suffix_n += n_g
        suffix_good += good_g
        suffix_bad += bad_g
        suffix_wn += w_n_g
        suffix_wbad += w_bad_g
        suffix_npc += n_pc
        suffix_wnpc += w_n_pc
        suffixes.append((suffix_n, suffix_good, suffix_bad,
                         suffix_wn, suffix_wbad,
                         suffix_npc.copy(), suffix_wnpc.copy()))
    suffixes.reverse()

    rows: list[GainsRow] = []
    cum_n = cum_good = cum_bad = 0
    cum_wn = cum_wbad = 0.0
    cum_npc = np.zeros(K, dtype=int)
    cum_wnpc = np.zeros(K, dtype=float)
    for (label, pd_val, n_g, good_g, bad_g, w_n_g, w_bad_g,
         n_pc, w_n_pc), (dn, dgood, dbad, dwn, dwbad, dnpc, dwnpc) in zip(
        stats, suffixes
    ):
        cum_n += n_g
        cum_good += good_g
        cum_bad += bad_g
        cum_wn += w_n_g
        cum_wbad += w_bad_g
        cum_npc += n_pc
        cum_wnpc += w_n_pc
        bad_rate_cum = cum_bad / cum_n
        w_good_g = w_n_g - w_bad_g
        w_bad_rate_g = w_bad_g / w_n_g if w_n_g > 0.0 else 0.0
        w_bad_rate_cum_g = cum_wbad / cum_wn if cum_wn > 0.0 else 0.0
        w_bad_rate_decum_g = dwbad / dwn if dwn > 0.0 else 0.0
        per_class = {}
        if multiclass:
            per_class = dict(
                n_per_class=tuple(int(v) for v in n_pc),
                n_per_class_cum=tuple(int(v) for v in cum_npc),
                n_per_class_decum=tuple(int(v) for v in dnpc),
                w_n_per_class=tuple(float(v) for v in w_n_pc),
                w_n_per_class_cum=tuple(float(v) for v in cum_wnpc),
                w_n_per_class_decum=tuple(float(v) for v in dwnpc),
            )
        rows.append(
            GainsRow(
                label=label,
                pd=pd_val,
                n=n_g,
                n_good=good_g,
                n_bad=bad_g,
                bad_rate=bad_g / n_g,
                n_cum=cum_n,
                n_good_cum=cum_good,
                n_bad_cum=cum_bad,
                bad_rate_cum=bad_rate_cum,
                lift_cum=(
                    bad_rate_cum / bad_rate_global
                    if bad_rate_global > 0.0
                    else float("nan")
                ),
                n_decum=dn,
                n_good_decum=dgood,
                n_bad_decum=dbad,
                bad_rate_decum=dbad / dn,
                w_n=w_n_g,
                w_good=w_good_g,
                w_bad=w_bad_g,
                w_bad_rate=w_bad_rate_g,
                w_n_cum=cum_wn,
                w_bad_cum=cum_wbad,
                w_bad_rate_cum=w_bad_rate_cum_g,
                w_lift_cum=(
                    w_bad_rate_cum_g / w_bad_rate_global
                    if w_bad_rate_global > 0.0
                    else float("nan")
                ),
                w_n_decum=dwn,
                w_bad_decum=dwbad,
                w_bad_rate_decum=w_bad_rate_decum_g,
                **per_class,
            )
        )

    if multiclass:
        n_per_class_global = tuple(
            int(np.count_nonzero(y_r == k)) for k in range(K)
        )
        w_n_per_class_global = tuple(
            float((w_r * (y_r == k)).sum()) for k in range(K)
        )
        if n_total < 15:
            # D20: por debajo del minimo Cochran-5 no hay metricas de
            # discriminacion (compute_oos_metrics no se llama).
            ks = auc = gini = None
            ks_pairs: tuple[tuple[int, int, float], ...] = ()
            auc_pairs: tuple[tuple[int, int, float], ...] = ()
        else:
            # D20: n_groups adaptativo (misma formula que evaluate_oot).
            n_groups_eff = min(10, max(3, n_total // 5))
            oos = compute_oos_metrics(
                node_pd[leaf_ids], y_r, n_groups=n_groups_eff,
                weights=w[routed] if w is not None else None,
            )
            ks, auc, gini = oos.ks, oos.auc, oos.gini
            ks_pairs, auc_pairs = oos.ks_pairs, oos.auc_pairs
        return GainsTableResult(
            by=by,
            rows=tuple(rows),
            n_total=n_total,
            n_good=n_good,
            n_bad=n_bad,
            bad_rate_global=bad_rate_global,
            ks=ks,
            auc=auc,
            gini=gini,
            n_excluded=n_excluded,
            w_total=w_total,
            w_bad=w_bad_global,
            w_bad_rate_global=w_bad_rate_global,
            class_labels=tuple(model.class_labels),
            n_per_class_global=n_per_class_global,
            w_n_per_class_global=w_n_per_class_global,
            ks_pairs=ks_pairs,
            auc_pairs=auc_pairs,
        )

    auc, ks = _pair_auc_ks(pd_row, bad_ind, w_r)
    gini = None if auc is None else 2.0 * auc - 1.0

    return GainsTableResult(
        by=by,
        rows=tuple(rows),
        n_total=n_total,
        n_good=n_good,
        n_bad=n_bad,
        bad_rate_global=bad_rate_global,
        ks=ks,
        auc=auc,
        gini=gini,
        n_excluded=n_excluded,
        w_total=w_total,
        w_bad=w_bad_global,
        w_bad_rate_global=w_bad_rate_global,
    )


def build_classification_matrix(
    leaf_assignment: np.ndarray,
    y: np.ndarray,
    pd_per_leaf: dict[int, float],
    *,
    threshold: float = 0.5,
    weights: np.ndarray | None = None,
) -> ClassificationMatrix:
    """Confusion matrix at a fixed PD threshold (deterministic).

    A routed row is predicted "bad" iff ``pd_per_leaf[leaf_id] >= threshold``,
    "good" otherwise. Unrouted rows (``leaf_assignment == -1``) join no cell;
    they only count in ``n_excluded``.

    tp = pred bad & real bad; tn = pred good & real good;
    fp = pred bad & real good; fn = pred good & real bad.
    ``bad_capture_rate`` mirrors ``recall`` with credit-scoring naming.

    Phase 3.2.g: ``weights`` (keyword-only, default None) adds the
    parallel ``w_*`` cells and ratios with weighted mass
    (Heeringa, West & Berglund 2010, §5.3). With ``weights=None`` the
    ``w_*`` values match their integer counterparts exactly (parity).

    Raises ``ValueError`` when ``threshold`` lies outside [0, 1].
    """
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(
            f"[reporting] threshold must lie in [0, 1]; got {threshold!r}"
        )

    routed, leaf_ids, y_r = _validated_routed(
        leaf_assignment, y, "classification_matrix"
    )
    n_excluded = int((~routed).sum())
    w = _validated_weights(
        weights, len(np.asarray(leaf_assignment)), "classification_matrix"
    )
    w_r = w[routed] if w is not None else np.ones(int(leaf_ids.size), dtype=float)

    pd_row = np.fromiter(
        (float(pd_per_leaf[int(lid)]) for lid in leaf_ids),
        dtype=float,
        count=int(leaf_ids.size),
    )
    pred_bad = pd_row >= threshold
    real_bad = y_r == 1
    tp = int(np.count_nonzero(pred_bad & real_bad))
    tn = int(np.count_nonzero(~pred_bad & ~real_bad))
    fp = int(np.count_nonzero(pred_bad & ~real_bad))
    fn = int(np.count_nonzero(~pred_bad & real_bad))

    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
    f1 = (
        None
        if precision is None or recall is None or (precision + recall) == 0.0
        else 2.0 * precision * recall / (precision + recall)
    )

    # Celdas ponderadas (con weights=None, w_r son unos: paridad exacta).
    w_tp = float(w_r[pred_bad & real_bad].sum())
    w_tn = float(w_r[~pred_bad & ~real_bad].sum())
    w_fp = float(w_r[pred_bad & ~real_bad].sum())
    w_fn = float(w_r[~pred_bad & real_bad].sum())
    w_precision = w_tp / (w_tp + w_fp) if (w_tp + w_fp) > 0.0 else None
    w_recall = w_tp / (w_tp + w_fn) if (w_tp + w_fn) > 0.0 else None
    w_f1 = (
        None
        if w_precision is None or w_recall is None
        or (w_precision + w_recall) == 0.0
        else 2.0 * w_precision * w_recall / (w_precision + w_recall)
    )

    # Fase 3.5.b (D19): accuracy tambien en K=2 (traza 2x2 / n_total).
    n_total = int(leaf_ids.size)
    accuracy = (tp + tn) / n_total if n_total > 0 else None

    return ClassificationMatrix(
        threshold=float(threshold),
        n_total=n_total,
        n_good=tn + fp,
        n_bad=tp + fn,
        tp=tp,
        tn=tn,
        fp=fp,
        fn=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        bad_capture_rate=recall,
        n_excluded=n_excluded,
        w_tp=w_tp,
        w_tn=w_tn,
        w_fp=w_fp,
        w_fn=w_fn,
        w_precision=w_precision,
        w_recall=w_recall,
        w_f1=w_f1,
        w_bad_capture_rate=w_recall,
        accuracy=accuracy,
    )


def build_classification_matrix_multiclass(
    leaf_assignment: np.ndarray,
    y: np.ndarray,
    pd_per_leaf: dict[int, tuple[float, ...]],
    *,
    weights: np.ndarray | None = None,
) -> ClassificationMatrix:
    """Multiclass classification matrix (Phase 3.5.b, decision D19).

    Para cada fila enrutable, la clase predicha es la de maximo valor en
    el vector ``pd_per_leaf[leaf_id]`` (argmax con desempate por indice
    ascendente). Construye la matriz K x K de clase verdadera (filas)
    contra clase predicha (columnas), en orden canonico.

    Los campos binarios heredados del DTO (tp, tn, fp, fn, precision,
    recall, f1, bad_capture_rate, n_good, n_bad) se pueblan con la clase
    de interes (indice 0) como positivo y todas las demas clases
    agrupadas como negativo. Contrato D19: un consumidor binario del
    panel sigue leyendo lo que espera, con la clase de interes como
    "positivo".

    ``threshold`` del DTO se registra como ``float('nan')`` porque no
    aplica en el path multiclase (la asignacion es argmax).

    En modo ponderado, las celdas de la matriz y los ratios por clase
    usan sumas de pesos (paridad con conteos si ``weights=None``).
    """
    who = "classification_matrix_multiclass"
    if not pd_per_leaf:
        raise ValueError(f"[reporting] {who}: pd_per_leaf vacio")
    K = len(next(iter(pd_per_leaf.values())))
    if K < 2:
        raise ValueError(f"[reporting] {who}: K={K} invalido (>= 2)")
    for lid, vec in pd_per_leaf.items():
        if len(vec) != K:
            raise ValueError(
                f"[reporting] {who}: pd_per_leaf[{lid}] tiene longitud "
                f"{len(vec)} != K={K}"
            )

    routed, leaf_ids, y_r = _validated_routed(
        leaf_assignment, y, who, n_classes=K
    )
    n_excluded = int((~routed).sum())
    n_total = int(leaf_ids.size)
    w = _validated_weights(weights, len(np.asarray(leaf_assignment)), who)
    w_r = w[routed] if w is not None else np.ones(n_total, dtype=float)

    # Matriz K x K: filas = clase verdadera, columnas = clase predicha.
    pd_mat = {
        int(lid): tuple(float(v) for v in vec)
        for lid, vec in pd_per_leaf.items()
    }
    cm = np.zeros((K, K), dtype=int)
    cm_w = np.zeros((K, K), dtype=float)
    for i in range(n_total):
        pred = int(np.argmax(pd_mat[int(leaf_ids[i])]))
        true_k = int(y_r[i])
        cm[true_k, pred] += 1
        cm_w[true_k, pred] += w_r[i]

    row_sum = cm.sum(axis=1)     # verdaderos por clase
    col_sum = cm.sum(axis=0)     # predichos por clase
    w_row_sum = cm_w.sum(axis=1)
    w_col_sum = cm_w.sum(axis=0)

    def _prf(diag: float, col: float, row: float):
        """(precision, recall, f1) con None cuando el denominador es 0."""
        p = None if col <= 0 else float(diag) / float(col)
        r = None if row <= 0 else float(diag) / float(row)
        f = (
            None
            if p is None or r is None or (p + r) == 0.0
            else 2.0 * p * r / (p + r)
        )
        return p, r, f

    precision_c: list[float | None] = []
    recall_c: list[float | None] = []
    f1_c: list[float | None] = []
    w_precision_c: list[float | None] = []
    w_recall_c: list[float | None] = []
    w_f1_c: list[float | None] = []
    for k in range(K):
        p, r, f = _prf(cm[k, k], col_sum[k], row_sum[k])
        precision_c.append(p)
        recall_c.append(r)
        f1_c.append(f)
        wp, wr, wf = _prf(cm_w[k, k], w_col_sum[k], w_row_sum[k])
        w_precision_c.append(wp)
        w_recall_c.append(wr)
        w_f1_c.append(wf)

    accuracy = (
        float(np.trace(cm)) / n_total if n_total > 0 else None
    )
    w_total_mass = float(cm_w.sum())
    w_accuracy = (
        float(np.trace(cm_w)) / w_total_mass if w_total_mass > 0.0 else None
    )

    # Campos binarios heredados: clase de interes (indice 0) como
    # "positivo", resto agrupado como "negativo" (D19).
    tp = int(cm[0, 0])
    fp = int(col_sum[0]) - tp
    fn = int(row_sum[0]) - tp
    tn = n_total - tp - fp - fn
    precision, recall, f1 = precision_c[0], recall_c[0], f1_c[0]
    w_tp = float(cm_w[0, 0])
    w_fp = float(w_col_sum[0]) - w_tp
    w_fn = float(w_row_sum[0]) - w_tp
    w_tn = w_total_mass - w_tp - w_fp - w_fn
    w_precision, w_recall, w_f1 = w_precision_c[0], w_recall_c[0], w_f1_c[0]

    return ClassificationMatrix(
        threshold=float("nan"),
        n_total=n_total,
        n_good=tn + fp,
        n_bad=tp + fn,
        tp=tp,
        tn=tn,
        fp=fp,
        fn=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        bad_capture_rate=recall,
        n_excluded=n_excluded,
        w_tp=w_tp,
        w_tn=w_tn,
        w_fp=w_fp,
        w_fn=w_fn,
        w_precision=w_precision,
        w_recall=w_recall,
        w_f1=w_f1,
        w_bad_capture_rate=w_recall,
        confusion_matrix=tuple(tuple(int(v) for v in row) for row in cm),
        n_per_class=tuple(int(v) for v in row_sum),
        precision_per_class=tuple(precision_c),
        recall_per_class=tuple(recall_c),
        f1_per_class=tuple(f1_c),
        accuracy=accuracy,
        w_confusion_matrix=tuple(
            tuple(float(v) for v in row) for row in cm_w
        ),
        w_n_per_class=tuple(float(v) for v in w_row_sum),
        w_precision_per_class=tuple(w_precision_c),
        w_recall_per_class=tuple(w_recall_c),
        w_f1_per_class=tuple(w_f1_c),
        w_accuracy=w_accuracy,
    )
