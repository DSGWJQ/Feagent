"""对话错误处理测试 - 第五步：异常处理与重规划

测试 ConversationAgent 将技术错误转化为用户友好提示的逻辑。
遵循 TDD 流程，先编写测试，再实现功能。
"""

from unittest.mock import MagicMock

import pytest


class TestUserFriendlyErrorMessage:
    """测试用户友好的错误消息生成"""

    def test_timeout_error_message(self):
        """TIMEOUT 错误应该生成友好的超时提示

        场景：API 调用超时
        期望：生成清晰的中文提示
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            UserFriendlyMessageGenerator,
        )

        generator = UserFriendlyMessageGenerator()
        message = generator.generate(category=ErrorCategory.TIMEOUT, details="调用用户信息接口超时")

        assert "超时" in message
        assert "用户信息" in message or "接口" in message
        # 应该是中文且易于理解
        assert len(message) < 200

    def test_data_missing_error_message(self):
        """DATA_MISSING 错误应该明确指出缺失的数据

        场景：缺少必填字段
        期望：生成指出缺失字段的提示
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            UserFriendlyMessageGenerator,
        )

        generator = UserFriendlyMessageGenerator()
        message = generator.generate(
            category=ErrorCategory.DATA_MISSING, details="缺少字段: api_key"
        )

        assert "数据" in message or "缺少" in message
        assert "api_key" in message

    def test_api_failure_error_message(self):
        """API_FAILURE 错误应该说明服务调用失败

        场景：外部 API 返回错误
        期望：生成服务调用失败的提示
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            UserFriendlyMessageGenerator,
        )

        generator = UserFriendlyMessageGenerator()
        message = generator.generate(
            category=ErrorCategory.API_FAILURE, details="GitHub API 返回 503 错误"
        )

        assert "服务" in message or "调用" in message
        assert "GitHub" in message or "API" in message

    def test_validation_error_message(self):
        """VALIDATION_ERROR 错误应该说明数据格式问题

        场景：输入数据格式不正确
        期望：生成数据格式错误的提示
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            UserFriendlyMessageGenerator,
        )

        generator = UserFriendlyMessageGenerator()
        message = generator.generate(
            category=ErrorCategory.VALIDATION_ERROR, details="email 格式不正确"
        )

        assert "格式" in message or "数据" in message
        assert "email" in message

    def test_node_crash_error_message(self):
        """NODE_CRASH 错误应该简化技术细节

        场景：节点执行时抛出异常
        期望：隐藏技术细节，提供简洁提示
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            UserFriendlyMessageGenerator,
        )

        generator = UserFriendlyMessageGenerator()
        message = generator.generate(
            category=ErrorCategory.NODE_CRASH,
            details="RuntimeError: NoneType has no attribute 'get'",
        )

        # 应该隐藏技术栈信息
        assert "NoneType" not in message
        assert "RuntimeError" not in message
        # 应该有通用错误提示
        assert "执行" in message or "处理" in message or "错误" in message


class TestUserActionOptions:
    """测试用户操作选项生成"""

    def test_retry_option_for_timeout(self):
        """超时错误应该提供重试选项

        场景：用户遇到超时错误
        期望：提供"重试"选项
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            UserActionOptionsGenerator,
        )

        generator = UserActionOptionsGenerator()
        options = generator.get_options(ErrorCategory.TIMEOUT)

        assert any(opt.action == "retry" for opt in options)
        retry_opt = next(opt for opt in options if opt.action == "retry")
        assert "重试" in retry_opt.label

    def test_provide_data_option_for_data_missing(self):
        """数据缺失应该提供"提供数据"选项

        场景：用户遇到数据缺失错误
        期望：提供输入数据的选项
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            UserActionOptionsGenerator,
        )

        generator = UserActionOptionsGenerator()
        options = generator.get_options(ErrorCategory.DATA_MISSING)

        assert any(opt.action == "provide_data" for opt in options)

    def test_skip_option_for_node_crash(self):
        """节点崩溃应该提供"跳过"选项

        场景：用户遇到节点崩溃
        期望：提供"跳过此步骤"选项
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            UserActionOptionsGenerator,
        )

        generator = UserActionOptionsGenerator()
        options = generator.get_options(ErrorCategory.NODE_CRASH)

        assert any(opt.action == "skip" for opt in options)
        skip_opt = next(opt for opt in options if opt.action == "skip")
        assert "跳过" in skip_opt.label

    def test_abort_option_always_available(self):
        """所有错误都应该提供"终止"选项

        场景：用户想要放弃当前操作
        期望：提供"终止"选项
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            UserActionOptionsGenerator,
        )

        generator = UserActionOptionsGenerator()

        for category in ErrorCategory:
            options = generator.get_options(category)
            assert any(opt.action == "abort" for opt in options)


class TestConversationAgentErrorHandling:
    """测试 ConversationAgent 的错误处理集成"""

    @pytest.mark.asyncio
    async def test_format_error_for_user(self):
        """ConversationAgent 应该能将错误格式化为用户友好消息

        场景：节点执行失败
        期望：返回包含消息和选项的结构
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
        )

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        mock_llm = MagicMock()
        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm)

        error = TimeoutError("API call timed out after 30s")
        formatted = agent.format_error_for_user(
            node_id="api_node", error=error, node_name="获取用户数据"
        )

        # 应该包含必要的字段
        assert formatted.message is not None
        assert formatted.options is not None
        assert len(formatted.options) > 0
        # 消息应该是用户友好的
        assert "获取用户数据" in formatted.message or "超时" in formatted.message

    @pytest.mark.asyncio
    async def test_handle_user_error_decision_retry(self):
        """ConversationAgent 应该能处理用户的重试决定

        场景：用户选择重试
        期望：触发重新执行
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.error_handling import UserDecision
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
        )

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        mock_llm = MagicMock()
        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm)

        decision = UserDecision(action="retry", node_id="api_node")

        result = await agent.handle_user_error_decision(decision)

        assert result.action_taken == "retry"
        assert result.should_continue is True

    @pytest.mark.asyncio
    async def test_handle_user_error_decision_skip(self):
        """ConversationAgent 应该能处理用户的跳过决定

        场景：用户选择跳过
        期望：标记节点为跳过并继续
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.error_handling import UserDecision
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
        )

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        mock_llm = MagicMock()
        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm)

        decision = UserDecision(action="skip", node_id="optional_node")

        result = await agent.handle_user_error_decision(decision)

        assert result.action_taken == "skip"
        assert result.node_skipped is True

    @pytest.mark.asyncio
    async def test_handle_user_error_decision_abort(self):
        """ConversationAgent 应该能处理用户的终止决定

        场景：用户选择终止
        期望：终止工作流执行
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.error_handling import UserDecision
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
        )

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        mock_llm = MagicMock()
        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm)

        decision = UserDecision(action="abort", node_id="any_node")

        result = await agent.handle_user_error_decision(decision)

        assert result.action_taken == "abort"
        assert result.should_continue is False
        assert result.workflow_aborted is True


class TestErrorDialogueFlow:
    """测试错误对话流程"""

    @pytest.mark.asyncio
    async def test_full_error_dialogue_flow(self):
        """完整的错误→解释→用户确认→重试流程

        场景：
        1. 节点执行失败
        2. 向用户解释错误
        3. 用户选择重试
        4. 重新执行成功

        期望：记录完整的对话历史
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.error_handling import (
            ErrorDialogueManager,
            UserDecision,
        )
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
        )

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        mock_llm = MagicMock()
        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm)

        dialogue_manager = ErrorDialogueManager(agent)

        # 第一步：错误发生
        error = TimeoutError("API timeout")
        dialogue_state = await dialogue_manager.start_error_dialogue(
            node_id="api_node", node_name="调用天气API", error=error
        )

        assert dialogue_state.awaiting_user_response is True
        assert dialogue_state.error_explanation is not None

        # 第二步：用户响应
        user_decision = UserDecision(action="retry")
        updated_state = await dialogue_manager.process_user_response(user_decision)

        assert updated_state.user_chose_retry is True

        # 第三步：重试成功
        retry_result = {"temperature": 25, "humidity": 60}
        final_state = await dialogue_manager.complete_recovery(success=True, result=retry_result)

        assert final_state.resolved is True
        assert final_state.resolution_method == "retry"

    @pytest.mark.asyncio
    async def test_error_dialogue_with_data_provision(self):
        """用户提供数据后继续执行的流程

        场景：
        1. 缺少 API Key
        2. 向用户解释并请求
        3. 用户提供 API Key
        4. 使用新数据重新执行

        期望：正确使用用户提供的数据
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.error_handling import (
            ErrorDialogueManager,
            UserDecision,
        )
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
        )

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        mock_llm = MagicMock()
        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm)

        dialogue_manager = ErrorDialogueManager(agent)

        # 错误发生：缺少 API Key
        error = KeyError("OPENAI_API_KEY")
        dialogue_state = await dialogue_manager.start_error_dialogue(
            node_id="llm_node", node_name="AI 问答", error=error
        )

        assert (
            "API" in dialogue_state.error_explanation or "缺少" in dialogue_state.error_explanation
        )

        # 用户提供数据
        user_decision = UserDecision(action="provide_data", data={"OPENAI_API_KEY": "sk-test123"})
        updated_state = await dialogue_manager.process_user_response(user_decision)

        assert updated_state.supplemental_data is not None
        assert "OPENAI_API_KEY" in updated_state.supplemental_data


class TestErrorEventEmission:
    """测试错误事件发布"""

    @pytest.mark.asyncio
    async def test_emit_error_event_to_event_bus(self):
        """发生错误时应该发布错误事件到事件总线

        场景：节点执行失败
        期望：发布 NodeErrorEvent
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.error_handling import NodeErrorEvent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        received_events = []

        async def error_handler(event: NodeErrorEvent):
            received_events.append(event)

        event_bus.subscribe(NodeErrorEvent, error_handler)

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        mock_llm = MagicMock()
        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm, event_bus=event_bus)

        # 触发错误处理
        error = TimeoutError("Timeout")
        await agent.emit_error_event(node_id="node_1", error=error, recovery_action="retry")

        assert len(received_events) == 1
        assert received_events[0].node_id == "node_1"
        assert received_events[0].recovery_action == "retry"

    @pytest.mark.asyncio
    async def test_emit_recovery_complete_event(self):
        """恢复完成时应该发布恢复完成事件

        场景：重试成功
        期望：发布 RecoveryCompleteEvent
        """
        from src.domain.agents.conversation_agent import ConversationAgent
        from src.domain.agents.error_handling import RecoveryCompleteEvent
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        received_events = []

        async def recovery_handler(event: RecoveryCompleteEvent):
            received_events.append(event)

        event_bus.subscribe(RecoveryCompleteEvent, recovery_handler)

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
        mock_llm = MagicMock()
        agent = ConversationAgent(session_context=session_ctx, llm=mock_llm, event_bus=event_bus)

        # 触发恢复完成
        await agent.emit_recovery_complete_event(
            node_id="node_1", success=True, method="retry", attempts=2
        )

        assert len(received_events) == 1
        assert received_events[0].node_id == "node_1"
        assert received_events[0].success is True
        assert received_events[0].recovery_method == "retry"
        assert received_events[0].attempts == 2


class TestErrorLogging:
    """测试错误日志记录"""

    def test_log_error_with_context(self):
        """应该记录包含完整上下文的错误日志

        场景：错误发生时记录详细信息
        期望：日志包含节点ID、错误类型、时间戳等
        """
        from src.domain.agents.error_handling import ErrorLogger

        logger = ErrorLogger()

        error = TimeoutError("API timeout")
        log_entry = logger.log_error(
            node_id="api_node",
            workflow_id="workflow_001",
            error=error,
            context={"url": "https://api.example.com/users"},
        )

        assert log_entry.node_id == "api_node"
        assert log_entry.workflow_id == "workflow_001"
        assert log_entry.error_type == "TimeoutError"
        assert log_entry.timestamp is not None
        assert log_entry.context["url"] == "https://api.example.com/users"

    def test_log_recovery_attempt(self):
        """应该记录恢复尝试

        场景：执行恢复动作时
        期望：记录恢复动作和结果
        """
        from src.domain.agents.error_handling import ErrorLogger, RecoveryAction

        logger = ErrorLogger()

        log_entry = logger.log_recovery_attempt(
            node_id="api_node",
            action=RecoveryAction.RETRY,
            attempt=1,
            success=False,
            next_action=RecoveryAction.RETRY_WITH_BACKOFF,
        )

        assert log_entry.action == RecoveryAction.RETRY
        assert log_entry.attempt == 1
        assert log_entry.success is False
        assert log_entry.next_action == RecoveryAction.RETRY_WITH_BACKOFF
