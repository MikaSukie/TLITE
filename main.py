import re
import shutil
import subprocess
from pypresence import Presence
import atexit

from PyQt5.QtWidgets import (
	QApplication, QMainWindow, QTextEdit, QFileDialog, QAction, QInputDialog, QFontDialog, QDesktopWidget, QStatusBar,
	QHBoxLayout, QPushButton, QCheckBox, QLabel, QLineEdit, QVBoxLayout, QWidget, QDockWidget, QDialog, QMessageBox,
	QCompleter, QTreeView, QFileSystemModel, QPlainTextEdit, QTabWidget, QTabBar
)
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QTextBlockFormat, QPainter, QPen, \
	QTextDocument, QTextCursor
from PyQt5.QtCore import QRegExp, pyqtSlot, Qt, QRect, QStringListModel
import sys
import os
import json
import random

IDESTATE = random.randint(0, 5)
global status
if IDESTATE == 1:
	status = "UWAHH! :3"
elif IDESTATE == 2:
	status = ":3"
elif IDESTATE == 3:
	status = "Haii! <3"
elif IDESTATE == 4:
	status = "Lunya :3"
elif IDESTATE == 5:
	status = "cute vibes only!"
else:
	status = "Editing Something..."

def resource_path(relative_path):
	base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
	return os.path.join(base_path, relative_path)


USER_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".tlintite_config")


def get_user_config_path(filename):
	return os.path.join(USER_CONFIG_DIR, filename)


def setup_user_config():
	if not os.path.exists(USER_CONFIG_DIR):
		os.makedirs(USER_CONFIG_DIR, exist_ok=True)
		default_config_dir = resource_path("config")
		for file in os.listdir(default_config_dir):
			src = os.path.join(default_config_dir, file)
			dst = os.path.join(USER_CONFIG_DIR, file)
			if os.path.isfile(src):
				shutil.copyfile(src, dst)

class PlaceholderTab(QWidget):
	def __init__(self):
		super().__init__()
		layout = QVBoxLayout(self)
		label = QLabel("📄 No document open.\nUse 'File > New' or 'Open' to get started.")
		label.setAlignment(Qt.AlignCenter)
		label.setStyleSheet("color: gray; font-size: 16px;")
		layout.addWidget(label)

class KeybindEditorDialog(QDialog):
	def __init__(self, keybinds, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Edit Keybindings")
		self.keybinds = keybinds.copy()
		self.init_ui()

	def init_ui(self):
		layout = QVBoxLayout()

		self.inputs = {}
		for action, key in self.keybinds.items():
			row = QHBoxLayout()
			label = QLabel(action.replace("_", " ").title() + ":")
			input_field = QLineEdit(key)
			self.inputs[action] = input_field
			row.addWidget(label)
			row.addWidget(input_field)
			layout.addLayout(row)

		button_layout = QHBoxLayout()
		save_btn = QPushButton("Save")
		cancel_btn = QPushButton("Cancel")
		save_btn.clicked.connect(self.save)
		cancel_btn.clicked.connect(self.reject)
		button_layout.addWidget(save_btn)
		button_layout.addWidget(cancel_btn)

		layout.addLayout(button_layout)
		self.setLayout(layout)

	def save(self):
		for action, field in self.inputs.items():
			self.keybinds[action] = field.text()
		self.accept()

	def get_keybinds(self):
		return self.keybinds


class EnglishLinter(QSyntaxHighlighter):
	def __init__(self, document, rules_path=get_user_config_path("linting.json")):
		super().__init__(document)
		self.rules_path = rules_path
		self.rules = []
		self.load_rules()

	def load_rules(self):
		try:
			self.rules.clear()
			if os.path.exists(self.rules_path):
				with open(self.rules_path, "r", encoding="utf-8") as file:
					rules_data = json.load(file)
					for rule in rules_data:
						fmt = QTextCharFormat()
						fmt.setForeground(QColor(rule["color"]))
						regex = QRegExp(f"\\b{rule['word']}\\b", Qt.CaseInsensitive)
						self.rules.append((regex, fmt))
			self.rehighlight()
		except Exception as e:
			print(e)

	def highlightBlock(self, text):
		default_format = QTextCharFormat()
		default_format.setForeground(QColor("white"))
		self.setFormat(0, len(text), default_format)

		for pattern, fmt in self.rules:
			index = pattern.indexIn(text)
			while index >= 0:
				length = pattern.matchedLength()
				self.setFormat(index, length, fmt)
				index = pattern.indexIn(text, index + length)

	def get_words(self):
		return [rule['word'] for rule in self.load_rules_from_file()]

	def load_rules_from_file(self):
		try:
			if os.path.exists(self.rules_path):
				with open(self.rules_path, "r", encoding="utf-8") as file:
					return json.load(file)
			return []
		except Exception as e:
			print(e)


class FindReplaceDock(QDockWidget):
	def __init__(self, parent=None):
		super().__init__("Find & Replace", parent)
		self.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)

		container = QWidget()
		layout = QVBoxLayout(container)

		self.find_input = QLineEdit()
		self.find_input.setPlaceholderText("Find...")
		layout.addWidget(QLabel("Find:"))
		layout.addWidget(self.find_input)

		self.replace_input = QLineEdit()
		self.replace_input.setPlaceholderText("Replace with...")
		layout.addWidget(QLabel("Replace:"))
		layout.addWidget(self.replace_input)

		self.case_checkbox = QCheckBox("Case Sensitive")
		layout.addWidget(self.case_checkbox)

		button_layout = QHBoxLayout()
		self.find_button = QPushButton("Find Next")
		self.replace_button = QPushButton("Replace")
		self.replace_all_button = QPushButton("Replace All")
		button_layout.addWidget(self.find_button)
		button_layout.addWidget(self.replace_button)
		button_layout.addWidget(self.replace_all_button)

		layout.addLayout(button_layout)
		self.setWidget(container)


class CustomTextEdit(QTextEdit):
	def __init__(self, plain_paste_callback=None, parent_tab=None, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.parent_tab = parent_tab
		self.get_plain_paste_enabled = plain_paste_callback
		self.completer = QCompleter()
		self.completer.setWidget(self)
		self.completer.setCompletionMode(QCompleter.PopupCompletion)
		self.completer.setCaseSensitivity(False)
		self.completer.activated.connect(self.insertCompletion)
		self.model = QStringListModel()
		self.completer.setModel(self.model)

	def paste(self):
		if self.get_plain_paste_enabled and self.get_plain_paste_enabled():
			clipboard = QApplication.clipboard()
			text = clipboard.text()

			self.insertPlainText(text)
		else:
			super().paste()

	def generateInstaplaceSuggestions(self, word):
		suggestions = set()

		word = word.lower()

		if self.parent_tab and getattr(self.parent_tab, "instaplace_rules", None):
			for rule in self.parent_tab.instaplace_rules:
				find = rule["find"].lower()
				replace = rule["replace"]
				if find.startswith(word) or replace.lower().startswith(word):
					suggestions.add(replace)

		if hasattr(self.parent(), "linter"):
			for lint_word in self.parent().linter.get_words():
				if lint_word.lower().startswith(word):
					suggestions.add(lint_word)

		return list(suggestions)

	def insertCompletion(self, completion):
		tc = self.textCursor()
		extra = len(completion) - len(self.completer.completionPrefix())
		tc.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, len(self.completer.completionPrefix()))
		tc.insertText(completion)
		self.setTextCursor(tc)

	def keyPressEvent(self, event):
		if self.parent_tab and not getattr(self.parent_tab, "suggestions_enabled", True):
			super().keyPressEvent(event)
			self.completer.popup().hide()
			return

		if self.completer.popup().isVisible():
			if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Tab):
				popup = self.completer.popup()
				current_index = popup.currentIndex()
				if current_index.isValid():
					completion = self.model.data(current_index, Qt.DisplayRole)
					if completion:
						event.accept()
						self.insertCompletion(completion)
						self.completer.popup().hide()
						return
			elif event.key() in (Qt.Key_Up, Qt.Key_Down):
				event.ignore()
				return

		super().keyPressEvent(event)

		cursor = self.textCursor()
		cursor.select(QTextCursor.WordUnderCursor)
		current_word = cursor.selectedText().strip()

		if not current_word or current_word.isspace():
			self.completer.popup().hide()
			return

		suggestions = self.generateInstaplaceSuggestions(current_word)

		if suggestions:
			self.model.setStringList(suggestions)
			self.completer.setCompletionPrefix(current_word)
			rect = self.cursorRect()
			popup = self.completer.popup()

			popup_size = popup.sizeHintForColumn(0) + 20
			popup.setFixedWidth(popup_size)

			self.completer.complete(rect)

		else:
			self.completer.popup().hide()

class TextEditorTab(QWidget):
	def __init__(self, get_plain_paste_callback, suggestions_enabled=True, instaplace_rules=None):
		super().__init__()
		layout = QVBoxLayout(self)
		self.editor = CustomTextEdit(plain_paste_callback=get_plain_paste_callback, parent_tab=self)
		self.editor.setFont(QFont("Consolas", 14))
		self.sentence_per_paragraph = 3
		self.editor.textChanged.connect(self.update_counters)
		layout.addWidget(self.editor)
		self.linter = EnglishLinter(self.editor.document())
		self.path = None
		self.suggestions_enabled = suggestions_enabled
		self.instaplace_rules = instaplace_rules or []

	def update_counters(self):
		text = self.editor.toPlainText()
		word_count = len(text.split())
		char_count = len(text)
		sentence_count = text.count('.') + text.count('!') + text.count('?')
		paragraph_count = max(1, sentence_count // self.sentence_per_paragraph)
		return word_count, char_count, paragraph_count

def load_supported_filetypes(path=get_user_config_path("filetypes.json")):
	try:
		if os.path.exists(path):
			with open(path, "r", encoding="utf-8") as f:
				data = json.load(f)
				if isinstance(data, list):
					return set(data)
				else:
					print("filetypes.json is not a list.")
	except Exception as e:
		print("Failed to load supported filetypes:", e)

	return {'.txt', '.tlxt'}
class DiscordRPCManager:
    def __init__(self, client_id, app_name="TLINT Editor"):
        self.client_id = str(client_id)
        self.app_name = app_name
        self.RPC = None
        self.connected = False

    def connect(self):
        try:
            self.RPC = Presence(self.client_id)
            self.RPC.connect()
            self.connected = True
        except Exception as e:
            print("Discord RPC connect failed:", e)
            self.connected = False

    def update(self, filename=None):
        if not self.connected:
            return
        try:
            self.RPC.update(
				state=status,
				details=f'Editing "{filename}"' if filename else "No file open",
				large_image="large",
				large_text="TLINT Editor"
			)
        except Exception as e:
            print("Discord RPC update failed:", e)

    def close(self):
        try:
            if self.RPC:
                try:
                    self.RPC.clear()
                except Exception:
                    pass
                try:
                    self.RPC.close()
                except Exception:
                    pass
        finally:
            self.connected = False

class MainWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		self.setWindowTitle("TLintITE")
		DISCORD_CLIENT_ID = "1433877002783428648"
		self.discord_rpc = DiscordRPCManager(DISCORD_CLIENT_ID, app_name="TLINT Editor")
		self.discord_rpc.connect()
		atexit.register(self.discord_rpc.close)

		self.load_keybinds()

		self.tabs = QTabWidget()
		self.tabs.setTabsClosable(True)
		self.tabs.currentChanged.connect(lambda _: self._update_discord_rpc())
		self.tabs.tabCloseRequested.connect(self.close_tab)
		self.setCentralWidget(self.tabs)

		self.placeholder_tab = None
		self.show_placeholder_tab()

		self.outline_mode = "None"
		if isinstance(self.current_tab(), TextEditorTab):
			editor = self.current_editor()
			if editor:
				editor.viewport().installEventFilter(self)

		self.init_menu()
		self.current_tab().sentence_per_paragraph = 3
		self.setStatusBar(QStatusBar())

		self.instaplace_checkbox = QCheckBox("Instaplace")
		self.instaplace_checkbox.stateChanged.connect(self.toggle_instaplace_checkbox)
		self.statusBar().addPermanentWidget(self.instaplace_checkbox)

		self.suggestion_checkbox = QCheckBox("Suggestions")
		self.suggestion_checkbox.setChecked(False)
		self.suggestion_checkbox.stateChanged.connect(self.toggle_suggestions_checkbox)
		self.statusBar().addPermanentWidget(self.suggestion_checkbox)

		self.suggestions_enabled = False

		editor = self.current_editor()
		if editor:
			editor.textChanged.connect(self.update_counters)
			editor.textChanged.connect(self.apply_instaplace_live)

		self.update_counters()

		self.find_dock = FindReplaceDock(self)

		self.terminal_dock = QDockWidget("Terminal", self)
		self.terminal_dock.setAllowedAreas(Qt.BottomDockWidgetArea)

		terminal_container = QWidget()
		terminal_layout = QVBoxLayout(terminal_container)

		self.terminal_output = QPlainTextEdit()
		self.terminal_output.setReadOnly(True)
		self.terminal_output.setStyleSheet("background-color: #1e1e1e; color: white;")

		self.terminal_input = QLineEdit()
		self.terminal_input.setPlaceholderText("Enter command...")
		self.terminal_input.returnPressed.connect(self.run_terminal_command)

		terminal_layout.addWidget(self.terminal_output)
		terminal_layout.addWidget(self.terminal_input)

		self.terminal_dock.setWidget(terminal_container)
		self.addDockWidget(Qt.BottomDockWidgetArea, self.terminal_dock)

		self.addDockWidget(Qt.BottomDockWidgetArea, self.find_dock)
		self.find_dock.hide()
		self.find_dock.find_button.clicked.connect(lambda: self.find_text_docked(self.find_dock))
		self.find_dock.replace_button.clicked.connect(lambda: self.replace_text(self.find_dock))
		self.find_dock.replace_all_button.clicked.connect(lambda: self.replace_all_text(self.find_dock))

		self.instaplace_enabled = False
		self.instaplace_rules = []
		self.load_instaplace_rules()

		self.plain_paste_checkbox = QCheckBox("Clean Paste")
		self.statusBar().addPermanentWidget(self.plain_paste_checkbox)

		self.current_file_path = None

		self.supported_filetypes = load_supported_filetypes()

	def _update_discord_rpc(self):
		tab = self.current_tab()
		filename = None
		if isinstance(tab, TextEditorTab) and getattr(tab, "path", None):
			filename = os.path.basename(tab.path)
		elif isinstance(tab, TextEditorTab):
			filename = "Untitled"
		self.discord_rpc.update(filename)

	def _wire_up_editor(self, editor: CustomTextEdit):
		editor.textChanged.connect(self.update_counters)
		editor.textChanged.connect(self.apply_instaplace_live)

	def show_placeholder_tab(self):
		if self.placeholder_tab is not None:
			return

		self.placeholder_tab = PlaceholderTab()
		index = self.tabs.addTab(self.placeholder_tab, "Welcome")
		self.tabs.setCurrentIndex(index)

		self.tabs.tabBar().setTabButton(index, QTabBar.RightSide, None)

	def remove_placeholder_tab(self):
		index = self.tabs.indexOf(self.placeholder_tab)
		if index != -1:
			self.tabs.removeTab(index)
		self.placeholder_tab = None

	def paste(self):
		if self.get_plain_paste_enabled and self.get_plain_paste_enabled():
			clipboard = QApplication.clipboard()
			text = clipboard.text()

			self.insertPlainText(text)
		else:
			super().paste()

	def toggle_suggestions_checkbox(self, state):
		self.suggestions_enabled = state == Qt.Checked
		for i in range(self.tabs.count()):
			tab = self.tabs.widget(i)
			if isinstance(tab, TextEditorTab):
				tab.instaplace_rules = self.instaplace_rules if self.instaplace_enabled else []
				tab.suggestions_enabled = self.suggestions_enabled

	def reload_all_rules(self):
		try:
			self.reload_rules()
			self.reload_instaplace()
		except Exception as e:
			print(e)
			QMessageBox.information(self, "Error:", e)

	def run_terminal_command(self):
		command = self.terminal_input.text().strip()
		if not command:
			return

		if command.lower() == "clear" or command.lower() == "cls":
			self.terminal_output.clear()
			self.terminal_input.clear()
			return

		self.terminal_output.appendPlainText(f"> {command}")

		try:
			result = subprocess.run(
				command, shell=True, check=False,
				stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
			)
			output = result.stdout.strip()
			error = result.stderr.strip()

			if output:
				self.terminal_output.appendPlainText(output)
			if error:
				self.terminal_output.appendPlainText(f"[stderr]\n{error}")

		except Exception as e:
			self.terminal_output.appendPlainText(f"[error] {str(e)}")

		self.terminal_input.clear()

	def init_menu(self):
		menu_bar = self.menuBar()

		file_menu = menu_bar.addMenu("File")
		edit_menu = menu_bar.addMenu("Edit")
		docs_menu = menu_bar.addMenu("Docs")
		outlines_menu = menu_bar.addMenu("Outlines")
		window_menu = menu_bar.addMenu("Window")

		open_action = QAction("Open", self)
		open_action.setObjectName("open_action")
		open_action.triggered.connect(self.open_file)

		save_action = QAction("Save", self)
		save_action.setObjectName("save_action")
		save_action.triggered.connect(self.save_file)

		save_as_action = QAction("Save As", self)
		save_as_action.setObjectName("save_as_action")
		save_as_action.triggered.connect(self.save_as_file)

		new_action = QAction("New", self)
		new_action.setObjectName("new_action")
		new_action.triggered.connect(self.new_document)

		file_menu.addAction(new_action)
		file_menu.addAction(open_action)
		file_menu.addAction(save_as_action)
		file_menu.addAction(save_action)

		save_raw_action = QAction("Save (Raw)", self)
		save_raw_action.triggered.connect(self.save_raw_file)
		save_raw_action.setObjectName("save_raw_action")
		save_raw_action.setShortcut(self.keybinds.get("save_raw_file", "Ctrl+Alt+S"))
		file_menu.addAction(save_raw_action)

		reload_all_action = QAction("Reload All Rules", self)
		reload_all_action.setObjectName("reload_all_action")
		reload_all_action.triggered.connect(self.reload_all_rules)
		edit_menu.addAction(reload_all_action)

		reload_rules_action = QAction("Reload Linter Rules", self)
		reload_rules_action.setObjectName("reload_rules_action")
		reload_rules_action.triggered.connect(self.reload_rules)

		font_action = QAction("Change Font", self)
		font_action.setObjectName("font_action")
		font_action.triggered.connect(self.change_font)

		font_size_action = QAction("Change Font Size", self)
		font_size_action.setObjectName("font_size_action")
		font_size_action.triggered.connect(self.change_font_size)

		line_spacing_action = QAction("Change Line Spacing", self)
		line_spacing_action.setObjectName("line_spacing_action")
		line_spacing_action.triggered.connect(self.change_line_spacing)

		none_action = QAction("None", self)
		none_action.setObjectName("none_action")
		none_action.triggered.connect(lambda: self.set_outline("None"))

		a4_action = QAction("A4", self)
		a4_action.setObjectName("a4_action")
		a4_action.triggered.connect(lambda: self.set_outline("A4"))

		iso216_action = QAction("ISO216", self)
		iso216_action.setObjectName("iso216_action")
		iso216_action.triggered.connect(lambda: self.set_outline("ISO216"))

		outlines_menu.addAction(none_action)
		outlines_menu.addAction(a4_action)
		outlines_menu.addAction(iso216_action)

		find_action = QAction("Find & Replace", self)
		find_action.setObjectName("find_action")
		find_action.triggered.connect(self.toggle_find_replace)
		edit_menu.addAction(find_action)

		edit_keybinds_action = QAction("Edit Keybindings", self)
		edit_keybinds_action.setObjectName("edit_keybinds_action")
		edit_keybinds_action.triggered.connect(self.edit_keybindings)
		edit_menu.addAction(edit_keybinds_action)

		toggle_suggestions_action = QAction("Toggle Suggestions", self)
		toggle_suggestions_action.setObjectName("toggle_suggestions_action")
		toggle_suggestions_action.triggered.connect(self.toggle_suggestions)
		edit_menu.addAction(toggle_suggestions_action)
		editor = self.current_editor()
		if editor:
			editor.addAction(toggle_suggestions_action)

		reload_keybinds_action = QAction("Reload Keybindings", self)
		reload_keybinds_action.setObjectName("reload_keybinds_action")
		reload_keybinds_action.triggered.connect(lambda: (self.load_keybinds(), self.init_menu()))
		edit_menu.addAction(reload_keybinds_action)

		toggle_instaplace_action = QAction("Toggle Instaplace (Live Replace)", self)
		toggle_instaplace_action.setObjectName("toggle_instaplace_action")
		toggle_instaplace_action.triggered.connect(self.toggle_instaplace)

		reload_instaplace_action = QAction("Reload Instaplace Rules", self)
		reload_instaplace_action.setObjectName("reload_instaplace_action")
		reload_instaplace_action.triggered.connect(self.reload_instaplace)
		edit_menu.addAction(toggle_instaplace_action)
		edit_menu.addAction(reload_instaplace_action)
		edit_menu.addAction(reload_rules_action)

		paragraph_settings_action = QAction("Set Paragraph Sentence Count", self)
		paragraph_settings_action.setObjectName("paragraph_settings_action")
		paragraph_settings_action.triggered.connect(self.set_paragraph_settings)
		docs_menu.addAction(paragraph_settings_action)
		docs_menu.addAction(font_action)
		docs_menu.addAction(font_size_action)
		docs_menu.addAction(line_spacing_action)

		show_terminal_action = QAction("Show Terminal", self)
		show_terminal_action.triggered.connect(lambda: self.terminal_dock.show())
		window_menu.addAction(show_terminal_action)

		show_file_browser_action = QAction("Show File Explorer", self)
		show_file_browser_action.triggered.connect(lambda: self.file_browser.show())
		window_menu.addAction(show_file_browser_action)

		self.file_browser = QDockWidget("File Browser", self)
		self.file_model = QFileSystemModel()
		self.file_model.setRootPath(os.path.expanduser("~"))

		self.tree_view = QTreeView()
		self.tree_view.setModel(self.file_model)
		self.tree_view.setRootIndex(self.file_model.index(os.path.expanduser("~")))
		self.tree_view.doubleClicked.connect(self.open_file_from_browser)

		self.file_browser.setWidget(self.tree_view)
		self.addDockWidget(Qt.LeftDockWidgetArea, self.file_browser)

		open_action.setShortcut(self.keybinds.get("open_file", "Ctrl+O"))
		save_action.setShortcut(self.keybinds.get("save_file", "Ctrl+S"))
		save_as_action.setShortcut(self.keybinds.get("save_as_file", "Ctrl+Shift+S"))
		new_action.setShortcut(self.keybinds.get("new_file", "Ctrl+N"))
		reload_all_action.setShortcut(self.keybinds.get("reload_all_rules", "Ctrl+Shift+R"))
		reload_rules_action.setShortcut(self.keybinds.get("reload_rules", "Ctrl+R"))
		reload_instaplace_action.setShortcut(self.keybinds.get("reload_instaplace", "Ctrl+Shift+I"))
		find_action.setShortcut(self.keybinds.get("find_replace", "Ctrl+F")),
		toggle_instaplace_action.setShortcut(self.keybinds.get("toggle_instaplace", "Ctrl+W"))
		toggle_suggestions_action.setShortcut(self.keybinds.get("toggle_suggestions", "Ctrl+E"))

	def toggle_find_replace(self):
		if self.find_dock.isVisible():
			self.find_dock.hide()
		else:
			self.find_dock.show()
			self.find_dock.find_input.setFocus()

	def current_tab(self) -> TextEditorTab:
		return self.tabs.currentWidget()

	def current_editor(self) -> CustomTextEdit:
		tab = self.current_tab()
		return tab.editor if tab else None

	def current_linter(self) -> EnglishLinter:
		tab = self.current_tab()
		return tab.linter if tab else None

	def close_tab(self, index):
		if self.tabs.widget(index) == self.placeholder_tab:
			return
		widget = self.tabs.widget(index)
		self.tabs.removeTab(index)

		if widget:
			widget.deleteLater()

		if self.tabs.count() == 0:
			self.show_placeholder_tab()

	def save_raw_file(self):
		try:
			tab = self.current_tab()
			if tab and isinstance(tab, TextEditorTab) and tab.path:
				with open(tab.path, "w", encoding="utf-8") as file:
					file.write(tab.editor.toPlainText())
			else:
				QMessageBox.information(self, "No path", "No file path is set for this tab.")
		except Exception as e:
			print(e)
			QMessageBox.information(self, "Error:", str(e))

	def load_keybinds(self, path=get_user_config_path("keybind.json")):
		default_binds = {
			"new_file": "Ctrl+N",
			"open_file": "Ctrl+O",
			"save_file": "Ctrl+S",
			"save_as_file": "Ctrl+Shift+S",
			"reload_rules": "Ctrl+L",
			"reload_all_rules": "Ctrl+R",
			"reload_instaplace": "Ctrl+I",
			"find_replace": "Ctrl+F",
			"toggle_instaplace": "Ctrl+W",

			"edit_keybindings": "None",
			"reload_keybinds": "None",
			"set_paragraph_settings": "None",
			"change_font": "None",
			"change_font_size": "None",
			"change_line_spacing": "None",
			"outline_none": "None",
			"outline_a4": "None",
			"outline_iso216": "None",
			"toggle_suggestions": "Ctrl+E",
			"save_raw_file": "Ctrl+Alt+S"
		}

		if os.path.exists(path):
			try:
				with open(path, "r", encoding="utf-8") as f:
					binds = json.load(f)
					default_binds.update(binds)
			except Exception as e:
				QMessageBox.information(self, "Keybindings Failed to load", e)
		self.keybinds = default_binds

	def apply_keybinds(self):
		actions = [
			("open_file", self.findChild(QAction, "open_action")),
			("save_file", self.findChild(QAction, "save_action")),
			("save_as_file", self.findChild(QAction, "save_as_action")),
			("new_file", self.findChild(QAction, "new_action")),
			("reload_all_rules", self.findChild(QAction, "reload_all_action")),
			("reload_rules", self.findChild(QAction, "reload_rules_action")),
			("reload_instaplace", self.findChild(QAction, "reload_instaplace_action")),
			("find_replace", self.findChild(QAction, "find_action")),
			("toggle_instaplace", self.findChild(QAction, "toggle_instaplace_action")),

			("edit_keybindings", self.findChild(QAction, "edit_keybinds_action")),
			("reload_keybinds", self.findChild(QAction, "reload_keybinds_action")),
			("set_paragraph_settings", self.findChild(QAction, "paragraph_settings_action")),
			("change_font", self.findChild(QAction, "font_action")),
			("change_font_size", self.findChild(QAction, "font_size_action")),
			("change_line_spacing", self.findChild(QAction, "line_spacing_action")),
			("outline_none", self.findChild(QAction, "none_action")),
			("outline_a4", self.findChild(QAction, "a4_action")),
			("outline_iso216", self.findChild(QAction, "iso216_action")),
			("toggle_suggestions", self.findChild(QAction, "toggle_suggestions_action")),
			("save_raw_file", self.findChild(QAction, "save_raw_action"))
		]
		for key, action in actions:
			if action:
				shortcut = self.keybinds.get(key)
				if shortcut and shortcut.lower() != "none":
					action.setShortcut(shortcut)

	def toggle_instaplace_checkbox(self, state):
		self.instaplace_enabled = state == Qt.Checked
		for i in range(self.tabs.count()):
			tab = self.tabs.widget(i)
			if isinstance(tab, TextEditorTab):
				tab.instaplace_rules = self.instaplace_rules if self.instaplace_enabled else []
				editor = self.current_editor()
				if editor and not self.instaplace_enabled:
					editor.completer.popup().hide()

	def edit_keybindings(self):
		try:
			dialog = KeybindEditorDialog(self.keybinds, self)
			if dialog.exec_() == QDialog.Accepted:
				self.keybinds = dialog.get_keybinds()
				with open(get_user_config_path("keybind.json"), "w", encoding="utf-8") as f:
					json.dump(self.keybinds, f, indent=4)
				self.apply_keybinds()
				QMessageBox.information(self, "Keybindings Updated", "Keybindings were updated and applied.")
		except Exception as e:
			print(e)
			QMessageBox.information(self, "Error:", e)

	def toggle_suggestions(self):
		current = getattr(self, "suggestions_enabled", True)
		self.suggestions_enabled = not current
		self.suggestion_checkbox.setChecked(self.suggestions_enabled)

	def find_text_docked(self, dock):
		text = dock.find_input.text()
		if not text:
			return
		flags = QTextDocument.FindFlags()
		if dock.case_checkbox.isChecked():
			flags |= QTextDocument.FindCaseSensitively

		cursor = self.current_editor().textCursor()
		found = self.current_editor().document().find(text, cursor, flags)
		if found.isNull():
			found = self.current_editor().document().find(text, QTextCursor(), flags)

		if not found.isNull():
			self.current_editor().setTextCursor(found)
			self.current_editor().setFocus()

	def new_document(self):
		tab = TextEditorTab(
			lambda: self.plain_paste_checkbox.isChecked(),
			suggestions_enabled=self.suggestions_enabled,
			instaplace_rules=self.instaplace_rules if self.instaplace_enabled else []
		)
		self._wire_up_editor(tab.editor)

		index = self.tabs.addTab(tab, "Untitled")
		self.tabs.setCurrentIndex(index)
		self.update_counters()
		self._update_discord_rpc()

	def replace_text(self, dock):
		cursor = self.current_editor().textCursor()
		if cursor.hasSelection() and cursor.selectedText() == dock.find_input.text():
			cursor.insertText(dock.replace_input.text())
		self.find_text_docked(dock)

	def current_tab(self):
		return self.tabs.currentWidget()

	def current_editor(self):
		tab = self.current_tab()
		return tab.editor if isinstance(tab, TextEditorTab) else None

	def load_instaplace_rules(self, path=get_user_config_path("instaplace.json")):
		try:
			self.instaplace_rules.clear()
			if os.path.exists(path):
				with open(path, "r", encoding="utf-8") as file:
					self.instaplace_rules = json.load(file)
		except Exception as e:
			print(e)
			QMessageBox.information(self, "Error:", e)

	def apply_instaplace_live(self):
		if not self.instaplace_enabled:
			return

		cursor = self.current_editor().textCursor()
		cursor.select(QTextCursor.WordUnderCursor)
		word = cursor.selectedText()

		for rule in self.instaplace_rules:
			if word == rule["find"]:
				cursor.insertText(rule["replace"])
				break

	def toggle_instaplace(self):
		self.instaplace_checkbox.setChecked(not self.instaplace_checkbox.isChecked())

	def reload_instaplace(self):
		self.load_instaplace_rules()
		if hasattr(self, 'instaplace_enabled') and self.instaplace_enabled:
			for i in range(self.tabs.count()):
				tab = self.tabs.widget(i)
				if isinstance(tab, TextEditorTab):
					tab.instaplace_rules = self.instaplace_rules

	def replace_all_text(self, dock):
		text = dock.find_input.text()
		replacement = dock.replace_input.text()
		if not text:
			return

		flags = Qt.CaseSensitive if dock.case_checkbox.isChecked() else Qt.CaseInsensitive
		content = self.current_editor().toPlainText()
		new_content = content.replace(text, replacement) if flags == Qt.CaseSensitive else re.sub(re.escape(text),
																								  replacement, content,
																								  flags=re.IGNORECASE)
		self.current_editor().setPlainText(new_content)

	def set_outline(self, mode):
		self.outline_mode = mode
		self.current_editor().viewport().update()

	def eventFilter(self, obj, event):
		if obj == self.current_editor().viewport() and event.type() == event.Paint:
			result = super().eventFilter(obj, event)
			self.draw_outline()
			return result
		return super().eventFilter(obj, event)

	def update_counters(self):
		editor = self.current_editor()
		tab = self.current_tab()

		if not editor or not isinstance(tab, TextEditorTab):
			self.statusBar().showMessage("No document open")
			return

		text = editor.toPlainText()
		word_count = len(text.split())
		char_count = len(text)
		sentence_count = text.count('.') + text.count('!') + text.count('?')
		paragraph_count = max(1,
							  sentence_count // tab.sentence_per_paragraph) if tab.sentence_per_paragraph > 0 else 1

		self.statusBar().showMessage(
			f"Words: {word_count} | Characters: {char_count} | Paragraphs (est.): {paragraph_count}")

	def set_paragraph_settings(self):
		value, ok = QInputDialog.getInt(self, "Paragraph Settings", "How many sentences per paragraph?",
										self.current_tab().sentence_per_paragraph, 1, 20)
		if ok:
			self.current_tab().sentence_per_paragraph = value
			self.update_counters()

	def draw_outline(self):
		editor = self.current_editor()
		if not editor:
			return
		painter = QPainter(editor.viewport())
		pen = QPen(Qt.magenta, 2, Qt.DashLine)
		painter.setPen(pen)

		dpi = self.logicalDpiX()

		if self.outline_mode == "A4":
			width_in, height_in = 8.27, 11.69
		elif self.outline_mode == "ISO216":
			width_in, height_in = 9.84, 13.9
		else:
			return

		width_px = int(width_in * dpi)
		height_px = int(height_in * dpi)

		rect = QRect(0, 0, min(width_px, self.current_editor().viewport().width()),
					 min(height_px, self.current_editor().viewport().height()))
		painter.drawRect(rect)

	def change_font(self):
		current_font = self.current_editor().font()
		font, ok = QFontDialog.getFont(current_font, self, "Select Font")
		if ok:
			self.current_editor().setFont(font)

	def change_font_size(self):
		current_font = self.current_editor().font()
		size, ok = QInputDialog.getInt(self, "Font Size", "Enter font size:", current_font.pointSize(), 6, 72)
		if ok:
			current_font.setPointSize(size)
			self.current_editor().setFont(current_font)

	def change_line_spacing(self):
		cursor = self.current_editor().textCursor()
		block_format = cursor.blockFormat()

		spacing, ok = QInputDialog.getDouble(self, "Line Spacing",
											 "Enter line spacing multiplier (e.g., 1.0 = normal):",
											 block_format.lineHeight() / 100.0 if block_format.lineHeight() else 1.0,
											 0.5, 5.0, 1)
		if ok:
			block_format.setLineHeight(spacing * 100, QTextBlockFormat.ProportionalHeight)
			cursor.setBlockFormat(block_format)

	def open_file_from_browser(self, index):
		if hasattr(self, 'placeholder_tab') and self.placeholder_tab:
			self.remove_placeholder_tab()
		try:
			path = self.file_model.filePath(index)
			if os.path.isfile(path):
				ext = os.path.splitext(path)[1].lower()
				if ext not in self.supported_filetypes:
					QMessageBox.warning(self, "Unsupported File", f"File type '{ext}' is not supported.")
					return

				try:
					with open(path, 'r', encoding='utf-8') as file:
						full_text = file.read()
				except UnicodeDecodeError:
					QMessageBox.warning(self, "Error", "Cannot open file: Not a valid UTF-8 text file.")
					return

				tab = TextEditorTab(
					lambda: self.plain_paste_checkbox.isChecked(),
					suggestions_enabled=self.suggestions_enabled,
					instaplace_rules=self.instaplace_rules if self.instaplace_enabled else []
				)
				self._wire_up_editor(tab.editor)

				tab.path = path
				tab_name = os.path.basename(path)

				index = self.tabs.addTab(tab, tab_name)
				self.tabs.setCurrentIndex(index)

				tab.path = path
				tab_name = os.path.basename(path)

				settings_match = re.search(
					r"<__s-e-t-t-i-n-g-s__>\s*(\{.*?\})\s*</__s-e-t-t-i-n-g-s__>",
					full_text, re.DOTALL
				)

				if settings_match:
					settings_str = settings_match.group(1)
					content_start = settings_match.end()
					content = full_text[content_start:].lstrip()
					tab.editor.setPlainText(content)
				else:
					tab.editor.setPlainText(full_text)

				index = self.tabs.addTab(tab, tab_name)
				self.tabs.setCurrentIndex(index)

				if settings_match:
					try:
						settings = json.loads(settings_str)
						font_family = settings.get("font_family", "Consolas")
						font_size = settings.get("font_size", 14)
						font = QFont(font_family, font_size)
						tab.editor.setFont(font)
						tab.editor.document().setDefaultFont(font)
						tab.sentence_per_paragraph = settings.get("sentence_per_paragraph", 3)

						spacing = settings.get("line_spacing", 1.0)
						cursor = tab.editor.textCursor()
						cursor.beginEditBlock()
						block = tab.editor.document().firstBlock()
						while block.isValid():
							cursor.setPosition(block.position())
							cursor.select(QTextCursor.BlockUnderCursor)
							fmt = cursor.blockFormat()
							fmt.setLineHeight(spacing * 100, QTextBlockFormat.ProportionalHeight)
							cursor.setBlockFormat(fmt)
							block = block.next()
						cursor.endEditBlock()
					except Exception as e:
						print("Failed to apply settings:", e)

				self.update_counters()
				self._update_discord_rpc()

		except Exception as e:
			print(e)
			QMessageBox.information(self, "Error:", str(e))

	def open_file(self):
		if hasattr(self, 'placeholder_tab') and self.placeholder_tab:
			self.remove_placeholder_tab()
		try:
			path, _ = QFileDialog.getOpenFileName(
				self, "Open File", "",
				"Text Files (*.txt *.tlxt *.py *.md *.json *.csv *.java *.class *.rs *.cpp *.css *.js *.html *.c *.cs);;All Files (*)"
			)
			if path:
				ext = os.path.splitext(path)[1].lower()
				if ext not in self.supported_filetypes:
					QMessageBox.warning(self, "Unsupported File", f"File type '{ext}' is not supported.")
					return

				try:
					with open(path, 'r', encoding='utf-8') as file:
						full_text = file.read()
				except UnicodeDecodeError:
					QMessageBox.warning(self, "Error", "Cannot open file: Not a valid UTF-8 text file.")
					return

				self.current_file_path = path

				tab = TextEditorTab(
					lambda: self.plain_paste_checkbox.isChecked(),
					suggestions_enabled=self.suggestions_enabled,
					instaplace_rules=self.instaplace_rules if self.instaplace_enabled else []
				)

				tab.path = path
				tab_name = os.path.basename(path)

				settings_match = re.search(
					r"<__s-e-t-t-i-n-g-s__>\s*(\{.*?\})\s*</__s-e-t-t-i-n-g-s__>",
					full_text, re.DOTALL
				)

				if settings_match:
					settings_str = settings_match.group(1)
					content_start = settings_match.end()
					content = full_text[content_start:].lstrip()
					tab.editor.setPlainText(content)
				else:
					tab.editor.setPlainText(full_text)

				index = self.tabs.addTab(tab, tab_name)
				self.tabs.setCurrentIndex(index)

				if settings_match:
					try:
						settings = json.loads(settings_str)
						font_family = settings.get("font_family", "Consolas")
						font_size = settings.get("font_size", 14)
						font = QFont(font_family, font_size)
						tab.editor.setFont(font)
						tab.editor.document().setDefaultFont(font)
						tab.sentence_per_paragraph = settings.get("sentence_per_paragraph", 3)

						spacing = settings.get("line_spacing", 1.0)
						cursor = tab.editor.textCursor()
						cursor.beginEditBlock()
						block = tab.editor.document().firstBlock()
						while block.isValid():
							cursor.setPosition(block.position())
							cursor.select(QTextCursor.BlockUnderCursor)
							fmt = cursor.blockFormat()
							fmt.setLineHeight(spacing * 100, QTextBlockFormat.ProportionalHeight)
							cursor.setBlockFormat(fmt)
							block = block.next()
						cursor.endEditBlock()
					except Exception as e:
						print("Failed to apply settings:", e)

				self.update_counters()
				self._update_discord_rpc()
		except Exception as e:
			print(e)
			QMessageBox.information(self, "Error:", str(e))

	def save_file(self):
		try:
			tab = self.current_tab()
			if tab and isinstance(tab, TextEditorTab) and tab.path:
				self._save_to_path(tab.path)
				self._update_discord_rpc()
			else:
				QMessageBox.information(self, "No path", "No file path is set for this tab.")
		except Exception as e:
			print(e)
			QMessageBox.information(self, "Error:", str(e))

	def save_as_file(self):
		try:
			path, _ = QFileDialog.getSaveFileName(self, "Save As", "", "TLintITE Files (*.tlxt)")
			if path:
				if not path.endswith('.tlxt'):
					path += '.tlxt'
				self.current_file_path = path
				self._save_to_path(path)
				self._update_discord_rpc()
		except Exception as e:
			print(e)
			QMessageBox.information(self, "Error:", e)

	def _save_to_path(self, path):
		try:
			settings = {
				"font_family": self.current_editor().font().family(),
				"font_size": self.current_editor().font().pointSize(),
				"sentence_per_paragraph": self.current_tab().sentence_per_paragraph,
				"line_spacing": self._get_line_spacing()
			}

			content = self.current_editor().toPlainText()
			data = f"<__s-e-t-t-i-n-g-s__>\n{json.dumps(settings, indent=2)}\n</__s-e-t-t-i-n-g-s__>\n{content}"

			with open(path, "w", encoding="utf-8") as file:
				file.write(data)
			self._update_discord_rpc()
		except Exception as e:
			print(e)
			QMessageBox.information(self, "Error:", str(e))

	def _apply_settings(self, settings):
		try:
			font_family = settings.get("font_family", "Consolas")
			font_size = settings.get("font_size", 14)
			font = QFont(font_family, font_size)
			self.current_editor().setFont(font)

			self.current_tab().sentence_per_paragraph = settings.get("sentence_per_paragraph", 3)

			spacing = settings.get("line_spacing", 1.0)
			cursor = self.current_editor().textCursor()
			cursor.beginEditBlock()

			doc = self.current_editor().document()
			block = doc.firstBlock()

			while block.isValid():
				cursor.setPosition(block.position())
				cursor.select(QTextCursor.BlockUnderCursor)
				block_format = cursor.blockFormat()
				block_format.setLineHeight(spacing * 100, QTextBlockFormat.ProportionalHeight)
				cursor.setBlockFormat(block_format)
				block = block.next()

			cursor.endEditBlock()

			self.update_counters()
		except Exception as e:
			print("Error applying settings:", e)

	def closeEvent(self, event):
		try:
			if getattr(self, "discord_rpc", None):
				self.discord_rpc.close()
		except Exception:
			pass
		super().closeEvent(event)

	@staticmethod
	def strip_settings_tag(text):
		return re.sub(r"<__s-e-t-t-i-n-g-s__>.*?</__s-e-t-t-i-n-g-s__>", "", text, flags=re.DOTALL)

	def _get_line_spacing(self):
		cursor = self.current_editor().textCursor()
		block_format = cursor.blockFormat()
		line_height = block_format.lineHeight()
		return (line_height / 100.0) if line_height > 0 else 1.0

	@pyqtSlot()
	def reload_rules(self):
		self.current_linter().load_rules()
		self.supported_filetypes = load_supported_filetypes()

if __name__ == "__main__":
	setup_user_config()
	app = QApplication(sys.argv)

	theme_path = get_user_config_path("theme.qss")
	if os.path.exists(theme_path):
		try:
			with open(theme_path, "r", encoding="utf-8") as file:
				app.setStyleSheet(file.read())
		except Exception as e:
			print("Could not apply stylesheet:", e)

	window = MainWindow()
	window.resize(1540, 900)
	window.show()
	try:
		window._update_discord_rpc()
	except Exception:
		pass
	sys.exit(app.exec_())
