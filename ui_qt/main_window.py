# ui_qt/main_window.py
from __future__ import annotations
import sys, datetime
from datetime import datetime, timedelta
from typing import Dict, Tuple

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt

from constants import DAYS_OF_WEEK_VN, FIXED_TIME_SLOTS
from ui_qt.windows.session_detail_window_qt import SessionDetailWindowQt
from PySide6.QtWidgets import QMenu, QMessageBox


def monday_of(date: datetime) -> datetime:
    return date - timedelta(days=(date.weekday() % 7))  # 0=Mon


def fmt_date(d: datetime) -> str:
    return d.strftime("%d/%m")


class MainWindow(QtWidgets.QMainWindow):
    """
    MainWindow (PySide6) – bố cục 2 cột như bản Tkinter:
    - Trái: Bảng điều khiển (giờ, lịch hôm nay, lớp sắp tới, thông báo)
    - Phải: Lịch biểu tuần (Tuần trước/ Tuần sau/ Hôm nay)
    Block lịch nhấn để mở SessionDetailWindowQt.
    """
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setWindowTitle("Phần mềm Quản lý Gia sư - Qt")
        self.resize(1280, 800)

        self.week_monday = monday_of(datetime.now())

        self._build_ui()
        self._ensure_cancel_table()
        self._refresh_sidebar()
        self._refresh_week_header()
        self._render_grid()

        # đồng hồ 1s
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    # ================= UI =================
    def _build_ui(self):
        cw = QtWidgets.QWidget()
        self.setCentralWidget(cw)
        root = QtWidgets.QHBoxLayout(cw)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ---- Sidebar trái
        self.sidebar = QtWidgets.QFrame()
        self.sidebar.setMinimumWidth(280)
        self.sidebar.setMaximumWidth(320)
        self.sidebar.setFrameShape(QtWidgets.QFrame.StyledPanel)
        s = QtWidgets.QVBoxLayout(self.sidebar)
        s.setContentsMargins(10, 10, 10, 10)

        title = QtWidgets.QLabel("Bảng điều khiển")
        title.setStyleSheet("font-size:18px;font-weight:700;")
        s.addWidget(title)

        self.time_label = QtWidgets.QLabel("--:--:--\nThứ ?, --/--/----")
        self.time_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.time_label.setStyleSheet("font-size:16px;margin:8px 0 12px 0;")
        s.addWidget(self.time_label)

        # lịch dạy hôm nay
        s.addWidget(self._section_title("Lịch dạy hôm nay"))
        self.today_list = QtWidgets.QListWidget()
        self.today_list.setMinimumHeight(130)
        s.addWidget(self.today_list)

        # lớp sắp tới
        s.addWidget(self._section_title("Lớp sắp tới"))
        self.next_class_box = QtWidgets.QTextEdit()
        self.next_class_box.setReadOnly(True)
        self.next_class_box.setMaximumHeight(60)
        self.next_class_box.setStyleSheet("color:#555;")
        s.addWidget(self.next_class_box)

        # thông báo
        s.addWidget(self._section_title("Thông báo"))
        self.notice = QtWidgets.QTextEdit()
        self.notice.setReadOnly(True)
        self.notice.setPlaceholderText("Sẵn sàng…")
        s.addWidget(self.notice, 1)

        root.addWidget(self.sidebar)

        # ---- Khu vực lịch phải
        right = QtWidgets.QWidget()
        r = QtWidgets.QVBoxLayout(right)
        r.setContentsMargins(0, 0, 0, 0)

        # thanh điều hướng tuần
        nav = QtWidgets.QHBoxLayout()
        self.btn_prev = QtWidgets.QPushButton("◀ Tuần trước")
        self.btn_next = QtWidgets.QPushButton("Tuần sau ▶")
        self.btn_today = QtWidgets.QPushButton("Hôm nay")
        self.btn_prev.clicked.connect(self._prev_week)
        self.btn_next.clicked.connect(self._next_week)
        self.btn_today.clicked.connect(self._goto_today)
        self.week_title = QtWidgets.QLabel("Lịch biểu Tuần")
        self.week_title.setStyleSheet("font-size:16px;font-weight:600;")
        nav.addWidget(self.btn_prev, 0, Qt.AlignLeft)
        nav.addWidget(self.week_title, 1, Qt.AlignCenter)
        nav.addWidget(self.btn_today, 0, Qt.AlignRight)
        nav.addWidget(self.btn_next, 0, Qt.AlignRight)
        r.addLayout(nav)

        # header ngày (Thứ + dd/mm)
        self.days_header = QtWidgets.QHBoxLayout()
        self.day_header_btns: list[QtWidgets.QToolButton] = []
        for i in range(7):
            b = QtWidgets.QToolButton()
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setMinimumHeight(48)
            b.setStyleSheet("QToolButton{background:#f4f6f8;border:1px solid #d6d9dd;border-radius:6px;}")
            # ✅ bật context menu (chuột phải)
            b.setContextMenuPolicy(Qt.CustomContextMenu)
            b.customContextMenuRequested.connect(lambda pos, idx=i, w=b: self._show_day_menu(pos, idx, w))
            self.day_header_btns.append(b)
            self.days_header.addWidget(b)
        r.addLayout(self.days_header)

        # khu vực lưới thời gian trong ScrollArea
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        r.addWidget(self.scroll, 1)

        self.grid_host = QtWidgets.QWidget()
        self.scroll.setWidget(self.grid_host)
        g = QtWidgets.QGridLayout(self.grid_host)
        g.setContentsMargins(0, 8, 0, 8)
        g.setHorizontalSpacing(6)
        g.setVerticalSpacing(12)
        self.grid: QtWidgets.QGridLayout = g

        root.addWidget(right, 1)

        # style nhỏ cho nhãn giờ
        self._hour_label_style = "font-weight:600;color:#555;padding:4px 6px;border:1px solid #e2e4e8;border-radius:6px;background:#fafafa;"

    def _section_title(self, text: str) -> QtWidgets.QLabel:
        lab = QtWidgets.QLabel(text)
        lab.setStyleSheet("font-weight:600;margin-top:12px;")
        return lab

    # ============== Sidebar data ============
    def _tick(self):
        now = datetime.now()
        d = now.strftime("%H:%M:%S")
        wd = DAYS_OF_WEEK_VN[now.weekday()]
        self.time_label.setText(f"{d}\n{wd}, {now.strftime('%d-%m-%Y')}")
        # cập nhật “lớp sắp tới” mỗi phút
        if now.second == 0:
            self._refresh_sidebar()

    def _refresh_sidebar(self):
        # lịch dạy hôm nay
        self.today_list.clear()
        today = datetime.now()
        day_vn = DAYS_OF_WEEK_VN[today.weekday()]
        rows = self.db.execute_query(
            "SELECT g.name, s.time_slot FROM schedule s JOIN groups g ON s.group_id=g.id "
            "WHERE s.day_of_week=? ORDER BY s.time_slot", (day_vn,), fetch="all"
        ) or []
        for r in rows:
            name = r["name"] if isinstance(r, dict) else r[0]
            slot = r["time_slot"] if isinstance(r, dict) else r[1]
            self.today_list.addItem(f"{slot}  •  {name}")

        # lớp sắp tới trong hôm nay
        upcoming = None
        now_str = datetime.now().strftime("%H:%M")
        for r in rows:
            slot = r["time_slot"] if isinstance(r, dict) else r[1]
            if slot >= now_str:
                upcoming = r
                break
        if upcoming:
            name = upcoming["name"] if isinstance(upcoming, dict) else upcoming[0]
            slot = upcoming["time_slot"] if isinstance(upcoming, dict) else upcoming[1]
            self.next_class_box.setPlainText(f"{slot}\n{name}")
        else:
            self.next_class_box.setPlainText("Chưa có lớp nào sắp diễn ra.")

    # ============== Week header =============
    def _refresh_week_header(self):
        mon = self.week_monday
        end = mon + timedelta(days=6)
        self.week_title.setText(f"Lịch biểu Tuần ({fmt_date(mon)} - {fmt_date(end)})")

        for i in range(7):
            d = mon + timedelta(days=i)
            wd = DAYS_OF_WEEK_VN[d.weekday()]
            btn = self.day_header_btns[i]
            btn.setText(f"{wd}\n({fmt_date(d)})")
            # highlight hôm nay
            if d.date() == datetime.now().date():
                btn.setStyleSheet("QToolButton{background:#e7f1ff;border:1px solid #a5c8ff;border-radius:6px;font-weight:700;}")
            else:
                btn.setStyleSheet("QToolButton{background:#f4f6f8;border:1px solid #d6d9dd;border-radius:6px;}")

    # ============== Grid render =============
    def _clear_grid(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _render_grid(self):
        self._clear_grid()

        # cột 0 là nhãn giờ cố định
        for r, t in enumerate(FIXED_TIME_SLOTS):
            lab = QtWidgets.QLabel(t)
            lab.setAlignment(Qt.AlignCenter)
            lab.setStyleSheet(self._hour_label_style)
            self.grid.addWidget(lab, r + 1, 0)

        # header cột trống (ô [0,0])
        self.grid.addWidget(QtWidgets.QLabel(""), 0, 0)

        # vẽ block lịch: tra bảng schedule
        mon = self.week_monday
        # tạo map: (date_str, time_slot) -> [(group_id, name)]
        items: Dict[Tuple[str, str], list[tuple[int, str]]] = {}

        # lấy tất cả lịch cố định rồi phân phối về từng ngày trong tuần
        schedules = self.db.execute_query(
            "SELECT s.group_id, g.name, s.day_of_week, s.time_slot "
            "FROM schedule s JOIN groups g ON s.group_id=g.id", fetch="all"
        ) or []

        day_map = {DAYS_OF_WEEK_VN[(mon + timedelta(days=i)).weekday()]: (mon + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)}
        for row in schedules:
            gid  = row["group_id"] if isinstance(row, dict) else row[0]
            name = row["name"]      if isinstance(row, dict) else row[1]
            dow  = row["day_of_week"] if isinstance(row, dict) else row[2]
            slot = row["time_slot"] if isinstance(row, dict) else row[3]
            if dow in day_map:
                dstr = day_map[dow]
                items.setdefault((dstr, slot), []).append((gid, name))

        # thêm (tuỳ chọn) các buổi bù riêng đã lên lịch trong tuần để bạn nhìn thấy khung đã bận
        makeups = self.db.execute_query(
            "SELECT session_date, time_slot, student_id FROM makeup_sessions "
            "WHERE session_date BETWEEN ? AND ? AND is_private=1",
            ((mon).strftime("%Y-%m-%d"), (mon + timedelta(days=6)).strftime("%Y-%m-%d")),
            fetch="all"
        ) or []
        for r in makeups:
            dstr = r["session_date"] if isinstance(r, dict) else r[0]
            slot = r["time_slot"] if isinstance(r, dict) else r[1]
            items.setdefault((dstr, slot), []).append((-1, "Buổi bù riêng"))

        # vẽ theo ngày x cột
        for c in range(7):
            day = mon + timedelta(days=c)
            day_str = day.strftime("%Y-%m-%d")
            # header cột (ô [0, c+1])
            header = QtWidgets.QLabel("")  # đã có thanh header phía trên
            self.grid.addWidget(header, 0, c + 1)

            for r, slot in enumerate(FIXED_TIME_SLOTS):
                key = (day_str, slot)
                cell_items = items.get(key, [])

                if not cell_items:
                    # ô trống -> khung mờ
                    placeholder = QtWidgets.QFrame()
                    placeholder.setStyleSheet("background:#f7f9fb;border:1px dashed #e3e6ea;border-radius:8px;")
                    self.grid.addWidget(placeholder, r + 1, c + 1)
                    continue

                # nếu nhiều nhóm trùng slot -> hiển thị chồng trong một card
                txt_lines = []
                first_gid = None
                first_name = ""
                for gid, name in cell_items:
                    txt_lines.append(name)
                    if first_gid is None and gid != -1:
                        first_gid = gid
                        first_name = name
                text = "\n".join(txt_lines)

                btn = QtWidgets.QPushButton(text)
                btn.setMinimumHeight(72)
                btn.setStyleSheet("""
                    QPushButton{
                        background:#eaf2ff;border:1px solid #bcd3ff;border-radius:10px;
                        padding:8px;font-weight:600;color:#284b7b;
                    }
                    QPushButton:hover{ background:#deebff; }
                """)
                is_cancelled = False
                if first_gid:
                    row = self.db.execute_query(
                        "SELECT 1 FROM cancelled_sessions WHERE group_id=? AND cancelled_date=?",
                        (first_gid, day_str), fetch="one"
                    )
                    is_cancelled = bool(row)

                btn = QtWidgets.QPushButton(text)
                btn.setMinimumHeight(72)

                # style theo trạng thái
                if is_cancelled:
                    btn.setStyleSheet("""
                        QPushButton{
                            background:#f0f0f0;border:1px dashed #c8c8c8;border-radius:10px;
                            padding:8px;color:#666;
                        }
                        QPushButton:hover{ background:#eaeaea; }
                    """)
                else:
                    btn.setStyleSheet("""
                        QPushButton{
                            background:#eaf2ff;border:1px solid #bcd3ff;border-radius:10px;
                            padding:8px;font-weight:600;color:#284b7b;
                        }
                        QPushButton:hover{ background:#deebff; }
                    """)

                # click trái: mở chi tiết nếu chưa hủy
                if first_gid and not is_cancelled:
                    btn.clicked.connect(lambda _=False, d=day_str, gid=first_gid, name=first_name:
                                        self._open_session_detail(d, gid, name))

                # ✅ gắn thông tin để xử lý menu chuột phải
                btn.setProperty("session_info", {
                    "group_id": first_gid, "group_name": first_name,
                    "date": day_str, "is_cancelled": is_cancelled
                })
                btn.setContextMenuPolicy(Qt.CustomContextMenu)
                btn.customContextMenuRequested.connect(self._show_session_menu)

                self.grid.addWidget(btn, r + 1, c + 1)

        # làm các cột bằng nhau
        for c in range(0, 8):
            self.grid.setColumnStretch(c, 1)

    # ============== Navigation =============
    def _prev_week(self):
        self.week_monday -= timedelta(days=7)
        self._refresh_week_header()
        self._render_grid()

    def _next_week(self):
        self.week_monday += timedelta(days=7)
        self._refresh_week_header()
        self._render_grid()

    def _goto_today(self):
        self.week_monday = monday_of(datetime.now())
        self._refresh_week_header()
        self._render_grid()

    # ============== Actions ================
    def _open_session_detail(self, date_str: str, group_id: int, group_name: str):
        dlg = SessionDetailWindowQt(self, self.db, date_str, group_id=group_id, group_name=group_name)
        dlg.exec()

    def update_all_schedules(self):
        self._refresh_sidebar()
        self._refresh_week_header()
        self._render_grid()

    def _show_day_menu(self, pos, day_index: int, widget: QtWidgets.QWidget):
        menu = QMenu(self)
        menu.addAction("Hủy tất cả buổi học trong ngày",
                       lambda: self._cancel_day_sessions_by_index(day_index))
        menu.exec(widget.mapToGlobal(pos))

    def _cancel_day_sessions_by_index(self, day_index: int):
        # xác định ngày thực tế theo tuần đang xem
        target_date = self.week_monday + timedelta(days=day_index)
        date_str = target_date.strftime("%Y-%m-%d")
        day_vn = DAYS_OF_WEEK_VN[target_date.weekday()]

        # Lấy các nhóm có lịch trong ngày đó
        rows = self.db.execute_query(
            "SELECT g.id, g.name FROM schedule s JOIN groups g ON s.group_id=g.id "
            "WHERE s.day_of_week=? ORDER BY g.name", (day_vn,), fetch='all'
        ) or []
        if not rows:
            QMessageBox.information(self, "Thông báo",
                                    f"Không có lớp nào lên lịch {day_vn} ({date_str}).")
            return

        group_names = ", ".join([(r["name"] if isinstance(r, dict) else r[1]) for r in rows])
        if QMessageBox.question(
                self, "Xác nhận",
                f"Bạn có chắc muốn HỦY TẤT CẢ buổi học ngày {day_vn} ({date_str})?\n"
                f"Các nhóm bị ảnh hưởng: {group_names}"
        ) != QMessageBox.Yes:
            return

        for r in rows:
            gid = r["id"] if isinstance(r, dict) else r[0]
            self._perform_cancellation(gid, date_str)

        self.update_all_schedules()

    def _show_session_menu(self, pos):
        w = self.sender()
        info = w.property("session_info") or {}
        gid = info.get("group_id")
        if not gid:
            return
        menu = QMenu(self)
        if info.get("is_cancelled"):
            menu.addAction("Phục hồi buổi học này", lambda: self._restore_single_session(info))
        else:
            menu.addAction("Hủy buổi học này", lambda: self._cancel_single_session(info))
        menu.exec(w.mapToGlobal(pos))

    def _cancel_single_session(self, info: dict):
        gid = info["group_id"];
        gname = info["group_name"];
        date_str = info["date"]
        if QMessageBox.question(self, "Xác nhận",
                                f"Hủy buổi học của Nhóm {gname} vào ngày {date_str}?") != QMessageBox.Yes:
            return
        self._perform_cancellation(gid, date_str)
        self.update_all_schedules()

    def _restore_single_session(self, info: dict):
        gid = info["group_id"];
        gname = info["group_name"];
        date_str = info["date"]
        if QMessageBox.question(self, "Xác nhận",
                                f"Phục hồi buổi học của Nhóm {gname} ngày {date_str}?") != QMessageBox.Yes:
            return
        # gỡ trạng thái hủy + xoá điểm danh 'Nghỉ do GV bận'
        self.db.execute_query("DELETE FROM cancelled_sessions WHERE group_id=? AND cancelled_date=?",
                              (gid, date_str))
        self.db.execute_query(
            "DELETE FROM attendance WHERE group_id=? AND session_date=? AND status='Nghỉ do GV bận'",
            (gid, date_str)
        )
        self.update_all_schedules()

    def _perform_cancellation(self, group_id: int, date_str: str):
        # Ghi vào bảng hủy buổi + set 'Nghỉ do GV bận' cho tất cả HS của nhóm
        self.db.execute_query(
            "INSERT OR IGNORE INTO cancelled_sessions(group_id, cancelled_date) VALUES (?, ?)",
            (group_id, date_str)
        )
        students = self.db.execute_query(
            "SELECT id FROM students WHERE group_id=?", (group_id,), fetch="all"
        ) or []
        for row in students:
            sid = row["id"] if isinstance(row, dict) else row[0]
            self.db.execute_query(
                "INSERT INTO attendance(student_id, group_id, session_date, status, make_up_status) "
                "VALUES (?, ?, ?, 'Nghỉ do GV bận', '') "
                "ON CONFLICT(student_id, group_id, session_date) DO UPDATE SET "
                "status=excluded.status, make_up_status=excluded.make_up_status",
                (sid, group_id, date_str)
            )

    def _ensure_cancel_table(self):
        self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS cancelled_sessions(
                group_id INTEGER,
                cancelled_date TEXT,
                PRIMARY KEY(group_id, cancelled_date)
            )
        """)

# Chạy độc lập để test nhanh
if __name__ == "__main__":
    from database import DatabaseManager
    app = QtWidgets.QApplication(sys.argv)
    db = DatabaseManager()
    w = MainWindow(db)
    w.show()
    sys.exit(app.exec())
