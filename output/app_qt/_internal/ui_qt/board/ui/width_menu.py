# ui_qt/board/ui/width_menu.py
from __future__ import annotations
from typing import Callable, Tuple
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt


def create_width_menu(parent, tool_name: str, init_value: int, callback: Callable[[int], None]) -> Tuple[
    QtWidgets.QMenu, QtWidgets.QSlider, QtWidgets.QLabel]:
    """
    Tạo menu popup chọn độ dày cho pen/eraser

    Returns:
        Tuple[QMenu, QSlider, QLabel] - Menu, slider, và label để parent có thể tham chiếu
    """
    menu = QtWidgets.QMenu(parent)

    # Widget container
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(8)

    # Label hiển thị giá trị
    label = QtWidgets.QLabel(f"Độ dày {tool_name.title()}: {init_value}px")
    label.setAlignment(Qt.AlignCenter)
    layout.addWidget(label)

    # Slider chọn độ dày
    slider = QtWidgets.QSlider(Qt.Horizontal)
    slider.setMinimum(1)
    slider.setMaximum(100)
    slider.setValue(init_value)
    slider.setFixedWidth(200)
    layout.addWidget(slider)

    # Buttons cho các giá trị thường dùng
    buttons_layout = QtWidgets.QHBoxLayout()
    common_values = [1, 2, 4, 6, 8, 12, 16, 20, 30] if tool_name == "pen" else [10, 20, 30, 40, 50, 60, 80, 100]

    for value in common_values:
        btn = QtWidgets.QPushButton(str(value))
        btn.setFixedSize(30, 25)
        btn.clicked.connect(lambda checked=False, v=value: slider.setValue(v))
        buttons_layout.addWidget(btn)

    layout.addLayout(buttons_layout)

    # Kết nối slider với callback
    slider.valueChanged.connect(callback)

    # Tạo action và thêm vào menu
    action = QtWidgets.QWidgetAction(parent)
    action.setDefaultWidget(widget)
    menu.addAction(action)

    return menu, slider, label