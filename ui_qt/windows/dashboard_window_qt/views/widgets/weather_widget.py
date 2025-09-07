    # ui_qt/windows/dashboard_window_qt/views/widgets/weather_widget.py
    """
    Weather Widget - Widget thời tiết cho Desktop
    Hiển thị: Nhiệt độ, độ ẩm, tốc độ gió, dự báo 5 ngày
    Sử dụng OpenWeatherMap API hoặc các API miễn phí khác
    """

    import json
    import requests
    from pathlib import Path
    from typing import Optional, List, Dict, Any, Tuple
    from datetime import datetime, timedelta
    from enum import Enum
    import logging
    from dataclasses import dataclass

    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QFrame, QGraphicsDropShadowEffect, QPushButton,
        QLineEdit, QCompleter, QMenu, QComboBox,
        QScrollArea, QGridLayout, QToolButton
    )
    from PySide6.QtCore import (
        Qt, QTimer, QThread, QSettings, QSize, QPoint,
        Signal, Property, QPropertyAnimation, QEasingCurve,
        QEvent, QUrl, QRect, Signal
    )
    from PySide6.QtGui import (
        QPainter, QColor, QPen, QBrush, QFont,
        QLinearGradient, QRadialGradient, QPixmap, QIcon,
        QPainterPath, QMouseEvent, QPaintEvent, QImage,
        QFontMetrics, QAction, QCursor
    )
    from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

    # Import utils
    try:
        from ...utils.constants import (
            WEATHER_WIDGET_SIZE, WEATHER_UPDATE_INTERVAL,
            ANIMATION_DURATION_NORMAL
        )
        from ...utils.assets import load_icon
    except ImportError:
        # Fallback values
        WEATHER_WIDGET_SIZE = QSize(250, 150)
        WEATHER_UPDATE_INTERVAL = 1800000  # 30 minutes
        ANIMATION_DURATION_NORMAL = 300


        def load_icon(name):
            return QIcon()

    # Logger
    logger = logging.getLogger(__name__)

    # ========== CONSTANTS ==========

    # API Configuration
    OPENWEATHERMAP_API_KEY = "YOUR_API_KEY_HERE"  # Replace with actual API key
    OPENWEATHERMAP_BASE_URL = "https://api.openweathermap.org/data/2.5"

    # Default cities in Vietnam
    DEFAULT_CITIES = [
        {"name": "Hà Nội", "lat": 21.0285, "lon": 105.8542},
        {"name": "TP. Hồ Chí Minh", "lat": 10.8231, "lon": 106.6297},
        {"name": "Đà Nẵng", "lat": 16.0544, "lon": 108.2022},
        {"name": "Cần Thơ", "lat": 10.0452, "lon": 105.7469},
        {"name": "Hải Phòng", "lat": 20.8449, "lon": 106.6881},
        {"name": "Nha Trang", "lat": 12.2388, "lon": 109.1967},
        {"name": "Đà Lạt", "lat": 11.9465, "lon": 108.4419},
        {"name": "Huế", "lat": 16.4637, "lon": 107.5909},
        {"name": "Vũng Tàu", "lat": 10.4114, "lon": 107.1362},
        {"name": "Quy Nhơn", "lat": 13.7830, "lon": 109.2197}
    ]


    # ========== ENUMS ==========

    class WeatherCondition(Enum):
        """Weather conditions"""
        CLEAR = "clear"
        CLOUDS = "clouds"
        RAIN = "rain"
        DRIZZLE = "drizzle"
        THUNDERSTORM = "thunderstorm"
        SNOW = "snow"
        MIST = "mist"
        FOG = "fog"
        HAZE = "haze"


    class TemperatureUnit(Enum):
        """Temperature units"""
        CELSIUS = "metric"
        FAHRENHEIT = "imperial"
        KELVIN = "standard"


    class WidgetStyle(Enum):
        """Widget visual styles"""
        MODERN = "modern"
        MINIMAL = "minimal"
        DETAILED = "detailed"
        COMPACT = "compact"
        GLASS = "glass"


    # ========== DATA CLASSES ==========

    @dataclass
    class WeatherData:
        """Current weather data"""
        city: str
        country: str
        temperature: float
        feels_like: float
        temp_min: float
        temp_max: float
        humidity: int
        pressure: int
        wind_speed: float
        wind_direction: int
        clouds: int
        condition: str
        description: str
        icon: str
        sunrise: datetime
        sunset: datetime
        timestamp: datetime


    @dataclass
    class ForecastData:
        """Forecast data for one day"""
        date: datetime
        temp_min: float
        temp_max: float
        condition: str
        description: str
        icon: str
        humidity: int
        wind_speed: float
        rain_chance: float


    # ========== API WORKER ==========

    class WeatherAPIWorker(QThread):
        """Background worker for API calls"""

        # Signals
        weather_received = Signal(dict)
        forecast_received = Signal(list)
        error_occurred = Signal(str)

        def __init__(self, api_key: str, parent=None):
            super().__init__(parent)
            self.api_key = api_key
            self.city_name = ""
            self.lat = 0
            self.lon = 0
            self.unit = TemperatureUnit.CELSIUS
            self.task = "weather"  # weather or forecast

        def set_location(self, city_name: str = "", lat: float = 0, lon: float = 0):
            """Set location for weather data"""
            self.city_name = city_name
            self.lat = lat
            self.lon = lon

        def set_unit(self, unit: TemperatureUnit):
            """Set temperature unit"""
            self.unit = unit

        def set_task(self, task: str):
            """Set task type"""
            self.task = task

        def run(self):
            """Fetch weather data"""
            try:
                if self.task == "weather":
                    self.fetch_current_weather()
                elif self.task == "forecast":
                    self.fetch_forecast()
            except Exception as e:
                self.error_occurred.emit(str(e))

        def fetch_current_weather(self):
            """Fetch current weather data"""
            try:
                # Build URL
                if self.city_name:
                    url = f"{OPENWEATHERMAP_BASE_URL}/weather"
                    params = {
                        "q": self.city_name,
                        "appid": self.api_key,
                        "units": self.unit.value,
                        "lang": "vi"
                    }
                else:
                    url = f"{OPENWEATHERMAP_BASE_URL}/weather"
                    params = {
                        "lat": self.lat,
                        "lon": self.lon,
                        "appid": self.api_key,
                        "units": self.unit.value,
                        "lang": "vi"
                    }

                # Make request
                response = requests.get(url, params=params, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    self.weather_received.emit(data)
                else:
                    self.error_occurred.emit(f"API Error: {response.status_code}")

            except requests.RequestException as e:
                self.error_occurred.emit(f"Network error: {str(e)}")
            except Exception as e:
                self.error_occurred.emit(f"Error: {str(e)}")

        def fetch_forecast(self):
            """Fetch 5-day forecast"""
            try:
                # Build URL
                if self.city_name:
                    url = f"{OPENWEATHERMAP_BASE_URL}/forecast"
                    params = {
                        "q": self.city_name,
                        "appid": self.api_key,
                        "units": self.unit.value,
                        "lang": "vi",
                        "cnt": 40  # 5 days * 8 (3-hour intervals)
                    }
                else:
                    url = f"{OPENWEATHERMAP_BASE_URL}/forecast"
                    params = {
                        "lat": self.lat,
                        "lon": self.lon,
                        "appid": self.api_key,
                        "units": self.unit.value,
                        "lang": "vi",
                        "cnt": 40
                    }

                # Make request
                response = requests.get(url, params=params, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    # Process to daily forecast
                    daily_forecast = self.process_forecast_data(data)
                    self.forecast_received.emit(daily_forecast)
                else:
                    self.error_occurred.emit(f"API Error: {response.status_code}")

            except requests.RequestException as e:
                self.error_occurred.emit(f"Network error: {str(e)}")
            except Exception as e:
                self.error_occurred.emit(f"Error: {str(e)}")

        def process_forecast_data(self, data: dict) -> list:
            """Process forecast data to daily format"""
            daily_data = {}

            for item in data.get('list', []):
                date = datetime.fromtimestamp(item['dt']).date()
                date_str = date.strftime('%Y-%m-%d')

                if date_str not in daily_data:
                    daily_data[date_str] = {
                        'date': date,
                        'temps': [],
                        'conditions': [],
                        'humidity': [],
                        'wind': [],
                        'rain': 0
                    }

                daily_data[date_str]['temps'].append(item['main']['temp'])
                daily_data[date_str]['conditions'].append(item['weather'][0]['main'])
                daily_data[date_str]['humidity'].append(item['main']['humidity'])
                daily_data[date_str]['wind'].append(item['wind']['speed'])

                if 'rain' in item:
                    daily_data[date_str]['rain'] += item['rain'].get('3h', 0)

            # Convert to list of daily forecasts
            forecast_list = []
            for date_str, day_data in daily_data.items():
                if day_data['temps']:  # Skip if no data
                    forecast_list.append({
                        'date': day_data['date'],
                        'temp_min': min(day_data['temps']),
                        'temp_max': max(day_data['temps']),
                        'condition': max(set(day_data['conditions']), key=day_data['conditions'].count),
                        'humidity': sum(day_data['humidity']) // len(day_data['humidity']),
                        'wind_speed': sum(day_data['wind']) / len(day_data['wind']),
                        'rain_chance': min(100, day_data['rain'] * 10)  # Rough estimate
                    })

            return forecast_list[:5]  # Return only 5 days


    # ========== MAIN WIDGET ==========

    class WeatherWidget(QFrame):
        """
        Main weather widget for desktop
        """

        # Signals
        location_changed = Signal(str)
        refresh_requested = Signal()

        def __init__(self, api_key: str = None, style: WidgetStyle = WidgetStyle.MODERN, parent=None):
            super().__init__(parent)

            # API configuration
            self.api_key = api_key or OPENWEATHERMAP_API_KEY
            self.style = style

            # Data
            self.current_weather = None
            self.forecast_data = []
            self.current_city = "Hà Nội"
            self.current_location = {"lat": 21.0285, "lon": 105.8542}
            self.temperature_unit = TemperatureUnit.CELSIUS

            # UI components
            self.is_expanded = False
            self.is_draggable = True
            self.drag_start_pos = None

            # API worker
            self.api_worker = WeatherAPIWorker(self.api_key)
            self.api_worker.weather_received.connect(self.on_weather_received)
            self.api_worker.forecast_received.connect(self.on_forecast_received)
            self.api_worker.error_occurred.connect(self.on_error)

            # Update timer
            self.update_timer = QTimer()
            self.update_timer.timeout.connect(self.refresh_weather)
            self.update_timer.setInterval(WEATHER_UPDATE_INTERVAL)

            # Settings
            self.settings = QSettings("TutorApp", "WeatherWidget")

            # Setup UI
            self.setup_ui()

            # Load settings
            self.load_settings()

            # Initial fetch
            self.refresh_weather()
            self.update_timer.start()

            # Window flags for desktop widget
            self.setWindowFlags(
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool
            )
            self.setAttribute(Qt.WA_TranslucentBackground)

        def setup_ui(self):
            """Setup UI components"""
            self.setObjectName("WeatherWidget")
            self.setFixedSize(WEATHER_WIDGET_SIZE)

            # Main layout
            layout = QVBoxLayout(self)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(5)

            # Header with location
            header_layout = QHBoxLayout()

            self.location_label = QLabel(self.current_city)
            self.location_label.setObjectName("WeatherLocation")
            font = QFont("Segoe UI", 12, QFont.Bold)
            self.location_label.setFont(font)
            header_layout.addWidget(self.location_label)

            header_layout.addStretch()

            # Settings button
            self.settings_btn = QToolButton()
            self.settings_btn.setText("⚙")
            self.settings_btn.setFixedSize(20, 20)
            self.settings_btn.setCursor(Qt.PointingHandCursor)
            self.settings_btn.clicked.connect(self.show_settings_menu)
            header_layout.addWidget(self.settings_btn)

            # Refresh button
            self.refresh_btn = QToolButton()
            self.refresh_btn.setText("🔄")
            self.refresh_btn.setFixedSize(20, 20)
            self.refresh_btn.setCursor(Qt.PointingHandCursor)
            self.refresh_btn.clicked.connect(self.refresh_weather)
            header_layout.addWidget(self.refresh_btn)

            layout.addLayout(header_layout)

            # Current weather display
            self.weather_display = CurrentWeatherDisplay()
            layout.addWidget(self.weather_display)

            # Forecast section (initially hidden)
            self.forecast_section = ForecastDisplay()
            self.forecast_section.hide()
            layout.addWidget(self.forecast_section)

            # Expand/Collapse button
            self.expand_btn = QPushButton("▼ Dự báo 5 ngày")
            self.expand_btn.setObjectName("ExpandButton")
            self.expand_btn.setCursor(Qt.PointingHandCursor)
            self.expand_btn.clicked.connect(self.toggle_forecast)
            layout.addWidget(self.expand_btn)

            # Apply style
            self.apply_style()

        def apply_style(self):
            """Apply visual style"""
            if self.style == WidgetStyle.MODERN:
                self.setStyleSheet("""
                    #WeatherWidget {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #667eea, stop:1 #764ba2);
                        border-radius: 15px;
                    }
                    #WeatherLocation {
                        color: white;
                    }
                    #ExpandButton {
                        background: rgba(255, 255, 255, 20);
                        color: white;
                        border: 1px solid rgba(255, 255, 255, 30);
                        border-radius: 5px;
                        padding: 5px;
                    }
                    #ExpandButton:hover {
                        background: rgba(255, 255, 255, 30);
                    }
                    QToolButton {
                        background: transparent;
                        color: white;
                        border: none;
                    }
                    QToolButton:hover {
                        background: rgba(255, 255, 255, 20);
                        border-radius: 10px;
                    }
                """)

                # Add shadow
                shadow = QGraphicsDropShadowEffect()
                shadow.setBlurRadius(20)
                shadow.setColor(QColor(0, 0, 0, 100))
                shadow.setOffset(0, 5)
                self.setGraphicsEffect(shadow)

            elif self.style == WidgetStyle.MINIMAL:
                self.setStyleSheet("""
                    #WeatherWidget {
                        background: white;
                        border: 1px solid #e0e0e0;
                        border-radius: 10px;
                    }
                    #WeatherLocation {
                        color: #333;
                    }
                """)

            elif self.style == WidgetStyle.GLASS:
                self.setStyleSheet("""
                    #WeatherWidget {
                        background: rgba(255, 255, 255, 150);
                        border: 1px solid rgba(255, 255, 255, 200);
                        border-radius: 15px;
                    }
                    #WeatherLocation {
                        color: #333;
                    }
                """)

        def refresh_weather(self):
            """Refresh weather data"""
            self.refresh_btn.setText("⏳")

            # Fetch current weather
            self.api_worker.set_location(
                city_name=self.current_city,
                lat=self.current_location['lat'],
                lon=self.current_location['lon']
            )
            self.api_worker.set_unit(self.temperature_unit)
            self.api_worker.set_task("weather")
            self.api_worker.start()

        def on_weather_received(self, data: dict):
            """Handle received weather data"""
            try:
                # Parse data
                self.current_weather = WeatherData(
                    city=data['name'],
                    country=data['sys']['country'],
                    temperature=data['main']['temp'],
                    feels_like=data['main']['feels_like'],
                    temp_min=data['main']['temp_min'],
                    temp_max=data['main']['temp_max'],
                    humidity=data['main']['humidity'],
                    pressure=data['main']['pressure'],
                    wind_speed=data['wind']['speed'],
                    wind_direction=data['wind'].get('deg', 0),
                    clouds=data['clouds']['all'],
                    condition=data['weather'][0]['main'],
                    description=data['weather'][0]['description'],
                    icon=data['weather'][0]['icon'],
                    sunrise=datetime.fromtimestamp(data['sys']['sunrise']),
                    sunset=datetime.fromtimestamp(data['sys']['sunset']),
                    timestamp=datetime.now()
                )

                # Update display
                self.weather_display.update_weather(self.current_weather)

                # Fetch forecast
                self.api_worker.set_task("forecast")
                self.api_worker.start()

            except Exception as e:
                logger.error(f"Error parsing weather data: {e}")
            finally:
                self.refresh_btn.setText("🔄")

        def on_forecast_received(self, data: list):
            """Handle received forecast data"""
            self.forecast_data = data
            self.forecast_section.update_forecast(data)

        def on_error(self, error_msg: str):
            """Handle API error"""
            logger.error(f"Weather API error: {error_msg}")
            self.refresh_btn.setText("❌")

            # Show error in display
            self.weather_display.show_error(error_msg)

        def toggle_forecast(self):
            """Toggle forecast section"""
            if self.is_expanded:
                self.forecast_section.hide()
                self.expand_btn.setText("▼ Dự báo 5 ngày")
                self.setFixedSize(WEATHER_WIDGET_SIZE)
                self.is_expanded = False
            else:
                self.forecast_section.show()
                self.expand_btn.setText("▲ Thu gọn")
                self.setFixedSize(WEATHER_WIDGET_SIZE.width(), WEATHER_WIDGET_SIZE.height() + 150)
                self.is_expanded = True

        def show_settings_menu(self):
            """Show settings menu"""
            menu = QMenu(self)

            # Location submenu
            location_menu = menu.addMenu("📍 Thành phố")
            for city in DEFAULT_CITIES:
                action = QAction(city['name'], location_menu)
                action.triggered.connect(lambda checked, c=city: self.set_location(c))
                location_menu.addAction(action)

            location_menu.addSeparator()
            custom_action = QAction("Khác...", location_menu)
            custom_action.triggered.connect(self.show_location_dialog)
            location_menu.addAction(custom_action)

            # Temperature unit submenu
            unit_menu = menu.addMenu("🌡 Đơn vị")

            celsius_action = QAction("Celsius (°C)", unit_menu)
            celsius_action.setCheckable(True)
            celsius_action.setChecked(self.temperature_unit == TemperatureUnit.CELSIUS)
            celsius_action.triggered.connect(lambda: self.set_temperature_unit(TemperatureUnit.CELSIUS))
            unit_menu.addAction(celsius_action)

            fahrenheit_action = QAction("Fahrenheit (°F)", unit_menu)
            fahrenheit_action.setCheckable(True)
            fahrenheit_action.setChecked(self.temperature_unit == TemperatureUnit.FAHRENHEIT)
            fahrenheit_action.triggered.connect(lambda: self.set_temperature_unit(TemperatureUnit.FAHRENHEIT))
            unit_menu.addAction(fahrenheit_action)

            # Update interval submenu
            interval_menu = menu.addMenu("⏱ Cập nhật")

            for minutes in [15, 30, 60, 120]:
                action = QAction(f"{minutes} phút", interval_menu)
                action.triggered.connect(lambda checked, m=minutes: self.set_update_interval(m))
                interval_menu.addAction(action)

            menu.addSeparator()

            # Style submenu
            style_menu = menu.addMenu("🎨 Phong cách")

            for style in WidgetStyle:
                action = QAction(style.name.title(), style_menu)
                action.triggered.connect(lambda checked, s=style: self.set_style(s))
                style_menu.addAction(action)

            menu.addSeparator()

            # Always on top
            on_top_action = QAction("📌 Luôn hiển thị trên cùng", menu)
            on_top_action.setCheckable(True)
            on_top_action.setChecked(bool(self.windowFlags() & Qt.WindowStaysOnTopHint))
            on_top_action.triggered.connect(self.toggle_always_on_top)
            menu.addAction(on_top_action)

            menu.exec_(QCursor.pos())

        def set_location(self, city: dict):
            """Set weather location"""
            self.current_city = city['name']
            self.current_location = {"lat": city['lat'], "lon": city['lon']}
            self.location_label.setText(self.current_city)
            self.save_settings()
            self.refresh_weather()
            self.location_changed.emit(self.current_city)

        def set_temperature_unit(self, unit: TemperatureUnit):
            """Set temperature unit"""
            self.temperature_unit = unit
            self.save_settings()
            self.refresh_weather()

        def set_update_interval(self, minutes: int):
            """Set update interval"""
            self.update_timer.setInterval(minutes * 60000)
            self.save_settings()

        def set_style(self, style: WidgetStyle):
            """Change widget style"""
            self.style = style
            self.apply_style()
            self.save_settings()

        def show_location_dialog(self):
            """Show dialog to enter custom location"""
            # This would show a dialog to enter city name or coordinates
            pass

        def toggle_always_on_top(self, checked: bool):
            """Toggle always on top"""
            flags = self.windowFlags()
            if checked:
                flags |= Qt.WindowStaysOnTopHint
            else:
                flags &= ~Qt.WindowStaysOnTopHint
            self.setWindowFlags(flags)
            self.show()

        # ========== DRAG & DROP ==========

        def mousePressEvent(self, event: QMouseEvent):
            """Start dragging"""
            if event.button() == Qt.LeftButton and self.is_draggable:
                self.drag_start_pos = event.globalPos() - self.frameGeometry().topLeft()

        def mouseMoveEvent(self, event: QMouseEvent):
            """Drag widget"""
            if event.buttons() == Qt.LeftButton and self.drag_start_pos:
                self.move(event.globalPos() - self.drag_start_pos)

        def mouseReleaseEvent(self, event: QMouseEvent):
            """Stop dragging"""
            self.drag_start_pos = None

        # ========== SETTINGS ==========

        def save_settings(self):
            """Save widget settings"""
            self.settings.setValue("city", self.current_city)
            self.settings.setValue("location", self.current_location)
            self.settings.setValue("unit", self.temperature_unit.value)
            self.settings.setValue("style", self.style.value)
            self.settings.setValue("position", self.pos())
            self.settings.setValue("update_interval", self.update_timer.interval())

        def load_settings(self):
            """Load saved settings"""
            self.current_city = self.settings.value("city", "Hà Nội")
            self.current_location = self.settings.value("location", {"lat": 21.0285, "lon": 105.8542})

            unit = self.settings.value("unit", TemperatureUnit.CELSIUS.value)
            for u in TemperatureUnit:
                if u.value == unit:
                    self.temperature_unit = u
                    break

            style = self.settings.value("style", WidgetStyle.MODERN.value)
            for s in WidgetStyle:
                if s.value == style:
                    self.style = s
                    self.apply_style()
                    break

            pos = self.settings.value("position")
            if pos:
                self.move(pos)

            interval = self.settings.value("update_interval", WEATHER_UPDATE_INTERVAL)
            self.update_timer.setInterval(int(interval))

            self.location_label.setText(self.current_city)


    # ========== DISPLAY COMPONENTS ==========

    class CurrentWeatherDisplay(QWidget):
        """Display current weather"""

        def __init__(self, parent=None):
            super().__init__(parent)

            self.weather_data = None
            self.setup_ui()

        def setup_ui(self):
            """Setup UI"""
            layout = QHBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)

            # Weather icon
            self.icon_label = QLabel()
            self.icon_label.setFixedSize(64, 64)
            self.icon_label.setScaledContents(True)
            layout.addWidget(self.icon_label)

            # Temperature and details
            details_layout = QVBoxLayout()

            # Temperature
            self.temp_label = QLabel("--°")
            self.temp_label.setObjectName("Temperature")
            font = QFont("Segoe UI", 24, QFont.Bold)
            self.temp_label.setFont(font)
            self.temp_label.setStyleSheet("color: white;")
            details_layout.addWidget(self.temp_label)

            # Description
            self.desc_label = QLabel("--")
            self.desc_label.setStyleSheet("color: rgba(255, 255, 255, 200);")
            details_layout.addWidget(self.desc_label)

            # Additional info
            self.info_label = QLabel("--")
            self.info_label.setStyleSheet("color: rgba(255, 255, 255, 180); font-size: 10px;")
            details_layout.addWidget(self.info_label)

            layout.addLayout(details_layout)
            layout.addStretch()

        def update_weather(self, data: WeatherData):
            """Update weather display"""
            self.weather_data = data

            # Update icon
            self.set_weather_icon(data.icon)

            # Update temperature
            self.temp_label.setText(f"{data.temperature:.0f}°")

            # Update description
            self.desc_label.setText(data.description.capitalize())

            # Update additional info
            info = f"Cảm giác: {data.feels_like:.0f}° | Độ ẩm: {data.humidity}% | Gió: {data.wind_speed:.1f} m/s"
            self.info_label.setText(info)

        def set_weather_icon(self, icon_code: str):
            """Set weather icon from code"""
            # Map icon codes to emoji or load from API
            icon_map = {
                "01d": "☀️", "01n": "🌙",
                "02d": "⛅", "02n": "☁️",
                "03d": "☁️", "03n": "☁️",
                "04d": "☁️", "04n": "☁️",
                "09d": "🌧️", "09n": "🌧️",
                "10d": "🌦️", "10n": "🌧️",
                "11d": "⛈️", "11n": "⛈️",
                "13d": "❄️", "13n": "❄️",
                "50d": "🌫️", "50n": "🌫️"
            }

            emoji = icon_map.get(icon_code, "❓")
            self.icon_label.setText(emoji)
            self.icon_label.setAlignment(Qt.AlignCenter)
            font = QFont("Segoe UI Emoji", 32)
            self.icon_label.setFont(font)

        def show_error(self, error_msg: str):
            """Show error message"""
            self.temp_label.setText("--°")
            self.desc_label.setText("Lỗi kết nối")
            self.info_label.setText(error_msg)
            self.icon_label.setText("❌")


    class ForecastDisplay(QWidget):
        """Display 5-day forecast"""

        def __init__(self, parent=None):
            super().__init__(parent)

            self.forecast_items = []
            self.setup_ui()

        def setup_ui(self):
            """Setup UI"""
            layout = QHBoxLayout(self)
            layout.setContentsMargins(0, 5, 0, 5)
            layout.setSpacing(5)

            # Create 5 forecast items
            for i in range(5):
                item = ForecastItem()
                self.forecast_items.append(item)
                layout.addWidget(item)

        def update_forecast(self, forecast_data: list):
            """Update forecast display"""
            for i, data in enumerate(forecast_data[:5]):
                if i < len(self.forecast_items):
                    self.forecast_items[i].update_data(data)


    class ForecastItem(QFrame):
        """Single forecast day item"""

        def __init__(self, parent=None):
            super().__init__(parent)

            self.setFixedSize(45, 80)
            self.setStyleSheet("""
                QFrame {
                    background: rgba(255, 255, 255, 10);
                    border: 1px solid rgba(255, 255, 255, 20);
                    border-radius: 5px;
                }
            """)

            layout = QVBoxLayout(self)
            layout.setContentsMargins(2, 2, 2, 2)
            layout.setSpacing(2)

            # Day label
            self.day_label = QLabel("--")
            self.day_label.setAlignment(Qt.AlignCenter)
            self.day_label.setStyleSheet("color: white; font-size: 9px;")
            layout.addWidget(self.day_label)

            # Icon
            self.icon_label = QLabel("❓")
            self.icon_label.setAlignment(Qt.AlignCenter)
            self.icon_label.setStyleSheet("font-size: 16px;")
            layout.addWidget(self.icon_label)

            # Temperature
            self.temp_label = QLabel("--°")
            self.temp_label.setAlignment(Qt.AlignCenter)
            self.temp_label.setStyleSheet("color: white; font-size: 10px;")
            layout.addWidget(self.temp_label)

        def update_data(self, data: dict):
            """Update forecast item"""
            # Day
            day_names = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"]
            day = day_names[data['date'].weekday()]
            self.day_label.setText(day)

            # Icon
            condition_icons = {
                "Clear": "☀️",
                "Clouds": "☁️",
                "Rain": "🌧️",
                "Drizzle": "🌦️",
                "Thunderstorm": "⛈️",
                "Snow": "❄️",
                "Mist": "🌫️",
                "Fog": "🌫️"
            }
            icon = condition_icons.get(data['condition'], "❓")
            self.icon_label.setText(icon)

            # Temperature
            self.temp_label.setText(f"{data['temp_max']:.0f}°/{data['temp_min']:.0f}°")


    # ========== EXAMPLE USAGE ==========

    if __name__ == "__main__":
        import sys
        from PySide6.QtWidgets import QApplication

        app = QApplication(sys.argv)

        # Note: Replace with your actual API key
        # Get free API key from: https://openweathermap.org/api
        API_KEY = "YOUR_API_KEY_HERE"

        # Create weather widget
        weather = WeatherWidget(api_key=API_KEY)
        weather.show()

        # Position on desktop
        weather.move(100, 100)

        sys.exit(app.exec())