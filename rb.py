

from datawin import *
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QLoggingCategory
#
# roadbook using qt & python; take 2
#
if __name__ == "__main__":


	QLoggingCategory.setFilterRules(".")
	app = QApplication(sys.argv)
	win = DataWindow(app)
	win.show()
	if os.path.exists("/u/trade/diary"):
		rb = RoadBook()
		rb.load("/u/trade/diary")
		win.changedata(rb)
	sys.exit(app.exec())
