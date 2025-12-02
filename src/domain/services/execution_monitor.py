"""执行监控器 (Execution Monitor) - Phase 7.3

业务定义：
- 维护工作流执行上下文
- 跟踪节点执行状态
- 记录输入输出数据
- 处理执行错误

设计原则：
- 观察者模式：监控器订阅执行事件
- 状态机模式：节点状态转换
- 策略模式：错误处理策略

使用示例：
    monitor = ExecutionMonitor()
    monitor.on_workflow_start("wf_123", ["node_1", "node_2"])
    monitor.on_node_start("wf_123", "node_1", {"input": "data"})
    monitor.on_node_complete("wf_123", "node_1", {"output": "result"})
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.domain.services.event_bus import Event, EventBus

logger = logging.getLogger(__name__)


class ErrorHandlingAction(str, Enum):
    """错误处理动作"""

    RETRY = "retry"  # 重试
    SKIP = "skip"  # 跳过
    FEEDBACK = "feedback"  # 反馈Agent
    ESCALATE = "escalate"  # 升级处理
    ABORT = "abort"  # 终止工作流


@dataclass
class ExecutionMetrics:
    """执行指标

    属性：
    - total_nodes: 总节点数
    - completed_nodes: 完成节点数
    - failed_nodes: 失败节点数
    - total_time_ms: 总执行时间（毫秒）
    - total_tokens: 总token消耗
    - total_cost: 总成本
    """

    total_nodes: int = 0
    completed_nodes: int = 0
    failed_nodes: int = 0
    skipped_nodes: int = 0
    total_time_ms: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0


@dataclass
class ErrorEntry:
    """错误记录

    属性：
    - node_id: 节点ID
    - error_type: 错误类型
    - error_message: 错误消息
    - attempt: 尝试次数
    - action_taken: 采取的处理动作
    - timestamp: 时间戳
    """

    node_id: str
    error_type: str
    error_message: str
    attempt: int
    action_taken: ErrorHandlingAction
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ErrorHandlingPolicy:
    """错误处理策略配置

    属性：
    - max_retries: 最大重试次数
    - retry_delay_seconds: 重试延迟（秒）
    - backoff_factor: 退避因子
    - skippable_node_types: 可跳过的节点类型
    - feedback_after_retries: 重试N次后反馈Agent
    - retryable_errors: 可重试的错误类型
    """

    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    backoff_factor: float = 2.0
    skippable_node_types: list[str] = field(default_factory=list)
    feedback_after_retries: int = 2
    retryable_errors: list[str] = field(
        default_factory=lambda: ["TimeoutError", "ConnectionError", "RateLimitError"]
    )


class ErrorHandler:
    """错误处理器

    职责：
    1. 根据错误类型确定处理动作
    2. 跟踪重试次数
    3. 计算重试延迟
    """

    def __init__(self, policy: ErrorHandlingPolicy | None = None):
        """初始化错误处理器

        参数：
            policy: 错误处理策略
        """
        self.policy = policy or ErrorHandlingPolicy()
        self.retry_counts: dict[str, int] = {}

    def determine_action(
        self,
        node_id: str,
        error: Exception,
        node_type: str | None = None,
    ) -> ErrorHandlingAction:
        """确定错误处理动作

        参数：
            node_id: 节点ID
            error: 异常
            node_type: 节点类型

        返回：
            处理动作
        """
        error_type = type(error).__name__
        current_retries = self.retry_counts.get(node_id, 0)

        # 检查是否是可重试的错误
        is_retryable = error_type in self.policy.retryable_errors

        if is_retryable and current_retries < self.policy.max_retries:
            self.retry_counts[node_id] = current_retries + 1
            return ErrorHandlingAction.RETRY

        # 检查是否达到反馈阈值
        if current_retries >= self.policy.feedback_after_retries:
            return ErrorHandlingAction.FEEDBACK

        # 检查是否是可跳过的节点
        if node_type and node_type in self.policy.skippable_node_types:
            return ErrorHandlingAction.SKIP

        return ErrorHandlingAction.ABORT

    def get_retry_delay(self, node_id: str) -> float:
        """获取重试延迟

        参数：
            node_id: 节点ID

        返回：
            延迟秒数
        """
        retries = self.retry_counts.get(node_id, 0)
        return self.policy.retry_delay_seconds * (self.policy.backoff_factor**retries)

    def reset_retry_count(self, node_id: str) -> None:
        """重置重试计数

        参数：
            node_id: 节点ID
        """
        if node_id in self.retry_counts:
            del self.retry_counts[node_id]


@dataclass
class ExecutionContext:
    """执行上下文

    维护工作流执行的完整状态。

    属性：
    - workflow_id: 工作流ID
    - started_at: 开始时间
    - completed_at: 完成时间
    - status: 执行状态
    - pending_nodes: 待执行节点
    - running_nodes: 执行中节点
    - executed_nodes: 已完成节点
    - failed_nodes: 失败节点
    - skipped_nodes: 跳过节点
    - node_inputs: 节点输入
    - node_outputs: 节点输出
    - error_log: 错误日志
    - metrics: 执行指标
    """

    workflow_id: str
    node_ids: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    status: str = "running"

    # 节点状态
    pending_nodes: list[str] = field(default_factory=list)
    running_nodes: list[str] = field(default_factory=list)
    executed_nodes: list[str] = field(default_factory=list)
    failed_nodes: list[str] = field(default_factory=list)
    skipped_nodes: list[str] = field(default_factory=list)

    # 数据
    node_inputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    node_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)

    # 错误
    error_log: list[ErrorEntry] = field(default_factory=list)

    # 指标
    metrics: ExecutionMetrics = field(default_factory=ExecutionMetrics)

    def __post_init__(self):
        """初始化后处理"""
        if self.node_ids and not self.pending_nodes:
            self.pending_nodes = list(self.node_ids)
            self.metrics.total_nodes = len(self.node_ids)

    def mark_node_running(self, node_id: str, inputs: dict[str, Any]) -> None:
        """标记节点开始运行

        参数：
            node_id: 节点ID
            inputs: 输入数据
        """
        if node_id in self.pending_nodes:
            self.pending_nodes.remove(node_id)

        if node_id not in self.running_nodes:
            self.running_nodes.append(node_id)

        self.node_inputs[node_id] = inputs

    def mark_node_completed(self, node_id: str, outputs: dict[str, Any]) -> None:
        """标记节点完成

        参数：
            node_id: 节点ID
            outputs: 输出数据
        """
        if node_id in self.running_nodes:
            self.running_nodes.remove(node_id)

        if node_id not in self.executed_nodes:
            self.executed_nodes.append(node_id)
            self.metrics.completed_nodes += 1

        self.node_outputs[node_id] = outputs

    def mark_node_failed(
        self,
        node_id: str,
        error_type: str,
        error_message: str,
        action_taken: ErrorHandlingAction,
        attempt: int = 1,
    ) -> None:
        """标记节点失败

        参数：
            node_id: 节点ID
            error_type: 错误类型
            error_message: 错误消息
            action_taken: 采取的动作
            attempt: 尝试次数
        """
        if node_id in self.running_nodes:
            self.running_nodes.remove(node_id)

        # 只有在不重试时才加入失败列表
        if action_taken != ErrorHandlingAction.RETRY:
            if node_id not in self.failed_nodes:
                self.failed_nodes.append(node_id)
                self.metrics.failed_nodes += 1

        # 记录错误
        entry = ErrorEntry(
            node_id=node_id,
            error_type=error_type,
            error_message=error_message,
            attempt=attempt,
            action_taken=action_taken,
        )
        self.error_log.append(entry)

    def mark_node_skipped(self, node_id: str, reason: str = "") -> None:
        """标记节点跳过

        参数：
            node_id: 节点ID
            reason: 跳过原因
        """
        if node_id in self.pending_nodes:
            self.pending_nodes.remove(node_id)

        if node_id in self.running_nodes:
            self.running_nodes.remove(node_id)

        if node_id not in self.skipped_nodes:
            self.skipped_nodes.append(node_id)
            self.metrics.skipped_nodes += 1

    def get_progress(self) -> dict[str, Any]:
        """获取进度信息

        返回：
            进度字典
        """
        total = self.metrics.total_nodes
        completed = self.metrics.completed_nodes
        percentage = (completed / total * 100) if total > 0 else 0.0

        return {
            "total": total,
            "completed": completed,
            "running": len(self.running_nodes),
            "pending": len(self.pending_nodes),
            "failed": self.metrics.failed_nodes,
            "skipped": self.metrics.skipped_nodes,
            "percentage": round(percentage, 1),
        }


# === 事件定义 ===


@dataclass
class WorkflowExecutionStartedEvent(Event):
    """工作流开始执行事件"""

    workflow_id: str = ""
    node_count: int = 0


@dataclass
class WorkflowExecutionCompletedEvent(Event):
    """工作流执行完成事件"""

    workflow_id: str = ""
    status: str = ""
    result: dict[str, Any] | None = None


@dataclass
class NodeExecutionStartedEvent(Event):
    """节点开始执行事件"""

    workflow_id: str = ""
    node_id: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeExecutionCompletedEvent(Event):
    """节点执行完成事件"""

    workflow_id: str = ""
    node_id: str = ""
    outputs: dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeExecutionFailedEvent(Event):
    """节点执行失败事件"""

    workflow_id: str = ""
    node_id: str = ""
    error_type: str = ""
    error_message: str = ""
    action_taken: str = ""


class ExecutionMonitor:
    """执行监控器

    职责：
    1. 创建和维护执行上下文
    2. 跟踪节点执行状态
    3. 处理执行错误
    4. 发布执行事件

    使用示例：
        monitor = ExecutionMonitor()
        monitor.on_workflow_start("wf_123", ["node_1", "node_2"])
        monitor.on_node_start("wf_123", "node_1", {"input": "data"})
    """

    def __init__(
        self,
        error_handler: ErrorHandler | None = None,
        event_bus: EventBus | None = None,
    ):
        """初始化执行监控器

        参数：
            error_handler: 错误处理器
            event_bus: 事件总线
        """
        self.contexts: dict[str, ExecutionContext] = {}
        self.error_handler = error_handler or ErrorHandler()
        self.event_bus = event_bus

    def on_workflow_start(self, workflow_id: str, node_ids: list[str]) -> ExecutionContext:
        """工作流开始

        参数：
            workflow_id: 工作流ID
            node_ids: 节点ID列表

        返回：
            执行上下文
        """
        ctx = ExecutionContext(workflow_id=workflow_id, node_ids=node_ids)
        self.contexts[workflow_id] = ctx
        logger.info(f"工作流开始: {workflow_id}, 节点数: {len(node_ids)}")
        return ctx

    async def on_workflow_start_async(
        self, workflow_id: str, node_ids: list[str]
    ) -> ExecutionContext:
        """异步工作流开始（发布事件）

        参数：
            workflow_id: 工作流ID
            node_ids: 节点ID列表

        返回：
            执行上下文
        """
        ctx = self.on_workflow_start(workflow_id, node_ids)

        if self.event_bus:
            event = WorkflowExecutionStartedEvent(
                source="execution_monitor",
                workflow_id=workflow_id,
                node_count=len(node_ids),
            )
            await self.event_bus.publish(event)

        return ctx

    def on_node_start(self, workflow_id: str, node_id: str, inputs: dict[str, Any]) -> None:
        """节点开始

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            inputs: 输入数据
        """
        ctx = self.contexts.get(workflow_id)
        if ctx:
            ctx.mark_node_running(node_id, inputs)
            logger.debug(f"节点开始: {node_id} (工作流: {workflow_id})")

    async def on_node_start_async(
        self, workflow_id: str, node_id: str, inputs: dict[str, Any]
    ) -> None:
        """异步节点开始（发布事件）"""
        self.on_node_start(workflow_id, node_id, inputs)

        if self.event_bus:
            event = NodeExecutionStartedEvent(
                source="execution_monitor",
                workflow_id=workflow_id,
                node_id=node_id,
                inputs=inputs,
            )
            await self.event_bus.publish(event)

    def on_node_complete(self, workflow_id: str, node_id: str, outputs: dict[str, Any]) -> None:
        """节点完成

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            outputs: 输出数据
        """
        ctx = self.contexts.get(workflow_id)
        if ctx:
            ctx.mark_node_completed(node_id, outputs)
            self.error_handler.reset_retry_count(node_id)
            logger.debug(f"节点完成: {node_id} (工作流: {workflow_id})")

    def on_node_error(
        self,
        workflow_id: str,
        node_id: str,
        error: Exception,
        node_type: str | None = None,
    ) -> ErrorHandlingAction:
        """节点错误

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            error: 异常
            node_type: 节点类型

        返回：
            错误处理动作
        """
        ctx = self.contexts.get(workflow_id)
        if not ctx:
            return ErrorHandlingAction.ABORT

        # 确定处理动作
        action = self.error_handler.determine_action(node_id, error, node_type)

        # 记录错误
        attempt = self.error_handler.retry_counts.get(node_id, 1)
        ctx.mark_node_failed(
            node_id=node_id,
            error_type=type(error).__name__,
            error_message=str(error),
            action_taken=action,
            attempt=attempt,
        )

        logger.warning(f"节点错误: {node_id}, 动作: {action.value}, 错误: {error}")
        return action

    def on_workflow_complete(self, workflow_id: str, status: str = "completed") -> None:
        """工作流完成

        参数：
            workflow_id: 工作流ID
            status: 完成状态
        """
        ctx = self.contexts.get(workflow_id)
        if ctx:
            ctx.completed_at = datetime.now()
            ctx.status = status

            # 计算总执行时间
            if ctx.started_at:
                delta = ctx.completed_at - ctx.started_at
                ctx.metrics.total_time_ms = int(delta.total_seconds() * 1000)

            logger.info(f"工作流完成: {workflow_id}, 状态: {status}")

    def get_context(self, workflow_id: str) -> ExecutionContext | None:
        """获取执行上下文

        参数：
            workflow_id: 工作流ID

        返回：
            执行上下文
        """
        return self.contexts.get(workflow_id)

    def get_all_workflows(self) -> dict[str, dict[str, Any]]:
        """获取所有工作流摘要

        返回：
            工作流摘要字典
        """
        summary = {}
        for wf_id, ctx in self.contexts.items():
            progress = ctx.get_progress()
            summary[wf_id] = {
                "workflow_id": wf_id,
                "status": ctx.status,
                "total_nodes": progress["total"],
                "completed_nodes": progress["completed"],
                "running_nodes": progress["running"],
                "failed_nodes": progress["failed"],
                "percentage": progress["percentage"],
                "started_at": ctx.started_at.isoformat() if ctx.started_at else None,
                "completed_at": ctx.completed_at.isoformat() if ctx.completed_at else None,
            }
        return summary


# 导出
__all__ = [
    "ErrorHandlingAction",
    "ExecutionMetrics",
    "ErrorEntry",
    "ErrorHandlingPolicy",
    "ErrorHandler",
    "ExecutionContext",
    "WorkflowExecutionStartedEvent",
    "WorkflowExecutionCompletedEvent",
    "NodeExecutionStartedEvent",
    "NodeExecutionCompletedEvent",
    "NodeExecutionFailedEvent",
    "ExecutionMonitor",
]
