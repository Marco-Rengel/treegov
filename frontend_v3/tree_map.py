"""Abstract tree map widget: tidy top-down minimap of the TreeModel.

Clean-room rewrite (Phase 3.11.e). This module only renders: it contains
zero analytic logic and consumes the immutable ``TreeModel`` as a
read-only snapshot. All colors come from ``frontend_v3.theme.PALETTES``;
no hard-coded hex values anywhere in the file.

Layout — simplified Reingold-Tilford tidy tree, drawn top-down: every
leaf occupies exactly one column, and every internal node is centered
over the span of its direct children.
    Reingold, E.M. & Tilford, J.S. (1981). "Tidier Drawings of Trees".
    IEEE Transactions on Software Engineering, SE-7(2), 223-228.

Connectors — orthogonal three-segment edges (vertical drop from the
parent, horizontal run, vertical entry into the child), the classical
convention for layered tree drawings.
    Battista, G. di, Eades, P., Tamassia, R. & Tollis, I.G. (1998).
    "Graph Drawing: Algorithms for the Visualization of Graphs".
    Prentice Hall, chapter 4.

Node ID labels use ``QGraphicsItem.ItemIgnoresTransformations`` so they
keep a constant on-screen size at any zoom level (Qt 6 documentation,
QGraphicsItem::GraphicsItemFlag).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QVBoxLayout,
    QWidget,
)

from frontend_v3.theme import PALETTES

if TYPE_CHECKING:
    from backend_v3.tree_builder import TreeModel

__all__ = ["TreeMap"]

# Geometry of the abstract layout (fixed by the 3.11.e design): each node
# is a CAJA_W x CAJA_H box; adjacent leaf columns are pitched
# CAJA_W + HUECO_H apart; consecutive depth levels are pitched
# CAJA_H + HUECO_V apart.
CAJA_W = 48.0
CAJA_H = 30.0
HUECO_H = 16.0
HUECO_V = 36.0

# Minimum zoom factor. When the factor required to fit the whole scene is
# smaller than MIN_SCALE, the view clamps to MIN_SCALE and switches the
# scroll bars to ScrollBarAsNeeded instead of shrinking further.
MIN_SCALE = 0.02

# Empty margin around the drawn tree inside the scene rect.
_MARGEN = 24.0


def _posiciones_arbol(model: TreeModel) -> dict[int, tuple[float, float]]:
    """Compute the (x, y) center of every node box.

    Simplified Reingold-Tilford: a post-order walk assigns each leaf the
    next free column, left to right; each internal node is centered on
    the midpoint between its first and its last child (the centering
    aesthetic of Reingold & Tilford 1981). The row of a node is its
    depth. ``TreeModel`` guarantees that every node is reachable from
    ``root_id`` and that ``nodes`` is indexed by ``node_id``.
    """
    pos: dict[int, tuple[float, float]] = {}
    cursor = [0.0]  # center x of the next free leaf column
    paso_x = CAJA_W + HUECO_H
    paso_y = CAJA_H + HUECO_V

    def _recorrer(node_id: int, depth: int) -> float:
        node = model.nodes[node_id]
        y = depth * paso_y
        if node.is_leaf:
            x = cursor[0]
            cursor[0] += paso_x
        else:
            xs = [_recorrer(cid, depth + 1) for cid in node.child_ids]
            x = (xs[0] + xs[-1]) / 2.0
        pos[node_id] = (x, y)
        return x

    _recorrer(model.root_id, 0)
    return pos


class _CajaNodo(QGraphicsRectItem):
    """Node box with its ID label centered inside.

    The label is a QGraphicsSimpleTextItem with the
    ItemIgnoresTransformations flag (Qt 6 docs,
    QGraphicsItem::GraphicsItemFlag): it keeps a constant on-screen size
    no matter how far the view zooms out, so the minimap stays readable
    when clamped at MIN_SCALE. The label accepts no mouse buttons, so
    clicks always reach the box underneath.
    """

    def __init__(
        self,
        node_id: int,
        is_leaf: bool,
        palette: dict[str, str],
        parent: QGraphicsItem | None = None,
    ) -> None:
        rect = QRectF(-CAJA_W / 2.0, -CAJA_H / 2.0, CAJA_W, CAJA_H)
        super().__init__(rect, parent)
        self.node_id = node_id
        self.is_leaf = is_leaf
        self._palette = palette
        self._selected = False
        self._texto = QGraphicsSimpleTextItem(str(node_id), self)
        self._texto.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self._texto.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True
        )
        self._texto.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        bounds = self._texto.boundingRect()
        self._texto.setPos(-bounds.width() / 2.0, -bounds.height() / 2.0)
        self._aplicar_estilo()

    def _aplicar_estilo(self) -> None:
        # DECISIÓN (31/10/2026): the design lists both "normal border: BORDER"
        # and kind-specific borders (leaf: STATUS_OK, internal: ACCENT).
        # Resolved conservatively: the kind-specific rule wins for boxes
        # (every node is either leaf or internal); BORDER is used for the
        # connectors, per the edge rule.
        pal = self._palette
        if self._selected:
            self.setBrush(QBrush(QColor(pal["ACCENT"])))
            self.setPen(QPen(QColor(pal["ACCENT"]), 2.0))
            self._texto.setBrush(QBrush(QColor(pal["ACCENT_FG"])))
        else:
            self.setBrush(QBrush(QColor(pal["SURFACE"])))
            border = pal["STATUS_OK"] if self.is_leaf else pal["ACCENT"]
            self.setPen(QPen(QColor(border), 1.0))
            self._texto.setBrush(QBrush(QColor(pal["FG"])))

    def set_selected_state(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self._aplicar_estilo()


class _TreeMapScene(QGraphicsScene):
    """Scene with a palette-driven background. Holds no logic."""

    def apply_palette(self, palette: dict[str, str]) -> None:
        self.setBackgroundBrush(QBrush(QColor(palette["BG"])))


class _TreeMapView(QGraphicsView):
    """Map view: left click on a box emits ``node_clicked(node_id)``."""

    node_clicked = Signal(int)

    def __init__(
        self, scene: QGraphicsScene, parent: QWidget | None = None
    ) -> None:
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def fit_scene(self) -> None:
        """Fit the whole scene into the viewport, clamped at MIN_SCALE.

        When the fit factor falls below MIN_SCALE the transform is fixed
        at MIN_SCALE (centered on the scene) and the scroll bars switch
        to ScrollBarAsNeeded; otherwise they stay AlwaysOff.
        """
        rect = self.scene().sceneRect()
        view = self.viewport().rect()
        if (
            rect.isNull()
            or rect.width() <= 0
            or rect.height() <= 0
            or view.width() <= 0
            or view.height() <= 0
        ):
            return
        factor = min(view.width() / rect.width(), view.height() / rect.height())
        if factor < MIN_SCALE:
            self._set_scroll_policies(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.resetTransform()
            self.scale(MIN_SCALE, MIN_SCALE)
            self.centerOn(rect.center())
        else:
            self._set_scroll_policies(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def _set_scroll_policies(self, policy: Qt.ScrollBarPolicy) -> None:
        # Guard against redundant changes: a policy switch resizes the
        # viewport, which re-enters resizeEvent -> fit_scene.
        if self.horizontalScrollBarPolicy() != policy:
            self.setHorizontalScrollBarPolicy(policy)
        if self.verticalScrollBarPolicy() != policy:
            self.setVerticalScrollBarPolicy(policy)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.fit_scene()

    def mousePressEvent(self, event) -> None:
        if event.button() is Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            while item is not None and not isinstance(item, _CajaNodo):
                item = item.parentItem()
            if isinstance(item, _CajaNodo):
                self.node_clicked.emit(item.node_id)
        event.accept()


class TreeMap(QWidget):
    """Tree Map block: abstract top-down minimap of the tree model.

    Public contract (consumed by main_window.py): the ``node_clicked``
    signal and the ``set_model`` / ``set_selected_node`` / ``set_theme``
    methods. Everything is rebuilt from scratch on every model or theme
    change; with no model the scene stays empty (no decorative text).
    """

    node_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._palette: dict[str, str] = PALETTES["light"]
        self._model: TreeModel | None = None
        self._selected_id: int | None = None
        self._items: dict[int, _CajaNodo] = {}
        self._scene = _TreeMapScene(self)
        self._scene.apply_palette(self._palette)
        self._view = _TreeMapView(self._scene, self)
        self._view.node_clicked.connect(self.node_clicked)
        layout = QVBoxLayout(self)
        layout.addWidget(self._view)

    def set_model(self, model: TreeModel | None) -> None:
        self._model = model
        self._rebuild()

    def set_selected_node(self, node_id: int | None) -> None:
        self._selected_id = node_id
        for nid, item in self._items.items():
            item.set_selected_state(nid == node_id)

    def set_theme(self, name: str) -> None:
        try:
            self._palette = PALETTES[name]
        except KeyError:
            raise ValueError(
                f"Unknown theme: {name!r} (available: {tuple(PALETTES)})"
            ) from None
        self._rebuild()

    def _rebuild(self) -> None:
        """Rebuild scene contents from the current model and palette."""
        self._scene.clear()
        self._items.clear()
        self._scene.apply_palette(self._palette)
        model = self._model
        if model is None:
            self._scene.setSceneRect(QRectF())
            return

        pos = _posiciones_arbol(model)

        # Connectors first, so the boxes paint on top of them.
        edge_pen = QPen(QColor(self._palette["BORDER"]), 1.0)
        for node in model.nodes:
            if node.is_leaf:
                continue
            px, py = pos[node.node_id]
            p_bottom = QPointF(px, py + CAJA_H / 2.0)
            for cid in node.child_ids:
                cx, cy = pos[cid]
                c_top = QPointF(cx, cy - CAJA_H / 2.0)
                mid_y = (p_bottom.y() + c_top.y()) / 2.0
                path = QPainterPath(p_bottom)
                path.lineTo(p_bottom.x(), mid_y)  # drop from the parent
                path.lineTo(cx, mid_y)            # horizontal run
                path.lineTo(c_top)                # entry into the child
                edge = QGraphicsPathItem(path)
                edge.setPen(edge_pen)
                self._scene.addItem(edge)

        for node in model.nodes:
            x, y = pos[node.node_id]
            item = _CajaNodo(node.node_id, node.is_leaf, self._palette)
            item.setPos(x, y)
            self._scene.addItem(item)
            self._items[node.node_id] = item

        if self._selected_id is not None:
            selected = self._selected_id
            for nid, item in self._items.items():
                item.set_selected_state(nid == selected)

        bounds = self._scene.itemsBoundingRect()
        self._scene.setSceneRect(
            bounds.adjusted(-_MARGEN, -_MARGEN, _MARGEN, _MARGEN)
        )
        self._view.fit_scene()
