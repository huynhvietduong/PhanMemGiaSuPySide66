# ui_qt/windows/student_window_qt.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QRadioButton, QPushButton, QGroupBox, QMessageBox, QTableView, QHeaderView
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from datetime import datetime


# ---- Table model thay cho ttk.Treeview ----
class StudentsTableModel(QAbstractTableModel):
    HEADERS = ["ID", "Họ tên", "Lớp", "Nhóm"]

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
        if orientation == Qt.Horizontal:
            return self.HEADERS[section]
        return section + 1

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.DisplayRole, Qt.EditRole):
            r = self._rows[index.row()]
            group_name = r["group_name"] if "group_name" in r.keys() else None
            return [r["id"], r["name"], r["grade"], group_name or "Kèm riêng"][index.column()]
        return None

    def student_id_at(self, row: int):
        if 0 <= row < len(self._rows):
            return self._rows[row]["id"]
        return None

    def set_rows(self, rows):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()


class StudentWindowQt(QWidget):
    """
    Quản lý Học sinh (PySide6) — chuyển đổi từ Tkinter Toplevel.
    Bản này để nhúng vào MainWindow (setCentralWidget / stacked page).
    """
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setWindowTitle("Quản lý Học sinh")
        self.package_map = {}     # name -> id
        self._build_ui()
        self._load_lookups()
        self.load_students()
        self.clear_form()

    # ---------- UI ----------
    def _build_ui(self):
        root = QHBoxLayout(self)
        # Left: table
        left = QVBoxLayout()
        title = QLabel("Danh sách học sinh")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title.setStyleSheet("font-size:16px; font-weight:600;")
        left.addWidget(title)

        self.table = QTableView()
        self.model = StudentsTableModel([])
        self.table.setModel(self.model)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.clicked.connect(self.on_student_select)
        left.addWidget(self.table, 1)

        # Right: form
        right = QVBoxLayout()
        right_title = QLabel("Hồ sơ học sinh")
        right_title.setStyleSheet("font-size:16px; font-weight:600;")
        right.addWidget(right_title)

        # Thông tin cá nhân
        gb_info = QGroupBox("Thông tin cá nhân")
        ly_info = QVBoxLayout(gb_info)

        self.ed_name = self._labeled_line(ly_info, "Họ tên:")
        self.ed_grade = self._labeled_line(ly_info, "Khối lớp:")
        self.ed_phone = self._labeled_line(ly_info, "SĐT:")

        right.addWidget(gb_info)

        # Thông tin học tập
        gb_study = QGroupBox("Thông tin học tập")
        ly_study = QVBoxLayout(gb_study)

        row_status = QHBoxLayout()
        row_status.addWidget(QLabel("Trạng thái học:"))
        self.rb_private = QRadioButton("Kèm riêng")
        self.rb_group = QRadioButton("Học nhóm")
        self.rb_private.setChecked(True)
        self.rb_private.toggled.connect(self.toggle_group_select)
        self.rb_group.toggled.connect(self.toggle_group_select)
        row_status.addWidget(self.rb_private)
        row_status.addWidget(self.rb_group)
        row_status.addStretch(1)
        ly_study.addLayout(row_status)

        row_group = QHBoxLayout()
        self.lb_group = QLabel("Chọn nhóm:")
        self.cb_group = QComboBox()
        row_group.addWidget(self.lb_group)
        row_group.addWidget(self.cb_group, 1)
        ly_study.addLayout(row_group)

        right.addWidget(gb_study)

        # Thông tin học phí
        gb_fee = QGroupBox("Thông tin học phí")
        ly_fee = QVBoxLayout(gb_fee)

        row_pkg = QHBoxLayout()
        row_pkg.addWidget(QLabel("Gói học:"))
        self.cb_package = QComboBox()
        row_pkg.addWidget(self.cb_package, 1)
        ly_fee.addLayout(row_pkg)

        row_date = QHBoxLayout()
        row_date.addWidget(QLabel("Ngày BĐ chu kỳ:"))
        self.ed_cycle_date = QLineEdit()
        self.ed_cycle_date.setPlaceholderText("DD-MM-YYYY")
        row_date.addWidget(self.ed_cycle_date, 1)
        ly_fee.addLayout(row_date)

        right.addWidget(gb_fee)

        # Buttons
        row_btn = QHBoxLayout()
        row_btn.addStretch(1)
        self.btn_add = QPushButton("Thêm mới")
        self.btn_update = QPushButton("Cập nhật")
        self.btn_delete = QPushButton("Xóa")
        self.btn_clear = QPushButton("Làm mới")
        for b in (self.btn_add, self.btn_update, self.btn_delete, self.btn_clear):
            row_btn.addWidget(b)
        right.addLayout(row_btn)

        # Wire actions
        self.btn_add.clicked.connect(self.add_student)
        self.btn_update.clicked.connect(self.update_student)
        self.btn_delete.clicked.connect(self.delete_student)
        self.btn_clear.clicked.connect(self.clear_form)

        # Layout to root
        root.addLayout(left, 2)
        root.addLayout(right, 3)

    def _labeled_line(self, parent_layout: QVBoxLayout, label: str) -> QLineEdit:
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        edit = QLineEdit()
        row.addWidget(edit, 1)
        parent_layout.addLayout(row)
        return edit

    # ---------- Lookups ----------
    def _load_lookups(self):
        # Nhóm
        groups = self.db.execute_query("SELECT name FROM groups ORDER BY name", fetch='all') or []
        self.cb_group.clear()
        self.cb_group.addItems([g[0] for g in groups])

        # Gói học
        packages = self.db.execute_query("SELECT id, name FROM packages ORDER BY name", fetch='all') or []
        self.package_map = {name: id_ for id_, name in packages}
        self.cb_package.clear()
        self.cb_package.addItems(list(self.package_map.keys()))

        self.toggle_group_select()

    # ---------- Load / Select ----------
    def load_students(self):
        students = self.db.get_all_students_for_display() or []
        self.model.set_rows(students)
        if students:
            self.table.selectRow(0)

    def on_student_select(self, index: QModelIndex):
        row = index.row()
        student_id = self.model.student_id_at(row)
        if student_id is None:
            return
        data = self.db.get_student_details_by_id(student_id)
        if not data:
            return

        self.ed_name.setText(data.get("name", "") or "")
        self.ed_grade.setText(data.get("grade", "") or "")
        self.ed_phone.setText(data.get("phone", "") or "")

        status = data.get("status") or "Kèm riêng"
        self.rb_group.setChecked(status == "Học nhóm")
        self.rb_private.setChecked(status != "Học nhóm")

        self.cb_group.setCurrentText(data.get("group_name") or "")
        self.cb_package.setCurrentText(data.get("package_name") or "")

        # Ngày BĐ chu kỳ -> DD-MM-YYYY
        self.ed_cycle_date.clear()
        cycle = data.get("cycle_start_date")
        if cycle:
            try:
                display_date = datetime.strptime(cycle, "%Y-%m-%d").strftime("%d-%m-%Y")
                self.ed_cycle_date.setText(display_date)
            except (ValueError, TypeError):
                # Giữ placeholder nếu lỗi
                pass

        self.toggle_group_select()

    # ---------- Helpers ----------
    def _is_group_mode(self) -> bool:
        return self.rb_group.isChecked()

    def toggle_group_select(self):
        enabled = self._is_group_mode()
        self.lb_group.setEnabled(enabled)
        self.cb_group.setEnabled(enabled)
        if not enabled:
            self.cb_group.setCurrentIndex(-1)

    def get_form_data(self):
        name = self.ed_name.text().strip()
        grade = self.ed_grade.text().strip()
        phone = self.ed_phone.text().strip()
        status = "Học nhóm" if self._is_group_mode() else "Kèm riêng"

        # group_id nếu Học nhóm
        group_id = None
        group_name = self.cb_group.currentText().strip()
        if status == "Học nhóm":
            if not group_name:
                QMessageBox.critical(self, "Lỗi", "Vui lòng chọn nhóm.")
                return None
            res = self.db.execute_query(
                "SELECT id FROM groups WHERE name = ?",
                (group_name,),
                fetch='one'
            )
            if res:
                group_id = res[0]

        # package_id
        package_id = None
        package_name = self.cb_package.currentText().strip()
        if package_name:
            package_id = self.package_map.get(package_name)

        # Ngày BĐ chu kỳ
        cycle_text = self.ed_cycle_date.text().strip()
        cycle_start_date = ""
        if cycle_text and cycle_text != "DD-MM-YYYY":
            try:
                d = datetime.strptime(cycle_text, "%d-%m-%Y")
                cycle_start_date = d.strftime("%Y-%m-%d")
            except ValueError:
                QMessageBox.critical(
                    self, "Lỗi Định Dạng",
                    "Ngày BĐ chu kỳ không hợp lệ. Vui lòng nhập theo định dạng DD-MM-YYYY."
                )
                return None

        return {
            "Họ tên": name,
            "Khối lớp": grade,
            "SĐT": phone,
            "status": status,
            "group_id": group_id,
            "package_id": package_id,
            "cycle_start_date": cycle_start_date
        }

    # ---------- Actions ----------
    def add_student(self):
        form = self.get_form_data()
        if not form:
            return
        if not form["Họ tên"] or not form["Khối lớp"]:
            QMessageBox.critical(self, "Lỗi", "Họ tên và Khối lớp là bắt buộc.")
            return

        form["start_date"] = datetime.now().strftime("%Y-%m-%d")
        self.db.add_student(form)
        QMessageBox.information(self, "Thành công", f"Đã thêm học sinh {form['Họ tên']}.")
        self.load_students()
        self.clear_form()

    def update_student(self):
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            QMessageBox.critical(self, "Lỗi", "Vui lòng chọn học sinh.")
            return
        student_id = self.model.student_id_at(sel[0].row())

        form = self.get_form_data()
        if not form:
            return

        self.db.update_student(student_id, form)
        QMessageBox.information(self, "Thành công", f"Đã cập nhật thông tin học sinh {form['Họ tên']}.")
        self.load_students()
        self.clear_form()

    def delete_student(self):
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            QMessageBox.critical(self, "Lỗi", "Vui lòng chọn học sinh.")
            return
        row = sel[0].row()
        student_id = self.model.student_id_at(row)

        if QMessageBox.question(self, "Xác nhận", "Bạn có chắc chắn muốn xóa học sinh này?") != QMessageBox.Yes:
            return

        self.db.delete_student_by_id(student_id)
        QMessageBox.information(self, "Thành công", "Đã xóa học sinh.")
        self.load_students()
        self.clear_form()

    def clear_form(self):
        self.ed_name.clear()
        self.ed_grade.clear()
        self.ed_phone.clear()
        self.cb_package.setCurrentIndex(-1)
        self.ed_cycle_date.clear()
        self.ed_cycle_date.setPlaceholderText("DD-MM-YYYY")
        self.rb_private.setChecked(True)
        self.toggle_group_select()
        self.table.clearSelection()
