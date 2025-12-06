"""监控与知识模块联动测试 (TDD - Step 9)

测试内容：
1. MonitoringKnowledgeBridge - 监控-知识桥接器（连接监控与知识库）
2. AlertKnowledgeHandler - 告警知识处理器（告警→知识条目）
3. PerformanceKnowledgeAdapter - 性能知识适配器（瓶颈→知识）
4. 闭环场景集成测试

完成标准：
- 测试覆盖"监控→知识库"联动场景
- 日志示例展示告警产生后自动更新知识库
- 文档说明该闭环系统
"""

import time

# ==================== 1. MonitoringKnowledgeBridge 测试 ====================


class TestMonitoringKnowledgeBridge:
    """监控-知识桥接器测试"""

    def test_bridge_initialization(self):
        """测试：桥接器初始化"""
        from src.domain.services.dynamic_node_monitoring import AlertManager
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import (
            MonitoringKnowledgeBridge,
        )

        maintainer = KnowledgeMaintainer()
        alert_manager = AlertManager()

        bridge = MonitoringKnowledgeBridge(
            knowledge_maintainer=maintainer,
            alert_manager=alert_manager,
        )

        assert bridge is not None
        assert bridge.knowledge_maintainer is maintainer
        assert bridge.alert_manager is alert_manager

    def test_bridge_registers_alert_callback(self):
        """测试：桥接器注册告警回调"""
        from src.domain.services.dynamic_node_monitoring import AlertManager
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import (
            MonitoringKnowledgeBridge,
        )

        maintainer = KnowledgeMaintainer()
        alert_manager = AlertManager()

        _bridge = MonitoringKnowledgeBridge(
            knowledge_maintainer=maintainer,
            alert_manager=alert_manager,
        )

        # 桥接器应该自动注册回调
        assert alert_manager._notification_callback is not None

    def test_bridge_handles_alert_creates_failure_case(self):
        """测试：桥接器处理告警并创建失败案例"""
        from src.domain.services.dynamic_node_monitoring import AlertManager
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import (
            MonitoringKnowledgeBridge,
        )

        maintainer = KnowledgeMaintainer()
        alert_manager = AlertManager()
        alert_manager.set_threshold("sandbox_failure_rate", 0.3)

        _bridge = MonitoringKnowledgeBridge(
            knowledge_maintainer=maintainer,
            alert_manager=alert_manager,
        )

        # 初始状态
        assert maintainer.failure_count == 0

        # 触发告警（超过阈值）
        alert_manager.check_failure_rate(0.5)

        # 应该自动创建失败案例
        assert maintainer.failure_count == 1

    def test_bridge_tracks_processed_alerts(self):
        """测试：桥接器跟踪已处理的告警"""
        from src.domain.services.dynamic_node_monitoring import AlertManager
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import (
            MonitoringKnowledgeBridge,
        )

        maintainer = KnowledgeMaintainer()
        alert_manager = AlertManager()
        alert_manager.set_threshold("sandbox_failure_rate", 0.3)

        bridge = MonitoringKnowledgeBridge(
            knowledge_maintainer=maintainer,
            alert_manager=alert_manager,
        )

        # 触发告警
        alert_manager.check_failure_rate(0.5)

        # 检查处理记录
        assert bridge.processed_alert_count == 1

    def test_bridge_does_not_duplicate_failure_for_same_alert(self):
        """测试：桥接器不重复创建同一告警的失败案例"""
        from src.domain.services.dynamic_node_monitoring import AlertManager
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import (
            MonitoringKnowledgeBridge,
        )

        maintainer = KnowledgeMaintainer()
        alert_manager = AlertManager()
        alert_manager.set_threshold("sandbox_failure_rate", 0.3)

        _bridge = MonitoringKnowledgeBridge(
            knowledge_maintainer=maintainer,
            alert_manager=alert_manager,
        )

        # 多次检查相同的失败率
        alert_manager.check_failure_rate(0.5)
        alert_manager.check_failure_rate(0.5)
        alert_manager.check_failure_rate(0.5)

        # AlertManager 不会重复创建告警，所以 failure_count 应该是 1
        assert maintainer.failure_count == 1


# ==================== 2. AlertKnowledgeHandler 测试 ====================


class TestAlertKnowledgeHandler:
    """告警知识处理器测试"""

    def test_handler_initialization(self):
        """测试：处理器初始化"""
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import (
            AlertKnowledgeHandler,
        )

        maintainer = KnowledgeMaintainer()
        handler = AlertKnowledgeHandler(maintainer)

        assert handler is not None
        assert handler.knowledge_maintainer is maintainer

    def test_handle_critical_alert_creates_failure_case(self):
        """测试：处理严重告警创建失败案例"""
        from src.domain.services.dynamic_node_monitoring import Alert
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import (
            AlertKnowledgeHandler,
        )

        maintainer = KnowledgeMaintainer()
        handler = AlertKnowledgeHandler(maintainer)

        alert = Alert(
            id="alert_001",
            type="sandbox_failure_rate",
            message="Sandbox failure rate 60% exceeds threshold 30%",
            severity="critical",
            created_at=time.time(),
        )

        result = handler.handle_alert(alert)

        assert result["success"] is True
        assert result["action"] == "failure_case_created"
        assert maintainer.failure_count == 1

    def test_handle_warning_alert_creates_memory(self):
        """测试：处理警告告警创建记忆"""
        from src.domain.services.dynamic_node_monitoring import Alert
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import (
            AlertKnowledgeHandler,
        )

        maintainer = KnowledgeMaintainer()
        handler = AlertKnowledgeHandler(maintainer)

        alert = Alert(
            id="alert_002",
            type="sandbox_failure_rate",
            message="Sandbox failure rate 40% exceeds threshold 30%",
            severity="warning",
            created_at=time.time(),
        )

        result = handler.handle_alert(alert)

        assert result["success"] is True
        assert result["action"] == "memory_created"
        assert maintainer.memory_count == 1

    def test_handle_alert_extracts_prevention_strategy(self):
        """测试：处理告警时提取预防策略"""
        from src.domain.services.dynamic_node_monitoring import Alert
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import (
            AlertKnowledgeHandler,
        )

        maintainer = KnowledgeMaintainer()
        handler = AlertKnowledgeHandler(maintainer)

        alert = Alert(
            id="alert_003",
            type="sandbox_failure_rate",
            message="Sandbox failure rate 80% exceeds threshold 30%",
            severity="critical",
            created_at=time.time(),
        )

        handler.handle_alert(alert)

        # 检查创建的失败案例是否有预防策略
        failures = maintainer.get_failures()
        assert len(failures) == 1
        assert len(failures[0].prevention_strategy) > 0

    def test_handle_alert_sets_correct_failure_category(self):
        """测试：处理告警时设置正确的失败类别"""
        from src.domain.services.dynamic_node_monitoring import Alert
        from src.domain.services.knowledge_maintenance import (
            FailureCategory,
            KnowledgeMaintainer,
        )
        from src.domain.services.monitoring_knowledge_bridge import (
            AlertKnowledgeHandler,
        )

        maintainer = KnowledgeMaintainer()
        handler = AlertKnowledgeHandler(maintainer)

        # 资源耗尽类型的告警
        alert = Alert(
            id="alert_004",
            type="resource_exhausted",
            message="Memory usage exceeded 90%",
            severity="critical",
            created_at=time.time(),
        )

        handler.handle_alert(alert)

        failures = maintainer.get_failures()
        assert len(failures) == 1
        assert failures[0].failure_category == FailureCategory.RESOURCE_EXHAUSTED

    def test_handle_timeout_alert(self):
        """测试：处理超时类型告警"""
        from src.domain.services.dynamic_node_monitoring import Alert
        from src.domain.services.knowledge_maintenance import (
            FailureCategory,
            KnowledgeMaintainer,
        )
        from src.domain.services.monitoring_knowledge_bridge import (
            AlertKnowledgeHandler,
        )

        maintainer = KnowledgeMaintainer()
        handler = AlertKnowledgeHandler(maintainer)

        alert = Alert(
            id="alert_005",
            type="execution_timeout",
            message="Workflow execution timeout after 30s",
            severity="critical",
            created_at=time.time(),
        )

        handler.handle_alert(alert)

        failures = maintainer.get_failures()
        assert len(failures) == 1
        assert failures[0].failure_category == FailureCategory.TIMEOUT


# ==================== 3. PerformanceKnowledgeAdapter 测试 ====================


class TestPerformanceKnowledgeAdapter:
    """性能知识适配器测试"""

    def test_adapter_initialization(self):
        """测试：适配器初始化"""
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import (
            PerformanceKnowledgeAdapter,
        )

        maintainer = KnowledgeMaintainer()
        adapter = PerformanceKnowledgeAdapter(maintainer)

        assert adapter is not None
        assert adapter.knowledge_maintainer is maintainer

    def test_process_bottleneck_creates_failure_case(self):
        """测试：处理瓶颈创建失败案例"""
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.log_analysis import Bottleneck
        from src.domain.services.monitoring_knowledge_bridge import (
            PerformanceKnowledgeAdapter,
        )

        maintainer = KnowledgeMaintainer()
        adapter = PerformanceKnowledgeAdapter(maintainer)

        bottleneck = Bottleneck(
            operation="llm_call",
            service="llm_executor",
            avg_duration_ms=5000,
            p95_duration_ms=8000,
            occurrence_count=50,
            suggestion="考虑使用更快的模型或减少 token 数量",
        )

        result = adapter.process_bottleneck(bottleneck)

        assert result["success"] is True
        assert maintainer.failure_count == 1

    def test_process_bottleneck_preserves_suggestion(self):
        """测试：处理瓶颈时保留优化建议"""
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.log_analysis import Bottleneck
        from src.domain.services.monitoring_knowledge_bridge import (
            PerformanceKnowledgeAdapter,
        )

        maintainer = KnowledgeMaintainer()
        adapter = PerformanceKnowledgeAdapter(maintainer)

        bottleneck = Bottleneck(
            operation="database_query",
            service="database",
            avg_duration_ms=3000,
            p95_duration_ms=6000,
            occurrence_count=100,
            suggestion="考虑添加数据库索引或优化查询语句",
        )

        adapter.process_bottleneck(bottleneck)

        failures = maintainer.get_failures()
        assert len(failures) == 1
        assert "索引" in failures[0].prevention_strategy[0] or "优化" in failures[0].lesson_learned

    def test_process_multiple_bottlenecks(self):
        """测试：批量处理多个瓶颈"""
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.log_analysis import Bottleneck
        from src.domain.services.monitoring_knowledge_bridge import (
            PerformanceKnowledgeAdapter,
        )

        maintainer = KnowledgeMaintainer()
        adapter = PerformanceKnowledgeAdapter(maintainer)

        bottlenecks = [
            Bottleneck(
                operation="llm_call",
                service="llm_executor",
                avg_duration_ms=5000,
                p95_duration_ms=8000,
                occurrence_count=50,
                suggestion="使用更快模型",
            ),
            Bottleneck(
                operation="http_request",
                service="api_client",
                avg_duration_ms=2000,
                p95_duration_ms=5000,
                occurrence_count=30,
                suggestion="添加缓存",
            ),
        ]

        results = adapter.process_bottlenecks(bottlenecks)

        assert len(results) == 2
        assert maintainer.failure_count == 2

    def test_record_successful_pattern(self):
        """测试：记录成功的执行模式"""
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import (
            PerformanceKnowledgeAdapter,
        )

        maintainer = KnowledgeMaintainer()
        adapter = PerformanceKnowledgeAdapter(maintainer)

        pattern = {
            "task_type": "data_processing",
            "description": "批量数据处理优化方案",
            "steps": ["分片处理", "并行执行", "结果合并"],
            "metrics": {"avg_duration_ms": 500, "success_rate": 0.99},
            "context": {"data_size": "large", "parallelism": 4},
        }

        result = adapter.record_successful_pattern(pattern)

        assert result["success"] is True
        assert maintainer.solution_count == 1


# ==================== 4. MetricsKnowledgeCollector 测试 ====================


class TestMetricsKnowledgeCollector:
    """指标知识收集器测试"""

    def test_collector_initialization(self):
        """测试：收集器初始化"""
        from src.domain.services.dynamic_node_monitoring import DynamicNodeMetricsCollector
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import (
            MetricsKnowledgeCollector,
        )

        maintainer = KnowledgeMaintainer()
        metrics_collector = DynamicNodeMetricsCollector()

        collector = MetricsKnowledgeCollector(
            knowledge_maintainer=maintainer,
            metrics_collector=metrics_collector,
        )

        assert collector is not None

    def test_analyze_and_record_frequent_failures(self):
        """测试：分析并记录频繁失败"""
        from src.domain.services.dynamic_node_monitoring import DynamicNodeMetricsCollector
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import (
            MetricsKnowledgeCollector,
        )

        maintainer = KnowledgeMaintainer()
        metrics_collector = DynamicNodeMetricsCollector()

        # 模拟多次失败
        for _ in range(10):
            metrics_collector.record_node_creation("problematic_node", success=False)

        collector = MetricsKnowledgeCollector(
            knowledge_maintainer=maintainer,
            metrics_collector=metrics_collector,
        )

        result = collector.analyze_and_record_failures(threshold=5)

        assert result["failures_recorded"] >= 1
        assert maintainer.failure_count >= 1

    def test_analyze_and_record_successful_workflows(self):
        """测试：分析并记录成功的工作流模式"""
        from src.domain.services.dynamic_node_monitoring import DynamicNodeMetricsCollector
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import (
            MetricsKnowledgeCollector,
        )

        maintainer = KnowledgeMaintainer()
        metrics_collector = DynamicNodeMetricsCollector()

        # 模拟多次成功执行
        for i in range(10):
            metrics_collector.record_workflow_execution(
                workflow_name="efficient_workflow",
                success=True,
                duration_ms=500 + i * 10,
                node_count=5,
            )

        collector = MetricsKnowledgeCollector(
            knowledge_maintainer=maintainer,
            metrics_collector=metrics_collector,
        )

        result = collector.analyze_and_record_successes(min_success_count=5)

        assert result["solutions_recorded"] >= 1
        assert maintainer.solution_count >= 1


# ==================== 5. 闭环场景集成测试 ====================


class TestClosedLoopIntegration:
    """闭环场景集成测试"""

    def test_full_alert_to_knowledge_loop(self):
        """测试：完整的告警→知识库闭环"""
        from src.domain.services.dynamic_node_monitoring import AlertManager
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            SolutionRetriever,
        )
        from src.domain.services.monitoring_knowledge_bridge import (
            MonitoringKnowledgeBridge,
        )

        # 1. 初始化组件
        maintainer = KnowledgeMaintainer()
        alert_manager = AlertManager()
        alert_manager.set_threshold("sandbox_failure_rate", 0.3)

        # 2. 创建桥接器（自动注册回调）
        _bridge = MonitoringKnowledgeBridge(
            knowledge_maintainer=maintainer,
            alert_manager=alert_manager,
        )

        # 3. 触发告警
        alert_manager.check_failure_rate(0.6)

        # 4. 验证知识库已更新
        assert maintainer.failure_count == 1

        # 5. 验证可以检索到相关失败案例
        retriever = SolutionRetriever(maintainer)
        warning = retriever.check_known_failure(
            task_type="sandbox_execution",
            task_description="执行沙箱任务",
            potential_error="failure rate",
        )

        assert warning is not None

    def test_metrics_to_knowledge_loop(self):
        """测试：指标→知识库闭环"""
        from src.domain.services.dynamic_node_monitoring import DynamicNodeMetricsCollector
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            SolutionRetriever,
        )
        from src.domain.services.monitoring_knowledge_bridge import (
            MetricsKnowledgeCollector,
        )

        # 1. 初始化组件
        maintainer = KnowledgeMaintainer()
        metrics_collector = DynamicNodeMetricsCollector()

        # 2. 模拟工作流执行
        for _ in range(10):
            metrics_collector.record_workflow_execution(
                workflow_name="data_pipeline",
                success=True,
                duration_ms=1000,
                node_count=5,
            )

        # 3. 创建收集器并分析
        collector = MetricsKnowledgeCollector(
            knowledge_maintainer=maintainer,
            metrics_collector=metrics_collector,
        )
        collector.analyze_and_record_successes(min_success_count=5)

        # 4. 验证可以检索到成功方案
        retriever = SolutionRetriever(maintainer)
        solutions = retriever.find_similar_solutions(
            task_type="workflow_execution",
            task_description="数据管道执行",
            context={},
        )

        assert len(solutions) >= 1

    def test_bottleneck_to_knowledge_loop(self):
        """测试：瓶颈检测→知识库闭环"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            SolutionRetriever,
        )
        from src.domain.services.log_analysis import Bottleneck
        from src.domain.services.monitoring_knowledge_bridge import (
            PerformanceKnowledgeAdapter,
        )

        # 1. 初始化组件
        maintainer = KnowledgeMaintainer()
        adapter = PerformanceKnowledgeAdapter(maintainer)

        # 2. 处理瓶颈
        bottleneck = Bottleneck(
            operation="slow_query",
            service="database",
            avg_duration_ms=5000,
            p95_duration_ms=10000,
            occurrence_count=100,
            suggestion="添加索引或优化查询",
        )
        adapter.process_bottleneck(bottleneck)

        # 3. 验证可以检索到相关失败案例
        # 使用与实现生成的描述相似的查询文本
        retriever = SolutionRetriever(maintainer)
        warning = retriever.check_known_failure(
            task_type="performance_bottleneck",
            task_description="database 服务的操作性能瓶颈",
        )

        assert warning is not None
        assert len(warning.prevention_strategy) > 0

    def test_continuous_learning_from_alerts(self):
        """测试：从告警中持续学习"""
        from src.domain.services.dynamic_node_monitoring import AlertManager
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import (
            MonitoringKnowledgeBridge,
        )

        maintainer = KnowledgeMaintainer()
        alert_manager = AlertManager()
        alert_manager.set_threshold("sandbox_failure_rate", 0.3)

        _bridge = MonitoringKnowledgeBridge(
            knowledge_maintainer=maintainer,
            alert_manager=alert_manager,
        )

        # 第一次告警
        alert_manager.check_failure_rate(0.5)
        initial_count = maintainer.failure_count

        # 清除告警后再次触发
        alert_manager.clear_all_alerts()
        alert_manager.check_failure_rate(0.7)

        # 应该记录新的失败案例
        assert maintainer.failure_count > initial_count

    def test_alert_triggers_task_creation(self):
        """测试：告警触发任务创建"""
        from src.domain.services.dynamic_node_monitoring import AlertManager
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import (
            MonitoringKnowledgeBridge,
        )

        maintainer = KnowledgeMaintainer()
        alert_manager = AlertManager()
        alert_manager.set_threshold("sandbox_failure_rate", 0.3)

        # 创建带任务回调的桥接器
        created_tasks = []

        def task_callback(task_info: dict):
            created_tasks.append(task_info)

        _bridge = MonitoringKnowledgeBridge(
            knowledge_maintainer=maintainer,
            alert_manager=alert_manager,
            task_creation_callback=task_callback,
        )

        # 触发严重告警
        alert_manager.check_failure_rate(0.8)

        # 验证任务被创建
        assert len(created_tasks) >= 1
        assert created_tasks[0]["priority"] == "high"


# ==================== 6. 日志记录测试 ====================


class TestLoggingIntegration:
    """日志记录集成测试"""

    def test_bridge_logs_alert_processing(self):
        """测试：桥接器记录告警处理日志"""
        from src.domain.services.dynamic_node_monitoring import AlertManager
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import (
            MonitoringKnowledgeBridge,
        )

        maintainer = KnowledgeMaintainer()
        alert_manager = AlertManager()
        alert_manager.set_threshold("sandbox_failure_rate", 0.3)

        bridge = MonitoringKnowledgeBridge(
            knowledge_maintainer=maintainer,
            alert_manager=alert_manager,
        )

        # 触发告警
        alert_manager.check_failure_rate(0.5)

        # 验证处理日志
        logs = bridge.get_processing_logs()
        assert len(logs) >= 1
        assert "alert" in logs[0]["event_type"].lower()

    def test_adapter_logs_bottleneck_processing(self):
        """测试：适配器记录瓶颈处理日志"""
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.log_analysis import Bottleneck
        from src.domain.services.monitoring_knowledge_bridge import (
            PerformanceKnowledgeAdapter,
        )

        maintainer = KnowledgeMaintainer()
        adapter = PerformanceKnowledgeAdapter(maintainer)

        bottleneck = Bottleneck(
            operation="test_op",
            service="test_service",
            avg_duration_ms=3000,
            p95_duration_ms=5000,
            occurrence_count=10,
            suggestion="测试建议",
        )

        adapter.process_bottleneck(bottleneck)

        logs = adapter.get_processing_logs()
        assert len(logs) >= 1
        assert "bottleneck" in logs[0]["event_type"].lower()


# ==================== 7. 边界条件测试 ====================


class TestEdgeCases:
    """边界条件测试"""

    def test_handle_empty_alert_message(self):
        """测试：处理空消息告警"""
        from src.domain.services.dynamic_node_monitoring import Alert
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import (
            AlertKnowledgeHandler,
        )

        maintainer = KnowledgeMaintainer()
        handler = AlertKnowledgeHandler(maintainer)

        alert = Alert(
            id="alert_empty",
            type="unknown",
            message="",
            severity="warning",
            created_at=time.time(),
        )

        result = handler.handle_alert(alert)

        # 应该优雅处理，不抛异常
        assert result["success"] is True

    def test_handle_unknown_alert_type(self):
        """测试：处理未知告警类型"""
        from src.domain.services.dynamic_node_monitoring import Alert
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import (
            AlertKnowledgeHandler,
        )

        maintainer = KnowledgeMaintainer()
        handler = AlertKnowledgeHandler(maintainer)

        alert = Alert(
            id="alert_unknown",
            type="completely_unknown_type",
            message="Some unknown alert",
            severity="critical",
            created_at=time.time(),
        )

        result = handler.handle_alert(alert)

        # 应该使用默认处理逻辑
        assert result["success"] is True
        assert maintainer.failure_count == 1

    def test_process_bottleneck_with_zero_duration(self):
        """测试：处理零耗时瓶颈"""
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.log_analysis import Bottleneck
        from src.domain.services.monitoring_knowledge_bridge import (
            PerformanceKnowledgeAdapter,
        )

        maintainer = KnowledgeMaintainer()
        adapter = PerformanceKnowledgeAdapter(maintainer)

        bottleneck = Bottleneck(
            operation="fast_op",
            service="fast_service",
            avg_duration_ms=0,
            p95_duration_ms=0,
            occurrence_count=0,
            suggestion="",
        )

        result = adapter.process_bottleneck(bottleneck)

        # 应该优雅处理
        assert result["success"] is True

    def test_bridge_without_task_callback(self):
        """测试：无任务回调的桥接器"""
        from src.domain.services.dynamic_node_monitoring import AlertManager
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import (
            MonitoringKnowledgeBridge,
        )

        maintainer = KnowledgeMaintainer()
        alert_manager = AlertManager()
        alert_manager.set_threshold("sandbox_failure_rate", 0.3)

        # 不传入 task_creation_callback
        _bridge = MonitoringKnowledgeBridge(
            knowledge_maintainer=maintainer,
            alert_manager=alert_manager,
        )

        # 触发告警，不应该抛异常
        alert_manager.check_failure_rate(0.8)

        assert maintainer.failure_count == 1
