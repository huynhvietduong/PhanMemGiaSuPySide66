# ui_qt/windows/exercise_manager_window_qt.py
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QMenu, QMessageBox, QDialog,
    QFormLayout, QDialogButtonBox, QTextEdit
)
import os
import webbrowser

class EditExerciseDialog(QDialog):
    """Form sửa bài tập (5 trường) – tương đương EditExerciseWindow Tkinter."""
    def __init__(self, parent, db, ex_id, values, on_saved=None):
        super().__init__(parent)
        self.db = db
        self.ex_id = ex_id
        self.on_saved = on_saved
        self.setWindowTitle("✏️ Sửa bài tập")
        self.resize(560, 360)

        chu_de, ten_bai, loai_tap, noi_dung, ghi_chu = values

        form = QFormLayout(self)

        self.ed_chu_de  = QLineEdit(chu_de)
        self.ed_ten_bai = QLineEdit(ten_bai)
        self.ed_loai    = QLineEdit(loai_tap)
        self.ed_noi_dung= QLineEdit(noi_dung)
        self.ed_ghi_chu = QLineEdit(ghi_chu)

        form.addRow("Chủ đề:", self.ed_chu_de)
        form.addRow("Tên bài:", self.ed_ten_bai)
        form.addRow("Loại:", self.ed_loai)
        form.addRow("Nội dung:", self.ed_noi_dung)
        form.addRow("Ghi chú:", self.ed_ghi_chu)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.save)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def save(self):
        values = (
            self.ed_chu_de.text().strip(),
            self.ed_ten_bai.text().strip(),
            self.ed_loai.text().strip(),
            self.ed_noi_dung.text().strip(),
            self.ed_ghi_chu.text().strip(),
        )
        if not all(values):
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng điền đầy đủ.")
            return
        self.db.execute_query(
            """
            UPDATE exercises SET chu_de = ?, ten_bai = ?, loai_tap = ?, noi_dung = ?, ghi_chu = ?
            WHERE id = ?
            """,
            (*values, self.ex_id)
        )
        QMessageBox.information(self, "Thành công", "Đã cập nhật bài tập.")
        if self.on_saved:
            self.on_saved()
        self.accept()


class ExerciseManagerWindowQt(QWidget):
    """
    🗂️ Quản lý bài tập – PySide6
    - Lọc theo chủ đề
    - Bảng danh sách (Chủ đề, Tên bài, Loại, Nội dung, Ghi chú)
    - Menu chuột phải: Xem / Sửa / Xoá (giống bản Tkinter):contentReference[oaicite:3]{index=3}
    """
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setObjectName("ExerciseManagerWindowQt")

        root = QVBoxLayout(self)

        # Top filter
        top = QHBoxLayout()
        top.addWidget(QLabel("Lọc theo chủ đề:"))
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Nhập từ khoá chủ đề…")
        btn_filter = QPushButton("Lọc")
        btn_filter.clicked.connect(self.load_data)
        top.addWidget(self.filter_edit)
        top.addWidget(btn_filter)
        root.addLayout(top)

        # Table
        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels(["Chủ đề", "Tên bài", "Loại", "Nội dung", "Ghi chú"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_context_menu)
        root.addWidget(self.table)

        # row_id -> ex_id
        self._id_map = {}

        self.load_data()

    # ---------- Data ----------
    def load_data(self):
        self.table.setRowCount(0)
        self._id_map.clear()

        keyword = self.filter_edit.text().strip()
        if keyword:
            query = """
                SELECT id, chu_de, ten_bai, loai_tap, noi_dung, ghi_chu
                FROM exercises
                WHERE chu_de LIKE ?
                ORDER BY chu_de
            """
            rows = self.db.execute_query(query, ('%' + keyword + '%',), fetch='all') or []
        else:
            rows = self.db.execute_query(
                "SELECT id, chu_de, ten_bai, loai_tap, noi_dung, ghi_chu FROM exercises ORDER BY chu_de",
                fetch='all'
            ) or []

        for r in rows:
            # sqlite3.Row or tuple – hỗ trợ cả 2
            if hasattr(r, "keys"):
                ex_id, chu_de, ten_bai, loai, nd, gc = r["id"], r["chu_de"], r["ten_bai"], r["loai_tap"], r["noi_dung"], r["ghi_chu"]
            else:
                ex_id, chu_de, ten_bai, loai, nd, gc = r

            row = self.table.rowCount()
            self.table.insertRow(row)
            for c, val in enumerate([chu_de, ten_bai, loai, nd, gc]):
                item = QTableWidgetItem(str(val) if val is not None else "")
                item.setData(Qt.UserRole, ex_id if c == 0 else None)
                self.table.setItem(row, c, item)
            self._id_map[row] = ex_id

    def selected_row_info(self):
        sel = self.table.currentRow()
        if sel < 0:
            return None, None
        ex_id = self._id_map.get(sel)
        values = [self.table.item(sel, c).text() if self.table.item(sel, c) else "" for c in range(5)]
        return ex_id, values  # (id, [chu_de, ten_bai, loai, noi_dung, ghi_chu])

    # ---------- Context menu ----------
    def open_context_menu(self, pos):
        if self.table.rowCount() == 0:
            return
        menu = QMenu(self)
        act_view = QAction("👁️ Xem bài tập", self)
        act_edit = QAction("✏️ Sửa bài tập", self)
        act_del  = QAction("🗑️ Xoá bài tập", self)
        act_view.triggered.connect(self.view_selected)
        act_edit.triggered.connect(self.edit_selected)
        act_del.triggered.connect(self.delete_selected)
        menu.addAction(act_view)
        menu.addAction(act_edit)
        menu.addAction(act_del)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    # ---------- Actions ----------
    def view_selected(self):
        ex_id, values = self.selected_row_info()
        if ex_id is None:
            return
        chu_de, ten_bai, loai_tap, noi_dung, _ = values

        if loai_tap == "text":
            dlg = QDialog(self)
            dlg.setWindowTitle(f"Bài: {ten_bai}")
            dlg.resize(560, 380)
            lay = QVBoxLayout(dlg)
            te = QTextEdit()
            te.setReadOnly(True)
            te.setPlainText(noi_dung or "")
            lay.addWidget(te)
            bb = QDialogButtonBox(QDialogButtonBox.Close)
            bb.rejected.connect(dlg.reject)
            lay.addWidget(bb)
            dlg.exec()

        elif loai_tap == "image":
            path = noi_dung or ""
            if os.path.exists(path):
                # mở bằng ứng dụng mặc định hệ điều hành
                webbrowser.open(path)
            else:
                QMessageBox.warning(self, "Không tìm thấy ảnh", f"Đường dẫn không tồn tại:\n{path}")
        else:
            # Loại khác – hiển thị nội dung thô
            QMessageBox.information(self, f"Bài: {ten_bai}", noi_dung or "(Không có nội dung)")

    def edit_selected(self):
        ex_id, values = self.selected_row_info()
        if ex_id is None:
            return
        dlg = EditExerciseDialog(self, self.db, ex_id, values, on_saved=self.load_data)
        dlg.exec()

    def delete_selected(self):
        ex_id, _ = self.selected_row_info()
        if ex_id is None:
            return
        ret = QMessageBox.question(self, "Xác nhận xoá", "Bạn có chắc muốn xoá bài tập này?")
        if ret == QMessageBox.Yes:
            self.db.execute_query("DELETE FROM exercises WHERE id = ?", (ex_id,))
            self.load_data()
