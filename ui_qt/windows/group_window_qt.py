# ui_qt/windows/group_window_qt.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableView, QHeaderView, QGroupBox, QCheckBox, QMessageBox, QScrollArea
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from constants import DAYS_OF_WEEK_VN, FIXED_TIME_SLOTS

class GroupsTableModel(QAbstractTableModel):
    HEADERS = ["ID", "Tên nhóm", "Khối lớp", "Sĩ số", "Lịch học"]

    def __init__(self, rows=None):
        super().__init__()
        self._rows = rows or []

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
        if role in (Qt.DisplayRole, Qt.EditRole):
            r = self._rows[index.row()]
            return [r["id"], r["name"], r["grade"], r["student_count"], r["schedule_str"]][index.column()]
        return None

    def group_id_at(self, row):
        if 0 <= row < len(self._rows):
            return self._rows[row]["id"]
        return None

    def set_rows(self, rows):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()


class GroupWindowQt(QWidget):
    def __init__(self, db_manager, parent_app=None, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.parent_app = parent_app
        self.setWindowTitle("Quản lý Nhóm học")
        self.schedule_vars = {}
        self._build_ui()
        self.load_groups()
        self.clear_form()

    def _build_ui(self):
        root = QHBoxLayout(self)

        # Left panel: Table
        left = QVBoxLayout()
        lb = QLabel("Danh sách các nhóm học")
        lb.setStyleSheet("font-size:16px; font-weight:600;")
        left.addWidget(lb)

        self.table = QTableView()
        self.model = GroupsTableModel([])
        self.table.setModel(self.model)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.clicked.connect(self.on_group_select)
        left.addWidget(self.table, 1)

        # Right panel: Form
        right = QVBoxLayout()

        # Tên nhóm
        lbl = QLabel("Tên nhóm (ví dụ: 9.1, 10.2):")
        self.ed_name = QLineEdit()
        right.addWidget(lbl)
        right.addWidget(self.ed_name)

        # Khối lớp
        lbl2 = QLabel("Khối lớp:")
        self.ed_grade = QLineEdit()
        right.addWidget(lbl2)
        right.addWidget(self.ed_grade)

        # Lịch học
        right.addWidget(QLabel("Lịch học:"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        schedule_widget = QWidget()
        schedule_layout = QVBoxLayout(schedule_widget)

        for day in DAYS_OF_WEEK_VN:
            gb = QGroupBox(day)
            hbox = QHBoxLayout(gb)
            self.schedule_vars[day] = {}
            for slot in FIXED_TIME_SLOTS:
                cb = QCheckBox(slot)
                hbox.addWidget(cb)
                self.schedule_vars[day][slot] = cb
            schedule_layout.addWidget(gb)

        schedule_layout.addStretch(1)
        scroll.setWidget(schedule_widget)
        right.addWidget(scroll, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("Thêm mới")
        btn_update = QPushButton("Cập nhật")
        btn_delete = QPushButton("Xóa")
        btn_clear = QPushButton("Làm mới form")
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_update)
        btn_layout.addWidget(btn_delete)
        btn_layout.addWidget(btn_clear)
        right.addLayout(btn_layout)

        btn_add.clicked.connect(self.add_group)
        btn_update.clicked.connect(self.update_group)
        btn_delete.clicked.connect(self.delete_group)
        btn_clear.clicked.connect(self.clear_form)

        root.addLayout(left, 2)
        root.addLayout(right, 3)

    # ===== Data Load =====
    def load_groups(self):
        groups = self.db.get_groups_with_details() or []
        self.model.set_rows(groups)
        if groups:
            self.table.selectRow(0)

    def on_group_select(self, index: QModelIndex):
        row = index.row()
        group_id = self.model.group_id_at(row)
        if group_id is None:
            return

        data = self.db.execute_query(
            "SELECT name, grade FROM groups WHERE id = ?",
            (group_id,), fetch='one'
        )
        if not data:
            return
        name, grade = data
        self.ed_name.setText(name)
        self.ed_grade.setText(grade)

        # reset checkboxes
        for slots in self.schedule_vars.values():
            for cb in slots.values():
                cb.setChecked(False)

        for day, slot in self.db.execute_query(
            "SELECT day_of_week, time_slot FROM schedule WHERE group_id = ?",
            (group_id,), fetch='all'
        ) or []:
            if day in self.schedule_vars and slot in self.schedule_vars[day]:
                self.schedule_vars[day][slot].setChecked(True)

    # ===== Actions =====
    def add_group(self):
        name = self.ed_name.text().strip()
        grade = self.ed_grade.text().strip()
        if not name or not grade:
            QMessageBox.critical(self, "Lỗi", "Tên nhóm và Khối lớp không được để trống.")
            return
        g_id = self.db.execute_query(
            "INSERT INTO groups (name, grade) VALUES (?, ?)",
            (name, grade)
        )
        if g_id:
            self._save_schedule(g_id)
            QMessageBox.information(self, "Thành công", "Đã thêm nhóm mới.")
            self.load_groups()
            self.clear_form()
            if self.parent_app:
                self.parent_app.update_all_schedules()
        else:
            QMessageBox.critical(self, "Lỗi", "Tên nhóm có thể đã tồn tại.")

    def update_group(self):
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            QMessageBox.critical(self, "Lỗi", "Vui lòng chọn nhóm.")
            return
        group_id = self.model.group_id_at(sel[0].row())
        name = self.ed_name.text().strip()
        grade = self.ed_grade.text().strip()
        self.db.execute_query(
            "UPDATE groups SET name = ?, grade = ? WHERE id = ?",
            (name, grade, group_id)
        )
        self.db.execute_query("DELETE FROM schedule WHERE group_id = ?", (group_id,))
        self._save_schedule(group_id)
        QMessageBox.information(self, "Thành công", "Đã cập nhật thông tin nhóm.")
        self.load_groups()
        self.clear_form()
        if self.parent_app:
            self.parent_app.update_all_schedules()

    def delete_group(self):
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            QMessageBox.critical(self, "Lỗi", "Vui lòng chọn nhóm.")
            return
        group_id = self.model.group_id_at(sel[0].row())
        if QMessageBox.question(self, "Xác nhận", "Bạn có chắc chắn muốn xóa nhóm này?") != QMessageBox.Yes:
            return
        if self.db.execute_query(
            "SELECT id FROM students WHERE group_id = ?",
            (group_id,), fetch='all'
        ):
            QMessageBox.critical(self, "Lỗi", "Không thể xóa nhóm vì vẫn còn học sinh.")
            return
        self.db.execute_query("DELETE FROM groups WHERE id = ?", (group_id,))
        QMessageBox.information(self, "Thành công", "Đã xóa nhóm.")
        self.load_groups()
        self.clear_form()
        if self.parent_app:
            self.parent_app.update_all_schedules()

    def _save_schedule(self, group_id):
        for day, slots in self.schedule_vars.items():
            for slot, cb in slots.items():
                if cb.isChecked():
                    self.db.execute_query(
                        "INSERT INTO schedule (group_id, day_of_week, time_slot) VALUES (?, ?, ?)",
                        (group_id, day, slot)
                    )

    def clear_form(self):
        self.ed_name.clear()
        self.ed_grade.clear()
        for slots in self.schedule_vars.values():
            for cb in slots.values():
                cb.setChecked(False)
        self.table.clearSelection()
