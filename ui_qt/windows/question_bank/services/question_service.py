"""
Question Service - Business Logic Layer for Question Management
File: ui_qt/windows/question_bank/services/question_service.py

Chức năng:
- CRUD operations cho question_bank
- Question validation và processing
- Content formatting và sanitization
- Image và media handling
- LaTeX support
- Answer processing
- Statistics và analytics
- Tag management
- Import/Export operations
- Question duplication detection
- Content versioning
"""

import json
import re
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from pathlib import Path

# Import utilities và repositories
from ..repositories.question_repository import QuestionRepository
from ..utils.helpers import (
    clean_text, extract_plain_text, normalize_vietnamese,
    safe_int, safe_str, generate_id
)
from ..utils.image_utils import ImageProcessor
from ..utils.file_utils import FileProcessor


@dataclass
class QuestionData:
    """Data class cho Question"""
    id: Optional[int] = None
    content_text: str = ""
    content_type: str = "text"  # text, html, markdown, latex
    answer_text: str = ""
    answer_type: str = "text"  # text, multiple_choice, true_false, fill_blank
    tree_id: Optional[int] = None

    # Extended properties
    difficulty_level: str = "medium"  # easy, medium, hard, expert
    question_type: str = "knowledge"  # knowledge, comprehension, application, analysis
    subject_code: str = ""
    topic: str = ""
    tags: List[str] = None

    # Media content
    content_data: Optional[bytes] = None  # Images, audio, video
    answer_data: Optional[bytes] = None

    # Metadata
    metadata: Dict[str, Any] = None
    created_date: Optional[str] = None
    modified_date: Optional[str] = None
    created_by: str = "system"
    status: str = "active"  # active, inactive, archived

    # Statistics
    usage_count: int = 0
    avg_score: float = 0.0
    estimated_time: int = 2  # minutes

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class QuestionStats:
    """Thống kê câu hỏi"""
    total_questions: int = 0
    by_difficulty: Dict[str, int] = None
    by_type: Dict[str, int] = None
    by_subject: Dict[str, int] = None
    by_status: Dict[str, int] = None
    recent_activity: List[Dict] = None

    def __post_init__(self):
        if self.by_difficulty is None:
            self.by_difficulty = {}
        if self.by_type is None:
            self.by_type = {}
        if self.by_subject is None:
            self.by_subject = {}
        if self.by_status is None:
            self.by_status = {}
        if self.recent_activity is None:
            self.recent_activity = []


class QuestionService:
    """Business Logic Service cho Question Management"""

    def __init__(self, db_manager):
        self.db = db_manager
        self.repository = QuestionRepository(db_manager)
        self.image_processor = ImageProcessor()
        self.file_processor = FileProcessor()

        # Question types và difficulty levels
        self.question_types = [
            "knowledge",  # Nhận biết
            "comprehension",  # Thông hiểu
            "application",  # Vận dụng
            "analysis",  # Phân tích
            "synthesis",  # Tổng hợp
            "evaluation"  # Đánh giá
        ]

        self.difficulty_levels = [
            "easy",  # Dễ
            "medium",  # Trung bình
            "hard",  # Khó
            "expert"  # Chuyên gia
        ]

        self.content_types = [
            "text",  # Text thuần
            "html",  # HTML formatting
            "markdown",  # Markdown
            "latex"  # LaTeX math
        ]

        self.answer_types = [
            "text",  # Tự luận
            "multiple_choice",  # Trắc nghiệm
            "true_false",  # Đúng/Sai
            "fill_blank",  # Điền vào chỗ trống
            "matching",  # Nối
            "ordering"  # Sắp xếp
        ]

    # ========== CRUD OPERATIONS ==========

    def create_question(self, question_data: QuestionData) -> Optional[int]:
        """Tạo câu hỏi mới"""
        try:
            # Validate dữ liệu
            if not self._validate_question_data(question_data):
                return None

            # Process content
            processed_data = self._process_question_content(question_data)

            # Set timestamps
            now = datetime.now().isoformat()
            processed_data.created_date = now
            processed_data.modified_date = now

            # Save to database
            question_id = self.repository.create_question(processed_data)

            if question_id:
                # Add tags if any
                if processed_data.tags:
                    self._add_question_tags(question_id, processed_data.tags)

                # Log activity
                self._log_question_activity(question_id, "created", "Tạo câu hỏi mới")

                print(f"✅ Đã tạo câu hỏi ID: {question_id}")
                return question_id

            return None

        except Exception as e:
            print(f"❌ Lỗi tạo câu hỏi: {e}")
            return None

    def get_question(self, question_id: int) -> Optional[QuestionData]:
        """Lấy thông tin câu hỏi theo ID"""
        try:
            question_dict = self.repository.get_question(question_id)
            if not question_dict:
                return None

            # Convert dict to QuestionData
            question_data = self._dict_to_question_data(question_dict)

            # Load tags
            tags = self.repository.get_question_tags(question_id)
            question_data.tags = [tag['tag_name'] for tag in tags]

            return question_data

        except Exception as e:
            print(f"❌ Lỗi lấy câu hỏi {question_id}: {e}")
            return None

    def update_question(self, question_id: int, question_data: QuestionData) -> bool:
        """Cập nhật câu hỏi"""
        try:
            # Validate dữ liệu
            if not self._validate_question_data(question_data):
                return False

            # Get original question for comparison
            original_question = self.get_question(question_id)
            if not original_question:
                return False

            # Process content
            processed_data = self._process_question_content(question_data)
            processed_data.id = question_id
            processed_data.modified_date = datetime.now().isoformat()

            # Update in database
            success = self.repository.update_question(question_id, processed_data)

            if success:
                # Update tags
                self._update_question_tags(question_id, processed_data.tags)

                # Log changes
                changes = self._detect_question_changes(original_question, processed_data)
                for change in changes:
                    self._log_question_activity(
                        question_id, "updated",
                        f"Cập nhật {change['field']}: {change['old']} -> {change['new']}"
                    )

                print(f"✅ Đã cập nhật câu hỏi ID: {question_id}")
                return True

            return False

        except Exception as e:
            print(f"❌ Lỗi cập nhật câu hỏi {question_id}: {e}")
            return False

    def delete_question(self, question_id: int, soft_delete: bool = True) -> bool:
        """Xóa câu hỏi (soft delete hoặc hard delete)"""
        try:
            if soft_delete:
                # Soft delete - chỉ đổi status
                success = self.repository.update_question_status(question_id, "deleted")
                if success:
                    self._log_question_activity(question_id, "deleted", "Xóa câu hỏi (soft delete)")
            else:
                # Hard delete - xóa hoàn toàn
                success = self.repository.delete_question(question_id)
                if success:
                    # Clean up related data
                    self.repository.delete_question_tags(question_id)
                    self.repository.delete_question_history(question_id)

            if success:
                print(f"✅ Đã xóa câu hỏi ID: {question_id}")
                return True

            return False

        except Exception as e:
            print(f"❌ Lỗi xóa câu hỏi {question_id}: {e}")
            return False

    # ========== QUERY METHODS ==========

    def get_questions_by_tree(self, tree_id: int,
                              filters: Optional[Dict] = None,
                              limit: Optional[int] = None) -> List[QuestionData]:
        """Lấy danh sách câu hỏi theo tree_id"""
        try:
            questions = self.repository.get_questions_by_tree(tree_id, filters, limit)
            return [self._dict_to_question_data(q) for q in questions]

        except Exception as e:
            print(f"❌ Lỗi lấy câu hỏi theo tree {tree_id}: {e}")
            return []

    def get_questions_by_criteria(self, criteria: Dict[str, Any]) -> List[QuestionData]:
        """Lấy câu hỏi theo nhiều tiêu chí"""
        try:
            questions = self.repository.get_questions_by_criteria(criteria)
            return [self._dict_to_question_data(q) for q in questions]

        except Exception as e:
            print(f"❌ Lỗi lấy câu hỏi theo criteria: {e}")
            return []

    def search_questions(self, query: str,
                         search_fields: List[str] = None,
                         limit: int = 50) -> List[QuestionData]:
        """Tìm kiếm câu hỏi"""
        try:
            if not search_fields:
                search_fields = ["content_text", "answer_text", "topic"]

            questions = self.repository.search_questions(query, search_fields, limit)
            return [self._dict_to_question_data(q) for q in questions]

        except Exception as e:
            print(f"❌ Lỗi tìm kiếm câu hỏi: {e}")
            return []

    # ========== VALIDATION METHODS ==========

    def _validate_question_data(self, question_data: QuestionData) -> bool:
        """Validate dữ liệu câu hỏi"""
        try:
            # Required fields
            if not question_data.content_text or not question_data.content_text.strip():
                print("❌ Nội dung câu hỏi không được trống")
                return False

            # Validate content type
            if question_data.content_type not in self.content_types:
                print(f"❌ Loại nội dung không hợp lệ: {question_data.content_type}")
                return False

            # Validate difficulty level
            if question_data.difficulty_level not in self.difficulty_levels:
                print(f"❌ Mức độ khó không hợp lệ: {question_data.difficulty_level}")
                return False

            # Validate question type
            if question_data.question_type not in self.question_types:
                print(f"❌ Loại câu hỏi không hợp lệ: {question_data.question_type}")
                return False

            # Validate answer type
            if question_data.answer_type not in self.answer_types:
                print(f"❌ Loại đáp án không hợp lệ: {question_data.answer_type}")
                return False

            # Content length validation
            if len(question_data.content_text) > 10000:
                print("❌ Nội dung câu hỏi quá dài (>10000 ký tự)")
                return False

            # Answer validation for specific types
            if question_data.answer_type == "multiple_choice":
                if not self._validate_multiple_choice_answer(question_data.answer_text):
                    return False

            return True

        except Exception as e:
            print(f"❌ Lỗi validate question data: {e}")
            return False

    def _validate_multiple_choice_answer(self, answer_text: str) -> bool:
        """Validate đáp án trắc nghiệm"""
        try:
            if not answer_text:
                print("❌ Đáp án trắc nghiệm không được trống")
                return False

            # Try to parse as JSON
            try:
                answer_data = json.loads(answer_text)
                if not isinstance(answer_data, dict):
                    return False

                # Required fields for multiple choice
                if 'choices' not in answer_data or 'correct' not in answer_data:
                    print("❌ Đáp án trắc nghiệm thiếu choices hoặc correct")
                    return False

                if len(answer_data['choices']) < 2:
                    print("❌ Trắc nghiệm cần ít nhất 2 lựa chọn")
                    return False

                return True

            except json.JSONDecodeError:
                # Plain text multiple choice - check format
                lines = answer_text.strip().split('\n')
                if len(lines) < 2:
                    print("❌ Trắc nghiệm cần ít nhất 2 dòng")
                    return False

                return True

        except Exception as e:
            print(f"❌ Lỗi validate multiple choice: {e}")
            return False

    # ========== CONTENT PROCESSING ==========

    def _process_question_content(self, question_data: QuestionData) -> QuestionData:
        """Xử lý nội dung câu hỏi"""
        try:
            # Clean và sanitize text content
            question_data.content_text = self._clean_content(question_data.content_text)
            question_data.answer_text = self._clean_content(question_data.answer_text)

            # Process LaTeX content
            if question_data.content_type == "latex":
                question_data.content_text = self._process_latex_content(question_data.content_text)

            # Process HTML content
            if question_data.content_type == "html":
                question_data.content_text = self._process_html_content(question_data.content_text)

            # Extract and normalize topic
            if not question_data.topic and question_data.tree_id:
                question_data.topic = self._extract_topic_from_tree(question_data.tree_id)

            # Auto-generate tags
            auto_tags = self._generate_auto_tags(question_data)
            if auto_tags:
                question_data.tags.extend(auto_tags)
                # Remove duplicates
                question_data.tags = list(set(question_data.tags))

            return question_data

        except Exception as e:
            print(f"❌ Lỗi process question content: {e}")
            return question_data

    def _clean_content(self, content: str) -> str:
        """Clean nội dung text"""
        if not content:
            return ""

        # Remove excessive whitespace
        content = re.sub(r'\s+', ' ', content.strip())

        # Remove HTML tags if not HTML content type
        content = re.sub(r'<[^>]+>', '', content)

        # Normalize Vietnamese
        content = normalize_vietnamese(content)

        return content

    def _process_latex_content(self, content: str) -> str:
        """Xử lý nội dung LaTeX"""
        try:
            # Validate LaTeX syntax
            latex_pattern = r'\$\$.*?\$\$|\$.*?\$'
            latex_matches = re.findall(latex_pattern, content, re.DOTALL)

            for match in latex_matches:
                # Basic LaTeX validation
                if match.count('$') % 2 != 0:
                    print(f"⚠️ LaTeX syntax error: {match}")

            return content

        except Exception as e:
            print(f"❌ Lỗi process LaTeX: {e}")
            return content

    def _process_html_content(self, content: str) -> str:
        """Xử lý nội dung HTML"""
        try:
            # Basic HTML sanitization
            allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'span', 'div', 'img']

            # Remove dangerous tags
            dangerous_pattern = r'<(?:script|iframe|object|embed|form)[^>]*>.*?</(?:script|iframe|object|embed|form)>'
            content = re.sub(dangerous_pattern, '', content, flags=re.IGNORECASE | re.DOTALL)

            return content

        except Exception as e:
            print(f"❌ Lỗi process HTML: {e}")
            return content

    def _generate_auto_tags(self, question_data: QuestionData) -> List[str]:
        """Tự động tạo tags từ nội dung"""
        try:
            auto_tags = []

            # Tags từ difficulty level
            auto_tags.append(f"level-{question_data.difficulty_level}")

            # Tags từ question type
            auto_tags.append(f"type-{question_data.question_type}")

            # Tags từ subject code
            if question_data.subject_code:
                auto_tags.append(f"subject-{question_data.subject_code}")

            # Tags từ keywords trong content
            keywords = self._extract_keywords(question_data.content_text)
            auto_tags.extend(keywords[:3])  # Chỉ lấy 3 keywords đầu

            return auto_tags

        except Exception as e:
            print(f"❌ Lỗi generate auto tags: {e}")
            return []

    def _extract_keywords(self, content: str) -> List[str]:
        """Trích xuất keywords từ nội dung"""
        try:
            # Danh sách stopwords tiếng Việt
            stopwords = {
                'là', 'của', 'và', 'có', 'được', 'trong', 'với', 'để', 'cho', 'từ',
                'một', 'hai', 'ba', 'bốn', 'năm', 'sáu', 'bảy', 'tám', 'chín', 'mười',
                'gì', 'ai', 'đâu', 'khi', 'nào', 'như', 'thế', 'sao', 'bao'
            }

            # Extract words
            words = re.findall(r'\b\w{3,}\b', content.lower())

            # Filter stopwords và tần suất
            word_freq = {}
            for word in words:
                if word not in stopwords:
                    word_freq[word] = word_freq.get(word, 0) + 1

            # Sort by frequency
            sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

            return [word[0] for word in sorted_words[:5]]

        except Exception as e:
            print(f"❌ Lỗi extract keywords: {e}")
            return []

    # ========== TAG MANAGEMENT ==========

    def _add_question_tags(self, question_id: int, tags: List[str]) -> bool:
        """Thêm tags cho câu hỏi"""
        try:
            for tag in tags:
                if tag and tag.strip():
                    self.repository.add_question_tag(question_id, tag.strip())
            return True

        except Exception as e:
            print(f"❌ Lỗi add question tags: {e}")
            return False

    def _update_question_tags(self, question_id: int, new_tags: List[str]) -> bool:
        """Cập nhật tags cho câu hỏi"""
        try:
            # Remove all existing tags
            self.repository.delete_question_tags(question_id)

            # Add new tags
            return self._add_question_tags(question_id, new_tags)

        except Exception as e:
            print(f"❌ Lỗi update question tags: {e}")
            return False

    # ========== UTILITY METHODS ==========

    def _dict_to_question_data(self, question_dict: Dict) -> QuestionData:
        """Convert dict sang QuestionData object"""
        try:
            # Parse metadata JSON
            metadata = {}
            if question_dict.get('metadata'):
                try:
                    metadata = json.loads(question_dict['metadata'])
                except json.JSONDecodeError:
                    metadata = {}

            # Parse tags from metadata hoặc separate tags
            tags = metadata.get('tags', [])

            return QuestionData(
                id=question_dict.get('id'),
                content_text=question_dict.get('content_text', ''),
                content_type=question_dict.get('content_type', 'text'),
                answer_text=question_dict.get('answer_text', ''),
                answer_type=question_dict.get('answer_type', 'text'),
                tree_id=question_dict.get('tree_id'),
                difficulty_level=question_dict.get('difficulty_level', 'medium'),
                question_type=question_dict.get('question_type', 'knowledge'),
                subject_code=question_dict.get('subject_code', ''),
                topic=question_dict.get('topic', ''),
                tags=tags,
                content_data=question_dict.get('content_data'),
                answer_data=question_dict.get('answer_data'),
                metadata=metadata,
                created_date=question_dict.get('created_date'),
                modified_date=question_dict.get('modified_date'),
                created_by=question_dict.get('created_by', 'system'),
                status=question_dict.get('status', 'active'),
                usage_count=question_dict.get('usage_count', 0),
                avg_score=question_dict.get('avg_score', 0.0),
                estimated_time=question_dict.get('estimated_time', 2)
            )

        except Exception as e:
            print(f"❌ Lỗi convert dict to QuestionData: {e}")
            return QuestionData()

    def _extract_topic_from_tree(self, tree_id: int) -> str:
        """Trích xuất topic từ tree hierarchy"""
        try:
            # Get tree path
            path_result = self.db.execute_query("""
                WITH RECURSIVE tree_path AS (
                    SELECT id, parent_id, name, level, 0 as depth
                    FROM exercise_tree WHERE id = ?
                    UNION ALL
                    SELECT et.id, et.parent_id, et.name, et.level, tp.depth + 1
                    FROM exercise_tree et
                    JOIN tree_path tp ON et.id = tp.parent_id
                )
                SELECT name, level FROM tree_path ORDER BY depth DESC
            """, (tree_id,), fetch="all")

            if path_result:
                # Find topic level
                for node in path_result:
                    if node['level'] in ['topic', 'chủ_đề', 'Chủ đề']:
                        return node['name']

                # Fallback to last node name
                return path_result[-1]['name']

            return ""

        except Exception as e:
            print(f"❌ Lỗi extract topic from tree: {e}")
            return ""

    def _detect_question_changes(self, old_question: QuestionData,
                                 new_question: QuestionData) -> List[Dict]:
        """Phát hiện thay đổi giữa 2 version câu hỏi"""
        changes = []

        # Check major fields
        fields_to_check = [
            'content_text', 'answer_text', 'difficulty_level',
            'question_type', 'subject_code', 'topic'
        ]

        for field in fields_to_check:
            old_value = getattr(old_question, field, "")
            new_value = getattr(new_question, field, "")

            if old_value != new_value:
                changes.append({
                    'field': field,
                    'old': old_value,
                    'new': new_value
                })

        return changes

    def _log_question_activity(self, question_id: int, action: str, description: str):
        """Ghi log hoạt động câu hỏi"""
        try:
            self.repository.add_question_history(
                question_id=question_id,
                action_type=action,
                field_changed="",
                old_value="",
                new_value="",
                reason=description
            )
        except Exception as e:
            print(f"❌ Lỗi log question activity: {e}")

    # ========== STATISTICS METHODS ==========

    def get_question_stats(self) -> QuestionStats:
        """Lấy thống kê câu hỏi"""
        try:
            stats = QuestionStats()

            # Total questions
            total_result = self.db.execute_query(
                "SELECT COUNT(*) as count FROM question_bank WHERE status != 'deleted'",
                fetch="one"
            )
            stats.total_questions = total_result['count'] if total_result else 0

            # By difficulty
            difficulty_result = self.db.execute_query("""
                SELECT difficulty_level, COUNT(*) as count
                FROM question_bank 
                WHERE status != 'deleted'
                GROUP BY difficulty_level
            """, fetch="all")

            for row in difficulty_result or []:
                stats.by_difficulty[row['difficulty_level']] = row['count']

            # By type
            type_result = self.db.execute_query("""
                SELECT question_type, COUNT(*) as count
                FROM question_bank 
                WHERE status != 'deleted'
                GROUP BY question_type
            """, fetch="all")

            for row in type_result or []:
                stats.by_type[row['question_type']] = row['count']

            # By subject
            subject_result = self.db.execute_query("""
                SELECT subject_code, COUNT(*) as count
                FROM question_bank 
                WHERE status != 'deleted' AND subject_code != ''
                GROUP BY subject_code
            """, fetch="all")

            for row in subject_result or []:
                stats.by_subject[row['subject_code']] = row['count']

            # Recent activity
            recent_result = self.db.execute_query("""
                SELECT id, content_text, created_date, modified_date
                FROM question_bank 
                WHERE status != 'deleted'
                ORDER BY COALESCE(modified_date, created_date) DESC
                LIMIT 10
            """, fetch="all")

            for row in recent_result or []:
                stats.recent_activity.append({
                    'id': row['id'],
                    'content': row['content_text'][:100] + '...' if len(row['content_text']) > 100 else row[
                        'content_text'],
                    'date': row['modified_date'] or row['created_date']
                })

            return stats

        except Exception as e:
            print(f"❌ Lỗi get question stats: {e}")
            return QuestionStats()

    def count_total_questions(self) -> int:
        """Đếm tổng số câu hỏi"""
        try:
            result = self.db.execute_query(
                "SELECT COUNT(*) as count FROM question_bank WHERE status != 'deleted'",
                fetch="one"
            )
            return result['count'] if result else 0

        except Exception as e:
            print(f"❌ Lỗi count questions: {e}")
            return 0

    def count_questions_by_tree(self, tree_id: int) -> int:
        """Đếm số câu hỏi theo tree_id"""
        try:
            result = self.db.execute_query(
                "SELECT COUNT(*) as count FROM question_bank WHERE tree_id = ? AND status != 'deleted'",
                (tree_id,), fetch="one"
            )
            return result['count'] if result else 0

        except Exception as e:
            print(f"❌ Lỗi count questions by tree: {e}")
            return 0

    # ========== BULK OPERATIONS ==========

    def bulk_update_questions(self, question_ids: List[int],
                              update_data: Dict[str, Any]) -> bool:
        """Cập nhật hàng loạt câu hỏi"""
        try:
            success_count = 0

            for question_id in question_ids:
                question = self.get_question(question_id)
                if question:
                    # Apply updates
                    for field, value in update_data.items():
                        if hasattr(question, field):
                            setattr(question, field, value)

                    if self.update_question(question_id, question):
                        success_count += 1

            print(f"✅ Đã cập nhật {success_count}/{len(question_ids)} câu hỏi")
            return success_count == len(question_ids)

        except Exception as e:
            print(f"❌ Lỗi bulk update: {e}")
            return False

    def bulk_delete_questions(self, question_ids: List[int],
                              soft_delete: bool = True) -> bool:
        """Xóa hàng loạt câu hỏi"""
        try:
            success_count = 0

            for question_id in question_ids:
                if self.delete_question(question_id, soft_delete):
                    success_count += 1

            print(f"✅ Đã xóa {success_count}/{len(question_ids)} câu hỏi")
            return success_count == len(question_ids)

        except Exception as e:
            print(f"❌ Lỗi bulk delete: {e}")
            return False

    def duplicate_question(self, question_id: int,
                           tree_id: Optional[int] = None) -> Optional[int]:
        """Nhân bản câu hỏi"""
        try:
            original_question = self.get_question(question_id)
            if not original_question:
                return None

            # Create duplicate
            duplicate_question = QuestionData(
                content_text=f"[BẢN SAO] {original_question.content_text}",
                content_type=original_question.content_type,
                answer_text=original_question.answer_text,
                answer_type=original_question.answer_type,
                tree_id=tree_id or original_question.tree_id,
                difficulty_level=original_question.difficulty_level,
                question_type=original_question.question_type,
                subject_code=original_question.subject_code,
                topic=original_question.topic,
                tags=original_question.tags.copy(),
                content_data=original_question.content_data,
                answer_data=original_question.answer_data,
                metadata=original_question.metadata.copy()
            )

            return self.create_question(duplicate_question)

        except Exception as e:
            print(f"❌ Lỗi duplicate question: {e}")
            return None


# ========== TESTING ==========
if __name__ == "__main__":
    print("Testing QuestionService...")


    # Mock database for testing
    class MockDB:
        def execute_query(self, query, params=None, fetch=None):
            return {'count': 10} if 'COUNT' in query else []


    # Test service
    service = QuestionService(MockDB())
    print("✅ QuestionService created successfully!")

    # Test question data
    test_question = QuestionData(
        content_text="Giải phương trình bậc hai ax² + bx + c = 0",
        answer_text="x = (-b ± √(b²-4ac)) / 2a",
        difficulty_level="medium",
        question_type="knowledge",
        tags=["toán", "phương trình", "bậc hai"]
    )

    # Test validation
    is_valid = service._validate_question_data(test_question)
    print(f"✅ Validation test: {is_valid}")

    print("🎉 All tests passed!")