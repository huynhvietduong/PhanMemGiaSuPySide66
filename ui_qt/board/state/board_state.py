from __future__ import annotations
from typing import List, Dict
from PySide6 import QtCore, QtGui
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QPen
from ui_qt.board.core.data_models import Stroke, Img
from collections import deque
import copy
import json
class BoardState:
    """Quản lý dữ liệu bảng vẽ: trang, strokes, images, rebuild lớp mực."""
    def __init__(self):
        self.pages: List[Dict[str, list]] = []    # [{"strokes":[Stroke], "images":[Img]}]
        self.current_page: int = 0
        self.ensure_one_page()
        self._undo_manager = UndoRedoManager()
        self._auto_save_enabled = True

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

    def save_state_for_undo(self):
        """Lưu trạng thái hiện tại để có thể undo"""
        if self._auto_save_enabled:
            current_state = self.to_dict()
            self._undo_manager.save_state(current_state)

    def undo(self) -> bool:
        """Hoàn tác thao tác cuối cùng"""
        if not self._undo_manager.can_undo():
            return False

        current_state = self.to_dict()
        previous_state = self._undo_manager.undo(current_state)
        self.from_dict(previous_state)
        return True

    def redo(self) -> bool:
        """Làm lại thao tác đã hoàn tác"""
        if not self._undo_manager.can_redo():
            return False

        current_state = self.to_dict()
        next_state = self._undo_manager.redo(current_state)
        self.from_dict(next_state)
        return True

    def can_undo(self) -> bool:
        return self._undo_manager.can_undo()

    def can_redo(self) -> bool:
        return self._undo_manager.can_redo()

    def to_dict(self) -> dict:
        """Chuyển đổi trạng thái hiện tại thành dictionary"""
        return {
            "pages": [
                {
                    "strokes": [
                        {
                            "type": s.t,
                            "points": s.points,
                            "rgba": list(s.rgba),
                            "width": s.width,
                            "mode": s.mode
                        } for s in page["strokes"]
                    ],
                    "images": [
                        {
                            "x": img.x,
                            "y": img.y,
                            "w": img.w,
                            "h": img.h,
                            # Lưu ảnh dưới dạng bytes data để có thể restore
                            "image_data": self._qimage_to_bytes(img.qimage)
                        } for img in page["images"]
                    ]
                } for page in self.pages
            ],
            "current_page": self.current_page
        }

    def from_dict(self, data: dict):
        """Khôi phục trạng thái từ dictionary"""
        from ui_qt.board.core.data_models import Stroke, Img

        # Tạm thời tắt auto save để tránh lưu state khi restore
        old_auto_save = self._auto_save_enabled
        self._auto_save_enabled = False

        try:
            self.pages = []

            for page_data in data.get("pages", []):
                # Khôi phục strokes
                strokes = []
                for s_data in page_data.get("strokes", []):
                    stroke = Stroke(
                        t=s_data.get("type", "line"),
                        points=[tuple(pt) if isinstance(pt, list) else pt for pt in s_data.get("points", [])],
                        rgba=tuple(s_data.get("rgba", [0, 0, 0, 255])),
                        width=int(s_data.get("width", 1)),
                        mode=s_data.get("mode", "pen")
                    )
                    strokes.append(stroke)

                # Khôi phục images
                images = []
                for img_data in page_data.get("images", []):
                    qimage = self._bytes_to_qimage(img_data.get("image_data", b""))
                    if not qimage.isNull():
                        img = Img(
                            qimage=qimage,
                            x=int(img_data.get("x", 0)),
                            y=int(img_data.get("y", 0)),
                            w=int(img_data.get("w", qimage.width())),
                            h=int(img_data.get("h", qimage.height()))
                        )
                        images.append(img)

                self.pages.append({"strokes": strokes, "images": images})

            # Đảm bảo có ít nhất 1 page
            if not self.pages:
                self.ensure_one_page()

            # Khôi phục current page
            self.current_page = max(0, min(data.get("current_page", 0), len(self.pages) - 1))

        finally:
            # Khôi phục auto save setting
            self._auto_save_enabled = old_auto_save

    def _qimage_to_bytes(self, qimage) -> bytes:
        """Chuyển QImage thành bytes để lưu trữ"""
        from PySide6 import QtCore

        if qimage.isNull():
            return b""

        buffer = QtCore.QBuffer()
        buffer.open(QtCore.QIODevice.WriteOnly)
        qimage.save(buffer, "PNG")
        return bytes(buffer.data())

    def _bytes_to_qimage(self, data: bytes):
        """Chuyển bytes thành QImage"""
        from PySide6.QtGui import QImage

        if not data:
            return QImage()

        qimage = QImage()
        qimage.loadFromData(data, "PNG")
        return qimage
class UndoRedoManager:
    """Quản lý lịch sử thay đổi cho Undo/Redo"""

    def __init__(self, max_history: int = 50):
        self.max_history = max_history
        self.undo_stack = deque(maxlen=max_history)
        self.redo_stack = deque(maxlen=max_history)
        self.current_state_hash = None

    def save_state(self, state_data: dict):
        """Lưu trạng thái hiện tại vào undo stack"""
        state_json = json.dumps(state_data, sort_keys=True)
        state_hash = hash(state_json)

        # Chỉ lưu nếu state thực sự thay đổi
        if state_hash != self.current_state_hash:
            self.undo_stack.append(state_data.copy())
            self.redo_stack.clear()  # Xóa redo stack khi có thay đổi mới
            self.current_state_hash = state_hash

    def can_undo(self) -> bool:
        """Kiểm tra có thể undo không"""
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        """Kiểm tra có thể redo không"""
        return len(self.redo_stack) > 0

    def undo(self, current_state: dict) -> dict:
        """Thực hiện undo, trả về state trước đó"""
        if not self.can_undo():
            return current_state

        # Lưu state hiện tại vào redo stack
        self.redo_stack.append(current_state.copy())

        # Lấy state trước đó từ undo stack
        return self.undo_stack.pop()

    def redo(self, current_state: dict) -> dict:
        """Thực hiện redo, trả về state sau đó"""
        if not self.can_redo():
            return current_state

        # Lưu state hiện tại vào undo stack
        self.undo_stack.append(current_state.copy())

        # Lấy state sau đó từ redo stack
        return self.redo_stack.pop()