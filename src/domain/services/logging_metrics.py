"""日志处理与监控指标采集 (Logging & Metrics) - Step 6

提供集中式日志管道和指标采集的完整实现：

1. StructuredLog - 结构化日志（带 trace_id、span_id）
2. LogBuffer - 日志缓冲区（批量写入）
3. LogStorage - 存储后端（InMemory、File、Database stub）
4. LogPipeline - 集中式日志管道
5. LogParser - 日志解析器
6. MetricsCollector - 指标采集（系统、API、工作流、Agent）
7. MetricsAggregator - 指标聚合与查询
8. DashboardDataGenerator - 仪表盘数据生成

日志 Schema:
    {
        "log_id": "唯一标识",
        "timestamp": "ISO8601 时间戳",
        "level": "DEBUG|INFO|WARNING|ERROR|CRITICAL",
        "source": "日志来源（agent_id 或组件名）",
        "message": "日志消息",
        "event_type": "事件类型",
        "trace": {
            "trace_id": "分布式追踪 ID",
            "span_id": "当前 span ID",
            "parent_span_id": "父 span ID"
        },
        "metadata": { "任意附加数据" }
    }

指标列表:
    系统指标: cpu_percent, memory_percent, memory_used_mb, disk_usage_percent
    API指标: call_count, error_count, latency_avg/p50/p95/p99/min/max
    工作流指标: total_executions, successful/failed, success_rate, avg_duration
    Agent指标: active_agents, agents_by_type, request_count, error_rate

用法：
    # 日志管道
    store = InMemoryLogStore()
    pipeline = LogPipeline(store=store, buffer_size=100)
    pipeline.emit(LogLevel.INFO, "agent_001", "处理请求", "request_start")

    # 指标采集
    api_collector = APIMetricsCollector()
    api_collector.record_call("/api/agents", "POST", 200, 150)

    # 仪表盘数据
    generator = DashboardDataGenerator(...)
    dashboard = generator.generate_full_dashboard()
"""

from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

# ==================== 1. 日志级别与追踪上下文 ====================


class LogLevel(str, Enum):
    """日志级别枚举"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @property
    def priority(self) -> int:
        """获取优先级（用于过滤）"""
        priorities = {
            "DEBUG": 0,
            "INFO": 1,
            "WARNING": 2,
            "ERROR": 3,
            "CRITICAL": 4,
        }
        return priorities[self.value]


@dataclass
class TraceContext:
    """分布式追踪上下文

    属性：
        trace_id: 追踪 ID（标识整个请求链路）
        span_id: 当前 span ID
        parent_span_id: 父 span ID（可选）
    """

    trace_id: str
    span_id: str
    parent_span_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
        }


# ==================== 2. 结构化日志 ====================


@dataclass
class StructuredLog:
    """结构化日志

    属性：
        level: 日志级别
        source: 日志来源
        message: 日志消息
        event_type: 事件类型
        trace: 追踪上下文（可选）
        metadata: 元数据（可选）
        timestamp: 时间戳
        log_id: 日志唯一标识
    """

    level: LogLevel
    source: str
    message: str
    event_type: str
    trace: TraceContext | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    log_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        result = {
            "log_id": self.log_id,
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "source": self.source,
            "message": self.message,
            "event_type": self.event_type,
            "metadata": self.metadata,
        }
        if self.trace:
            result["trace"] = self.trace.to_dict()
        return result

    def to_json(self, pretty: bool = True) -> str:
        """转换为 JSON 字符串

        参数：
            pretty: 是否美化输出（默认 True）
        """
        if pretty:
            return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StructuredLog:
        """从字典创建日志"""
        trace = None
        if "trace" in data and data["trace"]:
            trace = TraceContext(**data["trace"])

        return cls(
            level=LogLevel(data["level"]),
            source=data["source"],
            message=data["message"],
            event_type=data.get("event_type", ""),
            trace=trace,
            metadata=data.get("metadata", {}),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if "timestamp" in data
            else datetime.now(),
            log_id=data.get("log_id", str(uuid.uuid4())[:8]),
        )


# ==================== 3. 日志缓冲区 ====================


class LogBuffer:
    """日志缓冲区

    提供批量写入能力，减少 I/O 频率。

    属性：
        max_size: 最大缓冲大小
        flush_interval_seconds: 刷新间隔（秒）
        on_flush: 刷新回调函数
    """

    def __init__(
        self,
        max_size: int = 100,
        flush_interval_seconds: float = 5.0,
        on_flush: Callable[[list[StructuredLog]], None] | None = None,
    ) -> None:
        self.max_size = max_size
        self.flush_interval_seconds = flush_interval_seconds
        self.on_flush = on_flush
        self._buffer: list[StructuredLog] = []
        self._last_flush: datetime = datetime.now()

    @property
    def size(self) -> int:
        """当前缓冲区大小"""
        return len(self._buffer)

    def add(self, log: StructuredLog) -> None:
        """添加日志到缓冲区"""
        self._buffer.append(log)

        # 缓冲区满时自动刷新
        if len(self._buffer) >= self.max_size:
            self.flush()

    def flush(self) -> list[StructuredLog]:
        """刷新缓冲区"""
        logs = self._buffer.copy()
        self._buffer.clear()
        self._last_flush = datetime.now()

        if self.on_flush and logs:
            self.on_flush(logs)

        return logs


# ==================== 4. 日志存储后端 ====================


class LogStore(Protocol):
    """日志存储接口"""

    def write(self, log: StructuredLog) -> None:
        """写入单条日志"""
        ...

    def write_batch(self, logs: list[StructuredLog]) -> None:
        """批量写入日志"""
        ...

    def query(
        self,
        level: LogLevel | None = None,
        source: str | None = None,
        event_type: str | None = None,
        trace_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[StructuredLog]:
        """查询日志"""
        ...

    @property
    def count(self) -> int:
        """日志总数"""
        ...


class InMemoryLogStore:
    """内存日志存储

    适用于测试和小规模场景。
    """

    def __init__(self, max_entries: int = 10000) -> None:
        self._logs: list[StructuredLog] = []
        self._max_entries = max_entries

    @property
    def count(self) -> int:
        """日志总数"""
        return len(self._logs)

    def write(self, log: StructuredLog) -> None:
        """写入日志"""
        self._logs.append(log)
        if len(self._logs) > self._max_entries:
            self._logs = self._logs[-self._max_entries :]

    def write_batch(self, logs: list[StructuredLog]) -> None:
        """批量写入"""
        for log in logs:
            self.write(log)

    def query(
        self,
        level: LogLevel | None = None,
        source: str | None = None,
        event_type: str | None = None,
        trace_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[StructuredLog]:
        """查询日志"""
        results: list[StructuredLog] = []

        for log in self._logs:
            if level is not None and log.level != level:
                continue
            if source is not None and log.source != source:
                continue
            if event_type is not None and log.event_type != event_type:
                continue
            if trace_id is not None:
                if log.trace is None or log.trace.trace_id != trace_id:
                    continue
            if start_time is not None and log.timestamp < start_time:
                continue
            if end_time is not None and log.timestamp > end_time:
                continue

            results.append(log)
            if len(results) >= limit:
                break

        return results

    def aggregate_by_level(self) -> dict[str, int]:
        """按级别聚合"""
        stats: dict[str, int] = {}
        for log in self._logs:
            stats[log.level.value] = stats.get(log.level.value, 0) + 1
        return stats

    def aggregate_by_source(self) -> dict[str, int]:
        """按来源聚合"""
        stats: dict[str, int] = {}
        for log in self._logs:
            stats[log.source] = stats.get(log.source, 0) + 1
        return stats


class FileLogStore:
    """文件日志存储

    支持日志轮转。
    """

    def __init__(
        self,
        log_dir: str,
        max_file_size_bytes: int = 10 * 1024 * 1024,  # 10MB
        max_files: int = 10,
    ) -> None:
        self.log_dir = log_dir
        self.max_file_size_bytes = max_file_size_bytes
        self.max_files = max_files
        self._current_file: Path | None = None
        self._buffer: list[str] = []

        # 确保目录存在
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        self._init_current_file()

    def _init_current_file(self) -> None:
        """初始化当前日志文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._current_file = Path(self.log_dir) / f"app_{timestamp}.log"

    def _rotate_if_needed(self) -> None:
        """检查并执行日志轮转"""
        if self._current_file and self._current_file.exists():
            if self._current_file.stat().st_size >= self.max_file_size_bytes:
                self._init_current_file()
                self._cleanup_old_files()

    def _cleanup_old_files(self) -> None:
        """清理旧日志文件"""
        log_files = sorted(Path(self.log_dir).glob("*.log"), key=lambda p: p.stat().st_mtime)
        while len(log_files) > self.max_files:
            log_files[0].unlink()
            log_files = log_files[1:]

    def write(self, log: StructuredLog) -> None:
        """写入日志"""
        # 使用单行 JSON 格式便于逐行读取
        self._buffer.append(log.to_json(pretty=False))

    def write_batch(self, logs: list[StructuredLog]) -> None:
        """批量写入"""
        for log in logs:
            self._buffer.append(log.to_json())

    def flush(self) -> None:
        """刷新到文件"""
        if not self._buffer or not self._current_file:
            return

        self._rotate_if_needed()

        with open(self._current_file, "a", encoding="utf-8") as f:
            for line in self._buffer:
                f.write(line + "\n")

        self._buffer.clear()

    def read_all(self) -> list[StructuredLog]:
        """读取所有日志"""
        logs: list[StructuredLog] = []

        for log_file in Path(self.log_dir).glob("*.log"):
            with open(log_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            logs.append(StructuredLog.from_dict(data))
                        except (json.JSONDecodeError, KeyError):
                            continue

        return logs

    def query(
        self,
        level: LogLevel | None = None,
        source: str | None = None,
        **kwargs: Any,
    ) -> list[StructuredLog]:
        """查询日志"""
        all_logs = self.read_all()
        results: list[StructuredLog] = []

        for log in all_logs:
            if level is not None and log.level != level:
                continue
            if source is not None and log.source != source:
                continue
            results.append(log)

        return results


class DatabaseLogStore:
    """数据库日志存储（Stub 实现）

    提供数据库存储的接口定义，实际实现可对接 PostgreSQL、MongoDB 等。
    """

    def __init__(self, connection_string: str) -> None:
        self.connection_string = connection_string
        # Stub: 使用内存存储模拟
        self._memory_store = InMemoryLogStore()

    @property
    def count(self) -> int:
        """日志总数"""
        return self._memory_store.count

    def write(self, log: StructuredLog) -> None:
        """写入日志"""
        # Stub: 实际应该写入数据库
        self._memory_store.write(log)

    def write_batch(self, logs: list[StructuredLog]) -> None:
        """批量写入"""
        self._memory_store.write_batch(logs)

    def query(
        self,
        level: LogLevel | None = None,
        source: str | None = None,
        **kwargs: Any,
    ) -> list[StructuredLog]:
        """查询日志"""
        return self._memory_store.query(level=level, source=source, **kwargs)


# ==================== 5. 日志过滤器 ====================


@dataclass
class LogFilter:
    """日志过滤器

    属性：
        min_level: 最小日志级别
        allowed_sources: 允许的来源列表（空表示全部允许）
        excluded_sources: 排除的来源列表
    """

    min_level: LogLevel | None = None
    allowed_sources: list[str] | None = None
    excluded_sources: list[str] | None = None

    def should_pass(self, log: StructuredLog) -> bool:
        """判断日志是否应该通过过滤"""
        # 级别过滤
        if self.min_level is not None:
            if log.level.priority < self.min_level.priority:
                return False

        # 允许来源过滤
        if self.allowed_sources is not None:
            if log.source not in self.allowed_sources:
                return False

        # 排除来源过滤
        if self.excluded_sources is not None:
            if log.source in self.excluded_sources:
                return False

        return True


# ==================== 6. 日志管道 ====================


class LogPipeline:
    """集中式日志管道

    连接日志生产者和存储后端，支持缓冲和过滤。
    """

    def __init__(
        self,
        store: LogStore | InMemoryLogStore,
        buffer_size: int | None = None,
        log_filter: LogFilter | None = None,
    ) -> None:
        self.store = store
        self.log_filter = log_filter
        self._use_buffer = buffer_size is not None and buffer_size > 1

        # 设置缓冲区
        if self._use_buffer and buffer_size is not None:
            self._buffer = LogBuffer(
                max_size=buffer_size,
                on_flush=self._on_buffer_flush,
            )
        else:
            self._buffer = None

    def _on_buffer_flush(self, logs: list[StructuredLog]) -> None:
        """缓冲区刷新回调"""
        if hasattr(self.store, "write_batch"):
            self.store.write_batch(logs)
        else:
            for log in logs:
                self.store.write(log)

    def emit(
        self,
        level: LogLevel,
        source: str,
        message: str,
        event_type: str,
        trace: TraceContext | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """发送日志"""
        log = StructuredLog(
            level=level,
            source=source,
            message=message,
            event_type=event_type,
            trace=trace,
            metadata=metadata or {},
        )

        # 应用过滤器
        if self.log_filter and not self.log_filter.should_pass(log):
            return

        # 根据是否使用缓冲决定写入方式
        if self._use_buffer and self._buffer:
            self._buffer.add(log)
        else:
            # 直接写入存储
            self.store.write(log)

    def flush(self) -> None:
        """刷新缓冲区"""
        if self._buffer:
            self._buffer.flush()


# ==================== 7. 日志解析器 ====================


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

    基于正则表达式模式解析日志消息。
    """

    def __init__(self) -> None:
        self._patterns: list[LogPattern] = []

    @property
    def pattern_count(self) -> int:
        """模式数量"""
        return len(self._patterns)

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


# ==================== 8. 指标采集器 ====================


class SystemMetricsCollector:
    """系统指标采集器

    采集 CPU、内存等系统指标。
    """

    def __init__(self) -> None:
        self._samples: list[dict[str, Any]] = []

    def collect(self) -> dict[str, Any]:
        """采集系统指标"""
        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            metrics = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_mb": memory.used / (1024 * 1024),
                "memory_available_mb": memory.available / (1024 * 1024),
                "disk_usage_percent": disk.percent,
                "timestamp": datetime.now().isoformat(),
            }
        except ImportError:
            # psutil 不可用时使用模拟数据
            import random

            metrics = {
                "cpu_percent": random.uniform(10, 80),
                "memory_percent": random.uniform(30, 70),
                "memory_used_mb": random.uniform(1000, 4000),
                "memory_available_mb": random.uniform(2000, 8000),
                "disk_usage_percent": random.uniform(20, 60),
                "timestamp": datetime.now().isoformat(),
            }

        self._samples.append(metrics)
        return metrics


class APIMetricsCollector:
    """API 指标采集器

    记录 API 调用次数、延迟等指标。
    """

    def __init__(self) -> None:
        self._calls: list[dict[str, Any]] = []
        self._by_endpoint: dict[str, list[dict[str, Any]]] = defaultdict(list)

    @property
    def call_count(self) -> int:
        """总调用次数"""
        return len(self._calls)

    @property
    def error_count(self) -> int:
        """错误次数"""
        return sum(1 for call in self._calls if call["status_code"] >= 400)

    def record_call(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        latency_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录 API 调用"""
        call = {
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "timestamp": datetime.now(),
            "metadata": metadata or {},
        }
        self._calls.append(call)
        self._by_endpoint[endpoint].append(call)

    def get_latency_stats(self) -> dict[str, float]:
        """获取延迟统计"""
        if not self._calls:
            return {
                "avg_ms": 0,
                "min_ms": 0,
                "max_ms": 0,
                "p50_ms": 0,
                "p95_ms": 0,
                "p99_ms": 0,
            }

        latencies = sorted([c["latency_ms"] for c in self._calls])
        n = len(latencies)

        return {
            "avg_ms": sum(latencies) / n,
            "min_ms": latencies[0],
            "max_ms": latencies[-1],
            "p50_ms": latencies[int(n * 0.5)],
            "p95_ms": latencies[min(int(n * 0.95), n - 1)],
            "p99_ms": latencies[min(int(n * 0.99), n - 1)],
        }

    def get_metrics_by_endpoint(self) -> dict[str, dict[str, Any]]:
        """按端点获取指标"""
        result: dict[str, dict[str, Any]] = {}

        for endpoint, calls in self._by_endpoint.items():
            latencies = [c["latency_ms"] for c in calls]
            error_count = sum(1 for c in calls if c["status_code"] >= 400)

            result[endpoint] = {
                "call_count": len(calls),
                "error_count": error_count,
                "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
            }

        return result


class WorkflowMetricsCollector:
    """工作流指标采集器

    记录工作流执行次数、时长、成功率等指标。
    """

    def __init__(self) -> None:
        self._active: dict[str, dict[str, Any]] = {}
        self._completed: list[dict[str, Any]] = []

    @property
    def total_executions(self) -> int:
        """总执行次数"""
        return len(self._completed)

    @property
    def successful_executions(self) -> int:
        """成功执行次数"""
        return sum(1 for c in self._completed if c["success"])

    @property
    def failed_executions(self) -> int:
        """失败执行次数"""
        return sum(1 for c in self._completed if not c["success"])

    @property
    def active_workflows(self) -> int:
        """活跃工作流数"""
        return len(self._active)

    @property
    def success_rate(self) -> float:
        """成功率"""
        if not self._completed:
            return 0.0
        return self.successful_executions / len(self._completed)

    @property
    def avg_duration_ms(self) -> float:
        """平均时长"""
        if not self._completed:
            return 0.0
        durations = [c["duration_ms"] for c in self._completed]
        return sum(durations) / len(durations)

    def record_start(self, workflow_id: str, workflow_name: str) -> None:
        """记录工作流开始"""
        self._active[workflow_id] = {
            "workflow_name": workflow_name,
            "start_time": datetime.now(),
        }

    def record_completion(
        self,
        workflow_id: str,
        success: bool,
        duration_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录工作流完成"""
        workflow_info = self._active.pop(workflow_id, {})

        self._completed.append(
            {
                "workflow_id": workflow_id,
                "workflow_name": workflow_info.get("workflow_name", ""),
                "success": success,
                "duration_ms": duration_ms,
                "completed_at": datetime.now(),
                "metadata": metadata or {},
            }
        )


class AgentMetricsCollector:
    """Agent 指标采集器

    记录 Agent 活动状态、请求数、响应时间等。
    """

    def __init__(self) -> None:
        self._agents: dict[str, dict[str, Any]] = {}

    @property
    def active_agents(self) -> int:
        """活跃 Agent 数"""
        return len(self._agents)

    def record_start(self, agent_id: str, agent_type: str) -> None:
        """记录 Agent 启动"""
        self._agents[agent_id] = {
            "agent_type": agent_type,
            "start_time": datetime.now(),
            "total_requests": 0,
            "error_count": 0,
            "response_times": [],
        }

    def record_stop(self, agent_id: str) -> None:
        """记录 Agent 停止"""
        self._agents.pop(agent_id, None)

    def record_request(
        self,
        agent_id: str,
        response_time_ms: float,
        success: bool,
    ) -> None:
        """记录 Agent 请求"""
        if agent_id not in self._agents:
            return

        self._agents[agent_id]["total_requests"] += 1
        self._agents[agent_id]["response_times"].append(response_time_ms)
        if not success:
            self._agents[agent_id]["error_count"] += 1

    def get_agent_stats(self, agent_id: str) -> dict[str, Any]:
        """获取 Agent 统计"""
        if agent_id not in self._agents:
            return {}

        agent = self._agents[agent_id]
        return {
            "agent_type": agent["agent_type"],
            "total_requests": agent["total_requests"],
            "error_count": agent["error_count"],
            "avg_response_time_ms": (
                sum(agent["response_times"]) / len(agent["response_times"])
                if agent["response_times"]
                else 0
            ),
        }

    def get_agents_by_type(self) -> dict[str, int]:
        """按类型获取 Agent 数量"""
        by_type: dict[str, int] = {}
        for agent in self._agents.values():
            agent_type = agent["agent_type"]
            by_type[agent_type] = by_type.get(agent_type, 0) + 1
        return by_type


# ==================== 9. 指标聚合器 ====================


@dataclass
class MetricSample:
    """指标样本"""

    value: float
    labels: dict[str, str]
    timestamp: datetime


class MetricsAggregator:
    """指标聚合器

    提供指标聚合计算功能。
    """

    def __init__(self) -> None:
        self._samples: dict[str, list[MetricSample]] = defaultdict(list)

    def add_sample(
        self,
        metric_name: str,
        value: float,
        labels: dict[str, str] | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """添加指标样本"""
        sample = MetricSample(
            value=value,
            labels=labels or {},
            timestamp=timestamp or datetime.now(),
        )
        self._samples[metric_name].append(sample)

    def sample_count(self, metric_name: str) -> int:
        """获取样本数量"""
        return len(self._samples.get(metric_name, []))

    def _filter_by_time(
        self,
        samples: list[MetricSample],
        time_window_minutes: int | None,
    ) -> list[MetricSample]:
        """按时间窗口过滤"""
        if time_window_minutes is None:
            return samples

        cutoff = datetime.now() - timedelta(minutes=time_window_minutes)
        return [s for s in samples if s.timestamp >= cutoff]

    def aggregate(
        self,
        metric_name: str,
        aggregation: str,
        time_window_minutes: int | None = None,
    ) -> float:
        """聚合计算

        参数：
            metric_name: 指标名称
            aggregation: 聚合方式 (avg, sum, min, max, count)
            time_window_minutes: 时间窗口（分钟）
        """
        samples = self._filter_by_time(
            self._samples.get(metric_name, []),
            time_window_minutes,
        )

        if not samples:
            return 0.0

        values = [s.value for s in samples]

        if aggregation == "avg":
            return sum(values) / len(values)
        elif aggregation == "sum":
            return sum(values)
        elif aggregation == "min":
            return min(values)
        elif aggregation == "max":
            return max(values)
        elif aggregation == "count":
            return len(values)
        else:
            return 0.0

    def percentile(self, metric_name: str, p: int) -> float:
        """计算百分位数"""
        samples = self._samples.get(metric_name, [])
        if not samples:
            return 0.0

        values = sorted([s.value for s in samples])
        idx = int(len(values) * p / 100)
        idx = min(idx, len(values) - 1)
        return values[idx]

    def aggregate_by_label(
        self,
        metric_name: str,
        label_key: str,
        aggregation: str,
    ) -> dict[str, float]:
        """按标签聚合"""
        samples = self._samples.get(metric_name, [])

        by_label: dict[str, list[float]] = defaultdict(list)
        for sample in samples:
            label_value = sample.labels.get(label_key, "unknown")
            by_label[label_value].append(sample.value)

        result: dict[str, float] = {}
        for label_value, values in by_label.items():
            if aggregation == "avg":
                result[label_value] = sum(values) / len(values)
            elif aggregation == "sum":
                result[label_value] = sum(values)
            elif aggregation == "min":
                result[label_value] = min(values)
            elif aggregation == "max":
                result[label_value] = max(values)
            elif aggregation == "count":
                result[label_value] = len(values)

        return result


# ==================== 10. Dashboard 数据生成器 ====================


class DashboardDataGenerator:
    """仪表盘数据生成器

    聚合各种指标生成仪表盘展示数据。
    """

    def __init__(
        self,
        system_collector: SystemMetricsCollector | None = None,
        api_collector: APIMetricsCollector | None = None,
        workflow_collector: WorkflowMetricsCollector | None = None,
        agent_collector: AgentMetricsCollector | None = None,
        log_store: InMemoryLogStore | None = None,
    ) -> None:
        self.system_collector = system_collector
        self.api_collector = api_collector
        self.workflow_collector = workflow_collector
        self.agent_collector = agent_collector
        self.log_store = log_store

    def generate_system_overview(self) -> dict[str, Any]:
        """生成系统概览"""
        result: dict[str, Any] = {}

        if self.system_collector:
            metrics = self.system_collector.collect()
            result["cpu_percent"] = metrics.get("cpu_percent", 0)
            result["memory_percent"] = metrics.get("memory_percent", 0)
            result["memory_used_mb"] = metrics.get("memory_used_mb", 0)
            result["disk_usage_percent"] = metrics.get("disk_usage_percent", 0)

        if self.agent_collector:
            result["active_agents"] = self.agent_collector.active_agents
            result["agents_by_type"] = self.agent_collector.get_agents_by_type()

        return result

    def generate_api_summary(self) -> dict[str, Any]:
        """生成 API 摘要"""
        if not self.api_collector:
            return {}

        return {
            "total_calls": self.api_collector.call_count,
            "error_count": self.api_collector.error_count,
            "error_rate": (
                self.api_collector.error_count / self.api_collector.call_count
                if self.api_collector.call_count > 0
                else 0
            ),
            "latency_stats": self.api_collector.get_latency_stats(),
            "by_endpoint": self.api_collector.get_metrics_by_endpoint(),
        }

    def generate_workflow_summary(self) -> dict[str, Any]:
        """生成工作流摘要"""
        if not self.workflow_collector:
            return {}

        return {
            "total_executions": self.workflow_collector.total_executions,
            "successful_executions": self.workflow_collector.successful_executions,
            "failed_executions": self.workflow_collector.failed_executions,
            "success_rate": self.workflow_collector.success_rate,
            "avg_duration_ms": self.workflow_collector.avg_duration_ms,
            "active_workflows": self.workflow_collector.active_workflows,
        }

    def generate_agent_summary(self) -> dict[str, Any]:
        """生成 Agent 摘要"""
        if not self.agent_collector:
            return {}

        return {
            "active_agents": self.agent_collector.active_agents,
            "by_type": self.agent_collector.get_agents_by_type(),
        }

    def generate_log_analysis(self) -> dict[str, Any]:
        """生成日志分析"""
        if not self.log_store:
            return {}

        return {
            "total_logs": self.log_store.count,
            "by_level": self.log_store.aggregate_by_level(),
            "by_source": self.log_store.aggregate_by_source(),
        }

    def generate_full_dashboard(self) -> dict[str, Any]:
        """生成完整仪表盘数据"""
        return {
            "system_overview": self.generate_system_overview(),
            "api_summary": self.generate_api_summary(),
            "workflow_summary": self.generate_workflow_summary(),
            "agent_summary": self.generate_agent_summary(),
            "log_analysis": self.generate_log_analysis(),
            "generated_at": datetime.now().isoformat(),
        }
