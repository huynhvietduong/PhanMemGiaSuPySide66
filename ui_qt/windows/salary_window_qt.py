# ui_qt/windows/salary_window_qt.py
from PySide6 import QtWidgets, QtCore
from PySide6.QtWidgets import (
    QWidget, QLabel, QComboBox, QPushButton, QHBoxLayout, QVBoxLayout,
    QFormLayout, QDateEdit, QTableWidget, QTableWidgetItem, QMessageBox
)
from PySide6.QtCore import QDate
from datetime import datetime, timedelta


class SalaryWindowQt(QWidget):
    """
    Báo cáo tính lương gia sư theo chu kỳ 4 tuần (PySide6).
    - Lưu ngày bắt đầu chu kỳ đầu tiên (settings.key = 'salary_start_date')
    - Sinh 12 chu kỳ liên tiếp (mỗi chu kỳ 28 ngày)
    - Tính học phí tổng hợp theo chu kỳ (gọi DB: get_students_for_salary_report)
    """
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self._build_ui()
        self._init_data()

    # ---------------- UI ----------------
    def _build_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Tính lương Gia sư")
        title.setStyleSheet("font-size:18px; font-weight:700;")
        root.addWidget(title)

        # Khối: thiết lập & chọn chu kỳ
        setup_box = QtWidgets.QGroupBox("Chọn chu kỳ tính lương")
        setup_layout = QFormLayout(setup_box)

        # Ngày BĐ chu kỳ đầu tiên
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")

        h_save = QHBoxLayout()
        h_save.addWidget(self.start_date_edit, 1)
        btn_save = QPushButton("Lưu")
        btn_save.clicked.connect(self.save_start_date)
        h_save.addWidget(btn_save)
        setup_layout.addRow(QLabel("Ngày BĐ chu kỳ đầu tiên:"), self._wrap(h_save))

        # Chọn chu kỳ
        self.cycle_combo = QComboBox()
        btn_calc = QPushButton("Tính lương")
        btn_calc.clicked.connect(self.calculate_salary)

        h_cycle = QHBoxLayout()
        h_cycle.addWidget(self.cycle_combo, 1)
        h_cycle.addWidget(btn_calc)
        setup_layout.addRow(QLabel("Chọn chu kỳ để tính lương:"), self._wrap(h_cycle))

        root.addWidget(setup_box)

        # Bảng kết quả
        result_box = QtWidgets.QGroupBox("Bảng kê chi tiết")
        v_result = QVBoxLayout(result_box)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["STT", "Họ và tên", "Lớp", "Gói học", "Học phí"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        v_result.addWidget(self.table)

        self.total_label = QLabel("TỔNG CỘNG: 0 VND")
        self.total_label.setStyleSheet("font-size:14px; font-weight:700;")
        v_result.addWidget(self.total_label, alignment=QtCore.Qt.AlignRight)

        root.addWidget(result_box)

    def _wrap(self, layout):
        w = QWidget()
        w.setLayout(layout)
        return w

    # -------------- Data init --------------
    def _init_data(self):
        # nạp start_date từ settings
        try:
            row = self.db.execute_query(
                "SELECT value FROM settings WHERE key='salary_start_date'", fetch='one'
            )
            if row and row[0]:
                # DB lưu dạng "YYYY-MM-DD"
                dt = datetime.strptime(row[0], "%Y-%m-%d").date()
                self.start_date_edit.setDate(QDate(dt.year, dt.month, dt.day))
            else:
                # default để trống → đặt hôm nay
                today = QDate.currentDate()
                self.start_date_edit.setDate(today)
        except Exception as e:
            QMessageBox.warning(self, "Cảnh báo", f"Không đọc được ngày bắt đầu: {e}")

        self.generate_cycles()

    # -------------- Actions --------------
    def save_start_date(self):
        try:
            qd = self.start_date_edit.date()
            start_str = f"{qd.year():04d}-{qd.month():02d}-{qd.day():02d}"
            # validate
            datetime.strptime(start_str, "%Y-%m-%d")

            self.db.execute_query(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('salary_start_date', ?)",
                (start_str,)
            )
            QMessageBox.information(self, "Thành công", "Đã lưu ngày bắt đầu chu kỳ.")
            self.generate_cycles()
        except ValueError:
            QMessageBox.critical(self, "Lỗi", "Định dạng ngày không hợp lệ. Vui lòng dùng YYYY-MM-DD.")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu ngày bắt đầu: {e}")

    def generate_cycles(self):
        """Sinh 12 chu kỳ, mỗi chu kỳ 28 ngày (4 tuần)."""
        try:
            qd = self.start_date_edit.date()
            start_date = datetime(qd.year(), qd.month(), qd.day())
        except Exception:
            return

        cycles = []
        s = start_date
        for i in range(12):
            end_date = s + timedelta(days=27)  # 4 tuần = 28 ngày
            label = f"Chu kỳ {i + 1}: {s.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}"
            cycles.append(label)
            s = s + timedelta(days=28)

        self.cycle_combo.clear()
        self.cycle_combo.addItems(cycles)
        if cycles:
            self.cycle_combo.setCurrentIndex(0)

    def calculate_salary(self):
        """
        Lấy dữ liệu học phí theo chu kỳ đã chọn.
        Hiện tại hàm này gọi thẳng DB helper: get_students_for_salary_report()
        giống bản Tkinter (sang Qt vẫn tái sử dụng). Kết quả cần dạng:
        [
          {"name": "...", "grade": "...", "package_name": "...", "price": 0.0},
          ...
        ]
        """
        try:
            # xóa bảng cũ
            self.table.setRowCount(0)

            students = self.db.get_students_for_salary_report() or []
            total = 0
            for idx, s in enumerate(students, start=1):
                row = self.table.rowCount()
                self.table.insertRow(row)

                def _item(text, align_center=False, align_right=False):
                    it = QTableWidgetItem(text)
                    if align_center:
                        it.setTextAlignment(QtCore.Qt.AlignCenter)
                    elif align_right:
                        it.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                    return it

                price = float(s.get("price", 0) or 0)
                total += price

                self.table.setItem(row, 0, _item(str(idx), align_center=True))
                self.table.setItem(row, 1, _item(str(s.get("name", ""))))
                self.table.setItem(row, 2, _item(str(s.get("grade", "")), align_center=True))
                self.table.setItem(row, 3, _item(str(s.get("package_name", ""))))
                self.table.setItem(row, 4, _item(f"{price:,.0f}", align_right=True))

            self.total_label.setText(f"TỔNG CỘNG: {total:,.0f} VND")
            self.table.resizeColumnsToContents()
            self.table.horizontalHeader().setStretchLastSection(True)

        except AttributeError:
            QMessageBox.critical(
                self, "Lỗi",
                "Thiếu hàm db.get_students_for_salary_report(). Hãy bổ sung helper này trong database.py"
            )
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể tính lương: {e}")
