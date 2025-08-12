# ui_qt/windows/submit_exercise_window_qt.py
from __future__ import annotations

import os
import shutil
from datetime import datetime

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QLineEdit, QTextEdit, QDateEdit, QFileDialog, QMessageBox, QGroupBox, QFormLayout
)


class SubmitExerciseWindowQt(QWidget):
    """
    📤 Học sinh nộp bài tập (PySide6)
    - Giữ nguyên logic từ bản Tkinter:
      + Chọn học sinh -> nạp danh sách bài đã giao cho học sinh đó
      + Chọn file, ngày nộp, điểm, nhận xét
      + Sao chép file vào thư mục submissions và ghi CSDL bảng exercise_submissions
    """

    def __init__(self, db_manager, parent=None, submissions_dir: str = "data/submissions"):
        super().__init__(parent)
        self.db = db_manager
        self.submissions_dir = submissions_dir
        self.file_path: str | None = None

        self.setObjectName("SubmitExerciseWindowQt")
        self.setWindowTitle("📤 Học sinh nộp bài tập")
        self.resize(780, 440)

        root = QVBoxLayout(self)

        # --- Khối chọn / nhập thông tin ---
        box = QGroupBox("Thông tin nộp bài")
        form = QFormLayout(box)

        # Học sinh
        self.student_cb = QComboBox()
        self.student_map: dict[str, int] = {}
        try:
            rows = self.db.execute_query(
                "SELECT id, name FROM students ORDER BY name", fetch='all'
            ) or []
            for r in rows:
                sid = r["id"] if hasattr(r, "keys") else r[0]
                name = r["name"] if hasattr(r, "keys") else r[1]
                label = f"{name} (ID {sid})"
                self.student_cb.addItem(label)
                self.student_map[label] = sid
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không tải được danh sách học sinh:\n{e}")
        self.student_cb.currentIndexChanged.connect(self.update_assignments_for_student)
        form.addRow("Chọn học sinh:", self.student_cb)

        # Bài tập đã giao
        self.assignment_cb = QComboBox()
        self.assignment_map: dict[str, int] = {}
        form.addRow("Chọn bài tập đã giao:", self.assignment_cb)

        # File bài làm
        h_file = QHBoxLayout()
        self.file_label = QLineEdit()
        self.file_label.setPlaceholderText("Chưa chọn file…")
        self.file_label.setReadOnly(True)
        btn_pick = QPushButton("📂 Chọn file")
        btn_pick.clicked.connect(self.select_file)
        h_file.addWidget(self.file_label, 1)
        h_file.addWidget(btn_pick)
        file_wrap = QWidget()
        file_wrap.setLayout(h_file)
        form.addRow("File bài làm:", file_wrap)

        # Ngày nộp
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate.currentDate())
        form.addRow("Ngày nộp:", self.date_edit)

        # Điểm
        self.score_edit = QLineEdit()
        self.score_edit.setPlaceholderText("Ví dụ: 8.5 (để trống nếu chưa chấm)")
        form.addRow("Điểm:", self.score_edit)

        # Nhận xét
        self.comment_text = QTextEdit()
        self.comment_text.setPlaceholderText("Nhận xét (tuỳ chọn)")
        form.addRow("Nhận xét:", self.comment_text)

        root.addWidget(box)

        # --- Nút hành động ---
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_submit = QPushButton("✅ Xác nhận nộp bài")
        self.btn_submit.clicked.connect(self.submit)
        btns.addWidget(self.btn_submit)
        root.addLayout(btns)

        # Đảm bảo có bảng exercise_submissions (nếu schema cũ thiếu)
        self._ensure_table()

        # Nạp danh sách bài theo học sinh đầu tiên (nếu có)
        self.update_assignments_for_student()

    # ------------------ Helpers ------------------
    def _ensure_table(self):
        try:
            self.db.execute_query("""
                CREATE TABLE IF NOT EXISTS exercise_submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    assignment_id INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    ngay_nop TEXT NOT NULL,
                    diem TEXT,
                    nhan_xet TEXT,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
                )
            """)
        except Exception:
            # Nếu DB đã có bảng/khác đôi chút schema thì bỏ qua
            pass

    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn file bài làm", "", "Tất cả (*.*)")
        if path:
            self.file_path = path
            self.file_label.setText(os.path.basename(path))

    # ------------------ Data flows ------------------
    def update_assignments_for_student(self):
        self.assignment_cb.clear()
        self.assignment_map.clear()

        label = self.student_cb.currentText().strip()
        sid = self.student_map.get(label)
        if not sid:
            return
        try:
            rows = self.db.execute_query(
                """
                SELECT ae.id, e.ten_bai, e.chu_de
                FROM assigned_exercises ae
                JOIN exercises e ON ae.exercise_id = e.id
                WHERE ae.student_id = ?
                ORDER BY ae.ngay_giao DESC
                """,
                (sid,), fetch='all'
            ) or []

            for r in rows:
                aid = r["id"] if hasattr(r, "keys") else r[0]
                ten_bai = r["ten_bai"] if hasattr(r, "keys") else r[1]
                chu_de = r["chu_de"] if hasattr(r, "keys") else r[2]
                text = f"[{chu_de}] {ten_bai}"
                self.assignment_cb.addItem(text)
                self.assignment_map[text] = aid
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không tải được bài đã giao:\n{e}")

    # ------------------ Submit ------------------
    def submit(self):
        # Lấy dữ liệu
        stu_label = self.student_cb.currentText().strip()
        ass_label = self.assignment_cb.currentText().strip()
        student_id = self.student_map.get(stu_label)
        assignment_id = self.assignment_map.get(ass_label)
        if not student_id or not assignment_id or not self.file_path:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng chọn học sinh, bài tập và file.")
            return

        qd = self.date_edit.date()
        ngay = f"{qd.year():04d}-{qd.month():02d}-{qd.day():02d}"
        diem = self.score_edit.text().strip()
        nhan_xet = self.comment_text.toPlainText().strip()

        # Tạo thư mục submissions (ưu tiên dưới `data/`)
        try:
            os.makedirs(self.submissions_dir, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể tạo thư mục lưu bài:\n{e}")
            return

        # Tạo tên file đích giống bản Tk: {student_id}_{assignment_id}_{timestamp}{ext}
        ext = os.path.splitext(self.file_path)[1]
        fname = f"{student_id}_{assignment_id}_{int(datetime.now().timestamp())}{ext}"
        save_path = os.path.join(self.submissions_dir, fname)

        try:
            shutil.copy2(self.file_path, save_path)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể chép file:\n{e}")
            return

        # Ghi vào CSDL
        try:
            self.db.execute_query(
                """
                INSERT INTO exercise_submissions (student_id, assignment_id, file_path, ngay_nop, diem, nhan_xet)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (student_id, assignment_id, save_path, ngay, diem, nhan_xet)
            )
            QMessageBox.information(self, "Thành công", "Đã lưu bài nộp.")
            # reset form nhẹ
            self.file_path = None
            self.file_label.clear()
            self.score_edit.clear()
            self.comment_text.clear()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi CSDL", f"Có lỗi khi lưu vào cơ sở dữ liệu:\n{e}")
