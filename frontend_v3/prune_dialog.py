"""Interactive cost-complexity pruning dialog (TreeGov, Phase 3.9).

Design: docs/design_decisions.md §8.7. The dialog shows the pruning
sequence exposed by ``Session.get_prune_sequence()`` (flat DTO with
keys ``alpha``, ``n_leaves``, ``r_subtree``) and lets the analyst pick
the alpha with discretion (MRM human-in-the-loop). No analytical logic
here: all computation lives in ``backend_v3``; this dialog only reads
the DTO and calls ``Session.prune(alpha)``.

Live retranslation arrives via the language bus (same pattern as the
wizard and the panels); the bus is disconnected in ``done()`` so a
closed dialog never receives stale signals.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
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

_HEADERS = ("prune_col_alpha", "prune_col_terminal_nodes", "prune_col_error")


class PruneDialog(QDialog):
    """Modal table of PruneSteps + apply/close buttons (§8.7)."""

    def __init__(
        self,
        session,
        bus,
        parent: QWidget | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(parent)
        self._session = session
        self._bus = bus
        self._logger = logger
        self._sequence = session.get_prune_sequence()
        self.setModal(True)
        self.resize(440, 320)
        self._build_ui()
        self.retranslate_ui()
        self._bus.language_changed.connect(self.retranslate_ui)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._lbl_empty = QLabel(self)
        self._lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_empty.setWordWrap(True)
        layout.addWidget(self._lbl_empty)

        self._table = QTableWidget(len(self._sequence), 3, self)
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._table.verticalHeader().setVisible(False)
        for row, paso in enumerate(self._sequence):
            self._fill_row(row, paso)
        self._table.itemSelectionChanged.connect(self._sync_apply_button)
        # Ctrl+C copia la seleccion (o toda la tabla si no hay seleccion)
        # como TSV al portapapeles — REGLA CRITICA 4.1.1 del Design
        # System. El helper generico vive en ReportsPanel como
        # staticmethod (25/10/2026): se reutiliza sin acoplar instancias.
        # Contexto WidgetWithChildren para no secuestrar Ctrl+C de otros
        # widgets de la misma ventana.
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
        self._btn_apply = QPushButton(self)
        self._btn_apply.setEnabled(False)
        self._btn_apply.clicked.connect(self._on_apply)
        self._btn_close = QPushButton(self)
        self._btn_close.clicked.connect(self.reject)
        botones.addWidget(self._btn_apply)
        botones.addWidget(self._btn_close)
        layout.addLayout(botones)

        if not self._sequence:
            self._table.setVisible(False)
            self._lbl_empty.setVisible(True)
        else:
            self._lbl_empty.setVisible(False)

    def _fill_row(self, row: int, paso: dict) -> None:
        valores = (
            f"{paso['alpha']:.6g}",
            str(paso["n_leaves"]),
            f"{paso['r_subtree']:.6g}",
        )
        for col, texto in enumerate(valores):
            item = QTableWidgetItem(texto)
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(row, col, item)

    def retranslate_ui(self) -> None:
        """Single text path: first paint and live language switches."""
        self.setWindowTitle(tr("prune_dialog_title"))
        self._table.setHorizontalHeaderLabels([tr(k) for k in _HEADERS])
        self._lbl_empty.setText(tr("prune_no_sequence"))
        self._btn_apply.setText(tr("prune_btn_apply"))
        self._btn_close.setText(tr("prune_btn_close"))

    # ------------------------------------------------------------------
    # behaviour
    # ------------------------------------------------------------------

    def _sync_apply_button(self) -> None:
        self._btn_apply.setEnabled(
            bool(self._sequence) and self._table.currentRow() >= 0
        )

    def _on_apply(self) -> None:
        """Apply the selected alpha via Session.prune and accept()."""
        row = self._table.currentRow()
        if row < 0 or not self._sequence:
            return
        alpha = float(self._sequence[row]["alpha"])
        try:
            self._session.prune(alpha)
        except Exception as exc:  # noqa: BLE001 - last UI line of defense
            if self._logger is not None:
                self._logger.exception("Pruning failed")
            app = QApplication.instance()
            if app is not None and app.platformName() != "offscreen":
                QMessageBox.warning(self, tr("msg_error_title"), str(exc))
            return
        self.accept()

    def done(self, result: int) -> None:
        """Detach the bus so a dead dialog never gets stale signals."""
        try:
            self._bus.language_changed.disconnect(self.retranslate_ui)
        except RuntimeError:
            pass  # already disconnected
        super().done(result)
