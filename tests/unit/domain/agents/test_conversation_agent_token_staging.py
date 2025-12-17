"""ConversationAgent Token暂存与批量刷新测试

目标：补充Token暂存机制的完整测试覆盖
覆盖代码：conversation_agent.py:372-373, 412-417行
新增测试：4个

测试场景：
1. Token累积逻辑
2. 批量刷新到SessionContext
3. 计数器重置
4. 空数据快速路径
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
# Test: Token暂存机制
# ============================================================================


class TestTokenStaging:
    """测试Token暂存机制"""

    def test_stage_token_usage_accumulates_tokens(self, agent_with_event_bus):
        """测试：_stage_token_usage正确累积token"""
        agent = agent_with_event_bus

        # 初始状态：计数器为0
        assert agent._staged_prompt_tokens == 0
        assert agent._staged_completion_tokens == 0

        # 第一次暂存
        agent._stage_token_usage(prompt_tokens=100, completion_tokens=50)
        assert agent._staged_prompt_tokens == 100
        assert agent._staged_completion_tokens == 50

        # 第二次暂存：累积
        agent._stage_token_usage(prompt_tokens=200, completion_tokens=75)
        assert agent._staged_prompt_tokens == 300  # 100 + 200
        assert agent._staged_completion_tokens == 125  # 50 + 75

        # 第三次暂存：继续累积
        agent._stage_token_usage(prompt_tokens=150, completion_tokens=100)
        assert agent._staged_prompt_tokens == 450
        assert agent._staged_completion_tokens == 225

    @pytest.mark.asyncio
    async def test_flush_staged_state_updates_session_context(self, agent_with_event_bus):
        """测试：_flush_staged_state批量更新SessionContext"""
        agent = agent_with_event_bus

        # 暂存一些token
        agent._stage_token_usage(prompt_tokens=500, completion_tokens=300)

        # Mock session_context.update_token_usage
        with patch.object(agent.session_context, "update_token_usage") as mock_update:
            await agent._flush_staged_state()

            # 验证调用了update_token_usage
            mock_update.assert_called_once_with(
                prompt_tokens=500,
                completion_tokens=300,
            )

    @pytest.mark.asyncio
    async def test_flush_staged_state_resets_counters(self, agent_with_event_bus):
        """测试：_flush_staged_state重置计数器"""
        agent = agent_with_event_bus

        # 暂存一些token
        agent._stage_token_usage(prompt_tokens=1000, completion_tokens=800)
        assert agent._staged_prompt_tokens == 1000
        assert agent._staged_completion_tokens == 800

        # Mock update_token_usage
        with patch.object(agent.session_context, "update_token_usage"):
            await agent._flush_staged_state()

            # 验证计数器被重置为0
            assert agent._staged_prompt_tokens == 0
            assert agent._staged_completion_tokens == 0

    @pytest.mark.asyncio
    async def test_flush_staged_state_skips_when_empty(self, agent_with_event_bus):
        """测试：_flush_staged_state在无暂存数据时跳过（快速路径）"""
        agent = agent_with_event_bus

        # 确保计数器为0，无暂存决策记录
        assert agent._staged_prompt_tokens == 0
        assert agent._staged_completion_tokens == 0
        assert len(agent._staged_decision_records) == 0

        # Mock update_token_usage和add_decision
        with patch.object(agent.session_context, "update_token_usage") as mock_update:
            with patch.object(agent.session_context, "add_decision") as mock_add_decision:
                await agent._flush_staged_state()

                # 验证：快速路径，不调用任何更新方法
                mock_update.assert_not_called()
                mock_add_decision.assert_not_called()

    @pytest.mark.asyncio
    async def test_flush_staged_state_handles_only_tokens(self, agent_with_event_bus):
        """测试：_flush_staged_state仅有token时正确处理"""
        agent = agent_with_event_bus

        # 只暂存token，不暂存决策记录
        agent._stage_token_usage(prompt_tokens=200, completion_tokens=100)

        with patch.object(agent.session_context, "update_token_usage") as mock_update:
            with patch.object(agent.session_context, "add_decision") as mock_add_decision:
                await agent._flush_staged_state()

                # 验证：调用了update_token_usage
                mock_update.assert_called_once()
                # 验证：未调用add_decision
                mock_add_decision.assert_not_called()
                # 验证：计数器重置
                assert agent._staged_prompt_tokens == 0
                assert agent._staged_completion_tokens == 0

    @pytest.mark.asyncio
    async def test_stage_token_usage_converts_to_int(self, agent_with_event_bus):
        """测试：_stage_token_usage将输入转换为int"""
        agent = agent_with_event_bus

        # 传入浮点数
        agent._stage_token_usage(prompt_tokens=10.7, completion_tokens=5.3)
        assert agent._staged_prompt_tokens == 10
        assert agent._staged_completion_tokens == 5

        # 传入字符串（可转换为int）
        agent._stage_token_usage(prompt_tokens="20", completion_tokens="15")
        assert agent._staged_prompt_tokens == 30  # 10 + 20
        assert agent._staged_completion_tokens == 20  # 5 + 15


# 导出测试类
__all__ = [
    "TestTokenStaging",
]
