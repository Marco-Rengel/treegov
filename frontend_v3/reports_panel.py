"""Reports panel: partition/view controls, gains table and classification matrix.

Clean room: presentation only (PySide6 + i18n). All analytical payloads
arrive as plain dicts prepared by MainWindow from the backend DTOs.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
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
        self._view_combo.addItem(tr("reports_view_leaf"), userData="leaf")
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
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.setSortingEnabled(True)
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

        # Initial control state: leaf view disables the buckets spinbox.
        self._buckets_spin.setEnabled(self.current_view() == "bucket")
        self.set_session_available(train=False, oos=True, oot=False)

    def _build_bottom_section(self) -> QWidget:
        bottom = QWidget(self)
        layout = QHBoxLayout(bottom)

        # (a) Summary block: title + one label per metric row.
        summary = QWidget(bottom)
        summary_layout = QVBoxLayout(summary)
        self._summary_title = QLabel(summary)
        summary_layout.addWidget(self._summary_title)
        self._summary_rows: dict[str, QLabel] = {}
        for key in self._SUMMARY_FIELDS:
            row_label = QLabel(summary)
            summary_layout.addWidget(row_label)
            self._summary_rows[key] = row_label
        summary_layout.addStretch(1)
        layout.addWidget(summary, 1)

        # (b) Classification matrix: 3x3 grid + quality metric rows.
        matrix = QWidget(bottom)
        matrix_layout = QVBoxLayout(matrix)
        self._matrix_title = QLabel(matrix)
        matrix_layout.addWidget(self._matrix_title)
        grid = QGridLayout()
        self._matrix_corner = QLabel(matrix)
        self._matrix_pred_good = QLabel(matrix)
        self._matrix_pred_bad = QLabel(matrix)
        self._matrix_actual_good = QLabel(matrix)
        self._matrix_actual_bad = QLabel(matrix)
        for header in (
            self._matrix_corner,
            self._matrix_pred_good,
            self._matrix_pred_bad,
            self._matrix_actual_good,
            self._matrix_actual_bad,
        ):
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(self._matrix_corner, 0, 0)
        grid.addWidget(self._matrix_pred_good, 0, 1)
        grid.addWidget(self._matrix_pred_bad, 0, 2)
        grid.addWidget(self._matrix_actual_good, 1, 0)
        grid.addWidget(self._matrix_actual_bad, 2, 0)
        self._matrix_cells: dict[str, QLabel] = {}
        for key, row, col in (
            ("tn", 1, 1),
            ("fp", 1, 2),
            ("fn", 2, 1),
            ("tp", 2, 2),
        ):
            cell = QLabel(matrix)
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(cell, row, col)
            self._matrix_cells[key] = cell
        matrix_layout.addLayout(grid)
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

    def retranslate_ui(self) -> None:
        """Reassign every static text, then repaint (refresh uses tr())."""
        self._partition_label.setText(tr("reports_partition_label"))
        self._view_label.setText(tr("reports_view_label"))
        self._buckets_label.setText(tr("reports_buckets_label"))
        self._threshold_label.setText(tr("reports_threshold_label"))
        self._refresh_button.setText(tr("reports_refresh"))
        self._summary_title.setText(tr("reports_summary_title"))
        self._matrix_title.setText(tr("reports_matrix_title"))
        self._matrix_corner.setText(tr("reports_matrix_corner"))
        self._matrix_pred_good.setText(tr("reports_matrix_pred_good"))
        self._matrix_pred_bad.setText(tr("reports_matrix_pred_bad"))
        self._matrix_actual_good.setText(tr("reports_matrix_actual_good"))
        self._matrix_actual_bad.setText(tr("reports_matrix_actual_bad"))

        self._retranslate_combo(
            self._partition_combo,
            {code: tr(f"reports_partition_{code}") for code in self._PARTITION_CODES},
        )
        self._retranslate_combo(
            self._view_combo,
            {"leaf": tr("reports_view_leaf"), "bucket": tr("reports_view_bucket")},
        )

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
        gains = self._gains or {}
        for key, label in self._summary_rows.items():
            label.setText(f"{tr('reports_sum_' + key)}: {_fmt(gains.get(key))}")

    def _repaint_matrix(self) -> None:
        matrix = self._matrix or {}
        for key, cell in self._matrix_cells.items():
            cell.setText(_fmt(matrix.get(key)))
        for key, label in self._matrix_rows.items():
            label.setText(f"{tr('reports_matrix_' + key)}: {_fmt(matrix.get(key))}")

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
