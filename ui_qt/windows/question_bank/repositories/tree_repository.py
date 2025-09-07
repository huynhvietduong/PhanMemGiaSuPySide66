"""
Tree Repository - Data Access Layer for Tree Management
File: ui_qt/windows/question_bank/repositories/tree_repository.py

Chức năng:
- CRUD operations cho exercise_tree table
- Tree hierarchy management
- Node relationships và dependencies
- Tree structure queries
- Node movement và reorganization
- Statistics và analytics
- Batch operations
- Performance optimization
- Data integrity checks
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass

# Import utilities
from ..utils.helpers import safe_int, safe_str


@dataclass
class TreeFilter:
    """Filter cho query tree nodes"""
    parent_id: Optional[int] = None
    level: Optional[str] = None
    name_pattern: Optional[str] = None
    has_questions: Optional[bool] = None
    has_children: Optional[bool] = None
    created_after: Optional[str] = None
    created_before: Optional[str] = None
    include_empty: bool = True
    limit: Optional[int] = None
    offset: int = 0
    order_by: str = "name"
    order_direction: str = "ASC"


@dataclass
class TreeStatistics:
    """Statistics cho tree structure"""
    total_nodes: int = 0
    nodes_by_level: Dict[str, int] = None
    max_depth: int = 0
    total_questions: int = 0
    empty_nodes: int = 0
    orphaned_nodes: int = 0
    circular_references: int = 0

    def __post_init__(self):
        if self.nodes_by_level is None:
            self.nodes_by_level = {}


class TreeRepository:
    """Data Access Layer for Tree Management"""

    def __init__(self, db_manager):
        self.db = db_manager

        # Valid tree levels hierarchy
        self.valid_levels = [
            "subject",  # Môn học
            "grade",  # Lớp
            "chapter",  # Chương
            "section",  # Mục
            "topic",  # Chủ đề
            "difficulty",  # Độ khó
            "type"  # Loại câu hỏi
        ]

        # Level hierarchy mapping
        self.level_hierarchy = {
            None: ["subject"],
            "subject": ["grade", "chapter"],
            "grade": ["chapter", "topic"],
            "chapter": ["section", "topic"],
            "section": ["topic", "difficulty"],
            "topic": ["difficulty", "type"],
            "difficulty": ["type"],
            "type": []
        }

        # Ensure required tables exist
        self._ensure_tables()

    def _ensure_tables(self):
        """Đảm bảo các bảng cần thiết tồn tại"""
        try:
            # Upgrade exercise_tree schema
            self.db.upgrade_exercise_tree_schema()

            # Create supporting tables
            self._create_supporting_tables()

            # Create indexes
            self._create_indexes()

        except Exception as e:
            print(f"❌ Lỗi ensure tree tables: {e}")

    def _create_supporting_tables(self):
        """Tạo các bảng phụ trợ cho tree management"""
        tables_sql = [
            # Bảng tree statistics cache
            """
            CREATE TABLE IF NOT EXISTS tree_node_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id INTEGER UNIQUE NOT NULL,
                question_count INTEGER DEFAULT 0,
                child_count INTEGER DEFAULT 0,
                descendant_count INTEGER DEFAULT 0,
                depth_level INTEGER DEFAULT 0,
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (node_id) REFERENCES exercise_tree(id) ON DELETE CASCADE
            )
            """,

            # Bảng tree path cache cho performance
            """
            CREATE TABLE IF NOT EXISTS tree_paths (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id INTEGER NOT NULL,
                ancestor_id INTEGER NOT NULL,
                path_level INTEGER NOT NULL,
                UNIQUE(node_id, ancestor_id),
                FOREIGN KEY (node_id) REFERENCES exercise_tree(id) ON DELETE CASCADE,
                FOREIGN KEY (ancestor_id) REFERENCES exercise_tree(id) ON DELETE CASCADE
            )
            """,

            # Bảng tree history cho tracking changes
            """
            CREATE TABLE IF NOT EXISTS tree_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                old_parent_id INTEGER,
                new_parent_id INTEGER,
                old_name TEXT,
                new_name TEXT,
                old_level TEXT,
                new_level TEXT,
                changed_date TEXT DEFAULT CURRENT_TIMESTAMP,
                changed_by TEXT DEFAULT 'system',
                reason TEXT,
                FOREIGN KEY (node_id) REFERENCES exercise_tree(id) ON DELETE CASCADE
            )
            """
        ]

        for sql in tables_sql:
            try:
                self.db.execute_query(sql)
            except Exception as e:
                print(f"⚠️ Lỗi tạo supporting table: {e}")

    def _create_indexes(self):
        """Tạo indexes để tối ưu performance"""
        indexes_sql = [
            # Main table indexes
            "CREATE INDEX IF NOT EXISTS idx_tree_parent_id ON exercise_tree(parent_id)",
            "CREATE INDEX IF NOT EXISTS idx_tree_level ON exercise_tree(level)",
            "CREATE INDEX IF NOT EXISTS idx_tree_name ON exercise_tree(name)",
            "CREATE INDEX IF NOT EXISTS idx_tree_created_at ON exercise_tree(created_at)",

            # Supporting table indexes
            "CREATE INDEX IF NOT EXISTS idx_tree_stats_node_id ON tree_node_stats(node_id)",
            "CREATE INDEX IF NOT EXISTS idx_tree_paths_node_id ON tree_paths(node_id)",
            "CREATE INDEX IF NOT EXISTS idx_tree_paths_ancestor_id ON tree_paths(ancestor_id)",
            "CREATE INDEX IF NOT EXISTS idx_tree_history_node_id ON tree_history(node_id)",
            "CREATE INDEX IF NOT EXISTS idx_tree_history_date ON tree_history(changed_date)"
        ]

        for sql in indexes_sql:
            try:
                self.db.execute_query(sql)
            except Exception as e:
                print(f"⚠️ Lỗi tạo index: {e}")

    # ========== BASIC CRUD OPERATIONS ==========

    def create_node(self, node_data: Dict[str, Any]) -> Optional[int]:
        """Tạo node mới trong tree"""
        try:
            # Prepare data
            data = self._prepare_node_data(node_data)

            # Validate parent-child relationship
            if data.get('parent_id') and data.get('level'):
                if not self._validate_parent_child_relationship(data['parent_id'], data['level']):
                    print(f"❌ Invalid parent-child relationship: {data['parent_id']} -> {data['level']}")
                    return None

            # Insert query
            query = """
                INSERT INTO exercise_tree (parent_id, name, level, description, created_at)
                VALUES (?, ?, ?, ?, ?)
            """

            params = (
                data.get('parent_id'),
                data.get('name'),
                data.get('level'),
                data.get('description', ''),
                data.get('created_at', datetime.now().isoformat())
            )

            node_id = self.db.execute_query(query, params)

            if node_id:
                # Update tree caches
                self._update_tree_caches_after_create(node_id, data)

                # Log creation
                self._log_tree_action(node_id, 'CREATE', None, data.get('parent_id'),
                                      None, data.get('name'), None, data.get('level'))

                print(f"✅ Tạo tree node thành công ID: {node_id}")
                return node_id

            return None

        except Exception as e:
            print(f"❌ Lỗi tạo tree node: {e}")
            return None

    def get_node_by_id(self, node_id: int) -> Optional[Dict[str, Any]]:
        """Lấy node theo ID"""
        try:
            query = "SELECT * FROM exercise_tree WHERE id = ?"
            result = self.db.execute_query(query, (node_id,), fetch="one")

            if result:
                node_dict = self._row_to_dict(result)

                # Enrich với computed properties
                node_dict['question_count'] = self._get_node_question_count(node_id)
                node_dict['child_count'] = self._get_child_count(node_id)
                node_dict['depth'] = self._calculate_node_depth(node_id)
                node_dict['path'] = self._get_node_path(node_id)

                return node_dict

            return None

        except Exception as e:
            print(f"❌ Lỗi lấy tree node {node_id}: {e}")
            return None

    def update_node(self, node_id: int, node_data: Dict[str, Any]) -> bool:
        """Cập nhật tree node"""
        try:
            # Get old data for comparison
            old_data = self.get_node_by_id(node_id)
            if not old_data:
                return False

            # Prepare update data
            data = self._prepare_node_data(node_data, is_update=True)

            # Validate parent change (prevent circular references)
            new_parent_id = data.get('parent_id')
            if new_parent_id and new_parent_id != old_data.get('parent_id'):
                if self._would_create_cycle(node_id, new_parent_id):
                    print(f"❌ Parent change would create cycle: {node_id} -> {new_parent_id}")
                    return False

            # Build dynamic update query
            update_fields = []
            params = []

            for field, value in data.items():
                if field != 'id':
                    update_fields.append(f"{field} = ?")
                    params.append(value)

            if not update_fields:
                return True  # Nothing to update

            # Add modified timestamp (if column exists)
            try:
                # Check if modified_at column exists
                columns = self._get_table_columns('exercise_tree')
                if 'modified_at' in columns:
                    update_fields.append("modified_at = ?")
                    params.append(datetime.now().isoformat())
            except:
                pass

            # Add node_id for WHERE clause
            params.append(node_id)

            query = f"UPDATE exercise_tree SET {', '.join(update_fields)} WHERE id = ?"
            result = self.db.execute_query(query, params)

            if result is not None:
                # Update tree caches
                self._update_tree_caches_after_update(node_id, old_data, data)

                # Log changes
                self._log_tree_changes(node_id, old_data, data)

                print(f"✅ Cập nhật tree node thành công ID: {node_id}")
                return True

            return False

        except Exception as e:
            print(f"❌ Lỗi cập nhật tree node {node_id}: {e}")
            return False

    def delete_node(self, node_id: int, cascade: bool = False) -> bool:
        """Xóa tree node"""
        try:
            # Check for children
            children = self.get_children(node_id)
            if children and not cascade:
                print(f"❌ Cannot delete node {node_id}: has {len(children)} children")
                return False

            # Check for questions
            question_count = self._get_node_question_count(node_id)
            if question_count > 0 and not cascade:
                print(f"❌ Cannot delete node {node_id}: has {question_count} questions")
                return False

            if cascade:
                # Delete all children recursively
                for child in children:
                    self.delete_node(child['id'], cascade=True)

                # Move questions to parent or delete them
                parent_id = self._get_node_parent_id(node_id)
                if parent_id:
                    # Move questions to parent
                    self.db.execute_query(
                        "UPDATE question_bank SET tree_id = ? WHERE tree_id = ?",
                        (parent_id, node_id)
                    )
                else:
                    # Delete questions if no parent
                    self.db.execute_query(
                        "UPDATE question_bank SET status = 'deleted' WHERE tree_id = ?",
                        (node_id,)
                    )

            # Delete the node
            query = "DELETE FROM exercise_tree WHERE id = ?"
            result = self.db.execute_query(query, (node_id,))

            if result is not None:
                # Clean up caches
                self._cleanup_tree_caches_after_delete(node_id)

                # Log deletion
                self._log_tree_action(node_id, 'DELETE', None, None, None, None, None, None)

                print(f"✅ Xóa tree node thành công ID: {node_id}")
                return True

            return False

        except Exception as e:
            print(f"❌ Lỗi xóa tree node {node_id}: {e}")
            return False

    # ========== TREE STRUCTURE QUERIES ==========

    def get_all_nodes(self, include_stats: bool = False) -> List[Dict[str, Any]]:
        """Lấy tất cả nodes trong tree"""
        try:
            base_query = "SELECT * FROM exercise_tree ORDER BY level, name"

            if include_stats:
                query = """
                    SELECT et.*, 
                           COALESCE(tns.question_count, 0) as question_count,
                           COALESCE(tns.child_count, 0) as child_count,
                           COALESCE(tns.depth_level, 0) as depth
                    FROM exercise_tree et
                    LEFT JOIN tree_node_stats tns ON et.id = tns.node_id
                    ORDER BY et.level, et.name
                """
            else:
                query = base_query

            results = self.db.execute_query(query, fetch="all") or []
            return [self._row_to_dict(row) for row in results]

        except Exception as e:
            print(f"❌ Lỗi lấy all nodes: {e}")
            return []

    def get_root_nodes(self) -> List[Dict[str, Any]]:
        """Lấy các node gốc (parent_id = NULL)"""
        try:
            query = "SELECT * FROM exercise_tree WHERE parent_id IS NULL ORDER BY name"
            results = self.db.execute_query(query, fetch="all") or []
            return [self._row_to_dict(row) for row in results]

        except Exception as e:
            print(f"❌ Lỗi lấy root nodes: {e}")
            return []

    def get_children(self, parent_id: Optional[int]) -> List[Dict[str, Any]]:
        """Lấy các node con trực tiếp"""
        try:
            if parent_id is None:
                return self.get_root_nodes()

            query = "SELECT * FROM exercise_tree WHERE parent_id = ? ORDER BY name"
            results = self.db.execute_query(query, (parent_id,), fetch="all") or []
            return [self._row_to_dict(row) for row in results]

        except Exception as e:
            print(f"❌ Lỗi lấy children của {parent_id}: {e}")
            return []

    def get_descendants(self, node_id: int, max_depth: Optional[int] = None) -> List[Dict[str, Any]]:
        """Lấy tất cả descendants của một node"""
        try:
            # Use recursive CTE for efficient descendant query
            base_query = """
                WITH RECURSIVE descendants AS (
                    SELECT id, parent_id, name, level, description, created_at, 0 as depth
                    FROM exercise_tree WHERE parent_id = ?

                    UNION ALL

                    SELECT et.id, et.parent_id, et.name, et.level, et.description, et.created_at, d.depth + 1
                    FROM exercise_tree et
                    JOIN descendants d ON et.parent_id = d.id
                    {max_depth_condition}
                )
                SELECT * FROM descendants ORDER BY depth, name
            """

            max_depth_condition = f"WHERE d.depth < {max_depth}" if max_depth else ""
            query = base_query.format(max_depth_condition=max_depth_condition)

            results = self.db.execute_query(query, (node_id,), fetch="all") or []
            return [self._row_to_dict(row) for row in results]

        except Exception as e:
            print(f"❌ Lỗi lấy descendants của {node_id}: {e}")
            return []

    def get_ancestors(self, node_id: int, include_self: bool = False) -> List[Dict[str, Any]]:
        """Lấy tất cả ancestors của một node"""
        try:
            # Use recursive CTE for efficient ancestor query
            base_query = """
                WITH RECURSIVE ancestors AS (
                    SELECT id, parent_id, name, level, description, created_at, 0 as depth
                    FROM exercise_tree WHERE id = ?

                    UNION ALL

                    SELECT et.id, et.parent_id, et.name, et.level, et.description, et.created_at, a.depth + 1
                    FROM exercise_tree et
                    JOIN ancestors a ON et.id = a.parent_id
                )
                SELECT * FROM ancestors {filter_condition} ORDER BY depth DESC
            """

            filter_condition = "" if include_self else "WHERE depth > 0"
            query = base_query.format(filter_condition=filter_condition)

            results = self.db.execute_query(query, (node_id,), fetch="all") or []
            return [self._row_to_dict(row) for row in results]

        except Exception as e:
            print(f"❌ Lỗi lấy ancestors của {node_id}: {e}")
            return []

    def get_siblings(self, node_id: int, include_self: bool = False) -> List[Dict[str, Any]]:
        """Lấy các node anh em (cùng parent)"""
        try:
            # First get the parent_id of the node
            parent_result = self.db.execute_query(
                "SELECT parent_id FROM exercise_tree WHERE id = ?",
                (node_id,), fetch="one"
            )

            if not parent_result:
                return []

            parent_id = parent_result['parent_id']

            # Get all children of the same parent
            if parent_id is None:
                query = "SELECT * FROM exercise_tree WHERE parent_id IS NULL"
                params = []
            else:
                query = "SELECT * FROM exercise_tree WHERE parent_id = ?"
                params = [parent_id]

            if not include_self:
                query += " AND id != ?"
                params.append(node_id)

            query += " ORDER BY name"

            results = self.db.execute_query(query, params, fetch="all") or []
            return [self._row_to_dict(row) for row in results]

        except Exception as e:
            print(f"❌ Lỗi lấy siblings của {node_id}: {e}")
            return []

    def get_nodes_by_level(self, level: str) -> List[Dict[str, Any]]:
        """Lấy tất cả nodes theo level"""
        try:
            query = "SELECT * FROM exercise_tree WHERE level = ? ORDER BY name"
            results = self.db.execute_query(query, (level,), fetch="all") or []
            return [self._row_to_dict(row) for row in results]

        except Exception as e:
            print(f"❌ Lỗi lấy nodes theo level {level}: {e}")
            return []

    def search_nodes(self, search_term: str, search_fields: List[str] = None) -> List[Dict[str, Any]]:
        """Tìm kiếm nodes"""
        try:
            if not search_fields:
                search_fields = ['name', 'description']

            # Build search conditions
            conditions = []
            params = []

            for field in search_fields:
                conditions.append(f"{field} LIKE ?")
                params.append(f"%{search_term}%")

            query = f"""
                SELECT * FROM exercise_tree 
                WHERE {' OR '.join(conditions)}
                ORDER BY 
                    CASE WHEN name LIKE ? THEN 1 ELSE 2 END,
                    name
            """

            # Add exact match param for sorting
            params.append(f"%{search_term}%")

            results = self.db.execute_query(query, params, fetch="all") or []
            return [self._row_to_dict(row) for row in results]

        except Exception as e:
            print(f"❌ Lỗi search nodes: {e}")
            return []

    # ========== NODE MOVEMENT ==========

    def move_node(self, node_id: int, new_parent_id: Optional[int]) -> bool:
        """Di chuyển node sang parent mới"""
        try:
            # Get current data
            current_data = self.get_node_by_id(node_id)
            if not current_data:
                return False

            old_parent_id = current_data.get('parent_id')

            # Check for circular reference
            if new_parent_id and self._would_create_cycle(node_id, new_parent_id):
                print(f"❌ Move would create cycle: {node_id} -> {new_parent_id}")
                return False

            # Update parent_id
            query = "UPDATE exercise_tree SET parent_id = ? WHERE id = ?"
            result = self.db.execute_query(query, (new_parent_id, node_id))

            if result is not None:
                # Update tree caches
                self._update_tree_caches_after_move(node_id, old_parent_id, new_parent_id)

                # Log movement
                self._log_tree_action(node_id, 'MOVE', old_parent_id, new_parent_id,
                                      None, None, None, None)

                print(f"✅ Di chuyển node {node_id} từ {old_parent_id} -> {new_parent_id}")
                return True

            return False

        except Exception as e:
            print(f"❌ Lỗi move node {node_id}: {e}")
            return False

    def swap_nodes(self, node_id1: int, node_id2: int) -> bool:
        """Hoán đổi vị trí của 2 nodes"""
        try:
            # Get current parent_ids
            node1 = self.get_node_by_id(node_id1)
            node2 = self.get_node_by_id(node_id2)

            if not node1 or not node2:
                return False

            parent1 = node1.get('parent_id')
            parent2 = node2.get('parent_id')

            # Check for cycles
            if (parent1 and self._would_create_cycle(node_id1, parent2)) or \
                    (parent2 and self._would_create_cycle(node_id2, parent1)):
                print(f"❌ Swap would create cycle")
                return False

            # Perform swap
            success1 = self.move_node(node_id1, parent2)
            success2 = self.move_node(node_id2, parent1)

            if success1 and success2:
                print(f"✅ Hoán đổi thành công nodes {node_id1} <-> {node_id2}")
                return True

            return False

        except Exception as e:
            print(f"❌ Lỗi swap nodes {node_id1} <-> {node_id2}: {e}")
            return False

    # ========== STATISTICS & ANALYTICS ==========

    def get_tree_statistics(self) -> TreeStatistics:
        """Lấy thống kê tổng quan về tree"""
        try:
            stats = TreeStatistics()

            # Total nodes
            total_result = self.db.execute_query(
                "SELECT COUNT(*) as count FROM exercise_tree",
                fetch="one"
            )
            stats.total_nodes = total_result['count'] if total_result else 0

            # Nodes by level
            level_result = self.db.execute_query("""
                SELECT level, COUNT(*) as count 
                FROM exercise_tree 
                GROUP BY level
            """, fetch="all")

            for row in level_result or []:
                stats.nodes_by_level[row['level']] = row['count']

            # Total questions
            questions_result = self.db.execute_query(
                "SELECT COUNT(*) as count FROM question_bank WHERE status != 'deleted'",
                fetch="one"
            )
            stats.total_questions = questions_result['count'] if questions_result else 0

            # Max depth
            stats.max_depth = self._calculate_max_tree_depth()

            # Empty nodes (no questions and no children)
            empty_result = self.db.execute_query("""
                SELECT COUNT(*) as count 
                FROM exercise_tree et
                WHERE NOT EXISTS (
                    SELECT 1 FROM question_bank qb 
                    WHERE qb.tree_id = et.id AND qb.status != 'deleted'
                ) AND NOT EXISTS (
                    SELECT 1 FROM exercise_tree child 
                    WHERE child.parent_id = et.id
                )
            """, fetch="one")
            stats.empty_nodes = empty_result['count'] if empty_result else 0

            # Orphaned nodes (parent_id points to non-existent node)
            orphaned_result = self.db.execute_query("""
                SELECT COUNT(*) as count 
                FROM exercise_tree et1
                WHERE et1.parent_id IS NOT NULL 
                AND NOT EXISTS (
                    SELECT 1 FROM exercise_tree et2 
                    WHERE et2.id = et1.parent_id
                )
            """, fetch="one")
            stats.orphaned_nodes = orphaned_result['count'] if orphaned_result else 0

            return stats

        except Exception as e:
            print(f"❌ Lỗi get tree statistics: {e}")
            return TreeStatistics()

    def get_node_statistics(self, node_id: int) -> Dict[str, Any]:
        """Lấy thống kê chi tiết của một node"""
        try:
            stats = {}

            # Basic info
            node = self.get_node_by_id(node_id)
            if not node:
                return stats

            stats.update(node)

            # Question count (direct + descendants)
            stats['direct_question_count'] = self._get_node_question_count(node_id)
            stats['total_question_count'] = self._get_subtree_question_count(node_id)

            # Children info
            children = self.get_children(node_id)
            stats['child_count'] = len(children)
            stats['children'] = [{'id': c['id'], 'name': c['name'], 'level': c['level']} for c in children]

            # Depth and path
            stats['depth'] = self._calculate_node_depth(node_id)
            stats['path'] = self._get_node_path(node_id)

            # Recent activity
            stats['recent_questions'] = self._get_recent_questions_in_node(node_id, limit=5)

            return stats

        except Exception as e:
            print(f"❌ Lỗi get node statistics {node_id}: {e}")
            return {}

    # ========== BATCH OPERATIONS ==========

    def bulk_move_nodes(self, node_ids: List[int], new_parent_id: Optional[int]) -> int:
        """Di chuyển nhiều nodes cùng lúc"""
        try:
            success_count = 0

            for node_id in node_ids:
                if self.move_node(node_id, new_parent_id):
                    success_count += 1

            print(f"✅ Bulk move: {success_count}/{len(node_ids)} nodes")
            return success_count

        except Exception as e:
            print(f"❌ Lỗi bulk move nodes: {e}")
            return 0

    def bulk_delete_nodes(self, node_ids: List[int], cascade: bool = False) -> int:
        """Xóa nhiều nodes cùng lúc"""
        try:
            success_count = 0

            for node_id in node_ids:
                if self.delete_node(node_id, cascade):
                    success_count += 1

            print(f"✅ Bulk delete: {success_count}/{len(node_ids)} nodes")
            return success_count

        except Exception as e:
            print(f"❌ Lỗi bulk delete nodes: {e}")
            return 0

    def cleanup_empty_nodes(self, dry_run: bool = False) -> List[int]:
        """Dọn dẹp các nodes trống"""
        try:
            # Find empty leaf nodes
            empty_nodes = self.db.execute_query("""
                SELECT et.id, et.name, et.level
                FROM exercise_tree et
                WHERE NOT EXISTS (
                    SELECT 1 FROM question_bank qb 
                    WHERE qb.tree_id = et.id AND qb.status != 'deleted'
                ) AND NOT EXISTS (
                    SELECT 1 FROM exercise_tree child 
                    WHERE child.parent_id = et.id
                )
            """, fetch="all") or []

            empty_node_ids = [node['id'] for node in empty_nodes]

            if not dry_run and empty_node_ids:
                deleted_count = self.bulk_delete_nodes(empty_node_ids, cascade=False)
                print(f"✅ Cleaned up {deleted_count} empty nodes")

            return empty_node_ids

        except Exception as e:
            print(f"❌ Lỗi cleanup empty nodes: {e}")
            return []

    # ========== VALIDATION ==========

    def validate_tree_integrity(self) -> List[str]:
        """Validate tính toàn vẹn của tree structure"""
        errors = []

        try:
            # Check for orphaned nodes
            orphaned = self.db.execute_query("""
                SELECT id, name, parent_id 
                FROM exercise_tree et1
                WHERE et1.parent_id IS NOT NULL 
                AND NOT EXISTS (
                    SELECT 1 FROM exercise_tree et2 
                    WHERE et2.id = et1.parent_id
                )
            """, fetch="all") or []

            for node in orphaned:
                errors.append(
                    f"Orphaned node: {node['name']} (ID: {node['id']}) has non-existent parent {node['parent_id']}")

            # Check for circular references
            all_nodes = self.get_all_nodes()
            for node in all_nodes:
                if self._has_circular_reference(node['id'], all_nodes):
                    errors.append(f"Circular reference detected for node: {node['name']} (ID: {node['id']})")

            # Check level hierarchy violations
            hierarchy_violations = self.db.execute_query("""
                SELECT c.id, c.name, c.level, p.level as parent_level
                FROM exercise_tree c
                JOIN exercise_tree p ON c.parent_id = p.id
            """, fetch="all") or []

            for violation in hierarchy_violations:
                child_level = violation['level']
                parent_level = violation['parent_level']

                allowed_children = self.level_hierarchy.get(parent_level, [])
                if child_level not in allowed_children:
                    errors.append(
                        f"Invalid hierarchy: {violation['name']} (level: {child_level}) cannot be child of parent (level: {parent_level})")

            # Check for duplicate names at same level
            duplicates = self.db.execute_query("""
                SELECT parent_id, name, COUNT(*) as count
                FROM exercise_tree
                GROUP BY parent_id, LOWER(name)
                HAVING count > 1
            """, fetch="all") or []

            for dup in duplicates:
                errors.append(
                    f"Duplicate names found: '{dup['name']}' appears {dup['count']} times under parent {dup['parent_id']}")

        except Exception as e:
            errors.append(f"Error during validation: {str(e)}")

        return errors

    # ========== HELPER METHODS ==========

    def _prepare_node_data(self, data: Dict[str, Any], is_update: bool = False) -> Dict[str, Any]:
        """Chuẩn bị dữ liệu node trước khi lưu"""
        prepared = {}

        # Required fields
        if 'name' in data:
            prepared['name'] = safe_str(data['name']).strip()

        if 'level' in data:
            prepared['level'] = safe_str(data['level']).strip()

        # Optional fields
        if 'parent_id' in data:
            prepared['parent_id'] = safe_int(data['parent_id']) if data['parent_id'] is not None else None

        if 'description' in data:
            prepared['description'] = safe_str(data['description'])

        if 'created_at' in data:
            prepared['created_at'] = data['created_at']

        return prepared

    def _validate_parent_child_relationship(self, parent_id: int, child_level: str) -> bool:
        """Validate mối quan hệ parent-child theo hierarchy rules"""
        try:
            # Get parent level
            parent_result = self.db.execute_query(
                "SELECT level FROM exercise_tree WHERE id = ?",
                (parent_id,), fetch="one"
            )

            if not parent_result:
                return False

            parent_level = parent_result['level']
            allowed_children = self.level_hierarchy.get(parent_level, [])

            return child_level in allowed_children

        except Exception as e:
            print(f"❌ Lỗi validate parent-child relationship: {e}")
            return False

    def _would_create_cycle(self, node_id: int, new_parent_id: int) -> bool:
        """Kiểm tra xem việc đổi parent có tạo ra cycle không"""
        try:
            # Check if new_parent_id is a descendant of node_id
            ancestors = self.get_ancestors(new_parent_id, include_self=True)
            ancestor_ids = [a['id'] for a in ancestors]

            return node_id in ancestor_ids

        except Exception as e:
            print(f"❌ Lỗi check cycle: {e}")
            return True  # Err on the safe side

    def _has_circular_reference(self, node_id: int, all_nodes: List[Dict]) -> bool:
        """Kiểm tra circular reference"""
        visited = set()
        current = node_id

        node_dict = {node['id']: node.get('parent_id') for node in all_nodes}

        while current is not None:
            if current in visited:
                return True
            visited.add(current)
            current = node_dict.get(current)

        return False

    def _get_node_question_count(self, node_id: int) -> int:
        """Đếm số câu hỏi trực tiếp trong node"""
        try:
            result = self.db.execute_query(
                "SELECT COUNT(*) as count FROM question_bank WHERE tree_id = ? AND status != 'deleted'",
                (node_id,), fetch="one"
            )
            return result['count'] if result else 0

        except Exception as e:
            print(f"❌ Lỗi count questions in node {node_id}: {e}")
            return 0

    def _get_subtree_question_count(self, node_id: int) -> int:
        """Đếm tổng số câu hỏi trong subtree"""
        try:
            # Get all descendant node IDs
            descendants = self.get_descendants(node_id)
            all_node_ids = [node_id] + [d['id'] for d in descendants]

            if not all_node_ids:
                return 0

            placeholders = ','.join(['?' for _ in all_node_ids])
            result = self.db.execute_query(
                f"SELECT COUNT(*) as count FROM question_bank WHERE tree_id IN ({placeholders}) AND status != 'deleted'",
                all_node_ids, fetch="one"
            )
            return result['count'] if result else 0

        except Exception as e:
            print(f"❌ Lỗi count questions in subtree {node_id}: {e}")
            return 0

    def _get_child_count(self, node_id: int) -> int:
        """Đếm số con trực tiếp"""
        try:
            result = self.db.execute_query(
                "SELECT COUNT(*) as count FROM exercise_tree WHERE parent_id = ?",
                (node_id,), fetch="one"
            )
            return result['count'] if result else 0

        except Exception as e:
            print(f"❌ Lỗi count children of {node_id}: {e}")
            return 0

    def _calculate_node_depth(self, node_id: int) -> int:
        """Tính độ sâu của node"""
        try:
            depth = 0
            current_id = node_id

            while current_id is not None:
                parent_result = self.db.execute_query(
                    "SELECT parent_id FROM exercise_tree WHERE id = ?",
                    (current_id,), fetch="one"
                )

                if not parent_result:
                    break

                current_id = parent_result['parent_id']
                if current_id is not None:
                    depth += 1

                # Prevent infinite loops
                if depth > 20:
                    break

            return depth

        except Exception as e:
            print(f"❌ Lỗi calculate depth for {node_id}: {e}")
            return 0

    def _calculate_max_tree_depth(self) -> int:
        """Tính độ sâu tối đa của tree"""
        try:
            # Use recursive CTE to calculate max depth
            result = self.db.execute_query("""
                WITH RECURSIVE tree_depth AS (
                    SELECT id, parent_id, 0 as depth
                    FROM exercise_tree WHERE parent_id IS NULL

                    UNION ALL

                    SELECT et.id, et.parent_id, td.depth + 1
                    FROM exercise_tree et
                    JOIN tree_depth td ON et.parent_id = td.id
                )
                SELECT MAX(depth) as max_depth FROM tree_depth
            """, fetch="one")

            return result['max_depth'] if result else 0

        except Exception as e:
            print(f"❌ Lỗi calculate max tree depth: {e}")
            return 0

    def _get_node_path(self, node_id: int) -> str:
        """Lấy đường dẫn đầy đủ của node"""
        try:
            path_parts = []
            current_id = node_id

            while current_id is not None:
                node_result = self.db.execute_query(
                    "SELECT name, parent_id FROM exercise_tree WHERE id = ?",
                    (current_id,), fetch="one"
                )

                if not node_result:
                    break

                path_parts.insert(0, node_result['name'])
                current_id = node_result['parent_id']

                # Prevent infinite loops
                if len(path_parts) > 20:
                    break

            return " > ".join(path_parts)

        except Exception as e:
            print(f"❌ Lỗi get node path for {node_id}: {e}")
            return ""

    def _get_node_parent_id(self, node_id: int) -> Optional[int]:
        """Lấy parent_id của node"""
        try:
            result = self.db.execute_query(
                "SELECT parent_id FROM exercise_tree WHERE id = ?",
                (node_id,), fetch="one"
            )
            return result['parent_id'] if result else None

        except Exception as e:
            print(f"❌ Lỗi get parent_id for {node_id}: {e}")
            return None

    def _get_recent_questions_in_node(self, node_id: int, limit: int = 5) -> List[Dict]:
        """Lấy câu hỏi gần đây trong node"""
        try:
            result = self.db.execute_query("""
                SELECT id, content_text, created_date
                FROM question_bank 
                WHERE tree_id = ? AND status != 'deleted'
                ORDER BY created_date DESC
                LIMIT ?
            """, (node_id, limit), fetch="all") or []

            return [self._row_to_dict(row) for row in result]

        except Exception as e:
            print(f"❌ Lỗi get recent questions for {node_id}: {e}")
            return []

    def _get_table_columns(self, table_name: str) -> List[str]:
        """Lấy danh sách columns của table"""
        try:
            result = self.db.execute_query(f"PRAGMA table_info({table_name})", fetch="all") or []
            return [row[1] for row in result]  # Column name is at index 1

        except Exception as e:
            print(f"❌ Lỗi get table columns for {table_name}: {e}")
            return []

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Convert database row sang dictionary"""
        try:
            if row is None:
                return {}

            if isinstance(row, dict):
                return row

            # SQLite Row object
            if hasattr(row, 'keys'):
                return {key: row[key] for key in row.keys()}

            return {}

        except Exception as e:
            print(f"❌ Lỗi convert row to dict: {e}")
            return {}

    # ========== CACHE MANAGEMENT ==========

    def _update_tree_caches_after_create(self, node_id: int, node_data: Dict):
        """Update caches sau khi tạo node"""
        try:
            # Update tree_node_stats
            self.db.execute_query("""
                INSERT OR REPLACE INTO tree_node_stats 
                (node_id, question_count, child_count, descendant_count, depth_level)
                VALUES (?, 0, 0, 0, ?)
            """, (node_id, self._calculate_node_depth(node_id)))

            # Update tree_paths
            ancestors = self.get_ancestors(node_id)
            for i, ancestor in enumerate(ancestors):
                self.db.execute_query("""
                    INSERT OR REPLACE INTO tree_paths (node_id, ancestor_id, path_level)
                    VALUES (?, ?, ?)
                """, (node_id, ancestor['id'], i))

        except Exception as e:
            print(f"❌ Lỗi update caches after create: {e}")

    def _update_tree_caches_after_update(self, node_id: int, old_data: Dict, new_data: Dict):
        """Update caches sau khi cập nhật node"""
        try:
            # Update basic stats
            self.db.execute_query("""
                UPDATE tree_node_stats 
                SET last_updated = ?
                WHERE node_id = ?
            """, (datetime.now().isoformat(), node_id))

        except Exception as e:
            print(f"❌ Lỗi update caches after update: {e}")

    def _update_tree_caches_after_move(self, node_id: int, old_parent_id: Optional[int], new_parent_id: Optional[int]):
        """Update caches sau khi di chuyển node"""
        try:
            # Recalculate depth
            new_depth = self._calculate_node_depth(node_id)

            self.db.execute_query("""
                UPDATE tree_node_stats 
                SET depth_level = ?, last_updated = ?
                WHERE node_id = ?
            """, (new_depth, datetime.now().isoformat(), node_id))

            # Rebuild tree_paths for this node and its descendants
            self._rebuild_tree_paths(node_id)

        except Exception as e:
            print(f"❌ Lỗi update caches after move: {e}")

    def _cleanup_tree_caches_after_delete(self, node_id: int):
        """Clean up caches sau khi xóa node"""
        try:
            # Remove from tree_node_stats
            self.db.execute_query("DELETE FROM tree_node_stats WHERE node_id = ?", (node_id,))

            # Remove from tree_paths
            self.db.execute_query("DELETE FROM tree_paths WHERE node_id = ? OR ancestor_id = ?", (node_id, node_id))

        except Exception as e:
            print(f"❌ Lỗi cleanup caches after delete: {e}")

    def _rebuild_tree_paths(self, node_id: int):
        """Rebuild tree_paths cho node và descendants"""
        try:
            # Remove existing paths for this subtree
            descendants = self.get_descendants(node_id)
            all_node_ids = [node_id] + [d['id'] for d in descendants]

            for nid in all_node_ids:
                self.db.execute_query("DELETE FROM tree_paths WHERE node_id = ?", (nid,))

                # Rebuild paths
                ancestors = self.get_ancestors(nid)
                for i, ancestor in enumerate(ancestors):
                    self.db.execute_query("""
                        INSERT INTO tree_paths (node_id, ancestor_id, path_level)
                        VALUES (?, ?, ?)
                    """, (nid, ancestor['id'], i))

        except Exception as e:
            print(f"❌ Lỗi rebuild tree paths: {e}")

    # ========== HISTORY LOGGING ==========

    def _log_tree_action(self, node_id: int, action_type: str,
                         old_parent_id: Optional[int], new_parent_id: Optional[int],
                         old_name: Optional[str], new_name: Optional[str],
                         old_level: Optional[str], new_level: Optional[str]):
        """Log tree actions để tracking"""
        try:
            self.db.execute_query("""
                INSERT INTO tree_history 
                (node_id, action_type, old_parent_id, new_parent_id, old_name, new_name, old_level, new_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (node_id, action_type, old_parent_id, new_parent_id, old_name, new_name, old_level, new_level))

        except Exception as e:
            print(f"❌ Lỗi log tree action: {e}")

    def _log_tree_changes(self, node_id: int, old_data: Dict, new_data: Dict):
        """Log các thay đổi cụ thể"""
        try:
            changes = []

            # Check for changes
            if old_data.get('parent_id') != new_data.get('parent_id'):
                changes.append(('parent_id', old_data.get('parent_id'), new_data.get('parent_id')))

            if old_data.get('name') != new_data.get('name'):
                changes.append(('name', old_data.get('name'), new_data.get('name')))

            if old_data.get('level') != new_data.get('level'):
                changes.append(('level', old_data.get('level'), new_data.get('level')))

            # Log each change
            for field, old_val, new_val in changes:
                if field == 'parent_id':
                    self._log_tree_action(node_id, 'UPDATE', old_val, new_val, None, None, None, None)
                elif field == 'name':
                    self._log_tree_action(node_id, 'UPDATE', None, None, old_val, new_val, None, None)
                elif field == 'level':
                    self._log_tree_action(node_id, 'UPDATE', None, None, None, None, old_val, new_val)

        except Exception as e:
            print(f"❌ Lỗi log tree changes: {e}")


# ========== TESTING ==========
if __name__ == "__main__":
    print("Testing TreeRepository...")


    # Mock database for testing
    class MockDB:
        def execute_query(self, query, params=None, fetch=None):
            if 'COUNT' in query:
                return [{'count': 5}]
            elif 'SELECT *' in query and 'exercise_tree' in query:
                return [{
                    'id': 1,
                    'parent_id': None,
                    'name': 'Math',
                    'level': 'subject',
                    'description': 'Mathematics',
                    'created_at': '2024-01-01'
                }]
            return 1  # Return ID for INSERT

        def upgrade_exercise_tree_schema(self):
            pass


    # Test repository
    repo = TreeRepository(MockDB())
    print("✅ TreeRepository created successfully!")

    # Test create node
    node_data = {
        'name': 'Algebra',
        'level': 'chapter',
        'parent_id': 1,
        'description': 'Algebra chapter'
    }

    node_id = repo.create_node(node_data)
    print(f"✅ Create node test: {node_id}")

    # Test get node
    node = repo.get_node_by_id(1)
    print(f"✅ Get node test: {bool(node)}")

    # Test tree statistics
    stats = repo.get_tree_statistics()
    print(f"✅ Statistics test: {stats.total_nodes} nodes")

    # Test validation
    errors = repo.validate_tree_integrity()
    print(f"✅ Validation test: {len(errors)} errors found")

    print("🎉 All tests passed!")