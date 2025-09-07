# DEBUG SCRIPT - debug_question_bank_import.py
# Tạo file này để kiểm tra lỗi import cụ thể

import sys
import traceback


def test_import_question_bank():
    """Test import QuestionBankWindowQt để tìm lỗi cụ thể"""

    print("🔍 Đang kiểm tra import QuestionBankWindowQt...")

    try:
        print("1. Kiểm tra import PySide6...")
        from PySide6 import QtCore, QtGui, QtWidgets
        print("✅ PySide6 OK")

        print("2. Kiểm tra import typing...")
        from typing import List, Dict
        print("✅ typing OK")

        print("3. Kiểm tra import json, os, re...")
        import json, os, re
        print("✅ json, os, re OK")

        print("4. Kiểm tra import datetime...")
        from datetime import datetime
        print("✅ datetime OK")

        print("5. Kiểm tra import docx...")
        try:
            from docx.oxml.text.paragraph import CT_P
            from docx.oxml.table import CT_Tbl
            print("✅ docx OK")
        except ImportError as e:
            print(f"⚠️ docx import warning: {e}")
            print("   (Có thể bỏ qua nếu chưa cài python-docx)")

        print("6. Kiểm tra import QtWidgets components...")
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QKeySequence, QShortcut
        print("✅ QMenu, QKeySequence, QShortcut OK")

        print("7. Thử import module question_bank_window_qt...")
        import ui_qt.windows.question_bank_window_qt as qb_module
        print("✅ Module import OK")

        print("8. Thử lấy class QuestionBankWindowQt...")
        QuestionBankWindowQt = getattr(qb_module, 'QuestionBankWindowQt')
        print("✅ Class QuestionBankWindowQt OK")

        print("9. Kiểm tra class có callable không...")
        if callable(QuestionBankWindowQt):
            print("✅ Class có thể khởi tạo được")
        else:
            print("❌ Class không thể khởi tạo")

        print("\n🎉 TẤT CẢ IMPORT THÀNH CÔNG!")
        print("✅ QuestionBankWindowQt sẵn sàng sử dụng")

        return True

    except Exception as e:
        print(f"\n❌ LỖI IMPORT: {e}")
        print(f"📝 Chi tiết lỗi:")
        traceback.print_exc()

        print(f"\n💡 GỢI Ý SỬA LỖI:")

        if "No module named" in str(e):
            print("- Kiểm tra đường dẫn file")
            print("- Đảm bảo có __init__.py trong thư mục")

        elif "QShortcut" in str(e):
            print("- Sửa import QShortcut từ QtGui thay vì QtWidgets")

        elif "cannot import name" in str(e):
            print("- Kiểm tra tên class trong file")
            print("- Kiểm tra syntax error trong file")

        elif "syntax" in str(e).lower():
            print("- Kiểm tra syntax error trong question_bank_window_qt.py")
            print("- Kiểm tra indent, dấu ngoặc, dấu phẩy...")

        else:
            print("- Kiểm tra dependencies")
            print("- Kiểm tra version PySide6")

        return False


def check_file_structure():
    """Kiểm tra cấu trúc file"""
    print("\n📁 KIỂM TRA CẤU TRÚC FILE:")

    files_to_check = [
        "ui_qt/__init__.py",
        "ui_qt/windows/__init__.py",
        "ui_qt/windows/question_bank_window_qt.py",
        "ui_qt/windows/#dashboard_window_qt.py"
    ]

    for file_path in files_to_check:
        if os.path.exists(file_path):
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - THIẾU FILE")


def check_python_path():
    """Kiểm tra Python path"""
    print(f"\n🐍 PYTHON PATH:")
    for path in sys.path:
        print(f"  - {path}")


if __name__ == "__main__":
    print("=" * 60)
    print("🔧 DEBUG QUESTIONBANKWINDOWQT IMPORT")
    print("=" * 60)

    # Thêm current directory vào path
    import os

    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

    check_python_path()
    check_file_structure()

    success = test_import_question_bank()

    print("\n" + "=" * 60)
    if success:
        print("🎉 KẾT LUẬN: QuestionBankWindowQt có thể import được!")
        print("   Lỗi có thể nằm ở chỗ khác trong #dashboard_window_qt.py")
    else:
        print("❌ KẾT LUẬN: Có lỗi import cần sửa")
        print("   Hãy sửa các lỗi trên trước khi chạy lại ứng dụng")
    print("=" * 60)