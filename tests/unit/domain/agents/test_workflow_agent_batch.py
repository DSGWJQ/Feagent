"""WorkflowAgent 批量操作测试 - Phase 8.5

TDD RED阶段：测试 WorkflowAgent 的批量操作能力
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestWorkflowAgentExecutePlan:
    """WorkflowAgent execute_plan 测试"""

    @pytest.mark.asyncio
    async def test_execute_plan_creates_nodes_from_plan(self):
        """execute_plan 应从规划创建所有节点"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.agents.workflow_plan import WorkflowPlan
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        # 设置上下文
        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="wf_1", session_context=session_ctx)

        # 设置节点工厂
        registry = NodeRegistry()
        factory = NodeFactory(registry)

        # 创建规划
        plan = WorkflowPlan(
            name="测试规划",
            goal="测试批量创建",
            nodes=[
                NodeDefinition(
                    node_type=NodeType.PYTHON,
                    name="节点1",
                    code="result = 1",
                ),
                NodeDefinition(
                    node_type=NodeType.PYTHON,
                    name="节点2",
                    code="result = 2",
                ),
            ],
            edges=[],
        )

        agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
        )

        # 执行规划
        result = await agent.execute_plan(plan)

        # 验证节点已创建
        assert len(agent.nodes) == 2
        assert result["status"] == "completed"
        assert result["nodes_created"] == 2

    @pytest.mark.asyncio
    async def test_execute_plan_creates_edges_from_plan(self):
        """execute_plan 应从规划创建所有边"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="wf_1", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        plan = WorkflowPlan(
            name="测试规划",
            goal="测试边创建",
            nodes=[
                NodeDefinition(node_type=NodeType.PYTHON, name="A", code="a=1"),
                NodeDefinition(node_type=NodeType.PYTHON, name="B", code="b=2"),
                NodeDefinition(node_type=NodeType.PYTHON, name="C", code="c=3"),
            ],
            edges=[
                EdgeDefinition(source_node="A", target_node="B"),
                EdgeDefinition(source_node="B", target_node="C"),
            ],
        )

        agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
        )

        result = await agent.execute_plan(plan)

        # 验证边已创建
        assert len(agent.edges) == 2
        assert result["edges_created"] == 2

    @pytest.mark.asyncio
    async def test_execute_plan_executes_workflow(self):
        """execute_plan 应执行创建的工作流"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.agents.workflow_plan import WorkflowPlan
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="wf_1", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        # Mock 执行器
        executor = MagicMock()
        executor.execute = AsyncMock(return_value={"result": "ok"})

        plan = WorkflowPlan(
            name="执行测试",
            goal="测试执行",
            nodes=[
                NodeDefinition(node_type=NodeType.PYTHON, name="Step1", code="x=1"),
            ],
            edges=[],
        )

        agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
            node_executor=executor,
        )

        result = await agent.execute_plan(plan)

        # 验证执行器被调用
        assert executor.execute.called
        assert result["status"] == "completed"
        assert "results" in result

    @pytest.mark.asyncio
    async def test_execute_plan_returns_node_mapping(self):
        """execute_plan 应返回节点名称到ID的映射"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.agents.workflow_plan import WorkflowPlan
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="wf_1", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        plan = WorkflowPlan(
            name="映射测试",
            goal="测试映射",
            nodes=[
                NodeDefinition(node_type=NodeType.PYTHON, name="NodeA", code="a=1"),
                NodeDefinition(node_type=NodeType.PYTHON, name="NodeB", code="b=2"),
            ],
            edges=[],
        )

        agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
        )

        result = await agent.execute_plan(plan)

        # 验证映射
        assert "node_mapping" in result
        assert "NodeA" in result["node_mapping"]
        assert "NodeB" in result["node_mapping"]


class TestWorkflowAgentBatchNodeCreation:
    """WorkflowAgent 批量节点创建测试"""

    @pytest.mark.asyncio
    async def test_create_nodes_batch(self):
        """应支持批量创建节点"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="wf_1", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        node_definitions = [
            NodeDefinition(node_type=NodeType.PYTHON, name="N1", code="x=1"),
            NodeDefinition(node_type=NodeType.PYTHON, name="N2", code="y=2"),
            NodeDefinition(node_type=NodeType.PYTHON, name="N3", code="z=3"),
        ]

        agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
        )

        # 批量创建节点
        created_nodes = agent.create_nodes_batch(node_definitions)

        assert len(created_nodes) == 3
        assert len(agent.nodes) == 3

    @pytest.mark.asyncio
    async def test_create_nodes_batch_returns_name_to_id_mapping(self):
        """批量创建应返回名称到ID的映射"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="wf_1", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        node_definitions = [
            NodeDefinition(node_type=NodeType.PYTHON, name="Alpha", code="a=1"),
            NodeDefinition(node_type=NodeType.PYTHON, name="Beta", code="b=2"),
        ]

        agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
        )

        result = agent.create_nodes_batch(node_definitions)

        # 返回的是 list[tuple[str, Node]]
        name_to_id = {name: node.id for name, node in result}
        assert "Alpha" in name_to_id
        assert "Beta" in name_to_id


class TestWorkflowAgentBatchEdgeCreation:
    """WorkflowAgent 批量边创建测试"""

    def test_connect_nodes_batch(self):
        """应支持批量连接节点"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.agents.workflow_plan import EdgeDefinition
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="wf_1", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
        )

        # 先创建节点
        nodes = agent.create_nodes_batch(
            [
                NodeDefinition(node_type=NodeType.PYTHON, name="A", code="a=1"),
                NodeDefinition(node_type=NodeType.PYTHON, name="B", code="b=2"),
                NodeDefinition(node_type=NodeType.PYTHON, name="C", code="c=3"),
            ]
        )
        name_to_id = {name: node.id for name, node in nodes}

        # 批量创建边
        edge_definitions = [
            EdgeDefinition(source_node="A", target_node="B"),
            EdgeDefinition(source_node="B", target_node="C"),
        ]

        edges = agent.connect_nodes_batch(edge_definitions, name_to_id)

        assert len(edges) == 2
        assert len(agent.edges) == 2


class TestWorkflowAgentModifyNode:
    """WorkflowAgent 节点修改测试"""

    def test_modify_node_updates_config(self):
        """modify_node 应更新节点配置"""
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="wf_1", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
        )

        # 创建节点
        node = agent.create_node(
            {
                "node_type": "python",
                "config": {"code": "old_code"},
            }
        )
        agent.add_node(node)

        # 修改节点
        result = agent.modify_node(node.id, {"code": "new_code"})

        assert result["success"] is True
        modified_node = agent.get_node(node.id)
        assert modified_node.config.get("code") == "new_code"

    def test_modify_node_returns_error_for_nonexistent_node(self):
        """修改不存在的节点应返回错误"""
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="wf_1", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
        )

        result = agent.modify_node("nonexistent_id", {"code": "new"})

        assert result["success"] is False
        assert "error" in result


class TestWorkflowAgentHandleDecisionBatch:
    """WorkflowAgent handle_decision 批量操作测试"""

    @pytest.mark.asyncio
    async def test_handle_decision_create_workflow_plan(self):
        """handle_decision 应支持 create_workflow_plan 决策"""
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="wf_1", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
        )

        decision = {
            "decision_type": "create_workflow_plan",
            "name": "Test Plan",
            "goal": "Test Goal",
            "nodes": [
                {"name": "N1", "type": "python", "code": "x=1"},
                {"name": "N2", "type": "python", "code": "y=2"},
            ],
            "edges": [
                {"source": "N1", "target": "N2"},
            ],
        }

        result = await agent.handle_decision(decision)

        assert result["success"] is True
        assert len(agent.nodes) == 2
        assert len(agent.edges) == 1

    @pytest.mark.asyncio
    async def test_handle_decision_modify_node(self):
        """handle_decision 应支持 modify_node 决策"""
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="wf_1", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
        )

        # 先创建节点
        node = agent.create_node(
            {
                "node_type": "python",
                "config": {"code": "old"},
            }
        )
        agent.add_node(node)

        decision = {
            "decision_type": "modify_node",
            "node_id": node.id,
            "config": {"code": "new"},
        }

        result = await agent.handle_decision(decision)

        assert result["success"] is True
        modified_node = agent.get_node(node.id)
        assert modified_node.config.get("code") == "new"


class TestWorkflowAgentPlanFromDict:
    """WorkflowAgent 从字典创建规划测试"""

    @pytest.mark.asyncio
    async def test_execute_plan_from_dict(self):
        """应支持从字典格式的规划执行"""
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="wf_1", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
        )

        plan_dict = {
            "name": "Dict Plan",
            "goal": "Test dict plan",
            "nodes": [
                {"name": "Step1", "type": "python", "code": "a=1"},
                {"name": "Step2", "type": "python", "code": "b=2"},
            ],
            "edges": [
                {"source": "Step1", "target": "Step2"},
            ],
        }

        result = await agent.execute_plan_from_dict(plan_dict)

        assert result["status"] == "completed"
        assert len(agent.nodes) == 2
        assert len(agent.edges) == 1
