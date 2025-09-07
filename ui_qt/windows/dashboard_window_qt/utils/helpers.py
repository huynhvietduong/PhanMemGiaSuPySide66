# ui_qt/windows/dashboard_window_qt/utils/helpers.py
"""
Module chứa các hàm tiện ích cho Dashboard Desktop-Style
Bao gồm: format, validate, system utils, file operations
"""

import os
import sys
import json
import shutil
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any, Union
import logging

from PySide6.QtCore import QSize, QPoint, QRect, QUrl
from PySide6.QtGui import QIcon, QPixmap, QDesktopServices
from PySide6.QtWidgets import QMessageBox, QWidget

from .constants import (
    EXECUTABLE_FORMATS,
    SUPPORTED_IMAGE_FORMATS,
    SUPPORTED_DOCUMENT_FORMATS,
    ICONS_DIR,
    DEFAULT_ICON_SIZE
)

# Thiết lập logger
logger = logging.getLogger(__name__)


# ========== FILE & PATH UTILITIES ==========

def validate_exe_path(path: str) -> bool:
    """
    Kiểm tra đường dẫn file thực thi có hợp lệ không

    Args:
        path: Đường dẫn cần kiểm tra

    Returns:
        True nếu path hợp lệ và file tồn tại
    """
    try:
        if not path or not os.path.exists(path):
            return False

        path_obj = Path(path)

        # Kiểm tra extension
        if path_obj.suffix.lower() not in EXECUTABLE_FORMATS:
            return False

        # Kiểm tra file có thể thực thi
        if sys.platform == "win32":
            return os.access(path, os.X_OK) or path_obj.suffix.lower() in ['.exe', '.bat', '.cmd']
        else:
            return os.access(path, os.X_OK)

    except Exception as e:
        logger.error(f"Lỗi validate exe path: {e}")
        return False


def get_file_icon(file_path: str, size: QSize = DEFAULT_ICON_SIZE) -> QIcon:
    """
    Lấy icon từ file hoặc thư mục

    Args:
        file_path: Đường dẫn file/folder
        size: Kích thước icon mong muốn

    Returns:
        QIcon object
    """
    try:
        if not os.path.exists(file_path):
            return QIcon()

        # Windows: Lấy icon từ file
        if sys.platform == "win32":
            import win32api
            import win32con
            import win32gui
            import win32ui

            # Lấy icon handle
            ico_x = size.width()
            ico_y = size.height()

            large, small = win32gui.ExtractIconEx(file_path, 0)
            if large:
                win32gui.DestroyIcon(large[0])
            if small:
                pixmap = QPixmap.fromWinHICON(small[0])
                win32gui.DestroyIcon(small[0])
                return QIcon(pixmap)

        # Fallback: Dùng icon mặc định theo extension
        ext = Path(file_path).suffix.lower()
        icon_map = {
            '.exe': 'app.png',
            '.pdf': 'pdf.png',
            '.doc': 'doc.png',
            '.docx': 'doc.png',
            '.txt': 'txt.png',
            '.py': 'python.png',
            '.jpg': 'image.png',
            '.png': 'image.png',
            '.mp4': 'video.png',
            '.mp3': 'audio.png',
            '.zip': 'archive.png',
            '.rar': 'archive.png'
        }

        icon_name = icon_map.get(ext, 'file.png')
        icon_path = ICONS_DIR / icon_name

        if icon_path.exists():
            return QIcon(str(icon_path))

    except Exception as e:
        logger.error(f"Lỗi get file icon: {e}")

    return QIcon()


def create_desktop_shortcut(
        target_path: str,
        shortcut_name: str,
        icon_path: Optional[str] = None,
        arguments: str = "",
        description: str = ""
) -> bool:
    """
    Tạo shortcut trên desktop

    Args:
        target_path: Đường dẫn đến file/app
        shortcut_name: Tên shortcut
        icon_path: Đường dẫn icon (optional)
        arguments: Tham số dòng lệnh (optional)
        description: Mô tả shortcut (optional)

    Returns:
        True nếu tạo thành công
    """
    try:
        desktop = Path.home() / "Desktop"

        if sys.platform == "win32":
            import win32com.client

            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut_path = desktop / f"{shortcut_name}.lnk"

            shortcut = shell.CreateShortcut(str(shortcut_path))
            shortcut.TargetPath = target_path
            shortcut.Arguments = arguments
            shortcut.Description = description

            if icon_path and os.path.exists(icon_path):
                shortcut.IconLocation = icon_path

            shortcut.Save()
            return True

        else:
            # Linux/Mac: Tạo .desktop file
            desktop_file = desktop / f"{shortcut_name}.desktop"

            content = f"""[Desktop Entry]
Type=Application
Name={shortcut_name}
Comment={description}
Exec={target_path} {arguments}
Icon={icon_path if icon_path else 'application-x-executable'}
Terminal=false
"""
            desktop_file.write_text(content)
            desktop_file.chmod(0o755)
            return True

    except Exception as e:
        logger.error(f"Lỗi tạo desktop shortcut: {e}")
        return False


def get_file_info(file_path: str) -> Dict[str, Any]:
    """
    Lấy thông tin chi tiết về file

    Args:
        file_path: Đường dẫn file

    Returns:
        Dictionary chứa thông tin file
    """
    try:
        path = Path(file_path)

        if not path.exists():
            return {}

        stat = path.stat()

        info = {
            "name": path.name,
            "path": str(path.absolute()),
            "size": stat.st_size,
            "size_formatted": format_file_size(stat.st_size),
            "created": datetime.fromtimestamp(stat.st_ctime),
            "modified": datetime.fromtimestamp(stat.st_mtime),
            "accessed": datetime.fromtimestamp(stat.st_atime),
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
            "extension": path.suffix.lower() if path.is_file() else None,
            "mime_type": get_mime_type(file_path),
            "permissions": oct(stat.st_mode)[-3:]
        }

        # Thêm thông tin cho thư mục
        if path.is_dir():
            try:
                items = list(path.iterdir())
                info["item_count"] = len(items)
                info["total_size"] = sum(f.stat().st_size for f in items if f.is_file())
            except:
                info["item_count"] = 0
                info["total_size"] = 0

        return info

    except Exception as e:
        logger.error(f"Lỗi get file info: {e}")
        return {}


# ========== FORMAT UTILITIES ==========

def format_file_size(size_bytes: int) -> str:
    """
    Format kích thước file thành dạng đọc được (KB, MB, GB)

    Args:
        size_bytes: Kích thước tính bằng bytes

    Returns:
        String đã format (vd: "1.5 MB")
    """
    try:
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                if unit == 'B':
                    return f"{size_bytes} {unit}"
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
    except:
        return "0 B"


def format_duration(seconds: int) -> str:
    """
    Format thời gian từ giây sang dạng đọc được

    Args:
        seconds: Số giây

    Returns:
        String format (vd: "2 giờ 30 phút")
    """
    try:
        if seconds < 60:
            return f"{seconds} giây"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes} phút {secs} giây" if secs else f"{minutes} phút"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours} giờ {minutes} phút" if minutes else f"{hours} giờ"
    except:
        return "0 giây"


def format_datetime(dt: datetime, format_type: str = "full") -> str:
    """
    Format datetime theo các kiểu khác nhau

    Args:
        dt: Datetime object
        format_type: "full", "date", "time", "relative"

    Returns:
        String đã format
    """
    try:
        if format_type == "full":
            return dt.strftime("%d/%m/%Y %H:%M:%S")
        elif format_type == "date":
            return dt.strftime("%d/%m/%Y")
        elif format_type == "time":
            return dt.strftime("%H:%M:%S")
        elif format_type == "relative":
            return get_relative_time(dt)
        else:
            return str(dt)
    except:
        return ""


def get_relative_time(dt: datetime) -> str:
    """
    Lấy thời gian tương đối (vd: "2 giờ trước")

    Args:
        dt: Datetime object

    Returns:
        String thời gian tương đối
    """
    try:
        now = datetime.now()
        diff = now - dt

        if diff.days > 365:
            years = diff.days // 365
            return f"{years} năm trước"
        elif diff.days > 30:
            months = diff.days // 30
            return f"{months} tháng trước"
        elif diff.days > 7:
            weeks = diff.days // 7
            return f"{weeks} tuần trước"
        elif diff.days > 0:
            return f"{diff.days} ngày trước"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} giờ trước"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} phút trước"
        else:
            return "Vừa xong"
    except:
        return ""


# ========== VALIDATION UTILITIES ==========

def validate_email(email: str) -> bool:
    """
    Kiểm tra email hợp lệ

    Args:
        email: Địa chỉ email

    Returns:
        True nếu email hợp lệ
    """
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """
    Kiểm tra số điện thoại Việt Nam

    Args:
        phone: Số điện thoại

    Returns:
        True nếu hợp lệ
    """
    import re
    # Pattern cho số điện thoại VN (10-11 số)
    pattern = r'^(0|\+84)[0-9]{9,10}$'
    phone = phone.replace(" ", "").replace("-", "")
    return bool(re.match(pattern, phone))


def sanitize_filename(filename: str) -> str:
    """
    Làm sạch tên file, loại bỏ ký tự không hợp lệ

    Args:
        filename: Tên file gốc

    Returns:
        Tên file đã làm sạch
    """
    import re
    # Loại bỏ các ký tự không hợp lệ
    invalid_chars = r'[<>:"/\\|?*]'
    filename = re.sub(invalid_chars, '_', filename)
    # Giới hạn độ dài
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255 - len(ext)] + ext
    return filename.strip()


# ========== SYSTEM UTILITIES ==========

def get_system_info() -> Dict[str, Any]:
    """
    Lấy thông tin hệ thống

    Returns:
        Dictionary chứa thông tin hệ thống
    """
    import platform
    import psutil

    try:
        info = {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(logical=True),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_total": format_file_size(psutil.virtual_memory().total),
            "memory_available": format_file_size(psutil.virtual_memory().available),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": {}
        }

        # Thông tin ổ đĩa
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                info["disk_usage"][partition.device] = {
                    "total": format_file_size(usage.total),
                    "used": format_file_size(usage.used),
                    "free": format_file_size(usage.free),
                    "percent": usage.percent
                }
            except:
                pass

        return info
    except Exception as e:
        logger.error(f"Lỗi get system info: {e}")
        return {}


def open_file_explorer(path: str) -> bool:
    """
    Mở file explorer tại đường dẫn chỉ định

    Args:
        path: Đường dẫn thư mục

    Returns:
        True nếu mở thành công
    """
    try:
        if not os.path.exists(path):
            return False

        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])

        return True
    except Exception as e:
        logger.error(f"Lỗi open file explorer: {e}")
        return False


def run_as_admin(command: str, args: List[str] = None) -> bool:
    """
    Chạy lệnh với quyền admin

    Args:
        command: Lệnh cần chạy
        args: Danh sách tham số

    Returns:
        True nếu thành công
    """
    try:
        if sys.platform == "win32":
            import ctypes

            if args:
                params = ' '.join(args)
            else:
                params = ''

            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", command, params, None, 1
            )
            return ret > 32
        else:
            # Linux/Mac: Dùng sudo
            cmd = ["sudo", command]
            if args:
                cmd.extend(args)
            subprocess.run(cmd)
            return True

    except Exception as e:
        logger.error(f"Lỗi run as admin: {e}")
        return False


# ========== GEOMETRY UTILITIES ==========

def snap_to_grid(position: QPoint, grid_size: int) -> QPoint:
    """
    Căn chỉnh vị trí theo lưới

    Args:
        position: Vị trí hiện tại
        grid_size: Kích thước ô lưới

    Returns:
        Vị trí đã căn chỉnh
    """
    x = round(position.x() / grid_size) * grid_size
    y = round(position.y() / grid_size) * grid_size
    return QPoint(x, y)


def calculate_grid_layout(
        container_size: QSize,
        item_size: QSize,
        spacing: int = 10
) -> Tuple[int, int]:
    """
    Tính toán layout dạng lưới

    Args:
        container_size: Kích thước container
        item_size: Kích thước mỗi item
        spacing: Khoảng cách giữa items

    Returns:
        Tuple (số cột, số hàng)
    """
    cols = max(1, (container_size.width() - spacing) // (item_size.width() + spacing))
    rows = max(1, (container_size.height() - spacing) // (item_size.height() + spacing))
    return cols, rows


def arrange_windows_cascade(
        windows: List[QWidget],
        area: QRect,
        offset: int = 30
) -> None:
    """
    Sắp xếp cửa sổ kiểu cascade

    Args:
        windows: Danh sách cửa sổ
        area: Vùng sắp xếp
        offset: Khoảng cách cascade
    """
    x, y = area.x(), area.y()

    for window in windows:
        window.move(x, y)
        window.resize(
            min(window.width(), area.width() - x),
            min(window.height(), area.height() - y)
        )
        x += offset
        y += offset

        # Reset nếu vượt quá vùng
        if x + window.width() > area.right() or y + window.height() > area.bottom():
            x = area.x()
            y = area.y()


def arrange_windows_tile(
        windows: List[QWidget],
        area: QRect,
        horizontal: bool = True
) -> None:
    """
    Sắp xếp cửa sổ kiểu tile

    Args:
        windows: Danh sách cửa sổ
        area: Vùng sắp xếp
        horizontal: True = xếp ngang, False = xếp dọc
    """
    if not windows:
        return

    count = len(windows)

    if horizontal:
        # Xếp ngang
        height = area.height() // count
        for i, window in enumerate(windows):
            window.setGeometry(
                area.x(),
                area.y() + i * height,
                area.width(),
                height
            )
    else:
        # Xếp dọc
        width = area.width() // count
        for i, window in enumerate(windows):
            window.setGeometry(
                area.x() + i * width,
                area.y(),
                width,
                area.height()
            )


# ========== JSON UTILITIES ==========

def load_json_file(file_path: str, default: Any = None) -> Any:
    """
    Load dữ liệu từ file JSON

    Args:
        file_path: Đường dẫn file JSON
        default: Giá trị mặc định nếu lỗi

    Returns:
        Dữ liệu từ JSON hoặc default
    """
    try:
        path = Path(file_path)
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Lỗi load JSON: {e}")

    return default if default is not None else {}


def save_json_file(file_path: str, data: Any, indent: int = 2) -> bool:
    """
    Lưu dữ liệu vào file JSON

    Args:
        file_path: Đường dẫn file JSON
        data: Dữ liệu cần lưu
        indent: Số space indent

    Returns:
        True nếu lưu thành công
    """
    try:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)

        return True
    except Exception as e:
        logger.error(f"Lỗi save JSON: {e}")
        return False


# ========== HASH & SECURITY ==========

def calculate_file_hash(file_path: str, algorithm: str = "md5") -> Optional[str]:
    """
    Tính hash của file

    Args:
        file_path: Đường dẫn file
        algorithm: Thuật toán hash (md5, sha1, sha256)

    Returns:
        Hash string hoặc None nếu lỗi
    """
    try:
        hash_obj = hashlib.new(algorithm)

        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hash_obj.update(chunk)

        return hash_obj.hexdigest()
    except Exception as e:
        logger.error(f"Lỗi calculate hash: {e}")
        return None


# ========== DIALOG UTILITIES ==========

def show_message(
        parent: QWidget,
        title: str,
        message: str,
        msg_type: str = "info"
) -> None:
    """
    Hiển thị message box

    Args:
        parent: Parent widget
        title: Tiêu đề
        message: Nội dung
        msg_type: "info", "warning", "error", "question"
    """
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle(title)
    msg_box.setText(message)

    if msg_type == "info":
        msg_box.setIcon(QMessageBox.Information)
    elif msg_type == "warning":
        msg_box.setIcon(QMessageBox.Warning)
    elif msg_type == "error":
        msg_box.setIcon(QMessageBox.Critical)
    elif msg_type == "question":
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

    msg_box.exec()


def confirm_action(
        parent: QWidget,
        title: str,
        message: str
) -> bool:
    """
    Hiển thị dialog xác nhận

    Args:
        parent: Parent widget
        title: Tiêu đề
        message: Nội dung

    Returns:
        True nếu người dùng chọn Yes
    """
    reply = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No
    )
    return reply == QMessageBox.Yes


# ========== MISC UTILITIES ==========

def get_mime_type(file_path: str) -> str:
    """
    Lấy MIME type của file

    Args:
        file_path: Đường dẫn file

    Returns:
        MIME type string
    """
    import mimetypes

    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or "application/octet-stream"


def open_url(url: str) -> bool:
    """
    Mở URL trong browser mặc định

    Args:
        url: URL cần mở

    Returns:
        True nếu mở thành công
    """
    try:
        QDesktopServices.openUrl(QUrl(url))
        return True
    except:
        return False


def copy_to_clipboard(text: str) -> None:
    """
    Copy text vào clipboard

    Args:
        text: Text cần copy
    """
    from PySide6.QtWidgets import QApplication

    clipboard = QApplication.clipboard()
    clipboard.setText(text)


def get_from_clipboard() -> str:
    """
    Lấy text từ clipboard

    Returns:
        Text trong clipboard
    """
    from PySide6.QtWidgets import QApplication

    clipboard = QApplication.clipboard()
    return clipboard.text()


def create_backup(source_path: str, backup_dir: str = None) -> Optional[str]:
    """
    Tạo backup của file/folder

    Args:
        source_path: Đường dẫn nguồn
        backup_dir: Thư mục backup (mặc định: cùng thư mục)

    Returns:
        Đường dẫn file backup hoặc None nếu lỗi
    """
    try:
        source = Path(source_path)
        if not source.exists():
            return None

        # Tạo tên backup với timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{source.stem}_backup_{timestamp}{source.suffix}"

        if backup_dir:
            backup_path = Path(backup_dir) / backup_name
        else:
            backup_path = source.parent / backup_name

        # Copy file hoặc folder
        if source.is_file():
            shutil.copy2(source, backup_path)
        else:
            shutil.copytree(source, backup_path)

        return str(backup_path)

    except Exception as e:
        logger.error(f"Lỗi create backup: {e}")
        return None


def generate_unique_id() -> str:
    """
    Tạo ID unique

    Returns:
        String ID unique
    """
    import uuid
    return str(uuid.uuid4())


def clamp(value: float, min_val: float, max_val: float) -> float:
    """
    Giới hạn giá trị trong khoảng min-max

    Args:
        value: Giá trị cần giới hạn
        min_val: Giá trị tối thiểu
        max_val: Giá trị tối đa

    Returns:
        Giá trị đã giới hạn
    """
    return max(min_val, min(value, max_val))


# ========== CANVAS UTILITIES ==========

def open_canvas_window(parent: QWidget = None) -> None:
    """
    Mở cửa sổ Canvas để vẽ và ghi chú

    Args:
        parent: Parent widget
    """
    try:
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel, QColorDialog
        from PySide6.QtCore import Qt, QPoint
        from PySide6.QtGui import QPainter, QPen, QColor, QImage

        class CanvasWindow(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("📝 Canvas - Vẽ và Ghi chú")
                self.setGeometry(100, 100, 800, 600)

                # Canvas properties
                self.drawing = False
                self.last_point = QPoint()
                self.pen_color = QColor(0, 0, 0)
                self.pen_width = 2

                # Create image
                self.image = QImage(800, 600, QImage.Format_RGB32)
                self.image.fill(Qt.white)

                # Setup UI
                self.setup_ui()

            def setup_ui(self):
                layout = QVBoxLayout(self)

                # Toolbar
                toolbar = QHBoxLayout()

                # Pen width
                toolbar.addWidget(QLabel("Độ dày:"))

                self.width_slider = QSlider(Qt.Horizontal)
                self.width_slider.setMinimum(1)
                self.width_slider.setMaximum(20)
                self.width_slider.setValue(2)
                self.width_slider.valueChanged.connect(self.change_pen_width)
                toolbar.addWidget(self.width_slider)

                self.width_label = QLabel("2px")
                toolbar.addWidget(self.width_label)

                # Color picker
                color_btn = QPushButton("Chọn màu")
                color_btn.clicked.connect(self.choose_color)
                toolbar.addWidget(color_btn)

                # Clear button
                clear_btn = QPushButton("Xóa tất cả")
                clear_btn.clicked.connect(self.clear_canvas)
                toolbar.addWidget(clear_btn)

                # Save button
                save_btn = QPushButton("Lưu")
                save_btn.clicked.connect(self.save_canvas)
                toolbar.addWidget(save_btn)

                toolbar.addStretch()
                layout.addLayout(toolbar)

            def change_pen_width(self, value):
                self.pen_width = value
                self.width_label.setText(f"{value}px")

            def choose_color(self):
                color = QColorDialog.getColor(self.pen_color, self)
                if color.isValid():
                    self.pen_color = color

            def clear_canvas(self):
                self.image.fill(Qt.white)
                self.update()

            def save_canvas(self):
                from PySide6.QtWidgets import QFileDialog

                file_path, _ = QFileDialog.getSaveFileName(
                    self,
                    "Lưu Canvas",
                    "canvas.png",
                    "Images (*.png *.jpg *.bmp)"
                )

                if file_path:
                    self.image.save(file_path)
                    show_message(self, "Thành công", f"Đã lưu canvas vào:\n{file_path}", "info")

            def mousePressEvent(self, event):
                if event.button() == Qt.LeftButton:
                    self.drawing = True
                    self.last_point = event.pos()

            def mouseMoveEvent(self, event):
                if event.buttons() & Qt.LeftButton and self.drawing:
                    painter = QPainter(self.image)
                    painter.setPen(QPen(self.pen_color, self.pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                    painter.drawLine(self.last_point, event.pos())
                    self.last_point = event.pos()
                    self.update()

            def mouseReleaseEvent(self, event):
                if event.button() == Qt.LeftButton:
                    self.drawing = False

            def paintEvent(self, event):
                painter = QPainter(self)
                painter.drawImage(self.rect(), self.image, self.image.rect())

        # Tạo và hiển thị canvas window
        canvas = CanvasWindow(parent)
        canvas.exec()

    except Exception as e:
        logger.error(f"Lỗi open canvas window: {e}")
        if parent:
            show_message(parent, "Lỗi", f"Không thể mở Canvas:\n{str(e)}", "error")

def launch_app(app_path: str) -> bool:
    """Launch an application"""
    try:
        import subprocess
        subprocess.Popen(app_path, shell=True)
        return True
    except Exception as e:
        logger.error(f"Failed to launch app: {app_path}, error: {e}")
        return False


def create_window_id(app_id: str) -> str:
    """
    Create unique window ID for an app

    Args:
        app_id: Application ID

    Returns:
        Unique window ID
    """
    import uuid
    from datetime import datetime

    # Create unique ID combining app_id and timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_suffix = str(uuid.uuid4())[:8]

    return f"win_{app_id}_{timestamp}_{unique_suffix}"


def show_notification(title: str, message: str, notification_type: str = "info") -> bool:
    """
    Show system notification

    Args:
        title: Notification title
        message: Notification message
        notification_type: Type (info, warning, error, success)

    Returns:
        True if shown successfully
    """
    try:
        from PySide6.QtWidgets import QSystemTrayIcon
        if QSystemTrayIcon.isSystemTrayAvailable():
            # Use system tray notification
            return True
        else:
            # Fallback to console
            print(f"[{notification_type.upper()}] {title}: {message}")
            return True
    except Exception as e:
        logger.error(f"Failed to show notification: {e}")
        return False


def play_sound(sound_name: str) -> bool:
    """
    Play notification sound

    Args:
        sound_name: Sound file name (without extension)

    Returns:
        True if played successfully
    """
    try:
        # Simple beep fallback
        import sys
        if sys.platform == "win32":
            import winsound
            winsound.Beep(1000, 200)  # 1000Hz for 200ms
        return True
    except Exception as e:
        logger.error(f"Failed to play sound: {e}")
        return False