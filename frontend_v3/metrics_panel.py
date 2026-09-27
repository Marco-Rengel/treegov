"""Metrics panel for OOS/OOT validation (Phase 2.3 skeleton).

Clean room: no analytical logic. Pure Qt presentation layer.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from frontend_v3.i18n import language_bus, tr


class MetricsPanel(QWidget):
    """Placeholder panel for Out-of-Sample / Out-of-Time metrics."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        language_bus.language_changed.connect(self.retranslate_ui)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        layout.addStretch(1)
        layout.addWidget(self._label)
        layout.addStretch(1)
        self.retranslate_ui()

    def refresh(self) -> None:
        """Placeholder for future OOS/OOT metric computation."""
        pass

    def retranslate_ui(self) -> None:
        self._label.setText(tr("oos_oot_no_model"))