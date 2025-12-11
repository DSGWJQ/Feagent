"""干预系统事件定义

Phase 34.15: 从 intervention_system.py 提取事件模型

提供干预系统使用的事件类：
- NodeReplacedEvent: 节点替换事件
- TaskTerminatedEvent: 任务终止事件
- UserErrorNotificationEvent: 用户错误通知事件
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.services.event_bus import Event


# =============================================================================
# 事件定义
# =============================================================================


@dataclass
class NodeReplacedEvent(Event):
    """节点替换事件"""

    workflow_id: str = ""
    original_node_id: str = ""
    replacement_node_id: str = ""
    reason: str = ""
    session_id: str = ""

    @property
    def event_type(self) -> str:
        return "node_replaced"


@dataclass
class TaskTerminatedEvent(Event):
    """任务终止事件"""

    session_id: str = ""
    reason: str = ""
    error_code: str = ""

    @property
    def event_type(self) -> str:
        return "task_terminated"


@dataclass
class UserErrorNotificationEvent(Event):
    """用户错误通知事件"""

    session_id: str = ""
    error_code: str = ""
    error_message: str = ""
    user_friendly_message: str = ""

    @property
    def event_type(self) -> str:
        return "user_error_notification"


__all__ = [
    "NodeReplacedEvent",
    "TaskTerminatedEvent",
    "UserErrorNotificationEvent",
]
