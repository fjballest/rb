from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCharts import (
	QChart,
	QChartView,
	QBarSeries,
	QStackedBarSeries,
	QBarSet,
	QBarCategoryAxis,
	QValueAxis,
)
from PySide6.QtGui import QPainter, QColor
from PySide6.QtCore import Qt, QMargins


class XYStackBarWidget(QWidget):
	def __init__(self, labels: list[str], title: str = "", aspect_ratio: float | None = None, parent=None, colors=None):
		super().__init__(parent)

		# --- Chart ---
		self._chart = QChart()
		self._chart.setTitle(title)
		self._chart.legend().hide()
		self._labels = labels

		# --- Series ---
		self._bar_sets = [QBarSet(i) for i in labels]
		self._series = QStackedBarSeries()
		for bs in self._bar_sets:
			self._series.append(bs)
		self._chart.addSeries(self._series)
		self._series.setLabelsPosition(QBarSeries.LabelsPosition.LabelsOutsideEnd)
		self._series.setLabelsVisible(True)
		for i, bs in enumerate(self._bar_sets):
			bs.setLabelColor(QColor("black"))
			if colors:
				bs.setColor(QColor(colors[i]))
		# --- Axes ---
		self._axis_x = QBarCategoryAxis()
		self._axis_y = QValueAxis()
		self._axis_y.setLabelFormat("%.2f")

		self._chart.addAxis(self._axis_x, Qt.AlignmentFlag.AlignBottom)
		self._chart.addAxis(self._axis_y, Qt.AlignmentFlag.AlignLeft)
		self._series.attachAxis(self._axis_x)
		self._series.attachAxis(self._axis_y)

		# Disable vertical grid lines
		self._axis_x.setGridLineVisible(False)
		self._axis_x.setMinorGridLineVisible(False)

		# --- View ---
		self._view = QChartView(self._chart)
		self._view.setRenderHint(QPainter.RenderHint.Antialiasing)

		# --- Layout (with optional aspect ratio) ---
		layout = QVBoxLayout(self)
		layout.setContentsMargins(0, 0, 0, 0)
		layout.addWidget(self._view)

	# ----------------------------
	# Public API
	# ----------------------------

	def set_title(self, title: str):
		self._chart.setTitle(title)

	def set_data(self, x_labels: list[str], y_values: list[list[float]]):
		if len(y_values) != len(self._bar_sets):
			raise ValueError("wrong number of y series")
		for ys in y_values:
			if len(x_labels) != len(ys):
				raise ValueError("x_labels and y_values must have the same length")

		self._axis_x.clear()

		for i, ys in enumerate(y_values):
			self._bar_sets[i].remove(0, self._bar_sets[i].count())
			for y in ys:
				self._bar_sets[i].append(int(y))
		# Downsample / rotate labels if crowded
		if len(x_labels) > 10 or (len(x_labels)>0 and len(x_labels[0]) > 5):
			#display_labels = self._downsample_labels(x_labels, max_labels=6)
			display_labels = x_labels
			self._axis_x.setLabelsAngle(90)
			self._chart.setMargins(QMargins(10, 10, 10, 30))
		else:
			display_labels = x_labels
			self._axis_x.setLabelsAngle(0)
			self._chart.setMargins(QMargins(10, 10, 10, 10))

		self._axis_x.append(display_labels)

		# Auto-scale Y axis
		if y_values:
			min_y = min(y_values[0])
			max_y = max(y_values[0])
			for ys in y_values[1:]:
				min_y1 = min(ys)
				min_y = min(min_y, min_y1)
				max_y1 = max(ys)
				max_y += max(max_y, max_y1)
			min_y = 0
			padding = (max_y - min_y) * 0.1 or 1.0
			self._axis_y.setRange(min_y - padding, max_y + padding)

	# ----------------------------
	# Helpers
	# ----------------------------

	@staticmethod
	def _downsample_labels(labels: list[str], max_labels: int):
		if len(labels) <= max_labels:
			return labels

		step = max(1, len(labels) // max_labels)
		return [
			label if i % step == 0 else ""
			for i, label in enumerate(labels)
		]
