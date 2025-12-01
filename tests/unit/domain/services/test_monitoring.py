"""监控系统测试

Phase 4.2: 监控 - TDD测试

测试覆盖:
- 指标收集器 (MetricsCollector)
- 链路追踪 (Tracer)
- 健康检查 (HealthChecker)
- 告警管理 (AlertManager)
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest


class TestMetricsCollector:
    """指标收集器测试"""

    def test_record_counter_metric(self):
        """测试：记录计数器指标

        真实场景：
        - 记录API调用次数
        - 记录工作流执行次数

        验收标准：
        - 正确累加计数
        - 支持标签
        """
        from src.domain.services.monitoring import MetricsCollector

        collector = MetricsCollector()

        # 记录API调用
        collector.increment("api_calls", labels={"endpoint": "/workflows"})
        collector.increment("api_calls", labels={"endpoint": "/workflows"})
        collector.increment("api_calls", labels={"endpoint": "/agents"})

        # 获取指标
        metrics = collector.get_metrics()

        assert metrics["api_calls"]["endpoint=/workflows"] == 2
        assert metrics["api_calls"]["endpoint=/agents"] == 1

    def test_record_gauge_metric(self):
        """测试：记录仪表盘指标

        真实场景：
        - 记录当前活跃连接数
        - 记录缓存命中率

        验收标准：
        - 可设置为任意值
        - 可增减
        """
        from src.domain.services.monitoring import MetricsCollector

        collector = MetricsCollector()

        # 设置活跃连接数
        collector.set_gauge("active_connections", 10)
        collector.set_gauge("active_connections", 15)

        # 增减
        collector.inc_gauge("active_connections", 5)
        collector.dec_gauge("active_connections", 3)

        metrics = collector.get_metrics()
        assert metrics["active_connections"] == 17

    def test_record_histogram_metric(self):
        """测试：记录直方图指标

        真实场景：
        - 记录请求响应时间分布
        - 记录LLM调用耗时

        验收标准：
        - 支持分桶统计
        - 计算百分位数
        """
        from src.domain.services.monitoring import MetricsCollector

        collector = MetricsCollector()

        # 记录响应时间
        response_times = [0.1, 0.2, 0.15, 0.5, 1.0, 0.3, 0.25]
        for rt in response_times:
            collector.observe("response_time", rt)

        histogram = collector.get_histogram("response_time")

        assert histogram["count"] == 7
        assert histogram["sum"] == sum(response_times)
        assert histogram["p50"] is not None  # 50th percentile
        assert histogram["p95"] is not None  # 95th percentile

    def test_record_with_timestamp(self):
        """测试：带时间戳的指标记录

        真实场景：
        - 时序分析
        - 趋势图展示

        验收标准：
        - 记录时间戳
        - 支持时间范围查询
        """
        from src.domain.services.monitoring import MetricsCollector

        collector = MetricsCollector()

        # 记录带时间戳的指标
        collector.increment("requests", timestamp=datetime.now())
        collector.increment("requests", timestamp=datetime.now())

        # 查询时间范围
        since = datetime.now() - timedelta(minutes=5)
        series = collector.get_time_series("requests", since=since)

        assert len(series) == 2


class TestTracer:
    """链路追踪测试"""

    @pytest.mark.asyncio
    async def test_create_trace_span(self):
        """测试：创建追踪span

        真实场景：
        - 追踪工作流执行链路
        - 定位性能瓶颈

        验收标准：
        - 正确记录开始/结束时间
        - 支持嵌套span
        """
        from src.domain.services.monitoring import Tracer

        tracer = Tracer()

        async with tracer.span("workflow_execution") as span:
            span.set_attribute("workflow_id", "wf_123")
            await asyncio.sleep(0.01)

            async with tracer.span("node_execution", parent=span) as child_span:
                child_span.set_attribute("node_id", "node_1")
                await asyncio.sleep(0.01)

        assert span.duration > 0
        assert span.attributes["workflow_id"] == "wf_123"
        assert child_span.parent_id == span.span_id

    @pytest.mark.asyncio
    async def test_trace_propagation(self):
        """测试：链路追踪传播

        真实场景：
        - 跨服务调用追踪
        - 分布式系统调试

        验收标准：
        - trace_id保持一致
        - 支持跨上下文传播
        """
        from src.domain.services.monitoring import Tracer

        tracer = Tracer()

        # 创建根span
        async with tracer.span("parent") as parent:
            # 获取传播上下文
            context = tracer.get_propagation_context(parent)

            # 在另一个"服务"中恢复上下文
            restored_parent = tracer.restore_context(context)
            async with tracer.span("child", parent=restored_parent) as child:
                pass

        # 应该共享同一个trace_id
        assert parent.trace_id == child.trace_id

    @pytest.mark.asyncio
    async def test_record_span_events(self):
        """测试：记录span事件

        真实场景：
        - 记录关键执行点
        - 记录错误信息

        验收标准：
        - 支持事件时间戳
        - 支持事件属性
        """
        from src.domain.services.monitoring import Tracer

        tracer = Tracer()

        async with tracer.span("process") as span:
            span.add_event("started_processing")
            await asyncio.sleep(0.01)
            span.add_event("completed_step_1", {"items_processed": 100})

            try:
                raise ValueError("模拟错误")
            except Exception as e:
                span.record_exception(e)

        assert len(span.events) == 3  # 2 events + 1 exception
        assert span.events[0]["name"] == "started_processing"
        assert span.events[-1]["name"] == "exception"


class TestHealthChecker:
    """健康检查测试"""

    @pytest.mark.asyncio
    async def test_check_component_health(self):
        """测试：检查组件健康状态

        真实场景：
        - 检查数据库连接
        - 检查外部服务可用性

        验收标准：
        - 返回健康状态
        - 包含详细信息
        """
        from src.domain.services.monitoring import HealthChecker, HealthStatus

        checker = HealthChecker()

        # 注册健康检查
        async def check_database():
            return {"status": "healthy", "latency_ms": 5}

        async def check_redis():
            return {"status": "unhealthy", "error": "Connection refused"}

        checker.register("database", check_database)
        checker.register("redis", check_redis)

        # 执行检查
        result = await checker.check_all()

        assert result.overall_status == HealthStatus.UNHEALTHY
        assert result.components["database"]["status"] == "healthy"
        assert result.components["redis"]["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_health_check_timeout(self):
        """测试：健康检查超时

        真实场景：
        - 组件响应慢
        - 避免阻塞

        验收标准：
        - 超时后返回unhealthy
        - 记录超时信息
        """
        from src.domain.services.monitoring import HealthChecker

        checker = HealthChecker(timeout=0.1)

        async def slow_check():
            await asyncio.sleep(1.0)  # 超过超时时间
            return {"status": "healthy"}

        checker.register("slow_service", slow_check)

        result = await checker.check_all()

        assert result.components["slow_service"]["status"] == "timeout"

    @pytest.mark.asyncio
    async def test_readiness_vs_liveness(self):
        """测试：就绪检查vs存活检查

        真实场景：
        - Kubernetes探针
        - 服务启动/运行状态

        验收标准：
        - 分离就绪和存活检查
        - 不同的检查逻辑
        """
        from src.domain.services.monitoring import HealthChecker

        checker = HealthChecker()

        # 存活检查：进程是否在运行
        checker.register_liveness("process", lambda: {"status": "healthy"})

        # 就绪检查：是否可以接受请求
        checker.register_readiness("database", lambda: {"status": "healthy", "connections": 10})

        liveness = await checker.check_liveness()
        readiness = await checker.check_readiness()

        assert "process" in liveness.components
        assert "database" in readiness.components
        assert "process" not in readiness.components


class TestAlertManager:
    """告警管理测试"""

    @pytest.mark.asyncio
    async def test_trigger_alert(self):
        """测试：触发告警

        真实场景：
        - 错误率超阈值
        - 延迟异常

        验收标准：
        - 正确触发告警
        - 包含告警详情
        """
        from src.domain.services.monitoring import AlertManager, AlertSeverity

        manager = AlertManager()

        # 定义告警规则
        manager.add_rule(
            name="high_error_rate",
            condition=lambda metrics: metrics.get("error_rate", 0) > 0.1,
            severity=AlertSeverity.CRITICAL,
            message="错误率超过10%",
        )

        # 触发检查
        alerts = await manager.evaluate({"error_rate": 0.15})

        assert len(alerts) == 1
        assert alerts[0].name == "high_error_rate"
        assert alerts[0].severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_alert_deduplication(self):
        """测试：告警去重

        真实场景：
        - 避免重复告警
        - 告警风暴抑制

        验收标准：
        - 相同告警不重复触发
        - 支持静默期
        """
        from src.domain.services.monitoring import AlertManager, AlertSeverity

        manager = AlertManager(silence_duration=60)  # 60秒静默期

        manager.add_rule(
            name="high_latency",
            condition=lambda m: m.get("latency_p99", 0) > 1.0,
            severity=AlertSeverity.WARNING,
        )

        # 第一次触发
        alerts1 = await manager.evaluate({"latency_p99": 1.5})
        # 立即再次评估（在静默期内）
        alerts2 = await manager.evaluate({"latency_p99": 1.5})

        assert len(alerts1) == 1
        assert len(alerts2) == 0  # 被去重

    @pytest.mark.asyncio
    async def test_alert_notification(self):
        """测试：告警通知

        真实场景：
        - 发送邮件通知
        - 发送Slack消息

        验收标准：
        - 调用通知渠道
        - 格式化告警信息
        """
        from src.domain.services.monitoring import AlertManager, AlertSeverity, NotificationChannel

        # Mock通知渠道
        mock_channel = AsyncMock(spec=NotificationChannel)

        manager = AlertManager()
        manager.add_notification_channel(mock_channel)

        manager.add_rule(
            name="service_down",
            condition=lambda m: m.get("health") == "down",
            severity=AlertSeverity.CRITICAL,
        )

        await manager.evaluate({"health": "down"})

        mock_channel.send.assert_called_once()
        call_args = mock_channel.send.call_args[0][0]
        assert call_args.name == "service_down"


class TestRealWorldScenarios:
    """真实业务场景测试"""

    @pytest.mark.asyncio
    async def test_workflow_execution_monitoring(self):
        """测试：工作流执行监控

        真实业务场景：
        - 追踪整个工作流执行过程
        - 收集每个节点的执行指标
        - 检测性能异常

        验收标准：
        - 完整的执行链路
        - 准确的性能指标
        - 及时的异常告警
        """
        from src.domain.services.monitoring import (
            AlertManager,
            AlertSeverity,
            MetricsCollector,
            Tracer,
        )

        metrics = MetricsCollector()
        tracer = Tracer()
        alerts = AlertManager()

        # 配置告警规则
        alerts.add_rule(
            name="slow_node",
            condition=lambda m: m.get("node_duration", 0) > 5.0,
            severity=AlertSeverity.WARNING,
        )

        # 模拟工作流执行
        workflow_id = "wf_customer_service_001"

        async with tracer.span("workflow", attributes={"workflow_id": workflow_id}) as wf_span:
            metrics.increment("workflow_started", labels={"workflow_id": workflow_id})

            nodes = ["fetch_kb", "generate_response", "send_reply"]

            for node_id in nodes:
                async with tracer.span(
                    "node", parent=wf_span, attributes={"node_id": node_id}
                ) as node_span:
                    metrics.increment("node_started", labels={"node_id": node_id})

                    # 模拟执行
                    await asyncio.sleep(0.01)

                    # 记录执行时间
                    metrics.observe(
                        "node_duration", node_span.duration, labels={"node_id": node_id}
                    )

            metrics.increment("workflow_completed", labels={"workflow_id": workflow_id})

        # 验证指标
        all_metrics = metrics.get_metrics()
        assert all_metrics["workflow_started"][f"workflow_id={workflow_id}"] == 1
        assert all_metrics["workflow_completed"][f"workflow_id={workflow_id}"] == 1

        # 验证追踪
        assert wf_span.attributes["workflow_id"] == workflow_id

    @pytest.mark.asyncio
    async def test_llm_call_monitoring(self):
        """测试：LLM调用监控

        真实业务场景：
        - 追踪LLM API调用
        - 监控token使用和成本
        - 检测调用异常

        验收标准：
        - 记录调用次数和耗时
        - 统计token使用量
        - 检测错误率
        """
        from src.domain.services.monitoring import (
            MetricsCollector,
            Tracer,
        )

        metrics = MetricsCollector()
        tracer = Tracer()

        async def mock_llm_call(prompt: str):
            async with tracer.span("llm_call") as span:
                metrics.increment("llm_calls", labels={"model": "gpt-4"})

                # 模拟调用
                await asyncio.sleep(0.02)

                # 记录token
                input_tokens = len(prompt.split())
                output_tokens = 50
                metrics.inc_gauge("total_tokens", input_tokens + output_tokens)
                metrics.observe("llm_latency", span.duration, labels={"model": "gpt-4"})

                span.set_attribute("input_tokens", input_tokens)
                span.set_attribute("output_tokens", output_tokens)

                return {"response": "模拟响应"}

        # 执行多次调用
        for i in range(5):
            await mock_llm_call(f"这是第{i+1}个测试提示词")

        # 验证指标
        all_metrics = metrics.get_metrics()
        assert all_metrics["llm_calls"]["model=gpt-4"] == 5

        histogram = metrics.get_histogram("llm_latency")
        assert histogram["count"] == 5

    @pytest.mark.asyncio
    async def test_end_to_end_request_tracing(self):
        """测试：端到端请求追踪

        真实业务场景：
        - 用户请求从API到数据库的完整链路
        - 定位性能瓶颈

        验收标准：
        - 所有span共享同一trace_id
        - 正确的父子关系
        - 完整的耗时分解
        """
        from src.domain.services.monitoring import Tracer

        tracer = Tracer()

        async with tracer.span("api_request", attributes={"path": "/chat"}) as api_span:
            # 验证请求
            async with tracer.span("auth", parent=api_span) as auth_span:
                await asyncio.sleep(0.005)

            # 业务逻辑
            async with tracer.span("business_logic", parent=api_span) as biz_span:
                # 查询数据库
                async with tracer.span("db_query", parent=biz_span) as db_span:
                    await asyncio.sleep(0.01)

                # 调用LLM
                async with tracer.span("llm_call", parent=biz_span) as llm_span:
                    await asyncio.sleep(0.02)

        # 验证trace_id一致性
        assert api_span.trace_id == auth_span.trace_id
        assert api_span.trace_id == biz_span.trace_id
        assert api_span.trace_id == db_span.trace_id
        assert api_span.trace_id == llm_span.trace_id

        # 验证父子关系
        assert auth_span.parent_id == api_span.span_id
        assert biz_span.parent_id == api_span.span_id
        assert db_span.parent_id == biz_span.span_id
        assert llm_span.parent_id == biz_span.span_id


class TestMonitoringFactory:
    """监控工厂测试"""

    def test_create_monitoring_suite(self):
        """测试：创建监控套件"""
        from src.domain.services.monitoring import MonitoringFactory

        suite = MonitoringFactory.create()

        assert suite.metrics is not None
        assert suite.tracer is not None
        assert suite.health_checker is not None
        assert suite.alert_manager is not None

    def test_create_with_custom_config(self):
        """测试：使用自定义配置创建"""
        from src.domain.services.monitoring import MonitoringFactory

        config = {
            "health_check_timeout": 5.0,
            "alert_silence_duration": 300,
            "enable_tracing": True,
        }

        suite = MonitoringFactory.create(config)

        assert suite.health_checker.timeout == 5.0
        assert suite.alert_manager.silence_duration == 300
