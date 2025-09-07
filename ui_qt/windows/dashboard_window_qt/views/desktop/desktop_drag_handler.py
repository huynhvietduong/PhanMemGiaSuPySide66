# ui_qt/windows/dashboard_window_qt/views/desktop/desktop_drag_handler.py
"""
Desktop Drag Handler - Xử lý drag & drop operations
Hỗ trợ drag icons, files từ ngoài, multi-select drag, visual feedback
"""

import os
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
import logging

from PySide6.QtWidgets import (
    QWidget, QLabel, QRubberBand, QApplication,
    QMessageBox, QMenu, QFileDialog
)
from PySide6.QtCore import (
    Qt, QPoint, QRect, QSize, QTimer, QUrl,
    Signal, QObject, QMimeData, QByteArray,
    QPropertyAnimation, QEasingCurve, QEvent
)
from PySide6.QtGui import (
    QPainter, QPixmap, QBrush, QColor, QPen,
    QDrag, QDragEnterEvent, QDragMoveEvent,
    QDragLeaveEvent, QDropEvent, QMouseEvent,
    QCursor, QPolygon, QRegion, QBitmap,QFont
)

# Import widgets
from ..widgets.app_icon_widget import AppIconWidget

# Import utils
from ...utils.constants import (
    DESKTOP_ICON_WIDTH, DESKTOP_ICON_HEIGHT,
    DESKTOP_GRID_SIZE, DESKTOP_GRID_SPACING
)
from ...utils.helpers import (
    snap_to_grid, get_file_info, sanitize_filename
)

# Logger
logger = logging.getLogger(__name__)


# ========== ENUMS ==========

class DragType(Enum):
    """Loại drag operation"""
    ICON = "icon"  # Drag desktop icon
    FILE = "file"  # Drag file từ explorer
    TEXT = "text"  # Drag text
    URL = "url"  # Drag URL
    MULTI = "multi"  # Drag nhiều items


class DropAction(Enum):
    """Hành động khi drop"""
    MOVE = "move"  # Di chuyển
    COPY = "copy"  # Sao chép
    LINK = "link"  # Tạo shortcut
    CANCEL = "cancel"  # Hủy


class DragState(Enum):
    """Trạng thái của drag operation"""
    IDLE = "idle"  # Không drag
    STARTING = "starting"  # Chuẩn bị drag
    DRAGGING = "dragging"  # Đang drag
    DROPPING = "dropping"  # Đang drop
    CANCELLED = "cancelled"  # Đã hủy


# ========== DATA CLASSES ==========

@dataclass
class DragData:
    """Data cho drag operation"""
    drag_type: DragType
    source_widget: Optional[QWidget] = None
    source_position: Optional[QPoint] = None
    items: List[Any] = None
    mime_data: Optional[QMimeData] = None
    pixmap: Optional[QPixmap] = None
    hot_spot: Optional[QPoint] = None
    modifiers: Qt.KeyboardModifiers = Qt.NoModifier

    def __post_init__(self):
        if self.items is None:
            self.items = []


@dataclass
class DropZone:
    """Vùng có thể drop"""
    rect: QRect
    widget: Optional[QWidget] = None
    accepts_types: List[DragType] = None
    highlight_color: QColor = QColor(0, 120, 215, 50)

    def __post_init__(self):
        if self.accepts_types is None:
            self.accepts_types = [DragType.ICON, DragType.FILE]


# ========== DRAG HANDLER CLASS ==========

class DesktopDragHandler(QObject):
    """
    Handler xử lý mọi drag & drop operations trên desktop
    Quản lý visual feedback, validation, và execution
    """

    # Signals
    drag_started = Signal(DragData)
    drag_moved = Signal(QPoint)
    drag_ended = Signal(bool)  # success

    icon_dropped = Signal(str, QPoint)  # icon_id, position
    files_dropped = Signal(list, QPoint)  # file_paths, position
    text_dropped = Signal(str, QPoint)  # text, position

    def __init__(self, desktop_widget: QWidget, parent=None):
        """
        Initialize Drag Handler

        Args:
            desktop_widget: Desktop container widget
            parent: Parent object
        """
        super().__init__(parent)

        # Desktop reference
        self.desktop = desktop_widget

        # State
        self.drag_state = DragState.IDLE
        self.current_drag: Optional[DragData] = None
        self.drag_widget: Optional[QDrag] = None

        # Visual feedback
        self.drop_indicator = DropIndicator(self.desktop)
        self.drag_preview = DragPreview(self.desktop)
        self.rubber_band: Optional[QRubberBand] = None

        # Drop zones
        self.drop_zones: List[DropZone] = []
        self.active_drop_zone: Optional[DropZone] = None

        # Selection
        self.selected_items: List[Any] = []
        self.selection_start: Optional[QPoint] = None

        # Settings
        self.grid_enabled = True
        self.grid_size = DESKTOP_GRID_SIZE
        self.multi_select_enabled = True
        self.auto_scroll_enabled = True

        # Timers
        self.auto_scroll_timer = QTimer()
        self.auto_scroll_timer.timeout.connect(self._auto_scroll)

        # Install event filter
        self.desktop.installEventFilter(self)

        logger.info("Desktop Drag Handler initialized")

    # ========== EVENT FILTER ==========

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Filter events for drag handling"""
        if obj != self.desktop:
            return False

        event_type = event.type()

        # Drag events
        if event_type == QEvent.DragEnter:
            return self._handle_drag_enter(event)
        elif event_type == QEvent.DragMove:
            return self._handle_drag_move(event)
        elif event_type == QEvent.DragLeave:
            return self._handle_drag_leave(event)
        elif event_type == QEvent.Drop:
            return self._handle_drop(event)

        # Mouse events for rubber band selection
        elif event_type == QEvent.MouseButtonPress:
            return self._handle_mouse_press(event)
        elif event_type == QEvent.MouseMove:
            return self._handle_mouse_move(event)
        elif event_type == QEvent.MouseButtonRelease:
            return self._handle_mouse_release(event)

        return False

    # ========== DRAG START ==========

    def start_drag(
            self,
            items: List[Any],
            drag_type: DragType = DragType.ICON,
            source_widget: QWidget = None,
            position: QPoint = None
    ) -> bool:
        """
        Start a drag operation

        Args:
            items: Items to drag
            drag_type: Type of drag
            source_widget: Source widget
            position: Start position

        Returns:
            True if drag started successfully
        """
        if self.drag_state != DragState.IDLE:
            logger.warning("Drag already in progress")
            return False

        if not items:
            logger.warning("No items to drag")
            return False

        logger.info(f"Starting drag: {drag_type.value} with {len(items)} items")

        # Create drag data
        self.current_drag = DragData(
            drag_type=drag_type,
            source_widget=source_widget or self.desktop,
            source_position=position or QCursor.pos(),
            items=items,
            modifiers=QApplication.keyboardModifiers()
        )

        # Create mime data
        self.current_drag.mime_data = self._create_mime_data(items, drag_type)

        # Create drag pixmap
        self.current_drag.pixmap = self._create_drag_pixmap(items, drag_type)
        self.current_drag.hot_spot = QPoint(
            self.current_drag.pixmap.width() // 2,
            self.current_drag.pixmap.height() // 2
        )

        # Create QDrag
        self.drag_widget = QDrag(source_widget or self.desktop)
        self.drag_widget.setMimeData(self.current_drag.mime_data)
        self.drag_widget.setPixmap(self.current_drag.pixmap)
        self.drag_widget.setHotSpot(self.current_drag.hot_spot)

        # Update state
        self.drag_state = DragState.DRAGGING

        # Show preview
        self.drag_preview.show_preview(self.current_drag)

        # Emit signal
        self.drag_started.emit(self.current_drag)

        # Execute drag
        result = self.drag_widget.exec(
            Qt.MoveAction | Qt.CopyAction | Qt.LinkAction
        )

        # Handle result
        success = result != Qt.IgnoreAction
        self._end_drag(success)

        return success

    def start_icon_drag(self, icon_widgets: List[AppIconWidget]) -> bool:
        """
        Start dragging desktop icons

        Args:
            icon_widgets: Icon widgets to drag

        Returns:
            True if started
        """
        if not icon_widgets:
            return False

        # Get icon IDs
        items = [w.app_id for w in icon_widgets]

        # Start drag
        return self.start_drag(
            items=items,
            drag_type=DragType.MULTI if len(items) > 1 else DragType.ICON,
            source_widget=icon_widgets[0] if len(items) == 1 else self.desktop
        )

    # ========== DRAG EVENTS ==========

    def _handle_drag_enter(self, event: QDragEnterEvent) -> bool:
        """Handle drag enter event"""
        mime_data = event.mimeData()

        # Check if we accept this drag
        if self._can_accept_drag(mime_data):
            event.acceptProposedAction()

            # Show drop indicator
            self.drop_indicator.show()
            self.drop_indicator.move_to(event.pos())

            # Find drop zone
            self._update_active_drop_zone(event.pos())

            logger.debug("Drag entered desktop")
            return True
        else:
            event.ignore()
            return False

    def _handle_drag_move(self, event: QDragMoveEvent) -> bool:
        """Handle drag move event"""
        if not self._can_accept_drag(event.mimeData()):
            event.ignore()
            return False

        # Update position
        pos = event.pos()

        # Snap to grid if enabled
        if self.grid_enabled:
            pos = snap_to_grid(pos, self.grid_size)

        # Update drop indicator
        self.drop_indicator.move_to(pos)

        # Update active drop zone
        self._update_active_drop_zone(pos)

        # Auto-scroll if near edges
        if self.auto_scroll_enabled:
            self._check_auto_scroll(pos)

        # Check if position is valid
        if self._is_valid_drop_position(pos, event.mimeData()):
            event.acceptProposedAction()
            self.drop_indicator.set_valid(True)
        else:
            event.ignore()
            self.drop_indicator.set_valid(False)

        # Emit signal
        self.drag_moved.emit(pos)

        return True

    def _handle_drag_leave(self, event: QDragLeaveEvent) -> bool:
        """Handle drag leave event"""
        # Hide indicators
        self.drop_indicator.hide()

        # Clear active drop zone
        if self.active_drop_zone:
            self._highlight_drop_zone(self.active_drop_zone, False)
            self.active_drop_zone = None

        # Stop auto-scroll
        self.auto_scroll_timer.stop()

        logger.debug("Drag left desktop")
        return True

    def _handle_drop(self, event: QDropEvent) -> bool:
        """Handle drop event"""
        mime_data = event.mimeData()
        pos = event.pos()

        # Snap to grid
        if self.grid_enabled:
            pos = snap_to_grid(pos, self.grid_size)

        # Check if valid
        if not self._is_valid_drop_position(pos, mime_data):
            event.ignore()
            self.drop_indicator.hide()
            return False

        # Get drop action
        action = self._determine_drop_action(event)

        # Process drop based on content
        success = False

        if mime_data.hasUrls():
            success = self._handle_file_drop(mime_data.urls(), pos, action)
        elif mime_data.hasText():
            success = self._handle_text_drop(mime_data.text(), pos)
        elif mime_data.hasFormat("application/x-icon-id"):
            success = self._handle_icon_drop(mime_data, pos, action)

        # Accept or reject
        if success:
            event.acceptProposedAction()
            logger.info(f"Drop accepted at {pos}")
        else:
            event.ignore()
            logger.warning("Drop rejected")

        # Hide indicators
        self.drop_indicator.hide()

        # Clear active drop zone
        if self.active_drop_zone:
            self._highlight_drop_zone(self.active_drop_zone, False)
            self.active_drop_zone = None

        return success

    # ========== DROP HANDLERS ==========

    def _handle_file_drop(
            self,
            urls: List[QUrl],
            position: QPoint,
            action: DropAction
    ) -> bool:
        """Handle dropping files"""
        file_paths = []

        for url in urls:
            if url.isLocalFile():
                path = url.toLocalFile()
                if os.path.exists(path):
                    file_paths.append(path)

        if not file_paths:
            return False

        logger.info(f"Dropping {len(file_paths)} files at {position}")

        # Emit signal
        self.files_dropped.emit(file_paths, position)

        return True

    def _handle_text_drop(self, text: str, position: QPoint) -> bool:
        """Handle dropping text"""
        if not text:
            return False

        logger.info(f"Dropping text at {position}: {text[:50]}...")

        # Emit signal
        self.text_dropped.emit(text, position)

        return True

    def _handle_icon_drop(
            self,
            mime_data: QMimeData,
            position: QPoint,
            action: DropAction
    ) -> bool:
        """Handle dropping desktop icons"""
        # Get icon ID from mime data
        icon_id_bytes = mime_data.data("application/x-icon-id")
        if not icon_id_bytes:
            return False

        icon_id = str(icon_id_bytes, 'utf-8')

        logger.info(f"Dropping icon {icon_id} at {position}")

        # Emit signal
        self.icon_dropped.emit(icon_id, position)

        return True

    # ========== RUBBER BAND SELECTION ==========

    def _handle_mouse_press(self, event: QMouseEvent) -> bool:
        """Handle mouse press for selection"""
        if event.button() != Qt.LeftButton:
            return False

        # Check if clicking on empty space
        widget_at = self.desktop.childAt(event.pos())
        if widget_at and isinstance(widget_at, AppIconWidget):
            return False  # Let icon handle it

        # Start rubber band selection
        self.selection_start = event.pos()

        if not self.rubber_band:
            self.rubber_band = QRubberBand(QRubberBand.Rectangle, self.desktop)

        self.rubber_band.setGeometry(QRect(self.selection_start, QSize()))
        self.rubber_band.show()

        return True

    def _handle_mouse_move(self, event: QMouseEvent) -> bool:
        """Handle mouse move for selection"""
        if not self.selection_start:
            return False

        if not (event.buttons() & Qt.LeftButton):
            return False

        # Update rubber band
        selection_rect = QRect(
            self.selection_start,
            event.pos()
        ).normalized()

        self.rubber_band.setGeometry(selection_rect)

        # Select icons in rectangle
        self._select_items_in_rect(selection_rect)

        return True

    def _handle_mouse_release(self, event: QMouseEvent) -> bool:
        """Handle mouse release for selection"""
        if event.button() != Qt.LeftButton:
            return False

        if self.selection_start:
            # Hide rubber band
            if self.rubber_band:
                self.rubber_band.hide()

            # Final selection
            selection_rect = QRect(
                self.selection_start,
                event.pos()
            ).normalized()

            self._select_items_in_rect(selection_rect)

            self.selection_start = None
            return True

        return False

    def _select_items_in_rect(self, rect: QRect):
        """Select items within rectangle"""
        # This should connect to icon manager
        # For now, just log
        logger.debug(f"Selecting items in rect: {rect}")

    # ========== MIME DATA ==========

    def _create_mime_data(
            self,
            items: List[Any],
            drag_type: DragType
    ) -> QMimeData:
        """Create MIME data for drag"""
        mime_data = QMimeData()

        if drag_type == DragType.ICON:
            # Add icon ID
            if items:
                icon_id = str(items[0])
                mime_data.setData(
                    "application/x-icon-id",
                    icon_id.encode('utf-8')
                )
                mime_data.setText(icon_id)

        elif drag_type == DragType.FILE:
            # Add file URLs
            urls = [QUrl.fromLocalFile(str(item)) for item in items]
            mime_data.setUrls(urls)

        elif drag_type == DragType.TEXT:
            # Add text
            if items:
                mime_data.setText(str(items[0]))

        elif drag_type == DragType.MULTI:
            # Add multiple icon IDs
            icon_ids = ','.join(str(item) for item in items)
            mime_data.setData(
                "application/x-icon-list",
                icon_ids.encode('utf-8')
            )
            mime_data.setText(f"{len(items)} items")

        return mime_data

    def _create_drag_pixmap(
            self,
            items: List[Any],
            drag_type: DragType
    ) -> QPixmap:
        """Create pixmap for drag preview"""
        if drag_type == DragType.MULTI and len(items) > 1:
            # Create stacked pixmap for multiple items
            return self._create_multi_drag_pixmap(len(items))
        else:
            # Create single item pixmap
            return self._create_single_drag_pixmap(drag_type)

    def _create_single_drag_pixmap(self, drag_type: DragType) -> QPixmap:
        """Create pixmap for single item"""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw icon background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(0, 120, 215, 100)))
        painter.drawRoundedRect(pixmap.rect(), 8, 8)

        # Draw icon
        icon_rect = pixmap.rect().adjusted(8, 8, -8, -8)

        if drag_type == DragType.ICON:
            # Draw generic icon
            painter.setPen(QPen(Qt.white, 2))
            painter.drawRect(icon_rect)
        elif drag_type == DragType.FILE:
            # Draw file icon
            painter.setPen(QPen(Qt.white, 2))
            painter.drawRect(icon_rect)
            painter.drawLine(
                icon_rect.topRight() - QPoint(10, 0),
                icon_rect.topRight() + QPoint(0, 10)
            )

        painter.end()
        return pixmap

    def _create_multi_drag_pixmap(self, count: int) -> QPixmap:
        """Create pixmap for multiple items"""
        pixmap = QPixmap(80, 80)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw stacked rectangles
        for i in range(min(3, count)):
            offset = i * 5
            rect = pixmap.rect().adjusted(
                offset, offset,
                -20 + offset, -20 + offset
            )

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(0, 120, 215, 100 - i * 20)))
            painter.drawRoundedRect(rect, 6, 6)

        # Draw count
        painter.setPen(Qt.white)
        painter.setFont(QFont("Arial", 14, QFont.Bold))
        painter.drawText(
            pixmap.rect(),
            Qt.AlignCenter,
            str(count)
        )

        painter.end()
        return pixmap

    # ========== VALIDATION ==========

    def _can_accept_drag(self, mime_data: QMimeData) -> bool:
        """Check if we can accept this drag"""
        return (
                mime_data.hasUrls() or
                mime_data.hasText() or
                mime_data.hasFormat("application/x-icon-id") or
                mime_data.hasFormat("application/x-icon-list")
        )

    def _is_valid_drop_position(
            self,
            position: QPoint,
            mime_data: QMimeData
    ) -> bool:
        """Check if position is valid for drop"""
        # Check desktop bounds
        if not self.desktop.rect().contains(position):
            return False

        # Check if position is occupied (for icon drops)
        if mime_data.hasFormat("application/x-icon-id"):
            # This should check with icon manager
            # For now, always valid
            pass

        return True

    def _determine_drop_action(self, event: QDropEvent) -> DropAction:
        """Determine drop action based on modifiers"""
        modifiers = event.keyboardModifiers()

        if modifiers & Qt.ControlModifier:
            return DropAction.COPY
        elif modifiers & Qt.ShiftModifier:
            return DropAction.MOVE
        elif modifiers & Qt.AltModifier:
            return DropAction.LINK
        else:
            # Default action
            return DropAction.MOVE

    # ========== DROP ZONES ==========

    def add_drop_zone(
            self,
            rect: QRect,
            widget: QWidget = None,
            accepts_types: List[DragType] = None
    ) -> DropZone:
        """Add a drop zone"""
        zone = DropZone(
            rect=rect,
            widget=widget,
            accepts_types=accepts_types
        )

        self.drop_zones.append(zone)
        return zone

    def remove_drop_zone(self, zone: DropZone):
        """Remove a drop zone"""
        if zone in self.drop_zones:
            self.drop_zones.remove(zone)

    def _update_active_drop_zone(self, position: QPoint):
        """Update active drop zone based on position"""
        new_zone = None

        for zone in self.drop_zones:
            if zone.rect.contains(position):
                new_zone = zone
                break

        if new_zone != self.active_drop_zone:
            # Unhighlight old zone
            if self.active_drop_zone:
                self._highlight_drop_zone(self.active_drop_zone, False)

            # Highlight new zone
            if new_zone:
                self._highlight_drop_zone(new_zone, True)

            self.active_drop_zone = new_zone

    def _highlight_drop_zone(self, zone: DropZone, highlight: bool):
        """Highlight or unhighlight drop zone"""
        if zone.widget:
            if highlight:
                zone.widget.setStyleSheet(
                    f"background-color: {zone.highlight_color.name()};"
                )
            else:
                zone.widget.setStyleSheet("")

    # ========== AUTO SCROLL ==========

    def _check_auto_scroll(self, position: QPoint):
        """Check if we should auto-scroll"""
        margin = 50
        rect = self.desktop.rect()

        if position.x() < margin:
            # Scroll left
            self._start_auto_scroll(-5, 0)
        elif position.x() > rect.width() - margin:
            # Scroll right
            self._start_auto_scroll(5, 0)
        elif position.y() < margin:
            # Scroll up
            self._start_auto_scroll(0, -5)
        elif position.y() > rect.height() - margin:
            # Scroll down
            self._start_auto_scroll(0, 5)
        else:
            # Stop scrolling
            self.auto_scroll_timer.stop()

    def _start_auto_scroll(self, dx: int, dy: int):
        """Start auto-scrolling"""
        self.auto_scroll_delta = QPoint(dx, dy)

        if not self.auto_scroll_timer.isActive():
            self.auto_scroll_timer.start(50)  # 50ms interval

    def _auto_scroll(self):
        """Perform auto-scroll"""
        # This would scroll the desktop if it has scroll bars
        # For now, just log
        logger.debug(f"Auto-scrolling: {self.auto_scroll_delta}")

    # ========== CLEANUP ==========

    def _end_drag(self, success: bool):
        """End drag operation"""
        # Hide preview
        self.drag_preview.hide()

        # Hide indicators
        self.drop_indicator.hide()

        # Clear state
        self.drag_state = DragState.IDLE
        self.current_drag = None
        self.drag_widget = None

        # Stop auto-scroll
        self.auto_scroll_timer.stop()

        # Emit signal
        self.drag_ended.emit(success)

        logger.info(f"Drag ended: {'success' if success else 'cancelled'}")


# ========== VISUAL FEEDBACK WIDGETS ==========

class DropIndicator(QWidget):
    """Visual indicator for drop position"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.is_valid = True

        # Make transparent
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Size
        self.setFixedSize(DESKTOP_ICON_WIDTH, DESKTOP_ICON_HEIGHT)

        # Hide initially
        self.hide()

    def paintEvent(self, event):
        """Paint drop indicator"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Choose color based on validity
        if self.is_valid:
            color = QColor(0, 120, 215, 100)  # Blue
            border_color = QColor(0, 120, 215, 200)
        else:
            color = QColor(215, 0, 0, 100)  # Red
            border_color = QColor(215, 0, 0, 200)

        # Draw rectangle
        painter.setPen(QPen(border_color, 2, Qt.DashLine))
        painter.setBrush(QBrush(color))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 4, 4)

    def move_to(self, position: QPoint):
        """Move indicator to position"""
        self.move(position - QPoint(self.width() // 2, self.height() // 2))

    def set_valid(self, valid: bool):
        """Set validity state"""
        if self.is_valid != valid:
            self.is_valid = valid
            self.update()


class DragPreview(QLabel):
    """Preview widget shown during drag"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Style
        self.setStyleSheet("""
            QLabel {
                background: rgba(0, 120, 215, 50);
                border: 2px solid rgba(0, 120, 215, 150);
                border-radius: 4px;
                padding: 4px;
                color: white;
            }
        """)

        # Make transparent to mouse
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        # Hide initially
        self.hide()

    def show_preview(self, drag_data: DragData):
        """Show preview for drag data"""
        # Set text
        if drag_data.drag_type == DragType.MULTI:
            self.setText(f"Moving {len(drag_data.items)} items")
        elif drag_data.drag_type == DragType.FILE:
            self.setText(f"Copying {len(drag_data.items)} files")
        else:
            self.setText("Moving item")

        # Position near cursor
        cursor_pos = QCursor.pos()
        self.move(self.parent().mapFromGlobal(cursor_pos) + QPoint(20, 20))

        # Show
        self.show()

        # Auto-hide after a moment
        QTimer.singleShot(1000, self.hide)


class MultiSelectOverlay(QWidget):
    """Overlay showing multi-select count"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.count = 0

        # Size
        self.setFixedSize(50, 50)

        # Transparent
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.hide()

    def set_count(self, count: int):
        """Set selection count"""
        self.count = count
        self.update()

        if count > 0:
            self.show()
        else:
            self.hide()

    def paintEvent(self, event):
        """Paint count badge"""
        if self.count <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw circle
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(0, 120, 215)))
        painter.drawEllipse(self.rect())

        # Draw count
        painter.setPen(Qt.white)
        painter.setFont(QFont("Arial", 16, QFont.Bold))
        painter.drawText(
            self.rect(),
            Qt.AlignCenter,
            str(self.count)
        )