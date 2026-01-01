import sys
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, QSize
from data import *
from objtbl import *
from stats import *
import sys
from PySide6.QtWidgets import *
from PySide6.QtGui import *

import sys
from PySide6.QtWidgets import (
	QApplication, QWidget, QVBoxLayout, QHBoxLayout,
	QCheckBox, QPushButton, QLabel, QScrollArea
)
from PySide6.QtCore import Qt

class ListViewSz(QListView):
	def __init__(self):
		super().__init__()

	def sizeHint(self):
		s = QSize()
		s.setHeight(super(ListViewSz,self).sizeHint().height())
		s.setWidth(self.sizeHintForColumn(0))
		return s

class CheckBoxGroup(QWidget):
	def __init__(self,
			items=None, checked_items=None, checkedneg_items=None,
			wsetall=False, w3state=False, title=None,
			dirtied=None
		):
		super().__init__()

		layout = QVBoxLayout(self)
		self.updateitems = None
		self.w3state = w3state
		self.dirtied = dirtied
		if self.dirtied is None:
			self.dirtied = lambda: True

		# ---- List view + model ----
		self.view = ListViewSz()
		self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		self.model = QStandardItemModel(self.view)
		self.view.setModel(self.model)
		self.view.selectionModel().currentChanged.connect(self.changed)
		# ---- Buttons ----
		btn_clr = QPushButton("Clear")
		btn_clr.clicked.connect(self.select_none)

		if wsetall:
			bnt_all = QPushButton("All")
			bnt_all.clicked.connect(self.select_all)
			if w3state:
				bnt_negall = QPushButton("None")
				bnt_negall.clicked.connect(self.select_negall)



		btn_layout = QHBoxLayout()
		btn_layout.addWidget(btn_clr)
		if wsetall:
			btn_layout.addWidget(bnt_all)
			if w3state:
				btn_layout.addWidget(bnt_negall)
		btn_layout.addStretch()


		# ---- Assemble ----
		if title:
			self.label = QLabel(title)
			layout.addWidget(self.label)
		layout.addWidget(self.view)
		layout.addLayout(btn_layout)


		if items is not None:
			self.set_items(items, checked_items, checkedneg_items)

	def set_items(self, items, checked_items=None, checkedneg_items=None):
		"""
		Replace the contents of the list.
		"""
		if checked_items is None:
			checked_items = set(self.checked_items() or [])
		if checkedneg_items is None and self.w3state:
			checkedneg_items = set(self.checkedneg_items() or [])

		self.model.clear()
		for text in items:
			item = QStandardItem(text)
			item.setCheckable(True)
			item.setEditable(False)
			if self.w3state:
				item.setUserTristate(True)
			st = Qt.Checked if text in checked_items else Qt.Unchecked
			if self.w3state and text in checkedneg_items:
				st = Qt.PartiallyChecked
			item.setCheckState(st)
			self.model.appendRow(item)


	def updating(self, items):
		if self.updateitems is not None:
			self.changed(None, None)
		self.updateitems = items

	def changed(self, cur=None, prev=None):
		if self.updateitems is not None:
			self.dirtied()
			self.updateitems.clear()
			for x in self.checked_items():
				self.updateitems.add(x)

	def checked_items(self):
		return [
			self.model.item(row).text()
			for row in range(self.model.rowCount())
			if self.model.item(row).checkState() == Qt.Checked
		]

	def checkedneg_items(self):
		return [
			self.model.item(row).text()
			for row in range(self.model.rowCount())
			if self.model.item(row).checkState() == Qt.PartiallyChecked
		]

	# --------------------------------------------------
	# Slots
	# --------------------------------------------------
	def select_none(self):
		for row in range(self.model.rowCount()):
			self.model.item(row).setCheckState(Qt.Unchecked)

	def select_all(self):
		for row in range(self.model.rowCount()):
			self.model.item(row).setCheckState(Qt.Checked)

	def select_negall(self):
		for row in range(self.model.rowCount()):
			self.model.item(row).setCheckState(Qt.PartiallyChecked)

