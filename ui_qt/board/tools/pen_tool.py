from __future__ import annotations
from typing import List, Tuple
from PySide6 import QtCore, QtGui
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter, QPen, QColor
from ui_qt.board.core.data_models import Stroke


class PenTool:
    """Công cụ bút vẽ nâng cao với hỗ trợ pressure sensitivity và line smoothing"""

    def __init__(self, win: 'DrawingBoardWindowQt'):
        self.win = win
        self._pts: List[QPointF] = []
        self._pressures: List[float] = []  # Lưu áp lực từng điểm
        self._smoothing_enabled = True
        self._min_distance = 2.0  # Khoảng cách tối thiểu giữa các điểm

    def on_activate(self):
        self._pts.clear()
        self._pressures.clear()

    def on_deactivate(self):
        self._pts.clear()
        self._pressures.clear()

    def _get_pressure(self, e: QtGui.QMouseEvent) -> float:
        """Lấy áp lực từ tablet event, fallback về 1.0 cho mouse"""
        # Kiểm tra nếu là tablet event
        if hasattr(e, 'pressure'):
            return max(0.1, min(1.0, e.pressure()))
        return 1.0

    def _should_add_point(self, new_point: QPointF) -> bool:
        """Kiểm tra có nên thêm điểm mới không (dựa vào khoảng cách)"""
        if not self._pts:
            return True

        last_point = self._pts[-1]
        distance = ((new_point.x() - last_point.x()) ** 2 +
                    (new_point.y() - last_point.y()) ** 2) ** 0.5
        return distance >= self._min_distance

    def _smooth_path(self, points: List[QPointF]) -> List[QPointF]:
        """Làm mượt đường vẽ bằng Bezier curves"""
        if len(points) < 3:
            return points

        smoothed = [points[0]]

        for i in range(1, len(points) - 1):
            # Sử dụng điểm trung bình của 3 điểm liên tiếp
            prev_pt = points[i - 1]
            curr_pt = points[i]
            next_pt = points[i + 1]

            smooth_x = (prev_pt.x() + curr_pt.x() + next_pt.x()) / 3.0
            smooth_y = (prev_pt.y() + curr_pt.y() + next_pt.y()) / 3.0

            smoothed.append(QPointF(smooth_x, smooth_y))

        smoothed.append(points[-1])
        return smoothed

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() != Qt.LeftButton:
            return

        # Lưu state cho undo trước khi bắt đầu vẽ
        self.win.state.save_state_for_undo()

        point = QPointF(e.position())
        pressure = self._get_pressure(e)

        self._pts = [point]
        self._pressures = [pressure]

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if not self._pts or not (e.buttons() & Qt.LeftButton):
            return

        new_point = QPointF(e.position())

        # Chỉ thêm điểm nếu đủ xa điểm trước
        if not self._should_add_point(new_point):
            return

        pressure = self._get_pressure(e)
        self._pts.append(new_point)
        self._pressures.append(pressure)

        # Vẽ real-time với pressure-sensitive width
        self._draw_incremental()
        self.win.canvas.optimized_update()

    def _draw_incremental(self):
        """Vẽ thêm đoạn mới của nét"""
        if len(self._pts) < 2:
            return

        p = QPainter(self.win.canvas._ink)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)

        # Vẽ từ điểm gần cuối đến điểm cuối với pressure
        start_idx = max(0, len(self._pts) - 2)
        for i in range(start_idx, len(self._pts) - 1):
            pressure = self._pressures[i]
            width = max(1, int(self.win.pen_width * pressure))

            color = QColor(*self.win.pen_rgba)
            pen = QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            p.setPen(pen)
            p.drawLine(self._pts[i], self._pts[i + 1])

        p.end()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if e.button() != Qt.LeftButton or len(self._pts) < 2:
            return

        # Apply smoothing nếu được bật
        final_points = self._smooth_path(self._pts) if self._smoothing_enabled else self._pts

        # Chuyển đổi sang format lưu trữ
        pts = [(pt.x(), pt.y()) for pt in final_points]
        pressures = self._pressures if len(self._pressures) == len(final_points) else [1.0] * len(final_points)

        # Tạo stroke với thông tin pressure
        stroke = Stroke(
            t="line",
            points=pts,
            rgba=self.win.pen_rgba,
            width=self.win.pen_width,
            mode="pen"
        )
        # Thêm metadata pressure nếu cần
        if hasattr(stroke, 'metadata'):
            stroke.metadata['pressures'] = pressures

        self.win.state.strokes().append(stroke)
        self._pts.clear()
        self._pressures.clear()

    def keyPressEvent(self, e: QtGui.QKeyEvent):
        key, mods = e.key(), e.modifiers()

        # Phím điều chỉnh độ dày bút
        if key in (Qt.Key_BracketLeft, Qt.Key_BracketRight):
            step = 5 if (mods & Qt.ShiftModifier) else 1
            self.win.adjust_pen_width(step if key == Qt.Key_BracketRight else -step)

        # Toggle smoothing với phím S
        elif key == Qt.Key_S and (mods & Qt.ControlModifier):
            self._smoothing_enabled = not self._smoothing_enabled
            # Thông báo trạng thái smoothing
            status = "bật" if self._smoothing_enabled else "tắt"
            print(f"Line smoothing: {status}")