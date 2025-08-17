# ui_qt/windows/student_window_qt.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QRadioButton, QPushButton, QGroupBox, QMessageBox, QTableView, QHeaderView
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from datetime import datetime
# Import thư viện xử lý Excel
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from PySide6.QtWidgets import QFileDialog
# Import thêm các widget cần thiết
from PySide6.QtWidgets import (
    QTabWidget, QFormLayout, QTextEdit, QGroupBox,
    QGridLayout  # Thêm vào import hiện có
)
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

        # Thêm widget tìm kiếm vào layout trái
        search_widget = self._build_search_widget()
        left.addWidget(search_widget)

        # Thêm widget thống kê vào layout trái
        stats_widget = self._build_stats_widget()
        left.addWidget(stats_widget)

        # Bảng danh sách học sinh
        self.table = QTableView()
        self.model = StudentsTableModel([])
        self.table.setModel(self.model)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.clicked.connect(self.on_student_select)
        left.addWidget(self.table, 1)

        # Right: form với tabs
        right = QVBoxLayout()
        right_title = QLabel("Hồ sơ học sinh")
        right_title.setStyleSheet("font-size:16px; font-weight:600;")
        right.addWidget(right_title)

        # Tạo Tab Widget để chia nhóm thông tin
        self.student_tabs = QTabWidget()

        # Tab 1: Thông tin cơ bản
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)

        # Thông tin cá nhân
        gb_info = QGroupBox("Thông tin cá nhân")
        ly_info = QVBoxLayout(gb_info)
        self.ed_name = self._labeled_line(ly_info, "Họ tên:")
        self.ed_grade = self._labeled_line(ly_info, "Khối lớp:")
        self.ed_phone = self._labeled_line(ly_info, "SĐT:")
        basic_layout.addWidget(gb_info)

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
        basic_layout.addWidget(gb_study)

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
        basic_layout.addWidget(gb_fee)

        # Thêm tab cơ bản vào tab widget
        self.student_tabs.addTab(basic_tab, "📝 Cơ bản")

        # Tab 2: Thông tin phụ huynh
        parent_tab = self._build_parent_info_widget()
        self.student_tabs.addTab(parent_tab, "👨‍👩‍👧‍👦 Phụ huynh")

        # Thêm tab widget vào layout phải
        right.addWidget(self.student_tabs)

        # Buttons chính
        row_btn = QHBoxLayout()
        row_btn.addStretch(1)
        self.btn_add = QPushButton("Thêm mới")
        self.btn_update = QPushButton("Cập nhật")
        self.btn_delete = QPushButton("Xóa")
        self.btn_clear = QPushButton("Làm mới")
        for b in (self.btn_add, self.btn_update, self.btn_delete, self.btn_clear):
            row_btn.addWidget(b)
        right.addLayout(row_btn)

        # Thêm nút Excel vào toolbar
        excel_row = QHBoxLayout()
        excel_row.addStretch(1)
        btn_export = QPushButton("📤 Xuất Excel")
        btn_export.clicked.connect(self.export_to_excel)
        btn_import = QPushButton("📥 Nhập Excel")
        btn_import.clicked.connect(self.import_from_excel)
        excel_row.addWidget(btn_export)
        excel_row.addWidget(btn_import)
        right.addLayout(excel_row)

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
        # Cập nhật thống kê sau khi load dữ liệu
        self._update_student_stats()
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

    # Widget tìm kiếm và lọc nâng cao
    def _build_search_widget(self) -> QWidget:
        """Tạo widget tìm kiếm và lọc học sinh"""
        search_widget = QWidget()
        layout = QVBoxLayout(search_widget)

        # Tiêu đề
        search_title = QLabel("🔍 Tìm kiếm & Lọc")
        search_title.setStyleSheet("font-weight: 600; margin-bottom: 8px;")
        layout.addWidget(search_title)

        # Hàng 1: Tìm kiếm theo tên
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Tên:"))
        self.search_name = QLineEdit()
        self.search_name.setPlaceholderText("Nhập tên học sinh...")
        self.search_name.textChanged.connect(self._filter_students)
        row1.addWidget(self.search_name, 1)
        layout.addLayout(row1)

        # Hàng 2: Lọc theo lớp và trạng thái
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Lớp:"))
        self.filter_grade = QComboBox()
        self.filter_grade.addItems(["Tất cả", "6", "7", "8", "9", "10", "11", "12"])
        self.filter_grade.currentTextChanged.connect(self._filter_students)
        row2.addWidget(self.filter_grade)

        row2.addWidget(QLabel("Trạng thái:"))
        self.filter_status = QComboBox()
        self.filter_status.addItems(["Tất cả", "Học nhóm", "Kèm riêng"])
        self.filter_status.currentTextChanged.connect(self._filter_students)
        row2.addWidget(self.filter_status)
        layout.addLayout(row2)

        return search_widget

    # Phương thức lọc học sinh theo tiêu chí
    # Phương thức lọc học sinh theo tiêu chí - ĐÃ SỬA LỖI
    def _filter_students(self):
        """Lọc danh sách học sinh theo các tiêu chí tìm kiếm"""
        name_filter = self.search_name.text().strip().lower()
        grade_filter = self.filter_grade.currentText()
        status_filter = self.filter_status.currentText()

        # Lọc dữ liệu từ model - SỬA CHÍNH TẠI ĐÂY
        for row in range(self.model.rowCount()):
            # Sử dụng model.data() thay vì model.item()
            item_name = self.model.data(self.model.index(row, 1), Qt.DisplayRole) or ""
            item_grade = self.model.data(self.model.index(row, 2), Qt.DisplayRole) or ""
            item_group = self.model.data(self.model.index(row, 3), Qt.DisplayRole) or ""

            # Chuyển tên thành chữ thường để so sánh
            item_name = item_name.lower()

            # Xác định trạng thái từ thông tin nhóm
            if item_group and item_group != "Kèm riêng" and item_group.strip():
                item_status = "Học nhóm"
            else:
                item_status = "Kèm riêng"

            # Kiểm tra điều kiện lọc
            name_match = name_filter in item_name if name_filter else True
            grade_match = grade_filter == "Tất cả" or grade_filter == str(item_grade)
            status_match = status_filter == "Tất cả" or status_filter == item_status

            # Hiển thị/ẩn hàng
            self.table.setRowHidden(row, not (name_match and grade_match and status_match))
    # Xuất danh sách học sinh ra Excel
    def export_to_excel(self):
        """Xuất danh sách học sinh ra file Excel"""
        try:
            if not PANDAS_AVAILABLE:
                QMessageBox.warning(self, "Thiếu thư viện",
                                    "Cần cài đặt pandas để xuất Excel:\npip install pandas openpyxl")
                return

            # Chọn vị trí lưu file
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Xuất danh sách học sinh",
                f"DanhSachHocSinh_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                "Excel Files (*.xlsx)"
            )

            if not file_path:
                return

            # Lấy dữ liệu từ database
            students = self.db.get_all_students_for_display() or []

            # Chuyển đổi thành DataFrame
            df_data = []
            for student in students:
                df_data.append({
                    'ID': student.get('id', ''),
                    'Họ tên': student.get('name', ''),
                    'Lớp': student.get('grade', ''),
                    'SĐT': student.get('phone', ''),
                    'Nhóm': student.get('group_name', ''),
                    'Trạng thái': student.get('status', ''),
                    'Gói học': student.get('package_name', ''),
                    'Ngày bắt đầu': student.get('cycle_start_date', '')
                })

            df = pd.DataFrame(df_data)
            df.to_excel(file_path, index=False, sheet_name='Danh sách học sinh')

            QMessageBox.information(self, "Thành công", f"Đã xuất {len(df_data)} học sinh ra:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Lỗi xuất Excel", f"Không thể xuất file Excel:\n{str(e)}")

    # Nhập danh sách học sinh từ Excel
    def import_from_excel(self):
        """Nhập danh sách học sinh từ file Excel"""
        try:
            if not PANDAS_AVAILABLE:
                QMessageBox.warning(self, "Thiếu thư viện",
                                    "Cần cài đặt pandas để nhập Excel:\npip install pandas openpyxl")
                return

            # Chọn file Excel
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Nhập danh sách học sinh",
                "", "Excel Files (*.xlsx *.xls)"
            )

            if not file_path:
                return

            # Đọc file Excel
            df = pd.read_excel(file_path)

            # Validation cột bắt buộc
            required_columns = ['Họ tên', 'Lớp', 'SĐT']
            missing_columns = [col for col in required_columns if col not in df.columns]

            if missing_columns:
                QMessageBox.critical(self, "Lỗi định dạng",
                                     f"File Excel thiếu các cột: {', '.join(missing_columns)}")
                return

            # Xử lý từng dòng
            success_count = 0
            error_list = []

            for index, row in df.iterrows():
                try:
                    # Chuẩn bị dữ liệu
                    student_data = {
                        'Họ tên': str(row.get('Họ tên', '')).strip(),
                        'Khối lớp': str(row.get('Lớp', '')).strip(),
                        'SĐT': str(row.get('SĐT', '')).strip(),
                        'start_date': datetime.now().strftime('%Y-%m-%d'),
                        'status': str(row.get('Trạng thái', 'Kèm riêng')).strip(),
                        'group_id': None,  # Sẽ xử lý sau
                        'package_id': None,  # Sẽ xử lý sau
                        'cycle_start_date': ''
                    }

                    # Validation dữ liệu
                    if not student_data['Họ tên']:
                        error_list.append(f"Dòng {index + 2}: Thiếu họ tên")
                        continue

                    # Thêm vào database
                    self.db.add_student(student_data)
                    success_count += 1

                except Exception as e:
                    error_list.append(f"Dòng {index + 2}: {str(e)}")

            # Thông báo kết quả
            message = f"Đã nhập thành công {success_count} học sinh."
            if error_list:
                message += f"\n\nLỗi ({len(error_list)} dòng):\n" + "\n".join(error_list[:5])
                if len(error_list) > 5:
                    message += f"\n... và {len(error_list) - 5} lỗi khác"

            QMessageBox.information(self, "Kết quả nhập Excel", message)

            # Reload danh sách
            if success_count > 0:
                self.load_students()

        except Exception as e:
            QMessageBox.critical(self, "Lỗi nhập Excel", f"Không thể đọc file Excel:\n{str(e)}")

    # Widget quản lý thông tin phụ huynh
    def _build_parent_info_widget(self) -> QWidget:
        """Tạo widget thông tin phụ huynh"""
        parent_widget = QGroupBox("👨‍👩‍👧‍👦 Thông tin phụ huynh")
        layout = QVBoxLayout(parent_widget)

        # Thông tin bố
        father_group = QGroupBox("Thông tin bố")
        father_layout = QFormLayout(father_group)

        self.father_name = QLineEdit()
        self.father_phone = QLineEdit()
        self.father_job = QLineEdit()

        father_layout.addRow("Họ tên:", self.father_name)
        father_layout.addRow("SĐT:", self.father_phone)
        father_layout.addRow("Nghề nghiệp:", self.father_job)

        # Thông tin mẹ
        mother_group = QGroupBox("Thông tin mẹ")
        mother_layout = QFormLayout(mother_group)

        self.mother_name = QLineEdit()
        self.mother_phone = QLineEdit()
        self.mother_job = QLineEdit()

        mother_layout.addRow("Họ tên:", self.mother_name)
        mother_layout.addRow("SĐT:", self.mother_phone)
        mother_layout.addRow("Nghề nghiệp:", self.mother_job)

        # Thông tin chung
        general_group = QGroupBox("Thông tin chung")
        general_layout = QFormLayout(general_group)

        self.family_address = QTextEdit()
        self.family_address.setMaximumHeight(60)
        self.emergency_contact = QLineEdit()

        general_layout.addRow("Địa chỉ:", self.family_address)
        general_layout.addRow("Liên hệ khẩn cấp:", self.emergency_contact)

        layout.addWidget(father_group)
        layout.addWidget(mother_group)
        layout.addWidget(general_group)

        return parent_widget

    # Widget dashboard thống kê học sinh
    def _build_stats_widget(self) -> QWidget:
        """Tạo widget thống kê tổng quan học sinh"""
        stats_widget = QGroupBox("📊 Thống kê tổng quan")
        layout = QGridLayout(stats_widget)

        # Thống kê số lượng
        self.total_label = QLabel("Tổng: 0")
        self.total_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2196F3;")

        self.active_label = QLabel("Đang học: 0")
        self.active_label.setStyleSheet("font-size: 12px; color: #4CAF50;")

        self.group_label = QLabel("Học nhóm: 0")
        self.group_label.setStyleSheet("font-size: 12px; color: #FF9800;")

        self.private_label = QLabel("Kèm riêng: 0")
        self.private_label.setStyleSheet("font-size: 12px; color: #9C27B0;")

        # Phân bố theo lớp
        self.grade_stats = QLabel("Phân bố theo lớp:")
        self.grade_stats.setStyleSheet("font-size: 11px; color: #666;")

        layout.addWidget(self.total_label, 0, 0, 1, 2)
        layout.addWidget(self.active_label, 1, 0)
        layout.addWidget(self.group_label, 1, 1)
        layout.addWidget(self.private_label, 2, 0)
        layout.addWidget(self.grade_stats, 3, 0, 1, 2)

        return stats_widget

    # Cập nhật thống kê học sinh
    def _update_student_stats(self):
        """Cập nhật các số liệu thống kê học sinh"""
        try:
            # Lấy dữ liệu thống kê từ database
            total_query = "SELECT COUNT(*) as total FROM students"
            total_result = self.db.execute_query(total_query, fetch='one')
            total_count = total_result['total'] if total_result else 0

            # Thống kê theo trạng thái
            status_query = """
                SELECT status, COUNT(*) as count 
                FROM students 
                GROUP BY status
            """
            status_results = self.db.execute_query(status_query, fetch='all') or []

            group_count = 0
            private_count = 0
            for row in status_results:
                if 'nhóm' in row['status'].lower():
                    group_count = row['count']
                else:
                    private_count = row['count']

            # Thống kê theo lớp
            grade_query = """
                SELECT grade, COUNT(*) as count 
                FROM students 
                GROUP BY grade 
                ORDER BY grade
            """
            grade_results = self.db.execute_query(grade_query, fetch='all') or []
            grade_text = "Phân bố: " + ", ".join([f"Lớp {row['grade']}: {row['count']}" for row in grade_results])

            # Cập nhật UI
            self.total_label.setText(f"Tổng: {total_count}")
            self.active_label.setText(f"Đang học: {total_count}")
            self.group_label.setText(f"Học nhóm: {group_count}")
            self.private_label.setText(f"Kèm riêng: {private_count}")
            self.grade_stats.setText(grade_text[:50] + "..." if len(grade_text) > 50 else grade_text)

        except Exception as e:
            print(f"Lỗi cập nhật thống kê: {e}")