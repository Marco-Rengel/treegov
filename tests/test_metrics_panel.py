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
from frontend_v3.metrics_panel import (  # noqa: E402
    _STATUS_TO_I18N,
    _STATUS_TO_QSS,
    MetricsPanel,
)


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


def _all_labels(widget):
    """Devuelve todos los QLabel hijos, en orden."""
    from PySide6.QtWidgets import QLabel
    return widget.findChildren(QLabel)


def _label_texts(widget):
    """Lista de textos de los QLabel hijos, en orden."""
    return [lbl.text() for lbl in _all_labels(widget)]


def _badges(widget):
    """QWidget-QLabel que tienen la propiedad 'status' no vacia."""
    return [lbl for lbl in _all_labels(widget)
            if lbl.property("status")]


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
    set_language("en")
    panel.retranslate_ui()
    from frontend_v3.i18n import _STRINGS
    texts = _label_texts(panel)
    assert _STRINGS["en"]["oos_oot_no_model"] in texts
    set_language("es")
    panel.retranslate_ui()
    texts = _label_texts(panel)
    assert _STRINGS["es"]["oos_oot_no_model"] in texts
    panel.close()
    panel.deleteLater()


def test_mainwindow_main_tabs():
    _get_app()
    w = MainWindow()
    tabs = w._main_tabs
    assert tabs is not None
    assert tabs.count() == 5, f"expected 5 tabs, got {tabs.count()}"
    # Tab indices: 0=Tree, 1=Gains, 2=Risks, 3=Rules, 4=Summary
    # (Excel-style sheets filling the central area)
    assert tabs.tabText(0) == tr("tab_tree")
    assert tabs.tabText(1) == tr("tab_gains")
    assert tabs.tabText(2) == tr("tab_risks")
    assert tabs.tabText(3) == tr("tab_rules")
    assert tabs.tabText(4) == tr("tab_summary")
    # Tab 0 hosts the real tree canvas (no placeholder)
    assert tabs.widget(0) is w._tree_panel
    assert tabs.widget(1) is w._reports_panel
    assert tabs.widget(2) is w._metrics_panel
    w.close()
    w.deleteLater()


def test_set_report_none_shows_empty():
    _get_app()
    from frontend_v3.i18n import _STRINGS
    set_language("en")
    panel = MetricsPanel()
    panel.set_report(None)
    texts = _label_texts(panel)
    assert _STRINGS["en"]["oos_oot_no_model"] in texts
    assert len(_badges(panel)) == 0
    panel.close()
    panel.deleteLater()


def test_set_report_empty_dto_shows_empty():
    _get_app()
    from frontend_v3.i18n import _STRINGS
    set_language("en")
    panel = MetricsPanel()
    panel.set_report({"oos": None, "oot": None})
    texts = _label_texts(panel)
    assert _STRINGS["en"]["oos_oot_no_model"] in texts
    panel.close()
    panel.deleteLater()


def test_set_report_with_oos_only():
    _get_app()
    from frontend_v3.i18n import _STRINGS
    set_language("en")
    panel = MetricsPanel()
    dto = {"oos": {"n_test": 300, "gini": 0.5, "ks": 0.4,
                   "brier": 0.1, "brier_skill": -0.11, "hl_p": 0.76},
           "oot": None}
    panel.set_report(dto)
    texts = _label_texts(panel)
    assert _STRINGS["en"]["oos_section_title"] in texts
    assert "0.5" in " ".join(texts)
    assert len(_badges(panel)) == 0
    panel.close()
    panel.deleteLater()


def test_set_report_with_oot_only():
    _get_app()
    from frontend_v3.i18n import _STRINGS
    set_language("en")
    panel = MetricsPanel()
    dto = {"oos": None,
           "oot": {"psi": {"flag": "UNSTABLE"},
                   "drop": {"alert_oot": "CRITICAL"},
                   "csi": ({"predictor": "x1", "csi": 0.05,
                            "flag": "MODERATE"},)}}
    panel.set_report(dto)
    texts = _label_texts(panel)
    assert _STRINGS["en"]["oot_section_title"] in texts
    badges = _badges(panel)
    assert len(badges) == 3
    statuses = sorted(b.property("status") for b in badges)
    assert statuses == ["crit", "crit", "warn"]
    panel.close()
    panel.deleteLater()


def test_status_mapping_fallthrough():
    _get_app()
    panel = MetricsPanel()
    badge = panel._make_badge("UNKNOWN_CODE_XYZ")
    assert badge.property("status") == "unknown"
    from frontend_v3.i18n import _STRINGS
    set_language("en")
    assert badge.text() == _STRINGS["en"]["status_undetermined"]
    panel.close()
    panel.deleteLater()


def test_status_constants_cover_full_alphabet():
    """Verifica que ambos mapas cubren los 7 codigos del alfabeto."""
    expected = {"STABLE", "NONE", "MODERATE", "WARNING",
                "UNSTABLE", "CRITICAL", "UNDETERMINED"}
    assert set(_STATUS_TO_QSS.keys()) == expected
    assert set(_STATUS_TO_I18N.keys()) == expected


# ---------------------------------------------------------------------------
# Fase 3.1.f: badge de Gini negativo + boton de reversion de clase
# ---------------------------------------------------------------------------


def _dto_gini(gini):
    """DTO minimo con la seccion OOS y el gini indicado (oot=None)."""
    return {"oos": {"n_test": 300, "gini": gini, "ks": None,
                    "brier": None, "brier_skill": None, "hl_p": None},
            "oot": None}


def test_inversion_badge_and_button_visible_when_gini_negative():
    """Con gini < 0 aparecen el badge crit y el boton de reversion."""
    _get_app()
    from frontend_v3.i18n import _STRINGS
    set_language("en")
    panel = MetricsPanel()
    panel.set_report(_dto_gini(-0.15))
    assert panel._invert_button is not None
    assert panel._invert_button.objectName() == "metricsInvertButton"
    assert panel._invert_button.text() == _STRINGS["en"]["inversion_button_label"]
    crit = [b for b in _badges(panel) if b.property("status") == "crit"]
    assert len(crit) == 1
    assert crit[0].text() == _STRINGS["en"]["inversion_badge_title"]
    panel.close()
    panel.deleteLater()


def test_inversion_badge_absent_when_gini_non_negative():
    """Sin gini negativo estricto no hay ni boton ni badge crit."""
    _get_app()
    set_language("en")
    panel = MetricsPanel()
    # Caso A: gini positivo
    panel.set_report(_dto_gini(0.4))
    assert panel._invert_button is None
    assert [b for b in _badges(panel) if b.property("status") == "crit"] == []
    # Caso B: frontera 0.0 (no negativo estricto)
    panel.set_report(_dto_gini(0.0))
    assert panel._invert_button is None
    assert [b for b in _badges(panel) if b.property("status") == "crit"] == []
    # Caso C: gini None
    panel.set_report(_dto_gini(None))
    assert panel._invert_button is None
    assert [b for b in _badges(panel) if b.property("status") == "crit"] == []
    panel.close()
    panel.deleteLater()


def test_inversion_button_emits_signal_on_click():
    """El click del boton emite inversion_requested exactamente una vez."""
    _get_app()
    set_language("en")
    panel = MetricsPanel()
    captured: list = []
    panel.inversion_requested.connect(lambda: captured.append(1))
    panel.set_report(_dto_gini(-0.15))
    assert panel._invert_button is not None
    panel._invert_button.click()
    assert len(captured) == 1
    panel.close()
    panel.deleteLater()


def test_clear_content_removes_children_immediately():
    """Patron setParent(None)+deleteLater: tras set_report(None), y SIN
    processEvents(), findChildren ya no encuentra el badge crit."""
    _get_app()
    set_language("en")
    panel = MetricsPanel()
    panel.set_report(_dto_gini(-0.15))
    assert len(_badges(panel)) >= 1  # panel poblado (badge crit presente)
    panel.set_report(None)
    # Sin event loop: la limpieza debe ser inmediata, no diferida
    assert [b for b in _badges(panel) if b.property("status") == "crit"] == []
    panel.close()
    panel.deleteLater()


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
