from PySide6.QtWidgets import (
	QHBoxLayout,
	QLineEdit,
	QPushButton,
	QCheckBox,
	QLabel,
	QDialog,
	QVBoxLayout,
)
from PySide6.QtCore import Signal, Qt

class FindReplaceDialog(QDialog):
	"""signals carry the text to find, the replacement for replace_*,
	and the case sensitive and whole words options"""
	find_next = Signal(str, bool, bool)
	find_prev = Signal(str, bool, bool)
	replace_one = Signal(str, str, bool, bool)
	replace_all = Signal(str, str, bool, bool)

	def __init__(self, parent=None):
		super().__init__(parent)

		self.setWindowTitle("Find and Replace")
		self.setWindowModality(Qt.WindowModality.NonModal)
		self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

		# --- Widgets ---
		self.find_edit = QLineEdit()
		self.find_edit.setPlaceholderText("Find")

		self.replace_edit = QLineEdit()
		self.replace_edit.setPlaceholderText("Replace")

		self.case_checkbox = QCheckBox("Case sensitive")
		self.case_checkbox.setChecked(True)
		self.words_checkbox = QCheckBox("Whole words")
		self.status = QLabel("")

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
		buttons_layout.addWidget(self.words_checkbox)
		buttons_layout.addStretch()
		buttons_layout.addWidget(self.prev_button)
		buttons_layout.addWidget(self.next_button)
		buttons_layout.addWidget(self.replace_button)
		buttons_layout.addWidget(self.replace_all_button)
		buttons_layout.addWidget(self.close_button)

		main_layout.addLayout(find_layout)
		main_layout.addLayout(replace_layout)
		main_layout.addLayout(buttons_layout)
		main_layout.addWidget(self.status)

		# --- Signals ---
		self.next_button.clicked.connect(self._on_find_next)
		self.prev_button.clicked.connect(self._on_find_prev)
		self.replace_button.clicked.connect(self._on_replace_one)
		self.replace_all_button.clicked.connect(self._on_replace_all)
		self.close_button.clicked.connect(self.close)

		self.find_edit.returnPressed.connect(self._on_find_next)

		self.resize(620, 170)

	# ----------------------------
	# Internal handlers
	# ----------------------------

	def _on_find_next(self):
		self.find_next.emit(
			self.find_edit.text(),
			self.case_checkbox.isChecked(),
			self.words_checkbox.isChecked(),
		)

	def _on_find_prev(self):
		self.find_prev.emit(
			self.find_edit.text(),
			self.case_checkbox.isChecked(),
			self.words_checkbox.isChecked(),
		)

	def _on_replace_one(self):
		self.replace_one.emit(
			self.find_edit.text(),
			self.replace_edit.text(),
			self.case_checkbox.isChecked(),
			self.words_checkbox.isChecked(),
		)

	def _on_replace_all(self):
		self.replace_all.emit(
			self.find_edit.text(),
			self.replace_edit.text(),
			self.case_checkbox.isChecked(),
			self.words_checkbox.isChecked(),
		)

	def setStatus(self, txt):
		self.status.setText(txt)
