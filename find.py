from PySide6.QtWidgets import (
	QWidget,
	QHBoxLayout,
	QLineEdit,
	QPushButton,
	QCheckBox,
	QLabel,
	QDialog,
	QVBoxLayout,
)
from PySide6.QtCore import Signal, Qt

#widget = FindReplaceWidget()
#widget.find_next.connect(lambda t, c: find_next(editor, t, c))
#widget.find_prev.connect(lambda t, c: find_prev(editor, t, c))
#widget.replace_one.connect(lambda f, r, c: replace_one(editor, f, r, c))
#widget.replace_all.connect(lambda f, r, c: replace_all(editor, f, r, c))

class FindReplaceWidget(QWidget):
	find_next = Signal(str, bool)
	find_prev = Signal(str, bool)
	replace_one = Signal(str, str, bool)
	replace_all = Signal(str, str, bool)

	def __init__(self, parent=None):
		super().__init__(parent)

		self.find_edit = QLineEdit()
		self.find_edit.setPlaceholderText("Find")

		self.replace_edit = QLineEdit()
		self.replace_edit.setPlaceholderText("Replace")

		self.case_checkbox = QCheckBox("Aa")

		self.next_button = QPushButton("Next")
		self.prev_button = QPushButton("Prev")
		self.replace_button = QPushButton("Replace")
		self.replace_all_button = QPushButton("All")

		layout = QHBoxLayout(self)
		layout.setContentsMargins(4, 4, 4, 4)
		layout.setSpacing(4)

		layout.addWidget(QLabel("Find:"))
		layout.addWidget(self.find_edit)
		layout.addWidget(QLabel("Replace:"))
		layout.addWidget(self.replace_edit)

		layout.addWidget(self.case_checkbox)
		layout.addWidget(self.prev_button)
		layout.addWidget(self.next_button)
		layout.addWidget(self.replace_button)
		layout.addWidget(self.replace_all_button)

		self.next_button.clicked.connect(self._on_find_next)
		self.prev_button.clicked.connect(self._on_find_prev)
		self.replace_button.clicked.connect(self._on_replace_one)
		self.replace_all_button.clicked.connect(self._on_replace_all)

		self.find_edit.returnPressed.connect(self._on_find_next)

	# ----------------------------
	# Internal handlers
	# ----------------------------

	def _on_find_next(self):
		self.find_next.emit(
			self.find_edit.text(),
			self.case_checkbox.isChecked(),
		)

	def _on_find_prev(self):
		self.find_prev.emit(
			self.find_edit.text(),
			self.case_checkbox.isChecked(),
		)

	def _on_replace_one(self):
		self.replace_one.emit(
			self.find_edit.text(),
			self.replace_edit.text(),
			self.case_checkbox.isChecked(),
		)

	def _on_replace_all(self):
		self.replace_all.emit(
			self.find_edit.text(),
			self.replace_edit.text(),
			self.case_checkbox.isChecked(),
		)


class FindDialog(QDialog):
	find_next = Signal(str, bool)
	find_prev = Signal(str, bool)

	def __init__(self, parent=None):
		super().__init__(parent)

		self.setWindowTitle("Find")
		self.setWindowModality(Qt.NonModal)
		self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

		# --- Widgets ---
		self.find_edit = QLineEdit()
		self.find_edit.setPlaceholderText("Find")

		self.case_checkbox = QCheckBox("Case sensitive")
		self.case_checkbox.setChecked(True)

		self.next_button = QPushButton("Next")
		self.prev_button = QPushButton("Previous")
		self.close_button = QPushButton("Close")

		self.next_button.setDefault(True)

		# --- Layout ---
		main_layout = QVBoxLayout(self)

		find_layout = QHBoxLayout()
		find_layout.addWidget(QLabel("Find:"))
		find_layout.addWidget(self.find_edit)

		buttons_layout = QHBoxLayout()
		buttons_layout.addWidget(self.case_checkbox)
		buttons_layout.addStretch()
		buttons_layout.addWidget(self.prev_button)
		buttons_layout.addWidget(self.next_button)
		buttons_layout.addWidget(self.close_button)

		main_layout.addLayout(find_layout)
		main_layout.addLayout(buttons_layout)

		# --- Signals ---
		self.next_button.clicked.connect(self._on_find_next)
		self.prev_button.clicked.connect(self._on_find_prev)
		self.close_button.clicked.connect(self.close)

		self.find_edit.returnPressed.connect(self._on_find_next)

		self.resize(420, 120)

	# ----------------------------
	# Internal handlers
	# ----------------------------

	def _on_find_next(self):
		self.find_next.emit(
			self.find_edit.text(),
			self.case_checkbox.isChecked(),
		)

	def _on_find_prev(self):
		self.find_prev.emit(
			self.find_edit.text(),
			self.case_checkbox.isChecked(),
		)


class FindReplaceDialog(QDialog):
	find_next = Signal(str, bool)
	find_prev = Signal(str, bool)
	replace_one = Signal(str, str, bool)
	replace_all = Signal(str, str, bool)

	def __init__(self, parent=None):
		super().__init__(parent)

		self.setWindowTitle("Find and Replace")
		self.setWindowModality(Qt.NonModal)
		self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

		# --- Widgets ---
		self.find_edit = QLineEdit()
		self.find_edit.setPlaceholderText("Find")

		self.replace_edit = QLineEdit()
		self.replace_edit.setPlaceholderText("Replace")

		self.case_checkbox = QCheckBox("Case sensitive")
		self.case_checkbox.setChecked(True)

		self.next_button = QPushButton("Next")
		self.prev_button = QPushButton("Previous")
		self.replace_button = QPushButton("Replace")
		self.replace_all_button = QPushButton("Replace All")
		self.close_button = QPushButton("Close")

		self.next_button.setDefault(True)

		# --- Layout ---
		main_layout = QVBoxLayout(self)

		find_layout = QHBoxLayout()
		find_layout.addWidget(QLabel("Find:"))
		find_layout.addWidget(self.find_edit)

		replace_layout = QHBoxLayout()
		replace_layout.addWidget(QLabel("Replace:"))
		replace_layout.addWidget(self.replace_edit)

		buttons_layout = QHBoxLayout()
		buttons_layout.addWidget(self.case_checkbox)
		buttons_layout.addStretch()
		buttons_layout.addWidget(self.prev_button)
		buttons_layout.addWidget(self.next_button)
		buttons_layout.addWidget(self.replace_button)
		buttons_layout.addWidget(self.replace_all_button)
		buttons_layout.addWidget(self.close_button)

		main_layout.addLayout(find_layout)
		main_layout.addLayout(replace_layout)
		main_layout.addLayout(buttons_layout)

		# --- Signals ---
		self.next_button.clicked.connect(self._on_find_next)
		self.prev_button.clicked.connect(self._on_find_prev)
		self.replace_button.clicked.connect(self._on_replace_one)
		self.replace_all_button.clicked.connect(self._on_replace_all)
		self.close_button.clicked.connect(self.close)

		self.find_edit.returnPressed.connect(self._on_find_next)

		self.resize(520, 150)

	# ----------------------------
	# Internal handlers
	# ----------------------------

	def _on_find_next(self):
		self.find_next.emit(
			self.find_edit.text(),
			self.case_checkbox.isChecked(),
		)

	def _on_find_prev(self):
		self.find_prev.emit(
			self.find_edit.text(),
			self.case_checkbox.isChecked(),
		)

	def _on_replace_one(self):
		self.replace_one.emit(
			self.find_edit.text(),
			self.replace_edit.text(),
			self.case_checkbox.isChecked(),
		)

	def _on_replace_all(self):
		self.replace_all.emit(
			self.find_edit.text(),
			self.replace_edit.text(),
			self.case_checkbox.isChecked(),
		)
