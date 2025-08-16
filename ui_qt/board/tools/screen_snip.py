from __future__ import annotations
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPen, QColor, QPixmap, QImage, QGuiApplication

class ScreenSnipOverlay(QtWidgets.QWidget):
    """Overlay chụp màn hình: mode in {'full','rect','lasso'}."""
    def __init__(self, on_done, mode="rect", parent=None):
        super().__init__(None)
        self.on_done = on_done; self.mode = mode
        # Fix: Thêm flags để đảm bảo overlay hoạt động đúng
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.Tool |
            Qt.WindowStaysOnTopHint |
            Qt.BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setCursor(Qt.CrossCursor)
        # Fix: Đảm bảo capture thành công với error handling
        try:
            self._snap, self._virt = self._grab_full_desktop()
            self.setGeometry(self._virt)
        except Exception as e:
            print(f"Error capturing desktop: {e}")
            self.close()
            return
        self._dragging = False; self._origin = QtCore.QPoint()
        self._rect = QtCore.QRect(); self._lasso_pts: list[QtCore.QPoint] = []
        # Fix: Đảm bảo hiển thị và activate đúng cách
        self.show()
        self.raise_()
        self.activateWindow()
        if self.mode == "full":
            self._rect = QtCore.QRect(QtCore.QPoint(0,0), self._virt.size())
            QtCore.QTimer.singleShot(0, lambda: self._finalize(QtGui.QCursor.pos()))

    # Fix: Cải thiện việc capture desktop với error handling
    def _grab_full_desktop(self):
        app = QGuiApplication.instance()
        if not app:
            raise Exception("No QApplication instance")

        primary = app.primaryScreen()
        if not primary:
            raise Exception("No primary screen found")

        virt = primary.virtualGeometry()
        result = QPixmap(virt.size())
        result.fill(Qt.transparent)

        p = QPainter(result)
        try:
            for s in app.screens():
                try:
                    pm = s.grabWindow(0)
                    if not pm.isNull():
                        g = s.geometry()
                        p.drawPixmap(g.topLeft() - virt.topLeft(), pm)
                except Exception as e:
                    print(f"Error capturing screen {s.name()}: {e}")
                    continue
        finally:
            p.end()

        return result, virt

    # Fix: Thêm các phương thức chuyển đổi tọa độ
    def _widget_to_virtual(self, widget_pos: QtCore.QPoint) -> QtCore.QPoint:
        """Chuyển đổi từ widget coordinates sang virtual desktop coordinates"""
        return widget_pos + self._virt.topLeft()

    def _virtual_to_widget(self, virtual_pos: QtCore.QPoint) -> QtCore.QPoint:
        """Chuyển đổi từ virtual desktop coordinates sang widget coordinates"""
        return virtual_pos - self._virt.topLeft()

    def _virtual_to_global(self, virtual_pos: QtCore.QPoint) -> QtCore.QPoint:
        """Chuyển đổi từ virtual coordinates sang global screen coordinates"""
        return virtual_pos

    def _calculate_lasso_center(self) -> QtCore.QPoint:
        """Tính toán điểm trung tâm của lasso"""
        if not self._lasso_pts:
            return QtCore.QPoint(0, 0)

        sum_x = sum(p.x() for p in self._lasso_pts)
        sum_y = sum(p.y() for p in self._lasso_pts)
        count = len(self._lasso_pts)

        return QtCore.QPoint(sum_x // count, sum_y // count)
    def _finalize(self, global_pt: QtCore.QPoint):
        if self.mode == "lasso":
            if len(self._lasso_pts) < 5: self.close(); return
            poly = QtGui.QPolygon(self._lasso_pts); br = poly.boundingRect()
            img = QImage(br.size(), QImage.Format_ARGB32_Premultiplied); img.fill(Qt.transparent)
            painter = QPainter(img); painter.setRenderHint(QPainter.Antialiasing, True); painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            path = QtGui.QPainterPath(); path.addPolygon(QtGui.QPolygonF([QtCore.QPointF(p - br.topLeft()) for p in self._lasso_pts]))
            painter.setClipPath(path); painter.drawPixmap(-br.topLeft(), self._snap); painter.end(); cropped = img
        else:
            # Fix: Đảm bảo crop đúng vùng được chọn trong virtual coordinates
            virtual_rect = self._rect.intersected(QtCore.QRect(0, 0, self._snap.width(), self._snap.height()))
            if virtual_rect.isValid():
                cropped = self._snap.copy(virtual_rect).toImage()
            else:
                cropped = QImage(1, 1, QImage.Format_ARGB32_Premultiplied)
                cropped.fill(Qt.transparent)
        menu = QtWidgets.QMenu(self); act_cur = menu.addAction("Dán vào TRANG HIỆN TẠI"); act_new = menu.addAction("Dán vào TRANG MỚI")
        chosen = menu.exec(global_pt)
        if chosen: self.on_done(cropped, "current" if chosen == act_cur else "new")
        self.close()

    def paintEvent(self, e: QtGui.QPaintEvent):
        if self.mode == "full": return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # Vẽ ảnh nền
        p.drawPixmap(0, 0, self._snap)

        # Vẽ overlay tối
        p.fillRect(self.rect(), QColor(0, 0, 0, 120))

        if self.mode == "rect" and not self._rect.isNull():
            # Fix: Chuyển đổi tọa độ virtual sang widget để vẽ đúng
            widget_rect = QtCore.QRect(
                self._virtual_to_widget(self._rect.topLeft()),
                self._virtual_to_widget(self._rect.bottomRight())
            )

            # Vẽ vùng được chọn (không có overlay tối)
            p.drawPixmap(widget_rect, self._snap, widget_rect)

            # Vẽ khung viền
            p.setPen(QPen(Qt.white, 2, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(widget_rect)

        if self.mode == "lasso" and self._lasso_pts:
            # Fix: Chuyển đổi tọa độ lasso sang widget coordinates
            widget_points = [self._virtual_to_widget(pt) for pt in self._lasso_pts]
            path = QtGui.QPainterPath()
            path.addPolygon(QtGui.QPolygonF([QtCore.QPointF(p) for p in widget_points]))

            # Vẽ vùng được chọn
            p.save()
            p.setClipPath(path)
            p.drawPixmap(0, 0, self._snap)
            p.restore()

            # Vẽ đường viền lasso
            p.setPen(QPen(Qt.white, 2, Qt.DashLine))
            p.drawPath(path)

        p.end()
    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() != Qt.LeftButton or self.mode == "full": return
        # Fix: Chuyển đổi tọa độ từ widget coordinates sang virtual coordinates
        pos = self._widget_to_virtual(e.position().toPoint())
        self._dragging = True
        if self.mode == "rect":
            self._origin = pos
            self._rect = QtCore.QRect(self._origin, self._origin)
        else:
            self._lasso_pts = [pos]
            self.update()

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if not self._dragging or self.mode == "full": return
        # Fix: Chuyển đổi tọa độ từ widget coordinates sang virtual coordinates
        pos = self._widget_to_virtual(e.position().toPoint())
        if self.mode == "rect":
            self._rect = QtCore.QRect(self._origin, pos).normalized()
        else:
            self._lasso_pts.append(pos)
        self.update()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if e.button() != Qt.LeftButton or not self._dragging or self.mode == "full": return
        self._dragging = False
        if self.mode == "rect":
            self._rect = self._rect.normalized()
            if self._rect.width() < 3 or self._rect.height() < 3:
                self.close()
                return
            # Fix: Sử dụng tọa độ global đã được mapping đúng
            global_pt = self._virtual_to_global(self._rect.center())
            self._finalize(global_pt)
        else:
            if len(self._lasso_pts) < 5:
                self.close()
                return
            # Fix: Tính global point từ tọa độ trung tâm của lasso
            if self._lasso_pts:
                center = self._calculate_lasso_center()
                global_pt = self._virtual_to_global(center)
            else:
                global_pt = e.globalPosition().toPoint()
            self._finalize(global_pt)
    def keyPressEvent(self, e: QtGui.QKeyEvent):
        if e.key() in (Qt.Key_Escape, Qt.Key_Q): self.close()

class SnipController(QtWidgets.QWidget):
    """Bảng điều khiển chụp màn hình (nổi, luôn-on-top)."""
    def __init__(self, on_pick_mode, parent=None):
        super().__init__(None)
        self.on_pick_mode = on_pick_mode
        # Fix: Thêm flag để đảm bảo luôn ở trên và tránh xung đột
        self.setWindowFlags(
            Qt.Tool |
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        frame = QtWidgets.QFrame(self)
        frame.setStyleSheet("""
            QFrame { background:white; border:1px solid rgba(0,0,0,.18); border-radius:10px; }
            QToolButton { border:none; padding:8px 12px; }
            QToolButton:hover { background: rgba(0,0,0,.08); }
            QToolButton:pressed { background: rgba(0,0,0,.18); }
        """)
        lay = QtWidgets.QHBoxLayout(frame); lay.setContentsMargins(6,6,6,6); lay.setSpacing(0)

        def mk(text, tip):
            b = QtWidgets.QToolButton(frame); b.setText(text); b.setToolTip(tip); b.setAutoRaise(True); b.setCursor(Qt.PointingHandCursor)
            lay.addWidget(b); sep = QtWidgets.QFrame(frame); sep.setFrameShape(QtWidgets.QFrame.VLine); sep.setStyleSheet("color:rgba(0,0,0,.12)"); lay.addWidget(sep); return b
        self.btn_full = mk("🖥","Chụp toàn màn hình")
        self.btn_rect = mk("▭","Chụp vùng chữ nhật")
        self.btn_lasso = mk("◌","Chụp vùng lasso")
        self.btn_move = mk("⤧","Giữ để kéo")
        self.btn_power = QtWidgets.QToolButton(frame); self.btn_power.setText("⏻"); self.btn_power.setToolTip("Đóng"); self.btn_power.setAutoRaise(True); self.btn_power.setCursor(Qt.PointingHandCursor); lay.addWidget(self.btn_power)

        root = QtWidgets.QHBoxLayout(self); root.setContentsMargins(0,0,0,0); root.addWidget(frame)
        self.btn_full.clicked.connect(lambda: self._pick("full"))
        self.btn_rect.clicked.connect(lambda: self._pick("rect"))
        self.btn_lasso.clicked.connect(lambda: self._pick("lasso"))
        self.btn_power.clicked.connect(self.close)
        self._dragging=False; self._dragPos=QtCore.QPoint()
        self.btn_move.pressed.connect(lambda: setattr(self,"_dragging",True))
        self.btn_move.released.connect(lambda: setattr(self,"_dragging",False))

    def _pick(self, mode: str):
        self.hide(); self.on_pick_mode(mode)

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button()==Qt.LeftButton: self._dragPos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if self._dragging and (e.buttons() & Qt.LeftButton):
            delta = e.globalPosition().toPoint() - self._dragPos
            self.move(self.pos()+delta); self._dragPos = e.globalPosition().toPoint()
