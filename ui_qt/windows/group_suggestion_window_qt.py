# ui_qt/windows/group_suggestion_window_qt.py
from __future__ import annotations

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Qt


class GroupSuggestionWindowQt(QtWidgets.QWidget):
    """
    PySide6 - Gợi ý nhóm học phù hợp theo chủ đề kỹ năng
    Chuyển đổi 1:1 từ bản Tkinter, giữ nguyên truy vấn & logic tính điểm.
    """
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setObjectName("GroupSuggestionWindowQt")
        self.setWindowTitle("Gợi ý nhóm học phù hợp")
        self.resize(850, 600)

        root = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("🔍 Phân tích nhóm phù hợp theo chủ đề kỹ năng")
        title.setStyleSheet("font-size:16px; font-weight:600;")
        root.addWidget(title)

        form = QtWidgets.QWidget()
        form_l = QtWidgets.QGridLayout(form)
        root.addWidget(form)

        form_l.addWidget(QtWidgets.QLabel("Chọn học sinh:"), 0, 0, Qt.AlignLeft)
        self.student_cb = QtWidgets.QComboBox()
        form_l.addWidget(self.student_cb, 0, 1)

        form_l.addWidget(QtWidgets.QLabel("Chủ đề trọng tâm (ngăn cách bằng dấu phẩy):"), 1, 0, Qt.AlignLeft)
        self.topic_edit = QtWidgets.QLineEdit()
        self.topic_edit.setPlaceholderText("Ví dụ: Đại số, Hình học, Hàm số …")
        form_l.addWidget(self.topic_edit, 1, 1)

        self.btn_analyze = QtWidgets.QPushButton("Phân tích nhóm phù hợp")
        self.btn_analyze.clicked.connect(self.analyze)
        form_l.addWidget(self.btn_analyze, 2, 0, 1, 2)

        # Kết quả
        self.table = QtWidgets.QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Nhóm", "Lệch điểm trung bình"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        root.addWidget(self.table, 1)

        self._load_students()

    # ---------------- helpers ----------------
    def _load_students(self):
        """Nạp danh sách học sinh vào combobox."""
        rows = self.db.execute_query(
            "SELECT id, name FROM students ORDER BY name", fetch='all'
        ) or []
        self._student_map = {}  # display -> id
        self.student_cb.clear()
        for sid, name in rows:
            disp = f"{name} (ID {sid})"
            self._student_map[disp] = sid
            self.student_cb.addItem(disp)

    # ---------------- actions ----------------
    def analyze(self):
        """Giống bản Tkinter: tính độ lệch điểm TB theo các chủ đề được nhập."""
        self.table.setRowCount(0)

        display = self.student_cb.currentText().strip()
        student_id = self._student_map.get(display)
        if not student_id:
            QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng chọn học sinh.")
            return

        topics = [t.strip() for t in self.topic_edit.text().split(",") if t.strip()]
        if not topics:
            QtWidgets.QMessageBox.warning(self, "Thiếu chủ đề", "Vui lòng nhập ít nhất 1 chủ đề.")
            return

        # Lấy điểm TB của học sinh theo từng chủ đề
        student_scores = {}
        for topic in topics:
            row = self.db.execute_query(
                "SELECT ROUND(AVG(diem), 1) FROM student_skills WHERE student_id = ? AND chu_de = ?",
                (student_id, topic), fetch='one'
            )
            if row and row[0] is not None:
                student_scores[topic] = float(row[0])

        if not student_scores:
            QtWidgets.QMessageBox.information(
                self, "Không có dữ liệu",
                "Học sinh này chưa được đánh giá các chủ đề đã chọn."
            )
            return

        groups = self.db.execute_query("SELECT id, name FROM groups ORDER BY name", fetch='all') or []

        results = []
        for gid, gname in groups:
            total_diff, count = 0.0, 0
            for topic, st_score in student_scores.items():
                g_row = self.db.execute_query(
                    """
                    SELECT ROUND(AVG(diem), 1)
                    FROM student_skills
                    WHERE student_id IN (SELECT id FROM students WHERE group_id = ?)
                      AND chu_de = ?
                    """,
                    (gid, topic), fetch='one'
                )
                if g_row and g_row[0] is not None:
                    diff = abs(st_score - float(g_row[0]))
                    total_diff += diff
                    count += 1
            if count > 0:
                results.append((gname, round(total_diff / count, 2)))

        # sắp xếp tăng dần theo độ lệch
        results.sort(key=lambda x: x[1])

        # đổ ra bảng
        self.table.setRowCount(len(results))
        for r, (name, diff) in enumerate(results):
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(name))
            item = QtWidgets.QTableWidgetItem(f"{diff:.2f}")
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, 1, item)
