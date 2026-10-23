#
# data classes
#
from dataclasses import dataclass, field
from datetime import date, time, datetime
from typing import Optional, Set, List
from enum import Enum, IntEnum
import os
import re
import sys
import shutil
from csv_mapper import load_objects_from_csv,write_objects_to_csv

from newdata import NEWACCOUNT, NEWCURRENCIES, NEWFEATURES, NEWINSTRUMENTS, NEWSETUPS, NEWTRADES

ACCOUNTFILE = "account.csv"
SETUPSFILE = "setups.csv"
TRADESFILE = "trades.csv"
CURRENCIESFILE = "divisas.csv"
FEATURESFILE = "features.csv"
INSTRUMENTSFILE = "activos.csv"
GRAPHSDIR = "diarygraphs"
VERSION = 2.0
BCK = "~"

def graphindex(path: str) -> int:
	"""n for a graph named like trade12dax.n.png, 0 for any other name"""
	m = re.search(r"\.(\d+)\.png$", path, re.IGNORECASE)
	return int(m.group(1)) if m else 0

def canonlist(l):
	"""graphs in their right order: the primary one first.
	Roadbooks saved by older versions have the list sorted by name,
	which puts trade12dax.1.png before trade12dax.png; fix that order.
	Lists not sorted by name were saved in the right order already."""
	if len(l) <= 1 or l != sorted(l):
		return l
	return sorted(l, key=graphindex)

class Dir(Enum):
	Long = "Long"
	Short = "Short"

class Result(IntEnum):
	OK = 1
	KO = -1
	Neutral = 0

class WDay(IntEnum):
	Mon = 0
	Tue = 1
	Wed = 2
	Thu = 3
	Fry = 4
	Sat = 5
	Sun = 6

@dataclass
class Account:
	account: float = 10000
	neutral: float = 10
	fixed: bool = True
	copygraphs: bool = True
	version: float = VERSION

def accountexample():
	return Account()

@dataclass
class Setup:
	setup: str = ""
	descr: str = ""

def setupexample():
	return Setup("ApoyoH4 Aper", "apoyo pero antes de GL y con cota cerca")

@dataclass
class Feature:
	feature: str = ""
	descr: str = ""
	setups: Optional[Set[str]] = field(default_factory= set)
	aka: Optional[List[str]] = field(default_factory= list)	# other names for it

def featureexample():
	return Feature("ApoyoH4 Aper", "apoyo pero antes de GL y con cota cerca",
                   {"ApoyoH4 Aper", "ApoyoH4 Aper", "ApoyoH4 Aper"}, ["Apoyo H4", "H4 Aper"])

@dataclass
class Currency:
	name: str = "EUR"
	forex: Optional[str] = ""
	euros2: Optional[float] = 1.0

def currencyexample():
	return Currency("EUROS", "EURUSD", 43234.3)

@dataclass
class Instrument:
	instrument: str = ""
	aka: Optional[str] = ""
	currency: Optional[str] = ""
	pipmoney: Optional[float] = 1.0
	pip: Optional[float] = 1.0
	stoppips: Optional[float] = 0
	scale: Optional[float] = 0
	diary: Optional[float] = 0
	candleh4: Optional[float] = 0
	candle144: Optional[float] = 0
	spread: Optional[float] = 0
	sreadpm: Optional[float] = 0

def instrumentexample():
	return Instrument("NASDAQ", "SP 500", "EURUSD", 1.0, 0.0001, 144.3, 240000,
		243.4, 354.4, 354.4,  432, 432)

TRADEVIEWORDER = ["trade", "instrument", "setup", "dir", "out", "datein", "timein",
	"timeout", "lots", "euros", "notes", "has"]	#
TRADEVIEWRDONLY = ["trade"]

# old version of data
@dataclass
class Trade1:
	trade: int = 0
	instrument: str = ""
	setup: Optional[str] = None
	datein: date = field(default_factory= date.today)
	dir: Dir = Dir.Long
	lots: float = 1
	timein: time = None
	timeout: Optional[time] = None
	ptsin: Optional[float] = 0
	ptsout: Optional[float] = 0
	sysout: Optional[float] = 0
	ptsstop: Optional[float] = 0
	euros: Optional[float] = 0.0
	eurstop: Optional[float] = 0.0
	graf: Optional[str] = ""
	notes: Optional[str] = ""
	mistakes: Optional[str] = ""
	has: Optional[Set[str]] = field(default_factory= set)
	pts: Optional[float] = 0.0

	def points(self):
		if self.dir == Dir.Long:
			return self.ptsout - self.ptsin
		return self.ptsin - self.ptsout

@dataclass
class Trade:
	trade: int = 0
	instrument: str = ""
	setup: Optional[str] = None
	datein: date = field(default_factory= date.today)
	dir: Dir = Dir.Long
	lots: float = 1
	timein: time = None
	timeout: Optional[time] = None
	tp: float =  0.0
	stop: float  = 0.0
	out: float  = 0.0
	euros: Optional[float] = 0.0
	graf: Optional[List[str]] = field(default_factory=list)
	notes: Optional[str] = ""
	has: Optional[Set[str]] = field(default_factory= set)

	@staticmethod
	def old2new(t1):
		if t1.pts is None or t1.pts == 0.0:
			t1.pts = t1.points()
		t = Trade()
		t.trade = t1.trade
		t.instrument = t1.instrument
		t.setup = t1.setup
		t.datein = t1.datein
		t.dir = t1.dir
		t.lots = t1.lots
		t.timein = t1.timein
		t.timeout = t1.timeout
		t.euros = t1.euros
		if t1.graf is None or t1.graf == "":
			t.graf = []
		else:
			t.graf = [t1.graf]
		t.notes = t1.notes
		if t1.mistakes is not None and len(t1.mistakes) > 0:
			t.notes = f"{t.notes}. errs: {t1.mistakes}"
		t.has = t1.has
		if t.dir == Dir.Long:
			if t1.ptsout < t1.ptsin:
				t.tp = 0.0
			else:
				t.tp = t1.ptsout - t1.ptsin
			if t1.ptsstop > t1.ptsin:
				t.stop = 0
			else:
				t.stop = t1.ptsin - t1.ptsstop
		else:
			if t1.ptsout > t1.ptsin:
				t.tp = 0.0
			else:
				t.tp = abs(t1.ptsout - t1.ptsin)
			if t1.ptsstop < t1.ptsin:
				t.stop = 0
			else:
				t.stop = abs(t1.ptsin - t1.ptsstop)
		t.out = t1.points()
		return t

	def copy_from(self, o):
		"""swallow copy"""
		self.trade = o.trade
		self.instrument = o.instrument
		self.setup = o.setup
		self.datein = o.datein
		self.dir = o.dir
		self.lots = o.lots
		self.timein = o.timein
		self.timeout = o.timeout
		self.tp = o.tp
		self.stop = o.stop
		self.out = o.out
		self.euros = o.euros
		self.graf = o.graf
		self.notes = o.notes
		self.has = o.has

	def __post_init__(self):
		self.rb = None
	def inval(self)-> None:
		pass

	def setdefaults(self):
		if self.lots == 0 or self.lots is None:
			self.lots = 1
		if self.euros == 0 or self.euros is None:
			self.euros = self.lots * self.out
		if self.instrument == "":
			self.instrument = "DAX"
		if self.graf is None:
			self.graf = []
		if self.has is None:
			self.has = set()
		if len(self.graf) > 1:
			self.graf = canonlist(self.graf)
	def hour(self) -> int:
		return self.timein.hour if self.timein else 0

	def year(self) -> int:
		return self.datein.year
	def month(self) -> int:
		return self.datein.month
	def day(self) -> int:
		return self.datein.day
	def week(self) -> int:
		dt = datetime(self.datein.year, self.datein.month, self.datein.day)
		ic = dt.isocalendar()
		return ic[1]
	def dayofweek(self) -> WDay:
		dt = datetime(self.datein.year, self.datein.month, self.datein.day)
		ic = dt.isocalendar()
		return WDay(ic.weekday-1)
	def points(self) -> float:
		return self.out
	def stoppoints(self) -> float:
		return self.stop

	def result(self, neutral: float = 0) -> Result:
		if neutral == 0 and self.rb and self.rb.account:
			neutral = self.rb.account.neutral
		pt = self.euros if self.euros != 0 else self.points()
		if pt > neutral:
			return Result.OK
		if pt < -neutral:
			return Result.KO
		return Result.Neutral

	def isOK(self) -> bool:
		return self.result() == Result.OK
	def isKO(self) -> bool:
		return self.result() == Result.KO

	def instr(self) -> Instrument|None:
		if self.instrument is None or self.instrument == "":
			return None
		if self.rb is None:
			raise RuntimeError("roadbook not set in trade")
		return self.rb.findInstrument(self.instrument)

	def ptsnorm(self, pts = None) -> float:
		"""points normalized by scale"""
		if pts is None:
			pts = self.points()
		i = self.instr()
		if i is None:
			return pts
		if i.scale == 0:
			return pts
		return pts * 260000 / i.scale

	def currency(self) -> Currency|None:
		i = self.instr()
		if i is None:
			return None
		return self.rb.findCurrency(i.currency)

	def ptseuros(self, pts = None) -> float:
		if self.euros != 0:
			return self.euros
		if pts is None:
			pts = self.points()
		toeur = 1.0
		mult = 1.0
		i = self.instr()
		if i is not None and i.pipmoney is not None:
			mult = i.pipmoney
		c = self.currency()
		if c is not None and c.name not in ("EUR", "EURO") and c.euros2:
			toeur = 1/c.euros2
		return pts * self.lots * toeur * mult

	def hasfeature(self, name) -> bool:
		return self.has is not None and name in self.has

	def checkOut(self) -> str|None:
		t = self
		if t.instrument is None or t.instrument == "":
			return "no instrument"
		if t.setup is None or t.setup == "":
			return "no setup"
		if t.lots <= 0.0:
			return "bad size in lots"
		if t.tp <= 0.0 or t.tp > 1000:
			return "bad TP"
		if t.stop <= 0.0 or t.stop > 1000:
			return "bad stop"
		if t.out > 1000:
			return "bad out"
		return None

def tradeexample():
	t = time(15,30)
	to = time(15,30)
	return Trade(100, "NASDAQ", "ApoyoH4 Aper", date.today(), Dir.Short, 1.0,
		t, to, 100, 20, -20, -30,
		"/path/to/plot", "apoyo 4H, sin muros, fuerza, sem flojo. 1H sin fuerza: no reentrar",
		{"Apertura","Apoyo D","Apoyo4H","Desp.Corr","Pullback", "Sin Muros;Willy OK"})

@dataclass
class Table:
	"""one CSV file of a roadbook, loaded into the RoadBook attribute attr"""
	attr: str
	file: str
	cls: type
	key: object	# sort key used on load
	renames: Optional[dict] = None	# CSV header names that differ from field names

# in load order: instruments refer to currencies and trades to everything else
TABLES = [
	Table("currencies", CURRENCIESFILE, Currency, lambda c: c.name),
	Table("instruments", INSTRUMENTSFILE, Instrument, lambda i: i.instrument.lower()),
	Table("setups", SETUPSFILE, Setup, lambda s: s.setup.lower()),
	Table("features", FEATURESFILE, Feature, lambda f: f.feature.lower()),
	Table("trades", TRADESFILE, Trade, lambda t: t.datein, {"datein": "date", "has": "with"}),
]

def copyfile(src: str, dst: str) -> None:
	try:
		shutil.copyfile(src, dst)
	except Exception:
		pass

class RoadBook:
	def __init__(self, trades = None, instrs = None,
			setups = None, features = None, currencies = None):
		if trades is None:
			trades = []
		if instrs is None:
			instrs = []
		if setups is None:
			setups = []
		if features is None:
			features = []
		if currencies is None:
			currencies = []
		self.trades = trades
		self.filteredtrades = None
		self.instruments = instrs
		self.setups = setups
		self.features = features
		self.currencies = currencies
		self.account = Account()
		self.dir = None
		self.maxid = 0
		self.dirty = False
		self._defaults()

	def nextId(self):
		return self.maxid+1


	def findInstrument(self, name):
		for i in self.instruments:
			if i.instrument == name:
				return i
		return None
	def findSetup(self, name):
		for s in self.setups:
			if s.setup == name:
				return s
		return None
	def findFeature(self, name):
		for f in self.features:
			if f.feature == name:
				return f
		return None
	def listedtrades(self):
		"""the trades shown: the filtered ones when there is a filter"""
		return self.filteredtrades if self.filteredtrades is not None else self.trades

	@staticmethod
	def clearfeatures(trades) -> int:
		"""remove the features of trades; returns how many trades had some"""
		n = 0
		for t in trades:
			if t.has:
				n += 1
			t.has = set()
		return n

	@staticmethod
	def namepattern(name, wild=False) -> str:
		"""regex for a feature name in the notes: a final lowercase "s" is
		optional, so EQL matches EQLs and EQLs matches EQL. With wild, a "*"
		matches any run of word characters (EQ* matches EQL and EQH)."""
		if name.endswith("s") and len(name) > 1:
			name = name[:-1]
		if wild:
			p = r"\w*".join(re.escape(x) for x in name.split("*"))
		else:
			p = re.escape(name)
		if not (wild and name.endswith("*")):
			p += "(?-i:s)?"
		return p

	def autofeatures(self, trades) -> tuple[int, int]:
		"""add to each trade the features whose name or aka names appear
		as words in its notes, ignoring case (see namepattern). Features for other setups
		are not added. Returns how many features were added, to how many trades."""
		pats = []
		for f in self.features:
			names = [f.feature] + list(f.aka or [])
			alts = "|".join(self.namepattern(n.strip(), wild=i > 0)
				for i, n in enumerate(names) if n and n.strip())
			if alts:
				# whole words, also for names that start or end with a non word char
				pats.append((f, re.compile(rf"(?<!\w)(?:{alts})(?!\w)", re.IGNORECASE)))
		nfeat = ntrades = 0
		for t in trades:
			if not t.notes:
				continue
			added = 0
			for f, pat in pats:
				if t.has and f.feature in t.has:
					continue
				if f.setups and t.setup not in f.setups:
					continue
				if pat.search(t.notes):
					if t.has is None:
						t.has = set()
					t.has.add(f.feature)
					added += 1
			if added:
				nfeat += added
				ntrades += 1
		return nfeat, ntrades

	def findCurrency(self, name):
		for c in self.currencies:
			if c.name == name:
				return c
		return None

	def instrumentNames(self):
		return [i.instrument for i in self.instruments]

	def setupNames(self):
		return [s.setup for s in self.setups]

	def featureNames(self, setup=None):
		if setup is None:
			return [f.feature for f in self.features]
		rr = []
		for f in self.features:
			if f.setups is None or len(f.setups) == 0 or setup in f.setups:
				rr.append(f.feature)
		return rr
	def currencyNames(self):
		return [c.name for c in self.currencies]

	def setupUsed(self, name):
		for t in self.trades:
			if t.setup == name:
				return True
		for f in self.features:
			if f.setups and name in f.setups:
				return True
		return False
	def instrumentUsed(self, name):
		for t in self.trades:
			if t.instrument == name:
				return True
		return False
	def featureUsed(self, name):
		for t in self.trades:
			if t.has is not None and name in t.has:
				return True
		return False

	def _defaults(self) -> None:
		"""add default instr/setup/feature/currency for missing ones"""
		self.defaultsforfeatures()
		self.defaultsforinstruments()
		self.defaultsfortrades()


	def reninstrument(self, oname: str, nname: str) -> None:
		"""rename and update all data"""
		for t in self.trades:
			if t.instrument == oname:
				t.instrument = nname
		i = self.findInstrument(oname)
		if i is not None:
			i.instrument = nname
	def rencurrency(self, oname: str, nname: str) -> None:
		"""rename and update all data"""
		for i in self.instruments:
			if i.currency == oname:
				i.currency = nname
		c = self.findCurrency(oname)
		if c is not None:
			c.name = nname

	def rensetup(self, oname: str, nname: str) -> None:
		"""rename and update all data"""
		for t in self.trades:
			if t.setup == oname:
				t.setup = nname
		for f in self.features:
			if f.setups is None:
				f.setups = set([])
			if oname in f.setups:
				f.setups.remove(oname)
				f.setups.add(nname)
		s = self.findSetup(oname)
		if s is not None:
			s.setup = nname

	def renfeature(self, oname: str, nname: str) -> None:
		"""rename and update all data"""
		for t in self.trades:
			if t.has is None:
				t.has = set({})
			if oname in t.has:
				t.has.remove(oname)
				t.has.add(nname)
		f = self.findFeature(oname)
		if f is not None:
			f.feature = nname

	def defaultsforfeatures(self) -> None:
		for f in self.features:
			# files without the column, or with an empty cell, give None
			if f.setups is None:
				f.setups = set()
			if f.aka is None:
				f.aka = []
			self.defaultsetups(f.setups)


	def defaultsforinstruments(self) -> None:
		for i in self.instruments:
			self.defaultcurrency(i.currency)
			if i.pipmoney is None:
				i.pipmoney = 1.0
				if i.instrument == "NASDAQ":
					i.pipmoney = 2.0

	def defaultsfortrade(self, t):
			t.rb = self
			t.setdefaults()
			self.defaultinstr(t.instrument)
			self.defaultsetup(t.setup)
			#self.defaultfeatures(t.has, t.setup)
			if t.trade > self.maxid:
				self.maxid = t.trade

	def defaultsfortrades(self) -> None:
		for t in self.trades:
			self.defaultsfortrade(t)

	def defaultinstr(self, name: str) -> None:
		"""add a default for instrument name if not there"""
		if name is None or name == "":
			return
		ni = self.findInstrument(name)
		if ni is None:
			ni = Instrument(name)
			self.instruments.append(ni)

	def defaultsetups(self, setups: set[str]) ->None:
		"""add a default setup for names in setups if not there"""
		if setups is None:
			return
		for s in setups:
			self.defaultsetup(s)

	def defaultsetup(self, name: str) -> None:
		"""add a default for setup name if not there"""
		if name is None or name == "":
			return
		ns = self.findSetup(name)
		if ns is None:
			ns = Setup(name)
			self.setups.append(ns)

	def defaultcurrency(self, name: str) -> None:
		"""add a default for currency name if not there"""
		if name is None or name == "":
			return
		nc = self.findCurrency(name)
		if nc is None:
			nc = Currency(name)
			self.currencies.append(nc)

	def defaultfeatures(self, feats: set[str], setup: str = None) -> None:
		"""add a default for features in feats if not there"""
		if feats is None:
			return
		for k in feats:
			self.defaultfeature(k, setup)

	def defaultfeature(self, name: str, setup: str =  None) ->None:
		"""add a default for feature  if not there"""
		if name is None or name == "":
			return
		nf = self.findFeature(name)
		if nf is None:
			nf = Feature(name)
			self.features.append(nf)
			if setup is not None and setup != "":
				if nf.setups is None:
					nf.setups = set([])
				if not setup in nf.setups:
					nf.setups.add(setup)
			#self.defaultsetup(setup)


	def load(self, dirpath: str = None) -> list[dict]:
		"""load files from dir and return a list of errors.
		each error is a dict with 'file', 'row', 'errors', and 'data'
		"""
		if dirpath is None:
			dirpath = self.dir
		if dirpath is None:
			raise ValueError("no directory set")
		self.dir = dirpath
		errs = self.loadaccount()
		for tbl in TABLES:
			errs += self.loadtable(tbl)
		self.dirty = False
		return errs


	def save(self, dirpath: str = None, filtered=False) -> None:
		"""save files at dir, create it when it does not exist.
		"""
		savingas = (dirpath is not None and self.dir is not None and dirpath != self.dir)
		if dirpath is None:
			dirpath = self.dir
		if dirpath is None:
			raise ValueError("no directory set")
		if self.dir is None:
			self.dir = dirpath
		saved = self.dir
		self.dir = dirpath
		gdir = os.path.join(dirpath, GRAPHSDIR)
		try:
			os.makedirs(gdir, exist_ok = True)
			self.saveaccount()
			for tbl in TABLES:
				self.savetable(tbl, filtered=filtered)
			if not savingas:
				self.dirty = False
			elif self.account and self.account.copygraphs:
				self.savegraphs(filtered=filtered)
		finally:
			self.dir = saved

	@staticmethod
	def isRoadBook(path: str) ->bool:
		try:
			p1 = os.path.join(path, TRADESFILE)
			p2 = os.path.join(path, ACCOUNTFILE)
			return os.path.exists(p1) and os.path.exists(p2)
		except Exception:
			return False

	def path(self, fname: str) -> str:
		return os.path.join(self.dir, fname)

	@staticmethod
	def mknew(file_path: str) -> None:
		gdir = os.path.join(file_path, GRAPHSDIR)
		os.makedirs(gdir, exist_ok = True)
		files = [(ACCOUNTFILE, NEWACCOUNT), (CURRENCIESFILE, NEWCURRENCIES),
			(INSTRUMENTSFILE, NEWINSTRUMENTS), (SETUPSFILE, NEWSETUPS),
			(FEATURESFILE, NEWFEATURES), (TRADESFILE, NEWTRADES)]
		for fname, data in files:
			with open(os.path.join(file_path, fname), "w") as f:
				f.write(data)

	def mkgraphpath(self, t, nb = 0) -> str:
		d = os.path.join(self.dir, GRAPHSDIR)
		if nb == 0:
			p = os.path.join(d, f"trade{t.trade}{t.instrument.lower()}.png")
		else:
			p = os.path.join(d, f"trade{t.trade}{t.instrument.lower()}.{nb}.png")
		return p

	def graphpaths(self, t) -> list[str]:
		if t.graf is not None and len(t.graf) > 0:
			return t.graf
		d = os.path.join(self.dir, GRAPHSDIR)
		p = os.path.join(d, f"trade{t.trade}{t.instrument.lower()}.png")
		return [p]

	def loadaccount(self) -> list[dict]:
		fname = self.path(ACCOUNTFILE)
		aa, errors = load_objects_from_csv(fname, Account)
		for e in errors:
			e["file"] = fname
		if len(aa) == 0:
			raise ValueError(f"no account in {fname}")
		self.account = aa[0]
		return errors

	def saveaccount(self) -> None:
		fname = self.path(ACCOUNTFILE)
		copyfile(fname, fname+BCK)
		write_objects_to_csv(fname, [self.account], Account)

	def loadtable(self, tbl: "Table") -> list[dict]:
		"""load one CSV file into its list attribute and return the errors"""
		fname = self.path(tbl.file)
		cls = tbl.cls
		oldtrades = tbl.attr == "trades" and self.account.version < VERSION
		if oldtrades:
			cls = Trade1
		objs, errors = load_objects_from_csv(fname, cls, tbl.renames)
		for e in errors:
			e["file"] = fname
		if tbl.attr == "trades" and self.account.version != VERSION:
			self.account.version = VERSION
			if oldtrades:
				objs = [Trade.old2new(t) for t in objs]
		objs = sorted(objs, key=tbl.key)
		setattr(self, tbl.attr, objs)
		if tbl.attr == "instruments":
			self.defaultsforinstruments()
		elif tbl.attr == "features":
			self.defaultsforfeatures()
		elif tbl.attr == "trades":
			self.defaultsfortrades()
		return errors

	def savetable(self, tbl: "Table", filtered=False) -> None:
		fname = self.path(tbl.file)
		copyfile(fname, fname+BCK)
		objs = getattr(self, tbl.attr)
		if tbl.attr == "trades":
			if filtered and self.filteredtrades:
				objs = self.filteredtrades
			self.findgraphs(objs)
		write_objects_to_csv(fname, objs, tbl.cls, tbl.renames)

	def storegraphs(self, t) -> list[str]:
		"""copy the graphs of t that are not yet in the roadbook graphs
		directory there, named after the trade, keeping their order.
		Graphs already in that directory are left as they are.
		Returns the error messages."""
		gdir = os.path.realpath(self.path(GRAPHSDIR))
		os.makedirs(gdir, exist_ok=True)
		taken = {os.path.realpath(g) for g in t.graf}
		errs = []
		graf = []
		for src in t.graf:
			if os.path.dirname(os.path.realpath(src)) == gdir:
				graf.append(src)
				continue
			nb = 0
			while True:
				dst = self.mkgraphpath(t, nb)
				if os.path.realpath(dst) not in taken and not os.path.exists(dst):
					break
				nb += 1
			try:
				shutil.copyfile(src, dst)
				taken.add(os.path.realpath(dst))
				graf.append(dst)
			except Exception as e:
				errs.append(f"failed to copy {src}: {e}")
				graf.append(src)
		t.graf = graf
		return errs

	def findgraphs(self, trades) -> None:
		"""set graf for trades without one, using PNGs named after the trade"""
		for t in trades:
			if t.graf is None or len(t.graf) == 0:
				t.graf = []
				for nb in range(6):
					npath = self.mkgraphpath(t, nb)
					if os.path.exists(npath):
						t.graf.append(npath)


	def savegraphs(self, filtered=False) -> None:
		trades = self.trades
		if filtered and self.filteredtrades:
			trades = self.filteredtrades
		for t in trades:
			if t.graf is None or len(t.graf) == 0:
				continue
			for i,g in enumerate(t.graf):
				if not os.path.exists(g):
					continue
				npath = self.mkgraphpath(t, i)
				try:
					if os.path.samefile(g, npath):
						continue
				except Exception:
					pass
				try:
					shutil.copyfile(g, npath)
				except Exception as e:
					print(f"failed to copy graphic {e}", file=sys.stderr)
