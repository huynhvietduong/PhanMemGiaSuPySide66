
# whiteboard_eraser_unified.py
from __future__ import annotations

"""
✨ Bảng vẽ Bài giảng (PySide6)
- 🧽 Gom Tẩy nét + Tẩy theo vùng thành **1 nút** (dropdown)
- Ghi nhớ **lựa chọn tẩy gần nhất** (nét / vùng Rect / vùng Lasso) bằng QSettings
- 📐 Nhóm vẽ hình (Line / Rect / Oval) gọn 1 nút
- Tách độ dày Bút & Tẩy, popover hiện đại + preset + phím tắt
- Ảnh: chèn/dán, kéo/resize bằng tay nắm; nét/ảnh tách lớp (tẩy không ảnh hưởng ảnh)
- Đa trang, Lưu/Mở .board.json (ảnh nhúng base64)
- Phím tắt: Ctrl+V (dán ảnh), Delete (xoá ảnh), F11 (fullscreen), Alt+Enter (maximize)
  + [ / ]: ±1 px độ dày Bút (hoặc Tẩy nếu đang chọn Tẩy) — Shift để ±5
  + Ctrl+[ / Ctrl+]: ±1 px độ dày Tẩy ở mọi chế độ
  + Giữ Shift khi vẽ Rect/Oval để vuông/tròn; khi khoanh Rect để tẩy vùng: Shift để vuông

Chạy:
    pip install PySide6
    python whiteboard_eraser_unified.py --session-id 1 --group-name "Toán 8A" --session-date 2025-08-11
"""

import os, json, base64, sys, argparse
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

from PySide6.QtCore import QRect
from PySide6 import QtCore, QtGui, QtWidgets

from PySide6.QtCore import Qt, QPointF, QRectF, QSize
from PySide6.QtGui import (
    QAction, QActionGroup, QColor, QPainter, QPen, QBrush, QImage, QPixmap, QKeySequence
)
from PySide6.QtWidgets import QWidgetAction
from PySide6.QtGui import (
    QAction, QActionGroup, QColor, QPainter, QPen, QBrush, QImage, QPixmap, QKeySequence,
    QGuiApplication, QShortcut
)
from PySide6.QtGui import QGuiApplication, QShortcut

# ======================== Data Models & helpers ========================

def _resolve_scroll_area(obj):
    sa = getattr(obj, "scroll", None)
    if callable(sa) or sa is None:
        sa = getattr(obj, "scroll_area", None)
    return sa

@dataclass
class Stroke:
    t: str                        # "line" | "rect" | "oval" | "poly"
    points: List[Tuple[float, float]] | None
    rgba: Tuple[int, int, int, int]
    width: int
    mode: str = "pen"             # "pen" | "eraser"

@dataclass
class Img:
    qimage: QImage
    x: int
    y: int
    w: int
    h: int

# ======================== Canvas Widget ========================

class _Canvas(QtWidgets.QWidget):
    HANDLE_SIZE = 10

    def __init__(self, parent: 'DrawingBoardWindowQt'):
        super().__init__(parent)
        self.win = parent
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        # virtual space
        self.virtual_h = 4000
        self.virtual_w = 2000

        # runtime states (images)
        self._dragging_img_idx: Optional[int] = None
        self._dragging_handle: Optional[str] = None  # 'tl','tr','bl','br' or None
        self._drag_offset = QtCore.QPoint()

        # drawing states
        self._is_drawing = False
        self._freehand_points: List[QPointF] = []  # cho pen/eraser
        self._shape_start: Optional[QPointF] = None
        self._shape_end: Optional[QPointF] = None
        self._lasso_points: List[QPointF] = []     # cho tẩy vùng kiểu lasso

        # backing store for strokes (ink layer) — chỉ chứa nét/hình, KHÔNG chứa ảnh
        self._ink = QImage(self.virtual_w, self.virtual_h, QImage.Format_ARGB32_Premultiplied)
        self._ink.fill(Qt.transparent)

        self.setMinimumSize(self.virtual_w, self.virtual_h)
        self._selected_img_idx: Optional[int] = None

    # -------- utilities --------
    def _ensure_size(self):
        parent = self.parent()
        sa = _resolve_scroll_area(parent) if parent else None
        if sa is None or not hasattr(sa, "viewport"):
            return
        vieww = sa.viewport().width()
        if vieww <= 0:
            return
        if self.virtual_w != vieww:
            self.virtual_w = vieww
            new_img = QImage(self.virtual_w, self.virtual_h, QImage.Format_ARGB32_Premultiplied)
            new_img.fill(Qt.transparent)
            parent._rebuild_into(new_img)
            self._ink = new_img
        self.setMinimumSize(self.virtual_w, self.virtual_h)

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(self.virtual_w, self.virtual_h)

    # -------- painting --------
    def paintEvent(self, e: QtGui.QPaintEvent):
        self._ensure_size()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.fillRect(self.rect(), Qt.white)

        # 1) Vẽ ảnh theo (x,y,w,h)
        for img in self.win._page_images():
            dest = QtCore.QRect(img.x, img.y, img.w, img.h)
            p.drawImage(dest, img.qimage)

        # 2) Vẽ lớp mực (strokes)
        p.drawImage(0, 0, self._ink)

        # 3) Preview cho tool 'shape'
        if self.win.tool == "shape" and self._shape_start and self._shape_end:
            pen = QPen(QtGui.QColor(*self.win.pen_rgba), 1, Qt.DashLine)
            p.setPen(pen); p.setBrush(Qt.NoBrush)
            start = self._shape_start
            end = self._shape_end
            rect = QRectF(start, end).normalized()
            if self.win.shape_kind == "line":
                p.drawLine(start, end)
            elif self.win.shape_kind == "rect":
                p.drawRect(rect)
            elif self.win.shape_kind == "oval":
                p.drawEllipse(rect)

        # 4) Preview cho tool 'erase_area'
        if self.win.tool == "erase_area":
            p.setPen(QPen(Qt.red, 1, Qt.DashLine))
            p.setBrush(QtGui.QColor(255, 0, 0, 60))  # đỏ nhạt trong suốt
            if self.win.erase_area_mode == "rect" and self._shape_start and self._shape_end:
                rect = QRectF(self._shape_start, self._shape_end).normalized()
                p.drawRect(rect)
                p.fillRect(rect, QtGui.QColor(255, 0, 0, 60))
            elif self.win.erase_area_mode == "lasso" and len(self._lasso_points) > 1:
                path = QtGui.QPainterPath(self._lasso_points[0])
                for pt in self._lasso_points[1:]:
                    path.lineTo(pt)
                p.drawPath(path)
                p.fillPath(path, QtGui.QColor(255, 0, 0, 60))

        # 5) Khung chọn ảnh
        if self.win.tool == "select":
            sel = self._dragging_img_idx if self._dragging_img_idx is not None else self._selected_img_idx
            if sel is not None:
                img = self.win._page_images()[sel]
                rect = QRectF(img.x, img.y, img.w, img.h)
                pen = QPen(Qt.black, 1, Qt.DashLine)
                p.setPen(pen);
                p.setBrush(Qt.NoBrush)
                p.drawRect(rect)
                for r in self._handle_rects(rect).values():
                    p.fillRect(r, Qt.black)

        p.end()

    # -------- mouse helpers --------
    def _hit_test_image(self, pos: QtCore.QPoint) -> Optional[int]:
        for i in range(len(self.win._page_images()) - 1, -1, -1):
            img = self.win._page_images()[i]
            rect = QtCore.QRect(img.x, img.y, img.w, img.h)
            if rect.contains(pos):
                return i
        return None

    def _handle_rects(self, rect):
        s = self.HANDLE_SIZE
        cx = int((rect.left() + rect.right()) / 2)
        cy = int((rect.top() + rect.bottom()) / 2)
        return {
            "tl": QRect(int(rect.left()) - s // 2, int(rect.top()) - s // 2, s, s),
            "tr": QRect(int(rect.right()) - s // 2, int(rect.top()) - s // 2, s, s),
            "bl": QRect(int(rect.left()) - s // 2, int(rect.bottom()) - s // 2, s, s),
            "br": QRect(int(rect.right()) - s // 2, int(rect.bottom()) - s // 2, s, s),
            # mới: tay nắm cạnh
            "t": QRect(cx - s // 2, int(rect.top()) - s // 2, s, s),
            "b": QRect(cx - s // 2, int(rect.bottom()) - s // 2, s, s),
            "l": QRect(int(rect.left()) - s // 2, cy - s // 2, s, s),
            "r": QRect(int(rect.right()) - s // 2, cy - s // 2, s, s),
        }

    def _hit_test_handle(self, img_idx: int, pos: QtCore.QPoint) -> Optional[str]:
        img = self.win._page_images()[img_idx]
        rect = QRectF(img.x, img.y, img.w, img.h)
        for name, r in self._handle_rects(rect).items():
            if r.contains(pos):
                return name
        return None

    def _apply_region_erase(self, path: QtGui.QPainterPath):
        # 1) Vẽ clear vào _ink
        painter = QPainter(self._ink)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setCompositionMode(QPainter.CompositionMode_Clear)
        painter.fillPath(path, Qt.black)
        painter.end()

        # 2) Ghi stroke để rebuild về sau (lưu polygon)
        pts: List[Tuple[float, float]] = []
        poly = path.toFillPolygon()
        for p in poly:
            pts.append((p.x(), p.y()))
        if len(pts) >= 3:
            stroke = Stroke(t="poly", points=pts, rgba=(0,0,0,0), width=0, mode="eraser")
            self.win._page_strokes().append(stroke)

        self.win._refresh_ink()

    # -------- mouse events --------
    def mousePressEvent(self, e: QtGui.QMouseEvent):
        pos = e.position().toPoint()
        if e.button() != Qt.LeftButton:
            return

        if self.win.tool == "select":
            idx = self._hit_test_image(pos)
            if idx is not None:
                self._selected_img_idx = idx
                handle = self._hit_test_handle(idx, pos)
                if handle:
                    self._dragging_img_idx = idx
                    self._dragging_handle = handle
                else:
                    self._dragging_img_idx = idx
                    self._dragging_handle = None
                    img = self.win._page_images()[idx]
                    self._drag_offset = pos - QtCore.QPoint(img.x, img.y)
            else:
                self._selected_img_idx = None
                self._dragging_img_idx = None
                self._dragging_handle = None
            self.update()

        elif self.win.tool in ("pen", "eraser"):
            self._is_drawing = True
            self._freehand_points = [QPointF(pos)]

        elif self.win.tool == "shape":
            self._shape_start = QPointF(pos)
            self._shape_end = QPointF(pos)

        elif self.win.tool == "erase_area":
            if self.win.erase_area_mode == "rect":
                self._shape_start = QPointF(pos)
                self._shape_end = QPointF(pos)
            else:  # lasso
                self._lasso_points = [QPointF(pos)]

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        pos = e.position().toPoint()

        if self.win.tool == "select" and self._dragging_img_idx is not None:
            img = self.win._page_images()[self._dragging_img_idx]
            if self._dragging_handle:
                left, top, right, bottom = img.x, img.y, img.x + img.w, img.y + img.h
                if "t" in self._dragging_handle:
                    top = pos.y()
                if "b" in self._dragging_handle:
                    bottom = pos.y()
                if "l" in self._dragging_handle:
                    left = pos.x()
                if "r" in self._dragging_handle:
                    right = pos.x()
                x0, x1 = sorted([left, right])
                y0, y1 = sorted([top, bottom])
                if e.modifiers() & Qt.ShiftModifier:
                    # khoá tỉ lệ khi resize ảnh
                    w = x1 - x0
                    h = y1 - y0
                    side = max(2, int(max(abs(w), abs(h))))
                    x1 = x0 + side if right >= left else x0 - side
                    y1 = y0 + side if bottom >= top else y0 - side
                img.x, img.y = int(x0), int(y0)
                img.w, img.h = max(2, int(x1 - x0)), max(2, int(y1 - y0))
                self.update()
            else:
                new_top_left = pos - self._drag_offset
                img.x = int(new_top_left.x())
                img.y = int(new_top_left.y())
                self.update()

        elif (self.win.tool in ("pen", "eraser")
              and self._freehand_points
              and (e.buttons() & Qt.LeftButton)):
            self._freehand_points.append(QPointF(pos))
            painter = QPainter(self._ink)
            painter.setRenderHint(QPainter.Antialiasing, True)
            w = self.win._current_width()
            if self.win.tool == "eraser":
                painter.setCompositionMode(QPainter.CompositionMode_Clear)
                painter.setPen(QPen(Qt.black, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            else:
                painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
                c = QtGui.QColor(*self.win.pen_rgba)
                painter.setPen(QPen(c, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            path = QtGui.QPainterPath(self._freehand_points[0])
            for pt in self._freehand_points[1:]:
                path.lineTo(pt)
            painter.drawPath(path)
            painter.end()
            self.update()

        elif self.win.tool == "shape" and self._shape_start:
            end = QPointF(pos)
            if self.win.shape_kind in ("rect", "oval") and (e.modifiers() & Qt.ShiftModifier):
                # khoá tỉ lệ
                dx = end.x() - self._shape_start.x()
                dy = end.y() - self._shape_start.y()
                m = max(abs(dx), abs(dy))
                sx = 1 if dx >= 0 else -1
                sy = 1 if dy >= 0 else -1
                end = QPointF(self._shape_start.x() + sx*m, self._shape_start.y() + sy*m)
            self._shape_end = end
            self.update()

        elif self.win.tool == "erase_area":
            if self.win.erase_area_mode == "rect" and self._shape_start:
                end = QPointF(pos)
                if e.modifiers() & Qt.ShiftModifier:
                    dx = end.x() - self._shape_start.x()
                    dy = end.y() - self._shape_start.y()
                    m = max(abs(dx), abs(dy))
                    sx = 1 if dx >= 0 else -1
                    sy = 1 if dy >= 0 else -1
                    end = QPointF(self._shape_start.x() + sx*m, self._shape_start.y() + sy*m)
                self._shape_end = end
                self.update()
            elif self.win.erase_area_mode == "lasso" and self._lasso_points and (e.buttons() & Qt.LeftButton):
                self._lasso_points.append(QPointF(pos))
                self.update()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if e.button() != Qt.LeftButton:
            return

        if self.win.tool == "select":
            self._dragging_img_idx = None
            self._dragging_handle = None

        elif self.win.tool in ("pen", "eraser"):
            if len(self._freehand_points) >= 2:
                pts = [(pt.x(), pt.y()) for pt in self._freehand_points]
                if self.win.tool == "eraser":
                    stroke = Stroke(t="line", points=pts, rgba=(0,0,0,0),
                                    width=self.win.eraser_width, mode="eraser")
                else:
                    stroke = Stroke(t="line", points=pts, rgba=self.win.pen_rgba,
                                    width=self.win.pen_width, mode="pen")
                self.win._page_strokes().append(stroke)
                self._freehand_points.clear()
            self._is_drawing = False

        elif self.win.tool == "shape" and self._shape_start and self._shape_end:
            start = self._shape_start
            end = self._shape_end
            pts = [(start.x(), start.y()), (end.x(), end.y())]
            t = self.win.shape_kind
            stroke = Stroke(t=t, points=pts, rgba=self.win.pen_rgba, width=self.win.pen_width, mode="pen")
            self.win._page_strokes().append(stroke)
            self._shape_start = self._shape_end = None
            self.win._refresh_ink()

        elif self.win.tool == "erase_area":
            if self.win.erase_area_mode == "rect" and self._shape_start and self._shape_end:
                rect = QRectF(self._shape_start, self._shape_end).normalized()
                path = QtGui.QPainterPath(); path.addRect(rect)
                self._apply_region_erase(path)
                self._shape_start = self._shape_end = None
            elif self.win.erase_area_mode == "lasso" and len(self._lasso_points) >= 3:
                path = QtGui.QPainterPath(self._lasso_points[0])
                for pt in self._lasso_points[1:]:
                    path.lineTo(pt)
                path.closeSubpath()
                self._apply_region_erase(path)
                self._lasso_points.clear()

        self.update()

    def keyPressEvent(self, e: QtGui.QKeyEvent):
        key = e.key(); mods = e.modifiers()
        if key in (Qt.Key_Delete, Qt.Key_Backspace):
            self.win.delete_selected_image()
        elif key == Qt.Key_V and (mods & Qt.ControlModifier):
            self.win.paste_from_clipboard()
        elif key in (Qt.Key_BracketLeft, Qt.Key_BracketRight):
            step = 5 if (mods & Qt.ShiftModifier) else 1
            is_increase = (key == Qt.Key_BracketRight)
            if (mods & Qt.ControlModifier):
                self.win.adjust_eraser_width(step if is_increase else -step)
            else:
                if self.win.tool == "eraser":
                    self.win.adjust_eraser_width(step if is_increase else -step)
                else:
                    self.win.adjust_pen_width(step if is_increase else -step)
        else:
            super().keyPressEvent(e)
class ScreenSnipOverlay(QtWidgets.QWidget):
    """
    Overlay chụp màn hình: mode in {"full","rect","lasso"}.
    on_done: callable(QImage cropped, str target) với target in {"current","new"}.
    """
    def __init__(self, on_done, mode="rect", parent=None):
        super().__init__(None)
        self.on_done = on_done
        self.mode = mode
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setCursor(Qt.CrossCursor)

        # Chụp toàn desktop (đa màn hình)
        self._snap, self._virt = self._grab_full_desktop()
        self.setGeometry(self._virt)

        # Trạng thái chọn
        self._dragging = False
        self._origin = QtCore.QPoint()
        self._rect = QtCore.QRect()
        self._lasso_pts: list[QtCore.QPoint] = []

        self.show()
        self.activateWindow()

        # Mode 'full' → không cần vẽ overlay, hiện menu luôn
        if self.mode == "full":
            self._rect = QtCore.QRect(QtCore.QPoint(0, 0), self._virt.size())
            QtCore.QTimer.singleShot(0, lambda: self._finalize(QtGui.QCursor.pos()))

    # ----- helpers -----
    def _grab_full_desktop(self):
        app = QGuiApplication.instance()
        primary = app.primaryScreen()
        virt = primary.virtualGeometry()
        result = QPixmap(virt.size())
        result.fill(Qt.transparent)
        p = QPainter(result)
        for s in app.screens():
            pm = s.grabWindow(0)
            g = s.geometry()
            p.drawPixmap(g.topLeft() - virt.topLeft(), pm)
        p.end()
        return result, virt

    def _finalize(self, global_pt: QtCore.QPoint):
        # Tạo ảnh kết quả
        if self.mode == "lasso":
            if len(self._lasso_pts) < 5:
                self.close(); return
            poly = QtGui.QPolygon(self._lasso_pts)
            br = poly.boundingRect()
            img = QImage(br.size(), QImage.Format_ARGB32_Premultiplied)
            img.fill(Qt.transparent)
            painter = QPainter(img)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            path = QtGui.QPainterPath()
            path.addPolygon(QtGui.QPolygonF([QtCore.QPointF(p - br.topLeft()) for p in self._lasso_pts]))
            painter.setClipPath(path)
            painter.drawPixmap(-br.topLeft(), self._snap)
            painter.end()
            cropped = img
        else:
            cropped = self._snap.copy(self._rect).toImage()

        # Hỏi nơi dán
        menu = QtWidgets.QMenu(self)
        act_cur = menu.addAction("Dán vào TRANG HIỆN TẠI")
        act_new = menu.addAction("Dán vào TRANG MỚI")
        chosen = menu.exec(global_pt)
        if chosen:
            target = "current" if chosen == act_cur else "new"
            try:
                self.on_done(cropped, target)
            finally:
                self.close()
        else:
            self.close()

    # ----- events -----
    def paintEvent(self, e: QtGui.QPaintEvent):
        if self.mode == "full":
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.drawPixmap(0, 0, self._snap)
        p.fillRect(self.rect(), QColor(0, 0, 0, 120))

        if self.mode == "rect" and not self._rect.isNull():
            p.drawPixmap(self._rect, self._snap, self._rect)
            p.setPen(QPen(Qt.white, 1, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(self._rect)
            label = f"{self._rect.width()}×{self._rect.height()}"
            r = QtCore.QRect(self._rect.topLeft(), QtCore.QSize(max(60, len(label)*8+12), 24))
            r.moveTopLeft(self._rect.topLeft() + QtCore.QPoint(0, -28))
            if r.top() < 0: r.moveTop(self._rect.top()+6)
            p.setPen(Qt.NoPen); p.setBrush(QColor(0,0,0,160))
            p.drawRoundedRect(r, 4, 4)
            p.setPen(Qt.white); p.drawText(r, Qt.AlignCenter, label)

        if self.mode == "lasso" and self._lasso_pts:
            # làm sáng vùng bên trong lasso
            path = QtGui.QPainterPath()
            path.addPolygon(QtGui.QPolygonF([QtCore.QPointF(p) for p in self._lasso_pts]))
            p.save()
            p.setClipPath(path)
            p.drawPixmap(0, 0, self._snap)
            p.restore()
            p.setPen(QPen(Qt.white, 1, Qt.DashLine))
            p.drawPath(path)

        p.end()

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() != Qt.LeftButton or self.mode == "full":
            return
        pos = e.position().toPoint()
        self._dragging = True
        if self.mode == "rect":
            self._origin = pos
            self._rect = QtCore.QRect(self._origin, self._origin)
        else:
            self._lasso_pts = [pos]
        self.update()

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if not self._dragging or self.mode == "full":
            return
        pos = e.position().toPoint()
        if self.mode == "rect":
            self._rect = QtCore.QRect(self._origin, pos).normalized()
        else:
            self._lasso_pts.append(pos)
        self.update()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if e.button() != Qt.LeftButton or not self._dragging or self.mode == "full":
            return
        self._dragging = False
        if self.mode == "rect":
            self._rect = self._rect.normalized()
            if self._rect.width() < 3 or self._rect.height() < 3:
                self.close(); return
            self._finalize(e.globalPosition().toPoint())
        else:
            if len(self._lasso_pts) < 5:
                self.close(); return
            self._finalize(e.globalPosition().toPoint())

    def keyPressEvent(self, e: QtGui.QKeyEvent):
        if e.key() in (Qt.Key_Escape, Qt.Key_Q):
            self.close()
class SnipController(QtWidgets.QWidget):
    """
    Bảng điều khiển chụp màn hình (nổi, luôn-on-top).
    on_pick_mode(mode): callback khi chọn 'full' | 'rect' | 'lasso'.
    """
    def __init__(self, on_pick_mode, parent=None):
        super().__init__(None)  # top-level, không gắn vào main window
        self.on_pick_mode = on_pick_mode

        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        frame = QtWidgets.QFrame(self)
        frame.setStyleSheet("""
            QFrame { background: white; border:1px solid rgba(0,0,0,0.18); border-radius:10px; }
            QToolButton { border:none; padding:8px 12px; }
            QToolButton:hover { background: rgba(0,0,0,0.08); }
            QToolButton:pressed { background: rgba(0,0,0,0.18); }
        """)
        lay = QtWidgets.QHBoxLayout(frame); lay.setContentsMargins(6,6,6,6); lay.setSpacing(0)

        def mkbtn(text, tip):
            b = QtWidgets.QToolButton(frame)
            b.setText(text); b.setToolTip(tip); b.setAutoRaise(True)
            b.setCursor(Qt.PointingHandCursor)
            lay.addWidget(b)
            # kẻ vạch ngăn
            sep = QtWidgets.QFrame(frame)
            sep.setFrameShape(QtWidgets.QFrame.VLine)
            sep.setStyleSheet("color: rgba(0,0,0,0.12);")
            lay.addWidget(sep)
            return b

        self.btn_full  = mkbtn("🖥", "Chụp toàn màn hình")
        self.btn_rect  = mkbtn("▭", "Chụp vùng chữ nhật")
        self.btn_lasso = mkbtn("◌", "Chụp vùng lasso")
        self.btn_move  = mkbtn("⤧", "Giữ chuột để kéo bảng")
        self.btn_power = QtWidgets.QToolButton(frame); self.btn_power.setText("⏻"); self.btn_power.setToolTip("Đóng bảng")
        self.btn_power.setCursor(Qt.PointingHandCursor); self.btn_power.setAutoRaise(True)
        lay.addWidget(self.btn_power)

        root = QtWidgets.QHBoxLayout(self); root.setContentsMargins(0,0,0,0); root.addWidget(frame)

        # Sự kiện
        self.btn_full.clicked.connect(lambda: self._pick("full"))
        self.btn_rect.clicked.connect(lambda: self._pick("rect"))
        self.btn_lasso.clicked.connect(lambda: self._pick("lasso"))
        self.btn_power.clicked.connect(self.close)

        # Kéo bảng khi giữ nút ⤧
        self._dragging = False
        self._dragPos = QtCore.QPoint()
        self.btn_move.pressed.connect(lambda: setattr(self, "_dragging", True))
        self.btn_move.released.connect(lambda: setattr(self, "_dragging", False))

    def _pick(self, mode: str):
        # Ẩn trong lúc chụp để không lọt vào ảnh
        self.hide()
        self.on_pick_mode(mode)  # MainWindow sẽ mở overlay

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() == Qt.LeftButton:
            self._dragPos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if self._dragging and (e.buttons() & Qt.LeftButton):
            delta = e.globalPosition().toPoint() - self._dragPos
            self.move(self.pos() + delta)
            self._dragPos = e.globalPosition().toPoint()


class DrawingBoardWindowQt(QtWidgets.QMainWindow):
    """
    Bảng vẽ bài giảng – PySide6
    - Công cụ: pen, eraser(=tẩy nét), erase_area(=tẩy vùng), shape (line/rect/oval), select & kéo/resize ảnh
    - Dán/Chèn ảnh, đa trang, lưu/đọc .board.json
    """
    def __init__(self, parent=None, group_name=None, session_date=None,
                 session_id: Optional[int]=None, on_saved=None,
                 board_path: Optional[str]=None, lesson_dir: Optional[str]=None):
        super().__init__(parent)
        self.setWindowTitle("✨ Bảng vẽ Bài giảng (Qt)")
        self.resize(1200, 800)

        self._on_saved_cb = on_saved
        self.group_name = group_name or ""
        self.session_date = session_date or ""
        self.session_id = session_id
        self.lesson_dir = lesson_dir or os.path.join(os.getcwd(), "data", "lessons", str(self.session_id or "unknown"))

        # settings (ghi nhớ giữa các lần mở)
        self._settings = QtCore.QSettings()
        self.pen_width = int(self._settings.value("pen_width", 4))
        self.eraser_width = int(self._settings.value("eraser_width", 30))
        self._last_eraser_kind = str(self._settings.value("eraser_kind", "stroke"))  # "stroke" | "rect" | "lasso"
        self.erase_area_mode = str(self._settings.value("erase_area_mode", "rect"))  # "rect" | "lasso"

        # draw state
        self.tool = "pen"
        self.pen_rgba = (0, 0, 0, 255)

        # shape sub state
        self.shape_kind = "rect"          # "line" | "rect" | "oval"

        # multi page data
        self.pages: List[Dict[str, list]] = []  # [{"strokes": [Stroke...], "images": [Img...]}]
        self.current_page: int = 0
        self._ensure_one_page()

        # UI
        self._build_ui()

        # load existing
        self._current_board_path: Optional[str] = None
        if board_path and os.path.exists(board_path):
            try:
                self.load_from_file(board_path)
            except Exception as ex:
                QtWidgets.QMessageBox.warning(self, "Mở file", f"Không đọc được file:\n{ex}")

    # ----- UI helpers -----
    def _build_ui(self):
        tb = self.addToolBar("Tools")
        tb.setMovable(False)

        # ----- Pen & Select -----
        self.act_pen = QAction("✏️ Bút", self, checkable=True)
        self.act_select = QAction("🖱️ Chọn/Ảnh", self, checkable=True)
        for act, name in [(self.act_pen, "pen"), (self.act_select, "select")]:
            act.triggered.connect(lambda checked, n=name: self._set_tool(n))
            tb.addAction(act)
        self.act_pen.setChecked(True)

        # ---- Unified Eraser button (main + dropdown) ----
        self.btn_eraser = QtWidgets.QToolButton(self)
        self.btn_eraser.setCheckable(True)
        self.btn_eraser.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup)
        self._update_eraser_button_text(self._last_eraser_kind)
        self.btn_eraser.clicked.connect(self._activate_eraser_quick)

        menu_eraser = QtWidgets.QMenu(self)
        group = QActionGroup(self); group.setExclusive(True)
        self.act_eraser_stroke = QAction("Tẩy nét (freehand)", self, checkable=True)
        self.act_eraser_rect = QAction("Tẩy vùng: Rect", self, checkable=True)
        self.act_eraser_lasso = QAction("Tẩy vùng: Lasso", self, checkable=True)
        for a in (self.act_eraser_stroke, self.act_eraser_rect, self.act_eraser_lasso):
            group.addAction(a); menu_eraser.addAction(a)

        # restore check state from settings
        if self._last_eraser_kind == "stroke":
            self.act_eraser_stroke.setChecked(True)
        elif self._last_eraser_kind == "lasso":
            self.act_eraser_lasso.setChecked(True)
        else:
            self.act_eraser_rect.setChecked(True)

        self.act_eraser_stroke.triggered.connect(lambda _: self._choose_eraser("stroke"))
        self.act_eraser_rect.triggered.connect(lambda _: self._choose_eraser("rect"))
        self.act_eraser_lasso.triggered.connect(lambda _: self._choose_eraser("lasso"))
        self.btn_eraser.setMenu(menu_eraser)
        tb.addWidget(self.btn_eraser)

        # ---- shape group (one button + dropdown) ----
        self.btn_shape = QtWidgets.QToolButton(self)
        self.btn_shape.setText("📐 Hình: ▭")
        self.btn_shape.setCheckable(True)
        self.btn_shape.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup)
        menu_shape = QtWidgets.QMenu(self)
        self.act_shape_line = QAction("Đường thẳng", self, checkable=True)
        self.act_shape_rect = QAction("Hình chữ nhật", self, checkable=True)
        self.act_shape_oval = QAction("Hình tròn/Oval", self, checkable=True)
        for a in (self.act_shape_line, self.act_shape_rect, self.act_shape_oval):
            menu_shape.addAction(a)
        self.btn_shape.setMenu(menu_shape)
        tb.addWidget(self.btn_shape)

        def choose_shape(kind: str, text_for_btn: str, act_to_check: QAction):
            self.shape_kind = kind
            for a in (self.act_shape_line, self.act_shape_rect, self.act_shape_oval):
                a.setChecked(a == act_to_check)
            self.btn_shape.setText(f"📐 Hình: {text_for_btn}")
            # bật tool 'shape'
            self._set_tool("shape")
            self.btn_shape.setChecked(True)

        self.act_shape_line.triggered.connect(lambda _: choose_shape("line", "—", self.act_shape_line))
        self.act_shape_rect.triggered.connect(lambda _: choose_shape("rect", "▭", self.act_shape_rect))
        self.act_shape_oval.triggered.connect(lambda _: choose_shape("oval", "◯", self.act_shape_oval))
        self.act_shape_rect.setChecked(True)

        tb.addSeparator()

        # color
        self.btn_color = QtWidgets.QToolButton(self)
        self.btn_color.setText("🎨 Màu")
        self.btn_color.clicked.connect(self._pick_color)
        tb.addWidget(self.btn_color)

        # width chips (modern popover)
        tb.addWidget(QtWidgets.QLabel("｜"))
        self.btn_pen_width = QtWidgets.QToolButton(self)
        self.btn_pen_width.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.menu_pen_width, self._pen_slider, self._pen_label = self._build_width_menu("pen")
        self.btn_pen_width.setMenu(self.menu_pen_width)
        tb.addWidget(self.btn_pen_width)

        self.btn_eraser_width = QtWidgets.QToolButton(self)
        self.btn_eraser_width.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.menu_eraser_width, self._eraser_slider, self._eraser_label = self._build_width_menu("eraser")
        self.btn_eraser_width.setMenu(self.menu_eraser_width)
        tb.addWidget(self.btn_eraser_width)

        self._update_width_buttons()

        tb.addSeparator()

        # image ops
        self.act_insert_img = QAction("📂 Chèn ảnh…", self)
        self.act_insert_img.triggered.connect(self.insert_image_from_file)
        tb.addAction(self.act_insert_img)

        self.act_paste_img = QAction("📋 Dán ảnh", self)
        self.act_paste_img.setShortcut(QKeySequence("Ctrl+V"))
        self.act_paste_img.triggered.connect(self.paste_from_clipboard)
        tb.addAction(self.act_paste_img)

        # screen capture
        self.act_snip = QAction("📸 Chụp màn hình", self)
        self.act_snip.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.act_snip.triggered.connect(self.toggle_snip_controller)
        tb.addAction(self.act_snip)

        # phím PrintScreen
        self._sc_snip = QShortcut(QKeySequence(Qt.Key_Print), self)
        self._sc_snip.activated.connect(self._printscreen_behavior)

        self.act_delete_img = QAction("🗑 Xoá ảnh", self)
        self.act_delete_img.setShortcut(QKeySequence.Delete)
        self.act_delete_img.triggered.connect(self.delete_selected_image)
        tb.addAction(self.act_delete_img)

        tb.addSeparator()

        # save/lesson
        self.act_save_to_lesson = QAction("💾 Lưu vào Bài giảng", self)
        self.act_save_to_lesson.triggered.connect(self.save_to_lesson)
        tb.addAction(self.act_save_to_lesson)

        self.act_save_as = QAction("💾 Lưu thành…", self)
        self.act_save_as.triggered.connect(self.save_as_dialog)
        tb.addAction(self.act_save_as)

        self.act_open = QAction("📂 Mở…", self)
        self.act_open.triggered.connect(self.open_dialog)
        tb.addAction(self.act_open)

        tb.addSeparator()

        # pages
        self.act_prev = QAction("◀ Trang trước", self)
        self.act_next = QAction("Trang sau ▶", self)
        self.act_add = QAction("➕ Thêm trang", self)
        self.act_del = QAction("🗑 Xoá trang", self)

        self.act_prev.triggered.connect(self._page_prev)
        self.act_next.triggered.connect(self._page_next)
        self.act_add.triggered.connect(self._page_add)
        self.act_del.triggered.connect(self._page_del)

        for act in (self.act_prev, self.act_next, self.act_add, self.act_del):
            tb.addAction(act)

        tb.addSeparator()

        # window controls
        self.act_full = QAction("⛶ Fullscreen (F11)", self)
        self.act_full.setShortcut(Qt.Key_F11)
        self.act_full.triggered.connect(self._toggle_fullscreen)
        tb.addAction(self.act_full)

        self.act_max = QAction("⤢ Max/Restore (Alt+Enter)", self)
        self.act_max.setShortcut(QKeySequence("Alt+Return"))
        self.act_max.triggered.connect(self._toggle_max_restore)
        tb.addAction(self.act_max)

        # central area: scroll area + canvas
        self.scroll = QtWidgets.QScrollArea(self)
        self.scroll_area = self.scroll
        self.scroll.setWidgetResizable(True)
        self.canvas = _Canvas(self)
        self.scroll.setWidget(self.canvas)
        self.setCentralWidget(self.scroll)

    def _build_width_menu(self, kind: str):
        menu = QtWidgets.QMenu(self)
        w = QtWidgets.QWidget(self)
        vbox = QtWidgets.QVBoxLayout(w)
        vbox.setContentsMargins(8, 8, 8, 8)

        label = QtWidgets.QLabel()
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-weight:600; padding:2px;")

        slider = QtWidgets.QSlider(Qt.Horizontal)
        slider.setRange(1, 100)
        slider.setSingleStep(1)
        slider.setPageStep(5)
        slider.setFixedWidth(240)

        quick_layout = QtWidgets.QHBoxLayout()
        quick_layout.setSpacing(4)
        for val in [1, 2, 3, 5, 8, 12, 16, 20, 30, 50, 80]:
            btn = QtWidgets.QToolButton()
            btn.setText(str(val))
            btn.setAutoRaise(True)
            btn.clicked.connect(lambda _=False, v=val: self._set_width(kind, v))
            quick_layout.addWidget(btn)

        vbox.addWidget(label)
        vbox.addWidget(slider)
        vbox.addLayout(quick_layout)

        action = QWidgetAction(self)
        action.setDefaultWidget(w)
        menu.addAction(action)

        init_val = self.pen_width if kind == "pen" else self.eraser_width
        slider.setValue(init_val)
        label.setText(f"Độ dày {'Bút' if kind=='pen' else 'Tẩy'}: {init_val}px")
        slider.valueChanged.connect(lambda v: self._set_width(kind, int(v)))

        return menu, slider, label

    def _update_width_buttons(self):
        self.btn_pen_width.setText(f"✏️ {self.pen_width}px")
        self.btn_pen_width.setToolTip("Độ dày Bút\nPhím tắt: [ / ] (Shift=±5)")
        self.btn_eraser_width.setText(f"🧽 {self.eraser_width}px")
        self.btn_eraser_width.setToolTip("Độ dày Tẩy\nPhím tắt: Ctrl+[ / Ctrl+] (Shift=±5)")
        if hasattr(self, "_pen_label"):
            self._pen_label.setText(f"Độ dày Bút: {self.pen_width}px")
        if hasattr(self, "_eraser_label"):
            self._eraser_label.setText(f"Độ dày Tẩy: {self.eraser_width}px")

    def _update_eraser_button_text(self, kind: str):
        if kind == "stroke":
            self.btn_eraser.setText("🧽 Tẩy: Nét")
        elif kind == "lasso":
            self.btn_eraser.setText("🧽 Tẩy: Vùng Lasso")
        else:
            self.btn_eraser.setText("🧽 Tẩy: Vùng Rect")

    def _choose_eraser(self, kind: str):
        """Chọn loại tẩy từ menu & kích hoạt tool tương ứng, lưu QSettings."""
        self._last_eraser_kind = kind
        self._settings.setValue("eraser_kind", kind)
        if kind in ("rect", "lasso"):
            self.erase_area_mode = "lasso" if kind == "lasso" else "rect"
            self._settings.setValue("erase_area_mode", self.erase_area_mode)
            self._set_tool("erase_area")
            self.btn_eraser.setChecked(True)
        else:
            self._set_tool("eraser")
            self.btn_eraser.setChecked(True)
        self._update_eraser_button_text(kind)

    def _activate_eraser_quick(self):
        """Nhấn phần chính của nút → dùng loại tẩy gần nhất."""
        kind = self._last_eraser_kind
        if kind in ("rect", "lasso"):
            self.erase_area_mode = "lasso" if kind == "lasso" else "rect"
            self._set_tool("erase_area")
        else:
            self._set_tool("eraser")
        self._update_eraser_button_text(kind)

    def _set_tool(self, name: str):
        self.tool = name
        self.act_pen.setChecked(name == "pen")
        self.act_select.setChecked(name == "select")
        self.btn_shape.setChecked(name == "shape")
        # nút Tẩy coi là checked khi tool thuộc nhóm tẩy
        self.btn_eraser.setChecked(name in ("eraser", "erase_area"))

    def _pick_color(self):
        c = QtWidgets.QColorDialog.getColor(QtGui.QColor(*self.pen_rgba), self, "Chọn màu bút")
        if c.isValid():
            self.pen_rgba = (c.red(), c.green(), c.blue(), 255)

    # ----- Width helpers -----
    def _current_width(self) -> int:
        return self.eraser_width if self.tool == "eraser" else self.pen_width

    def _set_width(self, kind: str, value: int):
        v = max(1, min(100, int(value)))
        if kind == "pen":
            self.pen_width = v
            if hasattr(self, "_pen_slider"):
                self._pen_slider.blockSignals(True); self._pen_slider.setValue(v); self._pen_slider.blockSignals(False)
            self._settings.setValue("pen_width", v)
        else:
            self.eraser_width = v
            if hasattr(self, "_eraser_slider"):
                self._eraser_slider.blockSignals(True); self._eraser_slider.setValue(v); self._eraser_slider.blockSignals(False)
            self._settings.setValue("eraser_width", v)
        self._update_width_buttons()
        self.canvas.update()

    def adjust_pen_width(self, delta: int):
        self._set_width("pen", self.pen_width + int(delta))

    def adjust_eraser_width(self, delta: int):
        self._set_width("eraser", self.eraser_width + int(delta))

    # ----- Page data accessors -----
    def _ensure_one_page(self):
        if not self.pages:
            self.pages.append({"strokes": [], "images": []})
            self.current_page = 0

    def _page(self) -> Dict[str, list]:
        return self.pages[self.current_page]

    def _page_strokes(self) -> List[Stroke]:
        return self._page()["strokes"]

    def _page_images(self) -> List[Img]:
        return self._page()["images"]

    # ----- Rebuild ink from data (chỉ nét/hình, không vẽ ảnh vào _ink) -----
    def _rebuild_into(self, target_img: QImage):
        target_img.fill(Qt.transparent)
        p = QPainter(target_img)
        p.setRenderHint(QPainter.Antialiasing, True)
        for s in self._page_strokes():
            if s.t == "line":
                if not s.points or len(s.points) < 2:
                    continue
                path = QtGui.QPainterPath(QtCore.QPointF(*s.points[0]))
                for pt in s.points[1:]:
                    path.lineTo(QtCore.QPointF(*pt))
                if s.mode == "eraser":
                    p.setCompositionMode(QPainter.CompositionMode_Clear)
                    p.setPen(QPen(Qt.black, s.width or 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                    p.drawPath(path)
                else:
                    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
                    p.setPen(QPen(QtGui.QColor(*s.rgba), s.width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                    p.drawPath(path)

            elif s.t in ("rect", "oval"):
                rect = QtCore.QRectF(QtCore.QPointF(*s.points[0]), QtCore.QPointF(*s.points[1])).normalized()
                if s.mode == "eraser":
                    p.setCompositionMode(QPainter.CompositionMode_Clear)
                    if s.t == "rect":
                        p.fillRect(rect, Qt.black)
                    else:
                        p.setBrush(Qt.black); p.setPen(Qt.NoPen); p.drawEllipse(rect); p.setBrush(Qt.NoBrush)
                else:
                    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
                    p.setPen(QPen(QtGui.QColor(*s.rgba), s.width))
                    if s.t == "rect":
                        p.setBrush(Qt.NoBrush); p.drawRect(rect)
                    else:
                        p.setBrush(Qt.NoBrush); p.drawEllipse(rect)

            elif s.t in ("poly", "polygon"):
                if not s.points or len(s.points) < 3:
                    continue
                path = QtGui.QPainterPath(QtCore.QPointF(*s.points[0]))
                for pt in s.points[1:]:
                    path.lineTo(QtCore.QPointF(*pt))
                path.closeSubpath()
                if s.mode == "eraser":
                    p.setCompositionMode(QPainter.CompositionMode_Clear)
                    p.fillPath(path, Qt.black)
                else:
                    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
                    p.setPen(QPen(QtGui.QColor(*s.rgba), s.width or 1))
                    p.drawPath(path)
        p.end()

    def _refresh_ink(self):
        self.canvas._ink.fill(Qt.transparent)
        self._rebuild_into(self.canvas._ink)
        self.canvas.update()

    # ----- Image ops -----
    def insert_image_from_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Chọn ảnh", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if not path:
            return
        img = QImage(path)
        if img.isNull():
            QtWidgets.QMessageBox.critical(self, "Ảnh", "Không mở được ảnh.")
            return
        self._page_images().append(Img(qimage=img, x=..., y=..., w=img.width(), h=img.height()))
        self._set_tool("select")
        self.canvas._dragging_img_idx = len(self._page_images()) - 1
        self.canvas._dragging_handle = None
        self.canvas.update()

    def paste_from_clipboard(self):
        md = QtWidgets.QApplication.clipboard().mimeData()
        if md is None or (not md.hasImage() and not md.hasUrls()):
            QtWidgets.QMessageBox.information(self, "Dán ảnh", "Clipboard không có ảnh.")
            return
        if md.hasImage():
            img = QtGui.QImage(md.imageData())
        else:
            url = md.urls()[0]
            img = QtGui.QImage(url.toLocalFile())
        if img.isNull():
            QtWidgets.QMessageBox.information(self, "Dán ảnh", "Không đọc được ảnh.")
            return
        self._page_images().append(Img(qimage=img, x=..., y=..., w=img.width(), h=img.height()))
        self._set_tool("select")
        self.canvas._dragging_img_idx = len(self._page_images()) - 1
        self.canvas._dragging_handle = None
        self.canvas.update()

    def delete_selected_image(self):
        if self.tool != "select":
            if self._page_images():
                self._page_images().pop()
                self._refresh_ink()
                return
            return
        pos = self.mapFromGlobal(QtGui.QCursor.pos())
        pos = self.canvas.mapFrom(self, pos)
        idx = None
        for i in range(len(self._page_images()) - 1, -1, -1):
            img = self._page_images()[i]
            if QtCore.QRect(img.x, img.y, img.w, img.h).contains(pos):
                idx = i; break
        if idx is None and self._page_images():
            idx = len(self._page_images()) - 1
        if idx is not None:
            self._page_images().pop(idx)
            self._refresh_ink()

    # ----- Save / Load (.board.json) -----
    def to_dict(self) -> dict:
        data = {
            "version": 2,
            "meta": {
                "group_name": self.group_name,
                "session_date": self.session_date,
            },
            "pages": []
        }
        for p in self.pages:
            strokes = []
            for s in p["strokes"]:
                strokes.append({
                    "type": s.t,
                    "points": s.points,
                    "rgba": list(s.rgba),
                    "width": s.width,
                    "mode": s.mode
                })
            images = {}
            for idx, im in enumerate(p["images"]):
                buffer = QtCore.QBuffer()
                buffer.open(QtCore.QIODevice.WriteOnly)
                im.qimage.save(buffer, "PNG")
                b64 = base64.b64encode(bytes(buffer.data())).decode("ascii")
                images[str(idx)] = {
                    "x": im.x, "y": im.y, "w": im.w, "h": im.h,
                    "fmt": "png",
                    "b64": b64
                }
            data["pages"].append({"strokes": strokes, "images": images})
        return data

    def load_from_dict(self, data: dict):
        self.pages.clear()
        for page in data.get("pages", []):
            strokes: List[Stroke] = []
            for s in page.get("strokes", []):
                strokes.append(
                    Stroke(
                        t=s.get("type", "line"),
                        points=[tuple(pt) for pt in s.get("points", [])],
                        rgba=tuple(s.get("rgba", [0,0,0,255])),
                        width=int(s.get("width", 3)),
                        mode=s.get("mode", "pen"),
                    )
                )
            images: List[Img] = []
            imgs = page.get("images", {})
            if isinstance(imgs, dict):
                items = sorted(imgs.items(), key=lambda x: int(x[0]))
                for _, im in items:
                    b = base64.b64decode(im.get("b64", ""))
                    qimg = QImage.fromData(b, "PNG")
                    images.append(Img(qimage=qimg,
                                      x=int(im.get("x", 0)),
                                      y=int(im.get("y", 0)),
                                      w=int(im.get("w", qimg.width())),
                                      h=int(im.get("h", qimg.height()))))
            self.pages.append({"strokes": strokes, "images": images})
        if not self.pages:
            self._ensure_one_page()
        self.current_page = 0
        self.canvas._ink.fill(Qt.transparent)
        self._rebuild_into(self.canvas._ink)
        self.canvas.update()

    def load_from_file(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.load_from_dict(data)
        self._current_board_path = path

    def save_to_lesson(self):
        if not self.session_id:
            QtWidgets.QMessageBox.critical(self, "Bảng vẽ", "Chưa có session_id. Vui lòng lưu buổi học trước.")
            return
        os.makedirs(self.lesson_dir, exist_ok=True)

        path = getattr(self, "_current_board_path", None)
        if not path:
            topic = ""
            parent = self.parent()
            if parent and hasattr(parent, "topic_text"):
                try:
                    topic = parent.topic_text.toPlainText().strip().splitlines()[0]
                except Exception:
                    topic = ""
            topic_safe = (topic or "no_topic").replace(" ", "_").replace("/", "-")[:50]
            group_safe = (self.group_name or "no_group").replace(" ", "_")
            date_str = (self.session_date or "").replace("-", "_") or "unknown_date"
            fname = f"{group_safe}__{date_str}__{topic_safe}.board.json"
            path = os.path.join(self.lesson_dir, fname)

        data = self.to_dict()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        title = os.path.basename(path)
        if self._on_saved_cb:
            try:
                self._on_saved_cb(path, title)
            except Exception:
                pass
        QtWidgets.QMessageBox.information(self, "Bảng vẽ", f"Đã lưu vào Bài giảng:\n{title}")
        self._current_board_path = path

    def save_as_dialog(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Lưu thành", "", "Board (*.board.json)")
        if not path:
            return
        if not path.endswith(".board.json"):
            path += ".board.json"
        self._current_board_path = path
        self.save_to_lesson()

    def open_dialog(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Mở bảng vẽ", "", "Board (*.board.json)")
        if path:
            self.load_from_file(path)

    # ----- pages -----
    def _page_prev(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._refresh_ink()
            self.canvas.update()

    def _page_next(self):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self._refresh_ink()
            self.canvas.update()

    def _page_add(self):
        self.pages.insert(self.current_page + 1, {"strokes": [], "images": []})
        self.current_page += 1
        self._refresh_ink()
        self.canvas.update()

    def _page_del(self):
        if len(self.pages) <= 1:
            QtWidgets.QMessageBox.information(self, "Trang", "Không thể xoá, phải còn ít nhất 1 trang.")
            return
        self.pages.pop(self.current_page)
        self.current_page = max(0, self.current_page - 1)
        self._refresh_ink()
        self.canvas.update()

    # ----- window helpers -----
    def _toggle_fullscreen(self):
        self.setWindowState(self.windowState() ^ Qt.WindowFullScreen)

    def _toggle_max_restore(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # ===== Screen capture =====
    def start_screen_capture(self):
        """Ẩn tạm cửa sổ, chụp desktop bằng overlay rồi trả kết quả."""
        # Ẩn cửa sổ để không lọt vào ảnh chụp
        self.hide()
        QtWidgets.QApplication.processEvents()

        def _done(img: QImage, target: str):
            # Hiện lại cửa sổ
            self.show()
            self.raise_()
            self.activateWindow()
            self._insert_snip_image(img, to_new_page=(target == "new"))

        # Mở overlay
        self._snip_overlay = ScreenSnipOverlay(on_done=_done)

    def _insert_snip_image(self, img: QImage, to_new_page: bool = False):
        """Dán ảnh đã cắt vào trang hiện tại hoặc trang mới và chọn ngay ảnh."""
        if to_new_page:
            self._page_add()

        # Scale vừa bề rộng canvas (giữ tỉ lệ)
        max_w = max(100, int(self.canvas.virtual_w - 80))
        w, h = img.width(), img.height()
        if w > max_w:
            h = int(h * (max_w / float(w)))
            w = max_w

        x = int((self.canvas.virtual_w - w) / 2)
        y = 60  # cách mép trên một chút
        self._page_images().append(Img(qimage=img, x=x, y=y, w=w, h=h))

        # Chuyển về tool select và chọn ảnh mới thêm
        self._set_tool("select")
        new_idx = len(self._page_images()) - 1

        # Nếu bạn đã thêm biến _selected_img_idx theo fix trước đó:
        if hasattr(self.canvas, "_selected_img_idx"):
            self.canvas._selected_img_idx = new_idx
            self.canvas._dragging_img_idx = None
            self.canvas._dragging_handle = None
        else:
            # fallback: dùng cách cũ (đang kéo), handles sẽ ẩn sau khi thả
            self.canvas._dragging_img_idx = new_idx
            self.canvas._dragging_handle = None

        self.canvas.update()

    def toggle_snip_controller(self):
        if getattr(self, "_snip_ctrl", None) and self._snip_ctrl.isVisible():
            self._snip_ctrl.hide()
            return
        if not getattr(self, "_snip_ctrl", None):
            self._snip_ctrl = SnipController(on_pick_mode=self._start_snip_mode)
        self._snip_ctrl.show()
        self._snip_ctrl.raise_()
        # đặt vị trí góc phải dưới màn hình lần đầu
        if not getattr(self._snip_ctrl, "_placed", False):
            geo = QGuiApplication.primaryScreen().availableGeometry()
            self._snip_ctrl.move(geo.right() - self._snip_ctrl.width() - 40,
                                 geo.bottom() - self._snip_ctrl.height() - 40)
            self._snip_ctrl._placed = True

    def _printscreen_behavior(self):
        if getattr(self, "_snip_ctrl", None) and self._snip_ctrl.isVisible():
            self._snip_ctrl._pick("rect")  # chụp nhanh rect
        else:
            self.toggle_snip_controller()

    def _start_snip_mode(self, mode: str):
        """Được gọi từ SnipController khi chọn chế độ chụp."""
        # Ẩn cửa sổ chính để không lọt vào ảnh
        self.hide()
        QtWidgets.QApplication.processEvents()

        def _done(img: QImage, target: str):
            # Hiện lại cửa sổ & paste ảnh
            self.show();
            self.raise_();
            self.activateWindow()
            self._insert_snip_image(img, to_new_page=(target == "new"))
            # Hiện lại controller để chụp tiếp
            if getattr(self, "_snip_ctrl", None):
                self._snip_ctrl.show();
                self._snip_ctrl.raise_()

        # Mở overlay theo mode
        self._snip_overlay = ScreenSnipOverlay(on_done=_done, mode=mode)

    def _insert_snip_image(self, img: QImage, to_new_page: bool = False):
        if to_new_page:
            self._page_add()
        # Scale vừa rộng canvas, giữ tỉ lệ
        max_w = max(100, int(self.canvas.virtual_w - 80))
        w, h = img.width(), img.height()
        if w > max_w:
            h = int(h * (max_w / float(w)));
            w = max_w
        x = int((self.canvas.virtual_w - w) / 2)
        y = 60
        self._page_images().append(Img(qimage=img, x=x, y=y, w=w, h=h))

        # Chuyển sang Select và CHỌN ảnh mới
        self._set_tool("select")
        new_idx = len(self._page_images()) - 1
        if hasattr(self.canvas, "_selected_img_idx"):
            self.canvas._selected_img_idx = new_idx
            self.canvas._dragging_img_idx = None
            self.canvas._dragging_handle = None
        else:
            self.canvas._dragging_img_idx = new_idx
            self.canvas._dragging_handle = None
        self.canvas.update()


# ======================== Entrypoint ========================

def main():
    parser = argparse.ArgumentParser(description="Run Bảng vẽ bài giảng (Qt).")
    parser.add_argument("--session-id", type=int, default=1, help="ID buổi học (int).")
    parser.add_argument("--group-name", type=str, default="Nhom_A", help="Tên nhóm/lớp.")
    parser.add_argument("--session-date", type=str, default="", help="Ngày buổi học (YYYY-MM-DD).")
    parser.add_argument("--board-path", type=str, default=None, help="Đường dẫn file .board.json để mở (nếu có).")
    parser.add_argument("--lesson-dir", type=str, default=None, help="Thư mục lưu bài giảng (mặc định theo session_id).")
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    QtCore.QCoreApplication.setOrganizationName("TutorApp")
    QtCore.QCoreApplication.setApplicationName("DrawingBoard")

    win = DrawingBoardWindowQt(
        session_id=args.session_id,
        group_name=args.group_name,
        session_date=args.session_date,
        board_path=args.board_path,
        lesson_dir=args.lesson_dir,
    )
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
