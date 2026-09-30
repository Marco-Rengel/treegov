"""Metrics panel for OOS/OOT validation (Phase 2.3.e.4).

Consumidor del DTO de Session.get_oos_oot_report(): renderiza las
secciones OOS (metricas de discriminacion/calibracion) y OOT (banderas
de estabilidad PSI / caida de Gini / CSI) como presentacion Qt pura.

Clean room: no analytical logic. Pure Qt presentation layer.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from frontend_v3.i18n import language_bus, tr

_STATUS_TO_QSS: dict[str, str] = {
    "STABLE": "ok",
    "NONE": "ok",
    "MODERATE": "warn",
    "WARNING": "warn",
    "UNSTABLE": "crit",
    "CRITICAL": "crit",
    "UNDETERMINED": "unknown",
}

_STATUS_TO_I18N: dict[str, str] = {
    "STABLE": "status_stable",
    "NONE": "status_none",
    "MODERATE": "status_moderate",
    "WARNING": "status_warning",
    "UNSTABLE": "status_unstable",
    "CRITICAL": "status_critical",
    "UNDETERMINED": "status_undetermined",
}


def _fmt(value, digits: int = 4) -> str:
    """Formato seguro: '—' si None, %g si float, str en otro caso."""
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}g}"
    return str(value)


class MetricsPanel(QWidget):
    """Panel de metricas Out-of-Sample / Out-of-Time (consumidor del DTO)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._report: dict | None = None
        self._layout = QVBoxLayout(self)
        language_bus.language_changed.connect(self.retranslate_ui)
        self.refresh()

    def set_report(self, dto: dict | None) -> None:
        """Recibe el DTO de Session.get_oos_oot_report() y repinta."""
        self._report = dto
        self.refresh()

    def refresh(self) -> None:
        """Reconstruye el contenido del panel desde el DTO actual."""
        self._clear_content()
        if self._report is None:
            self._add_empty(tr("oos_oot_no_model"))
            return
        oos = self._report.get("oos")
        oot = self._report.get("oot")
        if oos is None and oot is None:
            self._add_empty(tr("oos_oot_no_model"))
            return
        if oos is not None:
            self._build_oos_section(oos)
        if oot is not None:
            self._build_oot_section(oot)
        self._layout.addStretch(1)

    def retranslate_ui(self) -> None:
        self.refresh()

    # ------------------------------------------------------------------
    # Helpers privados de construccion
    # ------------------------------------------------------------------

    def _clear_content(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _add_empty(self, text: str) -> None:
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        self._layout.addStretch(1)
        self._layout.addWidget(label)
        self._layout.addStretch(1)

    def _add_section_header(self, text: str) -> None:
        header = QLabel(text)
        header.setObjectName("panelTitle")
        self._layout.addWidget(header)

    def _add_row(self, label_key: str, value: str) -> None:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(QLabel(tr(label_key)))
        row_layout.addStretch(1)
        row_layout.addWidget(QLabel(value))
        self._layout.addWidget(row)

    def _add_badge_row(self, label_key: str, code: str) -> None:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(QLabel(tr(label_key)))
        row_layout.addStretch(1)
        row_layout.addWidget(self._make_badge(code))
        self._layout.addWidget(row)

    def _make_badge(self, code: str) -> QLabel:
        i18n_key = _STATUS_TO_I18N.get(code, "status_undetermined")
        qss_status = _STATUS_TO_QSS.get(code, "unknown")
        badge = QLabel(tr(i18n_key))
        badge.setProperty("status", qss_status)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return badge

    # ------------------------------------------------------------------
    # Secciones del DTO
    # ------------------------------------------------------------------

    def _build_oos_section(self, oos: dict) -> None:
        self._add_section_header(tr("oos_section_title"))
        self._add_row("oos_label_sample", _fmt(oos.get("n_test")))
        self._add_row("oos_label_gini", _fmt(oos.get("gini")))
        self._add_row("oos_label_ks", _fmt(oos.get("ks")))
        self._add_row("oos_label_brier", _fmt(oos.get("brier")))
        self._add_row("oos_label_brier_skill", _fmt(oos.get("brier_skill")))
        self._add_row("oos_label_hl", _fmt(oos.get("hl_p")))

    def _build_oot_section(self, oot: dict) -> None:
        self._add_section_header(tr("oot_section_title"))
        psi = oot.get("psi") or {}
        self._add_badge_row("oot_label_psi", psi.get("flag", "UNDETERMINED"))
        drop = oot.get("drop") or {}
        self._add_badge_row(
            "oot_label_gini_drop", drop.get("alert_oot", "UNDETERMINED")
        )
        csi = oot.get("csi") or ()
        if isinstance(csi, (list, tuple)) and len(csi) > 0:
            valid = [c for c in csi if isinstance(c, dict)]
            if valid:
                worst = max(valid, key=lambda c: float(c.get("csi") or 0.0))
                self._add_badge_row(
                    "oot_label_csi", worst.get("flag", "UNDETERMINED")
                )
