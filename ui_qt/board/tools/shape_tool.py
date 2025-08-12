from __future__ import annotations
from PySide6 import QtCore, QtGui
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPen
from ui_qt.board.core.data_models import Stroke

class ShapeTool:
    def __init__(self, win: 'DrawingBoardWindowQt'):
        self.win = win
        self.kind = self.win.shape_kind
        self._start: QPointF | None = None
        self._end:   QPointF | None = None

    def on_activate(self): self.kind = self.win.shape_kind
    def on_deactivate(self): self._start = self._end = None

    def paint_overlay(self, p: QtGui.QPainter):
        if not (self._start and self._end): return
        pen = QPen(QtGui.QColor(*self.win.pen_rgba), 1, Qt.DashLine); p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        if self.kind == "line": p.drawLine(self._start, self._end)
        else:
            r = QRectF(self._start, self._end).normalized()
            (p.drawRect if self.kind=="rect" else p.drawEllipse)(r)

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() != Qt.LeftButton: return
        self._start = self._end = QPointF(e.position())

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if not self._start: return
        end = QPointF(e.position())
        if self.kind in ("rect","oval") and (e.modifiers() & Qt.ShiftModifier):
            dx = end.x()-self._start.x(); dy = end.y()-self._start.y()
            m = max(abs(dx), abs(dy)); sx = 1 if dx>=0 else -1; sy = 1 if dy>=0 else -1
            end = QPointF(self._start.x()+sx*m, self._start.y()+sy*m)
        self._end = end; self.win.canvas.update()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if e.button() != Qt.LeftButton or not (self._start and self._end): return
        pts = [(self._start.x(), self._start.y()), (self._end.x(), self._end.y())]
        self.win.state.strokes().append(Stroke(t=self.kind, points=pts,
                                               rgba=self.win.pen_rgba, width=self.win.pen_width, mode="pen"))
        self._start = self._end = None; self.win._refresh_ink()

    def keyPressEvent(self, e: QtGui.QKeyEvent): ...
