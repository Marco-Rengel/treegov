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
from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QGraphicsPathItem,
    QGraphicsSimpleTextItem,
    QGraphicsTextItem,
    QStyleOptionGraphicsItem,
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


def _render_node(item: NodeItem, scale: int = 2) -> QImage:
    """Renderiza un NodeItem off-screen a traves de su propio paint()
    (disenio QPainter, sin HTML). scale=2 -> 1 px del item = 2 px imagen."""
    img = QImage(
        int(item.NODE_W * scale),
        int(item.NODE_H * scale),
        QImage.Format.Format_ARGB32,
    )
    img.fill(QColor(0, 0, 0, 0))
    painter = QPainter(img)
    painter.scale(float(scale), float(scale))
    item.paint(painter, QStyleOptionGraphicsItem(), None)
    painter.end()
    return img


def _px(img: QImage, item: NodeItem, x: float, y: float) -> QColor:
    """Pixel en coordenadas de ITEM (x, y) sobre la imagen renderizada."""
    s = img.width() / item.NODE_W
    return img.pixelColor(int(x * s), int(y * s))


def _leaf_node(node_id: int, pd0: float) -> TreeNode:
    """Hoja manual con pd_final[0] controlado (semaforo de cabecera)."""
    k0 = int(round(pd0 * 100))
    return TreeNode(
        node_id=node_id, depth=1, parent_id=0,
        n=100, n_events=(k0, 100 - k0),
        pd_jeffreys=(pd0, 1.0 - pd0), pd_final=(pd0, 1.0 - pd0),
        class_labels=("Event", "Non-event"),
        is_leaf=True, split=None, child_ids=(), leaf_reason="max_depth",
    )


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


def _binned_chaid_model() -> TreeModel:
    """Raiz CHAID con split continuo binned (Fase 3.10.b): cortes
    (25.5, 40.0, 55.0) -> bins 0..3; ramas = {0}, {1,2}, {3}."""
    split = SplitConfig(
        predictor="ingreso", method="CHAID",
        statistic=42.0, statistic_name="chi2", df=(1,),
        parent_n=120, child_ns=(40, 40, 40),
        p_value=1e-6, p_value_adjusted=1e-5,
        bonferroni_multiplier=6, n_merges=7,
        branches=(("bin_0",), ("bin_1", "bin_2"), ("bin_3",)),
        bin_edges=(25.5, 40.0, 55.0),
    )
    nodes = [TreeNode(
        node_id=0, depth=0, parent_id=None,
        n=120, n_events=(60, 60),
        pd_jeffreys=(0.5, 0.5), pd_final=(0.5, 0.5),
        class_labels=("Event", "Non-event"),
        is_leaf=False, split=split, child_ids=(1, 2, 3), leaf_reason=None,
    )]
    for i in (1, 2, 3):
        nodes.append(TreeNode(
            node_id=i, depth=1, parent_id=0,
            n=40, n_events=(20, 20),
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


def test_edge_label_binned_continuous():
    """Split continuo binned (CHAID con bin_edges): las etiquetas de
    rama muestran los cortes numericos reales, no "bin_<i>":
    -inf -> "≤ <high>", +inf -> "> <low>", rango -> "(<low>, <high>]".
    Los splits categoricos y por umbral NO cambian."""
    from frontend_v3.tree_view import _edge_label

    split = _binned_chaid_model().nodes[0].split
    assert _edge_label(split, 0) == "≤ 25.5"        # bin 0 baja a -inf
    assert _edge_label(split, 1) == "(25.5, 55]"    # rango cerrado
    assert _edge_label(split, 2) == "> 55"          # bin 3 sube a +inf

    # Fallback defensivo: grupo sin etiquetas bin_* con bin_edges.
    split_txt = SplitConfig(
        predictor="seg", method="CHAID",
        statistic=10.0, statistic_name="chi2", df=(1,),
        parent_n=80, child_ns=(40, 40),
        p_value=1e-3, p_value_adjusted=1e-2,
        bonferroni_multiplier=2, n_merges=1,
        branches=(("a",), ("b",)),
        bin_edges=(1.5,),
    )
    assert _edge_label(split_txt, 0) == "{a}"

    # Categorico clasico (bin_edges=()) y umbral (CRT): intactos.
    cat_split = _chaid_model().nodes[0].split
    assert _edge_label(cat_split, 0) == "{a}"
    thr_split = _crt_model().nodes[0].split
    assert _edge_label(thr_split, 0) == "≤ 39.5"
    assert _edge_label(thr_split, 1) == "> 39.5"

    # En el canvas: las aristas del modelo binned muestran numeros.
    panel = _make_panel()
    panel.set_model(_binned_chaid_model(), "BANKING")
    labels = {
        i.text() for i in panel._scene.items()
        if isinstance(i, QGraphicsSimpleTextItem)
    }
    assert {"≤ 25.5", "(25.5, 55]", "> 55"} <= labels
    assert not any(lbl.startswith("{bin_") for lbl in labels)
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
    panel.set_model(_crt_model(), "BANKING")   # zoom inicial 1.0 (3.11.a)
    view = panel._view
    factors: list[float] = []
    view.zoom_changed.connect(factors.append)

    z0 = view.zoom_factor()
    view.zoom_in()
    assert abs(
        view.zoom_factor() - max(ZOOM_MIN, min(ZOOM_MAX, z0 * ZOOM_STEP))
    ) < 1e-9
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
    # fit real (viewport 900x600): ni el fallback vacio (1.0) ni un clamp
    assert 0.0 < view.zoom_factor() != 1.0
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
        assert item1._header == ""                     # hoja: sin badge
        assert item1._header_full == "Nodo 1"          # prefijo retraducido
        assert "nodos" in panel._lbl_header.text()       # cabecera ES
    finally:
        set_language("en")
        language_bus.language_changed.emit("en")
    assert panel._scene._items[1]._header == ""
    assert panel._scene._items[1]._header_full == "Node 1"
    panel.close()
    panel.deleteLater()


def test_theme_recolor_on_switch():
    _get_app()
    w = MainWindow()
    w._tree_panel.set_model(_crt_model(), "BANKING")
    # Hoja de auditoría: el cuerpo del nodo pintado con QPainter es
    # SIEMPRE blanco puro (#FFFFFF), independiente del tema claro/oscuro;
    # la cabecera del nodo interno SI sigue el token ACCENT del tema.
    item0 = w._tree_panel._scene._items[0]
    assert _px(_render_node(item0), item0, 110, 33) == QColor("#FFFFFF")
    assert (
        _px(_render_node(item0), item0, 6, 12)
        == QColor(PALETTES["light"]["ACCENT"])
    )
    w._switch_theme("dark")
    item0d = w._tree_panel._scene._items[0]
    assert _px(_render_node(item0d), item0d, 110, 33) == QColor("#FFFFFF")
    assert (
        _px(_render_node(item0d), item0d, 6, 12)
        == QColor(PALETTES["dark"]["ACCENT"])
    )
    # lo que SI sigue al tema es el fondo de la escena
    bg_dark = w._tree_panel._scene.backgroundBrush().color()
    assert bg_dark == QColor(PALETTES["dark"]["BG"])
    w._switch_theme("light")                   # restaura (orden de la suite)
    item0l = w._tree_panel._scene._items[0]
    assert _px(_render_node(item0l), item0l, 110, 33) == QColor("#FFFFFF")
    assert (
        w._tree_panel._scene.backgroundBrush().color()
        == QColor(PALETTES["light"]["BG"])
    )
    w.close()
    w.deleteLater()


def test_node_paint_classic_station_design():
    """Diseño QPainter (hoja de auditoría): caja fija NODE_W x NODE_H con
    el cuerpo SIEMPRE blanco (#FFFFFF) en ambos temas; cabecera de 26 px
    (banda ACCENT en internos; semáforo verde/naranja/rojo en hojas según
    pd_final[0]: <0.05 / <0.15 / resto) con texto blanco en negrita; filas
    por clase con cuadrado semáforo + % + n; fila Total (N) en negrita;
    gráfica apilada; footer de 20 px con Gini (hojas) o stats del split
    (internos) arrancando exactamente en NODE_H - 20; borde $BORDER
    ($ACCENT si está seleccionado). Todo el ink queda DENTRO del
    boundingRect."""
    _get_app()
    model = _crt_model()
    root, leaf = model.nodes[0], model.nodes[1]
    assert not root.is_leaf and leaf.is_leaf and leaf.pd_final[0] < 0.05
    for theme in ("light", "dark"):
        pal = PALETTES[theme]
        item = NodeItem(root, pal, 1.0)
        img = _render_node(item)
        # 1. huecos del cuerpo y banda de footer siempre blancos
        assert _px(img, item, 110, 28) == QColor("#FFFFFF")   # sobre filas
        assert _px(img, item, 6, 116) == QColor("#FFFFFF")    # banda footer
        # 2. cabecera ACCENT (interno), texto blanco en negrita
        assert _px(img, item, 6, 12) == QColor(pal["ACCENT"])
        assert item._font_header.bold()
        assert item._header_fg == QColor("#FFFFFF")
        # 3. borde no seleccionado = $BORDER; seleccionado = $ACCENT
        assert _px(img, item, 0, 60) == QColor(pal["BORDER"])
        item.setSelected(True)
        img_sel = _render_node(item)
        assert _px(img_sel, item, 1, 60) == QColor(pal["ACCENT"])
        item.setSelected(False)
    # 4. semáforo de cabecera en hojas (umbrales 0.05 / 0.15)
    pal = PALETTES["light"]
    for pd0, token in (
        (0.01, "STATUS_OK"),
        (0.10, "STATUS_WARN"),
        (0.30, "STATUS_CRIT"),
    ):
        leaf_item = NodeItem(_leaf_node(1, pd0), pal, 1.0)
        img_leaf = _render_node(leaf_item)
        assert _px(img_leaf, leaf_item, 6, 12) == QColor(pal[token])
        assert leaf_item._header == ""                 # hoja: sin badge
    # 5. textos pintados: helpers puros auditados + strings precalculados
    from frontend_v3.tree_view import _caption_text, _footer_text
    assert _caption_text(root) == "edad"               # predictor (interno)
    assert _caption_text(leaf) == ""                   # hoja: cadena vacía
    assert "Adj. P-value:" in _footer_text(root)       # stats del split
    assert "Gini:" in _footer_text(leaf)               # impureza de la hoja
    assert NodeItem(root, pal, 1.0)._header == "edad"
    assert NodeItem(leaf, pal, 0.5)._header == ""
    # 6. título de cabecera: "Node <id> — <predictor>" (interno) /
    #    "Node <id>" (hoja, sin badge).
    assert (
        NodeItem(root, pal, 1.0)._header_full
        == f"{tr('tree_prop_node')} {root.node_id} — edad"
    )
    assert (
        NodeItem(leaf, pal, 0.5)._header_full
        == f"{tr('tree_prop_node')} {leaf.node_id}"
    )
    assert "Adj. P-value:" in NodeItem(root, pal, 1.0)._footer
    assert "Gini:" in NodeItem(leaf, pal, 0.5)._footer


def test_node_box_fixed_geometry():
    """Diseño QPainter: TODAS las cajas son exactamente NODE_W x NODE_H
    (geometría fija, sin auto-ajuste HTML ni espacio vacío); boundingRect
    coincide con las constantes de clase; la escena apila los niveles a
    NODE_H + V_GAP."""
    panel = _make_panel()
    panel.set_model(_crt_model(), "BANKING")
    items = panel._scene._items
    for item in items.values():
        assert item.boundingRect() == QRectF(0.0, 0.0, NODE_W, NODE_H)
        assert item.NODE_W == NODE_W and item.NODE_H == NODE_H
        assert item.HEADER_H + item.FOOTER_H < item.NODE_H  # bandas internas
    # layout: la distancia entre niveles es NODE_H + V_GAP (fija)
    dy = items[1].pos().y() - items[0].pos().y()
    assert dy == NODE_H + V_GAP
    panel.close()
    panel.deleteLater()


def test_node_total_row_and_stacked_bar():
    """Fila Total (N) en negrita (separador sutil encima) + gráfica de
    barras apilada proporcional a n_events, justo encima del footer
    (NODE_H - 20): índice 0 = clase de interés/Bad en rojo #D32F2F,
    índice 1 = Good en verde #2E7D32; multiclase cicla _CLASS_BAR_COLORS.
    El último segmento absorbe el redondeo (borde derecho exacto)."""
    _get_app()
    pal = PALETTES["light"]
    model = _crt_model()                       # raíz: n=120, k=(60,60)
    root = model.nodes[0]
    assert root.n == 120 and root.n_events == (60, 60)
    item = NodeItem(root, pal, 1.0)
    assert item._total_n == f"{root.n:,}"
    assert item._font_total.bold()
    img = _render_node(item)
    bar_cy = item.NODE_H - item.FOOTER_H - 4.0 - item.BAR_H / 2.0  # centro barra
    # mitad roja (izquierda, clase de interés) + mitad verde; frontera
    # exacta en x = 8 + (60/120)*204 = 110
    assert _px(img, item, 20, bar_cy) == QColor("#D32F2F")
    assert _px(img, item, 200, bar_cy) == QColor("#2E7D32")
    assert _px(img, item, 109, bar_cy) == QColor("#D32F2F")
    assert _px(img, item, 111, bar_cy) == QColor("#2E7D32")
    # hojas CHAID: barra toda verde (0 eventos) o toda roja (30 eventos)
    chaid = _chaid_model()
    leaf_a, leaf_b = chaid.nodes[1], chaid.nodes[2]
    assert leaf_a.n_events == (0, 30) and leaf_b.n_events == (30, 0)
    ia, ib = NodeItem(leaf_a, pal, 1.0), NodeItem(leaf_b, pal, 1.0)
    assert _px(_render_node(ia), ia, 110, bar_cy) == QColor("#2E7D32")
    assert _px(_render_node(ib), ib, 110, bar_cy) == QColor("#D32F2F")
    # multiclase (K=3): segmentos 50/30/20 con _CLASS_BAR_COLORS
    multi = TreeNode(
        node_id=1, depth=1, parent_id=0, n=100, n_events=(50, 30, 20),
        pd_jeffreys=(0.5, 0.3, 0.2), pd_final=(0.5, 0.3, 0.2),
        class_labels=("Bad", "Good", "Other"),
        is_leaf=True, split=None, child_ids=(), leaf_reason="max_depth",
    )
    im = NodeItem(multi, pal, 1.0)
    imgm = _render_node(im)
    assert _px(imgm, im, 20, bar_cy) == QColor("#D32F2F")    # 50% rojo
    assert _px(imgm, im, 140, bar_cy) == QColor("#2E7D32")   # 30% verde
    assert _px(imgm, im, 200, bar_cy) == QColor("#1A73E8")   # 20% azul


def test_node_total_pct_global():
    panel = _make_panel()
    panel.set_model(_crt_model(), "BANKING")
    # La raíz debe mostrar 100.00
    raiz_item = panel._scene._items[0]
    assert raiz_item._pct_global == 1.0
    # Una hoja (n=60 en el fixture _crt_model) debe mostrar 50.00
    hoja_item = panel._scene._items[1]
    assert hoja_item._pct_global == 0.5
    panel.close()
    panel.deleteLater()


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
        i.toPlainText() for i in panel._scene.items()
        if isinstance(i, QGraphicsTextItem)
    ]
    assert any(tr("tree_empty") in t for t in texts)
    assert any("TreeGov" in t for t in texts)        # marca en la tarjeta
    # idioma/tema sin modelo: el placeholder se reconstruye, nada rompe
    try:
        set_language("es")
        language_bus.language_changed.emit("es")
        texts = [
            i.toPlainText() for i in panel._scene.items()
            if isinstance(i, QGraphicsTextItem)
        ]
        assert any(tr("tree_empty", "es") in t for t in texts)
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
        assert tr("tree_prop_empty") in w._hud_placeholder.text()

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
            "min_child_weight": None,
            "governance_mode": "BANKING",
            "apply_jeffreys": True, "pd_floor": 0.0005,
        }
        w._on_wizard_finished(cfg)
        model = w._session.state.tree
        assert model is not None
        # The tree canvas is tab 0 of the main tab widget (sheets filling
        # the whole central area; tab bar anchored South, Phase 3.11.a.1
        # correction)
        assert w._main_tabs.count() == 5
        assert w._main_tabs.widget(0) is w._tree_panel
        items = [i for i in w._tree_panel._scene.items()
                 if isinstance(i, NodeItem)]
        assert len(items) == len(model.nodes)
        hdr = w._tree_panel._lbl_header.text()
        assert model.method in hdr and model.params_fingerprint in hdr
        # HUD: grupo Dataset poblado (sin seleccion)
        assert w._hud_lbl_file.text() == "mini_gui.csv"
        assert w._hud_lbl_rows.text() == "120"
        # seleccion de nodo -> tarjeta de detalle en el panel de propiedades
        w._tree_panel.select_node(1)
        assert model.nodes[1].split is None  # hoja identificable en detalle
        assert w._hud_lbl_rule_var.text() == tr("tree_node_terminal")
        w._tree_panel.select_node(0)
        assert w._hud_lbl_rule_var.text() == model.nodes[0].split.predictor
        # entrenamiento fallido -> rollback: el visor no conserva arbol
        bad = dict(cfg, engine="MOTOR_INEXISTENTE")
        w._on_wizard_finished(bad)
        assert w._session.state.state.name == "DATA_LOADED"
        assert w._session.state.tree is None
        assert [i for i in w._tree_panel._scene.items()
                if isinstance(i, NodeItem)] == []
        assert tr("tree_prop_empty") in w._hud_placeholder.text()
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
