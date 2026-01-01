import sys
from PySide6.QtWidgets import (
	QApplication, QMainWindow, QFileDialog,
	QLabel, QScrollArea, QPushButton,
	QWidget, QVBoxLayout, QHBoxLayout
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QEvent, QTimer
import os
class ImageViewer(QMainWindow):
	def __init__(self, file, parent=None, x=1400, y=1024):
		super().__init__(parent)
		self.file_path = file
		self.setWindowTitle(file)
		self.resize(x, y)
		self.scale_factor = 1.0
		self.original_pixmap = None
		self.fit_mode = False

		# --- Buttons ---
		self.zoom_in_button = QPushButton("Zoom +")
		self.zoom_out_button = QPushButton("Zoom -")
		self.fit_button = QPushButton("Fit")
		self.actual_button = QPushButton("Real Size")
		self.preview_button = QPushButton("OS View")

		self.zoom_in_button.clicked.connect(lambda: self.zoom(1.25))
		self.zoom_out_button.clicked.connect(lambda: self.zoom(0.8))
		self.fit_button.clicked.connect(self.enable_fit_mode)
		self.actual_button.clicked.connect(self.actual_size)
		self.preview_button.clicked.connect(self.preview)

		# --- Image label ---
		self.image_label = QLabel()
		self.image_label.setAlignment(Qt.AlignmentFlag.AlignLeft |
									  Qt.AlignmentFlag.AlignTop)

		# Drag-to-pan state
		self._drag_pos = None

		# --- Scroll area ---
		self.scroll_area = QScrollArea()
		self.scroll_area.setWidget(self.image_label)
		self.scroll_area.setWidgetResizable(True)
		self.scroll_area.viewport().installEventFilter(self)

		# --- Layout ---
		button_layout = QHBoxLayout()
		button_layout.addWidget(self.actual_button)
		button_layout.addWidget(self.fit_button)
		button_layout.addWidget(self.zoom_in_button)
		button_layout.addWidget(self.zoom_out_button)
		button_layout.addWidget(self.preview_button)
		button_layout.addStretch()

		container = QWidget()
		layout = QVBoxLayout(container)
		layout.addLayout(button_layout)
		layout.addWidget(self.scroll_area)
		self.setCentralWidget(container)
		self.setimage(self.file_path)
		QTimer.singleShot(0, lambda: self.enable_fit_mode(x = x, y = y))

	def preview(self):
		if self.file_path is not None:
			os.system(f"open {self.file_path}")

	def setimage(self, file):
		self.file_path = file
		try:
			pixmap = QPixmap(self.file_path)
			if not pixmap.isNull():
				self.original_pixmap = pixmap
		except:
			pass
		self.update_image()

	# ---------- Zoom controls ----------
	def zoom(self, factor):
		if not self.original_pixmap:
			return
		self.fit_mode = False   # 👈 disable auto-fit
		self.scale_factor *= factor
		self.update_image()

	def actual_size(self):
		if not self.original_pixmap:
			return
		self.fit_mode = False
		self.scale_factor = 1.0
		self.update_image()

	def enable_fit_mode(self, x=None, y=None):
		if not self.original_pixmap:
			return
		self.fit_mode = True
		self.update_fit_scale(x = x, y = y)
		self.update_image()

	# ---------- Fit logic ----------
	def update_fit_scale(self, x=None, y=None):
		viewport = self.scroll_area.viewport().size()
		img = self.original_pixmap.size()
		if x is None or y is None:
			x = viewport.width()
			y = viewport.height()
		self.scale_factor = min(
			x / img.width(),
			x / img.height()
		)

	def resizeEvent(self, event):
		super().resizeEvent(event)
		if self.fit_mode and self.original_pixmap:
			self.update_fit_scale()
			self.update_image()

	# ---------- Image update ----------
	def update_image(self):
		scaled = self.original_pixmap.scaled(
			self.original_pixmap.size() * self.scale_factor,
			Qt.AspectRatioMode.KeepAspectRatio,
			Qt.TransformationMode.SmoothTransformation
		)
		self.image_label.setPixmap(scaled)
		self.image_label.adjustSize()

	# ---------- Drag-to-pan ----------
	def eventFilter(self, source, event):
		if source is self.scroll_area.viewport():
			if (event.type() == QEvent.Type.MouseButtonPress and event.buttons() &
					Qt.MouseButton.LeftButton):
				self._drag_pos = event.pos()
				return True

			elif event.type() == QEvent.Type.MouseMove and self._drag_pos is not None:
				delta = event.pos() - self._drag_pos
				self._drag_pos = event.pos()

				self.scroll_area.horizontalScrollBar().setValue(
					self.scroll_area.horizontalScrollBar().value() - delta.x()
				)
				self.scroll_area.verticalScrollBar().setValue(
					self.scroll_area.verticalScrollBar().value() - delta.y()
				)
				return True

			elif event.type() == QEvent.Type.MouseButtonRelease:
				self._drag_pos = None
				return True

		return super().eventFilter(source, event)

