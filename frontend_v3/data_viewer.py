"""DataViewer — bloque Data Viewer del panel izquierdo (Fase 3.11.b.2).

Widget de solo lectura que muestra el preview crudo del CSV cargado,
consumiendo el DTO de `Session.get_data_preview()` (contrato D3 del
diseno 3.11.b: `{"columns", "rows", "n_total", "truncated"}`, tipos
nativos Python, ausentes como None). Fase 3.12.f: al seleccionar un nodo
consume `Session.get_node_cases()` con la particion elegida; al
deseleccionar vuelve al preview completo, sin cambiar el contrato D3.

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

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from frontend_v3.i18n import language_bus, tr
from frontend_v3.reports_panel import ReportsPanel

if TYPE_CHECKING:  # pragma: no cover - typing only
    from backend_v3.session_state import Session

__all__ = ["DataViewer"]

_PARTITIONS = ("train", "oos", "oot", "all")


class DataViewer(QWidget):
    """Bloque Data Viewer: preview crudo del dataset cargado.

    Layout: etiqueta de aviso (estado vacio / truncamiento) sobre una
    tabla de solo lectura. `set_preview(dto)` cachea el DTO y repinta.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dto: dict | None = None
        self._session: Session | None = None
        self._node_id: int | None = None
        layout = QVBoxLayout(self)

        partition_row = QHBoxLayout()
        self._lbl_partition = QLabel(self)
        partition_row.addWidget(self._lbl_partition)
        self._partition_combo = QComboBox(self)
        self._partition_combo.setObjectName("dataViewerPartition")
        for code in _PARTITIONS:
            self._partition_combo.addItem("", userData=code)
        partition_row.addWidget(self._partition_combo)
        partition_row.addStretch(1)
        layout.addLayout(partition_row)

        self._lbl_notice = QLabel(self)
        self._lbl_notice.setObjectName("dataViewerNotice")
        self._lbl_notice.setWordWrap(True)
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
        self._partition_combo.currentIndexChanged.connect(
            self._on_partition_changed
        )
        language_bus.language_changed.connect(self.retranslate_ui)
        self.retranslate_ui()

    # ---------------------------------------------------------- Public API

    def set_session(self, session: Session | None) -> None:
        """Guarda la sesion usada por `refresh_cases` (sin repintar)."""
        self._session = session

    def set_preview(self, dto: dict | None) -> None:
        """Recibe el DTO de `Session.get_data_preview()` y repinta.

        None o el dict vacio del backend (sin dataset cargado) muestran
        el estado vacio (`tr("data_viewer_empty")`). Es la entrada del
        preview completo, por lo que tambien limpia el nodo seleccionado.
        """
        self._node_id = None
        self._set_dto(dto)

    def refresh_cases(self, node_id: int | None) -> None:
        """Muestra los casos del nodo o vuelve al preview completo.

        Con nodo, llama a `get_node_cases(node_id, partition=...,
        n_rows=50)`. Sin nodo, conserva el comportamiento previo y llama
        a `get_data_preview()`. Sin sesion no hay consulta posible: solo
        se repinta el DTO cacheado (o se limpia si se pidio un nodo).
        """
        self._node_id = None if node_id is None else int(node_id)
        if self._session is None:
            if self._node_id is not None:
                self._set_dto(None)
            else:
                self._refresh()
            return
        if self._node_id is None:
            self._set_dto(self._session.get_data_preview())
        else:
            self._set_dto(self._session.get_node_cases(
                self._node_id,
                partition=self.current_partition(),
                n_rows=50,
            ))

    def current_partition(self) -> str:
        """Codigo de particion activo: train, oos, oot o all."""
        data = self._partition_combo.currentData()
        return str(data) if data is not None else "train"

    def retranslate_ui(self) -> None:
        """Retraduce selector y avisos; repinta desde el DTO cacheado."""
        self._lbl_partition.setText(tr("data_viewer_partition_label"))
        for index, code in enumerate(_PARTITIONS):
            self._partition_combo.setItemText(
                index, tr(f"data_viewer_partition_{code}")
            )
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

    def _set_dto(self, dto: dict | None) -> None:
        self._dto = dto
        self._refresh()

    def _on_partition_changed(self, _index: int) -> None:
        self.refresh_cases(self._node_id)

    def _refresh(self) -> None:
        # La particion solo es seleccionable cuando hay un nodo activo.
        self._partition_combo.setEnabled(self._node_id is not None)
        self._table.clear()
        self._table.setRowCount(0)
        self._table.setColumnCount(0)
        dto = self._dto
        if not dto or dto.get("n_total", 0) == 0:
            empty_key = (
                "data_viewer_node_empty"
                if self._node_id is not None
                else "data_viewer_empty"
            )
            self._lbl_notice.setText(tr(empty_key))
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
        notices: list[str] = []
        if self._node_id is not None:
            notices.append(
                tr("data_viewer_node_hint").format(node_id=self._node_id)
            )
        if dto.get("truncated"):
            notices.append(
                tr("data_viewer_truncated").format(
                    shown=len(rows), total=dto["n_total"]
                )
            )
        self._lbl_notice.setText(" ".join(notices))
        self._lbl_notice.setVisible(bool(notices))
