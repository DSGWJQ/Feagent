"""ConversationAgent 配置兼容性测试

测试 P1-4 步骤1：新旧配置参数的兼容性。

测试场景：
1. Config-only最小：仅传config（最小配置）
2. Config-only完整：仅传config（完整配置）
3. Legacy-only：仅传legacy参数（向后兼容）
4. 混用无冲突：config未指定字段，legacy补充
5. 混用有冲突：config与legacy同时指定，应抛异常
6. None vs sentinel：区分明确传None与未传参数
7. 部分config+legacy：config部分配置，legacy填充
8. 向后兼容：确保现有测试不破坏
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.domain.agents.conversation_agent_config import (
    ConversationAgentConfig,
    IntentConfig,
    LLMConfig,
    ReActConfig,
    ResourceConfig,
    StreamingConfig,
    WorkflowConfig,
)


class TestConfigOnlyMinimal:
    """测试场景1：Config-only最小配置"""

    def test_config_only_minimal_creates_agent(self):
        """仅传config（最小配置）能成功创建Agent"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.entities.session_context import SessionContext

        # 准备最小配置
        session_context = MagicMock(spec=SessionContext)
        llm_instance = MagicMock()

        config = ConversationAgentConfig(
            session_context=session_context,
            llm=LLMConfig(llm=llm_instance),
        )

        # 创建Agent（预期：使用config创建成功）
        agent = ConversationAgent(config=config)

        # 验证：Agent使用了config中的值
        assert agent.session_context == session_context
        assert agent.llm == llm_instance
        assert agent.max_iterations == 10  # 默认值
        assert agent.event_bus is None  # 未指定
        assert agent.enable_intent_classification is False  # 默认值


class TestConfigOnlyFull:
    """测试场景2：Config-only完整配置"""

    def test_config_only_full_creates_agent_with_all_settings(self):
        """仅传config（完整配置）能正确设置所有参数"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.entities.session_context import SessionContext

        # 准备完整配置
        session_context = MagicMock(spec=SessionContext)
        llm_instance = MagicMock()
        event_bus = MagicMock()
        coordinator = MagicMock()
        emitter = MagicMock()

        config = ConversationAgentConfig(
            session_context=session_context,
            llm=LLMConfig(llm=llm_instance, temperature=0.5),
            event_bus=event_bus,
            react=ReActConfig(max_iterations=20, timeout_seconds=60.0),
            intent=IntentConfig(
                enable_intent_classification=True,
                intent_confidence_threshold=0.8,
            ),
            workflow=WorkflowConfig(coordinator=coordinator),
            streaming=StreamingConfig(emitter=emitter),
            resource=ResourceConfig(max_tokens=5000, max_cost=1.0),
        )

        # 创建Agent
        agent = ConversationAgent(config=config)

        # 验证：所有配置生效
        assert agent.session_context == session_context
        assert agent.llm == llm_instance
        assert agent.event_bus == event_bus
        assert agent.max_iterations == 20
        assert agent.timeout_seconds == 60.0
        assert agent.enable_intent_classification is True
        assert agent.intent_confidence_threshold == 0.8
        assert agent.coordinator == coordinator
        assert agent.emitter == emitter
        assert agent.max_tokens == 5000
        assert agent.max_cost == 1.0


class TestLegacyOnly:
    """测试场景3：Legacy-only（向后兼容）"""

    def test_legacy_only_creates_agent(self):
        """仅传legacy参数能成功创建Agent（向后兼容）"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.entities.session_context import SessionContext

        # 准备legacy参数
        session_context = MagicMock(spec=SessionContext)
        llm_instance = MagicMock()
        event_bus = MagicMock()

        # 使用legacy参数创建（无config参数）
        agent = ConversationAgent(
            session_context=session_context,
            llm=llm_instance,
            event_bus=event_bus,
            max_iterations=15,
            timeout_seconds=30.0,
            enable_intent_classification=True,
            intent_confidence_threshold=0.9,
        )

        # 验证：所有参数生效
        assert agent.session_context == session_context
        assert agent.llm == llm_instance
        assert agent.event_bus == event_bus
        assert agent.max_iterations == 15
        assert agent.timeout_seconds == 30.0
        assert agent.enable_intent_classification is True
        assert agent.intent_confidence_threshold == 0.9


class TestMixedNoConflict:
    """测试场景4：混用无冲突（legacy补充config未指定字段）"""

    def test_mixed_no_conflict_merges_correctly(self):
        """config + legacy混用无冲突时，legacy补充config未指定字段"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.entities.session_context import SessionContext

        # 准备config（部分配置）
        session_context = MagicMock(spec=SessionContext)
        llm_instance = MagicMock()

        config = ConversationAgentConfig(
            session_context=session_context,
            llm=LLMConfig(llm=llm_instance),
            # 未指定其他配置
        )

        # 使用legacy参数补充
        event_bus = MagicMock()
        agent = ConversationAgent(
            config=config,
            event_bus=event_bus,  # config中未指定
            max_iterations=25,  # config使用默认值10
            enable_intent_classification=True,  # config使用默认值False
        )

        # 验证：legacy参数补充了config
        assert agent.session_context == session_context
        assert agent.llm == llm_instance
        assert agent.event_bus == event_bus  # legacy补充
        assert agent.max_iterations == 25  # legacy补充
        assert agent.enable_intent_classification is True  # legacy补充


class TestMixedConflict:
    """测试场景5：混用有冲突（应抛异常）"""

    def test_mixed_conflict_max_iterations_raises_error(self):
        """config与legacy同时指定max_iterations且值不同时，应抛ValueError"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.entities.session_context import SessionContext

        # 准备config（指定max_iterations=20）
        session_context = MagicMock(spec=SessionContext)
        llm_instance = MagicMock()

        config = ConversationAgentConfig(
            session_context=session_context,
            llm=LLMConfig(llm=llm_instance),
            react=ReActConfig(max_iterations=20),  # config中指定了
        )

        # 尝试用legacy参数覆盖（冲突）
        with pytest.raises(ValueError, match="Conflicting.*max_iterations"):
            ConversationAgent(
                config=config,
                max_iterations=15,  # 冲突！
            )

    def test_mixed_conflict_event_bus_raises_error(self):
        """config与legacy同时指定event_bus且值不同时，应抛ValueError"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.entities.session_context import SessionContext

        # 准备config（指定event_bus）
        session_context = MagicMock(spec=SessionContext)
        llm_instance = MagicMock()
        event_bus_1 = MagicMock()
        event_bus_2 = MagicMock()

        config = ConversationAgentConfig(
            session_context=session_context,
            llm=LLMConfig(llm=llm_instance),
            event_bus=event_bus_1,  # config中指定了
        )

        # 尝试用legacy参数覆盖（冲突）
        with pytest.raises(ValueError, match="Conflicting.*event_bus"):
            ConversationAgent(
                config=config,
                event_bus=event_bus_2,  # 冲突！
            )


class TestNoneVsSentinel:
    """测试场景6：区分None与sentinel"""

    def test_explicit_none_is_preserved(self):
        """明确传递None应被保留（区别于未传参数）"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.entities.session_context import SessionContext

        # 准备参数
        session_context = MagicMock(spec=SessionContext)
        llm_instance = MagicMock()

        # 明确传递None
        agent = ConversationAgent(
            session_context=session_context,
            llm=llm_instance,
            event_bus=None,  # 明确传递None
            coordinator=None,  # 明确传递None
        )

        # 验证：None被保留
        assert agent.event_bus is None
        assert agent.coordinator is None

    def test_unset_uses_default(self):
        """未传参数应使用默认值"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.entities.session_context import SessionContext

        # 准备参数
        session_context = MagicMock(spec=SessionContext)
        llm_instance = MagicMock()

        # 不传某些参数
        agent = ConversationAgent(
            session_context=session_context,
            llm=llm_instance,
            # 不传event_bus、coordinator
        )

        # 验证：使用默认值
        assert agent.event_bus is None  # 默认值
        assert agent.coordinator is None  # 默认值
        assert agent.max_iterations == 10  # 默认值


class TestPartialConfigWithLegacyFill:
    """测试场景7：部分config + legacy填充"""

    def test_partial_config_with_legacy_fill(self):
        """config部分配置 + legacy填充未指定字段"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.entities.session_context import SessionContext

        # 准备config（只配置了max_iterations）
        session_context = MagicMock(spec=SessionContext)
        llm_instance = MagicMock()

        config = ConversationAgentConfig(
            session_context=session_context,
            llm=LLMConfig(llm=llm_instance),
            react=ReActConfig(max_iterations=20),  # 只配置了max_iterations
        )

        # 用legacy填充其他字段
        event_bus = MagicMock()
        coordinator = MagicMock()

        agent = ConversationAgent(
            config=config,
            event_bus=event_bus,  # 填充
            timeout_seconds=90.0,  # 填充timeout_seconds
            enable_intent_classification=True,  # 填充
            coordinator=coordinator,  # 填充
        )

        # 验证：config优先，legacy填充
        assert agent.max_iterations == 20  # config值
        assert agent.event_bus == event_bus  # legacy填充
        assert agent.timeout_seconds == 90.0  # legacy填充
        assert agent.enable_intent_classification is True  # legacy填充
        assert agent.coordinator == coordinator  # legacy填充


class TestBackwardCompatibility:
    """测试场景8：向后兼容（确保现有代码不破坏）"""

    def test_all_legacy_combinations_work(self):
        """测试各种legacy参数组合仍然有效"""
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.entities.session_context import SessionContext

        session_context = MagicMock(spec=SessionContext)
        llm_instance = MagicMock()

        # 组合1：最小参数
        agent1 = ConversationAgent(
            session_context=session_context,
            llm=llm_instance,
        )
        assert agent1 is not None

        # 组合2：常用参数
        agent2 = ConversationAgent(
            session_context=session_context,
            llm=llm_instance,
            event_bus=MagicMock(),
            max_iterations=15,
        )
        assert agent2.max_iterations == 15

        # 组合3：完整参数
        agent3 = ConversationAgent(
            session_context=session_context,
            llm=llm_instance,
            event_bus=MagicMock(),
            max_iterations=20,
            timeout_seconds=60.0,
            max_tokens=10000,
            max_cost=2.0,
            coordinator=MagicMock(),
            enable_intent_classification=True,
            intent_confidence_threshold=0.85,
            emitter=MagicMock(),
            stream_emitter=MagicMock(),
        )
        assert agent3.max_iterations == 20
        assert agent3.timeout_seconds == 60.0
        assert agent3.enable_intent_classification is True
