# ui_qt/windows/dashboard_window_qt/views/widgets/notification_widget.py
"""
Notification Widget - Toast notifications hiện đại cho Desktop
Hỗ trợ: Multiple notifications, Stacking, Actions, Custom styles, Sound
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
import logging
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QToolButton, QTextEdit, QFrame,
    QGraphicsOpacityEffect, QProgressBar, QApplication,
    QStyle, QSystemTrayIcon,QGraphicsDropShadowEffect
)
from PySide6.QtCore import (
    Qt, QTimer, QDateTime, QPoint, QRect, QSize,
    Signal, Property, QPropertyAnimation, QEasingCurve,
    QParallelAnimationGroup, QSequentialAnimationGroup,
    QEvent, QSettings, QUrl
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont,
    QLinearGradient, QPixmap, QIcon, QPainterPath,
    QMouseEvent, QPaintEvent, QEnterEvent,
    QScreen, QGuiApplication
)
from PySide6.QtMultimedia import QSoundEffect

# Import utils
try:
    from ...utils.constants import (
        NOTIFICATION_WIDTH, NOTIFICATION_HEIGHT,
        NOTIFICATION_MARGIN, AUTO_HIDE_DURATION,
        COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_INFO,
        ANIMATION_DURATION_NORMAL
    )
    from ...utils.assets import load_icon
except ImportError:
    # Fallback values
    NOTIFICATION_WIDTH = 350
    NOTIFICATION_HEIGHT = 80
    NOTIFICATION_MARGIN = 10
    AUTO_HIDE_DURATION = 5000
    ANIMATION_DURATION_NORMAL = 300
    COLOR_SUCCESS = QColor(16, 185, 129)
    COLOR_WARNING = QColor(245, 158, 11)
    COLOR_ERROR = QColor(239, 68, 68)
    COLOR_INFO = QColor(59, 130, 246)


    def load_icon(name):
        return QIcon()

# Logger
logger = logging.getLogger(__name__)


# ========== ENUMS ==========

class NotificationType(Enum):
    """Notification types"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CUSTOM = "custom"


class NotificationPosition(Enum):
    """Screen positions for notifications"""
    TOP_RIGHT = "top_right"
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    BOTTOM_RIGHT = "bottom_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    CENTER = "center"


class NotificationStyle(Enum):
    """Visual styles"""
    MODERN = "modern"
    MINIMAL = "minimal"
    GLASS = "glass"
    DARK = "dark"
    COLORED = "colored"


# ========== DATA CLASSES ==========

@dataclass
class NotificationAction:
    """Action button for notification"""
    text: str
    callback: Callable
    style: str = "default"  # default, primary, danger
    icon: Optional[QIcon] = None


@dataclass
class NotificationData:
    """Notification data structure"""
    id: str
    title: str
    message: str
    type: NotificationType
    icon: Optional[QIcon] = None
    actions: List[NotificationAction] = None
    duration: int = AUTO_HIDE_DURATION
    timestamp: datetime = None
    sound: bool = True
    persist: bool = False
    progress: Optional[int] = None  # 0-100 for progress notifications
    custom_color: Optional[QColor] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.actions is None:
            self.actions = []


# ========== SINGLE NOTIFICATION ==========

class NotificationWidget(QFrame):
    """
    Single notification toast widget
    """

    # Signals
    closed = Signal(str)  # notification_id
    action_clicked = Signal(str, str)  # notification_id, action_text
    clicked = Signal(str)  # notification_id

    def __init__(self, data: NotificationData, style: NotificationStyle = NotificationStyle.MODERN, parent=None):
        super().__init__(parent)

        self.data = data
        self.style = style
        self.is_hovering = False
        self.is_closing = False

        # Animation components
        self.show_animation = None
        self.hide_animation = None
        self.hover_animation = None
        self.progress_animation = None

        # Timer for auto-hide
        self.auto_hide_timer = QTimer()
        self.auto_hide_timer.timeout.connect(self.hide_animated)

        # Setup UI
        self.setup_ui()

        # Setup animations
        self.setup_animations()

        # Start auto-hide timer if not persistent
        if not data.persist and data.duration > 0:
            self.auto_hide_timer.start(data.duration)

        # Play sound if enabled
        if data.sound:
            self.play_sound()

    def setup_ui(self):
        """Setup UI components"""
        self.setObjectName("NotificationWidget")
        self.setFixedSize(NOTIFICATION_WIDTH, NOTIFICATION_HEIGHT)

        # Window flags for floating widget
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        # Main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # Icon
        if self.data.icon or self.data.type != NotificationType.CUSTOM:
            icon_label = QLabel()
            icon = self.data.icon or self.get_type_icon()
            if icon:
                pixmap = icon.pixmap(32, 32)
                icon_label.setPixmap(pixmap)
            icon_label.setFixedSize(32, 32)
            main_layout.addWidget(icon_label)

        # Content area
        content_layout = QVBoxLayout()
        content_layout.setSpacing(4)

        # Title
        self.title_label = QLabel(self.data.title)
        self.title_label.setObjectName("NotificationTitle")
        self.title_label.setWordWrap(False)
        font = self.title_label.font()
        font.setWeight(QFont.Bold)
        font.setPointSize(11)
        self.title_label.setFont(font)
        content_layout.addWidget(self.title_label)

        # Message
        self.message_label = QLabel(self.data.message)
        self.message_label.setObjectName("NotificationMessage")
        self.message_label.setWordWrap(True)
        self.message_label.setMaximumHeight(40)
        content_layout.addWidget(self.message_label)

        # Progress bar if needed
        if self.data.progress is not None:
            self.progress_bar = QProgressBar()
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(self.data.progress)
            self.progress_bar.setTextVisible(False)
            self.progress_bar.setFixedHeight(4)
            content_layout.addWidget(self.progress_bar)

        # Actions if any
        if self.data.actions:
            actions_layout = QHBoxLayout()
            actions_layout.setSpacing(8)

            for action in self.data.actions:
                btn = QPushButton(action.text)
                if action.icon:
                    btn.setIcon(action.icon)
                btn.setObjectName(f"NotificationAction_{action.style}")
                btn.clicked.connect(lambda checked, a=action: self.handle_action(a))
                btn.setCursor(Qt.PointingHandCursor)
                actions_layout.addWidget(btn)

            actions_layout.addStretch()
            content_layout.addLayout(actions_layout)

        content_layout.addStretch()
        main_layout.addLayout(content_layout, 1)

        # Close button
        close_btn = QToolButton()
        close_btn.setObjectName("NotificationClose")
        close_btn.setText("×")
        close_btn.setFixedSize(20, 20)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.hide_animated)
        main_layout.addWidget(close_btn, 0, Qt.AlignTop)

        # Apply style
        self.apply_style()

        # Install event filter for hover
        self.installEventFilter(self)

    def apply_style(self):
        """Apply visual style"""
        # Get colors based on type
        bg_color, text_color, border_color = self.get_colors()

        if self.style == NotificationStyle.MODERN:
            self.setStyleSheet(f"""
                #NotificationWidget {{
                    background: {bg_color.name()};
                    border: 1px solid {border_color.name()};
                    border-radius: 8px;
                }}
                #NotificationTitle {{
                    color: {text_color.name()};
                }}
                #NotificationMessage {{
                    color: {text_color.darker(120).name()};
                    font-size: 10px;
                }}
                #NotificationClose {{
                    background: transparent;
                    border: none;
                    color: {text_color.name()};
                    font-size: 18px;
                    font-weight: bold;
                }}
                #NotificationClose:hover {{
                    background: rgba(255, 255, 255, 20);
                    border-radius: 10px;
                }}
                QPushButton {{
                    background: rgba(255, 255, 255, 20);
                    border: 1px solid rgba(255, 255, 255, 30);
                    color: {text_color.name()};
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background: rgba(255, 255, 255, 30);
                }}
                QProgressBar {{
                    background: rgba(255, 255, 255, 20);
                    border: none;
                    border-radius: 2px;
                }}
                QProgressBar::chunk {{
                    background: {text_color.name()};
                    border-radius: 2px;
                }}
            """)

        elif self.style == NotificationStyle.MINIMAL:
            self.setStyleSheet(f"""
                #NotificationWidget {{
                    background: white;
                    border: 1px solid #e5e5e5;
                    border-left: 4px solid {border_color.name()};
                }}
                #NotificationTitle {{
                    color: #1f2937;
                }}
                #NotificationMessage {{
                    color: #6b7280;
                    font-size: 10px;
                }}
            """)

        elif self.style == NotificationStyle.GLASS:
            self.setStyleSheet(f"""
                #NotificationWidget {{
                    background: rgba(255, 255, 255, 10);
                    border: 1px solid rgba(255, 255, 255, 20);
                    border-radius: 12px;
                }}
                #NotificationTitle {{
                    color: white;
                }}
                #NotificationMessage {{
                    color: rgba(255, 255, 255, 200);
                    font-size: 10px;
                }}
            """)

        elif self.style == NotificationStyle.DARK:
            self.setStyleSheet(f"""
                #NotificationWidget {{
                    background: #1f2937;
                    border: 1px solid #374151;
                    border-radius: 8px;
                }}
                #NotificationTitle {{
                    color: #f3f4f6;
                }}
                #NotificationMessage {{
                    color: #9ca3af;
                    font-size: 10px;
                }}
            """)

        # Add shadow effect
        if self.style != NotificationStyle.MINIMAL:
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(20)
            shadow.setColor(QColor(0, 0, 0, 80))
            shadow.setOffset(0, 5)
            self.setGraphicsEffect(shadow)

    def get_colors(self) -> tuple:
        """Get colors based on notification type"""
        if self.data.custom_color:
            bg = self.data.custom_color
            text = QColor("white") if bg.lightness() < 128 else QColor("black")
            border = bg.darker(120)
            return bg, text, border

        colors = {
            NotificationType.INFO: (COLOR_INFO, QColor("white"), COLOR_INFO.darker(120)),
            NotificationType.SUCCESS: (COLOR_SUCCESS, QColor("white"), COLOR_SUCCESS.darker(120)),
            NotificationType.WARNING: (COLOR_WARNING, QColor("white"), COLOR_WARNING.darker(120)),
            NotificationType.ERROR: (COLOR_ERROR, QColor("white"), COLOR_ERROR.darker(120)),
            NotificationType.CUSTOM: (QColor(50, 50, 60), QColor("white"), QColor(70, 70, 80))
        }

        return colors.get(self.data.type, colors[NotificationType.INFO])

    def get_type_icon(self) -> Optional[QIcon]:
        """Get icon for notification type"""
        icons = {
            NotificationType.INFO: "info",
            NotificationType.SUCCESS: "success",
            NotificationType.WARNING: "warning",
            NotificationType.ERROR: "error"
        }

        icon_name = icons.get(self.data.type)
        if icon_name:
            return load_icon(icon_name)
        return None

    def setup_animations(self):
        """Setup animations"""
        # Fade effect
        self.opacity_effect = QGraphicsOpacityEffect()
        if not self.graphicsEffect():  # Only set if no shadow
            self.setGraphicsEffect(self.opacity_effect)

        # Show animation - slide + fade
        self.show_animation = QParallelAnimationGroup()

        # Fade in
        fade_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        fade_in.setDuration(ANIMATION_DURATION_NORMAL)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.OutCubic)
        self.show_animation.addAnimation(fade_in)

        # Slide in
        slide_in = QPropertyAnimation(self, b"pos")
        slide_in.setDuration(ANIMATION_DURATION_NORMAL)
        slide_in.setEasingCurve(QEasingCurve.OutCubic)
        self.show_animation.addAnimation(slide_in)

        # Hide animation
        self.hide_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.hide_animation.setDuration(ANIMATION_DURATION_NORMAL)
        self.hide_animation.setStartValue(1.0)
        self.hide_animation.setEndValue(0.0)
        self.hide_animation.setEasingCurve(QEasingCurve.InCubic)
        self.hide_animation.finished.connect(self.on_hide_finished)

    def show_animated(self, start_pos: QPoint, end_pos: QPoint):
        """Show with animation"""
        # Set initial position
        self.move(start_pos)
        self.show()

        # Configure slide animation
        slide = self.show_animation.animationAt(1)
        slide.setStartValue(start_pos)
        slide.setEndValue(end_pos)

        # Start animation
        self.show_animation.start()

    def hide_animated(self):
        """Hide with animation"""
        if not self.is_closing:
            self.is_closing = True
            self.auto_hide_timer.stop()
            self.hide_animation.start()

    def on_hide_finished(self):
        """Called when hide animation finishes"""
        self.hide()
        self.closed.emit(self.data.id)
        self.deleteLater()

    def handle_action(self, action: NotificationAction):
        """Handle action button click"""
        self.action_clicked.emit(self.data.id, action.text)
        action.callback()
        if not self.data.persist:
            self.hide_animated()

    def play_sound(self):
        """Play notification sound"""
        try:
            sound = QSoundEffect()
            sound_file = self.get_sound_file()
            if sound_file and os.path.exists(sound_file):
                sound.setSource(QUrl.fromLocalFile(sound_file))
                sound.setVolume(0.5)
                sound.play()
        except Exception as e:
            logger.error(f"Error playing sound: {e}")

    def get_sound_file(self) -> Optional[str]:
        """Get sound file path based on type"""
        sound_dir = Path(__file__).parent.parent.parent / "assets" / "sounds"

        sounds = {
            NotificationType.INFO: "info.wav",
            NotificationType.SUCCESS: "success.wav",
            NotificationType.WARNING: "warning.wav",
            NotificationType.ERROR: "error.wav"
        }

        sound_file = sounds.get(self.data.type)
        if sound_file:
            path = sound_dir / sound_file
            if path.exists():
                return str(path)
        return None

    def update_progress(self, value: int):
        """Update progress bar value"""
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(value)
            if value >= 100:
                # Auto close on completion
                QTimer.singleShot(1000, self.hide_animated)

    # ========== EVENT HANDLERS ==========

    def eventFilter(self, obj, event: QEvent) -> bool:
        """Handle events"""
        if obj == self:
            if event.type() == QEvent.Enter:
                self.on_enter()
            elif event.type() == QEvent.Leave:
                self.on_leave()

        return super().eventFilter(obj, event)

    def on_enter(self):
        """Mouse entered"""
        self.is_hovering = True
        self.auto_hide_timer.stop()

        # Slight scale effect on hover
        if self.style == NotificationStyle.MODERN:
            self.setStyleSheet(self.styleSheet() + """
                #NotificationWidget {
                    transform: scale(1.02);
                }
            """)

    def on_leave(self):
        """Mouse left"""
        self.is_hovering = False
        if not self.data.persist and not self.is_closing:
            # Restart auto-hide timer with shorter duration
            self.auto_hide_timer.start(2000)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse click"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.data.id)
        super().mousePressEvent(event)


# ========== NOTIFICATION MANAGER ==========

class NotificationManager(QWidget):
    """
    Manages multiple notifications - positioning, stacking, queue
    """

    # Signals
    notification_closed = Signal(str)
    notification_action = Signal(str, str)

    def __init__(self, position: NotificationPosition = NotificationPosition.TOP_RIGHT,
                 max_visible: int = 5, parent=None):
        super().__init__(parent)

        self.position = position
        self.max_visible = max_visible
        self.style = NotificationStyle.MODERN

        # Storage
        self.active_notifications: Dict[str, NotificationWidget] = {}
        self.notification_queue: List[NotificationData] = []
        self.notification_history: List[NotificationData] = []

        # Settings
        self.settings = QSettings("TutorApp", "Notifications")
        self.load_settings()

        # Hide manager widget itself
        self.hide()

    def show_notification(self,
                          title: str,
                          message: str,
                          notification_type: NotificationType = NotificationType.INFO,
                          icon: Optional[QIcon] = None,
                          actions: List[NotificationAction] = None,
                          duration: int = AUTO_HIDE_DURATION,
                          sound: bool = True,
                          persist: bool = False,
                          progress: Optional[int] = None) -> str:
        """
        Show a notification

        Returns:
            Notification ID
        """
        # Create notification data
        notification_id = f"notif_{datetime.now().timestamp()}"
        data = NotificationData(
            id=notification_id,
            title=title,
            message=message,
            type=notification_type,
            icon=icon,
            actions=actions or [],
            duration=duration,
            sound=sound,
            persist=persist,
            progress=progress
        )

        # Add to history
        self.notification_history.append(data)

        # Check if can show immediately or queue
        if len(self.active_notifications) < self.max_visible:
            self._show_notification_widget(data)
        else:
            self.notification_queue.append(data)

        return notification_id

    def _show_notification_widget(self, data: NotificationData):
        """Create and show notification widget"""
        # Create widget
        widget = NotificationWidget(data, self.style)

        # Connect signals
        widget.closed.connect(self._on_notification_closed)
        widget.action_clicked.connect(self._on_notification_action)
        widget.clicked.connect(self._on_notification_clicked)

        # Calculate position
        start_pos, end_pos = self._calculate_position(len(self.active_notifications))

        # Store
        self.active_notifications[data.id] = widget

        # Show with animation
        widget.show_animated(start_pos, end_pos)

    def _calculate_position(self, index: int) -> tuple:
        """Calculate start and end positions for notification"""
        screen = QGuiApplication.primaryScreen().geometry()

        # Base position based on notification position setting
        x, y = 0, 0
        offset_x, offset_y = 0, 0

        if self.position == NotificationPosition.TOP_RIGHT:
            x = screen.width() - NOTIFICATION_WIDTH - NOTIFICATION_MARGIN
            y = NOTIFICATION_MARGIN + index * (NOTIFICATION_HEIGHT + NOTIFICATION_MARGIN)
            offset_x = NOTIFICATION_WIDTH + 50

        elif self.position == NotificationPosition.TOP_LEFT:
            x = NOTIFICATION_MARGIN
            y = NOTIFICATION_MARGIN + index * (NOTIFICATION_HEIGHT + NOTIFICATION_MARGIN)
            offset_x = -(NOTIFICATION_WIDTH + 50)

        elif self.position == NotificationPosition.TOP_CENTER:
            x = (screen.width() - NOTIFICATION_WIDTH) // 2
            y = NOTIFICATION_MARGIN + index * (NOTIFICATION_HEIGHT + NOTIFICATION_MARGIN)
            offset_y = -50

        elif self.position == NotificationPosition.BOTTOM_RIGHT:
            x = screen.width() - NOTIFICATION_WIDTH - NOTIFICATION_MARGIN
            y = screen.height() - NOTIFICATION_HEIGHT - NOTIFICATION_MARGIN - \
                index * (NOTIFICATION_HEIGHT + NOTIFICATION_MARGIN)
            offset_x = NOTIFICATION_WIDTH + 50

        elif self.position == NotificationPosition.BOTTOM_LEFT:
            x = NOTIFICATION_MARGIN
            y = screen.height() - NOTIFICATION_HEIGHT - NOTIFICATION_MARGIN - \
                index * (NOTIFICATION_HEIGHT + NOTIFICATION_MARGIN)
            offset_x = -(NOTIFICATION_WIDTH + 50)

        elif self.position == NotificationPosition.BOTTOM_CENTER:
            x = (screen.width() - NOTIFICATION_WIDTH) // 2
            y = screen.height() - NOTIFICATION_HEIGHT - NOTIFICATION_MARGIN - \
                index * (NOTIFICATION_HEIGHT + NOTIFICATION_MARGIN)
            offset_y = 50

        elif self.position == NotificationPosition.CENTER:
            x = (screen.width() - NOTIFICATION_WIDTH) // 2
            y = (screen.height() - NOTIFICATION_HEIGHT) // 2 + \
                index * (NOTIFICATION_HEIGHT + NOTIFICATION_MARGIN)

        start_pos = QPoint(x + offset_x, y + offset_y)
        end_pos = QPoint(x, y)

        return start_pos, end_pos

    def _on_notification_closed(self, notification_id: str):
        """Handle notification closed"""
        # Remove from active
        if notification_id in self.active_notifications:
            del self.active_notifications[notification_id]

        # Reposition remaining notifications
        self._reposition_notifications()

        # Show queued notification if any
        if self.notification_queue and len(self.active_notifications) < self.max_visible:
            next_data = self.notification_queue.pop(0)
            self._show_notification_widget(next_data)

        # Emit signal
        self.notification_closed.emit(notification_id)

    def _on_notification_action(self, notification_id: str, action_text: str):
        """Handle notification action clicked"""
        self.notification_action.emit(notification_id, action_text)

    def _on_notification_clicked(self, notification_id: str):
        """Handle notification clicked"""
        logger.info(f"Notification clicked: {notification_id}")

    def _reposition_notifications(self):
        """Reposition all active notifications"""
        for index, (notif_id, widget) in enumerate(self.active_notifications.items()):
            _, end_pos = self._calculate_position(index)

            # Animate to new position
            animation = QPropertyAnimation(widget, b"pos")
            animation.setDuration(200)
            animation.setEndValue(end_pos)
            animation.setEasingCurve(QEasingCurve.OutCubic)
            animation.start()

    def update_notification_progress(self, notification_id: str, progress: int):
        """Update progress for a notification"""
        if notification_id in self.active_notifications:
            self.active_notifications[notification_id].update_progress(progress)

    def close_notification(self, notification_id: str):
        """Close a specific notification"""
        if notification_id in self.active_notifications:
            self.active_notifications[notification_id].hide_animated()

    def close_all_notifications(self):
        """Close all active notifications"""
        for widget in list(self.active_notifications.values()):
            widget.hide_animated()

    def set_position(self, position: NotificationPosition):
        """Change notification position"""
        self.position = position
        self._reposition_notifications()
        self.save_settings()

    def set_style(self, style: NotificationStyle):
        """Change notification style"""
        self.style = style
        self.save_settings()

    def set_max_visible(self, max_visible: int):
        """Set maximum visible notifications"""
        self.max_visible = max(1, min(10, max_visible))
        self.save_settings()

    def get_history(self) -> List[NotificationData]:
        """Get notification history"""
        return self.notification_history.copy()

    def clear_history(self):
        """Clear notification history"""
        self.notification_history.clear()

    def save_settings(self):
        """Save settings"""
        self.settings.setValue("position", self.position.value)
        self.settings.setValue("style", self.style.value)
        self.settings.setValue("max_visible", self.max_visible)

    def load_settings(self):
        """Load settings"""
        pos = self.settings.value("position", NotificationPosition.TOP_RIGHT.value)
        for p in NotificationPosition:
            if p.value == pos:
                self.position = p
                break

        style = self.settings.value("style", NotificationStyle.MODERN.value)
        for s in NotificationStyle:
            if s.value == style:
                self.style = s
                break

        self.max_visible = int(self.settings.value("max_visible", 5))


# ========== CONVENIENCE FUNCTIONS ==========

# Global notification manager instance
_notification_manager = None


def get_notification_manager() -> NotificationManager:
    """Get or create global notification manager"""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager


def show_notification(title: str,
                      message: str,
                      notification_type: NotificationType = NotificationType.INFO,
                      **kwargs) -> str:
    """
    Show a notification using global manager

    Args:
        title: Notification title
        message: Notification message
        notification_type: Type of notification
        **kwargs: Additional arguments for NotificationManager.show_notification

    Returns:
        Notification ID
    """
    manager = get_notification_manager()
    return manager.show_notification(title, message, notification_type, **kwargs)


def show_info(title: str, message: str, **kwargs) -> str:
    """Show info notification"""
    return show_notification(title, message, NotificationType.INFO, **kwargs)


def show_success(title: str, message: str, **kwargs) -> str:
    """Show success notification"""
    return show_notification(title, message, NotificationType.SUCCESS, **kwargs)


def show_warning(title: str, message: str, **kwargs) -> str:
    """Show warning notification"""
    return show_notification(title, message, NotificationType.WARNING, **kwargs)


def show_error(title: str, message: str, **kwargs) -> str:
    """Show error notification"""
    return show_notification(title, message, NotificationType.ERROR, **kwargs)


def show_progress(title: str, message: str, progress: int, **kwargs) -> str:
    """Show progress notification"""
    return show_notification(title, message, NotificationType.INFO,
                             progress=progress, persist=True, **kwargs)


# ========== EXAMPLE USAGE ==========

if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    # Create notification manager
    manager = NotificationManager()

    # Example 1: Simple notification
    manager.show_notification(
        "Thông báo",
        "Đây là một thông báo mẫu",
        NotificationType.INFO
    )


    # Example 2: Success with action
    def on_view():
        print("View clicked")


    manager.show_notification(
        "Thành công!",
        "File đã được lưu thành công",
        NotificationType.SUCCESS,
        actions=[
            NotificationAction("Xem", on_view),
            NotificationAction("Đóng", lambda: None)
        ]
    )

    # Example 3: Progress notification
    notif_id = manager.show_notification(
        "Đang tải xuống",
        "Đang tải file: document.pdf",
        NotificationType.INFO,
        progress=0,
        persist=True
    )


    # Simulate progress
    def update_progress():
        for i in range(0, 101, 10):
            QTimer.singleShot(i * 100,
                              lambda p=i: manager.update_notification_progress(notif_id, p))


    update_progress()

    # Example 4: Error notification
    QTimer.singleShot(2000, lambda: manager.show_notification(
        "Lỗi!",
        "Không thể kết nối đến server",
        NotificationType.ERROR,
        duration=10000
    ))

    # Example 5: Custom styled notification
    QTimer.singleShot(3000, lambda: manager.show_notification(
        "Nhắc nhở",
        "Bạn có 3 bài tập cần chấm điểm",
        NotificationType.WARNING,
        sound=True
    ))

    sys.exit(app.exec())