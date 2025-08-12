from __future__ import annotations
from typing import List, Dict
from PySide6 import QtCore, QtGui
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QPen
from ui_qt.board.core.data_models import Stroke, Img

class BoardState:
    """Quản lý dữ liệu bảng vẽ: trang, strokes, images, rebuild lớp mực."""
    def __init__(self):
        self.pages: List[Dict[str, list]] = []    # [{"strokes":[Stroke], "images":[Img]}]
        self.current_page: int = 0
        self.ensure_one_page()

    # --------- page helpers ----------
    def ensure_one_page(self):
        if not self.pages:
            self.pages.append({"strokes": [], "images": []})
            self.current_page = 0

    def page(self) -> Dict[str, list]: return self.pages[self.current_page]
    def strokes(self) -> List[Stroke]: return self.page()["strokes"]
    def images(self) -> List[Img]:     return self.page()["images"]

    # --------- pagination ----------
    def add_page_after(self):
        self.pages.insert(self.current_page + 1, {"strokes": [], "images": []})
        self.current_page += 1

    def del_current_page(self) -> bool:
        if len(self.pages) <= 1:
            return False
        self.pages.pop(self.current_page)
        self.current_page = max(0, self.current_page - 1)
        return True

    def next_page(self) -> bool:
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1; return True
        return False

    def prev_page(self) -> bool:
        if self.current_page > 0:
            self.current_page -= 1; return True
        return False

    # --------- rebuild ink ----------
    def rebuild_into(self, target_img: QImage):
        """Vẽ lại toàn bộ strokes của trang hiện tại vào QImage trong suốt (ink layer)."""
        target_img.fill(Qt.transparent)
        p = QPainter(target_img)
        p.setRenderHint(QPainter.Antialiasing, True)

        for s in self.strokes():
            if s.t == "line":
                if not s.points or len(s.points) < 2:
                    continue
                path = QtGui.QPainterPath(QtCore.QPointF(*s.points[0]))
                for pt in s.points[1:]:
                    path.lineTo(QtCore.QPointF(*pt))
                if s.mode == "eraser":
                    p.setCompositionMode(QPainter.CompositionMode_Clear)
                    p.setPen(QPen(Qt.black, s.width or 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                else:
                    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
                    p.setPen(QPen(QtGui.QColor(*s.rgba), s.width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                p.drawPath(path)

            elif s.t in ("rect", "oval"):
                rect = QtCore.QRectF(QtCore.QPointF(*s.points[0]),
                                     QtCore.QPointF(*s.points[1])).normalized()
                if s.mode == "eraser":
                    p.setCompositionMode(QPainter.CompositionMode_Clear)
                    if s.t == "rect":
                        p.fillRect(rect, Qt.black)
                    else:
                        p.setBrush(Qt.black); p.setPen(Qt.NoPen); p.drawEllipse(rect); p.setBrush(Qt.NoBrush)
                else:
                    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
                    p.setPen(QPen(QtGui.QColor(*s.rgba), s.width))
                    p.setBrush(Qt.NoBrush)
                    (p.drawRect if s.t == "rect" else p.drawEllipse)(rect)

            elif s.t in ("poly", "polygon"):
                if not s.points or len(s.points) < 3:
                    continue
                path = QtGui.QPainterPath(QtCore.QPointF(*s.points[0]))
                for pt in s.points[1:]:
                    path.lineTo(QtCore.QPointF(*pt))
                path.closeSubpath()
                if s.mode == "eraser":
                    p.setCompositionMode(QPainter.CompositionMode_Clear); p.fillPath(path, Qt.black)
                else:
                    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
                    p.setPen(QPen(QtGui.QColor(*s.rgba), s.width or 1)); p.drawPath(path)
        p.end()
