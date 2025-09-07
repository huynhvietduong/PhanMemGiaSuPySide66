"""
Fullscreen Image Dialog - Dialog xem ảnh toàn màn hình
File: ui_qt/windows/question_bank/views/dialogs/fullscreen_image_dialog.py
"""

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QPixmap, QKeySequence, QShortcut, QPainter
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QToolBar, QScrollArea, QSlider, QApplication
)


class FullscreenImageDialog(QDialog):
    """Dialog xem ảnh fullscreen với đầy đủ tính năng zoom, pan"""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.original_pixmap = pixmap.copy() if pixmap else None
        self.current_zoom = 1.0
        self.min_zoom = 0.05  # Giảm từ 0.1 xuống 0.05 cho zoom mượt hơn
        self.max_zoom = 10.0
        self.zoom_step = 0.05  # Giảm từ 0.2 xuống 0.05 cho zoom mượt hơn
        self.pan_offset = QPoint(0, 0)
        self.last_pan_point = QPoint()
        self.is_panning = False
        self.rotation_angle = 0
        self.cursor_visible = True

        self._setup_window()
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_cursor_timer()

        # Hiển thị ảnh ban đầu và tự động fit
        if self.original_pixmap:
            self._update_image_display()
            # Tự động fit ngay lập tức thay vì delay 100ms
            QTimer.singleShot(50, self._fit_to_window)
            # Thêm một lần fit nữa sau khi cửa sổ đã hoàn toàn hiển thị
            QTimer.singleShot(200, self._fit_to_window)

    def _setup_window(self):
        """Thiết lập cửa sổ maximize (toàn màn hình với title bar)"""
        self.setWindowTitle("🖼️ Xem ảnh toàn màn hình - Nhấn ESC để thoát")

        # Thuộc tính window
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        # Style cho maximize window
        self.setStyleSheet("""
            QDialog {
                background-color: #000000;
                border: none;
            }
        """)

        # Hiển thị maximize thay vì fullscreen
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint |
            Qt.WindowSystemMenuHint |
            Qt.WindowTitleHint |
            Qt.CustomizeWindowHint
        )

    def _setup_ui(self):
        """Thiết lập giao diện"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar (ban đầu ẩn)
        self._create_toolbar(layout)

        # Main image area
        self._create_image_area(layout)

        # Status bar
        self._create_status_bar(layout)

    def _create_toolbar(self, layout: QVBoxLayout):
        """Tạo toolbar với controls"""
        self.toolbar = QToolBar()
        self.toolbar.setStyleSheet("""
            QToolBar {
                background: rgba(0, 0, 0, 200);
                border: none;
                color: white;
                padding: 8px;
                spacing: 5px;
            }
            QToolBar QPushButton {
                background: rgba(255, 255, 255, 100);
                color: white;
                border: 1px solid rgba(255, 255, 255, 150);
                border-radius: 6px;
                padding: 8px 16px;
                margin: 2px;
                font-weight: bold;
            }
            QToolBar QPushButton:hover {
                background: rgba(255, 255, 255, 180);
            }
            QToolBar QPushButton:pressed {
                background: rgba(255, 255, 255, 220);
            }
            QToolBar QSlider::groove:horizontal {
                background: rgba(255, 255, 255, 100);
                height: 8px;
                border-radius: 4px;
            }
            QToolBar QSlider::handle:horizontal {
                background: rgba(255, 255, 255, 200);
                border: 1px solid rgba(255, 255, 255, 100);
                width: 18px;
                border-radius: 9px;
                margin: -5px 0;
            }
        """)

        # Zoom controls
        zoom_out_btn = QPushButton("🔍- Thu nhỏ")
        zoom_out_btn.clicked.connect(self.zoom_out)
        self.toolbar.addWidget(zoom_out_btn)

        # Zoom slider
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setMinimum(int(self.min_zoom * 100))
        self.zoom_slider.setMaximum(int(self.max_zoom * 100))
        self.zoom_slider.setValue(int(self.current_zoom * 100))
        self.zoom_slider.setMinimumWidth(200)
        self.zoom_slider.setMaximumWidth(300)
        self.zoom_slider.valueChanged.connect(self._on_zoom_slider_changed)
        self.toolbar.addWidget(self.zoom_slider)

        # Zoom label
        self.zoom_label = QLabel("100%")
        self.zoom_label.setStyleSheet("color: white; font-weight: bold; min-width: 60px;")
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.toolbar.addWidget(self.zoom_label)

        zoom_in_btn = QPushButton("🔍+ Phóng to")
        zoom_in_btn.clicked.connect(self.zoom_in)
        self.toolbar.addWidget(zoom_in_btn)

        self.toolbar.addSeparator()

        # Fit controls
        fit_window_btn = QPushButton("📐 Vừa màn hình")
        fit_window_btn.clicked.connect(self._fit_to_window)
        self.toolbar.addWidget(fit_window_btn)

        actual_size_btn = QPushButton("🔢 Kích thước gốc")
        actual_size_btn.clicked.connect(self._actual_size)
        self.toolbar.addWidget(actual_size_btn)

        self.toolbar.addSeparator()

        # Rotate controls
        rotate_left_btn = QPushButton("↺ Xoay trái")
        rotate_left_btn.clicked.connect(self._rotate_left)
        self.toolbar.addWidget(rotate_left_btn)

        rotate_right_btn = QPushButton("↻ Xoay phải")
        rotate_right_btn.clicked.connect(self._rotate_right)
        self.toolbar.addWidget(rotate_right_btn)

        self.toolbar.addSeparator()

        # Toggle controls
        toggle_toolbar_btn = QPushButton("🔧 Ẩn Toolbar")
        toggle_toolbar_btn.clicked.connect(self._toggle_toolbar)
        self.toolbar.addWidget(toggle_toolbar_btn)

        # Close button
        close_btn = QPushButton("❌ Đóng")
        close_btn.clicked.connect(self.close)
        self.toolbar.addWidget(close_btn)

        # Ban đầu hiển thị toolbar
        layout.addWidget(self.toolbar)
        self.toolbar_visible = True

    def _create_image_area(self, layout: QVBoxLayout):
        """Tạo khu vực hiển thị ảnh"""
        # Scroll area với style tối ưu
        self.scroll_area = QScrollArea()
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: #000000;
                border: none;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                background: rgba(255, 255, 255, 50);
                width: 12px;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: rgba(255, 255, 255, 150);
                border-radius: 6px;
                min-height: 20px;
                min-width: 20px;
            }
            QScrollBar::handle:hover {
                background: rgba(255, 255, 255, 200);
            }
        """)

        # Image label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background: transparent; border: none;")
        self.image_label.setMinimumSize(100, 100)

        # Mouse events cho pan - sử dụng cả left và right button
        self.image_label.mousePressEvent = self._mouse_press_event
        self.image_label.mouseMoveEvent = self._mouse_move_event
        self.image_label.mouseReleaseEvent = self._mouse_release_event
        self.image_label.mouseDoubleClickEvent = self._mouse_double_click_event

        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setWidgetResizable(True)

        # Wheel event cho zoom
        self.scroll_area.wheelEvent = self._wheel_event

        layout.addWidget(self.scroll_area)

    def _create_status_bar(self, layout: QVBoxLayout):
        """Tạo status bar"""
        status_widget = QtWidgets.QWidget()
        status_widget.setFixedHeight(35)
        status_widget.setStyleSheet("""
            QWidget {
                background: rgba(0, 0, 0, 200);
                color: white;
                padding: 8px;
            }
            QLabel {
                color: white;
            }
        """)

        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(15, 5, 15, 5)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        # Help với các phím tắt
        help_label = QLabel("💡 ESC: Đóng | T: Ẩn/hiện toolbar | Ctrl+Wheel: Zoom | Drag: Di chuyển | Double-click: Đóng")
        help_label.setStyleSheet("color: #cccccc; font-size: 11px;")
        status_layout.addWidget(help_label)

        layout.addWidget(status_widget)

    def _setup_shortcuts(self):
        """Thiết lập phím tắt"""
        shortcuts = [
            (QKeySequence("Escape"), self.close),
            (QKeySequence("Ctrl+Plus"), self.zoom_in),
            (QKeySequence("Ctrl+Equal"), self.zoom_in),  # Thêm = key
            (QKeySequence("Ctrl+Minus"), self.zoom_out),
            (QKeySequence("Ctrl+0"), self._fit_to_window),
            (QKeySequence("Ctrl+1"), self._actual_size),
            (QKeySequence("Ctrl+Left"), self._rotate_left),
            (QKeySequence("Ctrl+Right"), self._rotate_right),
            (QKeySequence("T"), self._toggle_toolbar),
            (QKeySequence("Space"), self._toggle_toolbar),
        ]

        for key_seq, slot in shortcuts:
            QShortcut(key_seq, self, slot)

    def _setup_cursor_timer(self):
        """Thiết lập timer để tự động ẩn cursor"""
        self.cursor_timer = QTimer()
        self.cursor_timer.timeout.connect(self._hide_cursor)
        self.cursor_timer.setSingleShot(True)

    def _hide_cursor(self):
        """Ẩn cursor"""
        if self.cursor_visible:
            self.setCursor(Qt.BlankCursor)
            self.cursor_visible = False

    def _show_cursor(self):
        """Hiện cursor và khởi động lại timer"""
        if not self.cursor_visible:
            self.setCursor(Qt.ArrowCursor)
            self.cursor_visible = True

        # Khởi động lại timer 3 giây
        self.cursor_timer.stop()
        self.cursor_timer.start(3000)

    def _update_image_display(self):
        """Cập nhật hiển thị ảnh"""
        if not self.original_pixmap:
            self.image_label.setText("❌ Không có ảnh để hiển thị")
            return

        # Apply rotation
        pixmap = self.original_pixmap
        if self.rotation_angle != 0:
            transform = QtGui.QTransform()
            transform.rotate(self.rotation_angle)
            pixmap = pixmap.transformed(transform, Qt.SmoothTransformation)

        # Apply zoom
        if self.current_zoom != 1.0:
            size = pixmap.size() * self.current_zoom
            pixmap = pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        self.image_label.setPixmap(pixmap)
        self.image_label.resize(pixmap.size())

        # Update controls
        self._update_zoom_controls()
        self._update_status()

    def _update_zoom_controls(self):
        """Cập nhật controls zoom"""
        zoom_percent = int(self.current_zoom * 100)
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(zoom_percent)
        self.zoom_slider.blockSignals(False)
        self.zoom_label.setText(f"{zoom_percent}%")

    def _update_status(self):
        """Cập nhật status bar"""
        if self.original_pixmap:
            size = self.original_pixmap.size()
            zoom_percent = int(self.current_zoom * 100)
            rotation = self.rotation_angle % 360
            self.status_label.setText(
                f"📏 {size.width()}×{size.height()}px | "
                f"🔍 {zoom_percent}% | "
                f"↻ {rotation}°"
            )

    def _fit_to_window(self):
        """Fit ảnh vào cửa sổ"""
        if not self.original_pixmap:
            return

        # Đảm bảo scroll area đã được render hoàn toàn
        self.scroll_area.updateGeometry()
        QApplication.processEvents()

        # Get available space (trừ toolbar và status bar)
        available_size = self.scroll_area.viewport().size()

        # Kiểm tra nếu available_size chưa hợp lệ
        if available_size.width() <= 0 or available_size.height() <= 0:
            # Retry sau một chút
            QTimer.singleShot(100, self._fit_to_window)
            return

        # Get image size sau rotation
        if self.rotation_angle % 180 == 0:
            image_size = self.original_pixmap.size()
        else:
            image_size = QtCore.QSize(
                self.original_pixmap.height(),
                self.original_pixmap.width()
            )

        # Calculate scale to fit với margin lớn hơn để rõ ràng
        if image_size.width() > 0 and image_size.height() > 0:
            scale_x = available_size.width() / image_size.width()
            scale_y = available_size.height() / image_size.height()
            scale = min(scale_x, scale_y) * 0.9  # 90% để có margin rõ ràng

            # Đảm bảo zoom tối thiểu nhưng ưu tiên fit
            self.current_zoom = max(scale, self.min_zoom)

            # Force update ngay lập tức
            self._update_image_display()

            # Log để debug
            print(f"Fit to window: available={available_size}, image={image_size}, scale={scale:.2f}, zoom={self.current_zoom:.2f}")

    def _actual_size(self):
        """Hiển thị ảnh ở kích thước gốc"""
        self.current_zoom = 1.0
        self._update_image_display()

    def _toggle_toolbar(self):
        """Toggle hiển thị toolbar"""
        if self.toolbar_visible:
            self.toolbar.hide()
            self.toolbar_visible = False
        else:
            self.toolbar.show()
            self.toolbar_visible = True

    def zoom_in(self):
        """Phóng to ảnh"""
        new_zoom = min(self.current_zoom + self.zoom_step, self.max_zoom)
        if new_zoom != self.current_zoom:
            self.current_zoom = new_zoom
            self._update_image_display()

    def zoom_out(self):
        """Thu nhỏ ảnh"""
        new_zoom = max(self.current_zoom - self.zoom_step, self.min_zoom)
        if new_zoom != self.current_zoom:
            self.current_zoom = new_zoom
            self._update_image_display()

    def _rotate_left(self):
        """Xoay ảnh sang trái 90 độ"""
        self.rotation_angle = (self.rotation_angle - 90) % 360
        self._update_image_display()

    def _rotate_right(self):
        """Xoay ảnh sang phải 90 độ"""
        self.rotation_angle = (self.rotation_angle + 90) % 360
        self._update_image_display()

    def _on_zoom_slider_changed(self, value):
        """Xử lý thay đổi zoom slider"""
        new_zoom = value / 100.0
        if abs(new_zoom - self.current_zoom) > 0.01:
            self.current_zoom = new_zoom
            self.zoom_label.setText(f"{value}%")
            # Chỉ update image, không update slider để tránh vòng lặp
            self._update_image_display_without_controls()

    def _update_image_display_without_controls(self):
        """Update ảnh mà không update controls (tránh vòng lặp)"""
        if not self.original_pixmap:
            return

        pixmap = self.original_pixmap
        if self.rotation_angle != 0:
            transform = QtGui.QTransform()
            transform.rotate(self.rotation_angle)
            pixmap = pixmap.transformed(transform, Qt.SmoothTransformation)

        if self.current_zoom != 1.0:
            size = pixmap.size() * self.current_zoom
            pixmap = pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        self.image_label.setPixmap(pixmap)
        self.image_label.resize(pixmap.size())
        self._update_status()

    # ========== MOUSE EVENTS ==========

    def _mouse_press_event(self, event):
        """Mouse press event - hỗ trợ cả left và right button"""
        if event.button() in (Qt.LeftButton, Qt.RightButton):
            self.is_panning = True
            self.last_pan_point = event.pos()
            self.image_label.setCursor(Qt.ClosedHandCursor)
            self._show_cursor()

    def _mouse_move_event(self, event):
        """Mouse move event"""
        self._show_cursor()

        if self.is_panning and event.buttons() in (Qt.LeftButton, Qt.RightButton):
            delta = event.pos() - self.last_pan_point
            h_bar = self.scroll_area.horizontalScrollBar()
            v_bar = self.scroll_area.verticalScrollBar()

            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())

            self.last_pan_point = event.pos()

    def _mouse_release_event(self, event):
        """Mouse release event"""
        if event.button() in (Qt.LeftButton, Qt.RightButton):
            self.is_panning = False
            self.image_label.setCursor(Qt.ArrowCursor)

    def _mouse_double_click_event(self, event):
        """Double click để thoát"""
        if event.button() == Qt.LeftButton:
            self.close()

    def _wheel_event(self, event):
        """Wheel event cho zoom"""
        self._show_cursor()

        delta = event.angleDelta().y()
        if event.modifiers() & Qt.ControlModifier:
            # Zoom với Ctrl + Wheel
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            # Zoom không cần Ctrl (tiện hơn)
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()

    # ========== EVENT HANDLERS ==========

    def showEvent(self, event):
        """Xử lý khi hiển thị dialog"""
        super().showEvent(event)
        # Đảm bảo maximize state thay vì fullscreen
        self.setWindowState(Qt.WindowMaximized)

        # Tự động fit ảnh sau khi cửa sổ hiển thị
        if self.original_pixmap:
            QTimer.singleShot(100, self._fit_to_window)
            QTimer.singleShot(300, self._fit_to_window)  # Fit lần nữa để đảm bảo

    def keyPressEvent(self, event):
        """Xử lý sự kiện nhấn phím"""
        key = event.key()

        if key == Qt.Key_Escape:
            self.close()
        elif key == Qt.Key_T:
            self._toggle_toolbar()
        elif key == Qt.Key_Space:
            self._toggle_toolbar()
        elif key in (Qt.Key_Plus, Qt.Key_Equal):
            if event.modifiers() & Qt.ControlModifier:
                self.zoom_in()
        elif key == Qt.Key_Minus:
            if event.modifiers() & Qt.ControlModifier:
                self.zoom_out()
        elif key == Qt.Key_0:
            if event.modifiers() & Qt.ControlModifier:
                self._fit_to_window()
        elif key == Qt.Key_1:
            if event.modifiers() & Qt.ControlModifier:
                self._actual_size()
        else:
            super().keyPressEvent(event)

    def mouseMoveEvent(self, event):
        """Khi di chuyển chuột"""
        super().mouseMoveEvent(event)
        self._show_cursor()

    def closeEvent(self, event):
        """Xử lý khi đóng dialog"""
        # Dọn dẹp timers
        if hasattr(self, 'cursor_timer') and self.cursor_timer:
            self.cursor_timer.stop()

        super().closeEvent(event)

    # ========== STATIC METHODS ==========

    @staticmethod
    def show_fullscreen_image(pixmap: QPixmap, parent=None):
        """Static method để hiển thị ảnh fullscreen"""
        if not pixmap or pixmap.isNull():
            return None

        dialog = FullscreenImageDialog(pixmap, parent)
        dialog.showFullScreen()
        return dialog


# ========== USAGE EXAMPLE ==========

if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    # Tạo pixmap test
    pixmap = QPixmap(800, 600)
    pixmap.fill(Qt.blue)

    # Vẽ text test
    painter = QPainter(pixmap)
    painter.setPen(QtGui.QColor(255, 255, 255))
    painter.setFont(QtGui.QFont("Arial", 48))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "Test Fullscreen\nImage Dialog")
    painter.end()

    # Hiển thị maximize
    dialog = FullscreenImageDialog.show_maximized_image(pixmap)

    app.exec()