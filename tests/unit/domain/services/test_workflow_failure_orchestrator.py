"""WorkflowFailureOrchestrator 单元测试

测试失败处理编排器的四种策略：RETRY、SKIP、ABORT、REPLAN
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =====================================================================
# Mock Dependencies
# =====================================================================


class FailureHandlingStrategy(str, Enum):
    """失败处理策略枚举"""

    RETRY = "retry"
    SKIP = "skip"
    ABORT = "abort"
    REPLAN = "replan"


@dataclass
class FailureHandlingResult:
    """失败处理结果"""

    success: bool = False
    skipped: bool = False
    aborted: bool = False
    retry_count: int = 0
    output: dict[str, Any] = field(default_factory=dict)
    error_message: str = ""


class ErrorCode:
    """模拟错误码类"""

    def __init__(self, retryable: bool = True):
        self._retryable = retryable

    def is_retryable(self) -> bool:
        return self._retryable


# =====================================================================
# Test Fixtures
# =====================================================================


@pytest.fixture
def mock_event_bus():
    """Mock EventBus"""
    bus = MagicMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def mock_workflow_states():
    """Mock workflow states dictionary"""
    return {
        "workflow_1": {
            "workflow_id": "workflow_1",
            "status": "running",
            "executed_nodes": ["node_a"],
            "failed_nodes": ["node_b"],
            "node_outputs": {"node_a": {"result": "ok"}},
            "skipped_nodes": [],
        }
    }


@pytest.fixture
def mock_workflow_agent():
    """Mock WorkflowAgent"""
    agent = MagicMock()
    agent.execute_node_with_result = AsyncMock()
    return agent


@pytest.fixture
def mock_workflow_agents_registry(mock_workflow_agent):
    """Mock workflow agents registry"""
    return {"workflow_1": mock_workflow_agent}


@pytest.fixture
def orchestrator_config():
    """默认配置"""
    return {
        "default_strategy": FailureHandlingStrategy.RETRY,
        "max_retries": 3,
        "retry_delay": 1.0,
    }


@pytest.fixture
def orchestrator(
    mock_event_bus,
    mock_workflow_states,
    mock_workflow_agents_registry,
    orchestrator_config,
):
    """WorkflowFailureOrchestrator 实例"""
    from src.domain.services.workflow_failure_orchestrator import (
        WorkflowFailureOrchestrator,
    )

    return WorkflowFailureOrchestrator(
        event_bus=mock_event_bus,
        state_accessor=lambda wf_id: mock_workflow_states.get(wf_id),
        state_mutator=lambda wf_id: mock_workflow_states.setdefault(wf_id, {}),
        workflow_agent_resolver=lambda wf_id: mock_workflow_agents_registry.get(wf_id),
        config=orchestrator_config,
    )


# =====================================================================
# Test: 配置与策略管理
# =====================================================================


def test_orchestrator_initialization(orchestrator):
    """测试编排器初始化配置"""
    assert orchestrator.config["default_strategy"] == FailureHandlingStrategy.RETRY
    assert orchestrator.config["max_retries"] == 3
    assert orchestrator.config["retry_delay"] == 1.0
    assert orchestrator._node_strategies == {}


def test_set_node_strategy(orchestrator):
    """测试设置节点失败策略"""
    orchestrator.set_node_strategy("node_critical", FailureHandlingStrategy.ABORT)
    assert orchestrator._node_strategies["node_critical"] == FailureHandlingStrategy.ABORT


def test_get_node_strategy_with_override(orchestrator):
    """测试获取节点策略（存在覆盖）"""
    orchestrator.set_node_strategy("node_skip", FailureHandlingStrategy.SKIP)
    strategy = orchestrator.get_node_strategy("node_skip")
    assert strategy == FailureHandlingStrategy.SKIP


def test_get_node_strategy_default_fallback(orchestrator):
    """测试获取节点策略（回退到默认）"""
    strategy = orchestrator.get_node_strategy("node_unknown")
    assert strategy == FailureHandlingStrategy.RETRY


def test_register_workflow_agent(orchestrator, mock_workflow_agents_registry):
    """测试注册 WorkflowAgent"""
    new_agent = MagicMock()
    orchestrator.register_workflow_agent("workflow_2", new_agent)
    mock_workflow_agents_registry["workflow_2"] = new_agent
    assert orchestrator._resolve_agent("workflow_2") == new_agent


# =====================================================================
# Test: RETRY 策略
# =====================================================================


@pytest.mark.asyncio
async def test_retry_success_on_first_attempt(
    orchestrator, mock_workflow_agent, mock_event_bus, mock_workflow_states
):
    """测试重试策略 - 第一次尝试成功"""
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.output = {"result": "fixed"}
    mock_workflow_agent.execute_node_with_result = AsyncMock(return_value=mock_result)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await orchestrator.handle_node_failure(
            workflow_id="workflow_1",
            node_id="node_b",
            error_code=ErrorCode(retryable=True),
            error_message="Temporary error",
        )

    assert result.success is True
    assert result.retry_count == 1
    assert result.output == {"result": "fixed"}
    assert "node_b" in mock_workflow_states["workflow_1"]["executed_nodes"]
    assert "node_b" not in mock_workflow_states["workflow_1"]["failed_nodes"]
    mock_event_bus.publish.assert_called_once()


@pytest.mark.asyncio
async def test_retry_exhaustion_after_max_attempts(
    orchestrator, mock_workflow_agent, mock_event_bus
):
    """测试重试策略 - 重试耗尽"""
    mock_result = MagicMock()
    mock_result.success = False
    mock_workflow_agent.execute_node_with_result = AsyncMock(return_value=mock_result)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await orchestrator.handle_node_failure(
            workflow_id="workflow_1",
            node_id="node_b",
            error_code=ErrorCode(retryable=True),
            error_message="Persistent error",
        )

    assert result.success is False
    assert result.retry_count == 3
    assert "Max retries" in result.error_message

    # 修复：重试耗尽时应发布失败事件
    mock_event_bus.publish.assert_called_once()
    published_event = mock_event_bus.publish.call_args[0][0]
    assert published_event.workflow_id == "workflow_1"
    assert published_event.node_id == "node_b"
    assert published_event.strategy == "retry"
    assert published_event.success is False
    assert published_event.retry_count == 3


@pytest.mark.asyncio
async def test_non_retryable_error_short_circuits(orchestrator, mock_event_bus):
    """测试非可重试错误直接返回失败"""
    result = await orchestrator.handle_node_failure(
        workflow_id="workflow_1",
        node_id="node_b",
        error_code=ErrorCode(retryable=False),
        error_message="Fatal error",
    )

    assert result.success is False
    assert result.retry_count == 0
    assert "Non-retryable error" in result.error_message

    # 修复：不可重试错误也应发布失败事件
    mock_event_bus.publish.assert_called_once()
    published_event = mock_event_bus.publish.call_args[0][0]
    assert published_event.workflow_id == "workflow_1"
    assert published_event.node_id == "node_b"
    assert published_event.success is False
    assert published_event.retry_count == 0


@pytest.mark.asyncio
async def test_retry_without_workflow_agent_fails(
    orchestrator, mock_event_bus, mock_workflow_agents_registry
):
    """测试重试策略 - 缺少 WorkflowAgent"""
    mock_workflow_agents_registry.pop("workflow_1")

    result = await orchestrator.handle_node_failure(
        workflow_id="workflow_1",
        node_id="node_b",
        error_code=ErrorCode(retryable=True),
        error_message="Error",
    )

    assert result.success is False
    assert "No WorkflowAgent" in result.error_message
    mock_event_bus.publish.assert_not_called()


# =====================================================================
# Test: SKIP 策略
# =====================================================================


@pytest.mark.asyncio
async def test_skip_strategy_marks_node_skipped(orchestrator, mock_event_bus, mock_workflow_states):
    """测试 SKIP 策略标记节点为跳过"""
    orchestrator.set_node_strategy("node_b", FailureHandlingStrategy.SKIP)

    result = await orchestrator.handle_node_failure(
        workflow_id="workflow_1",
        node_id="node_b",
        error_code=ErrorCode(retryable=True),
        error_message="Skippable error",
    )

    assert result.success is True
    assert result.skipped is True
    assert "node_b" in mock_workflow_states["workflow_1"]["skipped_nodes"]
    assert "node_b" not in mock_workflow_states["workflow_1"]["failed_nodes"]
    mock_event_bus.publish.assert_called_once()


@pytest.mark.asyncio
async def test_skip_strategy_without_event_bus(orchestrator, mock_workflow_states):
    """测试 SKIP 策略 - 无 EventBus"""
    orchestrator.event_bus = None
    orchestrator.set_node_strategy("node_b", FailureHandlingStrategy.SKIP)

    result = await orchestrator.handle_node_failure(
        workflow_id="workflow_1",
        node_id="node_b",
        error_code=ErrorCode(retryable=True),
        error_message="Skippable error",
    )

    assert result.success is True
    assert result.skipped is True


# =====================================================================
# Test: ABORT 策略
# =====================================================================


@pytest.mark.asyncio
async def test_abort_strategy_sets_workflow_aborted(
    orchestrator, mock_event_bus, mock_workflow_states
):
    """测试 ABORT 策略终止工作流"""
    orchestrator.set_node_strategy("node_b", FailureHandlingStrategy.ABORT)

    result = await orchestrator.handle_node_failure(
        workflow_id="workflow_1",
        node_id="node_b",
        error_code=ErrorCode(retryable=True),
        error_message="Critical error",
    )

    assert result.success is False
    assert result.aborted is True
    assert mock_workflow_states["workflow_1"]["status"] == "aborted"
    mock_event_bus.publish.assert_called_once()


# =====================================================================
# Test: REPLAN 策略
# =====================================================================


@pytest.mark.asyncio
async def test_replan_strategy_publishes_adjustment_event(
    orchestrator, mock_event_bus, mock_workflow_states
):
    """测试 REPLAN 策略发布重新规划事件"""
    orchestrator.set_node_strategy("node_b", FailureHandlingStrategy.REPLAN)

    result = await orchestrator.handle_node_failure(
        workflow_id="workflow_1",
        node_id="node_b",
        error_code=ErrorCode(retryable=True),
        error_message="Needs replanning",
    )

    assert result.success is False
    assert "Replan requested" in result.error_message
    mock_event_bus.publish.assert_called_once()

    published_event = mock_event_bus.publish.call_args[0][0]
    assert published_event.workflow_id == "workflow_1"
    assert published_event.failed_node_id == "node_b"
    assert "executed_nodes" in published_event.execution_context


@pytest.mark.asyncio
async def test_replan_without_workflow_state(orchestrator, mock_event_bus):
    """测试 REPLAN 策略 - 缺少工作流状态"""
    orchestrator.set_node_strategy("node_unknown", FailureHandlingStrategy.REPLAN)

    result = await orchestrator.handle_node_failure(
        workflow_id="workflow_missing",
        node_id="node_unknown",
        error_code=ErrorCode(retryable=True),
        error_message="Error",
    )

    assert result.success is False
    mock_event_bus.publish.assert_called_once()


# =====================================================================
# Test: 边界情况
# =====================================================================


@pytest.mark.asyncio
async def test_config_max_retries_override(
    mock_event_bus,
    mock_workflow_states,
    mock_workflow_agents_registry,
):
    """测试配置覆盖 - max_retries"""
    custom_config = {
        "default_strategy": FailureHandlingStrategy.RETRY,
        "max_retries": 1,
        "retry_delay": 0.5,
    }

    from src.domain.services.workflow_failure_orchestrator import (
        WorkflowFailureOrchestrator,
    )

    orch = WorkflowFailureOrchestrator(
        event_bus=mock_event_bus,
        state_accessor=lambda wf_id: mock_workflow_states.get(wf_id),
        state_mutator=lambda wf_id: mock_workflow_states.setdefault(wf_id, {}),
        workflow_agent_resolver=lambda wf_id: mock_workflow_agents_registry.get(wf_id),
        config=custom_config,
    )

    mock_workflow_agents_registry["workflow_1"].execute_node_with_result = AsyncMock(
        return_value=MagicMock(success=False)
    )

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await orch.handle_node_failure(
            workflow_id="workflow_1",
            node_id="node_b",
            error_code=ErrorCode(retryable=True),
            error_message="Error",
        )

    assert result.retry_count == 1


@pytest.mark.asyncio
async def test_unknown_strategy_returns_failure(orchestrator):
    """测试未知策略返回失败"""
    # 强制设置一个无效策略（绕过枚举）
    orchestrator._node_strategies["node_invalid"] = "unknown_strategy"

    result = await orchestrator.handle_node_failure(
        workflow_id="workflow_1",
        node_id="node_invalid",
        error_code=ErrorCode(retryable=True),
        error_message="Error",
    )

    assert result.success is False
    assert "Unknown strategy" in result.error_message


# =====================================================================
# Test: 补充测试 - 覆盖 Codex 指出的缺口
# =====================================================================


@pytest.mark.asyncio
async def test_retry_handles_execute_exception(
    orchestrator, mock_workflow_agent, mock_event_bus, mock_workflow_states
):
    """测试重试处理执行异常"""
    # Agent 抛出异常
    mock_workflow_agent.execute_node_with_result = AsyncMock(
        side_effect=RuntimeError("Node execution failed")
    )

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await orchestrator.handle_node_failure(
            workflow_id="workflow_1",
            node_id="node_b",
            error_code=ErrorCode(retryable=True),
            error_message="Initial error",
        )

    # 应重试3次后失败
    assert result.success is False
    assert result.retry_count == 3
    assert "Max retries" in result.error_message

    # 应发布失败事件
    mock_event_bus.publish.assert_called_once()
    published_event = mock_event_bus.publish.call_args[0][0]
    assert published_event.success is False


@pytest.mark.asyncio
async def test_skip_creates_state_when_missing(orchestrator, mock_event_bus, mock_workflow_states):
    """测试 SKIP 策略在状态缺失时创建状态"""
    # 移除工作流状态
    mock_workflow_states.pop("workflow_1")

    orchestrator.set_node_strategy("node_b", FailureHandlingStrategy.SKIP)

    result = await orchestrator.handle_node_failure(
        workflow_id="workflow_1",
        node_id="node_b",
        error_code=ErrorCode(retryable=True),
        error_message="Error",
    )

    assert result.success is True
    assert result.skipped is True

    # 确认状态已创建
    assert "workflow_1" in mock_workflow_states
    assert "node_b" in mock_workflow_states["workflow_1"]["skipped_nodes"]


@pytest.mark.asyncio
async def test_abort_creates_state_when_missing(orchestrator, mock_event_bus, mock_workflow_states):
    """测试 ABORT 策略在状态缺失时创建状态"""
    # 移除工作流状态
    mock_workflow_states.pop("workflow_1")

    orchestrator.set_node_strategy("node_b", FailureHandlingStrategy.ABORT)

    result = await orchestrator.handle_node_failure(
        workflow_id="workflow_1",
        node_id="node_b",
        error_code=ErrorCode(retryable=True),
        error_message="Critical error",
    )

    assert result.success is False
    assert result.aborted is True

    # 确认状态已创建并设置为 aborted
    assert "workflow_1" in mock_workflow_states
    assert mock_workflow_states["workflow_1"]["status"] == "aborted"


@pytest.mark.asyncio
async def test_config_string_strategy_normalization(
    mock_event_bus,
    mock_workflow_states,
    mock_workflow_agents_registry,
):
    """测试配置字符串策略值的规范化"""
    from src.domain.services.workflow_failure_orchestrator import (
        FailureHandlingStrategy as FHS,
    )
    from src.domain.services.workflow_failure_orchestrator import (
        WorkflowFailureOrchestrator,
    )

    # 使用字符串策略（如从环境变量读取）
    config = {
        "default_strategy": "skip",  # 字符串而非枚举
        "max_retries": 3,
        "retry_delay": 1.0,
    }

    orch = WorkflowFailureOrchestrator(
        event_bus=mock_event_bus,
        state_accessor=lambda wf_id: mock_workflow_states.get(wf_id),
        state_mutator=lambda wf_id: mock_workflow_states.setdefault(wf_id, {}),
        workflow_agent_resolver=lambda wf_id: mock_workflow_agents_registry.get(wf_id),
        config=config,
    )

    # 确认字符串被规范化为枚举
    assert orch.config["default_strategy"] == FHS.SKIP
    assert orch.config["default_strategy"].value == "skip"

    # 使用默认策略处理节点失败
    result = await orch.handle_node_failure(
        workflow_id="workflow_1",
        node_id="node_x",
        error_code=ErrorCode(retryable=True),
        error_message="Error",
    )

    assert result.success is True
    assert result.skipped is True


@pytest.mark.asyncio
async def test_config_invalid_strategy_fallback_to_retry(
    mock_event_bus,
    mock_workflow_states,
    mock_workflow_agents_registry,
    mock_workflow_agent,
):
    """测试无效策略值回退到 RETRY"""
    from src.domain.services.workflow_failure_orchestrator import (
        WorkflowFailureOrchestrator,
    )

    # 使用无效的策略字符串
    config = {
        "default_strategy": "invalid_strategy",
        "max_retries": 1,
        "retry_delay": 0.1,
    }

    orch = WorkflowFailureOrchestrator(
        event_bus=mock_event_bus,
        state_accessor=lambda wf_id: mock_workflow_states.get(wf_id),
        state_mutator=lambda wf_id: mock_workflow_states.setdefault(wf_id, {}),
        workflow_agent_resolver=lambda wf_id: mock_workflow_agents_registry.get(wf_id),
        config=config,
    )

    # 确认回退到 RETRY
    assert orch.config["default_strategy"] == FailureHandlingStrategy.RETRY

    # 验证执行 RETRY 策略
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.output = {"result": "ok"}
    mock_workflow_agent.execute_node_with_result = AsyncMock(return_value=mock_result)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await orch.handle_node_failure(
            workflow_id="workflow_1",
            node_id="node_b",
            error_code=ErrorCode(retryable=True),
            error_message="Error",
        )

    assert result.success is True
    assert result.retry_count == 1
