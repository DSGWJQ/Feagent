"""WorkflowAgent 多层上下文条件分支测试 (Phase 2)

业务场景：
- 条件表达式支持多层上下文：节点输出 + workflow变量 + global变量
- 条件求值优先级：节点输出 > workflow_vars > global_vars
- 条件结果写入WorkflowContext供下游使用

测试策略：
- 测试条件使用workflow变量
- 测试条件使用global变量
- 测试多层上下文优先级
- 测试条件结果记录
"""

import pytest

from src.domain.agents.workflow_agent import WorkflowAgent
from src.domain.services.context_manager import (
    GlobalContext,
    SessionContext,
    WorkflowContext,
)
from src.domain.services.event_bus import EventBus
from src.domain.services.node_registry import NodeFactory, NodeRegistry, NodeType


class MockNodeExecutor:
    """模拟节点执行器"""

    def __init__(self):
        self.executed_nodes = []
        self.node_outputs = {}

    def set_node_output(self, node_id: str, output: dict):
        """设置节点的输出"""
        self.node_outputs[node_id] = output

    async def execute(self, node_id: str, config: dict, inputs: dict):
        """执行节点"""
        self.executed_nodes.append(node_id)
        return self.node_outputs.get(node_id, {"status": "success", "executed": True})


class TestMultiLayerContextConditions:
    """多层上下文条件测试"""

    def setup_method(self):
        """测试前设置"""
        self.event_bus = EventBus()

        # 创建上下文层次结构
        self.global_context = GlobalContext(user_id="test_user")
        self.session_context = SessionContext(
            session_id="test_session", global_context=self.global_context
        )
        self.workflow_context = WorkflowContext(
            workflow_id="test_wf", session_context=self.session_context
        )

        # 创建NodeFactory和Executor
        self.node_registry = NodeRegistry()
        self.node_factory = NodeFactory(self.node_registry)
        self.node_executor = MockNodeExecutor()

        self.agent = WorkflowAgent(
            workflow_context=self.workflow_context,
            node_factory=self.node_factory,
            node_executor=self.node_executor,
            event_bus=self.event_bus,
        )

    # ==================== Workflow变量测试 ====================

    @pytest.mark.asyncio
    async def test_condition_with_workflow_variable(self):
        """测试条件使用workflow变量

        场景：
        workflow_context.variables["quality_threshold"] = 0.8
        node_a (quality=0.9) -> [condition: quality >= quality_threshold] -> node_b
        预期：node_b被执行（因为0.9 >= 0.8）
        """
        # 设置workflow变量
        self.workflow_context.set_variable("quality_threshold", 0.8)

        # 创建节点
        node_a = self.node_factory.create(NodeType.GENERIC, {"name": "node_a"})
        node_b = self.node_factory.create(NodeType.GENERIC, {"name": "node_b"})

        self.agent.add_node(node_a)
        self.agent.add_node(node_b)

        # 设置node_a的输出
        self.node_executor.set_node_output(node_a.id, {"quality": 0.9})

        # 创建条件边（使用workflow变量）
        self.agent.connect_nodes(
            source_id=node_a.id,
            target_id=node_b.id,
            condition="quality >= quality_threshold",
        )

        # 执行工作流
        result = await self.agent.execute_workflow_with_conditions()

        # 验证：node_b应该被执行
        assert node_b.id in self.node_executor.executed_nodes
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_condition_with_workflow_variable_false(self):
        """测试条件使用workflow变量（条件不满足）

        场景：
        workflow_context.variables["min_score"] = 0.8
        node_a (score=0.7) -> [condition: score >= min_score] -> node_b
        预期：node_b被跳过（因为0.7 < 0.8）
        """
        # 设置workflow变量
        self.workflow_context.set_variable("min_score", 0.8)

        # 创建节点
        node_a = self.node_factory.create(NodeType.GENERIC, {"name": "node_a"})
        node_b = self.node_factory.create(NodeType.GENERIC, {"name": "node_b"})

        self.agent.add_node(node_a)
        self.agent.add_node(node_b)

        # 设置node_a的输出
        self.node_executor.set_node_output(node_a.id, {"score": 0.7})

        # 创建条件边
        self.agent.connect_nodes(
            source_id=node_a.id,
            target_id=node_b.id,
            condition="score >= min_score",
        )

        # 执行工作流
        result = await self.agent.execute_workflow_with_conditions()

        # 验证：node_b应该被跳过
        assert node_b.id not in self.node_executor.executed_nodes
        assert result["status"] == "completed"

    # ==================== Global变量测试 ====================

    @pytest.mark.asyncio
    async def test_condition_with_global_variable(self):
        """测试条件使用global变量

        场景：
        global_context.system_config["default_threshold"] = 0.5
        node_a (score=0.6) -> [condition: score > default_threshold] -> node_b
        预期：node_b被执行（因为0.6 > 0.5）
        """
        # 重新创建GlobalContext with system_config
        self.global_context = GlobalContext(
            user_id="test_user", system_config={"default_threshold": 0.5}
        )
        self.session_context = SessionContext(
            session_id="test_session", global_context=self.global_context
        )
        self.workflow_context = WorkflowContext(
            workflow_id="test_wf", session_context=self.session_context
        )
        self.agent = WorkflowAgent(
            workflow_context=self.workflow_context,
            node_factory=self.node_factory,
            node_executor=self.node_executor,
            event_bus=self.event_bus,
        )

        # 创建节点
        node_a = self.node_factory.create(NodeType.GENERIC, {"name": "node_a"})
        node_b = self.node_factory.create(NodeType.GENERIC, {"name": "node_b"})

        self.agent.add_node(node_a)
        self.agent.add_node(node_b)

        # 设置node_a的输出
        self.node_executor.set_node_output(node_a.id, {"score": 0.6})

        # 创建条件边
        self.agent.connect_nodes(
            source_id=node_a.id,
            target_id=node_b.id,
            condition="score > default_threshold",
        )

        # 执行工作流
        result = await self.agent.execute_workflow_with_conditions()

        # 验证：node_b应该被执行
        assert node_b.id in self.node_executor.executed_nodes
        assert result["status"] == "completed"

    # ==================== 优先级测试 ====================

    @pytest.mark.asyncio
    async def test_context_priority_node_output_overrides_workflow_var(self):
        """测试上下文优先级：节点输出 > workflow变量

        场景：
        workflow_context.variables["value"] = 10
        node_a (value=20) -> [condition: value > 15] -> node_b
        预期：node_b被执行（使用节点输出的value=20，而非workflow变量的value=10）
        """
        # 设置workflow变量
        self.workflow_context.set_variable("value", 10)

        # 创建节点
        node_a = self.node_factory.create(NodeType.GENERIC, {"name": "node_a"})
        node_b = self.node_factory.create(NodeType.GENERIC, {"name": "node_b"})

        self.agent.add_node(node_a)
        self.agent.add_node(node_b)

        # 设置node_a的输出（覆盖workflow变量）
        self.node_executor.set_node_output(node_a.id, {"value": 20})

        # 创建条件边
        self.agent.connect_nodes(source_id=node_a.id, target_id=node_b.id, condition="value > 15")

        # 执行工作流
        result = await self.agent.execute_workflow_with_conditions()

        # 验证：node_b应该被执行（因为使用节点输出的value=20）
        assert node_b.id in self.node_executor.executed_nodes
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_context_priority_workflow_var_overrides_global_var(self):
        """测试上下文优先级：workflow变量 > global变量

        场景：
        global_context.system_config["threshold"] = 0.5
        workflow_context.variables["threshold"] = 0.8
        node_a (score=0.7) -> [condition: score > threshold] -> node_b
        预期：node_b被跳过（使用workflow变量的threshold=0.8，而非global变量的0.5）
        """
        # 重新创建GlobalContext with system_config
        self.global_context = GlobalContext(user_id="test_user", system_config={"threshold": 0.5})
        self.session_context = SessionContext(
            session_id="test_session", global_context=self.global_context
        )
        self.workflow_context = WorkflowContext(
            workflow_id="test_wf", session_context=self.session_context
        )
        self.agent = WorkflowAgent(
            workflow_context=self.workflow_context,
            node_factory=self.node_factory,
            node_executor=self.node_executor,
            event_bus=self.event_bus,
        )

        # 设置workflow变量
        self.workflow_context.set_variable("threshold", 0.8)

        # 创建节点
        node_a = self.node_factory.create(NodeType.GENERIC, {"name": "node_a"})
        node_b = self.node_factory.create(NodeType.GENERIC, {"name": "node_b"})

        self.agent.add_node(node_a)
        self.agent.add_node(node_b)

        # 设置node_a的输出
        self.node_executor.set_node_output(node_a.id, {"score": 0.7})

        # 创建条件边
        self.agent.connect_nodes(
            source_id=node_a.id, target_id=node_b.id, condition="score > threshold"
        )

        # 执行工作流
        result = await self.agent.execute_workflow_with_conditions()

        # 验证：node_b应该被跳过（因为0.7 < 0.8，使用workflow变量）
        assert node_b.id not in self.node_executor.executed_nodes
        assert result["status"] == "completed"

    # ==================== 复杂场景测试 ====================

    @pytest.mark.asyncio
    async def test_complex_condition_with_all_context_layers(self):
        """测试复杂条件使用所有上下文层

        场景：
        global_context.system_config["base_value"] = 100
        workflow_context.variables["multiplier"] = 1.5
        node_a (input=50) -> [condition: input * multiplier > base_value] -> node_b
        预期：node_b被跳过（因为50 * 1.5 = 75 < 100）
        """
        # 重新创建GlobalContext with system_config
        self.global_context = GlobalContext(user_id="test_user", system_config={"base_value": 100})
        self.session_context = SessionContext(
            session_id="test_session", global_context=self.global_context
        )
        self.workflow_context = WorkflowContext(
            workflow_id="test_wf", session_context=self.session_context
        )
        self.agent = WorkflowAgent(
            workflow_context=self.workflow_context,
            node_factory=self.node_factory,
            node_executor=self.node_executor,
            event_bus=self.event_bus,
        )

        # 设置workflow变量
        self.workflow_context.set_variable("multiplier", 1.5)

        # 创建节点
        node_a = self.node_factory.create(NodeType.GENERIC, {"name": "node_a"})
        node_b = self.node_factory.create(NodeType.GENERIC, {"name": "node_b"})

        self.agent.add_node(node_a)
        self.agent.add_node(node_b)

        # 设置node_a的输出
        self.node_executor.set_node_output(node_a.id, {"input": 50})

        # 创建条件边（使用所有层的变量）
        self.agent.connect_nodes(
            source_id=node_a.id,
            target_id=node_b.id,
            condition="input * multiplier > base_value",
        )

        # 执行工作流
        result = await self.agent.execute_workflow_with_conditions()

        # 验证：node_b应该被跳过（因为75 < 100）
        assert node_b.id not in self.node_executor.executed_nodes
        assert result["status"] == "completed"


class TestConditionResultRecording:
    """条件结果记录测试"""

    def setup_method(self):
        """测试前设置"""
        self.event_bus = EventBus()

        # 创建上下文
        self.global_context = GlobalContext(user_id="test_user")
        self.session_context = SessionContext(
            session_id="test_session", global_context=self.global_context
        )
        self.workflow_context = WorkflowContext(
            workflow_id="test_wf", session_context=self.session_context
        )

        # 创建NodeFactory和Executor
        self.node_registry = NodeRegistry()
        self.node_factory = NodeFactory(self.node_registry)
        self.node_executor = MockNodeExecutor()

        self.agent = WorkflowAgent(
            workflow_context=self.workflow_context,
            node_factory=self.node_factory,
            node_executor=self.node_executor,
            event_bus=self.event_bus,
        )

    @pytest.mark.asyncio
    async def test_condition_result_written_to_context(self):
        """测试条件结果写入WorkflowContext

        场景：
        node_a (score=0.9) -> [condition: score > 0.8] -> node_b
        预期：条件结果（True）应该被记录到WorkflowContext.edge_conditions
        """
        # 创建节点
        node_a = self.node_factory.create(NodeType.GENERIC, {"name": "node_a"})
        node_b = self.node_factory.create(NodeType.GENERIC, {"name": "node_b"})

        self.agent.add_node(node_a)
        self.agent.add_node(node_b)

        # 设置node_a的输出
        self.node_executor.set_node_output(node_a.id, {"score": 0.9})

        # 创建条件边
        edge = self.agent.connect_nodes(
            source_id=node_a.id, target_id=node_b.id, condition="score > 0.8"
        )

        # 执行工作流
        result = await self.agent.execute_workflow_with_conditions()

        # 验证：条件结果应该被记录到WorkflowContext.edge_conditions
        assert result["status"] == "completed"
        assert hasattr(self.workflow_context, "edge_conditions")
        assert len(self.workflow_context.edge_conditions) > 0

        # 查找该边的条件记录
        edge_condition = self.workflow_context.edge_conditions.get(edge.id)
        assert edge_condition is not None
        assert edge_condition["result"] is True
        assert edge_condition["expression"] == "score > 0.8"
        assert edge_condition["source_id"] == node_a.id
        assert edge_condition["target_id"] == node_b.id
        assert "evaluated_at" in edge_condition
        assert "error" not in edge_condition  # 成功时无错误

    @pytest.mark.asyncio
    async def test_condition_error_recorded_to_context(self):
        """测试条件评估失败时错误信息被记录

        场景：
        node_a (no score) -> [condition: score > 0.8] -> node_b
        预期：条件评估失败，错误信息应该被记录到WorkflowContext.edge_conditions
        """
        # 创建节点
        node_a = self.node_factory.create(NodeType.GENERIC, {"name": "node_a"})
        node_b = self.node_factory.create(NodeType.GENERIC, {"name": "node_b"})

        self.agent.add_node(node_a)
        self.agent.add_node(node_b)

        # 设置node_a的输出（不包含score字段，将导致条件评估失败）
        self.node_executor.set_node_output(node_a.id, {"other_field": "value"})

        # 创建条件边
        edge = self.agent.connect_nodes(
            source_id=node_a.id, target_id=node_b.id, condition="score > 0.8"
        )

        # 执行工作流
        result = await self.agent.execute_workflow_with_conditions()

        # 验证：工作流完成，但node_b未执行
        assert result["status"] == "completed"
        assert node_b.id not in self.node_executor.executed_nodes

        # 验证：条件评估失败被记录
        assert hasattr(self.workflow_context, "edge_conditions")
        edge_condition = self.workflow_context.edge_conditions.get(edge.id)
        assert edge_condition is not None
        assert edge_condition["result"] is False
        assert edge_condition["expression"] == "score > 0.8"
        assert "error" in edge_condition  # 失败时有错误信息
        assert "score" in edge_condition["error"]  # 错误信息应提到缺失的变量
