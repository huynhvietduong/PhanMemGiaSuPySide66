#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Liệt kê cấu trúc thư mục và file Python trong question_bank
"""

import os
from pathlib import Path


def list_directory_structure(root_path, max_depth=10):
    """Liệt kê cấu trúc thư mục và file Python"""
    root = Path(root_path)

    if not root.exists():
        print(f"Đường dẫn không tồn tại: {root_path}")
        return

    print(f"📁 Cấu trúc thư mục: {root_path}")
    print("=" * 80)

    def scan_directory(path, prefix="", level=0):
        if level > max_depth:
            return

        try:
            items = sorted(path.iterdir())

            # Lọc chỉ lấy thư mục và file .py
            filtered_items = []
            for item in items:
                if item.is_dir() or item.suffix.lower() == '.py':
                    filtered_items.append(item)

            for i, item in enumerate(filtered_items):
                is_last = i == len(filtered_items) - 1
                current_prefix = "└── " if is_last else "├── "
                next_prefix = "    " if is_last else "│   "

                if item.is_dir():
                    print(f"{prefix}{current_prefix}📁 {item.name}/")
                    scan_directory(item, prefix + next_prefix, level + 1)
                else:
                    # Chỉ hiển thị file .py
                    print(f"{prefix}{current_prefix}🐍 {item.name}")

        except PermissionError:
            print(f"{prefix}└── ❌ (Không có quyền truy cập)")

    scan_directory(root)

    # Thống kê
    print("\n" + "=" * 80)
    count_stats(root)


def get_file_icon(extension):
    """Trả về icon cho loại file"""
    icons = {
        '.py': '🐍',
        '.txt': '📄',
        '.md': '📝',
        '.json': '📊',
        '.csv': '📈',
        '.xlsx': '📊',
        '.png': '🖼️',
        '.jpg': '🖼️',
        '.jpeg': '🖼️',
        '.gif': '🖼️',
        '.sql': '🗄️',
        '.db': '💾',
        '.sqlite': '💾',
        '.ini': '⚙️',
        '.cfg': '⚙️',
        '.log': '📋'
    }
    return icons.get(extension, '📄')


def count_stats(root_path):
    """Đếm thống kê file Python và folder"""
    folder_count = 0
    py_file_count = 0

    for item in Path(root_path).rglob('*'):
        if item.is_dir():
            folder_count += 1
        elif item.suffix.lower() == '.py':
            py_file_count += 1

    print("📊 THỐNG KÊ:")
    print(f"   📁 Tổng số thư mục: {folder_count}")
    print(f"   🐍 Tổng số file Python: {py_file_count}")


def main():
    # Đường dẫn cần quét
    target_path = r"C:\Users\lenovo\PycharmProjects\PhanMemGiaSuPySide6\ui_qt\windows\dashboard_window_qt"

    # Liệt kê cấu trúc
    list_directory_structure(target_path)

    # Lưu kết quả ra file text
    save_to_file = input("\n💾 Bạn có muốn lưu kết quả ra file text? (y/n): ")
    if save_to_file.lower() == 'y':
        output_file = "question_bank_python_files.txt"

        # Redirect output to file
        import sys
        original_stdout = sys.stdout

        with open(output_file, 'w', encoding='utf-8') as f:
            sys.stdout = f
            list_directory_structure(target_path)

        sys.stdout = original_stdout
        print(f"✅ Đã lưu kết quả vào file: {output_file}")


if __name__ == "__main__":
    main()