from __future__ import annotations
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPen, QColor, QPixmap, QImage, QGuiApplication

class ScreenSnipOverlay(QtWidgets.QWidget):
    """Overlay chụp màn hình: mode in {'full','rect','lasso'}."""
    def __init__(self, on_done, mode="rect", parent=None):
        super().__init__(None)
        self.on_done = on_done; self.mode = mode
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setCursor(Qt.CrossCursor)
        self._snap, self._virt = self._grab_full_desktop()
        self.setGeometry(self._virt)
        self._dragging = False; self._origin = QtCore.QPoint()
        self._rect = QtCore.QRect(); self._lasso_pts: list[QtCore.QPoint] = []
        self.show(); self.activateWindow()
        if self.mode == "full":
            self._rect = QtCore.QRect(QtCore.QPoint(0,0), self._virt.size())
            QtCore.QTimer.singleShot(0, lambda: self._finalize(QtGui.QCursor.pos()))

    def _grab_full_desktop(self):
        app = QGuiApplication.instance(); primary = app.primaryScreen()
        virt = primary.virtualGeometry(); result = QPixmap(virt.size()); result.fill(Qt.transparent)
        p = QPainter(result)
        for s in app.screens():
            pm = s.grabWindow(0); g = s.geometry()
            p.drawPixmap(g.topLeft() - virt.topLeft(), pm)
        p.end(); return result, virt

    def _finalize(self, global_pt: QtCore.QPoint):
        if self.mode == "lasso":
            if len(self._lasso_pts) < 5: self.close(); return
            poly = QtGui.QPolygon(self._lasso_pts); br = poly.boundingRect()
            img = QImage(br.size(), QImage.Format_ARGB32_Premultiplied); img.fill(Qt.transparent)
            painter = QPainter(img); painter.setRenderHint(QPainter.Antialiasing, True); painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            path = QtGui.QPainterPath(); path.addPolygon(QtGui.QPolygonF([QtCore.QPointF(p - br.topLeft()) for p in self._lasso_pts]))
            painter.setClipPath(path); painter.drawPixmap(-br.topLeft(), self._snap); painter.end(); cropped = img
        else:
            cropped = self._snap.copy(self._rect).toImage()

        menu = QtWidgets.QMenu(self); act_cur = menu.addAction("Dán vào TRANG HIỆN TẠI"); act_new = menu.addAction("Dán vào TRANG MỚI")
        chosen = menu.exec(global_pt)
        if chosen: self.on_done(cropped, "current" if chosen == act_cur else "new")
        self.close()

    def paintEvent(self, e: QtGui.QPaintEvent):
        if self.mode == "full": return
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing, True); p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.drawPixmap(0,0,self._snap); p.fillRect(self.rect(), QColor(0,0,0,120))
        if self.mode == "rect" and not self._rect.isNull():
            p.drawPixmap(self._rect, self._snap, self._rect)
            p.setPen(QPen(Qt.white, 1, Qt.DashLine)); p.setBrush(Qt.NoBrush); p.drawRect(self._rect)
        if self.mode == "lasso" and self._lasso_pts:
            path = QtGui.QPainterPath(); path.addPolygon(QtGui.QPolygonF([QtCore.QPointF(p) for p in self._lasso_pts]))
            p.save(); p.setClipPath(path); p.drawPixmap(0,0,self._snap); p.restore()
            p.setPen(QPen(Qt.white, 1, Qt.DashLine)); p.drawPath(path)
        p.end()

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button()!=Qt.LeftButton or self.mode=="full": return
        pos = e.position().toPoint(); self._dragging = True
        if self.mode=="rect": self._origin = pos; self._rect = QtCore.QRect(self._origin, self._origin)
        else: self._lasso_pts = [pos]; self.update()

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if not self._dragging or self.mode=="full": return
        pos = e.position().toPoint()
        if self.mode=="rect": self._rect = QtCore.QRect(self._origin, pos).normalized()
        else: self._lasso_pts.append(pos)
        self.update()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if e.button()!=Qt.LeftButton or not self._dragging or self.mode=="full": return
        self._dragging = False
        if self.mode=="rect":
            self._rect = self._rect.normalized()
            if self._rect.width()<3 or self._rect.height()<3: self.close(); return
            self._finalize(e.globalPosition().toPoint())
        else:
            if len(self._lasso_pts)<5: self.close(); return
            self._finalize(e.globalPosition().toPoint())

    def keyPressEvent(self, e: QtGui.QKeyEvent):
        if e.key() in (Qt.Key_Escape, Qt.Key_Q): self.close()

class SnipController(QtWidgets.QWidget):
    """Bảng điều khiển chụp màn hình (nổi, luôn-on-top)."""
    def __init__(self, on_pick_mode, parent=None):
        super().__init__(None)
        self.on_pick_mode = on_pick_mode
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
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
