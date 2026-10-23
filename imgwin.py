from PySide6.QtWidgets import (
	QMainWindow, QLabel, QPushButton, QWidget, QVBoxLayout,
	QHBoxLayout, QSizePolicy, QMessageBox
)
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtCore import Qt, QTimer, Signal
import json
import os

from data import canonlist
from viewer import ImageView
from drawbar import DrawBar

# the drawings on a graph are kept next to it, with its name and this extension:
# trade12dax.png -> trade12dax.drw
DRAWEXT = ".drw"

def drawpath(graph):
	return os.path.splitext(graph)[0] + DRAWEXT

def readdrawing(graph):
	"""the drawing saved for the graph, or None"""
	try:
		with open(drawpath(graph), encoding="utf-8") as f:
			d = json.load(f)
		return d if isinstance(d, dict) else None
	except (OSError, ValueError):
		return None

def savedrawing(graph, data):
	"""write the drawing of the graph; None or no shapes removes the file"""
	p = drawpath(graph)
	if not data or not data.get("shapes"):
		if os.path.exists(p):
			os.remove(p)
		return
	tmp = p + ".tmp"
	with open(tmp, "w", encoding="utf-8") as f:
		json.dump(data, f, ensure_ascii=False, indent=1)
	os.replace(tmp, p)

# the view's keys: left/right go through the graphs of the trade, up/down to the
# previous/next trade, home/end to the first/last one
NAVKEYS = {Qt.Key.Key_Left: "less", Qt.Key.Key_Right: "more", Qt.Key.Key_Up: "prev",
	Qt.Key.Key_Down: "next", Qt.Key.Key_Home: "first", Qt.Key.Key_End: "last"}

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
		self.pending = {}	# graph path -> its drawing not saved yet (None: no drawings)
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
		self.resize(x, y)

		# --- the graph, with its drawings ---
		self.view = ImageView()
		self.view.navkeys = NAVKEYS
		self.view.navigate.connect(self.navigate)
		self.view.drawchanged.connect(self.drawchanged)
		self.drawbar = DrawBar(self.view, self)
		self.addToolBar(self.drawbar)

		# --- Buttons ---
		self.prev_button = QPushButton("Prev")
		self.next_button = QPushButton("Next")
		self.more_button = QPushButton("More")
		self.zoom_in_button = QPushButton("Zoom +")
		self.zoom_out_button = QPushButton("Zoom -")
		self.fit_button = QPushButton("Fit")
		self.actual_button = QPushButton("Real Size")
		self.preview_button = QPushButton("OS View")
		self.save_button = QPushButton("Save")
		self.save_button.setToolTip("save the drawings (⌘S)")

		self.prev_button.clicked.connect(lambda: self.moveTo(-1))
		self.next_button.clicked.connect(lambda: self.moveTo(1))
		self.more_button.clicked.connect(lambda: self.more())
		self.zoom_in_button.clicked.connect(lambda: self.zoom(1.25))
		self.zoom_out_button.clicked.connect(lambda: self.zoom(0.8))
		self.fit_button.clicked.connect(self.enable_fit_mode)
		self.actual_button.clicked.connect(self.actual_size)
		self.preview_button.clicked.connect(self.preview)
		self.save_button.clicked.connect(self.savedrawings)
		self.saveact = QAction("Save", self)
		self.saveact.setShortcut(QKeySequence.StandardKey.Save)
		self.saveact.triggered.connect(self.savedrawings)
		self.addAction(self.saveact)

		# --- Layout ---
		button_layout = QHBoxLayout()
		for b in (self.prev_button, self.next_button, self.more_button, self.actual_button,
				self.fit_button, self.zoom_in_button, self.zoom_out_button, self.preview_button,
				self.save_button):
			b.setFocusPolicy(Qt.FocusPolicy.NoFocus)	# the keys go to the graph
			button_layout.addWidget(b)
		button_layout.addWidget(self.notes, 1)

		container = QWidget()
		layout = QVBoxLayout(container)
		layout.addLayout(button_layout)
		layout.addWidget(self.view)
		self.setCentralWidget(container)
		self.setimage(self.files)
		self.view.setFocus()
		# fit again once shown, when the view has its real size
		QTimer.singleShot(0, self.enable_fit_mode)

	def updateTitle(self):
		t = self.file_path
		if len(self.files) >= 2:
			t += f" ({self.fileno+1} of {len(self.files)})"
		if self.pending:
			t += " (unsaved)"
		self.setWindowTitle(t)
		self.save_button.setEnabled(bool(self.pending))
		self.notes.setText(self.desc)
		self.notes.setToolTip(self.desc)	# all of it, when it needs more than three lines

	def preview(self):
		if self.file_path is not None:
			os.system(f"open {self.file_path}")

	def setimage(self, files, no=0, desc=None):
		"""show files[no]; desc None keeps the notes of the trade being shown"""
		self.view.commitedit()	# a text box being edited goes with its graph
		if desc is not None:
			self.desc = desc
		self.files = files
		no = no % len(files) if files else 0
		self.fileno = no
		file = ""
		if len(files) > 0:
			file = files[no]
		self.file_path = file
		self.view.setimage(file, self.drawingof(file) if file else None)
		if not self.view.hasimage():
			self.view.scene().addText(f"no image {self.file_path}")
		self.updateTitle()

	def navigate(self, what):
		{"less": self.less, "more": self.more, "prev": lambda: self.moveTo(-1),
			"next": lambda: self.moveTo(1), "first": lambda: self.jumpTo(False),
			"last": lambda: self.jumpTo(True)}[what]()

	def more(self):
		self.setimage(self.files, self.fileno+1)

	def less(self):
		self.setimage(self.files, self.fileno-1)

	def moveTo(self, delta):
		self.moved.emit(delta)
		self.updateTitle()

	def jumpTo(self, last):
		self.jumped.emit(last)
		self.updateTitle()

	# ---------- Zoom controls ----------
	def zoom(self, factor):
		self.view.zoom(factor)

	def actual_size(self):
		self.view.realsize()

	def enable_fit_mode(self):
		self.view.fit()

	# ---------- Drawings ----------
	def drawchanged(self):
		"""the drawing of the graph shown changed: it is pending until saved"""
		if self.view.loading or not self.view.hasimage():
			return
		path = self.view.path
		data = self.view.drawingdata()
		if data == readdrawing(path):
			self.pending.pop(path, None)	# back as saved
		else:
			self.pending[path] = data
		self.updateTitle()

	def drawingof(self, path):
		"""the drawing of the graph: the one not saved yet, or the one in its file"""
		if path in self.pending:
			return self.pending[path]
		return readdrawing(path)

	def savedrawings(self):
		"""write the drawings not saved yet; False if one could not be"""
		self.view.commitedit()
		ok = True
		for path, data in list(self.pending.items()):
			try:
				savedrawing(path, data)
				self.pending.pop(path)
			except OSError as x:
				ok = False
				QMessageBox.warning(self, "Save", f"Can't save the drawing of {path}: {x}")
		self.updateTitle()
		return ok

	def keepdrawings(self, why):
		"""ask what to do with the drawings not saved, before why.
		False if the user cancels"""
		self.view.commitedit()
		if not self.pending:
			return True
		n = len(self.pending)
		qm = QMessageBox
		r = qm.question(self, "Unsaved drawings",
			f"The drawings of {n} graph{'s' if n > 1 else ''} are not saved. Save them before {why}?",
			qm.StandardButton.Save | qm.StandardButton.Discard | qm.StandardButton.Cancel, qm.StandardButton.Save)
		if r == qm.StandardButton.Cancel:
			return False
		if r == qm.StandardButton.Save:
			return self.savedrawings()
		self.pending = {}
		self.setimage(self.files, self.fileno)	# as saved
		return True

	def closeEvent(self, ev):
		if not self.keepdrawings("closing the graphs"):
			ev.ignore()
			return
		ev.accept()
