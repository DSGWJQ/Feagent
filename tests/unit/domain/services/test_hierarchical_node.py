"""层级节点测试 - Phase 9.1

TDD RED阶段：测试通用节点的父子关系和折叠/展开功能

业务场景：
- 用户说"帮我创建一个数据分析流程"
- ConversationAgent 规划出多个步骤
- 这些步骤作为子节点放入一个 GENERIC 父节点
- 用户可以折叠/展开查看细节
"""

import pytest


class TestHierarchicalNodeStructure:
    """层级节点结构测试"""

    def test_generic_node_can_have_children(self):
        """GENERIC 节点应能包含子节点"""
        from src.domain.services.node_registry import Node, NodeType

        parent = Node(id="parent_1", type=NodeType.GENERIC, config={"name": "数据分析"})
        child1 = Node(id="child_1", type=NodeType.CODE, config={"code": "x=1"})
        child2 = Node(id="child_2", type=NodeType.CODE, config={"code": "y=2"})

        parent.add_child(child1)
        parent.add_child(child2)

        assert len(parent.children) == 2
        assert parent.children[0].id == "child_1"
        assert parent.children[1].id == "child_2"

    def test_node_has_parent_reference(self):
        """子节点应有父节点引用"""
        from src.domain.services.node_registry import Node, NodeType

        parent = Node(id="parent_1", type=NodeType.GENERIC, config={"name": "流程"})
        child = Node(id="child_1", type=NodeType.CODE, config={"code": "x=1"})

        parent.add_child(child)

        assert child.parent_id == parent.id

    def test_remove_child_from_parent(self):
        """应能从父节点移除子节点"""
        from src.domain.services.node_registry import Node, NodeType

        parent = Node(id="parent_1", type=NodeType.GENERIC, config={"name": "流程"})
        child = Node(id="child_1", type=NodeType.CODE, config={"code": "x=1"})

        parent.add_child(child)
        assert len(parent.children) == 1

        parent.remove_child(child.id)
        assert len(parent.children) == 0
        assert child.parent_id is None

    def test_nested_hierarchy_three_levels(self):
        """应支持三层嵌套"""
        from src.domain.services.node_registry import Node, NodeType

        grandparent = Node(id="gp", type=NodeType.GENERIC, config={"name": "主流程"})
        parent = Node(id="p", type=NodeType.GENERIC, config={"name": "子流程"})
        child = Node(id="c", type=NodeType.CODE, config={"code": "x=1"})

        grandparent.add_child(parent)
        parent.add_child(child)

        assert len(grandparent.children) == 1
        assert len(grandparent.children[0].children) == 1
        assert grandparent.children[0].children[0].id == "c"


class TestNodeCollapseExpand:
    """节点折叠/展开测试"""

    def test_generic_node_default_collapsed(self):
        """GENERIC 节点默认折叠"""
        from src.domain.services.node_registry import Node, NodeType

        node = Node(id="node_1", type=NodeType.GENERIC, config={})

        assert node.collapsed is True

    def test_expand_node(self):
        """展开节点应设置 collapsed=False"""
        from src.domain.services.node_registry import Node, NodeType

        node = Node(id="node_1", type=NodeType.GENERIC, config={})
        node.expand()

        assert node.collapsed is False

    def test_collapse_node(self):
        """折叠节点应设置 collapsed=True"""
        from src.domain.services.node_registry import Node, NodeType

        node = Node(id="node_1", type=NodeType.GENERIC, config={})
        node.expand()
        node.collapse()

        assert node.collapsed is True

    def test_get_visible_children_when_collapsed(self):
        """折叠时 get_visible_children 应返回空列表"""
        from src.domain.services.node_registry import Node, NodeType

        parent = Node(id="parent", type=NodeType.GENERIC, config={})
        child = Node(id="child", type=NodeType.CODE, config={"code": "x=1"})
        parent.add_child(child)

        # 默认折叠
        assert parent.get_visible_children() == []

    def test_get_visible_children_when_expanded(self):
        """展开时 get_visible_children 应返回所有子节点"""
        from src.domain.services.node_registry import Node, NodeType

        parent = Node(id="parent", type=NodeType.GENERIC, config={})
        child = Node(id="child", type=NodeType.CODE, config={"code": "x=1"})
        parent.add_child(child)

        parent.expand()
        visible = parent.get_visible_children()

        assert len(visible) == 1
        assert visible[0].id == "child"


class TestNodeSerialization:
    """节点序列化测试（含层级）"""

    def test_node_to_dict_includes_children(self):
        """to_dict 应包含子节点"""
        from src.domain.services.node_registry import Node, NodeType

        parent = Node(id="parent", type=NodeType.GENERIC, config={"name": "流程"})
        child = Node(id="child", type=NodeType.CODE, config={"code": "x=1"})
        parent.add_child(child)

        data = parent.to_dict()

        assert "children" in data
        assert len(data["children"]) == 1
        assert data["children"][0]["id"] == "child"

    def test_node_to_dict_includes_collapsed(self):
        """to_dict 应包含 collapsed 状态"""
        from src.domain.services.node_registry import Node, NodeType

        node = Node(id="node", type=NodeType.GENERIC, config={})

        data = node.to_dict()

        assert "collapsed" in data
        assert data["collapsed"] is True

    def test_node_to_dict_includes_parent_id(self):
        """to_dict 应包含 parent_id"""
        from src.domain.services.node_registry import Node, NodeType

        parent = Node(id="parent", type=NodeType.GENERIC, config={})
        child = Node(id="child", type=NodeType.CODE, config={"code": "x=1"})
        parent.add_child(child)

        data = child.to_dict()

        assert "parent_id" in data
        assert data["parent_id"] == "parent"

    def test_node_from_dict_restores_hierarchy(self):
        """from_dict 应恢复层级结构"""
        from src.domain.services.node_registry import Node

        data = {
            "id": "parent",
            "type": "generic",
            "config": {"name": "流程"},
            "collapsed": False,
            "children": [
                {"id": "child", "type": "code", "config": {"code": "x=1"}, "parent_id": "parent"}
            ],
        }

        node = Node.from_dict(data)

        assert node.id == "parent"
        assert node.collapsed is False
        assert len(node.children) == 1
        assert node.children[0].id == "child"
        assert node.children[0].parent_id == "parent"


class TestNodeHierarchyValidation:
    """节点层级验证测试"""

    def test_non_generic_node_cannot_have_children(self):
        """非 GENERIC 节点不能有子节点"""
        from src.domain.services.node_registry import Node, NodeType

        parent = Node(id="parent", type=NodeType.CODE, config={"code": "x=1"})
        child = Node(id="child", type=NodeType.CODE, config={"code": "y=2"})

        with pytest.raises(ValueError, match="[Oo]nly.*GENERIC|只有.*通用"):
            parent.add_child(child)

    def test_cannot_add_node_to_itself(self):
        """不能将节点添加为自己的子节点"""
        from src.domain.services.node_registry import Node, NodeType

        node = Node(id="node", type=NodeType.GENERIC, config={})

        with pytest.raises(ValueError, match="[Cc]annot|不能"):
            node.add_child(node)

    def test_cannot_create_circular_hierarchy(self):
        """不能创建循环层级"""
        from src.domain.services.node_registry import Node, NodeType

        parent = Node(id="parent", type=NodeType.GENERIC, config={})
        child = Node(id="child", type=NodeType.GENERIC, config={})

        parent.add_child(child)

        # child 不能添加 parent 为子节点
        with pytest.raises(ValueError, match="[Cc]ircular|循环"):
            child.add_child(parent)


class TestNodeDepthLimit:
    """节点深度限制测试"""

    def test_max_depth_limit(self):
        """应限制最大嵌套深度"""
        from src.domain.services.node_registry import Node, NodeType

        # 创建 5 层嵌套（假设限制为 5）
        nodes = []
        for i in range(6):
            node = Node(id=f"node_{i}", type=NodeType.GENERIC, config={})
            nodes.append(node)
            if i > 0:
                nodes[i - 1].add_child(node)

        # 第 6 层应该失败
        too_deep = Node(id="too_deep", type=NodeType.GENERIC, config={})
        with pytest.raises(ValueError, match="[Dd]epth|深度"):
            nodes[5].add_child(too_deep)

    def test_get_depth_returns_current_depth(self):
        """get_depth 应返回当前深度"""
        from src.domain.services.node_registry import Node, NodeType

        root = Node(id="root", type=NodeType.GENERIC, config={})
        child = Node(id="child", type=NodeType.GENERIC, config={})
        grandchild = Node(id="grandchild", type=NodeType.CODE, config={"code": "x"})

        root.add_child(child)
        child.add_child(grandchild)

        assert root.get_depth() == 0
        assert child.get_depth() == 1
        assert grandchild.get_depth() == 2


class TestNodeHierarchyTraversal:
    """节点层级遍历测试"""

    def test_get_all_descendants(self):
        """get_all_descendants 应返回所有后代节点"""
        from src.domain.services.node_registry import Node, NodeType

        root = Node(id="root", type=NodeType.GENERIC, config={})
        child1 = Node(id="child1", type=NodeType.GENERIC, config={})
        child2 = Node(id="child2", type=NodeType.CODE, config={"code": "x"})
        grandchild = Node(id="grandchild", type=NodeType.CODE, config={"code": "y"})

        root.add_child(child1)
        root.add_child(child2)
        child1.add_child(grandchild)

        descendants = root.get_all_descendants()

        assert len(descendants) == 3
        ids = {d.id for d in descendants}
        assert ids == {"child1", "child2", "grandchild"}

    def test_get_root_node(self):
        """get_root 应返回根节点"""
        from src.domain.services.node_registry import Node, NodeType

        root = Node(id="root", type=NodeType.GENERIC, config={})
        child = Node(id="child", type=NodeType.GENERIC, config={})
        grandchild = Node(id="grandchild", type=NodeType.CODE, config={"code": "x"})

        root.add_child(child)
        child.add_child(grandchild)

        assert grandchild.get_root().id == "root"
        assert child.get_root().id == "root"
        assert root.get_root().id == "root"

    def test_get_ancestors(self):
        """get_ancestors 应返回所有祖先节点"""
        from src.domain.services.node_registry import Node, NodeType

        root = Node(id="root", type=NodeType.GENERIC, config={})
        child = Node(id="child", type=NodeType.GENERIC, config={})
        grandchild = Node(id="grandchild", type=NodeType.CODE, config={"code": "x"})

        root.add_child(child)
        child.add_child(grandchild)

        ancestors = grandchild.get_ancestors()

        assert len(ancestors) == 2
        assert ancestors[0].id == "child"  # 直接父节点
        assert ancestors[1].id == "root"  # 根节点
