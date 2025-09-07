# ui_qt/windows/assigned_exercise_manager_window_qt.py
from __future__ import annotations
from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QDateEdit, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QMessageBox, QGroupBox
)


class AssignedExerciseManagerWindowQt(QWidget):
    """
    📖 Bài tập đã giao – PySide6
    Giữ nguyên chức năng so với Tkinter:
      - Bộ lọc: Nhóm → Học sinh, Chủ đề, Trạng thái, Từ ngày/Đến ngày
      - Bảng: Ngày giao | Học sinh | Tên bài | Chủ đề | Trạng thái | Ghi chú
      - Chọn 1 dòng → xem nội dung bài tập phía dưới (text/link/khác)
    """
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager

        self.group_map: dict[str, int] = {}
        self.student_map: dict[str, int] = {}
        self.data_map: dict[str, dict] = {}

        root = QVBoxLayout(self)

        # --- Bộ lọc ---
        box = QGroupBox("Bộ lọc")
        fl = QtWidgets.QGridLayout(box)

        # Nhóm học
        fl.addWidget(QLabel("Nhóm học:"), 0, 0, alignment=Qt.AlignRight)
        self.cb_group = QComboBox()
        self.cb_group.currentIndexChanged.connect(self.on_group_selected)
        fl.addWidget(self.cb_group, 0, 1)

        # Học sinh (phụ thuộc nhóm)
        fl.addWidget(QLabel("Học sinh:"), 0, 2, alignment=Qt.AlignRight)
        self.cb_student = QComboBox()
        fl.addWidget(self.cb_student, 0, 3)

        # Chủ đề
        fl.addWidget(QLabel("Chủ đề:"), 0, 4, alignment=Qt.AlignRight)
        self.cb_topic = QComboBox()
        fl.addWidget(self.cb_topic, 0, 5)

        # Trạng thái
        fl.addWidget(QLabel("Trạng thái:"), 0, 6, alignment=Qt.AlignRight)
        self.cb_status = QComboBox()
        self.cb_status.addItems(["", "Chưa làm", "Đã làm", "Đã chấm"])
        fl.addWidget(self.cb_status, 0, 7)

        # Từ ngày / Đến ngày
        fl.addWidget(QLabel("Từ ngày:"), 1, 0, alignment=Qt.AlignRight)
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDisplayFormat("yyyy-MM-dd")
        self.from_date.setSpecialValueText("")  # cho phép rỗng
        self.from_date.setDate(QDate.currentDate())
        self.from_date.clear()  # để trống mặc định
        fl.addWidget(self.from_date, 1, 1)

        fl.addWidget(QLabel("Đến ngày:"), 1, 2, alignment=Qt.AlignRight)
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDisplayFormat("yyyy-MM-dd")
        self.to_date.setSpecialValueText("")
        self.to_date.setDate(QDate.currentDate())
        self.to_date.clear()
        fl.addWidget(self.to_date, 1, 3)

        # Nút Lọc / Xóa lọc
        self.btn_filter = QPushButton("🔍 Lọc")
        self.btn_clear = QPushButton("❌ Xóa lọc")
        self.btn_filter.clicked.connect(self.load_data)
        self.btn_clear.clicked.connect(self.clear_filters)
        fl.addWidget(self.btn_filter, 1, 7)
        fl.addWidget(self.btn_clear, 1, 8)

        root.addWidget(box)

        # --- Bảng dữ liệu ---
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Ngày giao", "Học sinh", "Tên bài", "Chủ đề", "Trạng thái", "Ghi chú"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self.view_exercise_content)
        root.addWidget(self.table, 1)

        # --- Khung xem nội dung ---
        self.content_box = QTextEdit()
        self.content_box.setReadOnly(True)
        self.content_box.setPlaceholderText("Nội dung bài tập sẽ hiển thị ở đây…")
        root.addWidget(self.content_box)

        self._load_filter_sources()
        self.load_data()

    # ---------- Filter sources ----------
    def _load_filter_sources(self):
        # Nhóm
        try:
            groups = self.db.execute_query(
                "SELECT id, name FROM groups ORDER BY name", fetch='all'
            ) or []
            self.cb_group.blockSignals(True)
            self.cb_group.clear()
            self.cb_group.addItem("")  # rỗng = không lọc
            self.group_map.clear()
            for g in groups:
                gid = g["id"] if isinstance(g, dict) else g[0]
                name = g["name"] if isinstance(g, dict) else g[1]
                self.cb_group.addItem(name)
                self.group_map[name] = gid
            self.cb_group.blockSignals(False)
        except Exception as e:
            QMessageBox.warning(self, "Lỗi", f"Không tải được danh sách nhóm:\n{e}")

        # Chủ đề
        try:
            topics = self.db.execute_query(
                "SELECT DISTINCT chu_de FROM exercises ORDER BY chu_de", fetch='all'
            ) or []
            self.cb_topic.clear()
            self.cb_topic.addItem("")  # rỗng
            for t in topics:
                chu_de = t["chu_de"] if isinstance(t, dict) else t[0]
                if chu_de:
                    self.cb_topic.addItem(chu_de)
        except Exception as e:
            QMessageBox.warning(self, "Lỗi", f"Không tải được chủ đề:\n{e}")

        # Học sinh (theo nhóm – để trống ban đầu)
        self.cb_student.clear()
        self.cb_student.addItem("")
        self.student_map.clear()

    def on_group_selected(self):
        # Khi chọn nhóm → nạp danh sách học sinh
        name = self.cb_group.currentText().strip()
        if not name:
            self.cb_student.clear()
            self.cb_student.addItem("")
            self.student_map.clear()
            return

        gid = self.group_map.get(name)
        if not gid:
            return

        students = self.db.execute_query(
            "SELECT id, name FROM students WHERE group_id = ? ORDER BY name",
            (gid,), fetch='all'
        ) or []

        self.cb_student.blockSignals(True)
        self.cb_student.clear()
        self.cb_student.addItem("")
        self.student_map.clear()
        for s in students:
            sid = s["id"] if isinstance(s, dict) else s[0]
            sname = s["name"] if isinstance(s, dict) else s[1]
            text = f"{sname} (ID {sid})"
            self.cb_student.addItem(text)
            self.student_map[text] = sid
        self.cb_student.blockSignals(False)

    # ---------- Data ----------
    def _date_text(self, w: QDateEdit) -> str:
        # Trả về chuỗi yyyy-MM-dd hoặc "" nếu rỗng
        try:
            if not w.date().isValid() or w.specialValueText() == "" and not w.text():
                return ""
            return w.date().toString("yyyy-MM-dd")
        except Exception:
            return ""

    def load_data(self):
        self.table.setRowCount(0)
        self.data_map.clear()

        query = """
            SELECT ae.id, ae.ngay_giao, s.name, e.ten_bai, e.chu_de,
                   ae.trang_thai, ae.ghi_chu, e.noi_dung, e.loai_tap
            FROM assigned_exercises ae
            JOIN exercises e ON ae.exercise_id = e.id
            JOIN students s  ON ae.student_id  = s.id
            WHERE 1=1
        """
        params: list = []

        # group
        gname = self.cb_group.currentText().strip()
        if gname:
            gid = self.group_map.get(gname)
            if gid:
                query += " AND s.group_id = ?"
                params.append(gid)

        # student
        s_text = self.cb_student.currentText().strip()
        if s_text:
            sid = self.student_map.get(s_text)
            if sid:
                query += " AND ae.student_id = ?"
                params.append(sid)

        # topic
        topic = self.cb_topic.currentText().strip()
        if topic:
            query += " AND e.chu_de = ?"
            params.append(topic)

        # status
        status = self.cb_status.currentText().strip()
        if status:
            query += " AND ae.trang_thai = ?"
            params.append(status)

        # date range
        fdate = self._date_text(self.from_date)
        if fdate:
            query += " AND ae.ngay_giao >= ?"
            params.append(fdate)
        tdate = self._date_text(self.to_date)
        if tdate:
            query += " AND ae.ngay_giao <= ?"
            params.append(tdate)

        try:
            rows = self.db.execute_query(query, params, fetch='all') or []
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể tải dữ liệu:\n{e}")
            return

        for r in rows:
            # hỗ trợ sqlite3.Row hoặc tuple
            if hasattr(r, "keys"):
                rid, ngay, hs_name, ten_bai, chu_de, trang_thai, ghi_chu, nd, loai = (
                    r["id"], r["ngay_giao"], r["name"], r["ten_bai"], r["chu_de"],
                    r["trang_thai"], r["ghi_chu"], r["noi_dung"], r["loai_tap"]
                )
            else:
                rid, ngay, hs_name, ten_bai, chu_de, trang_thai, ghi_chu, nd, loai = r

            row = self.table.rowCount()
            self.table.insertRow(row)
            self._set(row, 0, str(ngay), center=True)
            self._set(row, 1, str(hs_name))
            self._set(row, 2, str(ten_bai))
            self._set(row, 3, str(chu_de))
            self._set(row, 4, str(trang_thai), center=True)
            self._set(row, 5, str(ghi_chu or ""))

            # map id → content
            self.data_map[str(rid)] = {"content": nd, "loai": loai}
            # lưu id vào cột 0 (UserRole) để lấy nhanh khi chọn
            it = self.table.item(row, 0)
            it.setData(Qt.UserRole, str(rid))

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def _set(self, r: int, c: int, text: str, center: bool = False):
        it = QTableWidgetItem(text)
        if center:
            it.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(r, c, it)

    def view_exercise_content(self):
        sel_row = self.table.currentRow()
        if sel_row < 0:
            return
        it = self.table.item(sel_row, 0)
        if not it:
            return
        rid = it.data(Qt.UserRole)
        info = self.data_map.get(str(rid))
        if not info:
            self.content_box.clear()
            return

        nd = info.get("content", "")
        loai = (info.get("loai") or "").lower()
        self.content_box.clear()

        # Giữ đúng hành vi file Tk: text/link hiện thẳng; loại khác in dạng [TYPE] content
        if loai in ("text", "link"):
            self.content_box.setPlainText(str(nd or ""))
        else:
            self.content_box.setPlainText(f"[{loai.upper()}] {nd}")

    def clear_filters(self):
        self.cb_group.setCurrentIndex(0)
        self.cb_student.clear()
        self.cb_student.addItem("")
        self.cb_topic.setCurrentIndex(0)
        self.cb_status.setCurrentIndex(0)
        self.from_date.clear()
        self.to_date.clear()
        self.load_data()
