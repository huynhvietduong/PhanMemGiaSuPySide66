from __future__ import annotations
import os, sys, argparse
from typing import Optional, Dict, List

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QKeySequence, QShortcut

from ui_qt.board.core.data_models import Stroke, Img
from ui_qt.board.core.canvas_widget import CanvasWidget
from ui_qt.board.core.tool_api import Tool
from ui_qt.board.state.board_state import BoardState
from ui_qt.board.ui.toolbar import BoardToolbar
from ui_qt.board.tools.pen_tool import PenTool
from ui_qt.board.tools.eraser_tool import EraserTool
from ui_qt.board.tools.erase_area_tool import EraseAreaTool
from ui_qt.board.tools.shape_tool import ShapeTool
from ui_qt.board.tools.select_tool import SelectTool
from ui_qt.board.tools.screen_snip import ScreenSnipOverlay, SnipController
from ui_qt.board.io import file_io

class DrawingBoardWindowQt(QtWidgets.QMainWindow):
    """Cửa sổ chính – điều phối core/state/ui/tools, giữ QSettings & phím tắt."""
    def __init__(self, parent=None, group_name=None, session_date=None,
                 session_id: Optional[int]=None, on_saved=None,
                 board_path: Optional[str]=None, lesson_dir: Optional[str]=None):
        super().__init__(parent)
        self.setWindowTitle("✨ Bảng vẽ Bài giảng (Qt)")
        self.resize(1200, 800)

        # ---- meta ----
        self._on_saved_cb = on_saved
        self.group_name = group_name or ""
        self.session_date = session_date or ""
        self.session_id = session_id
        self.lesson_dir = lesson_dir or os.path.join(os.getcwd(), "data", "lessons", str(self.session_id or "unknown"))

        # ---- settings ----
        self._settings = QtCore.QSettings()
        self.pen_width = int(self._settings.value("pen_width", 4))
        self.eraser_width = int(self._settings.value("eraser_width", 30))
        self._last_eraser_kind = str(self._settings.value("eraser_kind", "stroke"))  # "stroke"|"rect"|"lasso"
        self.erase_area_mode = str(self._settings.value("erase_area_mode", "rect"))
        self.pen_rgba = (0,0,0,255)
        self.shape_kind = "rect"

        # ---- state ----
        self.state = BoardState()

        # ---- UI ----
        self._build_ui()

        # ---- tools ----
        self._install_tools()
        self.current_tool_obj: Optional[Tool] = None
        self._set_tool("pen")

        # ---- load nếu có ----
        self._current_board_path: Optional[str] = None
        if board_path and os.path.exists(board_path):
            self.load_from_file(board_path)

    # ========== UI ==========
    def _build_ui(self):
        # Toolbar
        self.toolbar = BoardToolbar(self, init_pen_width=self.pen_width,
                                    init_eraser_width=self.eraser_width,
                                    init_eraser_kind=self._last_eraser_kind,
                                    init_shape=self.shape_kind)
        self.addToolBar(self.toolbar)

        # Kết nối signal từ toolbar
        self.toolbar.toolChanged.connect(self._on_tool_changed)
        self.toolbar.shapeChanged.connect(self._on_shape_changed)
        self.toolbar.eraserKindChanged.connect(self._on_eraser_kind)
        self.toolbar.colorPicked.connect(self._on_color_picked)
        self.toolbar.penWidthChanged.connect(lambda v: self._set_width("pen", v))
        self.toolbar.eraserWidthChanged.connect(lambda v: self._set_width("eraser", v))
        self.toolbar.requestInsertImage.connect(self.insert_image_from_file)
        self.toolbar.requestPasteImage.connect(self.paste_from_clipboard)
        self.toolbar.requestSnip.connect(self.toggle_snip_controller)
        self.toolbar.requestDeleteImage.connect(self.delete_selected_image)
        self.toolbar.requestSave.connect(self.save_to_lesson)
        self.toolbar.requestSaveAs.connect(self.save_as_dialog)
        self.toolbar.requestOpen.connect(self.open_dialog)
        self.toolbar.pagePrev.connect(self._page_prev)
        self.toolbar.pageNext.connect(self._page_next)
        self.toolbar.pageAdd.connect(self._page_add)
        self.toolbar.pageDel.connect(self._page_del)
        self.toolbar.toggleFull.connect(self._toggle_fullscreen)
        self.toolbar.toggleMaxRestore.connect(self._toggle_max_restore)

        # Central canvas + scroll
        self.scroll = QtWidgets.QScrollArea(self); self.scroll_area = self.scroll
        self.scroll.setWidgetResizable(True)
        self.canvas = CanvasWidget(self)
        self.scroll.setWidget(self.canvas)
        self.setCentralWidget(self.scroll)

        # PrintScreen shortcut (như bản gốc)
        self._sc_snip = QShortcut(QKeySequence(Qt.Key_Print), self)
        self._sc_snip.activated.connect(self._printscreen_behavior)

    # ========== tools ==========
    def _install_tools(self):
        self._tools: dict[str, Tool] = {
            "pen": PenTool(self),
            "eraser": EraserTool(self),
            "erase_area": EraseAreaTool(self),
            "shape": ShapeTool(self),
            "select": SelectTool(self),
        }

    def _on_tool_changed(self, name: str):
        if name == "pen": self._set_tool("pen")
        elif name == "select": self._set_tool("select")

    def _on_shape_changed(self, kind: str):
        self.shape_kind = kind
        self._set_tool("shape")
        self.toolbar.reflect_tool("shape", self._last_eraser_kind, is_shape=True)

    def _on_eraser_kind(self, kind: str):
        self._last_eraser_kind = kind; self._settings.setValue("eraser_kind", kind)
        if kind in ("rect", "lasso"):
            self.erase_area_mode = "lasso" if kind=="lasso" else "rect"
            self._settings.setValue("erase_area_mode", self.erase_area_mode)
            self._set_tool("erase_area")
        else:
            self._set_tool("eraser")
        self.toolbar.reflect_tool(self.tool, self._last_eraser_kind, is_shape=(self.tool=="shape"))

    def _on_color_picked(self, rgba: tuple):
        self.pen_rgba = rgba

    def _set_tool(self, name: str):
        if hasattr(self, "current_tool_obj") and self.current_tool_obj:
            try: self.current_tool_obj.on_deactivate()
            except Exception: pass
        self.tool = name
        self.current_tool_obj = self._tools[name]
        try: self.current_tool_obj.on_activate()
        except Exception: pass
        self.toolbar.reflect_tool(name, self._last_eraser_kind, is_shape=(name=="shape"))
        self.canvas.update()

    # ========== width / settings ==========
    def _set_width(self, kind: str, value: int):
        v = max(1, min(100, int(value)))
        if kind == "pen":
            self.pen_width = v; self._settings.setValue("pen_width", v)
        else:
            self.eraser_width = v; self._settings.setValue("eraser_width", v)
        # toolbar tự đồng bộ vì đã đổi slider/label qua signal
        self.canvas.update()

    def adjust_pen_width(self, delta: int): self._set_width("pen", self.pen_width + int(delta))
    def adjust_eraser_width(self, delta: int): self._set_width("eraser", self.eraser_width + int(delta))

    # ========== render / rebuild ==========
    def _rebuild_into(self, target_img: QtGui.QImage):
        self.state.rebuild_into(target_img)

    def _refresh_ink(self):
        self.canvas._ink.fill(Qt.transparent)
        self._rebuild_into(self.canvas._ink)
        self.canvas.update()

    # ========== images ==========
    def _place_new_img(self, img: QImage):
        max_w = max(100, int(self.canvas.virtual_w - 80))
        w, h = img.width(), img.height()
        if w > max_w:
            h = int(h * (max_w/float(w))); w = max_w
        x = int((self.canvas.virtual_w - w)/2); y = 60
        self.state.images().append(Img(qimage=img, x=x, y=y, w=w, h=h))
        self._set_tool("select"); self.canvas.update()

    def insert_image_from_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Chọn ảnh", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if not path: return
        img = QImage(path)
        if img.isNull(): QtWidgets.QMessageBox.critical(self, "Ảnh", "Không mở được ảnh."); return
        self._place_new_img(img)

    def paste_from_clipboard(self):
        md = QtWidgets.QApplication.clipboard().mimeData()
        if md is None or (not md.hasImage() and not md.hasUrls()):
            QtWidgets.QMessageBox.information(self, "Dán ảnh", "Clipboard không có ảnh."); return
        img = QtGui.QImage(md.imageData()) if md.hasImage() else QtGui.QImage(md.urls()[0].toLocalFile())
        if img.isNull(): QtWidgets.QMessageBox.information(self, "Dán ảnh", "Không đọc được ảnh."); return
        self._place_new_img(img)

    def delete_selected_image(self):
        # Xoá ảnh đang chọn (nếu SelectTool báo về), nếu không có thì xoá ảnh cuối
        sel = getattr(self._tools.get("select"), "_sel", None)
        if isinstance(sel, int) and sel < len(self.state.images()):
            self.state.images().pop(sel)
        elif self.state.images():
            self.state.images().pop()
        self._refresh_ink()

    # ========== save / load ==========
    def to_dict(self) -> dict:
        return file_io.to_dict(self.state.pages, {"group_name": self.group_name, "session_date": self.session_date})

    def load_from_file(self, path: str):
        pages, meta = file_io.load_json(path)
        self.state.pages = pages
        self.state.current_page = 0
        self.group_name = meta.get("group_name",""); self.session_date = meta.get("session_date","")
        self._refresh_ink()
        self._current_board_path = path

    def save_to_lesson(self):
        if not self.session_id:
            QtWidgets.QMessageBox.critical(self, "Bảng vẽ", "Chưa có session_id."); return
        os.makedirs(self.lesson_dir, exist_ok=True)
        path = getattr(self, "_current_board_path", None)
        if not path:
            topic = ""
            if self.parent() and hasattr(self.parent(), "topic_text"):
                try: topic = self.parent().topic_text.toPlainText().strip().splitlines()[0]
                except Exception: topic = ""
            topic_safe = (topic or "no_topic").replace(" ", "_").replace("/", "-")[:50]
            group_safe = (self.group_name or "no_group").replace(" ", "_")
            date_str = (self.session_date or "").replace("-", "_") or "unknown_date"
            fname = f"{group_safe}__{date_str}__{topic_safe}.board.json"
            path = os.path.join(self.lesson_dir, fname)
        file_io.save_json(path, self.state.pages, {"group_name": self.group_name, "session_date": self.session_date})
        self._current_board_path = path
        QtWidgets.QMessageBox.information(self, "Bảng vẽ", f"Đã lưu vào Bài giảng:\n{os.path.basename(path)}")
        if self._on_saved_cb:
            try: self._on_saved_cb(path, os.path.basename(path))
            except Exception: pass

    def save_as_dialog(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Lưu thành", "", "Board (*.board.json)")
        if not path: return
        if not path.endswith(".board.json"): path += ".board.json"
        self._current_board_path = path
        self.save_to_lesson()

    def open_dialog(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Mở bảng vẽ", "", "Board (*.board.json)")
        if path: self.load_from_file(path)

    # ========== pages ==========
    def _page_prev(self):
        if self.state.prev_page(): self._refresh_ink()
    def _page_next(self):
        if self.state.next_page(): self._refresh_ink()
    def _page_add(self):
        self.state.add_page_after(); self._refresh_ink()
    def _page_del(self):
        if not self.state.del_current_page():
            QtWidgets.QMessageBox.information(self, "Trang", "Không thể xoá, phải còn ít nhất 1 trang.")
        self._refresh_ink()

    # ========== window ==========
    def _toggle_fullscreen(self): self.setWindowState(self.windowState() ^ Qt.WindowFullScreen)
    def _toggle_max_restore(self): self.showNormal() if self.isMaximized() else self.showMaximized()

    # ========== screen capture ==========
    def toggle_snip_controller(self):
        if getattr(self, "_snip_ctrl", None) and self._snip_ctrl.isVisible():
            self._snip_ctrl.hide(); return
        if not getattr(self, "_snip_ctrl", None):
            self._snip_ctrl = SnipController(on_pick_mode=self._start_snip_mode)
        self._snip_ctrl.show(); self._snip_ctrl.raise_()
        if not getattr(self._snip_ctrl, "_placed", False):
            geo = QtGui.QGuiApplication.primaryScreen().availableGeometry()
            self._snip_ctrl.move(geo.right()-self._snip_ctrl.width()-40, geo.bottom()-self._snip_ctrl.height()-40)
            self._snip_ctrl._placed = True

    def _printscreen_behavior(self):
        if getattr(self, "_snip_ctrl", None) and self._snip_ctrl.isVisible():
            self._snip_ctrl._pick("rect")
        else:
            self.toggle_snip_controller()

    def _start_snip_mode(self, mode: str):
        self.hide(); QtWidgets.QApplication.processEvents()
        def _done(img: QImage, target: str):
            self.show(); self.raise_(); self.activateWindow()
            if target == "new": self._page_add()
            self._place_new_img(img)
            if getattr(self, "_snip_ctrl", None): self._snip_ctrl.show(); self._snip_ctrl.raise_()
        self._snip_overlay = ScreenSnipOverlay(on_done=_done, mode=mode)

# ======= Entrypoint (chạy rời) =======
def main():
    app = QtWidgets.QApplication(sys.argv)
    QtCore.QCoreApplication.setOrganizationName("TutorApp")
    QtCore.QCoreApplication.setApplicationName("DrawingBoard")
    win = DrawingBoardWindowQt(session_id=1, group_name="Demo", session_date="")
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
