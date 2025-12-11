"""干预日志记录器

Phase 34.15: 从 intervention_system.py 提取 InterventionLogger
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from .models import InterventionLevel

logger = logging.getLogger(__name__)


class InterventionLogger:
    """干预日志记录器

    记录所有干预操作。
    """

    def __init__(self):
        """初始化"""
        self._logs: list[dict[str, Any]] = []

    def log_node_replacement(
        self,
        workflow_id: str,
        original_node_id: str,
        replacement_node_id: str | None,
        reason: str,
        session_id: str,
    ) -> None:
        """记录节点替换"""
        log_entry = {
            "type": "node_replacement",
            "workflow_id": workflow_id,
            "original_node_id": original_node_id,
            "replacement_node_id": replacement_node_id,
            "reason": reason,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
        }

        self._logs.append(log_entry)

        logger.info(
            f"[INTERVENTION] type=node_replacement "
            f"workflow={workflow_id} "
            f"node={original_node_id} -> {replacement_node_id} "
            f"reason={reason}"
        )

    def log_task_termination(
        self,
        session_id: str,
        reason: str,
        error_code: str,
    ) -> None:
        """记录任务终止"""
        log_entry = {
            "type": "task_termination",
            "session_id": session_id,
            "reason": reason,
            "error_code": error_code,
            "timestamp": datetime.now().isoformat(),
        }

        self._logs.append(log_entry)

        logger.info(
            f"[INTERVENTION] type=task_termination "
            f"session={session_id} "
            f"error_code={error_code} "
            f"reason={reason}"
        )

    def log_intervention(
        self,
        level: InterventionLevel,
        session_id: str,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """记录通用干预"""
        log_entry = {
            "type": "intervention",
            "level": level.value,
            "session_id": session_id,
            "action": action,
            "details": details or {},
            "timestamp": datetime.now().isoformat(),
        }

        self._logs.append(log_entry)

        logger.info(
            f"[INTERVENTION] level={level.value} " f"session={session_id} " f"action={action}"
        )

    def get_logs(self) -> list[dict[str, Any]]:
        """获取所有日志"""
        return self._logs.copy()

    def get_logs_by_session(self, session_id: str) -> list[dict[str, Any]]:
        """按会话获取日志"""
        return [log for log in self._logs if log.get("session_id") == session_id]

    def clear(self) -> None:
        """清空日志"""
        self._logs.clear()


__all__ = ["InterventionLogger"]
