import cv2
import pytesseract
import re
import os
import sys
import easyocr
import datetime
import time

import functools
print = functools.partial(print, flush=True)

reader = easyocr.Reader(['en'])  # add 'es' if needed

def s2f(text):
	try:
		text = text.replace('.','').replace('_', '')
		text = re.sub(r',', '.', text)
		if text[-1] == '.':
			text = text[:-1]
		return text
	except:
		return text


def ocr(n, pref):
	try:
		img = cv2.imread(n)
		results = reader.readtext(img)
		n = 0
		elems = [s2f(text) for (bbox, text, confidence) in results]
		fvgs = list(zip(*[iter(elems)]*3))
		for (fh, fce, fl) in fvgs:
			print(f'$fvg{pref}hi[{n}] = {fh}')
			print(f'$fvg{pref}ce[{n}] = {fce}')
			print(f'$fvg{pref}lo[{n}] = {fl}')
			n += 1
	except Exception as e:
		print(e, file=sys.stderr)

# use as in ocr.py 'cota[#]=%' /Users/nemo/Desktop/list.png
# # is the nb of matching text
# % is the matching text
if __name__ == "__main__":
	args = sys.argv[1:]
	chg=None
	pref='sem'
	if len(args) > 1:
		pref=args[0]
		args=args[1:]
	if len(args) == 0:
		args = ['/Users/nemo/Desktop/list.png']
	for n in args:
		ocr(n, pref)
