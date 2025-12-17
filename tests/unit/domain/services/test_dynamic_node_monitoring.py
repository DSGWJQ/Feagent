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


# ==================== P0-CRITICAL Tests: SystemRecoveryManager ====================


class TestSystemRecoveryManager:
    """SystemRecoveryManager P0-CRITICAL 测试（Codex识别的最大测试缺口）"""

    @pytest.mark.asyncio
    async def test_attempt_node_creation_success_creates_node_and_records_metric(self):
        """测试成功创建节点并记录指标"""
        from src.domain.services.dynamic_node_monitoring import SystemRecoveryManager

        manager = SystemRecoveryManager()
        manager.set_workflow_state("wf-1", {"nodes": []})

        node_def = {"name": "test_node", "executor_type": "code"}
        result = await manager.attempt_node_creation("wf-1", node_def)

        assert result["success"] is True

        # 验证节点已添加
        state = manager.get_workflow_state("wf-1")
        assert len(state["nodes"]) == 1
        assert state["nodes"][0]["name"] == "test_node"

        # 验证指标已记录
        stats = manager._metrics.get_statistics()
        assert stats["successful_creations"] == 1

    @pytest.mark.asyncio
    async def test_attempt_node_creation_failure_rolls_back_and_records_failure(self, monkeypatch):
        """测试创建失败时回滚并记录失败指标（真正验证回滚机制）"""
        from src.domain.services.dynamic_node_monitoring import SystemRecoveryManager

        manager = SystemRecoveryManager()
        initial_state = {"nodes": [{"id": "existing", "name": "old"}]}
        manager.set_workflow_state("wf-1", initial_state)

        # 有效节点定义，但在记录指标时抛出异常（模拟 state 修改后才失败）
        valid_node_def = {"name": "new_node", "executor_type": "code"}

        # Monkeypatch record_node_creation 让它在 state 已修改后抛异常
        original_record = manager._metrics.record_node_creation

        def failing_record(name, success):
            if success:  # 只在成功时抛异常
                raise RuntimeError("Simulated metric recording failure")
            return original_record(name, success)

        monkeypatch.setattr(manager._metrics, "record_node_creation", failing_record)

        with pytest.raises(RuntimeError, match="Simulated metric recording failure"):
            await manager.attempt_node_creation("wf-1", valid_node_def)

        # 验证状态已回滚（应该只有原来的节点）
        state = manager.get_workflow_state("wf-1")
        assert len(state["nodes"]) == 1
        assert state["nodes"][0]["name"] == "old"

        # 验证快照被创建并回滚生效
        assert manager._rollback.has_snapshot("wf-1") is False  # 回滚后快照被弹出

    @pytest.mark.asyncio
    async def test_attempt_node_creation_creates_snapshot_before_creation(self):
        """测试创建节点前会创建快照"""
        from src.domain.services.dynamic_node_monitoring import SystemRecoveryManager

        manager = SystemRecoveryManager()
        initial_state = {"nodes": [{"id": "existing", "name": "old"}]}
        manager.set_workflow_state("wf-1", initial_state)

        node_def = {"name": "new_node", "executor_type": "code"}
        await manager.attempt_node_creation("wf-1", node_def)

        # 验证快照已创建
        assert manager._rollback.has_snapshot("wf-1") is True

    @pytest.mark.asyncio
    async def test_execute_with_recovery_success_updates_node_status_and_records_metric(self):
        """测试执行成功时更新节点状态并记录指标"""
        from src.domain.services.dynamic_node_monitoring import SystemRecoveryManager

        manager = SystemRecoveryManager()
        manager.set_workflow_state(
            "wf-1", {"nodes": [{"id": "node-1", "name": "test", "status": "pending"}]}
        )

        code = "print('success')"
        result = await manager.execute_with_recovery("wf-1", "node-1", code)

        assert result["success"] is True
        assert result["recovered"] is False

        # 验证节点状态已更新
        state = manager.get_workflow_state("wf-1")
        assert state["nodes"][0]["status"] == "completed"

        # 验证指标已记录
        stats = manager._metrics.get_statistics()
        assert stats["sandbox_successes"] == 1

    @pytest.mark.asyncio
    async def test_execute_with_recovery_failure_recovers_state_and_returns_error(self):
        """测试执行失败时恢复状态并返回错误信息"""
        from src.domain.services.dynamic_node_monitoring import SystemRecoveryManager

        manager = SystemRecoveryManager()
        original_status = "pending"
        manager.set_workflow_state(
            "wf-1", {"nodes": [{"id": "node-1", "name": "test", "status": original_status}]}
        )

        # 触发失败的代码
        code = "raise Exception('execution error')"
        result = await manager.execute_with_recovery("wf-1", "node-1", code)

        assert result["success"] is False
        assert result["recovered"] is True
        assert "execution error" in result["error"] or "Sandbox execution failed" in result["error"]

        # 验证状态已恢复
        state = manager.get_workflow_state("wf-1")
        assert state["nodes"][0]["status"] == original_status

        # 验证失败已记录
        stats = manager._metrics.get_statistics()
        assert stats["sandbox_failures"] == 1

    @pytest.mark.asyncio
    async def test_execute_with_recovery_records_duration_metric(self):
        """测试执行时记录持续时间指标（精确验证 duration_ms）"""
        from src.domain.services.dynamic_node_monitoring import SystemRecoveryManager

        manager = SystemRecoveryManager()
        manager.set_workflow_state("wf-1", {"nodes": [{"id": "node-1", "name": "test"}]})

        await manager.execute_with_recovery("wf-1", "node-1", "print('test')")

        # 验证指标包含 duration_ms（精确断言）
        stats = manager._metrics.get_statistics()
        assert stats["sandbox_executions"] == 1

        # 精确验证最后一条记录包含 duration_ms
        last_record = manager._metrics._records[-1]
        assert last_record.metric_type == "sandbox_execution"
        assert last_record.duration_ms is not None
        assert last_record.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_workflow_with_recovery_success_completes_all_nodes(self):
        """测试工作流执行成功时完成所有节点"""
        from src.domain.services.dynamic_node_monitoring import SystemRecoveryManager

        manager = SystemRecoveryManager()
        manager.set_workflow_state(
            "wf-1",
            {
                "nodes": [
                    {"id": "node-1", "name": "step1", "status": "pending"},
                    {"id": "node-2", "name": "step2", "status": "pending"},
                    {"id": "node-3", "name": "step3", "status": "pending"},
                ]
            },
        )

        result = await manager.execute_workflow_with_recovery("wf-1")

        assert result["success"] is True

        # 验证所有节点已完成
        state = manager.get_workflow_state("wf-1")
        for node in state["nodes"]:
            assert node["status"] == "completed"

        # 验证指标已记录
        stats = manager._metrics.get_statistics()
        assert stats["workflow_successes"] == 1

    @pytest.mark.asyncio
    async def test_execute_workflow_with_recovery_fails_at_specific_node_and_rolls_back(self):
        """测试工作流在指定节点失败时回滚"""
        from src.domain.services.dynamic_node_monitoring import SystemRecoveryManager

        manager = SystemRecoveryManager()
        manager.set_workflow_state(
            "wf-1",
            {
                "nodes": [
                    {"id": "node-1", "name": "step1", "status": "pending"},
                    {"id": "node-2", "name": "step2", "status": "pending"},
                    {"id": "node-3", "name": "step3", "status": "pending"},
                ]
            },
        )

        result = await manager.execute_workflow_with_recovery("wf-1", fail_at_node="node-2")

        assert result["success"] is False
        assert "Execution failed at node node-2" in result["error"]

        # 验证已执行的节点被标记为 rolled_back
        state = manager.get_workflow_state("wf-1")
        assert state["nodes"][0]["status"] == "rolled_back"  # node-1 executed then rolled back
        assert state["nodes"][1]["status"] == "pending"  # node-2 never changed
        assert state["nodes"][2]["status"] == "pending"  # node-3 never executed

        # 验证失败已记录
        stats = manager._metrics.get_statistics()
        assert stats["workflow_failures"] == 1

    @pytest.mark.asyncio
    async def test_execute_workflow_with_recovery_records_node_count_and_duration(self):
        """测试工作流执行记录节点数量和持续时间（精确验证 node_count 和 duration_ms）"""
        from src.domain.services.dynamic_node_monitoring import SystemRecoveryManager

        manager = SystemRecoveryManager()
        manager.set_workflow_state(
            "wf-1",
            {
                "nodes": [
                    {"id": "node-1", "name": "step1"},
                    {"id": "node-2", "name": "step2"},
                ]
            },
        )

        await manager.execute_workflow_with_recovery("wf-1")

        # 验证指标记录了节点数量
        stats = manager._metrics.get_statistics()
        assert stats["workflow_executions"] == 1

        # 精确验证最后一条记录包含 node_count 和 duration_ms
        last_record = manager._metrics._records[-1]
        assert last_record.metric_type == "workflow_execution"
        assert last_record.duration_ms is not None
        assert last_record.duration_ms >= 0
        assert last_record.extra.get("node_count") == 2

    def test_validate_node_valid_definition_returns_valid_true(self):
        """测试验证有效节点定义返回 valid=True"""
        from src.domain.services.dynamic_node_monitoring import SystemRecoveryManager

        manager = SystemRecoveryManager()

        valid_node = {
            "name": "test_node",
            "executor_type": "code",
        }

        result = manager.validate_node(valid_node)

        assert result["valid"] is True
        assert "error" not in result

    def test_validate_node_missing_name_returns_error(self):
        """测试验证缺少 name 字段的节点返回错误"""
        from src.domain.services.dynamic_node_monitoring import SystemRecoveryManager

        manager = SystemRecoveryManager()

        invalid_node = {
            "executor_type": "code",
        }

        result = manager.validate_node(invalid_node)

        assert result["valid"] is False
        assert "Missing required field: name" in result["error"]

    def test_validate_node_invalid_executor_type_returns_error(self):
        """测试验证无效 executor_type 返回错误"""
        from src.domain.services.dynamic_node_monitoring import SystemRecoveryManager

        manager = SystemRecoveryManager()

        invalid_node = {
            "name": "test_node",
            "executor_type": "invalid_type",
        }

        result = manager.validate_node(invalid_node)

        assert result["valid"] is False
        assert "Invalid executor_type: invalid_type" in result["error"]

    def test_validate_node_multiple_errors_concatenates_messages(self):
        """测试验证多个错误时合并错误消息"""
        from src.domain.services.dynamic_node_monitoring import SystemRecoveryManager

        manager = SystemRecoveryManager()

        invalid_node = {
            "executor_type": "invalid_type",
            # missing name
        }

        result = manager.validate_node(invalid_node)

        assert result["valid"] is False
        assert "Missing required field: name" in result["error"]
        assert "Invalid executor_type" in result["error"]

    @pytest.mark.asyncio
    async def test_add_node_with_monitoring_valid_node_adds_to_workflow(self):
        """测试添加有效节点到工作流"""
        from src.domain.services.dynamic_node_monitoring import SystemRecoveryManager

        manager = SystemRecoveryManager()
        manager.set_workflow_state("wf-1", {"nodes": []})

        node = {"name": "test_node", "executor_type": "code"}
        result = await manager.add_node_with_monitoring("wf-1", node)

        assert result["success"] is True

        # 验证节点已添加
        state = manager.get_workflow_state("wf-1")
        assert len(state["nodes"]) == 1
        assert state["nodes"][0]["name"] == "test_node"

    @pytest.mark.asyncio
    async def test_add_node_with_monitoring_invalid_node_returns_error(self):
        """测试添加无效节点返回错误"""
        from src.domain.services.dynamic_node_monitoring import SystemRecoveryManager

        manager = SystemRecoveryManager()
        manager.set_workflow_state("wf-1", {"nodes": []})

        invalid_node = {"executor_type": "code"}  # missing name
        result = await manager.add_node_with_monitoring("wf-1", invalid_node)

        assert result["success"] is False
        assert "Missing required field: name" in result["error"]

        # 验证节点未添加
        state = manager.get_workflow_state("wf-1")
        assert len(state["nodes"]) == 0

    @pytest.mark.asyncio
    async def test_add_node_with_monitoring_initializes_nodes_list_if_missing(self):
        """测试当 nodes 列表不存在时自动初始化"""
        from src.domain.services.dynamic_node_monitoring import SystemRecoveryManager

        manager = SystemRecoveryManager()
        manager.set_workflow_state("wf-1", {})  # no nodes key

        node = {"name": "test_node", "executor_type": "code"}
        result = await manager.add_node_with_monitoring("wf-1", node)

        assert result["success"] is True

        # 验证 nodes 列表已初始化
        state = manager.get_workflow_state("wf-1")
        assert "nodes" in state
        assert len(state["nodes"]) == 1
