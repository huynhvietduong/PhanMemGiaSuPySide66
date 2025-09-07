# ui_qt/windows/dashboard_window_qt/views/taskbar/system_tray.py
"""
System Tray - Clock, notification icons, volume, network, battery
Hiển thị thông tin hệ thống và điều khiển nhanh
"""

import os
import sys
import psutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import logging

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QToolButton, QMenu, QSlider, QCalendarWidget,
    QFrame, QSystemTrayIcon, QApplication,
    QStyle, QToolTip, QGraphicsOpacityEffect,
    QWidgetAction, QCheckBox, QPushButton
)
from PySide6.QtCore import (
    Qt, QSize, QPoint, QRect, QTimer, QTime,
    Signal, Property, QPropertyAnimation,
    QEasingCurve, QEvent, QDate, QDateTime,
    QLocale
)
from PySide6.QtGui import (
    QPainter, QPixmap, QIcon, QFont, QColor,
    QPen, QBrush, QAction, QPalette,
    QLinearGradient, QMouseEvent, QPaintEvent,
    QWheelEvent, QEnterEvent
)
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices

# Import utils
from ...utils.constants import TASKBAR_HEIGHT
from ...utils.assets import load_icon

# Logger
logger = logging.getLogger(__name__)


# ========== ENUMS ==========

class NetworkStatus(Enum):
    """Network connection status"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    LIMITED = "limited"
    CONNECTING = "connecting"


class BatteryStatus(Enum):
    """Battery charging status"""
    CHARGING = "charging"
    DISCHARGING = "discharging"
    FULL = "full"
    NOT_PRESENT = "not_present"


# ========== MAIN SYSTEM TRAY ==========

class SystemTray(QWidget):
    """
    System Tray Container
    Contains: Hidden icons, Volume, Network, Battery, Notifications, Clock
    """

    # Signals
    calendar_requested = Signal()
    notifications_clicked = Signal()
    volume_changed = Signal(int)
    network_clicked = Signal()
    battery_clicked = Signal()
    tray_icon_clicked = Signal(str)  # icon_id

    def __init__(self, parent=None):
        """Initialize System Tray"""
        super().__init__(parent)

        # Components
        self.clock_widget = None
        self.notification_icon = None
        self.volume_control = None
        self.network_icon = None
        self.battery_icon = None
        self.tray_icons = {}

        # State
        self.notification_count = 0
        self.volume_level = 50
        self.is_muted = False
        self.network_status = NetworkStatus.CONNECTED
        self.battery_level = 100
        self.battery_status = BatteryStatus.FULL

        # Timers
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_system_info)
        self.update_timer.start(5000)  # Update every 5 seconds

        # Setup UI
        self._setup_ui()
        self._update_system_info()

        logger.info("System Tray initialized")

    def _setup_ui(self):
        """Setup UI components"""
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 10, 0)
        layout.setSpacing(5)

        # Hidden tray icons area
        self.tray_area = TrayIconsArea(self)
        layout.addWidget(self.tray_area)

        layout.addSpacing(10)

        # System icons (left to right)

        # Volume
        self.volume_control = VolumeControl(self)
        self.volume_control.volume_changed.connect(self.volume_changed.emit)
        layout.addWidget(self.volume_control)

        # Network
        self.network_icon = NetworkIcon(self)
        self.network_icon.clicked.connect(self.network_clicked.emit)
        layout.addWidget(self.network_icon)

        # Battery (if available)
        if self._has_battery():
            self.battery_icon = BatteryIcon(self)
            self.battery_icon.clicked.connect(self.battery_clicked.emit)
            layout.addWidget(self.battery_icon)

        # Notification center
        self.notification_icon = NotificationIcon(self)
        self.notification_icon.clicked.connect(self.notifications_clicked.emit)
        layout.addWidget(self.notification_icon)

        layout.addSpacing(10)

        # Clock
        self.clock_widget = ClockWidget(self)
        self.clock_widget.clicked.connect(self.calendar_requested.emit)
        layout.addWidget(self.clock_widget)

    def _update_system_info(self):
        """Update system information"""
        # Update network status
        self._update_network_status()

        # Update battery status
        if self.battery_icon:
            self._update_battery_status()

    def _update_network_status(self):
        """Check and update network status"""
        try:
            # Check network connectivity
            import socket
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            self.network_status = NetworkStatus.CONNECTED
        except OSError:
            self.network_status = NetworkStatus.DISCONNECTED

        if self.network_icon:
            self.network_icon.set_status(self.network_status)

    def _update_battery_status(self):
        """Update battery information"""
        try:
            battery = psutil.sensors_battery()
            if battery:
                self.battery_level = int(battery.percent)

                if battery.power_plugged:
                    self.battery_status = BatteryStatus.CHARGING if battery.percent < 100 else BatteryStatus.FULL
                else:
                    self.battery_status = BatteryStatus.DISCHARGING

                if self.battery_icon:
                    self.battery_icon.set_level(self.battery_level)
                    self.battery_icon.set_status(self.battery_status)
        except Exception as e:
            logger.error(f"Error updating battery status: {e}")

    def _has_battery(self) -> bool:
        """Check if system has battery"""
        try:
            battery = psutil.sensors_battery()
            return battery is not None
        except:
            return False

    # ========== PUBLIC METHODS ==========

    def update_time(self):
        """Update clock display"""
        if self.clock_widget:
            self.clock_widget.update_time()

    def set_notification_count(self, count: int):
        """Set notification count"""
        self.notification_count = count
        if self.notification_icon:
            self.notification_icon.set_count(count)

    def add_tray_icon(self, icon_id: str, icon: QIcon, tooltip: str = ""):
        """Add icon to system tray"""
        self.tray_area.add_icon(icon_id, icon, tooltip)

    def remove_tray_icon(self, icon_id: str):
        """Remove icon from system tray"""
        self.tray_area.remove_icon(icon_id)

    def show_volume_popup(self):
        """Show volume control popup"""
        if self.volume_control:
            self.volume_control.show_popup()

    def show_network_menu(self):
        """Show network connections menu"""
        if self.network_icon:
            self.network_icon.show_menu()


# ========== CLOCK WIDGET ==========

class ClockWidget(QToolButton):
    """Digital clock with date"""

    # Signals
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("SystemClock")
        self.setCursor(Qt.PointingHandCursor)

        # Timer for updating time
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)  # Update every second

        # Initial update
        self.update_time()

        # Style
        self.setStyleSheet("""
            #SystemClock {
                background: transparent;
                border: none;
                color: white;
                padding: 0 10px;
                font-size: 13px;
            }
            #SystemClock:hover {
                background: rgba(255, 255, 255, 10);
                border-radius: 4px;
            }
        """)

    def update_time(self):
        """Update time display"""
        now = QDateTime.currentDateTime()

        # Format: HH:mm\nMM/dd/yyyy
        time_str = now.toString("hh:mm AP")
        date_str = now.toString("M/d/yyyy")

        self.setText(f"{time_str}\n{date_str}")

        # Tooltip with full date
        self.setToolTip(now.toString("dddd, MMMM d, yyyy"))

    def mousePressEvent(self, event):
        """Handle mouse press"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Show calendar on double-click"""
        if event.button() == Qt.LeftButton:
            self.show_calendar()

    def show_calendar(self):
        """Show calendar popup"""
        calendar_popup = CalendarPopup(self)

        # Position above clock
        global_pos = self.mapToGlobal(QPoint(0, 0))
        popup_pos = QPoint(
            global_pos.x() - calendar_popup.width() + self.width(),
            global_pos.y() - calendar_popup.height() - 5
        )

        calendar_popup.move(popup_pos)
        calendar_popup.show()


# ========== CALENDAR POPUP ==========

class CalendarPopup(QFrame):
    """Calendar widget popup"""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)

        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setObjectName("CalendarPopup")

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Calendar widget
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        layout.addWidget(self.calendar)

        # Today button
        today_btn = QPushButton("Today")
        today_btn.clicked.connect(lambda: self.calendar.setSelectedDate(QDate.currentDate()))
        layout.addWidget(today_btn)

        # Style
        self.setStyleSheet("""
            #CalendarPopup {
                background: white;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QCalendarWidget {
                background: white;
            }
        """)

        # Auto-close when clicking outside
        self.calendar.clicked.connect(self.close)

    def closeEvent(self, event):
        """Handle close event"""
        self.deleteLater()
        super().closeEvent(event)


# ========== NOTIFICATION ICON ==========

class NotificationIcon(QToolButton):
    """Notification center icon with badge"""

    # Signals
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.notification_count = 0

        self.setObjectName("NotificationIcon")
        self.setFixedSize(32, 32)
        self.setCursor(Qt.PointingHandCursor)

        # Icon
        self.setIcon(load_icon("notification"))
        self.setIconSize(QSize(20, 20))

        # Tooltip
        self.setToolTip("No new notifications")

        # Style
        self.setStyleSheet("""
            #NotificationIcon {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            #NotificationIcon:hover {
                background: rgba(255, 255, 255, 10);
            }
        """)

    def set_count(self, count: int):
        """Set notification count"""
        self.notification_count = count

        if count > 0:
            self.setToolTip(f"{count} new notifications")
        else:
            self.setToolTip("No new notifications")

        self.update()

    def paintEvent(self, event):
        """Paint icon with badge"""
        super().paintEvent(event)

        if self.notification_count > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)

            # Badge
            badge_rect = QRect(18, 4, 14, 14)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(255, 0, 0)))
            painter.drawEllipse(badge_rect)

            # Count
            painter.setPen(Qt.white)
            painter.setFont(QFont("Arial", 8, QFont.Bold))

            text = str(self.notification_count) if self.notification_count < 10 else "9+"
            painter.drawText(badge_rect, Qt.AlignCenter, text)

    def mousePressEvent(self, event):
        """Handle click"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ========== VOLUME CONTROL ==========

class VolumeControl(QToolButton):
    """Volume control with slider popup"""

    # Signals
    volume_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.volume_level = 50
        self.is_muted = False

        self.setObjectName("VolumeControl")
        self.setFixedSize(32, 32)
        self.setCursor(Qt.PointingHandCursor)

        # Update icon
        self.update_icon()

        # Style
        self.setStyleSheet("""
            #VolumeControl {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            #VolumeControl:hover {
                background: rgba(255, 255, 255, 10);
            }
        """)

    def update_icon(self):
        """Update icon based on volume level"""
        if self.is_muted or self.volume_level == 0:
            icon_name = "volume_mute"
            tooltip = "Muted"
        elif self.volume_level < 33:
            icon_name = "volume_low"
            tooltip = f"Volume: {self.volume_level}%"
        elif self.volume_level < 66:
            icon_name = "volume_medium"
            tooltip = f"Volume: {self.volume_level}%"
        else:
            icon_name = "volume_high"
            tooltip = f"Volume: {self.volume_level}%"

        self.setIcon(load_icon(icon_name))
        self.setIconSize(QSize(20, 20))
        self.setToolTip(tooltip)

    def wheelEvent(self, event):
        """Handle wheel for volume adjustment"""
        delta = event.angleDelta().y()

        if delta > 0:
            # Increase volume
            self.set_volume(min(100, self.volume_level + 5))
        else:
            # Decrease volume
            self.set_volume(max(0, self.volume_level - 5))

    def mousePressEvent(self, event):
        """Handle click"""
        if event.button() == Qt.LeftButton:
            self.show_popup()
        elif event.button() == Qt.MiddleButton:
            # Toggle mute
            self.toggle_mute()

        super().mousePressEvent(event)

    def show_popup(self):
        """Show volume slider popup"""
        popup = VolumePopup(self.volume_level, self.is_muted, self)
        popup.volume_changed.connect(self.set_volume)
        popup.mute_toggled.connect(self.set_mute)

        # Position above icon
        global_pos = self.mapToGlobal(QPoint(0, 0))
        popup_pos = QPoint(
            global_pos.x() - (popup.width() - self.width()) // 2,
            global_pos.y() - popup.height() - 5
        )

        popup.move(popup_pos)
        popup.show()

    def set_volume(self, level: int):
        """Set volume level"""
        self.volume_level = level
        self.is_muted = False
        self.update_icon()
        self.volume_changed.emit(level)

    def set_mute(self, muted: bool):
        """Set mute state"""
        self.is_muted = muted
        self.update_icon()

    def toggle_mute(self):
        """Toggle mute state"""
        self.set_mute(not self.is_muted)


# ========== VOLUME POPUP ==========

class VolumePopup(QFrame):
    """Volume slider popup widget"""

    # Signals
    volume_changed = Signal(int)
    mute_toggled = Signal(bool)

    def __init__(self, initial_volume: int, is_muted: bool, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)

        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setObjectName("VolumePopup")
        self.setFixedSize(50, 200)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Volume label
        self.volume_label = QLabel(f"{initial_volume}%")
        self.volume_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.volume_label)

        # Volume slider
        self.slider = QSlider(Qt.Vertical)
        self.slider.setRange(0, 100)
        self.slider.setValue(initial_volume)
        self.slider.valueChanged.connect(self._on_volume_changed)
        layout.addWidget(self.slider, 1)

        # Mute button
        self.mute_btn = QToolButton()
        self.mute_btn.setIcon(load_icon("volume_mute"))
        self.mute_btn.setCheckable(True)
        self.mute_btn.setChecked(is_muted)
        self.mute_btn.toggled.connect(self.mute_toggled.emit)
        layout.addWidget(self.mute_btn)

        # Style
        self.setStyleSheet("""
            #VolumePopup {
                background: rgba(32, 32, 32, 230);
                border: 1px solid rgba(255, 255, 255, 20);
                border-radius: 4px;
            }
            QLabel {
                color: white;
                font-size: 12px;
            }
            QSlider::groove:vertical {
                background: rgba(255, 255, 255, 20);
                width: 4px;
                border-radius: 2px;
            }
            QSlider::handle:vertical {
                background: white;
                height: 12px;
                margin: 0 -4px;
                border-radius: 6px;
            }
        """)

    def _on_volume_changed(self, value: int):
        """Handle volume change"""
        self.volume_label.setText(f"{value}%")
        self.volume_changed.emit(value)


# ========== NETWORK ICON ==========

class NetworkIcon(QToolButton):
    """Network status icon"""

    # Signals
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.network_status = NetworkStatus.CONNECTED

        self.setObjectName("NetworkIcon")
        self.setFixedSize(32, 32)
        self.setCursor(Qt.PointingHandCursor)

        # Update icon
        self.update_icon()

        # Style
        self.setStyleSheet("""
            #NetworkIcon {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            #NetworkIcon:hover {
                background: rgba(255, 255, 255, 10);
            }
        """)

    def set_status(self, status: NetworkStatus):
        """Set network status"""
        self.network_status = status
        self.update_icon()

    def update_icon(self):
        """Update icon based on status"""
        if self.network_status == NetworkStatus.CONNECTED:
            icon_name = "wifi_on"
            tooltip = "Connected"
        elif self.network_status == NetworkStatus.LIMITED:
            icon_name = "wifi_limited"
            tooltip = "Limited connectivity"
        elif self.network_status == NetworkStatus.CONNECTING:
            icon_name = "wifi_connecting"
            tooltip = "Connecting..."
        else:
            icon_name = "wifi_off"
            tooltip = "No connection"

        self.setIcon(load_icon(icon_name))
        self.setIconSize(QSize(20, 20))
        self.setToolTip(tooltip)

    def mousePressEvent(self, event):
        """Handle click"""
        if event.button() == Qt.LeftButton:
            self.show_menu()
        super().mousePressEvent(event)

    def show_menu(self):
        """Show network connections menu"""
        menu = QMenu(self)

        # Network status
        status_action = QAction(f"Status: {self.network_status.value}", menu)
        status_action.setEnabled(False)
        menu.addAction(status_action)

        menu.addSeparator()

        # Available networks (mock)
        networks = ["WiFi Network 1", "WiFi Network 2", "Mobile Hotspot"]
        for network in networks:
            network_action = QAction(network, menu)
            if network == "WiFi Network 1":
                network_action.setIcon(load_icon("check"))
            menu.addAction(network_action)

        menu.addSeparator()

        # Network settings
        settings_action = QAction(load_icon("settings"), "Network Settings", menu)
        menu.addAction(settings_action)

        # Show menu
        global_pos = self.mapToGlobal(QPoint(0, 0))
        menu.exec(QPoint(global_pos.x(), global_pos.y() - menu.sizeHint().height()))


# ========== BATTERY ICON ==========

class BatteryIcon(QToolButton):
    """Battery status icon"""

    # Signals
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.battery_level = 100
        self.battery_status = BatteryStatus.FULL

        self.setObjectName("BatteryIcon")
        self.setFixedSize(32, 32)
        self.setCursor(Qt.PointingHandCursor)

        # Style
        self.setStyleSheet("""
            #BatteryIcon {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            #BatteryIcon:hover {
                background: rgba(255, 255, 255, 10);
            }
        """)

        # Initial update
        self.update_display()

    def set_level(self, level: int):
        """Set battery level"""
        self.battery_level = max(0, min(100, level))
        self.update_display()

    def set_status(self, status: BatteryStatus):
        """Set battery status"""
        self.battery_status = status
        self.update_display()

    def update_display(self):
        """Update icon and tooltip"""
        # Choose icon based on level and status
        if self.battery_status == BatteryStatus.CHARGING:
            icon_name = "battery_charging"
            status_text = "Charging"
        elif self.battery_level > 80:
            icon_name = "battery_full"
            status_text = "On battery"
        elif self.battery_level > 50:
            icon_name = "battery_medium"
            status_text = "On battery"
        elif self.battery_level > 20:
            icon_name = "battery_low"
            status_text = "On battery"
        else:
            icon_name = "battery_critical"
            status_text = "Low battery"

        self.setIcon(load_icon(icon_name))
        self.setIconSize(QSize(20, 20))
        self.setToolTip(f"{self.battery_level}% - {status_text}")

    def paintEvent(self, event):
        """Custom paint for battery icon"""
        super().paintEvent(event)

        # Draw battery level text
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Text
        painter.setPen(Qt.white)
        painter.setFont(QFont("Arial", 7))

        text_rect = QRect(0, 18, 32, 10)
        painter.drawText(text_rect, Qt.AlignCenter, f"{self.battery_level}%")

    def mousePressEvent(self, event):
        """Handle click"""
        if event.button() == Qt.LeftButton:
            self.show_power_menu()
        super().mousePressEvent(event)

    def show_power_menu(self):
        """Show power options menu"""
        menu = QMenu(self)

        # Battery info
        info_action = QAction(f"Battery: {self.battery_level}%", menu)
        info_action.setEnabled(False)
        menu.addAction(info_action)

        status_action = QAction(f"Status: {self.battery_status.value}", menu)
        status_action.setEnabled(False)
        menu.addAction(status_action)

        menu.addSeparator()

        # Power modes
        balanced_action = QAction("Balanced", menu)
        balanced_action.setCheckable(True)
        balanced_action.setChecked(True)
        menu.addAction(balanced_action)

        power_saver_action = QAction("Power Saver", menu)
        power_saver_action.setCheckable(True)
        menu.addAction(power_saver_action)

        performance_action = QAction("High Performance", menu)
        performance_action.setCheckable(True)
        menu.addAction(performance_action)

        menu.addSeparator()

        # Power settings
        settings_action = QAction(load_icon("settings"), "Power Settings", menu)
        menu.addAction(settings_action)

        # Show menu
        global_pos = self.mapToGlobal(QPoint(0, 0))
        menu.exec(QPoint(global_pos.x(), global_pos.y() - menu.sizeHint().height()))


# ========== TRAY ICONS AREA ==========

class TrayIconsArea(QWidget):
    """Container for third-party tray icons"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.icons = {}  # {icon_id: QToolButton}

        # Layout
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)

        # Expand button
        self.expand_btn = QToolButton()
        self.expand_btn.setIcon(load_icon("chevron_up"))
        self.expand_btn.setFixedSize(16, 32)
        self.expand_btn.setToolTip("Show hidden icons")
        self.expand_btn.clicked.connect(self.show_hidden_icons)
        self.layout.addWidget(self.expand_btn)

    def add_icon(self, icon_id: str, icon: QIcon, tooltip: str = ""):
        """Add tray icon"""
        if icon_id in self.icons:
            return

        # Create button
        btn = QToolButton()
        btn.setIcon(icon)
        btn.setIconSize(QSize(16, 16))
        btn.setFixedSize(24, 24)
        btn.setToolTip(tooltip)
        btn.setStyleSheet("""
            QToolButton {
                background: transparent;
                border: none;
            }
            QToolButton:hover {
                background: rgba(255, 255, 255, 10);
                border-radius: 2px;
            }
        """)

        # Add to layout (before expand button)
        self.layout.insertWidget(self.layout.count() - 1, btn)
        self.icons[icon_id] = btn

        # Hide if too many icons
        if len(self.icons) > 3:
            btn.hide()

    def remove_icon(self, icon_id: str):
        """Remove tray icon"""
        if icon_id in self.icons:
            btn = self.icons[icon_id]
            self.layout.removeWidget(btn)
            btn.deleteLater()
            del self.icons[icon_id]

    def show_hidden_icons(self):
        """Show popup with all hidden icons"""
        hidden_count = sum(1 for btn in self.icons.values() if btn.isHidden())

        if hidden_count == 0:
            return

        # Create popup menu
        menu = QMenu(self)

        for icon_id, btn in self.icons.items():
            if btn.isHidden():
                action = QAction(btn.icon(), btn.toolTip(), menu)
                menu.addAction(action)

        # Show menu
        global_pos = self.expand_btn.mapToGlobal(QPoint(0, 0))
        menu.exec(QPoint(global_pos.x(), global_pos.y() - menu.sizeHint().height()))
        #dsf