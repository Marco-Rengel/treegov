"""Gains charts (Phase 3.12.g): native QPainter views of the gains DTO.

Three small QGraphicsView widgets show cumulative gains, response rate
and lift. `GainsCharts.set_data()` only reads the existing DTO: X is
`n_cum / n_total`; cumulative Y is `n_bad_cum / n_bad_total`; response Y
is `bad_rate`; lift Y is `lift_cum`. There is no analytical logic beyond
those presentation ratios from docs/3.12_design_analysis_workspace.md
§5.5. Benefit and ROI remain explicitly out of scope (§5.1).

Colors come from the active QPalette and texts from i18n, so the views
repaint correctly after theme or language changes. No new dependency.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPalette, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)

from frontend_v3.i18n import tr

__all__ = ["GainsCharts"]

_KINDS = ("cumulative", "response", "lift")


def _finite(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _ratio(numerator, denominator: float | None) -> float | None:
    value = _finite(numerator)
    if value is None or denominator is None or denominator <= 0.0:
        return None
    return value / denominator


class _GainsChartView(QGraphicsView):
    """QGraphicsView whose paintEvent draws one gains curve with QPainter."""

    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._kind = kind
        self._points: list[tuple[float, float]] = []
        self._reference = 1.0
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setInteractive(False)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumHeight(190)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

    def set_points(
        self, points: list[tuple[float, float]], reference: float
    ) -> None:
        self._points = points
        self._reference = reference
        self.viewport().update()

    def changeEvent(self, event: QEvent) -> None:
        if event.type() in (
            QEvent.Type.PaletteChange,
            QEvent.Type.StyleChange,
        ):
            self.viewport().update()
        super().changeEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().paintEvent(event)
        if not self._points:
            return
        painter = QPainter(self.viewport())
        try:
            self._paint(painter)
        finally:
            painter.end()

    def _paint(self, painter: QPainter) -> None:
        palette = self.palette()
        text_color = palette.color(QPalette.ColorRole.WindowText)
        axis_color = palette.color(QPalette.ColorRole.Mid)
        curve_color = palette.color(QPalette.ColorRole.Highlight)

        width = float(self.viewport().width())
        height = float(self.viewport().height())
        left, right = 46.0, max(47.0, width - 12.0)
        top, bottom = 30.0, max(31.0, height - 36.0)
        if right <= left or bottom <= top:
            return

        painter.setPen(text_color)
        painter.drawText(
            QRectF(6.0, 3.0, width - 12.0, 22.0),
            Qt.AlignmentFlag.AlignCenter,
            tr(f"gains_chart_title_{self._kind}"),
        )

        values = [point[1] for point in self._points]
        if self._kind != "cumulative":
            values.append(self._reference)
        else:
            values.append(1.0)
        y_max = max(1.0, max(values, default=1.0)) * 1.05

        def map_point(x: float, y: float) -> QPointF:
            px = left + max(0.0, min(1.0, x)) * (right - left)
            py = bottom - max(0.0, min(y_max, y)) / y_max * (bottom - top)
            return QPointF(px, py)

        painter.setPen(QPen(axis_color, 1.0))
        painter.drawLine(map_point(0.0, 0.0), map_point(1.0, 0.0))
        painter.drawLine(map_point(0.0, 0.0), map_point(0.0, y_max))

        # Referencia: diagonal en ganancias, tasa global en respuesta y
        # 100% (lift=1) en elevacion.
        painter.setPen(QPen(axis_color, 1.0, Qt.PenStyle.DashLine))
        if self._kind == "cumulative":
            painter.drawLine(map_point(0.0, 0.0), map_point(1.0, 1.0))
        else:
            reference = self._reference if self._kind == "response" else 1.0
            painter.drawLine(
                map_point(0.0, reference), map_point(1.0, reference)
            )

        points = list(self._points)
        if self._kind == "cumulative":
            points.insert(0, (0.0, 0.0))
        polygon = QPolygonF([map_point(x, y) for x, y in points])
        painter.setPen(QPen(curve_color, 2.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolyline(polygon)
        painter.setBrush(curve_color)
        for x, y in points:
            painter.drawEllipse(map_point(x, y), 2.5, 2.5)

        painter.setPen(text_color)
        painter.drawText(
            QRectF(2.0, top - 8.0, left - 6.0, 16.0),
            Qt.AlignmentFlag.AlignRight,
            f"{y_max:.3g}",
        )
        painter.drawText(
            QRectF(2.0, bottom - 8.0, left - 6.0, 16.0),
            Qt.AlignmentFlag.AlignRight,
            "0",
        )
        for x, label in ((0.0, "0%"), (0.5, "50%"), (1.0, "100%")):
            center = map_point(x, 0.0).x()
            painter.drawText(
                QRectF(center - 24.0, bottom + 3.0, 48.0, 15.0),
                Qt.AlignmentFlag.AlignCenter,
                label,
            )
        painter.drawText(
            QRectF(left, height - 16.0, right - left, 14.0),
            Qt.AlignmentFlag.AlignCenter,
            tr("gains_chart_axis_percentile"),
        )


class GainsCharts(QWidget):
    """Fila con las curvas cumulative/response/lift del DTO de ganancias."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._series: dict[str, list[tuple[float, float]]] = {
            kind: [] for kind in _KINDS
        }
        self._references = {"cumulative": 1.0, "response": 0.0, "lift": 1.0}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._empty_label = QLabel(self)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_label, 1)
        self._charts: dict[str, _GainsChartView] = {}
        for kind in _KINDS:
            chart = _GainsChartView(kind, self)
            chart.setObjectName(f"gainsChart_{kind}")
            self._charts[kind] = chart
            layout.addWidget(chart, 1)
        self.retranslate_ui()
        self.set_data(None)

    def set_data(self, gains_dto: dict | None) -> None:
        """Extrae las tres series del DTO; sin filas oculta los graficos."""
        rows = gains_dto.get("rows") if isinstance(gains_dto, dict) else None
        if not isinstance(rows, (list, tuple)) or not rows:
            self._set_empty()
            return
        n_total = _finite(gains_dto.get("n_total"))
        n_bad_total = _finite(gains_dto.get("n_bad"))
        # Sin eventos no hay curva de ganancias: evita cualquier division
        # por cero y muestra el mismo estado vacio que una tabla ausente.
        if n_bad_total is None or n_bad_total <= 0.0:
            self._set_empty()
            return
        global_rate = _finite(gains_dto.get("bad_rate_global")) or 0.0
        series: dict[str, list[tuple[float, float]]] = {
            kind: [] for kind in _KINDS
        }
        for row in rows:
            if not isinstance(row, dict):
                continue
            x = _finite(row.get("pop_cum_pct"))
            if x is None:
                x = _ratio(row.get("n_cum"), n_total)
            if x is None:
                continue
            cumulative = _finite(row.get("bad_cum_pct"))
            if cumulative is None:
                cumulative = _ratio(row.get("n_bad_cum"), n_bad_total)
            response = _finite(row.get("bad_rate"))
            lift = _finite(row.get("lift_cum"))
            if cumulative is not None:
                series["cumulative"].append((x, cumulative))
            if response is not None:
                series["response"].append((x, response))
            if lift is not None:
                series["lift"].append((x, lift))
        if not any(series.values()):
            self._set_empty()
            return

        self._series = series
        self._references = {
            "cumulative": 1.0,
            "response": global_rate,
            "lift": 1.0,
        }
        self._empty_label.setVisible(False)
        for kind, chart in self._charts.items():
            chart.set_points(series[kind], self._references[kind])
            chart.setVisible(bool(series[kind]))

    def retranslate_ui(self) -> None:
        self._empty_label.setText(tr("gains_chart_empty"))
        for chart in self._charts.values():
            chart.viewport().update()

    def _set_empty(self) -> None:
        self._series = {kind: [] for kind in _KINDS}
        self._empty_label.setText(tr("gains_chart_empty"))
        self._empty_label.setVisible(True)
        for chart in self._charts.values():
            chart.set_points([], self._references[chart._kind])
            chart.setVisible(False)
