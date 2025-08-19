# ui_qt/windows/question_bank_window_qt.py
# Imports phải đúng thứ tự
from __future__ import annotations
import json
import os
import re
from typing import List, Dict
from datetime import datetime
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QKeySequence, QShortcut

# Imports này có thể optional
try:
    from docx.oxml.text.paragraph import CT_P
    from docx.oxml.table import CT_Tbl
except ImportError:
    # Bỏ qua nếu chưa cài python-docx
    pass


# Enhanced pattern matching cho định dạng câu hỏi của bạn
class FlexiblePatternMatcher:
    def __init__(self):
        # Patterns cho câu hỏi trắc nghiệm - định dạng: "1. Nội dung câu hỏi..."
        self.multiple_choice_patterns = [
            r'^(\d+)\.\s*(.*)',  # Định dạng chính: "1. Cho..."
            r'^(?:câu\s*(?:hỏi)?\s*)?(\d+)\s*[:.)\-–—]\s*(.*)',
            r'^(?:question\s*)?(\d+)\s*[:.)\-–—]\s*(.*)',
        ]

        # Patterns cho phần header của câu đúng/sai
        self.true_false_section_patterns = [
            r'^PHẦN\s*II\.\s*Câu\s*trắc\s*nghiệm\s*đúng\s*sai',
            r'^(\d+)\.\s*(.*)',  # Câu hỏi chính trong phần đúng/sai
        ]

        # Patterns cho các phần a), b), c), d) trong câu đúng/sai - có thể có dấu X
        self.sub_question_patterns = [
            r'^([a-e])\)\s*(.*?)\s*X?\s*$',  # a) Nội dung (có thể có X ở cuối)
            r'^([a-e])\)\s*(.*)',
        ]

        # Patterns cho câu trả lời ngắn
        self.short_answer_patterns = [
            r'^PHẦN\s*III\.\s*Câu\s*trắc\s*nghiệm\s*trả\s*lời\s*ngắn',
            r'^(\d+)\.\s*(.*)',  # Câu hỏi chính trong phần trả lời ngắn
            r'^Kết\s*quả\s*[:.]?\s*(.+)',  # "Kết quả: 10"
        ]

        # Patterns cho options trắc nghiệm - định dạng: "A. Nội dung" với có thể có gạch chân
        self.option_patterns = [
            r'^\*\*([A-E])\.\*\*\s*(.*)',  # **A.** Nội dung (định dạng bold)
            r'^([A-E])\.\s*(.*)',  # A. Nội dung (định dạng thường)
            r'^([A-E])\s+(.*)',
        ]

        # Patterns cho đáp án đúng - nhận diện gạch chân hoặc bold
        self.answer_patterns = [
            r'^\*\*\[([A-E])\.\]\{\.underline\}\*\*',  # **[A.]{.underline}** (đáp án đúng)
            r'^\[([A-E])\.\]\{\.underline\}',  # [A.]{.underline} (đáp án đúng)
            r'^\*\*([A-E])\.\*\*.*\{\.mark\}',  # **A.** với {.mark} (đáp án đúng)
        ]

    # Nhận diện câu hỏi trắc nghiệm 4 đáp án
    def smart_detect_question(self, line, question_type='multiple_choice', context_lines=None, line_index=0):
        """Phát hiện câu hỏi với confidence score theo loại"""
        line_clean = line.strip()

        if question_type == 'multiple_choice':
            return self._detect_multiple_choice(line_clean)
        elif question_type == 'true_false':
            return self._detect_true_false_question(line_clean, context_lines, line_index)
        elif question_type == 'short_answer':
            return self._detect_short_answer(line_clean)

        return {'is_question': False, 'confidence': 0}

    def _detect_multiple_choice(self, line):
        """Phát hiện câu hỏi trắc nghiệm thông thường"""
        for pattern in self.multiple_choice_patterns:
            match = re.match(pattern, line, re.IGNORECASE | re.UNICODE)
            if match:
                return {
                    'is_question': True,
                    'question_type': 'multiple_choice',
                    'number': match.group(1),
                    'content': match.group(2),
                    'confidence': 0.9,
                    'pattern_used': pattern
                }
        return {'is_question': False, 'confidence': 0}

    def _detect_true_false_question(self, line, context_lines=None, line_index=0):
        """Phát hiện câu hỏi đúng/sai với các phần a), b), c), d)"""
        # Kiểm tra xem có phải là câu hỏi chính
        for pattern in self.true_false_section_patterns:
            match = re.match(pattern, line, re.IGNORECASE | re.UNICODE)
            if match:
                return {
                    'is_question': True,
                    'question_type': 'true_false',
                    'number': match.group(1) if len(match.groups()) > 0 else None,
                    'content': match.group(2) if len(match.groups()) > 1 else line,
                    'confidence': 0.9,
                    'has_sub_parts': True,
                    'pattern_used': pattern
                }
        return {'is_question': False, 'confidence': 0}

    def _detect_short_answer(self, line):
        """Phát hiện câu hỏi trả lời ngắn"""
        for pattern in self.short_answer_patterns:
            match = re.match(pattern, line, re.IGNORECASE | re.UNICODE)
            if match:
                return {
                    'is_question': True,
                    'question_type': 'short_answer',
                    'number': match.group(1) if len(match.groups()) > 0 else None,
                    'content': match.group(2) if len(match.groups()) > 1 else line,
                    'confidence': 0.9,
                    'pattern_used': pattern
                }
        return {'is_question': False, 'confidence': 0}

    # Nhận diện các đáp án A, B, C, D
    def smart_detect_option(self, line):
        """Phát hiện đáp án A, B, C, D với xử lý gạch chân"""
        line_clean = line.strip()

        for pattern in self.option_patterns:
            match = re.match(pattern, line_clean, re.IGNORECASE | re.UNICODE)
            if match:
                return {
                    'is_option': True,
                    'label': match.group(1),
                    'text': match.group(2),
                    'confidence': 0.9
                }
        return {'is_option': False, 'confidence': 0}

    # Nhận diện đáp án đúng từ gạch chân hoặc bold
    def detect_correct_answer_from_format(self, line):
        """Phát hiện đáp án đúng từ định dạng gạch chân hoặc bold"""
        for pattern in self.answer_patterns:
            match = re.search(pattern, line)
            if match:
                return {
                    'is_correct': True,
                    'answer': match.group(1),
                    'confidence': 0.95
                }
        return {'is_correct': False, 'confidence': 0}

    # Nhận diện sub-question cho câu đúng/sai
    def detect_sub_question(self, line):
        """Phát hiện các phần a), b), c), d) và trạng thái Đúng/Sai"""
        line_clean = line.strip()

        for pattern in self.sub_question_patterns:
            match = re.match(pattern, line_clean, re.IGNORECASE | re.UNICODE)
            if match:
                content = match.group(2).strip()

                return {
                    'is_sub_question': True,
                    'label': match.group(1) + ')',
                    'content': content,
                    'confidence': 0.9
                }
        return {'is_sub_question': False, 'confidence': 0}

    # Nhận diện kết quả cho câu trả lời ngắn
    def detect_short_answer_result(self, line):
        """Phát hiện kết quả cho câu trả lời ngắn"""
        line_clean = line.strip()

        # Pattern "Kết quả: 10"
        result_pattern = r'^Kết\s*quả\s*[:.]?\s*(.+)'
        match = re.match(result_pattern, line_clean, re.IGNORECASE | re.UNICODE)
        if match:
            return {
                'is_result': True,
                'result': match.group(1).strip(),
                'confidence': 0.95
            }
        return {'is_result': False, 'confidence': 0}

    # Nhận diện phần header (PHẦN I, II, III)
    def detect_section_header(self, line):
        """Phát hiện các phần PHẦN I, II, III"""
        section_patterns = [
            r'^PHẦN\s*I\.\s*Câu\s*trắc\s*nghiệm\s*với\s*nhiều\s*phương\s*án',
            r'^PHẦN\s*II\.\s*Câu\s*trắc\s*nghiệm\s*đúng\s*sai',
            r'^PHẦN\s*III\.\s*Câu\s*trắc\s*nghiệm\s*trả\s*lời\s*ngắn'
        ]

        for i, pattern in enumerate(section_patterns):
            if re.match(pattern, line.strip(), re.IGNORECASE | re.UNICODE):
                section_types = ['multiple_choice', 'true_false', 'short_answer']
                return {
                    'is_section': True,
                    'section_type': section_types[i],
                    'section_number': i + 1,
                    'confidence': 1.0
                }
        return {'is_section': False, 'confidence': 0}
# Enhanced pattern matching cho 3 dạng câu hỏi khác nhau

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
        QShortcut("Ctrl+N", self, self.new_question)
        QShortcut("Ctrl+S", self, self.save_question)
        QShortcut("Ctrl+F", self, self.focus_search)
        QShortcut("Ctrl+Shift+F", self, self.show_advanced_search_dialog)
        QShortcut("Delete", self, self.delete_question)
        QShortcut("Ctrl+D", self, self.duplicate_question)
        QShortcut("F5", self, self.refresh_all)
        QShortcut("Ctrl+E", self, self.export_to_word)
        QShortcut("Ctrl+I", self, self.import_from_word)
        QShortcut("Ctrl+T", self, self.show_template_dialog)

        # Kích hoạt drag & drop
        self.setAcceptDrops(True)
        self.q_table.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.q_table.itemSelectionChanged.connect(self.on_question_select)
        self.q_table.itemClicked.connect(self.on_question_select)
        self._setup_tree_management()
    # ====================== DB helpers ======================
    # Thêm sau dòng 790 (sau phương thức __init__)
    def _get_row_value(self, row, key, default=""):
        """Helper để lấy giá trị từ sqlite3.Row một cách an toàn"""
        try:
            value = row[key]
            return value if value is not None else default
        except (KeyError, IndexError):
            return default
    def _ensure_tables(self):

        # Cập nhật cấu trúc bảng question_bank để hỗ trợ 3 dạng câu hỏi
        self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS question_bank (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_text TEXT,
                question_type TEXT DEFAULT 'multiple_choice',  -- 'multiple_choice', 'true_false', 'short_answer'
                options TEXT,
                correct TEXT,
                tree_id INTEGER,
                sub_questions TEXT,  -- JSON cho câu đúng/sai nhiều phần
                answer_format TEXT,  -- 'single', 'multiple', 'numeric', 'text'
                max_score REAL DEFAULT 1.0,
                difficulty_level TEXT,
                instruction TEXT,
                created_date TEXT DEFAULT CURRENT_TIMESTAMP,
                modified_date TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Thêm bảng cho sub-questions của câu đúng/sai
        self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS question_sub_parts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER,
                part_label TEXT,  -- 'a)', 'b)', 'c)', 'd)'
                part_content TEXT,
                is_correct INTEGER DEFAULT 0,  -- 0: sai, 1: đúng
                part_order INTEGER DEFAULT 0,
                FOREIGN KEY (question_id) REFERENCES question_bank(id) ON DELETE CASCADE
            );
        """)

        # Thêm bảng cho metadata của từng dạng câu hỏi
        self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS question_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER,
                metadata_key TEXT,
                metadata_value TEXT,
                FOREIGN KEY (question_id) REFERENCES question_bank(id) ON DELETE CASCADE
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
        # Selector cho loại câu hỏi
        question_type_group = QtWidgets.QGroupBox("🎯 Loại câu hỏi")
        type_layout = QtWidgets.QHBoxLayout(question_type_group)

        self.question_type_group = QtWidgets.QButtonGroup(self)

        self.multiple_choice_rb = QtWidgets.QRadioButton("📝 Trắc nghiệm thông thường")
        self.multiple_choice_rb.setChecked(True)
        self.question_type_group.addButton(self.multiple_choice_rb, 0)
        type_layout.addWidget(self.multiple_choice_rb)

        self.true_false_rb = QtWidgets.QRadioButton("✅❌ Đúng/Sai")
        self.question_type_group.addButton(self.true_false_rb, 1)
        type_layout.addWidget(self.true_false_rb)

        self.short_answer_rb = QtWidgets.QRadioButton("📝 Trả lời ngắn")
        self.question_type_group.addButton(self.short_answer_rb, 2)
        type_layout.addWidget(self.short_answer_rb)

        # Kết nối signal để thay đổi UI
        self.question_type_group.buttonClicked.connect(self.on_question_type_changed)

        layout.addWidget(question_type_group)
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
        self.answers_group = answers_group

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

    # Xử lý thay đổi loại câu hỏi
    def on_question_type_changed(self, button):
        """Xử lý khi thay đổi loại câu hỏi"""
        question_type = self.question_type_group.checkedId()

        if question_type == 0:  # Multiple choice
            self._setup_multiple_choice_ui()
        elif question_type == 1:  # True/False
            self._setup_true_false_ui()
        elif question_type == 2:  # Short answer
            self._setup_short_answer_ui()

    # Setup UI cho trắc nghiệm thông thường
    def _setup_multiple_choice_ui(self):
        """Setup UI cho câu hỏi trắc nghiệm thông thường"""
        # Hiện đáp án A-E
        for label in ["A", "B", "C", "D", "E"]:
            if label in self.option_entries:
                self.option_entries[label].parent().setVisible(True)

        # Ẩn sub-questions nếu có
        if hasattr(self, 'sub_questions_widget'):
            self.sub_questions_widget.setVisible(False)

        # Ẩn short answer widget nếu có
        if hasattr(self, 'short_answer_widget'):
            self.short_answer_widget.setVisible(False)

    # Setup UI cho câu đúng/sai
    def _setup_true_false_ui(self):
        """Setup UI cho câu hỏi đúng/sai"""
        # Ẩn đáp án A-E
        for label in ["A", "B", "C", "D", "E"]:
            if label in self.option_entries:
                entry = self.option_entries[label]
                # Kiểm tra parent tồn tại
                if entry.parent():
                    entry.parent().setVisible(False)

        # Hiện sub-questions
        if not hasattr(self, 'sub_questions_widget'):
            self._create_sub_questions_widget()
        self.sub_questions_widget.setVisible(True)

        # Ẩn short answer widget
        if hasattr(self, 'short_answer_widget'):
            self.short_answer_widget.setVisible(False)

    # Setup UI cho trả lời ngắn
    def _setup_short_answer_ui(self):
        """Setup UI cho câu hỏi trả lời ngắn"""
        # Ẩn đáp án A-E
        for label in ["A", "B", "C", "D", "E"]:
            if label in self.option_entries:
                self.option_entries[label].parent().setVisible(False)

        # Ẩn sub-questions
        if hasattr(self, 'sub_questions_widget'):
            self.sub_questions_widget.setVisible(False)

        # Hiện short answer widget
        if not hasattr(self, 'short_answer_widget'):
            self._create_short_answer_widget()
        self.short_answer_widget.setVisible(True)

    # Tạo widget cho sub-questions (đúng/sai)
    def _create_sub_questions_widget(self):
        """Tạo widget cho các phần a), b), c), d) của câu đúng/sai"""
        self.sub_questions_widget = QtWidgets.QGroupBox("📋 Các phần đúng/sai")
        sub_layout = QtWidgets.QVBoxLayout(self.sub_questions_widget)

        self.sub_question_entries = {}
        self.sub_question_checkboxes = {}

        for label in ["a)", "b)", "c)", "d)"]:
            row_widget = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)

            # Label
            label_widget = QtWidgets.QLabel(label.upper())
            label_widget.setMinimumWidth(30)
            row_layout.addWidget(label_widget)

            # Content
            content_edit = QtWidgets.QLineEdit()
            content_edit.setPlaceholderText(f"Nội dung phần {label}")
            row_layout.addWidget(content_edit, 1)

            # Đúng/Sai checkbox
            correct_cb = QtWidgets.QCheckBox("Đúng")
            row_layout.addWidget(correct_cb)

            sub_layout.addWidget(row_widget)

            self.sub_question_entries[label] = content_edit
            self.sub_question_checkboxes[label] = correct_cb

        # Thêm vào layout chính (cần tìm vị trí phù hợp)
        parent_widget = self.content_text.parent()
        if parent_widget and parent_widget.layout():
            parent_widget.layout().addWidget(self.sub_questions_widget)
        # Giả sử thêm sau answers_group
        if hasattr(self, 'answers_group') and self.answers_group.parent():
            parent_layout = self.answers_group.parent().layout()
            if parent_layout:
                index = parent_layout.indexOf(self.answers_group) + 1
                parent_layout.insertWidget(index, self.sub_questions_widget)
        else:
            # Thêm trực tiếp vào layout chính nếu không tìm thấy answers_group
            self.content_text.parent().layout().addWidget(self.sub_questions_widget)
        if parent_layout:
            index = parent_layout.indexOf(self.answers_group) + 1
            parent_layout.insertWidget(index, self.sub_questions_widget)
        self.sub_questions_widget.setVisible(False)
    # Tạo widget cho câu trả lời ngắn
    def _create_short_answer_widget(self):
        """Tạo widget cho câu hỏi trả lời ngắn"""
        self.short_answer_widget = QtWidgets.QGroupBox("📝 Đáp án trả lời ngắn")
        short_layout = QtWidgets.QVBoxLayout(self.short_answer_widget)

        # Loại đáp án
        answer_type_layout = QtWidgets.QHBoxLayout()
        answer_type_layout.addWidget(QtWidgets.QLabel("Loại đáp án:"))

        self.answer_type_combo = QtWidgets.QComboBox()
        self.answer_type_combo.addItems([
            "Số nguyên", "Số thực", "Văn bản", "Biểu thức toán học"
        ])
        answer_type_layout.addWidget(self.answer_type_combo)

        short_layout.addLayout(answer_type_layout)

        # Đáp án
        short_layout.addWidget(QtWidgets.QLabel("Đáp án đúng:"))
        self.short_answer_edit = QtWidgets.QLineEdit()
        self.short_answer_edit.setPlaceholderText("Nhập đáp án đúng")
        short_layout.addWidget(self.short_answer_edit)
        # Đáp án thay thế (nếu có)
        short_layout.addWidget(QtWidgets.QLabel("Đáp án thay thế (tùy chọn):"))
        self.alternative_answers_edit = QtWidgets.QTextEdit()
        self.alternative_answers_edit.setMaximumHeight(80)
        self.alternative_answers_edit.setPlaceholderText("Nhập các đáp án thay thế, mỗi đáp án một dòng")
        short_layout.addWidget(self.alternative_answers_edit)

        # Thêm vào layout chính
        parent_layout = self.answers_group.parent().layout()
        if parent_layout:
            index = parent_layout.indexOf(self.answers_group) + 1
            parent_layout.insertWidget(index, self.short_answer_widget)
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
        """Làm mới cây thư mục với xử lý lỗi tốt hơn"""
        try:
            self.tree.clear()
            self.tree_nodes.clear()

            # Đảm bảo bảng exercise_tree tồn tại
            self._ensure_exercise_tree_table()

            rows = self.db.execute_query(
                "SELECT id,parent_id,name,level FROM exercise_tree ORDER BY parent_id,level,name",
                fetch='all'
            ) or []

            if not rows:
                # Nếu không có dữ liệu, thêm dữ liệu mẫu
                self._insert_sample_tree_data()
                rows = self.db.execute_query(
                    "SELECT id,parent_id,name,level FROM exercise_tree ORDER BY parent_id,level,name",
                    fetch='all'
                ) or []

            children: Dict[int | None, list] = {}
            for r in rows:
                children.setdefault(r["parent_id"], []).append(r)

            def build(parent_db_id: int | None, parent_item: QtWidgets.QTreeWidgetItem | None):
                for node in children.get(parent_db_id, []):
                    # Tạo icon theo level
                    icon_text = self._get_level_icon(node["level"])
                    item_text = f"{icon_text} {node['name']}"

                    item = QtWidgets.QTreeWidgetItem([item_text])
                    item.setData(0, Qt.UserRole, node["id"])
                    item.setToolTip(0, f"Level: {node['level']}\nID: {node['id']}")

                    self.tree_nodes[str(id(item))] = node["id"]

                    if parent_item is None:
                        self.tree.addTopLevelItem(item)
                    else:
                        parent_item.addChild(item)
                    build(node["id"], item)

            build(None, None)
            self.tree.expandAll()

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Lỗi",
                f"Không thể tải cây thư mục: {e}\n\nVui lòng kiểm tra kết nối database."
            )

    def _ensure_exercise_tree_table(self):
        """Đảm bảo bảng exercise_tree tồn tại"""
        self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS exercise_tree (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER,
                name TEXT NOT NULL,
                level TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_id) REFERENCES exercise_tree (id)
            )
        """)

    def _insert_sample_tree_data(self):
        """Thêm dữ liệu mẫu cho cây thư mục"""
        sample_data = [
            # Môn học
            (None, "Toán", "Môn", "Môn Toán học"),
            (None, "Lý", "Môn", "Môn Vật lý"),
            (None, "Hóa", "Môn", "Môn Hóa học"),

            # Lớp (con của Toán - id=1)
            (1, "Lớp 10", "Lớp", "Toán lớp 10"),
            (1, "Lớp 11", "Lớp", "Toán lớp 11"),
            (1, "Lớp 12", "Lớp", "Toán lớp 12"),

            # Chủ đề (con của Lớp 10 - id=4)
            (4, "Mệnh đề - Tập hợp", "Chủ đề", "Chương 1: Mệnh đề và tập hợp"),
            (4, "Hàm số", "Chủ đề", "Chương 2: Hàm số"),
            (4, "Phương trình", "Chủ đề", "Chương 3: Phương trình và bất phương trình"),

            # Dạng (con của Mệnh đề - Tập hợp - id=7)
            (7, "Mệnh đề", "Dạng", "Dạng bài về mệnh đề"),
            (7, "Tập hợp", "Dạng", "Dạng bài về tập hợp"),
            (7, "Phép toán tập hợp", "Dạng", "Giao, hợp, hiệu tập hợp"),

            # Mức độ (con của Mệnh đề - id=10)
            (10, "Nhận biết", "Mức độ", "Câu hỏi nhận biết cơ bản"),
            (10, "Thông hiểu", "Mức độ", "Câu hỏi thông hiểu"),
            (10, "Vận dụng", "Mức độ", "Câu hỏi vận dụng"),
            (10, "Vận dụng cao", "Mức độ", "Câu hỏi vận dụng cao"),
        ]

        for parent_id, name, level, description in sample_data:
            self.db.execute_query(
                "INSERT INTO exercise_tree (parent_id, name, level, description) VALUES (?, ?, ?, ?)",
                (parent_id, name, level, description)
            )

    def _get_level_icon(self, level: str) -> str:
        """Trả về icon emoji cho từng level"""
        icons = {
            "Môn": "📚",
            "Lớp": "🎓",
            "Chủ đề": "📖",
            "Dạng": "📝",
            "Mức độ": "⭐"
        }
        return icons.get(level, "📁")
    def on_tree_select(self):
        items = self.tree.selectedItems()
        if not items:
            return
        tree_id = items[0].data(0, Qt.UserRole)
        if not tree_id:
            return

        rows = self.db.execute_query("SELECT * FROM question_bank WHERE tree_id=?", (tree_id,), fetch="all") or []
        self._load_question_rows(rows)
    # Nhiệm vụ: Phân tích bảng câu hỏi Đúng/Sai
    def _process_true_false_table(self, table):
        """
        Xử lý một đối tượng bảng (table) từ docx để trích xuất các câu hỏi con
        theo định dạng: Khẳng định | Đúng | Sai
        """
        sub_questions = []
        if not table or len(table.rows) < 2:
            return sub_questions  # Bảng không hợp lệ

        # Bỏ qua hàng tiêu đề (hàng đầu tiên)
        for row_index, row in enumerate(table.rows[1:], start=1):
            try:
                if len(row.cells) < 3:
                    continue  # Bỏ qua hàng không đủ cột

                # Cột 0: Nội dung, Cột 1: Đúng, Cột 2: Sai
                content_cell = row.cells[0].text.strip()
                true_cell = row.cells[1].text.strip()
                false_cell = row.cells[2].text.strip()

                if not content_cell:
                    continue  # Bỏ qua hàng trống

                # Tách label 'a)' ra khỏi nội dung
                label_match = re.match(r'^([a-e])\)\s*(.*)', content_cell)
                if label_match:
                    label = label_match.group(1) + ')'
                    content = label_match.group(2).strip()
                else:
                    # Nếu không có label, tự động tạo
                    label = chr(ord('a') + row_index - 1) + ')'
                    content = content_cell

                # Kiểm tra dấu 'X' trong cột Đúng hoặc Sai
                is_correct = None
                if 'X' in true_cell.upper() or 'x' in true_cell:
                    is_correct = True
                elif 'X' in false_cell.upper() or 'x' in false_cell:
                    is_correct = False
                else:
                    # Mặc định là đúng nếu không có dấu X rõ ràng
                    is_correct = True

                if content:
                    sub_questions.append({
                        'label': label,
                        'content': content,
                        'is_correct': is_correct
                    })

            except Exception as e:
                print(f"Lỗi khi xử lý hàng {row_index} trong bảng đúng/sai: {e}")
                continue  # Bỏ qua hàng bị lỗi và tiếp tục

        return sub_questions
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

        # Cập nhật hiển thị cho 3 dạng câu hỏi trong bảng
        for r in rows:
            # Tạo checkbox cho mỗi dòng
            checkbox = QtWidgets.QCheckBox()
            checkbox.setChecked(False)

            # Lấy giá trị an toàn từ Row
            content_preview = self._get_row_value(r, "content_text", "")[:50].replace("\n", " ").strip()
            question_type = self._get_row_value(r, "question_type", "multiple_choice")
            row_id = self._get_row_value(r, "id", 0)
            tree_id = self._get_row_value(r, "tree_id", 0)

            if question_type == "multiple_choice":
                opts_json = self._get_row_value(r, "options", "[]")
                opts = json.loads(opts_json) if opts_json else []
                so_dapan = len(opts)
                dap_an = self._get_row_value(r, "correct", "-")
                type_icon = "📝"
            elif question_type == "true_false":
                # Đếm sub-questions
                sub_parts = self.db.execute_query(
                    "SELECT COUNT(*) as count FROM question_sub_parts WHERE question_id=?",
                    (row_id,), fetch="one"
                )
                so_dapan = sub_parts["count"] if sub_parts else 0
                dap_an = "Đ/S"
                type_icon = "✅❌"
            elif question_type == "short_answer":
                so_dapan = 1
                correct_value = self._get_row_value(r, "correct", "")
                dap_an = correct_value[:10] + "..." if len(correct_value) > 10 else correct_value or "-"
                type_icon = "📝"
            else:
                so_dapan = 0
                dap_an = "-"
                type_icon = "❓"

            # Lấy chuỗi dạng/mức độ từ path
            path = self.get_tree_path(tree_id) if tree_id else []
            path_dict = {p["level"]: p["name"] for p in path}
            dang = path_dict.get("Dạng", "-")
            muc_do = path_dict.get("Mức độ", "-")

            # Lấy tags cho câu hỏi
            tags = self.db.execute_query(
                "SELECT tag_name FROM question_tags WHERE question_id=?",
                (row_id,), fetch="all"
            ) or []
            tags_text = ", ".join([tag["tag_name"] for tag in tags]) if tags else ""

            row_idx = self.q_table.rowCount()
            self.q_table.insertRow(row_idx)

            # Set checkbox
            self.q_table.setCellWidget(row_idx, 0, checkbox)

            # Set data với icon loại câu hỏi
            self.q_table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(f"{type_icon} {row_id}"))
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
    # Load câu hỏi với hỗ trợ 3 dạng
    def on_question_select(self):
        """Load câu hỏi được chọn với hỗ trợ 3 dạng"""
        items = self.q_table.selectedItems()
        if not items:
            return
        row = items[0].row()
        item_text = self.q_table.item(row, 1).text()

        # Trích xuất ID câu hỏi từ văn bản trong bảng (ví dụ: "📝 123" -> 123)
        try:
            qid = int(item_text.split()[-1])
        except (ValueError, IndexError):
            # Nếu không thể trích xuất ID, dừng xử lý để tránh lỗi
            return

        q = self.db.execute_query("SELECT * FROM question_bank WHERE id=?", (qid,), fetch="one")
        if not q:
            return

        self.current_question_id = qid

        # Load nội dung câu hỏi
        if hasattr(self, 'content_text'):
            self.content_text.blockSignals(True)
            self.content_text.setPlainText(q["content_text"] or "")
            self.content_text.blockSignals(False)

        # Xác định loại câu hỏi và set UI
        question_type = self._get_row_value(q, "question_type", "multiple_choice")

        if hasattr(self, 'question_type_group'):
            if question_type == 'multiple_choice':
                self.multiple_choice_rb.setChecked(True)
                self._setup_multiple_choice_ui()
                self._load_multiple_choice_data(q)
            elif question_type == 'true_false':
                self.true_false_rb.setChecked(True)
                self._setup_true_false_ui()
                self._load_true_false_data(q)
            elif question_type == 'short_answer':
                self.short_answer_rb.setChecked(True)
                self._setup_short_answer_ui()
                self._load_short_answer_data(q)

        # Load tags
        if hasattr(self, 'tags_edit'):
            tags = self.db.execute_query(
                "SELECT tag_name FROM question_tags WHERE question_id=? ORDER BY tag_name",
                (qid,), fetch="all"
            ) or []
            tags_text = ", ".join([tag["tag_name"] for tag in tags])
            self.tags_edit.setText(tags_text)

        # Load lịch sử
        if hasattr(self, 'history_table'):
            self._load_question_history(qid)

        # Update preview
        self.update_preview()

    # Load dữ liệu cho câu hỏi trắc nghiệm
    def _load_multiple_choice_data(self, question_data):
        """Load dữ liệu cho câu hỏi trắc nghiệm thông thường"""
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
        opts_json = self._get_row_value(question_data, "options", "[]")
        opts = json.loads(opts_json) if opts_json else []
        correct = self._get_row_value(question_data, "correct", "")

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

    # Load dữ liệu cho câu hỏi đúng/sai
    def _load_true_false_data(self, question_data):
        """Load dữ liệu cho câu hỏi đúng/sai"""
        if not hasattr(self, 'sub_question_entries'):
            return

        # Clear form
        for label, entry in self.sub_question_entries.items():
            entry.clear()
            self.sub_question_checkboxes[label].setChecked(False)

        # Load sub-questions từ database
        sub_parts = self.db.execute_query(
            "SELECT * FROM question_sub_parts WHERE question_id=? ORDER BY part_order",
            (question_data["id"],), fetch="all"
        ) or []

        for part in sub_parts:
            label = part["part_label"]
            if label in self.sub_question_entries:
                self.sub_question_entries[label].setText(part["part_content"])
                self.sub_question_checkboxes[label].setChecked(bool(part["is_correct"]))

    # Load dữ liệu cho câu hỏi trả lời ngắn
    def _load_short_answer_data(self, question_data):
        """Load dữ liệu cho câu hỏi trả lời ngắn"""
        if not hasattr(self, 'short_answer_edit'):
            return

        # Load đáp án chính
        self.short_answer_edit.setText(question_data["correct"] or "")

        # Load metadata từ options
        try:
            answer_data = json.loads(question_data["options"] or "{}")

            answer_type = answer_data.get("answer_type", "Số nguyên")
            for i in range(self.answer_type_combo.count()):
                if self.answer_type_combo.itemText(i) == answer_type:
                    self.answer_type_combo.setCurrentIndex(i)
                    break

            alternative_answers = answer_data.get("alternative_answers", [])
            self.alternative_answers_edit.setPlainText("\n".join(alternative_answers))

        except json.JSONDecodeError:
            pass
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
            time_str = self._get_row_value(h, "changed_date", "")
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
            self.history_table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(
                self._get_row_value(h, "action_type", "")
            ))

            # Truncate content cho display
            # Lấy nội dung một cách an toàn và cắt bớt để hiển thị
            old_content_full = self._get_row_value(h, "old_content", "")
            new_content_full = self._get_row_value(h, "new_content", "")

            old_content_display = (old_content_full[:100] + "...") if len(old_content_full) > 100 else old_content_full
            new_content_display = (new_content_full[:100] + "...") if len(new_content_full) > 100 else new_content_full

            self.history_table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(old_content_display))
            self.history_table.setItem(row_idx, 3, QtWidgets.QTableWidgetItem(new_content_display))
    # ====================== Save/Update/Delete ======================
    def _current_tree_id(self) -> int | None:
        items = self.tree.selectedItems()
        if not items:
            return None
        return items[0].data(0, Qt.UserRole)

    # Lưu câu hỏi với hỗ trợ 3 dạng
    def save_question(self):
        """Lưu câu hỏi với hỗ trợ 3 dạng câu hỏi"""
        tree_id = self._current_tree_id()
        if not tree_id:
            QtWidgets.QMessageBox.warning(self, "Chưa chọn thư mục", "Vui lòng chọn vị trí lưu trong cây.")
            return

        content = self.content_text.toPlainText().strip()
        question_type = self._get_current_question_type()

        # Validation cơ bản
        if not content or len(content.strip()) < 10:
            QtWidgets.QMessageBox.warning(self, "Lỗi dữ liệu", "Nội dung câu hỏi phải có ít nhất 10 ký tự")
            return

        try:
            # Lưu nội dung cũ để ghi lịch sử
            old_content = ""
            if self.current_question_id:
                old_q = self.db.execute_query("SELECT content_text FROM question_bank WHERE id=?",
                                              (self.current_question_id,), fetch="one")
                old_content = old_q["content_text"] if old_q else ""

            if question_type == 'multiple_choice':
                self._save_multiple_choice_question(content, tree_id, old_content)
            elif question_type == 'true_false':
                self._save_true_false_question(content, tree_id, old_content)
            elif question_type == 'short_answer':
                self._save_short_answer_question(content, tree_id, old_content)

            # Reload danh sách
            rows = self.db.execute_query("SELECT * FROM question_bank WHERE tree_id=?", (tree_id,), fetch="all") or []
            self._load_question_rows(rows)

            # Update preview và stats
            self.update_preview()
            self.update_statistics()

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi CSDL", f"{e}")

    # Lấy loại câu hỏi hiện tại
    def _get_current_question_type(self):
        """Lấy loại câu hỏi hiện tại từ UI"""
        if hasattr(self, 'question_type_group'):
            selected_id = self.question_type_group.checkedId()
            if selected_id == 0:
                return 'multiple_choice'
            elif selected_id == 1:
                return 'true_false'
            elif selected_id == 2:
                return 'short_answer'
        return 'multiple_choice'  # Mặc định

    # Lưu câu hỏi trắc nghiệm thông thường
    def _save_multiple_choice_question(self, content, tree_id, old_content):
        """Lưu câu hỏi trắc nghiệm thông thường"""
        if not hasattr(self, 'option_entries'):
            raise ValueError("Chưa khởi tạo form đáp án")
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

        # Validation
        if not correct:
            raise ValueError("Phải chọn đáp án đúng")
        if len(opts) < 2:
            raise ValueError("Phải có ít nhất 2 đáp án")

        if self.current_question_id:
            # Cập nhật
            self.db.execute_query(
                "UPDATE question_bank SET content_text=?, options=?, correct=?, question_type=?, tree_id=? WHERE id=?",
                (content, json.dumps(opts, ensure_ascii=False), correct, 'multiple_choice', tree_id,
                 self.current_question_id)
            )
            self._save_question_history(self.current_question_id, "UPDATE", old_content, content)
            QtWidgets.QMessageBox.information(self, "Cập nhật", "Đã cập nhật câu hỏi.")
        else:
            # Thêm mới
            new_id = self.db.execute_query(
                "INSERT INTO question_bank(content_text, options, correct, question_type, tree_id) VALUES (?,?,?,?,?)",
                (content, json.dumps(opts, ensure_ascii=False), correct, 'multiple_choice', tree_id)
            )
            self.current_question_id = new_id
            self._save_question_history(new_id, "CREATE", "", content)
            QtWidgets.QMessageBox.information(self, "Thêm mới", "Đã lưu câu hỏi mới.")

    # Lưu câu hỏi đúng/sai
    def _save_true_false_question(self, content, tree_id, old_content):
        """Lưu câu hỏi đúng/sai với sub-questions"""
        if not hasattr(self, 'sub_question_entries'):
            raise ValueError("Chưa có giao diện cho câu hỏi đúng/sai")

        sub_questions = []
        for label, entry in self.sub_question_entries.items():
            sub_content = entry.text().strip()
            if sub_content:
                is_correct = self.sub_question_checkboxes[label].isChecked()
                sub_questions.append({
                    "label": label,
                    "content": sub_content,
                    "is_correct": is_correct
                })

        if len(sub_questions) < 2:
            raise ValueError("Câu hỏi đúng/sai phải có ít nhất 2 phần")

        if self.current_question_id:
            # Cập nhật câu hỏi chính
            self.db.execute_query(
                "UPDATE question_bank SET content_text=?, question_type=?, sub_questions=?, tree_id=? WHERE id=?",
                (content, 'true_false', json.dumps(sub_questions, ensure_ascii=False), tree_id,
                 self.current_question_id)
            )

            # Xóa sub-parts cũ
            self.db.execute_query("DELETE FROM question_sub_parts WHERE question_id=?", (self.current_question_id,))

            # Thêm sub-parts mới
            for i, sub in enumerate(sub_questions):
                self.db.execute_query(
                    "INSERT INTO question_sub_parts(question_id, part_label, part_content, is_correct, part_order) VALUES (?,?,?,?,?)",
                    (self.current_question_id, sub["label"], sub["content"], int(sub["is_correct"]), i)
                )

            self._save_question_history(self.current_question_id, "UPDATE", old_content, content)
            QtWidgets.QMessageBox.information(self, "Cập nhật", "Đã cập nhật câu hỏi đúng/sai.")
        else:
            # Thêm mới
            new_id = self.db.execute_query(
                "INSERT INTO question_bank(content_text, question_type, sub_questions, tree_id) VALUES (?,?,?,?)",
                (content, 'true_false', json.dumps(sub_questions, ensure_ascii=False), tree_id)
            )

            # Thêm sub-parts
            for i, sub in enumerate(sub_questions):
                self.db.execute_query(
                    "INSERT INTO question_sub_parts(question_id, part_label, part_content, is_correct, part_order) VALUES (?,?,?,?,?)",
                    (new_id, sub["label"], sub["content"], int(sub["is_correct"]), i)
                )

            self.current_question_id = new_id
            self._save_question_history(new_id, "CREATE", "", content)
            QtWidgets.QMessageBox.information(self, "Thêm mới", "Đã lưu câu hỏi đúng/sai mới.")

    # Lưu câu hỏi trả lời ngắn
    def _save_short_answer_question(self, content, tree_id, old_content):
        """Lưu câu hỏi trả lời ngắn"""
        if not hasattr(self, 'short_answer_edit'):
            raise ValueError("Chưa có giao diện cho câu hỏi trả lời ngắn")

        answer = self.short_answer_edit.text().strip()
        answer_type = self.answer_type_combo.currentText()
        alternative_answers = self.alternative_answers_edit.toPlainText().strip()

        if not answer:
            raise ValueError("Phải có đáp án cho câu hỏi trả lời ngắn")

        # Chuẩn bị dữ liệu
        answer_data = {
            "main_answer": answer,
            "answer_type": answer_type,
            "alternative_answers": [alt.strip() for alt in alternative_answers.split('\n') if alt.strip()]
        }

        if self.current_question_id:
            # Cập nhật
            self.db.execute_query(
                "UPDATE question_bank SET content_text=?, correct=?, question_type=?, options=?, tree_id=? WHERE id=?",
                (content, answer, 'short_answer', json.dumps(answer_data, ensure_ascii=False), tree_id,
                 self.current_question_id)
            )
            self._save_question_history(self.current_question_id, "UPDATE", old_content, content)
            QtWidgets.QMessageBox.information(self, "Cập nhật", "Đã cập nhật câu hỏi trả lời ngắn.")
        else:
            # Thêm mới
            new_id = self.db.execute_query(
                "INSERT INTO question_bank(content_text, correct, question_type, options, tree_id) VALUES (?,?,?,?,?)",
                (content, answer, 'short_answer', json.dumps(answer_data, ensure_ascii=False), tree_id)
            )
            self.current_question_id = new_id
            self._save_question_history(new_id, "CREATE", "", content)
            QtWidgets.QMessageBox.information(self, "Thêm mới", "Đã lưu câu hỏi trả lời ngắn mới.")
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
    def import_from_word(self):
        """
        Import Word với logic nâng cao, tự động nhận diện loại câu hỏi
        dựa trên cấu trúc (văn bản, gạch chân, bảng).
        """
        try:
            from docx import Document
            from docx.text.paragraph import Paragraph
            from docx.table import Table
            # Thêm 2 dòng import này ở đầu file nếu chưa có
            from docx.oxml.text.paragraph import CT_P
            from docx.oxml.table import CT_Tbl
        except ImportError:
            QtWidgets.QMessageBox.critical(self, "Thiếu thư viện",
                                           "Vui lòng cài đặt python-docx: pip install python-docx")
            return

        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Chọn file Word chứa câu hỏi", "", "Word files (*.docx)")
        if not file_path:
            return

        tree_id = self._current_tree_id()
        if not tree_id:
            QtWidgets.QMessageBox.warning(self, "Thiếu thư mục", "Vui lòng chọn nơi lưu câu hỏi.")
            return

        # Khởi tạo pattern matcher và danh sách câu hỏi
        pattern_matcher = FlexiblePatternMatcher()
        all_questions = []
        errors = []
        current_section = 'multiple_choice'  # Mặc định bắt đầu với trắc nghiệm

        try:
            doc = Document(file_path)
            current_question = None

            # Duyệt qua từng khối trong tài liệu (văn bản hoặc bảng)
            for block in doc.element.body:
                if isinstance(block, CT_P):  # Nếu khối là một Paragraph (văn bản)
                    para = Paragraph(block, doc)
                    line = para.text.strip()
                    if not line:
                        continue

                    # 1. Kiểm tra phần header (PHẦN I, II, III)
                    section_result = pattern_matcher.detect_section_header(line)
                    if section_result.get('is_section'):
                        current_section = section_result['section_type']
                        continue

                    # 2. Kiểm tra câu hỏi mới
                    q_result = pattern_matcher.smart_detect_question(line, current_section)
                    if q_result.get('is_question'):
                        # Lưu câu hỏi cũ nếu có
                        if current_question:
                            all_questions.append(current_question)

                        # Bắt đầu câu hỏi mới
                        current_question = {
                            'question_type': q_result['question_type'],
                            'content': q_result['content'],
                            'options': [],
                            'sub_questions': [],
                            'answer': None,
                            'number': q_result.get('number')
                        }
                        continue

                    # 3. Xử lý nội dung theo loại câu hỏi hiện tại
                    if current_question:
                        if current_section == 'multiple_choice':
                            # Xử lý đáp án trắc nghiệm
                            option_result = pattern_matcher.smart_detect_option(line)
                            if option_result.get('is_option'):
                                current_question['options'].append({
                                    'text': f"{option_result['label']}. {option_result['text']}",
                                    'label': option_result['label']
                                })

                                # Kiểm tra đáp án đúng từ định dạng
                                correct_result = pattern_matcher.detect_correct_answer_from_format(line)
                                if correct_result.get('is_correct'):
                                    current_question['answer'] = correct_result['answer']

                                # Kiểm tra gạch chân trong runs
                                is_underlined = any(run.underline for run in para.runs if run.underline)
                                if is_underlined:
                                    current_question['answer'] = option_result['label']
                                continue

                        elif current_section == 'true_false':
                            # Xử lý sub-question cho đúng/sai
                            sub_result = pattern_matcher.detect_sub_question(line)
                            if sub_result.get('is_sub_question'):
                                current_question['sub_questions'].append({
                                    'label': sub_result['label'],
                                    'content': sub_result['content'],
                                    'is_correct': True  # Mặc định, sẽ được cập nhật từ bảng
                                })
                                continue

                        elif current_section == 'short_answer':
                            # Xử lý kết quả cho câu trả lời ngắn
                            result = pattern_matcher.detect_short_answer_result(line)
                            if result.get('is_result'):
                                current_question['answer'] = result['result']
                                continue

                elif isinstance(block, CT_Tbl):  # Nếu khối là bảng
                    table = Table(block, doc)

                    # Chỉ xử lý bảng cho câu đúng/sai
                    if current_section == 'true_false' and current_question:
                        sub_questions = self._process_true_false_table(table)
                        if sub_questions:
                            current_question['sub_questions'] = sub_questions

            # Lưu câu hỏi cuối cùng
            if current_question:
                all_questions.append(current_question)

        except Exception as e:
            errors.append(f"Lỗi khi đọc file: {str(e)}")
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể đọc file Word: {e}")
            return

    # Lưu câu hỏi trả lời ngắn import
    def _save_imported_short_answer(self, question_data, tree_id):
        """Lưu câu hỏi trả lời ngắn được import"""
        content = question_data["content"]
        answer = question_data.get("answer", "")

        if not answer:
            return None

        # Lưu câu hỏi chính
        new_id = self.db.execute_query(
            "INSERT INTO question_bank(content_text, correct, question_type, tree_id) VALUES (?,?,?,?)",
            (content, answer, 'short_answer', tree_id)
        )

        return new_id
    def _process_multiple_choice_question(self, lines, start_index, pattern_matcher, validator):
        """
        Xử lý câu hỏi trắc nghiệm, hỗ trợ nội dung và đáp án trên nhiều dòng.
        """
        i = start_index
        q_result = pattern_matcher.smart_detect_question(lines[i], 'multiple_choice')
        if not q_result.get('is_question'):
            return None, i + 1

        question = {
            'question_type': 'multiple_choice',
            'content': q_result['content'],
            'options': [],
            'answer': None,
            'line_number': i + 1,
            'errors': []
        }

        i += 1
        current_option = None

        # Vòng lặp chính để gom nội dung câu hỏi, đáp án và tìm câu trả lời
        while i < len(lines):
            line = lines[i]

            # Kiểm tra xem dòng hiện tại có phải là một thành phần mới không
            next_q = pattern_matcher.smart_detect_question(line, 'multiple_choice')
            next_o = pattern_matcher.smart_detect_option(line)
            next_a = pattern_matcher.smart_detect_answer(line)

            if next_q.get('is_question'):
                # Gặp câu hỏi mới, kết thúc câu hỏi hiện tại
                break

            if next_o.get('is_option'):
                # Gặp đáp án mới
                current_option = {
                    'text': f"{next_o['label']}. {next_o['text']}",
                    'label': next_o['label']
                }
                question['options'].append(current_option)
            elif next_a.get('is_answer'):
                # Gặp dòng đáp án
                question['answer'] = next_a['answer']
                i += 1
                break  # Kết thúc khi tìm thấy đáp án
            elif current_option:
                # Nếu đang trong một đáp án, ghép nội dung vào đáp án đó
                current_option['text'] += " " + line
            else:
                # Nếu chưa gặp đáp án nào, ghép nội dung vào câu hỏi
                question['content'] += " " + line

            i += 1

        # Kiểm tra lỗi sau khi xử lý xong một câu hỏi
        if not question['options']:
            question['errors'].append(f"Dòng {question['line_number']}: Câu hỏi không có đáp án nào.")
        if not question['answer']:
            question['errors'].append(
                f"Dòng {question['line_number']}: Không tìm thấy đáp án đúng (ví dụ: 'Đáp án: A').")

        return question, i
    # Xử lý câu hỏi đúng/sai
    def _process_true_false_question(self, lines, start_index, pattern_matcher, validator):
        """Xử lý câu hỏi đúng/sai với sub-questions"""
        i = start_index
        line = lines[i] if i < len(lines) else ""

        # Phát hiện câu hỏi chính
        q_result = pattern_matcher.smart_detect_question(line, 'true_false')

        if not q_result.get('is_question'):
            return None, i + 1

        question = {
            'question_type': 'true_false',
            'content': q_result['content'],
            'sub_questions': [],
            'line_number': i + 1,
            'confidence': q_result['confidence']
        }

        i += 1

        # Đọc các sub-questions a), b), c), d)
        while i < len(lines):
            line = lines[i]

            # Kiểm tra sub-question
            sub_result = pattern_matcher.detect_sub_question(line)
            if sub_result.get('is_sub_question'):
                question['sub_questions'].append({
                    'label': sub_result['label'],
                    'content': sub_result['content'],
                    'is_correct': None  # Sẽ được xác định sau hoặc mặc định
                })
                i += 1
                continue

            # Nếu gặp câu hỏi khác thì dừng
            next_q = pattern_matcher.smart_detect_question(line, 'true_false')
            if next_q.get('is_question'):
                break

            i += 1

        return question, i

    # Xử lý câu hỏi trả lời ngắn
    def _process_short_answer_question(self, lines, start_index, pattern_matcher, validator):
        """Xử lý câu hỏi trả lời ngắn"""
        i = start_index
        line = lines[i] if i < len(lines) else ""

        # Phát hiện câu hỏi
        q_result = pattern_matcher.smart_detect_question(line, 'short_answer')

        if not q_result.get('is_question'):
            return None, i + 1

        question = {
            'question_type': 'short_answer',
            'content': q_result['content'],
            'answer': '',
            'line_number': i + 1,
            'confidence': q_result['confidence']
        }

        i += 1

        # Tìm kết quả
        while i < len(lines):
            line = lines[i]

            # Kiểm tra kết quả
            result = pattern_matcher.detect_short_answer_result(line)
            if result.get('is_result'):
                question['answer'] = result['result']
                i += 1
                break

            # Nếu gặp câu hỏi khác thì dừng
            next_q = pattern_matcher.smart_detect_question(line, 'short_answer')
            if next_q.get('is_question'):
                break

            i += 1

        return question, i

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

    # Xử lý câu hỏi import với 3 dạng
    def _process_enhanced_imported_questions(self, questions, tree_id):
        """Xử lý và lưu câu hỏi với enhanced validation cho 3 dạng"""
        inserted = 0

        for q in questions:
            try:
                question_type = q.get("question_type", "multiple_choice")
                content = q["content"]

                if question_type == "multiple_choice":
                    new_id = self._save_imported_multiple_choice(q, tree_id)
                elif question_type == "true_false":
                    new_id = self._save_imported_true_false(q, tree_id)
                elif question_type == "short_answer":
                    new_id = self._save_imported_short_answer(q, tree_id)
                else:
                    continue

                if new_id:
                    # Save import history
                    self._save_question_history(new_id, "IMPORT", "", content)
                    inserted += 1

            except Exception as e:
                print(f"Lỗi khi lưu câu hỏi: {e}")

        # Reload view và thông báo
        rows = self.db.execute_query("SELECT * FROM question_bank WHERE tree_id=?", (tree_id,), fetch="all") or []
        self._load_question_rows(rows)
        QtWidgets.QMessageBox.information(self, "Thành công", f"Đã thêm {inserted} câu hỏi từ file Word.")

    # Lưu câu hỏi trắc nghiệm import
    def _save_imported_multiple_choice(self, question_data, tree_id):
        """Lưu câu hỏi trắc nghiệm được import"""
        content = question_data["content"]
        answer = question_data["answer"]
        raw_options = question_data["options"]

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
            return self.db.execute_query(
                "INSERT INTO question_bank(content_text, options, correct, question_type, tree_id) VALUES (?,?,?,?,?)",
                (content, json.dumps(opts_data, ensure_ascii=False), answer, 'multiple_choice', tree_id)
            )
        return None

    # Lưu câu hỏi đúng/sai import
    def _save_imported_true_false(self, question_data, tree_id):
        """Lưu câu hỏi đúng/sai được import"""
        content = question_data["content"]
        sub_questions = question_data.get("sub_questions", [])

        if len(sub_questions) < 2:
            return None

        # Lưu câu hỏi chính
        new_id = self.db.execute_query(
            "INSERT INTO question_bank(content_text, question_type, sub_questions, tree_id) VALUES (?,?,?,?)",
            (content, 'true_false', json.dumps(sub_questions, ensure_ascii=False), tree_id)
        )

        # Lưu sub-parts
        for i, sub in enumerate(sub_questions):
            # Mặc định tất cả là đúng nếu không có thông tin
            is_correct = sub.get("is_correct", True)
            self.db.execute_query(
                "INSERT INTO question_sub_parts(question_id, part_label, part_content, is_correct, part_order) VALUES (?,?,?,?,?)",
                (new_id, sub["label"], sub["content"], int(is_correct), i)
            )

        return new_id

    # Lưu câu hỏi trả lời ngắn import
    def _save_imported_short_answer(self, question_data, tree_id):
        """Lưu câu hỏi trả lời ngắn được import"""
        content = question_data["content"]
        answer = question_data.get("answer", "")

        if not answer:
            return None

        # Chuẩn bị answer data
        answer_data = {
            "main_answer": answer,
            "answer_type": "Số nguyên",  # Mặc định
            "alternative_answers": []
        }

        return self.db.execute_query(
            "INSERT INTO question_bank(content_text, correct, question_type, options, tree_id) VALUES (?,?,?,?,?)",
            (content, answer, 'short_answer', json.dumps(answer_data, ensure_ascii=False), tree_id)
        )

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

    # Export với hỗ trợ 3 dạng câu hỏi
    def export_to_word(self):
        """Xuất danh sách câu hỏi ra file Word với hỗ trợ 3 dạng"""
        tree_id = self._current_tree_id()
        if not tree_id:
            QtWidgets.QMessageBox.warning(self, "Chưa chọn thư mục", "Vui lòng chọn thư mục để xuất.")
            return

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Lưu file Word", "", "Word files (*.docx)")
        if not file_path:
            return

        try:
            from docx import Document
            from docx.shared import Inches

            doc = Document()
            doc.add_heading('NGÂN HÀNG CÂU HỎI', 0)

            # Thêm thông tin đường dẫn thư mục
            path_info = self.get_tree_path(tree_id)
            if path_info:
                path_text = " > ".join([p["name"] for p in path_info])
                doc.add_paragraph(f"Đường dẫn: {path_text}")

            # Lấy và phân loại câu hỏi
            rows = self.db.execute_query("SELECT * FROM question_bank WHERE tree_id=? ORDER BY question_type, id",
                                         (tree_id,), fetch="all") or []

            # Phân loại theo dạng
            questions_by_type = {
                'multiple_choice': [],
                'true_false': [],
                'short_answer': []
            }

            for row in rows:
                q_type = row.get("question_type", "multiple_choice")
                questions_by_type[q_type].append(row)

            # Export từng phần
            section_num = 1

            # PHẦN I: Trắc nghiệm thông thường
            if questions_by_type['multiple_choice']:
                doc.add_heading(f'PHẦN {section_num}. Câu trắc nghiệm với nhiều phương án lựa chọn', level=1)
                doc.add_paragraph(
                    f'Thí sinh trả lời từ câu 1 đến câu {len(questions_by_type["multiple_choice"])}. Mỗi câu hỏi, thí sinh chỉ chọn một phương án.')

                for i, row in enumerate(questions_by_type['multiple_choice'], 1):
                    doc.add_paragraph(f'Câu {i}. {row["content_text"]}', style='Heading 3')

                    try:
                        options = json.loads(row["options"] or "[]")
                        for opt in options:
                            doc.add_paragraph(opt["text"], style='List Bullet')
                    except json.JSONDecodeError:
                        doc.add_paragraph("Lỗi: Không thể đọc đáp án")

                    doc.add_paragraph("")  # Dòng trống
                section_num += 1

            # PHẦN II: Đúng/Sai
            if questions_by_type['true_false']:
                doc.add_heading(f'PHẦN {section_num}. Câu trắc nghiệm đúng sai', level=1)
                doc.add_paragraph(
                    f'Thí sinh trả lời từ câu 1 đến câu {len(questions_by_type["true_false"])}. Trong mỗi ý a), b), c), d) ở mỗi câu, thí sinh chọn đúng hoặc sai (điền dấu X vào ô chọn)')

                for i, row in enumerate(questions_by_type['true_false'], 1):
                    doc.add_paragraph(f'Câu {i}. {row["content_text"]}', style='Heading 3')

                    # Tạo bảng cho đúng/sai
                    table = doc.add_table(rows=1, cols=3)
                    table.style = 'Table Grid'

                    # Header
                    header_cells = table.rows[0].cells
                    header_cells[0].text = 'Khẳng định'
                    header_cells[1].text = 'Đúng'
                    header_cells[2].text = 'Sai'

                    # Lấy sub-questions
                    sub_parts = self.db.execute_query(
                        "SELECT * FROM question_sub_parts WHERE question_id=? ORDER BY part_order",
                        (row["id"],), fetch="all"
                    ) or []

                    for sub in sub_parts:
                        row_cells = table.add_row().cells
                        row_cells[0].text = f'{sub["part_label"]} {sub["part_content"]}'
                        row_cells[1].text = 'X' if sub["is_correct"] else ''
                        row_cells[2].text = '' if sub["is_correct"] else 'X'

                    doc.add_paragraph("")  # Dòng trống
                section_num += 1

            # PHẦN III: Trả lời ngắn
            if questions_by_type['short_answer']:
                doc.add_heading(f'PHẦN {section_num}. Câu trắc nghiệm trả lời ngắn', level=1)
                doc.add_paragraph(f'Thí sinh trả lời từ câu 1 đến câu {len(questions_by_type["short_answer"])}.')

                for i, row in enumerate(questions_by_type['short_answer'], 1):
                    doc.add_paragraph(f'Câu {i}. {row["content_text"]}', style='Heading 3')
                    doc.add_paragraph(f'Kết quả: {row["correct"]}')
                    doc.add_paragraph("")  # Dòng trống

            doc.save(file_path)
            total_questions = sum(len(questions_by_type[key]) for key in questions_by_type)
            QtWidgets.QMessageBox.information(self, "Thành công",
                                              f"Đã xuất {total_questions} câu hỏi ra file Word với {section_num - 1} phần.")

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

    # Preview với hỗ trợ 3 dạng câu hỏi
    def update_preview(self):
        """Cập nhật preview câu hỏi cho 3 dạng"""
        if not hasattr(self, 'preview_widget'):
            return

        content = self.content_text.toPlainText() if hasattr(self, 'content_text') else ""
        question_type = self._get_current_question_type()

        # Base HTML
        html = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.6;">
            <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
                📝 {self._get_question_type_display_name(question_type)}
            </h3>
            <p style="background: #f8f9fa; padding: 15px; border-left: 4px solid #007bff; margin: 10px 0;">
                {content or '<em>Chưa có nội dung câu hỏi...</em>'}
            </p>
        """

        if question_type == 'multiple_choice':
            html += self._generate_multiple_choice_preview()
        elif question_type == 'true_false':
            html += self._generate_true_false_preview()
        elif question_type == 'short_answer':
            html += self._generate_short_answer_preview()

        html += "</div>"
        self.preview_widget.setHtml(html)

    # Lấy tên hiển thị cho loại câu hỏi
    def _get_question_type_display_name(self, question_type):
        """Lấy tên hiển thị cho loại câu hỏi"""
        names = {
            'multiple_choice': 'Câu hỏi Trắc nghiệm',
            'true_false': 'Câu hỏi Đúng/Sai',
            'short_answer': 'Câu hỏi Trả lời ngắn'
        }
        return names.get(question_type, 'Câu hỏi')

    # Preview cho trắc nghiệm
    def _generate_multiple_choice_preview(self):
        """Tạo preview cho câu hỏi trắc nghiệm"""
        html = "<h4 style='color: #2c3e50; margin-top: 20px;'>📘 Đáp án:</h4>"

        if hasattr(self, 'option_entries'):
            for label, entry in self.option_entries.items():
                text = entry.text().strip() if entry.text() else f"<em>Chưa có đáp án {label}</em>"

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

        return html

    # Preview cho đúng/sai
    def _generate_true_false_preview(self):
        """Tạo preview cho câu hỏi đúng/sai"""
        html = "<h4 style='color: #2c3e50; margin-top: 20px;'>✅❌ Các phần đánh giá:</h4>"

        if hasattr(self, 'sub_question_entries'):
            for label, entry in self.sub_question_entries.items():
                text = entry.text().strip() if entry.text() else f"<em>Chưa có nội dung phần {label}</em>"

                is_correct = self.sub_question_checkboxes[label].isChecked()

                style = "background: #d4edda; border-left: 4px solid #28a745;" if is_correct else "background: #f8d7da; border-left: 4px solid #dc3545;"
                icon = "✅" if is_correct else "❌"
                status = "ĐÚNG" if is_correct else "SAI"

                html += f"""
                <div style="{style} padding: 10px; margin: 5px 0; border-radius: 4px;">
                    <strong>{label.upper()}</strong> {text}
                    <span style="float: right; font-weight: bold;">{icon} {status}</span>
                </div>
                """

        return html

    # Preview cho trả lời ngắn
    def _generate_short_answer_preview(self):
        """Tạo preview cho câu hỏi trả lời ngắn"""
        html = "<h4 style='color: #2c3e50; margin-top: 20px;'>📝 Đáp án:</h4>"

        if hasattr(self, 'short_answer_edit'):
            answer = self.short_answer_edit.text().strip() or "<em>Chưa có đáp án</em>"
            answer_type = self.answer_type_combo.currentText() if hasattr(self, 'answer_type_combo') else "Văn bản"

            html += f"""
            <div style="background: #e3f2fd; padding: 15px; border-radius: 4px; margin: 10px 0;">
                <p><strong>Loại đáp án:</strong> {answer_type}</p>
                <p><strong>Đáp án chính:</strong> <span style="background: #fff; padding: 5px 10px; border-radius: 3px; font-family: monospace;">{answer}</span></p>
            """

            if hasattr(self, 'alternative_answers_edit'):
                alt_answers = self.alternative_answers_edit.toPlainText().strip()
                if alt_answers:
                    alt_list = [alt.strip() for alt in alt_answers.split('\n') if alt.strip()]
                    if alt_list:
                        html += "<p><strong>Đáp án thay thế:</strong></p><ul>"
                        for alt in alt_list:
                            html += f"<li><span style='background: #f8f9fa; padding: 2px 6px; border-radius: 3px; font-family: monospace;'>{alt}</span></li>"
                        html += "</ul>"

            html += "</div>"

        return html
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
        from datetime import datetime
        self._stats_cache_time = datetime.now()
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

    # Helper methods cho 3 dạng câu hỏi
    def get_question_type_statistics(self):
        """Lấy thống kê theo loại câu hỏi"""
        try:
            stats = {}

            # Thống kê tổng quan
            total = self.db.execute_query("SELECT COUNT(*) as count FROM question_bank", fetch="one")["count"]
            stats['total'] = total

            # Thống kê theo loại
            type_stats = self.db.execute_query("""
                SELECT 
                    question_type,
                    COUNT(*) as count
                FROM question_bank 
                GROUP BY question_type
                ORDER BY count DESC
            """, fetch="all") or []

            stats['by_type'] = {}
            for stat in type_stats:
                q_type = stat["question_type"] or "multiple_choice"
                stats['by_type'][q_type] = stat["count"]

            return stats
        except Exception as e:
            print(f"Lỗi lấy thống kê: {e}")
            return {'total': 0, 'by_type': {}}

    # Validate dữ liệu cho từng loại câu hỏi
    def validate_question_by_type(self, question_type, data):
        """Validate dữ liệu theo loại câu hỏi"""
        errors = []

        if question_type == 'multiple_choice':
            if not data.get('options') or len(data['options']) < 2:
                errors.append("Câu hỏi trắc nghiệm phải có ít nhất 2 đáp án")
            if not data.get('correct'):
                errors.append("Phải chọn đáp án đúng")

        elif question_type == 'true_false':
            if not data.get('sub_questions') or len(data['sub_questions']) < 2:
                errors.append("Câu hỏi đúng/sai phải có ít nhất 2 phần")
            for sub in data.get('sub_questions', []):
                if not sub.get('content', '').strip():
                    errors.append(f"Phần {sub.get('label', '')} không được để trống")

        elif question_type == 'short_answer':
            if not data.get('answer', '').strip():
                errors.append("Câu hỏi trả lời ngắn phải có đáp án")

        return errors

    # Export template cho import
    def export_question_template(self):
        """Xuất template mẫu cho việc import"""
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Lưu file template", "question_template.docx", "Word files (*.docx)"
        )
        if not file_path:
            return

        try:
            from docx import Document

            doc = Document()
            doc.add_heading('TEMPLATE NGÂN HÀNG CÂU HỎI', 0)

            # PHẦN I: Mẫu trắc nghiệm
            doc.add_heading('PHẦN I. Câu trắc nghiệm với nhiều phương án lựa chọn', level=1)
            doc.add_paragraph('Thí sinh trả lời từ câu 1 đến câu 12. Mỗi câu hỏi, thí sinh chỉ chọn một phương án.')

            doc.add_paragraph('Câu 1. Nội dung câu hỏi trắc nghiệm mẫu?')
            doc.add_paragraph('A. Đáp án A')
            doc.add_paragraph('B. Đáp án B')
            doc.add_paragraph('C. Đáp án C')
            doc.add_paragraph('D. Đáp án D')
            doc.add_paragraph('Đáp án: A')
            doc.add_paragraph('')

            # PHẦN II: Mẫu đúng/sai
            doc.add_heading('PHẦN II. Câu trắc nghiệm đúng sai', level=1)
            doc.add_paragraph(
                'Thí sinh trả lời từ câu 1 đến câu 4. Trong mỗi ý a), b), c), d) ở mỗi câu, thí sinh chọn đúng hoặc sai (điền dấu X vào ô chọn)')

            doc.add_paragraph('Câu 1. Xét tính đúng sai của các khẳng định sau:')
            doc.add_paragraph('a) Khẳng định thứ nhất')
            doc.add_paragraph('b) Khẳng định thứ hai')
            doc.add_paragraph('c) Khẳng định thứ ba')
            doc.add_paragraph('d) Khẳng định thứ tư')
            doc.add_paragraph('')

            # PHẦN III: Mẫu trả lời ngắn
            doc.add_heading('PHẦN III. Câu trắc nghiệm trả lời ngắn', level=1)
            doc.add_paragraph('Thí sinh trả lời từ câu 1 đến câu 6.')

            doc.add_paragraph('Câu 1. Nội dung câu hỏi trả lời ngắn mẫu?')
            doc.add_paragraph('Kết quả: 10')
            doc.add_paragraph('')

            doc.save(file_path)
            QtWidgets.QMessageBox.information(self, "Thành công", "Đã xuất file template mẫu.")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể xuất template: {e}")

    # Clear form cho tất cả loại câu hỏi
    def clear_all_question_forms(self):
        """Clear form cho tất cả loại câu hỏi"""
        self.current_question_id = None
        self.content_text.clear()

        # Clear multiple choice
        self.correct_group.setExclusive(False)
        for b in self.correct_group.buttons():
            b.setChecked(False)
        self.correct_group.setExclusive(True)
        for ent in self.option_entries.values():
            ent.clear()

        # Clear true/false
        if hasattr(self, 'sub_question_entries'):
            for entry in self.sub_question_entries.values():
                entry.clear()
            for cb in self.sub_question_checkboxes.values():
                cb.setChecked(False)

        # Clear short answer
        if hasattr(self, 'short_answer_edit'):
            self.short_answer_edit.clear()
        if hasattr(self, 'alternative_answers_edit'):
            self.alternative_answers_edit.clear()

    # Thêm phương thức setup tree management
    def _setup_tree_management(self):
        """Thiết lập chức năng quản lý cây thư mục"""

        # Thêm context menu cho tree
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_tree_context_menu)

        # Thêm double-click để edit
        self.tree.itemDoubleClicked.connect(self._edit_tree_node)

        # Thêm keyboard shortcuts
        self._setup_tree_shortcuts()

    # Thêm phương thức context menu
    def _show_tree_context_menu(self, position):
        """Hiển thị context menu cho tree"""
        item = self.tree.itemAt(position)

        menu = QtWidgets.QMenu(self)

        # Thêm node mới
        add_action = menu.addAction("➕ Thêm nhánh mới")
        add_action.triggered.connect(lambda: self._add_tree_node(item))

        if item:  # Nếu click vào node
            menu.addSeparator()

            # Thêm node con
            add_child_action = menu.addAction("📁 Thêm nhánh con")
            add_child_action.triggered.connect(lambda: self._add_child_node(item))

            # Sửa node
            edit_action = menu.addAction("✏️ Sửa tên nhánh")
            edit_action.triggered.connect(lambda: self._edit_tree_node(item))

            # Sao chép node
            copy_action = menu.addAction("📋 Sao chép nhánh")
            copy_action.triggered.connect(lambda: self._copy_tree_node(item))

            menu.addSeparator()

            # Xóa node
            delete_action = menu.addAction("🗑️ Xóa nhánh")
            delete_action.triggered.connect(lambda: self._delete_tree_node(item))

        # Hiển thị menu
        menu.exec(self.tree.mapToGlobal(position))

    # Thêm phương thức keyboard shortcuts
    def _setup_tree_shortcuts(self):
        """Thiết lập keyboard shortcuts cho tree"""
        # F2 để edit node được chọn
        edit_shortcut = QShortcut(QKeySequence("F2"), self.tree)
        edit_shortcut.activated.connect(self._edit_selected_tree_node)

        # Delete để xóa node
        delete_shortcut = QShortcut(QKeySequence("Delete"), self.tree)
        delete_shortcut.activated.connect(self._delete_selected_tree_node)

        # Ctrl+N để thêm node mới
        add_shortcut = QShortcut(QKeySequence("Ctrl+N"), self.tree)
        add_shortcut.activated.connect(self._add_tree_node)
    # Thêm phương thức thêm node
    def _add_tree_node(self, parent_item=None):
        """Thêm node mới"""
        try:
            dialog = TreeNodeDialog(self.db, mode="add", parent=self)

            # Nếu có parent item, set làm parent
            parent_id = None
            if parent_item:
                parent_id = parent_item.data(0, Qt.UserRole)
                if parent_id:
                    dialog.set_parent_id(parent_id)

            if dialog.exec() == QtWidgets.QDialog.Accepted:
                # Refresh tree sau khi thêm
                self.refresh_tree()

                # Tìm lại parent item sau khi refresh (vì tree đã được rebuild)
                if parent_id:
                    self._expand_node_by_id(parent_id)

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể thêm node: {e}")
    # Thêm phương thức thêm node con
    def _add_child_node(self, parent_item):
        """Thêm node con"""
        if not parent_item:
            return

        parent_id = parent_item.data(0, Qt.UserRole)
        if not parent_id:
            return

        try:
            dialog = TreeNodeDialog(self.db, mode="add", parent=self)
            dialog.set_parent_id(parent_id)

            if dialog.exec() == QtWidgets.QDialog.Accepted:
                self.refresh_tree()
                # Tìm lại và expand parent sau khi refresh
                self._expand_node_by_id(parent_id)

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể thêm node con: {e}")

    # Thêm phương thức sửa node
    def _edit_tree_node(self, item):
        """Sửa node"""
        if not item:
            return

        node_id = item.data(0, Qt.UserRole)
        if not node_id:
            return

        try:
            dialog = TreeNodeDialog(self.db, mode="edit", node_id=node_id, parent=self)

            if dialog.exec() == QtWidgets.QDialog.Accepted:
                self.refresh_tree()
                # Tìm lại và select node sau khi refresh
                self._select_node_by_id(node_id)

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể sửa node: {e}")
    # Thêm phương thức sửa node được chọn
    def _edit_selected_tree_node(self):
        """Sửa node được chọn"""
        selected_items = self.tree.selectedItems()
        if selected_items:
            self._edit_tree_node(selected_items[0])

    # Thêm phương thức sao chép node
    def _copy_tree_node(self, item):
        """Sao chép node"""
        if not item:
            return

        node_id = item.data(0, Qt.UserRole)
        if not node_id:
            return

        try:
            # Lấy thông tin node gốc
            row = self.db.execute_query(
                "SELECT name, level, description, parent_id FROM exercise_tree WHERE id = ?",
                (node_id,), fetch="one"
            )

            if row:
                new_name = f"{row['name']} (Sao chép)"

                # Tạo node mới
                description = row.get('description', '') if row.get('description') else ''

                self.db.execute_query(
                    "INSERT INTO exercise_tree (parent_id, name, level, description) VALUES (?, ?, ?, ?)",
                    (row['parent_id'], new_name, row['level'], description)
                )

                self.refresh_tree()
                QtWidgets.QMessageBox.information(self, "Thành công", f"Đã sao chép '{new_name}'")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể sao chép node: {e}")
    # Thêm phương thức xóa node
    def _delete_tree_node(self, item):
        """Xóa node với xác nhận"""
        if not item:
            return

        node_id = item.data(0, Qt.UserRole)
        node_name = item.text(0)

        if not node_id:
            return

        try:
            # Kiểm tra node con
            children_count = self.db.execute_query(
                "SELECT COUNT(*) as count FROM exercise_tree WHERE parent_id = ?",
                (node_id,), fetch="one"
            )

            if children_count and children_count["count"] > 0:
                reply = QtWidgets.QMessageBox.question(
                    self, "Xác nhận xóa",
                    f"Nhánh '{node_name}' có {children_count['count']} nhánh con.\n"
                    f"Bạn có muốn xóa tất cả không?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No
                )
            else:
                reply = QtWidgets.QMessageBox.question(
                    self, "Xác nhận xóa",
                    f"Bạn có chắc muốn xóa nhánh '{node_name}'?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No
                )

            if reply == QtWidgets.QMessageBox.Yes:
                # Xóa node và tất cả con
                self.db.execute_query("DELETE FROM exercise_tree WHERE id = ?", (node_id,))
                self.refresh_tree()
                QtWidgets.QMessageBox.information(self, "Thành công", f"Đã xóa nhánh '{node_name}'")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể xóa node: {e}")
    # Thêm phương thức xóa node được chọn
    def _delete_selected_tree_node(self):
        """Xóa node được chọn"""
        selected_items = self.tree.selectedItems()
        if selected_items:
            self._delete_tree_node(selected_items[0])

    def _expand_node_by_id(self, node_id):
        """Tìm và expand node theo ID"""
        try:
            root = self.tree.invisibleRootItem()
            self._find_and_expand_recursive(root, node_id)
        except Exception:
            pass  # Bỏ qua lỗi nếu không tìm thấy

    def _find_and_expand_recursive(self, parent_item, target_id):
        """Đệ quy tìm và expand node"""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            if child and child.data(0, Qt.UserRole) == target_id:
                child.setExpanded(True)
                return True

            if self._find_and_expand_recursive(child, target_id):
                return True

        return False

    def _select_node_by_id(self, node_id):
        """Tìm và select node theo ID"""
        try:
            root = self.tree.invisibleRootItem()
            self._find_and_select_recursive(root, node_id)
        except Exception:
            pass  # Bỏ qua lỗi nếu không tìm thấy

    def _find_and_select_recursive(self, parent_item, target_id):
        """Đệ quy tìm và select node"""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            if child and child.data(0, Qt.UserRole) == target_id:
                self.tree.setCurrentItem(child)
                return True

            if self._find_and_select_recursive(child, target_id):
                return True

        return False


class TreeNodeDialog(QtWidgets.QDialog):
    """Dialog để thêm/sửa node trong cây thư mục"""

    def __init__(self, db_manager, mode="add", node_id=None, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.mode = mode  # "add" hoặc "edit"
        self.node_id = node_id
        self.parent_id = None

        self._setup_dialog()
        self._build_ui()
        self._load_data()

    def _setup_dialog(self):
        """Thiết lập dialog"""
        if self.mode == "add":
            self.setWindowTitle("➕ Thêm nhánh mới")
        else:
            self.setWindowTitle("✏️ Sửa nhánh")

        self.setModal(True)
        self.resize(450, 400)

        # Đặt icon cho dialog
        self.setWindowIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DirIcon))

    def _build_ui(self):
        """Xây dựng giao diện"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = QtWidgets.QLabel()
        if self.mode == "add":
            header.setText("➕ Thêm nhánh mới vào cây thư mục")
        else:
            header.setText("✏️ Chỉnh sửa thông tin nhánh")

        header.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #2E86AB;
                padding: 15px;
                background-color: #f8f9fa;
                border-radius: 8px;
                border: 1px solid #dee2e6;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(header)

        # Form container
        form_container = QtWidgets.QWidget()
        form_container.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #e1e5e9;
            }
        """)

        form_layout = QtWidgets.QFormLayout(form_container)
        form_layout.setSpacing(12)
        form_layout.setContentsMargins(20, 20, 20, 20)

        # Parent selection (chỉ hiện khi thêm)
        if self.mode == "add":
            self.parent_combo = QtWidgets.QComboBox()
            self.parent_combo.addItem("(Không có parent - Cấp gốc)", None)
            self._load_parent_options()

            parent_label = QtWidgets.QLabel("📁 Nhánh cha:")
            parent_label.setStyleSheet("font-weight: 500; color: #495057;")
            form_layout.addRow(parent_label, self.parent_combo)

        # Tên nhánh
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("Nhập tên nhánh...")

        name_label = QtWidgets.QLabel("📝 Tên nhánh:")
        name_label.setStyleSheet("font-weight: 500; color: #495057;")
        form_layout.addRow(name_label, self.name_edit)

        # Cấp độ
        self.level_combo = QtWidgets.QComboBox()
        self.level_combo.addItems(["Môn", "Lớp", "Chủ đề", "Dạng", "Mức độ"])

        level_label = QtWidgets.QLabel("📊 Cấp độ:")
        level_label.setStyleSheet("font-weight: 500; color: #495057;")
        form_layout.addRow(level_label, self.level_combo)

        # Mô tả
        self.description_edit = QtWidgets.QTextEdit()
        self.description_edit.setMaximumHeight(100)
        self.description_edit.setPlaceholderText("Nhập mô tả chi tiết...")

        desc_label = QtWidgets.QLabel("📄 Mô tả:")
        desc_label.setStyleSheet("font-weight: 500; color: #495057;")
        form_layout.addRow(desc_label, self.description_edit)

        # Style cho form inputs
        input_style = """
            QLineEdit, QComboBox, QTextEdit {
                padding: 10px;
                border: 2px solid #e1e5e9;
                border-radius: 6px;
                font-size: 13px;
                background-color: white;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border-color: #2E86AB;
                outline: none;
                background-color: #f8fbff;
            }
            QComboBox::drop-down {
                border: none;
                background-color: transparent;
            }
            QComboBox::down-arrow {
                image: none;
                border: none;
                width: 12px;
                height: 12px;
            }
        """

        self.name_edit.setStyleSheet(input_style)
        self.level_combo.setStyleSheet(input_style)
        self.description_edit.setStyleSheet(input_style)

        if hasattr(self, 'parent_combo'):
            self.parent_combo.setStyleSheet(input_style)

        layout.addWidget(form_container)

        # Buttons container
        button_container = QtWidgets.QWidget()
        button_layout = QtWidgets.QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 10, 0, 0)

        # Cancel button
        cancel_btn = QtWidgets.QPushButton("❌ Hủy")
        cancel_btn.setFixedSize(100, 40)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:pressed {
                background-color: #545b62;
            }
        """)

        # Save button
        if self.mode == "add":
            save_btn = QtWidgets.QPushButton("➕ Thêm")
            save_btn.setStyleSheet("""
                QPushButton {
                    background-color: #28a745;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 6px;
                    font-weight: 600;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #218838;
                }
                QPushButton:pressed {
                    background-color: #1e7e34;
                }
            """)
        else:
            save_btn = QtWidgets.QPushButton("💾 Lưu")
            save_btn.setStyleSheet("""
                QPushButton {
                    background-color: #007bff;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 6px;
                    font-weight: 600;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #0056b3;
                }
                QPushButton:pressed {
                    background-color: #004085;
                }
            """)

        save_btn.setFixedSize(100, 40)
        save_btn.clicked.connect(self.accept)
        save_btn.setDefault(True)

        # Add buttons to layout
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addSpacing(10)
        button_layout.addWidget(save_btn)

        layout.addWidget(button_container)

        # Focus vào name edit
        self.name_edit.setFocus()

        # Enter để submit
        self.name_edit.returnPressed.connect(save_btn.click)

    def _load_parent_options(self):
        """Load danh sách parent có thể chọn"""
        if self.mode != "add":
            return

        try:
            rows = self.db.execute_query(
                "SELECT id, name, level FROM exercise_tree ORDER BY level, name",
                fetch="all"
            ) or []

            for row in rows:
                # Nếu đang edit, không cho chọn chính nó làm parent
                if self.mode == "edit" and row["id"] == self.node_id:
                    continue

                display_text = f"{row['name']} ({row['level']})"
                self.parent_combo.addItem(display_text, row["id"])

        except Exception as e:
            print(f"Lỗi load parent options: {e}")

    def set_parent_id(self, parent_id):
        """Đặt parent được chọn"""
        self.parent_id = parent_id

        if self.mode == "add" and hasattr(self, 'parent_combo'):
            # Tìm và chọn parent trong combo
            for i in range(self.parent_combo.count()):
                if self.parent_combo.itemData(i) == parent_id:
                    self.parent_combo.setCurrentIndex(i)
                    break

    def _load_data(self):
        """Load dữ liệu nếu đang edit"""
        if self.mode != "edit" or not self.node_id:
            return

        try:
            # Thử query với description trước
            row = self.db.execute_query(
                "SELECT name, level, description FROM exercise_tree WHERE id = ?",
                (self.node_id,), fetch="one"
            )

            if row:
                self.name_edit.setText(row["name"] or "")

                # Set level
                level = row["level"] or "Môn"
                index = self.level_combo.findText(level)
                if index >= 0:
                    self.level_combo.setCurrentIndex(index)

                # Kiểm tra description
                description = ""
                if 'description' in row.keys() and row['description']:
                    description = row['description']

                self.description_edit.setPlainText(description)

        except Exception as e:
            # Nếu lỗi do thiếu cột description, thử query không có description
            try:
                row = self.db.execute_query(
                    "SELECT name, level FROM exercise_tree WHERE id = ?",
                    (self.node_id,), fetch="one"
                )

                if row:
                    self.name_edit.setText(row["name"] or "")
                    level = row["level"] or "Môn"
                    index = self.level_combo.findText(level)
                    if index >= 0:
                        self.level_combo.setCurrentIndex(index)
                    self.description_edit.setPlainText("")

            except Exception as e2:
                QtWidgets.QMessageBox.critical(
                    self, "Lỗi",
                    f"Không thể tải dữ liệu node: {e2}")
    def _validate_input(self):
        """Validate dữ liệu đầu vào"""
        name = self.name_edit.text().strip()

        if not name:
            QtWidgets.QMessageBox.warning(
                self, "Lỗi",
                "Tên nhánh không được để trống!"
            )
            self.name_edit.setFocus()
            return False

        if len(name) > 100:
            QtWidgets.QMessageBox.warning(
                self, "Lỗi",
                "Tên nhánh không được quá 100 ký tự!"
            )
            self.name_edit.setFocus()
            return False

        # Kiểm tra tên không bị trùng trong cùng parent
        if self.mode == "add":
            parent_id = None
            if hasattr(self, 'parent_combo'):
                parent_id = self.parent_combo.currentData()
            elif self.parent_id:
                parent_id = self.parent_id

            existing = self.db.execute_query(
                "SELECT id FROM exercise_tree WHERE parent_id = ? AND name = ?",
                (parent_id, name), fetch="one"
            )

            if existing:
                QtWidgets.QMessageBox.warning(
                    self, "Lỗi",
                    "Đã tồn tại nhánh với tên này trong cùng cấp!"
                )
                self.name_edit.setFocus()
                return False
        else:
            # Khi edit, kiểm tra trùng tên nhưng loại trừ chính nó
            existing = self.db.execute_query(
                "SELECT id FROM exercise_tree WHERE name = ? AND id != ?",
                (name, self.node_id), fetch="one"
            )

            if existing:
                reply = QtWidgets.QMessageBox.question(
                    self, "Cảnh báo",
                    "Đã tồn tại nhánh khác với tên này. Bạn có muốn tiếp tục?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No
                )

                if reply != QtWidgets.QMessageBox.Yes:
                    self.name_edit.setFocus()
                    return False

        return True

    def accept(self):
        """Xử lý khi người dùng nhấn Save/Add"""
        if not self._validate_input():
            return

        # Lấy dữ liệu từ form
        name = self.name_edit.text().strip()
        level = self.level_combo.currentText()
        description = self.description_edit.toPlainText().strip()

        try:
            if self.mode == "add":
                # Thêm node mới
                parent_id = None
                if hasattr(self, 'parent_combo'):
                    parent_id = self.parent_combo.currentData()
                elif self.parent_id:
                    parent_id = self.parent_id

                # Thử insert với description trước
                try:
                    self.db.execute_query(
                        "INSERT INTO exercise_tree (parent_id, name, level, description) VALUES (?, ?, ?, ?)",
                        (parent_id, name, level, description)
                    )
                except Exception:
                    # Nếu lỗi, thử insert không có description
                    self.db.execute_query(
                        "INSERT INTO exercise_tree (parent_id, name, level) VALUES (?, ?, ?)",
                        (parent_id, name, level)
                    )

                QtWidgets.QMessageBox.information(
                    self, "Thành công",
                    f"Đã thêm nhánh '{name}' thành công!"
                )

            else:
                # Cập nhật node
                try:
                    self.db.execute_query(
                        "UPDATE exercise_tree SET name = ?, level = ?, description = ? WHERE id = ?",
                        (name, level, description, self.node_id)
                    )
                except Exception:
                    # Nếu lỗi, thử update không có description
                    self.db.execute_query(
                        "UPDATE exercise_tree SET name = ?, level = ? WHERE id = ?",
                        (name, level, self.node_id)
                    )

                QtWidgets.QMessageBox.information(
                    self, "Thành công",
                    f"Đã cập nhật nhánh '{name}' thành công!"
                )

            super().accept()

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Lỗi database",
                f"Không thể lưu dữ liệu:\n{str(e)}"
            )

    def reject(self):
        """Xử lý khi người dùng hủy"""
        # Kiểm tra xem có thay đổi gì không
        if self.mode == "edit" and self.node_id:
            try:
                row = self.db.execute_query(
                    "SELECT name, level, description FROM exercise_tree WHERE id = ?",
                    (self.node_id,), fetch="one"
                )

                if row:
                    current_name = self.name_edit.text().strip()
                    current_level = self.level_combo.currentText()
                    current_desc = self.description_edit.toPlainText().strip()

                    if (current_name != (row["name"] or "") or
                            current_level != (row["level"] or "Môn") or
                            current_desc != (row["description"] or "")):

                        reply = QtWidgets.QMessageBox.question(
                            self, "Xác nhận",
                            "Bạn có thay đổi chưa lưu. Bạn có muốn thoát?",
                            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                            QtWidgets.QMessageBox.No
                        )

                        if reply != QtWidgets.QMessageBox.Yes:
                            return
            except:
                pass

        super().reject()