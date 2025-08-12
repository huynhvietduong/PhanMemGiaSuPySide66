from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QPushButton, QTableView, QHeaderView, QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex


class PackagesTableModel(QAbstractTableModel):
    HEADERS = ["ID", "Tên gói", "Số buổi / 4 tuần", "Học phí (VND)"]

    def __init__(self, rows=None):
        super().__init__()
        self._rows = rows or []  # mỗi row là dict: id, name, sessions, price

    def rowCount(self, parent=QModelIndex()):
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 4

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        return self.HEADERS[section] if orientation == Qt.Horizontal else section + 1

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        r = self._rows[index.row()]
        if role in (Qt.DisplayRole, Qt.EditRole):
            if index.column() == 0: return r["id"]
            if index.column() == 1: return r["name"]
            if index.column() == 2: return r["sessions"]
            if index.column() == 3: return f"{r['price']:.0f}"
        return None

    def id_at(self, row: int):
        return self._rows[row]["id"] if 0 <= row < len(self._rows) else None

    def set_rows(self, rows):
        self.beginResetModel()
        self._rows = rows or []
        self.endResetModel()


class PackageWindowQt(QWidget):
    """Quản lý Gói học (PySide6) — chuyển từ Tkinter."""
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setObjectName("PackageWindowQt")
        self._build_ui()
        self.load_packages()
        self.clear_form()

    # UI ----------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("Danh sách Gói học")
        title.setStyleSheet("font-size:16px; font-weight:600;")
        root.addWidget(title)

        self.table = QTableView()
        self.model = PackagesTableModel([])
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.clicked.connect(self.on_row_clicked)
        root.addWidget(self.table, 1)

        # Form
        gb = QGroupBox("Chi tiết Gói học")
        form = QVBoxLayout(gb)

        # tên gói
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Tên gói:"))
        self.ed_name = QLineEdit()
        self.ed_name.setMaxLength(100)
        row1.addWidget(self.ed_name, 1)
        form.addLayout(row1)

        # số buổi
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Số buổi (trong 4 tuần):"))
        self.spin_sessions = QSpinBox()
        self.spin_sessions.setRange(1, 60)
        self.spin_sessions.setValue(8)
        row2.addWidget(self.spin_sessions)
        form.addLayout(row2)

        # học phí
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Học phí (VND):"))
        self.spin_price = QDoubleSpinBox()
        self.spin_price.setDecimals(0)
        self.spin_price.setMaximum(1_000_000_000)
        self.spin_price.setSingleStep(50000)
        row3.addWidget(self.spin_price)
        form.addLayout(row3)

        root.addWidget(gb)

        # Buttons
        btns = QHBoxLayout()
        btn_add = QPushButton("Thêm mới")
        btn_upd = QPushButton("Cập nhật")
        btn_del = QPushButton("Xóa")
        btn_clr = QPushButton("Làm mới")

        btn_add.clicked.connect(self.add_package)
        btn_upd.clicked.connect(self.update_package)
        btn_del.clicked.connect(self.delete_package)
        btn_clr.clicked.connect(self.clear_form)

        for b in (btn_add, btn_upd, btn_del, btn_clr):
            btns.addWidget(b)
        btns.addStretch(1)
        root.addLayout(btns)

    # Data --------------------------------------------------------------------
    def load_packages(self):
        rows = self.db.execute_query(
            "SELECT id, name, sessions, price FROM packages ORDER BY name", fetch='all'
        ) or []
        data = [{"id": r[0], "name": r[1], "sessions": r[2], "price": float(r[3])} for r in rows]
        self.model.set_rows(data)
        if data:
            self.table.selectRow(0)

    # Events ------------------------------------------------------------------
    def on_row_clicked(self, index: QModelIndex):
        row = index.row()
        if row < 0:
            return
        pkg = self.model._rows[row]
        self.ed_name.setText(pkg["name"])
        self.spin_sessions.setValue(int(pkg["sessions"]))
        self.spin_price.setValue(float(pkg["price"]))

    # Actions -----------------------------------------------------------------
    def add_package(self):
        name = self.ed_name.text().strip()
        sessions = int(self.spin_sessions.value())
        price = float(self.spin_price.value())
        if not name or sessions <= 0 or price <= 0:
            QMessageBox.critical(self, "Lỗi", "Vui lòng nhập đầy đủ và hợp lệ.")
            return
        self.db.execute_query(
            "INSERT INTO packages (name, sessions, price) VALUES (?, ?, ?)",
            (name, sessions, price)
        )
        self.load_packages()
        self.clear_form()

    def update_package(self):
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            QMessageBox.critical(self, "Lỗi", "Vui lòng chọn 1 gói để cập nhật.")
            return
        pkg_id = self.model.id_at(sel[0].row())
        name = self.ed_name.text().strip()
        sessions = int(self.spin_sessions.value())
        price = float(self.spin_price.value())
        self.db.execute_query(
            "UPDATE packages SET name=?, sessions=?, price=? WHERE id=?",
            (name, sessions, price, pkg_id)
        )
        self.load_packages()
        self.clear_form()

    def delete_package(self):
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            QMessageBox.critical(self, "Lỗi", "Vui lòng chọn 1 gói để xóa.")
            return
        pkg_id = self.model.id_at(sel[0].row())
        ok = QMessageBox.question(
            self, "Xác nhận",
            "Xóa gói học này sẽ gỡ gói khỏi các học sinh đang được gán. Bạn có chắc không?"
        ) == QMessageBox.Yes
        if not ok:
            return
        self.db.execute_query("DELETE FROM packages WHERE id=?", (pkg_id,))
        self.load_packages()
        self.clear_form()

    def clear_form(self):
        self.ed_name.clear()
        self.spin_sessions.setValue(8)
        self.spin_price.setValue(0)
        self.table.clearSelection()
