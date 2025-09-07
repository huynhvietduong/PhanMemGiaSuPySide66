# ui_qt/windows/dashboard_window_qt/views/dashboard_event_handler.py
"""
Dashboard Event Handler - Xử lý global events cho dashboard
Quản lý keyboard shortcuts, system events, drag & drop, clipboard, notifications
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import logging

from PySide6.QtWidgets import (
    QWidget, QMainWindow, QApplication, QMessageBox,
    QSystemTrayIcon, QMenu,  QToolTip
)
from PySide6.QtCore import (
    Qt, QObject, QEvent, QTimer, Signal,
    QPoint, QMimeData, QUrl, QByteArray,
    QThread, QSettings, QDateTime
)
from PySide6.QtGui import (
    QKeyEvent, QMouseEvent, QWheelEvent, QFocusEvent,
    QDragEnterEvent, QDragMoveEvent, QDropEvent,
    QClipboard, QAction, QKeySequence, QIcon,
    QCloseEvent, QShowEvent, QHideEvent, QShortcut
)

# Import utils
from ..utils.constants import (
    DOUBLE_CLICK_INTERVAL, TOOLTIP_DELAY,
    MAX_RECENT_ITEMS, AUTO_SAVE_INTERVAL
)
from ..utils.assets import load_icon
from ..utils.helpers import show_notification, play_sound

# Logger
logger = logging.getLogger(__name__)


# ========== ENUMS ==========

class EventType(Enum):
    """Types of events"""
    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    DRAG_DROP = "drag_drop"
    CLIPBOARD = "clipboard"
    SYSTEM = "system"
    WINDOW = "window"
    CUSTOM = "custom"


class EventPriority(Enum):
    """Event priority levels"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class NotificationType(Enum):
    """Notification types"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


# ========== EVENT INFO ==========

@dataclass
class EventInfo:
    """Information about an event"""
    event_type: EventType
    event_name: str
    timestamp: datetime
    source: Optional[QObject] = None
    data: Optional[Any] = None
    priority: EventPriority = EventPriority.NORMAL
    handled: bool = False


# ========== SHORTCUT MANAGER ==========

class ShortcutManager:
    """Manager for keyboard shortcuts"""

    def __init__(self, parent: QWidget = None):
        """Initialize shortcut manager"""
        self.parent = parent
        self.shortcuts: Dict[str, QShortcut] = {}
        self.actions: Dict[str, Callable] = {}

        # Default shortcuts
        self._register_default_shortcuts()

        logger.debug("ShortcutManager initialized")

    def _register_default_shortcuts(self):
        """Register default keyboard shortcuts"""
        defaults = {
            # Window management
            "Alt+Tab": "switch_window",
            "Alt+F4": "close_window",
            "F11": "toggle_fullscreen",
            "Win+D": "show_desktop",
            "Win+L": "lock_screen",

            # Navigation
            "Alt+Left": "navigate_back",
            "Alt+Right": "navigate_forward",
            "Alt+Home": "go_home",
            "F5": "refresh",

            # File operations
            "Ctrl+N": "new_file",
            "Ctrl+O": "open_file",
            "Ctrl+S": "save_file",
            "Ctrl+Shift+S": "save_as",

            # Edit operations
            "Ctrl+Z": "undo",
            "Ctrl+Y": "redo",
            "Ctrl+X": "cut",
            "Ctrl+C": "copy",
            "Ctrl+V": "paste",
            "Ctrl+A": "select_all",

            # Search
            "Ctrl+F": "find",
            "F3": "find_next",
            "Shift+F3": "find_previous",

            # View
            "Ctrl++": "zoom_in",
            "Ctrl+-": "zoom_out",
            "Ctrl+0": "zoom_reset",

            # Special
            "F1": "show_help",
            "Esc": "escape",
            "Ctrl+Shift+Esc": "task_manager",
        }

        for key_seq, action_name in defaults.items():
            self.register_shortcut(key_seq, action_name)

    def register_shortcut(
            self,
            key_sequence: str,
            action_name: str,
            callback: Optional[Callable] = None
    ) -> QShortcut:
        """
        Register a keyboard shortcut

        Args:
            key_sequence: Key sequence string (e.g., "Ctrl+S")
            action_name: Action name identifier
            callback: Optional callback function

        Returns:
            QShortcut instance
        """
        if self.parent:
            shortcut = QShortcut(QKeySequence(key_sequence), self.parent)
            shortcut.setContext(Qt.ApplicationShortcut)

            # Store references
            self.shortcuts[action_name] = shortcut

            if callback:
                self.actions[action_name] = callback
                shortcut.activated.connect(callback)

            logger.debug(f"Registered shortcut: {key_sequence} -> {action_name}")
            return shortcut

        return None

    def unregister_shortcut(self, action_name: str):
        """Unregister a shortcut"""
        if action_name in self.shortcuts:
            self.shortcuts[action_name].deleteLater()
            del self.shortcuts[action_name]

            if action_name in self.actions:
                del self.actions[action_name]

    def set_action(self, action_name: str, callback: Callable):
        """Set action callback"""
        self.actions[action_name] = callback

        if action_name in self.shortcuts:
            # Disconnect old connections
            try:
                self.shortcuts[action_name].activated.disconnect()
            except:
                pass

            # Connect new callback
            self.shortcuts[action_name].activated.connect(callback)

    def trigger_action(self, action_name: str):
        """Manually trigger an action"""
        if action_name in self.actions:
            self.actions[action_name]()
            logger.debug(f"Triggered action: {action_name}")

    def is_enabled(self, action_name: str) -> bool:
        """Check if shortcut is enabled"""
        if action_name in self.shortcuts:
            return self.shortcuts[action_name].isEnabled()
        return False

    def set_enabled(self, action_name: str, enabled: bool):
        """Enable/disable shortcut"""
        if action_name in self.shortcuts:
            self.shortcuts[action_name].setEnabled(enabled)


# ========== CLIPBOARD MANAGER ==========

class ClipboardManager(QObject):
    """Manager for clipboard operations"""

    # Signals
    clipboard_changed = Signal(str)  # text
    clipboard_data_available = Signal(QMimeData)

    def __init__(self, parent=None):
        """Initialize clipboard manager"""
        super().__init__(parent)

        self.clipboard = QApplication.clipboard()
        self.history: List[str] = []
        self.max_history = MAX_RECENT_ITEMS

        # Connect signals
        self.clipboard.dataChanged.connect(self._on_clipboard_changed)

        logger.debug("ClipboardManager initialized")

    def _on_clipboard_changed(self):
        """Handle clipboard content change"""
        mime_data = self.clipboard.mimeData()

        if mime_data.hasText():
            text = mime_data.text()

            # Add to history
            if text and text not in self.history:
                self.history.insert(0, text)
                if len(self.history) > self.max_history:
                    self.history.pop()

            self.clipboard_changed.emit(text)

        self.clipboard_data_available.emit(mime_data)

    def copy_text(self, text: str):
        """Copy text to clipboard"""
        self.clipboard.setText(text)
        logger.debug(f"Copied text: {text[:50]}...")

    def copy_files(self, file_paths: List[str]):
        """Copy files to clipboard"""
        mime_data = QMimeData()
        urls = [QUrl.fromLocalFile(path) for path in file_paths]
        mime_data.setUrls(urls)
        self.clipboard.setMimeData(mime_data)
        logger.debug(f"Copied {len(file_paths)} files")

    def paste(self) -> Optional[Any]:
        """Get clipboard content"""
        mime_data = self.clipboard.mimeData()

        if mime_data.hasText():
            return mime_data.text()
        elif mime_data.hasUrls():
            return [url.toLocalFile() for url in mime_data.urls()]
        elif mime_data.hasImage():
            return mime_data.imageData()

        return None

    def clear(self):
        """Clear clipboard"""
        self.clipboard.clear()
        logger.debug("Clipboard cleared")

    def get_history(self) -> List[str]:
        """Get clipboard history"""
        return self.history.copy()

    def clear_history(self):
        """Clear clipboard history"""
        self.history.clear()


# ========== NOTIFICATION MANAGER ==========

class NotificationManager(QObject):
    """Manager for system notifications"""

    # Signals
    notification_clicked = Signal(str)  # notification_id
    notification_closed = Signal(str)  # notification_id

    def __init__(self, parent=None):
        """Initialize notification manager"""
        super().__init__(parent)

        self.notifications: Dict[str, Dict] = {}
        self.tray_icon: Optional[QSystemTrayIcon] = None

        # Create system tray icon if supported
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._setup_tray_icon()

        logger.debug("NotificationManager initialized")

    def _setup_tray_icon(self):
        """Setup system tray icon"""
        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(load_icon("app"))
        self.tray_icon.setToolTip("Dashboard")

        # Connect signals
        self.tray_icon.messageClicked.connect(self._on_message_clicked)

        # Create context menu
        menu = QMenu()

        show_action = QAction("Show Dashboard", menu)
        show_action.triggered.connect(self._show_dashboard)
        menu.addAction(show_action)

        menu.addSeparator()

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def show_notification(
            self,
            title: str,
            message: str,
            notification_type: NotificationType = NotificationType.INFO,
            duration: int = 5000,
            notification_id: Optional[str] = None
    ) -> str:
        """
        Show a notification

        Args:
            title: Notification title
            message: Notification message
            notification_type: Type of notification
            duration: Duration in milliseconds
            notification_id: Optional ID

        Returns:
            Notification ID
        """
        if not notification_id:
            notification_id = f"notif_{datetime.now().timestamp()}"

        # Store notification
        self.notifications[notification_id] = {
            'title': title,
            'message': message,
            'type': notification_type,
            'timestamp': datetime.now()
        }

        # Show system tray notification if available
        if self.tray_icon and QSystemTrayIcon.isSystemTrayAvailable():
            icon_type = {
                NotificationType.INFO: QSystemTrayIcon.Information,
                NotificationType.SUCCESS: QSystemTrayIcon.Information,
                NotificationType.WARNING: QSystemTrayIcon.Warning,
                NotificationType.ERROR: QSystemTrayIcon.Critical
            }.get(notification_type, QSystemTrayIcon.Information)

            self.tray_icon.showMessage(title, message, icon_type, duration)

        # Play sound if enabled
        if notification_type == NotificationType.ERROR:
            play_sound("error")
        elif notification_type == NotificationType.SUCCESS:
            play_sound("success")

        logger.info(f"Notification shown: {title}")

        # Auto-remove after duration
        QTimer.singleShot(duration, lambda: self._remove_notification(notification_id))

        return notification_id

    def _on_message_clicked(self):
        """Handle notification click"""
        # Get most recent notification
        if self.notifications:
            notification_id = list(self.notifications.keys())[-1]
            self.notification_clicked.emit(notification_id)

    def _remove_notification(self, notification_id: str):
        """Remove notification"""
        if notification_id in self.notifications:
            del self.notifications[notification_id]
            self.notification_closed.emit(notification_id)

    def _show_dashboard(self):
        """Show main dashboard window"""
        # This would be connected to show the main window
        pass

    def get_notifications(self) -> List[Dict]:
        """Get all notifications"""
        return list(self.notifications.values())

    def clear_all(self):
        """Clear all notifications"""
        self.notifications.clear()


# ========== MAIN EVENT HANDLER ==========

class DashboardEventHandler(QObject):
    """
    Main event handler for dashboard
    Coordinates all event handling and dispatching
    """

    # Signals
    event_received = Signal(EventInfo)
    event_handled = Signal(EventInfo)

    # Global events
    global_key_pressed = Signal(QKeyEvent)
    global_mouse_clicked = Signal(QMouseEvent)
    files_dropped = Signal(list)  # file_paths

    # System events
    system_idle = Signal(int)  # idle_seconds
    system_resumed = Signal()
    screen_locked = Signal()
    screen_unlocked = Signal()

    # Window events
    window_activated = Signal(str)  # window_id
    window_deactivated = Signal(str)  # window_id

    def __init__(self, main_window: QMainWindow = None, parent=None):
        """
        Initialize Dashboard Event Handler

        Args:
            main_window: Main window to handle events for
            parent: Parent object
        """
        super().__init__(parent)

        # Main window reference
        self.main_window = main_window

        # Managers
        self.shortcut_manager = ShortcutManager(main_window)
        self.clipboard_manager = ClipboardManager(self)
        self.notification_manager = NotificationManager(self)

        # Event queue
        self.event_queue: List[EventInfo] = []
        self.event_handlers: Dict[str, List[Callable]] = {}

        # State
        self.idle_timer = QTimer()
        self.idle_timer.timeout.connect(self._check_idle)
        self.idle_seconds = 0
        self.last_activity = datetime.now()

        # Settings
        self.settings = QSettings("TutorSoft", "Dashboard")

        # Setup
        if self.main_window:
            self._setup_main_window()

        self._setup_global_shortcuts()
        self._setup_timers()

        logger.info("DashboardEventHandler initialized")

    def _setup_main_window(self):
        """Setup main window event handling"""
        # Install event filter
        self.main_window.installEventFilter(self)

        # Enable drag & drop
        self.main_window.setAcceptDrops(True)

    def _setup_global_shortcuts(self):
        """Setup global keyboard shortcuts"""
        # Window management
        self.shortcut_manager.set_action("show_desktop", self._show_desktop)
        self.shortcut_manager.set_action("toggle_fullscreen", self._toggle_fullscreen)
        self.shortcut_manager.set_action("close_window", self._close_active_window)

        # Navigation
        self.shortcut_manager.set_action("refresh", self._refresh)

        # Clipboard
        self.shortcut_manager.set_action("copy", self._copy)
        self.shortcut_manager.set_action("paste", self._paste)
        self.shortcut_manager.set_action("cut", self._cut)

        # Help
        self.shortcut_manager.set_action("show_help", self._show_help)

        # Task manager
        self.shortcut_manager.set_action("task_manager", self._show_task_manager)

    def _setup_timers(self):
        """Setup timers for periodic checks"""
        # Idle detection
        self.idle_timer.start(1000)  # Check every second

        # Auto-save timer
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self._auto_save)
        self.auto_save_timer.start(AUTO_SAVE_INTERVAL)

    # ========== EVENT FILTER ==========

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Main event filter"""
        # Track activity for idle detection
        if event.type() in [QEvent.KeyPress, QEvent.MouseMove, QEvent.MouseButtonPress]:
            self.last_activity = datetime.now()
            self.idle_seconds = 0

        # Handle specific events
        if obj == self.main_window:
            if event.type() == QEvent.DragEnter:
                return self._handle_drag_enter(event)
            elif event.type() == QEvent.DragMove:
                return self._handle_drag_move(event)
            elif event.type() == QEvent.Drop:
                return self._handle_drop(event)
            elif event.type() == QEvent.KeyPress:
                return self._handle_key_press(event)
            elif event.type() == QEvent.Close:
                return self._handle_close(event)
            elif event.type() == QEvent.WindowActivate:
                self._handle_window_activate()
            elif event.type() == QEvent.WindowDeactivate:
                self._handle_window_deactivate()

        return False

    # ========== DRAG & DROP HANDLING ==========

    def _handle_drag_enter(self, event: QDragEnterEvent) -> bool:
        """Handle drag enter event"""
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
            return True
        return False

    def _handle_drag_move(self, event: QDragMoveEvent) -> bool:
        """Handle drag move event"""
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
            return True
        return False

    def _handle_drop(self, event: QDropEvent) -> bool:
        """Handle drop event"""
        mime_data = event.mimeData()

        if mime_data.hasUrls():
            # Get file paths
            file_paths = []
            for url in mime_data.urls():
                if url.isLocalFile():
                    file_paths.append(url.toLocalFile())

            if file_paths:
                # Emit signal
                self.files_dropped.emit(file_paths)

                # Create event info
                event_info = EventInfo(
                    event_type=EventType.DRAG_DROP,
                    event_name="files_dropped",
                    timestamp=datetime.now(),
                    data={'files': file_paths}
                )

                self._dispatch_event(event_info)

                event.acceptProposedAction()
                return True

        elif mime_data.hasText():
            text = mime_data.text()

            # Handle text drop
            event_info = EventInfo(
                event_type=EventType.DRAG_DROP,
                event_name="text_dropped",
                timestamp=datetime.now(),
                data={'text': text}
            )

            self._dispatch_event(event_info)

            event.acceptProposedAction()
            return True

        return False

    # ========== KEYBOARD HANDLING ==========

    def _handle_key_press(self, event: QKeyEvent) -> bool:
        """Handle global key press"""
        # Emit signal
        self.global_key_pressed.emit(event)

        # Create event info
        event_info = EventInfo(
            event_type=EventType.KEYBOARD,
            event_name="key_pressed",
            timestamp=datetime.now(),
            data={
                'key': event.key(),
                'modifiers': event.modifiers(),
                'text': event.text()
            }
        )

        self._dispatch_event(event_info)

        return False

    # ========== WINDOW EVENTS ==========

    def _handle_close(self, event: QCloseEvent) -> bool:
        """Handle window close event"""
        # Auto-save before closing
        self._auto_save()

        # Show confirmation if needed
        if self.settings.value("confirm_exit", True):
            reply = QMessageBox.question(
                self.main_window,
                "Confirm Exit",
                "Are you sure you want to exit?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.No:
                event.ignore()
                return True

        return False

    def _handle_window_activate(self):
        """Handle window activation"""
        self.window_activated.emit("main")
        logger.debug("Main window activated")

    def _handle_window_deactivate(self):
        """Handle window deactivation"""
        self.window_deactivated.emit("main")
        logger.debug("Main window deactivated")

    # ========== EVENT DISPATCHING ==========

    def register_handler(self, event_name: str, handler: Callable):
        """
        Register an event handler

        Args:
            event_name: Event name to handle
            handler: Handler function
        """
        if event_name not in self.event_handlers:
            self.event_handlers[event_name] = []

        self.event_handlers[event_name].append(handler)
        logger.debug(f"Registered handler for: {event_name}")

    def unregister_handler(self, event_name: str, handler: Callable):
        """Unregister an event handler"""
        if event_name in self.event_handlers:
            if handler in self.event_handlers[event_name]:
                self.event_handlers[event_name].remove(handler)

    def _dispatch_event(self, event_info: EventInfo):
        """Dispatch event to handlers"""
        # Add to queue
        self.event_queue.append(event_info)
        if len(self.event_queue) > 100:  # Limit queue size
            self.event_queue.pop(0)

        # Emit general signal
        self.event_received.emit(event_info)

        # Call specific handlers
        if event_info.event_name in self.event_handlers:
            for handler in self.event_handlers[event_info.event_name]:
                try:
                    handler(event_info)
                    event_info.handled = True
                except Exception as e:
                    logger.error(f"Error in event handler: {e}")

        # Emit handled signal
        if event_info.handled:
            self.event_handled.emit(event_info)

    def emit_custom_event(self, event_name: str, data: Any = None):
        """Emit a custom event"""
        event_info = EventInfo(
            event_type=EventType.CUSTOM,
            event_name=event_name,
            timestamp=datetime.now(),
            data=data
        )

        self._dispatch_event(event_info)

    # ========== IDLE DETECTION ==========

    def _check_idle(self):
        """Check for idle state"""
        now = datetime.now()
        idle_duration = (now - self.last_activity).total_seconds()

        self.idle_seconds = int(idle_duration)

        # Emit idle signal at certain thresholds
        if self.idle_seconds == 60:  # 1 minute
            self.system_idle.emit(60)
        elif self.idle_seconds == 300:  # 5 minutes
            self.system_idle.emit(300)
        elif self.idle_seconds == 900:  # 15 minutes
            self.system_idle.emit(900)

    def reset_idle(self):
        """Reset idle timer"""
        self.last_activity = datetime.now()
        self.idle_seconds = 0

    # ========== ACTION HANDLERS ==========

    def _show_desktop(self):
        """Show desktop action"""
        self.emit_custom_event("show_desktop")
        logger.info("Show desktop triggered")

    def _toggle_fullscreen(self):
        """Toggle fullscreen action"""
        if self.main_window:
            if self.main_window.isFullScreen():
                self.main_window.showNormal()
            else:
                self.main_window.showFullScreen()

    def _close_active_window(self):
        """Close active window"""
        self.emit_custom_event("close_active_window")

    def _refresh(self):
        """Refresh action"""
        self.emit_custom_event("refresh")
        logger.info("Refresh triggered")

    def _copy(self):
        """Copy action"""
        self.emit_custom_event("copy")

    def _paste(self):
        """Paste action"""
        data = self.clipboard_manager.paste()
        self.emit_custom_event("paste", data)

    def _cut(self):
        """Cut action"""
        self.emit_custom_event("cut")

    def _show_help(self):
        """Show help"""
        self.notification_manager.show_notification(
            "Help",
            "Press F1 for help\nCtrl+Shift+Esc for Task Manager",
            NotificationType.INFO
        )

    def _show_task_manager(self):
        """Show task manager"""
        self.emit_custom_event("show_task_manager")
        logger.info("Task manager requested")

    def _auto_save(self):
        """Auto-save action"""
        self.emit_custom_event("auto_save")
        logger.debug("Auto-save triggered")

    # ========== PUBLIC METHODS ==========

    def show_notification(self, title: str, message: str, type: NotificationType = NotificationType.INFO):
        """Show a notification"""
        return self.notification_manager.show_notification(title, message, type)

    def copy_to_clipboard(self, text: str):
        """Copy text to clipboard"""
        self.clipboard_manager.copy_text(text)

    def get_clipboard_content(self) -> Any:
        """Get clipboard content"""
        return self.clipboard_manager.paste()

    def register_shortcut(self, key_sequence: str, callback: Callable):
        """Register a keyboard shortcut"""
        action_name = f"custom_{datetime.now().timestamp()}"
        return self.shortcut_manager.register_shortcut(key_sequence, action_name, callback)

    def get_idle_seconds(self) -> int:
        """Get idle time in seconds"""
        return self.idle_seconds

    def get_event_history(self, limit: int = 50) -> List[EventInfo]:
        """Get event history"""
        return self.event_queue[-limit:]