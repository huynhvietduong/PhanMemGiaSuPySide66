# ui_qt/windows/#dashboard_window_qt.py
from __future__ import annotations
import os
from functools import partial
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
import sys
from pathlib import Path
current_dir = Path(__file__).parent
question_bank_path = current_dir / 'question_bank'
#(Debug thông tin về question_bank paths)
if question_bank_path.exists():
    main_window_file = question_bank_path / "views" / "main_window.py"
if str(question_bank_path) not in sys.path:
    sys.path.insert(0, str(question_bank_path))

def _safe_import(path: str, class_name: str):
    """Import tiện lợi: trả về class hoặc None nếu thiếu file Qt."""
    try:
        mod = __import__(path, fromlist=[class_name])
        return getattr(mod, class_name)
    except Exception as e:
        # In ra lỗi chi tiết để debug
        print(f"❌ Lỗi import {path}.{class_name}: {e}")
        import traceback
        traceback.print_exc()
        return None
class DashboardWindowQt(QtWidgets.QMainWindow):
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setWindowTitle("📚 Bảng điều khiển - Phần mềm Gia sư (Qt)")

        cw = QtWidgets.QWidget()
        self.setCentralWidget(cw)
        root = QtWidgets.QVBoxLayout(cw)

        # thanh tiêu đề
        title = QtWidgets.QLabel("📚 Bảng điều khiển")
        title.setStyleSheet("font-size:20px;font-weight:700;")
        root.addWidget(title)
        root.addSpacing(8)

        # khu vực cuộn
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll, 1)

        inner = QtWidgets.QWidget()
        scroll.setWidget(inner)
        lay = QtWidgets.QVBoxLayout(inner)

        # ==== Nhóm chức năng ====
        # Nhóm chức năng quản lý học tập - thêm Gói học
        self._add_section(lay, "📂 Quản lý học tập", [
            ("Học sinh", "assets/icons/students.png", self._open("ui_qt.windows.student_window_qt", "StudentWindowQt")),
            ("Nhóm học", "assets/icons/groups.png", self._open("ui_qt.windows.group_window_qt", "GroupWindowQt")),
            ("Gói học", "assets/icons/students.png", self._open("ui_qt.windows.package_window_qt", "PackageWindowQt")),
            ("Chuyên cần", "assets/icons/attendance.png",
             self._open("ui_qt.windows.attendance_report_window_qt", "AttendanceReportWindowQt")),
            ("Lịch dạy (Main)", "assets/icons/calendar.png", self._open_main_window),
        ])

        self._add_section(lay, "📝 Bài tập & Câu hỏi", [
            ("Giao bài",           "assets/icons/assignment.png",       self._open("ui_qt.windows.assign_exercise_window_qt", "AssignExerciseWindowQt")),
            ("Nộp bài",            "assets/icons/submit.png",           self._open("ui_qt.windows.submit_exercise_window_qt", "SubmitExerciseWindowQt")),
            ("Đã nộp",             "assets/icons/submitted.png",        self._open("ui_qt.windows.submitted_exercise_manager_window_qt", "SubmittedExerciseManagerWindowQt")),
            ("Ngân hàng câu hỏi", "assets/icons/question_bank.png",     self._open_question_bank_window),
            ("Gợi ý bài",          "assets/icons/suggest.png",          self._open("ui_qt.windows.exercise_suggestion_window_qt", "ExerciseSuggestionWindowQt")),
            ("Tạo đề PDF",         "assets/icons/test.png",             self._open("ui_qt.windows.create_test_window_qt", "CreateTestWindowQt")),
            ("Cây thư mục",        "assets/icons/folder.png",           self._open("ui_qt.windows.exercise_tree_manager_qt", "ExerciseTreeManagerQt")),
        ])

        self._add_section(lay, "📊 Báo cáo & Đánh giá", [
            ("Tiến độ",            "assets/icons/progress.png",         self._open("ui_qt.windows.progress_report_window_qt", "ProgressReportWindowQt")),
            ("Năng lực",           "assets/icons/skill.png",            self._open("ui_qt.windows.student_skill_report_window_qt", "StudentSkillReportWindowQt")),
            ("Đánh giá",           "assets/icons/rating.png",           self._open("ui_qt.windows.skill_rating_window_qt", "SkillRatingWindowQt")),
            ("Gợi ý nhóm",         "assets/icons/group_suggest.png",    self._open("ui_qt.windows.group_suggestion_window_qt", "GroupSuggestionWindowQt")),
            ("Học phí",            "assets/icons/salary.png",           self._open("ui_qt.windows.salary_window_qt", "SalaryWindowQt")),
        ])

        lay.addStretch(1)

        # menubar cơ bản
        m = self.menuBar().addMenu("Tệp")
        act_exit = QtGui.QAction("Thoát", self)
        act_exit.triggered.connect(self.close)
        m.addAction(act_exit)
        self.showMaximized()

    # ---------- helpers ----------
    def _add_section(self, parent_layout: QtWidgets.QVBoxLayout, title: str, items: list[tuple[str, str, callable]]):
        lab = QtWidgets.QLabel(title)
        lab.setStyleSheet("font-weight:600;margin-top:14px;")
        parent_layout.addWidget(lab)

        grid = QtWidgets.QGridLayout()
        parent_layout.addLayout(grid)

        # Điều chỉnh số cột mỗi hàng (mặc định là 5, có thể đổi thành 4)
        columns_per_row = 4  # Thay đổi từ 5 thành 4 nếu muốn

        for i, (text, icon_path, handler) in enumerate(items):
            w = self._make_card(text, icon_path, handler)
            grid.addWidget(w, i // columns_per_row, i % columns_per_row)
    def _make_card(self, text: str, icon_path: str, handler: callable) -> QtWidgets.QWidget:
        btn = QtWidgets.QToolButton()
        btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        btn.setText(text)
        if os.path.exists(icon_path):
            btn.setIcon(QtGui.QIcon(icon_path))
            btn.setIconSize(QtCore.QSize(64, 64))

        # Tùy chỉnh kích thước nếu có nhiều nút trong 1 hàng
        btn.setFixedSize(140, 120)  # Hoặc điều chỉnh theo nhu cầu

        btn.clicked.connect(handler)
        wrap = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(wrap)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(btn, 0, Qt.AlignLeft)
        return wrap
    # ui_qt/windows/#dashboard_window_qt.py
    def _open(self, module_path: str, class_name: str):
        def _handler():
            cls = _safe_import(module_path, class_name)
            if not cls:
                QtWidgets.QMessageBox.information(self, "Thông tin", f"Chức năng '{class_name}' (Qt) chưa sẵn sàng.")
                return

            # Tạo cửa sổ con
            win = cls(self.db, parent=self)

            # Kiểm tra loại cửa sổ và xử lý hiển thị phù hợp
            if isinstance(win, QtWidgets.QDialog):
                win.exec()
            else:
                # Fix: Đảm bảo cửa sổ QWidget luôn hiển thị trên cùng
                win.setWindowFlags(win.windowFlags() | Qt.Window)
                try:
                    win.showMaximized()
                except:
                    # Fallback nếu showMaximized() không hoạt động
                    win.show()
                    win.setWindowState(Qt.WindowMaximized)

                win.raise_()  # Đưa lên trên cùng
                win.activateWindow()  # Kích hoạt cửa sổ

                # Lưu tham chiếu để tránh bị garbage collect
                if not hasattr(self, '_child_windows'):
                    self._child_windows = []
                self._child_windows.append(win)

                # Xóa tham chiếu khi cửa sổ đóng
                def on_window_closed():
                    if win in self._child_windows:
                        self._child_windows.remove(win)

                win.destroyed.connect(on_window_closed)

        return _handler
    def _open_main_window(self):
        # mở “Lịch dạy” / MainWindow (Qt)
        from ui_qt.main_window import MainWindow
        self._mw = MainWindow(self.db)  # giữ tham chiếu

        # 🔧 FIX: Sử dụng showMaximized thay vì show
        self._mw.showMaximized()
        self._mw.raise_()
        self._mw.activateWindow()

    def _open_question_bank_window(self):
        """Mở cửa sổ Question Bank mới với error handling đầy đủ"""
        try:
            # (Thử import QuestionBankMainWindow từ đường dẫn chính)
            from ui_qt.windows.question_bank.views.main_window import QuestionBankMainWindow

            # (Tạo và hiển thị cửa sổ Question Bank)
            self.question_bank_window = QuestionBankMainWindow(self.db, parent=self)
            self.question_bank_window.showMaximized()
            self.question_bank_window.raise_()
            self.question_bank_window.activateWindow()

            # (Lưu reference để tránh garbage collection)
            if not hasattr(self, '_child_windows'):
                self._child_windows = []
            self._child_windows.append(self.question_bank_window)

            print("✅ Đã mở Question Bank thành công")

        except ImportError as e:
            print(f"❌ Lỗi import QuestionBankMainWindow: {e}")
            # (Thử fallback import path khác)
            try:
                from question_bank.views.main_window import QuestionBankMainWindow
                self.question_bank_window = QuestionBankMainWindow(self.db, parent=self)
                self.question_bank_window.showMaximized()  # Thay vì show()
                self.question_bank_window.raise_()
                self.question_bank_window.activateWindow()
                print("✅ Đã mở Question Bank bằng fallback path")
            except ImportError:
                # (Hiển thị dialog lỗi với hướng dẫn)
                QtWidgets.QMessageBox.warning(
                    self, "Không thể mở Question Bank",
                    "Lỗi: Không tìm thấy module Question Bank.\n\n"
                    "Kiểm tra:\n"
                    "1. File main_window.py có tồn tại không\n"
                    "2. Các dependencies có đầy đủ không\n"
                    "3. Import path có đúng không"
                )
        except Exception as e:
            print(f"❌ Lỗi không xác định: {e}")
            # (Hiển thị dialog lỗi chi tiết)
            QtWidgets.QMessageBox.critical(
                self, "Lỗi không xác định",
                f"Không thể mở Question Bank:\n{str(e)}\n\n"
                f"Vui lòng kiểm tra console để xem chi tiết lỗi."
            )