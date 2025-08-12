from __future__ import annotations
from typing import List
from PySide6 import QtCore, QtGui
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter, QPen
from ui_qt.board.core.data_models import Stroke

class PenTool:
    def __init__(self, win: 'DrawingBoardWindowQt'):
        self.win = win
        self._pts: List[QPointF] = []

    def on_activate(self): self._pts.clear()
    def on_deactivate(self): self._pts.clear()

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() != Qt.LeftButton: return
        self._pts = [QPointF(e.position())]

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if not self._pts or not (e.buttons() & Qt.LeftButton): return
        self._pts.append(QPointF(e.position()))
        p = QPainter(self.win.canvas._ink)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        c = QtGui.QColor(*self.win.pen_rgba)
        p.setPen(QPen(c, self.win.pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        path = QtGui.QPainterPath(self._pts[0])
        for pt in self._pts[1:]: path.lineTo(pt)
        p.drawPath(path); p.end()
        self.win.canvas.update()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if e.button() != Qt.LeftButton or len(self._pts) < 2: return
        pts = [(pt.x(), pt.y()) for pt in self._pts]
        self.win.state.strokes().append(Stroke(t="line", points=pts,
                                               rgba=self.win.pen_rgba, width=self.win.pen_width, mode="pen"))
        self._pts.clear()

    def keyPressEvent(self, e: QtGui.QKeyEvent):
        key, mods = e.key(), e.modifiers()
        if key in (Qt.Key_BracketLeft, Qt.Key_BracketRight):
            step = 5 if (mods & Qt.ShiftModifier) else 1
            self.win.adjust_pen_width(step if key == Qt.Key_BracketRight else -step)
