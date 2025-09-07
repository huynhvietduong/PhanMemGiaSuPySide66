# ui_qt/windows/dashboard_window_qt/views/taskbar/taskbar.py
"""
Taskbar Container - Thanh tác vụ chính của Dashboard
Chứa Start button, Search box, App buttons, System tray
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFrame,
    QPushButton, QLineEdit, QLabel, QToolButton,
    QScrollArea, QMenu, QSystemTrayIcon,
    QApplication, QStyle, QSizePolicy
)
from PySide6.QtCore import (
    Qt, QSize, QPoint, QRect, QTimer,
    Signal, Property, QPropertyAnimation,
    QEasingCurve, QEvent, QDateTime
)
from PySide6.QtGui import (
    QPainter, QPixmap, QIcon, QFont, QColor,
    QPen, QBrush, QAction, QPalette,
    QLinearGradient, QMouseEvent, QPaintEvent
)

# Import taskbar components
from taskbutton import TaskbarButton
from .system_tray import SystemTray

# Import utils
from ...utils.constants import (
    TASKBAR_HEIGHT, TASKBAR_BUTTON_WIDTH,
    TASKBAR_BUTTON_HEIGHT, TASKBAR_ICON_SIZE
)
from ...utils.assets import load_icon, get_app_icon
from ...utils.animations import fade_in_animation

# Import repositories
from ...repositories.app_repository import AppRepository, AppModel
from ...repositories.settings_repository import SettingsRepository

# Logger
logger = logging.getLogger(__name__)


# ========== TASKBAR CLASS ==========

class Taskbar(QFrame):
    """
    Main Taskbar Container
    Layout: [Start] [Search] [Pinned Apps] [Running Apps] [System Tray] [Clock]
    """

    # Signals
    start_clicked = Signal()
    search_focused = Signal()
    search_text_changed = Signal(str)

    app_launched = Signal(str)  # app_id
    app_focused = Signal(str)  # app_id
    app_closed = Signal(str)  # app_id

    show_desktop_clicked = Signal()
    notification_clicked = Signal()

    def __init__(self, parent=None):
        """Initialize Taskbar"""
        super().__init__(parent)

        # Repositories
        self.app_repo = AppRepository()
        self.settings_repo = SettingsRepository()

        # State
        self.is_locked = False
        self.auto_hide = False
        self.position = "bottom"  # bottom, top, left, right

        # App buttons storage
        self.app_buttons: Dict[str, TaskbarButton] = {}
        self.pinned_apps: List[str] = []
        self.running_apps: List[str] = []

        # Components
        self.start_button = None
        self.search_box = None
        self.apps_container = None
        self.system_tray = None
        self.show_desktop_button = None

        # Timers
        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self._update_clock)

        # Setup
        self._setup_ui()
        self._load_settings()
        self._setup_connections()
        self._load_pinned_apps()

        # Start clock
        self.clock_timer.start(1000)  # Update every second

        logger.info("Taskbar initialized")

    # ========== SETUP METHODS ==========

    def _setup_ui(self):
        """Setup UI components"""
        # Taskbar properties
        self.setObjectName("Taskbar")
        self.setFixedHeight(TASKBAR_HEIGHT)
        self.setFrameStyle(QFrame.NoFrame)

        # Main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left section: Start button and search
        left_section = self._create_left_section()
        main_layout.addWidget(left_section)

        # Center section: App buttons
        center_section = self._create_center_section()
        main_layout.addWidget(center_section, 1)  # Stretch

        # Right section: System tray and clock
        right_section = self._create_right_section()
        main_layout.addWidget(right_section)

        # Apply style
        self._apply_style()

    def _create_left_section(self) -> QWidget:
        """Create left section with Start and Search"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(10)

        # Start button
        self.start_button = StartButton(self)
        self.start_button.clicked.connect(self.start_clicked.emit)
        layout.addWidget(self.start_button)

        # Search box
        self.search_box = TaskbarSearchBox(self)
        self.search_box.textChanged.connect(self.search_text_changed.emit)
        self.search_box.focus_gained.connect(self.search_focused.emit)
        layout.addWidget(self.search_box)

        return container

    def _create_center_section(self) -> QWidget:
        """Create center section with app buttons"""
        # Scroll area for app buttons
        scroll = QScrollArea()
        scroll.setObjectName("TaskbarAppsArea")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidgetResizable(True)
        scroll.setFrameStyle(QFrame.NoFrame)

        # Container for buttons
        self.apps_container = QWidget()
        self.apps_layout = QHBoxLayout(self.apps_container)
        self.apps_layout.setContentsMargins(0, 0, 0, 0)
        self.apps_layout.setSpacing(2)
        self.apps_layout.addStretch()  # Push buttons to left

        scroll.setWidget(self.apps_container)

        return scroll

    def _create_right_section(self) -> QWidget:
        """Create right section with system tray"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(5)

        # System tray
        self.system_tray = SystemTray(self)
        layout.addWidget(self.system_tray)

        # Show desktop button (thin button at far right)
        self.show_desktop_button = ShowDesktopButton(self)
        self.show_desktop_button.clicked.connect(self.show_desktop_clicked.emit)
        layout.addWidget(self.show_desktop_button)

        return container

    def _apply_style(self):
        """Apply taskbar style"""
        self.setStyleSheet("""
            #Taskbar {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 rgba(32, 32, 32, 230),
                    stop: 1 rgba(16, 16, 16, 230)
                );
                border-top: 1px solid rgba(255, 255, 255, 10);
            }

            #TaskbarAppsArea {
                background: transparent;
            }

            QScrollArea {
                background: transparent;
                border: none;
            }
        """)

    def _load_settings(self):
        """Load taskbar settings"""
        try:
            settings = self.settings_repo.get_taskbar_settings()

            self.is_locked = settings.get("locked", False)
            self.auto_hide = settings.get("auto_hide", False)
            self.position = settings.get("position", "bottom")

            # Load pinned apps
            self.pinned_apps = settings.get("pinned_apps", [])

            logger.info("Taskbar settings loaded")

        except Exception as e:
            logger.error(f"Error loading taskbar settings: {e}")

    def _setup_connections(self):
        """Setup signal connections"""
        # System tray connections
        if self.system_tray:
            self.system_tray.calendar_requested.connect(self._show_calendar)
            self.system_tray.notifications_clicked.connect(
                self.notification_clicked.emit
            )

    def _load_pinned_apps(self):
        """Load pinned apps to taskbar"""
        try:
            # Get pinned apps from repository
            pinned_apps = self.app_repo.get_pinned_apps()

            for app in pinned_apps:
                self.add_app_button(app, is_pinned=True)

            logger.info(f"Loaded {len(pinned_apps)} pinned apps")

        except Exception as e:
            logger.error(f"Error loading pinned apps: {e}")

    # ========== APP BUTTON MANAGEMENT ==========

    def add_app_button(
            self,
            app: AppModel,
            is_pinned: bool = False,
            is_running: bool = False
    ) -> TaskbarButton:
        """
        Add app button to taskbar

        Args:
            app: App model
            is_pinned: Is pinned app
            is_running: Is currently running

        Returns:
            TaskbarButton instance
        """
        # Check if button already exists
        if app.id in self.app_buttons:
            button = self.app_buttons[app.id]
            if is_running:
                button.set_running(True)
            return button

        # Create new button
        button = TaskbarButton(
            app_id=app.id,
            app_name=app.display_name,
            icon=get_app_icon(app.id),
            parent=self.apps_container
        )

        # Set states
        button.set_pinned(is_pinned)
        button.set_running(is_running)

        # Connect signals
        button.clicked.connect(lambda: self._handle_app_click(app.id))
        button.middle_clicked.connect(lambda: self._launch_new_instance(app.id))
        button.close_requested.connect(lambda: self.app_closed.emit(app.id))

        # Add to layout (before stretch)
        count = self.apps_layout.count()
        self.apps_layout.insertWidget(count - 1, button)

        # Store reference
        self.app_buttons[app.id] = button

        if is_pinned:
            self.pinned_apps.append(app.id)
        if is_running:
            self.running_apps.append(app.id)

        # Animate entrance
        fade_in_animation(button, duration=200)

        logger.debug(f"Added taskbar button: {app.display_name}")

        return button

    def remove_app_button(self, app_id: str):
        """Remove app button from taskbar"""
        if app_id not in self.app_buttons:
            return

        button = self.app_buttons[app_id]

        # Only remove if not pinned
        if not button.is_pinned:
            # Animate removal
            fade_out = QPropertyAnimation(button, b"opacity")
            fade_out.setDuration(200)
            fade_out.setEndValue(0)
            fade_out.finished.connect(lambda: self._remove_button_widget(app_id))
            fade_out.start()
        else:
            # Just mark as not running
            button.set_running(False)
            if app_id in self.running_apps:
                self.running_apps.remove(app_id)

    def _remove_button_widget(self, app_id: str):
        """Actually remove button widget"""
        if app_id in self.app_buttons:
            button = self.app_buttons[app_id]
            self.apps_layout.removeWidget(button)
            button.deleteLater()
            del self.app_buttons[app_id]

            if app_id in self.running_apps:
                self.running_apps.remove(app_id)

    def set_app_running(self, app_id: str, is_running: bool = True):
        """Mark app as running/not running"""
        if app_id in self.app_buttons:
            self.app_buttons[app_id].set_running(is_running)

            if is_running and app_id not in self.running_apps:
                self.running_apps.append(app_id)
            elif not is_running and app_id in self.running_apps:
                self.running_apps.remove(app_id)
        else:
            # Create button if doesn't exist
            app = self.app_repo.get_app_by_id(app_id)
            if app:
                self.add_app_button(app, is_running=is_running)

    def set_app_active(self, app_id: str):
        """Set app as active (focused)"""
        # Deactivate all other buttons
        for button_id, button in self.app_buttons.items():
            button.set_active(button_id == app_id)

    def flash_app_button(self, app_id: str):
        """Flash app button for attention"""
        if app_id in self.app_buttons:
            self.app_buttons[app_id].flash_attention()

    def update_app_badge(self, app_id: str, count: int):
        """Update notification badge on app button"""
        if app_id in self.app_buttons:
            self.app_buttons[app_id].set_badge_count(count)

    def pin_app(self, app_id: str):
        """Pin app to taskbar"""
        if app_id not in self.pinned_apps:
            self.pinned_apps.append(app_id)

            if app_id in self.app_buttons:
                self.app_buttons[app_id].set_pinned(True)
            else:
                # Add button if doesn't exist
                app = self.app_repo.get_app_by_id(app_id)
                if app:
                    self.add_app_button(app, is_pinned=True)

            # Save to settings
            self._save_pinned_apps()

    def unpin_app(self, app_id: str):
        """Unpin app from taskbar"""
        if app_id in self.pinned_apps:
            self.pinned_apps.remove(app_id)

            if app_id in self.app_buttons:
                button = self.app_buttons[app_id]
                button.set_pinned(False)

                # Remove if not running
                if not button.is_running:
                    self.remove_app_button(app_id)

            # Save to settings
            self._save_pinned_apps()

    def _save_pinned_apps(self):
        """Save pinned apps to settings"""
        try:
            self.settings_repo.save_taskbar_pinned_apps(self.pinned_apps)
            logger.info(f"Saved {len(self.pinned_apps)} pinned apps")
        except Exception as e:
            logger.error(f"Error saving pinned apps: {e}")

    # ========== EVENT HANDLERS ==========

    def _handle_app_click(self, app_id: str):
        """Handle app button click"""
        if app_id in self.app_buttons:
            button = self.app_buttons[app_id]

            if button.is_running:
                # Focus existing window
                self.app_focused.emit(app_id)
            else:
                # Launch app
                self.app_launched.emit(app_id)
                self.set_app_running(app_id, True)

    def _launch_new_instance(self, app_id: str):
        """Launch new instance of app (middle-click)"""
        self.app_launched.emit(app_id)

    def _update_clock(self):
        """Update clock in system tray"""
        if self.system_tray:
            self.system_tray.update_time()

    def _show_calendar(self):
        """Show calendar popup"""
        # This would show a calendar widget
        logger.info("Calendar requested")

    # ========== PUBLIC METHODS ==========

    def get_height(self) -> int:
        """Get taskbar height"""
        return self.height()

    def set_position(self, position: str):
        """
        Set taskbar position

        Args:
            position: bottom, top, left, right
        """
        self.position = position

        if position in ["left", "right"]:
            self.setFixedWidth(TASKBAR_HEIGHT)
            self.setMaximumHeight(16777215)  # Remove height constraint
        else:
            self.setFixedHeight(TASKBAR_HEIGHT)
            self.setMaximumWidth(16777215)  # Remove width constraint

    def set_auto_hide(self, enabled: bool):
        """Enable/disable auto-hide"""
        self.auto_hide = enabled

        if enabled:
            # Setup auto-hide behavior
            self._setup_auto_hide()

    def _setup_auto_hide(self):
        """Setup auto-hide behavior"""
        # This would implement auto-hide logic
        pass

    def lock_taskbar(self, locked: bool):
        """Lock/unlock taskbar"""
        self.is_locked = locked
        # Update UI based on lock state

    def show_jump_list(self, app_id: str):
        """Show jump list for app"""
        if app_id in self.app_buttons:
            self.app_buttons[app_id].show_jump_list()

    def arrange_buttons(self):
        """Arrange taskbar buttons"""
        # Sort buttons: pinned first, then running
        sorted_buttons = []

        # Add pinned apps first
        for app_id in self.pinned_apps:
            if app_id in self.app_buttons:
                sorted_buttons.append(self.app_buttons[app_id])

        # Add running non-pinned apps
        for app_id in self.running_apps:
            if app_id not in self.pinned_apps and app_id in self.app_buttons:
                sorted_buttons.append(self.app_buttons[app_id])

        # Rearrange in layout
        for i, button in enumerate(sorted_buttons):
            self.apps_layout.insertWidget(i, button)

    def clear_search(self):
        """Clear search box"""
        if self.search_box:
            self.search_box.clear()

    def focus_search(self):
        """Focus search box"""
        if self.search_box:
            self.search_box.setFocus()

    # ========== PROPERTIES ==========

    def get_running_apps_count(self) -> int:
        """Get number of running apps"""
        return len(self.running_apps)

    def get_pinned_apps_count(self) -> int:
        """Get number of pinned apps"""
        return len(self.pinned_apps)


# ========== START BUTTON ==========

class StartButton(QPushButton):
    """Windows-style Start button"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("StartButton")
        self.setFixedSize(48, TASKBAR_HEIGHT - 1)
        self.setCursor(Qt.PointingHandCursor)

        # Set Windows logo icon
        self.setIcon(load_icon("windows"))
        self.setIconSize(QSize(24, 24))

        # Tooltip
        self.setToolTip("Start")

        # Style
        self.setStyleSheet("""
            #StartButton {
                background: transparent;
                border: none;
                border-radius: 4px;
                padding: 8px;
            }
            #StartButton:hover {
                background: rgba(255, 255, 255, 10);
            }
            #StartButton:pressed {
                background: rgba(255, 255, 255, 20);
            }
        """)


# ========== SEARCH BOX ==========

class TaskbarSearchBox(QLineEdit):
    """Taskbar search box"""

    # Signals
    focus_gained = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("TaskbarSearch")
        self.setFixedWidth(300)
        self.setFixedHeight(32)

        # Placeholder
        self.setPlaceholderText("🔍 Tìm kiếm")

        # Style
        self.setStyleSheet("""
            #TaskbarSearch {
                background: rgba(255, 255, 255, 10);
                border: 1px solid rgba(255, 255, 255, 20);
                border-radius: 16px;
                padding: 0 16px;
                color: white;
                font-size: 13px;
            }
            #TaskbarSearch:hover {
                background: rgba(255, 255, 255, 15);
                border: 1px solid rgba(255, 255, 255, 30);
            }
            #TaskbarSearch:focus {
                background: rgba(255, 255, 255, 95);
                color: black;
                border: 2px solid #0078d4;
            }
        """)

    def focusInEvent(self, event):
        """Handle focus in"""
        super().focusInEvent(event)
        self.focus_gained.emit()

    def keyPressEvent(self, event):
        """Handle key press"""
        if event.key() == Qt.Key_Escape:
            self.clear()
            self.clearFocus()
        else:
            super().keyPressEvent(event)


# ========== SHOW DESKTOP BUTTON ==========

class ShowDesktopButton(QToolButton):
    """Thin button at taskbar edge to show desktop"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("ShowDesktopButton")
        self.setFixedSize(7, TASKBAR_HEIGHT - 1)
        self.setCursor(Qt.PointingHandCursor)

        # Tooltip
        self.setToolTip("Show Desktop")

        # Style
        self.setStyleSheet("""
            #ShowDesktopButton {
                background: rgba(255, 255, 255, 5);
                border: none;
                border-left: 1px solid rgba(255, 255, 255, 10);
            }
            #ShowDesktopButton:hover {
                background: rgba(255, 255, 255, 20);
            }
            #ShowDesktopButton:pressed {
                background: rgba(255, 255, 255, 30);
            }
        """)


# ========== NOTIFICATION AREA ==========

class NotificationArea(QWidget):
    """Notification area in taskbar"""

    # Signals
    notification_clicked = Signal(int)  # notification_id

    def __init__(self, parent=None):
        super().__init__(parent)

        self.notification_count = 0

        self.setFixedSize(32, 32)
        self.setCursor(Qt.PointingHandCursor)

        # Tooltip
        self.setToolTip("Notifications")

    def set_count(self, count: int):
        """Set notification count"""
        self.notification_count = count
        self.setToolTip(f"{count} new notifications")
        self.update()

    def paintEvent(self, event):
        """Paint notification icon with badge"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw notification icon
        icon = load_icon("notification")
        icon.paint(painter, self.rect().adjusted(4, 4, -4, -4))

        # Draw badge if count > 0
        if self.notification_count > 0:
            # Badge background
            badge_rect = QRect(18, 2, 14, 14)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(255, 0, 0)))
            painter.drawEllipse(badge_rect)

            # Badge text
            painter.setPen(Qt.white)
            painter.setFont(QFont("Arial", 8, QFont.Bold))

            text = str(self.notification_count) if self.notification_count < 10 else "9+"
            painter.drawText(badge_rect, Qt.AlignCenter, text)

    def mousePressEvent(self, event):
        """Handle click"""
        if event.button() == Qt.LeftButton:
            self.notification_clicked.emit(self.notification_count)
