"""错误处理与恢复模块单元测试

覆盖 src.domain.agents.error_handling 的核心逻辑：
- 异常分类、恢复策略映射
- 指数退避
- 恢复执行器与用户干预流程
- 对话管理、日志与事件默认值
"""

from __future__ import annotations

import importlib
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture()
def error_handling_module():
    return importlib.import_module("src.domain.agents.error_handling")


class TestErrorCategoryAndMapper:
    # 2 tests

    def test_error_category_is_retryable_expected_set(self, error_handling_module):
        ErrorCategory = error_handling_module.ErrorCategory

        retryable = {ErrorCategory.TIMEOUT, ErrorCategory.API_FAILURE, ErrorCategory.RATE_LIMITED}
        for category in ErrorCategory:
            assert category.is_retryable() == (category in retryable)

    def test_recovery_strategy_mapper_default_and_custom_override(self, error_handling_module):
        ErrorCategory = error_handling_module.ErrorCategory
        RecoveryAction = error_handling_module.RecoveryAction
        RecoveryStrategyMapper = error_handling_module.RecoveryStrategyMapper

        default_mapper = RecoveryStrategyMapper()
        assert (
            default_mapper.get_recovery_action(ErrorCategory.TIMEOUT)
            == RecoveryAction.RETRY_WITH_BACKOFF
        )
        assert default_mapper.get_recovery_action(ErrorCategory.API_FAILURE) == RecoveryAction.RETRY

        custom_mapper = RecoveryStrategyMapper(
            custom_mapping={ErrorCategory.TIMEOUT: RecoveryAction.ABORT}
        )
        assert custom_mapper.get_recovery_action(ErrorCategory.TIMEOUT) == RecoveryAction.ABORT

        default_mapper.mapping.pop(ErrorCategory.TIMEOUT)
        assert default_mapper.get_recovery_action(ErrorCategory.TIMEOUT) == RecoveryAction.ASK_USER

    def test_error_category_requires_user_intervention_expected_set(self, error_handling_module):
        """Test: requires_user_intervention() returns True for expected categories (lines 49-55)"""
        ErrorCategory = error_handling_module.ErrorCategory

        user_intervention = {
            ErrorCategory.DATA_MISSING,
            ErrorCategory.VALIDATION_ERROR,
            ErrorCategory.PERMISSION_DENIED,
            ErrorCategory.UNKNOWN,
        }

        for category in ErrorCategory:
            assert category.requires_user_intervention() == (category in user_intervention)


class TestExceptionClassifier:
    # 8 tests

    def test_exception_classifier_exact_type_mapping_timeout(self, error_handling_module):
        ExceptionClassifier = error_handling_module.ExceptionClassifier
        ErrorCategory = error_handling_module.ErrorCategory

        classifier = ExceptionClassifier()
        assert classifier.classify(TimeoutError("t")) == ErrorCategory.TIMEOUT

    def test_exception_classifier_exact_type_mapping_keyerror(self, error_handling_module):
        ExceptionClassifier = error_handling_module.ExceptionClassifier
        ErrorCategory = error_handling_module.ErrorCategory

        classifier = ExceptionClassifier()
        assert classifier.classify(KeyError("missing")) == ErrorCategory.DATA_MISSING

    def test_exception_classifier_exact_type_mapping_permission(self, error_handling_module):
        ExceptionClassifier = error_handling_module.ExceptionClassifier
        ErrorCategory = error_handling_module.ErrorCategory

        classifier = ExceptionClassifier()
        assert classifier.classify(PermissionError("nope")) == ErrorCategory.PERMISSION_DENIED

    def test_exception_classifier_subclass_mapping_via_isinstance(self, error_handling_module):
        ExceptionClassifier = error_handling_module.ExceptionClassifier
        ErrorCategory = error_handling_module.ErrorCategory

        class MyConnectionError(ConnectionError):
            pass

        classifier = ExceptionClassifier()
        assert classifier.classify(MyConnectionError("down")) == ErrorCategory.API_FAILURE

    def test_exception_classifier_keyword_rate_limit(self, error_handling_module):
        ExceptionClassifier = error_handling_module.ExceptionClassifier
        ErrorCategory = error_handling_module.ErrorCategory

        classifier = ExceptionClassifier()
        assert classifier.classify(Exception("Rate limit exceeded")) == ErrorCategory.RATE_LIMITED
        assert classifier.classify(Exception("Too many requests")) == ErrorCategory.RATE_LIMITED

    def test_exception_classifier_keyword_timeout(self, error_handling_module):
        ExceptionClassifier = error_handling_module.ExceptionClassifier
        ErrorCategory = error_handling_module.ErrorCategory

        classifier = ExceptionClassifier()
        assert classifier.classify(Exception("request TIMEOUT after 30s")) == ErrorCategory.TIMEOUT

    def test_exception_classifier_keyword_connection_or_network(self, error_handling_module):
        ExceptionClassifier = error_handling_module.ExceptionClassifier
        ErrorCategory = error_handling_module.ErrorCategory

        classifier = ExceptionClassifier()
        assert classifier.classify(Exception("connection reset")) == ErrorCategory.API_FAILURE
        assert classifier.classify(Exception("network unreachable")) == ErrorCategory.API_FAILURE

    def test_exception_classifier_custom_mapping_overrides_default(self, error_handling_module):
        ExceptionClassifier = error_handling_module.ExceptionClassifier
        ErrorCategory = error_handling_module.ErrorCategory

        classifier = ExceptionClassifier(custom_mapping={RuntimeError: ErrorCategory.UNKNOWN})
        assert classifier.classify(RuntimeError("boom")) == ErrorCategory.UNKNOWN

    def test_exception_classifier_unknown_fallback_and_classify_with_context(
        self, error_handling_module
    ):
        """Test: UNKNOWN fallback (line 151) and classify_with_context wrapper (lines 162-163)"""
        ExceptionClassifier = error_handling_module.ExceptionClassifier
        ErrorCategory = error_handling_module.ErrorCategory

        classifier = ExceptionClassifier()

        # Unknown fallback - exception with no matching type or keyword
        unknown_error = Exception("Something completely random xyz123")
        assert classifier.classify(unknown_error) == ErrorCategory.UNKNOWN

        # classify_with_context wrapper
        result = classifier.classify_with_context(unknown_error)
        assert result.category == ErrorCategory.UNKNOWN
        assert result.original_message == "Something completely random xyz123"
        assert result.exception_type == "Exception"


class TestBackoffCalculator:
    # 5 tests

    def test_backoff_calculator_exponential_growth(self, error_handling_module):
        BackoffCalculator = error_handling_module.BackoffCalculator

        calculator = BackoffCalculator(base_delay=1.0, factor=2.0, max_delay=60.0)
        assert calculator.get_delay(0) == 1.0
        assert calculator.get_delay(1) == 2.0
        assert calculator.get_delay(2) == 4.0

    def test_backoff_calculator_caps_at_max_delay(self, error_handling_module):
        BackoffCalculator = error_handling_module.BackoffCalculator

        calculator = BackoffCalculator(base_delay=10.0, factor=10.0, max_delay=60.0)
        assert calculator.get_delay(0) == 10.0
        assert calculator.get_delay(2) == 60.0
        assert calculator.get_delay(100) == 60.0

    def test_backoff_calculator_jitter_zero_returns_base(self, error_handling_module):
        BackoffCalculator = error_handling_module.BackoffCalculator

        calculator = BackoffCalculator(base_delay=1.0, factor=2.0, max_delay=60.0, jitter=0.0)
        assert calculator.get_delay_with_jitter(3) == calculator.get_delay(3)

    def test_backoff_calculator_jitter_within_expected_range(
        self, monkeypatch, error_handling_module
    ):
        BackoffCalculator = error_handling_module.BackoffCalculator

        calculator = BackoffCalculator(base_delay=2.0, factor=2.0, max_delay=60.0, jitter=0.5)
        base = calculator.get_delay(2)  # 2 * 2^2 = 8
        assert base == 8.0

        # Force max jitter to validate upper bound
        jitter_range = base * calculator.jitter
        monkeypatch.setattr(error_handling_module.random, "uniform", lambda a, b: jitter_range)
        delay = calculator.get_delay_with_jitter(2)
        assert delay == base + jitter_range
        assert base * (1 - calculator.jitter) <= delay <= base * (1 + calculator.jitter)

    def test_backoff_calculator_negative_or_zero_jitter_treated_as_no_jitter(
        self, error_handling_module
    ):
        BackoffCalculator = error_handling_module.BackoffCalculator

        calculator = BackoffCalculator(base_delay=1.0, factor=2.0, max_delay=60.0, jitter=-0.1)
        assert calculator.get_delay_with_jitter(2) == calculator.get_delay(2)


class TestUserFriendlyMessageGenerator:
    # 2 tests

    def test_user_friendly_message_generator_formats_details(self, error_handling_module):
        ErrorCategory = error_handling_module.ErrorCategory
        UserFriendlyMessageGenerator = error_handling_module.UserFriendlyMessageGenerator

        generator = UserFriendlyMessageGenerator()
        message = generator.generate(ErrorCategory.TIMEOUT, details="调用接口超时")
        assert "超时" in message
        assert "调用接口超时" in message

    def test_user_friendly_message_generator_custom_template_override(self, error_handling_module):
        ErrorCategory = error_handling_module.ErrorCategory
        UserFriendlyMessageGenerator = error_handling_module.UserFriendlyMessageGenerator

        generator = UserFriendlyMessageGenerator(templates={ErrorCategory.TIMEOUT: "X:{details}"})
        assert generator.generate(ErrorCategory.TIMEOUT, details="D") == "X:D"


class TestUserActionOptionsGenerator:
    # 2 tests

    def test_user_action_options_generator_unknown_category_returns_default_and_has_abort(
        self, error_handling_module
    ):
        ErrorCategory = error_handling_module.ErrorCategory
        UserActionOptionsGenerator = error_handling_module.UserActionOptionsGenerator

        generator = UserActionOptionsGenerator()
        options = generator.get_options(ErrorCategory.RESOURCE_EXHAUSTED)
        assert any(opt.action == "abort" for opt in options)

    def test_user_action_options_generator_appends_abort_if_missing(
        self, monkeypatch, error_handling_module
    ):
        ErrorCategory = error_handling_module.ErrorCategory
        UserActionOption = error_handling_module.UserActionOption
        UserActionOptionsGenerator = error_handling_module.UserActionOptionsGenerator

        monkeypatch.setitem(
            error_handling_module.CATEGORY_OPTIONS,
            ErrorCategory.VALIDATION_ERROR,
            [
                UserActionOption("provide_data", "修正数据", "提供正确格式的数据"),
                UserActionOption("skip", "跳过", "跳过此步骤"),
            ],
        )

        generator = UserActionOptionsGenerator()
        options = generator.get_options(ErrorCategory.VALIDATION_ERROR)
        assert any(opt.action == "abort" for opt in options)


class TestRecoveryExecutor:
    # 5 async tests

    @pytest.mark.asyncio
    async def test_recovery_executor_retry_success_returns_result(self, error_handling_module):
        RecoveryAction = error_handling_module.RecoveryAction
        RecoveryContext = error_handling_module.RecoveryContext
        RecoveryExecutor = error_handling_module.RecoveryExecutor

        operation = AsyncMock(return_value="ok")
        executor = RecoveryExecutor()
        context = RecoveryContext(
            node_id="n1",
            action=RecoveryAction.RETRY,
            original_error=RuntimeError("x"),
            retry_count=0,
            max_retries=3,
        )

        result = await executor.execute(context=context, operation=operation)
        assert result.success is True
        assert result.result == "ok"
        assert operation.await_count == 1

    @pytest.mark.asyncio
    async def test_recovery_executor_retry_exhausted_sets_exhausted_retries(
        self, error_handling_module
    ):
        RecoveryAction = error_handling_module.RecoveryAction
        RecoveryContext = error_handling_module.RecoveryContext
        RecoveryExecutor = error_handling_module.RecoveryExecutor

        operation = AsyncMock(return_value="ok")
        executor = RecoveryExecutor()
        context = RecoveryContext(
            node_id="n1",
            action=RecoveryAction.RETRY,
            original_error=RuntimeError("x"),
            retry_count=3,
            max_retries=3,
        )

        result = await executor.execute(context=context, operation=operation)
        assert result.success is False
        assert result.exhausted_retries is True
        assert operation.await_count == 0

    @pytest.mark.asyncio
    async def test_recovery_executor_skip_and_replan_branches(self, error_handling_module):
        RecoveryAction = error_handling_module.RecoveryAction
        RecoveryContext = error_handling_module.RecoveryContext
        RecoveryExecutor = error_handling_module.RecoveryExecutor

        executor = RecoveryExecutor()
        operation = AsyncMock(return_value="ok")

        skip_ctx = RecoveryContext(
            node_id="n-skip",
            action=RecoveryAction.SKIP,
            original_error=RuntimeError("x"),
        )
        skip_result = await executor.execute(context=skip_ctx, operation=operation)
        assert skip_result.skipped is True

        replan_ctx = RecoveryContext(
            node_id="n-replan",
            action=RecoveryAction.REPLAN,
            original_error=RuntimeError("x"),
            failed_dependencies=["a", "b"],
        )
        replan_result = await executor.execute(context=replan_ctx, operation=operation)
        assert replan_result.needs_replan is True
        assert replan_result.failed_dependencies == ["a", "b"]

    @pytest.mark.asyncio
    async def test_recovery_executor_ask_user_includes_node_and_error_message(
        self, error_handling_module
    ):
        RecoveryAction = error_handling_module.RecoveryAction
        RecoveryContext = error_handling_module.RecoveryContext
        RecoveryExecutor = error_handling_module.RecoveryExecutor

        executor = RecoveryExecutor()
        operation = AsyncMock()
        error = ValueError("bad input")
        context = RecoveryContext(
            node_id="node_1", action=RecoveryAction.ASK_USER, original_error=error
        )

        result = await executor.execute(context=context, operation=operation)
        assert result.awaiting_user_input is True
        assert result.user_prompt is not None
        assert "节点 node_1" in result.user_prompt
        assert "bad input" in result.user_prompt

    @pytest.mark.asyncio
    async def test_recovery_executor_abort_sets_aborted_and_reason(self, error_handling_module):
        RecoveryAction = error_handling_module.RecoveryAction
        RecoveryContext = error_handling_module.RecoveryContext
        RecoveryExecutor = error_handling_module.RecoveryExecutor

        executor = RecoveryExecutor()
        operation = AsyncMock()
        error = MemoryError("oom")
        context = RecoveryContext(
            node_id="node_abort", action=RecoveryAction.ABORT, original_error=error
        )

        result = await executor.execute(context=context, operation=operation)
        assert result.aborted is True
        assert result.abort_reason is not None
        assert "严重错误" in result.abort_reason
        assert "oom" in result.abort_reason

    @pytest.mark.asyncio
    async def test_recovery_executor_retry_with_backoff_delegates_to_retry(
        self, error_handling_module
    ):
        """Test: RETRY_WITH_BACKOFF delegates to retry logic (lines 277, 310)"""
        RecoveryAction = error_handling_module.RecoveryAction
        RecoveryContext = error_handling_module.RecoveryContext
        RecoveryExecutor = error_handling_module.RecoveryExecutor

        operation = AsyncMock(return_value="ok")
        executor = RecoveryExecutor()
        context = RecoveryContext(
            node_id="n1",
            action=RecoveryAction.RETRY_WITH_BACKOFF,
            original_error=RuntimeError("x"),
            retry_count=0,
            max_retries=3,
        )

        result = await executor.execute(context=context, operation=operation)
        assert result.success is True
        assert result.result == "ok"

    @pytest.mark.asyncio
    async def test_recovery_executor_retry_exception_returns_failure(self, error_handling_module):
        """Test: retry catches exception and returns success=False (lines 301-302)"""
        RecoveryAction = error_handling_module.RecoveryAction
        RecoveryContext = error_handling_module.RecoveryContext
        RecoveryExecutor = error_handling_module.RecoveryExecutor

        operation = AsyncMock(side_effect=RuntimeError("retry failed"))
        executor = RecoveryExecutor()
        context = RecoveryContext(
            node_id="n1",
            action=RecoveryAction.RETRY,
            original_error=RuntimeError("x"),
            retry_count=0,
            max_retries=3,
        )

        result = await executor.execute(context=context, operation=operation)
        assert result.success is False
        assert result.exhausted_retries is False  # Not exhausted, just failed

    @pytest.mark.asyncio
    async def test_recovery_executor_fallback_returns_failure(self, error_handling_module):
        """Test: unknown/unhandled action returns success=False (line 287)"""
        RecoveryAction = error_handling_module.RecoveryAction
        RecoveryContext = error_handling_module.RecoveryContext
        RecoveryExecutor = error_handling_module.RecoveryExecutor

        executor = RecoveryExecutor()
        # Use FALLBACK action which isn't handled by execute()
        context = RecoveryContext(
            node_id="n1",
            action=RecoveryAction.FALLBACK,
            original_error=RuntimeError("x"),
            retry_count=0,
            max_retries=3,
        )

        # FALLBACK hits the else branch which returns RecoveryResult(success=False)
        result = await executor.execute(context=context, operation=AsyncMock())
        assert result.success is False


class TestErrorRecoveryHandler:
    # 6 tests

    def test_error_recovery_handler_create_plan_timeout_backoff_delay(self, error_handling_module):
        BackoffCalculator = error_handling_module.BackoffCalculator
        ErrorCategory = error_handling_module.ErrorCategory
        ErrorRecoveryHandler = error_handling_module.ErrorRecoveryHandler
        RecoveryAction = error_handling_module.RecoveryAction

        handler = ErrorRecoveryHandler(
            max_retries=3,
            backoff_calculator=BackoffCalculator(base_delay=1.0, factor=2.0, max_delay=60.0),
        )
        plan = handler.create_recovery_plan(node_id="n1", error=TimeoutError("t"), attempt=2)

        assert plan.category == ErrorCategory.TIMEOUT
        assert plan.action == RecoveryAction.RETRY_WITH_BACKOFF
        assert plan.delay == 4.0
        assert plan.awaiting_user_input is False
        assert plan.escalated is False

    def test_error_recovery_handler_create_plan_no_delay_for_retry_action_api_failure(
        self, error_handling_module
    ):
        ErrorCategory = error_handling_module.ErrorCategory
        ErrorRecoveryHandler = error_handling_module.ErrorRecoveryHandler
        RecoveryAction = error_handling_module.RecoveryAction

        handler = ErrorRecoveryHandler(max_retries=3)
        plan = handler.create_recovery_plan(node_id="n1", error=ConnectionError("down"), attempt=1)

        assert plan.category == ErrorCategory.API_FAILURE
        assert plan.action == RecoveryAction.RETRY
        assert plan.delay == 0.0
        assert plan.awaiting_user_input is False

    def test_error_recovery_handler_escalates_to_ask_user_after_max_retries(
        self, error_handling_module
    ):
        ErrorRecoveryHandler = error_handling_module.ErrorRecoveryHandler
        RecoveryAction = error_handling_module.RecoveryAction

        handler = ErrorRecoveryHandler(max_retries=1)
        plan = handler.create_recovery_plan(node_id="n1", error=TimeoutError("t"), attempt=1)

        assert plan.action == RecoveryAction.ASK_USER
        assert plan.awaiting_user_input is True
        assert plan.escalated is True
        assert plan.delay == 0.0

    def test_error_recovery_handler_apply_user_response_provide_data_sets_retry_ready_and_supplemental(
        self, error_handling_module
    ):
        ErrorCategory = error_handling_module.ErrorCategory
        ErrorRecoveryHandler = error_handling_module.ErrorRecoveryHandler
        RecoveryAction = error_handling_module.RecoveryAction
        RecoveryPlan = error_handling_module.RecoveryPlan
        UserResponse = error_handling_module.UserResponse

        handler = ErrorRecoveryHandler()
        plan = RecoveryPlan(
            node_id="n1",
            category=ErrorCategory.DATA_MISSING,
            action=RecoveryAction.ASK_USER,
            awaiting_user_input=True,
        )
        response = UserResponse(action="provide_data", data={"api_key": "k"})

        updated = handler.apply_user_response(plan=plan, response=response)
        assert updated.node_id == "n1"
        assert updated.category == ErrorCategory.DATA_MISSING
        assert updated.action == RecoveryAction.RETRY
        assert updated.ready_to_retry is True
        assert updated.supplemental_data == {"api_key": "k"}

    @pytest.mark.parametrize(
        ("response_action", "expected_action", "expected_ready"),
        [
            ("retry", "retry", True),
            ("skip", "skip", False),
            ("abort", "abort", False),
        ],
    )
    def test_error_recovery_handler_apply_user_response_retry_skip_abort(
        self, response_action, expected_action, expected_ready, error_handling_module
    ):
        ErrorCategory = error_handling_module.ErrorCategory
        ErrorRecoveryHandler = error_handling_module.ErrorRecoveryHandler
        RecoveryAction = error_handling_module.RecoveryAction
        RecoveryPlan = error_handling_module.RecoveryPlan
        UserResponse = error_handling_module.UserResponse

        handler = ErrorRecoveryHandler()
        plan = RecoveryPlan(
            node_id="n1",
            category=ErrorCategory.TIMEOUT,
            action=RecoveryAction.ASK_USER,
            awaiting_user_input=True,
        )
        response = UserResponse(action=response_action, data={})

        updated = handler.apply_user_response(plan=plan, response=response)
        assert updated.node_id == "n1"
        assert updated.category == ErrorCategory.TIMEOUT
        assert updated.action == RecoveryAction(expected_action)
        assert updated.ready_to_retry is expected_ready

    def test_error_recovery_handler_apply_user_response_unknown_is_noop(
        self, error_handling_module
    ):
        ErrorCategory = error_handling_module.ErrorCategory
        ErrorRecoveryHandler = error_handling_module.ErrorRecoveryHandler
        RecoveryAction = error_handling_module.RecoveryAction
        RecoveryPlan = error_handling_module.RecoveryPlan
        UserResponse = error_handling_module.UserResponse

        handler = ErrorRecoveryHandler()
        plan = RecoveryPlan(
            node_id="n1",
            category=ErrorCategory.UNKNOWN,
            action=RecoveryAction.ASK_USER,
            awaiting_user_input=True,
        )
        response = UserResponse(action="noop", data={"x": 1})

        updated = handler.apply_user_response(plan=plan, response=response)
        assert updated is plan


class TestErrorDialogueManager:
    # 4 async tests

    @pytest.mark.asyncio
    async def test_error_dialogue_manager_start_sets_state_and_explanation(
        self, error_handling_module
    ):
        ErrorDialogueManager = error_handling_module.ErrorDialogueManager

        manager = ErrorDialogueManager(conversation_agent=MagicMock())
        error = TimeoutError("API call timed out")
        state = await manager.start_error_dialogue(node_id="n1", node_name="node", error=error)

        assert manager.current_state is state
        assert state.node_id == "n1"
        assert state.node_name == "node"
        assert state.awaiting_user_response is True
        assert "API call timed out" in state.error_explanation

    @pytest.mark.asyncio
    async def test_error_dialogue_manager_process_user_response_without_state_raises(
        self, error_handling_module
    ):
        """Test: both process_user_response and complete_recovery raise without state (line 773)"""
        ErrorDialogueManager = error_handling_module.ErrorDialogueManager
        UserDecision = error_handling_module.UserDecision

        manager = ErrorDialogueManager(conversation_agent=MagicMock())

        # process_user_response without state
        with pytest.raises(ValueError, match="No active error dialogue"):
            await manager.process_user_response(UserDecision(action="retry", node_id="n1"))

        # complete_recovery without state (line 773)
        with pytest.raises(ValueError, match="No active error dialogue"):
            await manager.complete_recovery(success=True, result={})

    @pytest.mark.asyncio
    async def test_error_dialogue_manager_process_retry_sets_flags_and_complete_sets_resolution(
        self, error_handling_module
    ):
        ErrorDialogueManager = error_handling_module.ErrorDialogueManager
        UserDecision = error_handling_module.UserDecision

        manager = ErrorDialogueManager(conversation_agent=MagicMock())
        await manager.start_error_dialogue(node_id="n1", node_name="node", error=TimeoutError("t"))

        state = await manager.process_user_response(UserDecision(action="retry", node_id="n1"))
        assert state.user_chose_retry is True
        assert state.awaiting_user_response is False

        final = await manager.complete_recovery(success=True, result={"ok": True})
        assert final.resolved is True
        assert final.resolution_method == "retry"

    @pytest.mark.asyncio
    async def test_error_dialogue_manager_process_provide_data_stores_data(
        self, error_handling_module
    ):
        ErrorDialogueManager = error_handling_module.ErrorDialogueManager
        UserDecision = error_handling_module.UserDecision

        manager = ErrorDialogueManager(conversation_agent=MagicMock())
        await manager.start_error_dialogue(
            node_id="n1", node_name="node", error=KeyError("missing api_key")
        )

        state = await manager.process_user_response(
            UserDecision(action="provide_data", node_id="n1", data={"api_key": "k"})
        )
        assert state.awaiting_user_response is False
        assert state.supplemental_data == {"api_key": "k"}


class TestErrorLoggerAndEvents:
    # 2 tests

    def test_error_logger_log_error_appends_entry_and_defaults_context(self, error_handling_module):
        ErrorLogger = error_handling_module.ErrorLogger

        logger = ErrorLogger()
        entry = logger.log_error(
            node_id="n1",
            workflow_id="w1",
            error=ValueError("bad"),
            context=None,
        )

        assert len(logger.error_logs) == 1
        assert logger.error_logs[0] is entry
        assert entry.node_id == "n1"
        assert entry.workflow_id == "w1"
        assert entry.error_type == "ValueError"
        assert entry.error_message == "bad"
        assert isinstance(entry.timestamp, datetime)
        assert entry.context == {}

    def test_error_logger_log_recovery_attempt_appends_entry_and_events_default_timestamps(
        self, error_handling_module
    ):
        ErrorLogger = error_handling_module.ErrorLogger
        NodeErrorEvent = error_handling_module.NodeErrorEvent
        RecoveryAction = error_handling_module.RecoveryAction
        RecoveryCompleteEvent = error_handling_module.RecoveryCompleteEvent

        logger = ErrorLogger()
        entry = logger.log_recovery_attempt(
            node_id="n1",
            action=RecoveryAction.RETRY,
            attempt=1,
            success=False,
            next_action=RecoveryAction.ASK_USER,
        )

        assert len(logger.recovery_logs) == 1
        assert logger.recovery_logs[0] is entry
        assert entry.node_id == "n1"
        assert entry.action == RecoveryAction.RETRY
        assert entry.attempt == 1
        assert entry.success is False
        assert entry.next_action == RecoveryAction.ASK_USER
        assert isinstance(entry.timestamp, datetime)

        node_event = NodeErrorEvent()
        recovery_event = RecoveryCompleteEvent()
        assert isinstance(node_event.error_timestamp, datetime)
        assert isinstance(recovery_event.recovery_timestamp, datetime)
