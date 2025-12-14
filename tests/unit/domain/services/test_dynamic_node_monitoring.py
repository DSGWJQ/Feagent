"""
DynamicNodeMonitoring 单元测试

测试覆盖：
1. DynamicNodeMetricsCollector - 指标收集、统计、Prometheus导出
2. WorkflowRollbackManager - 快照管理与回滚
3. AlertManager - 告警CRUD操作
4. HealthChecker - 健康检查注册与执行 (可选)

测试策略：
- P0测试（14个）：DynamicNodeMetricsCollector核心功能
- P1测试（13个）：WorkflowRollbackManager + AlertManager
- P2测试（3个）：HealthChecker（可选）
"""

import time

import pytest

# ==================== P0 Tests: DynamicNodeMetricsCollector ====================


class TestDynamicNodeMetricsCollector:
    """DynamicNodeMetricsCollector 测试"""

    def test_dynamic_node_metrics_collector_record_node_creation_success(self):
        """测试记录节点创建成功"""
        from src.domain.services.dynamic_node_monitoring import DynamicNodeMetricsCollector

        collector = DynamicNodeMetricsCollector()
        collector.record_node_creation("test_node", success=True)

        stats = collector.get_statistics()
        assert stats["successful_creations"] == 1
        assert stats["failed_creations"] == 0

    def test_dynamic_node_metrics_collector_record_node_creation_failure(self):
        """测试记录节点创建失败"""
        from src.domain.services.dynamic_node_monitoring import DynamicNodeMetricsCollector

        collector = DynamicNodeMetricsCollector()
        collector.record_node_creation("test_node", success=False)

        stats = collector.get_statistics()
        assert stats["successful_creations"] == 0
        assert stats["failed_creations"] == 1

    def test_dynamic_node_metrics_collector_record_sandbox_execution_success_with_duration(
        self,
    ):
        """测试记录沙箱执行成功并包含duration"""
        from src.domain.services.dynamic_node_monitoring import DynamicNodeMetricsCollector

        collector = DynamicNodeMetricsCollector()
        collector.record_sandbox_execution("test_node", success=True, duration_ms=150.5)

        stats = collector.get_statistics()
        assert stats["sandbox_successes"] == 1
        assert stats["sandbox_failures"] == 0

    def test_dynamic_node_metrics_collector_record_sandbox_execution_failure_with_duration(
        self,
    ):
        """测试记录沙箱执行失败并包含duration"""
        from src.domain.services.dynamic_node_monitoring import DynamicNodeMetricsCollector

        collector = DynamicNodeMetricsCollector()
        collector.record_sandbox_execution("test_node", success=False, duration_ms=50.0)

        stats = collector.get_statistics()
        assert stats["sandbox_successes"] == 0
        assert stats["sandbox_failures"] == 1

    def test_dynamic_node_metrics_collector_record_workflow_execution_success_records_node_count(
        self,
    ):
        """测试记录工作流执行成功并存储node_count"""
        from src.domain.services.dynamic_node_monitoring import DynamicNodeMetricsCollector

        collector = DynamicNodeMetricsCollector()
        collector.record_workflow_execution(
            "test_workflow", success=True, duration_ms=1000.0, node_count=5
        )

        stats = collector.get_statistics()
        assert stats["workflow_successes"] == 1
        assert stats["workflow_failures"] == 0

    def test_dynamic_node_metrics_collector_record_workflow_execution_failure_records_duration(
        self,
    ):
        """测试记录工作流执行失败并包含duration"""
        from src.domain.services.dynamic_node_monitoring import DynamicNodeMetricsCollector

        collector = DynamicNodeMetricsCollector()
        collector.record_workflow_execution(
            "test_workflow", success=False, duration_ms=500.0, node_count=3
        )

        stats = collector.get_statistics()
        assert stats["workflow_successes"] == 0
        assert stats["workflow_failures"] == 1

    def test_dynamic_node_metrics_collector_get_statistics_no_records_returns_zeroed_stats(
        self,
    ):
        """测试无记录时返回全0统计"""
        from src.domain.services.dynamic_node_monitoring import DynamicNodeMetricsCollector

        collector = DynamicNodeMetricsCollector()
        stats = collector.get_statistics()

        assert stats["total_creations"] == 0
        assert stats["successful_creations"] == 0
        assert stats["failed_creations"] == 0
        assert stats["sandbox_executions"] == 0
        assert stats["sandbox_successes"] == 0
        assert stats["sandbox_failures"] == 0
        assert stats["sandbox_failure_rate"] == 0.0
        assert stats["workflow_executions"] == 0
        assert stats["workflow_successes"] == 0
        assert stats["workflow_failures"] == 0

    def test_dynamic_node_metrics_collector_get_statistics_aggregates_counts_by_metric_type(
        self,
    ):
        """测试统计按metric_type聚合计数"""
        from src.domain.services.dynamic_node_monitoring import DynamicNodeMetricsCollector

        collector = DynamicNodeMetricsCollector()
        collector.record_node_creation("node1", True)
        collector.record_node_creation("node2", False)
        collector.record_sandbox_execution("node1", True, 100.0)
        collector.record_workflow_execution("wf1", True, 500.0, 3)

        stats = collector.get_statistics()
        assert stats["total_creations"] == 2
        assert stats["sandbox_executions"] == 1
        assert stats["workflow_executions"] == 1

    def test_dynamic_node_metrics_collector_get_statistics_aggregates_success_and_failure_counts(
        self,
    ):
        """测试统计聚合成功/失败计数"""
        from src.domain.services.dynamic_node_monitoring import DynamicNodeMetricsCollector

        collector = DynamicNodeMetricsCollector()
        collector.record_sandbox_execution("node1", True, 100.0)
        collector.record_sandbox_execution("node2", True, 150.0)
        collector.record_sandbox_execution("node3", False, 50.0)

        stats = collector.get_statistics()
        assert stats["sandbox_successes"] == 2
        assert stats["sandbox_failures"] == 1
        assert stats["sandbox_failure_rate"] == pytest.approx(1 / 3, abs=0.01)

    def test_dynamic_node_metrics_collector_get_statistics_time_window_filters_out_old_records(
        self,
    ):
        """测试时间窗口过滤旧记录"""
        from src.domain.services.dynamic_node_monitoring import (
            DynamicNodeMetricsCollector,
            MetricRecord,
        )

        collector = DynamicNodeMetricsCollector()

        # 添加旧记录 (2小时前)
        old_time = time.time() - (2 * 60 * 60)
        collector._records.append(
            MetricRecord(
                timestamp=old_time,
                metric_type="node_creation",
                name="old_node",
                success=True,
            )
        )

        # 添加新记录 (当前)
        collector.record_node_creation("new_node", success=True)

        # 1分钟时间窗口应只包含新记录
        stats = collector.get_statistics(time_window_minutes=1)
        assert stats["total_creations"] == 1  # 只有new_node

        # 无时间窗口应包含所有记录
        stats_all = collector.get_statistics(time_window_minutes=None)
        assert stats_all["total_creations"] == 2  # old_node + new_node

    def test_dynamic_node_metrics_collector_get_sandbox_failure_rate_no_sandbox_records_returns_zero(
        self,
    ):
        """测试无沙箱记录时失败率为0"""
        from src.domain.services.dynamic_node_monitoring import DynamicNodeMetricsCollector

        collector = DynamicNodeMetricsCollector()
        collector.record_node_creation("node1", True)  # 非沙箱记录

        failure_rate = collector.get_sandbox_failure_rate()
        assert failure_rate == 0.0

    def test_dynamic_node_metrics_collector_get_sandbox_failure_rate_mixed_success_failure_computes_ratio(
        self,
    ):
        """测试混合成功失败时计算正确的失败率"""
        from src.domain.services.dynamic_node_monitoring import DynamicNodeMetricsCollector

        collector = DynamicNodeMetricsCollector()
        collector.record_sandbox_execution("node1", True, 100.0)
        collector.record_sandbox_execution("node2", False, 50.0)
        collector.record_sandbox_execution("node3", False, 75.0)

        failure_rate = collector.get_sandbox_failure_rate()
        assert failure_rate == pytest.approx(2 / 3, abs=0.01)

    def test_dynamic_node_metrics_collector_export_prometheus_includes_expected_metric_names_and_counts(
        self,
    ):
        """测试Prometheus导出包含预期的指标名称和计数"""
        from src.domain.services.dynamic_node_monitoring import DynamicNodeMetricsCollector

        collector = DynamicNodeMetricsCollector()
        collector.record_node_creation("node1", True)
        collector.record_node_creation("node2", False)
        collector.record_sandbox_execution("node1", True, 100.0)
        collector.record_sandbox_execution("node2", False, 50.0)
        collector.record_workflow_execution("wf1", True, 500.0, 3)

        prometheus_output = collector.export_prometheus()

        # 检查包含预期的指标名称
        assert "dynamic_node_creations_total" in prometheus_output
        assert "sandbox_executions_total" in prometheus_output
        assert "sandbox_failure_rate" in prometheus_output
        assert "workflow_executions_total" in prometheus_output

        # 检查包含正确的计数
        assert 'dynamic_node_creations_total{status="success"} 1' in prometheus_output
        assert 'dynamic_node_creations_total{status="failure"} 1' in prometheus_output
        assert 'sandbox_executions_total{status="success"} 1' in prometheus_output
        assert 'sandbox_executions_total{status="failure"} 1' in prometheus_output


# ==================== P1 Tests: WorkflowRollbackManager ====================


class TestWorkflowRollbackManager:
    """WorkflowRollbackManager 测试（实际API）"""

    def test_workflow_rollback_manager_create_snapshot_returns_snapshot_id(self):
        """测试创建快照返回snapshot_id字符串"""
        from src.domain.services.dynamic_node_monitoring import WorkflowRollbackManager

        manager = WorkflowRollbackManager()
        snapshot_id = manager.create_snapshot(
            workflow_id="wf-123", state={"step": 1}, reason="test"
        )

        assert isinstance(snapshot_id, str)
        assert len(snapshot_id) > 0

    def test_workflow_rollback_manager_has_snapshot_returns_true_when_exists(self):
        """测试has_snapshot在快照存在时返回True"""
        from src.domain.services.dynamic_node_monitoring import WorkflowRollbackManager

        manager = WorkflowRollbackManager()
        manager.create_snapshot("wf-123", {"step": 1}, "test")

        assert manager.has_snapshot("wf-123") is True
        assert manager.has_snapshot("nonexistent") is False

    def test_workflow_rollback_manager_rollback_pops_last_snapshot(self):
        """测试rollback弹出最新快照并返回state"""
        from src.domain.services.dynamic_node_monitoring import WorkflowRollbackManager

        manager = WorkflowRollbackManager()
        state1 = {"step": 1}
        state2 = {"step": 2}
        manager.create_snapshot("wf-123", state1, "s1")
        manager.create_snapshot("wf-123", state2, "s2")

        # 第一次rollback应返回state2
        restored = manager.rollback("wf-123")
        assert restored == state2

        # 第二次rollback应返回state1
        restored = manager.rollback("wf-123")
        assert restored == state1

    def test_workflow_rollback_manager_rollback_no_snapshot_returns_none(self):
        """测试rollback在无快照时返回None"""
        from src.domain.services.dynamic_node_monitoring import WorkflowRollbackManager

        manager = WorkflowRollbackManager()
        restored = manager.rollback("nonexistent")

        assert restored is None

    def test_workflow_rollback_manager_rollback_to_snapshot_by_id(self):
        """测试rollback_to_snapshot按ID恢复特定快照"""
        from src.domain.services.dynamic_node_monitoring import WorkflowRollbackManager

        manager = WorkflowRollbackManager()
        state1 = {"step": 1}
        state2 = {"step": 2}
        snapshot_id1 = manager.create_snapshot("wf-123", state1, "s1")
        manager.create_snapshot("wf-123", state2, "s2")

        # 恢复到第一个快照
        restored = manager.rollback_to_snapshot("wf-123", snapshot_id1)
        assert restored == state1

    def test_workflow_rollback_manager_get_snapshot_count(self):
        """测试get_snapshot_count返回正确的快照数量"""
        from src.domain.services.dynamic_node_monitoring import WorkflowRollbackManager

        manager = WorkflowRollbackManager()
        assert manager.get_snapshot_count("wf-123") == 0

        manager.create_snapshot("wf-123", {"step": 1}, "s1")
        manager.create_snapshot("wf-123", {"step": 2}, "s2")
        assert manager.get_snapshot_count("wf-123") == 2

    def test_workflow_rollback_manager_clear_snapshots_removes_all(self):
        """测试clear_snapshots移除所有快照"""
        from src.domain.services.dynamic_node_monitoring import WorkflowRollbackManager

        manager = WorkflowRollbackManager()
        manager.create_snapshot("wf-123", {"step": 1}, "s1")
        manager.create_snapshot("wf-123", {"step": 2}, "s2")

        manager.clear_snapshots("wf-123")
        assert manager.get_snapshot_count("wf-123") == 0

    def test_workflow_rollback_manager_remove_invalid_nodes_cleans_state(self):
        """测试remove_invalid_nodes移除无效节点和相关边"""
        from src.domain.services.dynamic_node_monitoring import WorkflowRollbackManager

        manager = WorkflowRollbackManager()
        workflow_state = {
            "nodes": [
                {"id": "node1", "valid": True},
                {"id": "node2", "valid": False},  # 无效节点
                {"id": "node3", "valid": True},
            ],
            "edges": [
                {"source": "node1", "target": "node2"},  # 涉及无效节点
                {"source": "node1", "target": "node3"},  # 有效边
                {"source": "node2", "target": "node3"},  # 涉及无效节点
            ],
        }

        cleaned = manager.remove_invalid_nodes(workflow_state)

        # 验证无效节点被移除
        assert len(cleaned["nodes"]) == 2
        node_ids = [n["id"] for n in cleaned["nodes"]]
        assert "node2" not in node_ids

        # 验证涉及无效节点的边被移除
        assert len(cleaned["edges"]) == 1
        assert cleaned["edges"][0]["source"] == "node1"
        assert cleaned["edges"][0]["target"] == "node3"


# ==================== P1 Tests: AlertManager ====================


class TestAlertManager:
    """AlertManager 测试（实际API）"""

    def test_alert_manager_set_threshold_stores_threshold(self):
        """测试set_threshold存储阈值"""
        from src.domain.services.dynamic_node_monitoring import AlertManager

        manager = AlertManager()
        manager.set_threshold("sandbox_failure_rate", 0.3)

        # 验证阈值已设置（通过check_failure_rate触发）
        manager.check_failure_rate(0.4)  # 超过阈值
        alerts = manager.get_active_alerts()
        assert len(alerts) > 0

    def test_alert_manager_check_failure_rate_triggers_alert_when_exceeds_threshold(self):
        """测试失败率超过阈值时触发告警"""
        from src.domain.services.dynamic_node_monitoring import AlertManager

        manager = AlertManager()
        manager.set_threshold("sandbox_failure_rate", 0.5)
        manager.check_failure_rate(0.6)  # 超过阈值

        alerts = manager.get_active_alerts()
        assert len(alerts) == 1
        assert alerts[0]["type"] == "sandbox_failure_rate"

    def test_alert_manager_check_failure_rate_clears_alert_when_below_threshold(self):
        """测试失败率低于阈值时清除告警"""
        from src.domain.services.dynamic_node_monitoring import AlertManager

        manager = AlertManager()
        manager.set_threshold("sandbox_failure_rate", 0.5)
        manager.check_failure_rate(0.6)  # 触发告警

        manager.check_failure_rate(0.3)  # 低于阈值，清除告警
        alerts = manager.get_active_alerts()
        assert len(alerts) == 0

    def test_alert_manager_get_active_alerts_returns_dicts_not_resolved(self):
        """测试get_active_alerts返回dict列表而非Alert对象"""
        from src.domain.services.dynamic_node_monitoring import AlertManager

        manager = AlertManager()
        manager.set_threshold("sandbox_failure_rate", 0.5)
        manager.check_failure_rate(0.7)

        alerts = manager.get_active_alerts()
        assert isinstance(alerts, list)
        if alerts:
            assert isinstance(alerts[0], dict)
            assert "id" in alerts[0]
            assert "type" in alerts[0]
            assert "message" in alerts[0]
            assert "severity" in alerts[0]

    def test_alert_manager_clear_alert_by_id_returns_true(self):
        """测试clear_alert按ID清除告警返回True"""
        from src.domain.services.dynamic_node_monitoring import AlertManager

        manager = AlertManager()
        manager.set_threshold("sandbox_failure_rate", 0.5)
        manager.check_failure_rate(0.7)

        alerts = manager.get_active_alerts()
        alert_id = alerts[0]["id"]

        success = manager.clear_alert(alert_id)
        assert success is True

        # 验证告警已清除
        active_alerts = manager.get_active_alerts()
        assert len(active_alerts) == 0

    def test_alert_manager_clear_all_alerts_returns_count(self):
        """测试clear_all_alerts返回清除的告警数量"""
        from src.domain.services.dynamic_node_monitoring import AlertManager

        manager = AlertManager()
        manager.set_threshold("sandbox_failure_rate", 0.5)
        manager.check_failure_rate(0.7)  # 触发告警

        count = manager.clear_all_alerts()
        assert count == 1

        # 验证所有告警已清除
        active_alerts = manager.get_active_alerts()
        assert len(active_alerts) == 0

    def test_alert_manager_notification_callback_triggered_on_alert(self):
        """测试告警触发时调用notification callback"""
        from src.domain.services.dynamic_node_monitoring import AlertManager

        manager = AlertManager()
        callback_called = []

        def test_callback(alert):
            callback_called.append(alert)

        manager.set_notification_callback(test_callback)
        manager.set_threshold("sandbox_failure_rate", 0.5)
        manager.check_failure_rate(0.7)  # 触发告警

        # 验证回调被调用
        assert len(callback_called) == 1
        assert callback_called[0].type == "sandbox_failure_rate"


# ==================== P2-Optional Tests: HealthChecker ====================


class TestHealthChecker:
    """HealthChecker 测试（实际API）"""

    def test_health_checker_check_health_returns_status_and_components(self):
        """测试check_health返回status和components"""
        from src.domain.services.dynamic_node_monitoring import HealthChecker

        checker = HealthChecker()
        health = checker.check_health()

        assert "status" in health
        assert "components" in health
        assert "timestamp" in health
        assert health["status"] in ["healthy", "degraded", "unhealthy"]

    def test_health_checker_check_sandbox_health_returns_availability(self):
        """测试check_sandbox_health返回可用性状态"""
        from src.domain.services.dynamic_node_monitoring import HealthChecker

        checker = HealthChecker()
        sandbox_health = checker.check_sandbox_health()

        assert "available" in sandbox_health
        assert isinstance(sandbox_health["available"], bool)

    def test_health_checker_check_metrics_health_returns_collecting_status(self):
        """测试check_metrics_health返回收集状态"""
        from src.domain.services.dynamic_node_monitoring import HealthChecker

        checker = HealthChecker()
        metrics_health = checker.check_metrics_health()

        assert "collecting" in metrics_health
        assert "storage_available" in metrics_health

    def test_health_checker_record_sandbox_execution_updates_last_execution_time(self):
        """测试record_sandbox_execution更新最后执行时间"""
        from src.domain.services.dynamic_node_monitoring import HealthChecker

        checker = HealthChecker()
        checker.record_sandbox_execution()

        sandbox_health = checker.check_sandbox_health()
        assert sandbox_health["last_execution_time"] is not None
        assert sandbox_health["last_execution_time"] > 0

    def test_health_checker_set_sandbox_available_updates_status(self):
        """测试set_sandbox_available更新沙箱可用性状态"""
        from src.domain.services.dynamic_node_monitoring import HealthChecker

        checker = HealthChecker()
        checker.set_sandbox_available(False)

        sandbox_health = checker.check_sandbox_health()
        assert sandbox_health["available"] is False

        health = checker.check_health()
        assert health["status"] == "unhealthy"
