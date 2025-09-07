# ui_qt/windows/dashboard_window_qt/utils/constants.py
"""
Module chứa các hằng số cho Dashboard Desktop-Style
Bao gồm: kích thước, màu sắc, đường dẫn, cấu hình mặc định
"""

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor
from pathlib import Path

# ========== PATHS - Đường dẫn ==========
BASE_DIR = Path(__file__).parent.parent  # Thư mục dashboard_window_qt
ASSETS_DIR = BASE_DIR / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
WALLPAPERS_DIR = ASSETS_DIR / "wallpapers"
THEMES_DIR = ASSETS_DIR / "themes"
SOUNDS_DIR = ASSETS_DIR / "sounds"

# Database và Settings
DB_PATH = "tutor_app.db"
SETTINGS_FILE = "dashboard_settings.json"
LAYOUT_STATE_FILE = "dashboard_layout.json"
ICON_POSITIONS_FILE = "desktop_icons.json"

# ========== DIMENSIONS - Kích thước ==========
# Desktop Area
DESKTOP_MIN_WIDTH = 800
DESKTOP_MIN_HEIGHT = 600
DESKTOP_GRID_SIZE = 100  # Kích thước 1 ô lưới cho icons
DESKTOP_GRID_SPACING = 10  # Khoảng cách giữa các ô

# Icon Sizes
ICON_SIZE_SMALL = QSize(32, 32)
ICON_SIZE_MEDIUM = QSize(48, 48)
ICON_SIZE_LARGE = QSize(64, 64)
ICON_SIZE_EXTRA_LARGE = QSize(96, 96)
DEFAULT_ICON_SIZE = ICON_SIZE_LARGE

# Desktop Icon Dimensions
DESKTOP_ICON_WIDTH = 75
DESKTOP_ICON_HEIGHT = 90  # Icon + Label
DESKTOP_ICON_SPACING = 20
DESKTOP_ICON_TEXT_HEIGHT = 30

# Taskbar
TASKBAR_HEIGHT = 45
TASKBAR_BUTTON_WIDTH = 50
TASKBAR_BUTTON_HEIGHT = 40
TASKBAR_BUTTON_MIN_WIDTH = 45
TASKBAR_BUTTON_MAX_WIDTH = 200
TASKBAR_ICON_SIZE = QSize(24, 24)
TASKBAR_PREVIEW_WIDTH = 200
TASKBAR_PREVIEW_HEIGHT = 150

# Start Menu
START_MENU_WIDTH = 450
START_MENU_HEIGHT = 600
START_MENU_TILE_SIZE = QSize(100, 100)
START_MENU_TILE_SMALL = QSize(50, 50)
START_MENU_TILE_MEDIUM = QSize(100, 100)
START_MENU_TILE_LARGE = QSize(200, 100)
START_MENU_TILE_WIDE = QSize(200, 200)
START_MENU_ANIMATION_DURATION = 300
# System Tray
SYSTEM_TRAY_ICON_SIZE = QSize(16, 16)
CLOCK_WIDTH = 100
NOTIFICATION_BADGE_SIZE = 18

# Windows
WINDOW_MIN_WIDTH = 400
WINDOW_MIN_HEIGHT = 300
WINDOW_DEFAULT_WIDTH = 800
WINDOW_DEFAULT_HEIGHT = 600
WINDOW_BORDER_WIDTH = 2
WINDOW_TITLE_HEIGHT = 30
WINDOW_ANIMATION_DURATION = 300

# Widgets
WIDGET_MIN_SIZE = QSize(150, 100)
CLOCK_WIDGET_SIZE = QSize(200, 200)
WEATHER_WIDGET_SIZE = QSize(250, 150)
NOTE_WIDGET_SIZE = QSize(200, 250)
NOTIFICATION_WIDTH = 350
NOTIFICATION_HEIGHT = 80
NOTIFICATION_MARGIN = 10

# ========== COLORS - Màu sắc ==========
# Theme Colors - Light Mode
LIGHT_BACKGROUND = QColor(240, 240, 240)
LIGHT_FOREGROUND = QColor(33, 33, 33)
LIGHT_ACCENT = QColor(0, 120, 215)  # Windows Blue
LIGHT_HOVER = QColor(229, 241, 251)
LIGHT_SELECTED = QColor(204, 232, 255)
LIGHT_BORDER = QColor(217, 217, 217)

# Theme Colors - Dark Mode
DARK_BACKGROUND = QColor(30, 30, 30)
DARK_FOREGROUND = QColor(255, 255, 255)
DARK_ACCENT = QColor(0, 150, 255)
DARK_HOVER = QColor(63, 63, 70)
DARK_SELECTED = QColor(75, 75, 80)
DARK_BORDER = QColor(67, 67, 67)

# Status Colors
COLOR_SUCCESS = QColor(16, 185, 129)  # Green
COLOR_WARNING = QColor(245, 158, 11)  # Orange
COLOR_ERROR = QColor(239, 68, 68)     # Red
COLOR_INFO = QColor(59, 130, 246)     # Blue

# Taskbar Colors
TASKBAR_BG = QColor(40, 40, 40, 230)  # Semi-transparent
TASKBAR_BUTTON_HOVER = QColor(60, 60, 60, 200)
TASKBAR_BUTTON_ACTIVE = QColor(80, 80, 80, 200)
TASKBAR_INDICATOR = QColor(0, 120, 215)

# Desktop Colors
DESKTOP_ICON_TEXT_COLOR = QColor(255, 255, 255)
DESKTOP_ICON_TEXT_SHADOW = QColor(0, 0, 0, 128)
DESKTOP_SELECTION_COLOR = QColor(0, 120, 215, 100)

# ========== ANIMATIONS - Hiệu ứng ==========
ANIMATION_DURATION_FAST = 150    # ms
ANIMATION_DURATION_NORMAL = 300  # ms
ANIMATION_DURATION_SLOW = 500    # ms
FADE_DURATION = 200
SLIDE_DURATION = 250
BOUNCE_DURATION = 400

# Easing Curves
EASING_IN_OUT = "InOutCubic"
EASING_OUT = "OutCubic"
EASING_BOUNCE = "OutBounce"

# ========== TIMING - Thời gian ==========
DOUBLE_CLICK_INTERVAL = 400  # ms
HOVER_PREVIEW_DELAY = 500    # ms
TOOLTIP_DELAY = 1000          # ms
AUTO_HIDE_DURATION = 5000    # ms cho notifications
AUTO_SAVE_INTERVAL = 60000   # ms (1 phút)
CLOCK_UPDATE_INTERVAL = 1000 # ms
WEATHER_UPDATE_INTERVAL = 1800000  # ms (30 phút)

# Session
SESSION_TIMEOUT = 1800  # seconds (30 phút)
IDLE_TIME_WARNING = 1500  # seconds (25 phút)

# ========== LIMITS - Giới hạn ==========
MAX_RECENT_APPS = 10
MAX_PINNED_APPS = 20
MAX_DESKTOP_ICONS = 100
MAX_NOTIFICATIONS = 5
MAX_SEARCH_RESULTS = 20
MAX_UNDO_HISTORY = 50
MAX_OPEN_WINDOWS = 30

# Icon Grid
MAX_ICONS_PER_ROW = 10
MAX_ICONS_PER_COLUMN = 7

# ========== DEFAULT VALUES - Giá trị mặc định ==========
DEFAULT_THEME = "light"
DEFAULT_WALLPAPER = "default_wallpaper.jpg"
DEFAULT_LANGUAGE = "vi_VN"
DEFAULT_FONT_FAMILY = "Segoe UI"
DEFAULT_FONT_SIZE = 10
DEFAULT_ICON_VIEW = "large"
DEFAULT_SORT_ORDER = "name"
DEFAULT_GRID_SNAP = True
DEFAULT_SHOW_DESKTOP_ICONS = True
DEFAULT_SHOW_WIDGETS = True
DEFAULT_TRANSPARENCY = 0.95

# ========== LIMITS & RECENT ITEMS ==========
MAX_RECENT_ITEMS = 10
MAX_RECENT_FILES = 15
MAX_RECENT_APPS = 8
MAX_CLIPBOARD_HISTORY = 20

 #========== LAYOUT & RESPONSIVE CONSTANTS ==========
SIDEBAR_WIDTH = 250              # Default sidebar width
BREAKPOINT_MOBILE = 768          # Mobile breakpoint (px)
BREAKPOINT_TABLET = 1024         # Tablet breakpoint (px)
BREAKPOINT_DESKTOP = 1200        # Desktop breakpoint (px)

# Layout dimensions
LAYOUT_MARGIN = 8
LAYOUT_SPACING = 4
SPLITTER_HANDLE_WIDTH = 6

# ========== TILE CONSTANTS - Start Menu Tiles ==========
TILE_SMALL_SIZE = 64      # 1x1 grid cell
TILE_MEDIUM_SIZE = 128    # 2x2 grid cells
TILE_WIDE_SIZE = 264      # 4x2 grid cells (wide rectangle)
TILE_LARGE_SIZE = 264     # 4x4 grid cells
TILE_SPACING = 4          # Khoảng cách giữa tiles
TILE_ANIMATION_DURATION = 250  # ms - thời gian animation
# ========== APP CATEGORIES - Danh mục ứng dụng ==========
APP_CATEGORIES = {
    "learning": {
        "name": "📚 Học tập",
        "icon": "learning.png",
        "apps": ["question_bank", "exercise_manager", "test_creator"]
    },
    "management": {
        "name": "👥 Quản lý",
        "icon": "management.png",
        "apps": ["student_window", "group_window", "attendance_report"]
    },
    "reports": {
        "name": "📊 Báo cáo",
        "icon": "reports.png",
        "apps": ["progress_report", "skill_report", "salary_window"]
    },
    "tools": {
        "name": "🛠️ Công cụ",
        "icon": "tools.png",
        "apps": ["calculator", "notepad", "file_manager"]
    },
    "system": {
        "name": "⚙️ Hệ thống",
        "icon": "system.png",
        "apps": ["settings", "database_manager", "backup_restore"]
    }
}

# ========== FILE EXTENSIONS - Phần mở rộng ==========
SUPPORTED_IMAGE_FORMATS = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg"]
SUPPORTED_VIDEO_FORMATS = [".mp4", ".avi", ".mkv", ".mov", ".wmv"]
SUPPORTED_DOCUMENT_FORMATS = [".pdf", ".doc", ".docx", ".txt", ".rtf"]
EXECUTABLE_FORMATS = [".exe", ".py", ".pyw", ".bat", ".cmd"]

# ========== SHORTCUTS - Phím tắt ==========
SHORTCUTS = {
    "show_start_menu": "Meta",  # Windows key
    "show_desktop": "Meta+D",
    "lock_screen": "Meta+L",
    "task_view": "Meta+Tab",
    "switch_apps": "Alt+Tab",
    "close_app": "Alt+F4",
    "minimize_all": "Meta+M",
    "new_folder": "Ctrl+Shift+N",
    "search": "Meta+S",
    "settings": "Meta+I",
    "file_explorer": "Meta+E",
    "run_dialog": "Meta+R",
    "refresh": "F5",
    "rename": "F2",
    "properties": "Alt+Enter",
    "fullscreen": "F11",
    "task_manager": "Ctrl+Shift+Esc"
}

# ========== CONTEXT MENU ITEMS - Menu chuột phải ==========
DESKTOP_CONTEXT_MENU = [
    {"id": "view", "label": "Xem", "icon": "view.png"},
    {"id": "sort", "label": "Sắp xếp theo", "icon": "sort.png"},
    {"id": "refresh", "label": "Làm mới", "icon": "refresh.png", "shortcut": "F5"},
    {"type": "separator"},
    {"id": "new", "label": "Mới", "icon": "new.png"},
    {"id": "paste", "label": "Dán", "icon": "paste.png", "shortcut": "Ctrl+V"},
    {"type": "separator"},
    {"id": "personalize", "label": "Cá nhân hóa", "icon": "personalize.png"},
    {"id": "display_settings", "label": "Cài đặt hiển thị", "icon": "display.png"}
]

TASKBAR_CONTEXT_MENU = [
    {"id": "toolbars", "label": "Thanh công cụ", "icon": "toolbar.png"},
    {"id": "search", "label": "Tìm kiếm", "icon": "search.png", "checkable": True},
    {"id": "task_view", "label": "Nút xem tác vụ", "icon": "task_view.png", "checkable": True},
    {"type": "separator"},
    {"id": "cascade", "label": "Xếp chồng cửa sổ", "icon": "cascade.png"},
    {"id": "tile_horizontal", "label": "Xếp ngang", "icon": "tile_h.png"},
    {"id": "tile_vertical", "label": "Xếp dọc", "icon": "tile_v.png"},
    {"id": "minimize_all", "label": "Thu nhỏ tất cả", "icon": "minimize.png"},
    {"type": "separator"},
    {"id": "task_manager", "label": "Trình quản lý tác vụ", "icon": "task_manager.png"},
    {"id": "lock_taskbar", "label": "Khóa thanh tác vụ", "icon": "lock.png", "checkable": True},
    {"id": "taskbar_settings", "label": "Cài đặt thanh tác vụ", "icon": "settings.png"}
]

# ========== MESSAGES - Thông báo ==========
MESSAGES = {
    "confirm_delete": "Bạn có chắc chắn muốn xóa '{name}'?",
    "confirm_close_all": "Bạn có muốn đóng tất cả các cửa sổ?",
    "session_timeout_warning": "Phiên làm việc sẽ hết hạn sau {minutes} phút",
    "app_not_found": "Không tìm thấy ứng dụng: {app}",
    "permission_denied": "Bạn không có quyền thực hiện thao tác này",
    "save_layout": "Lưu bố cục hiện tại?",
    "restore_default": "Khôi phục cài đặt mặc định?",
    "update_available": "Có bản cập nhật mới",
    "loading": "Đang tải...",
    "saving": "Đang lưu...",
    "search_no_results": "Không tìm thấy kết quả cho '{query}'"
}

# ========== SOUND EFFECTS - Âm thanh ==========
SOUNDS = {
    "startup": "startup.wav",
    "shutdown": "shutdown.wav",
    "login": "login.wav",
    "logout": "logout.wav",
    "notification": "notification.wav",
    "error": "error.wav",
    "warning": "warning.wav",
    "success": "success.wav",
    "click": "click.wav",
    "hover": "hover.wav",
    "minimize": "minimize.wav",
    "maximize": "maximize.wav",
    "close": "close.wav"
}

# ========== LOGGING - Ghi log ==========
LOG_LEVEL = "INFO"
LOG_FILE = "dashboard.log"
LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"