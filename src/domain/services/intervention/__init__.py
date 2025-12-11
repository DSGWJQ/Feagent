"""干预系统包

Phase 34.15: intervention 包统一导出

将 intervention_system.py 拆分为模块化包结构：
- models.py: 数据模型和枚举（InterventionLevel, 请求/结果数据类）
- events.py: 事件定义（NodeReplacedEvent, TaskTerminatedEvent, UserErrorNotificationEvent）
- logger.py: 日志记录（InterventionLogger）
- workflow_modifier.py: 工作流修改（WorkflowModifier）
- task_terminator.py: 任务终止（TaskTerminator）
- coordinator.py: 协调器（InterventionCoordinator）
"""

from __future__ import annotations

from .coordinator import InterventionCoordinator
from .events import NodeReplacedEvent, TaskTerminatedEvent, UserErrorNotificationEvent
from .logger import InterventionLogger
from .models import (
    InterventionLevel,
    InterventionResult,
    ModificationResult,
    NodeReplacementRequest,
    TaskTerminationRequest,
    TerminationResult,
    ValidationResult,
)
from .task_terminator import TaskTerminator
from .workflow_modifier import WorkflowModifier

__all__ = [
    # 枚举
    "InterventionLevel",
    # 请求数据类
    "NodeReplacementRequest",
    "TaskTerminationRequest",
    # 结果数据类
    "ModificationResult",
    "ValidationResult",
    "TerminationResult",
    "InterventionResult",
    # 事件
    "NodeReplacedEvent",
    "TaskTerminatedEvent",
    "UserErrorNotificationEvent",
    # 业务模块
    "InterventionLogger",
    "WorkflowModifier",
    "TaskTerminator",
    "InterventionCoordinator",
]
