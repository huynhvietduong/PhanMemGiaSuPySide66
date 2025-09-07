# ui_qt/windows/dashboard_window_qt/services/app_launcher_service.py
"""
Service layer để xử lý business logic khởi chạy apps trong Dashboard
Bao gồm: Validation, permission check, window creation, error handling
"""

import os
import sys
import subprocess
import importlib
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple, Callable
from enum import Enum
import logging

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QObject, Signal, QTimer, QProcess, QThread
from PySide6.QtWidgets import (
    QMainWindow, QDialog, QWidget, QMdiSubWindow,
    QMessageBox, QProgressDialog, QApplication
)



# Import repositories
from ..repositories.app_repository import AppModel, AppStatus, AppPermission
from ..repositories.settings_repository import SettingsRepository

# Setup logger
logger = logging.getLogger(__name__)


# ========== ENUMS & CONSTANTS ==========

class LaunchResult(Enum):
    """Kết quả khởi chạy app"""
    SUCCESS = "success"
    FAILED = "failed"
    PERMISSION_DENIED = "permission_denied"
    NOT_FOUND = "not_found"
    ALREADY_RUNNING = "already_running"
    MAINTENANCE = "maintenance"


class WindowMode(Enum):
    """Chế độ cửa sổ"""
    NORMAL = "normal"
    MAXIMIZED = "maximized"
    MINIMIZED = "minimized"
    FULLSCREEN = "fullscreen"
    MDI = "mdi"  # Multiple Document Interface


# ========== EXCEPTIONS ==========

class AppLaunchError(Exception):
    """Base exception for app launch errors"""
    pass


class AppNotFoundError(AppLaunchError):
    """App không tìm thấy"""
    pass


class PermissionDeniedError(AppLaunchError):
    """Không có quyền mở app"""
    pass


class AppAlreadyRunningError(AppLaunchError):
    """App đang chạy"""
    pass


# ========== APP LAUNCHER SERVICE ==========

class AppLauncherService(QObject):
    """
    Service xử lý việc khởi chạy apps
    Quản lý lifecycle của apps, windows, permissions
    """

    # Signals
    app_launched = Signal(str, object)  # app_id, window
    app_closed = Signal(str)  # app_id
    app_error = Signal(str, str)  # app_id, error_message
    launch_progress = Signal(int)  # progress percentage

    def __init__(self, db_manager=None, parent=None):
        """
        Initialize service

        Args:
            db_manager: Database manager instance
            parent: Parent QObject
        """
        super().__init__(parent)

        self.db = db_manager
        self.settings_repo = SettingsRepository()
        # Thêm reference đến window manager
        self.window_manager = None
        # Track running apps
        self.running_apps: Dict[str, QWidget] = {}  # app_id -> window
        self.app_processes: Dict[str, QProcess] = {}  # app_id -> process (for external apps)

        # MDI area reference (if using MDI mode)
        self.mdi_area: Optional[QtWidgets.QMdiArea] = None

        # User permission (simplified)
        self.current_user_role = AppPermission.TEACHER  # Default to teacher

        # Cache loaded modules
        self._module_cache: Dict[str, Any] = {}

        # Setup cleanup on app quit
        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self.cleanup_all)

    # ========== MAIN LAUNCH METHOD ==========
    # Set window manager để quản lý windows
    def set_window_manager(self, window_manager):
        """Set window manager service"""
        self.window_manager = window_manager
    def launch_app(
            self,
            app: AppModel,
            window_mode: WindowMode = WindowMode.NORMAL,
            parent_window: QWidget = None,
            **kwargs
    ) -> Tuple[LaunchResult, Optional[QWidget]]:
        """
        Khởi chạy app

        Args:
            app: AppModel object
            window_mode: Chế độ cửa sổ
            parent_window: Parent window (for MDI or dialog)
            **kwargs: Additional arguments for app

        Returns:
            Tuple (LaunchResult, window object or None)
        """
        try:
            logger.info(f"Đang khởi chạy app: {app.id}")

            # 1. Validate app
            validation_result = self._validate_app(app)
            if validation_result != LaunchResult.SUCCESS:
                self.app_error.emit(app.id, f"Validation failed: {validation_result.value}")
                return validation_result, None

            # 2. Check permission
            if not self._check_permission(app):
                self.app_error.emit(app.id, "Không có quyền truy cập ứng dụng này")
                return LaunchResult.PERMISSION_DENIED, None

            # 3. Check if already running
            if self._is_app_running(app.id):
                # Focus existing window instead
                existing_window = self.running_apps.get(app.id)
                if existing_window:
                    self._focus_window(existing_window)
                    return LaunchResult.ALREADY_RUNNING, existing_window

            # 4. Show loading progress
            self.launch_progress.emit(20)

            # 5. Launch based on type
            window = None

            if app.exe_path:
                # External executable
                window = self._launch_external_app(app)
            else:
                # Python module
                window = self._launch_python_app(app, parent_window, **kwargs)

            if not window:
                self.app_error.emit(app.id, "Không thể tạo cửa sổ ứng dụng")
                return LaunchResult.FAILED, None

            # 6. Configure window
            self._configure_window(window, app, window_mode)

            # 7. Track running app
            self.running_apps[app.id] = window
            self.launch_progress.emit(100)
            # Emit signal với cả app_id và window
            self.app_launched.emit(app.id, window)
            # 8. Connect close signal
            self._connect_close_signal(window, app.id)

            # 9. Show window
            self._show_window(window, window_mode)

            # 10. Update statistics
            self._update_app_statistics(app)

            # Complete
            self.launch_progress.emit(100)
            self.app_launched.emit(app.id, window)

            logger.info(f"Đã khởi chạy app thành công: {app.id}")
            return LaunchResult.SUCCESS, window

        except Exception as e:
            logger.error(f"Lỗi khởi chạy app {app.id}: {e}")
            traceback.print_exc()
            self.app_error.emit(app.id, str(e))
            return LaunchResult.FAILED, None

    # ========== VALIDATION METHODS ==========

    def _validate_app(self, app: AppModel) -> LaunchResult:
        """
        Validate app trước khi launch

        Args:
            app: AppModel object

        Returns:
            LaunchResult
        """
        # Check app status
        if app.status == AppStatus.MAINTENANCE:
            return LaunchResult.MAINTENANCE

        if app.status == AppStatus.ERROR:
            return LaunchResult.FAILED

        if not app.enabled:
            return LaunchResult.FAILED

        # Check paths
        if app.exe_path:
            # Validate external exe
            if not self._validate_exe_path(app.exe_path):
                logger.error(f"Exe path không hợp lệ: {app.exe_path}")
                return LaunchResult.NOT_FOUND
        else:
            # Validate Python module
            if not app.module_path or not app.class_name:
                logger.error(f"Module path hoặc class name không được định nghĩa")
                return LaunchResult.NOT_FOUND

        return LaunchResult.SUCCESS

    def _validate_exe_path(self, exe_path: str) -> bool:
        """
        Kiểm tra exe path có hợp lệ không

        Args:
            exe_path: Đường dẫn exe

        Returns:
            True nếu hợp lệ
        """
        if not exe_path:
            return False

        path = Path(exe_path)
        if not path.exists():
            return False

        if not path.is_file():
            return False

        # Check executable permission on Unix
        if sys.platform != "win32":
            if not os.access(str(path), os.X_OK):
                return False

        return True

    # ========== PERMISSION METHODS ==========

    def _check_permission(self, app: AppModel) -> bool:
        """
        Kiểm tra quyền truy cập app

        Args:
            app: AppModel object

        Returns:
            True nếu có quyền
        """
        # Public apps - everyone can access
        if app.permission == AppPermission.PUBLIC:
            return True

        # Check specific permissions
        if app.permission == AppPermission.TEACHER:
            return self.current_user_role in [AppPermission.TEACHER, AppPermission.ADMIN]

        if app.permission == AppPermission.ADMIN:
            return self.current_user_role == AppPermission.ADMIN

        if app.permission == AppPermission.STUDENT:
            return self.current_user_role == AppPermission.STUDENT

        return False

    def set_user_role(self, role: AppPermission):
        """Set current user role for permission checking"""
        self.current_user_role = role
        logger.info(f"User role set to: {role.value}")

    # ========== LAUNCH METHODS ==========

    def _launch_python_app(
            self,
            app: AppModel,
            parent_window: QWidget = None,
            **kwargs
    ) -> Optional[QWidget]:
        """
        Launch Python module app

        Args:
            app: AppModel object
            parent_window: Parent window
            **kwargs: Arguments for app constructor

        Returns:
            Window object or None
        """
        try:
            self.launch_progress.emit(40)

            # Import module
            if app.module_path not in self._module_cache:
                logger.info(f"Importing module: {app.module_path}")
                module = importlib.import_module(app.module_path)
                self._module_cache[app.module_path] = module
            else:
                module = self._module_cache[app.module_path]

            self.launch_progress.emit(60)

            # Get class
            if not hasattr(module, app.class_name):
                raise AppNotFoundError(f"Class {app.class_name} not found in {app.module_path}")

            WindowClass = getattr(module, app.class_name)

            self.launch_progress.emit(80)

            # Create window instance
            if self.db:
                # Pass db_manager if constructor needs it
                try:
                    window = WindowClass(self.db, parent=parent_window)
                except:
                    window = WindowClass(parent=parent_window)
            else:
                window = WindowClass(parent=parent_window)

            # Set window properties
            if hasattr(window, 'setWindowTitle'):
                window.setWindowTitle(app.display_name)

            return window

        except ImportError as e:
            logger.error(f"Không thể import module {app.module_path}: {e}")
            raise AppNotFoundError(f"Module không tìm thấy: {app.module_path}")
        except Exception as e:
            logger.error(f"Lỗi tạo window cho {app.id}: {e}")
            raise AppLaunchError(f"Không thể tạo window: {e}")

    def _launch_external_app(self, app: AppModel) -> Optional[QWidget]:
        """
        Launch external executable app

        Args:
            app: AppModel object

        Returns:
            Placeholder widget or None
        """
        try:
            # Create QProcess to launch external app
            process = QProcess()

            # Connect signals
            process.started.connect(lambda: logger.info(f"Started: {app.exe_path}"))
            process.finished.connect(lambda: self._on_external_app_closed(app.id))
            process.errorOccurred.connect(lambda e: logger.error(f"Process error: {e}"))

            # Start process
            process.start(app.exe_path)

            if not process.waitForStarted(5000):  # 5 seconds timeout
                raise AppLaunchError(f"Không thể khởi động: {app.exe_path}")

            # Store process
            self.app_processes[app.id] = process

            # Create placeholder widget to track
            placeholder = QWidget()
            placeholder.setWindowTitle(f"{app.display_name} (External)")
            placeholder.setMinimumSize(200, 100)

            label = QtWidgets.QLabel(f"Đang chạy: {app.display_name}")
            label.setAlignment(Qt.AlignCenter)

            layout = QtWidgets.QVBoxLayout(placeholder)
            layout.addWidget(label)

            return placeholder

        except Exception as e:
            logger.error(f"Lỗi launch external app: {e}")
            raise AppLaunchError(f"Không thể chạy external app: {e}")

    # ========== WINDOW CONFIGURATION ==========

    def _configure_window(self, window: QWidget, app: AppModel, mode: WindowMode):
        """
        Configure window properties

        Args:
            window: Window object
            app: AppModel object
            mode: WindowMode
        """
        # Set window icon
        if app.icon_path and os.path.exists(app.icon_path):
            window.setWindowIcon(QtGui.QIcon(app.icon_path))
        elif app.icon_name:
            from ..utils.assets import load_icon
            icon = load_icon(app.icon_name)
            window.setWindowIcon(icon)

        # Set window flags
        flags = window.windowFlags()

        if app.always_on_top:
            flags |= Qt.WindowStaysOnTopHint

        if not app.resizable:
            flags |= Qt.MSWindowsFixedSizeDialogHint

        window.setWindowFlags(flags)

        # Set size
        if app.default_size:
            window.resize(*app.default_size)

        # Set size constraints
        if not app.resizable:
            window.setFixedSize(window.size())

        if not app.maximizable:
            window.setWindowFlag(Qt.WindowMaximizeButtonHint, False)

        if not app.minimizable:
            window.setWindowFlag(Qt.WindowMinimizeButtonHint, False)

    def _show_window(self, window: QWidget, mode: WindowMode):
        """Show window with specified mode"""
        # Nếu có window_manager và mode là MDI
        if mode == WindowMode.MDI and self.window_manager:
            # Tạo window qua window_manager
            app_id = getattr(window, 'app_id', 'unknown')
            title = window.windowTitle()

            window_id = self.window_manager.create_window(
                app_id=app_id,
                title=title,
                content=window
            )

            if window_id:
                # Lưu reference
                self.running_apps[app_id] = self.window_manager.windows[window_id]
        elif mode == WindowMode.MDI and self.mdi_area:
            # Fallback cũ nếu không có window_manager
            sub_window = self.mdi_area.addSubWindow(window)
            sub_window.show()
        elif mode == WindowMode.MAXIMIZED:
            window.showMaximized()
        elif mode == WindowMode.MINIMIZED:
            window.showMinimized()
        elif mode == WindowMode.FULLSCREEN:
            window.showFullScreen()
        else:
            window.show()
    def _focus_window(self, window: QWidget):
        """
        Focus existing window

        Args:
            window: Window to focus
        """
        if window.isMinimized():
            window.showNormal()

        window.raise_()
        window.activateWindow()

        # Flash taskbar if needed
        if sys.platform == "win32":
            # Windows-specific flashing
            from ctypes import windll
            try:
                hwnd = int(window.winId())
                windll.user32.FlashWindow(hwnd, True)
            except:
                pass

    # ========== TRACKING & CLEANUP ==========

    def _is_app_running(self, app_id: str) -> bool:
        """
        Check if app is running

        Args:
            app_id: App ID

        Returns:
            True if running
        """
        if app_id in self.running_apps:
            window = self.running_apps[app_id]
            if window and not window.isHidden():
                return True
            else:
                # Clean up dead reference
                del self.running_apps[app_id]

        if app_id in self.app_processes:
            process = self.app_processes[app_id]
            if process.state() == QProcess.Running:
                return True
            else:
                # Clean up finished process
                del self.app_processes[app_id]

        return False

    def _connect_close_signal(self, window: QWidget, app_id: str):
        """
        Connect close signal to track when app closes

        Args:
            window: Window object
            app_id: App ID
        """
        # For QMainWindow and QDialog
        if isinstance(window, (QMainWindow, QDialog)):
            # Override closeEvent
            original_close = window.closeEvent

            def new_close_event(event):
                original_close(event)
                if event.isAccepted():
                    self._on_app_closed(app_id)

            window.closeEvent = new_close_event
        else:
            # For QWidget, use destroyed signal
            window.destroyed.connect(lambda: self._on_app_closed(app_id))

    def _on_app_closed(self, app_id: str):
        """Handle when app is closed"""
        logger.info(f"App closed: {app_id}")

        # Remove from tracking
        if app_id in self.running_apps:
            del self.running_apps[app_id]

        if app_id in self.app_processes:
            self.app_processes[app_id].terminate()
            del self.app_processes[app_id]

        # Emit signal
        self.app_closed.emit(app_id)  # Đảm bảo có dòng này
    def _on_external_app_closed(self, app_id: str):
        """
        Handle external app closed

        Args:
            app_id: App ID
        """
        logger.info(f"External app closed: {app_id}")

        # Clean up process
        if app_id in self.app_processes:
            del self.app_processes[app_id]

        # Clean up placeholder window
        if app_id in self.running_apps:
            window = self.running_apps[app_id]
            if window:
                window.close()
            del self.running_apps[app_id]

        self.app_closed.emit(app_id)

    # ========== STATISTICS ==========

    def _update_app_statistics(self, app: AppModel):
        """
        Update app usage statistics

        Args:
            app: AppModel object
        """
        try:
            # Update in repository
            from ..repositories.app_repository import AppRepository
            repo = AppRepository()
            repo.update_usage_stats(app.id)

            # Add to recent apps in settings
            self.settings_repo.add_recent_app(app.id)

        except Exception as e:
            logger.error(f"Lỗi update statistics: {e}")

    # ========== PUBLIC METHODS ==========

    def launch_app_by_id(
            self,
            app_id: str,
            window_mode: WindowMode = WindowMode.NORMAL,
            parent_window: QWidget = None,
            **kwargs
    ) -> Tuple[LaunchResult, Optional[QWidget]]:
        """
        Launch app by ID

        Args:
            app_id: App ID
            window_mode: Window mode
            parent_window: Parent window
            **kwargs: Additional arguments

        Returns:
            Tuple (LaunchResult, window)
        """
        from ..repositories.app_repository import AppRepository
        repo = AppRepository()

        app = repo.get_app_by_id(app_id)
        if not app:
            self.app_error.emit(app_id, f"App không tồn tại: {app_id}")
            return LaunchResult.NOT_FOUND, None

        return self.launch_app(app, window_mode, parent_window, **kwargs)

    def close_app(self, app_id: str) -> bool:
        """
        Close running app

        Args:
            app_id: App ID

        Returns:
            True if closed successfully
        """
        try:
            # Close internal window
            if app_id in self.running_apps:
                window = self.running_apps[app_id]
                if window:
                    window.close()
                return True

            # Terminate external process
            if app_id in self.app_processes:
                process = self.app_processes[app_id]
                process.terminate()
                if not process.waitForFinished(5000):
                    process.kill()
                return True

            return False

        except Exception as e:
            logger.error(f"Lỗi close app {app_id}: {e}")
            return False

    def close_all_apps(self):
        """Close all running apps"""
        # Copy list to avoid modification during iteration
        app_ids = list(self.running_apps.keys()) + list(self.app_processes.keys())

        for app_id in app_ids:
            self.close_app(app_id)

    def get_running_apps(self) -> List[str]:
        """
        Get list of running app IDs

        Returns:
            List of app IDs
        """
        running = []

        # Check internal apps
        for app_id in list(self.running_apps.keys()):
            if self._is_app_running(app_id):
                running.append(app_id)

        # Check external apps
        for app_id in list(self.app_processes.keys()):
            if self._is_app_running(app_id):
                running.append(app_id)

        return running

    def get_app_window(self, app_id: str) -> Optional[QWidget]:
        """
        Get window object of running app

        Args:
            app_id: App ID

        Returns:
            Window object or None
        """
        return self.running_apps.get(app_id)

    def set_mdi_area(self, mdi_area: QtWidgets.QMdiArea):
        """
        Set MDI area for MDI mode

        Args:
            mdi_area: QMdiArea object
        """
        self.mdi_area = mdi_area

    def cleanup_all(self):
        """Cleanup all resources on quit"""
        logger.info("Cleaning up app launcher service...")
        self.close_all_apps()
        self._module_cache.clear()

    # ========== ADMIN METHODS ==========

    def run_as_admin(self, app: AppModel) -> bool:
        """
        Run app with admin privileges

        Args:
            app: AppModel object

        Returns:
            True if successful
        """
        try:
            if sys.platform == "win32":
                import ctypes

                if app.exe_path:
                    # Run external app as admin
                    ctypes.windll.shell32.ShellExecuteW(
                        None, "runas", app.exe_path, None, None, 1
                    )
                else:
                    # Run Python script as admin
                    ctypes.windll.shell32.ShellExecuteW(
                        None, "runas", sys.executable,
                        f"-m {app.module_path}", None, 1
                    )
                return True
            else:
                # Unix-like systems
                if app.exe_path:
                    subprocess.run(["sudo", app.exe_path])
                else:
                    subprocess.run(["sudo", sys.executable, "-m", app.module_path])
                return True

        except Exception as e:
            logger.error(f"Lỗi run as admin: {e}")
            return False

    # ========== ERROR HANDLING ==========

    def handle_launch_error(self, app_id: str, error: Exception):
        """
        Handle and display launch error

        Args:
            app_id: App ID
            error: Exception object
        """
        error_msg = str(error)
        logger.error(f"Launch error for {app_id}: {error_msg}")

        # Determine error type and message
        if isinstance(error, AppNotFoundError):
            title = "Không tìm thấy ứng dụng"
            msg = f"Ứng dụng '{app_id}' không tồn tại hoặc đã bị xóa."
        elif isinstance(error, PermissionDeniedError):
            title = "Không có quyền truy cập"
            msg = f"Bạn không có quyền mở ứng dụng '{app_id}'."
        elif isinstance(error, AppAlreadyRunningError):
            title = "Ứng dụng đang chạy"
            msg = f"Ứng dụng '{app_id}' đã được mở."
        else:
            title = "Lỗi khởi chạy ứng dụng"
            msg = f"Không thể mở ứng dụng '{app_id}'.\n\nLỗi: {error_msg}"

        # Show error dialog
        QMessageBox.critical(None, title, msg)

        # Emit error signal
        self.app_error.emit(app_id, error_msg)


# ========== ASYNC APP LAUNCHER ==========

class AsyncAppLauncher(QThread):
    """
    Async launcher for heavy apps that need background loading
    """

    # Signals
    progress = Signal(int)
    finished = Signal(object)  # window object
    error = Signal(str)

    def __init__(self, app: AppModel, service: AppLauncherService, parent=None):
        super().__init__(parent)
        self.app = app
        self.service = service
        self.window = None

    def run(self):
        """Run app launch in background thread"""
        try:
            self.progress.emit(10)

            # Note: GUI operations must be done in main thread
            # This is just for demonstration

            self.progress.emit(50)

            # Simulate heavy loading
            import time
            time.sleep(1)

            self.progress.emit(100)

            # Signal completion (actual window creation must be in main thread)
            self.finished.emit(None)

        except Exception as e:
            self.error.emit(str(e))