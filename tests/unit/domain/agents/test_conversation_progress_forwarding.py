"""测试：ConversationAgent 进度转发 - Phase 8.4 TDD Red 阶段

测试目标：
1. ConversationAgent 订阅 ExecutionProgressEvent
2. ConversationAgent 将进度事件转发给流式输出接口
3. 支持 WebSocket/SSE 推送进度信息
4. 进度信息格式化为用户可读的消息

完成标准：
- 所有测试初始失败（Red阶段）
- 实现代码后所有测试通过（Green阶段）
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestConversationAgentSubscribeProgressEvents:
    """测试 ConversationAgent 订阅进度事件"""

    @pytest.fixture
    def mock_llm(self):
        """创建 Mock LLM"""
        llm = MagicMock()
        llm.think = AsyncMock(return_value="思考内容")
        llm.decide_action = AsyncMock(return_value={"action_type": "respond"})
        return llm

    @pytest.fixture
    def mock_session_context(self):
        """创建 Mock SessionContext"""
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        return SessionContext(session_id="session_001", global_context=global_ctx)

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock()
        event_bus.subscribe = MagicMock()
        event_bus.publish = AsyncMock()
        return event_bus

    def test_conversation_agent_can_start_progress_listener(
        self, mock_session_context, mock_llm, mock_event_bus
    ):
        """ConversationAgent 可以启动进度事件监听器

        场景：初始化 ConversationAgent 并启动监听器
        期望：订阅 ExecutionProgressEvent
        """
        from src.domain.agents.conversation_agent import ConversationAgent

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
            event_bus=mock_event_bus,
        )

        agent.start_progress_event_listener()

        # 验证订阅了 ExecutionProgressEvent
        mock_event_bus.subscribe.assert_called()

    def test_conversation_agent_receives_progress_events(
        self, mock_session_context, mock_llm, mock_event_bus
    ):
        """ConversationAgent 应能接收进度事件

        场景：WorkflowAgent 发布进度事件
        期望：ConversationAgent 的处理器被调用
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.workflow_agent import ExecutionProgressEvent

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
            event_bus=mock_event_bus,
        )

        agent.start_progress_event_listener()

        # 创建进度事件
        event = ExecutionProgressEvent(
            workflow_id="workflow_001",
            node_id="node_1",
            status="running",
            progress=0.5,
            message="正在执行节点",
        )

        # 处理事件
        agent.handle_progress_event(event)

        # 验证事件被记录
        assert hasattr(agent, "progress_events")
        assert len(agent.progress_events) > 0


class TestProgressEventForwarding:
    """测试进度事件转发"""

    @pytest.fixture
    def mock_llm(self):
        """创建 Mock LLM"""
        llm = MagicMock()
        llm.think = AsyncMock(return_value="思考内容")
        llm.decide_action = AsyncMock(return_value={"action_type": "respond"})
        return llm

    @pytest.fixture
    def mock_session_context(self):
        """创建 Mock SessionContext"""
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        return SessionContext(session_id="session_001", global_context=global_ctx)

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock()
        event_bus.subscribe = MagicMock()
        event_bus.publish = AsyncMock()
        return event_bus

    @pytest.fixture
    def mock_stream_emitter(self):
        """创建 Mock StreamEmitter"""
        emitter = MagicMock()
        emitter.emit = AsyncMock()
        return emitter

    @pytest.mark.asyncio
    async def test_forward_progress_event_to_stream_emitter(
        self, mock_session_context, mock_llm, mock_event_bus, mock_stream_emitter
    ):
        """进度事件应转发到流式输出器

        场景：ConversationAgent 收到进度事件
        期望：通过 StreamEmitter 推送给用户
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.workflow_agent import ExecutionProgressEvent

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
            event_bus=mock_event_bus,
            stream_emitter=mock_stream_emitter,
        )

        event = ExecutionProgressEvent(
            workflow_id="workflow_001",
            node_id="node_1",
            status="running",
            progress=0.5,
            message="正在执行节点",
        )

        await agent.forward_progress_event(event)

        # 验证调用了 emit
        mock_stream_emitter.emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_format_progress_event_message(
        self, mock_session_context, mock_llm, mock_event_bus
    ):
        """进度事件应格式化为用户可读消息

        场景：将进度事件转换为友好的消息
        期望：包含节点名称、状态、进度百分比
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.workflow_agent import ExecutionProgressEvent

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
            event_bus=mock_event_bus,
        )

        event = ExecutionProgressEvent(
            workflow_id="workflow_001",
            node_id="node_1",
            status="running",
            progress=0.5,
            message="正在执行HTTP请求",
        )

        formatted_message = agent.format_progress_message(event)

        assert "node_1" in formatted_message or "HTTP" in formatted_message
        assert "50%" in formatted_message or "0.5" in formatted_message


class TestProgressMessageFormatting:
    """测试进度消息格式化"""

    @pytest.fixture
    def mock_llm(self):
        """创建 Mock LLM"""
        llm = MagicMock()
        llm.think = AsyncMock(return_value="思考内容")
        return llm

    @pytest.fixture
    def mock_session_context(self):
        """创建 Mock SessionContext"""
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        return SessionContext(session_id="session_001", global_context=global_ctx)

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock()
        event_bus.subscribe = MagicMock()
        event_bus.publish = AsyncMock()
        return event_bus

    def test_format_started_progress_message(self, mock_session_context, mock_llm, mock_event_bus):
        """格式化"开始执行"进度消息

        场景：节点开始执行
        期望：消息包含"开始"、节点名称
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.workflow_agent import ExecutionProgressEvent

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
            event_bus=mock_event_bus,
        )

        event = ExecutionProgressEvent(
            workflow_id="workflow_001",
            node_id="fetch_data",
            status="started",
            progress=0.0,
            message="开始获取数据",
        )

        formatted = agent.format_progress_message(event)

        assert "开始" in formatted or "started" in formatted.lower()
        assert "fetch_data" in formatted or "获取数据" in formatted

    def test_format_completed_progress_message(
        self, mock_session_context, mock_llm, mock_event_bus
    ):
        """格式化"完成执行"进度消息

        场景：节点执行完成
        期望：消息包含"完成"、节点名称、100%
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.workflow_agent import ExecutionProgressEvent

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
            event_bus=mock_event_bus,
        )

        event = ExecutionProgressEvent(
            workflow_id="workflow_001",
            node_id="analyze_data",
            status="completed",
            progress=1.0,
            message="数据分析完成",
        )

        formatted = agent.format_progress_message(event)

        assert "完成" in formatted or "completed" in formatted.lower()
        assert "100%" in formatted or "1.0" in formatted

    def test_format_failed_progress_message(self, mock_session_context, mock_llm, mock_event_bus):
        """格式化"执行失败"进度消息

        场景：节点执行失败
        期望：消息包含"失败"、错误信息
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.workflow_agent import ExecutionProgressEvent

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
            event_bus=mock_event_bus,
        )

        event = ExecutionProgressEvent(
            workflow_id="workflow_001",
            node_id="send_request",
            status="failed",
            progress=0.5,
            message="HTTP请求超时",
        )

        formatted = agent.format_progress_message(event)

        assert "失败" in formatted or "failed" in formatted.lower()
        assert "超时" in formatted or "timeout" in formatted.lower()


class TestProgressEventHistory:
    """测试进度事件历史记录"""

    @pytest.fixture
    def mock_llm(self):
        """创建 Mock LLM"""
        llm = MagicMock()
        llm.think = AsyncMock(return_value="思考内容")
        return llm

    @pytest.fixture
    def mock_session_context(self):
        """创建 Mock SessionContext"""
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        return SessionContext(session_id="session_001", global_context=global_ctx)

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock()
        event_bus.subscribe = MagicMock()
        event_bus.publish = AsyncMock()
        return event_bus

    def test_agent_stores_progress_event_history(
        self, mock_session_context, mock_llm, mock_event_bus
    ):
        """Agent 应存储进度事件历史

        场景：收到多个进度事件
        期望：所有事件都被记录
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.workflow_agent import ExecutionProgressEvent

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
            event_bus=mock_event_bus,
        )

        # 创建多个事件
        events = [
            ExecutionProgressEvent(
                workflow_id="workflow_001",
                node_id=f"node_{i}",
                status="completed",
                progress=1.0,
                message=f"节点{i}完成",
            )
            for i in range(1, 4)
        ]

        # 处理事件
        for event in events:
            agent.handle_progress_event(event)

        # 验证历史记录
        assert len(agent.progress_events) == 3

    def test_get_progress_events_by_workflow_id(
        self, mock_session_context, mock_llm, mock_event_bus
    ):
        """可以按 workflow_id 查询进度事件

        场景：有多个工作流的进度事件
        期望：能够过滤特定工作流的事件
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.workflow_agent import ExecutionProgressEvent

        agent = ConversationAgent(
            session_context=mock_session_context,
            llm=mock_llm,
            event_bus=mock_event_bus,
        )

        # 添加不同工作流的事件
        agent.handle_progress_event(
            ExecutionProgressEvent(
                workflow_id="workflow_001",
                node_id="node_1",
                status="completed",
                progress=1.0,
                message="完成",
            )
        )

        agent.handle_progress_event(
            ExecutionProgressEvent(
                workflow_id="workflow_002",
                node_id="node_2",
                status="completed",
                progress=1.0,
                message="完成",
            )
        )

        # 查询特定工作流的事件
        workflow_001_events = agent.get_progress_events_by_workflow("workflow_001")

        assert len(workflow_001_events) == 1
        assert workflow_001_events[0].workflow_id == "workflow_001"


# 导出
__all__ = [
    "TestConversationAgentSubscribeProgressEvents",
    "TestProgressEventForwarding",
    "TestProgressMessageFormatting",
    "TestProgressEventHistory",
]
