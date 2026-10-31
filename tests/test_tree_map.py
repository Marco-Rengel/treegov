"""Acceptance tests for the clean-room TreeMap (frontend_v3/tree_map.py).

Part of mini-closure A2 (Clean Room rewrite, 31/10/2026): the TreeMap
widget was rewritten from scratch against the fixed decisions D1-D7
(Reingold-Tilford simplified layout, orthogonal 3-segment connectors,
100% palette-driven colors, zoom-clamped fit). These tests encode the
acceptance criteria for that rewrite; the previous four tests targeted
the superseded prototype port and were removed.

Dual runner: ``pytest tests/test_tree_map.py`` or ``python`` directly.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsSimpleTextItem,
)

from backend_v3.tree_builder import TreeModel, TreeNode
from backend_v3.types import SplitConfig
from frontend_v3.app import create_app
from frontend_v3.theme import PALETTES
from frontend_v3.tree_map import TreeMap

# Hard-coded hex colors of the superseded prototype. None of them may
# appear in any pen or brush of the rewritten scene (decision D3).
_PROTOTYPE_HEXES = frozenset(
    {"#1e293b", "#059669", "#3b82f6", "#38bdf8", "#1d4ed8"}
)


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
    """Fixture: one CHAID root with three leaves (4 nodes total)."""
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


def test_minimap_empty_state():
    _app()
    tm = TreeMap()
    assert tm._items == {}
    assert tm._scene.items() == []
    tm.set_model(None)
    assert tm._scene.items() == []
    tm.close()


def test_minimap_layout_deterministic():
    _app()
    tm1 = TreeMap()
    tm1.set_model(_model())
    tm2 = TreeMap()
    tm2.set_model(_model())
    # Same IDs in the same insertion order, same exact positions.
    assert list(tm1._items.keys()) == list(tm2._items.keys())
    for nid in tm1._items:
        assert tm1._items[nid].pos() == tm2._items[nid].pos()
    tm1.close()
    tm2.close()


def test_minimap_uses_palette_tokens():
    _app()
    tm = TreeMap()  # default palette: light
    tm.set_model(_model())
    for item in tm._scene.items():
        pen = item.pen()
        if pen.style() != Qt.PenStyle.NoPen:
            assert pen.color().name() not in _PROTOTYPE_HEXES
        brush = item.brush()
        if brush.style() != Qt.BrushStyle.NoBrush:
            assert brush.color().name() not in _PROTOTYPE_HEXES
    palette = PALETTES["light"]
    # Connector borders: thin pen in BORDER (decision D2).
    edges = [i for i in tm._scene.items() if isinstance(i, QGraphicsPathItem)]
    assert edges, "fixture must produce connectors"
    for edge in edges:
        assert edge.pen().color() == QColor(palette["BORDER"])
    # Leaf boxes: subtle differential border in STATUS_OK (decision D3).
    for item in tm._items.values():
        if item.is_leaf:
            assert item.pen().color() == QColor(palette["STATUS_OK"])
    tm.close()


def test_minimap_node_clicked_emits_id():
    _app()
    tm = TreeMap()
    tm.set_model(_model())
    captured: list[int] = []
    tm.node_clicked.connect(captured.append)
    # Emit the view signal directly (avoids a fragile hit-test).
    tm._view.node_clicked.emit(2)
    assert captured == [2]
    assert isinstance(captured[0], int)
    tm.close()


def test_minimap_highlight_follows_selection():
    _app()
    tm = TreeMap()
    tm.set_model(_model())
    palette = PALETTES["light"]
    tm.set_selected_node(2)
    assert tm._items[2].brush().color() == QColor(palette["ACCENT"])
    assert tm._items[2]._texto.brush().color() == QColor(palette["ACCENT_FG"])
    for nid, item in tm._items.items():
        if nid != 2:
            assert item.brush().color() == QColor(palette["SURFACE"])
    tm.set_selected_node(None)
    for item in tm._items.values():
        assert item.brush().color() == QColor(palette["SURFACE"])
    tm.close()


def test_minimap_renders_all_nodes():
    _app()
    tm = TreeMap()
    tm.set_model(_model())
    # 4 node boxes (1 root + 3 leaves) and 3 orthogonal connectors
    # (one per parent->child edge).
    assert len(tm._items) == 4
    edges = [i for i in tm._scene.items() if isinstance(i, QGraphicsPathItem)]
    assert len(edges) == 3
    tm.close()


def test_minimap_id_legible_bajo_zoom():
    _app()
    tm = TreeMap()
    tm.set_model(_model())
    texts = [
        i for i in tm._scene.items()
        if isinstance(i, QGraphicsSimpleTextItem) and i.text()
    ]
    assert len(texts) == 4
    flag = QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations
    for text in texts:
        assert bool(text.flags() & flag)
        assert text.font().pointSize() == 8
    tm.close()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
