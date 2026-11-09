import re
import os
import sys
import datetime
import time
from dataclasses import dataclass

import functools
print = functools.partial(print, flush=True)

debug=os.getenv("DEBUG") == 'y'

def dprint(*args, **xargs):
	"""Print errors."""
	if not debug:
		return
	sys.stdout.flush()
	print(*args, file=sys.stderr, **xargs)

_reader = None

def reader():
	"""OCR engine, loaded on first use because it takes a while to start."""
	global _reader
	if _reader is None:
		import easyocr
		_reader = easyocr.Reader(['en'])  # add 'es' if needed
	return _reader

def imread(path):
	import cv2
	return cv2.imread(path)

def s2i(s):
	try:
		s = s.replace(',','.').replace('..','.').replace('_','-')
		return round(float(s))
	except Exception:
		return 0

def s2f(s):
	try:
		s = s.replace(',','.').replace('..','.').replace('_','-')
		return float(s)
	except Exception:
		return 0

def s2t(s):
	try:
		s = re.sub(r"[,.*;'´`]", ":", s.strip())
		if re.fullmatch(r"\d{4}", s):	# the separator was lost
			s = s[:2] + ":" + s[2:]
		return datetime.datetime.strptime(s, "%H:%M").time()
	except Exception:
		return None

# instrument names as they show in the charts (TradingView, PRT...), checked
# in order: NASDAX is the Nasdaq, not the DAX
INSTRS = (
	("NASDAQ", re.compile(r"nasda[qx]|\b(?:M|N)?NQ[A-Z0-9!]*\b|\bNNQ|\bNAS ?100|\bUS ?100|\bUSTEC|\bUSTECH", re.I)),
	("DAX", re.compile(r"\bF?DAX|\bFDXM|\bFDXS|\bGER ?40|\bDE ?40|\bGERMANY ?40|Alemania ?40", re.I)),
)

def instrumentin(text):
	"""the instrument named in a text of the chart, or None"""
	for name, rx in INSTRS:
		if rx.search(text):
			return name
	return None

def chartzone(texts, instr):
	"""the time zone the chart times are in: the UTC offset it shows
	(TradingView: 04:31:42 UTC-5), or New York for the Nasdaq, or None
	when they are already local"""
	for t in texts:
		m = re.search(r"UTC\s*([+-−]\s*\d{1,2})(?:[:.]?(\d\d))?", t)
		if m:
			h = int(m.group(1).replace("−", "-").replace(" ", ""))
			mins = int(m.group(2) or 0)
			return datetime.timezone(datetime.timedelta(hours=h, minutes=mins if h >= 0 else -mins))
	if instr == "NASDAQ":
		try:
			from zoneinfo import ZoneInfo
			return ZoneInfo("America/New_York")
		except Exception:
			return None
	return None

def tolocal(dt, tz):
	"""dt, a chart time in zone tz, as local time (naive)"""
	if tz is None:
		return dt
	return dt.replace(tzinfo=tz).astimezone().replace(tzinfo=None)

def labelcolor(img, box):
	""""green", "red" or None: the color of the label under a text box
	(TradingView marks the entry time in green and the exit in red)"""
	try:
		x0, y0, x1, y1 = box
		h, w = img.shape[:2]
		x0, x1 = max(0, int(x0)), min(w, int(x1))
		y0, y1 = max(0, int(y0)), min(h, int(y1))
		if x1 <= x0 or y1 <= y0:
			return None
		px = img[y0:y1, x0:x1].reshape(-1, 3)	# BGR
		import numpy
		b, g, r = (numpy.median(px[:, i]) for i in range(3))
	except Exception:
		return None
	if g > r + 50 and g > b + 20:
		return "green"
	if r > g + 70 and r > b + 50:
		return "red"
	return None

DATERX = re.compile(r"(\d\d)-(\d\d)-(\d\d)")
TIMERX = re.compile(r"(?<!\d)(\d\d?[*.,:;'´`]\d\d|\d{4})(?!\d)")

def boxof(bbox):
	xs = [p[0] for p in bbox]
	ys = [p[1] for p in bbox]
	return float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))

def timelabels(img, results):
	"""the date and time labels of the time axis, as [(datetime, color)]:
	"lun 26-11-09 02:59" (yy-mm-dd), read as one text or as the date and a
	time just right of it"""
	boxes = [(boxof(bb), t) for bb, t, _ in results]
	labels = []
	for (x0, y0, x1, y1), t in boxes:
		m = DATERX.search(t)
		if not m:
			continue
		try:
			d = datetime.date(2000 + int(m.group(1)), int(m.group(2)), int(m.group(3)))
		except ValueError:
			continue
		box = [x0, y0, x1, y1]
		tm = None
		rest = TIMERX.search(t[m.end():])
		if rest:
			tm = s2t(rest.group(1))
		if tm is None:	# the time read apart, right after the date
			hh = y1 - y0
			near = [(bx0, b, tt) for b, tt in boxes for bx0 in [b[0]]
				if 0 <= b[0] - x1 <= 2 * hh and abs((b[1] + b[3]) / 2 - (y0 + y1) / 2) < hh / 2]
			for bx0, b, tt in sorted(near, key=lambda n: n[0]):
				r = TIMERX.search(tt)
				if r and s2t(r.group(1)) is not None:
					tm = s2t(r.group(1))
					box[2] = b[2]
					break
		if tm is None:
			continue
		labels.append((datetime.datetime.combine(d, tm), labelcolor(img, box)))
	return labels

def findsetup(s, ss):
	s = s.lower()
	for x in ss:
		if x.lower() in s:
			return x
	return None

@dataclass
class TradeOCR:
	setup: str = None
	instr: str = None
	ptstp: int = None
	ptsstop: int = None
	success: bool = None
	long: bool = None
	at: datetime.datetime = None
	size: float = None
	tin: time = None
	tout: time = None

	def OCR(path, setups=None):
		try:
			if setups is None:
				setups = []

			return TradeOCR._OCR(path, [ x for x in setups ])
		except Exception as e:
			print("OCR:", e, file=sys.stderr)
			return None

	def _times(img, results, instr):
		"""when the trade went in and out, as local datetimes: the labels
		of the time axis, the green one for the entry and the red one for
		the exit (the latest of each: charts of longer bars round them
		down), converted from the chart's time zone. Without colors, the
		first two times found."""
		labels = timelabels(img, results)
		dprint("labels:", labels)
		tz = chartzone([t for _, t, _ in results], instr)
		ins = [dt for dt, c in labels if c == "green"]
		outs = [dt for dt, c in labels if c == "red"]
		tin = max(ins) if ins else None
		tout = max([o for o in outs if tin is None or o >= tin] or outs) if outs else None
		if tin is None and tout is None and labels:
			dts = [dt for dt, _ in labels]
			tin, tout = dts[0], dts[1] if len(dts) > 1 else dts[0]
		if tin is None and tout is None:
			tin, tout = TradeOCR._dates(results)
			return tin, tout, None
		tin = tolocal(tin or tout, tz)
		tout = tolocal(tout or tin, tz)
		return tin.time(), tout.time(), tin

	def _side(ys):
		"""long or short from where the labels of the position are: the
		stop under the target or the entry is a long"""
		s = ys.get("stop")
		other = ys.get("target", ys.get("entry"))
		if s is not None and other is not None and s != other:
			return bool(s > other)
		t, e = ys.get("target"), ys.get("entry")
		if t is not None and e is not None and t != e:
			return bool(t < e)
		return None

	# heuristics to get dates in vertical marks
	def _dates(results):
		tin=None
		tout=None
		saved=None
		for (bbox, text, confidence) in results:
			dprint('--r-->', text)
			match1 = re.search(r'(\d\d-\d\d-\d\d)', text)
			match = re.search(r'(\d\d-\d\d-\d\d)\s+(\d\d[*.,:]\d\d)', text)
			if match1 and not match:
				saved = text
				continue
			if saved is not None:
				match = re.search(r'(\d\d-\d\d-\d\d)\s+(\d\d[*.,:]\d\d)', text+' '+saved)
			saved=None
			if match:
				x = match.group(2)
				dprint('==r=> ', x)
				if tin is None:
					tin=s2t(x)
				else:
					tout=s2t(x)
				if tout is not None:
					break
		if tout is None:
			tout = tin
		if tin is None:
			tin = tout
		return tin, tout

	# heuristics for PRT/TradingView scans according to experience
	def _OCR(path, setups):
		first=True
		instr=None
		ninstr=0
		votes = {}	# instrument -> how many texts name it
		ys = {}		# "stop", "target", "entry" -> the middle of their labels
		sizenext = False
		ptstp=None
		ptsstop=None
		success=None
		long=None
		at=None
		setup = None
		size=None
		tin=None
		tout=None
		ltext=''
		try:
			mt = os.path.getmtime(path)
			at = datetime.datetime.fromtimestamp(mt)
		except Exception:
			pass
		# Read text from image
		img = imread(path)
		results = reader().readtext(img)

		dprint(f"setups: {setups}")
		for (bbox, text, confidence) in results:
			_, y0, _, y1 = boxof(bbox)
			ymid = (y0 + y1) / 2
			# the instrument named most; else the first name, usually
			named = instrumentin(text)
			if named:
				votes[named] = votes.get(named, 0) + 1
			if first:
				first = False
				if text.isupper():
					instr=text
			if text == instr:
				ninstr += 1
			if re.search(r'\b(Cerrado|Abierto|Closed|Open)\b.*(PyG|P&L)', text):
				ys.setdefault("entry", ymid)
			if sizenext:	# "Cantidad:" ended the text before; the number came apart
				sizenext = False
				m = re.fullmatch(r'\s*(\d+([,.]\d+)?)\s*', text)
				if m and size is None:
					size = s2f(m.group(1))
					continue
			if re.search(r'Cantidad:\s*$', text):
				sizenext = True
			# combine separate strings if they seem to be split
			# PRT
			if 'nancia' in text or 'rdida' in text:
				if not 'pts' in text and 'pts' in ltext:
					text = ltext + text
				if not 'pips' in text and 'pips' in ltext:
					text = ltext + text
			dprint("-> ",text)
			if setup is None and len(setups) > 0:
				setup = findsetup(text.lower(), setups)

			# TradingView
			match = re.search(r'Stop:\s*([+-]?\d+([,.]+\d+)?)', text)
			if match:
				ys.setdefault("stop", ymid)
				x = match.group(1)
				ptsstop = s2i(x)
				ptsstop=abs(ptsstop)
				ltext = ''
				if long is None:
					long = False
				continue
			match = re.search(r'(?:Objetivo|Target):\s*([+-]?\d+([,.]+\d+)?)', text)
			if match:
				ys.setdefault("target", ymid)
				x = match.group(1)
				ptstp = s2i(x)
				ltext = ''
				if long is None:
					long = True
				ptstp=abs(ptstp)
				continue
			match = re.search(r'PyG:\s*([+-]?\d+([,.]+\d+)?)', text)
			if match:
				x = match.group(1)
				v = s2i(x)
				success = v > 0
				continue
			match = re.search(r'Cantidad:\s*([+-]?\d+([,.]+\d+)?)', text)
			if match:
				x = match.group(1)
				size = s2f(x)
				continue

			# PRT
			match = re.search(r'([+-]?\d+([,.]+\d+)?)\s*(pips|pts).*nancia', text)
			# sometimes the dot is missed, see if that's the case
			dotmatch = re.search(r'([+-]?\d+([,.]+\d+))\s*(pips|pts).*nancia', text)
			if match:
				dprint(f"MATCH: {text}, Confidence: {confidence:.2f}")
				x = match.group(1)
				ptstp = s2i(x)
				if not dotmatch:
					ptstp /= 100
				ltext = ''
				ptstp=abs(ptstp)
				continue
			match = re.search(r'([+-]?\d+([,.]+\d+)?)\s*(pips|pts).*rdida', text)
			dotmatch = re.search(r'([+-]?\d+([,.]+\d+))\s*(pips|pts).*rdida', text)
			if match:
				dprint(f"MATCH: {text}, Confidence: {confidence:.2f}")
				x = match.group(1)
				ptsstop = s2i(x)
				ptsstop=abs(ptsstop)
				if not dotmatch:
					ptsstop /= 100
				ltext = ''
				continue
			match = re.search(r'[PL](.*)(.*)nancia', text)
			if match:
				dprint("MATCH ", text)
				success = not 'cia:-' in text and not 'cia:_' in text
			ltext = text

		if votes:
			instr = max(votes, key=votes.get)
		# the stop below the entry (or the target) is a long, above it a short
		side = TradeOCR._side(ys)
		if side is not None:
			long = side
		tin, tout, when = TradeOCR._times(img, results, instr)
		if when is not None:
			at = when

		to = TradeOCR(setup, instr, ptstp, ptsstop, success, long, at, size, tin, tout)
		dprint(to)
		return to

#
#	python3 graphocr.py  /Users/nemo/Desktop/day260904.png
#	to print just text (three letters together at least) and clean a bit
#
#
#	python3 graphocr.py  -a /Users/nemo/Desktop/day260904.png
#	to print all text found as-is
#
if __name__ == "__main__":
	args = [x for x in sys.argv[1:]]
	clean = True
	if len(args) > 0 and args[0] == '-a':
		clean=False
		args = args[1:]
	for a in args:
		print(a)
		img = imread(a)
		results = reader().readtext(img)
		ltext = ''
		for (bbox, text, confidence) in results:
			if clean:
				if not re.search(r'[a-zA-Z][a-zA-Z][a-zA-Z]', text):
					continue
				text = text.strip()
				if text == ltext:
					continue
				ltext = text
			print(text)
