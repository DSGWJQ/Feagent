"""ToolConcurrencyController - 并发控制器 - 阶段 5

业务定义：
- 配置最大并发数，仅统计对话 Agent 工具调用
- 提供排队/抢占策略（FIFO、优先级、拒绝）
- 支持负载均衡（按工具类型分桶）
- 资源管理（记录执行时间、超时取消）
- 监控指标（当前并发、队列长度）

设计原则：
- 线程安全：使用锁保护并发访问
- 高性能：使用异步队列和信号量
- 可观测：完整的监控指标
"""

from __future__ import annotations

import asyncio
import heapq
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# 常量定义
# =============================================================================

VALID_STRATEGIES = {"fifo", "priority", "reject"}
DEFAULT_BUCKET = "__default__"


# =============================================================================
# 配置
# =============================================================================


@dataclass
class ConcurrencyConfig:
    """并发配置

    属性说明：
    - max_concurrent: 最大并发数（仅对话 Agent）
    - queue_size: 队列大小
    - default_timeout: 默认超时时间（秒）
    - strategy: 排队策略（fifo/priority/reject）
    - bucket_limits: 分桶并发限制
    """

    max_concurrent: int = 10
    queue_size: int = 100
    default_timeout: float = 30.0
    strategy: str = "fifo"
    bucket_limits: dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        """验证配置"""
        if self.max_concurrent < 1:
            raise ValueError("max_concurrent must be at least 1")
        if self.queue_size < 0:
            raise ValueError("queue_size must be non-negative")
        if self.strategy not in VALID_STRATEGIES:
            raise ValueError(f"strategy must be one of {VALID_STRATEGIES}, got '{self.strategy}'")


# =============================================================================
# 执行槽位
# =============================================================================


@dataclass
class ExecutionSlot:
    """执行槽位

    代表一个正在执行的工具调用。
    """

    slot_id: str
    tool_name: str
    caller_id: str
    caller_type: str
    bucket: str = DEFAULT_BUCKET
    timeout: float = 30.0
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    _start_time: float = field(default_factory=time.perf_counter)

    def elapsed_time(self) -> float:
        """获取已用时间（秒）"""
        return time.perf_counter() - self._start_time

    def is_timeout(self) -> bool:
        """检查是否超时"""
        return self.elapsed_time() > self.timeout

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "slot_id": self.slot_id,
            "tool_name": self.tool_name,
            "caller_id": self.caller_id,
            "caller_type": self.caller_type,
            "bucket": self.bucket,
            "timeout": self.timeout,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "elapsed_time": self.elapsed_time(),
            "is_timeout": self.is_timeout(),
        }


# =============================================================================
# 排队执行
# =============================================================================


@dataclass(order=False)
class QueuedExecution:
    """排队执行

    代表一个等待执行的工具调用。
    """

    queue_id: str
    tool_name: str
    caller_id: str
    caller_type: str
    params: dict[str, Any]
    bucket: str = DEFAULT_BUCKET
    priority: int = 5  # 默认优先级，数字越小优先级越高
    enqueued_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    _enqueue_time: float = field(default_factory=time.perf_counter)

    def wait_time(self) -> float:
        """获取等待时间（秒）"""
        return time.perf_counter() - self._enqueue_time

    def __lt__(self, other: QueuedExecution) -> bool:
        """比较优先级（用于优先级队列）"""
        if self.priority != other.priority:
            return self.priority < other.priority
        # 相同优先级按入队时间排序
        return self._enqueue_time < other._enqueue_time

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "queue_id": self.queue_id,
            "tool_name": self.tool_name,
            "caller_id": self.caller_id,
            "caller_type": self.caller_type,
            "bucket": self.bucket,
            "priority": self.priority,
            "enqueued_at": self.enqueued_at.isoformat() if self.enqueued_at else None,
            "wait_time": self.wait_time(),
        }


# =============================================================================
# 监控指标
# =============================================================================


@dataclass
class ConcurrencyMetrics:
    """并发控制指标"""

    current_concurrent: int = 0
    queue_length: int = 0
    total_acquired: int = 0
    total_released: int = 0
    total_rejected: int = 0
    total_enqueued: int = 0
    total_dequeued: int = 0
    total_timeout: int = 0
    total_execution_time: float = 0.0
    max_concurrent_observed: int = 0
    max_queue_length_observed: int = 0

    @property
    def avg_execution_time(self) -> float:
        """平均执行时间"""
        if self.total_released == 0:
            return 0.0
        return self.total_execution_time / self.total_released

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "current_concurrent": self.current_concurrent,
            "queue_length": self.queue_length,
            "total_acquired": self.total_acquired,
            "total_released": self.total_released,
            "total_rejected": self.total_rejected,
            "total_enqueued": self.total_enqueued,
            "total_dequeued": self.total_dequeued,
            "total_timeout": self.total_timeout,
            "total_execution_time": self.total_execution_time,
            "avg_execution_time": self.avg_execution_time,
            "max_concurrent_observed": self.max_concurrent_observed,
            "max_queue_length_observed": self.max_queue_length_observed,
        }


# =============================================================================
# 并发控制器
# =============================================================================


class ToolConcurrencyController:
    """工具并发控制器

    核心功能：
    1. 槽位管理（获取/释放）
    2. 排队策略（FIFO/优先级/拒绝）
    3. 负载均衡（按工具类型分桶）
    4. 资源管理（超时检测/取消）
    5. 监控指标
    """

    def __init__(self, config: ConcurrencyConfig | None = None):
        """初始化并发控制器

        参数：
            config: 并发配置
        """
        self._config = config or ConcurrencyConfig()
        self._lock = asyncio.Lock()

        # 槽位管理
        self._active_slots: dict[str, ExecutionSlot] = {}

        # 队列管理
        if self._config.strategy == "priority":
            self._queue: list[QueuedExecution] = []  # heapq
        else:
            self._queue: list[QueuedExecution] = []  # FIFO list

        # 分桶管理
        self._bucket_slots: dict[str, dict[str, ExecutionSlot]] = defaultdict(dict)

        # 监控指标
        self._metrics = ConcurrencyMetrics()

    @property
    def config(self) -> ConcurrencyConfig:
        """获取配置"""
        return self._config

    @property
    def current_concurrent(self) -> int:
        """当前并发数（仅对话 Agent）"""
        return self._metrics.current_concurrent

    @property
    def queue_length(self) -> int:
        """队列长度"""
        return len(self._queue)

    @property
    def metrics(self) -> ConcurrencyMetrics:
        """获取指标"""
        return self._metrics

    # =========================================================================
    # 槽位管理
    # =========================================================================

    async def acquire_slot(
        self,
        tool_name: str,
        caller_id: str,
        caller_type: str,
        bucket: str | None = None,
        timeout: float | None = None,
    ) -> ExecutionSlot | None:
        """获取执行槽位

        参数：
            tool_name: 工具名称
            caller_id: 调用者 ID
            caller_type: 调用者类型
            bucket: 分桶（可选）
            timeout: 超时时间（可选）

        返回：
            ExecutionSlot 或 None（被拒绝时）
        """
        async with self._lock:
            # Workflow 节点不受限制
            if caller_type == "workflow_node":
                return self._create_slot(
                    tool_name=tool_name,
                    caller_id=caller_id,
                    caller_type=caller_type,
                    bucket=bucket,
                    timeout=timeout,
                    count_concurrent=False,
                )

            # 检查是否达到并发限制
            if self._metrics.current_concurrent >= self._config.max_concurrent:
                self._metrics.total_rejected += 1
                logger.debug(
                    f"Slot rejected: concurrent={self._metrics.current_concurrent}, "
                    f"max={self._config.max_concurrent}"
                )
                return None

            # 检查分桶限制
            actual_bucket = bucket or DEFAULT_BUCKET
            if actual_bucket != DEFAULT_BUCKET:
                bucket_limit = self._config.bucket_limits.get(actual_bucket)
                if bucket_limit is not None:
                    current_bucket_count = len(self._bucket_slots.get(actual_bucket, {}))
                    if current_bucket_count >= bucket_limit:
                        self._metrics.total_rejected += 1
                        logger.debug(
                            f"Bucket '{actual_bucket}' limit reached: "
                            f"current={current_bucket_count}, limit={bucket_limit}"
                        )
                        return None

            # 创建槽位
            return self._create_slot(
                tool_name=tool_name,
                caller_id=caller_id,
                caller_type=caller_type,
                bucket=bucket,
                timeout=timeout,
                count_concurrent=True,
            )

    def _create_slot(
        self,
        tool_name: str,
        caller_id: str,
        caller_type: str,
        bucket: str | None,
        timeout: float | None,
        count_concurrent: bool,
    ) -> ExecutionSlot:
        """创建槽位（内部方法）"""
        slot_id = f"slot_{uuid.uuid4().hex[:12]}"
        actual_bucket = bucket or DEFAULT_BUCKET
        actual_timeout = timeout or self._config.default_timeout

        slot = ExecutionSlot(
            slot_id=slot_id,
            tool_name=tool_name,
            caller_id=caller_id,
            caller_type=caller_type,
            bucket=actual_bucket,
            timeout=actual_timeout,
        )

        self._active_slots[slot_id] = slot

        # 更新分桶
        if actual_bucket != DEFAULT_BUCKET:
            self._bucket_slots[actual_bucket][slot_id] = slot

        # 更新指标
        self._metrics.total_acquired += 1
        if count_concurrent:
            self._metrics.current_concurrent += 1
            self._metrics.max_concurrent_observed = max(
                self._metrics.max_concurrent_observed,
                self._metrics.current_concurrent,
            )

        logger.debug(f"Slot acquired: {slot_id} for {tool_name}")
        return slot

    async def release_slot(self, slot_id: str) -> float:
        """释放执行槽位

        参数：
            slot_id: 槽位 ID

        返回：
            执行时间（秒）
        """
        async with self._lock:
            slot = self._active_slots.pop(slot_id, None)
            if slot is None:
                return 0.0

            execution_time = slot.elapsed_time()

            # 更新分桶
            if slot.bucket != DEFAULT_BUCKET:
                self._bucket_slots[slot.bucket].pop(slot_id, None)

            # 更新指标
            self._metrics.total_released += 1
            self._metrics.total_execution_time += execution_time

            # 只有对话 Agent 计入并发数
            if slot.caller_type == "conversation_agent":
                self._metrics.current_concurrent = max(0, self._metrics.current_concurrent - 1)

            logger.debug(f"Slot released: {slot_id}, execution_time={execution_time:.3f}s")
            return execution_time

    # =========================================================================
    # 队列管理
    # =========================================================================

    async def enqueue(
        self,
        tool_name: str,
        caller_id: str,
        caller_type: str,
        params: dict[str, Any],
        bucket: str | None = None,
        priority: int = 5,
    ) -> QueuedExecution | None:
        """入队

        参数：
            tool_name: 工具名称
            caller_id: 调用者 ID
            caller_type: 调用者类型
            params: 调用参数
            bucket: 分桶（可选）
            priority: 优先级（可选）

        返回：
            QueuedExecution 或 None（队列满时）
        """
        async with self._lock:
            # 检查队列是否已满
            if len(self._queue) >= self._config.queue_size:
                self._metrics.total_rejected += 1
                logger.debug(f"Queue full, rejected: queue_size={len(self._queue)}")
                return None

            queue_id = f"queue_{uuid.uuid4().hex[:12]}"
            queued = QueuedExecution(
                queue_id=queue_id,
                tool_name=tool_name,
                caller_id=caller_id,
                caller_type=caller_type,
                params=params,
                bucket=bucket or DEFAULT_BUCKET,
                priority=priority,
            )

            if self._config.strategy == "priority":
                heapq.heappush(self._queue, queued)
            else:
                self._queue.append(queued)

            # 更新指标
            self._metrics.total_enqueued += 1
            self._metrics.queue_length = len(self._queue)
            self._metrics.max_queue_length_observed = max(
                self._metrics.max_queue_length_observed,
                len(self._queue),
            )

            logger.debug(f"Enqueued: {queue_id}, queue_length={len(self._queue)}")
            return queued

    async def dequeue(self) -> QueuedExecution | None:
        """出队

        返回：
            QueuedExecution 或 None（队列为空时）
        """
        async with self._lock:
            if not self._queue:
                return None

            if self._config.strategy == "priority":
                item = heapq.heappop(self._queue)
            else:
                item = self._queue.pop(0)

            # 更新指标
            self._metrics.total_dequeued += 1
            self._metrics.queue_length = len(self._queue)

            logger.debug(f"Dequeued: {item.queue_id}")
            return item

    # =========================================================================
    # 资源管理
    # =========================================================================

    def get_timeout_slots(self) -> list[ExecutionSlot]:
        """获取超时的槽位

        返回：
            超时槽位列表
        """
        return [slot for slot in self._active_slots.values() if slot.is_timeout()]

    async def cancel_timeout_slots(self) -> list[ExecutionSlot]:
        """取消超时槽位

        返回：
            被取消的槽位列表
        """
        async with self._lock:
            timeout_slots = self.get_timeout_slots()
            cancelled = []

            for slot in timeout_slots:
                self._active_slots.pop(slot.slot_id, None)

                # 更新分桶
                if slot.bucket != DEFAULT_BUCKET:
                    self._bucket_slots[slot.bucket].pop(slot.slot_id, None)

                # 更新指标
                if slot.caller_type == "conversation_agent":
                    self._metrics.current_concurrent = max(0, self._metrics.current_concurrent - 1)
                self._metrics.total_timeout += 1

                cancelled.append(slot)
                logger.warning(f"Slot cancelled due to timeout: {slot.slot_id}")

            return cancelled

    # =========================================================================
    # 监控指标
    # =========================================================================

    def get_metrics(self) -> ConcurrencyMetrics:
        """获取监控指标

        返回：
            ConcurrencyMetrics 实例
        """
        # 更新实时指标
        self._metrics.queue_length = len(self._queue)
        return self._metrics

    def get_bucket_metrics(self) -> dict[str, dict[str, Any]]:
        """获取分桶指标

        返回：
            分桶指标字典
        """
        result = {}
        for bucket, limit in self._config.bucket_limits.items():
            current = len(self._bucket_slots.get(bucket, {}))
            result[bucket] = {
                "current": current,
                "limit": limit,
                "utilization": current / limit if limit > 0 else 0.0,
            }
        return result

    def get_active_slots(self) -> list[ExecutionSlot]:
        """获取活跃槽位列表

        返回：
            活跃槽位列表
        """
        return list(self._active_slots.values())

    def get_queue_items(self) -> list[QueuedExecution]:
        """获取队列项列表

        返回：
            队列项列表（按出队顺序）
        """
        if self._config.strategy == "priority":
            # 返回排序后的副本
            return sorted(self._queue)
        return list(self._queue)

    # =========================================================================
    # 控制方法
    # =========================================================================

    async def reset(self) -> None:
        """重置控制器

        清空所有槽位和队列，重置指标。
        """
        async with self._lock:
            self._active_slots.clear()
            self._queue.clear()
            self._bucket_slots.clear()
            self._metrics = ConcurrencyMetrics()
            logger.info("Concurrency controller reset")


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    "ConcurrencyConfig",
    "ExecutionSlot",
    "QueuedExecution",
    "ConcurrencyMetrics",
    "ToolConcurrencyController",
]
