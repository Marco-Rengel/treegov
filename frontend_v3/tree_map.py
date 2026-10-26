"""TreeMap — minimapa del árbol (Fase 3.11.b.3, decisión D2 del diseño
auditado `docs/3.11.b_design_treemap_dataviewer.md`).

Escena `QGraphicsScene`/`QGraphicsView` PROPIA e independiente del canvas
principal (`TreeScene`/`TreeView`): no comparte escena, ítems ni estado de
selección (D2; alternativa 2.1-B elegida sobre compartir escena, que
acoplaría selección y foco). Un `QGraphicsRectItem` plano por nodo, sin
texto, sin tooltips y sin selección propia.

Colores (mismos umbrales que la banda de cabecera del `NodeItem`, Design
System §5.1.1): nodo interno -> token ACCENT (azul); nodo terminal ->
semáforo sobre `pd_final[0]` de la clase de interés (< 0.05 STATUS_OK,
< 0.15 STATUS_WARN, resto STATUS_CRIT).

Interacción (D2 + invariante 4 del diseño): el clic izquierdo sobre un
rectángulo emite `node_clicked(int)`; `MainWindow` responde con
`centerOn(nodo)` en el canvas principal SIN tocar su zoom ni su
selección. El `fitInView` se aplica EXCLUSIVAMENTE a la vista propia del
minimapa sobre su propia escena; está prohibido que esa operación toque
el `QTransform` de la vista principal (diseño general §3/§7: el minimapa
nunca dispara zoom fit en el canvas).

Resaltado pasivo: `set_selected_node(node_id)` dibuja un borde ACCENT
grueso (pluma cosmética: grosor en px de pantalla, independiente del
encaje del minimapa) en el rectángulo correspondiente, reflejando la
selección del canvas principal; el minimapa nunca propaga selección.

Reconstrucción completa ante cualquier cambio del modelo (fit, poda,
nuevo CSV): `set_model` reconstruye la escena entera; no hay
actualización incremental (el coste de repintar rectángulos es
despreciable frente a sincronizar deltas — riesgo mitigado en §6).

Sala limpia: cero lógica analítica. Las posiciones derivan del mismo
layout puro del canvas (`_layout_tree`, Reingold & Tilford 1981,
simplificado) y la estadística de color (`pd_final`) viene precalculada
en el `TreeModel` congelado del backend; el widget solo pinta.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QTransform,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QVBoxLayout,
    QWidget,
)

from frontend_v3.theme import PALETTES
from frontend_v3.tree_view import NODE_H, NODE_W, SCENE_MARGIN, _layout_tree

if TYPE_CHECKING:
    from backend_v3.tree_builder import TreeModel, TreeNode

__all__ = ["TreeMap"]

# Grosor de los conectores ortogonales: 1 px era invisible sobre el fondo
# del tema. 2 px con el token FG (no BORDER) garantiza contraste en ambos
# temas (verificado empíricamente en las capturas del mini-cierre #4).
_EDGE_PEN_WIDTH = 2

# Grosor del borde de resaltado pasivo (px de pantalla; pluma cosmética,
# visible con cualquier encaje del minimapa). El borde normal es 1 px.
_HIGHLIGHT_W = 3

# Zoom dinámico con clamp: fitInView encaja el árbol y se limita al
# rango [MIN, MAX]. Árbol pequeño -> zoom alto legible (hasta MAX);
# árbol grande -> zoom bajo que muestra la estructura completa (hasta
# MIN). Si ni al mínimo cabe, el QGraphicsView permite scroll.
MAP_MIN_ZOOM = 0.10
MAP_MAX_ZOOM = 0.30


def _fill_token(node: TreeNode) -> str:
    """Token de paleta del relleno del rectángulo del nodo.

    ACCENT en internos; semáforo por `pd_final[0]` (clase de interés) en
    terminales — los mismos umbrales 0.05/0.15 que la cabecera del
    `NodeItem` del canvas principal (Design System §5.1.1).
    """
    if node.is_leaf:
        p0 = float(node.pd_final[0]) if node.pd_final else 0.0
        if p0 < 0.05:
            return "STATUS_OK"
        if p0 < 0.15:
            return "STATUS_WARN"
        return "STATUS_CRIT"
    return "ACCENT"


def _connector_path(
    parent_rect: QRectF, child_rect: QRectF, orientation: str = "vertical"
) -> QPainterPath:
    """Conector ortogonal con codo único entre dos rectángulos.

    orientation="vertical": el árbol crece hacia abajo (raíz arriba).
        Sale del borde INFERIOR del padre, entra por el borde SUPERIOR
        del hijo. Es el modo actual del minimapa.

    orientation="horizontal": el árbol crece hacia la derecha (raíz
        izquierda). Sale del borde DERECHO del padre, entra por el borde
        IZQUIERDO del hijo. Reservado para el giro futuro del minimapa;
        ningún caller lo usa todavía.

    La función es agnóstica al layout: solo recibe los dos rects y el eje
    de crecimiento. Cuando se implemente el giro, el único cambio es pasar
    "horizontal" desde el bucle de _rebuild y ajustar el layout.
    """
    if orientation == "vertical":
        px, py = parent_rect.center().x(), parent_rect.bottom()
        cx, cy = child_rect.center().x(), child_rect.top()
        mid = (py + cy) / 2.0
        path = QPainterPath(QPointF(px, py))
        path.lineTo(px, mid)
        path.lineTo(cx, mid)
        path.lineTo(cx, cy)
        return path
    if orientation == "horizontal":
        px, py = parent_rect.right(), parent_rect.center().y()
        cx, cy = child_rect.left(), child_rect.center().y()
        mid = (px + cx) / 2.0
        path = QPainterPath(QPointF(px, py))
        path.lineTo(mid, py)
        path.lineTo(mid, cy)
        path.lineTo(cx, cy)
        return path
    raise ValueError(f"[tree_map] orientation inválida: {orientation!r}")


class _MapNodeItem(QGraphicsRectItem):
    """Rectángulo plano del minimapa (un nodo del árbol).

    Sin texto, sin tooltip, sin flags de selección/movimiento: el
    minimapa es un instrumento de navegación pasivo (D2).
    """

    def __init__(self, node_id: int, rect: QRectF) -> None:
        super().__init__(rect)
        self.node_id = node_id


class _MapView(QGraphicsView):
    """Vista propia del minimapa: encaje total (fitInView) y hit-testing
    del clic -> `node_clicked`.

    Sin scrollbars y sin gestos de zoom/pan: la vista es estática salvo
    el clic de navegación con el botón izquierdo. El encaje se recalcula
    en cada resize para que la raíz siga visible (D2).
    """

    node_clicked = Signal(int)

    def __init__(
        self, scene: QGraphicsScene, parent: QWidget | None = None
    ) -> None:
        super().__init__(scene, parent)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

    def fit_view(self) -> None:
        """Encaja el árbol completo (fitInView) con zoom dinámico:
        clamped a [MAP_MIN_ZOOM, MAP_MAX_ZOOM]. Árbol pequeño -> zoom
        alto legible. Árbol grande -> zoom bajo que muestra la
        estructura completa. Scrollbars si el zoom mínimo no basta."""
        rect = self.scene().sceneRect()
        if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
            self.resetTransform()
            return
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        factor = self.transform().m11()
        if factor > MAP_MAX_ZOOM:
            factor = MAP_MAX_ZOOM
        elif factor < MAP_MIN_ZOOM:
            factor = MAP_MIN_ZOOM
        else:
            return  # fitInView ya encaja y centra correctamente
        self.setTransform(QTransform().scale(factor, factor))
        self.centerOn(rect.center())

    # -- Qt overrides ------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Solo el botón izquierdo navega; el resto lo gestiona la base.
        # Se barren TODOS los ítems del punto (no solo el superior): el
        # texto del ID queda visualmente sobre el rectángulo y el clic
        # debe llegar al _MapNodeItem que hay debajo.
        # Corrección de arquitectura (mini-cierre #6): SÍ se llama a
        # super() al final — el modo ScrollHandDrag habilitado en #6
        # requiere la implementación base de QGraphicsView para arrastrar.
        # El trade-off aceptado: un clic sobre un nodo emite node_clicked
        # Y puede iniciar un drag; la navegación por clic sigue siendo
        # determinista (se emite en el press, antes de cualquier arrastre).
        if event.button() is Qt.MouseButton.LeftButton:
            for item in self.items(event.position().toPoint()):
                if isinstance(item, _MapNodeItem):
                    self.node_clicked.emit(item.node_id)
                    break
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.fit_view()


class TreeMap(QWidget):
    """Bloque Tree Map del panel izquierdo: minimapa pasivo del árbol.

    API pública: `set_model` (reconstrucción completa; None = estado
    vacío), `set_selected_node` (resaltado pasivo; None = sin resaltado),
    `node_pos` (centro del nodo en coords de escena, para el `centerOn`
    del canvas principal) y la señal `node_clicked(int)`.
    """

    node_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._palette: dict[str, str] = PALETTES["light"]
        self._model: TreeModel | None = None
        self._rects: dict[int, _MapNodeItem] = {}
        self._centers: dict[int, tuple[float, float]] = {}
        self._selected_id: int | None = None

        layout = QVBoxLayout(self)
        self._scene = QGraphicsScene(self)
        self._scene.setBackgroundBrush(QBrush(QColor(self._palette["BG"])))
        self._view = _MapView(self._scene, self)
        self._view.node_clicked.connect(self.node_clicked)  # reemisión
        layout.addWidget(self._view)

    # ---------------------------------------------------------- Public API

    def set_model(self, model: TreeModel | None) -> None:
        """Reconstruye la escena COMPLETA desde el modelo congelado
        (None -> estado vacío). Re-aplica el resaltado pasivo vigente."""
        self._model = model
        self._rebuild()

    def set_selected_node(self, node_id: int | None) -> None:
        """Resaltado PASIVO: borde ACCENT grueso sobre el rectángulo del
        nodo seleccionado en el canvas principal (None -> sin resaltado).
        El minimapa nunca selecciona por sí mismo (D2)."""
        self._selected_id = node_id
        self._apply_highlight()

    def node_pos(self, node_id: int) -> tuple[float, float] | None:
        """Centro del rectángulo del nodo en coordenadas de escena (para
        el `centerOn` del canvas principal); None si no está en el mapa."""
        return self._centers.get(node_id)

    def set_canvas_viewport(self, rect: QRectF) -> None:
        """Actualiza el rectángulo que indica qué parte del árbol
        está visible en el canvas principal."""
        if hasattr(self, "_viewport_rect"):
            self._viewport_rect.setRect(rect)

    def set_theme(self, name: str) -> None:
        """Recolorea con la paleta `name` (las escenas ignoran el QSS de
        la app; mismo fail-fast que TreePanel.set_theme)."""
        try:
            self._palette = PALETTES[name]
        except KeyError:
            raise ValueError(
                f"Unknown theme: {name!r} (available: {tuple(PALETTES)})"
            ) from None
        self._rebuild()

    # ------------------------------------------------------------ Internals

    def _rebuild(self) -> None:
        """Reconstrucción completa de la escena propia (D2: sin
        actualización incremental). Conserva el resaltado por node_id."""
        self._scene.clear()
        self._rects.clear()
        self._centers.clear()
        self._scene.setBackgroundBrush(QBrush(QColor(self._palette["BG"])))
        model = self._model
        if model is not None:
            pos = _layout_tree(model, node_h=NODE_H)
            pen_normal = QPen(QColor(self._palette["BORDER"]))
            pen_normal.setWidth(1)
            pen_normal.setCosmetic(True)
            for node in model.nodes:
                x, y = pos[node.node_id]
                rect = QRectF(x, y, NODE_W, NODE_H)
                item = _MapNodeItem(node.node_id, rect)
                item.setBrush(
                    QBrush(QColor(self._palette[_fill_token(node)]))
                )
                item.setPen(pen_normal)
                self._scene.addItem(item)
                self._rects[node.node_id] = item
                self._centers[node.node_id] = (
                    x + NODE_W / 2.0,
                    y + NODE_H / 2.0,
                )
                text = self._scene.addSimpleText(str(node.node_id))
                font = QFont()
                font.setPointSize(7)
                text.setFont(font)
                text.setBrush(QBrush(QColor(self._palette["FG"])))
                # Tamaño constante de pantalla: el fitInView del minimapa
                # reduce el factor a ~0.35 en árboles medianos; sin este
                # flag el texto se vuelve ilegible (verificado en las
                # capturas del mini-cierre #3).
                text.setFlag(
                    QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,
                    True,
                )
                text.setZValue(1.0)
                # No interactivo: el clic debe atravesar el texto y
                # llegar al rectángulo (_MapNodeItem -> node_clicked).
                text.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
                # Centrado DENTRO del rectángulo: QGraphicsSimpleTextItem
                # ancla en su esquina superior-izquierda, no en su centro.
                # Con ItemIgnoresTransformations el boundingRect NO cambia
                # con el zoom, así que basta compensar la mitad de sus
                # dimensiones lógicas para que el texto quede centrado
                # sobre rect.center().
                # Centrado real: QGraphicsSimpleTextItem.boundingRect()
                # tiene offset interno (top/left > 0 por métrica de la
                # fuente). Restar la mitad del ancho/alto desplaza el
                # texto hacia abajo. Restar br.center() anula el offset
                # y deja el centro visual del texto sobre rect.center().
                br = text.boundingRect()
                text.setPos(
                    rect.center().x() - br.center().x(),
                    rect.center().y() - br.center().y(),
                )
            # TODO(zona_gris): el hotfix pedía dibujar los conectores
            # ANTES del bucle de rectángulos sobre `self._items`; el
            # atributo real es `self._rects` y debe estar poblado, así
            # que el bloque va tras el bucle y con ZValue(-1) para que
            # las líneas queden bajo los rectángulos (misma intención).
            edge_pen = QPen(QColor(self._palette["FG"]), _EDGE_PEN_WIDTH)
            for node in model.nodes:
                if not node.is_leaf:
                    parent_rect = self._rects[node.node_id].rect()
                    for child_id in node.child_ids:
                        child_rect = self._rects[child_id].rect()
                        # Orientación "horizontal": el árbol crece hacia
                        # la derecha (raíz izquierda, hojas derecha). El
                        # canvas principal sigue vertical; solo el minimapa
                        # gira. Para revertir el giro en el futuro, cambiar
                        # aquí a "vertical" sin tocar el helper.
                        path = _connector_path(
                            parent_rect, child_rect, orientation="vertical"
                        )
                        edge = QGraphicsPathItem(path)
                        edge.setPen(edge_pen)
                        edge.setZValue(-1)
                        self._scene.addItem(edge)
            self._scene.setSceneRect(
                self._scene.itemsBoundingRect().adjusted(
                    -SCENE_MARGIN, -SCENE_MARGIN, SCENE_MARGIN, SCENE_MARGIN
                )
            )
            # Viewport rect: caja semitransparente que indica qué parte del
            # árbol se ve en el canvas principal. Va DENTRO del `if model
            # is not None` (y no al final de _rebuild): con modelo None la
            # escena debe quedar vacía (contrato de los tests de estado
            # vacío). Se actualiza vía set_canvas_viewport (cableado del
            # canvas principal pendiente de una fase futura).
            self._viewport_rect = QGraphicsRectItem()
            self._viewport_rect.setPen(QPen(QColor(self._palette["ACCENT"]), 2))
            self._viewport_rect.setBrush(QBrush(QColor(0, 0, 0, 40)))
            self._viewport_rect.setZValue(2.0)
            self._scene.addItem(self._viewport_rect)
        self._view.fit_view()
        self._apply_highlight()

    def _apply_highlight(self) -> None:
        """Pinta el borde ACCENT grueso en el rectángulo del nodo
        seleccionado y el borde normal en el resto (resaltado pasivo)."""
        pen_normal = QPen(QColor(self._palette["BORDER"]))
        pen_normal.setWidth(1)
        pen_normal.setCosmetic(True)
        pen_highlight = QPen(QColor(self._palette["ACCENT"]))
        pen_highlight.setWidth(_HIGHLIGHT_W)
        pen_highlight.setCosmetic(True)
        for nid, item in self._rects.items():
            item.setPen(
                pen_highlight if nid == self._selected_id else pen_normal
            )
