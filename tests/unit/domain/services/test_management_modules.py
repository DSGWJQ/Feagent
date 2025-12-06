"""管理模块测试 (TDD - Step 4)

测试三个子模块：
1. ResourceScheduler - 资源调度
2. AgentLifecycleManager - Agent 生命周期管理
3. LogAlertHandler - 日志/告警处理

测试覆盖：
- 资源度量（负载、GPU/CPU 配额）
- Agent 状态机（create/start/stop/restart）
- 日志采集与解析接口
- 调度策略（队列/优先级）
"""

import time
from datetime import datetime

# ==================== 1. 资源调度器测试 ====================


class TestLoadMetrics:
    """负载度量测试"""

    def test_create_load_metrics_with_defaults(self):
        """测试：创建默认负载度量"""
        from src.domain.services.management_modules import LoadMetrics

        metrics = LoadMetrics()
        assert metrics.cpu_percent == 0.0
        assert metrics.memory_percent == 0.0
        assert metrics.gpu_percent == 0.0
        assert metrics.queue_length == 0
        assert metrics.active_agents == 0

    def test_load_metrics_with_values(self):
        """测试：创建带值的负载度量"""
        from src.domain.services.management_modules import LoadMetrics

        metrics = LoadMetrics(
            cpu_percent=75.5,
            memory_percent=60.0,
            gpu_percent=80.0,
            queue_length=10,
            active_agents=5,
        )
        assert metrics.cpu_percent == 75.5
        assert metrics.memory_percent == 60.0
        assert metrics.gpu_percent == 80.0
        assert metrics.queue_length == 10
        assert metrics.active_agents == 5

    def test_load_metrics_is_overloaded(self):
        """测试：判断是否过载"""
        from src.domain.services.management_modules import LoadMetrics

        normal = LoadMetrics(cpu_percent=50.0, memory_percent=50.0)
        assert not normal.is_overloaded()

        overloaded = LoadMetrics(cpu_percent=95.0, memory_percent=50.0)
        assert overloaded.is_overloaded()

        memory_overloaded = LoadMetrics(cpu_percent=50.0, memory_percent=92.0)
        assert memory_overloaded.is_overloaded()

    def test_load_metrics_utilization_score(self):
        """测试：计算综合利用率得分"""
        from src.domain.services.management_modules import LoadMetrics

        metrics = LoadMetrics(
            cpu_percent=50.0,
            memory_percent=40.0,
            gpu_percent=60.0,
        )
        score = metrics.utilization_score()
        assert 0.0 <= score <= 1.0
        # 加权平均：CPU * 0.4 + Memory * 0.3 + GPU * 0.3
        expected = (50.0 * 0.4 + 40.0 * 0.3 + 60.0 * 0.3) / 100
        assert abs(score - expected) < 0.01


class TestResourceQuota:
    """资源配额测试"""

    def test_create_resource_quota(self):
        """测试：创建资源配额"""
        from src.domain.services.management_modules import ResourceQuota

        quota = ResourceQuota(
            cpu_cores=4,
            memory_mb=8192,
            gpu_memory_mb=4096,
            max_concurrent_agents=10,
        )
        assert quota.cpu_cores == 4
        assert quota.memory_mb == 8192
        assert quota.gpu_memory_mb == 4096
        assert quota.max_concurrent_agents == 10

    def test_quota_check_available(self):
        """测试：检查资源是否可用"""
        from src.domain.services.management_modules import (
            ResourceQuota,
            ResourceRequest,
        )

        quota = ResourceQuota(
            cpu_cores=4,
            memory_mb=8192,
            gpu_memory_mb=4096,
            max_concurrent_agents=10,
        )

        # 请求可满足
        request = ResourceRequest(cpu_cores=2, memory_mb=4096, gpu_memory_mb=2048)
        assert quota.can_fulfill(request, used_agents=5)

        # 请求超出
        big_request = ResourceRequest(cpu_cores=8, memory_mb=4096, gpu_memory_mb=2048)
        assert not quota.can_fulfill(big_request, used_agents=5)

        # Agent 数量超限
        assert not quota.can_fulfill(request, used_agents=10)

    def test_quota_remaining_capacity(self):
        """测试：计算剩余容量"""
        from src.domain.services.management_modules import (
            ResourceQuota,
            ResourceUsage,
        )

        quota = ResourceQuota(
            cpu_cores=4,
            memory_mb=8192,
            gpu_memory_mb=4096,
            max_concurrent_agents=10,
        )

        usage = ResourceUsage(cpu_cores=1, memory_mb=2048, gpu_memory_mb=1024)
        remaining = quota.remaining(usage)

        assert remaining.cpu_cores == 3
        assert remaining.memory_mb == 6144
        assert remaining.gpu_memory_mb == 3072


class TestSchedulingStrategy:
    """调度策略测试"""

    def test_priority_scheduler_basic(self):
        """测试：优先级调度器基础功能"""
        from src.domain.services.management_modules import (
            PriorityScheduler,
            ScheduleRequest,
        )

        scheduler = PriorityScheduler()

        # 添加不同优先级的请求
        req1 = ScheduleRequest(id="req1", priority=5, agent_type="conversation")
        req2 = ScheduleRequest(id="req2", priority=1, agent_type="workflow")
        req3 = ScheduleRequest(id="req3", priority=10, agent_type="conversation")

        scheduler.enqueue(req1)
        scheduler.enqueue(req2)
        scheduler.enqueue(req3)

        # 按优先级顺序出队（数字越小优先级越高）
        assert scheduler.dequeue().id == "req2"
        assert scheduler.dequeue().id == "req1"
        assert scheduler.dequeue().id == "req3"

    def test_queue_scheduler_fifo(self):
        """测试：队列调度器 FIFO"""
        from src.domain.services.management_modules import (
            QueueScheduler,
            ScheduleRequest,
        )

        scheduler = QueueScheduler()

        req1 = ScheduleRequest(id="req1", priority=5, agent_type="conversation")
        req2 = ScheduleRequest(id="req2", priority=1, agent_type="workflow")
        req3 = ScheduleRequest(id="req3", priority=10, agent_type="conversation")

        scheduler.enqueue(req1)
        scheduler.enqueue(req2)
        scheduler.enqueue(req3)

        # FIFO 顺序
        assert scheduler.dequeue().id == "req1"
        assert scheduler.dequeue().id == "req2"
        assert scheduler.dequeue().id == "req3"

    def test_resource_based_scheduler(self):
        """测试：基于资源的调度器"""
        from src.domain.services.management_modules import (
            LoadMetrics,
            ResourceBasedScheduler,
            ScheduleRequest,
        )

        scheduler = ResourceBasedScheduler()

        # 设置当前负载
        scheduler.update_load(LoadMetrics(cpu_percent=80.0, memory_percent=70.0))

        # 低资源需求请求可以通过
        light_req = ScheduleRequest(
            id="light",
            priority=5,
            agent_type="conversation",
            resource_requirement={"cpu_cores": 1, "memory_mb": 512},
        )
        assert scheduler.can_schedule(light_req)

        # 高资源需求请求被阻止
        heavy_req = ScheduleRequest(
            id="heavy",
            priority=1,
            agent_type="workflow",
            resource_requirement={"cpu_cores": 8, "memory_mb": 16384},
        )
        assert not scheduler.can_schedule(heavy_req)

    def test_scheduler_with_quota_enforcement(self):
        """测试：调度器配额强制执行"""
        from src.domain.services.management_modules import (
            ResourceQuota,
            ResourceScheduler,
            ScheduleRequest,
        )

        quota = ResourceQuota(
            cpu_cores=4,
            memory_mb=8192,
            gpu_memory_mb=4096,
            max_concurrent_agents=3,
        )

        scheduler = ResourceScheduler(quota=quota)

        # 添加3个请求
        for i in range(3):
            req = ScheduleRequest(
                id=f"req{i}",
                priority=5,
                agent_type="conversation",
                resource_requirement={"cpu_cores": 1, "memory_mb": 1024},
            )
            result = scheduler.schedule(req)
            assert result.scheduled

        # 第4个请求超出配额
        req4 = ScheduleRequest(
            id="req4",
            priority=1,
            agent_type="workflow",
            resource_requirement={"cpu_cores": 1, "memory_mb": 1024},
        )
        result = scheduler.schedule(req4)
        assert not result.scheduled
        assert "quota" in result.reason.lower() or "limit" in result.reason.lower()


class TestResourceScheduler:
    """资源调度器综合测试"""

    def test_scheduler_initialization(self):
        """测试：调度器初始化"""
        from src.domain.services.management_modules import ResourceScheduler

        scheduler = ResourceScheduler()
        assert scheduler.pending_count == 0
        assert scheduler.running_count == 0

    def test_scheduler_strategy_selection(self):
        """测试：调度策略选择"""
        from src.domain.services.management_modules import (
            ResourceScheduler,
            SchedulingStrategy,
        )

        # 默认优先级策略
        scheduler1 = ResourceScheduler(strategy=SchedulingStrategy.PRIORITY)
        assert scheduler1.strategy == SchedulingStrategy.PRIORITY

        # 队列策略
        scheduler2 = ResourceScheduler(strategy=SchedulingStrategy.FIFO)
        assert scheduler2.strategy == SchedulingStrategy.FIFO

        # 资源感知策略
        scheduler3 = ResourceScheduler(strategy=SchedulingStrategy.RESOURCE_AWARE)
        assert scheduler3.strategy == SchedulingStrategy.RESOURCE_AWARE

    def test_scheduler_complete_lifecycle(self):
        """测试：调度器完整生命周期"""
        from src.domain.services.management_modules import (
            ResourceScheduler,
            ScheduleRequest,
        )

        scheduler = ResourceScheduler()

        # 提交请求
        req = ScheduleRequest(id="req1", priority=5, agent_type="conversation")
        result = scheduler.schedule(req)
        assert result.scheduled
        assert scheduler.running_count == 1

        # 完成请求
        scheduler.complete("req1")
        assert scheduler.running_count == 0

    def test_scheduler_get_statistics(self):
        """测试：获取调度器统计信息"""
        from src.domain.services.management_modules import (
            ResourceScheduler,
            ScheduleRequest,
        )

        scheduler = ResourceScheduler()

        # 提交几个请求
        for i in range(5):
            req = ScheduleRequest(id=f"req{i}", priority=i, agent_type="conversation")
            scheduler.schedule(req)

        # 完成部分
        scheduler.complete("req0")
        scheduler.complete("req1")

        stats = scheduler.get_statistics()
        assert stats["total_scheduled"] == 5
        assert stats["total_completed"] == 2
        assert stats["running"] == 3


# ==================== 2. Agent 生命周期管理器测试 ====================


class TestAgentState:
    """Agent 状态测试"""

    def test_agent_states_exist(self):
        """测试：Agent 状态枚举存在"""
        from src.domain.services.management_modules import AgentState

        assert AgentState.CREATED is not None
        assert AgentState.INITIALIZING is not None
        assert AgentState.READY is not None
        assert AgentState.RUNNING is not None
        assert AgentState.PAUSED is not None
        assert AgentState.STOPPING is not None
        assert AgentState.STOPPED is not None
        assert AgentState.FAILED is not None
        assert AgentState.RESTARTING is not None

    def test_agent_state_values(self):
        """测试：Agent 状态值"""
        from src.domain.services.management_modules import AgentState

        assert AgentState.CREATED.value == "created"
        assert AgentState.RUNNING.value == "running"
        assert AgentState.STOPPED.value == "stopped"


class TestAgentLifecycle:
    """Agent 生命周期测试"""

    def test_create_agent_instance(self):
        """测试：创建 Agent 实例"""
        from src.domain.services.management_modules import (
            AgentLifecycleManager,
        )

        manager = AgentLifecycleManager()

        instance = manager.create_agent(
            agent_id="agent_001",
            agent_type="conversation",
            config={"model": "gpt-4"},
        )

        assert instance.agent_id == "agent_001"
        assert instance.agent_type == "conversation"
        assert instance.state.value == "created"

    def test_start_agent(self):
        """测试：启动 Agent"""
        from src.domain.services.management_modules import (
            AgentLifecycleManager,
            AgentState,
        )

        manager = AgentLifecycleManager()
        manager.create_agent("agent_001", "conversation", {})

        result = manager.start_agent("agent_001")

        assert result.success
        instance = manager.get_agent("agent_001")
        assert instance.state == AgentState.RUNNING

    def test_stop_agent(self):
        """测试：停止 Agent"""
        from src.domain.services.management_modules import (
            AgentLifecycleManager,
            AgentState,
        )

        manager = AgentLifecycleManager()
        manager.create_agent("agent_001", "conversation", {})
        manager.start_agent("agent_001")

        result = manager.stop_agent("agent_001")

        assert result.success
        instance = manager.get_agent("agent_001")
        assert instance.state == AgentState.STOPPED

    def test_restart_agent(self):
        """测试：重启 Agent"""
        from src.domain.services.management_modules import (
            AgentLifecycleManager,
            AgentState,
        )

        manager = AgentLifecycleManager()
        manager.create_agent("agent_001", "conversation", {})
        manager.start_agent("agent_001")

        result = manager.restart_agent("agent_001")

        assert result.success
        instance = manager.get_agent("agent_001")
        assert instance.state == AgentState.RUNNING
        assert instance.restart_count == 1

    def test_pause_and_resume_agent(self):
        """测试：暂停和恢复 Agent"""
        from src.domain.services.management_modules import (
            AgentLifecycleManager,
            AgentState,
        )

        manager = AgentLifecycleManager()
        manager.create_agent("agent_001", "conversation", {})
        manager.start_agent("agent_001")

        # 暂停
        result = manager.pause_agent("agent_001")
        assert result.success
        assert manager.get_agent("agent_001").state == AgentState.PAUSED

        # 恢复
        result = manager.resume_agent("agent_001")
        assert result.success
        assert manager.get_agent("agent_001").state == AgentState.RUNNING


class TestAgentStateTransitions:
    """Agent 状态转换测试"""

    def test_valid_transitions(self):
        """测试：有效状态转换"""
        from src.domain.services.management_modules import (
            AgentLifecycleManager,
        )

        manager = AgentLifecycleManager()

        # CREATED -> RUNNING (通过 start)
        manager.create_agent("a1", "conversation", {})
        assert manager.start_agent("a1").success

        # RUNNING -> PAUSED
        assert manager.pause_agent("a1").success

        # PAUSED -> RUNNING
        assert manager.resume_agent("a1").success

        # RUNNING -> STOPPED
        assert manager.stop_agent("a1").success

        # STOPPED -> RUNNING (通过 start)
        assert manager.start_agent("a1").success

    def test_invalid_transitions(self):
        """测试：无效状态转换"""
        from src.domain.services.management_modules import AgentLifecycleManager

        manager = AgentLifecycleManager()
        manager.create_agent("a1", "conversation", {})

        # CREATED -> PAUSED (无效)
        result = manager.pause_agent("a1")
        assert not result.success
        assert "invalid transition" in result.error.lower()

        # CREATED -> STOPPED (无效，还没启动)
        result = manager.stop_agent("a1")
        assert not result.success

    def test_transition_from_failed_state(self):
        """测试：从失败状态恢复"""
        from src.domain.services.management_modules import (
            AgentLifecycleManager,
            AgentState,
        )

        manager = AgentLifecycleManager()
        manager.create_agent("a1", "conversation", {})
        manager.start_agent("a1")

        # 模拟失败
        manager.mark_failed("a1", reason="Test failure")
        assert manager.get_agent("a1").state == AgentState.FAILED

        # 从失败状态重启
        result = manager.restart_agent("a1")
        assert result.success
        assert manager.get_agent("a1").state == AgentState.RUNNING


class TestAgentLifecycleEvents:
    """Agent 生命周期事件测试"""

    def test_lifecycle_events_emitted(self):
        """测试：生命周期事件发布"""
        from src.domain.services.management_modules import AgentLifecycleManager

        manager = AgentLifecycleManager()
        events = []

        # 订阅事件
        manager.on_state_change(lambda e: events.append(e))

        manager.create_agent("a1", "conversation", {})
        manager.start_agent("a1")
        manager.stop_agent("a1")

        assert len(events) >= 3
        event_types = [e.event_type for e in events]
        assert "agent_created" in event_types
        assert "agent_started" in event_types
        assert "agent_stopped" in event_types

    def test_event_contains_agent_info(self):
        """测试：事件包含 Agent 信息"""
        from src.domain.services.management_modules import AgentLifecycleManager

        manager = AgentLifecycleManager()
        events = []

        manager.on_state_change(lambda e: events.append(e))
        manager.create_agent("agent_001", "conversation", {"model": "gpt-4"})

        assert len(events) == 1
        event = events[0]
        assert event.agent_id == "agent_001"
        assert event.agent_type == "conversation"


class TestAgentHealthCheck:
    """Agent 健康检查测试"""

    def test_health_check_running_agent(self):
        """测试：运行中 Agent 的健康检查"""
        from src.domain.services.management_modules import AgentLifecycleManager

        manager = AgentLifecycleManager()
        manager.create_agent("a1", "conversation", {})
        manager.start_agent("a1")

        health = manager.health_check("a1")

        assert health.is_healthy
        assert health.state == "running"
        assert health.uptime_seconds >= 0

    def test_health_check_stopped_agent(self):
        """测试：已停止 Agent 的健康检查"""
        from src.domain.services.management_modules import AgentLifecycleManager

        manager = AgentLifecycleManager()
        manager.create_agent("a1", "conversation", {})

        health = manager.health_check("a1")

        assert not health.is_healthy
        assert health.state == "created"

    def test_health_check_nonexistent_agent(self):
        """测试：不存在 Agent 的健康检查"""
        from src.domain.services.management_modules import AgentLifecycleManager

        manager = AgentLifecycleManager()

        health = manager.health_check("nonexistent")

        assert not health.is_healthy
        assert health.error == "Agent not found"


# ==================== 3. 日志/告警处理器测试 ====================


class TestLogEntry:
    """日志条目测试"""

    def test_create_log_entry(self):
        """测试：创建日志条目"""
        from src.domain.services.management_modules import LogEntry, LogLevel

        entry = LogEntry(
            level=LogLevel.INFO,
            source="conversation_agent",
            message="Agent started",
            agent_id="agent_001",
        )

        assert entry.level == LogLevel.INFO
        assert entry.source == "conversation_agent"
        assert entry.message == "Agent started"
        assert entry.agent_id == "agent_001"
        assert entry.timestamp is not None

    def test_log_levels(self):
        """测试：日志级别"""
        from src.domain.services.management_modules import LogLevel

        assert LogLevel.DEBUG.value == "debug"
        assert LogLevel.INFO.value == "info"
        assert LogLevel.WARN.value == "warn"
        assert LogLevel.ERROR.value == "error"
        assert LogLevel.CRITICAL.value == "critical"

    def test_log_entry_to_dict(self):
        """测试：日志条目转字典"""
        from src.domain.services.management_modules import LogEntry, LogLevel

        entry = LogEntry(
            level=LogLevel.ERROR,
            source="workflow_agent",
            message="Execution failed",
            agent_id="wf_001",
            metadata={"node_id": "node_001"},
        )

        d = entry.to_dict()

        assert d["level"] == "error"
        assert d["source"] == "workflow_agent"
        assert d["message"] == "Execution failed"
        assert d["agent_id"] == "wf_001"
        assert d["metadata"]["node_id"] == "node_001"
        assert "timestamp" in d


class TestLogCollector:
    """日志采集器测试"""

    def test_collector_initialization(self):
        """测试：采集器初始化"""
        from src.domain.services.management_modules import LogCollector

        collector = LogCollector()
        assert collector.entry_count == 0

    def test_collect_log(self):
        """测试：采集日志"""
        from src.domain.services.management_modules import (
            LogCollector,
            LogLevel,
        )

        collector = LogCollector()

        collector.log(
            level=LogLevel.INFO,
            source="test",
            message="Test message",
        )

        assert collector.entry_count == 1

    def test_collect_multiple_logs(self):
        """测试：采集多条日志"""
        from src.domain.services.management_modules import (
            LogCollector,
            LogLevel,
        )

        collector = LogCollector()

        for i in range(10):
            collector.log(LogLevel.INFO, "test", f"Message {i}")

        assert collector.entry_count == 10

    def test_query_logs_by_level(self):
        """测试：按级别查询日志"""
        from src.domain.services.management_modules import (
            LogCollector,
            LogLevel,
        )

        collector = LogCollector()

        collector.log(LogLevel.INFO, "test", "Info 1")
        collector.log(LogLevel.ERROR, "test", "Error 1")
        collector.log(LogLevel.INFO, "test", "Info 2")
        collector.log(LogLevel.WARN, "test", "Warn 1")

        errors = collector.query(level=LogLevel.ERROR)
        assert len(errors) == 1
        assert errors[0].message == "Error 1"

    def test_query_logs_by_source(self):
        """测试：按来源查询日志"""
        from src.domain.services.management_modules import (
            LogCollector,
            LogLevel,
        )

        collector = LogCollector()

        collector.log(LogLevel.INFO, "agent_a", "From A")
        collector.log(LogLevel.INFO, "agent_b", "From B")
        collector.log(LogLevel.INFO, "agent_a", "From A again")

        from_a = collector.query(source="agent_a")
        assert len(from_a) == 2

    def test_query_logs_by_time_range(self):
        """测试：按时间范围查询日志"""
        from src.domain.services.management_modules import (
            LogCollector,
            LogLevel,
        )

        collector = LogCollector()

        # 记录日志
        collector.log(LogLevel.INFO, "test", "Message 1")
        time.sleep(0.01)
        start_time = datetime.now()
        time.sleep(0.01)
        collector.log(LogLevel.INFO, "test", "Message 2")
        collector.log(LogLevel.INFO, "test", "Message 3")
        time.sleep(0.01)
        end_time = datetime.now()
        time.sleep(0.01)
        collector.log(LogLevel.INFO, "test", "Message 4")

        # 查询时间范围内的日志
        results = collector.query(start_time=start_time, end_time=end_time)
        assert len(results) == 2

    def test_collector_max_entries(self):
        """测试：采集器最大条目限制"""
        from src.domain.services.management_modules import LogCollector, LogLevel

        collector = LogCollector(max_entries=100)

        for i in range(150):
            collector.log(LogLevel.INFO, "test", f"Message {i}")

        # 应该只保留最新的100条
        assert collector.entry_count == 100


class TestLogParser:
    """日志解析器测试"""

    def test_parse_error_pattern(self):
        """测试：解析错误模式"""
        from src.domain.services.management_modules import LogParser

        parser = LogParser()

        # 添加错误模式
        parser.add_pattern(
            name="exception",
            pattern=r"Exception:\s*(.+)",
            extract_fields=["error_message"],
        )

        result = parser.parse("Exception: Connection timeout")

        assert result.matched
        assert result.pattern_name == "exception"
        assert result.fields["error_message"] == "Connection timeout"

    def test_parse_performance_metrics(self):
        """测试：解析性能指标"""
        from src.domain.services.management_modules import LogParser

        parser = LogParser()

        parser.add_pattern(
            name="latency",
            pattern=r"Request completed in (\d+)ms",
            extract_fields=["latency_ms"],
            field_types={"latency_ms": int},
        )

        result = parser.parse("Request completed in 250ms")

        assert result.matched
        assert result.fields["latency_ms"] == 250

    def test_parse_no_match(self):
        """测试：无匹配的解析"""
        from src.domain.services.management_modules import LogParser

        parser = LogParser()

        result = parser.parse("Random log message")

        assert not result.matched
        assert result.pattern_name is None

    def test_parse_multiple_patterns(self):
        """测试：多模式解析"""
        from src.domain.services.management_modules import LogParser

        parser = LogParser()

        parser.add_pattern("error", r"ERROR:\s*(.+)", ["message"])
        parser.add_pattern("warn", r"WARN:\s*(.+)", ["message"])
        parser.add_pattern("info", r"INFO:\s*(.+)", ["message"])

        assert parser.parse("ERROR: Something bad").pattern_name == "error"
        assert parser.parse("WARN: Something odd").pattern_name == "warn"
        assert parser.parse("INFO: Something good").pattern_name == "info"


class TestAlertRule:
    """告警规则测试"""

    def test_create_alert_rule(self):
        """测试：创建告警规则"""
        from src.domain.services.management_modules import (
            AlertLevel,
            AlertRule,
        )

        rule = AlertRule(
            id="rule_001",
            name="高 CPU 告警",
            condition="cpu_percent > 90",
            level=AlertLevel.WARNING,
            message_template="CPU 使用率过高: {cpu_percent}%",
        )

        assert rule.id == "rule_001"
        assert rule.name == "高 CPU 告警"
        assert rule.level == AlertLevel.WARNING

    def test_alert_levels(self):
        """测试：告警级别"""
        from src.domain.services.management_modules import AlertLevel

        assert AlertLevel.INFO.value == "info"
        assert AlertLevel.WARNING.value == "warning"
        assert AlertLevel.ERROR.value == "error"
        assert AlertLevel.CRITICAL.value == "critical"


class TestAlertHandler:
    """告警处理器测试"""

    def test_handler_initialization(self):
        """测试：处理器初始化"""
        from src.domain.services.management_modules import AlertHandler

        handler = AlertHandler()
        assert handler.rule_count == 0
        assert handler.alert_count == 0

    def test_add_alert_rule(self):
        """测试：添加告警规则"""
        from src.domain.services.management_modules import (
            AlertHandler,
            AlertLevel,
        )

        handler = AlertHandler()

        rule_id = handler.add_rule(
            name="高内存告警",
            condition=lambda m: m.get("memory_percent", 0) > 90,
            level=AlertLevel.WARNING,
            message="内存使用率超过 90%",
        )

        assert handler.rule_count == 1
        assert rule_id is not None

    def test_evaluate_triggers_alert(self):
        """测试：评估触发告警"""
        from src.domain.services.management_modules import (
            AlertHandler,
            AlertLevel,
        )

        handler = AlertHandler()

        handler.add_rule(
            name="高 CPU 告警",
            condition=lambda m: m.get("cpu_percent", 0) > 90,
            level=AlertLevel.WARNING,
            message="CPU 使用率过高",
        )

        # 正常指标不触发
        alerts = handler.evaluate({"cpu_percent": 50})
        assert len(alerts) == 0

        # 超限指标触发
        alerts = handler.evaluate({"cpu_percent": 95})
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.WARNING

    def test_alert_suppression(self):
        """测试：告警抑制"""
        from src.domain.services.management_modules import (
            AlertHandler,
            AlertLevel,
        )

        handler = AlertHandler(suppression_seconds=60)

        handler.add_rule(
            name="测试告警",
            condition=lambda m: m.get("value", 0) > 10,
            level=AlertLevel.WARNING,
            message="Value too high",
        )

        # 第一次触发
        alerts1 = handler.evaluate({"value": 20})
        assert len(alerts1) == 1

        # 抑制期内不再触发
        alerts2 = handler.evaluate({"value": 25})
        assert len(alerts2) == 0

    def test_get_active_alerts(self):
        """测试：获取活跃告警"""
        from src.domain.services.management_modules import (
            AlertHandler,
            AlertLevel,
        )

        handler = AlertHandler(suppression_seconds=0)  # 禁用抑制

        handler.add_rule(
            name="规则1",
            condition=lambda m: m.get("a", 0) > 10,
            level=AlertLevel.WARNING,
            message="A too high",
        )
        handler.add_rule(
            name="规则2",
            condition=lambda m: m.get("b", 0) > 10,
            level=AlertLevel.ERROR,
            message="B too high",
        )

        handler.evaluate({"a": 20, "b": 5})  # 只触发规则1
        handler.evaluate({"a": 5, "b": 20})  # 只触发规则2

        active = handler.get_active_alerts()
        assert len(active) == 2

    def test_acknowledge_alert(self):
        """测试：确认告警"""
        from src.domain.services.management_modules import (
            AlertHandler,
            AlertLevel,
        )

        handler = AlertHandler(suppression_seconds=0)

        handler.add_rule(
            name="测试",
            condition=lambda m: True,
            level=AlertLevel.INFO,
            message="Test",
        )

        alerts = handler.evaluate({})
        alert_id = alerts[0].id

        result = handler.acknowledge(alert_id, acknowledged_by="admin")

        assert result.success
        assert handler.get_alert(alert_id).acknowledged


class TestLogAlertIntegration:
    """日志告警集成测试"""

    def test_log_triggers_alert(self):
        """测试：日志触发告警"""
        from src.domain.services.management_modules import (
            AlertLevel,
            LogAlertHandler,
            LogLevel,
        )

        handler = LogAlertHandler()

        # 添加基于日志的告警规则
        handler.add_log_alert_rule(
            name="错误日志告警",
            log_level=LogLevel.ERROR,
            alert_level=AlertLevel.WARNING,
            message="检测到错误日志",
        )

        # 记录普通日志不触发
        alerts = handler.log_and_check(LogLevel.INFO, "test", "Normal message")
        assert len(alerts) == 0

        # 记录错误日志触发告警
        alerts = handler.log_and_check(LogLevel.ERROR, "test", "Error occurred")
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.WARNING

    def test_pattern_based_alert(self):
        """测试：基于模式的告警"""
        from src.domain.services.management_modules import (
            AlertLevel,
            LogAlertHandler,
            LogLevel,
        )

        handler = LogAlertHandler()

        # 添加基于模式的告警规则
        handler.add_pattern_alert_rule(
            name="超时告警",
            pattern=r"timeout after (\d+)s",
            alert_level=AlertLevel.ERROR,
            message="检测到超时",
        )

        # 匹配模式触发告警
        alerts = handler.log_and_check(LogLevel.WARN, "test", "Request timeout after 30s")
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.ERROR

    def test_get_logs_and_alerts_summary(self):
        """测试：获取日志和告警摘要"""
        from src.domain.services.management_modules import (
            AlertLevel,
            LogAlertHandler,
            LogLevel,
        )

        handler = LogAlertHandler()

        handler.add_log_alert_rule(
            name="错误告警",
            log_level=LogLevel.ERROR,
            alert_level=AlertLevel.WARNING,
            message="Error detected",
        )

        # 记录一些日志
        handler.log_and_check(LogLevel.INFO, "a", "Info 1")
        handler.log_and_check(LogLevel.INFO, "b", "Info 2")
        handler.log_and_check(LogLevel.ERROR, "a", "Error 1")
        handler.log_and_check(LogLevel.WARN, "c", "Warn 1")

        summary = handler.get_summary()

        assert summary["total_logs"] == 4
        assert summary["logs_by_level"]["info"] == 2
        assert summary["logs_by_level"]["error"] == 1
        assert summary["logs_by_level"]["warn"] == 1
        assert summary["total_alerts"] == 1


# ==================== 4. 集成测试 ====================


class TestManagementModulesIntegration:
    """管理模块集成测试"""

    def test_scheduler_with_lifecycle_manager(self):
        """测试：调度器与生命周期管理器集成"""
        from src.domain.services.management_modules import (
            AgentLifecycleManager,
            ResourceScheduler,
            ScheduleRequest,
        )

        scheduler = ResourceScheduler()
        lifecycle = AgentLifecycleManager()

        # 提交调度请求
        req = ScheduleRequest(id="agent_001", priority=5, agent_type="conversation")
        result = scheduler.schedule(req)
        assert result.scheduled

        # 创建并启动 Agent
        lifecycle.create_agent("agent_001", "conversation", {})
        lifecycle.start_agent("agent_001")

        # 验证 Agent 运行
        health = lifecycle.health_check("agent_001")
        assert health.is_healthy

        # 停止 Agent 并完成调度
        lifecycle.stop_agent("agent_001")
        scheduler.complete("agent_001")

        assert scheduler.running_count == 0

    def test_lifecycle_with_log_handler(self):
        """测试：生命周期管理器与日志处理器集成"""
        from src.domain.services.management_modules import (
            AgentLifecycleManager,
            LogAlertHandler,
            LogLevel,
        )

        lifecycle = AgentLifecycleManager()
        log_handler = LogAlertHandler()

        # 配置生命周期事件日志
        def log_lifecycle_event(event):
            log_handler.log_and_check(
                LogLevel.INFO,
                source="lifecycle",
                message=f"Agent {event.agent_id}: {event.event_type}",
                agent_id=event.agent_id,
            )

        lifecycle.on_state_change(log_lifecycle_event)

        # 执行生命周期操作
        lifecycle.create_agent("a1", "conversation", {})
        lifecycle.start_agent("a1")
        lifecycle.stop_agent("a1")

        # 验证日志记录
        summary = log_handler.get_summary()
        assert summary["total_logs"] >= 3

    def test_full_management_flow(self):
        """测试：完整管理流程"""
        from src.domain.services.management_modules import (
            AgentLifecycleManager,
            AlertLevel,
            LogAlertHandler,
            LogLevel,
            ResourceQuota,
            ResourceScheduler,
            ScheduleRequest,
        )

        # 初始化组件
        quota = ResourceQuota(
            cpu_cores=4,
            memory_mb=8192,
            gpu_memory_mb=0,
            max_concurrent_agents=5,
        )
        scheduler = ResourceScheduler(quota=quota)
        lifecycle = AgentLifecycleManager()
        log_handler = LogAlertHandler()

        # 配置失败告警
        log_handler.add_log_alert_rule(
            name="Agent 失败告警",
            log_level=LogLevel.ERROR,
            alert_level=AlertLevel.ERROR,
            message="Agent failure detected",
        )

        # 模拟多个 Agent 的调度和管理
        for i in range(3):
            agent_id = f"agent_{i:03d}"

            # 调度
            req = ScheduleRequest(id=agent_id, priority=i, agent_type="conversation")
            scheduler.schedule(req)

            # 创建和启动
            lifecycle.create_agent(agent_id, "conversation", {})
            lifecycle.start_agent(agent_id)

            # 记录日志
            log_handler.log_and_check(
                LogLevel.INFO,
                source="management",
                message=f"Agent {agent_id} started successfully",
            )

        # 验证状态
        assert scheduler.running_count == 3
        assert log_handler.get_summary()["total_logs"] == 3

        # 模拟一个 Agent 失败
        lifecycle.mark_failed("agent_000", reason="Test failure")
        alerts = log_handler.log_and_check(
            LogLevel.ERROR,
            source="management",
            message="Agent agent_000 failed",
        )
        assert len(alerts) == 1

        # 重启失败的 Agent
        lifecycle.restart_agent("agent_000")

        # 清理
        for i in range(3):
            agent_id = f"agent_{i:03d}"
            lifecycle.stop_agent(agent_id)
            scheduler.complete(agent_id)

        assert scheduler.running_count == 0


class TestSchedulingDecisionBasis:
    """调度决策依据测试"""

    def test_decision_based_on_load(self):
        """测试：基于负载的调度决策"""
        from src.domain.services.management_modules import (
            LoadMetrics,
            ResourceScheduler,
            ScheduleRequest,
            SchedulingStrategy,
        )

        scheduler = ResourceScheduler(strategy=SchedulingStrategy.RESOURCE_AWARE)

        # 高负载时拒绝重资源请求
        scheduler.update_load(LoadMetrics(cpu_percent=85.0, memory_percent=80.0))

        heavy_req = ScheduleRequest(
            id="heavy",
            priority=1,
            agent_type="workflow",
            resource_requirement={"cpu_cores": 4, "memory_mb": 8192},
        )
        result = scheduler.schedule(heavy_req)
        assert not result.scheduled
        assert "load" in result.reason.lower() or "resource" in result.reason.lower()

    def test_decision_based_on_priority(self):
        """测试：基于优先级的调度决策"""
        from src.domain.services.management_modules import (
            ResourceQuota,
            ResourceScheduler,
            ScheduleRequest,
            SchedulingStrategy,
        )

        quota = ResourceQuota(
            cpu_cores=2,
            memory_mb=4096,
            gpu_memory_mb=0,
            max_concurrent_agents=2,
        )
        scheduler = ResourceScheduler(
            strategy=SchedulingStrategy.PRIORITY,
            quota=quota,
        )

        # 先添加低优先级请求
        low_req = ScheduleRequest(id="low", priority=10, agent_type="conversation")
        scheduler.schedule(low_req)

        # 再添加高优先级请求
        high_req = ScheduleRequest(id="high", priority=1, agent_type="workflow")
        result = scheduler.schedule(high_req)

        # 高优先级请求应该被调度
        assert result.scheduled

    def test_decision_based_on_quota(self):
        """测试：基于配额的调度决策"""
        from src.domain.services.management_modules import (
            ResourceQuota,
            ResourceScheduler,
            ScheduleRequest,
        )

        quota = ResourceQuota(
            cpu_cores=4,
            memory_mb=8192,
            gpu_memory_mb=0,
            max_concurrent_agents=2,
        )
        scheduler = ResourceScheduler(quota=quota)

        # 调度到配额上限
        scheduler.schedule(ScheduleRequest(id="a1", priority=5, agent_type="conv"))
        scheduler.schedule(ScheduleRequest(id="a2", priority=5, agent_type="conv"))

        # 超出配额时拒绝
        result = scheduler.schedule(ScheduleRequest(id="a3", priority=1, agent_type="conv"))
        assert not result.scheduled
        assert "quota" in result.reason.lower() or "limit" in result.reason.lower()

    def test_get_scheduling_decision_details(self):
        """测试：获取调度决策详情"""
        from src.domain.services.management_modules import (
            LoadMetrics,
            ResourceScheduler,
            ScheduleRequest,
        )

        scheduler = ResourceScheduler()
        scheduler.update_load(LoadMetrics(cpu_percent=60.0, memory_percent=50.0))

        req = ScheduleRequest(
            id="test",
            priority=5,
            agent_type="conversation",
            resource_requirement={"cpu_cores": 2, "memory_mb": 2048},
        )

        result = scheduler.schedule(req)

        # 决策应包含详细信息
        assert result.decision_basis is not None
        assert "load_metrics" in result.decision_basis
        assert "quota_available" in result.decision_basis
        assert "priority" in result.decision_basis
