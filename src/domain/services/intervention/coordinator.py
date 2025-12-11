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
            # ✅ Phase 35.0 修复：实际调用 WorkflowModifier
            request = self._build_replacement_request(context)
            workflow_def = context.get("workflow_definition", {})
            result = self._workflow_modifier.replace_node(workflow_def, request)

            self._logger.log_intervention(level, session_id, "node_replaced", context)

            # 将 ModificationResult 转换为字典以包含在 details 中
            return InterventionResult(
                success=result.success,
                action_taken="node_replaced",
                details={
                    "modification": {
                        "success": result.success,
                        "modified_workflow": result.modified_workflow,
                        "error": result.error,
                        "original_node_id": result.original_node_id,
                        "replacement_node_id": result.replacement_node_id,
                    }
                },
            )

        elif level == InterventionLevel.TERMINATE:
            # ✅ Phase 35.0 修复：实际调用 TaskTerminator
            request = self._build_termination_request(context)
            result = self._task_terminator.terminate(request)

            self._logger.log_intervention(level, session_id, "task_terminated", context)

            # 将 TerminationResult 转换为字典以包含在 details 中
            return InterventionResult(
                success=result.success,
                action_taken="task_terminated",
                details={
                    "termination": {
                        "success": result.success,
                        "session_id": result.session_id,
                        "notified_agents": result.notified_agents,
                        "user_notified": result.user_notified,
                        "user_message": result.user_message,
                    }
                },
            )

        return InterventionResult(success=False, action_taken="unknown")

    def _build_replacement_request(self, context: dict[str, Any]):
        """从上下文构建节点替换请求

        参数：
            context: 上下文数据

        返回：
            NodeReplacementRequest
        """
        from .models import NodeReplacementRequest

        return NodeReplacementRequest(
            workflow_id=context.get("workflow_id", ""),
            original_node_id=context.get("node_id", ""),
            replacement_node_config=context.get("replacement_config"),
            reason=context.get("reason", "Intervention triggered"),
            session_id=context.get("session_id", ""),
        )

    def _build_termination_request(self, context: dict[str, Any]):
        """从上下文构建任务终止请求

        参数：
            context: 上下文数据

        返回：
            TaskTerminationRequest
        """
        from .models import TaskTerminationRequest

        return TaskTerminationRequest(
            session_id=context.get("session_id", ""),
            reason=context.get("reason", "Intervention triggered"),
            error_code=context.get("error_code", "INTERVENTION_TERMINATE"),
            notify_agents=context.get("notify_agents", ["conversation", "workflow"]),
            notify_user=context.get("notify_user", True),
        )

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
