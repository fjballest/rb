#
# widget for list of objects as a table

from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex, QItemSelectionModel
from dataclasses import fields, is_dataclass
from csv_mapper import convert_value, format_value, is_optional, unwrap_optional
import re
import sys
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
	QLabel, QStyledItemDelegate, QStyleOptionViewItem, QStyle, QApplication
)
from find import FindReplaceDialog

from PySide6.QtWidgets import (
	QWidget, QVBoxLayout, QHBoxLayout, QTableView,
	QPushButton, QToolButton
)
from PySide6.QtCore import QTimer, Signal, QPersistentModelIndex

def findfield(flds, n):
	for i, f in enumerate(flds):
		if f.name == n:
			return i
	return -1

class Group:
	"""a header row of a grouped table; objs are all its objects, shown or not"""
	def __init__(self, key, label, level):
		self.key = key
		self.label = label
		self.level = level
		self.objs = []

class ObjectTableModel(QAbstractTableModel):
	dirtied = Signal()		# a cell was edited
	renamed = Signal(object, object)	# key column: old value (None for a new row), new value
	edited = Signal()		# the user added or deleted rows
	removed = Signal(object)	# the user deleted this object
	selected = Signal(object)
	graphicsRequested = Signal(object)
	fieldChanged = Signal(object, str)	# obj and the name of the field set in it

	def __init__(self, obj0, objects, order, rdonly, object_factory,
			uniquekey=False, editor=None, canremove=None,
			groupby=None, sortkey=None, groupinfo=None):
		"""uniquekey: column 0 is a unique name, and changing it emits renamed.
		editor(obj, filepath) edits a new or existing object in a dialog.
		canremove(obj) returns False to veto deleting obj.
		groupby(obj) returns the groups of obj, outermost first, as (key, label)
		pairs; keys must be unique among all groups (e.g. (year,), (year, month)).
		Rows are then sorted by sortkey(obj) and shown under group header rows
		that can be collapsed. groupinfo(objs) returns (text, sign) for a header.
		"""
		super().__init__()
		self.uniquekey = uniquekey
		self.editor = editor
		self.canremove = canremove
		self.groupby = groupby
		self.sortkey = sortkey
		self.groupinfo = groupinfo
		self.collapsed = set()	# keys of collapsed groups
		self.rows = None	# shown rows when grouped: Group or object
		self.order = None	# all objects in display order when grouped

		if objects and not is_dataclass(objects[0]):
			raise TypeError("Objects must be dataclass instances")
		if not is_dataclass(obj0):
			raise TypeError("Object must be dataclass instances")

		self.objects = objects
		self.obj0 = obj0
		self.object_factory = object_factory  # creates a new blank object
		self.field_defs = fields(obj0)
		self.rdonly = rdonly

		if order is not None and len(order) > 0:
			flds = [x for x in self.field_defs]
			defs = []
			for f in order:
				i = findfield(flds, f)
				if i >= 0:
					defs.append(flds[i])
					flds = flds[:i] + flds[i+1:]
			defs = defs + flds
			self.field_defs = defs

		self.field_pos = {}
		for i, f in enumerate(self.field_defs):
			self.field_pos[f.name] = i
		self.build()

	# ----- Groups -----

	def grouped(self):
		return self.groupby is not None

	def build(self):
		"""compute the shown rows from objects and the collapsed groups"""
		if not self.grouped():
			return
		if self.sortkey is not None:
			self.order = sorted(self.objects, key=self.sortkey)
		else:
			self.order = list(self.objects)
		rows = []
		path = []	# groups of the previous object
		for o in self.order:
			hidden = False
			for lvl, (key, label) in enumerate(self.groupby(o)):
				if lvl < len(path) and path[lvl].key == key:
					g = path[lvl]
				else:
					g = Group(key, label, lvl)
					path = path[:lvl] + [g]
					if not hidden:
						rows.append(g)
				g.objs.append(o)
				hidden = hidden or key in self.collapsed
			if not hidden:
				rows.append(o)
		self.rows = rows

	def regroup(self):
		if not self.grouped():
			return
		self.beginResetModel()
		self.build()
		self.endResetModel()

	def ordered(self):
		"""all objects in the order they are shown"""
		return self.order if self.grouped() else self.objects

	def shown(self):
		return self.rows if self.grouped() else self.objects

	def entry(self, row):
		rows = self.shown()
		if 0 <= row < len(rows):
			return rows[row]
		return None

	def objat(self, row):
		"""the object at row, None for a group header"""
		e = self.entry(row)
		return None if isinstance(e, Group) else e

	def isgroup(self, row):
		return isinstance(self.entry(row), Group)

	def rowof(self, obj):
		for i, e in enumerate(self.shown()):
			if e is obj:
				return i
		return -1

	def rowofgroup(self, key):
		for i, e in enumerate(self.shown()):
			if isinstance(e, Group) and e.key == key:
				return i
		return -1

	def reveal(self, obj):
		"""expand the groups holding obj and return its row, or -1"""
		if self.grouped():
			keys = {k for k, _ in self.groupby(obj)}
			if keys & self.collapsed:
				self.collapsed -= keys
				self.regroup()
		return self.rowof(obj)

	def toggle(self, row, expand=None):
		"""collapse or expand the group at row; expand None flips it"""
		g = self.entry(row)
		if not isinstance(g, Group):
			return
		iscollapsed = g.key in self.collapsed
		if expand is None:
			expand = iscollapsed
		if expand == iscollapsed:
			if expand:
				self.collapsed.discard(g.key)
			else:
				self.collapsed.add(g.key)
			self.regroup()

	def expandall(self):
		self.collapsed = set()
		self.regroup()

	def collapseall(self):
		self.collapseexcept([])

	def allcollapsed(self):
		"""every group shown is collapsed"""
		return self.grouped() and all(e.key in self.collapsed for e in self.rows if isinstance(e, Group))

	def toggleall(self):
		"""expand all groups when all are collapsed, else collapse all"""
		if self.allcollapsed():
			self.expandall()
		else:
			self.collapseall()

	def collapseexcept(self, objs):
		"""collapse every group but those holding objs"""
		if not self.grouped():
			return
		keep = {k for o in objs for k, _ in self.groupby(o)}
		self.collapsed = {k for o in self.objects for k, _ in self.groupby(o)} - keep
		self.regroup()

	def grouptext(self, g):
		arrow = "▶" if g.key in self.collapsed else "▼"
		txt = f"{'      '*g.level}{arrow} {g.label}"
		if self.groupinfo is not None:
			info, _ = self.groupinfo(g.objs)
			txt += f"    {info}"
		return txt

	def groupdata(self, g, index, role):
		if index.column() != 0:
			return None
		if role == Qt.ItemDataRole.DisplayRole:
			return self.grouptext(g)
		if role == Qt.ItemDataRole.FontRole:
			f = QFont()
			f.setBold(True)
			return f
		if role == Qt.ItemDataRole.BackgroundRole:
			return QColor((215, 225, 235)[min(g.level, 2)], (215, 225, 235)[min(g.level, 2)], 240)
		if role == Qt.ItemDataRole.ForegroundRole:
			sign = self.groupinfo(g.objs)[1] if self.groupinfo is not None else 0
			if sign > 0:
				return QColor('darkgreen')
			if sign < 0:
				return QColor('darkred')
			return QColor('black')
		return None

	# ----- Required overrides -----

	def rowCount(self, parent=QModelIndex()):
		return len(self.shown())

	def columnCount(self, parent=QModelIndex()):
		return len(self.field_defs)

	def data(self, index, role=Qt.ItemDataRole.DisplayRole):
		if not index.isValid():
			return None
		e = self.entry(index.row())
		if e is None:
			return None
		if isinstance(e, Group):
			return self.groupdata(e, index, role)
		obj = e
		field = self.field_defs[index.column()]
		value = getattr(obj, field.name)
		if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
			return format_value(value)
		if role == Qt.ItemDataRole.ForegroundRole:
			if hasattr(obj, "result") and callable(obj.result):
				try:
					r = obj.result()
					if r > 0:
						return QColor('green')
					if r < 0:
						return QColor('red')
					return None
				except Exception:
					pass
			x = 0
			if hasattr(obj, "euros"):
				x = obj.euros
			if x == 0 and hasattr(obj, "pts"):
				x = obj.pts
			if x < -10:
				return QColor('red')
			if x > 10:
				return QColor('green')
		return None

	def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
		if role != Qt.ItemDataRole.EditRole or not index.isValid():
			return False
		obj = self.objat(index.row())
		if obj is None:
			return False
		if not self.setvalue(obj, index.column(), value):
			return False
		if self.grouped():
			self.refresh()	# the group totals may change too
		else:
			self.dataChanged.emit(index, index,
						  [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
		return True

	def setvalue(self, obj, col, value):
		"""set the field at column col of obj from its text"""
		field = self.field_defs[col]

		ftype = field.type
		if is_optional(ftype):
			ftype = unwrap_optional(ftype)
		try:
			converted = convert_value(value, ftype)
		except Exception:
			return False
		renaming = col == 0 and self.uniquekey
		old = None
		if renaming:
			if not converted:
				return False	# names can't be blank
			for r in self.objects:
				if r is obj:
					continue
				other = getattr(r, field.name, None)
				if other and other == converted:
					# already in use
					return False
			old = getattr(obj, field.name, None)
			if old:
				# before the change, so the roadbook can still find it by its old name
				self.renamed.emit(old, converted)
		where = self.place(obj)
		setattr(obj, field.name, converted)
		self.dirtied.emit()
		if renaming and not old:
			self.renamed.emit(None, converted)
		self.fieldChanged.emit(obj, field.name)
		if where != self.place(obj):
			# later, not under the editor that is committing this value
			QTimer.singleShot(0, self.regroup)
		return True

	def place(self, obj):
		"""what decides where obj is shown"""
		if not self.grouped():
			return None
		return (self.groupby(obj), self.sortkey(obj) if self.sortkey else None)

	def flags(self, index):
		if self.isgroup(index.row()):
			return Qt.ItemFlag.ItemIsEnabled
		c = index.column()
		fd = self.field_defs[c]
		if fd.name in self.rdonly:
			return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
		return (Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled |
				Qt.ItemFlag.ItemIsEditable)

	def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
		if role != Qt.ItemDataRole.DisplayRole:
			return None

		if orientation == Qt.Orientation.Horizontal:
			return self.field_defs[section].name
		if self.grouped():
			obj = self.objat(section)
			if obj is None:
				return ""
			for i, o in enumerate(self.order):
				if o is obj:
					return i + 1
		return section + 1

	# ----- Row insertion -----

	def insertRows(self, row, count=1, parent=QModelIndex(), trade=None):
		if self.grouped():
			# rows go where their group is, so just add the objects
			for _ in range(count):
				if trade is None or count > 1:
					trade = self.object_factory()
				self.objects.append(trade)
			self.regroup()
			return True
		self.beginInsertRows(parent, row, row + count - 1)

		for _ in range(count):
			if trade is None or count > 1:
				trade = self.object_factory()
			self.objects.insert(row, trade)

		self.endInsertRows()
		return True

	# ----- Row removal -----

	def removeRows(self, row, count=1, parent=QModelIndex(), usrdel=False):
		o = None
		if usrdel:
			o = self.objat(row)
			if o is None:
				return False
			if self.canremove is not None and not self.canremove(o):
				return False
		if self.grouped():
			gone = [x for x in (self.objat(r) for r in range(row, row + count)) if x is not None]
			self.objects[:] = [x for x in self.objects if not any(x is g for g in gone)]
			self.regroup()
		else:
			self.beginRemoveRows(parent, row, row + count - 1)
			del self.objects[row: row + count]
			self.endRemoveRows()
		if usrdel:
			self.removed.emit(o)
			self.edited.emit()
		return True

	def newRow(self, row, filepath=None):
		"""add a row, editing it first when there is an editor; returns the new object or None"""
		t = self.object_factory()
		if self.editor is not None:
			self.editor(t, filepath)
			added = t.checkOut() is None
			if added:
				self.insertRows(row, trade=t)
			self.edited.emit()
			return t if added else None
		self.insertRows(row, trade=t)
		return t


	def editRow(self, row):
		obj = self.objat(row)
		if obj is None:
			return
		if self.editor is not None:
			self.editor(obj, None)
			if self.grouped():
				self.regroup()	# its date may have changed
			else:
				self.refresh()

	def graphics(self, row):
		obj = self.objat(row)
		if obj is not None:
			self.graphicsRequested.emit(obj)

	def selChanged(self, row):
		obj = self.objat(row)
		if obj is not None:
			self.selected.emit(obj)

	def changedata(self, objects):
		"""replace all data with a new set"""
		self.beginResetModel()
		self.objects = objects
		self.build()
		self.endResetModel()

	def refresh(self):
		n = self.rowCount()
		if n == 0:
			return
		topLeft = self.index(0,0)
		bottomRight = self.index(n-1, len(self.field_defs)-1)
		self.dataChanged.emit(topLeft, bottomRight)

	def position(self, row):
		"""where row is in ordered(); a group header is half a place before its first object"""
		e = self.entry(row)
		if e is None:
			return None
		o = e.objs[0] if isinstance(e, Group) else e
		for i, x in enumerate(self.ordered()):
			if x is o:
				if isinstance(e, Group):
					return i - 0.5
				return i
		return None

	def step(self, index, delta):
		"""the index of the object delta places from index, wrapping around
		and expanding its groups if they are collapsed"""
		objs = self.ordered()
		n = len(objs)
		if n == 0:
			return QModelIndex()
		col = max(index.column(), 0)
		p = self.position(index.row()) if index.isValid() else None
		if p is None:
			p = 0 if delta > 0 else n - 1
		elif p != int(p):
			# a header: the next is its first object, the prev the one before it
			p = p + 0.5 if delta > 0 else p - 0.5
		else:
			p = p + delta
		obj = objs[int(p) % n]
		return self.index(self.reveal(obj), col)

	def prev(self, index):
		return self.step(index, -1)

	def next(self, index):
		return self.step(index, 1)

	# ----- Find and replace -----
	# cells are searched by the text they show, object by object in the
	# order they are shown, including those in collapsed groups

	@staticmethod
	def pattern(txt, cs, words):
		p = re.escape(txt)
		if words:
			p = r"\b" + p + r"\b"
		return re.compile(p, 0 if cs else re.IGNORECASE)

	def objtext(self, obj, col):
		return format_value(getattr(obj, self.field_defs[col].name))

	def celltext(self, row, col):
		obj = self.objat(row)
		return "" if obj is None else self.objtext(obj, col)

	def matches(self, index, pat):
		return index.isValid() and pat.search(self.celltext(index.row(), index.column())) is not None

	def find(self, index, pat, backward=False):
		"""the next (or previous) cell after index matching pat, wrapping around"""
		objs = self.ordered()
		ncols = len(self.field_defs)
		n = len(objs) * ncols
		if n == 0:
			return None
		p = self.position(index.row()) if index.isValid() else None
		if p is None:
			pos = n if backward else -1
		elif p != int(p):
			# a header: start just before its first object
			pos = int(p + 0.5) * ncols + (0 if backward else -1)
		else:
			pos = int(p) * ncols + index.column()
		step = -1 if backward else 1
		for k in range(1, n+1):
			q = (pos + k*step) % n
			obj = objs[q // ncols]
			if pat.search(self.objtext(obj, q % ncols)):
				return self.index(self.reveal(obj), q % ncols)
		return None

	def replace(self, index, pat, rtxt):
		"""replace matches in the cell at index; False if the new value is refused"""
		if self.field_defs[index.column()].name in self.rdonly:
			return False
		new = pat.sub(lambda _: rtxt, self.celltext(index.row(), index.column()))
		return self.setData(index, new)

	def replaceall(self, pat, rtxt):
		"""replace in every cell; returns how many cells changed and how many were refused"""
		done = skipped = 0
		for obj in list(self.ordered()):
			for col in range(len(self.field_defs)):
				txt = self.objtext(obj, col)
				if pat.search(txt) is None:
					continue
				if self.field_defs[col].name not in self.rdonly and \
						self.setvalue(obj, col, pat.sub(lambda _: rtxt, txt)):
					done += 1
				else:
					skipped += 1
		self.refresh()
		return done, skipped


class HighlightDelegate(QStyledItemDelegate):
	"""paints cells marking the text that matches pat; the found cell is marked stronger"""
	def __init__(self, parent=None):
		super().__init__(parent)
		self.pat = None
		self.current = QPersistentModelIndex()

	def paint(self, painter, option, index):
		text = index.data(Qt.ItemDataRole.DisplayRole)
		if self.pat is None or not text or self.pat.search(text) is None:
			super().paint(painter, option, index)
			return
		opt = QStyleOptionViewItem(option)
		self.initStyleOption(opt, index)
		opt.text = ""
		widget = opt.widget
		style = widget.style() if widget else QApplication.style()
		style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)
		rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, opt, widget)
		margin = style.pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin, None, widget) + 1
		rect = rect.adjusted(margin, 0, -margin, 0)
		selected = opt.state & QStyle.StateFlag.State_Selected
		fg = index.data(Qt.ItemDataRole.ForegroundRole)
		if selected:
			fg = opt.palette.color(opt.palette.ColorRole.HighlightedText)
		elif fg is None:
			fg = opt.palette.color(opt.palette.ColorRole.Text)
		mark = QColor("orange") if QPersistentModelIndex(index) == self.current else QColor("yellow")
		fm = opt.fontMetrics
		painter.save()
		painter.setClipRect(rect)
		painter.setFont(opt.font)
		x = rect.left()
		top = rect.top() + (rect.height() - fm.height()) // 2
		base = top + fm.ascent()
		pos = 0
		for m in self.pat.finditer(text):
			for part, hit in ((text[pos:m.start()], False), (m.group(0), True)):
				w = fm.horizontalAdvance(part)
				if hit:
					painter.fillRect(x, top, w, fm.height(), mark)
				painter.setPen(QColor("black") if hit else fg)
				painter.drawText(x, base, part)
				x += w
			pos = m.end()
		painter.setPen(fg)
		painter.drawText(x, base, text[pos:])
		painter.restore()


class DTableView(QTableView):
	def __init__(self, drop=None):
		super().__init__()
		self.setAcceptDrops(True)
		self.setDragEnabled(True)
		self.setDropIndicatorShown(True)
		self.drop = drop
		self.corner = None	# a widget kept over the top left corner

	def updateGeometries(self):
		super().updateGeometries()
		if self.corner is not None:
			fw = self.frameWidth()
			self.corner.setGeometry(fw, fw, self.verticalHeader().width(), self.horizontalHeader().height())
			self.corner.raise_()

	def dragEnterEvent(self, event):
		if event.mimeData().hasUrls():
			event.acceptProposedAction()
		else:
			event.ignore()
	def dragMoveEvent(self, event):
			event.acceptProposedAction()
	def dropEvent(self, event):
		if event.mimeData().hasUrls():
			file_path = [x.toLocalFile() for x in event.mimeData().urls()]
			if self.drop is not None:
				try:
					self.drop(file_path)
				except Exception as e:
					print(e, file=sys.stderr)
			event.acceptProposedAction()
		else:
			event.ignore()


class ObjectTable(QWidget):
	"""editable table for a list of dataclass objects, using obj as the example row.
	The model signals are repeated here; see ObjectTableModel for
	uniquekey, editor and canremove. drop adds a row when files are dropped.
	info() returns the text for the label next to the buttons.
	extrabuttons may name "Graphics", "Filter" and "Stats".
	groupby, sortkey and groupinfo show the rows in groups that expand and
	collapse when their header is clicked; see ObjectTableModel.
	"""
	dirtied = Signal()
	renamed = Signal(object, object)
	edited = Signal()
	removed = Signal(object)
	selected = Signal(object)
	graphicsRequested = Signal(object)
	fieldChanged = Signal(object, str)
	filterRequested = Signal()
	statsRequested = Signal()

	def __init__(self, obj, objects, object_factory,
			order=None, rdonly=None, hasedit=True, parent=None, drop=False,
			uniquekey=False, editor=None, canremove=None, info=None, extrabuttons=(),
			groupby=None, sortkey=None, groupinfo=None):
		super().__init__(parent)
		self.info = info
		self.finddlg = None
		if order is None:
			order = []
		if rdonly is None:
			rdonly = []
		self.obj0 = obj
		fake = False
		if len(objects) == 0:
			objects.append(obj)
			fake = True
		self.model = ObjectTableModel(obj, objects, order, rdonly, object_factory,
			uniquekey=uniquekey, editor=editor, canremove=canremove,
			groupby=groupby, sortkey=sortkey, groupinfo=groupinfo)
		for name in ("dirtied", "renamed", "edited", "removed", "selected", "graphicsRequested", "fieldChanged"):
			getattr(self.model, name).connect(getattr(self, name))
		self.view = DTableView(self.add_row if drop else None)
		self.marker = HighlightDelegate(self.view)
		self.view.setItemDelegate(self.marker)
		self.view.setModel(self.model)
		self.view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
		self.view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
		self.view.resizeColumnsToContents()
		selmodel = self.view.selectionModel()
		selmodel.selectionChanged.connect(self.selChanged)
		if fake:
			del objects[0]
			self.model.changedata(objects)
		self.keep = None
		self.model.modelAboutToBeReset.connect(self.beforereset)
		self.model.modelReset.connect(self.afterreset)
		self.view.clicked.connect(self.clicked)
		self.setspans()

		self.viewkeypress = self.view.keyPressEvent
		self.view.keyPressEvent = self.keypress


		# Buttons
		add_btn = QPushButton("New")
		del_btn = QPushButton("Del")

		add_btn.clicked.connect(self.add_row)
		del_btn.clicked.connect(self.delete_row)

		find_btn = QPushButton("Find")
		find_btn.clicked.connect(self.find)
		# only while the table has the focus, so tables in the same window don't clash
		self.findshortcut = QShortcut(QKeySequence.StandardKey.Find, self, self.find,
			context=Qt.ShortcutContext.WidgetWithChildrenShortcut)

		btn_layout = QHBoxLayout()
		btn_layout.addWidget(add_btn)
		btn_layout.addWidget(del_btn)
		if hasedit:
			edit_btn = QPushButton("Edit")
			edit_btn.clicked.connect(self.edit_row)
			btn_layout.addWidget(edit_btn)
		btn_layout.addWidget(find_btn)
		self.cornerbtn = None
		if groupby is not None:
			# a tiny triangle in the top left corner expands or collapses all groups
			self.view.setCornerButtonEnabled(False)
			self.view.verticalHeader().setMinimumWidth(16)	# room for the triangle
			b = QToolButton(self.view)
			b.setAutoRaise(True)
			f = b.font()
			f.setPointSizeF(f.pointSizeF() * 0.8)
			b.setFont(f)
			b.setStyleSheet("QToolButton { border: none; padding: 0; }")
			b.clicked.connect(self.model.toggleall)
			self.cornerbtn = b
			self.view.corner = b
			self.updatecorner()
		if "Graphics" in extrabuttons:
			g_btn = QPushButton("Graphics")
			g_btn.clicked.connect(self.graphics)
			btn_layout.addWidget(g_btn)
		if "Filter" in extrabuttons:
			f_btn = QPushButton("Filter")
			f_btn.clicked.connect(lambda: self.filterRequested.emit())
			btn_layout.addWidget(f_btn)
		if "Stats" in extrabuttons:
			s_btn = QPushButton("Stats")
			s_btn.clicked.connect(lambda: self.statsRequested.emit())
			btn_layout.addWidget(s_btn)
		self.infolabel = None


		btn_layout.addStretch()
		if self.info is not None:
			self.infolabel = QLabel(self.info())
			myFont=QFont()
			myFont.setBold(True)
			self.infolabel.setFont(myFont)
			btn_layout.addWidget(self.infolabel)

		layout = QVBoxLayout(self)
		layout.addLayout(btn_layout)
		layout.addWidget(self.view)

		self.model.rowsInserted.connect(lambda: QTimer.singleShot(0, self.view.scrollToBottom))

	def keypress(self, event):
		row = self.view.currentIndex().row()
		if self.model.isgroup(row):
			k = event.key()
			if k in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
				self.model.toggle(row)
				event.accept()
				return
			if k in (Qt.Key_Left, Qt.Key_Right):
				self.model.toggle(row, expand=k == Qt.Key_Right)
				event.accept()
				return
		if event.key() == Qt.Key_End:
			self.view.scrollToBottom()
			event.accept()
			return
		if event.key() == Qt.Key_Home:
			self.view.scrollToTop()
			event.accept()
			return
		self.viewkeypress(event)
	def graphics(self):
		indexes = self.view.selectionModel().selectedRows()
		if not indexes:
			return
		row = indexes[0].row()
		self.model.graphics(row)

	def clicked(self, index):
		if self.model.isgroup(index.row()):
			self.model.toggle(index.row())

	def setspans(self):
		"""group headers use the whole row"""
		self.view.clearSpans()
		if not self.model.grouped():
			return
		ncols = self.model.columnCount()
		for row in range(self.model.rowCount()):
			if self.model.isgroup(row):
				self.view.setSpan(row, 0, 1, ncols)

	def beforereset(self):
		cur = self.view.currentIndex()
		obj = self.model.entry(cur.row()) if cur.isValid() else None
		self.keep = (obj, max(cur.column(), 0), self.view.verticalScrollBar().value())

	def updatecorner(self):
		if self.cornerbtn is None:
			return
		if self.model.allcollapsed():
			self.cornerbtn.setText("▶")
			self.cornerbtn.setToolTip("expand all groups (click a group to expand or collapse just that one)")
		else:
			self.cornerbtn.setText("▼")
			self.cornerbtn.setToolTip("collapse all groups (click a group to expand or collapse just that one)")

	def afterreset(self):
		"""after regrouping, keep the current object or group and the scroll position"""
		self.setspans()
		self.updatecorner()
		if self.keep is None:
			return
		obj, col, scroll = self.keep
		self.keep = None
		self.view.verticalScrollBar().setValue(scroll)
		if isinstance(obj, Group):
			row = self.model.rowofgroup(obj.key)
			if row >= 0:
				self.view.setCurrentIndex(self.model.index(row, 0))
			return
		row = self.model.rowof(obj) if obj is not None else -1
		if row >= 0:
			index = self.model.index(row, col)
			self.view.setCurrentIndex(index)
			self.view.selectionModel().select(index,
				QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)

	def selectobj(self, obj):
		"""select obj, expanding its groups if needed; False if it is not in the table"""
		row = self.model.reveal(obj)
		if row < 0:
			return False
		self.gocell(self.model.index(row, max(self.view.currentIndex().column(), 0)))
		return True

	def refresh(self):
		selmodel = self.view.selectionModel()
		oldi = self.view.currentIndex()
		olds = selmodel.selectedRows()
		self.model.refresh()
		self.view.resizeColumnsToContents()
		if self.infolabel is not None:
			self.infolabel.setText(self.info())
		if oldi:
			if 0 <= oldi.row() <= self.model.rowCount():
				self.view.setCurrentIndex(oldi)
			if olds and 0 <= olds[0].row() <= self.model.rowCount():
				selmodel.select(olds[0], QItemSelectionModel.SelectionFlag.ClearAndSelect)

	def selChanged(self):
		indexes = self.view.selectionModel().selectedRows()
		if not indexes:
			return
		row = indexes[0].row()
		self.model.selChanged(row)

	def contextMenuEvent(self, _):
		# swallow it, so the main window does not pop up its dock menu
		pass

	def add_row(self, filepath=None):
		obj = self.model.newRow(self.model.rowCount(), filepath)
		if obj is not None:
			self.selectobj(obj)

	def delete_row(self):
		indexes = self.view.selectionModel().selectedRows()
		if not indexes:
			return

		row = indexes[0].row()
		self.model.removeRows(row, usrdel=True)

	def edit_row(self):
		indexes = self.view.selectionModel().selectedRows()
		if not indexes:
			return
		row = indexes[0].row()
		self.model.editRow(row)

	def changedata(self, objects):
		"""replace all data with a new set"""
		self.model.changedata(objects)
		self.view.resizeColumnsToContents()
		if self.infolabel is not None:
			self.infolabel.setText(self.info())

	def find(self):
		if self.finddlg is None:
			f = FindReplaceDialog(self)
			f.find_next.connect(lambda t, cs, w: self.find_next(t, cs, w))
			f.find_prev.connect(lambda t, cs, w: self.find_prev(t, cs, w))
			f.replace_one.connect(self.replace_one)
			f.replace_all.connect(self.replace_all)
			f.finished.connect(lambda _: self.highlight(None))
			self.finddlg = f
		self.finddlg.setStatus("")
		self.finddlg.show()
		self.finddlg.raise_()
		self.finddlg.activateWindow()

	def highlight(self, pat, index=None):
		"""mark the text matching pat in the table, None to stop marking"""
		self.marker.pat = pat
		self.marker.current = QPersistentModelIndex(index) if index is not None else QPersistentModelIndex()
		self.view.viewport().update()

	def gocell(self, index):
		self.view.setCurrentIndex(index)
		self.view.selectionModel().select(index,
			QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
		self.view.scrollTo(index)

	def status(self, txt):
		if self.finddlg is not None:
			self.finddlg.setStatus(txt)

	def find_next(self, txt, cs, words=False, backward=False):
		if txt == "":
			return False
		pat = ObjectTableModel.pattern(txt, cs, words)
		index = self.model.find(self.view.currentIndex(), pat, backward)
		self.highlight(pat, index)
		if index is None:
			self.status(f"'{txt}' not found")
			return False
		self.status(f"found in row {index.row()+1}, {self.model.field_defs[index.column()].name}")
		self.gocell(index)
		return True

	def find_prev(self, txt, cs, words=False):
		return self.find_next(txt, cs, words, backward=True)

	def replace_one(self, txt, rtxt, cs, words=False):
		"""replace in the current cell when it matches, then go to the next match"""
		if txt == "":
			return
		pat = ObjectTableModel.pattern(txt, cs, words)
		index = self.view.currentIndex()
		if not self.model.matches(index, pat):
			self.find_next(txt, cs, words)
			return
		if not self.model.replace(index, pat, rtxt):
			self.status("can't replace that one (read only, invalid, or name already used)")
			return
		self.view.resizeColumnsToContents()
		if self.find_next(txt, cs, words):
			self.status("replaced one; " + self.finddlg.status.text())
		else:
			self.status("replaced one; no more found")

	def replace_all(self, txt, rtxt, cs, words=False):
		if txt == "":
			return
		pat = ObjectTableModel.pattern(txt, cs, words)
		done, skipped = self.model.replaceall(pat, rtxt)
		self.view.resizeColumnsToContents()
		msg = f"replaced {done}"
		if skipped:
			msg += f", {skipped} refused (read only, invalid, or name already used)"
		self.status(msg)

	def next(self):
		index = self.model.next(self.view.currentIndex())
		if index.isValid():
			self.gocell(index)

	def prev(self):
		index = self.model.prev(self.view.currentIndex())
		if index.isValid():
			self.gocell(index)

	def edge(self, last):
		"""select the first or (last True) the last object, in the order shown"""
		objs = self.model.ordered()
		if objs:
			self.selectobj(objs[-1] if last else objs[0])
