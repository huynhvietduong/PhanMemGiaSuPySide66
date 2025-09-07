"""
Question Edit Dialog - Dialog thêm/sửa câu hỏi
File: ui_qt/windows/question_bank/views/dialogs/question_edit_dialog.py
"""

import os
import re
from typing import Optional, Dict, Any, List
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal, QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QPixmap, QKeySequence
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QGroupBox, QSplitter, QWidget,
    QToolBar, QStackedWidget, QTextEdit, QComboBox,
    QLineEdit, QCheckBox, QMessageBox, QFileDialog,
    QApplication, QTabWidget
)

# Import widgets and dialogs
try:
    from ..widgets.image_viewer_widget import ImageViewerWidget
    from ..widgets.pdf_viewer_widget import PDFViewerWidget
    from .latex_input_dialog import LaTeXInputDialog
except ImportError:
    # Fallback widgets
    class ImageViewerWidget(QLabel):
        def __init__(self, parent=None, mode="adaptive"):
            super().__init__(parent)
            self.setAlignment(Qt.AlignCenter)
            self.setText("🖼️ Image Viewer")
            self.current_pixmap = None

        def set_pixmap(self, pixmap):
            self.current_pixmap = pixmap
            self.setPixmap(pixmap.scaled(400, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        def set_image_from_data(self, data):
            pixmap = QPixmap()
            if pixmap.loadFromData(data):
                self.set_pixmap(pixmap)

        def clear_image(self):
            self.clear()
            self.current_pixmap = None
            self.setText("🖼️ Không có ảnh")


    class PDFViewerWidget(QLabel):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setAlignment(Qt.AlignCenter)
            self.setText("📄 PDF Viewer")


    class LaTeXInputDialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.latex_code = ""

        def get_latex(self):
            return self.latex_code

        def exec(self):
            from PySide6.QtWidgets import QInputDialog
            text, ok = QInputDialog.getText(self.parent(), "LaTeX Input", "Nhập mã LaTeX:")
            if ok:
                self.latex_code = text
                return QDialog.Accepted
            return QDialog.Rejected


class QuestionEditDialog(QDialog):
    """Dialog thêm/sửa câu hỏi với giao diện đầy đủ"""

    # Signals
    question_saved = Signal(int)  # Phát tín hiệu khi lưu thành công

    def __init__(self, db_manager, tree_id=None, question_id=None, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.tree_id = tree_id
        self.question_id = question_id

        # Question data
        self.content_type = "text"
        self.answer_type = "text"
        self.content_data = None
        self.answer_data = None
        self.is_editing = question_id is not None

        self._setup_window()
        self._setup_ui()
        self._setup_connections()

        # Load data if editing
        if self.question_id:
            self._load_question_data()

    def _setup_window(self):
        """Thiết lập cửa sổ"""
        title = "✏️ Chỉnh sửa câu hỏi" if self.is_editing else "➕ Thêm câu hỏi mới"
        self.setWindowTitle(title)
        self.setModal(False)
        self.resize(1200, 800)
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint
        )

    def _setup_ui(self):
        """Thiết lập giao diện"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header với thông tin cơ bản
        self._create_header(layout)

        # Main content với tabs
        self._create_tabs(layout)

        # Bottom buttons
        self._create_bottom_buttons(layout)

    def _create_header(self, layout: QVBoxLayout):
        """Tạo header với thông tin cơ bản"""
        header_group = QGroupBox("ℹ️ Thông tin câu hỏi")
        header_layout = QFormLayout(header_group)

        # Question ID (nếu đang edit)
        if self.is_editing:
            self.id_label = QLabel(str(self.question_id))
            self.id_label.setStyleSheet("font-weight: bold; color: #007bff;")
            header_layout.addRow("🆔 ID:", self.id_label)

        # Tree path
        self.tree_path_label = QLabel(self._get_tree_path())
        header_layout.addRow("🗂️ Vị trí:", self.tree_path_label)

        # Difficulty
        self.difficulty_combo = QComboBox()
        self.difficulty_combo.addItems(["Dễ", "Trung bình", "Khó"])
        header_layout.addRow("🎯 Độ khó:", self.difficulty_combo)

        # Topic (optional)
        self.topic_edit = QLineEdit()
        self.topic_edit.setPlaceholderText("Chủ đề câu hỏi (tùy chọn)")
        header_layout.addRow("📚 Chủ đề:", self.topic_edit)

        layout.addWidget(header_group)

    def _create_tabs(self, layout: QVBoxLayout):
        """Tạo tabs chính"""
        self.tab_widget = QTabWidget()

        # Tab 1: Question Content
        self._create_question_tab()

        # Tab 2: Answer
        self._create_answer_tab()

        # Tab 3: Settings & Tags
        self._create_settings_tab()

        layout.addWidget(self.tab_widget)

    def _create_question_tab(self):
        """Tab nội dung câu hỏi"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Toolbar cho question content
        toolbar = self._create_question_toolbar()
        layout.addWidget(toolbar)

        # Content area
        content_group = QGroupBox("📝 Nội dung câu hỏi")
        content_layout = QVBoxLayout(content_group)

        # Stacked widget cho các loại content
        self.content_widget = QStackedWidget()

        # Text editor
        self.text_editor = QTextEdit()
        self.text_editor.setPlaceholderText("Nhập nội dung câu hỏi hoặc dán ảnh (Ctrl+V)...")
        self.text_editor.setAcceptRichText(True)
        self.text_editor.installEventFilter(self)
        self.content_widget.addWidget(self.text_editor)

        # Image viewer
        self.image_viewer = ImageViewerWidget(mode="full")
        self.content_widget.addWidget(self.image_viewer)

        # PDF viewer
        self.pdf_viewer = PDFViewerWidget()
        self.content_widget.addWidget(self.pdf_viewer)

        content_layout.addWidget(self.content_widget)
        layout.addWidget(content_group)

        self.tab_widget.addTab(tab, "📝 Câu hỏi")

    def _create_question_toolbar(self) -> QToolBar:
        """Tạo toolbar cho question content"""
        toolbar = QToolBar()
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        toolbar.addWidget(QLabel("📝 Thêm câu hỏi:"))

        # Content type actions
        text_action = toolbar.addAction("📝 Văn bản")
        text_action.triggered.connect(lambda: self._add_content("text"))

        image_action = toolbar.addAction("🖼️ Ảnh")
        image_action.triggered.connect(lambda: self._add_content("image"))

        pdf_action = toolbar.addAction("📄 PDF")
        pdf_action.triggered.connect(lambda: self._add_content("pdf"))

        toolbar.addSeparator()

        # Special tools
        latex_action = toolbar.addAction("∑ LaTeX")
        latex_action.triggered.connect(self._insert_latex)

        paste_action = toolbar.addAction("📋 Dán ảnh")
        paste_action.triggered.connect(self._paste_from_clipboard)

        return toolbar

    def _create_answer_tab(self):
        """Tab đáp án"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Answer enabled checkbox
        self.answer_enabled = QCheckBox("✅ Có đáp án")
        self.answer_enabled.setChecked(True)
        self.answer_enabled.toggled.connect(self._toggle_answer_section)
        layout.addWidget(self.answer_enabled)

        # Answer section
        self.answer_section = QWidget()
        answer_section_layout = QVBoxLayout(self.answer_section)

        # Toolbar cho answer
        answer_toolbar = self._create_answer_toolbar()
        answer_section_layout.addWidget(answer_toolbar)

        # Answer content area
        answer_group = QGroupBox("✅ Nội dung đáp án")
        answer_layout = QVBoxLayout(answer_group)

        # Stacked widget cho answer
        self.answer_widget = QStackedWidget()

        # Answer text editor
        self.answer_text_editor = QTextEdit()
        self.answer_text_editor.setPlaceholderText("Nhập đáp án hoặc dán ảnh (Ctrl+V)...")
        self.answer_text_editor.setAcceptRichText(True)
        self.answer_text_editor.installEventFilter(self)
        self.answer_widget.addWidget(self.answer_text_editor)

        # Answer image viewer
        self.answer_image_viewer = ImageViewerWidget(mode="full")
        self.answer_widget.addWidget(self.answer_image_viewer)

        # Answer PDF viewer
        self.answer_pdf_viewer = PDFViewerWidget()
        self.answer_widget.addWidget(self.answer_pdf_viewer)

        answer_layout.addWidget(self.answer_widget)
        answer_section_layout.addWidget(answer_group)

        layout.addWidget(self.answer_section)

        self.tab_widget.addTab(tab, "✅ Đáp án")

    def _create_answer_toolbar(self) -> QToolBar:
        """Tạo toolbar cho answer"""
        toolbar = QToolBar()
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        toolbar.addWidget(QLabel("📝 Thêm đáp án:"))

        # Answer type actions
        ans_text_action = toolbar.addAction("📝 Văn bản")
        ans_text_action.triggered.connect(lambda: self._add_answer("text"))

        ans_image_action = toolbar.addAction("🖼️ Ảnh")
        ans_image_action.triggered.connect(lambda: self._add_answer("image"))

        ans_pdf_action = toolbar.addAction("📄 PDF")
        ans_pdf_action.triggered.connect(lambda: self._add_answer("pdf"))

        toolbar.addSeparator()

        # Answer tools
        ans_latex_action = toolbar.addAction("∑ LaTeX")
        ans_latex_action.triggered.connect(self._insert_answer_latex)

        ans_paste_action = toolbar.addAction("📋 Dán ảnh")
        ans_paste_action.triggered.connect(self._paste_answer_from_clipboard)

        return toolbar

    def _create_settings_tab(self):
        """Tab cài đặt và tags"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Tags section
        tags_group = QGroupBox("🏷️ Tags")
        tags_layout = QVBoxLayout(tags_group)

        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("Nhập tags cách nhau bằng dấu phẩy (vd: toán học, đại số, khó)")
        tags_layout.addWidget(self.tags_edit)

        # Common tags buttons
        common_tags_layout = QHBoxLayout()
        common_tags = ["Toán học", "Vật lý", "Hóa học", "Sinh học", "Dễ", "Trung bình", "Khó"]

        for tag in common_tags:
            btn = QPushButton(f"#{tag}")
            btn.setMaximumWidth(100)
            btn.clicked.connect(lambda checked, t=tag: self._add_tag(t))
            common_tags_layout.addWidget(btn)

        common_tags_layout.addStretch()
        tags_layout.addLayout(common_tags_layout)
        layout.addWidget(tags_group)

        # Additional settings
        settings_group = QGroupBox("⚙️ Cài đặt khác")
        settings_layout = QFormLayout(settings_group)

        # Usage tracking
        self.track_usage = QCheckBox("Theo dõi số lần sử dụng")
        self.track_usage.setChecked(True)
        settings_layout.addRow("📊 Thống kê:", self.track_usage)

        # Public/Private
        self.is_public = QCheckBox("Công khai (chia sẻ với người khác)")
        settings_layout.addRow("🌐 Trạng thái:", self.is_public)

        layout.addWidget(settings_group)
        layout.addStretch()

        self.tab_widget.addTab(tab, "⚙️ Cài đặt")

    def _create_bottom_buttons(self, layout: QVBoxLayout):
        """Tạo nút ở dưới"""
        button_layout = QHBoxLayout()

        # Preview button
        preview_btn = QPushButton("👁️ Xem trước")
        preview_btn.clicked.connect(self._preview_question)
        button_layout.addWidget(preview_btn)

        # Validate button
        validate_btn = QPushButton("✅ Kiểm tra")
        validate_btn.clicked.connect(self._validate_question)
        button_layout.addWidget(validate_btn)

        button_layout.addStretch()

        # Cancel & Save buttons
        cancel_btn = QPushButton("❌ Hủy")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.save_btn = QPushButton("💾 Lưu")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._save_question)
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
        # Keyboard shortcuts
        QtGui.QShortcut(QKeySequence("Ctrl+S"), self, self._save_question)
        QtGui.QShortcut(QKeySequence("Ctrl+P"), self, self._preview_question)
        QtGui.QShortcut(QKeySequence("F5"), self, self._validate_question)
        QtGui.QShortcut(QKeySequence("Escape"), self, self.reject)

    # ========== HELPER METHODS ==========

    def _get_tree_path(self) -> str:
        """Lấy đường dẫn cây"""
        if not self.tree_id:
            return "Chưa chọn vị trí"

        try:
            path_parts = []
            current_id = self.tree_id

            while current_id:
                node = self.db.execute_query(
                    "SELECT id, parent_id, name FROM exercise_tree WHERE id=?",
                    (current_id,), fetch="one"
                )
                if not node:
                    break

                path_parts.insert(0, node['name'])
                current_id = node['parent_id']

            return ' > '.join(path_parts) if path_parts else 'Không xác định'

        except Exception:
            return 'Lỗi đường dẫn'

    def _add_tag(self, tag: str):
        """Thêm tag vào input"""
        current_tags = self.tags_edit.text()
        if current_tags:
            if tag not in current_tags:
                self.tags_edit.setText(f"{current_tags}, {tag}")
        else:
            self.tags_edit.setText(tag)

    def _toggle_answer_section(self, enabled: bool):
        """Ẩn/hiện phần đáp án"""
        self.answer_section.setVisible(enabled)

    # ========== CONTENT MANAGEMENT ==========

    def _add_content(self, content_type: str):
        """Thêm nội dung câu hỏi"""
        self.content_type = content_type

        if content_type == "text":
            self.content_widget.setCurrentWidget(self.text_editor)
            self.text_editor.setFocus()
        elif content_type == "image":
            self._select_image_file(is_answer=False)
        elif content_type == "pdf":
            self._select_pdf_file(is_answer=False)

    def _add_answer(self, answer_type: str):
        """Thêm đáp án"""
        self.answer_type = answer_type

        if answer_type == "text":
            self.answer_widget.setCurrentWidget(self.answer_text_editor)
            self.answer_text_editor.setFocus()
        elif answer_type == "image":
            self._select_image_file(is_answer=True)
        elif answer_type == "pdf":
            self._select_pdf_file(is_answer=True)

    def _select_image_file(self, is_answer: bool = False):
        """Chọn file ảnh"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn ảnh", "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;All Files (*)"
        )

        if file_path:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                if is_answer:
                    self.answer_image_viewer.set_pixmap(pixmap)
                    self.answer_widget.setCurrentWidget(self.answer_image_viewer)
                    # Convert to bytes
                    ba = QByteArray()
                    buffer = QBuffer(ba)
                    buffer.open(QIODevice.WriteOnly)
                    pixmap.save(buffer, "PNG")
                    self.answer_data = bytes(ba)
                else:
                    self.image_viewer.set_pixmap(pixmap)
                    self.content_widget.setCurrentWidget(self.image_viewer)
                    # Convert to bytes
                    ba = QByteArray()
                    buffer = QBuffer(ba)
                    buffer.open(QIODevice.WriteOnly)
                    pixmap.save(buffer, "PNG")
                    self.content_data = bytes(ba)

    def _select_pdf_file(self, is_answer: bool = False):
        """Chọn file PDF"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn PDF", "",
            "PDF files (*.pdf);;All Files (*)"
        )

        if file_path:
            try:
                with open(file_path, 'rb') as f:
                    pdf_data = f.read()

                if is_answer:
                    self.answer_data = pdf_data
                    self.answer_widget.setCurrentWidget(self.answer_pdf_viewer)
                else:
                    self.content_data = pdf_data
                    self.content_widget.setCurrentWidget(self.pdf_viewer)

            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể đọc file PDF: {e}")

    # ========== LATEX SUPPORT ==========

    def _insert_latex(self):
        """Chèn LaTeX vào câu hỏi"""
        dialog = LaTeXInputDialog(self)
        if dialog.exec() == QDialog.Accepted:
            latex_code = dialog.get_latex()
            if self.content_type == "text":
                cursor = self.text_editor.textCursor()
                cursor.insertText(f"$${latex_code}$$")

    def _insert_answer_latex(self):
        """Chèn LaTeX vào đáp án"""
        dialog = LaTeXInputDialog(self)
        if dialog.exec() == QDialog.Accepted:
            latex_code = dialog.get_latex()
            if self.answer_type == "text":
                cursor = self.answer_text_editor.textCursor()
                cursor.insertText(f"$${latex_code}$$")

    # ========== CLIPBOARD SUPPORT ==========

    def eventFilter(self, obj, event):
        """Xử lý paste ảnh từ clipboard"""
        if event.type() == QtCore.QEvent.KeyPress:
            if event.matches(QKeySequence.Paste):
                if obj == self.text_editor:
                    self._paste_from_clipboard()
                    return True
                elif obj == self.answer_text_editor:
                    self._paste_answer_from_clipboard()
                    return True

        return super().eventFilter(obj, event)

    def _paste_from_clipboard(self):
        """Dán ảnh từ clipboard vào câu hỏi"""
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()

        if mime_data.hasImage():
            image = clipboard.image()
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                self.content_type = "image"
                self.image_viewer.set_pixmap(pixmap)
                self.content_widget.setCurrentWidget(self.image_viewer)

                # Convert to bytes
                ba = QByteArray()
                buffer = QBuffer(ba)
                buffer.open(QIODevice.WriteOnly)
                pixmap.save(buffer, "PNG")
                self.content_data = bytes(ba)

                QMessageBox.information(self, "Thành công", "Đã dán ảnh vào câu hỏi")
                return

        # Fallback to text paste
        if mime_data.hasText():
            self.text_editor.insertPlainText(clipboard.text())

    def _paste_answer_from_clipboard(self):
        """Dán ảnh từ clipboard vào đáp án"""
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()

        if mime_data.hasImage():
            image = clipboard.image()
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                self.answer_type = "image"
                self.answer_image_viewer.set_pixmap(pixmap)
                self.answer_widget.setCurrentWidget(self.answer_image_viewer)

                # Convert to bytes
                ba = QByteArray()
                buffer = QBuffer(ba)
                buffer.open(QIODevice.WriteOnly)
                pixmap.save(buffer, "PNG")
                self.answer_data = bytes(ba)

                QMessageBox.information(self, "Thành công", "Đã dán ảnh vào đáp án")
                return

        # Fallback to text paste
        if mime_data.hasText():
            self.answer_text_editor.insertPlainText(clipboard.text())

    # ========== DATA LOADING ==========

    def _load_question_data(self):
        """Load dữ liệu câu hỏi (nếu đang edit)"""
        if not self.question_id:
            return

        try:
            question = self.db.execute_query(
                "SELECT * FROM question_bank WHERE id=?",
                (self.question_id,), fetch="one"
            )

            if not question:
                QMessageBox.warning(self, "Lỗi", "Không tìm thấy câu hỏi!")
                self.reject()
                return

            # Convert to dict
            if hasattr(question, 'keys'):
                q_dict = dict(question)
            else:
                q_dict = question

            # Load basic info
            self.difficulty_combo.setCurrentText(q_dict.get('difficulty_level', 'Dễ'))
            self.topic_edit.setText(q_dict.get('topic', ''))

            # Load content
            content_type = q_dict.get('content_type', 'text')
            content_text = q_dict.get('content_text', '')
            content_data = q_dict.get('content_data')

            self.content_type = content_type

            if content_type == 'text':
                self.text_editor.setHtml(content_text) if self._has_html_tags(
                    content_text) else self.text_editor.setPlainText(content_text)
                self.content_widget.setCurrentWidget(self.text_editor)
            elif content_type == 'image' and content_data:
                self.image_viewer.set_image_from_data(content_data)
                self.content_widget.setCurrentWidget(self.image_viewer)
                self.content_data = content_data

            # Load answer
            answer_type = q_dict.get('answer_type', 'text')
            answer_text = q_dict.get('answer_text', '') or q_dict.get('correct', '')
            answer_data = q_dict.get('answer_data')

            self.answer_type = answer_type

            if answer_text or answer_data:
                self.answer_enabled.setChecked(True)

                if answer_type == 'text':
                    self.answer_text_editor.setHtml(answer_text) if self._has_html_tags(
                        answer_text) else self.answer_text_editor.setPlainText(answer_text)
                    self.answer_widget.setCurrentWidget(self.answer_text_editor)
                elif answer_type == 'image' and answer_data:
                    self.answer_image_viewer.set_image_from_data(answer_data)
                    self.answer_widget.setCurrentWidget(self.answer_image_viewer)
                    self.answer_data = answer_data
            else:
                self.answer_enabled.setChecked(False)

            # Load tags
            tags = self.db.execute_query(
                "SELECT tag_name FROM question_tags WHERE question_id=?",
                (self.question_id,), fetch="all"
            ) or []

            if tags:
                tag_names = [tag['tag_name'] for tag in tags]
                self.tags_edit.setText(', '.join(tag_names))

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể load câu hỏi: {e}")
            self.reject()

    def _has_html_tags(self, text: str) -> bool:
        """Kiểm tra text có HTML tags không"""
        return bool(re.search(r'<[^>]+>', text))

    # ========== VALIDATION & PREVIEW ==========

    def _validate_question(self):
        """Kiểm tra tính hợp lệ của câu hỏi"""
        errors = []

        # Check tree_id
        if not self.tree_id:
            errors.append("⚠️ Chưa chọn vị trí lưu")

        # Check content
        if self.content_type == "text":
            content = self.text_editor.toPlainText().strip()
            if not content:
                errors.append("⚠️ Nội dung câu hỏi trống")
        elif self.content_type in ["image", "pdf"]:
            if not self.content_data:
                errors.append("⚠️ Chưa có file đính kèm")

        # Check answer if enabled
        if self.answer_enabled.isChecked():
            if self.answer_type == "text":
                answer = self.answer_text_editor.toPlainText().strip()
                if not answer:
                    errors.append("⚠️ Đáp án trống")
            elif self.answer_type in ["image", "pdf"]:
                if not self.answer_data:
                    errors.append("⚠️ Chưa có file đáp án")

        # Show results
        if errors:
            QMessageBox.warning(self, "Lỗi validation", "\n".join(errors))
        else:
            QMessageBox.information(self, "✅ Hợp lệ", "Câu hỏi hợp lệ và sẵn sàng lưu!")

    def _preview_question(self):
        """Xem trước câu hỏi"""
        # TODO: Implement preview dialog
        QMessageBox.information(self, "Preview", "Chức năng preview đang phát triển")

    # ========== SAVE LOGIC ==========

    def _save_question(self):
        """Lưu câu hỏi"""
        try:
            # Validate required fields
            if not self.tree_id:
                QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng chọn vị trí lưu trong cây.")
                return

            # Prepare content data
            content_text = None
            content_data = None

            if self.content_type == "text":
                content_text = self.text_editor.toPlainText().strip()
                if not content_text:
                    QMessageBox.warning(self, "Thiếu nội dung", "Nội dung câu hỏi không được để trống.")
                    return
            elif self.content_type in ["image", "pdf"]:
                content_data = self.content_data
                if not content_data:
                    QMessageBox.warning(self, "Thiếu file", "Vui lòng chọn file cho câu hỏi.")
                    return

            # Prepare answer data
            answer_text = None
            answer_data = None

            if self.answer_enabled.isChecked():
                if self.answer_type == "text":
                    answer_text = self.answer_text_editor.toPlainText().strip()
                elif self.answer_type in ["image", "pdf"]:
                    answer_data = self.answer_data

            # Additional fields
            difficulty = self.difficulty_combo.currentText()
            topic = self.topic_edit.text().strip()

            # Save to database
            if self.is_editing:
                # Update existing question
                result = self.db.execute_query(
                    """UPDATE question_bank SET
                       content_text=?, content_type=?, content_data=?,
                       answer_text=?, answer_type=?, answer_data=?,
                       difficulty_level=?, topic=?, modified_date=CURRENT_TIMESTAMP
                       WHERE id=?""",
                    (content_text, self.content_type, content_data,
                     answer_text, self.answer_type, answer_data,
                     difficulty, topic, self.question_id)
                )

                if not result:
                    QMessageBox.critical(self, "Lỗi", "Không thể cập nhật câu hỏi.")
                    return

                saved_id = self.question_id

            else:
                # Insert new question
                saved_id = self.db.execute_query(
                    """INSERT INTO question_bank
                       (content_text, content_type, content_data,
                        answer_text, answer_type, answer_data,
                        tree_id, difficulty_level, topic, created_date)
                       VALUES (?,?,?,?,?,?,?,?,?, CURRENT_TIMESTAMP)""",
                    (content_text, self.content_type, content_data,
                     answer_text, self.answer_type, answer_data,
                     self.tree_id, difficulty, topic)
                )

                if not saved_id:
                    QMessageBox.critical(self, "Lỗi", "Không thể tạo câu hỏi mới.")
                    return

            # Save tags
            self._save_tags(saved_id)

            # Emit signal
            self.question_saved.emit(saved_id)

            QMessageBox.information(self, "Thành công", "Đã lưu câu hỏi.")
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu câu hỏi: {e}")

    def _save_tags(self, question_id: int):
        """Lưu tags cho câu hỏi"""
        try:
            # Delete old tags
            self.db.execute_query(
                "DELETE FROM question_tags WHERE question_id=?",
                (question_id,)
            )

            # Add new tags
            tags_text = self.tags_edit.text().strip()
            if tags_text:
                tag_names = [tag.strip() for tag in tags_text.split(',') if tag.strip()]

                for tag_name in tag_names:
                    self.db.execute_query(
                        "INSERT INTO question_tags(question_id, tag_name) VALUES (?,?)",
                        (question_id, tag_name)
                    )

        except Exception as e:
            print(f"Lỗi lưu tags: {e}")


# ========== TEST FUNCTION ==========

def test_question_edit_dialog():
    """Test function"""
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Mock database
    class MockDB:
        def execute_query(self, query, params=None, fetch=None):
            return None

    dialog = QuestionEditDialog(MockDB(), tree_id=1)
    dialog.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    test_question_edit_dialog()