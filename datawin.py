#
# Data window (main window)
#
import sys

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
	QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
	QCheckBox, QLabel, QFileDialog, QPlainTextEdit
)
import traceback
import calendar
from datetime import date, timedelta
from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
	QApplication, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDockWidget, QFormLayout,
	QGroupBox, QLineEdit, QMainWindow, QMessageBox, QTableView, QTimeEdit
)
from checklist import CheckBoxGroup
from data import (
	RoadBook, Trade, Setup, Feature, Instrument, Currency, Dir, TRADEVIEWORDER,
	TRADEVIEWRDONLY, tradeexample,
	setupexample, featureexample, instrumentexample, currencyexample, tradedir
)
from calwin import TradeCalendar, daysign, tradeorder
from filterwin import FilterWindow, TextFilterEdit
from imgwin import ImageViewer
from menus import MainMenus, addrecent
from backup import BackupDialog
from objtbl import ObjectTable
from stats import StatTotals, StatUnit, TextFilter, tradevalue
from statswin import StatsWindow, TodayPanel
from graphocr import TradeOCR

class FileDropLineEdit(QLineEdit):
	dropped = Signal(list)	# paths of the files dropped

	def __init__(self, parent=None):
		super().__init__(parent)
		self.setAcceptDrops(True)
	def dragEnterEvent(self, event):
		if event.mimeData().hasUrls():
			self.setPlaceholderText("Drop your PNG here")
			event.acceptProposedAction()
		else:
			event.ignore()
	def dropEvent(self, event):
		if event.mimeData().hasUrls():
			self.dropped.emit([x.toLocalFile() for x in event.mimeData().urls()])
			event.acceptProposedAction()
		else:
			event.ignore()

def mkindouble(txt, v=None):
	x = QLineEdit()
	x.setPlaceholderText(txt)
	if v:
		x.setText(f"{v}")
	q = QDoubleValidator()
	q.setNotation(QDoubleValidator.Notation.StandardNotation)
	x.setValidator(q)
	return x

def mkintxt(txt, v=None):
	x = QPlainTextEdit()
	x.resize(420,50)
	x.setPlaceholderText(txt)
	if v:
		x.setPlainText(f"{v}")
	return x

def nborzero(q):
	try:
		return float(q)
	except Exception:
		return 0.0

def getstr(txt):
	try:
		return str(txt).strip().replace("\n", " ")
	except Exception:
		return ""

class AccountEdit(QWidget):
	def __init__(self, dwin):
		super(AccountEdit, self).__init__()
		self.dwin = dwin
		layout = QFormLayout(self)

		self.accbox = mkindouble("Account", 10000)
		self.accbox.editingFinished.connect(self.edited)
		self.neutbox = mkindouble("Neutral", 10)
		self.neutbox.editingFinished.connect(self.edited)
		self.fixedbox = QCheckBox("Fixed risk")
		self.fixedbox.checkStateChanged.connect(self.edited)
		self.fixedbox.setChecked(True)
		self.cpbox = QCheckBox("Copy Graphs")
		self.cpbox.checkStateChanged.connect(self.edited)
		self.cpbox.setChecked(True)

		layout.addRow(QLabel("Account"), self.accbox)
		layout.addRow(QLabel("Neutral"), self.neutbox)
		layout.addRow(QLabel("Fixed"), self.fixedbox)
		layout.addRow(QLabel("Copy Graphs"), self.cpbox)
		self.refresh()

	def edited(self):
		rb = self.dwin.rb
		if not rb or not rb.account:
			return
		a = rb.account
		acc = nborzero(self.accbox.text())
		neu = nborzero(self.neutbox.text())
		fx = self.fixedbox.isChecked()
		cp = self.cpbox.isChecked()
		if acc != a.account or neu != a.neutral or fx != a.fixed or cp  != a.copygraphs:
			neutralchanged = neu != a.neutral
			rb.account.account = acc
			rb.account.neutral = neu
			rb.account.fixed = fx
			rb.account.copygraphs = cp
			self.dwin.dirtied()
			if neutralchanged:
				# the day and group colours depend on it
				self.dwin.tradestbl.refresh()
				self.dwin.refreshcalendar()

	def refresh(self):
		rb = self.dwin.rb
		if not rb or not rb.account:
			return
		self.accbox.setText(f"{rb.account.account}")
		self.neutbox.setText(f"{rb.account.neutral}")
		self.fixedbox.setChecked(rb.account.fixed if rb else True)
		self.cpbox.setChecked(rb.account.copygraphs if rb else True)

class TradeEdit(QDialog):
	changed = Signal()	# the trade was saved into the roadbook

	def __init__(self, rb, t=None, filepath=None):
		super(TradeEdit, self).__init__()
		if filepath == False or filepath == True:
			filepath = None
		self.setWindowTitle(f"Trade {t.trade}" if t else "Trade")
		self.rb = rb
		self.t = t
		self.tOCR = None
		if t is not None and t.trade <= 0:
			t.trade = rb.nextId()
		self.formGroupBox = QGroupBox("Data:")

		self.instrbox = QComboBox()
		self.instrbox.addItems(rb.instrumentNames())
		self.instrbox.setEditable(True)
		if t:
			self.instrbox.setCurrentText(t.instrument)

		self.setupbox = QComboBox()
		self.setupbox.addItems(rb.setupNames())
		self.setupbox.setEditable(True)
		self.lastsetup = None
		if t:
			self.setupbox.setCurrentText(t.setup)
			self.lastsetup = t.setup
		ed = self.setupbox.lineEdit()
		ed.editingFinished.connect(lambda: self.setupchanged(ed.text()))
		td = date.today()
		qt = QDate(td.year, td.month, td.day)
		self.datebox = QDateEdit(date=qt,calendarPopup=True)
		self.datebox.setDate(qt)
		if t:
			self.datebox.setDate(t.datein)

		self.dirbox = QComboBox()
		self.dirbox.addItems(["Long", "Short"])
		if t:
			if t.dir == Dir.Long:
				self.dirbox.setCurrentText("Long")
			else:
				self.dirbox.setCurrentText("Short")

		self.sizebox = mkindouble("contracts", t.lots if t else None)

		self.timeinbox = QTimeEdit()
		if t:
			self.timeinbox.setTime(t.timein)

		self.timeoutbox = QTimeEdit()
		if t:
			self.timeoutbox.setTime(t.timeout)

		self.tpbox = mkindouble("TP Δpts", t.tp if t else None)
		self.stopbox = mkindouble("Stop Δpts", t.stop if t else None)
		self.outbox = mkindouble("Out Δpts", t.out if t else None)

		# to compute tp/stop/pts if we know points in/out/stop
		self.ptsinbox = mkindouble("TP at")
		self.ptsoutbox = mkindouble("Out at")
		self.ptsstopbox = mkindouble("Stop at")

		self.eurosbox = mkindouble("euros out", t.euros if t else None)
		self.grafbox = FileDropLineEdit()
		self.grafbox.dropped.connect(self.adddropped)
		self.grafbox.setPlaceholderText("drop your PNGs into this form")
		if t and t.graf is not None and len(t.graf) > 0:
			self.grafbox.setText(';'.join(t.graf))

		self.notesbox = mkintxt("your notes", t.notes if t else None)

		layout = QFormLayout()
		layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
		layout.addRow(QLabel("Instrument"), self.instrbox)
		layout.addRow(QLabel("Setup"), self.setupbox)
		layout.addRow(QLabel("Date"), self.datebox)
		layout.addRow(QLabel("Time In"), self.timeinbox)
		layout.addRow(QLabel("Time Out"), self.timeoutbox)
		layout.addRow(QLabel("Dir"), self.dirbox)
		layout.addRow(QLabel("Size"), self.sizebox)
		layout.addRow(QLabel("TP Δpts"), self.tpbox)
		layout.addRow(QLabel("Stop Δpts"), self.stopbox)
		layout.addRow(QLabel("Out Δpts"), self.outbox)
		layout.addRow(QLabel("Tp at"), self.ptsinbox)
		layout.addRow(QLabel("Out at"), self.ptsoutbox)
		layout.addRow(QLabel("Stop at"), self.ptsstopbox)

		layout.addRow(QLabel("Euros Out"), self.eurosbox)
		layout.addRow(QLabel("Graphics"), self.grafbox)
		layout.addRow(QLabel("Notes"), self.notesbox)

		fset = []
		if t and t.has is not None and len(t.has) > 0:
			fset = t.has
		self.featuresGroup = CheckBoxGroup(rb.featureNames(), fset)

		self.formGroupBox.setLayout(layout)
		self.errors = QLabel("")
		self.buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
										  QDialogButtonBox.StandardButton.Cancel)
		mainLayout = QVBoxLayout()
		x = QWidget()
		lay2 = QHBoxLayout()
		lay2.addWidget(self.formGroupBox)
		feats = QVBoxLayout()
		feats.addWidget(self.featuresGroup)
		autobtn = QPushButton("AutoFeatures")
		autobtn.setToolTip("Check the features whose name or aka names are in the notes above, "
			"as AutoFeatures does for the trades listed. Features for other setups are not checked.")
		autobtn.clicked.connect(self.autofeatures)
		feats.addWidget(autobtn)
		lay2.addLayout(feats)
		x.setLayout(lay2)
		mainLayout.addWidget(x)
		mainLayout.addWidget(self.errors)
		mainLayout.addWidget(self.buttonBox)
		self.setLayout(mainLayout)
		self.buttonBox.accepted.connect(self.accept)
		self.buttonBox.rejected.connect(self.reject)
		self.setAcceptDrops(True)
		if filepath is not None:
			if type(filepath) is not list:
				filepath = [filepath]
			self.adddropped(filepath)
	def dragEnterEvent(self, event):
		try:
			if event.mimeData().hasUrls():
				self.grafbox.setPlaceholderText("Drop your PNGs here")
				event.acceptProposedAction()
			else:
				event.ignore()
		except Exception:
			event.acceptProposedAction()

	def ocr(self, path):
		# the first call loads the OCR engine, which takes a few seconds
		QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
		try:
			return TradeOCR.OCR(path, self.rb.setupNames())
		finally:
			QApplication.restoreOverrideCursor()

	def ocrscore(self, o):
		"""how much trade data the OCR found; a known instrument counts most"""
		if o is None:
			return -1
		score = 0
		if o.instr and self.rb.findInstrument(o.instr) is not None:
			score += 3
		for v in (o.ptstp, o.ptsstop, o.success, o.size, o.tin):
			if v is not None:
				score += 1
		return score

	def ocrbest(self, paths):
		"""OCR the images and put first the one with most trade data.
		Returns the reordered paths and that image's OCR."""
		best, bestscore, bestocr = 0, -1, None
		for i, p in enumerate(paths):
			o = self.ocr(p)
			score = self.ocrscore(o)
			if score > bestscore:
				best, bestscore, bestocr = i, score, o
		return [paths[best]] + paths[:best] + paths[best+1:], bestocr

	def grafs(self):
		return [g for g in getstr(self.grafbox.text()).split(';') if g.strip()]

	def adddropped(self, paths):
		"""add dropped images to the trade; when it had none yet,
		the one with most data recognised is the primary one and fills the form"""
		paths = [p for p in paths if p]
		old = self.grafs()
		paths = [p for p in paths if p not in old]
		if not paths:
			return
		if not old:
			paths, self.tOCR = self.ocrbest(paths)
			if self.tOCR is not None:
				self.pnginfo()
		self.grafbox.setText(';'.join(old + paths))

	def pnginfo(self):
		if self.tOCR is None:
			return
		if self.tOCR.setup and len(self.setupbox.lineEdit().text()) == 0:
			self.setupbox.setCurrentText(self.tOCR.setup)
		if self.tOCR.instr and len(self.instrbox.lineEdit().text()) == 0:
			self.instrbox.setCurrentText(self.tOCR.instr)

		if self.tOCR.ptstp and len(self.tpbox.text()) == 0:
			self.tpbox.setText(f"{self.tOCR.ptstp}")
		if self.tOCR.ptsstop and len(self.stopbox.text()) == 0:
			self.stopbox.setText(f"{self.tOCR.ptsstop}")
		if self.tOCR.long is not None:
			if self.tOCR.long:
				self.dirbox.setCurrentText("Long")
			else:
				self.dirbox.setCurrentText("Short")
		if self.tOCR.success:
			self.outbox.setText(f"{self.tOCR.ptstp}")
		else:
			self.outbox.setText(f"-{self.tOCR.ptsstop}")
		if self.tOCR.size is not None:
			self.sizebox.setText(f"{self.tOCR.size}")
		if self.tOCR.at is not None:
			qt = QDate(self.tOCR.at.year, self.tOCR.at.month, self.tOCR.at.day)
			self.datebox.setDate(qt)
		if self.tOCR.tin is not None:
			self.timeinbox.setTime(self.tOCR.tin)
		if self.tOCR.tout is not None:
			self.timeoutbox.setTime(self.tOCR.tout)

	def dropEvent(self, event):
		if event.mimeData().hasUrls():
			try:
				event.acceptProposedAction()
				self.adddropped([x.toLocalFile() for x in event.mimeData().urls()])
			except Exception as e:
				print(e, file=sys.stderr)
				event.acceptProposedAction()
		else:
			event.ignore()

	def autofeatures(self):
		"""check the features named in the notes of the form"""
		found = self.rb.featuresin(self.notesbox.toPlainText(), self.setupbox.currentText())
		checked = set(self.featuresGroup.checked_items())
		new = found - checked
		if new:
			items = [self.featuresGroup.model.item(r).text() for r in range(self.featuresGroup.model.rowCount())]
			self.featuresGroup.set_items(items, checked | new)
			self.errors.setText("AutoFeatures checked " + ", ".join(sorted(new)))
		else:
			self.errors.setText("AutoFeatures: no new features in the notes")

	def setupchanged(self, txt):
		if self.lastsetup == txt or self.rb is None:
			return
		nfset = self.rb.featureNames(txt)
		self.featuresGroup.set_items(nfset)
		self.lastsetup = txt

	def edited(self):
		self.errors.setText("")
		t = Trade()
		if self.t:
			t.trade = self.t.trade
		t.instrument = getstr(self.instrbox.lineEdit().text())
		t.setup = getstr(self.setupbox.lineEdit().text())
		t.datein = self.datebox.date().toPython()
		t.timein = self.timeinbox.time().toPython()
		t.timeout = self.timeoutbox.time().toPython()
		ds = getstr(self.dirbox.currentText())
		t.dir = Dir.Long if ds == "Long" else Dir.Short
		t.lots = nborzero(self.sizebox.text())
		ptsin = nborzero(self.ptsinbox.text())
		ptsout = nborzero(self.ptsoutbox.text())
		ptsstop = nborzero(self.ptsstopbox.text())
		t.euros = nborzero(self.eurosbox.text())
		t.tp = nborzero(self.tpbox.text())
		t.stop = nborzero(self.stopbox.text())
		t.out = nborzero(self.outbox.text())
		if ptsin != 0 and ptsout != 0:
			if t.dir == Dir.Long:
				t.out = ptsout - ptsin
				if ptsstop != 0 and ptsstop > ptsin:
					self.errors.setText("bad stop for long")
					return None
				if ptsout < ptsin:
					t.tp = 0
					t.stop = ptsin-ptsout
				else:
					t.tp = ptsout - ptsin
					if ptsstop != 0:
						t.stop = ptsin - ptsstop
			else:
				t.out = ptsin - ptsout
				if ptsstop != 0 and ptsstop < ptsin:
					self.errors.setText("bad stop for short")
					return None
				if ptsout > ptsin:
					t.tp = 0
					t.stop = ptsout - ptsin
				else:
					t.tp = ptsin - ptsout
					if ptsstop != 0:
						t.stop = ptsstop - ptsin
		t.graf = self.grafs()
		t.notes = getstr(self.notesbox.toPlainText())
		t.has = set(self.featuresGroup.checked_items())
		t.inval()
		e = t.checkOut()
		if t.lots == 0:
			t.lots = 1
		if t.euros == 0:
			t.euros = t.lots * t.out
		if e:
			self.errors.setText(e)
			return None
		try:
			if self.t is not None:
				self.t.copy_from(t)
				t = self.t
			if t.rb is None:
				t.rb = self.rb
			if t.graf is not None and len(t.graf) > 0:
				self.maycopygraphs(t)
			self.rb.defaultsfortrade(t)
			self.rb.dirty = True
			self.changed.emit()
		except Exception as e:
			print(f"failed to add: {e}", file=sys.stderr)
		return t


	def accept(self):
		t = self.edited()
		if t is None:
			return
		super(TradeEdit, self).accept()

	def maycopygraphs(self, t):
		for e in self.rb.storegraphs(t):
			print(e, file=sys.stderr)

def setfeats(q):
	q.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable|QDockWidget.DockWidgetFeature.DockWidgetFloatable)

class DataWindow(QMainWindow):
	def __init__(self, app, rbs=None):
		super().__init__()
		self.app = app
		self.setWindowTitle("RoadBook")
		self.resize(1500,800)
		self.r = None
		self.rb = None
		self.info = ""

		self.graphwindow = None
		self.filterwindow = None
		self.winfilter = None	# the filter window's Filter, or None
		self.quickfilter = None	# the TextFilter of the trades tab's text box, or None
		self.statswindow = None

		self.tradestbl = self.mktradestbl()
		self.setupstbl = self.mksetupstbl()
		self.featurestbl = self.mkfeaturestbl()
		self.instrumentstbl = self.mkinstrumentstbl()
		self.currenciestbl = self.mkcurrenciestbl()
		self.accounttbl = AccountEdit(self)
		self.calendar = TradeCalendar()
		self.calendar.tradeSelected.connect(self.calendartrade)
		self.calendar.tradeActivated.connect(self.calendaropen)
		self.calendar.monthChanged.connect(self.calendarmonth)

		trades = QDockWidget("Trades", self)
		setfeats(trades)
		trades.setWidget(self.tradestbl)
		caldock = QDockWidget("Calendar", self)
		setfeats(caldock)
		caldock.setWidget(self.calendar)
		setups = QDockWidget("Setups", self)
		setfeats(setups)
		setups.setWidget(self.setupstbl)
		features = QDockWidget("Features", self)
		setfeats(features)
		features.setWidget(self.featurestbl)
		instruments = QDockWidget("Instruments", self)
		setfeats(instruments)
		instruments.setWidget(self.instrumentstbl)
		currencies = QDockWidget("Currencies", self)
		setfeats(currencies)
		currencies.setWidget(self.currenciestbl)

		account = QDockWidget("Account", self)
		setfeats(account)
		account.setWidget(self.accounttbl)

		w = QWidget(self)
		w.setFixedSize(0,0)
		self.setCentralWidget(w)

		self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, trades)
		self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, setups)
		self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, caldock)
		self.tabifyDockWidget(trades, caldock)
		self.tabifyDockWidget(caldock, setups)
		self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, features)
		self.tabifyDockWidget(setups, features)
		self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, instruments)
		self.tabifyDockWidget(features, instruments)
		self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, currencies)
		self.tabifyDockWidget(instruments, currencies)
		self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, account)
		self.tabifyDockWidget(currencies, account)

		self.featchecks = CheckBoxGroup([])
		self.featchecks.dirtied.connect(self.dirtied)
		checks = QDockWidget("Trade Features", self)
		setfeats(checks)
		checks.setWidget(self.featchecks)
		self.featcheckswidget = checks
		self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, checks)

		self.setupchecks = CheckBoxGroup([])
		self.setupchecks.dirtied.connect(self.dirtied)
		checks = QDockWidget("Feature Setups", self)
		setfeats(checks)
		checks.setWidget(self.setupchecks)
		self.setupcheckswidget = checks
		self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, checks)
		self.tabifyDockWidget(self.featcheckswidget, self.setupcheckswidget)

		self.today = TodayPanel(self.rb)
		today = QDockWidget("Today", self.rb)
		setfeats(today)
		today.setWidget(self.today)
		self.todaywidget = today
		self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, today)
		self.tabifyDockWidget(self.setupcheckswidget, self.todaywidget)

		self.todaywidget.raise_()

		trades.raise_()
		self.tradesdock = trades

		self.leftdocks = [trades, caldock, setups, features, instruments, currencies, account]
		self.rightdocks = [self.featcheckswidget, self.setupcheckswidget, self.todaywidget]
		self.menus = MainMenus(self, rbs)

		self.updateTitle()
		# once the event loop runs, the window and its first roadbook are in place
		QTimer.singleShot(0, self.shrinkrightdock)

	def shrinkrightdock(self):
		# docks are never made narrower than their minimum, so ask for 1 pixel
		# on the right and give the rest to the trades on the left
		self.resizeDocks([self.tradesdock, self.todaywidget], [self.width(), 1],
			Qt.Orientation.Horizontal)

	def moveTo(self, delta):
		# move to next prev callback
		if delta > 0:
			self.tradestbl.next()
		if delta < 0:
			self.tradestbl.prev()

	def updatetoday(self):
		self.today = TodayPanel(self.rb)
		self.todaywidget.setWidget(self.today)

	def newroadbook(self):
		if self.rb and self.rb.dirty:
			if not self.askuser('unsaved changed. sure to create another one?'):
				return
		file_path, _ = QFileDialog.getSaveFileName(
			self, "New Roadbook", tradedir(), "")
		if not file_path:
			return
		try:
			RoadBook.mknew(file_path)
			rb = RoadBook()
			rb.load(file_path)
		except Exception as e:
			QMessageBox.warning(
            	self,
            	"Failed to save",
            	f"Failed to save: {e}")
			return
		self.changedata(rb)
		self.updateTitle()

	def askuser(self, msg):
		qm = QMessageBox
		r = qm.question(self, '', msg, qm.StandardButton.Yes, qm.StandardButton.No)
		return r == qm.StandardButton.Yes

	def openroadbook1(self, s):
		if self.rb and self.rb.dirty:
			if not self.askuser('unsaved changed. sure to open another one?'):
				return
		if not RoadBook.isRoadBook(s):
			QMessageBox.warning(
            	self,
            	"Not a roadBook",
            	"The selected directory does not contain a roadbook.")
			return
		rb = RoadBook()
		rb.load(s)
		self.changedata(rb)
		self.updateTitle()

	def openroadbook(self):
		if self.rb and self.rb.dirty:
			if not self.askuser('unsaved changed. sure to open another one?'):
				return
		file_path = QFileDialog.getExistingDirectory(
			self, "Open Roadbook", tradedir(), QFileDialog.Option.ShowDirsOnly)
		if not file_path:
			return
		if not RoadBook.isRoadBook(file_path):
			QMessageBox.warning(
            	self,
            	"Not a roadBook",
            	"The selected directory does not contain a roadbook.")
			return
		rb = RoadBook()
		rb.load(file_path)
		self.changedata(rb)
		self.updateTitle()

	def saveroadbook(self):
		if not self.rb or not self.rb.dir:
			QMessageBox.warning(
            	self,
            	"No roadBook",
            	"Do not have a roadbook to save")
			return
		self.rb.save()
		self.updateTitle()

	def backups(self):
		if not self.rb or not self.rb.dir:
			QMessageBox.warning(self, "No roadBook", "Do not have a roadbook to back up")
			return
		dlg = BackupDialog(self)
		dlg.restored.connect(self.reload)
		dlg.exec()

	def reload(self):
		"""read the roadbook again from disk, dropping changes in memory"""
		rb = RoadBook()
		rb.load(self.rb.dir)
		self.changedata(rb)
		self.updateTitle()

	def saveroadbookas(self):
		if not self.rb or not self.rb.dir:
			QMessageBox.warning(
            	self,
            	"No roadBook",
            	"Do not have a roadbook to save")
			return
		file_path, _ = QFileDialog.getSaveFileName(
			self, "Save (Filtered) Roadbook as", tradedir(), "")
		if not file_path:
			return
		self.rb.save(file_path, filtered=True)

	def edittrade(self, trade, filepath=None):
		if trade.trade == 0:
			trade.trade = self.rb.nextId()
		try:
			w = TradeEdit(self.rb, trade, filepath=filepath)
			w.changed.connect(self.dirtiedTrades)
			w.exec()
		except Exception as e:
			print(e, file=sys.stderr)
	def calendartrade(self, t):
		"""a day was clicked in the calendar: select its first trade"""
		self.tradestbl.selectobj(t)

	def calendaropen(self, t):
		"""a day was double clicked: select its first trade and show the trades"""
		self.tradestbl.selectobj(t)
		self.tradesdock.raise_()

	def calendarmonth(self, y, m):
		"""the calendar moved to another month: show that month in the trades table"""
		M = self.tradestbl.model
		ts = [t for t in M.ordered() if t.datein and (t.datein.year, t.datein.month) == (y, m)]
		if not ts:
			return
		M.collapseexcept(ts)
		row = M.rowofgroup((y, m))
		if row >= 0:
			self.tradestbl.view.scrollTo(M.index(row, 0), QTableView.ScrollHint.PositionAtTop)

	def initialgroups(self):
		"""open only the last year, month and week of trades; when that week
		just started (its last trade is on Monday or Tuesday), the week before too"""
		M = self.tradestbl.model
		ts = [t for t in M.ordered() if t.datein]
		if not ts:
			return
		keep = [ts[-1]]
		d = ts[-1].datein
		if d.weekday() <= 1:
			monday = d - timedelta(days=d.weekday())
			before = [t for t in ts if t.datein < monday]
			if before:
				keep.append(before[-1])
		M.collapseexcept(keep)
		QTimer.singleShot(0, self.tradestbl.view.scrollToBottom)

	def refreshcalendar(self):
		if self.rb is None:
			return
		trades = self.rb.filteredtrades if self.rb.filteredtrades is not None else self.rb.trades
		self.calendar.settrades(trades, self.rb.account.neutral if self.rb.account else 0)

	def tradegroups(self, t):
		"""year, month and week of a trade, for the trades table"""
		d = t.datein or date.min
		y, m = d.year, d.month
		w = d.isocalendar()[1]
		return [((y,), str(y)), ((y, m), calendar.month_name[m]), ((y, m, w), f"Week {w}")]

	def groupinfo(self, trades):
		v = sum(tradevalue(t, StatUnit.Euros) for t in trades)
		neutral = self.rb.account.neutral if self.rb and self.rb.account else 0
		n = len(trades)
		return f"{n} trade{'s' if n != 1 else ''}, {v:+.0f}€", daysign(v, neutral)

	def selectedtrade(self, t):
		if t and t.has is None:
			t.has = set([])
		if t:
			self.calendar.showdate(t.datein)
		fset = t.has if t else []
		self.featcheckswidget.setWindowTitle(f"Trade {t.trade} Features")
		self.featchecks.updateitems = fset
		self.featchecks.set_items(self.rb.featureNames(t.setup), fset)
		self.featcheckswidget.raise_()
		if self.graphwindow is not None and self.graphwindow.isVisible():
			self.tradegraphics(t)

	def mkgraph(self, p, desc=''):
		self.graphwindow = ImageViewer(p, desc=desc)
		self.graphwindow.moved.connect(self.moveTo)
		self.graphwindow.jumped.connect(self.tradestbl.edge)

	def tradegraphics(self, t):
		if self.rb is None:
			return
		p = self.rb.graphpaths(t)
		if self.graphwindow is None:
			self.mkgraph(p, desc=t.notes)
		self.graphwindow.setimage(p, desc=t.notes or '')
		self.graphwindow.show()

	def selectedfeature(self, f):
		if f and f.setups is None:
			f.setups = set([])
		fset = f.setups if f else []
		x = f"{f.feature} Setups" if f else "Setups"
		self.setupchecks.updating(fset)
		self.setupcheckswidget.setWindowTitle(x)
		self.setupchecks.set_items(self.rb.setupNames(), fset)
		self.setupcheckswidget.raise_()

	def coloured(self, t) -> int:
		return int(t.result()) if t else 0


	def mkfilter(self):
		self.filterwindow = FilterWindow(self.rb)
		self.filterwindow.filterChanged.connect(self.setfilter)

	def setfilter(self, flt):
		"""the filter window's filter, None for none"""
		self.winfilter = flt
		self.applyfilters()

	def setquickfilter(self, text):
		"""the text box of the trades tab; empty text filters nothing"""
		self.quickfilter = TextFilter(text) if text else None
		self.applyfilters()

	def applyfilters(self):
		"""list the trades that pass both the filter window's filter and
		the trades tab's text filter"""
		if self.rb is None:
			return
		if self.winfilter is None and self.quickfilter is None:
			self.rb.filteredtrades = None
		else:
			trades = self.rb.trades
			for flt in (self.winfilter, self.quickfilter):
				if flt is not None:
					trades = flt.apply(trades)
			self.rb.filteredtrades = trades
		self.updateinfo()
		self.tradestbl.changedata(self.rb.listedtrades())
		self.refreshcalendar()
		if self.statswindow:
			self.statswindow.plotchanged()

	def filter(self):
		if self.filterwindow is None:
			self.mkfilter()
		self.filterwindow.show()

	def mkstats(self):
		self.statswindow = StatsWindow(self.rb)

	def stats(self):
		if self.statswindow is None:
			self.mkstats()
		self.statswindow.show()

	def dirtied(self):
		if not self.rb:
			return
		self.rb.dirty = True
		self.updateTitle()

	def dirtiedTrades(self):
		self.dirtied()
		self.updatetoday()
		self.updateinfo()
		self.refreshcalendar()
		if self.statswindow:
			self.statswindow.plotchanged()


	def tables(self):
		return [self.tradestbl, self.setupstbl, self.featurestbl, self.instrumentstbl, self.currenciestbl]

	def findintable(self):
		"""find in the table with the focus, else the one shown, else the trades"""
		# tabbed docks behind another one are still "visible"
		shown = [t for t in self.tables() if t.isVisible() and not t.visibleRegion().isEmpty()]
		focus = QApplication.focusWidget()
		for tbl in shown:
			if focus is not None and tbl.isAncestorOf(focus):
				tbl.find()
				return
		if shown:
			shown[0].find()
			return
		self.tradesdock.show()
		self.tradesdock.raise_()
		self.tradestbl.find()

	def updateTitle(self):
		if hasattr(self, "menus"):
			self.menus.save.setEnabled(bool(self.rb and self.rb.dir))
			self.menus.backup.setEnabled(bool(self.rb and self.rb.dir))
		if self.rb and self.rb.dirty and self.rb.dir:
			self.setWindowTitle(f"RoadBook {self.rb.dir} (unsaved)")
		elif self.rb and self.rb.dir:
			self.setWindowTitle(f"RoadBook {self.rb.dir}")
		elif self.rb:
			self.setWindowTitle("RoadBook")
		else:
			self.setWindowTitle("No RoadBook")


	def updateinfo(self):
		if self.rb is None or not self.rb.account:
			self.info = ""
			return
		trades = self.rb.listedtrades()
		tots = StatTotals(self.rb.account, trades)
		self.info = f"Δ{tots.total:+.0f}€ R={tots.pcent:.1f}%"

	def infofn(self):
		self.updateinfo()
		return self.info

	def mktradestbl(self):
		tbl = ObjectTable(tradeexample(), [], lambda: Trade(), TRADEVIEWORDER, TRADEVIEWRDONLY,
			drop=True, editor=self.edittrade, info=self.infofn,
			extrabuttons=("Graphics", "Filter", "Stats"),
			groupby=self.tradegroups, sortkey=tradeorder, groupinfo=self.groupinfo)
		tbl.selected.connect(self.selectedtrade)
		tbl.graphicsRequested.connect(self.tradegraphics)
		tbl.filterRequested.connect(self.filter)
		tbl.statsRequested.connect(self.stats)
		self.quicktext = TextFilterEdit()
		self.quicktext.setMinimumWidth(160)
		self.quicktext.edited.connect(self.setquickfilter)
		tbl.addwidget(self.quicktext, 1)
		tbl.dirtied.connect(self.dirtied)
		tbl.dirtied.connect(self.refreshcalendar)
		tbl.edited.connect(self.dirtiedTrades)
		tbl.fieldChanged.connect(self.tradeFieldChanged)
		return tbl

	def mknamestbl(self, example, factory, renamed, canremove=None):
		"""table for setups, features, instruments or currencies"""
		tbl = ObjectTable(example, [], factory, hasedit=False, uniquekey=True, canremove=canremove)
		tbl.dirtied.connect(self.dirtied)
		tbl.renamed.connect(renamed)
		tbl.removed.connect(self.refreshfilter)
		tbl.fieldChanged.connect(self.nameFieldChanged)
		return tbl

	def tradeFieldChanged(self, t, name):
		"""a trade cell was edited or replaced: add the instrument, setup
		or features it now names if the roadbook does not have them"""
		if self.rb is None or name not in ("instrument", "setup", "has"):
			return
		self.rb.defaultinstr(t.instrument)
		self.rb.defaultsetup(t.setup)
		self.rb.defaultfeatures(t.has, t.setup)
		self.refreshnames()
		self.dirtiedTrades()

	def nameFieldChanged(self, o, name):
		"""same for the setups of a feature and the currency of an instrument"""
		if self.rb is None:
			return
		if name == "setups":
			self.rb.defaultsetups(o.setups)
		elif name == "currency":
			self.rb.defaultcurrency(o.currency)
		else:
			return
		self.refreshnames()

	def refreshnames(self):
		"""show setups, features, instruments or currencies added to the roadbook"""
		rb = self.rb
		added = False
		for tbl, objs in [(self.setupstbl, rb.setups), (self.featurestbl, rb.features),
				(self.instrumentstbl, rb.instruments), (self.currenciestbl, rb.currencies)]:
			if tbl.model.rowCount() != len(objs):
				tbl.changedata(objs)
				added = True
		if added:
			self.featchecks.set_items(rb.featureNames())
			self.refreshfilter()

	def refreshfilter(self):
		if self.filterwindow is not None:
			self.filterwindow.refresh()

	def canremove(self, what, name, used):
		if self.rb is None:
			return True
		if used(name):
			QMessageBox.warning(self, f"{what} in use", f"{what} {name} is in use")
			return False
		return True

	def mksetupstbl(self):
		return self.mknamestbl(setupexample(), lambda: Setup(), self.renamedSetup,
			lambda o: self.canremove("Setup", o.setup, self.rb.setupUsed))
	def renamedSetup(self, oname, nname):
		if self.rb is None:
			return
		try:
			if oname is not None:
				self.rb.rensetup(oname, nname)
			self.dirtied()
			self.tradestbl.refresh()
			if self.filterwindow is not None:
				self.filterwindow.refresh()
		except Exception as e:
			print(e, file=sys.stderr)
	def mkfeaturestbl(self):
		tbl = self.mknamestbl(featureexample(), lambda: Feature(), self.renamedFeature,
			lambda o: self.canremove("Feature", o.feature, self.rb.featureUsed))
		tbl.selected.connect(self.selectedfeature)
		tbl.addbutton("ClearAll", "Remove all the features from the trades listed "
			"(only the filtered ones when a filter is on). Asks first.", self.clearfeatures)
		tbl.addbutton("AutoFeatures", "Look for each feature's name and its aka names as "
			"words in the notes of the trades listed, ignoring case, and add the features "
			"found to those trades. Features for other setups are not added.", self.autofeatures)
		return tbl

	def clearfeatures(self):
		if self.rb is None:
			return
		trades = self.rb.listedtrades()
		n = sum(1 for t in trades if t.has)
		if n == 0:
			QMessageBox.information(self, "ClearAll", "No trade listed has features.")
			return
		if not self.askuser(f"Remove the features of {n} trade{'s' if n != 1 else ''}?"):
			return
		self.rb.clearfeatures(trades)
		self.featureschanged()

	def autofeatures(self):
		if self.rb is None:
			return
		nfeat, ntrades = self.rb.autofeatures(self.rb.listedtrades())
		if nfeat:
			self.featureschanged()
			msg = f"Added {nfeat} feature{'s' if nfeat != 1 else ''} to {ntrades} trade{'s' if ntrades != 1 else ''}."
		else:
			msg = "No new features found in the notes."
		QMessageBox.information(self, "AutoFeatures", msg)

	def featureschanged(self):
		"""the features of many trades changed"""
		self.tradestbl.refresh()
		cur = self.tradestbl.view.currentIndex()
		t = self.tradestbl.model.objat(cur.row()) if cur.isValid() else None
		if t is not None:
			self.selectedtrade(t)	# its features panel
		self.dirtiedTrades()

	def renamedFeature(self, oname, nname):
		if self.rb is None:
			return
		if oname is not None:
			self.rb.renfeature(oname, nname)
		# else is a new element
		self.dirtied()
		try:
			self.tradestbl.refresh()
			self.featchecks.set_items(self.rb.featureNames())
			if self.filterwindow is not None:
				self.filterwindow.refresh()
		except Exception as e:
			print(e, file=sys.stderr)
	def mkinstrumentstbl(self):
		return self.mknamestbl(instrumentexample(), lambda: Instrument(), self.renamedInstrument,
			lambda o: self.canremove("Instrument", o.instrument, self.rb.instrumentUsed))
	def renamedInstrument(self, oname, nname):
		if self.rb is None:
			return
		if oname is not None:
			self.rb.reninstrument(oname, nname)
		self.dirtied()
		self.tradestbl.refresh()
		if self.filterwindow is not None:
			self.filterwindow.refresh()
	def mkcurrenciestbl(self):
		return self.mknamestbl(currencyexample(), lambda: Currency(), self.renamedCurrency)
	def renamedCurrency(self, oname, nname):
		if self.rb is None:
			return
		if oname is not None:
			self.rb.rencurrency(oname, nname)
		self.dirtied()
		self.instrumentstbl.refresh()

	def changedata(self, r):
		self.rb = r
		# a new roadbook starts unfiltered
		self.winfilter = self.quickfilter = None
		r.filteredtrades = None
		if self.filterwindow is not None:
			self.filterwindow.rb = r
			self.filterwindow.refresh()
		self.quicktext.blockSignals(True)
		self.quicktext.clear()
		self.quicktext.lasttext = ""
		self.quicktext.check()
		self.quicktext.timer.stop()
		self.quicktext.blockSignals(False)
		try:
			self.updateinfo()
			self.tradestbl.changedata(r.trades)
			self.initialgroups()
			self.setupstbl.changedata(r.setups)
			self.featurestbl.changedata(r.features)
			self.instrumentstbl.changedata(r.instruments)
			self.currenciestbl.changedata(r.currencies)
			self.featchecks.set_items(self.rb.featureNames())
			self.updateTitle()
			self.accounttbl.refresh()
			self.updatetoday()
			self.refreshcalendar()
			if r.dir:
				addrecent(r.dir)
				self.menus.updaterecent()
		except Exception as e:
			print("failed: ", e, file=sys.stderr)
			traceback.print_exc()
		self.updateinfo()

	def closeEvent(self, ev):
		g = self.graphwindow
		if g is not None and not g.keepdrawings("quitting"):
			ev.ignore()
			return
		if self.rb and self.rb.dirty:
			if not self.askuser('unsaved changed. sure to quit?'):
				ev.ignore()
				return
		ev.accept()
		self.app.quit()
