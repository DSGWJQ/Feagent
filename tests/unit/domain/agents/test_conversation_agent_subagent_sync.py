"""ConversationAgent 同步SubAgent生成测试

目标：补充request_subagent_spawn同步版本的测试覆盖
覆盖代码：conversation_agent.py:649, 696行
新增测试：3个

测试场景：
1. 基础同步生成子Agent
2. 带上下文快照生成
3. wait_for_result参数测试
"""

from unittest.mock import AsyncMock, patch

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


# ============================================================================
# Test: 同步SubAgent生成
# ============================================================================


class TestSyncSubAgentSpawn:
    """测试同步SubAgent生成"""

    def test_request_subagent_spawn_sync_basic(self, agent_with_event_bus):
        """测试：request_subagent_spawn基础同步生成"""
        agent = agent_with_event_bus

        # Mock _publish_notification_event和wait_for_subagent
        with patch.object(agent, "_publish_notification_event") as mock_publish:
            with patch.object(agent, "wait_for_subagent") as mock_wait:
                subagent_id = agent.request_subagent_spawn(
                    subagent_type="data_analyzer",
                    task_payload={"query": "analyze sales data"},
                    priority=1,
                    wait_for_result=True,
                )

                # 验证返回了subagent_id
                assert subagent_id is not None
                assert isinstance(subagent_id, str)
                assert subagent_id.startswith("subagent_")

                # 验证发布了通知事件
                mock_publish.assert_called_once()

                # 验证调用了wait_for_subagent（因为wait_for_result=True）
                mock_wait.assert_called_once()

    def test_request_subagent_spawn_sync_with_context_snapshot(self, agent_with_event_bus):
        """测试：request_subagent_spawn使用上下文快照（覆盖649行）"""
        agent = agent_with_event_bus

        context_snapshot = {
            "user_id": "user_123",
            "session_history": ["msg1", "msg2"],
            "current_state": "analyzing",
        }

        with patch.object(agent, "_publish_notification_event") as mock_publish:
            with patch.object(agent, "wait_for_subagent"):
                agent.request_subagent_spawn(
                    subagent_type="task_executor",
                    task_payload={"task": "execute workflow"},
                    context_snapshot=context_snapshot,
                )

                # 验证_publish_notification_event被调用
                mock_publish.assert_called_once()

                # 获取调用参数中的event对象
                call_args = mock_publish.call_args[0][0]

                # 验证context_snapshot被正确传递（覆盖649行）
                assert hasattr(call_args, "context_snapshot")
                assert call_args.context_snapshot == context_snapshot

    def test_request_subagent_spawn_sync_no_context_uses_empty_dict(self, agent_with_event_bus):
        """测试：request_subagent_spawn无上下文时使用空字典（覆盖649行）"""
        agent = agent_with_event_bus

        with patch.object(agent, "_publish_notification_event") as mock_publish:
            with patch.object(agent, "wait_for_subagent"):
                # 不传context_snapshot
                agent.request_subagent_spawn(
                    subagent_type="helper_agent",
                    task_payload={"task": "help"},
                    context_snapshot=None,  # 明确传None
                )

                # 获取调用参数
                call_args = mock_publish.call_args[0][0]

                # 验证使用了空字典（context_snapshot or {}）
                assert call_args.context_snapshot == {}

    def test_request_subagent_spawn_sync_waits_for_result(self, agent_with_event_bus):
        """测试：request_subagent_spawn的wait_for_result参数（覆盖696行）"""
        agent = agent_with_event_bus

        with patch.object(agent, "_publish_notification_event"):
            with patch.object(agent, "wait_for_subagent") as mock_wait:
                # wait_for_result=True（默认）
                agent.request_subagent_spawn(
                    subagent_type="worker",
                    task_payload={"job": "process"},
                    wait_for_result=True,
                )

                # 验证调用了wait_for_subagent（覆盖694-699行）
                mock_wait.assert_called_once()

                # 验证传递了正确的参数
                call_kwargs = mock_wait.call_args[1]
                assert "subagent_id" in call_kwargs
                assert "task_id" in call_kwargs
                assert "context" in call_kwargs

    def test_request_subagent_spawn_sync_no_wait(self, agent_with_event_bus):
        """测试：request_subagent_spawn的wait_for_result=False"""
        agent = agent_with_event_bus

        with patch.object(agent, "_publish_notification_event"):
            with patch.object(agent, "wait_for_subagent") as mock_wait:
                # wait_for_result=False
                agent.request_subagent_spawn(
                    subagent_type="fire_and_forget",
                    task_payload={"task": "background"},
                    wait_for_result=False,
                )

                # 验证未调用wait_for_subagent
                mock_wait.assert_not_called()

    def test_request_subagent_spawn_generates_unique_ids(self, agent_with_event_bus):
        """测试：request_subagent_spawn生成唯一ID"""
        agent = agent_with_event_bus

        with patch.object(agent, "_publish_notification_event"):
            with patch.object(agent, "wait_for_subagent"):
                # 生成多个subagent
                id1 = agent.request_subagent_spawn(
                    subagent_type="agent1",
                    task_payload={},
                    wait_for_result=False,
                )
                id2 = agent.request_subagent_spawn(
                    subagent_type="agent2",
                    task_payload={},
                    wait_for_result=False,
                )
                id3 = agent.request_subagent_spawn(
                    subagent_type="agent3",
                    task_payload={},
                    wait_for_result=False,
                )

                # 验证ID唯一性
                assert id1 != id2
                assert id2 != id3
                assert id1 != id3


# 导出测试类
__all__ = [
    "TestSyncSubAgentSpawn",
]
