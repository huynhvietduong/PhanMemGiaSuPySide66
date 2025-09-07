# ui_qt/windows/dashboard_window_qt/views/start_menu/start_menu_tiles.py
"""
Start Menu Tiles - Pinned apps tiles/shortcuts trong Start Menu
Hỗ trợ nhiều kích thước tile, drag & drop, live tiles
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime
import logging

from PySide6.QtWidgets import (
    QWidget, QGridLayout, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QMenu, QSizePolicy,
    QGraphicsOpacityEffect, QToolButton
)
from PySide6.QtCore import (
    Qt, QSize, QPoint, QRect, QTimer,
    Signal, Property, QPropertyAnimation,
    QEasingCurve, QEvent, QMimeData,
    QParallelAnimationGroup
)
from PySide6.QtGui import (
    QPainter, QPixmap, QIcon, QFont, QColor,
    QPen, QBrush, QAction, QPalette,
    QLinearGradient, QRadialGradient,
    QMouseEvent, QPaintEvent, QEnterEvent,
    QDragEnterEvent, QDragMoveEvent, QDropEvent,
    QDrag, QCursor, QTransform
)

# Import utils
from ...utils.constants import (
    TILE_SMALL_SIZE, TILE_MEDIUM_SIZE, TILE_WIDE_SIZE, TILE_LARGE_SIZE,
    TILE_SPACING, TILE_ANIMATION_DURATION
)
from ...utils.assets import load_icon, get_app_icon

# Logger
logger = logging.getLogger(__name__)


# ========== ENUMS ==========

class TileSize(Enum):
    """Tile sizes matching Windows Start Menu"""
    SMALL = "small"  # 1x1 grid cells
    MEDIUM = "medium"  # 2x2 grid cells
    WIDE = "wide"  # 4x2 grid cells
    LARGE = "large"  # 4x4 grid cells


class TileStyle(Enum):
    """Tile visual styles"""
    ICON_ONLY = "icon_only"
    ICON_AND_TEXT = "icon_and_text"
    LIVE = "live"  # Live tile with updates
    CUSTOM = "custom"  # Custom content


# ========== MAIN TILES CONTAINER ==========

class StartMenuTiles(QWidget):
    """
    Container for Start Menu tiles grid
    Manages pinned apps as tiles with various sizes
    """

    # Signals
    tile_clicked = Signal(str)  # app_id
    tile_removed = Signal(str)  # app_id
    tile_resized = Signal(str, TileSize)  # app_id, new_size
    tiles_rearranged = Signal()  # After drag & drop

    def __init__(self, parent=None):
        """Initialize tiles container"""
        super().__init__(parent)

        # Tiles storage
        self.tiles: Dict[str, 'Tile'] = {}
        self.tile_positions: Dict[str, Tuple[int, int]] = {}

        # Grid settings
        self.columns = 4
        self.rows = 3
        self.grid_size = TILE_SMALL_SIZE + TILE_SPACING

        # Drag & drop state
        self.drag_tile = None
        self.drag_start_pos = None
        self.drop_indicator = None

        # Setup UI
        self._setup_ui()

        logger.debug("StartMenuTiles initialized")

    def _setup_ui(self):
        """Setup UI layout"""
        self.setObjectName("StartMenuTiles")

        # Set fixed size based on grid
        width = self.columns * self.grid_size
        height = self.rows * self.grid_size
        self.setFixedSize(width, height)

        # Enable drag & drop
        self.setAcceptDrops(True)

        # Create grid layout
        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(TILE_SPACING)

        # Style
        self.setStyleSheet("""
            #StartMenuTiles {
                background: transparent;
            }
        """)

    # ========== TILE MANAGEMENT ==========

    def add_tile(
            self,
            app_id: str,
            name: str,
            icon: Optional[QIcon] = None,
            size: TileSize = TileSize.MEDIUM,
            position: Optional[Tuple[int, int]] = None,
            style: TileStyle = TileStyle.ICON_AND_TEXT,
            color: Optional[QColor] = None
    ) -> 'Tile':
        """
        Add a new tile to the grid

        Args:
            app_id: Application ID
            name: Display name
            icon: App icon
            size: Tile size
            position: Grid position (row, col) or auto
            style: Visual style
            color: Background color

        Returns:
            Created Tile widget
        """
        # Check if already exists
        if app_id in self.tiles:
            logger.warning(f"Tile already exists: {app_id}")
            return self.tiles[app_id]

        # Create tile
        tile = Tile(
            app_id=app_id,
            name=name,
            icon=icon or get_app_icon(app_id),
            size=size,
            style=style,
            parent=self
        )

        # Set color if provided
        if color:
            tile.set_background_color(color)

        # Connect signals
        tile.clicked.connect(lambda: self.tile_clicked.emit(app_id))
        tile.remove_requested.connect(lambda: self.remove_tile(app_id))
        tile.resize_requested.connect(lambda s: self._resize_tile(app_id, s))

        # Find position
        if not position:
            position = self._find_empty_position(size)

        if position:
            # Add to grid
            row, col = position
            row_span, col_span = self._get_tile_span(size)
            self.layout.addWidget(tile, row, col, row_span, col_span)

            # Store references
            self.tiles[app_id] = tile
            self.tile_positions[app_id] = position

            # Animate entrance
            tile.animate_in()

            logger.debug(f"Added tile: {name} at position {position}")
            return tile
        else:
            logger.warning(f"No space for tile: {name}")
            tile.deleteLater()
            return None

    def remove_tile(self, app_id: str):
        """Remove a tile from the grid"""
        if app_id not in self.tiles:
            return

        tile = self.tiles[app_id]

        # Animate out
        tile.animate_out()

        # Remove after animation
        QTimer.singleShot(TILE_ANIMATION_DURATION, lambda: self._remove_tile_widget(app_id))

        # Emit signal
        self.tile_removed.emit(app_id)

        logger.debug(f"Removed tile: {app_id}")

    def _remove_tile_widget(self, app_id: str):
        """Actually remove the tile widget"""
        if app_id in self.tiles:
            tile = self.tiles[app_id]
            self.layout.removeWidget(tile)
            tile.deleteLater()

            del self.tiles[app_id]
            del self.tile_positions[app_id]

    def _resize_tile(self, app_id: str, new_size: TileSize):
        """Resize a tile"""
        if app_id not in self.tiles:
            return

        tile = self.tiles[app_id]
        old_size = tile.size_type

        # Check if new size fits
        position = self.tile_positions[app_id]
        if self._can_fit_tile(position, new_size, exclude_id=app_id):
            # Update tile
            tile.set_size(new_size)

            # Update layout
            row, col = position
            row_span, col_span = self._get_tile_span(new_size)
            self.layout.addWidget(tile, row, col, row_span, col_span)

            # Emit signal
            self.tile_resized.emit(app_id, new_size)

            logger.debug(f"Resized tile {app_id}: {old_size.value} -> {new_size.value}")
        else:
            logger.warning(f"Cannot resize tile {app_id}: no space")

    def get_tile(self, index: int) -> Optional['Tile']:
        """Get tile by index"""
        tiles_list = list(self.tiles.values())
        if 0 <= index < len(tiles_list):
            return tiles_list[index]
        return None

    def count(self) -> int:
        """Get number of tiles"""
        return len(self.tiles)

    def clear(self):
        """Remove all tiles"""
        for app_id in list(self.tiles.keys()):
            self.remove_tile(app_id)

    # ========== POSITION MANAGEMENT ==========

    def _find_empty_position(self, size: TileSize) -> Optional[Tuple[int, int]]:
        """Find empty position for a tile of given size"""
        row_span, col_span = self._get_tile_span(size)

        # Try each position
        for row in range(self.rows - row_span + 1):
            for col in range(self.columns - col_span + 1):
                if self._is_position_empty(row, col, row_span, col_span):
                    return (row, col)

        return None

    def _is_position_empty(self, row: int, col: int, row_span: int, col_span: int) -> bool:
        """Check if a grid area is empty"""
        # Check bounds
        if row + row_span > self.rows or col + col_span > self.columns:
            return False

        # Check for overlaps with existing tiles
        for app_id, position in self.tile_positions.items():
            tile = self.tiles[app_id]
            tile_row, tile_col = position
            tile_row_span, tile_col_span = self._get_tile_span(tile.size_type)

            # Check overlap
            if not (row + row_span <= tile_row or
                    row >= tile_row + tile_row_span or
                    col + col_span <= tile_col or
                    col >= tile_col + tile_col_span):
                return False

        return True

    def _can_fit_tile(
            self,
            position: Tuple[int, int],
            size: TileSize,
            exclude_id: Optional[str] = None
    ) -> bool:
        """Check if a tile of given size can fit at position"""
        row, col = position
        row_span, col_span = self._get_tile_span(size)

        # Check bounds
        if row + row_span > self.rows or col + col_span > self.columns:
            return False

        # Check overlaps (excluding the tile being resized)
        for app_id, other_position in self.tile_positions.items():
            if app_id == exclude_id:
                continue

            tile = self.tiles[app_id]
            tile_row, tile_col = other_position
            tile_row_span, tile_col_span = self._get_tile_span(tile.size_type)

            # Check overlap
            if not (row + row_span <= tile_row or
                    row >= tile_row + tile_row_span or
                    col + col_span <= tile_col or
                    col >= tile_col + tile_col_span):
                return False

        return True

    def _get_tile_span(self, size: TileSize) -> Tuple[int, int]:
        """Get grid span for tile size"""
        if size == TileSize.SMALL:
            return (1, 1)
        elif size == TileSize.MEDIUM:
            return (2, 2)
        elif size == TileSize.WIDE:
            return (2, 4)
        elif size == TileSize.LARGE:
            return (4, 4)
        else:
            return (2, 2)

    # ========== DRAG & DROP ==========

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter"""
        if event.mimeData().hasFormat("application/x-tile-id"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        """Handle drag move"""
        if event.mimeData().hasFormat("application/x-tile-id"):
            # Show drop indicator
            pos = event.pos()
            grid_pos = self._get_grid_position(pos)

            if grid_pos:
                self._show_drop_indicator(grid_pos)

            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Handle drop"""
        if event.mimeData().hasFormat("application/x-tile-id"):
            tile_id = str(event.mimeData().data("application/x-tile-id"), 'utf-8')

            # Get drop position
            pos = event.pos()
            grid_pos = self._get_grid_position(pos)

            if grid_pos and tile_id in self.tiles:
                # Move tile to new position
                self._move_tile(tile_id, grid_pos)

            # Hide drop indicator
            self._hide_drop_indicator()

            event.acceptProposedAction()
        else:
            event.ignore()

    def _get_grid_position(self, pos: QPoint) -> Optional[Tuple[int, int]]:
        """Convert pixel position to grid position"""
        col = pos.x() // self.grid_size
        row = pos.y() // self.grid_size

        if 0 <= row < self.rows and 0 <= col < self.columns:
            return (row, col)
        return None

    def _move_tile(self, app_id: str, new_position: Tuple[int, int]):
        """Move tile to new position"""
        if app_id not in self.tiles:
            return

        tile = self.tiles[app_id]

        # Check if new position is valid
        if self._can_fit_tile(new_position, tile.size_type, exclude_id=app_id):
            # Update position
            old_position = self.tile_positions[app_id]
            self.tile_positions[app_id] = new_position

            # Update layout
            row, col = new_position
            row_span, col_span = self._get_tile_span(tile.size_type)
            self.layout.addWidget(tile, row, col, row_span, col_span)

            # Emit signal
            self.tiles_rearranged.emit()

            logger.debug(f"Moved tile {app_id}: {old_position} -> {new_position}")

    def _show_drop_indicator(self, position: Tuple[int, int]):
        """Show drop position indicator"""
        # Create indicator if not exists
        if not self.drop_indicator:
            self.drop_indicator = QWidget(self)
            self.drop_indicator.setStyleSheet("""
                background: rgba(0, 120, 215, 50);
                border: 2px dashed rgba(0, 120, 215, 150);
                border-radius: 4px;
            """)

        # Position indicator
        row, col = position
        x = col * self.grid_size
        y = row * self.grid_size

        self.drop_indicator.move(x, y)
        self.drop_indicator.resize(self.grid_size - TILE_SPACING, self.grid_size - TILE_SPACING)
        self.drop_indicator.show()

    def _hide_drop_indicator(self):
        """Hide drop indicator"""
        if self.drop_indicator:
            self.drop_indicator.hide()


# ========== INDIVIDUAL TILE WIDGET ==========

class Tile(QFrame):
    """
    Individual tile widget for Start Menu
    Represents a single app with icon and optional text
    """

    # Signals
    clicked = Signal()
    remove_requested = Signal()
    resize_requested = Signal(TileSize)

    def __init__(
            self,
            app_id: str,
            name: str,
            icon: Optional[QIcon] = None,
            size: TileSize = TileSize.MEDIUM,
            style: TileStyle = TileStyle.ICON_AND_TEXT,
            parent=None
    ):
        """Initialize tile"""
        super().__init__(parent)

        # Properties
        self.app_id = app_id
        self.name = name
        self.app_icon = icon or get_app_icon(app_id)
        self.size_type = size
        self.style_type = style

        # Visual state
        self.is_hovered = False
        self.is_pressed = False
        self.hover_progress = 0.0

        # Live tile data
        self.live_content = None
        self.live_update_timer = None

        # Custom color
        self.custom_color = None

        # Animations
        self.hover_animation = None
        self.press_animation = None
        self._setup_animations()

        # Setup UI
        self._setup_ui()

        # Install event filter
        self.installEventFilter(self)

    def _setup_ui(self):
        """Setup tile UI"""
        self.setObjectName("StartMenuTile")

        # Set size based on type
        self._update_size()

        # Frame style
        self.setFrameStyle(QFrame.NoFrame)

        # Enable mouse tracking for hover
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Create content based on style
        if self.style_type == TileStyle.ICON_ONLY:
            self._create_icon_only_content(layout)
        elif self.style_type == TileStyle.ICON_AND_TEXT:
            self._create_icon_text_content(layout)
        elif self.style_type == TileStyle.LIVE:
            self._create_live_content(layout)

        # Apply style
        self._apply_style()

    def _create_icon_only_content(self, layout: QVBoxLayout):
        """Create icon-only tile content"""
        # Icon label
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)

        # Set icon
        if self.app_icon:
            icon_size = self._get_icon_size()
            pixmap = self.app_icon.pixmap(icon_size)
            self.icon_label.setPixmap(pixmap)

        layout.addWidget(self.icon_label, 0, Qt.AlignCenter)

    def _create_icon_text_content(self, layout: QVBoxLayout):
        """Create icon and text tile content"""
        # Icon
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)

        if self.app_icon:
            icon_size = self._get_icon_size()
            pixmap = self.app_icon.pixmap(icon_size)
            self.icon_label.setPixmap(pixmap)

        layout.addWidget(self.icon_label, 1, Qt.AlignCenter)

        # Text
        self.text_label = QLabel(self.name)
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet("""
            color: white;
            font-size: 11px;
        """)
        layout.addWidget(self.text_label)

    def _create_live_content(self, layout: QVBoxLayout):
        """Create live tile content"""
        # Start with icon/text
        self._create_icon_text_content(layout)

        # Setup live updates
        self.live_update_timer = QTimer()
        self.live_update_timer.timeout.connect(self._update_live_content)
        self.live_update_timer.start(30000)  # Update every 30 seconds

    def _update_size(self):
        """Update widget size based on tile size"""
        if self.size_type == TileSize.SMALL:
            self.setFixedSize(TILE_SMALL_SIZE, TILE_SMALL_SIZE)
        elif self.size_type == TileSize.MEDIUM:
            self.setFixedSize(TILE_MEDIUM_SIZE, TILE_MEDIUM_SIZE)
        elif self.size_type == TileSize.WIDE:
            self.setFixedSize(TILE_WIDE_SIZE, TILE_MEDIUM_SIZE)
        elif self.size_type == TileSize.LARGE:
            self.setFixedSize(TILE_LARGE_SIZE, TILE_LARGE_SIZE)

    def _get_icon_size(self) -> QSize:
        """Get appropriate icon size for tile"""
        if self.size_type == TileSize.SMALL:
            return QSize(24, 24)
        elif self.size_type == TileSize.MEDIUM:
            return QSize(48, 48)
        elif self.size_type == TileSize.WIDE:
            return QSize(48, 48)
        elif self.size_type == TileSize.LARGE:
            return QSize(96, 96)
        else:
            return QSize(48, 48)

    def _apply_style(self):
        """Apply visual style"""
        # Default background color or custom
        if self.custom_color:
            bg_color = self.custom_color.name()
        else:
            bg_color = self._get_default_color()

        self.setStyleSheet(f"""
            #StartMenuTile {{
                background: {bg_color};
                border-radius: 4px;
            }}
            #StartMenuTile:hover {{
                background: {self._lighten_color(bg_color)};
            }}
        """)

    def _get_default_color(self) -> str:
        """Get default tile color based on app"""
        # Use a hash of app_id to generate consistent color
        colors = [
            "#0078d4",  # Blue
            "#107c10",  # Green
            "#5c2d91",  # Purple
            "#e81123",  # Red
            "#ff8c00",  # Orange
            "#00bcf2",  # Light blue
            "#e3008c",  # Magenta
            "#00cc6a",  # Mint
        ]

        index = hash(self.app_id) % len(colors)
        return colors[index]

    def _lighten_color(self, color: str) -> str:
        """Lighten a color for hover effect"""
        # Simple lightening by adjusting RGB values
        qcolor = QColor(color)
        qcolor = qcolor.lighter(120)
        return qcolor.name()

    def _setup_animations(self):
        """Setup animations"""
        # Hover animation
        self.hover_animation = QPropertyAnimation(self, b"hover_progress")
        self.hover_animation.setDuration(150)
        self.hover_animation.setEasingCurve(QEasingCurve.InOutQuad)

    # ========== PROPERTIES ==========

    def get_hover_progress(self) -> float:
        """Get hover animation progress"""
        return self.hover_progress

    def set_hover_progress(self, value: float):
        """Set hover animation progress"""
        self.hover_progress = value
        self.update()

    hover_progress = Property(float, get_hover_progress, set_hover_progress)

    # ========== PAINT EVENT ==========

    def paintEvent(self, event: QPaintEvent):
        """Custom paint for effects"""
        super().paintEvent(event)

        if self.hover_progress > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)

            # Draw hover overlay
            overlay_color = QColor(255, 255, 255, int(30 * self.hover_progress))
            painter.fillRect(self.rect(), overlay_color)

    # ========== MOUSE EVENTS ==========

    def enterEvent(self, event: QEnterEvent):
        """Mouse enter"""
        self.is_hovered = True

        # Start hover animation
        self.hover_animation.setStartValue(self.hover_progress)
        self.hover_animation.setEndValue(1.0)
        self.hover_animation.start()

        super().enterEvent(event)

    def leaveEvent(self, event):
        """Mouse leave"""
        self.is_hovered = False

        # Reverse hover animation
        self.hover_animation.setStartValue(self.hover_progress)
        self.hover_animation.setEndValue(0.0)
        self.hover_animation.start()

        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        """Mouse press"""
        if event.button() == Qt.LeftButton:
            self.is_pressed = True

            # Visual feedback
            self.setStyleSheet(self.styleSheet() + """
                #StartMenuTile {
                    transform: scale(0.95);
                }
            """)

            # Start drag if moved
            self.drag_start_pos = event.pos()

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Mouse release"""
        if event.button() == Qt.LeftButton:
            self.is_pressed = False

            # Reset visual
            self._apply_style()

            # Emit clicked if not dragged
            if self.rect().contains(event.pos()):
                self.clicked.emit()

        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Mouse move - start drag if needed"""
        if event.buttons() & Qt.LeftButton and self.drag_start_pos:
            if (event.pos() - self.drag_start_pos).manhattanLength() >= 10:
                self._start_drag()

        super().mouseMoveEvent(event)

    def contextMenuEvent(self, event):
        """Right-click context menu"""
        menu = QMenu(self)

        # Unpin from Start
        unpin_action = QAction(load_icon("unpin"), "Unpin from Start", menu)
        unpin_action.triggered.connect(self.remove_requested.emit)
        menu.addAction(unpin_action)

        menu.addSeparator()

        # Resize options
        resize_menu = menu.addMenu("Resize")

        for size in TileSize:
            size_action = QAction(size.value.capitalize(), resize_menu)
            size_action.setCheckable(True)
            size_action.setChecked(size == self.size_type)
            size_action.triggered.connect(lambda checked, s=size: self.resize_requested.emit(s))
            resize_menu.addAction(size_action)

        menu.addSeparator()

        # More options
        more_action = QAction("More", menu)
        more_action.setEnabled(False)
        menu.addAction(more_action)

        menu.exec(event.globalPos())

    # ========== DRAG & DROP ==========

    def _start_drag(self):
        """Start dragging the tile"""
        drag = QDrag(self)

        # Set mime data
        mime_data = QMimeData()
        mime_data.setData("application/x-tile-id", self.app_id.encode('utf-8'))
        drag.setMimeData(mime_data)

        # Create drag pixmap
        pixmap = QPixmap(self.size())
        self.render(pixmap)
        drag.setPixmap(pixmap)
        drag.setHotSpot(self.drag_start_pos)

        # Execute drag
        drag.exec(Qt.MoveAction)

    # ========== PUBLIC METHODS ==========

    def set_size(self, size: TileSize):
        """Change tile size"""
        self.size_type = size
        self._update_size()

        # Update icon if exists
        if hasattr(self, 'icon_label') and self.app_icon:
            icon_size = self._get_icon_size()
            pixmap = self.app_icon.pixmap(icon_size)
            self.icon_label.setPixmap(pixmap)

    def set_background_color(self, color: QColor):
        """Set custom background color"""
        self.custom_color = color
        self._apply_style()

    def animate_in(self):
        """Animate tile appearance"""
        # Scale and fade in
        effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(effect)

        fade_in = QPropertyAnimation(effect, b"opacity")
        fade_in.setDuration(TILE_ANIMATION_DURATION)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.OutCubic)
        fade_in.start()

    def animate_out(self):
        """Animate tile removal"""
        effect = self.graphicsEffect()
        if not effect:
            effect = QGraphicsOpacityEffect()
            self.setGraphicsEffect(effect)

        fade_out = QPropertyAnimation(effect, b"opacity")
        fade_out.setDuration(TILE_ANIMATION_DURATION)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.InCubic)
        fade_out.start()

    def _update_live_content(self):
        """Update live tile content (for live tiles)"""
        # This would fetch and display live content
        # For example: weather, news, notifications
        pass