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
	QPushButton
)
from PySide6.QtCore import QTimer, Signal, QPersistentModelIndex

def findfield(flds, n):
	for i, f in enumerate(flds):
		if f.name == n:
			return i
	return -1

class ObjectTableModel(QAbstractTableModel):
	dirtied = Signal()		# a cell was edited
	renamed = Signal(object, object)	# key column: old value (None for a new row), new value
	edited = Signal()		# the user added or deleted rows
	removed = Signal(object)	# the user deleted this object
	selected = Signal(object)
	graphicsRequested = Signal(object)
	fieldChanged = Signal(object, str)	# obj and the name of the field set in it

	def __init__(self, obj0, objects, order, rdonly, object_factory,
			uniquekey=False, editor=None, canremove=None):
		"""uniquekey: column 0 is a unique name, and changing it emits renamed.
		editor(obj, filepath) edits a new or existing object in a dialog.
		canremove(obj) returns False to veto deleting obj.
		"""
		super().__init__()
		self.uniquekey = uniquekey
		self.editor = editor
		self.canremove = canremove

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



	# ----- Required overrides -----

	def rowCount(self, parent=QModelIndex()):
		return len(self.objects)

	def columnCount(self, parent=QModelIndex()):
		return len(self.field_defs)

	def data(self, index, role=Qt.ItemDataRole.DisplayRole):
		if not index.isValid():
			return None
		if index.row() < 0 or index.row() >= len(self.objects):
			return None
		obj = self.objects[index.row()]
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

		if index.row() < 0 or index.row() >= len(self.objects):
			return False
		obj = self.objects[index.row()]
		field = self.field_defs[index.column()]

		ftype = field.type
		if is_optional(ftype):
			ftype = unwrap_optional(ftype)
		try:
			converted = convert_value(value, ftype)
		except Exception:
			return False
		renaming = index.column() == 0 and self.uniquekey
		old = None
		if renaming:
			if not converted:
				return False	# names can't be blank
			for i, r in enumerate(self.objects):
				if i == index.row():
					continue
				other = getattr(r, field.name, None)
				if other and other == converted:
					# already in use
					return False
			old = getattr(obj, field.name, None)
			if old:
				# before the change, so the roadbook can still find it by its old name
				self.renamed.emit(old, converted)
		setattr(obj, field.name, converted)
		self.dirtied.emit()
		if renaming and not old:
			self.renamed.emit(None, converted)
		self.fieldChanged.emit(obj, field.name)

		self.dataChanged.emit(index, index,
					  [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
		return True

	def flags(self, index):
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
		return section + 1

	# ----- Row insertion -----

	def insertRows(self, row, count=1, parent=QModelIndex(), trade=None):
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
		if usrdel and 0 <= row < len(self.objects):
			o = self.objects[row]
			if self.canremove is not None and not self.canremove(o):
				return False
		self.beginRemoveRows(parent, row, row + count - 1)
		del self.objects[row: row + count]
		self.endRemoveRows()
		if usrdel:
			self.removed.emit(o)
			self.edited.emit()
		return True

	def newRow(self, row, filepath=None):
		t = self.object_factory()
		if self.editor is not None:
			self.editor(t, filepath)
			if t.checkOut() is None:
				self.insertRows(row, trade=t)
			self.edited.emit()
			return
		self.insertRows(row)


	def editRow(self, row):
		if row < 0 or row >= len(self.objects):
			return
		if self.editor is not None:
			self.editor(self.objects[row], None)

	def graphics(self, row):
		if row < 0 or row >= len(self.objects):
			return
		self.graphicsRequested.emit(self.objects[row])

	def selChanged(self, row):
		if row < 0 or row >= len(self.objects):
			return
		self.selected.emit(self.objects[row])

	def changedata(self, objects):
		"""replace all data with a new set"""
		self.beginResetModel()
		self.objects = objects
		self.endResetModel()
		topLeft = self.index(0,0)
		bottomRight = self.index(len(objects)-1, len(self.field_defs)-1)
		self.dataChanged.emit(topLeft, bottomRight)

	def refresh(self):
		objects = self.objects
		topLeft = self.index(0,0)
		bottomRight = self.index(len(objects)-1, len(self.field_defs)-1)
		self.dataChanged.emit(topLeft, bottomRight)

	def prev(self, index):
		row = index.row()
		col = index.column()
		if row < 0:
			row = 0
		if col < 0:
			col = 0
		row = row + len(self.objects) - 1
		row = row % len(self.objects)
		return self.index(row, col)

	def next(self, index):
		row = index.row()
		col = index.column()
		if row < 0:
			row = 0
		if col < 0:
			col = 0
		row = row + 1
		row = row % len(self.objects)
		return self.index(row, col)

	# ----- Find and replace -----
	# cells are searched by the text they show, row by row

	@staticmethod
	def pattern(txt, cs, words):
		p = re.escape(txt)
		if words:
			p = r"\b" + p + r"\b"
		return re.compile(p, 0 if cs else re.IGNORECASE)

	def celltext(self, row, col):
		return format_value(getattr(self.objects[row], self.field_defs[col].name))

	def matches(self, index, pat):
		return index.isValid() and pat.search(self.celltext(index.row(), index.column())) is not None

	def find(self, index, pat, backward=False):
		"""the next (or previous) cell after index matching pat, wrapping around"""
		ncols = len(self.field_defs)
		n = len(self.objects) * ncols
		if n == 0:
			return None
		if index.isValid():
			pos = index.row()*ncols + index.column()
		else:
			pos = n if backward else -1
		step = -1 if backward else 1
		for k in range(1, n+1):
			p = (pos + k*step) % n
			if pat.search(self.celltext(p // ncols, p % ncols)):
				return self.index(p // ncols, p % ncols)
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
		for row in range(len(self.objects)):
			for col in range(len(self.field_defs)):
				index = self.index(row, col)
				if not self.matches(index, pat):
					continue
				if self.replace(index, pat, rtxt):
					done += 1
				else:
					skipped += 1
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
			uniquekey=False, editor=None, canremove=None, info=None, extrabuttons=()):
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
			uniquekey=uniquekey, editor=editor, canremove=canremove)
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
			self.model.removeRows(0)

		self.viewkeypress = self.view.keyPressEvent
		self.view.keyPressEvent = self.keypress


		# Buttons
		add_btn = QPushButton("New")
		del_btn = QPushButton("Del")

		add_btn.clicked.connect(self.add_row)
		del_btn.clicked.connect(self.delete_row)

		find_btn = QPushButton("Find")
		find_btn.clicked.connect(self.find)
		QShortcut(QKeySequence.StandardKey.Find, self, self.find)

		btn_layout = QHBoxLayout()
		btn_layout.addWidget(add_btn)
		btn_layout.addWidget(del_btn)
		if hasedit:
			edit_btn = QPushButton("Edit")
			edit_btn.clicked.connect(self.edit_row)
			btn_layout.addWidget(edit_btn)
		btn_layout.addWidget(find_btn)
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
		row = self.model.rowCount()
		self.model.newRow(row, filepath)
		self.view.selectRow(row)

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
		selmodel = self.view.selectionModel()
		old = self.view.currentIndex()
		index = self.model.next(old)
		if index:
			self.view.setCurrentIndex(index)
			selmodel.select(index, QItemSelectionModel.SelectionFlag.ClearAndSelect)

	def prev(self):
		selmodel = self.view.selectionModel()
		old = self.view.currentIndex()
		index = self.model.prev(old)
		if index:
			self.view.setCurrentIndex(index)
			selmodel.select(index, QItemSelectionModel.SelectionFlag.ClearAndSelect)
