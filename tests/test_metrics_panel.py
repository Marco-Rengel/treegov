"""Tests for MetricsPanel (Phase 2.3 skeleton). Dual: pytest or plain python.

    .venv\\Scripts\\python -m pytest tests/test_metrics_panel.py -v
    .venv\\Scripts\\python tests/test_metrics_panel.py

Headless: QT_QPA_PLATFORM defaults to offscreen here (setdefault, so a
real display session keeps its platform).
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from frontend_v3.app import create_app  # noqa: E402
from frontend_v3.i18n import set_language, tr  # noqa: E402
from frontend_v3.main_window import MainWindow  # noqa: E402
from frontend_v3.metrics_panel import MetricsPanel  # noqa: E402


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
# MetricsPanel tests
# ---------------------------------------------------------------------------


def test_metrics_panel_constructs():
    _get_app()
    panel = MetricsPanel()
    assert panel is not None
    panel.close()
    panel.deleteLater()


def test_metrics_panel_retranslate():
    _get_app()
    panel = MetricsPanel()
    # Test retranslate with English
    set_language("en")
    panel.retranslate_ui()
    from frontend_v3.i18n import _STRINGS
    assert panel._label.text() == _STRINGS["en"]["oos_oot_no_model"]

    # Test retranslate with Spanish
    set_language("es")
    panel.retranslate_ui()
    assert panel._label.text() == _STRINGS["es"]["oos_oot_no_model"]

    panel.close()
    panel.deleteLater()


def test_mainwindow_has_three_tabs():
    _get_app()
    w = MainWindow()
    tabs = w._tabs
    assert tabs is not None
    assert tabs.count() == 3, f"expected 3 tabs, got {tabs.count()}"
    # Tab indices: 0=Welcome, 1=Model tree, 2=OOS/OOT
    assert tabs.tabText(0) == tr("tab_welcome_title")
    assert tabs.tabText(1) == tr("tab_tree_title")
    assert tabs.tabText(2) == tr("tab_oos_oot_title")
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