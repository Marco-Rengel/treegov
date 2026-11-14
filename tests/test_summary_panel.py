"""Tests for SummaryPanel (Phase 3.12.e GUI). Dual: pytest or plain python.

    .venv\\Scripts\\python -m pytest tests/test_summary_panel.py -v
    .venv\\Scripts\\python tests/test_summary_panel.py

Headless: QT_QPA_PLATFORM defaults to offscreen here (setdefault, so a
real display session keeps its platform). El contrato `get_summary()` se
simula en las pruebas de presentacion; una prueba de integracion entrena
un modelo real para verificar el refresco desde MainWindow.
"""

import csv
import logging
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from backend_v3.session_state import Session  # noqa: E402
from backend_v3.types import PredictorType  # noqa: E402
from frontend_v3.app import create_app  # noqa: E402
from frontend_v3.i18n import (  # noqa: E402
    _STRINGS,
    get_language,
    language_bus,
    set_language,
    tr,
    tr_term,
)
from frontend_v3.main_window import MainWindow  # noqa: E402
from frontend_v3.summary_panel import SummaryPanel  # noqa: E402

_SUMMARY_KEYS = (
    "summary_title",
    "summary_section_model",
    "summary_section_dataset",
    "summary_section_partition",
    "summary_section_governance",
    "summary_section_validation",
    "summary_section_overrides",
    "summary_section_event_log",
    "summary_field_method",
    "summary_field_fingerprint",
    "summary_field_nodes",
    "summary_field_terminal",
    "summary_field_max_depth",
    "summary_field_classes",
    "summary_field_target",
    "summary_field_predictors",
    "summary_field_weights",
    "summary_field_population",
    "summary_field_cost_matrix",
    "summary_field_scheme",
    "summary_field_train_frac",
    "summary_field_seed",
    "summary_field_cv_k",
    "summary_field_n_train",
    "summary_field_n_test",
    "summary_field_n_oot",
    "summary_field_n_excluded_population",
    "summary_field_apply_jeffreys",
    "summary_field_pd_floor",
    "summary_field_min_child_size",
    "summary_field_min_child_weight",
    "summary_field_max_depth_param",
    "summary_yes",
    "summary_no",
    "summary_none",
    "summary_empty",
    "summary_btn_refresh",
    "summary_btn_copy",
    "summary_btn_export",
    "summary_export_title",
    "summary_export_saved",
    "summary_export_error",
)


def _get_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = create_app([])
    return app


def _quiet_logger() -> logging.Logger:
    logger = logging.getLogger("treegov.summary.tests")
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    logger.propagate = False
    return logger


def _dto() -> dict:
    return {
        "model": {
            "method": "CRT",
            "fingerprint": "abc123",
            "n_nodes": 3,
            "n_terminal": 2,
            "max_depth": 1,
            "class_labels": ["Malo", "Bueno"],
            "target_class": 1,
            "governance_mode": "BANKING",
        },
        "dataset": {
            "path": "C:/tmp/dev.csv",
            "n_rows": 120,
            "n_cols": 3,
            "target": "default",
            "predictors": ["edad", "seg"],
            "weights_col": None,
            "population_col": None,
            "population_ok_values": [],
            "cost_matrix": [],
        },
        "partition": {
            "scheme": "holdout",
            "train_frac": 0.7,
            "seed": 42,
            "cv_k": None,
            "n_train": 84,
            "n_test": 36,
            "n_oot": None,
            "n_excluded_population": 0,
        },
        "governance": {
            "apply_jeffreys": True,
            "pd_floor": 0.0005,
            "min_child_size": 5,
            "min_child_weight": None,
            "max_depth_param": 4,
        },
        "validation": {
            "oos_metrics": {
                "n_test": 36,
                "n_events": 18,
                "auc": 0.8,
                "gini": 0.6,
                "ks": 0.4,
            },
            "oot_report": {"psi": {"flag": "STABLE", "value": 0.01}},
            "cv_report": None,
        },
        "manual_overrides": [
            ("2026-11-14T10:00:00", 1, "prune_branch", "", "aa", "bb")
        ],
        "event_log": ["init/state=EMPTY", "train:CRT"],
    }


_UNSET = object()


class _FakeSession:
    def __init__(self, summary: dict | None | object = _UNSET) -> None:
        self.summary = _dto() if summary is _UNSET else summary
        self.calls = 0

    def get_summary(self) -> dict | None:
        self.calls += 1
        return self.summary


def test_summary_i18n_keys_present_in_both_languages():
    assert len(_SUMMARY_KEYS) == 42
    for key in _SUMMARY_KEYS:
        assert key in _STRINGS["en"], key
        assert key in _STRINGS["es"], key


def test_summary_panel_builds_empty_state():
    _get_app()
    prev = get_language()
    try:
        set_language("en")
        panel = SummaryPanel()
        assert panel._title.text() == tr("summary_title")
        assert panel._browser.isReadOnly() is True
        assert panel._browser.isHidden()
        assert not panel._empty_label.isHidden()
        assert panel._empty_label.text() == tr("summary_empty")
        assert panel._copy_button.isEnabled() is False
        assert panel._export_button.isEnabled() is False
        assert panel._refresh_button.text() == tr("summary_btn_refresh")
        assert panel._copy_button.text() == tr("summary_btn_copy")
        assert panel._export_button.text() == tr("summary_btn_export")
        panel.close()
        panel.deleteLater()
    finally:
        set_language(prev)


def test_summary_panel_html_contains_all_sections_and_data():
    _get_app()
    prev = get_language()
    try:
        set_language("en")
        panel = SummaryPanel()
        session = _FakeSession()
        panel.refresh(session)
        assert session.calls == 1
        assert not panel._browser.isHidden()
        assert panel._empty_label.isHidden()
        html_text = panel._html
        for section in (
            "summary_section_model",
            "summary_section_dataset",
            "summary_section_partition",
            "summary_section_governance",
            "summary_section_validation",
            "summary_section_overrides",
            "summary_section_event_log",
        ):
            assert tr(section) in html_text
        for value in (
            "CRT", "abc123", "dev.csv", "84", "0.8", "STABLE",
            "prune_branch", "train:CRT",
        ):
            assert value in html_text
        assert "<ul>" in html_text and "<li>" in html_text
        panel.close()
        panel.deleteLater()
    finally:
        set_language(prev)


def test_summary_panel_mode_changes_pd_label():
    _get_app()
    prev = get_language()
    try:
        set_language("en")
        panel = SummaryPanel()
        panel.refresh(_FakeSession())
        assert tr("summary_field_pd_floor") in panel._html
        panel.set_governance_mode("RESEARCH")
        assert "Probability floor:" in panel._html
        assert tr("summary_field_pd_floor") not in panel._html

        set_language("es")
        panel.retranslate_ui()
        expected = f"Piso de {tr_term('pd', 'RESEARCH')}:"
        assert expected in panel._html
        assert "Probabilidad" in panel._html
        panel.close()
        panel.deleteLater()
    finally:
        set_language(prev)


def test_summary_panel_refresh_without_model_clears_html():
    _get_app()
    panel = SummaryPanel()
    panel.refresh(_FakeSession())
    assert panel._html
    panel.refresh(_FakeSession(summary=None))
    assert panel._html == ""
    assert panel._browser.toPlainText() == ""
    assert panel._browser.isHidden()
    assert not panel._empty_label.isHidden()
    panel.close()
    panel.deleteLater()


def test_summary_panel_copy_uses_plain_text():
    _get_app()
    panel = SummaryPanel()
    panel.refresh(_FakeSession())
    panel._copy_button.click()
    copied = QApplication.clipboard().text()
    assert copied == panel._browser.toPlainText()
    assert "CRT" in copied and "abc123" in copied
    assert "<h3>" not in copied
    panel.close()
    panel.deleteLater()


def test_summary_panel_export_html_and_text():
    _get_app()
    panel = SummaryPanel()
    panel.refresh(_FakeSession())
    with tempfile.TemporaryDirectory() as td, \
            patch("frontend_v3.summary_panel.QMessageBox") as box:
        html_path = Path(td) / "summary.html"
        text_path = Path(td) / "summary.txt"
        assert panel._export_to_file(str(html_path)) is True
        assert panel._export_to_file(str(text_path)) is True
        assert html_path.read_text(encoding="utf-8") == panel._html
        assert text_path.read_text(encoding="utf-8") == (
            panel._browser.toPlainText()
        )
        assert box.information.call_count == 2
    panel.close()
    panel.deleteLater()


def test_summary_panel_export_button_cancel_does_not_write():
    _get_app()
    panel = SummaryPanel()
    panel.refresh(_FakeSession())
    with patch("frontend_v3.summary_panel.QFileDialog") as dialog:
        dialog.getSaveFileName.return_value = ("", "")
        panel._export_button.click()
        dialog.getSaveFileName.assert_called_once()
    panel.close()
    panel.deleteLater()


def test_summary_panel_retranslate_ui_uses_cached_dto():
    _get_app()
    prev = get_language()
    try:
        set_language("en")
        session = _FakeSession()
        panel = SummaryPanel()
        panel.refresh(session)
        calls = session.calls
        set_language("es")
        panel.retranslate_ui()
        assert session.calls == calls
        assert panel._title.text() == tr("summary_title", "es")
        assert tr("summary_section_model", "es") in panel._html
        assert tr("summary_section_event_log", "es") in panel._html
        panel.close()
        panel.deleteLater()
    finally:
        set_language(prev)


def test_main_window_hosts_summary_panel_and_language_bus():
    _get_app()
    prev = get_language()
    window = MainWindow()
    try:
        assert isinstance(window._summary_panel, SummaryPanel)
        assert window._main_tabs.widget(4) is window._summary_panel
        set_language("es")
        language_bus.language_changed.emit("es")
        assert window._summary_panel._title.text() == tr("summary_title", "es")
        assert window._main_tabs.tabText(4) == tr("tab_summary", "es")
    finally:
        set_language(prev)
        language_bus.language_changed.emit(prev)
        window.close()
        window.deleteLater()


def test_main_window_populates_summary_after_training():
    _get_app()
    prev = get_language()
    with tempfile.TemporaryDirectory() as td:
        csv_path = Path(td) / "research.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["age", "target"])
            writer.writerows(
                (20 + index * 5, int(index >= 6)) for index in range(12)
            )
        session = Session()
        session.load_dataset(str(csv_path))
        window = MainWindow(session=session, logger=_quiet_logger())
        try:
            set_language("en")
            window._on_wizard_finished({
                "target": "target",
                "predictors": {"age": PredictorType.CONTINUOUS},
                "target_class": 1,
                "class_labels": {0: "Non-event", 1: "Event"},
                "weight_col": None,
                "population_col": None,
                "population_ok_values": (),
                "train_frac": 0.75,
                "seed": 42,
                "engine": "CRT",
                "max_depth": 2,
                "min_child_size": 1,
                "min_child_weight": None,
                "governance_mode": "RESEARCH",
                "apply_jeffreys": False,
                "pd_floor": None,
            })
            assert session.state.tree is not None
            assert window._summary_panel._summary is not None
            assert "CRT" in window._summary_panel._html
            assert "research.csv" in window._summary_panel._html
            assert window._summary_panel._mode == "RESEARCH"
            assert "Probability floor:" in window._summary_panel._html
        finally:
            set_language(prev)
            window.close()
            window.deleteLater()


if __name__ == "__main__":
    tests = [
        obj for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nOK - {len(tests)} tests superados")
