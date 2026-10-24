"""Interactive tree viewer (TreeGov GUI, Phase 2.2).

Clean room: this module only READS the frozen TreeModel / TreeNode /
SplitConfig objects produced by backend_v3. There is NO analytical logic
here: every statistic shown (n, n_events, pd_jeffreys, pd_final, split
fields) is precomputed in the backend (tree_builder); the viewer merely
formats it for display. Type annotations of backend classes live under
TYPE_CHECKING: the module never imports backend_v3 at runtime.

Layout convention (tidy tree, simplified): leaves occupy consecutive
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
per-class tuples (index 0 = class of interest). The tree viewer
displays index 0 for now; full multiclass rendering arrives in
Phase 3.1.f.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
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
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from frontend_v3.i18n import language_bus, tr
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
NODE_H = 140.0          # node box height (Phase 3.11.a: table + bar chart)
H_GAP = 24.0            # horizontal gap between leaf slots
V_GAP = 48.0            # vertical gap between depth layers
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


def _layout_tree(model: TreeModel) -> dict[int, tuple[float, float]]:
    """Deterministic tidy layout: node_id -> (x, y) of the box top-left.

    Post-order DFS over child_ids. Leaves take consecutive integer slots;
    an internal node sits at the midpoint of its outermost children
    (Reingold & Tilford 1981, principles 1-4, simplified). The same model
    always yields the same dict (identity verified in the test suite).
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
            float(node.depth) * (NODE_H + V_GAP),
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


# Phase 3.11.a: per-class bar colors in the node body (classic station
# bar chart). Class 0 (class of interest) is red; the rest cycle through
# green, blue (Colab accent) and amber.
_CLASS_BAR_COLORS = ("#D32F2F", "#2E7D32", "#1A73E8", "#F29900")


def _node_label(node: TreeNode, palette: dict[str, str]) -> str:
    """HTML for the node box (Phase 3.11.a: classic station layout).

    Structure: colored header (predictor for internal nodes, leaf badge
    for leaves), distribution table `Categoría | % | n` with a `Total`
    row, a proportional per-class bar chart scaled to the node width,
    and a small footer with the split stats (internal) or the node Gini
    (leaves). Presentation-only: every number is precomputed by the
    backend; the Gini shown is the node impurity derived from pd_final.

    Theme-aware: body/footer text colors come from the ACTIVE palette
    (FG / DISABLED) and the table grid from palette BORDER; the outer div
    stays transparent so the NodeItem rect (solid NODE_BG) paints through.
    """
    # 1. Header (blue for internal, semaphore green/amber/red for leaves)
    if node.is_leaf:
        pd = node.pd_final[0]
        color = "#2E7D32" if pd < 0.05 else ("#ED6C02" if pd < 0.15 else "#D32F2F")
        header_text = f"{tr('tree_leaf_badge')}"
    else:
        color = "#1A73E8"  # Colab accent
        split = node.split
        header_text = str(split.predictor) if split else "Internal"

    header_html = f"<div style='background-color:{color}; color:#FFFFFF; font-weight:bold; text-align:center; padding:2px; border-top-left-radius:4px; border-top-right-radius:4px;'>{header_text}</div>"

    # 2. Distribution table: Categoría | % | n (canonical class order).
    # Visible grid (classic tree-station style): Qt's rich-text engine DOES support
    # <style> blocks and td/th borders + padding (verified empirically by
    # pixel count, audit log 24/10/2026). The border color follows the
    # active palette (BORDER token), so the grid is visible on both the
    # white (light) and black (dark) node bodies.
    style_html = (
        "<style>"
        "table { border-collapse: collapse; width: 100%; } "
        "th, td { border: 1px solid " + palette["BORDER"] + "; padding: 2px; }"
        "</style>"
    )
    rows: list[str] = []
    for c, label in enumerate(node.class_labels):
        k_c = node.n_events[c] if c < len(node.n_events) else 0
        p_c = node.pd_final[c] if c < len(node.pd_final) else 0.0
        rows.append(
            f"<tr><td>{label}</td>"
            f"<td style='text-align:right;'>{float(p_c) * 100:.1f}%</td>"
            f"<td style='text-align:right;'>{k_c}</td></tr>"
        )
    rows.append(
        "<tr><td><b>Total</b></td>"
        "<td style='text-align:right;'><b>100%</b></td>"
        f"<td style='text-align:right;'><b>{node.n}</b></td></tr>"
    )
    table_html = (
        '<table style="font-size:11px;">'
        "<tr><th>Categoría</th><th>%</th><th>n</th></tr>"
        + "".join(rows)
        + "</table>"
    )

    # 3. Proportional per-class bar chart, scaled to the node width
    n = node.n if node.n > 0 else 1
    bar_w_total = int(NODE_W) - 16  # outer padding (2x4px) + border slack
    spans: list[str] = []
    for c in range(len(node.class_labels)):
        k_c = node.n_events[c] if c < len(node.n_events) else 0
        w_c = int(round(bar_w_total * k_c / n))
        color_c = _CLASS_BAR_COLORS[c % len(_CLASS_BAR_COLORS)]
        spans.append(
            f"<span style='background-color:{color_c}; "
            f"display:inline-block; width:{w_c}px; height:6px;'></span>"
        )
    bar_html = (
        "<div style='margin-top:4px; margin-bottom:4px;'>"
        + "".join(spans)
        + "</div>"
    )

    # 4. Footer (small grey text): split stats for internal nodes,
    #    node Gini for leaves
    if node.is_leaf:
        # Gini calculated purely for display (pandas-free)
        gini = 1.0 - sum(p**2 for p in node.pd_final) if node.pd_final else 0.0
        footer_text = f"Gini: {gini:.3f}"
    else:
        split = node.split
        p_adj = (
            split.p_value_adjusted
            if split is not None and split.p_value_adjusted is not None
            else (split.p_value if split is not None else None)
        )
        p_str = f"{p_adj:.3g}" if p_adj is not None else "—"
        stat_name = split.statistic_name if split is not None else "—"
        stat_str = (
            f"{split.statistic:.4g}"
            if split is not None and split.statistic is not None
            else "—"
        )
        footer_text = f"Adj. P: {p_str} | {stat_name}: {stat_str}"

    footer_html = f"<div style='font-size:9px; color:{palette['DISABLED']}; text-align:center;'>{footer_text}</div>"

    # Combine (transparent background so the solid NodeItem rect paints
    # through); the style block travels with the HTML document.
    return f"""
    {style_html}
    <div style='width:{int(NODE_W) - 8}px; background-color: transparent; color: {palette["FG"]}; font-family: sans-serif; padding: 4px;'>
        {header_html}
        {table_html}
        {bar_html}
        {footer_html}
    </div>
    """


def _edge_label(split, branch_index: int) -> str:
    """Short branch rule for the elbow connector; long groups are elided."""
    if split is None:
        return ""
    if split.threshold is not None:
        t = _fmt_num(split.threshold)
        return f"≤ {t}" if branch_index == 0 else f"> {t}"
    group = (split.branches or ())[branch_index]
    text = "{" + ",".join(str(v) for v in group) + "}"
    if len(text) > EDGE_LABEL_MAX:
        text = text[: EDGE_LABEL_MAX - 1] + "…"
    return text


def node_detail_lines(node: TreeNode) -> list[str]:
    """Properties-panel card for one node (read-only formatting)."""
    lines = [
        f"{tr('tree_prop_node')}: {node.node_id}",
        f"{tr('tree_prop_depth')}: {node.depth}",
        f"n: {node.n}",
        f"{tr('tree_node_events')}: {node.n_events[0]}",
        f"{tr('tree_prop_pd_jeffreys')}: {_fmt_num(node.pd_jeffreys[0])}",
        f"{tr('tree_prop_pd_final')}: {_fmt_num(node.pd_final[0])}",
    ]
    if node.pd_final[0] != node.pd_jeffreys[0]:
        lines.append(tr("tree_prop_floor_note"))
    if node.is_leaf:
        lines.append(
            f"{tr('tree_prop_leaf')}: "
            f"{tr(f'tree_leaf_reason_{node.leaf_reason}')}"
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
    n_leaves = sum(1 for nd in model.nodes if nd.is_leaf)
    max_depth = max(nd.depth for nd in model.nodes)
    return [
        f"{tr('tree_prop_method')}: {model.method}",
        f"{tr('tree_hdr_nodes')}: {n_nodes}",
        f"{tr('tree_hdr_leaves')}: {n_leaves}",
        f"{tr('tree_prop_depth')}: {max_depth}",
        f"{tr('tree_hdr_fp')}: {model.params_fingerprint}",
        f"{tr('status_mode')}: {mode_label}",
    ]


# ---------------------------------------------------------------------------
# Graphics items
# ---------------------------------------------------------------------------


class NodeItem(QGraphicsRectItem):
    """One node box (fixed NODE_W x NODE_H) with centered text.

    Colors come from the active theme PALETTE (graphics items do not read
    the application QSS). Body: solid NODE_BG fill (pure white on light,
    pure black on dark — classic tree-station flat card) / BORDER pen / FG
    text (contrast guaranteed by the palette pairing). The header's
    semaphore color encodes the leaf status. Selection: ACCENT pen,
    width 3.
    """

    def __init__(self, node: TreeNode, palette: dict[str, str]) -> None:
        super().__init__(0.0, 0.0, NODE_W, NODE_H)
        self.node_id = node.node_id
        self._palette = palette
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setZValue(1.0)

        fg = QColor(palette["FG"])
        fill = QColor(palette["NODE_BG"])
        self.setBrush(QBrush(fill))
        self.setPen(QPen(QColor(palette["BORDER"]), 1))

        self._text = QGraphicsTextItem(self)
        self._text.setTextWidth(NODE_W)
        doc = self._text.document()
        opt = doc.defaultTextOption()
        opt.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        doc.setDefaultTextOption(opt)
        self._text.setDefaultTextColor(fg)
        self._text.setHtml(_node_label(node, palette))
        text_h = doc.size().height()
        self._text.setPos(0.0, max(0.0, (NODE_H - text_h) / 2.0))
        self.setToolTip("\n".join(node_detail_lines(node)))

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            pen = self.pen()
            if value:
                pen.setColor(QColor(self._palette["ACCENT"]))
                pen.setWidth(3)
            else:
                pen.setColor(QColor(self._palette["BORDER"]))
                pen.setWidth(1)
            self.setPen(pen)
        return super().itemChange(change, value)


class TreeScene(QGraphicsScene):
    """Scene holding node boxes and elbow connectors.

    Emits node_selected(node_id) on single selection; selection_cleared
    whenever no NodeItem remains selected (drives the model summary in the
    properties panel).
    """

    node_selected = Signal(int)
    selection_cleared = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: dict[int, NodeItem] = {}
        # Phase 3.11.a: the scene background follows the ACTIVE theme BG
        # (graphics scenes ignore the application QSS). Default = light,
        # matching TreePanel._palette; refreshed on every rebuild.
        self.setBackgroundBrush(QBrush(QColor(PALETTES["light"]["BG"])))
        self.selectionChanged.connect(self._emit_selected)

    # -- build ---------------------------------------------------------------

    def build_from_model(self, model: TreeModel, palette: dict[str, str]) -> None:
        """Rebuild every item from the frozen model (single render path)."""
        self.clear()
        self._items.clear()
        self.setBackgroundBrush(QBrush(QColor(palette["BG"])))
        pos = _layout_tree(model)

        # edges first (z=0, below the node boxes at z=1)
        edge_pen = QPen(QColor(palette["BORDER"]), 1)
        label_brush = QBrush(QColor(palette["DISABLED"]))
        for node in model.nodes:
            if node.is_leaf:
                continue
            x0, y0 = pos[node.node_id]
            x0c, y0b = x0 + NODE_W / 2.0, y0 + NODE_H
            for bi, cid in enumerate(node.child_ids):
                x1, y1 = pos[cid]
                x1c = x1 + NODE_W / 2.0
                mid_y = (y0b + y1) / 2.0
                path = QPainterPath(QPointF(x0c, y0b))
                path.lineTo(x0c, mid_y)
                path.lineTo(x1c, mid_y)
                path.lineTo(x1c, y1)
                edge = QGraphicsPathItem(path)
                edge.setPen(edge_pen)
                edge.setZValue(0.0)
                self.addItem(edge)
                label = self.addSimpleText(_edge_label(node.split, bi))
                label.setBrush(label_brush)
                lr = label.boundingRect()
                label.setPos((x0c + x1c - lr.width()) / 2.0, mid_y - lr.height())

        for node in model.nodes:
            item = NodeItem(node, palette)
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
        self._scene.build_from_model(self._model, self._palette)
        n = len(self._model.nodes)
        self._lbl_header.setText(self._header_text())
        self._lbl_warning.setVisible(n > LARGE_TREE_THRESHOLD)
        if n > LARGE_TREE_THRESHOLD:
            self._lbl_warning.setText(tr("tree_large_warning").format(n=n))
        if sel is not None:
            self._scene.select_node(sel)

    def select_node(self, node_id: int) -> None:
        self._scene.select_node(node_id)

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
        n_leaves = sum(1 for nd in m.nodes if nd.is_leaf)
        return (
            f"{m.method} · {len(m.nodes)} {tr('tree_hdr_nodes')} · "
            f"{n_leaves} {tr('tree_hdr_leaves')} · "
            f"{tr('tree_hdr_fp')}={m.params_fingerprint} · {self._mode_label}"
        )

    def _build_placeholder(self) -> None:
        self._scene.clear()
        self._scene.setBackgroundBrush(QBrush(QColor(self._palette["BG"])))
        text = self._scene.addSimpleText(tr("tree_empty"))
        text.setBrush(QBrush(QColor(self._palette["FG"])))
        r = text.boundingRect()
        text.setPos(-r.width() / 2.0, -r.height() / 2.0)
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
