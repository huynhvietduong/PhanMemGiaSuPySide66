from __future__ import annotations
from typing import Tuple
from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Qt

def create_width_menu(parent, kind: str, init_value: int, on_change) -> Tuple[QtWidgets.QMenu, QtWidgets.QSlider, QtWidgets.QLabel]:
    """Tạo popover độ dày (slider + các mốc nhanh)."""
    menu = QtWidgets.QMenu(parent)
    w = QtWidgets.QWidget(parent)
    vbox = QtWidgets.QVBoxLayout(w); vbox.setContentsMargins(8,8,8,8)

    label = QtWidgets.QLabel()
    label.setAlignment(Qt.AlignCenter); label.setStyleSheet("font-weight:600; padding:2px;")

    slider = QtWidgets.QSlider(Qt.Horizontal); slider.setRange(1,100)
    slider.setSingleStep(1); slider.setPageStep(5); slider.setFixedWidth(240)
    slider.setValue(init_value)
    label.setText(f"Độ dày {'Bút' if kind=='pen' else 'Tẩy'}: {init_value}px")

    quick = QtWidgets.QHBoxLayout(); quick.setSpacing(4)
    for val in [1,2,3,5,8,12,16,20,30,50,80]:
        b = QtWidgets.QToolButton(); b.setText(str(val)); b.setAutoRaise(True)
        b.clicked.connect(lambda _=False, v=val: on_change(int(v)))
        quick.addWidget(b)

    vbox.addWidget(label); vbox.addWidget(slider); vbox.addLayout(quick)
    act = QtWidgets.QWidgetAction(parent); act.setDefaultWidget(w); menu.addAction(act)

    slider.valueChanged.connect(lambda v: on_change(int(v)))
    return menu, slider, label
