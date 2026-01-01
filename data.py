#
# data classes
#
from dataclasses import dataclass, field
from time import gmtime
from datetime import date, time, datetime
from typing import Optional, Set
from enum import Enum, IntEnum
import os
import sys
import shutil
import traceback
from csv_mapper import load_objects_from_csv,write_objects_to_csv

ACCOUNTFILE = "account.csv"
SETUPSFILE = "setups.csv"
TRADESFILE = "trades.csv"
CURRENCIESFILE = "divisas.csv"
FEATURESFILE = "features.csv"
INSTRUMENTSFILE = "activos.csv"
GRAPHSDIR = "diarygraphs"
BCK = "~"

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
	version: float = 1.1

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

def featureexample():
	return Feature("ApoyoH4 Aper", "apoyo pero antes de GL y con cota cerca",
		set(["ApoyoH4 Aper", "ApoyoH4 Aper", "ApoyoH4 Aper"]))

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
	pip: Optional[float] = 1.0
	stoppips: Optional[float] = 0
	scale: Optional[float] = 0
	diary: Optional[float] = 0
	candleh4: Optional[float] = 0
	candle144: Optional[float] = 0
	spread: Optional[float] = 0
	sreadpm: Optional[float] = 0

def instrumentexample():
	return Instrument("NASDAQ", "SP 500", "EURUSD", 0.0001, 144.3, 240000,
		243.4, 354.4, 354.4,  432, 432)

TRADEVIEWORDER = ["trade", "instrument", "setup", "dir", "lots", "datein", "timein",
	"timeout", "euros", "pts", "notes"]	#
TRADEVIEWRDONLY = ["trade", "pts"]


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
	ptsin: float = 0
	ptsout: float = 0
	sysout: Optional[float] = 0
	ptsstop: Optional[float] = 0
	euros: Optional[float] = 0.0
	eurstop: Optional[float] = 0.0
	graf: Optional[str] = ""
	notes: Optional[str] = ""
	mistakes: Optional[str] = ""
	has: Optional[Set[str]] = field(default_factory= set)
	pts: Optional[float] = 0.0

	def copyFrom(self, o):
		"""swallow copy"""
		self.trade = o.trade
		self.instrument = o.instrument
		self.setup = o.setup
		self.datein = o.datein
		self.dir = o.dir
		self.lots = o.lots
		self.timein = o.timein
		self.timeout = o.timeout
		self.ptsin = o.ptsin
		self.ptsout = o.ptsout
		self.sysout = o.sysout
		self.ptsstop = o.ptsstop
		self.euros = o.euros
		self.eurstop = o.eurstop
		self.graf = o.graf
		self.notes = o.notes
		self.mistakes = o.mistakes
		self.has = o.has
		self.pts = o.pts

	def __postinit__(self):
		self.pts = self.points()
		self.rb = None
	def inval(self)-> None:
		self.pts = self.points()


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
		if self.dir == Dir.Long:
			return self.ptsout - self.ptsin
		else:
			return self.ptsin - self.ptsout
	def stoppoints(self) -> float:
		if self.dir == Dir.Short:
			return self.ptsstop - self.ptsin
		else:
			return self.ptsin - self.ptsstop
	def syspoints(self) -> float:
		if self.sysout == 0:
			self.sysout = self.ptsout
		if dir == Dir.Long:
			return self.sysout - self.ptsin
		else:
			return self.ptsin - self.sysout

	def result(self, neutral: float = 0) -> Result:
		if neutral == 0 and self.rb and self.rb.account:
			neutral = self.rb.account.neutral
		pt = self.euros if self.euros != 0 else self.points()
		if pt > neutral:
			return Result.OK
		if pt < -neutral:
			return Result.KO
		return Result.Neutral

	def sysresult(self, neutral: float = 0) -> Result:
		if neutral == 0 and self.rb and self.rb.account:
			neutral = self.rb.account.neutral
		pt = self.syspoints()
		if pt > neutral:
			return Result.OK
		if pt < -neutral:
			return Result.KO
		return Result.Neutral
	def isOK(self) -> bool:
		return self.result() == Result.OK
	def isKO(self) -> bool:
		return self.result() == Result.KO

	def instr(self) -> Instrument:
		if self.instrument is None or self.instrument == "":
			return None
		if self.rb is None:
			raise "roadbook not set in trade"
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

	def currency(self) -> Currency:
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
		if self.currency == "EUR" or self.currency == "EURO":
			return pts * self.lots * toeur
		c = self.currency()
		if c is not None and c.euros2 != 0:
			toeur = 1/c.euros2
		return pts * self.lots * toeur

	def syseuros(self) -> float:
		return self.ptseuros(self.syspoints())

	def hasfeature(self, name) -> bool:
		return self.has is not None and name in self.has

	def checkOut(self) -> str:
		t = self
		if t.instrument is None or t.instrument == "":
			return "no instrument"
		if t.setup is None or t.setup == "":
			return "no setup"
		if t.lots <= 0.0:
			return "bad size in lots"
		if t.ptsin <= 0.0:
			return "bad ptsin"
		if t.ptsout <= 0.0:
			return "bad ptsout"
		if t.ptsstop != 0:
			if t.dir == Dir.Long and t.ptsstop > t.ptsin:
				return "stop above in for long"
			if t.dir == Dir.Short and t.ptsstop < t.ptsin:
				return "stop not above in for short"
		return None

def tradeexample():
	return Trade(100, "NASDAQ", "ApoyoH4 Aper", date.today(), Dir.Short, 1.2,
		"15:30", "15:30", 245430, 245430, 245430, 245430,
		154.3, 154.3, "/path/to/plot", "apoyo 4H, sin muros, fuerza, sem flojo. 1H sin fuerza: no reentrar", "mejor salir por patron si sem en giro", "Apertura;Apoyo D;Apoyo4H;Desp.Corr.;Pullback;Sin Muros;Val Estr;Willy OK", 245430)

def copyfile(src: str, dst: str) -> None:
	try:
		shutil.copyfile(src, dst)
	except:
		pass

class RoadBook:
	def __init__(self, trades = [], instrs = [], setups = [], features = [], currencies = []):
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
		return [c.currency for c in self.currencies]

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
			c.currency = nname

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
			#self.defaultsetups(f.setups)
			pass

	def defaultsforinstruments(self) -> None:
		for i in self.instruments:
			self.defaultcurrency(i.currency)

	def defaultsfortrade(self, t):
			t.rb = self
			t.pts = t.points()
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
			#print(f"dflt setup {name}", file=sys.stderr)
			#traceback.print_stack()

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


	def load(self, dir: str = None) -> list[dict]:
		"""load files from dir and return a list of errors.
		each error is a dict with 'file', 'row', 'errors', and 'data'
		"""
		if dir is None:
			dir = self.dir
		if dir is None:
			raise "no directory set"
		self.dir = dir
		_, errs = self.loadaccount()

		_, ierrs = self.loadcurrencies()
		errs = errs +  ierrs
		_, ierrs = self.loadinstruments()
		errs = errs +  ierrs
		_, ierrs = self.loadsetups()
		errs = errs +  ierrs
		_, ierrs = self.loadfeatures()
		errs = errs +  ierrs
		_, ierrs = self.loadtrades()
		errs = errs +  ierrs
		self.dirty = False
		return errs

	def save(self, dir: str = None, filtered=False) -> None:
		"""save files at dir, create it when it does not exist.
		"""
		savingas = (dir is not None and self.dir is not None and dir != self.dir)
		if dir is None:
			dir = self.dir
		if dir is None:
			raise "no directory set"
		if self.dir is None:
			self.dir = dir
		saved = self.dir
		self.dir = dir
		gdir = os.path.join(dir, GRAPHSDIR)
		try:
			os.makedirs(gdir, exist_ok = True)
			self.saveaccount()
			self.savecurrencies()
			self.saveinstruments()
			self.savesetups()
			self.savefeatures()
			self.savetrades(filtered=filtered)
			if not savingas:
				self.dirty = False
			elif self.account and self.account.copygraphs:
				self.savegraphs(filtered=filtered)
		finally:
			self.dir = saved

	def isRoadBook(path):
		p = os.path.join(path, TRADESFILE)
		return os.path.exists(p)

	def accountpath(self, suff = "") -> str:
		return os.path.join(self.dir, ACCOUNTFILE) + suff
	def currenciespath(self, suff = "") -> str:
		return os.path.join(self.dir, CURRENCIESFILE) + suff
	def instrumentspath(self, suff = "") -> str:
		return os.path.join(self.dir, INSTRUMENTSFILE) + suff
	def setupspath(self, suff = "") -> str:
		return os.path.join(self.dir, SETUPSFILE) + suff
	def featurespath(self, suff = "") -> str:
		return os.path.join(self.dir, FEATURESFILE) + suff
	def tradespath(self, suff = "") -> str:
		return os.path.join(self.dir, TRADESFILE) + suff

	def mkgraphpath(self, t) -> str:
		d = os.path.join(self.dir, GRAPHSDIR)
		p = os.path.join(d, f"trade{t.trade}{t.instrument.lower()}.png")
		return p

	def graphpath(self, t) -> str:
		if t.graf is not None and t.graf != "":
			return t.graf
		d = os.path.join(self.dir, GRAPHSDIR)
		p = os.path.join(d, f"trade{t.trade}{t.instrument.lower()}.png")
		return p

	def loadaccount(self, fname: str = None) -> tuple[Account, list[dict]]:
		if fname is None or fname == "":
			fname = self.accountpath()
		aa, errors = load_objects_from_csv(fname, Account)
		for e in errors:
			e["file"] = fname
		if len(aa) == 0:
			raise "no account"
		self.account = aa[0]
		return self.account, errors

	def loadcurrencies(self, fname: str = None) -> tuple[list[Currency], list[dict]]:
		if fname is None or fname == "":
			fname = self.currenciespath()
		cs, errors = load_objects_from_csv(fname, Currency)
		for e in errors:
			e["file"] = fname
		cs = sorted(cs, key = lambda t: t.name)
		self.currencies = cs
		return cs, errors

	def savecurrencies(self, fname: str = None) -> None:
		if fname is None or fname == "":
			fname = self.currenciespath()
		copyfile(fname, fname+BCK)
		write_objects_to_csv(fname, self.currencies, Currency)

	def loadinstruments(self, fname: str = None) -> tuple[list[Instrument], list[dict]]:
		if fname is None or fname == "":
			fname = self.instrumentspath()
		ii, errors = load_objects_from_csv(fname, Instrument)
		for e in errors:
			e["file"] = fname
		ii = sorted(ii, key = lambda t: t.instrument.lower())
		self.instruments = ii
		self.defaultsforinstruments()
		return ii, errors

	def saveaccount(self, fname: str = None) -> None:
		if fname is None or fname == "":
			fname = self.accountpath()
		copyfile(fname, fname+BCK)
		write_objects_to_csv(fname, [self.account], Account)

	def saveinstruments(self, fname: str = None) -> None:
		if fname is None or fname == "":
			fname = self.instrumentspath()
		copyfile(fname, fname+BCK)
		write_objects_to_csv(fname, self.instruments, Instrument)

	def loadsetups(self, fname: str = None) -> tuple[list[Setup], list[dict]]:
		if fname is None or fname == "":
			fname = self.setupspath()
		ss, errors = load_objects_from_csv(fname, Setup)
		for e in errors:
			e["file"] = fname
		ss = sorted(ss, key = lambda t: t.setup.lower())
		self.setups = ss
		return ss, errors

	def savesetups(self, fname: str = None) -> None:
		if fname is None or fname == "":
			fname = self.setupspath()
		copyfile(fname, fname+BCK)
		write_objects_to_csv(fname, self.setups, Setup)

	def loadfeatures(self, fname: str = None) -> tuple[list[Feature], list[dict]]:
		if fname is None or fname == "":
			fname = self.featurespath()
		fs, errors = load_objects_from_csv(fname, Feature)
		for e in errors:
			e["file"] = fname
		fs = sorted(fs, key = lambda t: t.feature.lower())
		self.features = fs
		self.defaultsforfeatures()
		return fs, errors

	def savefeatures(self, fname: str = None) -> None:
		if fname is None or fname == "":
			fname = self.featurespath()
		copyfile(fname, fname+BCK)
		write_objects_to_csv(fname, self.features, Feature)

	def loadtrades(self, fname: str = None) -> tuple[list[Trade], list[dict]]:
		if fname is None or fname == "":
			fname = self.tradespath()
		rens = {"datein":"date", "has":"with"}
		ts, errors = load_objects_from_csv(fname, Trade, rens)
		for e in errors:
			e["file"] = fname
		ts = sorted(ts, key = lambda t: t.datein)
		self.trades = ts
		self.defaultsfortrades()
		return ts, errors

	def savetrades(self, fname: str = None, filtered=False) -> None:
		if fname is None or fname == "":
			fname = self.tradespath()
		copyfile(fname, fname+BCK)
		rens = {"datein":"date", "has":"with"}
		skips = set(["pts"])
		trades = self.trades
		if filtered and self.filteredtrades:
			trades = self.filteredtrades
		for t in trades:
			if t.graf is None or t.graf == "":
				npath = self.mkgraphpath(t)
				if os.path.exists(npath):
					t.graf = npath
		write_objects_to_csv(fname, trades, Trade, rens, skips)


	def savegraphs(self, filtered=False) -> None:
		trades = self.trades
		if filtered and self.filteredtrades:
			trades = self.filteredtrades
		for t in trades:
			if t.graf is None or not os.path.exists(t.graf):
				continue
			npath = self.mkgraphpath(t)
			try:
				if os.path.samefile(t.graf, npath):
					continue
			except:
				pass
			try:
				shutil.copyfile(t.graf, npath)
			except Exception as e:
				print(f"failed to copy graphic {e}", file=sys.stderr)
