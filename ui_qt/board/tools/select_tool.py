from __future__ import annotations
from typing import Optional
from PySide6 import QtCore, QtGui
from PySide6.QtCore import Qt, QRectF

class SelectTool:
    HANDLE = 10
    def __init__(self, win: 'DrawingBoardWindowQt'):
        self.win = win
        self._sel: Optional[int] = None
        self._drag_idx: Optional[int] = None
        self._drag_handle: Optional[str] = None
        self._drag_offset = QtCore.QPoint()

    def on_activate(self): ...
    def on_deactivate(self): self._drag_idx = None; self._drag_handle = None

    def paint_overlay(self, p: QtGui.QPainter):
        if self._sel is None: return
        img = self.win.state.images()[self._sel]
        rect = QtCore.QRect(img.x, img.y, img.w, img.h)
        p.setPen(QtGui.QPen(Qt.black, 1, Qt.DashLine)); p.setBrush(Qt.NoBrush); p.drawRect(rect)
        for r in self._handles(QRectF(rect)).values(): p.fillRect(r, Qt.black)

    def _handles(self, rect: QRectF):
        s = self.HANDLE
        cx = int((rect.left()+rect.right())/2); cy = int((rect.top()+rect.bottom())/2)
        return {
            "tl": QtCore.QRect(int(rect.left())-s//2,  int(rect.top())-s//2,     s, s),
            "tr": QtCore.QRect(int(rect.right())-s//2, int(rect.top())-s//2,     s, s),
            "bl": QtCore.QRect(int(rect.left())-s//2,  int(rect.bottom())-s//2,  s, s),
            "br": QtCore.QRect(int(rect.right())-s//2, int(rect.bottom())-s//2,  s, s),
            "t":  QtCore.QRect(cx - s//2,              int(rect.top())-s//2,     s, s),
            "b":  QtCore.QRect(cx - s//2,              int(rect.bottom())-s//2,  s, s),
            "l":  QtCore.QRect(int(rect.left())-s//2,  cy - s//2,                 s, s),
            "r":  QtCore.QRect(int(rect.right())-s//2, cy - s//2,                 s, s),
        }

    def _hit_image(self, pos: QtCore.QPoint) -> Optional[int]:
        for i in range(len(self.win.state.images())-1, -1, -1):
            im = self.win.state.images()[i]
            if QtCore.QRect(im.x, im.y, im.w, im.h).contains(pos): return i
        return None

    def _hit_handle(self, idx: int, pos: QtCore.QPoint) -> Optional[str]:
        im = self.win.state.images()[idx]
        rect = QRectF(im.x, im.y, im.w, im.h)
        for name, r in self._handles(rect).items():
            if r.contains(pos): return name
        return None

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() != Qt.LeftButton: return
        pos = e.position().toPoint()
        idx = self._hit_image(pos)
        if idx is not None:
            self._sel = idx
            h = self._hit_handle(idx, pos)
            if h:
                self._drag_idx, self._drag_handle = idx, h
            else:
                self._drag_idx, self._drag_handle = idx, None
                im = self.win.state.images()[idx]
                self._drag_offset = pos - QtCore.QPoint(im.x, im.y)
        else:
            self._sel = None; self._drag_idx = None; self._drag_handle = None
        self.win.canvas.update()

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if self._drag_idx is None: return
        pos = e.position().toPoint()
        im = self.win.state.images()[self._drag_idx]
        if self._drag_handle:
            l,t,r,b = im.x, im.y, im.x+im.w, im.y+im.h
            if "t" in self._drag_handle: t = pos.y()
            if "b" in self._drag_handle: b = pos.y()
            if "l" in self._drag_handle: l = pos.x()
            if "r" in self._drag_handle: r = pos.x()
            x0,x1 = sorted([l,r]); y0,y1 = sorted([t,b])
            if e.modifiers() & Qt.ShiftModifier:
                w = x1-x0; h=y1-y0; side = max(2, int(max(abs(w),abs(h))))
                x1 = x0+side if r>=l else x0-side
                y1 = y0+side if b>=t else y0-side
            im.x, im.y = int(x0), int(y0); im.w, im.h = max(2,int(x1-x0)), max(2,int(y1-y0))
        else:
            tl = pos - self._drag_offset; im.x, im.y = int(tl.x()), int(tl.y())
        self.win.canvas.update()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if e.button() != Qt.LeftButton: return
        self._drag_idx = None; self._drag_handle = None

    def keyPressEvent(self, e: QtGui.QKeyEvent):
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            if self._sel is not None and self._sel < len(self.win.state.images()):
                self.win.state.images().pop(self._sel); self._sel = None; self.win._refresh_ink()
