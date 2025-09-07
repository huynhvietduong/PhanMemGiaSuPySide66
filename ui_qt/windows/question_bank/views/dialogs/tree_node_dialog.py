"""
Tree Node Dialog - Dialog thêm/sửa node trong cây thư mục
File: ui_qt/windows/question_bank/views/dialogs/tree_node_dialog.py
"""

import re
from typing import Optional, Dict, Any, List
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QGroupBox, QWidget,
    QLineEdit, QComboBox, QTextEdit, QSpinBox,
    QCheckBox, QMessageBox, QTreeWidget, QTreeWidgetItem
)


class TreeNodeDialog(QDialog):
    """Dialog thêm/sửa node trong cây thư mục"""

    # Signals
    node_saved = Signal(int)  # Phát tín hiệu khi lưu thành công

    def __init__(self, db_manager, mode="add", node_id=None, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.mode = mode  # "add" hoặc "edit"
        self.node_id = node_id
        self.parent_id: Optional[int] = None
        self.node_data: Optional[Dict] = None

        self._setup_window()
        self._setup_ui()
        self._setup_connections()

        if self.mode == "edit" and self.node_id:
            self._load_node_data()
        elif self.mode == "add":
            self._set_default_values()

    def _setup_window(self):
        """Thiết lập cửa sổ"""
        title = "✏️ Chỉnh sửa thư mục" if self.mode == "edit" else "➕ Thêm thư mục mới"
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(500, 450)

    def _setup_ui(self):
        """Thiết lập giao diện"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Main form
        self._create_main_form(layout)

        # Parent selection (chỉ khi add)
        if self.mode == "add":
            self._create_parent_selection(layout)

        # Preview section
        self._create_preview_section(layout)

        # Buttons
        self._create_buttons(layout)

    def _create_main_form(self, layout: QVBoxLayout):
        """Tạo form chính"""
        form_group = QGroupBox("📝 Thông tin thư mục")
        form_layout = QFormLayout(form_group)
        form_layout.setLabelAlignment(Qt.AlignRight)

        # Node name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nhập tên thư mục...")
        self.name_edit.setMaxLength(100)
        form_layout.addRow("📁 Tên thư mục:", self.name_edit)

        # Node type/level
        self.level_combo = QComboBox()
        self.level_combo.addItems([
            "folder",  # Thư mục thông thường
            "subject",  # Môn học
            "chapter",  # Chương
            "section",  # Phần/Mục
            "topic",  # Chủ đề
            "difficulty",  # Mức độ khó
            "exam_type"  # Loại đề thi
        ])
        self.level_combo.currentTextChanged.connect(self._on_level_changed)
        form_layout.addRow("📊 Loại:", self.level_combo)

        # Description
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setPlaceholderText("Mô tả thư mục (tùy chọn)...")
        form_layout.addRow("📄 Mô tả:", self.description_edit)

        # Order/Position
        self.order_spin = QSpinBox()
        self.order_spin.setRange(0, 999)
        self.order_spin.setValue(0)
        self.order_spin.setToolTip("Thứ tự hiển thị (0 = tự động)")
        form_layout.addRow("🔢 Thứ tự:", self.order_spin)

        # Color (for UI highlighting)
        self.color_combo = QComboBox()
        self.color_combo.addItems([
            "Mặc định",
            "🔴 Đỏ (Quan trọng)",
            "🟡 Vàng (Cảnh báo)",
            "🟢 Xanh (Hoàn thành)",
            "🔵 Xanh dương (Thông tin)",
            "🟣 Tím (Nâng cao)"
        ])
        form_layout.addRow("🎨 Màu sắc:", self.color_combo)

        layout.addWidget(form_group)

    def _create_parent_selection(self, layout: QVBoxLayout):
        """Tạo phần chọn parent (chỉ khi add)"""
        parent_group = QGroupBox("👆 Chọn thư mục cha")
        parent_layout = QVBoxLayout(parent_group)

        # Current parent info
        self.parent_info_label = QLabel("Chưa chọn thư mục cha")
        self.parent_info_label.setStyleSheet("""
            QLabel {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                padding: 8px;
                border-radius: 4px;
            }
        """)
        parent_layout.addWidget(self.parent_info_label)

        # Buttons
        parent_buttons_layout = QHBoxLayout()

        select_parent_btn = QPushButton("📁 Chọn thư mục cha")
        select_parent_btn.clicked.connect(self._select_parent)

        clear_parent_btn = QPushButton("❌ Xóa lựa chọn")
        clear_parent_btn.clicked.connect(self._clear_parent)

        parent_buttons_layout.addWidget(select_parent_btn)
        parent_buttons_layout.addWidget(clear_parent_btn)
        parent_buttons_layout.addStretch()

        parent_layout.addLayout(parent_buttons_layout)
        layout.addWidget(parent_group)

    def _create_preview_section(self, layout: QVBoxLayout):
        """Tạo phần preview"""
        preview_group = QGroupBox("👁️ Xem trước")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_label = QLabel("Preview sẽ hiển thị ở đây")
        self.preview_label.setStyleSheet("""
            QLabel {
                background: white;
                border: 2px dashed #dee2e6;
                padding: 15px;
                border-radius: 8px;
                color: #6c757d;
                font-style: italic;
            }
        """)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(60)

        preview_layout.addWidget(self.preview_label)
        layout.addWidget(preview_group)

    def _create_buttons(self, layout: QVBoxLayout):
        """Tạo nút điều khiển"""
        button_layout = QHBoxLayout()

        # Validate button
        validate_btn = QPushButton("✅ Kiểm tra")
        validate_btn.clicked.connect(self._validate_input)
        button_layout.addWidget(validate_btn)

        button_layout.addStretch()

        # Cancel button
        cancel_btn = QPushButton("❌ Hủy")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        # Save button
        save_text = "💾 Cập nhật" if self.mode == "edit" else "💾 Tạo mới"
        self.save_btn = QPushButton(save_text)
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._save_node)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background: #28a745;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background: #218838;
            }
        """)
        button_layout.addWidget(self.save_btn)

        layout.addLayout(button_layout)

    def _setup_connections(self):
        """Thiết lập kết nối"""
        # Real-time preview update
        self.name_edit.textChanged.connect(self._update_preview)
        self.level_combo.currentTextChanged.connect(self._update_preview)
        self.description_edit.textChanged.connect(self._update_preview)

        # Keyboard shortcuts
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+S"), self, self._save_node)
        QtGui.QShortcut(QtGui.QKeySequence("Escape"), self, self.reject)

    # ========== DATA LOADING ==========

    def _load_node_data(self):
        """Load dữ liệu node (khi edit)"""
        if not self.node_id:
            return

        try:
            node = self.db.execute_query(
                "SELECT * FROM exercise_tree WHERE id = ?",
                (self.node_id,), fetch="one"
            )

            if not node:
                QMessageBox.warning(self, "Lỗi", "Không tìm thấy node!")
                self.reject()
                return

            # Convert to dict
            if hasattr(node, 'keys'):
                self.node_data = dict(node)
            else:
                self.node_data = node

            # Fill form
            self.name_edit.setText(self.node_data.get('name', ''))
            self.level_combo.setCurrentText(self.node_data.get('level', 'folder'))
            self.description_edit.setPlainText(self.node_data.get('description', ''))
            self.order_spin.setValue(self.node_data.get('display_order', 0))

            # Set parent info
            self.parent_id = self.node_data.get('parent_id')

            # Update preview
            self._update_preview()

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể load node: {e}")
            self.reject()

    def _set_default_values(self):
        """Thiết lập giá trị mặc định (khi add)"""
        self.level_combo.setCurrentText("folder")
        self.order_spin.setValue(0)
        self._update_preview()

    # ========== PARENT SELECTION ==========

    def set_parent_id(self, parent_id: Optional[int]):
        """Thiết lập parent ID từ bên ngoài"""
        self.parent_id = parent_id
        self._update_parent_info()
        self._update_preview()

    def _select_parent(self):
        """Chọn thư mục cha"""
        dialog = ParentSelectorDialog(self.db, self.node_id, self)
        if dialog.exec() == QDialog.Accepted:
            self.parent_id = dialog.selected_parent_id
            self._update_parent_info()
            self._update_preview()

    def _clear_parent(self):
        """Xóa lựa chọn parent"""
        self.parent_id = None
        self._update_parent_info()
        self._update_preview()

    def _update_parent_info(self):
        """Cập nhật hiển thị thông tin parent"""
        if not hasattr(self, 'parent_info_label'):
            return

        if self.parent_id:
            try:
                parent = self.db.execute_query(
                    "SELECT name FROM exercise_tree WHERE id = ?",
                    (self.parent_id,), fetch="one"
                )
                if parent:
                    path = self._get_parent_path(self.parent_id)
                    self.parent_info_label.setText(f"📁 {path}")
                else:
                    self.parent_info_label.setText("❌ Parent không tồn tại")
            except Exception:
                self.parent_info_label.setText("❌ Lỗi load parent")
        else:
            self.parent_info_label.setText("🌱 Thư mục gốc (Root)")

    def _get_parent_path(self, parent_id: int) -> str:
        """Lấy đường dẫn của parent"""
        try:
            path_parts = []
            current_id = parent_id

            while current_id:
                node = self.db.execute_query(
                    "SELECT id, parent_id, name FROM exercise_tree WHERE id = ?",
                    (current_id,), fetch="one"
                )
                if not node:
                    break

                path_parts.insert(0, node['name'])
                current_id = node['parent_id']

            return " > ".join(path_parts)

        except Exception:
            return "Lỗi đường dẫn"

    # ========== VALIDATION ==========

    def _validate_input(self) -> bool:
        """Validate input với thông báo chi tiết"""
        errors = []

        # Validate name
        name = self.name_edit.text().strip()
        if not name:
            errors.append("❌ Tên thư mục không được để trống")
        elif len(name) > 100:
            errors.append("❌ Tên thư mục không được quá 100 ký tự")
        elif not re.match(r'^[^<>:"/\\|?*]+$', name):
            errors.append("❌ Tên thư mục chứa ký tự không hợp lệ")

        # Validate description
        description = self.description_edit.toPlainText()
        if len(description) > 1000:
            errors.append("❌ Mô tả không được quá 1000 ký tự")

        # Check duplicate name (trong cùng parent)
        if self._check_duplicate_name(name):
            errors.append("❌ Tên thư mục đã tồn tại trong cùng cấp")

        # Show validation results
        if errors:
            QMessageBox.warning(self, "Lỗi validation", "\n".join(errors))
            return False
        else:
            QMessageBox.information(self, "✅ Hợp lệ", "Thông tin hợp lệ!")
            return True

    def _check_duplicate_name(self, name: str) -> bool:
        """Kiểm tra trùng tên trong cùng parent"""
        try:
            existing = self.db.execute_query(
                "SELECT id FROM exercise_tree WHERE name = ? AND parent_id = ? AND id != ?",
                (name, self.parent_id, self.node_id or -1), fetch="one"
            )
            return existing is not None
        except Exception:
            return False

    # ========== PREVIEW ==========

    def _update_preview(self):
        """Cập nhật preview"""
        name = self.name_edit.text().strip()
        level = self.level_combo.currentText()
        description = self.description_edit.toPlainText().strip()

        if not name:
            self.preview_label.setText("👻 Nhập tên để xem preview")
            return

        # Create preview text
        icon = self._get_level_icon(level)
        preview_text = f"{icon} {name}"

        if description:
            preview_text += f"\n💭 {description[:50]}{'...' if len(description) > 50 else ''}"

        # Parent path
        if self.parent_id:
            parent_path = self._get_parent_path(self.parent_id)
            preview_text += f"\n📍 Vị trí: {parent_path} > {name}"
        else:
            preview_text += f"\n📍 Vị trí: (Root) > {name}"

        self.preview_label.setText(preview_text)

    def _get_level_icon(self, level: str) -> str:
        """Lấy icon cho từng loại level"""
        icons = {
            "folder": "📁",
            "subject": "📚",
            "chapter": "📖",
            "section": "📄",
            "topic": "🎯",
            "difficulty": "⭐",
            "exam_type": "📋"
        }
        return icons.get(level, "📁")

    def _on_level_changed(self, level: str):
        """Xử lý khi thay đổi level"""
        # Auto-fill description based on level
        if not self.description_edit.toPlainText():
            descriptions = {
                "folder": "Thư mục tổ chức các nội dung con",
                "subject": "Môn học với các chương bài học",
                "chapter": "Chương học với các phần nhỏ",
                "section": "Phần học với câu hỏi cụ thể",
                "topic": "Chủ đề cụ thể",
                "difficulty": "Phân loại theo độ khó",
                "exam_type": "Phân loại theo loại đề thi"
            }

            if level in descriptions:
                self.description_edit.setPlaceholderText(descriptions[level])

        self._update_preview()

    # ========== SAVE LOGIC ==========

    def _save_node(self):
        """Lưu node"""
        # Validate first
        if not self._validate_input_silent():
            return

        try:
            name = self.name_edit.text().strip()
            level = self.level_combo.currentText()
            description = self.description_edit.toPlainText().strip()
            display_order = self.order_spin.value()

            if self.mode == "edit":
                # Update existing node
                self.db.execute_query(
                    """UPDATE exercise_tree 
                       SET name = ?, level = ?, description = ?, 
                           display_order = ?, modified_at = datetime('now')
                       WHERE id = ?""",
                    (name, level, description, display_order, self.node_id)
                )

                saved_id = self.node_id
                action = "cập nhật"

            else:
                # Insert new node
                saved_id = self.db.execute_query(
                    """INSERT INTO exercise_tree 
                       (parent_id, name, level, description, display_order, created_at)
                       VALUES (?, ?, ?, ?, ?, datetime('now'))""",
                    (self.parent_id, name, level, description, display_order)
                )

                if not saved_id:
                    QMessageBox.critical(self, "Lỗi", "Không thể tạo thư mục mới")
                    return

                action = "tạo"

            # Emit signal
            self.node_saved.emit(saved_id)

            QMessageBox.information(self, "Thành công", f"Đã {action} thư mục '{name}'")
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu: {e}")

    def _validate_input_silent(self) -> bool:
        """Validate input không hiện thông báo"""
        name = self.name_edit.text().strip()

        if not name:
            self.name_edit.setFocus()
            return False

        if len(name) > 100:
            self.name_edit.setFocus()
            return False

        if not re.match(r'^[^<>:"/\\|?*]+$', name):
            self.name_edit.setFocus()
            return False

        if self._check_duplicate_name(name):
            self.name_edit.setFocus()
            return False

        return True


class ParentSelectorDialog(QDialog):
    """Dialog chọn thư mục cha"""

    def __init__(self, db_manager, exclude_node_id=None, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.exclude_node_id = exclude_node_id
        self.selected_parent_id: Optional[int] = None

        self._setup_window()
        self._setup_ui()
        self._load_tree()

    def _setup_window(self):
        """Thiết lập cửa sổ"""
        self.setWindowTitle("📁 Chọn thư mục cha")
        self.setModal(True)
        self.resize(400, 500)

    def _setup_ui(self):
        """Thiết lập giao diện"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Instructions
        info_label = QLabel("🎯 Chọn thư mục làm parent hoặc để trống để tạo root node")
        info_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(info_label)

        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["📁 Thư mục", "📊 Loại"])
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)

        # Selection handling
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.itemDoubleClicked.connect(self._on_double_click)

        layout.addWidget(self.tree)

        # Selection info
        self.selection_label = QLabel("Chưa chọn thư mục nào")
        self.selection_label.setStyleSheet("""
            QLabel {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                padding: 8px;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.selection_label)

        # Buttons
        button_layout = QHBoxLayout()

        # Root option
        root_btn = QPushButton("🌱 Chọn Root")
        root_btn.clicked.connect(self._select_root)
        button_layout.addWidget(root_btn)

        button_layout.addStretch()

        # Cancel & OK
        cancel_btn = QPushButton("❌ Hủy")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.ok_btn = QPushButton("✅ Chọn")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setEnabled(False)
        button_layout.addWidget(self.ok_btn)

        layout.addLayout(button_layout)

    def _load_tree(self):
        """Load cây thư mục"""
        try:
            self.tree.clear()

            # Load all nodes except the one being edited
            query = "SELECT id, parent_id, name, level FROM exercise_tree"
            params = []

            if self.exclude_node_id:
                query += " WHERE id != ?"
                params.append(self.exclude_node_id)

            query += " ORDER BY parent_id, name"

            nodes = self.db.execute_query(query, params, fetch="all") or []

            # Build tree structure
            node_items = {}
            root_items = []

            for node in nodes:
                item = QTreeWidgetItem()
                item.setText(0, node['name'])
                item.setText(1, node['level'])
                item.setData(0, Qt.UserRole, node['id'])

                # Icon based on level
                icon = self._get_level_icon(node['level'])
                item.setText(0, f"{icon} {node['name']}")

                node_items[node['id']] = {
                    'item': item,
                    'parent_id': node['parent_id']
                }

            # Build hierarchy
            for node_id, node_info in node_items.items():
                parent_id = node_info['parent_id']
                if parent_id and parent_id in node_items:
                    node_items[parent_id]['item'].addChild(node_info['item'])
                else:
                    root_items.append(node_info['item'])

            self.tree.addTopLevelItems(root_items)
            self.tree.expandAll()

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể load cây: {e}")

    def _get_level_icon(self, level: str) -> str:
        """Lấy icon cho level"""
        icons = {
            "folder": "📁",
            "subject": "📚",
            "chapter": "📖",
            "section": "📄",
            "topic": "🎯",
            "difficulty": "⭐",
            "exam_type": "📋"
        }
        return icons.get(level, "📁")

    def _on_selection_changed(self):
        """Xử lý khi selection thay đổi"""
        items = self.tree.selectedItems()
        if items:
            item = items[0]
            self.selected_parent_id = item.data(0, Qt.UserRole)

            # Get path
            path = self._get_item_path(item)
            self.selection_label.setText(f"📍 Đã chọn: {path}")
            self.selection_label.setStyleSheet("""
                QLabel {
                    background: #d4edda;
                    border: 1px solid #c3e6cb;
                    padding: 8px;
                    border-radius: 4px;
                    color: #155724;
                }
            """)

            self.ok_btn.setEnabled(True)
        else:
            self.selected_parent_id = None
            self.selection_label.setText("Chưa chọn thư mục nào")
            self.ok_btn.setEnabled(False)

    def _on_double_click(self, item, column):
        """Xử lý double click"""
        self._on_selection_changed()
        if self.selected_parent_id:
            self.accept()

    def _select_root(self):
        """Chọn root làm parent"""
        self.selected_parent_id = None
        self.selection_label.setText("🌱 Đã chọn: Root (Thư mục gốc)")
        self.selection_label.setStyleSheet("""
            QLabel {
                background: #d1ecf1;
                border: 1px solid #bee5eb;
                padding: 8px;
                border-radius: 4px;
                color: #0c5460;
            }
        """)
        self.ok_btn.setEnabled(True)

    def _get_item_path(self, item: QTreeWidgetItem) -> str:
        """Lấy đường dẫn của item"""
        path_parts = []
        current_item = item

        while current_item:
            text = current_item.text(0)
            # Remove icon from text
            clean_text = re.sub(r'^[^\w\s]+\s*', '', text)
            path_parts.insert(0, clean_text)
            current_item = current_item.parent()

        return " > ".join(path_parts)


class NodeTypeTemplateDialog(QDialog):
    """Dialog chọn template cho node type"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_template: Optional[Dict] = None

        self._setup_window()
        self._setup_ui()

    def _setup_window(self):
        """Thiết lập cửa sổ"""
        self.setWindowTitle("📋 Chọn Template")
        self.setModal(True)
        self.resize(600, 400)

    def _setup_ui(self):
        """Thiết lập giao diện"""
        layout = QVBoxLayout(self)

        # Info
        info_label = QLabel("🎨 Chọn template để tự động tạo cấu trúc thư mục:")
        layout.addWidget(info_label)

        # Template list
        self.template_list = QtWidgets.QListWidget()
        self.template_list.setAlternatingRowColors(True)

        # Add templates
        templates = self._get_templates()
        for template in templates:
            item = QtWidgets.QListWidgetItem()
            item.setText(f"{template['icon']} {template['name']}\n💭 {template['description']}")
            item.setData(Qt.UserRole, template)
            self.template_list.addItem(item)

        self.template_list.itemSelectionChanged.connect(self._on_template_selected)
        self.template_list.itemDoubleClicked.connect(self._on_template_double_clicked)

        layout.addWidget(self.template_list)

        # Preview
        self.preview_text = QTextEdit()
        self.preview_text.setMaximumHeight(120)
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("Chọn template để xem preview cấu trúc...")
        layout.addWidget(self.preview_text)

        # Buttons
        button_layout = QHBoxLayout()

        button_layout.addStretch()

        cancel_btn = QPushButton("❌ Hủy")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.apply_btn = QPushButton("✅ Áp dụng")
        self.apply_btn.clicked.connect(self.accept)
        self.apply_btn.setEnabled(False)
        button_layout.addWidget(self.apply_btn)

        layout.addLayout(button_layout)

    def _get_templates(self) -> List[Dict]:
        """Lấy danh sách templates"""
        return [
            {
                "name": "Toán học cơ bản",
                "icon": "🔢",
                "description": "Cấu trúc cho môn Toán: Đại số, Hình học, Giải tích",
                "structure": [
                    {"name": "Đại số", "level": "chapter"},
                    {"name": "Hình học", "level": "chapter"},
                    {"name": "Giải tích", "level": "chapter"}
                ]
            },
            {
                "name": "Vật lý cơ bản",
                "icon": "⚛️",
                "description": "Cấu trúc cho môn Vật lý: Cơ học, Nhiệt học, Điện học",
                "structure": [
                    {"name": "Cơ học", "level": "chapter"},
                    {"name": "Nhiệt học", "level": "chapter"},
                    {"name": "Điện học", "level": "chapter"}
                ]
            },
            {
                "name": "Phân loại độ khó",
                "icon": "⭐",
                "description": "Chia theo mức độ: Dễ, Trung bình, Khó",
                "structure": [
                    {"name": "Dễ", "level": "difficulty"},
                    {"name": "Trung bình", "level": "difficulty"},
                    {"name": "Khó", "level": "difficulty"}
                ]
            },
            {
                "name": "Loại đề thi",
                "icon": "📋",
                "description": "Chia theo loại: Trắc nghiệm, Tự luận, Thực hành",
                "structure": [
                    {"name": "Trắc nghiệm", "level": "exam_type"},
                    {"name": "Tự luận", "level": "exam_type"},
                    {"name": "Thực hành", "level": "exam_type"}
                ]
            }
        ]

    def _on_template_selected(self):
        """Xử lý khi chọn template"""
        items = self.template_list.selectedItems()
        if items:
            self.selected_template = items[0].data(Qt.UserRole)
            self._update_preview()
            self.apply_btn.setEnabled(True)
        else:
            self.selected_template = None
            self.preview_text.clear()
            self.apply_btn.setEnabled(False)

    def _on_template_double_clicked(self, item):
        """Xử lý double click template"""
        self.selected_template = item.data(Qt.UserRole)
        self.accept()

    def _update_preview(self):
        """Cập nhật preview template"""
        if not self.selected_template:
            return

        structure = self.selected_template.get('structure', [])
        preview_lines = []

        for node in structure:
            icon = self._get_level_icon(node['level'])
            preview_lines.append(f"  {icon} {node['name']} ({node['level']})")

        preview_text = f"📋 Template: {self.selected_template['name']}\n"
        preview_text += f"📄 Mô tả: {self.selected_template['description']}\n\n"
        preview_text += "📁 Cấu trúc sẽ tạo:\n"
        preview_text += "\n".join(preview_lines)

        self.preview_text.setPlainText(preview_text)

    def _get_level_icon(self, level: str) -> str:
        """Lấy icon cho level"""
        icons = {
            "folder": "📁",
            "subject": "📚",
            "chapter": "📖",
            "section": "📄",
            "topic": "🎯",
            "difficulty": "⭐",
            "exam_type": "📋"
        }
        return icons.get(level, "📁")


# ========== TEST FUNCTIONS ==========

def test_tree_node_dialog():
    """Test TreeNodeDialog"""
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Mock database
    class MockDB:
        def execute_query(self, query, params=None, fetch=None):
            return None

    dialog = TreeNodeDialog(MockDB(), mode="add")
    dialog.show()

    sys.exit(app.exec())


def test_parent_selector_dialog():
    """Test ParentSelectorDialog"""
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Mock database
    class MockDB:
        def execute_query(self, query, params=None, fetch=None):
            return [
                {'id': 1, 'parent_id': None, 'name': 'Toán học', 'level': 'subject'},
                {'id': 2, 'parent_id': 1, 'name': 'Đại số', 'level': 'chapter'},
            ]

    dialog = ParentSelectorDialog(MockDB())
    dialog.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    test_tree_node_dialog()