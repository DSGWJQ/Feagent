"""测试：工作流Agent (WorkflowAgent)

TDD 第一步：编写测试用例，明确需求和验收标准

业务背景：
- 工作流Agent是多Agent协作系统的"执行者"
- 负责节点执行、工作流管理、画布同步
- 接收对话Agent的决策，执行具体操作

真实场景：
1. 收到创建节点的决策 → 通过NodeFactory创建节点
2. 收到执行工作流的决策 → 启动执行引擎
3. 节点执行完成 → 更新WorkflowContext
4. 执行状态变化 → 同步到画布（发布事件）

核心能力：
- 节点管理：创建、配置、连接节点
- 工作流执行：按DAG顺序执行节点
- 状态同步：将执行状态同步到画布
- 结果汇报：向对话Agent反馈执行结果
"""

from unittest.mock import AsyncMock

import pytest


class TestWorkflowAgentNodeManagement:
    """测试工作流Agent的节点管理能力

    业务背景：
    - 工作流Agent负责创建和管理节点
    - 节点通过NodeFactory创建
    - 节点存储在工作流中
    """

    def test_create_node_from_decision(self):
        """测试：根据决策创建节点

        业务场景：
        - 对话Agent决策创建LLM节点
        - 工作流Agent收到决策后创建节点

        验收标准：
        - 节点被正确创建
        - 节点类型和配置正确
        """
        # Arrange
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry, NodeType

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        agent = WorkflowAgent(workflow_context=workflow_ctx, node_factory=factory)

        decision = {
            "type": "create_node",
            "node_type": "LLM",
            "config": {"model": "gpt-4", "user_prompt": "分析数据"},
        }

        # Act
        node = agent.create_node(decision)

        # Assert
        assert node is not None
        assert node.type == NodeType.LLM
        assert node.config["model"] == "gpt-4"

    def test_add_node_to_workflow(self):
        """测试：将节点添加到工作流

        业务场景：
        - 节点创建后需要添加到工作流
        - 工作流维护节点列表

        验收标准：
        - 节点被添加到工作流
        - 可以通过ID获取节点
        """
        # Arrange
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        agent = WorkflowAgent(workflow_context=workflow_ctx, node_factory=factory)

        # Act
        node = agent.create_node(
            {
                "type": "create_node",
                "node_type": "API",
                "config": {"url": "https://api.example.com"},
            }
        )
        agent.add_node(node)

        # Assert
        assert agent.get_node(node.id) is not None
        assert len(agent.nodes) == 1

    def test_connect_nodes_with_edge(self):
        """测试：用边连接节点

        业务场景：
        - 工作流是DAG图结构
        - 节点通过边连接

        验收标准：
        - 可以创建边连接两个节点
        - 边存储源节点和目标节点
        """
        # Arrange
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        agent = WorkflowAgent(workflow_context=workflow_ctx, node_factory=factory)

        # 创建两个节点
        node1 = agent.create_node({"type": "create_node", "node_type": "START", "config": {}})
        node2 = agent.create_node(
            {"type": "create_node", "node_type": "LLM", "config": {"user_prompt": "test"}}
        )
        agent.add_node(node1)
        agent.add_node(node2)

        # Act
        edge = agent.connect_nodes(node1.id, node2.id)

        # Assert
        assert edge is not None
        assert edge.source_id == node1.id
        assert edge.target_id == node2.id
        assert len(agent.edges) == 1


class TestWorkflowAgentExecution:
    """测试工作流Agent的执行能力

    业务背景：
    - 工作流Agent负责执行工作流
    - 按DAG拓扑顺序执行节点
    - 管理执行状态和结果
    """

    @pytest.mark.asyncio
    async def test_execute_single_node(self):
        """测试：执行单个节点

        业务场景：
        - 工作流只有一个节点
        - 执行该节点并获取结果

        验收标准：
        - 节点被执行
        - 执行结果被存储
        """
        # Arrange
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        # Mock执行器
        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {"result": "执行成功"}

        agent = WorkflowAgent(
            workflow_context=workflow_ctx, node_factory=factory, node_executor=mock_executor
        )

        node = agent.create_node(
            {"type": "create_node", "node_type": "LLM", "config": {"user_prompt": "test"}}
        )
        agent.add_node(node)

        # Act
        result = await agent.execute_node(node.id)

        # Assert
        assert result is not None
        assert result["result"] == "执行成功"

    @pytest.mark.asyncio
    async def test_execute_workflow_in_order(self):
        """测试：按顺序执行工作流

        业务场景：
        - 工作流有多个节点
        - 按拓扑顺序执行

        验收标准：
        - 节点按正确顺序执行
        - 所有节点都被执行
        """
        # Arrange
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        execution_order = []

        async def mock_execute(node_id, config, inputs):
            execution_order.append(node_id)
            return {"status": "success"}

        mock_executor = AsyncMock()
        mock_executor.execute.side_effect = mock_execute

        agent = WorkflowAgent(
            workflow_context=workflow_ctx, node_factory=factory, node_executor=mock_executor
        )

        # 创建三个节点：START → LLM → END
        start = agent.create_node({"type": "create_node", "node_type": "START", "config": {}})
        llm = agent.create_node(
            {"type": "create_node", "node_type": "LLM", "config": {"user_prompt": "test"}}
        )
        end = agent.create_node({"type": "create_node", "node_type": "END", "config": {}})

        agent.add_node(start)
        agent.add_node(llm)
        agent.add_node(end)

        agent.connect_nodes(start.id, llm.id)
        agent.connect_nodes(llm.id, end.id)

        # Act
        await agent.execute_workflow()

        # Assert - START应该先执行，然后是LLM，最后是END
        assert len(execution_order) == 3
        assert execution_order[0] == start.id
        assert execution_order[1] == llm.id
        assert execution_order[2] == end.id

    @pytest.mark.asyncio
    async def test_node_output_passed_to_next_node(self):
        """测试：节点输出传递给下一个节点

        业务场景：
        - API节点获取数据
        - 数据传递给LLM节点分析

        验收标准：
        - 上游节点输出存储到Context
        - 下游节点可以获取上游输出
        """
        # Arrange
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        received_inputs = {}

        async def mock_execute(node_id, config, inputs):
            received_inputs[node_id] = inputs
            if "api" in node_id.lower() or config.get("url"):
                return {"data": [1, 2, 3]}
            return {"analysis": "数据分析完成"}

        mock_executor = AsyncMock()
        mock_executor.execute.side_effect = mock_execute

        agent = WorkflowAgent(
            workflow_context=workflow_ctx, node_factory=factory, node_executor=mock_executor
        )

        # 创建 API → LLM
        api_node = agent.create_node(
            {
                "type": "create_node",
                "node_type": "API",
                "config": {"url": "https://api.example.com"},
            }
        )
        llm_node = agent.create_node(
            {
                "type": "create_node",
                "node_type": "LLM",
                "config": {"user_prompt": "分析数据: {{input}}"},
            }
        )

        agent.add_node(api_node)
        agent.add_node(llm_node)
        agent.connect_nodes(api_node.id, llm_node.id)

        # Act
        await agent.execute_workflow()

        # Assert - LLM节点应该收到API节点的输出
        assert llm_node.id in received_inputs
        # 上游输出应该在inputs中
        assert api_node.id in received_inputs[llm_node.id] or "data" in str(
            received_inputs.get(llm_node.id, {})
        )


class TestWorkflowAgentStateSync:
    """测试工作流Agent的状态同步

    业务背景：
    - 执行状态需要同步到画布
    - 通过事件通知前端更新
    """

    @pytest.mark.asyncio
    async def test_publish_execution_started_event(self):
        """测试：发布执行开始事件

        业务场景：
        - 工作流开始执行
        - 发布事件通知画布更新状态

        验收标准：
        - 执行开始时发布事件
        - 事件包含工作流ID
        """
        # Arrange
        from src.domain.agents.workflow_agent import WorkflowAgent, WorkflowExecutionStartedEvent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.event_bus import EventBus
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        registry = NodeRegistry()
        factory = NodeFactory(registry)
        event_bus = EventBus()

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        received_events = []

        async def capture_event(event):
            received_events.append(event)

        event_bus.subscribe(WorkflowExecutionStartedEvent, capture_event)

        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {"status": "success"}

        agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
            node_executor=mock_executor,
            event_bus=event_bus,
        )

        # 添加一个简单节点
        node = agent.create_node({"type": "create_node", "node_type": "START", "config": {}})
        agent.add_node(node)

        # Act
        await agent.execute_workflow()

        # Assert
        assert len(received_events) >= 1
        assert received_events[0].workflow_id == "workflow_xyz"

    @pytest.mark.asyncio
    async def test_publish_node_execution_event(self):
        """测试：发布节点执行事件

        业务场景：
        - 每个节点执行时发布事件
        - 画布可以高亮当前执行的节点

        验收标准：
        - 节点开始执行时发布事件
        - 事件包含节点ID和状态
        """
        # Arrange
        from src.domain.agents.workflow_agent import NodeExecutionEvent, WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.event_bus import EventBus
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        registry = NodeRegistry()
        factory = NodeFactory(registry)
        event_bus = EventBus()

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        node_events = []

        async def capture_event(event):
            node_events.append(event)

        event_bus.subscribe(NodeExecutionEvent, capture_event)

        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {"status": "success"}

        agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
            node_executor=mock_executor,
            event_bus=event_bus,
        )

        node = agent.create_node(
            {"type": "create_node", "node_type": "LLM", "config": {"user_prompt": "test"}}
        )
        agent.add_node(node)

        # Act
        await agent.execute_node(node.id)

        # Assert
        assert len(node_events) >= 1
        # 应该有开始和完成两个事件
        statuses = [e.status for e in node_events]
        assert "running" in statuses or "completed" in statuses


class TestWorkflowAgentDecisionHandling:
    """测试工作流Agent处理决策

    业务背景：
    - 工作流Agent订阅决策验证事件
    - 收到验证通过的决策后执行相应操作
    """

    @pytest.mark.asyncio
    async def test_handle_validated_create_node_decision(self):
        """测试：处理验证通过的创建节点决策

        业务场景：
        - 协调者验证通过创建节点决策
        - 工作流Agent收到事件后创建节点

        验收标准：
        - 节点被创建
        - 节点添加到工作流
        """
        # Arrange
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry, NodeType

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        agent = WorkflowAgent(workflow_context=workflow_ctx, node_factory=factory)

        # 模拟验证通过的决策
        validated_decision = {
            "decision_type": "create_node",
            "node_type": "LLM",
            "config": {"user_prompt": "分析数据"},
            "is_valid": True,
        }

        # Act
        result = await agent.handle_decision(validated_decision)

        # Assert
        assert result["success"] is True
        assert len(agent.nodes) == 1
        assert agent.nodes[0].type == NodeType.LLM

    @pytest.mark.asyncio
    async def test_handle_execute_workflow_decision(self):
        """测试：处理执行工作流决策

        业务场景：
        - 收到执行工作流的决策
        - Phase 5 起：必须通过 Runs（run_id + WorkflowRunExecutionEntryPort），否则 fail-closed

        验收标准：
        - 缺少 run_id 时不得执行（返回结构化错误）
        """
        # Arrange
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {"status": "success"}

        agent = WorkflowAgent(
            workflow_context=workflow_ctx, node_factory=factory, node_executor=mock_executor
        )

        # 先创建一些节点
        node = agent.create_node({"type": "create_node", "node_type": "START", "config": {}})
        agent.add_node(node)

        # 执行工作流决策
        decision = {"decision_type": "execute_workflow", "workflow_id": "workflow_xyz"}

        # Act
        result = await agent.handle_decision(decision)

        # Assert
        assert result["success"] is False
        assert result["status"] == "failed"
        assert "run_id is required" in str(result.get("error", ""))


class TestWorkflowAgentRealWorldScenario:
    """测试真实业务场景"""

    @pytest.mark.asyncio
    async def test_complete_data_analysis_workflow(self):
        """测试：完整的数据分析工作流执行

        业务场景：
        1. 对话Agent决策创建工作流
        2. 工作流包含：获取数据 → 分析 → 生成报告
        3. 工作流Agent执行整个流程
        4. 结果返回给对话Agent

        这是工作流Agent的核心使用场景！

        验收标准：
        - 所有节点按顺序执行
        - 数据在节点间正确传递
        - 最终结果正确
        """
        # Arrange
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.event_bus import EventBus
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        registry = NodeRegistry()
        factory = NodeFactory(registry)
        event_bus = EventBus()

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        # 模拟各节点的执行结果
        node_results = {}

        async def mock_execute(node_id, config, inputs):
            if "START" in str(config) or config == {}:
                result = {"trigger": "manual"}
            elif config.get("url"):
                result = {"data": {"sales": [100, 200, 300]}}
            elif config.get("user_prompt"):
                result = {"analysis": "销售额稳步增长"}
            else:
                result = {"status": "completed"}

            node_results[node_id] = result
            return result

        mock_executor = AsyncMock()
        mock_executor.execute.side_effect = mock_execute

        agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
            node_executor=mock_executor,
            event_bus=event_bus,
        )

        # 创建工作流节点
        start = agent.create_node({"type": "create_node", "node_type": "START", "config": {}})
        api = agent.create_node(
            {
                "type": "create_node",
                "node_type": "API",
                "config": {"url": "https://api.example.com/sales"},
            }
        )
        llm = agent.create_node(
            {"type": "create_node", "node_type": "LLM", "config": {"user_prompt": "分析销售数据"}}
        )
        end = agent.create_node({"type": "create_node", "node_type": "END", "config": {}})

        # 添加节点
        for node in [start, api, llm, end]:
            agent.add_node(node)

        # 连接节点
        agent.connect_nodes(start.id, api.id)
        agent.connect_nodes(api.id, llm.id)
        agent.connect_nodes(llm.id, end.id)

        # Act
        result = await agent.execute_workflow()

        # Assert
        assert result["status"] == "completed"
        assert len(node_results) == 4
        # 验证数据流转
        assert "data" in node_results[api.id]
        assert "analysis" in node_results[llm.id]
