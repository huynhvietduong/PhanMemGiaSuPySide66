# ui_qt/windows/dashboard_window_qt/views/dashboard_layout_manager.py
"""
Dashboard Layout Manager - Quản lý layout responsive
Xử lý resize, splitters, docking, fullscreen và responsive breakpoints
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass
from enum import Enum
import logging

from PySide6.QtWidgets import (
    QWidget, QMainWindow, QDockWidget, QSplitter,
    QVBoxLayout, QHBoxLayout, QStackedWidget,
    QToolBar, QMenuBar, QStatusBar, QSizePolicy,
    QApplication
)
from PySide6.QtCore import (
    Qt, QSize, QPoint, QRect, QTimer,
    Signal, QObject, QSettings, QByteArray,
    QPropertyAnimation, QEasingCurve,
    QParallelAnimationGroup, QEvent
)
from PySide6.QtGui import (
    QScreen, QResizeEvent, QMoveEvent,
    QShowEvent, QHideEvent, QCloseEvent
)

# Import utils
from ..utils.constants import (
    TASKBAR_HEIGHT, SIDEBAR_WIDTH,
    DESKTOP_MIN_WIDTH, DESKTOP_MIN_HEIGHT,
    BREAKPOINT_MOBILE, BREAKPOINT_TABLET, BREAKPOINT_DESKTOP
)

# Logger
logger = logging.getLogger(__name__)


# ========== ENUMS ==========

class LayoutMode(Enum):
    """Layout modes for different screen sizes"""
    MOBILE = "mobile"  # < 768px
    TABLET = "tablet"  # 768px - 1024px
    DESKTOP = "desktop"  # > 1024px
    FULLSCREEN = "fullscreen"


class DockPosition(Enum):
    """Dock widget positions"""
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"
    FLOATING = "floating"


class SplitterOrientation(Enum):
    """Splitter orientations"""
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


# ========== LAYOUT CONFIG ==========

@dataclass
class LayoutConfig:
    """Configuration for a layout"""
    name: str
    mode: LayoutMode
    show_taskbar: bool = True
    show_sidebar: bool = True
    show_desktop: bool = True
    show_start_menu: bool = False
    taskbar_position: str = "bottom"
    sidebar_position: str = "left"
    sidebar_width: int = SIDEBAR_WIDTH
    taskbar_height: int = TASKBAR_HEIGHT
    splitter_sizes: List[int] = None
    dock_states: Dict[str, Any] = None
    window_state: str = "normal"

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'mode': self.mode.value,
            'show_taskbar': self.show_taskbar,
            'show_sidebar': self.show_sidebar,
            'show_desktop': self.show_desktop,
            'show_start_menu': self.show_start_menu,
            'taskbar_position': self.taskbar_position,
            'sidebar_position': self.sidebar_position,
            'sidebar_width': self.sidebar_width,
            'taskbar_height': self.taskbar_height,
            'splitter_sizes': self.splitter_sizes,
            'dock_states': self.dock_states,
            'window_state': self.window_state
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'LayoutConfig':
        """Create from dictionary"""
        return cls(
            name=data.get('name', 'default'),
            mode=LayoutMode(data.get('mode', 'desktop')),
            show_taskbar=data.get('show_taskbar', True),
            show_sidebar=data.get('show_sidebar', True),
            show_desktop=data.get('show_desktop', True),
            show_start_menu=data.get('show_start_menu', False),
            taskbar_position=data.get('taskbar_position', 'bottom'),
            sidebar_position=data.get('sidebar_position', 'left'),
            sidebar_width=data.get('sidebar_width', SIDEBAR_WIDTH),
            taskbar_height=data.get('taskbar_height', TASKBAR_HEIGHT),
            splitter_sizes=data.get('splitter_sizes'),
            dock_states=data.get('dock_states'),
            window_state=data.get('window_state', 'normal')
        )


# ========== LAYOUT MANAGER ==========

class DashboardLayoutManager(QObject):
    """
    Manager for dashboard layout
    Handles responsive layout, docking, splitters, and state persistence
    """

    # Signals
    layout_changed = Signal(LayoutMode)
    component_visibility_changed = Signal(str, bool)  # component_name, visible
    splitter_moved = Signal(str, list)  # splitter_name, sizes
    fullscreen_toggled = Signal(bool)
    layout_saved = Signal(str)  # layout_name
    layout_loaded = Signal(str)  # layout_name

    def __init__(self, main_window: QMainWindow = None, parent=None):
        """
        Initialize Layout Manager

        Args:
            main_window: Main window to manage
            parent: Parent object
        """
        super().__init__(parent)

        # Main window reference
        self.main_window = main_window

        # Components
        self.components: Dict[str, QWidget] = {}
        self.dock_widgets: Dict[str, QDockWidget] = {}
        self.splitters: Dict[str, QSplitter] = {}

        # State
        self.current_mode = LayoutMode.DESKTOP
        self.previous_mode = None
        self.is_fullscreen = False
        self.saved_layouts: Dict[str, LayoutConfig] = {}

        # Settings
        self.settings = QSettings("TutorSoft", "Dashboard")

        # Animations
        self.animations = []

        # Screen monitoring
        self.screen_timer = QTimer()
        self.screen_timer.timeout.connect(self._check_screen_size)
        self.screen_timer.start(1000)  # Check every second

        # Load saved layouts
        self._load_saved_layouts()

        # Setup if main window provided
        if self.main_window:
            self._setup_main_window()

        logger.info("DashboardLayoutManager initialized")

    def _setup_main_window(self):
        """Setup main window event handling"""
        # Install event filter
        self.main_window.installEventFilter(self)

        # Get initial screen size
        self._check_screen_size()

    # ========== COMPONENT MANAGEMENT ==========

    def register_component(self, name: str, widget: QWidget):
        """
        Register a component widget

        Args:
            name: Component name (e.g., 'taskbar', 'desktop', 'sidebar')
            widget: Component widget
        """
        self.components[name] = widget
        logger.debug(f"Registered component: {name}")

    def register_dock_widget(self, name: str, dock: QDockWidget):
        """
        Register a dock widget

        Args:
            name: Dock name
            dock: QDockWidget instance
        """
        self.dock_widgets[name] = dock

        # Connect signals
        dock.visibilityChanged.connect(
            lambda visible: self.component_visibility_changed.emit(name, visible)
        )

        logger.debug(f"Registered dock widget: {name}")

    def register_splitter(self, name: str, splitter: QSplitter):
        """
        Register a splitter

        Args:
            name: Splitter name
            splitter: QSplitter instance
        """
        self.splitters[name] = splitter

        # Connect signals
        splitter.splitterMoved.connect(
            lambda pos, index: self._on_splitter_moved(name)
        )

        logger.debug(f"Registered splitter: {name}")

    # ========== LAYOUT SETUP ==========

    def setup_main_layout(self):
        """Setup main dashboard layout"""
        if not self.main_window:
            logger.error("No main window set")
            return

        # Create central widget
        central_widget = QWidget()
        self.main_window.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create main splitter (horizontal)
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.register_splitter("main", self.main_splitter)

        # Add to layout
        main_layout.addWidget(self.main_splitter)

        logger.info("Main layout setup complete")

    def setup_desktop_area(self, desktop_widget: QWidget):
        """
        Setup desktop area

        Args:
            desktop_widget: Desktop widget
        """
        self.register_component("desktop", desktop_widget)

        if "main" in self.splitters:
            self.splitters["main"].addWidget(desktop_widget)

    def setup_taskbar_dock(self, taskbar_widget: QWidget) -> QDockWidget:
        """
        Setup taskbar as dock widget

        Args:
            taskbar_widget: Taskbar widget

        Returns:
            QDockWidget containing taskbar
        """
        self.register_component("taskbar", taskbar_widget)

        # Create dock widget
        dock = QDockWidget("Taskbar", self.main_window)
        dock.setObjectName("TaskbarDock")
        dock.setWidget(taskbar_widget)

        # Configure dock
        dock.setFeatures(QDockWidget.NoDockWidgetFeatures)  # No close/float
        dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)

        # Add to main window
        self.main_window.addDockWidget(Qt.BottomDockWidgetArea, dock)

        # Register
        self.register_dock_widget("taskbar", dock)

        return dock

    def setup_sidebar_dock(self, sidebar_widget: QWidget) -> QDockWidget:
        """
        Setup sidebar as dock widget

        Args:
            sidebar_widget: Sidebar widget

        Returns:
            QDockWidget containing sidebar
        """
        self.register_component("sidebar", sidebar_widget)

        # Create dock widget
        dock = QDockWidget("Sidebar", self.main_window)
        dock.setObjectName("SidebarDock")
        dock.setWidget(sidebar_widget)

        # Configure dock
        dock.setFeatures(
            QDockWidget.DockWidgetClosable |
            QDockWidget.DockWidgetMovable
        )
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        # Set size
        dock.setMinimumWidth(200)
        dock.setMaximumWidth(400)

        # Add to main window
        self.main_window.addDockWidget(Qt.LeftDockWidgetArea, dock)

        # Register
        self.register_dock_widget("sidebar", dock)

        return dock

    # ========== RESPONSIVE HANDLING ==========

    def _check_screen_size(self):
        """Check screen size and update layout mode"""
        if not self.main_window:
            return

        # Get screen size
        screen = self.main_window.screen()
        if not screen:
            screen = QApplication.primaryScreen()

        width = screen.size().width()

        # Determine layout mode
        new_mode = self._determine_layout_mode(width)

        # Update if changed
        if new_mode != self.current_mode:
            self._switch_layout_mode(new_mode)

    def _determine_layout_mode(self, width: int) -> LayoutMode:
        """
        Determine layout mode based on width

        Args:
            width: Screen width in pixels

        Returns:
            Appropriate LayoutMode
        """
        if self.is_fullscreen:
            return LayoutMode.FULLSCREEN
        elif width < BREAKPOINT_MOBILE:
            return LayoutMode.MOBILE
        elif width < BREAKPOINT_TABLET:
            return LayoutMode.TABLET
        else:
            return LayoutMode.DESKTOP

    def _switch_layout_mode(self, new_mode: LayoutMode):
        """
        Switch to new layout mode

        Args:
            new_mode: New layout mode
        """
        logger.info(f"Switching layout mode: {self.current_mode.value} -> {new_mode.value}")

        self.previous_mode = self.current_mode
        self.current_mode = new_mode

        # Apply layout based on mode
        if new_mode == LayoutMode.MOBILE:
            self._apply_mobile_layout()
        elif new_mode == LayoutMode.TABLET:
            self._apply_tablet_layout()
        elif new_mode == LayoutMode.DESKTOP:
            self._apply_desktop_layout()
        elif new_mode == LayoutMode.FULLSCREEN:
            self._apply_fullscreen_layout()

        # Emit signal
        self.layout_changed.emit(new_mode)

    def _apply_mobile_layout(self):
        """Apply mobile layout"""
        # Hide sidebar
        if "sidebar" in self.dock_widgets:
            self.dock_widgets["sidebar"].hide()

        # Make taskbar smaller
        if "taskbar" in self.components:
            taskbar = self.components["taskbar"]
            taskbar.setMaximumHeight(40)

        # Stack components vertically
        if "main" in self.splitters:
            self.splitters["main"].setOrientation(Qt.Vertical)

    def _apply_tablet_layout(self):
        """Apply tablet layout"""
        # Show collapsible sidebar
        if "sidebar" in self.dock_widgets:
            dock = self.dock_widgets["sidebar"]
            dock.show()
            dock.setFloating(False)
            dock.setMaximumWidth(250)

        # Normal taskbar
        if "taskbar" in self.components:
            taskbar = self.components["taskbar"]
            taskbar.setMaximumHeight(TASKBAR_HEIGHT)

        # Horizontal splitter
        if "main" in self.splitters:
            self.splitters["main"].setOrientation(Qt.Horizontal)

    def _apply_desktop_layout(self):
        """Apply desktop layout"""
        # Show all components
        if "sidebar" in self.dock_widgets:
            dock = self.dock_widgets["sidebar"]
            dock.show()
            dock.setFloating(False)
            dock.setMaximumWidth(400)

        if "taskbar" in self.dock_widgets:
            self.dock_widgets["taskbar"].show()

        # Normal sizes
        if "taskbar" in self.components:
            taskbar = self.components["taskbar"]
            taskbar.setMaximumHeight(TASKBAR_HEIGHT)

        # Horizontal splitter
        if "main" in self.splitters:
            self.splitters["main"].setOrientation(Qt.Horizontal)

    def _apply_fullscreen_layout(self):
        """Apply fullscreen layout"""
        # Hide taskbar
        if "taskbar" in self.dock_widgets:
            self.dock_widgets["taskbar"].hide()

        # Hide sidebar
        if "sidebar" in self.dock_widgets:
            self.dock_widgets["sidebar"].hide()

        # Maximize desktop area
        if "desktop" in self.components:
            desktop = self.components["desktop"]
            desktop.setContentsMargins(0, 0, 0, 0)

    # ========== FULLSCREEN HANDLING ==========

    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if not self.main_window:
            return

        self.is_fullscreen = not self.is_fullscreen

        if self.is_fullscreen:
            # Save current state
            self._save_window_state()

            # Enter fullscreen
            self.main_window.showFullScreen()
            self._switch_layout_mode(LayoutMode.FULLSCREEN)
        else:
            # Exit fullscreen
            self.main_window.showNormal()

            # Restore previous mode
            if self.previous_mode:
                self._switch_layout_mode(self.previous_mode)
            else:
                self._check_screen_size()

        # Emit signal
        self.fullscreen_toggled.emit(self.is_fullscreen)

    def enter_fullscreen(self):
        """Enter fullscreen mode"""
        if not self.is_fullscreen:
            self.toggle_fullscreen()

    def exit_fullscreen(self):
        """Exit fullscreen mode"""
        if self.is_fullscreen:
            self.toggle_fullscreen()

    # ========== COMPONENT VISIBILITY ==========

    def show_component(self, name: str):
        """Show a component"""
        if name in self.components:
            self.components[name].show()

        if name in self.dock_widgets:
            self.dock_widgets[name].show()

    def hide_component(self, name: str):
        """Hide a component"""
        if name in self.components:
            self.components[name].hide()

        if name in self.dock_widgets:
            self.dock_widgets[name].hide()

    def toggle_component(self, name: str):
        """Toggle component visibility"""
        if name in self.components:
            widget = self.components[name]
            widget.setVisible(not widget.isVisible())

        if name in self.dock_widgets:
            dock = self.dock_widgets[name]
            dock.setVisible(not dock.isVisible())

    def is_component_visible(self, name: str) -> bool:
        """Check if component is visible"""
        if name in self.components:
            return self.components[name].isVisible()

        if name in self.dock_widgets:
            return self.dock_widgets[name].isVisible()

        return False

    # ========== SPLITTER MANAGEMENT ==========

    def set_splitter_sizes(self, name: str, sizes: List[int]):
        """
        Set splitter sizes

        Args:
            name: Splitter name
            sizes: List of sizes for each section
        """
        if name in self.splitters:
            self.splitters[name].setSizes(sizes)

    def get_splitter_sizes(self, name: str) -> List[int]:
        """
        Get splitter sizes

        Args:
            name: Splitter name

        Returns:
            List of sizes
        """
        if name in self.splitters:
            return self.splitters[name].sizes()
        return []

    def _on_splitter_moved(self, name: str):
        """Handle splitter movement"""
        sizes = self.get_splitter_sizes(name)
        self.splitter_moved.emit(name, sizes)

        # Auto-save after delay
        QTimer.singleShot(1000, self.save_layout_state)

    # ========== STATE PERSISTENCE ==========

    def save_layout_state(self, name: str = "current"):
        """
        Save current layout state

        Args:
            name: Layout name
        """
        # Create layout config
        config = LayoutConfig(
            name=name,
            mode=self.current_mode,
            show_taskbar=self.is_component_visible("taskbar"),
            show_sidebar=self.is_component_visible("sidebar"),
            show_desktop=self.is_component_visible("desktop"),
            taskbar_position=self._get_dock_position("taskbar"),
            sidebar_position=self._get_dock_position("sidebar"),
            splitter_sizes=self._get_all_splitter_sizes(),
            dock_states=self._get_dock_states(),
            window_state=self._get_window_state()
        )

        # Save to memory
        self.saved_layouts[name] = config

        # Save to settings
        self.settings.setValue(f"layouts/{name}", json.dumps(config.to_dict()))

        # Emit signal
        self.layout_saved.emit(name)

        logger.info(f"Layout saved: {name}")

    def restore_layout_state(self, name: str = "current"):
        """
        Restore layout state

        Args:
            name: Layout name
        """
        # Load from settings if not in memory
        if name not in self.saved_layouts:
            layout_data = self.settings.value(f"layouts/{name}")
            if layout_data:
                try:
                    config = LayoutConfig.from_dict(json.loads(layout_data))
                    self.saved_layouts[name] = config
                except Exception as e:
                    logger.error(f"Error loading layout {name}: {e}")
                    return

        if name not in self.saved_layouts:
            logger.warning(f"Layout not found: {name}")
            return

        config = self.saved_layouts[name]

        # Apply layout
        self._apply_layout_config(config)

        # Emit signal
        self.layout_loaded.emit(name)

        logger.info(f"Layout restored: {name}")

    def _apply_layout_config(self, config: LayoutConfig):
        """Apply layout configuration"""
        # Set component visibility
        if config.show_taskbar:
            self.show_component("taskbar")
        else:
            self.hide_component("taskbar")

        if config.show_sidebar:
            self.show_component("sidebar")
        else:
            self.hide_component("sidebar")

        # Set splitter sizes
        if config.splitter_sizes:
            for name, sizes in config.splitter_sizes.items():
                self.set_splitter_sizes(name, sizes)

        # Restore dock states
        if config.dock_states and self.main_window:
            for dock_name, state in config.dock_states.items():
                if dock_name in self.dock_widgets:
                    dock = self.dock_widgets[dock_name]
                    if "geometry" in state:
                        dock.restoreGeometry(QByteArray.fromBase64(state["geometry"].encode()))

        # Restore window state
        if config.window_state == "maximized":
            self.main_window.showMaximized()
        elif config.window_state == "fullscreen":
            self.enter_fullscreen()
        else:
            self.main_window.showNormal()

    def _load_saved_layouts(self):
        """Load all saved layouts from settings"""
        # Load default layouts
        self._create_default_layouts()

        # Load user layouts
        layout_keys = self.settings.allKeys()
        for key in layout_keys:
            if key.startswith("layouts/"):
                layout_name = key.replace("layouts/", "")
                layout_data = self.settings.value(key)

                try:
                    config = LayoutConfig.from_dict(json.loads(layout_data))
                    self.saved_layouts[layout_name] = config
                except Exception as e:
                    logger.error(f"Error loading layout {layout_name}: {e}")

    def _create_default_layouts(self):
        """Create default layout presets"""
        # Desktop layout
        self.saved_layouts["desktop"] = LayoutConfig(
            name="desktop",
            mode=LayoutMode.DESKTOP,
            show_taskbar=True,
            show_sidebar=True,
            show_desktop=True
        )

        # Minimal layout
        self.saved_layouts["minimal"] = LayoutConfig(
            name="minimal",
            mode=LayoutMode.DESKTOP,
            show_taskbar=True,
            show_sidebar=False,
            show_desktop=True
        )

        # Focus layout
        self.saved_layouts["focus"] = LayoutConfig(
            name="focus",
            mode=LayoutMode.FULLSCREEN,
            show_taskbar=False,
            show_sidebar=False,
            show_desktop=True
        )

    # ========== HELPER METHODS ==========

    def _get_dock_position(self, name: str) -> str:
        """Get dock widget position"""
        if name not in self.dock_widgets or not self.main_window:
            return "unknown"

        dock = self.dock_widgets[name]
        area = self.main_window.dockWidgetArea(dock)

        if area == Qt.LeftDockWidgetArea:
            return "left"
        elif area == Qt.RightDockWidgetArea:
            return "right"
        elif area == Qt.TopDockWidgetArea:
            return "top"
        elif area == Qt.BottomDockWidgetArea:
            return "bottom"
        else:
            return "floating" if dock.isFloating() else "unknown"

    def _get_all_splitter_sizes(self) -> Dict[str, List[int]]:
        """Get all splitter sizes"""
        sizes = {}
        for name, splitter in self.splitters.items():
            sizes[name] = splitter.sizes()
        return sizes

    def _get_dock_states(self) -> Dict[str, Any]:
        """Get dock widget states"""
        states = {}
        for name, dock in self.dock_widgets.items():
            states[name] = {
                "visible": dock.isVisible(),
                "floating": dock.isFloating(),
                "geometry": dock.saveGeometry().toBase64().data().decode()
            }
        return states

    def _get_window_state(self) -> str:
        """Get main window state"""
        if not self.main_window:
            return "normal"

        if self.main_window.isFullScreen():
            return "fullscreen"
        elif self.main_window.isMaximized():
            return "maximized"
        else:
            return "normal"

    def _save_window_state(self):
        """Save window state before fullscreen"""
        if self.main_window:
            self.settings.setValue(
                "window/geometry",
                self.main_window.saveGeometry()
            )
            self.settings.setValue(
                "window/state",
                self.main_window.saveState()
            )

    # ========== EVENT FILTER ==========

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Event filter for main window"""
        if obj == self.main_window:
            if event.type() == QEvent.Resize:
                # Handle resize
                QTimer.singleShot(100, self._check_screen_size)
            elif event.type() == QEvent.WindowStateChange:
                # Handle state change
                if self.main_window.isFullScreen() and not self.is_fullscreen:
                    self.is_fullscreen = True
                    self._switch_layout_mode(LayoutMode.FULLSCREEN)
                elif not self.main_window.isFullScreen() and self.is_fullscreen:
                    self.is_fullscreen = False
                    self._check_screen_size()

        return False

    # ========== PUBLIC METHODS ==========

    def get_current_mode(self) -> LayoutMode:
        """Get current layout mode"""
        return self.current_mode

    def get_saved_layouts(self) -> List[str]:
        """Get list of saved layout names"""
        return list(self.saved_layouts.keys())

    def delete_layout(self, name: str) -> bool:
        """Delete a saved layout"""
        if name in ["desktop", "minimal", "focus"]:
            logger.warning(f"Cannot delete default layout: {name}")
            return False

        if name in self.saved_layouts:
            del self.saved_layouts[name]
            self.settings.remove(f"layouts/{name}")
            logger.info(f"Layout deleted: {name}")
            return True

        return False

    def export_layout(self, name: str, file_path: str) -> bool:
        """Export layout to file"""
        if name not in self.saved_layouts:
            return False

        try:
            config = self.saved_layouts[name]
            with open(file_path, 'w') as f:
                json.dump(config.to_dict(), f, indent=2)

            logger.info(f"Layout exported: {name} -> {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error exporting layout: {e}")
            return False

    def import_layout(self, file_path: str, name: Optional[str] = None) -> bool:
        """Import layout from file"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            config = LayoutConfig.from_dict(data)

            if name:
                config.name = name

            self.saved_layouts[config.name] = config
            self.save_layout_state(config.name)

            logger.info(f"Layout imported: {config.name}")
            return True

        except Exception as e:
            logger.error(f"Error importing layout: {e}")
            return False