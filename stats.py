
from enum import Enum, IntEnum, IntFlag, auto
from data import *

class StatKind(IntFlag):
	Tot = auto()
	Avg = auto()
	Cnt = auto()

class StatUnit(IntFlag):
	Euros = auto()
	Pts = auto()
	SysPts = auto()
	SysEuros = auto()
	PtsNorm = auto()
	StopPts = auto()
	Success = auto()
	Failure = auto()

class StatPlot(IntEnum):
	Plot = auto()
	PerResult = auto()
	DayResult = auto()
	WeekResult = auto()
	MonthResult = auto()
	WeekPlot = auto()
	MonthPlot = auto()
	PerDay = auto()
	PerWeek = auto()
	PerMonth = auto()
	PerSetup = auto()
	PerInstrument = auto()
	PerWeekDay = auto()
	PerHour = auto()


@dataclass
class Filter:
	# features
	musthave: Set[str] = field(default_factory= set)
	canthave: Set[str] = field(default_factory= set)
	# if these are empty, then anyone is ok
	# for negative filters, caller would just build the resulting
	# set of matching entries
	instruments: Set[str] = field(default_factory= set)
	setups: Set[str] = field(default_factory= set)
	dirs: Set[Dir] = field(default_factory= set)
	results: Set[Result] = field(default_factory= set)
	hours: Set[int] = field(default_factory= set)
	wdays: Set[WDay] = field(default_factory= set)

	# if since >= until, no filter by date
	since: date = None
	until: date = None

	def apply(self, trades: list[Trade]) -> list[Trade]:
		for mh in self.musthave:
			trades = [t for t in trades if t.hasfeature(mh)]
		for mh in self.canthave:
			trades = [t for t in trades if not t.hasfeature(mh)]
		if len(self.setups) > 0:
			trades = [t for t in trades if t.setup in self.setups]
		if len(self.instruments) > 0:
			trades = [t for t in trades if t.instrument in self.instruments]
		if len(self.dirs) > 0:
			trades = [t for t in trades if t.dir in self.dirs]
		if len(self.results) > 0:
			trades = [t for t in trades if t.result() in self.results]
		if len(self.hours) > 0:
			trades = [t for t in trades if t.hour() in self.hours]
		if len(self.wdays) > 0:
			trades = [t for t in trades if t.dayofweek() in self.wdays]
		if self.since is not None and self.until is not None and self.since < self.until:
			trades = [t for t in trades if self.since <= t.datein <= self.until]
		return trades

	@staticmethod
	def thisday(trades: list[Trade]) -> list[Trade]:
		if len(trades) == 0:
			return trades
		d = trades[-1].datein
		return [t for t in trades if t.datein == d]

	@staticmethod
	def thisweek(trades: list[Trade]) -> list[Trade]:
		if len(trades) == 0:
			return trades
		y = trades[-1].year()
		w = trades[-1].week()
		return [t for t in trades if t.year() == y and t.week() == w]

	@staticmethod
	def thismonth(trades: list[Trade]) -> list[Trade]:
		if len(trades) == 0:
			return trades
		y = trades[-1].year()
		m = trades[-1].month()
		return [t for t in trades if t.year() == y and t.month() == m]

	@staticmethod
	def thisyear(trades: list[Trade]) -> list[Trade]:
		if len(trades) == 0:
			return trades
		y = trades[-1].year()
		return [t for t in trades if t.year() == y]

def tradevalue(t: Trade, u: StatUnit, tots=False) -> float:
	if t is None:
		return 0.0
	match u:
		case StatUnit.Euros:
			return t.ptseuros()
		case StatUnit.Pts:
			return t.points()
		case StatUnit.SysPts:
			return t.syspoints()
		case StatUnit.SysEuros:
			return t.syseuros()
		case StatUnit.PtsNorm:
			return t.ptsnorm()
		case StatUnit.Success:
			if t.isOK():
				return 1
			if tots and t.isKO():
				return -1
			return 0
		case StatUnit.Failure:
			if t.isKO():
				return 1
			if tots and t.isOK():
				return -1
			return 0
		case StatUnit.StopPts:
			return t.stoppoints()
		case _:
			return t.ptseuros()

class StatTotals:
	def __init__(self, acc, trades, u = StatUnit.Euros):
		self.account = acc.account
		self.ntrades = 0
		self.total = 0.0
		self.average = 0.0
		self.nok = 0
		self.nko = 0
		self.nneutral = 0
		self.averageok = 0.0
		self.averageko = 0.0
		self.averageneutral = 0.0
		self.totalok = 0.0
		self.totalko = 0.0
		self.totalneutral = 0.0
		self.pcent = 0.0
		self.okpcent = 0.0
		self.kopcent = 0.0
		self.neutralpcent = 0.0
		for t in trades:
			v = tradevalue(t, u)
			self.total += v
			self.ntrades += 1
			if t.isOK():
				self.nok += 1
				self.totalok += v
			elif t.isKO():
				self.nko += 1
				self.totalko += v
			else:
				self.nneutral += 1
				self.totalneutral += v
		self.average = self.total / self.ntrades if self.ntrades>0 else 0
		self.averageok = self.totalok / self.nok if self.nok >0 else 0
		self.averageko = self.totalko / self.nko if self.nko>0 else 0
		self.averageneutral = self.totalneutral / self.nneutral if self.nneutral>0 else 0
		self.okpcent = 100 * self.nok / self.ntrades if self.ntrades > 0 else 0
		self.kopcent = 100 * self.nko / self.ntrades if self.ntrades > 0 else 0
		self.neutralpcent = 100 * self.nneutral / self.ntrades if self.ntrades > 0 else 0
		if acc and acc.account > 0:
			self.pcent = self.total / acc.account * 100

def tradevalues(ts: list[Trade], u: StatUnit) -> list[float]:
	return [tradevalue(t, u) for t in ts]


def tradevaluetots(ts: list[Trade], u: StatUnit, initial=0) -> list[float]:
	tots = []
	for t in ts:
		initial += tradevalue(t, u, tots=True)
		tots.append(initial)
	return tots

def forkind(iset, vdict, vcnt, k):
	iset = [str(i) for i in iset]
	if k == StatKind.Cnt:
		return iset, [vcnt[i] for i in iset]

	vals = [vdict[i] for i in iset]
	if k == StatKind.Avg:
		for i, v in enumerate(vals):
			n = vcnt[iset[i]]
			if n != 0:
				vals[i] = v / n
	return iset, vals

def perfunc(ts: list[Trade],
		u: StatUnit, k: StatKind, fn, nb=None) -> tuple[list[str],list[float]]:
	vals = []
	labels = []
	cnts = []
	val = 0
	cnt = 0
	lastlabel = None
	for t in ts:
		label = fn(t)
		if lastlabel != label:
			if lastlabel:
				vals.append(val)
				labels.append(lastlabel)
				cnts.append(cnt)
			val = 0
			cnt = 0
		val = val + tradevalue(t, u)
		cnt = cnt + 1
		lastlabel = label
	if lastlabel:
		vals.append(val)
		labels.append(lastlabel)
		cnts.append(cnt)
	if k == StatKind.Cnt:
		if nb and len(cnts) > nb:
			labels = labels[-nb:]
			cnts = cnts[-nb:]
		return labels, cnts
	if k == StatKind.Avg:
		for i, v in enumerate(vals):
			if cnts[i] != 0:
				vals[i] = vals[i] / cnts[i]
	if nb and len(vals) > nb:
		labels = labels[-nb:]
		vals = vals[-nb:]
	return labels, vals

def perday(ts: list[Trade], u: StatUnit, k: StatKind, nb=None) -> tuple[list[str],list[float]]:
	fn = lambda t: t.datein.isoformat() if t.datein else "none"
	return perfunc(ts, u, k, fn, nb)

def perweek(ts: list[Trade], u: StatUnit, k: StatKind, nb=None) -> tuple[list[str],list[float]]:
	fn = lambda t: f"{t.year()}-{t.week()}" if t.datein else "none"
	return perfunc(ts, u, k, fn, nb)

def permonth(ts: list[Trade], u: StatUnit, k: StatKind, nb=None) -> tuple[list[str],list[float]]:
	fn = lambda t: f"{t.year()}-{t.month()}" if t.datein else "none"
	return perfunc(ts, u, k, fn, nb)



def perfield(ts: list[Trade], u: StatUnit, k: StatKind, fn) -> tuple[list[str],list[float]]:
	iset = sorted(set([fn(t) or "none" for t in ts]))
	vdict = {i:0 for i in iset}
	vcnt = {i:0 for i in iset}
	for t in ts:
		nm = fn(t) or "none"
		v = tradevalue(t, u)
		vdict[nm] += v
		vcnt[nm] += 1
	return forkind(iset, vdict, vcnt, k)

def perresult(ts: list[Trade], u: StatUnit, k: StatKind, nb = 0) -> tuple[list[str],list[float]]:
	return perfield(ts, u, k, lambda t: t.result().name)

def perhour(ts: list[Trade], u: StatUnit, k: StatKind, nb = 0) -> tuple[list[str],list[float]]:
	return perfield(ts, u, k, lambda t: f"{t.hour():02d}")


def perdayofweek(ts: list[Trade], u: StatUnit, k: StatKind, nb = 0) -> tuple[list[str],list[float]]:
	return perfield(ts, u, k, lambda t: t.dayofweek().name)


def persetup(ts: list[Trade], u: StatUnit, k: StatKind, nb = 0) -> tuple[list[str],list[float]]:
	return perfield(ts, u, k, lambda t: t.setup)

def perinstrument(ts: list[Trade], u: StatUnit, k: StatKind, nb = 0) -> tuple[list[str],list[float]]:
	return perfield(ts, u, k, lambda t: t.instrument)
