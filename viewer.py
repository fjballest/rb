#
# the image view: fits the image, zooms with the buttons or double clicks
# (zoom in, zoom in again, back to fit), pans by dragging the image, and
# holds the drawings made on it, in image coordinates. Shared by DayJournal
# and pylg's graphics window.
#
import json

from PySide6.QtCore import QEvent, QMimeData, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QIcon, QImage, QKeySequence, QPainter, QPen, QPixmap, QUndoStack
from PySide6.QtWidgets import (
	QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGraphicsPixmapItem,
	QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton, QSlider
)

from drawing import (
	DRAWVERSION, FIBSETS, AddCmd, CircleShape, DeleteCmd, FibShape, GeomCmd, LevelsCmd, LineShape, MoveCmd, PencilShape,
	PropsCmd, RECTSETS, RectShape, StyleCmd, TextCmd, TextShape, allprops, fromdict
)

DCLICKZOOM = 2.0
DRAWMIME = "application/x-drawings"	# drawings copied, as saved (see drawingdata)
HANDLE = 7	# the size of the handles of a drawing selected, in pixels
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
	crosschanged = Signal(bool)	# the crosshair was turned on or off
	hiddenchanged = Signal(bool)	# the drawings were hidden (True) or shown again
	shapesaved = Signal(str, str, dict)	# the look of a shape of kind was saved with this name

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
		self.fibfrom2 = False	# the next fibs start their lines at the second point
		self.fibstyle = {}		# the width and dash of the next fibs, when their set has them
		self.rectpreset = None	# the RECTSETS entry for the next rectangles, None for a plain one
		self.presets = {}		# kind -> the look for the next shapes of it (see setpreset)
		self.fibdone = QTimer(self, singleShot=True)	# a click ends it, unless it was a double click
		self.fibdone.setInterval(QApplication.doubleClickInterval())
		self.fibdone.timeout.connect(lambda: self.endfib(False))
		self.viewport().setMouseTracking(True)	# fib steps follow the mouse with no button down
		self.pressed = {}		# selected item -> its position when the mouse was pressed
		self.reshaping = None	# (item, handle, its geometry before) while dragging a handle
		self.scene().selectionChanged.connect(self.viewport().update)	# the handles
		# Del deletes the drawings selected, unless delkey, set by the window,
		# takes it first (to delete the image when the mouse is on a list of
		# them, say): it says if it did
		self.delkey = None
		self.fibform = None	# see editfib
		# the configurations of a kind of drawing for its context menu: set by
		# the window (the drawing bar), called with the menu, the kind and the
		# drawings, to add them (see contextMenuEvent)
		self.presetmenu = None
		self.undo = QUndoStack(self)
		self.undo.indexChanged.connect(self.undochanged)
		self.loading = False
		self.navkeys = NAVKEYS
		self.dclickzoom = True	# double clicks on the image zoom; a trackpad double tap always does
		# the crosshair: a horizontal and a vertical line through the mouse,
		# across the image, to compare levels; cross is where, in the scene
		self.crosshair = True
		self.cross = None
		self.hidden = False	# the drawings are hidden, for this image and the next ones
		self.settool("select")

	def undochanged(self, _index):
		if self.hidden:	# an undo may bring one back
			for it in self.shapes():
				it.setVisible(False)
		self.drawchanged.emit()

	def setdrawingsshown(self, on):
		"""show or hide all the drawings; they are kept, and saved, either way"""
		self.hidden = not on
		if self.hidden:
			self.cancelfib()
			self.commitedit()
			self.scene().clearSelection()
		for it in self.shapes():
			it.setVisible(on)
		self.viewport().update()
		self.hiddenchanged.emit(self.hidden)

	def togglehidden(self):
		self.setdrawingsshown(self.hidden)

	# ---- image ----
	def setimage(self, path, drawing=None):
		"""show the image at path with the drawing saved for it"""
		self.commitedit()
		self.loading = True
		self.drawing = None
		self.cross = None
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
		it.setVisible(not self.hidden)
		if isinstance(it, TextShape):
			it.edited = self.textedited
		elif isinstance(it, (RectShape, LineShape, CircleShape)):
			it.edit = self.editshape
		elif isinstance(it, FibShape):
			it.edit = self.editfib

	def editfib(self, it):
		"""the levels form for fib it, from a double click: fibform, set by
		the window (the drawing bar), asks for them given its levels and
		diagonal, and gives the new ones, or None"""
		if self.fibform is None:
			return
		old = (list(it.levels), it.diagonal, it.from2)
		style = {"width": it.width, "dash": it.dash}
		def show(levels, diagonal, from2, width, dash):
			it.setlevels(levels, diagonal, from2)
			it.setprops({"width": width, "dash": dash})
		r = self.fibform(list(it.levels), it.diagonal, show=show, from2=it.from2, style=(it.width, it.dash))
		it.setlevels(*old)	# back as it was: the change is one undo step
		it.setprops(style)
		if r is None:
			return
		levels, diagonal, from2, width, dash = r
		new = {"width": width, "dash": dash}
		if new == style:
			self.applyfib([it], levels, diagonal, from2)
			return
		self.undo.beginMacro("Change fib")	# one undo step for both
		self.applyfib([it], levels, diagonal, from2)
		self.undo.push(PropsCmd(it, style, new))
		self.undo.endMacro()

	def applyfib(self, items, levels, diagonal, from2=False, style=None):
		"""levels, diagonal and from2 for the fibs items, and the width and
		dash in style, if any, in one undo step"""
		new = (list(levels), bool(diagonal), bool(from2))
		style = dict(style or {})
		levelsto = [it for it in items if (list(it.levels), bool(it.diagonal), bool(it.from2)) != new]
		styleto = [it for it in items if any(getattr(it, k) != v for k, v in style.items())]
		if not levelsto and not styleto:
			return
		self.undo.beginMacro("Change fibs")
		if levelsto:
			self.undo.push(LevelsCmd(items, *new))
		for it in styleto:
			before = {k: getattr(it, k) for k in style}
			it.setprops(style)
			self.undo.push(PropsCmd(it, before, style))
		self.undo.endMacro()

	def editshape(self, it):
		"""the dialog for the properties of rectangle, line, arrow or circle
		it; the drawing shows the changes while it is open"""
		before = allprops(it)
		dlg = RectDialog(it, self) if isinstance(it, RectShape) else ShapeDialog(it, self)
		self.shapedlg = dlg	# for the tests
		dlg.changed.connect(lambda: it.setprops(dlg.props()))
		ok = dlg.exec() == QDialog.DialogCode.Accepted
		after = dict(before)
		after.update(dlg.props())
		dlg.deleteLater()
		saveas = dlg.name() if ok else ""
		if ok and after != before:
			self.undo.push(PropsCmd(it, before, after))
		elif not ok:
			it.setprops(before)
		if saveas:
			preset = {"color": it.color, "width": it.width, "dash": it.dash}
			preset.update({k: v for k, v in after.items() if k != "size"})
			self.shapesaved.emit(it.kind, saveas, preset)
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
		self.refreshcross()

	def realsize(self):
		if self.pixitem:
			self.mode = "real"
			self.resetTransform()
			self.refreshcross()

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
		self.refreshcross()

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
		else:
			self.setDragMode(QGraphicsView.DragMode.NoDrag)
		self.setcursor()
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

	def setfiblevels(self, levels, diagonal=False, from2=False, style=None):
		"""the levels for the next fibs, and for the fibs selected, whether
		they have their diagonal, whether their lines start at the second
		point, and their width and dash (style; the bar's when not there)"""
		self.fiblevels = list(levels)
		self.fibdiagonal = diagonal
		self.fibfrom2 = from2
		self.fibstyle = dict(style or {})
		sel = [it for it in self.scene().selectedItems() if isinstance(it, FibShape)]
		if sel:
			self.applyfib(sel, levels, diagonal, from2, style)

	def setrectpreset(self, preset):
		self.setpreset("rect", preset)

	def setpreset(self, kind, preset):
		"""the look for the next shapes of kind (rect, line, arrow, circle: a
		RECTSETS entry or one saved; None for the plain one), and for the
		ones selected"""
		self.presets[kind] = dict(preset) if preset else None
		if kind == "rect":
			self.rectpreset = self.presets[kind]
		sel = [it for it in self.scene().selectedItems() if getattr(it, "kind", "") == kind]
		self.applypreset(sel, preset)

	def applypreset(self, items, preset):
		"""the look preset for the shapes items, in one undo step"""
		if not items or not preset:
			return
		self.undo.beginMacro("Change drawings")
		for it in items:
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
		if self.tool != "select" and self.hidden:
			self.setdrawingsshown(True)	# drawing shows them again
		if self.tool == "select":
			h = self.handleat(ev.position().toPoint())
			if h is not None:
				self.reshaping = (h[0], h[1], h[0].geom())
				return
			super().mousePressEvent(ev)
			self.pressed = {it: it.pos() for it in self.scene().selectedItems()}
			return
		focus = self.scene().focusItem()
		if focus is not None:
			focus.clearFocus()	# ends editing a text
		self.scene().clearSelection()
		if self.tool in ("line", "arrow"):
			d = {"dash": self.dash, "size": self.textsize}
			d.update(self.presets.get(self.tool) or {})
			self.drawing = LineShape(p, p, d.pop("color", self.color), d.pop("width", self.width),
				self.tool == "arrow", **d)
		elif self.tool == "pencil":
			self.drawing = PencilShape([p], self.color, self.width, self.dash)
		elif self.tool == "circle":
			d = {"dash": self.dash, "size": self.textsize}
			d.update(self.presets.get("circle") or {})
			self.drawing = CircleShape(QRectF(p, p), d.pop("color", self.color), d.pop("width", self.width), **d)
		elif self.tool == "rect":
			d = {"dash": self.dash, "size": self.textsize}
			d.update(self.rectpreset or {})
			self.drawing = RectShape(QRectF(p, p), d.pop("color", self.color), d.pop("width", self.width), **d)
		elif self.tool == "fib":
			self.drawing = FibShape(p, p, self.fiblevels, self.color, self.fibstyle.get("width", self.width),
				diagonal=self.fibdiagonal, dash=self.fibstyle.get("dash", self.dash), size=self.textsize, from2=self.fibfrom2)
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
			self.setcross(None)
			self.drawto(ev)
			return
		if self.reshaping is not None:
			it, i, start = self.reshaping
			it.movehandle(i, self.clamp(self.mapToScene(ev.position().toPoint())), start,
				bool(ev.modifiers() & Qt.KeyboardModifier.ShiftModifier))
			self.viewport().update()
			return
		super().mouseMoveEvent(ev)
		if ev.buttons() != Qt.MouseButton.NoButton and self.scene().selectedItems():
			self.viewport().update()	# the handles go with what is dragged
		elif self.tool == "select" and ev.buttons() == Qt.MouseButton.NoButton:
			if self.handleat(ev.position().toPoint()) is not None:
				self.viewport().setCursor(Qt.CursorShape.SizeAllCursor)
			else:
				self.setcursor()
		self.setcross(self.crossat(ev.position().toPoint(), ev.buttons()))

	# ---- handles: the points of a drawing selected that can be dragged to reshape it ----
	def handleat(self, at):
		"""(item, handle number) of the handle at viewport point at, or None"""
		if self.tool != "select" or self.pixitem is None:
			return None
		best = None
		for it in self.scene().selectedItems():
			if not hasattr(it, "handles"):
				continue
			for i, h in enumerate(it.handles()):
				v = self.mapFromScene(h)
				d = max(abs(v.x() - at.x()), abs(v.y() - at.y()))
				if d <= HANDLE and (best is None or d < best[0]):
					best = (d, it, i)
		return best[1:] if best else None

	def drawhandles(self, painter):
		items = [it for it in self.scene().selectedItems() if hasattr(it, "handles")]
		if not items or self.tool != "select":
			return
		painter.save()
		painter.resetTransform()	# in pixels, whatever the zoom
		painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
		painter.setPen(QPen(QColor(30, 120, 255), 1))
		painter.setBrush(QColor(255, 255, 255))
		s = HANDLE - 1
		for it in items:
			for h in it.handles():
				v = self.mapFromScene(h)
				painter.drawRect(QRect(v.x() - s // 2, v.y() - s // 2, s, s))
		painter.restore()

	# ---- copying ----
	def renderimage(self):
		"""the image with its drawings, at the image's size, or None"""
		if self.pixitem is None:
			return None
		self.commitedit()
		r = self.sceneRect()
		img = QImage(int(r.width()), int(r.height()), QImage.Format.Format_ARGB32)
		img.fill(Qt.GlobalColor.white)
		sel = self.scene().selectedItems()
		for it in sel:	# without the selection handles
			it.setSelected(False)
		p = QPainter(img)
		p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
		self.scene().render(p, QRectF(img.rect()), r)
		p.end()
		for it in sel:
			it.setSelected(True)
		return img

	def copyimage(self):
		"""put the image, with its drawings, on the clipboard, to paste it
		in other programs"""
		img = self.renderimage()
		if img is None:
			return False
		QApplication.clipboard().setImage(img)
		return True

	# ---- crosshair ----
	def setcrosshair(self, on):
		self.crosshair = bool(on)
		self.setcursor()
		self.setcross(self.crossat() if on else None)
		self.crosschanged.emit(self.crosshair)

	def crossat(self, at=None, buttons=None):
		"""where the crosshair goes for the mouse at viewport point at (where
		the mouse is), or None: off, out of the image, or while editing
		(drawing, dragging, writing a text)"""
		if not self.crosshair or self.pixitem is None or self.drawing is not None:
			return None
		if at is None:
			at = self.viewport().mapFromGlobal(QCursor.pos())
			if not self.viewport().rect().contains(at):
				return None
		if buttons is None:
			buttons = QApplication.mouseButtons()
		if buttons != Qt.MouseButton.NoButton:
			return None
		f = self.scene().focusItem()
		if isinstance(f, TextShape) and f.editing():
			return None
		p = self.mapToScene(at)
		return QPointF(p) if self.sceneRect().contains(p) else None

	def setcross(self, p):
		if p == self.cross:
			return
		old, self.cross = self.cross, p
		for q in (old, p):	# repaint just the lines
			if q is not None:
				v = self.mapFromScene(q)
				w = self.viewport().rect()
				self.viewport().update(QRect(w.left(), v.y() - 2, w.width(), 5))
				self.viewport().update(QRect(v.x() - 2, w.top(), 5, w.height()))

	def drawForeground(self, painter, rect):
		super().drawForeground(painter, rect)
		self.drawhandles(painter)
		p = self.cross
		if p is None:
			return
		r = self.sceneRect()
		painter.save()
		# white lines in difference mode show on light and dark charts alike
		painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Difference)
		pen = QPen(QColor(255, 255, 255, 200), 1)
		pen.setCosmetic(True)
		pen.setStyle(Qt.PenStyle.DashLine)
		painter.setPen(pen)
		painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
		painter.drawLine(QPointF(r.left(), p.y()), QPointF(r.right(), p.y()))
		painter.drawLine(QPointF(p.x(), r.top()), QPointF(p.x(), r.bottom()))
		painter.restore()

	def scrollContentsBy(self, dx, dy):
		super().scrollContentsBy(dx, dy)
		self.refreshcross()

	def refreshcross(self):
		"""the image moved or zoomed under the mouse"""
		if self.cross is not None or self.crosshair:
			self.cross = self.crossat()
			self.viewport().update()

	def setcursor(self):
		"""a cross on the image while the crosshair is on; else the hand
		to drag the image, or the cross to draw"""
		cross = self.tool != "select" or self.crosshair
		self.viewport().setCursor(Qt.CursorShape.CrossCursor if cross else Qt.CursorShape.OpenHandCursor)

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
		if self.reshaping is not None:
			it, _, start = self.reshaping
			self.reshaping = None
			if it.geom() != start:
				self.undo.push(GeomCmd(it, start, it.geom()))
			self.viewport().update()
			return
		super().mouseReleaseEvent(ev)
		if self.tool == "select":
			self.setcursor()	# the hand drag puts its own back
			self.setcross(self.crossat(ev.position().toPoint(), ev.buttons()))
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

	def contextMenuEvent(self, ev):
		"""the right button on a drawing: a menu with the configurations of
		its kind (the fib levels, the looks saved), to change it, and the
		other ones of its kind selected, to the one picked"""
		if self.drawing is not None or self.presetmenu is None:
			return super().contextMenuEvent(ev)
		shapes = set(self.shapes())
		it = next((i for i in self.items(ev.pos()) if i in shapes), None)
		if it is None:
			return super().contextMenuEvent(ev)
		if not it.isSelected():
			self.scene().clearSelection()
			it.setSelected(True)
		items = [i for i in self.scene().selectedItems() if getattr(i, "kind", "") == it.kind]
		m = QMenu(self)
		self.presetmenu(m, it.kind, items)
		if m.isEmpty():
			m.deleteLater()
			return super().contextMenuEvent(ev)
		self.ctxmenu = m	# for the tests
		m.exec(ev.globalPos())
		self.ctxmenu = None
		m.deleteLater()

	def zoomstep(self, at):
		"""zoom in at viewport point at, zoom in again, then fit"""
		if self.dstep < 2:
			self.dstep += 1
			self.zoom(DCLICKZOOM, at)
		else:
			self.fit()

	def viewportEvent(self, ev):
		if ev.type() == QEvent.Type.Leave:
			self.setcross(None)
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

	# ---- copying and pasting drawings ----
	def copydrawings(self):
		"""put the drawings selected on the clipboard; whether there were any"""
		sel = [it for it in self.shapes() if it.isSelected()]
		if not sel:
			return False
		md = QMimeData()
		md.setData(DRAWMIME, json.dumps({"version": DRAWVERSION, "shapes": [it.todict() for it in sel]}).encode())
		QApplication.clipboard().setMimeData(md)
		return True

	def clipdrawings(self):
		"""the drawings on the clipboard, as saved, or []"""
		md = QApplication.clipboard().mimeData()
		if md is None or not md.hasFormat(DRAWMIME):
			return []
		try:
			shapes = json.loads(bytes(md.data(DRAWMIME)).decode()).get("shapes", [])
		except (ValueError, AttributeError):
			return []
		return [d for d in shapes if isinstance(d, dict)]

	def pastedrawings(self, at=None):
		"""add the drawings on the clipboard, centered at scene point at (the
		mouse, when it is on the image), selected; whether there were any"""
		if self.pixitem is None:
			return False
		items = [it for it in map(fromdict, self.clipdrawings()) if it is not None]
		if not items:
			return False
		if self.hidden:
			self.setdrawingsshown(True)
		box = QRectF()
		for it in items:
			box = box.united(it.mapRectToScene(it.boundingRect()))
		if at is None:
			v = self.viewport().mapFromGlobal(QCursor.pos())
			at = self.mapToScene(v) if self.viewport().rect().contains(v) else None
		if at is None or not self.sceneRect().contains(at):
			at = box.center() + QPointF(20, 20)	# next to where it was
		off = at - box.center()
		self.scene().clearSelection()
		self.undo.beginMacro("Paste")
		for it in items:
			it.setPos(it.pos() + off)
			self.additem(it)
			it.setSelected(True)
			self.undo.push(AddCmd(self.scene(), it))
		self.undo.endMacro()
		return True

	def clipkey(self, ev):
		"""copy or paste, for key event ev, or None"""
		mac = ev.modifiers() & ~Qt.KeyboardModifier.KeypadModifier == Qt.KeyboardModifier.MetaModifier	# control on macOS
		if ev.matches(QKeySequence.StandardKey.Copy) or (mac and ev.key() == Qt.Key.Key_C):
			return "copy"
		if ev.matches(QKeySequence.StandardKey.Paste) or (mac and ev.key() == Qt.Key.Key_V):
			return "paste"
		return None

	def event(self, ev):
		# copy and paste of drawings come here before the window's shortcuts
		if ev.type() == QEvent.Type.ShortcutOverride:
			f = self.scene().focusItem()
			c = self.clipkey(ev)
			if not (isinstance(f, TextShape) and f.editing()) and (
					(c == "copy" and any(it.isSelected() for it in self.shapes()))
					or (c == "paste" and self.pixitem is not None and self.clipdrawings())):
				ev.accept()
				return True
		return super().event(ev)

	# ---- keys ----
	def keyPressEvent(self, ev):
		f = self.scene().focusItem()
		if isinstance(f, TextShape) and f.editing():
			super().keyPressEvent(ev)	# typing in a text box
			return
		c = self.clipkey(ev)
		if (c == "copy" and self.copydrawings()) or (c == "paste" and self.pastedrawings()):
			return
		k = ev.key()
		nav = self.navkeys
		# macOS marks the arrow keys as keypad keys
		plain = ev.modifiers() & ~Qt.KeyboardModifier.KeypadModifier == Qt.KeyboardModifier.NoModifier
		if k in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
			if self.delkey is None or not self.delkey():
				self.deleteselected()
		elif k == Qt.Key.Key_Escape:
			self.cancelfib()
			self.scene().clearSelection()
			self.settool("select")
		elif k == Qt.Key.Key_H and ev.modifiers() == Qt.KeyboardModifier.NoModifier:
			self.togglehidden()
		elif k in TOOLKEYS and ev.modifiers() == Qt.KeyboardModifier.NoModifier:
			self.settool(TOOLKEYS[k])
		elif k in nav and plain:
			self.navigate.emit(nav[k])
		else:
			super().keyPressEvent(ev)

ALIGNS = (("Center", "center"), ("Left", "left"), ("Right", "right"))

def namerow(dlg, form, menu, taken):
	"""the Save as field of the form for a shape: a name to keep its look
	in the menu of its tool"""
	dlg.namebox = QLineEdit()
	dlg.namebox.setPlaceholderText(f"to keep this look in the {menu} menu")
	dlg.namebox.setToolTip(f"a short name, like OB; how it looks (color, width, style, label...) is "
		f"saved under it and shows up in the {menu} menu. The same name replaces it")
	form.addRow("Save as:", dlg.namebox)
	dlg.taken = taken

def nametaken(dlg):
	"""warn when the name given is one of the built-in ones"""
	if dlg.name() in dlg.taken:
		QMessageBox.warning(dlg, dlg.windowTitle(), f"{dlg.name()} is already in the menu; use another name.")
		return True
	return False

class RectDialog(QDialog):
	"""asks for the border width and style, fill, middle line and label of a
	rectangle; changed is emitted on every change, to show it"""
	changed = Signal()

	def __init__(self, it, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Rectangle")
		self.fillcolor = it.fill or it.color
		form = QFormLayout(self)
		self.width = combo([(f"{w:g} px", w) for w in WIDTHS], it.width)
		form.addRow("Width:", self.width)
		self.dash = combo(DASHNAMES, it.dash)
		form.addRow("Style:", self.dash)
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
		namerow(self, form, "Rect", set(RECTSETS) | {"Plain"})
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
				self.label.textChanged, self.align.currentIndexChanged, self.labelcolor.picked,
				self.width.currentIndexChanged, self.dash.currentIndexChanged):
			sig.connect(lambda *_: self.changed.emit())

	def name(self):
		return " ".join(self.namebox.text().split())

	def accept(self):
		if nametaken(self):
			return
		super().accept()

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
		old = self.fillcolor
		def show(c):
			self.fillcolor = c
			self.showcolor()
			self.changed.emit()
		show(pickcolor(old, self, "Fill color", show) or old)

	def props(self):
		return {"width": self.width.currentData(), "dash": self.dash.currentData(),
			"fill": self.fillcolor if self.fillbox.isChecked() else None,
			"alpha": round((100 - self.alpha.value()) * 255 / 100),
			"middle": self.middlebox.isChecked(), "label": self.label.text().strip(),
			"align": self.align.currentData(),
			"midcolor": None if self.midcolor.color == self.color else self.midcolor.color,
			"labelcolor": None if self.labelcolor.color == self.color else self.labelcolor.color}

def pickcolor(color, parent, title, show):
	"""ask for a color, starting at color: its name, or None. show(name) is
	called as the color changes in the dialog, to show it; the caller puts
	back what was there when it gives None"""
	dlg = QColorDialog(QColor(color), parent)
	dlg.setWindowTitle(title)
	dlg.currentColorChanged.connect(lambda c: c.isValid() and show(c.name()))
	parent.colordlg = dlg	# for the tests
	ok = dlg.exec() == QDialog.DialogCode.Accepted
	c = dlg.selectedColor()
	parent.colordlg = None
	dlg.deleteLater()
	return c.name() if ok and c.isValid() else None

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
		old = self.color
		def show(c):
			self.setcolor(c)
			self.picked.emit()
		c = pickcolor(old, self, self.title, show)
		if c is None:
			show(old)

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
		self.extend = None
		if it.kind == "line":
			self.extend = QCheckBox("Extend across the image")
			self.extend.setChecked(it.extend)
			self.extend.setToolTip("a horizontal line goes to the left and right edges, a vertical one "
				"to the top and bottom, any other to where it meets the edges")
			form.addRow("", self.extend)
			self.extend.toggled.connect(lambda *_: self.changed.emit())
			# extended, Left and Right put the label at that end; Top and Bottom for a vertical line
			vertical = it.vertical()
			def relabel(on):
				names = ("Center", "Top", "Bottom") if on and vertical else [n for n, _ in ALIGNS]
				for i, n in enumerate(names):
					self.align.setItemText(i, n)
				self.align.setToolTip("at the end of the line extended, the line stopping before it" if on else
					"at its left, in its middle, or at its right, past its end")
			self.extend.toggled.connect(relabel)
			relabel(it.extend)
		namerow(self, form, {"line": "Line", "arrow": "Arrow", "circle": "Circle"}.get(it.kind, "Line"), {"Plain"})
		bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
		bb.accepted.connect(self.accept)
		bb.rejected.connect(self.reject)
		form.addRow(bb)
		for sig in (self.color.picked, self.width.currentIndexChanged, self.dash.currentIndexChanged,
				self.label.textChanged, self.valign.currentIndexChanged, self.align.currentIndexChanged,
				self.size.currentIndexChanged, self.labelcolor.picked):
			sig.connect(lambda *_: self.changed.emit())

	def name(self):
		return " ".join(self.namebox.text().split())

	def accept(self):
		if nametaken(self):
			return
		super().accept()

	def colorpicked(self):
		if self.labelsame:
			self.labelcolor.setcolor(self.color.color)

	def labelpicked(self):
		self.labelsame = False

	def props(self):
		return {"color": self.color.color, "width": self.width.currentData(), "dash": self.dash.currentData(),
			"label": self.label.text().strip(), "valign": self.valign.currentData(),
			"align": self.align.currentData(), "size": self.size.currentData(),
			"labelcolor": None if self.labelsame else self.labelcolor.color} | (
			{"extend": self.extend.isChecked()} if self.extend is not None else {})
