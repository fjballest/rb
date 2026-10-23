#
# the toolbar for drawing on an ImageView: the tools, color, width, undo,
# redo and delete. Shared by DayJournal and pylg's graphics window.
#
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import QColorDialog, QComboBox, QMenu, QToolBar, QToolButton

COLORS = (("Red", "#e53935"), ("Green", "#2e7d32"), ("Blue", "#1e63d6"), ("Orange", "#f57c00"),
	("Purple", "#8e24aa"), ("Black", "#000000"), ("White", "#ffffff"))
WIDTHS = (1.0, 2.0, 3.0, 5.0, 8.0)
TOOLS = (
	("select", "↖ Select", "S", "select, move and delete drawings; drag the image to move around"),
	("pencil", "✎ Pencil", "P", "draw free hand"),
	("line", "╱ Line", "L", "draw a line; shift keeps it horizontal or vertical"),
	("arrow", "➚ Arrow", "A", "draw an arrow; shift keeps it horizontal or vertical"),
	("circle", "◯ Circle", "C", "draw a circle or ellipse"),
	("text", "T Text", "T", "write a text box; double click one to edit it"),
)

def colorswatch(c):
	pm = QPixmap(14, 14)
	pm.fill(QColor(c))
	return QIcon(pm)

class DrawBar(QToolBar):
	def __init__(self, view, parent=None):
		super().__init__("Draw", parent)
		self.view = view
		self.setIconSize(QSize(18, 18))
		self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
		group = QActionGroup(self)
		group.setExclusive(True)
		self.toolacts = {}
		for tool, text, key, tip in TOOLS:
			a = QAction(text, self)
			a.setCheckable(True)
			a.setToolTip(f"{tip} ({key} on the image)")
			a.triggered.connect(lambda _=False, t=tool: self.view.settool(t))
			group.addAction(a)
			self.addAction(a)
			self.toolacts[tool] = a
		self.toolacts["select"].setChecked(True)
		view.toolchanged.connect(self.toolchanged)
		self.addSeparator()
		self.colorbtn = QToolButton(self)
		self.colorbtn.setToolTip("the color for drawing, and for what is selected")
		self.colorbtn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
		cm = QMenu(self.colorbtn)
		for name, c in COLORS:
			a = cm.addAction(colorswatch(c), name)
			a.triggered.connect(lambda _=False, c=c: self.setcolor(c))
		cm.addSeparator()
		cm.addAction("Other…").triggered.connect(self.othercolor)
		self.colorbtn.setMenu(cm)
		self.addWidget(self.colorbtn)
		self.widthbox = QComboBox()
		self.widthbox.setToolTip("the line width, and of the lines selected")
		for w in WIDTHS:
			self.widthbox.addItem(f"{w:g} px", w)
		self.widthbox.setCurrentIndex(WIDTHS.index(view.width) if view.width in WIDTHS else 0)
		self.widthbox.activated.connect(lambda i: self.view.setwidth(self.widthbox.itemData(i)))
		self.addWidget(self.widthbox)
		self.addSeparator()
		u = view.undo
		self.undoact = QAction("Undo", self)
		self.undoact.setShortcut(QKeySequence.StandardKey.Undo)
		self.undoact.triggered.connect(u.undo)
		self.redoact = QAction("Redo", self)
		self.redoact.setShortcut(QKeySequence.StandardKey.Redo)
		self.redoact.triggered.connect(u.redo)
		u.canUndoChanged.connect(self.undoact.setEnabled)
		u.canRedoChanged.connect(self.redoact.setEnabled)
		u.undoTextChanged.connect(self.undotext)
		u.redoTextChanged.connect(self.redotext)
		self.undoact.setEnabled(False)
		self.redoact.setEnabled(False)
		self.delact = QAction("Delete", self)
		self.delact.setToolTip("delete the drawings selected (Del on the image)")
		self.delact.triggered.connect(view.deleteselected)
		for a in (self.undoact, self.redoact, self.delact):
			self.addAction(a)
		view.scene().selectionChanged.connect(self.selchanged)
		self.setcolor(view.color, apply=False)
		self.selchanged()

	def undotext(self, t):
		self.undoact.setToolTip(f"undo {t.lower()}" if t else "undo")

	def redotext(self, t):
		self.redoact.setToolTip(f"redo {t.lower()}" if t else "redo")

	def setcolor(self, c, apply=True):
		if apply:
			self.view.setcolor(c)
		else:
			self.view.color = c
		self.colorbtn.setIcon(colorswatch(c))
		self.colorbtn.setText("Color")

	def othercolor(self):
		c = QColorDialog.getColor(QColor(self.view.color), self, "Drawing color")
		if c.isValid():
			self.setcolor(c.name())

	def toolchanged(self, tool):
		a = self.toolacts.get(tool)
		if a is not None:
			a.setChecked(True)

	def selchanged(self):
		try:
			sel = self.view.scene().selectedItems()
		except RuntimeError:
			return
		self.delact.setEnabled(bool(sel))
