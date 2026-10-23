#
# roadbook backups: a roadbook at /a/b/rb is backed up into
# /a/b/rb.dump/YYMMDD/, one backup per day, keeping the CSVs and the
# images with the same layout they have in the roadbook
#
import os
import re
import shutil
from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
	QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox,
	QPushButton, QVBoxLayout
)

DUMPSUFFIX = ".dump"
BACKUPNAME = re.compile(r"^\d{6}$")	# YYMMDD
COPIED = (".csv", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".drw")

def dumpdir(rbdir):
	return os.path.normpath(rbdir) + DUMPSUFFIX

def backups(rbdir):
	"""the backups of the roadbook at rbdir, oldest first"""
	d = dumpdir(rbdir)
	if not os.path.isdir(d):
		return []
	return sorted(n for n in os.listdir(d)
		if BACKUPNAME.match(n) and os.path.isdir(os.path.join(d, n)))

def backupdate(name):
	"""YYMMDD to a date, None if it isn't one"""
	try:
		return date(2000 + int(name[:2]), int(name[2:4]), int(name[4:]))
	except ValueError:
		return None

def backedup(rbdir):
	"""paths, relative to rbdir, of the files a backup copies"""
	files = []
	for root, dirs, names in os.walk(rbdir):
		dirs[:] = sorted(x for x in dirs if not x.startswith("."))
		for n in sorted(names):
			if n.lower().endswith(COPIED):
				files.append(os.path.relpath(os.path.join(root, n), rbdir))
	return files

def makebackup(rbdir, day=None):
	"""back up rbdir into its dump directory, replacing a backup made the same
	day; returns the backup name. The new backup is written aside and only
	takes the place of the old one when it is complete."""
	name = (day or date.today()).strftime("%y%m%d")
	d = dumpdir(rbdir)
	os.makedirs(d, exist_ok=True)
	final = os.path.join(d, name)
	tmp = os.path.join(d, f".{name}.new")
	old = os.path.join(d, f".{name}.old")
	for x in (tmp, old):
		shutil.rmtree(x, ignore_errors=True)
	try:
		for rel in backedup(rbdir):
			dst = os.path.join(tmp, rel)
			os.makedirs(os.path.dirname(dst), exist_ok=True)
			shutil.copy2(os.path.join(rbdir, rel), dst)
		os.makedirs(tmp, exist_ok=True)	# an empty roadbook still gets its backup
		if os.path.exists(final):
			os.rename(final, old)
		os.rename(tmp, final)
	finally:
		shutil.rmtree(tmp, ignore_errors=True)
		shutil.rmtree(old, ignore_errors=True)
	return name

def cleanup(rbdir):
	"""remove all backups but the last one; returns the names removed"""
	gone = backups(rbdir)[:-1]
	for n in gone:
		shutil.rmtree(os.path.join(dumpdir(rbdir), n))
	return gone

def remove(rbdir, name):
	"""delete backup name"""
	if not BACKUPNAME.match(name):
		raise ValueError(f"no backup {name}")
	shutil.rmtree(os.path.join(dumpdir(rbdir), name))

def restore(rbdir, name):
	"""copy the files of backup name back into rbdir, each one replacing
	the file it was copied from. Files made after the backup are left alone."""
	src = os.path.join(dumpdir(rbdir), name)
	if not BACKUPNAME.match(name) or not os.path.isdir(src):
		raise ValueError(f"no backup {name}")
	n = 0
	for rel in backedup(src):
		dst = os.path.join(rbdir, rel)
		os.makedirs(os.path.dirname(dst), exist_ok=True)
		tmp = dst + ".tmp"
		shutil.copy2(os.path.join(src, rel), tmp)
		os.replace(tmp, dst)
		n += 1
	return n

class BackupDialog(QDialog):
	"""back up the roadbook, clean up old backups, or restore one.
	restored is emitted after a restore, so the roadbook can be loaded again."""
	restored = Signal()

	def __init__(self, dwin):
		super().__init__(dwin)
		self.dwin = dwin
		self.rbdir = dwin.rb.dir
		self.setWindowTitle("Backups")
		self.setMinimumWidth(460)

		where = QLabel(f"Backups of <b>{self.rbdir}</b> go in<br><b>{dumpdir(self.rbdir)}</b>, "
			"one per day.")
		where.setWordWrap(True)
		where.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
		self.list = QListWidget()
		self.list.itemSelectionChanged.connect(self.updatebuttons)
		self.list.itemDoubleClicked.connect(lambda _: self.restore())
		self.status = QLabel()
		self.status.setWordWrap(True)

		self.backupb = QPushButton("Back Up Now")
		self.backupb.setDefault(True)
		self.backupb.clicked.connect(self.backup)
		self.restoreb = QPushButton("Restore…")
		self.restoreb.clicked.connect(self.restore)
		self.delb = QPushButton("Del")
		self.delb.setToolTip("delete the selected backup")
		self.delb.clicked.connect(self.delete)
		self.cleanb = QPushButton("Clean Up")
		self.cleanb.setToolTip("remove all backups but the last one")
		self.cleanb.clicked.connect(self.cleanup)
		closeb = QPushButton("Close")
		closeb.clicked.connect(self.accept)

		buttons = QHBoxLayout()
		buttons.addWidget(self.backupb)
		buttons.addWidget(self.restoreb)
		buttons.addWidget(self.delb)
		buttons.addWidget(self.cleanb)
		buttons.addStretch()
		buttons.addWidget(closeb)
		layout = QVBoxLayout(self)
		layout.addWidget(where)
		layout.addWidget(QLabel("Backups, newest first:"))
		layout.addWidget(self.list, 1)
		layout.addWidget(self.status)
		layout.addLayout(buttons)
		self.refresh()

	def refresh(self, select=None):
		self.list.clear()
		for n in reversed(backups(self.rbdir)):
			d = backupdate(n)
			it = QListWidgetItem(f"{n}    {d.strftime('%A %d %B %Y') if d else ''}")
			it.setData(Qt.ItemDataRole.UserRole, n)
			self.list.addItem(it)
			if n == select:
				it.setSelected(True)
		if select is None and self.list.count():
			self.list.item(0).setSelected(True)
		self.updatebuttons()

	def selected(self):
		items = self.list.selectedItems()
		return items[0].data(Qt.ItemDataRole.UserRole) if items else None

	def updatebuttons(self):
		self.restoreb.setEnabled(self.selected() is not None)
		self.delb.setEnabled(self.selected() is not None)
		self.cleanb.setEnabled(self.list.count() > 1)

	def ask(self, title, msg):
		qm = QMessageBox
		return qm.question(self, title, msg, qm.StandardButton.Yes | qm.StandardButton.No,
			qm.StandardButton.No) == qm.StandardButton.Yes

	def backup(self):
		rb = self.dwin.rb
		if rb.dirty:
			qm = QMessageBox
			r = qm.question(self, "Unsaved changes",
				"The roadbook has unsaved changes. Save them before backing up?",
				qm.StandardButton.Save | qm.StandardButton.Ignore | qm.StandardButton.Cancel,
				qm.StandardButton.Save)
			if r == qm.StandardButton.Cancel:
				return
			if r == qm.StandardButton.Save:
				self.dwin.saveroadbook()
		today = date.today().strftime("%y%m%d")
		replacing = today in backups(self.rbdir)
		try:
			name = makebackup(self.rbdir)
		except OSError as e:
			self.status.setText(f"Backup failed: {e}")
			return
		self.refresh(select=name)
		self.status.setText(f"Backed up to {name}" + (", replacing today's earlier backup." if replacing else "."))

	def cleanup(self):
		names = backups(self.rbdir)
		if len(names) < 2:
			return
		if not self.ask("Clean up backups",
				f"Remove {len(names)-1} backup{'s' if len(names) > 2 else ''} and keep only {names[-1]}?"):
			return
		try:
			gone = cleanup(self.rbdir)
		except OSError as e:
			self.status.setText(f"Clean up failed: {e}")
			self.refresh()
			return
		self.refresh()
		self.status.setText(f"Removed {len(gone)} backup{'s' if len(gone) != 1 else ''}; kept {names[-1]}.")

	def delete(self):
		name = self.selected()
		if name is None:
			return
		left = len(backups(self.rbdir)) - 1
		msg = f"Delete backup {name}?"
		if left == 0:
			msg += " It is the only backup."
		if not self.ask("Delete backup", msg):
			return
		try:
			remove(self.rbdir, name)
		except (OSError, ValueError) as e:
			self.status.setText(f"Delete failed: {e}")
			self.refresh()
			return
		self.refresh()
		self.status.setText(f"Deleted {name}.")

	def restore(self):
		name = self.selected()
		if name is None:
			return
		msg = (f"Replace the roadbook's CSV files and graphs with those in backup {name}? "
			"Changes made since then are lost")
		msg += ", including the unsaved ones." if self.dwin.rb.dirty else "."
		if not self.ask("Restore backup", msg):
			return
		try:
			n = restore(self.rbdir, name)
		except (OSError, ValueError) as e:
			self.status.setText(f"Restore failed: {e}")
			return
		self.status.setText(f"Restored {n} files from {name}.")
		self.restored.emit()
