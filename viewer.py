#
# the image view: fits the image, zooms with the buttons or double clicks
# (zoom in, zoom in again, back to fit), pans by dragging the image, and
# holds the drawings made on it, in image coordinates. Shared by DayJournal
# and pylg's graphics window.
#
from PySide6.QtCore import QEvent, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QUndoStack
from PySide6.QtWidgets import (
	QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGraphicsPixmapItem,
	QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSlider
)

from drawing import (
	DRAWVERSION, FIBSETS, AddCmd, CircleShape, DeleteCmd, FibShape, LevelsCmd, LineShape, MoveCmd, PencilShape,
	PropsCmd, RectShape, StyleCmd, TextCmd, TextShape, allprops, fromdict
)

DCLICKZOOM = 2.0
TOOLS = ("select", "pencil", "line", "arrow", "circle", "rect", "text", "fib")
TOOLKEYS = {Qt.Key.Key_S: "select", Qt.Key.Key_P: "pencil", Qt.Key.Key_L: "line", Qt.Key.Key_A: "arrow",
	Qt.Key.Key_C: "circle", Qt.Key.Key_R: "rect", Qt.Key.Key_T: "text", Qt.Key.Key_F: "fib"}
# the keys sent as navigate, and what for; a window can set its own navkeys
NAVKEYS = {Qt.Key.Key_Left: "prev", Qt.Key.Key_Up: "prev", Qt.Key.Key_Right: "next",
	Qt.Key.Key_Down: "next", Qt.Key.Key_Home: "first", Qt.Key.Key_End: "last", Qt.Key.Key_W: "week"}

class ImageView(QGraphicsView):
	navigate = Signal(str)		# keys for moving through the images (navkeys)
	drawchanged = Signal()		# the drawings changed
	toolchanged = Signal(str)

	def __init__(self, parent=None):
		super().__init__(parent)
		self.setScene(QGraphicsScene(self))
		self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
		self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
		self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
		self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
		self.pixitem = None
		self.path = None
		self.mode = "fit"	# "fit", "real", or "zoom" to keep the scale
		self.dstep = 0
		self.tool = "select"
		self.color = "#e53935"
		self.width = 3.0
		self.textsize = 16	# for text boxes, labels and fib levels
		self.dash = "solid"
		self.drawing = None		# the item being drawn
		# a fib is drawn in steps: "drag" from the first point, then "p2" when
		# that was a click, then "right" for where the lines end
		self.fibstep = None
		self.fiblevels = list(FIBSETS["OTE"])
		self.fibdiagonal = False
		self.rectpreset = None	# the RECTSETS entry for the next rectangles, None for a plain one
		self.fibdone = QTimer(self, singleShot=True)	# a click ends it, unless it was a double click
		self.fibdone.setInterval(QApplication.doubleClickInterval())
		self.fibdone.timeout.connect(lambda: self.endfib(False))
		self.viewport().setMouseTracking(True)	# fib steps follow the mouse with no button down
		self.pressed = {}		# selected item -> its position when the mouse was pressed
		self.undo = QUndoStack(self)
		self.undo.indexChanged.connect(self.undochanged)
		self.loading = False
		self.navkeys = NAVKEYS
		self.dclickzoom = True	# double clicks on the image zoom; a trackpad double tap always does
		self.settool("select")

	def undochanged(self, _index):
		self.drawchanged.emit()

	# ---- image ----
	def setimage(self, path, drawing=None):
		"""show the image at path with the drawing saved for it"""
		self.commitedit()
		self.loading = True
		self.drawing = None
		self.fibstep = None
		self.fibdone.stop()
		self.undo.clear()
		self.scene().clear()
		self.pixitem = None
		self.path = path
		p = QPixmap(path) if path else QPixmap()
		if not p.isNull():
			self.pixitem = QGraphicsPixmapItem(p)
			self.pixitem.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
			self.pixitem.setZValue(0)
			self.scene().addItem(self.pixitem)
			self.scene().setSceneRect(QRectF(p.rect()))
			for d in (drawing or {}).get("shapes", []):
				it = fromdict(d)
				if it is not None:
					self.additem(it)
		else:
			self.scene().setSceneRect(QRectF())
		if self.mode == "fit":
			self.fit(keep=True)
		elif self.mode == "real":
			self.resetTransform()
		self.loading = False

	def commitedit(self):
		"""end the editing of a text box, if any"""
		f = self.scene().focusItem()
		if f is not None:
			f.clearFocus()

	def hasimage(self):
		return self.pixitem is not None

	def shapes(self):
		"""the drawn items, in the order they were drawn"""
		return [it for it in self.scene().items(Qt.SortOrder.AscendingOrder) if it is not self.pixitem]

	def drawingdata(self):
		"""the drawings as saved, None when there are none"""
		shapes = [it.todict() for it in self.shapes()]
		return {"version": DRAWVERSION, "shapes": shapes} if shapes else None

	def additem(self, it):
		self.scene().addItem(it)
		if isinstance(it, TextShape):
			it.edited = self.textedited
		elif isinstance(it, (RectShape, LineShape, CircleShape)):
			it.edit = self.editshape

	def editshape(self, it):
		"""the dialog for the properties of rectangle, line, arrow or circle
		it; the drawing shows the changes while it is open"""
		before = allprops(it)
		dlg = RectDialog(it, self) if isinstance(it, RectShape) else ShapeDialog(it, self)
		dlg.changed.connect(lambda: it.setprops(dlg.props()))
		ok = dlg.exec() == QDialog.DialogCode.Accepted
		after = dict(before)
		after.update(dlg.props())
		dlg.deleteLater()
		if ok and after != before:
			self.undo.push(PropsCmd(it, before, after))
		else:
			it.setprops(before)
		self.drawchanged.emit()

	def setselprops(self, d, text):
		"""set d on the drawings selected that have those properties, in one undo step"""
		sel = [it for it in self.scene().selectedItems() if set(d) <= set(getattr(it, "PROPS", ()))]
		if not sel:
			return
		self.undo.beginMacro(text)
		for it in sel:
			before = {k: getattr(it, k) for k in d}
			it.setprops(d)
			self.undo.push(PropsCmd(it, before, d))
		self.undo.endMacro()

	def setdash(self, dash):
		"""solid, dash or dot for the lines drawn next, and the ones selected"""
		self.dash = dash
		self.setselprops({"dash": dash}, "Change line style")

	def settextsize(self, size):
		"""the size of the text boxes, labels and fib levels made next, and
		of the ones selected"""
		self.textsize = size
		self.setselprops({"size": size}, "Change text size")

	def clearall(self):
		"""delete every drawing, as one step that can be undone"""
		self.cancelfib()
		shapes = self.shapes()
		if shapes:
			self.undo.push(DeleteCmd(self.scene(), shapes))

	# ---- zoom ----
	def scale_(self):
		return self.transform().m11()

	def fit(self, keep=False):
		if not self.pixitem:
			return
		self.mode = "fit"
		self.dstep = 0
		r = self.pixitem.boundingRect()
		v = self.maximumViewportSize()
		s = min(v.width() / r.width(), v.height() / r.height())
		self.resetTransform()
		self.scale(s, s)

	def realsize(self):
		if self.pixitem:
			self.mode = "real"
			self.resetTransform()

	def zoom(self, factor, at=None):
		"""zoom by factor keeping the image point at viewport point at in place"""
		if not self.pixitem:
			return
		self.mode = "zoom"
		if at is None:
			at = self.viewport().rect().center()
		before = self.mapToScene(at)
		self.scale(factor, factor)
		after = self.mapToScene(at)
		d = (after - before) * self.scale_()
		self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - round(d.x()))
		self.verticalScrollBar().setValue(self.verticalScrollBar().value() - round(d.y()))

	def resizeEvent(self, ev):
		super().resizeEvent(ev)
		if self.mode == "fit":
			self.fit()

	# ---- tools ----
	def settool(self, tool):
		self.cancelfib()
		self.tool = tool
		if tool == "select":
			self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
			self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
		else:
			self.setDragMode(QGraphicsView.DragMode.NoDrag)
			self.viewport().setCursor(Qt.CursorShape.CrossCursor)
		self.toolchanged.emit(tool)

	def setcolor(self, color):
		"""the color for what is drawn next, and for the selection"""
		self.color = color
		sel = self.scene().selectedItems()
		if sel:
			self.undo.push(StyleCmd(sel, color, None))

	def setwidth(self, width):
		"""the line width for what is drawn next, and for the selection"""
		self.width = width
		sel = [it for it in self.scene().selectedItems() if not isinstance(it, TextShape)]
		if sel:
			self.undo.push(StyleCmd(sel, None, width))

	def setfiblevels(self, levels, diagonal=False):
		"""the levels for the next fibs, and for the fibs selected, and whether
		they have their diagonal"""
		self.fiblevels = list(levels)
		self.fibdiagonal = diagonal
		sel = [it for it in self.scene().selectedItems() if isinstance(it, FibShape)]
		if sel:
			self.undo.push(LevelsCmd(sel, levels, diagonal))

	def setrectpreset(self, preset):
		"""the RECTSETS entry for the next rectangles (None for a plain one),
		and for the rectangles selected"""
		self.rectpreset = dict(preset) if preset else None
		sel = [it for it in self.scene().selectedItems() if isinstance(it, RectShape)]
		if not sel or not preset:
			return
		self.undo.beginMacro("Change rectangles")
		for it in sel:
			before = {k: getattr(it, k) for k in preset}
			it.setprops(preset)
			self.undo.push(PropsCmd(it, before, preset))
		self.undo.endMacro()

	def cancelfib(self):
		"""drop a fib not finished"""
		if isinstance(self.drawing, FibShape):
			self.fibdone.stop()
			self.scene().removeItem(self.drawing)
			self.drawing = None
			self.fibstep = None

	def endfib(self, extend):
		"""the fib is done: its lines end where the mouse was, or at the
		right edge of the image when extend"""
		self.fibdone.stop()
		it, self.drawing, self.fibstep = self.drawing, None, None
		if not isinstance(it, FibShape):
			return
		it.setlive(False)
		if extend:
			it.setright(self.sceneRect().right(), True)
		self.undo.push(AddCmd(self.scene(), it))

	def fibpress(self, p):
		"""a click while drawing a fib, at p"""
		it = self.drawing
		if self.fibstep == "p2":
			it.setend(p)
			self.fibstep = "right"
		elif self.fibstep == "right" and not self.fibdone.isActive():
			it.setright(p.x())
			self.fibdone.start()	# done, unless this is the first click of a double one

	def deleteselected(self):
		sel = self.scene().selectedItems()
		if sel:
			self.undo.push(DeleteCmd(self.scene(), sel))

	def textedited(self, item, before, after):
		"""a text box was edited: an undo step for it, and an empty one goes"""
		new = getattr(item, "new", False)
		item.new = False
		if after.strip() == "":
			if new:
				self.scene().removeItem(item)
				self.drawchanged.emit()
			else:
				item.setPlainText(before)
				self.undo.push(DeleteCmd(self.scene(), [item]))
			return
		if new:
			self.undo.push(AddCmd(self.scene(), item))
		elif after != before:
			self.undo.push(TextCmd(item, before, after))

	# ---- mouse ----
	def mousePressEvent(self, ev):
		if isinstance(self.drawing, FibShape) and ev.button() == Qt.MouseButton.RightButton:
			self.cancelfib()	# the right button drops the fib being drawn
			return
		if self.pixitem is None or ev.button() != Qt.MouseButton.LeftButton:
			super().mousePressEvent(ev)
			return
		p = self.mapToScene(ev.position().toPoint())
		if isinstance(self.drawing, FibShape):
			self.fibpress(self.clamp(p))
			return
		if self.tool != "select" and not self.sceneRect().contains(p):
			return	# drawings go on the image
		if self.tool == "select":
			super().mousePressEvent(ev)
			self.pressed = {it: it.pos() for it in self.scene().selectedItems()}
			return
		focus = self.scene().focusItem()
		if focus is not None:
			focus.clearFocus()	# ends editing a text
		self.scene().clearSelection()
		if self.tool in ("line", "arrow"):
			self.drawing = LineShape(p, p, self.color, self.width, self.tool == "arrow", self.dash, size=self.textsize)
		elif self.tool == "pencil":
			self.drawing = PencilShape([p], self.color, self.width, self.dash)
		elif self.tool == "circle":
			self.drawing = CircleShape(QRectF(p, p), self.color, self.width, self.dash, size=self.textsize)
		elif self.tool == "rect":
			d = {"dash": self.dash, "size": self.textsize}
			d.update(self.rectpreset or {})
			self.drawing = RectShape(QRectF(p, p), d.pop("color", self.color), d.pop("width", self.width), **d)
		elif self.tool == "fib":
			self.drawing = FibShape(p, p, self.fiblevels, self.color, self.width, diagonal=self.fibdiagonal,
				dash=self.dash, size=self.textsize)
			self.drawing.setlive(True)
			self.fibstep = "drag"
		elif self.tool == "text":
			it = TextShape(p, "", self.color, self.textsize)
			it.new = True
			self.additem(it)
			it.startedit()
			self.settool("select")
			return
		self.additem(self.drawing)

	def mouseMoveEvent(self, ev):
		if self.drawing is not None:
			self.drawto(ev)
			return
		super().mouseMoveEvent(ev)

	def clamp(self, p):
		"""p, moved inside the image"""
		r = self.sceneRect()
		p.setX(min(max(p.x(), r.left()), r.right()))
		p.setY(min(max(p.y(), r.top()), r.bottom()))
		return p

	def drawto(self, ev):
		"""move the end of what is being drawn to the mouse, inside the image.
		With shift, lines and arrows are kept horizontal or vertical."""
		p = self.clamp(self.mapToScene(ev.position().toPoint()))
		if isinstance(self.drawing, FibShape):
			if self.fibstep in ("drag", "p2"):
				self.drawing.setend(p)
			elif self.fibstep == "right" and not self.fibdone.isActive():
				self.drawing.setright(p.x())
			return
		if isinstance(self.drawing, LineShape) and ev.modifiers() & Qt.KeyboardModifier.ShiftModifier:
			a = self.drawing.mapToScene(self.drawing.line().p1())
			if abs(p.x() - a.x()) >= abs(p.y() - a.y()):
				p.setY(a.y())
			else:
				p.setX(a.x())
		self.drawing.setend(p)

	def mouseReleaseEvent(self, ev):
		if isinstance(self.drawing, FibShape):
			if self.fibstep == "drag":
				# dragged to the second point, or clicked the first one: then click the second
				self.fibstep = "p2" if self.drawing.small() else "right"
			return
		if self.drawing is not None:
			if not isinstance(self.drawing, PencilShape):
				self.drawto(ev)
			it, self.drawing = self.drawing, None
			if it.small():
				self.scene().removeItem(it)
			else:
				self.undo.push(AddCmd(self.scene(), it))
			return
		super().mouseReleaseEvent(ev)
		if self.tool == "select" and self.pressed:
			moves = [(it, old, it.pos()) for it, old in self.pressed.items() if it.pos() != old]
			self.pressed = {}
			if moves:
				self.undo.push(MoveCmd(moves))

	def mouseDoubleClickEvent(self, ev):
		if isinstance(self.drawing, FibShape):
			if self.fibstep == "right":
				self.endfib(True)	# a double click on the second point: lines to the right edge
			return
		at = ev.position().toPoint()
		if self.tool != "select" or self.itemAt(at) not in (None, self.pixitem):
			super().mouseDoubleClickEvent(ev)
			return
		if self.dclickzoom:
			self.zoomstep(at)
		else:
			super().mouseDoubleClickEvent(ev)

	def zoomstep(self, at):
		"""zoom in at viewport point at, zoom in again, then fit"""
		if self.dstep < 2:
			self.dstep += 1
			self.zoom(DCLICKZOOM, at)
		else:
			self.fit()

	def viewportEvent(self, ev):
		# trackpad gestures (macOS): a two finger double tap zooms like a
		# double click, and pinching zooms in and out
		if ev.type() == QEvent.Type.NativeGesture and self.pixitem is not None:
			g = ev.gestureType()
			at = ev.position().toPoint()
			if g == Qt.NativeGestureType.SmartZoomNativeGesture:
				self.zoomstep(at)
				return True
			if g == Qt.NativeGestureType.ZoomNativeGesture:
				self.dstep = 0
				self.zoom(1 + ev.value(), at)
				return True
		return super().viewportEvent(ev)

	# ---- keys ----
	def keyPressEvent(self, ev):
		f = self.scene().focusItem()
		if isinstance(f, TextShape) and f.editing():
			super().keyPressEvent(ev)	# typing in a text box
			return
		k = ev.key()
		nav = self.navkeys
		# macOS marks the arrow keys as keypad keys
		plain = ev.modifiers() & ~Qt.KeyboardModifier.KeypadModifier == Qt.KeyboardModifier.NoModifier
		if k in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
			self.deleteselected()
		elif k == Qt.Key.Key_Escape:
			self.cancelfib()
			self.scene().clearSelection()
			self.settool("select")
		elif k in TOOLKEYS and ev.modifiers() == Qt.KeyboardModifier.NoModifier:
			self.settool(TOOLKEYS[k])
		elif k in nav and plain:
			self.navigate.emit(nav[k])
		else:
			super().keyPressEvent(ev)

ALIGNS = (("Center", "center"), ("Left", "left"), ("Right", "right"))

class RectDialog(QDialog):
	"""asks for the fill, middle line and label of a rectangle; changed is
	emitted on every change, to show it"""
	changed = Signal()

	def __init__(self, it, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Rectangle")
		self.fillcolor = it.fill or it.color
		form = QFormLayout(self)
		self.fillbox = QCheckBox("Fill")
		self.fillbox.setChecked(bool(it.fill))
		self.colorbtn = QPushButton()
		self.colorbtn.setToolTip("the fill color")
		self.colorbtn.clicked.connect(self.choosecolor)
		self.alpha = QSlider(Qt.Orientation.Horizontal)
		self.alpha.setRange(0, 100)	# % of transparency
		self.alpha.setValue(round(100 - it.alpha * 100 / 255))
		self.alpha.setToolTip("transparency: 0% hides what is under it, 100% shows it all")
		self.alphal = QLabel()
		self.alpha.valueChanged.connect(lambda v: self.alphal.setText(f"{v}%"))
		self.alphal.setText(f"{self.alpha.value()}%")
		row = QHBoxLayout()
		row.addWidget(self.fillbox)
		row.addWidget(self.colorbtn)
		form.addRow(row)
		row = QHBoxLayout()
		row.addWidget(self.alpha, 1)
		row.addWidget(self.alphal)
		form.addRow("Transparency:", row)
		self.middlebox = QCheckBox("Line across the middle")
		self.middlebox.setChecked(it.middle)
		self.midcolor = ColorButton(it.midcolor or it.color, "Middle line color", self)
		row = QHBoxLayout()
		row.addWidget(self.middlebox)
		row.addWidget(self.midcolor)
		form.addRow(row)
		self.label = QLineEdit(it.label)
		self.label.setPlaceholderText("FVG, OB...")
		form.addRow("Label:", self.label)
		self.align = QComboBox()
		for text, a in ALIGNS:
			self.align.addItem(text, a)
		self.align.setCurrentIndex(max(0, self.align.findData(it.align)))
		form.addRow("Aligned:", self.align)
		self.labelcolor = ColorButton(it.labelcolor or it.color, "Label color", self)
		form.addRow("Label color:", self.labelcolor)
		self.color = it.color
		bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
		bb.accepted.connect(self.accept)
		bb.rejected.connect(self.reject)
		form.addRow(bb)
		self.fillbox.toggled.connect(self.enable)
		self.middlebox.toggled.connect(self.enable)
		self.showcolor()
		self.enable()
		for sig in (self.fillbox.toggled, self.alpha.valueChanged, self.middlebox.toggled, self.midcolor.picked,
				self.label.textChanged, self.align.currentIndexChanged, self.labelcolor.picked):
			sig.connect(lambda *_: self.changed.emit())

	def enable(self):
		on = self.fillbox.isChecked()
		self.colorbtn.setEnabled(on)
		self.alpha.setEnabled(on)
		self.midcolor.setEnabled(self.middlebox.isChecked())

	def showcolor(self):
		pm = QPixmap(14, 14)
		pm.fill(QColor(self.fillcolor))
		self.colorbtn.setIcon(QIcon(pm))
		self.colorbtn.setText("Color…")

	def choosecolor(self):
		c = QColorDialog.getColor(QColor(self.fillcolor), self, "Fill color")
		if c.isValid():
			self.fillcolor = c.name()
			self.showcolor()
			self.changed.emit()

	def props(self):
		return {"fill": self.fillcolor if self.fillbox.isChecked() else None,
			"alpha": round((100 - self.alpha.value()) * 255 / 100),
			"middle": self.middlebox.isChecked(), "label": self.label.text().strip(),
			"align": self.align.currentData(),
			"midcolor": None if self.midcolor.color == self.color else self.midcolor.color,
			"labelcolor": None if self.labelcolor.color == self.color else self.labelcolor.color}

class ColorButton(QPushButton):
	"""a button showing a color, that asks for another one"""
	picked = Signal()

	def __init__(self, color, title, parent=None):
		super().__init__("Color…", parent)
		self.title = title
		self.setcolor(color)
		self.clicked.connect(self.choose)

	def setcolor(self, c):
		self.color = c
		pm = QPixmap(14, 14)
		pm.fill(QColor(c))
		self.setIcon(QIcon(pm))

	def choose(self):
		c = QColorDialog.getColor(QColor(self.color), self, self.title)
		if c.isValid():
			self.setcolor(c.name())
			self.picked.emit()

VALIGNS = (("Above", "above"), ("Center", "center"), ("Below", "below"))
DASHNAMES = (("Solid", "solid"), ("Dashed", "dash"), ("Dotted", "dot"))
WIDTHS = (1.0, 2.0, 3.0, 5.0, 8.0)
SIZES = (10, 12, 14, 16, 18, 22, 28, 36)

def combo(items, value):
	"""a combo box with items, (text, data), showing value"""
	c = QComboBox()
	for text, d in items:
		c.addItem(text, d)
	i = c.findData(value)
	if i < 0:
		c.addItem(str(value), value)
		i = c.count() - 1
	c.setCurrentIndex(i)
	return c

class ShapeDialog(QDialog):
	"""asks for the color, width, line style and label of a line, arrow or
	circle; changed is emitted on every change, to show it"""
	changed = Signal()

	def __init__(self, it, parent=None):
		super().__init__(parent)
		self.setWindowTitle({"line": "Line", "arrow": "Arrow", "circle": "Circle"}.get(it.kind, "Drawing"))
		form = QFormLayout(self)
		self.color = ColorButton(it.color, "Color", self)
		form.addRow("Color:", self.color)
		self.width = combo([(f"{w:g} px", w) for w in WIDTHS], it.width)
		form.addRow("Width:", self.width)
		self.dash = combo(DASHNAMES, it.dash)
		form.addRow("Style:", self.dash)
		self.label = QLineEdit(it.label)
		self.label.setPlaceholderText("a label for it")
		form.addRow("Label:", self.label)
		self.valign = combo(VALIGNS, it.valign)
		self.valign.setToolTip("above, across or below it")
		form.addRow("Vertical:", self.valign)
		self.align = combo(ALIGNS, it.align)
		self.align.setToolTip("at its left, in its middle, or at its right"
			+ (", past its end" if it.kind != "circle" else ""))
		form.addRow("Horizontal:", self.align)
		self.size = combo([(f"{z}", float(z)) for z in SIZES], float(it.size))
		form.addRow("Text size:", self.size)
		self.labelcolor = ColorButton(it.labelcolor or it.color, "Label color", self)
		form.addRow("Label color:", self.labelcolor)
		self.labelsame = it.labelcolor is None	# the label follows the color until one is picked
		self.labelcolor.picked.connect(self.labelpicked)
		self.color.picked.connect(self.colorpicked)
		bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
		bb.accepted.connect(self.accept)
		bb.rejected.connect(self.reject)
		form.addRow(bb)
		for sig in (self.color.picked, self.width.currentIndexChanged, self.dash.currentIndexChanged,
				self.label.textChanged, self.valign.currentIndexChanged, self.align.currentIndexChanged,
				self.size.currentIndexChanged, self.labelcolor.picked):
			sig.connect(lambda *_: self.changed.emit())

	def colorpicked(self):
		if self.labelsame:
			self.labelcolor.setcolor(self.color.color)

	def labelpicked(self):
		self.labelsame = False

	def props(self):
		return {"color": self.color.color, "width": self.width.currentData(), "dash": self.dash.currentData(),
			"label": self.label.text().strip(), "valign": self.valign.currentData(),
			"align": self.align.currentData(), "size": self.size.currentData(),
			"labelcolor": None if self.labelsame else self.labelcolor.color}
