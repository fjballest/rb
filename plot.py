from PySide6.QtWidgets import QWidget, QVBoxLayout, QGraphicsSimpleTextItem
from PySide6.QtCharts import (
	QChart,
	QChartView,
	QLineSeries,
	QBarCategoryAxis,
	QValueAxis,
)
from PySide6.QtGui import QPainter, QFont
from PySide6.QtCore import Qt, QMargins, QTimer
import sys
from PySide6.QtWidgets import QApplication, QMainWindow

from PySide6.QtWidgets import QWidget


class AspectRatioWidget(QWidget):
	def __init__(self, child: QWidget, aspect_ratio: float, parent=None):
		super().__init__(parent)
		self._child = child
		self._aspect_ratio = aspect_ratio
		self._child.setParent(self)

	def resizeEvent(self, event):
		w = self.width()
		h = self.height()

		# Compute the largest size that fits while preserving aspect ratio
		if w / h > self._aspect_ratio:
			new_h = h
			new_w = int(h * self._aspect_ratio)
		else:
			new_w = w
			new_h = int(w / self._aspect_ratio)

		x = (w - new_w) // 2
		y = (h - new_h) // 2

		self._child.setGeometry(x, y, new_w, new_h)

class XYPlotWidget(QWidget):
	def __init__(self, title: str = "", aspect_ratio: float | None = None, parent=None):
		super().__init__(parent)

		# --- Chart & series ---
		self._series = QLineSeries()
		self._chart = QChart()
		self._chart.addSeries(self._series)
		self._chart.setTitle(title)
		self._chart.legend().hide()

		# --- Axes ---
		self._axis_x = QBarCategoryAxis()
		self._axis_y = QValueAxis()
		#self._axis_y.setLabelFormat("%f")

		self._chart.addAxis(self._axis_x, Qt.AlignBottom)
		self._chart.addAxis(self._axis_y, Qt.AlignLeft)

		self._series.attachAxis(self._axis_x)
		self._series.attachAxis(self._axis_y)

		# --- View ---
		self._view = QChartView(self._chart)
		self._view.setRenderHint(QPainter.Antialiasing)
		# --- Optional aspect ratio enforcement ---
		if aspect_ratio is not None:
			self._container = AspectRatioWidget(self._view, aspect_ratio, self)
			layout = QVBoxLayout(self)
			layout.setContentsMargins(0, 0, 0, 0)
			layout.addWidget(self._container)
		else:
			layout = QVBoxLayout(self)
			layout.setContentsMargins(0, 0, 0, 0)
			layout.addWidget(self._view)
		self._last_value_label = QGraphicsSimpleTextItem(self._chart)
		font = QFont()
		font.setPointSize(11)
		font.setBold(True)
		self._last_value_label.setFont(font)
		self._last_value_label.setVisible(False)
		#self._chart.scene().addItem(self._last_value_label)

	# ----------------------------
	# Public API
	# ----------------------------

	def set_title(self, title: str):
		self._chart.setTitle(title)

	def set_data(self, x_labels: list[str], y_values: list[float]):
		"""
		Update the plot with new data.
		x_labels: list of strings
		y_values: list of floats
		"""

		if len(x_labels) != len(y_values):
			raise ValueError("x_labels and y_values must have the same length")

		# Clear old data
		self._series.clear()
		self._axis_x.clear()

		# Append new data
		for i, y in enumerate(y_values):
			self._series.append(i, y)

		self._axis_x.append(x_labels)
		# Auto-rotate labels if crowded
		if len(x_labels) > 8:
			self._axis_x.setLabelsAngle(90)
			self._chart.setMargins(QMargins(10, 10, 10, 30))
		else:
			self._axis_x.setLabelsAngle(0)
			self._chart.setMargins(QMargins(10, 10, 10, 10))
		self._axis_x.setGridLineVisible(False)
		# Auto-scale Y axis
		if y_values:
			min_y = min(y_values)
			max_y = max(y_values)
			padding = (max_y - min_y) * 0.1 or 1.0
			self._axis_y.setRange(min_y - padding, max_y + padding)

		if y_values:
			self._last_value_label.setText(f"{y_values[-1]:.1f}")
			QTimer.singleShot(0, self._update_last_value_label)

	def _update_last_value_label(self):
		if self._series.count() == 0:
			self._last_value_label.setVisible(False)
			return

		last_point = self._series.at(self._series.count() - 1)

		pos = self._chart.mapToPosition(last_point, self._series)

		self._last_value_label.setPos(
			pos.x() - 40,
			pos.y() - 12
		)
		self._last_value_label.setVisible(True)


	def resizeEvent(self, event):
		super().resizeEvent(event)
		self._update_last_value_label()

class MainWindow(QMainWindow):
	def __init__(self):
		super().__init__()

		plot = XYPlotWidget("Weekly Metrics", aspect_ratio=4/3)
		plot.set_data(
			["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
			[1.2, 3.4, 2.1, 4.8, 3.0, 2.7, 3.9],
		)

		self.setCentralWidget(plot)
		self.resize(700, 400)


if __name__ == "__main__":
	app = QApplication(sys.argv)
	w = MainWindow()
	w.show()
	sys.exit(app.exec())