from __future__ import annotations
from PySide6 import QtCore, QtGui
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPen, QPainter, QPainterPath
from ui_qt.board.core.data_models import Stroke
import math


class ShapeTool:
    """Công cụ vẽ hình dạng nâng cao"""

    def __init__(self, win: 'DrawingBoardWindowQt'):
        self.win = win
        self.kind = self.win.shape_kind
        self._start: QPointF | None = None
        self._end: QPointF | None = None
        self._control_points = []  # Cho các hình phức tạp

    def on_activate(self):
        self.kind = self.win.shape_kind

    def on_deactivate(self):
        self._start = self._end = None
        self._control_points.clear()

    def paint_overlay(self, p: QtGui.QPainter):
        """Vẽ preview shape đang tạo"""
        if not (self._start and self._end):
            return

        pen = QPen(QtGui.QColor(*self.win.pen_rgba), 1, Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)

        if self.kind == "line":
            p.drawLine(self._start, self._end)
        elif self.kind == "arrow":
            self._draw_arrow_preview(p)
        elif self.kind == "rect":
            r = QRectF(self._start, self._end).normalized()
            p.drawRect(r)
        elif self.kind == "oval":
            r = QRectF(self._start, self._end).normalized()
            p.drawEllipse(r)
        elif self.kind == "triangle":
            self._draw_triangle_preview(p)
        elif self.kind == "star":
            self._draw_star_preview(p)
        elif self.kind == "polygon":
            self._draw_polygon_preview(p)

    def _draw_arrow_preview(self, p: QPainter):
        """Vẽ preview mũi tên"""
        line = QtCore.QLineF(self._start, self._end)
        if line.length() < 10:
            return

        # Vẽ thân mũi tên
        p.drawLine(line)

        # Vẽ đầu mũi tên
        arrow_head_size = min(20, line.length() / 3)
        angle = math.radians(line.angle())

        # Tính toán 2 điểm của đầu mũi tên
        head_angle = math.pi / 6  # 30 degrees
        p1_x = self._end.x() - arrow_head_size * math.cos(angle - head_angle)
        p1_y = self._end.y() + arrow_head_size * math.sin(angle - head_angle)
        p2_x = self._end.x() - arrow_head_size * math.cos(angle + head_angle)
        p2_y = self._end.y() + arrow_head_size * math.sin(angle + head_angle)

        p.drawLine(self._end, QPointF(p1_x, p1_y))
        p.drawLine(self._end, QPointF(p2_x, p2_y))

    def _draw_triangle_preview(self, p: QPainter):
        """Vẽ preview tam giác"""
        center = QPointF((self._start.x() + self._end.x()) / 2, self._start.y())
        triangle = [self._start, center, self._end]
        p.drawPolygon(triangle)

    def _draw_star_preview(self, p: QPainter):
        """Vẽ preview ngôi sao 5 cánh"""
        center_x = (self._start.x() + self._end.x()) / 2
        center_y = (self._start.y() + self._end.y()) / 2
        radius = min(abs(self._end.x() - self._start.x()), abs(self._end.y() - self._start.y())) / 2

        if radius < 5:
            return

        star_points = []
        for i in range(10):  # 5 outer + 5 inner points
            angle = i * math.pi / 5
            r = radius if i % 2 == 0 else radius * 0.4
            x = center_x + r * math.cos(angle - math.pi / 2)
            y = center_y + r * math.sin(angle - math.pi / 2)
            star_points.append(QPointF(x, y))

        p.drawPolygon(star_points)

    def _draw_polygon_preview(self, p: QPainter):
        """Vẽ preview polygon (hexagon mặc định)"""
        center_x = (self._start.x() + self._end.x()) / 2
        center_y = (self._start.y() + self._end.y()) / 2
        radius = min(abs(self._end.x() - self._start.x()), abs(self._end.y() - self._start.y())) / 2

        if radius < 5:
            return

        sides = 6  # Hexagon
        polygon_points = []
        for i in range(sides):
            angle = 2 * math.pi * i / sides
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            polygon_points.append(QPointF(x, y))

        p.drawPolygon(polygon_points)

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() != Qt.LeftButton:
            return

        # Lưu state cho undo
        self.win.state.save_state_for_undo()

        self._start = self._end = QPointF(e.position())

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if not self._start:
            return

        end = QPointF(e.position())

        # Xử lý Shift để tạo hình vuông/tròn đều
        if self.kind in ("rect", "oval") and (e.modifiers() & Qt.ShiftModifier):
            dx = end.x() - self._start.x()
            dy = end.y() - self._start.y()
            size = max(abs(dx), abs(dy))
            sx = 1 if dx >= 0 else -1
            sy = 1 if dy >= 0 else -1
            end = QPointF(self._start.x() + sx * size, self._start.y() + sy * size)

        self._end = end
        self.win.canvas.update()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if e.button() != Qt.LeftButton or not (self._start and self._end):
            return

        # Tạo stroke tương ứng với shape type
        if self.kind in ("line", "rect", "oval"):
            # Shapes đơn giản với 2 điểm
            pts = [(self._start.x(), self._start.y()), (self._end.x(), self._end.y())]
        elif self.kind == "arrow":
            pts = self._create_arrow_points()
        elif self.kind == "triangle":
            pts = self._create_triangle_points()
        elif self.kind == "star":
            pts = self._create_star_points()
        elif self.kind == "polygon":
            pts = self._create_polygon_points()
        else:
            pts = [(self._start.x(), self._start.y()), (self._end.x(), self._end.y())]

        stroke = Stroke(
            t=self.kind,
            points=pts,
            rgba=self.win.pen_rgba,
            width=self.win.pen_width,
            mode="pen"
        )

        self.win.state.strokes().append(stroke)
        self._start = self._end = None
        self._control_points.clear()
        self.win._refresh_ink()

    def _create_arrow_points(self):
        """Tạo points cho mũi tên"""
        points = [(self._start.x(), self._start.y()), (self._end.x(), self._end.y())]

        # Thêm points cho đầu mũi tên
        line = QtCore.QLineF(self._start, self._end)
        if line.length() >= 10:
            arrow_head_size = min(20, line.length() / 3)
            angle = math.radians(line.angle())
            head_angle = math.pi / 6

            p1_x = self._end.x() - arrow_head_size * math.cos(angle - head_angle)
            p1_y = self._end.y() + arrow_head_size * math.sin(angle - head_angle)
            p2_x = self._end.x() - arrow_head_size * math.cos(angle + head_angle)
            p2_y = self._end.y() + arrow_head_size * math.sin(angle + head_angle)

            points.extend([
                (self._end.x(), self._end.y()),
                (p1_x, p1_y),
                (self._end.x(), self._end.y()),
                (p2_x, p2_y)
            ])

        return points

    def _create_triangle_points(self):
        """Tạo points cho tam giác"""
        center = QPointF((self._start.x() + self._end.x()) / 2, self._start.y())
        return [
            (self._start.x(), self._start.y()),
            (center.x(), center.y()),
            (self._end.x(), self._end.y()),
            (self._start.x(), self._start.y())  # Đóng hình
        ]

    def _create_star_points(self):
        """Tạo points cho ngôi sao"""
        center_x = (self._start.x() + self._end.x()) / 2
        center_y = (self._start.y() + self._end.y()) / 2
        radius = min(abs(self._end.x() - self._start.x()), abs(self._end.y() - self._start.y())) / 2

        points = []
        for i in range(10):
            angle = i * math.pi / 5
            r = radius if i % 2 == 0 else radius * 0.4
            x = center_x + r * math.cos(angle - math.pi / 2)
            y = center_y + r * math.sin(angle - math.pi / 2)
            points.append((x, y))

        points.append(points[0])  # Đóng hình
        return points

    def _create_polygon_points(self):
        """Tạo points cho polygon"""
        center_x = (self._start.x() + self._end.x()) / 2
        center_y = (self._start.y() + self._end.y()) / 2
        radius = min(abs(self._end.x() - self._start.x()), abs(self._end.y() - self._start.y())) / 2

        sides = 6  # Hexagon
        points = []
        for i in range(sides):
            angle = 2 * math.pi * i / sides
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            points.append((x, y))

        points.append(points[0])  # Đóng hình
        return points

    def keyPressEvent(self, e: QtGui.QKeyEvent):
        """Xử lý phím tắt cho shape tool"""
        key = e.key()

        # Phím số để chọn shape nhanh
        if key == Qt.Key_1:
            self.win.shape_kind = "line"
        elif key == Qt.Key_2:
            self.win.shape_kind = "rect"
        elif key == Qt.Key_3:
            self.win.shape_kind = "oval"
        elif key == Qt.Key_4:
            self.win.shape_kind = "arrow"
        elif key == Qt.Key_5:
            self.win.shape_kind = "triangle"
        elif key == Qt.Key_6:
            self.win.shape_kind = "star"
        elif key == Qt.Key_7:
            self.win.shape_kind = "polygon"

        if key in (Qt.Key_1, Qt.Key_2, Qt.Key_3, Qt.Key_4, Qt.Key_5, Qt.Key_6, Qt.Key_7):
            self.kind = self.win.shape_kind
            # Cập nhật toolbar
            self.win.toolbar.reflect_shape_change(self.kind)
