from PySide6.QtWidgets import (
	QMainWindow, QLabel, QScrollArea,
	QPushButton, QWidget, QVBoxLayout,
	QHBoxLayout, QSizePolicy
)
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtCore import Qt, QEvent, QTimer, Signal
import os

DCLICKZOOM = 2.0	# each zooming double click doubles the size
from data import canonlist

class ImageViewer(QMainWindow):
	moved = Signal(int)	# asks to show the next (+1) or previous (-1) trade
	jumped = Signal(bool)	# asks to show the first (False) or last (True) trade

	def __init__(self, file, parent=None, x=1400, y=1024, desc=''):
		super().__init__(parent)
		if desc is None:
			desc=''
		self.desc = desc
		self.file_path = ""
		self.files = file
		self.fileno = 0
		if len(file) > 0 and file[0] != "":
			file = canonlist(file)
			self.file_path = file[0]
		self.notes = QLabel(self.desc)
		self.notes.setWordWrap(True)
		# always three lines high, so the buttons beside it don't move with the notes
		fm = self.notes.fontMetrics()
		m = self.notes.contentsMargins()
		self.notes.setFixedHeight(3*fm.lineSpacing() + m.top() + m.bottom() + 2)
		self.notes.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
		self.notes.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
		self.updateTitle()
		self.resize(x, y)
		self.scale_factor = 1.0
		self.original_pixmap = None
		# how a new image is scaled: "fit" the window, "real" size, or "zoom" keeps scale_factor
		self.mode = "fit"
		self.dstep = 0		# double clicks: zoom in, zoom in again, then fit


		# --- Buttons ---
		self.prev_button = QPushButton("Prev")
		self.next_button = QPushButton("Next")
		self.more_button = QPushButton("More")
		self.zoom_in_button = QPushButton("Zoom +")
		self.zoom_out_button = QPushButton("Zoom -")
		self.fit_button = QPushButton("Fit")
		self.actual_button = QPushButton("Real Size")
		self.preview_button = QPushButton("OS View")

		self.prev_button.clicked.connect(lambda: self.moveTo(-1))
		self.next_button.clicked.connect(lambda: self.moveTo(1))
		self.more_button.clicked.connect(lambda: self.more())
		self.zoom_in_button.clicked.connect(lambda: self.zoom(1.25))
		self.zoom_out_button.clicked.connect(lambda: self.zoom(0.8))
		self.fit_button.clicked.connect(self.enable_fit_mode)
		self.actual_button.clicked.connect(self.actual_size)
		self.preview_button.clicked.connect(self.preview)

		# keys: left/right go through the graphs of the trade, up/down to the
		# previous/next trade, home/end to the first/last one. Shortcuts, so the
		# scroll area and the buttons don't take the arrows for themselves
		for key, fn in ((Qt.Key.Key_Left, self.less), (Qt.Key.Key_Right, self.more),
				(Qt.Key.Key_Up, lambda: self.moveTo(-1)), (Qt.Key.Key_Down, lambda: self.moveTo(1)),
				(Qt.Key.Key_Home, lambda: self.jumpTo(False)), (Qt.Key.Key_End, lambda: self.jumpTo(True))):
			QShortcut(QKeySequence(key), self, fn)

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
		button_layout.addWidget(self.prev_button)
		button_layout.addWidget(self.next_button)
		button_layout.addWidget(self.more_button)
		button_layout.addWidget(self.actual_button)
		button_layout.addWidget(self.fit_button)
		button_layout.addWidget(self.zoom_in_button)
		button_layout.addWidget(self.zoom_out_button)
		button_layout.addWidget(self.preview_button)
		button_layout.addWidget(self.notes, 1)

		container = QWidget()
		layout = QVBoxLayout(container)
		layout.addLayout(button_layout)
		layout.addWidget(self.scroll_area)
		self.setCentralWidget(container)
		self.setimage(self.files)
		# fit again once shown, when the scroll area has its real size
		QTimer.singleShot(0, self.enable_fit_mode)

	def updateTitle(self):
		if len(self.files) < 2:
			self.setWindowTitle(self.file_path)
		else:
			nb = f" ({self.fileno+1} of {len(self.files)})"
			self.setWindowTitle(self.file_path+nb)
		self.notes.setText(self.desc)
		self.notes.setToolTip(self.desc)	# all of it, when it needs more than three lines

	def preview(self):
		if self.file_path is not None:
			os.system(f"open {self.file_path}")

	def setimage(self, files, no=0, desc=None):
		"""show files[no]; desc None keeps the notes of the trade being shown"""
		if desc is not None:
			self.desc = desc
		self.files = files
		no = no % len(files) if files else 0
		self.fileno = no
		file = ""
		if len(files) > 0:
			file = files[no]
		self.file_path = file
		self.notes.setText(self.desc)
		self.notes.setToolTip(self.desc)
		pixmap = QPixmap(self.file_path)
		self.original_pixmap = None if pixmap.isNull() else pixmap
		if self.original_pixmap is None:
			self.image_label.clear()
			self.image_label.setText(f"no image {self.file_path}")
			return
		if self.mode == "fit":
			self.update_fit_scale()
		elif self.mode == "real":
			self.scale_factor = 1.0
		self.update_image()

	def more(self):
		self.setimage(self.files, self.fileno+1)
		self.updateTitle()

	def less(self):
		self.setimage(self.files, self.fileno-1)
		self.updateTitle()

	def moveTo(self, delta):
		self.moved.emit(delta)
		self.updateTitle()

	def jumpTo(self, last):
		self.jumped.emit(last)
		self.updateTitle()

	# ---------- Zoom controls ----------
	def zoom(self, factor):
		if not self.original_pixmap:
			return
		self.mode = "zoom"
		self.scale_factor *= factor
		self.update_image()

	def zoomat(self, factor, pos):
		"""zoom by factor keeping the image point at viewport pos where it is"""
		if not self.original_pixmap:
			return
		h = self.scroll_area.horizontalScrollBar()
		v = self.scroll_area.verticalScrollBar()
		old = self.scale_factor
		x = (pos.x() + h.value()) / old
		y = (pos.y() + v.value()) / old
		self.zoom(factor)
		h.setValue(round(x * self.scale_factor - pos.x()))
		v.setValue(round(y * self.scale_factor - pos.y()))

	def doubleclick(self, pos):
		"""cycle: zoom in, zoom in again, back to fit"""
		if self.dstep < 2:
			self.dstep += 1
			self.zoomat(DCLICKZOOM, pos)
		else:
			self.enable_fit_mode()

	def actual_size(self):
		if not self.original_pixmap:
			return
		self.mode = "real"
		self.scale_factor = 1.0
		self.update_image()

	def enable_fit_mode(self, x=None, y=None):
		if not self.original_pixmap:
			return
		self.mode = "fit"
		self.dstep = 0
		self.update_fit_scale(x = x, y = y)
		self.update_image()

	# ---------- Fit logic ----------
	def update_fit_scale(self, x=None, y=None):
		# the size without scroll bars, which go away once the image fits
		viewport = self.scroll_area.maximumViewportSize()
		img = self.original_pixmap.size()
		if x is None or y is None:
			x = viewport.width()
			y = viewport.height()
		self.scale_factor = min(
			x / img.width(),
			y / img.height()
		)

	def resizeEvent(self, event):
		super().resizeEvent(event)
		if self.mode == "fit" and self.original_pixmap:
			self.update_fit_scale()
			self.update_image()

	# ---------- Image update ----------
	def update_image(self):
		if self.original_pixmap:
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
			if event.type() == QEvent.Type.MouseButtonDblClick and \
					event.button() == Qt.MouseButton.LeftButton:
				self.doubleclick(event.position().toPoint())
				return True
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

