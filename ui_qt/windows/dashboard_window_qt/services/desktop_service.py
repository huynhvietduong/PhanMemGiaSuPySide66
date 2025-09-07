# ui_qt/windows/dashboard_window_qt/services/desktop_service.py
"""
Service layer để xử lý business logic của desktop area
Bao gồm: Arrange icons, snap to grid, save/restore positions
"""

import json
import math
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any, Set
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from PySide6.QtCore import QObject, Signal, QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QScreen, QGuiApplication

# Import từ các modules khác
try:
    from repositories.settings_repository import SettingsRepository
    from utils.constants import (
        DESKTOP_GRID_SIZE,
        DESKTOP_GRID_SPACING,
        DESKTOP_ICON_WIDTH,
        DESKTOP_ICON_HEIGHT,
        DESKTOP_ICON_SPACING,
        MAX_ICONS_PER_ROW,
        MAX_ICONS_PER_COLUMN
    )
except ImportError:
    # Fallback imports
    from ..repositories.settings_repository import SettingsRepository
    from ..utils.constants import (
        DESKTOP_GRID_SIZE,
        DESKTOP_GRID_SPACING,
        DESKTOP_ICON_WIDTH,
        DESKTOP_ICON_HEIGHT,
        DESKTOP_ICON_SPACING,
        MAX_ICONS_PER_ROW,
        MAX_ICONS_PER_COLUMN
    )

# Setup logger
logger = logging.getLogger(__name__)


# ========== ENUMS ==========

class ArrangeMode(Enum):
    """Chế độ sắp xếp icons"""
    GRID = "grid"  # Sắp xếp theo lưới
    LIST = "list"  # Sắp xếp danh sách dọc
    AUTO = "auto"  # Tự động sắp xếp
    MANUAL = "manual"  # Sắp xếp thủ công
    COLUMNS = "columns"  # Sắp xếp theo cột
    ROWS = "rows"  # Sắp xếp theo hàng


class SortBy(Enum):
    """Tiêu chí sắp xếp"""
    NAME = "name"  # Theo tên
    TYPE = "type"  # Theo loại
    SIZE = "size"  # Theo kích thước
    DATE_MODIFIED = "modified"  # Theo ngày sửa
    DATE_CREATED = "created"  # Theo ngày tạo
    CUSTOM = "custom"  # Tùy chỉnh


class IconAlignment(Enum):
    """Căn chỉnh icons"""
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    CENTER = "center"


# ========== DATA MODELS ==========

@dataclass
class DesktopIcon:
    """Model đại diện cho một icon trên desktop"""
    id: str  # ID unique
    name: str  # Tên hiển thị
    icon_path: str  # Đường dẫn icon
    target_path: str  # Đường dẫn target (app/file)
    position: Tuple[int, int]  # Vị trí (x, y)
    grid_position: Tuple[int, int]  # Vị trí lưới (row, col)
    size: Tuple[int, int] = (DESKTOP_ICON_WIDTH, DESKTOP_ICON_HEIGHT)
    is_selected: bool = False
    is_locked: bool = False  # Khóa vị trí
    is_hidden: bool = False
    icon_type: str = "app"  # app, file, folder, shortcut
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DesktopIcon':
        """Create from dictionary"""
        # Convert list to tuple for position
        if isinstance(data.get('position'), list):
            data['position'] = tuple(data['position'])
        if isinstance(data.get('grid_position'), list):
            data['grid_position'] = tuple(data['grid_position'])
        if isinstance(data.get('size'), list):
            data['size'] = tuple(data['size'])
        return cls(**data)


@dataclass
class DesktopLayout:
    """Layout configuration của desktop"""
    arrange_mode: ArrangeMode = ArrangeMode.GRID
    sort_by: SortBy = SortBy.NAME
    alignment: IconAlignment = IconAlignment.TOP_LEFT
    grid_enabled: bool = True
    snap_to_grid: bool = True
    auto_arrange: bool = False
    show_labels: bool = True
    icon_spacing: int = DESKTOP_ICON_SPACING
    grid_size: int = DESKTOP_GRID_SIZE
    max_columns: int = MAX_ICONS_PER_ROW
    max_rows: int = MAX_ICONS_PER_COLUMN


# ========== DESKTOP SERVICE ==========

class DesktopService(QObject):
    """
    Service xử lý logic desktop area
    Quản lý icons, positions, layouts
    """

    # Signals
    icon_added = Signal(str)  # icon_id
    icon_removed = Signal(str)  # icon_id
    icon_moved = Signal(str, tuple)  # icon_id, new_position
    icons_arranged = Signal()
    layout_changed = Signal()

    def __init__(self, parent=None):
        """Initialize service"""
        super().__init__(parent)

        # Data storage
        self.icons: Dict[str, DesktopIcon] = {}
        self.layout = DesktopLayout()
        self.desktop_size = self._get_desktop_size()

        # Grid tracking
        self.grid_occupied: Set[Tuple[int, int]] = set()

        # Settings repository
        self.settings_repo = SettingsRepository()

        # Load saved positions
        self.load_icon_positions()

    # ========== ICON MANAGEMENT ==========

    def add_icon(
            self,
            icon_id: str,
            name: str,
            icon_path: str,
            target_path: str,
            position: Optional[Tuple[int, int]] = None,
            icon_type: str = "app"
    ) -> bool:
        """
        Thêm icon vào desktop

        Args:
            icon_id: ID unique
            name: Tên hiển thị
            icon_path: Path to icon
            target_path: Path to target
            position: Vị trí (optional)
            icon_type: Loại icon

        Returns:
            True nếu thành công
        """
        try:
            # Check if already exists
            if icon_id in self.icons:
                logger.warning(f"Icon {icon_id} đã tồn tại")
                return False

            # Find position if not specified
            if position is None:
                position = self._find_free_position()

            # Snap to grid if enabled
            if self.layout.snap_to_grid:
                position = self._snap_to_grid(position)

            # Calculate grid position
            grid_position = self._pixel_to_grid(position)

            # Create icon
            icon = DesktopIcon(
                id=icon_id,
                name=name,
                icon_path=icon_path,
                target_path=target_path,
                position=position,
                grid_position=grid_position,
                icon_type=icon_type
            )

            # Add to storage
            self.icons[icon_id] = icon
            self.grid_occupied.add(grid_position)

            # Emit signal
            self.icon_added.emit(icon_id)

            # Save positions
            self.save_icon_positions()

            logger.info(f"Đã thêm icon: {icon_id}")
            return True

        except Exception as e:
            logger.error(f"Lỗi thêm icon: {e}")
            return False

    def remove_icon(self, icon_id: str) -> bool:
        """
        Xóa icon khỏi desktop

        Args:
            icon_id: ID của icon

        Returns:
            True nếu thành công
        """
        try:
            if icon_id not in self.icons:
                return False

            # Remove from grid tracking
            icon = self.icons[icon_id]
            self.grid_occupied.discard(icon.grid_position)

            # Remove from storage
            del self.icons[icon_id]

            # Emit signal
            self.icon_removed.emit(icon_id)

            # Save positions
            self.save_icon_positions()

            logger.info(f"Đã xóa icon: {icon_id}")
            return True

        except Exception as e:
            logger.error(f"Lỗi xóa icon: {e}")
            return False

    def move_icon(
            self,
            icon_id: str,
            new_position: Tuple[int, int],
            snap: bool = True
    ) -> bool:
        """
        Di chuyển icon đến vị trí mới

        Args:
            icon_id: ID của icon
            new_position: Vị trí mới (x, y)
            snap: Có snap to grid không

        Returns:
            True nếu thành công
        """
        try:
            if icon_id not in self.icons:
                return False

            icon = self.icons[icon_id]

            # Check if locked
            if icon.is_locked:
                logger.warning(f"Icon {icon_id} đã bị khóa")
                return False

            # Snap to grid if enabled
            if snap and self.layout.snap_to_grid:
                new_position = self._snap_to_grid(new_position)

            # Update grid tracking
            old_grid = icon.grid_position
            new_grid = self._pixel_to_grid(new_position)

            # Check if new position is occupied
            if new_grid in self.grid_occupied and new_grid != old_grid:
                # Find nearest free position
                new_grid = self._find_nearest_free_grid(new_grid)
                new_position = self._grid_to_pixel(new_grid)

            # Update positions
            self.grid_occupied.discard(old_grid)
            self.grid_occupied.add(new_grid)

            icon.position = new_position
            icon.grid_position = new_grid

            # Emit signal
            self.icon_moved.emit(icon_id, new_position)

            # Save positions
            self.save_icon_positions()

            return True

        except Exception as e:
            logger.error(f"Lỗi di chuyển icon: {e}")
            return False

    # ========== ARRANGE METHODS ==========

    def arrange_icons(
            self,
            mode: Optional[ArrangeMode] = None,
            sort_by: Optional[SortBy] = None
    ):
        """
        Sắp xếp tất cả icons

        Args:
            mode: Chế độ sắp xếp (optional)
            sort_by: Tiêu chí sắp xếp (optional)
        """
        try:
            if mode:
                self.layout.arrange_mode = mode
            if sort_by:
                self.layout.sort_by = sort_by

            # Sort icons
            sorted_icons = self._sort_icons(list(self.icons.values()))

            # Clear grid tracking
            self.grid_occupied.clear()

            # Arrange based on mode
            if self.layout.arrange_mode == ArrangeMode.GRID:
                self._arrange_grid(sorted_icons)
            elif self.layout.arrange_mode == ArrangeMode.LIST:
                self._arrange_list(sorted_icons)
            elif self.layout.arrange_mode == ArrangeMode.COLUMNS:
                self._arrange_columns(sorted_icons)
            elif self.layout.arrange_mode == ArrangeMode.ROWS:
                self._arrange_rows(sorted_icons)
            elif self.layout.arrange_mode == ArrangeMode.AUTO:
                self._arrange_auto(sorted_icons)

            # Emit signal
            self.icons_arranged.emit()

            # Save positions
            self.save_icon_positions()

            logger.info(f"Đã sắp xếp {len(sorted_icons)} icons")

        except Exception as e:
            logger.error(f"Lỗi sắp xếp icons: {e}")

    def _arrange_grid(self, icons: List[DesktopIcon]):
        """Sắp xếp theo lưới"""
        start_x, start_y = self._get_start_position()

        col = 0
        row = 0

        for icon in icons:
            # Calculate position
            x = start_x + col * (self.layout.grid_size + self.layout.icon_spacing)
            y = start_y + row * (self.layout.grid_size + self.layout.icon_spacing)

            # Update icon
            icon.position = (x, y)
            icon.grid_position = (row, col)
            self.grid_occupied.add((row, col))

            # Move to next position
            col += 1
            if col >= self.layout.max_columns:
                col = 0
                row += 1
                if row >= self.layout.max_rows:
                    break

    def _arrange_list(self, icons: List[DesktopIcon]):
        """Sắp xếp dạng danh sách dọc"""
        start_x, start_y = self._get_start_position()

        row = 0

        for icon in icons:
            # Calculate position
            x = start_x
            y = start_y + row * (DESKTOP_ICON_HEIGHT + self.layout.icon_spacing)

            # Update icon
            icon.position = (x, y)
            icon.grid_position = (row, 0)
            self.grid_occupied.add((row, 0))

            row += 1
            if row >= self.layout.max_rows:
                break

    def _arrange_columns(self, icons: List[DesktopIcon]):
        """Sắp xếp theo cột (dọc trước, ngang sau)"""
        start_x, start_y = self._get_start_position()

        col = 0
        row = 0

        for icon in icons:
            # Calculate position
            x = start_x + col * (self.layout.grid_size + self.layout.icon_spacing)
            y = start_y + row * (self.layout.grid_size + self.layout.icon_spacing)

            # Update icon
            icon.position = (x, y)
            icon.grid_position = (row, col)
            self.grid_occupied.add((row, col))

            # Move to next position (column-first)
            row += 1
            if row >= self.layout.max_rows:
                row = 0
                col += 1
                if col >= self.layout.max_columns:
                    break

    def _arrange_rows(self, icons: List[DesktopIcon]):
        """Sắp xếp theo hàng (ngang trước, dọc sau)"""
        # Giống arrange_grid
        self._arrange_grid(icons)

    def _arrange_auto(self, icons: List[DesktopIcon]):
        """Sắp xếp tự động - tối ưu không gian"""
        # Tính toán layout tối ưu dựa trên số lượng icons
        icon_count = len(icons)

        if icon_count <= 10:
            # Ít icons - sắp xếp 1 cột
            self._arrange_list(icons)
        elif icon_count <= 30:
            # Trung bình - sắp xếp grid
            self._arrange_grid(icons)
        else:
            # Nhiều icons - sắp xếp columns để tận dụng không gian
            self._arrange_columns(icons)

    def arrange_by_type(self):
        """Sắp xếp icons theo loại"""
        # Nhóm icons theo type
        grouped = {}
        for icon in self.icons.values():
            if icon.icon_type not in grouped:
                grouped[icon.icon_type] = []
            grouped[icon.icon_type].append(icon)

        # Sắp xếp từng nhóm
        start_x, start_y = self._get_start_position()
        current_row = 0

        for icon_type in ['folder', 'app', 'file', 'shortcut']:
            if icon_type in grouped:
                icons = sorted(grouped[icon_type], key=lambda i: i.name.lower())

                for i, icon in enumerate(icons):
                    col = i % self.layout.max_columns
                    row = current_row + i // self.layout.max_columns

                    x = start_x + col * (self.layout.grid_size + self.layout.icon_spacing)
                    y = start_y + row * (self.layout.grid_size + self.layout.icon_spacing)

                    icon.position = (x, y)
                    icon.grid_position = (row, col)
                    self.grid_occupied.add((row, col))

                # Next group starts on new row
                current_row += (len(icons) - 1) // self.layout.max_columns + 2

        self.icons_arranged.emit()
        self.save_icon_positions()

    def align_to_grid(self):
        """Căn chỉnh tất cả icons theo lưới"""
        for icon in self.icons.values():
            if not icon.is_locked:
                new_position = self._snap_to_grid(icon.position)
                new_grid = self._pixel_to_grid(new_position)

                # Update positions
                icon.position = new_position
                icon.grid_position = new_grid

        # Rebuild grid tracking
        self._rebuild_grid_tracking()

        self.icons_arranged.emit()
        self.save_icon_positions()

    # ========== SELECTION METHODS ==========

    def select_icon(self, icon_id: str, multi_select: bool = False):
        """Select icon(s)"""
        if icon_id in self.icons:
            if not multi_select:
                # Clear other selections
                for icon in self.icons.values():
                    icon.is_selected = False

            self.icons[icon_id].is_selected = True

    def deselect_icon(self, icon_id: str):
        """Deselect icon"""
        if icon_id in self.icons:
            self.icons[icon_id].is_selected = False

    def select_all(self):
        """Select all icons"""
        for icon in self.icons.values():
            icon.is_selected = True

    def deselect_all(self):
        """Deselect all icons"""
        for icon in self.icons.values():
            icon.is_selected = False

    def get_selected_icons(self) -> List[DesktopIcon]:
        """Get list of selected icons"""
        return [icon for icon in self.icons.values() if icon.is_selected]

    def delete_selected(self):
        """Delete all selected icons"""
        selected = self.get_selected_icons()
        for icon in selected:
            self.remove_icon(icon.id)

    # ========== GRID UTILITIES ==========

    def _snap_to_grid(self, position: Tuple[int, int]) -> Tuple[int, int]:
        """
        Snap position to grid

        Args:
            position: (x, y) pixel position

        Returns:
            Snapped position
        """
        x, y = position
        grid_size = self.layout.grid_size

        snapped_x = round(x / grid_size) * grid_size
        snapped_y = round(y / grid_size) * grid_size

        return (snapped_x, snapped_y)

    def _pixel_to_grid(self, position: Tuple[int, int]) -> Tuple[int, int]:
        """
        Convert pixel position to grid coordinates

        Args:
            position: (x, y) pixel position

        Returns:
            (row, col) grid position
        """
        x, y = position
        grid_size = self.layout.grid_size + self.layout.icon_spacing

        col = x // grid_size
        row = y // grid_size

        return (row, col)

    def _grid_to_pixel(self, grid_position: Tuple[int, int]) -> Tuple[int, int]:
        """
        Convert grid coordinates to pixel position

        Args:
            grid_position: (row, col) grid position

        Returns:
            (x, y) pixel position
        """
        row, col = grid_position
        grid_size = self.layout.grid_size + self.layout.icon_spacing

        x = col * grid_size
        y = row * grid_size

        return (x, y)

    def _find_free_position(self) -> Tuple[int, int]:
        """
        Find first free position on grid

        Returns:
            (x, y) pixel position
        """
        for row in range(self.layout.max_rows):
            for col in range(self.layout.max_columns):
                if (row, col) not in self.grid_occupied:
                    return self._grid_to_pixel((row, col))

        # No free position, return last position
        return self._grid_to_pixel((0, 0))

    def _find_nearest_free_grid(
            self,
            target_grid: Tuple[int, int]
    ) -> Tuple[int, int]:
        """
        Find nearest free grid position

        Args:
            target_grid: Target (row, col)

        Returns:
            Nearest free (row, col)
        """
        if target_grid not in self.grid_occupied:
            return target_grid

        row, col = target_grid

        # Search in expanding squares
        for distance in range(1, max(self.layout.max_rows, self.layout.max_columns)):
            # Check positions at this distance
            positions = []

            # Top and bottom rows
            for c in range(max(0, col - distance), min(self.layout.max_columns, col + distance + 1)):
                if row - distance >= 0:
                    positions.append((row - distance, c))
                if row + distance < self.layout.max_rows:
                    positions.append((row + distance, c))

            # Left and right columns
            for r in range(max(0, row - distance + 1), min(self.layout.max_rows, row + distance)):
                if col - distance >= 0:
                    positions.append((r, col - distance))
                if col + distance < self.layout.max_columns:
                    positions.append((r, col + distance))

            # Check each position
            for pos in positions:
                if pos not in self.grid_occupied:
                    return pos

        return target_grid

    def _rebuild_grid_tracking(self):
        """Rebuild grid occupation tracking"""
        self.grid_occupied.clear()
        for icon in self.icons.values():
            self.grid_occupied.add(icon.grid_position)

    # ========== SORT METHODS ==========

    def _sort_icons(self, icons: List[DesktopIcon]) -> List[DesktopIcon]:
        """
        Sort icons by current criteria

        Args:
            icons: List of icons to sort

        Returns:
            Sorted list
        """
        if self.layout.sort_by == SortBy.NAME:
            return sorted(icons, key=lambda i: i.name.lower())
        elif self.layout.sort_by == SortBy.TYPE:
            return sorted(icons, key=lambda i: (i.icon_type, i.name.lower()))
        elif self.layout.sort_by == SortBy.DATE_MODIFIED:
            # Would need actual file dates
            return sorted(icons, key=lambda i: i.name.lower())
        elif self.layout.sort_by == SortBy.DATE_CREATED:
            # Would need actual file dates
            return sorted(icons, key=lambda i: i.name.lower())
        else:
            return icons

    # ========== LAYOUT UTILITIES ==========

    def _get_start_position(self) -> Tuple[int, int]:
        """
        Get starting position based on alignment

        Returns:
            (x, y) starting position
        """
        margin = 20

        if self.layout.alignment == IconAlignment.TOP_LEFT:
            return (margin, margin)
        elif self.layout.alignment == IconAlignment.TOP_RIGHT:
            x = self.desktop_size[0] - (self.layout.max_columns * self.layout.grid_size) - margin
            return (x, margin)
        elif self.layout.alignment == IconAlignment.BOTTOM_LEFT:
            y = self.desktop_size[1] - (self.layout.max_rows * self.layout.grid_size) - margin
            return (margin, y)
        elif self.layout.alignment == IconAlignment.BOTTOM_RIGHT:
            x = self.desktop_size[0] - (self.layout.max_columns * self.layout.grid_size) - margin
            y = self.desktop_size[1] - (self.layout.max_rows * self.layout.grid_size) - margin
            return (x, y)
        elif self.layout.alignment == IconAlignment.CENTER:
            x = (self.desktop_size[0] - (self.layout.max_columns * self.layout.grid_size)) // 2
            y = (self.desktop_size[1] - (self.layout.max_rows * self.layout.grid_size)) // 2
            return (x, y)

        return (margin, margin)

    def _get_desktop_size(self) -> Tuple[int, int]:
        """Get desktop size"""
        try:
            screen = QGuiApplication.primaryScreen()
            if screen:
                size = screen.availableGeometry()
                return (size.width(), size.height())
        except:
            pass

        # Default size
        return (1920, 1080)

    def set_desktop_size(self, width: int, height: int):
        """Set desktop size (for resolution changes)"""
        self.desktop_size = (width, height)

        # Recalculate max columns/rows
        self.layout.max_columns = width // (self.layout.grid_size + self.layout.icon_spacing)
        self.layout.max_rows = height // (self.layout.grid_size + self.layout.icon_spacing)

    # ========== PERSISTENCE ==========

    def save_icon_positions(self):
        """Save icon positions to settings"""
        try:
            positions = {}
            for icon_id, icon in self.icons.items():
                positions[icon_id] = {
                    'position': list(icon.position),
                    'grid_position': list(icon.grid_position),
                    'is_locked': icon.is_locked
                }

            # Save to settings
            self.settings_repo.get_settings().desktop_icon_positions = positions
            self.settings_repo.save_settings()

            logger.info(f"Đã lưu vị trí {len(positions)} icons")

        except Exception as e:
            logger.error(f"Lỗi lưu icon positions: {e}")

    def load_icon_positions(self):
        """Load icon positions from settings"""
        try:
            positions = self.settings_repo.get_desktop_icon_positions()

            for icon_id, data in positions.items():
                if icon_id in self.icons:
                    icon = self.icons[icon_id]
                    icon.position = tuple(data['position'])
                    icon.grid_position = tuple(data['grid_position'])
                    icon.is_locked = data.get('is_locked', False)

            # Rebuild grid tracking
            self._rebuild_grid_tracking()

        except Exception as e:
            logger.error(f"Lỗi load icon positions: {e}")

    def save_layout_settings(self):
        """Save layout settings"""
        try:
            layout_data = {
                'arrange_mode': self.layout.arrange_mode.value,
                'sort_by': self.layout.sort_by.value,
                'alignment': self.layout.alignment.value,
                'grid_enabled': self.layout.grid_enabled,
                'snap_to_grid': self.layout.snap_to_grid,
                'auto_arrange': self.layout.auto_arrange,
                'icon_spacing': self.layout.icon_spacing,
                'grid_size': self.layout.grid_size
            }

            # Save to settings
            self.settings_repo.update_desktop(
                align_icons_to_grid=self.layout.snap_to_grid,
                auto_arrange_icons=self.layout.auto_arrange,
                icon_spacing=self.layout.icon_spacing
            )

        except Exception as e:
            logger.error(f"Lỗi lưu layout settings: {e}")

    # ========== PUBLIC METHODS ==========

    def refresh_desktop(self):
        """Refresh desktop - reload icons"""
        # Re-arrange if auto-arrange is enabled
        if self.layout.auto_arrange:
            self.arrange_icons()
        else:
            # Just align to grid
            if self.layout.snap_to_grid:
                self.align_to_grid()

    def cleanup_invalid_icons(self):
        """Remove icons with invalid targets"""
        invalid = []
        for icon_id, icon in self.icons.items():
            # Check if target exists
            if not Path(icon.target_path).exists():
                invalid.append(icon_id)

        for icon_id in invalid:
            self.remove_icon(icon_id)

        if invalid:
            logger.info(f"Đã xóa {len(invalid)} icons không hợp lệ")

    def get_icon_at_position(self, position: Tuple[int, int]) -> Optional[DesktopIcon]:
        """
        Get icon at specific position

        Args:
            position: (x, y) position

        Returns:
            DesktopIcon or None
        """
        for icon in self.icons.values():
            x, y = icon.position
            w, h = icon.size

            if x <= position[0] <= x + w and y <= position[1] <= y + h:
                return icon

        return None

    def get_icons_in_rect(self, rect: QRect) -> List[DesktopIcon]:
        """
        Get all icons within rectangle

        Args:
            rect: Selection rectangle

        Returns:
            List of icons in rect
        """
        icons_in_rect = []

        for icon in self.icons.values():
            x, y = icon.position
            w, h = icon.size
            icon_rect = QRect(x, y, w, h)

            if rect.intersects(icon_rect):
                icons_in_rect.append(icon)

        return icons_in_rect