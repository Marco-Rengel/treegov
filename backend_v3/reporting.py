"""Reporting layer (TreeGov, backend_v3): flat report DTOs, Qt-free.

White-box (numpy only) and deterministic. Two report families:

  * OOS/OOT flat DTO (Phase 2.3.d): ``build_oos_oot_report``.
  * Gains table and classification matrix over a fitted ``TreeModel``:
    ``build_gains_table`` and ``build_classification_matrix``.

KS / AUC / Gini reuse the exact formulas documented in
``backend_v3.validation`` (KS over the descending score accumulation; AUC by
Wilcoxon-Mann-Whitney with mid-ranks, Hanley & McNeil 1982; Gini = 2*AUC - 1),
reimplemented here on per-row PD: the Hosmer-Lemeshow ``n_groups`` logic of
``compute_oos_metrics`` does not apply to gains tables.

Phase 3.1 (multiclass): both report functions remain binary-only.
The model's class_labels must have exactly 2 entries; otherwise
build_gains_table raises ValueError. build_classification_matrix
delegates the K > 2 check to its caller (Session). Multiclass
reports are scheduled for Phase 3.5.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

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
]


def build_oos_oot_report(st: SessionState) -> dict[str, Any] | None:
    """Devuelve None si no hay modelo; si no, DTO con claves 'oos'/'oot' (None o asdict)."""
    if st.tree is None:
        return None
    return {
        "oos": None if st.oos_metrics is None else asdict(st.oos_metrics),
        "oot": None if st.oot_report is None else asdict(st.oot_report),
    }


@dataclass(frozen=True)
class GainsRow:
    """One immutable gains-table line (leaf or bucket).

    ``*_cum`` accumulates from the best (lowest-PD) row downwards;
    ``*_decum`` accumulates from the worst row upwards, current row included.
    ``lift_cum = bad_rate_cum / bad_rate_global`` (NaN when the global bad
    rate is 0, i.e. no events among the routed rows).
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


@dataclass(frozen=True)
class GainsTableResult:
    """Gains table over the routed rows of a scored sample.

    ``n_total`` / ``n_good`` / ``n_bad`` count routed rows only; unrouted rows
    (``leaf_assignment == -1``) appear solely in ``n_excluded``.
    ``ks`` / ``auc`` / ``gini`` are recomputed on per-row PD with the
    ``backend_v3.validation`` formulas; ``None`` when a class is absent.
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


@dataclass(frozen=True)
class ClassificationMatrix:
    """Confusion matrix at a fixed PD threshold (credit-scoring naming).

    ``bad_capture_rate`` is an explicit alias of ``recall`` (same value).
    Ratio fields are ``None`` when their denominator is 0. Counts cover
    routed rows only; unrouted rows appear solely in ``n_excluded``.
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


def _validated_routed(
    leaf_assignment: np.ndarray, y: np.ndarray, who: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return ``(routed_mask, leaf_ids_routed, y_routed)`` after basic checks."""
    assign = np.asarray(leaf_assignment, dtype=int)
    yv = np.asarray(y, dtype=int)
    if assign.shape != yv.shape or assign.ndim != 1:
        raise ValueError(
            f"[reporting] {who}: leaf_assignment and y must be 1-D vectors "
            "of equal length"
        )
    if not np.isin(yv, (0, 1)).all():
        raise ValueError(f"[reporting] {who}: y must be binary (0/1)")
    routed = assign >= 0
    return routed, assign[routed], yv[routed]


def _discrimination_metrics(
    pd_row: np.ndarray, y: np.ndarray, n_good: int, n_bad: int
) -> tuple[float | None, float | None, float | None]:
    """Return ``(ks, auc, gini)`` on per-row PD; ``(None, None, None)`` when a
    class is absent.

    Exact formulas of ``backend_v3.validation`` (see its module docstring):
    KS over the descending score accumulation covering whole tie blocks; AUC
    by Wilcoxon-Mann-Whitney with mid-ranks (Hanley & McNeil 1982);
    Gini = 2*AUC - 1.
    """
    if n_good == 0 or n_bad == 0:
        return None, None, None

    # KS: descending score, cumulative counts taken at the END of each tie
    # block (the threshold covers the whole block).
    orden = np.argsort(-pd_row, kind="mergesort")
    ys = y[orden]
    ps = pd_row[orden]
    finales = np.flatnonzero(np.r_[ps[1:] != ps[:-1], True])
    tp_t = np.cumsum(ys)[finales]
    fp_t = np.cumsum(1 - ys)[finales]
    ks = float(np.max(np.abs(tp_t / n_bad - fp_t / n_good)))

    # AUC by Wilcoxon-Mann-Whitney with mid-ranks (vectorized).
    n = int(pd_row.size)
    pos = np.argsort(pd_row, kind="mergesort")
    p_sorted = pd_row[pos]
    cambios = np.flatnonzero(np.r_[True, p_sorted[1:] != p_sorted[:-1], True])
    starts, ends = cambios[:-1], cambios[1:]
    mids = (starts + ends + 1) / 2.0  # mean of 1-based ranks per tie group
    ranks = np.empty(n, dtype=float)
    ranks[pos] = np.repeat(mids, ends - starts)
    r1 = float(ranks[y == 1].sum())
    auc = (r1 - n_bad * (n_bad + 1) / 2.0) / (n_bad * n_good)
    return ks, float(auc), float(2.0 * auc - 1.0)


def build_gains_table(
    model: TreeModel,
    leaf_assignment: np.ndarray,
    y: np.ndarray,
    *,
    by: str = "leaf",
    n_buckets: int = 10,
    tie: str = "preserve",
    seed: int | None = None,
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
    """
    if by not in ("leaf", "bucket"):
        raise ValueError(f"[reporting] invalid by={by!r} ('leaf'/'bucket')")
    if tie not in ("preserve", "random"):
        raise ValueError(f"[reporting] invalid tie={tie!r} ('preserve'/'random')")
    if n_buckets < 1:
        raise ValueError(f"[reporting] n_buckets must be >= 1; got {n_buckets}")
    if tie == "random" and seed is None:
        raise ValueError("[reporting] tie='random' requires an explicit seed")

    if len(model.class_labels) != 2:
        raise ValueError(
            f"[reporting] gains table is binary-only in Phase 3.1 "
            f"(model has K={len(model.class_labels)} classes). "
            "Multiclass reports are scheduled for Phase 3.5."
        )

    routed, leaf_ids, y_r = _validated_routed(leaf_assignment, y, "gains_table")
    n_excluded = int((~routed).sum())
    n_total = int(leaf_ids.size)
    if n_total == 0:
        raise ValueError("[reporting] gains table undefined: no routed rows")

    pd_per_node = np.fromiter(
        (nd.pd_final[0] for nd in model.nodes),
        dtype=float, count=len(model.nodes),
    )
    pd_row = pd_per_node[leaf_ids]

    n_bad = int(y_r.sum())
    n_good = n_total - n_bad
    bad_rate_global = n_bad / n_total

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
    stats: list[tuple[str, float, int, int, int]] = []
    for label, pd_val, idx in groups:
        n_g = int(idx.size)
        bad_g = int(y_r[idx].sum())
        stats.append((label, pd_val, n_g, n_g - bad_g, bad_g))

    # suffix totals (current row included) for the decumulative columns
    suffix_n = suffix_good = suffix_bad = 0
    suffixes: list[tuple[int, int, int]] = []
    for _, _, n_g, good_g, bad_g in reversed(stats):
        suffix_n += n_g
        suffix_good += good_g
        suffix_bad += bad_g
        suffixes.append((suffix_n, suffix_good, suffix_bad))
    suffixes.reverse()

    rows: list[GainsRow] = []
    cum_n = cum_good = cum_bad = 0
    for (label, pd_val, n_g, good_g, bad_g), (dn, dgood, dbad) in zip(stats, suffixes):
        cum_n += n_g
        cum_good += good_g
        cum_bad += bad_g
        bad_rate_cum = cum_bad / cum_n
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
            )
        )

    ks, auc, gini = _discrimination_metrics(pd_row, y_r, n_good, n_bad)

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
    )


def build_classification_matrix(
    leaf_assignment: np.ndarray,
    y: np.ndarray,
    pd_per_leaf: dict[int, float],
    *,
    threshold: float = 0.5,
) -> ClassificationMatrix:
    """Confusion matrix at a fixed PD threshold (deterministic).

    A routed row is predicted "bad" iff ``pd_per_leaf[leaf_id] >= threshold``,
    "good" otherwise. Unrouted rows (``leaf_assignment == -1``) join no cell;
    they only count in ``n_excluded``.

    tp = pred bad & real bad; tn = pred good & real good;
    fp = pred bad & real good; fn = pred good & real bad.
    ``bad_capture_rate`` mirrors ``recall`` with credit-scoring naming.

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

    return ClassificationMatrix(
        threshold=float(threshold),
        n_total=int(leaf_ids.size),
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
    )
