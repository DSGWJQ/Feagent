"""WorkflowEfficiencyMonitor 单元测试

Phase: P0-7 Coverage Improvement (25% → 80%+)
Coverage targets:
- record_resource_usage: aggregation logic (total_duration, max_memory, max_cpu)
- record_latency: datetime calculation
- get_workflow_usage / get_node_latency / get_workflow_total_duration: retrieval + missing cases
- check_thresholds: all 4 alert types (duration/node_duration/memory/cpu)
- init: custom threshold merging
"""

from datetime import datetime, timedelta

import pytest

from src.domain.services.supervision.efficiency import WorkflowEfficiencyMonitor


@pytest.fixture
def monitor():
    """创建默认监控器"""
    return WorkflowEfficiencyMonitor()


# ==================== TestInitThresholds ====================


class TestInitThresholds:
    """测试初始化与阈值配置"""

    def test_init_merges_custom_thresholds_over_defaults(self):
        """测试自定义阈值覆盖默认值（仅覆盖提供的键）"""
        custom_thresholds = {
            "max_duration_seconds": 600.0,  # 覆盖
            "max_memory_mb": 4096,  # 覆盖
        }
        monitor = WorkflowEfficiencyMonitor(thresholds=custom_thresholds)

        # 验证所有4个阈值都存在
        assert "max_duration_seconds" in monitor.thresholds
        assert "max_node_duration_seconds" in monitor.thresholds
        assert "max_memory_mb" in monitor.thresholds
        assert "max_cpu_percent" in monitor.thresholds

        # 验证覆盖的键已更新
        assert monitor.thresholds["max_duration_seconds"] == 600.0
        assert monitor.thresholds["max_memory_mb"] == 4096

        # 验证未覆盖的键保持默认值
        assert monitor.thresholds["max_node_duration_seconds"] == 60.0
        assert monitor.thresholds["max_cpu_percent"] == 90.0

    def test_init_without_custom_thresholds_uses_defaults(self):
        """测试不提供自定义阈值时使用默认值"""
        monitor = WorkflowEfficiencyMonitor()

        assert monitor.thresholds == WorkflowEfficiencyMonitor.DEFAULT_THRESHOLDS


# ==================== TestRecordResourceUsage ====================


class TestRecordResourceUsage:
    """测试资源使用记录"""

    def test_record_resource_usage_creates_workflow_and_node_entry(self, monitor):
        """测试首次记录创建工作流和节点条目"""
        monitor.record_resource_usage(
            workflow_id="wf1",
            node_id="node1",
            memory_mb=512.0,
            cpu_percent=45.5,
            duration_seconds=10.5,
        )

        # 验证工作流条目已创建
        assert "wf1" in monitor.workflow_usage
        usage = monitor.workflow_usage["wf1"]

        # 验证节点条目包含所有字段
        assert "node1" in usage["nodes"]
        node = usage["nodes"]["node1"]
        assert node["memory_mb"] == 512.0
        assert node["cpu_percent"] == 45.5
        assert node["duration_seconds"] == 10.5
        assert "recorded_at" in node

        # 验证 recorded_at 可解析
        datetime.fromisoformat(node["recorded_at"])

    def test_record_resource_usage_aggregates_total_duration_and_maxes(self, monitor):
        """测试记录多个节点时聚合总时长和最大值"""
        monitor.record_resource_usage("wf1", "node1", 512.0, 45.0, 10.0)
        monitor.record_resource_usage("wf1", "node2", 1024.0, 30.0, 15.0)

        usage = monitor.workflow_usage["wf1"]

        # 验证总时长累加
        assert usage["total_duration"] == 25.0  # 10.0 + 15.0

        # 验证最大值正确
        assert usage["max_memory"] == 1024.0  # max(512, 1024)
        assert usage["max_cpu"] == 45.0  # max(45, 30)

    def test_record_resource_usage_same_node_overwrites_node_but_duration_accumulates(
        self, monitor
    ):
        """测试同一节点多次记录时覆盖节点数据但累积总时长"""
        monitor.record_resource_usage("wf1", "node1", 512.0, 45.0, 10.0)
        monitor.record_resource_usage("wf1", "node1", 256.0, 60.0, 5.0)

        usage = monitor.workflow_usage["wf1"]
        node = usage["nodes"]["node1"]

        # 节点数据应反映最后一次记录
        assert node["memory_mb"] == 256.0
        assert node["cpu_percent"] == 60.0
        assert node["duration_seconds"] == 5.0

        # 总时长应累加两次记录
        assert usage["total_duration"] == 15.0  # 10.0 + 5.0


# ==================== TestLatency ====================


class TestLatency:
    """测试延迟记录"""

    def test_record_latency_stores_seconds_and_get_node_latency_returns_value(
        self, monitor
    ):
        """测试记录延迟并通过 get_node_latency 获取"""
        start = datetime(2025, 1, 1, 12, 0, 0)
        end = datetime(2025, 1, 1, 12, 0, 45)  # 45秒后

        monitor.record_latency("wf1", "node1", start, end)

        latency = monitor.get_node_latency("wf1", "node1")
        assert latency == pytest.approx(45.0)

    def test_record_latency_multiple_nodes_same_workflow(self, monitor):
        """测试同一工作流记录多个节点延迟"""
        base = datetime(2025, 1, 1, 12, 0, 0)

        monitor.record_latency("wf1", "node1", base, base + timedelta(seconds=10))
        monitor.record_latency("wf1", "node2", base, base + timedelta(seconds=20))

        assert monitor.get_node_latency("wf1", "node1") == pytest.approx(10.0)
        assert monitor.get_node_latency("wf1", "node2") == pytest.approx(20.0)

    def test_record_latency_end_before_start_allows_negative(self, monitor):
        """测试结束时间早于开始时间时允许负延迟（记录当前行为）"""
        start = datetime(2025, 1, 1, 12, 0, 0)
        end = datetime(2025, 1, 1, 11, 59, 50)  # 10秒前

        monitor.record_latency("wf1", "node1", start, end)

        latency = monitor.get_node_latency("wf1", "node1")
        assert latency == pytest.approx(-10.0)


# ==================== TestGetters ====================


class TestGetters:
    """测试获取方法"""

    def test_get_node_latency_missing_workflow_returns_none(self, monitor):
        """测试获取不存在的工作流延迟返回 None"""
        latency = monitor.get_node_latency("missing_wf", "node1")
        assert latency is None

    def test_get_node_latency_missing_node_returns_none(self, monitor):
        """测试获取不存在的节点延迟返回 None"""
        start = datetime(2025, 1, 1, 12, 0, 0)
        end = datetime(2025, 1, 1, 12, 0, 10)
        monitor.record_latency("wf1", "node1", start, end)

        latency = monitor.get_node_latency("wf1", "missing_node")
        assert latency is None

    def test_get_workflow_usage_missing_returns_none(self, monitor):
        """测试获取不存在的工作流使用情况返回 None"""
        usage = monitor.get_workflow_usage("missing_wf")
        assert usage is None

    def test_get_workflow_usage_returns_usage_dict(self, monitor):
        """测试获取存在的工作流使用情况"""
        monitor.record_resource_usage("wf1", "node1", 512.0, 45.0, 10.0)

        usage = monitor.get_workflow_usage("wf1")
        assert usage is not None
        assert "nodes" in usage
        assert "total_duration" in usage
        assert "max_memory" in usage
        assert "max_cpu" in usage

    def test_get_workflow_total_duration_missing_returns_zero(self, monitor):
        """测试获取不存在的工作流总时长返回 0.0"""
        duration = monitor.get_workflow_total_duration("missing_wf")
        assert duration == 0.0

    def test_get_workflow_total_duration_returns_total(self, monitor):
        """测试获取存在的工作流总时长"""
        monitor.record_resource_usage("wf1", "node1", 512.0, 45.0, 10.0)
        monitor.record_resource_usage("wf1", "node2", 256.0, 30.0, 5.0)

        duration = monitor.get_workflow_total_duration("wf1")
        assert duration == 15.0


# ==================== TestCheckThresholds ====================


class TestCheckThresholds:
    """测试阈值检查"""

    def test_check_thresholds_no_usage_returns_empty(self, monitor):
        """测试没有使用记录时返回空告警列表"""
        alerts = monitor.check_thresholds("wf1")
        assert alerts == []

    def test_check_thresholds_total_duration_violation_alert(self):
        """测试总时长超过阈值时生成告警"""
        monitor = WorkflowEfficiencyMonitor(thresholds={"max_duration_seconds": 20.0})
        monitor.record_resource_usage("wf1", "node1", 512.0, 45.0, 15.0)
        monitor.record_resource_usage("wf1", "node2", 256.0, 30.0, 10.0)

        alerts = monitor.check_thresholds("wf1")

        # 查找总时长告警（不包含 node_id）
        duration_alerts = [a for a in alerts if a["type"] == "slow_execution" and "node_id" not in a]
        assert len(duration_alerts) == 1

        alert = duration_alerts[0]
        assert alert["severity"] == "warning"
        assert alert["value"] == 25.0
        assert alert["threshold"] == 20.0
        assert "25.0" in alert["message"]
        assert "20.0" in alert["message"]

    def test_check_thresholds_node_duration_violation_alert_includes_node_id(self):
        """测试单个节点时长超过阈值时生成告警（包含 node_id）"""
        monitor = WorkflowEfficiencyMonitor(
            thresholds={"max_node_duration_seconds": 50.0}
        )
        monitor.record_resource_usage("wf1", "node1", 512.0, 45.0, 60.0)

        alerts = monitor.check_thresholds("wf1")

        # 查找节点时长告警（包含 node_id）
        node_alerts = [a for a in alerts if "node_id" in a]
        assert len(node_alerts) == 1

        alert = node_alerts[0]
        assert alert["type"] == "slow_execution"
        assert alert["node_id"] == "node1"
        assert alert["value"] == 60.0
        assert alert["threshold"] == 50.0

    def test_check_thresholds_memory_violation_alert(self):
        """测试内存使用超过阈值时生成告警"""
        monitor = WorkflowEfficiencyMonitor(thresholds={"max_memory_mb": 1000})
        monitor.record_resource_usage("wf1", "node1", 2048.0, 45.0, 10.0)

        alerts = monitor.check_thresholds("wf1")

        memory_alerts = [a for a in alerts if a["type"] == "memory_overuse"]
        assert len(memory_alerts) == 1

        alert = memory_alerts[0]
        assert alert["severity"] == "warning"
        assert alert["value"] == 2048.0
        assert alert["threshold"] == 1000

    def test_check_thresholds_cpu_violation_alert(self):
        """测试 CPU 使用率超过阈值时生成告警"""
        monitor = WorkflowEfficiencyMonitor(thresholds={"max_cpu_percent": 80.0})
        monitor.record_resource_usage("wf1", "node1", 512.0, 95.0, 10.0)

        alerts = monitor.check_thresholds("wf1")

        cpu_alerts = [a for a in alerts if a["type"] == "cpu_overuse"]
        assert len(cpu_alerts) == 1

        alert = cpu_alerts[0]
        assert alert["severity"] == "warning"
        assert alert["value"] == 95.0
        assert alert["threshold"] == 80.0

    def test_check_thresholds_multiple_violations_return_all(self):
        """测试多个违规时返回所有告警"""
        monitor = WorkflowEfficiencyMonitor(
            thresholds={
                "max_duration_seconds": 20.0,
                "max_node_duration_seconds": 50.0,
                "max_memory_mb": 1000,
                "max_cpu_percent": 80.0,
            }
        )

        # 构造违反所有阈值的使用情况
        monitor.record_resource_usage("wf1", "node1", 2048.0, 95.0, 60.0)
        monitor.record_resource_usage("wf1", "node2", 512.0, 50.0, 5.0)

        alerts = monitor.check_thresholds("wf1")

        # 验证所有4类告警都存在
        alert_types = {a["type"] for a in alerts}
        assert "slow_execution" in alert_types
        assert "memory_overuse" in alert_types
        assert "cpu_overuse" in alert_types

        # 验证有总时长告警（无 node_id）
        total_duration_alerts = [
            a for a in alerts if a["type"] == "slow_execution" and "node_id" not in a
        ]
        assert len(total_duration_alerts) == 1

        # 验证有节点时长告警（有 node_id）
        node_duration_alerts = [
            a for a in alerts if a["type"] == "slow_execution" and "node_id" in a
        ]
        assert len(node_duration_alerts) == 1

    def test_check_thresholds_boundary_equal_no_alert(self):
        """测试值恰好等于阈值时不生成告警（使用 > 比较）"""
        monitor = WorkflowEfficiencyMonitor(
            thresholds={
                "max_duration_seconds": 20.0,
                "max_memory_mb": 1000,
                "max_cpu_percent": 80.0,
            }
        )
        monitor.record_resource_usage("wf1", "node1", 1000.0, 80.0, 20.0)

        alerts = monitor.check_thresholds("wf1")
        assert alerts == []


# ==================== TestEdgeCases ====================


class TestEdgeCases:
    """测试边缘情况"""

    def test_check_thresholds_handles_float_inputs(self):
        """测试浮点数输入的处理（内存/CPU 带小数）"""
        monitor = WorkflowEfficiencyMonitor(
            thresholds={"max_memory_mb": 1000.5, "max_cpu_percent": 80.25}
        )
        monitor.record_resource_usage("wf1", "node1", 1500.75, 90.99, 10.0)

        alerts = monitor.check_thresholds("wf1")

        memory_alerts = [a for a in alerts if a["type"] == "memory_overuse"]
        cpu_alerts = [a for a in alerts if a["type"] == "cpu_overuse"]

        assert len(memory_alerts) == 1
        assert len(cpu_alerts) == 1

        # 验证值保留小数
        assert memory_alerts[0]["value"] == 1500.75
        assert cpu_alerts[0]["value"] == 90.99

    def test_record_resource_usage_zero_values_allowed(self, monitor):
        """测试允许记录零值（记录当前行为）"""
        monitor.record_resource_usage("wf1", "node1", 0.0, 0.0, 0.0)

        usage = monitor.workflow_usage["wf1"]
        assert usage["total_duration"] == 0.0
        assert usage["max_memory"] == 0.0
        assert usage["max_cpu"] == 0.0
