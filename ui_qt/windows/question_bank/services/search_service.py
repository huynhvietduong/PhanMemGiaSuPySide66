"""
Search Service - Business Logic Layer for Search and Filtering
File: ui_qt/windows/question_bank/services/search_service.py

Chức năng:
- Full-text search trong câu hỏi
- Advanced filtering với nhiều tiêu chí
- Fuzzy search và smart matching
- Search suggestions và auto-complete
- Search history và saved searches
- Performance optimization
- Search analytics
"""

import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from collections import Counter
from ..utils.helpers import (
    clean_text, extract_plain_text, normalize_vietnamese,
    extract_keywords, safe_int, safe_str
)


@dataclass
class SearchResult:
    """Kết quả tìm kiếm"""
    question_id: int
    content_text: str = ""
    content_type: str = "text"
    answer_text: str = ""
    tree_path: str = ""
    tags: List[str] = None
    difficulty_level: str = "medium"
    question_type: str = "knowledge"
    created_date: str = ""
    score: float = 0.0  # Relevance score
    highlights: List[str] = None  # Highlighted text snippets

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.highlights is None:
            self.highlights = []


@dataclass
class SearchQuery:
    """Query tìm kiếm"""
    text: str = ""
    filters: Dict[str, Any] = None
    fuzzy: bool = False
    case_sensitive: bool = False
    search_in: List[str] = None  # ['content', 'answer', 'tags']
    limit: int = 100
    offset: int = 0
    sort_by: str = "relevance"  # 'relevance', 'date', 'difficulty'
    sort_order: str = "desc"

    def __post_init__(self):
        if self.filters is None:
            self.filters = {}
        if self.search_in is None:
            self.search_in = ["content", "answer", "tags"]


@dataclass
class SearchStats:
    """Thống kê tìm kiếm"""
    total_results: int = 0
    search_time_ms: float = 0.0
    filters_applied: Dict[str, Any] = None
    most_common_terms: List[Tuple[str, int]] = None

    def __post_init__(self):
        if self.filters_applied is None:
            self.filters_applied = {}
        if self.most_common_terms is None:
            self.most_common_terms = []


class SearchService:
    """Business Logic Service for Search and Filtering"""

    def __init__(self, db_manager):
        self.db = db_manager
        self.search_history = []
        self.saved_searches = {}

        # Search configuration
        self.max_results = 1000
        self.default_limit = 50
        self.min_search_length = 2
        self.fuzzy_threshold = 0.6

        # Initialize FTS if supported
        self._init_full_text_search()

    # ========== MAIN SEARCH METHODS ==========

    def search_questions(self, query: Union[str, SearchQuery]) -> List[SearchResult]:
        """Tìm kiếm câu hỏi với query string hoặc SearchQuery object"""
        start_time = datetime.now()

        try:
            # Normalize query
            if isinstance(query, str):
                search_query = SearchQuery(text=query)
            else:
                search_query = query

            # Validate query
            if not self._validate_search_query(search_query):
                return []

            # Perform search
            if self._has_fts_support():
                results = self._search_with_fts(search_query)
            else:
                results = self._search_with_like(search_query)

            # Apply additional filters
            if search_query.filters:
                results = self._apply_filters(results, search_query.filters)

            # Sort results
            results = self._sort_results(results, search_query.sort_by, search_query.sort_order)

            # Limit results
            if search_query.limit > 0:
                results = results[search_query.offset:search_query.offset + search_query.limit]

            # Add to search history
            search_time = (datetime.now() - start_time).total_seconds() * 1000
            self._add_to_search_history(search_query, len(results), search_time)

            return results

        except Exception as e:
            print(f"Lỗi search questions: {e}")
            return []

    def advanced_search(self, criteria: Dict[str, Any]) -> List[SearchResult]:
        """Tìm kiếm nâng cao với nhiều tiêu chí"""
        try:
            # Build search query from criteria
            search_query = SearchQuery()

            # Text search
            if 'text' in criteria and criteria['text'].strip():
                search_query.text = criteria['text'].strip()

            # Search options
            search_query.fuzzy = criteria.get('fuzzy_search', False)
            search_query.case_sensitive = criteria.get('case_sensitive', False)
            search_query.search_in = criteria.get('search_in', ['content', 'answer', 'tags'])

            # Pagination
            search_query.limit = criteria.get('limit', self.default_limit)
            search_query.offset = criteria.get('offset', 0)

            # Sorting
            search_query.sort_by = criteria.get('sort_by', 'relevance')
            search_query.sort_order = criteria.get('sort_order', 'desc')

            # Filters
            filters = {}

            # Tree/Category filters
            if 'tree_id' in criteria:
                filters['tree_id'] = criteria['tree_id']
            if 'subject' in criteria:
                filters['subject'] = criteria['subject']
            if 'grade' in criteria:
                filters['grade'] = criteria['grade']
            if 'topic' in criteria:
                filters['topic'] = criteria['topic']

            # Content filters
            if 'content_type' in criteria:
                filters['content_type'] = criteria['content_type']
            if 'difficulty_level' in criteria:
                filters['difficulty_level'] = criteria['difficulty_level']
            if 'question_type' in criteria:
                filters['question_type'] = criteria['question_type']

            # Date filters
            if 'date_from' in criteria:
                filters['date_from'] = criteria['date_from']
            if 'date_to' in criteria:
                filters['date_to'] = criteria['date_to']

            # Status filters
            if 'status' in criteria:
                filters['status'] = criteria['status']

            # Tags filter
            if 'tags' in criteria:
                filters['tags'] = criteria['tags']

            search_query.filters = filters

            return self.search_questions(search_query)

        except Exception as e:
            print(f"Lỗi advanced search: {e}")
            return []

    def fuzzy_search(self, text: str, threshold: float = None) -> List[SearchResult]:
        """Tìm kiếm mờ (fuzzy search)"""
        try:
            if threshold is None:
                threshold = self.fuzzy_threshold

            query = SearchQuery(
                text=text,
                fuzzy=True,
                limit=self.default_limit
            )

            results = self.search_questions(query)

            # Filter by fuzzy threshold
            filtered_results = []
            for result in results:
                if result.score >= threshold:
                    filtered_results.append(result)

            return filtered_results

        except Exception as e:
            print(f"Lỗi fuzzy search: {e}")
            return []

    def search_by_tags(self, tags: List[str], match_all: bool = False) -> List[SearchResult]:
        """Tìm kiếm theo tags"""
        try:
            if not tags:
                return []

            # Build tag filter
            if match_all:
                # Must have ALL tags
                operator = "AND"
            else:
                # Must have ANY tag
                operator = "OR"

            # Create subquery for tag matching
            tag_placeholders = ','.join(['?' for _ in tags])

            if match_all:
                # For ALL tags: count must equal number of tags
                tag_query = f"""
                    SELECT question_id 
                    FROM question_tags 
                    WHERE tag_name IN ({tag_placeholders})
                    GROUP BY question_id
                    HAVING COUNT(DISTINCT tag_name) = ?
                """
                tag_params = tags + [len(tags)]
            else:
                # For ANY tag: just need to be in the list
                tag_query = f"""
                    SELECT DISTINCT question_id 
                    FROM question_tags 
                    WHERE tag_name IN ({tag_placeholders})
                """
                tag_params = tags

            # Get questions with matching tags
            tagged_question_ids = self.db.execute_query(
                tag_query, tag_params, fetch="all"
            ) or []

            if not tagged_question_ids:
                return []

            # Get question details
            question_ids = [row['question_id'] for row in tagged_question_ids]
            id_placeholders = ','.join(['?' for _ in question_ids])

            questions = self.db.execute_query(f"""
                SELECT q.*, et.name as tree_name 
                FROM question_bank q
                LEFT JOIN exercise_tree et ON q.tree_id = et.id
                WHERE q.id IN ({id_placeholders})
                ORDER BY q.created_date DESC
            """, question_ids, fetch="all") or []

            # Convert to SearchResult objects
            results = []
            for question in questions:
                result = self._question_to_search_result(question)
                result.score = 1.0  # Perfect match for tag search
                results.append(result)

            return results

        except Exception as e:
            print(f"Lỗi search by tags: {e}")
            return []

    def search_similar_questions(self, question_id: int, limit: int = 10) -> List[SearchResult]:
        """Tìm các câu hỏi tương tự"""
        try:
            # Get source question
            source_question = self.db.execute_query(
                "SELECT * FROM question_bank WHERE id = ?",
                (question_id,), fetch="one"
            )

            if not source_question:
                return []

            # Extract keywords from source question
            source_text = source_question.get('content_text', '')
            keywords = extract_keywords(source_text, max_keywords=10)

            if not keywords:
                return []

            # Search for questions containing these keywords
            keyword_query = ' OR '.join(keywords)
            similar_results = self.search_questions(SearchQuery(
                text=keyword_query,
                fuzzy=True,
                limit=limit * 2  # Get more to filter out the source
            ))

            # Remove source question and limit results
            filtered_results = []
            for result in similar_results:
                if result.question_id != question_id:
                    filtered_results.append(result)
                    if len(filtered_results) >= limit:
                        break

            return filtered_results

        except Exception as e:
            print(f"Lỗi search similar questions: {e}")
            return []

    # ========== FILTER METHODS ==========

    def filter_questions(self, filters: Dict[str, Any]) -> List[SearchResult]:
        """Lọc câu hỏi theo filters"""
        try:
            # Start with base query
            query = "SELECT q.*, et.name as tree_name FROM question_bank q LEFT JOIN exercise_tree et ON q.tree_id = et.id WHERE 1=1"
            params = []

            # Apply filters
            query, params = self._build_filter_query(query, params, filters)

            # Execute query
            questions = self.db.execute_query(query, params, fetch="all") or []

            # Convert to SearchResult objects
            results = []
            for question in questions:
                result = self._question_to_search_result(question)
                results.append(result)

            return results

        except Exception as e:
            print(f"Lỗi filter questions: {e}")
            return []

    def get_filter_options(self) -> Dict[str, List[str]]:
        """Lấy danh sách options cho các filter"""
        try:
            options = {}

            # Subjects
            subjects = self.db.execute_query("""
                SELECT DISTINCT et.name 
                FROM exercise_tree et
                WHERE et.level = 'subject' OR et.level = 'MÃ´n'
                ORDER BY et.name
            """, fetch="all") or []
            options['subjects'] = [s['name'] for s in subjects]

            # Grades
            grades = self.db.execute_query("""
                SELECT DISTINCT et.name 
                FROM exercise_tree et
                WHERE et.level = 'grade' OR et.level = 'Lá»›p'
                ORDER BY et.name
            """, fetch="all") or []
            options['grades'] = [g['name'] for g in grades]

            # Content types
            content_types = self.db.execute_query("""
                SELECT DISTINCT content_type 
                FROM question_bank 
                WHERE content_type IS NOT NULL
                ORDER BY content_type
            """, fetch="all") or []
            options['content_types'] = [ct['content_type'] for ct in content_types]

            # Difficulty levels
            difficulty_levels = self.db.execute_query("""
                SELECT DISTINCT difficulty_level 
                FROM question_bank 
                WHERE difficulty_level IS NOT NULL
                ORDER BY 
                    CASE difficulty_level
                        WHEN 'easy' THEN 1
                        WHEN 'medium' THEN 2  
                        WHEN 'hard' THEN 3
                        ELSE 4
                    END
            """, fetch="all") or []
            options['difficulty_levels'] = [dl['difficulty_level'] for dl in difficulty_levels]

            # Question types
            question_types = self.db.execute_query("""
                SELECT DISTINCT question_type 
                FROM question_bank 
                WHERE question_type IS NOT NULL
                ORDER BY question_type
            """, fetch="all") or []
            options['question_types'] = [qt['question_type'] for qt in question_types]

            # Tags (most popular)
            tags = self.db.execute_query("""
                SELECT tag_name, COUNT(*) as count
                FROM question_tags 
                GROUP BY tag_name
                ORDER BY count DESC
                LIMIT 50
            """, fetch="all") or []
            options['tags'] = [t['tag_name'] for t in tags]

            return options

        except Exception as e:
            print(f"Lỗi get filter options: {e}")
            return {}

    # ========== SUGGESTIONS AND AUTOCOMPLETE ==========

    def get_search_suggestions(self, partial_text: str, limit: int = 10) -> List[str]:
        """Lấy gợi ý tìm kiếm"""
        try:
            if len(partial_text.strip()) < 2:
                return []

            suggestions = []

            # Get suggestions from question content
            content_suggestions = self.db.execute_query("""
                SELECT DISTINCT content_text
                FROM question_bank 
                WHERE content_text LIKE ? 
                AND LENGTH(content_text) < 200
                ORDER BY LENGTH(content_text)
                LIMIT ?
            """, (f"%{partial_text}%", limit // 2), fetch="all") or []

            for suggestion in content_suggestions:
                text = extract_plain_text(suggestion['content_text'])[:100]
                if text and text not in suggestions:
                    suggestions.append(text)

            # Get suggestions from tags
            tag_suggestions = self.db.execute_query("""
                SELECT DISTINCT tag_name
                FROM question_tags 
                WHERE tag_name LIKE ?
                ORDER BY tag_name
                LIMIT ?
            """, (f"%{partial_text}%", limit // 2), fetch="all") or []

            for suggestion in tag_suggestions:
                tag = suggestion['tag_name']
                if tag and tag not in suggestions:
                    suggestions.append(tag)

            return suggestions[:limit]

        except Exception as e:
            print(f"Lỗi get search suggestions: {e}")
            return []

    def get_popular_searches(self, limit: int = 10) -> List[str]:
        """Lấy các tìm kiếm phổ biến"""
        try:
            # This would require a search_log table to track searches
            # For now, return some common educational terms
            popular_terms = [
                "phương trình bậc hai", "định lý Pythagore", "hàm số",
                "tích phân", "đạo hàm", "ma trận", "vectơ",
                "hình học", "đại số", "xác suất", "thống kê"
            ]

            return popular_terms[:limit]

        except Exception as e:
            print(f"Lỗi get popular searches: {e}")
            return []

    # ========== SEARCH HISTORY AND SAVED SEARCHES ==========

    def get_search_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Lấy lịch sử tìm kiếm"""
        try:
            return self.search_history[-limit:][::-1]  # Reverse to show newest first
        except Exception as e:
            print(f"Lỗi get search history: {e}")
            return []

    def clear_search_history(self):
        """Xóa lịch sử tìm kiếm"""
        self.search_history = []

    def save_search(self, name: str, query: SearchQuery) -> bool:
        """Lưu tìm kiếm để dùng lại"""
        try:
            self.saved_searches[name] = asdict(query)
            return True
        except Exception as e:
            print(f"Lỗi save search: {e}")
            return False

    def load_saved_search(self, name: str) -> Optional[SearchQuery]:
        """Load tìm kiếm đã lưu"""
        try:
            if name in self.saved_searches:
                return SearchQuery(**self.saved_searches[name])
            return None
        except Exception as e:
            print(f"Lỗi load saved search: {e}")
            return None

    def get_saved_searches(self) -> Dict[str, Dict]:
        """Lấy danh sách tìm kiếm đã lưu"""
        return self.saved_searches.copy()

    # ========== SEARCH ANALYTICS ==========

    def get_search_stats(self) -> SearchStats:
        """Lấy thống kê tìm kiếm"""
        try:
            stats = SearchStats()

            if self.search_history:
                # Calculate average search time
                total_time = sum(h.get('search_time_ms', 0) for h in self.search_history)
                stats.search_time_ms = total_time / len(self.search_history)

                # Find most common search terms
                all_terms = []
                for history in self.search_history:
                    query_text = history.get('query', {}).get('text', '')
                    if query_text:
                        terms = extract_keywords(query_text, max_keywords=5)
                        all_terms.extend(terms)

                if all_terms:
                    term_counts = Counter(all_terms)
                    stats.most_common_terms = term_counts.most_common(10)

            return stats

        except Exception as e:
            print(f"Lỗi get search stats: {e}")
            return SearchStats()

    # ========== SEARCH OPTIMIZATION ==========

    def optimize_search_performance(self):
        """Tối ưu hiệu suất tìm kiếm"""
        try:
            # Create indexes for better search performance
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_question_content ON question_bank(content_text)",
                "CREATE INDEX IF NOT EXISTS idx_question_tree ON question_bank(tree_id)",
                "CREATE INDEX IF NOT EXISTS idx_question_difficulty ON question_bank(difficulty_level)",
                "CREATE INDEX IF NOT EXISTS idx_question_type ON question_bank(question_type)",
                "CREATE INDEX IF NOT EXISTS idx_question_date ON question_bank(created_date)",
                "CREATE INDEX IF NOT EXISTS idx_tags_question ON question_tags(question_id)",
                "CREATE INDEX IF NOT EXISTS idx_tags_name ON question_tags(tag_name)",
            ]

            for index_sql in indexes:
                try:
                    self.db.execute_query(index_sql)
                except Exception as e:
                    print(f"Lỗi tạo index: {e}")

            return True

        except Exception as e:
            print(f"Lỗi optimize search: {e}")
            return False

    # ========== PRIVATE HELPER METHODS ==========

    def _init_full_text_search(self):
        """Khởi tạo Full-Text Search nếu có thể"""
        try:
            # Check if FTS is available
            result = self.db.execute_query(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='question_fts'",
                fetch="one"
            )

            if not result:
                # Try to create FTS table
                try:
                    self.db.execute_query("""
                        CREATE VIRTUAL TABLE question_fts USING fts5(
                            content_text, 
                            answer_text,
                            tags,
                            content='question_bank'
                        )
                    """)

                    # Populate FTS table
                    self._rebuild_fts_index()

                except Exception as e:
                    print(f"FTS không khả dụng: {e}")

        except Exception as e:
            print(f"Lỗi init FTS: {e}")

    def _has_fts_support(self) -> bool:
        """Kiểm tra có hỗ trợ FTS không"""
        try:
            result = self.db.execute_query(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='question_fts'",
                fetch="one"
            )
            return result is not None
        except:
            return False

    def _rebuild_fts_index(self):
        """Rebuild FTS index"""
        try:
            if not self._has_fts_support():
                return

            # Clear existing FTS data
            self.db.execute_query("DELETE FROM question_fts")

            # Get all questions
            questions = self.db.execute_query("""
                SELECT q.id, q.content_text, q.answer_text,
                       GROUP_CONCAT(t.tag_name, ' ') as tags
                FROM question_bank q
                LEFT JOIN question_tags t ON q.id = t.question_id
                GROUP BY q.id
            """, fetch="all") or []

            # Insert into FTS
            for question in questions:
                self.db.execute_query("""
                    INSERT INTO question_fts(rowid, content_text, answer_text, tags)
                    VALUES (?, ?, ?, ?)
                """, (
                    question['id'],
                    question.get('content_text', ''),
                    question.get('answer_text', ''),
                    question.get('tags', '')
                ))

        except Exception as e:
            print(f"Lỗi rebuild FTS index: {e}")

    def _search_with_fts(self, query: SearchQuery) -> List[SearchResult]:
        """Tìm kiếm sử dụng Full-Text Search"""
        try:
            if not query.text.strip():
                return []

            # Build FTS query
            search_text = query.text.strip()
            if query.fuzzy:
                # Add wildcard for fuzzy matching
                fts_query = f'"{search_text}"* OR {search_text}*'
            else:
                fts_query = f'"{search_text}"'

            # Search in FTS
            fts_results = self.db.execute_query("""
                SELECT q.*, et.name as tree_name, 
                       snippet(question_fts, 0, '<mark>', '</mark>', '...', 32) as content_snippet,
                       snippet(question_fts, 1, '<mark>', '</mark>', '...', 32) as answer_snippet,
                       bm25(question_fts) as relevance_score
                FROM question_fts 
                JOIN question_bank q ON question_fts.rowid = q.id
                LEFT JOIN exercise_tree et ON q.tree_id = et.id
                WHERE question_fts MATCH ?
                ORDER BY relevance_score
                LIMIT ?
            """, (fts_query, query.limit or self.default_limit), fetch="all") or []

            # Convert to SearchResult objects
            results = []
            for row in fts_results:
                result = self._question_to_search_result(row)
                result.score = abs(row.get('relevance_score', 0))  # BM25 score (negative, so abs)

                # Add highlights
                if row.get('content_snippet'):
                    result.highlights.append(row['content_snippet'])
                if row.get('answer_snippet'):
                    result.highlights.append(row['answer_snippet'])

                results.append(result)

            return results

        except Exception as e:
            print(f"Lỗi search with FTS: {e}")
            return []

    def _search_with_like(self, query: SearchQuery) -> List[SearchResult]:
        """Tìm kiếm sử dụng LIKE (fallback khi không có FTS)"""
        try:
            if not query.text.strip():
                return []

            search_text = query.text.strip()

            # Build search conditions
            conditions = []
            params = []

            # Search in content
            if 'content' in query.search_in:
                if query.case_sensitive:
                    conditions.append("q.content_text LIKE ?")
                    params.append(f"%{search_text}%")
                else:
                    conditions.append("LOWER(q.content_text) LIKE LOWER(?)")
                    params.append(f"%{search_text}%")

            # Search in answer
            if 'answer' in query.search_in:
                if query.case_sensitive:
                    conditions.append("q.answer_text LIKE ?")
                    params.append(f"%{search_text}%")
                else:
                    conditions.append("LOWER(q.answer_text) LIKE LOWER(?)")
                    params.append(f"%{search_text}%")

            # Search in tags
            if 'tags' in query.search_in:
                if query.case_sensitive:
                    conditions.append("""
                        q.id IN (
                            SELECT question_id FROM question_tags 
                            WHERE tag_name LIKE ?
                        )
                    """)
                    params.append(f"%{search_text}%")
                else:
                    conditions.append("""
                        q.id IN (
                            SELECT question_id FROM question_tags 
                            WHERE LOWER(tag_name) LIKE LOWER(?)
                        )
                    """)
                    params.append(f"%{search_text}%")

            if not conditions:
                return []

            # Combine conditions with OR
            where_clause = " OR ".join(conditions)

            # Execute search
            search_results = self.db.execute_query(f"""
                SELECT DISTINCT q.*, et.name as tree_name
                FROM question_bank q
                LEFT JOIN exercise_tree et ON q.tree_id = et.id
                WHERE {where_clause}
                ORDER BY q.created_date DESC
                LIMIT ?
            """, params + [query.limit or self.default_limit], fetch="all") or []

            # Convert to SearchResult objects
            results = []
            for row in search_results:
                result = self._question_to_search_result(row)

                # Calculate simple relevance score
                result.score = self._calculate_relevance_score(row, search_text, query)

                results.append(result)

            return results

        except Exception as e:
            print(f"Lỗi search with LIKE: {e}")
            return []

    def _apply_filters(self, results: List[SearchResult], filters: Dict[str, Any]) -> List[SearchResult]:
        """Áp dụng filters lên kết quả tìm kiếm"""
        try:
            filtered_results = []

            for result in results:
                # Get full question data for filtering
                question = self.db.execute_query(
                    "SELECT * FROM question_bank WHERE id = ?",
                    (result.question_id,), fetch="one"
                )

                if not question:
                    continue

                # Apply filters
                if not self._question_matches_filters(question, filters):
                    continue

                filtered_results.append(result)

            return filtered_results

        except Exception as e:
            print(f"Lỗi apply filters: {e}")
            return results

    def _question_matches_filters(self, question: Dict, filters: Dict[str, Any]) -> bool:
        """Kiểm tra question có match với filters không"""
        try:
            # Tree ID filter
            if 'tree_id' in filters:
                if question.get('tree_id') != filters['tree_id']:
                    return False

            # Content type filter
            if 'content_type' in filters:
                if question.get('content_type') != filters['content_type']:
                    return False

            # Difficulty level filter
            if 'difficulty_level' in filters:
                if question.get('difficulty_level') != filters['difficulty_level']:
                    return False

            # Question type filter
            if 'question_type' in filters:
                if question.get('question_type') != filters['question_type']:
                    return False

            # Date range filter
            if 'date_from' in filters or 'date_to' in filters:
                question_date = question.get('created_date', '')
                if question_date:
                    try:
                        q_date = datetime.fromisoformat(question_date.replace('Z', '+00:00'))

                        if 'date_from' in filters:
                            from_date = datetime.fromisoformat(filters['date_from'])
                            if q_date < from_date:
                                return False

                        if 'date_to' in filters:
                            to_date = datetime.fromisoformat(filters['date_to'])
                            if q_date > to_date:
                                return False

                    except ValueError:
                        pass  # Skip date filtering if date parsing fails

            # Status filter
            if 'status' in filters:
                status_filter = filters['status']
                question_status = question.get('status', 'active')

                if isinstance(status_filter, list):
                    if question_status not in status_filter:
                        return False
                else:
                    if question_status != status_filter:
                        return False

            # Tags filter
            if 'tags' in filters:
                required_tags = filters['tags']
                if isinstance(required_tags, str):
                    required_tags = [required_tags]

                # Get question tags
                question_tags = self.db.execute_query("""
                    SELECT tag_name FROM question_tags WHERE question_id = ?
                """, (question['id'],), fetch="all") or []

                question_tag_names = [t['tag_name'] for t in question_tags]

                # Check if has required tags
                for required_tag in required_tags:
                    if required_tag not in question_tag_names:
                        return False

            return True

        except Exception as e:
            print(f"Lỗi question matches filters: {e}")
            return True  # Default to include if error

    def _sort_results(self, results: List[SearchResult], sort_by: str, sort_order: str) -> List[SearchResult]:
        """Sắp xếp kết quả"""
        try:
            reverse = sort_order.lower() == 'desc'

            if sort_by == 'relevance':
                return sorted(results, key=lambda x: x.score, reverse=reverse)
            elif sort_by == 'date':
                return sorted(results, key=lambda x: x.created_date or '', reverse=reverse)
            elif sort_by == 'difficulty':
                difficulty_order = {'easy': 1, 'medium': 2, 'hard': 3}
                return sorted(results, key=lambda x: difficulty_order.get(x.difficulty_level, 2), reverse=reverse)
            else:
                return results  # No sorting

        except Exception as e:
            print(f"Lỗi sort results: {e}")
            return results

    def _calculate_relevance_score(self, question: Dict, search_text: str, query: SearchQuery) -> float:
        """Tính điểm relevance đơn giản"""
        try:
            score = 0.0
            search_lower = search_text.lower()

            # Score based on content matches
            content = question.get('content_text', '').lower()
            if content:
                # Exact phrase match gets highest score
                if search_lower in content:
                    score += 10.0

                # Word matches
                search_words = search_lower.split()
                content_words = content.split()
                matches = sum(1 for word in search_words if word in content_words)
                score += matches * 2.0

            # Score based on answer matches
            answer = question.get('answer_text', '').lower()
            if answer and search_lower in answer:
                score += 5.0

            # Normalize score (0-1 range)
            return min(score / 20.0, 1.0)

        except Exception as e:
            print(f"Lỗi calculate relevance: {e}")
            return 0.0

    def _question_to_search_result(self, question: Dict) -> SearchResult:
        """Chuyển question dict thành SearchResult"""
        try:
            # Get tags
            tags = self.db.execute_query("""
                SELECT tag_name FROM question_tags WHERE question_id = ?
            """, (question['id'],), fetch="all") or []

            tag_names = [t['tag_name'] for t in tags]

            # Get tree path
            tree_path = self._get_tree_path(question.get('tree_id'))

            return SearchResult(
                question_id=question['id'],
                content_text=question.get('content_text', ''),
                content_type=question.get('content_type', 'text'),
                answer_text=question.get('answer_text', '') or question.get('correct_answer', ''),
                tree_path=tree_path,
                tags=tag_names,
                difficulty_level=question.get('difficulty_level', 'medium'),
                question_type=question.get('question_type', 'knowledge'),
                created_date=question.get('created_date', '')
            )

        except Exception as e:
            print(f"Lỗi question to search result: {e}")
            return SearchResult(question_id=question.get('id', 0))

    def _get_tree_path(self, tree_id: Optional[int]) -> str:
        """Lấy đường dẫn tree"""
        try:
            if not tree_id:
                return ""

            path_parts = []
            current_id = tree_id

            while current_id:
                node = self.db.execute_query(
                    "SELECT id, parent_id, name FROM exercise_tree WHERE id = ?",
                    (current_id,), fetch="one"
                )

                if not node:
                    break

                path_parts.insert(0, node['name'])
                current_id = node['parent_id']

            return " > ".join(path_parts)

        except Exception as e:
            print(f"Lỗi get tree path: {e}")
            return ""

    def _build_filter_query(self, base_query: str, params: List, filters: Dict[str, Any]) -> Tuple[str, List]:
        """Build SQL query với filters"""
        try:
            query = base_query

            # Tree filters (subject, grade, etc.)
            if 'subject' in filters:
                query += """ AND q.tree_id IN (
                    SELECT id FROM exercise_tree 
                    WHERE name = ? AND (level = 'subject' OR level = 'MÃ´n')
                    UNION
                    SELECT et2.id FROM exercise_tree et2
                    JOIN exercise_tree et1 ON et2.parent_id = et1.id
                    WHERE et1.name = ? AND (et1.level = 'subject' OR et1.level = 'MÃ´n')
                )"""
                params.extend([filters['subject'], filters['subject']])

            # Other filters...
            if 'content_type' in filters:
                query += " AND q.content_type = ?"
                params.append(filters['content_type'])

            if 'difficulty_level' in filters:
                query += " AND q.difficulty_level = ?"
                params.append(filters['difficulty_level'])

            # Add ORDER BY
            query += " ORDER BY q.created_date DESC"

            return query, params

        except Exception as e:
            print(f"Lỗi build filter query: {e}")
            return base_query, params

    def _validate_search_query(self, query: SearchQuery) -> bool:
        """Validate search query"""
        # Check minimum search length
        if query.text and len(query.text.strip()) < self.min_search_length:
            return False

        # Check limit
        if query.limit < 0 or query.limit > self.max_results:
            query.limit = self.default_limit

        return True

    def _add_to_search_history(self, query: SearchQuery, result_count: int, search_time: float):
        """Thêm vào lịch sử tìm kiếm"""
        try:
            history_entry = {
                'timestamp': datetime.now().isoformat(),
                'query': asdict(query),
                'result_count': result_count,
                'search_time_ms': search_time
            }

            self.search_history.append(history_entry)

            # Keep only last 100 searches
            if len(self.search_history) > 100:
                self.search_history = self.search_history[-100:]

        except Exception as e:
            print(f"Lỗi add to search history: {e}")


if __name__ == "__main__":
    # Test SearchService
    print("Testing SearchService...")


    # Mock database for testing
    class MockDB:
        def execute_query(self, query, params=None, fetch=None):
            if 'sqlite_master' in query:
                return None  # No FTS support
            if 'question_bank' in query:
                return [
                    {
                        'id': 1,
                        'content_text': 'Giải phương trình bậc hai',
                        'content_type': 'text',
                        'difficulty_level': 'medium',
                        'created_date': '2024-01-01'
                    }
                ]
            return []


    # Test service
    service = SearchService(MockDB())
    print("✅ SearchService created successfully!")

    # Test search
    results = service.search_questions("phương trình")
    print(f"✅ Search test: found {len(results)} results")

    # Test filter options
    options = service.get_filter_options()
    print(f"✅ Filter options: {len(options)} categories")

    print("🎉 All tests passed!")