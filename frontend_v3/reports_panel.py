"""Reports panel: partition/view controls, gains table and classification matrix.

Clean room: presentation only (PySide6 + i18n). All analytical payloads
arrive as plain dicts prepared by MainWindow from the backend DTOs.
"""

from __future__ import annotations

import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from frontend_v3.i18n import language_bus, tr


def _fmt(value, digits: int = 4) -> str:
    """Format a scalar for display: em dash for None, g-format for floats."""
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}g}"
    return str(value)


class ReportsPanel(QWidget):
    """Gains table + classification matrix with partition/view controls.

    Public API consumed by MainWindow:
      - set_session_available(train=, oos=, oot=): enable partition choices.
      - set_gains_table(dto) / set_classification_matrix(dto): push payloads.
      - current_partition/view/threshold/n_buckets: read the control state.
      - refresh() / retranslate_ui(): repaint cycle (retranslate calls
        refresh, and every dynamic text is resolved with tr() at paint time).

    The panel holds no analytical state beyond the last DTOs received; all
    control changes travel outward through the class signals.
    """

    partition_changed = Signal(str)
    view_changed = Signal(str, int)
    threshold_changed = Signal(float)
    refresh_requested = Signal()

    _PARTITION_CODES: tuple[str, ...] = ("train", "oos", "oot")
    _HEADER_KEYS: tuple[str, ...] = (
        "reports_col_label",
        "reports_col_pd",
        "reports_col_n",
        "reports_col_n_good",
        "reports_col_n_bad",
        "reports_col_bad_rate",
        "reports_col_n_cum",
        "reports_col_n_bad_cum",
        "reports_col_bad_rate_cum",
        "reports_col_lift_cum",
        "reports_col_n_decum",
        "reports_col_n_bad_decum",
        "reports_col_bad_rate_decum",
    )
    _ROW_FIELDS: tuple[str, ...] = (
        "label",
        "pd",
        "n",
        "n_good",
        "n_bad",
        "bad_rate",
        "n_cum",
        "n_bad_cum",
        "bad_rate_cum",
        "lift_cum",
        "n_decum",
        "n_bad_decum",
        "bad_rate_decum",
    )
    _SUMMARY_FIELDS: tuple[str, ...] = (
        "n_total",
        "n_good",
        "n_bad",
        "bad_rate_global",
        "ks",
        "auc",
        "gini",
    )
    _MATRIX_METRICS: tuple[str, ...] = (
        "precision",
        "recall",
        "f1",
        "bad_capture_rate",
        "accuracy",
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._gains: dict | None = None
        self._matrix: dict | None = None
        self._partitions: tuple[str, ...] = ("oos",)
        self._build_ui()
        language_bus.language_changed.connect(self.retranslate_ui)
        self.retranslate_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # Top control row.
        top = QHBoxLayout()
        self._partition_label = QLabel(self)
        top.addWidget(self._partition_label)
        self._partition_combo = QComboBox(self)
        self._partition_combo.setObjectName("reportsPartition")
        for code in self._PARTITION_CODES:
            self._partition_combo.addItem(
                tr(f"reports_partition_{code}"), userData=code
            )
        top.addWidget(self._partition_combo)
        top.addSpacing(12)

        self._view_label = QLabel(self)
        top.addWidget(self._view_label)
        self._view_combo = QComboBox(self)
        self._view_combo.setObjectName("reportsView")
        self._view_combo.addItem(tr("reports_view_terminal"), userData="leaf")
        self._view_combo.addItem(tr("reports_view_bucket"), userData="bucket")
        top.addWidget(self._view_combo)
        top.addSpacing(12)

        self._buckets_label = QLabel(self)
        top.addWidget(self._buckets_label)
        self._buckets_spin = QSpinBox(self)
        self._buckets_spin.setObjectName("reportsBuckets")
        self._buckets_spin.setRange(2, 100)
        self._buckets_spin.setValue(10)
        top.addWidget(self._buckets_spin)
        top.addSpacing(12)

        self._threshold_label = QLabel(self)
        top.addWidget(self._threshold_label)
        self._threshold_spin = QDoubleSpinBox(self)
        self._threshold_spin.setObjectName("reportsThreshold")
        self._threshold_spin.setRange(0.0, 1.0)
        self._threshold_spin.setDecimals(4)
        self._threshold_spin.setSingleStep(0.05)
        self._threshold_spin.setValue(0.5)
        top.addWidget(self._threshold_spin)

        top.addStretch(1)
        self._refresh_button = QPushButton(self)
        self._refresh_button.setObjectName("reportsRefresh")
        top.addWidget(self._refresh_button)
        self._export_button = QPushButton(self)
        self._export_button.setObjectName("reportsExport")
        self._export_button.clicked.connect(self._on_export_clicked)
        top.addWidget(self._export_button)
        main_layout.addLayout(top)

        # Empty-state message (visible only when no payload has arrived).
        self._empty_label = QLabel(self)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        main_layout.addWidget(self._empty_label)

        # Splitter: gains table on top, summary + matrix below.
        splitter = QSplitter(Qt.Orientation.Vertical, self)
        self._table = QTableWidget(self)
        self._table.setObjectName("reportsGainsTable")
        self._table.setColumnCount(len(self._HEADER_KEYS))
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.setSortingEnabled(True)
        # Ctrl+C copia la seleccion (o toda la tabla si no hay seleccion)
        # como TSV al portapapeles. Contexto WidgetWithChildren para no
        # secuestrar Ctrl+C de otros widgets de la misma ventana.
        self._copy_shortcut = QShortcut(
            QKeySequence.StandardKey.Copy,
            self._table,
            context=Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
        self._copy_shortcut.activated.connect(
            lambda: self._copy_selection_to_clipboard(self._table)
        )
        splitter.addWidget(self._table)
        splitter.addWidget(self._build_bottom_section())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter, 1)

        # Control wiring.
        self._partition_combo.currentIndexChanged.connect(self._on_partition_changed)
        self._view_combo.currentIndexChanged.connect(self._on_view_changed)
        self._buckets_spin.valueChanged.connect(self._on_buckets_changed)
        self._threshold_spin.valueChanged.connect(self.threshold_changed.emit)
        self._refresh_button.clicked.connect(self.refresh_requested.emit)

        # Initial control state: terminal-node view disables the buckets spinbox.
        self._buckets_spin.setEnabled(self.current_view() == "bucket")
        self.set_session_available(train=False, oos=True, oot=False)

    def _build_bottom_section(self) -> QWidget:
        bottom = QWidget(self)
        layout = QHBoxLayout(bottom)

        # (a) Summary block: card-styled frame with a single rich-HTML
        # label (no rigid per-metric grid). The stylesheet uses palette
        # roles (base/mid) so the card follows the active theme in both
        # light and dark mode.
        summary = QFrame(bottom)
        summary.setFrameShape(QFrame.Shape.StyledPanel)
        # QLabel hereda de QFrame: el selector QSS va por objectName
        # (regla QFrame#summaryCard en styles.qss, con tokens de tema) o
        # cada etiqueta hija heredaria borde/fondo propios. La tarjeta
        # NO se estira verticalmente: Preferred/Maximum la ajusta al
        # contenido; los margenes internos los da el layout.
        summary.setObjectName("summaryCard")
        summary.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(15, 15, 15, 15)
        self._summary_title = QLabel(summary)
        summary_layout.addWidget(self._summary_title)
        self._lbl_summary_text = QLabel(summary)
        self._lbl_summary_text.setWordWrap(True)
        summary_layout.addWidget(self._lbl_summary_text)
        self._per_class_label = QLabel(summary)
        self._per_class_label.setWordWrap(True)
        self._per_class_label.setVisible(False)
        summary_layout.addWidget(self._per_class_label)
        summary_layout.addStretch(1)
        layout.addWidget(summary, 1)

        # (b) Classification matrix: real 2x2 QTableWidget + quality
        # metric rows. Las reglas globales QTableWidget / QHeaderView::
        # section de styles.qss aportan grid, cabeceras elevadas en
        # negrita y colores de tema en claro/oscuro (sin estilos inline).
        # Cabeceras de fila/columna = Real good/bad x Predicted good/bad
        # (textos en retranslate_ui). Celdas centradas, min 100 px/col.
        matrix = QWidget(bottom)
        matrix_layout = QVBoxLayout(matrix)
        self._matrix_title = QLabel(matrix)
        matrix_layout.addWidget(self._matrix_title)
        self._matrix_table = QTableWidget(2, 2, matrix)
        self._matrix_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self._matrix_table.setSelectionMode(
            QTableWidget.SelectionMode.NoSelection
        )
        self._matrix_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._matrix_table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._matrix_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        h_header = self._matrix_table.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        h_header.setMinimumSectionSize(100)
        self._matrix_table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._matrix_cells: dict[str, QTableWidgetItem] = {}
        for key, row, col in (
            ("tn", 0, 0),
            ("fp", 0, 1),
            ("fn", 1, 0),
            ("tp", 1, 1),
        ):
            cell = QTableWidgetItem("")
            cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._matrix_table.setItem(row, col, cell)
            self._matrix_cells[key] = cell
        matrix_layout.addWidget(self._matrix_table)
        self._matrix_warning = QLabel(matrix)
        self._matrix_warning.setObjectName("lblMatrixWarning")
        self._matrix_warning.setWordWrap(True)
        self._matrix_warning.setStyleSheet("color: #ED6C02; font-weight: bold;")
        self._matrix_warning.setVisible(False)
        matrix_layout.addWidget(self._matrix_warning)
        self._matrix_rows: dict[str, QLabel] = {}
        for key in self._MATRIX_METRICS:
            metric_label = QLabel(matrix)
            matrix_layout.addWidget(metric_label)
            self._matrix_rows[key] = metric_label
        matrix_layout.addStretch(1)
        layout.addWidget(matrix, 1)

        return bottom

    # --------------------------------------------------------------- Slots
    def _on_partition_changed(self, _index: int) -> None:
        self.partition_changed.emit(self.current_partition())

    def _on_view_changed(self, _index: int) -> None:
        self._buckets_spin.setEnabled(self.current_view() == "bucket")
        self.view_changed.emit(self.current_view(), self.current_n_buckets())

    def _on_buckets_changed(self, value: int) -> None:
        self.view_changed.emit(self.current_view(), value)

    @staticmethod
    def _copy_selection_to_clipboard(table: QTableWidget) -> None:
        """Copia la seleccion al portapapeles como TSV (pega directa en Excel/Word).

        Sin seleccion previa, copia toda la tabla. La primera linea
        lleva las cabeceras de las columnas implicadas; cada fila es una
        linea con valores separados por tabuladores. Generico: sirve para
        cualquier QTableWidget pasado como argumento. Static (25/10/2026):
        lo comparten ReportsPanel y PruneDialog (REGLA CRITICA 4.1.1 del
        Design System) sin acoplamiento de instancia. Nota: el fallback
        "toda la tabla" NO usa selectAll(): en tablas con
        SelectionMode.SingleSelection (PruneDialog) selectAll() no
        selecciona nada; se iteran las celdas directamente.
        """
        indexes = table.selectedIndexes()
        if indexes:
            pairs = [(i.row(), i.column()) for i in indexes]
        else:
            pairs = [
                (r, c)
                for r in range(table.rowCount())
                for c in range(table.columnCount())
            ]
        if not pairs:
            return
        cols = sorted({c for _r, c in pairs})
        rows: dict[int, dict[int, str]] = {}
        for r, c in pairs:
            item = table.item(r, c)
            rows.setdefault(r, {})[c] = item.text() if item is not None else ""
        header = table.horizontalHeaderItem
        lines = [
            "\t".join(
                header(c).text() if header(c) is not None else "" for c in cols
            )
        ]
        for row_index in sorted(rows):
            lines.append("\t".join(rows[row_index].get(c, "") for c in cols))
        QApplication.clipboard().setText("\n".join(lines))

    # ---------------------------------------------------------- Public API
    def set_session_available(self, *, train: bool, oos: bool, oot: bool) -> None:
        """Enable the available partition choices; never emits a signal."""
        flags = {"train": train, "oos": oos, "oot": oot}
        self._partitions = tuple(c for c in self._PARTITION_CODES if flags[c])
        model = self._partition_combo.model()
        self._partition_combo.blockSignals(True)
        for row in range(self._partition_combo.count()):
            item = model.item(row)
            if item is not None:
                item.setEnabled(
                    self._partition_combo.itemData(row) in self._partitions
                )
        if self._partitions and self.current_partition() not in self._partitions:
            index = self._partition_combo.findData(self._partitions[0])
            if index >= 0:
                self._partition_combo.setCurrentIndex(index)
        self._partition_combo.blockSignals(False)

    def set_gains_table(self, dto: dict | None) -> None:
        """Store the gains-table payload and repaint."""
        self._gains = dto
        self.refresh()

    def set_classification_matrix(self, dto: dict | None) -> None:
        """Store the classification-matrix payload and repaint."""
        self._matrix = dto
        self.refresh()

    def current_partition(self) -> str:
        data = self._partition_combo.currentData()
        return str(data) if data is not None else "oos"

    def current_threshold(self) -> float:
        return float(self._threshold_spin.value())

    def current_view(self) -> str:
        data = self._view_combo.currentData()
        return str(data) if data is not None else "leaf"

    def current_n_buckets(self) -> int:
        return int(self._buckets_spin.value())

    def refresh(self) -> None:
        """Repaint table, summary and matrix from the stored DTOs."""
        self._repaint_gains()
        self._repaint_summary()
        self._repaint_matrix()
        has_data = self._gains is not None or self._matrix is not None
        self._empty_label.setText(tr("reports_no_model"))
        self._empty_label.setVisible(not has_data)

    def _on_export_clicked(self) -> None:
        """Export button: build HTML and open preview dialog (or warn if empty)."""
        if self._gains is None and self._matrix is None:
            QMessageBox.information(
                self, tr("reports_export_title"), tr("reports_export_empty")
            )
            return
        html = self._build_report_html()
        self._open_export_dialog(html)

    def _build_report_html(self) -> str:
        """Self-contained HTML report: header + gains table + summary + matrix.

        No external assets. Inline CSS in <style>. Values come from
        self._gains / self._matrix (dicts from the backend DTOs).
        """
        gains = self._gains or {}
        matrix = self._matrix or {}
        partition = self.current_partition()
        threshold = self.current_threshold()

        def esc(value) -> str:
            return html.escape(_fmt(value), quote=True)

        parts: list[str] = []
        parts.append("<!DOCTYPE html><html><head><meta charset='utf-8'>")
        parts.append(f"<title>{esc(tr('reports_export_doc_title'))}</title>")
        parts.append(
            "<style>"
            "body{font-family:sans-serif;margin:24px;color:#222;}"
            "h1{font-size:18px;margin:0 0 8px 0;}"
            "h2{font-size:14px;margin:20px 0 8px 0;}"
            "p.meta{color:#666;margin:0 0 12px 0;font-size:12px;}"
            "table{border-collapse:collapse;margin-bottom:16px;}"
            "th,td{border:1px solid #ccc;padding:4px 8px;font-size:12px;text-align:right;}"
            "th{background:#f0f0f0;font-weight:bold;text-align:center;}"
            "td.label{text-align:left;font-weight:bold;}"
            "</style></head><body>"
        )
        parts.append(f"<h1>{esc(tr('reports_export_doc_title'))}</h1>")
        parts.append(
            f"<p class='meta'>{esc(tr('reports_partition_label'))} "
            f"<b>{esc(partition)}</b> &middot; "
            f"{esc(tr('reports_threshold_label'))} <b>{esc(threshold)}</b></p>"
        )

        # Gains table
        rows = gains.get("rows") or []
        parts.append(f"<h2>{esc(tr('reports_summary_title'))}</h2>")
        parts.append("<table><thead><tr>")
        for key in self._HEADER_KEYS:
            parts.append(f"<th>{esc(tr(key))}</th>")
        parts.append("</tr></thead><tbody>")
        for row in rows:
            parts.append("<tr>")
            for i, field in enumerate(self._ROW_FIELDS):
                cell_class = " class='label'" if field == "label" else ""
                parts.append(f"<td{cell_class}>{esc(row.get(field))}</td>")
            parts.append("</tr>")
        parts.append("</tbody></table>")

        # Summary metrics
        parts.append(f"<h2>{esc(tr('reports_summary_title'))}</h2>")
        parts.append("<table><tbody>")
        for key in self._SUMMARY_FIELDS:
            parts.append(
                f"<tr><td class='label'>{esc(tr('reports_sum_' + key))}</td>"
                f"<td>{esc(gains.get(key))}</td></tr>"
            )
        parts.append("</tbody></table>")

        # Classification matrix
        parts.append(f"<h2>{esc(tr('reports_matrix_title'))}</h2>")
        parts.append("<table><tbody>")
        parts.append(
            f"<tr><td class='label'></td>"
            f"<td>{esc(tr('reports_matrix_pred_good'))}</td>"
            f"<td>{esc(tr('reports_matrix_pred_bad'))}</td></tr>"
        )
        parts.append(
            f"<tr><td class='label'>{esc(tr('reports_matrix_actual_good'))}</td>"
            f"<td>{esc(matrix.get('tn'))}</td>"
            f"<td>{esc(matrix.get('fp'))}</td></tr>"
        )
        parts.append(
            f"<tr><td class='label'>{esc(tr('reports_matrix_actual_bad'))}</td>"
            f"<td>{esc(matrix.get('fn'))}</td>"
            f"<td>{esc(matrix.get('tp'))}</td></tr>"
        )
        parts.append("</tbody></table>")

        parts.append("<table><tbody>")
        for key in self._MATRIX_METRICS:
            parts.append(
                f"<tr><td class='label'>{esc(tr('reports_matrix_' + key))}</td>"
                f"<td>{esc(matrix.get(key))}</td></tr>"
            )
        parts.append("</tbody></table>")

        parts.append("</body></html>")
        return "".join(parts)

    def _open_export_dialog(self, html: str) -> None:
        """Modal dialog with HTML preview and Save-as / Close buttons."""
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("reports_export_title"))
        dialog.resize(900, 650)
        layout = QVBoxLayout(dialog)

        hint = QLabel(tr("reports_export_hint"))
        layout.addWidget(hint)

        browser = QTextBrowser(dialog)
        browser.setOpenExternalLinks(False)
        browser.setHtml(html)
        layout.addWidget(browser, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        save_btn = QPushButton(tr("reports_export_save"), dialog)
        close_btn = QPushButton(tr("reports_export_close"), dialog)
        save_btn.clicked.connect(lambda: self._save_html_to_file(dialog, html))
        close_btn.clicked.connect(dialog.accept)
        buttons.addWidget(save_btn)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        dialog.exec()

    def _save_html_to_file(self, parent: QDialog, html: str) -> None:
        """Ask for a path and write the HTML file. Errors -> QMessageBox."""
        path, _filt = QFileDialog.getSaveFileName(
            parent,
            tr("reports_export_save"),
            tr("reports_export_default_filename"),
            tr("reports_export_file_filter"),
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(html)
        except OSError as exc:
            QMessageBox.warning(
                parent,
                tr("reports_export_error_title"),
                tr("reports_export_error_body").format(error=exc),
            )
            return
        QMessageBox.information(
            parent,
            tr("reports_export_saved_title"),
            tr("reports_export_saved_body").format(path=path),
        )

    def retranslate_ui(self) -> None:
        """Reassign every static text, then repaint (refresh uses tr())."""
        self._partition_label.setText(tr("reports_partition_label"))
        self._view_label.setText(tr("reports_view_label"))
        self._buckets_label.setText(tr("reports_buckets_label"))
        self._threshold_label.setText(tr("reports_threshold_label"))
        self._refresh_button.setText(tr("reports_refresh"))
        self._export_button.setText(tr("reports_export_html"))
        self._summary_title.setText(tr("reports_summary_title"))
        self._matrix_table.setHorizontalHeaderLabels([
            tr("reports_matrix_pred_good"),
            tr("reports_matrix_pred_bad"),
        ])
        self._matrix_table.setVerticalHeaderLabels([
            tr("reports_matrix_actual_good"),
            tr("reports_matrix_actual_bad"),
        ])

        self._retranslate_combo(
            self._partition_combo,
            {code: tr(f"reports_partition_{code}") for code in self._PARTITION_CODES},
        )
        self._retranslate_combo(
            self._view_combo,
            {"leaf": tr("reports_view_terminal"), "bucket": tr("reports_view_bucket")},
        )

        # Repaint warning if needed
        if hasattr(self, "_matrix_warning"):
            self._repaint_matrix()
        self._table.setHorizontalHeaderLabels([tr(key) for key in self._HEADER_KEYS])
        self.refresh()

    # ------------------------------------------------------------ Painting
    def _repaint_gains(self) -> None:
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        rows = (self._gains or {}).get("rows") or []
        self._table.setRowCount(len(rows))
        numeric_alignment = (
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        for row_index, row in enumerate(rows):
            for col, field in enumerate(self._ROW_FIELDS):
                item = QTableWidgetItem(_fmt(row.get(field)))
                if field != "label":
                    item.setTextAlignment(numeric_alignment)
                self._table.setItem(row_index, col, item)
        self._table.setSortingEnabled(True)

    def _repaint_summary(self) -> None:
        """Rich-HTML summary: bold labels + values on two wrapped lines
        (totals row, then rates/quality metrics). _fmt(None) -> em dash,
        so an empty payload renders as dashes, never crashes."""
        gains = self._gains or {}

        def _chip(key: str) -> str:
            return f"<b>{tr('reports_sum_' + key)}:</b> {_fmt(gains.get(key))}"

        fields = self._SUMMARY_FIELDS
        line1 = " &nbsp;&nbsp; ".join(_chip(k) for k in fields[:3])
        line2 = " &nbsp;&nbsp; ".join(_chip(k) for k in fields[3:])
        html = f"{line1}<br>{line2}"
        self._lbl_summary_text.setText(html)
        # QLabel con wordWrap + rich text negocia mal su altura en el
        # layout (la tarjeta, con policy Maximum, recorta la 2a linea):
        # alto minimo = nº de lineas de diseno (separadas por <br>).
        fm = self._lbl_summary_text.fontMetrics()
        n_lines = html.count("<br>") + 1
        self._lbl_summary_text.setMinimumHeight(n_lines * fm.lineSpacing())
        n_per_class = gains.get("n_per_class_global") or ()
        if n_per_class:
            values = ", ".join(str(int(v)) for v in n_per_class)
            self._per_class_label.setText(
                f"{tr('reports_sum_n_per_class')}: ({values})"
            )
            self._per_class_label.setVisible(True)
        else:
            self._per_class_label.setVisible(False)

    def _repaint_matrix(self) -> None:
        matrix = self._matrix or {}
        # Titulo dinamico: en K>2 el DTO trae confusion_matrix poblada;
        # en K=2 llega vacia y se usa el titulo binario clasico.
        cm = matrix.get("confusion_matrix") or ()
        if cm:
            self._matrix_title.setText(tr("reports_matrix_title_multiclass"))
        else:
            self._matrix_title.setText(tr("reports_matrix_title"))
        for key, cell in self._matrix_cells.items():
            cell.setText(_fmt(matrix.get(key)))
        # La tabla abraza su contenido en ambas dimensiones: sin hueco
        # vacio bajo la 2a fila ni a la derecha de la 2a columna (el
        # sizeHint de un QAbstractScrollArea seria ~256x192 siempre).
        self._matrix_table.setMaximumHeight(
            self._matrix_table.horizontalHeader().sizeHint().height()
            + sum(self._matrix_table.rowHeight(r) for r in range(2))
            + 2 * self._matrix_table.frameWidth()
        )
        self._matrix_table.setMaximumWidth(
            self._matrix_table.verticalHeader().sizeHint().width()
            + sum(self._matrix_table.columnWidth(c) for c in range(2))
            + 2 * self._matrix_table.frameWidth()
        )
        for key, label in self._matrix_rows.items():
            label.setText(f"{tr('reports_matrix_' + key)}: {_fmt(matrix.get(key))}")
        recall = matrix.get("recall")
        if recall is not None and recall == 0.0:
            self._matrix_warning.setText(tr("reports_warning_recall_zero"))
            self._matrix_warning.setVisible(True)
        else:
            self._matrix_warning.setVisible(False)

    # ------------------------------------------------------------- Helpers
    @staticmethod
    def _retranslate_combo(combo: QComboBox, texts: dict[str, str]) -> None:
        """Rewrite combo item texts in place, keeping data and selection."""
        combo.blockSignals(True)
        for row in range(combo.count()):
            code = combo.itemData(row)
            if code in texts:
                combo.setItemText(row, texts[code])
        combo.blockSignals(False)
