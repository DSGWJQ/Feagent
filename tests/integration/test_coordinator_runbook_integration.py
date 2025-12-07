"""
Coordinator Runbook Integration Tests - Step 10

集成测试覆盖：
1. 完整的模板更新工作流
2. 版本切换与监控
3. A/B 测试完整生命周期
4. 上下文调试工作流
5. 日常运维操作流程
6. 异常处置案例应用
7. 回归测试 CI 集成
"""

from datetime import datetime

import pytest

from src.domain.services.coordinator_runbook import (
    ABTestOperation,
    ABTestStrategy,
    ContextDebugOperation,
    CoordinatorRunbook,
    DebugLevel,
    ExceptionCaseManager,
    # Data classes
    OperationRecorder,
    OperationStatus,
    # Enums
    OperationType,
    RollbackStrategy,
    TemplateUpdateOperation,
    VersionSwitchOperation,
)


class TestTemplateUpdateWorkflow:
    """测试模板更新完整工作流"""

    def test_full_template_update_cycle(self):
        """测试完整的模板更新周期：准备 -> 验证 -> 执行 -> 记录"""
        template_op = TemplateUpdateOperation()
        recorder = OperationRecorder()

        # 1. 准备更新
        change = template_op.prepare_update(
            template_id="tpl-system-001",
            module_name="system_prompt",
            new_content="You are an expert AI assistant specializing in {domain}.",
            reason="Add domain specialization",
        )
        assert change.template_id == "tpl-system-001"

        # 2. 验证模板
        validation = template_op.validate_template(
            content=change.new_content,
            required_variables=["domain"],
        )
        assert validation.is_valid is True

        # 3. 执行更新
        record = template_op.execute_update(change, operator="admin")
        assert record.status == OperationStatus.COMPLETED

        # 4. 记录操作
        recorded = recorder.record(
            operation_type=OperationType.TEMPLATE_UPDATE,
            operator="admin",
            description=f"Updated {change.module_name}",
            details={"template_id": change.template_id},
            result={"record_id": record.record_id},
        )
        assert recorded.operation_type == OperationType.TEMPLATE_UPDATE

        # 5. 生成日报
        report = recorder.generate_daily_report()
        assert report["total_operations"] >= 1

    def test_template_update_with_validation_failure(self):
        """测试模板更新验证失败"""
        template_op = TemplateUpdateOperation()

        change = template_op.prepare_update(
            template_id="tpl-task-001",
            module_name="task_prompt",
            new_content="Task: {task_name}",  # 缺少 priority 变量
            reason="Update task template",
        )

        # 验证应该失败
        validation = template_op.validate_template(
            content=change.new_content,
            required_variables=["task_name", "priority"],
        )
        assert validation.is_valid is False
        assert "priority" in validation.missing_variables

    def test_template_update_rollback(self):
        """测试模板更新回滚"""
        template_op = TemplateUpdateOperation()

        # 执行更新
        change = template_op.prepare_update(
            template_id="tpl-rollback-test",
            module_name="test_module",
            new_content="New content",
            reason="Test rollback",
        )
        record = template_op.execute_update(change, operator="admin")

        # 回滚
        rollback_record = template_op.rollback(record.record_id, reason="Test rollback")
        assert rollback_record.status == OperationStatus.ROLLED_BACK


class TestVersionSwitchWorkflow:
    """测试版本切换完整工作流"""

    def test_gradual_version_rollout(self):
        """测试渐进式版本发布"""
        version_op = VersionSwitchOperation()

        # 1. 计划切换
        switch = version_op.plan_switch(
            from_version="1.0.0",
            to_version="2.0.0",
            modules=["system_prompt", "task_prompt", "output_format"],
            strategy=RollbackStrategy.GRADUAL,
        )
        assert switch.rollback_strategy == RollbackStrategy.GRADUAL

        # 2. 获取发布阶段
        stages = version_op.get_rollout_stages(switch)
        assert len(stages) >= 3
        assert stages[0].percentage == 10.0
        assert stages[1].percentage == 50.0
        assert stages[2].percentage == 100.0

        # 3. 执行切换
        record = version_op.execute_switch(switch, operator="devops")
        assert record.status == OperationStatus.COMPLETED

        # 4. 报告正常指标
        version_op.report_metrics(switch.switch_id, error_rate=0.01, latency_ms=120)
        status = version_op.get_switch_status(switch.switch_id)
        assert status == OperationStatus.COMPLETED

    def test_version_switch_auto_rollback(self):
        """测试版本切换自动回滚"""
        version_op = VersionSwitchOperation()

        # 计划带回滚条件的切换
        switch = version_op.plan_switch(
            from_version="1.0.0",
            to_version="2.0.0",
            modules=["system_prompt"],
            strategy=RollbackStrategy.IMMEDIATE,
        )
        switch.rollback_conditions = {"error_rate_threshold": 0.05}

        # 执行切换
        version_op.execute_switch(switch, operator="devops")

        # 报告高错误率，触发回滚
        version_op.report_metrics(switch.switch_id, error_rate=0.10)
        status = version_op.get_switch_status(switch.switch_id)
        assert status == OperationStatus.ROLLED_BACK


class TestABTestWorkflow:
    """测试 A/B 测试完整工作流"""

    def test_complete_ab_test_lifecycle(self):
        """测试完整的 A/B 测试生命周期"""
        ab_op = ABTestOperation()

        # 1. 创建测试
        config = ab_op.create_test(
            name="Prompt Quality Experiment",
            variant_a={"prompt": "You are a helpful assistant.", "version": "1.0"},
            variant_b={"prompt": "You are an expert AI assistant.", "version": "2.0"},
            strategy=ABTestStrategy.RANDOM,
            traffic_split=0.5,
        )
        assert config.name == "Prompt Quality Experiment"

        # 2. 启动测试
        ab_op.start_test(config)

        # 3. 模拟流量分配和指标收集
        variant_counts = {"a": 0, "b": 0}
        for i in range(200):
            variant = ab_op.assign_variant(config.test_id, f"session-{i}")
            variant_counts[variant] += 1

            # 模拟变体 B 有更好的成功率
            success_rate = 0.94 if variant == "a" else 0.97
            ab_op.record_metric(config.test_id, variant, "success", success_rate)

        # 验证流量分配大致均匀
        assert variant_counts["a"] > 50
        assert variant_counts["b"] > 50

        # 4. 获取指标
        metrics = ab_op.get_metrics(config.test_id)
        assert len(metrics["a"]) == variant_counts["a"]
        assert len(metrics["b"]) == variant_counts["b"]

        # 5. 结束测试
        result = ab_op.conclude_test(config.test_id)
        assert result.test_id == config.test_id
        assert result.winner in ["a", "b", "inconclusive"]
        assert result.confidence_level > 0

    def test_weighted_ab_test(self):
        """测试加权 A/B 测试"""
        ab_op = ABTestOperation()

        config = ab_op.create_test(
            name="Gradual Rollout Test",
            variant_a={"version": "stable"},
            variant_b={"version": "canary"},
            strategy=ABTestStrategy.WEIGHTED,
            traffic_split=0.1,
            weights={"a": 0.9, "b": 0.1},
        )

        ab_op.start_test(config)

        # 模拟流量
        variant_counts = {"a": 0, "b": 0}
        for i in range(1000):
            variant = ab_op.assign_variant(config.test_id, f"session-{i}")
            variant_counts[variant] += 1

        # 验证加权分配（允许一定误差）
        assert variant_counts["a"] > variant_counts["b"] * 5


class TestContextDebugWorkflow:
    """测试上下文调试完整工作流"""

    def test_complete_debug_session(self):
        """测试完整的调试会话"""
        debug_op = ContextDebugOperation()

        # 1. 启动调试会话
        session = debug_op.start_session(
            target_session_id="production-sess-001",
            debug_level=DebugLevel.VERBOSE,
            breakpoints=["context_load", "prompt_build", "execution_start"],
        )
        assert session.debug_level == DebugLevel.VERBOSE

        # 2. 设置上下文数据
        debug_op.set_context_data(
            session.session_id,
            {
                "task_id": "task-001",
                "parent_goal": "Analyze sales data",
                "modules": ["system", "task", "output"],
            },
        )

        # 3. 捕获多个快照
        snap1 = debug_op.capture_snapshot(
            session_id=session.session_id,
            checkpoint="context_load",
            context_state={"modules_loaded": 1},
            prompt_state={"length": 100},
        )

        debug_op.capture_snapshot(
            session_id=session.session_id,
            checkpoint="prompt_build",
            context_state={"modules_loaded": 3},
            prompt_state={"length": 500},
        )

        snap3 = debug_op.capture_snapshot(
            session_id=session.session_id,
            checkpoint="execution_start",
            context_state={"modules_loaded": 3, "ready": True},
            prompt_state={"length": 500, "rendered": True},
        )

        # 4. 比较快照
        diff = snap1.compare(snap3)
        assert "context_state" in diff
        assert "prompt_state" in diff

        # 5. 添加追踪事件
        debug_op.add_trace_event(session.session_id, "context_loaded", {"duration_ms": 50})
        debug_op.add_trace_event(session.session_id, "prompt_assembled", {"tokens": 500})
        debug_op.add_trace_event(session.session_id, "llm_invoked", {"model": "gpt-4"})

        # 6. 获取追踪
        trace = debug_op.get_trace(session.session_id)
        assert len(trace) == 3

        # 7. 检查上下文
        inspection = debug_op.inspect_context(session.session_id)
        assert inspection["task_id"] == "task-001"

        # 8. 结束会话
        report = debug_op.end_session(session.session_id)
        assert report["snapshots_count"] == 3
        assert report["trace_events_count"] == 3


class TestDailyOperations:
    """测试日常运维操作"""

    def test_daily_health_check_procedure(self):
        """测试日常健康检查流程"""
        runbook = CoordinatorRunbook()

        # 添加健康检查条目
        entry = runbook.add_entry(
            title="Daily Health Check",
            category="maintenance",
            procedure=[
                "1. Check template validation status",
                "2. Review prompt version consistency",
                "3. Analyze error rate trends",
                "4. Generate health report",
            ],
            estimated_duration_minutes=15,
            required_permissions=["admin", "devops"],
        )

        # 执行流程
        log = runbook.execute_procedure(
            entry_id=entry.entry_id,
            operator="ops-team",
            parameters={"date": datetime.now().strftime("%Y-%m-%d")},
        )

        assert log["status"] == "completed"
        assert len(log["steps_completed"]) == 4

    def test_template_update_procedure(self):
        """测试模板更新流程"""
        runbook = CoordinatorRunbook()

        entry = runbook.add_entry(
            title="Template Update Procedure",
            category="update",
            procedure=[
                "1. Review proposed changes",
                "2. Validate template syntax",
                "3. Check variable compatibility",
                "4. Execute update in staging",
                "5. Monitor metrics for 30 minutes",
                "6. Deploy to production",
            ],
            estimated_duration_minutes=60,
            required_permissions=["admin"],
        )

        log = runbook.execute_procedure(
            entry_id=entry.entry_id,
            operator="admin",
            parameters={"template_id": "tpl-system-001"},
        )

        assert log["status"] == "completed"
        assert len(log["steps_completed"]) == 6


class TestExceptionHandling:
    """测试异常处置"""

    def test_exception_case_management(self):
        """测试异常案例管理"""
        manager = ExceptionCaseManager()

        # 添加异常案例
        case1 = manager.add_case(
            title="Context Overflow Error",
            description="Context package exceeds maximum size limit",
            symptoms=[
                "Memory usage spike",
                "Slow response time",
                "Timeout errors",
            ],
            root_cause="Large document attachment without compression",
            resolution_steps=[
                "1. Check context package size",
                "2. Enable context compression",
                "3. Remove unnecessary attachments",
                "4. Increase memory limit if needed",
            ],
            prevention_measures=[
                "Set max size validation",
                "Auto-compress large contexts",
                "Monitor context size metrics",
            ],
        )

        manager.add_case(
            title="Prompt Version Mismatch",
            description="Prompt version incompatible with context format",
            symptoms=[
                "Invalid JSON output",
                "Schema validation failures",
            ],
            root_cause="Version upgrade without proper migration",
            resolution_steps=[
                "1. Identify mismatched versions",
                "2. Rollback to previous version",
                "3. Plan proper migration",
            ],
            prevention_measures=[
                "Version compatibility check before deploy",
                "Automated migration tests",
            ],
        )

        # 搜索案例
        memory_cases = manager.search_by_symptom("Memory")
        assert len(memory_cases) == 1
        assert memory_cases[0].title == "Context Overflow Error"

        json_cases = manager.search_by_symptom("JSON")
        assert len(json_cases) == 1
        assert json_cases[0].title == "Prompt Version Mismatch"

        # 获取解决指南
        guide = manager.get_resolution_guide(case1.case_id)
        assert guide["title"] == "Context Overflow Error"
        assert len(guide["steps"]) == 4


class TestRunbookDocumentation:
    """测试 Runbook 文档生成"""

    def test_generate_runbook_document(self):
        """测试生成 Runbook 文档"""
        runbook = CoordinatorRunbook()

        # 添加多个条目
        runbook.add_entry(
            title="Daily Health Check",
            category="maintenance",
            procedure=["Check status", "Review logs", "Generate report"],
            estimated_duration_minutes=15,
            required_permissions=["admin"],
        )

        runbook.add_entry(
            title="Emergency Rollback",
            category="emergency",
            procedure=["Identify issue", "Execute rollback", "Verify status"],
            estimated_duration_minutes=10,
            required_permissions=["admin", "devops"],
        )

        runbook.add_entry(
            title="Template Update",
            category="update",
            procedure=["Prepare changes", "Validate", "Deploy"],
            estimated_duration_minutes=30,
            required_permissions=["admin"],
        )

        # 生成文档
        document = runbook.generate_document()

        # 验证文档内容
        assert "# Coordinator Runbook" in document
        assert "Daily Health Check" in document
        assert "Emergency Rollback" in document
        assert "Template Update" in document
        assert "Estimated Duration" in document
        assert "Required Permissions" in document


class TestOperationRecording:
    """测试操作记录"""

    def test_comprehensive_operation_recording(self):
        """测试综合操作记录"""
        recorder = OperationRecorder()

        # 记录多种操作
        recorder.record(
            OperationType.TEMPLATE_UPDATE,
            "admin",
            "Update system prompt",
        )
        recorder.record(
            OperationType.VERSION_SWITCH,
            "devops",
            "Switch to v2.0",
        )
        recorder.record(
            OperationType.AB_TEST,
            "analyst",
            "Start quality test",
        )
        recorder.record(
            OperationType.CONTEXT_DEBUG,
            "developer",
            "Debug session issue",
        )
        recorder.record(
            OperationType.TEMPLATE_UPDATE,
            "admin",
            "Update task prompt",
        )

        # 查询记录
        template_ops = recorder.query(operation_type=OperationType.TEMPLATE_UPDATE)
        assert len(template_ops) == 2

        admin_ops = recorder.query(operator="admin")
        assert len(admin_ops) == 2

        # 获取最近记录
        recent = recorder.get_recent(limit=3)
        assert len(recent) == 3

        # 生成日报
        report = recorder.generate_daily_report()
        assert report["total_operations"] == 5
        assert report["by_type"]["template_update"] == 2
        assert report["by_type"]["version_switch"] == 1


class TestCIIntegration:
    """测试 CI 集成回归测试"""

    def test_regression_suite_completeness(self):
        """测试回归测试套件完整性"""
        # 验证所有核心组件可用
        from src.domain.services.coordinator_runbook import (
            ABTestOperation,
            ContextDebugOperation,
            CoordinatorRunbook,
            ExceptionCaseManager,
            OperationRecorder,
            TemplateUpdateOperation,
            VersionSwitchOperation,
        )

        # 验证可以实例化
        template_op = TemplateUpdateOperation()
        version_op = VersionSwitchOperation()
        ab_op = ABTestOperation()
        debug_op = ContextDebugOperation()
        recorder = OperationRecorder()
        exception_mgr = ExceptionCaseManager()
        runbook = CoordinatorRunbook()

        # 验证基本操作
        assert template_op is not None
        assert version_op is not None
        assert ab_op is not None
        assert debug_op is not None
        assert recorder is not None
        assert exception_mgr is not None
        assert runbook is not None

    def test_cross_module_integration(self):
        """测试跨模块集成"""
        # 模拟完整的运维场景
        template_op = TemplateUpdateOperation()
        version_op = VersionSwitchOperation()
        recorder = OperationRecorder()
        runbook = CoordinatorRunbook()

        # 1. 添加运维流程
        update_entry = runbook.add_entry(
            title="Version Upgrade Procedure",
            category="update",
            procedure=[
                "Validate templates",
                "Plan version switch",
                "Execute gradual rollout",
                "Monitor metrics",
            ],
            estimated_duration_minutes=45,
            required_permissions=["admin", "devops"],
        )

        # 2. 准备模板更新
        change = template_op.prepare_update(
            template_id="tpl-cross-001",
            module_name="cross_module",
            new_content="Cross module test content",
            reason="CI integration test",
        )

        # 3. 执行模板更新
        update_record = template_op.execute_update(change, operator="ci-bot")

        # 4. 计划版本切换
        switch = version_op.plan_switch(
            from_version="1.0.0",
            to_version="1.1.0",
            modules=["cross_module"],
            strategy=RollbackStrategy.IMMEDIATE,
        )

        # 5. 执行版本切换
        switch_record = version_op.execute_switch(switch, operator="ci-bot")

        # 6. 记录操作
        recorder.record(
            OperationType.TEMPLATE_UPDATE,
            "ci-bot",
            "Template update for CI",
            result={"record_id": update_record.record_id},
        )
        recorder.record(
            OperationType.VERSION_SWITCH,
            "ci-bot",
            "Version switch for CI",
            result={"record_id": switch_record.record_id},
        )

        # 7. 执行运维流程
        exec_log = runbook.execute_procedure(
            entry_id=update_entry.entry_id,
            operator="ci-bot",
        )

        # 验证完整流程
        assert update_record.status == OperationStatus.COMPLETED
        assert switch_record.status == OperationStatus.COMPLETED
        assert exec_log["status"] == "completed"

        # 验证记录
        ci_ops = recorder.query(operator="ci-bot")
        assert len(ci_ops) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
