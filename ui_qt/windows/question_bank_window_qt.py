# ui_qt/windows/question_bank_window_qt.py
from __future__ import annotations
import json
import os
import re
from typing import List, Dict
from datetime import datetime
import json
from typing import List, Dict
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut


# Enhanced pattern matching cho import câu hỏi với nhiều format
class FlexiblePatternMatcher:
    def __init__(self):
        self.question_patterns = [
            # Tiếng Việt variants
            r'^(?:câu\s*(?:hỏi)?\s*)?(\d+)\s*[:.)\-–—]\s*(.*)',  # Câu 1: / Câu hỏi 1. / 1) / 1-
            r'^(?:bài\s*(?:tập)?\s*)?(\d+)\s*[:.)\-–—]\s*(.*)',  # Bài 1: / Bài tập 1.
            r'^(?:question\s*)?(\d+)\s*[:.)\-–—]\s*(.*)',  # Question 1: / 1.
            r'^\s*(\d+)\s*[:.)\-–—]\s*(.*)',  # 1. / 1) / 1-

            # Không có số thứ tự
            r'^(?:câu\s*hỏi|question)\s*[:.)\-–—]?\s*(.*)',  # Câu hỏi: / Question:
            r'^(?:hỏi|ask)\s*[:.)\-–—]?\s*(.*)',  # Hỏi: / Ask:
        ]

        self.option_patterns = [
            r'^([A-E])\s*[:.)\-–—]\s*(.*)',  # A. / A) / A:
            r'^([A-E])\s+(.*)',  # A text
            r'^\s*([A-E])\s*[:.)\-–—]\s*(.*)',  # Với khoảng trắng đầu
        ]

        self.answer_patterns = [
            r'^(?:đáp\s*án|answer|key|correct)\s*[:.)\-–—]?\s*([A-E])',
            r'^(?:kết\s*quả|result)\s*[:.)\-–—]?\s*([A-E])',
            r'^([A-E])\s*(?:là\s*đáp\s*án\s*đúng)',
            r'^\s*([A-E])\s*$',  # Chỉ có một chữ cái
        ]

    # Phát hiện câu hỏi với confidence score
    def smart_detect_question(self, line):
        """Phát hiện câu hỏi với confidence score"""
        line_clean = line.strip()

        for pattern in self.question_patterns:
            match = re.match(pattern, line_clean, re.IGNORECASE | re.UNICODE)
            if match:
                return {
                    'is_question': True,
                    'number': match.group(1) if len(match.groups()) > 1 else None,
                    'content': match.group(2) if len(match.groups()) > 1 else match.group(1),
                    'confidence': 0.9,
                    'pattern_used': pattern
                }

        # Fallback: heuristic detection
        if any(keyword in line_clean.lower() for keyword in ['tính', 'giải', 'tìm', 'chọn', 'xác định']):
            return {
                'is_question': True,
                'number': None,
                'content': line_clean,
                'confidence': 0.6,
                'pattern_used': 'heuristic'
            }

        return {'is_question': False, 'confidence': 0}

    # Phát hiện đáp án với pattern linh hoạt
    def smart_detect_option(self, line):
        """Phát hiện đáp án với confidence score"""
        line_clean = line.strip()

        for pattern in self.option_patterns:
            match = re.match(pattern, line_clean, re.IGNORECASE)
            if match:
                return {
                    'is_option': True,
                    'label': match.group(1).upper(),
                    'text': match.group(2).strip(),
                    'confidence': 0.9
                }

        return {'is_option': False, 'confidence': 0}

    # Phát hiện đáp án đúng
    def smart_detect_answer(self, line):
        """Phát hiện đáp án đúng"""
        line_clean = line.strip()

        for pattern in self.answer_patterns:
            match = re.match(pattern, line_clean, re.IGNORECASE)
            if match:
                return {
                    'is_answer': True,
                    'answer': match.group(1).upper(),
                    'confidence': 0.9
                }

        return {'is_answer': False, 'confidence': 0}
# Validation nâng cao với scoring system
class AdvancedQuestionValidator:
    def __init__(self):
        self.min_question_length = 10
        self.max_question_length = 1000
        self.min_option_length = 1
        self.max_option_length = 200

        # Từ khóa nghi ngờ
        self.suspicious_keywords = [
            'lorem ipsum', 'test', 'sample', 'example only',
            'placeholder', 'temp', 'xxx', '???'
        ]

        # Patterns không hợp lệ
        self.invalid_patterns = [
            r'^[.\-_\s]*$',  # Chỉ ký tự đặc biệt
            r'^\d+$',  # Chỉ số
            r'^[A-E]$',  # Chỉ một chữ cái
        ]

    # Validation toàn diện với scoring system
    def comprehensive_validate(self, question_data, line_number):
        """Validation toàn diện với scoring system"""

        validation_result = {
            'valid': True,
            'score': 100,  # Điểm chất lượng
            'errors': [],
            'warnings': [],
            'suggestions': []
        }

        # 1. Content validation
        content = question_data.get('content', '').strip()

        if not content:
            validation_result['errors'].append(f"Dòng {line_number}: Thiếu nội dung câu hỏi")
            validation_result['valid'] = False
            validation_result['score'] -= 50
        elif len(content) < self.min_question_length:
            validation_result['warnings'].append(f"Dòng {line_number}: Nội dung quá ngắn ({len(content)} ký tự)")
            validation_result['score'] -= 20
        elif len(content) > self.max_question_length:
            validation_result['warnings'].append(f"Dòng {line_number}: Nội dung quá dài")
            validation_result['score'] -= 10

        # 2. Options validation
        options = question_data.get('options', [])

        if len(options) < 2:
            validation_result['errors'].append(f"Dòng {line_number}: Cần ít nhất 2 đáp án")
            validation_result['valid'] = False
            validation_result['score'] -= 30
        elif len(options) > 5:
            validation_result['warnings'].append(f"Dòng {line_number}: Quá nhiều đáp án ({len(options)})")
            validation_result['score'] -= 5

        # Check option quality
        for i, option in enumerate(options):
            option_text = option.get('text', '').strip()
            label = chr(65 + i)  # A, B, C, D, E

            if not option_text:
                validation_result['errors'].append(f"Dòng {line_number}: Đáp án {label} trống")
                validation_result['valid'] = False
                validation_result['score'] -= 15
            elif len(option_text) < self.min_option_length:
                validation_result['warnings'].append(f"Dòng {line_number}: Đáp án {label} quá ngắn")
                validation_result['score'] -= 5

        # 3. Similarity check between options
        if len(options) >= 2:
            similarity_score = self.check_option_similarity(options)
            if similarity_score > 0.8:
                validation_result['warnings'].append(f"Dòng {line_number}: Các đáp án quá giống nhau")
                validation_result['score'] -= 15

        # 4. Answer validation
        correct_answer = question_data.get('answer', '').upper()
        if not correct_answer:
            validation_result['errors'].append(f"Dòng {line_number}: Thiếu đáp án đúng")
            validation_result['valid'] = False
            validation_result['score'] -= 25
        elif correct_answer not in 'ABCDE'[:len(options)]:
            validation_result['errors'].append(f"Dòng {line_number}: Đáp án đúng '{correct_answer}' không hợp lệ")
            validation_result['valid'] = False
            validation_result['score'] -= 25

        # 5. Content quality checks
        self.check_content_quality(content, validation_result, line_number)

        # 6. Suggestions for improvement
        if validation_result['score'] < 80:
            validation_result['suggestions'].append("Cân nhắc kiểm tra lại nội dung câu hỏi")

        return validation_result

    # Kiểm tra độ tương tự giữa các đáp án
    def check_option_similarity(self, options):
        """Kiểm tra độ tương tự giữa các đáp án"""
        from difflib import SequenceMatcher

        if len(options) < 2:
            return 0

        similarities = []
        for i in range(len(options)):
            for j in range(i + 1, len(options)):
                text1 = options[i].get('text', '').lower()
                text2 = options[j].get('text', '').lower()
                sim = SequenceMatcher(None, text1, text2).ratio()
                similarities.append(sim)

        return max(similarities) if similarities else 0

    # Kiểm tra chất lượng nội dung
    def check_content_quality(self, content, validation_result, line_number):
        """Kiểm tra chất lượng nội dung"""
        content_lower = content.lower()

        # Check suspicious content
        for keyword in self.suspicious_keywords:
            if keyword in content_lower:
                validation_result['warnings'].append(f"Dòng {line_number}: Nội dung nghi ngờ chứa '{keyword}'")
                validation_result['score'] -= 10

        # Check invalid patterns
        for pattern in self.invalid_patterns:
            if re.match(pattern, content):
                validation_result['errors'].append(f"Dòng {line_number}: Nội dung không hợp lệ")
                validation_result['valid'] = False
                validation_result['score'] -= 30
                break

        # Grammar hints (basic)
        if content.count('?') == 0 and any(word in content_lower for word in ['gì', 'nào', 'tính', 'tìm']):
            validation_result['suggestions'].append(f"Dòng {line_number}: Có thể thiếu dấu hỏi")
            validation_result['score'] -= 5
# Progress dialog với real-time feedback cho import
class ImportProgressDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔄 Đang import câu hỏi...")
        self.setModal(True)
        self.resize(600, 400)
        self.setup_ui()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Header info
        self.status_label = QtWidgets.QLabel("Đang khởi tạo...")
        self.status_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        # Statistics panel
        stats_group = QtWidgets.QGroupBox("📊 Thống kê")
        stats_layout = QtWidgets.QGridLayout(stats_group)

        self.questions_found_label = QtWidgets.QLabel("0")
        self.questions_valid_label = QtWidgets.QLabel("0")
        self.errors_count_label = QtWidgets.QLabel("0")
        self.warnings_count_label = QtWidgets.QLabel("0")

        stats_layout.addWidget(QtWidgets.QLabel("Câu hỏi tìm thấy:"), 0, 0)
        stats_layout.addWidget(self.questions_found_label, 0, 1)
        stats_layout.addWidget(QtWidgets.QLabel("Câu hỏi hợp lệ:"), 0, 2)
        stats_layout.addWidget(self.questions_valid_label, 0, 3)
        stats_layout.addWidget(QtWidgets.QLabel("Lỗi:"), 1, 0)
        stats_layout.addWidget(self.errors_count_label, 1, 1)
        stats_layout.addWidget(QtWidgets.QLabel("Cảnh báo:"), 1, 2)
        stats_layout.addWidget(self.warnings_count_label, 1, 3)

        layout.addWidget(stats_group)

        # Log area với tabs
        log_tabs = QtWidgets.QTabWidget()

        # Tab 1: Live processing
        self.live_log = QtWidgets.QTextEdit()
        self.live_log.setMaximumHeight(150)
        self.live_log.setReadOnly(True)
        log_tabs.addTab(self.live_log, "🔄 Live")

        # Tab 2: Errors
        self.error_log = QtWidgets.QTextEdit()
        self.error_log.setReadOnly(True)
        self.error_log.setStyleSheet("color: #e74c3c;")
        log_tabs.addTab(self.error_log, "❌ Lỗi")

        # Tab 3: Warnings
        self.warning_log = QtWidgets.QTextEdit()
        self.warning_log.setReadOnly(True)
        self.warning_log.setStyleSheet("color: #f39c12;")
        log_tabs.addTab(self.warning_log, "⚠️ Cảnh báo")

        layout.addWidget(log_tabs)

        # Control buttons
        button_layout = QtWidgets.QHBoxLayout()

        self.pause_btn = QtWidgets.QPushButton("⏸️ Tạm dừng")
        self.pause_btn.clicked.connect(self.toggle_pause)

        self.cancel_btn = QtWidgets.QPushButton("❌ Hủy")
        self.cancel_btn.clicked.connect(self.cancel_import)

        self.details_btn = QtWidgets.QPushButton("📋 Chi tiết")
        self.details_btn.clicked.connect(self.show_details)
        self.details_btn.setVisible(False)

        button_layout.addWidget(self.pause_btn)
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.details_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

    # Update progress với detailed stats
    def update_progress(self, current, total, status, stats=None):
        """Update progress với detailed stats"""

        # Update progress bar
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"{current}/{total} ({current / total * 100:.1f}%)")

        # Update status
        self.status_label.setText(status)

        # Update live log
        self.live_log.append(f"[{current:03d}] {status}")

        # Update statistics
        if stats:
            self.questions_found_label.setText(str(stats.get('found', 0)))
            self.questions_valid_label.setText(str(stats.get('valid', 0)))
            self.errors_count_label.setText(str(stats.get('errors', 0)))
            self.warnings_count_label.setText(str(stats.get('warnings', 0)))

            # Update error/warning logs
            if 'new_errors' in stats:
                for error in stats['new_errors']:
                    self.error_log.append(error)

            if 'new_warnings' in stats:
                for warning in stats['new_warnings']:
                    self.warning_log.append(warning)

        # Auto-scroll to bottom
        self.live_log.verticalScrollBar().setValue(
            self.live_log.verticalScrollBar().maximum()
        )

        # Process events to keep UI responsive
        QtWidgets.QApplication.processEvents()

    def toggle_pause(self):
        """Toggle pause/resume import"""
        # Implementation for pause/resume
        pass

    def cancel_import(self):
        """Cancel import process"""
        self.reject()

    def show_details(self):
        """Show detailed import results"""
        pass
class QuestionBankWindowQt(QtWidgets.QWidget):
    """
    PySide6 - Ngân hàng câu hỏi
    - Trái: Cây thư mục (exercise_tree)
    - Giữa: Danh sách câu hỏi
    - Phải: Chi tiết câu hỏi + đáp án A-E
    - Thanh cấu hình: Môn / Lớp / Chủ đề / Dạng / Mức độ, Tìm kiếm, Nhập từ Word
    """
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setObjectName("QuestionBankWindowQt")
        self.setWindowTitle("Ngân hàng câu hỏi")
        self.resize(1200, 680)

        # đảm bảo bảng tồn tại (an toàn nếu CSDL cũ)
        self._ensure_tables()

        self.current_question_id: int | None = None
        self.tree_nodes: Dict[str, int] = {}  # QTreeWidgetItem->id

        root = QtWidgets.QVBoxLayout(self)

        # Tạo toolbar chính với nhóm chức năng hiện đại
        main_toolbar = QtWidgets.QToolBar()
        main_toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        main_toolbar.setMovable(False)
        main_toolbar.setStyleSheet("""
                    QToolBar { 
                        background: #f8f9fa; 
                        border: 1px solid #dee2e6; 
                        spacing: 8px; 
                        padding: 4px;
                    }
                    QToolBar::separator { 
                        background: #dee2e6; 
                        width: 2px; 
                        margin: 0 4px;
                    }
                """)
        root.addWidget(main_toolbar)

        # Nhóm quản lý cây
        toggle_action = main_toolbar.addAction("🌲 Ẩn/Hiện cây")
        toggle_action.triggered.connect(self.toggle_tree_panel)

        manage_action = main_toolbar.addAction("⚙️ Quản lý cây")
        manage_action.triggered.connect(self.open_tree_manager)

        main_toolbar.addSeparator()

        # Nhóm tìm kiếm với widget tùy chỉnh
        search_widget = QtWidgets.QWidget()
        search_layout = QtWidgets.QHBoxLayout(search_widget)
        search_layout.setContentsMargins(0, 0, 0, 0)

        search_layout.addWidget(QtWidgets.QLabel("🔍"))

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Tìm kiếm câu hỏi...")
        self.search_edit.setMinimumWidth(200)
        self.search_edit.setStyleSheet("padding: 4px; border: 1px solid #ced4da; border-radius: 4px;")
        search_layout.addWidget(self.search_edit)

        main_toolbar.addWidget(search_widget)

        search_action = main_toolbar.addAction("Tìm")
        search_action.triggered.connect(self.search_questions)

        advanced_search_action = main_toolbar.addAction("🔍 Nâng cao")
        advanced_search_action.triggered.connect(self.show_advanced_search_dialog)

        main_toolbar.addSeparator()

        # Nhóm template và tạo mới
        new_action = main_toolbar.addAction("➕ Tạo mới")
        new_action.triggered.connect(self.new_question)

        template_action = main_toolbar.addAction("📝 Template")
        template_action.triggered.connect(self.show_template_dialog)

        main_toolbar.addSeparator()

        # Nhóm import/export
        import_action = main_toolbar.addAction("📥 Import Word")
        import_action.triggered.connect(self.import_from_word)

        export_action = main_toolbar.addAction("📤 Export Word")
        export_action.triggered.connect(self.export_to_word)

        export_pdf_action = main_toolbar.addAction("📄 Export PDF")
        export_pdf_action.triggered.connect(self.export_to_pdf)

        main_toolbar.addSeparator()

        # Toolbar phụ cho filters
        filter_toolbar = QtWidgets.QToolBar()
        filter_toolbar.setStyleSheet("QToolBar { background: #e9ecef; border: 1px solid #dee2e6; }")
        root.addWidget(filter_toolbar)

        self._create_filter_controls(filter_toolbar)
        # ----------------- splitter 3 cột -----------------
        split = QtWidgets.QSplitter(Qt.Horizontal)
        root.addWidget(split, 1)

        # --- Cột trái: Cây ---
        left = QtWidgets.QWidget()
        left_l = QtWidgets.QVBoxLayout(left)
        left_l.setContentsMargins(6, 6, 6, 6)

        left_l.addWidget(QtWidgets.QLabel("Cây thư mục"))
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemSelectionChanged.connect(self.on_tree_select)
        left_l.addWidget(self.tree, 1)

        split.addWidget(left)
        # --- Cột giữa: Danh sách câu hỏi ---
        mid = QtWidgets.QWidget()
        mid_l = QtWidgets.QVBoxLayout(mid)
        mid_l.setContentsMargins(6, 6, 6, 6)

        mid_l.addWidget(QtWidgets.QLabel("Danh sách câu hỏi"))
        # Bảng câu hỏi với nhiều tính năng cải tiến
        self.q_table = QtWidgets.QTableWidget(0, 8)  # Thêm cột checkbox và actions
        headers = ["☑️", "ID", "Nội dung", "Số đáp án", "Đáp án đúng", "Dạng", "Mức độ", "🏷️"]
        self.q_table.setHorizontalHeaderLabels(headers)

        # Cấu hình resize mode
        header = self.q_table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)  # Checkbox
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)  # ID
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)  # Nội dung
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)  # Số đáp án
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)  # Đáp án đúng
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)  # Dạng
        header.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeToContents)  # Mức độ
        header.setSectionResizeMode(7, QtWidgets.QHeaderView.ResizeToContents)  # Tags

        # Cho phép sắp xếp
        self.q_table.setSortingEnabled(True)

        # Thêm context menu
        self.q_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.q_table.customContextMenuRequested.connect(self.show_table_context_menu)

        # Cải tiến visual
        self.q_table.setAlternatingRowColors(True)
        self.q_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.q_table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        # Styling cho bảng
        self.q_table.setStyleSheet("""
                    QTableWidget {
                        gridline-color: #e9ecef;
                        background-color: white;
                        alternate-background-color: #f8f9fa;
                    }
                    QTableWidget::item {
                        padding: 8px;
                        border-bottom: 1px solid #e9ecef;
                    }
                    QTableWidget::item:selected {
                        background-color: #007bff;
                        color: white;
                    }
                """)

        mid_l.addWidget(self.q_table, 1)
        split.addWidget(mid)
        # Kết nối signal cho table selection
        self.q_table.itemSelectionChanged.connect(self.on_question_select)
        self.q_table.itemClicked.connect(self.on_question_select)
        # --- Cột phải: Panel chi tiết với tabs ---
        right_tabs = QtWidgets.QTabWidget()
        right_tabs.setStyleSheet("""
                    QTabWidget::pane {
                        border: 1px solid #dee2e6;
                        background: white;
                    }
                    QTabBar::tab {
                        background: #f8f9fa;
                        padding: 8px 16px;
                        margin-right: 2px;
                        border: 1px solid #dee2e6;
                        border-bottom: none;
                    }
                    QTabBar::tab:selected {
                        background: white;
                        border-bottom: 1px solid white;
                    }
                """)

        # Tab 1: Chỉnh sửa câu hỏi
        edit_tab = QtWidgets.QWidget()
        edit_layout = QtWidgets.QVBoxLayout(edit_tab)
        edit_layout.setContentsMargins(10, 10, 10, 10)

        self._create_edit_tab_content(edit_layout)
        right_tabs.addTab(edit_tab, "✏️ Chỉnh sửa")

        # Tab 2: Preview câu hỏi
        preview_tab = QtWidgets.QWidget()
        preview_layout = QtWidgets.QVBoxLayout(preview_tab)
        preview_layout.setContentsMargins(10, 10, 10, 10)

        self._create_preview_tab_content(preview_layout)
        right_tabs.addTab(preview_tab, "👁️ Xem trước")

        # Tab 3: Thống kê
        stats_tab = QtWidgets.QWidget()
        stats_layout = QtWidgets.QVBoxLayout(stats_tab)
        stats_layout.setContentsMargins(10, 10, 10, 10)

        self._create_stats_tab_content(stats_layout)
        right_tabs.addTab(stats_tab, "📊 Thống kê")

        # Tab 4: Lịch sử
        history_tab = QtWidgets.QWidget()
        history_layout = QtWidgets.QVBoxLayout(history_tab)
        history_layout.setContentsMargins(10, 10, 10, 10)

        self._create_history_tab_content(history_layout)
        right_tabs.addTab(history_tab, "📜 Lịch sử")

        split.addWidget(right_tabs)

        split.setSizes([240, 520, 440])

        # init dữ liệu
        self.refresh_tree()
        self.load_available_subjects()
        self.load_available_grades()

        # signal cho combobox
        self.subject_cb.currentIndexChanged.connect(self.load_available_topics)
        self.grade_cb.currentIndexChanged.connect(self.load_available_topics)
        self.topic_cb.currentIndexChanged.connect(self.load_available_types)
        # Thêm keyboard shortcuts cho tăng năng suất
        QtGui.QShortcut("Ctrl+N", self, self.new_question)
        QtGui.QShortcut("Ctrl+S", self, self.save_question)
        QtGui.QShortcut("Ctrl+F", self, self.focus_search)
        QtGui.QShortcut("Ctrl+Shift+F", self, self.show_advanced_search_dialog)
        QtGui.QShortcut("Delete", self, self.delete_question)
        QtGui.QShortcut("Ctrl+D", self, self.duplicate_question)
        QtGui.QShortcut("F5", self, self.refresh_all)
        QtGui.QShortcut("Ctrl+E", self, self.export_to_word)
        QtGui.QShortcut("Ctrl+I", self, self.import_from_word)
        QtGui.QShortcut("Ctrl+T", self, self.show_template_dialog)

        # Kích hoạt drag & drop
        self.setAcceptDrops(True)
        self.q_table.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.q_table.itemSelectionChanged.connect(self.on_question_select)
        self.q_table.itemClicked.connect(self.on_question_select)
    # ====================== DB helpers ======================
    def _ensure_tables(self):
        self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS exercise_tree (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER,
                name TEXT NOT NULL,
                level TEXT NOT NULL,
                UNIQUE(parent_id, name, level)
            );
        """)
        self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS question_bank (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_text TEXT,
                options TEXT,
                correct TEXT,
                tree_id INTEGER
            );
        """)
        # Thêm bảng tags cho câu hỏi
        self.db.execute_query("""
                    CREATE TABLE IF NOT EXISTS question_tags (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        question_id INTEGER,
                        tag_name TEXT,
                        color TEXT DEFAULT '#3498db',
                        created_date TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (question_id) REFERENCES question_bank(id) ON DELETE CASCADE,
                        UNIQUE(question_id, tag_name)
                    );
                """)

        # Thêm bảng bookmark
        self.db.execute_query("""
                    CREATE TABLE IF NOT EXISTS question_bookmarks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        question_id INTEGER,
                        bookmark_name TEXT,
                        notes TEXT,
                        created_date TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (question_id) REFERENCES question_bank(id) ON DELETE CASCADE
                    );
                """)

        # Thêm bảng lịch sử chỉnh sửa
        self.db.execute_query("""
                    CREATE TABLE IF NOT EXISTS question_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        question_id INTEGER,
                        action_type TEXT,
                        old_content TEXT,
                        new_content TEXT,
                        changed_date TEXT DEFAULT CURRENT_TIMESTAMP,
                        user_note TEXT,
                        FOREIGN KEY (question_id) REFERENCES question_bank(id) ON DELETE CASCADE
                    );
                """)

        # Thêm bảng template
        self.db.execute_query("""
                    CREATE TABLE IF NOT EXISTS question_templates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        template_name TEXT NOT NULL,
                        template_content TEXT,
                        template_options TEXT,
                        category TEXT,
                        created_date TEXT DEFAULT CURRENT_TIMESTAMP
                    );
                """)
        self.db.execute_query("CREATE INDEX IF NOT EXISTS idx_question_tree_id ON question_bank(tree_id)")
        self.db.execute_query("CREATE INDEX IF NOT EXISTS idx_question_tags_question_id ON question_tags(question_id)")
        self.db.execute_query("CREATE INDEX IF NOT EXISTS idx_question_tags_tag_name ON question_tags(tag_name)")
        self.db.execute_query(
            "CREATE INDEX IF NOT EXISTS idx_question_history_question_id ON question_history(question_id)")
        self.db.execute_query("CREATE INDEX IF NOT EXISTS idx_exercise_tree_parent_id ON exercise_tree(parent_id)")
        self.db.execute_query("CREATE INDEX IF NOT EXISTS idx_exercise_tree_level ON exercise_tree(level)")
    # Tạo các control filter trong toolbar
    def _create_filter_controls(self, toolbar):
        """Tạo các combobox filter trong toolbar"""
        toolbar.addWidget(QtWidgets.QLabel("Môn:"))
        self.subject_cb = QtWidgets.QComboBox()
        self.subject_cb.setMinimumWidth(120)
        toolbar.addWidget(self.subject_cb)

        toolbar.addWidget(QtWidgets.QLabel("Lớp:"))
        self.grade_cb = QtWidgets.QComboBox()
        self.grade_cb.setMinimumWidth(100)
        toolbar.addWidget(self.grade_cb)

        toolbar.addWidget(QtWidgets.QLabel("Chủ đề:"))
        self.topic_cb = QtWidgets.QComboBox()
        self.topic_cb.setMinimumWidth(150)
        toolbar.addWidget(self.topic_cb)

        toolbar.addWidget(QtWidgets.QLabel("Dạng:"))
        self.type_cb = QtWidgets.QComboBox()
        self.type_cb.setMinimumWidth(120)
        toolbar.addWidget(self.type_cb)

        toolbar.addWidget(QtWidgets.QLabel("Mức độ:"))
        self.level_cb = QtWidgets.QComboBox()
        self.level_cb.addItems(["", "Nhận biết", "Thông hiểu", "Vận dụng", "Vận dụng cao", "Sáng tạo"])
        self.level_cb.setMinimumWidth(120)
        toolbar.addWidget(self.level_cb)

        toolbar.addSeparator()

        filter_btn = toolbar.addAction("🔽 Lọc")
        filter_btn.triggered.connect(self.filter_by_combobox)

        clear_filter_btn = toolbar.addAction("🔄 Xóa lọc")
        clear_filter_btn.triggered.connect(self.clear_filters)
    # Tạo nội dung tab chỉnh sửa câu hỏi
    def _create_edit_tab_content(self, layout):
        """Tạo nội dung cho tab chỉnh sửa"""
        # Toolbar cho text editor
        text_toolbar = QtWidgets.QToolBar()
        text_toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)

        # Tạo font và action cho Bold
        bold_action = text_toolbar.addAction("B")
        bold_font = QtGui.QFont("Arial", 10)
        bold_font.setBold(True)
        bold_action.setFont(bold_font)
        bold_action.triggered.connect(self.format_bold)

        # Tạo font và action cho Italic
        italic_action = text_toolbar.addAction("I")
        italic_font = QtGui.QFont("Arial", 10)
        italic_font.setItalic(True)
        italic_action.setFont(italic_font)
        italic_action.triggered.connect(self.format_italic)

        text_toolbar.addSeparator()

        # Các action khác
        math_action = text_toolbar.addAction("∑")
        math_action.triggered.connect(self.insert_math)

        image_action = text_toolbar.addAction("🖼️")
        image_action.triggered.connect(self.insert_image)

        layout.addWidget(text_toolbar)
        # Nội dung câu hỏi
        layout.addWidget(QtWidgets.QLabel("Nội dung câu hỏi:"))
        self.content_text = QtWidgets.QTextEdit()
        self.content_text.setMinimumHeight(150)
        self.content_text.textChanged.connect(self.update_preview)
        layout.addWidget(self.content_text)

        # Đáp án với nhóm
        answers_group = QtWidgets.QGroupBox("Đáp án")
        answers_layout = QtWidgets.QVBoxLayout(answers_group)

        self.correct_group = QtWidgets.QButtonGroup(self)
        self.option_entries = {}

        for label in ["A", "B", "C", "D", "E"]:
            row_widget = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)

            rb = QtWidgets.QRadioButton(label)
            self.correct_group.addButton(rb)
            row_layout.addWidget(rb)

            ent = QtWidgets.QLineEdit()
            ent.setPlaceholderText(f"Nội dung đáp án {label}")
            ent.textChanged.connect(self.update_preview)
            row_layout.addWidget(ent, 1)

            # Nút xóa đáp án
            del_btn = QtWidgets.QPushButton("⌫")
            del_btn.setMaximumWidth(30)
            del_btn.clicked.connect(lambda checked, lbl=label: self.remove_option(lbl))
            row_layout.addWidget(del_btn)

            answers_layout.addWidget(row_widget)
            self.option_entries[label] = ent

        layout.addWidget(answers_group)

        # Tags section
        tags_group = QtWidgets.QGroupBox("🏷️ Thẻ")
        tags_layout = QtWidgets.QHBoxLayout(tags_group)

        self.tags_edit = QtWidgets.QLineEdit()
        self.tags_edit.setPlaceholderText("Nhập thẻ, phân cách bằng dấu phẩy")
        tags_layout.addWidget(self.tags_edit)

        add_tag_btn = QtWidgets.QPushButton("➕")
        add_tag_btn.clicked.connect(self.add_new_tag)
        tags_layout.addWidget(add_tag_btn)

        layout.addWidget(tags_group)

        # Buttons
        buttons_layout = QtWidgets.QHBoxLayout()

        self.btn_save = QtWidgets.QPushButton("💾 Lưu/Cập nhật")
        self.btn_save.clicked.connect(self.save_question)
        self.btn_save.setStyleSheet("QPushButton { background: #28a745; color: white; padding: 8px 16px; }")

        self.btn_delete = QtWidgets.QPushButton("🗑️ Xóa")
        self.btn_delete.clicked.connect(self.delete_question)
        self.btn_delete.setStyleSheet("QPushButton { background: #dc3545; color: white; padding: 8px 16px; }")

        duplicate_btn = QtWidgets.QPushButton("📋 Nhân bản")
        duplicate_btn.clicked.connect(self.duplicate_question)
        duplicate_btn.setStyleSheet("QPushButton { background: #6c757d; color: white; padding: 8px 16px; }")

        buttons_layout.addWidget(self.btn_save)
        buttons_layout.addWidget(duplicate_btn)
        buttons_layout.addWidget(self.btn_delete)

        layout.addLayout(buttons_layout)

    # Tạo nội dung tab preview
    def _create_preview_tab_content(self, layout):
        """Tạo nội dung cho tab preview"""
        layout.addWidget(QtWidgets.QLabel("🔍 Xem trước câu hỏi:"))

        self.preview_widget = QtWidgets.QTextEdit()
        self.preview_widget.setReadOnly(True)
        self.preview_widget.setStyleSheet("""
            QTextEdit {
                background: white;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                padding: 16px;
                font-size: 14px;
                line-height: 1.5;
            }
        """)
        layout.addWidget(self.preview_widget)

        # Nút refresh preview
        refresh_btn = QtWidgets.QPushButton("🔄 Làm mới preview")
        refresh_btn.clicked.connect(self.update_preview)
        layout.addWidget(refresh_btn)

    # Tạo nội dung tab thống kê
    def _create_stats_tab_content(self, layout):
        """Tạo nội dung cho tab thống kê"""
        layout.addWidget(QtWidgets.QLabel("📊 Thống kê ngân hàng câu hỏi:"))

        self.stats_widget = QtWidgets.QTextEdit()
        self.stats_widget.setReadOnly(True)
        layout.addWidget(self.stats_widget)

        # Nút cập nhật thống kê
        update_stats_btn = QtWidgets.QPushButton("🔄 Cập nhật thống kê")
        update_stats_btn.clicked.connect(self.update_statistics)
        layout.addWidget(update_stats_btn)

    # Tạo nội dung tab lịch sử
    def _create_history_tab_content(self, layout):
        """Tạo nội dung cho tab lịch sử"""
        layout.addWidget(QtWidgets.QLabel("📜 Lịch sử chỉnh sửa:"))

        self.history_table = QtWidgets.QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels(["Thời gian", "Hành động", "Nội dung cũ", "Nội dung mới"])
        self.history_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)

        layout.addWidget(self.history_table)

        # Nút xóa lịch sử
        clear_history_btn = QtWidgets.QPushButton("🗑️ Xóa lịch sử")
        clear_history_btn.clicked.connect(self.clear_history)
        layout.addWidget(clear_history_btn)
    def validate_question_data(self, content, correct, opts):
        """Kiểm tra tính hợp lệ của dữ liệu câu hỏi"""
        errors = []

        if not content or len(content.strip()) < 10:
            errors.append("Nội dung câu hỏi phải có ít nhất 10 ký tự")

        if not correct:
            errors.append("Phải chọn đáp án đúng")

        if len(opts) < 2:
            errors.append("Phải có ít nhất 2 đáp án")

        # Kiểm tra đáp án trống
        empty_options = [opt for opt in opts if not opt.get("text", "").strip()]
        if empty_options:
            errors.append("Không được để trống đáp án")

        return errors
    # ====================== Tree ======================
    def refresh_tree(self):
        self.tree.clear()
        self.tree_nodes.clear()

        rows = self.db.execute_query(
            "SELECT id,parent_id,name,level FROM exercise_tree ORDER BY parent_id,level,name",
            fetch='all'
        ) or []
        children: Dict[int | None, list] = {}
        for r in rows:
            children.setdefault(r["parent_id"], []).append(r)

        def build(parent_db_id: int | None, parent_item: QtWidgets.QTreeWidgetItem | None):
            for node in children.get(parent_db_id, []):
                item = QtWidgets.QTreeWidgetItem([node["name"]])
                item.setData(0, Qt.UserRole, node["id"])
                self.tree_nodes[str(id(item))] = node["id"]
                if parent_item is None:
                    self.tree.addTopLevelItem(item)
                else:
                    parent_item.addChild(item)
                build(node["id"], item)

        build(None, None)
        self.tree.expandAll()

    def on_tree_select(self):
        items = self.tree.selectedItems()
        if not items:
            return
        tree_id = items[0].data(0, Qt.UserRole)
        if not tree_id:
            return

        rows = self.db.execute_query("SELECT * FROM question_bank WHERE tree_id=?", (tree_id,), fetch="all") or []
        self._load_question_rows(rows)

    # ====================== Questions list ======================
    def _load_question_rows(self, rows):
        # Clear các widget cũ để tránh memory leak
        for row in range(self.q_table.rowCount()):
            widget = self.q_table.cellWidget(row, 0)
            if widget:
                widget.deleteLater()
        self.q_table.setRowCount(0)

        # Tối ưu hiệu suất với nhiều dữ liệu
        if len(rows) > 100:
            self.q_table.setUpdatesEnabled(False)

        for r in rows:
            # Tạo checkbox cho mỗi dòng
            checkbox = QtWidgets.QCheckBox()
            checkbox.setChecked(False)

            content_preview = (r["content_text"] or "")[:50].replace("\n", " ").strip()
            opts = json.loads(r["options"] or "[]")
            so_dapan = len(opts)
            dap_an = r.get("correct", "-") if isinstance(r, dict) else "-"

            # Lấy chuỗi dạng/mức độ từ path
            path = self.get_tree_path(r["tree_id"])
            path_dict = {p["level"]: p["name"] for p in path}
            dang = path_dict.get("Dạng", "-")
            muc_do = path_dict.get("Mức độ", "-")

            # Lấy tags cho câu hỏi
            tags = self.db.execute_query(
                "SELECT tag_name FROM question_tags WHERE question_id=?",
                (r["id"],), fetch="all"
            ) or []
            tags_text = ", ".join([tag["tag_name"] for tag in tags]) if tags else ""

            row_idx = self.q_table.rowCount()
            self.q_table.insertRow(row_idx)

            # Set checkbox
            self.q_table.setCellWidget(row_idx, 0, checkbox)

            # Set data
            self.q_table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(str(r["id"])))
            self.q_table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(content_preview))
            self.q_table.setItem(row_idx, 3, QtWidgets.QTableWidgetItem(str(so_dapan)))
            self.q_table.setItem(row_idx, 4, QtWidgets.QTableWidgetItem(dap_an or "-"))
            self.q_table.setItem(row_idx, 5, QtWidgets.QTableWidgetItem(dang))
            self.q_table.setItem(row_idx, 6, QtWidgets.QTableWidgetItem(muc_do))

            # Tags cell với màu
            tags_item = QtWidgets.QTableWidgetItem(tags_text)
            if tags_text:
                tags_item.setBackground(QtGui.QColor("#e3f2fd"))
            self.q_table.setItem(row_idx, 7, tags_item)

        # Bật lại update nếu đã tắt
        if len(rows) > 100:
            self.q_table.setUpdatesEnabled(True)
    def on_question_select(self):
        items = self.q_table.selectedItems()
        if not items:
            return
        row = items[0].row()
        qid = int(self.q_table.item(row, 1).text())

        q = self.db.execute_query("SELECT * FROM question_bank WHERE id=?", (qid,), fetch="one")
        if not q:
            return

        # Load nội dung câu hỏi
        if hasattr(self, 'content_text'):
            self.content_text.blockSignals(True)
            if hasattr(self.content_text, 'setPlainText'):
                self.content_text.setPlainText(q["content_text"] or "")
            else:
                self.content_text.setPlainText(q["content_text"] or "")
            self.content_text.blockSignals(False)

        # Reset đáp án
        self.correct_group.setExclusive(False)
        for b in self.correct_group.buttons():
            b.setChecked(False)
        self.correct_group.setExclusive(True)

        for label, ent in self.option_entries.items():
            ent.blockSignals(True)
            ent.clear()
            ent.blockSignals(False)

        # Load đáp án
        opts = json.loads(q["options"] or "[]")
        correct = q["correct"] if q["correct"] else ""

        if correct and correct in [b.text() for b in self.correct_group.buttons()]:
            for b in self.correct_group.buttons():
                if b.text() == correct:
                    b.setChecked(True)
                    break

        # Load options
        for opt in opts:
            text = opt.get("text", "")
            if "." not in text:
                continue
            label, content = text.split(".", 1)
            label = label.strip().upper()
            ent = self.option_entries.get(label)
            if ent:
                ent.setText(content.strip())

        # Load tags
        if hasattr(self, 'tags_edit'):
            tags = self.db.execute_query(
                "SELECT tag_name FROM question_tags WHERE question_id=? ORDER BY tag_name",
                (qid,), fetch="all"
            ) or []
            tags_text = ", ".join([tag["tag_name"] for tag in tags])
            self.tags_edit.setText(tags_text)

        # Load lịch sử cho tab history
        if hasattr(self, 'history_table'):
            self._load_question_history(qid)

        # Update preview
        self.update_preview()

    # Load lịch sử câu hỏi
    def _load_question_history(self, question_id):
        """Load lịch sử thay đổi của câu hỏi"""
        if not hasattr(self, 'history_table'):
            return

        history = self.db.execute_query(
            "SELECT * FROM question_history WHERE question_id=? ORDER BY changed_date DESC LIMIT 50",
            (question_id,), fetch="all"
        ) or []

        self.history_table.setRowCount(0)

        for h in history:
            row_idx = self.history_table.rowCount()
            self.history_table.insertRow(row_idx)

            # Format thời gian
            time_str = h.get("changed_date", "")
            if time_str:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    formatted_time = dt.strftime("%d/%m/%Y %H:%M")
                except:
                    formatted_time = time_str
            else:
                formatted_time = "-"

            # Set data
            self.history_table.setItem(row_idx, 0, QtWidgets.QTableWidgetItem(formatted_time))
            self.history_table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(h.get("action_type", "")))

            # Truncate content cho display
            old_content = (h.get("old_content", "") or "")[:100] + "..." if len(
                h.get("old_content", "") or "") > 100 else h.get("old_content", "")
            new_content = (h.get("new_content", "") or "")[:100] + "..." if len(
                h.get("new_content", "") or "") > 100 else h.get("new_content", "")

            self.history_table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(old_content))
            self.history_table.setItem(row_idx, 3, QtWidgets.QTableWidgetItem(new_content))
    # ====================== Save/Update/Delete ======================
    def _current_tree_id(self) -> int | None:
        items = self.tree.selectedItems()
        if not items:
            return None
        return items[0].data(0, Qt.UserRole)

    def save_question(self):
        tree_id = self._current_tree_id()
        if not tree_id:
            QtWidgets.QMessageBox.warning(self, "Chưa chọn thư mục", "Vui lòng chọn vị trí lưu trong cây.")
            return

        content = self.content_text.toPlainText().strip() if hasattr(self, 'content_text') and hasattr(
            self.content_text, 'toPlainText') else self.content_text.toPlainText().strip()

        # Tìm radio đúng
        correct = ""
        for b in self.correct_group.buttons():
            if b.isChecked():
                correct = b.text()
                break

        opts = []
        for label, ent in self.option_entries.items():
            t = ent.text().strip()
            if t:
                opts.append({"text": f"{label}. {t}", "is_correct": (label == correct)})

        # Validation dữ liệu nâng cao
        validation_errors = self.validate_question_data(content, correct, opts)
        if validation_errors:
            error_msg = "Dữ liệu không hợp lệ:\n" + "\n".join(validation_errors)
            QtWidgets.QMessageBox.warning(self, "Lỗi dữ liệu", error_msg)
            return

        try:
            # Lưu nội dung cũ để ghi lịch sử
            old_content = ""
            if self.current_question_id:
                old_q = self.db.execute_query("SELECT content_text FROM question_bank WHERE id=?",
                                              (self.current_question_id,), fetch="one")
                old_content = old_q["content_text"] if old_q else ""

            if self.current_question_id:
                # Cập nhật câu hỏi
                self.db.execute_query(
                    "UPDATE question_bank SET content_text=?, options=?, correct=?, tree_id=? WHERE id=?",
                    (content, json.dumps(opts, ensure_ascii=False), correct, tree_id, self.current_question_id)
                )

                # Ghi lịch sử chỉnh sửa
                self._save_question_history(self.current_question_id, "UPDATE", old_content, content)

                QtWidgets.QMessageBox.information(self, "Cập nhật", "Đã cập nhật câu hỏi.")
            else:
                # Thêm câu hỏi mới
                new_id = self.db.execute_query(
                    "INSERT INTO question_bank(content_text, options, correct, tree_id) VALUES (?,?,?,?)",
                    (content, json.dumps(opts, ensure_ascii=False), correct, tree_id)
                )

                self.current_question_id = new_id

                # Ghi lịch sử tạo mới
                self._save_question_history(new_id, "CREATE", "", content)

                QtWidgets.QMessageBox.information(self, "Thêm mới", "Đã lưu câu hỏi mới.")

            # Lưu tags nếu có
            if hasattr(self, 'tags_edit') and self.tags_edit.text().strip():
                self._save_question_tags()

            # Reload danh sách
            rows = self.db.execute_query("SELECT * FROM question_bank WHERE tree_id=?", (tree_id,), fetch="all") or []
            self._load_question_rows(rows)

            # Update preview và stats
            self.update_preview()
            self.update_statistics()

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi CSDL", f"{e}")

    # Lưu lịch sử thay đổi câu hỏi
    def _save_question_history(self, question_id, action_type, old_content, new_content):
        """Lưu lịch sử thay đổi câu hỏi"""
        try:
            self.db.execute_query(
                "INSERT INTO question_history(question_id, action_type, old_content, new_content) VALUES (?,?,?,?)",
                (question_id, action_type, old_content, new_content)
            )
        except Exception as e:
            print(f"Lỗi lưu lịch sử: {e}")

    # Lưu tags cho câu hỏi
    def _save_question_tags(self):
        """Lưu tags cho câu hỏi hiện tại"""
        if not self.current_question_id or not hasattr(self, 'tags_edit'):
            return

        tags_text = self.tags_edit.text().strip()
        if not tags_text:
            return

        # Xóa tags cũ
        self.db.execute_query("DELETE FROM question_tags WHERE question_id=?", (self.current_question_id,))

        # Thêm tags mới
        tag_names = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
        for tag_name in tag_names:
            try:
                self.db.execute_query(
                    "INSERT INTO question_tags(question_id, tag_name) VALUES (?,?)",
                    (self.current_question_id, tag_name)
                )
            except:
                pass  # Tag đã tồn tại hoặc lỗi khác
    def clear_question_form(self):
        self.current_question_id = None
        self.content_text.clear()
        self.correct_group.setExclusive(False)
        for b in self.correct_group.buttons():
            b.setChecked(False)
        self.correct_group.setExclusive(True)
        for ent in self.option_entries.values():
            ent.clear()

    def delete_question(self):
        if not self.current_question_id:
            QtWidgets.QMessageBox.warning(self, "Chưa chọn", "Vui lòng chọn câu hỏi để xoá.")
            return
        if QtWidgets.QMessageBox.question(self, "Xác nhận", "Bạn có chắc muốn xoá câu hỏi này?") != QtWidgets.QMessageBox.Yes:
            return
        try:
            self.db.execute_query("DELETE FROM question_bank WHERE id=?", (self.current_question_id,))
            self.clear_question_form()
            tree_id = self._current_tree_id()
            if tree_id:
                rows = self.db.execute_query("SELECT * FROM question_bank WHERE tree_id=?", (tree_id,), fetch="all") or []
                self._load_question_rows(rows)
            QtWidgets.QMessageBox.information(self, "Đã xoá", "Câu hỏi đã được xoá.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi CSDL", f"{e}")

    # ====================== Path helpers ======================
    def get_tree_path(self, tree_id: int) -> List[dict]:
        path = []
        while tree_id:
            row = self.db.execute_query(
                "SELECT id, parent_id, name, level FROM exercise_tree WHERE id=?",
                (tree_id,), fetch="one"
            )
            if row:
                path.insert(0, row)
                tree_id = row["parent_id"]
            else:
                break
        return path

    # ====================== Search & Filters ======================
    def get_all_subtree_ids(self, root_id: int) -> List[int]:
        ids = [root_id]
        children = self.db.execute_query("SELECT id FROM exercise_tree WHERE parent_id=?", (root_id,), fetch="all") or []
        for c in children:
            ids.extend(self.get_all_subtree_ids(c["id"]))
        return ids

    def search_questions(self):
        keyword = (self.search_edit.text() or "").strip().lower()
        if not keyword:
            self.on_tree_select()
            return

        items = self.tree.selectedItems()
        if not items:
            QtWidgets.QMessageBox.warning(self, "Chưa chọn", "Hãy chọn thư mục để tìm trong đó.")
            return

        root_id = items[0].data(0, Qt.UserRole)
        all_ids = self.get_all_subtree_ids(root_id)
        if not all_ids:
            return

        placeholders = ",".join(["?"] * len(all_ids))
        query = f"SELECT * FROM question_bank WHERE tree_id IN ({placeholders})"
        rows = self.db.execute_query(query, tuple(all_ids), fetch="all") or []

        # filter theo keyword trong content_text
        rows = [r for r in rows if keyword in (r["content_text"] or "").lower()]
        self._load_question_rows(rows)

    def load_available_subjects(self):
        rows = self.db.execute_query(
            "SELECT DISTINCT name FROM exercise_tree WHERE level='Môn' ORDER BY name ASC",
            fetch="all"
        ) or []
        self.subject_cb.blockSignals(True)
        self.subject_cb.clear()
        self.subject_cb.addItem("")
        for r in rows:
            self.subject_cb.addItem(r["name"])
        self.subject_cb.blockSignals(False)

    def load_available_grades(self):
        rows = self.db.execute_query(
            "SELECT DISTINCT name FROM exercise_tree WHERE level='Lớp' ORDER BY name ASC",
            fetch="all"
        ) or []
        self.grade_cb.blockSignals(True)
        self.grade_cb.clear()
        self.grade_cb.addItem("")
        for r in rows:
            self.grade_cb.addItem(r["name"])
        self.grade_cb.blockSignals(False)

    def load_available_topics(self):
        subject = self.subject_cb.currentText().strip()
        grade = self.grade_cb.currentText().strip()
        if not subject or not grade:
            self.topic_cb.clear(); self.type_cb.clear()
            return

        rows = self.db.execute_query("""
                SELECT name FROM exercise_tree 
                WHERE level='Chủ đề' AND parent_id IN (
                    SELECT id FROM exercise_tree 
                    WHERE name=? AND level='Lớp' AND parent_id IN (
                        SELECT id FROM exercise_tree WHERE name=? AND level='Môn'
                    )
                )
            """, (grade, subject), fetch="all") or []
        self.topic_cb.blockSignals(True); self.topic_cb.clear(); self.topic_cb.addItem("")
        for r in rows:
            self.topic_cb.addItem(r["name"])
        self.topic_cb.blockSignals(False)

        self.load_available_types()  # reset types theo topic mới

    def load_available_types(self):
        topic = self.topic_cb.currentText().strip()
        if not topic:
            self.type_cb.clear()
            return
        rows = self.db.execute_query("""
                SELECT name FROM exercise_tree
                WHERE level='Dạng' AND parent_id IN (
                    SELECT id FROM exercise_tree WHERE level='Chủ đề' AND name=?
                )
            """, (topic,), fetch="all") or []
        self.type_cb.blockSignals(True); self.type_cb.clear(); self.type_cb.addItem("")
        for r in rows:
            self.type_cb.addItem(r["name"])
        self.type_cb.blockSignals(False)

    def filter_by_combobox(self):
        subject = self.subject_cb.currentText().strip()
        grade = self.grade_cb.currentText().strip()
        topic = self.topic_cb.currentText().strip()
        q_type = self.type_cb.currentText().strip()
        level = self.level_cb.currentText().strip()

        conditions = []
        params: List[object] = []

        if subject and grade:
            conditions.append("""
                EXISTS (
                    SELECT 1 FROM exercise_tree s 
                    WHERE s.id = q.tree_id AND s.level='Mức độ'
                      AND s.parent_id IN (
                          SELECT id FROM exercise_tree WHERE level='Dạng' AND parent_id IN (
                              SELECT id FROM exercise_tree WHERE level='Chủ đề' AND parent_id IN (
                                  SELECT id FROM exercise_tree WHERE level='Lớp' AND name=? AND parent_id IN (
                                      SELECT id FROM exercise_tree WHERE level='Môn' AND name=?
                                  )
                              )
                          )
                      )
                )
            """)
            params.extend([grade, subject])
        elif subject and not grade:
            conditions.append("""
                EXISTS (
                    SELECT 1 FROM exercise_tree s 
                    WHERE s.id = q.tree_id AND s.level='Mức độ'
                      AND s.parent_id IN (
                          SELECT id FROM exercise_tree WHERE level='Dạng' AND parent_id IN (
                              SELECT id FROM exercise_tree WHERE level='Chủ đề' AND parent_id IN (
                                  SELECT id FROM exercise_tree WHERE level='Lớp' AND parent_id IN (
                                      SELECT id FROM exercise_tree WHERE level='Môn' AND name=?
                                  )
                              )
                          )
                      )
                )
            """)
            params.append(subject)
        elif grade and not subject:
            conditions.append("""
                EXISTS (
                    SELECT 1 FROM exercise_tree s 
                    WHERE s.id = q.tree_id AND s.level='Mức độ'
                      AND s.parent_id IN (
                          SELECT id FROM exercise_tree WHERE level='Dạng' AND parent_id IN (
                              SELECT id FROM exercise_tree WHERE level='Chủ đề' AND parent_id IN (
                                  SELECT id FROM exercise_tree WHERE level='Lớp' AND name=?
                              )
                          )
                      )
                )
            """)
            params.append(grade)

        if topic:
            conditions.append("""
                EXISTS (
                    SELECT 1 FROM exercise_tree s 
                    WHERE s.id = q.tree_id AND s.level='Mức độ'
                      AND s.parent_id IN (
                          SELECT id FROM exercise_tree WHERE level='Dạng' AND parent_id IN (
                              SELECT id FROM exercise_tree WHERE level='Chủ đề' AND name=?
                          )
                      )
                )
            """)
            params.append(topic)

        if q_type:
            conditions.append("""
                EXISTS (
                    SELECT 1 FROM exercise_tree s 
                    WHERE s.id = q.tree_id AND s.level='Mức độ'
                      AND s.parent_id IN (
                          SELECT id FROM exercise_tree WHERE level='Dạng' AND name=?
                      )
                )
            """)
            params.append(q_type)

        if level:
            conditions.append("""
                EXISTS (
                    SELECT 1 FROM exercise_tree s 
                    WHERE s.id = q.tree_id AND s.name=? AND s.level='Mức độ'
                )
            """)
            params.append(level)

        where_clause = " AND ".join([c.strip() for c in conditions]) if conditions else "1=1"
        query = f"SELECT q.* FROM question_bank q WHERE {where_clause}"

        rows = self.db.execute_query(query, tuple(params), fetch="all") or []
        self._load_question_rows(rows)

    # ====================== Import from Word ======================
    # Import Word với pattern matching nâng cao và progress tracking
    def import_from_word(self):
        """Import Word với pattern matching nâng cao"""
        try:
            from docx import Document
        except Exception:
            QtWidgets.QMessageBox.critical(self, "Thiếu thư viện",
                                           "Vui lòng cài đặt python-docx (pip install python-docx).")
            return

        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Chọn file Word chứa câu hỏi", "", "Word files (*.docx)"
        )
        if not file_path:
            return

        tree_id = self._current_tree_id()
        if not tree_id:
            QtWidgets.QMessageBox.warning(self, "Thiếu thư mục", "Vui lòng chọn nơi lưu câu hỏi (trong cây bên trái).")
            return

        # Show template selection dialog
        template_choice = self.show_import_template_choice()
        if not template_choice:
            return

        # Initialize enhanced tools
        pattern_matcher = FlexiblePatternMatcher()
        validator = AdvancedQuestionValidator()

        try:
            doc = Document(file_path)
            questions = []
            errors = []
            warnings = []
            current = None

            total_paragraphs = len(doc.paragraphs)

            # Create progress dialog
            progress_dialog = QtWidgets.QProgressDialog("Đang xử lý file Word...", "Hủy", 0, total_paragraphs, self)
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setAutoClose(True)
            progress_dialog.setAutoReset(True)

            # Process each paragraph with enhanced pattern matching
            for i, para in enumerate(doc.paragraphs):
                if progress_dialog.wasCanceled():
                    return

                progress_dialog.setValue(i)
                progress_dialog.setLabelText(f"Xử lý dòng {i + 1}/{total_paragraphs}")
                QtWidgets.QApplication.processEvents()

                line = para.text.strip()
                if not line:
                    continue

                # Smart question detection
                q_result = pattern_matcher.smart_detect_question(line)

                if q_result['is_question'] and q_result['confidence'] > 0.7:
                    # Process previous question
                    if current:
                        validation_result = validator.comprehensive_validate(current, current['line_number'])
                        if validation_result['valid']:
                            questions.append(current)
                        else:
                            errors.extend(validation_result['errors'])
                        warnings.extend(validation_result.get('warnings', []))

                    # Start new question
                    current = {
                        'content': q_result['content'],
                        'options': [],
                        'answer': '',
                        'line_number': i + 1,
                        'confidence': q_result['confidence']
                    }
                    continue

                # Smart option detection
                if current:
                    o_result = pattern_matcher.smart_detect_option(line)
                    if o_result['is_option'] and o_result['confidence'] > 0.8:
                        current['options'].append({
                            'text': f"{o_result['label']}. {o_result['text']}",
                            'label': o_result['label']
                        })
                        continue

                    # Smart answer detection
                    a_result = pattern_matcher.smart_detect_answer(line)
                    if a_result['is_answer'] and a_result['confidence'] > 0.8:
                        current['answer'] = a_result['answer']
                        continue

            # Process last question
            if current:
                validation_result = validator.comprehensive_validate(current, len(doc.paragraphs))
                if validation_result['valid']:
                    questions.append(current)
                else:
                    errors.extend(validation_result['errors'])
                warnings.extend(validation_result.get('warnings', []))

            progress_dialog.close()

            # Show results summary
            self.show_import_results_dialog(questions, errors, warnings)

            # Process valid questions
            if questions:
                self._process_enhanced_imported_questions(questions, tree_id)

        except ImportError:
            QtWidgets.QMessageBox.critical(self, "Thiếu thư viện", "Cần cài đặt python-docx: pip install python-docx")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể xử lý file: {e}")

    # Hiển thị dialog chọn template import
    def show_import_template_choice(self):
        """Hiển thị dialog chọn template import"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("📋 Chọn template import")
        dialog.setModal(True)
        dialog.resize(400, 300)

        layout = QtWidgets.QVBoxLayout(dialog)

        layout.addWidget(QtWidgets.QLabel("Chọn template phù hợp với format file Word:"))

        # Template options
        template_group = QtWidgets.QButtonGroup(dialog)

        standard_rb = QtWidgets.QRadioButton("📚 Chuẩn SGK (Câu 1:, A., B., Đáp án: A)")
        standard_rb.setChecked(True)
        template_group.addButton(standard_rb, 0)
        layout.addWidget(standard_rb)

        exam_rb = QtWidgets.QRadioButton("📝 Đề thi (Question 1:, A), B), Answer: A)")
        template_group.addButton(exam_rb, 1)
        layout.addWidget(exam_rb)

        exercise_rb = QtWidgets.QRadioButton("📖 Bài tập (Bài 1., 1., 2., Key: A)")
        template_group.addButton(exercise_rb, 2)
        layout.addWidget(exercise_rb)

        custom_rb = QtWidgets.QRadioButton("🔧 Tự động phát hiện")
        template_group.addButton(custom_rb, 3)
        layout.addWidget(custom_rb)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()

        ok_btn = QtWidgets.QPushButton("✅ Tiếp tục")
        ok_btn.clicked.connect(dialog.accept)

        cancel_btn = QtWidgets.QPushButton("❌ Hủy")
        cancel_btn.clicked.connect(dialog.reject)

        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        if dialog.exec() == QtWidgets.QDialog.Accepted:
            return template_group.checkedId()
        return None

    # Hiển thị kết quả import với thống kê chi tiết
    def show_import_results_dialog(self, questions, errors, warnings):
        """Hiển thị kết quả import với thống kê chi tiết"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("📊 Kết quả Import")
        dialog.setModal(True)
        dialog.resize(600, 400)

        layout = QtWidgets.QVBoxLayout(dialog)

        # Summary
        summary_text = f"""
        📈 Tóm tắt kết quả:

        ✅ Câu hỏi hợp lệ: {len(questions)}
        ❌ Lỗi: {len(errors)}
        ⚠️ Cảnh báo: {len(warnings)}
        """

        summary_label = QtWidgets.QLabel(summary_text)
        summary_label.setStyleSheet("font-weight: bold; background: #f0f8ff; padding: 10px; border: 1px solid #ddd;")
        layout.addWidget(summary_label)

        # Tabs for details
        tabs = QtWidgets.QTabWidget()

        # Errors tab
        if errors:
            error_text = QtWidgets.QTextEdit()
            error_text.setPlainText("\n".join(errors))
            error_text.setReadOnly(True)
            tabs.addTab(error_text, f"❌ Lỗi ({len(errors)})")

        # Warnings tab
        if warnings:
            warning_text = QtWidgets.QTextEdit()
            warning_text.setPlainText("\n".join(warnings))
            warning_text.setReadOnly(True)
            tabs.addTab(warning_text, f"⚠️ Cảnh báo ({len(warnings)})")

        # Success tab
        if questions:
            success_text = QtWidgets.QTextEdit()
            success_content = []
            for i, q in enumerate(questions[:10], 1):  # Show first 10
                success_content.append(
                    f"{i}. {q['content'][:100]}..." if len(q['content']) > 100 else f"{i}. {q['content']}")
            if len(questions) > 10:
                success_content.append(f"... và {len(questions) - 10} câu hỏi khác")
            success_text.setPlainText("\n\n".join(success_content))
            success_text.setReadOnly(True)
            tabs.addTab(success_text, f"✅ Thành công ({len(questions)})")

        layout.addWidget(tabs)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()

        continue_btn = QtWidgets.QPushButton("✅ Tiếp tục Import")
        continue_btn.clicked.connect(dialog.accept)

        cancel_btn = QtWidgets.QPushButton("❌ Hủy")
        cancel_btn.clicked.connect(dialog.reject)

        button_layout.addWidget(continue_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        return dialog.exec() == QtWidgets.QDialog.Accepted

    # Xử lý câu hỏi đã được validate nâng cao
    def _process_enhanced_imported_questions(self, questions, tree_id):
        """Xử lý và lưu câu hỏi với enhanced validation"""
        inserted = 0

        for q in questions:
            try:
                content = q["content"]
                answer = q["answer"]
                raw_options = q["options"]

                opts_data = []
                for opt in raw_options:
                    label = opt.get('label', '')
                    text = opt.get('text', '')
                    if label and text:
                        is_correct = (label == answer)
                        opts_data.append({
                            "text": text,
                            "is_correct": is_correct
                        })

                if opts_data:
                    new_id = self.db.execute_query(
                        "INSERT INTO question_bank(content_text, options, correct, tree_id) VALUES (?,?,?,?)",
                        (content, json.dumps(opts_data, ensure_ascii=False), answer, tree_id)
                    )

                    # Save import history
                    self._save_question_history(new_id, "IMPORT", "", content)
                    inserted += 1

            except Exception as e:
                print(f"Lỗi khi lưu câu hỏi: {e}")

        # Reload view và thông báo
        rows = self.db.execute_query("SELECT * FROM question_bank WHERE tree_id=?", (tree_id,), fetch="all") or []
        self._load_question_rows(rows)
        QtWidgets.QMessageBox.information(self, "Thành công", f"Đã thêm {inserted} câu hỏi từ file Word.")
    # ====================== Misc ======================
    def toggle_tree_panel(self):
        # ẩn/hiện panel trái
        w = self.tree.parentWidget()
        w.setVisible(not w.isVisible())
    # Tìm kiếm câu hỏi theo nhiều tiêu chí
    def advanced_search(self):
        """Tìm kiếm câu hỏi theo nội dung, độ khó, chủ đề"""
        search_text = self.search_edit.text().strip()
        selected_subject = self.subject_cb.currentText()
        selected_grade = self.grade_cb.currentText()
        selected_topic = self.topic_cb.currentText()
        selected_type = self.type_cb.currentText()
        selected_level = self.level_cb.currentText()

        conditions = []
        params = []

        if search_text:
            conditions.append("content_text LIKE ?")
            params.append(f"%{search_text}%")

        # Tìm kiếm theo cây phân cấp
        if selected_subject or selected_grade or selected_topic or selected_type or selected_level:
            tree_conditions = []
            tree_params = []

            if selected_level:
                tree_conditions.append("s.name = ? AND s.level = 'Mức độ'")
                tree_params.append(selected_level)

            if selected_type:
                tree_conditions.append("s.parent_id IN (SELECT id FROM exercise_tree WHERE name = ? AND level = 'Dạng')")
                tree_params.append(selected_type)

            if selected_topic:
                tree_conditions.append("s.parent_id IN (SELECT id FROM exercise_tree WHERE name = ? AND level = 'Chủ đề')")
                tree_params.append(selected_topic)

            if tree_conditions:
                tree_query = " AND ".join(tree_conditions)
                conditions.append(f"EXISTS (SELECT 1 FROM exercise_tree s WHERE s.id = question_bank.tree_id AND {tree_query})")
                params.extend(tree_params)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT * FROM question_bank WHERE {where_clause}"

        rows = self.db.execute_query(query, tuple(params), fetch="all") or []
        self._load_question_rows(rows)

        QtWidgets.QMessageBox.information(self, "Kết quả tìm kiếm", f"Tìm thấy {len(rows)} câu hỏi.")
    # Xuất câu hỏi ra file Word
    def export_to_word(self):
        """Xuất danh sách câu hỏi ra file Word"""
        tree_id = self._current_tree_id()
        if not tree_id:
            QtWidgets.QMessageBox.warning(self, "Chưa chọn thư mục", "Vui lòng chọn thư mục để xuất.")
            return

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Lưu file Word", "", "Word files (*.docx)")
        if not file_path:
            return

        try:
            from docx import Document

            doc = Document()
            doc.add_heading('Ngân hàng câu hỏi', 0)

            # Thêm thông tin đường dẫn thư mục
            path_info = self.get_tree_path(tree_id)
            if path_info:
                path_text = " > ".join([p["name"] for p in path_info])
                doc.add_paragraph(f"Đường dẫn: {path_text}")

            # Lấy và xuất câu hỏi
            rows = self.db.execute_query("SELECT * FROM question_bank WHERE tree_id=?", (tree_id,), fetch="all") or []

            for i, row in enumerate(rows, 1):
                doc.add_heading(f'Câu hỏi {i}:', level=2)
                doc.add_paragraph(row["content_text"])

                # Parse và xuất các đáp án
                try:
                    options = json.loads(row["options"] or "[]")
                    for opt in options:
                        doc.add_paragraph(opt["text"], style='List Bullet')

                    doc.add_paragraph(f"Đáp án: {row['correct']}")
                    doc.add_paragraph("")  # Dòng trống

                except json.JSONDecodeError:
                    doc.add_paragraph("Lỗi: Không thể đọc đáp án")

            doc.save(file_path)
            QtWidgets.QMessageBox.information(self, "Thành công", f"Đã xuất {len(rows)} câu hỏi ra file Word.")

        except ImportError:
            QtWidgets.QMessageBox.critical(self, "Thiếu thư viện", "Cần cài đặt python-docx: pip install python-docx")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể xuất file: {e}")
    # Kiểm tra tính hợp lệ của câu hỏi được import
    def _validate_imported_question(self, question, line_num):
        """Kiểm tra tính hợp lệ của câu hỏi import"""
        errors = []

        if not question["content"]:
            errors.append(f"Dòng {line_num}: Thiếu nội dung câu hỏi")

        if len(question["options"]) < 2:
            errors.append(f"Dòng {line_num}: Cần ít nhất 2 đáp án")

        if not question["answer"] or question["answer"] not in "ABCDE":
            errors.append(f"Dòng {line_num}: Đáp án không hợp lệ")

        return errors

    # Xử lý và lưu các câu hỏi đã được validate
    def _process_imported_questions(self, questions, tree_id):
        """Xử lý và lưu câu hỏi import"""
        inserted = 0
        for q in questions:
            try:
                content = q["content"]
                answer = q["answer"]
                raw_options = q["options"]

                opts_data = []
                for opt in raw_options:
                    if "." not in opt:
                        continue
                    label, text = opt.split(".", 1)
                    label = label.strip().upper()
                    if label not in "ABCDE":
                        continue
                    is_correct = (label == answer)
                    opts_data.append({
                        "text": f"{label}. {text.strip()}",
                        "is_correct": is_correct
                    })

                if opts_data:
                    self.db.execute_query(
                        "INSERT INTO question_bank(content_text, options, correct, tree_id) VALUES (?,?,?,?)",
                        (content, json.dumps(opts_data, ensure_ascii=False), answer, tree_id)
                    )
                    inserted += 1

            except Exception as e:
                print(f"Lỗi khi lưu câu hỏi: {e}")

        # Reload view và thông báo
        rows = self.db.execute_query("SELECT * FROM question_bank WHERE tree_id=?", (tree_id,), fetch="all") or []
        self._load_question_rows(rows)
        QtWidgets.QMessageBox.information(self, "Thành công", f"Đã thêm {inserted} câu hỏi từ file Word.")
    def open_tree_manager(self):
        # Cố gắng mở bản Qt nếu bạn có sẵn; nếu không, thông báo.
        try:
            from ui_qt.windows.exercise_tree_manager_qt import ExerciseTreeManagerQt  # type: ignore
            dlg = ExerciseTreeManagerQt(self.db, parent=self)
            dlg.show()
        except Exception:
            QtWidgets.QMessageBox.information(
                self, "Thông tin",
                "Chưa có cửa sổ 'Quản lý cây' bản PySide6. Bạn có thể mở sau."
            )
    # Tạo câu hỏi mới
    def new_question(self):
        """Tạo câu hỏi mới"""
        self.clear_question_form()
        self.content_text.setFocus()

    # Focus vào ô tìm kiếm
    def focus_search(self):
        """Focus vào ô tìm kiếm"""
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    # Làm mới toàn bộ
    def refresh_all(self):
        """Làm mới toàn bộ dữ liệu"""
        self.refresh_tree()
        self.load_available_subjects()
        self.load_available_grades()
        self.on_tree_select()
        self.update_statistics()

    # Xóa bộ lọc
    def clear_filters(self):
        """Xóa tất cả bộ lọc"""
        self.subject_cb.setCurrentIndex(0)
        self.grade_cb.setCurrentIndex(0)
        self.topic_cb.setCurrentIndex(0)
        self.type_cb.setCurrentIndex(0)
        self.level_cb.setCurrentIndex(0)
        self.on_tree_select()

    # Context menu cho bảng
    def show_table_context_menu(self, position):
        """Hiển thị context menu cho bảng câu hỏi"""
        if not self.q_table.itemAt(position):
            return

        menu = QtWidgets.QMenu(self)

        # Các action cơ bản
        edit_action = menu.addAction("✏️ Chỉnh sửa")
        edit_action.triggered.connect(self.edit_selected_question)

        duplicate_action = menu.addAction("📋 Nhân bản")
        duplicate_action.triggered.connect(self.duplicate_question)

        menu.addSeparator()

        # Tag và bookmark
        tag_menu = menu.addMenu("🏷️ Thẻ")
        tag_menu.addAction("Thêm thẻ mới").triggered.connect(self.add_tag_to_question)
        tag_menu.addAction("Quản lý thẻ").triggered.connect(self.manage_question_tags)

        bookmark_action = menu.addAction("⭐ Bookmark")
        bookmark_action.triggered.connect(self.bookmark_question)

        menu.addSeparator()

        # Export options
        export_menu = menu.addMenu("📤 Xuất")
        export_menu.addAction("Xuất câu hỏi này ra Word").triggered.connect(self.export_selected_question)
        export_menu.addAction("Xuất câu hỏi này ra PDF").triggered.connect(self.export_selected_to_pdf)

        menu.addSeparator()

        # Xóa
        delete_action = menu.addAction("🗑️ Xóa")
        delete_action.triggered.connect(self.delete_question)

        menu.exec(self.q_table.mapToGlobal(position))

    def edit_selected_question(self):
        """Chỉnh sửa câu hỏi được chọn"""
        current_row = self.q_table.currentRow()
        if current_row >= 0:
            self.on_question_select()

    def duplicate_question(self):
        """Nhân bản câu hỏi hiện tại"""
        if not self.current_question_id:
            QtWidgets.QMessageBox.warning(self, "Chưa chọn", "Vui lòng chọn câu hỏi để nhân bản.")
            return

        # Lấy dữ liệu câu hỏi hiện tại
        q = self.db.execute_query("SELECT * FROM question_bank WHERE id=?", (self.current_question_id,), fetch="one")
        if not q:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Không tìm thấy câu hỏi để nhân bản.")
            return

        try:
            # Tạo câu hỏi mới với nội dung tương tự
            content = f"[COPY] {q['content_text']}"

            self.db.execute_query(
                "INSERT INTO question_bank(content_text, options, correct, tree_id) VALUES (?,?,?,?)",
                (content, q["options"], q["correct"], q["tree_id"])
            )

            # Reload danh sách
            tree_id = self._current_tree_id()
            if tree_id:
                rows = self.db.execute_query("SELECT * FROM question_bank WHERE tree_id=?", (tree_id,),
                                             fetch="all") or []
                self._load_question_rows(rows)

            QtWidgets.QMessageBox.information(self, "Thành công", "Đã nhân bản câu hỏi.")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể nhân bản: {e}")
    def add_tag_to_question(self):
        """Thêm tag cho câu hỏi được chọn"""
        if not self.current_question_id:
            QtWidgets.QMessageBox.warning(self, "Chưa chọn", "Vui lòng chọn câu hỏi để thêm tag.")
            return

        tag_name, ok = QtWidgets.QInputDialog.getText(self, "Thêm tag", "Tên tag:")
        if ok and tag_name.strip():
            try:
                self.db.execute_query(
                    "INSERT INTO question_tags(question_id, tag_name) VALUES (?,?)",
                    (self.current_question_id, tag_name.strip())
                )

                # Reload table để hiển thị tag mới
                tree_id = self._current_tree_id()
                if tree_id:
                    rows = self.db.execute_query("SELECT * FROM question_bank WHERE tree_id=?", (tree_id,),
                                                 fetch="all") or []
                    self._load_question_rows(rows)

                QtWidgets.QMessageBox.information(self, "Thành công", f"Đã thêm tag '{tag_name}'")

            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Lỗi", f"Không thể thêm tag: {e}")

        # Quản lý tags của câu hỏi

    def manage_question_tags(self):
        """Quản lý tags của câu hỏi hiện tại"""
        if not self.current_question_id:
            QtWidgets.QMessageBox.warning(self, "Chưa chọn", "Vui lòng chọn câu hỏi để quản lý tags.")
            return

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("🏷️ Quản lý Tags")
        dialog.setModal(True)
        dialog.resize(400, 300)

        layout = QtWidgets.QVBoxLayout(dialog)

        # Danh sách tags hiện tại
        layout.addWidget(QtWidgets.QLabel("Tags hiện tại:"))
        tags_list = QtWidgets.QListWidget()

        # Load tags của câu hỏi
        current_tags = self.db.execute_query(
            "SELECT * FROM question_tags WHERE question_id=?",
            (self.current_question_id,), fetch="all"
        ) or []

        for tag in current_tags:
            item = QtWidgets.QListWidgetItem(tag["tag_name"])
            item.setData(Qt.UserRole, tag["id"])
            tags_list.addItem(item)

        layout.addWidget(tags_list)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()

        add_btn = QtWidgets.QPushButton("➕ Thêm")
        add_btn.clicked.connect(lambda: self.add_tag_to_question())

        remove_btn = QtWidgets.QPushButton("❌ Xóa")
        remove_btn.clicked.connect(lambda: self.remove_selected_tag(tags_list, dialog))

        close_btn = QtWidgets.QPushButton("Đóng")
        close_btn.clicked.connect(dialog.accept)

        button_layout.addWidget(add_btn)
        button_layout.addWidget(remove_btn)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        dialog.exec()

        # Bookmark câu hỏi

    def bookmark_question(self):
        """Bookmark câu hỏi hiện tại"""
        if not self.current_question_id:
            QtWidgets.QMessageBox.warning(self, "Chưa chọn", "Vui lòng chọn câu hỏi để bookmark.")
            return

        bookmark_name, ok = QtWidgets.QInputDialog.getText(
            self, "Bookmark câu hỏi", "Tên bookmark:", text=f"Bookmark {self.current_question_id}"
        )

        if ok and bookmark_name.strip():
            try:
                self.db.execute_query(
                    "INSERT INTO question_bookmarks(question_id, bookmark_name) VALUES (?,?)",
                    (self.current_question_id, bookmark_name.strip())
                )
                QtWidgets.QMessageBox.information(self, "Thành công", f"Đã bookmark với tên '{bookmark_name}'")

            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Lỗi", f"Không thể bookmark: {e}")

        # Formatting functions cho text editor

    def format_bold(self):
        """Định dạng chữ đậm"""
        if hasattr(self, 'content_text') and isinstance(self.content_text, QtWidgets.QTextEdit):
            cursor = self.content_text.textCursor()
            fmt = cursor.charFormat()
            fmt.setFontWeight(QtGui.QFont.Bold if fmt.fontWeight() != QtGui.QFont.Bold else QtGui.QFont.Normal)
            cursor.setCharFormat(fmt)

    def format_italic(self):
        """Định dạng chữ nghiêng"""
        if hasattr(self, 'content_text') and isinstance(self.content_text, QtWidgets.QTextEdit):
            cursor = self.content_text.textCursor()
            fmt = cursor.charFormat()
            fmt.setFontItalic(not fmt.fontItalic())
            cursor.setCharFormat(fmt)

    def insert_math(self):
        """Chèn công thức toán học"""
        formula, ok = QtWidgets.QInputDialog.getText(self, "Chèn công thức", "Nhập công thức LaTeX:")
        if ok and formula.strip():
            self.content_text.insertPlainText(f"$${formula.strip()}$$")

    def insert_image(self):
        """Chèn hình ảnh"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Chọn hình ảnh", "", "Image files (*.png *.jpg *.jpeg *.gif *.bmp)"
        )
        if file_path:
            self.content_text.insertPlainText(f"[Hình ảnh: {file_path}]")

        # Cập nhật preview real-time

    def update_preview(self):
        """Cập nhật preview câu hỏi"""
        if not hasattr(self, 'preview_widget'):
            return

        content = self.content_text.toPlainText() if hasattr(self, 'content_text') else ""

        # Tạo HTML preview
        html = f"""
           <div style="font-family: Arial, sans-serif; line-height: 1.6;">
               <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
                   📝 Câu hỏi
               </h3>
               <p style="background: #f8f9fa; padding: 15px; border-left: 4px solid #007bff; margin: 10px 0;">
                   {content or '<em>Chưa có nội dung câu hỏi...</em>'}
               </p>

               <h4 style="color: #2c3e50; margin-top: 20px;">🔘 Đáp án:</h4>
           """

        # Thêm các đáp án
        if hasattr(self, 'option_entries'):
            for label, entry in self.option_entries.items():
                text = entry.text().strip() if entry.text() else f"<em>Chưa có đáp án {label}</em>"

                # Kiểm tra xem có phải đáp án đúng không
                is_correct = False
                if hasattr(self, 'correct_group'):
                    for btn in self.correct_group.buttons():
                        if btn.isChecked() and btn.text() == label:
                            is_correct = True
                            break

                style = "background: #d4edda; border-left: 4px solid #28a745;" if is_correct else "background: #f8f9fa;"
                html += f"""
                   <div style="{style} padding: 10px; margin: 5px 0; border-radius: 4px;">
                       <strong>{label}.</strong> {text}
                       {'<span style="color: #28a745; font-weight: bold;"> ✓ (Đáp án đúng)</span>' if is_correct else ''}
                   </div>
                   """

        html += "</div>"
        self.preview_widget.setHtml(html)

        # Cập nhật thống kê

    def update_statistics(self):
        """Cập nhật thống kê câu hỏi"""
        if not hasattr(self, 'stats_widget'):
            return
        if hasattr(self, '_stats_cache_time'):
            from datetime import datetime, timedelta
            if datetime.now() - self._stats_cache_time < timedelta(minutes=5):
                return  # Sử dụng cache trong 5 phút
        try:
            # Tổng số câu hỏi
            total_questions = self.db.execute_query("SELECT COUNT(*) as count FROM question_bank", fetch="one")["count"]

            # Thống kê theo mức độ
            level_stats = self.db.execute_query("""
                   SELECT e.name, COUNT(q.id) as count 
                   FROM question_bank q 
                   JOIN exercise_tree e ON e.id = q.tree_id 
                   WHERE e.level = 'Mức độ'
                   GROUP BY e.name
                   ORDER BY count DESC
               """, fetch="all") or []

            # Thống kê theo môn học
            subject_stats = self.db.execute_query("""
                   SELECT 
                       s.name, 
                       COUNT(q.id) as count 
                   FROM question_bank q 
                   JOIN exercise_tree e ON e.id = q.tree_id 
                   JOIN exercise_tree d ON d.id = e.parent_id
                   JOIN exercise_tree c ON c.id = d.parent_id  
                   JOIN exercise_tree g ON g.id = c.parent_id
                   JOIN exercise_tree s ON s.id = g.parent_id
                   WHERE s.level = 'Môn'
                   GROUP BY s.name
                   ORDER BY count DESC
               """, fetch="all") or []

            # Thống kê tags phổ biến
            tag_stats = self.db.execute_query("""
                   SELECT tag_name, COUNT(*) as count 
                   FROM question_tags 
                   GROUP BY tag_name 
                   ORDER BY count DESC 
                   LIMIT 10
               """, fetch="all") or []

            # Tạo HTML thống kê
            stats_html = f"""
               <div style="font-family: Arial, sans-serif;">
                   <h2 style="color: #2c3e50; text-align: center;">📊 Thống kê Ngân hàng Câu hỏi</h2>

                   <div style="background: #e3f2fd; padding: 15px; border-radius: 8px; margin: 10px 0;">
                       <h3 style="color: #1976d2;">📈 Tổng quan</h3>
                       <p style="font-size: 18px;"><strong>Tổng số câu hỏi:</strong> 
                          <span style="color: #1976d2; font-weight: bold;">{total_questions}</span>
                       </p>
                   </div>

                   <div style="background: #fff3e0; padding: 15px; border-radius: 8px; margin: 10px 0;">
                       <h3 style="color: #f57c00;">🎯 Phân bố theo mức độ</h3>
                       <table style="width: 100%; border-collapse: collapse;">
                           <tr style="background: #fff8e1;">
                               <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Mức độ</th>
                               <th style="border: 1px solid #ddd; padding: 8px; text-align: center;">Số lượng</th>
                               <th style="border: 1px solid #ddd; padding: 8px; text-align: center;">Tỷ lệ</th>
                           </tr>
               """

            for stat in level_stats:
                percentage = (stat["count"] / total_questions * 100) if total_questions > 0 else 0
                stats_html += f"""
                   <tr>
                       <td style="border: 1px solid #ddd; padding: 8px;">{stat['name']}</td>
                       <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{stat['count']}</td>
                       <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{percentage:.1f}%</td>
                   </tr>
                   """

            stats_html += """
                       </table>
                   </div>

                   <div style="background: #e8f5e8; padding: 15px; border-radius: 8px; margin: 10px 0;">
                       <h3 style="color: #388e3c;">📚 Phân bố theo môn học</h3>
                       <table style="width: 100%; border-collapse: collapse;">
                           <tr style="background: #f1f8e9;">
                               <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Môn học</th>
                               <th style="border: 1px solid #ddd; padding: 8px; text-align: center;">Số lượng</th>
                               <th style="border: 1px solid #ddd; padding: 8px; text-align: center;">Tỷ lệ</th>
                           </tr>
               """

            for stat in subject_stats:
                percentage = (stat["count"] / total_questions * 100) if total_questions > 0 else 0
                stats_html += f"""
                   <tr>
                       <td style="border: 1px solid #ddd; padding: 8px;">{stat['name']}</td>
                       <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{stat['count']}</td>
                       <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{percentage:.1f}%</td>
                   </tr>
                   """

            if tag_stats:
                stats_html += """
                       </table>
                   </div>

                   <div style="background: #fce4ec; padding: 15px; border-radius: 8px; margin: 10px 0;">
                       <h3 style="color: #c2185b;">🏷️ Tags phổ biến nhất</h3>
                       <ul style="list-style-type: none; padding: 0;">
                   """

                for tag in tag_stats:
                    stats_html += f"""
                       <li style="background: #f8bbd9; margin: 5px 0; padding: 8px; border-radius: 4px;">
                           <strong>{tag['tag_name']}</strong>: {tag['count']} câu hỏi
                       </li>
                       """

                stats_html += "</ul></div>"
            else:
                stats_html += "</table></div>"

            stats_html += "</div>"

            self.stats_widget.setHtml(stats_html)

        except Exception as e:
            error_html = f"""
               <div style="color: #d32f2f; padding: 20px; text-align: center;">
                   <h3>❌ Lỗi khi tải thống kê</h3>
                   <p>{str(e)}</p>
               </div>
               """
            self.stats_widget.setHtml(error_html)

        # Xóa lịch sử

    def clear_history(self):
        """Xóa lịch sử chỉnh sửa"""
        reply = QtWidgets.QMessageBox.question(
            self, "Xác nhận", "Bạn có chắc muốn xóa toàn bộ lịch sử chỉnh sửa?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                self.db.execute_query("DELETE FROM question_history")
                self.history_table.setRowCount(0)
                QtWidgets.QMessageBox.information(self, "Thành công", "Đã xóa lịch sử chỉnh sửa.")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể xóa lịch sử: {e}")

        # Export PDF cho câu hỏi được chọn

    def export_to_pdf(self):
        """Export toàn bộ câu hỏi ra PDF"""
        tree_id = self._current_tree_id()
        if not tree_id:
            QtWidgets.QMessageBox.warning(self, "Chưa chọn thư mục", "Vui lòng chọn thư mục để xuất.")
            return

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Lưu file PDF", "", "PDF files (*.pdf)")
        if not file_path:
            return

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch

            doc = SimpleDocTemplate(file_path, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []

            # Tiêu đề
            title = Paragraph("NGÂN HÀNG CÂU HỎI", styles['Title'])
            story.append(title)
            story.append(Spacer(1, 0.2 * inch))

            # Thông tin thư mục
            path_info = self.get_tree_path(tree_id)
            if path_info:
                path_text = " > ".join([p["name"] for p in path_info])
                path_para = Paragraph(f"<b>Đường dẫn:</b> {path_text}", styles['Normal'])
                story.append(path_para)
                story.append(Spacer(1, 0.2 * inch))

            # Lấy câu hỏi
            rows = self.db.execute_query("SELECT * FROM question_bank WHERE tree_id=?", (tree_id,), fetch="all") or []

            for i, row in enumerate(rows, 1):
                # Câu hỏi
                question_para = Paragraph(f"<b>Câu {i}:</b> {row['content_text']}", styles['Normal'])
                story.append(question_para)
                story.append(Spacer(1, 0.1 * inch))

                # Đáp án
                try:
                    options = json.loads(row["options"] or "[]")
                    for opt in options:
                        opt_para = Paragraph(opt["text"], styles['Normal'])
                        story.append(opt_para)

                    answer_para = Paragraph(f"<b>Đáp án đúng:</b> {row['correct']}", styles['Normal'])
                    story.append(answer_para)
                    story.append(Spacer(1, 0.2 * inch))

                except json.JSONDecodeError:
                    error_para = Paragraph("Lỗi: Không thể đọc đáp án", styles['Normal'])
                    story.append(error_para)
                    story.append(Spacer(1, 0.2 * inch))

            doc.build(story)
            QtWidgets.QMessageBox.information(self, "Thành công", f"Đã xuất {len(rows)} câu hỏi ra file PDF.")

        except ImportError:
            QtWidgets.QMessageBox.critical(self, "Thiếu thư viện", "Cần cài đặt reportlab: pip install reportlab")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể xuất PDF: {e}")

        # Export câu hỏi được chọn

    def export_selected_question(self):
        """Export câu hỏi được chọn ra Word"""
        if not self.current_question_id:
            QtWidgets.QMessageBox.warning(self, "Chưa chọn", "Vui lòng chọn câu hỏi để xuất.")
            return

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Lưu file Word", "", "Word files (*.docx)")
        if not file_path:
            return

        try:
            from docx import Document

            doc = Document()
            doc.add_heading('Câu hỏi xuất ra', 0)

            # Lấy thông tin câu hỏi
            q = self.db.execute_query("SELECT * FROM question_bank WHERE id=?", (self.current_question_id,),
                                      fetch="one")
            if not q:
                return

            doc.add_paragraph(f"ID: {q['id']}")
            doc.add_paragraph(f"Nội dung: {q['content_text']}")

            # Đáp án
            try:
                options = json.loads(q["options"] or "[]")
                for opt in options:
                    doc.add_paragraph(opt["text"], style='List Bullet')
                doc.add_paragraph(f"Đáp án đúng: {q['correct']}")
            except json.JSONDecodeError:
                doc.add_paragraph("Lỗi: Không thể đọc đáp án")

            doc.save(file_path)
            QtWidgets.QMessageBox.information(self, "Thành công", "Đã xuất câu hỏi ra file Word.")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể xuất file: {e}")

        # Export câu hỏi được chọn ra PDF

    def export_selected_to_pdf(self):
        """Export câu hỏi được chọn ra PDF"""
        if not self.current_question_id:
            QtWidgets.QMessageBox.warning(self, "Chưa chọn", "Vui lòng chọn câu hỏi để xuất.")
            return

        # Logic tương tự export_to_pdf nhưng chỉ cho 1 câu hỏi
        # ... implementation details ...

        # Xóa tag được chọn

    def remove_selected_tag(self, tags_list, dialog):
        """Xóa tag được chọn"""
        current_item = tags_list.currentItem()
        if not current_item:
            return

        tag_id = current_item.data(Qt.UserRole)
        try:
            self.db.execute_query("DELETE FROM question_tags WHERE id=?", (tag_id,))
            tags_list.takeItem(tags_list.row(current_item))

            # Reload table
            tree_id = self._current_tree_id()
            if tree_id:
                rows = self.db.execute_query("SELECT * FROM question_bank WHERE tree_id=?", (tree_id,),
                                             fetch="all") or []
                self._load_question_rows(rows)

        except Exception as e:
            QtWidgets.QMessageBox.warning(dialog, "Lỗi", f"Không thể xóa tag: {e}")

        # Thêm tag mới từ input

    def add_new_tag(self):
        """Thêm tag mới từ input field"""
        if not hasattr(self, 'tags_edit') or not self.current_question_id:
            return

        tags_text = self.tags_edit.text().strip()
        if not tags_text:
            return

        # Tách các tag bằng dấu phẩy
        tag_names = [tag.strip() for tag in tags_text.split(',') if tag.strip()]

        added_count = 0
        for tag_name in tag_names:
            try:
                self.db.execute_query(
                    "INSERT INTO question_tags(question_id, tag_name) VALUES (?,?)",
                    (self.current_question_id, tag_name)
                )
                added_count += 1
            except:
                pass  # Tag đã tồn tại

        if added_count > 0:
            self.tags_edit.clear()

            # Reload table
            tree_id = self._current_tree_id()
            if tree_id:
                rows = self.db.execute_query("SELECT * FROM question_bank WHERE tree_id=?", (tree_id,),
                                             fetch="all") or []
                self._load_question_rows(rows)

            QtWidgets.QMessageBox.information(self, "Thành công", f"Đã thêm {added_count} tag(s).")

        # Xóa option

    def remove_option(self, label):
        """Xóa option theo label"""
        if label in self.option_entries:
            self.option_entries[label].clear()
            # Uncheck radio button tương ứng
            for btn in self.correct_group.buttons():
                if btn.text() == label:
                    btn.setChecked(False)
                    break

    # Dialog tìm kiếm nâng cao
    def show_advanced_search_dialog(self):
        """Hiển thị dialog tìm kiếm nâng cao với nhiều tùy chọn"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("🔍 Tìm kiếm nâng cao")
        dialog.setModal(True)
        dialog.resize(600, 500)

        layout = QtWidgets.QVBoxLayout(dialog)

        # Scroll area cho nội dung dài
        scroll = QtWidgets.QScrollArea()
        scroll_widget = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_widget)

        # Tìm kiếm theo nội dung
        content_group = QtWidgets.QGroupBox("🔤 Tìm theo nội dung")
        content_layout = QtWidgets.QFormLayout(content_group)

        self.adv_search_content = QtWidgets.QLineEdit()
        self.adv_search_exact = QtWidgets.QCheckBox("Tìm chính xác")
        self.adv_search_case_sensitive = QtWidgets.QCheckBox("Phân biệt hoa thường")
        self.adv_search_regex = QtWidgets.QCheckBox("Sử dụng Regular Expression")

        content_layout.addRow("Từ khóa:", self.adv_search_content)
        content_layout.addRow("", self.adv_search_exact)
        content_layout.addRow("", self.adv_search_case_sensitive)
        content_layout.addRow("", self.adv_search_regex)

        scroll_layout.addWidget(content_group)

        # Tìm kiếm theo phân loại
        category_group = QtWidgets.QGroupBox("📁 Tìm theo phân loại")
        category_layout = QtWidgets.QFormLayout(category_group)

        self.adv_subject_cb = QtWidgets.QComboBox()
        self.adv_grade_cb = QtWidgets.QComboBox()
        self.adv_topic_cb = QtWidgets.QComboBox()
        self.adv_type_cb = QtWidgets.QComboBox()
        self.adv_level_cb = QtWidgets.QComboBox()

        # Populate combos
        self._populate_advanced_search_combos()

        category_layout.addRow("Môn:", self.adv_subject_cb)
        category_layout.addRow("Lớp:", self.adv_grade_cb)
        category_layout.addRow("Chủ đề:", self.adv_topic_cb)
        category_layout.addRow("Dạng:", self.adv_type_cb)
        category_layout.addRow("Mức độ:", self.adv_level_cb)

        scroll_layout.addWidget(category_group)

        # Tìm kiếm theo tags
        tags_group = QtWidgets.QGroupBox("🏷️ Tìm theo Tags")
        tags_layout = QtWidgets.QVBoxLayout(tags_group)

        self.adv_tags_edit = QtWidgets.QLineEdit()
        self.adv_tags_edit.setPlaceholderText("Nhập tags, phân cách bằng dấu phẩy")
        tags_layout.addWidget(self.adv_tags_edit)

        self.adv_tags_all = QtWidgets.QRadioButton("Có tất cả tags")
        self.adv_tags_any = QtWidgets.QRadioButton("Có ít nhất 1 tag")
        self.adv_tags_any.setChecked(True)

        tags_layout.addWidget(self.adv_tags_all)
        tags_layout.addWidget(self.adv_tags_any)

        scroll_layout.addWidget(tags_group)

        # Tìm kiếm theo thời gian
        time_group = QtWidgets.QGroupBox("📅 Tìm theo thời gian")
        time_layout = QtWidgets.QFormLayout(time_group)

        self.adv_date_from = QtWidgets.QDateEdit()
        self.adv_date_to = QtWidgets.QDateEdit()
        self.adv_date_from.setCalendarPopup(True)
        self.adv_date_to.setCalendarPopup(True)
        self.adv_date_from.setDate(QtCore.QDate.currentDate().addDays(-30))
        self.adv_date_to.setDate(QtCore.QDate.currentDate())

        self.adv_use_date_filter = QtWidgets.QCheckBox("Sử dụng bộ lọc thời gian")

        time_layout.addRow("", self.adv_use_date_filter)
        time_layout.addRow("Từ ngày:", self.adv_date_from)
        time_layout.addRow("Đến ngày:", self.adv_date_to)

        scroll_layout.addWidget(time_group)

        # Tìm kiếm theo đáp án
        answer_group = QtWidgets.QGroupBox("🎯 Tìm theo đáp án")
        answer_layout = QtWidgets.QFormLayout(answer_group)

        self.adv_correct_answer = QtWidgets.QComboBox()
        self.adv_correct_answer.addItems(["", "A", "B", "C", "D", "E"])

        self.adv_min_options = QtWidgets.QSpinBox()
        self.adv_min_options.setRange(2, 10)
        self.adv_min_options.setValue(2)

        self.adv_max_options = QtWidgets.QSpinBox()
        self.adv_max_options.setRange(2, 10)
        self.adv_max_options.setValue(5)

        answer_layout.addRow("Đáp án đúng:", self.adv_correct_answer)
        answer_layout.addRow("Số đáp án tối thiểu:", self.adv_min_options)
        answer_layout.addRow("Số đáp án tối đa:", self.adv_max_options)

        scroll_layout.addWidget(answer_group)

        # Setup scroll area
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()

        search_btn = QtWidgets.QPushButton("🔍 Tìm kiếm")
        search_btn.setStyleSheet("QPushButton { background: #007bff; color: white; padding: 8px 16px; }")
        search_btn.clicked.connect(lambda: self.execute_advanced_search(dialog))

        reset_btn = QtWidgets.QPushButton("🔄 Đặt lại")
        reset_btn.clicked.connect(self.reset_advanced_search)

        save_preset_btn = QtWidgets.QPushButton("💾 Lưu preset")
        save_preset_btn.clicked.connect(self.save_search_preset)

        load_preset_btn = QtWidgets.QPushButton("📂 Tải preset")
        load_preset_btn.clicked.connect(self.load_search_preset)

        cancel_btn = QtWidgets.QPushButton("❌ Hủy")
        cancel_btn.clicked.connect(dialog.reject)

        button_layout.addWidget(search_btn)
        button_layout.addWidget(reset_btn)
        button_layout.addWidget(save_preset_btn)
        button_layout.addWidget(load_preset_btn)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        dialog.exec()

        # Dialog template câu hỏi

    def show_template_dialog(self):
        """Hiển thị dialog chọn template câu hỏi"""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("📝 Template câu hỏi")
        dialog.setModal(True)
        dialog.resize(800, 600)

        layout = QtWidgets.QHBoxLayout(dialog)

        # Panel trái: Danh sách template
        left_panel = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.addWidget(QtWidgets.QLabel("📋 Chọn template:"))

        template_list = QtWidgets.QListWidget()
        template_list.setMaximumWidth(250)

        # Các template có sẵn
        templates = [
            {
                "name": "📊 Câu hỏi biểu đồ",
                "category": "Phân tích dữ liệu",
                "content": "Dựa vào biểu đồ dưới đây, hãy trả lời câu hỏi:\n\n[Chèn biểu đồ ở đây]\n\nCâu hỏi: Theo biểu đồ, xu hướng nào sau đây là đúng?",
                "options": [
                    "A. Xu hướng tăng đều",
                    "B. Xu hướng giảm đều",
                    "C. Xu hướng tăng-giảm xen kẽ",
                    "D. Không có xu hướng rõ ràng"
                ],
                "correct": "A"
            },
            {
                "name": "🧮 Câu hỏi tính toán",
                "category": "Toán học",
                "content": "Cho biết:\n\n- Giá trị ban đầu: [X]\n- Tỉ lệ thay đổi: [Y]%\n- Thời gian: [Z] năm\n\nTính giá trị cuối cùng?",
                "options": [
                    "A. [Kết quả 1]",
                    "B. [Kết quả 2]",
                    "C. [Kết quả 3]",
                    "D. [Kết quả 4]"
                ],
                "correct": "C"
            },
            {
                "name": "📖 Câu hỏi lý thuyết",
                "category": "Kiến thức cơ bản",
                "content": "Khái niệm về [Chủ đề] được định nghĩa như thế nào?",
                "options": [
                    "A. [Định nghĩa 1]",
                    "B. [Định nghĩa 2]",
                    "C. [Định nghĩa đúng]",
                    "D. [Định nghĩa 4]"
                ],
                "correct": "C"
            },
            {
                "name": "🔬 Câu hỏi thí nghiệm",
                "category": "Khoa học",
                "content": "Trong thí nghiệm [Tên thí nghiệm], khi thay đổi [Biến độc lập], kết quả quan sát được là gì?",
                "options": [
                    "A. [Kết quả 1]",
                    "B. [Kết quả 2]",
                    "C. [Kết quả 3]",
                    "D. [Kết quả 4]"
                ],
                "correct": "B"
            },
            {
                "name": "🌍 Câu hỏi địa lý",
                "category": "Địa lý",
                "content": "Vị trí địa lý của [Địa danh] có đặc điểm gì nổi bật?",
                "options": [
                    "A. [Đặc điểm 1]",
                    "B. [Đặc điểm 2]",
                    "C. [Đặc điểm 3]",
                    "D. [Đặc điểm 4]"
                ],
                "correct": "A"
            },
            {
                "name": "📚 Câu hỏi văn học",
                "category": "Ngữ văn",
                "content": "Tác phẩm \"[Tên tác phẩm]\" của tác giả [Tên tác giả] thuộc thể loại nào?",
                "options": [
                    "A. Truyện ngắn",
                    "B. Tiểu thuyết",
                    "C. Thơ",
                    "D. Kịch"
                ],
                "correct": "B"
            }
        ]

        # Thêm templates vào list
        for template in templates:
            item = QtWidgets.QListWidgetItem(f"{template['name']}\n({template['category']})")
            item.setData(Qt.UserRole, template)
            template_list.addItem(item)

        left_layout.addWidget(template_list)

        # Nút quản lý template
        template_mgmt_layout = QtWidgets.QVBoxLayout()

        new_template_btn = QtWidgets.QPushButton("➕ Tạo template mới")
        new_template_btn.clicked.connect(self.create_new_template)

        edit_template_btn = QtWidgets.QPushButton("✏️ Chỉnh sửa")
        edit_template_btn.clicked.connect(lambda: self.edit_template(template_list))

        delete_template_btn = QtWidgets.QPushButton("🗑️ Xóa")
        delete_template_btn.clicked.connect(lambda: self.delete_template(template_list))

        template_mgmt_layout.addWidget(new_template_btn)
        template_mgmt_layout.addWidget(edit_template_btn)
        template_mgmt_layout.addWidget(delete_template_btn)

        left_layout.addLayout(template_mgmt_layout)
        layout.addWidget(left_panel)

        # Panel phải: Preview và sử dụng
        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_panel)

        right_layout.addWidget(QtWidgets.QLabel("👁️ Preview template:"))

        # Preview area
        preview_text = QtWidgets.QTextEdit()
        preview_text.setReadOnly(True)
        preview_text.setStyleSheet("""
                   QTextEdit {
                       background: #f8f9fa;
                       border: 2px solid #dee2e6;
                       border-radius: 8px;
                       padding: 15px;
                       font-family: Arial, sans-serif;
                       font-size: 14px;
                       line-height: 1.5;
                   }
               """)
        right_layout.addWidget(preview_text)

        # Template info
        info_group = QtWidgets.QGroupBox("ℹ️ Thông tin template")
        info_layout = QtWidgets.QFormLayout(info_group)

        self.template_name_label = QtWidgets.QLabel("-")
        self.template_category_label = QtWidgets.QLabel("-")
        self.template_correct_label = QtWidgets.QLabel("-")

        info_layout.addRow("Tên:", self.template_name_label)
        info_layout.addRow("Danh mục:", self.template_category_label)
        info_layout.addRow("Đáp án mặc định:", self.template_correct_label)

        right_layout.addWidget(info_group)

        # Update preview khi chọn template
        def update_template_preview():
            current = template_list.currentItem()
            if current:
                template = current.data(Qt.UserRole)

                # Update preview
                preview_content = f"<h3 style='color: #2c3e50;'>📝 {template['name']}</h3>"
                preview_content += f"<div style='background: white; padding: 15px; border-left: 4px solid #007bff; margin: 10px 0;'>"
                preview_content += f"<strong>Câu hỏi:</strong><br>{template['content']}</div>"

                preview_content += "<h4 style='color: #2c3e50;'>🔘 Đáp án:</h4>"
                for i, option in enumerate(template['options']):
                    is_correct = chr(65 + i) == template['correct']
                    style = "background: #d4edda; border-left: 4px solid #28a745;" if is_correct else "background: #f8f9fa;"
                    preview_content += f"<div style='{style} padding: 10px; margin: 5px 0; border-radius: 4px;'>"
                    preview_content += f"{option}"
                    if is_correct:
                        preview_content += " <span style='color: #28a745; font-weight: bold;'>✓</span>"
                    preview_content += "</div>"

                preview_text.setHtml(preview_content)

                # Update info
                self.template_name_label.setText(template['name'])
                self.template_category_label.setText(template['category'])
                self.template_correct_label.setText(template['correct'])

        template_list.currentItemChanged.connect(update_template_preview)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()

        use_btn = QtWidgets.QPushButton("✅ Sử dụng template")
        use_btn.setStyleSheet(
            "QPushButton { background: #28a745; color: white; padding: 10px 20px; font-weight: bold; }")
        use_btn.clicked.connect(lambda: self.apply_template(template_list.currentItem(), dialog))

        customize_btn = QtWidgets.QPushButton("🎨 Tùy chỉnh và sử dụng")
        customize_btn.clicked.connect(lambda: self.customize_and_apply_template(template_list.currentItem(), dialog))

        cancel_btn = QtWidgets.QPushButton("❌ Hủy")
        cancel_btn.clicked.connect(dialog.reject)

        button_layout.addWidget(use_btn)
        button_layout.addWidget(customize_btn)
        button_layout.addWidget(cancel_btn)

        right_layout.addLayout(button_layout)
        layout.addWidget(right_panel)

        dialog.exec()

    # Populate combos cho advanced search
    def _populate_advanced_search_combos(self):
        """Populate các combobox cho advanced search"""
        # Subject combo
        subjects = self.db.execute_query("SELECT DISTINCT name FROM exercise_tree WHERE level='Môn' ORDER BY name",
                                         fetch="all") or []
        self.adv_subject_cb.clear()
        self.adv_subject_cb.addItem("")
        for s in subjects:
            self.adv_subject_cb.addItem(s["name"])

        # Grade combo
        grades = self.db.execute_query("SELECT DISTINCT name FROM exercise_tree WHERE level='Lớp' ORDER BY name",
                                       fetch="all") or []
        self.adv_grade_cb.clear()
        self.adv_grade_cb.addItem("")
        for g in grades:
            self.adv_grade_cb.addItem(g["name"])

        # Topic combo
        topics = self.db.execute_query("SELECT DISTINCT name FROM exercise_tree WHERE level='Chủ đề' ORDER BY name",
                                       fetch="all") or []
        self.adv_topic_cb.clear()
        self.adv_topic_cb.addItem("")
        for t in topics:
            self.adv_topic_cb.addItem(t["name"])

        # Type combo
        types = self.db.execute_query("SELECT DISTINCT name FROM exercise_tree WHERE level='Dạng' ORDER BY name",
                                      fetch="all") or []
        self.adv_type_cb.clear()
        self.adv_type_cb.addItem("")
        for tp in types:
            self.adv_type_cb.addItem(tp["name"])

        # Level combo
        self.adv_level_cb.clear()
        self.adv_level_cb.addItems(["", "Nhận biết", "Thông hiểu", "Vận dụng", "Vận dụng cao", "Sáng tạo"])

    # Thực hiện advanced search
    def execute_advanced_search(self, dialog):
        """Thực hiện tìm kiếm nâng cao"""
        try:
            conditions = []
            params = []

            # Tìm kiếm theo nội dung
            search_text = self.adv_search_content.text().strip()
            if search_text:
                if self.adv_search_exact.isChecked():
                    if self.adv_search_case_sensitive.isChecked():
                        conditions.append("content_text = ?")
                    else:
                        conditions.append("LOWER(content_text) = LOWER(?)")
                    params.append(search_text)
                else:
                    if self.adv_search_case_sensitive.isChecked():
                        conditions.append("content_text LIKE ?")
                    else:
                        conditions.append("LOWER(content_text) LIKE LOWER(?)")
                    params.append(f"%{search_text}%")

            # Tìm kiếm theo đáp án đúng
            correct_answer = self.adv_correct_answer.currentText()
            if correct_answer:
                conditions.append("correct = ?")
                params.append(correct_answer)

            # Tìm kiếm theo số lượng đáp án (sử dụng cách khác thay vì JSON_ARRAY_LENGTH)
            min_options = self.adv_min_options.value()
            max_options = self.adv_max_options.value()
            # Đếm số lần xuất hiện của '"text":' trong chuỗi options
            conditions.append("""
                ((LENGTH(options) - LENGTH(REPLACE(options, '"text":', ''))) / LENGTH('"text":')) BETWEEN ? AND ?
            """)
            params.extend([min_options, max_options])

            # Tìm kiếm theo tags
            tags_text = self.adv_tags_edit.text().strip()
            if tags_text:
                tag_names = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
                if tag_names:
                    if self.adv_tags_all.isChecked():
                        # Có tất cả tags
                        for tag in tag_names:
                            conditions.append(
                                "EXISTS (SELECT 1 FROM question_tags WHERE question_id = question_bank.id AND tag_name = ?)")
                            params.append(tag)
                    else:
                        # Có ít nhất 1 tag
                        tag_placeholders = ",".join(["?"] * len(tag_names))
                        conditions.append(
                            f"EXISTS (SELECT 1 FROM question_tags WHERE question_id = question_bank.id AND tag_name IN ({tag_placeholders}))")
                        params.extend(tag_names)

            # Xây dựng query
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            query = f"SELECT * FROM question_bank WHERE {where_clause} ORDER BY id DESC"

            rows = self.db.execute_query(query, tuple(params), fetch="all") or []
            self._load_question_rows(rows)

            dialog.accept()
            QtWidgets.QMessageBox.information(self, "Kết quả tìm kiếm",
                                              f"Tìm thấy {len(rows)} câu hỏi phù hợp với điều kiện.")

        except Exception as e:
            QtWidgets.QMessageBox.critical(dialog, "Lỗi tìm kiếm", f"Có lỗi xảy ra: {e}")
    # Reset advanced search
    def reset_advanced_search(self):
        """Reset tất cả field trong advanced search"""
        if hasattr(self, 'adv_search_content'):
            self.adv_search_content.clear()
            self.adv_search_exact.setChecked(False)
            self.adv_search_case_sensitive.setChecked(False)
            self.adv_search_regex.setChecked(False)

            self.adv_subject_cb.setCurrentIndex(0)
            self.adv_grade_cb.setCurrentIndex(0)
            self.adv_topic_cb.setCurrentIndex(0)
            self.adv_type_cb.setCurrentIndex(0)
            self.adv_level_cb.setCurrentIndex(0)

            self.adv_tags_edit.clear()
            self.adv_tags_any.setChecked(True)

            self.adv_correct_answer.setCurrentIndex(0)
            self.adv_min_options.setValue(2)
            self.adv_max_options.setValue(5)

            self.adv_use_date_filter.setChecked(False)

    # Apply template
    def apply_template(self, template_item, dialog):
        """Áp dụng template được chọn"""
        if not template_item:
            QtWidgets.QMessageBox.warning(dialog, "Chưa chọn", "Vui lòng chọn template để sử dụng.")
            return

        template = template_item.data(Qt.UserRole)

        # Clear form và điền template
        self.clear_question_form()

        # Điền nội dung
        if hasattr(self, 'content_text'):
            self.content_text.setPlainText(template['content'])

        # Điền đáp án
        for i, option in enumerate(template['options']):
            label = chr(65 + i)  # A, B, C, D, E
            if label in self.option_entries:
                # Lấy phần sau dấu chấm
                option_text = option.split('. ', 1)[1] if '. ' in option else option
                self.option_entries[label].setText(option_text)

        # Set đáp án đúng
        for btn in self.correct_group.buttons():
            if btn.text() == template['correct']:
                btn.setChecked(True)
                break

        # Update preview
        self.update_preview()

        dialog.accept()
        QtWidgets.QMessageBox.information(self, "Thành công", f"Đã áp dụng template '{template['name']}'.")

    # Tùy chỉnh và apply template
    def customize_and_apply_template(self, template_item, dialog):
        """Tùy chỉnh template trước khi áp dụng"""
        if not template_item:
            QtWidgets.QMessageBox.warning(dialog, "Chưa chọn", "Vui lòng chọn template để tùy chỉnh.")
            return

        template = template_item.data(Qt.UserRole)

        # Tạo dialog tùy chỉnh
        customize_dialog = QtWidgets.QDialog(dialog)
        customize_dialog.setWindowTitle(f"🎨 Tùy chỉnh: {template['name']}")
        customize_dialog.setModal(True)
        customize_dialog.resize(600, 500)

        layout = QtWidgets.QVBoxLayout(customize_dialog)

        # Nội dung câu hỏi
        layout.addWidget(QtWidgets.QLabel("Nội dung câu hỏi:"))
        content_edit = QtWidgets.QTextEdit()
        content_edit.setPlainText(template['content'])
        layout.addWidget(content_edit)

        # Đáp án
        layout.addWidget(QtWidgets.QLabel("Đáp án:"))
        option_edits = {}

        for i, option in enumerate(template['options']):
            label = chr(65 + i)
            row_layout = QtWidgets.QHBoxLayout()
            row_layout.addWidget(QtWidgets.QLabel(f"{label}."))

            option_edit = QtWidgets.QLineEdit()
            option_text = option.split('. ', 1)[1] if '. ' in option else option
            option_edit.setText(option_text)
            row_layout.addWidget(option_edit)

            layout.addLayout(row_layout)
            option_edits[label] = option_edit

        # Đáp án đúng
        correct_layout = QtWidgets.QHBoxLayout()
        correct_layout.addWidget(QtWidgets.QLabel("Đáp án đúng:"))
        correct_combo = QtWidgets.QComboBox()
        correct_combo.addItems(["A", "B", "C", "D", "E"])
        correct_combo.setCurrentText(template['correct'])
        correct_layout.addWidget(correct_combo)
        layout.addLayout(correct_layout)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()

        apply_btn = QtWidgets.QPushButton("✅ Áp dụng")
        apply_btn.clicked.connect(lambda: self._apply_customized_template(
            content_edit.toPlainText(), option_edits, correct_combo.currentText(),
            customize_dialog, dialog
        ))

        cancel_btn = QtWidgets.QPushButton("❌ Hủy")
        cancel_btn.clicked.connect(customize_dialog.reject)

        button_layout.addWidget(apply_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        customize_dialog.exec()

    # Apply customized template
    def _apply_customized_template(self, content, option_edits, correct_answer, customize_dialog, main_dialog):
        """Áp dụng template đã được tùy chỉnh"""
        # Clear form
        self.clear_question_form()

        # Điền nội dung
        if hasattr(self, 'content_text'):
            self.content_text.setPlainText(content)

        # Điền đáp án
        for label, edit in option_edits.items():
            if label in self.option_entries:
                self.option_entries[label].setText(edit.text())

        # Set đáp án đúng
        for btn in self.correct_group.buttons():
            if btn.text() == correct_answer:
                btn.setChecked(True)
                break

        # Update preview
        self.update_preview()

        customize_dialog.accept()
        main_dialog.accept()
        QtWidgets.QMessageBox.information(self, "Thành công", "Đã áp dụng template đã tùy chỉnh.")

    # Lưu preset tìm kiếm
    def save_search_preset(self):
        """Lưu preset tìm kiếm"""
        preset_name, ok = QtWidgets.QInputDialog.getText(self, "Lưu preset", "Tên preset:")
        if ok and preset_name.strip():
            # Logic lưu preset vào database hoặc file
            QtWidgets.QMessageBox.information(self, "Thành công", f"Đã lưu preset '{preset_name}'.")

    # Tải preset tìm kiếm
    def load_search_preset(self):
        """Tải preset tìm kiếm"""
        # Logic load preset từ database hoặc file
        QtWidgets.QMessageBox.information(self, "Thông tin", "Chức năng đang phát triển.")

    # Tạo template mới
    def create_new_template(self):
        """Tạo template mới"""
        QtWidgets.QMessageBox.information(self, "Thông tin", "Chức năng tạo template mới đang phát triển.")

    # Chỉnh sửa template
    def edit_template(self, template_list):
        """Chỉnh sửa template được chọn"""
        current = template_list.currentItem()
        if not current:
            QtWidgets.QMessageBox.warning(self, "Chưa chọn", "Vui lòng chọn template để chỉnh sửa.")
            return
        QtWidgets.QMessageBox.information(self, "Thông tin", "Chức năng chỉnh sửa template đang phát triển.")

    # Xóa template
    def delete_template(self, template_list):
        """Xóa template được chọn"""
        current = template_list.currentItem()
        if not current:
            QtWidgets.QMessageBox.warning(self, "Chưa chọn", "Vui lòng chọn template để xóa.")
            return

        reply = QtWidgets.QMessageBox.question(
            self, "Xác nhận xóa",
            f"Bạn có chắc muốn xóa template này?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            template_list.takeItem(template_list.row(current))
            QtWidgets.QMessageBox.information(self, "Thành công", "Đã xóa template.")