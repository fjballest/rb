#
# the toolbar for drawing on an ImageView: the tools, color, width, undo,
# redo and delete. Shared by DayJournal and pylg's graphics window.
#
import json

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QKeySequence, QPainter, QPixmap
from PySide6.QtWidgets import (
	QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QGridLayout, QLabel, QLayout, QLineEdit,
	QMainWindow, QMenu, QMessageBox, QToolBar, QToolButton, QVBoxLayout, QWidget
)

from drawing import FIBALL, FIBROWS, FIBSETS, RECTSETS, fmtlevels, parselevels

COLORS = (("Red", "#e53935"), ("Green", "#2e7d32"), ("Blue", "#1e63d6"), ("Orange", "#f57c00"),
	("Purple", "#8e24aa"), ("Black", "#000000"), ("White", "#ffffff"))
WIDTHS = (1.0, 2.0, 3.0, 5.0, 8.0)
TEXTSIZES = (10, 12, 14, 16, 18, 22, 28, 36)
TOOLS = (
	("select", "↖ Select", "S", "select, move and delete drawings; drag the image to move around"),
	("pencil", "✎ Pencil", "P", "draw free hand"),
	("line", "╱ Line", "L", "draw a line; shift keeps it horizontal or vertical"),
	("arrow", "➚ Arrow", "A", "draw an arrow; shift keeps it horizontal or vertical"),
	("circle", "◯ Circle", "C", "draw a circle or ellipse"),
	("rect", "▭ Rect", "R", "draw a rectangle; double click one for its fill, middle line and label. "
		"The menu picks a kind of rectangle (BRK, FVG...)"),
	("text", "T Text", "T", "write a text box; double click one to edit it"),
	("fib", "≡ Fib", "F", "draw Fibonacci levels: from the first point (1) to the second (0), then click "
		"where the lines end, or double click on the second point to take them to the right edge; "
		"the right button drops it. The menu picks the levels"),
)

def fibsettings():
	"""where the custom levels are kept, the same for every program using this"""
	return QSettings("fjballest", "drawing")

def customrows():
	"""the rows of the custom levels form, [(on, text)...], and whether the
	diagonal is drawn"""
	st = fibsettings()
	try:
		d = json.loads(str(st.value("customfibrows", "")))
		rows = [(bool(on), str(t)) for on, t in d["rows"]][:FIBROWS]
		diag = bool(d.get("diagonal"))
	except (ValueError, KeyError, TypeError):
		try:	# what was kept before the form: just the levels used
			used = set(parselevels(str(st.value("customfib", ""))))
		except ValueError:
			used = set(FIBALL)
		levels = sorted(set(FIBALL) | used)
		rows = [(l in used, f"{l:g}") for l in levels]
		diag = False
	rows += [(False, "")] * (FIBROWS - len(rows))
	return rows, diag

def rowlevels(rows):
	"""the levels of the rows that are on, sorted; ValueError if one is not
	a number or there are none"""
	return parselevels(" ".join(t for on, t in rows if on and t.strip()))

def customlevels():
	rows, diag = customrows()
	try:
		return rowlevels(rows), diag
	except ValueError:
		return list(FIBALL), diag

class FibDialog(QDialog):
	"""the custom fib levels: FIBROWS levels in two columns, each one with a
	check to use it, and whether to draw the diagonal"""
	def __init__(self, rows, diagonal, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Custom Fib Levels")
		lay = QVBoxLayout(self)
		lay.addWidget(QLabel("The levels checked are drawn: 0 is at the second point, 1 at the first."))
		grid = QGridLayout()
		half = (len(rows) + 1) // 2
		self.checks, self.edits = [], []
		for i, (on, text) in enumerate(rows):
			c = QCheckBox()
			c.setChecked(on)
			e = QLineEdit(text)
			e.setPlaceholderText("level")
			e.setMaximumWidth(90)
			e.textEdited.connect(lambda t, c=c: c.setChecked(bool(t.strip())))
			col = 0 if i < half else 3
			grid.addWidget(c, i % half, col)
			grid.addWidget(e, i % half, col + 1)
			self.checks.append(c)
			self.edits.append(e)
		grid.setColumnMinimumWidth(2, 24)
		grid.setColumnStretch(5, 1)	# the room left goes after the levels
		lay.addLayout(grid)
		self.diagbox = QCheckBox("Draw the diagonal")
		self.diagbox.setToolTip("the dashed line from the first point to the second")
		self.diagbox.setChecked(diagonal)
		lay.addWidget(self.diagbox)
		bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
		bb.accepted.connect(self.accept)
		bb.rejected.connect(self.reject)
		lay.addWidget(bb)

	def rows(self):
		return [(c.isChecked(), e.text().strip()) for c, e in zip(self.checks, self.edits)]

	def diagonal(self):
		return self.diagbox.isChecked()

	def accept(self):
		bad = [t for on, t in self.rows() if on and t]
		bad = [t for t in bad if not isnumber(t)]
		if bad:
			QMessageBox.warning(self, "Fib levels", f"Not a number: {', '.join(bad)}")
			return
		try:
			rowlevels(self.rows())
		except ValueError:
			QMessageBox.warning(self, "Fib levels", "Check at least one level.")
			return
		super().accept()

def isnumber(t):
	try:
		float(t)
		return True
	except ValueError:
		return False

class FloatBar(QWidget):
	"""the window for the drawing bar when it is detached: it stays on top,
	and closing it puts the bar back"""
	def __init__(self, bar, parent):
		super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
		self.bar = bar
		self.setWindowTitle("Draw")
		self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
		lay = QVBoxLayout(self)
		lay.setContentsMargins(2, 2, 2, 2)
		lay.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)	# as wide as all the buttons

	def closeEvent(self, ev):
		ev.ignore()
		self.bar.attach()

def rectswatch(d):
	"""an icon for the rectangle preset d: its fill and border"""
	pm = QPixmap(16, 12)
	c = QColor(d["fill"])
	c.setAlpha(max(d["alpha"], 90))
	pm.fill(c)
	p = QPainter(pm)
	p.setPen(QColor(d["color"]))
	p.drawRect(0, 0, 15, 11)
	p.setPen(QColor(d.get("midcolor") or d["color"]))
	p.drawLine(2, 6, 13, 6)
	p.end()
	return QIcon(pm)

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
		self.floating = None	# the FloatBar while it is detached
		self.home = None		# where it goes back: the QMainWindow or the layout, and where in it
		self.detachact = QAction("⧉", self)
		self.detachact.setCheckable(True)
		self.detachact.setToolTip("detach the drawing tools as a floating bar that stays on top; "
			"click again, or close it, to put it back")
		self.detachact.toggled.connect(lambda on: self.detach() if on else self.attach())
		self.addAction(self.detachact)
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
		self.mkfibmenu()
		self.mkrectmenu()
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
		self.dashbox = QComboBox()
		self.dashbox.setToolTip("the line style, and of the lines selected")
		for text, d in (("━ Solid", "solid"), ("╍ Dashed", "dash"), ("┈ Dotted", "dot")):
			self.dashbox.addItem(text, d)
		self.dashbox.activated.connect(lambda i: self.view.setdash(self.dashbox.itemData(i)))
		self.addWidget(self.dashbox)
		self.sizebox = QComboBox()
		self.sizebox.setToolTip("the text size of text boxes, labels and fib levels, and of the ones selected")
		for z in TEXTSIZES:
			self.sizebox.addItem(f"Aa {z}", float(z))
		size = fibsettings().value("textsize", view.textsize)
		try:
			view.textsize = float(size)
		except (TypeError, ValueError):
			pass
		i = self.sizebox.findData(float(view.textsize))
		self.sizebox.setCurrentIndex(i if i >= 0 else TEXTSIZES.index(16))
		self.sizebox.activated.connect(self.sizepicked)
		self.addWidget(self.sizebox)
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
		self.clearact = QAction("Clear", self)
		self.clearact.setToolTip("delete every drawing on this image (it can be undone)")
		self.clearact.triggered.connect(view.clearall)
		for a in (self.undoact, self.redoact, self.delact, self.clearact):
			self.addAction(a)
		view.scene().selectionChanged.connect(self.selchanged)
		self.setcolor(view.color, apply=False)
		self.selchanged()

	def mkfibmenu(self):
		a = self.toolacts["fib"]
		m = QMenu(self)
		g = QActionGroup(m)
		self.fibacts = {}
		for name, levels in FIBSETS.items():
			x = m.addAction(f"{name}: {fmtlevels(levels)}")
			x.triggered.connect(lambda _=False, n=name: self.setfib(n))
			self.fibacts[name] = x
		x = m.addAction("Custom…")
		x.triggered.connect(lambda _=False: self.setfib("Custom"))
		self.fibacts["Custom"] = x
		for x in self.fibacts.values():
			x.setCheckable(True)
			g.addAction(x)
		a.setMenu(m)
		b = self.widgetForAction(a)
		if b is not None:
			b.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
		self.fibname = "OTE"
		self.fibacts["OTE"].setChecked(True)

	def mkrectmenu(self):
		a = self.toolacts["rect"]
		m = QMenu(self)
		g = QActionGroup(m)
		self.rectacts = {}
		for name in ("Plain",) + tuple(RECTSETS):
			x = m.addAction(name if name != "Plain" else "Plain: just the border")
			if name != "Plain":
				x.setIcon(rectswatch(RECTSETS[name]))
			x.setCheckable(True)
			g.addAction(x)
			x.triggered.connect(lambda _=False, n=name: self.setrect(n))
			self.rectacts[name] = x
		a.setMenu(m)
		b = self.widgetForAction(a)
		if b is not None:
			b.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
		self.rectname = "Plain"
		self.rectacts["Plain"].setChecked(True)

	def setrect(self, name):
		"""draw rectangles of kind name (Plain or one of RECTSETS); the ones
		selected change to it"""
		self.rectname = name
		self.rectacts[name].setChecked(True)
		self.view.setrectpreset(RECTSETS.get(name))
		if not any(getattr(it, "kind", "") == "rect" for it in self.view.scene().selectedItems()):
			self.view.settool("rect")

	def setfib(self, name):
		"""use the levels of set name for the fibs, asking for the custom ones"""
		diagonal = False
		if name == "Custom":
			rows, diagonal = customrows()
			dlg = FibDialog(rows, diagonal, self.window())
			ok = dlg.exec()
			rows, diagonal = dlg.rows(), dlg.diagonal()
			dlg.deleteLater()
			if not ok:
				self.fibacts[self.fibname].setChecked(True)
				return
			fibsettings().setValue("customfibrows", json.dumps({"rows": rows, "diagonal": diagonal}))
			levels = rowlevels(rows)
		else:
			levels = FIBSETS[name]
		self.fibname = name
		self.fibacts[name].setChecked(True)
		self.view.setfiblevels(levels, diagonal)
		if not any(getattr(it, "kind", "") == "fib" for it in self.view.scene().selectedItems()):
			self.view.settool("fib")	# else it was for the fibs selected

	def detach(self):
		"""move the bar to a window of its own that stays on top"""
		if self.floating is not None:
			return
		win = self.window()
		if isinstance(self.parentWidget(), QMainWindow):
			self.home = (self.parentWidget(), self.parentWidget().toolBarArea(self))
			self.parentWidget().removeToolBar(self)
		else:
			lay = findlayout(self.parentWidget().layout(), self)
			self.home = (lay, lay.indexOf(self)) if lay is not None else None
		for a in (self.undoact, self.redoact):
			win.addAction(a)	# their keys still work in the window
		f = self.floating = FloatBar(self, win)
		f.layout().addWidget(self)
		self.show()
		f.adjustSize()
		pos = fibsettings().value("floatpos")
		if pos is not None:
			f.move(pos)
		else:
			f.move(win.mapToGlobal(win.rect().topLeft()) + win.rect().center() / 4)
		f.show()
		self.detachact.setChecked(True)

	def attach(self):
		"""put the bar back where it was"""
		f = self.floating
		if f is None:
			return
		fibsettings().setValue("floatpos", f.pos())
		self.floating = None
		home, self.home = self.home, None
		if home is not None and isinstance(home[0], QMainWindow):
			home[0].addToolBar(home[1], self)
		elif home is not None:
			home[0].insertWidget(home[1], self)
		self.show()
		f.hide()
		f.deleteLater()
		self.detachact.setChecked(False)

	def sizepicked(self, i):
		z = self.sizebox.itemData(i)
		fibsettings().setValue("textsize", z)
		self.view.settextsize(z)

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

def findlayout(lay, w):
	"""the layout, lay or one inside it, that has w"""
	if lay is None:
		return None
	if lay.indexOf(w) >= 0:
		return lay
	for i in range(lay.count()):
		sub = findlayout(lay.itemAt(i).layout(), w)
		if sub is not None:
			return sub
	return None
