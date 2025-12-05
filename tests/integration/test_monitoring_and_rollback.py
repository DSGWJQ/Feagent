"""
TDD 测试：监控、回滚与系统恢复 (Step 9)

测试范围：
1. DynamicNodeMetrics - 动态节点监控指标
2. WorkflowRollbackManager - 失败回滚机制
3. SystemRecovery - 系统恢复验证
4. 回归测试：完整流程测试
"""

import pytest

# ==================== 1. 监控指标测试 ====================


class TestDynamicNodeMetrics:
    """测试：动态节点监控指标"""

    @pytest.fixture
    def metrics_collector(self):
        """创建指标收集器"""
        from src.domain.services.dynamic_node_monitoring import DynamicNodeMetricsCollector

        return DynamicNodeMetricsCollector()

    def test_track_node_creation(self, metrics_collector):
        """测试：跟踪节点创建"""
        metrics_collector.record_node_creation("test_node_1", success=True)
        metrics_collector.record_node_creation("test_node_2", success=True)
        metrics_collector.record_node_creation("test_node_3", success=False)

        stats = metrics_collector.get_statistics()

        assert stats["total_creations"] == 3
        assert stats["successful_creations"] == 2
        assert stats["failed_creations"] == 1

    def test_track_sandbox_execution(self, metrics_collector):
        """测试：跟踪沙箱执行"""
        metrics_collector.record_sandbox_execution("node_1", success=True, duration_ms=100)
        metrics_collector.record_sandbox_execution("node_2", success=True, duration_ms=200)
        metrics_collector.record_sandbox_execution("node_3", success=False, duration_ms=50)

        stats = metrics_collector.get_statistics()

        assert stats["sandbox_executions"] == 3
        assert stats["sandbox_successes"] == 2
        assert stats["sandbox_failures"] == 1
        assert stats["sandbox_failure_rate"] == pytest.approx(1 / 3, rel=0.01)

    def test_track_workflow_execution(self, metrics_collector):
        """测试：跟踪工作流执行"""
        metrics_collector.record_workflow_execution(
            "workflow_1", success=True, duration_ms=1000, node_count=3
        )
        metrics_collector.record_workflow_execution(
            "workflow_2", success=False, duration_ms=500, node_count=2
        )

        stats = metrics_collector.get_statistics()

        assert stats["workflow_executions"] == 2
        assert stats["workflow_successes"] == 1
        assert stats["workflow_failures"] == 1

    def test_calculate_failure_rate(self, metrics_collector):
        """测试：计算失败率"""
        for i in range(7):
            metrics_collector.record_sandbox_execution(f"node_{i}", success=True, duration_ms=100)
        for i in range(3):
            metrics_collector.record_sandbox_execution(f"fail_{i}", success=False, duration_ms=50)

        failure_rate = metrics_collector.get_sandbox_failure_rate()

        assert failure_rate == pytest.approx(0.3, rel=0.01)  # 3/10 = 30%

    def test_get_metrics_by_time_window(self, metrics_collector):
        """测试：按时间窗口获取指标"""
        # 记录一些指标
        metrics_collector.record_node_creation("node_1", success=True)
        metrics_collector.record_node_creation("node_2", success=True)

        # 获取最近 1 小时的指标
        stats = metrics_collector.get_statistics(time_window_minutes=60)

        assert stats["total_creations"] >= 2

    def test_export_prometheus_format(self, metrics_collector):
        """测试：导出 Prometheus 格式"""
        metrics_collector.record_node_creation("test", success=True)
        metrics_collector.record_sandbox_execution("test", success=True, duration_ms=100)

        prometheus_output = metrics_collector.export_prometheus()

        assert "dynamic_node_creations_total" in prometheus_output
        assert "sandbox_executions_total" in prometheus_output
        assert "sandbox_failure_rate" in prometheus_output


# ==================== 2. 回滚机制测试 ====================


class TestWorkflowRollbackManager:
    """测试：工作流回滚管理器"""

    @pytest.fixture
    def rollback_manager(self):
        """创建回滚管理器"""
        from src.domain.services.dynamic_node_monitoring import WorkflowRollbackManager

        return WorkflowRollbackManager()

    def test_create_snapshot_before_change(self, rollback_manager):
        """测试：变更前创建快照"""
        workflow_state = {
            "id": "workflow_1",
            "nodes": [{"id": "node_1", "type": "LLM"}],
            "edges": [],
        }

        snapshot_id = rollback_manager.create_snapshot(
            workflow_id="workflow_1",
            state=workflow_state,
            reason="添加新节点前",
        )

        assert snapshot_id is not None
        assert rollback_manager.has_snapshot("workflow_1")

    def test_rollback_to_snapshot(self, rollback_manager):
        """测试：回滚到快照"""
        original_state = {
            "id": "workflow_1",
            "nodes": [{"id": "node_1", "type": "LLM"}],
            "edges": [],
        }
        rollback_manager.create_snapshot("workflow_1", original_state, "before change")

        # 模拟变更后的状态（在实际场景中会被应用到工作流）
        # 这里只是演示回滚可以恢复到原始状态
        _ = {
            "id": "workflow_1",
            "nodes": [
                {"id": "node_1", "type": "LLM"},
                {"id": "node_2", "type": "INVALID"},  # 无效节点
            ],
            "edges": [],
        }

        # 执行回滚
        restored_state = rollback_manager.rollback("workflow_1")

        assert restored_state is not None
        assert len(restored_state["nodes"]) == 1
        assert restored_state["nodes"][0]["id"] == "node_1"

    def test_delete_invalid_nodes(self, rollback_manager):
        """测试：删除无效节点"""
        workflow_state = {
            "id": "workflow_1",
            "nodes": [
                {"id": "node_1", "type": "LLM", "valid": True},
                {"id": "node_2", "type": "INVALID", "valid": False},
                {"id": "node_3", "type": "CODE", "valid": True},
            ],
            "edges": [
                {"source": "node_1", "target": "node_2"},
                {"source": "node_2", "target": "node_3"},
            ],
        }

        cleaned_state = rollback_manager.remove_invalid_nodes(workflow_state)

        # 验证无效节点被删除
        node_ids = [n["id"] for n in cleaned_state["nodes"]]
        assert "node_2" not in node_ids
        assert "node_1" in node_ids
        assert "node_3" in node_ids

        # 验证相关边也被删除
        for edge in cleaned_state["edges"]:
            assert edge["source"] != "node_2"
            assert edge["target"] != "node_2"

    def test_rollback_with_multiple_snapshots(self, rollback_manager):
        """测试：多快照回滚"""
        # 创建多个快照
        state_v1 = {"id": "wf", "nodes": [{"id": "n1"}], "version": 1}
        state_v2 = {"id": "wf", "nodes": [{"id": "n1"}, {"id": "n2"}], "version": 2}
        state_v3 = {"id": "wf", "nodes": [{"id": "n1"}, {"id": "n2"}, {"id": "n3"}], "version": 3}

        rollback_manager.create_snapshot("wf", state_v1, "v1")
        rollback_manager.create_snapshot("wf", state_v2, "v2")
        rollback_manager.create_snapshot("wf", state_v3, "v3")

        # 回滚到上一个版本
        restored = rollback_manager.rollback("wf")
        assert restored["version"] == 3  # 最新快照

        # 再次回滚
        restored = rollback_manager.rollback("wf")
        assert restored["version"] == 2

    def test_clear_snapshots(self, rollback_manager):
        """测试：清除快照"""
        rollback_manager.create_snapshot("wf_1", {"id": "wf_1"}, "test")
        rollback_manager.create_snapshot("wf_2", {"id": "wf_2"}, "test")

        rollback_manager.clear_snapshots("wf_1")

        assert not rollback_manager.has_snapshot("wf_1")
        assert rollback_manager.has_snapshot("wf_2")


# ==================== 3. 系统恢复测试 ====================


class TestSystemRecovery:
    """测试：系统恢复"""

    @pytest.fixture
    def recovery_manager(self):
        """创建恢复管理器"""
        from src.domain.services.dynamic_node_monitoring import SystemRecoveryManager

        return SystemRecoveryManager()

    @pytest.mark.asyncio
    async def test_recover_from_node_creation_failure(self, recovery_manager):
        """测试：从节点创建失败恢复"""
        # 设置初始状态
        initial_workflow = {
            "id": "workflow_1",
            "nodes": [{"id": "node_1", "name": "existing_node"}],
            "edges": [],
        }

        # 模拟节点创建失败
        recovery_manager.set_workflow_state("workflow_1", initial_workflow)

        # 尝试创建新节点（会失败）
        try:
            await recovery_manager.attempt_node_creation(
                workflow_id="workflow_1",
                node_definition={"name": "bad_node", "executor_type": "invalid"},
            )
        except Exception:
            pass  # 预期失败

        # 验证系统恢复到初始状态
        current_state = recovery_manager.get_workflow_state("workflow_1")
        assert len(current_state["nodes"]) == 1
        assert current_state["nodes"][0]["id"] == "node_1"

    @pytest.mark.asyncio
    async def test_recover_from_sandbox_failure(self, recovery_manager):
        """测试：从沙箱执行失败恢复"""
        workflow = {
            "id": "workflow_1",
            "nodes": [
                {"id": "node_1", "name": "safe_node", "status": "ready"},
            ],
            "edges": [],
        }
        recovery_manager.set_workflow_state("workflow_1", workflow)

        # 模拟沙箱执行失败
        result = await recovery_manager.execute_with_recovery(
            workflow_id="workflow_1",
            node_id="node_1",
            code="raise Exception('Sandbox error')",
        )

        assert result["success"] is False
        assert result["recovered"] is True

        # 验证节点状态被恢复
        current_state = recovery_manager.get_workflow_state("workflow_1")
        assert current_state["nodes"][0]["status"] == "ready"  # 恢复到 ready 状态

    @pytest.mark.asyncio
    async def test_recover_from_workflow_execution_failure(self, recovery_manager):
        """测试：从工作流执行失败恢复"""
        workflow = {
            "id": "workflow_1",
            "nodes": [
                {"id": "node_1", "name": "step_1", "status": "ready"},
                {"id": "node_2", "name": "step_2", "status": "ready"},
            ],
            "edges": [{"source": "node_1", "target": "node_2"}],
        }
        recovery_manager.set_workflow_state("workflow_1", workflow)

        # 模拟工作流执行中间失败
        result = await recovery_manager.execute_workflow_with_recovery(
            workflow_id="workflow_1",
            fail_at_node="node_2",  # 在第二个节点失败
        )

        assert result["success"] is False

        # 验证部分执行的节点状态被恢复
        current_state = recovery_manager.get_workflow_state("workflow_1")
        for node in current_state["nodes"]:
            assert node["status"] in ["ready", "rolled_back"]


# ==================== 4. 完整流程集成测试 ====================


class TestFullRecoveryFlow:
    """测试：完整恢复流程"""

    @pytest.mark.asyncio
    async def test_full_recovery_pipeline(self):
        """测试：完整恢复管道

        流程：识别需求 → 生成节点 → 沙箱验证 → 接入工作流 → 监控 → 回滚
        """
        from src.domain.services.dynamic_node_monitoring import (
            DynamicNodeMetricsCollector,
            SystemRecoveryManager,
            WorkflowRollbackManager,
        )

        metrics = DynamicNodeMetricsCollector()
        rollback = WorkflowRollbackManager()
        recovery = SystemRecoveryManager(
            metrics_collector=metrics,
            rollback_manager=rollback,
        )

        # 1. 设置初始工作流
        initial_workflow = {
            "id": "sales_pipeline",
            "nodes": [{"id": "node_1", "name": "data_fetch", "status": "ready"}],
            "edges": [],
        }
        recovery.set_workflow_state("sales_pipeline", initial_workflow)

        # 2. 创建快照
        rollback.create_snapshot("sales_pipeline", initial_workflow, "before adding nodes")

        # 3. 尝试添加新节点（使用无效的 executor_type 触发验证失败）
        new_node = {
            "id": "node_2",
            "name": "metric_calc",
            "executor_type": "invalid_executor",  # 无效类型，将触发验证失败
            "status": "pending",
        }

        # 4. 模拟验证失败
        validation_result = recovery.validate_node(new_node)
        if not validation_result["valid"]:
            # 5. 记录失败指标
            metrics.record_node_creation("metric_calc", success=False)

            # 6. 执行回滚
            restored = rollback.rollback("sales_pipeline")

            # 7. 验证恢复
            assert restored is not None
            assert len(restored["nodes"]) == 1

        # 8. 检查指标
        stats = metrics.get_statistics()
        assert stats["failed_creations"] >= 1

    @pytest.mark.asyncio
    async def test_successful_node_addition_with_monitoring(self):
        """测试：成功添加节点并监控"""
        from src.domain.services.dynamic_node_monitoring import (
            DynamicNodeMetricsCollector,
            SystemRecoveryManager,
            WorkflowRollbackManager,
        )

        metrics = DynamicNodeMetricsCollector()
        rollback = WorkflowRollbackManager()
        recovery = SystemRecoveryManager(
            metrics_collector=metrics,
            rollback_manager=rollback,
        )

        workflow = {
            "id": "test_workflow",
            "nodes": [],
            "edges": [],
        }
        recovery.set_workflow_state("test_workflow", workflow)

        # 添加有效节点
        valid_node = {
            "id": "node_1",
            "name": "valid_node",
            "executor_type": "code",
            "status": "ready",
        }

        result = await recovery.add_node_with_monitoring(
            workflow_id="test_workflow",
            node=valid_node,
        )

        assert result["success"] is True
        metrics.record_node_creation("valid_node", success=True)

        # 检查指标
        stats = metrics.get_statistics()
        assert stats["successful_creations"] >= 1


# ==================== 5. 健康检查测试 ====================


class TestHealthCheck:
    """测试：健康检查"""

    @pytest.fixture
    def health_checker(self):
        from src.domain.services.dynamic_node_monitoring import HealthChecker

        return HealthChecker()

    def test_check_system_health(self, health_checker):
        """测试：检查系统健康状态"""
        health = health_checker.check_health()

        assert "status" in health
        assert health["status"] in ["healthy", "degraded", "unhealthy"]
        assert "components" in health

    def test_check_sandbox_health(self, health_checker):
        """测试：检查沙箱健康状态"""
        health = health_checker.check_sandbox_health()

        assert "available" in health
        assert "last_execution_time" in health

    def test_check_metrics_health(self, health_checker):
        """测试：检查指标收集健康状态"""
        health = health_checker.check_metrics_health()

        assert "collecting" in health
        assert "storage_available" in health


# ==================== 6. 告警测试 ====================


class TestAlertManager:
    """测试：告警管理"""

    @pytest.fixture
    def alert_manager(self):
        from src.domain.services.dynamic_node_monitoring import AlertManager

        return AlertManager()

    def test_trigger_high_failure_rate_alert(self, alert_manager):
        """测试：触发高失败率告警"""
        alert_manager.set_threshold("sandbox_failure_rate", 0.2)  # 20% 阈值

        # 模拟高失败率
        alert_manager.check_failure_rate(0.35)  # 35% 失败率

        alerts = alert_manager.get_active_alerts()
        assert len(alerts) >= 1
        assert any("failure_rate" in a["type"] for a in alerts)

    def test_auto_clear_alert_when_resolved(self, alert_manager):
        """测试：问题解决后自动清除告警"""
        alert_manager.set_threshold("sandbox_failure_rate", 0.2)

        # 触发告警
        alert_manager.check_failure_rate(0.35)
        assert len(alert_manager.get_active_alerts()) >= 1

        # 失败率下降
        alert_manager.check_failure_rate(0.1)

        # 告警应该被清除
        failure_alerts = [
            a for a in alert_manager.get_active_alerts() if "failure_rate" in a["type"]
        ]
        assert len(failure_alerts) == 0

    def test_alert_notification_callback(self, alert_manager):
        """测试：告警通知回调"""
        notifications = []

        def callback(alert):
            notifications.append(alert)

        alert_manager.set_notification_callback(callback)
        alert_manager.set_threshold("sandbox_failure_rate", 0.2)
        alert_manager.check_failure_rate(0.35)

        assert len(notifications) >= 1


# ==================== 7. 边界情况测试 ====================


class TestEdgeCases:
    """测试：边界情况"""

    def test_rollback_nonexistent_workflow(self):
        """测试：回滚不存在的工作流"""
        from src.domain.services.dynamic_node_monitoring import WorkflowRollbackManager

        rollback = WorkflowRollbackManager()
        result = rollback.rollback("nonexistent_workflow")

        assert result is None

    def test_metrics_with_no_data(self):
        """测试：无数据时的指标"""
        from src.domain.services.dynamic_node_monitoring import DynamicNodeMetricsCollector

        metrics = DynamicNodeMetricsCollector()
        stats = metrics.get_statistics()

        assert stats["total_creations"] == 0
        assert stats["sandbox_failure_rate"] == 0.0

    def test_recovery_manager_without_dependencies(self):
        """测试：无依赖的恢复管理器"""
        from src.domain.services.dynamic_node_monitoring import SystemRecoveryManager

        recovery = SystemRecoveryManager()

        # 应该能正常工作
        recovery.set_workflow_state("test", {"id": "test", "nodes": []})
        state = recovery.get_workflow_state("test")
        assert state is not None
