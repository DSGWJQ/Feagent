"""测试：多Agent协作集成

TDD 第一步：编写集成测试，验证三个Agent的协作机制

业务背景：
- 对话Agent（大脑）负责理解用户意图、做出决策
- 协调者Agent（守门人）负责验证决策合法性
- 工作流Agent（执行者）负责执行验证通过的决策
- 三者通过EventBus进行事件驱动的协作

真实场景：
1. 用户输入 → 对话Agent理解并做出决策
2. 对话Agent发布DecisionMadeEvent
3. 协调者Agent（作为中间件）拦截并验证
4. 验证通过 → 发布DecisionValidatedEvent → 工作流Agent执行
5. 验证失败 → 发布DecisionRejectedEvent → 对话Agent收到反馈

核心协作模式：
- 事件驱动：通过EventBus发布/订阅事件
- 中间件拦截：协调者作为EventBus中间件
- 职责分离：每个Agent只关注自己的职责
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestAgentCollaborationSetup:
    """测试Agent协作系统的基础设置

    业务背景：
    - 三个Agent需要正确连接到同一个EventBus
    - 协调者需要注册为中间件
    - 工作流Agent需要订阅验证事件
    """

    @pytest.mark.asyncio
    async def test_setup_agent_collaboration_system(self):
        """测试：设置Agent协作系统

        业务场景：
        - 创建三个Agent
        - 连接到同一个EventBus
        - 协调者注册为中间件

        验收标准：
        - 所有Agent正确初始化
        - 协调者作为中间件注册
        - 事件可以在Agent间流转
        """
        # Arrange
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.event_bus import EventBus
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        # 创建共享的EventBus
        event_bus = EventBus()

        # 创建上下文
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        # 创建LLM mock
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="ACTION: create_node\nPARAMS: {}")

        # 创建节点工厂
        registry = NodeRegistry()
        factory = NodeFactory(registry)

        # Act - 创建三个Agent
        conversation_agent = ConversationAgent(
            session_context=session_ctx, llm=mock_llm, event_bus=event_bus
        )

        coordinator_agent = CoordinatorAgent(event_bus=event_bus)

        workflow_agent = WorkflowAgent(
            workflow_context=workflow_ctx, node_factory=factory, event_bus=event_bus
        )

        # 注册协调者为中间件
        event_bus.add_middleware(coordinator_agent.as_middleware())

        # Assert
        assert conversation_agent is not None
        assert coordinator_agent is not None
        assert workflow_agent is not None
        assert len(event_bus._middlewares) == 1


class TestDecisionFlowWithValidation:
    """测试决策流经验证的完整流程

    业务背景：
    - 对话Agent发布决策
    - 协调者验证决策
    - 验证结果决定后续处理
    """

    @pytest.mark.asyncio
    async def test_valid_decision_flows_through_system(self):
        """测试：有效决策流经系统

        业务场景：
        1. 对话Agent决策创建LLM节点
        2. 协调者验证通过
        3. 工作流Agent收到验证事件并执行

        验收标准：
        - 决策事件被发布
        - 协调者验证通过
        - 验证事件被发布
        - 工作流Agent收到事件
        """
        # Arrange
        from src.domain.agents.conversation_agent import (
            DecisionMadeEvent,
        )
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            DecisionValidatedEvent,
            Rule,
        )
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.event_bus import EventBus
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        event_bus = EventBus()

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        # 创建协调者并添加规则
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.add_rule(
            Rule(
                id="allow_llm",
                name="允许LLM节点",
                condition=lambda d: d.get("node_type") in ["LLM", "API", "START", "END"],
                error_message="不允许的节点类型",
            )
        )

        # 注册中间件
        event_bus.add_middleware(coordinator.as_middleware())

        # 创建工作流Agent
        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {"status": "success"}

        workflow_agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
            node_executor=mock_executor,
            event_bus=event_bus,
        )

        # 捕获验证事件
        validated_events = []

        async def capture_validated(event):
            validated_events.append(event)
            # 工作流Agent处理验证通过的决策
            await workflow_agent.handle_decision(
                {"decision_type": event.decision_type, **event.payload}
            )

        event_bus.subscribe(DecisionValidatedEvent, capture_validated)

        # Act - 发布决策事件
        decision_event = DecisionMadeEvent(
            source="conversation_agent",
            decision_type="create_node",
            payload={"node_type": "LLM", "config": {"model": "gpt-4", "user_prompt": "分析数据"}},
        )
        await event_bus.publish(decision_event)

        # Assert
        assert len(validated_events) == 1
        assert validated_events[0].decision_type == "create_node"
        assert len(workflow_agent.nodes) == 1

    @pytest.mark.asyncio
    async def test_invalid_decision_is_rejected(self):
        """测试：无效决策被拒绝

        业务场景：
        1. 对话Agent决策创建危险节点
        2. 协调者验证失败
        3. 拒绝事件被发布
        4. 工作流Agent不执行

        验收标准：
        - 决策被拒绝
        - 拒绝事件包含原因
        - 工作流Agent没有创建节点
        """
        # Arrange
        from src.domain.agents.conversation_agent import DecisionMadeEvent
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            DecisionRejectedEvent,
            DecisionValidatedEvent,
            Rule,
        )
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.event_bus import EventBus
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        event_bus = EventBus()

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        # 创建协调者并添加严格规则
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.add_rule(
            Rule(
                id="only_safe_types",
                name="只允许安全节点",
                condition=lambda d: d.get("node_type") in ["START", "END", "LLM"],
                error_message="节点类型不安全",
            )
        )

        event_bus.add_middleware(coordinator.as_middleware())

        workflow_agent = WorkflowAgent(
            workflow_context=workflow_ctx, node_factory=factory, event_bus=event_bus
        )

        # 捕获事件
        rejected_events = []
        validated_events = []

        async def capture_rejected(event):
            rejected_events.append(event)

        async def capture_validated(event):
            validated_events.append(event)

        event_bus.subscribe(DecisionRejectedEvent, capture_rejected)
        event_bus.subscribe(DecisionValidatedEvent, capture_validated)

        # Act - 发布不安全的决策
        decision_event = DecisionMadeEvent(
            source="conversation_agent",
            decision_type="create_node",
            payload={
                "node_type": "DANGEROUS",  # 不在允许列表中
                "config": {},
            },
        )
        await event_bus.publish(decision_event)

        # Assert
        assert len(rejected_events) == 1
        assert "不安全" in rejected_events[0].reason
        assert len(validated_events) == 0
        assert len(workflow_agent.nodes) == 0


class TestConversationToWorkflowCollaboration:
    """测试对话Agent到工作流Agent的完整协作

    业务背景：
    - 用户通过对话Agent表达意图
    - 对话Agent分解目标并做出决策
    - 决策经过协调者验证后由工作流Agent执行
    """

    @pytest.mark.asyncio
    async def test_user_request_creates_workflow(self):
        """测试：用户请求创建工作流

        业务场景：
        用户说："帮我创建一个数据分析工作流"
        1. 对话Agent分解目标
        2. 做出创建节点的决策
        3. 协调者验证
        4. 工作流Agent执行创建

        验收标准：
        - 用户意图被理解
        - 多个节点被创建
        - 节点被正确连接
        """
        # Arrange
        from src.domain.agents.conversation_agent import DecisionMadeEvent
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            DecisionValidatedEvent,
            Rule,
        )
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.event_bus import EventBus
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        event_bus = EventBus()

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        # 配置协调者
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.add_rule(
            Rule(
                id="allow_workflow_nodes",
                name="允许工作流节点",
                condition=lambda d: d.get("node_type")
                in ["START", "END", "LLM", "API", "CONDITION"],
            )
        )
        event_bus.add_middleware(coordinator.as_middleware())

        # 配置工作流Agent
        workflow_agent = WorkflowAgent(
            workflow_context=workflow_ctx, node_factory=factory, event_bus=event_bus
        )

        # 设置事件处理
        async def handle_validated(event):
            await workflow_agent.handle_decision(
                {"decision_type": event.decision_type, **event.payload}
            )

        event_bus.subscribe(DecisionValidatedEvent, handle_validated)

        # 模拟对话Agent发布的一系列决策
        decisions = [
            DecisionMadeEvent(
                source="conversation_agent",
                decision_type="create_node",
                payload={"node_type": "START", "config": {}},
            ),
            DecisionMadeEvent(
                source="conversation_agent",
                decision_type="create_node",
                payload={"node_type": "API", "config": {"url": "https://api.example.com"}},
            ),
            DecisionMadeEvent(
                source="conversation_agent",
                decision_type="create_node",
                payload={"node_type": "LLM", "config": {"user_prompt": "分析数据"}},
            ),
            DecisionMadeEvent(
                source="conversation_agent",
                decision_type="create_node",
                payload={"node_type": "END", "config": {}},
            ),
        ]

        # Act - 发布所有决策
        for decision in decisions:
            await event_bus.publish(decision)

        # Assert
        assert len(workflow_agent.nodes) == 4
        # 验证节点类型
        node_types = [n.type.value for n in workflow_agent.nodes]
        assert "start" in node_types
        assert "api" in node_types
        assert "llm" in node_types
        assert "end" in node_types


class TestFeedbackLoop:
    """测试反馈循环

    业务背景：
    - 当决策被拒绝时，对话Agent需要收到反馈
    - 对话Agent根据反馈调整决策
    """

    @pytest.mark.asyncio
    async def test_conversation_agent_receives_rejection_feedback(self):
        """测试：对话Agent收到拒绝反馈

        业务场景：
        1. 对话Agent发布决策
        2. 协调者拒绝
        3. 对话Agent收到拒绝事件
        4. 对话Agent可以据此调整

        验收标准：
        - 拒绝事件被发布
        - 包含拒绝原因
        - 对话Agent可以订阅并处理
        """
        # Arrange
        from src.domain.agents.conversation_agent import ConversationAgent, DecisionMadeEvent
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            DecisionRejectedEvent,
            Rule,
        )
        from src.domain.services.context_manager import GlobalContext, SessionContext
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        # Mock LLM
        mock_llm = MagicMock()

        # 创建对话Agent
        conversation_agent = ConversationAgent(
            session_context=session_ctx, llm=mock_llm, event_bus=event_bus
        )

        # 创建协调者
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.add_rule(
            Rule(
                id="deny_code",
                name="禁止代码节点",
                condition=lambda d: d.get("node_type") != "CODE",
                error_message="代码节点被禁止",
            )
        )
        event_bus.add_middleware(coordinator.as_middleware())

        # 对话Agent订阅拒绝事件
        rejection_feedback = []

        async def handle_rejection(event):
            rejection_feedback.append(
                {"decision_id": event.original_decision_id, "reason": event.reason}
            )

        event_bus.subscribe(DecisionRejectedEvent, handle_rejection)

        # Act - 发布会被拒绝的决策
        decision_event = DecisionMadeEvent(
            source="conversation_agent",
            decision_type="create_node",
            payload={"node_type": "CODE", "config": {"code": "print('hello')"}},
        )
        await event_bus.publish(decision_event)

        # Assert
        assert len(rejection_feedback) == 1
        assert "禁止" in rejection_feedback[0]["reason"]


class TestCollaborativeWorkflowExecution:
    """测试协作工作流执行

    业务背景：
    - 对话Agent发起工作流执行
    - 工作流Agent执行并汇报状态
    - 执行状态通过事件同步
    """

    @pytest.mark.asyncio
    async def test_execute_workflow_with_status_updates(self):
        """测试：执行工作流并更新状态

        业务场景：
        1. 对话Agent决策执行工作流
        2. 协调者验证通过
        3. 工作流Agent执行
        4. 执行状态事件被发布

        验收标准：
        - 工作流开始执行
        - 节点执行事件被发布
        - 工作流完成事件被发布
        """
        # Arrange
        from src.domain.agents.conversation_agent import DecisionMadeEvent
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            DecisionValidatedEvent,
            Rule,
        )
        from src.domain.agents.workflow_agent import (
            NodeExecutionEvent,
            WorkflowAgent,
            WorkflowExecutionCompletedEvent,
            WorkflowExecutionStartedEvent,
        )
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.event_bus import EventBus
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        event_bus = EventBus()

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        # 协调者
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.add_rule(Rule(id="allow_all", name="允许所有", condition=lambda d: True))
        event_bus.add_middleware(coordinator.as_middleware())

        # 工作流Agent
        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {"result": "success"}

        workflow_agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
            node_executor=mock_executor,
            event_bus=event_bus,
        )

        # 预先创建一些节点
        start = workflow_agent.create_node({"node_type": "START", "config": {}})
        llm = workflow_agent.create_node({"node_type": "LLM", "config": {"user_prompt": "test"}})
        end = workflow_agent.create_node({"node_type": "END", "config": {}})

        workflow_agent.add_node(start)
        workflow_agent.add_node(llm)
        workflow_agent.add_node(end)

        workflow_agent.connect_nodes(start.id, llm.id)
        workflow_agent.connect_nodes(llm.id, end.id)

        # 捕获执行事件
        execution_events = []

        async def capture_events(event):
            execution_events.append(event)

        event_bus.subscribe(WorkflowExecutionStartedEvent, capture_events)
        event_bus.subscribe(WorkflowExecutionCompletedEvent, capture_events)
        event_bus.subscribe(NodeExecutionEvent, capture_events)

        # 处理验证事件
        async def handle_validated(event):
            if event.decision_type == "execute_workflow":
                await workflow_agent.execute_workflow()

        event_bus.subscribe(DecisionValidatedEvent, handle_validated)

        # Act - 发布执行工作流的决策
        execute_decision = DecisionMadeEvent(
            source="conversation_agent",
            decision_type="execute_workflow",
            payload={"workflow_id": "workflow_xyz"},
        )
        await event_bus.publish(execute_decision)

        # Assert
        # 应该有：1个开始事件 + 6个节点事件(每个节点2个:running+completed) + 1个完成事件
        assert len(execution_events) >= 3  # 至少有开始、节点执行、完成

        # 验证事件类型
        event_types = [type(e).__name__ for e in execution_events]
        assert "WorkflowExecutionStartedEvent" in event_types
        assert "WorkflowExecutionCompletedEvent" in event_types


class TestRealWorldScenario:
    """测试真实业务场景"""

    @pytest.mark.asyncio
    async def test_complete_user_interaction_flow(self):
        """测试：完整的用户交互流程

        业务场景：
        模拟用户与系统的完整交互：
        1. 用户说"帮我分析这份销售数据"
        2. 对话Agent理解意图，分解为子目标
        3. 对话Agent依次做出决策（创建节点）
        4. 协调者验证每个决策
        5. 工作流Agent执行创建
        6. 对话Agent决策执行工作流
        7. 工作流Agent执行并返回结果
        8. 结果反馈给用户

        这是多Agent协作系统的核心使用场景！

        验收标准：
        - 完整流程正常工作
        - 各Agent职责清晰
        - 事件正确流转
        - 最终结果正确
        """
        # Arrange
        from src.domain.agents.conversation_agent import DecisionMadeEvent
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            DecisionRejectedEvent,
            DecisionValidatedEvent,
            Rule,
        )
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.event_bus import EventBus
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        # 创建共享的EventBus
        event_bus = EventBus()

        # 创建上下文层级
        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        # 创建节点工厂
        registry = NodeRegistry()
        factory = NodeFactory(registry)

        # === 配置协调者Agent ===
        coordinator = CoordinatorAgent(event_bus=event_bus)

        # 添加业务规则
        coordinator.add_rule(
            Rule(
                id="allowed_node_types",
                name="允许的节点类型",
                condition=lambda d: (
                    # 只对create_node决策检查node_type
                    d.get("type") != "create_node" and d.get("node_type") is None
                )
                or d.get("node_type") in ["START", "END", "LLM", "API", "CONDITION", "LOOP", None],
                error_message="不支持的节点类型",
                priority=1,
            )
        )

        coordinator.add_rule(
            Rule(
                id="require_config",
                name="LLM节点需要配置",
                condition=lambda d: (
                    d.get("node_type") != "LLM"
                    or d.get("config", {}).get("user_prompt") is not None
                ),
                error_message="LLM节点必须提供user_prompt",
                priority=2,
            )
        )

        # 注册为中间件
        event_bus.add_middleware(coordinator.as_middleware())

        # === 配置工作流Agent ===
        execution_log = []

        async def mock_execute(node_id, config, inputs):
            execution_log.append({"node_id": node_id, "config": config})
            if config.get("url"):
                return {"data": {"sales": [100, 200, 300]}}
            elif config.get("user_prompt"):
                return {"analysis": "销售额稳步增长，建议继续当前策略"}
            return {"status": "completed"}

        mock_executor = AsyncMock()
        mock_executor.execute.side_effect = mock_execute

        workflow_agent = WorkflowAgent(
            workflow_context=workflow_ctx,
            node_factory=factory,
            node_executor=mock_executor,
            event_bus=event_bus,
        )

        # === 设置事件订阅 ===
        created_nodes = []

        async def handle_validated(event):
            if event.decision_type == "create_node":
                result = await workflow_agent.handle_decision(
                    {"decision_type": event.decision_type, **event.payload}
                )
                if result.get("node_id"):
                    created_nodes.append(result["node_id"])
            elif event.decision_type == "connect_nodes":
                await workflow_agent.handle_decision(
                    {"decision_type": event.decision_type, **event.payload}
                )
            elif event.decision_type == "execute_workflow":
                await workflow_agent.handle_decision(
                    {"decision_type": event.decision_type, **event.payload}
                )

        event_bus.subscribe(DecisionValidatedEvent, handle_validated)

        rejected_decisions = []

        async def handle_rejected(event):
            rejected_decisions.append(event)

        event_bus.subscribe(DecisionRejectedEvent, handle_rejected)

        # === Act: 模拟用户交互流程 ===

        # 1. 创建START节点
        await event_bus.publish(
            DecisionMadeEvent(
                source="conversation_agent",
                decision_type="create_node",
                payload={"node_type": "START", "config": {}},
            )
        )

        # 2. 创建API节点（获取数据）
        await event_bus.publish(
            DecisionMadeEvent(
                source="conversation_agent",
                decision_type="create_node",
                payload={"node_type": "API", "config": {"url": "https://api.example.com/sales"}},
            )
        )

        # 3. 创建LLM节点（分析数据）
        await event_bus.publish(
            DecisionMadeEvent(
                source="conversation_agent",
                decision_type="create_node",
                payload={"node_type": "LLM", "config": {"user_prompt": "分析销售数据并给出建议"}},
            )
        )

        # 4. 创建END节点
        await event_bus.publish(
            DecisionMadeEvent(
                source="conversation_agent",
                decision_type="create_node",
                payload={"node_type": "END", "config": {}},
            )
        )

        # 5. 连接节点
        if len(created_nodes) == 4:
            for i in range(len(created_nodes) - 1):
                await event_bus.publish(
                    DecisionMadeEvent(
                        source="conversation_agent",
                        decision_type="connect_nodes",
                        payload={"source_id": created_nodes[i], "target_id": created_nodes[i + 1]},
                    )
                )

        # 6. 执行工作流
        await event_bus.publish(
            DecisionMadeEvent(
                source="conversation_agent",
                decision_type="execute_workflow",
                payload={"workflow_id": "workflow_xyz"},
            )
        )

        # === Assert ===

        # 验证节点创建
        assert len(workflow_agent.nodes) == 4, "应该创建4个节点"

        # 验证节点连接
        assert len(workflow_agent.edges) == 3, "应该有3条边"

        # 验证执行日志
        assert len(execution_log) == 4, "应该执行4个节点"

        # 验证没有拒绝
        assert len(rejected_decisions) == 0, "不应该有被拒绝的决策"

        # 验证协调者统计
        stats = coordinator.get_statistics()
        assert stats["total"] == 8  # 4个create_node + 3个connect_nodes + 1个execute_workflow
        assert stats["passed"] == 8
        assert stats["rejected"] == 0

    @pytest.mark.asyncio
    async def test_decision_rejection_and_retry(self):
        """测试：决策被拒绝后重试

        业务场景：
        1. 对话Agent发布不完整的决策
        2. 协调者拒绝
        3. 对话Agent收到反馈
        4. 对话Agent修正决策后重试
        5. 决策通过

        验收标准：
        - 第一次决策被拒绝
        - 收到明确的错误信息
        - 修正后的决策通过
        """
        # Arrange
        from src.domain.agents.conversation_agent import DecisionMadeEvent
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            DecisionRejectedEvent,
            DecisionValidatedEvent,
            Rule,
        )
        from src.domain.agents.workflow_agent import WorkflowAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.event_bus import EventBus
        from src.domain.services.node_registry import NodeFactory, NodeRegistry

        event_bus = EventBus()

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        # 协调者：要求LLM节点必须有user_prompt
        coordinator = CoordinatorAgent(event_bus=event_bus)
        coordinator.add_rule(
            Rule(
                id="llm_must_have_prompt",
                name="LLM必须有提示",
                condition=lambda d: (
                    d.get("node_type") != "LLM" or bool(d.get("config", {}).get("user_prompt"))
                ),
                error_message="LLM节点必须提供user_prompt配置",
            )
        )
        event_bus.add_middleware(coordinator.as_middleware())

        workflow_agent = WorkflowAgent(
            workflow_context=workflow_ctx, node_factory=factory, event_bus=event_bus
        )

        # 事件捕获
        validated = []
        rejected = []

        async def on_validated(event):
            validated.append(event)
            await workflow_agent.handle_decision(
                {"decision_type": event.decision_type, **event.payload}
            )

        async def on_rejected(event):
            rejected.append(event)

        event_bus.subscribe(DecisionValidatedEvent, on_validated)
        event_bus.subscribe(DecisionRejectedEvent, on_rejected)

        # Act 1: 发布不完整的决策（缺少user_prompt）
        await event_bus.publish(
            DecisionMadeEvent(
                source="conversation_agent",
                decision_type="create_node",
                payload={"node_type": "LLM", "config": {}},  # 缺少user_prompt
            )
        )

        # Assert 1: 应该被拒绝
        assert len(rejected) == 1
        assert "user_prompt" in rejected[0].reason
        assert len(workflow_agent.nodes) == 0

        # Act 2: 修正后重试
        await event_bus.publish(
            DecisionMadeEvent(
                source="conversation_agent",
                decision_type="create_node",
                payload={
                    "node_type": "LLM",
                    "config": {"user_prompt": "分析数据"},  # 添加了user_prompt
                },
            )
        )

        # Assert 2: 应该通过
        assert len(validated) == 1
        assert len(workflow_agent.nodes) == 1
