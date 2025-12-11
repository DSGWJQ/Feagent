"""工作流失败编排器 (WorkflowFailureOrchestrator)

业务定义：
- 从 CoordinatorAgent 提取失败处理逻辑，负责节点失败时的策略执行
- 支持四种策略：RETRY（重试）、SKIP（跳过）、ABORT（终止）、REPLAN（重新规划）
- 与 WorkflowAgent 协同进行重试执行
- 通过 EventBus 发布失败处理事件

设计原则：
- 策略驱动：根据配置的策略执行不同的失败处理路径
- 可配置性：支持节点级别的策略覆盖和默认配置
- 事件发布：通过事件通知其他 Agent 失败处理结果
- 状态管理：更新 workflow_states 以维护执行上下文

实现日期：2025-12-11
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.domain.services.event_bus import Event

logger = logging.getLogger(__name__)


# =============================================================================
# 枚举定义
# =============================================================================


class FailureHandlingStrategy(str, Enum):
    """失败处理策略枚举

    定义节点失败时的处理方式：
    - RETRY: 重试执行
    - SKIP: 跳过节点继续执行
    - ABORT: 终止工作流
    - REPLAN: 请求对话Agent重新规划
    """

    RETRY = "retry"
    SKIP = "skip"
    ABORT = "abort"
    REPLAN = "replan"


# =============================================================================
# 数据结构定义
# =============================================================================


@dataclass
class FailureHandlingResult:
    """失败处理结果（Phase 12）

    属性：
    - success: 处理是否成功（重试成功或跳过）
    - skipped: 是否跳过了节点
    - aborted: 是否终止了工作流
    - retry_count: 实际重试次数
    - output: 成功时的输出
    - error_message: 失败时的错误信息
    """

    success: bool = False
    skipped: bool = False
    aborted: bool = False
    retry_count: int = 0
    output: dict[str, Any] = field(default_factory=dict)
    error_message: str = ""


@dataclass
class WorkflowAdjustmentRequestedEvent(Event):
    """工作流调整请求事件（Phase 12）

    当节点失败需要重新规划时发布此事件，
    对话Agent收到后应重新规划工作流。
    """

    workflow_id: str = ""
    failed_node_id: str = ""
    failure_reason: str = ""
    suggested_action: str = "replan"
    execution_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeFailureHandledEvent(Event):
    """节点失败处理完成事件（Phase 12）

    记录节点失败处理的结果。
    """

    workflow_id: str = ""
    node_id: str = ""
    strategy: str = ""
    success: bool = False
    retry_count: int = 0
    error_message: str = ""


@dataclass
class WorkflowAbortedEvent(Event):
    """工作流终止事件（Phase 12）

    当工作流因严重错误被终止时发布。
    """

    workflow_id: str = ""
    node_id: str = ""
    reason: str = ""


# =============================================================================
# 工作流失败编排器
# =============================================================================


class WorkflowFailureOrchestrator:
    """工作流失败编排器

    职责：
    1. 管理节点失败策略（默认策略 + 节点级覆盖）
    2. 执行失败处理：RETRY / SKIP / ABORT / REPLAN
    3. 维护 WorkflowAgent 注册表以支持重试
    4. 更新工作流状态并发布事件

    使用示例：
        orchestrator = WorkflowFailureOrchestrator(
            event_bus=event_bus,
            state_accessor=lambda wf_id: workflow_states.get(wf_id),
            state_mutator=lambda wf_id: workflow_states.setdefault(wf_id, {}),
            workflow_agent_resolver=lambda wf_id: workflow_agents.get(wf_id),
            config={"default_strategy": FailureHandlingStrategy.RETRY, "max_retries": 3}
        )
        result = await orchestrator.handle_node_failure(
            workflow_id="wf_1",
            node_id="node_b",
            error_code=ErrorCode(...),
            error_message="Failed"
        )
    """

    def __init__(
        self,
        event_bus: Any | None,
        state_accessor: Callable[[str], dict[str, Any] | None],
        state_mutator: Callable[[str], dict[str, Any]],
        workflow_agent_resolver: Callable[[str], Any],
        config: dict[str, Any] | None = None,
        logger_instance: Any | None = None,
    ):
        """初始化工作流失败编排器

        参数：
            event_bus: 事件总线（用于发布失败处理事件）
            state_accessor: 状态访问器（获取 workflow_states）
            state_mutator: 状态修改器（创建/更新 workflow_states）
            workflow_agent_resolver: WorkflowAgent 解析器（根据 workflow_id 获取 agent）
            config: 配置字典（default_strategy, max_retries, retry_delay）
            logger_instance: 日志记录器（可选）
        """
        self.event_bus = event_bus
        self._get_state = state_accessor
        self._mutate_state = state_mutator
        self._resolve_agent = workflow_agent_resolver
        self._logger = logger_instance or logger

        # 配置：合并默认值并规范化策略枚举
        raw_config = config or {}
        default_strategy = raw_config.get("default_strategy", FailureHandlingStrategy.RETRY)

        # 规范化策略配置：如果是字符串则转换为枚举
        if isinstance(default_strategy, str):
            try:
                default_strategy = FailureHandlingStrategy(default_strategy)
            except ValueError:
                self._logger.warning(f"Invalid default_strategy '{default_strategy}', using RETRY")
                default_strategy = FailureHandlingStrategy.RETRY

        self.config = {
            "default_strategy": default_strategy,
            "max_retries": raw_config.get("max_retries", 3),
            "retry_delay": raw_config.get("retry_delay", 1.0),
        }

        # 节点级别的失败策略覆盖
        self._node_strategies: dict[str, FailureHandlingStrategy] = {}

    # =========================================================================
    # 策略管理
    # =========================================================================

    def set_node_strategy(self, node_id: str, strategy: FailureHandlingStrategy) -> None:
        """为特定节点设置失败处理策略

        参数：
            node_id: 节点ID
            strategy: 失败处理策略
        """
        self._node_strategies[node_id] = strategy
        self._logger.info(f"Set failure strategy for node {node_id}: {strategy.value}")

    def get_node_strategy(self, node_id: str) -> FailureHandlingStrategy:
        """获取节点的失败处理策略

        如果节点没有特定策略，返回默认策略。

        参数：
            node_id: 节点ID

        返回：
            失败处理策略
        """
        if node_id in self._node_strategies:
            return self._node_strategies[node_id]
        return self.config["default_strategy"]

    def register_workflow_agent(self, workflow_id: str, agent: Any) -> None:
        """注册 WorkflowAgent 实例

        用于在失败处理时调用重试。
        注意：此方法通过 workflow_agent_resolver 间接实现，
        实际注册由外部管理（如 CoordinatorAgent._workflow_agents）。

        参数：
            workflow_id: 工作流ID
            agent: WorkflowAgent 实例
        """
        self._logger.info(f"WorkflowAgent registered for workflow {workflow_id}")

    # =========================================================================
    # 失败处理主入口
    # =========================================================================

    async def handle_node_failure(
        self,
        workflow_id: str,
        node_id: str,
        error_code: Any,
        error_message: str,
    ) -> FailureHandlingResult:
        """处理节点失败

        根据配置的策略处理节点执行失败：
        - RETRY: 重试执行节点
        - SKIP: 跳过节点继续执行
        - ABORT: 终止工作流
        - REPLAN: 请求重新规划

        参数：
            workflow_id: 工作流ID
            node_id: 失败的节点ID
            error_code: 错误码（ErrorCode 实例或其他）
            error_message: 错误信息

        返回：
            失败处理结果
        """
        strategy = self.get_node_strategy(node_id)

        # 记录日志（安全获取 strategy.value）
        strategy_value = (
            strategy.value if isinstance(strategy, FailureHandlingStrategy) else str(strategy)
        )
        self._logger.info(
            f"Handling node failure: workflow={workflow_id}, node={node_id}, "
            f"strategy={strategy_value}, error={error_message}"
        )

        # SKIP 策略
        if strategy == FailureHandlingStrategy.SKIP:
            return await self._handle_skip(workflow_id, node_id, error_message)

        # ABORT 策略
        if strategy == FailureHandlingStrategy.ABORT:
            return await self._handle_abort(workflow_id, node_id, error_message)

        # REPLAN 策略
        if strategy == FailureHandlingStrategy.REPLAN:
            return await self._handle_replan(workflow_id, node_id, error_message)

        # RETRY 策略（默认）
        if strategy == FailureHandlingStrategy.RETRY:
            # 检查错误是否可重试
            if hasattr(error_code, "is_retryable") and not error_code.is_retryable():
                # 不可重试的错误，发布失败事件并返回
                self._logger.warning(f"Non-retryable error for node {node_id}: {error_message}")

                if self.event_bus:
                    event = NodeFailureHandledEvent(
                        source="workflow_failure_orchestrator",
                        workflow_id=workflow_id,
                        node_id=node_id,
                        strategy="retry",
                        success=False,
                        retry_count=0,
                        error_message=f"Non-retryable error: {error_message}",
                    )
                    await self.event_bus.publish(event)

                return FailureHandlingResult(
                    success=False,
                    error_message=f"Non-retryable error: {error_message}",
                )

            return await self._handle_retry(workflow_id, node_id, error_message)

        # 未知策略，返回失败
        return FailureHandlingResult(
            success=False,
            error_message=f"Unknown strategy: {strategy}",
        )

    # =========================================================================
    # 私有策略处理方法
    # =========================================================================

    async def _handle_retry(
        self, workflow_id: str, node_id: str, error_message: str
    ) -> FailureHandlingResult:
        """处理重试策略

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            error_message: 错误信息

        返回：
            失败处理结果
        """
        max_retries = self.config.get("max_retries", 3)
        retry_delay = self.config.get("retry_delay", 1.0)

        agent = self._resolve_agent(workflow_id)
        if not agent:
            self._logger.error(f"No WorkflowAgent registered for {workflow_id}")
            return FailureHandlingResult(
                success=False,
                error_message=f"No WorkflowAgent registered for {workflow_id}",
            )

        retry_count = 0
        last_error = error_message

        while retry_count < max_retries:
            await asyncio.sleep(retry_delay)
            retry_count += 1

            self._logger.info(
                f"Retry attempt {retry_count}/{max_retries} for node {node_id} "
                f"in workflow {workflow_id}"
            )

            try:
                result = await agent.execute_node_with_result(node_id)

                if result.success:
                    # 更新执行上下文
                    self._update_context_after_success(workflow_id, node_id, result.output)

                    # 发布成功事件
                    if self.event_bus:
                        event = NodeFailureHandledEvent(
                            source="workflow_failure_orchestrator",
                            workflow_id=workflow_id,
                            node_id=node_id,
                            strategy="retry",
                            success=True,
                            retry_count=retry_count,
                        )
                        await self.event_bus.publish(event)

                    self._logger.info(
                        f"Retry successful for node {node_id} after {retry_count} attempts"
                    )

                    return FailureHandlingResult(
                        success=True,
                        retry_count=retry_count,
                        output=result.output,
                    )
                else:
                    # 记录失败原因，继续重试
                    last_error = getattr(result, "error_message", "Unknown error")
                    self._logger.debug(f"Retry {retry_count} failed: {last_error}")

            except Exception as e:
                # 捕获执行异常，记录并继续重试
                last_error = str(e)
                self._logger.warning(
                    f"Retry {retry_count} raised exception: {last_error}", exc_info=True
                )

        # 重试耗尽 - 发布失败事件
        self._logger.warning(
            f"Max retries ({max_retries}) exceeded for node {node_id}: {last_error}"
        )

        if self.event_bus:
            event = NodeFailureHandledEvent(
                source="workflow_failure_orchestrator",
                workflow_id=workflow_id,
                node_id=node_id,
                strategy="retry",
                success=False,
                retry_count=retry_count,
                error_message=f"Max retries ({max_retries}) exceeded",
            )
            await self.event_bus.publish(event)

        return FailureHandlingResult(
            success=False,
            retry_count=retry_count,
            error_message=f"Max retries ({max_retries}) exceeded: {last_error}",
        )

    async def _handle_skip(
        self, workflow_id: str, node_id: str, error_message: str
    ) -> FailureHandlingResult:
        """处理跳过策略

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            error_message: 错误信息

        返回：
            失败处理结果
        """
        # 确保状态存在
        state = self._get_state(workflow_id)
        if not state:
            state = self._mutate_state(workflow_id)

        # 标记节点为已跳过
        if "skipped_nodes" not in state:
            state["skipped_nodes"] = []
        if node_id not in state["skipped_nodes"]:
            state["skipped_nodes"].append(node_id)

        # 从失败节点中移除
        if node_id in state.get("failed_nodes", []):
            state["failed_nodes"].remove(node_id)

        # 发布事件
        if self.event_bus:
            event = NodeFailureHandledEvent(
                source="workflow_failure_orchestrator",
                workflow_id=workflow_id,
                node_id=node_id,
                strategy="skip",
                success=True,
            )
            await self.event_bus.publish(event)

        self._logger.info(f"Node {node_id} skipped in workflow {workflow_id}")

        return FailureHandlingResult(
            success=True,
            skipped=True,
        )

    async def _handle_abort(
        self, workflow_id: str, node_id: str, error_message: str
    ) -> FailureHandlingResult:
        """处理终止策略

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            error_message: 错误信息

        返回：
            失败处理结果
        """
        # 确保状态存在并更新
        state = self._get_state(workflow_id)
        if not state:
            state = self._mutate_state(workflow_id)

        state["status"] = "aborted"

        # 发布终止事件
        if self.event_bus:
            event = WorkflowAbortedEvent(
                source="workflow_failure_orchestrator",
                workflow_id=workflow_id,
                node_id=node_id,
                reason=error_message,
            )
            await self.event_bus.publish(event)

        self._logger.warning(
            f"Workflow {workflow_id} aborted due to node {node_id} failure: {error_message}"
        )

        return FailureHandlingResult(
            success=False,
            aborted=True,
            error_message=error_message,
        )

    async def _handle_replan(
        self, workflow_id: str, node_id: str, error_message: str
    ) -> FailureHandlingResult:
        """处理重新规划策略

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            error_message: 错误信息

        返回：
            失败处理结果
        """
        # 确保状态存在并获取执行上下文
        state = self._get_state(workflow_id)
        if not state:
            state = self._mutate_state(workflow_id)

        execution_context = {
            "executed_nodes": state.get("executed_nodes", []),
            "node_outputs": state.get("node_outputs", {}),
            "failed_nodes": state.get("failed_nodes", []),
        }

        # 发布重新规划事件
        if self.event_bus:
            event = WorkflowAdjustmentRequestedEvent(
                source="workflow_failure_orchestrator",
                workflow_id=workflow_id,
                failed_node_id=node_id,
                failure_reason=error_message,
                suggested_action="replan",
                execution_context=execution_context,
            )
            await self.event_bus.publish(event)

        self._logger.info(
            f"Replan requested for workflow {workflow_id} due to node {node_id} failure"
        )

        return FailureHandlingResult(
            success=False,
            error_message=f"Replan requested: {error_message}",
        )

    def _update_context_after_success(
        self, workflow_id: str, node_id: str, output: dict[str, Any]
    ) -> None:
        """重试成功后更新执行上下文

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            output: 节点输出
        """
        # 确保状态存在
        state = self._get_state(workflow_id)
        if not state:
            state = self._mutate_state(workflow_id)

        # 添加到已执行节点
        if node_id not in state.get("executed_nodes", []):
            if "executed_nodes" not in state:
                state["executed_nodes"] = []
            state["executed_nodes"].append(node_id)

        # 从失败节点中移除
        if node_id in state.get("failed_nodes", []):
            state["failed_nodes"].remove(node_id)

        # 保存输出
        if "node_outputs" not in state:
            state["node_outputs"] = {}
        state["node_outputs"][node_id] = output

        self._logger.debug(
            f"Context updated after successful retry: workflow={workflow_id}, node={node_id}"
        )


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    "FailureHandlingStrategy",
    "FailureHandlingResult",
    "WorkflowAdjustmentRequestedEvent",
    "NodeFailureHandledEvent",
    "WorkflowAbortedEvent",
    "WorkflowFailureOrchestrator",
]
