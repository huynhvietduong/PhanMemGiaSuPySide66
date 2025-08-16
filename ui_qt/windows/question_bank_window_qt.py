# ui_qt/windows/question_bank_window_qt.py
from __future__ import annotations

import json
import os
from typing import List, Dict

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt


class QuestionBankWindowQt(QtWidgets.QWidget):
    """
    PySide6 - Ngân hàng câu hỏi
    - Trái: Cây thư mục (exercise_tree)
    - Giữa: Danh sách câu hỏi
    - Phải: Chi tiết câu hỏi + đáp án A-E
    - Thanh cấu hình: Môn / Lớp / Chủ đề / Dạng / Mức độ, Tìm kiếm, Nhập từ Word
    """
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setObjectName("QuestionBankWindowQt")
        self.setWindowTitle("Ngân hàng câu hỏi")
        self.resize(1200, 680)

        # đảm bảo bảng tồn tại (an toàn nếu CSDL cũ)
        self._ensure_tables()

        self.current_question_id: int | None = None
        self.tree_nodes: Dict[str, int] = {}  # QTreeWidgetItem->id

        root = QtWidgets.QVBoxLayout(self)

        # ----------------- thanh cấu hình trên cùng -----------------
        top = QtWidgets.QGridLayout()
        root.addLayout(top)

        self.btn_toggle_tree = QtWidgets.QPushButton("🪟 Ẩn/Hiện cây")
        self.btn_toggle_tree.clicked.connect(self.toggle_tree_panel)
        top.addWidget(self.btn_toggle_tree, 0, 0)

        top.addWidget(QtWidgets.QLabel("Môn:"), 0, 1)
        self.subject_cb = QtWidgets.QComboBox()
        self.subject_cb.setEditable(False)
        top.addWidget(self.subject_cb, 0, 2)

        top.addWidget(QtWidgets.QLabel("Lớp:"), 0, 3)
        self.grade_cb = QtWidgets.QComboBox()
        top.addWidget(self.grade_cb, 0, 4)

        top.addWidget(QtWidgets.QLabel("Chủ đề:"), 0, 5)
        self.topic_cb = QtWidgets.QComboBox()
        top.addWidget(self.topic_cb, 0, 6)

        top.addWidget(QtWidgets.QLabel("Dạng:"), 0, 7)
        self.type_cb = QtWidgets.QComboBox()
        top.addWidget(self.type_cb, 0, 8)

        top.addWidget(QtWidgets.QLabel("Mức độ:"), 0, 9)
        self.level_cb = QtWidgets.QComboBox()
        self.level_cb.addItems(["", "Nhận biết", "Thông hiểu", "Vận dụng", "Vận dụng cao", "Sáng tạo"])
        top.addWidget(self.level_cb, 0, 10)

        # hàng 2
        self.btn_open_tree = QtWidgets.QPushButton("🌲 Quản lý cây")
        self.btn_open_tree.clicked.connect(self.open_tree_manager)
        top.addWidget(self.btn_open_tree, 1, 1)

        top.addWidget(QtWidgets.QLabel("🔍 Từ khoá:"), 1, 2)
        self.search_edit = QtWidgets.QLineEdit()
        top.addWidget(self.search_edit, 1, 3)

        self.btn_search = QtWidgets.QPushButton("Tìm")
        self.btn_search.clicked.connect(self.search_questions)
        top.addWidget(self.btn_search, 1, 4)

        self.btn_import = QtWidgets.QPushButton("📥 Nhập từ Word")
        self.btn_import.clicked.connect(self.import_from_word)
        top.addWidget(self.btn_import, 1, 5)

        self.btn_filter = QtWidgets.QPushButton("Lọc theo combobox")
        self.btn_filter.clicked.connect(self.filter_by_combobox)
        top.addWidget(self.btn_filter, 1, 6)

        # ----------------- splitter 3 cột -----------------
        split = QtWidgets.QSplitter(Qt.Horizontal)
        root.addWidget(split, 1)

        # --- Cột trái: Cây ---
        left = QtWidgets.QWidget()
        left_l = QtWidgets.QVBoxLayout(left)
        left_l.setContentsMargins(6, 6, 6, 6)

        left_l.addWidget(QtWidgets.QLabel("Cây thư mục"))
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemSelectionChanged.connect(self.on_tree_select)
        left_l.addWidget(self.tree, 1)

        split.addWidget(left)

        # --- Cột giữa: Danh sách câu hỏi ---
        mid = QtWidgets.QWidget()
        mid_l = QtWidgets.QVBoxLayout(mid)
        mid_l.setContentsMargins(6, 6, 6, 6)

        mid_l.addWidget(QtWidgets.QLabel("Danh sách câu hỏi"))
        self.q_table = QtWidgets.QTableWidget(0, 6)
        self.q_table.setHorizontalHeaderLabels(["ID", "Nội dung", "Số đáp án", "Đáp án đúng", "Dạng", "Mức độ"])
        self.q_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.q_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.q_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.q_table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.q_table.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        self.q_table.horizontalHeader().setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)
        self.q_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.q_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.q_table.itemSelectionChanged.connect(self.on_question_select)
        mid_l.addWidget(self.q_table, 1)

        split.addWidget(mid)

        # --- Cột phải: Chi tiết ---
        right = QtWidgets.QWidget()
        r = QtWidgets.QVBoxLayout(right)
        r.setContentsMargins(6, 6, 6, 6)

        r.addWidget(QtWidgets.QLabel("Chi tiết câu hỏi"))
        self.content_text = QtWidgets.QPlainTextEdit()
        self.content_text.setPlaceholderText("Nội dung câu hỏi…")
        self.content_text.setMaximumBlockCount(500)
        self.content_text.setMinimumHeight(120)
        r.addWidget(self.content_text)

        # đáp án A-E
        self.correct_group = QtWidgets.QButtonGroup(self)
        self.option_entries: Dict[str, QtWidgets.QLineEdit] = {}

        for label in ["A", "B", "C", "D", "E"]:
            row = QtWidgets.QHBoxLayout()
            rb = QtWidgets.QRadioButton(label)
            self.correct_group.addButton(rb)
            row.addWidget(rb)
            ent = QtWidgets.QLineEdit()
            ent.setPlaceholderText(f"Nội dung đáp án {label}")
            row.addWidget(ent, 1)
            r.addLayout(row)
            self.option_entries[label] = ent

        # buttons
        btns = QtWidgets.QHBoxLayout()
        self.btn_save = QtWidgets.QPushButton("Lưu/Cập nhật")
        self.btn_save.clicked.connect(self.save_question)
        self.btn_delete = QtWidgets.QPushButton("❌ Xoá")
        self.btn_delete.clicked.connect(self.delete_question)
        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_delete)
        r.addLayout(btns)

        split.addWidget(right)

        split.setSizes([240, 520, 440])

        # init dữ liệu
        self.refresh_tree()
        self.load_available_subjects()
        self.load_available_grades()

        # signal cho combobox
        self.subject_cb.currentIndexChanged.connect(self.load_available_topics)
        self.grade_cb.currentIndexChanged.connect(self.load_available_topics)
        self.topic_cb.currentIndexChanged.connect(self.load_available_types)

    # ====================== DB helpers ======================
    def _ensure_tables(self):
        self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS exercise_tree (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER,
                name TEXT NOT NULL,
                level TEXT NOT NULL,
                UNIQUE(parent_id, name, level)
            );
        """)
        self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS question_bank (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_text TEXT,
                options TEXT,
                correct TEXT,
                tree_id INTEGER
            );
        """)

    # ====================== Tree ======================
    def refresh_tree(self):
        self.tree.clear()
        self.tree_nodes.clear()

        rows = self.db.execute_query(
            "SELECT id,parent_id,name,level FROM exercise_tree ORDER BY parent_id,level,name",
            fetch='all'
        ) or []
        children: Dict[int | None, list] = {}
        for r in rows:
            children.setdefault(r["parent_id"], []).append(r)

        def build(parent_db_id: int | None, parent_item: QtWidgets.QTreeWidgetItem | None):
            for node in children.get(parent_db_id, []):
                item = QtWidgets.QTreeWidgetItem([node["name"]])
                item.setData(0, Qt.UserRole, node["id"])
                self.tree_nodes[str(id(item))] = node["id"]
                if parent_item is None:
                    self.tree.addTopLevelItem(item)
                else:
                    parent_item.addChild(item)
                build(node["id"], item)

        build(None, None)
        self.tree.expandAll()

    def on_tree_select(self):
        items = self.tree.selectedItems()
        if not items:
            return
        tree_id = items[0].data(0, Qt.UserRole)
        if not tree_id:
            return

        rows = self.db.execute_query("SELECT * FROM question_bank WHERE tree_id=?", (tree_id,), fetch="all") or []
        self._load_question_rows(rows)

    # ====================== Questions list ======================
    def _load_question_rows(self, rows):
        self.q_table.setRowCount(0)
        for r in rows:
            content_preview = (r["content_text"] or "")[:50].replace("\n", " ").strip()
            opts = json.loads(r["options"] or "[]")
            so_dapan = len(opts)
            dap_an = r.get("correct", "-") if isinstance(r, dict) else "-"
            # lấy chuỗi dạng/mức độ từ path
            path = self.get_tree_path(r["tree_id"])
            path_dict = {p["level"]: p["name"] for p in path}
            dang = path_dict.get("Dạng", "-")
            muc_do = path_dict.get("Mức độ", "-")

            row_idx = self.q_table.rowCount()
            self.q_table.insertRow(row_idx)
            self.q_table.setItem(row_idx, 0, QtWidgets.QTableWidgetItem(str(r["id"])))
            self.q_table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(content_preview))
            self.q_table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(str(so_dapan)))
            self.q_table.setItem(row_idx, 3, QtWidgets.QTableWidgetItem(dap_an or "-"))
            self.q_table.setItem(row_idx, 4, QtWidgets.QTableWidgetItem(dang))
            self.q_table.setItem(row_idx, 5, QtWidgets.QTableWidgetItem(muc_do))

    def on_question_select(self):
        items = self.q_table.selectedItems()
        if not items:
            return
        row = items[0].row()
        qid = int(self.q_table.item(row, 0).text())
        self.current_question_id = qid

        q = self.db.execute_query("SELECT * FROM question_bank WHERE id=?", (qid,), fetch="one")
        if not q:
            return

        self.content_text.blockSignals(True)
        self.content_text.setPlainText(q["content_text"] or "")
        self.content_text.blockSignals(False)

        # reset đáp án
        self.correct_group.setExclusive(False)
        for b in self.correct_group.buttons():
            b.setChecked(False)
        self.correct_group.setExclusive(True)
        for label, ent in self.option_entries.items():
            ent.blockSignals(True)
            ent.clear()
            ent.blockSignals(False)

        opts = json.loads(q["options"] or "[]")
        correct = q["correct"] if q["correct"] else ""
        if correct and correct in [b.text() for b in self.correct_group.buttons()]:
            for b in self.correct_group.buttons():
                if b.text() == correct:
                    b.setChecked(True)
                    break

        # Lưu ý: trong DB hiện tại options lưu dạng {"text": "A. ...", "is_correct": bool}
        for opt in opts:
            text = opt.get("text", "")
            if "." not in text:
                continue
            label, content = text.split(".", 1)
            label = label.strip().upper()
            ent = self.option_entries.get(label)
            if ent:
                ent.setText(content.strip())

    # ====================== Save/Update/Delete ======================
    def _current_tree_id(self) -> int | None:
        items = self.tree.selectedItems()
        if not items:
            return None
        return items[0].data(0, Qt.UserRole)

    def save_question(self):
        tree_id = self._current_tree_id()
        if not tree_id:
            QtWidgets.QMessageBox.warning(self, "Chưa chọn thư mục", "Vui lòng chọn vị trí lưu trong cây.")
            return

        content = self.content_text.toPlainText().strip()
        # tìm radio đúng
        correct = ""
        for b in self.correct_group.buttons():
            if b.isChecked():
                correct = b.text()
                break

        opts = []
        for label, ent in self.option_entries.items():
            t = ent.text().strip()
            if t:
                opts.append({"text": f"{label}. {t}", "is_correct": (label == correct)})

        if not content or not correct or not opts:
            QtWidgets.QMessageBox.warning(self, "Thiếu dữ liệu", "Cần nhập đầy đủ nội dung và đáp án.")
            return

        try:
            if self.current_question_id:
                self.db.execute_query(
                    "UPDATE question_bank SET content_text=?, options=?, correct=?, tree_id=? WHERE id=?",
                    (content, json.dumps(opts, ensure_ascii=False), correct, tree_id, self.current_question_id)
                )
                QtWidgets.QMessageBox.information(self, "Cập nhật", "Đã cập nhật câu hỏi.")
            else:
                self.db.execute_query(
                    "INSERT INTO question_bank(content_text, options, correct, tree_id) VALUES (?,?,?,?)",
                    (content, json.dumps(opts, ensure_ascii=False), correct, tree_id)
                )
                QtWidgets.QMessageBox.information(self, "Thêm mới", "Đã lưu câu hỏi mới.")

            # reload danh sách
            rows = self.db.execute_query("SELECT * FROM question_bank WHERE tree_id=?", (tree_id,), fetch="all") or []
            self._load_question_rows(rows)
            self.clear_question_form()

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi CSDL", f"{e}")

    def clear_question_form(self):
        self.current_question_id = None
        self.content_text.clear()
        self.correct_group.setExclusive(False)
        for b in self.correct_group.buttons():
            b.setChecked(False)
        self.correct_group.setExclusive(True)
        for ent in self.option_entries.values():
            ent.clear()

    def delete_question(self):
        if not self.current_question_id:
            QtWidgets.QMessageBox.warning(self, "Chưa chọn", "Vui lòng chọn câu hỏi để xoá.")
            return
        if QtWidgets.QMessageBox.question(self, "Xác nhận", "Bạn có chắc muốn xoá câu hỏi này?") != QtWidgets.QMessageBox.Yes:
            return
        try:
            self.db.execute_query("DELETE FROM question_bank WHERE id=?", (self.current_question_id,))
            self.clear_question_form()
            tree_id = self._current_tree_id()
            if tree_id:
                rows = self.db.execute_query("SELECT * FROM question_bank WHERE tree_id=?", (tree_id,), fetch="all") or []
                self._load_question_rows(rows)
            QtWidgets.QMessageBox.information(self, "Đã xoá", "Câu hỏi đã được xoá.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi CSDL", f"{e}")

    # ====================== Path helpers ======================
    def get_tree_path(self, tree_id: int) -> List[dict]:
        path = []
        while tree_id:
            row = self.db.execute_query(
                "SELECT id, parent_id, name, level FROM exercise_tree WHERE id=?",
                (tree_id,), fetch="one"
            )
            if row:
                path.insert(0, row)
                tree_id = row["parent_id"]
            else:
                break
        return path

    # ====================== Search & Filters ======================
    def get_all_subtree_ids(self, root_id: int) -> List[int]:
        ids = [root_id]
        children = self.db.execute_query("SELECT id FROM exercise_tree WHERE parent_id=?", (root_id,), fetch="all") or []
        for c in children:
            ids.extend(self.get_all_subtree_ids(c["id"]))
        return ids

    def search_questions(self):
        keyword = (self.search_edit.text() or "").strip().lower()
        if not keyword:
            self.on_tree_select()
            return

        items = self.tree.selectedItems()
        if not items:
            QtWidgets.QMessageBox.warning(self, "Chưa chọn", "Hãy chọn thư mục để tìm trong đó.")
            return

        root_id = items[0].data(0, Qt.UserRole)
        all_ids = self.get_all_subtree_ids(root_id)
        if not all_ids:
            return

        placeholders = ",".join(["?"] * len(all_ids))
        query = f"SELECT * FROM question_bank WHERE tree_id IN ({placeholders})"
        rows = self.db.execute_query(query, tuple(all_ids), fetch="all") or []

        # filter theo keyword trong content_text
        rows = [r for r in rows if keyword in (r["content_text"] or "").lower()]
        self._load_question_rows(rows)

    def load_available_subjects(self):
        rows = self.db.execute_query(
            "SELECT DISTINCT name FROM exercise_tree WHERE level='Môn' ORDER BY name ASC",
            fetch="all"
        ) or []
        self.subject_cb.blockSignals(True); self.subject_cb.clear(); self.subject_cb.addItem("")
        for r in rows:
            self.subject_cb.addItem(r["name"])
        self.subject_cb.blockSignals(False)

    def load_available_grades(self):
        rows = self.db.execute_query(
            "SELECT DISTINCT name FROM exercise_tree WHERE level='Lớp' ORDER BY name ASC",
            fetch="all"
        ) or []
        self.grade_cb.blockSignals(True); self.grade_cb.clear(); self.grade_cb.addItem("")
        for r in rows:
            self.grade_cb.addItem(r["name"])
        self.grade_cb.blockSignals(False)

    def load_available_topics(self):
        subject = self.subject_cb.currentText().strip()
        grade = self.grade_cb.currentText().strip()
        if not subject or not grade:
            self.topic_cb.clear(); self.type_cb.clear()
            return

        rows = self.db.execute_query("""
            SELECT name FROM exercise_tree 
            WHERE level='Chủ đề' AND parent_id IN (
                SELECT id FROM exercise_tree 
                WHERE name=? AND level='Lớp' AND parent_id IN (
                    SELECT id FROM exercise_tree WHERE name=? AND level='Môn'
                )
            )
        """, (grade, subject), fetch="all") or []
        self.topic_cb.blockSignals(True); self.topic_cb.clear(); self.topic_cb.addItem("")
        for r in rows:
            self.topic_cb.addItem(r["name"])
        self.topic_cb.blockSignals(False)

        self.load_available_types()  # reset types theo topic mới

    def load_available_types(self):
        topic = self.topic_cb.currentText().strip()
        if not topic:
            self.type_cb.clear()
            return
        rows = self.db.execute_query("""
            SELECT name FROM exercise_tree
            WHERE level='Dạng' AND parent_id IN (
                SELECT id FROM exercise_tree WHERE level='Chủ đề' AND name=?
            )
        """, (topic,), fetch="all") or []
        self.type_cb.blockSignals(True); self.type_cb.clear(); self.type_cb.addItem("")
        for r in rows:
            self.type_cb.addItem(r["name"])
        self.type_cb.blockSignals(False)

    def filter_by_combobox(self):
        subject = self.subject_cb.currentText().strip()
        grade = self.grade_cb.currentText().strip()
        topic = self.topic_cb.currentText().strip()
        q_type = self.type_cb.currentText().strip()
        level = self.level_cb.currentText().strip()

        conditions = []
        params: List[object] = []

        if subject and grade:
            conditions.append("""
                EXISTS (
                    SELECT 1 FROM exercise_tree s 
                    WHERE s.id = q.tree_id AND s.level='Mức độ'
                      AND s.parent_id IN (
                          SELECT id FROM exercise_tree WHERE level='Dạng' AND parent_id IN (
                              SELECT id FROM exercise_tree WHERE level='Chủ đề' AND parent_id IN (
                                  SELECT id FROM exercise_tree WHERE level='Lớp' AND name=? AND parent_id IN (
                                      SELECT id FROM exercise_tree WHERE level='Môn' AND name=?
                                  )
                              )
                          )
                      )
                )
            """)
            params.extend([grade, subject])
        elif subject and not grade:
            conditions.append("""
                EXISTS (
                    SELECT 1 FROM exercise_tree s 
                    WHERE s.id = q.tree_id AND s.level='Mức độ'
                      AND s.parent_id IN (
                          SELECT id FROM exercise_tree WHERE level='Dạng' AND parent_id IN (
                              SELECT id FROM exercise_tree WHERE level='Chủ đề' AND parent_id IN (
                                  SELECT id FROM exercise_tree WHERE level='Lớp' AND parent_id IN (
                                      SELECT id FROM exercise_tree WHERE level='Môn' AND name=?
                                  )
                              )
                          )
                      )
                )
            """)
            params.append(subject)
        elif grade and not subject:
            conditions.append("""
                EXISTS (
                    SELECT 1 FROM exercise_tree s 
                    WHERE s.id = q.tree_id AND s.level='Mức độ'
                      AND s.parent_id IN (
                          SELECT id FROM exercise_tree WHERE level='Dạng' AND parent_id IN (
                              SELECT id FROM exercise_tree WHERE level='Chủ đề' AND parent_id IN (
                                  SELECT id FROM exercise_tree WHERE level='Lớp' AND name=?
                              )
                          )
                      )
                )
            """)
            params.append(grade)

        if topic:
            conditions.append("""
                EXISTS (
                    SELECT 1 FROM exercise_tree s 
                    WHERE s.id = q.tree_id AND s.level='Mức độ'
                      AND s.parent_id IN (
                          SELECT id FROM exercise_tree WHERE level='Dạng' AND parent_id IN (
                              SELECT id FROM exercise_tree WHERE level='Chủ đề' AND name=?
                          )
                      )
                )
            """)
            params.append(topic)

        if q_type:
            conditions.append("""
                EXISTS (
                    SELECT 1 FROM exercise_tree s 
                    WHERE s.id = q.tree_id AND s.level='Mức độ'
                      AND s.parent_id IN (
                          SELECT id FROM exercise_tree WHERE level='Dạng' AND name=?
                      )
                )
            """)
            params.append(q_type)

        if level:
            conditions.append("""
                EXISTS (
                    SELECT 1 FROM exercise_tree s 
                    WHERE s.id = q.tree_id AND s.name=? AND s.level='Mức độ'
                )
            """)
            params.append(level)

        where_clause = " AND ".join([c.strip() for c in conditions]) if conditions else "1=1"
        query = f"SELECT q.* FROM question_bank q WHERE {where_clause}"

        rows = self.db.execute_query(query, tuple(params), fetch="all") or []
        self._load_question_rows(rows)

    # ====================== Import from Word ======================
    def import_from_word(self):
        try:
            from docx import Document
        except Exception:
            QtWidgets.QMessageBox.critical(self, "Thiếu thư viện", "Vui lòng cài đặt python-docx (pip install python-docx).")
            return

        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Chọn file Word chứa câu hỏi", "", "Word files (*.docx)"
        )
        if not file_path:
            return

        tree_id = self._current_tree_id()
        if not tree_id:
            QtWidgets.QMessageBox.warning(self, "Thiếu thư mục", "Vui lòng chọn nơi lưu câu hỏi (trong cây bên trái).")
            return

        try:
            doc = Document(file_path)
            questions = []
            current = None
            for para in doc.paragraphs:
                line = para.text.strip()
                if not line:
                    continue
                if line.lower().startswith("câu hỏi:"):
                    if current:
                        questions.append(current)
                    current = {"content": line[8:].strip(), "options": [], "answer": ""}
                elif any(line.startswith(f"{opt}.") for opt in "ABCDE"):
                    if current:
                        current["options"].append(line.strip())
                elif line.lower().startswith("đáp án:"):
                    if current:
                        current["answer"] = line.split(":")[-1].strip().upper()
            if current:
                questions.append(current)

            inserted = 0
            for q in questions:
                content = q["content"]
                answer = q["answer"]
                raw_options = q["options"]
                if not content or not answer or not raw_options:
                    continue

                opts_data = []
                for opt in raw_options:
                    if "." not in opt:
                        continue
                    label, text = opt.split(".", 1)
                    label = label.strip().upper()
                    if label not in "ABCDE":
                        continue
                    is_correct = (label == answer)
                    opts_data.append({
                        "text": f"{label}. {text.strip()}",
                        "is_correct": is_correct
                    })
                if not opts_data:
                    continue

                self.db.execute_query(
                    "INSERT INTO question_bank(content_text, options, correct, tree_id) VALUES (?,?,?,?)",
                    (content, json.dumps(opts_data, ensure_ascii=False), answer, tree_id)
                )
                inserted += 1

            # reload view
            rows = self.db.execute_query("SELECT * FROM question_bank WHERE tree_id=?", (tree_id,), fetch="all") or []
            self._load_question_rows(rows)
            QtWidgets.QMessageBox.information(self, "Thành công", f"Đã thêm {inserted} câu hỏi từ file Word.")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể xử lý file: {e}")

    # ====================== Misc ======================
    def toggle_tree_panel(self):
        # ẩn/hiện panel trái
        w = self.tree.parentWidget()
        w.setVisible(not w.isVisible())

    def open_tree_manager(self):
        # Cố gắng mở bản Qt nếu bạn có sẵn; nếu không, thông báo.
        try:
            from ui_qt.windows.exercise_tree_manager_qt import ExerciseTreeManagerQt  # type: ignore
            dlg = ExerciseTreeManagerQt(self.db, parent=self)
            dlg.show()
        except Exception:
            QtWidgets.QMessageBox.information(
                self, "Thông tin",
                "Chưa có cửa sổ 'Quản lý cây' bản PySide6. Bạn có thể mở sau."
            )
