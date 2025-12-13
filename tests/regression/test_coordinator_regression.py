"""Coordinator 回归测试套件 (Regression Test Suite) - Step 10

回归测试覆盖范围：
1. 监督模块 (Supervision) - 内容过滤、安全检测、效率监控
2. 管理模块 (Management) - 资源调度、生命周期管理、日志告警
3. 知识模块 (Knowledge) - 知识维护、检索、监控集成
4. 日志模块 (Logging) - 结构化日志、分析、审计

执行方式：
    pytest tests/regression/test_coordinator_regression.py -v --tb=short

CI 集成：
    pytest tests/regression/ -v --junitxml=reports/regression_report.xml
"""

import time
from datetime import datetime, timedelta

# ==================== 1. 监督模块回归测试 ====================


class TestSupervisionModuleRegression:
    """监督模块回归测试"""

    def test_conversation_supervision_bias_detection(self):
        """回归测试：对话监督偏见检测"""
        from src.domain.services.supervision import ConversationSupervisionModule

        module = ConversationSupervisionModule()

        # 测试偏见检测 - 中文模式
        bias_result = module.check_bias("只有男性才能做技术工作")
        assert bias_result.detected is True
        assert "gender" in bias_result.category.lower()

        # 测试无偏见内容
        safe_result = module.check_bias("工程师完成了任务")
        assert safe_result.detected is False

    def test_conversation_supervision_harmful_content(self):
        """回归测试：对话监督有害内容检测"""
        from src.domain.services.supervision import ConversationSupervisionModule

        module = ConversationSupervisionModule()

        # 测试有害内容检测
        harmful_result = module.check_harmful_content("如何制造武器")
        assert harmful_result.detected is True

        # 测试安全内容
        safe_result = module.check_harmful_content("正常的业务讨论")
        assert safe_result.detected is False

    def test_conversation_supervision_stability(self):
        """回归测试：对话监督稳定性检测"""
        from src.domain.services.supervision import ConversationSupervisionModule

        module = ConversationSupervisionModule()

        # 测试正常输入
        normal_result = module.check_stability("请帮我写一个函数")
        assert normal_result.detected is False

        # 测试上下文溢出
        overflow_text = "x" * 60000
        overflow_result = module.check_stability(overflow_text)
        assert overflow_result.detected is True

    def test_conversation_supervision_comprehensive_check(self):
        """回归测试：对话监督综合检查"""
        from src.domain.services.supervision import ConversationSupervisionModule

        module = ConversationSupervisionModule()

        # 综合检查 - 使用 check_all 方法
        result = module.check_all("正常的技术讨论内容")
        assert result.passed is True
        assert len(result.issues) == 0

    def test_workflow_efficiency_monitor(self):
        """回归测试：工作流效率监控"""
        from src.domain.services.supervision import WorkflowEfficiencyMonitor

        monitor = WorkflowEfficiencyMonitor()

        # 记录资源使用 - 使用 record_resource_usage
        monitor.record_resource_usage(
            workflow_id="wf_001",
            node_id="node_001",
            memory_mb=100.0,
            cpu_percent=50.0,
            duration_seconds=1.0,
        )
        monitor.record_resource_usage(
            workflow_id="wf_001",
            node_id="node_002",
            memory_mb=2500.0,  # 超过阈值
            cpu_percent=95.0,  # 超过阈值
            duration_seconds=2.0,
        )

        # 检查告警
        alerts = monitor.check_thresholds("wf_001")
        assert len(alerts) >= 1  # 应该有超阈值告警

    def test_strategy_repository_crud(self):
        """回归测试：策略仓库 CRUD"""
        from src.domain.services.supervision import StrategyRepository

        repo = StrategyRepository()

        # 注册策略 - 使用 register 方法
        strategy_id = repo.register(
            name="test_strategy",
            trigger_conditions=["bias_detected"],
            action="warn",
            priority=10,
        )
        assert strategy_id is not None

        # 获取策略 - 使用 get 方法
        strategy = repo.get(strategy_id)
        assert strategy is not None
        assert strategy["name"] == "test_strategy"

        # 列出策略 - 使用 list_all 方法
        strategies = repo.list_all()
        assert len(strategies) >= 1

    def test_supervision_coordinator_flow(self):
        """回归测试：监督协调器流程"""
        from src.domain.services.supervision import SupervisionCoordinator

        coordinator = SupervisionCoordinator()

        # 测试终止流程
        result = coordinator.initiate_termination(
            task_id="task_001",
            reason="测试终止",
            severity="high",
            graceful=True,
        )
        assert result.success is True

        # 验证终止事件被记录
        events = coordinator.get_termination_events()
        assert len(events) >= 1


# ==================== 2. 管理模块回归测试 ====================


class TestManagementModuleRegression:
    """管理模块回归测试"""

    def test_priority_scheduler(self):
        """回归测试：优先级调度器"""
        from src.domain.services.management_modules import PriorityScheduler, ScheduleRequest

        scheduler = PriorityScheduler()

        # 创建调度请求 - 使用 id 字段
        requests = [
            ScheduleRequest(id="agent_1", priority=5, agent_type="analysis"),
            ScheduleRequest(id="agent_2", priority=1, agent_type="urgent"),  # 最高优先级
            ScheduleRequest(id="agent_3", priority=10, agent_type="background"),
        ]

        # 入队
        for req in requests:
            scheduler.enqueue(req)

        # 出队验证优先级顺序
        first = scheduler.dequeue()
        assert first is not None
        assert first.id == "agent_2"  # 优先级1最高，先出队

    def test_resource_scheduler(self):
        """回归测试：资源调度器"""
        from src.domain.services.management_modules import (
            LoadMetrics,
            ResourceScheduler,
            ScheduleRequest,
        )

        scheduler = ResourceScheduler()

        # 设置资源状态 - 使用 update_load 和 LoadMetrics
        scheduler.update_load(LoadMetrics(cpu_percent=50.0, memory_percent=60.0, queue_length=2))

        # 创建调度请求
        request = ScheduleRequest(
            id="agent_1",
            priority=5,
            agent_type="analysis",
            resource_requirement={"cpu_cores": 2, "memory_mb": 1024},
        )

        # 调度
        result = scheduler.schedule(request)
        assert result.scheduled is True

    def test_agent_lifecycle_manager(self):
        """回归测试：Agent 生命周期管理"""
        from src.domain.services.management_modules import AgentLifecycleManager

        manager = AgentLifecycleManager()

        # 创建 Agent - 使用位置参数
        instance = manager.create_agent(
            "test_agent_001",
            "workflow_agent",
            {"name": "test_agent"},
        )
        assert instance is not None
        assert instance.agent_id == "test_agent_001"

        # 获取 Agent
        agent = manager.get_agent("test_agent_001")
        assert agent is not None

        # 启动 Agent
        start_result = manager.start_agent("test_agent_001")
        assert start_result.success is True

        # 停止 Agent
        stop_result = manager.stop_agent("test_agent_001")
        assert stop_result.success is True

    def test_log_collector(self):
        """回归测试：日志收集器"""
        from src.domain.services.management_modules import LogCollector, LogLevel

        collector = LogCollector()

        # 记录日志 - 位置参数
        collector.log(LogLevel.INFO, "test", "Test info message")
        collector.log(LogLevel.WARN, "test", "Test warning")
        collector.log(LogLevel.ERROR, "test", "Test error")

        # 查询日志
        all_logs = collector.query()
        assert len(all_logs) >= 3

        # 按级别查询
        errors = collector.query(level=LogLevel.ERROR)
        assert len(errors) >= 1

    def test_alert_handler(self):
        """回归测试：告警处理器"""
        from src.domain.services.management_modules import AlertHandler, AlertLevel

        handler = AlertHandler(suppression_seconds=0)

        # 添加告警规则 - 使用 callable 条件
        def high_cpu_condition(metrics: dict) -> bool:
            return metrics.get("cpu_percent", 0) > 80

        rule_id = handler.add_rule(
            name="High CPU Alert",
            condition=high_cpu_condition,
            level=AlertLevel.WARNING,
            message="CPU 使用率过高",
        )
        assert rule_id is not None

        # 评估规则并生成告警
        metrics = {"cpu_percent": 90}
        alerts = handler.evaluate(metrics)
        assert len(alerts) >= 1

        # 确认告警
        if alerts:
            ack_result = handler.acknowledge(alerts[0].id)
            assert ack_result.success is True


# ==================== 3. 知识模块回归测试 ====================


class TestKnowledgeModuleRegression:
    """知识模块回归测试"""

    def test_knowledge_crud_operations(self):
        """回归测试：知识库 CRUD 操作"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            MemoryCategory,
            PreferenceType,
        )

        maintainer = KnowledgeMaintainer()

        # Create - 添加记忆
        memory_id = maintainer.add_memory(
            category=MemoryCategory.FACT,
            content="项目使用 Python 3.11",
            source="config",
            confidence=1.0,
        )
        assert memory_id is not None
        assert maintainer.memory_count == 1

        # Read - 获取记忆
        memory = maintainer.get_memory(memory_id)
        assert memory is not None
        assert memory.content == "项目使用 Python 3.11"

        # Search - 搜索记忆
        results = maintainer.search_memories("Python")
        assert len(results) >= 1

        # 添加偏好
        pref_id = maintainer.add_preference(
            user_id="user_001",
            preference_type=PreferenceType.CODING_STYLE,
            key="indentation",
            value="4_spaces",
        )
        assert pref_id is not None

    def test_solution_retrieval_pipeline(self):
        """回归测试：解法检索管道"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            SolutionRetriever,
        )

        maintainer = KnowledgeMaintainer()
        retriever = SolutionRetriever(maintainer)

        # 记录成功解法
        maintainer.record_success(
            task_type="data_analysis",
            task_description="分析用户行为数据",
            workflow_id="wf_analysis_001",
            solution_steps=["获取数据", "清洗", "分析", "报告"],
            success_metrics={"accuracy": 0.95},
            context={"domain": "analytics"},
        )

        # 查找相似解法
        solutions = retriever.find_similar_solutions(
            task_type="data_analysis",
            task_description="分析销售数据",
            context={"domain": "analytics"},
        )
        assert len(solutions) >= 1

        # 获取最佳解法
        best = retriever.get_best_solution("data_analysis", "accuracy")
        assert best is not None
        assert best.success_metrics["accuracy"] >= 0.9

    def test_failure_case_prevention(self):
        """回归测试：失败案例预防"""
        from src.domain.services.knowledge_maintenance import (
            FailureCategory,
            KnowledgeMaintainer,
            SolutionRetriever,
        )

        maintainer = KnowledgeMaintainer()
        retriever = SolutionRetriever(maintainer)

        # 记录失败案例
        maintainer.record_failure(
            task_type="api_integration",
            task_description="调用支付 API",
            workflow_id="wf_payment_001",
            failure_category=FailureCategory.TIMEOUT,
            error_message="Connection timeout",
            root_cause="未设置超时",
            lesson_learned="必须设置合理超时",
            prevention_strategy=["设置超时", "添加重试"],
        )

        # 检查已知失败
        warning = retriever.check_known_failure(
            task_type="api_integration",
            task_description="调用订单 API",
            potential_error="timeout",
        )
        assert warning is not None
        assert len(warning.prevention_strategy) >= 1

    def test_monitoring_knowledge_integration(self):
        """回归测试：监控-知识集成"""
        from src.domain.services.dynamic_node_monitoring import AlertManager
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import (
            MonitoringKnowledgeBridge,
        )

        maintainer = KnowledgeMaintainer()
        alert_manager = AlertManager()
        alert_manager.set_threshold("sandbox_failure_rate", 0.3)

        # 创建桥接器
        _bridge = MonitoringKnowledgeBridge(
            knowledge_maintainer=maintainer,
            alert_manager=alert_manager,
        )

        # 触发告警
        alert_manager.check_failure_rate(0.5)

        # 验证知识库更新
        assert maintainer.failure_count >= 1


# ==================== 4. 日志模块回归测试 ====================


class TestLoggingModuleRegression:
    """日志模块回归测试"""

    def test_structured_log_storage(self):
        """回归测试：结构化日志存储"""
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
        )

        store = InMemoryLogStore()

        # 创建日志
        log = StructuredLog(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            message="Test message",
            source="test",
            event_type="test_event",
        )
        store.write(log)  # 使用 write 方法

        # 验证存储
        assert store.count >= 1

        # 查询
        logs = store.query(level=LogLevel.INFO)
        assert len(logs) >= 1

    def test_trace_context_propagation(self):
        """回归测试：追踪上下文传播"""
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
            TraceContext,
        )

        store = InMemoryLogStore()

        # 创建带追踪的日志
        trace = TraceContext(trace_id="trace_001", span_id="span_001")
        log = StructuredLog(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            message="Traced message",
            source="test",
            event_type="test",
            trace=trace,
        )
        store.write(log)  # 使用 write 方法

        # 按追踪 ID 查询
        logs = store.query(trace_id="trace_001")
        assert len(logs) >= 1
        assert logs[0].trace.trace_id == "trace_001"

    def test_log_analysis_bottleneck_detection(self):
        """回归测试：日志分析瓶颈检测"""
        from src.domain.services.log_analysis import (
            PerformanceAnalyzer,
            TaskTrace,
            TraceSpan,
        )

        perf_analyzer = PerformanceAnalyzer(bottleneck_threshold_ms=1000)

        # 创建模拟追踪
        now = datetime.now()
        trace = TaskTrace(
            trace_id="trace_perf_001",
            user_input="Test task",
            started_at=now,
        )

        # 添加慢操作
        trace.add_span(
            TraceSpan(
                span_id="span_slow",
                parent_span_id=None,
                operation="slow_query",
                service="database",
                start_time=now,
                end_time=now + timedelta(milliseconds=3000),
            )
        )

        trace.complete(now + timedelta(milliseconds=3000))

        # 检测瓶颈
        bottlenecks = perf_analyzer.find_bottlenecks([trace])
        assert len(bottlenecks) >= 1
        assert bottlenecks[0].avg_duration_ms >= 1000

    def test_audit_report_generation(self):
        """回归测试：审计报告生成"""
        from src.domain.services.log_analysis import AuditReportGenerator
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
            TraceContext,
        )

        store = InMemoryLogStore()

        # 生成一些日志
        trace = TraceContext(trace_id="audit_trace_001", span_id="span_001")
        store.write(
            StructuredLog(
                timestamp=datetime.now(),
                level=LogLevel.INFO,
                message="Task started",
                source="test",
                event_type="task_started",
                trace=trace,
            )
        )
        store.write(
            StructuredLog(
                timestamp=datetime.now(),
                level=LogLevel.INFO,
                message="Task completed",
                source="test",
                event_type="task_completed",
                trace=trace,
            )
        )

        # 生成审计报告
        generator = AuditReportGenerator(log_store=store)
        report = generator.generate_report(
            start_time=datetime.now() - timedelta(hours=1),
            end_time=datetime.now() + timedelta(hours=1),
        )

        assert "summary" in report
        assert "report_id" in report


# ==================== 5. 端到端集成测试 ====================


class TestEndToEndRegression:
    """端到端集成回归测试"""

    def test_alert_to_knowledge_to_retrieval_flow(self):
        """回归测试：告警→知识→检索完整流程"""
        from src.domain.services.dynamic_node_monitoring import AlertManager
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            SolutionRetriever,
        )
        from src.domain.services.monitoring_knowledge_bridge import (
            MonitoringKnowledgeBridge,
        )

        # Step 1: 初始化系统
        maintainer = KnowledgeMaintainer()
        alert_manager = AlertManager()
        alert_manager.set_threshold("sandbox_failure_rate", 0.3)
        _retriever = SolutionRetriever(maintainer)

        # Step 2: 创建桥接器
        _bridge = MonitoringKnowledgeBridge(
            knowledge_maintainer=maintainer,
            alert_manager=alert_manager,
        )

        # Step 3: 触发告警
        alert_manager.check_failure_rate(0.6)

        # Step 4: 验证知识库已更新
        assert maintainer.failure_count >= 1

        # Step 5: 验证可以检索到失败案例（使用更宽松的查询）
        failures = maintainer.get_failures()
        assert len(failures) >= 1

    def test_metrics_to_bottleneck_to_knowledge_flow(self):
        """回归测试：指标→瓶颈→知识完整流程"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            SolutionRetriever,
        )
        from src.domain.services.log_analysis import Bottleneck
        from src.domain.services.monitoring_knowledge_bridge import (
            PerformanceKnowledgeAdapter,
        )

        # Step 1: 初始化
        maintainer = KnowledgeMaintainer()
        adapter = PerformanceKnowledgeAdapter(maintainer)
        retriever = SolutionRetriever(maintainer)

        # Step 2: 处理瓶颈
        bottleneck = Bottleneck(
            operation="slow_query",
            service="database",
            avg_duration_ms=5000,
            p95_duration_ms=10000,
            occurrence_count=100,
            suggestion="添加索引",
        )
        adapter.process_bottleneck(bottleneck)

        # Step 3: 验证知识库更新
        assert maintainer.failure_count >= 1

        # Step 4: 验证可以检索
        warning = retriever.check_known_failure(
            task_type="performance_bottleneck",
            task_description="database 服务性能瓶颈",
        )
        assert warning is not None

    def test_supervision_comprehensive_flow(self):
        """回归测试：监督综合检查流程"""
        from src.domain.services.supervision import (
            ConversationSupervisionModule,
            SupervisionCoordinator,
        )

        # Step 1: 初始化
        module = ConversationSupervisionModule()
        _coordinator = SupervisionCoordinator()

        # Step 2: 检测安全内容 - 使用 check_all
        safe_result = module.check_all("正常的技术讨论")
        assert safe_result.passed is True

        # Step 3: 检测不安全内容
        unsafe_result = module.check_harmful_content("如何制造武器")
        assert unsafe_result.detected is True

    def test_logging_to_analysis_flow(self):
        """回归测试：日志→分析流程"""
        from src.domain.services.log_analysis import (
            AuditReportGenerator,
        )
        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
            TraceContext,
        )

        # Step 1: 初始化
        store = InMemoryLogStore()

        # Step 2: 记录日志 - 使用 write 方法
        trace = TraceContext(trace_id="e2e_trace", span_id="span_001")
        store.write(
            StructuredLog(
                timestamp=datetime.now(),
                level=LogLevel.INFO,
                message="Task started",
                source="test",
                event_type="task_started",
                trace=trace,
            )
        )
        time.sleep(0.01)
        store.write(
            StructuredLog(
                timestamp=datetime.now(),
                level=LogLevel.INFO,
                message="Task completed",
                source="test",
                event_type="task_completed",
                trace=trace,
            )
        )

        # Step 3: 生成报告
        generator = AuditReportGenerator(log_store=store)
        report = generator.generate_report(
            start_time=datetime.now() - timedelta(hours=1),
            end_time=datetime.now() + timedelta(hours=1),
        )

        # Step 4: 验证报告
        assert report["summary"]["total_logs"] >= 2


# ==================== 6. 配置验证测试 ====================


class TestConfigurationRegression:
    """配置验证回归测试"""

    def test_supervision_module_has_default_rules(self):
        """回归测试：监督模块有默认规则"""
        from src.domain.services.supervision import ConversationSupervisionModule

        module = ConversationSupervisionModule()

        # 验证默认规则存在
        assert len(module.rules) > 0
        assert any("bias" in rule_id for rule_id in module.rules)

    def test_alert_manager_threshold_configuration(self):
        """回归测试：告警管理器阈值配置"""
        from src.domain.services.dynamic_node_monitoring import AlertManager

        manager = AlertManager()

        # 设置阈值
        manager.set_threshold("sandbox_failure_rate", 0.3)

        # 低于阈值不触发告警
        manager.check_failure_rate(0.2)
        assert len(manager.get_active_alerts()) == 0

        # 高于阈值触发告警
        manager.check_failure_rate(0.5)
        assert len(manager.get_active_alerts()) >= 1

    def test_knowledge_similarity_threshold(self):
        """回归测试：知识相似度阈值"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            SolutionRetriever,
        )

        maintainer = KnowledgeMaintainer()
        retriever = SolutionRetriever(maintainer)

        # 添加解法
        maintainer.record_success(
            task_type="test_type",
            task_description="Test description",
            workflow_id="wf_001",
            solution_steps=["step1"],
            success_metrics={"score": 0.9},
        )

        # 高相似度查询
        results = retriever.find_similar_solutions(
            task_type="test_type",
            task_description="Test description",
            context={},
            min_similarity=0.3,
        )
        assert len(results) >= 1


# ==================== 7. 异常处理测试 ====================


class TestExceptionHandlingRegression:
    """异常处理回归测试"""

    def test_knowledge_maintainer_handles_invalid_input(self):
        """回归测试：知识维护器处理无效输入"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            MemoryCategory,
        )

        maintainer = KnowledgeMaintainer()

        # 空内容应该能处理
        memory_id = maintainer.add_memory(
            category=MemoryCategory.FACT,
            content="",
            source="test",
            confidence=0.5,
        )
        assert memory_id is not None

    def test_alert_handler_handles_unknown_type(self):
        """回归测试：告警处理器处理未知类型"""
        from src.domain.services.dynamic_node_monitoring import Alert
        from src.domain.services.knowledge_maintenance import KnowledgeMaintainer
        from src.domain.services.monitoring_knowledge_bridge import AlertKnowledgeHandler

        maintainer = KnowledgeMaintainer()
        handler = AlertKnowledgeHandler(maintainer)

        # 未知告警类型
        alert = Alert(
            id="unknown_001",
            type="completely_unknown_type",
            message="Unknown alert",
            severity="critical",
            created_at=time.time(),
        )

        # 应该优雅处理
        result = handler.handle_alert(alert)
        assert result["success"] is True

    def test_retriever_handles_empty_knowledge_base(self):
        """回归测试：检索器处理空知识库"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            SolutionRetriever,
        )

        maintainer = KnowledgeMaintainer()
        retriever = SolutionRetriever(maintainer)

        # 空知识库查询
        solutions = retriever.find_similar_solutions(
            task_type="any",
            task_description="any",
            context={},
        )
        assert solutions == []


# ==================== 8. 并发安全测试 ====================


class TestConcurrencySafetyRegression:
    """并发安全回归测试"""

    def test_knowledge_maintainer_concurrent_writes(self):
        """回归测试：知识维护器并发写入"""
        import threading

        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            MemoryCategory,
        )

        maintainer = KnowledgeMaintainer()
        errors = []

        def write_memory(thread_id: int):
            try:
                for i in range(10):
                    maintainer.add_memory(
                        category=MemoryCategory.FACT,
                        content=f"Thread {thread_id} memory {i}",
                        source="concurrent_test",
                        confidence=0.8,
                    )
            except Exception as e:
                errors.append(e)

        # 启动多个线程
        threads = [threading.Thread(target=write_memory, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证无错误
        assert len(errors) == 0
        assert maintainer.memory_count == 50

    def test_log_store_concurrent_writes(self):
        """回归测试：日志存储并发写入"""
        import threading

        from src.domain.services.logging_metrics import (
            InMemoryLogStore,
            LogLevel,
            StructuredLog,
        )

        store = InMemoryLogStore()
        errors = []

        def write_logs(thread_id: int):
            try:
                for i in range(10):
                    log = StructuredLog(
                        timestamp=datetime.now(),
                        level=LogLevel.INFO,
                        message=f"Thread {thread_id} log {i}",
                        source="concurrent_test",
                        event_type="test",
                    )
                    store.write(log)  # 使用 write 方法
            except Exception as e:
                errors.append(e)

        # 启动多个线程
        threads = [threading.Thread(target=write_logs, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证无错误
        assert len(errors) == 0
        assert store.count == 50
