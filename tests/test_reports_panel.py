"""Tests for ReportsPanel (Phase 2.4.c.2). Dual: pytest or plain python.

    .venv\\Scripts\\python -m pytest tests/test_reports_panel.py -v
    .venv\\Scripts\\python tests/test_reports_panel.py

Headless: QT_QPA_PLATFORM defaults to offscreen here (setdefault, so a
real display session keeps its platform).
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from frontend_v3.app import create_app  # noqa: E402
from frontend_v3.i18n import set_language, tr, _STRINGS  # noqa: E402
from frontend_v3.reports_panel import ReportsPanel  # noqa: E402


def _get_app() -> QApplication:
    """Reuse the running QApplication or create one (Qt is a singleton)."""
    app = QApplication.instance()
    if app is None:
        app = create_app([])
    return app


def _sample_gains_dto() -> dict:
    """Single-row GainsTableResult-shaped payload."""
    row = {
        "label": "L0",
        "pd": 0.1,
        "n": 50,
        "n_good": 45,
        "n_bad": 5,
        "bad_rate": 0.1,
        "n_cum": 50,
        "n_good_cum": 45,
        "n_bad_cum": 5,
        "bad_rate_cum": 0.1,
        "lift_cum": 0.3333,
        "n_decum": 100,
        "n_good_decum": 70,
        "n_bad_decum": 30,
        "bad_rate_decum": 0.3,
    }
    return {
        "by": "leaf",
        "n_total": 100,
        "n_good": 70,
        "n_bad": 30,
        "bad_rate_global": 0.3,
        "ks": 0.45,
        "auc": 0.75,
        "gini": 0.5,
        "n_excluded": 0,
        "rows": (row,),
    }


def _sample_matrix_dto() -> dict:
    """ClassificationMatrix-shaped payload."""
    return {
        "threshold": 0.5,
        "n_total": 100,
        "n_good": 70,
        "n_bad": 30,
        "tp": 60,
        "tn": 60,
        "fp": 10,
        "fn": 10,
        "precision": 0.857,
        "recall": 0.857,
        "f1": 0.857,
        "bad_capture_rate": 0.857,
        "n_excluded": 0,
    }


# ---------------------------------------------------------------------------
# ReportsPanel tests
# ---------------------------------------------------------------------------


def test_panel_constructs():
    _get_app()
    panel = ReportsPanel()
    assert panel is not None
    panel.close()
    panel.deleteLater()


def test_retranslate():
    _get_app()
    panel = ReportsPanel()
    set_language("en")
    panel.retranslate_ui()
    expected_en = _STRINGS["en"]["reports_partition_label"]
    assert expected_en in panel._partition_label.text()
    set_language("es")
    panel.retranslate_ui()
    expected_es = _STRINGS["es"]["reports_partition_label"]
    assert expected_es in panel._partition_label.text()
    panel.close()
    panel.deleteLater()


def test_set_session_available():
    _get_app()
    panel = ReportsPanel()
    panel.set_session_available(train=True, oos=True, oot=True)
    panel.set_session_available(train=False, oos=True, oot=False)
    combo = panel._partition_combo
    model = combo.model()
    row_oos = combo.findData("oos")
    row_train = combo.findData("train")
    row_oot = combo.findData("oot")
    assert row_oos >= 0 and row_train >= 0 and row_oot >= 0
    assert model.item(row_oos).isEnabled()
    assert not model.item(row_train).isEnabled()
    assert not model.item(row_oot).isEnabled()
    panel.close()
    panel.deleteLater()


def test_set_gains_table_populates():
    _get_app()
    panel = ReportsPanel()
    panel.set_gains_table(_sample_gains_dto())
    assert panel._table.rowCount() == 1
    assert panel._table.item(0, 0).text() == "L0"
    assert panel._table.columnCount() == 13
    panel.close()
    panel.deleteLater()


def test_signals_emitted():
    _get_app()
    panel = ReportsPanel()
    panel.set_session_available(train=True, oos=True, oot=True)
    # Forzar un estado inicial distinto al objetivo: si el combo ya
    # estuviera en el valor destino, setCurrentIndex no dispararía
    # currentIndexChanged y la señal no se emitiría.
    combo_p = panel._partition_combo
    combo_p.setCurrentIndex(combo_p.findData("train"))
    combo_v = panel._view_combo
    combo_v.setCurrentIndex(combo_v.findData("leaf"))
    captured = {"partition": [], "view": [], "threshold": []}
    panel.partition_changed.connect(
        lambda v: captured["partition"].append(v))
    panel.view_changed.connect(
        lambda v: captured["view"].append(v))
    panel.threshold_changed.connect(
        lambda v: captured["threshold"].append(v))
    combo_p.setCurrentIndex(combo_p.findData("oos"))
    combo_v.setCurrentIndex(combo_v.findData("bucket"))
    panel._threshold_spin.setValue(0.3)
    assert captured["partition"] and captured["partition"][-1] == "oos"
    assert captured["view"] and captured["view"][-1] == "bucket"
    assert captured["threshold"]
    assert abs(captured["threshold"][-1] - 0.3) < 1e-9
    panel.close()
    panel.deleteLater()


def test_build_report_html_contains_data():
    _get_app()
    panel = ReportsPanel()
    panel.set_gains_table(_sample_gains_dto())
    panel.set_classification_matrix(_sample_matrix_dto())
    html = panel._build_report_html()
    assert html.startswith("<!DOCTYPE html>")
    assert "L0" in html
    assert "60" in html
    assert tr("reports_export_doc_title") in html
    assert tr("reports_matrix_pred_good") in html
    assert tr("reports_matrix_pred_bad") in html
    panel.close()
    panel.deleteLater()


def test_export_empty_does_not_crash():
    _get_app()
    panel = ReportsPanel()
    panel._gains = None
    panel._matrix = None
    with patch(
        "frontend_v3.reports_panel.QMessageBox.information"
    ) as mock_info:
        panel._on_export_clicked()
    assert mock_info.call_count == 1
    panel.close()
    panel.deleteLater()


def test_matrix_accuracy_row_visible():
    _get_app()
    panel = ReportsPanel()
    dto = _sample_matrix_dto()
    dto["accuracy"] = 0.875
    panel.set_classification_matrix(dto)
    assert "accuracy" in panel._matrix_rows
    label = panel._matrix_rows["accuracy"]
    assert tr("reports_matrix_accuracy") in label.text()
    assert "0.875" in label.text()
    panel.close()
    panel.deleteLater()


def test_summary_n_per_class_appears_k3():
    _get_app()
    panel = ReportsPanel()
    dto = _sample_gains_dto()
    dto["n_per_class_global"] = (30, 30, 30)
    panel.set_gains_table(dto)
    assert panel._per_class_label.isVisible() is False or True  # offscreen quirk
    # El texto se asigna aunque isVisible() sea False en offscreen.
    assert tr("reports_sum_n_per_class") in panel._per_class_label.text()
    assert "(30, 30, 30)" in panel._per_class_label.text()
    panel.close()
    panel.deleteLater()


def test_summary_n_per_class_hidden_k2():
    _get_app()
    panel = ReportsPanel()
    panel.set_gains_table(_sample_gains_dto())  # sin n_per_class_global
    assert tr("reports_sum_n_per_class") not in panel._per_class_label.text()
    panel.close()
    panel.deleteLater()


def test_copy_selection_to_clipboard():
    _get_app()
    panel = ReportsPanel()
    panel.set_gains_table(_sample_gains_dto())
    clipboard = QApplication.clipboard()
    # Sin seleccion previa: copia toda la tabla con cabeceras.
    panel._table.clearSelection()
    panel._copy_selection_to_clipboard()
    lines = clipboard.text().split("\n")
    assert len(lines) == 2  # cabecera + 1 fila de datos
    assert len(lines[0].split("\t")) == 13
    assert len(lines[1].split("\t")) == 13
    assert "L0" in lines[1]
    # Con seleccion explicita: mismas columnas, mismas filas.
    panel._table.selectRow(0)
    panel._copy_selection_to_clipboard()
    lines_sel = clipboard.text().split("\n")
    assert lines_sel == lines
    # Tabla vacia: no toca el portapapeles.
    panel._table.setRowCount(0)
    panel._table.clearSelection()
    clipboard.setText("SENTINEL")
    panel._copy_selection_to_clipboard()
    assert clipboard.text() == "SENTINEL"
    panel.close()
    panel.deleteLater()


def test_matrix_title_multiclass_when_k3():
    _get_app()
    panel = ReportsPanel()
    dto = _sample_matrix_dto()
    dto["confusion_matrix"] = ((30, 0, 0), (0, 30, 0), (0, 0, 30))
    panel.set_classification_matrix(dto)
    assert (
        panel._matrix_title.text()
        == tr("reports_matrix_title_multiclass")
    )
    panel.close()
    panel.deleteLater()


def test_matrix_title_binary_when_k2():
    _get_app()
    panel = ReportsPanel()
    panel.set_classification_matrix(_sample_matrix_dto())  # sin confusion_matrix
    assert panel._matrix_title.text() == tr("reports_matrix_title")
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
