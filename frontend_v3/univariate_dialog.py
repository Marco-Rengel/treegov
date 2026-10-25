"""Univariate trees dialog (TreeGov, Phase 3.11.c.2).

Design: docs/3.11.c_design_univariate_cost_matrix.md §2.2. The dialog
shows the flat DTO exposed by ``Session.get_univariate_trees(max_depth)``
(one dict per predictor with keys ``predictor``, ``gini``, ``ks`` and
``cut_points``) in a 4-column table (Predictor | Gini | KS | Cuts).
No analytical logic here (clean room): all computation lives in
``backend_v3``; this dialog only renders the DTO, copies it as TSV
(CRITICAL RULE 4.1.1 of the Design System, via the generic helper
``ReportsPanel._copy_selection_to_clipboard``) and exports it as CSV.
"""

from __future__ import annotations

import csv
import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from frontend_v3.i18n import tr
from frontend_v3.reports_panel import ReportsPanel

_HEADERS = (
    "univariate_col_predictor",
    "univariate_col_gini",
    "univariate_col_ks",
    "univariate_col_cuts",
)


class UnivariateDialog(QDialog):
    """Modal table of univariate trees (one row per predictor)."""

    def __init__(
        self,
        parent: QWidget | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(parent)
        self._logger = logger
        self.setModal(True)
        self.setObjectName("univariate_dialog")
        self.resize(560, 360)
        self._build_ui()
        self.retranslate_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._lbl_empty = QLabel(self)
        self._lbl_empty.setObjectName("univariate_empty_label")
        self._lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_empty.setWordWrap(True)
        self._lbl_empty.setVisible(False)
        layout.addWidget(self._lbl_empty)

        self._table = QTableWidget(0, len(_HEADERS), self)
        self._table.setObjectName("univariate_table")
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
        # System. Mismo patron que PruneDialog/DataViewer.
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
        self._btn_copy.setObjectName("univariate_btn_copy")
        self._btn_copy.clicked.connect(self._on_copy_tsv)
        self._btn_export = QPushButton(self)
        self._btn_export.setObjectName("univariate_btn_export")
        self._btn_export.clicked.connect(self._on_export_csv)
        self._btn_close = QPushButton(self)
        self._btn_close.setObjectName("univariate_btn_close")
        self._btn_close.clicked.connect(self.accept)
        botones.addWidget(self._btn_copy)
        botones.addWidget(self._btn_export)
        botones.addWidget(self._btn_close)
        layout.addLayout(botones)

    def retranslate_ui(self) -> None:
        """Re-aplica tr() a los textos visibles del dialogo."""
        self.setWindowTitle(tr("univariate_title"))
        self._lbl_empty.setText(tr("univariate_empty"))
        self._table.setHorizontalHeaderLabels([tr(k) for k in _HEADERS])
        self._btn_copy.setText(tr("univariate_btn_copy"))
        self._btn_export.setText(tr("univariate_btn_export"))
        self._btn_close.setText(tr("reports_export_close"))

    # ------------------------------------------------------------------
    # Datos (DTO plano del backend; sala limpia)
    # ------------------------------------------------------------------

    def set_data(self, data: list[dict]) -> None:
        """Limpia la tabla y la puebla con el DTO de get_univariate_trees."""
        self._table.setRowCount(0)
        self._table.setRowCount(len(data))
        for row, item in enumerate(data):
            cuts = "; ".join(
                f"{var}: {thr:.6g}" for var, thr in item.get("cut_points", [])
            )
            valores = (
                str(item.get("predictor", "")),
                f"{float(item.get('gini', 0.0)):.4f}",
                f"{float(item.get('ks', 0.0)):.4f}",
                cuts,
            )
            for col, texto in enumerate(valores):
                cell = QTableWidgetItem(texto)
                if col in (1, 2):
                    cell.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )
                self._table.setItem(row, col, cell)
        hay_datos = len(data) > 0
        self._table.setVisible(hay_datos)
        self._lbl_empty.setVisible(not hay_datos)
        self._btn_copy.setEnabled(hay_datos)
        self._btn_export.setEnabled(hay_datos)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_copy_tsv(self) -> None:
        ReportsPanel._copy_selection_to_clipboard(self._table)

    def _on_export_csv(self) -> None:
        path, _filt = QFileDialog.getSaveFileName(
            self, tr("univariate_btn_export"), "univariate_trees.csv",
            "CSV (*.csv)",
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow([tr(k) for k in _HEADERS])
                for row in range(self._table.rowCount()):
                    writer.writerow([
                        self._table.item(row, col).text()
                        if self._table.item(row, col) is not None else ""
                        for col in range(self._table.columnCount())
                    ])
        except OSError as exc:
            QMessageBox.warning(self, tr("msg_error_title"), str(exc))
            return
        if self._logger is not None:
            self._logger.info(
                "[gui] univariate trees exportados a CSV: %s (%d filas)",
                path, self._table.rowCount(),
            )
