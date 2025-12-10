"""
测试 NodeDefinition 和 NodeRegistry 的控制流配置统一

Priority 1: 统一控制流配置与执行支持
- NodeRegistry LOOP schema 对齐
- NodeDefinition 验证 CONDITION/LOOP 必填字段
- WorkflowAgent 执行 CONDITION 节点
"""

import pytest

from src.domain.agents.node_definition import NodeDefinition, NodeType
from src.domain.agents.workflow_agent import WorkflowAgent
from src.domain.services.context_manager import GlobalContext, SessionContext, WorkflowContext
from src.domain.services.event_bus import EventBus
from src.domain.services.expression_evaluator import ExpressionEvaluationError
from src.domain.services.node_registry import NodeRegistry


class TestNodeRegistryLoopSchema:
    """测试 NodeRegistry LOOP schema 包含正确字段"""

    def test_loop_schema_contains_collection_field(self):
        """测试 LOOP schema 包含 collection_field 字段"""
        registry = NodeRegistry()
        loop_schema = registry.get_schema(NodeType.LOOP)

        assert loop_schema is not None
        properties = loop_schema.get("properties", {})
        assert "collection_field" in properties, "LOOP schema 应包含 collection_field"

    def test_loop_schema_contains_transform_expression(self):
        """测试 LOOP schema 包含 transform_expression 字段"""
        registry = NodeRegistry()
        loop_schema = registry.get_schema(NodeType.LOOP)

        assert loop_schema is not None
        properties = loop_schema.get("properties", {})
        assert "transform_expression" in properties, "LOOP schema 应包含 transform_expression"

    def test_loop_schema_contains_filter_condition(self):
        """测试 LOOP schema 包含 filter_condition 字段"""
        registry = NodeRegistry()
        loop_schema = registry.get_schema(NodeType.LOOP)

        assert loop_schema is not None
        properties = loop_schema.get("properties", {})
        assert "filter_condition" in properties, "LOOP schema 应包含 filter_condition"


class TestConditionNodeValidation:
    """测试 CONDITION 节点验证逻辑"""

    def test_condition_node_requires_expression(self):
        """测试 CONDITION 节点必须有 expression 字段"""
        # 缺少 expression 字段应该抛出异常
        with pytest.raises(ValueError, match="expression|必填|required"):
            NodeDefinition(
                node_type=NodeType.CONDITION,
                name="quality_check",
                config={},  # 缺少 expression
            )

    def test_condition_node_with_valid_expression(self):
        """测试带有效 expression 的 CONDITION 节点"""
        node = NodeDefinition(
            node_type=NodeType.CONDITION,
            name="quality_check",
            config={"expression": "quality_score > 0.8"},
        )

        assert node.node_type == NodeType.CONDITION
        assert node.config["expression"] == "quality_score > 0.8"

    def test_condition_node_from_yaml_without_expression(self):
        """测试从YAML加载缺少 expression 的 CONDITION 节点"""
        yaml_content = """
        id: cond1
        name: quality_check
        type: CONDITION
        config: {}
        """

        with pytest.raises(ValueError, match="expression|必填|required"):
            NodeDefinition.from_yaml(yaml_content)


class TestLoopNodeValidation:
    """测试 LOOP 节点验证逻辑"""

    def test_loop_node_has_default_loop_type(self):
        """测试 LOOP 节点 loop_type 有默认值 for_each"""
        # loop_type 有默认值，所以不提供也是合法的
        node = NodeDefinition(
            node_type=NodeType.LOOP,
            name="process_datasets",
            config={"collection_field": "datasets"},  # 不提供 loop_type，应使用默认值
        )
        # 验证节点创建成功
        assert node.node_type == NodeType.LOOP
        assert node.config["collection_field"] == "datasets"

    def test_loop_node_requires_collection_field(self):
        """测试 LOOP 节点必须有 collection_field 字段"""
        with pytest.raises(ValueError, match="collection_field|必填|required"):
            NodeDefinition(
                node_type=NodeType.LOOP,
                name="process_datasets",
                config={"loop_type": "for_each"},  # 缺少 collection_field
            )

    def test_loop_node_with_valid_config(self):
        """测试带有效配置的 LOOP 节点"""
        node = NodeDefinition(
            node_type=NodeType.LOOP,
            name="process_datasets",
            config={
                "loop_type": "for_each",
                "collection_field": "datasets",
                "item_variable": "dataset",
            },
        )

        assert node.node_type == NodeType.LOOP
        assert node.config["loop_type"] == "for_each"
        assert node.config["collection_field"] == "datasets"

    def test_loop_node_map_type_requires_transform_expression(self):
        """测试 map 类型的 LOOP 节点需要 transform_expression"""
        with pytest.raises(ValueError, match="transform_expression|必填|required"):
            NodeDefinition(
                node_type=NodeType.LOOP,
                name="transform_data",
                config={
                    "loop_type": "map",
                    "collection_field": "items",
                    # 缺少 transform_expression
                },
            )

    def test_loop_node_filter_type_requires_filter_condition(self):
        """测试 filter 类型的 LOOP 节点需要 filter_condition"""
        with pytest.raises(ValueError, match="filter_condition|必填|required"):
            NodeDefinition(
                node_type=NodeType.LOOP,
                name="filter_data",
                config={
                    "loop_type": "filter",
                    "collection_field": "items",
                    # 缺少 filter_condition
                },
            )


class TestWorkflowAgentConditionNodeExecution:
    """测试 WorkflowAgent 执行 CONDITION 节点"""

    @pytest.fixture
    def workflow_agent(self):
        """创建 WorkflowAgent 实例"""
        event_bus = EventBus()
        agent = WorkflowAgent(event_bus=event_bus)
        return agent

    @pytest.fixture
    def workflow_context(self):
        """创建工作流上下文"""
        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="test_session", global_context=global_ctx)
        context = WorkflowContext(workflow_id="wf1", session_context=session_ctx)
        # 设置一些节点输出
        context.set_node_output("node1", {"quality_score": 0.9})
        return context

    def test_workflow_agent_has_evaluate_condition_node_method(self, workflow_agent):
        """测试 WorkflowAgent 有 evaluate_condition_node 方法"""
        assert hasattr(workflow_agent, "evaluate_condition_node")
        assert callable(workflow_agent.evaluate_condition_node)

    def test_evaluate_condition_node_returns_boolean(self, workflow_agent, workflow_context):
        """测试 evaluate_condition_node 返回布尔值"""
        condition_node = NodeDefinition(
            node_type=NodeType.CONDITION,
            name="quality_check",
            config={"expression": "quality_score > 0.8"},
        )

        result = workflow_agent.evaluate_condition_node(
            node=condition_node, context=workflow_context
        )

        assert isinstance(result, bool)
        assert result is True  # 0.9 > 0.8

    def test_evaluate_condition_node_false_condition(self, workflow_agent, workflow_context):
        """测试 evaluate_condition_node 返回 False"""
        condition_node = NodeDefinition(
            node_type=NodeType.CONDITION,
            name="quality_check",
            config={"expression": "quality_score < 0.5"},
        )

        result = workflow_agent.evaluate_condition_node(
            node=condition_node, context=workflow_context
        )

        assert result is False  # 0.9 < 0.5 为假

    def test_evaluate_condition_node_with_workflow_vars(self, workflow_agent):
        """测试 evaluate_condition_node 使用工作流变量"""
        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="test_session", global_context=global_ctx)
        context = WorkflowContext(workflow_id="wf1", session_context=session_ctx)
        context.set_variable("threshold", 0.7)
        context.set_node_output("node1", {"quality_score": 0.85})

        condition_node = NodeDefinition(
            node_type=NodeType.CONDITION,
            name="quality_check",
            config={"expression": "quality_score > threshold"},
        )

        result = workflow_agent.evaluate_condition_node(node=condition_node, context=context)

        assert result is True  # 0.85 > 0.7

    def test_evaluate_condition_node_invalid_expression(self, workflow_agent, workflow_context):
        """测试 evaluate_condition_node 处理无效表达式"""
        condition_node = NodeDefinition(
            node_type=NodeType.CONDITION,
            name="invalid_check",
            config={"expression": "invalid syntax !!!"},
        )

        with pytest.raises(ExpressionEvaluationError):  # 应该抛出表达式错误
            workflow_agent.evaluate_condition_node(node=condition_node, context=workflow_context)
