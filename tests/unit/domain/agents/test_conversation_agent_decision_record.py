"""ConversationAgent 决策记录暂存测试

目标：补充决策记录暂存机制的测试覆盖
覆盖代码：conversation_agent.py:383, 421-423行
新增测试：2个

测试场景：
1. 暂存决策记录
2. 批量刷新决策记录到SessionContext
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
# Test: 决策记录暂存
# ============================================================================


class TestDecisionRecordStaging:
    """测试决策记录暂存机制"""

    def test_stage_decision_record_appends_to_list(self, agent_with_event_bus):
        """测试：_stage_decision_record追加到列表（覆盖383行）"""
        agent = agent_with_event_bus

        # 初始状态：空列表
        assert len(agent._staged_decision_records) == 0

        # 暂存第一条决策记录
        record1 = {
            "action": "spawn_subagent",
            "reasoning": "需要数据分析",
            "confidence": 0.9,
        }
        agent._stage_decision_record(record1)

        # 验证追加到列表（覆盖383行）
        assert len(agent._staged_decision_records) == 1
        assert agent._staged_decision_records[0] == record1

        # 暂存第二条决策记录
        record2 = {
            "action": "respond",
            "reasoning": "任务完成",
            "confidence": 0.95,
        }
        agent._stage_decision_record(record2)

        # 验证继续追加
        assert len(agent._staged_decision_records) == 2
        assert agent._staged_decision_records[0] == record1
        assert agent._staged_decision_records[1] == record2

        # 暂存第三条
        record3 = {"action": "think", "reasoning": "需要深入思考"}
        agent._stage_decision_record(record3)

        assert len(agent._staged_decision_records) == 3

    @pytest.mark.asyncio
    async def test_flush_staged_state_flushes_decision_records(self, agent_with_event_bus):
        """测试：_flush_staged_state批量刷新决策记录（覆盖421-423行）"""
        agent = agent_with_event_bus

        # 暂存多条决策记录
        record1 = {"action": "action1", "data": "data1"}
        record2 = {"action": "action2", "data": "data2"}
        record3 = {"action": "action3", "data": "data3"}

        agent._stage_decision_record(record1)
        agent._stage_decision_record(record2)
        agent._stage_decision_record(record3)

        assert len(agent._staged_decision_records) == 3

        # Mock session_context.add_decision
        with patch.object(agent.session_context, "add_decision") as mock_add_decision:
            await agent._flush_staged_state()

            # 验证每条记录都调用了add_decision（覆盖421-422行）
            assert mock_add_decision.call_count == 3

            # 验证调用参数正确
            calls = mock_add_decision.call_args_list
            assert calls[0][0][0] == record1
            assert calls[1][0][0] == record2
            assert calls[2][0][0] == record3

            # 验证列表被清空（覆盖423行）
            assert len(agent._staged_decision_records) == 0

    @pytest.mark.asyncio
    async def test_flush_staged_state_handles_only_decision_records(self, agent_with_event_bus):
        """测试：_flush_staged_state仅有决策记录时正确处理"""
        agent = agent_with_event_bus

        # 只暂存决策记录，不暂存token
        record = {"action": "test_action"}
        agent._stage_decision_record(record)

        # 确保token计数器为0
        assert agent._staged_prompt_tokens == 0
        assert agent._staged_completion_tokens == 0

        with patch.object(agent.session_context, "add_decision") as mock_add_decision:
            with patch.object(agent.session_context, "update_token_usage") as mock_update_token:
                await agent._flush_staged_state()

                # 验证：调用了add_decision
                mock_add_decision.assert_called_once_with(record)
                # 验证：未调用update_token_usage（因为token计数器为0）
                mock_update_token.assert_not_called()
                # 验证：决策记录列表被清空
                assert len(agent._staged_decision_records) == 0

    @pytest.mark.asyncio
    async def test_flush_staged_state_with_both_tokens_and_decisions(self, agent_with_event_bus):
        """测试：_flush_staged_state同时刷新token和决策记录"""
        agent = agent_with_event_bus

        # 同时暂存token和决策记录
        agent._stage_token_usage(prompt_tokens=100, completion_tokens=50)
        record = {"action": "combined_test"}
        agent._stage_decision_record(record)

        with patch.object(agent.session_context, "update_token_usage") as mock_update_token:
            with patch.object(agent.session_context, "add_decision") as mock_add_decision:
                await agent._flush_staged_state()

                # 验证：同时调用了token更新和决策记录添加
                mock_update_token.assert_called_once_with(prompt_tokens=100, completion_tokens=50)
                mock_add_decision.assert_called_once_with(record)

                # 验证：两者都被清空
                assert agent._staged_prompt_tokens == 0
                assert agent._staged_completion_tokens == 0
                assert len(agent._staged_decision_records) == 0

    def test_stage_decision_record_handles_empty_dict(self, agent_with_event_bus):
        """测试：_stage_decision_record处理空字典"""
        agent = agent_with_event_bus

        empty_record = {}
        agent._stage_decision_record(empty_record)

        assert len(agent._staged_decision_records) == 1
        assert agent._staged_decision_records[0] == {}

    def test_stage_decision_record_handles_complex_dict(self, agent_with_event_bus):
        """测试：_stage_decision_record处理复杂字典"""
        agent = agent_with_event_bus

        complex_record = {
            "action": "complex_action",
            "metadata": {
                "timestamp": "2024-01-01",
                "tags": ["tag1", "tag2"],
                "nested": {"key": "value"},
            },
            "confidence": 0.85,
            "alternatives": ["option1", "option2"],
        }

        agent._stage_decision_record(complex_record)

        assert len(agent._staged_decision_records) == 1
        assert agent._staged_decision_records[0] == complex_record
        # 验证是引用而非拷贝（除非有特殊需求）
        assert agent._staged_decision_records[0] is complex_record


# 导出测试类
__all__ = [
    "TestDecisionRecordStaging",
]
