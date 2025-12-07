"""提示词稳定性监控与审计测试

测试覆盖：
1. 提示词使用日志记录
2. 版本漂移检测
3. 格式漂移检测
4. 输出格式验证
5. 审计协调
6. 警报触发
7. 报表生成
"""

from datetime import datetime

from src.domain.services.prompt_stability_monitor import (
    AlertLevel,
    AlertType,
    AuditAlert,
    AuditResult,
    DriftDetectionResult,
    DriftType,
    OutputFormatValidator,
    OutputValidationResult,
    PromptAuditCoordinator,
    PromptDriftDetector,
    PromptStabilityMonitor,
    PromptUsageLog,
    PromptUsageLogger,
    StabilityMetrics,
    StabilityStatus,
    ValidationErrorType,
)


class TestPromptUsageLog:
    """提示词使用日志数据类测试"""

    def test_create_prompt_usage_log(self) -> None:
        """测试创建提示词使用日志"""
        log = PromptUsageLog(
            session_id="session_001",
            prompt_version="v1.0.0",
            module_combination=["system", "task", "output_format"],
            scenario="data_analysis",
            task_prompt="分析销售数据",
            expected_output_format="json",
        )

        assert log.session_id == "session_001"
        assert log.prompt_version == "v1.0.0"
        assert log.module_combination == ["system", "task", "output_format"]
        assert log.scenario == "data_analysis"
        assert log.task_prompt == "分析销售数据"
        assert log.expected_output_format == "json"
        assert log.log_id is not None
        assert log.timestamp is not None

    def test_prompt_usage_log_with_actual_output(self) -> None:
        """测试带实际输出的日志"""
        log = PromptUsageLog(
            session_id="session_002",
            prompt_version="v1.0.0",
            module_combination=["system"],
            scenario="greeting",
            task_prompt="打招呼",
            expected_output_format="text",
            actual_output="你好！",
            output_valid=True,
        )

        assert log.actual_output == "你好！"
        assert log.output_valid is True

    def test_prompt_usage_log_to_dict(self) -> None:
        """测试日志转字典"""
        log = PromptUsageLog(
            session_id="session_003",
            prompt_version="v1.0.0",
            module_combination=["system", "task"],
            scenario="qa",
            task_prompt="回答问题",
            expected_output_format="json",
        )

        log_dict = log.to_dict()

        assert log_dict["session_id"] == "session_003"
        assert log_dict["prompt_version"] == "v1.0.0"
        assert "timestamp" in log_dict
        assert "log_id" in log_dict

    def test_prompt_usage_log_from_dict(self) -> None:
        """测试从字典创建日志"""
        data = {
            "log_id": "log_001",
            "session_id": "session_004",
            "timestamp": datetime.now().isoformat(),
            "prompt_version": "v1.1.0",
            "module_combination": ["system"],
            "scenario": "test",
            "task_prompt": "测试任务",
            "expected_output_format": "json",
        }

        log = PromptUsageLog.from_dict(data)

        assert log.log_id == "log_001"
        assert log.session_id == "session_004"
        assert log.prompt_version == "v1.1.0"


class TestPromptUsageLogger:
    """提示词使用日志记录器测试"""

    def test_log_prompt_usage(self) -> None:
        """测试记录提示词使用"""
        logger = PromptUsageLogger()

        log_id = logger.log_prompt_usage(
            session_id="session_001",
            prompt_version="v1.0.0",
            module_combination=["system", "task"],
            scenario="analysis",
            task_prompt="分析数据",
            expected_output_format="json",
        )

        assert log_id is not None
        history = logger.get_usage_history()
        assert len(history) == 1
        assert history[0].session_id == "session_001"

    def test_get_usage_by_session(self) -> None:
        """测试按会话获取使用记录"""
        logger = PromptUsageLogger()

        # 记录多个会话
        logger.log_prompt_usage(
            session_id="session_A",
            prompt_version="v1.0.0",
            module_combination=["system"],
            scenario="test1",
            task_prompt="任务1",
            expected_output_format="json",
        )
        logger.log_prompt_usage(
            session_id="session_B",
            prompt_version="v1.0.0",
            module_combination=["system"],
            scenario="test2",
            task_prompt="任务2",
            expected_output_format="json",
        )
        logger.log_prompt_usage(
            session_id="session_A",
            prompt_version="v1.0.0",
            module_combination=["system", "task"],
            scenario="test3",
            task_prompt="任务3",
            expected_output_format="json",
        )

        session_a_logs = logger.get_usage_by_session("session_A")

        assert len(session_a_logs) == 2
        assert all(log.session_id == "session_A" for log in session_a_logs)

    def test_get_usage_by_version(self) -> None:
        """测试按版本获取使用记录"""
        logger = PromptUsageLogger()

        logger.log_prompt_usage(
            session_id="s1",
            prompt_version="v1.0.0",
            module_combination=["system"],
            scenario="test",
            task_prompt="任务",
            expected_output_format="json",
        )
        logger.log_prompt_usage(
            session_id="s2",
            prompt_version="v1.1.0",
            module_combination=["system"],
            scenario="test",
            task_prompt="任务",
            expected_output_format="json",
        )
        logger.log_prompt_usage(
            session_id="s3",
            prompt_version="v1.0.0",
            module_combination=["system"],
            scenario="test",
            task_prompt="任务",
            expected_output_format="json",
        )

        v1_logs = logger.get_usage_by_version("v1.0.0")

        assert len(v1_logs) == 2

    def test_update_actual_output(self) -> None:
        """测试更新实际输出"""
        logger = PromptUsageLogger()

        log_id = logger.log_prompt_usage(
            session_id="session_001",
            prompt_version="v1.0.0",
            module_combination=["system"],
            scenario="test",
            task_prompt="任务",
            expected_output_format="json",
        )

        logger.update_actual_output(
            log_id=log_id,
            actual_output='{"result": "success"}',
            output_valid=True,
        )

        log = logger.get_log_by_id(log_id)
        assert log is not None
        assert log.actual_output == '{"result": "success"}'
        assert log.output_valid is True

    def test_get_usage_statistics(self) -> None:
        """测试获取使用统计"""
        logger = PromptUsageLogger()

        # 添加多条记录
        for i in range(5):
            logger.log_prompt_usage(
                session_id=f"session_{i}",
                prompt_version="v1.0.0" if i < 3 else "v1.1.0",
                module_combination=["system"],
                scenario="test",
                task_prompt=f"任务{i}",
                expected_output_format="json",
            )

        stats = logger.get_usage_statistics()

        assert stats["total_logs"] == 5
        assert stats["by_version"]["v1.0.0"] == 3
        assert stats["by_version"]["v1.1.0"] == 2
        assert stats["unique_sessions"] == 5


class TestPromptDriftDetector:
    """提示漂移检测器测试"""

    def test_detect_version_drift(self) -> None:
        """测试检测版本漂移"""
        detector = PromptDriftDetector()

        logs = [
            PromptUsageLog(
                session_id="s1",
                prompt_version="v1.0.0",
                module_combination=["system"],
                scenario="test",
                task_prompt="任务",
                expected_output_format="json",
            ),
            PromptUsageLog(
                session_id="s2",
                prompt_version="v1.0.0",
                module_combination=["system"],
                scenario="test",
                task_prompt="任务",
                expected_output_format="json",
            ),
            PromptUsageLog(
                session_id="s3",
                prompt_version="v1.1.0",  # 版本变化
                module_combination=["system"],
                scenario="test",
                task_prompt="任务",
                expected_output_format="json",
            ),
        ]

        result = detector.detect_version_drift(logs)

        assert result.drift_detected is True
        assert result.drift_type == DriftType.VERSION
        assert "v1.0.0" in result.details["versions"]
        assert "v1.1.0" in result.details["versions"]

    def test_no_version_drift(self) -> None:
        """测试无版本漂移"""
        detector = PromptDriftDetector()

        logs = [
            PromptUsageLog(
                session_id=f"s{i}",
                prompt_version="v1.0.0",
                module_combination=["system"],
                scenario="test",
                task_prompt="任务",
                expected_output_format="json",
            )
            for i in range(5)
        ]

        result = detector.detect_version_drift(logs)

        assert result.drift_detected is False

    def test_detect_module_drift(self) -> None:
        """测试检测模块组合漂移"""
        detector = PromptDriftDetector()

        logs = [
            PromptUsageLog(
                session_id="s1",
                prompt_version="v1.0.0",
                module_combination=["system", "task"],
                scenario="analysis",
                task_prompt="任务",
                expected_output_format="json",
            ),
            PromptUsageLog(
                session_id="s2",
                prompt_version="v1.0.0",
                module_combination=["system", "task", "extra"],  # 模块变化
                scenario="analysis",
                task_prompt="任务",
                expected_output_format="json",
            ),
        ]

        result = detector.detect_module_drift(logs, expected_modules=["system", "task"])

        assert result.drift_detected is True
        assert result.drift_type == DriftType.MODULE

    def test_detect_output_format_drift(self) -> None:
        """测试检测输出格式漂移"""
        detector = PromptDriftDetector()

        logs = [
            PromptUsageLog(
                session_id="s1",
                prompt_version="v1.0.0",
                module_combination=["system"],
                scenario="test",
                task_prompt="任务",
                expected_output_format="json",
                actual_output='{"key": "value"}',
                output_valid=True,
            ),
            PromptUsageLog(
                session_id="s2",
                prompt_version="v1.0.0",
                module_combination=["system"],
                scenario="test",
                task_prompt="任务",
                expected_output_format="json",
                actual_output="这不是JSON",  # 格式不符
                output_valid=False,
            ),
        ]

        result = detector.detect_output_format_drift(logs)

        assert result.drift_detected is True
        assert result.drift_type == DriftType.OUTPUT_FORMAT
        assert result.details["invalid_count"] == 1

    def test_detect_scenario_drift(self) -> None:
        """测试检测场景漂移"""
        detector = PromptDriftDetector()

        logs = [
            PromptUsageLog(
                session_id="s1",
                prompt_version="v1.0.0",
                module_combination=["system"],
                scenario="data_analysis",
                task_prompt="分析数据",
                expected_output_format="json",
            ),
            PromptUsageLog(
                session_id="s2",
                prompt_version="v1.0.0",
                module_combination=["system"],
                scenario="unknown_scenario",  # 未知场景
                task_prompt="未知任务",
                expected_output_format="json",
            ),
        ]

        result = detector.detect_scenario_drift(
            logs,
            allowed_scenarios=["data_analysis", "greeting", "qa"],
        )

        assert result.drift_detected is True
        assert result.drift_type == DriftType.SCENARIO

    def test_comprehensive_drift_detection(self) -> None:
        """测试综合漂移检测"""
        detector = PromptDriftDetector()

        logs = [
            PromptUsageLog(
                session_id="s1",
                prompt_version="v1.0.0",
                module_combination=["system", "task"],
                scenario="analysis",
                task_prompt="任务",
                expected_output_format="json",
                actual_output='{"result": "ok"}',
                output_valid=True,
            ),
            PromptUsageLog(
                session_id="s2",
                prompt_version="v1.1.0",  # 版本漂移
                module_combination=["system"],  # 模块漂移
                scenario="unknown",  # 场景漂移
                task_prompt="任务",
                expected_output_format="json",
                actual_output="不是JSON",  # 格式漂移
                output_valid=False,
            ),
        ]

        results = detector.detect_all_drifts(
            logs,
            expected_modules=["system", "task"],
            allowed_scenarios=["analysis"],
        )

        # 应该检测到多种漂移
        drift_types = [r.drift_type for r in results if r.drift_detected]
        assert len(drift_types) >= 2


class TestOutputFormatValidator:
    """输出格式验证器测试"""

    def test_validate_valid_json(self) -> None:
        """测试验证有效JSON"""
        validator = OutputFormatValidator()

        result = validator.validate_json_format('{"key": "value", "number": 123}')

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_invalid_json(self) -> None:
        """测试验证无效JSON"""
        validator = OutputFormatValidator()

        result = validator.validate_json_format("这不是JSON格式")

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert result.errors[0].error_type == ValidationErrorType.JSON_PARSE_ERROR

    def test_validate_against_template(self) -> None:
        """测试对比模板验证"""
        validator = OutputFormatValidator()

        template = {
            "type": "object",
            "required": ["status", "data"],
            "properties": {
                "status": {"type": "string"},
                "data": {"type": "object"},
            },
        }

        # 有效输出
        valid_output = '{"status": "success", "data": {"key": "value"}}'
        result = validator.validate_against_template(valid_output, template)
        assert result.is_valid is True

        # 缺少必需字段
        invalid_output = '{"status": "success"}'
        result = validator.validate_against_template(invalid_output, template)
        assert result.is_valid is False
        assert any(
            e.error_type == ValidationErrorType.MISSING_REQUIRED_FIELD for e in result.errors
        )

    def test_validate_json_structure_depth(self) -> None:
        """测试验证JSON结构深度"""
        validator = OutputFormatValidator(max_depth=3)

        # 深度为2，应通过
        shallow = '{"level1": {"level2": "value"}}'
        result = validator.validate_json_format(shallow)
        assert result.is_valid is True

        # 深度为4，超过限制
        deep = '{"l1": {"l2": {"l3": {"l4": "too deep"}}}}'
        result = validator.validate_json_format(deep)
        assert result.is_valid is False
        assert any(e.error_type == ValidationErrorType.STRUCTURE_TOO_DEEP for e in result.errors)

    def test_validate_output_size(self) -> None:
        """测试验证输出大小"""
        validator = OutputFormatValidator(max_output_size=100)

        # 小输出，应通过
        small_output = '{"key": "value"}'
        result = validator.validate_json_format(small_output)
        assert result.is_valid is True

        # 大输出，超过限制
        large_output = '{"data": "' + "x" * 200 + '"}'
        result = validator.validate_json_format(large_output)
        assert result.is_valid is False
        assert any(e.error_type == ValidationErrorType.OUTPUT_TOO_LARGE for e in result.errors)

    def test_validate_expected_keys(self) -> None:
        """测试验证期望的键"""
        validator = OutputFormatValidator()

        output = '{"result": "ok", "extra": "data"}'
        expected_keys = ["result", "status"]

        result = validator.validate_expected_keys(output, expected_keys)

        assert result.is_valid is False
        assert any(e.error_type == ValidationErrorType.MISSING_EXPECTED_KEY for e in result.errors)


class TestAuditAlert:
    """审计警报测试"""

    def test_create_audit_alert(self) -> None:
        """测试创建审计警报"""
        alert = AuditAlert(
            alert_type=AlertType.DRIFT_DETECTED,
            alert_level=AlertLevel.WARNING,
            message="检测到版本漂移",
            details={"from_version": "v1.0.0", "to_version": "v1.1.0"},
        )

        assert alert.alert_type == AlertType.DRIFT_DETECTED
        assert alert.alert_level == AlertLevel.WARNING
        assert alert.alert_id is not None
        assert alert.timestamp is not None

    def test_alert_to_dict(self) -> None:
        """测试警报转字典"""
        alert = AuditAlert(
            alert_type=AlertType.FORMAT_VIOLATION,
            alert_level=AlertLevel.ERROR,
            message="输出格式不符合JSON模板",
            details={"session_id": "s1", "error": "parse error"},
        )

        alert_dict = alert.to_dict()

        assert alert_dict["alert_type"] == "format_violation"
        assert alert_dict["alert_level"] == "error"
        assert "message" in alert_dict


class TestPromptAuditCoordinator:
    """提示词审计协调者测试"""

    def test_run_audit(self) -> None:
        """测试运行审计"""
        logger = PromptUsageLogger()
        coordinator = PromptAuditCoordinator(logger=logger)

        # 添加一些日志
        logger.log_prompt_usage(
            session_id="s1",
            prompt_version="v1.0.0",
            module_combination=["system", "task"],
            scenario="analysis",
            task_prompt="任务",
            expected_output_format="json",
        )

        result = coordinator.run_audit()

        assert isinstance(result, AuditResult)
        assert result.audit_id is not None
        assert result.logs_analyzed > 0

    def test_audit_detects_drifts(self) -> None:
        """测试审计检测漂移"""
        logger = PromptUsageLogger()
        coordinator = PromptAuditCoordinator(
            logger=logger,
            expected_modules=["system", "task"],
            allowed_scenarios=["analysis", "greeting"],
        )

        # 添加有漂移的日志
        logger.log_prompt_usage(
            session_id="s1",
            prompt_version="v1.0.0",
            module_combination=["system", "task"],
            scenario="analysis",
            task_prompt="任务",
            expected_output_format="json",
        )
        log_id = logger.log_prompt_usage(
            session_id="s2",
            prompt_version="v1.1.0",  # 版本漂移
            module_combination=["system"],  # 模块漂移
            scenario="unknown",  # 场景漂移
            task_prompt="任务",
            expected_output_format="json",
        )
        logger.update_actual_output(log_id, "不是JSON", output_valid=False)

        result = coordinator.run_audit()

        assert result.drifts_detected > 0
        assert len(result.alerts) > 0

    def test_generate_report(self) -> None:
        """测试生成报表"""
        logger = PromptUsageLogger()
        coordinator = PromptAuditCoordinator(logger=logger)

        # 添加日志
        for i in range(10):
            logger.log_prompt_usage(
                session_id=f"s{i}",
                prompt_version="v1.0.0" if i < 7 else "v1.1.0",
                module_combination=["system"],
                scenario="test",
                task_prompt=f"任务{i}",
                expected_output_format="json",
            )

        report = coordinator.generate_report()

        assert "total_logs" in report
        assert "version_distribution" in report
        assert "audit_summary" in report
        assert report["total_logs"] == 10

    def test_trigger_alert(self) -> None:
        """测试触发警报"""
        logger = PromptUsageLogger()
        coordinator = PromptAuditCoordinator(logger=logger)

        # 注册警报回调
        alerts_received: list[AuditAlert] = []

        def alert_callback(alert: AuditAlert) -> None:
            alerts_received.append(alert)

        coordinator.register_alert_callback(alert_callback)

        # 触发警报
        coordinator.trigger_alert(
            alert_type=AlertType.DRIFT_DETECTED,
            alert_level=AlertLevel.WARNING,
            message="测试警报",
            details={},
        )

        assert len(alerts_received) == 1
        assert alerts_received[0].message == "测试警报"

    def test_get_alert_history(self) -> None:
        """测试获取警报历史"""
        logger = PromptUsageLogger()
        coordinator = PromptAuditCoordinator(logger=logger)

        # 触发多个警报
        coordinator.trigger_alert(AlertType.DRIFT_DETECTED, AlertLevel.WARNING, "警报1", {})
        coordinator.trigger_alert(AlertType.FORMAT_VIOLATION, AlertLevel.ERROR, "警报2", {})

        history = coordinator.get_alert_history()

        assert len(history) == 2

    def test_filter_alerts_by_level(self) -> None:
        """测试按级别过滤警报"""
        logger = PromptUsageLogger()
        coordinator = PromptAuditCoordinator(logger=logger)

        coordinator.trigger_alert(AlertType.DRIFT_DETECTED, AlertLevel.INFO, "信息", {})
        coordinator.trigger_alert(AlertType.DRIFT_DETECTED, AlertLevel.WARNING, "警告", {})
        coordinator.trigger_alert(AlertType.FORMAT_VIOLATION, AlertLevel.ERROR, "错误", {})
        coordinator.trigger_alert(AlertType.STABILITY_ISSUE, AlertLevel.CRITICAL, "严重", {})

        error_alerts = coordinator.get_alerts_by_level(AlertLevel.ERROR)

        assert len(error_alerts) == 1
        assert error_alerts[0].alert_level == AlertLevel.ERROR


class TestPromptStabilityMonitor:
    """提示词稳定性监控器测试"""

    def test_check_stability(self) -> None:
        """测试检查稳定性"""
        logger = PromptUsageLogger()
        monitor = PromptStabilityMonitor(logger=logger)

        # 添加稳定的日志
        for i in range(10):
            log_id = logger.log_prompt_usage(
                session_id=f"s{i}",
                prompt_version="v1.0.0",
                module_combination=["system", "task"],
                scenario="analysis",
                task_prompt=f"任务{i}",
                expected_output_format="json",
            )
            logger.update_actual_output(log_id, '{"result": "ok"}', output_valid=True)

        metrics = monitor.check_stability()

        assert metrics.status == StabilityStatus.STABLE
        assert metrics.version_consistency >= 0.9
        assert metrics.output_validity_rate >= 0.9

    def test_detect_instability(self) -> None:
        """测试检测不稳定"""
        logger = PromptUsageLogger()
        monitor = PromptStabilityMonitor(logger=logger)

        # 添加不稳定的日志
        for i in range(10):
            log_id = logger.log_prompt_usage(
                session_id=f"s{i}",
                prompt_version=f"v1.{i}.0",  # 每次都不同版本
                module_combination=["system"],
                scenario="test",
                task_prompt=f"任务{i}",
                expected_output_format="json",
            )
            # 50% 输出无效
            logger.update_actual_output(
                log_id,
                '{"result": "ok"}' if i % 2 == 0 else "invalid",
                output_valid=(i % 2 == 0),
            )

        metrics = monitor.check_stability()

        assert metrics.status in [StabilityStatus.UNSTABLE, StabilityStatus.DEGRADED]
        assert metrics.version_consistency < 0.5

    def test_get_stability_metrics(self) -> None:
        """测试获取稳定性指标"""
        logger = PromptUsageLogger()
        monitor = PromptStabilityMonitor(logger=logger)

        # 添加日志
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

        metrics = monitor.get_stability_metrics()

        assert isinstance(metrics, StabilityMetrics)
        assert metrics.total_logs == 5
        assert metrics.version_consistency == 1.0
        assert metrics.output_validity_rate == 1.0

    def test_stability_trend_analysis(self) -> None:
        """测试稳定性趋势分析"""
        logger = PromptUsageLogger()
        monitor = PromptStabilityMonitor(logger=logger)

        # 添加一些日志
        for i in range(10):
            log_id = logger.log_prompt_usage(
                session_id=f"s{i}",
                prompt_version="v1.0.0",
                module_combination=["system"],
                scenario="test",
                task_prompt=f"任务{i}",
                expected_output_format="json",
            )
            logger.update_actual_output(log_id, '{"ok": true}', output_valid=True)

        trend = monitor.analyze_stability_trend(window_size=5)

        assert "trend" in trend
        assert "data_points" in trend
        assert len(trend["data_points"]) > 0


class TestAuditResult:
    """审计结果测试"""

    def test_create_audit_result(self) -> None:
        """测试创建审计结果"""
        result = AuditResult(
            logs_analyzed=100,
            drifts_detected=3,
            format_violations=2,
            alerts=[],
            stability_metrics=StabilityMetrics(
                status=StabilityStatus.STABLE,
                total_logs=100,
                version_consistency=0.95,
                module_consistency=0.98,
                output_validity_rate=0.92,
                scenario_compliance=1.0,
            ),
        )

        assert result.audit_id is not None
        assert result.logs_analyzed == 100
        assert result.drifts_detected == 3

    def test_audit_result_summary(self) -> None:
        """测试审计结果摘要"""
        result = AuditResult(
            logs_analyzed=50,
            drifts_detected=1,
            format_violations=0,
            alerts=[],
            stability_metrics=StabilityMetrics(
                status=StabilityStatus.STABLE,
                total_logs=50,
                version_consistency=0.9,
                module_consistency=0.95,
                output_validity_rate=0.88,
                scenario_compliance=1.0,
            ),
        )

        summary = result.get_summary()

        assert "logs_analyzed" in summary
        assert "stability_status" in summary
        assert summary["stability_status"] == "stable"


class TestValidationErrorType:
    """验证错误类型测试"""

    def test_error_types_exist(self) -> None:
        """测试错误类型存在"""
        assert ValidationErrorType.JSON_PARSE_ERROR is not None
        assert ValidationErrorType.MISSING_REQUIRED_FIELD is not None
        assert ValidationErrorType.STRUCTURE_TOO_DEEP is not None
        assert ValidationErrorType.OUTPUT_TOO_LARGE is not None
        assert ValidationErrorType.MISSING_EXPECTED_KEY is not None
        assert ValidationErrorType.TYPE_MISMATCH is not None


class TestDriftType:
    """漂移类型测试"""

    def test_drift_types_exist(self) -> None:
        """测试漂移类型存在"""
        assert DriftType.VERSION is not None
        assert DriftType.MODULE is not None
        assert DriftType.SCENARIO is not None
        assert DriftType.OUTPUT_FORMAT is not None


class TestAlertType:
    """警报类型测试"""

    def test_alert_types_exist(self) -> None:
        """测试警报类型存在"""
        assert AlertType.DRIFT_DETECTED is not None
        assert AlertType.FORMAT_VIOLATION is not None
        assert AlertType.STABILITY_ISSUE is not None
        assert AlertType.THRESHOLD_EXCEEDED is not None


class TestAlertLevel:
    """警报级别测试"""

    def test_alert_levels_exist(self) -> None:
        """测试警报级别存在"""
        assert AlertLevel.INFO is not None
        assert AlertLevel.WARNING is not None
        assert AlertLevel.ERROR is not None
        assert AlertLevel.CRITICAL is not None


class TestStabilityStatus:
    """稳定性状态测试"""

    def test_stability_statuses_exist(self) -> None:
        """测试稳定性状态存在"""
        assert StabilityStatus.STABLE is not None
        assert StabilityStatus.DEGRADED is not None
        assert StabilityStatus.UNSTABLE is not None
        assert StabilityStatus.UNKNOWN is not None


class TestOutputValidationResult:
    """输出验证结果测试"""

    def test_create_validation_result(self) -> None:
        """测试创建验证结果"""
        from src.domain.services.prompt_stability_monitor import ValidationError

        result = OutputValidationResult(
            is_valid=False,
            errors=[
                ValidationError(
                    error_type=ValidationErrorType.JSON_PARSE_ERROR,
                    message="无法解析JSON",
                    location="root",
                )
            ],
        )

        assert result.is_valid is False
        assert len(result.errors) == 1

    def test_validation_result_with_warnings(self) -> None:
        """测试带警告的验证结果"""
        from src.domain.services.prompt_stability_monitor import ValidationError

        result = OutputValidationResult(
            is_valid=True,
            errors=[],
            warnings=[
                ValidationError(
                    error_type=ValidationErrorType.STRUCTURE_TOO_DEEP,
                    message="结构较深，建议简化",
                    location="data.nested",
                )
            ],
        )

        assert result.is_valid is True
        assert len(result.warnings) == 1


class TestDriftDetectionResult:
    """漂移检测结果测试"""

    def test_create_drift_result(self) -> None:
        """测试创建漂移检测结果"""
        result = DriftDetectionResult(
            drift_detected=True,
            drift_type=DriftType.VERSION,
            details={"versions": ["v1.0.0", "v1.1.0"]},
            affected_logs=["log_001", "log_002"],
        )

        assert result.drift_detected is True
        assert result.drift_type == DriftType.VERSION
        assert len(result.affected_logs) == 2

    def test_no_drift_result(self) -> None:
        """测试无漂移结果"""
        result = DriftDetectionResult(
            drift_detected=False,
            drift_type=None,
            details={},
            affected_logs=[],
        )

        assert result.drift_detected is False
        assert result.drift_type is None
