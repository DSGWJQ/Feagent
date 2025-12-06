"""资源调度与生命周期管理测试 (TDD - Step 5)

测试内容：
1. RuntimeContext - Agent 运行上下文管理
2. EnhancedResourceScheduler - 增强资源调度器
3. LifecycleAPI - 生命周期 API（spawn/terminate/restart）与 EventBus 集成
4. ExecutionLogger - 执行日志记录

完成标准：
- 单元测试验证调度策略、生命周期状态转换
- 执行日志示例显示资源分配和 agent 状态变化
"""

import asyncio

import pytest

# ==================== 1. Agent 运行上下文测试 ====================


class TestRuntimeContext:
    """Agent 运行上下文测试"""

    def test_create_runtime_context(self):
        """测试：创建运行上下文"""
        from src.domain.services.resource_lifecycle import RuntimeContext

        ctx = RuntimeContext(
            agent_id="agent_001",
            agent_type="conversation",
        )

        assert ctx.agent_id == "agent_001"
        assert ctx.agent_type == "conversation"
        assert ctx.allocated_resources is not None
        assert ctx.metrics is not None
        assert ctx.created_at is not None

    def test_context_with_allocated_resources(self):
        """测试：带资源分配的上下文"""
        from src.domain.services.resource_lifecycle import (
            AllocatedResources,
            RuntimeContext,
        )

        resources = AllocatedResources(
            cpu_cores=2,
            memory_mb=4096,
            gpu_memory_mb=1024,
        )

        ctx = RuntimeContext(
            agent_id="agent_001",
            agent_type="workflow",
            allocated_resources=resources,
        )

        assert ctx.allocated_resources.cpu_cores == 2
        assert ctx.allocated_resources.memory_mb == 4096
        assert ctx.allocated_resources.gpu_memory_mb == 1024

    def test_context_update_metrics(self):
        """测试：更新运行指标"""
        from src.domain.services.resource_lifecycle import RuntimeContext

        ctx = RuntimeContext(agent_id="agent_001", agent_type="conversation")

        ctx.update_metrics(
            cpu_usage=45.5,
            memory_usage=60.0,
            request_count=100,
            error_count=2,
        )

        assert ctx.metrics.cpu_usage == 45.5
        assert ctx.metrics.memory_usage == 60.0
        assert ctx.metrics.request_count == 100
        assert ctx.metrics.error_count == 2

    def test_context_record_activity(self):
        """测试：记录活动"""
        from src.domain.services.resource_lifecycle import RuntimeContext

        ctx = RuntimeContext(agent_id="agent_001", agent_type="conversation")

        ctx.record_activity("处理用户请求")
        ctx.record_activity("调用 LLM")
        ctx.record_activity("生成响应")

        assert len(ctx.activity_log) == 3
        assert ctx.activity_log[0].message == "处理用户请求"
        assert ctx.last_activity_at is not None

    def test_context_uptime(self):
        """测试：计算运行时间"""
        from src.domain.services.resource_lifecycle import RuntimeContext

        ctx = RuntimeContext(agent_id="agent_001", agent_type="conversation")

        # 运行时间应该大于等于 0
        assert ctx.uptime_seconds >= 0


class TestRuntimeContextManager:
    """运行上下文管理器测试"""

    def test_manager_initialization(self):
        """测试：管理器初始化"""
        from src.domain.services.resource_lifecycle import RuntimeContextManager

        manager = RuntimeContextManager()

        assert manager.context_count == 0

    def test_create_context(self):
        """测试：创建上下文"""
        from src.domain.services.resource_lifecycle import RuntimeContextManager

        manager = RuntimeContextManager()

        ctx = manager.create_context(
            agent_id="agent_001",
            agent_type="conversation",
            cpu_cores=2,
            memory_mb=2048,
        )

        assert ctx is not None
        assert manager.context_count == 1
        assert manager.get_context("agent_001") == ctx

    def test_destroy_context(self):
        """测试：销毁上下文"""
        from src.domain.services.resource_lifecycle import RuntimeContextManager

        manager = RuntimeContextManager()
        manager.create_context("agent_001", "conversation")

        result = manager.destroy_context("agent_001")

        assert result is True
        assert manager.context_count == 0
        assert manager.get_context("agent_001") is None

    def test_get_all_contexts(self):
        """测试：获取所有上下文"""
        from src.domain.services.resource_lifecycle import RuntimeContextManager

        manager = RuntimeContextManager()

        manager.create_context("agent_001", "conversation")
        manager.create_context("agent_002", "workflow")
        manager.create_context("agent_003", "coordinator")

        contexts = manager.get_all_contexts()

        assert len(contexts) == 3

    def test_get_contexts_by_type(self):
        """测试：按类型获取上下文"""
        from src.domain.services.resource_lifecycle import RuntimeContextManager

        manager = RuntimeContextManager()

        manager.create_context("conv_001", "conversation")
        manager.create_context("conv_002", "conversation")
        manager.create_context("wf_001", "workflow")

        conversation_ctxs = manager.get_contexts_by_type("conversation")

        assert len(conversation_ctxs) == 2


# ==================== 2. 增强资源调度器测试 ====================


class TestEnhancedResourceScheduler:
    """增强资源调度器测试"""

    def test_scheduler_with_context_manager(self):
        """测试：调度器与上下文管理器集成"""
        from src.domain.services.resource_lifecycle import (
            EnhancedResourceScheduler,
            RuntimeContextManager,
        )

        ctx_manager = RuntimeContextManager()
        scheduler = EnhancedResourceScheduler(context_manager=ctx_manager)

        assert scheduler.context_manager == ctx_manager

    def test_schedule_creates_context(self):
        """测试：调度时创建上下文"""
        from src.domain.services.resource_lifecycle import (
            EnhancedResourceScheduler,
            ScheduleRequest,
        )

        scheduler = EnhancedResourceScheduler()

        req = ScheduleRequest(
            id="agent_001",
            agent_id="agent_001",
            agent_type="conversation",
            priority=5,
            resource_requirement={"cpu_cores": 2, "memory_mb": 2048},
        )

        result = scheduler.schedule(req)

        assert result.scheduled
        assert scheduler.get_context("agent_001") is not None

    def test_complete_destroys_context(self):
        """测试：完成时销毁上下文"""
        from src.domain.services.resource_lifecycle import (
            EnhancedResourceScheduler,
            ScheduleRequest,
        )

        scheduler = EnhancedResourceScheduler()

        req = ScheduleRequest(
            id="agent_001",
            agent_id="agent_001",
            agent_type="conversation",
            priority=5,
        )
        scheduler.schedule(req)

        scheduler.complete("agent_001")

        assert scheduler.get_context("agent_001") is None

    def test_get_resource_allocation_summary(self):
        """测试：获取资源分配摘要"""
        from src.domain.services.resource_lifecycle import (
            EnhancedResourceScheduler,
            ScheduleRequest,
        )

        scheduler = EnhancedResourceScheduler()

        # 调度多个请求
        for i in range(3):
            req = ScheduleRequest(
                id=f"agent_{i:03d}",
                agent_id=f"agent_{i:03d}",
                agent_type="conversation",
                priority=5,
                resource_requirement={"cpu_cores": 2, "memory_mb": 1024},
            )
            scheduler.schedule(req)

        summary = scheduler.get_resource_allocation_summary()

        assert summary["total_allocated_cpu"] == 6
        assert summary["total_allocated_memory"] == 3072
        assert summary["active_agents"] == 3


class TestSchedulingAlgorithms:
    """调度算法测试"""

    def test_weighted_fair_scheduling(self):
        """测试：加权公平调度"""
        from src.domain.services.resource_lifecycle import (
            EnhancedResourceScheduler,
            ScheduleRequest,
            SchedulingAlgorithm,
        )

        scheduler = EnhancedResourceScheduler(algorithm=SchedulingAlgorithm.WEIGHTED_FAIR)

        # 不同权重的请求
        high_weight = ScheduleRequest(
            id="high",
            agent_id="high",
            agent_type="conversation",
            priority=1,
            weight=10,
        )
        low_weight = ScheduleRequest(
            id="low",
            agent_id="low",
            agent_type="conversation",
            priority=1,
            weight=1,
        )

        scheduler.schedule(high_weight)
        scheduler.schedule(low_weight)

        # 高权重应获得更多资源
        high_ctx = scheduler.get_context("high")
        low_ctx = scheduler.get_context("low")

        assert high_ctx.allocated_resources.cpu_cores >= low_ctx.allocated_resources.cpu_cores

    def test_least_loaded_scheduling(self):
        """测试：最小负载调度"""
        from src.domain.services.resource_lifecycle import (
            EnhancedResourceScheduler,
            ScheduleRequest,
            SchedulingAlgorithm,
        )

        scheduler = EnhancedResourceScheduler(algorithm=SchedulingAlgorithm.LEAST_LOADED)

        # 创建几个 agent，模拟不同负载
        for i in range(3):
            req = ScheduleRequest(
                id=f"agent_{i}",
                agent_id=f"agent_{i}",
                agent_type="conversation",
                priority=5,
            )
            scheduler.schedule(req)

        # 更新负载
        scheduler.update_context_metrics("agent_0", cpu_usage=80.0)
        scheduler.update_context_metrics("agent_1", cpu_usage=30.0)
        scheduler.update_context_metrics("agent_2", cpu_usage=50.0)

        # 获取负载最低的 agent
        least_loaded = scheduler.get_least_loaded_agent()

        assert least_loaded == "agent_1"

    def test_round_robin_scheduling(self):
        """测试：轮询调度"""
        from src.domain.services.resource_lifecycle import (
            EnhancedResourceScheduler,
            ScheduleRequest,
            SchedulingAlgorithm,
        )

        scheduler = EnhancedResourceScheduler(algorithm=SchedulingAlgorithm.ROUND_ROBIN)

        # 调度多个请求
        for i in range(5):
            req = ScheduleRequest(
                id=f"agent_{i}",
                agent_id=f"agent_{i}",
                agent_type="conversation",
                priority=5,
            )
            scheduler.schedule(req)

        # 轮询选择
        selections = []
        for _ in range(6):
            selected = scheduler.select_next_agent()
            selections.append(selected)

        # 应该轮询所有 agent
        assert len(set(selections[:5])) == 5


# ==================== 3. 生命周期 API 与 EventBus 集成测试 ====================


class TestLifecycleAPI:
    """生命周期 API 测试"""

    def test_spawn_agent(self):
        """测试：spawn 创建并启动 Agent"""
        from src.domain.services.resource_lifecycle import LifecycleAPI

        api = LifecycleAPI()

        result = api.spawn(
            agent_id="agent_001",
            agent_type="conversation",
            config={"model": "gpt-4"},
            resources={"cpu_cores": 2, "memory_mb": 2048},
        )

        assert result.success
        assert result.agent_id == "agent_001"
        assert result.state == "running"

    def test_terminate_agent(self):
        """测试：terminate 停止并清理 Agent"""
        from src.domain.services.resource_lifecycle import LifecycleAPI

        api = LifecycleAPI()
        api.spawn("agent_001", "conversation", {})

        result = api.terminate("agent_001", reason="用户请求终止")

        assert result.success
        assert result.state == "terminated"
        assert "用户请求终止" in result.reason

    def test_restart_agent(self):
        """测试：restart 重启 Agent"""
        from src.domain.services.resource_lifecycle import LifecycleAPI

        api = LifecycleAPI()
        api.spawn("agent_001", "conversation", {})

        result = api.restart("agent_001", reason="配置更新")

        assert result.success
        assert result.state == "running"
        assert result.restart_count == 1

    def test_spawn_with_resource_validation(self):
        """测试：spawn 时验证资源"""
        from src.domain.services.resource_lifecycle import (
            LifecycleAPI,
            ResourceQuota,
        )

        quota = ResourceQuota(
            cpu_cores=4,
            memory_mb=8192,
            max_concurrent_agents=2,
        )
        api = LifecycleAPI(quota=quota)

        # 第一个和第二个成功
        api.spawn("agent_001", "conversation", {})
        api.spawn("agent_002", "conversation", {})

        # 第三个超出配额
        result = api.spawn("agent_003", "conversation", {})

        assert not result.success
        assert "quota" in result.error.lower() or "limit" in result.error.lower()


class TestLifecycleEventBusIntegration:
    """生命周期 EventBus 集成测试"""

    @pytest.mark.asyncio
    async def test_spawn_publishes_event(self):
        """测试：spawn 发布事件"""
        from src.domain.services.event_bus import EventBus
        from src.domain.services.resource_lifecycle import LifecycleAPI

        event_bus = EventBus()
        api = LifecycleAPI(event_bus=event_bus)

        events_received = []

        async def handler(event):
            events_received.append(event)

        # 订阅生命周期事件
        from src.domain.services.resource_lifecycle import AgentSpawnedEvent

        event_bus.subscribe(AgentSpawnedEvent, handler)

        api.spawn("agent_001", "conversation", {})

        # 等待事件处理
        await asyncio.sleep(0.1)

        assert len(events_received) >= 1
        assert events_received[0].agent_id == "agent_001"

    @pytest.mark.asyncio
    async def test_terminate_publishes_event(self):
        """测试：terminate 发布事件"""
        from src.domain.services.event_bus import EventBus
        from src.domain.services.resource_lifecycle import LifecycleAPI

        event_bus = EventBus()
        api = LifecycleAPI(event_bus=event_bus)

        events_received = []

        async def handler(event):
            events_received.append(event)

        from src.domain.services.resource_lifecycle import AgentTerminatedEvent

        event_bus.subscribe(AgentTerminatedEvent, handler)

        api.spawn("agent_001", "conversation", {})
        api.terminate("agent_001", reason="测试终止")

        await asyncio.sleep(0.1)

        assert len(events_received) >= 1
        assert events_received[0].agent_id == "agent_001"
        assert "测试终止" in events_received[0].reason

    @pytest.mark.asyncio
    async def test_lifecycle_events_chain(self):
        """测试：生命周期事件链"""
        from src.domain.services.event_bus import EventBus
        from src.domain.services.resource_lifecycle import LifecycleAPI

        event_bus = EventBus()
        api = LifecycleAPI(event_bus=event_bus)

        all_events = []

        async def collect_events(event):
            all_events.append(event)

        # 订阅所有生命周期事件
        from src.domain.services.resource_lifecycle import (
            AgentRestartedEvent,
            AgentSpawnedEvent,
            AgentTerminatedEvent,
        )

        event_bus.subscribe(AgentSpawnedEvent, collect_events)
        event_bus.subscribe(AgentTerminatedEvent, collect_events)
        event_bus.subscribe(AgentRestartedEvent, collect_events)

        # 执行生命周期操作
        api.spawn("agent_001", "conversation", {})
        api.restart("agent_001")
        api.terminate("agent_001")

        await asyncio.sleep(0.1)

        # 应该收到 spawn, restart, terminate 事件
        assert len(all_events) >= 3


# ==================== 4. 执行日志测试 ====================


class TestExecutionLogger:
    """执行日志测试"""

    def test_logger_initialization(self):
        """测试：日志记录器初始化"""
        from src.domain.services.resource_lifecycle import ExecutionLogger

        logger = ExecutionLogger()

        assert logger.entry_count == 0

    def test_log_resource_allocation(self):
        """测试：记录资源分配"""
        from src.domain.services.resource_lifecycle import ExecutionLogger

        logger = ExecutionLogger()

        logger.log_resource_allocation(
            agent_id="agent_001",
            cpu_cores=2,
            memory_mb=2048,
            gpu_memory_mb=0,
        )

        assert logger.entry_count == 1
        entries = logger.get_entries(agent_id="agent_001")
        assert len(entries) == 1
        assert entries[0].event_type == "resource_allocation"
        assert entries[0].details["cpu_cores"] == 2

    def test_log_state_change(self):
        """测试：记录状态变化"""
        from src.domain.services.resource_lifecycle import ExecutionLogger

        logger = ExecutionLogger()

        logger.log_state_change(
            agent_id="agent_001",
            previous_state="created",
            new_state="running",
            reason="Agent started",
        )

        entries = logger.get_entries(event_type="state_change")
        assert len(entries) == 1
        assert entries[0].details["previous_state"] == "created"
        assert entries[0].details["new_state"] == "running"

    def test_log_lifecycle_operation(self):
        """测试：记录生命周期操作"""
        from src.domain.services.resource_lifecycle import ExecutionLogger

        logger = ExecutionLogger()

        logger.log_lifecycle_operation(
            agent_id="agent_001",
            operation="spawn",
            success=True,
            duration_ms=150,
        )

        entries = logger.get_entries(event_type="lifecycle_operation")
        assert len(entries) == 1
        assert entries[0].details["operation"] == "spawn"
        assert entries[0].details["success"] is True
        assert entries[0].details["duration_ms"] == 150

    def test_get_execution_timeline(self):
        """测试：获取执行时间线"""
        from src.domain.services.resource_lifecycle import ExecutionLogger

        logger = ExecutionLogger()

        # 模拟完整的生命周期
        logger.log_resource_allocation("agent_001", 2, 2048, 0)
        logger.log_state_change("agent_001", "created", "initializing", "Starting")
        logger.log_state_change("agent_001", "initializing", "running", "Ready")
        logger.log_lifecycle_operation("agent_001", "spawn", True, 200)

        timeline = logger.get_execution_timeline("agent_001")

        assert len(timeline) == 4
        # 时间线应该按时间排序
        for i in range(len(timeline) - 1):
            assert timeline[i].timestamp <= timeline[i + 1].timestamp


class TestExecutionLogFormat:
    """执行日志格式测试"""

    def test_log_entry_to_json(self):
        """测试：日志条目转 JSON"""
        from src.domain.services.resource_lifecycle import ExecutionLogger

        logger = ExecutionLogger()
        logger.log_resource_allocation("agent_001", 2, 2048, 0)

        entries = logger.get_entries()
        json_output = entries[0].to_json()

        assert "timestamp" in json_output
        assert "agent_001" in json_output
        assert "resource_allocation" in json_output

    def test_log_export_to_dict(self):
        """测试：日志导出为字典"""
        from src.domain.services.resource_lifecycle import ExecutionLogger

        logger = ExecutionLogger()
        logger.log_resource_allocation("agent_001", 2, 2048, 0)
        logger.log_state_change("agent_001", "created", "running", "Start")

        export = logger.export_logs()

        assert "entries" in export
        assert len(export["entries"]) == 2
        assert "metadata" in export

    def test_formatted_log_output(self):
        """测试：格式化日志输出"""
        from src.domain.services.resource_lifecycle import ExecutionLogger

        logger = ExecutionLogger()
        logger.log_resource_allocation("agent_001", 2, 2048, 0)
        logger.log_state_change("agent_001", "created", "running", "Started")

        formatted = logger.format_logs(style="readable")

        assert "agent_001" in formatted
        assert "resource_allocation" in formatted or "资源分配" in formatted


# ==================== 5. 集成测试 ====================


class TestResourceLifecycleIntegration:
    """资源调度与生命周期集成测试"""

    def test_full_lifecycle_with_scheduler(self):
        """测试：完整生命周期与调度器集成"""
        from src.domain.services.resource_lifecycle import (
            EnhancedResourceScheduler,
            ExecutionLogger,
            LifecycleAPI,
        )

        scheduler = EnhancedResourceScheduler()
        logger = ExecutionLogger()
        api = LifecycleAPI(scheduler=scheduler, logger=logger)

        # Spawn
        result = api.spawn(
            agent_id="agent_001",
            agent_type="conversation",
            config={"model": "gpt-4"},
            resources={"cpu_cores": 2, "memory_mb": 2048},
        )
        assert result.success

        # 验证上下文创建
        ctx = scheduler.get_context("agent_001")
        assert ctx is not None
        assert ctx.allocated_resources.cpu_cores == 2

        # 验证日志记录
        assert logger.entry_count >= 2  # 至少有资源分配和状态变化

        # Terminate
        api.terminate("agent_001", reason="测试完成")

        # 验证上下文销毁
        assert scheduler.get_context("agent_001") is None

    @pytest.mark.asyncio
    async def test_lifecycle_with_eventbus_and_logging(self):
        """测试：生命周期与 EventBus 和日志集成"""
        from src.domain.services.event_bus import EventBus
        from src.domain.services.resource_lifecycle import (
            ExecutionLogger,
            LifecycleAPI,
        )

        event_bus = EventBus()
        logger = ExecutionLogger()
        api = LifecycleAPI(event_bus=event_bus, logger=logger)

        events = []

        async def collect(event):
            events.append(event)

        from src.domain.services.resource_lifecycle import AgentSpawnedEvent

        event_bus.subscribe(AgentSpawnedEvent, collect)

        # 执行操作
        api.spawn("agent_001", "conversation", {})

        await asyncio.sleep(0.1)

        # 验证事件和日志
        assert len(events) >= 1
        assert logger.entry_count >= 1

    def test_multiple_agents_resource_tracking(self):
        """测试：多 Agent 资源跟踪"""
        from src.domain.services.resource_lifecycle import (
            ExecutionLogger,
            LifecycleAPI,
            ResourceQuota,
        )

        quota = ResourceQuota(
            cpu_cores=8,
            memory_mb=16384,
            max_concurrent_agents=10,
        )
        logger = ExecutionLogger()
        api = LifecycleAPI(quota=quota, logger=logger)

        # Spawn 多个 agent
        for i in range(5):
            api.spawn(
                agent_id=f"agent_{i:03d}",
                agent_type="conversation",
                config={},
                resources={"cpu_cores": 1, "memory_mb": 1024},
            )

        # 获取资源摘要
        summary = api.get_resource_summary()

        assert summary["active_agents"] == 5
        assert summary["total_cpu_allocated"] == 5
        assert summary["total_memory_allocated"] == 5120

        # 终止部分
        api.terminate("agent_000")
        api.terminate("agent_001")

        summary = api.get_resource_summary()
        assert summary["active_agents"] == 3


class TestExecutionLogExamples:
    """执行日志示例测试"""

    def test_resource_allocation_log_example(self):
        """测试：资源分配日志示例"""
        from src.domain.services.resource_lifecycle import (
            ExecutionLogger,
            LifecycleAPI,
        )

        logger = ExecutionLogger()
        api = LifecycleAPI(logger=logger)

        api.spawn(
            agent_id="conversation_agent_001",
            agent_type="conversation",
            config={"model": "gpt-4", "temperature": 0.7},
            resources={"cpu_cores": 2, "memory_mb": 4096, "gpu_memory_mb": 1024},
        )

        # 获取资源分配日志
        entries = logger.get_entries(event_type="resource_allocation")
        assert len(entries) >= 1

        entry = entries[0]
        assert entry.agent_id == "conversation_agent_001"
        assert entry.details["cpu_cores"] == 2
        assert entry.details["memory_mb"] == 4096

    def test_state_change_log_example(self):
        """测试：状态变化日志示例"""
        from src.domain.services.resource_lifecycle import (
            ExecutionLogger,
            LifecycleAPI,
        )

        logger = ExecutionLogger()
        api = LifecycleAPI(logger=logger)

        api.spawn("agent_001", "conversation", {})
        api.terminate("agent_001", reason="任务完成")

        # 获取状态变化日志
        entries = logger.get_entries(event_type="state_change")

        # 应该有多个状态变化：created -> running, running -> terminated
        assert len(entries) >= 2

    def test_complete_execution_log(self):
        """测试：完整执行日志"""
        from src.domain.services.resource_lifecycle import (
            ExecutionLogger,
            LifecycleAPI,
        )

        logger = ExecutionLogger()
        api = LifecycleAPI(logger=logger)

        # 完整生命周期
        api.spawn(
            agent_id="workflow_agent_001",
            agent_type="workflow",
            config={"max_steps": 10},
            resources={"cpu_cores": 4, "memory_mb": 8192},
        )

        api.restart("workflow_agent_001", reason="配置更新")
        api.terminate("workflow_agent_001", reason="工作流完成")

        # 导出日志
        export = logger.export_logs(agent_id="workflow_agent_001")

        assert len(export["entries"]) >= 4  # 分配, spawn状态, restart, terminate

        # 验证日志包含必要信息
        formatted = logger.format_logs(agent_id="workflow_agent_001")
        assert "workflow_agent_001" in formatted
        assert "spawn" in formatted.lower() or "创建" in formatted
