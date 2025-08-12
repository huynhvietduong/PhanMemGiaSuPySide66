# ui_qt/windows/exercise_suggestion_window_qt.py
from PySide6 import QtCore, QtGui, QtWidgets

class ExerciseSuggestionWindowQt(QtWidgets.QWidget):
    """
    Gợi ý bài tập theo điểm yếu của học sinh (PySide6)
    - Chọn học sinh -> tìm các chủ đề yếu (AVG < 3 trong student_skills)
    - Hiển thị danh sách bài tập theo từng chủ đề (text hoặc ảnh)
    """
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setObjectName("ExerciseSuggestionWindowQt")

        # ==== Layout gốc ====
        root = QtWidgets.QVBoxLayout(self)
        title = QtWidgets.QLabel("📘 Gợi ý bài tập theo điểm yếu")
        title.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        title.setStyleSheet("font-weight:600; font-size:16px;")
        root.addWidget(title)

        # ==== Khung chọn học sinh ====
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Học sinh:"))
        self.student_cb = QtWidgets.QComboBox()
        self.student_cb.setMinimumWidth(320)
        row.addWidget(self.student_cb, 1)
        row.addStretch()
        root.addLayout(row)

        # nạp danh sách học sinh
        self.student_map = {}  # display -> id
        rows = self.db.execute_query("SELECT id, name FROM students ORDER BY name", fetch='all') or []
        for sid, name in rows:
            display = f"{name} (ID {sid})"
            self.student_map[display] = sid
            self.student_cb.addItem(display)

        # ==== Vùng nội dung gợi ý (cuộn được) ====
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.inner = QtWidgets.QWidget()
        self.inner_layout = QtWidgets.QVBoxLayout(self.inner)
        self.inner_layout.setContentsMargins(4, 4, 4, 4)
        self.scroll.setWidget(self.inner)
        root.addWidget(self.scroll, 1)

        # sự kiện
        self.student_cb.currentIndexChanged.connect(self.load_suggestions)

        # load lần đầu (nếu có dữ liệu)
        if self.student_cb.count() > 0:
            self.load_suggestions()

    def clear_suggestions(self):
        while self.inner_layout.count():
            item = self.inner_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def load_suggestions(self):
        self.clear_suggestions()

        display = self.student_cb.currentText()
        student_id = self.student_map.get(display)
        if not student_id:
            return

        # Chủ đề yếu: AVG(diem) < 3  (giữ logic như bản Tkinter)  :contentReference[oaicite:1]{index=1}
        weak_topics = self.db.execute_query("""
            SELECT chu_de, ROUND(AVG(diem), 1)
            FROM student_skills
            WHERE student_id = ?
            GROUP BY chu_de
            HAVING AVG(diem) < 3
            ORDER BY AVG(diem) ASC
        """, (student_id,), fetch='all') or []

        if not weak_topics:
            ok = QtWidgets.QLabel("🎉 Học sinh không có chủ đề yếu!")
            ok.setStyleSheet("color:green;")
            self.inner_layout.addWidget(ok)
            self.inner_layout.addStretch(1)
            return

        for chu_de, avg in weak_topics:
            box = QtWidgets.QGroupBox(f"📉 {chu_de} (Điểm TB: {avg})")
            box_l = QtWidgets.QVBoxLayout(box)

            rows = self.db.execute_query(
                "SELECT ten_bai, loai_tap, noi_dung FROM exercises WHERE chu_de = ?",
                (chu_de,), fetch='all'
            ) or []

            if not rows:
                box_l.addWidget(QtWidgets.QLabel("(Chưa có bài tập nào trong chủ đề này)"))
                self.inner_layout.addWidget(box)
                continue

            for ten_bai, loai_tap, noi_dung in rows:
                row_w = QtWidgets.QWidget()
                hl = QtWidgets.QHBoxLayout(row_w)
                hl.setContentsMargins(0, 2, 0, 2)

                name_lbl = QtWidgets.QLabel(f"• {ten_bai}")
                name_lbl.setMinimumWidth(220)
                hl.addWidget(name_lbl, 0)

                if loai_tap == "text":
                    txt = QtWidgets.QPlainTextEdit()
                    txt.setPlainText(noi_dung or "")
                    txt.setReadOnly(True)
                    txt.setMaximumHeight(90)
                    hl.addWidget(txt, 1)

                elif loai_tap == "image":
                    lbl = QtWidgets.QLabel()
                    lbl.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
                    pix = QtGui.QPixmap(noi_dung) if noi_dung and os.path.exists(noi_dung) else QtGui.QPixmap()
                    if not pix.isNull():
                        lbl.setPixmap(pix.scaled(300, 220, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
                    else:
                        lbl.setText("[Không mở được ảnh]")
                    hl.addWidget(lbl, 1)

                else:
                    hl.addWidget(QtWidgets.QLabel("(Loại bài tập không hỗ trợ)"), 1)

                box_l.addWidget(row_w)

            self.inner_layout.addWidget(box)

        self.inner_layout.addStretch(1)
