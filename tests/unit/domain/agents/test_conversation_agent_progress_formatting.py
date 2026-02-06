"""ConversationAgent 进度格式化测试

目标：补充进度事件格式化方法的测试覆盖
覆盖代码：conversation_agent.py:862, 841, 890行
新增测试：3个

测试场景：
1. SSE格式化
2. 按工作流ID查询进度事件
"""

from unittest.mock import AsyncMock, Mock

import pytest

from src.domain.agents.conversation_agent import ConversationAgent
from src.domain.entities.session_context import GlobalContext, SessionContext
from src.domain.services.event_bus import EventBus


@pytest.fixture
def global_context():
    """Global context"""
    return GlobalContext(user_id="test_user")


@pytest.fixture
def session_context(global_context):
    """Session context"""
    return SessionContext(
        session_id="test_session",
        global_context=global_context,
    )


@pytest.fixture
def mock_llm():
    """Mock LLM"""
    llm = AsyncMock()
    llm.think = AsyncMock(return_value="思考")
    llm.decide_action = AsyncMock(return_value={"action": "finish"})
    return llm


@pytest.fixture
def event_bus():
    """Event bus"""
    return EventBus()


@pytest.fixture
def agent_with_event_bus(session_context, mock_llm, event_bus):
    """Agent with EventBus enabled"""
    agent = ConversationAgent(
        session_context=session_context,
        llm=mock_llm,
        event_bus=event_bus,
    )
    return agent


@pytest.fixture
def mock_progress_event():
    """Mock ExecutionProgressEvent"""
    event = Mock()
    event.workflow_id = "workflow_123"
    event.node_id = "node_456"
    event.status = "running"
    event.progress = 0.5
    event.message = "Processing data..."
    return event


# ============================================================================
# Test: 进度格式化
# ============================================================================


class TestProgressFormatting:
    """测试进度格式化"""

    def test_format_progress_for_sse_returns_sse_format(
        self, agent_with_event_bus, mock_progress_event
    ):
        """测试：format_progress_for_sse返回SSE格式（覆盖862, 876行）"""
        agent = agent_with_event_bus

        # 调用格式化方法
        sse_message = agent.format_progress_for_sse(mock_progress_event)

        # 验证返回SSE格式字符串
        assert isinstance(sse_message, str)
        assert sse_message.startswith("data: ")
        assert sse_message.endswith("\n\n")

        # 验证JSON内容
        import json

        json_str = sse_message.replace("data: ", "").replace("\n\n", "")
        data = json.loads(json_str)

        assert data["workflow_id"] == "workflow_123"
        assert data["node_id"] == "node_456"
        assert data["status"] == "running"
        assert data["progress"] == 0.5
        assert data["message"] == "Processing data..."

    def test_format_progress_for_sse_handles_special_characters(self, agent_with_event_bus):
        """测试：format_progress_for_sse处理特殊字符"""
        agent = agent_with_event_bus

        # 创建包含特殊字符的事件
        event = Mock()
        event.workflow_id = "workflow_中文"
        event.node_id = "node_<script>"
        event.status = "完成"
        event.progress = 1.0
        event.message = 'Message with "quotes" and\nnewlines'

        sse_message = agent.format_progress_for_sse(event)

        # 验证能正确JSON序列化
        import json

        json_str = sse_message.replace("data: ", "").replace("\n\n", "")
        data = json.loads(json_str)  # 不抛异常说明JSON有效

        assert data["workflow_id"] == "workflow_中文"
        assert '"quotes"' in data["message"]

    def test_get_progress_events_by_workflow_filters_correctly(self, agent_with_event_bus):
        """测试：get_progress_events_by_workflow正确过滤（覆盖890行）"""
        agent = agent_with_event_bus

        # 创建多个进度事件
        event1 = Mock()
        event1.workflow_id = "workflow_A"
        event1.node_id = "node_1"

        event2 = Mock()
        event2.workflow_id = "workflow_B"
        event2.node_id = "node_2"

        event3 = Mock()
        event3.workflow_id = "workflow_A"
        event3.node_id = "node_3"

        # 没有workflow_id属性的事件
        event4 = Mock(spec=[])  # 没有workflow_id

        # 添加到progress_events
        agent.progress_events = [event1, event2, event3, event4]

        # 查询workflow_A的事件
        events_a = agent.get_progress_events_by_workflow("workflow_A")

        # 验证过滤结果（覆盖890行：hasattr检查和workflow_id匹配）
        assert len(events_a) == 2
        assert event1 in events_a
        assert event3 in events_a
        assert event2 not in events_a
        assert event4 not in events_a  # 没有workflow_id属性的事件被过滤

    def test_get_progress_events_by_workflow_returns_empty_list(self, agent_with_event_bus):
        """测试：get_progress_events_by_workflow无匹配时返回空列表"""
        agent = agent_with_event_bus

        event = Mock()
        event.workflow_id = "workflow_X"

        agent.progress_events = [event]

        # 查询不存在的workflow
        events = agent.get_progress_events_by_workflow("workflow_Y")

        assert events == []

    def test_get_progress_events_by_workflow_handles_empty_list(self, agent_with_event_bus):
        """测试：get_progress_events_by_workflow处理空事件列表"""
        agent = agent_with_event_bus

        agent.progress_events = []

        events = agent.get_progress_events_by_workflow("any_workflow")

        assert events == []


# 导出测试类
__all__ = [
    "TestProgressFormatting",
]
