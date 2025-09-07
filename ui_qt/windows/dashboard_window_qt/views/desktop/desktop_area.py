# ui_qt/windows/dashboard_window_qt/views/desktop/desktop_area.py
"""
Desktop Area Container - Vùng làm việc chính của Dashboard
Quản lý wallpaper, desktop icons, widgets và drag-drop
"""

import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any
from datetime import datetime
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QMenu, QMessageBox, QFileDialog,
    QGraphicsOpacityEffect, QScrollArea
)
from PySide6.QtCore import (
    Qt, QPoint, QRect, QSize, QTimer,
    Signal, QPropertyAnimation, QEasingCurve,
    QMimeData, QUrl, QEvent
)
from PySide6.QtGui import (
    QPainter, QPixmap, QBrush, QPalette,
    QAction, QDragEnterEvent, QDropEvent,
    QContextMenuEvent, QPaintEvent, QResizeEvent,
    QMouseEvent, QKeyEvent, QWheelEvent,
    QLinearGradient, QColor, QFont, QPen,QLinearGradient,QBrush
)

# Import từ các modules khác
from ...utils.constants import (
    DESKTOP_MIN_WIDTH, DESKTOP_MIN_HEIGHT,
    DESKTOP_GRID_SIZE, DESKTOP_GRID_SPACING,
    DESKTOP_ICON_WIDTH, DESKTOP_ICON_HEIGHT,
    DESKTOP_ICON_SPACING, WALLPAPERS_DIR
)
from ...utils.assets import load_wallpaper, load_icon
from ...utils.helpers import (
    snap_to_grid, calculate_grid_layout,
    get_file_info, open_file_explorer
)

# Import repositories
from ...repositories.app_repository import AppRepository, AppModel
from ...repositories.settings_repository import SettingsRepository

# Logger
logger = logging.getLogger(__name__)


class DesktopArea(QWidget):
    """
    Container chính của Desktop Area
    Quản lý wallpaper, icons, widgets và các tương tác
    """

    # Signals
    icon_double_clicked = Signal(str)  # app_id hoặc file_path
    icon_selected = Signal(list)  # list các icon được chọn
    context_menu_requested = Signal(QPoint)  # vị trí menu
    file_dropped = Signal(list)  # list file paths
    wallpaper_changed = Signal(str)  # wallpaper path

    def __init__(self, parent=None):
        """
        Khởi tạo Desktop Area

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        # Repositories
        self.app_repo = AppRepository()
        self.settings_repo = SettingsRepository()

        # Desktop state
        self.wallpaper_path = ""
        self.wallpaper_pixmap = None
        self.wallpaper_mode = "fill"  # fill, fit, stretch, tile, center

        # Icons management
        self.desktop_icons = {}  # {id: DesktopIcon}
        self.selected_icons = []  # list các icon đang được chọn
        self.icon_positions = {}  # {id: QPoint}

        # Widgets management
        self.desktop_widgets = []  # list các widget trên desktop

        # Grid settings
        self.grid_enabled = True
        self.grid_size = DESKTOP_GRID_SIZE
        self.grid_spacing = DESKTOP_GRID_SPACING
        self.auto_arrange = False

        # Selection
        self.selection_start = None
        self.selection_rect = QRect()
        self.is_selecting = False

        # Drag & Drop
        self.drag_start_pos = None
        self.is_dragging = False

        # Animation
        self.animations = []

        # Setup UI
        self._setup_ui()
        self._load_settings()
        self._setup_connections()

    # ========== SETUP METHODS ==========

    def _setup_ui(self):
        """Setup giao diện cơ bản"""
        # Set minimum size
        self.setMinimumSize(DESKTOP_MIN_WIDTH, DESKTOP_MIN_HEIGHT)

        # Enable drag & drop
        self.setAcceptDrops(True)

        # Set background style
        self.setAutoFillBackground(True)

        # Focus policy
        self.setFocusPolicy(Qt.StrongFocus)

        # Context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)

        # Set object name for styling
        self.setObjectName("DesktopArea")

        # Create main layout (for widgets)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Create icon container (floating over wallpaper)
        self.icon_container = QWidget(self)
        self.icon_container.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.icon_container.setStyleSheet("background: transparent;")

        # Update stylesheet
        self._update_stylesheet()

    def _load_settings(self):
        """Load settings từ repository"""
        try:
            desktop_settings = self.settings_repo.get_desktop()

            # Load wallpaper
            self.set_wallpaper(
                desktop_settings.wallpaper_path,
                desktop_settings.wallpaper_mode
            )

            # Grid settings
            self.grid_enabled = desktop_settings.align_icons_to_grid
            self.auto_arrange = desktop_settings.auto_arrange_icons

            # Load icon positions
            self.icon_positions = self.settings_repo.get_desktop_icon_positions()
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            # Use defaults
            self.set_wallpaper("default")

    def _setup_connections(self):
        """Setup signal connections"""
        # Context menu
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _update_stylesheet(self):
        """Update stylesheet cho desktop"""
        self.setStyleSheet("""
            #DesktopArea {
                border: none;
            }
        """)
        # ĐÃ XÓA: background: transparent;
    # ========== WALLPAPER METHODS ==========

    def set_wallpaper(self, path: str, mode: str = "fill"):
        """
        Đặt wallpaper cho desktop

        Args:
            path: Đường dẫn wallpaper hoặc "default"
            mode: fill, fit, stretch, tile, center
        """
        try:
            # Load wallpaper
            self.wallpaper_pixmap = load_wallpaper(path)
            if not self.wallpaper_pixmap.isNull():
                self.wallpaper_pixmap = self.wallpaper_pixmap.scaled(
                    self.size(),
                    Qt.KeepAspectRatioByExpanding,
                    Qt.SmoothTransformation
                )
            self.wallpaper_path = path
            self.wallpaper_mode = mode

            # Force repaint
            self.update()

            # Emit signal
            self.wallpaper_changed.emit(path)

            # Save to settings
            self.settings_repo.set_wallpaper(path)

        except Exception as e:
            logger.error(f"Error setting wallpaper: {e}")
            # Create default gradient
            self._create_default_wallpaper()

    def _create_default_wallpaper(self):
        """Tạo wallpaper gradient mặc định"""
        size = self.size()
        if size.width() <= 0 or size.height() <= 0:
            size = QSize(1920, 1080)  # Size mặc định

        self.wallpaper_pixmap = QPixmap(size)

        painter = QPainter(self.wallpaper_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Windows 11 style gradient
        gradient = QLinearGradient(0, 0, size.width(), size.height())
        gradient.setColorAt(0.0, QColor(26, 42, 108))  # Xanh đậm
        gradient.setColorAt(0.5, QColor(178, 31, 102))  # Tím
        gradient.setColorAt(1.0, QColor(216, 162, 221))  # Hồng nhạt

        painter.fillRect(self.wallpaper_pixmap.rect(), QBrush(gradient))
        painter.end()

    def change_wallpaper(self):
        """Mở dialog chọn wallpaper"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn Wallpaper",
            str(WALLPAPERS_DIR),
            "Images (*.jpg *.jpeg *.png *.bmp *.gif)"
        )

        if file_path:
            self.set_wallpaper(file_path)

    # ========== PAINT METHODS ==========

    def paintEvent(self, event: QPaintEvent):
        """Vẽ wallpaper và các elements"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw wallpaper
        if self.wallpaper_pixmap:
            self._draw_wallpaper(painter)

        # Draw grid (if enabled and in design mode)
        if self.grid_enabled and hasattr(self, 'show_grid') and self.show_grid:
            self._draw_grid(painter)

        # Draw selection rectangle
        if self.is_selecting and not self.selection_rect.isNull():
            self._draw_selection_rect(painter)

    def _draw_wallpaper(self, painter: QPainter):
        """Vẽ wallpaper theo mode"""
        rect = self.rect()

        if self.wallpaper_mode == "fill":
            # Scale to fill (keep aspect ratio, crop if needed)
            scaled = self.wallpaper_pixmap.scaled(
                rect.size(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )
            # Center and draw
            x = (rect.width() - scaled.width()) // 2
            y = (rect.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)

        elif self.wallpaper_mode == "fit":
            # Scale to fit (keep aspect ratio, may have borders)
            scaled = self.wallpaper_pixmap.scaled(
                rect.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            # Center and draw
            x = (rect.width() - scaled.width()) // 2
            y = (rect.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)

        elif self.wallpaper_mode == "stretch":
            # Stretch to fill (ignore aspect ratio)
            painter.drawPixmap(rect, self.wallpaper_pixmap)

        elif self.wallpaper_mode == "tile":
            # Tile wallpaper
            for x in range(0, rect.width(), self.wallpaper_pixmap.width()):
                for y in range(0, rect.height(), self.wallpaper_pixmap.height()):
                    painter.drawPixmap(x, y, self.wallpaper_pixmap)

        elif self.wallpaper_mode == "center":
            # Center without scaling
            x = (rect.width() - self.wallpaper_pixmap.width()) // 2
            y = (rect.height() - self.wallpaper_pixmap.height()) // 2
            painter.drawPixmap(x, y, self.wallpaper_pixmap)

    def _draw_grid(self, painter: QPainter):
        """Vẽ lưới căn chỉnh"""
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1, Qt.DotLine))

        # Vertical lines
        for x in range(0, self.width(), self.grid_size):
            painter.drawLine(x, 0, x, self.height())

        # Horizontal lines
        for y in range(0, self.height(), self.grid_size):
            painter.drawLine(0, y, self.width(), y)

    def _draw_selection_rect(self, painter: QPainter):
        """Vẽ khung chọn"""
        # Draw border
        painter.setPen(QPen(QColor(0, 120, 215), 1))
        painter.setBrush(QBrush(QColor(0, 120, 215, 50)))
        painter.drawRect(self.selection_rect)

    # ========== ICON MANAGEMENT ==========

    def _load_desktop_icons(self):
        """Load desktop icons từ repository"""

        if hasattr(self, '_skip_auto_load_icons') and self._skip_auto_load_icons:
            return

        try:
            # Get pinned apps
            pinned_apps = self.app_repo.get_pinned_apps()

            # Add icons cho mỗi app
            for app in pinned_apps:
                self.add_desktop_icon(app)

        except Exception as e:
            logger.error(f"Lỗi load desktop icons: {e}")
    def add_desktop_icon(self, app: AppModel, position: QPoint = None):
        """
        Thêm icon app lên desktop

        Args:
            app: AppModel object
            position: Vị trí (None = auto)
        """
        try:
            try:
                from ..widgets.app_icon_widget import AppIconWidget
            except ImportError:
                logger.error("Không thể import AppIconWidget")
                return

            # Create icon widget với error handling
            icon_widget = AppIconWidget(
                app_id=app.id,
                name=app.display_name,
                icon=load_icon(app.icon_name, QSize(48, 48)) or load_icon("app", QSize(48, 48)),
                parent=self.icon_container
            )

            # Connect signals
            icon_widget.double_clicked.connect(
                lambda: self.icon_double_clicked.emit(app.id)
            )
            icon_widget.context_menu_requested.connect(
                lambda pos: self._show_icon_context_menu(app.id, pos)
            )

            # Set position
            if position:
                if self.grid_enabled:
                    position = snap_to_grid(position, self.grid_size)
            else:
                position = self._find_empty_position()

            icon_widget.move(position)
            icon_widget.show()

            # Store reference
            self.desktop_icons[app.id] = icon_widget
            self.icon_positions[app.id] = position


        except Exception as e:
            logger.error(f"Error adding desktop icon: {e}")

    def add_file_icon(self, file_path: str, position: QPoint = None):
        """
        Thêm icon file/folder lên desktop

        Args:
            file_path: Đường dẫn file
            position: Vị trí
        """
        try:
            from ..widgets.app_icon_widget import AppIconWidget

            file_info = get_file_info(file_path)
            if not file_info:
                return

            # Create icon widget
            icon_widget = AppIconWidget(
                app_id=file_path,  # Use path as ID
                name=file_info['name'],
                icon=load_icon("file", QSize(48, 48)),
                parent=self.icon_container
            )

            # Connect signals
            icon_widget.double_clicked.connect(
                lambda: self._open_file(file_path)
            )

            # Set position
            if not position:
                position = self._find_empty_position()
            elif self.grid_enabled:
                position = snap_to_grid(position, self.grid_size)

            icon_widget.move(position)
            icon_widget.show()

            # Store reference
            self.desktop_icons[file_path] = icon_widget
            self.icon_positions[file_path] = position

        except Exception as e:
            logger.error(f"Error adding file icon: {e}")

    def remove_desktop_icon(self, icon_id: str):
        """Xóa icon khỏi desktop"""
        if icon_id in self.desktop_icons:
            widget = self.desktop_icons[icon_id]
            widget.deleteLater()
            del self.desktop_icons[icon_id]

            if icon_id in self.icon_positions:
                del self.icon_positions[icon_id]

    def _find_empty_position(self) -> QPoint:
        """Tìm vị trí trống cho icon mới"""
        # Start from top-left
        x, y = self.grid_spacing, self.grid_spacing

        # Check each grid position
        while y < self.height() - DESKTOP_ICON_HEIGHT:
            while x < self.width() - DESKTOP_ICON_WIDTH:
                pos = QPoint(x, y)

                # Check if position is occupied
                occupied = False
                for existing_pos in self.icon_positions.values():
                    if (abs(existing_pos.x() - x) < DESKTOP_ICON_WIDTH and
                            abs(existing_pos.y() - y) < DESKTOP_ICON_HEIGHT):
                        occupied = True
                        break

                if not occupied:
                    return pos

                x += self.grid_size

            x = self.grid_spacing
            y += self.grid_size

        # Default position if no space
        return QPoint(self.grid_spacing, self.grid_spacing)

    def arrange_icons(self, sort_by: str = "name"):
        """
        Sắp xếp icons theo thứ tự

        Args:
            sort_by: name, type, date
        """
        if not self.desktop_icons:
            return

        # Sort icons
        icon_list = list(self.desktop_icons.items())

        if sort_by == "name":
            icon_list.sort(key=lambda x: x[1].name.lower())

        # Calculate grid
        cols = self.width() // self.grid_size

        # Arrange
        for index, (icon_id, widget) in enumerate(icon_list):
            row = index // cols
            col = index % cols

            x = self.grid_spacing + col * self.grid_size
            y = self.grid_spacing + row * self.grid_size

            new_pos = QPoint(x, y)

            # Animate movement
            self._animate_icon_move(widget, widget.pos(), new_pos)

            # Update position
            self.icon_positions[icon_id] = new_pos

        # Save positions
        self.save_icon_positions()

    def _animate_icon_move(self, widget: QWidget, start: QPoint, end: QPoint):
        """Animate icon movement"""
        animation = QPropertyAnimation(widget, b"pos")
        animation.setDuration(300)
        animation.setStartValue(start)
        animation.setEndValue(end)
        animation.setEasingCurve(QEasingCurve.InOutCubic)
        animation.start()

        # Store animation reference
        self.animations.append(animation)
        animation.finished.connect(lambda: self.animations.remove(animation))

    def save_icon_positions(self):
        """Lưu vị trí icons"""
        try:
            for icon_id, position in self.icon_positions.items():
                self.settings_repo.save_desktop_icon_position(
                    icon_id,
                    (position.x(), position.y())
                )
        except Exception as e:
            logger.error(f"Error saving icon positions: {e}")

    def restore_icon_positions(self):
        """Khôi phục vị trí icons đã lưu"""
        try:
            saved_positions = self.settings_repo.get_desktop_icon_positions()

            for icon_id, widget in self.desktop_icons.items():
                if icon_id in saved_positions:
                    x, y = saved_positions[icon_id]
                    widget.move(QPoint(x, y))
                    self.icon_positions[icon_id] = QPoint(x, y)

        except Exception as e:
            logger.error(f"Error restoring icon positions: {e}")

    # ========== MOUSE EVENTS ==========

    def mousePressEvent(self, event: QMouseEvent):
        """Xử lý mouse press"""
        if event.button() == Qt.LeftButton:
            # Clear selection
            self.clear_selection()

            # Start selection
            self.selection_start = event.pos()
            self.selection_rect = QRect(self.selection_start, QSize())
            self.is_selecting = True

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Xử lý mouse move"""
        if self.is_selecting and self.selection_start:
            # Update selection rectangle
            self.selection_rect = QRect(
                self.selection_start,
                event.pos()
            ).normalized()

            # Select icons in rectangle
            self._select_icons_in_rect(self.selection_rect)

            # Update display
            self.update()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Xử lý mouse release"""
        if event.button() == Qt.LeftButton:
            self.is_selecting = False
            self.selection_start = None
            self.selection_rect = QRect()
            self.update()

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Xử lý double click trên desktop"""
        # Check if clicked on empty area
        if not self.childAt(event.pos()):
            # Could open a launcher or do nothing
            pass

        super().mouseDoubleClickEvent(event)

    def _select_icons_in_rect(self, rect: QRect):
        """Chọn các icon trong vùng chọn"""
        self.selected_icons.clear()

        for icon_id, widget in self.desktop_icons.items():
            if rect.intersects(widget.geometry()):
                widget.set_selected(True)
                self.selected_icons.append(icon_id)
            else:
                widget.set_selected(False)

        self.icon_selected.emit(self.selected_icons)

    def clear_selection(self):
        """Xóa selection"""
        for widget in self.desktop_icons.values():
            if hasattr(widget, 'set_selected'):
                widget.set_selected(False)

        self.selected_icons.clear()

    # ========== KEYBOARD EVENTS ==========

    def keyPressEvent(self, event: QKeyEvent):
        """Xử lý keyboard events"""
        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key_F5:
            # Refresh desktop
            self.refresh_desktop()

        elif key == Qt.Key_Delete:
            # Delete selected icons
            if self.selected_icons:
                self._delete_selected_icons()

        elif key == Qt.Key_A and modifiers & Qt.ControlModifier:
            # Select all
            self.select_all_icons()

        elif key == Qt.Key_Escape:
            # Clear selection
            self.clear_selection()

        super().keyPressEvent(event)

    def select_all_icons(self):
        """Chọn tất cả icons"""
        self.selected_icons = list(self.desktop_icons.keys())

        for widget in self.desktop_icons.values():
            if hasattr(widget, 'set_selected'):
                widget.set_selected(True)

        self.icon_selected.emit(self.selected_icons)

    def _delete_selected_icons(self):
        """Xóa các icon đã chọn"""
        if not self.selected_icons:
            return

        reply = QMessageBox.question(
            self,
            "Xác nhận xóa",
            f"Xóa {len(self.selected_icons)} mục đã chọn khỏi desktop?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            for icon_id in self.selected_icons:
                self.remove_desktop_icon(icon_id)

            self.clear_selection()

    # ========== DRAG & DROP ==========

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Xử lý drag enter"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """Xử lý drag move"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Xử lý drop files"""
        if event.mimeData().hasUrls():
            file_paths = []

            for url in event.mimeData().urls():
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    file_paths.append(file_path)

                    # Add icon for dropped file
                    self.add_file_icon(file_path, event.pos())

            if file_paths:
                self.file_dropped.emit(file_paths)

            event.acceptProposedAction()
        else:
            event.ignore()

    # ========== CONTEXT MENU ==========

    def _show_context_menu(self, pos: QPoint):
        """Hiển thị context menu cho desktop"""
        from .desktop_context_menu import DesktopContextMenu
        from PySide6.QtGui import QAction

        # Tạo menu từ DesktopContextMenu (giữ nguyên menu cũ)
        menu = DesktopContextMenu(self)

        # THÊM menu đổi hình nền vào menu cũ
        menu.addSeparator()  # Thêm gạch ngang phân cách

        wallpaper_action = QAction("🖼️ Đổi hình nền...", self)
        wallpaper_action.triggered.connect(self.change_wallpaper)
        menu.addAction(wallpaper_action)

        # Kết nối các signal cũ (nếu có)
        menu.refresh_requested.connect(self.refresh_desktop)
        menu.new_folder_requested.connect(self._create_new_folder)

        # Hiển thị menu
        menu.exec(self.mapToGlobal(pos))
    def _show_icon_context_menu(self, icon_id: str, pos: QPoint):
        """Hiển thị context menu cho icon"""
        menu = QMenu(self)

        # Open action
        open_action = QAction(load_icon("open"), "Mở", self)
        open_action.triggered.connect(
            lambda: self.icon_double_clicked.emit(icon_id)
        )
        menu.addAction(open_action)

        menu.addSeparator()

        # Delete action
        delete_action = QAction(load_icon("delete"), "Xóa", self)
        delete_action.triggered.connect(
            lambda: self.remove_desktop_icon(icon_id)
        )
        menu.addAction(delete_action)

        # Properties action
        properties_action = QAction(load_icon("info"), "Thuộc tính", self)
        menu.addAction(properties_action)

        menu.exec(self.mapToGlobal(pos))

    # ========== PUBLIC METHODS ==========

    def refresh_desktop(self):
        """Refresh desktop - reload icons and wallpaper"""

        # Clear current icons
        for widget in self.desktop_icons.values():
            widget.deleteLater()

        self.desktop_icons.clear()
        self.selected_icons.clear()

        # Reload
        self._load_desktop_icons()
        self.update()

    def add_widget(self, widget: QWidget, position: QPoint = None):
        """
        Thêm widget lên desktop

        Args:
            widget: Widget cần thêm
            position: Vị trí
        """
        widget.setParent(self)

        if position:
            widget.move(position)
        else:
            # Center widget
            widget.move(
                (self.width() - widget.width()) // 2,
                (self.height() - widget.height()) // 2
            )

        widget.show()
        self.desktop_widgets.append(widget)

    def _create_new_folder(self):
        """Tạo folder mới trên desktop"""
        # Implementation for creating new folder
        pass

    def _open_file(self, file_path: str):
        """Mở file/folder"""
        try:
            if os.path.isdir(file_path):
                open_file_explorer(file_path)
            else:
                os.startfile(file_path)  # Windows
        except Exception as e:
            logger.error(f"Error opening file: {e}")

    # ========== RESIZE EVENT ==========

    def resizeEvent(self, event: QResizeEvent):
        """Xử lý resize"""
        super().resizeEvent(event)

        # Resize icon container
        if hasattr(self, 'icon_container'):
            self.icon_container.resize(self.size())

        # Reload wallpaper at new size
        if self.wallpaper_path:
            self.wallpaper_pixmap = load_wallpaper(
                self.wallpaper_path,
                self.size()
            )
            self.update()

    # ========== CLEANUP ==========

    def cleanup(self):
        """Cleanup resources"""
        # Save icon positions
        self.save_icon_positions()

        # Clear animations
        for animation in self.animations:
            animation.stop()
        self.animations.clear()

    # Phương thức tạo icon test khi có lỗi
    def _create_test_icon(self):
        """Tạo icon test để debug"""
        try:
            from ..widgets.app_icon_widget import AppIconWidget

            test_icon = AppIconWidget(
                app_id="test",
                name="Test App",
                icon=load_icon("app", QSize(48, 48)),
                parent=self.icon_container
            )
            test_icon.move(QPoint(50, 50))
            test_icon.show()

            self.desktop_icons["test"] = test_icon

        except Exception as e:
            logger.error(f"Không thể tạo test icon: {e}")

    # Tìm vị trí trống cho icon mới
    def _find_empty_position(self) -> QPoint:
        """Tìm vị trí trống cho icon mới"""
        start_x, start_y = 50, 50
        cols = 4  # Số cột
        spacing = 120  # Khoảng cách giữa icons

        for row in range(10):  # Tối đa 10 hàng
            for col in range(cols):
                x = start_x + col * spacing
                y = start_y + row * 100
                position = QPoint(x, y)

                # Kiểm tra vị trí có bị trùng không
                occupied = False
                for existing_pos in self.icon_positions.values():
                    if (abs(existing_pos.x() - x) < 80 and
                            abs(existing_pos.y() - y) < 80):
                        occupied = True
                        break

                if not occupied:
                    return position

        # Nếu không tìm được, trả về vị trí mặc định
        return QPoint(start_x, start_y)