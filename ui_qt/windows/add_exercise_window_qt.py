# ui_qt/windows/add_exercise_window_qt.py
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit, QComboBox,
    QPushButton, QFileDialog, QMessageBox, QFormLayout
)
import os
import json

class AddExerciseWindowQt(QWidget):
    """
    Thêm bài tập vào bảng exercises.
    Cột tham chiếu (theo app cũ): chu_de, ten_bai, loai_tap, noi_dung, ghi_chu
    - loai_tap: text | image | link
    - noi_dung:
        + text  -> nội dung văn bản trong QTextEdit
        + image -> đường dẫn file ảnh
        + link  -> URL (Google doc/drive, v.v…)
    """

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self._ensure_table()
        self._build_ui()

    # Tạo bảng nếu thiếu (giữ tương thích dự án cũ)
    def _ensure_table(self):
        self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS exercises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chu_de   TEXT NOT NULL,
                ten_bai  TEXT NOT NULL,
                loai_tap TEXT NOT NULL,     -- text | image | link
                noi_dung TEXT NOT NULL,     -- json/text tuỳ loại
                ghi_chu  TEXT
            )
        """)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)

        title = QLabel("➕ Thêm bài tập")
        title.setStyleSheet("font-size:18px; font-weight:600;")
        root.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        # Trường cơ bản
        self.ed_chude = QLineEdit()
        self.ed_tenbai = QLineEdit()

        self.cb_loai = QComboBox()
        self.cb_loai.addItems(["text", "image", "link"])
        self.cb_loai.currentTextChanged.connect(self._on_kind_changed)

        # Khu nội dung theo loại
        self.txt_noidung = QTextEdit()     # cho loại "text"
        self.ed_link = QLineEdit()         # cho loại "link"
        self.ed_image = QLineEdit()        # path ảnh
        self.btn_browse = QPushButton("Chọn ảnh…")
        self.btn_browse.clicked.connect(self._pick_image)

        # ghi chú
        self.ed_ghichu = QLineEdit()

        form.addRow("Chủ đề:", self.ed_chude)
        form.addRow("Tên bài:", self.ed_tenbai)
        form.addRow("Loại:", self.cb_loai)

        # container cho nội dung (sẽ thay đổi theo loại)
        self._content_stack = QVBoxLayout()

        # widget text
        self._w_text = QWidget()
        lay_text = QVBoxLayout(self._w_text)
        lay_text.addWidget(QLabel("Nội dung văn bản:"))
        lay_text.addWidget(self.txt_noidung)

        # widget image
        self._w_image = QWidget()
        lay_img = QHBoxLayout(self._w_image)
        lay_img.addWidget(self.ed_image)
        lay_img.addWidget(self.btn_browse)

        # widget link
        self._w_link = QWidget()
        lay_link = QVBoxLayout(self._w_link)
        lay_link.addWidget(QLabel("URL / liên kết:"))
        lay_link.addWidget(self.ed_link)

        # mặc định hiển thị theo loại hiện tại
        self._set_content_widget("text")

        form.addRow(QLabel("Nội dung:"), self._wrap(self._content_stack))
        form.addRow("Ghi chú:", self.ed_ghichu)

        root.addLayout(form)

        # Nút lệnh
        btns = QHBoxLayout()
        btns.addStretch(1)
        btn_save = QPushButton("💾 Lưu")
        btn_clear = QPushButton("Làm mới")
        btn_save.clicked.connect(self._save)
        btn_clear.clicked.connect(self._clear)
        btns.addWidget(btn_clear)
        btns.addWidget(btn_save)
        root.addLayout(btns)

    def _wrap(self, layout: QVBoxLayout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        return w

    def _set_content_widget(self, kind: str):
        # clear layout
        while self._content_stack.count():
            item = self._content_stack.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)

        if kind == "text":
            self._content_stack.addWidget(self._w_text)
        elif kind == "image":
            self._content_stack.addWidget(self._w_image)
        else:
            self._content_stack.addWidget(self._w_link)

    def _on_kind_changed(self, kind: str):
        self._set_content_widget(kind)

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh", "", "Ảnh (*.png *.jpg *.jpeg *.bmp *.gif);;Tất cả (*.*)")
        if path:
            self.ed_image.setText(path)

    def _validate(self) -> tuple[bool, str]:
        chu_de = self.ed_chude.text().strip()
        ten_bai = self.ed_tenbai.text().strip()
        kind = self.cb_loai.currentText()

        if not chu_de or not ten_bai:
            return False, "Vui lòng nhập đầy đủ 'Chủ đề' và 'Tên bài'."

        if kind == "text":
            content = self.txt_noidung.toPlainText().strip()
            if not content:
                return False, "Bạn chọn loại 'text' nhưng nội dung đang trống."
        elif kind == "image":
            p = self.ed_image.text().strip()
            if not p:
                return False, "Bạn chọn loại 'image' nhưng chưa chọn file."
            if not os.path.exists(p):
                return False, f"File ảnh không tồn tại:\n{p}"
        elif kind == "link":
            url = self.ed_link.text().strip()
            if not url:
                return False, "Bạn chọn loại 'link' nhưng chưa nhập URL."
        return True, ""

    def _save(self):
        ok, msg = self._validate()
        if not ok:
            QMessageBox.warning(self, "Thiếu dữ liệu", msg)
            return

        chu_de = self.ed_chude.text().strip()
        ten_bai = self.ed_tenbai.text().strip()
        kind = self.cb_loai.currentText()
        ghi_chu = self.ed_ghichu.text().strip()

        if kind == "text":
            # Lưu nội dung text trực tiếp
            noi_dung = self.txt_noidung.toPlainText().strip()
        elif kind == "image":
            # Lưu metadata dạng JSON để dễ mở rộng
            noi_dung = json.dumps({"type": "image", "path": self.ed_image.text().strip()}, ensure_ascii=False)
        else:  # link
            noi_dung = json.dumps({"type": "link", "url": self.ed_link.text().strip()}, ensure_ascii=False)

        self.db.execute_query(
            "INSERT INTO exercises (chu_de, ten_bai, loai_tap, noi_dung, ghi_chu) VALUES (?, ?, ?, ?, ?)",
            (chu_de, ten_bai, kind, noi_dung, ghi_chu)
        )
        QMessageBox.information(self, "Thành công", "Đã thêm bài tập.")
        self._clear()

    def _clear(self):
        self.ed_chude.clear()
        self.ed_tenbai.clear()
        self.cb_loai.setCurrentText("text")
        self.txt_noidung.clear()
        self.ed_link.clear()
        self.ed_image.clear()
        self.ed_ghichu.clear()
