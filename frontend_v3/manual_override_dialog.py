"""Manual Override Log dialog (TreeGov, Phase 3.11.d.3).

Design: docs/3.11.d_design_context_menu_interactivity.md §4. Renders
``SessionState.manual_overrides`` — one row per manual intervention with
columns Time | Node | Action | FP Before | FP After (the ``params_str``
field of the log tuple is kept in the backend record but not displayed).
No analytical logic here (clean room): the dialog only renders the
immutable backend record and copies it as TSV (CRITICAL RULE 4.1.1 of
the Design System, via the generic helper
``ReportsPanel._copy_selection_to_clipboard``).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from frontend_v3.i18n import tr
from frontend_v3.reports_panel import ReportsPanel

_HEADERS = (
    "override_col_time",
    "override_col_node",
    "override_col_action",
    "override_col_fp_before",
    "override_col_fp_after",
)


class ManualOverrideDialog(QDialog):
    """Modal table of the Manual Override Log (one row per intervention)."""

    def __init__(
        self,
        parent: QWidget | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(parent)
        self._logger = logger
        self.setModal(True)
        self.setObjectName("manual_override_dialog")
        self.resize(640, 320)
        self._build_ui()
        self.retranslate_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._lbl_empty = QLabel(self)
        self._lbl_empty.setObjectName("override_empty_label")
        self._lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_empty.setWordWrap(True)
        self._lbl_empty.setVisible(False)
        layout.addWidget(self._lbl_empty)

        self._table = QTableWidget(0, len(_HEADERS), self)
        self._table.setObjectName("override_table")
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        # Ctrl+C copia la seleccion (o toda la tabla si no hay seleccion)
        # como TSV al portapapeles — REGLA CRITICA 4.1.1 del Design
        # System. Mismo patron que UnivariateDialog/PruneDialog/DataViewer.
        self._copy_shortcut = QShortcut(
            QKeySequence.StandardKey.Copy,
            self._table,
            context=Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
        self._copy_shortcut.activated.connect(
            lambda: ReportsPanel._copy_selection_to_clipboard(self._table)
        )
        layout.addWidget(self._table)

        botones = QHBoxLayout()
        botones.addStretch(1)
        self._btn_copy = QPushButton(self)
        self._btn_copy.setObjectName("override_btn_copy")
        self._btn_copy.clicked.connect(self._on_copy_tsv)
        self._btn_close = QPushButton(self)
        self._btn_close.setObjectName("override_btn_close")
        self._btn_close.clicked.connect(self.accept)
        botones.addWidget(self._btn_copy)
        botones.addWidget(self._btn_close)
        layout.addLayout(botones)

    def retranslate_ui(self) -> None:
        """Re-aplica tr() a los textos visibles del dialogo."""
        self.setWindowTitle(tr("override_title"))
        self._lbl_empty.setText(tr("override_empty"))
        self._table.setHorizontalHeaderLabels([tr(k) for k in _HEADERS])
        # TODO(zona_gris): se reutiliza la clave existente
        # "univariate_btn_copy" (texto identico: "Copy TSV"/"Copiar TSV");
        # pendiente una clave generica btn_copy_tsv compartida.
        self._btn_copy.setText(tr("univariate_btn_copy"))
        self._btn_close.setText(tr("reports_export_close"))

    # ------------------------------------------------------------------
    # Datos (registro inmutable del backend; sala limpia)
    # ------------------------------------------------------------------

    def set_data(self, overrides: tuple) -> None:
        """Limpia la tabla y la puebla con SessionState.manual_overrides.

        Cada elemento es (timestamp_str, node_id, action, params_str,
        fp_before, fp_after); params_str no se muestra en la tabla.
        """
        self._table.setRowCount(0)
        self._table.setRowCount(len(overrides))
        for row, override in enumerate(overrides):
            timestamp, node_id, action, _params, fp_before, fp_after = override
            valores = (
                str(timestamp),
                str(node_id),
                str(action),
                str(fp_before),
                str(fp_after),
            )
            for col, texto in enumerate(valores):
                self._table.setItem(row, col, QTableWidgetItem(texto))
        hay_datos = len(overrides) > 0
        self._table.setVisible(hay_datos)
        self._lbl_empty.setVisible(not hay_datos)
        self._btn_copy.setEnabled(hay_datos)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_copy_tsv(self) -> None:
        ReportsPanel._copy_selection_to_clipboard(self._table)
