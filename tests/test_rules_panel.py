"""Tests for RulesPanel (Phase 3.12.d GUI). Dual: pytest or plain python.

    .venv\\Scripts\\python -m pytest tests/test_rules_panel.py -v
    .venv\\Scripts\\python tests/test_rules_panel.py

Headless: QT_QPA_PLATFORM defaults to offscreen here (setdefault, so a
real display session keeps its platform).

The backend contract `Session.get_rules(format, node_id, unseen_policy)`
is simulated with a fake session: these tests cover presentation only
(empty state, format switch, node filter, copy, export, retranslation and
the MainWindow wiring).
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from frontend_v3.app import create_app  # noqa: E402
from frontend_v3.i18n import (  # noqa: E402
    _STRINGS,
    get_language,
    language_bus,
    set_language,
    tr,
)
from frontend_v3.main_window import MainWindow  # noqa: E402
from frontend_v3.rules_panel import RulesPanel  # noqa: E402

_RULES_KEYS = (
    "rules_title",
    "rules_format_label",
    "rules_format_markdown",
    "rules_format_sql",
    "rules_format_python",
    "rules_node_filter",
    "rules_node_all",
    "rules_empty",
    "rules_btn_refresh",
    "rules_btn_copy",
    "rules_btn_export",
    "rules_export_title",
    "rules_export_saved",
    "rules_export_error",
)


def _get_app() -> QApplication:
    """Reuse the running QApplication or create one (Qt is a singleton)."""
    app = QApplication.instance()
    if app is None:
        app = create_app([])
    return app


class _FakeSession:
    """Minimal stand-in for Session.get_rules (no backend, no CSV)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int | None, str]] = []
        self.texts = {
            "markdown": "# Rules\n\ntree 0 -> class 0\n",
            "sql": "SELECT 1;\n",
            "python": "def score(row):\n    return 0.5\n",
        }

    def get_rules(
        self,
        format: str = "markdown",
        node_id: int | None = None,
        unseen_policy: str = "exclude",
    ) -> str | None:
        self.calls.append((format, node_id, unseen_policy))
        return self.texts.get(format)


def test_rules_i18n_keys_present_in_both_languages():
    for key in _RULES_KEYS:
        assert key in _STRINGS["en"], key
        assert key in _STRINGS["es"], key
    assert _STRINGS["en"]["rules_empty"] != _STRINGS["es"]["rules_empty"]


def test_rules_panel_builds_empty_state():
    _get_app()
    prev = get_language()
    try:
        set_language("en")
        panel = RulesPanel()
        assert panel._title.text() == tr("rules_title")
        assert panel._format_combo.count() == 3
        assert [
            panel._format_combo.itemData(i) for i in range(3)
        ] == ["markdown", "sql", "python"]
        assert panel.current_format() == "markdown"
        assert panel._text.isReadOnly() is True
        assert (
            panel._text.font().styleHint() == QFont.StyleHint.Monospace
        )
        # Sin modelo: mensaje vacio visible, caja oculta, acciones off.
        assert panel._text.isHidden()
        assert not panel._empty_label.isHidden()
        assert panel._empty_label.text() == tr("rules_empty")
        assert panel._copy_button.isEnabled() is False
        assert panel._export_button.isEnabled() is False
        assert panel._refresh_button.text() == tr("rules_btn_refresh")
        assert panel._copy_button.text() == tr("rules_btn_copy")
        assert panel._export_button.text() == tr("rules_btn_export")
        panel.close()
        panel.deleteLater()
    finally:
        set_language(prev)


def test_rules_panel_refresh_format_and_node_filter():
    _get_app()
    prev = get_language()
    try:
        set_language("en")
        panel = RulesPanel()
        session = _FakeSession()

        panel.refresh(session, None)
        assert session.calls == [("markdown", None, "exclude")]
        assert panel._text.toPlainText() == session.texts["markdown"]
        assert not panel._text.isHidden()
        assert panel._empty_label.isHidden()
        assert panel._copy_button.isEnabled() is True
        assert panel._export_button.isEnabled() is True
        assert tr("rules_node_all") in panel._node_label.text()

        # Cambiar formato re-consulta el backend con el nodo cacheado.
        panel._format_combo.setCurrentIndex(1)
        assert session.calls[-1] == ("sql", None, "exclude")
        assert panel._text.toPlainText() == session.texts["sql"]

        # Filtro por nodo (el formato elegido se conserva).
        panel.refresh(session, 2)
        assert session.calls[-1] == ("sql", 2, "exclude")
        assert "#2" in panel._node_label.text()
        assert tr("rules_node_filter") in panel._node_label.text()

        # Deseleccionar vuelve al arbol completo.
        panel.refresh(session, None)
        assert session.calls[-1] == ("sql", None, "exclude")
        assert tr("rules_node_all") in panel._node_label.text()
        panel.close()
        panel.deleteLater()
    finally:
        set_language(prev)


def test_rules_panel_refresh_without_model_clears_text():
    _get_app()
    panel = RulesPanel()
    panel.refresh(None, None)
    assert panel._text.toPlainText() == ""
    assert panel._text.isHidden()
    assert not panel._empty_label.isHidden()
    assert panel._copy_button.isEnabled() is False
    assert panel._export_button.isEnabled() is False
    panel.close()
    panel.deleteLater()


def test_rules_panel_set_governance_mode_keeps_text():
    _get_app()
    panel = RulesPanel()
    session = _FakeSession()
    panel.refresh(session, None)
    before = panel._text.toPlainText()
    panel.set_governance_mode("RESEARCH")
    assert panel._mode == "RESEARCH"
    assert panel._text.toPlainText() == before
    panel.close()
    panel.deleteLater()


def test_rules_panel_copy_button_uses_clipboard():
    _get_app()
    panel = RulesPanel()
    session = _FakeSession()
    panel.refresh(session, None)
    panel._copy_button.click()
    assert QApplication.clipboard().text() == panel._text.toPlainText()
    panel.close()
    panel.deleteLater()


def test_rules_panel_export_cancel_does_not_write():
    _get_app()
    panel = RulesPanel()
    panel.refresh(_FakeSession(), None)
    with patch("frontend_v3.rules_panel.QFileDialog") as dlg:
        dlg.getSaveFileName.return_value = ("", "")
        panel._export_button.click()
        dlg.getSaveFileName.assert_called_once()
    panel.close()
    panel.deleteLater()


def test_rules_panel_export_writes_utf8_file():
    _get_app()
    panel = RulesPanel()
    session = _FakeSession()
    panel.refresh(session, None)
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "rules.md"
        with patch("frontend_v3.rules_panel.QFileDialog") as dlg, \
                patch("frontend_v3.rules_panel.QMessageBox") as box:
            dlg.getSaveFileName.return_value = (str(target), "")
            panel._export_button.click()
            assert target.read_text(encoding="utf-8") == session.texts[
                "markdown"
            ]
            box.information.assert_called_once()
    panel.close()
    panel.deleteLater()


def test_rules_panel_export_error_reports_and_returns_false():
    _get_app()
    panel = RulesPanel()
    panel.refresh(_FakeSession(), None)
    with tempfile.TemporaryDirectory() as td, \
            patch("frontend_v3.rules_panel.QMessageBox") as box:
        ok = panel._export_to_file(td)  # un directorio no es escribible
        assert ok is False
        box.warning.assert_called_once()
    panel.close()
    panel.deleteLater()


def test_rules_panel_retranslate_ui():
    _get_app()
    prev = get_language()
    panel = RulesPanel()
    try:
        set_language("es")
        panel.retranslate_ui()
        assert panel._title.text() == tr("rules_title", "es")
        assert panel._format_label.text() == tr("rules_format_label", "es")
        assert panel._refresh_button.text() == tr("rules_btn_refresh", "es")
        assert panel._copy_button.text() == tr("rules_btn_copy", "es")
        assert panel._export_button.text() == tr("rules_btn_export", "es")
        assert panel._empty_label.text() == tr("rules_empty", "es")
        assert tr("rules_node_filter", "es") in panel._node_label.text()
        assert tr("rules_node_all", "es") in panel._node_label.text()
    finally:
        set_language(prev)
        panel.close()
        panel.deleteLater()


def test_main_window_hosts_rules_panel_and_wires_selection():
    _get_app()
    w = MainWindow()
    try:
        assert isinstance(w._rules_panel, RulesPanel)
        assert w._main_tabs.widget(3) is w._rules_panel
        assert w._main_tabs.tabText(3) == tr("tab_rules")

        seen: list[int | None] = []

        def _record(session, node_id):
            seen.append(node_id)

        w._rules_panel.refresh = _record
        w._tree_panel.node_selected.emit(4)
        w._tree_panel.selection_cleared.emit()
        assert seen == [4, None]
    finally:
        w.close()
        w.deleteLater()


def test_main_window_retranslates_rules_on_language_bus():
    _get_app()
    prev = get_language()
    w = MainWindow()
    try:
        set_language("es")
        language_bus.language_changed.emit("es")
        assert w._rules_panel._title.text() == tr("rules_title", "es")
        assert (
            w._main_tabs.tabText(3) == tr("tab_rules", "es")
        )
    finally:
        set_language(prev)
        language_bus.language_changed.emit(prev)
        w.close()
        w.deleteLater()


if __name__ == "__main__":
    tests = [
        obj for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nOK - {len(tests)} tests superados")
