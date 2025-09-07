# ui_qt/windows/dashboard_window_qt/views/desktop/desktop_icon_manager.py
"""
Desktop Icon Manager - Quản lý icons trên desktop
Xử lý thêm, xóa, sắp xếp, lưu/khôi phục vị trí icons
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime
from enum import Enum
import logging

from PySide6.QtWidgets import (
    QWidget, QMessageBox, QInputDialog,
    QMenu, QFileDialog, QApplication
)
from PySide6.QtCore import (
    Qt, QPoint, QRect, QSize, QTimer,
    Signal, QObject, QPropertyAnimation,
    QParallelAnimationGroup, QEasingCurve
)
from PySide6.QtGui import QIcon, QAction, QPixmap

# Import widgets
from ..widgets.app_icon_widget import (
    AppIconWidget, FileIconWidget, ShortcutIconWidget
)

# Import utils
from ...utils.constants import (
    DESKTOP_ICON_WIDTH, DESKTOP_ICON_HEIGHT,
    DESKTOP_ICON_SPACING, DESKTOP_GRID_SIZE,
    MAX_DESKTOP_ICONS, MAX_ICONS_PER_ROW,
    MAX_ICONS_PER_COLUMN
)
from ...utils.helpers import (
    snap_to_grid, calculate_grid_layout,
    get_file_info, get_file_icon,
    create_desktop_shortcut, sanitize_filename
)
from ...utils.assets import load_icon, get_app_icon

# Import repositories
from ...repositories.app_repository import AppRepository, AppModel
from ...repositories.settings_repository import SettingsRepository

# Logger
logger = logging.getLogger(__name__)


# ========== ENUMS ==========

class SortBy(Enum):
    """Tiêu chí sắp xếp icons"""
    NAME = "name"
    TYPE = "type"
    SIZE = "size"
    DATE_MODIFIED = "date_modified"
    DATE_CREATED = "date_created"


class ArrangeMode(Enum):
    """Chế độ sắp xếp icons"""
    GRID = "grid"  # Lưới đều
    AUTO = "auto"  # Tự động
    LIST = "list"  # Danh sách dọc
    CUSTOM = "custom"  # Tùy chỉnh


class IconType(Enum):
    """Loại icon"""
    APP = "app"
    FILE = "file"
    FOLDER = "folder"
    SHORTCUT = "shortcut"
    WIDGET = "widget"


# ========== ICON MANAGER CLASS ==========

class DesktopIconManager(QObject):
    """
    Manager quản lý tất cả icons trên desktop
    Xử lý CRUD operations, arrangements, persistence
    """

    # Signals
    icon_added = Signal(str, QWidget)  # icon_id, widget
    icon_removed = Signal(str)  # icon_id
    icon_moved = Signal(str, QPoint)  # icon_id, new_position
    icon_renamed = Signal(str, str)  # icon_id, new_name
    icons_arranged = Signal()  # After arrangement
    selection_changed = Signal(list)  # selected icon_ids

    def __init__(self, desktop_widget: QWidget, parent=None):
        """
        Initialize Icon Manager

        Args:
            desktop_widget: Desktop container widget
            parent: Parent object
        """
        super().__init__(parent)

        # Desktop reference
        self.desktop = desktop_widget

        # Repositories
        self.app_repo = AppRepository()
        self.settings_repo = SettingsRepository()

        # Icon storage
        self.icons: Dict[str, AppIconWidget] = {}  # {icon_id: widget}
        self.icon_positions: Dict[str, QPoint] = {}  # {icon_id: position}
        self.icon_types: Dict[str, IconType] = {}  # {icon_id: type}
        self.icon_data: Dict[str, Any] = {}  # {icon_id: metadata}

        # Selection
        self.selected_icons: List[str] = []

        # Grid settings
        self.grid_enabled = True
        self.grid_size = DESKTOP_GRID_SIZE
        self.grid_spacing = DESKTOP_ICON_SPACING
        self.arrange_mode = ArrangeMode.GRID

        # Animation
        self.animations = []

        # Auto-save timer
        self.save_timer = QTimer()
        self.save_timer.timeout.connect(self._auto_save_positions)
        self.save_timer.setSingleShot(True)

        # Load saved state
        self._load_saved_state()

        logger.info("Desktop Icon Manager initialized")

    # ========== INITIALIZATION ==========

    def _load_saved_state(self):
        """Load saved icon positions and settings"""
        try:
            # Load desktop settings
            desktop_settings = self.settings_repo.get_desktop()
            self.grid_enabled = desktop_settings.align_icons_to_grid

            # Load saved positions
            saved_positions = self.settings_repo.get_desktop_icon_positions()
            self.icon_positions = {
                icon_id: QPoint(x, y)
                for icon_id, (x, y) in saved_positions.items()
            }

            logger.info(f"Loaded {len(self.icon_positions)} saved icon positions")

        except Exception as e:
            logger.error(f"Error loading saved state: {e}")

    # ========== ADD ICON METHODS ==========

    def add_app_icon(
            self,
            app: Union[AppModel, str],
            position: QPoint = None
    ) -> Optional[str]:
        """
        Add app icon to desktop

        Args:
            app: AppModel or app_id
            position: Desired position (None = auto)

        Returns:
            icon_id if successful, None otherwise
        """
        try:
            # Get app model if needed
            if isinstance(app, str):
                app = self.app_repo.get_app_by_id(app)
                if not app:
                    logger.error(f"App not found: {app}")
                    return None

            # Check icon limit
            if len(self.icons) >= MAX_DESKTOP_ICONS:
                QMessageBox.warning(
                    self.desktop,
                    "Giới hạn icons",
                    f"Desktop chỉ cho phép tối đa {MAX_DESKTOP_ICONS} icons"
                )
                return None

            # Check if already exists
            if app.id in self.icons:
                logger.warning(f"Icon already exists: {app.id}")
                return app.id

            # Create icon widget
            icon_widget = AppIconWidget(
                app_id=app.id,
                name=app.display_name,
                icon=get_app_icon(app.id),
                parent=self.desktop
            )

            # Connect signals
            self._connect_icon_signals(icon_widget, app.id)

            # Determine position
            if position is None:
                position = self._find_empty_position()
            elif self.grid_enabled:
                position = snap_to_grid(position, self.grid_size)

            # Place icon
            icon_widget.move(position)
            icon_widget.show()

            # Store references
            self.icons[app.id] = icon_widget
            self.icon_positions[app.id] = position
            self.icon_types[app.id] = IconType.APP
            self.icon_data[app.id] = {
                'app_model': app,
                'added_time': datetime.now()
            }

            # Emit signal
            self.icon_added.emit(app.id, icon_widget)

            # Schedule save
            self._schedule_save()

            logger.info(f"Added app icon: {app.display_name} at {position}")
            return app.id

        except Exception as e:
            logger.error(f"Error adding app icon: {e}")
            return None

    def add_file_icon(
            self,
            file_path: str,
            position: QPoint = None
    ) -> Optional[str]:
        """
        Add file/folder icon to desktop

        Args:
            file_path: Path to file/folder
            position: Desired position

        Returns:
            icon_id if successful
        """
        try:
            # Validate path
            path = Path(file_path)
            if not path.exists():
                logger.error(f"File not found: {file_path}")
                return None

            # Generate unique ID
            icon_id = self._generate_icon_id(file_path)

            # Check if already exists
            if icon_id in self.icons:
                logger.warning(f"Icon already exists: {icon_id}")
                return icon_id

            # Check limit
            if len(self.icons) >= MAX_DESKTOP_ICONS:
                QMessageBox.warning(
                    self.desktop,
                    "Giới hạn icons",
                    f"Desktop chỉ cho phép tối đa {MAX_DESKTOP_ICONS} icons"
                )
                return None

            # Create icon widget
            icon_widget = FileIconWidget(
                file_path=file_path,
                parent=self.desktop
            )

            # Connect signals
            self._connect_icon_signals(icon_widget, icon_id)

            # Determine position
            if position is None:
                position = self._find_empty_position()
            elif self.grid_enabled:
                position = snap_to_grid(position, self.grid_size)

            # Place icon
            icon_widget.move(position)
            icon_widget.show()

            # Store references
            self.icons[icon_id] = icon_widget
            self.icon_positions[icon_id] = position
            self.icon_types[icon_id] = IconType.FOLDER if path.is_dir() else IconType.FILE
            self.icon_data[icon_id] = {
                'file_path': file_path,
                'file_info': get_file_info(file_path),
                'added_time': datetime.now()
            }

            # Emit signal
            self.icon_added.emit(icon_id, icon_widget)

            # Schedule save
            self._schedule_save()

            logger.info(f"Added file icon: {path.name} at {position}")
            return icon_id

        except Exception as e:
            logger.error(f"Error adding file icon: {e}")
            return None

    def add_shortcut_icon(
            self,
            target: str,
            name: str = None,
            icon: Union[QIcon, str] = None,
            position: QPoint = None
    ) -> Optional[str]:
        """
        Add shortcut icon to desktop

        Args:
            target: Target path (app_id or file path)
            name: Display name
            icon: Icon
            position: Position

        Returns:
            icon_id if successful
        """
        try:
            # Generate shortcut ID
            icon_id = f"shortcut_{self._generate_icon_id(target)}"

            # Check if exists
            if icon_id in self.icons:
                return icon_id

            # Check limit
            if len(self.icons) >= MAX_DESKTOP_ICONS:
                return None

            # Determine name
            if not name:
                if os.path.exists(target):
                    name = Path(target).stem
                else:
                    app = self.app_repo.get_app_by_id(target)
                    name = app.display_name if app else target

            # Create widget
            icon_widget = ShortcutIconWidget(
                shortcut_path=icon_id,
                target_path=target,
                name=name,
                icon=icon or get_app_icon(target),
                parent=self.desktop
            )

            # Connect signals
            self._connect_icon_signals(icon_widget, icon_id)

            # Position
            if position is None:
                position = self._find_empty_position()
            elif self.grid_enabled:
                position = snap_to_grid(position, self.grid_size)

            # Place
            icon_widget.move(position)
            icon_widget.show()

            # Store
            self.icons[icon_id] = icon_widget
            self.icon_positions[icon_id] = position
            self.icon_types[icon_id] = IconType.SHORTCUT
            self.icon_data[icon_id] = {
                'target': target,
                'name': name,
                'added_time': datetime.now()
            }

            # Emit
            self.icon_added.emit(icon_id, icon_widget)

            # Save
            self._schedule_save()

            logger.info(f"Added shortcut: {name}")
            return icon_id

        except Exception as e:
            logger.error(f"Error adding shortcut: {e}")
            return None

    # ========== REMOVE ICON METHODS ==========

    def remove_icon(self, icon_id: str, confirm: bool = True) -> bool:
        """
        Remove icon from desktop

        Args:
            icon_id: Icon ID to remove
            confirm: Show confirmation dialog

        Returns:
            True if removed
        """
        try:
            if icon_id not in self.icons:
                logger.warning(f"Icon not found: {icon_id}")
                return False

            # Confirmation
            if confirm:
                widget = self.icons[icon_id]
                reply = QMessageBox.question(
                    self.desktop,
                    "Xác nhận xóa",
                    f"Xóa '{widget.get_name()}' khỏi desktop?",
                    QMessageBox.Yes | QMessageBox.No
                )

                if reply != QMessageBox.Yes:
                    return False

            # Remove widget
            widget = self.icons[icon_id]
            widget.hide()
            widget.deleteLater()

            # Remove from storage
            del self.icons[icon_id]
            del self.icon_positions[icon_id]
            del self.icon_types[icon_id]
            if icon_id in self.icon_data:
                del self.icon_data[icon_id]

            # Remove from selection
            if icon_id in self.selected_icons:
                self.selected_icons.remove(icon_id)

            # Emit signal
            self.icon_removed.emit(icon_id)

            # Save
            self._schedule_save()

            logger.info(f"Removed icon: {icon_id}")
            return True

        except Exception as e:
            logger.error(f"Error removing icon: {e}")
            return False

    def remove_selected_icons(self) -> int:
        """
        Remove all selected icons

        Returns:
            Number of icons removed
        """
        if not self.selected_icons:
            return 0

        # Confirm
        reply = QMessageBox.question(
            self.desktop,
            "Xác nhận xóa",
            f"Xóa {len(self.selected_icons)} mục đã chọn?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return 0

        # Remove each
        removed = 0
        for icon_id in list(self.selected_icons):
            if self.remove_icon(icon_id, confirm=False):
                removed += 1

        self.clear_selection()
        return removed

    def clear_all_icons(self, confirm: bool = True) -> bool:
        """
        Remove all icons from desktop

        Args:
            confirm: Show confirmation

        Returns:
            True if cleared
        """
        if not self.icons:
            return True

        if confirm:
            reply = QMessageBox.question(
                self.desktop,
                "Xác nhận",
                "Xóa tất cả icons khỏi desktop?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return False

        # Remove all
        for icon_id in list(self.icons.keys()):
            self.remove_icon(icon_id, confirm=False)

        return True

    # ========== ARRANGE METHODS ==========

    def arrange_icons(
            self,
            sort_by: SortBy = SortBy.NAME,
            ascending: bool = True
    ):
        """
        Arrange all icons in order

        Args:
            sort_by: Sort criteria
            ascending: Sort direction
        """
        if not self.icons:
            return

        logger.info(f"Arranging icons by {sort_by.value}")

        # Get sorted list
        sorted_icons = self._sort_icons(sort_by, ascending)

        # Calculate grid layout
        cols, rows = self._calculate_grid_dimensions()

        # Create animation group
        animation_group = QParallelAnimationGroup()

        # Arrange each icon
        for index, (icon_id, widget) in enumerate(sorted_icons):
            # Calculate position
            row = index // cols
            col = index % cols

            x = self.grid_spacing + col * self.grid_size
            y = self.grid_spacing + row * self.grid_size

            new_pos = QPoint(x, y)

            # Animate movement
            if widget.pos() != new_pos:
                animation = self._create_move_animation(widget, new_pos)
                animation_group.addAnimation(animation)

            # Update position
            self.icon_positions[icon_id] = new_pos

        # Start animations
        if animation_group.animationCount() > 0:
            animation_group.start()
            self.animations.append(animation_group)
            animation_group.finished.connect(
                lambda: self.animations.remove(animation_group)
            )

        # Emit signal
        self.icons_arranged.emit()

        # Save positions
        self._schedule_save()

    def arrange_by_name(self):
        """Arrange icons by name"""
        self.arrange_icons(SortBy.NAME, True)

    def arrange_by_type(self):
        """Arrange icons by type"""
        self.arrange_icons(SortBy.TYPE, True)

    def arrange_by_date(self):
        """Arrange icons by date modified"""
        self.arrange_icons(SortBy.DATE_MODIFIED, False)

    def align_to_grid(self):
        """Align all icons to grid without sorting"""
        if not self.grid_enabled:
            return

        logger.info("Aligning icons to grid")

        animation_group = QParallelAnimationGroup()

        for icon_id, widget in self.icons.items():
            current_pos = widget.pos()
            grid_pos = snap_to_grid(current_pos, self.grid_size)

            if current_pos != grid_pos:
                animation = self._create_move_animation(widget, grid_pos)
                animation_group.addAnimation(animation)
                self.icon_positions[icon_id] = grid_pos

        if animation_group.animationCount() > 0:
            animation_group.start()
            self.animations.append(animation_group)

        self._schedule_save()

    def auto_arrange(self):
        """Auto arrange icons to fill empty spaces"""
        if not self.icons:
            return

        logger.info("Auto-arranging icons")

        # Get all icons sorted by current position (top-left to bottom-right)
        icons_list = sorted(
            self.icons.items(),
            key=lambda x: (x[1].y(), x[1].x())
        )

        # Find all valid positions
        valid_positions = self._get_valid_grid_positions()

        animation_group = QParallelAnimationGroup()

        for index, (icon_id, widget) in enumerate(icons_list):
            if index < len(valid_positions):
                new_pos = valid_positions[index]

                if widget.pos() != new_pos:
                    animation = self._create_move_animation(widget, new_pos)
                    animation_group.addAnimation(animation)

                self.icon_positions[icon_id] = new_pos

        if animation_group.animationCount() > 0:
            animation_group.start()
            self.animations.append(animation_group)

        self._schedule_save()

    # ========== SELECTION METHODS ==========

    def select_icon(self, icon_id: str, add_to_selection: bool = False):
        """
        Select an icon

        Args:
            icon_id: Icon to select
            add_to_selection: Add to current selection (Ctrl+Click)
        """
        if icon_id not in self.icons:
            return

        if not add_to_selection:
            self.clear_selection()

        widget = self.icons[icon_id]
        widget.set_selected(True)

        if icon_id not in self.selected_icons:
            self.selected_icons.append(icon_id)

        self.selection_changed.emit(self.selected_icons)

    def clear_selection(self):
        """Clear all selections"""
        for icon_id in self.selected_icons:
            if icon_id in self.icons:
                self.icons[icon_id].set_selected(False)

        self.selected_icons.clear()
        self.selection_changed.emit([])

    def select_all(self):
        """Select all icons"""
        self.selected_icons = list(self.icons.keys())

        for widget in self.icons.values():
            widget.set_selected(True)

        self.selection_changed.emit(self.selected_icons)

    def select_icons_in_rect(self, rect: QRect):
        """
        Select icons within rectangle

        Args:
            rect: Selection rectangle
        """
        self.clear_selection()

        for icon_id, widget in self.icons.items():
            if rect.intersects(widget.geometry()):
                widget.set_selected(True)
                self.selected_icons.append(icon_id)

        self.selection_changed.emit(self.selected_icons)

    # ========== MOVE METHODS ==========

    def move_icon(self, icon_id: str, position: QPoint, animate: bool = True):
        """
        Move icon to new position

        Args:
            icon_id: Icon to move
            position: New position
            animate: Use animation
        """
        if icon_id not in self.icons:
            return

        widget = self.icons[icon_id]

        # Snap to grid if enabled
        if self.grid_enabled:
            position = snap_to_grid(position, self.grid_size)

        # Check if position is valid
        if not self._is_valid_position(position, icon_id):
            return

        # Move
        if animate:
            animation = self._create_move_animation(widget, position)
            animation.start()
            self.animations.append(animation)
        else:
            widget.move(position)

        # Update position
        self.icon_positions[icon_id] = position

        # Emit signal
        self.icon_moved.emit(icon_id, position)

        # Save
        self._schedule_save()

    def move_selected_icons(self, delta: QPoint):
        """
        Move all selected icons by delta

        Args:
            delta: Movement delta
        """
        for icon_id in self.selected_icons:
            if icon_id in self.icons:
                current_pos = self.icon_positions[icon_id]
                new_pos = current_pos + delta
                self.move_icon(icon_id, new_pos, animate=False)

    # ========== RENAME METHODS ==========

    def rename_icon(self, icon_id: str):
        """Start renaming an icon"""
        if icon_id in self.icons:
            self.icons[icon_id].start_rename()

    def _handle_rename(self, icon_id: str, new_name: str):
        """Handle rename completion"""
        if icon_id in self.icon_data:
            self.icon_data[icon_id]['custom_name'] = new_name

        self.icon_renamed.emit(icon_id, new_name)
        self._schedule_save()

        logger.info(f"Renamed icon {icon_id} to {new_name}")

    # ========== PERSISTENCE METHODS ==========

    def save_state(self):
        """Save icon positions and data"""
        try:
            # Save positions to settings
            positions_dict = {
                icon_id: (pos.x(), pos.y())
                for icon_id, pos in self.icon_positions.items()
            }

            # Save each position
            for icon_id, (x, y) in positions_dict.items():
                self.settings_repo.save_desktop_icon_position(icon_id, (x, y))

            # Save icon data to separate file
            self._save_icon_data()

            logger.info(f"Saved {len(positions_dict)} icon positions")

        except Exception as e:
            logger.error(f"Error saving state: {e}")

    def _save_icon_data(self):
        """Save icon metadata to file"""
        try:
            data_file = Path("desktop_icons.json")

            save_data = {}
            for icon_id, data in self.icon_data.items():
                # Convert to serializable format
                save_item = {
                    'type': self.icon_types[icon_id].value,
                    'data': {}
                }

                if self.icon_types[icon_id] == IconType.APP:
                    save_item['data']['app_id'] = data['app_model'].id
                elif self.icon_types[icon_id] == IconType.FILE:
                    save_item['data']['file_path'] = data['file_path']
                elif self.icon_types[icon_id] == IconType.SHORTCUT:
                    save_item['data']['target'] = data['target']
                    save_item['data']['name'] = data['name']

                if 'custom_name' in data:
                    save_item['data']['custom_name'] = data['custom_name']

                save_data[icon_id] = save_item

            # Write to file
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving icon data: {e}")

    def load_saved_icons(self):
        """Load previously saved icons"""
        try:
            data_file = Path("desktop_icons.json")
            if not data_file.exists():
                return

            with open(data_file, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)

            for icon_id, item in saved_data.items():
                icon_type = IconType(item['type'])
                data = item['data']

                # Get saved position
                position = self.icon_positions.get(icon_id)

                # Create icon based on type
                if icon_type == IconType.APP:
                    self.add_app_icon(data['app_id'], position)
                elif icon_type == IconType.FILE:
                    if os.path.exists(data['file_path']):
                        self.add_file_icon(data['file_path'], position)
                elif icon_type == IconType.SHORTCUT:
                    self.add_shortcut_icon(
                        data['target'],
                        data.get('name'),
                        None,
                        position
                    )

                # Apply custom name if any
                if 'custom_name' in data and icon_id in self.icons:
                    self.icons[icon_id].set_name(data['custom_name'])

            logger.info(f"Loaded {len(saved_data)} saved icons")

        except Exception as e:
            logger.error(f"Error loading saved icons: {e}")

    def _schedule_save(self):
        """Schedule auto-save after delay"""
        self.save_timer.stop()
        self.save_timer.start(1000)  # Save after 1 second

    def _auto_save_positions(self):
        """Auto-save positions"""
        self.save_state()

    # ========== HELPER METHODS ==========

    def _find_empty_position(self) -> QPoint:
        """Find empty position for new icon"""
        desktop_rect = self.desktop.rect()

        # Start from top-left
        x = self.grid_spacing
        y = self.grid_spacing

        while y < desktop_rect.height() - DESKTOP_ICON_HEIGHT:
            while x < desktop_rect.width() - DESKTOP_ICON_WIDTH:
                pos = QPoint(x, y)

                # Check if position is occupied
                if self._is_position_empty(pos):
                    return pos

                x += self.grid_size

            x = self.grid_spacing
            y += self.grid_size

        # Default if no space
        return QPoint(self.grid_spacing, self.grid_spacing)

    def _is_position_empty(self, position: QPoint) -> bool:
        """Check if position is empty"""
        test_rect = QRect(position, QSize(DESKTOP_ICON_WIDTH, DESKTOP_ICON_HEIGHT))

        for widget in self.icons.values():
            if test_rect.intersects(widget.geometry()):
                return False

        return True

    def _is_valid_position(self, position: QPoint, exclude_id: str = None) -> bool:
        """Check if position is valid for icon"""
        # Check desktop bounds
        desktop_rect = self.desktop.rect()
        if not desktop_rect.contains(
                QRect(position, QSize(DESKTOP_ICON_WIDTH, DESKTOP_ICON_HEIGHT))
        ):
            return False

        # Check collision with other icons
        test_rect = QRect(position, QSize(DESKTOP_ICON_WIDTH, DESKTOP_ICON_HEIGHT))

        for icon_id, widget in self.icons.items():
            if icon_id != exclude_id:
                if test_rect.intersects(widget.geometry()):
                    return False

        return True

    def _get_valid_grid_positions(self) -> List[QPoint]:
        """Get all valid grid positions"""
        positions = []
        desktop_rect = self.desktop.rect()

        y = self.grid_spacing
        while y < desktop_rect.height() - DESKTOP_ICON_HEIGHT:
            x = self.grid_spacing
            while x < desktop_rect.width() - DESKTOP_ICON_WIDTH:
                positions.append(QPoint(x, y))
                x += self.grid_size
            y += self.grid_size

        return positions

    def _calculate_grid_dimensions(self) -> Tuple[int, int]:
        """Calculate grid columns and rows"""
        desktop_rect = self.desktop.rect()

        cols = max(1, (desktop_rect.width() - self.grid_spacing) // self.grid_size)
        rows = max(1, (desktop_rect.height() - self.grid_spacing) // self.grid_size)

        return min(cols, MAX_ICONS_PER_ROW), min(rows, MAX_ICONS_PER_COLUMN)

    def _sort_icons(
            self,
            sort_by: SortBy,
            ascending: bool
    ) -> List[Tuple[str, QWidget]]:
        """Sort icons by criteria"""
        icons_list = list(self.icons.items())

        if sort_by == SortBy.NAME:
            icons_list.sort(
                key=lambda x: x[1].get_name().lower(),
                reverse=not ascending
            )
        elif sort_by == SortBy.TYPE:
            icons_list.sort(
                key=lambda x: (self.icon_types[x[0]].value, x[1].get_name().lower()),
                reverse=not ascending
            )
        elif sort_by == SortBy.DATE_MODIFIED:
            icons_list.sort(
                key=lambda x: self.icon_data.get(x[0], {}).get('added_time', datetime.min),
                reverse=not ascending
            )

        return icons_list

    def _create_move_animation(
            self,
            widget: QWidget,
            end_pos: QPoint,
            duration: int = 300
    ) -> QPropertyAnimation:
        """Create movement animation"""
        animation = QPropertyAnimation(widget, b"pos")
        animation.setDuration(duration)
        animation.setStartValue(widget.pos())
        animation.setEndValue(end_pos)
        animation.setEasingCurve(QEasingCurve.InOutCubic)

        return animation

    def _generate_icon_id(self, source: str) -> str:
        """Generate unique icon ID"""
        # Use hash of source
        import hashlib

        hash_obj = hashlib.md5(source.encode())
        return hash_obj.hexdigest()[:8]

    def _connect_icon_signals(self, widget: AppIconWidget, icon_id: str):
        """Connect icon widget signals"""
        # Double-click
        widget.double_clicked.connect(
            lambda: self._handle_icon_double_click(icon_id)
        )

        # Click
        widget.clicked.connect(
            lambda: self.select_icon(icon_id, QApplication.keyboardModifiers() & Qt.ControlModifier)
        )

        # Rename
        widget.renamed.connect(
            lambda name: self._handle_rename(icon_id, name)
        )

        # Context menu
        widget.context_menu_requested.connect(
            lambda pos: self._show_icon_context_menu(icon_id, pos)
        )

    def _handle_icon_double_click(self, icon_id: str):
        """Handle icon double-click"""
        # This should be connected to launcher service
        logger.info(f"Double-clicked icon: {icon_id}")

    def _show_icon_context_menu(self, icon_id: str, pos: QPoint):
        """Show context menu for icon"""
        menu = QMenu(self.desktop)

        # Open
        open_action = QAction(load_icon("open"), "Mở", menu)
        open_action.triggered.connect(lambda: self._handle_icon_double_click(icon_id))
        menu.addAction(open_action)

        menu.addSeparator()

        # Rename
        rename_action = QAction(load_icon("edit"), "Đổi tên", menu)
        rename_action.triggered.connect(lambda: self.rename_icon(icon_id))
        menu.addAction(rename_action)

        # Delete
        delete_action = QAction(load_icon("delete"), "Xóa", menu)
        delete_action.triggered.connect(lambda: self.remove_icon(icon_id))
        menu.addAction(delete_action)

        menu.addSeparator()

        # Properties
        properties_action = QAction(load_icon("info"), "Thuộc tính", menu)
        menu.addAction(properties_action)

        # Show menu
        widget = self.icons[icon_id]
        menu.exec(widget.mapToGlobal(pos))

    # ========== PUBLIC METHODS ==========

    def get_icon_count(self) -> int:
        """Get total number of icons"""
        return len(self.icons)

    def get_selected_count(self) -> int:
        """Get number of selected icons"""
        return len(self.selected_icons)

    def get_icon_widget(self, icon_id: str) -> Optional[AppIconWidget]:
        """Get icon widget by ID"""
        return self.icons.get(icon_id)

    def has_icon(self, icon_id: str) -> bool:
        """Check if icon exists"""
        return icon_id in self.icons

    def refresh(self):
        """Refresh all icons"""
        # Re-align to grid
        if self.grid_enabled:
            self.align_to_grid()

        # Update all widgets
        for widget in self.icons.values():
            widget.update()

    def cleanup(self):
        """Cleanup manager"""
        # Stop animations
        for animation in self.animations:
            animation.stop()
        self.animations.clear()

        # Save state
        self.save_state()

        logger.info("Icon Manager cleaned up")