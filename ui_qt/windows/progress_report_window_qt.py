# ui_qt/windows/progress_report_window_qt.py
from PySide6 import QtWidgets, QtCore
from PySide6.QtWidgets import (
    QDialog, QLabel, QComboBox, QPushButton,
    QHBoxLayout, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QMessageBox
)

class ProgressReportWindowQt(QDialog):
    """
    Báo cáo Tiến độ Giảng dạy (PySide6)
    - Chọn khối lớp
    - Bảng: Hàng = Chủ đề, Cột = Nhóm trong khối => đánh dấu ✅ nếu nhóm đã học chủ đề
    """
    def __init__(self,db_manager, parent=None ):
        super().__init__(parent)
        self.db = db_manager
        self.setWindowTitle("Báo cáo Tiến độ")
        self.resize(900, 600)
        self._build_ui()
        self._load_grades()
        self._load_report()

    # -------- UI --------
    def _build_ui(self):
        title = QLabel("Báo cáo Tiến độ Giảng dạy")
        title.setStyleSheet("font-size:18px; font-weight:700;")

        # bộ lọc
        self.grade_cb = QComboBox()
        self.grade_cb.currentIndexChanged.connect(self._load_report)
        self.refresh_btn = QPushButton("Làm mới")
        self.refresh_btn.clicked.connect(self._load_report)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Chọn khối lớp:"))
        filter_row.addWidget(self.grade_cb, 1)
        filter_row.addStretch()
        filter_row.addWidget(self.refresh_btn)

        # bảng
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(False)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(filter_row)
        layout.addWidget(self.table, 1)

    # -------- DATA --------
    def _load_grades(self):
        """Nạp danh sách khối lớp vào combobox."""
        try:
            rows = self.db.execute_query(
                "SELECT DISTINCT grade FROM groups ORDER BY grade", fetch='all'
            ) or []
            self.grade_cb.blockSignals(True)
            self.grade_cb.clear()
            for r in rows:
                # r có thể là sqlite3.Row hoặc tuple
                grade = r[0] if not isinstance(r, dict) else r["grade"]
                self.grade_cb.addItem(str(grade))
            self.grade_cb.blockSignals(False)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể tải danh sách khối lớp:\n{e}")

    def _load_report(self):
        """Dựng bảng tiến độ theo khối đã chọn."""
        grade = self.grade_cb.currentText().strip()
        if not grade:
            self.table.clear()
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return

        # 1) Lấy groups thuộc khối
        groups = self.db.execute_query(
            "SELECT id, name FROM groups WHERE grade = ? ORDER BY name",
            (grade,), fetch='all'
        ) or []

        # 2) Lấy danh sách chủ đề thuộc các buổi của khối (loại rỗng)
        topics = self.db.execute_query(
            """
            SELECT DISTINCT sl.topic
            FROM session_logs sl
            JOIN groups g ON sl.group_id = g.id
            WHERE g.grade = ?
              AND sl.topic IS NOT NULL
              AND sl.topic != ''
            ORDER BY sl.session_date
            """,
            (grade,), fetch='all'
        ) or []

        if not groups or not topics:
            self.table.clear()
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            self.table.setColumnCount(1)
            self.table.setHorizontalHeaderLabels(["Chủ đề"])
            self.table.setRowCount(1)
            self.table.setItem(0, 0, QTableWidgetItem("Không có dữ liệu tiến độ cho khối lớp này."))
            return

        g_ids = [int(r[0] if not isinstance(r, dict) else r["id"]) for r in groups]
        g_names = [str(r[1] if not isinstance(r, dict) else r["name"]) for r in groups]
        topic_list = [str(r[0] if not isinstance(r, dict) else r["topic"]) for r in topics]

        # 3) Tạo map topic đã học: {(group_id, topic): True}
        learned = {}
        # Cẩn thận số lượng placeholder '?'
        placeholders = ",".join("?" for _ in topic_list)
        query = f"SELECT group_id, topic FROM session_logs WHERE topic IN ({placeholders})"
        res = self.db.execute_query(query, topic_list, fetch='all') or []
        for row in res:
            gid = row[0] if not isinstance(row, dict) else row["group_id"]
            tpc = row[1] if not isinstance(row, dict) else row["topic"]
            learned[(int(gid), str(tpc))] = True

        # 4) Lấp bảng: cột 0 = Chủ đề, các cột sau là tên nhóm
        self.table.clear()
        self.table.setRowCount(len(topic_list))
        self.table.setColumnCount(1 + len(g_names))
        headers = ["Chủ đề"] + g_names
        self.table.setHorizontalHeaderLabels(headers)

        for r, topic in enumerate(topic_list):
            # chủ đề
            self.table.setItem(r, 0, QTableWidgetItem(topic))
            # từng nhóm
            for c, gid in enumerate(g_ids, start=1):
                mark = "✅" if learned.get((gid, topic)) else ""
                item = QTableWidgetItem(mark)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(r, c, item)

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
