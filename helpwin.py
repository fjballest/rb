#
# the user guide (docs/MANUAL.md) in a window of the application, with its
# contents on the left and a search: Help ▸ User Guide
#
import os
import re
import sys

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QKeySequence, QShortcut, QTextCharFormat, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
	QHBoxLayout, QLabel, QLineEdit, QMainWindow, QSplitter, QTextBrowser, QToolButton, QTreeWidget,
	QTreeWidgetItem, QVBoxLayout, QWidget, QTextEdit
)

class GuideView(QTextBrowser):
	"""the text of the guide; its pictures are shrunk to fit it"""
	MAXW = 640

	def loadResource(self, kind, url):
		r = super().loadResource(kind, url)
		if kind == QTextDocument.ResourceType.ImageResource.value or kind == QTextDocument.ResourceType.ImageResource:
			from PySide6.QtGui import QImage
			img = r if isinstance(r, QImage) else QImage.fromData(r) if r is not None else None
			if img is not None and not img.isNull() and img.width() > self.MAXW:
				return img.scaledToWidth(self.MAXW, Qt.TransformationMode.SmoothTransformation)
			return img if img is not None else r
		return r

def guidepath():
	"""where MANUAL.md is: next to the program, or in its bundle"""
	for base in (getattr(sys, "_MEIPASS", None), os.path.dirname(os.path.abspath(__file__))):
		if base:
			p = os.path.join(base, "docs", "MANUAL.md")
			if os.path.exists(p):
				return p
	return None

def sections(text):
	"""[(level, title, body)] of the markdown text, split at its headings
	(# lines outside code blocks)"""
	out, cur, code = [], [0, "", []], False
	for line in text.splitlines():
		if line.startswith("```"):
			code = not code
		m = None if code else re.match(r"(#{1,4})\s+(.*)", line)
		if m:
			out.append(tuple(cur[:2]) + ("\n".join(cur[2]),))
			cur = [len(m.group(1)), m.group(2).strip(), [line]]
		else:
			cur[2].append(line)
	out.append(tuple(cur[:2]) + ("\n".join(cur[2]),))
	return [s for s in out if s[1] or s[2].strip()]

def plain(md):
	"""md without its markup, for searching"""
	return re.sub(r"[*`_#>]|\]\([^)]*\)|!\[|\[", "", md).lower()

def matches(body, words):
	t = plain(body)
	return all(w in t for w in words)

class HelpWindow(QMainWindow):
	"""the guide: the contents (or the sections a search finds) on the
	left, the text on the right, the words searched highlighted"""
	def __init__(self, appname, parent=None):
		super().__init__(parent)
		self.setWindowTitle(f"{appname} User Guide")
		self.resize(1000, 720)
		path = guidepath()
		self.text = open(path, encoding="utf-8").read() if path else f"# {appname}\n\nThe user guide is not installed."
		self.secs = sections(self.text)
		self.search = QLineEdit()
		self.search.setPlaceholderText("Search the guide")
		self.search.setClearButtonEnabled(True)
		self.search.textChanged.connect(lambda: self.timer.start())
		self.search.returnPressed.connect(lambda: self.findnext(False))
		self.timer = QTimer(self, singleShot=True, interval=250)
		self.timer.timeout.connect(self.filter)
		prev, nxt = QToolButton(), QToolButton()
		prev.setText("▲")
		prev.setToolTip("the previous place found (⇧↩)")
		prev.clicked.connect(lambda: self.findnext(True))
		nxt.setText("▼")
		nxt.setToolTip("the next place found (↩)")
		nxt.clicked.connect(lambda: self.findnext(False))
		self.count = QLabel()
		self.toc = QTreeWidget()
		self.toc.setHeaderHidden(True)
		self.toc.itemClicked.connect(self.gosection)
		self.toc.currentItemChanged.connect(lambda it, _: self.gosection(it))
		self.view = GuideView()
		self.view.setOpenExternalLinks(True)
		self.view.setOpenLinks(False)
		self.view.anchorClicked.connect(self.link)
		if path:
			self.view.setSearchPaths([os.path.dirname(path)])
		self.view.setMarkdown(self.text)
		self.view.document().setBaseUrl(QUrl.fromLocalFile(os.path.dirname(path) + "/") if path else QUrl())
		top = QHBoxLayout()
		top.addWidget(self.search, 1)
		top.addWidget(prev)
		top.addWidget(nxt)
		top.addWidget(self.count)
		left = QWidget()
		lv = QVBoxLayout(left)
		lv.setContentsMargins(0, 0, 0, 0)
		lv.addLayout(top)
		lv.addWidget(self.toc)
		split = QSplitter()
		split.addWidget(left)
		split.addWidget(self.view)
		split.setSizes([300, 700])
		self.setCentralWidget(split)
		QShortcut(QKeySequence.StandardKey.Find, self, activated=lambda: (self.search.setFocus(), self.search.selectAll()))
		QShortcut(QKeySequence("Shift+Return"), self.search, activated=lambda: self.findnext(True))
		QShortcut(QKeySequence.StandardKey.Close, self, activated=self.close)
		self.filter()

	def words(self):
		return [w for w in self.search.text().lower().split() if w]

	def filter(self):
		"""the contents, or the sections that have all the words searched"""
		words = self.words()
		self.toc.blockSignals(True)
		self.toc.clear()
		parents = {}
		n = 0
		for i, (level, title, body) in enumerate(self.secs):
			if not title or level == 1:
				continue
			if words and not matches(body, words):
				continue
			n += 1
			it = QTreeWidgetItem([title])
			it.setData(0, Qt.ItemDataRole.UserRole, i)
			p = None if words else next((parents[l] for l in range(level - 1, 0, -1) if l in parents), None)
			(p.addChild(it) if p is not None else self.toc.addTopLevelItem(it))
			parents = {l: x for l, x in parents.items() if l < level}
			parents[level] = it
		self.toc.expandAll()
		self.toc.blockSignals(False)
		self.highlight(words)
		self.count.setText(f"{n} found" if words else "")
		if words and self.toc.topLevelItemCount():
			self.toc.setCurrentItem(self.toc.topLevelItem(0))

	def highlight(self, words):
		"""mark every place where a word searched is"""
		doc = self.view.document()
		sels = []
		fmt = QTextCharFormat()
		fmt.setBackground(QColor(255, 225, 90))
		fmt.setForeground(QColor("black"))
		for w in words:
			c = QTextCursor(doc)
			while True:
				c = doc.find(w, c)
				if c.isNull():
					break
				s = QTextEdit.ExtraSelection()
				s.cursor, s.format = c, fmt
				sels.append(s)
		self.view.setExtraSelections(sels)

	def gosection(self, it):
		"""show the section of contents item it at the top"""
		if it is None:
			return
		i = it.data(0, Qt.ItemDataRole.UserRole)
		title = self.secs[i][1]
		title = re.sub(r"[*`_]", "", title)
		doc = self.view.document()
		c = QTextCursor(doc)
		while True:
			c = doc.find(title, c, QTextDocument.FindFlag.FindCaseSensitively)
			if c.isNull():
				return
			if c.block().blockFormat().headingLevel() > 0:
				break
		words = self.words()
		c.setPosition(c.selectionStart())	# no selection on the heading
		self.view.setTextCursor(c)
		end = self.view.verticalScrollBar().maximum()
		self.view.verticalScrollBar().setValue(end)	# so the heading ends up at the top
		self.view.ensureCursorVisible()
		if words:	# go to the first word found in the section
			f = doc.find(words[0], c)
			if not f.isNull():
				self.view.setTextCursor(f)
				self.view.ensureCursorVisible()

	def findnext(self, back):
		words = self.words()
		if not words:
			return
		flags = QTextDocument.FindFlag.FindBackward if back else QTextDocument.FindFlag(0)
		if not self.view.find(words[0], flags):	# wrap around
			c = self.view.textCursor()
			c.movePosition(QTextCursor.MoveOperation.End if back else QTextCursor.MoveOperation.Start)
			self.view.setTextCursor(c)
			self.view.find(words[0], flags)

	def gotosection(self, i):
		"""show section i of secs, with the contents as they are"""
		it = QTreeWidgetItem([self.secs[i][1]])
		it.setData(0, Qt.ItemDataRole.UserRole, i)
		self.gosection(it)

	def link(self, url):
		"""links to sections of the guide go there; others open outside"""
		if url.scheme() in ("http", "https", "mailto"):
			from PySide6.QtGui import QDesktopServices
			QDesktopServices.openUrl(url)
			return
		frag = url.fragment()
		if frag:
			for i, (_, title, _) in enumerate(self.secs):
				if slug(title) == frag:
					self.gotosection(i)
					return

def slug(title):
	"""the anchor GitHub makes for a heading"""
	t = re.sub(r"[^\w\- ]", "", re.sub(r"[*`]", "", title).lower())
	return t.replace(" ", "-")

guides = {}	# appname -> its window, kept while open

def showguide(appname, parent=None):
	"""open (or raise) the guide's window"""
	w = guides.get(appname)
	if w is None:	# a window of its own, so it outlives the one that opened it
		w = guides[appname] = HelpWindow(appname)
	w.show()
	w.raise_()
	w.activateWindow()
	return w

def guidetopics():
	"""[(level, title, index in sections)] of the guide's sections, for menus"""
	path = guidepath()
	if not path:
		return []
	secs = sections(open(path, encoding="utf-8").read())
	return [(lv, re.sub(r"[*`_]", "", t), i) for i, (lv, t, _) in enumerate(secs)
		if t and lv in (2, 3) and t.lower() != "contents"]

def addtopics(menu, appname):
	"""a Guide Topics submenu in menu, with an entry per section of the guide
	that opens it there; on macOS the guide also goes into the Help menu's
	search (registerhelpsearch)"""
	topics = guidetopics()
	if not topics:
		return None
	registerhelpsearch(appname)
	sub = menu.addMenu("Guide &Topics")
	for lv, title, i in topics:
		a = sub.addAction(title)
		a.triggered.connect(lambda _=False, i=i: showguide(appname).gotosection(i))
	return sub

# macOS: the search box of the Help menu lists, under Help Topics, the
# sections of the guide that have the words typed; picking one opens the
# guide there, and Show All Help Topics opens it with that search. Through
# NSUserInterfaceItemSearching, with PyObjC; without it nothing is added.
_searcher = None	# kept, so it is not collected

def registerhelpsearch(appname):
	"""add the guide to the Help menu's search, on macOS; True if done"""
	global _searcher
	if sys.platform != "darwin" or _searcher is not None:
		return _searcher is not None
	path = guidepath()
	if not path:
		return False
	try:
		import objc
		from AppKit import NSApplication
		from Foundation import NSObject
	except ImportError:
		return False
	secs = sections(open(path, encoding="utf-8").read())
	topics = [(i, re.sub(r"[*`_]", "", t), plain(t + "\n" + body)) for i, (lv, t, body) in enumerate(secs)
		if t and lv >= 2 and t.lower() != "contents"]

	class GuideSearch(NSObject, protocols=[objc.protocolNamed("NSUserInterfaceItemSearching")]):
		def searchForItemsWithSearchString_resultLimit_matchedItemHandler_(self, text, limit, handler):
			words = [w for w in str(text).lower().split() if w]
			found = []
			if words:
				# titles with the words first, then sections that have them
				intitle = [i for i, t, _ in topics if all(w in t.lower() for w in words)]
				inbody = [i for i, _, b in topics if i not in intitle and all(w in b for w in words)]
				found = (intitle + inbody)[:max(int(limit), 0) or 10]
			handler(found)

		def localizedTitlesForItem_(self, item):
			i = int(item)
			return [next((t for k, t, _ in topics if k == i), "")]

		def performActionForItem_(self, item):
			showguide(appname).gotosection(int(item))

		def showAllHelpTopicsForSearchString_(self, text):
			w = showguide(appname)
			w.search.setText(str(text))
			w.filter()

	try:
		_searcher = GuideSearch.alloc().init()
		NSApplication.sharedApplication().registerUserInterfaceItemSearchHandler_(_searcher)
	except Exception as x:
		print("help search:", x, file=sys.stderr)
		_searcher = None
		return False
	return True
