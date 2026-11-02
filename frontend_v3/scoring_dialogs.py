"""Dialogs and workers for Phase 6 batch scoring and Champion-Challenger.

Clean-room boundary: widgets only collect parameters and render flat DTOs.
Every analytical operation, including CSV I/O, lives in ``Session``/backend.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from frontend_v3.i18n import tr
from frontend_v3.reports_panel import ReportsPanel

if TYPE_CHECKING:
    from backend_v3.session_state import Session


# The canonical TSV helper is a ReportsPanel static method. Aliasing it here
# keeps this module independent of panel instances and preserves Rule 4.1.1.
_copy_selection_to_clipboard = ReportsPanel._copy_selection_to_clipboard

__all__ = [
    "BatchWorker",
    "BatchScoringDialog",
    "CCWorker",
    "ChampionChallengerDialog",
]


class BatchWorker(QThread):
    """Execute Session.score_batch outside the GUI thread."""

    finished_ok = Signal(dict)
    failed = Signal(str)
    progress = Signal(int)

    def __init__(
        self,
        session: "Session",
        input_path: str,
        output_path: str,
        unseen_policy: str,
        chunksize: int,
        include_rules: bool,
    ) -> None:
        super().__init__()
        self._session = session
        self._input_path = input_path
        self._output_path = output_path
        self._unseen_policy = unseen_policy
        self._chunksize = chunksize
        self._include_rules = include_rules

    def run(self) -> None:
        try:
            result = self._session.score_batch(
                csv_path=self._input_path,
                output_path=self._output_path,
                unseen_policy=self._unseen_policy,
                chunksize=self._chunksize,
                include_rules=self._include_rules,
            )
        except Exception as exc:  # noqa: BLE001 - transport backend error to UI
            self.failed.emit(str(exc))
        else:
            self.finished_ok.emit(result)


class CCWorker(QThread):
    """Execute Session.compare_champion_challenger outside the GUI thread."""

    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        session: "Session",
        eval_csv: str,
        challenger_engine: str,
        target: str | None,
        weight_col: str | None,
        unseen_policy: str,
    ) -> None:
        super().__init__()
        self._session = session
        self._eval_csv = eval_csv
        self._challenger_engine = challenger_engine
        self._target = target
        self._weight_col = weight_col
        self._unseen_policy = unseen_policy

    def run(self) -> None:
        try:
            result = self._session.compare_champion_challenger(
                evaluation_csv=self._eval_csv,
                challenger_engine=self._challenger_engine,
                target=self._target,
                weight_col=self._weight_col,
                unseen_policy=self._unseen_policy,
            )
        except Exception as exc:  # noqa: BLE001 - transport backend error to UI
            self.failed.emit(str(exc))
        else:
            self.finished_ok.emit(result)


class BatchScoringDialog(QDialog):
    """Collect batch-scoring parameters and display its bounded summary."""

    def __init__(self, session: "Session", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session = session
        self._worker: BatchWorker | None = None
        self._running = False
        self.setModal(True)
        self.setObjectName("batch_scoring_dialog")
        self.resize(620, 280)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._input_edit = QLineEdit(self)
        self._input_button = QPushButton(tr("scoring_btn_browse"), self)
        self._input_button.clicked.connect(self._browse_input)
        input_row = QHBoxLayout()
        input_row.addWidget(self._input_edit, 1)
        input_row.addWidget(self._input_button)
        input_container = QWidget(self)
        input_container.setLayout(input_row)
        input_row.setContentsMargins(0, 0, 0, 0)
        form.addRow(tr("batch_input_label"), input_container)

        self._output_edit = QLineEdit(self)
        self._output_button = QPushButton(tr("scoring_btn_browse"), self)
        self._output_button.clicked.connect(self._browse_output)
        output_row = QHBoxLayout()
        output_row.addWidget(self._output_edit, 1)
        output_row.addWidget(self._output_button)
        output_container = QWidget(self)
        output_container.setLayout(output_row)
        output_row.setContentsMargins(0, 0, 0, 0)
        form.addRow(tr("batch_output_label"), output_container)

        self._policy_combo = QComboBox(self)
        self._policy_combo.addItems(["exclude", "error", "majority"])
        form.addRow(tr("scoring_policy_label"), self._policy_combo)

        self._chunksize_spin = QSpinBox(self)
        self._chunksize_spin.setRange(1, 10_000_000)
        self._chunksize_spin.setValue(50000)
        form.addRow(tr("batch_chunksize_label"), self._chunksize_spin)

        self._rules_check = QCheckBox(self)
        self._rules_check.setChecked(True)
        form.addRow(tr("batch_include_rules_label"), self._rules_check)

        self._progress = QProgressBar(self)
        self._progress.setTextVisible(False)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._cancel_button = QPushButton(tr("wizard_cancel"), self)
        self._cancel_button.clicked.connect(self.reject)
        self._run_button = QPushButton(tr("scoring_btn_execute"), self)
        self._run_button.setEnabled(False)
        self._run_button.clicked.connect(self._execute)
        buttons.addWidget(self._cancel_button)
        buttons.addWidget(self._run_button)
        layout.addLayout(buttons)

        self._input_edit.textChanged.connect(self._sync_execute_button)
        self._output_edit.textChanged.connect(self._sync_execute_button)
        self.setWindowTitle(tr("batch_dialog_title"))

    def _sync_execute_button(self) -> None:
        has_paths = bool(
            self._input_edit.text().strip() and self._output_edit.text().strip()
        )
        self._run_button.setEnabled(has_paths and not self._running)

    def _set_running(self, running: bool) -> None:
        self._running = running
        for widget in (
            self._input_edit,
            self._input_button,
            self._output_edit,
            self._output_button,
            self._policy_combo,
            self._chunksize_spin,
            self._rules_check,
            self._cancel_button,
        ):
            widget.setEnabled(not running)
        self._progress.setVisible(running)
        if running:
            self._progress.setRange(0, 0)
        else:
            self._progress.setRange(0, 1)
            self._progress.setValue(0)
        self._sync_execute_button()

    def _browse_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("batch_input_dialog_title"),
            "",
            tr("scoring_csv_filter"),
        )
        if path:
            self._input_edit.setText(path)

    def _browse_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("batch_output_dialog_title"),
            "scored.csv",
            tr("scoring_csv_filter"),
        )
        if path:
            self._output_edit.setText(path)

    def _execute(self) -> None:
        if self._running:
            return
        self._set_running(True)
        self._worker = BatchWorker(
            self._session,
            self._input_edit.text().strip(),
            self._output_edit.text().strip(),
            self._policy_combo.currentText(),
            self._chunksize_spin.value(),
            self._rules_check.isChecked(),
        )
        self._worker.finished_ok.connect(self._on_worker_finished)
        self._worker.failed.connect(self._on_worker_failed)
        self._worker.start()

    def _on_worker_finished(self, res: dict) -> None:
        self._set_running(False)
        self.accept()
        body = tr("batch_success_body").format(
            output=os.path.basename(str(res.get("output_path", ""))),
            total=res.get("total_rows", 0),
            scored=res.get("scored_rows", 0),
            excluded=res.get("excluded_rows", 0),
            fallbacks=res.get("majority_fallback_rows", 0),
        )
        QMessageBox.information(self, tr("batch_success_title"), body)

    def _on_worker_failed(self, err: str) -> None:
        self._set_running(False)
        QMessageBox.critical(self, tr("msg_error_title"), err)

    def reject(self) -> None:
        if self._running:
            return
        super().reject()


class ChampionChallengerDialog(QDialog):
    """Configure a challenger and render the comparison DTO without analytics."""

    def __init__(self, session: "Session", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session = session
        self._worker: CCWorker | None = None
        self._running = False
        self.setModal(True)
        self.setObjectName("champion_challenger_dialog")
        self.resize(760, 520)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._eval_edit = QLineEdit(self)
        self._eval_button = QPushButton(tr("scoring_btn_browse"), self)
        self._eval_button.clicked.connect(self._browse_evaluation)
        eval_row = QHBoxLayout()
        eval_row.addWidget(self._eval_edit, 1)
        eval_row.addWidget(self._eval_button)
        eval_container = QWidget(self)
        eval_container.setLayout(eval_row)
        eval_row.setContentsMargins(0, 0, 0, 0)
        form.addRow(tr("cc_eval_label"), eval_container)

        self._engine_combo = QComboBox(self)
        self._engine_combo.addItems(["CRT", "CHAID", "QUEST"])
        form.addRow(tr("cc_engine_label"), self._engine_combo)

        self._target_edit = QLineEdit(self)
        form.addRow(tr("cc_target_label"), self._target_edit)

        self._weight_edit = QLineEdit(self)
        form.addRow(tr("cc_weight_label"), self._weight_edit)

        self._policy_combo = QComboBox(self)
        self._policy_combo.addItems(["exclude", "error", "majority"])
        form.addRow(tr("scoring_policy_label"), self._policy_combo)

        self._result_label = QLabel(self)
        self._result_label.setWordWrap(True)
        self._result_label.setVisible(False)
        layout.addWidget(self._result_label)

        self._progress = QProgressBar(self)
        self._progress.setTextVisible(False)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._table = QTableWidget(0, 4, self)
        self._table.setHorizontalHeaderLabels([
            tr("cc_col_metric"),
            tr("cc_col_champion"),
            tr("cc_col_challenger"),
            tr("cc_col_delta"),
        ])
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setVisible(False)
        self._copy_shortcut = QShortcut(
            QKeySequence.StandardKey.Copy,
            self._table,
            context=Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
        self._copy_shortcut.activated.connect(
            lambda: _copy_selection_to_clipboard(self._table)
        )
        layout.addWidget(self._table, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._cancel_button = QPushButton(tr("wizard_cancel"), self)
        self._cancel_button.clicked.connect(self.reject)
        self._run_button = QPushButton(tr("scoring_btn_execute"), self)
        self._run_button.setEnabled(False)
        self._run_button.clicked.connect(self._execute)
        buttons.addWidget(self._cancel_button)
        buttons.addWidget(self._run_button)
        layout.addLayout(buttons)

        self._eval_edit.textChanged.connect(self._sync_execute_button)
        self.setWindowTitle(tr("cc_dialog_title"))

    def _sync_execute_button(self) -> None:
        self._run_button.setEnabled(
            bool(self._eval_edit.text().strip()) and not self._running
        )

    def _set_running(self, running: bool) -> None:
        self._running = running
        for widget in (
            self._eval_edit,
            self._eval_button,
            self._engine_combo,
            self._target_edit,
            self._weight_edit,
            self._policy_combo,
            self._cancel_button,
        ):
            widget.setEnabled(not running)
        self._progress.setVisible(running)
        if running:
            self._progress.setRange(0, 0)
        else:
            self._progress.setRange(0, 1)
            self._progress.setValue(0)
        self._sync_execute_button()

    def _browse_evaluation(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("cc_eval_dialog_title"),
            "",
            tr("scoring_csv_filter"),
        )
        if path:
            self._eval_edit.setText(path)

    def _execute(self) -> None:
        if self._running:
            return
        self._set_running(True)
        self._table.setVisible(False)
        self._result_label.setVisible(False)
        self._worker = CCWorker(
            self._session,
            self._eval_edit.text().strip(),
            self._engine_combo.currentText(),
            self._target_edit.text().strip() or None,
            self._weight_edit.text().strip() or None,
            self._policy_combo.currentText(),
        )
        self._worker.finished_ok.connect(self._on_worker_finished)
        self._worker.failed.connect(self._on_worker_failed)
        self._worker.start()

    @staticmethod
    def _format_metric(value: float | None) -> str:
        return "—" if value is None else f"{float(value):.6g}"

    def _on_worker_finished(self, res: dict) -> None:
        self._set_running(False)
        self._result_label.setText(
            tr("cc_result_summary").format(
                champion=res.get("champion_fingerprint", ""),
                challenger=res.get("challenger_fingerprint", ""),
                common=res.get("n_common_routed", 0),
            )
        )
        self._result_label.setVisible(True)

        metrics = res.get("metrics", ())
        self._table.setRowCount(len(metrics))
        for row, metric in enumerate(metrics):
            name, champion, challenger, delta = metric
            values = (
                str(name),
                self._format_metric(champion),
                self._format_metric(challenger),
                self._format_metric(delta),
            )
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col > 0:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self._table.setItem(row, col, item)
        self._table.setVisible(True)

    def _on_worker_failed(self, err: str) -> None:
        self._set_running(False)
        QMessageBox.critical(self, tr("msg_error_title"), err)

    def reject(self) -> None:
        if self._running:
            return
        super().reject()
