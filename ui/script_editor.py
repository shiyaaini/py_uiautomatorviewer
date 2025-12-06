import os
from typing import Optional, Dict
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, 
    QPlainTextEdit, QToolBar, QMessageBox, QSplitter, QFileDialog, QApplication,
    QCompleter, QListView, QTextEdit
)
from PyQt5.QtCore import Qt, QEvent, QStringListModel, QRect, QSize
from PyQt5.QtGui import QFont, QTextCursor, QStandardItemModel, QStandardItem, QPainter, QColor, QTextFormat

from core.doc_parser import DocParser
from ui.syntax_highlighter import JSHighlighter


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)

class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Consolas", 11))
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        
        self.updateLineNumberAreaWidth(0)
        
        self.completer: Optional[QCompleter] = None
        self.highlighter: Optional[JSHighlighter] = None
        self.api_data = {}

    def lineNumberAreaWidth(self):
        digits = 1
        max_val = max(1, self.blockCount())
        while max_val >= 10:
            max_val //= 10
            digits += 1
        
        space = 3 + self.fontMetrics().width('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            lineColor = QColor(Qt.yellow).lighter(160)
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), Qt.lightGray)

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(Qt.black)
                painter.drawText(0, top, self.lineNumberArea.width(), self.fontMetrics().height(),
                                 Qt.AlignRight, number)
            
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            blockNumber += 1

    def set_api_data(self, data: Dict):
        self.api_data = data
        # Initialize/Update highlighter with API keys
        api_keys = list(data.keys())
        self.highlighter = JSHighlighter(self.document(), api_keys)

    def _collect_variables_up_to_cursor(self):
        """Collect variable and function names in the whole document.

        Heuristic:
        - Lines starting with `var/let/const` define variables
        - Lines starting with `function name(` define functions
        - Lines like `name = ...` at column 0 are treated as assignments to a variable
        - Indentation == 0 -> treat as global, otherwise as local
        """
        import re

        text = self.toPlainText()
        lines = text.splitlines()
        cursor = self.textCursor()
        current_line = cursor.blockNumber()

        local_vars = set()
        global_vars = set()

        var_decl_re = re.compile(r"^\s*(var|let|const)\s+(.+?);?\s*$")
        func_decl_re = re.compile(r"^\s*function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(")
        assign_re = re.compile(r"^\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*=(?!=)")

        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue

            indent = len(line) - len(line.lstrip(" \t"))

            # function declarations
            m_func = func_decl_re.match(line)
            if m_func:
                name = m_func.group(1)
                (global_vars if indent == 0 else local_vars).add(name)

            # var/let/const declarations (support multiple, e.g. "let a = 1, b = 2;")
            m = var_decl_re.match(line)
            if m:
                rest = m.group(2)
                for part in rest.split(","):
                    part = part.strip()
                    if not part:
                        continue
                    m_name = re.match(r"^([A-Za-z_$][A-Za-z0-9_$]*)", part)
                    if m_name:
                        name = m_name.group(1)
                        (global_vars if indent == 0 else local_vars).add(name)

            # Simple assignments at start of line: foo = ...
            # (covers globals created by direct assignment without var/let/const)
            m_assign = assign_re.match(line)
            if m_assign:
                name = m_assign.group(1)
                (global_vars if indent == 0 else local_vars).add(name)

        return local_vars, global_vars

    def set_completer(self, completer: QCompleter):
        if self.completer:
            self.completer.disconnect(self)
        
        self.completer = completer
        if not self.completer:
            return

        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.activated.connect(self.insert_completion)

    def insert_completion(self, completion: str):
        if self.completer.widget() != self:
            return
        
        tc = self.textCursor()
        extra = len(completion) - len(self.completer.completionPrefix())
        tc.movePosition(QTextCursor.Left)
        tc.movePosition(QTextCursor.EndOfWord)
        tc.insertText(completion[-extra:])
        self.setTextCursor(tc)

    def text_under_cursor(self):
        tc = self.textCursor()
        tc.select(QTextCursor.WordUnderCursor)
        return tc.selectedText()

    def keyPressEvent(self, event):
        if self.completer and self.completer.popup().isVisible():
            # Let the completer handle these keys if popup is visible
            if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape, Qt.Key_Tab, Qt.Key_Backtab):
                event.ignore()
                return
        
        is_shortcut = (event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Space)
        
        # Smart Indentation logic (preserve existing)
        if event.key() == Qt.Key_Return:
            cursor = self.textCursor()
            block = cursor.block()
            text = block.text()
            indentation = ""
            for char in text:
                if char == ' ' or char == '\t':
                    indentation += char
                else:
                    break
            if text.strip().endswith('{') or text.strip().endswith(':') or text.strip().endswith('['):
                indentation += "    "
            super().keyPressEvent(event)
            self.insertPlainText(indentation)
            return # Don't process completion for Enter
        
        if event.text() == "}":
            cursor = self.textCursor()
            block = cursor.block()
            text = block.text()
            pos = cursor.positionInBlock()
            leading = 0
            for ch in text:
                if ch == ' ' or ch == '\t':
                    leading += 1
                else:
                    break
            if pos <= leading and leading >= 4:
                cursor.beginEditBlock()
                cursor.movePosition(QTextCursor.StartOfBlock)
                for _ in range(4):
                    cursor.deleteChar()
                cursor.endEditBlock()
            super().keyPressEvent(event)
            return
        
        super().keyPressEvent(event)
        
        if not self.completer:
            return

        ctrl_or_shift = event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)
        if not self.completer or (not is_shortcut and ctrl_or_shift and not event.text()):
            return

        # Logic to decide what to show
        # 1. Check if we are after a dot
        # 2. Check if we are typing a word
        
        cursor = self.textCursor()
        # Get current line up to cursor
        pos = cursor.positionInBlock()
        text = cursor.block().text()[:pos]

        # Collect variable names visible up to current cursor
        local_vars, global_vars = self._collect_variables_up_to_cursor()

        # Find the word prefix
        completion_prefix = self.text_under_cursor()
        
        # Check for dot trigger
        # If the character just typed is '.', or we explicitly requested with Ctrl+Space
        # We need to find the object before the dot.
        
        # Simple regex-like parsing for "object.property"
        # Go back from cursor to find the last word+dot
        
        show_popup = False
        suggestions = []
        
        # Case 1: Just typed '.' or triggered after '.'
        if event.text() == "." or (is_shortcut and text.endswith(".")):
            # Find what is before the dot
            # E.g. "app." -> look up "app"
            # E.g. "files." -> look up "files"
            
            # Trim the dot if we just typed it
            pre_dot = text[:-1] if text.endswith(".") else text
            
            # Get the last word
            # This is a simplification. Ideally we use a tokenizer.
            # We grab the last sequence of alphanumeric chars
            import re
            match = re.search(r"([a-zA-Z0-9_]+)$", pre_dot)
            if match:
                obj_name = match.group(1)
                if obj_name in self.api_data:
                    # It's a known module/object
                    children = self.api_data[obj_name].get("children", {})
                    suggestions = list(children.keys())
                    # Add methods/props
                    
                elif obj_name == "this":
                    pass # Handle 'this' if needed
            
            completion_prefix = "" # We are starting a new word after dot

        # Case 2: Typing a word (not after dot, or after dot + chars)
        elif len(completion_prefix) > 0 or is_shortcut:
             # Need to find context. Are we part of "obj.pre"?
             # Look back
             
             # text ends with completion_prefix
             # Check character before completion_prefix
             prefix_start_pos = len(text) - len(completion_prefix)
             if prefix_start_pos > 0 and text[prefix_start_pos-1] == '.':
                 # It is "obj.prefix"
                 # Find obj
                 pre_dot = text[:prefix_start_pos-1]
                 import re
                 match = re.search(r"([a-zA-Z0-9_]+)$", pre_dot)
                 if match:
                     obj_name = match.group(1)
                     if obj_name in self.api_data:
                         children = self.api_data[obj_name].get("children", {})
                         suggestions = list(children.keys())
             else:
                 # Global scope or unknown scope
                 # Suggest variables in scope first, then modules and global functions
                 suggestions = list(local_vars) + list(global_vars)
                 # Add global modules
                 suggestions += list(self.api_data.keys())
                 # Add global functions
                 if "global" in self.api_data:
                     suggestions += list(self.api_data["global"].get("children", {}).keys())

        if not suggestions:
            self.completer.popup().hide()
            return

        # Update model
        model = QStringListModel(sorted(list(set(suggestions))))
        self.completer.setModel(model)
        
        if completion_prefix != self.completer.completionPrefix():
            self.completer.setCompletionPrefix(completion_prefix)
            self.completer.popup().setCurrentIndex(self.completer.completionModel().index(0, 0))
        
        cr = self.cursorRect()
        cr.setWidth(self.completer.popup().sizeHintForColumn(0) + self.completer.popup().verticalScrollBar().sizeHint().width())
        self.completer.complete(cr)

class ScriptEditorWindow(QMainWindow):
    def __init__(self, adb_client, parent=None):
        super().__init__(parent)
        self.adb_client = adb_client
        self.device_id = self._detect_device_id()
        self.local_script_root = os.path.abspath(os.path.join("local_scripts", self.device_id))
        self.remote_script_root = "/storage/emulated/0/脚本/"
        self.current_relative_path: Optional[str] = None
        
        self._init_ui()
        
        if not os.path.exists(self.local_script_root):
            os.makedirs(self.local_script_root)
        self.refresh_local_file_tree()
        
        # Initialize documentation parser in background? Or just do it now (it's fast)
        # Assuming the path relative to project root
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        doc_path = os.path.join(project_root, "AutoJs6-Documentation-master", "api")
        
        parser = DocParser(doc_path)
        self.api_data = parser.parse_all()
        
        # Setup completer
        completer = QCompleter(self)
        self.editor.set_api_data(self.api_data)
        self.editor.set_completer(completer)

    def _detect_device_id(self) -> str:
        try:
            result = self.adb_client._run(["devices"])
            if result.returncode != 0:
                return "default"
            lines = [line.strip() for line in result.stdout.splitlines()[1:] if line.strip()]
            for line in lines:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device":
                    return parts[0]
        except Exception:
            pass
        return "default"

    def _init_ui(self):
        self.setWindowTitle("Script Editor")
        self.resize(1000, 700)
        
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        sync_action = toolbar.addAction("Sync from Android")
        sync_action.triggered.connect(self.sync_from_android)
        
        push_action = toolbar.addAction("Push to Android")
        push_action.triggered.connect(self.push_current_to_android)
        
        save_action = toolbar.addAction("Save (Local)")
        save_action.triggered.connect(self.save_current_file)
        
        run_action = toolbar.addAction("Run on Device")
        run_action.triggered.connect(self.run_script)
        
        refresh_action = toolbar.addAction("Refresh Local Tree")
        refresh_action.triggered.connect(self.refresh_local_file_tree)

        splitter = QSplitter(Qt.Horizontal)
        
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabel("Scripts")
        self.tree_widget.itemClicked.connect(self.on_file_clicked)
        splitter.addWidget(self.tree_widget)
        
        self.editor = CodeEditor() # Use CodeEditor instead of SmartEditor
        splitter.addWidget(self.editor)
        
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 7)
        
        self.setCentralWidget(splitter)

    def sync_from_android(self):
        try:
            remote_files = self.adb_client.list_files(self.remote_script_root)
            if not remote_files:
                QMessageBox.information(self, "Info", "No files found or failed to list files.")
                return

            count = 0
            for remote_file in remote_files:
                if remote_file.startswith(self.remote_script_root):
                    rel_path = remote_file[len(self.remote_script_root):]
                elif remote_file.startswith("/sdcard/脚本/"):
                     rel_path = remote_file[len("/sdcard/脚本/"):]
                else:
                    continue
                
                rel_path = rel_path.lstrip("/")
                local_path = os.path.join(self.local_script_root, rel_path)
                
                if self.adb_client.pull_file(remote_file, local_path):
                    count += 1
            
            QMessageBox.information(self, "Success", f"Synced {count} files from Android.")
            self.refresh_local_file_tree()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Sync failed: {str(e)}")

    def push_current_to_android(self):
        if not self.current_relative_path:
            QMessageBox.warning(self, "Warning", "No file selected.")
            return
        
        self.save_current_file()
        
        local_path = os.path.join(self.local_script_root, self.current_relative_path)
        remote_rel_path = self.current_relative_path.replace("\\", "/")
        remote_path = self.remote_script_root.rstrip("/") + "/" + remote_rel_path
        
        try:
            if self.adb_client.push_file(local_path, remote_path):
                QMessageBox.information(self, "Success", f"Pushed {remote_rel_path} to Android.")
            else:
                QMessageBox.warning(self, "Failure", "Failed to push file.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Push failed: {str(e)}")

    def run_script(self):
        if not self.current_relative_path:
            QMessageBox.warning(self, "Warning", "No file selected.")
            return
            
        # 1. Push the file first
        self.push_current_to_android()
        
        # 2. Execute
        # Construct the remote path
        remote_rel_path = self.current_relative_path.replace("\\", "/")
        remote_path = self.remote_script_root.rstrip("/") + "/" + remote_rel_path
        
        # AutoJs6 Intent execution
        # am start -n org.autojs.autojs6/org.autojs.autojs.external.open.RunIntentActivity -d file:///... -t text/javascript
        # Note: Package name might be org.autojs.autojs or org.autojs.autojs6 depending on version
        # We will try a generic approach or assume the package based on previous user context (AutoJs6)
        
        # Construct URI
        file_uri = f"file://{remote_path}"
        
        # Try AutoJs6 package first
        pkg = "org.autojs.autojs6"
        cls = "org.autojs.autojs.external.open.RunIntentActivity"
        
        cmd = ["shell", "am", "start", "-n", f"{pkg}/{cls}", "-d", file_uri, "-t", "text/javascript"]
        
        try:
            result = self.adb_client._run(cmd)
            if result.returncode == 0:
                # Check output for error
                if "Error" in result.stderr or "Error" in result.stdout:
                     # Try alternative package name if it fails? 
                     # But for now just show info
                     QMessageBox.warning(self, "Run Result", f"Command executed with potential error:\n{result.stderr}\n{result.stdout}")
                else:
                     self.statusBar().showMessage(f"Running: {remote_rel_path}", 3000)
            else:
                QMessageBox.warning(self, "Run Failed", f"ADB Command Failed:\n{result.stderr}")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Run execution failed: {str(e)}")

    def save_current_file(self):
        if not self.current_relative_path:
            return
            
        local_path = os.path.join(self.local_script_root, self.current_relative_path)
        try:
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
            self.statusBar().showMessage(f"Saved: {self.current_relative_path}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Save failed: {str(e)}")

    def refresh_local_file_tree(self):
        self.tree_widget.clear()
        
        def get_or_create_item(path_parts, parent_item):
            if not path_parts:
                return parent_item
            
            current_part = path_parts[0]
            
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                if child.text(0) == current_part:
                    return get_or_create_item(path_parts[1:], child)
            
            new_item = QTreeWidgetItem(parent_item, [current_part])
            return get_or_create_item(path_parts[1:], new_item)

        for root, dirs, files in os.walk(self.local_script_root):
            rel_dir = os.path.relpath(root, self.local_script_root)
            if rel_dir == ".":
                rel_dir = ""
            
            path_parts = rel_dir.split(os.sep) if rel_dir else []
            path_parts = [p for p in path_parts if p]
            
            parent_item = get_or_create_item(path_parts, self.tree_widget.invisibleRootItem())
            
            for f in files:
                f_item = QTreeWidgetItem(parent_item, [f])
                f_rel = os.path.join(rel_dir, f)
                f_item.setData(0, Qt.UserRole, f_rel)

        self.tree_widget.expandAll()

    def on_file_clicked(self, item, column):
        rel_path = item.data(0, Qt.UserRole)
        if not rel_path:
            return
            
        full_path = os.path.join(self.local_script_root, rel_path)
        
        if os.path.isfile(full_path):
            self.current_relative_path = rel_path
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.editor.setPlainText(content)
                self.setWindowTitle(f"Script Editor - {rel_path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not read file: {str(e)}")
