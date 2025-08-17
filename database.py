import sqlite3
from tkinter import messagebox
class DatabaseManager:
    def __init__(self, db_name="data/giasu_management.db"):
        self.db_name = db_name
        self.conn = self.create_connection()
        self._initialize_schema()
        self.upgrade_database_schema()

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
            c.execute("""
                CREATE TABLE IF NOT EXISTS question_bank (id INTEGER PRIMARY KEY AUTOINCREMENT,content_text TEXT, options TEXT,correct TEXT, tree_id INTEGER,content_image TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
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
                    UNIQUE(parent_id, name, level)
                );
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
            c.execute("PRAGMA table_info(question_bank)")
            cols = [info[1] for info in c.fetchall()]
            if 'content_text' not in cols:
                c.execute("ALTER TABLE question_bank ADD COLUMN content_text TEXT")
            c.execute("PRAGMA table_info(question_bank)")
            cols = [info[1] for info in c.fetchall()]
            if 'chu_de' not in cols:
                c.execute("ALTER TABLE question_bank ADD COLUMN chu_de TEXT")
            if 'do_kho' not in cols:
                c.execute("ALTER TABLE question_bank ADD COLUMN do_kho TEXT")
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Lỗi khi nâng cấp CSDL: {e}")

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
