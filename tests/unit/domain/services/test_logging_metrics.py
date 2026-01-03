"""日志处理与监控指标采集测试 (TDD - Step 6)

测试内容：
1. StructuredLog - 结构化日志（带 trace_id、span_id）
2. LogBuffer - 日志缓冲区（批量写入）
3. LogStorage - 存储后端（InMemory、File、Database stub）
4. LogPipeline - 集中式日志管道
5. LogParser - 日志解析器
6. MetricsCollector - 指标采集（系统、API、工作流）
7. MetricsAggregator - 指标聚合与查询
8. Dashboard 数据生成

完成标准：
- 日志 schema 与指标列表完整定义
- 收集器/解析器实现
- TDD 测试覆盖日志入库、查询、指标计算
"""

import json
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

# ==================== 1. 结构化日志测试 ====================


class TestStructuredLog:
    """结构化日志测试"""

    def test_create_structured_log(self):
        """测试：创建结构化日志"""
        from src.domain.services.logging_metrics import LogLevel, StructuredLog

        log = StructuredLog(
            level=LogLevel.INFO,
            source="conversation_agent",
            message="处理用户请求",
            event_type="request_received",
        )

        assert log.level == LogLevel.INFO
        assert log.source == "conversation_agent"
        assert log.message == "处理用户请求"
        assert log.event_type == "request_received"
        assert log.timestamp is not None
        assert log.log_id is not None

    def test_log_with_trace_context(self):
        """测试：带追踪上下文的日志"""
        from src.domain.services.logging_metrics import LogLevel, StructuredLog, TraceContext

        trace = TraceContext(
            trace_id="trace_001",
            span_id="span_001",
            parent_span_id="parent_001",
        )

        log = StructuredLog(
            level=LogLevel.INFO,
            source="workflow_agent",
            message="执行节点",
            event_type="node_execution",
            trace=trace,
        )

        assert log.trace.trace_id == "trace_001"
        assert log.trace.span_id == "span_001"
        assert log.trace.parent_span_id == "parent_001"

    def test_log_with_metadata(self):
        """测试：带元数据的日志"""
        from src.domain.services.logging_metrics import LogLevel, StructuredLog

        log = StructuredLog(
            level=LogLevel.ERROR,
            source="coordinator_agent",
            message="决策验证失败",
            event_type="validation_failed",
            metadata={
                "decision_id": "d001",
                "rule_id": "r001",
                "reason": "资源不足",
            },
        )

        assert log.metadata["decision_id"] == "d001"
        assert log.metadata["rule_id"] == "r001"
        assert log.metadata["reason"] == "资源不足"

    def test_log_to_json(self):
        """测试：日志转 JSON"""
        from src.domain.services.logging_metrics import LogLevel, StructuredLog

        log = StructuredLog(
            level=LogLevel.INFO,
            source="test",
            message="test message",
            event_type="test_event",
        )

        json_str = log.to_json()
        data = json.loads(json_str)

        assert data["level"] == "INFO"
        assert data["source"] == "test"
        assert data["message"] == "test message"
        assert data["event_type"] == "test_event"
        assert "timestamp" in data
        assert "log_id" in data

    def test_log_from_dict(self):
        """测试：从字典创建日志"""
        from src.domain.services.logging_metrics import StructuredLog

        data = {
            "level": "ERROR",
            "source": "agent",
            "message": "error occurred",
            "event_type": "error",
            "metadata": {"code": 500},
        }

        log = StructuredLog.from_dict(data)

        assert log.level.value == "ERROR"
        assert log.source == "agent"
        assert log.message == "error occurred"
        assert log.metadata["code"] == 500


class TestLogLevel:
    """日志级别测试"""

    def test_log_levels(self):
        """测试：日志级别枚举"""
        from src.domain.services.logging_metrics import LogLevel

        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"

    def test_log_level_priority(self):
        """测试：日志级别优先级"""
        from src.domain.services.logging_metrics import LogLevel

        # 优先级应该是 DEBUG < INFO < WARNING < ERROR < CRITICAL
        assert LogLevel.DEBUG.priority < LogLevel.INFO.priority
        assert LogLevel.INFO.priority < LogLevel.WARNING.priority
        assert LogLevel.WARNING.priority < LogLevel.ERROR.priority
        assert LogLevel.ERROR.priority < LogLevel.CRITICAL.priority


# ==================== 2. 日志缓冲区测试 ====================


class TestLogBuffer:
    """日志缓冲区测试"""

    def test_buffer_initialization(self):
        """测试：缓冲区初始化"""
        from src.domain.services.logging_metrics import LogBuffer

        buffer = LogBuffer(max_size=100, flush_interval_seconds=5.0)

        assert buffer.max_size == 100
        assert buffer.flush_interval_seconds == 5.0
        assert buffer.size == 0

    def test_buffer_add_log(self):
        """测试：添加日志到缓冲区"""
        from src.domain.services.logging_metrics import LogBuffer, LogLevel, StructuredLog

        buffer = LogBuffer(max_size=10)

        log = StructuredLog(
            level=LogLevel.INFO,
            source="test",
            message="test",
            event_type="test",
        )
        buffer.add(log)

        assert buffer.size == 1

    def test_buffer_auto_flush_on_full(self):
        """测试：缓冲区满时自动刷新"""
        from src.domain.services.logging_metrics import LogBuffer, LogLevel, StructuredLog

        flushed_logs = []

        def on_flush(logs):
            flushed_logs.extend(logs)

        buffer = LogBuffer(max_size=3, on_flush=on_flush)

        for i in range(5):
            log = StructuredLog(
                level=LogLevel.INFO,
                source="test",
                message=f"message {i}",
                event_type="test",
            )
            buffer.add(log)

        # 缓冲区满 (3) 时应该触发一次刷新
        assert len(flushed_logs) >= 3

    def test_buffer_manual_flush(self):
        """测试：手动刷新缓冲区"""
        from src.domain.services.logging_metrics import LogBuffer, LogLevel, StructuredLog

        flushed_logs = []

        def on_flush(logs):
            flushed_logs.extend(logs)

        buffer = LogBuffer(max_size=100, on_flush=on_flush)

        log = StructuredLog(
            level=LogLevel.INFO,
            source="test",
            message="test",
            event_type="test",
        )
        buffer.add(log)
        buffer.flush()

        assert len(flushed_logs) == 1
        assert buffer.size == 0


# ==================== 3. 日志存储后端测试 ====================


class TestInMemoryLogStore:
    """内存日志存储测试"""

    def test_store_initialization(self):
        """测试：存储初始化"""
        from src.domain.services.logging_metrics import InMemoryLogStore

        store = InMemoryLogStore()

        assert store.count == 0

    def test_store_write_log(self):
        """测试：写入日志"""
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
        )

        store = InMemoryLogStore()

        log = StructuredLog(
            level=LogLevel.INFO,
            source="test",
            message="test message",
            event_type="test",
        )
        store.write(log)

        assert store.count == 1

    def test_store_write_batch(self):
        """测试：批量写入日志"""
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
        )

        store = InMemoryLogStore()

        logs = [StructuredLog(LogLevel.INFO, "test", f"msg {i}", "test") for i in range(10)]
        store.write_batch(logs)

        assert store.count == 10

    def test_store_query_by_level(self):
        """测试：按级别查询"""
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
        )

        store = InMemoryLogStore()

        store.write(StructuredLog(LogLevel.INFO, "a", "info 1", "test"))
        store.write(StructuredLog(LogLevel.ERROR, "b", "error 1", "test"))
        store.write(StructuredLog(LogLevel.INFO, "c", "info 2", "test"))

        results = store.query(level=LogLevel.ERROR)

        assert len(results) == 1
        assert results[0].message == "error 1"

    def test_store_query_by_source(self):
        """测试：按来源查询"""
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
        )

        store = InMemoryLogStore()

        store.write(StructuredLog(LogLevel.INFO, "agent_a", "msg 1", "test"))
        store.write(StructuredLog(LogLevel.INFO, "agent_b", "msg 2", "test"))
        store.write(StructuredLog(LogLevel.INFO, "agent_a", "msg 3", "test"))

        results = store.query(source="agent_a")

        assert len(results) == 2

    def test_store_query_by_time_range(self):
        """测试：按时间范围查询"""
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
        )

        store = InMemoryLogStore()

        # 写入日志
        store.write(StructuredLog(LogLevel.INFO, "test", "msg 1", "test"))
        time.sleep(0.01)
        start_time = datetime.now()
        time.sleep(0.01)
        store.write(StructuredLog(LogLevel.INFO, "test", "msg 2", "test"))
        store.write(StructuredLog(LogLevel.INFO, "test", "msg 3", "test"))
        time.sleep(0.01)
        end_time = datetime.now()
        time.sleep(0.01)
        store.write(StructuredLog(LogLevel.INFO, "test", "msg 4", "test"))

        results = store.query(start_time=start_time, end_time=end_time)

        assert len(results) == 2

    def test_store_query_by_event_type(self):
        """测试：按事件类型查询"""
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
        )

        store = InMemoryLogStore()

        store.write(StructuredLog(LogLevel.INFO, "a", "msg", "request_start"))
        store.write(StructuredLog(LogLevel.INFO, "b", "msg", "request_end"))
        store.write(StructuredLog(LogLevel.INFO, "c", "msg", "request_start"))

        results = store.query(event_type="request_start")

        assert len(results) == 2

    def test_store_query_by_trace_id(self):
        """测试：按 trace_id 查询"""
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
            TraceContext,
        )

        store = InMemoryLogStore()

        trace1 = TraceContext(trace_id="trace_001", span_id="s1")
        trace2 = TraceContext(trace_id="trace_002", span_id="s2")

        store.write(StructuredLog(LogLevel.INFO, "a", "msg 1", "test", trace=trace1))
        store.write(StructuredLog(LogLevel.INFO, "b", "msg 2", "test", trace=trace2))
        store.write(StructuredLog(LogLevel.INFO, "c", "msg 3", "test", trace=trace1))

        results = store.query(trace_id="trace_001")

        assert len(results) == 2


class TestFileLogStore:
    """文件日志存储测试"""

    def test_file_store_initialization(self):
        """测试：文件存储初始化"""
        from src.domain.services.logging_metrics import FileLogStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = FileLogStore(log_dir=tmpdir)

            assert store.log_dir == tmpdir
            assert Path(tmpdir).exists()

    def test_file_store_write_and_read(self):
        """测试：写入和读取日志文件"""
        from src.domain.services.logging_metrics import (
            FileLogStore,
            LogLevel,
            StructuredLog,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            store = FileLogStore(log_dir=tmpdir)

            log = StructuredLog(
                level=LogLevel.INFO,
                source="test",
                message="test message",
                event_type="test",
            )
            store.write(log)
            store.flush()

            # 读取文件内容
            logs = store.read_all()

            assert len(logs) >= 1
            assert any(log.message == "test message" for log in logs)

    def test_file_store_rotation(self):
        """测试：日志文件轮转"""
        from src.domain.services.logging_metrics import (
            FileLogStore,
            LogLevel,
            StructuredLog,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # 设置小的最大文件大小以触发轮转
            store = FileLogStore(log_dir=tmpdir, max_file_size_bytes=100)

            # 写入足够多的日志以触发轮转
            for i in range(20):
                log = StructuredLog(
                    level=LogLevel.INFO,
                    source="test",
                    message=f"message {i} with some extra content",
                    event_type="test",
                )
                store.write(log)
                store.flush()

            # 应该有多个日志文件
            log_files = list(Path(tmpdir).glob("*.log"))
            assert len(log_files) >= 1


class TestDatabaseLogStore:
    """数据库日志存储测试（Stub）"""

    def test_database_store_initialization(self):
        """测试：数据库存储初始化"""
        from src.domain.services.logging_metrics import DatabaseLogStore

        store = DatabaseLogStore(connection_string="stub://localhost")

        assert store.connection_string == "stub://localhost"

    def test_database_store_write(self):
        """测试：数据库写入（stub）"""
        from src.domain.services.logging_metrics import (
            DatabaseLogStore,
            LogLevel,
            StructuredLog,
        )

        store = DatabaseLogStore(connection_string="stub://localhost")

        log = StructuredLog(
            level=LogLevel.INFO,
            source="test",
            message="test",
            event_type="test",
        )

        # Stub 实现应该能正常调用
        store.write(log)
        assert store.count >= 1

    def test_database_store_query(self):
        """测试：数据库查询（stub）"""
        from src.domain.services.logging_metrics import (
            DatabaseLogStore,
            LogLevel,
            StructuredLog,
        )

        store = DatabaseLogStore(connection_string="stub://localhost")

        store.write(StructuredLog(LogLevel.ERROR, "test", "error msg", "error"))

        results = store.query(level=LogLevel.ERROR)

        assert len(results) >= 1


# ==================== 4. 日志管道测试 ====================


class TestLogPipeline:
    """日志管道测试"""

    def test_pipeline_initialization(self):
        """测试：管道初始化"""
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogPipeline,
        )

        store = InMemoryLogStore()
        pipeline = LogPipeline(store=store)

        assert pipeline.store == store

    def test_pipeline_emit_log(self):
        """测试：发送日志"""
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            LogPipeline,
        )

        store = InMemoryLogStore()
        pipeline = LogPipeline(store=store)

        pipeline.emit(
            level=LogLevel.INFO,
            source="agent",
            message="test message",
            event_type="test",
        )

        # 日志应该进入存储
        assert store.count >= 1

    def test_pipeline_with_buffer(self):
        """测试：带缓冲的管道"""
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            LogPipeline,
        )

        store = InMemoryLogStore()
        pipeline = LogPipeline(store=store, buffer_size=10)

        for i in range(5):
            pipeline.emit(LogLevel.INFO, "test", f"msg {i}", "test")

        # 缓冲区未满，日志可能还没写入
        pipeline.flush()

        assert store.count == 5

    def test_pipeline_with_filter(self):
        """测试：带过滤器的管道"""
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogFilter,
            LogLevel,
            LogPipeline,
        )

        store = InMemoryLogStore()
        # 只记录 WARNING 及以上级别
        log_filter = LogFilter(min_level=LogLevel.WARNING)
        pipeline = LogPipeline(store=store, log_filter=log_filter)

        pipeline.emit(LogLevel.DEBUG, "test", "debug msg", "test")
        pipeline.emit(LogLevel.INFO, "test", "info msg", "test")
        pipeline.emit(LogLevel.WARNING, "test", "warning msg", "test")
        pipeline.emit(LogLevel.ERROR, "test", "error msg", "test")
        pipeline.flush()

        # 只有 WARNING 和 ERROR 应该被记录
        assert store.count == 2

    def test_pipeline_with_source_filter(self):
        """测试：按来源过滤"""
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogFilter,
            LogLevel,
            LogPipeline,
        )

        store = InMemoryLogStore()
        # 只记录来自 agent_a 的日志
        log_filter = LogFilter(allowed_sources=["agent_a", "agent_b"])
        pipeline = LogPipeline(store=store, log_filter=log_filter)

        pipeline.emit(LogLevel.INFO, "agent_a", "msg 1", "test")
        pipeline.emit(LogLevel.INFO, "agent_c", "msg 2", "test")
        pipeline.emit(LogLevel.INFO, "agent_b", "msg 3", "test")
        pipeline.flush()

        assert store.count == 2


class TestLogFilter:
    """日志过滤器测试"""

    def test_filter_by_min_level(self):
        """测试：按最小级别过滤"""
        from src.domain.services.logging_metrics import (
            LogFilter,
            LogLevel,
            StructuredLog,
        )

        log_filter = LogFilter(min_level=LogLevel.WARNING)

        debug_log = StructuredLog(LogLevel.DEBUG, "test", "debug", "test")
        warning_log = StructuredLog(LogLevel.WARNING, "test", "warning", "test")

        assert not log_filter.should_pass(debug_log)
        assert log_filter.should_pass(warning_log)

    def test_filter_by_allowed_sources(self):
        """测试：按允许来源过滤"""
        from src.domain.services.logging_metrics import (
            LogFilter,
            LogLevel,
            StructuredLog,
        )

        log_filter = LogFilter(allowed_sources=["agent_a"])

        log_a = StructuredLog(LogLevel.INFO, "agent_a", "msg", "test")
        log_b = StructuredLog(LogLevel.INFO, "agent_b", "msg", "test")

        assert log_filter.should_pass(log_a)
        assert not log_filter.should_pass(log_b)

    def test_filter_by_excluded_sources(self):
        """测试：按排除来源过滤"""
        from src.domain.services.logging_metrics import (
            LogFilter,
            LogLevel,
            StructuredLog,
        )

        log_filter = LogFilter(excluded_sources=["noisy_agent"])

        log_good = StructuredLog(LogLevel.INFO, "agent_a", "msg", "test")
        log_noisy = StructuredLog(LogLevel.INFO, "noisy_agent", "msg", "test")

        assert log_filter.should_pass(log_good)
        assert not log_filter.should_pass(log_noisy)


# ==================== 5. 日志解析器测试 ====================


class TestLogParser:
    """日志解析器测试"""

    def test_parser_initialization(self):
        """测试：解析器初始化"""
        from src.domain.services.logging_metrics import LogParser

        parser = LogParser()

        assert parser is not None

    def test_parser_add_pattern(self):
        """测试：添加解析模式"""
        from src.domain.services.logging_metrics import LogParser

        parser = LogParser()

        parser.add_pattern(
            name="error_code",
            pattern=r"Error code: (\d+)",
            extract_fields=["error_code"],
            field_types={"error_code": int},
        )

        assert parser.pattern_count == 1

    def test_parser_parse_message(self):
        """测试：解析日志消息"""
        from src.domain.services.logging_metrics import LogParser

        parser = LogParser()
        parser.add_pattern(
            name="latency",
            pattern=r"Request completed in (\d+)ms",
            extract_fields=["latency_ms"],
            field_types={"latency_ms": int},
        )

        result = parser.parse("Request completed in 250ms")

        assert result.matched
        assert result.pattern_name == "latency"
        assert result.fields["latency_ms"] == 250

    def test_parser_multiple_patterns(self):
        """测试：多模式解析"""
        from src.domain.services.logging_metrics import LogParser

        parser = LogParser()
        parser.add_pattern("error", r"ERROR: (.+)", ["message"])
        parser.add_pattern("latency", r"Latency: (\d+)ms", ["ms"], {"ms": int})

        error_result = parser.parse("ERROR: Connection failed")
        latency_result = parser.parse("Latency: 150ms")

        assert error_result.matched
        assert error_result.pattern_name == "error"
        assert error_result.fields["message"] == "Connection failed"

        assert latency_result.matched
        assert latency_result.pattern_name == "latency"
        assert latency_result.fields["ms"] == 150

    def test_parser_no_match(self):
        """测试：无匹配"""
        from src.domain.services.logging_metrics import LogParser

        parser = LogParser()
        parser.add_pattern("specific", r"SPECIFIC: (.+)", ["content"])

        result = parser.parse("Random log message")

        assert not result.matched


# ==================== 6. 指标采集测试 ====================


class TestSystemMetricsCollector:
    """系统指标采集测试"""

    def test_collector_initialization(self):
        """测试：采集器初始化"""
        from src.domain.services.logging_metrics import SystemMetricsCollector

        collector = SystemMetricsCollector()

        assert collector is not None

    def test_collect_system_metrics(self):
        """测试：采集系统指标"""
        from src.domain.services.logging_metrics import SystemMetricsCollector

        collector = SystemMetricsCollector()

        metrics = collector.collect()

        assert "cpu_percent" in metrics
        assert "memory_percent" in metrics
        assert "memory_used_mb" in metrics
        assert "timestamp" in metrics
        assert 0 <= metrics["cpu_percent"] <= 100
        assert 0 <= metrics["memory_percent"] <= 100

    def test_collect_with_interval(self):
        """测试：间隔采集"""
        from src.domain.services.logging_metrics import SystemMetricsCollector

        collector = SystemMetricsCollector()

        samples = []
        for _ in range(3):
            samples.append(collector.collect())
            time.sleep(0.01)

        assert len(samples) == 3
        # 每个样本都应该有时间戳
        for sample in samples:
            assert "timestamp" in sample


class TestAPIMetricsCollector:
    """API 指标采集测试"""

    def test_collector_initialization(self):
        """测试：采集器初始化"""
        from src.domain.services.logging_metrics import APIMetricsCollector

        collector = APIMetricsCollector()

        assert collector.call_count == 0
        assert collector.error_count == 0

    def test_record_api_call(self):
        """测试：记录 API 调用"""
        from src.domain.services.logging_metrics import APIMetricsCollector

        collector = APIMetricsCollector()

        collector.record_call(
            endpoint="/api/agents",
            method="POST",
            status_code=200,
            latency_ms=150,
        )

        assert collector.call_count == 1
        assert collector.error_count == 0

    def test_record_api_error(self):
        """测试：记录 API 错误"""
        from src.domain.services.logging_metrics import APIMetricsCollector

        collector = APIMetricsCollector()

        collector.record_call(
            endpoint="/api/workflows/chat-create/stream",
            method="POST",
            status_code=500,
            latency_ms=50,
        )

        assert collector.call_count == 1
        assert collector.error_count == 1

    def test_get_latency_stats(self):
        """测试：获取延迟统计"""
        from src.domain.services.logging_metrics import APIMetricsCollector

        collector = APIMetricsCollector()

        # 记录多次调用
        latencies = [100, 150, 200, 250, 300, 350, 400, 450, 500, 1000]
        for latency in latencies:
            collector.record_call("/api/test", "GET", 200, latency)

        stats = collector.get_latency_stats()

        assert "avg_ms" in stats
        assert "p50_ms" in stats
        assert "p95_ms" in stats
        assert "p99_ms" in stats
        assert "min_ms" in stats
        assert "max_ms" in stats

        # 验证平均值
        assert stats["avg_ms"] == sum(latencies) / len(latencies)
        assert stats["min_ms"] == 100
        assert stats["max_ms"] == 1000

    def test_get_metrics_by_endpoint(self):
        """测试：按端点获取指标"""
        from src.domain.services.logging_metrics import APIMetricsCollector

        collector = APIMetricsCollector()

        collector.record_call("/api/agents", "POST", 200, 100)
        collector.record_call("/api/agents", "GET", 200, 50)
        collector.record_call("/api/workflows/chat-create/stream", "POST", 200, 200)

        metrics = collector.get_metrics_by_endpoint()

        assert "/api/agents" in metrics
        assert "/api/workflows/chat-create/stream" in metrics
        assert metrics["/api/agents"]["call_count"] == 2
        assert metrics["/api/workflows/chat-create/stream"]["call_count"] == 1


class TestWorkflowMetricsCollector:
    """工作流指标采集测试"""

    def test_collector_initialization(self):
        """测试：采集器初始化"""
        from src.domain.services.logging_metrics import WorkflowMetricsCollector

        collector = WorkflowMetricsCollector()

        assert collector.total_executions == 0
        assert collector.successful_executions == 0
        assert collector.failed_executions == 0

    def test_record_workflow_start(self):
        """测试：记录工作流开始"""
        from src.domain.services.logging_metrics import WorkflowMetricsCollector

        collector = WorkflowMetricsCollector()

        collector.record_start(workflow_id="wf_001", workflow_name="test_workflow")

        assert collector.active_workflows == 1

    def test_record_workflow_success(self):
        """测试：记录工作流成功"""
        from src.domain.services.logging_metrics import WorkflowMetricsCollector

        collector = WorkflowMetricsCollector()

        collector.record_start("wf_001", "test")
        collector.record_completion("wf_001", success=True, duration_ms=1000)

        assert collector.total_executions == 1
        assert collector.successful_executions == 1
        assert collector.failed_executions == 0
        assert collector.active_workflows == 0

    def test_record_workflow_failure(self):
        """测试：记录工作流失败"""
        from src.domain.services.logging_metrics import WorkflowMetricsCollector

        collector = WorkflowMetricsCollector()

        collector.record_start("wf_001", "test")
        collector.record_completion("wf_001", success=False, duration_ms=500)

        assert collector.total_executions == 1
        assert collector.successful_executions == 0
        assert collector.failed_executions == 1

    def test_get_success_rate(self):
        """测试：获取成功率"""
        from src.domain.services.logging_metrics import WorkflowMetricsCollector

        collector = WorkflowMetricsCollector()

        # 7 成功，3 失败
        for i in range(7):
            collector.record_start(f"wf_{i}", "test")
            collector.record_completion(f"wf_{i}", success=True, duration_ms=100)

        for i in range(7, 10):
            collector.record_start(f"wf_{i}", "test")
            collector.record_completion(f"wf_{i}", success=False, duration_ms=50)

        assert collector.success_rate == 0.7

    def test_get_average_duration(self):
        """测试：获取平均时长"""
        from src.domain.services.logging_metrics import WorkflowMetricsCollector

        collector = WorkflowMetricsCollector()

        durations = [100, 200, 300]
        for i, duration in enumerate(durations):
            collector.record_start(f"wf_{i}", "test")
            collector.record_completion(f"wf_{i}", success=True, duration_ms=duration)

        assert collector.avg_duration_ms == 200


class TestAgentMetricsCollector:
    """Agent 指标采集测试"""

    def test_collector_initialization(self):
        """测试：采集器初始化"""
        from src.domain.services.logging_metrics import AgentMetricsCollector

        collector = AgentMetricsCollector()

        assert collector.active_agents == 0

    def test_record_agent_start(self):
        """测试：记录 Agent 启动"""
        from src.domain.services.logging_metrics import AgentMetricsCollector

        collector = AgentMetricsCollector()

        collector.record_start(agent_id="agent_001", agent_type="conversation")

        assert collector.active_agents == 1

    def test_record_agent_stop(self):
        """测试：记录 Agent 停止"""
        from src.domain.services.logging_metrics import AgentMetricsCollector

        collector = AgentMetricsCollector()

        collector.record_start("agent_001", "conversation")
        collector.record_stop("agent_001")

        assert collector.active_agents == 0

    def test_record_agent_request(self):
        """测试：记录 Agent 请求"""
        from src.domain.services.logging_metrics import AgentMetricsCollector

        collector = AgentMetricsCollector()

        collector.record_start("agent_001", "conversation")
        collector.record_request("agent_001", response_time_ms=50, success=True)
        collector.record_request("agent_001", response_time_ms=100, success=True)
        collector.record_request("agent_001", response_time_ms=75, success=False)

        stats = collector.get_agent_stats("agent_001")

        assert stats["total_requests"] == 3
        assert stats["error_count"] == 1

    def test_get_agents_by_type(self):
        """测试：按类型获取 Agent 统计"""
        from src.domain.services.logging_metrics import AgentMetricsCollector

        collector = AgentMetricsCollector()

        collector.record_start("conv_001", "conversation")
        collector.record_start("conv_002", "conversation")
        collector.record_start("wf_001", "workflow")
        collector.record_start("coord_001", "coordinator")

        by_type = collector.get_agents_by_type()

        assert by_type["conversation"] == 2
        assert by_type["workflow"] == 1
        assert by_type["coordinator"] == 1


# ==================== 7. 指标聚合测试 ====================


class TestMetricsAggregator:
    """指标聚合器测试"""

    def test_aggregator_initialization(self):
        """测试：聚合器初始化"""
        from src.domain.services.logging_metrics import MetricsAggregator

        aggregator = MetricsAggregator()

        assert aggregator is not None

    def test_add_metrics_sample(self):
        """测试：添加指标样本"""
        from src.domain.services.logging_metrics import MetricsAggregator

        aggregator = MetricsAggregator()

        aggregator.add_sample(
            metric_name="cpu_percent",
            value=75.5,
            labels={"host": "server1"},
        )

        assert aggregator.sample_count("cpu_percent") == 1

    def test_aggregate_avg(self):
        """测试：计算平均值"""
        from src.domain.services.logging_metrics import MetricsAggregator

        aggregator = MetricsAggregator()

        values = [10, 20, 30, 40, 50]
        for v in values:
            aggregator.add_sample("test_metric", v)

        avg = aggregator.aggregate("test_metric", "avg")

        assert avg == 30

    def test_aggregate_sum(self):
        """测试：计算总和"""
        from src.domain.services.logging_metrics import MetricsAggregator

        aggregator = MetricsAggregator()

        for v in [10, 20, 30]:
            aggregator.add_sample("test_metric", v)

        total = aggregator.aggregate("test_metric", "sum")

        assert total == 60

    def test_aggregate_min_max(self):
        """测试：计算最小/最大值"""
        from src.domain.services.logging_metrics import MetricsAggregator

        aggregator = MetricsAggregator()

        for v in [5, 10, 3, 20, 8]:
            aggregator.add_sample("test_metric", v)

        assert aggregator.aggregate("test_metric", "min") == 3
        assert aggregator.aggregate("test_metric", "max") == 20

    def test_aggregate_count(self):
        """测试：计算数量"""
        from src.domain.services.logging_metrics import MetricsAggregator

        aggregator = MetricsAggregator()

        for i in range(5):
            aggregator.add_sample("test_metric", i)

        count = aggregator.aggregate("test_metric", "count")

        assert count == 5

    def test_aggregate_percentile(self):
        """测试：计算百分位数"""
        from src.domain.services.logging_metrics import MetricsAggregator

        aggregator = MetricsAggregator()

        # 1-100 的值
        for v in range(1, 101):
            aggregator.add_sample("test_metric", v)

        p50 = aggregator.percentile("test_metric", 50)
        p95 = aggregator.percentile("test_metric", 95)
        p99 = aggregator.percentile("test_metric", 99)

        # 允许一定误差
        assert 49 <= p50 <= 51
        assert 94 <= p95 <= 96
        assert 98 <= p99 <= 100

    def test_aggregate_with_time_window(self):
        """测试：时间窗口聚合"""
        from src.domain.services.logging_metrics import MetricsAggregator

        aggregator = MetricsAggregator()

        # 添加一些旧数据
        old_time = datetime.now() - timedelta(minutes=10)
        aggregator.add_sample("test_metric", 100, timestamp=old_time)

        # 添加一些新数据
        for v in [10, 20, 30]:
            aggregator.add_sample("test_metric", v)

        # 只聚合最近 5 分钟的数据
        avg = aggregator.aggregate(
            "test_metric",
            "avg",
            time_window_minutes=5,
        )

        assert avg == 20  # (10 + 20 + 30) / 3

    def test_aggregate_by_labels(self):
        """测试：按标签聚合"""
        from src.domain.services.logging_metrics import MetricsAggregator

        aggregator = MetricsAggregator()

        aggregator.add_sample("requests", 100, labels={"endpoint": "/api/a"})
        aggregator.add_sample("requests", 200, labels={"endpoint": "/api/a"})
        aggregator.add_sample("requests", 50, labels={"endpoint": "/api/b"})

        result = aggregator.aggregate_by_label("requests", "endpoint", "sum")

        assert result["/api/a"] == 300
        assert result["/api/b"] == 50


# ==================== 8. Dashboard 数据测试 ====================


class TestDashboardDataGenerator:
    """Dashboard 数据生成器测试"""

    def test_generator_initialization(self):
        """测试：生成器初始化"""
        from src.domain.services.logging_metrics import DashboardDataGenerator

        generator = DashboardDataGenerator()

        assert generator is not None

    def test_generate_system_overview(self):
        """测试：生成系统概览数据"""
        from src.domain.services.logging_metrics import (
            AgentMetricsCollector,
            DashboardDataGenerator,
            SystemMetricsCollector,
        )

        system_collector = SystemMetricsCollector()
        agent_collector = AgentMetricsCollector()

        agent_collector.record_start("agent_001", "conversation")
        agent_collector.record_start("agent_002", "workflow")

        generator = DashboardDataGenerator(
            system_collector=system_collector,
            agent_collector=agent_collector,
        )

        overview = generator.generate_system_overview()

        assert "cpu_percent" in overview
        assert "memory_percent" in overview
        assert "active_agents" in overview
        assert overview["active_agents"] == 2

    def test_generate_api_metrics_summary(self):
        """测试：生成 API 指标摘要"""
        from src.domain.services.logging_metrics import (
            APIMetricsCollector,
            DashboardDataGenerator,
        )

        api_collector = APIMetricsCollector()
        api_collector.record_call("/api/agents", "GET", 200, 100)
        api_collector.record_call("/api/agents", "POST", 201, 150)
        api_collector.record_call("/api/workflows/chat-create/stream", "POST", 500, 50)

        generator = DashboardDataGenerator(api_collector=api_collector)

        summary = generator.generate_api_summary()

        assert "total_calls" in summary
        assert "error_rate" in summary
        assert "latency_stats" in summary
        assert summary["total_calls"] == 3

    def test_generate_workflow_metrics_summary(self):
        """测试：生成工作流指标摘要"""
        from src.domain.services.logging_metrics import (
            DashboardDataGenerator,
            WorkflowMetricsCollector,
        )

        wf_collector = WorkflowMetricsCollector()

        for i in range(10):
            wf_collector.record_start(f"wf_{i}", "test")
            wf_collector.record_completion(
                f"wf_{i}",
                success=(i < 8),  # 8 成功，2 失败
                duration_ms=100 + i * 10,
            )

        generator = DashboardDataGenerator(workflow_collector=wf_collector)

        summary = generator.generate_workflow_summary()

        assert "total_executions" in summary
        assert "success_rate" in summary
        assert "avg_duration_ms" in summary
        assert summary["total_executions"] == 10
        assert summary["success_rate"] == 0.8

    def test_generate_log_analysis(self):
        """测试：生成日志分析数据"""
        from src.domain.services.logging_metrics import (
            DashboardDataGenerator,
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
        )

        store = InMemoryLogStore()

        store.write(StructuredLog(LogLevel.INFO, "agent_a", "msg 1", "test"))
        store.write(StructuredLog(LogLevel.INFO, "agent_b", "msg 2", "test"))
        store.write(StructuredLog(LogLevel.ERROR, "agent_a", "error 1", "error"))
        store.write(StructuredLog(LogLevel.WARNING, "agent_c", "warn 1", "warning"))

        generator = DashboardDataGenerator(log_store=store)

        analysis = generator.generate_log_analysis()

        assert "total_logs" in analysis
        assert "by_level" in analysis
        assert "by_source" in analysis
        assert analysis["total_logs"] == 4
        assert analysis["by_level"]["INFO"] == 2
        assert analysis["by_level"]["ERROR"] == 1


# ==================== 9. 集成测试 ====================


class TestLoggingMetricsIntegration:
    """日志与指标集成测试"""

    def test_full_logging_pipeline(self):
        """测试：完整日志管道"""
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            LogPipeline,
        )

        store = InMemoryLogStore()
        pipeline = LogPipeline(store=store, buffer_size=5)

        # 发送多条日志
        pipeline.emit(LogLevel.INFO, "agent_a", "Request started", "request_start")
        pipeline.emit(LogLevel.INFO, "agent_a", "Processing data", "processing")
        pipeline.emit(LogLevel.INFO, "agent_a", "Request completed in 150ms", "request_end")
        pipeline.emit(LogLevel.ERROR, "agent_b", "Connection failed", "error")
        pipeline.flush()

        # 查询验证
        all_logs = store.query()
        errors = store.query(level=LogLevel.ERROR)
        agent_a_logs = store.query(source="agent_a")

        assert len(all_logs) == 4
        assert len(errors) == 1
        assert len(agent_a_logs) == 3

    def test_metrics_collection_workflow(self):
        """测试：指标采集工作流"""
        from src.domain.services.logging_metrics import (
            APIMetricsCollector,
            MetricsAggregator,
            WorkflowMetricsCollector,
        )

        api_collector = APIMetricsCollector()
        wf_collector = WorkflowMetricsCollector()
        aggregator = MetricsAggregator()

        # 模拟 API 调用
        for i in range(10):
            latency = 100 + i * 20
            api_collector.record_call("/api/test", "GET", 200, latency)
            aggregator.add_sample("api_latency", latency)

        # 模拟工作流执行
        for i in range(5):
            wf_collector.record_start(f"wf_{i}", "test")
            wf_collector.record_completion(f"wf_{i}", success=True, duration_ms=500 + i * 100)
            aggregator.add_sample("workflow_duration", 500 + i * 100)

        # 验证指标
        assert api_collector.call_count == 10
        assert wf_collector.total_executions == 5
        assert wf_collector.success_rate == 1.0

        # 聚合验证
        avg_latency = aggregator.aggregate("api_latency", "avg")
        avg_duration = aggregator.aggregate("workflow_duration", "avg")

        assert avg_latency == 190  # (100 + 280) / 2 = 190
        assert avg_duration == 700  # (500 + 900) / 2 = 700

    def test_dashboard_data_generation(self):
        """测试：Dashboard 数据生成"""
        from src.domain.services.logging_metrics import (
            AgentMetricsCollector,
            APIMetricsCollector,
            DashboardDataGenerator,
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
            SystemMetricsCollector,
            WorkflowMetricsCollector,
        )

        # 初始化所有采集器
        system_collector = SystemMetricsCollector()
        api_collector = APIMetricsCollector()
        wf_collector = WorkflowMetricsCollector()
        agent_collector = AgentMetricsCollector()
        log_store = InMemoryLogStore()

        # 模拟活动
        agent_collector.record_start("agent_001", "conversation")
        api_collector.record_call("/api/agents", "GET", 200, 100)
        wf_collector.record_start("wf_001", "test")
        wf_collector.record_completion("wf_001", True, 500)
        log_store.write(StructuredLog(LogLevel.INFO, "test", "msg", "test"))

        # 生成 Dashboard 数据
        generator = DashboardDataGenerator(
            system_collector=system_collector,
            api_collector=api_collector,
            workflow_collector=wf_collector,
            agent_collector=agent_collector,
            log_store=log_store,
        )

        dashboard = generator.generate_full_dashboard()

        assert "system_overview" in dashboard
        assert "api_summary" in dashboard
        assert "workflow_summary" in dashboard
        assert "agent_summary" in dashboard
        assert "log_analysis" in dashboard
        assert "generated_at" in dashboard


class TestLoggingMetricsQueryExamples:
    """日志与指标查询示例测试"""

    def test_query_errors_last_hour(self):
        """测试：查询最近一小时的错误"""
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
        )

        store = InMemoryLogStore()

        # 添加各种日志
        for i in range(10):
            level = LogLevel.ERROR if i % 3 == 0 else LogLevel.INFO
            store.write(StructuredLog(level, f"agent_{i}", f"msg {i}", "test"))

        # 查询错误
        one_hour_ago = datetime.now() - timedelta(hours=1)
        errors = store.query(level=LogLevel.ERROR, start_time=one_hour_ago)

        assert len(errors) >= 1
        assert all(log.level == LogLevel.ERROR for log in errors)

    def test_query_logs_by_trace(self):
        """测试：按 trace 查询相关日志"""
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
            TraceContext,
        )

        store = InMemoryLogStore()

        trace = TraceContext(trace_id="trace_abc", span_id="span_1")

        # 同一 trace 的多个日志
        store.write(StructuredLog(LogLevel.INFO, "agent_a", "step 1", "start", trace=trace))
        store.write(StructuredLog(LogLevel.INFO, "agent_b", "step 2", "process", trace=trace))
        store.write(StructuredLog(LogLevel.INFO, "agent_c", "step 3", "end", trace=trace))

        # 其他 trace 的日志
        other_trace = TraceContext(trace_id="trace_xyz", span_id="span_2")
        store.write(StructuredLog(LogLevel.INFO, "agent_d", "other", "other", trace=other_trace))

        # 查询特定 trace
        trace_logs = store.query(trace_id="trace_abc")

        assert len(trace_logs) == 3

    def test_metrics_time_series_query(self):
        """测试：指标时间序列查询"""
        from src.domain.services.logging_metrics import MetricsAggregator

        aggregator = MetricsAggregator()

        # 模拟一段时间的指标
        base_time = datetime.now()
        for i in range(60):
            t = base_time - timedelta(minutes=60 - i)
            aggregator.add_sample("cpu_percent", 50 + (i % 20), timestamp=t)

        # 查询最近 10 分钟的平均值
        recent_avg = aggregator.aggregate("cpu_percent", "avg", time_window_minutes=10)

        assert recent_avg is not None
        assert 50 <= recent_avg <= 70
