from __future__ import annotations
from typing import List, Tuple
from PySide6 import QtCore, QtGui
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPen
from ui_qt.board.core.data_models import Stroke

class EraseAreaTool:
    def __init__(self, win: 'DrawingBoardWindowQt'):
        self.win = win
        self.mode = self.win.erase_area_mode  # "rect" | "lasso"
        self._start: QPointF | None = None
        self._end:   QPointF | None = None
        self._lasso: List[QPointF] = []

    def on_activate(self): self.mode = self.win.erase_area_mode
    def on_deactivate(self): self._start = self._end = None; self._lasso.clear()

    def paint_overlay(self, p: QtGui.QPainter):
        p.setPen(QPen(Qt.red, 1, Qt.DashLine))
        shade = QtGui.QColor(255,0,0,60); p.setBrush(shade)
        if self.mode == "rect" and self._start and self._end:
            r = QRectF(self._start, self._end).normalized(); p.drawRect(r); p.fillRect(r, shade)
        if self.mode == "lasso" and len(self._lasso)>1:
            path = QtGui.QPainterPath(self._lasso[0])
            for pt in self._lasso[1:]: path.lineTo(pt)
            p.drawPath(path); p.fillPath(path, shade)

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() != Qt.LeftButton: return
        if self.mode == "rect":
            self._start = QPointF(e.position()); self._end = QPointF(e.position())
        else:
            self._lasso = [QPointF(e.position())]

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if self.mode == "rect" and self._start:
            end = QPointF(e.position())
            if e.modifiers() & Qt.ShiftModifier:
                dx = end.x()-self._start.x(); dy = end.y()-self._start.y()
                m = max(abs(dx), abs(dy)); sx = 1 if dx>=0 else -1; sy = 1 if dy>=0 else -1
                end = QPointF(self._start.x()+sx*m, self._start.y()+sy*m)
            self._end = end; self.win.canvas.update()
        elif self.mode == "lasso" and self._lasso and (e.buttons() & Qt.LeftButton):
            self._lasso.append(QPointF(e.position())); self.win.canvas.update()

    def _apply(self, path: QtGui.QPainterPath):
        p = QtGui.QPainter(self.win.canvas._ink)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        p.setCompositionMode(QtGui.QPainter.CompositionMode_Clear)
        p.fillPath(path, Qt.black); p.end()

        # Lưu stroke polygon để rebuild
        pts: List[Tuple[float,float]] = [(pt.x(), pt.y()) for pt in path.toFillPolygon()]
        if len(pts) >= 3:
            self.win.state.strokes().append(Stroke(t="poly", points=pts, rgba=(0,0,0,0), width=0, mode="eraser"))
        self.win._refresh_ink()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if e.button() != Qt.LeftButton: return
        if self.mode == "rect" and self._start and self._end:
            r = QRectF(self._start, self._end).normalized()
            path = QtGui.QPainterPath(); path.addRect(r); self._apply(path)
            self._start = self._end = None
        elif self.mode == "lasso" and len(self._lasso) >= 3:
            path = QtGui.QPainterPath(self._lasso[0])
            for pt in self._lasso[1:]: path.lineTo(pt)
            path.closeSubpath(); self._apply(path); self._lasso.clear()

    def keyPressEvent(self, e: QtGui.QKeyEvent): ...
