import cv2
import pytesseract
import re
import os
import sys
import easyocr
import datetime
import time
from dataclasses import dataclass, field

import functools
print = functools.partial(print, flush=True)

debug=os.getenv("DEBUG") == 'y'

def dprint(*args, **xargs):
	"""Print errors."""
	if not debug:
		return
	sys.stdout.flush()
	print(*args, file=sys.stderr, **xargs)

reader = easyocr.Reader(['en'])  # add 'es' if needed

def s2i(s):
	try:
		s = s.replace(',','.').replace('..','.').replace('_','-')
		return round(float(s))
	except:
		#print("XXX float", s, file=sys.stderr)
		return 0

def s2f(s):
	try:
		s = s.replace(',','.').replace('..','.').replace('_','-')
		return float(s)
	except:
		#print("XXX float ", s, file=sys.stderr)
		return 0

def s2t(s):
	try:
		s = s.replace(',',':').replace('.',':').replace('*',':')
		return datetime.datetime.strptime(s, "%H:%M").time()
	except:
		#print("XXX time ", s, file=sys.stderr)
		return None

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

	# heuristics to get dates in vertical marks
	def _dates(img):
		#img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
		results = reader.readtext(img)
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
		ptstp=None
		ptsstop=None
		success=None
		long=None
		at=None
		setup = None
		size=None
		tin=None
		tout=None
		try:
			mt = os.path.getmtime(path)
			at = datetime.datetime.fromtimestamp(mt)
		except:
			pass
		# Read text from image
		img = cv2.imread(path)
		results = reader.readtext(img)

		dprint(f"setups: {setups}")
		for (bbox, text, confidence) in results:
			# first name is the instrument usually
			if first:
				first = False
				if text.isupper():
					instr=text
			if 'DAX' in text and instr is None:
				instr="DAX"
			elif 'NASDAQ' in text and instr is None:
				instr="NASDAQ"
			if text == instr:
				ninstr += 1
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
				x = match.group(1)
				ptsstop = s2i(x)
				ptsstop=abs(ptsstop)
				ltext = ''
				if long is None:
					long = False
				continue
			match = re.search(r'Objetivo:\s*([+-]?\d+([,.]+\d+)?)', text)
			if match:
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

		tin, tout = TradeOCR._dates(img)

		to = TradeOCR(setup, instr, ptstp, ptsstop, success, long, at, size, tin, tout)
		dprint(to)
		return to

if __name__ == "__main__":
	to = TradeOCR.OCR("/Users/nemo/Desktop/testing.png")
	print(to)
