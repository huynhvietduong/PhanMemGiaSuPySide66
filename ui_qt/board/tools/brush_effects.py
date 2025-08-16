# Tạo file mới: board/tools/brush_effects.py
from __future__ import annotations
import math
import random
from typing import List, Tuple
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QRadialGradient, QPainterPath


class BrushEffects:
    """Các hiệu ứng brush nâng cao"""

    @staticmethod
    def draw_textured_stroke(painter: QPainter, points: List[QPointF],
                             width: int, color: QColor, texture_type: str):
        """Vẽ nét với texture đa dạng"""

        if texture_type == "rough":
            BrushEffects._draw_rough_stroke(painter, points, width, color)
        elif texture_type == "soft":
            BrushEffects._draw_soft_stroke(painter, points, width, color)
        elif texture_type == "ink":
            BrushEffects._draw_ink_stroke(painter, points, width, color)
        elif texture_type == "chalk":
            BrushEffects._draw_chalk_stroke(painter, points, width, color)
        elif texture_type == "watercolor":
            BrushEffects._draw_watercolor_stroke(painter, points, width, color)
        else:
            # Default smooth stroke
            BrushEffects._draw_smooth_stroke(painter, points, width, color)

    @staticmethod
    def _draw_rough_stroke(painter: QPainter, points: List[QPointF], width: int, color: QColor):
        """Hiệu ứng nét gồ ghề như bút chì"""
        painter.setRenderHint(QPainter.Antialiasing, False)  # Tắt antialiasing cho hiệu ứng rough

        for i in range(len(points) - 1):
            # Thêm nhiễu ngẫu nhiên vào độ dày và vị trí
            noise_width = random.randint(-2, 2)
            noise_x = random.uniform(-1, 1)
            noise_y = random.uniform(-1, 1)

            current_width = max(1, width + noise_width)

            # Điểm với nhiễu
            noisy_start = QPointF(points[i].x() + noise_x, points[i].y() + noise_y)
            noisy_end = QPointF(points[i + 1].x() + noise_x, points[i + 1].y() + noise_y)

            # Màu với độ đậm nhạt ngẫu nhiên
            alpha_noise = random.randint(-30, 30)
            rough_color = QColor(color.red(), color.green(), color.blue(),
                                 max(50, min(255, color.alpha() + alpha_noise)))

            pen = QPen(rough_color, current_width, Qt.SolidLine, Qt.RoundCap)
            painter.setPen(pen)
            painter.drawLine(noisy_start, noisy_end)

    @staticmethod
    def _draw_soft_stroke(painter: QPainter, points: List[QPointF], width: int, color: QColor):
        """Hiệu ứng nét mềm với gradient"""
        painter.setRenderHint(QPainter.Antialiasing, True)

        for i in range(len(points) - 1):
            # Tạo gradient radial cho hiệu ứng mềm
            center = QPointF((points[i].x() + points[i + 1].x()) / 2,
                             (points[i].y() + points[i + 1].y()) / 2)

            gradient = QRadialGradient(center, width / 2)

            # Màu đậm ở giữa, mờ dần ra ngoài
            solid_color = QColor(color.red(), color.green(), color.blue(), color.alpha())
            transparent_color = QColor(color.red(), color.green(), color.blue(), 0)

            gradient.setColorAt(0, solid_color)
            gradient.setColorAt(0.7, solid_color)
            gradient.setColorAt(1, transparent_color)

            brush = QBrush(gradient)
            painter.setBrush(brush)
            painter.setPen(Qt.NoPen)

            # Vẽ ellipse tại mỗi điểm
            painter.drawEllipse(center, width / 2, width / 2)

    @staticmethod
    def _draw_ink_stroke(painter: QPainter, points: List[QPointF], width: int, color: QColor):
        """Hiệu ứng mực với độ đậm nhạt thay đổi"""
        painter.setRenderHint(QPainter.Antialiasing, True)

        for i in range(len(points) - 1):
            # Độ đậm thay đổi dựa trên tốc độ vẽ
            if i > 0:
                dist1 = math.sqrt((points[i].x() - points[i - 1].x()) ** 2 +
                                  (points[i].y() - points[i - 1].y()) ** 2)
                dist2 = math.sqrt((points[i + 1].x() - points[i].x()) ** 2 +
                                  (points[i + 1].y() - points[i].y()) ** 2)

                # Tốc độ cao -> nét nhạt, tốc độ thấp -> nét đậm
                speed = (dist1 + dist2) / 2
                alpha_factor = max(0.3, min(1.0, 10 / (speed + 1)))
            else:
                alpha_factor = 1.0

            ink_color = QColor(color.red(), color.green(), color.blue(),
                               int(color.alpha() * alpha_factor))

            pen = QPen(ink_color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(points[i], points[i + 1])

    @staticmethod
    def _draw_chalk_stroke(painter: QPainter, points: List[QPointF], width: int, color: QColor):
        """Hiệu ứng phấn với texture hạt"""
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Vẽ nét chính
        main_pen = QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(main_pen)

        path = QPainterPath()
        if points:
            path.moveTo(points[0])
            for point in points[1:]:
                path.lineTo(point)
        painter.drawPath(path)

        # Thêm texture hạt phấn
        for i in range(0, len(points), 3):  # Sparse points
            for _ in range(random.randint(2, 5)):  # Multiple dots per point
                offset_x = random.uniform(-width / 2, width / 2)
                offset_y = random.uniform(-width / 2, width / 2)
                dot_pos = QPointF(points[i].x() + offset_x, points[i].y() + offset_y)

                # Màu hạt ngẫu nhiên
                grain_alpha = random.randint(30, 100)
                grain_color = QColor(color.red(), color.green(), color.blue(), grain_alpha)

                painter.setPen(QPen(grain_color, 1))
                painter.drawPoint(dot_pos)

    @staticmethod
    def _draw_watercolor_stroke(painter: QPainter, points: List[QPointF], width: int, color: QColor):
        """Hiệu ứng màu nước với bleeding effect"""
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Vẽ nhiều layer với opacity khác nhau
        layers = [
            (width * 1.5, 0.2),  # Layer ngoài, rất mờ
            (width * 1.2, 0.3),  # Layer giữa
            (width * 0.8, 0.5),  # Layer trong
        ]

        for layer_width, opacity in layers:
            layer_color = QColor(color.red(), color.green(), color.blue(),
                                 int(color.alpha() * opacity))

            pen = QPen(layer_color, int(layer_width), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)

            # Vẽ path với offset nhỏ cho hiệu ứng bleeding
            for i in range(len(points) - 1):
                offset_x = random.uniform(-1, 1)
                offset_y = random.uniform(-1, 1)

                start = QPointF(points[i].x() + offset_x, points[i].y() + offset_y)
                end = QPointF(points[i + 1].x() + offset_x, points[i + 1].y() + offset_y)

                painter.drawLine(start, end)

    @staticmethod
    def _draw_smooth_stroke(painter: QPainter, points: List[QPointF], width: int, color: QColor):
        """Nét mượt chuẩn"""
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)

        if len(points) >= 2:
            path = QPainterPath()
            path.moveTo(points[0])

            # Sử dụng quadratic curves cho smooth
            for i in range(1, len(points)):
                if i < len(points) - 1:
                    # Control point là trung điểm
                    control = QPointF((points[i].x() + points[i + 1].x()) / 2,
                                      (points[i].y() + points[i + 1].y()) / 2)
                    path.quadTo(points[i], control)
                else:
                    path.lineTo(points[i])

            painter.drawPath(path)