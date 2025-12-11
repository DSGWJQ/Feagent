"""任务终止器

Phase 34.15: 从 intervention_system.py 提取 TaskTerminator
"""

from __future__ import annotations

import logging

from .events import TaskTerminatedEvent
from .logger import InterventionLogger
from .models import TaskTerminationRequest, TerminationResult

logger = logging.getLogger(__name__)


class TaskTerminator:
    """任务终止器

    提供终止任务的指令通道。
    """

    def __init__(self, logger: InterventionLogger | None = None):
        """初始化

        参数：
            logger: 干预日志记录器
        """
        self._logger = logger or InterventionLogger()

    def terminate(self, request: TaskTerminationRequest) -> TerminationResult:
        """终止任务

        参数：
            request: 终止请求

        返回：
            终止结果
        """
        notified_agents = []
        user_message = None

        # 通知 Agent
        for agent_type in request.notify_agents:
            self._notify_agent(agent_type, request.session_id, request.reason)
            notified_agents.append(agent_type)

        # 通知用户
        user_notified = False
        if request.notify_user:
            user_message = self._create_user_message(request)
            user_notified = True

        # 创建错误事件
        error_event = TaskTerminatedEvent(
            session_id=request.session_id,
            reason=request.reason,
            error_code=request.error_code,
        )

        # 记录日志
        self._logger.log_task_termination(
            session_id=request.session_id,
            reason=request.reason,
            error_code=request.error_code,
        )

        return TerminationResult(
            success=True,
            session_id=request.session_id,
            notified_agents=notified_agents,
            user_notified=user_notified,
            user_message=user_message,
            error_event=error_event,
        )

    def _notify_agent(self, agent_type: str, session_id: str, reason: str) -> None:
        """通知 Agent

        参数：
            agent_type: Agent 类型
            session_id: 会话 ID
            reason: 终止原因
        """
        logger.info(
            f"[TERMINATION] Notifying {agent_type} agent: " f"session={session_id} reason={reason}"
        )

    def _create_user_message(self, request: TaskTerminationRequest) -> str:
        """创建用户消息

        参数：
            request: 终止请求

        返回：
            用户友好的错误消息
        """
        return (
            f"任务已终止 [错误代码: {request.error_code}]\n"
            f"原因: {request.reason}\n"
            f"如需帮助，请联系管理员。"
        )


__all__ = ["TaskTerminator"]
