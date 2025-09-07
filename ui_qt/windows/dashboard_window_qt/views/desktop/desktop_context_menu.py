# ui_qt/windows/dashboard_window_qt/views/desktop/desktop_context_menu.py
"""
Desktop Context Menu - Right-click menu cho desktop
Cung cấp các options như View, Sort, New, Refresh, Personalize
"""

import os
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
import logging

from PySide6.QtWidgets import (
    QMenu, QWidget, QMessageBox, QInputDialog,
    QFileDialog, QColorDialog, QWidgetAction,
    QSlider, QLabel, QHBoxLayout, QVBoxLayout,
    QButtonGroup, QRadioButton, QCheckBox
)
from PySide6.QtCore import (
    Qt, Signal, QObject, QPoint, QSize,
    QTimer, QSettings
)
from PySide6.QtGui import (
    QAction, QIcon, QKeySequence, QFont,
    QActionGroup, QPixmap, QColor
)

# Import utils
from ...utils.assets import load_icon
from ...utils.helpers import create_desktop_shortcut, open_file_explorer

# Logger
logger = logging.getLogger(__name__)


# ========== ENUMS ==========

class ViewMode(Enum):
    """Chế độ xem icons"""
    LARGE_ICONS = "large"
    MEDIUM_ICONS = "medium"
    SMALL_ICONS = "small"
    LIST = "list"
    DETAILS = "details"
    TILES = "tiles"


class SortBy(Enum):
    """Tiêu chí sắp xếp"""
    NAME = "name"
    SIZE = "size"
    TYPE = "type"
    DATE_MODIFIED = "date_modified"


class GroupBy(Enum):
    """Tiêu chí nhóm"""
    NONE = "none"
    TYPE = "type"
    DATE = "date"
    SIZE = "size"
    NAME = "name"


# ========== MAIN CONTEXT MENU ==========

class DesktopContextMenu(QMenu):
    """
    Context menu chính của desktop
    Hiển thị khi right-click trên vùng trống
    """

    # Signals
    view_changed = Signal(ViewMode)
    sort_changed = Signal(SortBy, bool)  # sort_by, ascending
    group_changed = Signal(GroupBy)

    refresh_requested = Signal()
    arrange_requested = Signal(str)  # arrange_mode
    align_requested = Signal()

    new_item_requested = Signal(str)  # item_type
    paste_requested = Signal()

    wallpaper_requested = Signal()
    personalize_requested = Signal()
    display_settings_requested = Signal()

    new_folder_requested = Signal()
    new_file_requested = Signal(str)  # file_type

    def __init__(self, parent: QWidget = None):
        """
        Initialize Desktop Context Menu

        Args:
            parent: Parent widget (desktop)
        """
        super().__init__(parent)

        # Settings
        self.settings = QSettings("TutorSoft", "Dashboard")

        # Current state
        self.current_view = ViewMode.LARGE_ICONS
        self.current_sort = SortBy.NAME
        self.sort_ascending = True
        self.current_group = GroupBy.NONE

        # Build menu
        self._build_menu()

        # Apply style
        self._apply_style()

        logger.debug("Desktop context menu created")

    def _build_menu(self):
        """Build menu structure"""
        # View submenu
        self._add_view_menu()

        # Sort submenu
        self._add_sort_menu()

        # Group by submenu (optional)
        # self._add_group_menu()

        # Separator
        self.addSeparator()

        # Refresh
        refresh_action = QAction(
            load_icon("refresh"),
            "Làm mới",
            self
        )
        refresh_action.setShortcut(QKeySequence.Refresh)
        refresh_action.triggered.connect(self.refresh_requested.emit)
        self.addAction(refresh_action)

        # Separator
        self.addSeparator()

        # New submenu
        self._add_new_menu()

        # Separator
        self.addSeparator()

        # Paste
        paste_action = QAction(
            load_icon("paste"),
            "Dán",
            self
        )
        paste_action.setShortcut(QKeySequence.Paste)
        paste_action.triggered.connect(self.paste_requested.emit)
        paste_action.setEnabled(self._has_clipboard_data())
        self.addAction(paste_action)

        # Paste shortcut
        paste_shortcut_action = QAction(
            load_icon("paste"),
            "Dán shortcut",
            self
        )
        paste_shortcut_action.triggered.connect(
            lambda: self.new_item_requested.emit("shortcut")
        )
        paste_shortcut_action.setEnabled(self._has_clipboard_data())
        self.addAction(paste_shortcut_action)

        # Separator
        self.addSeparator()

        # Screen resolution
        resolution_action = QAction(
            load_icon("display"),
            "Độ phân giải màn hình",
            self
        )
        resolution_action.triggered.connect(self.display_settings_requested.emit)
        self.addAction(resolution_action)

        # Personalize
        personalize_action = QAction(
            load_icon("personalize"),
            "Cá nhân hóa",
            self
        )
        personalize_action.triggered.connect(self.personalize_requested.emit)
        self.addAction(personalize_action)

    def _add_view_menu(self):
        """Add View submenu"""
        view_menu = QMenu("Xem", self)
        view_menu.setIcon(load_icon("view"))

        # View modes
        view_group = QActionGroup(self)

        # Large icons
        large_action = QAction(
            load_icon("large_icons"),
            "Biểu tượng lớn",
            self
        )
        large_action.setCheckable(True)
        large_action.setChecked(self.current_view == ViewMode.LARGE_ICONS)
        large_action.triggered.connect(
            lambda: self._change_view(ViewMode.LARGE_ICONS)
        )
        view_group.addAction(large_action)
        view_menu.addAction(large_action)

        # Medium icons
        medium_action = QAction(
            load_icon("medium_icons"),
            "Biểu tượng vừa",
            self
        )
        medium_action.setCheckable(True)
        medium_action.setChecked(self.current_view == ViewMode.MEDIUM_ICONS)
        medium_action.triggered.connect(
            lambda: self._change_view(ViewMode.MEDIUM_ICONS)
        )
        view_group.addAction(medium_action)
        view_menu.addAction(medium_action)

        # Small icons
        small_action = QAction(
            load_icon("small_icons"),
            "Biểu tượng nhỏ",
            self
        )
        small_action.setCheckable(True)
        small_action.setChecked(self.current_view == ViewMode.SMALL_ICONS)
        small_action.triggered.connect(
            lambda: self._change_view(ViewMode.SMALL_ICONS)
        )
        view_group.addAction(small_action)
        view_menu.addAction(small_action)

        view_menu.addSeparator()

        # Auto arrange
        auto_arrange_action = QAction(
            "Tự động sắp xếp biểu tượng",
            self
        )
        auto_arrange_action.setCheckable(True)
        auto_arrange_action.setChecked(
            self.settings.value("desktop/auto_arrange", False, bool)
        )
        auto_arrange_action.triggered.connect(self._toggle_auto_arrange)
        view_menu.addAction(auto_arrange_action)

        # Align to grid
        align_grid_action = QAction(
            "Căn chỉnh biểu tượng theo lưới",
            self
        )
        align_grid_action.triggered.connect(self.align_requested.emit)
        view_menu.addAction(align_grid_action)

        view_menu.addSeparator()

        # Show desktop icons
        show_icons_action = QAction(
            "Hiển thị biểu tượng desktop",
            self
        )
        show_icons_action.setCheckable(True)
        show_icons_action.setChecked(
            self.settings.value("desktop/show_icons", True, bool)
        )
        show_icons_action.triggered.connect(self._toggle_show_icons)
        view_menu.addAction(show_icons_action)

        # Show desktop widgets
        show_widgets_action = QAction(
            "Hiển thị desktop widgets",
            self
        )
        show_widgets_action.setCheckable(True)
        show_widgets_action.setChecked(
            self.settings.value("desktop/show_widgets", True, bool)
        )
        show_widgets_action.triggered.connect(self._toggle_show_widgets)
        view_menu.addAction(show_widgets_action)

        self.addMenu(view_menu)

    def _add_sort_menu(self):
        """Add Sort submenu"""
        sort_menu = QMenu("Sắp xếp theo", self)
        sort_menu.setIcon(load_icon("sort"))

        sort_group = QActionGroup(self)

        # Sort by name
        name_action = QAction(
            load_icon("sort_name"),
            "Tên",
            self
        )
        name_action.setCheckable(True)
        name_action.setChecked(self.current_sort == SortBy.NAME)
        name_action.triggered.connect(
            lambda: self._change_sort(SortBy.NAME)
        )
        sort_group.addAction(name_action)
        sort_menu.addAction(name_action)

        # Sort by size
        size_action = QAction(
            load_icon("sort_size"),
            "Kích thước",
            self
        )
        size_action.setCheckable(True)
        size_action.setChecked(self.current_sort == SortBy.SIZE)
        size_action.triggered.connect(
            lambda: self._change_sort(SortBy.SIZE)
        )
        sort_group.addAction(size_action)
        sort_menu.addAction(size_action)

        # Sort by type
        type_action = QAction(
            load_icon("sort_type"),
            "Loại",
            self
        )
        type_action.setCheckable(True)
        type_action.setChecked(self.current_sort == SortBy.TYPE)
        type_action.triggered.connect(
            lambda: self._change_sort(SortBy.TYPE)
        )
        sort_group.addAction(type_action)
        sort_menu.addAction(type_action)

        # Sort by date modified
        date_action = QAction(
            load_icon("sort_date"),
            "Ngày sửa đổi",
            self
        )
        date_action.setCheckable(True)
        date_action.setChecked(self.current_sort == SortBy.DATE_MODIFIED)
        date_action.triggered.connect(
            lambda: self._change_sort(SortBy.DATE_MODIFIED)
        )
        sort_group.addAction(date_action)
        sort_menu.addAction(date_action)

        sort_menu.addSeparator()

        # Ascending/Descending
        ascending_action = QAction(
            load_icon("sort_asc"),
            "Tăng dần",
            self
        )
        ascending_action.setCheckable(True)
        ascending_action.setChecked(self.sort_ascending)
        ascending_action.triggered.connect(self._toggle_sort_order)
        sort_menu.addAction(ascending_action)

        self.addMenu(sort_menu)

    def _add_new_menu(self):
        """Add New submenu"""
        new_menu = QMenu("Mới", self)
        new_menu.setIcon(load_icon("new"))

        # New folder
        folder_action = QAction(
            load_icon("folder"),
            "Thư mục",
            self
        )
        folder_action.setShortcut(QKeySequence("Ctrl+Shift+N"))
        folder_action.triggered.connect(self.new_folder_requested.emit)
        new_menu.addAction(folder_action)

        new_menu.addSeparator()

        # New shortcut
        shortcut_action = QAction(
            load_icon("shortcut"),
            "Lối tắt",
            self
        )
        shortcut_action.triggered.connect(
            lambda: self.new_item_requested.emit("shortcut")
        )
        new_menu.addAction(shortcut_action)

        new_menu.addSeparator()

        # Document types
        # Text document
        text_action = QAction(
            load_icon("txt"),
            "Tài liệu văn bản",
            self
        )
        text_action.triggered.connect(
            lambda: self.new_file_requested.emit("txt")
        )
        new_menu.addAction(text_action)

        # Word document
        word_action = QAction(
            load_icon("doc"),
            "Tài liệu Microsoft Word",
            self
        )
        word_action.triggered.connect(
            lambda: self.new_file_requested.emit("docx")
        )
        new_menu.addAction(word_action)

        # Excel workbook
        excel_action = QAction(
            load_icon("xls"),
            "Bảng tính Microsoft Excel",
            self
        )
        excel_action.triggered.connect(
            lambda: self.new_file_requested.emit("xlsx")
        )
        new_menu.addAction(excel_action)

        # PowerPoint presentation
        ppt_action = QAction(
            load_icon("ppt"),
            "Bản trình bày Microsoft PowerPoint",
            self
        )
        ppt_action.triggered.connect(
            lambda: self.new_file_requested.emit("pptx")
        )
        new_menu.addAction(ppt_action)

        self.addMenu(new_menu)

    def _apply_style(self):
        """Apply custom style to menu"""
        self.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #ccc;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px 6px 30px;
                border-radius: 2px;
            }
            QMenu::item:selected {
                background-color: #e3f2fd;
            }
            QMenu::item:disabled {
                color: #999;
            }
            QMenu::separator {
                height: 1px;
                background: #e0e0e0;
                margin: 4px 10px;
            }
            QMenu::icon {
                margin-left: 5px;
            }
        """)

    # ========== EVENT HANDLERS ==========

    def _change_view(self, view_mode: ViewMode):
        """Change view mode"""
        self.current_view = view_mode
        self.settings.setValue("desktop/view_mode", view_mode.value)
        self.view_changed.emit(view_mode)
        logger.info(f"View mode changed to: {view_mode.value}")

    def _change_sort(self, sort_by: SortBy):
        """Change sort criteria"""
        self.current_sort = sort_by
        self.settings.setValue("desktop/sort_by", sort_by.value)
        self.sort_changed.emit(sort_by, self.sort_ascending)
        logger.info(f"Sort changed to: {sort_by.value}")

    def _toggle_sort_order(self):
        """Toggle sort order"""
        self.sort_ascending = not self.sort_ascending
        self.settings.setValue("desktop/sort_ascending", self.sort_ascending)
        self.sort_changed.emit(self.current_sort, self.sort_ascending)
        logger.info(f"Sort order: {'ascending' if self.sort_ascending else 'descending'}")

    def _toggle_auto_arrange(self, checked: bool):
        """Toggle auto arrange"""
        self.settings.setValue("desktop/auto_arrange", checked)
        if checked:
            self.arrange_requested.emit("auto")
        logger.info(f"Auto arrange: {checked}")

    def _toggle_show_icons(self, checked: bool):
        """Toggle show desktop icons"""
        self.settings.setValue("desktop/show_icons", checked)
        # This would hide/show all desktop icons
        logger.info(f"Show icons: {checked}")

    def _toggle_show_widgets(self, checked: bool):
        """Toggle show desktop widgets"""
        self.settings.setValue("desktop/show_widgets", checked)
        # This would hide/show desktop widgets
        logger.info(f"Show widgets: {checked}")

    def _has_clipboard_data(self) -> bool:
        """Check if clipboard has data"""
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        return bool(clipboard.text() or clipboard.mimeData().hasUrls())


# ========== ICON CONTEXT MENU ==========

class IconContextMenu(QMenu):
    """
    Context menu cho desktop icons
    Hiển thị khi right-click trên icon
    """

    # Signals
    open_requested = Signal()
    open_with_requested = Signal()
    pin_to_taskbar_requested = Signal()

    rename_requested = Signal()
    delete_requested = Signal()

    cut_requested = Signal()
    copy_requested = Signal()

    create_shortcut_requested = Signal()
    properties_requested = Signal()

    def __init__(
            self,
            icon_type: str = "app",
            icon_name: str = "",
            parent: QWidget = None
    ):
        """
        Initialize Icon Context Menu

        Args:
            icon_type: Type of icon (app, file, folder, shortcut)
            icon_name: Name of icon
            parent: Parent widget
        """
        super().__init__(parent)

        self.icon_type = icon_type
        self.icon_name = icon_name

        # Build menu
        self._build_menu()

        # Apply style
        self._apply_style()

        logger.debug(f"Icon context menu created for: {icon_name}")

    def _build_menu(self):
        """Build menu structure based on icon type"""
        # Open
        open_action = QAction(
            load_icon("open"),
            "Mở",
            self
        )
        open_action.setFont(QFont("", -1, QFont.Bold))
        open_action.triggered.connect(self.open_requested.emit)
        self.addAction(open_action)

        # Open with (for files)
        if self.icon_type in ["file", "unknown"]:
            open_with_action = QAction(
                "Mở bằng...",
                self
            )
            open_with_action.triggered.connect(self.open_with_requested.emit)
            self.addAction(open_with_action)

        # Pin to taskbar (for apps)
        if self.icon_type == "app":
            pin_action = QAction(
                load_icon("pin"),
                "Ghim vào thanh tác vụ",
                self
            )
            pin_action.triggered.connect(self.pin_to_taskbar_requested.emit)
            self.addAction(pin_action)

        self.addSeparator()

        # Cut
        cut_action = QAction(
            load_icon("cut"),
            "Cắt",
            self
        )
        cut_action.setShortcut(QKeySequence.Cut)
        cut_action.triggered.connect(self.cut_requested.emit)
        self.addAction(cut_action)

        # Copy
        copy_action = QAction(
            load_icon("copy"),
            "Sao chép",
            self
        )
        copy_action.setShortcut(QKeySequence.Copy)
        copy_action.triggered.connect(self.copy_requested.emit)
        self.addAction(copy_action)

        self.addSeparator()

        # Create shortcut
        shortcut_action = QAction(
            load_icon("shortcut"),
            "Tạo lối tắt",
            self
        )
        shortcut_action.triggered.connect(self.create_shortcut_requested.emit)
        self.addAction(shortcut_action)

        # Delete
        delete_action = QAction(
            load_icon("delete"),
            "Xóa",
            self
        )
        delete_action.setShortcut(QKeySequence.Delete)
        delete_action.triggered.connect(self.delete_requested.emit)
        self.addAction(delete_action)

        # Rename
        rename_action = QAction(
            load_icon("rename"),
            "Đổi tên",
            self
        )
        rename_action.setShortcut(QKeySequence("F2"))
        rename_action.triggered.connect(self.rename_requested.emit)
        self.addAction(rename_action)

        self.addSeparator()

        # Properties
        properties_action = QAction(
            load_icon("properties"),
            "Thuộc tính",
            self
        )
        properties_action.setShortcut(QKeySequence("Alt+Return"))
        properties_action.triggered.connect(self.properties_requested.emit)
        self.addAction(properties_action)

    def _apply_style(self):
        """Apply custom style"""
        self.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #ccc;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px 6px 30px;
                border-radius: 2px;
            }
            QMenu::item:selected {
                background-color: #e3f2fd;
            }
            QMenu::separator {
                height: 1px;
                background: #e0e0e0;
                margin: 4px 10px;
            }
        """)


# ========== WALLPAPER CONTEXT MENU ==========

class WallpaperContextMenu(QMenu):
    """
    Quick wallpaper change menu
    Part of personalization
    """

    # Signals
    wallpaper_changed = Signal(str)  # wallpaper_path
    slideshow_toggled = Signal(bool)  # enabled

    def __init__(self, parent: QWidget = None):
        super().__init__("Hình nền", parent)

        self.setIcon(load_icon("wallpaper"))

        # Recent wallpapers
        self._add_recent_wallpapers()

        self.addSeparator()

        # Browse
        browse_action = QAction(
            load_icon("folder"),
            "Duyệt...",
            self
        )
        browse_action.triggered.connect(self._browse_wallpaper)
        self.addAction(browse_action)

        # Slideshow
        slideshow_action = QAction(
            load_icon("slideshow"),
            "Trình chiếu",
            self
        )
        slideshow_action.setCheckable(True)
        slideshow_action.triggered.connect(
            lambda checked: self.slideshow_toggled.emit(checked)
        )
        self.addAction(slideshow_action)

    def _add_recent_wallpapers(self):
        """Add recent wallpapers to menu"""
        settings = QSettings("TutorSoft", "Dashboard")
        recent = settings.value("wallpaper/recent", [], list)

        for path in recent[:5]:  # Show last 5
            if os.path.exists(path):
                # Create action with thumbnail
                action = QAction(Path(path).name, self)

                # Load thumbnail
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    icon = QIcon(pixmap.scaled(
                        64, 64,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    ))
                    action.setIcon(icon)

                action.triggered.connect(
                    lambda checked, p=path: self.wallpaper_changed.emit(p)
                )
                self.addAction(action)

    def _browse_wallpaper(self):
        """Browse for wallpaper"""
        file_path, _ = QFileDialog.getOpenFileName(
            self.parentWidget(),
            "Chọn hình nền",
            str(Path.home() / "Pictures"),
            "Images (*.jpg *.jpeg *.png *.bmp *.gif)"
        )

        if file_path:
            self.wallpaper_changed.emit(file_path)


# ========== ARRANGE MENU ==========

class ArrangeMenu(QMenu):
    """
    Submenu for arranging icons
    """

    # Signals
    arrange_by_requested = Signal(str)  # arrange_mode

    def __init__(self, parent: QWidget = None):
        super().__init__("Sắp xếp", parent)

        self.setIcon(load_icon("arrange"))

        # Grid
        grid_action = QAction(
            load_icon("grid"),
            "Theo lưới",
            self
        )
        grid_action.triggered.connect(
            lambda: self.arrange_by_requested.emit("grid")
        )
        self.addAction(grid_action)

        # Auto arrange
        auto_action = QAction(
            load_icon("auto"),
            "Tự động",
            self
        )
        auto_action.triggered.connect(
            lambda: self.arrange_by_requested.emit("auto")
        )
        self.addAction(auto_action)

        # By name
        name_action = QAction(
            "Theo tên",
            self
        )
        name_action.triggered.connect(
            lambda: self.arrange_by_requested.emit("name")
        )
        self.addAction(name_action)

        # By type
        type_action = QAction(
            "Theo loại",
            self
        )
        type_action.triggered.connect(
            lambda: self.arrange_by_requested.emit("type")
        )
        self.addAction(type_action)

        # By date
        date_action = QAction(
            "Theo ngày",
            self
        )
        date_action.triggered.connect(
            lambda: self.arrange_by_requested.emit("date")
        )
        self.addAction(date_action)


# ========== TASKBAR CONTEXT MENU ==========

class TaskbarContextMenu(QMenu):
    """
    Context menu for taskbar
    """

    # Signals
    toolbars_toggled = Signal(str, bool)  # toolbar_name, visible
    taskbar_locked = Signal(bool)
    taskbar_settings_requested = Signal()
    task_manager_requested = Signal()

    cascade_windows_requested = Signal()
    tile_horizontal_requested = Signal()
    tile_vertical_requested = Signal()
    minimize_all_requested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        # Toolbars submenu
        toolbars_menu = QMenu("Thanh công cụ", self)

        # Search
        search_action = QAction("Tìm kiếm", self)
        search_action.setCheckable(True)
        search_action.setChecked(True)
        search_action.triggered.connect(
            lambda checked: self.toolbars_toggled.emit("search", checked)
        )
        toolbars_menu.addAction(search_action)

        # Task view button
        task_view_action = QAction("Nút xem tác vụ", self)
        task_view_action.setCheckable(True)
        task_view_action.setChecked(True)
        task_view_action.triggered.connect(
            lambda checked: self.toolbars_toggled.emit("task_view", checked)
        )
        toolbars_menu.addAction(task_view_action)

        # Widgets
        widgets_action = QAction("Widgets", self)
        widgets_action.setCheckable(True)
        widgets_action.triggered.connect(
            lambda checked: self.toolbars_toggled.emit("widgets", checked)
        )
        toolbars_menu.addAction(widgets_action)

        self.addMenu(toolbars_menu)

        self.addSeparator()

        # Window arrangement
        cascade_action = QAction(
            load_icon("cascade"),
            "Xếp chồng cửa sổ",
            self
        )
        cascade_action.triggered.connect(self.cascade_windows_requested.emit)
        self.addAction(cascade_action)

        tile_h_action = QAction(
            load_icon("tile_horizontal"),
            "Xếp ngang",
            self
        )
        tile_h_action.triggered.connect(self.tile_horizontal_requested.emit)
        self.addAction(tile_h_action)

        tile_v_action = QAction(
            load_icon("tile_vertical"),
            "Xếp dọc",
            self
        )
        tile_v_action.triggered.connect(self.tile_vertical_requested.emit)
        self.addAction(tile_v_action)

        minimize_action = QAction(
            load_icon("minimize_all"),
            "Thu nhỏ tất cả",
            self
        )
        minimize_action.triggered.connect(self.minimize_all_requested.emit)
        self.addAction(minimize_action)

        self.addSeparator()

        # Task manager
        task_mgr_action = QAction(
            load_icon("task_manager"),
            "Trình quản lý tác vụ",
            self
        )
        task_mgr_action.setShortcut(QKeySequence("Ctrl+Shift+Esc"))
        task_mgr_action.triggered.connect(self.task_manager_requested.emit)
        self.addAction(task_mgr_action)

        self.addSeparator()

        # Lock taskbar
        lock_action = QAction(
            load_icon("lock"),
            "Khóa thanh tác vụ",
            self
        )
        lock_action.setCheckable(True)
        lock_action.triggered.connect(self.taskbar_locked.emit)
        self.addAction(lock_action)

        # Taskbar settings
        settings_action = QAction(
            load_icon("settings"),
            "Cài đặt thanh tác vụ",
            self
        )
        settings_action.triggered.connect(self.taskbar_settings_requested.emit)
        self.addAction(settings_action)


# ========== HELPER FUNCTIONS ==========

def show_desktop_context_menu(
        parent: QWidget,
        position: QPoint,
        **kwargs
) -> DesktopContextMenu:
    """
    Helper function to show desktop context menu

    Args:
        parent: Parent widget (desktop)
        position: Position to show menu
        **kwargs: Additional parameters

    Returns:
        DesktopContextMenu instance
    """
    menu = DesktopContextMenu(parent)

    # Connect any passed handlers
    for signal_name, handler in kwargs.items():
        if hasattr(menu, signal_name):
            signal = getattr(menu, signal_name)
            signal.connect(handler)

    # Show menu
    menu.exec(position)

    return menu


def show_icon_context_menu(
        icon_type: str,
        icon_name: str,
        parent: QWidget,
        position: QPoint,
        **kwargs
) -> IconContextMenu:
    """
    Helper function to show icon context menu

    Args:
        icon_type: Type of icon
        icon_name: Name of icon
        parent: Parent widget
        position: Position to show
        **kwargs: Signal handlers

    Returns:
        IconContextMenu instance
    """
    menu = IconContextMenu(icon_type, icon_name, parent)

    # Connect handlers
    for signal_name, handler in kwargs.items():
        if hasattr(menu, signal_name):
            signal = getattr(menu, signal_name)
            signal.connect(handler)

    # Show menu
    menu.exec(position)

    return menu