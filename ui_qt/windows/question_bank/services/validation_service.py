"""
Validation Service - Business Logic Layer for Data Validation
File: ui_qt/windows/question_bank/services/validation_service.py

Chức năng:
- Question content validation
- Answer format validation
- Tree structure validation
- Data integrity checking
- Format validation (LaTeX, HTML, etc.)
- File validation
- Input sanitization
- Data consistency checking
- Business rule enforcement
- Security validation
"""

import re
import json
import base64
import mimetypes
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum

# Import utilities
from ..utils.helpers import (
    clean_text, normalize_vietnamese, is_valid_email,
    safe_int, safe_str
)


class ValidationLevel(Enum):
    """Mức độ validation"""
    BASIC = "basic"  # Validation cơ bản
    STANDARD = "standard"  # Validation tiêu chuẩn
    STRICT = "strict"  # Validation nghiêm ngặt
    CUSTOM = "custom"  # Validation tùy chỉnh


class ValidationSeverity(Enum):
    """Mức độ nghiêm trọng của lỗi"""
    INFO = "info"  # Thông tin
    WARNING = "warning"  # Cảnh báo
    ERROR = "error"  # Lỗi
    CRITICAL = "critical"  # Lỗi nghiêm trọng


@dataclass
class ValidationRule:
    """Quy tắc validation"""
    name: str
    description: str
    validator_func: str  # Tên function validator
    severity: ValidationSeverity = ValidationSeverity.ERROR
    enabled: bool = True
    params: Dict[str, Any] = None

    def __post_init__(self):
        if self.params is None:
            self.params = {}


@dataclass
class ValidationResult:
    """Kết quả validation"""
    is_valid: bool = True
    errors: List[str] = None
    warnings: List[str] = None
    info_messages: List[str] = None
    field_errors: Dict[str, List[str]] = None
    validation_time: float = 0.0
    rules_checked: int = 0
    rules_passed: int = 0

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.info_messages is None:
            self.info_messages = []
        if self.field_errors is None:
            self.field_errors = {}

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0 or len(self.field_errors) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    @property
    def success_rate(self) -> float:
        return (self.rules_passed / self.rules_checked) * 100 if self.rules_checked > 0 else 0


@dataclass
class QuestionValidationConfig:
    """Cấu hình validation cho câu hỏi"""
    level: ValidationLevel = ValidationLevel.STANDARD
    check_content_length: bool = True
    min_content_length: int = 10
    max_content_length: int = 10000
    check_answer_required: bool = True
    check_html_tags: bool = True
    check_latex_syntax: bool = True
    check_image_format: bool = True
    max_image_size_mb: float = 10.0
    allowed_image_formats: List[str] = None
    check_duplicate_content: bool = False
    enable_profanity_check: bool = False
    custom_rules: List[ValidationRule] = None

    def __post_init__(self):
        if self.allowed_image_formats is None:
            self.allowed_image_formats = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        if self.custom_rules is None:
            self.custom_rules = []


class ValidationService:
    """Business Logic Service for Data Validation"""

    def __init__(self, db_manager):
        self.db = db_manager

        # Validation configurations
        self.question_config = QuestionValidationConfig()
        self.tree_config = self._get_tree_validation_config()

        # Validation rules
        self.question_rules = self._init_question_validation_rules()
        self.tree_rules = self._init_tree_validation_rules()

        # Patterns for validation
        self.patterns = {
            'html_tag': re.compile(r'<[^>]+>'),
            'latex_inline': re.compile(r'\$[^$]+\$'),
            'latex_block': re.compile(r'\$\$[^$]+\$\$'),
            'email': re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
            'url': re.compile(
                r'https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?'),
            'vietnamese_text': re.compile(r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđĐ]')
        }

        # Profanity words (if enabled)
        self.profanity_words = self._load_profanity_words()

    # ========== QUESTION VALIDATION ==========

    def validate_question(self, question_data: Dict[str, Any],
                          config: QuestionValidationConfig = None) -> ValidationResult:
        """Validate toàn bộ câu hỏi"""
        start_time = datetime.now()

        if not config:
            config = self.question_config

        result = ValidationResult()

        try:
            # Basic validation
            if not self._validate_question_basic(question_data, result):
                result.is_valid = False

            # Content validation
            if not self._validate_question_content(question_data, config, result):
                result.is_valid = False

            # Answer validation
            if not self._validate_question_answer(question_data, config, result):
                result.is_valid = False

            # Format validation
            if not self._validate_question_formats(question_data, config, result):
                result.is_valid = False

            # Media validation
            if not self._validate_question_media(question_data, config, result):
                result.is_valid = False

            # Business rules validation
            if not self._validate_question_business_rules(question_data, config, result):
                result.is_valid = False

            # Custom rules validation
            if config.custom_rules:
                if not self._validate_custom_rules(question_data, config.custom_rules, result):
                    result.is_valid = False

            # Final checks
            result.validation_time = (datetime.now() - start_time).total_seconds()

            return result

        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Lỗi validation: {str(e)}")
            result.validation_time = (datetime.now() - start_time).total_seconds()
            return result

    def _validate_question_basic(self, question_data: Dict, result: ValidationResult) -> bool:
        """Validation cơ bản"""
        is_valid = True
        result.rules_checked += 1

        # Check required fields
        required_fields = ['content_text', 'tree_id']
        for field in required_fields:
            if not question_data.get(field):
                result.field_errors.setdefault(field, []).append(f"Trường {field} là bắt buộc")
                is_valid = False

        # Check data types
        if question_data.get('tree_id') and not isinstance(question_data['tree_id'], int):
            result.field_errors.setdefault('tree_id', []).append("tree_id phải là số nguyên")
            is_valid = False

        if is_valid:
            result.rules_passed += 1

        return is_valid

    def _validate_question_content(self, question_data: Dict,
                                   config: QuestionValidationConfig,
                                   result: ValidationResult) -> bool:
        """Validate nội dung câu hỏi"""
        is_valid = True
        content_text = question_data.get('content_text', '')

        if not content_text or not content_text.strip():
            result.field_errors.setdefault('content_text', []).append("Nội dung câu hỏi không được trống")
            return False

        result.rules_checked += 1

        # Check length
        if config.check_content_length:
            content_length = len(content_text.strip())

            if content_length < config.min_content_length:
                result.field_errors.setdefault('content_text', []).append(
                    f"Nội dung quá ngắn (tối thiểu {config.min_content_length} ký tự)"
                )
                is_valid = False

            if content_length > config.max_content_length:
                result.field_errors.setdefault('content_text', []).append(
                    f"Nội dung quá dài (tối đa {config.max_content_length} ký tự)"
                )
                is_valid = False

        # Check for meaningful content
        clean_content = re.sub(r'\s+', ' ', content_text).strip()
        if len(clean_content) < 5:
            result.warnings.append("Nội dung câu hỏi có vẻ quá ngắn")

        # Check for question indicators
        question_indicators = ['?', 'gì', 'nào', 'ai', 'đâu', 'khi nào', 'tại sao', 'như thế nào']
        has_question_indicator = any(indicator in content_text.lower() for indicator in question_indicators)
        if not has_question_indicator:
            result.warnings.append("Nội dung có vẻ không phải câu hỏi (không có dấu ? hoặc từ nghi vấn)")

        # Profanity check
        if config.enable_profanity_check:
            if self._contains_profanity(content_text):
                result.errors.append("Nội dung chứa từ ngữ không phù hợp")
                is_valid = False

        if is_valid:
            result.rules_passed += 1

        return is_valid

    def _validate_question_answer(self, question_data: Dict,
                                  config: QuestionValidationConfig,
                                  result: ValidationResult) -> bool:
        """Validate đáp án"""
        is_valid = True
        result.rules_checked += 1

        answer_text = question_data.get('answer_text', '')
        answer_data = question_data.get('answer_data')
        answer_type = question_data.get('answer_type', 'text')

        # Check if answer is required
        if config.check_answer_required:
            if not answer_text and not answer_data:
                result.field_errors.setdefault('answer', []).append("Câu hỏi phải có đáp án")
                is_valid = False

        # Validate answer format based on type
        if answer_text:
            if answer_type == 'multiple_choice':
                if not self._validate_multiple_choice_answer(answer_text, result):
                    is_valid = False
            elif answer_type == 'true_false':
                if not self._validate_true_false_answer(answer_text, result):
                    is_valid = False
            elif answer_type == 'fill_blank':
                if not self._validate_fill_blank_answer(answer_text, result):
                    is_valid = False

        if is_valid:
            result.rules_passed += 1

        return is_valid

    def _validate_question_formats(self, question_data: Dict,
                                   config: QuestionValidationConfig,
                                   result: ValidationResult) -> bool:
        """Validate formats (HTML, LaTeX, etc.)"""
        is_valid = True
        result.rules_checked += 1

        content_text = question_data.get('content_text', '')
        content_type = question_data.get('content_type', 'text')

        # HTML validation
        if config.check_html_tags and content_type == 'html':
            if not self._validate_html_content(content_text, result):
                is_valid = False

        # LaTeX validation
        if config.check_latex_syntax and ('$' in content_text or content_type == 'latex'):
            if not self._validate_latex_content(content_text, result):
                is_valid = False

        if is_valid:
            result.rules_passed += 1

        return is_valid

    def _validate_question_media(self, question_data: Dict,
                                 config: QuestionValidationConfig,
                                 result: ValidationResult) -> bool:
        """Validate media content"""
        is_valid = True
        result.rules_checked += 1

        content_data = question_data.get('content_data')
        answer_data = question_data.get('answer_data')

        # Validate images
        if config.check_image_format:
            for data_field, field_name in [(content_data, 'content_data'), (answer_data, 'answer_data')]:
                if data_field:
                    if not self._validate_image_data(data_field, config, result, field_name):
                        is_valid = False

        if is_valid:
            result.rules_passed += 1

        return is_valid

    def _validate_question_business_rules(self, question_data: Dict,
                                          config: QuestionValidationConfig,
                                          result: ValidationResult) -> bool:
        """Validate business rules"""
        is_valid = True
        result.rules_checked += 1

        # Check tree_id exists
        tree_id = question_data.get('tree_id')
        if tree_id:
            tree_exists = self.db.execute_query(
                "SELECT id FROM exercise_tree WHERE id = ?",
                (tree_id,), fetch="one"
            )
            if not tree_exists:
                result.field_errors.setdefault('tree_id', []).append("Tree ID không tồn tại")
                is_valid = False

        # Check for duplicate content
        if config.check_duplicate_content:
            content_text = question_data.get('content_text', '')
            if content_text:
                duplicate = self.db.execute_query(
                    "SELECT id FROM question_bank WHERE content_text = ? AND status != 'deleted'",
                    (content_text,), fetch="one"
                )
                if duplicate:
                    question_id = question_data.get('id')
                    if not question_id or duplicate['id'] != question_id:
                        result.warnings.append("Đã tồn tại câu hỏi có nội dung tương tự")

        # Validate difficulty level
        difficulty = question_data.get('difficulty_level')
        if difficulty:
            valid_difficulties = ['easy', 'medium', 'hard', 'expert']
            if difficulty not in valid_difficulties:
                result.field_errors.setdefault('difficulty_level', []).append(
                    f"Mức độ khó không hợp lệ. Phải là một trong: {', '.join(valid_difficulties)}"
                )
                is_valid = False

        # Validate question type
        question_type = question_data.get('question_type')
        if question_type:
            valid_types = ['knowledge', 'comprehension', 'application', 'analysis', 'synthesis', 'evaluation']
            if question_type not in valid_types:
                result.field_errors.setdefault('question_type', []).append(
                    f"Loại câu hỏi không hợp lệ. Phải là một trong: {', '.join(valid_types)}"
                )
                is_valid = False

        if is_valid:
            result.rules_passed += 1

        return is_valid

    # ========== SPECIFIC FORMAT VALIDATORS ==========

    def _validate_multiple_choice_answer(self, answer_text: str, result: ValidationResult) -> bool:
        """Validate đáp án trắc nghiệm"""
        try:
            # Try JSON format first
            try:
                answer_data = json.loads(answer_text)
                if not isinstance(answer_data, dict):
                    result.field_errors.setdefault('answer_text', []).append("Đáp án trắc nghiệm phải là object JSON")
                    return False

                if 'choices' not in answer_data:
                    result.field_errors.setdefault('answer_text', []).append(
                        "Đáp án trắc nghiệm thiếu trường 'choices'")
                    return False

                if 'correct' not in answer_data:
                    result.field_errors.setdefault('answer_text', []).append(
                        "Đáp án trắc nghiệm thiếu trường 'correct'")
                    return False

                choices = answer_data['choices']
                if not isinstance(choices, list) or len(choices) < 2:
                    result.field_errors.setdefault('answer_text', []).append("Trắc nghiệm phải có ít nhất 2 lựa chọn")
                    return False

                correct = answer_data['correct']
                if isinstance(correct, int):
                    if correct < 0 or correct >= len(choices):
                        result.field_errors.setdefault('answer_text', []).append("Chỉ số đáp án đúng không hợp lệ")
                        return False
                elif isinstance(correct, str):
                    if correct not in choices:
                        result.field_errors.setdefault('answer_text', []).append(
                            "Đáp án đúng không có trong danh sách lựa chọn")
                        return False

                return True

            except json.JSONDecodeError:
                # Try plain text format
                lines = answer_text.strip().split('\n')
                if len(lines) < 2:
                    result.field_errors.setdefault('answer_text', []).append(
                        "Trắc nghiệm phải có ít nhất 2 dòng lựa chọn")
                    return False

                # Look for correct answer indicator
                has_correct = any(line.strip().startswith(('*', '>', '✓')) for line in lines)
                if not has_correct:
                    result.warnings.append("Không tìm thấy dấu hiệu đáp án đúng (*, >, ✓)")

                return True

        except Exception as e:
            result.field_errors.setdefault('answer_text', []).append(f"Lỗi validate đáp án trắc nghiệm: {str(e)}")
            return False

    def _validate_true_false_answer(self, answer_text: str, result: ValidationResult) -> bool:
        """Validate đáp án đúng/sai"""
        answer_lower = answer_text.lower().strip()
        valid_answers = ['true', 'false', 'đúng', 'sai', '1', '0', 'yes', 'no', 'có', 'không']

        if answer_lower not in valid_answers:
            result.field_errors.setdefault('answer_text', []).append(
                f"Đáp án đúng/sai phải là một trong: {', '.join(valid_answers)}"
            )
            return False

        return True

    def _validate_fill_blank_answer(self, answer_text: str, result: ValidationResult) -> bool:
        """Validate đáp án điền vào chỗ trống"""
        if not answer_text or not answer_text.strip():
            result.field_errors.setdefault('answer_text', []).append("Đáp án điền chỗ trống không được trống")
            return False

        # Check for multiple acceptable answers
        if '|' in answer_text:
            answers = [ans.strip() for ans in answer_text.split('|')]
            if any(not ans for ans in answers):
                result.warnings.append("Có đáp án trống trong danh sách các đáp án có thể chấp nhận")

        return True

    def _validate_html_content(self, content: str, result: ValidationResult) -> bool:
        """Validate HTML content"""
        try:
            # Check for dangerous tags
            dangerous_tags = ['script', 'iframe', 'object', 'embed', 'form', 'input']
            for tag in dangerous_tags:
                if f'<{tag}' in content.lower():
                    result.errors.append(f"HTML chứa thẻ không an toàn: {tag}")
                    return False

            # Check for balanced tags (basic check)
            open_tags = re.findall(r'<([^/>]+)>', content)
            close_tags = re.findall(r'</([^>]+)>', content)

            # Remove self-closing tags
            open_tags = [tag.split()[0] for tag in open_tags if not tag.endswith('/')]

            if len(open_tags) != len(close_tags):
                result.warnings.append("HTML có vẻ không cân bằng thẻ mở/đóng")

            return True

        except Exception as e:
            result.errors.append(f"Lỗi validate HTML: {str(e)}")
            return False

    def _validate_latex_content(self, content: str, result: ValidationResult) -> bool:
        """Validate LaTeX content"""
        try:
            # Check for balanced math delimiters
            inline_count = content.count('$')
            if inline_count % 2 != 0:
                result.errors.append("LaTeX có dấu $ không cân bằng")
                return False

            # Check for block math delimiters
            block_open = content.count('$$')
            if block_open % 2 != 0:
                result.errors.append("LaTeX có dấu $$ không cân bằng")
                return False

            # Check for common LaTeX errors
            latex_patterns = [
                (r'\\[a-zA-Z]+', 'LaTeX commands found'),
                (r'\\frac{[^}]*}{[^}]*}', 'Fraction notation found'),
                (r'\\sqrt{[^}]*}', 'Square root notation found')
            ]

            for pattern, description in latex_patterns:
                if re.search(pattern, content):
                    result.info_messages.append(f"Phát hiện LaTeX: {description}")

            return True

        except Exception as e:
            result.errors.append(f"Lỗi validate LaTeX: {str(e)}")
            return False

    def _validate_image_data(self, image_data: Any,
                             config: QuestionValidationConfig,
                             result: ValidationResult,
                             field_name: str) -> bool:
        """Validate image data"""
        try:
            if isinstance(image_data, str):
                # Base64 encoded image
                try:
                    if ',' in image_data:
                        header, data = image_data.split(',', 1)
                        decoded_data = base64.b64decode(data)
                    else:
                        decoded_data = base64.b64decode(image_data)

                    # Check file size
                    size_mb = len(decoded_data) / (1024 * 1024)
                    if size_mb > config.max_image_size_mb:
                        result.field_errors.setdefault(field_name, []).append(
                            f"Ảnh quá lớn ({size_mb:.1f}MB > {config.max_image_size_mb}MB)"
                        )
                        return False

                    # Try to determine image format
                    if decoded_data.startswith(b'\xff\xd8\xff'):
                        format_ext = '.jpg'
                    elif decoded_data.startswith(b'\x89PNG'):
                        format_ext = '.png'
                    elif decoded_data.startswith(b'GIF8'):
                        format_ext = '.gif'
                    else:
                        result.warnings.append(f"Không thể xác định định dạng ảnh cho {field_name}")
                        return True

                    if format_ext not in config.allowed_image_formats:
                        result.field_errors.setdefault(field_name, []).append(
                            f"Định dạng ảnh không được hỗ trợ: {format_ext}"
                        )
                        return False

                except Exception as e:
                    result.field_errors.setdefault(field_name, []).append(
                        f"Không thể decode ảnh base64: {str(e)}"
                    )
                    return False

            elif isinstance(image_data, bytes):
                # Binary image data
                size_mb = len(image_data) / (1024 * 1024)
                if size_mb > config.max_image_size_mb:
                    result.field_errors.setdefault(field_name, []).append(
                        f"Ảnh quá lớn ({size_mb:.1f}MB > {config.max_image_size_mb}MB)"
                    )
                    return False

            return True

        except Exception as e:
            result.field_errors.setdefault(field_name, []).append(f"Lỗi validate ảnh: {str(e)}")
            return False

    # ========== TREE VALIDATION ==========

    def validate_tree_node(self, node_data: Dict[str, Any]) -> ValidationResult:
        """Validate tree node"""
        result = ValidationResult()
        result.rules_checked += 1

        try:
            # Required fields
            if not node_data.get('name') or not node_data.get('name').strip():
                result.field_errors.setdefault('name', []).append("Tên node không được trống")
                result.is_valid = False

            if not node_data.get('level'):
                result.field_errors.setdefault('level', []).append("Level không được trống")
                result.is_valid = False

            # Validate level
            valid_levels = ['subject', 'grade', 'chapter', 'section', 'topic', 'difficulty', 'type']
            level = node_data.get('level')
            if level and level not in valid_levels:
                result.field_errors.setdefault('level', []).append(
                    f"Level không hợp lệ. Phải là một trong: {', '.join(valid_levels)}"
                )
                result.is_valid = False

            # Check parent-child relationship
            parent_id = node_data.get('parent_id')
            if parent_id:
                parent_node = self.db.execute_query(
                    "SELECT level FROM exercise_tree WHERE id = ?",
                    (parent_id,), fetch="one"
                )
                if not parent_node:
                    result.field_errors.setdefault('parent_id', []).append("Parent node không tồn tại")
                    result.is_valid = False
                elif level:
                    if not self._validate_parent_child_level_relationship(parent_node['level'], level):
                        result.field_errors.setdefault('level', []).append(
                            f"Node level '{level}' không thể là con của parent level '{parent_node['level']}'"
                        )
                        result.is_valid = False

            # Check for duplicate names
            name = node_data.get('name', '').strip()
            if name and parent_id is not None:
                duplicate = self.db.execute_query(
                    "SELECT id FROM exercise_tree WHERE name = ? AND parent_id = ? AND id != ?",
                    (name, parent_id, node_data.get('id', 0)), fetch="one"
                )
                if duplicate:
                    result.field_errors.setdefault('name', []).append(
                        "Đã tồn tại node cùng tên trong cùng parent"
                    )
                    result.is_valid = False

            if result.is_valid:
                result.rules_passed += 1

            return result

        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Lỗi validate tree node: {str(e)}")
            return result

    def validate_tree_structure(self) -> ValidationResult:
        """Validate toàn bộ cấu trúc tree"""
        result = ValidationResult()

        try:
            # Get all nodes
            nodes = self.db.execute_query("SELECT * FROM exercise_tree", fetch="all") or []
            result.rules_checked = len(nodes)

            node_dict = {node['id']: node for node in nodes}

            for node in nodes:
                node_valid = True

                # Check parent exists
                parent_id = node['parent_id']
                if parent_id is not None and parent_id not in node_dict:
                    result.errors.append(f"Node '{node['name']}' có parent_id không tồn tại: {parent_id}")
                    node_valid = False

                # Check for circular references
                if self._has_circular_reference(node['id'], node_dict):
                    result.errors.append(f"Node '{node['name']}' tạo thành vòng lặp")
                    node_valid = False

                if node_valid:
                    result.rules_passed += 1

            result.is_valid = len(result.errors) == 0
            return result

        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Lỗi validate tree structure: {str(e)}")
            return result

    # ========== CUSTOM VALIDATION ==========

    def _validate_custom_rules(self, data: Dict, rules: List[ValidationRule],
                               result: ValidationResult) -> bool:
        """Validate custom rules"""
        is_valid = True

        for rule in rules:
            if not rule.enabled:
                continue

            result.rules_checked += 1

            try:
                # Get validator function
                validator_func = getattr(self, rule.validator_func, None)
                if not validator_func:
                    result.warnings.append(f"Không tìm thấy validator function: {rule.validator_func}")
                    continue

                # Run validation
                rule_result = validator_func(data, rule.params)

                if rule_result:
                    result.rules_passed += 1
                else:
                    is_valid = False
                    if rule.severity == ValidationSeverity.ERROR:
                        result.errors.append(f"Custom rule '{rule.name}': {rule.description}")
                    elif rule.severity == ValidationSeverity.WARNING:
                        result.warnings.append(f"Custom rule '{rule.name}': {rule.description}")
                    elif rule.severity == ValidationSeverity.INFO:
                        result.info_messages.append(f"Custom rule '{rule.name}': {rule.description}")
                        is_valid = True  # Info messages don't invalidate

            except Exception as e:
                result.warnings.append(f"Lỗi chạy custom rule '{rule.name}': {str(e)}")

        return is_valid

    # ========== HELPER METHODS ==========

    def _contains_profanity(self, text: str) -> bool:
        """Check if text contains profanity"""
        if not self.profanity_words:
            return False

        text_lower = text.lower()
        return any(word in text_lower for word in self.profanity_words)

    def _validate_parent_child_level_relationship(self, parent_level: str, child_level: str) -> bool:
        """Validate parent-child level relationship"""
        level_hierarchy = {
            None: ["subject"],
            "subject": ["grade", "chapter"],
            "grade": ["chapter", "topic"],
            "chapter": ["section", "topic"],
            "section": ["topic", "difficulty"],
            "topic": ["difficulty", "type"],
            "difficulty": ["type"],
            "type": []
        }

        allowed_children = level_hierarchy.get(parent_level, [])
        return child_level in allowed_children

    def _has_circular_reference(self, node_id: int, node_dict: Dict) -> bool:
        """Check for circular references in tree"""
        visited = set()
        current = node_id

        while current is not None:
            if current in visited:
                return True
            visited.add(current)
            current = node_dict.get(current, {}).get('parent_id')

        return False

    def _init_question_validation_rules(self) -> List[ValidationRule]:
        """Initialize question validation rules"""
        return [
            ValidationRule(
                name="content_required",
                description="Nội dung câu hỏi là bắt buộc",
                validator_func="_validate_content_required"
            ),
            ValidationRule(
                name="answer_required",
                description="Đáp án là bắt buộc",
                validator_func="_validate_answer_required"
            ),
            ValidationRule(
                name="tree_exists",
                description="Tree ID phải tồn tại",
                validator_func="_validate_tree_exists"
            )
        ]

    def _init_tree_validation_rules(self) -> List[ValidationRule]:
        """Initialize tree validation rules"""
        return [
            ValidationRule(
                name="name_required",
                description="Tên node là bắt buộc",
                validator_func="_validate_node_name_required"
            ),
            ValidationRule(
                name="level_valid",
                description="Level phải hợp lệ",
                validator_func="_validate_node_level_valid"
            )
        ]

    def _get_tree_validation_config(self) -> Dict:
        """Get tree validation configuration"""
        return {
            'check_circular_refs': True,
            'check_duplicate_names': True,
            'validate_hierarchy': True
        }

    def _load_profanity_words(self) -> List[str]:
        """Load profanity words list"""
        # This would typically load from a file or database
        # For now, return empty list
        return []

    # ========== VALIDATION RULE FUNCTIONS ==========

    def _validate_content_required(self, data: Dict, params: Dict) -> bool:
        """Validate content is required"""
        content = data.get('content_text', '')
        return bool(content and content.strip())

    def _validate_answer_required(self, data: Dict, params: Dict) -> bool:
        """Validate answer is required"""
        answer_text = data.get('answer_text', '')
        answer_data = data.get('answer_data')
        return bool(answer_text or answer_data)

    def _validate_tree_exists(self, data: Dict, params: Dict) -> bool:
        """Validate tree ID exists"""
        tree_id = data.get('tree_id')
        if not tree_id:
            return True  # Not required in this rule

        result = self.db.execute_query(
            "SELECT id FROM exercise_tree WHERE id = ?",
            (tree_id,), fetch="one"
        )
        return bool(result)

    def _validate_node_name_required(self, data: Dict, params: Dict) -> bool:
        """Validate node name is required"""
        name = data.get('name', '')
        return bool(name and name.strip())

    def _validate_node_level_valid(self, data: Dict, params: Dict) -> bool:
        """Validate node level is valid"""
        level = data.get('level')
        valid_levels = ['subject', 'grade', 'chapter', 'section', 'topic', 'difficulty', 'type']
        return level in valid_levels

    # ========== UTILITY METHODS ==========

    def create_validation_report(self, result: ValidationResult) -> str:
        """Create detailed validation report"""
        report_lines = []

        report_lines.append("=" * 50)
        report_lines.append("VALIDATION REPORT")
        report_lines.append("=" * 50)

        # Summary
        status = "✅ PASSED" if result.is_valid else "❌ FAILED"
        report_lines.append(f"Status: {status}")
        report_lines.append(f"Rules checked: {result.rules_checked}")
        report_lines.append(f"Rules passed: {result.rules_passed}")
        report_lines.append(f"Success rate: {result.success_rate:.1f}%")
        report_lines.append(f"Validation time: {result.validation_time:.3f}s")
        report_lines.append("")

        # Errors
        if result.errors:
            report_lines.append("❌ ERRORS:")
            for error in result.errors:
                report_lines.append(f"  - {error}")
            report_lines.append("")

        # Field Errors
        if result.field_errors:
            report_lines.append("🏷️ FIELD ERRORS:")
            for field, errors in result.field_errors.items():
                report_lines.append(f"  {field}:")
                for error in errors:
                    report_lines.append(f"    - {error}")
            report_lines.append("")

        # Warnings
        if result.warnings:
            report_lines.append("⚠️ WARNINGS:")
            for warning in result.warnings:
                report_lines.append(f"  - {warning}")
            report_lines.append("")

        # Info Messages
        if result.info_messages:
            report_lines.append("ℹ️ INFO:")
            for info in result.info_messages:
                report_lines.append(f"  - {info}")
            report_lines.append("")

        return "\n".join(report_lines)

    def get_validation_config(self) -> QuestionValidationConfig:
        """Get current validation configuration"""
        return self.question_config

    def set_validation_config(self, config: QuestionValidationConfig):
        """Set validation configuration"""
        self.question_config = config


# ========== TESTING ==========
if __name__ == "__main__":
    print("Testing ValidationService...")


    # Mock database for testing
    class MockDB:
        def execute_query(self, query, params=None, fetch=None):
            if 'exercise_tree' in query:
                return [{'id': 1, 'level': 'subject'}]
            return []


    # Test service
    service = ValidationService(MockDB())
    print("✅ ValidationService created successfully!")

    # Test question validation
    test_question = {
        'content_text': 'Giải phương trình x² + 2x + 1 = 0',
        'answer_text': 'x = -1',
        'tree_id': 1,
        'difficulty_level': 'medium',
        'question_type': 'knowledge'
    }

    result = service.validate_question(test_question)
    print(f"✅ Question validation test: {'PASSED' if result.is_valid else 'FAILED'}")

    # Print validation report
    if not result.is_valid:
        print("Validation Report:")
        print(service.create_validation_report(result))

    print("🎉 All tests completed!")