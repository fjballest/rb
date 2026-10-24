#
# drawings on top of an image: lines, arrows, circles, rectangles, text
# boxes and Fibonacci levels, in
# image coordinates, with the undo commands that change them and their
# JSON form, kept in a file next to the image (see Journal.drawpath)
#
import math

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainterPath, QPainterPathStroker, QPen, QPolygonF, QUndoCommand
from PySide6.QtWidgets import (
	QGraphicsEllipseItem, QGraphicsItem, QGraphicsLineItem, QGraphicsPathItem, QGraphicsRectItem, QGraphicsTextItem,
	QStyle
)

DRAWVERSION = 1
KINDS = ("line", "arrow", "circle", "rect", "text", "pencil", "fib")
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

class RectShape(QGraphicsRectItem):
	"""a rectangle: its border, and optionally a fill (fill color and alpha,
	0 to 255), a dashed line across its middle, and a label at its top,
	aligned left, center or right. Double click calls edit(self)"""
	LABELSIZE = 16
	PROPS = ("fill", "alpha", "middle", "label", "align")

	def __init__(self, rect, color, width, fill=None, alpha=64, middle=False, label="", align="center"):
		super().__init__(rect)
		self.kind = "rect"
		self.color = color
		self.width = width
		self.fill, self.alpha, self.middle, self.label, self.align = fill, alpha, middle, label, align
		self.origin = rect.topLeft()
		self.edit = None
		self.setFlags(FLAGS)
		self.setZValue(ZDRAW)

	def props(self):
		return {k: getattr(self, k) for k in self.PROPS}

	def setprops(self, d):
		self.prepareGeometryChange()
		for k in self.PROPS:
			if k in d:
				setattr(self, k, d[k])
		self.update()

	def setstyle(self, color, width):
		self.prepareGeometryChange()
		self.color, self.width = color, width
		self.update()

	def font(self):
		f = QFont()
		f.setPixelSize(self.LABELSIZE)
		f.setBold(True)
		return f

	def labelrect(self):
		"""where the label goes: inside the top of the rectangle, or just
		above it when the rectangle is too low for it"""
		r = self.rect()
		h = self.LABELSIZE * 1.4
		m = self.width / 2 + 3
		if r.height() >= h + 2 * m:
			return QRectF(r.left() + m, r.top() + m, max(r.width() - 2 * m, 1), h)
		return QRectF(r.left(), r.top() - h - 1, max(r.width(), 1), h)

	def boundingRect(self):
		m = self.width * 2 + 2
		r = self.rect().adjusted(-m, -m, m, m)
		if self.label:
			lr = self.labelrect()
			extra = max(0.0, QFontMetricsF(self.font()).horizontalAdvance(self.label) - lr.width()) + 2
			r = r.united(lr.adjusted(-extra, 0, extra, 0))
		return r

	def shape(self):
		# its border, so the inside doesn't hide what is under it, unless filled
		path = QPainterPath()
		path.addRect(self.rect())
		if self.fill:
			return path
		s = QPainterPathStroker()
		s.setWidth(max(self.width, 1) + 8)
		return s.createStroke(path)

	def paint(self, painter, option, widget=None):
		painter.setRenderHint(painter.RenderHint.Antialiasing)
		r = self.rect()
		if self.fill:
			c = QColor(self.fill)
			c.setAlpha(int(self.alpha))
			painter.fillRect(r, c)
		painter.setPen(mkpen(self.color, self.width))
		painter.setBrush(Qt.BrushStyle.NoBrush)
		painter.drawRect(r)
		if self.middle:
			pen = mkpen(self.color, max(1.0, self.width / 2))
			pen.setStyle(Qt.PenStyle.DashLine)
			painter.setPen(pen)
			y = r.center().y()
			painter.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
		if self.label:
			painter.setFont(self.font())
			painter.setPen(QColor(self.color))
			al = {"left": Qt.AlignmentFlag.AlignLeft, "right": Qt.AlignmentFlag.AlignRight}.get(
				self.align, Qt.AlignmentFlag.AlignHCenter)
			# a label wider than the rectangle goes out of it, by the side it's aligned to
			painter.drawText(self.labelrect(), al | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextDontClip, self.label)
		if self.isSelected():
			selpen(painter)
			painter.drawRect(r.adjusted(-3, -3, 3, 3))

	def mouseDoubleClickEvent(self, ev):
		if self.edit is not None:
			self.edit(self)
			return
		super().mouseDoubleClickEvent(ev)

	def todict(self):
		d = {"kind": "rect", "rect": rct(self.mapRectToScene(self.rect())), "color": self.color, "width": self.width}
		if self.fill:
			d["fill"], d["alpha"] = self.fill, self.alpha
		if self.middle:
			d["middle"] = True
		if self.label:
			d["label"], d["align"] = self.label, self.align
		return d

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

# the level sets for Fibonacci drawings: 0 is at the second point, 1 at the first
FIBSETS = {
	"OTE": (0.5, 0.62, 0.705, 0.79),
	"Quadrants": (0, 0.25, 0.5, 0.75, 1),
	"PO3": (-2.5, -2, -1.5, -1, -0.5, 0, 0.25, 0.5, 0.75, 1, 1.5, 2, 2.5, 3, 3.5),
}
FIBALL = tuple(sorted({l for ls in FIBSETS.values() for l in ls}))	# where Custom starts

def parselevels(text):
	"""the levels in text, numbers separated by spaces or commas, sorted;
	ValueError if one is not a number or there are none"""
	ls = sorted({float(x) for x in text.replace(",", " ").split()})
	if not ls:
		raise ValueError("no levels")
	return ls

def fmtlevels(levels):
	return " ".join(f"{l:g}" for l in levels)

class FibShape(QGraphicsItem):
	"""Fibonacci levels between p1 (level 1) and p2 (level 0): a horizontal
	line for each level, from the left point to right, or to the right
	edge of the image when extend"""
	LABELSIZE = 14

	def __init__(self, p1, p2, levels, color, width, right=None, extend=False):
		super().__init__()
		self.kind = "fib"
		self.p1, self.p2 = QPointF(p1), QPointF(p2)
		self.levels = list(levels)
		self.color = color
		self.width = width
		self.right = max(p1.x(), p2.x()) if right is None else right
		self.extend = extend
		self.setFlags(FLAGS)
		self.setZValue(ZDRAW)

	def setstyle(self, color, width):
		self.prepareGeometryChange()
		self.color, self.width = color, width
		self.update()

	def setlevels(self, levels):
		self.prepareGeometryChange()
		self.levels = list(levels)
		self.update()

	def setend(self, p):
		"""move the second point; the lines end there for now"""
		self.prepareGeometryChange()
		self.p2 = self.mapFromScene(p)
		self.right = max(self.p1.x(), self.p2.x())

	def setright(self, x, extend=False):
		"""where the lines end, in scene x; never left of both points"""
		self.prepareGeometryChange()
		self.right = max(self.mapFromScene(QPointF(x, 0)).x(), min(self.p1.x(), self.p2.x()) + 1)
		self.extend = extend

	def xs(self):
		"""the left and right ends of the lines"""
		left = min(self.p1.x(), self.p2.x())
		right = self.right
		if self.extend and self.scene() is not None:
			right = self.mapFromScene(QPointF(self.scene().sceneRect().right(), 0)).x()
		return left, max(right, left + 1)

	def ys(self):
		"""(level, y) of each line"""
		y1, y0 = self.p1.y(), self.p2.y()
		return [(l, y0 + (y1 - y0) * l) for l in self.levels]

	def boundingRect(self):
		left, right = self.xs()
		ys = [y for _, y in self.ys()] + [self.p1.y(), self.p2.y()]
		m = self.width * 2 + 4
		return QRectF(QPointF(left - m, min(ys) - self.LABELSIZE - m),
			QPointF(right + m, max(ys) + m))

	def shape(self):
		left, right = self.xs()
		path = QPainterPath()
		for _, y in self.ys():
			path.moveTo(left, y)
			path.lineTo(right, y)
		path.moveTo(self.p1)
		path.lineTo(self.p2)
		s = QPainterPathStroker()
		s.setWidth(max(self.width, 1) + 8)
		return s.createStroke(path)

	def paint(self, painter, option, widget=None):
		painter.setRenderHint(painter.RenderHint.Antialiasing)
		left, right = self.xs()
		dash = mkpen(self.color, 1)
		dash.setStyle(Qt.PenStyle.DashLine)
		painter.setPen(dash)
		painter.drawLine(self.p1, self.p2)
		f = QFont()
		f.setPixelSize(self.LABELSIZE)
		painter.setFont(f)
		pen = mkpen(self.color, self.width)
		pen.setCapStyle(Qt.PenCapStyle.FlatCap)
		for l, y in self.ys():
			painter.setPen(pen)
			painter.drawLine(QPointF(left, y), QPointF(right, y))
			painter.setPen(QColor(self.color))
			painter.drawText(QPointF(left + 3, y - self.width / 2 - 3), f"{l:g}")
		if self.isSelected():
			selpen(painter)
			painter.setBrush(Qt.BrushStyle.NoBrush)
			painter.drawRect(self.boundingRect())

	def todict(self):
		right = self.mapToScene(QPointF(self.right, 0)).x()
		return {"kind": "fib", "p1": pt(self.mapToScene(self.p1)), "p2": pt(self.mapToScene(self.p2)),
			"right": round(right, 1), "extend": self.extend, "levels": self.levels,
			"color": self.color, "width": self.width}

	def small(self):
		return QLineF(self.p1, self.p2).length() < 4

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
		if k == "rect":
			return RectShape(QRectF(*d["rect"]), color, float(d.get("width", 3)), d.get("fill"),
				int(d.get("alpha", 64)), bool(d.get("middle")), str(d.get("label", "")), str(d.get("align", "center")))
		if k == "pencil":
			pts = [QPointF(*p) for p in d["points"]]
			return PencilShape(pts, color, float(d.get("width", 3))) if pts else None
		if k == "fib":
			return FibShape(QPointF(*d["p1"]), QPointF(*d["p2"]), [float(l) for l in d["levels"]], color,
				float(d.get("width", 1)), float(d["right"]), bool(d.get("extend")))
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

class PropsCmd(QUndoCommand):
	"""other fill, middle line or label for a rectangle"""
	def __init__(self, item, before, after):
		super().__init__("Change rectangle")
		self.item, self.before, self.after = item, dict(before), dict(after)

	def redo(self):
		self.item.setprops(self.after)

	def undo(self):
		self.item.setprops(self.before)

class LevelsCmd(QUndoCommand):
	"""other levels for Fibonacci drawings"""
	def __init__(self, items, levels):
		super().__init__("Change levels")
		self.changes = [(it, list(it.levels)) for it in items]
		self.levels = list(levels)

	def redo(self):
		for it, _ in self.changes:
			it.setlevels(self.levels)

	def undo(self):
		for it, old in self.changes:
			it.setlevels(old)

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
