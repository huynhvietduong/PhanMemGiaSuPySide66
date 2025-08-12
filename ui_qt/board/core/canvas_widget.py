from __future__ import annotations
from typing import Optional
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage, QPainter

def _resolve_scroll_area(obj):
    sa = getattr(obj, "scroll", None)
    if callable(sa) or sa is None:
        sa = getattr(obj, "scroll_area", None)
    return sa

class CanvasWidget(QtWidgets.QWidget):
    """Canvas trung lập: vẽ ảnh + lớp mực, chuyển sự kiện cho tool hiện tại, gọi paint_overlay nếu có."""
    def __init__(self, win: 'DrawingBoardWindowQt'):
        super().__init__(win)
        self.win = win
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.virtual_h = 4000
        self.virtual_w = 2000

        self._ink = QImage(self.virtual_w, self.virtual_h, QImage.Format_ARGB32_Premultiplied)
        self._ink.fill(Qt.transparent)
        self.setMinimumSize(self.virtual_w, self.virtual_h)

    # ---- infra ----
    def _ensure_size(self):
        parent = self.parent()
        sa = _resolve_scroll_area(parent) if parent else None
        if sa is None or not hasattr(sa, "viewport"):
            return
        vieww = sa.viewport().width()
        if vieww <= 0: return
        if self.virtual_w != vieww:
            self.virtual_w = vieww
            new_img = QImage(self.virtual_w, self.virtual_h, QImage.Format_ARGB32_Premultiplied)
            new_img.fill(Qt.transparent)
            parent._rebuild_into(new_img)   # nhờ Window → BoardState vẽ lại
            self._ink = new_img
        self.setMinimumSize(self.virtual_w, self.virtual_h)

    def sizeHint(self) -> QtCore.QSize: return QSize(self.virtual_w, self.virtual_h)

    # ---- paint ----
    def paintEvent(self, e: QtGui.QPaintEvent):
        self._ensure_size()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.fillRect(self.rect(), Qt.white)

        # a) Ảnh (images)
        for img in self.win.state.images():
            dest = QtCore.QRect(img.x, img.y, img.w, img.h)
            p.drawImage(dest, img.qimage)

        # b) Lớp mực
        p.drawImage(0, 0, self._ink)

        # c) Overlay của tool (preview)
        try:
            preview = getattr(self.win.current_tool_obj, "paint_overlay", None)
            if callable(preview): preview(p)
        except Exception:
            pass
        p.end()

    # ---- events → forward cho tool hiện tại ----
    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if self.win.current_tool_obj: self.win.current_tool_obj.mousePressEvent(e)
    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if self.win.current_tool_obj: self.win.current_tool_obj.mouseMoveEvent(e)
    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if self.win.current_tool_obj: self.win.current_tool_obj.mouseReleaseEvent(e)
    def keyPressEvent(self, e: QtGui.QKeyEvent):
        if self.win.current_tool_obj: self.win.current_tool_obj.keyPressEvent(e)
        else: super().keyPressEvent(e)
