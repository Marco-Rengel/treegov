"""Reports panel for Phase 2.4 (skeleton). Clean room."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from frontend_v3.i18n import language_bus, tr


class ReportsPanel(QWidget):
    """Placeholder reports panel (Phase 2.4 skeleton).

    Mirrors the MetricsPanel pattern: a single centered label, live
    retranslation via language_bus, and a no-op refresh() slot kept for
    API compatibility with the main window refresh cycle.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        language_bus.language_changed.connect(self.retranslate_ui)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addStretch(1)
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        layout.addWidget(self._label)
        layout.addStretch(1)
        self.retranslate_ui()

    def refresh(self) -> None:
        """Placeholder: nothing to refresh until Phase 2.4 lands."""
        pass

    def retranslate_ui(self) -> None:
        self._label.setText(tr("reports_no_model"))
