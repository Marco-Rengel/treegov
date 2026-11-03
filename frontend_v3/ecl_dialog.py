"""Dialog and worker for the simplified ECL calculation (Phase 7).

Clean-room boundary: widgets only collect parameters and render the flat
summary returned by ``Session.calculate_ecl``. All validation and analytics
remain in the backend.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from frontend_v3.i18n import language_bus, tr
from frontend_v3.reports_panel import ReportsPanel

if TYPE_CHECKING:
    from backend_v3.session_state import Session

__all__ = ["ECLWorker", "ECLDialog"]


class ECLWorker(QThread):
    """Execute ``Session.calculate_ecl`` outside the GUI thread."""

    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        session: "Session",
        csv_path: str,
        pd_column: str,
        eir: float | None,
    ) -> None:
        super().__init__()
        self._session = session
        self._csv_path = csv_path
        self._pd_column = pd_column
        self._eir = eir

    def run(self) -> None:
        """Transport the bounded summary or the backend error to the dialog."""
        try:
            result = self._session.calculate_ecl(
                self._csv_path,
                pd_column=self._pd_column,
                eir=self._eir,
            )
        except Exception as exc:  # noqa: BLE001 - transport backend error to UI
            self.failed.emit(str(exc))
        else:
            self.finished_ok.emit(result)


class ECLDialog(QDialog):
    """Collect ECL inputs and display totals and stage counts."""

    def __init__(self, session: "Session", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session = session
        self._worker: ECLWorker | None = None
        self._running = False
        # Cached flat DTO: retranslate_ui repaints the five rows from it so a
        # language switch never leaves the table in the previous language.
        self._report_dto: dict | None = None
        self._bus_attached = False
        self.setModal(True)
        self.setObjectName("ecl_dialog")
        self.resize(560, 400)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._csv_edit = QLineEdit(self)
        self._browse_button = QPushButton(tr("scoring_btn_browse"), self)
        self._browse_button.clicked.connect(self._browse_csv)
        csv_row = QHBoxLayout()
        csv_row.setContentsMargins(0, 0, 0, 0)
        csv_row.addWidget(self._csv_edit, 1)
        csv_row.addWidget(self._browse_button)
        csv_container = QWidget(self)
        csv_container.setLayout(csv_row)
        self._lbl_input_csv = QLabel(self)
        form.addRow(self._lbl_input_csv, csv_container)

        self._pd_edit = QLineEdit("pd_current", self)
        self._lbl_pd_col = QLabel(self)
        form.addRow(self._lbl_pd_col, self._pd_edit)

        self._eir_spin = QDoubleSpinBox(self)
        self._eir_spin.setDecimals(6)
        self._eir_spin.setRange(-0.999999, 1_000_000.0)
        self._eir_spin.setValue(0.0)
        self._eir_spin.setEnabled(False)
        self._lbl_eir = QLabel(self)
        form.addRow(self._lbl_eir, self._eir_spin)

        self._discount_check = QCheckBox(self)
        self._discount_check.toggled.connect(self._eir_spin.setEnabled)
        form.addRow("", self._discount_check)

        self._table = QTableWidget(0, 2, self)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.setVisible(False)
        self._copy_shortcut = QShortcut(
            QKeySequence.StandardKey.Copy,
            self._table,
            context=Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
        self._copy_shortcut.activated.connect(self._copy_results_to_clipboard)
        layout.addWidget(self._table, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._cancel_button = QPushButton(self)
        self._cancel_button.clicked.connect(self.reject)
        self._calculate_button = QPushButton(self)
        self._calculate_button.setEnabled(False)
        self._calculate_button.clicked.connect(self._on_calculate)
        buttons.addWidget(self._cancel_button)
        buttons.addWidget(self._calculate_button)
        layout.addLayout(buttons)

        self._csv_edit.textChanged.connect(self._sync_calculate_button)

        self.retranslate_ui()
        language_bus.language_changed.connect(self.retranslate_ui)
        self._bus_attached = True

    # ------------------------------------------------------------ Public API

    def retranslate_ui(self) -> None:
        """Single text path: first paint and live language switches."""
        self.setWindowTitle(tr("ecl_dlg_title"))
        self._lbl_input_csv.setText(tr("ecl_input_csv"))
        self._lbl_pd_col.setText(tr("ecl_pd_col"))
        self._lbl_eir.setText(tr("ecl_eir"))
        self._browse_button.setText(tr("scoring_btn_browse"))
        self._discount_check.setText(tr("ecl_apply_eir"))
        self._table.setHorizontalHeaderLabels(
            [tr("ecl_col_metric"), tr("ecl_col_value")]
        )
        self._cancel_button.setText(tr("wizard_cancel"))
        self._calculate_button.setText(tr("ecl_btn_calculate"))
        # Without the cached DTO a switch would leave the rendered rows in the
        # previous language; a running worker owns the table until it finishes.
        if self._report_dto is not None and not self._running:
            self._on_finished(self._report_dto)

    def _detach_bus(self) -> None:
        """Idempotent disconnect so a dead dialog never gets stale signals."""
        if not self._bus_attached:
            return
        try:
            language_bus.language_changed.disconnect(self.retranslate_ui)
        except (RuntimeError, TypeError):
            pass  # already disconnected
        finally:
            self._bus_attached = False

    def _sync_calculate_button(self) -> None:
        """Enable calculation only with a CSV path and no active worker."""
        self._calculate_button.setEnabled(
            bool(self._csv_edit.text().strip()) and not self._running
        )

    def _set_inputs_enabled(self, enabled: bool) -> None:
        """Toggle input controls without changing the EIR checkbox state."""
        for widget in (
            self._csv_edit,
            self._browse_button,
            self._pd_edit,
            self._discount_check,
        ):
            widget.setEnabled(enabled)
        self._eir_spin.setEnabled(enabled and self._discount_check.isChecked())

    def _browse_csv(self) -> None:
        """Select the input CSV without reading it in the frontend."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("ecl_input_dialog_title"),
            "",
            tr("scoring_csv_filter"),
        )
        if path:
            self._csv_edit.setText(os.path.normpath(path))

    def _on_calculate(self) -> None:
        """Start one backend calculation with the current form values."""
        csv_path = self._csv_edit.text().strip()
        if self._running or not csv_path:
            return

        self._running = True
        self._set_inputs_enabled(False)
        self._calculate_button.setEnabled(False)
        self._cancel_button.setEnabled(False)
        self._table.setVisible(False)

        eir = self._eir_spin.value() if self._discount_check.isChecked() else None
        self._worker = ECLWorker(
            self._session,
            csv_path,
            self._pd_edit.text().strip(),
            eir,
        )
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_error)
        self._worker.start()

    @staticmethod
    def _format_value(value: object) -> str:
        """Format floats to two decimals and preserve missing values visibly."""
        if value is None:
            return "—"
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)

    def _on_finished(self, result: dict) -> None:
        """Render the bounded summary and hide the calculate action."""
        self._report_dto = result
        self._running = False
        self._cancel_button.setEnabled(True)
        self._calculate_button.setVisible(False)

        stage_counts = result.get("stage_counts", (None, None, None))
        metrics = (
            (tr("ecl_total_12m"), result.get("total_ecl_12m")),
            (tr("ecl_total_lifetime"), result.get("total_ecl_lifetime")),
            (tr("ecl_stage_1"), stage_counts[0]),
            (tr("ecl_stage_2"), stage_counts[1]),
            (tr("ecl_stage_3"), stage_counts[2]),
        )
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(metrics))
        for row, (label, value) in enumerate(metrics):
            self._table.setItem(row, 0, QTableWidgetItem(label))
            value_item = QTableWidgetItem(self._format_value(value))
            value_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(row, 1, value_item)
        # Keep the contractual metric order; interactive sorting would reorder
        # the five fixed summary rows as soon as it is enabled.
        self._table.setVisible(True)

    def _on_error(self, error: str) -> None:
        """Restore the form and display a backend or CSV error."""
        self._running = False
        self._set_inputs_enabled(True)
        self._cancel_button.setEnabled(True)
        self._sync_calculate_button()
        QMessageBox.critical(self, tr("msg_error_title"), error)

    def _copy_results_to_clipboard(self) -> None:
        """Copy the selection, or all results, as TSV (Rule 4.1.1)."""
        ReportsPanel._copy_selection_to_clipboard(self._table)

    def reject(self) -> None:
        """Prevent closing the dialog while the backend worker is active."""
        if self._running:
            return
        super().reject()

    def closeEvent(self, event) -> None:
        """Detach the bus on window close (QDialog.close)."""
        self._detach_bus()
        super().closeEvent(event)

    def done(self, result: int) -> None:
        """Detach the bus on accept/reject; ``closeEvent`` does not fire there."""
        self._detach_bus()
        super().done(result)
