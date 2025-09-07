# ui_qt/windows/dashboard_window_qt/repositories/app_repository.py
"""
Repository layer để quản lý dữ liệu apps trong Dashboard
Bao gồm: CRUD operations, data models, database/JSON storage
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
import logging

# Setup logger
logger = logging.getLogger(__name__)


# ========== ENUMS & CONSTANTS ==========

class AppCategory(Enum):
    """Danh mục ứng dụng"""
    LEARNING = "learning"  # Học tập
    MANAGEMENT = "management"  # Quản lý
    REPORTS = "reports"  # Báo cáo
    EXERCISES = "exercises"  # Bài tập
    TOOLS = "tools"  # Công cụ
    SYSTEM = "system"  # Hệ thống
    CUSTOM = "custom"  # Tùy chỉnh


class AppStatus(Enum):
    """Trạng thái app"""
    ACTIVE = "active"  # Đang hoạt động
    INACTIVE = "inactive"  # Không hoạt động
    UPDATING = "updating"  # Đang cập nhật
    ERROR = "error"  # Lỗi
    MAINTENANCE = "maintenance"  # Bảo trì


class AppPermission(Enum):
    """Quyền truy cập app"""
    PUBLIC = "public"  # Ai cũng dùng được
    TEACHER = "teacher"  # Chỉ giáo viên
    ADMIN = "admin"  # Chỉ admin
    STUDENT = "student"  # Chỉ học sinh
    CUSTOM = "custom"  # Tùy chỉnh


# ========== DATA MODELS ==========

@dataclass
class AppModel:
    """Model đại diện cho một ứng dụng"""

    # Thông tin cơ bản
    id: str  # ID unique của app
    name: str  # Tên hiển thị
    display_name: str  # Tên đầy đủ tiếng Việt
    description: str = ""  # Mô tả app
    version: str = "1.0.0"  # Phiên bản

    # Phân loại
    category: AppCategory = AppCategory.TOOLS  # Danh mục
    tags: List[str] = field(default_factory=list)  # Tags để search

    # Đường dẫn & resources
    module_path: str = ""  # Path Python module (vd: ui_qt.windows.student_window_qt)
    class_name: str = ""  # Tên class (vd: StudentWindowQt)
    icon_name: str = "app"  # Tên icon
    icon_path: str = ""  # Đường dẫn icon tùy chỉnh
    exe_path: str = ""  # Đường dẫn exe (nếu là external app)

    # Trạng thái & quyền
    status: AppStatus = AppStatus.ACTIVE  # Trạng thái hiện tại
    permission: AppPermission = AppPermission.PUBLIC  # Quyền truy cập
    enabled: bool = True  # Có được bật không
    pinned: bool = False  # Có được ghim không

    # UI Configuration
    window_type: str = "window"  # "window", "dialog", "widget"
    default_size: Tuple[int, int] = (800, 600)  # Kích thước mặc định
    resizable: bool = True  # Có thể resize
    maximizable: bool = True  # Có thể maximize
    minimizable: bool = True  # Có thể minimize
    always_on_top: bool = False  # Luôn ở trên

    # Thống kê sử dụng
    usage_count: int = 0  # Số lần mở
    last_used: Optional[datetime] = None  # Lần cuối sử dụng
    total_time: int = 0  # Tổng thời gian sử dụng (seconds)
    favorite_rank: int = 0  # Độ ưu tiên (0-10)

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    author: str = "System"  # Tác giả/người tạo

    # Custom data
    settings: Dict[str, Any] = field(default_factory=dict)  # Settings riêng của app
    shortcuts: List[str] = field(default_factory=list)  # Phím tắt
    dependencies: List[str] = field(default_factory=list)  # Dependencies

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        # Convert enums to string
        data['category'] = self.category.value
        data['status'] = self.status.value
        data['permission'] = self.permission.value
        # Convert datetime to string
        if self.last_used:
            data['last_used'] = self.last_used.isoformat()
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppModel':
        """Create from dictionary"""
        # Convert string to enums
        if 'category' in data:
            data['category'] = AppCategory(data['category'])
        if 'status' in data:
            data['status'] = AppStatus(data['status'])
        if 'permission' in data:
            data['permission'] = AppPermission(data['permission'])
        # Convert string to datetime
        if 'last_used' in data and data['last_used']:
            data['last_used'] = datetime.fromisoformat(data['last_used'])
        if 'created_at' in data:
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data:
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)


# ========== REPOSITORY CLASS ==========

class AppRepository:
    """
    Repository để quản lý CRUD operations cho apps
    Có thể dùng SQLite hoặc JSON storage
    """

    def update_all_apps_pinned(self):
        """Force update tất cả apps thành pinned=True"""
        apps = self.get_all_apps()
        updated_count = 0

        for app in apps:
            if not app.pinned:
                app.pinned = True
                self.update_app(app.id, {'pinned': True})
                updated_count += 1
                logger.info(f"Updated {app.id} to pinned=True")

        logger.info(f"Updated {updated_count} apps to pinned=True")
        return updated_count
    def __init__(self, storage_type: str = "json", storage_path: str = None):
        """
        Initialize repository

        Args:
            storage_type: "json" hoặc "sqlite"
            storage_path: Đường dẫn file storage
        """
        self.storage_type = storage_type

        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            # Default paths
            if storage_type == "json":
                self.storage_path = Path("dashboard_apps.json")
            else:
                self.storage_path = Path("dashboard.db")

        # Ensure storage exists
        self._init_storage()

        # Load default apps if empty
        if self.get_all_apps():
            pinned_count = len([a for a in self.get_all_apps() if a.pinned])
            if pinned_count < 10:  # Nếu ít hơn 10 apps được pinned
                logger.info("Updating apps to pinned=True...")
                self.update_all_apps_pinned()

    def _init_storage(self):
        """Initialize storage (create file/tables if not exist)"""
        if self.storage_type == "json":
            if not self.storage_path.exists():
                self.storage_path.write_text("[]")
        else:
            self._init_database()

    def _init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(str(self.storage_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS apps (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                display_name TEXT,
                description TEXT,
                version TEXT,
                category TEXT,
                tags TEXT,
                module_path TEXT,
                class_name TEXT,
                icon_name TEXT,
                icon_path TEXT,
                exe_path TEXT,
                status TEXT,
                permission TEXT,
                enabled INTEGER,
                pinned INTEGER,
                window_type TEXT,
                default_width INTEGER,
                default_height INTEGER,
                resizable INTEGER,
                maximizable INTEGER,
                minimizable INTEGER,
                always_on_top INTEGER,
                usage_count INTEGER,
                last_used TEXT,
                total_time INTEGER,
                favorite_rank INTEGER,
                created_at TEXT,
                updated_at TEXT,
                author TEXT,
                settings TEXT,
                shortcuts TEXT,
                dependencies TEXT
            )
        """)

        conn.commit()
        conn.close()

    def _load_default_apps(self):
        """Load danh sách apps mặc định"""
        default_apps = [
            # === HỌC TẬP ===
            AppModel(
                id="student_manager",
                name="Học sinh",
                display_name="Quản lý học sinh",
                description="Quản lý thông tin học sinh, theo dõi tiến độ",
                category=AppCategory.MANAGEMENT,
                tags=["học sinh", "student", "quản lý"],
                module_path="ui_qt.windows.student_window_qt",
                class_name="StudentWindowQt",
                icon_name="students",
                permission=AppPermission.TEACHER,
                pinned=True,
                favorite_rank=1
            ),

            AppModel(
                id="group_manager",
                name="Nhóm học",
                display_name="Quản lý nhóm học",
                description="Tạo và quản lý các nhóm học tập",
                category=AppCategory.MANAGEMENT,
                tags=["nhóm", "group", "lớp học"],
                module_path="ui_qt.windows.group_window_qt",
                class_name="GroupWindowQt",
                icon_name="groups",
                permission=AppPermission.TEACHER,
                pinned=True,
                favorite_rank=2
            ),

            AppModel(
                id="package_manager",
                name="Gói học",
                display_name="Quản lý gói học",
                description="Quản lý các gói học và khóa học",
                category=AppCategory.MANAGEMENT,
                tags=["gói học", "package", "khóa học"],
                module_path="ui_qt.windows.package_window_qt",
                class_name="PackageWindowQt",
                icon_name="package",
                permission=AppPermission.TEACHER,
                pinned=True,
                favorite_rank=3
            ),

            AppModel(
                id="attendance_report",
                name="Chuyên cần",
                display_name="Báo cáo chuyên cần",
                description="Theo dõi và báo cáo chuyên cần học sinh",
                category=AppCategory.REPORTS,
                tags=["chuyên cần", "điểm danh", "attendance"],
                module_path="ui_qt.windows.attendance_report_window_qt",
                class_name="AttendanceReportWindowQt",
                icon_name="attendance",
                permission=AppPermission.TEACHER,
                pinned=True,
                favorite_rank=4
            ),

            AppModel(
                id="main_calendar",
                name="Lịch dạy",
                display_name="Lịch dạy (Main)",
                description="Xem và quản lý lịch dạy học",
                category=AppCategory.MANAGEMENT,
                tags=["lịch", "calendar", "schedule"],
                module_path="ui_qt.main_window",
                class_name="MainWindow",
                icon_name="calendar",
                permission=AppPermission.PUBLIC,
                pinned=True,
                favorite_rank=5
            ),

            # === BÀI TẬP & CÂU HỎI ===
            AppModel(
                id="assign_exercise",
                name="Giao bài",
                display_name="Giao bài tập",
                description="Giao bài tập cho học sinh",
                category=AppCategory.EXERCISES,
                tags=["bài tập", "exercise", "assignment"],
                module_path="ui_qt.windows.assign_exercise_window_qt",
                class_name="AssignExerciseWindowQt",
                icon_name="assignment",
                permission=AppPermission.TEACHER,
                pinned = True,
                favorite_rank = 6
            ),

            AppModel(
                id="submit_exercise",
                name="Nộp bài",
                display_name="Nộp bài tập",
                description="Học sinh nộp bài tập",
                category=AppCategory.EXERCISES,
                tags=["nộp bài", "submit", "homework"],
                module_path="ui_qt.windows.submit_exercise_window_qt",
                class_name="SubmitExerciseWindowQt",
                icon_name="submit",
                permission=AppPermission.STUDENT,
                pinned=True,
                favorite_rank=7
            ),

            AppModel(
                id="submitted_exercises",
                name="Đã nộp",
                display_name="Bài tập đã nộp",
                description="Quản lý bài tập đã nộp",
                category=AppCategory.EXERCISES,
                tags=["đã nộp", "submitted", "completed"],
                module_path="ui_qt.windows.submitted_exercise_manager_window_qt",
                class_name="SubmittedExerciseManagerWindowQt",
                icon_name="submitted",
                permission=AppPermission.TEACHER,
                pinned=True,
                favorite_rank=8
            ),

            AppModel(
                id="question_bank",
                name="Ngân hàng câu hỏi",
                display_name="Ngân hàng câu hỏi",
                description="Quản lý kho câu hỏi và đề thi",
                category=AppCategory.LEARNING,
                tags=["câu hỏi", "question", "bank", "đề thi"],
                module_path="ui_qt.windows.question_bank.views.main_window",
                class_name="QuestionBankMainWindow",
                icon_name="question_bank",
                permission=AppPermission.TEACHER,
                pinned=True,
                favorite_rank=9,
                default_size=(1200, 800)
            ),

            AppModel(
                id="exercise_suggestion",
                name="Gợi ý bài",
                display_name="Gợi ý bài tập",
                description="Gợi ý bài tập phù hợp cho học sinh",
                category=AppCategory.EXERCISES,
                tags=["gợi ý", "suggest", "recommendation"],
                module_path="ui_qt.windows.exercise_suggestion_window_qt",
                class_name="ExerciseSuggestionWindowQt",
                icon_name="suggest",
                permission=AppPermission.TEACHER,
                pinned=True,
                favorite_rank=10
            ),

            AppModel(
                id="create_test",
                name="Tạo đề PDF",
                display_name="Tạo đề thi PDF",
                description="Tạo đề thi và xuất ra file PDF",
                category=AppCategory.EXERCISES,
                tags=["đề thi", "test", "pdf", "exam"],
                module_path="ui_qt.windows.create_test_window_qt",
                class_name="CreateTestWindowQt",
                icon_name="test",
                permission=AppPermission.TEACHER,
                pinned=True,
                favorite_rank=11
            ),

            AppModel(
                id="exercise_tree",
                name="Cây thư mục",
                display_name="Cây thư mục bài tập",
                description="Quản lý cấu trúc thư mục bài tập",
                category=AppCategory.EXERCISES,
                tags=["thư mục", "folder", "tree", "structure"],
                module_path="ui_qt.windows.exercise_tree_manager_qt",
                class_name="ExerciseTreeManagerQt",
                icon_name="folder",
                permission=AppPermission.TEACHER,
                pinned=True,
                favorite_rank=12
            ),

            # === BÁO CÁO & ĐÁNH GIÁ ===
            AppModel(
                id="progress_report",
                name="Tiến độ",
                display_name="Báo cáo tiến độ",
                description="Theo dõi tiến độ học tập của học sinh",
                category=AppCategory.REPORTS,
                tags=["tiến độ", "progress", "report"],
                module_path="ui_qt.windows.progress_report_window_qt",
                class_name="ProgressReportWindowQt",
                icon_name="progress",
                permission=AppPermission.TEACHER,
                pinned=True,
                favorite_rank=13
            ),

            AppModel(
                id="skill_report",
                name="Năng lực",
                display_name="Báo cáo năng lực",
                description="Đánh giá năng lực học sinh",
                category=AppCategory.REPORTS,
                tags=["năng lực", "skill", "ability"],
                module_path="ui_qt.windows.student_skill_report_window_qt",
                class_name="StudentSkillReportWindowQt",
                icon_name="skill",
                permission=AppPermission.TEACHER,
                pinned=True,
                favorite_rank=14
            ),

            AppModel(
                id="skill_rating",
                name="Đánh giá",
                display_name="Đánh giá kỹ năng",
                description="Đánh giá chi tiết kỹ năng học sinh",
                category=AppCategory.REPORTS,
                tags=["đánh giá", "rating", "evaluation"],
                module_path="ui_qt.windows.skill_rating_window_qt",
                class_name="SkillRatingWindowQt",
                icon_name="rating",
                permission=AppPermission.TEACHER,
                pinned=True,
                favorite_rank=15
            ),

            AppModel(
                id="group_suggestion",
                name="Gợi ý nhóm",
                display_name="Gợi ý phân nhóm",
                description="Gợi ý cách phân nhóm học sinh hiệu quả",
                category=AppCategory.REPORTS,
                tags=["gợi ý nhóm", "group suggestion", "clustering"],
                module_path="ui_qt.windows.group_suggestion_window_qt",
                class_name="GroupSuggestionWindowQt",
                icon_name="group_suggest",
                permission=AppPermission.TEACHER,
                pinned=True,
                favorite_rank=16
            ),

            AppModel(
                id="salary_report",
                name="Học phí",
                display_name="Báo cáo học phí",
                description="Quản lý và báo cáo học phí",
                category=AppCategory.REPORTS,
                tags=["học phí", "salary", "tuition", "payment"],
                module_path="ui_qt.windows.salary_window_qt",
                class_name="SalaryWindowQt",
                icon_name="salary",
                permission=AppPermission.ADMIN,
                pinned=True,
                favorite_rank=17
            )
        ]

        # Save all default apps
        for app in default_apps:
            self.add_app(app)

        logger.info(f"Đã load {len(default_apps)} apps mặc định")

    # ========== CRUD OPERATIONS ==========

    def get_all_apps(self) -> List[AppModel]:
        """
        Lấy tất cả apps

        Returns:
            List các AppModel
        """
        if self.storage_type == "json":
            return self._get_all_apps_json()
        else:
            return self._get_all_apps_db()

    def _get_all_apps_json(self) -> List[AppModel]:
        """Get all apps from JSON"""
        try:
            data = json.loads(self.storage_path.read_text(encoding='utf-8'))
            return [AppModel.from_dict(item) for item in data]
        except Exception as e:
            logger.error(f"Lỗi đọc apps từ JSON: {e}")
            return []

    def _get_all_apps_db(self) -> List[AppModel]:
        """Get all apps from database"""
        conn = sqlite3.connect(str(self.storage_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM apps")
        rows = cursor.fetchall()
        conn.close()

        apps = []
        for row in rows:
            data = dict(row)
            # Parse JSON fields
            if data.get('tags'):
                data['tags'] = json.loads(data['tags'])
            if data.get('settings'):
                data['settings'] = json.loads(data['settings'])
            if data.get('shortcuts'):
                data['shortcuts'] = json.loads(data['shortcuts'])
            if data.get('dependencies'):
                data['dependencies'] = json.loads(data['dependencies'])
            # Parse tuple
            if data.get('default_width') and data.get('default_height'):
                data['default_size'] = (data.pop('default_width'), data.pop('default_height'))
            # Convert bool
            data['enabled'] = bool(data.get('enabled'))
            data['pinned'] = bool(data.get('pinned'))
            data['resizable'] = bool(data.get('resizable'))
            data['maximizable'] = bool(data.get('maximizable'))
            data['minimizable'] = bool(data.get('minimizable'))
            data['always_on_top'] = bool(data.get('always_on_top'))

            apps.append(AppModel.from_dict(data))

        return apps

    def get_app_by_id(self, app_id: str) -> Optional[AppModel]:
        """
        Lấy app theo ID

        Args:
            app_id: ID của app

        Returns:
            AppModel hoặc None
        """
        apps = self.get_all_apps()
        for app in apps:
            if app.id == app_id:
                return app
        return None

    def add_app(self, app: AppModel) -> bool:
        """
        Thêm app mới

        Args:
            app: AppModel object

        Returns:
            True nếu thành công
        """
        try:
            # Check if exists
            if self.get_app_by_id(app.id):
                logger.warning(f"App {app.id} đã tồn tại")
                return False

            if self.storage_type == "json":
                return self._add_app_json(app)
            else:
                return self._add_app_db(app)

        except Exception as e:
            logger.error(f"Lỗi thêm app: {e}")
            return False

    def _add_app_json(self, app: AppModel) -> bool:
        """Add app to JSON"""
        apps = self.get_all_apps()
        apps.append(app)

        data = [a.to_dict() for a in apps]
        self.storage_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        return True

    def _add_app_db(self, app: AppModel) -> bool:
        """Add app to database"""
        conn = sqlite3.connect(str(self.storage_path))
        cursor = conn.cursor()

        data = app.to_dict()
        # Convert complex types to JSON
        data['tags'] = json.dumps(data.get('tags', []))
        data['settings'] = json.dumps(data.get('settings', {}))
        data['shortcuts'] = json.dumps(data.get('shortcuts', []))
        data['dependencies'] = json.dumps(data.get('dependencies', []))
        # Split tuple
        if 'default_size' in data:
            data['default_width'] = data['default_size'][0]
            data['default_height'] = data['default_size'][1]
            del data['default_size']

        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])

        cursor.execute(
            f"INSERT INTO apps ({columns}) VALUES ({placeholders})",
            list(data.values())
        )

        conn.commit()
        conn.close()
        return True

    def update_app(self, app_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Cập nhật thông tin app

        Args:
            app_id: ID của app
            update_data: Dict chứa fields cần update

        Returns:
            True nếu thành công
        """
        try:
            app = self.get_app_by_id(app_id)
            if not app:
                logger.warning(f"Không tìm thấy app {app_id}")
                return False

            # Update fields
            for key, value in update_data.items():
                if hasattr(app, key):
                    setattr(app, key, value)

            app.updated_at = datetime.now()

            if self.storage_type == "json":
                return self._update_app_json(app_id, app)
            else:
                return self._update_app_db(app_id, app)

        except Exception as e:
            logger.error(f"Lỗi update app: {e}")
            return False

    def _update_app_json(self, app_id: str, app: AppModel) -> bool:
        """Update app in JSON"""
        apps = self.get_all_apps()

        for i, a in enumerate(apps):
            if a.id == app_id:
                apps[i] = app
                break

        data = [a.to_dict() for a in apps]
        self.storage_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        return True

    def _update_app_db(self, app_id: str, app: AppModel) -> bool:
        """Update app in database"""
        conn = sqlite3.connect(str(self.storage_path))
        cursor = conn.cursor()

        data = app.to_dict()
        # Convert complex types
        data['tags'] = json.dumps(data.get('tags', []))
        data['settings'] = json.dumps(data.get('settings', {}))
        data['shortcuts'] = json.dumps(data.get('shortcuts', []))
        data['dependencies'] = json.dumps(data.get('dependencies', []))
        # Split tuple
        if 'default_size' in data:
            data['default_width'] = data['default_size'][0]
            data['default_height'] = data['default_size'][1]
            del data['default_size']

        # Remove id from update
        del data['id']

        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])

        cursor.execute(
            f"UPDATE apps SET {set_clause} WHERE id = ?",
            list(data.values()) + [app_id]
        )

        conn.commit()
        conn.close()
        return True

    def delete_app(self, app_id: str) -> bool:
        """
        Xóa app

        Args:
            app_id: ID của app

        Returns:
            True nếu thành công
        """
        try:
            if not self.get_app_by_id(app_id):
                logger.warning(f"Không tìm thấy app {app_id}")
                return False

            if self.storage_type == "json":
                return self._delete_app_json(app_id)
            else:
                return self._delete_app_db(app_id)

        except Exception as e:
            logger.error(f"Lỗi xóa app: {e}")
            return False

    def _delete_app_json(self, app_id: str) -> bool:
        """Delete app from JSON"""
        apps = self.get_all_apps()
        apps = [a for a in apps if a.id != app_id]

        data = [a.to_dict() for a in apps]
        self.storage_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
        return True

    def _delete_app_db(self, app_id: str) -> bool:
        """Delete app from database"""
        conn = sqlite3.connect(str(self.storage_path))
        cursor = conn.cursor()

        cursor.execute("DELETE FROM apps WHERE id = ?", (app_id,))

        conn.commit()
        conn.close()
        return True

    # ========== QUERY METHODS ==========

    def get_apps_by_category(self, category: AppCategory) -> List[AppModel]:
        """
        Lấy apps theo danh mục

        Args:
            category: AppCategory enum

        Returns:
            List các AppModel
        """
        apps = self.get_all_apps()
        return [a for a in apps if a.category == category]

    def get_pinned_apps(self) -> List[AppModel]:
        """
        Lấy apps được ghim và sắp xếp theo favorite_rank

        Returns:
            List các AppModel được ghim, sắp xếp theo favorite_rank tăng dần
        """
        # Debug: Kiểm tra storage
        logger.info(f"Storage path: {self.storage_path}")
        logger.info(f"Storage exists: {self.storage_path.exists()}")

        # Lấy tất cả apps
        all_apps = self.get_all_apps()
        logger.info(f"Total apps in storage: {len(all_apps)}")

        # KIỂM TRA: Nếu ít hơn expected, reload
        if len(all_apps) < 17:  # Biết có 17 apps mặc định
            logger.warning(f"Only {len(all_apps)} apps found, reloading defaults...")
            self._load_default_apps()
            all_apps = self.get_all_apps()
            logger.info(f"After reload: {len(all_apps)} apps")

        # Lọc apps có pinned=True
        pinned = [a for a in all_apps if a.pinned]
        # Sắp xếp theo favorite_rank
        pinned.sort(key=lambda x: x.favorite_rank if x.favorite_rank > 0 else 999)

        return pinned
    def get_recent_apps(self, limit: int = 10) -> List[AppModel]:
        """
        Lấy apps sử dụng gần đây

        Args:
            limit: Số lượng apps

        Returns:
            List các AppModel, sắp xếp theo last_used
        """
        apps = self.get_all_apps()
        # Filter apps có last_used
        recent = [a for a in apps if a.last_used]
        # Sort by last_used descending
        recent.sort(key=lambda x: x.last_used, reverse=True)
        return recent[:limit]

    def get_most_used_apps(self, limit: int = 10) -> List[AppModel]:
        """
        Lấy apps được dùng nhiều nhất

        Args:
            limit: Số lượng apps

        Returns:
            List các AppModel, sắp xếp theo usage_count
        """
        apps = self.get_all_apps()
        # Sort by usage_count descending
        apps.sort(key=lambda x: x.usage_count, reverse=True)
        return apps[:limit]

    def get_favorite_apps(self, limit: int = 10) -> List[AppModel]:
        """
        Lấy apps yêu thích

        Args:
            limit: Số lượng apps

        Returns:
            List các AppModel, sắp xếp theo favorite_rank
        """
        apps = self.get_all_apps()
        # Filter apps có favorite_rank > 0
        favorites = [a for a in apps if a.favorite_rank > 0]
        # Sort by favorite_rank descending
        favorites.sort(key=lambda x: x.favorite_rank, reverse=True)
        return favorites[:limit]

    def search_apps(self, keyword: str) -> List[AppModel]:
        """
        Tìm kiếm apps theo từ khóa

        Args:
            keyword: Từ khóa tìm kiếm

        Returns:
            List các AppModel khớp
        """
        keyword = keyword.lower()
        apps = self.get_all_apps()
        results = []

        for app in apps:
            # Search in name, display_name, description, tags
            searchable = [
                             app.name.lower(),
                             app.display_name.lower(),
                             app.description.lower()
                         ] + [tag.lower() for tag in app.tags]

            if any(keyword in s for s in searchable):
                results.append(app)

        return results

    def get_apps_by_permission(self, permission: AppPermission) -> List[AppModel]:
        """
        Lấy apps theo quyền truy cập

        Args:
            permission: AppPermission enum

        Returns:
            List các AppModel
        """
        apps = self.get_all_apps()
        return [a for a in apps if a.permission == permission or a.permission == AppPermission.PUBLIC]

    # ========== STATISTICS METHODS ==========

    def update_usage_stats(self, app_id: str, session_time: int = 0) -> bool:
        """
        Cập nhật thống kê sử dụng app

        Args:
            app_id: ID của app
            session_time: Thời gian sử dụng trong session (seconds)

        Returns:
            True nếu thành công
        """
        return self.update_app(app_id, {
            'usage_count': self.get_app_by_id(app_id).usage_count + 1,
            'last_used': datetime.now(),
            'total_time': self.get_app_by_id(app_id).total_time + session_time
        })

    def get_usage_statistics(self) -> Dict[str, Any]:
        """
        Lấy thống kê tổng quan

        Returns:
            Dictionary chứa các thống kê
        """
        apps = self.get_all_apps()

        stats = {
            'total_apps': len(apps),
            'active_apps': len([a for a in apps if a.status == AppStatus.ACTIVE]),
            'pinned_apps': len([a for a in apps if a.pinned]),
            'total_usage': sum(a.usage_count for a in apps),
            'total_time': sum(a.total_time for a in apps),
            'by_category': {},
            'by_permission': {}
        }

        # Stats by category
        for category in AppCategory:
            category_apps = self.get_apps_by_category(category)
            stats['by_category'][category.value] = {
                'count': len(category_apps),
                'usage': sum(a.usage_count for a in category_apps)
            }

        # Stats by permission
        for permission in AppPermission:
            perm_apps = self.get_apps_by_permission(permission)
            stats['by_permission'][permission.value] = len(perm_apps)

        return stats

    # ========== IMPORT/EXPORT ==========

    def export_to_json(self, file_path: str) -> bool:
        """
        Export all apps to JSON file

        Args:
            file_path: Đường dẫn file output

        Returns:
            True nếu thành công
        """
        try:
            apps = self.get_all_apps()
            data = [a.to_dict() for a in apps]

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return True
        except Exception as e:
            logger.error(f"Lỗi export: {e}")
            return False

    def import_from_json(self, file_path: str, replace: bool = False) -> int:
        """
        Import apps from JSON file

        Args:
            file_path: Đường dẫn file input
            replace: True = replace all, False = merge

        Returns:
            Số apps đã import
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if replace:
                # Clear all existing apps
                for app in self.get_all_apps():
                    self.delete_app(app.id)

            count = 0
            for item in data:
                app = AppModel.from_dict(item)
                if self.add_app(app):
                    count += 1

            return count

        except Exception as e:
            logger.error(f"Lỗi import: {e}")
            return 0