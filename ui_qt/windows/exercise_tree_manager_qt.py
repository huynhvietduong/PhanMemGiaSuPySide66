# ui_qt/windows/exercise_tree_manager_qt.py
from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
import json
import os
from datetime import datetime


class ModernExerciseTreeManagerQt(QtWidgets.QDialog):
    """
    🌳 Quản lý cây thư mục hiện đại - PySide6
    Quản lý cấu trúc phân cấp: Môn → Lớp → Chủ đề → Dạng → Mức độ

    Tính năng mới:
    - Drag & Drop di chuyển nodes
    - Undo/Redo operations
    - Advanced search với filters
    - Import/Export JSON/CSV
    - Keyboard shortcuts
    - Modern UI với icons và animations
    - Bulk operations
    """

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setWindowTitle("🌳 Quản lý cây thư mục hiện đại")
        self.setModal(True)
        self.resize(1200, 800)

        # Đảm bảo bảng tồn tại
        self._ensure_table()

        # Dictionary để track nodes
        self.tree_nodes: Dict[int, QtWidgets.QTreeWidgetItem] = {}

        # History cho undo/redo
        self.command_history: List[Dict] = []
        self.history_index: int = -1
        self.max_history: int = 50

        # Search timer để tránh search liên tục
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_search)

        # Clipboard cho copy/paste
        self.clipboard_data: Optional[Dict] = None

        self._build_modern_ui()
        self._setup_shortcuts()
        self._load_tree()
        self._apply_modern_styles()

    def _ensure_table(self):
        """Tạo bảng exercise_tree nếu chưa có với các cột mở rộng"""
        self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS exercise_tree (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER,
                name TEXT NOT NULL,
                level TEXT NOT NULL,
                description TEXT,
                icon TEXT DEFAULT '',
                color TEXT DEFAULT '#2E86AB',
                is_active BOOLEAN DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_id) REFERENCES exercise_tree (id)
            )
        """)

        # Thêm trigger để tự động cập nhật updated_at
        self.db.execute_query("""
            CREATE TRIGGER IF NOT EXISTS update_exercise_tree_timestamp 
            AFTER UPDATE ON exercise_tree
            BEGIN
                UPDATE exercise_tree SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
        """)

        # Thêm dữ liệu mẫu nếu bảng trống
        count = self.db.execute_query("SELECT COUNT(*) as count FROM exercise_tree", fetch="one")
        if count and count["count"] == 0:
            self._insert_sample_data()

    def _insert_sample_data(self):
        """Thêm dữ liệu mẫu với icons và colors"""
        sample_data = [
            # Môn học với icons
            (None, "Toán", "Môn", "Môn Toán học", "📊", "#2E86AB", 1),
            (None, "Lý", "Môn", "Môn Vật lý", "⚛️", "#A23B72", 1),
            (None, "Hóa", "Môn", "Môn Hóa học", "🧪", "#F18F01", 1),
            (None, "Văn", "Môn", "Môn Ngữ văn", "📚", "#C73E1D", 1),

            # Lớp (con của Toán - id=1)
            (1, "Lớp 10", "Lớp", "Toán lớp 10", "🎓", "#2E86AB", 1),
            (1, "Lớp 11", "Lớp", "Toán lớp 11", "🎓", "#2E86AB", 1),
            (1, "Lớp 12", "Lớp", "Toán lớp 12", "🎓", "#2E86AB", 1),

            # Chủ đề (con của Lớp 10 - id=5)
            (5, "Mệnh đề - Tập hợp", "Chủ đề", "Chương 1: Mệnh đề và tập hợp", "📋", "#5D737E", 1),
            (5, "Hàm số", "Chủ đề", "Chương 2: Hàm số", "📈", "#5D737E", 1),
            (5, "Phương trình", "Chủ đề", "Chương 3: Phương trình và bất phương trình", "📐", "#5D737E", 1),
        ]

        for parent_id, name, level, description, icon, color, is_active in sample_data:
            self.db.execute_query(
                """INSERT INTO exercise_tree 
                   (parent_id, name, level, description, icon, color, is_active) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (parent_id, name, level, description, icon, color, is_active)
            )

    def _build_modern_ui(self):
        """Xây dựng giao diện hiện đại"""
        layout = QtWidgets.QVBoxLayout(self)

        # Header với logo và title
        self._create_header(layout)

        # Toolbar hiện đại
        self._create_modern_toolbar(layout)

        # Search panel mở rộng
        self._create_advanced_search_panel(layout)

        # Main content với splitter
        splitter = QtWidgets.QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Tree panel
        self._create_tree_panel(splitter)

        # Properties panel
        self._create_properties_panel(splitter)

        # Status bar
        self._create_status_bar(layout)

        # Dialog buttons
        self._create_dialog_buttons(layout)

        splitter.setSizes([700, 500])

    def _create_header(self, layout):
        """# Tạo header với logo và title"""
        header_widget = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 10, 10, 5)

        # Logo
        logo_label = QtWidgets.QLabel("🌳")
        logo_label.setStyleSheet("font-size: 24px;")

        # Title
        title_label = QtWidgets.QLabel("Quản lý cây thư mục hiện đại")
        title_label.setStyleSheet("""
            font-size: 18px; 
            font-weight: bold; 
            color: #2E86AB;
            margin-left: 10px;
        """)

        header_layout.addWidget(logo_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        layout.addWidget(header_widget)

    def _create_modern_toolbar(self, layout):
        """# Tạo toolbar hiện đại với icons"""
        toolbar_widget = QtWidgets.QWidget()
        toolbar_layout = QtWidgets.QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(10, 5, 10, 5)

        # Group: File operations
        file_group = QtWidgets.QGroupBox("Tệp")
        file_layout = QtWidgets.QHBoxLayout(file_group)

        self.import_btn = self._create_modern_button("📁 Import", "Ctrl+I")
        self.import_btn.clicked.connect(self.import_data)

        self.export_btn = self._create_modern_button("💾 Export", "Ctrl+E")
        self.export_btn.clicked.connect(self.export_data)

        file_layout.addWidget(self.import_btn)
        file_layout.addWidget(self.export_btn)

        # Group: Edit operations
        edit_group = QtWidgets.QGroupBox("Chỉnh sửa")
        edit_layout = QtWidgets.QHBoxLayout(edit_group)

        self.add_btn = self._create_modern_button("➕ Thêm", "Ctrl+N")
        self.add_btn.clicked.connect(self.add_node)

        self.edit_btn = self._create_modern_button("✏️ Sửa", "F2")
        self.edit_btn.clicked.connect(self.edit_node)
        self.edit_btn.setEnabled(False)

        self.delete_btn = self._create_modern_button("🗑️ Xóa", "Delete")
        self.delete_btn.clicked.connect(self.delete_node)
        self.delete_btn.setEnabled(False)

        self.copy_btn = self._create_modern_button("📋 Sao chép", "Ctrl+C")
        self.copy_btn.clicked.connect(self.copy_node)
        self.copy_btn.setEnabled(False)

        self.paste_btn = self._create_modern_button("📄 Dán", "Ctrl+V")
        self.paste_btn.clicked.connect(self.paste_node)
        self.paste_btn.setEnabled(False)

        edit_layout.addWidget(self.add_btn)
        edit_layout.addWidget(self.edit_btn)
        edit_layout.addWidget(self.delete_btn)
        edit_layout.addWidget(self.copy_btn)
        edit_layout.addWidget(self.paste_btn)

        # Group: History operations
        history_group = QtWidgets.QGroupBox("Lịch sử")
        history_layout = QtWidgets.QHBoxLayout(history_group)

        self.undo_btn = self._create_modern_button("↶ Hoàn tác", "Ctrl+Z")
        self.undo_btn.clicked.connect(self.undo)
        self.undo_btn.setEnabled(False)

        self.redo_btn = self._create_modern_button("↷ Làm lại", "Ctrl+Y")
        self.redo_btn.clicked.connect(self.redo)
        self.redo_btn.setEnabled(False)

        history_layout.addWidget(self.undo_btn)
        history_layout.addWidget(self.redo_btn)

        # Group: View operations
        view_group = QtWidgets.QGroupBox("Hiển thị")
        view_layout = QtWidgets.QHBoxLayout(view_group)

        self.expand_all_btn = self._create_modern_button("📖 Mở rộng", "Ctrl+Plus")
        self.expand_all_btn.clicked.connect(self.expand_all)

        self.collapse_all_btn = self._create_modern_button("📚 Thu gọn", "Ctrl+Minus")
        self.collapse_all_btn.clicked.connect(self.collapse_all)

        self.refresh_btn = self._create_modern_button("🔄 Làm mới", "F5")
        self.refresh_btn.clicked.connect(self.refresh_tree)

        view_layout.addWidget(self.expand_all_btn)
        view_layout.addWidget(self.collapse_all_btn)
        view_layout.addWidget(self.refresh_btn)

        # Add groups to toolbar
        toolbar_layout.addWidget(file_group)
        toolbar_layout.addWidget(edit_group)
        toolbar_layout.addWidget(history_group)
        toolbar_layout.addWidget(view_group)
        toolbar_layout.addStretch()

        layout.addWidget(toolbar_widget)

    def _create_modern_button(self, text: str, shortcut: str = "") -> QtWidgets.QPushButton:
        """# Tạo button hiện đại với style"""
        btn = QtWidgets.QPushButton(text)
        if shortcut:
            btn.setToolTip(f"{text} ({shortcut})")

        btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 500;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                border-color: #2E86AB;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
            QPushButton:disabled {
                background-color: #f8f8f8;
                color: #999;
                border-color: #e0e0e0;
            }
        """)

        return btn

    def _create_advanced_search_panel(self, layout):
        """# Tạo panel tìm kiếm nâng cao"""
        search_widget = QtWidgets.QWidget()
        search_layout = QtWidgets.QHBoxLayout(search_widget)
        search_layout.setContentsMargins(10, 5, 10, 10)

        # Search input
        search_label = QtWidgets.QLabel("🔍 Tìm kiếm:")
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Nhập từ khóa tìm kiếm...")
        self.search_input.textChanged.connect(self._on_search_text_changed)

        # Level filter
        level_label = QtWidgets.QLabel("Cấp độ:")
        self.level_filter = QtWidgets.QComboBox()
        self.level_filter.addItems(["Tất cả", "Môn", "Lớp", "Chủ đề", "Dạng", "Mức độ"])
        self.level_filter.currentTextChanged.connect(self._perform_search)

        # Active filter
        active_label = QtWidgets.QLabel("Trạng thái:")
        self.active_filter = QtWidgets.QComboBox()
        self.active_filter.addItems(["Tất cả", "Đang hoạt động", "Đã ẩn"])
        self.active_filter.currentTextChanged.connect(self._perform_search)

        # Clear search
        self.clear_search_btn = QtWidgets.QPushButton("❌ Xóa")
        self.clear_search_btn.clicked.connect(self.clear_search)

        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input, 2)
        search_layout.addWidget(level_label)
        search_layout.addWidget(self.level_filter)
        search_layout.addWidget(active_label)
        search_layout.addWidget(self.active_filter)
        search_layout.addWidget(self.clear_search_btn)
        search_layout.addStretch()

        layout.addWidget(search_widget)

    def _create_tree_panel(self, splitter):
        """# Tạo panel cây thư mục với drag & drop"""
        tree_widget = QtWidgets.QWidget()
        tree_layout = QtWidgets.QVBoxLayout(tree_widget)

        # Tree header
        tree_header = QtWidgets.QLabel("📂 Cấu trúc thư mục")
        tree_header.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 5px;")
        tree_layout.addWidget(tree_header)

        # Tree widget với drag & drop
        self.tree = DragDropTreeWidget()
        self.tree.setHeaderLabels(["Tên", "Cấp độ", "Trạng thái", "Mô tả"])
        self.tree.setColumnWidth(0, 200)
        self.tree.setColumnWidth(1, 80)
        self.tree.setColumnWidth(2, 80)

        # Enable drag & drop
        self.tree.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.tree.setDefaultDropAction(Qt.MoveAction)

        # Context menu
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)

        # Selection changed
        self.tree.itemSelectionChanged.connect(self.on_tree_selection_changed)

        # Drop event
        self.tree.item_moved.connect(self.on_item_moved)

        tree_layout.addWidget(self.tree)
        splitter.addWidget(tree_widget)

    def _create_properties_panel(self, splitter):
        """# Tạo panel thuộc tính chi tiết"""
        props_widget = QtWidgets.QWidget()
        props_layout = QtWidgets.QVBoxLayout(props_widget)

        # Properties header
        props_header = QtWidgets.QLabel("⚙️ Thuộc tính")
        props_header.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 5px;")
        props_layout.addWidget(props_header)

        # Scroll area cho form
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        form_widget = QtWidgets.QWidget()
        form_layout = QtWidgets.QFormLayout(form_widget)

        # Basic info
        self.name_edit = QtWidgets.QLineEdit()
        self.level_combo = QtWidgets.QComboBox()
        self.level_combo.addItems(["Môn", "Lớp", "Chủ đề", "Dạng", "Mức độ"])

        # Icon picker
        self.icon_edit = QtWidgets.QLineEdit()
        self.icon_edit.setPlaceholderText("📊 (emoji icon)")

        # Color picker
        self.color_btn = QtWidgets.QPushButton()
        self.color_btn.setFixedSize(60, 30)
        self.color_btn.clicked.connect(self.pick_color)
        self.current_color = "#2E86AB"
        self._update_color_button()

        # Active checkbox
        self.active_checkbox = QtWidgets.QCheckBox("Đang hoạt động")
        self.active_checkbox.setChecked(True)

        # Description
        self.description_edit = QtWidgets.QTextEdit()
        self.description_edit.setMaximumHeight(100)

        # Metadata (JSON)
        self.metadata_edit = QtWidgets.QTextEdit()
        self.metadata_edit.setMaximumHeight(80)
        self.metadata_edit.setPlaceholderText('{"key": "value"}')

        # Timestamps (read-only)
        self.created_label = QtWidgets.QLabel("-")
        self.updated_label = QtWidgets.QLabel("-")

        form_layout.addRow("Tên:", self.name_edit)
        form_layout.addRow("Cấp độ:", self.level_combo)
        form_layout.addRow("Icon:", self.icon_edit)
        form_layout.addRow("Màu sắc:", self.color_btn)
        form_layout.addRow("", self.active_checkbox)
        form_layout.addRow("Mô tả:", self.description_edit)
        form_layout.addRow("Metadata:", self.metadata_edit)
        form_layout.addRow("Tạo lúc:", self.created_label)
        form_layout.addRow("Cập nhật:", self.updated_label)

        # Save button
        save_layout = QtWidgets.QHBoxLayout()
        self.save_btn = QtWidgets.QPushButton("💾 Lưu thay đổi")
        self.save_btn.clicked.connect(self.save_current_node)
        self.save_btn.setEnabled(False)

        save_layout.addWidget(self.save_btn)
        save_layout.addStretch()
        form_layout.addRow("", save_layout)

        scroll.setWidget(form_widget)
        props_layout.addWidget(scroll)

        # Disable form initially
        self.set_form_enabled(False)

        splitter.addWidget(props_widget)

    def _create_status_bar(self, layout):
        """# Tạo status bar"""
        self.status_bar = QtWidgets.QLabel("Sẵn sàng")
        self.status_bar.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                border-top: 1px solid #dee2e6;
                padding: 5px 10px;
                color: #6c757d;
            }
        """)
        layout.addWidget(self.status_bar)

    def _create_dialog_buttons(self, layout):
        """# Tạo dialog buttons"""
        dialog_buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        dialog_buttons.accepted.connect(self.accept)
        dialog_buttons.rejected.connect(self.reject)
        layout.addWidget(dialog_buttons)

    def _setup_shortcuts(self):
        """# Thiết lập keyboard shortcuts"""
        shortcuts = [
            ("Ctrl+N", self.add_node),
            ("F2", self.edit_node),
            ("Delete", self.delete_node),
            ("Ctrl+C", self.copy_node),
            ("Ctrl+V", self.paste_node),
            ("Ctrl+Z", self.undo),
            ("Ctrl+Y", self.redo),
            ("Ctrl+I", self.import_data),
            ("Ctrl+E", self.export_data),
            ("F5", self.refresh_tree),
            ("Ctrl+Plus", self.expand_all),
            ("Ctrl+Minus", self.collapse_all),
            ("Ctrl+F", lambda: self.search_input.setFocus()),
        ]

        for key_sequence, slot in shortcuts:
            shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(key_sequence), self)
            shortcut.activated.connect(slot)

    def _apply_modern_styles(self):
        """# Áp dụng styles hiện đại"""
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ccc;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QLineEdit, QComboBox, QTextEdit {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 6px;
                background-color: white;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border-color: #2E86AB;
                outline: none;
            }
            QTreeWidget {
                border: 1px solid #ddd;
                border-radius: 8px;
                background-color: white;
                alternate-background-color: #f8f9fa;
            }
            QTreeWidget::item {
                padding: 4px;
                border-bottom: 1px solid #f0f0f0;
            }
            QTreeWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
            }
            QTreeWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)

    # ======================= EVENT HANDLERS =======================

    def _on_search_text_changed(self):
        """# Xử lý khi text search thay đổi"""
        self.search_timer.stop()
        self.search_timer.start(300)  # Delay 300ms

    def _perform_search(self):
        """# Thực hiện tìm kiếm với filters"""
        search_text = self.search_input.text().lower()
        level_filter = self.level_filter.currentText()
        active_filter = self.active_filter.currentText()

        self._filter_tree_recursive(
            self.tree.invisibleRootItem(),
            search_text,
            level_filter,
            active_filter
        )

        # Update status
        visible_count = self._count_visible_items()
        self.status_bar.setText(f"Tìm thấy {visible_count} mục")

    def _filter_tree_recursive(self, parent_item, search_text, level_filter, active_filter):
        """# Đệ quy filter cây"""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)

            # Check search text
            text_match = (search_text == "" or
                          search_text in child.text(0).lower() or
                          search_text in child.text(3).lower())

            # Check level filter
            level_match = (level_filter == "Tất cả" or
                           child.text(1) == level_filter)

            # Check active filter
            active_match = (active_filter == "Tất cả" or
                            (active_filter == "Đang hoạt động" and child.text(2) == "✓") or
                            (active_filter == "Đã ẩn" and child.text(2) == "✗"))

            # Show/hide item
            visible = text_match and level_match and active_match
            child.setHidden(not visible)

            # Recursive call
            self._filter_tree_recursive(child, search_text, level_filter, active_filter)

    def _count_visible_items(self) -> int:
        """# Đếm số items visible"""
        count = 0

        def count_recursive(parent_item):
            nonlocal count
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                if not child.isHidden():
                    count += 1
                count_recursive(child)

        count_recursive(self.tree.invisibleRootItem())
        return count

    def clear_search(self):
        """# Xóa tìm kiếm"""
        self.search_input.clear()
        self.level_filter.setCurrentText("Tất cả")
        self.active_filter.setCurrentText("Tất cả")
        self._perform_search()

    def on_tree_selection_changed(self):
        """# Xử lý khi selection thay đổi"""
        selected_items = self.tree.selectedItems()
        has_selection = len(selected_items) > 0

        # Enable/disable buttons
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
        self.copy_btn.setEnabled(has_selection)

        if has_selection:
            # Load node details
            self._load_node_details(selected_items[0])
            self.set_form_enabled(True)
        else:
            self.set_form_enabled(False)

    def _load_node_details(self, item: QtWidgets.QTreeWidgetItem):
        """# Load chi tiết node vào form"""
        node_id = item.data(0, Qt.UserRole)
        if not node_id:
            return

        row = self.db.execute_query(
            """SELECT name, level, description, icon, color, is_active, 
                      metadata, created_at, updated_at 
               FROM exercise_tree WHERE id = ?""",
            (node_id,), fetch="one"
        )

        if row:
            self.name_edit.setText(row["name"] or "")
            self.level_combo.setCurrentText(row["level"] or "Môn")
            self.icon_edit.setText(row["icon"] or "")
            self.current_color = row["color"] or "#2E86AB"
            self._update_color_button()
            self.active_checkbox.setChecked(bool(row["is_active"]))
            self.description_edit.setPlainText(row["description"] or "")
            self.metadata_edit.setPlainText(row["metadata"] or "{}")

            # Format timestamps
            created = row["created_at"] or ""
            updated = row["updated_at"] or ""
            self.created_label.setText(created)
            self.updated_label.setText(updated)

    def set_form_enabled(self, enabled: bool):
        """# Enable/disable form"""
        widgets = [
            self.name_edit, self.level_combo, self.icon_edit,
            self.color_btn, self.active_checkbox, self.description_edit,
            self.metadata_edit, self.save_btn
        ]

        for widget in widgets:
            widget.setEnabled(enabled)

    def pick_color(self):
        """# Chọn màu sắc"""
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.current_color), self)
        if color.isValid():
            self.current_color = color.name()
            self._update_color_button()

    def _update_color_button(self):
        """# Cập nhật button màu"""
        self.color_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.current_color};
                border: 2px solid #333;
                border-radius: 4px;
            }}
        """)

    def on_item_moved(self, item: QtWidgets.QTreeWidgetItem, new_parent_id: Optional[int]):
        """# Xử lý khi item được di chuyển"""
        node_id = item.data(0, Qt.UserRole)
        if not node_id:
            return

        # Save command for undo
        old_parent_id = self._get_current_parent_id(node_id)
        command = {
            "type": "move",
            "node_id": node_id,
            "old_parent_id": old_parent_id,
            "new_parent_id": new_parent_id,
            "timestamp": datetime.now().isoformat()
        }
        self._add_command_to_history(command)

        # Update database
        self.db.execute_query(
            "UPDATE exercise_tree SET parent_id = ? WHERE id = ?",
            (new_parent_id, node_id)
        )

        self.status_bar.setText(f"Đã di chuyển '{item.text(0)}'")

    def _get_current_parent_id(self, node_id: int) -> Optional[int]:
        """# Lấy parent_id hiện tại"""
        row = self.db.execute_query(
            "SELECT parent_id FROM exercise_tree WHERE id = ?",
            (node_id,), fetch="one"
        )
        return row["parent_id"] if row else None

    # ======================= COMMAND HISTORY =======================

    def _add_command_to_history(self, command: Dict):
        """# Thêm command vào history"""
        # Remove commands after current index
        self.command_history = self.command_history[:self.history_index + 1]

        # Add new command
        self.command_history.append(command)
        self.history_index += 1

        # Limit history size
        if len(self.command_history) > self.max_history:
            self.command_history.pop(0)
            self.history_index -= 1

        # Update buttons
        self.undo_btn.setEnabled(self.history_index >= 0)
        self.redo_btn.setEnabled(False)

    def undo(self):
        """# Hoàn tác lệnh cuối"""
        if self.history_index < 0:
            return

        command = self.command_history[self.history_index]

        if command["type"] == "move":
            # Undo move
            self.db.execute_query(
                "UPDATE exercise_tree SET parent_id = ? WHERE id = ?",
                (command["old_parent_id"], command["node_id"])
            )
        elif command["type"] == "add":
            # Undo add (delete)
            self.db.execute_query(
                "DELETE FROM exercise_tree WHERE id = ?",
                (command["node_id"],)
            )
        elif command["type"] == "delete":
            # Undo delete (restore)
            self._restore_deleted_node(command)
        elif command["type"] == "edit":
            # Undo edit
            self._restore_node_state(command["node_id"], command["old_data"])

        self.history_index -= 1
        self.refresh_tree()

        # Update buttons
        self.undo_btn.setEnabled(self.history_index >= 0)
        self.redo_btn.setEnabled(True)

        self.status_bar.setText("Đã hoàn tác")

    def redo(self):
        """# Làm lại lệnh"""
        if self.history_index >= len(self.command_history) - 1:
            return

        self.history_index += 1
        command = self.command_history[self.history_index]

        if command["type"] == "move":
            # Redo move
            self.db.execute_query(
                "UPDATE exercise_tree SET parent_id = ? WHERE id = ?",
                (command["new_parent_id"], command["node_id"])
            )
        elif command["type"] == "add":
            # Redo add
            self._restore_node_state(command["node_id"], command["new_data"])
        elif command["type"] == "delete":
            # Redo delete
            self.db.execute_query(
                "DELETE FROM exercise_tree WHERE id = ?",
                (command["node_id"],)
            )
        elif command["type"] == "edit":
            # Redo edit
            self._restore_node_state(command["node_id"], command["new_data"])

        self.refresh_tree()

        # Update buttons
        self.undo_btn.setEnabled(True)
        self.redo_btn.setEnabled(self.history_index < len(self.command_history) - 1)

        self.status_bar.setText("Đã làm lại")

    # ======================= CRUD OPERATIONS =======================

    def add_node(self):
        """# Thêm node mới"""
        selected_items = self.tree.selectedItems()
        parent_id = None

        if selected_items:
            parent_id = selected_items[0].data(0, Qt.UserRole)

        dialog = ModernAddNodeDialog(self.db, parent=self)
        if parent_id:
            dialog.set_parent(parent_id)

        if dialog.exec() == QtWidgets.QDialog.Accepted:
            # Get new node data for history
            node_data = dialog.get_node_data()

            # Add command to history
            command = {
                "type": "add",
                "node_id": dialog.new_node_id,
                "new_data": node_data,
                "timestamp": datetime.now().isoformat()
            }
            self._add_command_to_history(command)

            self.refresh_tree()
            self.status_bar.setText(f"Đã thêm '{node_data['name']}'")

    def edit_node(self):
        """# Sửa node"""
        selected_items = self.tree.selectedItems()
        if not selected_items:
            return

        node_id = selected_items[0].data(0, Qt.UserRole)

        # Save old data for undo
        old_data = self._get_node_data(node_id)

        dialog = ModernEditNodeDialog(self.db, node_id, parent=self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            new_data = self._get_node_data(node_id)

            # Add command to history
            command = {
                "type": "edit",
                "node_id": node_id,
                "old_data": old_data,
                "new_data": new_data,
                "timestamp": datetime.now().isoformat()
            }
            self._add_command_to_history(command)

            self.refresh_tree()
            self.status_bar.setText(f"Đã sửa '{new_data['name']}'")

    def delete_node(self):
        """# Xóa node với confirmation"""
        selected_items = self.tree.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        node_id = item.data(0, Qt.UserRole)
        node_name = item.text(0)

        # Check for children
        children_count = self._count_children(node_id)
        if children_count > 0:
            reply = QtWidgets.QMessageBox.question(
                self, "Xác nhận xóa",
                f"Node '{node_name}' có {children_count} node con.\n"
                f"Bạn có muốn xóa tất cả không?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
        else:
            reply = QtWidgets.QMessageBox.question(
                self, "Xác nhận xóa",
                f"Bạn có chắc muốn xóa node '{node_name}'?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )

        if reply == QtWidgets.QMessageBox.Yes:
            # Save data for undo
            deleted_data = self._get_deleted_tree_data(node_id)

            # Delete from database
            self.db.execute_query("DELETE FROM exercise_tree WHERE id = ?", (node_id,))

            # Add command to history
            command = {
                "type": "delete",
                "node_id": node_id,
                "deleted_data": deleted_data,
                "timestamp": datetime.now().isoformat()
            }
            self._add_command_to_history(command)

            self.refresh_tree()
            self.status_bar.setText(f"Đã xóa '{node_name}'")

    def copy_node(self):
        """# Sao chép node vào clipboard"""
        selected_items = self.tree.selectedItems()
        if not selected_items:
            return

        node_id = selected_items[0].data(0, Qt.UserRole)
        self.clipboard_data = self._get_node_data(node_id)
        self.paste_btn.setEnabled(True)
        self.status_bar.setText(f"Đã sao chép '{self.clipboard_data['name']}'")

    def paste_node(self):
        """# Dán node từ clipboard"""
        if not self.clipboard_data:
            return

        selected_items = self.tree.selectedItems()
        parent_id = None

        if selected_items:
            parent_id = selected_items[0].data(0, Qt.UserRole)

        # Create new node
        new_name = f"{self.clipboard_data['name']} (Sao chép)"

        self.db.execute_query(
            """INSERT INTO exercise_tree 
               (parent_id, name, level, description, icon, color, is_active, metadata) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (parent_id, new_name, self.clipboard_data['level'],
             self.clipboard_data['description'], self.clipboard_data['icon'],
             self.clipboard_data['color'], self.clipboard_data['is_active'],
             self.clipboard_data['metadata'])
        )

        self.refresh_tree()
        self.status_bar.setText(f"Đã dán '{new_name}'")

    def save_current_node(self):
        """# Lưu thông tin node hiện tại"""
        selected_items = self.tree.selectedItems()
        if not selected_items:
            return

        node_id = selected_items[0].data(0, Qt.UserRole)

        # Validate data
        name = self.name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Tên node không được để trống.")
            return

        # Validate JSON metadata
        metadata_text = self.metadata_edit.toPlainText().strip()
        if metadata_text:
            try:
                json.loads(metadata_text)
            except json.JSONDecodeError:
                QtWidgets.QMessageBox.warning(self, "Lỗi", "Metadata phải là JSON hợp lệ.")
                return
        else:
            metadata_text = "{}"

        # Save old data for undo
        old_data = self._get_node_data(node_id)

        # Update database
        level = self.level_combo.currentText()
        description = self.description_edit.toPlainText().strip()
        icon = self.icon_edit.text().strip()
        is_active = self.active_checkbox.isChecked()

        self.db.execute_query(
            """UPDATE exercise_tree 
               SET name = ?, level = ?, description = ?, icon = ?, 
                   color = ?, is_active = ?, metadata = ?
               WHERE id = ?""",
            (name, level, description, icon, self.current_color,
             is_active, metadata_text, node_id)
        )

        # Add command to history
        new_data = self._get_node_data(node_id)
        command = {
            "type": "edit",
            "node_id": node_id,
            "old_data": old_data,
            "new_data": new_data,
            "timestamp": datetime.now().isoformat()
        }
        self._add_command_to_history(command)

        # Update tree item
        item = selected_items[0]
        item.setText(0, f"{icon} {name}" if icon else name)
        item.setText(1, level)
        item.setText(2, "✓" if is_active else "✗")
        item.setText(3, description)

        self.status_bar.setText(f"Đã lưu '{name}'")

    # ======================= IMPORT/EXPORT =======================

    def import_data(self):
        """# Import dữ liệu từ file"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import dữ liệu", "",
            "JSON Files (*.json);;CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return

        try:
            if file_path.endswith('.json'):
                self._import_json(file_path)
            elif file_path.endswith('.csv'):
                self._import_csv(file_path)
            else:
                QtWidgets.QMessageBox.warning(self, "Lỗi", "Định dạng file không được hỗ trợ.")
                return

            self.refresh_tree()
            self.status_bar.setText("Import thành công")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi Import", f"Không thể import file: {e}")

    def export_data(self):
        """# Export dữ liệu ra file"""
        file_path, file_type = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export dữ liệu", "",
            "JSON Files (*.json);;CSV Files (*.csv)"
        )

        if not file_path:
            return

        try:
            if "JSON" in file_type:
                self._export_json(file_path)
            elif "CSV" in file_type:
                self._export_csv(file_path)

            self.status_bar.setText(f"Đã export: {os.path.basename(file_path)}")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi Export", f"Không thể export file: {e}")

    def _import_json(self, file_path: str):
        """# Import từ JSON file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Clear existing data if requested
        reply = QtWidgets.QMessageBox.question(
            self, "Import JSON",
            "Bạn có muốn xóa dữ liệu hiện tại trước khi import?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            self.db.execute_query("DELETE FROM exercise_tree")

        # Import data recursively
        self._import_json_recursive(data, None)

    def _import_json_recursive(self, nodes: List[Dict], parent_id: Optional[int]):
        """# Import JSON đệ quy"""
        for node_data in nodes:
            # Insert node
            cursor = self.db.execute_query(
                """INSERT INTO exercise_tree 
                   (parent_id, name, level, description, icon, color, is_active, metadata) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (parent_id, node_data.get('name', ''), node_data.get('level', 'Môn'),
                 node_data.get('description', ''), node_data.get('icon', ''),
                 node_data.get('color', '#2E86AB'), node_data.get('is_active', True),
                 json.dumps(node_data.get('metadata', {}))),
                return_cursor=True
            )

            new_id = cursor.lastrowid

            # Import children
            children = node_data.get('children', [])
            if children:
                self._import_json_recursive(children, new_id)

    def _export_json(self, file_path: str):
        """# Export ra JSON file"""
        data = self._export_tree_to_dict()

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _export_tree_to_dict(self) -> List[Dict]:
        """# Export tree thành dictionary"""
        # Get root nodes
        root_nodes = self.db.execute_query(
            """SELECT id, name, level, description, icon, color, is_active, metadata
               FROM exercise_tree WHERE parent_id IS NULL
               ORDER BY sort_order, name""",
            fetch="all"
        ) or []

        result = []
        for node in root_nodes:
            node_dict = {
                "name": node["name"],
                "level": node["level"],
                "description": node["description"] or "",
                "icon": node["icon"] or "",
                "color": node["color"] or "#2E86AB",
                "is_active": bool(node["is_active"]),
                "metadata": json.loads(node["metadata"] or "{}"),
                "children": self._export_children_to_dict(node["id"])
            }
            result.append(node_dict)

        return result

    def _export_children_to_dict(self, parent_id: int) -> List[Dict]:
        """# Export children đệ quy"""
        children = self.db.execute_query(
            """SELECT id, name, level, description, icon, color, is_active, metadata
               FROM exercise_tree WHERE parent_id = ?
               ORDER BY sort_order, name""",
            (parent_id,), fetch="all"
        ) or []

        result = []
        for child in children:
            child_dict = {
                "name": child["name"],
                "level": child["level"],
                "description": child["description"] or "",
                "icon": child["icon"] or "",
                "color": child["color"] or "#2E86AB",
                "is_active": bool(child["is_active"]),
                "metadata": json.loads(child["metadata"] or "{}"),
                "children": self._export_children_to_dict(child["id"])
            }
            result.append(child_dict)

        return result

    # ======================= UTILITY METHODS =======================

    def _load_tree(self):
        """# Tải cây từ database"""
        self.tree.clear()
        self.tree_nodes.clear()

        # Lấy tất cả nodes
        rows = self.db.execute_query(
            """SELECT id, parent_id, name, level, description, icon, color, is_active
               FROM exercise_tree ORDER BY sort_order, level, name""",
            fetch="all"
        ) or []

        # Tạo dictionary để nhóm theo parent
        children_map: Dict[Optional[int], List[dict]] = {}
        for row in rows:
            parent_id = row["parent_id"]
            if parent_id not in children_map:
                children_map[parent_id] = []
            children_map[parent_id].append(row)

        # Build tree recursively
        self._build_tree_recursive(None, children_map)

        # Expand first level
        self.tree.expandToDepth(0)

        # Update status
        total_count = len(rows)
        self.status_bar.setText(f"Tải {total_count} mục")

    def _build_tree_recursive(self, parent_id: Optional[int],
                              children_map: Dict[Optional[int], List[dict]],
                              parent_item: Optional[QtWidgets.QTreeWidgetItem] = None):
        """# Xây dựng cây đệ quy"""
        if parent_id not in children_map:
            return

        for row in children_map[parent_id]:
            # Create tree item
            icon = row["icon"] or ""
            name = row["name"]
            display_name = f"{icon} {name}" if icon else name

            item = QtWidgets.QTreeWidgetItem([
                display_name,
                row["level"],
                "✓" if row["is_active"] else "✗",
                row["description"] or ""
            ])

            # Store node ID
            item.setData(0, Qt.UserRole, row["id"])

            # Set color
            color = QtGui.QColor(row["color"] or "#2E86AB")
            item.setForeground(0, color)

            # Add to parent
            if parent_item:
                parent_item.addChild(item)
            else:
                self.tree.addTopLevelItem(item)

            # Store in nodes map
            self.tree_nodes[row["id"]] = item

            # Build children
            self._build_tree_recursive(row["id"], children_map, item)

    def refresh_tree(self):
        """# Làm mới cây"""
        self._load_tree()
        self.set_form_enabled(False)

    def expand_all(self):
        """# Mở rộng tất cả"""
        self.tree.expandAll()
        self.status_bar.setText("Đã mở rộng tất cả")

    def collapse_all(self):
        """# Thu gọn tất cả"""
        self.tree.collapseAll()
        self.status_bar.setText("Đã thu gọn tất cả")

    def show_context_menu(self, position):
        """# Hiển thị context menu"""
        item = self.tree.itemAt(position)
        if not item:
            return

        menu = QtWidgets.QMenu(self)

        # Add child
        add_child_action = menu.addAction("➕ Thêm node con")
        add_child_action.triggered.connect(lambda: self.add_child_node(item))

        menu.addSeparator()

        # Edit
        edit_action = menu.addAction("✏️ Sửa")
        edit_action.triggered.connect(self.edit_node)

        # Copy
        copy_action = menu.addAction("📋 Sao chép")
        copy_action.triggered.connect(self.copy_node)

        # Paste (if clipboard has data)
        if self.clipboard_data:
            paste_action = menu.addAction("📄 Dán vào đây")
            paste_action.triggered.connect(lambda: self.paste_to_node(item))

        menu.addSeparator()

        # Delete
        delete_action = menu.addAction("🗑️ Xóa")
        delete_action.triggered.connect(self.delete_node)

        menu.exec(self.tree.mapToGlobal(position))

    def add_child_node(self, parent_item):
        """# Thêm node con"""
        parent_id = parent_item.data(0, Qt.UserRole)

        dialog = ModernAddNodeDialog(self.db, parent=self)
        dialog.set_parent(parent_id)

        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.refresh_tree()
            # Expand parent để thấy node mới
            parent_item.setExpanded(True)

    def paste_to_node(self, parent_item):
        """# Dán vào node cụ thể"""
        if not self.clipboard_data:
            return

        parent_id = parent_item.data(0, Qt.UserRole)

        # Create new node
        new_name = f"{self.clipboard_data['name']} (Sao chép)"

        self.db.execute_query(
            """INSERT INTO exercise_tree 
               (parent_id, name, level, description, icon, color, is_active, metadata) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (parent_id, new_name, self.clipboard_data['level'],
             self.clipboard_data['description'], self.clipboard_data['icon'],
             self.clipboard_data['color'], self.clipboard_data['is_active'],
             self.clipboard_data['metadata'])
        )

        self.refresh_tree()
        parent_item.setExpanded(True)
        self.status_bar.setText(f"Đã dán '{new_name}' vào '{parent_item.text(0)}'")

    # ======================= HELPER METHODS =======================

    def _get_node_data(self, node_id: int) -> Dict:
        """# Lấy dữ liệu node"""
        row = self.db.execute_query(
            """SELECT name, level, description, icon, color, is_active, metadata, parent_id
               FROM exercise_tree WHERE id = ?""",
            (node_id,), fetch="one"
        )

        if row:
            return {
                "name": row["name"],
                "level": row["level"],
                "description": row["description"] or "",
                "icon": row["icon"] or "",
                "color": row["color"] or "#2E86AB",
                "is_active": bool(row["is_active"]),
                "metadata": row["metadata"] or "{}",
                "parent_id": row["parent_id"]
            }
        return {}

    def _count_children(self, node_id: int) -> int:
        """# Đếm số node con"""
        row = self.db.execute_query(
            "SELECT COUNT(*) as count FROM exercise_tree WHERE parent_id = ?",
            (node_id,), fetch="one"
        )
        return row["count"] if row else 0

    def _get_deleted_tree_data(self, node_id: int) -> Dict:
        """# Lấy dữ liệu cây bị xóa (cho undo)"""
        # Get node and all descendants
        nodes = []
        self._collect_tree_data_recursive(node_id, nodes)
        return {"nodes": nodes}

    def _collect_tree_data_recursive(self, node_id: int, nodes: List[Dict]):
        """# Thu thập dữ liệu cây đệ quy"""
        # Get current node
        row = self.db.execute_query(
            """SELECT id, parent_id, name, level, description, icon, color, 
                      is_active, metadata, sort_order
               FROM exercise_tree WHERE id = ?""",
            (node_id,), fetch="one"
        )

        if row:
            nodes.append(dict(row))

            # Get children
            children = self.db.execute_query(
                "SELECT id FROM exercise_tree WHERE parent_id = ?",
                (node_id,), fetch="all"
            ) or []

            for child in children:
                self._collect_tree_data_recursive(child["id"], nodes)

    def _restore_deleted_node(self, command: Dict):
        """# Khôi phục node đã xóa"""
        nodes = command["deleted_data"]["nodes"]

        # Restore nodes in correct order (parents first)
        for node in nodes:
            self.db.execute_query(
                """INSERT INTO exercise_tree 
                   (id, parent_id, name, level, description, icon, color, 
                    is_active, metadata, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (node["id"], node["parent_id"], node["name"], node["level"],
                 node["description"], node["icon"], node["color"],
                 node["is_active"], node["metadata"], node["sort_order"])
            )

    def _restore_node_state(self, node_id: int, data: Dict):
        """# Khôi phục trạng thái node"""
        self.db.execute_query(
            """UPDATE exercise_tree 
               SET name = ?, level = ?, description = ?, icon = ?, 
                   color = ?, is_active = ?, metadata = ?
               WHERE id = ?""",
            (data["name"], data["level"], data["description"], data["icon"],
             data["color"], data["is_active"], data["metadata"], node_id)
        )


# ======================= DRAG & DROP TREE WIDGET =======================

class DragDropTreeWidget(QtWidgets.QTreeWidget):
    """Tree widget với drag & drop support"""

    item_moved = QtCore.Signal(QtWidgets.QTreeWidgetItem, object)  # item, new_parent_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)

    def dropEvent(self, event):
        """# Xử lý drop event"""
        if event.source() != self:
            return

        # Get dropped item
        drop_item = self.currentItem()
        if not drop_item:
            return

        # Get drop position
        drop_indicator = self.dropIndicatorPosition()
        target_item = self.itemAt(event.pos())

        # Determine new parent
        new_parent_id = None

        if target_item:
            if drop_indicator == QtWidgets.QAbstractItemView.OnItem:
                # Drop on item - make it a child
                new_parent_id = target_item.data(0, Qt.UserRole)
            elif drop_indicator in [QtWidgets.QAbstractItemView.AboveItem,
                                    QtWidgets.QAbstractItemView.BelowItem]:
                # Drop above/below item - same parent as target
                parent = target_item.parent()
                new_parent_id = parent.data(0, Qt.UserRole) if parent else None

        # Validate move (prevent moving to descendant)
        if self._is_descendant(drop_item, target_item):
            event.ignore()
            return

        # Accept the drop
        super().dropEvent(event)

        # Emit signal
        self.item_moved.emit(drop_item, new_parent_id)

    def _is_descendant(self, ancestor: QtWidgets.QTreeWidgetItem,
                       potential_descendant: QtWidgets.QTreeWidgetItem) -> bool:
        """# Kiểm tra xem item có phải là descendant không"""
        if not potential_descendant:
            return False

        current = potential_descendant.parent()
        while current:
            if current == ancestor:
                return True
            current = current.parent()
        return False


# ======================= MODERN DIALOGS =======================

class ModernAddNodeDialog(QtWidgets.QDialog):
    """Dialog thêm node hiện đại"""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.new_node_id = None
        self.setWindowTitle("➕ Thêm node mới")
        self.setModal(True)
        self.resize(500, 600)

        self._build_ui()
        self._apply_styles()

    def _build_ui(self):
        """# Xây dựng UI"""
        layout = QtWidgets.QVBoxLayout(self)

        # Header
        header = QtWidgets.QLabel("➕ Thêm node mới")
        header.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header)

        # Form
        form = QtWidgets.QFormLayout()

        # Parent selection
        self.parent_combo = QtWidgets.QComboBox()
        self.parent_combo.addItem("(Không có parent)", None)
        self._load_parent_options()

        # Basic fields
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("Nhập tên node...")

        self.level_combo = QtWidgets.QComboBox()
        self.level_combo.addItems(["Môn", "Lớp", "Chủ đề", "Dạng", "Mức độ"])

        # Icon picker with suggestions
        icon_layout = QtWidgets.QHBoxLayout()
        self.icon_edit = QtWidgets.QLineEdit()
        self.icon_edit.setPlaceholderText("📊 (emoji icon)")

        icon_suggestions = ["📊", "📚", "📋", "📈", "📐", "🎓", "⚛️", "🧪"]
        for icon in icon_suggestions:
            btn = QtWidgets.QPushButton(icon)
            btn.setFixedSize(30, 30)
            btn.clicked.connect(lambda checked, i=icon: self.icon_edit.setText(i))
            icon_layout.addWidget(btn)

        icon_layout.addStretch()
        icon_widget = QtWidgets.QWidget()
        icon_widget.setLayout(icon_layout)

        # Color picker
        self.color_btn = QtWidgets.QPushButton("Chọn màu")
        self.color_btn.setFixedSize(100, 30)
        self.color_btn.clicked.connect(self.pick_color)
        self.current_color = "#2E86AB"
        self._update_color_button()

        # Active checkbox
        self.active_checkbox = QtWidgets.QCheckBox("Đang hoạt động")
        self.active_checkbox.setChecked(True)

        # Description
        self.description_edit = QtWidgets.QTextEdit()
        self.description_edit.setMaximumHeight(100)
        self.description_edit.setPlaceholderText("Mô tả chi tiết...")

        # Metadata
        self.metadata_edit = QtWidgets.QTextEdit()
        self.metadata_edit.setMaximumHeight(80)
        self.metadata_edit.setPlaceholderText('{"key": "value"}')
        self.metadata_edit.setText("{}")

        # Add to form
        form.addRow("Node cha:", self.parent_combo)
        form.addRow("Tên:", self.name_edit)
        form.addRow("Cấp độ:", self.level_combo)
        form.addRow("Icon:", self.icon_edit)
        form.addRow("", icon_widget)
        form.addRow("Màu sắc:", self.color_btn)
        form.addRow("", self.active_checkbox)
        form.addRow("Mô tả:", self.description_edit)
        form.addRow("Metadata:", self.metadata_edit)

        layout.addLayout(form)

        # Buttons
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Focus on name
        self.name_edit.setFocus()

    def _apply_styles(self):
        """# Áp dụng styles"""
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLineEdit, QComboBox, QTextEdit {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 8px;
                background-color: white;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border-color: #2E86AB;
                outline: none;
            }
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                border-color: #2E86AB;
            }
        """)

    def _load_parent_options(self):
        """# Load danh sách parent có thể chọn"""
        rows = self.db.execute_query(
            """SELECT id, name, level FROM exercise_tree 
               ORDER BY level, name""",
            fetch="all"
        ) or []

        for row in rows:
            self.parent_combo.addItem(
                f"{row['name']} ({row['level']})",
                row["id"]
            )

    def set_parent(self, parent_id: int):
        """# Đặt parent được chọn"""
        for i in range(self.parent_combo.count()):
            if self.parent_combo.itemData(i) == parent_id:
                self.parent_combo.setCurrentIndex(i)
                break

    def pick_color(self):
        """# Chọn màu sắc"""
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.current_color), self)
        if color.isValid():
            self.current_color = color.name()
            self._update_color_button()

    def _update_color_button(self):
        """# Cập nhật button màu"""
        self.color_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.current_color};
                color: white;
                border: 2px solid #333;
                border-radius: 4px;
                font-weight: bold;
            }}
        """)

    def accept(self):
        """# Xử lý khi accept"""
        # Validate
        name = self.name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Tên node không được để trống.")
            return

        # Validate JSON
        metadata_text = self.metadata_edit.toPlainText().strip()
        try:
            json.loads(metadata_text)
        except json.JSONDecodeError:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Metadata phải là JSON hợp lệ.")
            return

        # Get data
        parent_id = self.parent_combo.currentData()
        level = self.level_combo.currentText()
        description = self.description_edit.toPlainText().strip()
        icon = self.icon_edit.text().strip()
        is_active = self.active_checkbox.isChecked()

        try:
            # Insert to database
            cursor = self.db.execute_query(
                """INSERT INTO exercise_tree 
                   (parent_id, name, level, description, icon, color, is_active, metadata) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (parent_id, name, level, description, icon, self.current_color,
                 is_active, metadata_text),
                return_cursor=True
            )

            self.new_node_id = cursor.lastrowid
            super().accept()

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể thêm node: {e}")

    def get_node_data(self) -> Dict:
        """# Lấy dữ liệu node đã tạo"""
        return {
            "name": self.name_edit.text().strip(),
            "level": self.level_combo.currentText(),
            "description": self.description_edit.toPlainText().strip(),
            "icon": self.icon_edit.text().strip(),
            "color": self.current_color,
            "is_active": self.active_checkbox.isChecked(),
            "metadata": self.metadata_edit.toPlainText().strip(),
            "parent_id": self.parent_combo.currentData()
        }


class ModernEditNodeDialog(QtWidgets.QDialog):
    """Dialog sửa node hiện đại"""

    def __init__(self, db_manager, node_id: int, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.node_id = node_id
        self.setWindowTitle("✏️ Sửa node")
        self.setModal(True)
        self.resize(500, 600)

        self._build_ui()
        self._load_data()
        self._apply_styles()

    def _build_ui(self):
        """# Xây dựng UI"""
        layout = QtWidgets.QVBoxLayout(self)

        # Header
        header = QtWidgets.QLabel("✏️ Sửa node")
        header.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header)

        # Form
        form = QtWidgets.QFormLayout()

        # Parent selection
        self.parent_combo = QtWidgets.QComboBox()
        self.parent_combo.addItem("(Không có parent)", None)
        self._load_parent_options()

        # Basic fields
        self.name_edit = QtWidgets.QLineEdit()
        self.level_combo = QtWidgets.QComboBox()
        self.level_combo.addItems(["Môn", "Lớp", "Chủ đề", "Dạng", "Mức độ"])

        # Icon picker
        icon_layout = QtWidgets.QHBoxLayout()
        self.icon_edit = QtWidgets.QLineEdit()

        icon_suggestions = ["📊", "📚", "📋", "📈", "📐", "🎓", "⚛️", "🧪"]
        for icon in icon_suggestions:
            btn = QtWidgets.QPushButton(icon)
            btn.setFixedSize(30, 30)
            btn.clicked.connect(lambda checked, i=icon: self.icon_edit.setText(i))
            icon_layout.addWidget(btn)

        icon_layout.addStretch()
        icon_widget = QtWidgets.QWidget()
        icon_widget.setLayout(icon_layout)

        # Color picker
        self.color_btn = QtWidgets.QPushButton("Chọn màu")
        self.color_btn.setFixedSize(100, 30)
        self.color_btn.clicked.connect(self.pick_color)
        self.current_color = "#2E86AB"

        # Active checkbox
        self.active_checkbox = QtWidgets.QCheckBox("Đang hoạt động")

        # Description
        self.description_edit = QtWidgets.QTextEdit()
        self.description_edit.setMaximumHeight(100)

        # Metadata
        self.metadata_edit = QtWidgets.QTextEdit()
        self.metadata_edit.setMaximumHeight(80)

        # Add to form
        form.addRow("Node cha:", self.parent_combo)
        form.addRow("Tên:", self.name_edit)
        form.addRow("Cấp độ:", self.level_combo)
        form.addRow("Icon:", self.icon_edit)
        form.addRow("", icon_widget)
        form.addRow("Màu sắc:", self.color_btn)
        form.addRow("", self.active_checkbox)
        form.addRow("Mô tả:", self.description_edit)
        form.addRow("Metadata:", self.metadata_edit)

        layout.addLayout(form)

        # Buttons
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply_styles(self):
        """# Áp dụng styles giống AddNodeDialog"""
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLineEdit, QComboBox, QTextEdit {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 8px;
                background-color: white;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border-color: #2E86AB;
                outline: none;
            }
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                border-color: #2E86AB;
            }
        """)

    def _load_parent_options(self):
        """# Load danh sách parent (trừ chính nó và descendants)"""
        # Lấy tất cả descendants
        descendants = self._get_all_descendants(self.node_id)
        descendants.add(self.node_id)  # Thêm chính nó

        rows = self.db.execute_query(
            "SELECT id, name, level FROM exercise_tree ORDER BY level, name",
            fetch="all"
        ) or []

        for row in rows:
            if row["id"] not in descendants:
                self.parent_combo.addItem(
                    f"{row['name']} ({row['level']})",
                    row["id"]
                )

    def _get_all_descendants(self, node_id: int) -> set:
        """# Lấy tất cả descendants"""
        descendants = set()

        children = self.db.execute_query(
            "SELECT id FROM exercise_tree WHERE parent_id = ?",
            (node_id,), fetch="all"
        ) or []

        for child in children:
            child_id = child["id"]
            descendants.add(child_id)
            descendants.update(self._get_all_descendants(child_id))

        return descendants

    def _load_data(self):
        """# Load dữ liệu node hiện tại"""
        row = self.db.execute_query(
            """SELECT parent_id, name, level, description, icon, color, 
                      is_active, metadata FROM exercise_tree WHERE id = ?""",
            (self.node_id,), fetch="one"
        )

        if row:
            # Set parent
            parent_id = row["parent_id"]
            for i in range(self.parent_combo.count()):
                if self.parent_combo.itemData(i) == parent_id:
                    self.parent_combo.setCurrentIndex(i)
                    break

            # Set other fields
            self.name_edit.setText(row["name"] or "")
            self.level_combo.setCurrentText(row["level"] or "Môn")
            self.icon_edit.setText(row["icon"] or "")
            self.current_color = row["color"] or "#2E86AB"
            self._update_color_button()
            self.active_checkbox.setChecked(bool(row["is_active"]))
            self.description_edit.setPlainText(row["description"] or "")
            self.metadata_edit.setPlainText(row["metadata"] or "{}")

    def pick_color(self):
        """# Chọn màu sắc"""
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.current_color), self)
        if color.isValid():
            self.current_color = color.name()
            self._update_color_button()

    def _update_color_button(self):
        """# Cập nhật button màu"""
        self.color_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.current_color};
                color: white;
                border: 2px solid #333;
                border-radius: 4px;
                font-weight: bold;
            }}
        """)

    def accept(self):
        """# Xử lý khi accept"""
        # Validate
        name = self.name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Tên node không được để trống.")
            return

        # Validate JSON
        metadata_text = self.metadata_edit.toPlainText().strip()
        try:
            json.loads(metadata_text)
        except json.JSONDecodeError:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Metadata phải là JSON hợp lệ.")
            return

        # Get data
        parent_id = self.parent_combo.currentData()
        level = self.level_combo.currentText()
        description = self.description_edit.toPlainText().strip()
        icon = self.icon_edit.text().strip()
        is_active = self.active_checkbox.isChecked()

        try:
            # Update database
            self.db.execute_query(
                """UPDATE exercise_tree 
                   SET parent_id = ?, name = ?, level = ?, description = ?, 
                       icon = ?, color = ?, is_active = ?, metadata = ?
                   WHERE id = ?""",
                (parent_id, name, level, description, icon, self.current_color,
                 is_active, metadata_text, self.node_id)
            )

            super().accept()

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể cập nhật node: {e}")