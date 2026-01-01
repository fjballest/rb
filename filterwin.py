import sys
from PySide6.QtWidgets import (
	QApplication, QMainWindow, QFileDialog,
	QLabel, QScrollArea, QPushButton,
	QWidget, QVBoxLayout, QHBoxLayout
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QEvent, QDate
from checklist import *
from stats import *
import os
WDAYS = [d.name for d in WDay]
HOURS = [f"{h}" for h in range(6,20)]

class FilterWindow(QMainWindow):
	def __init__(self, rb, setfn=None, parent=None):
		super().__init__(parent)
		self.rb = rb
		self.setfn = setfn
		if self.setfn is None:
			self.setfn = lambda f: True
		self.setWindowTitle("Filter")

		b_apply = QPushButton("Apply")
		b_apply.clicked.connect(self.apply)
		b_clr = QPushButton("Clear")
		b_clr.clicked.connect(self.clear)
		b_none = QPushButton("No Filter")
		b_none.clicked.connect(self.nofilter)

		td = date.today()
		self.b_since = QDateEdit(QDate(td.year,td.month,td.day), calendarPopup=True)
		self.b_until = QDateEdit(QDate(td.year,td.month,td.day), calendarPopup=True)
		self.b_since.setDate(QDate(td.year,td.month,td.day))
		self.b_until.setDate(QDate(td.year,td.month,td.day))

		b_layout = QHBoxLayout()
		b_layout.addWidget(b_apply)
		b_layout.addWidget(b_clr)
		b_layout.addWidget(b_none)
		b_layout.addWidget(QLabel("Since"))
		b_layout.addWidget(self.b_since)
		b_layout.addWidget(QLabel("Until"))
		b_layout.addWidget(self.b_until)
		b_layout.addStretch()

		self.instruments = CheckBoxGroup(rb.instrumentNames(), wsetall=True)
		instruments, self.instrumentsb = self.mkgrp("Instrument", self.instruments)

		self.setups = CheckBoxGroup(rb.setupNames(), wsetall=True)
		setups, self.setupsb = self.mkgrp("Setup", self.setups)

		self.features = CheckBoxGroup(rb.featureNames(), wsetall=True)
		features, _ = self.mkgrp("With features", self.features, simple=True)
		self.nfeatures = CheckBoxGroup(rb.featureNames(), wsetall=True)
		nfeatures, _ = self.mkgrp("Without features", self.nfeatures, simple=True)

		self.dirs = CheckBoxGroup([r.name for r in Dir])
		dirs, _ = self.mkgrp("Direction", self.dirs, simple=True)

		self.results = CheckBoxGroup([r.name for r in Result])
		results, _ = self.mkgrp("results", self.results, simple=True)

		vb = QWidget()
		vlay = QVBoxLayout(vb)
		vlay.addWidget(dirs)
		vlay.addWidget(results)

		self.wdays = CheckBoxGroup(WDAYS, wsetall=True)
		wdays, self.wdaysb = self.mkgrp("Day", self.wdays)
		self.hours = CheckBoxGroup(HOURS, wsetall=True)
		hours, self.hoursb = self.mkgrp("Hour", self.hours)

		vb2 = QWidget()
		vlay2 = QVBoxLayout(vb2)
		vlay2.addWidget(wdays)
		vlay2.addWidget(hours)

		sets = QWidget()
		setslay = QHBoxLayout(sets)
		setslay.addWidget(instruments)
		setslay.addWidget(setups)
		setslay.addWidget(features)
		setslay.addWidget(nfeatures)
		setslay.addWidget(vb)
		setslay.addWidget(vb2)
		container = QWidget()
		layout = QVBoxLayout(container)
		layout.addLayout(b_layout)
		layout.addWidget(sets)
		self.setCentralWidget(container)

	def refreshInstruments(self):
		self.instruments.set_items(self.rb.instrumentNames())
	def refreshFeatures(self):
		self.features.set_items(self.rb.featureNames())
		self.nfeatures.set_items(self.rb.featureNames())
	def refreshSetups(self):
		self.setups.set_items(self.rb.setupNames())
	def refresh(self):
		self.refreshInstruments()
		self.refreshFeatures()
		self.refreshSetups()

	def clear(self):
		self.instruments.select_none()
		self.setups.select_none()
		self.features.select_none()
		self.nfeatures.select_none()
		self.dirs.select_none()
		self.results.select_none()
		self.wdays.select_none()
		self.hours.select_none()
		self.hours.select_none()
		td = date.today()
		self.b_since.setDate(QDate(td.year,td.month,td.day))
		self.b_until.setDate(QDate(td.year,td.month,td.day))
		self.instrumentsb.setChecked(True)
		self.setupsb.setChecked(True)
		self.wdaysb.setChecked(True)
		self.hoursb.setChecked(True)

	def mkgrp(self, name, w, simple=False):
		b_with = None
		if not simple:
			b_layout = QHBoxLayout()
			b_with = QRadioButton("Is")
			b_without = QRadioButton("Is not")
			b_with.setChecked(True)
			b_layout.addWidget(b_with)
			b_layout.addWidget(b_without)
		g = QWidget()
		b_label = QLabel(name)
		v_layout = QVBoxLayout(g)
		v_layout.addWidget(b_label)
		if not simple:
			v_layout.addLayout(b_layout)
		v_layout.addWidget(w)
		return g, b_with

	def getFilter(self):
		# create a Filter() out of this data
		flt = Filter()
		instrset = self.instruments.checked_items()
		if not self.instrumentsb.isChecked():
			neg = set(self.rb.instrumentNames()).difference(set(instrset))
			instrset = list(neg)
		setupset = self.setups.checked_items()
		if not self.setupsb.isChecked():
			neg = set(self.rb.setupNames()).difference(set(setupset))
			setupset = list(neg)
		hasset = self.features.checked_items()
		hasnotset = self.nfeatures.checked_items()
		dirsset = [Dir[n] for n in self.dirs.checked_items()]
		resultsset = [Result[n] for n in self.results.checked_items()]
		wdaysset = self.wdays.checked_items()
		if not self.wdaysb.isChecked():
			neg = set(WDAYS).difference(set(wdaysset))
			wdaysset = list(neg)
		wdaysset = [WDay[n] for n in wdaysset]
		hoursset = self.hours.checked_items()
		if not self.hoursb.isChecked():
			neg = set(HOURS).difference(set(hoursset))
			hoursset = list(neg)
		hoursset = [int(h) for h in hoursset]
		since = self.b_since.date().toPython()
		until = self.b_until.date().toPython()

		flt.musthave = set(hasset)
		flt.canthave = set(hasnotset)
		flt.instruments = set(instrset)
		flt.setups = set(setupset)
		flt.dirs = set(dirsset)
		flt.results = set(resultsset)
		flt.wdays = set(wdaysset)
		flt.hours = set(hoursset)
		return flt

	def apply(self):
		flt = self.getFilter()
		self.setfn(flt)

	def nofilter(self):
		self.setfn(None)
