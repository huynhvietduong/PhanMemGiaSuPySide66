# ui_qt/windows/schedule_makeup_window_qt.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QCheckBox, QComboBox, QPushButton,
    QHBoxLayout, QMessageBox, QGridLayout
)
from PySide6.QtCore import Qt, QDate
from datetime import datetime, timedelta
from constants import DAYS_OF_WEEK_VN, FIXED_TIME_SLOTS  # <-- sửa dòng này

# LƯU Ý: chỉnh import đường dẫn constants cho khớp repo của bạn

class ScheduleMakeUpWindowQt(QWidget):
    """
    Sắp xếp dạy bù (PySide6).
    - attendance_info_list: có thể None/[] (khi mở độc lập), hoặc danh sách vắng mặt được chọn từ báo cáo.
      Mỗi phần tử (nếu có) dự kiến dạng: {'att_id', 'student_id', 'student_name', 'group_grade', 'session_date', ...}
    """
    def __init__(self, db_manager, attendance_info_list=None, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.attendance_list = attendance_info_list or []
        # Nếu có danh sách từ điểm danh -> cố gắng lấy grade; nếu không có thì None
        self.student_grade = None
        for it in self.attendance_list:
            if it.get('group_grade'):
                self.student_grade = it['group_grade']
                break

        self.group_map = {}
        self.free_slot_map = {}

        self.setObjectName("ScheduleMakeUpWindowQt")
        self._build_ui()
        self.populate_group_combo()     # sau khi UI sẵn sàng
        self.find_and_display_free_slots()

    def _build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("Sắp xếp Lịch Dạy bù")
        title.setAlignment(Qt.AlignLeft)
        title.setStyleSheet("font-size:18px;font-weight:600;")
        root.addWidget(title)

        # Gợi ý: nếu mở từ danh sách vắng -> dòng mô tả
        if len(self.attendance_list) == 1:
            info = self.attendance_list[0]
            hint = QLabel(f"Học sinh: {info.get('student_name','?')}  •  Vắng ngày: {info.get('session_date','?')}")
            root.addWidget(hint)
        elif len(self.attendance_list) > 1:
            hint = QLabel(f"Đang sắp xếp dạy bù cho {len(self.attendance_list)} học sinh đã chọn")
            root.addWidget(hint)
        else:
            hint = QLabel("Mở độc lập (không có danh sách vắng cụ thể) — bạn có thể chọn nhóm/khung giờ dạy bù.")
            hint.setStyleSheet("color:#666;")
            root.addWidget(hint)

        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        # ===== TAB 1: Học bù với nhóm khác =====
        tab_group = QWidget()
        g = QVBoxLayout(tab_group)

        self.chk_show_all = QCheckBox("Hiển thị cả các nhóm khác khối")
        self.chk_show_all.stateChanged.connect(self.populate_group_combo)
        g.addWidget(self.chk_show_all)

        g.addWidget(QLabel("Bước 1: Chọn nhóm để học bù:"))
        self.group_combo = QComboBox()
        self.group_combo.currentIndexChanged.connect(self.on_group_selected)
        g.addWidget(self.group_combo)

        g.addWidget(QLabel("Bước 2: Chọn ngày học của nhóm:"))
        self.session_combo = QComboBox()
        self.session_combo.setEnabled(False)
        g.addWidget(self.session_combo)

        btn_group = QPushButton("Xác nhận học bù với nhóm")
        btn_group.clicked.connect(self.schedule_group_session)
        g.addWidget(btn_group)

        tabs.addTab(tab_group, "Học bù với nhóm khác")

        # ===== TAB 2: Dạy bù riêng (1-1 hoặc nhiều HS cùng được chọn) =====
        tab_private = QWidget()
        grid = QGridLayout(tab_private)

        grid.addWidget(QLabel("Khung giờ trống sẵn có (14 ngày tới):"), 0, 0)
        self.free_slot_combo = QComboBox()
        grid.addWidget(self.free_slot_combo, 0, 1)

        btn_private = QPushButton("Lên lịch buổi bù mới")
        btn_private.clicked.connect(self.schedule_private_session)
        grid.addWidget(btn_private, 1, 0, 1, 2)

        tabs.addTab(tab_private, "Dạy bù riêng")

    # ====== Logic ======
    def populate_group_combo(self):
        # lấy danh sách nhóm
        if self.chk_show_all.isChecked() or not self.student_grade:
            rows = self.db.execute_query("SELECT id, name FROM groups ORDER BY name", fetch='all') or []
        else:
            rows = self.db.execute_query(
                "SELECT id, name FROM groups WHERE grade = ? ORDER BY name",
                (self.student_grade,), fetch='all'
            ) or []

        self.group_map = {r['name']: r['id'] for r in rows}
        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        self.group_combo.addItems(self.group_map.keys())
        self.group_combo.blockSignals(False)

        # reset session combo
        self.session_combo.clear()
        self.session_combo.setEnabled(False)

    def on_group_selected(self):
        name = self.group_combo.currentText()
        gid = self.group_map.get(name)
        self.session_combo.clear()
        self.session_combo.setEnabled(False)
        if not gid:
            return

        schedule = self.db.execute_query(
            "SELECT day_of_week, time_slot FROM schedule WHERE group_id = ?",
            (gid,), fetch='all'
        ) or []
        if not schedule:
            return

        # liệt kê các ngày trong 30 ngày tới trùng day_of_week của nhóm
        today = datetime.now()
        possible = []
        for i in range(1, 31):
            d = today + timedelta(days=i)
            day_vn = DAYS_OF_WEEK_VN[d.weekday()]
            for row in schedule:
                if row['day_of_week'] == day_vn:
                    possible.append(f"Nhóm {name} - {day_vn}, {d.strftime('%Y-%m-%d')} ({row['time_slot']})")

        if possible:
            self.session_combo.addItems(possible)
            self.session_combo.setEnabled(True)

    def find_and_display_free_slots(self):
        # tính khung trống 14 ngày tới: lấy tất cả slot cố định – (lịch nhóm + các buổi bù riêng đã có)
        today = datetime.now()
        busy = set()

        # lịch nhóm theo lịch cố định (theo thứ)
        for i in range(14):
            dd = today + timedelta(days=i)
            day_vn = DAYS_OF_WEEK_VN[dd.weekday()]
            rows = self.db.execute_query(
                "SELECT time_slot FROM schedule WHERE day_of_week = ?",
                (day_vn,), fetch='all'
            ) or []
            for r in rows:
                busy.add((dd.strftime("%Y-%m-%d"), r['time_slot']))

        # lịch bù riêng đã xếp
        start_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        end_date   = (today + timedelta(days=14)).strftime("%Y-%m-%d")
        rows = self.db.execute_query(
            "SELECT session_date, time_slot FROM makeup_sessions WHERE is_private = 1 AND session_date BETWEEN ? AND ?",
            (start_date, end_date), fetch='all'
        ) or []
        for r in rows:
            busy.add((r['session_date'], r['time_slot']))

        free_items = []
        for i in range(1, 15):
            dd = today + timedelta(days=i)
            date_str = dd.strftime("%Y-%m-%d")
            day_vn = DAYS_OF_WEEK_VN[dd.weekday()]
            for slot in FIXED_TIME_SLOTS:
                if (date_str, slot) not in busy:
                    label = f"{day_vn}, {date_str} ({slot})"
                    free_items.append({'display': label, 'date': date_str, 'time': slot})

        self.free_slot_map = {x['display']: x for x in free_items}
        self.free_slot_combo.clear()
        self.free_slot_combo.addItems([x['display'] for x in free_items])

    def schedule_group_session(self):
        disp = self.session_combo.currentText().strip()
        if not disp:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng chọn một buổi học trong danh sách.")
            return
        # parse ngày từ chuỗi "Nhóm {name} - {day_vn}, YYYY-MM-DD (HH:MM)"
        try:
            after_comma = disp.split(", ", 1)[1]
            date_str = after_comma.split(" ")[0]  # YYYY-MM-DD
        except Exception:
            QMessageBox.critical(self, "Lỗi", "Không đọc được ngày từ lựa chọn.")
            return

        gid = self.group_map.get(self.group_combo.currentText())
        if not gid:
            QMessageBox.critical(self, "Lỗi", "Nhóm không hợp lệ.")
            return

        # Nếu không có danh sách vắng: không thể gắn attendance_id -> chỉ tạo lịch “tham gia học bù” lỏng (không attendance gốc)
        if not self.attendance_list:
            QMessageBox.information(self, "Thông tin",
                                    "Bạn mở cửa sổ độc lập nên không có 'attendance_id' để gắn vào.\n"
                                    "Hãy mở từ màn hình điểm danh nếu muốn đánh dấu 'Đã dạy bù' tự động.")
            return

        try:
            for att in self.attendance_list:
                self.db.execute_query(
                    "DELETE FROM makeup_sessions WHERE attendance_id = ?",
                    (att['att_id'],)
                )
                self.db.execute_query(
                    "INSERT INTO makeup_sessions(attendance_id, student_id, session_date, time_slot, host_group_id, is_private) "
                    "VALUES (?, ?, ?, NULL, ?, 0)",
                    (att['att_id'], att['student_id'], date_str, gid)
                )
            QMessageBox.information(self, "Thành công", "Đã ghi nhận học bù với nhóm.")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi CSDL", f"Không thể lưu: {e}")

    def schedule_private_session(self):
        disp = self.free_slot_combo.currentText().strip()
        if not disp:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng chọn một khung giờ trống.")
            return
        info = self.free_slot_map.get(disp)
        if not info:
            QMessageBox.critical(self, "Lỗi", "Không đọc được dữ liệu khung giờ.")
            return

        # Không có danh sách vắng -> không biết học sinh nào; yêu cầu mở từ báo cáo vắng để tự động gắn
        if not self.attendance_list:
            QMessageBox.information(self, "Thông tin",
                                    "Bạn mở cửa sổ độc lập nên không có danh sách học sinh để xếp buổi bù riêng.\n"
                                    "Hãy mở từ màn hình báo cáo/điểm danh để chọn học sinh vắng trước.")
            return

        try:
            for att in self.attendance_list:
                self.db.execute_query(
                    "DELETE FROM makeup_sessions WHERE attendance_id = ?",
                    (att['att_id'],)
                )
                self.db.execute_query(
                    "INSERT INTO makeup_sessions(attendance_id, student_id, session_date, time_slot, host_group_id, is_private) "
                    "VALUES (?, ?, ?, ?, NULL, 1)",
                    (att['att_id'], att['student_id'], info['date'], info['time'])
                )
            QMessageBox.information(self, "Thành công", "Đã lên lịch buổi bù riêng.")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi CSDL", f"Không thể lưu: {e}")
