"""Interactive tree viewer (TreeGov GUI, Phase 2.2).

Clean room: this module only READS the frozen TreeModel / TreeNode /
SplitConfig objects produced by backend_v3. There is NO analytical logic
here: every statistic shown (n, n_events, pd_jeffreys, pd_final, split
fields) is precomputed in the backend (tree_builder); the viewer merely
formats it for display. Type annotations of backend classes live under
TYPE_CHECKING: the module never imports backend_v3 at runtime.

Layout convention (tidy tree, simplified): terminal nodes occupy consecutive
integer slots respecting child_ids order (BFS ids are already
deterministic); every internal node is centered over its outermost
children; y = depth. Deterministic by construction. No subtree
compaction: unnecessary under the TreeBuilder pre-pruning regime
(max_depth <= 10); KISS and trivially auditable.

  Citation: Reingold, E.M. & Tilford, J.S. (1981). Tidier Drawings of
  Trees. IEEE Transactions on Software Engineering, SE-7(2), 223-228.

Scene colors come from frontend_v3.theme.PALETTES: QGraphicsItems are NOT
widgets and therefore ignore the application QSS; the QSS still styles the
panel chrome (header, labels, buttons) as usual.

Approved design decisions (Phase 2.2 audit):
  - OBS 1: a large-tree warning is shown in the panel header when
    n_nodes > LARGE_TREE_THRESHOLD (uncompacted layouts grow wide).
  - OBS 2: ScrollHandDrag panning on left-button drag.
  - OBS 3: Antialiasing | TextAntialiasing render hints.
  - OBS 4: TreePanel.refresh() is a FULL re-render (same pattern as
    wizard.retranslate_ui), not a partial recolor; selection survives
    rebuilds via node_id.
  - Zoom is idempotent: setTransform from scratch on every change,
    clamped to [ZOOM_MIN, ZOOM_MAX]; never an accumulated product.

Phase 3.1 (multiclass): n_events, pd_jeffreys and pd_final are
per-class tuples (index 0 = class of interest). The node box draws
every class row in canonical order.

Node rendering: each NodeItem is painted ENTIRELY with QPainter (no
HTML): a fixed-geometry "audit sheet" (NODE_W x NODE_H) with a 26 px
header band (predictor name / terminal-node semaphore), per-class body rows
(square + label + % + n), a bold Total (N) row, a stacked bar
proportional to n_events (class colors) and a 20 px footer band (Gini /
split stats). Fixed geometry kills the HTML auto-fit slack for good.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QShortcut,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from frontend_v3.i18n import language_bus, tr, tr_term
from frontend_v3.theme import PALETTES

if TYPE_CHECKING:
    from backend_v3.tree_builder import TreeModel, TreeNode

__all__ = [
    "TreePanel",
    "TreeScene",
    "TreeView",
    "NodeItem",
    "model_summary_lines",
    "node_detail_lines",
]

# --- layout geometry (module constants, documented) -------------------------
NODE_W = 220.0          # node box width (scene units == px at zoom 1.0)
NODE_H = 126.0          # node box height (FIXED: the box is painted with
                        # QPainter at exactly NODE_W x NODE_H — header band
                        # 26 px + body rows + Total row + stacked bar 10 px
                        # + footer band 20 px; no auto-fit, no dead space)
H_GAP = 24.0            # horizontal gap between terminal-node slots
V_GAP = 64.0            # vertical gap between depth layers (elbow band +
                        # edge-label room)
EDGE_LABEL_MAX = 24     # max characters on a categorical edge label
SCENE_MARGIN = 20.0     # padding around itemsBoundingRect for sceneRect
ZOOM_MIN = 0.10         # idempotent zoom clamp (out)
ZOOM_MAX = 4.00         # idempotent zoom clamp (in)
ZOOM_STEP = 1.15        # multiplicative step per zoom action / wheel notch
# Phase 3.11.a: legibility floor for AUTO-fit only. fitInView can propose
# a tiny factor on wide trees (illegible nodes); the fit never goes below
# 50%. Manual zoom-out is unaffected (still allowed down to ZOOM_MIN).
ZOOM_FIT_MIN = 0.50
# OBS 1 (media, audit 2.2): beyond this node count the uncompacted layout
# gets too wide for comfortable reading; warn in the header (no truncation,
# the model is always rendered in full for auditability).
LARGE_TREE_THRESHOLD = 200


# ---------------------------------------------------------------------------
# Pure helpers (stdlib only; unit-testable without a QApplication)
# ---------------------------------------------------------------------------


def _layout_tree(
    model: TreeModel, node_h: float = NODE_H
) -> dict[int, tuple[float, float]]:
    """Deterministic tidy layout: node_id -> (x, y) of the box top-left.

    Post-order DFS over child_ids. Terminal nodes take consecutive integer slots;
    an internal node sits at the midpoint of its outermost children
    (Reingold & Tilford 1981, principles 1-4, simplified). The same model
    always yields the same dict (identity verified in the test suite).

    `node_h` is the per-layer box height; the scene passes the fixed
    NODE_H (QPainter node design). The default keeps the pure function
    standalone-testable.
    """
    pos: dict[int, tuple[float, float]] = {}
    next_slot = 0.0

    def visit(node_id: int) -> float:
        nonlocal next_slot
        node = model.nodes[node_id]
        if node.is_leaf:
            slot = next_slot
            next_slot += 1.0
        else:
            xs = [visit(cid) for cid in node.child_ids]
            slot = (xs[0] + xs[-1]) / 2.0
        pos[node_id] = (
            slot * (NODE_W + H_GAP),
            float(node.depth) * (node_h + V_GAP),
        )
        return slot

    visit(model.root_id)
    return pos


def _fmt_num(x: float) -> str:
    """Compact audit format (same .6g convention as types.SplitConfig)."""
    return format(float(x), ".6g")


def _fmt_pct(x: float) -> str:
    """PD display format (presentation scaling of a backend value)."""
    return f"{float(x) * 100:.2f}%"


# Audit-sheet node design (classic tree station, circa 2001), painted
# with QPainter: the node body is ALWAYS a white sheet — independent of
# the app theme — so it reads as an auditable document on the canvas.
# The sheet fill/text/grid colors are fixed neutrals (Google light
# palette), decoupled from PALETTES; the header band and the outer border
# DO read palette tokens (ACCENT / STATUS_* / BORDER).
_NODE_SHEET_BG = "#FFFFFF"     # sheet background (both themes)
_NODE_SHEET_FG = "#202124"     # sheet text (both themes)
_NODE_SHEET_BORDER = "#DADCE0" # sheet inner grid (footer separator)
_NODE_HEADER_FG = "#FFFFFF"    # header band text (white bold, both themes)

# Semaphore squares in the category column (classic tree station): class 0
# (class of interest) is red, the rest cycle green / blue / amber.
_CLASS_BAR_COLORS = ("#D32F2F", "#2E7D32", "#1A73E8", "#F29900")

# Display names for the footer statistic (backend statistic_name is a
# machine key: chi2 / f / gini_gain / variance_gain).
_STAT_DISPLAY = {
    "chi2": "Chi-square",
    "f": "F",
    "gini_gain": "Gini gain",
    "variance_gain": "Variance gain",
}


def _caption_text(node: TreeNode) -> str:
    """Header band text (top 26 px of the box): predictor name (internal)
    or empty string (terminal node — the header shows only "Node <id>")."""
    if node.is_leaf:
        return ""
    split = node.split
    return str(split.predictor) if split is not None else "Internal"


def _footer_text(node: TreeNode) -> str:
    """Footer band text (bottom 20 px of the box): split stats (internal)
    or node Gini (terminal node).

    The Gini shown is the node impurity derived from pd_final (display
    only, pandas-free); split stats are precomputed by the backend.
    """
    if node.is_leaf:
        gini = 1.0 - sum(p**2 for p in node.pd_final) if node.pd_final else 0.0
        return f"Gini: {gini:.3f}"
    split = node.split
    p_adj = (
        split.p_value_adjusted
        if split is not None and split.p_value_adjusted is not None
        else (split.p_value if split is not None else None)
    )
    p_str = f"{p_adj:.3g}" if p_adj is not None else "—"
    stat_name = (
        _STAT_DISPLAY.get(split.statistic_name, split.statistic_name)
        if split is not None
        else "—"
    )
    stat_str = (
        f"{split.statistic:.4g}"
        if split is not None and split.statistic is not None
        else "—"
    )
    text = f"Adj. P-value: {p_str} | {stat_name}: {stat_str}"
    if split is not None and split.df:
        text += f" | df: {split.df}"
    return text


def _edge_label(split, branch_index: int) -> str:
    """Short branch rule for the elbow connector; long groups are elided.

    Binned continuous splits (CHAID, split.bin_edges non-empty) resolve
    the "bin_<i>" labels of the branch to the real numeric cuts: bin i
    covers (bin_edges[i-1], bin_edges[i]], with bin 0 extending to -inf
    and bin len(bin_edges) extending to +inf.
    """
    if split is None:
        return ""
    if split.threshold is not None:
        t = _fmt_num(split.threshold)
        return f"≤ {t}" if branch_index == 0 else f"> {t}"
    group = (split.branches or ())[branch_index]
    if split.bin_edges:
        bins = [
            int(str(lbl)[4:]) for lbl in group if str(lbl).startswith("bin_")
        ]
        if bins:
            low = (
                float("-inf")
                if min(bins) == 0
                else split.bin_edges[min(bins) - 1]
            )
            high = (
                float("inf")
                if max(bins) == len(split.bin_edges)
                else split.bin_edges[max(bins)]
            )
            if low == float("-inf"):
                return f"≤ {_fmt_num(high)}"
            if high == float("inf"):
                return f"> {_fmt_num(low)}"
            return f"({_fmt_num(low)}, {_fmt_num(high)}]"
    text = "{" + ",".join(str(v) for v in group) + "}"
    if len(text) > EDGE_LABEL_MAX:
        text = text[: EDGE_LABEL_MAX - 1] + "…"
    return text


def node_detail_lines(node: TreeNode, mode: str = "BANKING") -> list[str]:
    """Properties-panel card for one node (read-only formatting)."""
    # TODO(zona_gris): el prompt 3.6.e.2 sustituía ambos labels por
    # tr_term("pd", mode), lo que en BANKING colapsaba "PD (Jeffreys)" y
    # "PD (final, ...)" en el mismo texto "PD" (pérdida de la distinción
    # Jeffreys/final y ruptura de la paridad visual BANKING del diseño
    # 3.6.e §5). Decisión conservadora: BANKING conserva las claves
    # clásicas; RESEARCH usa el término neutro con sufijo de distinción.
    if mode == "RESEARCH":
        lbl_pd_j = f"{tr_term('pd', mode)} (Jeffreys)"
        lbl_pd_f = f"{tr_term('pd', mode)} (final)"
    else:
        lbl_pd_j = tr("tree_prop_pd_jeffreys")
        lbl_pd_f = tr("tree_prop_pd_final")
    lines = [
        f"{tr('tree_prop_node')}: {node.node_id}",
        f"{tr('tree_prop_depth')}: {node.depth}",
        f"n: {node.n}",
        f"{tr('tree_node_events')}: {node.n_events[0]}",
        f"{lbl_pd_j}: {_fmt_num(node.pd_jeffreys[0])}",
        f"{lbl_pd_f}: {_fmt_num(node.pd_final[0])}",
    ]
    if node.pd_final[0] != node.pd_jeffreys[0]:
        lines.append(tr("tree_prop_floor_note"))
    if node.is_leaf:
        lines.append(
            f"{tr('tree_prop_terminal_reason')}: "
            f"{tr(f'tree_terminal_reason_{node.leaf_reason}')}"
        )
        return lines
    split = node.split
    assert split is not None
    lines.append(f"{tr('tree_prop_predictor')}: {split.predictor}")
    lines.append(
        f"{tr('tree_prop_statistic')}: "
        f"{split.statistic_name}={_fmt_num(split.statistic)}"
    )
    if split.df:
        lines.append(f"df: {split.df}")
    if split.p_value is not None:
        lines.append(f"p: {_fmt_num(split.p_value)}")
    if split.p_value_adjusted is not None:
        lines.append(
            f"p_adj (Bonferroni ×{split.bonferroni_multiplier}): "
            f"{_fmt_num(split.p_value_adjusted)}"
        )
    if split.impurity_gain is not None:
        lines.append(f"{tr('tree_prop_gain')}: {_fmt_num(split.impurity_gain)}")
    if split.threshold is not None:
        t = _fmt_num(split.threshold)
        lines.append(f"x ≤ {t} | x > {t}")
    else:
        for i, group in enumerate(split.branches or ()):
            text = "{" + ",".join(str(v) for v in group) + "}"
            lines.append(f"{tr('tree_prop_branch')} {i + 1}: {text}")
    return lines


def model_summary_lines(model: TreeModel, mode_label: str) -> list[str]:
    """Properties-panel card when no node is selected (model overview)."""
    n_nodes = len(model.nodes)
    n_terminal = sum(1 for nd in model.nodes if nd.is_leaf)
    max_depth = max(nd.depth for nd in model.nodes)
    return [
        f"{tr('tree_prop_method')}: {model.method}",
        f"{tr('tree_hdr_nodes')}: {n_nodes}",
        f"{tr('tree_hdr_nodes_terminal')}: {n_terminal}",
        f"{tr('tree_prop_depth')}: {max_depth}",
        f"{tr('tree_hdr_fp')}: {model.params_fingerprint}",
        f"{tr('status_mode')}: {mode_label}",
    ]


# ---------------------------------------------------------------------------
# Graphics items
# ---------------------------------------------------------------------------


class NodeItem(QGraphicsItem):
    """One node box painted ENTIRELY with QPainter (no HTML), with FIXED
    geometry NODE_W x NODE_H: the "audit sheet" is always white (#FFFFFF)
    on both themes.

    Bands (all INSIDE the bounding rect):
      - Header (26 px): "Node <id> — <predictor name>" (internal node,
        ACCENT band) or strictly "Node <id>" / "Nodo <id>" (terminal
        node, semaphore band by pd_final[0]: < 0.05 green, < 0.15
        orange, otherwise red); white bold text, elided to the box
        width.
      - Body: one row per class (semaphore square + label + % + n),
        a bold Total (N) row with a subtle separator above, and a
        stacked bar proportional to n_events (index 0 = class of
        interest/Bad -> red #D32F2F, index 1 = Good -> green #2E7D32;
        multiclass cycles _CLASS_BAR_COLORS).
      - Footer (20 px): node Gini (terminal nodes) or adjusted p-value + split
        statistic (internals), via the audited _footer_text helper; the
        band starts EXACTLY at NODE_H - 20 (no dead space below the bar).
    Selection: ACCENT border, width 3 (read from isSelected() in paint();
    the border is always drawn INSIDE the bounding rect, inset by half
    the pen width, so nothing is clipped).
    """

    NODE_W = NODE_W      # class constants: mirror the module layout values
    NODE_H = NODE_H
    HEADER_H = 26.0      # header band height (Node <id> / predictor)
    FOOTER_H = 20.0      # footer band height (Gini / split stats)
    ROW_H = 18.0         # body row height (shrinks if many classes)
    BAR_H = 10.0         # stacked-bar height (class distribution)
    SQ = 8.0             # semaphore square side in the body rows

    def __init__(
        self, node: TreeNode, palette: dict[str, str], pct_global: float,
        mode: str = "BANKING",
    ) -> None:
        super().__init__()
        self.node_id = node.node_id
        self._node = node
        self._palette = palette
        # Phase 3.6.e.2: modo de gobernanza (terminología del tooltip).
        self._mode = mode
        # Phase 3.11.b.5: cuota del nodo sobre la población raíz [0, 1]
        self._pct_global = pct_global
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setZValue(1.0)

        # Display strings precomputed once (the node is frozen).
        self._header = _caption_text(node)   # predictor (internal) / "" (terminal)
        # DECISIÓN (25/10/2026): el texto de cabecera es Node <id> /
        # Nodo <id>, vía tr(), para retraducción en caliente.
        # Ver design_decisions.md §18.5.
        if node.is_leaf:
            self._header_full = f"{tr('tree_prop_node')} {node.node_id}"
        else:
            self._header_full = (
                f"{tr('tree_prop_node')} {node.node_id} — {self._header}"
            )
        self._footer = _footer_text(node)    # Gini (terminal) / split stats
        self._total_n = f"{node.n:,}"        # Total (N) row, right column
        # Header band color: palette ACCENT for internal nodes; terminal-node
        # semaphore from pd_final[0] (class of interest).
        if node.is_leaf:
            p0 = float(node.pd_final[0]) if node.pd_final else 0.0
            if p0 < 0.05:
                token = "STATUS_OK"
            elif p0 < 0.15:
                token = "STATUS_WARN"
            else:
                token = "STATUS_CRIT"
        else:
            token = "ACCENT"
        self._header_color = QColor(palette[token])
        self._header_fg = QColor(_NODE_HEADER_FG)

        self._font_header = QFont()
        self._font_header.setPointSize(9)
        self._font_header.setBold(True)
        self._font_body = QFont()
        self._font_body.setPointSize(9)
        self._font_total = QFont()
        self._font_total.setPointSize(9)
        self._font_total.setBold(True)
        self._font_footer = QFont()
        self._font_footer.setPointSize(8)
        self.setToolTip("\n".join(node_detail_lines(node, self._mode)))

    # -- QGraphicsItem API ----------------------------------------------------

    def boundingRect(self) -> QRectF:
        return QRectF(0.0, 0.0, self.NODE_W, self.NODE_H)

    def paint(self, painter: QPainter, option, widget: QWidget | None = None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.NODE_W), float(self.NODE_H)
        sheet_bg = QColor(_NODE_SHEET_BG)
        sheet_fg = QColor(_NODE_SHEET_FG)

        # 1. audit sheet background (always white, both themes)
        painter.fillRect(QRectF(0.0, 0.0, w, h), QBrush(sheet_bg))

        # 2. header band (26 px) + white bold composite title
        #    "Node <id>" (terminal) / "Node <id> — <predictor>" (internal),
        #    elided to the box width with QFontMetrics ("…" on overflow).
        hh = float(self.HEADER_H)
        painter.fillRect(QRectF(0.0, 0.0, w, hh), QBrush(self._header_color))
        painter.setFont(self._font_header)
        painter.setPen(QPen(self._header_fg))
        header = painter.fontMetrics().elidedText(
            self._header_full, Qt.TextElideMode.ElideRight, int(w - 16.0)
        )
        painter.drawText(
            QRectF(8.0, 0.0, w - 16.0, hh),
            Qt.AlignmentFlag.AlignCenter,
            header,
        )

        # 3. body, BOTTOM-ANCHORED so the block sits snugly above the
        #    footer band: per-class rows, then the bold Total (N) row
        #    (subtle separator above), then the stacked bar.
        node = self._node
        k = len(node.class_labels)
        fh = float(self.FOOTER_H)
        sep_y = h - fh                             # footer top (NODE_H-20)
        bar_h = float(self.BAR_H)
        bar_y = sep_y - 4.0 - bar_h                # bar just above footer
        total_h = float(self.ROW_H)
        total_y = bar_y - 4.0 - total_h            # Total row above the bar
        rows_top = hh + 4.0
        avail = total_y - 2.0 - rows_top           # room for class rows
        row_h = min(self.ROW_H, avail / k) if k else avail
        painter.setFont(self._font_body)
        painter.setPen(QPen(sheet_fg))
        for c in range(k):
            ry = rows_top + c * row_h
            painter.fillRect(
                QRectF(8.0, ry + (row_h - self.SQ) / 2.0, self.SQ, self.SQ),
                QBrush(QColor(_CLASS_BAR_COLORS[c % len(_CLASS_BAR_COLORS)])),
            )
            label = painter.fontMetrics().elidedText(
                str(node.class_labels[c]), Qt.TextElideMode.ElideRight, 88
            )
            painter.drawText(
                QRectF(20.0, ry, 88.0, row_h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                label,
            )
            p_c = node.pd_final[c] if c < len(node.pd_final) else 0.0
            painter.drawText(
                QRectF(112.0, ry, 56.0, row_h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                f"{float(p_c) * 100:.1f}%",
            )
            k_c = node.n_events[c] if c < len(node.n_events) else 0
            painter.drawText(
                QRectF(172.0, ry, 40.0, row_h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                str(k_c),
            )

        # 3b. Total row: bold, subtle separator above, n right-aligned
        #     in the n column (same x as the per-class counts).
        #     Phase 3.11.b.5: la etiqueta lleva pct_global (n / n raíz) a 2
        #     decimales vía tr(); formato final "Total (<pct_global>) <n>".
        painter.fillRect(
            QRectF(8.0, total_y - 2.0, w - 16.0, 1.0),
            QBrush(QColor(_NODE_SHEET_BORDER)),
        )
        painter.setFont(self._font_total)
        painter.setPen(QPen(sheet_fg))
        texto_total = f"{tr('tree_node_total')} ({self._pct_global * 100:.2f})"
        painter.drawText(
            QRectF(20.0, total_y, 140.0, total_h),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            texto_total,
        )
        painter.drawText(
            QRectF(172.0, total_y, 40.0, total_h),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
            self._total_n,
        )

        # 3c. stacked bar: segment widths proportional to n_events (raw
        #     counts, canonical order: index 0 = class of interest/Bad in
        #     red #D32F2F, index 1 = Good in green #2E7D32; multiclass
        #     cycles _CLASS_BAR_COLORS). The last segment absorbs the
        #     rounding slack so the bar always ends exactly at the right
        #     edge. Skipped on degenerate n == 0 nodes.
        if k and node.n > 0:
            bar_x = 8.0
            bar_w = w - 16.0
            x = bar_x
            for c in range(k):
                k_c = node.n_events[c] if c < len(node.n_events) else 0
                if c == k - 1:
                    seg_w = bar_x + bar_w - x    # absorb rounding slack
                else:
                    seg_w = bar_w * (k_c / node.n)
                painter.fillRect(
                    QRectF(x, bar_y, seg_w, bar_h),
                    QBrush(
                        QColor(_CLASS_BAR_COLORS[c % len(_CLASS_BAR_COLORS)])
                    ),
                )
                x += seg_w
            # subtle frame around the bar (audit-sheet grid style)
            painter.setPen(QPen(QColor(_NODE_SHEET_BORDER), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(
                QRectF(bar_x + 0.5, bar_y + 0.5, bar_w - 1.0, bar_h - 1.0)
            )

        # 4. footer band (20 px): separator + Gini (terminal) / split stats.
        #    The band starts EXACTLY at NODE_H - 20 (sep_y computed in
        #    section 3), so no dead space remains below the stacked bar.
        # DECISIÓN (25/10/2026): el footer de nodos terminales muestra
        # solo Gini. El KS no se expone en TreeNode; añadirlo requeriría
        # un campo nuevo en backend. Ver design_decisions.md §18.6.
        painter.fillRect(
            QRectF(0.0, sep_y, w, 1.0), QBrush(QColor(_NODE_SHEET_BORDER))
        )
        painter.setFont(self._font_footer)
        painter.setPen(QPen(sheet_fg))
        footer = painter.fontMetrics().elidedText(
            self._footer, Qt.TextElideMode.ElideRight, int(w - 16.0)
        )
        painter.drawText(
            QRectF(8.0, sep_y, w - 16.0, float(self.FOOTER_H)),
            Qt.AlignmentFlag.AlignCenter,
            footer,
        )

        # 5. border, ALWAYS inside the bounding rect (inset half pen width)
        if self.isSelected():
            pen_w, token = 3.0, "ACCENT"
        else:
            pen_w, token = 1.0, "BORDER"
        painter.setPen(QPen(QColor(self._palette[token]), pen_w))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        inset = pen_w / 2.0
        painter.drawRect(QRectF(inset, inset, w - pen_w, h - pen_w))


class TreeScene(QGraphicsScene):
    """Scene holding node boxes and elbow connectors.

    Emits node_selected(node_id) on single selection; selection_cleared
    whenever no NodeItem remains selected (drives the model summary in the
    properties panel).
    """

    node_selected = Signal(int)
    selection_cleared = Signal()
    # Phase 3.11.d.2: clic derecho sobre un NodeItem (menú contextual del
    # analista). La emite TreeView.contextMenuEvent; MainWindow la
    # captura y construye el QMenu (Grow / Prune / ...).
    node_context_menu = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: dict[int, NodeItem] = {}
        # Phase 3.11.a: the scene background follows the ACTIVE theme BG
        # (graphics scenes ignore the application QSS). Default = light,
        # matching TreePanel._palette; refreshed on every rebuild.
        self.setBackgroundBrush(QBrush(QColor(PALETTES["light"]["BG"])))
        self.selectionChanged.connect(self._emit_selected)

    # -- build ---------------------------------------------------------------

    def build_from_model(
        self, model: TreeModel, palette: dict[str, str],
        mode: str = "BANKING",
    ) -> None:
        """Rebuild every item from the frozen model (single render path)."""
        self.clear()
        self._items.clear()
        self.setBackgroundBrush(QBrush(QColor(palette["BG"])))
        # Fixed geometry (QPainter node design): every box is EXACTLY
        # NODE_W x NODE_H, so the layout uses the module constants
        # directly — no content-measurement probe.
        pos = _layout_tree(model, node_h=NODE_H)

        # edges first (z=0, below the node boxes at z=1). Line color is the
        # palette BORDER token: legible on both themes (light grey on dark
        # scene BG, dark grey on light scene BG).
        edge_pen = QPen(QColor(palette["BORDER"]), 1)
        label_brush = QBrush(QColor(palette["DISABLED"]))
        for node in model.nodes:
            if node.is_leaf:
                continue
            x0, y0 = pos[node.node_id]
            # Fixed box width: the connector centres exactly on the box.
            x0c = x0 + NODE_W / 2.0
            # The elbow exits the BOTTOM edge of the parent box and arrives
            # at the TOP edge of the child box: header and footer bands now
            # live INSIDE the box, so there are no outside bands to avoid.
            y0b = y0 + NODE_H
            for bi, cid in enumerate(node.child_ids):
                x1, y1 = pos[cid]
                x1c = x1 + NODE_W / 2.0
                y1t = y1
                mid_y = (y0b + y1t) / 2.0
                path = QPainterPath(QPointF(x0c, y0b))
                path.lineTo(x0c, mid_y)
                path.lineTo(x1c, mid_y)
                path.lineTo(x1c, y1t)
                edge = QGraphicsPathItem(path)
                edge.setPen(edge_pen)
                edge.setZValue(0.0)
                self.addItem(edge)
                # Cut label (e.g. "≤ 1", "> 1") centered on the elbow.
                label = self.addSimpleText(_edge_label(node.split, bi))
                label.setBrush(label_brush)
                lr = label.boundingRect()
                label.setPos((x0c + x1c - lr.width()) / 2.0, mid_y - lr.height())

        # Phase 3.11.b.5: cuota de cada nodo sobre la población raíz
        total_n = float(model.nodes[model.root_id].n)
        for node in model.nodes:
            pct = (node.n / total_n) if total_n > 0 else 0.0
            item = NodeItem(node, palette, pct, mode)
            x, y = pos[node.node_id]
            item.setPos(x, y)
            self.addItem(item)
            self._items[node.node_id] = item
        self.setSceneRect(
            self.itemsBoundingRect().adjusted(
                -SCENE_MARGIN, -SCENE_MARGIN, SCENE_MARGIN, SCENE_MARGIN
            )
        )

    # -- selection -------------------------------------------------------------

    def select_node(self, node_id: int) -> None:
        self.clearSelection()
        item = self._items.get(node_id)
        if item is not None:
            item.setSelected(True)

    def selected_node_id(self) -> int | None:
        for item in self.selectedItems():
            if isinstance(item, NodeItem):
                return int(item.node_id)
        return None

    def _emit_selected(self) -> None:
        sel = self.selected_node_id()
        if sel is None:
            self.selection_cleared.emit()
        else:
            self.node_selected.emit(sel)


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


class TreeView(QGraphicsView):
    """QGraphicsView with Ctrl+wheel / Ctrl+- / Ctrl++ / Ctrl+0 zoom.

    Zoom is idempotent (OBS-approved): every change rewrites the transform
    from scratch via setTransform, clamped to [ZOOM_MIN, ZOOM_MAX]; there is
    no accumulated floating-point product.
    """

    zoom_changed = Signal(float)

    def __init__(self, scene: TreeScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self._scene = scene
        self._zoom = 1.0
        # OBS 2 (audit 2.2): fluid panning with left-button drag
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        # OBS 3 (audit 2.2): crisp edges/text under zoom
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        ctx = Qt.ShortcutContext.WidgetWithChildrenShortcut
        for key, slot in (
            ("Ctrl++", self.zoom_in),
            ("Ctrl+-", self.zoom_out),
            ("Ctrl+0", self.zoom_fit),
        ):
            sc = QShortcut(QKeySequence(key), self, context=ctx)
            sc.activated.connect(slot)

    # -- zoom API ---------------------------------------------------------------

    def zoom_factor(self) -> float:
        return self._zoom

    def zoom_in(self) -> None:
        self._set_zoom(self._zoom * ZOOM_STEP)

    def zoom_out(self) -> None:
        self._set_zoom(self._zoom / ZOOM_STEP)

    def zoom_fit(self) -> None:
        """Fit the whole tree in the viewport (Ctrl+0); factor 1.0 if empty."""
        rect = self.scene().sceneRect()
        vw, vh = self.viewport().width(), self.viewport().height()
        if rect.isNull() or rect.width() <= 0 or vw <= 0 or vh <= 0:
            self._set_zoom(1.0)
            return
        self.resetTransform()
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        # H12: the fitted factor must respect [ZOOM_MIN, ZOOM_MAX]
        # Phase 3.11.a: ...and the legibility floor ZOOM_FIT_MIN (50%)
        factor = self.transform().m11()
        self._set_zoom(max(factor, ZOOM_FIT_MIN))

    def _set_zoom(self, factor: float) -> None:
        self._zoom = max(ZOOM_MIN, min(ZOOM_MAX, float(factor)))
        self.setTransform(QTransform().scale(self._zoom, self._zoom))
        self.zoom_changed.emit(self._zoom)

    # -- Qt overrides -------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            steps = event.angleDelta().y() / 120.0
            if steps:
                self._set_zoom(self._zoom * (ZOOM_STEP ** steps))
            event.accept()
            return
        super().wheelEvent(event)

    def contextMenuEvent(self, event) -> None:
        """Clic derecho sobre el canvas (Phase 3.11.d.2).

        Si el item bajo el cursor es un NodeItem, emite
        TreeScene.node_context_menu(node_id) y acepta el evento; si no,
        delega en la implementación base (sin menú).
        """
        item = self.itemAt(event.pos())
        if isinstance(item, NodeItem):
            self._scene.node_context_menu.emit(item.node_id)
            event.accept()
        else:
            super().contextMenuEvent(event)


# ---------------------------------------------------------------------------
# Panel (tab widget content)
# ---------------------------------------------------------------------------


class TreePanel(QWidget):
    """Tree tab: header (model id), toolbar (zoom), TreeView.

    Holds no analytical state: only the frozen TreeModel reference handed
    by MainWindow. Live retranslation arrives via language_bus (the panel
    rebuilds its scene texts, preserving selection by node_id).
    """

    node_selected = Signal(int)
    selection_cleared = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model: TreeModel | None = None
        self._mode_label: str = ""
        # Phase 3.6.e.2: modo de gobernanza del modelo entrenado (fija la
        # terminología de los tooltips; BANKING por defecto = paridad).
        self._mode: str = "BANKING"
        self._palette: dict[str, str] = PALETTES["light"]

        layout = QVBoxLayout(self)
        self._lbl_header = QLabel()
        self._lbl_header.setObjectName("panelTitle")  # reuse accent style
        self._lbl_warning = QLabel()
        self._lbl_warning.setObjectName("treeLargeWarning")  # QSS accent rule
        self._lbl_warning.setVisible(False)
        layout.addWidget(self._lbl_header)
        layout.addWidget(self._lbl_warning)

        bar = QHBoxLayout()
        self._btn_out = QPushButton("−")
        self._btn_in = QPushButton("+")
        self._btn_fit = QPushButton()
        self._lbl_zoom = QLabel()
        for w in (self._btn_out, self._btn_in, self._btn_fit):
            w.setEnabled(False)
            bar.addWidget(w)
        bar.addWidget(self._lbl_zoom)
        bar.addStretch(1)
        layout.addLayout(bar)

        self._scene = TreeScene(self)
        self._view = TreeView(self._scene, self)
        layout.addWidget(self._view, 1)

        self._btn_in.clicked.connect(self._view.zoom_in)
        self._btn_out.clicked.connect(self._view.zoom_out)
        self._btn_fit.clicked.connect(self._view.zoom_fit)
        self._view.zoom_changed.connect(self._on_zoom_changed)
        self._scene.node_selected.connect(self.node_selected)
        self._scene.selection_cleared.connect(self.selection_cleared)

        language_bus.language_changed.connect(self._on_language_changed)
        self.retranslate_ui()

    # -- public API ---------------------------------------------------------------

    def set_model(self, model: TreeModel, governance_mode: str) -> None:
        """Bind the (frozen) trained model and render it at 100% zoom.

        Phase 3.11.a: the initial view is a legible fixed scale (1.0)
        instead of auto-fit (a wide tree rendered tiny was illegible).
        The user can still fit via Ctrl+0 / the Fit button.
        """
        self._model = model
        self._mode = governance_mode
        self._mode_label = tr(
            "step4_govmode_banking_short"
            if governance_mode == "BANKING"
            else "step4_govmode_research_short"
        )
        for w in (self._btn_out, self._btn_in, self._btn_fit):
            w.setEnabled(True)
        self.refresh()
        self._view._set_zoom(1.0)

    def clear_model(self) -> None:
        """Back to the empty placeholder (no model bound).

        Called by MainWindow whenever the session returns to DATA_LOADED
        (retrain or failed transition), so the viewer never displays a
        tree the session state no longer holds.
        """
        self._model = None
        for w in (self._btn_out, self._btn_in, self._btn_fit):
            w.setEnabled(False)
        self.refresh()

    def set_theme(self, name: str) -> None:
        """Re-render with palette `name` (scene items ignore the app QSS)."""
        try:
            self._palette = PALETTES[name]
        except KeyError:
            raise ValueError(
                f"Unknown theme: {name!r} (available: {tuple(PALETTES)})"
            ) from None
        self.refresh()

    def refresh(self) -> None:
        """FULL re-render (OBS 4, audit 2.2 - Opción A): rebuilds the whole
        scene from the stored model (or the placeholder) with the active
        palette and language - the same single render path used by
        set_model(). Node selection is preserved across the rebuild via
        node_id. Mirrors wizard.retranslate_ui() semantics: one code path
        for first paint and for language/theme switches.
        """
        sel = self.selected_node_id()
        if self._model is None:
            self._lbl_header.setText("")
            self._lbl_warning.setVisible(False)
            self._build_placeholder()
            return
        self._scene.build_from_model(self._model, self._palette, self._mode)
        n = len(self._model.nodes)
        self._lbl_header.setText(self._header_text())
        self._lbl_warning.setVisible(n > LARGE_TREE_THRESHOLD)
        if n > LARGE_TREE_THRESHOLD:
            self._lbl_warning.setText(tr("tree_large_warning").format(n=n))
        if sel is not None:
            self._scene.select_node(sel)

    def select_node(self, node_id: int) -> None:
        self._scene.select_node(node_id)

    def center_on_node(self, node_id: int) -> None:
        """Centra la vista del canvas en el nodo indicado."""
        item = self._scene._items.get(node_id)
        if item is not None:
            self._view.centerOn(item)

    def zoom_in(self) -> None:
        self._view.zoom_in()

    def zoom_out(self) -> None:
        self._view.zoom_out()

    def zoom_fit(self) -> None:
        self._view.zoom_fit()

    def selected_node_id(self) -> int | None:
        return self._scene.selected_node_id()

    def retranslate_ui(self) -> None:
        """Re-apply tr() to panel chrome; scene texts via refresh()."""
        self._btn_out.setToolTip(tr("tree_zoom_out"))
        self._btn_in.setToolTip(tr("tree_zoom_in"))
        self._btn_fit.setText(tr("tree_zoom_fit"))
        self._btn_fit.setToolTip(tr("tree_zoom_fit"))
        if self._model is None:
            self._lbl_header.setText("")
        self.refresh()

    # -- internals ------------------------------------------------------------

    def _header_text(self) -> str:
        m = self._model
        assert m is not None
        n_terminal = sum(1 for nd in m.nodes if nd.is_leaf)
        return (
            f"{m.method} · {len(m.nodes)} {tr('tree_hdr_nodes')} · "
            f"{n_terminal} {tr('tree_hdr_nodes_terminal')} · "
            f"{tr('tree_hdr_fp')}={m.params_fingerprint} · {self._mode_label}"
        )

    def _build_placeholder(self) -> None:
        """Pantalla vacía: tarjeta HTML centrada (marca TreeGov en ACCENT,
        instrucción en DISABLED). QGraphicsTextItem + QTextDocument; la
        escena ignora la QSS de la app, así que el color va inline con
        los tokens de la paleta activa."""
        self._scene.clear()
        self._scene.setBackgroundBrush(QBrush(QColor(self._palette["BG"])))
        html = (
            f"<div style='text-align: center;"
            f" color: {self._palette['DISABLED']};'>"
            f"<h2 style='color: {self._palette['ACCENT']};"
            f" font-weight: bold;'>TreeGov</h2>"
            f"<p>{tr('tree_empty')}</p></div>"
        )
        item = QGraphicsTextItem()
        item.document().setDocumentMargin(0)
        item.setHtml(html)
        self._scene.addItem(item)
        r = item.boundingRect()
        item.setPos(-r.width() / 2.0, -r.height() / 2.0)
        self._scene.setSceneRect(r.adjusted(-40.0, -40.0, 40.0, 40.0))

    def _on_zoom_changed(self, factor: float) -> None:
        self._lbl_zoom.setText(f"{round(factor * 100)}%")

    def _on_language_changed(self, _lang: str) -> None:
        self.retranslate_ui()

    # -- Qt overrides -------------------------------------------------------------

    def closeEvent(self, event) -> None:
        # disconnect the bus: without this, the bound method keeps the
        # panel alive (and rebuilding) until Qt deletes the object
        try:
            language_bus.language_changed.disconnect(self._on_language_changed)
        except (RuntimeError, TypeError):
            pass  # already disconnected
        super().closeEvent(event)
