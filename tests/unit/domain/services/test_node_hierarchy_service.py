"""NodeHierarchyService 测试 - Phase 9.2

TDD RED阶段：测试父子节点管理服务

业务场景：
- 用户说"帮我创建一个数据分析流程"
- ConversationAgent 规划出多个步骤
- NodeHierarchyService 管理这些节点的层级关系
- 支持批量操作、移动节点、查询层级等
"""

import pytest


class TestNodeHierarchyServiceCreation:
    """NodeHierarchyService 创建测试"""

    def test_create_service(self):
        """应能创建服务实例"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService

        service = NodeHierarchyService()

        assert service is not None

    def test_create_service_with_node_registry(self):
        """应能使用 NodeRegistry 创建服务"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import NodeRegistry

        registry = NodeRegistry()
        service = NodeHierarchyService(node_registry=registry)

        assert service.node_registry is registry


class TestCreateHierarchy:
    """创建层级结构测试"""

    def test_create_parent_with_children(self):
        """应能创建父节点并添加子节点"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import NodeType

        service = NodeHierarchyService()

        # 创建父节点
        parent = service.create_parent_node(
            name="数据分析流程",
            children_configs=[
                {"type": NodeType.CODE, "config": {"code": "import pandas as pd"}},
                {"type": NodeType.CODE, "config": {"code": "df.describe()"}},
            ],
        )

        assert parent.type == NodeType.GENERIC
        assert len(parent.children) == 2
        assert parent.children[0].type == NodeType.CODE
        assert parent.children[1].type == NodeType.CODE

    def test_create_parent_with_name(self):
        """父节点应有正确的名称配置"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService

        service = NodeHierarchyService()

        parent = service.create_parent_node(name="我的流程", children_configs=[])

        assert parent.config.get("name") == "我的流程"

    def test_create_nested_hierarchy(self):
        """应能创建嵌套层级"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import NodeType

        service = NodeHierarchyService()

        # 创建嵌套结构
        parent = service.create_parent_node(
            name="主流程",
            children_configs=[
                {
                    "type": NodeType.GENERIC,
                    "config": {"name": "子流程"},
                    "children": [
                        {"type": NodeType.CODE, "config": {"code": "x=1"}},
                    ],
                },
            ],
        )

        assert len(parent.children) == 1
        assert parent.children[0].type == NodeType.GENERIC
        assert len(parent.children[0].children) == 1


class TestAddChildToExisting:
    """向已有节点添加子节点测试"""

    def test_add_child_by_id(self):
        """应能通过父节点ID添加子节点"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import Node, NodeType

        service = NodeHierarchyService()

        # 先创建父节点并注册
        parent = Node(id="parent_1", type=NodeType.GENERIC, config={"name": "流程"})
        service.register_node(parent)

        # 添加子节点
        child = service.add_child_to_parent(
            parent_id="parent_1",
            child_type=NodeType.CODE,
            child_config={"code": "x=1"},
        )

        assert child.parent_id == "parent_1"
        assert len(parent.children) == 1

    def test_add_child_to_nonexistent_parent_raises(self):
        """向不存在的父节点添加子节点应抛出异常"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import NodeType

        service = NodeHierarchyService()

        with pytest.raises(ValueError, match="[Pp]arent.*not found|父节点.*不存在"):
            service.add_child_to_parent(
                parent_id="nonexistent",
                child_type=NodeType.CODE,
                child_config={"code": "x=1"},
            )


class TestMoveNode:
    """移动节点测试"""

    def test_move_node_to_new_parent(self):
        """应能将节点移动到新父节点"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import Node, NodeType

        service = NodeHierarchyService()

        # 创建两个父节点
        parent1 = Node(id="parent_1", type=NodeType.GENERIC, config={"name": "流程1"})
        parent2 = Node(id="parent_2", type=NodeType.GENERIC, config={"name": "流程2"})
        child = Node(id="child_1", type=NodeType.CODE, config={"code": "x=1"})

        parent1.add_child(child)
        service.register_node(parent1)
        service.register_node(parent2)
        service.register_node(child)

        # 移动节点
        service.move_node(node_id="child_1", new_parent_id="parent_2")

        assert len(parent1.children) == 0
        assert len(parent2.children) == 1
        assert child.parent_id == "parent_2"

    def test_move_node_to_root(self):
        """应能将节点移动到根级别（无父节点）"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import Node, NodeType

        service = NodeHierarchyService()

        parent = Node(id="parent_1", type=NodeType.GENERIC, config={"name": "流程"})
        child = Node(id="child_1", type=NodeType.CODE, config={"code": "x=1"})

        parent.add_child(child)
        service.register_node(parent)
        service.register_node(child)

        # 移动到根级别
        service.move_node(node_id="child_1", new_parent_id=None)

        assert len(parent.children) == 0
        assert child.parent_id is None


class TestRemoveNode:
    """删除节点测试"""

    def test_remove_leaf_node(self):
        """删除叶子节点应成功"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import Node, NodeType

        service = NodeHierarchyService()

        parent = Node(id="parent_1", type=NodeType.GENERIC, config={"name": "流程"})
        child = Node(id="child_1", type=NodeType.CODE, config={"code": "x=1"})

        parent.add_child(child)
        service.register_node(parent)
        service.register_node(child)

        service.remove_node("child_1")

        assert len(parent.children) == 0
        assert service.get_node("child_1") is None

    def test_remove_parent_node_removes_children(self):
        """删除父节点应同时删除所有子节点"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import Node, NodeType

        service = NodeHierarchyService()

        parent = Node(id="parent_1", type=NodeType.GENERIC, config={"name": "流程"})
        child1 = Node(id="child_1", type=NodeType.CODE, config={"code": "x=1"})
        child2 = Node(id="child_2", type=NodeType.CODE, config={"code": "y=2"})

        parent.add_child(child1)
        parent.add_child(child2)
        service.register_node(parent)
        service.register_node(child1)
        service.register_node(child2)

        service.remove_node("parent_1")

        assert service.get_node("parent_1") is None
        assert service.get_node("child_1") is None
        assert service.get_node("child_2") is None


class TestCollapseExpandOperations:
    """折叠/展开操作测试"""

    def test_collapse_node_by_id(self):
        """应能通过ID折叠节点"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import Node, NodeType

        service = NodeHierarchyService()

        node = Node(id="node_1", type=NodeType.GENERIC, config={})
        node.expand()  # 先展开
        service.register_node(node)

        service.collapse_node("node_1")

        assert node.collapsed is True

    def test_expand_node_by_id(self):
        """应能通过ID展开节点"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import Node, NodeType

        service = NodeHierarchyService()

        node = Node(id="node_1", type=NodeType.GENERIC, config={})
        service.register_node(node)

        service.expand_node("node_1")

        assert node.collapsed is False

    def test_toggle_collapse(self):
        """应能切换折叠状态"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import Node, NodeType

        service = NodeHierarchyService()

        node = Node(id="node_1", type=NodeType.GENERIC, config={})
        service.register_node(node)

        assert node.collapsed is True
        service.toggle_collapse("node_1")
        assert node.collapsed is False
        service.toggle_collapse("node_1")
        assert node.collapsed is True

    def test_expand_all_descendants(self):
        """应能展开所有后代节点"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import Node, NodeType

        service = NodeHierarchyService()

        root = Node(id="root", type=NodeType.GENERIC, config={})
        child = Node(id="child", type=NodeType.GENERIC, config={})
        grandchild = Node(id="grandchild", type=NodeType.GENERIC, config={})

        root.add_child(child)
        child.add_child(grandchild)
        service.register_node(root)
        service.register_node(child)
        service.register_node(grandchild)

        # 默认都是折叠的
        assert root.collapsed is True
        assert child.collapsed is True
        assert grandchild.collapsed is True

        service.expand_all("root")

        assert root.collapsed is False
        assert child.collapsed is False
        assert grandchild.collapsed is False

    def test_collapse_all_descendants(self):
        """应能折叠所有后代节点"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import Node, NodeType

        service = NodeHierarchyService()

        root = Node(id="root", type=NodeType.GENERIC, config={})
        child = Node(id="child", type=NodeType.GENERIC, config={})

        root.add_child(child)
        service.register_node(root)
        service.register_node(child)

        # 先展开所有
        root.expand()
        child.expand()

        service.collapse_all("root")

        assert root.collapsed is True
        assert child.collapsed is True


class TestQueryHierarchy:
    """查询层级结构测试"""

    def test_get_children(self):
        """应能获取直接子节点"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import Node, NodeType

        service = NodeHierarchyService()

        parent = Node(id="parent", type=NodeType.GENERIC, config={})
        child1 = Node(id="child1", type=NodeType.CODE, config={"code": "x"})
        child2 = Node(id="child2", type=NodeType.CODE, config={"code": "y"})

        parent.add_child(child1)
        parent.add_child(child2)
        service.register_node(parent)

        children = service.get_children("parent")

        assert len(children) == 2

    def test_get_visible_children(self):
        """应能获取可见子节点（考虑折叠状态）"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import Node, NodeType

        service = NodeHierarchyService()

        parent = Node(id="parent", type=NodeType.GENERIC, config={})
        child = Node(id="child", type=NodeType.CODE, config={"code": "x"})

        parent.add_child(child)
        service.register_node(parent)

        # 折叠时
        visible = service.get_visible_children("parent")
        assert len(visible) == 0

        # 展开后
        parent.expand()
        visible = service.get_visible_children("parent")
        assert len(visible) == 1

    def test_get_root_nodes(self):
        """应能获取所有根节点"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import Node, NodeType

        service = NodeHierarchyService()

        root1 = Node(id="root1", type=NodeType.GENERIC, config={})
        root2 = Node(id="root2", type=NodeType.CODE, config={"code": "x"})
        child = Node(id="child", type=NodeType.CODE, config={"code": "y"})

        root1.add_child(child)
        service.register_node(root1)
        service.register_node(root2)
        service.register_node(child)

        roots = service.get_root_nodes()

        assert len(roots) == 2
        root_ids = {r.id for r in roots}
        assert root_ids == {"root1", "root2"}

    def test_get_hierarchy_tree(self):
        """应能获取完整的层级树"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import Node, NodeType

        service = NodeHierarchyService()

        root = Node(id="root", type=NodeType.GENERIC, config={"name": "根"})
        child1 = Node(id="child1", type=NodeType.CODE, config={"code": "x"})
        child2 = Node(id="child2", type=NodeType.GENERIC, config={"name": "子"})
        grandchild = Node(id="grandchild", type=NodeType.CODE, config={"code": "y"})

        root.add_child(child1)
        root.add_child(child2)
        child2.add_child(grandchild)
        service.register_node(root)
        service.register_node(child1)
        service.register_node(child2)
        service.register_node(grandchild)

        tree = service.get_hierarchy_tree("root")

        assert tree["id"] == "root"
        assert len(tree["children"]) == 2
        # 找到 child2（有子节点的那个）
        child2_tree = next(c for c in tree["children"] if c["id"] == "child2")
        assert len(child2_tree["children"]) == 1


class TestBatchOperations:
    """批量操作测试"""

    def test_batch_add_children(self):
        """应能批量添加子节点"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import Node, NodeType

        service = NodeHierarchyService()

        parent = Node(id="parent", type=NodeType.GENERIC, config={})
        service.register_node(parent)

        children_configs = [
            {"type": NodeType.CODE, "config": {"code": "x=1"}},
            {"type": NodeType.CODE, "config": {"code": "y=2"}},
            {"type": NodeType.CODE, "config": {"code": "z=3"}},
        ]

        children = service.batch_add_children("parent", children_configs)

        assert len(children) == 3
        assert len(parent.children) == 3

    def test_batch_remove_children(self):
        """应能批量删除子节点"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import Node, NodeType

        service = NodeHierarchyService()

        parent = Node(id="parent", type=NodeType.GENERIC, config={})
        child1 = Node(id="child1", type=NodeType.CODE, config={"code": "x"})
        child2 = Node(id="child2", type=NodeType.CODE, config={"code": "y"})
        child3 = Node(id="child3", type=NodeType.CODE, config={"code": "z"})

        parent.add_child(child1)
        parent.add_child(child2)
        parent.add_child(child3)
        service.register_node(parent)
        service.register_node(child1)
        service.register_node(child2)
        service.register_node(child3)

        service.batch_remove_children("parent", ["child1", "child3"])

        assert len(parent.children) == 1
        assert parent.children[0].id == "child2"


class TestReorderChildren:
    """子节点重排序测试"""

    def test_reorder_children(self):
        """应能重排序子节点"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import Node, NodeType

        service = NodeHierarchyService()

        parent = Node(id="parent", type=NodeType.GENERIC, config={})
        child1 = Node(id="child1", type=NodeType.CODE, config={"code": "x"})
        child2 = Node(id="child2", type=NodeType.CODE, config={"code": "y"})
        child3 = Node(id="child3", type=NodeType.CODE, config={"code": "z"})

        parent.add_child(child1)
        parent.add_child(child2)
        parent.add_child(child3)
        service.register_node(parent)

        # 重排序
        service.reorder_children("parent", ["child3", "child1", "child2"])

        assert parent.children[0].id == "child3"
        assert parent.children[1].id == "child1"
        assert parent.children[2].id == "child2"

    def test_move_child_to_index(self):
        """应能将子节点移动到指定位置"""
        from src.domain.services.node_hierarchy_service import NodeHierarchyService
        from src.domain.services.node_registry import Node, NodeType

        service = NodeHierarchyService()

        parent = Node(id="parent", type=NodeType.GENERIC, config={})
        child1 = Node(id="child1", type=NodeType.CODE, config={"code": "x"})
        child2 = Node(id="child2", type=NodeType.CODE, config={"code": "y"})
        child3 = Node(id="child3", type=NodeType.CODE, config={"code": "z"})

        parent.add_child(child1)
        parent.add_child(child2)
        parent.add_child(child3)
        service.register_node(parent)

        # 将 child3 移动到第一位
        service.move_child_to_index("parent", "child3", 0)

        assert parent.children[0].id == "child3"
        assert parent.children[1].id == "child1"
        assert parent.children[2].id == "child2"


class TestHierarchyEvents:
    """层级事件测试"""

    @pytest.mark.asyncio
    async def test_emit_child_added_event(self):
        """添加子节点时应发布事件"""
        from src.domain.services.event_bus import EventBus
        from src.domain.services.node_hierarchy_service import (
            ChildAddedEvent,
            NodeHierarchyService,
        )
        from src.domain.services.node_registry import Node, NodeType

        event_bus = EventBus()
        received_events = []

        async def handler(event):
            received_events.append(event)

        event_bus.subscribe(ChildAddedEvent, handler)

        service = NodeHierarchyService(event_bus=event_bus)

        parent = Node(id="parent", type=NodeType.GENERIC, config={})
        service.register_node(parent)

        await service.add_child_to_parent_async(
            parent_id="parent",
            child_type=NodeType.CODE,
            child_config={"code": "x=1"},
        )

        assert len(received_events) == 1
        assert received_events[0].parent_id == "parent"

    @pytest.mark.asyncio
    async def test_emit_node_collapsed_event(self):
        """折叠节点时应发布事件"""
        from src.domain.services.event_bus import EventBus
        from src.domain.services.node_hierarchy_service import (
            NodeCollapsedEvent,
            NodeHierarchyService,
        )
        from src.domain.services.node_registry import Node, NodeType

        event_bus = EventBus()
        received_events = []

        async def handler(event):
            received_events.append(event)

        event_bus.subscribe(NodeCollapsedEvent, handler)

        service = NodeHierarchyService(event_bus=event_bus)

        node = Node(id="node", type=NodeType.GENERIC, config={})
        node.expand()
        service.register_node(node)

        await service.collapse_node_async("node")

        assert len(received_events) == 1
        assert received_events[0].node_id == "node"

    @pytest.mark.asyncio
    async def test_emit_node_expanded_event(self):
        """展开节点时应发布事件"""
        from src.domain.services.event_bus import EventBus
        from src.domain.services.node_hierarchy_service import (
            NodeExpandedEvent,
            NodeHierarchyService,
        )
        from src.domain.services.node_registry import Node, NodeType

        event_bus = EventBus()
        received_events = []

        async def handler(event):
            received_events.append(event)

        event_bus.subscribe(NodeExpandedEvent, handler)

        service = NodeHierarchyService(event_bus=event_bus)

        node = Node(id="node", type=NodeType.GENERIC, config={})
        service.register_node(node)

        await service.expand_node_async("node")

        assert len(received_events) == 1
        assert received_events[0].node_id == "node"
