# ui_qt/windows/dashboard_window_qt/views/widgets/quick_note_widget.py
"""
Quick Note Widget - Sticky Notes trên Desktop
Ghi chú nhanh với tính năng: Auto-save, Multiple notes, Rich text, Colors, Pin to desktop
"""

import json
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QToolButton, QLabel, QMenu, QColorDialog,
    QFontDialog, QMessageBox, QFrame, QSizeGrip,
    QGraphicsDropShadowEffect, QRubberBand, QApplication, QGraphicsOpacityEffect
)
from PySide6.QtCore import (
    Qt, QTimer, QPoint, QRect, QSize, QSettings,
    Signal, Property, QPropertyAnimation, QEasingCurve,
    QEvent, QMimeData, QByteArray, QDataStream, QIODevice,
    QParallelAnimationGroup, QSequentialAnimationGroup
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont,
    QLinearGradient, QPixmap, QIcon, QPainterPath,
    QMouseEvent, QPaintEvent, QResizeEvent, QKeyEvent,
    QTextCharFormat, QTextCursor, QDrag, QAction,
    QFontMetrics, QPolygonF, QCursor
)

# Import utils
try:
    from ...utils.constants import (
        NOTE_WIDGET_SIZE, AUTO_SAVE_INTERVAL,
        ANIMATION_DURATION_NORMAL
    )
    from ...utils.assets import load_icon
except ImportError:
    # Fallback values
    NOTE_WIDGET_SIZE = QSize(200, 250)
    AUTO_SAVE_INTERVAL = 60000
    ANIMATION_DURATION_NORMAL = 300


    def load_icon(name):
        return QIcon()

# Logger
logger = logging.getLogger(__name__)


# ========== ENUMS ==========

class NoteColor(Enum):
    """Predefined note colors"""
    YELLOW = "#FFEB3B"
    PINK = "#F48FB1"
    BLUE = "#64B5F6"
    GREEN = "#81C784"
    ORANGE = "#FFB74D"
    PURPLE = "#BA68C8"
    RED = "#E57373"
    GRAY = "#90A4AE"
    WHITE = "#FFFFFF"
    CUSTOM = "custom"


class NoteStyle(Enum):
    """Note visual styles"""
    CLASSIC = "classic"  # Traditional sticky note
    MODERN = "modern"  # Clean modern design
    GLASS = "glass"  # Transparent glass effect
    PAPER = "paper"  # Paper texture
    MINIMAL = "minimal"  # Minimal design


# ========== NOTE DATA ==========

class NoteData:
    """Data structure for a note"""

    def __init__(self, note_id: str = None):
        self.id = note_id or str(uuid.uuid4())
        self.title = "Ghi chú"
        self.content = ""
        self.html_content = ""
        self.color = NoteColor.YELLOW
        self.custom_color = None
        self.position = QPoint(100, 100)
        self.size = NOTE_WIDGET_SIZE
        self.font_family = "Segoe UI"
        self.font_size = 11
        self.is_bold = False
        self.is_italic = False
        self.is_pinned = False
        self.is_minimized = False
        self.opacity = 1.0
        self.created_at = datetime.now()
        self.modified_at = datetime.now()
        self.tags = []

    def to_dict(self) -> dict:
        """Convert to dictionary for saving"""
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'html_content': self.html_content,
            'color': self.color.value if isinstance(self.color, NoteColor) else self.color,
            'custom_color': self.custom_color,
            'position': {'x': self.position.x(), 'y': self.position.y()},
            'size': {'width': self.size.width(), 'height': self.size.height()},
            'font_family': self.font_family,
            'font_size': self.font_size,
            'is_bold': self.is_bold,
            'is_italic': self.is_italic,
            'is_pinned': self.is_pinned,
            'is_minimized': self.is_minimized,
            'opacity': self.opacity,
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat(),
            'tags': self.tags
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'NoteData':
        """Create from dictionary"""
        note = cls(data.get('id'))
        note.title = data.get('title', 'Ghi chú')
        note.content = data.get('content', '')
        note.html_content = data.get('html_content', '')

        # Color
        color_value = data.get('color', NoteColor.YELLOW.value)
        note.color = NoteColor.YELLOW
        for c in NoteColor:
            if c.value == color_value:
                note.color = c
                break

        note.custom_color = data.get('custom_color')

        # Position and size
        pos = data.get('position', {'x': 100, 'y': 100})
        note.position = QPoint(pos['x'], pos['y'])

        size = data.get('size', {'width': 200, 'height': 250})
        note.size = QSize(size['width'], size['height'])

        # Font
        note.font_family = data.get('font_family', 'Segoe UI')
        note.font_size = data.get('font_size', 11)
        note.is_bold = data.get('is_bold', False)
        note.is_italic = data.get('is_italic', False)

        # State
        note.is_pinned = data.get('is_pinned', False)
        note.is_minimized = data.get('is_minimized', False)
        note.opacity = data.get('opacity', 1.0)

        # Dates
        if 'created_at' in data:
            note.created_at = datetime.fromisoformat(data['created_at'])
        if 'modified_at' in data:
            note.modified_at = datetime.fromisoformat(data['modified_at'])

        note.tags = data.get('tags', [])

        return note


# ========== TITLE BAR ==========

class NoteTitleBar(QFrame):
    """Custom title bar for note"""

    # Signals
    minimize_clicked = Signal()
    close_clicked = Signal()
    menu_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedHeight(30)
        self.setObjectName("NoteTitleBar")

        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)

        # Title label
        self.title_label = QLabel("Ghi chú")
        self.title_label.setObjectName("NoteTitleLabel")
        font = self.title_label.font()
        font.setPointSize(10)
        font.setBold(True)
        self.title_label.setFont(font)
        layout.addWidget(self.title_label)

        layout.addStretch()

        # Pin indicator
        self.pin_indicator = QLabel("📌")
        self.pin_indicator.setVisible(False)
        layout.addWidget(self.pin_indicator)

        # Menu button
        self.menu_btn = QToolButton()
        self.menu_btn.setObjectName("NoteMenuButton")
        self.menu_btn.setText("☰")
        self.menu_btn.setFixedSize(20, 20)
        self.menu_btn.setCursor(Qt.PointingHandCursor)
        self.menu_btn.clicked.connect(self.menu_clicked.emit)
        layout.addWidget(self.menu_btn)

        # Minimize button
        self.minimize_btn = QToolButton()
        self.minimize_btn.setObjectName("NoteMinimizeButton")
        self.minimize_btn.setText("─")
        self.minimize_btn.setFixedSize(20, 20)
        self.minimize_btn.setCursor(Qt.PointingHandCursor)
        self.minimize_btn.clicked.connect(self.minimize_clicked.emit)
        layout.addWidget(self.minimize_btn)

        # Close button
        self.close_btn = QToolButton()
        self.close_btn.setObjectName("NoteCloseButton")
        self.close_btn.setText("×")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.close_clicked.emit)
        layout.addWidget(self.close_btn)

        # For dragging
        self.drag_start_pos = None

    def set_title(self, title: str):
        """Set title text"""
        self.title_label.setText(title)

    def set_pinned(self, pinned: bool):
        """Show/hide pin indicator"""
        self.pin_indicator.setVisible(pinned)

    def mousePressEvent(self, event: QMouseEvent):
        """Start dragging"""
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.globalPos() - self.parent().frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Drag window"""
        if event.buttons() == Qt.LeftButton and self.drag_start_pos:
            self.parent().move(event.globalPos() - self.drag_start_pos)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Stop dragging"""
        self.drag_start_pos = None

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Toggle minimize on double click"""
        if event.button() == Qt.LeftButton:
            self.minimize_clicked.emit()


# ========== MAIN NOTE WIDGET ==========

class QuickNoteWidget(QFrame):
    """
    Single sticky note widget
    """

    # Signals
    note_changed = Signal(str)  # note_id
    note_closed = Signal(str)  # note_id
    note_focused = Signal(str)  # note_id
    position_changed = Signal(str, QPoint)  # note_id, position

    def __init__(self, data: NoteData = None, style: NoteStyle = NoteStyle.CLASSIC, parent=None):
        super().__init__(parent)

        # Data
        self.data = data or NoteData()
        self.style = style
        self.is_editing = False
        self.is_minimized = False

        # Auto-save timer
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.setInterval(5000)  # 5 seconds

        # Animation
        self.show_animation = None
        self.hide_animation = None

        # Setup UI
        self.setup_ui()

        # Load data
        self.load_data()

        # Setup window flags
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Install event filter
        self.installEventFilter(self)

    def setup_ui(self):
        """Setup UI components"""
        self.setObjectName("QuickNoteWidget")

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title bar
        self.title_bar = NoteTitleBar()
        self.title_bar.minimize_clicked.connect(self.toggle_minimize)
        self.title_bar.close_clicked.connect(self.close_note)
        self.title_bar.menu_clicked.connect(self.show_menu)
        main_layout.addWidget(self.title_bar)

        # Content container
        self.content_container = QFrame()
        self.content_container.setObjectName("NoteContent")
        content_layout = QVBoxLayout(self.content_container)
        content_layout.setContentsMargins(8, 8, 8, 8)

        # Text editor
        self.text_edit = QTextEdit()
        self.text_edit.setObjectName("NoteTextEdit")
        self.text_edit.setAcceptRichText(True)
        self.text_edit.textChanged.connect(self.on_text_changed)
        content_layout.addWidget(self.text_edit)

        # Size grip for resizing
        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(16, 16)

        main_layout.addWidget(self.content_container)

        # Apply style
        self.apply_style()

        # Set initial size and position
        self.resize(self.data.size)
        self.move(self.data.position)

    def apply_style(self):
        """Apply visual style based on note color and style"""
        color = self.get_current_color()

        if self.style == NoteStyle.CLASSIC:
            # Classic sticky note style
            self.setStyleSheet(f"""
                #QuickNoteWidget {{
                    background: transparent;
                }}
                #NoteTitleBar {{
                    background: {color};
                    border: 1px solid {QColor(color).darker(120).name()};
                    border-bottom: none;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                }}
                #NoteTitleLabel {{
                    color: {self.get_text_color(color)};
                }}
                #NoteMenuButton, #NoteMinimizeButton, #NoteCloseButton {{
                    background: transparent;
                    border: none;
                    color: {self.get_text_color(color)};
                    font-weight: bold;
                }}
                #NoteMenuButton:hover, #NoteMinimizeButton:hover, #NoteCloseButton:hover {{
                    background: rgba(255, 255, 255, 50);
                    border-radius: 2px;
                }}
                #NoteContent {{
                    background: {color};
                    border: 1px solid {QColor(color).darker(120).name()};
                    border-top: none;
                    border-bottom-left-radius: 4px;
                    border-bottom-right-radius: 4px;
                }}
                #NoteTextEdit {{
                    background: transparent;
                    border: none;
                    color: {self.get_text_color(color)};
                    font-family: {self.data.font_family};
                    font-size: {self.data.font_size}pt;
                }}
            """)

            # Add shadow
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(10)
            shadow.setColor(QColor(0, 0, 0, 80))
            shadow.setOffset(2, 2)
            self.setGraphicsEffect(shadow)

        elif self.style == NoteStyle.MODERN:
            # Modern clean style
            self.setStyleSheet(f"""
                #QuickNoteWidget {{
                    background: white;
                    border: 1px solid #e0e0e0;
                    border-radius: 8px;
                }}
                #NoteTitleBar {{
                    background: {color};
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                }}
                #NoteContent {{
                    background: white;
                    border-bottom-left-radius: 8px;
                    border-bottom-right-radius: 8px;
                }}
                #NoteTextEdit {{
                    background: transparent;
                    border: none;
                    color: #333333;
                    font-family: {self.data.font_family};
                    font-size: {self.data.font_size}pt;
                }}
            """)

        elif self.style == NoteStyle.GLASS:
            # Glass transparent style
            self.setStyleSheet(f"""
                #QuickNoteWidget {{
                    background: rgba(255, 255, 255, 200);
                    border: 1px solid rgba(255, 255, 255, 100);
                    border-radius: 12px;
                }}
                #NoteTitleBar {{
                    background: {QColor(color).name()}40;
                    border-top-left-radius: 12px;
                    border-top-right-radius: 12px;
                }}
                #NoteContent {{
                    background: rgba(255, 255, 255, 150);
                    border-bottom-left-radius: 12px;
                    border-bottom-right-radius: 12px;
                }}
                #NoteTextEdit {{
                    background: transparent;
                    border: none;
                    color: #333333;
                }}
            """)

        elif self.style == NoteStyle.MINIMAL:
            # Minimal style
            self.setStyleSheet(f"""
                #QuickNoteWidget {{
                    background: {color};
                    border: none;
                }}
                #NoteTitleBar {{
                    background: transparent;
                    border-bottom: 1px solid {QColor(color).darker(110).name()};
                }}
                #NoteContent {{
                    background: transparent;
                }}
                #NoteTextEdit {{
                    background: transparent;
                    border: none;
                    color: {self.get_text_color(color)};
                }}
            """)

    def get_current_color(self) -> str:
        """Get current note color"""
        if self.data.color == NoteColor.CUSTOM and self.data.custom_color:
            return self.data.custom_color
        return self.data.color.value if isinstance(self.data.color, NoteColor) else self.data.color

    def get_text_color(self, bg_color: str) -> str:
        """Get appropriate text color for background"""
        color = QColor(bg_color)
        # Use black text for light backgrounds, white for dark
        if color.lightness() > 128:
            return "#000000"
        return "#FFFFFF"

    def load_data(self):
        """Load note data into UI"""
        self.title_bar.set_title(self.data.title)
        self.title_bar.set_pinned(self.data.is_pinned)

        # Set content
        if self.data.html_content:
            self.text_edit.setHtml(self.data.html_content)
        else:
            self.text_edit.setPlainText(self.data.content)

        # Set font
        font = QFont(self.data.font_family, self.data.font_size)
        font.setBold(self.data.is_bold)
        font.setItalic(self.data.is_italic)
        self.text_edit.setFont(font)

        # Set opacity
        self.setWindowOpacity(self.data.opacity)

        # Position and size
        self.move(self.data.position)
        self.resize(self.data.size)

    def save_data(self):
        """Save current state to data"""
        self.data.content = self.text_edit.toPlainText()
        self.data.html_content = self.text_edit.toHtml()
        self.data.position = self.pos()
        self.data.size = self.size()
        self.data.modified_at = datetime.now()

    def on_text_changed(self):
        """Handle text change"""
        if not self.is_editing:
            self.is_editing = True
            self.auto_save_timer.start()

        # Update title from first line
        text = self.text_edit.toPlainText()
        if text:
            first_line = text.split('\n')[0][:30]
            if first_line:
                self.data.title = first_line
                self.title_bar.set_title(first_line)

    def auto_save(self):
        """Auto save note"""
        self.save_data()
        self.note_changed.emit(self.data.id)
        self.is_editing = False
        self.auto_save_timer.stop()
        logger.debug(f"Auto-saved note: {self.data.id}")

    def toggle_minimize(self):
        """Toggle minimize state"""
        if self.is_minimized:
            # Restore
            self.content_container.show()
            self.resize(self.data.size)
            self.is_minimized = False
        else:
            # Minimize
            self.data.size = self.size()  # Save current size
            self.content_container.hide()
            self.resize(self.width(), 30)  # Only title bar height
            self.is_minimized = True

    def close_note(self):
        """Close and delete note"""
        reply = QMessageBox.question(
            self,
            "Xóa ghi chú",
            "Bạn có chắc chắn muốn xóa ghi chú này?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.save_data()
            self.note_closed.emit(self.data.id)
            self.close()
            self.deleteLater()

    def show_menu(self):
        """Show context menu"""
        menu = QMenu(self)

        # Color submenu
        color_menu = menu.addMenu("🎨 Màu sắc")
        for color in NoteColor:
            if color != NoteColor.CUSTOM:
                action = QAction(color.name.title(), color_menu)
                action.triggered.connect(lambda checked, c=color: self.set_color(c))
                color_menu.addAction(action)

        color_menu.addSeparator()
        custom_action = QAction("Tùy chỉnh...", color_menu)
        custom_action.triggered.connect(self.choose_custom_color)
        color_menu.addAction(custom_action)

        # Font menu
        font_action = QAction("🔤 Phông chữ...", menu)
        font_action.triggered.connect(self.choose_font)
        menu.addAction(font_action)

        menu.addSeparator()

        # Pin/Unpin
        pin_action = QAction("📌 Ghim" if not self.data.is_pinned else "📌 Bỏ ghim", menu)
        pin_action.triggered.connect(self.toggle_pin)
        menu.addAction(pin_action)

        # Always on top
        on_top_action = QAction("👁 Luôn hiển thị trên cùng", menu)
        on_top_action.setCheckable(True)
        on_top_action.setChecked(bool(self.windowFlags() & Qt.WindowStaysOnTopHint))
        on_top_action.triggered.connect(self.toggle_always_on_top)
        menu.addAction(on_top_action)

        menu.addSeparator()

        # Opacity submenu
        opacity_menu = menu.addMenu("👻 Độ trong suốt")
        for value in [100, 90, 80, 70, 60, 50]:
            action = QAction(f"{value}%", opacity_menu)
            action.triggered.connect(lambda checked, v=value: self.set_opacity(v / 100))
            opacity_menu.addAction(action)

        menu.addSeparator()

        # Duplicate
        duplicate_action = QAction("📋 Nhân bản", menu)
        duplicate_action.triggered.connect(lambda: self.duplicate_requested.emit(self.data.id))
        menu.addAction(duplicate_action)

        # Delete
        delete_action = QAction("🗑 Xóa", menu)
        delete_action.triggered.connect(self.close_note)
        menu.addAction(delete_action)

        menu.exec_(QCursor.pos())

    def set_color(self, color: NoteColor):
        """Set note color"""
        self.data.color = color
        self.apply_style()
        self.save_data()
        self.note_changed.emit(self.data.id)

    def choose_custom_color(self):
        """Choose custom color"""
        color = QColorDialog.getColor(QColor(self.get_current_color()), self, "Chọn màu")
        if color.isValid():
            self.data.color = NoteColor.CUSTOM
            self.data.custom_color = color.name()
            self.apply_style()
            self.save_data()
            self.note_changed.emit(self.data.id)

    def choose_font(self):
        """Choose font"""
        font, ok = QFontDialog.getFont(self.text_edit.font(), self, "Chọn phông chữ")
        if ok:
            self.data.font_family = font.family()
            self.data.font_size = font.pointSize()
            self.data.is_bold = font.bold()
            self.data.is_italic = font.italic()
            self.text_edit.setFont(font)
            self.save_data()
            self.note_changed.emit(self.data.id)

    def toggle_pin(self):
        """Toggle pin state"""
        self.data.is_pinned = not self.data.is_pinned
        self.title_bar.set_pinned(self.data.is_pinned)
        self.save_data()
        self.note_changed.emit(self.data.id)

    def toggle_always_on_top(self, checked: bool):
        """Toggle always on top"""
        flags = self.windowFlags()
        if checked:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def set_opacity(self, value: float):
        """Set window opacity"""
        self.data.opacity = value
        self.setWindowOpacity(value)
        self.save_data()
        self.note_changed.emit(self.data.id)

    # ========== EVENTS ==========

    def eventFilter(self, obj, event: QEvent) -> bool:
        """Event filter"""
        if event.type() == QEvent.WindowActivate:
            self.note_focused.emit(self.data.id)
        return super().eventFilter(obj, event)

    def moveEvent(self, event):
        """Handle move event"""
        super().moveEvent(event)
        self.data.position = self.pos()
        self.position_changed.emit(self.data.id, self.pos())

    def resizeEvent(self, event: QResizeEvent):
        """Handle resize event"""
        super().resizeEvent(event)
        if not self.is_minimized:
            self.data.size = self.size()

        # Position size grip
        self.size_grip.move(self.width() - 16, self.height() - 16)

    def closeEvent(self, event):
        """Handle close event"""
        self.save_data()
        super().closeEvent(event)

    # Additional signals
    duplicate_requested = Signal(str)  # note_id


# ========== NOTES MANAGER ==========

class QuickNotesManager(QWidget):
    """
    Manager for all sticky notes
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Storage
        self.notes: Dict[str, QuickNoteWidget] = {}
        self.notes_data: Dict[str, NoteData] = {}

        # Settings
        self.settings = QSettings("TutorApp", "QuickNotes")
        self.save_path = Path.home() / ".tutor_app" / "notes.json"
        self.save_path.parent.mkdir(parents=True, exist_ok=True)

        # Auto-save timer
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.save_all_notes)
        self.auto_save_timer.setInterval(AUTO_SAVE_INTERVAL)
        self.auto_save_timer.start()

        # Load existing notes
        self.load_all_notes()

        # Hide manager widget
        self.hide()

    def create_note(self,
                    title: str = "Ghi chú mới",
                    content: str = "",
                    color: NoteColor = NoteColor.YELLOW,
                    position: QPoint = None) -> str:
        """Create new note"""
        # Create data
        data = NoteData()
        data.title = title
        data.content = content
        data.color = color

        if position:
            data.position = position
        else:
            # Cascade position
            offset = len(self.notes) * 30
            data.position = QPoint(100 + offset, 100 + offset)

        # Create widget
        note_widget = QuickNoteWidget(data)

        # Connect signals
        note_widget.note_changed.connect(self.on_note_changed)
        note_widget.note_closed.connect(self.on_note_closed)
        note_widget.note_focused.connect(self.on_note_focused)
        note_widget.duplicate_requested.connect(self.duplicate_note)

        # Store
        self.notes[data.id] = note_widget
        self.notes_data[data.id] = data

        # Show
        note_widget.show()

        # Animate entrance
        self.animate_note_entrance(note_widget)

        # Save
        self.save_all_notes()

        logger.info(f"Created note: {data.id}")
        return data.id

    def duplicate_note(self, note_id: str):
        """Duplicate an existing note"""
        if note_id in self.notes_data:
            original = self.notes_data[note_id]

            # Create copy with offset position
            self.create_note(
                title=f"{original.title} (Copy)",
                content=original.content,
                color=original.color,
                position=original.position + QPoint(30, 30)
            )

    def delete_note(self, note_id: str):
        """Delete a note"""
        if note_id in self.notes:
            widget = self.notes[note_id]
            widget.close()
            widget.deleteLater()
            del self.notes[note_id]

        if note_id in self.notes_data:
            del self.notes_data[note_id]

        self.save_all_notes()
        logger.info(f"Deleted note: {note_id}")

    def on_note_changed(self, note_id: str):
        """Handle note change"""
        if note_id in self.notes:
            widget = self.notes[note_id]
            widget.save_data()
            self.notes_data[note_id] = widget.data

    def on_note_closed(self, note_id: str):
        """Handle note close"""
        self.delete_note(note_id)

    def on_note_focused(self, note_id: str):
        """Handle note focus - bring to front"""
        if note_id in self.notes:
            self.notes[note_id].raise_()

    def animate_note_entrance(self, note_widget: QuickNoteWidget):
        """Animate note appearance"""
        # Fade in effect
        effect = QGraphicsOpacityEffect()
        note_widget.setGraphicsEffect(effect)

        animation = QPropertyAnimation(effect, b"opacity")
        animation.setDuration(ANIMATION_DURATION_NORMAL)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.finished.connect(lambda: note_widget.setGraphicsEffect(None))
        animation.start()

    def save_all_notes(self):
        """Save all notes to file"""
        try:
            notes_list = []
            for note_id, data in self.notes_data.items():
                if note_id in self.notes:
                    # Update data from widget
                    self.notes[note_id].save_data()
                    notes_list.append(self.notes[note_id].data.to_dict())
                else:
                    notes_list.append(data.to_dict())

            with open(self.save_path, 'w', encoding='utf-8') as f:
                json.dump(notes_list, f, indent=2, ensure_ascii=False)

            logger.debug(f"Saved {len(notes_list)} notes")
        except Exception as e:
            logger.error(f"Error saving notes: {e}")

    def load_all_notes(self):
        """Load all notes from file"""
        if not self.save_path.exists():
            return

        try:
            with open(self.save_path, 'r', encoding='utf-8') as f:
                notes_list = json.load(f)

            for note_dict in notes_list:
                data = NoteData.from_dict(note_dict)

                # Create widget
                note_widget = QuickNoteWidget(data)

                # Connect signals
                note_widget.note_changed.connect(self.on_note_changed)
                note_widget.note_closed.connect(self.on_note_closed)
                note_widget.note_focused.connect(self.on_note_focused)
                note_widget.duplicate_requested.connect(self.duplicate_note)

                # Store
                self.notes[data.id] = note_widget
                self.notes_data[data.id] = data

                # Show if not minimized
                if not data.is_minimized:
                    note_widget.show()

            logger.info(f"Loaded {len(self.notes)} notes")
        except Exception as e:
            logger.error(f"Error loading notes: {e}")

    def show_all_notes(self):
        """Show all notes"""
        for widget in self.notes.values():
            widget.show()
            widget.raise_()

    def hide_all_notes(self):
        """Hide all notes"""
        for widget in self.notes.values():
            widget.hide()

    def arrange_notes(self, arrangement: str = "cascade"):
        """Arrange all notes"""
        if arrangement == "cascade":
            offset = 0
            for widget in self.notes.values():
                widget.move(100 + offset, 100 + offset)
                offset += 30

        elif arrangement == "grid":
            cols = 3
            col = 0
            row = 0
            for widget in self.notes.values():
                x = 100 + col * (widget.width() + 20)
                y = 100 + row * (widget.height() + 20)
                widget.move(x, y)

                col += 1
                if col >= cols:
                    col = 0
                    row += 1

    def get_notes_count(self) -> int:
        """Get number of notes"""
        return len(self.notes)

    def clear_all_notes(self):
        """Delete all notes"""
        reply = QMessageBox.question(
            None,
            "Xóa tất cả ghi chú",
            "Bạn có chắc chắn muốn xóa TẤT CẢ ghi chú?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            for note_id in list(self.notes.keys()):
                self.delete_note(note_id)


# ========== CONVENIENCE FUNCTIONS ==========

# Global manager instance
_notes_manager = None


def get_notes_manager() -> QuickNotesManager:
    """Get or create global notes manager"""
    global _notes_manager
    if _notes_manager is None:
        _notes_manager = QuickNotesManager()
    return _notes_manager


def create_quick_note(title: str = "Ghi chú mới",
                      content: str = "",
                      color: NoteColor = NoteColor.YELLOW,
                      position: QPoint = None) -> str:
    """Create a quick note using global manager"""
    manager = get_notes_manager()
    return manager.create_note(title, content, color, position)


def show_all_notes():
    """Show all notes"""
    manager = get_notes_manager()
    manager.show_all_notes()


def hide_all_notes():
    """Hide all notes"""
    manager = get_notes_manager()
    manager.hide_all_notes()


# ========== EXAMPLE USAGE ==========

if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    # Create notes manager
    manager = QuickNotesManager()

    # Create sample notes
    manager.create_note(
        "Danh sách việc cần làm",
        "✅ Chấm bài tập\n📚 Chuẩn bị bài giảng\n📝 Họp phụ huynh",
        NoteColor.YELLOW
    )

    manager.create_note(
        "Ghi nhớ",
        "Họp lúc 14:00\nGọi cho phụ huynh học sinh A",
        NoteColor.PINK,
        QPoint(350, 150)
    )

    manager.create_note(
        "Ý tưởng bài giảng",
        "- Sử dụng video minh họa\n- Thêm bài tập nhóm\n- Kiểm tra 15 phút",
        NoteColor.GREEN,
        QPoint(600, 200)
    )

    sys.exit(app.exec())