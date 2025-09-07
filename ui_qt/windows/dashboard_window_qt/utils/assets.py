# ui_qt/windows/dashboard_window_qt/utils/assets.py
"""
Module quản lý assets (icons, images, resources) cho Dashboard Desktop-Style
Bao gồm: Load, cache, resize icons và images
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Tuple, Union, Any
from functools import lru_cache
import logging

from PySide6.QtCore import QSize, Qt, QFile, QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QImage, QLinearGradient, QBrush
from PySide6.QtSvg import QSvgRenderer

# Import constants
from .constants import (
    ICONS_DIR,
    WALLPAPERS_DIR,
    DEFAULT_ICON_SIZE,
    ICON_SIZE_SMALL,
    ICON_SIZE_MEDIUM,
    ICON_SIZE_LARGE,
    ICON_SIZE_EXTRA_LARGE,
    SUPPORTED_IMAGE_FORMATS
)

# Thiết lập logger
logger = logging.getLogger(__name__)


# ========== ASSET MANAGER CLASS ==========

class AssetsManager:
    """
    Quản lý tập trung tất cả assets của Dashboard
    Singleton pattern để đảm bảo chỉ có 1 instance
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._icon_cache: Dict[str, QIcon] = {}
        self._pixmap_cache: Dict[str, QPixmap] = {}
        self._svg_cache: Dict[str, QSvgRenderer] = {}
        self._wallpaper_cache: Dict[str, QPixmap] = {}

        # Đường dẫn assets
        self.base_dir = Path(__file__).parent.parent
        self.assets_dir = self.base_dir / "assets"
        self.icons_dir = self.assets_dir / "icons"
        self.app_icons_dir = self.icons_dir / "app"  # ← QUAN TRỌNG
        self.system_icons_dir = self.icons_dir / "system"
        self.categories_icons_dir = self.icons_dir / "categories"
        self.wallpapers_dir = self.assets_dir / "wallpapers"
        self.themes_dir = self.assets_dir / "themes"
        self.sounds_dir = self.assets_dir / "sounds"
        # Tạo thư mục nếu chưa tồn tại
        self._create_directories()

        # Load icon mappings
        self._load_icon_mappings()

    def _create_directories(self):
        """Tạo các thư mục nếu chưa tồn tại"""
        dirs_to_create = [
            self.assets_dir,
            self.icons_dir,
            self.app_icons_dir,
            self.system_icons_dir,
            self.categories_icons_dir,
            self.wallpapers_dir,
            self.themes_dir,
            self.sounds_dir
        ]

        for dir_path in dirs_to_create:
            dir_path.mkdir(parents=True, exist_ok=True)

    def _load_icon_mappings(self):
        """Load mapping giữa tên icon và file thực tế"""
        self.icon_map = {
            # === Học tập ===
            "students": "students.png",
            "groups": "groups.png",
            "attendance": "attendance.png",
            "calendar": "calendar.png",
            "assignment": "assignment.png",
            "submit": "submit.png",
            "submitted": "submitted.png",
            "question_bank": "question_bank.png",
            "suggest": "suggest.png",
            "test": "test.png",
            "package": "package.png",

            # === Báo cáo ===
            "progress": "progress.png",
            "skill": "skill.png",
            "rating": "rating.png",
            "group_suggest": "group_suggest.png",
            "salary": "salary.png",

            # === System icons ===
            "app": "app.png",
            "close": "close.png",
            "minimize": "minimize.png",
            "maximize": "maximize.png",
            "restore": "restore.png",
            "settings": "settings.png",
            "search": "search.png",
            "home": "home.png",
            "back": "back.png",
            "forward": "forward.png",
            "refresh": "refresh.png",
            "save": "save.png",
            "open": "open.png",
            "new": "new.png",
            "delete": "delete.png",
            "edit": "edit.png",
            "copy": "copy.png",
            "paste": "paste.png",
            "cut": "cut.png",
            "undo": "undo.png",
            "redo": "redo.png",

            # === File type icons ===
            "file": "file.png",
            "folder": "folder.png",
            "pdf": "pdf.png",
            "doc": "doc.png",
            "xls": "xls.png",
            "ppt": "ppt.png",
            "txt": "txt.png",
            "image": "image.png",
            "video": "video.png",
            "audio": "audio.png",
            "zip": "zip.png",
            "exe": "exe.png",
            "python": "python.png",

            # === Status icons ===
            "success": "success.png",
            "error": "error.png",
            "warning": "warning.png",
            "info": "info.png",
            "question": "question.png",

            # === UI elements ===
            "menu": "menu.png",
            "more": "more.png",
            "dropdown": "dropdown.png",
            "checkbox": "checkbox.png",
            "radio": "radio.png",
            "star": "star.png",
            "heart": "heart.png",
            "bell": "bell.png",
            "lock": "lock.png",
            "unlock": "unlock.png",
            "user": "user.png",
            "users": "users.png",
            "email": "email.png",
            "phone": "phone.png",
            "location": "location.png",
            "time": "time.png",
            "date": "date.png",

            # === Default/Fallback ===
            "default": "default.png",
            "unknown": "unknown.png"
        }

    def clear_cache(self):
        """Xóa toàn bộ cache"""
        self._icon_cache.clear()
        self._pixmap_cache.clear()
        self._svg_cache.clear()
        self._wallpaper_cache.clear()
        logger.info("Đã xóa cache assets")


# ========== ICON UTILITIES ==========

@lru_cache(maxsize=128)
# Trong utils/assets.py

def load_icon(name: str, size: Optional[QSize] = None) -> QIcon:
    """Load icon từ tên"""
    manager = AssetsManager()

    # Kiểm tra trong các thư mục theo thứ tự ưu tiên
    search_dirs = [
        manager.app_icons_dir,  # 1. Tìm trong app icons
        manager.system_icons_dir,  # 2. Tìm trong system icons
        manager.categories_icons_dir,  # 3. Tìm trong categories
        manager.icons_dir  # 4. Tìm trong icons chung
    ]

    icon_path = None

    # Tìm file icon
    for dir_path in search_dirs:
        # Thử với các extension
        for ext in ['.png', '.svg', '.ico', '.jpg']:
            test_path = dir_path / f"{name}{ext}"
            if test_path.exists():
                icon_path = test_path
                break
        if icon_path:
            break

    # Nếu không tìm thấy, dùng default
    if not icon_path:
        default_path = manager.app_icons_dir / "default.png"
        if default_path.exists():
            icon_path = default_path
        else:
            # Tạo icon placeholder
            return create_placeholder_icon(name, size or QSize(48, 48))

    # Load icon
    pixmap = QPixmap(str(icon_path))
    if size:
        pixmap = pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    return QIcon(pixmap)


def load_svg_pixmap(
        svg_path: str,
        size: QSize,
        color: Optional[QColor] = None
) -> QPixmap:
    """
    Load SVG và convert thành QPixmap

    Args:
        svg_path: Đường dẫn file SVG
        size: Kích thước output
        color: Màu fill (optional)

    Returns:
        QPixmap object
    """
    try:
        # Đọc và modify SVG nếu cần đổi màu
        if color:
            with open(svg_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()

            # Replace fill color
            color_hex = color.name()
            import re
            svg_content = re.sub(
                r'fill="[^"]*"',
                f'fill="{color_hex}"',
                svg_content
            )
            svg_content = re.sub(
                r'stroke="[^"]*"',
                f'stroke="{color_hex}"',
                svg_content
            )

            # Load từ string
            renderer = QSvgRenderer(QByteArray(svg_content.encode()))
        else:
            renderer = QSvgRenderer(svg_path)

        # Render thành pixmap
        pixmap = QPixmap(size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        renderer.render(painter)
        painter.end()

        return pixmap

    except Exception as e:
        logger.error(f"Lỗi load SVG: {e}")
        return QPixmap(size)


def apply_color_to_pixmap(pixmap: QPixmap, color: QColor) -> QPixmap:
    """
    Apply màu cho pixmap (dùng cho monochrome icons)

    Args:
        pixmap: QPixmap gốc
        color: Màu cần apply

    Returns:
        QPixmap đã tô màu
    """
    colored_pixmap = QPixmap(pixmap.size())
    colored_pixmap.fill(Qt.transparent)

    painter = QPainter(colored_pixmap)
    painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
    painter.drawPixmap(0, 0, pixmap)

    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(colored_pixmap.rect(), color)
    painter.end()

    return colored_pixmap


def create_placeholder_icon(text: str, size: QSize) -> QIcon:
    """
    Tạo placeholder icon với chữ cái đầu

    Args:
        text: Text để lấy chữ cái đầu
        size: Kích thước icon

    Returns:
        QIcon placeholder
    """
    pixmap = QPixmap(size)
    pixmap.fill(QColor(200, 200, 200))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Draw background circle
    painter.setBrush(QColor(100, 100, 100))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(pixmap.rect())

    # Draw text
    painter.setPen(Qt.white)
    font = QFont("Arial", size.height() // 3)
    font.setBold(True)
    painter.setFont(font)

    initial = text[0].upper() if text else "?"
    painter.drawText(pixmap.rect(), Qt.AlignCenter, initial)
    painter.end()

    return QIcon(pixmap)


def get_app_icon(app_id: str, size: QSize = DEFAULT_ICON_SIZE) -> QIcon:
    """
    Lấy icon cho app theo ID

    Args:
        app_id: ID của app
        size: Kích thước icon

    Returns:
        QIcon của app
    """
    # Mapping app_id to icon name
    app_icon_map = {
        "student_window": "students",
        "group_window": "groups",
        "package_window": "package",
        "attendance_report": "attendance",
        "main_window": "calendar",
        "assign_exercise": "assignment",
        "submit_exercise": "submit",
        "submitted_exercise": "submitted",
        "question_bank": "question_bank",
        "exercise_suggestion": "suggest",
        "create_test": "test",
        "exercise_tree": "folder",
        "progress_report": "progress",
        "skill_report": "skill",
        "skill_rating": "rating",
        "group_suggestion": "group_suggest",
        "salary_window": "salary"
    }

    icon_name = app_icon_map.get(app_id, "app")
    return load_icon(icon_name, size)


# ========== IMAGE UTILITIES ==========

@lru_cache(maxsize=32)
def load_image(
        path: str,
        size: Optional[QSize] = None,
        keep_aspect: bool = True
) -> QPixmap:
    """
    Load image từ file

    Args:
        path: Đường dẫn image
        size: Kích thước resize (optional)
        keep_aspect: Giữ tỷ lệ khi resize

    Returns:
        QPixmap object
    """
    manager = AssetsManager()

    # Check cache
    cache_key = f"img_{path}_{size}_{keep_aspect}"
    if cache_key in manager._pixmap_cache:
        return manager._pixmap_cache[cache_key]

    try:
        pixmap = QPixmap(path)

        if pixmap.isNull():
            logger.warning(f"Không thể load image: {path}")
            return QPixmap()

        # Resize nếu cần
        if size:
            if keep_aspect:
                pixmap = pixmap.scaled(
                    size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
            else:
                pixmap = pixmap.scaled(
                    size,
                    Qt.IgnoreAspectRatio,
                    Qt.SmoothTransformation
                )

        # Cache
        manager._pixmap_cache[cache_key] = pixmap
        return pixmap

    except Exception as e:
        logger.error(f"Lỗi load image: {e}")
        return QPixmap()


def load_wallpaper(
        name: str = "default",
        size: Optional[QSize] = None,
        **kwargs
) -> QPixmap:
    """
    Load wallpaper image

    Args:
        name: Tên wallpaper hoặc đường dẫn
        size: Kích thước screen (optional)
        **kwargs: Hỗ trợ keyword arguments khác

    Returns:
        QPixmap wallpaper
    """
    manager = AssetsManager()

    # Xử lý size từ kwargs nếu không được truyền trực tiếp
    if size is None and 'size' in kwargs:
        size = kwargs['size']

    # Check cache
    cache_key = f"wallpaper_{name}_{size}"
    if cache_key in manager._wallpaper_cache:
        return manager._wallpaper_cache[cache_key]

    try:
        # Xác định path
        if os.path.exists(name):
            wallpaper_path = Path(name)
        else:
            wallpaper_path = manager.wallpapers_dir / f"{name}.jpg"
            if not wallpaper_path.exists():
                # Thử các format khác
                for ext in SUPPORTED_IMAGE_FORMATS:
                    test_path = manager.wallpapers_dir / f"{name}{ext}"
                    if test_path.exists():
                        wallpaper_path = test_path
                        break
                else:
                    # Tạo default gradient wallpaper
                    default_size = size or QSize(1920, 1080)
                    return create_gradient_wallpaper(default_size)

        # Load wallpaper
        pixmap = QPixmap(str(wallpaper_path))

        # Kiểm tra pixmap có hợp lệ không
        if pixmap.isNull():
            logger.warning(f"Không thể load wallpaper: {wallpaper_path}")
            default_size = size or QSize(1920, 1080)
            return create_gradient_wallpaper(default_size)

        # Scale to screen size nếu được chỉ định
        if size and isinstance(size, QSize) and size.width() > 0 and size.height() > 0:
            pixmap = pixmap.scaled(
                size,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )

        # Cache pixmap
        manager._wallpaper_cache[cache_key] = pixmap
        return pixmap

    except Exception as e:
        logger.error(f"Lỗi load wallpaper: {e}")
        default_size = size or QSize(1920, 1080)
        return create_gradient_wallpaper(default_size)


def create_gradient_wallpaper(size: QSize) -> QPixmap:
    """Tạo gradient wallpaper mặc định"""
    from PySide6.QtGui import QLinearGradient, QBrush  # Thêm import

    pixmap = QPixmap(size)

    painter = QPainter(pixmap)

    # Tạo gradient object riêng (ĐÚNG)
    gradient = QLinearGradient(0, 0, size.width(), size.height())

    # Set màu cho gradient
    gradient.setColorAt(0.0, QColor(26, 42, 108))   # Dark blue
    gradient.setColorAt(0.5, QColor(178, 31, 102))  # Purple
    gradient.setColorAt(1.0, QColor(216, 162, 221)) # Light purple

    # Dùng QBrush để fill với gradient
    painter.fillRect(pixmap.rect(), QBrush(gradient))
    painter.end()

    return pixmap

def create_thumbnail(
        source: Union[str, QPixmap],
        size: QSize = QSize(200, 150)
) -> QPixmap:
    """
    Tạo thumbnail từ image

    Args:
        source: Path hoặc QPixmap gốc
        size: Kích thước thumbnail

    Returns:
        QPixmap thumbnail
    """
    try:
        if isinstance(source, str):
            pixmap = QPixmap(source)
        else:
            pixmap = source

        if pixmap.isNull():
            return QPixmap(size)

        # Create thumbnail với border
        thumb = QPixmap(size)
        thumb.fill(Qt.white)

        # Scale image
        scaled = pixmap.scaled(
            size - QSize(4, 4),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        # Center image
        painter = QPainter(thumb)
        x = (size.width() - scaled.width()) // 2
        y = (size.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)

        # Draw border
        painter.setPen(QColor(200, 200, 200))
        painter.drawRect(thumb.rect().adjusted(0, 0, -1, -1))
        painter.end()

        return thumb

    except Exception as e:
        logger.error(f"Lỗi create thumbnail: {e}")
        return QPixmap(size)


# ========== RESOURCE UTILITIES ==========

def get_resource_path(resource_type: str, name: str) -> Optional[Path]:
    """
    Lấy đường dẫn đến resource

    Args:
        resource_type: "icon", "wallpaper", "theme", "sound"
        name: Tên resource

    Returns:
        Path object hoặc None
    """
    manager = AssetsManager()

    type_map = {
        "icon": manager.icons_dir,
        "wallpaper": manager.wallpapers_dir,
        "theme": manager.themes_dir,
        "sound": manager.sounds_dir
    }

    base_dir = type_map.get(resource_type)
    if not base_dir:
        return None

    # Tìm file với các extension khác nhau
    for ext in ['', '.png', '.jpg', '.svg', '.ico', '.wav', '.mp3', '.json']:
        path = base_dir / f"{name}{ext}"
        if path.exists():
            return path

    return None


def cache_image(key: str, image: Union[QPixmap, QIcon]) -> None:
    """
    Lưu image vào cache

    Args:
        key: Cache key
        image: QPixmap hoặc QIcon
    """
    manager = AssetsManager()

    if isinstance(image, QPixmap):
        manager._pixmap_cache[key] = image
    elif isinstance(image, QIcon):
        manager._icon_cache[key] = image


def get_cached_image(key: str) -> Optional[Union[QPixmap, QIcon]]:
    """
    Lấy image từ cache

    Args:
        key: Cache key

    Returns:
        Cached image hoặc None
    """
    manager = AssetsManager()

    if key in manager._pixmap_cache:
        return manager._pixmap_cache[key]
    elif key in manager._icon_cache:
        return manager._icon_cache[key]

    return None


def preload_common_assets():
    """
    Preload các assets thường dùng vào cache
    """
    common_icons = [
        "app", "close", "minimize", "maximize",
        "settings", "search", "folder", "file",
        "students", "groups", "attendance", "calendar"
    ]

    for icon_name in common_icons:
        load_icon(icon_name)

    logger.info(f"Đã preload {len(common_icons)} icons vào cache")


# ========== ICON SIZE UTILITIES ==========

def get_icon_size_by_name(size_name: str) -> QSize:
    """
    Lấy QSize từ tên kích thước

    Args:
        size_name: "small", "medium", "large", "extra_large"

    Returns:
        QSize object
    """
    size_map = {
        "small": ICON_SIZE_SMALL,
        "medium": ICON_SIZE_MEDIUM,
        "large": ICON_SIZE_LARGE,
        "extra_large": ICON_SIZE_EXTRA_LARGE,
        "default": DEFAULT_ICON_SIZE
    }

    return size_map.get(size_name, DEFAULT_ICON_SIZE)


def resize_icon(icon: QIcon, size: QSize) -> QIcon:
    """
    Resize icon về kích thước mới

    Args:
        icon: QIcon gốc
        size: Kích thước mới

    Returns:
        QIcon đã resize
    """
    pixmap = icon.pixmap(size)
    return QIcon(pixmap)


# ========== EXPORT UTILITIES ==========

def export_icon_to_file(
        icon: QIcon,
        file_path: str,
        size: QSize = DEFAULT_ICON_SIZE
) -> bool:
    """
    Export icon ra file

    Args:
        icon: QIcon cần export
        file_path: Đường dẫn output
        size: Kích thước export

    Returns:
        True nếu thành công
    """
    try:
        pixmap = icon.pixmap(size)
        return pixmap.save(file_path)
    except Exception as e:
        logger.error(f"Lỗi export icon: {e}")
        return False
def get_user_avatar() -> QPixmap:
    """Load user avatar image"""
    # Default avatar path
    avatar_path = Path.home() / "Pictures" / "avatar.png"
    if avatar_path.exists():
        return QPixmap(str(avatar_path))
    else:
        # Return default avatar
        return QPixmap()  # Empty pixmap

# ========== INITIALIZATION ==========

# Tạo instance singleton khi import module
_assets_manager = AssetsManager()

# Preload common assets khi khởi động
# preload_common_assets()  # Uncomment nếu muốn preload

logger.info("Assets manager đã khởi tạo")