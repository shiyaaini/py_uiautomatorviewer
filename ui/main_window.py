import os
import json
from typing import Optional, Set

from PyQt5.QtCore import Qt, QModelIndex, QSortFilterProxyModel, QUrl
from PyQt5.QtGui import QPixmap, QStandardItemModel, QStandardItem, QPen, QColor, QBrush, QDesktopServices
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QToolBar, 
    QSplitter, QTreeView, QTableWidget, QTableWidgetItem, 
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QMessageBox, 
    QAbstractItemView, QLineEdit, QComboBox, QMenu, QDialog,
    QDialogButtonBox, QCheckBox, QGroupBox, QPlainTextEdit,
    QPushButton, QApplication
)

from core.adb_client import AdbClient
from core.uixml_parser import UiXmlParser, UiNode
from core.autojs_parser import AutoJsTreeParser
from ui.script_editor import ScriptEditorWindow


class NodeFilterProxyModel(QSortFilterProxyModel):
    """
    自定义过滤器模型，支持关键字和类型的多重过滤
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.filter_text = ""
        self.filter_class = "All"
        # 关键：启用递归过滤，这样如果子节点匹配，父节点也会显示
        self.setRecursiveFilteringEnabled(True)

    def set_filter_text(self, text: str):
        self.filter_text = text.lower()
        self.invalidateFilter()

    def set_filter_class(self, class_name: str):
        self.filter_class = class_name
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        # 获取当前行的数据
        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        item = model.itemFromIndex(index)
        
        if not item:
            return False
            
        node: UiNode = item.data(Qt.UserRole)
        if not node:
            return False

        # 1. 类型筛选 (Class Filter)
        if self.filter_class != "All":
            # 简单判断：如果节点类名不包含筛选词
            if self.filter_class not in node.class_name:
                return False

        # 2. 关键字搜索 (Keyword Search)
        if self.filter_text:
            # 搜索范围：文本、资源ID、描述、类名
            content = f"{node.text} {node.resource_id} {node.content_desc} {node.class_name}".lower()
            if self.filter_text not in content:
                return False
        
        return True


class ScreenCanvas(QGraphicsView):
    """自定义的画布，用于显示截图和处理点击"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(True) 
        self.main_window = None
        
        self.pixmap_item = None
        self.rect_item = None
        self.current_pixmap = None

    def set_image(self, image_path: str):
        self.scene.clear()
        self.current_pixmap = QPixmap(image_path)
        if self.current_pixmap.isNull():
            return
        
        self.pixmap_item = self.scene.addPixmap(self.current_pixmap)
        self.setSceneRect(self.scene.itemsBoundingRect())
        
        self.rect_item = QGraphicsRectItem(0, 0, 0, 0)
        self.rect_item.setPen(QPen(Qt.red, 3))
        self.rect_item.setBrush(QBrush(QColor(0, 0, 0, 0)))
        self.rect_item.setZValue(10)
        self.scene.addItem(self.rect_item)
        self.rect_item.hide()
        
        self.fit_image()

    def fit_image(self):
        if self.pixmap_item:
            self.fitInView(self.pixmap_item, Qt.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_image()

    def draw_rect(self, x, y, w, h):
        if self.rect_item:
            self.rect_item.setRect(x, y, w, h)
            self.rect_item.show()

    def mousePressEvent(self, event):
        if not self.pixmap_item:
            return
            
        scene_pos = self.mapToScene(event.pos())
        item_pos = self.pixmap_item.mapFromScene(scene_pos)
        
        x = int(item_pos.x())
        y = int(item_pos.y())
        
        img_w = self.pixmap_item.pixmap().width()
        img_h = self.pixmap_item.pixmap().height()
        
        print(f"DEBUG: Clicked View({event.pos().x()}, {event.pos().y()}) -> Scene({scene_pos.x():.1f}, {scene_pos.y():.1f}) -> Image({x}, {y})")

        if 0 <= x < img_w and 0 <= y < img_h:
            if self.main_window:
                self.main_window.on_screenshot_clicked(x, y)
        else:
            print(f"DEBUG: Click out of image bounds (0,0 - {img_w},{img_h})")
                
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.adb_client = AdbClient()
        self.xml_parser = UiXmlParser()
        self.autojs_parser = AutoJsTreeParser()
        self.root_node: Optional[UiNode] = None
        self.current_node: Optional[UiNode] = None
        self.script_editor = None
        
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle("Python UIAutomatorViewer")
        self.resize(1200, 800)

        # --- 工具栏 ---
        toolbar = QToolBar(self)
        self.addToolBar(toolbar)

        self.source_combo = QComboBox()
        self.source_combo.addItem("uiautomator")
        self.source_combo.addItem("AutoJs")
        toolbar.addWidget(self.source_combo)

        refresh_action = toolbar.addAction("刷新")
        refresh_action.triggered.connect(self.refresh_snapshot)
        
        script_editor_action = toolbar.addAction("脚本编辑")
        script_editor_action.triggered.connect(self.open_script_editor)

        autojs_doc_action = toolbar.addAction("AutoJs6 说明")
        autojs_doc_action.triggered.connect(self.open_autojs6_doc)

        # --- 主布局 (Splitter) ---
        main_splitter = QSplitter(Qt.Horizontal)
        
        # 1. 左侧：截图区域
        self.screen_canvas = ScreenCanvas()
        self.screen_canvas.main_window = self
        main_splitter.addWidget(self.screen_canvas)

        # 2. 右侧：垂直分割 (搜索栏 + 树 + 属性表)
        right_splitter = QSplitter(Qt.Vertical)
        
        # 2.1 右上：容器 (搜索栏 + 树)
        right_top_widget = QWidget()
        right_top_layout = QVBoxLayout(right_top_widget)
        right_top_layout.setContentsMargins(0, 0, 0, 0)
        
        # >> 搜索过滤区域 <<
        filter_layout = QHBoxLayout()
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search keywords...")
        self.search_edit.textChanged.connect(self.on_search_changed)
        
        self.type_combo = QComboBox()
        self.type_combo.addItem("All")
        self.type_combo.setMinimumWidth(120)
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        
        filter_layout.addWidget(self.search_edit)
        filter_layout.addWidget(self.type_combo)
        
        right_top_layout.addLayout(filter_layout)
        
        # >> 树形视图 <<
        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(True)
        self.tree_view.clicked.connect(self.on_tree_node_clicked)
        
        # 模型设置：StandardModel -> ProxyModel -> View
        self.tree_model = QStandardItemModel()
        self.proxy_model = NodeFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.tree_model)
        self.tree_view.setModel(self.proxy_model)
        self.tree_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        right_top_layout.addWidget(self.tree_view)
        
        right_splitter.addWidget(right_top_widget)
        
        # 2.2 右下：属性表
        self.prop_table = QTableWidget()
        self.prop_table.setColumnCount(2)
        self.prop_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.prop_table.horizontalHeader().setStretchLastSection(True)
        self.prop_table.verticalHeader().setVisible(False)
        self.prop_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.prop_table.customContextMenuRequested.connect(self.on_prop_table_context_menu)
        right_splitter.addWidget(self.prop_table)

        right_splitter.setStretchFactor(0, 6)
        right_splitter.setStretchFactor(1, 4)

        main_splitter.addWidget(right_splitter)
        main_splitter.setSizes([720, 480]) # 初始比例 6:4
        self.screen_canvas.setMinimumWidth(400)

        self.setCentralWidget(main_splitter)

    def open_autojs6_doc(self) -> None:
        """打开 AutoJs6 本地 HTML 文档"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        html_path = os.path.join(project_root, "AutoJs6-Documentation-master", "docs", "web.html")

        if os.path.exists(html_path):
            url = QUrl.fromLocalFile(html_path)
        else:
            QMessageBox.warning(self, "文档不存在", f"未找到文档文件：{html_path}")
            return

        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(self, "打开失败", f"无法在浏览器中打开：{url.toString()}")

    def open_script_editor(self):
        if not self.script_editor:
            # 不指定 MainWindow 作为父窗口，避免子窗口始终浮在父窗口前面
            self.script_editor = ScriptEditorWindow(self.adb_client)
        # 作为普通窗口显示，不强制置顶或抢占前台
        self.script_editor.show()

    def on_search_changed(self, text):
        """搜索框文本变化"""
        self.proxy_model.set_filter_text(text)
        self.tree_view.expandAll() # 搜索时自动展开所有匹配项

    def on_type_changed(self, text):
        """类型下拉框变化"""
        self.proxy_model.set_filter_class(text)
        self.tree_view.expandAll()

    def refresh_snapshot(self) -> None:
        try:
            source = self.source_combo.currentText() if hasattr(self, "source_combo") else "uiautomator"
            if source == "AutoJs":
                snapshot = self.adb_client.capture_snapshot_via_autojs()
                screenshot_path = snapshot.get("screenshot")
                json_path = snapshot.get("autojs_json")

                if screenshot_path and os.path.exists(screenshot_path):
                    self.screen_canvas.set_image(screenshot_path)

                if json_path and os.path.exists(json_path):
                    self.root_node = self.autojs_parser.parse_json(json_path)
                    if self.root_node:
                        self.build_tree(self.root_node)
                        print("DEBUG: Tree built successfully from AutoJs JSON")
                    else:
                        QMessageBox.warning(self, "解析警告", "AutoJs JSON 解析失败，无法显示控件树")
                else:
                    QMessageBox.warning(self, "数据缺失", "未能获取到 AutoJs UI 树 JSON 文件")
            else:
                snapshot = self.adb_client.capture_snapshot()
                screenshot_path = snapshot.get("screenshot")
                xml_path = snapshot.get("xml")
                
                if screenshot_path and os.path.exists(screenshot_path):
                    self.screen_canvas.set_image(screenshot_path)
                
                if xml_path and os.path.exists(xml_path):
                    self.root_node = self.xml_parser.parse_xml(xml_path)
                    if self.root_node:
                        self.build_tree(self.root_node)
                        print("DEBUG: Tree built successfully")
                    else:
                        QMessageBox.warning(self, "解析警告", "XML 解析失败，无法显示控件树")
                else:
                    QMessageBox.warning(self, "数据缺失", "未能获取到 XML 文件")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            import traceback
            traceback.print_exc()

    def build_tree(self, root_node: UiNode):
        """构建树并提取所有控件类型"""
        self.tree_model.clear()
        if not root_node:
            return

        # 1. 构建树
        root_item = self._create_tree_item(root_node)
        self.tree_model.appendRow(root_item)
        self.tree_view.expandToDepth(0)

        # 2. 提取所有出现的类名，填充下拉框
        all_classes = set()
        self._collect_classes(root_node, all_classes)
        
        self.type_combo.blockSignals(True) # 避免清空时触发信号
        self.type_combo.clear()
        self.type_combo.addItem("All")
        # 排序并添加
        for cls in sorted(list(all_classes)):
            self.type_combo.addItem(cls)
        self.type_combo.blockSignals(False)

    def _collect_classes(self, node: UiNode, classes: Set[str]):
        """递归收集类名"""
        if node.class_name:
            # 提取短类名 (e.g. android.widget.TextView -> TextView)
            short_name = node.class_name.split('.')[-1]
            classes.add(short_name)
        for child in node.children:
            self._collect_classes(child, classes)

    def _create_tree_item(self, node: UiNode) -> QStandardItem:
        item = QStandardItem(node.display_text)
        item.setData(node, Qt.UserRole)
        
        for child in node.children:
            child_item = self._create_tree_item(child)
            item.appendRow(child_item)
            
        return item

    def on_tree_node_clicked(self, index: QModelIndex):
        """
        树节点被点击 -> 高亮截图 + 显示属性
        注意：这里的 index 是 ProxyModel 的索引，需要映射回 SourceModel
        """
        # 从 Proxy 映射回 Source
        source_index = self.proxy_model.mapToSource(index)
        item = self.tree_model.itemFromIndex(source_index)
        
        if not item:
            return
            
        node: UiNode = item.data(Qt.UserRole)
        if node:
            x, y, w, h = node.rect
            self.screen_canvas.draw_rect(x, y, w, h)
            self.update_properties(node)

    def on_screenshot_clicked(self, x: int, y: int):
        """截图被点击 -> 查找节点 -> 选中树 -> 高亮"""
        if not self.root_node:
            return
        
        if self.screen_canvas.pixmap_item:
            pw = self.screen_canvas.pixmap_item.pixmap().width()
            ph = self.screen_canvas.pixmap_item.pixmap().height()
            print(f"DEBUG: Image({pw}x{ph}) Click({x},{y})")
            
        target_node = self._find_node_optimized(self.root_node, x, y)
        
        if target_node:
            print(f"DEBUG: Found node: {target_node.display_text}")
            self._select_node_in_tree(target_node)
        else:
            print(f"DEBUG: No node found at ({x}, {y})")

    def _find_node_optimized(self, root: UiNode, x: int, y: int) -> Optional[UiNode]:
        candidates = []
        
        def traverse(node: UiNode):
            nx, ny, nw, nh = node.rect
            if nw > 0 and nh > 0:
                if nx <= x <= nx + nw and ny <= y <= ny + nh:
                    candidates.append(node)
            for child in node.children:
                traverse(child)

        traverse(root)
        if not candidates:
            return None
        
        candidates.sort(key=lambda n: n.rect[2] * n.rect[3])
        return candidates[0]

    def _select_node_in_tree(self, target_node: UiNode):
        """在 TreeView 中选中指定节点 (需要处理 ProxyModel 映射)"""
        root_item = self.tree_model.item(0)
        if not root_item:
            return
            
        # 1. 在 Source Model 中找到 Item
        target_item = self._find_item_by_node(root_item, target_node)
        if target_item:
            source_index = target_item.index()
            
            # 2. 将 Source Index 映射为 Proxy Index
            proxy_index = self.proxy_model.mapFromSource(source_index)
            
            # 3. 如果该节点被过滤掉了（proxy_index 无效），则清空筛选以便显示
            if not proxy_index.isValid():
                print("DEBUG: Target node is hidden by filter, clearing filter...")
                self.search_edit.clear()
                self.type_combo.setCurrentIndex(0) # All
                # 清空后重新映射
                proxy_index = self.proxy_model.mapFromSource(source_index)

            if proxy_index.isValid():
                self.tree_view.setCurrentIndex(proxy_index)
                self.tree_view.scrollTo(proxy_index)
                # 手动触发点击逻辑 (注意要传 proxy index)
                self.on_tree_node_clicked(proxy_index)

    def _find_item_by_node(self, parent_item: QStandardItem, target_node: UiNode) -> Optional[QStandardItem]:
        if parent_item.data(Qt.UserRole) == target_node:
            return parent_item
        for i in range(parent_item.rowCount()):
            child = parent_item.child(i)
            res = self._find_item_by_node(child, target_node)
            if res:
                return res
        return None

    def update_properties(self, node: UiNode):
        self.prop_table.setRowCount(0)
        props = [
            ("text", node.text),
            ("id", node.resource_id.split(":id/")[-1] if ":id/" in node.resource_id else node.resource_id),
            ("fullid", node.resource_id),
            ("class", node.class_name),
            ("package", node.package),
            ("desc", node.content_desc),
            ("checkable", node.checkable),
            ("checked", node.checked),
            ("clickable", node.clickable),
            ("enabled", node.enabled),
            ("focusable", node.focusable),
            ("focused", node.focused),
            ("scrollable", node.scrollable),
            ("long-clickable", node.long_clickable),
            ("password", node.password),
            ("selected", node.selected),
            ("bounds", node.bounds_str),
            ("center", f"[{node.rect[0] + node.rect[2] // 2},{node.rect[1] + node.rect[3] // 2}]"),
            ("index", str(node.index))
        ]
        self.prop_table.setRowCount(len(props))
        for row, (key, val) in enumerate(props):
            self.prop_table.setItem(row, 0, QTableWidgetItem(key))
            self.prop_table.setItem(row, 1, QTableWidgetItem(val))
        self.current_node = node

    def _escape_js_string(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "")

    def _build_autojs_selector(
        self,
        node: UiNode,
        use_id: bool = True,
        use_text: bool = True,
        use_desc: bool = True,
        use_class: bool = True
    ) -> str:
        expr = "selector()"
        if use_id and node.resource_id:
            simple_id = node.resource_id.split(":id/")[-1] if ":id/" in node.resource_id else node.resource_id
            escaped_id = self._escape_js_string(simple_id)
            expr += f'.id("{escaped_id}")'
        if use_text and node.text:
            escaped_text = self._escape_js_string(node.text)
            expr += f'.text("{escaped_text}")'
        if use_desc and node.content_desc:
            escaped_desc = self._escape_js_string(node.content_desc)
            expr += f'.desc("{escaped_desc}")'
        if use_class and node.class_name:
            escaped_class = self._escape_js_string(node.class_name)
            expr += f'.className("{escaped_class}")'
        return expr

    def _build_autojs_function_name(self, node: UiNode) -> str:
        if node.resource_id:
            base = node.resource_id.split(":id/")[-1] if ":id/" in node.resource_id else node.resource_id
        elif node.text:
            base = node.text
        elif node.content_desc:
            base = node.content_desc
        elif node.class_name:
            base = node.class_name.split('.')[-1]
        else:
            base = f"node_{node.index}"
        sanitized = []
        for ch in base:
            if ch.isalnum():
                sanitized.append(ch)
            else:
                sanitized.append("_")
        name = "".join(sanitized).strip("_")
        if not name:
            name = f"node_{node.index}"
        return f"exists_{name}"

    def on_prop_table_context_menu(self, pos):
        if not self.current_node:
            return
        menu = QMenu(self)
        action_generate_code = menu.addAction("生成 AutoJs6 代码...")
        action_generate_exists_fn = menu.addAction("生成判断控件存在的函数")
        action_copy_json = menu.addAction("复制 JSON")
        global_pos = self.prop_table.viewport().mapToGlobal(pos)
        action = menu.exec_(global_pos)
        if action == action_generate_code:
            self.generate_autojs_code_for_current_node()
        elif action == action_generate_exists_fn:
            self.generate_exists_function_for_current_node()
        elif action == action_copy_json:
            self.copy_current_node_json()

    def generate_exists_function_for_current_node(self):
        if not self.current_node:
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("生成判断控件存在的函数")
        layout = QVBoxLayout(dialog)
        
        # 筛选条件
        filter_group = QGroupBox("筛选条件")
        filter_layout = QVBoxLayout(filter_group)
        chk_use_id = QCheckBox("使用 id")
        chk_use_text = QCheckBox("使用 text")
        chk_use_desc = QCheckBox("使用 desc")
        chk_use_class = QCheckBox("使用 className")
        # 默认都勾选
        chk_use_id.setChecked(True)
        chk_use_text.setChecked(True)
        chk_use_desc.setChecked(True)
        chk_use_class.setChecked(True)
        
        # 根据当前节点是否有值来设置初始勾选状态和启用状态
        if not self.current_node.resource_id:
            chk_use_id.setEnabled(False)
        if not self.current_node.text:
            chk_use_text.setEnabled(False)
        if not self.current_node.content_desc:
            chk_use_desc.setEnabled(False)
        if not self.current_node.class_name:
            chk_use_class.setEnabled(False)
            
        filter_layout.addWidget(chk_use_id)
        filter_layout.addWidget(chk_use_text)
        filter_layout.addWidget(chk_use_desc)
        filter_layout.addWidget(chk_use_class)
        layout.addWidget(filter_group)
        
        code_edit = QPlainTextEdit()
        code_edit.setReadOnly(True)
        layout.addWidget(code_edit)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_copy = QPushButton("复制")
        button_box.addButton(btn_copy, QDialogButtonBox.ActionRole)
        layout.addWidget(button_box)
        
        def update_code():
            selector_expr = self._build_autojs_selector(
                self.current_node,
                chk_use_id.isChecked(),
                chk_use_text.isChecked(),
                chk_use_desc.isChecked(),
                chk_use_class.isChecked()
            )
            fn_name = self._build_autojs_function_name(self.current_node)
            code = f"function {fn_name}() {{\n    return {selector_expr}.exists();\n}}\n"
            code_edit.setPlainText(code)
            return code
            
        def copy_code():
            code = update_code()
            self._copy_to_clipboard(code)
            
        # 初始更新一次
        update_code()
        
        # 连接信号
        chk_use_id.toggled.connect(update_code)
        chk_use_text.toggled.connect(update_code)
        chk_use_desc.toggled.connect(update_code)
        chk_use_class.toggled.connect(update_code)
        
        btn_copy.clicked.connect(copy_code)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        
        dialog.resize(500, 400)
        dialog.exec_()

    def _build_autojs_code_from_options(
        self,
        node: UiNode,
        use_find_one: bool,
        use_until_find: bool,
        use_wait_for: bool,
        use_exists: bool,
        do_click: bool,
        do_long_click: bool,
        do_set_text: bool,
        do_scroll_forward: bool,
        do_scroll_backward: bool,
        use_id: bool = True,
        use_text: bool = True,
        use_desc: bool = True,
        use_class: bool = True,
    ) -> str:
        selector_expr = self._build_autojs_selector(node, use_id, use_text, use_desc, use_class)
        if use_exists and not (do_click or do_long_click or do_set_text or do_scroll_forward or do_scroll_backward):
            return f"{selector_expr}.exists();"

        method = None
        if use_find_one:
            method = "findOne()"
        elif use_until_find:
            method = "untilFind()"
        elif use_wait_for:
            method = "waitFor()"

        has_action = do_click or do_long_click or do_set_text or do_scroll_forward or do_scroll_backward

        if method is None:
            if not has_action:
                return f"{selector_expr};"
            method = "findOne()"

        object_expr = f"{selector_expr}.{method}"
        lines = []
        var_name = "nodes" if use_until_find else "w"
        lines.append(f"let {var_name} = {object_expr};")

        if do_click:
            if use_until_find:
                lines.append(f"{var_name}.forEach(w => w.click());")
            else:
                lines.append(f"{var_name}.click();")
        if do_long_click:
            if use_until_find:
                lines.append(f"{var_name}.forEach(w => w.longClick());")
            else:
                lines.append(f"{var_name}.longClick();")
        if do_set_text:
            if use_until_find:
                lines.append(f"{var_name}.forEach(w => w.setText(\"TODO\"));")
            else:
                lines.append(f"{var_name}.setText(\"TODO\");")
        if do_scroll_forward:
            if use_until_find:
                lines.append(f"{var_name}.forEach(w => w.scrollForward());")
            else:
                lines.append(f"{var_name}.scrollForward();")
        if do_scroll_backward:
            if use_until_find:
                lines.append(f"{var_name}.forEach(w => w.scrollBackward());")
            else:
                lines.append(f"{var_name}.scrollBackward();")

        return "\n".join(lines)

    def generate_autojs_code_for_current_node(self):
        if not self.current_node:
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle("生成 AutoJs6 代码")

        layout = QVBoxLayout(dialog)

        # 查找方式
        select_group = QGroupBox("查找方式")
        select_layout = QVBoxLayout(select_group)
        chk_find_one = QCheckBox("直到找到一个 (findOne)")
        chk_until_find = QCheckBox("直到找到所有 (untilFind)")
        chk_wait_for = QCheckBox("等待控件出现 (waitFor)")
        chk_exists = QCheckBox("判断控件存在 (exists)")
        chk_find_one.setChecked(True)
        select_layout.addWidget(chk_find_one)
        select_layout.addWidget(chk_until_find)
        select_layout.addWidget(chk_wait_for)
        select_layout.addWidget(chk_exists)
        layout.addWidget(select_group)

        # 筛选条件
        filter_group = QGroupBox("筛选条件")
        filter_layout = QVBoxLayout(filter_group)
        chk_use_id = QCheckBox("使用 id")
        chk_use_text = QCheckBox("使用 text")
        chk_use_desc = QCheckBox("使用 desc")
        chk_use_class = QCheckBox("使用 className")
        # 默认都勾选
        chk_use_id.setChecked(True)
        chk_use_text.setChecked(True)
        chk_use_desc.setChecked(True)
        chk_use_class.setChecked(True)
        
        # 根据当前节点是否有值来设置初始勾选状态
        if not self.current_node.resource_id:
            chk_use_id.setEnabled(False)
        if not self.current_node.text:
            chk_use_text.setEnabled(False)
        if not self.current_node.content_desc:
            chk_use_desc.setEnabled(False)
        if not self.current_node.class_name:
            chk_use_class.setEnabled(False)
            
        filter_layout.addWidget(chk_use_id)
        filter_layout.addWidget(chk_use_text)
        filter_layout.addWidget(chk_use_desc)
        filter_layout.addWidget(chk_use_class)
        layout.addWidget(filter_group)

        action_group = QGroupBox("动作")
        action_layout = QVBoxLayout(action_group)
        chk_click = QCheckBox("点击 (click)")
        chk_long_click = QCheckBox("长按 (longClick)")
        chk_set_text = QCheckBox("设置文本 (setText)")
        chk_scroll_forward = QCheckBox("向前/右/下滑动 (scrollForward)")
        chk_scroll_backward = QCheckBox("向后/上/左滑动 (scrollBackward)")
        action_layout.addWidget(chk_click)
        action_layout.addWidget(chk_long_click)
        action_layout.addWidget(chk_set_text)
        action_layout.addWidget(chk_scroll_forward)
        action_layout.addWidget(chk_scroll_backward)
        layout.addWidget(action_group)

        code_edit = QPlainTextEdit()
        code_edit.setReadOnly(True)
        layout.addWidget(code_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.Cancel)
        btn_generate = QPushButton("生成预览")
        btn_copy = QPushButton("复制并关闭")
        button_box.addButton(btn_generate, QDialogButtonBox.ActionRole)
        button_box.addButton(btn_copy, QDialogButtonBox.ActionRole)
        layout.addWidget(button_box)

        def update_code():
            code = self._build_autojs_code_from_options(
                self.current_node,
                chk_find_one.isChecked(),
                chk_until_find.isChecked(),
                chk_wait_for.isChecked(),
                chk_exists.isChecked(),
                chk_click.isChecked(),
                chk_long_click.isChecked(),
                chk_set_text.isChecked(),
                chk_scroll_forward.isChecked(),
                chk_scroll_backward.isChecked(),
                chk_use_id.isChecked(),
                chk_use_text.isChecked(),
                chk_use_desc.isChecked(),
                chk_use_class.isChecked(),
            )
            code_edit.setPlainText(code)

        def copy_and_close():
            code = code_edit.toPlainText()
            if code:
                self._copy_to_clipboard(code)
            dialog.accept()

        btn_generate.clicked.connect(update_code)
        btn_copy.clicked.connect(copy_and_close)
        button_box.rejected.connect(dialog.reject)
        
        # 初始生成一次代码
        update_code()
        
        # 连接筛选条件变更事件
        chk_use_id.toggled.connect(update_code)
        chk_use_text.toggled.connect(update_code)
        chk_use_desc.toggled.connect(update_code)
        chk_use_class.toggled.connect(update_code)
        
        dialog.resize(600, 500)
        dialog.exec_()

    def _show_autojs_code_dialog(self, code: str):
        dialog = QDialog(self)
        dialog.setWindowTitle("生成 AutoJs6 代码")
        layout = QVBoxLayout(dialog)
        code_edit = QPlainTextEdit()
        code_edit.setReadOnly(True)
        code_edit.setPlainText(code)
        layout.addWidget(code_edit)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        btn_copy = QPushButton("复制")
        button_box.addButton(btn_copy, QDialogButtonBox.ActionRole)
        layout.addWidget(button_box)

        def copy_and_close():
            self._copy_to_clipboard(code)
            dialog.accept()

        btn_copy.clicked.connect(copy_and_close)
        button_box.accepted.connect(dialog.accept)

        dialog.resize(520, 400)
        dialog.exec_()

    def _copy_to_clipboard(self, text: str):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        QMessageBox.information(self, "已复制", "已复制到剪贴板")

    def copy_current_node_json(self):
        if not self.current_node:
            return
        node = self.current_node
        x, y, w, h = node.rect
        data = {
            "text": node.text,
            "id": node.resource_id.split(":id/")[-1] if ":id/" in node.resource_id else node.resource_id,
            "fullid": node.resource_id,
            "class": node.class_name,
            "package": node.package,
            "desc": node.content_desc,
            "checkable": str(node.checkable).lower() == "true",
            "checked": str(node.checked).lower() == "true",
            "clickable": str(node.clickable).lower() == "true",
            "enabled": str(node.enabled).lower() == "true",
            "focusable": str(node.focusable).lower() == "true",
            "focused": str(node.focused).lower() == "true",
            "scrollable": str(node.scrollable).lower() == "true",
            "long_clickable": str(node.long_clickable).lower() == "true",
            "password": str(node.password).lower() == "true",
            "selected": str(node.selected).lower() == "true",
            "bounds": node.bounds_str,
            "rect": {"x": x, "y": y, "w": w, "h": h},
            "center": {"x": x + w // 2, "y": y + h // 2},
            "index": int(node.index),
        }
        text = json.dumps(data, ensure_ascii=False, indent=2)
        self._copy_to_clipboard(text)
