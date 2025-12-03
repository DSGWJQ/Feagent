"""测试：NodeDefinition 层次化支持

测试目标：
1. NodeDefinition 支持父子关系
2. 支持折叠状态
3. 支持容器标识
4. 层级树结构操作
5. 序列化/反序列化包含层级信息

完成标准：
- NodeDefinition 可以有子节点
- 可以设置折叠状态
- 支持 to_dict/from_dict 含层级
"""

import pytest

from src.domain.agents.node_definition import (
    NodeDefinition,
    NodeType,
)

# ==================== 测试1：NodeDefinition 父子关系 ====================


class TestNodeDefinitionHierarchy:
    """测试 NodeDefinition 父子关系"""

    def test_node_definition_has_parent_id(self):
        """NodeDefinition 应有 parent_id 属性"""
        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="子节点",
            code="print('hello')",
        )

        assert hasattr(node, "parent_id")
        assert node.parent_id is None  # 默认无父节点

    def test_node_definition_has_children(self):
        """NodeDefinition 应有 children 属性"""
        node = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
        )

        assert hasattr(node, "children")
        assert isinstance(node.children, list)
        assert len(node.children) == 0

    def test_can_add_child_to_generic_node(self):
        """可以向 GENERIC 节点添加子节点"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
        )

        child = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="Python子节点",
            code="print('child')",
        )

        parent.add_child(child)

        assert len(parent.children) == 1
        assert parent.children[0].name == "Python子节点"
        assert child.parent_id == parent.id

    def test_cannot_add_child_to_non_generic_node(self):
        """非 GENERIC 节点不能添加子节点"""
        parent = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="Python节点",
            code="print('parent')",
        )

        child = NodeDefinition(
            node_type=NodeType.LLM,
            name="LLM子节点",
            prompt="test",
        )

        with pytest.raises(ValueError, match="Only GENERIC"):
            parent.add_child(child)

    def test_can_remove_child(self):
        """可以移除子节点"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
        )

        child = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="子节点",
            code="print('hello')",
        )

        parent.add_child(child)
        assert len(parent.children) == 1

        parent.remove_child(child.id)
        assert len(parent.children) == 0
        assert child.parent_id is None


# ==================== 测试2：折叠状态 ====================


class TestNodeDefinitionCollapsed:
    """测试 NodeDefinition 折叠状态"""

    def test_node_has_collapsed_attribute(self):
        """节点应有 collapsed 属性"""
        node = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
        )

        assert hasattr(node, "collapsed")

    def test_generic_node_default_collapsed_true(self):
        """GENERIC 节点默认折叠"""
        node = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
        )

        assert node.collapsed is True

    def test_can_expand_node(self):
        """可以展开节点"""
        node = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
        )

        node.expand()
        assert node.collapsed is False

    def test_can_collapse_node(self):
        """可以折叠节点"""
        node = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
        )

        node.expand()
        node.collapse()
        assert node.collapsed is True

    def test_toggle_collapse(self):
        """可以切换折叠状态"""
        node = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
        )

        initial = node.collapsed
        node.toggle_collapsed()
        assert node.collapsed != initial


# ==================== 测试3：容器节点标识 ====================


class TestContainerNodeDefinition:
    """测试容器节点定义"""

    def test_node_has_is_container_attribute(self):
        """节点应有 is_container 属性"""
        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="容器节点",
            code="print('hello')",
        )

        assert hasattr(node, "is_container")

    def test_container_node_default_false(self):
        """is_container 默认为 False"""
        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="普通节点",
            code="print('hello')",
        )

        assert node.is_container is False

    def test_can_set_is_container(self):
        """可以设置 is_container"""
        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="容器节点",
            code="import pandas; print(pandas.__version__)",
            is_container=True,
        )

        assert node.is_container is True

    def test_container_node_has_container_config(self):
        """容器节点应有容器配置"""
        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="容器节点",
            code="print('hello')",
            is_container=True,
            container_config={
                "image": "python:3.11",
                "timeout": 60,
                "memory_limit": "256m",
            },
        )

        assert hasattr(node, "container_config")
        assert node.container_config["image"] == "python:3.11"
        assert node.container_config["timeout"] == 60


# ==================== 测试4：获取子节点 ====================


class TestGetChildren:
    """测试获取子节点"""

    def test_get_visible_children_when_expanded(self):
        """展开时应返回所有子节点"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
        )

        child1 = NodeDefinition(node_type=NodeType.PYTHON, name="子1", code="pass")
        child2 = NodeDefinition(node_type=NodeType.LLM, name="子2", prompt="test")

        parent.add_child(child1)
        parent.add_child(child2)
        parent.expand()

        visible = parent.get_visible_children()
        assert len(visible) == 2

    def test_get_visible_children_when_collapsed(self):
        """折叠时应返回空列表"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
        )

        child = NodeDefinition(node_type=NodeType.PYTHON, name="子节点", code="pass")
        parent.add_child(child)

        # 确保折叠状态
        parent.collapse()

        visible = parent.get_visible_children()
        assert len(visible) == 0

    def test_get_all_descendants(self):
        """可以获取所有后代节点"""
        grandparent = NodeDefinition(node_type=NodeType.GENERIC, name="祖父")
        parent = NodeDefinition(node_type=NodeType.GENERIC, name="父亲")
        child = NodeDefinition(node_type=NodeType.PYTHON, name="孩子", code="pass")

        grandparent.add_child(parent)
        parent.add_child(child)

        descendants = grandparent.get_all_descendants()
        assert len(descendants) == 2
        assert parent in descendants
        assert child in descendants


# ==================== 测试5：序列化包含层级 ====================


class TestHierarchySerialization:
    """测试层级结构序列化"""

    def test_to_dict_includes_hierarchy(self):
        """to_dict 应包含层级信息"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
        )

        child = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="子节点",
            code="print('hello')",
            is_container=True,
        )

        parent.add_child(child)

        data = parent.to_dict()

        assert "children" in data
        assert len(data["children"]) == 1
        assert "parent_id" in data
        assert "collapsed" in data
        assert data["children"][0]["name"] == "子节点"
        assert data["children"][0]["is_container"] is True

    def test_from_dict_restores_hierarchy(self):
        """from_dict 应恢复层级结构"""
        data = {
            "node_type": "generic",
            "name": "父节点",
            "collapsed": False,
            "children": [
                {
                    "node_type": "python",
                    "name": "子节点",
                    "code": "print('hello')",
                    "is_container": True,
                    "container_config": {"image": "python:3.11"},
                }
            ],
        }

        node = NodeDefinition.from_dict(data)

        assert node.name == "父节点"
        assert node.collapsed is False
        assert len(node.children) == 1
        assert node.children[0].name == "子节点"
        assert node.children[0].is_container is True
        assert node.children[0].parent_id == node.id


# ==================== 测试6：深度限制 ====================


class TestHierarchyDepthLimit:
    """测试层级深度限制"""

    def test_max_depth_limit(self):
        """应有最大深度限制"""
        from src.domain.agents.node_definition import MAX_NODE_DEFINITION_DEPTH

        assert MAX_NODE_DEFINITION_DEPTH == 5

    def test_cannot_exceed_max_depth(self):
        """不能超过最大深度"""
        from src.domain.agents.node_definition import MAX_NODE_DEFINITION_DEPTH

        # 创建深度链
        nodes = []
        for i in range(MAX_NODE_DEFINITION_DEPTH + 1):
            nodes.append(NodeDefinition(node_type=NodeType.GENERIC, name=f"层级{i}"))

        # 链接到第5层应该成功
        for i in range(MAX_NODE_DEFINITION_DEPTH):
            nodes[i].add_child(nodes[i + 1])

        # 尝试添加第6层应该失败
        too_deep = NodeDefinition(node_type=NodeType.GENERIC, name="太深了")
        with pytest.raises(ValueError, match="Max depth"):
            nodes[MAX_NODE_DEFINITION_DEPTH].add_child(too_deep)


# 导出
__all__ = [
    "TestNodeDefinitionHierarchy",
    "TestNodeDefinitionCollapsed",
    "TestContainerNodeDefinition",
    "TestGetChildren",
    "TestHierarchySerialization",
    "TestHierarchyDepthLimit",
]
