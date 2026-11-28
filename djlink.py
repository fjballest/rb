#
# The DayJournal button of the graphics window: DayJournal shows the day of
# the trade, zoomed on its entry, in the journal with data of its
# instrument. A running DayJournal gets the trade on its local socket; one
# not running is started with --goto and the same text (see link.py in
# DayJournal).
#
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime

SERVER = "DayJournal-goto"
APP = "DayJournal"

def request(t, inst=None):
	"""the text sent for trade t, or None without a date and an entry time;
	inst, its Instrument, gives the names it goes by. Times are the local
	ones of the trade, sent as seconds since 1970"""
	if t is None or t.datein is None or t.timein is None:
		return None
	at = datetime.combine(t.datein, t.timein).timestamp()
	ex = None
	if t.timeout is not None:
		ex = datetime.combine(t.datein, t.timeout).timestamp()
		if ex < at:	# out after midnight
			ex += 86400
	names = []
	if inst is not None:
		aka = inst.aka.split(";") if isinstance(inst.aka, str) else (inst.aka or [])
		names = [x.strip() for x in aka if x and x.strip()]
	d = getattr(t.dir, "name", str(t.dir)).lower()
	return json.dumps({"instrument": t.instrument or "", "names": names, "at": int(at),
		"exitat": int(ex) if ex is not None else None, "dir": -1 if d.startswith("s") else 1,
		"trade": t.trade})

def send(text, wait=1000):
	"""text to the DayJournal running, if any: whether it got it"""
	from PySide6.QtNetwork import QLocalSocket
	s = QLocalSocket()
	s.connectToServer(SERVER)
	if not s.waitForConnected(wait):
		return False
	s.write((text + "\n").encode("utf-8"))
	s.flush()
	s.waitForBytesWritten(wait)
	s.waitForReadyRead(wait)
	s.disconnectFromServer()
	return True

def command():
	"""how to start DayJournal here: [program, args...], or None"""
	if sys.platform == "darwin":
		if os.path.isdir(f"/Applications/{APP}.app") or os.path.isdir(os.path.expanduser(f"~/Applications/{APP}.app")):
			return ["open", "-a", APP, "--args"]
		return None
	for name in (APP, "dj"):
		p = shutil.which(name)
		if p:
			return [p]
	return None

def goto(t, inst=None):
	"""show trade t in DayJournal: None when done, or why not"""
	text = request(t, inst)
	if text is None:
		return "The trade needs a date and an entry time."
	if send(text):
		return None
	cmd = command()
	if cmd is None:
		return f"{APP} is not running, and it is not installed where it can be started from here."
	try:
		subprocess.Popen(cmd + ["--goto", text], close_fds=True)
	except OSError as e:
		return f"Can't start {APP}: {e}"
	return None
