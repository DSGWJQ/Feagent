"""Phase 34.14: WorkflowEfficiencyMonitor extracted from supervision_modules."""

from __future__ import annotations

from datetime import datetime
from typing import Any


class WorkflowEfficiencyMonitor:
    """工作流效率监控

    监控工作流的资源使用和延迟。
    """

    DEFAULT_THRESHOLDS = {
        "max_duration_seconds": 300.0,  # 5 分钟
        "max_node_duration_seconds": 60.0,  # 1 分钟
        "max_memory_mb": 2048,  # 2 GB
        "max_cpu_percent": 90.0,
    }

    def __init__(self, thresholds: dict[str, float] | None = None) -> None:
        """初始化效率监控器

        参数：
            thresholds: 自定义阈值
        """
        self.thresholds = {**self.DEFAULT_THRESHOLDS}
        if thresholds:
            self.thresholds.update(thresholds)

        self.workflow_usage: dict[str, dict[str, Any]] = {}
        self.latency_records: dict[str, dict[str, float]] = {}

    def record_resource_usage(
        self,
        workflow_id: str,
        node_id: str,
        memory_mb: float,
        cpu_percent: float,
        duration_seconds: float,
    ) -> None:
        """记录资源使用

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            memory_mb: 内存使用 (MB)
            cpu_percent: CPU 使用率 (%)
            duration_seconds: 执行时长 (秒)
        """
        if workflow_id not in self.workflow_usage:
            self.workflow_usage[workflow_id] = {
                "nodes": {},
                "total_duration": 0.0,
                "max_memory": 0.0,
                "max_cpu": 0.0,
            }

        usage = self.workflow_usage[workflow_id]

        usage["nodes"][node_id] = {
            "memory_mb": memory_mb,
            "cpu_percent": cpu_percent,
            "duration_seconds": duration_seconds,
            "recorded_at": datetime.now().isoformat(),
        }

        usage["total_duration"] += duration_seconds
        usage["max_memory"] = max(usage["max_memory"], memory_mb)
        usage["max_cpu"] = max(usage["max_cpu"], cpu_percent)

    def record_latency(
        self,
        workflow_id: str,
        node_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        """记录节点延迟

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID
            start_time: 开始时间
            end_time: 结束时间
        """
        if workflow_id not in self.latency_records:
            self.latency_records[workflow_id] = {}

        latency = (end_time - start_time).total_seconds()
        self.latency_records[workflow_id][node_id] = latency

    def get_workflow_usage(self, workflow_id: str) -> dict[str, Any] | None:
        """获取工作流资源使用情况

        参数：
            workflow_id: 工作流ID

        返回：
            资源使用情况
        """
        return self.workflow_usage.get(workflow_id)

    def get_node_latency(self, workflow_id: str, node_id: str) -> float | None:
        """获取节点延迟

        参数：
            workflow_id: 工作流ID
            node_id: 节点ID

        返回：
            延迟（秒）
        """
        if workflow_id not in self.latency_records:
            return None
        return self.latency_records[workflow_id].get(node_id)

    def get_workflow_total_duration(self, workflow_id: str) -> float:
        """获取工作流总时长

        参数：
            workflow_id: 工作流ID

        返回：
            总时长（秒）
        """
        usage = self.workflow_usage.get(workflow_id)
        if not usage:
            return 0.0
        return usage["total_duration"]

    def check_thresholds(self, workflow_id: str) -> list[dict[str, Any]]:
        """检查阈值并生成告警

        参数：
            workflow_id: 工作流ID

        返回：
            告警列表
        """
        alerts = []
        usage = self.workflow_usage.get(workflow_id)

        if not usage:
            return alerts

        # 检查总时长
        if usage["total_duration"] > self.thresholds["max_duration_seconds"]:
            alerts.append(
                {
                    "type": "slow_execution",
                    "severity": "warning",
                    "message": f"工作流总时长 ({usage['total_duration']:.1f}s) 超过阈值 ({self.thresholds['max_duration_seconds']}s)",
                    "value": usage["total_duration"],
                    "threshold": self.thresholds["max_duration_seconds"],
                }
            )

        # 检查内存
        if usage["max_memory"] > self.thresholds["max_memory_mb"]:
            alerts.append(
                {
                    "type": "memory_overuse",
                    "severity": "warning",
                    "message": f"内存使用 ({usage['max_memory']:.0f}MB) 超过阈值 ({self.thresholds['max_memory_mb']}MB)",
                    "value": usage["max_memory"],
                    "threshold": self.thresholds["max_memory_mb"],
                }
            )

        # 检查 CPU
        if usage["max_cpu"] > self.thresholds["max_cpu_percent"]:
            alerts.append(
                {
                    "type": "cpu_overuse",
                    "severity": "warning",
                    "message": f"CPU 使用率 ({usage['max_cpu']:.1f}%) 超过阈值 ({self.thresholds['max_cpu_percent']}%)",
                    "value": usage["max_cpu"],
                    "threshold": self.thresholds["max_cpu_percent"],
                }
            )

        # 检查单个节点时长
        for node_id, node_usage in usage["nodes"].items():
            if node_usage["duration_seconds"] > self.thresholds["max_node_duration_seconds"]:
                alerts.append(
                    {
                        "type": "slow_execution",
                        "severity": "warning",
                        "message": f"节点 {node_id} 执行时长 ({node_usage['duration_seconds']:.1f}s) 超过阈值",
                        "node_id": node_id,
                        "value": node_usage["duration_seconds"],
                        "threshold": self.thresholds["max_node_duration_seconds"],
                    }
                )

        return alerts


__all__ = ["WorkflowEfficiencyMonitor"]
