# ui_qt/windows/dashboard_window_qt/views/main_dashboard.py
"""
Main Dashboard Window - Cửa sổ chính của Dashboard Desktop-Style
Điều phối tất cả các components: Desktop, Taskbar, Start Menu
"""

import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from PySide6.QtCore import Qt, QTimer, QSize, QPoint, QRect, Signal, QEvent
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QSplitter, QMdiArea, QMdiSubWindow,
    QMenuBar, QMenu, QStatusBar, QToolBar,
    QDockWidget, QMessageBox, QApplication, QSystemTrayIcon
)
from PySide6.QtGui import (
    QAction, QIcon, QPixmap, QPalette, QColor,
    QFont, QFontDatabase, QCloseEvent, QResizeEvent,
    QKeySequence, QShortcut
)
# Thêm đường dẫn đến thư mục cha (dashboard_window_qt)
current_file = Path(__file__)  # views/main_dashboard.py
project_root = current_file.parent.parent.parent.parent.parent  # Lùi về thư mục gốc project
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import services
try:
    from ui_qt.windows.dashboard_window_qt.services.app_launcher_service import (
        AppLauncherService, LaunchResult, WindowMode
    )
    from ui_qt.windows.dashboard_window_qt.services.desktop_service import (
        DesktopService, ArrangeMode, SortBy
    )
    from ui_qt.windows.dashboard_window_qt.services.window_manager_service import (
        WindowManagerService
    )
    from ui_qt.windows.dashboard_window_qt.repositories.app_repository import (
        AppRepository, AppModel
    )
    from ui_qt.windows.dashboard_window_qt.repositories.settings_repository import (
        SettingsRepository
    )
    from ui_qt.windows.dashboard_window_qt.utils.assets import (
        AssetsManager, load_icon, load_wallpaper
    )
    from ui_qt.windows.dashboard_window_qt.utils.constants import (
        TASKBAR_HEIGHT,
        START_MENU_WIDTH,
        START_MENU_HEIGHT,
        DEFAULT_THEME,
        SHORTCUTS
    )

    print("✅ Import thành công tất cả modules")
    MODULES_AVAILABLE = True

except ImportError as e:
    print(f"❌ Lỗi import: {e}")
    import traceback

    traceback.print_exc()

except ImportError as e:
    print(f"❌ Lỗi import: {e}")
    import traceback

    traceback.print_exc()

    # Fallback: Tạo dummy classes
    from PySide6.QtCore import QObject, Signal
    from PySide6.QtGui import QIcon, QPixmap


    class DummyService(QObject):
        def __init__(self, *args, **kwargs):
            super().__init__()

        def __getattr__(self, name):
            return lambda *args, **kwargs: None


    class DummyRepo:
        def __init__(self, *args, **kwargs): pass

        def __getattr__(self, name): return lambda *args, **kwargs: None


    # Dummy enums
    class LaunchResult:
        SUCCESS = "success"
        FAILED = "failed"
        NOT_FOUND = "not_found"


    class WindowMode:
        NORMAL = "normal"
        MAXIMIZED = "maximized"
        MINIMIZED = "minimized"


    class ArrangeMode:
        GRID = "grid"
        AUTO = "auto"


    class SortBy:
        NAME = "name"
        TYPE = "type"


    # Assign dummy classes
    AppLauncherService = DummyService
    DesktopService = DummyService
    WindowManagerService = DummyService
    AppRepository = DummyRepo
    AppModel = dict
    SettingsRepository = DummyRepo
    AssetsManager = DummyService


    # Dummy functions
    def load_icon(name, size=None):
        return QIcon()


    def load_wallpaper(path):
        return QPixmap()


    # Dummy constants
    TASKBAR_HEIGHT = 45
    START_MENU_WIDTH = 450
    START_MENU_HEIGHT = 600
    DEFAULT_THEME = "light"
    SHORTCUTS = {}

    MODULES_AVAILABLE = False
# Setup logger
logger = logging.getLogger(__name__)


# ========== MAIN DASHBOARD WINDOW ==========

class MainDashboard(QMainWindow):
    """
    Cửa sổ chính của Dashboard Desktop-Style
    Quản lý và điều phối tất cả components
    """

    # Signals
    app_launched = Signal(str, object)  # app_id, window
    app_closed = Signal(str)  # app_id
    theme_changed = Signal(str)  # theme_name

    def __init__(self, db_manager=None, parent=None):
        """
        Initialize Main Dashboard

        Args:
            db_manager: Database manager instance
            parent: Parent widget
        """
        super().__init__(parent)

        # Core components
        self.db = db_manager
        self.settings_repo = SettingsRepository()
        self.app_repo = AppRepository()
        self.assets_manager = AssetsManager()
        # Khai báo các attributes
        self.db_manager = db_manager

        # Services
        self.app_launcher = AppLauncherService(self.db, self)
        self.desktop_service = DesktopService(self)

        # UI Components (will be initialized)
        self.desktop_area = None
        self.taskbar = None
        self.start_menu = None
        self.system_tray = None
        self.mdi_area = None

        # State tracking
        self.is_fullscreen = False
        self.start_menu_visible = False
        self.current_theme = DEFAULT_THEME

        # Window tracking
        self.child_windows: Dict[str, QWidget] = {}

        # Initialize UI
        self.setup_ui()
        self.setup_services()
        self.setup_connections()
        self.load_settings()
        self.setup_shortcuts()

        # Start timers
        self.setup_timers()

        # Show window
        self.show_window()
        if self.mdi_area:
            self.mdi_area.installEventFilter(self)
    # ========== UI SETUP ==========
    # Chặn các event có thể trigger auto-show
    def eventFilter(self, source, event):
        """Event filter để chặn auto-show windows"""
        # Nếu là MDI area và là resize event
        if source == self.mdi_area:
            if event.type() == QEvent.Resize:
                # Không cho resize trigger show windows
                for window in self.mdi_area.subWindowList():
                    if hasattr(window, 'is_manually_hidden') and window.is_manually_hidden:
                        # Giữ window ẩn nếu đang ẩn thủ công
                        window.hide()

        return super().eventFilter(source, event)
    def setup_ui(self):
        """Setup main UI components"""
        self.setWindowTitle("🖥️ Dashboard Desktop - Phần mềm Gia sư")
        self.setObjectName("MainDashboard")

        # Set window icon
        icon = load_icon("app")
        if icon:
            self.setWindowIcon(icon)

        # Set minimum size
        self.setMinimumSize(1024, 768)

        # Create central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Main layout
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Create desktop area (main content)
        self.create_desktop_area()

        # Create taskbar
        self.create_taskbar()

        # Create start menu (hidden initially)
        self.create_start_menu()

        # Create system tray
        self.create_system_tray()

        # Setup menu bar
        self.setup_menu_bar()

        # Setup status bar
        self.setup_status_bar()

        # Apply theme
        self.apply_theme()

    def create_desktop_area(self):
        """Create desktop area with wallpaper"""
        # Desktop container
        self.desktop_container = QWidget()
        self.desktop_container.setObjectName("DesktopContainer")

        # SỬA: Dùng lại QVBoxLayout thay vì QStackedLayout
        desktop_layout = QVBoxLayout(self.desktop_container)
        desktop_layout.setContentsMargins(0, 0, 0, 0)
        desktop_layout.setSpacing(0)

        # Import and create desktop widget
        try:
            from .desktop.desktop_area import DesktopArea
            self.desktop_area = DesktopArea(parent=self.desktop_container)
            self.desktop_area._skip_auto_load_icons = True

            # Connect signals
            if hasattr(self.desktop_area, 'icon_double_clicked'):
                self.desktop_area.icon_double_clicked.connect(self.handle_app_launch)


        except Exception as e:
            logger.error(f"Failed to create desktop area: {e}")
            self.desktop_area = None

        # MDI Area for app windows
        self.mdi_area = QMdiArea()
        self.mdi_area.setObjectName("MdiArea")
        # QUAN TRỌNG: Disable auto tile/cascade khi resize
        self.mdi_area.setOption(QMdiArea.DontMaximizeSubWindowOnActivation, True)

        # Disable tự động arrange
        self.mdi_area.setActivationOrder(QMdiArea.ActivationHistoryOrder)
        # QUAN TRỌNG: Set MDI area không chặn mouse events khi không có child windows
        self.mdi_area.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # Set MDI area transparent
        self.mdi_area.setStyleSheet("""
            QMdiArea {
                background: transparent;
                border: none;
            }
            QMdiArea::viewport {
                background: transparent;
            }
        """)

        from PySide6.QtGui import QBrush
        self.mdi_area.setBackground(QBrush(Qt.transparent))

        # Add cả 2 widgets vào layout
        if self.desktop_area:
            desktop_layout.addWidget(self.desktop_area)

        # QUAN TRỌNG: Set MDI area nằm chồng lên desktop area
        self.mdi_area.setParent(self.desktop_container)
        self.mdi_area.move(0, 0)
        self.mdi_area.resize(self.desktop_container.size())

        # Add desktop container to main layout
        self.main_layout.addWidget(self.desktop_container, 1)
    def create_taskbar(self):
        """Create taskbar at bottom"""
        try:
            from .taskbar.taskbar import Taskbar
            self.taskbar = Taskbar(self)

            # Thêm dictionary để lưu window references
            self.taskbar.window_refs = {}  # Thêm dòng này

            # Connect signal để xử lý đóng app từ taskbar
            if hasattr(self.taskbar, 'close_app_requested'):
                self.taskbar.close_app_requested.connect(self.close_app_from_taskbar)
        except ImportError:
            # Fallback: Create basic taskbar
            self.taskbar = QWidget()
            self.taskbar.setObjectName("Taskbar")
            self.taskbar.setFixedHeight(TASKBAR_HEIGHT)

            # Taskbar layout
            taskbar_layout = QHBoxLayout(self.taskbar)
            taskbar_layout.setContentsMargins(5, 0, 5, 0)

            # Start button
            from PySide6.QtWidgets import QPushButton
            self.start_button = QPushButton("⊞ Start")
            self.start_button.setObjectName("StartButton")
            self.start_button.clicked.connect(self.toggle_start_menu)
            taskbar_layout.addWidget(self.start_button)

            # Search box
            from PySide6.QtWidgets import QLineEdit
            self.search_box = QLineEdit()
            self.search_box.setPlaceholderText("🔍 Tìm kiếm...")
            self.search_box.setMaximumWidth(200)
            taskbar_layout.addWidget(self.search_box)

            # App buttons area
            self.app_buttons_area = QWidget()
            self.app_buttons_layout = QHBoxLayout(self.app_buttons_area)
            self.app_buttons_layout.setContentsMargins(0, 0, 0, 0)
            taskbar_layout.addWidget(self.app_buttons_area, 1)

            # System tray area
            taskbar_layout.addStretch()

            # Clock
            from PySide6.QtWidgets import QLabel
            self.clock_label = QLabel()
            self.update_clock()
            taskbar_layout.addWidget(self.clock_label)

        # Add taskbar to main layout
        self.main_layout.addWidget(self.taskbar)

    def create_start_menu(self):
        """Create start menu (hidden by default)"""
        # Tạo start menu đơn giản (không cần import phức tạp)
        from PySide6.QtWidgets import QLabel, QFrame, QListWidget, QPushButton

        self.start_menu = QWidget(self)
        self.start_menu.setObjectName("StartMenu")
        self.start_menu.setFixedSize(450, 600)  # Kích thước cố định

        # Start menu layout
        menu_layout = QVBoxLayout(self.start_menu)

        # User info
        user_label = QLabel("👤 Giáo viên")
        user_label.setObjectName("UserLabel")
        menu_layout.addWidget(user_label)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        menu_layout.addWidget(separator)

        # Pinned apps
        menu_layout.addWidget(QLabel("📌 Ứng dụng được ghim:"))

        # App list
        self.app_list = QListWidget()

        # Thêm một số app mẫu (không cần load từ database)
        self.app_list.addItem("📚 Ngân hàng câu hỏi")
        self.app_list.addItem("👥 Quản lý học sinh")
        self.app_list.addItem("📊 Báo cáo tiến độ")

        menu_layout.addWidget(self.app_list)

        # Power buttons
        power_layout = QHBoxLayout()
        shutdown_btn = QPushButton("⏻ Tắt máy")
        restart_btn = QPushButton("🔄 Khởi động lại")
        power_layout.addWidget(shutdown_btn)
        power_layout.addWidget(restart_btn)
        menu_layout.addLayout(power_layout)

        # Position and hide
        self.start_menu.hide()
        self.position_start_menu()

    def create_system_tray(self):
        """Create system tray icon"""
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.system_tray = QSystemTrayIcon(self)

            # Set icon
            icon = load_icon("app")
            if icon:
                self.system_tray.setIcon(icon)

            # Create context menu
            tray_menu = QMenu()

            show_action = QAction("Hiện Dashboard", self)
            show_action.triggered.connect(self.show)
            tray_menu.addAction(show_action)

            tray_menu.addSeparator()

            exit_action = QAction("Thoát", self)
            exit_action.triggered.connect(self.close)
            tray_menu.addAction(exit_action)

            self.system_tray.setContextMenu(tray_menu)

            # Show tray icon
            self.system_tray.show()

            # Connect double click
            self.system_tray.activated.connect(self.on_tray_activated)

    def setup_menu_bar(self):
        """Setup menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        new_action = QAction("Mới", self)
        new_action.setShortcut("Ctrl+N")
        file_menu.addAction(new_action)

        open_action = QAction("Mở", self)
        open_action.setShortcut("Ctrl+O")
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        exit_action = QAction("Thoát", self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        fullscreen_action = QAction("Toàn màn hình", self)
        fullscreen_action.setShortcut("F11")
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)

        view_menu.addSeparator()

        # Theme submenu
        theme_menu = view_menu.addMenu("Theme")

        light_theme = QAction("Light", self)
        light_theme.triggered.connect(lambda: self.change_theme("light"))
        theme_menu.addAction(light_theme)

        dark_theme = QAction("Dark", self)
        dark_theme.triggered.connect(lambda: self.change_theme("dark"))
        theme_menu.addAction(dark_theme)

        # Apps menu
        apps_menu = menubar.addMenu("&Apps")
        self.populate_apps_menu(apps_menu)

        # Window menu
        window_menu = menubar.addMenu("&Window")

        cascade_action = QAction("Xếp chồng", self)
        cascade_action.triggered.connect(self.cascade_windows)
        window_menu.addAction(cascade_action)

        tile_action = QAction("Xếp ngói", self)
        tile_action.triggered.connect(self.tile_windows)
        window_menu.addAction(tile_action)

        window_menu.addSeparator()

        close_all_action = QAction("Đóng tất cả", self)
        close_all_action.triggered.connect(self.close_all_windows)
        window_menu.addAction(close_all_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("Về Dashboard", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def setup_status_bar(self):
        """Setup status bar"""
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Sẵn sàng")

        # Add permanent widgets
        from PySide6.QtWidgets import QLabel

        # User label
        self.user_label = QLabel("👤 Giáo viên")
        self.status_bar.addPermanentWidget(self.user_label)

        # App count label
        self.app_count_label = QLabel("Apps: 0")
        self.status_bar.addPermanentWidget(self.app_count_label)

    # ========== SERVICES SETUP ==========

    def setup_services(self):
        """Setup and configure services"""
        # Configure app launcher
        self.app_launcher.set_mdi_area(self.mdi_area)

        # Connect app launcher signals
        self.app_launcher.app_launched.connect(self.on_app_launched)
        self.app_launcher.app_closed.connect(self.on_app_closed)
        self.app_launcher.app_error.connect(self.on_app_error)

        # Connect desktop service signals
        self.desktop_service.icon_added.connect(self.on_icon_added)
        self.desktop_service.icon_removed.connect(self.on_icon_removed)

        # Load desktop icons
        self.load_desktop_icons()

    def setup_connections(self):
        """Setup signal/slot connections"""
        # Search box
        if hasattr(self, 'search_box'):
            self.search_box.returnPressed.connect(self.on_search)

        # App list in start menu
        if hasattr(self, 'app_list'):
            self.app_list.itemDoubleClicked.connect(self.on_app_list_double_click)

    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Win key - Show start menu
        QShortcut(QKeySequence(Qt.Key_Meta), self, self.toggle_start_menu)

        # Win+D - Show desktop
        QShortcut(QKeySequence("Meta+D"), self, self.toggle_desktop)
        # Win+L - Lock screen
        QShortcut(QKeySequence("Meta+L"), self, self.lock_screen)

        # Alt+Tab - Switch apps
        QShortcut(QKeySequence("Alt+Tab"), self, self.switch_apps)

        # Win+E - File explorer
        QShortcut(QKeySequence("Meta+E"), self, self.open_file_explorer)

        # F5 - Refresh
        QShortcut(QKeySequence("F5"), self, self.refresh_desktop)

    def setup_timers(self):
        """Setup timers for updates"""
        # Clock timer
        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)  # Update every second

        # Auto-save timer
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.start(60000)  # Auto-save every minute

    # ========== WINDOW MANAGEMENT ==========

    def show_window(self):
        """Show main window"""
        # Set wallpaper sau khi desktop area sẵn sàng
        if self.desktop_area:
            self.set_wallpaper()

        # Check startup mode - SỬA PHẦN NÀY
        try:
            # Thử lấy setting start_maximized nếu có
            start_maximized = False
            if hasattr(self.settings_repo, 'get_general'):
                general_settings = self.settings_repo.get_general()
                if hasattr(general_settings, 'start_maximized'):
                    start_maximized = general_settings.start_maximized
        except:
            start_maximized = False

        # Hiển thị window
        if start_maximized:
            self.showMaximized()
        else:
            self.show()
            # Center window
            screen = QApplication.primaryScreen()
            if screen:
                self.move(
                    (screen.geometry().width() - self.width()) // 2,
                    (screen.geometry().height() - self.height()) // 2
                )

    def cascade_windows(self):
        """Cascade MDI windows"""
        if self.mdi_area:
            self.mdi_area.cascadeSubWindows()

    def tile_windows(self):
        """Tile MDI windows"""
        if self.mdi_area:
            self.mdi_area.tileSubWindows()

    def close_all_windows(self):
        """Close all MDI windows"""
        if self.mdi_area:
            self.mdi_area.closeAllSubWindows()

        # Also close app launcher windows
        self.app_launcher.close_all_apps()

    def show_desktop(self):
        """Minimize all windows to show desktop"""
        if self.mdi_area:
            for window in self.mdi_area.subWindowList():
                # Chỉ ẩn những window đang hiển thị
                if window.isVisible() and not window.isMinimized():
                    if hasattr(window, 'hide_manually'):
                        window.hide_manually()
                    else:
                        window.hide()

    def toggle_desktop(self):
        """Toggle show/hide desktop"""
        if not self.mdi_area:
            return

        # Lấy danh sách windows đang hiển thị
        visible_windows = []
        for window in self.mdi_area.subWindowList():
            if window.isVisible() and not window.isMinimized():
                if not (hasattr(window, 'is_manually_hidden') and window.is_manually_hidden):
                    visible_windows.append(window)

        if visible_windows:
            # Ẩn các windows đang hiển thị
            for window in visible_windows:
                if hasattr(window, 'hide_manually'):
                    window.hide_manually()
                else:
                    window.hide()
        else:
            # Restore các windows (trừ manually hidden)
            for window in self.mdi_area.subWindowList():
                if hasattr(window, 'is_manually_hidden') and not window.is_manually_hidden:
                    if hasattr(window, 'show_manually'):
                        window.show_manually()
                    else:
                        window.show()
    def launch_app(self, app_id: str):
        """Launch app by ID"""
        result, window = self.app_launcher.launch_app_by_id(
            app_id,
            WindowMode.NORMAL,
            self
        )

        if result == LaunchResult.SUCCESS:
            self.status_bar.showMessage(f"Đã mở ứng dụng: {app_id}", 3000)
        elif result == LaunchResult.ALREADY_RUNNING:
            self.status_bar.showMessage(f"Ứng dụng đang chạy: {app_id}", 3000)
        elif result == LaunchResult.PERMISSION_DENIED:
            QMessageBox.warning(self, "Lỗi", "Bạn không có quyền mở ứng dụng này")
        else:
            QMessageBox.critical(self, "Lỗi", f"Không thể mở ứng dụng: {app_id}")

    def on_app_launched(self, app_id: str, window: QWidget):
        """Handle app launched"""
        logger.info(f"App launched: {app_id}")

        # Update taskbar - truyền cả app_id và window
        if self.taskbar:
            try:
                self.taskbar.add_app_button(app_id, window)
                logger.info(f"Added button to taskbar for app: {app_id}")
            except Exception as e:
                logger.error(f"Error adding button to taskbar: {e}")

        # Update app count
        self.update_app_count()

        # Emit signal
        self.app_launched.emit(app_id, window)

    def on_app_closed(self, app_id: str):
        """Handle app closed"""
        logger.info(f"App closed: {app_id}")

        # Update taskbar
        if self.taskbar:
            try:
                self.taskbar.remove_app_button(app_id)
                logger.info(f"Removed button from taskbar for app: {app_id}")
            except Exception as e:
                logger.error(f"Error removing button from taskbar: {e}")

        # Update app count
        self.update_app_count()

        # Emit signal
        self.app_closed.emit(app_id)

    # Đóng app khi click close từ taskbar
    def close_app_from_taskbar(self, app_id: str):
        """Đóng app từ taskbar button"""
        if hasattr(self.app_launcher, 'close_app'):
            self.app_launcher.close_app(app_id)
    def on_app_error(self, app_id: str, error_msg: str):
        """Handle app error"""
        logger.error(f"App error {app_id}: {error_msg}")
        QMessageBox.critical(self, "Lỗi", f"Lỗi mở ứng dụng {app_id}:\n{error_msg}")

    def update_app_count(self):
        """Update app count in status bar"""
        count = len(self.app_launcher.get_running_apps())
        self.app_count_label.setText(f"Apps: {count}")

    def handle_app_launch(self, app_id: str):
        """
        Handle khi user double-click vào desktop icon

        Args:
            app_id: ID của app cần mở
        """
        try:

            # Gọi launch_app để mở ứng dụng
            self.launch_app(app_id)

        except Exception as e:
            logger.error(f"Error handling app launch: {e}")
            QMessageBox.warning(
                self,
                "Lỗi",
                f"Không thể mở ứng dụng: {str(e)}"
            )
    # ========== DESKTOP MANAGEMENT ==========

    def load_desktop_icons(self):
        """Load desktop icons từ pinned apps"""
        try:

            # Kiểm tra và tạo desktop area nếu cần
            if not self.desktop_area:
                logger.warning("Desktop area chưa tồn tại, đang tạo...")
                if not self._force_create_desktop_area():
                    logger.error("Không thể tạo desktop area")
                    return

            # Đảm bảo app_repo sẵn sàng
            if not self.app_repo:
                logger.error("App repository chưa sẵn sàng")
                return

            pinned_apps = self.app_repo.get_pinned_apps()

            # KIỂM TRA XEM CÓ BỊ CẮT KHÔNG
            if len(pinned_apps) > 4:
                logger.warning(f"Have {len(pinned_apps)} apps but may only show some!")

            # Đảm bảo luôn có apps để hiển thị
            if not pinned_apps:
                logger.warning("Không có pinned apps, lấy apps mặc định")
                all_apps = self.app_repo.get_all_apps()
                pinned_apps = all_apps[:6] if len(all_apps) >= 6 else all_apps  # ← DÒNG NÀY CÓ THỂ LÀ VẤN ĐỀ

            # Tạo icons trực tiếp trên desktop area
            self._create_desktop_icons_directly(pinned_apps)

        except Exception as e:
            logger.error(f"Lỗi load desktop icons: {e}")
            import traceback
            traceback.print_exc()
    def on_icon_added(self, icon_id: str):
        """Handle icon added to desktop"""

        # Create icon widget if desktop area exists
        if self.desktop_area and hasattr(self.desktop_area, 'create_icon_widget'):
            self.desktop_area.create_icon_widget(icon_id)

    def on_icon_removed(self, icon_id: str):
        """Handle icon removed from desktop"""

        # Remove icon widget if desktop area exists
        if self.desktop_area and hasattr(self.desktop_area, 'remove_icon_widget'):
            self.desktop_area.remove_icon_widget(icon_id)

    def refresh_desktop(self):
        """Refresh desktop"""
        self.desktop_service.refresh_desktop()
        self.status_bar.showMessage("Desktop đã được làm mới", 2000)

    # Tạo icons trực tiếp trên desktop area
    def _create_desktop_icons_directly(self, apps: list):
        """Tạo icons trực tiếp trên desktop area"""
        try:
            if not self.desktop_area:
                logger.error("Desktop area không tồn tại")
                return

            # Clear existing icons first để tránh duplicate
            if hasattr(self.desktop_area, 'desktop_icons'):
                for widget in self.desktop_area.desktop_icons.values():
                    widget.deleteLater()
                self.desktop_area.desktop_icons.clear()

            # Import AppIconWidget
            try:
                from .widgets.app_icon_widget import AppIconWidget
            except ImportError:
                logger.error("Không thể import AppIconWidget")
                self._create_basic_icons(apps)
                return

            # Xác định parent container
            icon_parent = getattr(self.desktop_area, 'icon_container', self.desktop_area)

            # Load saved positions
            saved_positions = self.settings_repo.get_desktop_icon_positions()

            # Layout configuration - điều chỉnh để hiển thị nhiều icons
            ICONS_PER_ROW = 8  # Tăng từ 4 lên 8 icons mỗi hàng
            ICON_WIDTH = 90  # Giảm từ 120 xuống 90
            ICON_HEIGHT = 100  # Giữ nguyên 100
            START_X = 20  # Margin trái
            START_Y = 20  # Margin trên

            # Tạo icons cho từng app
            for i, app in enumerate(apps):
                try:
                    # Check saved position first
                    if app.id in saved_positions:
                        x_pos, y_pos = saved_positions[app.id]
                        position = QPoint(x_pos, y_pos)
                    else:
                        # Calculate grid position
                        col = i % ICONS_PER_ROW
                        row = i // ICONS_PER_ROW
                        position = QPoint(
                            START_X + col * ICON_WIDTH,
                            START_Y + row * ICON_HEIGHT
                        )

                    # Tạo icon widget
                    icon_widget = AppIconWidget(
                        app_id=app.id,
                        name=app.display_name,
                        icon=load_icon(app.icon_name or "app", QSize(48, 48)),
                        parent=icon_parent
                    )

                    # Connect signal với closure đúng cách
                    def make_launcher(app_id):
                        return lambda: self.handle_app_launch(app_id)

                    icon_widget.double_clicked.connect(make_launcher(app.id))

                    # Set position và hiển thị
                    icon_widget.move(position)
                    icon_widget.show()

                    # Lưu reference
                    if hasattr(self.desktop_area, 'desktop_icons'):
                        self.desktop_area.desktop_icons[app.id] = icon_widget
                    if hasattr(self.desktop_area, 'icon_positions'):
                        self.desktop_area.icon_positions[app.id] = position

                    # Save position to settings
                    self.settings_repo.save_desktop_icon_position(app.id, position)

                except Exception as e:
                    logger.error(f"Lỗi tạo icon cho {app.display_name}: {e}")

            icon_count = len(self.desktop_area.desktop_icons)

        except Exception as e:
            logger.error(f"Lỗi tạo desktop icons: {e}")
    # Force tạo desktop area nếu import thất bại
    def _force_create_desktop_area(self):
        """Force tạo desktop area với basic widget"""
        try:
            # Tạo basic desktop widget
            self.desktop_area = QWidget(self.desktop_container)
            self.desktop_area.setObjectName("BasicDesktopArea")
            self.desktop_area.setMinimumSize(800, 600)

            # Thêm vào layout
            if hasattr(self, 'desktop_container'):
                layout = self.desktop_container.layout()
                if layout:
                    layout.insertWidget(0, self.desktop_area)

            # Tạo icon container
            self.desktop_area.icon_container = QWidget(self.desktop_area)
            self.desktop_area.icon_container.setStyleSheet("background: transparent;")

            # Tạo storage cho icons
            self.desktop_area.desktop_icons = {}
            self.desktop_area.icon_positions = {}

            logger.info("Basic desktop area đã được tạo")
            return True

        except Exception as e:
            logger.error(f"Lỗi tạo basic desktop area: {e}")
            return False
    # Tạo apps demo khi không có dữ liệu
    # Fallback: tạo basic icons khi không import được AppIconWidget
    def _create_basic_icons(self, apps: list):
        """Tạo basic icons khi không import được AppIconWidget"""
        try:
            from PySide6.QtWidgets import QPushButton

            # Tạo basic buttons cho từng app
            x, y = 50, 50
            for i, app in enumerate(apps):
                col = i % 4
                row = i // 4
                position = QPoint(x + col * 120, y + row * 100)

                # Tạo button
                button = QPushButton(app.display_name, self.desktop_area)
                button.setGeometry(position.x(), position.y(), 100, 80)
                button.clicked.connect(
                    lambda checked, app_id=app.id: self.handle_app_launch(app_id)
                )
                button.show()

                # Lưu reference
                if not hasattr(self.desktop_area, 'desktop_icons'):
                    self.desktop_area.desktop_icons = {}
                self.desktop_area.desktop_icons[app.id] = button


        except Exception as e:
            logger.error(f"Lỗi tạo basic icons: {e}")

    # ========== START MENU ==========

    def toggle_start_menu(self):
        """Toggle start menu visibility"""
        if self.start_menu:
            if self.start_menu.isVisible():
                self.start_menu.hide()
                self.start_menu_visible = False
            else:
                self.position_start_menu()
                self.start_menu.show()
                self.start_menu.raise_()
                self.start_menu_visible = True

    def position_start_menu(self):
        """Position start menu above taskbar"""
        if self.start_menu and self.taskbar:
            # Get taskbar position
            taskbar_pos = self.taskbar.mapToGlobal(QPoint(0, 0))

            # Position start menu
            x = taskbar_pos.x()
            y = taskbar_pos.y() - self.start_menu.height()

            self.start_menu.move(x, y)

    def load_pinned_apps(self):
        """Load pinned apps vào Start Menu"""
        try:
            # Kiểm tra xem app_list có tồn tại không
            if not hasattr(self, 'app_list') or not self.app_list:
                return

            # Lấy pinned apps từ repository
            pinned_apps = None
            if hasattr(self, 'app_repo') and self.app_repo:
                pinned_apps = self.app_repo.get_pinned_apps()

            # NẾU pinned_apps là None hoặc rỗng, dùng apps mặc định
            if not pinned_apps:
                # Tạo danh sách apps mặc định
                default_apps = [
                    {"id": "question_bank", "name": "📚 Ngân hàng câu hỏi"},
                    {"id": "student_mgr", "name": "👥 Quản lý học sinh"},
                    {"id": "exercises", "name": "📝 Bài tập"},
                    {"id": "reports", "name": "📊 Báo cáo"},
                    {"id": "settings", "name": "⚙️ Cài đặt"}
                ]

                # Thêm apps mặc định vào list
                for app in default_apps:
                    self.app_list.addItem(app["name"])
            else:
                # Có pinned apps, thêm vào list
                for app in pinned_apps:
                    if hasattr(app, 'display_name'):
                        self.app_list.addItem(f"📱 {app.display_name}")
                    elif hasattr(app, 'name'):
                        self.app_list.addItem(f"📱 {app.name}")

        except Exception as e:
            # Nếu có lỗi, log và thêm apps mặc định
            print(f"Lỗi khi load apps: {e}")

            # Đảm bảo luôn có ít nhất một số apps
            if self.app_list and self.app_list.count() == 0:
                self.app_list.addItem("📚 Ngân hàng câu hỏi")
                self.app_list.addItem("👥 Quản lý học sinh")
                self.app_list.addItem("⚙️ Cài đặt")

    def populate_apps_menu(self, menu: QMenu):
        """Populate apps menu with all apps"""
        apps = self.app_repo.get_all_apps()

        # Group by category
        categories = {}
        for app in apps:
            if app.category not in categories:
                categories[app.category] = []
            categories[app.category].append(app)

        # Create submenus
        for category, apps_in_cat in categories.items():
            cat_menu = menu.addMenu(category.value)

            for app in apps_in_cat:
                action = QAction(app.display_name, self)
                action.triggered.connect(lambda checked, a=app.id: self.launch_app(a))
                cat_menu.addAction(action)

    # ========== THEME & APPEARANCE ==========

    def apply_theme(self):
        """Apply theme to dashboard"""
        if self.current_theme:
            theme = self.current_theme
            if theme == "dark":
                self.setStyleSheet("""
                    QMainWindow {
                        background-color: #1e1e1e;
                        color: #ffffff;
                    }
                    #Taskbar {
                        background-color: #2b2b2b;
                        border-top: 1px solid #3c3c3c;
                    }
                    #StartMenu {
                        background-color: #252525;
                        border: 1px solid #3c3c3c;
                    }
                """)
            else:
                self.setStyleSheet("""
                    QMainWindow {
                        background-color: #f0f0f0;
                        color: #000000;
                    }
                    #Taskbar {
                        background-color: #e0e0e0;
                        border-top: 1px solid #c0c0c0;
                    }
                    #StartMenu {
                        background-color: #f5f5f5;
                        border: 1px solid #c0c0c0;
                    }
                """)
        # LƯU Ý: Không có style cho QMdiArea nữa
    def change_theme(self, theme_name: str):
        """Change theme"""
        self.current_theme = theme_name
        self.settings_repo.set_theme(theme_name)
        self.apply_theme()
        self.theme_changed.emit(theme_name)
        self.status_bar.showMessage(f"Đã đổi theme: {theme_name}", 3000)

    def set_wallpaper(self):
        """Set desktop wallpaper cho desktop area"""
        if not self.desktop_area:
            logger.warning("Desktop area chưa được khởi tạo")
            return

        wallpaper_path = self.settings_repo.get_wallpaper()

        # Gọi set_wallpaper của desktop_area
        if hasattr(self.desktop_area, 'set_wallpaper'):
            self.desktop_area.set_wallpaper(wallpaper_path)
    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.is_fullscreen:
            self.showNormal()
            if self.taskbar:
                self.taskbar.show()
            self.menuBar().show()
            self.is_fullscreen = False
        else:
            self.showFullScreen()
            if self.taskbar:
                self.taskbar.hide()
            self.menuBar().hide()
            self.is_fullscreen = True

    # ========== OTHER FEATURES ==========

    def update_clock(self):
        """Update clock display"""
        if hasattr(self, 'clock_label'):
            current_time = datetime.now().strftime("%H:%M:%S")
            current_date = datetime.now().strftime("%d/%m/%Y")
            self.clock_label.setText(f"🕐 {current_time}\n📅 {current_date}")

    def on_search(self):
        """Handle search"""
        if hasattr(self, 'search_box'):
            query = self.search_box.text()
            if query:
                # Search apps
                results = self.app_repo.search_apps(query)
                if results:
                    # Launch first result
                    self.launch_app(results[0].id)
                else:
                    self.status_bar.showMessage(f"Không tìm thấy: {query}", 3000)

    def on_app_list_double_click(self, item):
        """Handle double click on app list"""
        if item:
            # Extract app name from item text
            text = item.text()
            if text.startswith("📌 "):
                app_name = text[2:]  # Remove pin emoji

                # Find and launch app
                apps = self.app_repo.get_all_apps()
                for app in apps:
                    if app.display_name == app_name:
                        self.launch_app(app.id)
                        self.toggle_start_menu()  # Hide start menu
                        break

    def on_tray_activated(self, reason):
        """Handle system tray activation"""
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.raise_()
                self.activateWindow()

    def lock_screen(self):
        """Lock screen (placeholder)"""
        QMessageBox.information(self, "Lock Screen", "Chức năng khóa màn hình chưa được triển khai")

    def switch_apps(self):
        """Switch between apps (Alt+Tab)"""
        if self.mdi_area:
            windows = self.mdi_area.subWindowList()
            if windows:
                # Activate next window
                self.mdi_area.activateNextSubWindow()

    def open_file_explorer(self):
        """Open file explorer"""
        from ..utils.helpers import open_file_explorer
        open_file_explorer(str(Path.home()))

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "Về Dashboard Desktop",
            "Dashboard Desktop-Style v1.0\n\n"
            "Phần mềm quản lý gia sư với giao diện desktop hiện đại.\n\n"
            "© 2024 - Phát triển bởi Team Gia sư"
        )

    # ========== SETTINGS & PERSISTENCE ==========

    def load_settings(self):
        """Load saved settings"""
        settings = self.settings_repo.get_settings()

        # Apply theme
        self.current_theme = settings.appearance.theme
        self.apply_theme()

        # Load window state
        window_state = settings.window_state.get("main_dashboard")
        if window_state and not self.isMaximized():
            self.resize(window_state.get('width', 1200), window_state.get('height', 800))

    def save_settings(self):
        """Save current settings"""
        # Save window state
        window_state = {
            'x': self.x(),
            'y': self.y(),
            'width': self.width(),
            'height': self.height(),
            'maximized': self.isMaximized()
        }

        self.settings_repo.save_window_state("main_dashboard", window_state)

        # Save desktop icon positions
        self.desktop_service.save_icon_positions()

    def auto_save(self):
        """Auto-save settings"""
        self.save_settings()

    # ========== EVENT HANDLERS ==========

    def closeEvent(self, event: QCloseEvent):
        """Handle window close event"""
        # Check if should confirm
        if self.settings_repo.get_general().confirm_exit:
            reply = QMessageBox.question(
                self,
                "Xác nhận thoát",
                "Bạn có chắc chắn muốn thoát Dashboard?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.No:
                event.ignore()
                return

        # Save settings
        self.save_settings()

        # Close all apps
        self.app_launcher.close_all_apps()

        # Hide system tray
        if self.system_tray:
            self.system_tray.hide()

        # Accept close
        event.accept()

    def resizeEvent(self, event: QResizeEvent):
        """Handle window resize"""
        super().resizeEvent(event)

        # Update wallpaper size
        if self.mdi_area:
            self.set_wallpaper()

        # Reposition start menu
        if self.start_menu and self.start_menu.isVisible():
            self.position_start_menu()

    def eventFilter(self, obj, event: QEvent) -> bool:
        """Event filter for global events"""
        # Hide start menu when clicking outside
        if event.type() == QEvent.MouseButtonPress:
            if self.start_menu and self.start_menu.isVisible():
                if not self.start_menu.geometry().contains(event.globalPos()):
                    self.start_menu.hide()
                    self.start_menu_visible = False

        return super().eventFilter(obj, event)

    def position_start_menu(self):
        """Định vị start menu ở góc dưới trái"""
        if self.start_menu:
            self.start_menu.move(10, self.height() - 650)

    def _load_desktop_items(self):
        """Load desktop icons và widgets"""
        try:
            # Gọi phương thức load_desktop_icons nếu có
            if hasattr(self, 'load_desktop_icons'):
                self.load_desktop_icons()

            # Hoặc load trực tiếp từ desktop_area
            elif self.desktop_area and hasattr(self.desktop_area, '_load_desktop_icons'):
                self.desktop_area._load_desktop_icons()


        except Exception as e:
            logger.error(f"Lỗi khi load desktop items: {e}")
    # Check và fix desktop area nếu cần
    def _check_and_fix_desktop(self):
        """Check và fix desktop area nếu có vấn đề"""
        # Check desktop area
        if not self.desktop_area:
            logger.warning("Desktop area không tồn tại, đang tạo lại...")
            self._force_create_desktop_area()
            # Sau khi tạo mới thì mới load icons
            if self.desktop_area:
                self.load_desktop_icons()
        else:
            # Desktop area đã tồn tại
            if hasattr(self.desktop_area, 'desktop_icons'):
                icon_count = len(self.desktop_area.desktop_icons)

                # KHÔNG load lại nếu đã có icons
                # Chỉ log warning thôi
                if icon_count == 0:
                    logger.warning("Desktop không có icons!")
                    # KHÔNG GỌI load_desktop_icons() ở đây
            else:
                logger.warning("Desktop area không có attribute desktop_icons")

        logger.info("=== END CHECK ===")
    # phương thức debug desktop icons
    def debug_desktop_icons(self):
        """Debug desktop icons status"""
        logger.info("=== DEBUG DESKTOP ICONS ===")

        # Check desktop area
        if not self.desktop_area:
            logger.error("Desktop area is None!")
            return

        logger.info(f"Desktop area type: {type(self.desktop_area)}")

        # Check icon container
        if hasattr(self.desktop_area, 'icon_container'):
            container = self.desktop_area.icon_container
        else:
            logger.warning("No icon_container attribute")

        # Check desktop icons dict
        if hasattr(self.desktop_area, 'desktop_icons'):
            icons = self.desktop_area.desktop_icons
            for app_id, widget in icons.items():
                logger.info(f"  - {app_id}: visible={widget.isVisible()}, pos={widget.pos()}")
        else:
            logger.warning("No desktop_icons dict")

        logger.info("=== END DEBUG ===")
