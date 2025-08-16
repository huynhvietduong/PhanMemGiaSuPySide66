from __future__ import annotations
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from .width_menu import create_width_menu

class BoardToolbar(QtWidgets.QToolBar):
    # ==== Signals (Window sẽ connect) ====
    toolChanged = Signal(str)               # "pen"|"select"|"eraser"|"erase_area"|"shape"
    shapeChanged = Signal(str)              # "line"|"rect"|"oval"
    eraserKindChanged = Signal(str)         # "stroke"|"rect"|"lasso"
    colorPicked = Signal(tuple)             # (r,g,b,a)
    penWidthChanged = Signal(int)
    eraserWidthChanged = Signal(int)

    requestInsertImage = Signal()
    requestPasteImage = Signal()
    requestSnip = Signal()
    requestDeleteImage = Signal()

    requestSave = Signal()
    requestSaveAs = Signal()
    requestOpen = Signal()

    pagePrev = Signal()
    pageNext = Signal()
    pageAdd = Signal()
    pageDel = Signal()

    toggleFull = Signal()
    toggleMaxRestore = Signal()

    def __init__(self, parent=None, init_pen_width=4, init_eraser_width=30, init_eraser_kind="stroke", init_shape="rect"):
        super().__init__("Tools", parent)
        self.setMovable(False)

        # Pen / Select
        self.act_pen = QAction("✏️ Bút", self, checkable=True)
        self.act_select = QAction("🖱️ Chọn/Ảnh", self, checkable=True)
        for act, name in [(self.act_pen,"pen"), (self.act_select,"select")]:
            act.triggered.connect(lambda _=False, n=name: self.toolChanged.emit(n))
            self.addAction(act)
        self.act_pen.setChecked(True)

        # Eraser (dropdown)
        self.btn_eraser = QtWidgets.QToolButton(self)
        self.btn_eraser.setCheckable(True)
        self.btn_eraser.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup)
        self._update_eraser_button_text(init_eraser_kind)
        self.btn_eraser.clicked.connect(lambda: self.eraserKindChanged.emit(init_eraser_kind))
        menu_eraser = QtWidgets.QMenu(self); group = QActionGroup(self); group.setExclusive(True)
        self.act_eraser_stroke = QAction("Tẩy nét (freehand)", self, checkable=True)
        self.act_eraser_rect   = QAction("Tẩy vùng: Rect", self, checkable=True)
        self.act_eraser_lasso  = QAction("Tẩy vùng: Lasso", self, checkable=True)
        for a in (self.act_eraser_stroke, self.act_eraser_rect, self.act_eraser_lasso):
            group.addAction(a); menu_eraser.addAction(a)
        if init_eraser_kind == "stroke": self.act_eraser_stroke.setChecked(True)
        elif init_eraser_kind == "lasso": self.act_eraser_lasso.setChecked(True)
        else: self.act_eraser_rect.setChecked(True)
        self.act_eraser_stroke.triggered.connect(lambda _: self.eraserKindChanged.emit("stroke"))
        self.act_eraser_rect.triggered.connect(lambda _: self.eraserKindChanged.emit("rect"))
        self.act_eraser_lasso.triggered.connect(lambda _: self.eraserKindChanged.emit("lasso"))
        self.btn_eraser.setMenu(menu_eraser)
        self.addWidget(self.btn_eraser)

        # Shape (dropdown)
        self.btn_shape = QtWidgets.QToolButton(self); self.btn_shape.setText("📐 Hình: ▭")
        self.btn_shape.setCheckable(True); self.btn_shape.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup)
        menu_shape = QtWidgets.QMenu(self)
        self.act_shape_line = QAction("Đường thẳng", self, checkable=True)
        self.act_shape_rect = QAction("Hình chữ nhật", self, checkable=True)
        self.act_shape_oval = QAction("Hình tròn/Oval", self, checkable=True)
        for a in (self.act_shape_line, self.act_shape_rect, self.act_shape_oval): menu_shape.addAction(a)
        self.act_shape_rect.setChecked(True if init_shape=="rect" else False)
        self.btn_shape.setMenu(menu_shape)
        self.addWidget(self.btn_shape)
        self.act_shape_line.triggered.connect(lambda _: self._choose_shape("line", "—"))
        self.act_shape_rect.triggered.connect(lambda _: self._choose_shape("rect", "▭"))
        self.act_shape_oval.triggered.connect(lambda _: self._choose_shape("oval", "◯"))

        self.addSeparator()

        # Color picker
        self.btn_color = QtWidgets.QToolButton(self); self.btn_color.setText("🎨 Màu")
        self.btn_color.clicked.connect(self._pick_color); self.addWidget(self.btn_color)

        # Width menus
        self.addWidget(QtWidgets.QLabel("｜"))
        self.btn_pen_w = QtWidgets.QToolButton(self); self.btn_pen_w.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.menu_pen, self._pen_slider, self._pen_label = create_width_menu(self, "pen", init_pen_width, self._on_pen_width)
        self.btn_pen_w.setMenu(self.menu_pen); self.addWidget(self.btn_pen_w)

        self.btn_eraser_w = QtWidgets.QToolButton(self); self.btn_eraser_w.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.menu_eraser, self._eraser_slider, self._eraser_label = create_width_menu(self, "eraser", init_eraser_width, self._on_eraser_width)
        self.btn_eraser_w.setMenu(self.menu_eraser); self.addWidget(self.btn_eraser_w)

        self._sync_width_buttons(init_pen_width, init_eraser_width)

        self.addSeparator()

        # Image / snip
        self.addAction(self._act("📂 Chèn ảnh…", self.requestInsertImage.emit))
        a_paste = self._act("📋 Dán ảnh", self.requestPasteImage.emit); a_paste.setShortcut(QKeySequence("Ctrl+V")); self.addAction(a_paste)
        a_snip = self._act("📸 Chụp màn hình", self.requestSnip.emit); a_snip.setShortcut(QKeySequence("Ctrl+Shift+S")); self.addAction(a_snip)
        a_del = self._act("🗑 Xóa ảnh", self.requestDeleteImage.emit); a_del.setShortcut(QKeySequence.Delete); self.addAction(a_del)

        self.addSeparator()

        # Save/Open
        self.addAction(self._act("💾 Lưu vào Bài giảng", self.requestSave.emit))
        self.addAction(self._act("💾 Lưu thành…", self.requestSaveAs.emit))
        self.addAction(self._act("📂 Mở…", self.requestOpen.emit))

        self.addSeparator()

        # Pages
        self.addAction(self._act("◀ Trang trước", self.pagePrev.emit))
        self.addAction(self._act("Trang sau ▶", self.pageNext.emit))
        self.addAction(self._act("➕ Thêm trang", self.pageAdd.emit))
        self.addAction(self._act("🗑 Xóa trang", self.pageDel.emit))

        self.addSeparator()

        # Window control
        a_full = self._act("⛶ Fullscreen (F11)", self.toggleFull.emit); a_full.setShortcut(Qt.Key_F11); self.addAction(a_full)
        a_max  = self._act("⤢ Max/Restore (Alt+Enter)", self.toggleMaxRestore.emit); a_max.setShortcut(QKeySequence("Alt+Return")); self.addAction(a_max)

    # ---- helpers ----
    def _act(self, text, slot):
        a = QAction(text, self); a.triggered.connect(slot); return a

    def _update_eraser_button_text(self, kind: str):
        self.btn_eraser.setText("🧽 Tẩy: Nét" if kind=="stroke" else ("🧽 Tẩy: Vùng Lasso" if kind=="lasso" else "🧽 Tẩy: Vùng Rect"))

    def _choose_shape(self, kind: str, symbol: str):
        self.btn_shape.setChecked(True); self.btn_shape.setText(f"📐 Hình: {symbol}")
        self.shapeChanged.emit(kind)

    def _pick_color(self):
        c = QtWidgets.QColorDialog.getColor(parent=self)
        if c.isValid(): self.colorPicked.emit((c.red(), c.green(), c.blue(), 255))

    def _sync_width_buttons(self, pen_w: int, eraser_w: int):
        self.btn_pen_w.setText(f"✏️ {pen_w}px")
        self.btn_eraser_w.setText(f"🧽 {eraser_w}px")
        self._pen_label.setText(f"Độ dày Bút: {pen_w}px")
        self._eraser_label.setText(f"Độ dày Tẩy: {eraser_w}px")

    def _on_pen_width(self, v: int):
        v = max(1, min(100, int(v)))
        self._pen_slider.blockSignals(True); self._pen_slider.setValue(v); self._pen_slider.blockSignals(False)
        self._sync_width_buttons(v, self._eraser_slider.value())
        self.penWidthChanged.emit(v)

    def _on_eraser_width(self, v: int):
        v = max(1, min(100, int(v)))
        self._eraser_slider.blockSignals(True); self._eraser_slider.setValue(v); self._eraser_slider.blockSignals(False)
        self._sync_width_buttons(self._pen_slider.value(), v)
        self.eraserWidthChanged.emit(v)

    # Cho Window đồng bộ lại trạng thái nút khi đổi tool từ ngoài:
    def reflect_tool(self, name: str, eraser_kind: str, is_shape: bool):
        self.act_pen.setChecked(name == "pen")
        self.act_select.setChecked(name == "select")
        self.btn_shape.setChecked(is_shape)
        self.btn_eraser.setChecked(name in ("eraser","erase_area"))
        self._update_eraser_button_text(eraser_kind)