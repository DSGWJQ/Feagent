"""监督协调器

Phase 34.14: SupervisionCoordinator extracted from supervision_modules.
"""

from __future__ import annotations

from .conversation import ConversationSupervisionModule
from .efficiency import WorkflowEfficiencyMonitor
from .events import InterventionEvent, TaskTerminationEvent
from .models import TerminationResult
from .strategy_repo import StrategyRepository


class SupervisionCoordinator:
    """监督协调器

    协调对话监督和效率监控，管理终止流程。
    """

    def __init__(self) -> None:
        """初始化监督协调器"""
        self.conversation_supervision = ConversationSupervisionModule()
        self.efficiency_monitor = WorkflowEfficiencyMonitor()
        self.strategy_repository = StrategyRepository()

        self.intervention_events: list[InterventionEvent] = []
        self.termination_events: list[TaskTerminationEvent] = []

    def initiate_termination(
        self,
        task_id: str,
        reason: str,
        severity: str,
        graceful: bool = True,
        workflow_id: str = "",
    ) -> TerminationResult:
        """发起任务终止

        参数：
            task_id: 任务ID
            reason: 终止原因
            severity: 严重性
            graceful: 是否优雅终止
            workflow_id: 工作流ID

        返回：
            终止结果
        """
        termination_type = "graceful" if graceful else "immediate"

        # 创建终止事件
        event = TaskTerminationEvent(
            task_id=task_id,
            workflow_id=workflow_id,
            reason=reason,
            initiated_by="supervision_coordinator",
            termination_type=termination_type,
            severity=severity,
        )

        self.termination_events.append(event)

        return TerminationResult(
            success=True,
            task_id=task_id,
            termination_type=termination_type,
            message=f"任务 {task_id} 已{termination_type}终止: {reason}",
            severity=severity,
        )

    def get_termination_events(self) -> list[TaskTerminationEvent]:
        """获取终止事件列表

        返回：
            终止事件列表
        """
        return self.termination_events

    def record_intervention(
        self,
        intervention_type: str,
        reason: str,
        source: str,
        target_id: str,
        severity: str = "medium",
    ) -> InterventionEvent:
        """记录干预事件

        参数：
            intervention_type: 干预类型
            reason: 原因
            source: 来源
            target_id: 目标ID
            severity: 严重性

        返回：
            干预事件
        """
        event = InterventionEvent(
            intervention_type=intervention_type,
            reason=reason,
            source=source,
            target_id=target_id,
            severity=severity,
        )

        self.intervention_events.append(event)
        return event

    def get_intervention_events(self) -> list[InterventionEvent]:
        """获取干预事件列表

        返回：
            干预事件列表
        """
        return self.intervention_events


__all__ = ["SupervisionCoordinator"]
