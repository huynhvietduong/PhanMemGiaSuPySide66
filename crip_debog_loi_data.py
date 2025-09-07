# Script debug để tìm chính xác dòng SQL gây lỗi

import sqlite3
import re


def debug_sql_error():
    """Tìm chính xác SQL nào gây lỗi"""

    # Test các SQL statements riêng lẻ
    test_sqls = [
        # Test comment styles
        "CREATE TABLE test1 (id INTEGER PRIMARY KEY, name TEXT)",  # No comment - should work
        "CREATE TABLE test2 (id INTEGER PRIMARY KEY, name TEXT) -- comment",  # SQL comment - should work
        "CREATE TABLE test3 (id INTEGER PRIMARY KEY, name TEXT) /* comment */",  # C-style comment - should work
        # "CREATE TABLE test4 (id INTEGER PRIMARY KEY, name TEXT) # comment", # Python comment - will fail
    ]

    conn = sqlite3.connect(":memory:")

    for i, sql in enumerate(test_sqls):
        try:
            print(f"Testing SQL {i + 1}: {sql[:50]}...")
            conn.execute(sql)
            print(f"  ✅ SUCCESS")
        except Exception as e:
            print(f"  ❌ ERROR: {e}")

    conn.close()


def find_problematic_sql_in_file(file_path="database.py"):
    """Tìm SQL có vấn đề trong file"""

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Tìm tất cả SQL strings
    sql_patterns = [
        r'c\.execute\(\s*"""(.*?)"""\s*\)',
        r'c\.execute\(\s*\'\'\'(.*?)\'\'\'\s*\)',
        r'c\.execute\(\s*"([^"]*?)"\s*\)',
        r'c\.execute\(\s*\'([^\']*?)\'\s*\)'
    ]

    problematic_lines = []

    for pattern in sql_patterns:
        matches = re.finditer(pattern, content, re.DOTALL)
        for match in matches:
            sql_content = match.group(1)
            if '#' in sql_content:
                # Tìm số dòng
                start_pos = match.start()
                line_num = content[:start_pos].count('\n') + 1
                problematic_lines.append((line_num, sql_content.strip()[:100]))

    if problematic_lines:
        print("🔍 Tìm thấy SQL có comment # (có thể gây lỗi):")
        for line_num, sql_preview in problematic_lines:
            print(f"  Dòng {line_num}: {sql_preview}...")
    else:
        print("✅ Không tìm thấy SQL có comment # trong file")

    return problematic_lines


def check_recent_changes():
    """Kiểm tra thay đổi gần đây có thể gây lỗi"""

    print("🔍 KIỂM TRA NGUYÊN NHÂN LỖI:")
    print("=" * 50)

    # 1. Kiểm tra phiên bản
    import sys
    print(f"Python version: {sys.version_info}")
    print(f"SQLite version: {sqlite3.sqlite_version}")
    print(f"SQLite module version: {sqlite3.version}")

    # 2. Kiểm tra file database.py
    try:
        problematic = find_problematic_sql_in_file("database.py")
        if problematic:
            print(f"\n⚠️ Tìm thấy {len(problematic)} SQL có thể có vấn đề")
        else:
            print("\n✅ File database.py không có vấn đề về comment")
    except FileNotFoundError:
        print("\n❌ Không tìm thấy file database.py")

    # 3. Test SQLite behavior
    print(f"\n🧪 TEST SQLITE COMMENT SUPPORT:")
    debug_sql_error()

    # 4. Kiểm tra git changes (nếu có)
    try:
        import subprocess
        result = subprocess.run(['git', 'log', '--oneline', '-5'],
                                capture_output=True, text=True)
        if result.returncode == 0:
            print(f"\n📝 5 COMMIT GẦN NHẤT:")
            print(result.stdout)
    except:
        print("\n📝 Không thể kiểm tra git history")


def quick_fix_sql_comments(file_path="database.py", backup=True):
    """Sửa nhanh tất cả comment # trong SQL"""

    if backup:
        import shutil
        shutil.copy(file_path, f"{file_path}.backup")
        print(f"✅ Đã backup file thành {file_path}.backup")

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Đếm số lần thay thế
    original_content = content

    # Thay thế # trong SQL strings
    def fix_sql_comment(match):
        sql_part = match.group(1)
        # Thay # thành -- trong SQL, nhưng giữ nguyên # trong Python comment
        fixed_sql = re.sub(r'(\s+)#([^\n]*)', r'\1--\2', sql_part)
        return f'"""{fixed_sql}"""'

    # Áp dụng fix cho các SQL strings
    content = re.sub(r'c\.execute\(\s*"""(.*?)"""\s*\)', fix_sql_comment, content, flags=re.DOTALL)

    changes = len(re.findall(r'#', original_content)) - len(re.findall(r'#', content))

    if changes > 0:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Đã sửa {changes} comment # trong SQL")
        return True
    else:
        print("ℹ️ Không có comment # nào cần sửa")
        return False


if __name__ == "__main__":
    print("🔍 CHẨN ĐOÁN LỖI SQL COMMENT")
    print("=" * 40)
    check_recent_changes()

    print(f"\n🛠️ TỰ ĐỘNG SỬA LỖI?")
    response = input("Nhấn 'y' để tự động sửa file database.py: ")
    if response.lower() == 'y':
        quick_fix_sql_comments()
        print("🎉 Hoàn thành! Thử chạy lại ứng dụng.")