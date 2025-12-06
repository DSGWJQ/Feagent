"""资源调度与生命周期管理 (Resource & Lifecycle) - Step 5

提供资源调度和 Agent 生命周期的完整实现：

1. RuntimeContext - Agent 运行上下文管理
   - AllocatedResources: 已分配资源
   - RuntimeMetrics: 运行时指标
   - ActivityLog: 活动日志

2. EnhancedResourceScheduler - 增强资源调度器
   - 与上下文管理器集成
   - 多种调度算法支持
   - 资源分配跟踪

3. LifecycleAPI - 生命周期 API
   - spawn/terminate/restart 操作
   - EventBus 集成
   - 执行日志记录

4. ExecutionLogger - 执行日志记录器
   - 资源分配日志
   - 状态变化日志
   - 生命周期操作日志

用法：
    # 创建生命周期 API
    api = LifecycleAPI(event_bus=event_bus, logger=logger)

    # Spawn Agent
    result = api.spawn("agent_001", "conversation", config, resources)

    # Terminate Agent
    api.terminate("agent_001", reason="任务完成")
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.domain.services.event_bus import Event, EventBus
from src.domain.services.management_modules import (
    AgentLifecycleManager,
    ResourceQuota,
    ScheduleResult,
)
from src.domain.services.management_modules import (
    ScheduleRequest as BaseScheduleRequest,
)

# ==================== 1. 运行上下文 ====================


@dataclass
class AllocatedResources:
    """已分配资源

    属性：
        cpu_cores: 分配的 CPU 核心数
        memory_mb: 分配的内存 (MB)
        gpu_memory_mb: 分配的 GPU 内存 (MB)
    """

    cpu_cores: int = 1
    memory_mb: int = 512
    gpu_memory_mb: int = 0


@dataclass
class RuntimeMetrics:
    """运行时指标

    属性：
        cpu_usage: CPU 使用率 (0-100)
        memory_usage: 内存使用率 (0-100)
        request_count: 请求计数
        error_count: 错误计数
        last_updated: 最后更新时间
    """

    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    request_count: int = 0
    error_count: int = 0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class ActivityLogEntry:
    """活动日志条目"""

    timestamp: datetime
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeContext:
    """Agent 运行上下文

    维护单个 Agent 的运行状态、资源分配和活动日志。

    属性：
        agent_id: Agent ID
        agent_type: Agent 类型
        allocated_resources: 已分配资源
        metrics: 运行时指标
        activity_log: 活动日志
        created_at: 创建时间
        last_activity_at: 最后活动时间
    """

    agent_id: str
    agent_type: str
    allocated_resources: AllocatedResources = field(default_factory=AllocatedResources)
    metrics: RuntimeMetrics = field(default_factory=RuntimeMetrics)
    activity_log: list[ActivityLogEntry] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity_at: datetime | None = None
    config: dict[str, Any] = field(default_factory=dict)

    def update_metrics(
        self,
        cpu_usage: float | None = None,
        memory_usage: float | None = None,
        request_count: int | None = None,
        error_count: int | None = None,
    ) -> None:
        """更新运行指标"""
        if cpu_usage is not None:
            self.metrics.cpu_usage = cpu_usage
        if memory_usage is not None:
            self.metrics.memory_usage = memory_usage
        if request_count is not None:
            self.metrics.request_count = request_count
        if error_count is not None:
            self.metrics.error_count = error_count
        self.metrics.last_updated = datetime.now()

    def record_activity(self, message: str, details: dict[str, Any] | None = None) -> None:
        """记录活动"""
        entry = ActivityLogEntry(
            timestamp=datetime.now(),
            message=message,
            details=details or {},
        )
        self.activity_log.append(entry)
        self.last_activity_at = entry.timestamp

    @property
    def uptime_seconds(self) -> float:
        """计算运行时间（秒）"""
        return (datetime.now() - self.created_at).total_seconds()


class RuntimeContextManager:
    """运行上下文管理器

    管理所有 Agent 的运行上下文。
    """

    def __init__(self) -> None:
        self._contexts: dict[str, RuntimeContext] = {}

    @property
    def context_count(self) -> int:
        """上下文数量"""
        return len(self._contexts)

    def create_context(
        self,
        agent_id: str,
        agent_type: str,
        cpu_cores: int = 1,
        memory_mb: int = 512,
        gpu_memory_mb: int = 0,
        config: dict[str, Any] | None = None,
    ) -> RuntimeContext:
        """创建运行上下文"""
        resources = AllocatedResources(
            cpu_cores=cpu_cores,
            memory_mb=memory_mb,
            gpu_memory_mb=gpu_memory_mb,
        )
        ctx = RuntimeContext(
            agent_id=agent_id,
            agent_type=agent_type,
            allocated_resources=resources,
            config=config or {},
        )
        self._contexts[agent_id] = ctx
        return ctx

    def get_context(self, agent_id: str) -> RuntimeContext | None:
        """获取运行上下文"""
        return self._contexts.get(agent_id)

    def destroy_context(self, agent_id: str) -> bool:
        """销毁运行上下文"""
        if agent_id in self._contexts:
            del self._contexts[agent_id]
            return True
        return False

    def get_all_contexts(self) -> list[RuntimeContext]:
        """获取所有上下文"""
        return list(self._contexts.values())

    def get_contexts_by_type(self, agent_type: str) -> list[RuntimeContext]:
        """按类型获取上下文"""
        return [ctx for ctx in self._contexts.values() if ctx.agent_type == agent_type]

    def update_metrics(
        self,
        agent_id: str,
        cpu_usage: float | None = None,
        memory_usage: float | None = None,
        **kwargs: Any,
    ) -> bool:
        """更新指标"""
        ctx = self._contexts.get(agent_id)
        if ctx:
            ctx.update_metrics(cpu_usage=cpu_usage, memory_usage=memory_usage, **kwargs)
            return True
        return False


# ==================== 2. 增强资源调度器 ====================


class SchedulingAlgorithm(str, Enum):
    """调度算法枚举"""

    PRIORITY = "priority"
    FIFO = "fifo"
    WEIGHTED_FAIR = "weighted_fair"
    LEAST_LOADED = "least_loaded"
    ROUND_ROBIN = "round_robin"


@dataclass
class ScheduleRequest(BaseScheduleRequest):
    """扩展的调度请求"""

    agent_id: str = ""  # Agent ID
    weight: int = 1  # 用于加权公平调度


class EnhancedResourceScheduler:
    """增强资源调度器

    集成上下文管理器，支持多种调度算法。
    """

    def __init__(
        self,
        context_manager: RuntimeContextManager | None = None,
        algorithm: SchedulingAlgorithm = SchedulingAlgorithm.PRIORITY,
        quota: ResourceQuota | None = None,
    ) -> None:
        self.context_manager = context_manager or RuntimeContextManager()
        self.algorithm = algorithm
        self.quota = quota or ResourceQuota()

        # 内部状态
        self._running: dict[str, ScheduleRequest] = {}
        self._round_robin_index = 0
        self._total_scheduled = 0
        self._total_completed = 0

    def schedule(self, request: ScheduleRequest) -> ScheduleResult:
        """调度请求并创建上下文"""
        # 检查配额
        if len(self._running) >= self.quota.max_concurrent_agents:
            return ScheduleResult(
                scheduled=False,
                request_id=request.id,
                reason="Quota limit reached",
            )

        # 获取资源需求
        req = request.resource_requirement
        cpu_cores = req.get("cpu_cores", 1)
        memory_mb = req.get("memory_mb", 512)
        gpu_memory_mb = req.get("gpu_memory_mb", 0)

        # 根据算法调整资源分配
        if self.algorithm == SchedulingAlgorithm.WEIGHTED_FAIR:
            # 加权分配
            cpu_cores = max(1, cpu_cores * request.weight // 5)
            memory_mb = max(512, memory_mb * request.weight // 5)

        # 创建上下文
        agent_id = request.agent_id or request.id
        agent_type = request.agent_type

        self.context_manager.create_context(
            agent_id=agent_id,
            agent_type=agent_type,
            cpu_cores=cpu_cores,
            memory_mb=memory_mb,
            gpu_memory_mb=gpu_memory_mb,
        )

        # 记录运行请求
        self._running[agent_id] = request
        self._total_scheduled += 1

        return ScheduleResult(
            scheduled=True,
            request_id=request.id,
            reason="Scheduled successfully",
            decision_basis={
                "algorithm": self.algorithm.value,
                "allocated_cpu": cpu_cores,
                "allocated_memory": memory_mb,
            },
        )

    def complete(self, agent_id: str) -> bool:
        """完成请求并销毁上下文"""
        if agent_id in self._running:
            del self._running[agent_id]
            self.context_manager.destroy_context(agent_id)
            self._total_completed += 1
            return True
        return False

    def get_context(self, agent_id: str) -> RuntimeContext | None:
        """获取上下文"""
        return self.context_manager.get_context(agent_id)

    def update_context_metrics(
        self,
        agent_id: str,
        cpu_usage: float | None = None,
        memory_usage: float | None = None,
    ) -> bool:
        """更新上下文指标"""
        return self.context_manager.update_metrics(
            agent_id, cpu_usage=cpu_usage, memory_usage=memory_usage
        )

    def get_least_loaded_agent(self) -> str | None:
        """获取负载最低的 Agent"""
        contexts = self.context_manager.get_all_contexts()
        if not contexts:
            return None

        min_load = float("inf")
        least_loaded = None

        for ctx in contexts:
            load = ctx.metrics.cpu_usage
            if load < min_load:
                min_load = load
                least_loaded = ctx.agent_id

        return least_loaded

    def select_next_agent(self) -> str | None:
        """选择下一个 Agent（用于轮询调度）"""
        contexts = self.context_manager.get_all_contexts()
        if not contexts:
            return None

        idx = self._round_robin_index % len(contexts)
        self._round_robin_index += 1
        return contexts[idx].agent_id

    def get_resource_allocation_summary(self) -> dict[str, Any]:
        """获取资源分配摘要"""
        contexts = self.context_manager.get_all_contexts()

        total_cpu = sum(ctx.allocated_resources.cpu_cores for ctx in contexts)
        total_memory = sum(ctx.allocated_resources.memory_mb for ctx in contexts)
        total_gpu = sum(ctx.allocated_resources.gpu_memory_mb for ctx in contexts)

        return {
            "active_agents": len(contexts),
            "total_allocated_cpu": total_cpu,
            "total_allocated_memory": total_memory,
            "total_allocated_gpu": total_gpu,
            "total_scheduled": self._total_scheduled,
            "total_completed": self._total_completed,
        }


# ==================== 3. 生命周期事件 ====================


@dataclass
class AgentSpawnedEvent(Event):
    """Agent 创建事件"""

    agent_id: str = ""
    agent_type: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    resources: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentTerminatedEvent(Event):
    """Agent 终止事件"""

    agent_id: str = ""
    reason: str = ""
    final_state: str = ""


@dataclass
class AgentRestartedEvent(Event):
    """Agent 重启事件"""

    agent_id: str = ""
    reason: str = ""
    restart_count: int = 0


# ==================== 4. 执行日志 ====================


@dataclass
class ExecutionLogEntry:
    """执行日志条目"""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(default_factory=datetime.now)
    agent_id: str = ""
    event_type: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """转换为 JSON"""
        return json.dumps(
            {
                "id": self.id,
                "timestamp": self.timestamp.isoformat(),
                "agent_id": self.agent_id,
                "event_type": self.event_type,
                "details": self.details,
            },
            ensure_ascii=False,
            indent=2,
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "event_type": self.event_type,
            "details": self.details,
        }


class ExecutionLogger:
    """执行日志记录器"""

    def __init__(self, max_entries: int = 10000) -> None:
        self._entries: deque[ExecutionLogEntry] = deque(maxlen=max_entries)

    @property
    def entry_count(self) -> int:
        """日志条目数"""
        return len(self._entries)

    def _add_entry(
        self,
        agent_id: str,
        event_type: str,
        details: dict[str, Any],
    ) -> ExecutionLogEntry:
        """添加日志条目"""
        entry = ExecutionLogEntry(
            agent_id=agent_id,
            event_type=event_type,
            details=details,
        )
        self._entries.append(entry)
        return entry

    def log_resource_allocation(
        self,
        agent_id: str,
        cpu_cores: int,
        memory_mb: int,
        gpu_memory_mb: int,
    ) -> None:
        """记录资源分配"""
        self._add_entry(
            agent_id=agent_id,
            event_type="resource_allocation",
            details={
                "cpu_cores": cpu_cores,
                "memory_mb": memory_mb,
                "gpu_memory_mb": gpu_memory_mb,
            },
        )

    def log_state_change(
        self,
        agent_id: str,
        previous_state: str,
        new_state: str,
        reason: str = "",
    ) -> None:
        """记录状态变化"""
        self._add_entry(
            agent_id=agent_id,
            event_type="state_change",
            details={
                "previous_state": previous_state,
                "new_state": new_state,
                "reason": reason,
            },
        )

    def log_lifecycle_operation(
        self,
        agent_id: str,
        operation: str,
        success: bool,
        duration_ms: int = 0,
        error: str = "",
    ) -> None:
        """记录生命周期操作"""
        self._add_entry(
            agent_id=agent_id,
            event_type="lifecycle_operation",
            details={
                "operation": operation,
                "success": success,
                "duration_ms": duration_ms,
                "error": error,
            },
        )

    def get_entries(
        self,
        agent_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[ExecutionLogEntry]:
        """获取日志条目"""
        results: list[ExecutionLogEntry] = []

        for entry in self._entries:
            if agent_id and entry.agent_id != agent_id:
                continue
            if event_type and entry.event_type != event_type:
                continue
            results.append(entry)
            if len(results) >= limit:
                break

        return results

    def get_execution_timeline(self, agent_id: str) -> list[ExecutionLogEntry]:
        """获取执行时间线"""
        entries = [e for e in self._entries if e.agent_id == agent_id]
        return sorted(entries, key=lambda e: e.timestamp)

    def export_logs(
        self,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """导出日志"""
        entries = self.get_entries(agent_id=agent_id, limit=10000)
        return {
            "entries": [e.to_dict() for e in entries],
            "metadata": {
                "exported_at": datetime.now().isoformat(),
                "total_entries": len(entries),
                "agent_id_filter": agent_id,
            },
        }

    def format_logs(
        self,
        agent_id: str | None = None,
        style: str = "readable",
    ) -> str:
        """格式化日志输出"""
        entries = self.get_entries(agent_id=agent_id, limit=1000)

        if style == "readable":
            lines = []
            for entry in entries:
                time_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                lines.append(f"[{time_str}] [{entry.agent_id}] {entry.event_type}")
                for key, value in entry.details.items():
                    lines.append(f"    {key}: {value}")
            return "\n".join(lines)
        else:
            return json.dumps(
                [e.to_dict() for e in entries],
                ensure_ascii=False,
                indent=2,
            )


# ==================== 5. 生命周期 API ====================


@dataclass
class LifecycleResult:
    """生命周期操作结果"""

    success: bool = True
    agent_id: str = ""
    state: str = ""
    error: str = ""
    reason: str = ""
    restart_count: int = 0


class LifecycleAPI:
    """生命周期 API

    提供 spawn/terminate/restart 操作，集成 EventBus 和执行日志。
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        scheduler: EnhancedResourceScheduler | None = None,
        logger: ExecutionLogger | None = None,
        quota: ResourceQuota | None = None,
    ) -> None:
        self.event_bus = event_bus
        self.scheduler = scheduler or EnhancedResourceScheduler(quota=quota)
        self.logger = logger or ExecutionLogger()
        self.quota = quota or ResourceQuota()

        # Agent 状态跟踪
        self._agents: dict[str, dict[str, Any]] = {}
        self._lifecycle_manager = AgentLifecycleManager()

    def _publish_event(self, event: Event) -> None:
        """发布事件"""
        if self.event_bus:
            # 异步发布
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.event_bus.publish(event))
                else:
                    loop.run_until_complete(self.event_bus.publish(event))
            except RuntimeError:
                # 没有运行的事件循环，创建新的
                asyncio.run(self.event_bus.publish(event))

    def spawn(
        self,
        agent_id: str,
        agent_type: str,
        config: dict[str, Any],
        resources: dict[str, Any] | None = None,
    ) -> LifecycleResult:
        """创建并启动 Agent

        参数：
            agent_id: Agent ID
            agent_type: Agent 类型
            config: 配置信息
            resources: 资源需求

        返回：
            LifecycleResult: 操作结果
        """
        start_time = datetime.now()
        resources = resources or {}

        # 检查配额
        if len(self._agents) >= self.quota.max_concurrent_agents:
            return LifecycleResult(
                success=False,
                agent_id=agent_id,
                state="",
                error="Quota limit reached: max concurrent agents exceeded",
            )

        # 调度资源
        req = ScheduleRequest(
            id=agent_id,
            agent_type=agent_type,
            priority=5,
            resource_requirement=resources,
        )
        # 添加 agent_id 属性
        req.agent_id = agent_id

        schedule_result = self.scheduler.schedule(req)
        if not schedule_result.scheduled:
            return LifecycleResult(
                success=False,
                agent_id=agent_id,
                state="",
                error=schedule_result.reason,
            )

        # 记录资源分配日志
        cpu_cores = resources.get("cpu_cores", 1)
        memory_mb = resources.get("memory_mb", 512)
        gpu_memory_mb = resources.get("gpu_memory_mb", 0)

        self.logger.log_resource_allocation(
            agent_id=agent_id,
            cpu_cores=cpu_cores,
            memory_mb=memory_mb,
            gpu_memory_mb=gpu_memory_mb,
        )

        # 创建 Agent 实例
        self._lifecycle_manager.create_agent(agent_id, agent_type, config)
        self._lifecycle_manager.start_agent(agent_id)

        # 记录状态变化
        self.logger.log_state_change(
            agent_id=agent_id,
            previous_state="none",
            new_state="running",
            reason="Agent spawned",
        )

        # 保存状态
        self._agents[agent_id] = {
            "agent_type": agent_type,
            "config": config,
            "resources": resources,
            "state": "running",
            "restart_count": 0,
            "spawned_at": datetime.now(),
        }

        # 记录操作日志
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        self.logger.log_lifecycle_operation(
            agent_id=agent_id,
            operation="spawn",
            success=True,
            duration_ms=duration_ms,
        )

        # 发布事件
        self._publish_event(
            AgentSpawnedEvent(
                agent_id=agent_id,
                agent_type=agent_type,
                config=config,
                resources=resources,
                source="lifecycle_api",
            )
        )

        return LifecycleResult(
            success=True,
            agent_id=agent_id,
            state="running",
        )

    def terminate(
        self,
        agent_id: str,
        reason: str = "",
    ) -> LifecycleResult:
        """终止 Agent

        参数：
            agent_id: Agent ID
            reason: 终止原因

        返回：
            LifecycleResult: 操作结果
        """
        start_time = datetime.now()

        if agent_id not in self._agents:
            return LifecycleResult(
                success=False,
                agent_id=agent_id,
                error="Agent not found",
            )

        # 停止 Agent
        self._lifecycle_manager.stop_agent(agent_id)

        # 记录状态变化
        previous_state = self._agents[agent_id]["state"]
        self.logger.log_state_change(
            agent_id=agent_id,
            previous_state=previous_state,
            new_state="terminated",
            reason=reason,
        )

        # 完成调度（释放资源）
        self.scheduler.complete(agent_id)

        # 记录操作日志
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        self.logger.log_lifecycle_operation(
            agent_id=agent_id,
            operation="terminate",
            success=True,
            duration_ms=duration_ms,
        )

        # 更新状态
        self._agents[agent_id]["state"] = "terminated"

        # 发布事件
        self._publish_event(
            AgentTerminatedEvent(
                agent_id=agent_id,
                reason=reason,
                final_state="terminated",
                source="lifecycle_api",
            )
        )

        # 移除
        del self._agents[agent_id]

        return LifecycleResult(
            success=True,
            agent_id=agent_id,
            state="terminated",
            reason=reason,
        )

    def restart(
        self,
        agent_id: str,
        reason: str = "",
    ) -> LifecycleResult:
        """重启 Agent

        参数：
            agent_id: Agent ID
            reason: 重启原因

        返回：
            LifecycleResult: 操作结果
        """
        start_time = datetime.now()

        if agent_id not in self._agents:
            return LifecycleResult(
                success=False,
                agent_id=agent_id,
                error="Agent not found",
            )

        # 重启
        self._lifecycle_manager.restart_agent(agent_id)

        # 更新重启计数
        self._agents[agent_id]["restart_count"] += 1
        restart_count = self._agents[agent_id]["restart_count"]

        # 记录状态变化
        self.logger.log_state_change(
            agent_id=agent_id,
            previous_state="running",
            new_state="running",
            reason=f"Restarted: {reason}",
        )

        # 记录操作日志
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        self.logger.log_lifecycle_operation(
            agent_id=agent_id,
            operation="restart",
            success=True,
            duration_ms=duration_ms,
        )

        # 发布事件
        self._publish_event(
            AgentRestartedEvent(
                agent_id=agent_id,
                reason=reason,
                restart_count=restart_count,
                source="lifecycle_api",
            )
        )

        return LifecycleResult(
            success=True,
            agent_id=agent_id,
            state="running",
            restart_count=restart_count,
        )

    def get_resource_summary(self) -> dict[str, Any]:
        """获取资源摘要"""
        # 获取调度器分配摘要（用于未来扩展）
        _ = self.scheduler.get_resource_allocation_summary()

        # 计算详细资源使用
        total_cpu = 0
        total_memory = 0

        for agent_info in self._agents.values():
            resources = agent_info.get("resources", {})
            total_cpu += resources.get("cpu_cores", 1)
            total_memory += resources.get("memory_mb", 512)

        return {
            "active_agents": len(self._agents),
            "total_cpu_allocated": total_cpu,
            "total_memory_allocated": total_memory,
            "quota": {
                "max_agents": self.quota.max_concurrent_agents,
                "max_cpu": self.quota.cpu_cores,
                "max_memory": self.quota.memory_mb,
            },
        }

    def get_agent_info(self, agent_id: str) -> dict[str, Any] | None:
        """获取 Agent 信息"""
        return self._agents.get(agent_id)

    def list_agents(self) -> list[str]:
        """列出所有 Agent"""
        return list(self._agents.keys())
