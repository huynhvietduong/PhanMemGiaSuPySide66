# app_qt.py
import sys
from PySide6.QtWidgets import QApplication
from database import DatabaseManager
from ui_qt.windows.dashboard_window_qt import DashboardWindowQt  # file ở mục (2)

def main():
    app = QApplication(sys.argv)
    db = DatabaseManager()
    win = DashboardWindowQt(db)
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
    #