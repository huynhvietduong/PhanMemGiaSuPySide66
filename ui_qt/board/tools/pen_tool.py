from __future__ import annotations
from typing import List
from PySide6 import QtCore, QtGui
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter, QPen, QColor
from ui_qt.board.core.data_models import Stroke


class PenTool:
    """Công cụ bút vẽ với hỗ trợ brush effects"""

    def __init__(self, win: 'DrawingBoardWindowQt'):
        self.win = win
        self._pts: List[QPointF] = []
        self._current_brush_effect = "smooth"  # Default effect
        self._min_distance = 2.0  # Khoảng cách tối thiểu giữa các điểm

    def on_activate(self):
        self._pts.clear()

    def on_deactivate(self):
        self._pts.clear()

    def set_brush_effect(self, effect: str):
        """Đặt hiệu ứng brush"""
        self._current_brush_effect = effect

    def _should_add_point(self, new_point: QPointF) -> bool:
        """Kiểm tra có nên thêm điểm mới không (dựa vào khoảng cách)"""
        if not self._pts:
            return True

        last_point = self._pts[-1]
        distance = ((new_point.x() - last_point.x()) ** 2 +
                    (new_point.y() - last_point.y()) ** 2) ** 0.5
        return distance >= self._min_distance

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() != Qt.LeftButton:
            return

        # Lưu state cho undo nếu method tồn tại
        try:
            if hasattr(self.win.state, 'save_state_for_undo'):
                self.win.state.save_state_for_undo()
        except Exception:
            pass  # Bỏ qua nếu chưa implement undo

        self._pts = [QPointF(e.position())]

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if not self._pts or not (e.buttons() & Qt.LeftButton):
            return

        new_point = QPointF(e.position())

        # Chỉ thêm điểm nếu đủ xa điểm trước
        if not self._should_add_point(new_point):
            return

        self._pts.append(new_point)

        # Vẽ real-time với brush effect
        self._draw_with_effect()
        self.win.canvas.update()

    def _draw_with_effect(self):
        """Vẽ với hiệu ứng brush"""
        if len(self._pts) < 2:
            return

        painter = QPainter(self.win.canvas._ink)
        color = QColor(*self.win.pen_rgba)
        width = self.win.pen_width

        # Sử dụng brush effects nếu có
        try:
            from ui_qt.board.tools.brush_effects import BrushEffects
            BrushEffects.draw_textured_stroke(painter, self._pts, width, color, self._current_brush_effect)
        except ImportError:
            # Fallback về smooth stroke nếu không có brush effects
            self._draw_smooth_stroke(painter, color, width)

        painter.end()

    def _draw_smooth_stroke(self, painter: QPainter, color: QColor, width: int):
        """Vẽ nét mượt cơ bản (fallback)"""
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        pen = QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)

        path = QtGui.QPainterPath(self._pts[0])
        for pt in self._pts[1:]:
            path.lineTo(pt)
        painter.drawPath(path)

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if e.button() != Qt.LeftButton or len(self._pts) < 2:
            return

        # Tạo stroke với metadata về brush effect
        pts = [(pt.x(), pt.y()) for pt in self._pts]
        stroke = Stroke(t="line", points=pts,
                        rgba=self.win.pen_rgba, width=self.win.pen_width, mode="pen")

        # Thêm metadata về brush effect nếu cần
        if hasattr(stroke, 'metadata'):
            stroke.metadata = {"brush_effect": self._current_brush_effect}

        self.win.state.strokes().append(stroke)
        self._pts.clear()

    def keyPressEvent(self, e: QtGui.QKeyEvent):
        key, mods = e.key(), e.modifiers()

        # Phím điều chỉnh độ dày bút
        if key in (Qt.Key_BracketLeft, Qt.Key_BracketRight):
            step = 5 if (mods & Qt.ShiftModifier) else 1
            self.win.adjust_pen_width(step if key == Qt.Key_BracketRight else -step)

        # Phím nhanh chuyển brush effect
        elif key == Qt.Key_1:
            self._current_brush_effect = "smooth"
        elif key == Qt.Key_2:
            self._current_brush_effect = "rough"
        elif key == Qt.Key_3:
            self._current_brush_effect = "soft"
        elif key == Qt.Key_4:
            self._current_brush_effect = "ink"
        elif key == Qt.Key_5:
            self._current_brush_effect = "chalk"
        elif key == Qt.Key_6:
            self._current_brush_effect = "watercolor"