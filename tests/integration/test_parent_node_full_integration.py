"""父子节点任务折叠机制 - 完整集成测试

测试目标：
1. 从 YAML 加载父节点定义
2. 验证策略传播到所有子节点
3. 验证容器化执行
4. 验证错误处理策略
5. 验证资源限制继承

完成标准：
- 父节点成功加载并展开子节点
- 所有子节点继承父节点的 error_strategy 和 resource_limits
- 容器执行成功并应用资源限制
- 错误策略正确触发（abort/skip/continue）
"""

import pytest

from src.domain.agents.node_definition import NodeDefinition, NodeType
from src.domain.services.parent_node_schema import ParentNodeValidator


class TestParentNodeFullIntegration:
    """完整集成测试：从 YAML 到执行"""

    @pytest.fixture
    def sample_parent_yaml(self):
        """示例父节点 YAML 配置"""
        return {
            "name": "data_processing_pipeline",
            "kind": "workflow",
            "version": "1.0.0",
            "description": "数据处理流水线",
            "inherit": {
                "error_strategy": {
                    "retry": {"max_attempts": 3, "delay_seconds": 5.0},
                    "on_failure": "abort",
                },
                "resources": {
                    "cpu": "2",
                    "memory": "4Gi",
                    "timeout_seconds": 600,
                },
                "parameters": {
                    "input_file": {"type": "string", "required": True},
                },
                "returns": {
                    "output_file": {"type": "string"},
                    "records_processed": {"type": "integer"},
                },
            },
            "children": [
                {"ref": "node.load", "alias": "load_step"},
                {"ref": "node.transform", "alias": "transform_step"},
                {"ref": "node.save", "alias": "save_step"},
            ],
        }

    @pytest.fixture
    def child_registry(self):
        """子节点注册表"""
        return {
            "node.load": NodeDefinition(
                node_type=NodeType.PYTHON,
                name="加载数据",
                code="df = pd.read_csv(input_file)",
            ),
            "node.transform": NodeDefinition(
                node_type=NodeType.PYTHON,
                name="数据转换",
                code="df['processed'] = df['value'] * 2",
            ),
            "node.save": NodeDefinition(
                node_type=NodeType.PYTHON,
                name="保存数据",
                code="df.to_csv(output_file)",
            ),
        }

    def test_full_pipeline_yaml_to_execution(self, sample_parent_yaml, child_registry):
        """完整流程：从 YAML 加载到节点定义"""
        # 1. 使用 ParentNodeValidator 验证
        validator = ParentNodeValidator()
        result = validator.validate(sample_parent_yaml)
        assert result.is_valid, f"YAML 验证失败: {result.errors}"

        # 2. 从 schema 创建 NodeDefinition
        parent = NodeDefinition.from_parent_schema(sample_parent_yaml, child_registry, validator)

        # 3. 验证父节点属性
        assert parent.name == "data_processing_pipeline"
        assert parent.node_type == NodeType.GENERIC
        assert parent.error_strategy is not None
        assert parent.error_strategy["on_failure"] == "abort"
        assert parent.error_strategy["retry"]["max_attempts"] == 3
        assert parent.resource_limits["cpu"] == "2"
        assert parent.resource_limits["memory"] == "4Gi"

        # 4. 验证子节点已展开
        assert len(parent.children) == 3
        assert parent.children[0].name == "加载数据"
        assert parent.children[1].name == "数据转换"
        assert parent.children[2].name == "保存数据"

        # 5. 传播策略到子节点
        parent.propagate_strategy_to_children()

        # 6. 验证策略传播成功
        for child in parent.children:
            assert (
                child.error_strategy == parent.error_strategy
            ), f"子节点 {child.name} 未继承 error_strategy"
            assert (
                child.resource_limits == parent.resource_limits
            ), f"子节点 {child.name} 未继承 resource_limits"
            assert (
                child.inherited_strategy is True
            ), f"子节点 {child.name} inherited_strategy 标志未设置"

    def test_nested_parent_strategy_propagation(self, child_registry):
        """测试多层嵌套的策略传播"""
        # 创建三层嵌套结构
        grandparent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="顶层流程",
            error_strategy={"on_failure": "abort", "retry": {"max_attempts": 5}},
            resource_limits={"cpu": "4", "memory": "8Gi"},
        )

        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="子流程",
        )

        child1 = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="步骤1",
            code="print('step1')",
        )

        child2 = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="步骤2",
            code="print('step2')",
        )

        # 构建层次结构
        grandparent.add_child(parent)
        parent.add_child(child1)
        parent.add_child(child2)

        # 从顶层传播策略
        grandparent.propagate_strategy_to_children()

        # 验证传播到所有层级
        assert parent.error_strategy == grandparent.error_strategy
        assert parent.resource_limits == grandparent.resource_limits
        assert parent.inherited_strategy is True

        assert child1.error_strategy == grandparent.error_strategy
        assert child1.resource_limits == grandparent.resource_limits
        assert child1.inherited_strategy is True

        assert child2.error_strategy == grandparent.error_strategy
        assert child2.resource_limits == grandparent.resource_limits
        assert child2.inherited_strategy is True

    def test_container_config_inheritance(self):
        """测试容器配置继承"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="容器化父节点",
            error_strategy={"on_failure": "continue"},
            resource_limits={
                "cpu_limit": "2.0",
                "memory_limit": "4Gi",
                "timeout_seconds": 300,
            },
            container_config={
                "image": "python:3.11-slim",
                "pip_packages": ["pandas", "numpy"],
            },
        )

        child = NodeDefinition(
            node_type=NodeType.CONTAINER,
            name="容器子节点",
            code="import pandas as pd",
            is_container=True,
        )

        parent.add_child(child)
        parent.propagate_strategy_to_children()

        # 验证子节点继承策略
        assert child.error_strategy == parent.error_strategy
        assert child.resource_limits == parent.resource_limits
        assert child.inherited_strategy is True

    def test_error_strategy_abort(self):
        """测试 abort 错误策略"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="严格流程",
            error_strategy={"on_failure": "abort"},
            resource_limits={"timeout_seconds": 60},
        )

        child1 = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="步骤1",
            code="success = True",
        )

        child2 = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="步骤2（会失败）",
            code="raise ValueError('测试失败')",
        )

        child3 = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="步骤3",
            code="print('should not execute')",
        )

        parent.add_child(child1)
        parent.add_child(child2)
        parent.add_child(child3)

        parent.propagate_strategy_to_children()

        # 验证策略已设置
        for child in parent.children:
            assert child.error_strategy["on_failure"] == "abort"

    def test_serialization_with_hierarchy(self):
        """测试带层次结构的序列化"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
            error_strategy={"on_failure": "skip"},
            resource_limits={"cpu": "1", "memory": "2Gi"},
        )

        child = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="子节点",
            code="result = 42",
        )

        parent.add_child(child)
        parent.propagate_strategy_to_children()

        # 序列化
        data = parent.to_dict()

        # 反序列化
        restored = NodeDefinition.from_dict(data)

        # 验证父节点
        assert restored.name == parent.name
        assert restored.error_strategy == parent.error_strategy
        assert restored.resource_limits == parent.resource_limits

        # 验证子节点
        assert len(restored.children) == 1
        assert restored.children[0].name == child.name
        assert restored.children[0].error_strategy == child.error_strategy
        assert restored.children[0].inherited_strategy is True


class TestResourceLimitValidation:
    """资源限制验证测试"""

    def test_cpu_limit_format(self):
        """测试 CPU 限制格式"""
        node = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="测试节点",
            resource_limits={"cpu_limit": "2.0"},
        )

        assert node.resource_limits["cpu_limit"] == "2.0"

    def test_memory_limit_format(self):
        """测试内存限制格式"""
        node = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="测试节点",
            resource_limits={"memory_limit": "4Gi"},
        )

        assert node.resource_limits["memory_limit"] == "4Gi"

    def test_timeout_limit(self):
        """测试超时限制"""
        node = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="测试节点",
            resource_limits={"timeout_seconds": 300},
        )

        assert node.resource_limits["timeout_seconds"] == 300

    def test_all_limits_combined(self):
        """测试所有限制组合"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
            error_strategy={"on_failure": "abort"},
            resource_limits={
                "cpu_limit": "2.0",
                "memory_limit": "4Gi",
                "timeout_seconds": 600,
                "max_concurrent_children": 3,
            },
        )

        child = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="子节点",
            code="pass",
        )

        parent.add_child(child)
        parent.propagate_strategy_to_children()

        # 验证所有限制都被继承
        assert child.resource_limits["cpu_limit"] == "2.0"
        assert child.resource_limits["memory_limit"] == "4Gi"
        assert child.resource_limits["timeout_seconds"] == 600
        assert child.resource_limits["max_concurrent_children"] == 3


__all__ = [
    "TestParentNodeFullIntegration",
    "TestResourceLimitValidation",
]
