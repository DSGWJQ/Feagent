"""干预系统模块（向后兼容）

⚠️ DEPRECATED: 本模块已在 Phase 34.15 拆分为子包 `intervention/`

新导入路径：
    from src.domain.services.intervention import InterventionCoordinator
    from src.domain.services.intervention import WorkflowModifier
    from src.domain.services.intervention import TaskTerminator
    from src.domain.services.intervention import InterventionLogger
    from src.domain.services.intervention import InterventionLevel
    from src.domain.services.intervention import NodeReplacementRequest
    ...

本文件保留向后兼容性，所有导入均转发至新包。

旧导入方式仍然有效：
    from src.domain.services.intervention_system import InterventionCoordinator  # 仍可用

建议迁移：
    - 更新导入语句使用新包路径
    - 代码逻辑保持不变
    - 所有 API 接口完全兼容

模块结构：
    intervention/
    ├── __init__.py          # 包导出
    ├── models.py            # 数据模型（InterventionLevel, 请求/结果数据类）
    ├── events.py            # 事件定义（NodeReplacedEvent, TaskTerminatedEvent, UserErrorNotificationEvent）
    ├── logger.py            # 日志记录（InterventionLogger）
    ├── workflow_modifier.py # 工作流修改（WorkflowModifier）
    ├── task_terminator.py   # 任务终止（TaskTerminator）
    └── coordinator.py       # 协调器（InterventionCoordinator）

业务定义：
- 为 Coordinator 提供修改工作流定义的接口（替换/移除节点）
- 提供终止任务的指令通道（通知 ConversationAgent、WorkflowAgent、用户）
- 支持干预级别升级机制

设计原则：
- 干预级别递进：NONE → NOTIFY → WARN → REPLACE → TERMINATE
- 完整日志：记录每次干预操作
- 通知机制：支持多目标通知

实现日期：2025-12-08
Phase 34.15: 2025-12-12 拆分为模块化包
"""

from __future__ import annotations

# ==================== 向后兼容导入 ====================
# 从新包导入所有组件并重新导出
from src.domain.services.intervention import (
    InterventionCoordinator,
    InterventionLevel,
    InterventionLogger,
    InterventionResult,
    ModificationResult,
    NodeReplacedEvent,
    NodeReplacementRequest,
    TaskTerminatedEvent,
    TaskTerminationRequest,
    TaskTerminator,
    TerminationResult,
    UserErrorNotificationEvent,
    ValidationResult,
    WorkflowModifier,
)

# ==================== 导出列表（保持不变）====================
__all__ = [
    "InterventionLevel",
    "NodeReplacementRequest",
    "TaskTerminationRequest",
    "ModificationResult",
    "ValidationResult",
    "TerminationResult",
    "InterventionResult",
    "NodeReplacedEvent",
    "TaskTerminatedEvent",
    "UserErrorNotificationEvent",
    "InterventionLogger",
    "WorkflowModifier",
    "TaskTerminator",
    "InterventionCoordinator",
]
