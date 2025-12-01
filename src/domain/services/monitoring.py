"""监控系统（Monitoring System）

Phase 4.2: 监控

组件：
- MetricsCollector: 指标收集器
- Tracer: 链路追踪
- HealthChecker: 健康检查
- AlertManager: 告警管理
- MonitoringFactory: 工厂类

功能：
- 计数器/仪表盘/直方图指标
- 分布式链路追踪
- 组件健康检查
- 告警规则和通知

设计原则：
- 低开销：异步收集，不阻塞业务
- 可扩展：支持自定义指标和检查
- 可观测：完整的系统可见性

"""

import asyncio
import logging
import time
import uuid
from collections import defaultdict
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# ============ 指标收集器 ============


class MetricsCollector:
    """指标收集器

    收集计数器、仪表盘和直方图指标。

    使用示例：
        collector = MetricsCollector()
        collector.increment("api_calls", labels={"endpoint": "/workflows"})
    """

    def __init__(self):
        """初始化"""
        self._counters: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._gauges: dict[str, float] = defaultdict(float)
        self._histograms: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        self._time_series: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def increment(
        self,
        name: str,
        value: int = 1,
        labels: dict[str, str] | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """增加计数器

        参数：
            name: 指标名称
            value: 增量（默认1）
            labels: 标签字典
            timestamp: 可选的时间戳
        """
        label_key = self._format_labels(labels)
        self._counters[name][label_key] += value

        if timestamp:
            self._time_series[name].append(
                {"timestamp": timestamp, "value": value, "labels": labels}
            )

    def set_gauge(self, name: str, value: float) -> None:
        """设置仪表盘值

        参数：
            name: 指标名称
            value: 值
        """
        self._gauges[name] = value

    def inc_gauge(self, name: str, delta: float = 1.0) -> None:
        """增加仪表盘值

        参数：
            name: 指标名称
            delta: 增量
        """
        self._gauges[name] += delta

    def dec_gauge(self, name: str, delta: float = 1.0) -> None:
        """减少仪表盘值

        参数：
            name: 指标名称
            delta: 减量
        """
        self._gauges[name] -= delta

    def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """记录直方图观察值

        参数：
            name: 指标名称
            value: 观察值
            labels: 标签字典
        """
        label_key = self._format_labels(labels)
        self._histograms[name][label_key].append(value)

    def get_metrics(self) -> dict[str, Any]:
        """获取所有指标

        返回：
            指标字典
        """
        result = {}

        # 计数器
        for name, labels_dict in self._counters.items():
            result[name] = dict(labels_dict)

        # 仪表盘
        for name, value in self._gauges.items():
            result[name] = value

        return result

    def get_histogram(self, name: str) -> dict[str, Any]:
        """获取直方图统计

        参数：
            name: 指标名称

        返回：
            直方图统计信息
        """
        all_values = []
        for values in self._histograms.get(name, {}).values():
            all_values.extend(values)

        if not all_values:
            return {"count": 0, "sum": 0, "p50": None, "p95": None}

        sorted_values = sorted(all_values)
        count = len(sorted_values)

        return {
            "count": count,
            "sum": sum(all_values),
            "p50": sorted_values[int(count * 0.5)] if count > 0 else None,
            "p95": sorted_values[int(count * 0.95)] if count > 0 else None,
            "min": min(sorted_values),
            "max": max(sorted_values),
        }

    def get_time_series(self, name: str, since: datetime | None = None) -> list[dict[str, Any]]:
        """获取时间序列数据

        参数：
            name: 指标名称
            since: 起始时间

        返回：
            时间序列数据列表
        """
        series = self._time_series.get(name, [])
        if since:
            series = [s for s in series if s["timestamp"] >= since]
        return series

    def _format_labels(self, labels: dict[str, str] | None) -> str:
        """格式化标签为字符串键"""
        if not labels:
            return ""
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))


# ============ 链路追踪 ============


@dataclass
class Span:
    """追踪span"""

    span_id: str
    trace_id: str
    name: str
    parent_id: str | None = None
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration(self) -> float:
        """获取持续时间（秒）"""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    def set_attribute(self, key: str, value: Any) -> None:
        """设置属性"""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """添加事件"""
        self.events.append({"name": name, "timestamp": time.time(), "attributes": attributes or {}})

    def record_exception(self, exception: Exception) -> None:
        """记录异常"""
        self.events.append(
            {
                "name": "exception",
                "timestamp": time.time(),
                "attributes": {
                    "exception.type": type(exception).__name__,
                    "exception.message": str(exception),
                },
            }
        )

    def end(self) -> None:
        """结束span"""
        self.end_time = time.time()


class Tracer:
    """链路追踪器

    创建和管理追踪span。

    使用示例：
        tracer = Tracer()
        async with tracer.span("operation") as span:
            span.set_attribute("key", "value")
    """

    def __init__(self):
        """初始化"""
        self._spans: dict[str, Span] = {}

    @asynccontextmanager
    async def span(
        self, name: str, parent: Span | None = None, attributes: dict[str, Any] | None = None
    ):
        """创建span上下文管理器

        参数：
            name: span名称
            parent: 父span
            attributes: 初始属性
        """
        # 确定trace_id
        if parent:
            trace_id = parent.trace_id
            parent_id = parent.span_id
        else:
            trace_id = str(uuid.uuid4())
            parent_id = None

        span = Span(
            span_id=str(uuid.uuid4()),
            trace_id=trace_id,
            name=name,
            parent_id=parent_id,
            attributes=attributes or {},
        )

        self._spans[span.span_id] = span

        try:
            yield span
        finally:
            span.end()

    def get_propagation_context(self, span: Span) -> dict[str, str]:
        """获取传播上下文

        参数：
            span: 当前span

        返回：
            可传播的上下文字典
        """
        return {"trace_id": span.trace_id, "span_id": span.span_id}

    def restore_context(self, context: dict[str, str]) -> Span:
        """从上下文恢复span引用

        参数：
            context: 传播上下文

        返回：
            恢复的span（用作父span）
        """
        # 创建一个虚拟span用于传递trace_id
        return Span(span_id=context["span_id"], trace_id=context["trace_id"], name="restored")


# ============ 健康检查 ============


class HealthStatus(Enum):
    """健康状态"""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


@dataclass
class HealthResult:
    """健康检查结果"""

    overall_status: HealthStatus
    components: dict[str, dict[str, Any]]


class HealthChecker:
    """健康检查器

    检查系统组件的健康状态。

    使用示例：
        checker = HealthChecker()
        checker.register("database", check_database)
        result = await checker.check_all()
    """

    def __init__(self, timeout: float = 10.0):
        """初始化

        参数：
            timeout: 检查超时时间（秒）
        """
        self.timeout = timeout
        self._checks: dict[str, Callable] = {}
        self._liveness_checks: dict[str, Callable] = {}
        self._readiness_checks: dict[str, Callable] = {}

    def register(self, name: str, check_fn: Callable) -> None:
        """注册健康检查

        参数：
            name: 组件名称
            check_fn: 检查函数（返回dict）
        """
        self._checks[name] = check_fn

    def register_liveness(self, name: str, check_fn: Callable) -> None:
        """注册存活检查"""
        self._liveness_checks[name] = check_fn

    def register_readiness(self, name: str, check_fn: Callable) -> None:
        """注册就绪检查"""
        self._readiness_checks[name] = check_fn

    async def check_all(self) -> HealthResult:
        """执行所有健康检查

        返回：
            健康检查结果
        """
        components = {}
        has_unhealthy = False

        for name, check_fn in self._checks.items():
            try:
                result = await asyncio.wait_for(self._run_check(check_fn), timeout=self.timeout)
                components[name] = result
                if result.get("status") != "healthy":
                    has_unhealthy = True
            except TimeoutError:
                components[name] = {"status": "timeout"}
                has_unhealthy = True
            except Exception as e:
                components[name] = {"status": "error", "error": str(e)}
                has_unhealthy = True

        return HealthResult(
            overall_status=HealthStatus.UNHEALTHY if has_unhealthy else HealthStatus.HEALTHY,
            components=components,
        )

    async def check_liveness(self) -> HealthResult:
        """执行存活检查"""
        return await self._run_checks(self._liveness_checks)

    async def check_readiness(self) -> HealthResult:
        """执行就绪检查"""
        return await self._run_checks(self._readiness_checks)

    async def _run_checks(self, checks: dict[str, Callable]) -> HealthResult:
        """运行一组检查"""
        components = {}
        has_unhealthy = False

        for name, check_fn in checks.items():
            try:
                if asyncio.iscoroutinefunction(check_fn):
                    result = await check_fn()
                else:
                    result = check_fn()
                components[name] = result
                if result.get("status") != "healthy":
                    has_unhealthy = True
            except Exception as e:
                components[name] = {"status": "error", "error": str(e)}
                has_unhealthy = True

        return HealthResult(
            overall_status=HealthStatus.UNHEALTHY if has_unhealthy else HealthStatus.HEALTHY,
            components=components,
        )

    async def _run_check(self, check_fn: Callable) -> dict[str, Any]:
        """运行单个检查"""
        if asyncio.iscoroutinefunction(check_fn):
            return await check_fn()
        return check_fn()


# ============ 告警管理 ============


class AlertSeverity(Enum):
    """告警级别"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    """告警"""

    name: str
    severity: AlertSeverity
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class AlertRule:
    """告警规则"""

    name: str
    condition: Callable[[dict[str, Any]], bool]
    severity: AlertSeverity
    message: str = ""


class NotificationChannel(Protocol):
    """通知渠道协议"""

    async def send(self, alert: Alert) -> None:
        """发送告警"""
        ...


class AlertManager:
    """告警管理器

    管理告警规则和发送通知。

    使用示例：
        manager = AlertManager()
        manager.add_rule("high_error", condition, AlertSeverity.CRITICAL)
        alerts = await manager.evaluate(metrics)
    """

    def __init__(self, silence_duration: int = 300):
        """初始化

        参数：
            silence_duration: 告警静默期（秒）
        """
        self.silence_duration = silence_duration
        self._rules: list[AlertRule] = []
        self._channels: list[NotificationChannel] = []
        self._fired_alerts: dict[str, datetime] = {}

    def add_rule(
        self,
        name: str,
        condition: Callable[[dict[str, Any]], bool],
        severity: AlertSeverity,
        message: str = "",
    ) -> None:
        """添加告警规则

        参数：
            name: 规则名称
            condition: 条件函数
            severity: 告警级别
            message: 告警消息
        """
        self._rules.append(
            AlertRule(name=name, condition=condition, severity=severity, message=message)
        )

    def add_notification_channel(self, channel: NotificationChannel) -> None:
        """添加通知渠道"""
        self._channels.append(channel)

    async def evaluate(self, metrics: dict[str, Any]) -> list[Alert]:
        """评估所有规则

        参数：
            metrics: 当前指标

        返回：
            触发的告警列表
        """
        alerts = []

        for rule in self._rules:
            try:
                if rule.condition(metrics):
                    # 检查是否在静默期内
                    if self._is_silenced(rule.name):
                        continue

                    alert = Alert(
                        name=rule.name,
                        severity=rule.severity,
                        message=rule.message or f"Alert: {rule.name}",
                    )

                    alerts.append(alert)
                    self._fired_alerts[rule.name] = datetime.now()

                    # 发送通知
                    await self._notify(alert)

            except Exception as e:
                logger.error(f"告警规则评估失败 {rule.name}: {e}")

        return alerts

    def _is_silenced(self, rule_name: str) -> bool:
        """检查是否在静默期内"""
        if rule_name not in self._fired_alerts:
            return False

        last_fired = self._fired_alerts[rule_name]
        silence_until = last_fired + timedelta(seconds=self.silence_duration)
        return datetime.now() < silence_until

    async def _notify(self, alert: Alert) -> None:
        """发送通知"""
        for channel in self._channels:
            try:
                await channel.send(alert)
            except Exception as e:
                logger.error(f"发送通知失败: {e}")


# ============ 工厂类 ============


@dataclass
class MonitoringSuite:
    """监控套件"""

    metrics: MetricsCollector
    tracer: Tracer
    health_checker: HealthChecker
    alert_manager: AlertManager


class MonitoringFactory:
    """监控工厂

    创建监控套件。

    使用示例：
        suite = MonitoringFactory.create(config)
    """

    @staticmethod
    def create(config: dict[str, Any] | None = None) -> MonitoringSuite:
        """创建监控套件

        参数：
            config: 可选配置
                - health_check_timeout: 健康检查超时
                - alert_silence_duration: 告警静默期
                - enable_tracing: 是否启用追踪

        返回：
            监控套件
        """
        config = config or {}

        health_check_timeout = config.get("health_check_timeout", 10.0)
        alert_silence_duration = config.get("alert_silence_duration", 300)

        return MonitoringSuite(
            metrics=MetricsCollector(),
            tracer=Tracer(),
            health_checker=HealthChecker(timeout=health_check_timeout),
            alert_manager=AlertManager(silence_duration=alert_silence_duration),
        )


# 导出
__all__ = [
    "MetricsCollector",
    "Tracer",
    "Span",
    "HealthChecker",
    "HealthStatus",
    "HealthResult",
    "AlertManager",
    "AlertSeverity",
    "Alert",
    "AlertRule",
    "NotificationChannel",
    "MonitoringSuite",
    "MonitoringFactory",
]
