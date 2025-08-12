# ui_qt/windows/student_skill_report_window_qt.py
from __future__ import annotations

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTableWidget,
    QTableWidgetItem, QPushButton, QDialog, QFormLayout, QDateEdit,
    QSpinBox, QTextEdit, QLineEdit, QMessageBox
)

from datetime import datetime


class StudentSkillReportWindowQt(QWidget):
    """
    Hồ sơ năng lực học sinh (PySide6)
    - Chọn học sinh
    - Bảng tổng hợp theo chủ đề: (Chủ đề | Điểm TB | Lần cuối đánh giá | Xếp loại)
    - Double-click 1 chủ đề để mở chi tiết: xem các lần đánh giá, thêm/sửa/xoá
    """
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager

        root = QVBoxLayout(self)
        title = QLabel("Hồ sơ năng lực theo chủ đề")
        title.setStyleSheet("font-size:18px; font-weight:700;")
        root.addWidget(title)

        # ---- Bộ lọc: chọn học sinh ----
        filt = QHBoxLayout()
        filt.addWidget(QLabel("Chọn học sinh:"))
        self.student_cb = QComboBox()
        self.student_cb.currentIndexChanged.connect(self.load_report)
        filt.addWidget(self.student_cb, 1)

        self.refresh_btn = QPushButton("Làm mới")
        self.refresh_btn.clicked.connect(self.reload_students)
        filt.addWidget(self.refresh_btn)

        root.addLayout(filt)

        # ---- Bảng tổng hợp ----
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Chủ đề", "Điểm TB", "Lần cuối đánh giá", "Xếp loại"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(self.open_detail_dialog)
        root.addWidget(self.table, 1)

        # Gợi ý sử dụng
        hint = QLabel("Mẹo: Double‑click vào 1 dòng chủ đề để xem/nhập các lần đánh giá chi tiết.")
        hint.setStyleSheet("color: gray;")
        root.addWidget(hint)

        self.reload_students()

    # ---------------- Data loading ----------------
    def reload_students(self):
        try:
            rows = self.db.execute_query(
                "SELECT id, name FROM students ORDER BY name", fetch='all'
            ) or []
            self.student_cb.blockSignals(True)
            self.student_cb.clear()
            self._students = []  # list of (id, name)
            for r in rows:
                sid = r["id"] if isinstance(r, dict) else r[0]
                name = r["name"] if isinstance(r, dict) else r[1]
                self.student_cb.addItem(f"{name} (ID {sid})")
                self._students.append((sid, name))
            self.student_cb.blockSignals(False)
            self.load_report()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không tải được danh sách học sinh:\n{e}")

    def current_student_id(self) -> int | None:
        idx = self.student_cb.currentIndex()
        if idx < 0 or idx >= len(getattr(self, "_students", [])):
            return None
        return self._students[idx][0]

    def load_report(self):
        self.table.setRowCount(0)
        sid = self.current_student_id()
        if not sid:
            return
        try:
            query = """
                SELECT chu_de, ROUND(AVG(diem),1) AS avg_score, MAX(ngay_danh_gia) AS last_date
                FROM student_skills
                WHERE student_id = ?
                GROUP BY chu_de
                ORDER BY chu_de
            """
            rows = self.db.execute_query(query, (sid,), fetch='all') or []
            self.table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                topic = r["chu_de"] if isinstance(r, dict) else r[0]
                avg = r["avg_score"] if isinstance(r, dict) else r[1]
                last_date = r["last_date"] if isinstance(r, dict) else r[2]
                rating = self.get_rating_label(avg)

                self._set_item(i, 0, topic)
                self._set_item(i, 1, f"{avg:.1f}" if avg is not None else "", align=Qt.AlignCenter)
                self._set_item(i, 2, str(last_date or ""), align=Qt.AlignCenter)
                self._set_item(i, 3, rating, align=Qt.AlignCenter)

            self.table.resizeColumnsToContents()
            self.table.horizontalHeader().setStretchLastSection(True)

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không tải được báo cáo:\n{e}")

    def _set_item(self, row: int, col: int, text: str, align: Qt.AlignmentFlag | None = None):
        it = QTableWidgetItem(text)
        if align is not None:
            it.setTextAlignment(align | Qt.AlignVCenter)
        self.table.setItem(row, col, it)

    @staticmethod
    def get_rating_label(score):
        if score is None:
            return ""
        try:
            s = float(score)
        except Exception:
            return ""
        if s >= 4.5:
            return "Giỏi"
        elif s >= 3.5:
            return "Khá"
        elif s >= 2.5:
            return "Trung bình"
        else:
            return "Yếu"

    # ---------------- Detail dialog ----------------
    def open_detail_dialog(self, item: QTableWidgetItem):
        row = item.row()
        topic_item = self.table.item(row, 0)
        if not topic_item:
            return
        topic = topic_item.text().strip()
        sid = self.current_student_id()
        if not sid or not topic:
            return

        dlg = SkillDetailDialog(self.db, student_id=sid, student_name=self._students[self.student_cb.currentIndex()][1],
                                topic=topic, parent=self)
        if dlg.exec() == QDialog.Accepted:
            # reload summary after changes
            self.load_report()


class SkillDetailDialog(QDialog):
    """
    Hộp thoại chi tiết đánh giá cho 1 (học sinh, chủ đề)
    - Liệt kê tất cả lần đánh giá
    - Thêm / Sửa / Xoá
    """
    def __init__(self, db_manager, student_id: int, student_name: str, topic: str, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.student_id = student_id
        self.student_name = student_name
        self.topic = topic

        self.setWindowTitle(f"Chi tiết đánh giá – {student_name} | {topic}")
        self.resize(720, 480)

        root = QVBoxLayout(self)

        header = QLabel(f"Học sinh: <b>{student_name}</b> &nbsp;&nbsp;|&nbsp;&nbsp; Chủ đề: <b>{topic}</b>")
        root.addWidget(header)

        # Bảng chi tiết
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Ngày đánh giá", "Điểm (1–5)", "Nhận xét"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)

        # Form nhập / chỉnh sửa
        form_box = QtWidgets.QGroupBox("Nhập/Chỉnh sửa")
        form = QFormLayout(form_box)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate.currentDate())

        self.score_spin = QSpinBox()
        self.score_spin.setRange(1, 5)
        self.score_spin.setValue(3)

        self.comment_text = QTextEdit()
        self.comment_text.setPlaceholderText("Nhận xét (tuỳ chọn)")

        # ID đang chỉnh (nếu có)
        self.id_edit = QLineEdit()
        self.id_edit.setReadOnly(True)
        self.id_edit.setPlaceholderText("ID bản ghi (auto)")

        form.addRow("ID:", self.id_edit)
        form.addRow("Ngày đánh giá:", self.date_edit)
        form.addRow("Điểm (1–5):", self.score_spin)
        form.addRow("Nhận xét:", self.comment_text)

        root.addWidget(form_box)

        # Buttons
        btns = QHBoxLayout()
        self.btn_add = QPushButton("➕ Thêm")
        self.btn_update = QPushButton("💾 Cập nhật")
        self.btn_delete = QPushButton("🗑️ Xoá")
        self.btn_close = QPushButton("Đóng")
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_update)
        btns.addWidget(self.btn_delete)
        btns.addStretch(1)
        btns.addWidget(self.btn_close)
        root.addLayout(btns)

        # Signals
        self.table.itemSelectionChanged.connect(self.on_row_selected)
        self.btn_add.clicked.connect(self.add_entry)
        self.btn_update.clicked.connect(self.update_entry)
        self.btn_delete.clicked.connect(self.delete_entry)
        self.btn_close.clicked.connect(self.accept)

        self.load_details()

    # --------- Helpers ---------
    def load_details(self):
        self.table.setRowCount(0)
        rows = self.db.execute_query(
            """
            SELECT id, ngay_danh_gia, diem, nhan_xet
            FROM student_skills
            WHERE student_id = ? AND chu_de = ?
            ORDER BY ngay_danh_gia DESC, id DESC
            """,
            (self.student_id, self.topic),
            fetch='all'
        ) or []

        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            rid = r["id"] if isinstance(r, dict) else r[0]
            ngay = r["ngay_danh_gia"] if isinstance(r, dict) else r[1]
            diem = r["diem"] if isinstance(r, dict) else r[2]
            nx = r["nhan_xet"] if isinstance(r, dict) else r[3]

            self._set(i, 0, str(rid), center=True)
            self._set(i, 1, str(ngay), center=True)
            self._set(i, 2, str(diem), center=True)
            self._set(i, 3, str(nx or ""))

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.clear_form()

    def _set(self, r, c, text, center=False):
        it = QTableWidgetItem(text)
        if center:
            it.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(r, c, it)

    def clear_form(self):
        self.id_edit.clear()
        self.date_edit.setDate(QDate.currentDate())
        self.score_spin.setValue(3)
        self.comment_text.clear()

    def on_row_selected(self):
        sel = self.table.currentRow()
        if sel < 0:
            self.clear_form()
            return
        rid = self.table.item(sel, 0).text()
        ngay = self.table.item(sel, 1).text()
        diem = self.table.item(sel, 2).text()
        nx = self.table.item(sel, 3).text()

        self.id_edit.setText(rid)
        try:
            d = datetime.strptime(ngay, "%Y-%m-%d").date()
            self.date_edit.setDate(QDate(d.year, d.month, d.day))
        except Exception:
            pass
        try:
            self.score_spin.setValue(int(diem))
        except Exception:
            self.score_spin.setValue(3)
        self.comment_text.setPlainText(nx)

    # --------- CRUD ---------
    def add_entry(self):
        try:
            qd = self.date_edit.date()
            ngay = f"{qd.year():04d}-{qd.month():02d}-{qd.day():02d}"
            diem = int(self.score_spin.value())
            nhan_xet = self.comment_text.toPlainText().strip()

            self.db.add_student_skill(self.student_id, self.topic, ngay, diem, nhan_xet)
            QMessageBox.information(self, "Thành công", "Đã thêm đánh giá.")
            self.load_details()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể thêm đánh giá:\n{e}")

    def update_entry(self):
        rid = self.id_edit.text().strip()
        if not rid:
            QMessageBox.warning(self, "Thiếu thông tin", "Hãy chọn 1 bản ghi để cập nhật.")
            return
        try:
            diem = int(self.score_spin.value())
            nhan_xet = self.comment_text.toPlainText().strip()
            self.db.update_student_skill(int(rid), diem, nhan_xet)
            QMessageBox.information(self, "Thành công", "Đã cập nhật đánh giá.")
            self.load_details()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể cập nhật:\n{e}")

    def delete_entry(self):
        rid = self.id_edit.text().strip()
        if not rid:
            QMessageBox.warning(self, "Thiếu thông tin", "Hãy chọn 1 bản ghi để xoá.")
            return
        if QMessageBox.question(self, "Xác nhận", "Xoá bản ghi này?") != QMessageBox.Yes:
            return
        try:
            self.db.delete_student_skill(int(rid))
            QMessageBox.information(self, "Thành công", "Đã xoá đánh giá.")
            self.load_details()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể xoá:\n{e}")
