"""
Widget hiển thị ảnh chuyên dụng với đầy đủ tính năng
Tách từ ImageViewerDialog, AdaptiveImageViewer trong file gốc
"""

import os
import base64
from typing import Optional
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal, QPoint, QTimer, QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QPixmap, QImage, QCursor, QPainter, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QToolBar, QSlider, QMenu, QApplication
)


class ImageViewerWidget(QWidget):
    """Widget hiển thị ảnh với zoom, pan, rotate và fullscreen"""

    # Signals
    image_clicked = Signal()  # Click vào ảnh
    image_double_clicked = Signal()  # Double click để fullscreen
    image_changed = Signal()  # Ảnh thay đổi

    def __init__(self, parent=None, mode="adaptive"):
        """
        Args:
            mode: "adaptive" (tự động điều chỉnh) hoặc "full" (đầy đủ tính năng)
        """
        super().__init__(parent)
        self.mode = mode
        self.auto_fullscreen = False
        # Image data
        self.original_pixmap: Optional[QPixmap] = None
        self.current_pixmap: Optional[QPixmap] = None

        # Zoom & Pan properties
        self.current_zoom = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        self.zoom_step = 0.05
        self.pan_offset = QPoint(0, 0)
        self.last_pan_point = QPoint()
        self.is_panning = False

        # Adaptive mode properties
        self.max_width = 600
        self.max_height = 400
        self.min_height = 100

        # Rotation
        self.rotation_angle = 0

        self._setup_ui()
        self._setup_connections()
        self.setWindowFlags(
            Qt.Window |
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_DeleteOnClose)

        # Thiết lập kích thước toàn màn hình
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.geometry()
            self.setGeometry(screen_geometry)
    def _setup_ui(self):
        """Thiết lập giao diện theo mode"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        if self.mode == "full":
            # Mode đầy đủ tính năng với toolbar
            self._create_toolbar(layout)
            self._create_full_viewer(layout)
            self._create_status_bar(layout)
        else:
            # Mode adaptive (đơn giản)
            self._create_adaptive_viewer(layout)

    def _create_toolbar(self, layout: QVBoxLayout):
        """Tạo toolbar với controls"""
        self.toolbar = QToolBar()
        self.toolbar.setStyleSheet("""
            QToolBar {
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                spacing: 4px;
                padding: 4px;
            }
            QToolBar QPushButton {
                padding: 4px 8px;
                border: 1px solid #ced4da;
                border-radius: 3px;
                background: white;
            }
            QToolBar QPushButton:hover {
                background: #e9ecef;
                border-color: #adb5bd;
            }
        """)

        # Zoom controls
        zoom_out_btn = QPushButton("🔍-")
        zoom_out_btn.setToolTip("Thu nhỏ (Ctrl+Mouse Wheel)")
        zoom_out_btn.clicked.connect(self.zoom_out)
        self.toolbar.addWidget(zoom_out_btn)

        # Zoom slider
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(10, 1000)  # 10% to 1000%
        self.zoom_slider.setValue(100)
        self.zoom_slider.setMaximumWidth(150)
        self.zoom_slider.valueChanged.connect(self._on_zoom_slider_changed)
        self.toolbar.addWidget(self.zoom_slider)

        zoom_in_btn = QPushButton("🔍+")
        zoom_in_btn.setToolTip("Phóng to (Ctrl+Mouse Wheel)")
        zoom_in_btn.clicked.connect(self.zoom_in)
        self.toolbar.addWidget(zoom_in_btn)

        # Zoom level label
        self.zoom_label = QLabel("100%")
        self.zoom_label.setMinimumWidth(50)
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.toolbar.addWidget(self.zoom_label)

        self.toolbar.addSeparator()

        # Fit controls
        fit_btn = QPushButton("📐 Vừa cửa sổ")
        fit_btn.clicked.connect(self.fit_to_window)
        self.toolbar.addWidget(fit_btn)

        actual_size_btn = QPushButton("🔢 1:1")
        actual_size_btn.setToolTip("Kích thước gốc")
        actual_size_btn.clicked.connect(self.actual_size)
        self.toolbar.addWidget(actual_size_btn)

        self.toolbar.addSeparator()

        # Rotation controls
        rotate_left_btn = QPushButton("↺")
        rotate_left_btn.setToolTip("Xoay trái 90°")
        rotate_left_btn.clicked.connect(self.rotate_left)
        self.toolbar.addWidget(rotate_left_btn)

        rotate_right_btn = QPushButton("↻")
        rotate_right_btn.setToolTip("Xoay phải 90°")
        rotate_right_btn.clicked.connect(self.rotate_right)
        self.toolbar.addWidget(rotate_right_btn)

        self.toolbar.addSeparator()

        # Action buttons
        fullscreen_btn = QPushButton("🔍 Fullscreen")
        fullscreen_btn.clicked.connect(self.open_fullscreen)
        self.toolbar.addWidget(fullscreen_btn)

        save_btn = QPushButton("💾 Lưu")
        save_btn.clicked.connect(self.save_image)
        self.toolbar.addWidget(save_btn)

        layout.addWidget(self.toolbar)

    def _create_full_viewer(self, layout: QVBoxLayout):
        """Tạo viewer đầy đủ tính năng với scroll area"""
        # Scroll area chứa ảnh
        self.scroll_area = QScrollArea()
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: #2b2b2b;
                border: 1px solid #555;
            }
        """)

        # Label hiển thị ảnh
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                background: transparent;
                color: #888;
            }
        """)
        self.image_label.setText("🖼️ Chưa có ảnh")
        self.image_label.setMinimumSize(400, 300)

        # Thiết lập mouse events
        self.image_label.mousePressEvent = self._mouse_press_event
        self.image_label.mouseMoveEvent = self._mouse_move_event
        self.image_label.mouseReleaseEvent = self._mouse_release_event
        self.image_label.mouseDoubleClickEvent = self._mouse_double_click_event

        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setWidgetResizable(True)

        # Enable wheel event cho zoom
        self.scroll_area.wheelEvent = self._wheel_event

        layout.addWidget(self.scroll_area)

    def _create_adaptive_viewer(self, layout: QVBoxLayout):
        """Tạo viewer adaptive (tự động điều chỉnh kích thước)"""
        # Info label
        self.info_label = QLabel("📷 Ảnh sẽ hiển thị ở đây")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 12px;
                padding: 5px;
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.info_label)

        # Image label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                border: 1px solid #ddd;
                border-radius: 4px;
                background: white;
                padding: 10px;
                min-height: 100px;
            }
        """)
        self.image_label.setText("🖼️ Chưa có ảnh")
        self.image_label.mouseDoubleClickEvent = self._mouse_double_click_event

        # Enable drag & drop
        self.image_label.setAcceptDrops(True)
        self.image_label.dragEnterEvent = self._drag_enter_event
        self.image_label.dropEvent = self._drop_event

        layout.addWidget(self.image_label)

    def _create_status_bar(self, layout: QVBoxLayout):
        """Tạo status bar hiển thị thông tin ảnh"""
        self.status_label = QLabel("Sẵn sàng")
        self.status_label.setStyleSheet("""
            QLabel {
                background: #e9ecef;
                border-top: 1px solid #dee2e6;
                padding: 5px 10px;
                font-size: 11px;
                color: #495057;
            }
        """)
        layout.addWidget(self.status_label)

    def _setup_connections(self):
        """Thiết lập kết nối và shortcuts"""
        # Context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        if hasattr(self, 'scroll_area'):
            # Keyboard shortcuts chỉ có trong full mode
            QtGui.QShortcut(QtGui.QKeySequence("Ctrl+0"), self, self.fit_to_window)
            QtGui.QShortcut(QtGui.QKeySequence("Ctrl+1"), self, self.actual_size)
            QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Plus"), self, self.zoom_in)
            QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Minus"), self, self.zoom_out)
            QtGui.QShortcut(QtGui.QKeySequence("F11"), self, self.open_fullscreen)
            QtGui.QShortcut(QtGui.QKeySequence("Ctrl+S"), self, self.save_image)

    # ========== PUBLIC METHODS - Hiển thị ảnh ==========

    def set_pixmap(self, pixmap: QPixmap):
        """Thiết lập ảnh từ QPixmap"""
        if pixmap is None or pixmap.isNull():
            self.clear_image()
            return

        self.original_pixmap = pixmap.copy()
        self.current_pixmap = pixmap.copy()
        self.rotation_angle = 0

        if self.mode == "adaptive":
            self._display_adaptive_image()
        else:
            self.current_zoom = 1.0
            self._update_display()
            QTimer.singleShot(100, self.fit_to_window)

        self.image_changed.emit()

    def set_image_from_data(self, data, format_hint: str = None):
        """Thiết lập ảnh từ binary data"""
        if not data:
            self.clear_image()
            return False

        try:
            pixmap = QPixmap()
            success = False

            # Nếu là bytes
            if isinstance(data, (bytes, bytearray)):
                if pixmap.loadFromData(data):
                    success = True
                else:
                    # Thử decode base64 nếu load trực tiếp thất bại
                    try:
                        decoded_data = base64.b64decode(data)
                        if pixmap.loadFromData(decoded_data):
                            success = True
                    except Exception:
                        pass

            # Nếu là string
            elif isinstance(data, str):
                # Kiểm tra file path
                if os.path.exists(data):
                    pixmap = QPixmap(data)
                    if not pixmap.isNull():
                        success = True
                else:
                    # Xử lý Data URL format
                    if data.startswith('data:image'):
                        if ',base64,' in data:
                            try:
                                _, base64_data = data.split(',base64,', 1)
                                decoded_data = base64.b64decode(base64_data)
                                if pixmap.loadFromData(decoded_data):
                                    success = True
                            except Exception:
                                pass
                    else:
                        # Thử decode base64 string thuần
                        try:
                            decoded_data = base64.b64decode(data)
                            if pixmap.loadFromData(decoded_data):
                                success = True
                        except Exception:
                            pass

            # Nếu load thành công
            if success and not pixmap.isNull():
                self.set_pixmap(pixmap)
                # Tự động fit ảnh vừa màn hình cho mode full
                if self.mode == "full":
                    QTimer.singleShot(150, self.fit_to_window)
                return True

            # Nếu thất bại
            self.clear_image()
            return False

        except Exception as e:
            print(f"Lỗi load ảnh từ data: {e}")
            self.clear_image()
            return False
    def set_image_from_file(self, file_path: str):
        """Thiết lập ảnh từ file"""
        if not os.path.exists(file_path):
            self.clear_image()
            return False

        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            self.set_pixmap(pixmap)
            # Tự động fit ảnh vừa màn hình
            if self.mode == "full":
                QTimer.singleShot(100, self.fit_to_window)
            return True
        return False

    def clear_image(self):
        """Xóa ảnh"""
        self.original_pixmap = None
        self.current_pixmap = None
        self.current_zoom = 1.0
        self.rotation_angle = 0
        self.pan_offset = QPoint(0, 0)

        self.image_label.clear()
        self.image_label.setText("🖼️ Chưa có ảnh")

        if self.mode == "adaptive":
            self.setMinimumHeight(self.min_height)
            self.setMaximumHeight(self.min_height)
            self.info_label.setText("📷 Chưa có ảnh")
        else:
            self._update_status("Chưa có ảnh")

        self.image_changed.emit()

    # ========== ZOOM & PAN METHODS ==========

    def zoom_in(self):
        """Phóng to ảnh"""
        self._set_zoom(self.current_zoom + self.zoom_step)

    def zoom_out(self):
        """Thu nhỏ ảnh"""
        self._set_zoom(self.current_zoom - self.zoom_step)

    def _set_zoom(self, zoom_level: float):
        """Thiết lập mức zoom"""
        if not self.original_pixmap:
            return

        zoom_level = max(self.min_zoom, min(self.max_zoom, zoom_level))
        self.current_zoom = zoom_level

        if self.mode == "full":
            self._update_display()
            # Cập nhật slider
            self.zoom_slider.blockSignals(True)
            self.zoom_slider.setValue(int(zoom_level * 100))
            self.zoom_slider.blockSignals(False)
        else:
            # Adaptive mode: thay đổi max size
            original_size = self.original_pixmap.size()
            self.max_width = int(original_size.width() * zoom_level)
            self.max_height = int(original_size.height() * zoom_level)
            self._display_adaptive_image()

    def fit_to_window(self):
        """Điều chỉnh ảnh vừa cửa sổ"""
        if not self.original_pixmap or self.mode != "full":
            return

        # Đảm bảo scroll area đã render
        self.scroll_area.updateGeometry()
        QApplication.processEvents()

        available_size = self.scroll_area.viewport().size()

        # Kiểm tra kích thước hợp lệ
        if available_size.width() <= 0 or available_size.height() <= 0:
            QTimer.singleShot(100, self.fit_to_window)
            return

        image_size = self._get_rotated_size(self.original_pixmap.size())

        scale_w = available_size.width() / image_size.width()
        scale_h = available_size.height() / image_size.height()
        scale_factor = min(scale_w, scale_h) * 0.95  # 95% để có margin

        self._set_zoom(scale_factor)
    def actual_size(self):
        """Hiển thị ảnh ở kích thước gốc"""
        self._set_zoom(1.0)

    # ========== ROTATION METHODS ==========

    def rotate_left(self):
        """Xoay trái 90°"""
        self.rotation_angle = (self.rotation_angle - 90) % 360
        self._apply_rotation()

    def rotate_right(self):
        """Xoay phải 90°"""
        self.rotation_angle = (self.rotation_angle + 90) % 360
        self._apply_rotation()

    def _apply_rotation(self):
        """Áp dụng góc xoay"""
        if not self.original_pixmap:
            return

        if self.rotation_angle == 0:
            self.current_pixmap = self.original_pixmap.copy()
        else:
            transform = QtGui.QTransform()
            transform.rotate(self.rotation_angle)
            self.current_pixmap = self.original_pixmap.transformed(transform)

        if self.mode == "adaptive":
            self._display_adaptive_image()
        else:
            self._update_display()

    def _get_rotated_size(self, size):
        """Lấy kích thước sau khi xoay"""
        if self.rotation_angle % 180 == 0:
            return size
        else:
            return QtCore.QSize(size.height(), size.width())

    # ========== DISPLAY METHODS ==========

    def _update_display(self):
        """Cập nhật hiển thị (full mode)"""
        if not self.current_pixmap or self.mode != "full":
            return

        new_size = self.current_pixmap.size() * self.current_zoom
        scaled_pixmap = self.current_pixmap.scaled(
            new_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.resize(new_size)

        self._update_status()
        self._update_zoom_label()

    def _display_adaptive_image(self):
        """Hiển thị ảnh adaptive mode"""
        if not self.current_pixmap or self.mode != "adaptive":
            return

        original_size = self.current_pixmap.size()

        # Tính toán kích thước hiển thị
        display_width = min(original_size.width(), self.max_width)
        display_height = min(original_size.height(), self.max_height)

        if original_size.width() > 0 and original_size.height() > 0:
            scale_width = self.max_width / original_size.width()
            scale_height = self.max_height / original_size.height()
            scale_factor = min(scale_width, scale_height, 1.0)

            display_width = int(original_size.width() * scale_factor)
            display_height = int(original_size.height() * scale_factor)

        # Scale ảnh
        scaled_pixmap = self.current_pixmap.scaled(
            display_width, display_height,
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.setMinimumSize(display_width, display_height)

        # Điều chỉnh kích thước widget
        widget_height = display_height + 80
        self.setMinimumHeight(widget_height)
        self.setMaximumHeight(max(widget_height, 400))

        # Cập nhật info
        scale_percent = int((display_width / original_size.width()) * 100) if original_size.width() > 0 else 100
        self.info_label.setText(
            f"📷 Gốc: {original_size.width()}×{original_size.height()} | "
            f"Hiển thị: {display_width}×{display_height} | "
            f"Tỷ lệ: {scale_percent}%"
        )

        if self.parent():
            self.parent().updateGeometry()

    def _update_status(self, message: str = None):
        """Cập nhật status bar"""
        if self.mode != "full" or not hasattr(self, 'status_label'):
            return

        if message:
            self.status_label.setText(message)
            return

        if not self.original_pixmap:
            self.status_label.setText("Chưa có ảnh")
            return

        original_size = self.original_pixmap.size()
        current_size = self.image_label.size()
        zoom_percent = int(self.current_zoom * 100)

        status_text = (
            f"🖼️ Gốc: {original_size.width()}×{original_size.height()} | "
            f"Hiển thị: {current_size.width()}×{current_size.height()} | "
            f"Zoom: {zoom_percent}% | "
            f"Xoay: {self.rotation_angle}°"
        )

        self.status_label.setText(status_text)

    def _update_zoom_label(self):
        """Cập nhật label zoom"""
        if hasattr(self, 'zoom_label'):
            self.zoom_label.setText(f"{int(self.current_zoom * 100)}%")

    # ========== EVENT HANDLERS ==========

    def _on_zoom_slider_changed(self, value):
        """Xử lý thay đổi zoom slider"""
        zoom_level = value / 100.0
        if abs(zoom_level - self.current_zoom) > 0.01:
            self._set_zoom(zoom_level)

    def _mouse_press_event(self, event):
        """Xử lý nhấn chuột"""
        if event.button() == Qt.LeftButton:
            self.is_panning = True
            self.last_pan_point = event.pos()
            self.image_label.setCursor(Qt.ClosedHandCursor)
            self.image_clicked.emit()

        # Gọi parent event
        QLabel.mousePressEvent(self.image_label, event)

    def _mouse_move_event(self, event):
        """Xử lý di chuyển chuột (panning)"""
        if self.is_panning and (event.buttons() & Qt.LeftButton) and self.mode == "full":
            delta = event.pos() - self.last_pan_point

            h_scroll = self.scroll_area.horizontalScrollBar()
            v_scroll = self.scroll_area.verticalScrollBar()

            h_scroll.setValue(h_scroll.value() - delta.x())
            v_scroll.setValue(v_scroll.value() - delta.y())

            self.last_pan_point = event.pos()

        QLabel.mouseMoveEvent(self.image_label, event)

    def _mouse_release_event(self, event):
        """Xử lý thả chuột"""
        if event.button() == Qt.LeftButton:
            self.is_panning = False
            self.image_label.setCursor(Qt.OpenHandCursor if self.original_pixmap else Qt.ArrowCursor)

        QLabel.mouseReleaseEvent(self.image_label, event)

    def _mouse_double_click_event(self, event):
        """Xử lý double click"""
        self.image_double_clicked.emit()

    def _wheel_event(self, event):
        """Xử lý zoom bằng mouse wheel"""
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.ControlModifier and self.original_pixmap:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            # Scroll bình thường
            QtWidgets.QScrollArea.wheelEvent(self.scroll_area, event)

    def _drag_enter_event(self, event):
        """Xử lý drag enter"""
        if event.mimeData().hasImage() or event.mimeData().hasUrls():
            event.acceptProposedAction()

    def _drop_event(self, event):
        """Xử lý drop file"""
        mime_data = event.mimeData()

        if mime_data.hasImage():
            image = mime_data.imageData()
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                self.set_pixmap(pixmap)
        elif mime_data.hasUrls():
            for url in mime_data.urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
                    if self.set_image_from_file(file_path):
                        break

    def _show_context_menu(self, position):
        """Hiển thị context menu"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: white;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QMenu::item {
                padding: 8px 16px;
            }
            QMenu::item:selected {
                background: #e3f2fd;
            }
        """)

        if self.original_pixmap:
            if self.mode == "full":
                menu.addAction("🔍+ Phóng to", self.zoom_in)
                menu.addAction("🔍- Thu nhỏ", self.zoom_out)
                menu.addAction("📐 Vừa cửa sổ", self.fit_to_window)
                menu.addAction("🔢 Kích thước gốc", self.actual_size)
                menu.addSeparator()
                menu.addAction("↺ Xoay trái", self.rotate_left)
                menu.addAction("↻ Xoay phải", self.rotate_right)
                menu.addSeparator()

            menu.addAction("🔍 Fullscreen", self.open_fullscreen)
            menu.addAction("💾 Lưu ảnh", self.save_image)
            menu.addAction("📋 Copy", self.copy_image)
            menu.addSeparator()

        menu.addAction("📂 Mở file", self.open_file)
        menu.addAction("📋 Paste", self.paste_image)

        if self.original_pixmap:
            menu.addSeparator()
            menu.addAction("🗑️ Xóa ảnh", self.clear_image)

        if self.original_pixmap:
            menu.addSeparator()
            auto_action = menu.addAction("🔄 Tự động Fullscreen")
            auto_action.setCheckable(True)
            auto_action.setChecked(self.auto_fullscreen)
            auto_action.triggered.connect(lambda checked: self.set_auto_fullscreen(checked))
        menu.exec(self.mapToGlobal(position))

    # ========== ACTION METHODS ==========

    def open_fullscreen(self):
        """Mở ảnh trong cửa sổ fullscreen"""
        if not self.original_pixmap:
            return

        # Tạo dialog fullscreen
        from ..dialogs.fullscreen_image_dialog import FullscreenImageDialog
        dialog = FullscreenImageDialog(self.original_pixmap, self)

        # Hiển thị fullscreen - KHÔNG dùng setModal() cho widget
        dialog.showFullScreen()

    def save_image(self):
        """Lưu ảnh ra file"""
        if not self.original_pixmap:
            QtWidgets.QMessageBox.information(self, "Thông báo", "Chưa có ảnh để lưu")
            return

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Lưu ảnh", "",
            "PNG Files (*.png);;JPEG Files (*.jpg);;All Files (*)"
        )

        if file_path:
            if self.original_pixmap.save(file_path):
                QtWidgets.QMessageBox.information(self, "Thành công", f"Đã lưu ảnh: {file_path}")
            else:
                QtWidgets.QMessageBox.warning(self, "Lỗi", "Không thể lưu ảnh")

    def copy_image(self):
        """Copy ảnh vào clipboard"""
        if self.original_pixmap:
            QApplication.clipboard().setPixmap(self.original_pixmap)

    def paste_image(self):
        """Paste ảnh từ clipboard"""
        clipboard = QApplication.clipboard()
        if clipboard.mimeData().hasImage():
            image = clipboard.image()
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                self.set_pixmap(pixmap)
        else:
            QtWidgets.QMessageBox.information(self, "Thông báo", "Clipboard không có ảnh")

    def open_file(self):
        """Mở file ảnh"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Chọn ảnh", "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;All Files (*)"
        )

        if file_path:
            self.set_image_from_file(file_path)

    # ========== UTILITY METHODS ==========

    def get_image_data(self) -> Optional[bytes]:
        """Lấy dữ liệu ảnh dưới dạng bytes"""
        if not self.original_pixmap:
            return None

        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        buffer.open(QIODevice.WriteOnly)

        if self.original_pixmap.save(buffer, "PNG"):
            return bytes(byte_array)

        return None

    def set_size_limits(self, max_width: int, max_height: int, min_height: int = 100):
        """Thiết lập giới hạn kích thước (adaptive mode)"""
        if self.mode != "adaptive":
            return

        self.max_width = max_width
        self.max_height = max_height
        self.min_height = min_height

        if self.current_pixmap:
            self._display_adaptive_image()

    def has_image(self) -> bool:
        """Kiểm tra có ảnh hay không"""
        return self.original_pixmap is not None and not self.original_pixmap.isNull()

    def get_image_info(self) -> dict:
        """Lấy thông tin ảnh"""
        if not self.original_pixmap:
            return {}

        size = self.original_pixmap.size()
        return {
            'width': size.width(),
            'height': size.height(),
            'zoom': self.current_zoom,
            'rotation': self.rotation_angle,
            'has_alpha': self.original_pixmap.hasAlphaChannel()
        }

    def set_auto_fullscreen(self, enabled: bool):
        """Thiết lập chế độ tự động fullscreen khi có ảnh"""
        self.auto_fullscreen = enabled