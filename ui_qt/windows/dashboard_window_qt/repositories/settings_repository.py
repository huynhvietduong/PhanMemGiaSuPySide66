# ui_qt/windows/dashboard_window_qt/repositories/settings_repository.py
"""
Repository layer để quản lý settings và preferences của Dashboard
Bao gồm: User preferences, UI settings, theme, layout state
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
import logging

# Setup logger
logger = logging.getLogger(__name__)


# ========== ENUMS & CONSTANTS ==========

class ThemeMode(Enum):
    """Chế độ theme"""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"  # Theo hệ thống
    CUSTOM = "custom"


class Language(Enum):
    """Ngôn ngữ"""
    VIETNAMESE = "vi_VN"
    ENGLISH = "en_US"


class IconSize(Enum):
    """Kích thước icon"""
    SMALL = "small"  # 32x32
    MEDIUM = "medium"  # 48x48
    LARGE = "large"  # 64x64
    EXTRA_LARGE = "xlarge"  # 96x96


class ViewMode(Enum):
    """Chế độ hiển thị"""
    GRID = "grid"  # Dạng lưới
    LIST = "list"  # Dạng danh sách
    TILES = "tiles"  # Dạng tiles


class StartupMode(Enum):
    """Chế độ khởi động"""
    NORMAL = "normal"
    MAXIMIZED = "maximized"
    FULLSCREEN = "fullscreen"
    LAST_STATE = "last_state"


# Default values
DEFAULT_SETTINGS = {
    "version": "1.0.0",
    "theme": ThemeMode.LIGHT.value,
    "language": Language.VIETNAMESE.value,
    "icon_size": IconSize.LARGE.value,
    "view_mode": ViewMode.GRID.value,
    "startup_mode": StartupMode.MAXIMIZED.value,
    "auto_save": True,
    "auto_save_interval": 60,  # seconds
    "show_tooltips": True,
    "enable_animations": True,
    "enable_sounds": True,
    "confirm_exit": True
}


# ========== DATA MODELS ==========

@dataclass
class GeneralSettings:
    """Cài đặt chung"""
    language: str = Language.VIETNAMESE.value
    startup_mode: str = StartupMode.MAXIMIZED.value
    auto_save: bool = True
    auto_save_interval: int = 60  # seconds
    confirm_exit: bool = True
    check_updates: bool = True
    show_splash: bool = True
    recent_files_limit: int = 10
    session_timeout: int = 1800  # 30 minutes
    enable_logging: bool = True
    log_level: str = "INFO"
    """Cài đặt desktop"""
    wallpaper_path: str = "default"
    wallpaper_mode: str = "fill"  # fill, fit, stretch, tile, center
    show_desktop_icons: bool = True
    show_system_icons: bool = True  # Computer, Recycle Bin, etc.
    align_icons_to_grid: bool = True
    auto_arrange_icons: bool = False
    icon_view_mode: str = ViewMode.GRID.value
    icon_size: str = IconSize.LARGE.value
    show_icon_labels: bool = True
    desktop_color: str = "#1E1E1E"

    # THÊM field mới để lưu vị trí icons
    icon_positions: Dict[str, Tuple[int, int]] = field(default_factory=dict)

@dataclass
class AppearanceSettings:
    """Cài đặt giao diện"""
    theme: str = ThemeMode.LIGHT.value
    accent_color: str = "#0078D4"  # Windows blue
    font_family: str = "Segoe UI"
    font_size: int = 10
    icon_size: str = IconSize.LARGE.value
    view_mode: str = ViewMode.GRID.value
    show_grid_lines: bool = False
    grid_snap: bool = True
    grid_size: int = 100
    transparency: float = 0.95
    blur_background: bool = True
    enable_animations: bool = True
    animation_speed: str = "normal"  # slow, normal, fast


@dataclass
class DesktopSettings:
    """Cài đặt desktop"""
    wallpaper_path: str = "default"
    wallpaper_mode: str = "fill"  # fill, fit, stretch, tile, center
    wallpaper_slideshow: bool = False
    slideshow_interval: int = 300  # 5 minutes
    slideshow_folder: str = ""
    show_desktop_icons: bool = True
    icon_spacing: int = 75
    icon_text_color: str = "#FFFFFF"
    icon_text_shadow: bool = True
    auto_arrange_icons: bool = False
    align_icons_to_grid: bool = True
    show_widgets: bool = True
    widgets_locked: bool = False


@dataclass
class TaskbarSettings:
    """Cài đặt taskbar"""
    position: str = "bottom"  # top, bottom, left, right
    height: int = 45
    auto_hide: bool = False
    always_on_top: bool = True
    show_clock: bool = True
    show_date: bool = True
    clock_format: str = "24h"  # 12h, 24h
    show_search: bool = True
    show_start_button: bool = True
    show_task_view: bool = True
    show_system_tray: bool = True
    combine_buttons: str = "always"  # never, when_full, always
    show_labels: bool = True
    show_preview: bool = True
    preview_delay: int = 500  # ms


@dataclass
class StartMenuSettings:
    """Cài đặt Start Menu"""
    width: int = 450
    height: int = 600
    show_recent_apps: bool = True
    recent_apps_limit: int = 5
    show_pinned_apps: bool = True
    show_all_apps: bool = True
    show_power_buttons: bool = True
    show_user_info: bool = True
    tile_size: str = "medium"  # small, medium, large
    groups_expanded: bool = True
    show_suggestions: bool = False
    transparency: float = 0.9


@dataclass
class NotificationSettings:
    """Cài đặt thông báo"""
    enabled: bool = True
    position: str = "bottom-right"  # top-left, top-right, bottom-left, bottom-right
    duration: int = 5000  # ms
    max_visible: int = 3
    show_app_icon: bool = True
    play_sound: bool = True
    sound_volume: int = 50  # 0-100
    do_not_disturb: bool = False
    dnd_start: str = "22:00"
    dnd_end: str = "07:00"
    priority_only: bool = False


@dataclass
class ShortcutSettings:
    """Cài đặt phím tắt"""
    shortcuts: Dict[str, str] = field(default_factory=lambda: {
        "show_desktop": "Meta+D",
        "show_start_menu": "Meta",
        "lock_screen": "Meta+L",
        "task_view": "Meta+Tab",
        "switch_apps": "Alt+Tab",
        "search": "Meta+S",
        "settings": "Meta+I",
        "file_explorer": "Meta+E",
        "close_app": "Alt+F4",
        "minimize_all": "Meta+M",
        "refresh": "F5"
    })
    custom_shortcuts: Dict[str, str] = field(default_factory=dict)
    enable_global: bool = True


@dataclass
class PrivacySettings:
    """Cài đặt riêng tư"""
    save_recent_files: bool = True
    save_recent_apps: bool = True
    save_search_history: bool = True
    clear_on_exit: bool = False
    telemetry_enabled: bool = False
    error_reporting: bool = True
    anonymous_usage: bool = False


@dataclass
class PerformanceSettings:
    """Cài đặt hiệu năng"""
    hardware_acceleration: bool = True
    reduce_animations: bool = False
    disable_transparency: bool = False
    low_power_mode: bool = False
    max_fps: int = 60
    cache_size: int = 100  # MB
    preload_apps: bool = True
    lazy_loading: bool = True

@dataclass
class DashboardSettings:
    """Tổng hợp tất cả settings"""
    version: str = "1.0.0"
    general: GeneralSettings = field(default_factory=GeneralSettings)
    appearance: AppearanceSettings = field(default_factory=AppearanceSettings)
    desktop: DesktopSettings = field(default_factory=DesktopSettings)
    taskbar: TaskbarSettings = field(default_factory=TaskbarSettings)
    start_menu: StartMenuSettings = field(default_factory=StartMenuSettings)
    notifications: NotificationSettings = field(default_factory=NotificationSettings)
    shortcuts: ShortcutSettings = field(default_factory=ShortcutSettings)
    privacy: PrivacySettings = field(default_factory=PrivacySettings)
    performance: PerformanceSettings = field(default_factory=PerformanceSettings)

    # Layout states
    window_state: Dict[str, Any] = field(default_factory=dict)
    desktop_icon_positions: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    widget_positions: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    recent_files: List[str] = field(default_factory=list)
    recent_apps: List[str] = field(default_factory=list)
    search_history: List[str] = field(default_factory=list)

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DashboardSettings':
        """Create from dictionary"""
        # Parse nested dataclasses
        if 'general' in data and isinstance(data['general'], dict):
            data['general'] = GeneralSettings(**data['general'])
        if 'appearance' in data and isinstance(data['appearance'], dict):
            data['appearance'] = AppearanceSettings(**data['appearance'])
        if 'desktop' in data and isinstance(data['desktop'], dict):
            data['desktop'] = DesktopSettings(**data['desktop'])
        if 'taskbar' in data and isinstance(data['taskbar'], dict):
            data['taskbar'] = TaskbarSettings(**data['taskbar'])
        if 'start_menu' in data and isinstance(data['start_menu'], dict):
            data['start_menu'] = StartMenuSettings(**data['start_menu'])
        if 'notifications' in data and isinstance(data['notifications'], dict):
            data['notifications'] = NotificationSettings(**data['notifications'])
        if 'shortcuts' in data and isinstance(data['shortcuts'], dict):
            data['shortcuts'] = ShortcutSettings(**data['shortcuts'])
        if 'privacy' in data and isinstance(data['privacy'], dict):
            data['privacy'] = PrivacySettings(**data['privacy'])
        if 'performance' in data and isinstance(data['performance'], dict):
            data['performance'] = PerformanceSettings(**data['performance'])

        return cls(**data)


# ========== REPOSITORY CLASS ==========

class SettingsRepository:
    """
    Repository để quản lý settings của Dashboard
    Singleton pattern để đảm bảo consistency
    """

    _instance = None
    _settings: Optional[DashboardSettings] = None

    def __new__(cls, settings_path: str = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, settings_path: str = None):
        """
        Initialize repository

        Args:
            settings_path: Đường dẫn file settings
        """
        if self._initialized:
            return

        self._initialized = True

        # Settings file path
        if settings_path:
            self.settings_path = Path(settings_path)
        else:
            # Default path in user config directory
            self.settings_path = self._get_default_settings_path()

        # Ensure directory exists
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)

        # Load settings
        self.load_settings()

        # Setup auto-save timer if needed
        self._auto_save_timer = None
        if self._settings.general.auto_save:
            self._start_auto_save()

    def _get_default_settings_path(self) -> Path:
        """Get default settings path based on OS"""
        if os.name == 'nt':  # Windows
            config_dir = Path(os.environ.get('APPDATA', '')) / 'DashboardQt'
        else:  # Linux/Mac
            config_dir = Path.home() / '.config' / 'dashboard_qt'

        return config_dir / 'settings.json'

    def _start_auto_save(self):
        """Start auto-save timer"""
        from PySide6.QtCore import QTimer

        if self._auto_save_timer:
            self._auto_save_timer.stop()

        self._auto_save_timer = QTimer()
        self._auto_save_timer.timeout.connect(self.save_settings)
        self._auto_save_timer.start(self._settings.general.auto_save_interval * 1000)

    # ========== LOAD/SAVE OPERATIONS ==========

    def load_settings(self) -> DashboardSettings:
        """
        Load settings từ file

        Returns:
            DashboardSettings object
        """
        try:
            if self.settings_path.exists():
                data = json.loads(self.settings_path.read_text(encoding='utf-8'))
                self._settings = DashboardSettings.from_dict(data)

            else:
                # Create default settings
                self._settings = DashboardSettings()
                self.save_settings()

        except Exception as e:
            logger.error(f"Lỗi load settings: {e}")
            self._settings = DashboardSettings()

        return self._settings

    def save_settings(self) -> bool:
        """
        Save settings vào file

        Returns:
            True nếu thành công
        """
        try:
            if not self._settings:
                return False

            # Update timestamp
            self._settings.updated_at = datetime.now().isoformat()

            # Convert to dict and save
            data = self._settings.to_dict()
            self.settings_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )

            return True

        except Exception as e:
            logger.error(f"Lỗi save settings: {e}")
            return False

    def reset_to_default(self) -> DashboardSettings:
        """
        Reset về settings mặc định

        Returns:
            DashboardSettings mặc định
        """
        self._settings = DashboardSettings()
        self.save_settings()
        return self._settings

    # ========== GET METHODS ==========

    def get_settings(self) -> DashboardSettings:
        """Get toàn bộ settings"""
        if not self._settings:
            self.load_settings()
        return self._settings

    def get_general(self) -> GeneralSettings:
        """Get general settings"""
        return self.get_settings().general

    def get_appearance(self) -> AppearanceSettings:
        """Get appearance settings"""
        return self.get_settings().appearance

    def get_desktop(self) -> DesktopSettings:
        """Get desktop settings"""
        return self.get_settings().desktop

    def get_taskbar(self) -> TaskbarSettings:
        """Get taskbar settings"""
        return self.get_settings().taskbar

    def get_start_menu(self) -> StartMenuSettings:
        """Get start menu settings"""
        return self.get_settings().start_menu

    def get_notifications(self) -> NotificationSettings:
        """Get notification settings"""
        return self.get_settings().notifications

    def get_shortcuts(self) -> ShortcutSettings:
        """Get shortcut settings"""
        return self.get_settings().shortcuts

    def get_privacy(self) -> PrivacySettings:
        """Get privacy settings"""
        return self.get_settings().privacy

    def get_performance(self) -> PerformanceSettings:
        """Get performance settings"""
        return self.get_settings().performance

    # ========== SPECIFIC GETTERS ==========

    def get_theme(self) -> str:
        """Get current theme"""
        return self.get_appearance().theme

    def get_language(self) -> str:
        """Get current language"""
        return self.get_general().language

    def get_wallpaper(self) -> str:
        """Get wallpaper path"""
        return self.get_desktop().wallpaper_path

    def get_icon_size(self) -> str:
        """Get icon size"""
        return self.get_appearance().icon_size

    def get_font_settings(self) -> Dict[str, Any]:
        """Get font settings"""
        appearance = self.get_appearance()
        return {
            'family': appearance.font_family,
            'size': appearance.font_size
        }

    def get_window_state(self, window_id: str = "main") -> Optional[Dict[str, Any]]:
        """Get saved window state"""
        return self.get_settings().window_state.get(window_id)

    def get_desktop_icon_positions(self) -> Dict[str, Tuple[int, int]]:
        """Get saved desktop icon positions"""
        return self.get_settings().desktop_icon_positions

    def get_recent_files(self, limit: int = None) -> List[str]:
        """Get recent files list"""
        files = self.get_settings().recent_files
        if limit:
            return files[:limit]
        return files

    def get_recent_apps(self, limit: int = None) -> List[str]:
        """Get recent apps list"""
        apps = self.get_settings().recent_apps
        if limit:
            return apps[:limit]
        return apps

    # ========== SET METHODS ==========

    def set_theme(self, theme: str) -> bool:
        """Set theme"""
        try:
            self.get_appearance().theme = theme
            return self.save_settings()
        except Exception as e:
            logger.error(f"Lỗi set theme: {e}")
            return False

    def set_language(self, language: str) -> bool:
        """Set language"""
        try:
            self.get_general().language = language
            return self.save_settings()
        except Exception as e:
            logger.error(f"Lỗi set language: {e}")
            return False

    def set_wallpaper(self, path: str) -> bool:
        """Set wallpaper"""
        try:
            self.get_desktop().wallpaper_path = path
            return self.save_settings()
        except Exception as e:
            logger.error(f"Lỗi set wallpaper: {e}")
            return False

    def set_icon_size(self, size: str) -> bool:
        """Set icon size"""
        try:
            self.get_appearance().icon_size = size
            return self.save_settings()
        except Exception as e:
            logger.error(f"Lỗi set icon size: {e}")
            return False

    def set_font(self, family: str = None, size: int = None) -> bool:
        """Set font settings"""
        try:
            appearance = self.get_appearance()
            if family:
                appearance.font_family = family
            if size:
                appearance.font_size = size
            return self.save_settings()
        except Exception as e:
            logger.error(f"Lỗi set font: {e}")
            return False

    def save_window_state(self, window_id: str, state: Dict[str, Any]) -> bool:
        """Save window state"""
        try:
            self.get_settings().window_state[window_id] = state
            return self.save_settings()
        except Exception as e:
            logger.error(f"Lỗi save window state: {e}")
            return False

    # ========== DESKTOP ICON POSITIONS ==========
    def save_desktop_icon_position(self, icon_id: str, position):
        """
        Save vị trí của desktop icon

        Args:
            icon_id: ID của icon
            position: QPoint hoặc tuple (x, y)
        """
        try:
            # Convert QPoint to tuple if needed
            if hasattr(position, 'x') and hasattr(position, 'y'):
                # This is a QPoint
                position_tuple = (position.x(), position.y())
            elif isinstance(position, (list, tuple)) and len(position) == 2:
                # Already a tuple/list
                position_tuple = tuple(position)
            else:
                logger.error(f"Invalid position type: {type(position)}")
                return False

            # Save to desktop_icon_positions dict
            if not hasattr(self._settings.desktop, 'icon_positions'):
                self._settings.desktop.icon_positions = {}

            self._settings.desktop.icon_positions[icon_id] = position_tuple

            # Trigger save
            return self.save_settings()

        except Exception as e:
            logger.error(f"Error saving icon position: {e}")
            return False

    def get_desktop_icon_positions(self) -> Dict[str, Tuple[int, int]]:
        """
        Get all saved desktop icon positions

        Returns:
            Dict of {icon_id: (x, y)}
        """
        if hasattr(self._settings.desktop, 'icon_positions'):
            return self._settings.desktop.icon_positions
        return {}
    def add_recent_file(self, file_path: str) -> bool:
        """Add to recent files"""
        try:
            recent = self.get_settings().recent_files
            # Remove if exists
            if file_path in recent:
                recent.remove(file_path)
            # Add to beginning
            recent.insert(0, file_path)
            # Limit size
            limit = self.get_general().recent_files_limit
            self.get_settings().recent_files = recent[:limit]
            return self.save_settings()
        except Exception as e:
            logger.error(f"Lỗi add recent file: {e}")
            return False

    def add_recent_app(self, app_id: str) -> bool:
        """Add to recent apps"""
        try:
            recent = self.get_settings().recent_apps
            # Remove if exists
            if app_id in recent:
                recent.remove(app_id)
            # Add to beginning
            recent.insert(0, app_id)
            # Limit size
            limit = self.get_start_menu().recent_apps_limit
            self.get_settings().recent_apps = recent[:limit]
            return self.save_settings()
        except Exception as e:
            logger.error(f"Lỗi add recent app: {e}")
            return False

    # ========== UPDATE METHODS ==========

    def update_general(self, **kwargs) -> bool:
        """Update general settings"""
        try:
            general = self.get_general()
            for key, value in kwargs.items():
                if hasattr(general, key):
                    setattr(general, key, value)
            return self.save_settings()
        except Exception as e:
            logger.error(f"Lỗi update general: {e}")
            return False

    def update_appearance(self, **kwargs) -> bool:
        """Update appearance settings"""
        try:
            appearance = self.get_appearance()
            for key, value in kwargs.items():
                if hasattr(appearance, key):
                    setattr(appearance, key, value)
            return self.save_settings()
        except Exception as e:
            logger.error(f"Lỗi update appearance: {e}")
            return False

    def update_desktop(self, **kwargs) -> bool:
        """Update desktop settings"""
        try:
            desktop = self.get_desktop()
            for key, value in kwargs.items():
                if hasattr(desktop, key):
                    setattr(desktop, key, value)
            return self.save_settings()
        except Exception as e:
            logger.error(f"Lỗi update desktop: {e}")
            return False

    def update_taskbar(self, **kwargs) -> bool:
        """Update taskbar settings"""
        try:
            taskbar = self.get_taskbar()
            for key, value in kwargs.items():
                if hasattr(taskbar, key):
                    setattr(taskbar, key, value)
            return self.save_settings()
        except Exception as e:
            logger.error(f"Lỗi update taskbar: {e}")
            return False

    # ========== CLEAR METHODS ==========

    def clear_recent_files(self) -> bool:
        """Clear recent files list"""
        try:
            self.get_settings().recent_files = []
            return self.save_settings()
        except Exception as e:
            logger.error(f"Lỗi clear recent files: {e}")
            return False

    def clear_recent_apps(self) -> bool:
        """Clear recent apps list"""
        try:
            self.get_settings().recent_apps = []
            return self.save_settings()
        except Exception as e:
            logger.error(f"Lỗi clear recent apps: {e}")
            return False

    def clear_search_history(self) -> bool:
        """Clear search history"""
        try:
            self.get_settings().search_history = []
            return self.save_settings()
        except Exception as e:
            logger.error(f"Lỗi clear search history: {e}")
            return False

    def clear_all_history(self) -> bool:
        """Clear all history and recent items"""
        try:
            settings = self.get_settings()
            settings.recent_files = []
            settings.recent_apps = []
            settings.search_history = []
            return self.save_settings()
        except Exception as e:
            logger.error(f"Lỗi clear all history: {e}")
            return False

    # ========== IMPORT/EXPORT ==========

    def export_settings(self, file_path: str) -> bool:
        """
        Export settings to file

        Args:
            file_path: Đường dẫn file output

        Returns:
            True nếu thành công
        """
        try:
            data = self.get_settings().to_dict()
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Lỗi export settings: {e}")
            return False

    def import_settings(self, file_path: str) -> bool:
        """
        Import settings from file

        Args:
            file_path: Đường dẫn file input

        Returns:
            True nếu thành công
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self._settings = DashboardSettings.from_dict(data)
            self.save_settings()

            # Restart auto-save if needed
            if self._settings.general.auto_save:
                self._start_auto_save()

            return True

        except Exception as e:
            logger.error(f"Lỗi import settings: {e}")
            return False

    # ========== VALIDATION ==========

    def validate_settings(self) -> List[str]:
        """
        Validate current settings

        Returns:
            List các lỗi (empty nếu valid)
        """
        errors = []
        settings = self.get_settings()

        # Validate paths
        if settings.desktop.wallpaper_path != "default":
            if not Path(settings.desktop.wallpaper_path).exists():
                errors.append(f"Wallpaper không tồn tại: {settings.desktop.wallpaper_path}")

        # Validate ranges
        if not 0 <= settings.appearance.transparency <= 1:
            errors.append("Transparency phải trong khoảng 0-1")

        if not 0 <= settings.notifications.sound_volume <= 100:
            errors.append("Volume phải trong khoảng 0-100")

        if settings.taskbar.height < 30 or settings.taskbar.height > 100:
            errors.append("Taskbar height phải trong khoảng 30-100")

        return errors