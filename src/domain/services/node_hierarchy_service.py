"""NodeHierarchyService - 父子节点管理服务 - Phase 9.2

业务定义：
- 管理节点的层级关系
- 提供创建、移动、删除、折叠/展开操作
- 发布层级变更事件

设计原则：
- 服务层封装：封装 Node 的层级操作
- 事件驱动：层级变更时发布事件
- 内存管理：维护节点注册表

使用示例：
    service = NodeHierarchyService(event_bus=event_bus)
    parent = service.create_parent_node(name="流程", children_configs=[...])
    service.expand_node(parent.id)
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from src.domain.services.event_bus import Event, EventBus
from src.domain.services.node_registry import Node, NodeRegistry, NodeType

logger = logging.getLogger(__name__)


# ============ 事件定义 ============


@dataclass
class ChildAddedEvent(Event):
    """子节点添加事件"""

    parent_id: str = ""
    child_id: str = ""
    child_type: str = ""


@dataclass
class ChildRemovedEvent(Event):
    """子节点移除事件"""

    parent_id: str = ""
    child_id: str = ""


@dataclass
class NodeMovedEvent(Event):
    """节点移动事件"""

    node_id: str = ""
    old_parent_id: str | None = None
    new_parent_id: str | None = None


@dataclass
class NodeCollapsedEvent(Event):
    """节点折叠事件"""

    node_id: str = ""


@dataclass
class NodeExpandedEvent(Event):
    """节点展开事件"""

    node_id: str = ""


# ============ NodeHierarchyService ============


class NodeHierarchyService:
    """父子节点管理服务

    职责：
    1. 管理节点注册表
    2. 创建父节点和层级结构
    3. 添加/移除/移动节点
    4. 折叠/展开操作
    5. 查询层级结构
    6. 发布层级变更事件
    """

    def __init__(
        self,
        node_registry: NodeRegistry | None = None,
        event_bus: EventBus | None = None,
    ):
        """初始化服务

        参数：
            node_registry: 节点注册表（可选）
            event_bus: 事件总线（可选，用于发布事件）
        """
        self.node_registry = node_registry
        self.event_bus = event_bus
        self._nodes: dict[str, Node] = {}

    def register_node(self, node: Node) -> None:
        """注册节点到服务

        参数：
            node: 要注册的节点
        """
        self._nodes[node.id] = node

    def get_node(self, node_id: str) -> Node | None:
        """获取节点

        参数：
            node_id: 节点ID

        返回：
            节点实例，不存在返回 None
        """
        return self._nodes.get(node_id)

    def _generate_id(self) -> str:
        """生成节点ID"""
        return f"node_{uuid.uuid4().hex[:12]}"

    # ============ 创建层级结构 ============

    def create_parent_node(
        self,
        name: str,
        children_configs: list[dict[str, Any]],
        node_id: str | None = None,
    ) -> Node:
        """创建父节点并添加子节点

        参数：
            name: 父节点名称
            children_configs: 子节点配置列表
            node_id: 可选的节点ID

        返回：
            创建的父节点
        """
        parent = Node(
            id=node_id or self._generate_id(),
            type=NodeType.GENERIC,
            config={"name": name},
        )

        for child_config in children_configs:
            child = self._create_node_from_config(child_config)
            parent.add_child(child)
            self._nodes[child.id] = child

        self._nodes[parent.id] = parent
        return parent

    def _create_node_from_config(self, config: dict[str, Any]) -> Node:
        """从配置创建节点

        参数：
            config: 节点配置

        返回：
            创建的节点
        """
        node_type = config.get("type")
        if isinstance(node_type, str):
            node_type = NodeType(node_type)
        if not isinstance(node_type, NodeType):
            raise ValueError("Node config missing valid 'type'")

        node = Node(
            id=config.get("id") or self._generate_id(),
            type=node_type,
            config=config.get("config", {}),
        )

        # 递归处理子节点
        children_configs = config.get("children", [])
        for child_config in children_configs:
            child = self._create_node_from_config(child_config)
            node.add_child(child)
            self._nodes[child.id] = child

        return node

    # ============ 添加子节点 ============

    def add_child_to_parent(
        self,
        parent_id: str,
        child_type: NodeType,
        child_config: dict[str, Any],
        child_id: str | None = None,
    ) -> Node:
        """向父节点添加子节点

        参数：
            parent_id: 父节点ID
            child_type: 子节点类型
            child_config: 子节点配置
            child_id: 可选的子节点ID

        返回：
            创建的子节点

        异常：
            ValueError: 父节点不存在
        """
        parent = self._nodes.get(parent_id)
        if parent is None:
            raise ValueError(f"Parent node not found: {parent_id}")

        child = Node(
            id=child_id or self._generate_id(),
            type=child_type,
            config=child_config,
        )

        parent.add_child(child)
        self._nodes[child.id] = child

        return child

    async def add_child_to_parent_async(
        self,
        parent_id: str,
        child_type: NodeType,
        child_config: dict[str, Any],
        child_id: str | None = None,
    ) -> Node:
        """异步版本：向父节点添加子节点（发布事件）

        参数：
            parent_id: 父节点ID
            child_type: 子节点类型
            child_config: 子节点配置
            child_id: 可选的子节点ID

        返回：
            创建的子节点
        """
        child = self.add_child_to_parent(parent_id, child_type, child_config, child_id)

        if self.event_bus:
            event = ChildAddedEvent(
                source="node_hierarchy_service",
                parent_id=parent_id,
                child_id=child.id,
                child_type=child_type.value,
            )
            await self.event_bus.publish(event)

        return child

    # ============ 移动节点 ============

    def move_node(self, node_id: str, new_parent_id: str | None) -> None:
        """移动节点到新父节点

        参数：
            node_id: 要移动的节点ID
            new_parent_id: 新父节点ID，None 表示移动到根级别

        异常：
            ValueError: 节点不存在
        """
        node = self._nodes.get(node_id)
        if node is None:
            raise ValueError(f"Node not found: {node_id}")

        old_parent_id = node.parent_id

        # 从旧父节点移除
        if old_parent_id:
            old_parent = self._nodes.get(old_parent_id)
            if old_parent:
                old_parent.remove_child(node_id)

        # 添加到新父节点
        if new_parent_id:
            new_parent = self._nodes.get(new_parent_id)
            if new_parent is None:
                raise ValueError(f"New parent not found: {new_parent_id}")
            new_parent.add_child(node)
        else:
            # 移动到根级别
            node.parent_id = None
            node._parent = None

    # ============ 删除节点 ============

    def remove_node(self, node_id: str) -> None:
        """删除节点及其所有子节点

        参数：
            node_id: 要删除的节点ID
        """
        node = self._nodes.get(node_id)
        if node is None:
            return

        # 递归删除所有后代
        for child in list(node.children):
            self.remove_node(child.id)

        # 从父节点移除
        if node.parent_id:
            parent = self._nodes.get(node.parent_id)
            if parent:
                parent.remove_child(node_id)

        # 从注册表移除
        del self._nodes[node_id]

    # ============ 折叠/展开操作 ============

    def collapse_node(self, node_id: str) -> None:
        """折叠节点

        参数：
            node_id: 节点ID
        """
        node = self._nodes.get(node_id)
        if node:
            node.collapse()

    async def collapse_node_async(self, node_id: str) -> None:
        """异步版本：折叠节点（发布事件）

        参数：
            node_id: 节点ID
        """
        self.collapse_node(node_id)

        if self.event_bus:
            event = NodeCollapsedEvent(
                source="node_hierarchy_service",
                node_id=node_id,
            )
            await self.event_bus.publish(event)

    def expand_node(self, node_id: str) -> None:
        """展开节点

        参数：
            node_id: 节点ID
        """
        node = self._nodes.get(node_id)
        if node:
            node.expand()

    async def expand_node_async(self, node_id: str) -> None:
        """异步版本：展开节点（发布事件）

        参数：
            node_id: 节点ID
        """
        self.expand_node(node_id)

        if self.event_bus:
            event = NodeExpandedEvent(
                source="node_hierarchy_service",
                node_id=node_id,
            )
            await self.event_bus.publish(event)

    def toggle_collapse(self, node_id: str) -> None:
        """切换折叠状态

        参数：
            node_id: 节点ID
        """
        node = self._nodes.get(node_id)
        if node:
            if node.collapsed:
                node.expand()
            else:
                node.collapse()

    def expand_all(self, node_id: str) -> None:
        """展开节点及其所有后代

        参数：
            node_id: 节点ID
        """
        node = self._nodes.get(node_id)
        if node is None:
            return

        node.expand()
        for descendant in node.get_all_descendants():
            if descendant.type == NodeType.GENERIC:
                descendant.expand()

    def collapse_all(self, node_id: str) -> None:
        """折叠节点及其所有后代

        参数：
            node_id: 节点ID
        """
        node = self._nodes.get(node_id)
        if node is None:
            return

        node.collapse()
        for descendant in node.get_all_descendants():
            if descendant.type == NodeType.GENERIC:
                descendant.collapse()

    # ============ 查询层级结构 ============

    def get_children(self, node_id: str) -> list[Node]:
        """获取直接子节点

        参数：
            node_id: 节点ID

        返回：
            子节点列表
        """
        node = self._nodes.get(node_id)
        if node:
            return list(node.children)
        return []

    def get_visible_children(self, node_id: str) -> list[Node]:
        """获取可见子节点（考虑折叠状态）

        参数：
            node_id: 节点ID

        返回：
            可见子节点列表
        """
        node = self._nodes.get(node_id)
        if node:
            return node.get_visible_children()
        return []

    def get_root_nodes(self) -> list[Node]:
        """获取所有根节点

        返回：
            根节点列表
        """
        return [node for node in self._nodes.values() if node.parent_id is None]

    def get_hierarchy_tree(self, node_id: str) -> dict[str, Any]:
        """获取完整的层级树

        参数：
            node_id: 根节点ID

        返回：
            层级树字典
        """
        node = self._nodes.get(node_id)
        if node is None:
            return {}

        return self._node_to_tree(node)

    def _node_to_tree(self, node: Node) -> dict[str, Any]:
        """将节点转换为树结构

        参数：
            node: 节点

        返回：
            树结构字典
        """
        name = ""
        if isinstance(node.config, dict):
            name_value = node.config.get("name")
            if isinstance(name_value, str):
                name = name_value

        return {
            "id": node.id,
            "type": node.type.value,
            "name": name,
            "config": node.config,
            "collapsed": node.collapsed,
            "children": [self._node_to_tree(child) for child in node.children],
        }

    # ============ 批量操作 ============

    def batch_add_children(
        self,
        parent_id: str,
        children_configs: list[dict[str, Any]],
    ) -> list[Node]:
        """批量添加子节点

        参数：
            parent_id: 父节点ID
            children_configs: 子节点配置列表

        返回：
            创建的子节点列表
        """
        children = []
        for config in children_configs:
            child_type = config.get("type")
            if isinstance(child_type, str):
                child_type = NodeType(child_type)
            if not isinstance(child_type, NodeType):
                raise ValueError("Child config missing valid 'type'")

            child = self.add_child_to_parent(
                parent_id=parent_id,
                child_type=child_type,
                child_config=config.get("config", {}),
            )
            children.append(child)

        return children

    def batch_remove_children(
        self,
        parent_id: str,
        child_ids: list[str],
    ) -> None:
        """批量删除子节点

        参数：
            parent_id: 父节点ID
            child_ids: 要删除的子节点ID列表
        """
        parent = self._nodes.get(parent_id)
        if parent is None:
            return

        for child_id in child_ids:
            if child_id in self._nodes:
                parent.remove_child(child_id)
                del self._nodes[child_id]

    # ============ 重排序 ============

    def reorder_children(self, parent_id: str, child_ids: list[str]) -> None:
        """重排序子节点

        参数：
            parent_id: 父节点ID
            child_ids: 新的子节点ID顺序
        """
        parent = self._nodes.get(parent_id)
        if parent is None:
            return

        # 按新顺序重建 children 列表
        new_children = []
        for child_id in child_ids:
            for child in parent.children:
                if child.id == child_id:
                    new_children.append(child)
                    break

        parent.children = new_children

    def move_child_to_index(
        self,
        parent_id: str,
        child_id: str,
        index: int,
    ) -> None:
        """将子节点移动到指定位置

        参数：
            parent_id: 父节点ID
            child_id: 子节点ID
            index: 目标位置
        """
        parent = self._nodes.get(parent_id)
        if parent is None:
            return

        # 找到子节点
        child = None
        for c in parent.children:
            if c.id == child_id:
                child = c
                break

        if child is None:
            return

        # 移除再插入
        parent.children.remove(child)
        parent.children.insert(index, child)


# 导出
__all__ = [
    "NodeHierarchyService",
    "ChildAddedEvent",
    "ChildRemovedEvent",
    "NodeMovedEvent",
    "NodeCollapsedEvent",
    "NodeExpandedEvent",
]
