"""提示词稳定性监控与审计集成测试

测试完整的端到端流程：
1. 模拟会话记录提示词使用
2. 检测各类漂移
3. 验证输出格式
4. 生成审计报表
5. 触发异常警报
"""

import json

from src.domain.services.prompt_stability_monitor import (
    AlertLevel,
    AlertType,
    AuditAlert,
    OutputFormatValidator,
    PromptAuditCoordinator,
    PromptDriftDetector,
    PromptStabilityMonitor,
    PromptUsageLogger,
    StabilityStatus,
)


class TestEndToEndPromptMonitoring:
    """端到端提示词监控测试"""

    def test_complete_monitoring_workflow(self) -> None:
        """
        测试完整的监控工作流

        场景：
        1. 记录多个会话的提示词使用
        2. 更新实际输出
        3. 运行审计
        4. 生成报表
        """
        # 1. 创建日志记录器和监控器
        logger = PromptUsageLogger()
        monitor = PromptStabilityMonitor(
            logger=logger,
            expected_modules=["system", "task", "output_format"],
            allowed_scenarios=["data_analysis", "qa", "summarization"],
        )

        # 2. 模拟多个会话的提示词使用
        sessions = [
            {
                "session_id": "session_001",
                "prompt_version": "v1.0.0",
                "modules": ["system", "task", "output_format"],
                "scenario": "data_analysis",
                "task": "分析Q3销售数据",
                "output": '{"trend": "up", "rate": "15%"}',
                "valid": True,
            },
            {
                "session_id": "session_002",
                "prompt_version": "v1.0.0",
                "modules": ["system", "task", "output_format"],
                "scenario": "qa",
                "task": "回答用户问题",
                "output": '{"answer": "Python是一种编程语言"}',
                "valid": True,
            },
            {
                "session_id": "session_003",
                "prompt_version": "v1.0.0",
                "modules": ["system", "task", "output_format"],
                "scenario": "summarization",
                "task": "总结文档内容",
                "output": '{"summary": "文档主要讨论了..."}',
                "valid": True,
            },
        ]

        for session in sessions:
            log_id = logger.log_prompt_usage(
                session_id=session["session_id"],
                prompt_version=session["prompt_version"],
                module_combination=session["modules"],
                scenario=session["scenario"],
                task_prompt=session["task"],
                expected_output_format="json",
            )
            logger.update_actual_output(
                log_id=log_id,
                actual_output=session["output"],
                output_valid=session["valid"],
            )

        # 3. 检查稳定性
        metrics = monitor.check_stability()

        assert metrics.status == StabilityStatus.STABLE
        assert metrics.version_consistency == 1.0
        assert metrics.output_validity_rate == 1.0

        # 4. 生成报表
        coordinator = PromptAuditCoordinator(
            logger=logger,
            expected_modules=["system", "task", "output_format"],
            allowed_scenarios=["data_analysis", "qa", "summarization"],
        )
        report = coordinator.generate_report()

        assert report["total_logs"] == 3
        assert report["unique_sessions"] == 3
        assert report["version_distribution"]["v1.0.0"] == 3

    def test_drift_detection_and_alerting(self) -> None:
        """
        测试漂移检测和警报触发

        场景：
        1. 记录正常日志
        2. 引入版本漂移
        3. 引入模块漂移
        4. 验证警报触发
        """
        logger = PromptUsageLogger()
        coordinator = PromptAuditCoordinator(
            logger=logger,
            expected_modules=["system", "task"],
            allowed_scenarios=["analysis"],
        )

        # 收集警报
        alerts_received: list[AuditAlert] = []
        coordinator.register_alert_callback(lambda a: alerts_received.append(a))

        # 正常日志
        logger.log_prompt_usage(
            session_id="s1",
            prompt_version="v1.0.0",
            module_combination=["system", "task"],
            scenario="analysis",
            task_prompt="分析数据",
            expected_output_format="json",
        )

        # 引入版本漂移
        logger.log_prompt_usage(
            session_id="s2",
            prompt_version="v1.1.0",  # 版本变化
            module_combination=["system", "task"],
            scenario="analysis",
            task_prompt="分析数据",
            expected_output_format="json",
        )

        # 引入模块漂移
        logger.log_prompt_usage(
            session_id="s3",
            prompt_version="v1.0.0",
            module_combination=["system", "task", "extra"],  # 模块变化
            scenario="analysis",
            task_prompt="分析数据",
            expected_output_format="json",
        )

        # 运行审计
        result = coordinator.run_audit()

        # 验证检测到漂移
        assert result.drifts_detected >= 2  # 版本和模块漂移

        # 验证警报历史
        alert_history = coordinator.get_alert_history()
        assert len(alert_history) >= 2

    def test_output_format_violation_detection(self) -> None:
        """
        测试输出格式违规检测

        场景：
        1. 记录有效JSON输出
        2. 记录无效输出
        3. 验证格式违规被检测
        """
        logger = PromptUsageLogger()

        # 有效输出
        log1 = logger.log_prompt_usage(
            session_id="s1",
            prompt_version="v1.0.0",
            module_combination=["system"],
            scenario="test",
            task_prompt="任务1",
            expected_output_format="json",
        )
        logger.update_actual_output(log1, '{"status": "ok"}', output_valid=True)

        # 无效输出
        log2 = logger.log_prompt_usage(
            session_id="s2",
            prompt_version="v1.0.0",
            module_combination=["system"],
            scenario="test",
            task_prompt="任务2",
            expected_output_format="json",
        )
        logger.update_actual_output(log2, "这不是JSON格式", output_valid=False)

        log3 = logger.log_prompt_usage(
            session_id="s3",
            prompt_version="v1.0.0",
            module_combination=["system"],
            scenario="test",
            task_prompt="任务3",
            expected_output_format="json",
        )
        logger.update_actual_output(log3, "{invalid json}", output_valid=False)

        # 运行审计
        coordinator = PromptAuditCoordinator(logger=logger)
        result = coordinator.run_audit()

        # 验证格式违规
        assert result.format_violations == 2

        # 验证警报
        format_alerts = [a for a in result.alerts if a.alert_type == AlertType.FORMAT_VIOLATION]
        assert len(format_alerts) == 1


class TestPromptUsageReporting:
    """提示词使用报表测试"""

    def test_generate_comprehensive_report(self) -> None:
        """测试生成综合报表"""
        logger = PromptUsageLogger()

        # 创建多样化的使用记录
        scenarios = ["analysis", "qa", "summarization"]
        versions = ["v1.0.0", "v1.0.0", "v1.0.0", "v1.1.0", "v1.1.0"]

        for i, (scenario, version) in enumerate(
            zip(scenarios * 2, versions + versions[:1], strict=False)
        ):
            log_id = logger.log_prompt_usage(
                session_id=f"session_{i:03d}",
                prompt_version=version,
                module_combination=["system", "task"],
                scenario=scenario,
                task_prompt=f"任务 {i}",
                expected_output_format="json",
            )
            # 80% 有效输出
            logger.update_actual_output(
                log_id,
                '{"result": "ok"}' if i % 5 != 0 else "invalid",
                output_valid=(i % 5 != 0),
            )

        coordinator = PromptAuditCoordinator(
            logger=logger,
            allowed_scenarios=scenarios,
        )
        report = coordinator.generate_report()

        # 验证报表内容
        assert "total_logs" in report
        assert "version_distribution" in report
        assert "scenario_distribution" in report
        assert "stability_metrics" in report
        assert "audit_summary" in report

        # 验证版本分布
        assert sum(report["version_distribution"].values()) == report["total_logs"]

    def test_stability_trend_analysis(self) -> None:
        """测试稳定性趋势分析"""
        logger = PromptUsageLogger()
        monitor = PromptStabilityMonitor(logger=logger)

        # 模拟多次检查
        for i in range(5):
            log_id = logger.log_prompt_usage(
                session_id=f"s{i}",
                prompt_version="v1.0.0",
                module_combination=["system"],
                scenario="test",
                task_prompt=f"任务{i}",
                expected_output_format="json",
            )
            logger.update_actual_output(log_id, '{"ok": true}', output_valid=True)
            monitor.check_stability()

        trend = monitor.analyze_stability_trend(window_size=5)

        assert "trend" in trend
        assert "data_points" in trend
        assert len(trend["data_points"]) >= 1


class TestAlertManagement:
    """警报管理测试"""

    def test_alert_callback_system(self) -> None:
        """测试警报回调系统"""
        logger = PromptUsageLogger()
        coordinator = PromptAuditCoordinator(logger=logger)

        # 设置多个回调
        callback1_calls = []
        callback2_calls = []

        coordinator.register_alert_callback(lambda a: callback1_calls.append(a.alert_id))
        coordinator.register_alert_callback(lambda a: callback2_calls.append(a.message))

        # 触发警报
        coordinator.trigger_alert(
            AlertType.STABILITY_ISSUE,
            AlertLevel.WARNING,
            "测试警报消息",
            {"key": "value"},
        )

        # 验证两个回调都被调用
        assert len(callback1_calls) == 1
        assert len(callback2_calls) == 1
        assert callback2_calls[0] == "测试警报消息"

    def test_alert_filtering_by_level(self) -> None:
        """测试按级别过滤警报"""
        logger = PromptUsageLogger()
        coordinator = PromptAuditCoordinator(logger=logger)

        # 创建不同级别的警报
        levels = [
            (AlertLevel.INFO, "信息级别"),
            (AlertLevel.WARNING, "警告级别"),
            (AlertLevel.WARNING, "另一个警告"),
            (AlertLevel.ERROR, "错误级别"),
            (AlertLevel.CRITICAL, "严重级别"),
        ]

        for level, msg in levels:
            coordinator.trigger_alert(
                AlertType.STABILITY_ISSUE,
                level,
                msg,
                {},
            )

        # 过滤测试
        warnings = coordinator.get_alerts_by_level(AlertLevel.WARNING)
        errors = coordinator.get_alerts_by_level(AlertLevel.ERROR)
        criticals = coordinator.get_alerts_by_level(AlertLevel.CRITICAL)

        assert len(warnings) == 2
        assert len(errors) == 1
        assert len(criticals) == 1


class TestOutputValidationIntegration:
    """输出验证集成测试"""

    def test_json_template_validation(self) -> None:
        """测试JSON模板验证"""
        validator = OutputFormatValidator()

        # 定义API响应模板
        api_response_template = {
            "type": "object",
            "required": ["status", "data", "timestamp"],
            "properties": {
                "status": {"type": "string"},
                "data": {"type": "object"},
                "timestamp": {"type": "string"},
            },
        }

        # 有效响应
        valid_response = json.dumps(
            {
                "status": "success",
                "data": {"users": [], "total": 0},
                "timestamp": "2024-01-01T00:00:00Z",
            }
        )
        result = validator.validate_against_template(valid_response, api_response_template)
        assert result.is_valid is True

        # 缺少必需字段
        invalid_response = json.dumps(
            {
                "status": "success",
                "data": {"users": []},
                # 缺少 timestamp
            }
        )
        result = validator.validate_against_template(invalid_response, api_response_template)
        assert result.is_valid is False
        assert any("timestamp" in e.message for e in result.errors)

    def test_nested_json_validation(self) -> None:
        """测试嵌套JSON验证"""
        validator = OutputFormatValidator(max_depth=4)

        # 合理深度
        reasonable = json.dumps({"level1": {"level2": {"level3": "value"}}})
        result = validator.validate_json_format(reasonable)
        assert result.is_valid is True

        # 过深嵌套
        too_deep = json.dumps({"l1": {"l2": {"l3": {"l4": {"l5": "too deep"}}}}})
        result = validator.validate_json_format(too_deep)
        assert result.is_valid is False


class TestScenarioDriftDetection:
    """场景漂移检测测试"""

    def test_detect_unknown_scenario(self) -> None:
        """测试检测未知场景"""
        logger = PromptUsageLogger()

        allowed_scenarios = ["analysis", "qa", "summarization"]

        # 正常场景
        logger.log_prompt_usage(
            session_id="s1",
            prompt_version="v1.0.0",
            module_combination=["system"],
            scenario="analysis",
            task_prompt="分析任务",
            expected_output_format="json",
        )

        # 未知场景
        logger.log_prompt_usage(
            session_id="s2",
            prompt_version="v1.0.0",
            module_combination=["system"],
            scenario="unknown_scenario",
            task_prompt="未知任务",
            expected_output_format="json",
        )

        detector = PromptDriftDetector()
        result = detector.detect_scenario_drift(
            logger.get_usage_history(),
            allowed_scenarios=allowed_scenarios,
        )

        assert result.drift_detected is True
        assert "unknown_scenario" in result.details["unknown_scenarios"]


class TestMultiSessionTracking:
    """多会话追踪测试"""

    def test_track_multiple_sessions(self) -> None:
        """测试追踪多个会话"""
        logger = PromptUsageLogger()

        # 创建多个会话的日志
        for session_idx in range(3):
            session_id = f"session_{session_idx:03d}"
            for log_idx in range(4):
                logger.log_prompt_usage(
                    session_id=session_id,
                    prompt_version="v1.0.0",
                    module_combination=["system", "task"],
                    scenario="analysis",
                    task_prompt=f"会话{session_idx}任务{log_idx}",
                    expected_output_format="json",
                )

        # 验证会话追踪
        stats = logger.get_usage_statistics()
        assert stats["total_logs"] == 12
        assert stats["unique_sessions"] == 3

        # 验证按会话获取
        session_0_logs = logger.get_usage_by_session("session_000")
        assert len(session_0_logs) == 4

    def test_session_isolation(self) -> None:
        """测试会话隔离"""
        logger = PromptUsageLogger()

        # 会话A使用版本1.0
        for i in range(3):
            logger.log_prompt_usage(
                session_id="session_A",
                prompt_version="v1.0.0",
                module_combination=["system"],
                scenario="analysis",
                task_prompt=f"A任务{i}",
                expected_output_format="json",
            )

        # 会话B使用版本1.1
        for i in range(3):
            logger.log_prompt_usage(
                session_id="session_B",
                prompt_version="v1.1.0",
                module_combination=["system", "extra"],
                scenario="qa",
                task_prompt=f"B任务{i}",
                expected_output_format="json",
            )

        # 验证会话A的日志
        session_a_logs = logger.get_usage_by_session("session_A")
        assert all(log.prompt_version == "v1.0.0" for log in session_a_logs)
        assert all(log.scenario == "analysis" for log in session_a_logs)

        # 验证会话B的日志
        session_b_logs = logger.get_usage_by_session("session_B")
        assert all(log.prompt_version == "v1.1.0" for log in session_b_logs)
        assert all(log.scenario == "qa" for log in session_b_logs)


class TestAuditDocumentation:
    """审计文档测试"""

    def test_audit_result_contains_documentation(self) -> None:
        """测试审计结果包含文档信息"""
        logger = PromptUsageLogger()

        # 创建测试数据
        for i in range(5):
            log_id = logger.log_prompt_usage(
                session_id=f"s{i}",
                prompt_version="v1.0.0",
                module_combination=["system"],
                scenario="test",
                task_prompt=f"任务{i}",
                expected_output_format="json",
            )
            logger.update_actual_output(log_id, '{"ok": true}', output_valid=True)

        coordinator = PromptAuditCoordinator(logger=logger)
        result = coordinator.run_audit()

        # 验证审计结果摘要
        summary = result.get_summary()
        assert "audit_id" in summary
        assert "timestamp" in summary
        assert "logs_analyzed" in summary
        assert "stability_status" in summary

        # 验证可以用于文档记录
        assert summary["logs_analyzed"] == 5
        assert summary["stability_status"] == "stable"
