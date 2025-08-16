# Tạo file mới: board/core/layer_manager.py
from __future__ import annotations
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtCore import Qt


@dataclass
class Layer:
    """Đại diện cho một layer vẽ"""
    name: str
    image: QImage
    visible: bool = True
    opacity: float = 1.0
    blend_mode: str = "normal"  # normal, multiply, overlay, etc.
    locked: bool = False
    metadata: Dict = field(default_factory=dict)


class LayerManager:
    """Quản lý hệ thống layers cho bảng vẽ"""

    def __init__(self, width: int = 2000, height: int = 4000):
        self.width = width
        self.height = height
        self.layers: List[Layer] = []
        self.active_layer_index = 0

        # Tạo layer nền mặc định
        self.add_layer("Background", is_background=True)

    def add_layer(self, name: str, is_background: bool = False) -> int:
        """Thêm layer mới. Trả về index của layer"""
        new_image = QImage(self.width, self.height, QImage.Format_ARGB32_Premultiplied)

        if is_background:
            new_image.fill(Qt.white)  # Nền trắng
        else:
            new_image.fill(Qt.transparent)  # Trong suốt

        layer = Layer(
            name=name,
            image=new_image,
            metadata={"is_background": is_background}
        )

        if is_background:
            # Background layer luôn ở dưới cùng
            self.layers.insert(0, layer)
            # Adjust active index nếu cần
            if self.active_layer_index >= 0:
                self.active_layer_index += 1
        else:
            self.layers.append(layer)

        return len(self.layers) - 1 if not is_background else 0

    def remove_layer(self, index: int) -> bool:
        """Xóa layer tại index. Không thể xóa layer background và phải có ít nhất 1 layer"""
        if not (0 <= index < len(self.layers)):
            return False

        layer = self.layers[index]
        if layer.metadata.get("is_background", False):
            return False  # Không thể xóa background

        if len(self.layers) <= 2:  # Background + 1 layer tối thiểu
            return False

        del self.layers[index]

        # Adjust active layer index
        if self.active_layer_index >= len(self.layers):
            self.active_layer_index = len(self.layers) - 1
        elif self.active_layer_index > index:
            self.active_layer_index -= 1

        return True

    def move_layer(self, from_index: int, to_index: int) -> bool:
        """Di chuyển layer từ vị trí này sang vị trí khác"""
        if not (0 <= from_index < len(self.layers) and 0 <= to_index < len(self.layers)):
            return False

        # Không thể di chuyển background layer
        if self.layers[from_index].metadata.get("is_background", False):
            return False

        layer = self.layers.pop(from_index)
        self.layers.insert(to_index, layer)

        # Update active index
        if self.active_layer_index == from_index:
            self.active_layer_index = to_index
        elif from_index < self.active_layer_index <= to_index:
            self.active_layer_index -= 1
        elif to_index <= self.active_layer_index < from_index:
            self.active_layer_index += 1

        return True

    def set_active_layer(self, index: int) -> bool:
        """Đặt layer active"""
        if 0 <= index < len(self.layers):
            self.active_layer_index = index
            return True
        return False

    def get_active_layer(self) -> Optional[Layer]:
        """Lấy layer đang active"""
        if 0 <= self.active_layer_index < len(self.layers):
            return self.layers[self.active_layer_index]
        return None

    def set_layer_visibility(self, index: int, visible: bool):
        """Đặt trạng thái hiển thị layer"""
        if 0 <= index < len(self.layers):
            self.layers[index].visible = visible

    def set_layer_opacity(self, index: int, opacity: float):
        """Đặt độ trong suốt layer (0.0 - 1.0)"""
        if 0 <= index < len(self.layers):
            self.layers[index].opacity = max(0.0, min(1.0, opacity))

    def merge_visible_layers(self) -> QImage:
        """Gộp tất cả layers hiển thị thành một ảnh"""
        result = QImage(self.width, self.height, QImage.Format_ARGB32_Premultiplied)
        result.fill(Qt.transparent)

        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing, True)

        for layer in self.layers:
            if layer.visible:
                painter.setOpacity(layer.opacity)
                # TODO: Implement blend modes nếu cần
                painter.drawImage(0, 0, layer.image)

        painter.end()
        return result

    def duplicate_layer(self, index: int) -> Optional[int]:
        """Nhân đôi layer tại index"""
        if not (0 <= index < len(self.layers)):
            return None

        original = self.layers[index]
        if original.metadata.get("is_background", False):
            return None  # Không nhân đôi background

        # Tạo bản sao
        new_image = original.image.copy()
        new_layer = Layer(
            name=f"{original.name} Copy",
            image=new_image,
            visible=original.visible,
            opacity=original.opacity,
            blend_mode=original.blend_mode,
            locked=original.locked,
            metadata=original.metadata.copy()
        )

        # Thêm vào vị trí sau layer gốc
        self.layers.insert(index + 1, new_layer)
        return index + 1