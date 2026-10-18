#
# calendar of trading days, coloured by the day result
#
import calendar
from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPalette, QPen, QTextCharFormat
from PySide6.QtWidgets import (
	QCalendarWidget, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
	QTabWidget, QVBoxLayout, QWidget
)

from stats import StatUnit, tradevalue

DAYCOLORS = {1: QColor("#8fd98f"), -1: QColor("#f09090"), 0: QColor("#c8c8c8")}
TEXTCOLORS = {1: QColor("darkgreen"), -1: QColor("darkred"), 0: QColor("black")}

def daysign(v, neutral):
	if v > neutral:
		return 1
	if v < -neutral:
		return -1
	return 0

def tradeorder(t):
	return (t.datein or date.min, t.timein.isoformat() if t.timein else "", t.trade)

class DayCalendar(QCalendarWidget):
	"""a calendar painting days with the colours in colors (date -> QColor).
	A month calendar (onemonth) shows only the days of its month and no selection."""
	def __init__(self, onemonth=False, parent=None):
		super().__init__(parent)
		self.colors = {}
		self.tips = {}
		self.onemonth = onemonth
		self.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
		if onemonth:
			self.setNavigationBarVisible(False)
			self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
			self.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.SingleLetterDayNames)
			self.setMinimumSize(200, 150)
		else:
			self.setGridVisible(True)
			self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.ISOWeekNumbers)

	def setmonth(self, y, m):
		"""for a month calendar: show month m of year y and only its days"""
		self.setDateRange(QDate(1, 1, 1), QDate(9999, 12, 31))
		self.setCurrentPage(y, m)
		self.setDateRange(QDate(y, m, 1), QDate(y, m, calendar.monthrange(y, m)[1]))

	def setcolors(self, colors, tips):
		self.colors = colors
		old = self.tips
		self.tips = tips
		for d in old:
			if d not in tips:
				self.setDateTextFormat(QDate(d.year, d.month, d.day), QTextCharFormat())
		for d, tip in tips.items():
			fmt = QTextCharFormat()
			fmt.setToolTip(tip)
			self.setDateTextFormat(QDate(d.year, d.month, d.day), fmt)
		self.updateCells()

	def paintCell(self, painter, rect, qd):
		d = qd.toPython()
		inmonth = qd.month() == self.monthShown() and qd.year() == self.yearShown()
		pal = self.palette()
		painter.save()
		painter.fillRect(rect, pal.color(QPalette.ColorRole.Base))
		if inmonth or not self.onemonth:
			color = self.colors.get(d)
			if color is not None:
				painter.fillRect(rect.adjusted(1, 1, -1, -1), color)
			if color is not None:
				fg = QColor("black")
			elif not inmonth:
				fg = pal.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text)
			else:
				# weekends keep their own colour
				wfg = self.weekdayTextFormat(Qt.DayOfWeek(qd.dayOfWeek())).foreground()
				fg = wfg.color() if wfg.style() != Qt.BrushStyle.NoBrush else pal.color(QPalette.ColorRole.Text)
			font = painter.font()
			if d == date.today():
				font.setBold(True)
				painter.setFont(font)
			painter.setPen(fg)
			painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(qd.day()))
			if not self.onemonth and qd == self.selectedDate():
				painter.setPen(QPen(pal.color(QPalette.ColorRole.Highlight), 3))
				painter.drawRect(rect.adjusted(2, 2, -2, -2))
		painter.restore()

class YearView(QWidget):
	"""the twelve months of a year, to scroll through"""
	dayClicked = Signal(object)
	dayActivated = Signal(object)
	monthClicked = Signal(int, int)
	yearChanged = Signal(int)

	def __init__(self, parent=None):
		super().__init__(parent)
		self.year = date.today().year
		self.cols = 0
		prevb = QPushButton("◀")
		nextb = QPushButton("▶")
		prevb.clicked.connect(lambda: self.setyear(self.year - 1, True))
		nextb.clicked.connect(lambda: self.setyear(self.year + 1, True))
		self.yearlabel = QLabel()
		f = QFont()
		f.setBold(True)
		self.yearlabel.setFont(f)
		self.yearlabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
		top = QHBoxLayout()
		top.addWidget(prevb)
		top.addWidget(self.yearlabel, 1)
		top.addWidget(nextb)

		self.boxes = []
		self.titles = []
		self.cals = []
		for m in range(1, 13):
			box = QWidget()
			v = QVBoxLayout(box)
			v.setContentsMargins(4, 4, 4, 4)
			title = QPushButton(calendar.month_name[m])
			title.setFlat(True)
			title.setFont(f)
			title.setToolTip("show this month in the trades table")
			title.clicked.connect(lambda _=False, m=m: self.monthClicked.emit(self.year, m))
			cal = DayCalendar(onemonth=True)
			cal.clicked.connect(lambda qd: self.dayClicked.emit(qd.toPython()))
			cal.activated.connect(lambda qd: self.dayActivated.emit(qd.toPython()))
			v.addWidget(title)
			v.addWidget(cal)
			self.boxes.append(box)
			self.titles.append(title)
			self.cals.append(cal)
		self.grid = QGridLayout()
		inner = QWidget()
		inner.setLayout(self.grid)
		self.scroll = QScrollArea()
		self.scroll.setWidgetResizable(True)
		self.scroll.setWidget(inner)
		layout = QVBoxLayout(self)
		layout.setContentsMargins(0, 0, 0, 0)
		layout.addLayout(top)
		layout.addWidget(self.scroll, 1)
		self.relayout()
		self.setyear(self.year)

	def relayout(self):
		"""as many months per row as fit"""
		cols = max(1, min(4, self.scroll.viewport().width() // 230))
		if cols == self.cols:
			return
		self.cols = cols
		for b in self.boxes:
			self.grid.removeWidget(b)
		for i, b in enumerate(self.boxes):
			self.grid.addWidget(b, i // cols, i % cols)

	def resizeEvent(self, ev):
		super().resizeEvent(ev)
		self.relayout()

	def setyear(self, y, byuser=False):
		self.year = y
		self.yearlabel.setText(str(y))
		for m, cal in enumerate(self.cals, 1):
			cal.setmonth(y, m)
		if byuser:
			self.yearChanged.emit(y)

	def setcolors(self, colors, tips, monthinfo):
		"""monthinfo(y, m) returns (text, sign) for a month title"""
		for m, (cal, title) in enumerate(zip(self.cals, self.titles), 1):
			cal.setcolors(colors, tips)
			txt, sign = monthinfo(self.year, m)
			title.setText(f"{calendar.month_name[m]}  {txt}" if txt else calendar.month_name[m])
			title.setStyleSheet(f"color: {TEXTCOLORS[sign].name()}" if txt else "")

	def showmonth(self, m):
		self.scroll.ensureWidgetVisible(self.boxes[m-1], 0, 0)

class TradeCalendar(QWidget):
	"""days with trades are green, red or grey for positive, negative or
	neutral totals; clicking one emits the first trade of that day.
	monthChanged is emitted when the user moves to another month."""
	tradeSelected = Signal(object)
	tradeActivated = Signal(object)	# double click
	monthChanged = Signal(int, int)

	def __init__(self, parent=None):
		super().__init__(parent)
		self.days = {}		# date -> trades of that day, in order
		self.neutral = 0
		self.colors = {}	# date -> colour of the day
		self.tips = {}
		self.quiet = False	# moving because a trade was selected elsewhere
		self.cal = DayCalendar()
		self.cal.clicked.connect(self.clicked)
		self.cal.activated.connect(self.activated)
		self.cal.currentPageChanged.connect(self.pagechanged)
		self.monthlabel = QLabel()
		self.daylabel = QLabel()
		month = QWidget()
		ml = QVBoxLayout(month)
		ml.addWidget(self.cal, 1)
		self.year = YearView()
		self.year.dayClicked.connect(self.yearclicked)
		self.year.dayActivated.connect(lambda d: self.activated(QDate(d.year, d.month, d.day)))
		self.year.monthClicked.connect(self.yearmonth)
		self.year.yearChanged.connect(lambda y: self.paintyear())
		self.tabs = QTabWidget()
		self.tabs.addTab(month, "Month")
		self.tabs.addTab(self.year, "Year")
		layout = QVBoxLayout(self)
		layout.addWidget(self.tabs, 1)
		layout.addWidget(self.monthlabel)
		layout.addWidget(self.daylabel)

	def settrades(self, trades, neutral):
		self.neutral = neutral
		self.days = {}
		for t in sorted(trades, key=tradeorder):
			if t.datein is not None:
				self.days.setdefault(t.datein, []).append(t)
		self.colors = {}
		self.tips = {}
		for d, ts in self.days.items():
			self.colors[d] = DAYCOLORS[self.total(ts)[1]]
			self.tips[d] = self.summary(ts)
		self.cal.setcolors(self.colors, self.tips)
		self.paintyear()
		self.showinfo()

	def paintyear(self):
		self.year.setcolors(self.colors, self.tips, self.monthinfo)

	def total(self, ts):
		v = sum(tradevalue(t, StatUnit.Euros) for t in ts)
		return v, daysign(v, self.neutral)

	def summary(self, ts):
		v, _ = self.total(ts)
		n = len(ts)
		return f"{n} trade{'s' if n != 1 else ''}, {v:+.0f}€"

	def monthtrades(self, y, m):
		return [t for day, l in self.days.items() if day.year == y and day.month == m for t in l]

	def monthinfo(self, y, m):
		ts = self.monthtrades(y, m)
		if not ts:
			return "", 0
		v, sign = self.total(ts)
		return f"{v:+.0f}€", sign

	def showinfo(self, d=None):
		y, m = self.cal.yearShown(), self.cal.monthShown()
		ts = self.monthtrades(y, m)
		ndays = len({t.datein for t in ts})
		self.monthlabel.setText(f"{calendar.month_name[m]} {y}: {self.summary(ts)} in {ndays} day{'s' if ndays != 1 else ''}"
			if ts else f"{calendar.month_name[m]} {y}: no trades")
		if d is not None:
			ts = self.days.get(d, [])
			self.daylabel.setText(f"{d.isoformat()}: {self.summary(ts)}" if ts else f"{d.isoformat()}: no trades")

	def pagechanged(self, y, m):
		if y != self.year.year:
			self.year.setyear(y)
			self.paintyear()
		self.year.showmonth(m)
		self.showinfo()
		if not self.quiet:
			self.monthChanged.emit(y, m)

	def showdate(self, d):
		"""show the day of a trade selected elsewhere"""
		if d is None:
			return
		self.quiet = True
		try:
			self.cal.setSelectedDate(QDate(d.year, d.month, d.day))
		finally:
			self.quiet = False
		self.showinfo(d)

	def clicked(self, qd):
		d = qd.toPython()
		self.showinfo(d)
		if d in self.days:
			self.tradeSelected.emit(self.days[d][0])

	def activated(self, qd):
		d = qd.toPython()
		if d in self.days:
			self.tradeActivated.emit(self.days[d][0])

	def yearclicked(self, d):
		"""a day in the year view: the same as clicking it in the month view"""
		self.cal.setSelectedDate(QDate(d.year, d.month, d.day))
		self.clicked(QDate(d.year, d.month, d.day))

	def yearmonth(self, y, m):
		"""a month title in the year view: move the month view and the trades there"""
		if (y, m) == (self.cal.yearShown(), self.cal.monthShown()):
			self.monthChanged.emit(y, m)
		else:
			self.cal.setCurrentPage(y, m)
