#!/usr/bin/env python3
"""
Script tạo sơ đồ cây thư mục với mô tả tự động
Chạy: python generate_tree.py
"""

import os
from pathlib import Path

# Cấu hình
IGNORE_DIRS = {'.git', '__pycache__', '.vscode', 'node_modules', '.idea', 'venv', '.env'}
IGNORE_FILES = {'.gitignore', '.DS_Store', '*.pyc', '*.pyo'}

# Mô tả cho từng thư mục/file (tùy chỉnh theo dự án)
DESCRIPTIONS = {
    'board': 'Module Bảng vẽ (Drawing Board)',
    'core': 'Lõi render + hợp đồng (không phụ thuộc UI)',
    'canvas_widget.py': 'Canvas trung lập: vẽ nền trắng, ảnh, lớp mực (ink)',
    'data_models.py': 'Mẫu dữ liệu dùng chung: Stroke, Img',
    'tool_api.py': 'Giao diện Tool (Protocol): on_activate/deactivate, events',
    'state': 'Trạng thái bảng vẽ (không dính UI)',
    'board_state.py': 'Quản lý pages (strokes + images theo trang)',
    'io': 'Vào/ra dữ liệu (định dạng file)',
    'file_io.py': 'Lưu/Mở .board.json với encode/decode ảnh PNG base64',
    'tools': 'Mỗi công cụ 1 file, độc lập engine',
    'pen_tool.py': 'Bút vẽ freehand: Ghi Stroke(line) vào state',
    'eraser_tool.py': 'Tẩy nét freehand với CompositionMode_Clear',
    'erase_area_tool.py': 'Tẩy theo vùng: Rect/Lasso với overlay',
    'shape_tool.py': 'Vẽ hình cơ bản: line/rect/oval',
    'select_tool.py': 'Chọn/di chuyển/resize ảnh',
    'screen_snip.py': 'Chụp màn hình: SnipController + ScreenSnipOverlay',
    'ui': 'Thành phần giao diện tái sử dụng',
    'toolbar.py': 'QToolBar đóng gói: chọn tool, màu, độ dày',
    'width_menu.py': 'Popover chọn độ dày (slider + mốc nhanh)',
    'window.py': 'DrawingBoardWindowQt (orchestrator): khởi tạo tất cả'
}


def should_ignore(name, is_dir=False):
    """Kiểm tra có nên bỏ qua file/folder không"""
    if name in IGNORE_DIRS and is_dir:
        return True
    if name.startswith('.') and name not in DESCRIPTIONS:
        return True
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