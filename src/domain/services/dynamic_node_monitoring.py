"""
动态节点监控、回滚与系统恢复模块 (Step 9)

提供：
1. DynamicNodeMetricsCollector - 监控指标收集
2. WorkflowRollbackManager - 失败回滚机制
3. SystemRecoveryManager - 系统恢复
4. HealthChecker - 健康检查
5. AlertManager - 告警管理
"""

import copy
import time
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

# ==================== 数据结构 ====================


@dataclass
class MetricRecord:
    """单条指标记录"""

    timestamp: float
    metric_type: str
    name: str
    success: bool
    duration_ms: float | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class WorkflowSnapshot:
    """工作流快照"""

    id: str
    workflow_id: str
    state: dict
    reason: str
    created_at: float


@dataclass
class Alert:
    """告警信息"""

    id: str
    type: str
    message: str
    severity: str  # "warning", "critical"
    created_at: float
    resolved: bool = False


# ==================== 1. 监控指标收集器 ====================


class DynamicNodeMetricsCollector:
    """动态节点监控指标收集器

    跟踪：
    - 节点创建次数（成功/失败）
    - 沙箱执行统计（成功率、耗时）
    - 工作流执行统计
    - Prometheus 格式导出
    """

    def __init__(self):
        self._records: list[MetricRecord] = []

    def record_node_creation(self, node_name: str, success: bool) -> None:
        """记录节点创建"""
        self._records.append(
            MetricRecord(
                timestamp=time.time(),
                metric_type="node_creation",
                name=node_name,
                success=success,
            )
        )

    def record_sandbox_execution(self, node_name: str, success: bool, duration_ms: float) -> None:
        """记录沙箱执行"""
        self._records.append(
            MetricRecord(
                timestamp=time.time(),
                metric_type="sandbox_execution",
                name=node_name,
                success=success,
                duration_ms=duration_ms,
            )
        )

    def record_workflow_execution(
        self,
        workflow_name: str,
        success: bool,
        duration_ms: float,
        node_count: int,
    ) -> None:
        """记录工作流执行"""
        self._records.append(
            MetricRecord(
                timestamp=time.time(),
                metric_type="workflow_execution",
                name=workflow_name,
                success=success,
                duration_ms=duration_ms,
                extra={"node_count": node_count},
            )
        )

    def get_statistics(self, time_window_minutes: int | None = None) -> dict:
        """获取统计信息

        Args:
            time_window_minutes: 时间窗口（分钟），None 表示全部

        Returns:
            统计字典
        """
        records = self._filter_by_time_window(time_window_minutes)

        # 节点创建统计
        node_creations = [r for r in records if r.metric_type == "node_creation"]
        successful_creations = sum(1 for r in node_creations if r.success)
        failed_creations = sum(1 for r in node_creations if not r.success)

        # 沙箱执行统计
        sandbox_execs = [r for r in records if r.metric_type == "sandbox_execution"]
        sandbox_successes = sum(1 for r in sandbox_execs if r.success)
        sandbox_failures = sum(1 for r in sandbox_execs if not r.success)
        sandbox_failure_rate = sandbox_failures / len(sandbox_execs) if sandbox_execs else 0.0

        # 工作流执行统计
        workflow_execs = [r for r in records if r.metric_type == "workflow_execution"]
        workflow_successes = sum(1 for r in workflow_execs if r.success)
        workflow_failures = sum(1 for r in workflow_execs if not r.success)

        return {
            "total_creations": len(node_creations),
            "successful_creations": successful_creations,
            "failed_creations": failed_creations,
            "sandbox_executions": len(sandbox_execs),
            "sandbox_successes": sandbox_successes,
            "sandbox_failures": sandbox_failures,
            "sandbox_failure_rate": sandbox_failure_rate,
            "workflow_executions": len(workflow_execs),
            "workflow_successes": workflow_successes,
            "workflow_failures": workflow_failures,
        }

    def get_sandbox_failure_rate(self, time_window_minutes: int | None = None) -> float:
        """获取沙箱失败率"""
        stats = self.get_statistics(time_window_minutes)
        return stats["sandbox_failure_rate"]

    def export_prometheus(self) -> str:
        """导出 Prometheus 格式指标"""
        stats = self.get_statistics()

        lines = [
            "# HELP dynamic_node_creations_total Total number of dynamic node creations",
            "# TYPE dynamic_node_creations_total counter",
            f"dynamic_node_creations_total{{status=\"success\"}} {stats['successful_creations']}",
            f"dynamic_node_creations_total{{status=\"failure\"}} {stats['failed_creations']}",
            "",
            "# HELP sandbox_executions_total Total number of sandbox executions",
            "# TYPE sandbox_executions_total counter",
            f"sandbox_executions_total{{status=\"success\"}} {stats['sandbox_successes']}",
            f"sandbox_executions_total{{status=\"failure\"}} {stats['sandbox_failures']}",
            "",
            "# HELP sandbox_failure_rate Current sandbox failure rate",
            "# TYPE sandbox_failure_rate gauge",
            f"sandbox_failure_rate {stats['sandbox_failure_rate']:.4f}",
            "",
            "# HELP workflow_executions_total Total number of workflow executions",
            "# TYPE workflow_executions_total counter",
            f"workflow_executions_total{{status=\"success\"}} {stats['workflow_successes']}",
            f"workflow_executions_total{{status=\"failure\"}} {stats['workflow_failures']}",
        ]

        return "\n".join(lines)

    def _filter_by_time_window(self, time_window_minutes: int | None) -> list[MetricRecord]:
        """按时间窗口过滤记录"""
        if time_window_minutes is None:
            return self._records

        cutoff = time.time() - (time_window_minutes * 60)
        return [r for r in self._records if r.timestamp >= cutoff]


# ==================== 2. 回滚管理器 ====================


class WorkflowRollbackManager:
    """工作流回滚管理器

    功能：
    - 变更前创建快照
    - 回滚到历史快照
    - 删除无效节点
    - 管理多个快照版本
    """

    def __init__(self):
        # workflow_id -> list of snapshots (按时间顺序)
        self._snapshots: dict[str, list[WorkflowSnapshot]] = defaultdict(list)

    def create_snapshot(
        self,
        workflow_id: str,
        state: dict,
        reason: str,
    ) -> str:
        """创建工作流快照

        Args:
            workflow_id: 工作流 ID
            state: 当前状态
            reason: 创建原因

        Returns:
            快照 ID
        """
        snapshot_id = f"snap_{uuid.uuid4().hex[:8]}"
        snapshot = WorkflowSnapshot(
            id=snapshot_id,
            workflow_id=workflow_id,
            state=copy.deepcopy(state),
            reason=reason,
            created_at=time.time(),
        )
        self._snapshots[workflow_id].append(snapshot)
        return snapshot_id

    def has_snapshot(self, workflow_id: str) -> bool:
        """检查是否有快照"""
        return len(self._snapshots.get(workflow_id, [])) > 0

    def rollback(self, workflow_id: str) -> dict | None:
        """回滚到上一个快照

        Args:
            workflow_id: 工作流 ID

        Returns:
            恢复的状态，如果没有快照则返回 None
        """
        snapshots = self._snapshots.get(workflow_id, [])
        if not snapshots:
            return None

        # 弹出最新的快照并返回
        snapshot = snapshots.pop()
        return copy.deepcopy(snapshot.state)

    def rollback_to_snapshot(self, workflow_id: str, snapshot_id: str) -> dict | None:
        """回滚到指定快照

        Args:
            workflow_id: 工作流 ID
            snapshot_id: 快照 ID

        Returns:
            恢复的状态
        """
        snapshots = self._snapshots.get(workflow_id, [])
        for snapshot in snapshots:
            if snapshot.id == snapshot_id:
                return copy.deepcopy(snapshot.state)
        return None

    def remove_invalid_nodes(self, workflow_state: dict) -> dict:
        """删除无效节点及其相关边

        Args:
            workflow_state: 工作流状态

        Returns:
            清理后的状态
        """
        cleaned = copy.deepcopy(workflow_state)

        # 找出无效节点
        invalid_node_ids = set()
        valid_nodes = []

        for node in cleaned.get("nodes", []):
            if node.get("valid", True) is False:
                invalid_node_ids.add(node["id"])
            else:
                valid_nodes.append(node)

        cleaned["nodes"] = valid_nodes

        # 删除涉及无效节点的边
        valid_edges = []
        for edge in cleaned.get("edges", []):
            if edge["source"] not in invalid_node_ids and edge["target"] not in invalid_node_ids:
                valid_edges.append(edge)

        cleaned["edges"] = valid_edges

        return cleaned

    def clear_snapshots(self, workflow_id: str) -> None:
        """清除指定工作流的所有快照"""
        if workflow_id in self._snapshots:
            del self._snapshots[workflow_id]

    def get_snapshot_count(self, workflow_id: str) -> int:
        """获取快照数量"""
        return len(self._snapshots.get(workflow_id, []))


# ==================== 3. 系统恢复管理器 ====================


class SystemRecoveryManager:
    """系统恢复管理器

    提供：
    - 节点创建失败恢复
    - 沙箱执行失败恢复
    - 工作流执行失败恢复
    - 整合监控与回滚
    """

    def __init__(
        self,
        metrics_collector: DynamicNodeMetricsCollector | None = None,
        rollback_manager: WorkflowRollbackManager | None = None,
    ):
        self._metrics = metrics_collector or DynamicNodeMetricsCollector()
        self._rollback = rollback_manager or WorkflowRollbackManager()
        self._workflow_states: dict[str, dict] = {}

    def set_workflow_state(self, workflow_id: str, state: dict) -> None:
        """设置工作流状态"""
        self._workflow_states[workflow_id] = copy.deepcopy(state)

    def get_workflow_state(self, workflow_id: str) -> dict | None:
        """获取工作流状态"""
        state = self._workflow_states.get(workflow_id)
        return copy.deepcopy(state) if state else None

    async def attempt_node_creation(
        self,
        workflow_id: str,
        node_definition: dict,
    ) -> dict:
        """尝试创建节点，失败时自动恢复

        Args:
            workflow_id: 工作流 ID
            node_definition: 节点定义

        Returns:
            创建结果
        """
        # 创建快照
        current_state = self._workflow_states.get(workflow_id)
        if current_state:
            self._rollback.create_snapshot(workflow_id, current_state, "before node creation")

        try:
            # 验证节点
            validation = self.validate_node(node_definition)
            if not validation["valid"]:
                raise ValueError(validation["error"])

            # 模拟节点创建
            if current_state:
                new_node = {
                    "id": f"node_{uuid.uuid4().hex[:8]}",
                    **node_definition,
                }
                current_state["nodes"].append(new_node)
                self._workflow_states[workflow_id] = current_state

            self._metrics.record_node_creation(
                node_definition.get("name", "unknown"),
                success=True,
            )
            return {"success": True}

        except Exception:
            # 记录失败
            self._metrics.record_node_creation(
                node_definition.get("name", "unknown"),
                success=False,
            )

            # 恢复到快照
            if self._rollback.has_snapshot(workflow_id):
                restored = self._rollback.rollback(workflow_id)
                if restored:
                    self._workflow_states[workflow_id] = restored

            raise

    async def execute_with_recovery(
        self,
        workflow_id: str,
        node_id: str,
        code: str,
    ) -> dict:
        """执行代码，失败时恢复状态

        Args:
            workflow_id: 工作流 ID
            node_id: 节点 ID
            code: 要执行的代码

        Returns:
            执行结果
        """
        # 保存原始状态
        original_state = copy.deepcopy(self._workflow_states.get(workflow_id, {}))

        # 找到节点并更新状态
        current_state = self._workflow_states.get(workflow_id, {})
        target_node = None
        for node in current_state.get("nodes", []):
            if node["id"] == node_id:
                target_node = node
                break

        start_time = time.time()

        try:
            # 尝试执行代码（这里模拟执行）
            if "raise Exception" in code or "error" in code.lower():
                raise RuntimeError("Sandbox execution failed")

            # 成功
            if target_node:
                target_node["status"] = "completed"

            duration_ms = (time.time() - start_time) * 1000
            self._metrics.record_sandbox_execution(node_id, success=True, duration_ms=duration_ms)

            return {"success": True, "recovered": False}

        except Exception as e:
            # 恢复原始状态
            self._workflow_states[workflow_id] = original_state

            duration_ms = (time.time() - start_time) * 1000
            self._metrics.record_sandbox_execution(node_id, success=False, duration_ms=duration_ms)

            return {"success": False, "recovered": True, "error": str(e)}

    async def execute_workflow_with_recovery(
        self,
        workflow_id: str,
        fail_at_node: str | None = None,
    ) -> dict:
        """执行工作流，失败时恢复

        Args:
            workflow_id: 工作流 ID
            fail_at_node: 模拟在此节点失败

        Returns:
            执行结果
        """
        original_state = copy.deepcopy(self._workflow_states.get(workflow_id, {}))
        current_state = self._workflow_states.get(workflow_id, {})

        start_time = time.time()
        executed_nodes = []

        try:
            for node in current_state.get("nodes", []):
                if fail_at_node and node["id"] == fail_at_node:
                    raise RuntimeError(f"Execution failed at node {fail_at_node}")

                node["status"] = "completed"
                executed_nodes.append(node["id"])

            duration_ms = (time.time() - start_time) * 1000
            node_count = len(current_state.get("nodes", []))
            self._metrics.record_workflow_execution(
                workflow_id,
                success=True,
                duration_ms=duration_ms,
                node_count=node_count,
            )

            return {"success": True}

        except Exception as e:
            # 恢复所有节点状态
            for node in original_state.get("nodes", []):
                if node["id"] in executed_nodes:
                    node["status"] = "rolled_back"

            self._workflow_states[workflow_id] = original_state

            duration_ms = (time.time() - start_time) * 1000
            node_count = len(current_state.get("nodes", []))
            self._metrics.record_workflow_execution(
                workflow_id,
                success=False,
                duration_ms=duration_ms,
                node_count=node_count,
            )

            return {"success": False, "error": str(e)}

    def validate_node(self, node_definition: dict) -> dict:
        """验证节点定义

        Args:
            node_definition: 节点定义

        Returns:
            验证结果
        """
        errors = []

        # 检查必需字段
        if "name" not in node_definition:
            errors.append("Missing required field: name")

        # 检查执行器类型
        executor_type = node_definition.get("executor_type", "")
        valid_types = ["code", "llm", "http", "prompt", "javascript"]
        if executor_type and executor_type not in valid_types:
            errors.append(f"Invalid executor_type: {executor_type}")

        if errors:
            return {"valid": False, "error": "; ".join(errors)}

        return {"valid": True}

    async def add_node_with_monitoring(
        self,
        workflow_id: str,
        node: dict,
    ) -> dict:
        """添加节点并监控

        Args:
            workflow_id: 工作流 ID
            node: 节点定义

        Returns:
            添加结果
        """
        current_state = self._workflow_states.get(workflow_id, {})

        # 验证节点
        validation = self.validate_node(node)
        if not validation["valid"]:
            return {"success": False, "error": validation["error"]}

        # 添加节点
        if "nodes" not in current_state:
            current_state["nodes"] = []
        current_state["nodes"].append(node)

        self._workflow_states[workflow_id] = current_state

        return {"success": True}


# ==================== 4. 健康检查器 ====================


class HealthChecker:
    """系统健康检查器

    检查：
    - 整体系统健康
    - 沙箱可用性
    - 指标收集状态
    """

    def __init__(self):
        self._last_sandbox_execution: float | None = None
        self._sandbox_available: bool = True
        self._metrics_collecting: bool = True
        self._storage_available: bool = True

    def check_health(self) -> dict:
        """检查整体系统健康状态"""
        components = {
            "sandbox": self.check_sandbox_health(),
            "metrics": self.check_metrics_health(),
        }

        # 计算整体状态
        all_healthy = all(
            c.get("available", True) and c.get("collecting", True) for c in components.values()
        )

        if all_healthy:
            status = "healthy"
        elif any(not c.get("available", True) for c in components.values()):
            status = "unhealthy"
        else:
            status = "degraded"

        return {
            "status": status,
            "components": components,
            "timestamp": time.time(),
        }

    def check_sandbox_health(self) -> dict:
        """检查沙箱健康状态"""
        return {
            "available": self._sandbox_available,
            "last_execution_time": self._last_sandbox_execution,
        }

    def check_metrics_health(self) -> dict:
        """检查指标收集健康状态"""
        return {
            "collecting": self._metrics_collecting,
            "storage_available": self._storage_available,
        }

    def record_sandbox_execution(self) -> None:
        """记录沙箱执行时间"""
        self._last_sandbox_execution = time.time()

    def set_sandbox_available(self, available: bool) -> None:
        """设置沙箱可用性"""
        self._sandbox_available = available


# ==================== 5. 告警管理器 ====================


class AlertManager:
    """告警管理器

    功能：
    - 设置阈值
    - 检测异常
    - 触发/清除告警
    - 通知回调
    """

    def __init__(self):
        self._thresholds: dict[str, float] = {}
        self._active_alerts: list[Alert] = []
        self._notification_callback: Callable[[Alert], None] | None = None

    def set_threshold(self, metric_name: str, threshold: float) -> None:
        """设置告警阈值"""
        self._thresholds[metric_name] = threshold

    def set_notification_callback(self, callback: Callable[[Alert], None]) -> None:
        """设置通知回调"""
        self._notification_callback = callback

    def check_failure_rate(self, current_rate: float) -> None:
        """检查失败率并触发/清除告警"""
        threshold = self._thresholds.get("sandbox_failure_rate", 0.5)

        if current_rate > threshold:
            # 检查是否已有此类告警
            existing = [
                a
                for a in self._active_alerts
                if a.type == "sandbox_failure_rate" and not a.resolved
            ]

            if not existing:
                alert = Alert(
                    id=f"alert_{uuid.uuid4().hex[:8]}",
                    type="sandbox_failure_rate",
                    message=f"Sandbox failure rate {current_rate:.1%} exceeds threshold {threshold:.1%}",
                    severity="critical" if current_rate > threshold * 1.5 else "warning",
                    created_at=time.time(),
                )
                self._active_alerts.append(alert)

                if self._notification_callback:
                    self._notification_callback(alert)
        else:
            # 清除已解决的告警
            for alert in self._active_alerts:
                if alert.type == "sandbox_failure_rate" and not alert.resolved:
                    alert.resolved = True

    def get_active_alerts(self) -> list[dict]:
        """获取活跃告警列表"""
        return [
            {
                "id": a.id,
                "type": a.type,
                "message": a.message,
                "severity": a.severity,
                "created_at": a.created_at,
            }
            for a in self._active_alerts
            if not a.resolved
        ]

    def clear_alert(self, alert_id: str) -> bool:
        """清除指定告警"""
        for alert in self._active_alerts:
            if alert.id == alert_id:
                alert.resolved = True
                return True
        return False

    def clear_all_alerts(self) -> int:
        """清除所有告警"""
        count = 0
        for alert in self._active_alerts:
            if not alert.resolved:
                alert.resolved = True
                count += 1
        return count
