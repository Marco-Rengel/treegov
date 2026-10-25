"""DataViewer — bloque Data Viewer del panel izquierdo (Fase 3.11.b.2).

Widget de solo lectura que muestra el preview crudo del CSV cargado,
consumiendo el DTO de `Session.get_data_preview()` (contrato D3 del
diseno 3.11.b: `{"columns", "rows", "n_total", "truncated"}`, tipos
nativos Python, ausentes como None). El visor responde a "que cargue?",
no a "que vio el modelo?" (sin imputacion, sin split).

Sala limpia: cero logica analitica; el widget pinta el DTO, no calcula.

REGLA CRITICA 4.1.1 del Design System (`docs/3.11_gui_design_system.md`):
Ctrl+C -> TSV, via el helper estatico
`ReportsPanel._copy_selection_to_clipboard` (sin acoplar instancias).

Retraduccion en caliente via `language_bus` (patron MetricsPanel:
`retranslate_ui()` repinta desde el DTO cacheado; las cabeceras de la
tabla son nombres de columna del CSV —dato, no texto UI— y NO se
traducen).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from frontend_v3.i18n import language_bus, tr
from frontend_v3.reports_panel import ReportsPanel

__all__ = ["DataViewer"]


class DataViewer(QWidget):
    """Bloque Data Viewer: preview crudo del dataset cargado.

    Layout: etiqueta de aviso (estado vacio / truncamiento) sobre una
    tabla de solo lectura. `set_preview(dto)` cachea el DTO y repinta.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dto: dict | None = None
        layout = QVBoxLayout(self)
        self._lbl_notice = QLabel(self)
        self._lbl_notice.setObjectName("dataViewerNotice")
        layout.addWidget(self._lbl_notice)
        self._table = QTableWidget(self)
        self._table.setObjectName("dataViewerTable")
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # REGLA CRITICA 4.1.1: Ctrl+C -> TSV. Contexto acotado a la
        # tabla para no secuestrar el Ctrl+C de otros widgets.
        self._copy_shortcut = QShortcut(
            QKeySequence.StandardKey.Copy,
            self._table,
            context=Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
        self._copy_shortcut.activated.connect(
            lambda: ReportsPanel._copy_selection_to_clipboard(self._table)
        )
        layout.addWidget(self._table, 1)
        language_bus.language_changed.connect(self.retranslate_ui)
        self._refresh()

    # ---------------------------------------------------------- Public API

    def set_preview(self, dto: dict | None) -> None:
        """Recibe el DTO de `Session.get_data_preview()` y repinta.

        None o el dict vacio del backend (sin dataset cargado) muestran
        el estado vacio (`tr("data_viewer_empty")`).
        """
        self._dto = dto
        self._refresh()

    def retranslate_ui(self) -> None:
        """Retraduccion en caliente: repinta desde el DTO cacheado."""
        self._refresh()

    def closeEvent(self, event):
        # Desconexion defensiva del bus: sin ella, el bound method
        # retranslate_ui mantiene el widget vivo tras el cierre.
        try:
            language_bus.language_changed.disconnect(self.retranslate_ui)
        except (RuntimeError, TypeError):
            pass
        super().closeEvent(event)

    # ------------------------------------------------------------ Internals

    def _refresh(self) -> None:
        self._table.clear()
        self._table.setRowCount(0)
        self._table.setColumnCount(0)
        dto = self._dto
        if not dto or dto.get("n_total", 0) == 0:
            self._lbl_notice.setText(tr("data_viewer_empty"))
            self._lbl_notice.setVisible(True)
            return
        columns = [str(c) for c in dto["columns"]]
        rows = list(dto["rows"])
        self._table.setColumnCount(len(columns))
        self._table.setHorizontalHeaderLabels(columns)
        self._table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                # Ausentes (None del contrato D3): celda vacia, nunca
                # el literal "None" ni "nan".
                self._table.setItem(
                    i, j, QTableWidgetItem("" if val is None else str(val))
                )
        if dto.get("truncated"):
            self._lbl_notice.setText(
                tr("data_viewer_truncated").format(
                    shown=len(rows), total=dto["n_total"]
                )
            )
            self._lbl_notice.setVisible(True)
        else:
            self._lbl_notice.setVisible(False)
