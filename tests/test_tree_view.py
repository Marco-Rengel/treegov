"""Tests del visor interactivo de arbol (frontend_v3/tree_view.py +
orquestacion en frontend_v3/main_window.py, Fase 2.2). Dual: pytest o
python directo.

    .venv\\Scripts\\python -m pytest tests/test_tree_view.py -v
    .venv\\Scripts\\python tests\\test_tree_view.py

Headless: QT_QPA_PLATFORM=offscreen por defecto (setdefault). Los tests
de integracion usan un CSV sintetico en tempfile; NADA se escribe en
data/ (zona protegida). Las identidades de layout se verifican sobre
arboles CONOCIDOS (fixtures deterministicos), no sobre autoreferencias.
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402  (tests/ SI puede importar: fuera del frontend)
import pandas as pd  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QGraphicsPathItem,
    QGraphicsSimpleTextItem,
)

from backend_v3.chaid_engine import ChaidEngine  # noqa: E402
from backend_v3.crt_engine import CrtEngine  # noqa: E402
from backend_v3.tree_builder import (  # noqa: E402
    TreeBuilder,
    TreeModel,
    TreeNode,
)
from backend_v3.types import PredictorType, SplitConfig, TargetType  # noqa: E402
from frontend_v3.app import create_app  # noqa: E402
from frontend_v3.i18n import language_bus, set_language, tr  # noqa: E402
from frontend_v3.main_window import MainWindow  # noqa: E402
from frontend_v3.theme import PALETTES  # noqa: E402
from frontend_v3.tree_view import (  # noqa: E402
    H_GAP,
    LARGE_TREE_THRESHOLD,
    NODE_H,
    NODE_W,
    V_GAP,
    ZOOM_MAX,
    ZOOM_MIN,
    ZOOM_STEP,
    NodeItem,
    TreePanel,
    _layout_tree,
)

_SLOT = NODE_W + H_GAP   # distancia entre slots de hojas (unidad del layout)
_LAYER = NODE_H + V_GAP  # distancia entre niveles de profundidad


def _get_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = create_app([])
    return app


def _make_panel() -> TreePanel:
    _get_app()
    panel = TreePanel()
    panel.resize(900, 600)  # viewport con tamano real para fitInView
    return panel


def _crt_model() -> TreeModel:
    """120 filas; y = 1_{edad >= 40} -> arbol conocido (Fase 1): raiz con
    split en edad<=39.5 y 2 hojas de n=60 (fixture de test_tree_builder)."""
    edad = np.tile(np.arange(20, 60), 3)
    df = pd.DataFrame({"edad": edad})
    y = pd.Series((edad >= 40).astype(int))
    spec = {"edad": PredictorType.CONTINUOUS}
    return TreeBuilder(
        CrtEngine(), target_type=TargetType.BINARY, target_class=1,
        class_labels=("Event", "Non-event"),
        max_depth=4, min_child_size=5,
    ).build(df, y, spec)


def _chaid_model() -> TreeModel:
    """90 filas; seg en {a,b,c} con tasas 0 / 1 / 0.5 (deterministas):
    chi2 fuerte entre cada par -> CHAID no fusiona: raiz con 3 ramas."""
    seg = np.tile(["a", "b", "c"], 30)
    ys = []
    for i, s in enumerate(seg):
        if s == "a":
            ys.append(0)
        elif s == "b":
            ys.append(1)
        else:
            ys.append((i // 3) % 2)
    df = pd.DataFrame({"seg": seg})
    y = pd.Series(ys)
    spec = {"seg": PredictorType.NOMINAL}
    return TreeBuilder(
        ChaidEngine(), target_type=TargetType.BINARY, target_class=1,
        class_labels=("Event", "Non-event"),
        max_depth=4, min_child_size=10,
    ).build(df, y, spec)


def _big_model(n_leaves: int = LARGE_TREE_THRESHOLD + 50) -> TreeModel:
    """Arbol manual (raiz CHAID con N ramas) para disparar el aviso OBS 1."""
    branches = tuple((i,) for i in range(n_leaves))
    split = SplitConfig(
        predictor="seg", method="CHAID",
        statistic=5000.0, statistic_name="chi2", df=(n_leaves - 1,),
        parent_n=100 * n_leaves, child_ns=(100,) * n_leaves,
        p_value=1e-300, p_value_adjusted=1e-290,
        bonferroni_multiplier=100, n_merges=0, branches=branches,
    )
    nodes = [TreeNode(
        node_id=0, depth=0, parent_id=None,
        n=100 * n_leaves, n_events=(50 * n_leaves, 50 * n_leaves),
        pd_jeffreys=(0.5, 0.5), pd_final=(0.5, 0.5),
        class_labels=("Event", "Non-event"),
        is_leaf=False, split=split,
        child_ids=tuple(range(1, n_leaves + 1)), leaf_reason=None,
    )]
    for i in range(1, n_leaves + 1):
        nodes.append(TreeNode(
            node_id=i, depth=1, parent_id=0,
            n=100, n_events=(50, 50),
            pd_jeffreys=(0.5, 0.5), pd_final=(0.5, 0.5),
            class_labels=("Event", "Non-event"),
            is_leaf=True, split=None, child_ids=(), leaf_reason="max_depth",
        ))
    return TreeModel(
        root_id=0, nodes=tuple(nodes), method="CHAID",
        params_fingerprint="ab12cd34ef56gh78",
        class_labels=("Event", "Non-event"),
        target_class=1,
        target_class_index=0,
    )


# ---------------------------------------------------------------------------
# 1-2: layout puro (determinismo + identidades geometricas)
# ---------------------------------------------------------------------------


def test_layout_deterministic():
    model = _crt_model()
    assert _layout_tree(model) == _layout_tree(model)


def test_layout_known_positions():
    model = _crt_model()
    assert len(model.nodes) == 3            # identidad del fixture (Fase 1)
    assert model.nodes[0].split.threshold == 39.5  # punto medio 39|40
    pos = _layout_tree(model)
    assert pos[1] == (0.0, _LAYER)          # hoja izquierda: slot 0
    assert pos[2] == (_SLOT, _LAYER)        # hoja derecha: slot 1
    assert pos[0] == (_SLOT / 2.0, 0.0)     # raiz centrada sobre sus hijos
    # identidad general (Reingold & Tilford): padre = punto medio de extremos
    for nd in model.nodes:
        if not nd.is_leaf:
            xs = [pos[c][0] for c in nd.child_ids]
            assert pos[nd.node_id][0] == (min(xs) + max(xs)) / 2.0


# ---------------------------------------------------------------------------
# 3-4: construccion de escena (conteos, aviso OBS 1, multi-via CHAID)
# ---------------------------------------------------------------------------


def test_scene_counts_and_large_warning():
    panel = _make_panel()
    panel.set_model(_crt_model(), "BANKING")
    items = [i for i in panel._scene.items() if isinstance(i, NodeItem)]
    edges = [i for i in panel._scene.items() if isinstance(i, QGraphicsPathItem)]
    assert len(items) == 3                  # un NodeItem por nodo
    assert len(edges) == 2                  # n_nodos - 1 aristas
    assert panel._lbl_warning.isHidden()    # arbol pequenio: sin aviso

    panel.set_model(_big_model(), "BANKING")  # 251 nodos > 200 (OBS 1)
    items_big = [i for i in panel._scene.items() if isinstance(i, NodeItem)]
    assert len(items_big) == LARGE_TREE_THRESHOLD + 51
    assert not panel._lbl_warning.isHidden()
    assert str(LARGE_TREE_THRESHOLD + 51) in panel._lbl_warning.text()
    panel.close()
    panel.deleteLater()


def test_layout_and_labels_multiway_chaid():
    model = _chaid_model()
    assert len(model.nodes) == 4            # raiz + 3 ramas (sin fusiones)
    pos = _layout_tree(model)
    assert pos[1] == (0.0, _LAYER)
    assert pos[2] == (_SLOT, _LAYER)
    assert pos[3] == (2 * _SLOT, _LAYER)
    assert pos[0] == (_SLOT, 0.0)           # (0 + 2S) / 2
    panel = _make_panel()
    panel.set_model(model, "BANKING")
    edges = [i for i in panel._scene.items() if isinstance(i, QGraphicsPathItem)]
    assert len(edges) == 3
    labels = {
        i.text() for i in panel._scene.items()
        if isinstance(i, QGraphicsSimpleTextItem)
    }
    assert {"{a}", "{b}", "{c}"} <= labels  # etiqueta de rama por grupo
    panel.close()
    panel.deleteLater()


# ---------------------------------------------------------------------------
# 5-6: seleccion y zoom
# ---------------------------------------------------------------------------


def test_selection_signal():
    panel = _make_panel()
    panel.set_model(_crt_model(), "BANKING")
    seen: list[int] = []
    panel.node_selected.connect(seen.append)
    panel.select_node(2)
    _get_app().processEvents()
    assert seen == [2]
    assert panel.selected_node_id() == 2
    panel.close()
    panel.deleteLater()


def test_zoom_clamps():
    panel = _make_panel()
    panel.set_model(_crt_model(), "BANKING")   # auto-fit ya ocurrio
    view = panel._view
    factors: list[float] = []
    view.zoom_changed.connect(factors.append)

    z0 = view.zoom_factor()
    view.zoom_in()
    assert abs(view.zoom_factor() - min(ZOOM_MAX, z0 * ZOOM_STEP)) < 1e-9
    assert abs(view.transform().m11() - view.zoom_factor()) < 1e-9

    for _ in range(100):
        view.zoom_in()
    assert view.zoom_factor() == ZOOM_MAX      # clamp superior
    for _ in range(400):
        view.zoom_out()
    assert view.zoom_factor() == ZOOM_MIN      # clamp inferior
    assert factors[-1] == ZOOM_MIN             # señal emitida en cada paso
    assert panel._lbl_zoom.text() == f"{round(ZOOM_MIN * 100)}%"

    view.zoom_fit()
    assert view.zoom_factor() > ZOOM_MIN       # fit real (viewport 900x600)
    panel.close()
    panel.deleteLater()


# ---------------------------------------------------------------------------
# 7-8: retraduccion en caliente y recoloreo por tema
# ---------------------------------------------------------------------------


def test_retranslate_preserves_selection():
    panel = _make_panel()
    panel.set_model(_crt_model(), "BANKING")
    panel.select_node(1)
    try:
        set_language("es")
        language_bus.language_changed.emit("es")
        item1 = panel._scene._items[1]
        assert panel.selected_node_id() == 1   # seleccion preservada (rebuild)
        assert "HOJA" in item1._text.toPlainText()       # badge retraducido
        assert "nodos" in panel._lbl_header.text()       # cabecera ES
    finally:
        set_language("en")
        language_bus.language_changed.emit("en")
    assert "HOJA" not in panel._scene._items[1]._text.toPlainText()
    panel.close()
    panel.deleteLater()


def test_theme_recolor_on_switch():
    _get_app()
    w = MainWindow()
    w._tree_panel.set_model(_crt_model(), "BANKING")
    root_light = w._tree_panel._scene._items[0].brush().color()
    assert root_light == QColor(PALETTES["light"]["SURFACE"])
    w._switch_theme("dark")
    root_dark = w._tree_panel._scene._items[0].brush().color()
    assert root_dark == QColor(PALETTES["dark"]["SURFACE"])
    w._switch_theme("light")                   # restaura (orden de la suite)
    assert w._tree_panel._scene._items[0].brush().color() == root_light
    w.close()
    w.deleteLater()


# ---------------------------------------------------------------------------
# 9-10: estado vacio e integracion MainWindow <-> Session (backend real)
# ---------------------------------------------------------------------------


def test_empty_state():
    panel = _make_panel()
    assert panel._lbl_header.text() == ""
    assert panel._lbl_warning.isHidden()
    assert not panel._btn_in.isEnabled()
    assert not panel._btn_fit.isEnabled()
    texts = [
        i.text() for i in panel._scene.items()
        if isinstance(i, QGraphicsSimpleTextItem)
    ]
    assert any(tr("tree_empty") == t for t in texts)
    # idioma/tema sin modelo: el placeholder se reconstruye, nada rompe
    try:
        set_language("es")
        language_bus.language_changed.emit("es")
        texts = [
            i.text() for i in panel._scene.items()
            if isinstance(i, QGraphicsSimpleTextItem)
        ]
        assert any(tr("tree_empty", "es") == t for t in texts)
        panel.set_theme("dark")
        panel.set_theme("light")
    finally:
        set_language("en")
        language_bus.language_changed.emit("en")
    # ciclo completo: modelo -> clear -> placeholder de nuevo
    panel.set_model(_crt_model(), "BANKING")
    assert panel._btn_in.isEnabled()
    panel.clear_model()
    assert not panel._btn_in.isEnabled()
    assert panel._lbl_header.text() == ""
    panel.close()
    panel.deleteLater()


def test_e2e_mainwindow():
    with tempfile.TemporaryDirectory() as td:
        edad = np.tile(np.arange(20, 60), 3)
        seg = np.tile(["a", "b", "c"], 40)
        df = pd.DataFrame({"edad": edad, "seg": seg,
                           "default": (edad >= 40).astype(int)})
        csv_path = Path(td) / "mini_gui.csv"
        df.to_csv(csv_path, index=False)

        _get_app()
        w = MainWindow()
        assert w._load_dataset_path(str(csv_path)) is True
        # sin modelo: placeholder en la pestaña Tree y HUD en estado vacio
        assert tr("tree_prop_empty") in w._hud_body.text()

        cfg = {
            "engine": "CRT", "target": "default",
            "predictors": ["edad", "seg"],
            "target_class": 1,
            "class_labels": {0: "Non-event", 1: "Event"},
                "weight_col": None,
                "population_col": None,
                "population_ok_values": (),
            "train_frac": 0.7, "seed": 42,
            "max_depth": 4, "min_child_size": 5,
            "governance_mode": "BANKING",
            "apply_jeffreys": True, "pd_floor": 0.0003,
        }
        w._on_wizard_finished(cfg)
        model = w._session.state.tree
        assert model is not None
        assert w._tabs.count() == 4
        assert w._tabs.currentWidget() is w._tree_panel
        items = [i for i in w._tree_panel._scene.items()
                 if isinstance(i, NodeItem)]
        assert len(items) == len(model.nodes)
        hdr = w._tree_panel._lbl_header.text()
        assert model.method in hdr and model.params_fingerprint in hdr
        # HUD: resumen del modelo (sin seleccion)
        assert model.params_fingerprint in w._hud_body.text()
        # seleccion de nodo -> tarjeta de detalle en el panel de propiedades
        w._tree_panel.select_node(1)
        assert tr("tree_prop_node") in w._hud_body.text()
        assert model.nodes[1].split is None  # hoja identificable en detalle
        w._tree_panel.select_node(0)
        assert tr("tree_prop_predictor") in w._hud_body.text()
        # entrenamiento fallido -> rollback: el visor no conserva arbol
        bad = dict(cfg, engine="MOTOR_INEXISTENTE")
        w._on_wizard_finished(bad)
        assert w._session.state.state.name == "DATA_LOADED"
        assert w._session.state.tree is None
        assert [i for i in w._tree_panel._scene.items()
                if isinstance(i, NodeItem)] == []
        assert tr("tree_prop_empty") in w._hud_body.text()
        w.close()
        w.deleteLater()


# ---------------------------------------------------------------------------
# ejecucion directa sin pytest
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
