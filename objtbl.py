#
# widget for list of objects as a table

from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex, QItemSelectionModel
from dataclasses import fields, is_dataclass
from csv_mapper import convert_value, format_value
import sys
from PySide6.QtGui import *
from find import *

from PySide6.QtWidgets import (
	QWidget, QVBoxLayout, QHBoxLayout, QDateEdit,
	QTableView, QPushButton
)

def findfield(flds, n):
	for i, f in enumerate(flds):
		if f.name == n:
			return i
	return -1

class ObjectTableModel(QAbstractTableModel):
	def __init__(self, obj0, objects, order, rdonly, object_factory):
		super().__init__()

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

		try:
			converted = convert_value(value, field.type)
		except Exception:
			return False
		isnew = None
		if index.column() == 0 and hasattr(self.obj0, 'renamed'):
			for i, r in enumerate(self.objects):
				if i == index.row():
					continue
				old = getattr(self.objects[i], field.name, None)
				if old and old == converted:
					# already in use
					return False
			try:
				old = getattr(obj, field.name, None)
				if old:
					self.obj0.renamed(old, converted)
				isnew = not old
			except:
				pass
		setattr(obj, field.name, converted)
		if hasattr(self.obj0, 'dirtied'):
			try:
				self.obj0.dirtied()
			except:
				pass
		if isnew is not None:
			self.obj0.renamed(None, converted)

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
		fn = None
		if usrdel and 0 <= row < len(self.objects) and hasattr(self.obj0, "removing"):
			fn = self.obj0.removing
			o = self.objects[row]
			if not fn(o, False):
				return False
		self.beginRemoveRows(parent, row, row + count - 1)
		del self.objects[row: row + count]
		self.endRemoveRows()
		if fn:
			fn(o, True)
		return True

	def newRow(self, row):
		t = self.object_factory()
		o = self.obj0
		if hasattr(o, "edit") and callable(o.edit):
			o.edit(t)
			if t.checkOut() is None:
				self.insertRows(row, trade=t)
			return
		self.insertRows(row)


	def editRow(self, row):
		if row < 0 or row >= len(self.objects):
			return
		o = self.obj0
		if hasattr(o, "edit") and callable(o.edit):
			o.edit(self.objects[row])

	def graphics(self, row):
		if row < 0 or row >= len(self.objects):
			return
		o = self.obj0
		if hasattr(o, "graphics") and callable(o.graphics):
			o.graphics(self.objects[row])

	def selChanged(self, row):
		if row < 0 or row >= len(self.objects):
			return
		o = self.obj0
		if hasattr(o, "selected") and callable(o.selected):
			o.selected(self.objects[row])

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

	def findNext(self, index, txt, cs):
		row = index.row()
		col = index.column()
		if row < 0:
			row = 0
		if col < 0:
			col = 0
		#print(f"find {row} {col}...", file=sys.stderr)
		col = col+1
		if col >= len(self.field_defs):
			row += 1
			col = 0
		if row >= len(self.objects):
			row = 0
		found = False
		if not cs:
			txt = txt.lower()
		for i in range(len(self.objects)):
			if 0 <= row < len(self.objects):
				obj = self.objects[row]
				j = col
			while obj and j < len(self.field_defs):
				field = self.field_defs[j]
				value = getattr(obj, field.name)
				value = f"{value}"
				if not cs:
					value = value.lower()
				found = txt in value
				if found:
					break
				j = j + 1
			if found:
				break
			row = row+1
			row = row % len(self.objects)
			col = 0
		if found:
			return self.index(row, j)
		return None

	def findPrev(self, index, txt, cs):
		row = index.row()
		col = index.column()
		if row < 0:
			row = 0
		if col < 0:
			col = 0
		#print(f"find {row} {col}...", file=sys.stderr)
		col = col-1
		if col < 0:
			col = len(self.field_defs)-1
			row -= 1
		if row < 0:
			#row = len(self.objects)-1
			row = 0
		if row < 0:
			return None
		found = False
		if not cs:
			txt = txt.lower()
		for i in range(len(self.objects)):
			if 0 <= row < len(self.objects):
				obj = self.objects[row]
				j = col
			while obj and j >= 0:
				field = self.field_defs[j]
				value = getattr(obj, field.name)
				value = f"{value}"
				if not cs:
					value = value.lower()
				found = txt in value
				if found:
					break
				j = j - 1
			if found:
				break
			row = row - 1 + len(self.objects)
			row = row % len(self.objects)
			col = len(self.field_defs)-1
		if found:
			return self.index(row, j)
		return None

class ObjectTable(QWidget):
	def __init__(self, obj, objects, object_factory,
			order=None, rdonly=None, hasedit=True, parent=None):
		super().__init__(parent)
		if order is None:
			order = []
		if rdonly is None:
			rdonly = []
		self.obj0 = obj
		fake = False
		if len(objects) == 0:
			objects.append(obj)
			fake = True
		self.model = ObjectTableModel(obj, objects, order, rdonly, object_factory)

		self.view = QTableView()
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

		btn_layout = QHBoxLayout()
		btn_layout.addWidget(add_btn)
		btn_layout.addWidget(del_btn)
		if hasedit:
			edit_btn = QPushButton("Edit")
			edit_btn.clicked.connect(self.edit_row)
			btn_layout.addWidget(edit_btn)
		btn_layout.addWidget(find_btn)
		if hasattr(obj, "graphics"):
			g_btn = QPushButton("Graphics")
			g_btn.clicked.connect(self.graphics)
			btn_layout.addWidget(g_btn)
		if hasattr(obj, "filter"):
			f_btn = QPushButton("Filter")
			f_btn.clicked.connect(obj.filter)
			btn_layout.addWidget(f_btn)
		if hasattr(obj, "stats"):
			s_btn = QPushButton("Stats")
			s_btn.clicked.connect(obj.stats)
			btn_layout.addWidget(s_btn)
		self.infolabel = None


		btn_layout.addStretch()
		if hasattr(obj, "info"):
			self.infolabel = QLabel(obj.info())
			myFont=QFont()
			myFont.setBold(True)
			self.infolabel.setFont(myFont)
			btn_layout.addWidget(self.infolabel)

		layout = QVBoxLayout(self)
		layout.addLayout(btn_layout)
		layout.addWidget(self.view)

#		self.setContextMenuPolicy(Qt.CustomContextMenu)
#		self.customContextMenuRequested.connect(self.openmenu)

#		self.view.doubleClicked.connect(self.clicked2)
		self.model.rowsInserted.connect(lambda: QtCore.QTimer.singleShot(0, self.view.scrollToBottom))

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
			self.infolabel.setText(self.obj0.info())
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


	def cellact(self, r, c):
		#print(r, c, file=sys.stderr)
		pass

	def contextMenuEvent(self, _):
		#print(ev, file=sys.stderr)
		pass

	def add_row(self):
		row = self.model.rowCount()
		self.model.newRow(row)
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
			self.infolabel.setText(self.obj0.info())

	def openmenu(self, item):
		row = self.view.indexAt(item)
		print(self.view.currentRow(), file=sys.stderr)
		print(self.view.currentColumn(), file=sys.stderr)
		print(row.row(), row.column(), file=sys.stderr)

	def find(self):
		f = FindDialog(self)
		f.find_next.connect(self.find_next)
		f.find_prev.connect(self.find_prev)
		#f.replace_one.connect(self.replace1)
		#f.replace_all.connect(self.replaceall)
		f.show()

	def find_next(self, txt, cs):
		selmodel = self.view.selectionModel()
		indexes = selmodel.selectedRows()
		#row = 0
		#col = 0
		#if indexes:
		#	row = indexes[0].row()
		#	col = indexes[0].column()
		#old = self.model.index(row, col)
		old = self.view.currentIndex()
		index = self.model.findNext(old, txt, cs)
		if index:
			self.view.setCurrentIndex(index)
			selmodel.select(index, QItemSelectionModel.SelectionFlag.ClearAndSelect)
	def find_prev(self, txt, cs):
		selmodel = self.view.selectionModel()
		indexes = selmodel.selectedRows()
		#row = 0
		#col = 0
		#if indexes:
		#	row = indexes[0].row()
		#	col = indexes[0].column()
		#old = self.model.index(row, col)
		old = self.view.currentIndex()
		index = self.model.findPrev(old, txt, cs)
		if index:
			self.view.setCurrentIndex(index)
			selmodel.select(index, QItemSelectionModel.SelectionFlag.ClearAndSelect)
	def replace1(self, txt, rtxt, cs):
		pass
	def replaceall(self, txt, rtxt, cs):
		pass
