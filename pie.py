from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCharts import (
	QChart,
	QChartView,
	QBarSeries,
	QPieSeries,
	QBarSet,
	QBarCategoryAxis,
	QValueAxis,
)
from PySide6.QtGui import QPainter, QColor
from PySide6.QtCore import Qt, QMargins


class PieWidget(QWidget):
	def __init__(self, labels: list[str], vals: list[float],
			title: str = "",
			aspect_ratio: float | None = None, parent=None, colors=None):
		super().__init__(parent)

		# --- Chart ---
		self._chart = QChart()
		self._chart.setTitle(title)
		self._chart.legend().hide()
		self._labels = labels
		self._vals = vals

		# --- Series ---
		self._series = QPieSeries()
		self._series.setHoleSize(0.3)
		for i, lbl in enumerate(labels):
			slice = self._series.append(lbl, vals[i])
			slice.setLabelVisible()
			slice.setLabel(f"{vals[i]:.0f} {lbl}")
			if colors is not None:
				slice.setColor(colors[i])
		self._chart.addSeries(self._series)
		self._series.setLabelsVisible(True)

		# --- View ---
		self._view = QChartView(self._chart)
		self._view.setRenderHint(QPainter.Antialiasing)

		# --- Layout (with optional aspect ratio) ---
		if aspect_ratio is not None:
			self._container = AspectRatioWidget(self._view, aspect_ratio, self)
			layout = QVBoxLayout(self)
			layout.setContentsMargins(0, 0, 0, 0)
			layout.addWidget(self._container)
		else:
			layout = QVBoxLayout(self)
			layout.setContentsMargins(0, 0, 0, 0)
			layout.addWidget(self._view)

	# ----------------------------
	# Public API
	# ----------------------------

	def set_title(self, title: str):
		self._chart.setTitle(title)

	def set_data(self, labels: list[str], vals: list[list[float]]):
		self._labels = labels
		self._vals = vals
		self._series.clear()
		for i, lbl in enumerate(labels):
			self._series.append(lbl, vals[i])
