#
# main window menus, toolbar and the list of recently used roadbooks
#
import os

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QMenu, QMessageBox, QToolBar, QToolButton

from data import RoadBook
from icons import icon

RECENTMAX = 10
QUICKMAX = 6	# roadbooks with their own toolbar button

def settings():
	return QSettings("pylg", "RoadBook")

def recentrbs():
	"""recently used roadbook directories, newest first"""
	v = settings().value("recent", [])
	if isinstance(v, str):
		v = [v]
	return [p for p in (v or []) if p]

def addrecent(path):
	path = os.path.abspath(path)
	l = [path] + [p for p in recentrbs() if p != path]
	settings().setValue("recent", l[:RECENTMAX])

def clearrecent():
	settings().setValue("recent", [])

def rbname(path, paths):
	"""a short name for path, with its parent when another one has the same name"""
	name = os.path.basename(path.rstrip(os.sep)) or path
	same = [p for p in paths if os.path.basename(p.rstrip(os.sep)) == name]
	if len(same) > 1:
		parent = os.path.basename(os.path.dirname(path.rstrip(os.sep)))
		return f"{parent}/{name}"
	return name

def mkaction(dwin, text, fn, iconname=None, shortcut=None, tip=None, role=None):
	a = QAction(text, dwin)
	if iconname:
		a.setIcon(icon(iconname))
	if shortcut:
		a.setShortcut(QKeySequence(shortcut))
	if tip:
		a.setToolTip(tip)
		a.setStatusTip(tip)
	if role is not None:
		a.setMenuRole(role)
	a.triggered.connect(lambda _=False: fn())
	return a

class MainMenus:
	"""builds the menu bar and toolbar of the DataWindow dwin.
	located are roadbooks found on disk, offered after the recent ones."""
	def __init__(self, dwin, located=None):
		self.dwin = dwin
		self.located = located or []
		self.quick = []
		d = dwin
		self.new = mkaction(d, "&New Roadbook…", d.newroadbook, "new", QKeySequence.StandardKey.New,
			"create a new roadbook")
		self.open = mkaction(d, "&Open Roadbook…", d.openroadbook, "open", QKeySequence.StandardKey.Open,
			"open a roadbook directory")
		self.save = mkaction(d, "&Save", d.saveroadbook, "save", QKeySequence.StandardKey.Save,
			"save the roadbook")
		self.saveas = mkaction(d, "Save &As…", d.saveroadbookas, "saveas", "Ctrl+Shift+S",
			"save the (filtered) roadbook in another directory")
		self.quit = mkaction(d, "&Quit", d.close, "quit", QKeySequence.StandardKey.Quit,
			role=QAction.MenuRole.QuitRole)
		self.recent = QMenu("Open &Recent", d)
		self.recent.setIcon(icon("recent"))
		self.recent.aboutToShow.connect(self.fillrecent)
		self.mkmenubar()
		self.mktoolbar()
		self.updaterecent()

	def mkmenubar(self):
		d = self.dwin
		mb = d.menuBar()
		f = mb.addMenu("&File")
		f.addAction(self.new)
		f.addAction(self.open)
		f.addMenu(self.recent)
		f.addSeparator()
		f.addAction(self.save)
		f.addAction(self.saveas)
		f.addSeparator()
		f.addAction(self.quit)

		t = d.tradestbl
		e = mb.addMenu("&Edit")
		e.addAction(mkaction(d, "&New Trade…", t.add_row, shortcut="Ctrl+T", tip="add a trade"))
		e.addAction(mkaction(d, "&Edit Trade…", t.edit_row, shortcut="Ctrl+E", tip="edit the selected trade"))
		e.addAction(mkaction(d, "&Delete Trade", t.delete_row, tip="delete the selected trade"))
		e.addSeparator()
		e.addAction(mkaction(d, "&Find and Replace…", d.findintable, "find",
			QKeySequence.StandardKey.Find, "find in the table shown"))
		for tbl in d.tables():
			tbl.findshortcut.setEnabled(False)	# the menu has it

		v = mb.addMenu("&View")
		for i, dock in enumerate(d.leftdocks):
			v.addAction(mkaction(d, dock.windowTitle(), lambda dock=dock: self.showdock(dock),
				shortcut=f"Ctrl+{i+1}" if i < 9 else None))
		v.addSeparator()
		v.addAction(mkaction(d, "Expand or Collapse All Trades", d.tradestbl.model.toggleall,
			shortcut="Ctrl+Shift+E"))
		v.addSeparator()
		v.addAction(mkaction(d, "&Graphics", t.graphics, "graphics", "Ctrl+G", "show the graphs of the selected trade"))
		v.addAction(mkaction(d, "&Filter…", d.filter, "filter", "Ctrl+Shift+F", "filter the trades"))
		v.addAction(mkaction(d, "&Statistics", d.stats, "stats", tip="show the statistics"))
		v.addSeparator()
		panels = v.addMenu("Side &Panels")
		for dock in d.rightdocks:
			panels.addAction(dock.toggleViewAction())

		h = mb.addMenu("&Help")
		h.addAction(mkaction(d, "&About RoadBook", self.about, role=QAction.MenuRole.AboutRole))

	def mktoolbar(self):
		d = self.dwin
		tb = QToolBar("File", d)
		tb.setObjectName("filetoolbar")
		tb.setMovable(False)
		tb.setFloatable(False)
		tb.setIconSize(QSize(20, 20))
		tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
		self.new.setIconText("New")
		self.open.setIconText("Open")
		self.save.setIconText("Save")
		self.saveas.setIconText("Save As")
		tb.addAction(self.new)
		# open, with the recent roadbooks in its drop down
		ob = QToolButton(tb)
		ob.setDefaultAction(self.open)
		ob.setMenu(self.recent)
		ob.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
		ob.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
		tb.addWidget(ob)
		tb.addAction(self.save)
		tb.addAction(self.saveas)
		tb.addSeparator()
		self.toolbar = tb
		self.quickgroup = QActionGroup(d)
		self.quickgroup.setExclusive(True)
		d.addToolBar(tb)

	def candidates(self):
		"""roadbooks to offer: recent ones first, then those found on disk"""
		l = [p for p in recentrbs() if RoadBook.isRoadBook(p)]
		for p in self.located:
			p = os.path.abspath(p)
			if p not in l:
				l.append(p)
		return l

	def updaterecent(self):
		"""a button for each of the most recent roadbooks, the open one checked"""
		d = self.dwin
		for a in self.quick:
			self.toolbar.removeAction(a)
			self.quickgroup.removeAction(a)
		self.quick = []
		cur = os.path.abspath(d.rb.dir) if d.rb and d.rb.dir else None
		paths = self.candidates()[:QUICKMAX]
		for p in paths:
			a = QAction(icon("book"), rbname(p, paths), d)
			a.setToolTip(f"open {p}")
			a.setStatusTip(f"open {p}")
			a.setCheckable(True)
			a.setChecked(p == cur)
			a.triggered.connect(lambda _=False, p=p: self.openrecent(p))
			self.quickgroup.addAction(a)
			self.toolbar.addAction(a)
			self.quick.append(a)

	def fillrecent(self):
		m = self.recent
		m.clear()
		paths = recentrbs()
		for p in paths:
			a = m.addAction(f"{rbname(p, paths)}    {os.path.dirname(p)}")
			a.setEnabled(RoadBook.isRoadBook(p))
			a.triggered.connect(lambda _=False, p=p: self.openrecent(p))
		if not paths:
			m.addAction("No recent roadbooks").setEnabled(False)
		m.addSeparator()
		clear = m.addAction("Clear Recent")
		clear.setEnabled(bool(paths))
		clear.triggered.connect(self.clear)

	def clear(self):
		clearrecent()
		self.updaterecent()

	def openrecent(self, p):
		self.dwin.openroadbook1(p)
		self.updaterecent()	# checks the open one again if the user cancelled

	def showdock(self, dock):
		dock.show()
		dock.raise_()

	def about(self):
		QMessageBox.about(self.dwin, "About RoadBook",
			"<b>RoadBook</b><p>A trading roadbook: trades, setups, features, "
			"graphs and statistics.</p>")
