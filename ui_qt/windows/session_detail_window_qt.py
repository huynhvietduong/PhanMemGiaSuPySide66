# ui_qt/windows/session_detail_window_qt.py
from __future__ import annotations
import os, re, time, platform, shutil, subprocess, json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QScrollArea, QWidget,
    QComboBox, QPushButton, QPlainTextEdit, QMessageBox, QFileDialog
)

def _to_date_str(d) -> str:
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%d")
    # allow 'YYYY-MM-DD'
    try:
        return datetime.strptime(str(d), "%Y-%m-%d").strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


# Lớp controller xử lý logic nghiệp vụ
class SessionController:
    """Controller quản lý logic nghiệp vụ cho session"""

    def __init__(self, db_manager):
        self.db = db_manager

    # Xử lý lưu điểm danh học sinh
    def save_attendance_data(self, students_status: Dict, group_id: int, session_date: str, makeup_joiners: List):
        """Lưu dữ liệu điểm danh học sinh"""
        for sid, widget in students_status.items():
            # Bỏ qua các em đã xử lý học bù
            if any(s["student_id"] == sid for s in makeup_joiners):
                continue

            status = widget.currentText()
            make_up_status = "Chưa sắp xếp" if "Nghỉ" in status else ""

            self.db.execute_query(
                "INSERT INTO attendance (student_id, group_id, session_date, status, make_up_status) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(student_id, group_id, session_date) DO UPDATE SET "
                "status = excluded.status, make_up_status = excluded.make_up_status",
                (sid, group_id, session_date, status, make_up_status)
            )

    # Xử lý lưu nhật ký buổi học
    def save_session_log_data(self, group_id: int, session_date: str, topic: str, homework: str):
        """Lưu nhật ký buổi học"""
        self.db.execute_query(
            "INSERT OR REPLACE INTO session_logs (group_id, session_date, topic, homework) "
            "VALUES (?, ?, ?, ?)",
            (group_id, session_date, topic, homework)
        )
class SessionDetailWindowQt(QDialog):
    """
    PySide6 port của SessionDetailWindow (Tkinter)
    - Điểm danh học sinh (cả học bù)
    - Ghi nhật ký buổi học (topic/homework)
    - Gắn & mở file bài giảng
    - Mở bảng vẽ / Paint (Windows)
    - Mở cửa sổ 'Đánh giá năng lực'
    """
    def __init__(self,parent: QtWidgets.QWidget,db_manager,session_date,group_id: Optional[int] = None,group_name: Optional[str] = None,makeup_info: Optional[List[Dict[str, Any]]] = None):
        super().__init__(parent)
        self.setWindowTitle("Chi tiết Buổi học")
        self.resize(900, 680)
        self.setModal(True)

        self.db = db_manager
        self.controller = SessionController(db_manager)
        self.is_makeup_session = makeup_info is not None
        self.session_date = _to_date_str(session_date)
        self.group_id = group_id
        self.group_name = group_name or ""
        self.makeup_list: List[Dict[str, Any]] = makeup_info or []
        self.session_id: Optional[int] = None
        self.student_status: Dict[int, QComboBox] = {}  # student_id -> widget chọn trạng thái

        root = QVBoxLayout(self)

        # ====== Thông tin chung ======
        box_info = QGroupBox("Thông tin chung ℹ️")
        info_l = QVBoxLayout(box_info)
        if self.is_makeup_session:
            info_l.addWidget(QLabel(f"Buổi học bù cho {len(self.makeup_list)} học sinh"))
            info_l.addWidget(QLabel(f"Ngày: {self.session_date}"))
            self.setWindowTitle("Chi tiết Buổi học bù")
        else:
            last = self.db.execute_query(
                "SELECT topic FROM session_logs WHERE group_id=? AND session_date < ? "
                "ORDER BY session_date DESC LIMIT 1",
                (self.group_id, self.session_date), fetch="one"
            )
            info_l.addWidget(QLabel(f"Nhóm: {self.group_name}"))
            info_l.addWidget(QLabel(f"Ngày: {self.session_date}"))
            last_topic = (last[0] if isinstance(last, (list, tuple)) else (last["topic"] if last else None)) if last else None
            lab = QLabel(f"Buổi trước đã học: {last_topic or 'Chưa có'}")
            lab.setStyleSheet("color: #1976d2;")
            info_l.addWidget(lab)
        root.addWidget(box_info)

        # ====== Điểm danh ======
        box_att = QGroupBox("Điểm danh ✅")
        att_l = QVBoxLayout(box_att)

        # danh sách hàng điểm danh trong scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        att_container = QWidget()
        self.att_rows = QVBoxLayout(att_container)
        self.att_rows.setContentsMargins(6, 6, 6, 6)
        scroll.setWidget(att_container)
        att_l.addWidget(scroll)

        # makeup joiners (với buổi thường)
        self.makeup_joiners: List[Dict[str, Any]] = []
        if self.is_makeup_session:
            for info in self.makeup_list:
                self._add_attendance_row(info["student_id"], info["student_name"])
        else:
            self.makeup_joiners = self._get_makeup_joiners()
            students = self.db.execute_query(
                "SELECT id, name FROM students WHERE group_id = ?",
                (self.group_id,), fetch="all"
            ) or []
            if not students and not self.makeup_joiners:
                self.att_rows.addWidget(QLabel("Chưa có học sinh nào trong nhóm này."))
            else:
                for sid, sname in students:
                    self._add_attendance_row(sid, sname)
                if self.makeup_joiners:
                    self.att_rows.addWidget(self._hr())
                    for mk in self.makeup_joiners:
                        self._add_attendance_row(mk["student_id"], f"[Bù] {mk['student_name']}")
        root.addWidget(box_att, 1)

        # ====== Nhật ký buổi học ======
        box_log = QGroupBox("Nhật ký buổi dạy hôm nay ✍️")
        log_l = QVBoxLayout(box_log)
        log_l.addWidget(QLabel("Chủ đề đã dạy:"))
        self.topic_text = QPlainTextEdit()
        self.topic_text.setPlaceholderText("Ví dụ: Ôn tập phương trình bậc hai; bất đẳng thức Cauchy…")
        self.topic_text.setMaximumBlockCount(300)
        log_l.addWidget(self.topic_text)
        log_l.addWidget(QLabel("Bài tập về nhà:"))
        self.homework_text = QPlainTextEdit()
        self.homework_text.setMaximumBlockCount(200)
        log_l.addWidget(self.homework_text)

        # Nút 'Thêm file bài giảng' + list file đã gắn
        btn_add_file = QPushButton("📂 Thêm file bài giảng")
        btn_add_file.clicked.connect(self._choose_lesson_file)
        log_l.addWidget(btn_add_file)

        self.files_box = QGroupBox("📎 File bài giảng đã gắn:")
        self.files_l = QVBoxLayout(self.files_box)
        log_l.addWidget(self.files_box)

        root.addWidget(box_log)

        # ====== Buttons ======
        btn_row = QHBoxLayout()
        if not self.is_makeup_session:
            btn_skill = QPushButton("Đánh giá năng lực")
            btn_skill.clicked.connect(self._open_skill_rating)
            btn_row.addWidget(btn_skill)

        btn_board = QPushButton("🖍️ Bảng Vẽ Bài Giảng")
        btn_board.clicked.connect(self._open_board_chooser)
        btn_row.addWidget(btn_board)

        btn_save = QPushButton("Lưu & Kết thúc buổi học")
        btn_save.clicked.connect(self._save_session)
        btn_row.addWidget(btn_save)

        btn_close = QPushButton("Đóng")
        btn_close.clicked.connect(self.reject)
        btn_row.addWidget(btn_close)

        root.addLayout(btn_row)
        self._ensure_session_row()
        # ====== Khởi tạo session_id nếu đã có log ======
        if not self.is_makeup_session:
            row = self.db.execute_query(
                "SELECT id FROM session_logs WHERE group_id = ? AND session_date = ?",
                (self.group_id, self.session_date), fetch="one"
            )
            if row:
                self.session_id = row["id"] if isinstance(row, dict) else row[0]

        self._load_today_log()
        self._render_lesson_files()

    # ---------- helpers ----------
    def _hr(self) -> QWidget:
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        return line

    def _add_attendance_row(self, student_id: int, display_name: str):
        row = QHBoxLayout()
        lab = QLabel(display_name)
        lab.setMinimumWidth(240)
        row.addWidget(lab)

        cb = QComboBox()
        cb.addItems(["Có mặt", "Nghỉ có phép", "Nghỉ không phép"])
        cb.setCurrentIndex(0)
        row.addWidget(cb)
        self.student_status[student_id] = cb

        wrap = QWidget()
        wrap.setLayout(row)
        self.att_rows.addWidget(wrap)

    def _get_makeup_joiners(self) -> List[Dict[str, Any]]:
        """Lấy danh sách học sinh học bù với truy vấn tối ưu"""
        if not self.group_id:
            return []

        # Sử dụng INNER JOIN thay vì JOIN và thêm ORDER BY
        query = """
        SELECT m.attendance_id, m.student_id, s.name 
        FROM makeup_sessions m 
        INNER JOIN students s ON m.student_id = s.id 
        WHERE m.host_group_id = ? AND m.session_date = ?
        ORDER BY s.name ASC
        """

        rows = self.db.execute_query(query, (self.group_id, self.session_date), fetch="all") or []

        # Xử lý kết quả một cách hiệu quả
        result = []
        for r in rows:
            att_id = r[0] if isinstance(r, (list, tuple)) else r["attendance_id"]
            sid = r[1] if isinstance(r, (list, tuple)) else r["student_id"]
            name = r[2] if isinstance(r, (list, tuple)) else r["name"]
            result.append({
                "attendance_id": att_id,
                "student_id": sid,
                "student_name": name
            })

        return result
    # ---------- load / save ----------

    def _load_today_log(self):
        def _get_val(row, key_or_idx, default=""):
            try:
                # sqlite3.Row hỗ trợ truy cập theo tên cột
                if hasattr(row, "keys"):
                    return row[key_or_idx]
                # tuple/list
                if isinstance(row, (list, tuple)):
                    return row[key_or_idx if isinstance(key_or_idx, int) else 0]
                # dict (phòng khi ở nơi khác bạn trả về dict)
                if isinstance(row, dict):
                    return row.get(key_or_idx, default)
            except Exception:
                pass
            return default
        group_id_for_log = self.group_id if not self.is_makeup_session else None
        if not group_id_for_log:
            return

        row = self.db.execute_query(
            "SELECT topic, homework FROM session_logs WHERE group_id = ? AND session_date = ?",
            (group_id_for_log, self.session_date),
            fetch='one'
        )

        if row:
            topic = _get_val(row, 'topic')  # hoặc index 0
            homework = _get_val(row, 'homework')  # hoặc index 1
            self.topic_text.setPlainText(topic or "")
            self.homework_text.setPlainText(homework or "")

    # Kiểm tra tính hợp lệ dữ liệu buổi học
    def _validate_session_data(self) -> bool:
        """Kiểm tra tính hợp lệ của dữ liệu buổi học trước khi lưu"""

        # Kiểm tra có ít nhất 1 học sinh được điểm danh
        if not self.student_status:
            QMessageBox.warning(self, "Thiếu dữ liệu", "Chưa có học sinh nào được điểm danh.")
            return False

        # Kiểm tra độ dài topic không quá 500 ký tự
        topic = self.topic_text.toPlainText().strip()
        if len(topic) > 500:
            QMessageBox.warning(self, "Dữ liệu quá dài", "Chủ đề không được vượt quá 500 ký tự.")
            return False

        # Kiểm tra độ dài homework không quá 1000 ký tự
        homework = self.homework_text.toPlainText().strip()
        if len(homework) > 1000:
            QMessageBox.warning(self, "Dữ liệu quá dài", "Bài tập về nhà không được vượt quá 1000 ký tự.")
            return False

        # Kiểm tra ngày học hợp lệ
        try:
            session_date = datetime.strptime(self.session_date, "%Y-%m-%d")
            if session_date > datetime.now():
                QMessageBox.warning(self, "Ngày không hợp lệ", "Không thể tạo buổi học trong tương lai.")
                return False
        except ValueError:
            QMessageBox.critical(self, "Lỗi ngày tháng", "Định dạng ngày không hợp lệ.")
            return False

        return True
    def _save_session(self, keep_open: bool = False) -> bool:
        """
        Lưu điểm danh + nhật ký buổi học.
        - keep_open=True: chỉ lưu và REFRESH, KHÔNG đóng cửa sổ (dùng khi chuẩn bị mở Bảng vẽ).
        - keep_open=False: lưu xong sẽ đóng cửa sổ như hành vi cũ.
        Trả về True nếu lưu thành công, ngược lại False.
        """
        try:
            # Validate dữ liệu trước khi lưu
            if not self._validate_session_data():
                return False
            # 1) Xử lý danh sách học bù (nếu là buổi bù hoặc buổi thường có học sinh học bù)
            list_to_process = self.makeup_list if self.is_makeup_session else self.makeup_joiners
            for mk in list_to_process:
                sid = mk["student_id"]
                status = self.student_status.get(sid).currentText() if sid in self.student_status else "Có mặt"
                original_att_id = mk.get("att_id") or mk.get("attendance_id")
                new_status = "Đã dạy bù" if status == "Có mặt" else "Vắng buổi bù"
                self.db.execute_query(
                    "UPDATE attendance SET make_up_status=? WHERE id=?",
                    (new_status, original_att_id)
                )
                self.db.execute_query(
                    "DELETE FROM makeup_sessions WHERE attendance_id=?",
                    (original_att_id,)
                )

            # 2) Điểm danh & ghi log cho buổi THƯỜNG
            if not self.is_makeup_session:
                for sid, widget in self.student_status.items():
                    # Bỏ qua các em đã xử lý học bù ở trên
                    if any(s["student_id"] == sid for s in self.makeup_joiners):
                        continue
                    status = widget.currentText()
                    make_up_status = "Chưa sắp xếp" if "Nghỉ" in status else ""
                    self.db.execute_query(
                        "INSERT INTO attendance (student_id, group_id, session_date, status, make_up_status) "
                        "VALUES (?, ?, ?, ?, ?) "
                        "ON CONFLICT(student_id, group_id, session_date) DO UPDATE SET "
                        "status = excluded.status, make_up_status = excluded.make_up_status",
                        (sid, self.group_id, self.session_date, status, make_up_status)
                    )

                topic = self.topic_text.toPlainText().strip()
                homework = self.homework_text.toPlainText().strip()
                self.db.execute_query(
                    "INSERT OR REPLACE INTO session_logs (group_id, session_date, topic, homework) "
                    "VALUES (?, ?, ?, ?)",
                    (self.group_id, self.session_date, topic, homework)
                )

                # Lấy/ cập nhật session_id ngay sau khi lưu để gắn file/bảng vẽ
                row = self.db.execute_query(
                    "SELECT id FROM session_logs WHERE group_id=? AND session_date=?",
                    (self.group_id, self.session_date), fetch="one"
                )
                if row:
                    self.session_id = row["id"] if isinstance(row, dict) else row[0]

            # 3) Thông báo & refresh các màn hình liên quan
            QtWidgets.QMessageBox.information(self, "Thành công", "Đã lưu thông tin buổi học.")

            if hasattr(self.parent(), "update_all_schedules"):
                try:
                    self.parent().update_all_schedules()
                except Exception:
                    pass

            if hasattr(self.parent(), "page_attendance") and hasattr(self.parent().page_attendance, "load_report"):
                try:
                    self.parent().page_attendance.load_report()
                except Exception:
                    pass

            # 4) Đóng hay giữ cửa sổ
            if not keep_open:
                self.accept()

            return True

        except Exception as e:
            # Xử lý lỗi chi tiết theo loại
            if "UNIQUE constraint failed" in str(e):
                QtWidgets.QMessageBox.warning(self, "Trùng lặp dữ liệu",
                                              "Dữ liệu buổi học này đã tồn tại. Vui lòng kiểm tra lại.")
            elif "database is locked" in str(e):
                QtWidgets.QMessageBox.critical(self, "Lỗi cơ sở dữ liệu",
                                               "Cơ sở dữ liệu đang bị khóa. Vui lòng thử lại sau.")
            elif "no such table" in str(e):
                QtWidgets.QMessageBox.critical(self, "Lỗi cấu trúc dữ liệu",
                                               "Cơ sở dữ liệu chưa được khởi tạo đúng cách.")
            else:
                QtWidgets.QMessageBox.critical(self, "Lỗi không xác định",
                                               f"Đã có lỗi khi lưu dữ liệu:\n{str(e)}\n\nVui lòng liên hệ hỗ trợ kỹ thuật.")
            return False

    # ---------- Lesson files ----------
    def _choose_lesson_file(self):
        if not self.session_id:
            QMessageBox.critical(self, "Chưa lưu buổi học", "Vui lòng lưu buổi học trước khi gắn file.")
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file bài giảng",
            "", "Tất cả (*.*);;PDF (*.pdf);;PowerPoint (*.pptx);;Word (*.docx);;EasiNote (*.enb);;OneNote (*.one)"
        )
        if file_path:
            self._save_lesson_file(file_path)

    def _save_lesson_file(self, file_path: str):
        """Lưu file bài giảng với kiểm tra bảo mật và validation"""
        try:
            # Kiểm tra file tồn tại và có thể đọc
            if not os.path.exists(file_path):
                raise FileNotFoundError("File không tồn tại")

            if not os.access(file_path, os.R_OK):
                raise PermissionError("Không có quyền đọc file")

            # Kiểm tra định dạng file cho phép
            allowed_extensions = {'.pdf', '.pptx', '.docx', '.enb', '.one', '.jpg', '.png', '.txt', '.ppt', '.xls',
                                  '.xlsx'}
            file_ext = Path(file_path).suffix.lower()
            if file_ext not in allowed_extensions:
                raise ValueError(f"Định dạng file {file_ext} không được hỗ trợ")

            # Kiểm tra kích thước file (tối đa 50MB)
            file_size = os.path.getsize(file_path)
            max_size = 50 * 1024 * 1024  # 50MB
            if file_size > max_size:
                raise ValueError(f"File quá lớn (tối đa 50MB). Kích thước hiện tại: {file_size // 1024 // 1024}MB")

            # Kiểm tra tên file hợp lệ
            file_name = Path(file_path).name
            if len(file_name) > 255:
                raise ValueError("Tên file quá dài (tối đa 255 ký tự)")

            file_type = Path(file_path).suffix
            title = Path(file_path).stem

            # Lưu vào database
            self.db.add_lesson_file(self.session_id, file_path, file_type, title, "")
            QMessageBox.information(self, "✅ Thành công", "Đã lưu file bài giảng vào CSDL.")
            self._render_lesson_files()

        except FileNotFoundError as e:
            QMessageBox.critical(self, "Lỗi file", f"File không tìm thấy: {str(e)}")
        except PermissionError as e:
            QMessageBox.critical(self, "Lỗi quyền truy cập", f"Không có quyền truy cập: {str(e)}")
        except ValueError as e:
            QMessageBox.warning(self, "Lỗi định dạng", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu file bài giảng: {e}")
    def _render_lesson_files(self):
        # clear
        for i in reversed(range(self.files_l.count())):
            w = self.files_l.itemAt(i).widget()
            if w:
                w.deleteLater()
            else:
                self.files_l.removeItem(self.files_l.itemAt(i))

        if not self.session_id:
            self.files_l.addWidget(QLabel("⛔ Chưa có file bài giảng."))
            return

        rows = self.db.execute_query(
            "SELECT id, file_path, title, file_type FROM lesson_files "
            "WHERE session_id = ? ORDER BY id DESC",
            (self.session_id,), fetch="all"
        ) or []

        if not rows:
            self.files_l.addWidget(QLabel("⛔ Chưa có file bài giảng."))
            return

        for r in rows:
            file_path = r["file_path"] if isinstance(r, dict) else r[1]
            title = (r["title"] if isinstance(r, dict) else r[2]) or os.path.basename(file_path)
            ftype = (r["file_type"] if isinstance(r, dict) else r[3] or "").lower()

            roww = QHBoxLayout()
            roww.addWidget(QLabel(title))
            open_btn = QPushButton("📂 Mở")
            open_btn.clicked.connect(lambda _, p=file_path: self._open_file(p))
            roww.addWidget(open_btn)

            if ftype == "board" or str(file_path).endswith(".board.json"):
                edit_btn = QPushButton("🖍️ Mở & Sửa")
                edit_btn.clicked.connect(lambda _, p=file_path: self._open_board(board_path=p))
                roww.addWidget(edit_btn)

            roww.addStretch(1)
            wrap = QWidget(); wrap.setLayout(roww)
            self.files_l.addWidget(wrap)

    def _open_file(self, file_path: str):
        if not os.path.exists(file_path):
            QMessageBox.critical(self, "Lỗi", f"File không tồn tại:\n{file_path}")
            return
        # mở theo hệ thống
        QtGui.QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))

    # ---------- Board chooser / Board / Paint ----------
    def _open_board_chooser(self):
        if not self.session_id:
            ok = self._save_session(keep_open=True)
            if not ok or not self.session_id:
                QtWidgets.QMessageBox.critical(self, "Chưa có buổi học",
                                               "Không thể mở Bảng vẽ do chưa lưu được buổi học.")
                return

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Chọn phần mềm bảng vẽ")
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("Chọn công cụ để mở:"))
        btn_default = QPushButton("Bảng vẽ mặc định")
        btn_paint = QPushButton("Paint (Windows)")
        btn_easinote = QPushButton("EasiNote")
        btn_word = QPushButton("Word")
        btn_onenote = QPushButton("OneNote")
        v.addWidget(btn_default); v.addWidget(btn_paint); v.addWidget(btn_easinote); v.addWidget(btn_word); v.addWidget(btn_onenote)

        btn_default.clicked.connect(lambda: (dlg.accept(), self._open_board()))
        btn_paint.clicked.connect(lambda: (dlg.accept(), self._launch_external_board("paint")))
        btn_easinote.clicked.connect(lambda: (dlg.accept(), self._launch_external_board("easinote")))
        btn_word.clicked.connect(lambda: (dlg.accept(), self._launch_external_board("word")))
        btn_onenote.clicked.connect(lambda: (dlg.accept(), self._launch_external_board("onenote")))

        cancel = QPushButton("Hủy"); cancel.clicked.connect(dlg.reject); v.addWidget(cancel)
        dlg.exec()

    def _lesson_dir(self) -> str:
        d = os.path.join(os.getcwd(), "data", "lessons", str(self.session_id))
        os.makedirs(d, exist_ok=True)
        return d

    def _compose_paint_filepath(self) -> tuple[str, str]:
        date_str = self.session_date
        group = self._sanitize_filename(self.group_name or "Nhom")
        topic = self._sanitize_filename((self.topic_text.toPlainText().strip().splitlines() or ["ChuDe"])[0])
        base = f"{group}+{topic}+{date_str}"
        lesson_dir = self._lesson_dir()
        candidate = os.path.join(lesson_dir, base + ".png")
        idx = 1
        while os.path.exists(candidate):
            candidate = os.path.join(lesson_dir, f"{base}({idx}).png")
            idx += 1
        title = Path(candidate).stem
        return candidate, title

    def _create_blank_png(self, path: str, width: int = 1400, height: int = 575, color=(255, 255, 255, 255)):
        import struct, zlib
        sig = b'\x89PNG\r\n\x1a\n'
        def chunk(typ: bytes, data: bytes) -> bytes:
            return struct.pack("!I", len(data)) + typ + data + struct.pack("!I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        ihdr = struct.pack("!IIBBBBB", width, height, 8, 6, 0, 0, 0)
        r, g, b, a = color
        pixel = bytes((r, g, b, a))
        row = b'\x00' + pixel * width
        raw = row * height
        idat = zlib.compress(raw, 9)
        png = sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', idat) + chunk(b'IEND', b'')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(png)

    def _launch_external_board(self, app_name: str):
        try:
            if app_name == "paint":
                if platform.system() != "Windows":
                    QMessageBox.critical(self, "Không hỗ trợ", "Paint chỉ khả dụng trên Windows.")
                    return
                paint_cmd = shutil.which("mspaint") or r"C:\Windows\System32\mspaint.exe"
                if not os.path.exists(paint_cmd):
                    QMessageBox.critical(self, "Không tìm thấy Paint", "Không tìm thấy mspaint trên máy.")
                    return
                target_path, title = self._compose_paint_filepath()
                if not os.path.exists(target_path):
                    self._create_blank_png(target_path)
                start_time = time.time()
                proc = subprocess.Popen([paint_cmd, target_path])
                # chờ đến khi Paint đóng rồi tự gắn vào DB
                self._poll_paint_and_attach(proc, target_path, title, start_time)
                return

            QMessageBox.information(self, "Chưa hỗ trợ", f"'{app_name}' sẽ được thêm ở bước tiếp theo.")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi mở ứng dụng", f"Không thể mở {app_name}:\n{e}")

    def _poll_paint_and_attach(self, proc, target_path: str, title: str, start_time: float):
        # dùng QTimer thay vì after()
        timer = QtCore.QTimer(self)
        timer.setInterval(700)

        def check():
            if proc.poll() is None:
                return  # vẫn đang mở
            timer.stop()
            ok = (
                os.path.exists(target_path)
                and os.path.getsize(target_path) > 0
                and os.path.getmtime(target_path) >= start_time
            )
            if not ok:
                QMessageBox.warning(self, "Không có thay đổi", "Không thấy file được lưu/chỉnh sửa trong Paint.")
                return
            self.db.add_lesson_file(self.session_id, target_path, Path(target_path).suffix, title, "")
            self._render_lesson_files()
            QMessageBox.information(self, "Thành công", f"Đã lưu và gắn file: {os.path.basename(target_path)}")

        timer.timeout.connect(check)
        timer.start()

    def _open_board(self, board_path: Optional[str] = None):
        if not self.session_id:
            QMessageBox.critical(self, "Chưa có buổi học", "Vui lòng lưu buổi học trước khi mở Bảng vẽ.")
            return
        lesson_dir = self._lesson_dir()

        # Ưu tiên phiên bản Qt (nếu có)
        try:
            from ui_qt.board.window import DrawingBoardWindowQt  # type: ignore
        except Exception:
            DrawingBoardWindowQt = None

        if DrawingBoardWindowQt is None:
            QMessageBox.information(self, "Thông tin", "Bảng vẽ Qt sẽ được bổ sung sau.")
            return

        def _on_saved(path: str, title: str):
            self.db.add_lesson_file(self.session_id, path, "board", title, "")
            self._render_lesson_files()

        # Fix: Tạo DrawingBoard độc lập để tránh xung đột modal
        win = DrawingBoardWindowQt(
            parent=None,  # Thay đổi từ self thành None
            group_name=self.group_name,
            session_date=self.session_date,
            session_id=self.session_id,
            lesson_dir=lesson_dir,
            board_path=board_path,
            on_saved=_on_saved
        )

        # Fix: Thêm window flags để đảm bảo hoạt động độc lập
        win.setWindowFlags(win.windowFlags() | Qt.Window)

        # Fix: Ẩn SessionDetailWindow tạm thời để tránh xung đột
        self.hide()

        # Fix: Xử lý khi đóng DrawingBoard - hiện lại SessionDetailWindow
        def on_board_closed():
            # Kiểm tra xem đối tượng còn tồn tại không trước khi gọi show()
            try:
                if not self.isVisible():
                    self.show()
                    self.raise_()
                    self.activateWindow()
            except RuntimeError:
                # Đối tượng đã bị xóa, bỏ qua
                pass

        win.destroyed.connect(on_board_closed)
        win.show()
        win.raise_()
        win.activateWindow()

    # Phương thức khôi phục cửa sổ một cách an toàn
    def _restore_window_safely(self):
        """Khôi phục hiển thị cửa sổ SessionDetail một cách an toàn sau khi đóng DrawingBoard"""
        try:
            # Kiểm tra xem đối tượng còn hợp lệ không
            if hasattr(self, 'isVisible') and not self.isVisible():
                self.show()
                self.raise_()
                self.activateWindow()
        except (RuntimeError, AttributeError):
            # Đối tượng đã bị xóa hoặc không hợp lệ, bỏ qua
            pass
    def _open_skill_rating(self):
        # lấy danh sách học sinh
        if self.is_makeup_session:
            students = [(i["student_id"], i["student_name"]) for i in self.makeup_list]
        else:
            students = self.db.execute_query(
                "SELECT id, name FROM students WHERE group_id=?",
                (self.group_id,), fetch="all"
            ) or []
        # tách chủ đề từ ô topic (phân tách , ;)
        raw = self.topic_text.toPlainText().strip()
        topics: List[str] = []
        for part in raw.replace(";", ",").split(","):
            if part.strip():
                topics.append(part.strip())

        try:
            from ui_qt.windows.skill_rating_window_qt import SkillRatingWindowQt  # type: ignore
        except Exception:
            QMessageBox.information(self, "Thông tin", "Cửa sổ Đánh giá năng lực (Qt) chưa sẵn sàng.")
            return

        dlg = SkillRatingWindowQt(self.db, students, default_topics=topics, parent=self)
        dlg.exec()

    def _ensure_session_row(self) -> None:
        """Đảm bảo có 1 dòng trong session_logs cho (group_id, session_date) và set self.session_id.
           Chỉ dùng cho buổi thường (không áp dụng buổi bù)."""
        if self.is_makeup_session or not self.group_id:
            return

        # 1) thử lấy sẵn
        row = self.db.execute_query(
            "SELECT id FROM session_logs WHERE group_id=? AND session_date=?",
            (self.group_id, self.session_date), fetch="one"
        )
        if row:
            self.session_id = row["id"] if isinstance(row, dict) else row[0]
            return

        # 2) chưa có -> khởi tạo dòng trống
        _ = self.db.execute_query(
            "INSERT INTO session_logs (group_id, session_date, topic, homework) VALUES (?, ?, ?, ?)",
            (self.group_id, self.session_date, "", "")
        )

        # 3) lấy lại id
        row2 = self.db.execute_query(
            "SELECT id FROM session_logs WHERE group_id=? AND session_date=?",
            (self.group_id, self.session_date), fetch="one"
        )
        if row2:
            self.session_id = row2["id"] if isinstance(row2, dict) else row2[0]

