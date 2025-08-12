# ui_qt/windows/skill_rating_window_qt.py
from __future__ import annotations

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QTextEdit, QSpinBox, QDateEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QGroupBox, QFormLayout
)


class SkillRatingWindowQt(QWidget):
    """
    ⭐ Đánh giá năng lực (nhanh) – PySide6
    - Chọn Nhóm → Học sinh
    - Nhập Chủ đề, Ngày, Điểm (1–5), Nhận xét → LƯU
    - Bảng đánh giá gần đây cho học sinh đang chọn (chọn dòng để sửa/xoá)
    """
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager

        self.group_map: dict[str, int] = {}
        self.student_map: dict[str, int] = {}
        self.current_row_id: int | None = None

        self._build_ui()
        self._ensure_table()
        self._load_groups()

    # -------------------- UI --------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("⭐ Đánh giá năng lực (nhanh)")
        title.setStyleSheet("font-size:18px; font-weight:700;")
        root.addWidget(title)

        # ---- Khối chọn nhóm/học sinh ----
        box_sel = QGroupBox("Chọn đối tượng")
        sel = QFormLayout(box_sel)

        self.cb_group = QComboBox()
        self.cb_group.currentIndexChanged.connect(self.on_group_changed)
        sel.addRow("Nhóm:", self.cb_group)

        self.cb_student = QComboBox()
        self.cb_student.currentIndexChanged.connect(self.reload_recent)
        sel.addRow("Học sinh:", self.cb_student)

        root.addWidget(box_sel)

        # ---- Khối nhập đánh giá ----
        box_form = QGroupBox("Thông tin đánh giá")
        form = QFormLayout(box_form)

        self.ed_topic = QLineEdit()
        self.ed_topic.setPlaceholderText("VD: Hệ phương trình, Hình học góc…")
        form.addRow("Chủ đề:", self.ed_topic)

        self.dt_eval = QDateEdit()
        self.dt_eval.setCalendarPopup(True)
        self.dt_eval.setDisplayFormat("yyyy-MM-dd")
        self.dt_eval.setDate(QDate.currentDate())
        form.addRow("Ngày đánh giá:", self.dt_eval)

        self.sp_score = QSpinBox()
        self.sp_score.setRange(1, 5)
        self.sp_score.setValue(3)
        form.addRow("Điểm (1–5):", self.sp_score)

        self.tx_comment = QTextEdit()
        self.tx_comment.setPlaceholderText("Nhận xét (tuỳ chọn)")
        form.addRow("Nhận xét:", self.tx_comment)

        # nút hành động cho form
        hbtn = QHBoxLayout()
        self.btn_save = QPushButton("💾 Lưu / Cập nhật")
        self.btn_clear = QPushButton("Làm mới form")
        self.btn_save.clicked.connect(self.save_or_update)
        self.btn_clear.clicked.connect(self.clear_form)
        hbtn.addStretch(1)
        hbtn.addWidget(self.btn_clear)
        hbtn.addWidget(self.btn_save)
        form.addRow(hbtn)

        root.addWidget(box_form)

        # ---- Bảng các đánh giá gần đây ----
        box_tbl = QGroupBox("Đánh giá gần đây (theo học sinh)")
        vtbl = QVBoxLayout(box_tbl)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "Ngày", "Chủ đề", "Điểm", "Nhận xét", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self.on_row_selected)
        vtbl.addWidget(self.table)

        # nút thao tác bảng
        htbl = QHBoxLayout()
        self.btn_delete = QPushButton("🗑️ Xoá bản ghi")
        self.btn_refresh = QPushButton("↻ Làm mới danh sách")
        self.btn_delete.clicked.connect(self.delete_selected)
        self.btn_refresh.clicked.connect(self.reload_recent)
        htbl.addStretch(1)
        htbl.addWidget(self.btn_delete)
        htbl.addWidget(self.btn_refresh)
        vtbl.addLayout(htbl)

        root.addWidget(box_tbl)

    # -------------------- DB helpers --------------------
    def _ensure_table(self):
        """Đảm bảo tồn tại bảng student_skills (nếu chưa có)."""
        try:
            self.db.execute_query("""
                CREATE TABLE IF NOT EXISTS student_skills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    chu_de TEXT NOT NULL,
                    ngay_danh_gia TEXT NOT NULL,
                    diem INTEGER NOT NULL,
                    nhan_xet TEXT,
                    FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
                )
            """)
        except Exception:
            # có thể bảng đã tồn tại với schema tương tự
            pass

    def _load_groups(self):
        try:
            rows = self.db.execute_query(
                "SELECT id, name FROM groups ORDER BY name", fetch='all'
            ) or []
            self.cb_group.blockSignals(True)
            self.cb_group.clear()
            self.group_map.clear()
            self.cb_group.addItem("")  # rỗng = không lọc
            for r in rows:
                gid = r["id"] if hasattr(r, "keys") else r[0]
                name = r["name"] if hasattr(r, "keys") else r[1]
                self.cb_group.addItem(name)
                self.group_map[name] = gid
            self.cb_group.blockSignals(False)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không tải được nhóm:\n{e}")
        self.on_group_changed()

    def on_group_changed(self):
        name = self.cb_group.currentText().strip()
        gid = self.group_map.get(name)
        try:
            if gid:
                rows = self.db.execute_query(
                    "SELECT id, name FROM students WHERE group_id = ? ORDER BY name",
                    (gid,), fetch='all'
                ) or []
            else:
                rows = self.db.execute_query(
                    "SELECT id, name FROM students ORDER BY name", fetch='all'
                ) or []

            self.cb_student.blockSignals(True)
            self.cb_student.clear()
            self.student_map.clear()
            for r in rows:
                sid = r["id"] if hasattr(r, "keys") else r[0]
                sname = r["name"] if hasattr(r, "keys") else r[1]
                label = f"{sname} (ID {sid})"
                self.cb_student.addItem(label)
                self.student_map[label] = sid
            self.cb_student.blockSignals(False)
            self.reload_recent()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không tải được học sinh:\n{e}")

    # -------------------- Actions --------------------
    def current_student_id(self) -> int | None:
        label = self.cb_student.currentText().strip()
        return self.student_map.get(label)

    def save_or_update(self):
        sid = self.current_student_id()
        topic = self.ed_topic.text().strip()
        ngay = self.dt_eval.date().toString("yyyy-MM-dd")
        diem = int(self.sp_score.value())
        nhan_xet = self.tx_comment.toPlainText().strip()

        if not sid or not topic:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng chọn học sinh và nhập Chủ đề.")
            return

        try:
            if self.current_row_id:  # cập nhật
                self.db.execute_query(
                    "UPDATE student_skills SET chu_de=?, ngay_danh_gia=?, diem=?, nhan_xet=? WHERE id=?",
                    (topic, ngay, diem, nhan_xet, self.current_row_id)
                )
                QMessageBox.information(self, "Thành công", "Đã cập nhật đánh giá.")
            else:  # thêm mới
                self.db.execute_query(
                    "INSERT INTO student_skills (student_id, chu_de, ngay_danh_gia, diem, nhan_xet) VALUES (?, ?, ?, ?, ?)",
                    (sid, topic, ngay, diem, nhan_xet)
                )
                QMessageBox.information(self, "Thành công", "Đã lưu đánh giá.")
            self.clear_form()
            self.reload_recent()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu dữ liệu:\n{e}")

    def clear_form(self):
        self.current_row_id = None
        self.ed_topic.clear()
        self.dt_eval.setDate(QDate.currentDate())
        self.sp_score.setValue(3)
        self.tx_comment.clear()
        # Bỏ chọn bảng nếu đang chọn
        self.table.clearSelection()

    def reload_recent(self):
        """Nạp các đánh giá gần đây theo học sinh đang chọn."""
        self.table.setRowCount(0)
        self.current_row_id = None
        sid = self.current_student_id()
        if not sid:
            return
        try:
            rows = self.db.execute_query(
                """
                SELECT id, ngay_danh_gia, chu_de, diem, nhan_xet
                FROM student_skills
                WHERE student_id = ?
                ORDER BY ngay_danh_gia DESC, id DESC
                LIMIT 200
                """,
                (sid,), fetch='all'
            ) or []
            for r in rows:
                if hasattr(r, "keys"):
                    rid, ngay, chu_de, diem, nx = r["id"], r["ngay_danh_gia"], r["chu_de"], r["diem"], r["nhan_xet"]
                else:
                    rid, ngay, chu_de, diem, nx = r
                row = self.table.rowCount()
                self.table.insertRow(row)
                self._set(row, 0, str(rid), center=True)
                self._set(row, 1, str(ngay), center=True)
                self._set(row, 2, str(chu_de))
                self._set(row, 3, str(diem), center=True)
                self._set(row, 4, str(nx or ""))

                # cột 5: hint
                self._set(row, 5, "Chọn dòng để sửa/xoá", center=True)

            self.table.resizeColumnsToContents()
            self.table.horizontalHeader().setStretchLastSection(True)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không tải dữ liệu:\n{e}")

    def _set(self, r, c, text, center=False):
        it = QTableWidgetItem(text)
        if center:
            it.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(r, c, it)

    def on_row_selected(self):
        """Khi chọn 1 dòng → đổ lại dữ liệu lên form để sửa nhanh."""
        row = self.table.currentRow()
        if row < 0:
            self.current_row_id = None
            return
        try:
            rid = int(self.table.item(row, 0).text())
            ngay = self.table.item(row, 1).text()
            chu_de = self.table.item(row, 2).text()
            diem = int(self.table.item(row, 3).text())
            nx = self.table.item(row, 4).text()
        except Exception:
            return

        self.current_row_id = rid
        # set form
        self.ed_topic.setText(chu_de)
        try:
            y, m, d = [int(x) for x in ngay.split("-")]
            self.dt_eval.setDate(QDate(y, m, d))
        except Exception:
            self.dt_eval.setDate(QDate.currentDate())
        self.sp_score.setValue(diem)
        self.tx_comment.setPlainText(nx)

    def delete_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Thông báo", "Hãy chọn một dòng để xoá.")
            return
        rid = self.table.item(row, 0).text()
        if not rid:
            return
        if QMessageBox.question(self, "Xác nhận", "Xoá bản ghi này?") != QMessageBox.Yes:
            return
        try:
            self.db.execute_query("DELETE FROM student_skills WHERE id = ?", (int(rid),))
            QMessageBox.information(self, "Thành công", "Đã xoá.")
            self.clear_form()
            self.reload_recent()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể xoá:\n{e}")
