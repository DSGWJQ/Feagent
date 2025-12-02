"""执行结果标准化测试 - Phase 11

TDD RED阶段：测试结构化执行结果和失败标准

业务场景：
- 节点执行返回结构化结果（成功/错误码/可重试）
- 根据规则判断失败（超过重试次数、输出校验不合格）
- 支持自动重试可重试的错误
"""

import asyncio

import pytest

# ============ Phase 11.1: 结构化执行结果 ============


class TestExecutionResult:
    """ExecutionResult 数据结构测试"""

    def test_success_result(self):
        """成功结果应包含正确的属性"""
        from src.domain.services.execution_result import ErrorCode, ExecutionResult

        result = ExecutionResult.ok(output={"data": "processed"})

        assert result.success is True
        assert result.error_code == ErrorCode.SUCCESS
        assert result.error_message is None
        assert result.retryable is False
        assert result.output == {"data": "processed"}

    def test_failure_result_with_retryable_error(self):
        """可重试的失败结果"""
        from src.domain.services.execution_result import ErrorCode, ExecutionResult

        result = ExecutionResult.failure(
            error_code=ErrorCode.TIMEOUT,
            error_message="Node execution timed out",
        )

        assert result.success is False
        assert result.error_code == ErrorCode.TIMEOUT
        assert result.retryable is True
        assert result.error_message == "Node execution timed out"

    def test_failure_result_with_non_retryable_error(self):
        """不可重试的失败结果"""
        from src.domain.services.execution_result import ErrorCode, ExecutionResult

        result = ExecutionResult.failure(
            error_code=ErrorCode.VALIDATION_FAILED,
            error_message="Output validation failed",
        )

        assert result.success is False
        assert result.error_code == ErrorCode.VALIDATION_FAILED
        assert result.retryable is False

    def test_result_metadata(self):
        """结果应包含执行元数据"""
        from src.domain.services.execution_result import ExecutionResult

        result = ExecutionResult.ok(
            output={"data": "test"},
            metadata={
                "execution_time_ms": 150,
                "retry_count": 2,
                "node_id": "node_1",
            },
        )

        assert result.metadata["execution_time_ms"] == 150
        assert result.metadata["retry_count"] == 2

    def test_result_to_dict(self):
        """结果应能序列化为字典"""
        from src.domain.services.execution_result import ExecutionResult

        result = ExecutionResult.ok(output={"value": 42})
        data = result.to_dict()

        assert data["success"] is True
        assert data["error_code"] == "SUCCESS"
        assert data["output"] == {"value": 42}

    def test_result_from_exception(self):
        """应能从异常创建失败结果"""
        from src.domain.services.execution_result import ErrorCode, ExecutionResult

        try:
            raise TimeoutError("Operation timed out")
        except TimeoutError as e:
            result = ExecutionResult.from_exception(e)

        assert result.success is False
        assert result.error_code == ErrorCode.TIMEOUT
        assert result.retryable is True


# ============ Phase 11.2: 错误码和重试策略 ============


class TestErrorCode:
    """错误码测试"""

    def test_all_error_codes_defined(self):
        """应定义所有必要的错误码"""
        from src.domain.services.execution_result import ErrorCode

        assert hasattr(ErrorCode, "SUCCESS")
        assert hasattr(ErrorCode, "TIMEOUT")
        assert hasattr(ErrorCode, "VALIDATION_FAILED")
        assert hasattr(ErrorCode, "NETWORK_ERROR")
        assert hasattr(ErrorCode, "RESOURCE_LIMIT")
        assert hasattr(ErrorCode, "INTERNAL_ERROR")
        assert hasattr(ErrorCode, "DEPENDENCY_FAILED")

    def test_retryable_error_codes(self):
        """应能判断错误码是否可重试"""
        from src.domain.services.execution_result import ErrorCode

        assert ErrorCode.TIMEOUT.is_retryable() is True
        assert ErrorCode.NETWORK_ERROR.is_retryable() is True
        assert ErrorCode.RESOURCE_LIMIT.is_retryable() is True
        assert ErrorCode.VALIDATION_FAILED.is_retryable() is False
        assert ErrorCode.INTERNAL_ERROR.is_retryable() is False


class TestRetryPolicy:
    """重试策略测试"""

    def test_default_retry_policy(self):
        """默认重试策略"""
        from src.domain.services.execution_result import RetryPolicy

        policy = RetryPolicy()

        assert policy.max_retries == 3
        assert policy.base_delay == 1.0
        assert policy.exponential_backoff is True

    def test_custom_retry_policy(self):
        """自定义重试策略"""
        from src.domain.services.execution_result import RetryPolicy

        policy = RetryPolicy(
            max_retries=5,
            base_delay=0.5,
            exponential_backoff=False,
            max_delay=10.0,
        )

        assert policy.max_retries == 5
        assert policy.base_delay == 0.5

    def test_calculate_delay_with_exponential_backoff(self):
        """指数退避延迟计算"""
        from src.domain.services.execution_result import RetryPolicy

        policy = RetryPolicy(base_delay=1.0, exponential_backoff=True)

        assert policy.get_delay(attempt=0) == 1.0
        assert policy.get_delay(attempt=1) == 2.0
        assert policy.get_delay(attempt=2) == 4.0

    def test_calculate_delay_with_max_limit(self):
        """延迟应有最大限制"""
        from src.domain.services.execution_result import RetryPolicy

        policy = RetryPolicy(base_delay=1.0, max_delay=5.0, exponential_backoff=True)

        # 第 10 次重试理论上是 1024 秒，但应该被限制在 5 秒
        assert policy.get_delay(attempt=10) == 5.0

    def test_should_retry(self):
        """判断是否应该重试"""
        from src.domain.services.execution_result import ErrorCode, RetryPolicy

        policy = RetryPolicy(max_retries=3)

        assert policy.should_retry(ErrorCode.TIMEOUT, attempt=0) is True
        assert policy.should_retry(ErrorCode.TIMEOUT, attempt=2) is True
        assert policy.should_retry(ErrorCode.TIMEOUT, attempt=3) is False  # 已达最大
        assert policy.should_retry(ErrorCode.VALIDATION_FAILED, attempt=0) is False


# ============ Phase 11.3: 输出校验器 ============


class TestOutputValidator:
    """输出校验器测试"""

    def test_validate_required_fields(self):
        """校验必填字段"""
        from src.domain.services.execution_result import OutputValidator

        validator = OutputValidator(
            schema={
                "result": {"type": "string", "required": True},
                "count": {"type": "integer", "required": True},
            }
        )

        # 有效输出
        assert validator.validate({"result": "ok", "count": 10}).is_valid is True

        # 缺少必填字段
        result = validator.validate({"result": "ok"})
        assert result.is_valid is False
        assert "count" in result.error_message

    def test_validate_field_types(self):
        """校验字段类型"""
        from src.domain.services.execution_result import OutputValidator

        validator = OutputValidator(
            schema={
                "count": {"type": "integer"},
                "name": {"type": "string"},
            }
        )

        # 类型正确
        assert validator.validate({"count": 10, "name": "test"}).is_valid is True

        # 类型错误
        result = validator.validate({"count": "not_a_number", "name": "test"})
        assert result.is_valid is False

    def test_validate_custom_constraints(self):
        """校验自定义约束"""
        from src.domain.services.execution_result import OutputValidator

        validator = OutputValidator(
            schema={"score": {"type": "number"}},
            constraints=[
                lambda output: output.get("score", 0) >= 0,
                lambda output: output.get("score", 0) <= 100,
            ],
        )

        assert validator.validate({"score": 50}).is_valid is True
        assert validator.validate({"score": -10}).is_valid is False
        assert validator.validate({"score": 150}).is_valid is False

    def test_validation_result_details(self):
        """校验结果应包含详细信息"""
        from src.domain.services.execution_result import OutputValidator

        validator = OutputValidator(schema={"data": {"type": "array", "required": True}})

        result = validator.validate({})

        assert result.is_valid is False
        assert result.error_message is not None
        assert result.failed_field == "data"


# ============ Phase 11.4: 增强的 execute_node ============


class TestExecuteNodeWithRetry:
    """带重试的节点执行测试"""

    @pytest.mark.asyncio
    async def test_execute_node_returns_structured_result(self):
        """execute_node 应返回结构化结果"""
        from src.domain.services.execution_result import ExecutionResult
        from tests.unit.domain.agents.test_workflow_agent_enhanced import (
            create_workflow_agent_for_test,
        )

        agent = create_workflow_agent_for_test()

        node = agent.create_node(
            {
                "node_type": "code",
                "config": {"code": "x = 1"},
            }
        )
        agent.add_node(node)

        result = await agent.execute_node_with_result(node.id)

        assert isinstance(result, ExecutionResult)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_node_auto_retry_on_timeout(self):
        """超时时应自动重试"""
        from src.domain.services.execution_result import RetryPolicy
        from tests.unit.domain.agents.test_workflow_agent_enhanced import (
            create_workflow_agent_for_test,
        )

        agent = create_workflow_agent_for_test()

        # 模拟一个会超时的执行器
        call_count = 0

        class TimeoutExecutor:
            async def execute(self, node_id, config, inputs):
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise TimeoutError("Timed out")
                return {"status": "success"}

        agent.node_executor = TimeoutExecutor()

        node = agent.create_node({"node_type": "code", "config": {}})
        agent.add_node(node)

        policy = RetryPolicy(max_retries=3, base_delay=0.01)
        result = await agent.execute_node_with_result(node.id, retry_policy=policy)

        assert result.success is True
        assert call_count == 3  # 前两次失败，第三次成功

    @pytest.mark.asyncio
    async def test_execute_node_fails_after_max_retries(self):
        """超过最大重试次数应失败"""
        from src.domain.services.execution_result import ErrorCode, RetryPolicy
        from tests.unit.domain.agents.test_workflow_agent_enhanced import (
            create_workflow_agent_for_test,
        )

        agent = create_workflow_agent_for_test()

        class AlwaysTimeoutExecutor:
            async def execute(self, node_id, config, inputs):
                raise TimeoutError("Always times out")

        agent.node_executor = AlwaysTimeoutExecutor()

        node = agent.create_node({"node_type": "code", "config": {}})
        agent.add_node(node)

        policy = RetryPolicy(max_retries=2, base_delay=0.01)
        result = await agent.execute_node_with_result(node.id, retry_policy=policy)

        assert result.success is False
        assert result.error_code == ErrorCode.TIMEOUT
        assert result.metadata.get("retry_count", 0) >= 2

    @pytest.mark.asyncio
    async def test_execute_node_no_retry_on_validation_error(self):
        """校验错误不应重试"""
        from src.domain.services.execution_result import RetryPolicy
        from tests.unit.domain.agents.test_workflow_agent_enhanced import (
            create_workflow_agent_for_test,
        )

        agent = create_workflow_agent_for_test()

        call_count = 0

        class ValidationErrorExecutor:
            async def execute(self, node_id, config, inputs):
                nonlocal call_count
                call_count += 1
                raise ValueError("Invalid input data")

        agent.node_executor = ValidationErrorExecutor()

        node = agent.create_node({"node_type": "code", "config": {}})
        agent.add_node(node)

        policy = RetryPolicy(max_retries=3, base_delay=0.01)
        result = await agent.execute_node_with_result(node.id, retry_policy=policy)

        assert result.success is False
        assert call_count == 1  # 不应重试


class TestExecuteNodeWithValidation:
    """带输出校验的节点执行测试"""

    @pytest.mark.asyncio
    async def test_execute_node_validates_output(self):
        """应校验节点输出"""
        from src.domain.services.execution_result import OutputValidator
        from tests.unit.domain.agents.test_workflow_agent_enhanced import (
            create_workflow_agent_for_test,
        )

        agent = create_workflow_agent_for_test()

        class GoodOutputExecutor:
            async def execute(self, node_id, config, inputs):
                return {"result": "success", "count": 10}

        agent.node_executor = GoodOutputExecutor()

        node = agent.create_node({"node_type": "code", "config": {}})
        agent.add_node(node)

        validator = OutputValidator(
            schema={
                "result": {"type": "string", "required": True},
                "count": {"type": "integer", "required": True},
            }
        )

        result = await agent.execute_node_with_result(node.id, output_validator=validator)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_node_fails_on_invalid_output(self):
        """输出校验失败应返回失败结果"""
        from src.domain.services.execution_result import ErrorCode, OutputValidator
        from tests.unit.domain.agents.test_workflow_agent_enhanced import (
            create_workflow_agent_for_test,
        )

        agent = create_workflow_agent_for_test()

        class BadOutputExecutor:
            async def execute(self, node_id, config, inputs):
                return {"wrong_field": "value"}  # 缺少必填字段

        agent.node_executor = BadOutputExecutor()

        node = agent.create_node({"node_type": "code", "config": {}})
        agent.add_node(node)

        validator = OutputValidator(schema={"result": {"type": "string", "required": True}})

        result = await agent.execute_node_with_result(node.id, output_validator=validator)

        assert result.success is False
        assert result.error_code == ErrorCode.VALIDATION_FAILED


# ============ Phase 11.5: 真实场景集成测试 ============


class TestRealWorldExecutionScenarios:
    """真实场景执行测试"""

    @pytest.mark.asyncio
    async def test_api_call_with_network_retry(self):
        """场景：API 调用网络错误重试"""
        from src.domain.services.execution_result import (
            RetryPolicy,
        )
        from tests.unit.domain.agents.test_workflow_agent_enhanced import (
            create_workflow_agent_for_test,
        )

        agent = create_workflow_agent_for_test()

        # 模拟不稳定的网络
        call_count = 0

        class UnstableNetworkExecutor:
            async def execute(self, node_id, config, inputs):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    raise ConnectionError("Network unreachable")
                return {"api_response": {"status": "ok"}}

        agent.node_executor = UnstableNetworkExecutor()

        node = agent.create_node(
            {
                "node_type": "http",
                "config": {"url": "https://api.example.com/data"},
            }
        )
        agent.add_node(node)

        policy = RetryPolicy(max_retries=5, base_delay=0.01)
        result = await agent.execute_node_with_result(node.id, retry_policy=policy)

        assert result.success is True
        assert result.output["api_response"]["status"] == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_data_processing_with_validation(self):
        """场景：数据处理节点输出校验"""
        from src.domain.services.execution_result import OutputValidator
        from tests.unit.domain.agents.test_workflow_agent_enhanced import (
            create_workflow_agent_for_test,
        )

        agent = create_workflow_agent_for_test()

        class DataProcessorExecutor:
            async def execute(self, node_id, config, inputs):
                # 模拟数据处理
                return {
                    "processed_count": 100,
                    "success_rate": 0.95,
                    "records": [{"id": 1}, {"id": 2}],
                }

        agent.node_executor = DataProcessorExecutor()

        node = agent.create_node(
            {
                "node_type": "code",
                "config": {"code": "process_data()"},
            }
        )
        agent.add_node(node)

        validator = OutputValidator(
            schema={
                "processed_count": {"type": "integer", "required": True},
                "success_rate": {"type": "number", "required": True},
            },
            constraints=[
                lambda o: o.get("success_rate", 0) >= 0.9,  # 成功率必须 >= 90%
            ],
        )

        result = await agent.execute_node_with_result(node.id, output_validator=validator)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_llm_call_with_timeout_retry(self):
        """场景：LLM 调用超时重试"""
        from src.domain.services.execution_result import RetryPolicy
        from tests.unit.domain.agents.test_workflow_agent_enhanced import (
            create_workflow_agent_for_test,
        )

        agent = create_workflow_agent_for_test()

        call_count = 0

        class SlowLLMExecutor:
            async def execute(self, node_id, config, inputs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise TimeoutError("LLM response too slow")
                return {"content": "Generated response", "tokens_used": 150}

        agent.node_executor = SlowLLMExecutor()

        node = agent.create_node(
            {
                "node_type": "code",  # 使用 code 类型避免 LLM 配置校验
                "config": {"code": "summarize()"},
            }
        )
        agent.add_node(node)

        policy = RetryPolicy(max_retries=3, base_delay=0.01)
        result = await agent.execute_node_with_result(node.id, retry_policy=policy)

        assert result.success is True
        assert "content" in result.output

    @pytest.mark.asyncio
    async def test_workflow_execution_with_node_failure(self):
        """场景：工作流中某个节点失败"""
        from tests.unit.domain.agents.test_workflow_agent_enhanced import (
            create_workflow_agent_for_test,
        )

        agent = create_workflow_agent_for_test()

        executed_nodes = []

        class PartialFailureExecutor:
            async def execute(self, node_id, config, inputs):
                executed_nodes.append(node_id)
                if config.get("should_fail"):
                    raise RuntimeError("Critical error")
                return {"status": "ok"}

        agent.node_executor = PartialFailureExecutor()

        # 创建工作流：node1 -> node2(失败) -> node3
        node1 = agent.create_node({"node_type": "code", "config": {"step": 1}})
        node2 = agent.create_node({"node_type": "code", "config": {"should_fail": True}})
        node3 = agent.create_node({"node_type": "code", "config": {"step": 3}})

        agent.add_node(node1)
        agent.add_node(node2)
        agent.add_node(node3)

        agent.connect_nodes(node1.id, node2.id)
        agent.connect_nodes(node2.id, node3.id)

        # 执行工作流
        workflow_result = await agent.execute_workflow_with_results()

        assert workflow_result.success is False
        assert workflow_result.failed_node_id == node2.id
        assert node3.id not in executed_nodes  # node3 不应执行

    @pytest.mark.asyncio
    async def test_execution_result_includes_timing_info(self):
        """执行结果应包含时间信息"""
        from tests.unit.domain.agents.test_workflow_agent_enhanced import (
            create_workflow_agent_for_test,
        )

        agent = create_workflow_agent_for_test()

        class SlowExecutor:
            async def execute(self, node_id, config, inputs):
                await asyncio.sleep(0.05)  # 50ms
                return {"result": "done"}

        agent.node_executor = SlowExecutor()

        node = agent.create_node({"node_type": "code", "config": {}})
        agent.add_node(node)

        result = await agent.execute_node_with_result(node.id)

        assert result.success is True
        assert "execution_time_ms" in result.metadata
        assert result.metadata["execution_time_ms"] >= 50

    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff(self):
        """测试指数退避重试"""
        from src.domain.services.execution_result import RetryPolicy
        from tests.unit.domain.agents.test_workflow_agent_enhanced import (
            create_workflow_agent_for_test,
        )

        agent = create_workflow_agent_for_test()

        retry_timestamps = []

        class TimingExecutor:
            async def execute(self, node_id, config, inputs):
                import time

                retry_timestamps.append(time.time())
                if len(retry_timestamps) < 3:
                    raise TimeoutError("Retry me")
                return {"done": True}

        agent.node_executor = TimingExecutor()

        node = agent.create_node({"node_type": "code", "config": {}})
        agent.add_node(node)

        # 使用很短的延迟便于测试
        policy = RetryPolicy(
            max_retries=5,
            base_delay=0.02,  # 20ms
            exponential_backoff=True,
        )

        result = await agent.execute_node_with_result(node.id, retry_policy=policy)

        assert result.success is True
        assert len(retry_timestamps) == 3

        # 验证延迟增加（指数退避）
        if len(retry_timestamps) >= 3:
            delay1 = retry_timestamps[1] - retry_timestamps[0]
            delay2 = retry_timestamps[2] - retry_timestamps[1]
            # delay2 应该大于 delay1（指数退避）
            assert delay2 > delay1 * 1.5  # 允许一些误差
