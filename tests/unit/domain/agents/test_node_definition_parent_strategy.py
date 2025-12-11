"""测试 NodeDefinition 父节点策略继承机制

测试范围：
1. 父节点必须定义 error_strategy 和 resource_limits
2. 策略传播到所有子节点（包括递归传播）
3. 子节点不能覆盖继承的策略
4. resource_limits 字段验证
"""

import pytest

from src.domain.agents.node_definition import NodeDefinition, NodeType


class TestParentNodeRequirements:
    """测试父节点必须定义策略"""

    def test_parent_node_requires_error_strategy(self):
        """父节点（GENERIC + 有子节点）必须定义 error_strategy"""
        # 创建父节点但不定义 error_strategy
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="parent_node",
        )

        # 添加子节点
        child = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="child_node",
            code="return {'result': 'ok'}",
        )
        parent.add_child(child)

        # 验证应该失败，因为缺少 error_strategy
        errors = parent.validate()
        assert len(errors) > 0
        assert any("error_strategy" in err.lower() for err in errors)

    def test_parent_node_requires_resource_limits(self):
        """父节点必须定义 resource_limits"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="parent_node",
            error_strategy={"on_failure": "abort"},
        )

        child = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="child_node",
            code="return {}",
        )
        parent.add_child(child)

        # 验证应该失败，因为缺少 resource_limits
        errors = parent.validate()
        assert len(errors) > 0
        assert any("resource_limits" in err.lower() for err in errors)

    def test_parent_node_with_complete_strategy_is_valid(self):
        """父节点定义完整策略时验证通过"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="parent_node",
            error_strategy={"on_failure": "abort", "retry": {"max_attempts": 2}},
            resource_limits={
                "cpu_limit": "2.0",
                "memory_limit": "4Gi",
                "timeout_seconds": 300,
            },
        )

        child = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="child_node",
            code="return {}",
        )
        parent.add_child(child)

        errors = parent.validate()
        assert len(errors) == 0

    def test_non_parent_generic_node_does_not_require_strategy(self):
        """没有子节点的 GENERIC 节点不强制要求策略"""
        node = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="leaf_node",
        )

        # 没有子节点，不应要求 error_strategy
        errors = node.validate()
        # 不应该有关于 error_strategy 或 resource_limits 的错误
        assert not any("error_strategy" in err.lower() for err in errors)
        assert not any("resource_limits" in err.lower() for err in errors)

    def test_non_generic_node_does_not_require_strategy(self):
        """非 GENERIC 节点不要求 error_strategy 和 resource_limits"""
        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="python_node",
            code="return {}",
        )

        errors = node.validate()
        assert not any("error_strategy" in err.lower() for err in errors)
        assert not any("resource_limits" in err.lower() for err in errors)


class TestStrategyPropagation:
    """测试策略传播逻辑"""

    def test_strategy_propagation_to_children(self):
        """策略应该传播到所有直接子节点"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="parent",
            error_strategy={"on_failure": "abort"},
            resource_limits={"memory_limit": "4Gi", "cpu_limit": "2.0"},
        )

        child1 = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="child1",
            code="pass",
        )
        child2 = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="child2",
            code="pass",
        )

        parent.add_child(child1)
        parent.add_child(child2)

        # 调用策略传播
        parent.propagate_strategy_to_children()

        # 验证子节点继承了策略
        assert child1.error_strategy == parent.error_strategy
        assert child1.resource_limits == parent.resource_limits
        assert child1.inherited_strategy is True

        assert child2.error_strategy == parent.error_strategy
        assert child2.resource_limits == parent.resource_limits
        assert child2.inherited_strategy is True

    def test_recursive_strategy_propagation(self):
        """策略应该递归传播到所有后代节点"""
        # 构建三层结构
        grandparent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="grandparent",
            error_strategy={"on_failure": "skip"},
            resource_limits={"timeout_seconds": 600},
        )

        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="parent",
        )

        child = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="child",
            code="pass",
        )

        grandparent.add_child(parent)
        parent.add_child(child)

        # 传播策略
        grandparent.propagate_strategy_to_children()

        # 验证传播到所有层级
        assert parent.error_strategy == grandparent.error_strategy
        assert parent.resource_limits == grandparent.resource_limits
        assert parent.inherited_strategy is True

        assert child.error_strategy == grandparent.error_strategy
        assert child.resource_limits == grandparent.resource_limits
        assert child.inherited_strategy is True

    def test_child_cannot_override_inherited_strategy(self):
        """子节点不能覆盖继承的策略"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="parent",
            error_strategy={"on_failure": "abort"},
            resource_limits={"memory_limit": "2Gi"},
        )

        child = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="child",
            code="pass",
            error_strategy={"on_failure": "continue"},  # 子节点尝试定义自己的策略
        )

        parent.add_child(child)
        parent.propagate_strategy_to_children()

        # 验证子节点的策略被父节点覆盖
        assert child.error_strategy == parent.error_strategy
        assert child.error_strategy != {"on_failure": "continue"}
        assert child.inherited_strategy is True

    def test_resource_limits_are_copied_not_referenced(self):
        """resource_limits 应该被复制，而不是引用"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="parent",
            error_strategy={"on_failure": "abort"},
            resource_limits={"memory_limit": "4Gi"},
        )

        child = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="child",
            code="pass",
        )

        parent.add_child(child)
        parent.propagate_strategy_to_children()

        # 修改子节点的 resource_limits
        child.resource_limits["cpu_limit"] = "1.0"

        # 父节点的 resource_limits 不应受影响
        assert "cpu_limit" not in parent.resource_limits
        assert parent.resource_limits == {"memory_limit": "4Gi"}


class TestResourceLimitsField:
    """测试 resource_limits 字段"""

    def test_resource_limits_default_value(self):
        """resource_limits 默认值应该是空字典"""
        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="test_node",
            code="pass",
        )

        assert node.resource_limits == {}

    def test_resource_limits_can_be_set(self):
        """可以设置 resource_limits"""
        node = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="test_node",
            resource_limits={
                "cpu_limit": "2.0",
                "memory_limit": "4Gi",
                "timeout_seconds": 300,
                "max_concurrent_children": 3,
            },
        )

        assert node.resource_limits["cpu_limit"] == "2.0"
        assert node.resource_limits["memory_limit"] == "4Gi"
        assert node.resource_limits["timeout_seconds"] == 300
        assert node.resource_limits["max_concurrent_children"] == 3


class TestInheritedStrategyField:
    """测试 inherited_strategy 字段"""

    def test_inherited_strategy_default_value(self):
        """inherited_strategy 默认值应该是 False"""
        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="test_node",
            code="pass",
        )

        assert node.inherited_strategy is False

    def test_inherited_strategy_set_after_propagation(self):
        """策略传播后 inherited_strategy 应该为 True"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="parent",
            error_strategy={"on_failure": "abort"},
            resource_limits={"memory_limit": "4Gi"},
        )

        child = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="child",
            code="pass",
        )

        parent.add_child(child)

        # 传播前
        assert child.inherited_strategy is False

        # 传播后
        parent.propagate_strategy_to_children()
        assert child.inherited_strategy is True


class TestSerializationWithNewFields:
    """测试序列化包含新字段"""

    def test_to_dict_includes_resource_limits(self):
        """to_dict 应该包含 resource_limits"""
        node = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="test_node",
            resource_limits={"cpu_limit": "2.0"},
        )

        data = node.to_dict()
        assert "resource_limits" in data
        assert data["resource_limits"] == {"cpu_limit": "2.0"}

    def test_to_dict_includes_inherited_strategy(self):
        """to_dict 应该包含 inherited_strategy"""
        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="test_node",
            code="pass",
            inherited_strategy=True,
        )

        data = node.to_dict()
        assert "inherited_strategy" in data
        assert data["inherited_strategy"] is True

    def test_from_dict_restores_resource_limits(self):
        """from_dict 应该恢复 resource_limits"""
        data = {
            "node_type": "generic",
            "name": "test_node",
            "resource_limits": {"memory_limit": "4Gi"},
        }

        node = NodeDefinition.from_dict(data)
        assert node.resource_limits == {"memory_limit": "4Gi"}

    def test_from_dict_restores_inherited_strategy(self):
        """from_dict 应该恢复 inherited_strategy"""
        data = {
            "node_type": "python",
            "name": "test_node",
            "code": "pass",
            "inherited_strategy": True,
        }

        node = NodeDefinition.from_dict(data)
        assert node.inherited_strategy is True


class TestEdgeCases:
    """测试边界情况"""

    def test_propagation_on_node_with_no_children(self):
        """在没有子节点的情况下调用 propagate_strategy_to_children 不应报错"""
        node = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="parent",
            error_strategy={"on_failure": "abort"},
            resource_limits={"memory_limit": "4Gi"},
        )

        # 不应抛出异常
        node.propagate_strategy_to_children()
        assert node.children == []

    def test_propagation_to_many_children(self):
        """验证策略传播到大量子节点"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="parent",
            error_strategy={"on_failure": "abort"},
            resource_limits={"memory_limit": "4Gi"},
        )

        # 创建10个子节点
        children = [
            NodeDefinition(node_type=NodeType.PYTHON, name=f"child_{i}", code="pass")
            for i in range(10)
        ]

        for child in children:
            parent.add_child(child)

        parent.propagate_strategy_to_children()

        # 验证所有子节点都继承了策略
        for child in children:
            assert child.error_strategy == parent.error_strategy, (
                f"Child {child.name} did not inherit error_strategy"
            )
            assert child.resource_limits == parent.resource_limits, (
                f"Child {child.name} did not inherit resource_limits"
            )
            assert child.inherited_strategy is True, (
                f"Child {child.name} inherited_strategy flag not set"
            )

    def test_parent_node_with_empty_resource_limits(self):
        """空的 resource_limits 字典应该被视为无效"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="parent",
            error_strategy={"on_failure": "abort"},
            resource_limits={},  # 空字典
        )

        child = NodeDefinition(node_type=NodeType.PYTHON, name="child", code="pass")
        parent.add_child(child)

        errors = parent.validate()
        # 空的 resource_limits 应该被视为未定义
        assert any("resource_limits" in err.lower() for err in errors), (
            f"Expected resource_limits validation error, but got: {errors}"
        )
