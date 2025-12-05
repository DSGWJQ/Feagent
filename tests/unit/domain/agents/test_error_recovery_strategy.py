"""错误恢复策略测试 - 第五步：异常处理与重规划

测试错误分类到恢复策略的映射和执行逻辑。
遵循 TDD 流程，先编写测试，再实现功能。
"""

from unittest.mock import AsyncMock

import pytest


class TestRecoveryAction:
    """测试恢复动作枚举"""

    def test_recovery_action_should_have_retry(self):
        """RecoveryAction 应该包含 RETRY 动作

        场景：可重试错误的自动重试
        期望：有明确的 RETRY 动作
        """
        from src.domain.agents.error_handling import RecoveryAction

        assert hasattr(RecoveryAction, "RETRY")
        assert RecoveryAction.RETRY.value == "retry"

    def test_recovery_action_should_have_skip(self):
        """RecoveryAction 应该包含 SKIP 动作

        场景：非关键节点失败时跳过
        期望：有明确的 SKIP 动作
        """
        from src.domain.agents.error_handling import RecoveryAction

        assert hasattr(RecoveryAction, "SKIP")
        assert RecoveryAction.SKIP.value == "skip"

    def test_recovery_action_should_have_replan(self):
        """RecoveryAction 应该包含 REPLAN 动作

        场景：依赖失败需要重新规划执行路径
        期望：有明确的 REPLAN 动作
        """
        from src.domain.agents.error_handling import RecoveryAction

        assert hasattr(RecoveryAction, "REPLAN")
        assert RecoveryAction.REPLAN.value == "replan"

    def test_recovery_action_should_have_ask_user(self):
        """RecoveryAction 应该包含 ASK_USER 动作

        场景：需要用户决定如何处理
        期望：有明确的 ASK_USER 动作
        """
        from src.domain.agents.error_handling import RecoveryAction

        assert hasattr(RecoveryAction, "ASK_USER")
        assert RecoveryAction.ASK_USER.value == "ask_user"

    def test_recovery_action_should_have_abort(self):
        """RecoveryAction 应该包含 ABORT 动作

        场景：严重错误需要终止执行
        期望：有明确的 ABORT 动作
        """
        from src.domain.agents.error_handling import RecoveryAction

        assert hasattr(RecoveryAction, "ABORT")
        assert RecoveryAction.ABORT.value == "abort"

    def test_recovery_action_should_have_retry_with_backoff(self):
        """RecoveryAction 应该包含 RETRY_WITH_BACKOFF 动作

        场景：限流等需要指数退避重试
        期望：有明确的 RETRY_WITH_BACKOFF 动作
        """
        from src.domain.agents.error_handling import RecoveryAction

        assert hasattr(RecoveryAction, "RETRY_WITH_BACKOFF")
        assert RecoveryAction.RETRY_WITH_BACKOFF.value == "retry_backoff"


class TestRecoveryStrategyMapper:
    """测试恢复策略映射器"""

    def test_timeout_maps_to_retry_with_backoff(self):
        """TIMEOUT 应该映射到 RETRY_WITH_BACKOFF

        场景：超时通常是暂时性问题，适合指数退避重试
        期望：返回 RETRY_WITH_BACKOFF
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            RecoveryAction,
            RecoveryStrategyMapper,
        )

        mapper = RecoveryStrategyMapper()
        action = mapper.get_recovery_action(ErrorCategory.TIMEOUT)

        assert action == RecoveryAction.RETRY_WITH_BACKOFF

    def test_api_failure_maps_to_retry(self):
        """API_FAILURE 应该映射到 RETRY

        场景：API 调用失败可能是暂时的
        期望：返回 RETRY
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            RecoveryAction,
            RecoveryStrategyMapper,
        )

        mapper = RecoveryStrategyMapper()
        action = mapper.get_recovery_action(ErrorCategory.API_FAILURE)

        assert action == RecoveryAction.RETRY

    def test_rate_limited_maps_to_retry_with_backoff(self):
        """RATE_LIMITED 应该映射到 RETRY_WITH_BACKOFF

        场景：限流需要等待后重试
        期望：返回 RETRY_WITH_BACKOFF
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            RecoveryAction,
            RecoveryStrategyMapper,
        )

        mapper = RecoveryStrategyMapper()
        action = mapper.get_recovery_action(ErrorCategory.RATE_LIMITED)

        assert action == RecoveryAction.RETRY_WITH_BACKOFF

    def test_data_missing_maps_to_ask_user(self):
        """DATA_MISSING 应该映射到 ASK_USER

        场景：缺失数据需要用户提供
        期望：返回 ASK_USER
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            RecoveryAction,
            RecoveryStrategyMapper,
        )

        mapper = RecoveryStrategyMapper()
        action = mapper.get_recovery_action(ErrorCategory.DATA_MISSING)

        assert action == RecoveryAction.ASK_USER

    def test_validation_error_maps_to_ask_user(self):
        """VALIDATION_ERROR 应该映射到 ASK_USER

        场景：数据格式错误需要用户修正
        期望：返回 ASK_USER
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            RecoveryAction,
            RecoveryStrategyMapper,
        )

        mapper = RecoveryStrategyMapper()
        action = mapper.get_recovery_action(ErrorCategory.VALIDATION_ERROR)

        assert action == RecoveryAction.ASK_USER

    def test_dependency_error_maps_to_replan(self):
        """DEPENDENCY_ERROR 应该映射到 REPLAN

        场景：依赖节点失败需要重新规划执行路径
        期望：返回 REPLAN
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            RecoveryAction,
            RecoveryStrategyMapper,
        )

        mapper = RecoveryStrategyMapper()
        action = mapper.get_recovery_action(ErrorCategory.DEPENDENCY_ERROR)

        assert action == RecoveryAction.REPLAN

    def test_node_crash_maps_to_skip(self):
        """NODE_CRASH 应该映射到 SKIP

        场景：节点崩溃可以跳过继续执行
        期望：返回 SKIP
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            RecoveryAction,
            RecoveryStrategyMapper,
        )

        mapper = RecoveryStrategyMapper()
        action = mapper.get_recovery_action(ErrorCategory.NODE_CRASH)

        assert action == RecoveryAction.SKIP

    def test_resource_exhausted_maps_to_abort(self):
        """RESOURCE_EXHAUSTED 应该映射到 ABORT

        场景：资源耗尽无法继续执行
        期望：返回 ABORT
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            RecoveryAction,
            RecoveryStrategyMapper,
        )

        mapper = RecoveryStrategyMapper()
        action = mapper.get_recovery_action(ErrorCategory.RESOURCE_EXHAUSTED)

        assert action == RecoveryAction.ABORT

    def test_custom_mapping_override(self):
        """应该支持自定义映射覆盖默认策略

        场景：特定场景需要不同的恢复策略
        期望：自定义映射生效
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            RecoveryAction,
            RecoveryStrategyMapper,
        )

        custom_mapping = {ErrorCategory.TIMEOUT: RecoveryAction.ABORT}
        mapper = RecoveryStrategyMapper(custom_mapping=custom_mapping)

        action = mapper.get_recovery_action(ErrorCategory.TIMEOUT)

        assert action == RecoveryAction.ABORT


class TestRecoveryExecutor:
    """测试恢复执行器"""

    @pytest.mark.asyncio
    async def test_execute_retry_action(self):
        """执行 RETRY 动作应该重新执行失败的操作

        场景：API 调用失败后重试
        期望：调用重试逻辑并返回结果
        """
        from src.domain.agents.error_handling import (
            RecoveryAction,
            RecoveryContext,
            RecoveryExecutor,
        )

        # 模拟重试成功
        mock_operation = AsyncMock(return_value={"success": True})
        context = RecoveryContext(
            node_id="node_1",
            action=RecoveryAction.RETRY,
            retry_count=0,
            max_retries=3,
            original_error=ConnectionError("Connection failed"),
        )

        executor = RecoveryExecutor()
        result = await executor.execute(context, mock_operation)

        assert result.success is True
        mock_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_respects_max_retries(self):
        """重试应该遵守最大重试次数限制

        场景：重试多次仍然失败
        期望：达到最大重试次数后停止
        """
        from src.domain.agents.error_handling import (
            RecoveryAction,
            RecoveryContext,
            RecoveryExecutor,
        )

        # 模拟持续失败
        mock_operation = AsyncMock(side_effect=ConnectionError("Still failing"))
        context = RecoveryContext(
            node_id="node_1",
            action=RecoveryAction.RETRY,
            retry_count=3,  # 已达到最大重试次数
            max_retries=3,
            original_error=ConnectionError("Connection failed"),
        )

        executor = RecoveryExecutor()
        result = await executor.execute(context, mock_operation)

        assert result.success is False
        assert result.exhausted_retries is True

    @pytest.mark.asyncio
    async def test_execute_skip_action(self):
        """执行 SKIP 动作应该跳过当前节点

        场景：非关键节点失败
        期望：返回跳过结果，不执行操作
        """
        from src.domain.agents.error_handling import (
            RecoveryAction,
            RecoveryContext,
            RecoveryExecutor,
        )

        mock_operation = AsyncMock()
        context = RecoveryContext(
            node_id="node_1",
            action=RecoveryAction.SKIP,
            original_error=RuntimeError("Node crashed"),
        )

        executor = RecoveryExecutor()
        result = await executor.execute(context, mock_operation)

        assert result.skipped is True
        mock_operation.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_replan_action(self):
        """执行 REPLAN 动作应该触发重新规划

        场景：依赖节点失败需要调整执行计划
        期望：返回需要重新规划的标志
        """
        from src.domain.agents.error_handling import (
            RecoveryAction,
            RecoveryContext,
            RecoveryExecutor,
        )

        context = RecoveryContext(
            node_id="node_1",
            action=RecoveryAction.REPLAN,
            failed_dependencies=["node_0"],
            original_error=Exception("Dependency failed"),
        )

        executor = RecoveryExecutor()
        result = await executor.execute(context, AsyncMock())

        assert result.needs_replan is True
        assert "node_0" in result.failed_dependencies

    @pytest.mark.asyncio
    async def test_execute_ask_user_action(self):
        """执行 ASK_USER 动作应该暂停等待用户输入

        场景：缺失数据需要用户提供
        期望：返回等待用户输入的标志
        """
        from src.domain.agents.error_handling import (
            RecoveryAction,
            RecoveryContext,
            RecoveryExecutor,
        )

        context = RecoveryContext(
            node_id="node_1",
            action=RecoveryAction.ASK_USER,
            original_error=KeyError("missing_field"),
        )

        executor = RecoveryExecutor()
        result = await executor.execute(context, AsyncMock())

        assert result.awaiting_user_input is True
        assert result.user_prompt is not None

    @pytest.mark.asyncio
    async def test_execute_abort_action(self):
        """执行 ABORT 动作应该终止整个工作流

        场景：严重错误无法恢复
        期望：返回终止标志
        """
        from src.domain.agents.error_handling import (
            RecoveryAction,
            RecoveryContext,
            RecoveryExecutor,
        )

        context = RecoveryContext(
            node_id="node_1",
            action=RecoveryAction.ABORT,
            original_error=MemoryError("Out of memory"),
        )

        executor = RecoveryExecutor()
        result = await executor.execute(context, AsyncMock())

        assert result.aborted is True
        assert result.abort_reason is not None


class TestRetryWithBackoff:
    """测试指数退避重试"""

    @pytest.mark.asyncio
    async def test_backoff_delay_increases_exponentially(self):
        """退避延迟应该指数增长

        场景：限流后需要逐渐增加等待时间
        期望：延迟时间呈指数增长
        """
        from src.domain.agents.error_handling import BackoffCalculator

        calculator = BackoffCalculator(base_delay=1.0, max_delay=60.0, factor=2.0)

        delay_0 = calculator.get_delay(attempt=0)
        delay_1 = calculator.get_delay(attempt=1)
        delay_2 = calculator.get_delay(attempt=2)

        assert delay_0 == 1.0
        assert delay_1 == 2.0
        assert delay_2 == 4.0

    @pytest.mark.asyncio
    async def test_backoff_delay_capped_at_max(self):
        """退避延迟应该有最大值限制

        场景：避免等待时间过长
        期望：延迟不超过最大值
        """
        from src.domain.agents.error_handling import BackoffCalculator

        calculator = BackoffCalculator(base_delay=1.0, max_delay=10.0, factor=2.0)

        delay_10 = calculator.get_delay(attempt=10)  # 2^10 = 1024 > 10

        assert delay_10 == 10.0

    @pytest.mark.asyncio
    async def test_backoff_with_jitter(self):
        """退避延迟应该支持抖动

        场景：避免多个客户端同时重试
        期望：延迟有随机抖动
        """
        from src.domain.agents.error_handling import BackoffCalculator

        calculator = BackoffCalculator(base_delay=1.0, max_delay=60.0, jitter=0.1)

        delays = [calculator.get_delay_with_jitter(attempt=1) for _ in range(10)]

        # 延迟应该在 1.8 到 2.2 之间（2.0 ± 10%）
        assert all(1.8 <= d <= 2.2 for d in delays)
        # 延迟应该有变化
        assert len(set(delays)) > 1


class TestErrorRecoveryIntegration:
    """测试错误恢复的集成场景"""

    @pytest.mark.asyncio
    async def test_full_error_recovery_flow(self):
        """完整的错误分类→策略→执行流程

        场景：节点执行抛出 TimeoutError
        期望：正确分类、选择策略、执行恢复
        """
        from src.domain.agents.error_handling import (
            ErrorCategory,
            ErrorRecoveryHandler,
            RecoveryAction,
        )

        handler = ErrorRecoveryHandler()

        # 模拟节点执行失败
        error = TimeoutError("API call timed out")

        # 完整恢复流程
        recovery_plan = handler.create_recovery_plan(node_id="api_node_1", error=error, attempt=0)

        assert recovery_plan.category == ErrorCategory.TIMEOUT
        assert recovery_plan.action == RecoveryAction.RETRY_WITH_BACKOFF
        assert recovery_plan.delay > 0

    @pytest.mark.asyncio
    async def test_recovery_with_user_response(self):
        """用户响应后继续执行

        场景：DATA_MISSING 错误后用户提供了数据
        期望：使用用户提供的数据继续执行
        """
        from src.domain.agents.error_handling import (
            ErrorRecoveryHandler,
            UserResponse,
        )

        handler = ErrorRecoveryHandler()

        # 第一阶段：创建需要用户输入的恢复计划
        error = KeyError("api_key")
        recovery_plan = handler.create_recovery_plan(node_id="config_node", error=error, attempt=0)

        assert recovery_plan.awaiting_user_input is True

        # 第二阶段：用户提供响应
        user_response = UserResponse(action="provide_data", data={"api_key": "sk-xxx123"})

        updated_plan = handler.apply_user_response(recovery_plan, user_response)

        assert updated_plan.ready_to_retry is True
        assert updated_plan.supplemental_data == {"api_key": "sk-xxx123"}

    @pytest.mark.asyncio
    async def test_recovery_escalation(self):
        """多次重试失败后升级处理

        场景：重试达到上限但仍失败
        期望：升级为需要用户干预
        """
        from src.domain.agents.error_handling import (
            ErrorRecoveryHandler,
            RecoveryAction,
        )

        handler = ErrorRecoveryHandler(max_retries=3)

        error = ConnectionError("Connection refused")

        # 模拟多次重试失败
        for attempt in range(3):
            recovery_plan = handler.create_recovery_plan(
                node_id="api_node", error=error, attempt=attempt
            )

        # 第四次应该升级为询问用户
        final_plan = handler.create_recovery_plan(node_id="api_node", error=error, attempt=3)

        assert final_plan.action == RecoveryAction.ASK_USER
        assert final_plan.escalated is True
