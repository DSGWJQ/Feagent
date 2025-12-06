"""管理模块 (Management Modules) - Step 4

提供三个核心子模块：

1. ResourceScheduler - 资源调度
   - LoadMetrics: 负载度量（CPU/GPU/内存/队列长度）
   - ResourceQuota: 资源配额管理
   - 调度策略：优先级/FIFO/资源感知

2. AgentLifecycleManager - Agent 生命周期管理
   - AgentState: 状态机（create/start/stop/restart/pause/resume）
   - AgentInstance: Agent 实例管理
   - 生命周期事件发布

3. LogAlertHandler - 日志/告警处理
   - LogCollector: 日志采集
   - LogParser: 日志解析
   - AlertHandler: 告警处理

用法：
    # 资源调度
    scheduler = ResourceScheduler(strategy=SchedulingStrategy.PRIORITY)
    result = scheduler.schedule(ScheduleRequest(id="agent_001", priority=5))

    # Agent 生命周期
    lifecycle = AgentLifecycleManager()
    lifecycle.create_agent("agent_001", "conversation", {})
    lifecycle.start_agent("agent_001")

    # 日志告警
    handler = LogAlertHandler()
    handler.add_log_alert_rule("错误告警", LogLevel.ERROR, AlertLevel.WARNING)
    alerts = handler.log_and_check(LogLevel.ERROR, "source", "message")
"""

from __future__ import annotations

import heapq
import re
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.domain.services.event_bus import Event

# ==================== 1. 资源调度器 ====================


@dataclass
class LoadMetrics:
    """负载度量

    属性：
        cpu_percent: CPU 使用率 (0-100)
        memory_percent: 内存使用率 (0-100)
        gpu_percent: GPU 使用率 (0-100)
        queue_length: 等待队列长度
        active_agents: 活跃 Agent 数量
    """

    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    gpu_percent: float = 0.0
    queue_length: int = 0
    active_agents: int = 0

    # 过载阈值
    CPU_OVERLOAD_THRESHOLD: float = 90.0
    MEMORY_OVERLOAD_THRESHOLD: float = 90.0
    GPU_OVERLOAD_THRESHOLD: float = 95.0

    def is_overloaded(self) -> bool:
        """判断是否过载"""
        return (
            self.cpu_percent >= self.CPU_OVERLOAD_THRESHOLD
            or self.memory_percent >= self.MEMORY_OVERLOAD_THRESHOLD
            or self.gpu_percent >= self.GPU_OVERLOAD_THRESHOLD
        )

    def utilization_score(self) -> float:
        """计算综合利用率得分 (0-1)

        加权平均：CPU * 0.4 + Memory * 0.3 + GPU * 0.3
        """
        return (self.cpu_percent * 0.4 + self.memory_percent * 0.3 + self.gpu_percent * 0.3) / 100.0


@dataclass
class ResourceRequest:
    """资源请求"""

    cpu_cores: int = 1
    memory_mb: int = 512
    gpu_memory_mb: int = 0


@dataclass
class ResourceUsage:
    """资源使用情况"""

    cpu_cores: int = 0
    memory_mb: int = 0
    gpu_memory_mb: int = 0


@dataclass
class ResourceQuota:
    """资源配额

    属性：
        cpu_cores: CPU 核心数配额
        memory_mb: 内存配额 (MB)
        gpu_memory_mb: GPU 内存配额 (MB)
        max_concurrent_agents: 最大并发 Agent 数
    """

    cpu_cores: int = 4
    memory_mb: int = 8192
    gpu_memory_mb: int = 0
    max_concurrent_agents: int = 10

    def can_fulfill(self, request: ResourceRequest, used_agents: int = 0) -> bool:
        """检查是否可以满足资源请求"""
        if used_agents >= self.max_concurrent_agents:
            return False
        if request.cpu_cores > self.cpu_cores:
            return False
        if request.memory_mb > self.memory_mb:
            return False
        if request.gpu_memory_mb > self.gpu_memory_mb:
            return False
        return True

    def remaining(self, usage: ResourceUsage) -> ResourceUsage:
        """计算剩余资源"""
        return ResourceUsage(
            cpu_cores=self.cpu_cores - usage.cpu_cores,
            memory_mb=self.memory_mb - usage.memory_mb,
            gpu_memory_mb=self.gpu_memory_mb - usage.gpu_memory_mb,
        )


class SchedulingStrategy(str, Enum):
    """调度策略枚举"""

    PRIORITY = "priority"  # 优先级调度
    FIFO = "fifo"  # 先进先出
    RESOURCE_AWARE = "resource_aware"  # 资源感知调度


@dataclass
class ScheduleRequest:
    """调度请求

    属性：
        id: 请求ID
        priority: 优先级（数字越小优先级越高）
        agent_type: Agent 类型
        resource_requirement: 资源需求
        created_at: 创建时间
    """

    id: str
    priority: int = 5
    agent_type: str = "conversation"
    resource_requirement: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def __lt__(self, other: ScheduleRequest) -> bool:
        """优先级比较（用于堆排序）"""
        return self.priority < other.priority


@dataclass
class ScheduleResult:
    """调度结果

    属性：
        scheduled: 是否已调度
        request_id: 请求ID
        reason: 原因说明
        decision_basis: 决策依据
    """

    scheduled: bool = False
    request_id: str = ""
    reason: str = ""
    decision_basis: dict[str, Any] = field(default_factory=dict)


class PriorityScheduler:
    """优先级调度器"""

    def __init__(self) -> None:
        self._heap: list[ScheduleRequest] = []

    def enqueue(self, request: ScheduleRequest) -> None:
        """入队"""
        heapq.heappush(self._heap, request)

    def dequeue(self) -> ScheduleRequest | None:
        """出队"""
        if self._heap:
            return heapq.heappop(self._heap)
        return None

    def peek(self) -> ScheduleRequest | None:
        """查看队首"""
        if self._heap:
            return self._heap[0]
        return None

    def __len__(self) -> int:
        return len(self._heap)


class QueueScheduler:
    """队列调度器（FIFO）"""

    def __init__(self) -> None:
        self._queue: deque[ScheduleRequest] = deque()

    def enqueue(self, request: ScheduleRequest) -> None:
        """入队"""
        self._queue.append(request)

    def dequeue(self) -> ScheduleRequest | None:
        """出队"""
        if self._queue:
            return self._queue.popleft()
        return None

    def peek(self) -> ScheduleRequest | None:
        """查看队首"""
        if self._queue:
            return self._queue[0]
        return None

    def __len__(self) -> int:
        return len(self._queue)


class ResourceBasedScheduler:
    """资源感知调度器"""

    def __init__(self) -> None:
        self._queue: deque[ScheduleRequest] = deque()
        self._load: LoadMetrics = LoadMetrics()

    def update_load(self, load: LoadMetrics) -> None:
        """更新当前负载"""
        self._load = load

    def can_schedule(self, request: ScheduleRequest) -> bool:
        """判断是否可以调度"""
        # 如果过载，拒绝重资源请求
        if self._load.is_overloaded():
            return False

        req = request.resource_requirement
        cpu_needed = req.get("cpu_cores", 1)
        memory_needed = req.get("memory_mb", 512)

        # 基于当前负载判断
        if self._load.cpu_percent >= 80 and cpu_needed > 2:
            return False
        if self._load.memory_percent >= 80 and memory_needed > 4096:
            return False

        return True

    def enqueue(self, request: ScheduleRequest) -> None:
        """入队"""
        self._queue.append(request)

    def dequeue(self) -> ScheduleRequest | None:
        """出队"""
        if self._queue:
            return self._queue.popleft()
        return None

    def __len__(self) -> int:
        return len(self._queue)


class ResourceScheduler:
    """资源调度器（主调度器）

    整合多种调度策略，管理资源配额和调度决策。

    属性：
        strategy: 调度策略
        quota: 资源配额
    """

    def __init__(
        self,
        strategy: SchedulingStrategy = SchedulingStrategy.PRIORITY,
        quota: ResourceQuota | None = None,
    ) -> None:
        self.strategy = strategy
        self.quota = quota or ResourceQuota()

        # 内部调度器
        self._priority_scheduler = PriorityScheduler()
        self._queue_scheduler = QueueScheduler()
        self._resource_scheduler = ResourceBasedScheduler()

        # 运行中的请求
        self._running: dict[str, ScheduleRequest] = {}
        self._completed: list[str] = []

        # 统计
        self._total_scheduled = 0
        self._total_completed = 0
        self._load = LoadMetrics()

    @property
    def pending_count(self) -> int:
        """等待中的请求数"""
        if self.strategy == SchedulingStrategy.PRIORITY:
            return len(self._priority_scheduler)
        elif self.strategy == SchedulingStrategy.FIFO:
            return len(self._queue_scheduler)
        else:
            return len(self._resource_scheduler)

    @property
    def running_count(self) -> int:
        """运行中的请求数"""
        return len(self._running)

    def update_load(self, load: LoadMetrics) -> None:
        """更新负载指标"""
        self._load = load
        self._resource_scheduler.update_load(load)

    def schedule(self, request: ScheduleRequest) -> ScheduleResult:
        """调度请求

        根据策略和资源配额决定是否调度请求。

        返回：
            ScheduleResult: 包含调度决策和决策依据
        """
        decision_basis = {
            "load_metrics": {
                "cpu_percent": self._load.cpu_percent,
                "memory_percent": self._load.memory_percent,
            },
            "quota_available": self.running_count < self.quota.max_concurrent_agents,
            "priority": request.priority,
        }

        # 检查配额
        if self.running_count >= self.quota.max_concurrent_agents:
            return ScheduleResult(
                scheduled=False,
                request_id=request.id,
                reason="Quota limit reached: max concurrent agents exceeded",
                decision_basis=decision_basis,
            )

        # 资源感知策略额外检查
        if self.strategy == SchedulingStrategy.RESOURCE_AWARE:
            if not self._resource_scheduler.can_schedule(request):
                return ScheduleResult(
                    scheduled=False,
                    request_id=request.id,
                    reason="Resource constraint: system load too high for this request",
                    decision_basis=decision_basis,
                )

        # 调度成功
        self._running[request.id] = request
        self._total_scheduled += 1

        # 加入对应调度器队列（用于优先级排序等）
        if self.strategy == SchedulingStrategy.PRIORITY:
            self._priority_scheduler.enqueue(request)
        elif self.strategy == SchedulingStrategy.FIFO:
            self._queue_scheduler.enqueue(request)
        else:
            self._resource_scheduler.enqueue(request)

        return ScheduleResult(
            scheduled=True,
            request_id=request.id,
            reason="Request scheduled successfully",
            decision_basis=decision_basis,
        )

    def complete(self, request_id: str) -> bool:
        """完成请求"""
        if request_id in self._running:
            del self._running[request_id]
            self._completed.append(request_id)
            self._total_completed += 1
            return True
        return False

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "total_scheduled": self._total_scheduled,
            "total_completed": self._total_completed,
            "running": self.running_count,
            "pending": self.pending_count,
            "strategy": self.strategy.value,
        }


# ==================== 2. Agent 生命周期管理器 ====================


class AgentState(str, Enum):
    """Agent 状态枚举

    状态流转：
    - CREATED -> INITIALIZING -> READY -> RUNNING
    - RUNNING -> PAUSED -> RUNNING
    - RUNNING -> STOPPING -> STOPPED
    - ANY -> FAILED
    - ANY -> RESTARTING -> INITIALIZING -> READY -> RUNNING
    """

    CREATED = "created"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    RESTARTING = "restarting"


# 有效的状态转换
VALID_STATE_TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.CREATED: {AgentState.INITIALIZING, AgentState.FAILED},
    AgentState.INITIALIZING: {AgentState.READY, AgentState.FAILED},
    AgentState.READY: {AgentState.RUNNING, AgentState.FAILED},
    AgentState.RUNNING: {
        AgentState.PAUSED,
        AgentState.STOPPING,
        AgentState.RESTARTING,
        AgentState.FAILED,
    },
    AgentState.PAUSED: {AgentState.RUNNING, AgentState.STOPPING, AgentState.FAILED},
    AgentState.STOPPING: {AgentState.STOPPED, AgentState.FAILED},
    AgentState.STOPPED: {AgentState.INITIALIZING, AgentState.FAILED},
    AgentState.FAILED: {AgentState.RESTARTING},
    AgentState.RESTARTING: {AgentState.INITIALIZING, AgentState.FAILED},
}


@dataclass
class AgentInstance:
    """Agent 实例

    属性：
        agent_id: Agent ID
        agent_type: Agent 类型
        config: 配置信息
        state: 当前状态
        created_at: 创建时间
        started_at: 启动时间
        restart_count: 重启次数
    """

    agent_id: str
    agent_type: str
    config: dict[str, Any]
    state: AgentState = AgentState.CREATED
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    restart_count: int = 0
    failure_reason: str = ""


@dataclass
class LifecycleResult:
    """生命周期操作结果"""

    success: bool = True
    error: str = ""
    previous_state: str = ""
    new_state: str = ""


@dataclass
class AgentLifecycleEvent(Event):
    """Agent 生命周期事件"""

    agent_id: str = ""
    agent_type: str = ""
    event_type: str = ""
    previous_state: str = ""
    new_state: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentHealthStatus:
    """Agent 健康状态"""

    is_healthy: bool = False
    state: str = ""
    uptime_seconds: float = 0.0
    error: str = ""
    last_check: datetime = field(default_factory=datetime.now)


class AgentLifecycleManager:
    """Agent 生命周期管理器

    管理 Agent 的完整生命周期，包括：
    - 创建/启动/停止/重启
    - 暂停/恢复
    - 健康检查
    - 生命周期事件发布
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentInstance] = {}
        self._event_handlers: list[Callable[[AgentLifecycleEvent], None]] = []

    def on_state_change(self, handler: Callable[[AgentLifecycleEvent], None]) -> None:
        """订阅状态变更事件"""
        self._event_handlers.append(handler)

    def _emit_event(
        self,
        agent: AgentInstance,
        event_type: str,
        previous_state: str = "",
    ) -> None:
        """发布事件"""
        event = AgentLifecycleEvent(
            agent_id=agent.agent_id,
            agent_type=agent.agent_type,
            event_type=event_type,
            previous_state=previous_state,
            new_state=agent.state.value,
        )
        for handler in self._event_handlers:
            handler(event)

    def _can_transition(self, current: AgentState, target: AgentState) -> bool:
        """检查状态转换是否有效"""
        valid_targets = VALID_STATE_TRANSITIONS.get(current, set())
        return target in valid_targets

    def create_agent(
        self,
        agent_id: str,
        agent_type: str,
        config: dict[str, Any],
    ) -> AgentInstance:
        """创建 Agent 实例"""
        instance = AgentInstance(
            agent_id=agent_id,
            agent_type=agent_type,
            config=config,
            state=AgentState.CREATED,
        )
        self._agents[agent_id] = instance
        self._emit_event(instance, "agent_created")
        return instance

    def get_agent(self, agent_id: str) -> AgentInstance | None:
        """获取 Agent 实例"""
        return self._agents.get(agent_id)

    def start_agent(self, agent_id: str) -> LifecycleResult:
        """启动 Agent

        状态流转：CREATED/STOPPED -> INITIALIZING -> READY -> RUNNING
        """
        agent = self._agents.get(agent_id)
        if not agent:
            return LifecycleResult(
                success=False,
                error="Agent not found",
            )

        # 检查是否可以启动
        if agent.state not in {AgentState.CREATED, AgentState.STOPPED}:
            return LifecycleResult(
                success=False,
                error=f"Invalid transition: cannot start from {agent.state.value}",
                previous_state=agent.state.value,
            )

        previous_state = agent.state.value

        # 执行状态转换
        agent.state = AgentState.INITIALIZING
        agent.state = AgentState.READY
        agent.state = AgentState.RUNNING
        agent.started_at = datetime.now()

        self._emit_event(agent, "agent_started", previous_state)

        return LifecycleResult(
            success=True,
            previous_state=previous_state,
            new_state=agent.state.value,
        )

    def stop_agent(self, agent_id: str) -> LifecycleResult:
        """停止 Agent

        状态流转：RUNNING/PAUSED -> STOPPING -> STOPPED
        """
        agent = self._agents.get(agent_id)
        if not agent:
            return LifecycleResult(success=False, error="Agent not found")

        # 检查是否可以停止
        if agent.state not in {AgentState.RUNNING, AgentState.PAUSED}:
            return LifecycleResult(
                success=False,
                error=f"Invalid transition: cannot stop from {agent.state.value}",
                previous_state=agent.state.value,
            )

        previous_state = agent.state.value

        agent.state = AgentState.STOPPING
        agent.state = AgentState.STOPPED
        agent.stopped_at = datetime.now()

        self._emit_event(agent, "agent_stopped", previous_state)

        return LifecycleResult(
            success=True,
            previous_state=previous_state,
            new_state=agent.state.value,
        )

    def restart_agent(self, agent_id: str) -> LifecycleResult:
        """重启 Agent

        状态流转：ANY -> RESTARTING -> INITIALIZING -> READY -> RUNNING
        """
        agent = self._agents.get(agent_id)
        if not agent:
            return LifecycleResult(success=False, error="Agent not found")

        previous_state = agent.state.value

        # 允许从任何状态重启（特别是 FAILED）
        agent.state = AgentState.RESTARTING
        agent.state = AgentState.INITIALIZING
        agent.state = AgentState.READY
        agent.state = AgentState.RUNNING
        agent.restart_count += 1
        agent.started_at = datetime.now()
        agent.failure_reason = ""

        self._emit_event(agent, "agent_restarted", previous_state)

        return LifecycleResult(
            success=True,
            previous_state=previous_state,
            new_state=agent.state.value,
        )

    def pause_agent(self, agent_id: str) -> LifecycleResult:
        """暂停 Agent"""
        agent = self._agents.get(agent_id)
        if not agent:
            return LifecycleResult(success=False, error="Agent not found")

        if agent.state != AgentState.RUNNING:
            return LifecycleResult(
                success=False,
                error=f"Invalid transition: cannot pause from {agent.state.value}",
                previous_state=agent.state.value,
            )

        previous_state = agent.state.value
        agent.state = AgentState.PAUSED

        self._emit_event(agent, "agent_paused", previous_state)

        return LifecycleResult(
            success=True,
            previous_state=previous_state,
            new_state=agent.state.value,
        )

    def resume_agent(self, agent_id: str) -> LifecycleResult:
        """恢复 Agent"""
        agent = self._agents.get(agent_id)
        if not agent:
            return LifecycleResult(success=False, error="Agent not found")

        if agent.state != AgentState.PAUSED:
            return LifecycleResult(
                success=False,
                error=f"Invalid transition: cannot resume from {agent.state.value}",
                previous_state=agent.state.value,
            )

        previous_state = agent.state.value
        agent.state = AgentState.RUNNING

        self._emit_event(agent, "agent_resumed", previous_state)

        return LifecycleResult(
            success=True,
            previous_state=previous_state,
            new_state=agent.state.value,
        )

    def mark_failed(self, agent_id: str, reason: str = "") -> LifecycleResult:
        """标记 Agent 为失败状态"""
        agent = self._agents.get(agent_id)
        if not agent:
            return LifecycleResult(success=False, error="Agent not found")

        previous_state = agent.state.value
        agent.state = AgentState.FAILED
        agent.failure_reason = reason

        self._emit_event(agent, "agent_failed", previous_state)

        return LifecycleResult(
            success=True,
            previous_state=previous_state,
            new_state=agent.state.value,
        )

    def health_check(self, agent_id: str) -> AgentHealthStatus:
        """健康检查"""
        agent = self._agents.get(agent_id)
        if not agent:
            return AgentHealthStatus(
                is_healthy=False,
                error="Agent not found",
            )

        is_healthy = agent.state == AgentState.RUNNING
        uptime = 0.0
        if agent.started_at and is_healthy:
            uptime = (datetime.now() - agent.started_at).total_seconds()

        return AgentHealthStatus(
            is_healthy=is_healthy,
            state=agent.state.value,
            uptime_seconds=uptime,
        )


# ==================== 3. 日志/告警处理器 ====================


class LogLevel(str, Enum):
    """日志级别"""

    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"


# 日志级别优先级（用于过滤）
LOG_LEVEL_PRIORITY: dict[LogLevel, int] = {
    LogLevel.DEBUG: 0,
    LogLevel.INFO: 1,
    LogLevel.WARN: 2,
    LogLevel.ERROR: 3,
    LogLevel.CRITICAL: 4,
}


@dataclass
class LogEntry:
    """日志条目

    属性：
        level: 日志级别
        source: 日志来源
        message: 日志消息
        agent_id: 关联的 Agent ID
        timestamp: 时间戳
        metadata: 元数据
    """

    level: LogLevel
    source: str
    message: str
    agent_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "level": self.level.value,
            "source": self.source,
            "message": self.message,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class LogCollector:
    """日志采集器

    收集和查询日志条目。

    属性：
        max_entries: 最大条目数（超出后丢弃旧条目）
    """

    def __init__(self, max_entries: int = 10000) -> None:
        self._entries: deque[LogEntry] = deque(maxlen=max_entries)
        self._max_entries = max_entries

    @property
    def entry_count(self) -> int:
        """日志条目数"""
        return len(self._entries)

    def log(
        self,
        level: LogLevel,
        source: str,
        message: str,
        agent_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> LogEntry:
        """记录日志"""
        entry = LogEntry(
            level=level,
            source=source,
            message=message,
            agent_id=agent_id,
            metadata=metadata or {},
        )
        self._entries.append(entry)
        return entry

    def query(
        self,
        level: LogLevel | None = None,
        source: str | None = None,
        agent_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[LogEntry]:
        """查询日志

        参数：
            level: 按级别过滤
            source: 按来源过滤
            agent_id: 按 Agent ID 过滤
            start_time: 开始时间
            end_time: 结束时间
            limit: 最大返回数量
        """
        results: list[LogEntry] = []

        for entry in self._entries:
            # 级别过滤
            if level is not None and entry.level != level:
                continue

            # 来源过滤
            if source is not None and entry.source != source:
                continue

            # Agent ID 过滤
            if agent_id is not None and entry.agent_id != agent_id:
                continue

            # 时间范围过滤
            if start_time is not None and entry.timestamp < start_time:
                continue
            if end_time is not None and entry.timestamp > end_time:
                continue

            results.append(entry)

            if len(results) >= limit:
                break

        return results

    def clear(self) -> None:
        """清空日志"""
        self._entries.clear()


@dataclass
class ParseResult:
    """解析结果"""

    matched: bool = False
    pattern_name: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class LogPattern:
    """日志模式"""

    name: str
    pattern: str
    extract_fields: list[str]
    field_types: dict[str, type] = field(default_factory=dict)
    _compiled: re.Pattern | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self._compiled = re.compile(self.pattern)


class LogParser:
    """日志解析器

    基于正则表达式模式解析日志。
    """

    def __init__(self) -> None:
        self._patterns: list[LogPattern] = []

    def add_pattern(
        self,
        name: str,
        pattern: str,
        extract_fields: list[str],
        field_types: dict[str, type] | None = None,
    ) -> None:
        """添加解析模式"""
        log_pattern = LogPattern(
            name=name,
            pattern=pattern,
            extract_fields=extract_fields,
            field_types=field_types or {},
        )
        self._patterns.append(log_pattern)

    def parse(self, message: str) -> ParseResult:
        """解析日志消息"""
        for pattern in self._patterns:
            match = pattern._compiled.search(message) if pattern._compiled else None
            if match:
                fields: dict[str, Any] = {}
                for i, field_name in enumerate(pattern.extract_fields):
                    value = match.group(i + 1)
                    # 类型转换
                    if field_name in pattern.field_types:
                        value = pattern.field_types[field_name](value)
                    fields[field_name] = value

                return ParseResult(
                    matched=True,
                    pattern_name=pattern.name,
                    fields=fields,
                )

        return ParseResult(matched=False)


class AlertLevel(str, Enum):
    """告警级别"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AlertRule:
    """告警规则

    属性：
        id: 规则ID
        name: 规则名称
        condition: 条件表达式或函数
        level: 告警级别
        message_template: 消息模板
    """

    id: str
    name: str
    condition: str | Callable[[dict[str, Any]], bool]
    level: AlertLevel
    message_template: str = ""

    def evaluate(self, metrics: dict[str, Any]) -> bool:
        """评估条件"""
        if callable(self.condition):
            return self.condition(metrics)
        # 简单字符串条件暂不支持
        return False


@dataclass
class Alert:
    """告警"""

    id: str
    rule_id: str
    rule_name: str
    level: AlertLevel
    message: str
    triggered_at: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False
    acknowledged_by: str = ""
    acknowledged_at: datetime | None = None


@dataclass
class AcknowledgeResult:
    """确认结果"""

    success: bool = True
    error: str = ""


class AlertHandler:
    """告警处理器

    管理告警规则和告警生成。

    属性：
        suppression_seconds: 告警抑制时间（秒）
    """

    def __init__(self, suppression_seconds: int = 60) -> None:
        self._rules: dict[str, AlertRule] = {}
        self._alerts: dict[str, Alert] = {}
        self._last_triggered: dict[str, datetime] = {}
        self._suppression_seconds = suppression_seconds

    @property
    def rule_count(self) -> int:
        """规则数量"""
        return len(self._rules)

    @property
    def alert_count(self) -> int:
        """告警数量"""
        return len(self._alerts)

    def add_rule(
        self,
        name: str,
        condition: Callable[[dict[str, Any]], bool],
        level: AlertLevel,
        message: str,
    ) -> str:
        """添加告警规则"""
        rule_id = str(uuid.uuid4())[:8]
        rule = AlertRule(
            id=rule_id,
            name=name,
            condition=condition,
            level=level,
            message_template=message,
        )
        self._rules[rule_id] = rule
        return rule_id

    def evaluate(self, metrics: dict[str, Any]) -> list[Alert]:
        """评估所有规则并生成告警"""
        alerts: list[Alert] = []
        now = datetime.now()

        for rule_id, rule in self._rules.items():
            # 检查抑制
            last = self._last_triggered.get(rule_id)
            if last and self._suppression_seconds > 0:
                elapsed = (now - last).total_seconds()
                if elapsed < self._suppression_seconds:
                    continue

            # 评估条件
            if rule.evaluate(metrics):
                alert_id = str(uuid.uuid4())[:8]
                alert = Alert(
                    id=alert_id,
                    rule_id=rule_id,
                    rule_name=rule.name,
                    level=rule.level,
                    message=rule.message_template,
                )
                self._alerts[alert_id] = alert
                self._last_triggered[rule_id] = now
                alerts.append(alert)

        return alerts

    def get_active_alerts(self) -> list[Alert]:
        """获取所有活跃告警"""
        return list(self._alerts.values())

    def get_alert(self, alert_id: str) -> Alert | None:
        """获取告警"""
        return self._alerts.get(alert_id)

    def acknowledge(
        self,
        alert_id: str,
        acknowledged_by: str = "",
    ) -> AcknowledgeResult:
        """确认告警"""
        alert = self._alerts.get(alert_id)
        if not alert:
            return AcknowledgeResult(success=False, error="Alert not found")

        alert.acknowledged = True
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.now()

        return AcknowledgeResult(success=True)


class LogAlertHandler:
    """日志告警处理器

    整合日志采集和告警生成。
    """

    def __init__(self, max_entries: int = 10000) -> None:
        self._collector = LogCollector(max_entries=max_entries)
        self._alert_handler = AlertHandler(suppression_seconds=0)
        self._parser = LogParser()

        # 日志级别告警规则
        self._log_level_rules: dict[str, tuple[LogLevel, AlertLevel, str]] = {}
        # 模式告警规则
        self._pattern_rules: dict[str, tuple[str, AlertLevel, str]] = {}
        # 存储生成的告警
        self._generated_alerts: list[Alert] = []

    def add_log_alert_rule(
        self,
        name: str,
        log_level: LogLevel,
        alert_level: AlertLevel,
        message: str,
    ) -> str:
        """添加基于日志级别的告警规则"""
        rule_id = str(uuid.uuid4())[:8]
        self._log_level_rules[rule_id] = (log_level, alert_level, message)
        return rule_id

    def add_pattern_alert_rule(
        self,
        name: str,
        pattern: str,
        alert_level: AlertLevel,
        message: str,
    ) -> str:
        """添加基于模式的告警规则"""
        rule_id = str(uuid.uuid4())[:8]
        self._pattern_rules[rule_id] = (pattern, alert_level, message)
        self._parser.add_pattern(f"pattern_{rule_id}", pattern, [])
        return rule_id

    def log_and_check(
        self,
        level: LogLevel,
        source: str,
        message: str,
        agent_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> list[Alert]:
        """记录日志并检查告警"""
        # 记录日志
        self._collector.log(level, source, message, agent_id, metadata)

        alerts: list[Alert] = []

        # 检查级别规则
        for rule_id, (log_level, alert_level, alert_msg) in self._log_level_rules.items():
            if level == log_level:
                alert = Alert(
                    id=str(uuid.uuid4())[:8],
                    rule_id=rule_id,
                    rule_name=f"log_level_{log_level.value}",
                    level=alert_level,
                    message=alert_msg,
                )
                alerts.append(alert)

        # 检查模式规则
        for rule_id, (pattern, alert_level, alert_msg) in self._pattern_rules.items():
            if re.search(pattern, message):
                alert = Alert(
                    id=str(uuid.uuid4())[:8],
                    rule_id=rule_id,
                    rule_name=f"pattern_{rule_id}",
                    level=alert_level,
                    message=alert_msg,
                )
                alerts.append(alert)

        # 存储生成的告警
        self._generated_alerts.extend(alerts)

        return alerts

    def get_summary(self) -> dict[str, Any]:
        """获取摘要"""
        logs_by_level: dict[str, int] = {}
        for entry in self._collector._entries:
            level_str = entry.level.value
            logs_by_level[level_str] = logs_by_level.get(level_str, 0) + 1

        return {
            "total_logs": self._collector.entry_count,
            "logs_by_level": logs_by_level,
            "total_alerts": len(self._generated_alerts),
        }
