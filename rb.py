

from datawin import *
from data import *
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QLoggingCategory, QStandardPaths
#
# roadbook using qt & python; take 2
#

def dirrbs(d):
	rbs = []
	try:
		for f in os.listdir(d):
			p = os.path.join(d, f)
			if RoadBook.isRoadBook(p):
				rbs += [p]
		return rbs
	except Exception as e:
		print(e)
		return []

def locaterbs():
	dirs = []
	rbs = []
	e = os.getenv('RBDIR')
	if e is not None:
		dirs += [e]
	else:
		dirs += ['/u/trade']
	dirs += QStandardPaths.standardLocations(QStandardPaths.StandardLocation.HomeLocation)
	dirs += QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DocumentsLocation)
	for dir in dirs:
		rbs += dirrbs(dir)
	return rbs

if __name__ == "__main__":


	QLoggingCategory.setFilterRules(".")
	app = QApplication(sys.argv)
	rbs = locaterbs()
	win = DataWindow(app, rbs)
	win.show()
	p = None
	if len(rbs) > 0:
		for rb in rbs:
			if os.path.basename(rb) == 'rb':
				p = rb
				break
		if p is None:
			p = rbs[0]
	if p is not None:
		rb = RoadBook()
		rb.load(p)
		win.changedata(rb)
	sys.exit(app.exec())
