# ui_qt/board/ui/layer_panel.py
from __future__ import annotations
from typing import Optional
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QSlider, \
    QLabel


class LayerItem(QListWidgetItem):
    """Item đại diện cho một layer trong list"""

    def __init__(self, layer_index: int, layer_name: str, visible: bool = True, opacity: float = 1.0):
        super().__init__()
        self.layer_index = layer_index
        self.layer_name = layer_name
        self.visible = visible
        self.opacity = opacity

        self.setText(f"{'👁️' if visible else '🚫'} {layer_name} ({int(opacity * 100)}%)")

        # Set custom data
        self.setData(Qt.UserRole, layer_index)


class LayerListWidget(QListWidget):
    """Custom list widget với drag & drop cho layers"""

    layerMoved = Signal(int, int)  # from_index, to_index
    layerVisibilityChanged = Signal(int, bool)  # layer_index, visible
    layerSelected = Signal(int)  # layer_index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QListWidget.InternalMove)
        self.setSelectionMode(QListWidget.SingleSelection)

        # Connect signals
        self.itemChanged.connect(self._on_item_changed)
        self.currentRowChanged.connect(self._on_selection_changed)

    def _on_item_changed(self, item: LayerItem):
        """Xử lý khi item thay đổi"""
        pass

    def _on_selection_changed(self, row: int):
        """Xử lý khi selection thay đổi"""
        if row >= 0:
            item = self.item(row)
            if item:
                layer_index = item.data(Qt.UserRole)
                self.layerSelected.emit(layer_index)

    def mousePressEvent(self, event):
        """Override để xử lý click vào visibility icon"""
        item = self.itemAt(event.pos())
        if item:
            # Kiểm tra click vào vùng visibility icon (30px đầu)
            item_rect = self.visualItemRect(item)
            if event.pos().x() - item_rect.left() < 30:
                # Toggle visibility
                layer_item = item
                layer_item.visible = not layer_item.visible
                layer_item.setText(
                    f"{'👁️' if layer_item.visible else '🚫'} {layer_item.layer_name} ({int(layer_item.opacity * 100)}%)")
                self.layerVisibilityChanged.emit(layer_item.layer_index, layer_item.visible)
                return

        super().mousePressEvent(event)

    def dropEvent(self, event):
        """Xử lý drop để emit signal layer moved"""
        source_row = self.currentRow()
        super().dropEvent(event)
        target_row = self.currentRow()

        if source_row != target_row and source_row >= 0 and target_row >= 0:
            self.layerMoved.emit(source_row, target_row)


class LayerPanel(QWidget):
    """Panel quản lý layers"""

    # Signals
    layerAdded = Signal(str)  # layer_name
    layerRemoved = Signal(int)  # layer_index
    layerDuplicated = Signal(int)  # layer_index
    layerMoved = Signal(int, int)  # from_index, to_index
    layerSelected = Signal(int)  # layer_index
    layerVisibilityChanged = Signal(int, bool)  # layer_index, visible
    layerOpacityChanged = Signal(int, float)  # layer_index, opacity
    layerModeChanged = Signal(str)  # "single" | "multi"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_layer_index = 0
        self.layer_mode = "single"

        self.setWindowTitle("Layers")
        self.setMinimumSize(200, 300)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Thiết lập giao diện"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Header với toggle mode
        header_layout = QHBoxLayout()
        self.mode_toggle = QPushButton("📄 Single Layer")
        self.mode_toggle.setCheckable(True)
        self.mode_toggle.setToolTip("Toggle between Single Layer and Multi Layer mode")
        header_layout.addWidget(QLabel("Layers:"))
        header_layout.addStretch()
        header_layout.addWidget(self.mode_toggle)
        layout.addLayout(header_layout)

        # Layer list
        self.layer_list = LayerListWidget()
        layout.addWidget(self.layer_list)

        # Opacity slider
        opacity_layout = QVBoxLayout()
        self.opacity_label = QLabel("Opacity: 100%")
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(100)
        opacity_layout.addWidget(self.opacity_label)
        opacity_layout.addWidget(self.opacity_slider)
        layout.addLayout(opacity_layout)

        # Buttons
        button_layout = QHBoxLayout()
        self.btn_add = QPushButton("➕")
        self.btn_add.setToolTip("Add Layer")
        self.btn_remove = QPushButton("🗑️")
        self.btn_remove.setToolTip("Remove Layer")
        self.btn_duplicate = QPushButton("📋")
        self.btn_duplicate.setToolTip("Duplicate Layer")

        for btn in [self.btn_add, self.btn_remove, self.btn_duplicate]:
            btn.setFixedSize(30, 30)
            button_layout.addWidget(btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    def _connect_signals(self):
        """Kết nối signals"""
        self.mode_toggle.toggled.connect(self._on_mode_toggle)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)

        self.btn_add.clicked.connect(self._on_add_layer)
        self.btn_remove.clicked.connect(self._on_remove_layer)
        self.btn_duplicate.clicked.connect(self._on_duplicate_layer)

        # Layer list signals
        self.layer_list.layerMoved.connect(self.layerMoved.emit)
        self.layer_list.layerSelected.connect(self._on_layer_selected)
        self.layer_list.layerVisibilityChanged.connect(self.layerVisibilityChanged.emit)

    def _on_mode_toggle(self, checked: bool):
        """Xử lý toggle layer mode"""
        if checked:
            self.layer_mode = "multi"
            self.mode_toggle.setText("📚 Multi Layer")
            self.layer_list.setEnabled(True)
        else:
            self.layer_mode = "single"
            self.mode_toggle.setText("📄 Single Layer")
            self.layer_list.setEnabled(False)

        self.layerModeChanged.emit(self.layer_mode)

    def _on_opacity_changed(self, value: int):
        """Xử lý thay đổi opacity"""
        opacity = value / 100.0
        self.opacity_label.setText(f"Opacity: {value}%")

        current_row = self.layer_list.currentRow()
        if current_row >= 0:
            item = self.layer_list.item(current_row)
            if item:
                layer_index = item.data(Qt.UserRole)
                self.layerOpacityChanged.emit(layer_index, opacity)

                # Update item display
                layer_item = item
                layer_item.opacity = opacity
                layer_item.setText(f"{'👁️' if layer_item.visible else '🚫'} {layer_item.layer_name} ({value}%)")

    def _on_layer_selected(self, layer_index: int):
        """Xử lý khi layer được chọn"""
        self.current_layer_index = layer_index

        # Update opacity slider
        item = self.layer_list.currentItem()
        if item:
            layer_item = item
            self.opacity_slider.blockSignals(True)
            self.opacity_slider.setValue(int(layer_item.opacity * 100))
            self.opacity_slider.blockSignals(False)
            self.opacity_label.setText(f"Opacity: {int(layer_item.opacity * 100)}%")

        self.layerSelected.emit(layer_index)

    def _on_add_layer(self):
        """Thêm layer mới"""
        layer_name, ok = QtWidgets.QInputDialog.getText(
            self, "Add Layer", "Layer name:", text=f"Layer {self.layer_list.count() + 1}"
        )
        if ok and layer_name:
            self.layerAdded.emit(layer_name)

    def _on_remove_layer(self):
        """Xóa layer hiện tại"""
        current_row = self.layer_list.currentRow()
        if current_row >= 0:
            item = self.layer_list.item(current_row)
            if item:
                layer_index = item.data(Qt.UserRole)
                self.layerRemoved.emit(layer_index)

    def _on_duplicate_layer(self):
        """Nhân đôi layer hiện tại"""
        current_row = self.layer_list.currentRow()
        if current_row >= 0:
            item = self.layer_list.item(current_row)
            if item:
                layer_index = item.data(Qt.UserRole)
                self.layerDuplicated.emit(layer_index)

    def update_layers(self, layers: list):
        """Cập nhật danh sách layers"""
        self.layer_list.clear()

        for i, layer in enumerate(layers):
            item = LayerItem(i, layer.name, layer.visible, layer.opacity)
            self.layer_list.addItem(item)

        # Select first item if exists
        if self.layer_list.count() > 0:
            self.layer_list.setCurrentRow(0)

    def set_active_layer(self, index: int):
        """Đặt layer active"""
        if 0 <= index < self.layer_list.count():
            self.layer_list.setCurrentRow(index)