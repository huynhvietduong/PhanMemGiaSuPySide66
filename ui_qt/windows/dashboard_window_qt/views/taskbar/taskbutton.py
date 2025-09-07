# ui_qt/windows/dashboard_window_qt/views/taskbar/taskbar_button.py
"""
Taskbar Button - Button cho mỗi app trong taskbar
Hiển thị icon, running state, preview, jump list, badges
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from enum import Enum
import logging

from PySide6.QtWidgets import (
    QToolButton, QWidget, QLabel, QMenu,
    QVBoxLayout, QHBoxLayout, QFrame,
    QGraphicsDropShadowEffect, QApplication,
    QStyle, QToolTip
)
from PySide6.QtCore import (
    Qt, QSize, QPoint, QRect, QTimer,
    Signal, Property, QPropertyAnimation,
    QSequentialAnimationGroup, QParallelAnimationGroup,
    QEasingCurve, QEvent, QObject
)
from PySide6.QtGui import (
    QPainter, QPixmap, QIcon, QFont, QColor,
    QPen, QBrush, QAction, QPalette,
    QLinearGradient, QRadialGradient,
    QMouseEvent, QPaintEvent, QEnterEvent,
    QContextMenuEvent, QWheelEvent
)

# Import utils
from ...utils.constants import (
    TASKBAR_BUTTON_WIDTH, TASKBAR_BUTTON_HEIGHT,
    TASKBAR_ICON_SIZE
)
from ...utils.assets import load_icon, get_app_icon

# Logger
logger = logging.getLogger(__name__)


# ========== ENUMS ==========

class ButtonState(Enum):
    """Taskbar button states"""
    NORMAL = "normal"
    HOVER = "hover"
    PRESSED = "pressed"
    ACTIVE = "active"  # Currently focused window


# ========== TASKBAR BUTTON CLASS ==========

class TaskbarButton(QToolButton):
    """
    Button for each app in taskbar
    Shows icon, running indicator, hover preview, jump list
    """

    # Signals
    clicked = Signal()  # Left click
    middle_clicked = Signal()  # Middle click (new instance)
    right_clicked = Signal()  # Right click (context menu)
    close_requested = Signal()  # Close app

    preview_requested = Signal()  # Show window preview
    jump_list_requested = Signal()  # Show jump list

    def __init__(
            self,
            app_id: str,
            app_name: str,
            icon: Optional[QIcon] = None,
            parent: Optional[QWidget] = None
    ):
        """
        Initialize taskbar button

        Args:
            app_id: Application ID
            app_name: Display name
            icon: App icon
            parent: Parent widget
        """
        super().__init__(parent)

        # Properties
        self.app_id = app_id
        self.app_name = app_name
        self.app_icon = icon or get_app_icon(app_id)

        # State
        self.is_pinned = False
        self.is_running = False
        self.is_active = False
        self.window_count = 0
        self.badge_count = 0

        # Visual state
        self.button_state = ButtonState.NORMAL
        self.hover_progress = 0.0
        self.flash_count = 0

        # Components
        self.preview_popup = None
        self.jump_list = None
        self.progress_overlay = None

        # Timers
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self._show_preview)
        self.preview_timer.setSingleShot(True)

        self.flash_timer = QTimer()
        self.flash_timer.timeout.connect(self._flash_step)

        # Animations
        self.hover_animation = None
        self.flash_animation = None
        self._setup_animations()

        # Setup UI
        self._setup_ui()

        # Install event filter
        self.installEventFilter(self)

        logger.debug(f"TaskbarButton created: {app_name}")

    # ========== SETUP METHODS ==========

    def _setup_ui(self):
        """Setup button UI"""
        # Button properties
        self.setObjectName("TaskbarButton")
        self.setFixedSize(TASKBAR_BUTTON_WIDTH, TASKBAR_BUTTON_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)

        # Icon
        self.setIcon(self.app_icon)
        self.setIconSize(QSize(TASKBAR_ICON_SIZE, TASKBAR_ICON_SIZE))

        # Style
        self.setStyleSheet(self._get_base_style())

        # Tooltip
        self.setToolTip(self.app_name)
        self.setToolTipDuration(2000)

        # Context menu policy
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _setup_animations(self):
        """Setup animations"""
        # Hover animation
        self.hover_animation = QPropertyAnimation(self, b"hover_progress")
        self.hover_animation.setDuration(150)
        self.hover_animation.setEasingCurve(QEasingCurve.InOutQuad)

        # Flash animation group
        self.flash_animation = QSequentialAnimationGroup()

        # Create flash sequence
        for i in range(6):  # 3 flashes
            fade_out = QPropertyAnimation(self, b"windowOpacity")
            fade_out.setDuration(100)
            fade_out.setStartValue(1.0)
            fade_out.setEndValue(0.3)

            fade_in = QPropertyAnimation(self, b"windowOpacity")
            fade_in.setDuration(100)
            fade_in.setStartValue(0.3)
            fade_in.setEndValue(1.0)

            self.flash_animation.addAnimation(fade_out)
            self.flash_animation.addAnimation(fade_in)

    def _get_base_style(self) -> str:
        """Get base stylesheet"""
        return """
            TaskbarButton {
                background: transparent;
                border: none;
                border-radius: 4px;
                padding: 4px;
            }
            TaskbarButton:hover {
                background: rgba(255, 255, 255, 15);
            }
            TaskbarButton:pressed {
                background: rgba(255, 255, 255, 25);
            }
        """

    def _get_running_style(self) -> str:
        """Get style khi app đang chạy"""
        return """
            QToolButton {
                background: rgba(255, 255, 255, 10);
                border: none;
                border-bottom: 2px solid #0078d4;
                border-radius: 4px;
                padding: 4px;
            }
            QToolButton:hover {
                background: rgba(255, 255, 255, 20);
                border-bottom: 2px solid #40a0ff;
            }
            QToolButton:pressed {
                background: rgba(255, 255, 255, 30);
            }
        """

    def _get_active_style(self) -> str:
        """Get style khi window đang focus"""
        return """
            QToolButton {
                background: rgba(0, 120, 215, 40);
                border: none;
                border-bottom: 2px solid #ffffff;
                border-radius: 4px;
                padding: 4px;
            }
            QToolButton:hover {
                background: rgba(0, 120, 215, 50);
            }
            QToolButton:pressed {
                background: rgba(0, 120, 215, 60);
            }
        """
    # ========== PROPERTIES ==========

    def get_hover_progress(self) -> float:
        """Get hover animation progress"""
        return self.hover_progress

    def set_hover_progress(self, value: float):
        """Set hover animation progress"""
        self.hover_progress = value
        self.update()

    hover_progress = Property(float, get_hover_progress, set_hover_progress)

    # ========== PAINT METHODS ==========

    def paintEvent(self, event: QPaintEvent):
        """Custom paint for button"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()

        # Draw background based on state
        self._draw_background(painter, rect)

        # Draw icon
        self._draw_icon(painter, rect)

        # Draw running indicator
        if self.is_running:
            self._draw_running_indicator(painter, rect)

        # Draw active indicator
        if self.is_active:
            self._draw_active_indicator(painter, rect)

        # Draw badge
        if self.badge_count > 0:
            self._draw_badge(painter, rect)

        # Draw progress overlay if any
        if hasattr(self, 'progress_value') and self.progress_value > 0:
            self._draw_progress(painter, rect)

    def _draw_background(self, painter: QPainter, rect: QRect):
        """Draw button background"""
        if self.button_state == ButtonState.PRESSED:
            # Pressed state
            painter.fillRect(rect, QColor(255, 255, 255, 40))

        elif self.button_state == ButtonState.HOVER:
            # Hover state with animation
            alpha = int(20 + self.hover_progress * 20)
            painter.fillRect(rect, QColor(255, 255, 255, alpha))

        elif self.is_active:
            # Active window background
            gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            gradient.setColorAt(0, QColor(0, 120, 215, 80))
            gradient.setColorAt(1, QColor(0, 120, 215, 60))
            painter.fillRect(rect, gradient)

    def _draw_icon(self, painter: QPainter, rect: QRect):
        """Draw app icon"""
        icon_rect = QRect(
            rect.center().x() - TASKBAR_ICON_SIZE // 2,
            rect.center().y() - TASKBAR_ICON_SIZE // 2,
            TASKBAR_ICON_SIZE,
            TASKBAR_ICON_SIZE
        )

        # Apply press effect
        if self.button_state == ButtonState.PRESSED:
            icon_rect.translate(0, 1)

        # Draw icon
        if self.app_icon:
            pixmap = self.app_icon.pixmap(QSize(TASKBAR_ICON_SIZE, TASKBAR_ICON_SIZE))

            # Apply hover effect
            if self.hover_progress > 0:
                painter.setOpacity(0.8 + self.hover_progress * 0.2)

            painter.drawPixmap(icon_rect, pixmap)
            painter.setOpacity(1.0)

    def _draw_running_indicator(self, painter: QPainter, rect: QRect):
        """Draw running indicator line"""
        # Draw line at bottom
        indicator_rect = QRect(
            rect.center().x() - 12,
            rect.bottom() - 3,
            24,
            2
        )

        # Choose color based on state
        if self.is_active:
            color = QColor(255, 255, 255, 255)
        else:
            color = QColor(0, 120, 215, 255)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawRoundedRect(indicator_rect, 1, 1)

        # Draw multiple indicators for multiple windows
        if self.window_count > 1:
            # Second indicator
            indicator_rect.translate(0, -4)
            painter.setOpacity(0.7)
            painter.drawRoundedRect(indicator_rect, 1, 1)

            if self.window_count > 2:
                # Third indicator
                indicator_rect.translate(0, -4)
                painter.setOpacity(0.5)
                painter.drawRoundedRect(indicator_rect, 1, 1)

        painter.setOpacity(1.0)

    def _draw_active_indicator(self, painter: QPainter, rect: QRect):
        """Draw active window indicator"""
        # Draw highlight border
        painter.setPen(QPen(QColor(0, 120, 215, 100), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 3, 3)

    def _draw_badge(self, painter: QPainter, rect: QRect):
        """Draw notification badge"""
        # Badge position (top-right)
        badge_size = 16
        badge_rect = QRect(
            rect.right() - badge_size - 2,
            rect.top() + 2,
            badge_size,
            badge_size
        )

        # Draw background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 0, 0)))
        painter.drawEllipse(badge_rect)

        # Draw text
        painter.setPen(Qt.white)
        font = QFont("Arial", 9, QFont.Bold)
        painter.setFont(font)

        text = str(self.badge_count) if self.badge_count < 10 else "9+"
        painter.drawText(badge_rect, Qt.AlignCenter, text)

    def _draw_progress(self, painter: QPainter, rect: QRect):
        """Draw progress overlay"""
        if not hasattr(self, 'progress_value'):
            return

        # Draw progress bar at bottom
        progress_rect = QRect(
            rect.left() + 4,
            rect.bottom() - 6,
            int((rect.width() - 8) * self.progress_value),
            3
        )

        # Progress color based on value
        if self.progress_value < 0.3:
            color = QColor(255, 0, 0, 200)  # Red
        elif self.progress_value < 0.7:
            color = QColor(255, 165, 0, 200)  # Orange
        else:
            color = QColor(0, 255, 0, 200)  # Green

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawRoundedRect(progress_rect, 1, 1)

    # ========== EVENT HANDLERS ==========

    def enterEvent(self, event: QEnterEvent):
        """Mouse enter event"""
        super().enterEvent(event)

        self.button_state = ButtonState.HOVER

        # Start hover animation
        self.hover_animation.setStartValue(self.hover_progress)
        self.hover_animation.setEndValue(1.0)
        self.hover_animation.start()

        # Start preview timer
        if self.is_running:
            self.preview_timer.start(500)  # Show preview after 500ms

    def leaveEvent(self, event):
        """Mouse leave event"""
        super().leaveEvent(event)

        self.button_state = ButtonState.NORMAL

        # Reverse hover animation
        self.hover_animation.setStartValue(self.hover_progress)
        self.hover_animation.setEndValue(0.0)
        self.hover_animation.start()

        # Cancel preview
        self.preview_timer.stop()
        self._hide_preview()

    def mousePressEvent(self, event: QMouseEvent):
        """Mouse press event"""
        if event.button() == Qt.LeftButton:
            self.button_state = ButtonState.PRESSED
            self.update()
        elif event.button() == Qt.MiddleButton:
            self.middle_clicked.emit()

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Mouse release event"""
        if event.button() == Qt.LeftButton:
            self.button_state = ButtonState.HOVER if self.rect().contains(event.pos()) else ButtonState.NORMAL
            self.update()

            # Emit clicked signal
            if self.rect().contains(event.pos()):
                self.clicked.emit()

        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        """Mouse wheel event - cycle through windows"""
        if self.window_count > 1:
            # Cycle through windows
            if event.angleDelta().y() > 0:
                # Scroll up - previous window
                logger.debug(f"Cycle to previous window: {self.app_id}")
            else:
                # Scroll down - next window
                logger.debug(f"Cycle to next window: {self.app_id}")

    def contextMenuEvent(self, event: QContextMenuEvent):
        """Context menu event"""
        self._show_context_menu(event.pos())
        event.accept()

    # ========== STATE MANAGEMENT ==========
    def set_running(self, is_running: bool, window_count: int = 1):
        """Set running state của button"""
        self.is_running = is_running
        self.window_count = window_count if is_running else 0

        # Update visual
        if is_running:
            # Thêm indicator (dấu chấm hoặc gạch dưới)
            self.setStyleSheet(self._get_running_style())
        else:
            self.setStyleSheet(self._get_base_style())

        self.update()

    def set_active(self, is_active: bool):
        """Set active state (đang được focus)"""
        self.is_active = is_active

        if is_active:
            self.setStyleSheet(self._get_active_style())
        else:
            self.setStyleSheet(self._get_running_style() if self.is_running else self._get_base_style())

        self.update()

    def set_pinned(self, is_pinned: bool):
        """Set pinned state"""
        self.is_pinned = is_pinned
        self.update()
    def set_badge_count(self, count: int):
        """Set notification badge count"""
        self.badge_count = count
        self.update()

    def set_progress(self, value: float):
        """
        Set progress value (0.0 to 1.0)

        Args:
            value: Progress value or -1 to hide
        """
        if value < 0:
            if hasattr(self, 'progress_value'):
                delattr(self, 'progress_value')
        else:
            self.progress_value = max(0.0, min(1.0, value))

        self.update()

    def add_window(self):
        """Add a window to this app"""
        self.window_count += 1
        self.set_running(True, self.window_count)

    def remove_window(self):
        """Remove a window from this app"""
        if self.window_count > 0:
            self.window_count -= 1

        if self.window_count == 0:
            self.set_running(False)
        else:
            self.set_running(True, self.window_count)

    # ========== PREVIEW METHODS ==========

    def _show_preview(self):
        """Show window preview popup"""
        if not self.is_running:
            return

        # Create preview if not exists
        if not self.preview_popup:
            self.preview_popup = WindowPreview(self.app_name, self)

        # Position above button
        global_pos = self.mapToGlobal(QPoint(0, 0))
        preview_pos = QPoint(
            global_pos.x() + (self.width() - self.preview_popup.width()) // 2,
            global_pos.y() - self.preview_popup.height() - 10
        )

        self.preview_popup.move(preview_pos)
        self.preview_popup.show()

        # Emit signal for actual preview content
        self.preview_requested.emit()

    def _hide_preview(self):
        """Hide window preview"""
        if self.preview_popup:
            self.preview_popup.hide()

    def update_preview(self, pixmap: QPixmap):
        """Update preview with window snapshot"""
        if self.preview_popup:
            self.preview_popup.set_preview(pixmap)

    # ========== JUMP LIST METHODS ==========

    def show_jump_list(self):
        """Show jump list menu"""
        if not self.jump_list:
            self.jump_list = JumpListMenu(self.app_id, self.app_name, self)

        # Position above button
        global_pos = self.mapToGlobal(QPoint(0, 0))
        menu_pos = QPoint(
            global_pos.x(),
            global_pos.y() - self.jump_list.sizeHint().height()
        )

        self.jump_list.exec(menu_pos)

    def _show_context_menu(self, pos: QPoint):
        """Show context menu"""
        menu = QMenu(self)

        # Pin/Unpin
        if self.is_pinned:
            unpin_action = QAction(load_icon("unpin"), "Bỏ ghim", self)
            menu.addAction(unpin_action)
        else:
            pin_action = QAction(load_icon("pin"), "Ghim vào thanh tác vụ", self)
            menu.addAction(pin_action)

        menu.addSeparator()

        # Close window(s)
        if self.is_running:
            if self.window_count > 1:
                close_action = QAction(
                    load_icon("close"),
                    f"Đóng tất cả ({self.window_count}) cửa sổ",
                    self
                )
            else:
                close_action = QAction(load_icon("close"), "Đóng cửa sổ", self)

            close_action.triggered.connect(self.close_requested.emit)
            menu.addAction(close_action)

        # Show menu
        menu.exec(self.mapToGlobal(pos))

    # ========== ANIMATION METHODS ==========

    def flash_attention(self, count: int = 3):
        """Flash button for attention"""
        self.flash_count = count * 2  # Each flash = fade out + fade in
        self.flash_timer.start(150)

    def _flash_step(self):
        """Flash animation step"""
        if self.flash_count > 0:
            # Toggle opacity
            if self.flash_count % 2 == 0:
                self.setWindowOpacity(0.5)
            else:
                self.setWindowOpacity(1.0)

            self.flash_count -= 1
        else:
            # Stop flashing
            self.flash_timer.stop()
            self.setWindowOpacity(1.0)

    def bounce(self):
        """Bounce animation for notification"""
        # Create bounce animation
        bounce = QPropertyAnimation(self, b"pos")
        bounce.setDuration(300)

        current_pos = self.pos()
        bounce.setKeyValueAt(0, current_pos)
        bounce.setKeyValueAt(0.3, current_pos - QPoint(0, 10))
        bounce.setKeyValueAt(0.6, current_pos - QPoint(0, 5))
        bounce.setKeyValueAt(1.0, current_pos)

        bounce.setEasingCurve(QEasingCurve.OutBounce)
        bounce.start()


# ========== WINDOW PREVIEW WIDGET ==========

class WindowPreview(QFrame):
    """Preview popup for window thumbnails"""

    def __init__(self, app_name: str, parent=None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint)

        self.app_name = app_name
        self.preview_pixmap = None

        self.setObjectName("WindowPreview")
        self.setFixedSize(200, 150)

        # Shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 100))
        self.setGraphicsEffect(shadow)

        # Style
        self.setStyleSheet("""
            #WindowPreview {
                background: white;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
        """)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Title
        self.title_label = QLabel(app_name)
        self.title_label.setStyleSheet("""
            font-size: 11px;
            font-weight: bold;
            padding: 2px;
        """)
        layout.addWidget(self.title_label)

        # Preview area
        self.preview_label = QLabel()
        self.preview_label.setScaledContents(True)
        self.preview_label.setStyleSheet("""
            background: #f0f0f0;
            border: 1px solid #ddd;
        """)
        layout.addWidget(self.preview_label, 1)

    def set_preview(self, pixmap: QPixmap):
        """Set preview image"""
        if pixmap:
            scaled = pixmap.scaled(
                self.preview_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled)


# ========== JUMP LIST MENU ==========

class JumpListMenu(QMenu):
    """Jump list for taskbar button"""

    def __init__(self, app_id: str, app_name: str, parent=None):
        super().__init__(parent)

        self.app_id = app_id
        self.app_name = app_name

        self._build_menu()

    def _build_menu(self):
        """Build jump list menu"""
        # Recent items
        recent_section = self.addSection("Recent")

        # Add recent items (mock data)
        for i in range(3):
            recent_action = QAction(f"Recent Item {i + 1}", self)
            self.addAction(recent_action)

        self.addSeparator()

        # Pinned items
        pinned_section = self.addSection("Pinned")

        # Add pinned items (mock data)
        for i in range(2):
            pinned_action = QAction(f"Pinned Item {i + 1}", self)
            self.addAction(pinned_action)

        self.addSeparator()

        # App actions
        new_window_action = QAction(
            load_icon("new_window"),
            "New Window",
            self
        )
        self.addAction(new_window_action)

    def addSection(self, title: str) -> QAction:
        """Add section header to menu"""
        section_action = QAction(title, self)
        section_action.setEnabled(False)
        font = section_action.font()
        font.setBold(True)
        section_action.setFont(font)
        self.addAction(section_action)
        return section_action