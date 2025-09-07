# ui_qt/windows/assign_exercise_window_qt.py
from __future__ import annotations
from datetime import datetime

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QDialog, QWidget, QLabel, QComboBox, QDateEdit, QTextEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea, QCheckBox, QMessageBox,
    QListWidget, QListWidgetItem, QSizePolicy, QFrame
)

class AssignExerciseWindowQt(QDialog):
    """
    📩 Giao bài tập cho học sinh / nhóm (PySide6)
    - Chọn Nhóm -> tải danh sách học sinh (checkbox)
    - Chọn Bài tập (từ bảng exercises)
    - Chọn Ngày giao + nhập Ghi chú
    - Bấm 'Giao bài tập' để chèn vào bảng assigned_exercises
    """
    def __init__(self, db_manager, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db_manager

        self.setWindowTitle("📩 Giao bài tập cho học sinh / nhóm")
        self.resize(920, 600)
        self.setModal(True)

        self.group_map: dict[str, int] = {}
        self.exercise_map: dict[str, int] = {}
        self.student_checks: dict[int, QCheckBox] = {}

        self._build_ui()
        self._load_groups()
        self._load_exercises()

    # ------------------------- UI -------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)

        # --- Hàng chọn nhóm + ngày ---
        row1 = QGridLayout()
        root.addLayout(row1)

        row1.addWidget(QLabel("Nhóm học:"), 0, 0)
        self.cb_group = QComboBox()
        self.cb_group.currentIndexChanged.connect(self._on_group_changed)
        self.cb_group.setMinimumWidth(260)
        row1.addWidget(self.cb_group, 0, 1)

        row1.addWidget(QLabel("Ngày giao:"), 0, 2, alignment=Qt.AlignRight)
        self.date_assign = QDateEdit()
        self.date_assign.setDisplayFormat("yyyy-MM-dd")
        self.date_assign.setCalendarPopup(True)
        self.date_assign.setDate(datetime.now().date())
        row1.addWidget(self.date_assign, 0, 3)

        # --- Khung danh sách học sinh (checkbox) ---
        self.student_box = QFrame()
        self.student_box.setFrameShape(QFrame.StyledPanel)
        box_layout = QVBoxLayout(self.student_box)
        box_layout.addWidget(QLabel("Chọn học sinh nhận bài:"))

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_inner = QWidget()
        self.scroll_inner_layout = QVBoxLayout(self.scroll_inner)
        self.scroll_inner_layout.addStretch(1)
        self.scroll.setWidget(self.scroll_inner)
        box_layout.addWidget(self.scroll)

        root.addWidget(self.student_box, 1)

        # --- Hàng chọn bài tập ---
        row2 = QGridLayout()
        root.addLayout(row2)

        row2.addWidget(QLabel("Chọn bài tập:"), 0, 0)
        self.cb_exercise = QComboBox()
        self.cb_exercise.setMinimumWidth(420)
        row2.addWidget(self.cb_exercise, 0, 1, 1, 3)

        # --- Ghi chú ---
        row3 = QGridLayout()
        root.addLayout(row3)
        row3.addWidget(QLabel("Ghi chú:"), 0, 0, alignment=Qt.AlignTop)
        self.ed_note = QTextEdit()
        self.ed_note.setPlaceholderText("Nhập ghi chú (tuỳ chọn)")
        self.ed_note.setFixedHeight(70)
        row3.addWidget(self.ed_note, 0, 1, 1, 3)

        # --- Nút hành động ---
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_assign = QPushButton("📤 Giao bài tập")
        self.btn_assign.clicked.connect(self._assign_exercise)
        btn_row.addWidget(self.btn_assign)
        root.addLayout(btn_row)

    # ------------------------- Data loading -------------------------
    def _load_groups(self):
        """Nạp danh sách nhóm -> combobox"""
        self.cb_group.blockSignals(True)
        self.cb_group.clear()
        self.group_map.clear()

        rows = self.db.execute_query(
            "SELECT id, name FROM groups ORDER BY name", fetch="all"
        ) or []
        for gid, name in rows:
            self.group_map[name] = gid
            self.cb_group.addItem(name)

        self.cb_group.blockSignals(False)
        if self.cb_group.count() > 0:
            self.cb_group.setCurrentIndex(0)
            self._on_group_changed()  # tải học sinh nhóm đầu tiên

    def _load_exercises(self):
        """Nạp danh sách bài tập -> combobox: '[chủ đề] tên bài'"""
        self.cb_exercise.clear()
        self.exercise_map.clear()

        rows = self.db.execute_query(
            "SELECT id, chu_de, ten_bai FROM exercises ORDER BY chu_de", fetch="all"
        ) or []
        for eid, chu_de, ten_bai in rows:
            label = f"[{chu_de}] {ten_bai}"
            self.exercise_map[label] = eid
            self.cb_exercise.addItem(label)

    def _on_group_changed(self):
        """Khi chọn nhóm -> nạp học sinh sang danh sách checkbox."""
        # clear cũ
        for i in reversed(range(self.scroll_inner_layout.count() - 1)):  # chừa stretch
            w = self.scroll_inner_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        self.student_checks.clear()

        name = self.cb_group.currentText()
        if not name:
            return

        gid = self.group_map.get(name)
        if not gid:
            return

        rows = self.db.execute_query(
            "SELECT id, name FROM students WHERE group_id = ?",
            (gid,), fetch="all"
        ) or []

        if not rows:
            lbl = QLabel("Nhóm này chưa có học sinh.")
            lbl.setStyleSheet("color:gray;")
            self.scroll_inner_layout.insertWidget(0, lbl)
            return

        for sid, sname in rows:
            cb = QCheckBox(sname)
            cb.setChecked(True)  # mặc định tick hết
            self.student_checks[sid] = cb
            self.scroll_inner_layout.insertWidget(self.scroll_inner_layout.count() - 1, cb)

    # ------------------------- Action -------------------------
    def _assign_exercise(self):
        """Ghi giao bài cho các học sinh đã tick."""
        # danh sách học sinh
        selected_ids = [sid for sid, cb in self.student_checks.items() if cb.isChecked()]
        if not selected_ids:
            QMessageBox.warning(self, "Thiếu thông tin", "Bạn chưa chọn học sinh nào.")
            return

        # bài tập
        label = self.cb_exercise.currentText().strip()
        eid = self.exercise_map.get(label)
        if not eid:
            QMessageBox.warning(self, "Thiếu bài tập", "Vui lòng chọn bài tập.")
            return

        # ngày + ghi chú
        ngay = self.date_assign.date().toString("yyyy-MM-dd")
        ghi_chu = self.ed_note.toPlainText().strip()

        # chèn DB
        count = 0
        try:
            for sid in selected_ids:
                self.db.execute_query(
                    """
                    INSERT INTO assigned_exercises
                        (student_id, exercise_id, ngay_giao, trang_thai, ghi_chu)
                    VALUES (?, ?, ?, 'Chưa làm', ?)
                    """,
                    (sid, eid, ngay, ghi_chu),
                )
                count += 1
        except Exception as e:
            QMessageBox.critical(self, "Lỗi CSDL", f"Không thể giao bài:\n{e}")
            return

        QMessageBox.information(self, "Thành công", f"Đã giao bài cho {count} học sinh.")
        self.accept()  # đóng dialog

# ---- Helper để mở nhanh dưới dạng modal từ MainWindow (tuỳ chọn) ----
def open_assign_exercise_dialog(db_manager, parent: QWidget | None = None):
    dlg = AssignExerciseWindowQt(db_manager, parent=parent)
    dlg.exec()
