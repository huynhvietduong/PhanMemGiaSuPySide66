# app_qt.py
"""
Main Application Entry Point - Dashboard Desktop-Style
Khởi động ứng dụng với giao diện Desktop Windows-like
"""

import sys
import os
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication, QMessageBox, QSplashScreen
from PySide6.QtCore import Qt, QTimer, QTranslator, QLocale, QSettings
from PySide6.QtGui import QPixmap, QIcon, QFont, QPalette, QColor

# Import database
from database import DatabaseManager


# ========== LOGGING SETUP ==========
def setup_logging():
    """Cấu hình logging cho ứng dụng"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    return logging.getLogger(__name__)


# ========== SPLASH SCREEN ==========
class SplashScreen(QSplashScreen):
    """Custom splash screen với progress updates"""

    def __init__(self):
        super().__init__()
        self.create_splash()

    def create_splash(self):
        """Tạo giao diện splash screen"""
        # Tạo pixmap
        splash_pix = QPixmap(700, 450)
        splash_pix.fill(Qt.transparent)

        # Vẽ nội dung
        from PySide6.QtGui import QPainter, QLinearGradient, QBrush
        painter = QPainter(splash_pix)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background gradient giống Windows 11
        gradient = QLinearGradient(0, 0, 700, 450)
        gradient.setColorAt(0.0, QColor(0, 120, 215))  # Windows Blue
        gradient.setColorAt(0.5, QColor(0, 90, 180))
        gradient.setColorAt(1.0, QColor(0, 60, 120))

        painter.fillRect(splash_pix.rect(), QBrush(gradient))

        # Logo/Icon
        logo_rect = splash_pix.rect().adjusted(0, -50, 0, 0)
        painter.setPen(Qt.white)

        # Title
        title_font = QFont("Segoe UI", 36, QFont.Bold)
        painter.setFont(title_font)
        painter.drawText(logo_rect, Qt.AlignCenter, "📚 Dashboard Desktop")

        # Subtitle
        subtitle_font = QFont("Segoe UI", 18)
        painter.setFont(subtitle_font)
        painter.drawText(
            splash_pix.rect().adjusted(0, 40, 0, 0),
            Qt.AlignCenter,
            "Phần mềm Quản lý Gia sư"
        )

        # Loading text area
        loading_font = QFont("Segoe UI", 11)
        painter.setFont(loading_font)
        painter.drawText(
            splash_pix.rect().adjusted(20, 0, -20, -30),
            Qt.AlignBottom | Qt.AlignLeft,
            "Đang khởi động..."
        )

        # Version
        version_font = QFont("Segoe UI", 10)
        painter.setFont(version_font)
        painter.setPen(QColor(200, 200, 200))
        painter.drawText(
            splash_pix.rect().adjusted(0, 0, -20, -10),
            Qt.AlignBottom | Qt.AlignRight,
            "Version 1.0.0 - Desktop Style"
        )

        painter.end()

        # Set pixmap
        self.setPixmap(splash_pix)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)

    def show_message(self, message: str, progress: int = -1):
        """Hiển thị thông báo trên splash"""
        if progress >= 0:
            msg = f"{message} ({progress}%)"
        else:
            msg = message

        self.showMessage(
            msg,
            Qt.AlignBottom | Qt.AlignLeft,
            Qt.white
        )
        QApplication.processEvents()


# ========== APPLICATION SETUP ==========
def setup_application():
    """Cấu hình QApplication với style Windows"""
    # High DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)

    # Application metadata
    app.setApplicationName("Dashboard Desktop")
    app.setApplicationDisplayName("Dashboard Desktop - Phần mềm Gia sư")
    app.setOrganizationName("TutorSoft")
    app.setOrganizationDomain("tutorsoft.vn")

    # Windows-like style
    app.setStyle("Fusion")  # Modern Windows-like style

    # Application icon
    icon_path = Path("ui_qt/windows/dashboard_window_qt/assets/icons/app.png")
    if not icon_path.exists():
        # Create default icon if not exists
        icon_path.parent.mkdir(parents=True, exist_ok=True)

    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Default font - Segoe UI like Windows
    default_font = QFont("Segoe UI", 10)
    default_font.setStyleHint(QFont.SansSerif)
    app.setFont(default_font)

    # Color palette - Windows 11 style
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.WindowText, Qt.black)
    palette.setColor(QPalette.Base, Qt.white)
    palette.setColor(QPalette.AlternateBase, QColor(245, 245, 245))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.black)
    palette.setColor(QPalette.Text, Qt.black)
    palette.setColor(QPalette.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ButtonText, Qt.black)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(0, 120, 215))
    palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
    palette.setColor(QPalette.HighlightedText, Qt.white)
    app.setPalette(palette)

    return app


# ========== REQUIREMENTS CHECK ==========
def check_and_create_structure():
    """Kiểm tra và tạo cấu trúc thư mục cần thiết"""
    logger = logging.getLogger(__name__)

    # Base path
    base_path = Path("ui_qt/windows/dashboard_window_qt")

    # Required structure
    required_dirs = [
        base_path,
        base_path / "assets",
        base_path / "assets/icons",
        base_path / "assets/wallpapers",
        base_path / "assets/themes",
        base_path / "assets/sounds",
        base_path / "repositories",
        base_path / "services",
        base_path / "utils",
        base_path / "views",
        base_path / "views/desktop",
        base_path / "views/taskbar",
        base_path / "views/start_menu",
        base_path / "views/widgets"
    ]

    # Create directories
    for dir_path in required_dirs:
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {dir_path}")

    # Check for main files
    main_file = base_path / "views/main_dashboard.py"
    if not main_file.exists():
        logger.warning(f"Main dashboard file not found: {main_file}")

        # Try to use fallback
        fallback = base_path / "dashboard_window_qt.py"
        if fallback.exists():
            logger.info("Using fallback dashboard file")
            return "fallback"

    return "main"


# ========== LOAD DASHBOARD ==========
def load_dashboard(db_manager, mode="main"):
    """Load Dashboard với error handling"""
    logger = logging.getLogger(__name__)

    try:
        if mode == "main":
            # Try loading new MainDashboard
            try:
                from ui_qt.windows.dashboard_window_qt.views.main_dashboard import MainDashboard
                logger.info("Loading MainDashboard (Desktop-Style)...")
                window = MainDashboard(db_manager)
                window.setWindowTitle("Dashboard Desktop - Phần mềm Quản lý Gia sư")
                return window, "main"

            except ImportError as e:
                logger.warning(f"Cannot import MainDashboard: {e}")
                mode = "fallback"

        if mode == "fallback":
            # Try loading old DashboardWindowQt
            try:
                from ui_qt.windows.dashboard_window_qt import DashboardWindowQt
                logger.info("Loading DashboardWindowQt (Classic)...")
                window = DashboardWindowQt(db_manager)
                return window, "classic"

            except ImportError as e:
                logger.error(f"Cannot import any dashboard: {e}")
                raise

    except Exception as e:
        logger.error(f"Failed to load dashboard: {e}")
        raise


# ========== INITIALIZE SERVICES ==========
def initialize_services(window, splash=None):
    """Khởi tạo các services cần thiết"""
    logger = logging.getLogger(__name__)

    try:
        if splash:
            splash.show_message("Đang tải assets...", 60)

        # Initialize Assets Manager
        from ui_qt.windows.dashboard_window_qt.utils.assets import AssetsManager
        assets = AssetsManager()
        logger.info("Assets manager initialized")

        if splash:
            splash.show_message("Đang tải cấu hình...", 70)

        # Initialize Settings Repository
        from ui_qt.windows.dashboard_window_qt.repositories.settings_repository import SettingsRepository
        settings = SettingsRepository()
        logger.info("Settings loaded")

        if splash:
            splash.show_message("Đang tải ứng dụng...", 80)

        # Initialize App Repository
        from ui_qt.windows.dashboard_window_qt.repositories.app_repository import AppRepository
        app_repo = AppRepository()

        # Load default apps if empty
        if not app_repo.get_all_apps():
            logger.info("Loading default applications...")
            app_repo._load_default_apps()

        if splash:
            splash.show_message("Đang khởi tạo services...", 90)

        # Initialize App Launcher Service
        from ui_qt.windows.dashboard_window_qt.services.app_launcher_service import AppLauncherService
        if hasattr(window, 'db'):
            launcher = AppLauncherService(window.db)
            if hasattr(window, 'set_launcher_service'):
                window.set_launcher_service(launcher)

        logger.info("All services initialized successfully")

    except Exception as e:
        logger.error(f"Error initializing services: {e}")
        # Continue anyway - services are optional enhancements


# ========== MAIN FUNCTION ==========
def main():
    """Main entry point của ứng dụng"""
    # Setup logging
    logger = setup_logging()
    logger.info("=" * 70)
    logger.info("🚀 Starting Dashboard Desktop Application")
    logger.info("=" * 70)

    try:
        # Create QApplication
        app = setup_application()
        logger.info("✓ Application initialized")

        # Create and show splash screen
        splash = SplashScreen()
        splash.show()
        splash.show_message("Đang khởi động Dashboard Desktop...", 10)

        # Check and create directory structure
        splash.show_message("Đang kiểm tra cấu trúc...", 20)
        dashboard_mode = check_and_create_structure()
        logger.info(f"✓ Directory structure ready (mode: {dashboard_mode})")

        # Initialize database
        splash.show_message("Đang kết nối database...", 30)
        try:
            db = DatabaseManager()
            logger.info("✓ Database connected")
        except Exception as e:
            splash.close()
            logger.error(f"✗ Database error: {e}")
            QMessageBox.critical(
                None,
                "Lỗi Database",
                f"Không thể kết nối database:\n{str(e)}\n\n"
                "Vui lòng kiểm tra:\n"
                "1. File database có tồn tại\n"
                "2. Quyền truy cập file\n"
                "3. Database không bị corrupt"
            )
            return 1

        # Load main dashboard
        splash.show_message("Đang tải giao diện chính...", 50)
        try:
            window, window_type = load_dashboard(db, dashboard_mode)
            logger.info(f"✓ Dashboard loaded ({window_type})")
        except Exception as e:
            splash.close()
            logger.error(f"✗ Failed to create window: {e}")

            import traceback
            traceback.print_exc()

            QMessageBox.critical(
                None,
                "Lỗi khởi động",
                f"Không thể tạo cửa sổ chính:\n{str(e)}\n\n"
                "Vui lòng kiểm tra:\n"
                "1. Các file cần thiết có đầy đủ\n"
                "2. Không có lỗi syntax trong code\n"
                "3. Xem file log để biết chi tiết"
            )
            return 1

        # Initialize services
        initialize_services(window, splash)

        # Final preparation
        splash.show_message("Hoàn tất khởi động...", 100)

        # Schedule splash close and window show
        QTimer.singleShot(1500, splash.close)
        QTimer.singleShot(1600, lambda: show_main_window(window))

        # Setup shutdown handler
        def on_shutdown():
            logger.info("Shutting down application...")
            try:
                # Save settings if available
                if hasattr(window, 'save_settings'):
                    window.save_settings()
                    logger.info("✓ Settings saved")

                # Close database
                if db:
                    db.close()
                    logger.info("✓ Database closed")

            except Exception as e:
                logger.error(f"Error during shutdown: {e}")

            logger.info("=" * 70)
            logger.info("Application shutdown complete")
            logger.info("=" * 70)

        app.aboutToQuit.connect(on_shutdown)

        # Run application
        logger.info("✓ Application ready - Starting event loop")
        return app.exec()

    except Exception as e:
        logger.error(f"✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()

        try:
            QMessageBox.critical(
                None,
                "Lỗi nghiêm trọng",
                f"Đã xảy ra lỗi nghiêm trọng:\n{str(e)}\n\n"
                "Ứng dụng sẽ đóng."
            )
        except:
            pass

        return 1


def show_main_window(window):
    """Hiển thị cửa sổ chính với animation"""
    window.show()

    # Maximize by default (Windows desktop style)
    window.showMaximized()

    # Bring to front
    window.raise_()
    window.activateWindow()


# ========== DEVELOPMENT MODE ==========
def main_dev():
    """Chế độ development - không có splash, nhiều log hơn"""
    # Verbose logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s'
    )

    logger = logging.getLogger(__name__)
    logger.info("🔧 Starting in DEVELOPMENT mode")

    # Create app
    app = setup_application()

    # Check structure
    check_and_create_structure()

    # Create database
    db = DatabaseManager()

    # Load dashboard
    try:
        window, _ = load_dashboard(db, "main")
    except:
        logger.error("Using simple fallback")
        from ui_qt.windows.dashboard_window_qt import DashboardWindowQt
        window = DashboardWindowQt(db)

    # Initialize services
    initialize_services(window)

    # Show immediately
    window.show()
    window.showMaximized()

    return app.exec()


# ========== ENTRY POINT ==========
if __name__ == "__main__":
    # Check command line arguments
    if "--dev" in sys.argv:
        sys.exit(main_dev())
    elif "--help" in sys.argv:
        print("Dashboard Desktop - Phần mềm Quản lý Gia sư")
        print("\nOptions:")
        print("  --dev        Development mode (no splash, verbose logging)")
        print("  --help       Show this help message")
        sys.exit(0)
    else:
        sys.exit(main())