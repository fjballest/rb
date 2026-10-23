#
# drawings on top of an image: lines, arrows, circles and text boxes, in
# image coordinates, with the undo commands that change them and their
# JSON form, kept in a file next to the image (see Journal.drawpath)
#
import math

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainterPath, QPainterPathStroker, QPen, QPolygonF, QUndoCommand
from PySide6.QtWidgets import (
	QGraphicsEllipseItem, QGraphicsItem, QGraphicsLineItem, QGraphicsPathItem, QGraphicsTextItem, QStyle
)

DRAWVERSION = 1
KINDS = ("line", "arrow", "circle", "text", "pencil")
FLAGS = (QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
ZDRAW = 10

def mkpen(color, width):
	p = QPen(QColor(color), width)
	p.setCapStyle(Qt.PenCapStyle.RoundCap)
	p.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
	return p

class LineShape(QGraphicsLineItem):
	"""a line, with a head at its end when arrow"""
	def __init__(self, p1, p2, color, width, arrow=False):
		super().__init__(QLineF(p1, p2))
		self.kind = "arrow" if arrow else "line"
		self.color = color
		self.width = width
		self.setPen(mkpen(color, width))
		self.setFlags(FLAGS)
		self.setZValue(ZDRAW)

	def setstyle(self, color, width):
		self.prepareGeometryChange()
		self.color, self.width = color, width
		self.setPen(mkpen(color, width))

	def head(self):
		l = self.line()
		if self.kind != "arrow" or l.length() < 1:
			return None
		size = max(16.0, self.width * 5)
		a = math.atan2(l.dy(), l.dx())
		p = l.p2()
		left = p - QPointF(math.cos(a - math.pi / 7) * size, math.sin(a - math.pi / 7) * size)
		right = p - QPointF(math.cos(a + math.pi / 7) * size, math.sin(a + math.pi / 7) * size)
		return QPolygonF([p, left, right])

	def boundingRect(self):
		r = super().boundingRect()
		h = self.head()
		if h is not None:
			r = r.united(h.boundingRect())
		m = self.width * 2 + 2
		return r.adjusted(-m, -m, m, m)

	def shape(self):
		path = QPainterPath()
		l = self.line()
		path.moveTo(l.p1())
		path.lineTo(l.p2())
		s = QPainterPathStroker()
		s.setWidth(max(self.width, 1) + 8)	# easier to pick
		path = s.createStroke(path)
		h = self.head()
		if h is not None:
			path.addPolygon(h)
		return path

	def paint(self, painter, option, widget=None):
		painter.setRenderHint(painter.RenderHint.Antialiasing)
		pen = self.pen()
		painter.setPen(pen)
		l = self.line()
		h = self.head()
		if h is not None:
			# stop the line at the base of the head, so its end stays sharp
			base = (h[1] + h[2]) / 2
			painter.drawLine(l.p1(), base)
			painter.setBrush(QBrush(QColor(self.color)))
			painter.setPen(mkpen(self.color, 1))
			painter.drawPolygon(h)
		else:
			painter.drawLine(l)
		if self.isSelected():
			selpen(painter)
			painter.setBrush(Qt.BrushStyle.NoBrush)
			painter.drawPath(self.shape())

	def todict(self):
		l = self.line()
		p1, p2 = self.mapToScene(l.p1()), self.mapToScene(l.p2())
		return {"kind": self.kind, "p1": pt(p1), "p2": pt(p2), "color": self.color, "width": self.width}

	def setend(self, p):
		self.prepareGeometryChange()
		self.setLine(QLineF(self.line().p1(), self.mapFromScene(p)))

	def small(self):
		return self.line().length() < 4

class CircleShape(QGraphicsEllipseItem):
	def __init__(self, rect, color, width):
		super().__init__(rect)
		self.kind = "circle"
		self.color = color
		self.width = width
		self.origin = rect.topLeft()
		self.setPen(mkpen(color, width))
		self.setFlags(FLAGS)
		self.setZValue(ZDRAW)

	def setstyle(self, color, width):
		self.prepareGeometryChange()
		self.color, self.width = color, width
		self.setPen(mkpen(color, width))

	def shape(self):
		# its outline, so the inside doesn't hide what is under it
		path = QPainterPath()
		path.addEllipse(self.rect())
		s = QPainterPathStroker()
		s.setWidth(max(self.width, 1) + 8)
		return s.createStroke(path)

	def paint(self, painter, option, widget=None):
		painter.setRenderHint(painter.RenderHint.Antialiasing)
		painter.setPen(self.pen())
		painter.setBrush(Qt.BrushStyle.NoBrush)
		painter.drawEllipse(self.rect())
		if self.isSelected():
			selpen(painter)
			painter.drawRect(self.rect())

	def todict(self):
		return {"kind": "circle", "rect": rct(self.mapRectToScene(self.rect())),
			"color": self.color, "width": self.width}

	def setend(self, p):
		self.prepareGeometryChange()
		self.setRect(QRectF(self.origin, self.mapFromScene(p)).normalized())

	def small(self):
		r = self.rect()
		return r.width() < 4 and r.height() < 4

class PencilShape(QGraphicsPathItem):
	"""a free hand stroke"""
	MINSTEP = 1.5	# image pixels between the points kept

	def __init__(self, points, color, width):
		super().__init__()
		self.kind = "pencil"
		self.color = color
		self.width = width
		self.points = [QPointF(p) for p in points]
		self.setPen(mkpen(color, width))
		self.setFlags(FLAGS)
		self.setZValue(ZDRAW)
		self.rebuild()

	def rebuild(self):
		path = QPainterPath()
		if self.points:
			path.moveTo(self.points[0])
			if len(self.points) == 1:
				path.lineTo(self.points[0])
			# smooth: quadratic curves through the midpoints
			for a, b in zip(self.points[1:], self.points[2:]):
				path.quadTo(a, (a + b) / 2)
			if len(self.points) > 1:
				path.lineTo(self.points[-1])
		self.setPath(path)

	def setstyle(self, color, width):
		self.prepareGeometryChange()
		self.color, self.width = color, width
		self.setPen(mkpen(color, width))

	def shape(self):
		s = QPainterPathStroker()
		s.setWidth(max(self.width, 1) + 8)
		s.setCapStyle(Qt.PenCapStyle.RoundCap)
		return s.createStroke(self.path())

	def paint(self, painter, option, widget=None):
		painter.setRenderHint(painter.RenderHint.Antialiasing)
		painter.setPen(self.pen())
		painter.setBrush(Qt.BrushStyle.NoBrush)
		painter.drawPath(self.path())
		if self.isSelected():
			selpen(painter)
			painter.drawRect(self.path().boundingRect())

	def setend(self, p):
		p = self.mapFromScene(p)
		if self.points and QLineF(self.points[-1], p).length() < self.MINSTEP:
			return
		self.points.append(p)
		self.rebuild()

	def todict(self):
		return {"kind": "pencil", "points": [pt(self.mapToScene(p)) for p in self.points],
			"color": self.color, "width": self.width}

	def small(self):
		r = self.path().boundingRect()
		return r.width() < 3 and r.height() < 3

class TextShape(QGraphicsTextItem):
	"""a text box: text on a light background with a frame. Double click
	to edit it; edited is called with the text before and after"""
	def __init__(self, pos, text, color, size):
		super().__init__(text)
		self.kind = "text"
		self.color = color
		self.size = size
		self.width = 1
		self.edited = None
		self.before = text
		self.setPos(pos)
		self.setDefaultTextColor(QColor(color))
		f = QFont()
		f.setPixelSize(size)
		self.setFont(f)
		self.setFlags(FLAGS | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
		self.setZValue(ZDRAW + 1)

	def setstyle(self, color, width):
		self.color = color
		self.setDefaultTextColor(QColor(color))
		self.update()

	def setsize(self, size):
		self.prepareGeometryChange()
		self.size = size
		f = self.font()
		f.setPixelSize(size)
		self.setFont(f)

	def paint(self, painter, option, widget=None):
		r = self.boundingRect()
		painter.setPen(mkpen(self.color, 1))
		painter.setBrush(QColor(255, 255, 255, 215))
		painter.drawRect(r.adjusted(0.5, 0.5, -0.5, -0.5))
		option.state &= ~QStyle.StateFlag.State_Selected	# no dashed frame from Qt
		super().paint(painter, option, widget)
		if self.isSelected():
			selpen(painter)
			painter.setBrush(Qt.BrushStyle.NoBrush)
			painter.drawRect(r.adjusted(-2, -2, 2, 2))

	def editing(self):
		return self.textInteractionFlags() != Qt.TextInteractionFlag.NoTextInteraction

	def startedit(self):
		self.before = self.toPlainText()
		self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
		self.setFocus()
		c = self.textCursor()
		c.select(c.SelectionType.Document)
		self.setTextCursor(c)

	def mouseDoubleClickEvent(self, ev):
		if not self.editing():
			self.startedit()
			return
		super().mouseDoubleClickEvent(ev)

	def keyPressEvent(self, ev):
		if ev.key() == Qt.Key.Key_Escape:
			self.clearFocus()
			return
		super().keyPressEvent(ev)

	def focusOutEvent(self, ev):
		super().focusOutEvent(ev)
		if not self.editing():
			return
		self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
		c = self.textCursor()
		c.clearSelection()
		self.setTextCursor(c)
		after = self.toPlainText()
		if self.edited is not None:
			self.edited(self, self.before, after)

	def todict(self):
		return {"kind": "text", "pos": pt(self.scenePos()), "text": self.toPlainText(),
			"color": self.color, "size": self.size}

	def small(self):
		return False

def selpen(painter):
	p = QPen(QColor(30, 120, 255), 0, Qt.PenStyle.DashLine)
	painter.setPen(p)

def pt(p):
	return [round(p.x(), 1), round(p.y(), 1)]

def rct(r):
	return [round(r.x(), 1), round(r.y(), 1), round(r.width(), 1), round(r.height(), 1)]

def fromdict(d):
	"""the item for a shape saved by todict, or None"""
	k = d.get("kind")
	color = d.get("color", "#e53935")
	try:
		if k in ("line", "arrow"):
			return LineShape(QPointF(*d["p1"]), QPointF(*d["p2"]), color, float(d.get("width", 3)), k == "arrow")
		if k == "circle":
			return CircleShape(QRectF(*d["rect"]), color, float(d.get("width", 3)))
		if k == "pencil":
			pts = [QPointF(*p) for p in d["points"]]
			return PencilShape(pts, color, float(d.get("width", 3))) if pts else None
		if k == "text":
			return TextShape(QPointF(*d["pos"]), str(d.get("text", "")), color, int(d.get("size", 18)))
	except (KeyError, TypeError, ValueError):
		pass
	return None

# ---- undo commands ----

class AddCmd(QUndoCommand):
	def __init__(self, scene, item, text="Add"):
		super().__init__(f"{text} {item.kind}")
		self.scene, self.item = scene, item
		self.first = item.scene() is scene	# drawn already

	def redo(self):
		if self.first:
			self.first = False
			return
		self.scene.addItem(self.item)

	def undo(self):
		self.item.setSelected(False)
		self.scene.removeItem(self.item)

class DeleteCmd(QUndoCommand):
	def __init__(self, scene, items):
		super().__init__("Delete")
		self.scene, self.items = scene, list(items)

	def redo(self):
		for it in self.items:
			it.setSelected(False)
			self.scene.removeItem(it)

	def undo(self):
		for it in self.items:
			self.scene.addItem(it)

class MoveCmd(QUndoCommand):
	def __init__(self, moves):
		super().__init__("Move")
		self.moves = moves	# [(item, old pos, new pos)]
		self.first = True

	def redo(self):
		if self.first:
			self.first = False
			return
		for it, _, new in self.moves:
			it.setPos(new)

	def undo(self):
		for it, old, _ in self.moves:
			it.setPos(old)

class TextCmd(QUndoCommand):
	def __init__(self, item, before, after):
		super().__init__("Edit text")
		self.item, self.before, self.after = item, before, after
		self.first = True

	def redo(self):
		if self.first:
			self.first = False
			return
		self.item.setPlainText(self.after)

	def undo(self):
		self.item.setPlainText(self.before)

class StyleCmd(QUndoCommand):
	"""a new color or width (None keeps the old one) for items"""
	def __init__(self, items, color, width):
		super().__init__("Change style")
		self.changes = [(it, it.color, it.width) for it in items]
		self.color, self.width = color, width

	def redo(self):
		for it, c, w in self.changes:
			it.setstyle(self.color or c, self.width if self.width is not None else w)

	def undo(self):
		for it, c, w in self.changes:
			it.setstyle(c, w)
