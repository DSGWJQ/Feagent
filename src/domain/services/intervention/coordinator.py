"""干预协调器

Phase 34.15: 从 intervention_system.py 提取 InterventionCoordinator
"""

from __future__ import annotations

import logging
from typing import Any

from .logger import InterventionLogger
from .models import InterventionLevel, InterventionResult
from .task_terminator import TaskTerminator
from .workflow_modifier import WorkflowModifier

logger = logging.getLogger(__name__)


class InterventionCoordinator:
    """干预协调器

    协调干预操作，支持级别升级。
    """

    def __init__(
        self,
        workflow_modifier: WorkflowModifier | None = None,
        task_terminator: TaskTerminator | None = None,
        logger: InterventionLogger | None = None,
    ):
        """初始化

        参数：
            workflow_modifier: 工作流修改器
            task_terminator: 任务终止器
            logger: 干预日志记录器
        """
        self._logger = logger or InterventionLogger()
        self._workflow_modifier = workflow_modifier or WorkflowModifier(self._logger)
        self._task_terminator = task_terminator or TaskTerminator(self._logger)

    @property
    def intervention_logger(self) -> InterventionLogger:
        """获取日志记录器"""
        return self._logger

    def handle_intervention(
        self,
        level: InterventionLevel,
        context: dict[str, Any],
    ) -> InterventionResult:
        """处理干预

        参数：
            level: 干预级别
            context: 上下文数据

        返回：
            干预结果
        """
        session_id = context.get("session_id", "unknown")

        if level == InterventionLevel.NONE:
            return InterventionResult(success=True, action_taken="none")

        elif level == InterventionLevel.NOTIFY:
            self._logger.log_intervention(level, session_id, "logged", context)
            return InterventionResult(success=True, action_taken="logged")

        elif level == InterventionLevel.WARN:
            self._logger.log_intervention(level, session_id, "warning_injected", context)
            return InterventionResult(success=True, action_taken="warning_injected")

        elif level == InterventionLevel.REPLACE:
            self._logger.log_intervention(level, session_id, "node_replaced", context)
            return InterventionResult(success=True, action_taken="node_replaced")

        elif level == InterventionLevel.TERMINATE:
            self._logger.log_intervention(level, session_id, "task_terminated", context)
            return InterventionResult(success=True, action_taken="task_terminated")

        return InterventionResult(success=False, action_taken="unknown")

    def escalate_intervention(
        self,
        current_level: InterventionLevel,
        reason: str,
    ) -> InterventionLevel:
        """升级干预级别

        参数：
            current_level: 当前级别
            reason: 升级原因

        返回：
            新的干预级别
        """
        new_level = InterventionLevel.next_level(current_level)

        logger.info(f"[ESCALATION] {current_level.value} -> {new_level.value}: {reason}")

        return new_level


__all__ = ["InterventionCoordinator"]
