"""Tests del TreeMap (frontend_v3/tree_map.py, Fase 3.11.b.3, decisión
D2 del diseño auditado 3.11.b). Dual: pytest o python directo.

    .venv\\Scripts\\python -m pytest tests/test_tree_map.py -v
    .venv\\Scripts\\python tests\\test_tree_map.py

Headless: QT_QPA_PLATFORM=offscreen por defecto (setdefault, para que
una sesión con display real conserve su plataforma). El modelo de prueba
es un TreeModel manual y determinista (raíz interna + 3 hojas con
pd_final[0] en los tres tramos del semáforo), sin backend ni CSV.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from backend_v3.tree_builder import TreeModel, TreeNode  # noqa: E402
from backend_v3.types import SplitConfig  # noqa: E402
from frontend_v3.app import create_app  # noqa: E402
from frontend_v3.theme import PALETTES  # noqa: E402
from frontend_v3.tree_map import _HIGHLIGHT_W, _MapNodeItem, TreeMap  # noqa: E402
from frontend_v3.tree_view import NODE_H, NODE_W, _layout_tree  # noqa: E402


def _get_app() -> QApplication:
    """Reuse the running QApplication or create one (Qt is a singleton)."""
    app = QApplication.instance()
    if app is None:
        app = create_app([])
    return app


def _leaf(node_id: int, pd0: float) -> TreeNode:
    """Hoja manual con pd_final[0] controlado (semáforo del minimapa)."""
    k0 = int(round(pd0 * 100))
    return TreeNode(
        node_id=node_id, depth=1, parent_id=0,
        n=100, n_events=(k0, 100 - k0),
        pd_jeffreys=(pd0, 1.0 - pd0), pd_final=(pd0, 1.0 - pd0),
        class_labels=("Event", "Non-event"),
        is_leaf=True, split=None, child_ids=(), leaf_reason="max_depth",
    )


def _model_semaphore() -> TreeModel:
    """Raíz interna + 3 hojas con pd0 = 0.01 / 0.10 / 0.30: cubre los
    tres tramos del semáforo (STATUS_OK / WARN / CRIT) y el ACCENT de la
    raíz interna."""
    split = SplitConfig(
        predictor="seg", method="CHAID",
        statistic=100.0, statistic_name="chi2", df=(2,),
        parent_n=300, child_ns=(100, 100, 100),
        p_value=1e-10, p_value_adjusted=1e-9,
        bonferroni_multiplier=3, n_merges=0,
        branches=(("a",), ("b",), ("c",)),
    )
    root = TreeNode(
        node_id=0, depth=0, parent_id=None,
        n=300, n_events=(41, 259),
        pd_jeffreys=(41 / 300, 259 / 300), pd_final=(41 / 300, 259 / 300),
        class_labels=("Event", "Non-event"),
        is_leaf=False, split=split, child_ids=(1, 2, 3), leaf_reason=None,
    )
    return TreeModel(
        root_id=0,
        nodes=(root, _leaf(1, 0.01), _leaf(2, 0.10), _leaf(3, 0.30)),
        method="CHAID",
        params_fingerprint="ab12cd34ef56gh78",
        class_labels=("Event", "Non-event"),
        target_class=1,
        target_class_index=0,
    )


def test_tree_map_build_empty_state():
    """Construcción: escena y vista PROPIAS (D2), sin ítems; set_model(None)
    es el estado vacío idempotente (mapa vacío sin escena poblada)."""
    _get_app()
    tm = TreeMap()
    assert tm._view.scene() is tm._scene
    assert tm._scene.items() == []
    assert tm._rects == {}
    assert tm.node_pos(0) is None
    tm.set_model(None)
    assert tm._scene.items() == []
    tm.close()
    tm.deleteLater()


def test_tree_map_set_model_items_colors_and_highlight():
    """Mini-cierre #6: resaltado y colores con layout compartido."""
    _get_app()
    pal = PALETTES["light"]
    model = _model_semaphore()
    tm = TreeMap()
    tm.set_model(model)
    pos = _layout_tree(model, node_h=NODE_H)
    for nid, item in tm._rects.items():
        assert item.rect() == QRectF(pos[nid][0], pos[nid][1], NODE_W, NODE_H)
    assert tm._rects[0].brush().color() == QColor(pal["ACCENT"])
    assert tm._rects[1].brush().color() == QColor(pal["STATUS_OK"])
    assert tm.node_pos(0) == (pos[0][0] + NODE_W/2.0, pos[0][1] + NODE_H/2.0)
    tm.set_selected_node(2)
    assert tm._rects[2].pen().color() == QColor(pal["ACCENT"])
    assert tm._scene.selectedItems() == []
    tm.set_selected_node(None)
    tm.set_model(None)
    assert tm._scene.items() == []
    tm.close()


def _click_left(view, pos_view) -> None:
    """Clic izquierdo sintético en `pos_view` (coords del viewport)."""
    local = QPointF(pos_view)
    ev = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        local,                  # localPos (la que lee mousePressEvent)
        local,                  # scenePos (coords de ventana)
        local,                  # globalPos (coords de pantalla)
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.mousePressEvent(ev)


def test_tree_map_click_emits_node_clicked():
    """Clic izquierdo sobre un rectángulo emite node_clicked(node_id);
    clic en el margen de la escena (sin rectángulo) no emite nada."""
    _get_app()
    tm = TreeMap()
    tm.resize(240, 200)
    tm.set_model(_model_semaphore())
    seen: list[int] = []
    tm.node_clicked.connect(seen.append)
    # clic sobre el centro del rectángulo del nodo 2 (coords de escena ->
    # coords del viewport)
    _click_left(tm._view, tm._view.mapFromScene(QPointF(*tm.node_pos(2))))
    assert seen == [2]
    # clic en el margen de la escena (dentro del sceneRect, fuera de todo
    # rectángulo): no emite
    margin = tm._scene.sceneRect().topLeft() + QPointF(5.0, 5.0)
    _click_left(tm._view, tm._view.mapFromScene(margin))
    assert seen == [2]
    tm.close()
    tm.deleteLater()


def test_tree_map_orthogonal_connectors_and_numbered_labels():
    """Mini-cierre #6: minimapa con layout compartido y viewport."""
    from PySide6.QtWidgets import (
        QGraphicsItem as _QI, QGraphicsPathItem as _QPI,
        QGraphicsSimpleTextItem as _QSTI,
    )
    from frontend_v3.tree_map import (
        _EDGE_PEN_WIDTH,
        MAP_MAX_ZOOM,
        MAP_MIN_ZOOM,
    )
    from frontend_v3.tree_view import NODE_H, NODE_W, _layout_tree
    _get_app()
    model = _model_semaphore()
    for theme in ("light", "dark"):
        pal = PALETTES[theme]
        tm = TreeMap()
        tm.set_theme(theme)
        tm.resize(240, 200)
        tm.set_model(model)
        pos = _layout_tree(model, node_h=NODE_H)
        # Rectángulos compartidos
        for item in tm._rects.values():
            assert item.rect().width() == NODE_W
            assert item.rect().height() == NODE_H
        # Conectores verticales
        paths = [i for i in tm._scene.items() if isinstance(i, _QPI)]
        for path in paths:
            assert path.pen().color() == QColor(pal["FG"])
        # Etiquetas: una por nodo y centradas sobre rect.center()
        labels = [i for i in tm._scene.items() if isinstance(i, _QSTI)]
        assert len(labels) == len(model.nodes)
        for lbl in labels:
            br = lbl.boundingRect()
            lbl_cx = lbl.pos().x() + br.center().x()
            lbl_cy = lbl.pos().y() + br.center().y()
            match = [
                it for it in tm._rects.values()
                if abs(it.rect().center().x() - lbl_cx) < 0.5
                and abs(it.rect().center().y() - lbl_cy) < 0.5
            ]
            assert len(match) == 1, f"etiqueta {lbl.text()} no centrada"
        # Zoom dinámico clamped entre [MAP_MIN_ZOOM, MAP_MAX_ZOOM]
        zoom = tm._view.transform().m11()
        assert MAP_MIN_ZOOM - 1e-9 <= zoom <= MAP_MAX_ZOOM + 1e-9
        tm.close()


# ---------------------------------------------------------------------------
# ejecución directa sin pytest
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        obj
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nOK - {len(tests)} tests superados")
