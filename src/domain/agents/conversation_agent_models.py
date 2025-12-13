"""ConversationAgent shared models module.

This module contains Decision and DecisionType that were extracted from
conversation_agent.py to break circular dependencies (P1-6 Phase 3/4).

By placing these types in a separate module, both conversation_agent.py
and its mixins (workflow/recovery) can import them without creating
circular dependency chains.

Design principles:
- Keep models simple and focused on data representation
- Avoid complex logic or dependencies
- Enable clean dependency graphs for mixin modules
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

__all__ = [
    "DecisionType",
    "Decision",
]


class DecisionType(str, Enum):
    """决策类型

    用于标识对话Agent做出的决策类型。

    枚举值：
    - CREATE_NODE: 创建节点
    - CREATE_WORKFLOW_PLAN: 创建完整工作流规划（Phase 8）
    - EXECUTE_WORKFLOW: 执行工作流
    - MODIFY_NODE: 修改节点定义（Phase 8）
    - REQUEST_CLARIFICATION: 请求澄清
    - RESPOND: 直接回复
    - CONTINUE: 继续推理
    - ERROR_RECOVERY: 错误恢复（Phase 13）
    - REPLAN_WORKFLOW: 重新规划工作流（Phase 13）
    - SPAWN_SUBAGENT: 生成子Agent（Phase 3）
    """

    CREATE_NODE = "create_node"
    CREATE_WORKFLOW_PLAN = "create_workflow_plan"
    EXECUTE_WORKFLOW = "execute_workflow"
    MODIFY_NODE = "modify_node"
    REQUEST_CLARIFICATION = "request_clarification"
    RESPOND = "respond"
    CONTINUE = "continue"
    ERROR_RECOVERY = "error_recovery"
    REPLAN_WORKFLOW = "replan_workflow"
    SPAWN_SUBAGENT = "spawn_subagent"


@dataclass
class Decision:
    """决策实体

    封装对话Agent做出的决策信息。

    属性：
    - id: 决策唯一标识（UUID格式字符串）
    - type: 决策类型（DecisionType枚举）
    - payload: 决策负载，包含决策的具体内容
    - confidence: 决策置信度（0-1之间）
    - timestamp: 决策生成时间戳

    示例：
        decision = Decision(
            type=DecisionType.CREATE_NODE,
            payload={"node_type": "python", "code": "..."},
            confidence=0.95
        )
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    type: DecisionType = DecisionType.CONTINUE
    payload: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=datetime.now)
