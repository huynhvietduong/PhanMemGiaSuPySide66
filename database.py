import sqlite3
from tkinter import messagebox
class DatabaseManager:
    def __init__(self, db_name="data/giasu_management.db"):
        self.db_name = db_name
        self.conn = self.create_connection()
        self._initialize_schema()
        self.upgrade_database_schema()
        self.upgrade_exercise_tree_schema()
        if not hasattr(self, '_question_bank_upgraded'):
            self.upgrade_question_bank_schema()
            self._question_bank_upgraded = True

    def create_connection(self):
        try:
            conn = sqlite3.connect(self.db_name)
            conn.execute("PRAGMA foreign_keys = 1")
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            print(f"Lỗi kết nối CSDL: {e}"); return None

    def _initialize_schema(self):
        c = self.conn.cursor()
        try:
            c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS packages (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, sessions INTEGER NOT NULL, price REAL NOT NULL)")
            c.execute("CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, grade TEXT NOT NULL)")
            c.execute("CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, grade TEXT NOT NULL, phone TEXT, start_date TEXT NOT NULL, status TEXT NOT NULL, group_id INTEGER, notes TEXT, package_id INTEGER, cycle_start_date TEXT, FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL, FOREIGN KEY (package_id) REFERENCES packages(id) ON DELETE SET NULL)")
            c.execute("CREATE TABLE IF NOT EXISTS schedule (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL, day_of_week TEXT NOT NULL, time_slot TEXT NOT NULL, FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE)")
            c.execute("CREATE TABLE IF NOT EXISTS attendance (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL, group_id INTEGER NOT NULL, session_date TEXT NOT NULL, status TEXT NOT NULL, make_up_status TEXT, UNIQUE(student_id, group_id, session_date), FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE, FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE)")
            c.execute("CREATE TABLE IF NOT EXISTS session_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL, session_date TEXT NOT NULL, topic TEXT, homework TEXT, UNIQUE(group_id, session_date), FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE)")
            c.execute("CREATE TABLE IF NOT EXISTS cancelled_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL, cancelled_date TEXT NOT NULL, UNIQUE(group_id, cancelled_date), FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE)")
            c.execute("CREATE TABLE IF NOT EXISTS makeup_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, attendance_id INTEGER UNIQUE NOT NULL, student_id INTEGER NOT NULL, session_date TEXT NOT NULL, time_slot TEXT, host_group_id INTEGER, is_private INTEGER DEFAULT 1, FOREIGN KEY (attendance_id) REFERENCES attendance(id) ON DELETE CASCADE, FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE, FOREIGN KEY (host_group_id) REFERENCES groups(id) ON DELETE CASCADE)")
            c.execute("CREATE TABLE IF NOT EXISTS student_skills (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL, chu_de TEXT NOT NULL, ngay_danh_gia TEXT NOT NULL, diem INTEGER CHECK (diem BETWEEN 1 AND 5), nhan_xet TEXT, FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE)")
            # ========== TẠO CẤU TRÚC NGÂN HÀNG CÂU HỎI TỐI ƯU ========== #
            # Bảng câu hỏi chính với cấu trúc đầy đủ
            c.execute("""
                CREATE TABLE IF NOT EXISTS question_bank (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    -- Nội dung câu hỏi
                    content_text TEXT NOT NULL,
                    content_type TEXT DEFAULT 'text',
                    content_data BLOB,
                    content_metadata TEXT,

                    -- Đáp án
                    answer_type TEXT DEFAULT 'text',
                    answer_data TEXT,
                    correct_answer TEXT,
                    answer_explanation TEXT,

                    -- Phân loại
                    tree_id INTEGER NOT NULL,
                    difficulty_level TEXT DEFAULT 'medium',
                    question_type TEXT DEFAULT 'knowledge',
                    subject_code TEXT,
                    grade_level TEXT,

                    -- Metadata
                    status TEXT DEFAULT 'active',
                    usage_count INTEGER DEFAULT 0,
                    avg_score REAL DEFAULT 0,
                    estimated_time INTEGER DEFAULT 2,

                    -- Thời gian
                    created_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    modified_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT DEFAULT 'system',

                    FOREIGN KEY (tree_id) REFERENCES exercise_tree(id) ON DELETE RESTRICT
                )
            """)

            # Bảng tags nâng cao
            c.execute("""
                CREATE TABLE IF NOT EXISTS question_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER NOT NULL,
                    tag_name TEXT NOT NULL,
                    tag_type TEXT DEFAULT 'custom',
                    color TEXT DEFAULT '#6c757d',
                    created_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT DEFAULT 'user',
                    FOREIGN KEY (question_id) REFERENCES question_bank(id) ON DELETE CASCADE,
                    UNIQUE(question_id, tag_name)
                )
            """)

            # Bảng lịch sử chi tiết
            c.execute("""
                CREATE TABLE IF NOT EXISTS question_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    field_changed TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    change_reason TEXT,
                    changed_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    changed_by TEXT DEFAULT 'user',
                    session_id TEXT,
                    FOREIGN KEY (question_id) REFERENCES question_bank(id) ON DELETE CASCADE
                )
            """)

            # Bảng thống kê sử dụng
            c.execute("""
                CREATE TABLE IF NOT EXISTS question_statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER NOT NULL,
                    total_attempts INTEGER DEFAULT 0,
                    correct_attempts INTEGER DEFAULT 0,
                    avg_time_spent INTEGER DEFAULT 0,
                    difficulty_rating REAL DEFAULT 0,
                    last_used_date TEXT,
                    created_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (question_id) REFERENCES question_bank(id) ON DELETE CASCADE
                )
            """)
            # --- Trong file database.py, trong _initialize_schema(self) sau các bảng hiện có ---
            c.execute("""
                CREATE TABLE IF NOT EXISTS exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chu_de   TEXT NOT NULL,
                    ten_bai  TEXT NOT NULL,
                    loai_tap TEXT NOT NULL,      -- 'text' | 'image' | ...
                    noi_dung TEXT NOT NULL,      -- nội dung văn bản hoặc đường dẫn ảnh
                    ghi_chu  TEXT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS assigned_exercises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id  INTEGER NOT NULL,
                    exercise_id INTEGER NOT NULL,
                    ngay_giao   TEXT    NOT NULL,
                    trang_thai  TEXT    DEFAULT 'Chưa nộp',
                    ghi_chu     TEXT,
                    FOREIGN KEY(student_id)  REFERENCES students(id)  ON DELETE CASCADE,
                    FOREIGN KEY(exercise_id) REFERENCES exercises(id) ON DELETE CASCADE,
                    UNIQUE(student_id, exercise_id, ngay_giao)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS exercise_submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id    INTEGER NOT NULL,
                    assignment_id INTEGER NOT NULL,
                    ngay_nop      TEXT    NOT NULL,
                    file_path     TEXT    NOT NULL,
                    diem          REAL,
                    nhan_xet      TEXT,
                    FOREIGN KEY(student_id)    REFERENCES students(id) ON DELETE CASCADE,
                    FOREIGN KEY(assignment_id) REFERENCES assigned_exercises(id) ON DELETE CASCADE
                )
            """)

            # Bảng lưu các file bài giảng gắn với buổi học
            c.execute("""
                CREATE TABLE IF NOT EXISTS lesson_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    file_path TEXT NOT NULL,
                    file_type TEXT,
                    added_time TEXT,
                    title TEXT,
                    notes TEXT,
                    FOREIGN KEY (session_id) REFERENCES session_logs(id) ON DELETE CASCADE
                )
            """)
            # --- THÊM VÀO _initialize_schema (sau các bảng khác) ---
            c.execute("""
            CREATE TABLE IF NOT EXISTS assigned_exercises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                exercise_id INTEGER NOT NULL,
                ngay_giao TEXT NOT NULL,
                trang_thai TEXT DEFAULT 'Đã giao', -- Đã giao / Đã nộp / Quá hạn...
                ghi_chu TEXT,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            )
            """)

            c.execute("""
            CREATE TABLE IF NOT EXISTS exercise_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                assignment_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                ngay_nop TEXT NOT NULL,
                diem REAL,
                nhan_xet TEXT,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY (assignment_id) REFERENCES assigned_exercises(id) ON DELETE CASCADE
            )
            """)
            c.execute("""
                        CREATE TABLE IF NOT EXISTS exercise_tree (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            parent_id INTEGER,
                            name TEXT NOT NULL,
                            level TEXT NOT NULL,
                            description TEXT DEFAULT '',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (parent_id) REFERENCES exercise_tree (id)
                        )
                    """)

            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Lỗi khi khởi tạo schema: {e}")

    def upgrade_database_schema(self):
        c = self.conn.cursor()
        try:
            c.execute("PRAGMA table_info(attendance)")
            cols = [info[1] for info in c.fetchall()]
            if 'make_up_status' not in cols:
                c.execute("ALTER TABLE attendance ADD COLUMN make_up_status TEXT DEFAULT 'Chưa sắp xếp'")
            c.execute("PRAGMA table_info(students)")
            cols = [info[1] for info in c.fetchall()]
            if 'package_id' not in cols:
                c.execute("ALTER TABLE students ADD COLUMN package_id INTEGER REFERENCES packages(id) ON DELETE SET NULL")
            if 'cycle_start_date' not in cols:
                c.execute("ALTER TABLE students ADD COLUMN cycle_start_date TEXT")
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Lỗi khi nâng cấp CSDL: {e}")
            self.conn.rollback()

    def upgrade_question_bank_schema(self):
        """Nâng cấp schema cho bảng question_bank và các bảng liên quan"""
        c = self.conn.cursor()
        try:
            # Kiểm tra và nâng cấp bảng question_bank
            c.execute("PRAGMA table_info(question_bank)")
            existing_columns = [column[1] for column in c.fetchall()]

            # Thêm các cột mới nếu thiếu
            new_columns = [
                ('content_metadata', 'TEXT'),
                ('answer_type', "TEXT DEFAULT 'text'"),
                ('answer_data', 'TEXT'),
                ('correct_answer', 'TEXT'),
                ('answer_explanation', 'TEXT'),
                ('difficulty_level', "TEXT DEFAULT 'medium'"),
                ('question_type', "TEXT DEFAULT 'knowledge'"),
                ('subject_code', 'TEXT'),
                ('grade_level', 'TEXT'),
                ('status', "TEXT DEFAULT 'active'"),
                ('usage_count', 'INTEGER DEFAULT 0'),
                ('avg_score', 'REAL DEFAULT 0'),
                ('estimated_time', 'INTEGER DEFAULT 2'),
                ('modified_date', "TEXT DEFAULT CURRENT_TIMESTAMP"),
                ('created_by', "TEXT DEFAULT 'system'")
            ]

            for col_name, col_type in new_columns:
                if col_name not in existing_columns:
                    try:
                        c.execute(f"ALTER TABLE question_bank ADD COLUMN {col_name} {col_type}")
                        print(f"✅ Đã thêm cột {col_name}")
                    except sqlite3.Error as e:
                        if "duplicate column name" not in str(e).lower():
                            print(f"⚠️ Lỗi thêm cột {col_name}: {e}")

            # Tạo indexes để tối ưu hiệu suất
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_question_tree_id ON question_bank(tree_id)",
                "CREATE INDEX IF NOT EXISTS idx_question_difficulty ON question_bank(difficulty_level)",
                "CREATE INDEX IF NOT EXISTS idx_question_type ON question_bank(question_type)",
                "CREATE INDEX IF NOT EXISTS idx_question_subject ON question_bank(subject_code)",
                "CREATE INDEX IF NOT EXISTS idx_question_status ON question_bank(status)",
                "CREATE INDEX IF NOT EXISTS idx_question_created ON question_bank(created_date)",
                "CREATE INDEX IF NOT EXISTS idx_tags_question_id ON question_tags(question_id)",
                "CREATE INDEX IF NOT EXISTS idx_tags_name ON question_tags(tag_name)",
                "CREATE INDEX IF NOT EXISTS idx_history_question_id ON question_history(question_id)",
                "CREATE INDEX IF NOT EXISTS idx_history_date ON question_history(changed_date)",
                "CREATE INDEX IF NOT EXISTS idx_tree_parent ON exercise_tree(parent_id)",
                "CREATE INDEX IF NOT EXISTS idx_tree_level ON exercise_tree(level)"
            ]

            for index_sql in indexes:
                try:
                    c.execute(index_sql)
                except sqlite3.Error:
                    pass  # Index có thể đã tồn tại

            self.conn.commit()

        except sqlite3.Error as e:
            print(f"❌ Lỗi nâng cấp schema question_bank: {e}")
            self.conn.rollback()
    def execute_query(self, query, params=(), fetch=None):
        c = self.conn.cursor()
        try:
            c.execute(query, params)
            self.conn.commit()
            if fetch == 'one': return c.fetchone()
            if fetch == 'all': return c.fetchall()
            return c.lastrowid
        except sqlite3.Error as e:
            print(f"Lỗi truy vấn: {query} - {e}")
            messagebox.showerror("Lỗi CSDL", f"Có lỗi xảy ra: {e}"); return None

    def add_student_skill(self, student_id, chu_de, ngay_danh_gia, diem, nhan_xet=""):
        query = "INSERT INTO student_skills (student_id, chu_de, ngay_danh_gia, diem, nhan_xet) VALUES (?, ?, ?, ?, ?)"
        return self.execute_query(query, (student_id, chu_de, ngay_danh_gia, diem, nhan_xet))

    def update_student_skill(self, skill_id, diem, nhan_xet=""):
        query = "UPDATE student_skills SET diem = ?, nhan_xet = ? WHERE id = ?"
        return self.execute_query(query, (diem, nhan_xet, skill_id))

    def delete_student_skill(self, skill_id):
        query = "DELETE FROM student_skills WHERE id = ?"
        return self.execute_query(query, (skill_id,))

    def delete_question(self, q_id):
        self.conn.execute("DELETE FROM question_bank WHERE id = ?;", (q_id,)); self.conn.commit()

    def get_all_students(self):
        query = "SELECT id, name FROM students"
        cursor = self.conn.execute(query)
        rows = cursor.fetchall()
        return [{"id": r[0], "name": r[1]} for r in rows]

    # Thêm hàm này vào file: database.py

    def get_groups_with_details(self):
        """Lấy danh sách nhóm kèm sĩ số và lịch học đã được định dạng."""
        groups = self.execute_query("SELECT id, name, grade FROM groups ORDER BY name", fetch='all') or []
        detailed_groups = []

        for group in groups:
            group_id = group['id']
            count_result = self.execute_query("SELECT COUNT(id) as count FROM students WHERE group_id = ?", (group_id,),
                                              fetch='one')
            student_count = count_result['count'] if count_result else 0

            schedule_data = self.execute_query("SELECT day_of_week, time_slot FROM schedule WHERE group_id = ?",
                                               (group_id,), fetch='all') or []
            schedule_str = "; ".join([f"{row['day_of_week']}-{row['time_slot']}" for row in schedule_data])

            detailed_groups.append({
                "id": group_id,
                "name": group['name'],
                "grade": group['grade'],
                "student_count": student_count,
                "schedule_str": schedule_str
            })

        return detailed_groups

    def get_all_students_for_display(self):
        """Lấy danh sách học sinh để hiển thị lên bảng, kèm tên nhóm."""
        query = """
            SELECT s.id, s.name, s.grade, g.name as group_name 
            FROM students s 
            LEFT JOIN groups g ON s.group_id = g.id 
            ORDER BY s.name
        """
        return self.execute_query(query, fetch='all') or []

    def get_student_details_by_id(self, student_id):
        """Lấy toàn bộ thông tin chi tiết của một học sinh theo ID."""
        query = "SELECT * FROM students WHERE id = ?"
        student_data = self.execute_query(query, (student_id,), fetch='one')
        if not student_data:
            return None

        # Lấy thêm tên nhóm và tên gói học
        group_name_res = self.execute_query("SELECT name FROM groups WHERE id = ?", (student_data['group_id'],),
                                            fetch='one')
        package_name_res = self.execute_query("SELECT name FROM packages WHERE id = ?", (student_data['package_id'],),
                                              fetch='one')

        # Chuyển đổi sqlite3.Row thành dict để dễ dàng thêm key mới
        details = dict(student_data)
        details['group_name'] = group_name_res[0] if group_name_res else ""
        details['package_name'] = package_name_res[0] if package_name_res else ""
        return details

    def add_student(self, student_data):
        """Thêm một học sinh mới vào CSDL."""
        query = """
            INSERT INTO students 
            (name, grade, phone, start_date, status, group_id, notes, package_id, cycle_start_date) 
            VALUES (?, ?, ?, ?, ?, ?, '', ?, ?)
        """
        params = (
            student_data['Họ tên'],
            student_data['Khối lớp'],
            student_data['SĐT'],
            student_data['start_date'],
            student_data['status'],
            student_data['group_id'],
            student_data['package_id'],
            student_data['cycle_start_date']
        )
        return self.execute_query(query, params)

    def update_student(self, student_id, student_data):
        """Cập nhật thông tin của một học sinh."""
        query = """
            UPDATE students SET 
            name=?, grade=?, phone=?, status=?, group_id=?, package_id=?, cycle_start_date=? 
            WHERE id=?
        """
        params = (
            student_data['Họ tên'],
            student_data['Khối lớp'],
            student_data['SĐT'],
            student_data['status'],
            student_data['group_id'],
            student_data['package_id'],
            student_data['cycle_start_date'],
            student_id
        )
        return self.execute_query(query, params)

    def delete_student_by_id(self, student_id):
        """Xóa một học sinh khỏi CSDL."""
        return self.execute_query("DELETE FROM students WHERE id=?", (student_id,))

    def get_attendance_report(self, start_date, end_date, hide_completed):
        """Lấy dữ liệu báo cáo chuyên cần đã xử lý."""
        base_query = """
            SELECT a.id, a.session_date, s.name, s.id as student_id, g.name as group_name, g.grade, a.status, a.make_up_status
            FROM attendance a 
            JOIN students s ON a.student_id = s.id 
            JOIN groups g ON a.group_id = g.id
            WHERE a.status LIKE 'Nghỉ%' AND a.session_date BETWEEN ? AND ? 
        """
        params = [start_date, end_date]

        if hide_completed:
            base_query += " AND a.make_up_status != 'Đã dạy bù' "

        base_query += " ORDER BY a.session_date DESC, s.name "

        report_data = []
        absent_sessions = self.execute_query(base_query, tuple(params), fetch='all') or []

        for row in absent_sessions:
            att_id = row['id']
            detailed_status = row['make_up_status']

            makeup_info = self.execute_query(
                "SELECT ms.session_date, ms.time_slot, host_g.name as host_group_name, ms.is_private, ms.host_group_id FROM makeup_sessions ms LEFT JOIN groups host_g ON ms.host_group_id = host_g.id WHERE ms.attendance_id = ?",
                (att_id,), fetch='one')

            if row['make_up_status'] == 'Đã lên lịch' and makeup_info:
                m_date, m_time, m_group, is_private, host_group_id = makeup_info
                if is_private == 1:
                    detailed_status = f"Dạy bù riêng ({m_date}, {m_time})"
                else:
                    detailed_status = f"Học bù với Nhóm {m_group} ({m_date})"

            report_data.append({
                'id': att_id,
                'session_date': row['session_date'],
                'student_name': row['name'],
                'student_id': row['student_id'],
                'group_name': row['group_name'],
                'group_grade': row['grade'],
                'status': row['status'],
                'detailed_status': detailed_status
            })
        return report_data
    def get_students_for_salary_report(self):
        """Lấy danh sách học sinh có đăng ký gói học để tính lương."""
        query = """
            SELECT s.name, s.grade, p.name as package_name, p.price
            FROM students s
            JOIN packages p ON s.package_id = p.id
            WHERE s.cycle_start_date IS NOT NULL AND s.cycle_start_date != ''
            ORDER BY s.grade
        """
        # Logic lọc theo chu kỳ sẽ được xử lý ở đây nếu cần trong tương lai
        return self.execute_query(query, fetch='all') or []

    def add_lesson_file(self, session_id, file_path, file_type, title="", notes=""):
        from datetime import datetime
        query = """
            INSERT INTO lesson_files (session_id, file_path, file_type, added_time, title, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (
            session_id,
            file_path,
            file_type,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            title,
            notes
        )
        return self.execute_query(query, params)

    # GIẢI PHÁP SỬA LỖI SQLite VÀ RuntimeError

    # ===================== BƯỚC 1: SỬA database.py =====================

    # Vị trí: Trong file database.py, phương thức upgrade_exercise_tree_schema
    # Hành động: THAY THẾ toàn bộ phương thức

    def upgrade_exercise_tree_schema(self):
        """Nâng cấp schema cho bảng exercise_tree"""
        c = self.conn.cursor()
        try:
            # Kiểm tra xem bảng có tồn tại không
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='exercise_tree'")
            if not c.fetchone():
                # Tạo bảng mới nếu chưa có
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
                # Kiểm tra và thêm các cột thiếu
                c.execute("PRAGMA table_info(exercise_tree)")
                columns = [column[1] for column in c.fetchall()]

                if 'description' not in columns:
                    # Thêm cột description với default value đơn giản
                    c.execute("ALTER TABLE exercise_tree ADD COLUMN description TEXT DEFAULT ''")
                    print("✅ Đã thêm cột description vào bảng exercise_tree")

                if 'created_at' not in columns:
                    # Thêm cột created_at với default value đơn giản
                    c.execute("ALTER TABLE exercise_tree ADD COLUMN created_at TEXT DEFAULT ''")
                    print("✅ Đã thêm cột created_at vào bảng exercise_tree")

                    # Cập nhật created_at cho các record hiện có
                    c.execute("""
                        UPDATE exercise_tree 
                        SET created_at = datetime('now') 
                        WHERE created_at = '' OR created_at IS NULL
                    """)
                    print("✅ Đã cập nhật created_at cho dữ liệu hiện có")

            self.conn.commit()
            return True

        except sqlite3.Error as e:
            print(f"❌ Lỗi nâng cấp schema exercise_tree: {e}")
            return False

    def get_table_columns(self, table_name):
        """Lấy danh sách tên cột của bảng"""
        try:
            c = self.conn.cursor()
            c.execute(f"PRAGMA table_info({table_name})")
            columns = [row[1] for row in c.fetchall()]  # row[1] là tên cột
            return columns
        except sqlite3.Error as e:
            print(f"Lỗi lấy thông tin cột: {e}")
            return []

    def column_exists(self, table_name, column_name):
        """Kiểm tra cột có tồn tại trong bảng không"""
        columns = self.get_table_columns(table_name)
        return column_name in columns

    def add_column_safely(self, table_name, column_name, column_type):
        """Thêm cột một cách an toàn (kiểm tra trước)"""
        if not self.column_exists(table_name, column_name):
            try:
                query = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                self.execute_query(query)
                print(f"✅ Đã thêm cột {column_name} vào bảng {table_name}")
                return True
            except sqlite3.Error as e:
                if "duplicate column name" not in str(e).lower():
                    print(f"❌ Lỗi thêm cột {column_name}: {e}")
                return False
        else:
            print(f"✅ Cột {column_name} đã tồn tại trong bảng {table_name}")
            return True
# ========== PHƯƠNG THỨC CRUD CHO NGÂN HÀNG CÂU HỎI ========== #
def create_question(self, question_data):
    """Tạo câu hỏi mới với cấu trúc đầy đủ"""
    query = """
        INSERT INTO question_bank (
            content_text, content_type, content_data, content_metadata,
            answer_type, answer_data, correct_answer, answer_explanation,
            tree_id, difficulty_level, question_type, subject_code, grade_level,
            status, estimated_time, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        question_data.get('content_text', ''),
        question_data.get('content_type', 'text'),
        question_data.get('content_data'),
        question_data.get('content_metadata'),
        question_data.get('answer_type', 'text'),
        question_data.get('answer_data'),
        question_data.get('correct_answer'),
        question_data.get('answer_explanation'),
        question_data.get('tree_id'),
        question_data.get('difficulty_level', 'medium'),
        question_data.get('question_type', 'knowledge'),
        question_data.get('subject_code'),
        question_data.get('grade_level'),
        question_data.get('status', 'active'),
        question_data.get('estimated_time', 2),
        question_data.get('created_by', 'user')
    )

    question_id = self.execute_query(query, params)

    # Lưu lịch sử tạo câu hỏi
    if question_id:
        self.save_question_history(question_id, 'CREATE', None, question_data.get('content_text', ''))

    return question_id


def update_question(self, question_id, question_data, changed_fields=None):
    """Cập nhật câu hỏi với tracking thay đổi"""
    # Lấy dữ liệu cũ để so sánh
    old_data = self.execute_query("SELECT * FROM question_bank WHERE id=?", (question_id,), fetch="one")
    if not old_data:
        return False

    # Chuẩn bị câu lệnh update
    update_fields = []
    params = []

    updatable_fields = [
        'content_text', 'content_type', 'content_data', 'content_metadata',
        'answer_type', 'answer_data', 'correct_answer', 'answer_explanation',
        'tree_id', 'difficulty_level', 'question_type', 'subject_code',
        'grade_level', 'status', 'estimated_time'
    ]

    for field in updatable_fields:
        if field in question_data:
            update_fields.append(f"{field}=?")
            params.append(question_data[field])

    if not update_fields:
        return False

    # Thêm modified_date
    update_fields.append("modified_date=CURRENT_TIMESTAMP")
    params.append(question_id)

    query = f"UPDATE question_bank SET {', '.join(update_fields)} WHERE id=?"

    success = self.execute_query(query, params)

    # Lưu lịch sử thay đổi
    if success and changed_fields:
        for field in changed_fields:
            if field in question_data and field in old_data:
                old_value = str(old_data[field] or '')
                new_value = str(question_data[field] or '')
                if old_value != new_value:
                    self.save_question_history(
                        question_id, 'UPDATE', field,
                        old_value, new_value
                    )

    return success


def delete_question(self, question_id):
    """Xóa câu hỏi và dữ liệu liên quan"""
    # Lưu lịch sử trước khi xóa
    question = self.execute_query("SELECT content_text FROM question_bank WHERE id=?", (question_id,), fetch="one")
    if question:
        self.save_question_history(question_id, 'DELETE', None, question['content_text'])

    # Xóa câu hỏi (cascade sẽ xóa tags và history)
    return self.execute_query("DELETE FROM question_bank WHERE id=?", (question_id,))


def save_question_history(self, question_id, action_type, field_changed=None, old_value='', new_value='', reason=''):
    """Lưu lịch sử thay đổi câu hỏi"""
    query = """
        INSERT INTO question_history (
            question_id, action_type, field_changed, old_value, new_value, change_reason
        ) VALUES (?, ?, ?, ?, ?, ?)
    """
    return self.execute_query(query, (question_id, action_type, field_changed, old_value, new_value, reason))


def add_question_tag(self, question_id, tag_name, tag_type='custom', color='#6c757d'):
    """Thêm tag cho câu hỏi"""
    query = """
        INSERT OR IGNORE INTO question_tags (question_id, tag_name, tag_type, color)
        VALUES (?, ?, ?, ?)
    """
    return self.execute_query(query, (question_id, tag_name, tag_type, color))


def remove_question_tag(self, question_id, tag_name):
    """Xóa tag khỏi câu hỏi"""
    return self.execute_query(
        "DELETE FROM question_tags WHERE question_id=? AND tag_name=?",
        (question_id, tag_name)
    )


def get_questions_by_criteria(self, tree_id=None, difficulty=None, subject=None, status='active', limit=None):
    """Lấy danh sách câu hỏi theo tiêu chí"""
    conditions = ["status=?"]
    params = [status]

    if tree_id:
        conditions.append("tree_id=?")
        params.append(tree_id)

    if difficulty:
        conditions.append("difficulty_level=?")
        params.append(difficulty)

    if subject:
        conditions.append("subject_code=?")
        params.append(subject)

    query = f"SELECT * FROM question_bank WHERE {' AND '.join(conditions)} ORDER BY created_date DESC"

    if limit:
        query += f" LIMIT {limit}"

    return self.execute_query(query, params, fetch="all") or []


def get_question_with_details(self, question_id):
    """Lấy câu hỏi với thông tin chi tiết (tags, lịch sử)"""
    # Lấy thông tin câu hỏi
    question = self.execute_query("SELECT * FROM question_bank WHERE id=?", (question_id,), fetch="one")
    if not question:
        return None

    # Lấy tags
    tags = self.execute_query("SELECT * FROM question_tags WHERE question_id=?", (question_id,), fetch="all") or []

    # Lấy lịch sử (5 bản ghi gần nhất)
    history = self.execute_query(
        "SELECT * FROM question_history WHERE question_id=? ORDER BY changed_date DESC LIMIT 5",
        (question_id,), fetch="all"
    ) or []

    return {
        'question': dict(question),
        'tags': [dict(tag) for tag in tags],
        'history': [dict(h) for h in history]
    }


def update_question_statistics(self, question_id, is_correct=None, time_spent=None):
    """Cập nhật thống kê sử dụng câu hỏi"""
    # Lấy hoặc tạo record thống kê
    stats = self.execute_query(
        "SELECT * FROM question_statistics WHERE question_id=?",
        (question_id,), fetch="one"
    )

    if not stats:
        # Tạo record mới
        self.execute_query(
            "INSERT INTO question_statistics (question_id, total_attempts, correct_attempts) VALUES (?, 0, 0)",
            (question_id,)
        )
        stats = {'total_attempts': 0, 'correct_attempts': 0, 'avg_time_spent': 0}

    # Cập nhật thống kê
    new_attempts = stats['total_attempts'] + 1
    new_correct = stats['correct_attempts'] + (1 if is_correct else 0)

    # Tính thời gian trung bình
    if time_spent:
        current_avg = stats.get('avg_time_spent', 0)
        new_avg = ((current_avg * stats['total_attempts']) + time_spent) / new_attempts
    else:
        new_avg = stats.get('avg_time_spent', 0)

    # Cập nhật database
    query = """
        UPDATE question_statistics 
        SET total_attempts=?, correct_attempts=?, avg_time_spent=?, last_used_date=CURRENT_TIMESTAMP
        WHERE question_id=?
    """
    self.execute_query(query, (new_attempts, new_correct, new_avg, question_id))

    # Cập nhật usage_count trong question_bank
    self.execute_query(
        "UPDATE question_bank SET usage_count=usage_count+1 WHERE id=?",
        (question_id,)
    )