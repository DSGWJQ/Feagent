"""日志分析与审计能力测试 (TDD - Step 7)

测试内容：
1. TraceSpan - 追踪跨度（单个操作）
2. TaskTrace - 任务追踪（完整链路重建）
3. TraceAnalyzer - 追踪分析器（从日志重建链路）
4. PerformanceAnalyzer - 性能分析器（瓶颈检测）
5. PreferenceAnalyzer - 偏好分析器（用户行为挖掘）
6. AuditReportGenerator - 审计报告生成器

完成标准：
- 集成测试展示一条任务日志被完整解析
- 文档新增"日志追踪与分析"小节
- 提供脚本或 API 生成报告
"""

import json
from datetime import datetime, timedelta

# ==================== 1. TraceSpan 测试 ====================


class TestTraceSpan:
    """追踪跨度测试"""

    def test_create_trace_span(self):
        """测试：创建追踪跨度"""
        from src.domain.services.log_analysis import TraceSpan

        span = TraceSpan(
            span_id="span_001",
            parent_span_id=None,
            operation="user_input",
            service="conversation_agent",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(milliseconds=100),
        )

        assert span.span_id == "span_001"
        assert span.parent_span_id is None
        assert span.operation == "user_input"
        assert span.service == "conversation_agent"
        assert span.duration_ms >= 0

    def test_span_with_parent(self):
        """测试：带父跨度的跨度"""
        from src.domain.services.log_analysis import TraceSpan

        span = TraceSpan(
            span_id="span_002",
            parent_span_id="span_001",
            operation="llm_call",
            service="workflow_agent",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(milliseconds=500),
        )

        assert span.parent_span_id == "span_001"
        assert span.duration_ms >= 500

    def test_span_with_metadata(self):
        """测试：带元数据的跨度"""
        from src.domain.services.log_analysis import TraceSpan

        span = TraceSpan(
            span_id="span_003",
            parent_span_id="span_001",
            operation="http_request",
            service="http_tool",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(milliseconds=200),
            status="success",
            metadata={"url": "https://api.example.com", "status_code": 200},
        )

        assert span.status == "success"
        assert span.metadata["url"] == "https://api.example.com"
        assert span.metadata["status_code"] == 200

    def test_span_error_status(self):
        """测试：错误状态的跨度"""
        from src.domain.services.log_analysis import TraceSpan

        span = TraceSpan(
            span_id="span_004",
            parent_span_id="span_001",
            operation="database_query",
            service="database_tool",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(milliseconds=50),
            status="error",
            error_message="Connection timeout",
        )

        assert span.status == "error"
        assert span.error_message == "Connection timeout"

    def test_span_to_dict(self):
        """测试：跨度转字典"""
        from src.domain.services.log_analysis import TraceSpan

        start = datetime.now()
        end = start + timedelta(milliseconds=100)

        span = TraceSpan(
            span_id="span_005",
            parent_span_id=None,
            operation="test_op",
            service="test_service",
            start_time=start,
            end_time=end,
        )

        data = span.to_dict()

        assert data["span_id"] == "span_005"
        assert data["operation"] == "test_op"
        assert "duration_ms" in data


# ==================== 2. TaskTrace 测试 ====================


class TestTaskTrace:
    """任务追踪测试"""

    def test_create_task_trace(self):
        """测试：创建任务追踪"""
        from src.domain.services.log_analysis import TaskTrace

        trace = TaskTrace(
            trace_id="trace_001",
            user_input="分析销售数据",
            started_at=datetime.now(),
        )

        assert trace.trace_id == "trace_001"
        assert trace.user_input == "分析销售数据"
        assert trace.spans == []
        assert trace.status == "pending"

    def test_add_span_to_trace(self):
        """测试：添加跨度到追踪"""
        from src.domain.services.log_analysis import TaskTrace, TraceSpan

        trace = TaskTrace(
            trace_id="trace_001",
            user_input="查询天气",
            started_at=datetime.now(),
        )

        span = TraceSpan(
            span_id="span_001",
            parent_span_id=None,
            operation="intent_classification",
            service="conversation_agent",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(milliseconds=50),
        )

        trace.add_span(span)

        assert len(trace.spans) == 1
        assert trace.spans[0].span_id == "span_001"

    def test_trace_build_span_tree(self):
        """测试：构建跨度树"""
        from src.domain.services.log_analysis import TaskTrace, TraceSpan

        trace = TaskTrace(
            trace_id="trace_001",
            user_input="复杂任务",
            started_at=datetime.now(),
        )

        # 根跨度
        root = TraceSpan(
            span_id="root",
            parent_span_id=None,
            operation="process_request",
            service="conversation_agent",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(milliseconds=1000),
        )

        # 子跨度
        child1 = TraceSpan(
            span_id="child1",
            parent_span_id="root",
            operation="workflow_execution",
            service="workflow_agent",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(milliseconds=800),
        )

        child2 = TraceSpan(
            span_id="child2",
            parent_span_id="root",
            operation="result_formatting",
            service="conversation_agent",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(milliseconds=100),
        )

        # 孙跨度
        grandchild = TraceSpan(
            span_id="grandchild",
            parent_span_id="child1",
            operation="llm_call",
            service="llm_executor",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(milliseconds=600),
        )

        trace.add_span(root)
        trace.add_span(child1)
        trace.add_span(child2)
        trace.add_span(grandchild)

        tree = trace.build_span_tree()

        assert tree["span_id"] == "root"
        assert len(tree["children"]) == 2

    def test_trace_total_duration(self):
        """测试：计算总时长"""
        from src.domain.services.log_analysis import TaskTrace, TraceSpan

        start = datetime.now()
        trace = TaskTrace(
            trace_id="trace_001",
            user_input="测试",
            started_at=start,
        )

        trace.add_span(
            TraceSpan(
                span_id="span_001",
                parent_span_id=None,
                operation="op1",
                service="svc1",
                start_time=start,
                end_time=start + timedelta(milliseconds=500),
            )
        )

        trace.complete(start + timedelta(milliseconds=500))

        assert trace.total_duration_ms >= 500
        assert trace.status == "completed"

    def test_trace_get_critical_path(self):
        """测试：获取关键路径（最长执行路径）"""
        from src.domain.services.log_analysis import TaskTrace, TraceSpan

        trace = TaskTrace(
            trace_id="trace_001",
            user_input="测试关键路径",
            started_at=datetime.now(),
        )

        start = datetime.now()

        # 添加多个跨度，模拟不同执行时长
        trace.add_span(
            TraceSpan(
                span_id="root",
                parent_span_id=None,
                operation="root_op",
                service="svc",
                start_time=start,
                end_time=start + timedelta(milliseconds=100),
            )
        )

        trace.add_span(
            TraceSpan(
                span_id="fast_path",
                parent_span_id="root",
                operation="fast_op",
                service="svc",
                start_time=start,
                end_time=start + timedelta(milliseconds=50),
            )
        )

        trace.add_span(
            TraceSpan(
                span_id="slow_path",
                parent_span_id="root",
                operation="slow_op",
                service="svc",
                start_time=start,
                end_time=start + timedelta(milliseconds=800),
            )
        )

        critical_path = trace.get_critical_path()

        # 关键路径应该包含最慢的操作
        assert any(span.span_id == "slow_path" for span in critical_path)

    def test_trace_to_timeline(self):
        """测试：转换为时间线"""
        from src.domain.services.log_analysis import TaskTrace, TraceSpan

        start = datetime.now()
        trace = TaskTrace(
            trace_id="trace_001",
            user_input="时间线测试",
            started_at=start,
        )

        trace.add_span(
            TraceSpan(
                span_id="s1",
                parent_span_id=None,
                operation="op1",
                service="svc1",
                start_time=start,
                end_time=start + timedelta(milliseconds=100),
            )
        )

        trace.add_span(
            TraceSpan(
                span_id="s2",
                parent_span_id=None,
                operation="op2",
                service="svc2",
                start_time=start + timedelta(milliseconds=100),
                end_time=start + timedelta(milliseconds=300),
            )
        )

        timeline = trace.to_timeline()

        # 时间线应该按开始时间排序
        assert len(timeline) == 2
        assert timeline[0]["span_id"] == "s1"
        assert timeline[1]["span_id"] == "s2"


# ==================== 3. TraceAnalyzer 测试 ====================


class TestTraceAnalyzer:
    """追踪分析器测试"""

    def test_analyzer_initialization(self):
        """测试：分析器初始化"""
        from src.domain.services.log_analysis import TraceAnalyzer
        from src.domain.services.logging_metrics import InMemoryLogStore

        store = InMemoryLogStore()
        analyzer = TraceAnalyzer(log_store=store)

        assert analyzer.log_store == store

    def test_reconstruct_trace_from_logs(self):
        """测试：从日志重建追踪"""
        from src.domain.services.log_analysis import TraceAnalyzer
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
            TraceContext,
        )

        store = InMemoryLogStore()

        # 模拟一个完整的任务日志链
        trace_id = "trace_abc123"

        # 1. 用户输入
        store.write(
            StructuredLog(
                level=LogLevel.INFO,
                source="conversation_agent",
                message="收到用户输入: 分析销售数据",
                event_type="user_input",
                trace=TraceContext(trace_id=trace_id, span_id="span_001"),
                metadata={"user_input": "分析销售数据"},
            )
        )

        # 2. 意图分类
        store.write(
            StructuredLog(
                level=LogLevel.INFO,
                source="conversation_agent",
                message="意图分类: complex_task",
                event_type="intent_classified",
                trace=TraceContext(
                    trace_id=trace_id, span_id="span_002", parent_span_id="span_001"
                ),
                metadata={"intent": "complex_task", "confidence": 0.95},
            )
        )

        # 3. 工作流执行
        store.write(
            StructuredLog(
                level=LogLevel.INFO,
                source="workflow_agent",
                message="开始执行工作流",
                event_type="workflow_started",
                trace=TraceContext(
                    trace_id=trace_id, span_id="span_003", parent_span_id="span_001"
                ),
                metadata={"workflow_id": "wf_001"},
            )
        )

        # 4. 节点执行
        store.write(
            StructuredLog(
                level=LogLevel.INFO,
                source="workflow_agent",
                message="执行数据采集节点",
                event_type="node_executed",
                trace=TraceContext(
                    trace_id=trace_id, span_id="span_004", parent_span_id="span_003"
                ),
                metadata={"node_id": "data_collector", "duration_ms": 150},
            )
        )

        # 5. 输出结果
        store.write(
            StructuredLog(
                level=LogLevel.INFO,
                source="conversation_agent",
                message="任务完成，返回结果",
                event_type="task_completed",
                trace=TraceContext(
                    trace_id=trace_id, span_id="span_005", parent_span_id="span_001"
                ),
                metadata={"output": "销售数据分析完成"},
            )
        )

        analyzer = TraceAnalyzer(log_store=store)
        task_trace = analyzer.reconstruct_trace(trace_id)

        assert task_trace is not None
        assert task_trace.trace_id == trace_id
        assert len(task_trace.spans) >= 4  # 至少有4个跨度

    def test_analyze_trace_not_found(self):
        """测试：追踪不存在"""
        from src.domain.services.log_analysis import TraceAnalyzer
        from src.domain.services.logging_metrics import InMemoryLogStore

        store = InMemoryLogStore()
        analyzer = TraceAnalyzer(log_store=store)

        result = analyzer.reconstruct_trace("nonexistent_trace")

        assert result is None

    def test_get_all_traces_in_period(self):
        """测试：获取时间段内所有追踪"""
        from src.domain.services.log_analysis import TraceAnalyzer
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
            TraceContext,
        )

        store = InMemoryLogStore()

        # 写入多个追踪的日志
        for i in range(5):
            store.write(
                StructuredLog(
                    level=LogLevel.INFO,
                    source="agent",
                    message=f"Task {i}",
                    event_type="user_input",
                    trace=TraceContext(trace_id=f"trace_{i:03d}", span_id=f"span_{i}"),
                )
            )

        analyzer = TraceAnalyzer(log_store=store)
        traces = analyzer.get_traces_in_period(
            start_time=datetime.now() - timedelta(hours=1),
            end_time=datetime.now() + timedelta(hours=1),
        )

        assert len(traces) == 5

    def test_reconstruct_full_task_chain(self):
        """测试：重建完整任务链（用户输入→对话→工作流→输出）"""
        from src.domain.services.log_analysis import TraceAnalyzer
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
            TraceContext,
        )

        store = InMemoryLogStore()
        trace_id = "trace_full_chain"
        base_time = datetime.now()

        # 完整链路日志
        logs_data = [
            {
                "source": "api_gateway",
                "event_type": "request_received",
                "span_id": "s1",
                "parent_span_id": None,
                "message": "收到 API 请求",
                "offset_ms": 0,
            },
            {
                "source": "conversation_agent",
                "event_type": "user_input",
                "span_id": "s2",
                "parent_span_id": "s1",
                "message": "解析用户输入: 查询最近订单",
                "offset_ms": 10,
            },
            {
                "source": "conversation_agent",
                "event_type": "intent_classified",
                "span_id": "s3",
                "parent_span_id": "s2",
                "message": "意图: query_orders",
                "offset_ms": 50,
            },
            {
                "source": "workflow_agent",
                "event_type": "workflow_started",
                "span_id": "s4",
                "parent_span_id": "s2",
                "message": "启动订单查询工作流",
                "offset_ms": 60,
            },
            {
                "source": "database_tool",
                "event_type": "node_started",
                "span_id": "s5",
                "parent_span_id": "s4",
                "message": "执行数据库查询",
                "offset_ms": 70,
            },
            {
                "source": "database_tool",
                "event_type": "node_completed",
                "span_id": "s5",
                "parent_span_id": "s4",
                "message": "查询完成，返回 10 条记录",
                "offset_ms": 200,
            },
            {
                "source": "llm_executor",
                "event_type": "node_started",
                "span_id": "s6",
                "parent_span_id": "s4",
                "message": "LLM 格式化结果",
                "offset_ms": 210,
            },
            {
                "source": "llm_executor",
                "event_type": "node_completed",
                "span_id": "s6",
                "parent_span_id": "s4",
                "message": "LLM 响应完成",
                "offset_ms": 500,
            },
            {
                "source": "workflow_agent",
                "event_type": "workflow_completed",
                "span_id": "s4",
                "parent_span_id": "s2",
                "message": "工作流执行完成",
                "offset_ms": 510,
            },
            {
                "source": "conversation_agent",
                "event_type": "response_generated",
                "span_id": "s7",
                "parent_span_id": "s2",
                "message": "生成最终响应",
                "offset_ms": 520,
            },
            {
                "source": "api_gateway",
                "event_type": "response_sent",
                "span_id": "s8",
                "parent_span_id": "s1",
                "message": "返回响应给客户端",
                "offset_ms": 530,
            },
        ]

        for log_data in logs_data:
            log = StructuredLog(
                level=LogLevel.INFO,
                source=log_data["source"],
                message=log_data["message"],
                event_type=log_data["event_type"],
                trace=TraceContext(
                    trace_id=trace_id,
                    span_id=log_data["span_id"],
                    parent_span_id=log_data["parent_span_id"],
                ),
                timestamp=base_time + timedelta(milliseconds=log_data["offset_ms"]),
            )
            store.write(log)

        analyzer = TraceAnalyzer(log_store=store)
        task_trace = analyzer.reconstruct_trace(trace_id)

        # 验证完整链路
        assert task_trace is not None
        assert len(task_trace.spans) >= 5

        # 验证链路完整性
        chain = task_trace.get_execution_chain()
        stages = [step["stage"] for step in chain]

        # 应该包含主要阶段
        assert "request_received" in stages or "user_input" in stages
        assert "workflow_started" in stages or "node_started" in stages


# ==================== 4. PerformanceAnalyzer 测试 ====================


class TestPerformanceAnalyzer:
    """性能分析器测试"""

    def test_analyzer_initialization(self):
        """测试：分析器初始化"""
        from src.domain.services.log_analysis import PerformanceAnalyzer

        analyzer = PerformanceAnalyzer()

        assert analyzer is not None

    def test_find_bottlenecks(self):
        """测试：发现性能瓶颈"""
        from src.domain.services.log_analysis import (
            PerformanceAnalyzer,
            TaskTrace,
            TraceSpan,
        )

        analyzer = PerformanceAnalyzer()

        # 创建多个追踪，模拟有瓶颈的场景
        traces = []
        for i in range(10):
            trace = TaskTrace(
                trace_id=f"trace_{i}",
                user_input=f"Task {i}",
                started_at=datetime.now(),
            )

            # 模拟快速操作
            trace.add_span(
                TraceSpan(
                    span_id=f"fast_{i}",
                    parent_span_id=None,
                    operation="fast_operation",
                    service="fast_service",
                    start_time=datetime.now(),
                    end_time=datetime.now() + timedelta(milliseconds=50),
                )
            )

            # 模拟慢操作（瓶颈）
            trace.add_span(
                TraceSpan(
                    span_id=f"slow_{i}",
                    parent_span_id=None,
                    operation="slow_database_query",
                    service="database_tool",
                    start_time=datetime.now(),
                    end_time=datetime.now() + timedelta(milliseconds=2000),
                )
            )

            traces.append(trace)

        bottlenecks = analyzer.find_bottlenecks(traces)

        assert len(bottlenecks) >= 1
        # 最慢的操作应该被识别为瓶颈
        assert any(b.operation == "slow_database_query" for b in bottlenecks)

    def test_analyze_latency_distribution(self):
        """测试：分析延迟分布"""
        from src.domain.services.log_analysis import (
            PerformanceAnalyzer,
            TaskTrace,
            TraceSpan,
        )

        analyzer = PerformanceAnalyzer()

        traces = []
        durations = [100, 150, 200, 250, 300, 500, 1000, 2000]

        for i, duration in enumerate(durations):
            trace = TaskTrace(
                trace_id=f"trace_{i}",
                user_input=f"Task {i}",
                started_at=datetime.now(),
            )
            trace.add_span(
                TraceSpan(
                    span_id=f"span_{i}",
                    parent_span_id=None,
                    operation="test_op",
                    service="test_svc",
                    start_time=datetime.now(),
                    end_time=datetime.now() + timedelta(milliseconds=duration),
                )
            )
            trace.complete(datetime.now() + timedelta(milliseconds=duration))
            traces.append(trace)

        distribution = analyzer.analyze_latency_distribution(traces)

        assert "p50" in distribution
        assert "p95" in distribution
        assert "p99" in distribution
        assert "avg" in distribution
        assert "min" in distribution
        assert "max" in distribution

    def test_identify_slow_services(self):
        """测试：识别慢服务"""
        from src.domain.services.log_analysis import (
            PerformanceAnalyzer,
            TaskTrace,
            TraceSpan,
        )

        analyzer = PerformanceAnalyzer()

        traces = []
        for i in range(10):
            trace = TaskTrace(
                trace_id=f"trace_{i}",
                user_input=f"Task {i}",
                started_at=datetime.now(),
            )

            # 不同服务不同延迟
            services = [
                ("fast_service", 50),
                ("medium_service", 200),
                ("slow_service", 1500),
            ]

            for svc, duration in services:
                trace.add_span(
                    TraceSpan(
                        span_id=f"{svc}_{i}",
                        parent_span_id=None,
                        operation=f"{svc}_op",
                        service=svc,
                        start_time=datetime.now(),
                        end_time=datetime.now() + timedelta(milliseconds=duration),
                    )
                )

            traces.append(trace)

        slow_services = analyzer.identify_slow_services(traces, threshold_ms=500)

        assert "slow_service" in slow_services
        assert "fast_service" not in slow_services

    def test_generate_performance_report(self):
        """测试：生成性能报告"""
        from src.domain.services.log_analysis import (
            PerformanceAnalyzer,
            TaskTrace,
            TraceSpan,
        )

        analyzer = PerformanceAnalyzer()

        traces = []
        for i in range(5):
            trace = TaskTrace(
                trace_id=f"trace_{i}",
                user_input=f"Task {i}",
                started_at=datetime.now(),
            )
            trace.add_span(
                TraceSpan(
                    span_id=f"span_{i}",
                    parent_span_id=None,
                    operation="test_op",
                    service="test_svc",
                    start_time=datetime.now(),
                    end_time=datetime.now() + timedelta(milliseconds=100 + i * 50),
                )
            )
            traces.append(trace)

        report = analyzer.generate_performance_report(traces)

        assert "summary" in report
        assert "bottlenecks" in report
        assert "latency_distribution" in report
        assert "slow_services" in report
        assert "recommendations" in report


# ==================== 5. PreferenceAnalyzer 测试 ====================


class TestPreferenceAnalyzer:
    """偏好分析器测试"""

    def test_analyzer_initialization(self):
        """测试：分析器初始化"""
        from src.domain.services.log_analysis import PreferenceAnalyzer

        analyzer = PreferenceAnalyzer()

        assert analyzer is not None

    def test_analyze_intent_distribution(self):
        """测试：分析意图分布"""
        from src.domain.services.log_analysis import (
            PreferenceAnalyzer,
            TaskTrace,
            TraceSpan,
        )

        analyzer = PreferenceAnalyzer()

        traces = []
        intents = [
            "query_data",
            "query_data",
            "query_data",
            "generate_report",
            "generate_report",
            "analyze_trend",
        ]

        for i, intent in enumerate(intents):
            trace = TaskTrace(
                trace_id=f"trace_{i}",
                user_input=f"Task for {intent}",
                started_at=datetime.now(),
            )
            trace.add_span(
                TraceSpan(
                    span_id=f"span_{i}",
                    parent_span_id=None,
                    operation="intent_classification",
                    service="conversation_agent",
                    start_time=datetime.now(),
                    end_time=datetime.now() + timedelta(milliseconds=50),
                    metadata={"intent": intent},
                )
            )
            traces.append(trace)

        distribution = analyzer.analyze_intent_distribution(traces)

        assert "query_data" in distribution
        assert distribution["query_data"]["count"] == 3
        assert distribution["query_data"]["percentage"] == 0.5  # 3/6

    def test_analyze_workflow_usage(self):
        """测试：分析工作流使用情况"""
        from src.domain.services.log_analysis import (
            PreferenceAnalyzer,
            TaskTrace,
            TraceSpan,
        )

        analyzer = PreferenceAnalyzer()

        traces = []
        workflows = [
            "sales_report",
            "sales_report",
            "sales_report",
            "inventory_check",
            "customer_analysis",
        ]

        for i, wf in enumerate(workflows):
            trace = TaskTrace(
                trace_id=f"trace_{i}",
                user_input=f"Execute {wf}",
                started_at=datetime.now(),
            )
            trace.add_span(
                TraceSpan(
                    span_id=f"span_{i}",
                    parent_span_id=None,
                    operation="workflow_execution",
                    service="workflow_agent",
                    start_time=datetime.now(),
                    end_time=datetime.now() + timedelta(milliseconds=1000),
                    metadata={"workflow_name": wf},
                )
            )
            traces.append(trace)

        usage = analyzer.analyze_workflow_usage(traces)

        assert "sales_report" in usage
        assert usage["sales_report"]["count"] == 3
        assert usage["sales_report"]["rank"] == 1  # 最常用

    def test_analyze_time_patterns(self):
        """测试：分析时间模式"""
        from src.domain.services.log_analysis import PreferenceAnalyzer, TaskTrace

        analyzer = PreferenceAnalyzer()

        traces = []
        # 模拟不同时间段的任务
        base_date = datetime(2025, 1, 15, 9, 0, 0)  # 9点开始

        hours = [9, 10, 10, 11, 14, 14, 14, 15, 16]  # 大部分在下午
        for i, hour in enumerate(hours):
            trace = TaskTrace(
                trace_id=f"trace_{i}",
                user_input=f"Task {i}",
                started_at=base_date.replace(hour=hour),
            )
            traces.append(trace)

        patterns = analyzer.analyze_time_patterns(traces)

        assert "peak_hours" in patterns
        assert "by_hour" in patterns
        # 14点应该是高峰
        assert 14 in patterns["peak_hours"]

    def test_extract_user_preferences(self):
        """测试：提取用户偏好"""
        from src.domain.services.log_analysis import (
            PreferenceAnalyzer,
            TaskTrace,
            TraceSpan,
        )

        analyzer = PreferenceAnalyzer()

        traces = []
        # 模拟用户偏好数据
        user_data = [
            {"model": "gpt-4", "format": "table"},
            {"model": "gpt-4", "format": "table"},
            {"model": "gpt-4", "format": "chart"},
            {"model": "gpt-3.5", "format": "table"},
        ]

        for i, data in enumerate(user_data):
            trace = TaskTrace(
                trace_id=f"trace_{i}",
                user_input=f"Task {i}",
                started_at=datetime.now(),
            )
            trace.add_span(
                TraceSpan(
                    span_id=f"span_{i}",
                    parent_span_id=None,
                    operation="llm_call",
                    service="llm_executor",
                    start_time=datetime.now(),
                    end_time=datetime.now() + timedelta(milliseconds=500),
                    metadata=data,
                )
            )
            traces.append(trace)

        preferences = analyzer.extract_user_preferences(traces)

        assert "preferred_model" in preferences
        assert preferences["preferred_model"] == "gpt-4"  # 最常用
        assert "preferred_format" in preferences
        assert preferences["preferred_format"] == "table"  # 最常用

    def test_generate_preference_report(self):
        """测试：生成偏好报告"""
        from src.domain.services.log_analysis import (
            PreferenceAnalyzer,
            TaskTrace,
            TraceSpan,
        )

        analyzer = PreferenceAnalyzer()

        traces = []
        for i in range(5):
            trace = TaskTrace(
                trace_id=f"trace_{i}",
                user_input=f"Task {i}",
                started_at=datetime.now(),
            )
            trace.add_span(
                TraceSpan(
                    span_id=f"span_{i}",
                    parent_span_id=None,
                    operation="test_op",
                    service="test_svc",
                    start_time=datetime.now(),
                    end_time=datetime.now() + timedelta(milliseconds=100),
                    metadata={"intent": "query_data"},
                )
            )
            traces.append(trace)

        report = analyzer.generate_preference_report(traces)

        assert "intent_distribution" in report
        assert "workflow_usage" in report
        assert "time_patterns" in report
        assert "user_preferences" in report


# ==================== 6. AuditReportGenerator 测试 ====================


class TestAuditReportGenerator:
    """审计报告生成器测试"""

    def test_generator_initialization(self):
        """测试：生成器初始化"""
        from src.domain.services.log_analysis import AuditReportGenerator
        from src.domain.services.logging_metrics import InMemoryLogStore

        store = InMemoryLogStore()
        generator = AuditReportGenerator(log_store=store)

        assert generator.log_store == store

    def test_generate_audit_report(self):
        """测试：生成审计报告"""
        from src.domain.services.log_analysis import AuditReportGenerator
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
            TraceContext,
        )

        store = InMemoryLogStore()

        # 写入测试日志
        for i in range(10):
            store.write(
                StructuredLog(
                    level=LogLevel.INFO,
                    source="agent",
                    message=f"Task {i}",
                    event_type="user_input",
                    trace=TraceContext(trace_id=f"trace_{i}", span_id=f"span_{i}"),
                    metadata={"intent": "query_data"},
                )
            )

        generator = AuditReportGenerator(log_store=store)
        report = generator.generate_report(
            start_time=datetime.now() - timedelta(hours=1),
            end_time=datetime.now() + timedelta(hours=1),
        )

        assert report is not None
        assert "report_id" in report
        assert "generated_at" in report
        assert "period" in report
        assert "summary" in report
        assert "traces" in report

    def test_report_includes_performance_analysis(self):
        """测试：报告包含性能分析"""
        from src.domain.services.log_analysis import AuditReportGenerator
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
            TraceContext,
        )

        store = InMemoryLogStore()

        # 写入带性能数据的日志
        for i in range(5):
            store.write(
                StructuredLog(
                    level=LogLevel.INFO,
                    source="agent",
                    message=f"Task {i}",
                    event_type="node_completed",
                    trace=TraceContext(trace_id=f"trace_{i}", span_id=f"span_{i}"),
                    metadata={"duration_ms": 100 + i * 50},
                )
            )

        generator = AuditReportGenerator(log_store=store)
        report = generator.generate_report(
            start_time=datetime.now() - timedelta(hours=1),
            end_time=datetime.now() + timedelta(hours=1),
        )

        assert "performance_analysis" in report

    def test_report_includes_preference_analysis(self):
        """测试：报告包含偏好分析"""
        from src.domain.services.log_analysis import AuditReportGenerator
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
            TraceContext,
        )

        store = InMemoryLogStore()

        # 写入带偏好数据的日志
        intents = ["query", "query", "report", "analyze"]
        for i, intent in enumerate(intents):
            store.write(
                StructuredLog(
                    level=LogLevel.INFO,
                    source="agent",
                    message=f"Task {i}",
                    event_type="intent_classified",
                    trace=TraceContext(trace_id=f"trace_{i}", span_id=f"span_{i}"),
                    metadata={"intent": intent},
                )
            )

        generator = AuditReportGenerator(log_store=store)
        report = generator.generate_report(
            start_time=datetime.now() - timedelta(hours=1),
            end_time=datetime.now() + timedelta(hours=1),
        )

        assert "preference_analysis" in report

    def test_export_report_to_json(self):
        """测试：导出报告为 JSON"""
        from src.domain.services.log_analysis import AuditReportGenerator
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
            TraceContext,
        )

        store = InMemoryLogStore()
        store.write(
            StructuredLog(
                level=LogLevel.INFO,
                source="agent",
                message="Test",
                event_type="user_input",
                trace=TraceContext(trace_id="trace_001", span_id="span_001"),
            )
        )

        generator = AuditReportGenerator(log_store=store)
        report = generator.generate_report(
            start_time=datetime.now() - timedelta(hours=1),
            end_time=datetime.now() + timedelta(hours=1),
        )

        json_output = generator.export_to_json(report)

        # 应该是有效的 JSON
        parsed = json.loads(json_output)
        assert "report_id" in parsed

    def test_export_report_to_markdown(self):
        """测试：导出报告为 Markdown"""
        from src.domain.services.log_analysis import AuditReportGenerator
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
            TraceContext,
        )

        store = InMemoryLogStore()
        store.write(
            StructuredLog(
                level=LogLevel.INFO,
                source="agent",
                message="Test",
                event_type="user_input",
                trace=TraceContext(trace_id="trace_001", span_id="span_001"),
            )
        )

        generator = AuditReportGenerator(log_store=store)
        report = generator.generate_report(
            start_time=datetime.now() - timedelta(hours=1),
            end_time=datetime.now() + timedelta(hours=1),
        )

        md_output = generator.export_to_markdown(report)

        # 应该包含 Markdown 标题
        assert "# " in md_output or "## " in md_output


# ==================== 7. Bottleneck 数据类测试 ====================


class TestBottleneck:
    """性能瓶颈数据类测试"""

    def test_create_bottleneck(self):
        """测试：创建瓶颈记录"""
        from src.domain.services.log_analysis import Bottleneck

        bottleneck = Bottleneck(
            operation="slow_query",
            service="database_tool",
            avg_duration_ms=2500,
            p95_duration_ms=3500,
            occurrence_count=50,
            suggestion="考虑添加数据库索引或优化查询语句",
        )

        assert bottleneck.operation == "slow_query"
        assert bottleneck.avg_duration_ms == 2500
        assert bottleneck.suggestion != ""

    def test_bottleneck_severity(self):
        """测试：瓶颈严重程度"""
        from src.domain.services.log_analysis import Bottleneck

        # 轻微瓶颈
        minor = Bottleneck(
            operation="op1",
            service="svc1",
            avg_duration_ms=500,
            p95_duration_ms=800,
            occurrence_count=10,
        )

        # 严重瓶颈
        severe = Bottleneck(
            operation="op2",
            service="svc2",
            avg_duration_ms=5000,
            p95_duration_ms=8000,
            occurrence_count=100,
        )

        assert minor.severity in ["low", "medium", "high", "critical"]
        assert severe.severity in ["high", "critical"]


# ==================== 8. 集成测试 ====================


class TestLogAnalysisIntegration:
    """日志分析集成测试"""

    def test_full_task_trace_analysis(self):
        """测试：完整任务追踪分析（用户输入→对话→工作流→输出）"""
        from src.domain.services.log_analysis import (
            AuditReportGenerator,
            PerformanceAnalyzer,
            PreferenceAnalyzer,
            TraceAnalyzer,
        )
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
            TraceContext,
        )

        store = InMemoryLogStore()
        trace_id = "trace_integration_test"
        base_time = datetime.now()

        # 模拟完整的任务执行链路
        full_chain = [
            # 1. 用户输入
            {
                "source": "api_gateway",
                "event_type": "request_received",
                "span_id": "api_1",
                "parent_span_id": None,
                "message": "POST /api/chat",
                "offset_ms": 0,
                "metadata": {"method": "POST", "path": "/api/chat"},
            },
            # 2. 对话处理开始
            {
                "source": "conversation_agent",
                "event_type": "conversation_started",
                "span_id": "conv_1",
                "parent_span_id": "api_1",
                "message": "开始处理对话",
                "offset_ms": 5,
                "metadata": {"user_input": "帮我分析上月销售数据，生成报表"},
            },
            # 3. 意图识别
            {
                "source": "conversation_agent",
                "event_type": "intent_classified",
                "span_id": "intent_1",
                "parent_span_id": "conv_1",
                "message": "意图识别: complex_analysis",
                "offset_ms": 50,
                "metadata": {"intent": "complex_analysis", "confidence": 0.92},
            },
            # 4. 目标分解
            {
                "source": "conversation_agent",
                "event_type": "goal_decomposed",
                "span_id": "goal_1",
                "parent_span_id": "conv_1",
                "message": "目标分解为3个子任务",
                "offset_ms": 100,
                "metadata": {"subtasks": ["data_fetch", "analysis", "report_gen"]},
            },
            # 5. 工作流启动
            {
                "source": "workflow_agent",
                "event_type": "workflow_started",
                "span_id": "wf_1",
                "parent_span_id": "conv_1",
                "message": "启动销售分析工作流",
                "offset_ms": 110,
                "metadata": {"workflow_id": "sales_analysis_v1"},
            },
            # 6. 数据采集节点
            {
                "source": "database_tool",
                "event_type": "node_started",
                "span_id": "node_1",
                "parent_span_id": "wf_1",
                "message": "开始数据采集",
                "offset_ms": 120,
                "metadata": {"node_type": "DATA_COLLECTOR"},
            },
            {
                "source": "database_tool",
                "event_type": "node_completed",
                "span_id": "node_1",
                "parent_span_id": "wf_1",
                "message": "数据采集完成",
                "offset_ms": 350,
                "metadata": {"rows_fetched": 1500, "duration_ms": 230},
            },
            # 7. 分析节点
            {
                "source": "llm_executor",
                "event_type": "node_started",
                "span_id": "node_2",
                "parent_span_id": "wf_1",
                "message": "开始 LLM 分析",
                "offset_ms": 360,
                "metadata": {"node_type": "LLM", "model": "gpt-4"},
            },
            {
                "source": "llm_executor",
                "event_type": "node_completed",
                "span_id": "node_2",
                "parent_span_id": "wf_1",
                "message": "LLM 分析完成",
                "offset_ms": 1200,
                "metadata": {"tokens_used": 2500, "duration_ms": 840},
            },
            # 8. 报表生成节点
            {
                "source": "report_generator",
                "event_type": "node_started",
                "span_id": "node_3",
                "parent_span_id": "wf_1",
                "message": "开始生成报表",
                "offset_ms": 1210,
                "metadata": {"node_type": "REPORT_GEN"},
            },
            {
                "source": "report_generator",
                "event_type": "node_completed",
                "span_id": "node_3",
                "parent_span_id": "wf_1",
                "message": "报表生成完成",
                "offset_ms": 1500,
                "metadata": {"format": "excel", "duration_ms": 290},
            },
            # 9. 工作流完成
            {
                "source": "workflow_agent",
                "event_type": "workflow_completed",
                "span_id": "wf_1",
                "parent_span_id": "conv_1",
                "message": "工作流执行完成",
                "offset_ms": 1510,
                "metadata": {"success": True, "total_nodes": 3},
            },
            # 10. 生成响应
            {
                "source": "conversation_agent",
                "event_type": "response_generated",
                "span_id": "resp_1",
                "parent_span_id": "conv_1",
                "message": "生成用户响应",
                "offset_ms": 1520,
                "metadata": {"output_type": "report_with_summary"},
            },
            # 11. 返回结果
            {
                "source": "api_gateway",
                "event_type": "response_sent",
                "span_id": "api_2",
                "parent_span_id": "api_1",
                "message": "响应已发送",
                "offset_ms": 1550,
                "metadata": {"status_code": 200},
            },
        ]

        # 写入日志
        for log_data in full_chain:
            log = StructuredLog(
                level=LogLevel.INFO,
                source=log_data["source"],
                message=log_data["message"],
                event_type=log_data["event_type"],
                trace=TraceContext(
                    trace_id=trace_id,
                    span_id=log_data["span_id"],
                    parent_span_id=log_data["parent_span_id"],
                ),
                timestamp=base_time + timedelta(milliseconds=log_data["offset_ms"]),
                metadata=log_data.get("metadata", {}),
            )
            store.write(log)

        # 1. 追踪分析
        trace_analyzer = TraceAnalyzer(log_store=store)
        task_trace = trace_analyzer.reconstruct_trace(trace_id)

        assert task_trace is not None
        assert len(task_trace.spans) >= 10

        # 验证链路完整性
        chain = task_trace.get_execution_chain()
        assert len(chain) >= 5

        # 2. 性能分析
        perf_analyzer = PerformanceAnalyzer()
        bottlenecks = perf_analyzer.find_bottlenecks([task_trace])

        # LLM 节点应该是最慢的
        if bottlenecks:
            slowest = max(bottlenecks, key=lambda b: b.avg_duration_ms)
            assert slowest.avg_duration_ms > 500

        # 3. 偏好分析
        pref_analyzer = PreferenceAnalyzer()
        preferences = pref_analyzer.extract_user_preferences([task_trace])

        assert preferences is not None

        # 4. 生成审计报告
        report_generator = AuditReportGenerator(log_store=store)
        report = report_generator.generate_report(
            start_time=base_time - timedelta(minutes=1),
            end_time=base_time + timedelta(minutes=5),
        )

        assert report is not None
        assert "summary" in report
        assert "performance_analysis" in report
        assert "preference_analysis" in report

    def test_bottleneck_detection_scenario(self):
        """测试：瓶颈检测场景"""
        from src.domain.services.log_analysis import (
            PerformanceAnalyzer,
            TraceAnalyzer,
        )
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
            TraceContext,
        )

        store = InMemoryLogStore()
        base_time = datetime.now()

        # 模拟多个任务，其中数据库查询是瓶颈
        for task_idx in range(10):
            trace_id = f"trace_perf_{task_idx}"

            # 快速操作
            store.write(
                StructuredLog(
                    level=LogLevel.INFO,
                    source="agent",
                    message="Intent classified",
                    event_type="intent_classified",
                    trace=TraceContext(trace_id=trace_id, span_id=f"s1_{task_idx}"),
                    timestamp=base_time + timedelta(seconds=task_idx),
                    metadata={"duration_ms": 30},
                )
            )

            # 慢操作（瓶颈）
            store.write(
                StructuredLog(
                    level=LogLevel.INFO,
                    source="database_tool",
                    message="Database query",
                    event_type="node_completed",
                    trace=TraceContext(
                        trace_id=trace_id,
                        span_id=f"s2_{task_idx}",
                        parent_span_id=f"s1_{task_idx}",
                    ),
                    timestamp=base_time + timedelta(seconds=task_idx, milliseconds=2500),
                    metadata={"duration_ms": 2500, "operation": "complex_join_query"},
                )
            )

        trace_analyzer = TraceAnalyzer(log_store=store)
        perf_analyzer = PerformanceAnalyzer()

        # 重建所有追踪
        traces = trace_analyzer.get_traces_in_period(
            start_time=base_time - timedelta(minutes=1),
            end_time=base_time + timedelta(minutes=5),
        )

        assert len(traces) == 10

        # 发现瓶颈
        bottlenecks = perf_analyzer.find_bottlenecks(traces)

        assert len(bottlenecks) >= 1
        # 数据库查询应该被识别为瓶颈
        db_bottleneck = next((b for b in bottlenecks if "database" in b.service.lower()), None)
        assert db_bottleneck is not None
        assert db_bottleneck.avg_duration_ms >= 2000

    def test_preference_mining_scenario(self):
        """测试：偏好挖掘场景"""
        from src.domain.services.log_analysis import (
            PreferenceAnalyzer,
            TraceAnalyzer,
        )
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
            TraceContext,
        )

        store = InMemoryLogStore()
        base_time = datetime.now()

        # 模拟用户行为数据
        user_actions = [
            {"intent": "query_sales", "workflow": "sales_report", "format": "table"},
            {"intent": "query_sales", "workflow": "sales_report", "format": "table"},
            {"intent": "query_sales", "workflow": "sales_report", "format": "chart"},
            {"intent": "analyze_trend", "workflow": "trend_analysis", "format": "chart"},
            {"intent": "query_inventory", "workflow": "inventory_check", "format": "table"},
            {"intent": "query_sales", "workflow": "sales_report", "format": "table"},
        ]

        for i, action in enumerate(user_actions):
            trace_id = f"trace_pref_{i}"

            store.write(
                StructuredLog(
                    level=LogLevel.INFO,
                    source="conversation_agent",
                    message=f"Intent: {action['intent']}",
                    event_type="intent_classified",
                    trace=TraceContext(trace_id=trace_id, span_id=f"s1_{i}"),
                    timestamp=base_time + timedelta(minutes=i),
                    metadata={"intent": action["intent"]},
                )
            )

            store.write(
                StructuredLog(
                    level=LogLevel.INFO,
                    source="workflow_agent",
                    message=f"Workflow: {action['workflow']}",
                    event_type="workflow_completed",
                    trace=TraceContext(
                        trace_id=trace_id, span_id=f"s2_{i}", parent_span_id=f"s1_{i}"
                    ),
                    timestamp=base_time + timedelta(minutes=i, seconds=30),
                    metadata={
                        "workflow_name": action["workflow"],
                        "output_format": action["format"],
                    },
                )
            )

        trace_analyzer = TraceAnalyzer(log_store=store)
        pref_analyzer = PreferenceAnalyzer()

        traces = trace_analyzer.get_traces_in_period(
            start_time=base_time - timedelta(minutes=1),
            end_time=base_time + timedelta(hours=1),
        )

        # 分析偏好
        intent_dist = pref_analyzer.analyze_intent_distribution(traces)
        workflow_usage = pref_analyzer.analyze_workflow_usage(traces)
        preferences = pref_analyzer.extract_user_preferences(traces)

        # query_sales 应该是最常见的意图
        assert "query_sales" in intent_dist
        assert intent_dist["query_sales"]["count"] == 4

        # sales_report 应该是最常用的工作流
        assert "sales_report" in workflow_usage
        assert workflow_usage["sales_report"]["count"] == 4

        # 用户偏好 table 格式
        assert preferences["preferred_format"] == "table"


# ==================== 9. 报告输出示例测试 ====================


class TestAuditReportExamples:
    """审计报告输出示例测试"""

    def test_json_report_structure(self):
        """测试：JSON 报告结构"""
        from src.domain.services.log_analysis import AuditReportGenerator
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
            TraceContext,
        )

        store = InMemoryLogStore()

        # 写入样例数据
        for i in range(3):
            store.write(
                StructuredLog(
                    level=LogLevel.INFO,
                    source="agent",
                    message=f"Test {i}",
                    event_type="user_input",
                    trace=TraceContext(trace_id=f"trace_{i}", span_id=f"span_{i}"),
                )
            )

        generator = AuditReportGenerator(log_store=store)
        report = generator.generate_report(
            start_time=datetime.now() - timedelta(hours=1),
            end_time=datetime.now() + timedelta(hours=1),
        )

        json_output = generator.export_to_json(report)
        parsed = json.loads(json_output)

        # 验证必要字段
        required_fields = [
            "report_id",
            "generated_at",
            "period",
            "summary",
            "traces",
            "performance_analysis",
            "preference_analysis",
        ]

        for field in required_fields:
            assert field in parsed, f"Missing field: {field}"

    def test_markdown_report_format(self):
        """测试：Markdown 报告格式"""
        from src.domain.services.log_analysis import AuditReportGenerator
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
            TraceContext,
        )

        store = InMemoryLogStore()

        store.write(
            StructuredLog(
                level=LogLevel.INFO,
                source="agent",
                message="Test task",
                event_type="user_input",
                trace=TraceContext(trace_id="trace_001", span_id="span_001"),
                metadata={"intent": "query_data"},
            )
        )

        generator = AuditReportGenerator(log_store=store)
        report = generator.generate_report(
            start_time=datetime.now() - timedelta(hours=1),
            end_time=datetime.now() + timedelta(hours=1),
        )

        md_output = generator.export_to_markdown(report)

        # 验证 Markdown 格式
        assert "# 审计报告" in md_output or "# Audit Report" in md_output
        assert "##" in md_output  # 应该有二级标题
        assert "---" in md_output or "```" in md_output  # 应该有分隔符或代码块
