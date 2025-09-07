# ui_qt/windows/dashboard_window_qt/services/window_manager_service.py
"""
Window Manager Service - Quản lý MDI child windows
Xử lý tạo, đóng, minimize, maximize, arrange windows trong dashboard
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import logging

from PySide6.QtWidgets import (
    QMdiArea, QMdiSubWindow, QWidget, QMainWindow,
    QMenuBar, QToolBar, QStatusBar, QMessageBox,
    QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QPushButton, QSizePolicy
)
from PySide6.QtCore import (
    Qt, QSize, QPoint, QRect, QTimer,
    Signal, QObject, QThread, QProcess,
    QPropertyAnimation, QEasingCurve,
    QParallelAnimationGroup, QSequentialAnimationGroup,QEvent
)
from PySide6.QtGui import (
    QIcon, QPixmap, QAction, QKeySequence,
    QCloseEvent, QResizeEvent, QPainter,
    QBrush, QColor, QPen, QFont,
)

# Import utils
from ..utils.constants import (
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT,
    WINDOW_ANIMATION_DURATION
)
from ..utils.assets import get_app_icon
from ..utils.helpers import create_window_id

# Import repositories
from ..repositories.app_repository import AppRepository, AppModel

# Logger
logger = logging.getLogger(__name__)


# ========== ENUMS ==========

class WindowState(Enum):
    """Window states"""
    NORMAL = "normal"
    MINIMIZED = "minimized"
    MAXIMIZED = "maximized"
    FULLSCREEN = "fullscreen"
    HIDDEN = "hidden"


class WindowArrangement(Enum):
    """Window arrangement modes"""
    CASCADE = "cascade"
    TILE_HORIZONTAL = "tile_horizontal"
    TILE_VERTICAL = "tile_vertical"
    TILE_GRID = "tile_grid"


class WindowType(Enum):
    """Types of windows"""
    APP = "app"  # Application window
    DOCUMENT = "document"  # Document window
    DIALOG = "dialog"  # Dialog window
    TOOL = "tool"  # Tool window
    WIDGET = "widget"  # Widget window


# ========== WINDOW INFO ==========

@dataclass
class WindowInfo:
    """Information about a window"""
    window_id: str
    app_id: str
    title: str
    window_type: WindowType
    state: WindowState
    position: QPoint
    size: QSize
    z_order: int
    created_at: datetime
    last_active: datetime
    is_active: bool = False
    is_pinned: bool = False
    process: Optional[QProcess] = None


# ========== APP WINDOW ==========

class AppWindow(QMdiSubWindow):
    """
    Custom MDI sub-window for applications
    Enhanced with custom title bar and controls
    """

    # Signals
    window_activated = Signal(str)  # window_id
    window_closed = Signal(str)  # window_id
    window_state_changed = Signal(str, WindowState)  # window_id, state

    def __init__(
            self,
            window_id: str,
            app_id: str,
            title: str,
            icon: Optional[QIcon] = None,
            parent=None
    ):
        """Initialize app window"""
        super().__init__(parent)

        # Properties
        self.window_id = window_id
        self.app_id = app_id
        self.window_title = title
        self.window_icon = icon or get_app_icon(app_id)
        self.is_manually_hidden = False
        # State
        self.is_active = False
        self.is_pinned = False
        self.window_state = WindowState.NORMAL
        # Set window properties
        self.setWindowTitle(title)
        self.setAttribute(Qt.WA_DeleteOnClose)
        # Process (if external app)
        self.process = None

        # Setup
        self._setup_window()

        logger.debug(f"AppWindow created: {window_id} - {title}")

    def _setup_window(self):
        """Setup window properties"""
        # Window properties
        self.setWindowTitle(self.window_title)
        self.setWindowIcon(self.window_icon)

        # Set minimum size
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        # Set object name for styling
        self.setObjectName("AppWindow")

        # Style
        self.setStyleSheet("""
            QMdiSubWindow {
                background: white;
                border: 1px solid #ccc;
            }
            QMdiSubWindow::title {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f0f0f0,
                    stop: 1 #e0e0e0
                );
                padding: 5px;
            }
        """)

        # Create content widget
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.setWidget(self.content_widget)

    def set_content(self, widget: QWidget):
        """Set window content"""
        # Clear existing content
        for i in reversed(range(self.content_layout.count())):
            self.content_layout.itemAt(i).widget().setParent(None)

        # Add new content
        self.content_layout.addWidget(widget)

    def embed_process(self, process: QProcess):
        """Embed external process window"""
        self.process = process
        # This would use Windows API to embed the process window
        # For now, just store the reference

    def activate(self):
        """Activate this window"""
        self.is_active = True
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.window_activated.emit(self.window_id)

    # Override showMinimized để ẩn hoàn toàn thay vì minimize
    def showMinimized(self):
        """Override showMinimized - ẩn hoàn toàn thay vì minimize"""
        # Ẩn window hoàn toàn
        self.hide()

        # Update state
        self.window_state = WindowState.MINIMIZED

        # Emit signal
        self.window_state_changed.emit(self.window_id, WindowState.MINIMIZED)

        logger.debug(f"Window {self.window_id} hidden instead of minimized")

    # Override showNormal để restore từ hidden
    def showNormal(self):
        """Override showNormal - restore từ hidden state"""
        # Hiện window nếu đang ẩn
        if self.isHidden():
            self.show()

        # Gọi super để restore normal state
        super().showNormal()

        # Update state
        self.window_state = WindowState.NORMAL

        # Focus window
        self.raise_()
        self.activateWindow()
    def closeEvent(self, event: QCloseEvent):
        """Handle window close"""
        # Terminate process if exists
        if self.process and self.process.state() == QProcess.Running:
            self.process.terminate()
            if not self.process.waitForFinished(5000):
                self.process.kill()

        self.window_closed.emit(self.window_id)
        super().closeEvent(event)

    def setVisible(self, visible):
        """Override setVisible để control khi nào window được hiện"""
        # Nếu đang ẩn thủ công, không cho phép tự động hiện
        if visible and self.is_manually_hidden:
            return  # Chặn không cho hiện
        super().setVisible(visible)

    # Override showEvent để chặn
    def showEvent(self, event):
        """Override showEvent để chặn tự động hiện"""
        if self.is_manually_hidden:
            event.ignore()  # Ignore event show
            return
        super().showEvent(event)

    # Phương thức ẩn thủ công
    def hide_manually(self):
        """Ẩn window và đánh dấu là ẩn thủ công"""
        self.is_manually_hidden = True
        self.hide()

    # Phương thức hiện thủ công
    def show_manually(self):
        """Hiện window và xóa đánh dấu ẩn thủ công"""
        self.is_manually_hidden = False
        self.show()
        self.showNormal()

    def changeEvent(self, event):
        """Override changeEvent để track state changes"""
        if event.type() == QEvent.WindowStateChange:
            # Nếu window bị minimize
            if self.windowState() & Qt.WindowMinimized:
                # Thay vì minimize, ẩn hoàn toàn
                self.hide()
                self.is_manually_hidden = True
                event.accept()
                return

        super().changeEvent(event)
# ========== WINDOW MANAGER SERVICE ==========

class WindowManagerService(QObject):
    """
    Service for managing MDI windows in dashboard
    Handles window lifecycle, arrangement, and state
    """

    # Signals
    window_created = Signal(str, WindowInfo)  # window_id, info
    window_closed = Signal(str)  # window_id
    window_activated = Signal(str)  # window_id
    active_window_changed = Signal(str)  # window_id
    windows_arranged = Signal(WindowArrangement)

    def __init__(self, mdi_area: Optional[QMdiArea] = None, parent=None):
        """
        Initialize Window Manager Service

        Args:
            mdi_area: MDI area widget to manage
            parent: Parent object
        """
        super().__init__(parent)

        # MDI area reference
        self.mdi_area = mdi_area

        # Window storage
        self.windows: Dict[str, AppWindow] = {}
        self.window_info: Dict[str, WindowInfo] = {}
        self.windows_state_before_desktop = {}

        # Thêm tracking cho windows bị minimize thủ công
        self.manually_minimized_windows = set()  # Set các window_id đã minimize thủ công
        # State
        self.active_window_id: Optional[str] = None
        self.z_order_counter = 0

        # App repository
        self.app_repo = AppRepository()

        # Animations
        self.animations = []

        # Setup MDI area if provided
        if self.mdi_area:
            self._setup_mdi_area()

        logger.info("WindowManagerService initialized")

    def _setup_mdi_area(self):
        """Setup MDI area properties"""
        # Set view mode
        self.mdi_area.setViewMode(QMdiArea.SubWindowView)

        # Set background
        self.mdi_area.setBackground(QBrush(QColor(240, 240, 240)))
        # Connect to subWindowActivated signal
        self.mdi_area.subWindowActivated.connect(self._on_mdi_window_activated)
        # Enable tab view option
        self.mdi_area.setTabsClosable(True)
        self.mdi_area.setTabsMovable(True)

        # Connect signals
        self.mdi_area.subWindowActivated.connect(self._on_window_activated)
        # Khi có window mới được thêm vào MDI area
        self.mdi_area.subWindowActivated.connect(self._connect_window_signals)
    def set_mdi_area(self, mdi_area: QMdiArea):
        """Set MDI area to manage"""
        self.mdi_area = mdi_area
        self._setup_mdi_area()

    # Connect signals cho từng MDI window
    def _connect_window_signals(self, mdi_window):
        """Connect signals để track window state changes"""
        if not mdi_window:
            return

        # Tìm window_id từ mdi_window
        window_id = None
        for wid, window in self.windows.items():
            if window == mdi_window:
                window_id = wid
                break

        if not window_id:
            return

        # Override windowStateChanged để track minimize
        def on_state_changed():
            if mdi_window.isMinimized():
                # Window vừa được minimize từ title bar
                self.mark_manually_minimized(window_id)
            elif not mdi_window.isMinimized() and window_id in self.manually_minimized_windows:
                # Window được restore từ minimize
                self.unmark_manually_minimized(window_id)

        # Connect signal
        mdi_window.windowStateChanged.connect(on_state_changed)
    # ========== WINDOW CREATION ==========

    def create_window(
            self,
            app_id: str,
            title: Optional[str] = None,
            window_type: WindowType = WindowType.APP,
            size: Optional[QSize] = None,
            position: Optional[QPoint] = None,
            content: Optional[QWidget] = None
    ) -> Optional[str]:
        """
        Create a new window

        Args:
            app_id: Application ID
            title: Window title
            window_type: Type of window
            size: Initial size
            position: Initial position
            content: Content widget

        Returns:
            Window ID if successful
        """
        if not self.mdi_area:
            logger.error("No MDI area set")
            return None

        try:
            # Get app info
            app = self.app_repo.get_app_by_id(app_id)
            if not app and window_type == WindowType.APP:
                logger.error(f"App not found: {app_id}")
                return None

            # Generate window ID
            window_id = create_window_id(app_id)

            # Determine title
            if not title:
                title = app.display_name if app else app_id

            # Create window
            window = AppWindow(
                window_id=window_id,
                app_id=app_id,
                title=title,
                icon=get_app_icon(app_id) if app else None,
                parent=self.mdi_area
            )

            # Set content if provided
            if content:
                window.set_content(content)

            # Set size
            if size:
                window.resize(size)
            else:
                window.resize(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)

            # Set position
            if position:
                window.move(position)
            else:
                # Auto position (cascade)
                self._auto_position_window(window)

            # Connect signals
            window.window_closed.connect(lambda: self.close_window(window_id))
            window.window_activated.connect(self._on_window_activated_by_id)
            window.window_state_changed.connect(self._on_window_state_changed)

            # Add to MDI area
            self.mdi_area.addSubWindow(window)

            # Store references
            self.windows[window_id] = window

            # Create window info
            info = WindowInfo(
                window_id=window_id,
                app_id=app_id,
                title=title,
                window_type=window_type,
                state=WindowState.NORMAL,
                position=window.pos(),
                size=window.size(),
                z_order=self._get_next_z_order(),
                created_at=datetime.now(),
                last_active=datetime.now(),
                is_active=False
            )
            self.window_info[window_id] = info

            # Show window with animation
            self._show_window_animated(window)

            # Emit signal
            self.window_created.emit(window_id, info)

            def on_state_changed():
                if window.isMinimized():
                    self.mark_manually_minimized(window_id)
                elif not window.isMinimized() and window_id in self.manually_minimized_windows:
                    self.unmark_manually_minimized(window_id)

            window.windowStateChanged.connect(on_state_changed)
            logger.info(f"Window created: {window_id} - {title}")
            return window_id

        except Exception as e:
            logger.error(f"Error creating window: {e}")
            return None

    def create_app_window(self, app_id: str) -> Optional[str]:
        """
        Create window for an application

        Args:
            app_id: Application ID

        Returns:
            Window ID if successful
        """
        # Check if app is external
        app = self.app_repo.get_app_by_id(app_id)
        if not app:
            return None

        if app.is_external:
            # Launch external app
            return self._launch_external_app(app)
        else:
            # Create internal window
            return self.create_window(
                app_id=app_id,
                window_type=WindowType.APP
            )

    def _launch_external_app(self, app: AppModel) -> Optional[str]:
        """Launch external application"""
        try:
            # Create window first
            window_id = create_window_id(app.id)

            window = AppWindow(
                window_id=window_id,
                app_id=app.id,
                title=app.display_name,
                parent=self.mdi_area
            )

            # Create process
            process = QProcess()

            # Connect process signals
            process.started.connect(lambda: logger.info(f"Started: {app.exe_path}"))
            process.finished.connect(lambda: self.close_window(window_id))
            process.errorOccurred.connect(
                lambda error: logger.error(f"Process error: {error}")
            )

            # Start process
            process.start(app.exe_path, app.arguments or [])

            # Embed process window (platform specific)
            window.embed_process(process)

            # Add to MDI area
            self.mdi_area.addSubWindow(window)
            window.show()

            # Store references
            self.windows[window_id] = window

            logger.info(f"Launched external app: {app.display_name}")
            return window_id

        except Exception as e:
            logger.error(f"Error launching external app: {e}")
            return None

    # ========== WINDOW OPERATIONS ==========
    # Ẩn window hoàn toàn (không hiện title bar)
    def hide_to_taskbar(self):
        """Ẩn window hoàn toàn - chỉ hiện trên taskbar"""
        self.hide()
        self.window_state = WindowState.MINIMIZED
        logger.debug(f"Window {self.window_id} hidden to taskbar")

    # Restore window từ taskbar
    def restore_from_taskbar(self):
        """Hiện lại window từ taskbar"""
        self.show()
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.window_state = WindowState.NORMAL
        logger.debug(f"Window {self.window_id} restored from taskbar")
    def close_window(self, window_id: str) -> bool:
        """
        Close a window

        Args:
            window_id: Window ID to close

        Returns:
            True if closed successfully
        """
        if window_id not in self.windows:
            logger.warning(f"Window not found: {window_id}")
            return False

        try:
            window = self.windows[window_id]

            # Animate close
            self._close_window_animated(window)

            # Remove references
            del self.windows[window_id]
            del self.window_info[window_id]

            # Update active window
            if self.active_window_id == window_id:
                self.active_window_id = None
                self._update_active_window()

            # Emit signal
            self.window_closed.emit(window_id)

            logger.info(f"Window closed: {window_id}")
            return True

        except Exception as e:
            logger.error(f"Error closing window: {e}")
            return False

    def close_all_windows(self) -> int:
        """
        Close all windows

        Returns:
            Number of windows closed
        """
        count = 0
        for window_id in list(self.windows.keys()):
            if self.close_window(window_id):
                count += 1

        logger.info(f"Closed {count} windows")
        return count

    def minimize_window(self, window_id: str) -> bool:
        """Minimize window - ẩn hoàn toàn với flag"""
        if window_id in self.windows:
            window = self.windows[window_id]

            # Sử dụng hide_manually để đánh dấu
            if hasattr(window, 'hide_manually'):
                window.hide_manually()
            else:
                window.hide()

            if window_id in self.window_info:
                self.window_info[window_id].state = WindowState.MINIMIZED

            logger.info(f"Window {window_id} minimized with manual flag")
            return True
        return False
    # Track window được minimize thủ công (từ title bar)
    def mark_manually_minimized(self, window_id: str):
        """Đánh dấu window được minimize thủ công từ title bar"""
        if window_id in self.windows:
            self.manually_minimized_windows.add(window_id)
            logger.debug(f"Window {window_id} marked as manually minimized")

    # Xóa mark khi window được restore thủ công
    def unmark_manually_minimized(self, window_id: str):
        """Xóa đánh dấu manually minimized khi window được restore"""
        if window_id in self.manually_minimized_windows:
            self.manually_minimized_windows.remove(window_id)
            logger.debug(f"Window {window_id} unmarked from manually minimized")

    def restore_window(self, window_id: str) -> bool:
        """Restore window từ taskbar"""
        if window_id in self.windows:
            window = self.windows[window_id]

            # Sử dụng show_manually để xóa flag và hiện window
            if hasattr(window, 'show_manually'):
                window.show_manually()
            else:
                window.show()
                window.showNormal()

            window.raise_()
            window.activateWindow()

            if window_id in self.window_info:
                self.window_info[window_id].state = WindowState.NORMAL

            logger.info(f"Window {window_id} restored and manual flag cleared")
            return True
        return False
    def toggle_window(self, window_id: str) -> bool:
        """Toggle show/hide window"""
        if window_id not in self.windows:
            return False

        window = self.windows[window_id]

        # Toggle based on visibility
        if window.isVisible():
            return self.minimize_window(window_id)
        else:
            return self.restore_window(window_id)    # Lấy window ID từ app ID
    def get_window_by_app_id(self, app_id: str) -> Optional[str]:
        """Get first window ID for an app"""
        for window_id, info in self.window_info.items():
            if info.app_id == app_id:
                return window_id
        return None

    def minimize_all_windows(self):
        """Minimize all windows và lưu trạng thái (trừ đã minimize thủ công)"""
        # Lưu trạng thái trước khi minimize
        self.save_windows_state()

        count = 0
        for window_id in list(self.windows.keys()):
            # Bỏ qua những window đã minimize thủ công
            if window_id not in self.manually_minimized_windows:
                if self.minimize_window(window_id):
                    count += 1

        logger.info(f"Minimized {count} windows (skipped {len(self.manually_minimized_windows)} manually minimized)")
        return count    # Lưu trạng thái hiện tại của tất cả windows
    def save_windows_state(self):
        """Lưu trạng thái hiện tại của tất cả windows trước khi show desktop"""
        self.windows_state_before_desktop.clear()

        for window_id, window in self.windows.items():
            # Bỏ qua những window đã được minimize thủ công
            if window_id in self.manually_minimized_windows:
                continue

            # Chỉ lưu những window đang hiển thị
            if window.isVisible() and not window.isMinimized():
                self.windows_state_before_desktop[window_id] = {
                    'visible': True,
                    'state': self.window_info[window_id].state
                }

        logger.info(
            f"Saved state for {len(self.windows_state_before_desktop)} visible windows (excluded {len(self.manually_minimized_windows)} manually minimized)")
    # Khôi phục lại trạng thái đã lưu
    def restore_saved_windows_state(self):
        """Khôi phục lại trạng thái windows đã lưu trước khi show desktop"""
        restored_count = 0

        for window_id in self.windows_state_before_desktop:
            if window_id in self.windows:
                window = self.windows[window_id]
                saved_state = self.windows_state_before_desktop[window_id]

                # Chỉ restore những window đã visible trước đó
                if saved_state.get('visible', False):
                    window.showNormal()
                    restored_count += 1

        # Clear saved state sau khi restore
        self.windows_state_before_desktop.clear()

        logger.info(f"Restored {restored_count} windows to previous state")
        return restored_count

    def restore_all_windows(self):
        """Restore all windows (trừ những cái minimize thủ công)"""
        count = 0
        for window_id, window in self.windows.items():
            # Bỏ qua những window minimize thủ công
            if window_id not in self.manually_minimized_windows:
                window.showNormal()
                count += 1

        logger.info(f"Restored {count} windows (skipped {len(self.manually_minimized_windows)} manually minimized)")
    # ========== WINDOW ARRANGEMENT ==========

    def cascade_windows(self):
        """Cascade all windows"""
        if not self.mdi_area:
            return

        self.mdi_area.cascadeSubWindows()

        # Update window info
        for window_id, window in self.windows.items():
            self.window_info[window_id].position = window.pos()

        self.windows_arranged.emit(WindowArrangement.CASCADE)
        logger.info("Windows cascaded")

    def tile_horizontal(self):
        """Tile windows horizontally"""
        if not self.mdi_area:
            return

        windows = [w for w in self.windows.values() if not w.isMinimized()]
        if not windows:
            return

        # Calculate dimensions
        area_rect = self.mdi_area.rect()
        window_height = area_rect.height() // len(windows)

        # Position windows
        y = 0
        for window in windows:
            window.move(0, y)
            window.resize(area_rect.width(), window_height)
            y += window_height

        # Update info
        for window_id, window in self.windows.items():
            self.window_info[window_id].position = window.pos()
            self.window_info[window_id].size = window.size()

        self.windows_arranged.emit(WindowArrangement.TILE_HORIZONTAL)
        logger.info("Windows tiled horizontally")

    def tile_vertical(self):
        """Tile windows vertically"""
        if not self.mdi_area:
            return

        windows = [w for w in self.windows.values() if not w.isMinimized()]
        if not windows:
            return

        # Calculate dimensions
        area_rect = self.mdi_area.rect()
        window_width = area_rect.width() // len(windows)

        # Position windows
        x = 0
        for window in windows:
            window.move(x, 0)
            window.resize(window_width, area_rect.height())
            x += window_width

        # Update info
        for window_id, window in self.windows.items():
            self.window_info[window_id].position = window.pos()
            self.window_info[window_id].size = window.size()

        self.windows_arranged.emit(WindowArrangement.TILE_VERTICAL)
        logger.info("Windows tiled vertically")

    def tile_grid(self):
        """Tile windows in a grid"""
        if not self.mdi_area:
            return

        self.mdi_area.tileSubWindows()

        # Update window info
        for window_id, window in self.windows.items():
            self.window_info[window_id].position = window.pos()
            self.window_info[window_id].size = window.size()

        self.windows_arranged.emit(WindowArrangement.TILE_GRID)
        logger.info("Windows tiled in grid")

    def arrange_windows(self, arrangement: WindowArrangement):
        """Arrange windows in specified mode"""
        if arrangement == WindowArrangement.CASCADE:
            self.cascade_windows()
        elif arrangement == WindowArrangement.TILE_HORIZONTAL:
            self.tile_horizontal()
        elif arrangement == WindowArrangement.TILE_VERTICAL:
            self.tile_vertical()
        elif arrangement == WindowArrangement.TILE_GRID:
            self.tile_grid()

    # ========== WINDOW FOCUS ==========

    def get_active_window(self) -> Optional[str]:
        """Get active window ID"""
        return self.active_window_id

    def set_active_window(self, window_id: str) -> bool:
        """Set active window"""
        if window_id not in self.windows:
            return False

        window = self.windows[window_id]
        window.activate()

        # Update active window
        self.active_window_id = window_id
        self._update_active_window()

        return True

    def switch_window(self, window_id: str) -> bool:
        """Switch to a window"""
        return self.set_active_window(window_id)

    def switch_to_next_window(self):
        """Switch to next window"""
        if not self.windows:
            return

        window_ids = list(self.windows.keys())
        if not self.active_window_id:
            self.set_active_window(window_ids[0])
        else:
            current_index = window_ids.index(self.active_window_id)
            next_index = (current_index + 1) % len(window_ids)
            self.set_active_window(window_ids[next_index])

    def switch_to_previous_window(self):
        """Switch to previous window"""
        if not self.windows:
            return

        window_ids = list(self.windows.keys())
        if not self.active_window_id:
            self.set_active_window(window_ids[-1])
        else:
            current_index = window_ids.index(self.active_window_id)
            prev_index = (current_index - 1) % len(window_ids)
            self.set_active_window(window_ids[prev_index])

    def _update_active_window(self):
        """Update active window state"""
        # Update all window states
        for window_id, window in self.windows.items():
            is_active = window_id == self.active_window_id
            window.is_active = is_active

            if window_id in self.window_info:
                self.window_info[window_id].is_active = is_active
                if is_active:
                    self.window_info[window_id].last_active = datetime.now()

        # Emit signal
        if self.active_window_id:
            self.active_window_changed.emit(self.active_window_id)

    # ========== WINDOW QUERIES ==========

    def get_window_count(self) -> int:
        """Get number of windows"""
        return len(self.windows)

    def get_windows(self) -> List[str]:
        """Get all window IDs"""
        return list(self.windows.keys())

    def get_window_info(self, window_id: str) -> Optional[WindowInfo]:
        """Get window information"""
        return self.window_info.get(window_id)

    def get_windows_by_app(self, app_id: str) -> List[str]:
        """Get windows for an app"""
        return [
            window_id
            for window_id, info in self.window_info.items()
            if info.app_id == app_id
        ]

    def has_window(self, window_id: str) -> bool:
        """Check if window exists"""
        return window_id in self.windows

    def find_window_by_title(self, title: str) -> Optional[str]:
        """Find window by title"""
        for window_id, info in self.window_info.items():
            if info.title == title:
                return window_id
        return None

    # ========== ANIMATIONS ==========

    def _show_window_animated(self, window: AppWindow):
        """Show window with animation"""
        # Create fade in animation
        window.setWindowOpacity(0)
        window.show()

        animation = QPropertyAnimation(window, b"windowOpacity")
        animation.setDuration(WINDOW_ANIMATION_DURATION)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.start()

        self.animations.append(animation)
        animation.finished.connect(lambda: self.animations.remove(animation))

    def _close_window_animated(self, window: AppWindow):
        """Close window with animation"""
        animation = QPropertyAnimation(window, b"windowOpacity")
        animation.setDuration(WINDOW_ANIMATION_DURATION // 2)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setEasingCurve(QEasingCurve.InCubic)
        animation.finished.connect(window.close)
        animation.start()

    # ========== HELPER METHODS ==========

    def _auto_position_window(self, window: AppWindow):
        """Auto position window (cascade)"""
        # Calculate cascade offset
        offset = len(self.windows) * 30
        window.move(offset, offset)

    def _get_next_z_order(self) -> int:
        """Get next z-order value"""
        self.z_order_counter += 1
        return self.z_order_counter

    def _on_window_activated(self, window: Optional[QMdiSubWindow]):
        """Handle MDI window activation"""
        if not window:
            return

        # Find window ID
        for window_id, win in self.windows.items():
            if win == window:
                self.active_window_id = window_id
                self._update_active_window()
                self.window_activated.emit(window_id)
                break

    def _on_window_activated_by_id(self, window_id: str):
        """Handle window activation by ID"""
        self.active_window_id = window_id
        self._update_active_window()
        self.window_activated.emit(window_id)

    def _on_window_state_changed(self, window_id: str, state: WindowState):
        """Handle window state change"""
        if window_id in self.window_info:
            self.window_info[window_id].state = state
            logger.debug(f"Window {window_id} state changed to {state.value}")

    # ========== VIEW MODES ==========

    def set_tabbed_view(self, enabled: bool):
        """Enable/disable tabbed view"""
        if not self.mdi_area:
            return

        if enabled:
            self.mdi_area.setViewMode(QMdiArea.TabbedView)
        else:
            self.mdi_area.setViewMode(QMdiArea.SubWindowView)

    def set_background(self, color: QColor):
        """Set MDI area background color"""
        if self.mdi_area:
            self.mdi_area.setBackground(QBrush(color))