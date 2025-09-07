#!/usr/bin/env python3
"""
Script tạo sơ đồ cây thư mục với mô tả tự động
Chạy: python generate_tree.py
"""

import os
from pathlib import Path

# Cấu hình
# (Cấu hình ignore mở rộng - loại bỏ các thư mục không cần thiết)
IGNORE_DIRS = {
    # Môi trường ảo và cache
    '.venv', 'venv', '__pycache__', '.pytest_cache',
    'node_modules', '.npm', '.yarn',

    # Build và dist
    'build', 'dist', 'output', '_internal',
    '.egg-info', '*.egg-info',

    # IDE và editor
    '.idea', '.vscode', '.vs',

    # Version control
    '.git', '.svn', '.hg',

    # OS files
    '.DS_Store', 'Thumbs.db',

    # Logs và temp
    'logs', 'log', 'tmp', 'temp',

    # Thư mục cụ thể của dự án (có thể tùy chỉnh)
    'assets'  # Bỏ comment nếu muốn ẩn thư mục assets
}

# (Các file riêng lẻ cần ignore)
IGNORE_FILES = {
    # Compiled files
    '*.pyc', '*.pyo', '*.pyd', '*.so', '*.dll','*.json','*.png','*.txt', '*.pdf'

    # Temp files
    '*.tmp', '*.temp', '*.log', '*.bak',

    # IDE files
    '*.swp', '*.swo', '*~',

    # Specific files
    'desktop.ini', '.DS_Store', 'Thumbs.db'
}

# (Pattern ignore - các pattern cần bỏ qua)
IGNORE_PATTERNS = [
    # Files bắt đầu với dấu chấm (trừ file đặc biệt)
    lambda name: name.startswith('.') and name not in DESCRIPTIONS,

    # Files kết thúc với extension cụ thể
    lambda name: any(name.endswith(ext.replace('*', '')) for ext in IGNORE_FILES
                     if ext.startswith('*')),

    # Thư mục chứa "cache" hoặc "temp"
    lambda name: any(word in name.lower() for word in ['cache', 'temp', 'tmp']),

    # Files executable trên Windows
    lambda name: name.endswith('.exe') or name.endswith('.msi')
]#(Định nghĩa các thư mục/file đặc biệt cần mô tả)
# (Định nghĩa các thư mục/file đặc biệt cần mô tả - mở rộng)
DESCRIPTIONS = {
    # Files cấu hình Python
    'requirements.txt': 'Danh sách thư viện Python',
    'setup.py': 'File setup Python package',
    'pyproject.toml': 'Cấu hình dự án Python hiện đại',
    'main.py': 'File khởi chạy chính',
    'main_qt.py': 'File khởi chạy giao diện Qt',
    'app_qt.py': 'Ứng dụng Qt chính',
    'constants.py': 'Các hằng số của ứng dụng',
    'database.py': 'Quản lý cơ sở dữ liệu',
    'utils.py': 'Các tiện ích chung',

    # Thư mục quan trọng
    'ui_qt': 'Giao diện người dùng Qt',
    'core': 'Logic cốt lõi ứng dụng',
    'windows': 'Các cửa sổ giao diện',
    'board': 'Module bảng vẽ',
    'resources': 'Tài nguyên (icon, images, styles)',
    'question_bank': 'Module ngân hàng câu hỏi',

    # Files đặc biệt
    '.gitignore': 'Cấu hình Git ignore',
    'README.md': 'Tài liệu mô tả dự án',
    'LICENSE': 'Giấy phép sử dụng',

    # Config files có thể muốn hiển thị
    'config.ini': 'File cấu hình ứng dụng',
    'settings.json': 'Cài đặt JSON'
}


def should_ignore(name, is_dir=False):
    """Kiểm tra có nên bỏ qua file/folder không - logic cải tiến"""

    # (Kiểm tra thư mục theo danh sách IGNORE_DIRS)
    if is_dir and name in IGNORE_DIRS:
        return True

    # (Kiểm tra file theo danh sách IGNORE_FILES)
    if not is_dir and name in IGNORE_FILES:
        return True

    # (Kiểm tra theo patterns)
    for pattern_func in IGNORE_PATTERNS:
        if pattern_func(name):
            return True

    # (Luôn giữ các file có mô tả đặc biệt)
    if name in DESCRIPTIONS:
        return False

    # (Ignore file quá lớn - tránh hiển thị file binary)
    if not is_dir:
        try:
            # Chỉ ignore file có extension nguy hiểm
            dangerous_exts = ['.dll', '.exe', '.pyd', '.so', '.dylib']
            if any(name.endswith(ext) for ext in dangerous_exts):
                return True
        except:
            pass

    return False

def generate_tree(root_path, prefix="", is_last=True, max_depth=10, current_depth=0):
    """Tạo cây thư mục với mô tả"""
    if current_depth >= max_depth:
        return ""

    root = Path(root_path)
    if not root.exists():
        return f"Thư mục {root_path} không tồn tại!\n"

    # Lấy danh sách items và sắp xếp
    try:
        items = sorted([item for item in root.iterdir()
                        if not should_ignore(item.name, item.is_dir())])
    except PermissionError:
        return f"{prefix}[Không có quyền truy cập]\n"

    result = ""

    for i, item in enumerate(items):
        is_last_item = (i == len(items) - 1)

        # Tạo prefix cho item hiện tại
        if current_depth == 0:
            current_prefix = ""
            next_prefix = ""
        else:
            current_prefix = prefix + ("└─ " if is_last_item else "├─ ")
            next_prefix = prefix + ("   " if is_last_item else "│  ")

        # Tên + mô tả
        name = item.name
        description = DESCRIPTIONS.get(name, "")
        desc_text = f" ← {description}" if description else ""

        if current_depth == 0:
            result += f"{name}/{desc_text}\n"
        else:
            result += f"{current_prefix}{name}{'/' if item.is_dir() else ''}{desc_text}\n"

        # Đệ quy cho thư mục con
        if item.is_dir():
            result += generate_tree(
                item,
                next_prefix,
                is_last_item,
                max_depth,
                current_depth + 1
            )

    return result


def main():
    """Hàm chính"""
    # Thư mục gốc (có thể thay đổi)
    root_directory = "."  # Thư mục hiện tại
    output_file = "project_structure.txt"

    print("Đang tạo sơ đồ cây thư mục...")

    # Tạo sơ đồ
    tree_content = generate_tree(root_directory, max_depth=5)

    # Thêm header
    header = f"""# Cấu trúc dự án - {Path(root_directory).resolve().name}
Tạo tự động bởi generate_tree.py

"""

    full_content = header + tree_content

    # Ghi file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(full_content)
        print(f"✅ Đã tạo {output_file}")

        # In ra màn hình
        print("\n" + "=" * 50)
        print(full_content)

    except Exception as e:
        print(f"❌ Lỗi khi ghi file: {e}")


if __name__ == "__main__":
    main()