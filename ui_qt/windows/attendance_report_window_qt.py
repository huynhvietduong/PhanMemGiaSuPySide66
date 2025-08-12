from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit, QCheckBox, QPushButton,
    QTableView, QHeaderView, QMenu, QMessageBox
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QDate, QPoint
from datetime import datetime, timedelta

# Nếu bạn đã chuyển ScheduleMakeUpWindow sang PySide6, import ở đây:
try:
    from ui_qt.windows.schedule_makeup_window_qt import ScheduleMakeUpWindowQt
except Exception:
    ScheduleMakeUpWindowQt = None


class AttendanceTableModel(QAbstractTableModel):
    HEADERS = ["Ngày", "Học sinh", "Nhóm", "Lý do", "Dạy bù"]

    def __init__(self, rows=None):
        super().__init__()
        self._rows = rows or []   # mỗi row: dict như item của db.get_attendance_report

    def rowCount(self, parent=QModelIndex()):
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        return self.HEADERS[section] if orientation == Qt.Horizontal else section + 1

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        r = self._rows[index.row()]
        if role in (Qt.DisplayRole, Qt.EditRole):
            mapping = [
                r.get("session_date", ""),
                r.get("student_name", ""),
                r.get("group_name", ""),
                r.get("status", ""),
                r.get("detailed_status", ""),
            ]
            return mapping[index.column()]
        return None

    def id_at(self, row: int):
        if 0 <= row < len(self._rows):
            return self._rows[row].get("id")
        return None

    def row_at(self, row: int):
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def set_rows(self, rows):
        self.beginResetModel()
        self._rows = rows or []
        self.endResetModel()


class AttendanceReportWindowQt(QWidget):
    """
    Báo cáo Chuyên cần & sắp xếp học bù (PySide6).
    Chuyển đổi từ Tkinter: start/end date, ẩn buổi đã dạy bù, bảng kết quả, menu chuột phải.
    """
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setWindowTitle("Báo cáo Chuyên cần")
        self._build_ui()
        self.load_report()

    # -------------------- UI --------------------
    def _build_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Báo cáo Chuyên cần")
        title.setStyleSheet("font-size:16px; font-weight:600;")
        root.addWidget(title)

        # Bộ lọc
        filter_bar = QHBoxLayout()
        filter_bar.addWidget(QLabel("Từ ngày:"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.setDate(QDate.currentDate().addDays(-7))

        filter_bar.addWidget(self.start_date)

        filter_bar.addWidget(QLabel("Đến ngày:"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date.setDate(QDate.currentDate())
        filter_bar.addWidget(self.end_date)

        self.cb_hide_completed = QCheckBox("Ẩn các buổi đã dạy bù")
        self.cb_hide_completed.setChecked(True)
        self.cb_hide_completed.stateChanged.connect(self.load_report)
        filter_bar.addWidget(self.cb_hide_completed)

        btn_view = QPushButton("Xem báo cáo")
        btn_view.clicked.connect(self.load_report)
        filter_bar.addWidget(btn_view)

        filter_bar.addStretch(1)
        root.addLayout(filter_bar)

        # Bảng kết quả
        self.table = QTableView()
        self.model = AttendanceTableModel([])
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.ExtendedSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        root.addWidget(self.table, 1)

    # -------------------- Data --------------------
    def load_report(self):
        start = self.start_date.date().toString("yyyy-MM-dd")
        end = self.end_date.date().toString("yyyy-MM-dd")
        hide_completed = self.cb_hide_completed.isChecked()

        report_items = self.db.get_attendance_report(start, end, hide_completed) or []
        # Kỳ vọng mỗi item: id, session_date, student_name, student_id, group_name, group_grade, status, detailed_status
        self.model.set_rows(report_items)
        if report_items:
            self.table.selectRow(0)

    # -------------------- Context menu --------------------
    def show_context_menu(self, pos: QPoint):
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        menu = QMenu(self)
        act = menu.addAction("🗓️ Sắp xếp lịch bù...")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == act:
            self.open_schedule_makeup_window()

    def open_schedule_makeup_window(self):
        # Lấy các dòng được chọn
        sel_indexes = self.table.selectionModel().selectedRows()
        if not sel_indexes:
            QMessageBox.warning(self, "Chưa chọn", "Vui lòng chọn ít nhất một học sinh để sắp xếp lịch.")
            return

        # Dựng danh sách attendance_info_list theo format của bản gốc
        attendance_info_list = []
        for idx in sel_indexes:
            row_data = self.model.row_at(idx.row())
            if not row_data:
                continue
            attendance_info_list.append({
                "id": row_data.get("id"),
                "session_date": row_data.get("session_date"),
                "student_name": row_data.get("student_name"),
                "student_id": row_data.get("student_id"),
                "group_grade": row_data.get("group_grade"),
            })

        if not attendance_info_list:
            QMessageBox.warning(self, "Chưa chọn", "Không có dữ liệu hợp lệ để sắp xếp lịch.")
            return

        # Kiểm tra cùng khối lớp
        first_grade = attendance_info_list[0]["group_grade"]
        if any(info["group_grade"] != first_grade for info in attendance_info_list):
            QMessageBox.critical(self, "Lỗi", "Vui lòng chỉ chọn các học sinh có cùng khối lớp để sắp xếp lịch chung.")
            return

        if ScheduleMakeUpWindowQt is None:
            QMessageBox.information(
                self, "Chưa sẵn sàng",
                "Màn hình 'Sắp xếp lịch bù' (ScheduleMakeUpWindowQt) chưa được chuyển sang PySide6."
            )
            return

        # Mở cửa sổ sắp xếp học bù
        dlg = ScheduleMakeUpWindowQt(self.db, attendance_info_list, parent=self)
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.show()  # hoặc dlg.exec() nếu là QDialog blocking
