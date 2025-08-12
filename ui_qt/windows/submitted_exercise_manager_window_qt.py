# ui_qt/windows/submitted_exercise_manager_window_qt.py
from PySide6.QtCore import Qt, QUrl, QDate
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QDateEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,QAbstractItemView
)
from PySide6.QtWidgets import QAbstractItemView
from PySide6.QtWidgets import QHeaderView, QAbstractItemView

class SubmittedExerciseManagerWindowQt(QWidget):
    """
    📂 Danh sách bài đã nộp — PySide6
    - Bộ lọc: Học sinh, Chủ đề, Từ ngày, Đến ngày
    - Bảng: HS | Chủ đề | Tên bài | Ngày nộp | Điểm | Nhận xét | (ẩn) File
    - Double click vào một dòng để mở file nộp
    """
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self._student_map = {}
        self._build_ui()
        self._load_students()
        self.load_data()

    # ---------------- UI ----------------
    def _build_ui(self):
        root = QVBoxLayout(self)

        # --- Filter bar ---
        filter_bar = QHBoxLayout()
        root.addLayout(filter_bar)

        # Học sinh
        filter_bar.addWidget(QLabel("Học sinh:"))
        self.cb_student = QComboBox()
        self.cb_student.setEditable(False)
        self.cb_student.setMinimumWidth(240)
        filter_bar.addWidget(self.cb_student)

        # Chủ đề
        filter_bar.addWidget(QLabel("Chủ đề:"))
        self.ed_topic = QLineEdit()
        self.ed_topic.setPlaceholderText("Nhập từ khoá chủ đề...")
        self.ed_topic.setMinimumWidth(180)
        filter_bar.addWidget(self.ed_topic)

        # Từ ngày / Đến ngày
        filter_bar.addWidget(QLabel("Từ ngày:"))
        self.dt_from = QDateEdit()
        self.dt_from.setCalendarPopup(True)
        self.dt_from.setDisplayFormat("yyyy-MM-dd")
        self.dt_from.setDate(QDate(2000, 1, 1))  # mốc xa để mặc định “không lọc”
        filter_bar.addWidget(self.dt_from)

        filter_bar.addWidget(QLabel("Đến:"))
        self.dt_to = QDateEdit()
        self.dt_to.setCalendarPopup(True)
        self.dt_to.setDisplayFormat("yyyy-MM-dd")
        self.dt_to.setDate(QDate.currentDate())
        filter_bar.addWidget(self.dt_to)

        # Nút lọc
        btn_filter = QPushButton("🔍 Lọc")
        btn_filter.clicked.connect(self.load_data)
        filter_bar.addWidget(btn_filter)
        filter_bar.addStretch(1)

        # --- Table ---
        self.table = QTableWidget(0, 7, self)
        self.table.setHorizontalHeaderLabels(
            ["HS", "Chủ đề", "Tên bài", "Ngày nộp", "Điểm", "Nhận xét", "File"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # HS
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Ngày
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Điểm
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._open_selected_file)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemDoubleClicked.connect(self.on_open_file)

        root.addWidget(self.table)

    def _load_students(self):
        # SELECT id, name FROM students ORDER BY name
        rows = self.db.execute_query(
            "SELECT id, name FROM students ORDER BY name",
            fetch='all'
        ) or []
        self._student_map.clear()
        self.cb_student.clear()
        self.cb_student.addItem("")  # trống = không lọc
        for sid, name in rows:
            label = f"{name} (ID {sid})"
            self._student_map[label] = sid
            self.cb_student.addItem(label)

    # -------------- Data loading --------------
    def load_data(self):
        self.table.setRowCount(0)

        query = """
            SELECT s.name, e.chu_de, e.ten_bai, sub.ngay_nop, sub.diem, sub.nhan_xet, sub.file_path
            FROM exercise_submissions sub
            JOIN assigned_exercises ae ON sub.assignment_id = ae.id
            JOIN exercises e ON ae.exercise_id = e.id
            JOIN students s ON sub.student_id = s.id
            WHERE 1=1
        """
        params = []

        # Học sinh
        stu_label = self.cb_student.currentText().strip()
        if stu_label:
            sid = self._student_map.get(stu_label)
            if sid:
                query += " AND sub.student_id = ?"
                params.append(sid)

        # Chủ đề
        topic = self.ed_topic.text().strip()
        if topic:
            query += " AND e.chu_de LIKE ?"
            params.append(f"%{topic}%")

        # Khoảng ngày
        from_str = self.dt_from.date().toString("yyyy-MM-dd")
        to_str = self.dt_to.date().toString("yyyy-MM-dd")
        if from_str:
            query += " AND sub.ngay_nop >= ?"
            params.append(from_str)
        if to_str:
            query += " AND sub.ngay_nop <= ?"
            params.append(to_str)

        query += " ORDER BY sub.ngay_nop DESC"

        rows = self.db.execute_query(query, tuple(params), fetch='all') or []

        for r in rows:
            self._append_row(r)

    def _append_row(self, row_tuple):
        # (name, chu_de, ten_bai, ngay_nop, diem, nhan_xet, file_path)
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c, val in enumerate(row_tuple):
            item = QTableWidgetItem("" if val is None else str(val))
            if c in (3, 4):  # Ngày nộp, Điểm
                item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, c, item)

        # Ẩn cột file để bảng gọn (vẫn giữ để double‑click lấy đường dẫn)
        self.table.setColumnHidden(6, True)

    # -------------- Actions --------------
    def _open_selected_file(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            return
        path_item = self.table.item(idx.row(), 6)  # cột "File"
        file_path = path_item.text() if path_item else ""
        if not file_path:
            QMessageBox.warning(self, "Không tìm thấy", "Dòng này không có đường dẫn tệp.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))

    def on_open_file(self, item: QTableWidgetItem):
        """Mở file khi double-click dòng hoặc riêng cột 'Xem'."""
        try:
            # Nếu double-click cột khác, vẫn lấy path từ cột 6
            if item.column() == 6:
                path_item = item
            else:
                path_item = self.table.item(item.row(), 6)

            if path_item is None:
                QMessageBox.warning(self, "Thiếu dữ liệu", "Không tìm thấy thông tin file để mở.")
                return

            file_path = path_item.data(Qt.UserRole)
            if not file_path:
                QMessageBox.warning(self, "Thiếu dữ liệu", "Không có đường dẫn file kèm theo.")
                return

            # mở bằng app mặc định của hệ điều hành
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(file_path)):
                QMessageBox.warning(self, "Không mở được", f"Không thể mở file:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Đã xảy ra lỗi khi mở file:\n{e}")
