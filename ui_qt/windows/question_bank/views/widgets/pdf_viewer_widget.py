"""
Widget hiển thị PDF với đầy đủ tính năng
Tách từ PDFViewer class trong file gốc
"""

import os
import base64
from typing import Optional, List
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QPixmap, QImage, QPainter, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QSlider, QScrollArea, QToolBar, QComboBox,
    QProgressBar, QMenu, QMessageBox, QFileDialog, QApplication
)


class PDFRenderThread(QThread):
    """Thread để render PDF không block UI"""

    page_rendered = Signal(int, QPixmap)
    render_finished = Signal()
    error_occurred = Signal(str)

    def __init__(self, pdf_data, page_num, zoom_level=1.0):
        super().__init__()
        self.pdf_data = pdf_data
        self.page_num = page_num
        self.zoom_level = zoom_level
        self.should_stop = False

    def run(self):
        """Render PDF page trong background thread"""
        try:
            # Thử render với PyMuPDF nếu có
            pixmap = self._render_with_pymupdf()
            if not pixmap.isNull():
                self.page_rendered.emit(self.page_num, pixmap)
                self.render_finished.emit()
                return

            # Fallback: Tạo placeholder image
            pixmap = self._create_pdf_placeholder()
            self.page_rendered.emit(self.page_num, pixmap)
            self.render_finished.emit()

        except Exception as e:
            self.error_occurred.emit(str(e))

    def _render_with_pymupdf(self) -> QPixmap:
        """Render PDF với PyMuPDF (fitz) nếu có cài đặt"""
        try:
            import fitz  # PyMuPDF

            # Mở PDF từ data
            if isinstance(self.pdf_data, str):
                doc = fitz.open(self.pdf_data)  # File path
            else:
                doc = fitz.open(stream=self.pdf_data)  # Binary data

            if self.page_num >= doc.page_count:
                return QPixmap()

            # Render page
            page = doc.load_page(self.page_num - 1)  # 0-based index
            mat = fitz.Matrix(self.zoom_level, self.zoom_level)
            pix = page.get_pixmap(matrix=mat)

            # Convert to QPixmap
            img_data = pix.tobytes("ppm")
            qimg = QImage.fromData(img_data)
            pixmap = QPixmap.fromImage(qimg)

            doc.close()
            return pixmap

        except ImportError:
            print("PyMuPDF không có sẵn - sử dụng placeholder")
            return QPixmap()
        except Exception as e:
            print(f"Lỗi render PDF với PyMuPDF: {e}")
            return QPixmap()

    def _create_pdf_placeholder(self) -> QPixmap:
        """Tạo placeholder image cho PDF"""
        pixmap = QPixmap(400, 500)
        pixmap.fill(Qt.white)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background
        painter.fillRect(pixmap.rect(), Qt.white)
        painter.setPen(QtGui.QPen(Qt.gray, 2))
        painter.drawRect(10, 10, 380, 480)

        # PDF icon và text
        painter.setPen(Qt.black)
        font = painter.font()
        font.setPointSize(16)
        painter.setFont(font)

        painter.drawText(pixmap.rect(), Qt.AlignCenter,
                         f"📄 PDF Trang {self.page_num}\n\n"
                         f"Cần cài PyMuPDF để hiển thị\n"
                         f"pip install PyMuPDF")

        painter.end()
        return pixmap

    def stop(self):
        """Dừng thread"""
        self.should_stop = True


class PDFViewerWidget(QWidget):
    """Widget hiển thị PDF với navigation và zoom"""

    # Signals
    page_changed = Signal(int)  # Trang thay đổi
    pdf_loaded = Signal(str)  # PDF được load
    pdf_closed = Signal()  # PDF bị đóng

    def __init__(self, parent=None):
        super().__init__(parent)

        # PDF data
        self.pdf_data = None
        self.pdf_path: Optional[str] = None
        self.current_page = 1
        self.total_pages = 1
        self.zoom_level = 1.0
        self.min_zoom = 0.25
        self.max_zoom = 5.0

        # Render thread
        self.render_thread: Optional[PDFRenderThread] = None

        # Page cache để tăng tốc
        self.page_cache = {}  # {page_num: QPixmap}
        self.max_cache_size = 10

        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self):
        """Thiết lập giao diện"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Toolbar với controls
        self._create_toolbar(layout)

        # Main display area
        self._create_display_area(layout)

        # Status bar
        self._create_status_bar(layout)

    def _create_toolbar(self, layout: QVBoxLayout):
        """Tạo toolbar với navigation controls"""
        self.toolbar = QToolBar()
        self.toolbar.setStyleSheet("""
            QToolBar {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                spacing: 4px;
                padding: 4px;
            }
            QToolBar QPushButton, QToolBar QSpinBox, QToolBar QComboBox {
                padding: 4px 8px;
                border: 1px solid #ced4da;
                border-radius: 3px;
                background: white;
            }
            QToolBar QPushButton:hover {
                background: #e9ecef;
            }
            QToolBar QPushButton:disabled {
                background: #f8f9fa;
                color: #6c757d;
            }
        """)

        # File operations
        open_btn = QPushButton("📂 Mở")
        open_btn.clicked.connect(self.open_file)
        self.toolbar.addWidget(open_btn)

        close_btn = QPushButton("✖️ Đóng")
        close_btn.clicked.connect(self.close_pdf)
        self.toolbar.addWidget(close_btn)

        self.toolbar.addSeparator()

        # Navigation controls
        self.first_page_btn = QPushButton("⏮️")
        self.first_page_btn.setToolTip("Trang đầu")
        self.first_page_btn.clicked.connect(self.first_page)
        self.toolbar.addWidget(self.first_page_btn)

        self.prev_page_btn = QPushButton("◀️")
        self.prev_page_btn.setToolTip("Trang trước")
        self.prev_page_btn.clicked.connect(self.prev_page)
        self.toolbar.addWidget(self.prev_page_btn)

        # Page input
        self.toolbar.addWidget(QLabel("Trang:"))
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setValue(1)
        self.page_spin.valueChanged.connect(self.goto_page)
        self.toolbar.addWidget(self.page_spin)

        self.page_total_label = QLabel("/ 1")
        self.toolbar.addWidget(self.page_total_label)

        self.next_page_btn = QPushButton("▶️")
        self.next_page_btn.setToolTip("Trang sau")
        self.next_page_btn.clicked.connect(self.next_page)
        self.toolbar.addWidget(self.next_page_btn)

        self.last_page_btn = QPushButton("⏭️")
        self.last_page_btn.setToolTip("Trang cuối")
        self.last_page_btn.clicked.connect(self.last_page)
        self.toolbar.addWidget(self.last_page_btn)

        self.toolbar.addSeparator()

        # Zoom controls
        self.zoom_out_btn = QPushButton("🔍-")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.toolbar.addWidget(self.zoom_out_btn)

        self.zoom_combo = QComboBox()
        self.zoom_combo.addItems([
            "25%", "50%", "75%", "100%", "125%", "150%", "200%", "300%", "400%"
        ])
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.currentTextChanged.connect(self._on_zoom_combo_changed)
        self.toolbar.addWidget(self.zoom_combo)

        self.zoom_in_btn = QPushButton("🔍+")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.toolbar.addWidget(self.zoom_in_btn)

        self.fit_width_btn = QPushButton("📏 Vừa rộng")
        self.fit_width_btn.clicked.connect(self.fit_to_width)
        self.toolbar.addWidget(self.fit_width_btn)

        self.fit_page_btn = QPushButton("📄 Vừa trang")
        self.fit_page_btn.clicked.connect(self.fit_to_page)
        self.toolbar.addWidget(self.fit_page_btn)

        self.toolbar.addSeparator()

        # Actions
        self.save_btn = QPushButton("💾 Lưu")
        self.save_btn.clicked.connect(self.save_current_page)
        self.toolbar.addWidget(self.save_btn)

        self.print_btn = QPushButton("🖨️ In")
        self.print_btn.clicked.connect(self.print_pdf)
        self.toolbar.addWidget(self.print_btn)

        layout.addWidget(self.toolbar)

    def _create_display_area(self, layout: QVBoxLayout):
        """Tạo khu vực hiển thị PDF"""
        # Scroll area chứa PDF page
        self.scroll_area = QScrollArea()
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: #e9ecef;
                border: 1px solid #dee2e6;
            }
        """)

        # Label hiển thị trang PDF
        self.pdf_label = QLabel()
        self.pdf_label.setAlignment(Qt.AlignCenter)
        self.pdf_label.setStyleSheet("""
            QLabel {
                background: white;
                border: 1px solid #ccc;
                margin: 10px;
            }
        """)
        self.pdf_label.setText("📄 Chưa mở PDF nào\n\nClick 'Mở' để chọn file PDF")
        self.pdf_label.setMinimumSize(400, 500)

        # Context menu cho PDF
        self.pdf_label.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pdf_label.customContextMenuRequested.connect(self._show_context_menu)

        self.scroll_area.setWidget(self.pdf_label)
        self.scroll_area.setWidgetResizable(True)

        layout.addWidget(self.scroll_area)

    def _create_status_bar(self, layout: QVBoxLayout):
        """Tạo status bar"""
        status_widget = QWidget()
        status_widget.setFixedHeight(25)
        status_widget.setStyleSheet("""
            QWidget {
                background: #e9ecef;
                border-top: 1px solid #dee2e6;
            }
        """)

        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(10, 2, 10, 2)

        self.status_label = QLabel("Sẵn sàng")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        # Progress bar cho loading
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        status_layout.addWidget(self.progress_bar)

        layout.addWidget(status_widget)

    def _setup_connections(self):
        """Thiết lập kết nối và shortcuts"""
        # Keyboard shortcuts
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+O"), self, self.open_file)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+W"), self, self.close_pdf)
        QtGui.QShortcut(QtGui.QKeySequence("Home"), self, self.first_page)
        QtGui.QShortcut(QtGui.QKeySequence("End"), self, self.last_page)
        QtGui.QShortcut(QtGui.QKeySequence("Page_Up"), self, self.prev_page)
        QtGui.QShortcut(QtGui.QKeySequence("Page_Down"), self, self.next_page)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Plus"), self, self.zoom_in)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Minus"), self, self.zoom_out)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+0"), self, self.fit_to_page)

    # ========== PUBLIC METHODS - File Operations ==========

    def open_file(self):
        """Mở file PDF"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file PDF", "", "PDF Files (*.pdf);;All Files (*)"
        )

        if file_path:
            self.load_pdf(file_path)

    def load_pdf(self, file_path: str):
        """Load PDF từ file path"""
        if not os.path.exists(file_path):
            self._show_error(f"File không tồn tại: {file_path}")
            return False

        try:
            self.pdf_path = file_path
            with open(file_path, 'rb') as f:
                self.pdf_data = f.read()

            self._analyze_pdf()
            self._update_ui_state()
            self.goto_page(1)

            self.status_label.setText(f"📄 {os.path.basename(file_path)}")
            self.pdf_loaded.emit(file_path)
            return True

        except Exception as e:
            self._show_error(f"Không thể mở PDF: {e}")
            return False

    def load_pdf_from_data(self, pdf_data: bytes, filename: str = "document.pdf"):
        """Load PDF từ binary data"""
        try:
            self.pdf_data = pdf_data
            self.pdf_path = filename

            self._analyze_pdf()
            self._update_ui_state()
            self.goto_page(1)

            self.status_label.setText(f"📄 {filename}")
            self.pdf_loaded.emit(filename)
            return True

        except Exception as e:
            self._show_error(f"Không thể load PDF data: {e}")
            return False

    def close_pdf(self):
        """Đóng PDF hiện tại"""
        self.pdf_data = None
        self.pdf_path = None
        self.current_page = 1
        self.total_pages = 1
        self.page_cache.clear()

        if self.render_thread:
            self.render_thread.stop()
            self.render_thread.wait()
            self.render_thread = None

        self.pdf_label.setText("📄 Chưa mở PDF nào\n\nClick 'Mở' để chọn file PDF")
        self.pdf_label.setMinimumSize(400, 500)

        self._update_ui_state()
        self.status_label.setText("Đã đóng PDF")
        self.pdf_closed.emit()

    # ========== PUBLIC METHODS - Navigation ==========

    def first_page(self):
        """Đi đến trang đầu"""
        self.goto_page(1)

    def last_page(self):
        """Đi đến trang cuối"""
        self.goto_page(self.total_pages)

    def prev_page(self):
        """Trang trước"""
        if self.current_page > 1:
            self.goto_page(self.current_page - 1)

    def next_page(self):
        """Trang sau"""
        if self.current_page < self.total_pages:
            self.goto_page(self.current_page + 1)

    def goto_page(self, page_num: int):
        """Đi đến trang cụ thể"""
        if not self.pdf_data:
            return

        page_num = max(1, min(page_num, self.total_pages))
        if page_num == self.current_page:
            return

        self.current_page = page_num
        self.page_spin.setValue(page_num)
        self._render_current_page()
        self._update_navigation_buttons()

        self.page_changed.emit(page_num)

    # ========== PUBLIC METHODS - Zoom ==========

    def zoom_in(self):
        """Phóng to"""
        new_zoom = min(self.zoom_level * 1.05, self.max_zoom)
        self.set_zoom_level(new_zoom)

    def zoom_out(self):
        """Thu nhỏ"""
        new_zoom = max(self.zoom_level / 1.05, self.min_zoom)
        self.set_zoom_level(new_zoom)

    def set_zoom_level(self, zoom_level: float):
        """Thiết lập mức zoom"""
        zoom_level = max(self.min_zoom, min(zoom_level, self.max_zoom))
        if abs(zoom_level - self.zoom_level) < 0.01:
            return

        self.zoom_level = zoom_level
        self.zoom_combo.setCurrentText(f"{int(zoom_level * 100)}%")

        # Clear cache vì zoom thay đổi
        self.page_cache.clear()
        self._render_current_page()

    def fit_to_width(self):
        """Vừa độ rộng"""
        if not self.pdf_data:
            return

        # Estimate zoom để fit width
        available_width = self.scroll_area.viewport().width() - 20
        # Giả sử PDF page có tỷ lệ A4 (210mm x 297mm)
        estimated_zoom = available_width / 595  # 595 points ≈ A4 width

        self.set_zoom_level(max(self.min_zoom, min(estimated_zoom, self.max_zoom)))

    def fit_to_page(self):
        """Vừa cả trang"""
        if not self.pdf_data:
            return

        available_size = self.scroll_area.viewport().size()
        available_width = available_size.width() - 20
        available_height = available_size.height() - 20

        # Tỷ lệ A4
        zoom_width = available_width / 595
        zoom_height = available_height / 842
        estimated_zoom = min(zoom_width, zoom_height)

        self.set_zoom_level(max(self.min_zoom, min(estimated_zoom, self.max_zoom)))

    # ========== PUBLIC METHODS - Actions ==========

    def save_current_page(self):
        """Lưu trang hiện tại thành ảnh"""
        if not self.pdf_data:
            return

        pixmap = self.pdf_label.pixmap()
        if not pixmap:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Lưu trang", f"page_{self.current_page}.png",
            "PNG Files (*.png);;JPEG Files (*.jpg);;All Files (*)"
        )

        if file_path and pixmap.save(file_path):
            self.status_label.setText(f"Đã lưu: {os.path.basename(file_path)}")

    def print_pdf(self):
        """In PDF"""
        if not self.pdf_data:
            return

        QMessageBox.information(
            self, "Thông báo",
            "Tính năng in đang được phát triển"
        )

    # ========== PRIVATE METHODS ==========

    def _analyze_pdf(self):
        """Phân tích PDF để lấy thông tin cơ bản"""
        try:
            # Thử dùng PyMuPDF để đếm trang
            import fitz
            if isinstance(self.pdf_data, str):
                doc = fitz.open(self.pdf_data)
            else:
                doc = fitz.open(stream=self.pdf_data)

            self.total_pages = doc.page_count
            doc.close()

        except ImportError:
            # Fallback: Estimate dựa trên file size
            self.total_pages = max(1, len(self.pdf_data) // 50000)
        except Exception as e:
            print(f"Lỗi phân tích PDF: {e}")
            self.total_pages = 1

    def _render_current_page(self):
        """Render trang hiện tại"""
        if not self.pdf_data:
            return

        # Kiểm tra cache
        cache_key = f"{self.current_page}_{self.zoom_level}"
        if cache_key in self.page_cache:
            pixmap = self.page_cache[cache_key]
            self.pdf_label.setPixmap(pixmap)
            self.pdf_label.resize(pixmap.size())
            return

        # Dừng render thread cũ
        if self.render_thread:
            self.render_thread.stop()
            self.render_thread.wait()

        # Hiển thị loading
        self.progress_bar.setVisible(True)
        self.status_label.setText("Đang tải...")

        # Bắt đầu render thread mới
        self.render_thread = PDFRenderThread(self.pdf_data, self.current_page, self.zoom_level)
        self.render_thread.page_rendered.connect(self._on_page_rendered)
        self.render_thread.render_finished.connect(self._on_render_finished)
        self.render_thread.error_occurred.connect(self._on_render_error)
        self.render_thread.start()

    def _on_page_rendered(self, page_num: int, pixmap: QPixmap):
        """Xử lý khi render xong"""
        if page_num == self.current_page:
            self.pdf_label.setPixmap(pixmap)
            self.pdf_label.resize(pixmap.size())

            # Lưu vào cache
            cache_key = f"{page_num}_{self.zoom_level}"
            self.page_cache[cache_key] = pixmap

            # Giới hạn cache size
            if len(self.page_cache) > self.max_cache_size:
                oldest_key = list(self.page_cache.keys())[0]
                del self.page_cache[oldest_key]

    def _on_render_finished(self):
        """Xử lý khi render hoàn tất"""
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Trang {self.current_page}/{self.total_pages}")

    def _on_render_error(self, error_msg: str):
        """Xử lý lỗi render"""
        self.progress_bar.setVisible(False)
        self.status_label.setText("Lỗi hiển thị")
        self._show_error(f"Lỗi render PDF: {error_msg}")

    def _update_ui_state(self):
        """Cập nhật trạng thái UI"""
        has_pdf = self.pdf_data is not None

        # Update navigation
        self.page_spin.setMaximum(self.total_pages)
        self.page_total_label.setText(f"/ {self.total_pages}")

        # Enable/disable controls
        controls = [
            self.first_page_btn, self.prev_page_btn, self.next_page_btn,
            self.last_page_btn, self.page_spin, self.zoom_in_btn,
            self.zoom_out_btn, self.zoom_combo, self.fit_width_btn,
            self.fit_page_btn, self.save_btn, self.print_btn
        ]

        for control in controls:
            control.setEnabled(has_pdf)

        if has_pdf:
            self._update_navigation_buttons()

    def _update_navigation_buttons(self):
        """Cập nhật trạng thái navigation buttons"""
        self.first_page_btn.setEnabled(self.current_page > 1)
        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < self.total_pages)
        self.last_page_btn.setEnabled(self.current_page < self.total_pages)

    def _on_zoom_combo_changed(self, text: str):
        """Xử lý thay đổi zoom combo"""
        try:
            zoom_percent = int(text.replace('%', ''))
            zoom_level = zoom_percent / 100.0
            if abs(zoom_level - self.zoom_level) > 0.01:
                self.set_zoom_level(zoom_level)
        except ValueError:
            pass

    def _show_context_menu(self, position):
        """Hiển thị context menu"""
        if not self.pdf_data:
            return

        menu = QMenu(self)

        menu.addAction("📄 Trang đầu", self.first_page)
        menu.addAction("📄 Trang cuối", self.last_page)
        menu.addSeparator()

        menu.addAction("🔍+ Phóng to", self.zoom_in)
        menu.addAction("🔍- Thu nhỏ", self.zoom_out)
        menu.addAction("📏 Vừa rộng", self.fit_to_width)
        menu.addAction("📄 Vừa trang", self.fit_to_page)
        menu.addSeparator()

        menu.addAction("💾 Lưu trang", self.save_current_page)
        menu.addAction("📋 Copy", self._copy_current_page)
        menu.addSeparator()

        menu.addAction("✖️ Đóng PDF", self.close_pdf)

        menu.exec(self.pdf_label.mapToGlobal(position))

    def _copy_current_page(self):
        """Copy trang hiện tại vào clipboard"""
        pixmap = self.pdf_label.pixmap()
        if pixmap:
            QApplication.clipboard().setPixmap(pixmap)
            self.status_label.setText("Đã copy trang vào clipboard")

    def _show_error(self, message: str):
        """Hiển thị lỗi"""
        QMessageBox.warning(self, "Lỗi PDF Viewer", message)
        self.status_label.setText("Lỗi")

    # ========== UTILITY METHODS ==========

    def has_pdf(self) -> bool:
        """Kiểm tra có PDF đang mở hay không"""
        return self.pdf_data is not None

    def get_current_page(self) -> int:
        """Lấy trang hiện tại"""
        return self.current_page

    def get_total_pages(self) -> int:
        """Lấy tổng số trang"""
        return self.total_pages

    def get_zoom_level(self) -> float:
        """Lấy mức zoom hiện tại"""
        return self.zoom_level

    def get_pdf_info(self) -> dict:
        """Lấy thông tin PDF"""
        return {
            'path': self.pdf_path,
            'current_page': self.current_page,
            'total_pages': self.total_pages,
            'zoom_level': self.zoom_level,
            'has_pdf': self.has_pdf()
        }

    def clear(self):
        """Xóa PDF (alias cho close_pdf)"""
        self.close_pdf()