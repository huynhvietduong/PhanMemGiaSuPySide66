#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script tự động tạo cấu trúc module Question Bank
Chạy: python create_question_bank_module.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime


class QuestionBankModuleGenerator:
    """Generator tạo cấu trúc module Question Bank hoàn chỉnh"""

    def __init__(self, base_path="question_bank"):
        self.base_path = Path(base_path)
        self.created_files = []
        self.created_dirs = []

    def create_directory_structure(self):
        """Tạo cấu trúc thư mục"""
        directories = [
            # Root
            "",

            # Core
            "core",

            # Database
            "database",

            # UI
            "ui",
            "ui/toolbars",
            "ui/panels",
            "ui/dialogs",

            # Widgets
            "widgets",
            "widgets/viewers",
            "widgets/editors",
            "widgets/tables",

            # Managers
            "managers",

            # Utils
            "utils",

            # Services
            "services",

            # Styles
            "styles",

            # Resources
            "resources",
            "resources/icons",
            "resources/translations",
            "resources/templates",

            # Tests
            "tests",
            "tests/test_managers",
            "tests/test_widgets",
            "tests/test_utils",
            "tests/fixtures"
        ]

        for dir_path in directories:
            full_path = self.base_path / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            self.created_dirs.append(str(full_path))
            print(f"✅ Tạo thư mục: {full_path}")

    def create_init_files(self):
        """Tạo các file __init__.py"""
        init_files = [
            ("__init__.py", self._get_root_init_content()),
            ("core/__init__.py", self._get_core_init_content()),
            ("database/__init__.py", self._get_database_init_content()),
            ("ui/__init__.py", self._get_ui_init_content()),
            ("ui/toolbars/__init__.py", self._get_generic_init_content("Toolbars")),
            ("ui/panels/__init__.py", self._get_generic_init_content("UI Panels")),
            ("ui/dialogs/__init__.py", self._get_generic_init_content("Dialogs")),
            ("widgets/__init__.py", self._get_widgets_init_content()),
            ("widgets/viewers/__init__.py", self._get_generic_init_content("Viewers")),
            ("widgets/editors/__init__.py", self._get_generic_init_content("Editors")),
            ("widgets/tables/__init__.py", self._get_generic_init_content("Tables")),
            ("managers/__init__.py", self._get_managers_init_content()),
            ("utils/__init__.py", self._get_utils_init_content()),
            ("services/__init__.py", self._get_services_init_content()),
            ("styles/__init__.py", self._get_styles_init_content()),
            ("resources/__init__.py", self._get_generic_init_content("Resources")),
            ("tests/__init__.py", self._get_generic_init_content("Tests")),
            ("tests/test_managers/__init__.py", ""),
            ("tests/test_widgets/__init__.py", ""),
            ("tests/test_utils/__init__.py", ""),
            ("tests/fixtures/__init__.py", "")
        ]

        for file_path, content in init_files:
            self._create_file(file_path, content)

    def create_core_files(self):
        """Tạo các file trong core/"""
        files = [
            ("core/base_widgets.py", self._get_base_widgets_content()),
            ("core/constants.py", self._get_constants_content()),
            ("core/exceptions.py", self._get_exceptions_content())
        ]

        for file_path, content in files:
            self._create_file(file_path, content)

    def create_database_files(self):
        """Tạo các file database/"""
        files = [
            ("database/models.py", self._get_models_content()),
            ("database/queries.py", self._get_queries_content())
        ]

        for file_path, content in files:
            self._create_file(file_path, content)

    def create_ui_files(self):
        """Tạo các file UI"""
        files = [
            # Main window
            ("ui/main_window.py", self._get_main_window_content()),

            # Toolbars
            ("ui/toolbars/main_toolbar.py", self._get_main_toolbar_content()),
            ("ui/toolbars/filter_toolbar.py", self._get_filter_toolbar_content()),

            # Panels
            ("ui/panels/tree_panel.py", self._get_tree_panel_content()),
            ("ui/panels/question_list_panel.py", self._get_question_list_panel_content()),
            ("ui/panels/preview_panel.py", self._get_preview_panel_content()),

            # Dialogs
            ("ui/dialogs/question_edit_dialog.py", self._get_question_edit_dialog_content()),
            ("ui/dialogs/tree_node_dialog.py", self._get_tree_node_dialog_content()),
            ("ui/dialogs/question_detail_dialog.py", self._get_question_detail_dialog_content()),
            ("ui/dialogs/folder_select_dialog.py", self._get_folder_select_dialog_content()),
            ("ui/dialogs/tags_manager_dialog.py", self._get_tags_manager_dialog_content()),
            ("ui/dialogs/tree_manager_dialog.py", self._get_tree_manager_dialog_content())
        ]

        for file_path, content in files:
            self._create_file(file_path, content)

    def create_widgets_files(self):
        """Tạo các file widgets"""
        files = [
            # Viewers
            ("widgets/viewers/image_viewer.py", self._get_image_viewer_content()),
            ("widgets/viewers/pdf_viewer.py", self._get_pdf_viewer_content()),
            ("widgets/viewers/adaptive_image_viewer.py", self._get_adaptive_image_viewer_content()),
            ("widgets/viewers/html_viewer.py", self._get_html_viewer_content()),
            ("widgets/viewers/image_viewer_dialog.py", self._get_image_viewer_dialog_content()),

            # Editors
            ("widgets/editors/rich_text_editor.py", self._get_rich_text_editor_content()),
            ("widgets/editors/latex_input_dialog.py", self._get_latex_input_dialog_content()),

            # Tables
            ("widgets/tables/question_table.py", self._get_question_table_content())
        ]

        for file_path, content in files:
            self._create_file(file_path, content)

    def create_managers_files(self):
        """Tạo các file managers"""
        files = [
            ("managers/question_manager.py", self._get_question_manager_content()),
            ("managers/tree_manager.py", self._get_tree_manager_content()),
            ("managers/import_export_manager.py", self._get_import_export_manager_content()),
            ("managers/search_manager.py", self._get_search_manager_content()),
            ("managers/preview_manager.py", self._get_preview_manager_content())
        ]

        for file_path, content in files:
            self._create_file(file_path, content)

    def create_utils_files(self):
        """Tạo các file utils"""
        files = [
            ("utils/file_utils.py", self._get_file_utils_content()),
            ("utils/image_utils.py", self._get_image_utils_content()),
            ("utils/clipboard_utils.py", self._get_clipboard_utils_content()),
            ("utils/validation_utils.py", self._get_validation_utils_content()),
            ("utils/ui_utils.py", self._get_ui_utils_content())
        ]

        for file_path, content in files:
            self._create_file(file_path, content)

    def create_services_files(self):
        """Tạo các file services"""
        files = [
            ("services/export_service.py", self._get_export_service_content()),
            ("services/import_service.py", self._get_import_service_content()),
            ("services/template_service.py", self._get_template_service_content())
        ]

        for file_path, content in files:
            self._create_file(file_path, content)

    def create_styles_files(self):
        """Tạo các file styles"""
        files = [
            ("styles/themes.py", self._get_themes_content()),
            ("styles/stylesheets.py", self._get_stylesheets_content())
        ]

        for file_path, content in files:
            self._create_file(file_path, content)

    def create_config_files(self):
        """Tạo các file cấu hình"""
        files = [
            ("setup.py", self._get_setup_content()),
            ("requirements.txt", self._get_requirements_content()),
            ("README.md", self._get_readme_content()),
            (".gitignore", self._get_gitignore_content()),
            ("pyproject.toml", self._get_pyproject_content())
        ]

        for file_path, content in files:
            self._create_file(file_path, content)

    def _create_file(self, file_path, content):
        """Tạo file với nội dung"""
        full_path = self.base_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

        self.created_files.append(str(full_path))
        print(f"📄 Tạo file: {full_path}")

    # ===========================================
    # CONTENT GENERATORS - INIT FILES
    # ===========================================

    def _get_root_init_content(self):
        return f'''# -*- coding: utf-8 -*-
"""
Question Bank Module
Mô-đun quản lý ngân hàng câu hỏi chuyên nghiệp

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

__version__ = "1.0.0"
__author__ = "Question Bank Team"
__description__ = "Hệ thống quản lý ngân hàng câu hỏi"

from .ui.main_window import QuestionBankMainWindow
from .managers import QuestionManager, TreeManager
from .core.constants import *

__all__ = [
    "QuestionBankMainWindow",
    "QuestionManager", 
    "TreeManager"
]
'''

    def _get_core_init_content(self):
        return '''# -*- coding: utf-8 -*-
"""
Core module - Các thành phần cơ sở
"""

from .base_widgets import *
from .constants import *
from .exceptions import *

__all__ = [
    # Constants
    "DIFFICULTY_LEVELS", "CONTENT_TYPES", "QUESTION_TYPES",

    # Exceptions  
    "QuestionBankError", "ValidationError", "DatabaseError",

    # Base widgets
    "BaseWidget", "BaseDialog", "BaseTableWidget"
]
'''

    def _get_database_init_content(self):
        return '''# -*- coding: utf-8 -*-
"""
Database module - Xử lý cơ sở dữ liệu
"""

from .models import *
from .queries import *

__all__ = [
    "QuestionModel", "TreeModel", "TagModel",
    "QuestionQueries", "TreeQueries", "TagQueries"
]
'''

    def _get_ui_init_content(self):
        return '''# -*- coding: utf-8 -*-
"""
UI module - Giao diện người dùng
"""

from .main_window import QuestionBankMainWindow
from .toolbars import *
from .panels import *
from .dialogs import *

__all__ = [
    "QuestionBankMainWindow"
]
'''

    def _get_widgets_init_content(self):
        return '''# -*- coding: utf-8 -*-
"""
Widgets module - Widget tùy chỉnh
"""

from .viewers import *
from .editors import *
from .tables import *

__all__ = [
    # Viewers
    "ImageViewer", "PDFViewer", "AdaptiveImageViewer", "HTMLViewer",

    # Editors
    "RichTextEditor", "LaTeXInputDialog",

    # Tables
    "QuestionTableWidget"
]
'''

    def _get_managers_init_content(self):
        return '''# -*- coding: utf-8 -*-
"""
Managers module - Quản lý logic nghiệp vụ
"""

from .question_manager import QuestionManager
from .tree_manager import TreeManager
from .import_export_manager import ImportExportManager
from .search_manager import SearchManager
from .preview_manager import PreviewManager

__all__ = [
    "QuestionManager",
    "TreeManager", 
    "ImportExportManager",
    "SearchManager",
    "PreviewManager"
]
'''

    def _get_utils_init_content(self):
        return '''# -*- coding: utf-8 -*-
"""
Utils module - Tiện ích
"""

from .file_utils import *
from .image_utils import *
from .clipboard_utils import *
from .validation_utils import *
from .ui_utils import *

__all__ = [
    # File utils
    "get_file_extension", "read_binary_file", "save_binary_file",

    # Image utils  
    "load_pixmap_from_data", "pixmap_to_bytes", "resize_pixmap",

    # Clipboard utils
    "paste_from_clipboard", "copy_to_clipboard",

    # Validation utils
    "validate_question_data", "validate_tree_node",

    # UI utils
    "safe_get", "row_to_dict", "show_error_message"
]
'''

    def _get_services_init_content(self):
        return '''# -*- coding: utf-8 -*-
"""
Services module - Dịch vụ
"""

from .export_service import ExportService
from .import_service import ImportService  
from .template_service import TemplateService

__all__ = [
    "ExportService",
    "ImportService",
    "TemplateService"
]
'''

    def _get_styles_init_content(self):
        return '''# -*- coding: utf-8 -*-
"""
Styles module - Giao diện và themes
"""

from .themes import *
from .stylesheets import *

__all__ = [
    "get_theme", "apply_theme", "get_stylesheet"
]
'''

    def _get_generic_init_content(self, module_name):
        return f'''# -*- coding: utf-8 -*-
"""
{module_name} module
"""
'''

    # ===========================================
    # CONTENT GENERATORS - CORE FILES
    # ===========================================

    def _get_base_widgets_content(self):
        return '''# -*- coding: utf-8 -*-
"""
Base widgets - Widget cơ sở để kế thừa
"""

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt, Signal

from ..core.exceptions import QuestionBankError


class BaseWidget(QtWidgets.QWidget):
    """Widget cơ sở với các chức năng chung"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """Thiết lập giao diện - override trong subclass"""
        pass

    def connect_signals(self):
        """Kết nối signals - override trong subclass"""  
        pass

    def show_error(self, title, message):
        """Hiển thị lỗi"""
        QtWidgets.QMessageBox.critical(self, title, message)

    def show_info(self, title, message):
        """Hiển thị thông báo"""
        QtWidgets.QMessageBox.information(self, title, message)

    def confirm(self, title, message):
        """Hỏi xác nhận"""
        return QtWidgets.QMessageBox.question(
            self, title, message
        ) == QtWidgets.QMessageBox.Yes


class BaseDialog(QtWidgets.QDialog):
    """Dialog cơ sở"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """Thiết lập giao diện"""
        pass

    def connect_signals(self):
        """Kết nối signals"""
        pass


class BaseTableWidget(QtWidgets.QTableWidget):
    """Table widget cơ sở với các chức năng mở rộng"""

    item_double_clicked = Signal(int, int)  # row, column
    context_menu_requested = Signal(object)  # QPoint

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_table()

    def setup_table(self):
        """Thiết lập table"""
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setSortingEnabled(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)

        # Connect signals
        self.cellDoubleClicked.connect(self.item_double_clicked.emit)
        self.customContextMenuRequested.connect(self.context_menu_requested.emit)

    def add_row_data(self, data_list):
        """Thêm dòng với dữ liệu"""
        row = self.rowCount()
        self.insertRow(row)

        for col, data in enumerate(data_list):
            if col < self.columnCount():
                item = QtWidgets.QTableWidgetItem(str(data))
                self.setItem(row, col, item)

    def get_selected_row_data(self):
        """Lấy dữ liệu dòng được chọn"""
        current_row = self.currentRow()
        if current_row < 0:
            return None

        data = []
        for col in range(self.columnCount()):
            item = self.item(current_row, col)
            data.append(item.text() if item else "")

        return data

    def clear_all_data(self):
        """Xóa tất cả dữ liệu"""
        self.setRowCount(0)
'''

    def _get_constants_content(self):
        return '''# -*- coding: utf-8 -*-
"""
Constants - Hằng số và cấu hình
"""

# Độ khó câu hỏi
DIFFICULTY_LEVELS = {
    "easy": "🟢 Dễ",
    "medium": "🟡 Trung bình", 
    "hard": "🔴 Khó"
}

# Loại nội dung
CONTENT_TYPES = {
    "text": "📝 Text",
    "image": "🖼️ Image", 
    "pdf": "📄 PDF",
    "word": "📘 Word",
    "mixed": "🔀 Mixed"
}

# Loại câu hỏi
QUESTION_TYPES = {
    "multiple_choice": "Trắc nghiệm",
    "true_false": "Đúng/Sai",
    "fill_blank": "Điền khuyết",
    "essay": "Tự luận",
    "matching": "Nối đáp án"
}

# Loại đáp án  
ANSWER_TYPES = {
    "text": "📝 Text",
    "image": "🖼️ Image",
    "pdf": "📄 PDF" 
}

# Cấp độ cây thư mục
TREE_LEVELS = {
    "subject": "📚 Môn",
    "grade": "🎓 Lớp", 
    "topic": "📖 Chủ đề",
    "subtopic": "📄 Chủ đề con",
    "difficulty": "🎯 Mức độ"
}

# Icon cho cấp độ
LEVEL_ICONS = {
    "Môn": "📚",
    "Lớp": "🎓", 
    "Chủ đề": "📖",
    "Dạng": "📝",
    "Mức độ": "⭐"
}

# Trạng thái câu hỏi
QUESTION_STATUS = {
    "active": "✅ Hoạt động",
    "draft": "📝 Nháp", 
    "archived": "📁 Lưu trữ",
    "deleted": "🗑️ Đã xóa"
}

# Kích thước mặc định
DEFAULT_SIZES = {
    "window_width": 1200,
    "window_height": 800,
    "preview_max_width": 600,
    "preview_max_height": 400,
    "thumbnail_size": 150
}

# Đường dẫn
PATHS = {
    "icons": "resources/icons",
    "templates": "resources/templates",
    "exports": "exports",
    "imports": "imports"
}

# Database
DATABASE_CONFIG = {
    "timeout": 30,
    "check_same_thread": False,
    "isolation_level": None
}

# UI Colors
COLORS = {
    "primary": "#2E86AB",
    "secondary": "#A23B72", 
    "success": "#28a745",
    "warning": "#ffc107",
    "danger": "#dc3545",
    "info": "#17a2b8",
    "light": "#f8f9fa",
    "dark": "#343a40"
}

# File extensions
SUPPORTED_EXTENSIONS = {
    "images": [".png", ".jpg", ".jpeg", ".gif", ".bmp"],
    "documents": [".docx", ".doc", ".pdf"],
    "exports": [".docx", ".pdf", ".json", ".xlsx"]
}
'''

    def _get_exceptions_content(self):
        return '''# -*- coding: utf-8 -*-
"""
Exceptions - Exception tùy chỉnh
"""


class QuestionBankError(Exception):
    """Exception cơ sở cho Question Bank"""
    pass


class ValidationError(QuestionBankError):
    """Lỗi validation dữ liệu"""
    pass


class DatabaseError(QuestionBankError):
    """Lỗi cơ sở dữ liệu"""
    pass


class FileOperationError(QuestionBankError):
    """Lỗi thao tác file"""
    pass


class ImportError(QuestionBankError):
    """Lỗi import dữ liệu"""
    pass


class ExportError(QuestionBankError):
    """Lỗi export dữ liệu"""
    pass


class WidgetError(QuestionBankError):
    """Lỗi widget/UI"""
    pass


class ImageProcessingError(QuestionBankError):
    """Lỗi xử lý ảnh"""
    pass


class SearchError(QuestionBankError):
    """Lỗi tìm kiếm"""
    pass


class TemplateError(QuestionBankError):
    """Lỗi template"""
    pass
'''

    # ===========================================
    # CONTENT GENERATORS - STUB FILES
    # ===========================================

    def _get_models_content(self):
        return '''# -*- coding: utf-8 -*-
"""
Models - Mô hình dữ liệu
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class QuestionModel:
    """Model cho câu hỏi"""
    id: Optional[int] = None
    content_text: str = ""
    content_type: str = "text"
    content_data: Optional[bytes] = None
    answer_text: str = ""
    answer_type: str = "text" 
    answer_data: Optional[bytes] = None
    difficulty_level: str = "medium"
    question_type: str = "multiple_choice"
    tree_id: Optional[int] = None
    status: str = "active"
    usage_count: int = 0
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    created_by: str = "user"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "content_text": self.content_text,
            "content_type": self.content_type,
            "content_data": self.content_data,
            "answer_text": self.answer_text,
            "answer_type": self.answer_type,
            "answer_data": self.answer_data,
            "difficulty_level": self.difficulty_level,
            "question_type": self.question_type,
            "tree_id": self.tree_id,
            "status": self.status,
            "usage_count": self.usage_count,
            "created_date": self.created_date,
            "modified_date": self.modified_date,
            "created_by": self.created_by
        }


@dataclass  
class TreeModel:
    """Model cho node cây thư mục"""
    id: Optional[int] = None
    parent_id: Optional[int] = None
    name: str = ""
    level: str = "topic"
    description: str = ""
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "name": self.name,
            "level": self.level,
            "description": self.description,
            "created_at": self.created_at
        }


@dataclass
class TagModel:
    """Model cho tag"""
    question_id: int
    tag_name: str
    color: str = "#3498db"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "question_id": self.question_id,
            "tag_name": self.tag_name,
            "color": self.color
        }


# TODO: Thêm các model khác khi cần
'''

    def _get_queries_content(self):
        return '''# -*- coding: utf-8 -*-
"""
Queries - Truy vấn phức tạp
"""

from typing import List, Dict, Any, Optional


class QuestionQueries:
    """Truy vấn cho bảng question_bank"""

    @staticmethod
    def get_questions_by_tree(tree_id: int) -> str:
        """Lấy câu hỏi theo tree_id"""
        return "SELECT * FROM question_bank WHERE tree_id = ? ORDER BY created_date DESC"

    @staticmethod  
    def search_questions(keyword: str) -> str:
        """Tìm kiếm câu hỏi"""
        return """
        SELECT * FROM question_bank 
        WHERE content_text LIKE ? OR answer_text LIKE ?
        ORDER BY usage_count DESC, created_date DESC
        """

    @staticmethod
    def get_statistics() -> str:
        """Thống kê câu hỏi"""
        return """
        SELECT 
            difficulty_level,
            COUNT(*) as count,
            AVG(usage_count) as avg_usage
        FROM question_bank 
        WHERE status = 'active'
        GROUP BY difficulty_level
        """


class TreeQueries:
    """Truy vấn cho bảng exercise_tree"""

    @staticmethod
    def get_tree_with_question_count() -> str:
        """Lấy cây với số câu hỏi"""
        return """
        SELECT 
            t.*,
            COUNT(q.id) as question_count
        FROM exercise_tree t
        LEFT JOIN question_bank q ON q.tree_id = t.id
        GROUP BY t.id
        ORDER BY t.parent_id, t.name
        """

    @staticmethod
    def get_path_to_root(node_id: int) -> str:
        """Lấy đường dẫn từ node đến root"""
        return """
        WITH RECURSIVE tree_path AS (
            SELECT id, parent_id, name, level, 0 as depth
            FROM exercise_tree WHERE id = ?

            UNION ALL

            SELECT t.id, t.parent_id, t.name, t.level, tp.depth + 1
            FROM exercise_tree t
            JOIN tree_path tp ON t.id = tp.parent_id
        )
        SELECT * FROM tree_path ORDER BY depth DESC
        """


class TagQueries:
    """Truy vấn cho bảng question_tags"""

    @staticmethod
    def get_popular_tags(limit: int = 20) -> str:
        """Lấy tag phổ biến"""
        return """
        SELECT tag_name, COUNT(*) as usage_count
        FROM question_tags
        GROUP BY tag_name
        ORDER BY usage_count DESC
        LIMIT ?
        """

    @staticmethod
    def get_questions_by_tag(tag_name: str) -> str:
        """Lấy câu hỏi theo tag"""
        return """
        SELECT q.*
        FROM question_bank q
        JOIN question_tags t ON q.id = t.question_id
        WHERE t.tag_name = ?
        ORDER BY q.created_date DESC
        """


# TODO: Thêm các query class khác
'''

    def _get_main_window_content(self):
        return '''# -*- coding: utf-8 -*-
"""
Main Window - Cửa sổ chính (đã module hóa)
"""

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt

from ..core.base_widgets import BaseWidget
from ..managers import QuestionManager, TreeManager, SearchManager
from .toolbars.main_toolbar import MainToolbar
from .toolbars.filter_toolbar import FilterToolbar
from .panels.tree_panel import TreePanel
from .panels.question_list_panel import QuestionListPanel
from .panels.preview_panel import PreviewPanel


class QuestionBankMainWindow(BaseWidget):
    """Cửa sổ chính của ứng dụng Question Bank (đã module hóa)"""

    def __init__(self, db_manager, parent=None):
        self.db = db_manager
        self.current_question_id = None

        # Khởi tạo managers
        self.question_manager = QuestionManager(db_manager)
        self.tree_manager = TreeManager(db_manager) 
        self.search_manager = SearchManager(db_manager)

        super().__init__(parent)
        self.setWindowTitle("Ngân hàng câu hỏi - Module hóa")
        self.showMaximized()

    def setup_ui(self):
        """Thiết lập giao diện chính"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main toolbar
        self.main_toolbar = MainToolbar(self)
        layout.addWidget(self.main_toolbar)

        # Filter toolbar  
        self.filter_toolbar = FilterToolbar(self)
        layout.addWidget(self.filter_toolbar)

        # Splitter 3 cột
        splitter = QtWidgets.QSplitter(Qt.Horizontal)

        # Tree panel
        self.tree_panel = TreePanel(self.tree_manager, self)
        splitter.addWidget(self.tree_panel)

        # Question list panel
        self.question_list_panel = QuestionListPanel(self.question_manager, self)
        splitter.addWidget(self.question_list_panel)

        # Preview panel
        self.preview_panel = PreviewPanel(self.question_manager, self)
        splitter.addWidget(self.preview_panel)

        # Thiết lập tỷ lệ splitter
        splitter.setSizes([250, 500, 400])

        layout.addWidget(splitter)

    def connect_signals(self):
        """Kết nối signals giữa các panel"""
        # Tree selection -> load questions
        self.tree_panel.tree_selected.connect(self.on_tree_selected)

        # Question selection -> show preview
        self.question_list_panel.question_selected.connect(self.on_question_selected)

        # Toolbar actions
        self.main_toolbar.add_question_requested.connect(self.add_question)
        self.main_toolbar.search_requested.connect(self.search_questions)

        # Filter changes
        self.filter_toolbar.filter_changed.connect(self.apply_filters)

    def on_tree_selected(self, tree_id):
        """Xử lý khi chọn node trong cây"""
        questions = self.question_manager.get_questions_by_tree(tree_id)
        self.question_list_panel.load_questions(questions)

    def on_question_selected(self, question_id):
        """Xử lý khi chọn câu hỏi"""
        self.current_question_id = question_id
        question = self.question_manager.get_question_by_id(question_id)
        if question:
            self.preview_panel.show_question(question)

    def add_question(self):
        """Thêm câu hỏi mới"""
        from .dialogs.question_edit_dialog import QuestionEditDialog

        tree_id = self.tree_panel.get_selected_tree_id()
        if not tree_id:
            self.show_error("Lỗi", "Vui lòng chọn thư mục trong cây")
            return

        dialog = QuestionEditDialog(self.question_manager, tree_id=tree_id, parent=self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.refresh_current_view()

    def search_questions(self, keyword):
        """Tìm kiếm câu hỏi"""
        results = self.search_manager.search(keyword)
        self.question_list_panel.load_questions(results)

    def apply_filters(self, filters):
        """Áp dụng bộ lọc"""
        # TODO: Implement filtering logic
        pass

    def refresh_current_view(self):
        """Refresh view hiện tại"""
        tree_id = self.tree_panel.get_selected_tree_id()
        if tree_id:
            self.on_tree_selected(tree_id)


# TODO: Thêm các method khác khi cần
'''

    def _get_main_toolbar_content(self):
        return '''# -*- coding: utf-8 -*-
"""
Main Toolbar - Thanh công cụ chính
"""

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import Qt, Signal

from ...core.base_widgets import BaseWidget


class MainToolbar(BaseWidget):
    """Thanh công cụ chính"""

    # Signals
    add_question_requested = Signal()
    search_requested = Signal(str)
    import_requested = Signal()
    export_requested = Signal()
    tree_toggle_requested = Signal()

    def setup_ui(self):
        """Thiết lập giao diện toolbar"""
        layout = QtWidgets.QHBoxLayout(self)

        # Tạo toolbar
        toolbar = QtWidgets.QToolBar()
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        toolbar.setMovable(False)

        # Style toolbar
        toolbar.setStyleSheet("""
            QToolBar { 
                background: #f8f9fa; 
                border: 1px solid #dee2e6; 
                spacing: 8px; 
                padding: 4px;
            }
            QToolBar::separator { 
                background: #dee2e6; 
                width: 2px; 
                margin: 0 4px;
            }
        """)

        # Nhóm quản lý cây
        self.tree_toggle_action = toolbar.addAction("🌲 Ẩn/Hiện cây")
        self.tree_manage_action = toolbar.addAction("⚙️ Quản lý cây")

        toolbar.addSeparator()

        # Nhóm tìm kiếm
        search_widget = self._create_search_widget()
        toolbar.addWidget(search_widget)

        self.search_action = toolbar.addAction("🔍 Tìm")

        toolbar.addSeparator()

        # Nút thêm câu hỏi nổi bật
        self.add_question_action = toolbar.addAction("➕ Thêm câu hỏi")
        self._style_add_button()

        # Nhóm tạo mới
        self.new_action = toolbar.addAction("➕ Tạo mới")
        self.template_action = toolbar.addAction("📋 Template")

        toolbar.addSeparator()

        # Nhóm import/export
        self.import_action = toolbar.addAction("📥 Import Word")
        self.export_action = toolbar.addAction("📤 Export Word")
        self.export_pdf_action = toolbar.addAction("📄 Export PDF")

        layout.addWidget(toolbar)

    def connect_signals(self):
        """Kết nối signals"""
        self.tree_toggle_action.triggered.connect(self.tree_toggle_requested.emit)
        self.add_question_action.triggered.connect(self.add_question_requested.emit)
        self.search_action.triggered.connect(self._on_search_clicked)
        self.import_action.triggered.connect(self.import_requested.emit)
        self.export_action.triggered.connect(self.export_requested.emit)

        # Enter key trong search
        self.search_edit.returnPressed.connect(self._on_search_clicked)

    def _create_search_widget(self):
        """Tạo widget tìm kiếm"""
        search_widget = QtWidgets.QWidget()
        search_layout = QtWidgets.QHBoxLayout(search_widget)
        search_layout.setContentsMargins(0, 0, 0, 0)

        search_layout.addWidget(QtWidgets.QLabel("🔍"))

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Tìm kiếm câu hỏi...")
        self.search_edit.setMinimumWidth(200)
        self.search_edit.setStyleSheet(
            "padding: 4px; border: 1px solid #ced4da; border-radius: 4px;"
        )
        search_layout.addWidget(self.search_edit)

        return search_widget

    def _style_add_button(self):
        """Style cho nút thêm câu hỏi"""
        add_btn_widget = self.parent().findChild(QtWidgets.QToolButton)
        if add_btn_widget:
            add_btn_widget.setStyleSheet("""
                QToolButton {
                    background: #28a745;
                    color: white;
                    font-weight: bold;
                    padding: 6px 12px;
                    border-radius: 4px;
                }
                QToolButton:hover {
                    background: #218838;
                }
            """)

    def _on_search_clicked(self):
        """Xử lý click nút tìm kiếm"""
        keyword = self.search_edit.text().strip()
        if keyword:
            self.search_requested.emit(keyword)


# TODO: Thêm các method khác
'''

    # ===========================================
    # STUB CONTENT GENERATORS
    # ===========================================

    def _generate_stub_content(self, class_name, description, imports=None):
        """Tạo nội dung stub chung"""
        imports_str = ""
        if imports:
            imports_str = "\n".join(imports) + "\n\n"

        return f'''# -*- coding: utf-8 -*-
"""
{description}
"""

{imports_str}
class {class_name}:
    """
    {description}

    TODO: Implement {class_name}
    - Thêm các method cần thiết
    - Xử lý logic nghiệp vụ
    - Kết nối với database/UI
    """

    def __init__(self, *args, **kwargs):
        """Khởi tạo {class_name}"""
        # TODO: Implement initialization
        pass

    # TODO: Thêm các method cần thiết


# TODO: Thêm các class/function khác nếu cần
'''

    # Generate các file stub content
    def _get_filter_toolbar_content(self):
        return self._generate_stub_content(
            "FilterToolbar",
            "Thanh công cụ bộ lọc",
            ["from PySide6 import QtWidgets", "from ...core.base_widgets import BaseWidget"]
        )

    def _get_tree_panel_content(self):
        return self._generate_stub_content(
            "TreePanel",
            "Panel cây thư mục",
            ["from PySide6 import QtWidgets", "from ...core.base_widgets import BaseWidget"]
        )

    def _get_question_list_panel_content(self):
        return self._generate_stub_content(
            "QuestionListPanel",
            "Panel danh sách câu hỏi",
            ["from PySide6 import QtWidgets", "from ...core.base_widgets import BaseWidget"]
        )

    def _get_preview_panel_content(self):
        return self._generate_stub_content(
            "PreviewPanel",
            "Panel xem trước câu hỏi",
            ["from PySide6 import QtWidgets", "from ...core.base_widgets import BaseWidget"]
        )

    def _get_question_edit_dialog_content(self):
        return self._generate_stub_content(
            "QuestionEditDialog",
            "Dialog chỉnh sửa câu hỏi",
            ["from PySide6 import QtWidgets", "from ...core.base_widgets import BaseDialog"]
        )

    def _get_tree_node_dialog_content(self):
        return self._generate_stub_content(
            "TreeNodeDialog",
            "Dialog chỉnh sửa node cây",
            ["from PySide6 import QtWidgets", "from ...core.base_widgets import BaseDialog"]
        )

    def _get_question_detail_dialog_content(self):
        return self._generate_stub_content(
            "QuestionDetailDialog",
            "Dialog xem chi tiết câu hỏi",
            ["from PySide6 import QtWidgets", "from ...core.base_widgets import BaseDialog"]
        )

    def _get_folder_select_dialog_content(self):
        return self._generate_stub_content(
            "FolderSelectDialog",
            "Dialog chọn thư mục",
            ["from PySide6 import QtWidgets", "from ...core.base_widgets import BaseDialog"]
        )

    def _get_tags_manager_dialog_content(self):
        return self._generate_stub_content(
            "TagsManagerDialog",
            "Dialog quản lý tags",
            ["from PySide6 import QtWidgets", "from ...core.base_widgets import BaseDialog"]
        )

    def _get_tree_manager_dialog_content(self):
        return self._generate_stub_content(
            "TreeManagerDialog",
            "Dialog quản lý cây nâng cao",
            ["from PySide6 import QtWidgets", "from ...core.base_widgets import BaseDialog"]
        )

    def _get_image_viewer_content(self):
        return self._generate_stub_content(
            "ImageViewer",
            "Widget xem ảnh cơ bản",
            ["from PySide6 import QtWidgets", "from ...core.base_widgets import BaseWidget"]
        )

    def _get_pdf_viewer_content(self):
        return self._generate_stub_content(
            "PDFViewer",
            "Widget xem PDF",
            ["from PySide6 import QtWidgets", "from ...core.base_widgets import BaseWidget"]
        )

    def _get_adaptive_image_viewer_content(self):
        return self._generate_stub_content(
            "AdaptiveImageViewer",
            "Widget xem ảnh tự động điều chỉnh",
            ["from PySide6 import QtWidgets", "from ...core.base_widgets import BaseWidget"]
        )

    def _get_html_viewer_content(self):
        return self._generate_stub_content(
            "HTMLViewer",
            "Widget xem HTML với ảnh từ database",
            ["from PySide6 import QtWidgets", "from ...core.base_widgets import BaseWidget"]
        )

    def _get_image_viewer_dialog_content(self):
        return self._generate_stub_content(
            "ImageViewerDialog",
            "Dialog xem ảnh fullscreen",
            ["from PySide6 import QtWidgets", "from ...core.base_widgets import BaseDialog"]
        )

    def _get_rich_text_editor_content(self):
        return self._generate_stub_content(
            "RichTextEditor",
            "Trình soạn thảo văn bản rich text",
            ["from PySide6 import QtWidgets", "from ...core.base_widgets import BaseWidget"]
        )

    def _get_latex_input_dialog_content(self):
        return self._generate_stub_content(
            "LaTeXInputDialog",
            "Dialog nhập công thức LaTeX",
            ["from PySide6 import QtWidgets", "from ...core.base_widgets import BaseDialog"]
        )

    def _get_question_table_content(self):
        return self._generate_stub_content(
            "QuestionTableWidget",
            "Bảng câu hỏi tùy chỉnh",
            ["from PySide6 import QtWidgets", "from ...core.base_widgets import BaseTableWidget"]
        )

    def _get_question_manager_content(self):
        return self._generate_stub_content(
            "QuestionManager",
            "Quản lý câu hỏi - CRUD operations",
            ["from ..database.models import QuestionModel", "from ..core.exceptions import *"]
        )

    def _get_tree_manager_content(self):
        return self._generate_stub_content(
            "TreeManager",
            "Quản lý cây thư mục",
            ["from ..database.models import TreeModel", "from ..core.exceptions import *"]
        )

    def _get_import_export_manager_content(self):
        return self._generate_stub_content(
            "ImportExportManager",
            "Quản lý import/export",
            ["from ..core.exceptions import ImportError, ExportError"]
        )

    def _get_search_manager_content(self):
        return self._generate_stub_content(
            "SearchManager",
            "Quản lý tìm kiếm nâng cao",
            ["from ..database.queries import QuestionQueries", "from ..core.exceptions import SearchError"]
        )

    def _get_preview_manager_content(self):
        return self._generate_stub_content(
            "PreviewManager",
            "Quản lý preview đa dạng (text, image, PDF)",
            ["from ..core.exceptions import WidgetError"]
        )

    def _get_file_utils_content(self):
        return self._generate_stub_content(
            "FileUtils",
            "Tiện ích xử lý file",
            ["import os", "from pathlib import Path", "from ..core.exceptions import FileOperationError"]
        )

    def _get_image_utils_content(self):
        return self._generate_stub_content(
            "ImageUtils",
            "Tiện ích xử lý ảnh",
            ["from PySide6 import QtGui", "from ..core.exceptions import ImageProcessingError"]
        )

    def _get_clipboard_utils_content(self):
        return self._generate_stub_content(
            "ClipboardUtils",
            "Tiện ích clipboard",
            ["from PySide6 import QtWidgets, QtGui"]
        )

    def _get_validation_utils_content(self):
        return self._generate_stub_content(
            "ValidationUtils",
            "Tiện ích validation",
            ["from ..core.exceptions import ValidationError"]
        )

    def _get_ui_utils_content(self):
        return self._generate_stub_content(
            "UIUtils",
            "Tiện ích UI - safe_get, row_to_dict, etc",
            ["from PySide6 import QtWidgets"]
        )

    def _get_export_service_content(self):
        return self._generate_stub_content(
            "ExportService",
            "Dịch vụ xuất Word, PDF với template",
            ["from ..core.exceptions import ExportError"]
        )

    def _get_import_service_content(self):
        return self._generate_stub_content(
            "ImportService",
            "Dịch vụ nhập từ Word, Excel",
            ["from ..core.exceptions import ImportError"]
        )

    def _get_template_service_content(self):
        return self._generate_stub_content(
            "TemplateService",
            "Dịch vụ quản lý template câu hỏi",
            ["from ..core.exceptions import TemplateError"]
        )

    def _get_themes_content(self):
        return self._generate_stub_content(
            "ThemeManager",
            "Quản lý themes và giao diện",
            ["from PySide6 import QtGui"]
        )

    def _get_stylesheets_content(self):
        return self._generate_stub_content(
            "StyleSheetManager",
            "Quản lý stylesheets CSS/QSS",
            []
        )

    # ===========================================
    # CONFIG FILES
    # ===========================================

    def _get_setup_content(self):
        return f'''# -*- coding: utf-8 -*-
"""
Setup script for Question Bank Module
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="question-bank-module",
    version="1.0.0",
    author="Question Bank Team",
    author_email="team@questionbank.com",
    description="Hệ thống quản lý ngân hàng câu hỏi chuyên nghiệp",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourorg/question-bank-module",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Education",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "PySide6>=6.4.0",
        "python-docx>=0.8.11",
        "reportlab>=3.6.0",
        "Pillow>=9.0.0",
        "openpyxl>=3.0.9",
    ],
    extras_require={{
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.950",
        ],
        "pdf": [
            "PyMuPDF>=1.20.0",
        ],
        "latex": [
            "sympy>=1.10.1",
            "matplotlib>=3.5.0",
        ]
    }},
    entry_points={{
        "console_scripts": [
            "question-bank=question_bank.cli:main",
        ],
    }},
    include_package_data=True,
    package_data={{
        "question_bank": [
            "resources/icons/*.png",
            "resources/templates/*.docx",
            "resources/translations/*.qm",
        ],
    }},
)
'''

    def _get_requirements_content(self):
        return '''# Core dependencies
PySide6>=6.4.0
python-docx>=0.8.11
reportlab>=3.6.0
Pillow>=9.0.0
openpyxl>=3.0.9

# Optional dependencies
PyMuPDF>=1.20.0  # PDF processing
sympy>=1.10.1    # LaTeX support
matplotlib>=3.5.0  # LaTeX rendering

# Development dependencies (install with: pip install -e .[dev])
pytest>=7.0.0
pytest-cov>=4.0.0
black>=22.0.0
flake8>=4.0.0
mypy>=0.950
'''

    def _get_readme_content(self):
        return f'''# Question Bank Module

Hệ thống quản lý ngân hàng câu hỏi chuyên nghiệp được module hóa.

## Đặc điểm

✅ **Module hóa hoàn toàn** - Cấu trúc rõ ràng, dễ bảo trì
✅ **Hỗ trợ đa dạng** - Text, ảnh, PDF, LaTeX  
✅ **Giao diện hiện đại** - PySide6 Qt6
✅ **Tìm kiếm thông minh** - Full-text search
✅ **Import/Export** - Word, PDF, Excel
✅ **Cây thư mục linh hoạt** - Phân loại theo môn/lớp/chủ đề
✅ **Tag system** - Gắn thẻ và phân loại
✅ **Preview tự động** - Xem trước ảnh/PDF ngay trong app

## Cài đặt

```bash
# Clone repository
git clone https://github.com/yourorg/question-bank-module.git
cd question-bank-module

# Cài đặt dependencies  
pip install -r requirements.txt

# Hoặc cài đặt với development tools
pip install -e .[dev]
```

## Sử dụng

```python
from question_bank import QuestionBankMainWindow
from your_db_manager import DatabaseManager

# Khởi tạo
db = DatabaseManager("your_database.db")
app = QApplication([])
window = QuestionBankMainWindow(db)
window.show()
app.exec()
```

## Cấu trúc Module

```
question_bank/
├── core/           # Lớp nền tảng
├── database/       # Models và queries
├── ui/            # Giao diện
│   ├── toolbars/  # Thanh công cụ
│   ├── panels/    # Các panel chính
│   └── dialogs/   # Dialog boxes
├── widgets/       # Widget tùy chỉnh
├── managers/      # Business logic
├── utils/         # Tiện ích
├── services/      # Dịch vụ
└── styles/        # Themes và CSS
```

## Phát triển

```bash
# Chạy tests
pytest

# Code formatting
black .

# Type checking  
mypy .

# Linting
flake8 .
```

## Đóng góp

1. Fork repository
2. Tạo feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push branch (`git push origin feature/AmazingFeature`)
5. Tạo Pull Request

## License

MIT License - xem [LICENSE](LICENSE) để biết chi tiết.

## Tác giả

Question Bank Team - Generated {datetime.now().strftime("%Y-%m-%d")}
'''

    def _get_gitignore_content(self):
        return '''# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# PyInstaller
*.manifest
*.spec

# Installer logs
pip-log.txt
pip-delete-this-directory.txt

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/
cover/

# Translations
*.mo
*.pot

# Django stuff:
*.log
local_settings.py
db.sqlite3
db.sqlite3-journal

# Flask stuff:
instance/
.webassets-cache

# Scrapy stuff:
.scrapy

# Sphinx documentation
docs/_build/

# PyBuilder
.pybuilder/
target/

# Jupyter Notebook
.ipynb_checkpoints

# IPython
profile_default/
ipython_config.py

# pyenv
.python-version

# pipenv
Pipfile.lock

# poetry
poetry.lock

# pdm
.pdm.toml

# PEP 582
__pypackages__/

# Celery stuff
celerybeat-schedule
celerybeat.pid

# SageMath parsed files
*.sage.py

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Spyder project settings
.spyderproject
.spyproject

# Rope project settings
.ropeproject

# mkdocs documentation
/site

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# Pyre type checker
.pyre/

# pytype static type analyzer
.pytype/

# Cython debug symbols
cython_debug/

# PyCharm
.idea/

# VS Code
.vscode/

# Database files
*.db
*.sqlite
*.sqlite3

# Temporary files
*.tmp
*.temp
*~

# OS generated files
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Project specific
exports/
imports/
logs/
temp/
'''

#( Sử dụng raw string để tránh escape sequence errors )
@staticmethod
def _get_pyproject_content():
    return r'''[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "question-bank-module"
version = "1.0.0"
description = "Hệ thống quản lý ngân hàng câu hỏi chuyên nghiệp"
readme = "README.md"
authors = [
    {name = "Question Bank Team", email = "team@questionbank.com"}
]
license = {text = "MIT"}
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Education",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9", 
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
]
requires-python = ">=3.8"
dependencies = [
    "PySide6>=6.4.0",
    "python-docx>=0.8.11",
    "reportlab>=3.6.0", 
    "Pillow>=9.0.0",
    "openpyxl>=3.0.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "black>=22.0.0",
    "flake8>=4.0.0",
    "mypy>=0.950",
]
pdf = ["PyMuPDF>=1.20.0"]
latex = ["sympy>=1.10.1", "matplotlib>=3.5.0"]

[project.scripts]
question-bank = "question_bank.cli:main"

[tool.black]
line-length = 88
target-version = ["py38", "py39", "py310", "py311"]

[tool.mypy]
python_version = "3.8"
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
minversion = "6.0"
addopts = "-ra -q"
testpaths = ["tests"]

[tool.coverage.run]
source = ["question_bank"]
omit = ["*/tests/*", "setup.py"]
'''