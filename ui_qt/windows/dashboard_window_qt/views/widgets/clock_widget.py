# ui_qt/windows/dashboard_window_qt/views/widgets/clock_widget.py
"""
Clock Widget - Đồng hồ desktop với nhiều chế độ hiển thị
Hỗ trợ: Analog, Digital, Calendar, Timezone, Alarms
"""

import math
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Tuple
from enum import Enum
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QMenu, QCalendarWidget, QTimeEdit, QComboBox,
    QListWidget, QListWidgetItem, QPushButton, QDialog,
    QDialogButtonBox, QMessageBox, QGraphicsDropShadowEffect,
    QFrame, QGridLayout, QSpinBox, QCheckBox,QLineEdit
)
from PySide6.QtCore import (
    Qt, QTimer, QTime, QDate, QDateTime, QTimeZone,
    QPoint, QRect, QSize, QRectF, QPointF,
    Signal, Property, QPropertyAnimation, QEasingCurve,
    QEvent, QSettings, QLocale
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont,
    QLinearGradient, QRadialGradient, QConicalGradient,
    QPainterPath, QPolygonF, QFontMetrics,
    QMouseEvent, QPaintEvent, QResizeEvent,
    QContextMenuEvent, QWheelEvent, QPixmap, QIcon, QAction
)

# Import utils
try:
    from ...utils.constants import DESKTOP_ICON_SIZE
    from ...utils.assets import load_icon
except ImportError:
    DESKTOP_ICON_SIZE = 64


    def load_icon(name):
        return QIcon()

# Logger
logger = logging.getLogger(__name__)


# ========== ENUMS ==========

class ClockMode(Enum):
    """Clock display modes"""
    ANALOG = "analog"
    DIGITAL = "digital"
    BOTH = "both"
    MINIMAL = "minimal"


class ClockStyle(Enum):
    """Clock visual styles"""
    CLASSIC = "classic"
    MODERN = "modern"
    NEON = "neon"
    GLASS = "glass"
    DARK = "dark"


# ========== ANALOG CLOCK ==========

class AnalogClock(QWidget):
    """Đồng hồ kim analog với style hiện đại"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Clock settings
        self.show_seconds = True
        self.show_numbers = True
        self.show_date = False
        self.clock_style = ClockStyle.MODERN

        # Colors
        self.bg_color = QColor(30, 30, 40, 200)
        self.border_color = QColor(100, 100, 120)
        self.hour_color = QColor(255, 255, 255)
        self.minute_color = QColor(200, 200, 220)
        self.second_color = QColor(255, 100, 100)
        self.text_color = QColor(200, 200, 220)

        # Size
        self.setMinimumSize(150, 150)

        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(1000)  # Update every second

        # Enable antialiasing
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, event):
        """Draw analog clock"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Get dimensions
        size = min(self.width(), self.height())
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = size / 2 - 10

        # Draw based on style
        if self.clock_style == ClockStyle.MODERN:
            self._draw_modern_clock(painter, center, radius)
        elif self.clock_style == ClockStyle.GLASS:
            self._draw_glass_clock(painter, center, radius)
        elif self.clock_style == ClockStyle.NEON:
            self._draw_neon_clock(painter, center, radius)
        else:
            self._draw_classic_clock(painter, center, radius)

    def _draw_modern_clock(self, painter: QPainter, center: QPointF, radius: float):
        """Draw modern style clock"""
        # Background with gradient
        gradient = QRadialGradient(center, radius)
        gradient.setColorAt(0, QColor(50, 50, 60, 220))
        gradient.setColorAt(1, QColor(20, 20, 30, 250))
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(self.border_color, 2))
        painter.drawEllipse(center, radius, radius)

        # Draw hour markers
        painter.setPen(QPen(self.text_color, 2))
        for i in range(12):
            angle = math.radians(i * 30 - 90)
            start = QPointF(
                center.x() + math.cos(angle) * (radius - 15),
                center.y() + math.sin(angle) * (radius - 15)
            )
            end = QPointF(
                center.x() + math.cos(angle) * (radius - 5),
                center.y() + math.sin(angle) * (radius - 5)
            )
            painter.drawLine(start, end)

            # Draw numbers
            if self.show_numbers:
                num = 12 if i == 0 else i
                text_pos = QPointF(
                    center.x() + math.cos(angle) * (radius - 30),
                    center.y() + math.sin(angle) * (radius - 30)
                )
                painter.setFont(QFont("Arial", 10, QFont.Bold))
                painter.drawText(
                    QRectF(text_pos.x() - 15, text_pos.y() - 10, 30, 20),
                    Qt.AlignCenter,
                    str(num)
                )

        # Get current time
        current_time = QTime.currentTime()

        # Draw hour hand
        hour_angle = math.radians((current_time.hour() % 12) * 30 +
                                  current_time.minute() * 0.5 - 90)
        painter.setPen(QPen(self.hour_color, 4, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(
            center,
            QPointF(
                center.x() + math.cos(hour_angle) * (radius * 0.5),
                center.y() + math.sin(hour_angle) * (radius * 0.5)
            )
        )

        # Draw minute hand
        minute_angle = math.radians(current_time.minute() * 6 - 90)
        painter.setPen(QPen(self.minute_color, 3, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(
            center,
            QPointF(
                center.x() + math.cos(minute_angle) * (radius * 0.7),
                center.y() + math.sin(minute_angle) * (radius * 0.7)
            )
        )

        # Draw second hand
        if self.show_seconds:
            second_angle = math.radians(current_time.second() * 6 - 90)
            painter.setPen(QPen(self.second_color, 2, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(
                center,
                QPointF(
                    center.x() + math.cos(second_angle) * (radius * 0.8),
                    center.y() + math.sin(second_angle) * (radius * 0.8)
                )
            )

        # Center dot
        painter.setBrush(QBrush(self.hour_color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, 5, 5)

        # Draw date if enabled
        if self.show_date:
            painter.setPen(QPen(self.text_color, 1))
            painter.setFont(QFont("Arial", 9))
            date_str = QDate.currentDate().toString("dd/MM")
            painter.drawText(
                QRectF(center.x() - 30, center.y() + radius * 0.3, 60, 20),
                Qt.AlignCenter,
                date_str
            )

    def _draw_glass_clock(self, painter: QPainter, center: QPointF, radius: float):
        """Draw glass effect clock"""
        # Glass background
        gradient = QRadialGradient(center, radius)
        gradient.setColorAt(0, QColor(255, 255, 255, 30))
        gradient.setColorAt(0.5, QColor(100, 100, 120, 60))
        gradient.setColorAt(1, QColor(20, 20, 30, 100))
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(200, 200, 220, 150), 1))
        painter.drawEllipse(center, radius, radius)

        # Glass reflection
        reflection = QRadialGradient(
            QPointF(center.x() - radius * 0.3, center.y() - radius * 0.3),
            radius * 0.7
        )
        reflection.setColorAt(0, QColor(255, 255, 255, 100))
        reflection.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(reflection))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, radius * 0.95, radius * 0.95)

        # Continue with clock hands...
        self._draw_clock_hands(painter, center, radius)

    def _draw_neon_clock(self, painter: QPainter, center: QPointF, radius: float):
        """Draw neon glow effect clock"""
        # Dark background
        painter.setBrush(QBrush(QColor(10, 10, 20)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, radius, radius)

        # Neon border
        pen = QPen(QColor(0, 200, 255, 200), 3)
        pen.setStyle(Qt.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center, radius - 3, radius - 3)

        # Neon glow effect
        for i in range(3):
            pen = QPen(QColor(0, 150, 255, 100 - i * 30), 6 + i * 3)
            painter.setPen(pen)
            painter.drawEllipse(center, radius - 3, radius - 3)

        # Draw glowing hands
        self._draw_clock_hands(painter, center, radius, neon=True)

    def _draw_classic_clock(self, painter: QPainter, center: QPointF, radius: float):
        """Draw classic style clock"""
        # White background
        painter.setBrush(QBrush(QColor(250, 250, 250)))
        painter.setPen(QPen(QColor(50, 50, 50), 2))
        painter.drawEllipse(center, radius, radius)

        # Roman numerals or numbers
        painter.setPen(QPen(QColor(30, 30, 30), 1))
        painter.setFont(QFont("Times New Roman", 12))

        roman = ["XII", "I", "II", "III", "IV", "V",
                 "VI", "VII", "VIII", "IX", "X", "XI"]

        for i in range(12):
            angle = math.radians(i * 30 - 90)
            text_pos = QPointF(
                center.x() + math.cos(angle) * (radius - 25),
                center.y() + math.sin(angle) * (radius - 25)
            )
            painter.drawText(
                QRectF(text_pos.x() - 20, text_pos.y() - 10, 40, 20),
                Qt.AlignCenter,
                roman[i]
            )

        # Classic hands
        self._draw_clock_hands(painter, center, radius, classic=True)

    def _draw_clock_hands(self, painter: QPainter, center: QPointF,
                          radius: float, neon=False, classic=False):
        """Draw clock hands"""
        current_time = QTime.currentTime()

        # Hour hand
        hour_angle = math.radians((current_time.hour() % 12) * 30 +
                                  current_time.minute() * 0.5 - 90)

        if neon:
            # Neon glow effect
            for i in range(3):
                pen = QPen(QColor(255, 100, 100, 150 - i * 40), 6 - i * 2)
                pen.setCapStyle(Qt.RoundCap)
                painter.setPen(pen)
                painter.drawLine(
                    center,
                    QPointF(
                        center.x() + math.cos(hour_angle) * (radius * 0.5),
                        center.y() + math.sin(hour_angle) * (radius * 0.5)
                    )
                )
        else:
            color = QColor(30, 30, 30) if classic else self.hour_color
            painter.setPen(QPen(color, 4, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(
                center,
                QPointF(
                    center.x() + math.cos(hour_angle) * (radius * 0.5),
                    center.y() + math.sin(hour_angle) * (radius * 0.5)
                )
            )

        # Minute hand
        minute_angle = math.radians(current_time.minute() * 6 - 90)

        if neon:
            for i in range(3):
                pen = QPen(QColor(100, 255, 100, 150 - i * 40), 4 - i)
                pen.setCapStyle(Qt.RoundCap)
                painter.setPen(pen)
                painter.drawLine(
                    center,
                    QPointF(
                        center.x() + math.cos(minute_angle) * (radius * 0.7),
                        center.y() + math.sin(minute_angle) * (radius * 0.7)
                    )
                )
        else:
            color = QColor(30, 30, 30) if classic else self.minute_color
            painter.setPen(QPen(color, 3, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(
                center,
                QPointF(
                    center.x() + math.cos(minute_angle) * (radius * 0.7),
                    center.y() + math.sin(minute_angle) * (radius * 0.7)
                )
            )

        # Second hand
        if self.show_seconds:
            second_angle = math.radians(current_time.second() * 6 - 90)

            if neon:
                for i in range(3):
                    pen = QPen(QColor(255, 255, 100, 150 - i * 40), 3 - i)
                    pen.setCapStyle(Qt.RoundCap)
                    painter.setPen(pen)
                    painter.drawLine(
                        center,
                        QPointF(
                            center.x() + math.cos(second_angle) * (radius * 0.8),
                            center.y() + math.sin(second_angle) * (radius * 0.8)
                        )
                    )
            else:
                color = QColor(255, 0, 0) if classic else self.second_color
                painter.setPen(QPen(color, 2 if classic else 1,
                                    Qt.SolidLine, Qt.RoundCap))
                painter.drawLine(
                    center,
                    QPointF(
                        center.x() + math.cos(second_angle) * (radius * 0.8),
                        center.y() + math.sin(second_angle) * (radius * 0.8)
                    )
                )

        # Center dot
        if neon:
            painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
        else:
            painter.setBrush(QBrush(QColor(30, 30, 30) if classic else self.hour_color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, 4, 4)


# ========== DIGITAL CLOCK ==========

class DigitalClock(QLabel):
    """Đồng hồ số với nhiều định dạng"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Settings
        self.time_format = "hh:mm:ss"  # 24h format
        self.show_date = True
        self.show_seconds = True
        self.show_ampm = False

        # Style
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(30, 30, 40, 200),
                    stop:1 rgba(50, 50, 60, 200));
                color: #00ff00;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 24px;
                font-weight: bold;
                padding: 10px;
                border: 2px solid rgba(100, 100, 120, 150);
                border-radius: 10px;
            }
        """)

        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)

        # Initial update
        self.update_time()

        # Add shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 255, 0, 100))
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)

    def update_time(self):
        """Update time display"""
        now = QDateTime.currentDateTime()

        # Format time
        if self.show_ampm:
            time_format = "hh:mm" if not self.show_seconds else "hh:mm:ss"
            time_str = now.toString(time_format + " AP")
        else:
            time_format = "HH:mm" if not self.show_seconds else "HH:mm:ss"
            time_str = now.toString(time_format)

        # Add date if enabled
        if self.show_date:
            date_str = now.toString("dd/MM/yyyy")
            display_text = f"{time_str}\n{date_str}"
        else:
            display_text = time_str

        self.setText(display_text)

    def set_time_format(self, format_24h: bool):
        """Toggle 12/24 hour format"""
        self.show_ampm = not format_24h
        self.update_time()

    def set_style(self, style: str):
        """Change digital clock style"""
        styles = {
            "lcd": """
                background: #000000;
                color: #00ff00;
                font-family: 'LCD', 'Digital-7', monospace;
                font-size: 32px;
                padding: 15px;
                border: 3px solid #00ff00;
            """,
            "neon": """
                background: rgba(10, 10, 20, 230);
                color: #00ffff;
                font-family: 'Arial Black';
                font-size: 28px;
                text-shadow: 0 0 10px #00ffff;
                padding: 12px;
                border: 2px solid #00ffff;
                border-radius: 15px;
            """,
            "minimal": """
                background: transparent;
                color: white;
                font-family: 'Segoe UI Light';
                font-size: 36px;
                padding: 5px;
                border: none;
            """,
            "matrix": """
                background: #000000;
                color: #00ff41;
                font-family: 'Consolas';
                font-size: 24px;
                padding: 10px;
                border: 1px solid #00ff41;
            """
        }

        if style in styles:
            self.setStyleSheet(f"QLabel {{ {styles[style]} }}")


# ========== MAIN CLOCK WIDGET ==========

class ClockWidget(QWidget):
    """
    Main Clock Widget - Kết hợp analog và digital
    Có thể kéo thả, resize, và cấu hình
    """

    # Signals
    alarm_triggered = Signal(str)  # alarm_name
    timezone_changed = Signal(str)  # timezone_name

    def __init__(self, parent=None):
        super().__init__(parent)

        # Widget settings
        self.mode = ClockMode.BOTH
        self.current_timezone = "Local"
        self.alarms = []
        self.is_draggable = True
        self.is_resizable = True

        # Components
        self.analog_clock = None
        self.digital_clock = None
        self.calendar_popup = None

        # Mouse tracking for drag
        self.drag_start_pos = None

        # Settings
        self.settings = QSettings("TutorApp", "ClockWidget")

        # Setup UI
        self.setup_ui()

        # Load saved settings
        self.load_settings()

        # Setup context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def setup_ui(self):
        """Setup UI components"""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Create clocks based on mode
        if self.mode in [ClockMode.ANALOG, ClockMode.BOTH]:
            self.analog_clock = AnalogClock()
            layout.addWidget(self.analog_clock)

        if self.mode in [ClockMode.DIGITAL, ClockMode.BOTH]:
            self.digital_clock = DigitalClock()
            layout.addWidget(self.digital_clock)

        # Set window flags for desktop widget
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Default size
        self.resize(200, 250 if self.mode == ClockMode.BOTH else 200)

    def show_context_menu(self, pos):
        """Show right-click context menu"""
        menu = QMenu(self)

        # Clock mode submenu
        mode_menu = menu.addMenu("🎨 Chế độ hiển thị")

        analog_action = QAction("⏰ Đồng hồ kim", self)
        analog_action.triggered.connect(lambda: self.set_mode(ClockMode.ANALOG))
        mode_menu.addAction(analog_action)

        digital_action = QAction("🔢 Đồng hồ số", self)
        digital_action.triggered.connect(lambda: self.set_mode(ClockMode.DIGITAL))
        mode_menu.addAction(digital_action)

        both_action = QAction("🎯 Cả hai", self)
        both_action.triggered.connect(lambda: self.set_mode(ClockMode.BOTH))
        mode_menu.addAction(both_action)

        menu.addSeparator()

        # Style submenu
        if self.analog_clock:
            style_menu = menu.addMenu("🎨 Phong cách")

            for style in ClockStyle:
                action = QAction(style.value.title(), self)
                action.triggered.connect(
                    lambda checked, s=style: self.set_style(s)
                )
                style_menu.addAction(action)

        menu.addSeparator()

        # Settings
        settings_action = QAction("⚙️ Cài đặt", self)
        settings_action.triggered.connect(self.show_settings_dialog)
        menu.addAction(settings_action)

        # Timezone
        timezone_action = QAction("🌍 Múi giờ", self)
        timezone_action.triggered.connect(self.show_timezone_dialog)
        menu.addAction(timezone_action)

        # Alarms
        alarm_action = QAction("⏰ Báo thức", self)
        alarm_action.triggered.connect(self.show_alarm_dialog)
        menu.addAction(alarm_action)

        menu.addSeparator()

        # Calendar
        calendar_action = QAction("📅 Xem lịch", self)
        calendar_action.triggered.connect(self.show_calendar_popup)
        menu.addAction(calendar_action)

        menu.addSeparator()

        # Always on top toggle
        on_top_action = QAction("📌 Luôn hiển thị trên cùng", self)
        on_top_action.setCheckable(True)
        on_top_action.setChecked(
            bool(self.windowFlags() & Qt.WindowStaysOnTopHint)
        )
        on_top_action.triggered.connect(self.toggle_always_on_top)
        menu.addAction(on_top_action)

        # Close
        close_action = QAction("❌ Đóng", self)
        close_action.triggered.connect(self.close)
        menu.addAction(close_action)

        menu.exec_(self.mapToGlobal(pos))

    def set_mode(self, mode: ClockMode):
        """Change clock display mode"""
        if mode != self.mode:
            self.mode = mode

            # Clear current layout
            while self.layout().count():
                item = self.layout().takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            # Recreate clocks
            if mode in [ClockMode.ANALOG, ClockMode.BOTH]:
                self.analog_clock = AnalogClock()
                self.layout().addWidget(self.analog_clock)

            if mode in [ClockMode.DIGITAL, ClockMode.BOTH]:
                self.digital_clock = DigitalClock()
                self.layout().addWidget(self.digital_clock)

            # Adjust size
            if mode == ClockMode.BOTH:
                self.resize(200, 250)
            else:
                self.resize(200, 200)

            self.save_settings()

    def set_style(self, style: ClockStyle):
        """Change clock style"""
        if self.analog_clock:
            self.analog_clock.clock_style = style
            self.analog_clock.update()
        self.save_settings()

    def show_settings_dialog(self):
        """Show settings dialog"""
        dialog = ClockSettingsDialog(self)
        if dialog.exec_():
            settings = dialog.get_settings()
            self.apply_settings(settings)

    def show_timezone_dialog(self):
        """Show timezone selection dialog"""
        dialog = TimezoneDialog(self)
        if dialog.exec_():
            timezone = dialog.get_selected_timezone()
            self.set_timezone(timezone)

    def show_alarm_dialog(self):
        """Show alarm management dialog"""
        dialog = AlarmDialog(self.alarms, self)
        if dialog.exec_():
            self.alarms = dialog.get_alarms()
            self.save_settings()
            self.start_alarm_check()

    def show_calendar_popup(self):
        """Show calendar popup"""
        if not self.calendar_popup:
            self.calendar_popup = CalendarPopup(self)

        # Position near clock
        pos = self.mapToGlobal(QPoint(self.width() + 10, 0))
        self.calendar_popup.move(pos)
        self.calendar_popup.show()

    def toggle_always_on_top(self, checked):
        """Toggle always on top"""
        flags = self.windowFlags()
        if checked:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint

        self.setWindowFlags(flags)
        self.show()

    def apply_settings(self, settings: dict):
        """Apply settings from dialog"""
        if self.analog_clock:
            self.analog_clock.show_seconds = settings.get('show_seconds', True)
            self.analog_clock.show_numbers = settings.get('show_numbers', True)
            self.analog_clock.show_date = settings.get('show_date', False)
            self.analog_clock.update()

        if self.digital_clock:
            self.digital_clock.show_seconds = settings.get('show_seconds', True)
            self.digital_clock.show_date = settings.get('show_date', False)
            self.digital_clock.set_time_format(settings.get('format_24h', True))

        self.save_settings()

    def set_timezone(self, timezone_name: str):
        """Set timezone"""
        self.current_timezone = timezone_name
        self.timezone_changed.emit(timezone_name)
        # TODO: Implement timezone conversion
        self.save_settings()

    def start_alarm_check(self):
        """Start checking for alarms"""
        # TODO: Implement alarm checking
        pass

    # ========== DRAG & DROP ==========

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press for dragging"""
        if event.button() == Qt.LeftButton and self.is_draggable:
            self.drag_start_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move for dragging"""
        if event.buttons() == Qt.LeftButton and self.drag_start_pos:
            self.move(event.globalPos() - self.drag_start_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release"""
        self.drag_start_pos = None

    def wheelEvent(self, event: QWheelEvent):
        """Handle wheel for resizing"""
        if self.is_resizable and event.modifiers() == Qt.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.1 if delta > 0 else 0.9

            new_size = self.size() * factor
            new_size.setWidth(max(150, min(400, new_size.width())))
            new_size.setHeight(max(150, min(400, new_size.height())))

            self.resize(new_size)
            event.accept()

    # ========== SETTINGS ==========

    def save_settings(self):
        """Save widget settings"""
        self.settings.setValue("mode", self.mode.value)
        self.settings.setValue("position", self.pos())
        self.settings.setValue("size", self.size())
        self.settings.setValue("timezone", self.current_timezone)
        self.settings.setValue("alarms", self.alarms)

        if self.analog_clock:
            self.settings.setValue("analog_style", self.analog_clock.clock_style.value)
            self.settings.setValue("show_seconds", self.analog_clock.show_seconds)
            self.settings.setValue("show_numbers", self.analog_clock.show_numbers)

    def load_settings(self):
        """Load saved settings"""
        # Position and size
        pos = self.settings.value("position")
        if pos:
            self.move(pos)

        size = self.settings.value("size")
        if size:
            self.resize(size)

        # Timezone
        self.current_timezone = self.settings.value("timezone", "Local")

        # Alarms
        self.alarms = self.settings.value("alarms", [])

        # Analog clock settings
        if self.analog_clock:
            style = self.settings.value("analog_style", "modern")
            for s in ClockStyle:
                if s.value == style:
                    self.analog_clock.clock_style = s
                    break

            self.analog_clock.show_seconds = self.settings.value("show_seconds", True)
            self.analog_clock.show_numbers = self.settings.value("show_numbers", True)


# ========== DIALOGS ==========

class ClockSettingsDialog(QDialog):
    """Clock settings dialog"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cài đặt đồng hồ")
        self.setModal(True)
        self.resize(400, 300)

        # Layout
        layout = QVBoxLayout(self)

        # Show seconds
        self.show_seconds_cb = QCheckBox("Hiển thị kim giây")
        self.show_seconds_cb.setChecked(True)
        layout.addWidget(self.show_seconds_cb)

        # Show numbers
        self.show_numbers_cb = QCheckBox("Hiển thị số")
        self.show_numbers_cb.setChecked(True)
        layout.addWidget(self.show_numbers_cb)

        # Show date
        self.show_date_cb = QCheckBox("Hiển thị ngày")
        layout.addWidget(self.show_date_cb)

        # 24h format
        self.format_24h_cb = QCheckBox("Định dạng 24 giờ")
        self.format_24h_cb.setChecked(True)
        layout.addWidget(self.format_24h_cb)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_settings(self) -> dict:
        """Get settings from dialog"""
        return {
            'show_seconds': self.show_seconds_cb.isChecked(),
            'show_numbers': self.show_numbers_cb.isChecked(),
            'show_date': self.show_date_cb.isChecked(),
            'format_24h': self.format_24h_cb.isChecked()
        }


class TimezoneDialog(QDialog):
    """Timezone selection dialog"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chọn múi giờ")
        self.setModal(True)
        self.resize(400, 500)

        # Layout
        layout = QVBoxLayout(self)

        # Timezone list
        self.timezone_list = QListWidget()

        # Add common timezones
        timezones = [
            "Local",
            "UTC",
            "Asia/Ho_Chi_Minh",
            "Asia/Bangkok",
            "Asia/Singapore",
            "Asia/Tokyo",
            "Asia/Seoul",
            "Asia/Shanghai",
            "Europe/London",
            "Europe/Paris",
            "America/New_York",
            "America/Los_Angeles"
        ]

        for tz in timezones:
            self.timezone_list.addItem(tz)

        layout.addWidget(self.timezone_list)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_selected_timezone(self) -> str:
        """Get selected timezone"""
        current = self.timezone_list.currentItem()
        return current.text() if current else "Local"


class AlarmDialog(QDialog):
    """Alarm management dialog"""

    def __init__(self, alarms: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quản lý báo thức")
        self.setModal(True)
        self.resize(500, 400)
        self.alarms = alarms.copy()

        # Layout
        layout = QVBoxLayout(self)

        # Alarm list
        self.alarm_list = QListWidget()
        for alarm in self.alarms:
            self.alarm_list.addItem(f"{alarm['time']} - {alarm['name']}")

        layout.addWidget(self.alarm_list)

        # Add alarm section
        add_layout = QHBoxLayout()

        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        add_layout.addWidget(self.time_edit)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Tên báo thức")
        add_layout.addWidget(self.name_edit)

        add_btn = QPushButton("Thêm")
        add_btn.clicked.connect(self.add_alarm)
        add_layout.addWidget(add_btn)

        layout.addLayout(add_layout)

        # Remove button
        remove_btn = QPushButton("Xóa báo thức đã chọn")
        remove_btn.clicked.connect(self.remove_alarm)
        layout.addWidget(remove_btn)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def add_alarm(self):
        """Add new alarm"""
        time = self.time_edit.time().toString("HH:mm")
        name = self.name_edit.text() or "Báo thức"

        alarm = {
            'time': time,
            'name': name,
            'enabled': True
        }

        self.alarms.append(alarm)
        self.alarm_list.addItem(f"{time} - {name}")

        self.name_edit.clear()

    def remove_alarm(self):
        """Remove selected alarm"""
        row = self.alarm_list.currentRow()
        if row >= 0:
            self.alarm_list.takeItem(row)
            del self.alarms[row]

    def get_alarms(self) -> list:
        """Get alarm list"""
        return self.alarms


class CalendarPopup(QFrame):
    """Calendar popup widget"""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)

        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setObjectName("CalendarPopup")

        # Style
        self.setStyleSheet("""
            QFrame#CalendarPopup {
                background: rgba(30, 30, 40, 240);
                border: 2px solid rgba(100, 100, 120, 200);
                border-radius: 10px;
            }
        """)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("📅 Lịch")
        title.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Calendar widget
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)

        # Style calendar
        self.calendar.setStyleSheet("""
            QCalendarWidget {
                background: rgba(50, 50, 60, 200);
                color: white;
            }
            QCalendarWidget QToolButton {
                color: white;
                background: rgba(70, 70, 80, 150);
                border: 1px solid rgba(100, 100, 120, 100);
                border-radius: 3px;
                padding: 3px;
            }
            QCalendarWidget QToolButton:hover {
                background: rgba(100, 100, 120, 150);
            }
            QCalendarWidget QMenu {
                background: rgba(40, 40, 50, 240);
                color: white;
            }
            QCalendarWidget QSpinBox {
                background: rgba(40, 40, 50, 200);
                color: white;
                border: 1px solid rgba(100, 100, 120, 100);
            }
            QCalendarWidget QTableView {
                background: rgba(30, 30, 40, 200);
                selection-background-color: rgba(100, 100, 200, 150);
                color: white;
            }
        """)

        layout.addWidget(self.calendar)

        # Today button
        today_btn = QPushButton("Hôm nay")
        today_btn.clicked.connect(lambda: self.calendar.setSelectedDate(QDate.currentDate()))
        layout.addWidget(today_btn)

        # Size
        self.resize(350, 400)