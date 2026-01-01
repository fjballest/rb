import sys
from PySide6.QtWidgets import (
	QApplication, QMainWindow, QFileDialog,
	QLabel, QScrollArea, QPushButton,
	QWidget, QVBoxLayout, QHBoxLayout
)
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtCore import Qt, QEvent
from checklist import *
from stats import *
import os
from functools import partial
from plot import XYPlotWidget
from bar import XYBarWidget
from stackbar import XYStackBarWidget
from pie import PieWidget

class StatsWindow(QMainWindow):
	def __init__(self, rb, parent=None):
		super().__init__(parent)
		self.rb = rb
		self.unit = StatUnit.Euros
		self.setWindowTitle("Stats")
		self.plotxsize = 600
		self.plotysize = 400
		self.resize(1500,800)

		kcontainer = QWidget()
		klayout = QHBoxLayout(kcontainer)
		self.unit_bs = [QRadioButton(u.name) for u in StatUnit]
		self.unit_bs[0].setChecked(True)
		for b in self.unit_bs:
			klayout.addWidget(b)
			u = StatUnit[b.text()]
			fn = partial(lambda x: self.setunit(x), x=u)
			b.clicked.connect(fn)
		klayout.addStretch()
		self.kind_bs = [QPushButton(k.name) for k in StatKind]
		for b in self.kind_bs:
			klayout.addWidget(b)
			b.setCheckable(True)
			b.setChecked(True)
			b.clicked.connect(self.plotchanged)
		self.kind_bs[-1].setChecked(False)

		scontainer = QWidget()
		slayout = QVBoxLayout(scontainer)
		self.plot_bs = [QPushButton(p.name) for p in StatPlot]
		for b in self.plot_bs:
			slayout.addWidget(b)
			b.setCheckable(True)
			b.setChecked(True)
			b.clicked.connect(self.plotchanged)
		none_bs = QPushButton("One")
		none_bs.clicked.connect(self.singlestat)
		slayout.addWidget(none_bs)
		all_bs = QPushButton("All")
		all_bs.clicked.connect(self.allstat)
		slayout.addWidget(all_bs)
		slayout.addStretch()
		large_bs = QPushButton("Size +")
		large_bs.clicked.connect(self.larger)
		small_bs = QPushButton("Size -")
		small_bs.clicked.connect(self.smaller)
		slayout.addWidget(large_bs)
		slayout.addWidget(small_bs)


		sc = QScrollArea()
		sc.setWidgetResizable(True) # Allow widget to resize
		sc.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
		#sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		self.scroll = sc
		sc.setWidget(self.mkstats())

		sw = QWidget(self)
		swlay = QVBoxLayout(sw)
		swlay.addWidget(kcontainer)
		swlay.addWidget(sc)

		w = QWidget(self)
		lay = QHBoxLayout(w)
		lay.addWidget(scontainer)
		lay.addWidget(sw)
		self.setCentralWidget(w)

	def smaller(self):
		self.plotxsize = int(self.plotxsize * 0.8)
		self.plotysize = int(self.plotysize * 0.8)
		self.plotchanged()
	def larger(self):
		self.plotxsize = int(self.plotxsize * 1.2)
		self.plotysize = int(self.plotysize * 1.2)
		self.plotchanged()

	def singlestat(self):
		for b in self.plot_bs[1:]:
			b.setChecked(False)
		self.plotchanged()
	def allstat(self):
		for b in self.plot_bs:
			b.setChecked(True)
		self.plotchanged()

	def mkplot(self, k, u, p, fn=lambda x: x):
		trades = self.rb.filteredtrades or self.rb.trades
		trades = fn(trades)
		y = tradevaluetots(trades, u)
		x = range(len(y))
		x = [str(a) for a in x]
		plot = XYPlotWidget(f"{k.name} {u.name} {p.name}")
		plot.set_data(x, y)
		plot.setFixedSize(self.plotxsize,self.plotysize)
		return plot

	def mkokpie(self, k, u, nb=None):
		trades = self.rb.filteredtrades or self.rb.trades
		if u in [StatUnit.Success, StatUnit.Failure]:
			u = StatUnit.Pts
		x, yok = perresult(trades, u, k, nb)
		res = {x[i]: yok[i] for i in range(3)}

		vok, vko, vneutral = yok[2], yok[1], yok[0]

		plot = PieWidget(["OK", "Neut", "KO"],
			[res["OK"], res["Neutral"], res["KO"]],
			self.mktitle(k, u, StatPlot.PerResult),
			colors=["green", "grey", "red"])
		plot.setFixedSize(self.plotxsize,self.plotysize)
		return plot

	def mkgraph(self, k, u, p, fn, nb=None):
		trades = self.rb.filteredtrades or self.rb.trades
		if p == StatPlot.PerResult:
			return self.mkokpie(k, u, nb=nb)
		x, y = fn(trades, u, k, nb)
		title = f"{k.name} {u.name} {p.name}"
		if k == StatKind.Cnt:
			title = f"{k.name} {p.name}"
		plot = XYBarWidget(self.mktitle(k, u, p))
		plot.set_data(x, y)
		f = 1
		if p == StatPlot.PerInstrument:
			f = 2
		plot.setFixedSize(self.plotxsize*f,self.plotysize)
		return plot

	def mktitle(self, k, u, p):
		title = f"{k.name} {u.name} {p.name}"
		if k == StatKind.Cnt:
			title = f"{k.name} {p.name}"
		return title.replace("Per", "per ")

	def mkokgraph(self, k, u, p, fn, nb=None):
		trades = self.rb.filteredtrades or self.rb.trades
		x, yok = fn(trades, StatUnit.Success, k, nb)
		x2, yko = fn(trades, StatUnit.Failure, k, nb)
		plot = XYStackBarWidget(["KO", "OK"], self.mktitle(k, u, p),
			colors = ["red", "green"])
		plot.set_data(x, [yko, yok])
		f = 1
		if p == StatPlot.PerInstrument:
			f = 2
		plot.setFixedSize(self.plotxsize*f,self.plotysize)
		return plot


	def mkstat(self, p, k):
		if p == StatPlot.Plot:
			return self.mkplot(k, self.unit, p)
		if p == StatPlot.WeekPlot:
			return self.mkplot(k, self.unit, p, Filter.thisweek)
		if p == StatPlot.MonthPlot:
			return self.mkplot(k, self.unit, p, Filter.thismonth)
		fn = self.mkgraph
		if self.unit == StatUnit.Success:
			fn = self.mkokgraph
		if p == StatPlot.PerDay:
			return fn(k, self.unit, p, perday, 10)
		if p == StatPlot.PerWeek:
			return fn(k, self.unit, p, perweek, 10)
		if p == StatPlot.PerMonth:
			return fn(k, self.unit, p, permonth, 10)
		if p == StatPlot.PerResult:
			return fn(k, self.unit, p, perresult)
		if p == StatPlot.PerSetup:
			return fn(k, self.unit, p, persetup)
		if p == StatPlot.PerInstrument:
			return fn(k, self.unit, p, perinstrument)
		if p == StatPlot.PerWeekDay:
			return fn(k, self.unit, p, perdayofweek)
		if p == StatPlot.PerHour:
			return fn(k, self.unit, p, perhour)

	def mktots(self, playout):
		trades = self.rb.filteredtrades or self.rb.trades
		t = StatTotals(self.rb.account, trades, self.unit)
		ln1 = f"account {t.account}"
		if self.unit in [StatUnit.Euros, StatUnit.SysEuros]:
			ln1 += f" return {t.pcent:.0f}%"
		ln1 += f"\t{t.ntrades} trades, total {t.total:.0f} {self.unit.name}, "
		ln1 += f"average {t.average:.0f} {self.unit.name}"
		ln2 = f"{t.nok:4} OK {t.okpcent:.0f}%\ttotal {t.totalok:.0f} {self.unit.name}\taverage {t.averageok:.0f} {self.unit.name}"
		ln3 = f"{t.nko:4} KO {t.kopcent:.0f}%\ttotal {t.totalko:.0f} {self.unit.name}\taverage {t.averageko:.0f} {self.unit.name}"
		ln4 = f"{t.nneutral:4} KO {t.neutralpcent:.0f}%\ttotal {t.totalneutral:.0f} {self.unit.name}\taverage {t.averageneutral:.0f} {self.unit.name}"
		myFont=QFont()
		myFont.setBold(True)
		for ln in [ln1, ln2, ln3, ln4]:
			lbl = QLabel(ln)
			lbl.setFont(myFont)
			playout.addWidget(lbl)

	def mkstats(self):
		x = QWidget()
		playout = QVBoxLayout(x)
		self.mktots(playout)
		#Plot, PerResult, and Week, Month use their own boxes

		if self.plot_bs[0].isChecked() or self.plot_bs[1].isChecked():
			h = QWidget()
			hlayout = QHBoxLayout(h)
			hlayout.setAlignment(Qt.AlignmentFlag.AlignLeft)
			if self.plot_bs[0].isChecked():
				w = self.mkstat(StatPlot.Plot, StatKind.Tot)
				if w is not None:
					hlayout.addWidget(w)
			w = self.mkokpie(StatKind.Tot, self.unit)
			if w is not None:
				hlayout.addWidget(w)
			playout.addWidget(h)
		if self.plot_bs[1].isChecked():
			h = QWidget()
			hlayout = QHBoxLayout(h)
			hlayout.setAlignment(Qt.AlignmentFlag.AlignLeft)
			w = self.mkokpie(StatKind.Avg, self.unit)
			hlayout.addWidget(w)
			w = self.mkokpie(StatKind.Cnt, self.unit)
			hlayout.addWidget(w)
			playout.addWidget(h)
		if self.plot_bs[2].isChecked() or self.plot_bs[3].isChecked():
			h = QWidget()
			hlayout = QHBoxLayout(h)
			hlayout.setAlignment(Qt.AlignmentFlag.AlignLeft)
			if self.plot_bs[2].isChecked():
				w = self.mkstat(StatPlot.WeekPlot, StatKind.Tot)
				if w is not None:
					hlayout.addWidget(w)
			if self.plot_bs[3].isChecked():
				w = self.mkstat(StatPlot.MonthPlot, StatKind.Tot)
				if w is not None:
					hlayout.addWidget(w)
			playout.addWidget(h)

		for i, b in enumerate(self.plot_bs):
			st = StatPlot[b.text()]
			if st <= StatPlot.MonthPlot:
				continue
			if not b.isChecked():
				continue
			if st != StatPlot.PerInstrument:
				h = QWidget()
				hlayout = QHBoxLayout(h)
				hlayout.setAlignment(Qt.AlignmentFlag.AlignLeft)
			for k in self.kind_bs:
				if not k.isChecked():
					continue
				ks = StatKind[k.text()]
				w = self.mkstat(st, ks)
				if w is not None:
					if st == StatPlot.PerInstrument:
						h = QWidget()
						hlayout = QHBoxLayout(h)
						hlayout.setAlignment(Qt.AlignmentFlag.AlignLeft)
					hlayout.addWidget(w)
					if st == StatPlot.PerInstrument:
						playout.addWidget(h)
			if st != StatPlot.PerInstrument:
				playout.addWidget(h)
		return x


	def setunit(self, w):
		self.unit = w
		self.scroll.setWidget(self.mkstats())

	def plotchanged(self):
		self.scroll.setWidget(self.mkstats())
