"""日志分析与审计能力 (Log Analysis & Audit) - Step 7

提供任务追踪、性能分析、偏好挖掘和审计报告的完整实现：

1. TraceSpan - 追踪跨度（单个操作的时间记录）
2. TaskTrace - 任务追踪（完整链路重建）
3. TraceAnalyzer - 追踪分析器（从日志重建任务链路）
4. PerformanceAnalyzer - 性能分析器（瓶颈检测、延迟分析）
5. PreferenceAnalyzer - 偏好分析器（用户行为挖掘）
6. AuditReportGenerator - 审计报告生成器

任务链路：用户输入 → 对话步骤 → 工作流节点 → 输出

用法：
    # 追踪分析
    analyzer = TraceAnalyzer(log_store=store)
    trace = analyzer.reconstruct_trace("trace_001")

    # 性能分析
    perf = PerformanceAnalyzer()
    bottlenecks = perf.find_bottlenecks(traces)

    # 偏好分析
    pref = PreferenceAnalyzer()
    preferences = pref.extract_user_preferences(traces)

    # 审计报告
    generator = AuditReportGenerator(log_store=store)
    report = generator.generate_report(start_time, end_time)
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from src.domain.services.logging_metrics import (
    InMemoryLogStore,
    LogLevel,
)

# ==================== 1. TraceSpan 追踪跨度 ====================


@dataclass
class TraceSpan:
    """追踪跨度

    表示单个操作的时间记录，用于构建完整的任务链路。

    属性：
        span_id: 跨度唯一标识
        parent_span_id: 父跨度 ID（根跨度为 None）
        operation: 操作名称
        service: 服务名称
        start_time: 开始时间
        end_time: 结束时间
        status: 状态 (success/error/pending)
        error_message: 错误消息（可选）
        metadata: 元数据
    """

    span_id: str
    parent_span_id: str | None
    operation: str
    service: str
    start_time: datetime
    end_time: datetime
    status: str = "success"
    error_message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        """计算持续时间（毫秒）"""
        delta = self.end_time - self.start_time
        return delta.total_seconds() * 1000

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation": self.operation,
            "service": self.service,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


# ==================== 2. TaskTrace 任务追踪 ====================


@dataclass
class TaskTrace:
    """任务追踪

    表示一个完整任务的执行链路。

    属性：
        trace_id: 追踪唯一标识
        user_input: 用户输入
        started_at: 开始时间
        completed_at: 完成时间（可选）
        spans: 跨度列表
        status: 状态 (pending/completed/failed)
        output: 输出结果（可选）
    """

    trace_id: str
    user_input: str
    started_at: datetime
    completed_at: datetime | None = None
    spans: list[TraceSpan] = field(default_factory=list)
    status: str = "pending"
    output: str = ""

    @property
    def total_duration_ms(self) -> float:
        """计算总时长（毫秒）"""
        if self.completed_at is None:
            return 0.0
        delta = self.completed_at - self.started_at
        return delta.total_seconds() * 1000

    def add_span(self, span: TraceSpan) -> None:
        """添加跨度"""
        self.spans.append(span)

    def complete(self, completed_at: datetime, output: str = "") -> None:
        """标记完成"""
        self.completed_at = completed_at
        self.status = "completed"
        self.output = output

    def fail(self, completed_at: datetime, error: str = "") -> None:
        """标记失败"""
        self.completed_at = completed_at
        self.status = "failed"
        self.output = error

    def build_span_tree(self) -> dict[str, Any]:
        """构建跨度树

        将扁平的跨度列表构建为树形结构。
        """
        # 创建 span_id -> span 映射
        span_map = {span.span_id: span for span in self.spans}

        # 创建 span_id -> children 映射
        children_map: dict[str, list[str]] = defaultdict(list)
        root_spans: list[str] = []

        for span in self.spans:
            if span.parent_span_id is None:
                root_spans.append(span.span_id)
            else:
                children_map[span.parent_span_id].append(span.span_id)

        def build_node(span_id: str) -> dict[str, Any]:
            span = span_map[span_id]
            return {
                "span_id": span.span_id,
                "operation": span.operation,
                "service": span.service,
                "duration_ms": span.duration_ms,
                "status": span.status,
                "children": [build_node(child_id) for child_id in children_map.get(span_id, [])],
            }

        if not root_spans:
            return {}

        # 返回第一个根节点（通常只有一个根）
        return build_node(root_spans[0])

    def get_critical_path(self) -> list[TraceSpan]:
        """获取关键路径（最长执行路径）

        返回从根到叶子的最长时间路径。
        """
        if not self.spans:
            return []

        # 按 parent_span_id 分组
        children_map: dict[str | None, list[TraceSpan]] = defaultdict(list)
        for span in self.spans:
            children_map[span.parent_span_id].append(span)

        def find_longest_path(parent_id: str | None) -> list[TraceSpan]:
            children = children_map.get(parent_id, [])
            if not children:
                return []

            longest = []
            for child in children:
                path = [child] + find_longest_path(child.span_id)
                if sum(s.duration_ms for s in path) > sum(s.duration_ms for s in longest):
                    longest = path

            return longest

        return find_longest_path(None)

    def to_timeline(self) -> list[dict[str, Any]]:
        """转换为时间线

        按开始时间排序返回所有跨度。
        """
        sorted_spans = sorted(self.spans, key=lambda s: s.start_time)
        return [span.to_dict() for span in sorted_spans]

    def get_execution_chain(self) -> list[dict[str, Any]]:
        """获取执行链

        返回按时间顺序排列的执行步骤。
        """
        chain = []
        for span in sorted(self.spans, key=lambda s: s.start_time):
            chain.append(
                {
                    "stage": span.operation if span.operation else span.service,
                    "service": span.service,
                    "operation": span.operation,
                    "duration_ms": span.duration_ms,
                    "status": span.status,
                    "metadata": span.metadata,
                }
            )
        return chain


# ==================== 3. Bottleneck 性能瓶颈 ====================


@dataclass
class Bottleneck:
    """性能瓶颈

    表示系统中的性能瓶颈点。

    属性：
        operation: 操作名称
        service: 服务名称
        avg_duration_ms: 平均耗时
        p95_duration_ms: P95 耗时
        occurrence_count: 出现次数
        suggestion: 优化建议
    """

    operation: str
    service: str
    avg_duration_ms: float
    p95_duration_ms: float
    occurrence_count: int
    suggestion: str = ""

    @property
    def severity(self) -> str:
        """计算严重程度"""
        if self.avg_duration_ms >= 5000 or self.p95_duration_ms >= 10000:
            return "critical"
        elif self.avg_duration_ms >= 2000 or self.p95_duration_ms >= 5000:
            return "high"
        elif self.avg_duration_ms >= 1000 or self.p95_duration_ms >= 2000:
            return "medium"
        else:
            return "low"

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "operation": self.operation,
            "service": self.service,
            "avg_duration_ms": self.avg_duration_ms,
            "p95_duration_ms": self.p95_duration_ms,
            "occurrence_count": self.occurrence_count,
            "severity": self.severity,
            "suggestion": self.suggestion,
        }


# ==================== 4. TraceAnalyzer 追踪分析器 ====================


class TraceAnalyzer:
    """追踪分析器

    从日志存储中重建任务追踪链路。
    """

    def __init__(self, log_store: InMemoryLogStore) -> None:
        self.log_store = log_store

    def reconstruct_trace(self, trace_id: str) -> TaskTrace | None:
        """从日志重建追踪

        参数：
            trace_id: 追踪 ID

        返回：
            TaskTrace 或 None（如果追踪不存在）
        """
        logs = self.log_store.query(trace_id=trace_id, limit=10000)

        if not logs:
            return None

        # 按时间排序
        logs = sorted(logs, key=lambda log: log.timestamp)

        # 提取用户输入
        user_input = ""
        for log in logs:
            if log.event_type in ("user_input", "request_received"):
                user_input = log.metadata.get("user_input", log.message)
                break

        # 创建 TaskTrace
        trace = TaskTrace(
            trace_id=trace_id,
            user_input=user_input,
            started_at=logs[0].timestamp,
        )

        # 跟踪 span 开始时间和结束时间
        span_starts: dict[str, datetime] = {}
        span_ends: dict[str, datetime] = {}
        span_data: dict[str, dict[str, Any]] = {}
        completed_spans: set[str] = set()

        for log in logs:
            if log.trace is None:
                continue

            span_id = log.trace.span_id
            parent_span_id = log.trace.parent_span_id

            # 记录 span 开始
            if span_id not in span_starts:
                span_starts[span_id] = log.timestamp
                span_data[span_id] = {
                    "operation": log.event_type,
                    "service": log.source,
                    "parent_span_id": parent_span_id,
                    "metadata": log.metadata.copy(),
                    "status": "success",
                }

            # 更新结束时间（每次都更新为最新的日志时间）
            span_ends[span_id] = log.timestamp

            # 合并 metadata
            if span_id in span_data:
                span_data[span_id]["metadata"].update(log.metadata)

            # 检查是否是完成事件
            if log.event_type.endswith("_completed") or log.event_type.endswith("_sent"):
                # 创建完整的 span
                start_time = span_starts.get(span_id, log.timestamp)
                data = span_data.get(span_id, {})
                metadata = data.get("metadata", {})

                # 如果 metadata 中有 duration_ms，用它计算真正的 start_time
                if "duration_ms" in metadata and start_time == log.timestamp:
                    duration_ms = metadata["duration_ms"]
                    start_time = log.timestamp - timedelta(milliseconds=duration_ms)

                span = TraceSpan(
                    span_id=span_id,
                    parent_span_id=data.get("parent_span_id"),
                    operation=data.get("operation", log.event_type),
                    service=data.get("service", log.source),
                    start_time=start_time,
                    end_time=log.timestamp,
                    status="success" if log.level != LogLevel.ERROR else "error",
                    metadata=metadata,
                )
                trace.add_span(span)
                completed_spans.add(span_id)

            # 检查错误
            if log.level == LogLevel.ERROR:
                if span_id in span_data:
                    span_data[span_id]["status"] = "error"

        # 为没有完成事件的 span 创建条目
        for span_id, start_time in span_starts.items():
            if span_id in completed_spans:
                continue  # 已经在上面处理过了

            data = span_data.get(span_id, {})
            end_time = span_ends.get(span_id, start_time)

            span = TraceSpan(
                span_id=span_id,
                parent_span_id=data.get("parent_span_id"),
                operation=data.get("operation", ""),
                service=data.get("service", ""),
                start_time=start_time,
                end_time=end_time,
                status=data.get("status", "success"),
                metadata=data.get("metadata", {}),
            )
            trace.add_span(span)

        # 设置完成时间
        if logs:
            trace.complete(logs[-1].timestamp)

        return trace

    def get_traces_in_period(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> list[TaskTrace]:
        """获取时间段内的所有追踪

        参数：
            start_time: 开始时间
            end_time: 结束时间

        返回：
            TaskTrace 列表
        """
        logs = self.log_store.query(
            start_time=start_time,
            end_time=end_time,
            limit=100000,
        )

        # 按 trace_id 分组
        trace_ids: set[str] = set()
        for log in logs:
            if log.trace:
                trace_ids.add(log.trace.trace_id)

        # 重建每个追踪
        traces = []
        for trace_id in trace_ids:
            trace = self.reconstruct_trace(trace_id)
            if trace:
                traces.append(trace)

        return traces


# ==================== 5. PerformanceAnalyzer 性能分析器 ====================


class PerformanceAnalyzer:
    """性能分析器

    分析任务执行性能，发现瓶颈。
    """

    def __init__(self, bottleneck_threshold_ms: float = 1000) -> None:
        self.bottleneck_threshold_ms = bottleneck_threshold_ms

    def find_bottlenecks(
        self,
        traces: list[TaskTrace],
        threshold_ms: float | None = None,
    ) -> list[Bottleneck]:
        """发现性能瓶颈

        参数：
            traces: 任务追踪列表
            threshold_ms: 瓶颈阈值（毫秒）

        返回：
            Bottleneck 列表
        """
        threshold = threshold_ms or self.bottleneck_threshold_ms

        # 按操作+服务聚合
        op_stats: dict[tuple[str, str], list[float]] = defaultdict(list)

        for trace in traces:
            for span in trace.spans:
                key = (span.operation, span.service)
                op_stats[key].append(span.duration_ms)

        # 识别瓶颈
        bottlenecks = []
        for (operation, service), durations in op_stats.items():
            if not durations:
                continue

            avg = sum(durations) / len(durations)
            sorted_durations = sorted(durations)
            p95_idx = int(len(sorted_durations) * 0.95)
            p95 = sorted_durations[min(p95_idx, len(sorted_durations) - 1)]

            if avg >= threshold or p95 >= threshold * 1.5:
                suggestion = self._generate_suggestion(operation, service, avg, p95)
                bottlenecks.append(
                    Bottleneck(
                        operation=operation,
                        service=service,
                        avg_duration_ms=avg,
                        p95_duration_ms=p95,
                        occurrence_count=len(durations),
                        suggestion=suggestion,
                    )
                )

        # 按平均耗时降序排序
        bottlenecks.sort(key=lambda b: b.avg_duration_ms, reverse=True)
        return bottlenecks

    def _generate_suggestion(
        self,
        operation: str,
        service: str,
        avg_ms: float,
        p95_ms: float,
    ) -> str:
        """生成优化建议"""
        suggestions = []

        if "database" in service.lower() or "query" in operation.lower():
            suggestions.append("考虑添加数据库索引或优化查询语句")
        if "llm" in service.lower() or "llm" in operation.lower():
            suggestions.append("考虑使用更快的模型或减少 token 数量")
        if "http" in service.lower() or "api" in operation.lower():
            suggestions.append("考虑添加缓存或使用连接池")

        if p95_ms > avg_ms * 2:
            suggestions.append("存在长尾延迟，建议设置超时和重试机制")

        if avg_ms > 3000:
            suggestions.append("平均延迟过高，建议异步处理或任务拆分")

        return "; ".join(suggestions) if suggestions else "建议进行详细性能分析"

    def analyze_latency_distribution(
        self,
        traces: list[TaskTrace],
    ) -> dict[str, float]:
        """分析延迟分布

        参数：
            traces: 任务追踪列表

        返回：
            延迟分布统计
        """
        durations = [trace.total_duration_ms for trace in traces if trace.total_duration_ms > 0]

        if not durations:
            return {
                "avg": 0,
                "min": 0,
                "max": 0,
                "p50": 0,
                "p95": 0,
                "p99": 0,
            }

        sorted_durations = sorted(durations)
        n = len(sorted_durations)

        return {
            "avg": sum(durations) / n,
            "min": sorted_durations[0],
            "max": sorted_durations[-1],
            "p50": sorted_durations[int(n * 0.5)],
            "p95": sorted_durations[min(int(n * 0.95), n - 1)],
            "p99": sorted_durations[min(int(n * 0.99), n - 1)],
        }

    def identify_slow_services(
        self,
        traces: list[TaskTrace],
        threshold_ms: float = 1000,
    ) -> dict[str, dict[str, Any]]:
        """识别慢服务

        参数：
            traces: 任务追踪列表
            threshold_ms: 阈值（毫秒）

        返回：
            慢服务字典
        """
        service_stats: dict[str, list[float]] = defaultdict(list)

        for trace in traces:
            for span in trace.spans:
                service_stats[span.service].append(span.duration_ms)

        slow_services = {}
        for service, durations in service_stats.items():
            avg = sum(durations) / len(durations)
            if avg >= threshold_ms:
                slow_services[service] = {
                    "avg_duration_ms": avg,
                    "call_count": len(durations),
                    "total_time_ms": sum(durations),
                }

        return slow_services

    def generate_performance_report(
        self,
        traces: list[TaskTrace],
    ) -> dict[str, Any]:
        """生成性能报告

        参数：
            traces: 任务追踪列表

        返回：
            性能报告字典
        """
        bottlenecks = self.find_bottlenecks(traces)
        latency_dist = self.analyze_latency_distribution(traces)
        slow_services = self.identify_slow_services(traces)

        # 生成建议
        recommendations = []
        for bottleneck in bottlenecks[:5]:  # 取前5个瓶颈
            if bottleneck.suggestion:
                recommendations.append(
                    f"[{bottleneck.service}] {bottleneck.operation}: {bottleneck.suggestion}"
                )

        return {
            "summary": {
                "total_traces": len(traces),
                "avg_duration_ms": latency_dist["avg"],
                "p95_duration_ms": latency_dist["p95"],
                "bottleneck_count": len(bottlenecks),
            },
            "bottlenecks": [b.to_dict() for b in bottlenecks],
            "latency_distribution": latency_dist,
            "slow_services": slow_services,
            "recommendations": recommendations,
        }


# ==================== 6. PreferenceAnalyzer 偏好分析器 ====================


class PreferenceAnalyzer:
    """偏好分析器

    分析用户行为偏好。
    """

    def analyze_intent_distribution(
        self,
        traces: list[TaskTrace],
    ) -> dict[str, dict[str, Any]]:
        """分析意图分布

        参数：
            traces: 任务追踪列表

        返回：
            意图分布字典
        """
        intent_counts: dict[str, int] = defaultdict(int)

        for trace in traces:
            for span in trace.spans:
                if "intent" in span.metadata:
                    intent_counts[span.metadata["intent"]] += 1

        total = sum(intent_counts.values()) or 1

        result = {}
        for intent, count in intent_counts.items():
            result[intent] = {
                "count": count,
                "percentage": count / total,
            }

        return result

    def analyze_workflow_usage(
        self,
        traces: list[TaskTrace],
    ) -> dict[str, dict[str, Any]]:
        """分析工作流使用情况

        参数：
            traces: 任务追踪列表

        返回：
            工作流使用统计
        """
        workflow_counts: dict[str, int] = defaultdict(int)

        for trace in traces:
            for span in trace.spans:
                if "workflow_name" in span.metadata:
                    workflow_counts[span.metadata["workflow_name"]] += 1

        # 按使用次数排序
        sorted_workflows = sorted(workflow_counts.items(), key=lambda x: x[1], reverse=True)

        result = {}
        for rank, (workflow, count) in enumerate(sorted_workflows, 1):
            result[workflow] = {
                "count": count,
                "rank": rank,
            }

        return result

    def analyze_time_patterns(
        self,
        traces: list[TaskTrace],
    ) -> dict[str, Any]:
        """分析时间模式

        参数：
            traces: 任务追踪列表

        返回：
            时间模式分析
        """
        hour_counts: dict[int, int] = defaultdict(int)

        for trace in traces:
            hour = trace.started_at.hour
            hour_counts[hour] += 1

        # 找出高峰时段（超过平均值的时段）
        if hour_counts:
            avg = sum(hour_counts.values()) / len(hour_counts)
            peak_hours = [hour for hour, count in hour_counts.items() if count > avg]
        else:
            peak_hours = []

        return {
            "by_hour": dict(hour_counts),
            "peak_hours": peak_hours,
            "total_tasks": sum(hour_counts.values()),
        }

    def extract_user_preferences(
        self,
        traces: list[TaskTrace],
    ) -> dict[str, Any]:
        """提取用户偏好

        参数：
            traces: 任务追踪列表

        返回：
            用户偏好字典
        """
        # 收集各类偏好数据
        models: dict[str, int] = defaultdict(int)
        formats: dict[str, int] = defaultdict(int)
        features: dict[str, int] = defaultdict(int)

        for trace in traces:
            for span in trace.spans:
                meta = span.metadata

                if "model" in meta:
                    models[meta["model"]] += 1

                if "format" in meta:
                    formats[meta["format"]] += 1
                if "output_format" in meta:
                    formats[meta["output_format"]] += 1

                if "intent" in meta:
                    features[meta["intent"]] += 1

        # 找出最常用的
        def get_top(counts: dict[str, int]) -> str | None:
            if not counts:
                return None
            return max(counts.items(), key=lambda x: x[1])[0]

        return {
            "preferred_model": get_top(models),
            "preferred_format": get_top(formats),
            "top_features": dict(sorted(features.items(), key=lambda x: x[1], reverse=True)[:5]),
            "model_usage": dict(models),
            "format_usage": dict(formats),
        }

    def generate_preference_report(
        self,
        traces: list[TaskTrace],
    ) -> dict[str, Any]:
        """生成偏好报告

        参数：
            traces: 任务追踪列表

        返回：
            偏好报告字典
        """
        return {
            "intent_distribution": self.analyze_intent_distribution(traces),
            "workflow_usage": self.analyze_workflow_usage(traces),
            "time_patterns": self.analyze_time_patterns(traces),
            "user_preferences": self.extract_user_preferences(traces),
        }


# ==================== 7. AuditReportGenerator 审计报告生成器 ====================


class AuditReportGenerator:
    """审计报告生成器

    生成完整的审计报告。
    """

    def __init__(self, log_store: InMemoryLogStore) -> None:
        self.log_store = log_store
        self.trace_analyzer = TraceAnalyzer(log_store)
        self.perf_analyzer = PerformanceAnalyzer()
        self.pref_analyzer = PreferenceAnalyzer()

    def generate_report(
        self,
        start_time: datetime,
        end_time: datetime,
        title: str = "审计报告",
    ) -> dict[str, Any]:
        """生成审计报告

        参数：
            start_time: 开始时间
            end_time: 结束时间
            title: 报告标题

        返回：
            审计报告字典
        """
        # 获取所有追踪
        traces = self.trace_analyzer.get_traces_in_period(start_time, end_time)

        # 性能分析
        perf_report = self.perf_analyzer.generate_performance_report(traces)

        # 偏好分析
        pref_report = self.pref_analyzer.generate_preference_report(traces)

        # 汇总统计
        summary = {
            "title": title,
            "total_traces": len(traces),
            "total_logs": self.log_store.count,
            "period_start": start_time.isoformat(),
            "period_end": end_time.isoformat(),
            "success_count": sum(1 for t in traces if t.status == "completed"),
            "error_count": sum(1 for t in traces if t.status == "failed"),
        }

        return {
            "report_id": str(uuid.uuid4())[:8],
            "generated_at": datetime.now().isoformat(),
            "period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            "summary": summary,
            "traces": [
                {
                    "trace_id": t.trace_id,
                    "user_input": t.user_input,
                    "status": t.status,
                    "duration_ms": t.total_duration_ms,
                    "span_count": len(t.spans),
                }
                for t in traces[:100]  # 限制100条
            ],
            "performance_analysis": perf_report,
            "preference_analysis": pref_report,
        }

    def export_to_json(self, report: dict[str, Any]) -> str:
        """导出为 JSON

        参数：
            report: 报告字典

        返回：
            JSON 字符串
        """
        return json.dumps(report, ensure_ascii=False, indent=2, default=str)

    def export_to_markdown(self, report: dict[str, Any]) -> str:
        """导出为 Markdown

        参数：
            report: 报告字典

        返回：
            Markdown 字符串
        """
        lines = []

        # 标题
        lines.append("# 审计报告")
        lines.append("")
        lines.append(f"**报告 ID:** {report.get('report_id', 'N/A')}")
        lines.append(f"**生成时间:** {report.get('generated_at', 'N/A')}")
        lines.append("")

        # 概要
        summary = report.get("summary", {})
        lines.append("## 概要")
        lines.append("")
        lines.append(
            f"- **统计周期:** {summary.get('period_start', '')} ~ {summary.get('period_end', '')}"
        )
        lines.append(f"- **总任务数:** {summary.get('total_traces', 0)}")
        lines.append(f"- **成功数:** {summary.get('success_count', 0)}")
        lines.append(f"- **失败数:** {summary.get('error_count', 0)}")
        lines.append("")

        # 性能分析
        lines.append("## 性能分析")
        lines.append("")

        perf = report.get("performance_analysis", {})
        perf_summary = perf.get("summary", {})
        lines.append(f"- **平均延迟:** {perf_summary.get('avg_duration_ms', 0):.2f} ms")
        lines.append(f"- **P95 延迟:** {perf_summary.get('p95_duration_ms', 0):.2f} ms")
        lines.append(f"- **瓶颈数量:** {perf_summary.get('bottleneck_count', 0)}")
        lines.append("")

        # 瓶颈列表
        bottlenecks = perf.get("bottlenecks", [])
        if bottlenecks:
            lines.append("### 性能瓶颈")
            lines.append("")
            lines.append("| 服务 | 操作 | 平均耗时 | P95 耗时 | 严重程度 |")
            lines.append("|------|------|----------|----------|----------|")
            for b in bottlenecks[:10]:
                lines.append(
                    f"| {b.get('service', '')} | {b.get('operation', '')} | "
                    f"{b.get('avg_duration_ms', 0):.0f}ms | "
                    f"{b.get('p95_duration_ms', 0):.0f}ms | "
                    f"{b.get('severity', '')} |"
                )
            lines.append("")

        # 优化建议
        recommendations = perf.get("recommendations", [])
        if recommendations:
            lines.append("### 优化建议")
            lines.append("")
            for rec in recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        # 偏好分析
        lines.append("## 偏好分析")
        lines.append("")

        pref = report.get("preference_analysis", {})

        # 意图分布
        intent_dist = pref.get("intent_distribution", {})
        if intent_dist:
            lines.append("### 意图分布")
            lines.append("")
            for intent, data in list(intent_dist.items())[:10]:
                pct = data.get("percentage", 0) * 100
                lines.append(f"- **{intent}:** {data.get('count', 0)} 次 ({pct:.1f}%)")
            lines.append("")

        # 工作流使用
        workflow_usage = pref.get("workflow_usage", {})
        if workflow_usage:
            lines.append("### 工作流使用")
            lines.append("")
            for wf, data in list(workflow_usage.items())[:10]:
                lines.append(
                    f"- **{wf}:** {data.get('count', 0)} 次 (排名 #{data.get('rank', '-')})"
                )
            lines.append("")

        # 分隔线
        lines.append("---")
        lines.append("")
        lines.append("*报告由系统自动生成*")

        return "\n".join(lines)
