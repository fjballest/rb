#
# the toolbar for drawing on an ImageView: the tools, color, width, undo,
# redo and delete. Shared by DayJournal and pylg's graphics window.
#
import json

from PySide6.QtCore import QSettings, QSize, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QKeySequence, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
	QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout, QLabel, QLayout,
	QLineEdit, QListWidget, QMainWindow, QMenu, QMessageBox, QPushButton, QStatusBar, QToolBar, QToolButton, QVBoxLayout,
	QWidget
)

from drawing import FIBALL, FIBROWS, FIBSETS, RECTSETS, FibShape, fmtlevels, parselevels
from viewer import pickcolor

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
	"""the rows of the custom levels form, [(on, text)...], whether the
	diagonal is drawn, and whether the lines start at the second point"""
	st = fibsettings()
	try:
		d = json.loads(str(st.value("customfibrows", "")))
		rows = [(bool(on), str(t)) for on, t in d["rows"]][:FIBROWS]
		diag = bool(d.get("diagonal"))
		from2 = bool(d.get("from2"))
	except (ValueError, KeyError, TypeError):
		try:	# what was kept before the form: just the levels used
			used = set(parselevels(str(st.value("customfib", ""))))
		except ValueError:
			used = set(FIBALL)
		levels = sorted(set(FIBALL) | used)
		rows = [(l in used, f"{l:g}") for l in levels]
		diag = from2 = False
	rows += [(False, "")] * (FIBROWS - len(rows))
	return rows, diag, from2

# the sets saved by name from the custom forms, in the menus after the built-in ones
def savedfibs():
	"""{name: {"levels": [...], "diagonal": bool, "from2": bool}}"""
	try:
		d = json.loads(str(fibsettings().value("savedfibs", "") or "{}"))
		return {str(n): {"levels": [float(l) for l in v["levels"]], "diagonal": bool(v.get("diagonal")),
			"from2": bool(v.get("from2"))} for n, v in d.items() if v.get("levels")}
	except (ValueError, KeyError, TypeError, AttributeError):
		return {}

def savefib(name, levels, diagonal, from2=False):
	d = savedfibs()
	d[name] = {"levels": list(levels), "diagonal": bool(diagonal), "from2": bool(from2)}
	fibsettings().setValue("savedfibs", json.dumps(d))

# what is saved of each kind of shape: its look, not its size or place
SHAPEKEYS = {
	"rect": ("color", "width", "fill", "alpha", "middle", "midcolor", "label", "align", "labelcolor", "dash"),
	"line": ("color", "width", "dash", "label", "labelcolor", "valign", "align", "extend"),
	"arrow": ("color", "width", "dash", "label", "labelcolor", "valign", "align"),
	"circle": ("color", "width", "dash", "label", "labelcolor", "valign", "align"),
}
SHAPENAMES = {"rect": "Rect", "line": "Line", "arrow": "Arrow", "circle": "Circle", "fib": "Fib"}

def savedkey(kind):
	return "savedfibs" if kind == "fib" else f"saved{kind}s"

def savedshapes(kind):
	"""{name: the properties of the shape, as in RECTSETS}, in their order"""
	try:
		d = json.loads(str(fibsettings().value(savedkey(kind), "") or "{}"))
		return {str(n): {k: v[k] for k in SHAPEKEYS[kind] if k in v} for n, v in d.items() if "color" in v}
	except (ValueError, TypeError, AttributeError):
		return {}

def saveshape(kind, name, preset):
	d = savedshapes(kind)
	d[name] = {k: preset[k] for k in SHAPEKEYS[kind] if k in preset}
	fibsettings().setValue(savedkey(kind), json.dumps(d))

def saved(kind):
	return savedfibs() if kind == "fib" else savedshapes(kind)

def setsaved(kind, d):
	"""keep d, {name: what is saved}, as the sets saved of kind, in its order"""
	fibsettings().setValue(savedkey(kind), json.dumps(d))

class SavedDialog(QDialog):
	"""the sets saved in a menu: edit, rename, remove or move them. editor
	is called with the kind and what is saved of one, to change it: it
	gives the new one, or None"""
	def __init__(self, kind, taken, parent=None, editor=None):
		super().__init__(parent)
		self.kind = kind
		self.editor = editor
		self.taken = set(taken)
		self.sets = dict(saved(kind))
		self.setWindowTitle(f"Saved {SHAPENAMES[kind]}s")
		lay = QVBoxLayout(self)
		lay.addWidget(QLabel(f"The ones saved in the {SHAPENAMES[kind]} menu. Double click one to rename it; "
			"Edit changes it."))
		row = QHBoxLayout()
		self.list = QListWidget()
		self.list.addItems(list(self.sets))
		for i in range(self.list.count()):
			it = self.list.item(i)
			it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEditable)
			it.setData(Qt.ItemDataRole.UserRole, it.text())
		self.list.itemChanged.connect(self.renamed)
		row.addWidget(self.list, 1)
		col = QVBoxLayout()
		for text, fn in (("Edit…", self.edit), ("Rename", self.rename), ("Remove", self.remove),
				("Up", lambda: self.move(-1)), ("Down", lambda: self.move(1))):
			if fn == self.edit and editor is None:
				continue
			b = QPushButton(text)
			b.setAutoDefault(False)
			b.clicked.connect(fn)
			col.addWidget(b)
		col.addStretch()
		row.addLayout(col)
		lay.addLayout(row)
		bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
		bb.accepted.connect(self.accept)
		bb.rejected.connect(self.reject)
		lay.addWidget(bb)
		if self.list.count():
			self.list.setCurrentRow(0)

	def names(self):
		return [self.list.item(i).text() for i in range(self.list.count())]

	def edit(self):
		"""change the one selected, with the form of its kind"""
		it = self.list.currentItem()
		if it is None or self.editor is None:
			return
		new = self.editor(self.kind, self.sets[it.text()])
		if new is not None:
			self.sets[it.text()] = new

	def rename(self):
		it = self.list.currentItem()
		if it is not None:
			self.list.editItem(it)

	def renamed(self, it):
		old = it.data(Qt.ItemDataRole.UserRole)
		new = " ".join(it.text().split())
		if not new or new in self.taken or self.names().count(new) > 1:
			if new and new != old:
				QMessageBox.warning(self, self.windowTitle(), f"{new} is already in the menu.")
			self.list.blockSignals(True)
			it.setText(old)
			self.list.blockSignals(False)
			return
		self.list.blockSignals(True)
		it.setText(new)
		it.setData(Qt.ItemDataRole.UserRole, new)
		self.list.blockSignals(False)
		self.sets[new] = self.sets.pop(old)

	def remove(self):
		r = self.list.currentRow()
		if r >= 0:
			it = self.list.takeItem(r)
			self.sets.pop(it.text(), None)

	def move(self, d):
		r = self.list.currentRow()
		if 0 <= r + d < self.list.count() and r >= 0:
			self.list.blockSignals(True)
			it = self.list.takeItem(r)
			self.list.insertItem(r + d, it)
			self.list.setCurrentRow(r + d)
			self.list.blockSignals(False)

	def result_(self):
		"""what is saved, in the order shown"""
		return {n: self.sets[n] for n in self.names()}

def rowlevels(rows):
	"""the levels of the rows that are on, sorted; ValueError if one is not
	a number or there are none"""
	return parselevels(" ".join(t for on, t in rows if on and t.strip()))

def customlevels():
	rows, diag, from2 = customrows()
	try:
		return rowlevels(rows), diag, from2
	except ValueError:
		return list(FIBALL), diag, from2

class FibDialog(QDialog):
	"""the custom fib levels: FIBROWS levels in two columns, each one with a
	check to use it, whether to draw the diagonal, and whether the lines
	start at the second point (From 2); changed is emitted on every change,
	to show it"""
	changed = Signal()

	def __init__(self, rows, diagonal, parent=None, taken=(), from2=False):
		super().__init__(parent)
		self.taken = set(taken)	# names that can't be used: the built-in sets
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
		self.from2box = QCheckBox("From 2")
		self.from2box.setToolTip("the lines start at the second point, not at the first, and go to the third")
		self.from2box.setChecked(from2)
		row = QHBoxLayout()
		row.addWidget(self.diagbox)
		row.addWidget(self.from2box)
		row.addStretch()
		clear = QPushButton("Clear")
		clear.setToolTip("uncheck all the levels")
		clear.setAutoDefault(False)
		clear.clicked.connect(self.clear)
		row.addWidget(clear)
		lay.addLayout(row)
		row = QHBoxLayout()
		self.namerow = QWidget()	# the name and its label
		self.namerow.setLayout(row)
		row.setContentsMargins(0, 0, 0, 0)
		row.addWidget(QLabel("Name:"))
		self.namebox = QLineEdit()
		self.namebox.setPlaceholderText("to keep these levels in the Fib menu")
		self.namebox.setToolTip("a short name, like OTE2; the levels are saved under it and show up "
			"in the menu. The same name replaces them")
		row.addWidget(self.namebox, 1)
		lay.addWidget(self.namerow)
		bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
		bb.accepted.connect(self.accept)
		bb.rejected.connect(self.reject)
		lay.addWidget(bb)
		for c, e in zip(self.checks, self.edits):
			c.toggled.connect(lambda *_: self.changed.emit())
			e.textChanged.connect(lambda *_: self.changed.emit())
		self.diagbox.toggled.connect(lambda *_: self.changed.emit())
		self.from2box.toggled.connect(lambda *_: self.changed.emit())

	def shown(self):
		"""the levels, diagonal and from2 as they are now, or None if they
		are not levels yet"""
		try:
			return rowlevels(self.rows()), self.diagonal(), self.from2()
		except ValueError:
			return None

	def from2(self):
		return self.from2box.isChecked()

	def rows(self):
		return [(c.isChecked(), e.text().strip()) for c, e in zip(self.checks, self.edits)]

	def diagonal(self):
		return self.diagbox.isChecked()

	def clear(self):
		for c in self.checks:
			c.setChecked(False)

	def name(self):
		return " ".join(self.namebox.text().split())

	def accept(self):
		if self.name() in self.taken:
			QMessageBox.warning(self, "Fib levels", f"{self.name()} is one of the sets already in the menu; "
				"give these levels another name.")
			return
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
	c = QColor(d.get("fill") or "#ffffff")
	c.setAlpha(max(d.get("alpha", 64), 90) if d.get("fill") else 255)
	pm.fill(c)
	p = QPainter(pm)
	p.setPen(QColor(d["color"]))
	p.drawRect(0, 0, 15, 11)
	p.setPen(QColor(d.get("midcolor") or d["color"]))
	p.drawLine(2, 6, 13, 6)
	p.end()
	return QIcon(pm)

def lineswatch(d, kind):
	"""an icon for a saved line, arrow or circle: its color and style"""
	pm = QPixmap(16, 12)
	pm.fill(Qt.GlobalColor.transparent)
	p = QPainter(pm)
	p.setRenderHint(QPainter.RenderHint.Antialiasing)
	pen = QPen(QColor(d.get("color", "#000000")), min(3.0, float(d.get("width", 2))))
	pen.setStyle({"dash": Qt.PenStyle.DashLine, "dot": Qt.PenStyle.DotLine}.get(d.get("dash"), Qt.PenStyle.SolidLine))
	p.setPen(pen)
	if kind == "circle":
		p.drawEllipse(2, 1, 12, 10)
	else:
		p.drawLine(1, 10, 14, 2)
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
		self.shapeacts, self.shapenames = {}, {}
		self.mkfibmenu()
		for kind in ("rect", "line", "arrow", "circle"):
			self.mkshapemenu(kind)
		view.shapesaved.connect(self.shapesaved)
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
		self.addSeparator()
		self.copyimgact = QAction("Copy", self)
		self.copyimgact.setToolTip("copy the image, with its drawings, to paste it in other programs (⇧⌘C)")
		self.copyimgact.setShortcut(QKeySequence("Ctrl+Shift+C"))
		self.copyimgact.triggered.connect(self.copyimage)
		self.addAction(self.copyimgact)
		# the crosshair is always on; Hide hides all the drawings, and Show brings them back
		view.setcrosshair(True)
		view.fibform = self.fibform	# a double click on a fib changes its levels
		view.presetmenu = self.presetmenu	# the right button on a drawing
		self.hideact = QAction("Hide", self)
		self.hideact.setToolTip("hide all the drawings, to see the image as it is (H on the image); "
			"they are kept, and drawing shows them again")
		self.hideact.triggered.connect(view.togglehidden)
		view.hiddenchanged.connect(self.hiddenchanged)
		self.addAction(self.hideact)
		view.scene().selectionChanged.connect(self.selchanged)
		self.setcolor(view.color, apply=False)
		self.selchanged()

	def copyimage(self):
		if self.view.copyimage():
			sb = self.view.window().findChild(QStatusBar)
			if sb is not None:
				sb.showMessage("Image copied", 3000)

	def hiddenchanged(self, hidden):
		self.hideact.setText("Show" if hidden else "Hide")
		self.hideact.setToolTip("show the drawings again (H on the image)" if hidden else
			"hide all the drawings, to see the image as it is (H on the image); they are kept, and drawing shows them again")

	def fibsets(self):
		"""the levels in the menu, built-in and saved: {name: (levels, diagonal, from2)}"""
		sets = {n: (ls, False, False) for n, ls in FIBSETS.items()}
		for n, v in savedfibs().items():
			sets.setdefault(n, (v["levels"], v["diagonal"], v["from2"]))
		return sets

	def mkfibmenu(self):
		a = self.toolacts["fib"]
		m = QMenu(self)
		g = QActionGroup(m)
		self.fibacts = {}
		mine = [n for n in savedfibs() if n not in FIBSETS]
		for name, (levels, *_) in self.fibsets().items():
			if mine and name == mine[0]:
				m.addSeparator()
			x = m.addAction(f"{name}: {fmtlevels(levels)}")
			x.triggered.connect(lambda _=False, n=name: self.setfib(n))
			self.fibacts[name] = x
		m.addSeparator()
		x = m.addAction("Custom…")
		x.setToolTip("your own levels; give them a name to keep them in this menu")
		x.triggered.connect(lambda _=False: self.setfib("Custom"))
		self.fibacts["Custom"] = x
		for x in self.fibacts.values():
			x.setCheckable(True)
			g.addAction(x)
		self.editsavedact(m, "fib", bool(mine))
		self.setmenu(a, m)
		if getattr(self, "fibname", None) not in self.fibacts:
			self.fibname = "OTE"
		self.fibacts[self.fibname].setChecked(True)

	def setmenu(self, a, m):
		old = a.menu()
		a.setMenu(m)
		if old is not None:
			old.deleteLater()
		b = self.widgetForAction(a)
		if b is not None:
			b.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)

	def editsavedact(self, m, kind, on):
		x = m.addAction("Edit Saved…")
		x.setToolTip("edit, rename, remove or reorder the ones saved")
		x.setEnabled(on)
		x.triggered.connect(lambda _=False: self.editsaved(kind))

	def builtin(self, kind):
		"""the names in the menu of kind that are not saved ones"""
		return {"fib": tuple(FIBSETS) + ("Custom",), "rect": ("Plain",) + tuple(RECTSETS)}.get(kind, ("Plain",))

	def editsaved(self, kind):
		dlg = SavedDialog(kind, self.builtin(kind), self.window(), editor=self.editpreset)
		self.saveddlg = dlg	# for the tests
		if dlg.exec() == QDialog.DialogCode.Accepted:
			setsaved(kind, dlg.result_())
			self.remakemenu(kind)
			# the one in use may have been edited: draw with it as it is now
			if kind == "fib" and self.fibname in savedfibs():
				f = savedfibs()[self.fibname]
				# not the ones selected
				self.view.fiblevels, self.view.fibdiagonal, self.view.fibfrom2 = list(f["levels"]), f["diagonal"], f["from2"]
			elif kind != "fib" and self.shapenames.get(kind) in savedshapes(kind):
				self.view.setpreset(kind, self.shapesets(kind)[self.shapenames[kind]])
		dlg.deleteLater()
		self.saveddlg = None

	def editpreset(self, kind, preset):
		"""the form for a look saved of kind (the levels of a fib), to change
		it: the new one, or None"""
		if kind == "fib":
			r = self.fibform(preset["levels"], preset["diagonal"], named=False, from2=preset.get("from2", False))
			return {"levels": r[0], "diagonal": bool(r[1]), "from2": bool(r[2])} if r else None
		from PySide6.QtCore import QPointF, QRectF
		from drawing import CircleShape, LineShape, RectShape
		from viewer import RectDialog, ShapeDialog
		d = {k: v for k, v in preset.items() if k not in ("color", "width")}
		args = (preset.get("color", "#e53935"), float(preset.get("width", 2)))
		try:
			if kind == "rect":
				it = RectShape(QRectF(0, 0, 100, 50), *args, **d)
			elif kind == "circle":
				it = CircleShape(QRectF(0, 0, 100, 50), *args, **d)
			else:
				it = LineShape(QPointF(0, 0), QPointF(100, 0), *args, kind == "arrow", **d)
		except TypeError:
			return None
		dlg = (RectDialog if kind == "rect" else ShapeDialog)(it, self.window())
		dlg.namebox.setText("")
		form = dlg.layout()
		if hasattr(form, "setRowVisible"):
			form.setRowVisible(dlg.namebox, False)	# it has its name
		self.shapedlg = dlg	# for the tests
		ok = dlg.exec() == QDialog.DialogCode.Accepted
		props = dlg.props()
		dlg.deleteLater()
		self.shapedlg = None
		if not ok:
			return None
		new = dict(preset)
		new.update({k: v for k, v in props.items() if k in SHAPEKEYS[kind]})
		return {k: new[k] for k in SHAPEKEYS[kind] if k in new}

	def remakemenu(self, kind):
		if kind == "fib":
			self.mkfibmenu()
		else:
			self.mkshapemenu(kind)

	def shapesets(self, kind):
		"""the looks in the menu of kind, built-in and saved: {name: properties}"""
		sets = dict(RECTSETS) if kind == "rect" else {}
		for n, v in savedshapes(kind).items():
			sets.setdefault(n, v)
		return sets

	def mkshapemenu(self, kind):
		"""the menu of the tool for kind (rect, line, arrow, circle): a plain
		one, the built-in looks (rectangles) and the ones saved"""
		a = self.toolacts[kind]
		m = QMenu(self)
		g = QActionGroup(m)
		acts = self.shapeacts[kind] = {}
		sets = self.shapesets(kind)
		mine = [n for n in savedshapes(kind) if n not in self.builtin(kind)]
		plain = "Plain: just the border" if kind == "rect" else "Plain: the color, width and style chosen"
		for name in ("Plain",) + tuple(sets):
			if mine and name == mine[0]:
				m.addSeparator()
			x = m.addAction(plain if name == "Plain" else name)
			if name != "Plain":
				x.setIcon(rectswatch(sets[name]) if kind == "rect" else lineswatch(sets[name], kind))
			x.setCheckable(True)
			g.addAction(x)
			x.triggered.connect(lambda _=False, n=name: self.setshape(kind, n))
			acts[name] = x
		m.addSeparator()
		h = m.addAction(f"To save one: double click it and give it a name")
		h.setEnabled(False)
		self.editsavedact(m, kind, bool(mine))
		self.setmenu(a, m)
		if self.shapenames.get(kind) not in acts:
			self.shapenames[kind] = "Plain"
			self.view.setpreset(kind, None)
		acts[self.shapenames[kind]].setChecked(True)
		if kind == "rect":	# the names used before
			self.rectacts, self.rectname = acts, self.shapenames[kind]

	def shapesaved(self, kind, name, preset):
		"""a shape was saved with a name in its form: keep it in the menu"""
		saveshape(kind, name, preset)
		self.remakemenu(kind)

	def setshape(self, kind, name):
		"""draw shapes of kind with the look name (Plain, built-in or saved);
		the ones selected change to it"""
		self.shapenames[kind] = name
		self.shapeacts[kind][name].setChecked(True)
		if kind == "rect":
			self.rectname = name
		self.view.setpreset(kind, self.shapesets(kind).get(name))
		if not any(getattr(it, "kind", "") == kind for it in self.view.scene().selectedItems()):
			self.view.settool(kind)

	def setrect(self, name):
		self.setshape("rect", name)

	def setfib(self, name):
		"""use the levels of set name for the fibs, asking for the custom ones"""
		diagonal = from2 = False
		if name == "Custom":
			rows, diagonal, from2 = customrows()
			dlg = FibDialog(rows, diagonal, self.window(), taken=tuple(FIBSETS) + ("Custom",), from2=from2)
			sel = [it for it in self.view.scene().selectedItems() if isinstance(it, FibShape)]
			old = [(it, list(it.levels), it.diagonal, it.from2) for it in sel]
			def show():	# the fibs selected show the levels as they are edited
				r = dlg.shown()
				for it, *_ in old if r else ():
					it.setlevels(*r)
			dlg.changed.connect(show)
			self.fibdlg = dlg	# for the tests
			ok = dlg.exec()
			rows, diagonal, from2, saveas = dlg.rows(), dlg.diagonal(), dlg.from2(), dlg.name()
			dlg.deleteLater()
			self.fibdlg = None
			for it, lv, dg, f2 in old:	# back as they were: the change is one undo step
				it.setlevels(lv, dg, f2)
			if not ok:
				self.fibacts[self.fibname].setChecked(True)
				return
			fibsettings().setValue("customfibrows", json.dumps({"rows": rows, "diagonal": diagonal, "from2": from2}))
			levels = rowlevels(rows)
			if saveas:
				savefib(saveas, levels, diagonal, from2)
				self.fibname = saveas
				self.mkfibmenu()
				name = saveas
		else:
			levels, diagonal, from2 = self.fibsets()[name]
		self.fibname = name
		self.fibacts[name].setChecked(True)
		self.view.setfiblevels(levels, diagonal, from2)
		if not any(getattr(it, "kind", "") == "fib" for it in self.view.scene().selectedItems()):
			self.view.settool("fib")	# else it was for the fibs selected

	def fibform(self, levels, diagonal, named=True, show=None, from2=False):
		"""ask for other levels for a fib drawn with these: (levels,
		diagonal, from2), or None. A name given keeps them in the menu too
		(named: the form asks for one). show(levels, diagonal, from2), if
		given, is called on every change that gives levels, to show them
		while the form is open"""
		rows = [(l in levels, f"{l:g}") for l in sorted(set(FIBALL) | set(levels))][:FIBROWS]
		rows += [(False, "")] * (FIBROWS - len(rows))
		dlg = FibDialog(rows, diagonal, self.window(), taken=tuple(FIBSETS) + ("Custom",), from2=from2)
		dlg.setWindowTitle("Fib Levels")
		if not named:
			dlg.namerow.setVisible(False)
		if show is not None:
			dlg.changed.connect(lambda: (lambda r: r and show(*r))(dlg.shown()))
		self.fibdlg = dlg	# for the tests
		ok = dlg.exec()
		rows, diagonal, from2, saveas = dlg.rows(), dlg.diagonal(), dlg.from2(), dlg.name()
		dlg.deleteLater()
		self.fibdlg = None
		if not ok:
			return None
		levels = rowlevels(rows)
		if saveas:
			savefib(saveas, levels, diagonal, from2)
			self.mkfibmenu()
		return levels, diagonal, from2

	def presetmenu(self, m, kind, items):
		"""fill menu m, the context menu of the drawings items of kind, with
		the configurations of that kind in the bar's menu: the fib levels,
		or the looks built-in and saved; picking one changes items to it.
		The one they have is checked"""
		g = QActionGroup(m)
		if kind == "fib":
			for name, (levels, diagonal, from2) in self.fibsets().items():
				x = m.addAction(f"{name}: {fmtlevels(levels)}")
				x.setCheckable(True)
				x.setChecked(all((list(it.levels), bool(it.diagonal), bool(it.from2)) ==
					(list(levels), bool(diagonal), bool(from2)) for it in items))
				x.triggered.connect(lambda _=False, r=(levels, diagonal, from2): self.view.applyfib(items, *r))
				g.addAction(x)
			return
		if kind not in SHAPEKEYS:
			return
		for name, preset in self.shapesets(kind).items():
			x = m.addAction(name)
			x.setCheckable(True)
			x.setChecked(all(getattr(it, k, None) == v for it in items for k, v in preset.items()))
			x.triggered.connect(lambda _=False, p=dict(preset): self.view.applypreset(items, p))
			g.addAction(x)
		if m.isEmpty():
			x = m.addAction(f"No saved {SHAPENAMES[kind].lower()}s: double click it to save its look")
			x.setEnabled(False)

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
		for a in (self.undoact, self.redoact, self.copyimgact):
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
		"""ask for another color; the drawings selected show it while asking"""
		old = [(it, it.color, it.width) for it in self.view.scene().selectedItems()]
		def show(c):
			for it, _, w in old:
				it.setstyle(c, w)
		c = pickcolor(self.view.color, self, "Drawing color", show)
		for it, c0, w in old:
			it.setstyle(c0, w)
		if c:
			self.setcolor(c)

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
