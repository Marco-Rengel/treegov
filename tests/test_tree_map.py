"""Tests del TreeMap (frontend_v3/tree_map.py). Dual: pytest o python directo.

Layout abstracto desacoplado (cajas 48x30); navegación por node_id.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QGraphicsPathItem

from backend_v3.tree_builder import TreeModel, TreeNode
from backend_v3.types import SplitConfig
from frontend_v3.app import create_app
from frontend_v3.theme import PALETTES
from frontend_v3.tree_map import BOX_H, BOX_W, TreeMap


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = create_app([])
    return app


def _leaf(node_id: int, pd0: float) -> TreeNode:
    k0 = int(round(pd0 * 100))
    return TreeNode(
        node_id=node_id, depth=1, parent_id=0,
        n=100, n_events=(k0, 100 - k0),
        pd_jeffreys=(pd0, 1.0 - pd0), pd_final=(pd0, 1.0 - pd0),
        class_labels=("Event", "Non-event"),
        is_leaf=True, split=None, child_ids=(), leaf_reason="max_depth",
    )


def _model() -> TreeModel:
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
        pd_jeffreys=(41/300, 259/300), pd_final=(41/300, 259/300),
        class_labels=("Event", "Non-event"),
        is_leaf=False, split=split, child_ids=(1, 2, 3), leaf_reason=None,
    )
    return TreeModel(
        root_id=0,
        nodes=(root, _leaf(1, 0.01), _leaf(2, 0.10), _leaf(3, 0.30)),
        method="CHAID",
        params_fingerprint="ab12cd34ef56gh78",
        class_labels=("Event", "Non-event"),
        target_class=1, target_class_index=0,
    )


def test_empty_state():
    _app()
    tm = TreeMap()
    assert tm._items == {}
    assert tm._scene.items() == []
    tm.set_model(None)
    assert tm._scene.items() == []
    tm.close()


def test_layout_and_connectors():
    _app()
    tm = TreeMap()
    tm.resize(240, 240)
    tm.set_model(_model())
    assert len(tm._items) == 4
    # cajas 48x30, independientes del canvas
    for item in tm._items.values():
        assert item.rect().width() == BOX_W
        assert item.rect().height() == BOX_H
    # conectores: 3 QGraphicsPathItem (uno por arista padre->hijo)
    paths = [i for i in tm._scene.items() if isinstance(i, QGraphicsPathItem)]
    assert len(paths) == 3
    # raíz arriba, hojas abajo
    assert tm._items[0].pos().y() < tm._items[1].pos().y()
    tm.close()


def test_node_clicked_emits_id():
    _app()
    tm = TreeMap()
    tm.resize(240, 240)
    tm.set_model(_model())
    captured: list[int] = []
    tm.node_clicked.connect(captured.append)
    # emular el clic directo sobre la señal del view (evita hit-test frágil)
    tm._view.node_clicked.emit(2)
    assert captured == [2]
    tm.close()


def test_selected_node_state():
    _app()
    tm = TreeMap()
    tm.set_model(_model())
    tm.set_selected_node(1)
    assert tm._items[1]._selected is True
    assert tm._items[2]._selected is False
    # Color del prototipo (cian brillante del estado seleccionado)
    assert tm._items[1].pen().color() == QColor("#38bdf8")
    tm.set_selected_node(None)
    assert all(not it._selected for it in tm._items.values())
    tm.close()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
