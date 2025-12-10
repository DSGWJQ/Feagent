"""ExperimentOrchestrator TDD 测试

验证从 CoordinatorAgent 提取的 A/B 实验管理功能。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class TestExperimentOrchestratorInit:
    """测试初始化"""

    def test_default_init_creates_dependencies(self) -> None:
        """默认初始化应创建内部依赖"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        orchestrator = ExperimentOrchestrator()

        assert orchestrator._experiment_manager is not None
        assert orchestrator._metrics_collector is not None
        assert orchestrator._rollout_controller is not None
        assert orchestrator._experiment_adapter is not None

    def test_init_with_log_collector(self) -> None:
        """可注入 log_collector"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_log_collector = MagicMock()
        orchestrator = ExperimentOrchestrator(log_collector=mock_log_collector)

        assert orchestrator._log_collector is mock_log_collector

    def test_init_with_custom_dependencies(self) -> None:
        """可注入自定义依赖（用于测试）"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_manager = MagicMock()
        mock_collector = MagicMock()
        mock_controller = MagicMock()
        mock_adapter = MagicMock()

        orchestrator = ExperimentOrchestrator(
            experiment_manager=mock_manager,
            metrics_collector=mock_collector,
            rollout_controller=mock_controller,
            experiment_adapter=mock_adapter,
        )

        assert orchestrator._experiment_manager is mock_manager
        assert orchestrator._metrics_collector is mock_collector
        assert orchestrator._rollout_controller is mock_controller
        assert orchestrator._experiment_adapter is mock_adapter


class TestExperimentCreation:
    """测试实验创建"""

    def test_create_experiment_basic(self) -> None:
        """创建基础 A/B 实验"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_manager = MagicMock()
        mock_config = MagicMock()
        mock_config.to_dict.return_value = {
            "experiment_id": "exp-001",
            "name": "Test Experiment",
            "module_name": "intent_classifier",
        }
        mock_manager.create_experiment.return_value = mock_config

        orchestrator = ExperimentOrchestrator(experiment_manager=mock_manager)

        result = orchestrator.create_experiment(
            experiment_id="exp-001",
            name="Test Experiment",
            module_name="intent_classifier",
            control_version="1.0.0",
            treatment_version="1.1.0",
        )

        assert result["experiment_id"] == "exp-001"
        mock_manager.create_experiment.assert_called_once()

    def test_create_experiment_with_traffic_allocation(self) -> None:
        """创建带流量分配的实验"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_manager = MagicMock()
        mock_config = MagicMock()
        mock_config.to_dict.return_value = {"experiment_id": "exp-002"}
        mock_manager.create_experiment.return_value = mock_config

        orchestrator = ExperimentOrchestrator(experiment_manager=mock_manager)

        result = orchestrator.create_experiment(
            experiment_id="exp-002",
            name="Traffic Test",
            module_name="test_module",
            control_version="1.0.0",
            treatment_version="2.0.0",
            traffic_allocation={"control": 70, "treatment": 30},
        )

        call_kwargs = mock_manager.create_experiment.call_args[1]
        assert call_kwargs["traffic_allocation"] == {"control": 70, "treatment": 30}

    def test_create_multi_variant_experiment(self) -> None:
        """创建多变体实验"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_manager = MagicMock()
        mock_config = MagicMock()
        mock_config.to_dict.return_value = {"experiment_id": "exp-003", "variant_count": 3}
        mock_manager.create_multi_variant_experiment.return_value = mock_config

        orchestrator = ExperimentOrchestrator(experiment_manager=mock_manager)

        variants = {
            "v1": {"version": "1.0", "allocation": 33},
            "v2": {"version": "2.0", "allocation": 33},
            "v3": {"version": "3.0", "allocation": 34},
        }

        result = orchestrator.create_multi_variant_experiment(
            experiment_id="exp-003",
            name="Multi Variant Test",
            module_name="test_module",
            variants=variants,
        )

        assert result["experiment_id"] == "exp-003"
        mock_manager.create_multi_variant_experiment.assert_called_once()


class TestExperimentLifecycle:
    """测试实验生命周期管理"""

    def test_start_experiment_success(self) -> None:
        """启动实验成功"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_manager = MagicMock()
        orchestrator = ExperimentOrchestrator(experiment_manager=mock_manager)

        result = orchestrator.start_experiment("exp-001")

        assert result is True
        mock_manager.start_experiment.assert_called_once_with("exp-001")

    def test_start_experiment_failure(self) -> None:
        """启动实验失败时返回 False"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_manager = MagicMock()
        mock_manager.start_experiment.side_effect = Exception("Failed")
        orchestrator = ExperimentOrchestrator(experiment_manager=mock_manager)

        result = orchestrator.start_experiment("exp-001")

        assert result is False

    def test_pause_experiment_success(self) -> None:
        """暂停实验成功"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_manager = MagicMock()
        orchestrator = ExperimentOrchestrator(experiment_manager=mock_manager)

        result = orchestrator.pause_experiment("exp-001")

        assert result is True
        mock_manager.pause_experiment.assert_called_once_with("exp-001")

    def test_pause_experiment_failure(self) -> None:
        """暂停实验失败时返回 False"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_manager = MagicMock()
        mock_manager.pause_experiment.side_effect = Exception("Failed")
        orchestrator = ExperimentOrchestrator(experiment_manager=mock_manager)

        result = orchestrator.pause_experiment("exp-001")

        assert result is False

    def test_complete_experiment_success(self) -> None:
        """完成实验成功"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_manager = MagicMock()
        orchestrator = ExperimentOrchestrator(experiment_manager=mock_manager)

        result = orchestrator.complete_experiment("exp-001")

        assert result is True
        mock_manager.complete_experiment.assert_called_once_with("exp-001")

    def test_complete_experiment_failure(self) -> None:
        """完成实验失败时返回 False"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_manager = MagicMock()
        mock_manager.complete_experiment.side_effect = Exception("Failed")
        orchestrator = ExperimentOrchestrator(experiment_manager=mock_manager)

        result = orchestrator.complete_experiment("exp-001")

        assert result is False


class TestVariantAssignment:
    """测试变体分配"""

    def test_get_experiment_variant(self) -> None:
        """获取用户实验变体"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_manager = MagicMock()
        mock_manager.assign_variant.return_value = "treatment"
        orchestrator = ExperimentOrchestrator(experiment_manager=mock_manager)

        result = orchestrator.get_experiment_variant("exp-001", "user-123")

        assert result == "treatment"
        mock_manager.assign_variant.assert_called_once_with("exp-001", "user-123")

    def test_get_experiment_variant_returns_none_on_error(self) -> None:
        """实验未运行时返回 None"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_manager = MagicMock()
        mock_manager.assign_variant.side_effect = Exception("Not running")
        orchestrator = ExperimentOrchestrator(experiment_manager=mock_manager)

        result = orchestrator.get_experiment_variant("exp-001", "user-123")

        assert result is None

    def test_get_prompt_version_for_experiment(self) -> None:
        """获取用户在模块实验中应使用的提示词版本"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_adapter = MagicMock()
        mock_adapter.get_version_for_user.return_value = "1.1.0"
        orchestrator = ExperimentOrchestrator(experiment_adapter=mock_adapter)

        result = orchestrator.get_prompt_version_for_experiment("intent_classifier", "user-123")

        assert result == "1.1.0"
        mock_adapter.get_version_for_user.assert_called_once_with("intent_classifier", "user-123")


class TestMetricsRecording:
    """测试指标记录"""

    def test_record_experiment_metrics(self) -> None:
        """记录实验指标"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_adapter = MagicMock()
        orchestrator = ExperimentOrchestrator(experiment_adapter=mock_adapter)

        orchestrator.record_experiment_metrics(
            module_name="intent_classifier",
            user_id="user-123",
            success=True,
            duration_ms=150,
            satisfaction=4,
        )

        mock_adapter.record_interaction.assert_called_once_with(
            module_name="intent_classifier",
            user_id="user-123",
            success=True,
            duration_ms=150,
            satisfaction=4,
        )

    def test_get_experiment_report(self) -> None:
        """获取实验报告"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_adapter = MagicMock()
        mock_adapter.get_experiment_report.return_value = {
            "experiment_id": "exp-001",
            "variants": {"control": {"success_rate": 0.85}, "treatment": {"success_rate": 0.92}},
        }
        orchestrator = ExperimentOrchestrator(experiment_adapter=mock_adapter)

        result = orchestrator.get_experiment_report("exp-001")

        assert "variants" in result
        mock_adapter.get_experiment_report.assert_called_once_with("exp-001")

    def test_get_experiment_metrics_summary(self) -> None:
        """获取实验指标汇总"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_collector = MagicMock()
        mock_collector.get_metrics_summary.return_value = {"total_interactions": 1000}
        orchestrator = ExperimentOrchestrator(metrics_collector=mock_collector)

        result = orchestrator.get_experiment_metrics_summary("exp-001")

        assert result["total_interactions"] == 1000
        mock_collector.get_metrics_summary.assert_called_once_with("exp-001")


class TestRolloutManagement:
    """测试灰度发布管理"""

    def test_create_rollout_plan(self) -> None:
        """创建灰度发布计划"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_controller = MagicMock()
        mock_plan = MagicMock()
        mock_plan.experiment_id = "exp-001"
        mock_plan.module_name = "intent_classifier"
        mock_plan.new_version = "2.0.0"
        mock_plan.current_stage = 0
        mock_plan.stages = [{"name": "canary", "percentage": 5}]
        mock_controller.create_rollout_plan.return_value = mock_plan

        orchestrator = ExperimentOrchestrator(rollout_controller=mock_controller)

        stages = [{"name": "canary", "percentage": 5, "success_threshold": 0.95}]
        result = orchestrator.create_rollout_plan(
            experiment_id="exp-001",
            module_name="intent_classifier",
            new_version="2.0.0",
            stages=stages,
        )

        assert result["experiment_id"] == "exp-001"
        assert result["new_version"] == "2.0.0"
        mock_controller.create_rollout_plan.assert_called_once()

    def test_advance_rollout_stage(self) -> None:
        """推进灰度发布阶段"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_controller = MagicMock()
        mock_collector = MagicMock()

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.message = "Advanced to stage 1"
        mock_controller.advance_stage.return_value = mock_result

        mock_plan = MagicMock()
        mock_plan.current_stage = 1
        mock_controller.get_plan.return_value = mock_plan

        orchestrator = ExperimentOrchestrator(
            rollout_controller=mock_controller,
            metrics_collector=mock_collector,
        )

        result = orchestrator.advance_rollout_stage("exp-001")

        assert result["success"] is True
        assert result["current_stage"] == 1

    def test_rollback_rollout(self) -> None:
        """回滚灰度发布"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_controller = MagicMock()

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.message = "Rolled back"
        mock_controller.rollback.return_value = mock_result

        mock_plan = MagicMock()
        mock_plan.current_stage = 0
        mock_controller.get_plan.return_value = mock_plan

        orchestrator = ExperimentOrchestrator(rollout_controller=mock_controller)

        result = orchestrator.rollback_rollout("exp-001")

        assert result["success"] is True
        mock_controller.rollback.assert_called_once_with("exp-001")

    def test_should_rollback_rollout(self) -> None:
        """检查是否应该回滚"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_controller = MagicMock()
        mock_collector = MagicMock()
        mock_controller.should_rollback.return_value = True

        orchestrator = ExperimentOrchestrator(
            rollout_controller=mock_controller,
            metrics_collector=mock_collector,
        )

        result = orchestrator.should_rollback_rollout("exp-001")

        assert result is True
        mock_controller.should_rollback.assert_called_once()


class TestExperimentQuery:
    """测试实验查询"""

    def test_get_experiment_audit_logs(self) -> None:
        """获取实验审计日志"""
        from datetime import datetime

        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_manager = MagicMock()
        mock_log = MagicMock()
        mock_log.timestamp = datetime(2025, 1, 1, 12, 0, 0)
        mock_log.action = "started"
        mock_log.actor = "admin"
        mock_log.details = {"reason": "test"}
        mock_manager.get_audit_logs.return_value = [mock_log]

        orchestrator = ExperimentOrchestrator(experiment_manager=mock_manager)

        result = orchestrator.get_experiment_audit_logs("exp-001")

        assert len(result) == 1
        assert result[0]["action"] == "started"
        assert result[0]["actor"] == "admin"

    def test_list_experiments(self) -> None:
        """列出所有实验"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_manager = MagicMock()
        mock_exp = MagicMock()
        mock_exp.to_dict.return_value = {"experiment_id": "exp-001", "status": "running"}
        mock_manager.list_experiments.return_value = [mock_exp]

        orchestrator = ExperimentOrchestrator(experiment_manager=mock_manager)

        result = orchestrator.list_experiments(status="running")

        assert len(result) == 1
        assert result[0]["status"] == "running"
        mock_manager.list_experiments.assert_called_once_with(status="running")

    def test_get_experiment(self) -> None:
        """获取实验详情"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_manager = MagicMock()
        mock_config = MagicMock()
        mock_config.to_dict.return_value = {"experiment_id": "exp-001", "name": "Test"}
        mock_manager.get_experiment.return_value = mock_config

        orchestrator = ExperimentOrchestrator(experiment_manager=mock_manager)

        result = orchestrator.get_experiment("exp-001")

        assert result is not None
        assert result["experiment_id"] == "exp-001"

    def test_get_experiment_not_found(self) -> None:
        """实验不存在时返回 None"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_manager = MagicMock()
        mock_manager.get_experiment.return_value = None

        orchestrator = ExperimentOrchestrator(experiment_manager=mock_manager)

        result = orchestrator.get_experiment("non-existent")

        assert result is None


class TestMetricsThreshold:
    """测试指标阈值检查"""

    def test_check_experiment_metrics_threshold(self) -> None:
        """检查实验指标是否达到阈值"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_collector = MagicMock()
        orchestrator = ExperimentOrchestrator(metrics_collector=mock_collector)

        thresholds = {"success_rate": 0.95, "avg_duration": 5000}

        # Mock the MetricsThresholdChecker at the import location
        with patch(
            "src.domain.services.ab_testing_system.MetricsThresholdChecker"
        ) as MockChecker:
            mock_checker_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.passed = True
            mock_result.details = {"success_rate": {"passed": True, "actual": 0.96}}
            mock_checker_instance.check.return_value = mock_result
            MockChecker.return_value = mock_checker_instance

            result = orchestrator.check_experiment_metrics_threshold(
                experiment_id="exp-001",
                variant="treatment",
                thresholds=thresholds,
            )

            assert result["passed"] is True
            assert "details" in result


class TestLogging:
    """测试日志记录"""

    def test_create_experiment_logs(self) -> None:
        """创建实验时记录日志"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_manager = MagicMock()
        mock_config = MagicMock()
        mock_config.to_dict.return_value = {"experiment_id": "exp-001"}
        mock_manager.create_experiment.return_value = mock_config

        mock_log_collector = MagicMock()
        orchestrator = ExperimentOrchestrator(
            experiment_manager=mock_manager,
            log_collector=mock_log_collector,
        )

        orchestrator.create_experiment(
            experiment_id="exp-001",
            name="Test",
            module_name="test",
            control_version="1.0",
            treatment_version="2.0",
        )

        mock_log_collector.info.assert_called_once()

    def test_start_experiment_logs_on_failure(self) -> None:
        """启动实验失败时记录错误日志"""
        from src.domain.services.experiment_orchestrator import ExperimentOrchestrator

        mock_manager = MagicMock()
        mock_manager.start_experiment.side_effect = Exception("Failed")

        mock_log_collector = MagicMock()
        orchestrator = ExperimentOrchestrator(
            experiment_manager=mock_manager,
            log_collector=mock_log_collector,
        )

        orchestrator.start_experiment("exp-001")

        mock_log_collector.error.assert_called_once()
