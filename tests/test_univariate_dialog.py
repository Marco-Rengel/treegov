"""Tests de frontend_v3/univariate_dialog.py (Fase 3.11.c.2).

Headless: QT_QPA_PLATFORM defaults to offscreen here (setdefault, so a
developer console can still override it). Dual: pytest o python directo.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from frontend_v3.app import create_app  # noqa: E402
from frontend_v3.i18n import set_language  # noqa: E402
from frontend_v3.univariate_dialog import UnivariateDialog  # noqa: E402


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = create_app([])
    return app


def test_univariate_dialog_constructs():
    """El dialogo se instancia y expone botones de copiar/exportar/cerrar."""
    _app()
    set_language("en")
    dlg = UnivariateDialog()
    assert dlg._btn_copy is not None
    assert dlg._btn_export is not None
    assert dlg._btn_close is not None
    assert dlg._table.columnCount() == 4
    dlg.close()


def test_univariate_dialog_populates():
    """set_data puebla la tabla: 1 fila, 4 columnas, cortes formateados."""
    _app()
    set_language("en")
    dlg = UnivariateDialog()
    dto = [
        {"predictor": "edad", "gini": 0.8, "ks": 0.6,
         "cut_points": [("edad", 40.0)]},
    ]
    dlg.set_data(dto)
    assert dlg._table.rowCount() == 1
    assert dlg._table.columnCount() == 4
    assert dlg._table.item(0, 0).text() == "edad"
    assert "edad: 40" in dlg._table.item(0, 3).text()
    dlg.close()


if __name__ == "__main__":
    tests = [
        obj for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\nOK - {len(tests)} tests superados")
