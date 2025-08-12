# main_qt.py
import sys
from PySide6.QtWidgets import QApplication
from ui_qt.main_window import MainWindow
from database import DatabaseManager  # dùng lại lớp DB hiện tại

if __name__ == "__main__":
    app = QApplication(sys.argv)
    db = DatabaseManager()  # khởi tạo như app cũ của bạn
    w = MainWindow(db)
    w.show()
    sys.exit(app.exec())
