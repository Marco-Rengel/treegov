"""
TreeMap — minimapa abstracto del árbol (portado del prototipo Antigravity).

Layout abstracto desacoplado del canvas principal: cajas 48x30 con gap
horizontal 16 y vertical 36. El texto (ID del nodo, 11 pt negrita) escala
con la caja porque no usa ItemIgnoresTransformations. La navegación es por
node_id: el clic emite node_clicked(int); MainWindow busca el TreeNodeItem
en el canvas y hace centerOn. Nunca se traducen coordenadas.

Sala limpia: cero lógica analítica. El widget solo pinta.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional, Tuple

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
    from backend_v3.tree_builder import TreeModel, TreeNode

__all__ = ["TreeMap"]

# Geometría abstracta del minimapa (independiente del canvas principal).
BOX_W = 48.0
BOX_H = 30.0
H_GAP = 16.0
V_GAP = 36.0


class _AbstractNodeItem(QGraphicsRectItem):
    """Caja abstracta con el ID del nodo centrado (estilo prototipo)."""

    def __init__(
        self,
        node_id: int,
        rect: QRectF,
        is_leaf: bool,
        palette: dict[str, str],
        parent: Optional[QGraphicsItem] = None,
    ) -> None:
        super().__init__(rect, parent)
        self.node_id = node_id
        self.is_leaf = is_leaf
        self._palette = palette
        self._selected = False
        self._apply_style()
        text = QGraphicsSimpleTextItem(str(node_id), self)
        font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        text.setFont(font)
        text.setBrush(QBrush(QColor("#FFFFFF")))
        # Mantiene el texto al mismo tamaño en pantalla,
        # sin importar cuánto se reduzca la escena en fitInView.
        text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        tr = text.boundingRect()
        # Centrar el texto (el origen del item es el centro del rect)
        text.setPos(-tr.width() / 2.0, -tr.height() / 2.0)
        text.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def _apply_style(self) -> None:
        if self._selected:
            # Seleccionado: cian brillante, fondo azul intenso
            self.setPen(QPen(QColor("#38bdf8"), 2.5))
            self.setBrush(QBrush(QColor("#1d4ed8")))
        else:
            # Normal: borde verde (hoja) o azul (interno), fondo oscuro fijo
            border = QColor("#059669") if self.is_leaf else QColor("#3b82f6")
            self.setPen(QPen(border, 1.5))
            self.setBrush(QBrush(QColor("#1e293b")))

    def set_selected_state(self, selected: bool) -> None:
        if self._selected != selected:
            self._selected = selected
            self._apply_style()


class _MapView(QGraphicsView):
    """Vista propia del minimapa: clic -> node_clicked."""

    node_clicked = Signal(int)

    def __init__(
        self, scene: QGraphicsScene, parent: QWidget | None = None
    ) -> None:
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def fit_scene(self) -> None:
        rect = self.scene().sceneRect()
        if not rect.isNull() and rect.width() > 0 and rect.height() > 0:
            self.fitInView(
                rect.adjusted(-20, -20, 20, 20),
                Qt.AspectRatioMode.KeepAspectRatio,
            )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.fit_scene()

    def mousePressEvent(self, event) -> None:
        if event.button() is Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            while item is not None and not isinstance(item, _AbstractNodeItem):
                item = item.parentItem()
            if isinstance(item, _AbstractNodeItem):
                self.node_clicked.emit(item.node_id)
        event.accept()


class TreeMap(QWidget):
    """Bloque Tree Map: minimapa abstracto del árbol."""

    node_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._palette: dict[str, str] = PALETTES["light"]
        self._model: TreeModel | None = None
        self._items: Dict[int, _AbstractNodeItem] = {}
        self._layout = QVBoxLayout(self)
        self._scene = QGraphicsScene(self)
        self._scene.setBackgroundBrush(QBrush(QColor(self._palette["BG"])))
        self._view = _MapView(self._scene, self)
        self._view.node_clicked.connect(self.node_clicked)
        self._layout.addWidget(self._view)

    def set_model(self, model: TreeModel | None) -> None:
        self._model = model
        self._rebuild()

    def set_selected_node(self, node_id: int | None) -> None:
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
        self._scene.clear()
        self._items.clear()
        self._scene.setBackgroundBrush(QBrush(QColor(self._palette["BG"])))
        model = self._model
        if model is None:
            self._view.fit_scene()
            return

        row_h = BOX_H + V_GAP
        positions: Dict[int, Tuple[float, float]] = {}
        next_x = [0.0]

        def _walk(node_id: int, depth: int) -> float:
            node = model.nodes[node_id]
            y = depth * row_h
            if node.is_leaf:
                x = next_x[0]
                next_x[0] += BOX_W + H_GAP
                positions[node_id] = (x, y)
                return x
            child_xs = [_walk(cid, depth + 1) for cid in node.child_ids]
            x = sum(child_xs) / len(child_xs)
            positions[node_id] = (x, y)
            return x

        _walk(model.root_id, 0)

        edge_pen = QPen(QColor(self._palette["DISABLED"]), 1.5)
        for node in model.nodes:
            if node.is_leaf:
                continue
            px, py = positions[node.node_id]
            p_bottom = QPointF(px, py + BOX_H / 2.0)
            for cid in node.child_ids:
                cx, cy = positions[cid]
                c_top = QPointF(cx, cy - BOX_H / 2.0)
                mid_y = (p_bottom.y() + c_top.y()) / 2.0
                path = QPainterPath(p_bottom)
                path.lineTo(p_bottom.x(), mid_y)
                path.lineTo(cx, mid_y)
                path.lineTo(c_top)
                edge = QGraphicsPathItem(path)
                edge.setPen(edge_pen)
                self._scene.addItem(edge)

        box_rect = QRectF(-BOX_W / 2.0, -BOX_H / 2.0, BOX_W, BOX_H)
        for node in model.nodes:
            if node.node_id not in positions:
                continue
            x, y = positions[node.node_id]
            item = _AbstractNodeItem(
                node.node_id, box_rect, node.is_leaf, self._palette
            )
            item.setPos(x, y)
            self._scene.addItem(item)
            self._items[node.node_id] = item

        bounds = self._scene.itemsBoundingRect()
        self._scene.setSceneRect(bounds.adjusted(-25, -25, 25, 25))
        self._view.fit_scene()
