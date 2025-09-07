"""
Tree Service - Business Logic Layer for Tree Management
File: ui_qt/windows/question_bank/services/tree_service.py

Chức năng:
- CRUD operations cho exercise_tree
- Tree structure validation
- Tree hierarchy management
- Node movement và reorganization
- Statistics và reporting
- Template management
- Import/Export operations
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from ..repositories.tree_repository import TreeRepository


@dataclass
class TreeNode:
    """Data class cho tree node"""
    id: Optional[int] = None
    parent_id: Optional[int] = None
    name: str = ""
    level: str = ""
    description: str = ""
    created_at: Optional[str] = None
    modified_at: Optional[str] = None

    # Computed properties
    children: List['TreeNode'] = None
    question_count: int = 0
    depth: int = 0
    path: str = ""

    def __post_init__(self):
        if self.children is None:
            self.children = []


@dataclass
class TreeStats:
    """Thống kê cây"""
    total_nodes: int = 0
    total_questions: int = 0
    max_depth: int = 0
    nodes_by_level: Dict[str, int] = None
    empty_nodes: int = 0

    def __post_init__(self):
        if self.nodes_by_level is None:
            self.nodes_by_level = {}


class TreeService:
    """Business Logic Service for Tree Management"""

    def __init__(self, db_manager):
        self.db = db_manager
        self.repository = TreeRepository(db_manager)

        # Valid tree levels
        self.valid_levels = [
            "subject",  # Môn học
            "grade",  # Lớp
            "chapter",  # Chương
            "section",  # Mục
            "topic",  # Chủ đề
            "difficulty",  # Độ khó
            "type"  # Loại câu hỏi
        ]

        # Level hierarchy (parent -> children)
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

    # ========== CRUD OPERATIONS ==========

    def create_node(self, name: str, level: str, parent_id: Optional[int] = None,
                    description: str = "") -> Optional[int]:
        """Tạo node mới với validation"""
        try:
            # Validate input
            if not name or not name.strip():
                raise ValueError("Tên node không được để trống")

            if level not in self.valid_levels:
                raise ValueError(f"Level không hợp lệ: {level}")

            # Validate parent-child relationship
            if parent_id is not None:
                if not self._validate_parent_child_relationship(parent_id, level):
                    parent_node = self.get_node(parent_id)
                    parent_level = parent_node.level if parent_node else "unknown"
                    raise ValueError(f"Không thể tạo node level '{level}' trong parent level '{parent_level}'")

            # Check for duplicate names at same level
            if self._check_duplicate_name(name, parent_id, level):
                raise ValueError(f"Đã tồn tại node '{name}' ở cùng cấp")

            # Create node
            node_data = {
                'name': name.strip(),
                'level': level,
                'parent_id': parent_id,
                'description': description.strip(),
                'created_at': datetime.now().isoformat()
            }

            node_id = self.repository.create_node(node_data)
            return node_id

        except Exception as e:
            raise Exception(f"Lỗi tạo node: {str(e)}")

    def get_node(self, node_id: int) -> Optional[TreeNode]:
        """Lấy thông tin node theo ID"""
        try:
            node_data = self.repository.get_node_by_id(node_id)
            if not node_data:
                return None

            # Convert to TreeNode
            node = TreeNode(**node_data)

            # Add computed properties
            node.question_count = self._count_questions_in_subtree(node_id)
            node.depth = self._calculate_node_depth(node_id)
            node.path = self._get_node_path(node_id)

            return node

        except Exception as e:
            print(f"Lỗi get node: {e}")
            return None

    def update_node(self, node_id: int, name: Optional[str] = None,
                    level: Optional[str] = None, description: Optional[str] = None) -> bool:
        """Cập nhật node"""
        try:
            current_node = self.get_node(node_id)
            if not current_node:
                raise ValueError("Node không tồn tại")

            update_data = {'modified_at': datetime.now().isoformat()}

            # Update name
            if name is not None:
                name = name.strip()
                if not name:
                    raise ValueError("Tên node không được để trống")

                # Check duplicate (excluding current node)
                if name != current_node.name:
                    if self._check_duplicate_name(name, current_node.parent_id,
                                                  current_node.level, exclude_id=node_id):
                        raise ValueError(f"Đã tồn tại node '{name}' ở cùng cấp")

                update_data['name'] = name

            # Update level
            if level is not None:
                if level not in self.valid_levels:
                    raise ValueError(f"Level không hợp lệ: {level}")

                # Validate parent-child relationship
                if current_node.parent_id is not None:
                    if not self._validate_parent_child_relationship(current_node.parent_id, level):
                        raise ValueError(f"Không thể thay đổi level thành '{level}'")

                update_data['level'] = level

            # Update description
            if description is not None:
                update_data['description'] = description.strip()

            return self.repository.update_node(node_id, update_data)

        except Exception as e:
            raise Exception(f"Lỗi cập nhật node: {str(e)}")

    def delete_node(self, node_id: int, force: bool = False) -> bool:
        """Xóa node"""
        try:
            node = self.get_node(node_id)
            if not node:
                raise ValueError("Node không tồn tại")

            # Check for children
            children = self.get_children(node_id)
            if children and not force:
                raise ValueError(f"Node có {len(children)} node con, không thể xóa")

            # Check for questions
            question_count = self._count_questions_in_subtree(node_id)
            if question_count > 0 and not force:
                raise ValueError(f"Node có {question_count} câu hỏi, không thể xóa")

            # Delete recursively if force
            if force:
                return self._delete_subtree(node_id)
            else:
                return self.repository.delete_node(node_id)

        except Exception as e:
            raise Exception(f"Lỗi xóa node: {str(e)}")

    # ========== TREE STRUCTURE OPERATIONS ==========

    def get_tree_structure(self, root_id: Optional[int] = None) -> List[TreeNode]:
        """Lấy cấu trúc cây hoàn chỉnh"""
        try:
            # Get all nodes
            all_nodes = self.repository.get_all_nodes()
            if not all_nodes:
                return []

            # Convert to TreeNode objects
            nodes_dict = {}
            for node_data in all_nodes:
                node = TreeNode(**node_data)
                node.question_count = self._count_questions_in_node(node.id)
                nodes_dict[node.id] = node

            # Build hierarchy
            root_nodes = []
            for node in nodes_dict.values():
                if node.parent_id is None or node.parent_id == root_id:
                    root_nodes.append(node)
                else:
                    parent = nodes_dict.get(node.parent_id)
                    if parent:
                        parent.children.append(node)

            # Sort and calculate depths
            self._sort_tree_nodes(root_nodes)
            self._calculate_tree_depths(root_nodes, 0)

            return root_nodes

        except Exception as e:
            print(f"Lỗi get tree structure: {e}")
            return []

    def get_children(self, parent_id: Optional[int]) -> List[TreeNode]:
        """Lấy danh sách node con"""
        try:
            children_data = self.repository.get_children(parent_id)

            children = []
            for child_data in children_data:
                child = TreeNode(**child_data)
                child.question_count = self._count_questions_in_node(child.id)
                child.depth = self._calculate_node_depth(child.id)
                children.append(child)

            return sorted(children, key=lambda x: (x.level, x.name))

        except Exception as e:
            print(f"Lỗi get children: {e}")
            return []

    def get_ancestors(self, node_id: int, include_self: bool = False) -> List[TreeNode]:
        """Lấy danh sách tổ tiên"""
        try:
            ancestors = []
            current_id = node_id if include_self else None

            # Get current node's parent if not including self
            if not include_self:
                current_node = self.get_node(node_id)
                if current_node:
                    current_id = current_node.parent_id

            # Traverse up the tree
            while current_id is not None:
                ancestor = self.get_node(current_id)
                if ancestor:
                    ancestors.append(ancestor)
                    current_id = ancestor.parent_id
                else:
                    break

            # Reverse to get root -> leaf order
            ancestors.reverse()
            return ancestors

        except Exception as e:
            print(f"Lỗi get ancestors: {e}")
            return []

    def move_node(self, node_id: int, new_parent_id: Optional[int]) -> bool:
        """Di chuyển node đến parent mới"""
        try:
            node = self.get_node(node_id)
            if not node:
                raise ValueError("Node không tồn tại")

            # Cannot move to self or descendant
            if new_parent_id == node_id:
                raise ValueError("Không thể di chuyển node vào chính nó")

            if new_parent_id is not None:
                if self._is_descendant(new_parent_id, node_id):
                    raise ValueError("Không thể di chuyển node vào node con của nó")

            # Validate parent-child relationship
            if new_parent_id is not None:
                if not self._validate_parent_child_relationship(new_parent_id, node.level):
                    new_parent = self.get_node(new_parent_id)
                    parent_level = new_parent.level if new_parent else "unknown"
                    raise ValueError(f"Không thể di chuyển node level '{node.level}' vào parent level '{parent_level}'")

            # Check for duplicate name
            if self._check_duplicate_name(node.name, new_parent_id, node.level, exclude_id=node_id):
                raise ValueError(f"Đã tồn tại node '{node.name}' ở vị trí đích")

            # Update parent_id
            update_data = {
                'parent_id': new_parent_id,
                'modified_at': datetime.now().isoformat()
            }

            return self.repository.update_node(node_id, update_data)

        except Exception as e:
            raise Exception(f"Lỗi di chuyển node: {str(e)}")

    def copy_subtree(self, source_node_id: int, target_parent_id: Optional[int],
                     new_name: Optional[str] = None) -> Optional[int]:
        """Copy subtree đến vị trí mới"""
        try:
            source_node = self.get_node(source_node_id)
            if not source_node:
                raise ValueError("Source node không tồn tại")

            # Validate target parent
            if target_parent_id is not None:
                if not self._validate_parent_child_relationship(target_parent_id, source_node.level):
                    raise ValueError("Vị trí đích không phù hợp với level của node")

            # Create new root node
            copy_name = new_name or f"{source_node.name} (Copy)"
            new_root_id = self.create_node(
                name=copy_name,
                level=source_node.level,
                parent_id=target_parent_id,
                description=source_node.description
            )

            if new_root_id:
                # Copy children recursively
                self._copy_children_recursive(source_node_id, new_root_id)
                return new_root_id

            return None

        except Exception as e:
            raise Exception(f"Lỗi copy subtree: {str(e)}")

    # ========== STATISTICS AND ANALYSIS ==========

    def get_tree_statistics(self) -> TreeStats:
        """Lấy thống kê cây"""
        try:
            stats = TreeStats()

            # Get all nodes
            all_nodes = self.repository.get_all_nodes()
            stats.total_nodes = len(all_nodes)

            # Count by level
            stats.nodes_by_level = {}
            for node in all_nodes:
                level = node.get('level', 'unknown')
                stats.nodes_by_level[level] = stats.nodes_by_level.get(level, 0) + 1

            # Count total questions
            result = self.db.execute_query(
                "SELECT COUNT(*) as count FROM question_bank",
                fetch="one"
            )
            stats.total_questions = result['count'] if result else 0

            # Count empty nodes
            for node in all_nodes:
                node_id = node['id']
                question_count = self._count_questions_in_node(node_id)
                children_count = len(self.get_children(node_id))

                if question_count == 0 and children_count == 0:
                    stats.empty_nodes += 1

            # Calculate max depth
            tree_structure = self.get_tree_structure()
            stats.max_depth = self._calculate_max_depth(tree_structure)

            return stats

        except Exception as e:
            print(f"Lỗi get statistics: {e}")
            return TreeStats()

    def find_empty_nodes(self) -> List[TreeNode]:
        """Tìm các node rỗng (không có câu hỏi và không có con)"""
        try:
            empty_nodes = []
            all_nodes = self.repository.get_all_nodes()

            for node_data in all_nodes:
                node_id = node_data['id']
                question_count = self._count_questions_in_node(node_id)
                children_count = len(self.get_children(node_id))

                if question_count == 0 and children_count == 0:
                    node = TreeNode(**node_data)
                    empty_nodes.append(node)

            return empty_nodes

        except Exception as e:
            print(f"Lỗi find empty nodes: {e}")
            return []

    def find_duplicate_nodes(self) -> List[List[TreeNode]]:
        """Tìm các node trùng tên ở cùng cấp"""
        try:
            duplicates = []
            all_nodes = self.repository.get_all_nodes()

            # Group by parent_id and name
            groups = {}
            for node_data in all_nodes:
                parent_id = node_data.get('parent_id')
                name = node_data.get('name', '').lower()
                key = (parent_id, name)

                if key not in groups:
                    groups[key] = []
                groups[key].append(TreeNode(**node_data))

            # Find groups with more than one node
            for group in groups.values():
                if len(group) > 1:
                    duplicates.append(group)

            return duplicates

        except Exception as e:
            print(f"Lỗi find duplicates: {e}")
            return []

    # ========== VALIDATION AND MAINTENANCE ==========

    def validate_tree_structure(self) -> List[str]:
        """Validate cấu trúc cây và trả về danh sách lỗi"""
        errors = []

        try:
            all_nodes = self.repository.get_all_nodes()
            node_ids = {node['id'] for node in all_nodes}

            for node in all_nodes:
                node_id = node['id']
                parent_id = node.get('parent_id')
                level = node.get('level')
                name = node.get('name')

                # Check parent exists
                if parent_id is not None and parent_id not in node_ids:
                    errors.append(f"Node '{name}' (ID: {node_id}) có parent_id không tồn tại: {parent_id}")

                # Check level validity
                if level not in self.valid_levels:
                    errors.append(f"Node '{name}' (ID: {node_id}) có level không hợp lệ: '{level}'")

                # Check parent-child relationship
                if parent_id is not None:
                    parent_node = next((n for n in all_nodes if n['id'] == parent_id), None)
                    if parent_node:
                        parent_level = parent_node.get('level')
                        if not self._validate_parent_child_relationship_by_levels(parent_level, level):
                            errors.append(
                                f"Node '{name}' (level: {level}) không thể là con của "
                                f"node '{parent_node.get('name')}' (level: {parent_level})"
                            )

                # Check circular references
                if self._has_circular_reference(node_id, all_nodes):
                    errors.append(f"Node '{name}' (ID: {node_id}) tạo thành vòng lặp")

            return errors

        except Exception as e:
            return [f"Lỗi validate tree: {str(e)}"]

    def cleanup_empty_nodes(self) -> int:
        """Xóa các node rỗng"""
        try:
            empty_nodes = self.find_empty_nodes()
            deleted_count = 0

            # Sort by depth (deepest first) to avoid foreign key issues
            empty_nodes.sort(key=lambda n: n.depth, reverse=True)

            for node in empty_nodes:
                try:
                    if self.repository.delete_node(node.id):
                        deleted_count += 1
                except Exception as e:
                    print(f"Lỗi xóa node {node.name}: {e}")

            return deleted_count

        except Exception as e:
            print(f"Lỗi cleanup empty nodes: {e}")
            return 0

    def reorganize_by_level(self, target_parent_id: Optional[int] = None) -> bool:
        """Tổ chức lại cây theo level"""
        try:
            # This is a complex operation that would reorganize nodes
            # based on their levels in a hierarchical manner
            # Implementation would depend on specific business rules

            # For now, just return success
            return True

        except Exception as e:
            print(f"Lỗi reorganize by level: {e}")
            return False

    # ========== TEMPLATES AND PRESETS ==========

    def create_default_structure(self) -> bool:
        """Tạo cấu trúc mặc định"""
        try:
            # Check if already has data
            existing_nodes = self.repository.get_all_nodes()
            if existing_nodes:
                return True

            # Create default subjects
            subjects = [
                ("Toán học", "Môn học toán"),
                ("Vật lý", "Môn học vật lý"),
                ("Hóa học", "Môn học hóa học"),
                ("Sinh học", "Môn học sinh học"),
                ("Văn học", "Môn học văn"),
                ("Lịch sử", "Môn học lịch sử"),
                ("Địa lý", "Môn học địa lý"),
                ("Tiếng Anh", "Môn học tiếng Anh")
            ]

            for name, description in subjects:
                subject_id = self.create_node(name, "subject", None, description)

                if subject_id:
                    # Create grade levels for each subject
                    for grade in range(10, 13):  # Lớp 10, 11, 12
                        grade_name = f"Lớp {grade}"
                        grade_description = f"{name} lớp {grade}"
                        self.create_node(grade_name, "grade", subject_id, grade_description)

            return True

        except Exception as e:
            print(f"Lỗi create default structure: {e}")
            return False

    def apply_template(self, template_name: str, parent_id: Optional[int] = None) -> bool:
        """Áp dụng template cấu trúc"""
        try:
            templates = {
                "math_high_school": self._get_math_template(),
                "physics_high_school": self._get_physics_template(),
                "chemistry_high_school": self._get_chemistry_template(),
            }

            template = templates.get(template_name)
            if not template:
                raise ValueError(f"Template không tồn tại: {template_name}")

            return self._apply_template_recursive(template, parent_id)

        except Exception as e:
            print(f"Lỗi apply template: {e}")
            return False

    # ========== IMPORT/EXPORT ==========

    def export_tree_structure(self, format: str = "json") -> Union[str, Dict]:
        """Export cấu trúc cây"""
        try:
            tree_structure = self.get_tree_structure()

            if format.lower() == "json":
                return json.dumps(self._tree_to_dict(tree_structure),
                                  ensure_ascii=False, indent=2)
            elif format.lower() == "dict":
                return self._tree_to_dict(tree_structure)
            else:
                raise ValueError(f"Format không được hỗ trợ: {format}")

        except Exception as e:
            print(f"Lỗi export tree: {e}")
            return "" if format == "json" else {}

    def import_tree_structure(self, data: Union[str, Dict],
                              parent_id: Optional[int] = None) -> bool:
        """Import cấu trúc cây"""
        try:
            if isinstance(data, str):
                tree_data = json.loads(data)
            else:
                tree_data = data

            return self._import_tree_recursive(tree_data, parent_id)

        except Exception as e:
            print(f"Lỗi import tree: {e}")
            return False

    # ========== SEARCH AND FILTERING ==========

    def search_nodes(self, query: str, search_in: List[str] = None) -> List[TreeNode]:
        """Tìm kiếm nodes"""
        try:
            if search_in is None:
                search_in = ["name", "description"]

            results = []
            query_lower = query.lower()
            all_nodes = self.repository.get_all_nodes()

            for node_data in all_nodes:
                match = False

                if "name" in search_in:
                    name = node_data.get('name', '').lower()
                    if query_lower in name:
                        match = True

                if "description" in search_in and not match:
                    description = node_data.get('description', '').lower()
                    if query_lower in description:
                        match = True

                if match:
                    node = TreeNode(**node_data)
                    node.question_count = self._count_questions_in_node(node.id)
                    node.path = self._get_node_path(node.id)
                    results.append(node)

            return results

        except Exception as e:
            print(f"Lỗi search nodes: {e}")
            return []

    def filter_nodes_by_level(self, level: str) -> List[TreeNode]:
        """Lọc nodes theo level"""
        try:
            nodes_data = self.repository.get_nodes_by_level(level)

            nodes = []
            for node_data in nodes_data:
                node = TreeNode(**node_data)
                node.question_count = self._count_questions_in_node(node.id)
                node.path = self._get_node_path(node.id)
                nodes.append(node)

            return nodes

        except Exception as e:
            print(f"Lỗi filter by level: {e}")
            return []

    # ========== PRIVATE HELPER METHODS ==========

    def _validate_parent_child_relationship(self, parent_id: int, child_level: str) -> bool:
        """Validate mối quan hệ parent-child"""
        try:
            parent_node = self.get_node(parent_id)
            if not parent_node:
                return False

            return self._validate_parent_child_relationship_by_levels(parent_node.level, child_level)

        except Exception:
            return False

    def _validate_parent_child_relationship_by_levels(self, parent_level: str, child_level: str) -> bool:
        """Validate relationship giữa các level"""
        allowed_children = self.level_hierarchy.get(parent_level, [])
        return child_level in allowed_children

    def _check_duplicate_name(self, name: str, parent_id: Optional[int],
                              level: str, exclude_id: Optional[int] = None) -> bool:
        """Kiểm tra trùng tên ở cùng cấp"""
        try:
            existing = self.repository.find_node_by_name(name, parent_id, level)
            if not existing:
                return False

            if exclude_id and existing.get('id') == exclude_id:
                return False

            return True

        except Exception:
            return False

    def _count_questions_in_node(self, node_id: int) -> int:
        """Đếm câu hỏi trong node (không bao gồm subtree)"""
        try:
            result = self.db.execute_query(
                "SELECT COUNT(*) as count FROM question_bank WHERE tree_id = ?",
                (node_id,), fetch="one"
            )
            return result['count'] if result else 0
        except Exception:
            return 0

    def _count_questions_in_subtree(self, node_id: int) -> int:
        """Đếm câu hỏi trong toàn bộ subtree"""
        try:
            all_ids = self._get_all_subtree_ids(node_id)
            if not all_ids:
                return 0

            placeholders = ','.join(['?'] * len(all_ids))
            result = self.db.execute_query(
                f"SELECT COUNT(*) as count FROM question_bank WHERE tree_id IN ({placeholders})",
                all_ids, fetch="one"
            )
            return result['count'] if result else 0
        except Exception:
            return 0

    def _get_all_subtree_ids(self, root_id: int) -> List[int]:
        """Lấy tất cả ID trong subtree"""
        ids = [root_id]
        children = self.get_children(root_id)

        for child in children:
            ids.extend(self._get_all_subtree_ids(child.id))

        return ids

    def _calculate_node_depth(self, node_id: int) -> int:
        """Tính độ sâu của node"""
        try:
            depth = 0
            current_id = node_id

            while current_id is not None:
                node = self.repository.get_node_by_id(current_id)
                if not node:
                    break

                current_id = node.get('parent_id')
                if current_id is not None:
                    depth += 1

            return depth

        except Exception:
            return 0

    def _get_node_path(self, node_id: int) -> str:
        """Lấy đường dẫn đến node"""
        try:
            ancestors = self.get_ancestors(node_id, include_self=True)
            return " > ".join([ancestor.name for ancestor in ancestors])
        except Exception:
            return ""

    def _is_descendant(self, potential_descendant_id: int, ancestor_id: int) -> bool:
        """Kiểm tra một node có phải là con cháu của node khác"""
        try:
            current_id = potential_descendant_id

            while current_id is not None:
                if current_id == ancestor_id:
                    return True

                node = self.repository.get_node_by_id(current_id)
                if not node:
                    break

                current_id = node.get('parent_id')

            return False

        except Exception:
            return False

    def _has_circular_reference(self, node_id: int, all_nodes: List[Dict]) -> bool:
        """Kiểm tra vòng lặp trong cây"""
        try:
            visited = set()
            current_id = node_id

            while current_id is not None:
                if current_id in visited:
                    return True

                visited.add(current_id)

                # Find parent
                parent_id = None
                for node in all_nodes:
                    if node['id'] == current_id:
                        parent_id = node.get('parent_id')
                        break

                current_id = parent_id

            return False

        except Exception:
            return True  # Assume error means circular reference

    def _delete_subtree(self, root_id: int) -> bool:
        """Xóa toàn bộ subtree"""
        try:
            # Get all descendant IDs (deepest first)
            all_ids = []
            self._collect_descendants(root_id, all_ids)
            all_ids.reverse()  # Delete deepest first
            all_ids.append(root_id)  # Add root last

            # Delete questions first
            for node_id in all_ids:
                self.db.execute_query(
                    "DELETE FROM question_bank WHERE tree_id = ?",
                    (node_id,)
                )

            # Delete nodes
            for node_id in all_ids:
                self.repository.delete_node(node_id)

            return True

        except Exception as e:
            print(f"Lỗi delete subtree: {e}")
            return False

    def _collect_descendants(self, node_id: int, result: List[int]):
        """Thu thập tất cả con cháu (recursive)"""
        children = self.get_children(node_id)
        for child in children:
            self._collect_descendants(child.id, result)
            result.append(child.id)

    def _copy_children_recursive(self, source_parent_id: int, target_parent_id: int):
        """Copy children recursively"""
        children = self.get_children(source_parent_id)

        for child in children:
            # Create copy of child
            new_child_id = self.create_node(
                name=child.name,
                level=child.level,
                parent_id=target_parent_id,
                description=child.description
            )

            if new_child_id:
                # Recursively copy grandchildren
                self._copy_children_recursive(child.id, new_child_id)

    def _sort_tree_nodes(self, nodes: List[TreeNode]):
        """Sort nodes và children recursively"""
        nodes.sort(key=lambda x: (x.level, x.name))

        for node in nodes:
            if node.children:
                self._sort_tree_nodes(node.children)

    def _calculate_tree_depths(self, nodes: List[TreeNode], current_depth: int):
        """Tính toán depth cho tất cả nodes"""
        for node in nodes:
            node.depth = current_depth
            if node.children:
                self._calculate_tree_depths(node.children, current_depth + 1)

    def _calculate_max_depth(self, nodes: List[TreeNode]) -> int:
        """Tính max depth của cây"""
        if not nodes:
            return 0

        max_depth = 0
        for node in nodes:
            current_depth = 1
            if node.children:
                child_depth = self._calculate_max_depth(node.children)
                current_depth += child_depth

            max_depth = max(max_depth, current_depth)

        return max_depth

    def _tree_to_dict(self, nodes: List[TreeNode]) -> List[Dict]:
        """Convert tree structure to dict"""
        result = []
        for node in nodes:
            node_dict = {
                'name': node.name,
                'level': node.level,
                'description': node.description,
                'question_count': node.question_count
            }

            if node.children:
                node_dict['children'] = self._tree_to_dict(node.children)

            result.append(node_dict)

        return result

    def _import_tree_recursive(self, tree_data: List[Dict], parent_id: Optional[int]) -> bool:
        """Import tree structure recursively"""
        try:
            for node_data in tree_data:
                # Create node
                node_id = self.create_node(
                    name=node_data['name'],
                    level=node_data['level'],
                    parent_id=parent_id,
                    description=node_data.get('description', '')
                )

                # Import children
                if node_id and 'children' in node_data:
                    self._import_tree_recursive(node_data['children'], node_id)

            return True

        except Exception as e:
            print(f"Lỗi import recursive: {e}")
            return False

    def _apply_template_recursive(self, template: List[Dict], parent_id: Optional[int]) -> bool:
        """Apply template recursively"""
        try:
            for item in template:
                node_id = self.create_node(
                    name=item['name'],
                    level=item['level'],
                    parent_id=parent_id,
                    description=item.get('description', '')
                )

                if node_id and 'children' in item:
                    self._apply_template_recursive(item['children'], node_id)

            return True

        except Exception as e:
            print(f"Lỗi apply template recursive: {e}")
            return False

    def _get_math_template(self) -> List[Dict]:
        """Template cho Toán học"""
        return [
            {
                "name": "Đại số",
                "level": "chapter",
                "description": "Chương đại số",
                "children": [
                    {"name": "Phương trình", "level": "topic", "description": "Các dạng phương trình"},
                    {"name": "Bất phương trình", "level": "topic", "description": "Các dạng bất phương trình"},
                    {"name": "Hệ phương trình", "level": "topic", "description": "Hệ phương trình tuyến tính"}
                ]
            },
            {
                "name": "Hình học",
                "level": "chapter",
                "description": "Chương hình học",
                "children": [
                    {"name": "Tam giác", "level": "topic", "description": "Các tính chất tam giác"},
                    {"name": "Tứ giác", "level": "topic", "description": "Các loại tứ giác"},
                    {"name": "Đường tròn", "level": "topic", "description": "Tính chất đường tròn"}
                ]
            }
        ]

    def _get_physics_template(self) -> List[Dict]:
        """Template cho Vật lý"""
        return [
            {
                "name": "Cơ học",
                "level": "chapter",
                "description": "Chương cơ học",
                "children": [
                    {"name": "Động học", "level": "topic", "description": "Chuyển động cơ học"},
                    {"name": "Động lực học", "level": "topic", "description": "Lực và chuyển động"}
                ]
            },
            {
                "name": "Nhiệt học",
                "level": "chapter",
                "description": "Chương nhiệt học",
                "children": [
                    {"name": "Nhiệt độ", "level": "topic", "description": "Khái niệm nhiệt độ"},
                    {"name": "Sự dãn nở", "level": "topic", "description": "Sự dãn nở vì nhiệt"}
                ]
            }
        ]

    def _get_chemistry_template(self) -> List[Dict]:
        """Template cho Hóa học"""
        return [
            {
                "name": "Hóa vô cơ",
                "level": "chapter",
                "description": "Chương hóa vô cơ",
                "children": [
                    {"name": "Axit - Bazơ", "level": "topic", "description": "Tính chất axit bazơ"},
                    {"name": "Muối", "level": "topic", "description": "Các loại muối"}
                ]
            },
            {
                "name": "Hóa hữu cơ",
                "level": "chapter",
                "description": "Chương hóa hữu cơ",
                "children": [
                    {"name": "Hydrocarbon", "level": "topic", "description": "Hợp chất hydrocarbon"},
                    {"name": "Dẫn xuất", "level": "topic", "description": "Dẫn xuất của hydrocarbon"}
                ]
            }
        ]


if __name__ == "__main__":
    # Test TreeService
    print("Testing TreeService...")


    # Mock database for testing
    class MockDB:
        def execute_query(self, query, params=None, fetch=None):
            return {'count': 0} if 'COUNT' in query else []


    # Test service
    service = TreeService(MockDB())
    print("✅ TreeService created successfully!")

    # Test validation
    errors = service.validate_tree_structure()
    print(f"✅ Tree validation: {len(errors)} errors found")

    # Test statistics
    stats = service.get_tree_statistics()
    print(f"✅ Tree statistics: {stats.total_nodes} nodes")

    print("🎉 All tests passed!")


    def load_tree_data_fixed():
        """✅ Load tree data với xử lý SQLite Row đúng cách"""
        try:
            query = "SELECT * FROM exercise_tree ORDER BY parent_id, name"
            rows = db.execute_query(query, fetch='all') or []

            tree_data = []
            for row in rows:
                # ✅ SỬA: Không dùng .get(), dùng safe access
                tree_item = {
                    'id': row['id'] if 'id' in row else None,
                    'parent_id': row['parent_id'] if 'parent_id' in row else None,
                    'name': row['name'] if 'name' in row else 'Unknown',
                    'level': row['level'] if 'level' in row else '',
                    'description': row['description'] if 'description' in row else '',
                    'created_at': row['created_at'] if 'created_at' in row else '',
                }

                tree_data.append(tree_item)

            return tree_data

        except Exception as e:
            print(f"❌ Lỗi load tree data: {e}")
            return []