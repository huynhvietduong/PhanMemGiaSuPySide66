# ui_qt/windows/create_test_window_qt.py
from __future__ import annotations
import os, json, re, sys
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGroupBox, QGridLayout, QLabel,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QLineEdit, QMessageBox, QSizePolicy
)

# ReportLab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

class CreateTestWindowQt(QWidget):
    """
    Port PySide6 của CreateTestWindow (Tkinter).
    - Lọc câu hỏi theo chủ đề/độ khó
    - Chọn câu hỏi và xuất PDF + trang đáp án
    """
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setWindowTitle("Tạo Đề thi từ Ngân hàng câu hỏi")
        self.resize(1100, 700)

        root = QHBoxLayout(self)

        # ===== Left: Bộ lọc + bảng available =====
        left_box = QVBoxLayout()
        filter_group = QGroupBox("Bộ lọc câu hỏi")
        grid = QGridLayout(filter_group)

        grid.addWidget(QLabel("Chủ đề:"), 0, 0)
        self.subject_combo = QComboBox()
        self.subject_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        grid.addWidget(self.subject_combo, 0, 1)

        grid.addWidget(QLabel("Độ khó:"), 0, 2)
        self.difficulty_combo = QComboBox()
        self.difficulty_combo.addItems(["", "1", "2", "3", "4", "5"])
        self.difficulty_combo.setFixedWidth(80)
        grid.addWidget(self.difficulty_combo, 0, 3)

        btn_filter = QPushButton("Lọc")
        btn_filter.clicked.connect(self.apply_filter)
        grid.addWidget(btn_filter, 0, 4)

        left_box.addWidget(filter_group)

        available_group = QGroupBox("Câu hỏi có sẵn")
        vbox_avail = QVBoxLayout(available_group)
        self.available_table = QTableWidget(0, 3)
        self.available_table.setHorizontalHeaderLabels(["ID", "Chủ đề", "Độ khó"])
        self.available_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.available_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.available_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.available_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.available_table.setSelectionMode(QTableWidget.ExtendedSelection)
        vbox_avail.addWidget(self.available_table)
        left_box.addWidget(available_group)

        # ===== Middle: control buttons =====
        mid_box = QVBoxLayout()
        mid_box.addStretch(1)
        btn_add = QPushButton(">>")
        btn_add.clicked.connect(self.add_question)
        btn_remove = QPushButton("<<")
        btn_remove.clicked.connect(self.remove_question)
        for b in (btn_add, btn_remove):
            b.setFixedWidth(70)
            mid_box.addWidget(b)
        mid_box.addStretch(1)

        # ===== Right: Thông tin đề + bảng selected + Export =====
        right_box = QVBoxLayout()

        info_group = QGroupBox("Thông tin đề thi")
        grid_info = QGridLayout(info_group)
        grid_info.addWidget(QLabel("Tiêu đề:"), 0, 0)
        self.title_edit = QLineEdit("BÀI KIỂM TRA")
        grid_info.addWidget(self.title_edit, 0, 1)
        grid_info.addWidget(QLabel("Thời gian:"), 1, 0)
        self.time_edit = QLineEdit("45 phút")
        self.time_edit.setFixedWidth(120)
        grid_info.addWidget(self.time_edit, 1, 1)
        right_box.addWidget(info_group)

        selected_group = QGroupBox("Câu hỏi đã chọn")
        vbox_sel = QVBoxLayout(selected_group)
        self.selected_table = QTableWidget(0, 2)
        self.selected_table.setHorizontalHeaderLabels(["ID", "Chủ đề"])
        self.selected_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.selected_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.selected_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.selected_table.setSelectionMode(QTableWidget.ExtendedSelection)
        vbox_sel.addWidget(self.selected_table)
        right_box.addWidget(selected_group, 1)

        btn_export = QPushButton("TẠO VÀ XUẤT FILE PDF")
        btn_export.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_export.clicked.connect(self.generate_pdf)
        right_box.addWidget(btn_export)

        # Compose layout
        root.addLayout(left_box, 1)
        root.addLayout(mid_box)
        root.addLayout(right_box, 1)

        # Data
        self.load_subjects()
        self.apply_filter()

    # ---------- Data helpers ----------
    def load_subjects(self):
        rows = self.db.execute_query(
            "SELECT DISTINCT chu_de FROM question_bank ORDER BY chu_de", fetch='all'
        ) or []
        self.subject_combo.clear()
        self.subject_combo.addItem("")
        for r in rows:
            self.subject_combo.addItem(r['chu_de'])

    def apply_filter(self):
        sql = "SELECT id, chu_de, do_kho FROM question_bank WHERE 1=1"
        params: List[object] = []
        subj = self.subject_combo.currentText().strip()
        if subj:
            sql += " AND chu_de = ?"
            params.append(subj)
        diff = self.difficulty_combo.currentText().strip()
        if diff:
            sql += " AND do_kho = ?"
            params.append(int(diff))
        sql += " ORDER BY id DESC"

        rows = self.db.execute_query(sql, tuple(params), fetch='all') or []
        self.available_table.setRowCount(0)
        for row in rows:
            r = self.available_table.rowCount()
            self.available_table.insertRow(r)
            self.available_table.setItem(r, 0, QTableWidgetItem(str(row['id'])))
            self.available_table.setItem(r, 1, QTableWidgetItem(row['chu_de']))
            self.available_table.setItem(r, 2, QTableWidgetItem(str(row['do_kho'])))

    def _selected_rows(self, table: QTableWidget) -> List[int]:
        rows = set(idx.row() for idx in table.selectedIndexes())
        return sorted(rows)

    def _find_row_in_selected_by_id(self, qid: str) -> int:
        for r in range(self.selected_table.rowCount()):
            if self.selected_table.item(r, 0) and self.selected_table.item(r, 0).text() == qid:
                return r
        return -1

    def add_question(self):
        for r in self._selected_rows(self.available_table):
            qid = self.available_table.item(r, 0).text()
            if self._find_row_in_selected_by_id(qid) != -1:
                continue
            chu_de = self.available_table.item(r, 1).text()
            rr = self.selected_table.rowCount()
            self.selected_table.insertRow(rr)
            self.selected_table.setItem(rr, 0, QTableWidgetItem(qid))
            self.selected_table.setItem(rr, 1, QTableWidgetItem(chu_de))

    def remove_question(self):
        rows = self._selected_rows(self.selected_table)
        for r in reversed(rows):
            self.selected_table.removeRow(r)

    # ---------- Export PDF ----------
    def generate_pdf(self):
        ids: List[str] = []
        for r in range(self.selected_table.rowCount()):
            ids.append(self.selected_table.item(r, 0).text())
        if not ids:
            QMessageBox.warning(self, "Thông báo", "Chưa có câu hỏi nào trong đề thi.")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Lưu file đề thi", "", "PDF Documents (*.pdf)"
        )
        if not save_path:
            return

        try:
            # 1) Định vị font DejaVu
            # file này nằm ở ui_qt/windows/..., project_dir là 1 cấp trên thư mục ui_qt
            ui_qt_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            project_dir = os.path.dirname(ui_qt_dir)
            font_dir = os.path.join(project_dir, "assets", "fonts")
            font_reg = os.path.join(font_dir, "DejaVuSans.ttf")
            font_bold = os.path.join(font_dir, "DejaVuSans-Bold.ttf")
            if not (os.path.exists(font_reg) and os.path.exists(font_bold)):
                QMessageBox.critical(self, "Lỗi", f"Không tìm thấy font tại:\n{font_dir}")
                return

            pdfmetrics.registerFont(TTFont("DejaVu", font_reg))
            pdfmetrics.registerFont(TTFont("DejaVu-Bold", font_bold))

            # 2) Khởi tạo tài liệu
            doc = SimpleDocTemplate(
                save_path, pagesize=A4,
                rightMargin=40, leftMargin=40, topMargin=60, bottomMargin=40
            )
            styles = getSampleStyleSheet()
            styles.add(ParagraphStyle(
                name="ExamTitle", fontName="DejaVu-Bold", fontSize=18, alignment=1, spaceAfter=12
            ))
            styles.add(ParagraphStyle(
                name="Normal_DejaVu", fontName="DejaVu", fontSize=12, leading=15
            ))
            styles.add(ParagraphStyle(
                name="QuestionNum", fontName="DejaVu-Bold", fontSize=12, spaceBefore=8, leading=14
            ))

            flowables = []
            # 3) Tiêu đề
            flowables.append(Paragraph(self.title_edit.text(), styles["ExamTitle"]))
            flowables.append(Paragraph(f"Thời gian làm bài: {self.time_edit.text()}", styles["Normal_DejaVu"]))
            flowables.append(Spacer(1, 12))

            answer_key = []

            # 4) Duyệt câu hỏi
            for idx, qid in enumerate(ids, start=1):
                row = self.db.execute_query(
                    "SELECT * FROM question_bank WHERE id=?", (qid,), fetch='one'
                )
                if not row:
                    continue

                # Nội dung câu hỏi (text hoặc ảnh)
                content_text = row["content_text"] or ""
                content_img = row["content_image"] or ""
                if content_text.strip():
                    body = re.sub(r"^Câu\s*\d+\s*:\s*", "", content_text).strip()
                    flowables.append(Paragraph(f"<b>Câu {idx}:</b> {body}", styles["Normal_DejaVu"]))
                    flowables.append(Spacer(1, 6))
                elif content_img and os.path.exists(content_img):
                    flowables.append(Image(content_img, width=400, height=0))

                # Phương án
                opts = json.loads(row["options"] or "[]")
                table_data = []
                labels = ["A", "B", "C", "D", "E"]
                for j, opt in enumerate(opts):
                    lbl = labels[j]
                    txt = (opt.get("text") or "").strip()
                    img = opt.get("image_path") or ""

                    cell_label = Paragraph(f"<b>{lbl}.</b>", styles["Normal_DejaVu"])
                    if txt:
                        cell_content = Paragraph(txt, styles["Normal_DejaVu"])
                    elif img and os.path.exists(img):
                        cell_content = Image(img, width=200, height=0)
                    else:
                        cell_content = Paragraph("(Không có nội dung)", styles["Normal_DejaVu"])

                    table_data.append([cell_label, cell_content])
                    if opt.get("is_correct"):
                        answer_key.append((idx, lbl))

                tbl = Table(table_data, colWidths=[20, 420])
                tbl.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]))
                flowables.append(tbl)
                flowables.append(Spacer(1, 12))

            # 5) Trang ĐÁP ÁN
            flowables.append(PageBreak())
            flowables.append(Paragraph("ĐÁP ÁN", styles["ExamTitle"]))
            ans_cells = [Paragraph(f"{num}-{lbl}", styles["Normal_DejaVu"]) for num, lbl in answer_key]
            rows = [ans_cells[i:i+5] for i in range(0, len(ans_cells), 5)]
            if not rows:
                rows = [[Paragraph("(Chưa có đáp án)", styles["Normal_DejaVu"])]]
            ans_tbl = Table(rows, colWidths=[80]*max(1, len(rows[0])))
            ans_tbl.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]))
            flowables.append(ans_tbl)

            # 6) Build
            doc.build(flowables)

            QMessageBox.information(self, "Thành công", f"Đã xuất file PDF:\n{save_path}")
            # mở file (Windows)
            try:
                os.startfile(save_path)
            except Exception:
                pass

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể tạo file PDF:\n{e}")
