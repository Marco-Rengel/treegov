"""Tests for DataViewer (Phase 3.11.b.2 GUI). Dual: pytest or plain python.

    .venv\\Scripts\\python -m pytest tests/test_data_viewer.py -v
    .venv\\Scripts\\python tests/test_data_viewer.py

Headless: QT_QPA_PLATFORM defaults to offscreen here (setdefault, so a
real display session keeps its platform).

El DTO es el contrato D3 de `Session.get_data_preview()` (tipos nativos,
ausentes como None); aqui se simula — no hace falta backend ni CSV.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from frontend_v3.app import create_app  # noqa: E402
from frontend_v3.data_viewer import DataViewer  # noqa: E402
from frontend_v3.i18n import (  # noqa: E402
    get_language,
    language_bus,
    set_language,
    tr,
)
from frontend_v3.reports_panel import ReportsPanel  # noqa: E402


def _get_app() -> QApplication:
    """Reuse the running QApplication or create one (Qt is a singleton)."""
    app = QApplication.instance()
    if app is None:
        app = create_app([])
    return app


def _dto(truncated: bool = True) -> dict:
    """DTO D3 simulado: 3 columnas x 3 filas de 120 totales.

    Incluye un None (ausente del CSV) para anclar la celda vacia.
    """
    return {
        "columns": ["edad", "seg", "default"],
        "rows": [(20, "a", 0), (25, "b", 1), (30, "c", None)],
        "n_total": 120,
        "truncated": truncated,
    }


def test_data_viewer_build_empty_state_and_retranslate():
    """Construccion: estado vacio visible; retraduccion en caliente EN->ES."""
    _get_app()
    viewer = DataViewer()
    # estado vacio por defecto (sin set_preview): etiqueta visible, tabla 0x0
    assert not viewer._lbl_notice.isHidden()
    assert viewer._table.rowCount() == 0
    assert viewer._table.columnCount() == 0
    assert viewer._lbl_notice.text() == tr("data_viewer_empty")
    # retraduccion en caliente via language_bus
    prev = get_language()
    try:
        set_language("es")
        language_bus.language_changed.emit("es")
        assert viewer._lbl_notice.text() == tr("data_viewer_empty", "es")
        assert "dataset" in viewer._lbl_notice.text()
    finally:
        set_language(prev)
        language_bus.language_changed.emit(prev)  # restore the singleton
    viewer.close()
    viewer.deleteLater()


def test_data_viewer_set_preview_populates_and_truncation_notice():
    """Con datos: tabla poblada; aviso de truncamiento aparece/desaparece."""
    _get_app()
    viewer = DataViewer()
    viewer.set_preview(_dto(truncated=True))
    assert viewer._table.rowCount() == 3
    assert viewer._table.columnCount() == 3
    assert [
        viewer._table.horizontalHeaderItem(c).text() for c in range(3)
    ] == ["edad", "seg", "default"]
    # celdas como texto; el None del contrato se pinta como celda vacia
    assert viewer._table.item(0, 0).text() == "20"
    assert viewer._table.item(1, 1).text() == "b"
    assert viewer._table.item(2, 2).text() == ""
    # aviso de truncamiento con el formato del catalogo i18n
    assert not viewer._lbl_notice.isHidden()
    esperado = tr("data_viewer_truncated").format(shown=3, total=120)
    assert viewer._lbl_notice.text() == esperado
    # sin truncamiento: el aviso se oculta
    viewer.set_preview(_dto(truncated=False))
    assert viewer._lbl_notice.isHidden()
    assert viewer._table.rowCount() == 3
    viewer.close()
    viewer.deleteLater()


def test_data_viewer_copy_tsv_to_clipboard():
    """REGLA CRITICA 4.1.1 del Design System: Ctrl+C -> TSV."""
    _get_app()
    viewer = DataViewer()
    viewer.set_preview(_dto())
    # el shortcut Ctrl+C existe, vive sobre la tabla y con contexto
    # acotado (no secuestra el Ctrl+C de otros widgets)
    assert viewer._copy_shortcut.parent() is viewer._table
    # sin seleccion previa: copia toda la tabla con cabeceras
    viewer._table.clearSelection()
    ReportsPanel._copy_selection_to_clipboard(viewer._table)
    lines = QApplication.clipboard().text().split("\n")
    assert len(lines) == 4  # cabecera + 3 filas
    assert lines[0].split("\t") == ["edad", "seg", "default"]
    assert lines[1].split("\t") == ["20", "a", "0"]
    assert lines[2].split("\t") == ["25", "b", "1"]
    assert lines[3].split("\t") == ["30", "c", ""]  # None -> celda vacia
    viewer.close()
    viewer.deleteLater()


def test_data_viewer_set_preview_none_and_empty_dict_clear():
    """set_preview(None) y el dict vacio del backend limpian la tabla y
    muestran el estado vacio (divergencia consciente §18.7)."""
    _get_app()
    viewer = DataViewer()
    viewer.set_preview(_dto())
    assert viewer._table.rowCount() == 3
    # None: vuelta al estado vacio
    viewer.set_preview(None)
    assert viewer._table.rowCount() == 0
    assert viewer._table.columnCount() == 0
    assert viewer._lbl_notice.text() == tr("data_viewer_empty")
    assert not viewer._lbl_notice.isHidden()
    # dict vacio del backend (Session sin dataset): mismo estado vacio
    viewer.set_preview(_dto())
    viewer.set_preview(
        {"columns": [], "rows": [], "n_total": 0, "truncated": False}
    )
    assert viewer._table.rowCount() == 0
    assert viewer._table.columnCount() == 0
    assert viewer._lbl_notice.text() == tr("data_viewer_empty")
    assert not viewer._lbl_notice.isHidden()
    viewer.close()
    viewer.deleteLater()


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
    print(f"\nOK - {len(tests)} tests superados")
