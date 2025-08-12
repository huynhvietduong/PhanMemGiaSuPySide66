from PySide6.QtWidgets import QMainWindow, QMessageBox, QFileDialog, QApplication
from PySide6.QtCore import Qt

# Tên import đúng là 'qdarktheme' (dù gói cài đặt là 'pyqtdarktheme')
try:
    import qdarktheme
except ImportError as e:
    # Thông báo rõ ràng khi thiếu lib
    raise ImportError(
        "Thiếu thư viện 'qdarktheme'. Hãy cài bằng: "
        "python -m pip install pyqtdarktheme"
    ) from e


class BaseWindow(QMainWindow):
    def __init__(self, *, title="Gia Sư TVC", theme="light"):
        super().__init__()
        self.setWindowTitle(title)
        self.resize(1200, 800)
        self._theme = None
        self.apply_theme(theme)

    # ===== Theme =====
    def apply_theme(self, theme: str = "light"):
        """theme: 'light' | 'dark'"""
        if theme == self._theme:
            return
        self._theme = theme

        # Cách ưu tiên: setup_theme nếu có (API mới)
        if hasattr(qdarktheme, "setup_theme"):
            # setup_theme sẽ áp dụng palette & style tự động cho QApplication
            qdarktheme.setup_theme(theme)
            return

        # Fallback: dùng load_stylesheet (API cũ)
        if hasattr(qdarktheme, "load_stylesheet"):
            app = QApplication.instance()
            if app is None:
                # Phòng trường hợp apply_theme được gọi trước khi tạo QApplication
                app = QApplication([])
            app.setStyleSheet(qdarktheme.load_stylesheet(theme))
            return

        # Nếu không có cả 2 API trên
        raise RuntimeError(
            "Phiên bản qdarktheme không hỗ trợ setup_theme/load_stylesheet."
        )

    def toggle_theme(self):
        self.apply_theme("dark" if self._theme == "light" else "light")

    # ===== Message helpers =====
    def info(self, text, title="Thông báo"):
        QMessageBox.information(self, title, text)

    def error(self, text, title="Lỗi"):
        QMessageBox.critical(self, title, text)

    def ask_yes_no(self, text, title="Xác nhận") -> bool:
        return QMessageBox.question(self, title, text) == QMessageBox.Yes

    # ===== File dialogs (thay thế filedialog của Tkinter) =====
    def open_file(self, caption="Chọn file", filter_="All Files (*.*)"):
        return QFileDialog.getOpenFileName(self, caption, "", filter_)[0]

    def save_file(self, caption="Lưu file", filter_="All Files (*.*)"):
        return QFileDialog.getSaveFileName(self, caption, "", filter_)[0]
