

from datawin import *
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QLoggingCategory, QStandardPaths
#
# roadbook using qt & python; take 2
#

def locaterb():
	dirs = ["/u/trade"]
	dirs += QStandardPaths.standardLocations(QStandardPaths.StandardLocation.HomeLocation)
	dirs += QStandardPaths.standardLocations(QStandardPaths.StandardLocation.DocumentsLocation)
	for dir in dirs:
		rb = os.path.join(dir, "diary")
		p = os.path.join(rb, "trades.csv")
		if os.path.exists(p):
			return rb
	return None

if __name__ == "__main__":


	QLoggingCategory.setFilterRules(".")
	app = QApplication(sys.argv)
	win = DataWindow(app)
	locaterb()
	win.show()
	p = locaterb()
	if p is not None:
		rb = RoadBook()
		rb.load(p)
		win.changedata(rb)
	sys.exit(app.exec())
