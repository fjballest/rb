#
# the Window menu: lay out the windows shown on the screen of the active one,
# as a mosaic, side by side, one big and the others beside it..., or the
# active one alone on a half of the screen. The same file is in RoadBook (rb)
# and DayJournal (pyjou); keep them the same.
#
import math

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QMenu

def narrow(*buttons):
	"""let push buttons get as narrow as their text when the window is, so
	windows fit the layouts; they keep their usual width when there is room"""
	for b in buttons:
		b.setMinimumWidth(b.fontMetrics().horizontalAdvance(b.text()) + 16)

def windows(active=None):
	"""the windows shown, the active one first: main windows and dialogs,
	not floating tool bars, docks or menus"""
	kinds = (Qt.WindowType.Window, Qt.WindowType.Dialog)
	ws = [w for w in QApplication.topLevelWidgets()
		if w.isVisible() and not w.isMinimized() and w.windowType() in kinds]
	# as they are on the screen, top to bottom and left to right, so a
	# layout keeps them more or less where they were
	ws.sort(key=lambda w: (w.frameGeometry().top(), w.frameGeometry().left()))
	active = active or QApplication.activeWindow()
	if active in ws:
		ws.remove(active)
		ws.insert(0, active)
	return ws

def place(w, r, screen=None):
	"""put window w, with its frame, in rectangle r of the screen; a window
	that can't be made that small is moved back into the screen"""
	if w.isMaximized() or w.isFullScreen():
		w.showNormal()
	fg, g = w.frameGeometry(), w.geometry()
	l, t = g.left() - fg.left(), g.top() - fg.top()
	rt, b = fg.right() - g.right(), fg.bottom() - g.bottom()
	w.setGeometry(r.adjusted(l, t, -rt, -b))
	fg = w.frameGeometry()
	if screen is not None and not screen.contains(fg):
		dx = min(0, screen.right() - fg.right())
		dy = min(0, screen.bottom() - fg.bottom())
		w.move(max(screen.left(), fg.left() + dx), max(screen.top(), fg.top() + dy))

def split(r, n, across=True):
	"""r in n parts, side by side (across) or one over the other"""
	parts = []
	for i in range(n):
		if across:
			x0, x1 = r.left() + r.width() * i // n, r.left() + r.width() * (i + 1) // n
			parts.append(QRect(x0, r.top(), x1 - x0, r.height()))
		else:
			y0, y1 = r.top() + r.height() * i // n, r.top() + r.height() * (i + 1) // n
			parts.append(QRect(r.left(), y0, r.width(), y1 - y0))
	return parts

def grid(r, n):
	"""a mosaic of n cells, in rows; a last row with fewer cells has them wider"""
	if n == 0:
		return []
	cols = math.ceil(math.sqrt(n))
	rows = math.ceil(n / cols)
	cells = []
	for i, row in enumerate(split(r, rows, across=False)):
		k = min(cols, n - i * cols)
		cells += split(row, k)
	return cells

def halves(r, across=True):
	return split(r, 2, across)

# layouts of all the windows shown: name -> fn(screen rect, n) -> rects,
# for the active window first
def mainleft(r, n):
	if n == 1:
		return [r]
	left, right = halves(r)
	return [left] + split(right, n - 1, across=False)

def maintop(r, n):
	if n == 1:
		return [r]
	top, bottom = halves(r, across=False)
	return [top] + split(bottom, n - 1)

def cascade(r, n):
	step = 32
	w, h = r.width() * 2 // 3, r.height() * 2 // 3
	rects = []
	for i in range(n):
		k = i % max(1, min((r.width() - w) // step, (r.height() - h) // step) + 1)
		rects.append(QRect(r.left() + k * step, r.top() + k * step, w, h))
	return rects[::-1]	# the active one last, on top

ALL = (
	("&Tile", grid, "Ctrl+Alt+T", "all the windows as a mosaic"),
	("Side by &Side", lambda r, n: split(r, n), None, "all the windows in columns"),
	("Sta&cked", lambda r, n: split(r, n, across=False), None, "all the windows in rows"),
	("Main on the &Left", mainleft, None, "this window on the left half, the others on the right"),
	("Main on &Top", maintop, None, "this window on the top half, the others below"),
	("Casca&de", cascade, None, "all the windows one over the other, a bit apart"),
)

# where the active window alone goes: name -> fn(screen rect) -> rect
def center(r):
	w, h = r.width() * 2 // 3, r.height() * 2 // 3
	return QRect(r.left() + (r.width() - w) // 2, r.top() + (r.height() - h) // 2, w, h)

ONE = (
	("&Fill the Screen", lambda r: r, None),
	("Left &Half", lambda r: halves(r)[0], None),
	("&Right Half", lambda r: halves(r)[1], None),
	("Top H&alf", lambda r: halves(r, False)[0], None),
	("&Bottom Half", lambda r: halves(r, False)[1], None),
	("Ce&nter", center, None),
)

def screenof(w):
	s = w.screen() if w is not None else None
	s = s or QApplication.primaryScreen()
	return s.availableGeometry()

def layout(fn, active=None):
	"""lay out the windows shown with fn of ALL"""
	ws = windows(active)
	if not ws:
		return
	scr = screenof(ws[0])
	rects = fn(scr, len(ws))
	if fn is cascade:
		rects = rects[::-1]
	for w, r in zip(ws, rects):
		place(w, r, scr)
	if fn is cascade:
		for w in reversed(ws):
			w.raise_()
	else:
		ws[0].raise_()
	ws[0].activateWindow()

def layoutone(fn, active=None):
	"""put the active window where fn of ONE says"""
	ws = windows(active)
	if ws:
		scr = screenof(ws[0])
		place(ws[0], fn(scr), scr)
		ws[0].raise_()

def windowmenu(win):
	"""the Window menu for window win: the layouts, minimize, and the
	windows shown, to bring one to the front"""
	m = QMenu("&Window", win)
	def act(text, fn, shortcut=None, tip=None):
		a = QAction(text, win)
		if shortcut:
			a.setShortcut(QKeySequence(shortcut))
		if tip:
			a.setToolTip(tip)
			a.setStatusTip(tip)
		a.triggered.connect(lambda _=False: fn())
		m.addAction(a)
		return a
	act("&Minimize", win.showMinimized, "Ctrl+M")
	m.addSeparator()
	for text, fn, key, tip in ALL:
		act(text, lambda fn=fn: layout(fn, win), key, tip)
	m.addSeparator()
	for text, fn, key in ONE:
		act(text, lambda fn=fn: layoutone(fn, win), key, "this window alone")
	m.addSeparator()
	first = len(m.actions())
	def fill():
		for a in m.actions()[first:]:
			m.removeAction(a)
		for w in windows(win):
			a = m.addAction(w.windowTitle() or "untitled")
			a.setCheckable(True)
			a.setChecked(w is win)
			a.triggered.connect(lambda _=False, w=w: (w.raise_(), w.activateWindow()))
	m.aboutToShow.connect(fill)
	return m
