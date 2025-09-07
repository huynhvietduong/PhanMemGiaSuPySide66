"""
Widget lọc và tìm kiếm cho ngân hàng câu hỏi
Tách từ _create_filter_controls và quick_search trong file gốc
"""

from typing import Dict, Any
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QGroupBox,
    QCheckBox, QSlider, QSpinBox
)


class FilterWidget(QWidget):
    """Widget lọc và tìm kiếm câu hỏi"""

    # Signals
    filters_changed = Signal(dict)  # Phát tín hiệu khi filter thay đổi
    search_requested = Signal(str)  # Phát tín hiệu khi tìm kiếm

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.current_filters = {}

        self._setup_ui()
        self._setup_connections()
        self._load_filter_data()

    def _setup_ui(self):
        """Thiết lập giao diện filter"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # Tiêu đề
        title_label = QLabel("🔍 Tìm kiếm & Lọc")
        title_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 14px;
                color: #2c3e50;
                padding: 5px;
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
            }
        """)
        layout.addWidget(title_label)

        # Nhóm tìm kiếm
        self._create_search_group(layout)

        # Nhóm filter cơ bản
        self._create_basic_filter_group(layout)

        # Nhóm filter nâng cao
        self._create_advanced_filter_group(layout)

        # Buttons
        self._create_action_buttons(layout)

        layout.addStretch()

    def _create_search_group(self, layout: QVBoxLayout):
        """Tạo nhóm tìm kiếm"""
        search_group = QGroupBox("🔍 Tìm kiếm")
        search_layout = QVBoxLayout(search_group)

        # Ô tìm kiếm chính
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Tìm theo nội dung, tags...")
        self.search_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #e3f2fd;
                border-radius: 6px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #2196f3;
                background: #fafafa;
            }
        """)
        search_layout.addWidget(self.search_edit)

        # Tùy chọn tìm kiếm
        search_options_layout = QHBoxLayout()

        self.fuzzy_search_cb = QCheckBox("Tìm mờ")
        self.fuzzy_search_cb.setToolTip("Tìm kiếm gần đúng, bỏ qua lỗi chính tả")
        search_options_layout.addWidget(self.fuzzy_search_cb)

        self.case_sensitive_cb = QCheckBox("Phân biệt hoa thường")
        search_options_layout.addWidget(self.case_sensitive_cb)

        search_options_layout.addStretch()
        search_layout.addLayout(search_options_layout)

        layout.addWidget(search_group)

    def _create_basic_filter_group(self, layout: QVBoxLayout):
        """Tạo nhóm filter cơ bản"""
        basic_group = QGroupBox("📋 Lọc cơ bản")
        basic_layout = QFormLayout(basic_group)
        basic_layout.setLabelAlignment(Qt.AlignRight)

        # Lọc theo môn học
        self.subject_cb = QComboBox()
        self.subject_cb.setMinimumWidth(150)
        basic_layout.addRow("📚 Môn:", self.subject_cb)

        # Lọc theo lớp
        self.grade_cb = QComboBox()
        self.grade_cb.setMinimumWidth(150)
        basic_layout.addRow("🎓 Lớp:", self.grade_cb)

        # Lọc theo chủ đề
        self.topic_cb = QComboBox()
        self.topic_cb.setMinimumWidth(150)
        basic_layout.addRow("📖 Chủ đề:", self.topic_cb)

        # Lọc theo dạng bài
        self.type_cb = QComboBox()
        self.type_cb.setMinimumWidth(150)
        basic_layout.addRow("📝 Dạng bài:", self.type_cb)

        layout.addWidget(basic_group)

    def _create_advanced_filter_group(self, layout: QVBoxLayout):
        """Tạo nhóm filter nâng cao"""
        advanced_group = QGroupBox("⚙️ Lọc nâng cao")
        advanced_layout = QVBoxLayout(advanced_group)

        # Filter theo mức độ
        level_layout = QFormLayout()
        self.level_cb = QComboBox()
        self.level_cb.addItems([
            "Tất cả mức độ",
            "🟢 Nhận biết",
            "🟡 Thông hiểu",
            "🟠 Vận dụng",
            "🔴 Vận dụng cao"
        ])
        level_layout.addRow("📊 Mức độ:", self.level_cb)
        advanced_layout.addLayout(level_layout)

        # Filter theo độ khó (slider)
        difficulty_layout = QVBoxLayout()
        difficulty_layout.addWidget(QLabel("🎯 Độ khó:"))

        self.difficulty_slider = QSlider(Qt.Horizontal)
        self.difficulty_slider.setRange(1, 5)
        self.difficulty_slider.setValue(1)
        self.difficulty_slider.setTickPosition(QSlider.TicksBelow)
        self.difficulty_slider.setTickInterval(1)

        difficulty_labels_layout = QHBoxLayout()
        difficulty_labels = ["Rất dễ", "Dễ", "TB", "Khó", "Rất khó"]
        for label in difficulty_labels:
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("font-size: 10px; color: #666;")
            difficulty_labels_layout.addWidget(lbl)

        difficulty_layout.addWidget(self.difficulty_slider)
        difficulty_layout.addLayout(difficulty_labels_layout)
        advanced_layout.addLayout(difficulty_layout)

        # Filter theo loại nội dung
        content_type_layout = QFormLayout()
        self.content_type_cb = QComboBox()
        self.content_type_cb.addItems([
            "Tất cả loại",
            "📝 Text",
            "🖼️ Hình ảnh",
            "📄 PDF",
            "📘 Word"
        ])
        content_type_layout.addRow("💾 Loại nội dung:", self.content_type_cb)
        advanced_layout.addLayout(content_type_layout)

        # Filter theo thời gian tạo
        date_layout = QVBoxLayout()
        date_layout.addWidget(QLabel("📅 Thời gian tạo:"))

        date_range_layout = QHBoxLayout()
        self.date_from_cb = QComboBox()
        self.date_from_cb.addItems([
            "Bất kỳ",
            "Hôm nay",
            "7 ngày qua",
            "30 ngày qua",
            "90 ngày qua",
            "1 năm qua"
        ])
        date_range_layout.addWidget(self.date_from_cb)

        date_layout.addLayout(date_range_layout)
        advanced_layout.addLayout(date_layout)

        # Filter theo trạng thái
        status_layout = QVBoxLayout()
        status_layout.addWidget(QLabel("📌 Trạng thái:"))

        status_checkboxes_layout = QHBoxLayout()
        self.active_cb = QCheckBox("Đang dùng")
        self.active_cb.setChecked(True)
        self.draft_cb = QCheckBox("Nháp")
        self.archived_cb = QCheckBox("Lưu trữ")

        status_checkboxes_layout.addWidget(self.active_cb)
        status_checkboxes_layout.addWidget(self.draft_cb)
        status_checkboxes_layout.addWidget(self.archived_cb)

        status_layout.addLayout(status_checkboxes_layout)
        advanced_layout.addLayout(status_layout)

        layout.addWidget(advanced_group)

    def _create_action_buttons(self, layout: QVBoxLayout):
        """Tạo các nút hành động"""
        buttons_layout = QVBoxLayout()

        # Nút áp dụng filter
        apply_btn = QPushButton("🔄 Áp dụng lọc")
        apply_btn.setStyleSheet("""
            QPushButton {
                background: #28a745;
                color: white;
                font-weight: bold;
                padding: 8px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #218838;
            }
            QPushButton:pressed {
                background: #1e7e34;
            }
        """)
        apply_btn.clicked.connect(self.apply_filters)
        buttons_layout.addWidget(apply_btn)

        # Nút xóa filter
        clear_btn = QPushButton("🗑️ Xóa lọc")
        clear_btn.setStyleSheet("""
            QPushButton {
                background: #6c757d;
                color: white;
                padding: 6px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #5a6268;
            }
        """)
        clear_btn.clicked.connect(self.clear_filters)
        buttons_layout.addWidget(clear_btn)

        # Nút lưu preset
        save_preset_btn = QPushButton("💾 Lưu bộ lọc")
        save_preset_btn.clicked.connect(self.save_filter_preset)
        buttons_layout.addWidget(save_preset_btn)

        layout.addLayout(buttons_layout)

    def _setup_connections(self):
        """Thiết lập kết nối signals"""
        # Kết nối search với timer để tránh search quá nhiều
        self.search_timer = QtCore.QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_search)

        self.search_edit.textChanged.connect(self._on_search_text_changed)

        # Kết nối các filter comboboxes
        self.subject_cb.currentTextChanged.connect(self._on_subject_changed)
        self.grade_cb.currentTextChanged.connect(self._on_grade_changed)
        self.topic_cb.currentTextChanged.connect(self.apply_filters)
        self.type_cb.currentTextChanged.connect(self.apply_filters)
        self.level_cb.currentTextChanged.connect(self.apply_filters)
        self.content_type_cb.currentTextChanged.connect(self.apply_filters)
        self.date_from_cb.currentTextChanged.connect(self.apply_filters)

        # Kết nối difficulty slider
        self.difficulty_slider.valueChanged.connect(self.apply_filters)

        # Kết nối checkboxes
        self.active_cb.toggled.connect(self.apply_filters)
        self.draft_cb.toggled.connect(self.apply_filters)
        self.archived_cb.toggled.connect(self.apply_filters)
        self.fuzzy_search_cb.toggled.connect(self._perform_search)
        self.case_sensitive_cb.toggled.connect(self._perform_search)

    def _load_filter_data(self):
        """Load dữ liệu cho các filter combobox"""
        try:
            # Load subjects (môn học)
            self._load_subjects()

            # Load grades (lớp)
            self._load_grades()

        except Exception as e:
            print(f"Lỗi load filter data: {e}")

    def _load_subjects(self):
        """Load danh sách môn học"""
        try:
            rows = self.db.execute_query(
                "SELECT DISTINCT name FROM exercise_tree WHERE level='Môn' ORDER BY name ASC",
                fetch="all"
            ) or []

            self.subject_cb.clear()
            self.subject_cb.addItem("Tất cả môn")

            for row in rows:
                self.subject_cb.addItem(row["name"])

        except Exception as e:
            print(f"Lỗi load subjects: {e}")

    def _load_grades(self):
        """Load danh sách lớp"""
        try:
            rows = self.db.execute_query(
                "SELECT DISTINCT name FROM exercise_tree WHERE level='Lớp' ORDER BY name ASC",
                fetch="all"
            ) or []

            self.grade_cb.clear()
            self.grade_cb.addItem("Tất cả lớp")

            for row in rows:
                self.grade_cb.addItem(row["name"])

        except Exception as e:
            print(f"Lỗi load grades: {e}")

    def _load_topics(self, subject: str, grade: str):
        """Load chủ đề theo môn và lớp"""
        try:
            self.topic_cb.clear()
            self.topic_cb.addItem("Tất cả chủ đề")

            if not subject or subject == "Tất cả môn" or not grade or grade == "Tất cả lớp":
                return

            # Tìm chủ đề thuộc về môn và lớp được chọn
            rows = self.db.execute_query("""
                SELECT name FROM exercise_tree 
                WHERE level='Chủ đề' AND parent_id IN (
                    SELECT id FROM exercise_tree 
                    WHERE name=? AND parent_id IN (
                        SELECT id FROM exercise_tree WHERE name=?
                    )
                )
                ORDER BY name ASC
            """, (grade, subject), fetch="all") or []

            for row in rows:
                self.topic_cb.addItem(row["name"])

        except Exception as e:
            print(f"Lỗi load topics: {e}")

    def _load_types(self, subject: str, grade: str, topic: str):
        """Load dạng bài theo môn, lớp, chủ đề"""
        try:
            self.type_cb.clear()
            self.type_cb.addItem("Tất cả dạng")

            if not all([subject, grade, topic]) or any([
                subject == "Tất cả môn",
                grade == "Tất cả lớp",
                topic == "Tất cả chủ đề"
            ]):
                return

            # Tìm dạng bài thuộc chủ đề
            rows = self.db.execute_query("""
                SELECT name FROM exercise_tree 
                WHERE level='Mức độ' AND parent_id IN (
                    SELECT id FROM exercise_tree WHERE name=? AND level='Chủ đề'
                )
                ORDER BY name ASC
            """, (topic,), fetch="all") or []

            for row in rows:
                self.type_cb.addItem(row["name"])

        except Exception as e:
            print(f"Lỗi load types: {e}")

    # ========== EVENT HANDLERS ==========

    def _on_search_text_changed(self, text: str):
        """Xử lý khi text tìm kiếm thay đổi"""
        # Delay search để tránh search quá nhiều lần
        self.search_timer.stop()
        if len(text.strip()) >= 2:  # Tối thiểu 2 ký tự
            self.search_timer.start(500)  # Delay 500ms
        elif len(text.strip()) == 0:
            self._perform_search()  # Search ngay khi xóa hết

    def _on_subject_changed(self, subject: str):
        """Xử lý khi thay đổi môn học"""
        grade = self.grade_cb.currentText()
        self._load_topics(subject, grade)
        self.apply_filters()

    def _on_grade_changed(self, grade: str):
        """Xử lý khi thay đổi lớp"""
        subject = self.subject_cb.currentText()
        self._load_topics(subject, grade)
        self.apply_filters()

    def _perform_search(self):
        """Thực hiện tìm kiếm"""
        search_text = self.search_edit.text().strip()
        self.search_requested.emit(search_text)

    # ========== PUBLIC METHODS ==========

    def apply_filters(self):
        """Áp dụng tất cả filters"""
        filters = self.get_current_filters()
        self.current_filters = filters
        self.filters_changed.emit(filters)

    def get_current_filters(self) -> Dict[str, Any]:
        """Lấy filters hiện tại"""
        filters = {}

        # Basic filters
        if self.subject_cb.currentText() != "Tất cả môn":
            filters['subject'] = self.subject_cb.currentText()

        if self.grade_cb.currentText() != "Tất cả lớp":
            filters['grade'] = self.grade_cb.currentText()

        if self.topic_cb.currentText() != "Tất cả chủ đề":
            filters['topic'] = self.topic_cb.currentText()

        if self.type_cb.currentText() != "Tất cả dạng":
            filters['type'] = self.type_cb.currentText()

        # Advanced filters
        if self.level_cb.currentText() != "Tất cả mức độ":
            filters['level'] = self.level_cb.currentText()

        if self.content_type_cb.currentText() != "Tất cả loại":
            filters['content_type'] = self.content_type_cb.currentText()

        if self.date_from_cb.currentText() != "Bất kỳ":
            filters['date_range'] = self.date_from_cb.currentText()

        # Difficulty (luôn có giá trị)
        filters['difficulty'] = self.difficulty_slider.value()

        # Status filters
        status_filters = []
        if self.active_cb.isChecked():
            status_filters.append('active')
        if self.draft_cb.isChecked():
            status_filters.append('draft')
        if self.archived_cb.isChecked():
            status_filters.append('archived')

        if status_filters:
            filters['status'] = status_filters

        # Search options
        search_text = self.search_edit.text().strip()
        if search_text:
            filters['search_text'] = search_text
            filters['fuzzy_search'] = self.fuzzy_search_cb.isChecked()
            filters['case_sensitive'] = self.case_sensitive_cb.isChecked()

        return filters

    def clear_filters(self):
        """Xóa tất cả filters"""
        # Reset search
        self.search_edit.clear()
        self.fuzzy_search_cb.setChecked(False)
        self.case_sensitive_cb.setChecked(False)

        # Reset basic filters
        self.subject_cb.setCurrentIndex(0)
        self.grade_cb.setCurrentIndex(0)
        self.topic_cb.setCurrentIndex(0)
        self.type_cb.setCurrentIndex(0)

        # Reset advanced filters
        self.level_cb.setCurrentIndex(0)
        self.content_type_cb.setCurrentIndex(0)
        self.date_from_cb.setCurrentIndex(0)
        self.difficulty_slider.setValue(1)

        # Reset status
        self.active_cb.setChecked(True)
        self.draft_cb.setChecked(False)
        self.archived_cb.setChecked(False)

        # Apply empty filters
        self.apply_filters()

    def set_filters(self, filters: Dict[str, Any]):
        """Thiết lập filters từ bên ngoài"""
        # Block signals để tránh trigger nhiều lần
        self.blockSignals(True)

        try:
            # Set search
            if 'search_text' in filters:
                self.search_edit.setText(filters['search_text'])
                self.fuzzy_search_cb.setChecked(filters.get('fuzzy_search', False))
                self.case_sensitive_cb.setChecked(filters.get('case_sensitive', False))

            # Set basic filters
            if 'subject' in filters:
                index = self.subject_cb.findText(filters['subject'])
                if index >= 0:
                    self.subject_cb.setCurrentIndex(index)

            if 'grade' in filters:
                index = self.grade_cb.findText(filters['grade'])
                if index >= 0:
                    self.grade_cb.setCurrentIndex(index)

            # Set difficulty
            if 'difficulty' in filters:
                self.difficulty_slider.setValue(filters['difficulty'])

            # Apply filters
            self.current_filters = filters

        finally:
            self.blockSignals(False)
            self.filters_changed.emit(filters)

    def save_filter_preset(self):
        """Lưu preset filter hiện tại"""
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Lưu bộ lọc",
            "Tên bộ lọc:"
        )

        if ok and name.strip():
            # TODO: Implement save preset to database or config file
            QtWidgets.QMessageBox.information(
                self,
                "Thành công",
                f"Đã lưu bộ lọc '{name.strip()}'"
            )

    def get_filter_summary(self) -> str:
        """Lấy tóm tắt filters hiện tại"""
        filters = self.get_current_filters()
        if not filters:
            return "Không có bộ lọc nào"

        summary_parts = []

        if 'search_text' in filters:
            summary_parts.append(f"🔍 '{filters['search_text']}'")

        if 'subject' in filters:
            summary_parts.append(f"📚 {filters['subject']}")

        if 'grade' in filters:
            summary_parts.append(f"🎓 {filters['grade']}")

        if 'difficulty' in filters and filters['difficulty'] > 1:
            difficulty_names = ["", "Rất dễ", "Dễ", "Trung bình", "Khó", "Rất khó"]
            summary_parts.append(f"🎯 {difficulty_names[filters['difficulty']]}")

        return " | ".join(summary_parts) if summary_parts else "Bộ lọc trống"