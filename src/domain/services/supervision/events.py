"""监督模块事件定义

Phase 34.14: 从 supervision_modules.py 提取事件模型

提供监督系统使用的事件类：
- InterventionEvent: 干预事件
- ContextInjectionEvent: 上下文注入事件
- TaskTerminationEvent: 任务终止事件
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.domain.services.event_bus import Event

# ==================== 事件定义 ====================


@dataclass
class InterventionEvent(Event):
    """干预事件

    当监督模块检测到问题并采取干预措施时发布。

    属性：
        intervention_type: 干预类型 (warn/block/terminate)
        reason: 干预原因
        source: 干预来源模块
        session_id: 会话ID（可选，用于追踪/审计聚合）
        target_id: 目标ID（消息/任务/工作流）
        severity: 严重性 (low/medium/high/critical)
        details: 详细信息
    """

    intervention_type: str = ""
    reason: str = ""
    source: str = ""
    session_id: str | None = None
    target_id: str = ""
    severity: str = "medium"
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def event_type(self) -> str:
        return "intervention"


@dataclass
class ContextInjectionEvent(Event):
    """上下文注入事件

    当需要向目标 Agent 注入额外上下文时发布。

    属性：
        target_agent: 目标Agent
        context_data: 注入的上下文数据
        injection_type: 注入类型 (pre_response/post_detection)
    """

    target_agent: str = ""
    context_data: dict[str, Any] = field(default_factory=dict)
    injection_type: str = "pre_response"

    @property
    def event_type(self) -> str:
        return "context_injection"


@dataclass
class TaskTerminationEvent(Event):
    """任务终止事件

    当任务被监督模块强制终止时发布。

    属性：
        task_id: 任务ID
        workflow_id: 工作流ID
        reason: 终止原因
        initiated_by: 发起终止的模块
        termination_type: 终止类型 (graceful/immediate)
        severity: 严重性 (low/medium/high/critical)
    """

    task_id: str = ""
    workflow_id: str = ""
    reason: str = ""
    initiated_by: str = ""
    termination_type: str = "graceful"
    severity: str = "medium"

    @property
    def event_type(self) -> str:
        return "task_termination"


__all__ = [
    "InterventionEvent",
    "ContextInjectionEvent",
    "TaskTerminationEvent",
]
