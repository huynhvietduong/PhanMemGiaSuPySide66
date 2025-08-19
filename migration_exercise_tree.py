import sqlite3
import os
from datetime import datetime


def migrate_exercise_tree_table_fixed():
    """Script migration sửa lỗi SQLite default value"""

    db_path = "data/giasu_management.db"

    if not os.path.exists(db_path):
        print(f"❌ Không tìm thấy database: {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        print("🔍 Kiểm tra cấu trúc bảng exercise_tree...")

        # Kiểm tra bảng có tồn tại không
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='exercise_tree'")
        if not c.fetchone():
            print("📝 Tạo bảng exercise_tree mới...")
            c.execute("""
                CREATE TABLE exercise_tree (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id INTEGER,
                    name TEXT NOT NULL,
                    level TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    created_at TEXT DEFAULT '',
                    FOREIGN KEY (parent_id) REFERENCES exercise_tree (id)
                )
            """)
            print("✅ Đã tạo bảng exercise_tree")
        else:
            # Kiểm tra các cột
            c.execute("PRAGMA table_info(exercise_tree)")
            columns = [column[1] for column in c.fetchall()]
            print(f"📋 Các cột hiện có: {columns}")

            # Thêm cột description nếu thiếu
            if 'description' not in columns:
                print("➕ Thêm cột description...")
                c.execute("ALTER TABLE exercise_tree ADD COLUMN description TEXT DEFAULT ''")
                print("✅ Đã thêm cột description")
            else:
                print("✅ Cột description đã tồn tại")

            # Thêm cột created_at nếu thiếu
            if 'created_at' not in columns:
                print("➕ Thêm cột created_at...")
                c.execute("ALTER TABLE exercise_tree ADD COLUMN created_at TEXT DEFAULT ''")

                # Cập nhật created_at cho các record hiện có
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                c.execute("UPDATE exercise_tree SET created_at = ? WHERE created_at = '' OR created_at IS NULL",
                          (current_time,))

                print("✅ Đã thêm cột created_at và cập nhật dữ liệu")
            else:
                print("✅ Cột created_at đã tồn tại")

        conn.commit()
        conn.close()

        print("🎉 Migration hoàn tất!")
        return True

    except sqlite3.Error as e:
        print(f"❌ Lỗi migration: {e}")
        return False


if __name__ == "__main__":
    migrate_exercise_tree_table_fixed()