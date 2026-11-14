"""Summary panel (Phase 3.12.e): acta HTML del modelo activo.

Consumidor de `Session.get_summary()` (Fase 3.12.b). El backend compone
el DTO; este widget solo lo recorre, traduce etiquetas y escapa valores
para pintar siete secciones: Modelo, Dataset, Particion, Gobernanza,
Validacion, Intervenciones manuales y Bitacora.

Clean room: cero logica analitica. El modo RESEARCH cambia la
terminologia visible (PD -> Probabilidad / Probability) sin alterar los
datos. `MainWindow` posee la unica conexion al `language_bus` y refresca
el panel tras las transiciones que cambian el acta.
"""

from __future__ import annotations

import html
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from frontend_v3.i18n import tr, tr_term

if TYPE_CHECKING:  # pragma: no cover - typing only
    from backend_v3.session_state import Session

__all__ = ["SummaryPanel"]

_FIELD_I18N: dict[str, str] = {
    "method": "summary_field_method",
    "fingerprint": "summary_field_fingerprint",
    "n_nodes": "summary_field_nodes",
    "n_terminal": "summary_field_terminal",
    "max_depth": "summary_field_max_depth",
    "class_labels": "summary_field_classes",
    "target": "summary_field_target",
    "predictors": "summary_field_predictors",
    "weights_col": "summary_field_weights",
    "population_col": "summary_field_population",
    "cost_matrix": "summary_field_cost_matrix",
    "scheme": "summary_field_scheme",
    "train_frac": "summary_field_train_frac",
    "seed": "summary_field_seed",
    "cv_k": "summary_field_cv_k",
    "n_train": "summary_field_n_train",
    "n_test": "summary_field_n_test",
    "n_oot": "summary_field_n_oot",
    "n_excluded_population": "summary_field_n_excluded_population",
    "apply_jeffreys": "summary_field_apply_jeffreys",
    "pd_floor": "summary_field_pd_floor",
    "min_child_size": "summary_field_min_child_size",
    "min_child_weight": "summary_field_min_child_weight",
    "max_depth_param": "summary_field_max_depth_param",
}

_METRIC_I18N: dict[str, str] = {
    "n_test": "oos_label_sample",
    "auc": "oos_label_auc",
    "gini": "oos_label_gini",
    "ks": "oos_label_ks",
    "pr_auc": "oos_label_pr_auc",
    "brier": "oos_label_brier",
    "brier_skill": "oos_label_brier_skill",
    "hl_p": "oos_label_hl",
    "pd_mean": "oos_label_pd_mean",
    "psi": "oot_label_psi",
    "csi": "oot_label_csi",
    "gini_drop": "oot_label_gini_drop",
}


def _esc(value: Any) -> str:
    """Texto seguro para HTML (los datos del CSV nunca son marcado)."""
    return html.escape(str(value), quote=True)


class SummaryPanel(QWidget):
    """Pestana Resumen: botones de accion + `QTextBrowser` de solo lectura."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session: Session | None = None
        self._summary: dict | None = None
        self._html = ""
        self._mode = "BANKING"
        self._build_ui()
        self.retranslate_ui()

    # ---------------------------------------------------------- Public API

    def set_governance_mode(self, mode: str) -> None:
        """Fija la terminologia BANKING/RESEARCH y repinta el DTO cacheado."""
        self._mode = mode
        self._repaint()

    def refresh(self, session: Session | None) -> None:
        """Lee `session.get_summary()` y reconstruye el HTML."""
        self._session = session
        try:
            summary = session.get_summary() if session is not None else None
        except Exception:
            logging.getLogger(__name__).exception(
                "[summary_panel] fallo al obtener el resumen"
            )
            summary = None
        self._summary = summary if isinstance(summary, dict) else None
        self._repaint()

    def retranslate_ui(self) -> None:
        """Retraduce controles y reconstruye el HTML sin llamar al backend."""
        self._title.setText(tr("summary_title"))
        self._refresh_button.setText(tr("summary_btn_refresh"))
        self._copy_button.setText(tr("summary_btn_copy"))
        self._export_button.setText(tr("summary_btn_export"))
        self._repaint()

    # ------------------------------------------------------------ Internals

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self._title = QLabel(self)
        self._title.setObjectName("panelTitle")
        top.addWidget(self._title)
        top.addStretch(1)
        self._refresh_button = QPushButton(self)
        self._refresh_button.setObjectName("summaryRefresh")
        top.addWidget(self._refresh_button)
        self._copy_button = QPushButton(self)
        self._copy_button.setObjectName("summaryCopy")
        top.addWidget(self._copy_button)
        self._export_button = QPushButton(self)
        self._export_button.setObjectName("summaryExport")
        top.addWidget(self._export_button)
        layout.addLayout(top)

        self._empty_label = QLabel(self)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        layout.addWidget(self._empty_label)

        self._browser = QTextBrowser(self)
        self._browser.setObjectName("summaryText")
        self._browser.setReadOnly(True)
        self._browser.setOpenExternalLinks(False)
        layout.addWidget(self._browser, 1)

        self._refresh_button.clicked.connect(self._refresh_from_session)
        self._copy_button.clicked.connect(self._on_copy_clicked)
        self._export_button.clicked.connect(self._on_export_clicked)

    def _refresh_from_session(self) -> None:
        self.refresh(self._session)

    def _repaint(self) -> None:
        if self._summary is None:
            self._html = ""
            self._browser.clear()
            self._browser.setVisible(False)
            self._empty_label.setText(tr("summary_empty"))
            self._empty_label.setVisible(True)
            self._copy_button.setEnabled(False)
            self._export_button.setEnabled(False)
            return
        self._html = self._build_html(self._summary)
        self._browser.setHtml(self._html)
        self._empty_label.setVisible(False)
        self._browser.setVisible(True)
        self._copy_button.setEnabled(True)
        self._export_button.setEnabled(True)

    def _build_html(self, summary: dict) -> str:
        parts = [
            "<!DOCTYPE html><html><head><meta charset='utf-8'></head>"
            "<body>",
            f"<h2>{_esc(tr('summary_title'))}</h2>",
        ]
        sections = (
            ("summary_section_model", "model", self._field_label),
            ("summary_section_dataset", "dataset", self._field_label),
            ("summary_section_partition", "partition", self._field_label),
            ("summary_section_governance", "governance", self._field_label),
        )
        for title_key, data_key, labeler in sections:
            data = summary.get(data_key)
            parts.append(f"<h3>{_esc(tr(title_key))}</h3>")
            if isinstance(data, dict) and data:
                parts.append(self._render_mapping(data, labeler))
            else:
                parts.append(f"<p>{_esc(tr('summary_none'))}</p>")

        parts.append(f"<h3>{_esc(tr('summary_section_validation'))}</h3>")
        validation = summary.get("validation")
        validation = validation if isinstance(validation, dict) else {}
        for subtitle, key in (
            ("OOS", "oos_metrics"),
            ("OOT", "oot_report"),
            (tr("cv_report_title"), "cv_report"),
        ):
            parts.append(f"<h4>{_esc(subtitle)}</h4>")
            report = validation.get(key)
            if isinstance(report, dict) and report:
                parts.append(self._render_mapping(report, self._metric_label))
            else:
                parts.append(f"<p>{_esc(tr('summary_none'))}</p>")

        parts.append(f"<h3>{_esc(tr('summary_section_overrides'))}</h3>")
        parts.append(self._render_overrides(summary.get("manual_overrides")))
        parts.append(f"<h3>{_esc(tr('summary_section_event_log'))}</h3>")
        parts.append(self._render_event_log(summary.get("event_log")))
        parts.append("</body></html>")
        return "".join(parts)

    def _field_label(self, key: str) -> str:
        i18n_key = _FIELD_I18N.get(key)
        if i18n_key is None:
            return self._fallback_label(key)
        label = tr(i18n_key)
        if key == "pd_floor" and self._mode == "RESEARCH":
            # "PD floor:" / "Piso de PD:" -> modo neutro por gobernanza.
            label = label.replace("PD", tr_term("pd", self._mode))
        return label

    def _metric_label(self, key: str) -> str:
        i18n_key = _METRIC_I18N.get(key)
        label = tr(i18n_key) if i18n_key is not None else key.replace("_", " ")
        if self._mode == "RESEARCH":
            label = label.replace("PD", tr_term("pd", self._mode))
            if key == "n_events":
                label = tr_term("event", self._mode)
            if "bad_rate" in key:
                bad_rate = tr_term("bad_rate", self._mode)
                label = label.replace("Bad rate", bad_rate)
                label = label.replace("Tasa malos", bad_rate)
        if not label.endswith(":"):
            label += ":"
        return label

    @staticmethod
    def _fallback_label(key: str) -> str:
        return key.replace("_", " ").strip().capitalize() + ":"

    def _format_value(self, value: Any) -> str:
        if value is None:
            return tr("summary_none")
        if isinstance(value, bool):
            return tr("summary_yes") if value else tr("summary_no")
        if isinstance(value, float):
            return format(value, ".6g")
        if isinstance(value, (list, tuple)):
            if not value:
                return tr("summary_none")
            return ", ".join(self._format_value(item) for item in value)
        return str(value)

    def _render_mapping(
        self,
        data: dict,
        labeler: Callable[[str], str],
    ) -> str:
        parts = ["<ul>"]
        for raw_key, value in data.items():
            key = str(raw_key)
            label = _esc(labeler(key))
            if isinstance(value, dict):
                parts.append(f"<li><b>{label}</b>")
                parts.append(self._render_mapping(value, labeler))
                parts.append("</li>")
            elif isinstance(value, (list, tuple)) and any(
                isinstance(item, (dict, list, tuple)) for item in value
            ):
                parts.append(f"<li><b>{label}</b><ul>")
                for item in value:
                    if isinstance(item, dict):
                        parts.append(
                            f"<li>{self._render_mapping(item, labeler)}</li>"
                        )
                    else:
                        parts.append(
                            f"<li>{_esc(self._format_value(item))}</li>"
                        )
                parts.append("</ul></li>")
            else:
                parts.append(
                    f"<li>{label} {_esc(self._format_value(value))}</li>"
                )
        parts.append("</ul>")
        return "".join(parts)

    def _render_overrides(self, overrides: Any) -> str:
        if not isinstance(overrides, (list, tuple)) or not overrides:
            return f"<p>{_esc(tr('summary_none'))}</p>"
        parts = ["<ul>"]
        for override in overrides:
            if isinstance(override, (list, tuple)):
                text = " · ".join(str(value) for value in override)
            else:
                text = str(override)
            parts.append(f"<li>{_esc(text)}</li>")
        parts.append("</ul>")
        return "".join(parts)

    def _render_event_log(self, events: Any) -> str:
        if not isinstance(events, (list, tuple)) or not events:
            return f"<p>{_esc(tr('summary_none'))}</p>"
        items = "".join(f"<li>{_esc(event)}</li>" for event in events)
        return f"<ul>{items}</ul>"

    def _on_copy_clicked(self) -> None:
        QApplication.clipboard().setText(self._browser.toPlainText())

    def _on_export_clicked(self) -> None:
        if not self._html:
            return
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            tr("summary_export_title"),
            "treegov_summary.html",
            "HTML (*.html);;Text (*.txt);;All files (*)",
        )
        if path:
            self._export_to_file(path)

    def _export_to_file(self, path: str) -> bool:
        """Guarda HTML (o texto plano si el destino es `.txt`) en UTF-8."""
        content = (
            self._browser.toPlainText()
            if Path(path).suffix.lower() == ".txt"
            else self._html
        )
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(content)
        except OSError as exc:
            QMessageBox.warning(
                self,
                tr("summary_export_title"),
                tr("summary_export_error").format(error=exc),
            )
            return False
        QMessageBox.information(
            self,
            tr("summary_export_title"),
            tr("summary_export_saved").format(path=path),
        )
        return True
