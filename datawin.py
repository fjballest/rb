#
# Data window (main window)
#
import sys

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QStyle
from PySide6.QtWidgets import QToolBar
from PySide6.QtWidgets import (
	QWidget, QVBoxLayout, QHBoxLayout,
	QCheckBox, QLabel, QFileDialog, QPlainTextEdit
)

from filterwin import *
from imgwin import *
from objtbl import *
from statswin import *


def create_file_actions(parent):
	style = parent.style()

	new_action = QAction(
		style.standardIcon(QStyle.StandardPixmap.SP_FileIcon),
		"New",
		parent,
	)
	new_action.setShortcut("Ctrl+N")
	new_action.setToolTip("New RoadBook")
	open_action = QAction(
		style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton),
		"Open",
		parent,
	)
	open_action.setShortcut("Ctrl+O")
	open_action.setToolTip("Open RoadBbook")

	save_action = QAction(
		style.standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton),
		"Save",
		parent,
	)
	save_action.setShortcut("Ctrl+S")
	save_action.setToolTip("Save RoadBook")

	saveas_action = QAction(
		style.standardIcon(QStyle.StandardPixmap.SP_DirLinkIcon),
		"SaveAs",
		parent,
	)
	saveas_action.setToolTip("Save RoadBook as")

	return [new_action, open_action, save_action, saveas_action]

def mktoolbar(dwin):
		toolbar = QToolBar("File", dwin)
		toolbar.setMovable(False)
		toolbar.setFloatable(False)
		toolbar.setIconSize(QSize(16, 16))
		acts = create_file_actions(dwin)
		fns = [dwin.newroadbook, dwin.openroadbook, dwin.saveroadbook,
			dwin.saveroadbookas]
		menu = dwin.menuBar()
		fmenu = menu.addMenu("&File")

		for i, a in enumerate(acts):
			toolbar.addAction(a)
			fmenu.addAction(a)
			a.triggered.connect(fns[i])
		dwin.addToolBar(toolbar)


class FileDropLineEdit(QLineEdit):
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
			file_path = event.mimeData().urls()[0].toLocalFile()
			self.setText(file_path)
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
	except:
		return 0.0

def getstr(txt):
	try:
		return str(txt).strip().replace("\n", " ")
	except:
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

		#layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
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
			rb.account.account = acc
			rb.account.neutral = neu
			rb.account.fixed = fx
			rb.account.copygraphs = cp
			self.dwin.dirtied()

	def refresh(self):
		rb = self.dwin.rb
		if not rb or not rb.account:
			return
		self.accbox.setText(f"{rb.account.account}")
		self.neutbox.setText(f"{rb.account.neutral}")
		self.fixedbox.setChecked(rb.account.fixed if rb else True)
		self.cpbox.setChecked(rb.account.copygraphs if rb else True)

class TradeEdit(QDialog):
	def __init__(self, rb, t=None, dirtied=None):
		super(TradeEdit, self).__init__()
		self.setWindowTitle(f"Trade {t.trade}")
		self.rb = rb
		self.t = t
		self.dirtiedfn = dirtied
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
		#self.setupbox.currentTextChanged.connect(self.setupchanged)
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

		self.ptsinbox = mkindouble("points", t.ptsin if t else None)
		self.ptsoutbox = mkindouble("points", t.ptsout if t else None)
		self.sysoutbox = mkindouble("points (Optional)", t.sysout if t else None)
		self.ptsstopbox = mkindouble("points (Optional)", t.ptsstop if t else None)

		self.eurosbox = mkindouble("euros (Optional)", t.euros if t else None)
		self.eurostopbox = mkindouble("euros (Optional)", t.eurstop if t else None)
		self.grafbox = FileDropLineEdit()
		self.grafbox.setPlaceholderText("drop your PNG into this form")
		if t and t.graf != "":
			self.grafbox.setText(t.graf)

		self.notesbox = mkintxt("your notes", t.notes if t else None)
		self.mistakesbox = mkintxt("your notes", t.mistakes if t else None)

		layout = QFormLayout()
		layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
		layout.addRow(QLabel("Instrument"), self.instrbox)
		layout.addRow(QLabel("Setup"), self.setupbox)
		layout.addRow(QLabel("Date"), self.datebox)
		layout.addRow(QLabel("Dir"), self.dirbox)
		layout.addRow(QLabel("Size"), self.sizebox)
		layout.addRow(QLabel("Time In"), self.timeinbox)
		layout.addRow(QLabel("Time Out"), self.timeoutbox)
		layout.addRow(QLabel("Points In"), self.ptsinbox)
		layout.addRow(QLabel("Points Out"), self.ptsoutbox)
		layout.addRow(QLabel("System Out"), self.sysoutbox)
		layout.addRow(QLabel("Points Stop"), self.ptsstopbox)
		layout.addRow(QLabel("Euros Out"), self.eurosbox)
		layout.addRow(QLabel("Euros Stop"), self.eurostopbox)
		layout.addRow(QLabel("Graphics"), self.grafbox)
		layout.addRow(QLabel("Notes"), self.notesbox)
		layout.addRow(QLabel("Mistakes"), self.mistakesbox)

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
		lay2.addWidget(self.featuresGroup)
		x.setLayout(lay2)
		mainLayout.addWidget(x)
		mainLayout.addWidget(self.errors)
		mainLayout.addWidget(self.buttonBox)
		self.setLayout(mainLayout)
		self.buttonBox.accepted.connect(self.accept)
		self.buttonBox.rejected.connect(self.reject)
		self.setAcceptDrops(True)
	def dragEnterEvent(self, event):
		if event.mimeData().hasUrls():
			self.grafbox.setPlaceholderText("Drop your PNG here")
			event.acceptProposedAction()
		else:
			event.ignore()
	def dropEvent(self, event):
		if event.mimeData().hasUrls():
			file_path = event.mimeData().urls()[0].toLocalFile()
			self.grafbox.setText(file_path)
			event.acceptProposedAction()
		else:
			event.ignore()

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
		t.ptsin = nborzero(self.ptsinbox.text())
		t.ptsout = nborzero(self.ptsoutbox.text())
		t.sysout = nborzero(self.sysoutbox.text())
		t.ptsstop = nborzero(self.ptsstopbox.text())
		t.euros = nborzero(self.eurosbox.text())
		t.eurstop = nborzero(self.eurostopbox.text())
		t.graf = getstr(self.grafbox.text())
		t.notes = getstr(self.notesbox.toPlainText())
		t.mistakes = getstr(self.mistakesbox.toPlainText())
		t.has = set(self.featuresGroup.checked_items())
		t.inval()
		e = t.checkOut()
		if e:
			self.errors.setText(e)
			return None
		try:
			if self.t is not None:
				self.t.copy_from(t)
				t = self.t
			if t.rb is None:
				t.rb = self.rb
			if t.graf:
				self.maycopygraph(t)
			self.rb.defaultsfortrade(t)
			self.rb.dirty = True
			if self.dirtiedfn is not None:
				self.dirtiedfn()
		except Exception as e:
			print(f"failed to add: {e}", file=sys.stderr)
		return t


	def accept(self):
		t = self.edited()
		if t is None:
			return
		super(TradeEdit, self).accept()

	def maycopygraph(self, t):
		src = t.graf
		dst = self.rb.mkgraphpath(t)
		t.graf = dst
		try:
			if src == dst or os.path.samefile(src, dst):
				return
		except:
			pass
		try:
			shutil.copyfile(src, dst)
			t.graf = dst
		except Exception as e:
			print(f"failed to copy graphics: {e}", file=sys.stderr)


def setfeats(q):
	q.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable|QDockWidget.DockWidgetFeature.DockWidgetFloatable)

class DataWindow(QMainWindow):
	def __init__(self, app):
		super().__init__()
		self.app = app
		self.setWindowTitle("RoadBook")
		self.resize(1500,800)
		self.r = None
		self.rb = None
		self.info = ""

		self.graphwindow = None
		self.filterwindow = None
		self.statswindow = None

		self.tradestbl = self.mktradestbl()
		self.setupstbl = self.mksetupstbl()
		self.featurestbl = self.mkfeaturestbl()
		self.instrumentstbl = self.mkinstrumentstbl()
		self.currenciestbl = self.mkcurrenciestbl()
		self.accounttbl = AccountEdit(self)

		trades = QDockWidget("Trades", self)
		setfeats(trades)
		trades.setWidget(self.tradestbl)
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
		self.tabifyDockWidget(trades, setups)
		self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, features)
		self.tabifyDockWidget(setups, features)
		self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, instruments)
		self.tabifyDockWidget(features, instruments)
		self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, currencies)
		self.tabifyDockWidget(instruments, currencies)
		self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, account)
		self.tabifyDockWidget(currencies, account)

		self.featchecks = CheckBoxGroup([], dirtied=self.dirtied)
		checks = QDockWidget("Trade Features", self)
		setfeats(checks)
		checks.setWidget(self.featchecks)
		self.featcheckswidget = checks
		self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, checks)

		self.setupchecks = CheckBoxGroup([], dirtied=self.dirtied)
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

		self.featcheckswidget.raise_()

		trades.raise_()

		mktoolbar(self)

		self.updateTitle()

	def updatetoday(self):
		self.today = TodayPanel(self.rb)
		self.todaywidget.setWidget(self.today)

	def newroadbook(self):
		if self.rb and self.rb.dirty:
			if not self.askuser('unsaved changed. sure to create another one?'):
				return
		file_path, _ = QFileDialog.getSaveFileName(
			self, "New Roadbook", "", "")
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

	def openroadbook(self):
		if self.rb and self.rb.dirty:
			if not self.askuser('unsaved changed. sure to open another one?'):
				return
		file_path = QFileDialog.getExistingDirectory(
			self, "Open Roadbook", "", QFileDialog.Option.ShowDirsOnly)
		if not file_path:
			return
		if not RoadBook.isRoadBook(file_path):
			QMessageBox.warning(
            	self,
            	"Not a roadBook",
            	f"The selected directory does not contain a roadbook.")
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
            	f"Do not have a roadbook to save")
			return
		self.rb.save()
		self.updateTitle()

	def saveroadbookas(self):
		if not self.rb or not self.rb.dir:
			QMessageBox.warning(
            	self,
            	"No roadBook",
            	f"Do not have a roadbook to save")
			return
		file_path, _ = QFileDialog.getSaveFileName(
			self, "Save (Filtered) Roadbook as", "", "")
		if not file_path:
			return
		self.rb.save(file_path, filtered=True)

	def edittrade(self, trade):
		if trade.trade == 0:
			trade.trade = self.rb.nextId()
		w = TradeEdit(self.rb, trade, self.dirtied)
		w.exec()

	def selectedtrade(self, t):
		if t and t.has is None:
			t.has = set([])
		fset = t.has if t else []
		self.featcheckswidget.setWindowTitle(f"Trade {t.trade} Features")
		self.featchecks.updateitems = fset
		self.featchecks.set_items(self.rb.featureNames(t.setup), fset)
		self.featcheckswidget.raise_()
		if self.graphwindow is not None and self.graphwindow.isVisible():
			self.tradegraphics(t)

	def mkgraph(self, p):
		self.graphwindow = ImageViewer(p)

	def tradegraphics(self, t):
		if self.rb is None:
			return
		p = self.rb.graphpath(t)
		if self.graphwindow is None:
			self.mkgraph(p)
		else:
			self.graphwindow.setimage(p)
		self.graphwindow.show()

	def selectedfeature(self, f):
		if f and f.setups is None:
			f.setups = set([])
		fset = f.setups if f else []
		x = f"{f.feature} Setups" if f else "Setups"
		self.setupchecks.updating(fset)
		self.setupchecks.dirtied = self.dirtied
		self.setupcheckswidget.setWindowTitle(x)
		self.setupchecks.set_items(self.rb.setupNames(), fset)
		self.setupcheckswidget.raise_()

	def coloured(self, t) -> int:
		return int(t.result()) if t else 0


	def mkfilter(self):
		self.filterwindow = FilterWindow(self.rb, self.setfilter)

	def setfilter(self, flt):
		if flt is None:
			self.rb.filteredtrades = None
			self.updateinfo()
			self.tradestbl.changedata(self.rb.trades)
		else:
			self.rb.filteredtrades = flt.apply(self.rb.trades)
			self.updateinfo()
			self.tradestbl.changedata(self.rb.filteredtrades)
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

	def updateTitle(self):
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
		trades = self.rb.filteredtrades or self.rb.trades
		tots = StatTotals(self.rb.account, trades)
		self.info = f"Δ{tots.total:+.0f}€ HR {tots.pcent:.1f}%"

	def infofn(self):
		return self.info

	def mktradestbl(self):
		t = tradeexample()
		t.edit = self.edittrade
		t.selected = self.selectedtrade
		t.graphics = self.tradegraphics
		t.filter = self.filter
		t.stats = self.stats
		t.dirtied = self.dirtied
		t.info = self.infofn
		tbl = ObjectTable(t, [], lambda: Trade(), TRADEVIEWORDER, TRADEVIEWRDONLY)
		return tbl
	def mksetupstbl(self):
		s = setupexample()
		s.dirtied = self.dirtied
		s.renamed = self.renamedSetup
		s.removing = self.removingSetup
		return ObjectTable(s, [], lambda: Setup(), hasedit=False )
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
	def removingSetup(self, o, done=False):
		name = o.setup
		if done and self.filterwindow is not None:
			self.filterwindow.refresh()
			return
		if self.rb is None:
			return True
		if self.rb.setupUsed(name):
			QMessageBox.warning(self,"Setup in use", f"Setup {name} is in use")
			return False
		return True
	def mkfeaturestbl(self):
		f = featureexample()
		f.selected = self.selectedfeature
		f.dirtied = self.dirtied
		f.renamed = self.renamedFeature
		f.removing = self.removingFeature
		return ObjectTable(f, [], lambda: Feature(), hasedit=False  )
	def renamedFeature(self, oname, nname):
		if self.rb is None:
			return
		if oname is not None:
			self.rb.renfeature(oname, nname)
		# else is a new element
		self.dirtied()
		try:
			self.tradestbl.refresh()
			print("refreshD", file=sys.stderr)
			self.featchecks.set_items(self.rb.featureNames())
			print("refreshE", file=sys.stderr)
			if self.filterwindow is not None:
				self.filterwindow.refresh()
		except Exception as e:
			print(e, file=sys.stderr)
	def removingFeature(self, o, done=False):
		name = o.feature
		if done and self.filterwindow is not None:
			self.filterwindow.refresh()
			return
		if self.rb is None:
			return True
		if self.rb.featureUsed(name):
			QMessageBox.warning(self,"Feature in use", f"Feature {name} is in use")
			return False
		return True
	def mkinstrumentstbl(self):
		i = instrumentexample()
		i.dirtied = self.dirtied
		i.renamed = self.renamedInstrument
		i.removing = self.removingInstrument
		return ObjectTable(i, [], lambda: Instrument(), hasedit=False )
	def renamedInstrument(self, oname, nname):
		if self.rb is None:
			return
		if oname is not None:
			self.rb.reninstrument(oname, nname)
		self.dirtied()
		self.tradestbl.refresh()
		if self.filterwindow is not None:
			self.filterwindow.refresh()
	def removingInstrument(self, o, done=False):
		name = o.instrument
		if done and self.filterwindow is not None:
			self.filterwindow.refresh()
			return
		if self.rb is None:
			return True
		if self.rb.instrumentUsed(name):
			QMessageBox.warning(self,"Instrument in use", f"Instrument {name} is in use")
			return False
		return True
	def mkcurrenciestbl(self):
		c = currencyexample()
		c.dirtied = self.dirtied
		c.renamed = self.renamedCurrency
		return ObjectTable(c, [], lambda: Currency(), hasedit=False  )
	def renamedCurrency(self, oname, nname):
		if self.rb is None:
			return
		if oname is not None:
			self.rb.rencurrency(oname, nname)
		self.dirtied()
		self.instrumentstbl.refresh()

	def changedata(self, r):
		self.rb = r
		self.updateinfo()
		self.tradestbl.changedata(r.trades)
		self.setupstbl.changedata(r.setups)
		self.featurestbl.changedata(r.features)
		self.instrumentstbl.changedata(r.instruments)
		self.currenciestbl.changedata(r.currencies)
		self.featchecks.set_items(self.rb.featureNames())
		self.updateTitle()
		self.accounttbl.refresh()
		self.updatetoday()

	def closeEvent(self, ev):
		if self.rb and self.rb.dirty:
			if not self.askuser('unsaved changed. sure to quit?'):
				ev.ignore()
				return
		ev.accept()
		self.app.quit()
