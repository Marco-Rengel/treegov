"""Smoke tests for frontend_v3 (Phase 2.0). Dual: pytest or plain python.

    .venv\\Scripts\\python -m pytest tests/test_gui_smoke.py -v
    .venv\\Scripts\\python tests\\test_gui_smoke.py

Headless: QT_QPA_PLATFORM defaults to offscreen here (setdefault, so a
real display session keeps its platform). 10 tests: 7 smoke + 3 i18n.
"""

import ast
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtGui import QAction  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QFrame,
    QLabel,
    QMenu,
    QSplitter,
    QTabWidget,
)

from frontend_v3.app import create_app  # noqa: E402
from frontend_v3.i18n import (  # noqa: E402
    SUPPORTED,
    _STRINGS,
    detect_system_language,
    get_language,
    set_language,
    tr,
)
from frontend_v3.main_window import MainWindow  # noqa: E402
from frontend_v3.theme import (  # noqa: E402
    apply_palette,
    apply_theme,
    available_themes,
)

_BANNED = {"numpy", "pandas", "scipy"}
_TOKEN_RE = re.compile(r"\$[A-Z_]+")
_FRONTEND_ROOT = Path(__file__).resolve().parents[1] / "frontend_v3"


def _get_app() -> QApplication:
    """Reuse the running QApplication or create one (Qt is a singleton)."""
    app = QApplication.instance()
    if app is None:
        app = create_app([])
    return app


def _assert_raises(exc_type, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc_type:
        return
    except Exception as e:  # pragma: no cover
        raise AssertionError(
            f"{fn.__name__} raised {type(e).__name__} "
            f"instead of {exc_type.__name__}: {e}"
        ) from e
    raise AssertionError(f"{fn.__name__} did not raise {exc_type.__name__}")


# ---------------------------------------------------------------------------
# Smoke tests (7)
# ---------------------------------------------------------------------------


def test_main_window_constructs():
    _get_app()
    w = MainWindow()
    assert w.windowTitle(), "window title must not be empty"
    w.close()
    w.deleteLater()


def test_layout_structure():
    _get_app()
    w = MainWindow()
    splitter = w.findChild(QSplitter, "centralSplitter")
    assert splitter is not None
    assert splitter.count() == 3
    # Phase 3.11.a.1 (classic layout): the left panel is a vertical
    # splitter with three stacked group boxes (Explorer / Tree Map /
    # Data Viewer).
    left = splitter.widget(0)
    assert left is w.findChild(QSplitter, "leftPanel")
    assert left.count() == 3
    assert splitter.widget(2) is w.findChild(QFrame, "hudPanel")
    tabs = w.findChild(QTabWidget, "centralTabs")
    # 5 main tabs filling the WHOLE central area, with the tab bar
    # anchored at the bottom (Excel-sheet style, TabPosition.South):
    # Tree (0) + Gains (1) + Risks (2) + Rules (3) + Summary (4)
    assert tabs is not None and tabs.count() == 5
    assert tabs.tabPosition() == QTabWidget.TabPosition.South
    # the tab widget IS the central splitter pane (no vertical splitter)
    assert splitter.widget(1) is tabs
    assert tabs.widget(0) is w._tree_panel
    w.close()
    w.deleteLater()


def test_hud_panel_bounded_and_toggleable():
    """Properties panel: width capped (never oversized) and the View menu
    action really hides/shows it via setVisible()."""
    _get_app()
    w = MainWindow()
    assert w._hud_panel.minimumWidth() == 200
    assert w._hud_panel.maximumWidth() == 400
    act = w.findChild(QAction, "act_toggle_hud")
    assert act is not None and act.isCheckable()
    w.show()
    assert w._hud_panel.isVisible()
    act.setChecked(False)
    assert not w._hud_panel.isVisible()
    act.setChecked(True)
    assert w._hud_panel.isVisible()
    w.close()
    w.deleteLater()


def test_menus_exist():
    _get_app()
    w = MainWindow()
    menu_names = {m.objectName() for m in w.findChildren(QMenu)}
    # Phase 3.11.a.1: classic menu structure (Estándar Clásico de
    # Estaciones de Árboles, circa 2001):
    # File, Edit, View, Format, Analysis, Tree, Window, Help.
    assert {
        "menu_file",
        "menu_edit",
        "menu_view",
        "menu_format",
        "menu_analysis",
        "menu_tree",
        "menu_window",
        "menu_help",
        "menu_theme",
        "menu_language",
    } <= menu_names

    # (objectName, expected enabled) - wizard gated hasta DATA_LOADED (2.1);
    # evaluate_oos / load_oot siguen como placeholder hasta Phase 2.3
    expected = [
        ("act_new_wizard", False),
        ("act_open", True),
        ("act_exit", True),
        ("act_train", False),
        ("act_evaluate_oos", False),
        ("act_load_oot", False),
        ("act_about", True),
        ("act_theme_light", True),
        ("act_theme_dark", True),
        ("act_lang_en", True),
        ("act_lang_es", True),
        ("act_toggle_left", True),
        ("act_toggle_hud", True),
    ]
    for name, enabled in expected:
        act = w.findChild(QAction, name)
        assert act is not None, f"missing action {name}"
        assert act.isEnabled() is enabled, f"wrong enabled state: {name}"
    w.close()
    w.deleteLater()


def test_statusbar_indicators():
    _get_app()
    w = MainWindow()
    lbl_session = w.findChild(QLabel, "statusSessionLabel")
    lbl_theme = w.findChild(QLabel, "statusThemeLabel")
    assert lbl_session is not None and ":" in lbl_session.text()
    assert lbl_theme is not None and ":" in lbl_theme.text()
    w.close()
    w.deleteLater()


def test_theme_switch_both():
    app = _get_app()
    assert set(available_themes()) == {"light", "dark"}
    for name in available_themes():
        apply_theme(name, app)
        qss = app.styleSheet()
        assert qss, "stylesheet must not be empty"
        assert not _TOKEN_RE.findall(qss), f"unresolved $TOKEN in {name} theme"
    _assert_raises(ValueError, apply_theme, "neon", app)
    apply_theme("light", app)  # restore default


def test_apply_palette_roles():
    """Phase 3.11.a.1: apply_palette pins the TreeGov QPalette so native-
    rendered chrome (QWizard/QDialog) follows the app theme, not the
    Windows light/dark mode. Fail-fast on unknown theme (like apply_theme).
    """
    from PySide6.QtGui import QColor, QPalette

    from frontend_v3.theme import PALETTES

    app = _get_app()
    R = QPalette.ColorRole
    for name in available_themes():
        apply_palette(name, app)
        pal = app.palette()
        expected = PALETTES[name]
        assert pal.color(R.Window) == QColor(expected["BG"])
        assert pal.color(R.WindowText) == QColor(expected["FG"])
        assert pal.color(R.Base) == QColor(expected["SURFACE_ELEVATED"])
        assert pal.color(R.AlternateBase) == QColor(expected["SURFACE"])
        assert pal.color(R.Text) == QColor(expected["FG"])
        assert pal.color(R.Button) == QColor(expected["SURFACE"])
        assert pal.color(R.ButtonText) == QColor(expected["FG"])
    _assert_raises(ValueError, apply_palette, "neon", app)
    apply_palette("light", app)  # restore default


def test_frontend_clean_room():
    """AST guardrail: no numpy/pandas/scipy imports inside frontend_v3/.

    AST (not text search) avoids false positives from strings/comments.
    """
    offenders: list[str] = []
    for path in sorted(_FRONTEND_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots = [node.module.split(".")[0]]
            else:
                continue  # covers "from . import x" (module=None)
            bad = _BANNED.intersection(roots)
            if bad:
                offenders.append(f"{path.name}: {sorted(bad)}")
    assert not offenders, f"forbidden imports in frontend_v3: {offenders}"


# ---------------------------------------------------------------------------
# i18n tests (3)
# ---------------------------------------------------------------------------


def test_i18n_dict_keys_match():
    """No orphan keys: every locale holds exactly the same key set."""
    key_sets = [set(_STRINGS[lang]) for lang in SUPPORTED]
    assert key_sets[0], "dictionary must not be empty"
    assert all(s == key_sets[0] for s in key_sets)


def test_i18n_tr_and_language():
    assert tr("menu_file", "en") == "File"
    assert tr("menu_file", "es") == "Archivo"
    prev = get_language()
    try:
        set_language("es")
        assert get_language() == "es"
        assert tr("menu_file") == "Archivo"
    finally:
        set_language(prev)  # restore the global singleton

    # about_body carries {version}; .format must work in every locale
    for lang in ("en", "es"):
        body = tr("about_body", lang).format(version="1.0.0a0")
        assert "1.0.0a0" in body

    _assert_raises(ValueError, set_language, "fr")
    _assert_raises(ValueError, tr, "menu_file", "fr")
    _assert_raises(KeyError, tr, "no_such_key", "en")


def test_detect_system_language_returns_valid():
    assert detect_system_language() in SUPPORTED


def test_project_explorer_updates():
    # TODO(zona_gris): el prompt original pasaba cfg={"governance_mode": ...}
    # y sesión/arbol MagicMock sin más scaffolding, pero (1) _train_pipeline
    # exige las 15 claves del cfg (KeyError -> rollback -> label nunca se
    # actualiza) y (2) _on_new_wizard solo ejecuta la rama de reseteo si
    # _dataset_info no es None. Se completan el cfg y el stub de dataset, y
    # se mockean los paneles para aislar el cableado del QLabel (el render
    # real de un MagicMock-tree en set_model no es determinista). El asistente
    # estratégico decidirá si se prefiere un e2e con CSV real.
    from unittest.mock import MagicMock, patch

    from backend_v3.session_state import FlowState
    _get_app()
    w = MainWindow()
    assert w._lbl_explorer_model.text() == "—"

    mock_tree = MagicMock()
    mock_tree.method = "CRT"
    mock_tree.params_fingerprint = "1234567890abcdef"

    mock_state = MagicMock()
    mock_state.state = FlowState.TRAINED
    mock_state.tree = mock_tree

    w._session = MagicMock()
    w._session.state = mock_state
    w._dataset_info = (["x"], {"x": "numeric"})
    w._tree_panel = MagicMock()
    w._tree_panel.selected_node_id.return_value = None
    w._tree_map = MagicMock()
    w._metrics_panel = MagicMock()
    w._reports_panel = MagicMock()

    cfg = {
        "governance_mode": "BANKING",
        "target": "y", "predictors": ["x"], "target_class": 1,
        "class_labels": {0: "No", 1: "Yes"},
        "weight_col": None, "population_col": None,
        "population_ok_values": (),
        "train_frac": 0.7, "seed": 42, "engine": "CRT",
        "max_depth": 3, "min_child_size": 5,
        "min_child_weight": None, "pd_floor": 0.0005,
        "apply_jeffreys": True,
    }
    w._on_wizard_finished(cfg)
    assert w._lbl_explorer_model.text() == "CRT · 12345678"

    with patch("frontend_v3.main_window.ModelWizard"):
        w._on_new_wizard()
    assert w._lbl_explorer_model.text() == "—"

    w.close()
    w.deleteLater()


# ---------------------------------------------------------------------------
# Direct execution without pytest
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
    print(f"\nOK - {len(tests)} tests passed")
