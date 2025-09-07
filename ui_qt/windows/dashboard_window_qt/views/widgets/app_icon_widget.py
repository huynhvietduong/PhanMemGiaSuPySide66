# ui_qt/windows/dashboard_window_qt/views/widgets/app_icon_widget.py
"""
App Icon Widget - Desktop shortcut icon
Widget hiển thị icon của app/file trên desktop với double-click, rename, drag & drop
"""

import os
from pathlib import Path
from typing import Optional, Union
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit,
    QGraphicsDropShadowEffect, QToolTip, QMenu,
    QApplication, QStyle
)
from PySide6.QtCore import (
    Qt, QSize, QPoint, QRect, QTimer,
    Signal, QPropertyAnimation, QEasingCurve,
    QMimeData, Property, QEvent, QObject
)
from PySide6.QtGui import (
    QPainter, QPixmap, QIcon, QFont, QColor,
    QPen, QBrush, QAction, QPalette,
    QMouseEvent, QKeyEvent, QPaintEvent,
    QFocusEvent, QContextMenuEvent,
    QEnterEvent, QDragEnterEvent, QDrag, QCursor
)

# Logger
logger = logging.getLogger(__name__)


class AppIconWidget(QWidget):
    """
    Desktop Icon Widget - Hiển thị icon app/file trên desktop

    Features:
    - Double-click to open
    - Single-click to select
    - F2 to rename
    - Drag to move
    - Right-click context menu
    - Hover effects
    """

    # Signals
    double_clicked = Signal()  # Double-click để mở
    clicked = Signal()  # Single click
    renamed = Signal(str)  # Đổi tên xong
    context_menu_requested = Signal(QPoint)  # Right-click menu
    drag_started = Signal()  # Bắt đầu drag
    selection_changed = Signal(bool)  # Selection state changed

    def __init__(
            self,
            app_id: str,
            name: str,
            icon: Union[QIcon, QPixmap, str] = None,
            parent: QWidget = None
    ):
        """
        Khởi tạo Desktop Icon

        Args:
            app_id: ID của app hoặc path của file
            name: Tên hiển thị
            icon: Icon (QIcon, QPixmap hoặc path)
            parent: Parent widget
        """
        super().__init__(parent)

        # Properties
        self.app_id = app_id
        self.name = name
        self.original_name = name

        # Icon
        self.icon = self._process_icon(icon)
        self.icon_size = QSize(48, 48)  # Default icon size

        # State
        self.is_selected = False
        self.is_hovered = False
        self.is_pressed = False
        self.is_renaming = False
        self.is_dragging = False

        # Drag
        self.drag_start_pos = None

        # Animation
        self._opacity = 1.0
        self.hover_animation = None
        self.press_animation = None

        # Setup
        self._setup_ui()
        self._setup_effects()
        self._setup_animations()

        # Install event filter for tooltip
        self.installEventFilter(self)

        logger.debug(f"Icon widget created: {name}")

    # ========== SETUP METHODS ==========

    def _setup_ui(self):
        """Setup UI components"""
        # Set fixed size for icon widget
        self.setFixedSize(75, 90)  # Width x Height

        # Transparent background
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAutoFillBackground(False)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignCenter)

        # Icon label (using custom paint instead)
        # We'll paint the icon directly

        # Text label
        self.text_label = QLabel(self.name, self)
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setWordWrap(True)
        self.text_label.setMaximumHeight(30)

        # Text style
        font = QFont("Segoe UI", 9)
        self.text_label.setFont(font)

        # Text color (white with shadow for desktop)
        self.text_label.setStyleSheet("""
            QLabel {
                color: white;
                background: transparent;
                padding: 2px;
            }
        """)

        # Text editor for rename (hidden by default)
        self.text_editor = QLineEdit(self.name, self)
        self.text_editor.setAlignment(Qt.AlignCenter)
        self.text_editor.hide()
        self.text_editor.editingFinished.connect(self._finish_rename)
        self.text_editor.installEventFilter(self)

        # Position elements manually since we're painting
        self.text_label.move(0, 55)
        self.text_label.resize(75, 30)
        self.text_editor.move(0, 55)
        self.text_editor.resize(75, 20)

        # Focus policy
        self.setFocusPolicy(Qt.StrongFocus)

        # Cursor
        self.setCursor(Qt.PointingHandCursor)

        # Object name for styling
        self.setObjectName("DesktopIcon")

    def _setup_effects(self):
        """Setup visual effects"""
        # Text shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(2)
        shadow.setOffset(1, 1)
        shadow.setColor(QColor(0, 0, 0, 128))
        self.text_label.setGraphicsEffect(shadow)

    def _setup_animations(self):
        """Setup animations"""
        # Hover animation
        self.hover_animation = QPropertyAnimation(self, b"opacity")
        self.hover_animation.setDuration(150)
        self.hover_animation.setEasingCurve(QEasingCurve.InOutQuad)

        # Press animation
        self.press_animation = QPropertyAnimation(self, b"iconScale")
        self.press_animation.setDuration(100)
        self.press_animation.setEasingCurve(QEasingCurve.OutQuad)

    def _process_icon(self, icon: Union[QIcon, QPixmap, str]) -> QIcon:
        """Process icon input to QIcon"""
        if isinstance(icon, QIcon):
            return icon
        elif isinstance(icon, QPixmap):
            return QIcon(icon)
        elif isinstance(icon, str):
            if os.path.exists(icon):
                return QIcon(icon)
            else:
                # Try to load from theme
                return QIcon.fromTheme(icon)
        else:
            # Default icon
            return self.style().standardIcon(QStyle.SP_FileIcon)

    # ========== PROPERTIES ==========

    def get_opacity(self) -> float:
        """Get current opacity"""
        return self._opacity

    def set_opacity(self, value: float):
        """Set opacity with update"""
        self._opacity = value
        self.update()

    opacity = Property(float, get_opacity, set_opacity)

    @property
    def icon_scale(self) -> float:
        """Get icon scale for animation"""
        return getattr(self, '_icon_scale', 1.0)

    @icon_scale.setter
    def icon_scale(self, value: float):
        """Set icon scale for animation"""
        self._icon_scale = value
        self.update()

    # ========== PAINT METHODS ==========

    def paintEvent(self, event: QPaintEvent):
        """Custom paint for icon and selection"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Apply opacity
        painter.setOpacity(self._opacity)

        # Draw selection background
        if self.is_selected:
            self._draw_selection(painter)
        elif self.is_hovered:
            self._draw_hover(painter)

        # Draw icon
        self._draw_icon(painter)

        # Draw badge (if any)
        # self._draw_badge(painter)

    def _draw_selection(self, painter: QPainter):
        """Draw selection highlight"""
        # Selection rectangle
        rect = QRect(5, 5, 65, 50)

        # Windows-style selection
        painter.setPen(QPen(QColor(0, 120, 215), 1))
        painter.setBrush(QBrush(QColor(0, 120, 215, 100)))
        painter.drawRoundedRect(rect, 3, 3)

    def _draw_hover(self, painter: QPainter):
        """Draw hover effect"""
        # Hover rectangle
        rect = QRect(5, 5, 65, 50)

        # Subtle hover effect
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 30)))
        painter.drawRoundedRect(rect, 3, 3)

    def _draw_icon(self, painter: QPainter):
        """Draw the icon"""
        # Icon rectangle (centered)
        icon_rect = QRect(
            (self.width() - self.icon_size.width()) // 2,
            5,
            self.icon_size.width(),
            self.icon_size.height()
        )

        # Apply scale for animation
        if hasattr(self, '_icon_scale') and self._icon_scale != 1.0:
            painter.save()
            center = icon_rect.center()
            painter.translate(center)
            painter.scale(self._icon_scale, self._icon_scale)
            painter.translate(-center)

        # Draw icon
        if self.icon:
            pixmap = self.icon.pixmap(self.icon_size)

            # Apply effects if selected/pressed
            if self.is_pressed:
                # Darken when pressed
                temp_pixmap = QPixmap(pixmap.size())
                temp_pixmap.fill(Qt.transparent)
                temp_painter = QPainter(temp_pixmap)
                temp_painter.setOpacity(0.8)
                temp_painter.drawPixmap(0, 0, pixmap)
                temp_painter.end()
                pixmap = temp_pixmap

            painter.drawPixmap(icon_rect, pixmap)

        if hasattr(self, '_icon_scale') and self._icon_scale != 1.0:
            painter.restore()

    def _draw_badge(self, painter: QPainter):
        """Draw notification badge (if needed)"""
        # Example: Draw a red circle with number
        # This could be used for notification count
        pass

    # ========== MOUSE EVENTS ==========

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press"""
        if event.button() == Qt.LeftButton:
            self.is_pressed = True
            self.drag_start_pos = event.pos()

            # Animate press
            if self.press_animation:
                self.press_animation.setStartValue(1.0)
                self.press_animation.setEndValue(0.95)
                self.press_animation.start()

            self.update()

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move - start drag if needed"""
        if event.buttons() & Qt.LeftButton and self.drag_start_pos:
            # Check if we should start dragging
            if (event.pos() - self.drag_start_pos).manhattanLength() >= \
                    QApplication.startDragDistance():
                self._start_drag()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release"""
        if event.button() == Qt.LeftButton:
            was_pressed = self.is_pressed
            self.is_pressed = False

            # Animate release
            if self.press_animation:
                self.press_animation.setStartValue(0.95)
                self.press_animation.setEndValue(1.0)
                self.press_animation.start()

            # Check for click (not drag)
            if was_pressed and not self.is_dragging:
                if self.rect().contains(event.pos()):
                    self.clicked.emit()

                    # Toggle selection
                    modifiers = QApplication.keyboardModifiers()
                    if modifiers & Qt.ControlModifier:
                        # Ctrl+Click: toggle selection
                        self.set_selected(not self.is_selected)
                    else:
                        # Normal click: select only this
                        if self.parent():
                            # Clear other selections
                            for child in self.parent().children():
                                if isinstance(child, AppIconWidget) and child != self:
                                    child.set_selected(False)
                        self.set_selected(True)

            self.is_dragging = False
            self.drag_start_pos = None
            self.update()

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Handle double-click"""
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()

        super().mouseDoubleClickEvent(event)

    def _show_tooltip(self):
        """Show tooltip với text"""
        if self.is_hovered:  # Chỉ show nếu vẫn đang hover
            QToolTip.showText(QCursor.pos(), self.name, self)
    def enterEvent(self, event: QEnterEvent):
        """Handle mouse enter"""
        self.is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Handle mouse leave"""
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)

    # ========== KEYBOARD EVENTS ==========

    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press"""
        key = event.key()

        if key == Qt.Key_F2:
            # Start rename
            self.start_rename()

        elif key == Qt.Key_Delete:
            # Could emit delete signal
            pass

        elif key == Qt.Key_Return or key == Qt.Key_Enter:
            # Open on Enter
            if not self.is_renaming:
                self.double_clicked.emit()

        super().keyPressEvent(event)

    # ========== CONTEXT MENU ==========

    def contextMenuEvent(self, event: QContextMenuEvent):
        """Handle right-click"""
        self.context_menu_requested.emit(event.pos())
        # Don't call super to prevent propagation

    # ========== DRAG & DROP ==========

    def _start_drag(self):
        """Start dragging the icon"""
        if not self.app_id:
            return

        self.is_dragging = True
        self.drag_started.emit()

        # Create drag object
        drag = QDrag(self)

        # Set mime data
        mime_data = QMimeData()
        mime_data.setText(self.app_id)
        drag.setMimeData(mime_data)

        # Set drag pixmap
        pixmap = QPixmap(self.size())
        pixmap.fill(Qt.transparent)
        self.render(pixmap)
        drag.setPixmap(pixmap)
        drag.setHotSpot(self.drag_start_pos)

        # Execute drag
        drag.exec(Qt.MoveAction)

    # ========== RENAME METHODS ==========

    def start_rename(self):
        """Start renaming mode"""
        if self.is_renaming:
            return

        self.is_renaming = True

        # Show editor
        self.text_editor.setText(self.name)
        self.text_editor.selectAll()
        self.text_editor.show()
        self.text_editor.setFocus()

        # Hide label
        self.text_label.hide()

        logger.debug(f"Start renaming: {self.name}")

    def _finish_rename(self):
        """Finish renaming"""
        if not self.is_renaming:
            return

        new_name = self.text_editor.text().strip()

        if new_name and new_name != self.name:
            old_name = self.name
            self.name = new_name
            self.text_label.setText(new_name)
            self.renamed.emit(new_name)
            logger.info(f"Renamed: {old_name} -> {new_name}")

        # Hide editor, show label
        self.text_editor.hide()
        self.text_label.show()
        self.is_renaming = False

    def cancel_rename(self):
        """Cancel renaming"""
        if self.is_renaming:
            self.text_editor.setText(self.name)
            self._finish_rename()

    # ========== EVENT FILTER ==========

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Event filter for text editor"""
        if obj == self.text_editor:
            if event.type() == QEvent.KeyPress:
                key = event.key()
                if key == Qt.Key_Escape:
                    # Cancel rename on Escape
                    self.cancel_rename()
                    return True

        return super().eventFilter(obj, event)

    # ========== PUBLIC METHODS ==========

    def set_selected(self, selected: bool):
        """Set selection state"""
        if self.is_selected != selected:
            self.is_selected = selected
            self.selection_changed.emit(selected)
            self.update()

            # Update text color based on selection
            if selected:
                self.text_label.setStyleSheet("""
                    QLabel {
                        color: white;
                        background: rgba(0, 120, 215, 100);
                        padding: 2px;
                        border-radius: 2px;
                    }
                """)
            else:
                self.text_label.setStyleSheet("""
                    QLabel {
                        color: white;
                        background: transparent;
                        padding: 2px;
                    }
                """)

    def set_icon(self, icon: Union[QIcon, QPixmap, str]):
        """Change icon"""
        self.icon = self._process_icon(icon)
        self.update()

    def set_icon_size(self, size: QSize):
        """Set icon size"""
        self.icon_size = size
        self.update()

    def set_name(self, name: str):
        """Set display name"""
        self.name = name
        self.text_label.setText(name)
        self.text_editor.setText(name)

    def get_name(self) -> str:
        """Get display name"""
        return self.name

    def _show_tooltip(self):
        """Show tooltip if still hovering"""
        if self.is_hovered and not self.is_renaming:
            # Show full name as tooltip if truncated
            if self.text_label.text() != self.name or len(self.name) > 10:
                QToolTip.showText(
                    self.mapToGlobal(QPoint(self.width() // 2, 0)),
                    self.name,
                    self
                )

    def animate_click(self):
        """Animate click effect"""
        if self.press_animation:
            self.press_animation.setStartValue(1.0)
            self.press_animation.setEndValue(0.9)
            self.press_animation.start()

            QTimer.singleShot(100, lambda: self.press_animation.setDirection(
                QPropertyAnimation.Backward
            ))

    def flash(self, count: int = 3):
        """Flash the icon for attention"""

        def toggle_opacity():
            self.set_opacity(0.5 if self._opacity == 1.0 else 1.0)

        for i in range(count * 2):
            QTimer.singleShot(i * 150, toggle_opacity)

        # Ensure we end with full opacity
        QTimer.singleShot(count * 300, lambda: self.set_opacity(1.0))


class FileIconWidget(AppIconWidget):
    """
    Specialized icon widget for files/folders
    Extends AppIconWidget with file-specific features
    """

    def __init__(
            self,
            file_path: str,
            parent: QWidget = None
    ):
        """
        Initialize file icon

        Args:
            file_path: Path to file/folder
            parent: Parent widget
        """
        # Get file info
        path = Path(file_path)
        name = path.name

        # Get appropriate icon
        if path.is_dir():
            icon = QApplication.style().standardIcon(QStyle.SP_DirIcon)
        else:
            icon = QApplication.style().standardIcon(QStyle.SP_FileIcon)

        # Initialize parent
        super().__init__(
            app_id=str(file_path),
            name=name,
            icon=icon,
            parent=parent
        )

        self.file_path = file_path
        self.is_directory = path.is_dir()

        # File-specific properties
        self.file_size = path.stat().st_size if path.is_file() else 0
        self.modified_time = path.stat().st_mtime

    def get_file_info(self) -> dict:
        """Get file information"""
        path = Path(self.file_path)

        return {
            'path': self.file_path,
            'name': path.name,
            'extension': path.suffix,
            'size': self.file_size,
            'is_directory': self.is_directory,
            'modified': self.modified_time,
            'exists': path.exists()
        }


class ShortcutIconWidget(AppIconWidget):
    """
    Specialized icon widget for shortcuts (.lnk files on Windows)
    Shows small arrow overlay on icon
    """

    def __init__(
            self,
            shortcut_path: str,
            target_path: str,
            name: str = None,
            icon: Union[QIcon, QPixmap, str] = None,
            parent: QWidget = None
    ):
        """
        Initialize shortcut icon

        Args:
            shortcut_path: Path to .lnk file
            target_path: Path to target file/app
            name: Display name
            icon: Icon
            parent: Parent widget
        """
        if not name:
            name = Path(shortcut_path).stem

        super().__init__(
            app_id=shortcut_path,
            name=name,
            icon=icon,
            parent=parent
        )

        self.shortcut_path = shortcut_path
        self.target_path = target_path
        self.is_shortcut = True

    def paintEvent(self, event: QPaintEvent):
        """Paint with shortcut arrow overlay"""
        # Paint normal icon
        super().paintEvent(event)

        # Draw shortcut arrow overlay
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Small arrow in bottom-left corner
        arrow_size = 16
        arrow_rect = QRect(
            8,
            self.icon_size.height() - arrow_size + 5,
            arrow_size,
            arrow_size
        )

        # Draw arrow background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
        painter.drawEllipse(arrow_rect.adjusted(1, 1, -1, -1))

        # Draw arrow
        arrow_icon = self.style().standardIcon(QStyle.SP_ArrowRight)
        arrow_pixmap = arrow_icon.pixmap(QSize(12, 12))
        painter.drawPixmap(
            arrow_rect.x() + 2,
            arrow_rect.y() + 2,
            arrow_pixmap
        )