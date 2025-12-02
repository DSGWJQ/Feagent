"""Phase 14: 输入分类层 - TDD 测试

测试对话入口的意图识别功能：
1. 区分普通对话 vs workflow 修改请求
2. 只有修改请求才调用 ReAct 循环
3. 普通对话直接生成回复
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.context_manager import GlobalContext, SessionContext

# ==================== Phase 14.1: 意图类型定义 ====================


class TestIntentType:
    """测试意图类型枚举"""

    def test_intent_type_has_conversation(self):
        """测试：IntentType 应包含 CONVERSATION（普通对话）"""
        from src.domain.agents.conversation_agent import IntentType

        assert hasattr(IntentType, "CONVERSATION")
        assert IntentType.CONVERSATION.value == "conversation"

    def test_intent_type_has_workflow_modification(self):
        """测试：IntentType 应包含 WORKFLOW_MODIFICATION"""
        from src.domain.agents.conversation_agent import IntentType

        assert hasattr(IntentType, "WORKFLOW_MODIFICATION")
        assert IntentType.WORKFLOW_MODIFICATION.value == "workflow_modification"

    def test_intent_type_has_workflow_query(self):
        """测试：IntentType 应包含 WORKFLOW_QUERY（查询工作流状态）"""
        from src.domain.agents.conversation_agent import IntentType

        assert hasattr(IntentType, "WORKFLOW_QUERY")
        assert IntentType.WORKFLOW_QUERY.value == "workflow_query"

    def test_intent_type_has_clarification(self):
        """测试：IntentType 应包含 CLARIFICATION（澄清请求）"""
        from src.domain.agents.conversation_agent import IntentType

        assert hasattr(IntentType, "CLARIFICATION")
        assert IntentType.CLARIFICATION.value == "clarification"

    def test_intent_type_has_error_recovery(self):
        """测试：IntentType 应包含 ERROR_RECOVERY_REQUEST"""
        from src.domain.agents.conversation_agent import IntentType

        assert hasattr(IntentType, "ERROR_RECOVERY_REQUEST")
        assert IntentType.ERROR_RECOVERY_REQUEST.value == "error_recovery_request"


# ==================== Phase 14.2: 意图分类结果 ====================


class TestIntentClassificationResult:
    """测试意图分类结果"""

    def test_classification_result_creation(self):
        """测试：应能创建 IntentClassificationResult"""
        from src.domain.agents.conversation_agent import (
            IntentClassificationResult,
            IntentType,
        )

        result = IntentClassificationResult(
            intent=IntentType.CONVERSATION,
            confidence=0.95,
            reasoning="用户在闲聊",
        )

        assert result.intent == IntentType.CONVERSATION
        assert result.confidence == 0.95
        assert result.reasoning == "用户在闲聊"

    def test_classification_result_has_extracted_entities(self):
        """测试：分类结果应包含提取的实体"""
        from src.domain.agents.conversation_agent import (
            IntentClassificationResult,
            IntentType,
        )

        result = IntentClassificationResult(
            intent=IntentType.WORKFLOW_MODIFICATION,
            confidence=0.9,
            extracted_entities={"workflow_id": "wf_1", "action": "add_node"},
        )

        assert result.extracted_entities["workflow_id"] == "wf_1"
        assert result.extracted_entities["action"] == "add_node"


# ==================== Phase 14.3: 意图分类器 ====================


class TestIntentClassifier:
    """测试意图分类器"""

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.classify_intent = AsyncMock(
            return_value={
                "intent": "conversation",
                "confidence": 0.9,
                "reasoning": "普通问候",
            }
        )
        return llm

    def test_conversation_agent_has_classify_intent_method(self):
        """测试：ConversationAgent 应有 classify_intent 方法"""
        from src.domain.agents.conversation_agent import ConversationAgent

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(global_context=global_ctx, session_id="session_1")

        mock_llm = MagicMock()
        mock_llm.think = AsyncMock(return_value="")
        mock_llm.decide_action = AsyncMock(return_value={"action_type": "respond"})
        mock_llm.should_continue = AsyncMock(return_value=False)

        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm)

        assert hasattr(agent, "classify_intent")

    @pytest.mark.asyncio
    async def test_classify_conversation_intent(self, mock_llm):
        """测试：应能分类普通对话意图"""
        from src.domain.agents.conversation_agent import ConversationAgent, IntentType

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(global_context=global_ctx, session_id="session_1")

        mock_llm.think = AsyncMock(return_value="")
        mock_llm.decide_action = AsyncMock(return_value={"action_type": "respond"})
        mock_llm.should_continue = AsyncMock(return_value=False)

        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm)

        result = await agent.classify_intent("你好，今天天气怎么样？")

        assert result.intent == IntentType.CONVERSATION

    @pytest.mark.asyncio
    async def test_classify_workflow_modification_intent(self, mock_llm):
        """测试：应能分类工作流修改意图"""
        from src.domain.agents.conversation_agent import ConversationAgent, IntentType

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(global_context=global_ctx, session_id="session_1")

        mock_llm.classify_intent = AsyncMock(
            return_value={
                "intent": "workflow_modification",
                "confidence": 0.95,
                "reasoning": "用户要求创建工作流",
                "extracted_entities": {"action": "create_workflow"},
            }
        )
        mock_llm.think = AsyncMock(return_value="")
        mock_llm.decide_action = AsyncMock(return_value={"action_type": "respond"})
        mock_llm.should_continue = AsyncMock(return_value=False)

        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm)

        result = await agent.classify_intent("帮我创建一个数据处理工作流")

        assert result.intent == IntentType.WORKFLOW_MODIFICATION

    @pytest.mark.asyncio
    async def test_classify_workflow_query_intent(self, mock_llm):
        """测试：应能分类工作流查询意图"""
        from src.domain.agents.conversation_agent import ConversationAgent, IntentType

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(global_context=global_ctx, session_id="session_1")

        mock_llm.classify_intent = AsyncMock(
            return_value={
                "intent": "workflow_query",
                "confidence": 0.88,
                "reasoning": "用户询问工作流状态",
            }
        )
        mock_llm.think = AsyncMock(return_value="")
        mock_llm.decide_action = AsyncMock(return_value={"action_type": "respond"})
        mock_llm.should_continue = AsyncMock(return_value=False)

        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm)

        result = await agent.classify_intent("工作流 wf_1 执行到哪一步了？")

        assert result.intent == IntentType.WORKFLOW_QUERY


# ==================== Phase 14.4: 分流处理 ====================


class TestIntentBasedRouting:
    """测试基于意图的分流处理"""

    @pytest.fixture
    def session_context(self):
        global_ctx = GlobalContext(user_id="user_1")
        return SessionContext(global_context=global_ctx, session_id="session_1")

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.think = AsyncMock(return_value="思考中...")
        llm.decide_action = AsyncMock(
            return_value={"action_type": "respond", "response": "任务完成"}
        )
        llm.should_continue = AsyncMock(return_value=False)
        llm.classify_intent = AsyncMock(
            return_value={
                "intent": "conversation",
                "confidence": 0.9,
                "reasoning": "普通对话",
            }
        )
        llm.generate_response = AsyncMock(return_value="你好！我是AI助手。")
        return llm

    def test_conversation_agent_has_process_with_intent_method(self, session_context, mock_llm):
        """测试：ConversationAgent 应有 process_with_intent 方法"""
        from src.domain.agents.conversation_agent import ConversationAgent

        agent = ConversationAgent(session_context=session_context, llm=mock_llm)

        assert hasattr(agent, "process_with_intent")

    @pytest.mark.asyncio
    async def test_conversation_intent_skips_react_loop(self, session_context, mock_llm):
        """测试：普通对话意图应跳过 ReAct 循环"""
        from src.domain.agents.conversation_agent import ConversationAgent

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            enable_intent_classification=True,  # 启用意图分类
        )

        result = await agent.process_with_intent("你好")

        # 应该直接返回回复，不调用 ReAct 循环
        assert result.final_response is not None
        # 应该调用了 generate_response 而不是完整的 ReAct
        assert mock_llm.generate_response.called

    @pytest.mark.asyncio
    async def test_workflow_modification_uses_react_loop(self, session_context, mock_llm):
        """测试：工作流修改意图应使用 ReAct 循环"""
        from src.domain.agents.conversation_agent import ConversationAgent

        mock_llm.classify_intent = AsyncMock(
            return_value={
                "intent": "workflow_modification",
                "confidence": 0.95,
                "reasoning": "用户要求修改工作流",
            }
        )

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            max_iterations=3,
            enable_intent_classification=True,  # 启用意图分类
        )

        result = await agent.process_with_intent("在工作流中添加一个数据校验节点")

        # 应该使用 ReAct 循环
        assert result.iterations >= 1
        # 应该调用了 think 和 decide_action
        assert mock_llm.think.called
        assert mock_llm.decide_action.called

    @pytest.mark.asyncio
    async def test_workflow_query_returns_status(self, session_context, mock_llm):
        """测试：工作流查询应返回状态信息"""
        from src.domain.agents.conversation_agent import ConversationAgent

        mock_llm.classify_intent = AsyncMock(
            return_value={
                "intent": "workflow_query",
                "confidence": 0.9,
                "reasoning": "用户查询状态",
                "extracted_entities": {"workflow_id": "wf_1"},
            }
        )
        mock_llm.generate_workflow_status = AsyncMock(
            return_value="工作流 wf_1 正在执行，已完成 3/5 个节点。"
        )

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            enable_intent_classification=True,  # 启用意图分类
        )

        result = await agent.process_with_intent("工作流执行情况如何？")

        assert result.final_response is not None


# ==================== Phase 14.5: 配置和默认行为 ====================


class TestIntentClassificationConfig:
    """测试意图分类配置"""

    @pytest.fixture
    def session_context(self):
        global_ctx = GlobalContext(user_id="user_1")
        return SessionContext(global_context=global_ctx, session_id="session_1")

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.think = AsyncMock(return_value="")
        llm.decide_action = AsyncMock(return_value={"action_type": "respond"})
        llm.should_continue = AsyncMock(return_value=False)
        llm.classify_intent = AsyncMock(return_value={"intent": "conversation", "confidence": 0.9})
        llm.generate_response = AsyncMock(return_value="回复")
        return llm

    def test_agent_has_enable_intent_classification_flag(self, session_context, mock_llm):
        """测试：Agent 应有 enable_intent_classification 配置"""
        from src.domain.agents.conversation_agent import ConversationAgent

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            enable_intent_classification=True,
        )

        assert agent.enable_intent_classification is True

    def test_intent_classification_disabled_by_default(self, session_context, mock_llm):
        """测试：意图分类默认应该禁用（保持向后兼容）"""
        from src.domain.agents.conversation_agent import ConversationAgent

        agent = ConversationAgent(session_context=session_context, llm=mock_llm)

        # 默认禁用以保持向后兼容
        assert agent.enable_intent_classification is False

    @pytest.mark.asyncio
    async def test_disabled_classification_uses_react_directly(self, session_context, mock_llm):
        """测试：禁用分类时应直接使用 ReAct 循环"""
        from src.domain.agents.conversation_agent import ConversationAgent

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            enable_intent_classification=False,
            max_iterations=2,
        )

        # 使用 run_async 而不是 process_with_intent
        await agent.run_async("你好")

        # 应该走 ReAct 循环
        assert mock_llm.think.called


# ==================== Phase 14.6: 置信度阈值 ====================


class TestConfidenceThreshold:
    """测试置信度阈值"""

    @pytest.fixture
    def session_context(self):
        global_ctx = GlobalContext(user_id="user_1")
        return SessionContext(global_context=global_ctx, session_id="session_1")

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.think = AsyncMock(return_value="")
        llm.decide_action = AsyncMock(return_value={"action_type": "respond", "response": "完成"})
        llm.should_continue = AsyncMock(return_value=False)
        llm.classify_intent = AsyncMock(return_value={"intent": "conversation", "confidence": 0.6})
        llm.generate_response = AsyncMock(return_value="回复")
        return llm

    def test_agent_accepts_confidence_threshold(self, session_context, mock_llm):
        """测试：Agent 应接受置信度阈值配置"""
        from src.domain.agents.conversation_agent import ConversationAgent

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            enable_intent_classification=True,
            intent_confidence_threshold=0.8,
        )

        assert agent.intent_confidence_threshold == 0.8

    @pytest.mark.asyncio
    async def test_low_confidence_falls_back_to_react(self, session_context, mock_llm):
        """测试：低置信度应回退到 ReAct 循环"""
        from src.domain.agents.conversation_agent import ConversationAgent

        # 低置信度分类结果
        mock_llm.classify_intent = AsyncMock(
            return_value={
                "intent": "conversation",
                "confidence": 0.5,  # 低于阈值
                "reasoning": "不确定",
            }
        )

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            enable_intent_classification=True,
            intent_confidence_threshold=0.7,
            max_iterations=2,
        )

        await agent.process_with_intent("这是什么？")

        # 低置信度应该使用 ReAct 循环
        assert mock_llm.think.called


# ==================== Phase 14.7: 真实场景测试 ====================


class TestRealWorldScenarios:
    """真实场景测试"""

    @pytest.fixture
    def session_context(self):
        global_ctx = GlobalContext(user_id="user_1")
        return SessionContext(global_context=global_ctx, session_id="session_1")

    @pytest.mark.asyncio
    async def test_scenario_greeting_conversation(self, session_context):
        """场景：用户问候 - 应直接回复"""
        from src.domain.agents.conversation_agent import ConversationAgent

        mock_llm = MagicMock()
        mock_llm.classify_intent = AsyncMock(
            return_value={
                "intent": "conversation",
                "confidence": 0.98,
                "reasoning": "简单问候语",
            }
        )
        mock_llm.generate_response = AsyncMock(return_value="你好！有什么可以帮你的吗？")
        mock_llm.think = AsyncMock(return_value="")
        mock_llm.decide_action = AsyncMock(return_value={"action_type": "respond"})
        mock_llm.should_continue = AsyncMock(return_value=False)

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            enable_intent_classification=True,
        )

        result = await agent.process_with_intent("你好")

        assert result.final_response == "你好！有什么可以帮你的吗？"
        # 不应调用 ReAct 循环
        assert not mock_llm.think.called

    @pytest.mark.asyncio
    async def test_scenario_create_workflow_request(self, session_context):
        """场景：创建工作流请求 - 应使用 ReAct"""
        from src.domain.agents.conversation_agent import ConversationAgent

        mock_llm = MagicMock()
        mock_llm.classify_intent = AsyncMock(
            return_value={
                "intent": "workflow_modification",
                "confidence": 0.95,
                "reasoning": "用户要求创建工作流",
                "extracted_entities": {
                    "action": "create",
                    "workflow_type": "data_processing",
                },
            }
        )
        mock_llm.think = AsyncMock(return_value="用户需要创建数据处理工作流...")
        mock_llm.decide_action = AsyncMock(
            return_value={
                "action_type": "create_workflow_plan",
                "plan": {"name": "数据处理"},
            }
        )
        mock_llm.should_continue = AsyncMock(side_effect=[True, False])
        mock_llm.generate_response = AsyncMock(return_value="")

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            enable_intent_classification=True,
            max_iterations=3,
        )

        result = await agent.process_with_intent("帮我创建一个数据ETL工作流")

        # 应该使用 ReAct 循环
        assert mock_llm.think.called
        assert result.iterations >= 1

    @pytest.mark.asyncio
    async def test_scenario_mixed_conversation(self, session_context):
        """场景：混合对话 - 先问候后请求"""
        from src.domain.agents.conversation_agent import ConversationAgent

        mock_llm = MagicMock()
        mock_llm.think = AsyncMock(return_value="")
        mock_llm.decide_action = AsyncMock(
            return_value={"action_type": "respond", "response": "完成"}
        )
        mock_llm.should_continue = AsyncMock(return_value=False)

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            enable_intent_classification=True,
        )

        # 第一次：问候
        mock_llm.classify_intent = AsyncMock(
            return_value={"intent": "conversation", "confidence": 0.95}
        )
        mock_llm.generate_response = AsyncMock(return_value="你好！")

        result1 = await agent.process_with_intent("你好")
        assert result1.final_response == "你好！"

        # 第二次：工作流请求
        mock_llm.classify_intent = AsyncMock(
            return_value={"intent": "workflow_modification", "confidence": 0.9}
        )

        await agent.process_with_intent("创建一个工作流")
        assert mock_llm.think.called

    @pytest.mark.asyncio
    async def test_scenario_ambiguous_input(self, session_context):
        """场景：模糊输入 - 低置信度回退到 ReAct"""
        from src.domain.agents.conversation_agent import ConversationAgent

        mock_llm = MagicMock()
        mock_llm.classify_intent = AsyncMock(
            return_value={
                "intent": "conversation",
                "confidence": 0.55,
                "reasoning": "输入模糊，难以判断",
            }
        )
        mock_llm.think = AsyncMock(return_value="需要更多信息来理解用户意图...")
        mock_llm.decide_action = AsyncMock(
            return_value={
                "action_type": "request_clarification",
                "question": "请问你想了解什么？",
            }
        )
        mock_llm.should_continue = AsyncMock(return_value=False)
        mock_llm.generate_response = AsyncMock(return_value="")

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            enable_intent_classification=True,
            intent_confidence_threshold=0.7,
            max_iterations=2,
        )

        await agent.process_with_intent("那个东西")

        # 应该回退到 ReAct 循环处理模糊输入
        assert mock_llm.think.called

    @pytest.mark.asyncio
    async def test_scenario_error_recovery_request(self, session_context):
        """场景：错误恢复请求"""
        from src.domain.agents.conversation_agent import ConversationAgent

        mock_llm = MagicMock()
        mock_llm.classify_intent = AsyncMock(
            return_value={
                "intent": "error_recovery_request",
                "confidence": 0.92,
                "reasoning": "用户报告错误需要帮助",
                "extracted_entities": {"workflow_id": "wf_1", "error_type": "timeout"},
            }
        )
        mock_llm.think = AsyncMock(return_value="用户遇到超时错误...")
        mock_llm.decide_action = AsyncMock(return_value={"action_type": "error_recovery"})
        mock_llm.should_continue = AsyncMock(return_value=False)
        mock_llm.generate_response = AsyncMock(return_value="")

        agent = ConversationAgent(
            session_context=session_context,
            llm=mock_llm,
            enable_intent_classification=True,
            max_iterations=3,
        )

        await agent.process_with_intent("工作流 wf_1 超时了，怎么办？")

        # 应该使用 ReAct 循环处理错误恢复
        assert mock_llm.think.called
