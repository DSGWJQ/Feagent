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
    "StepType",
    "IntentType",
    "ReActStep",
    "ReActResult",
    "get_decision_type_map",
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


class StepType(str, Enum):
    """ReAct步骤类型"""

    REASONING = "reasoning"  # 推理步骤
    ACTION = "action"  # 行动步骤
    OBSERVATION = "observation"  # 观察步骤
    FINAL = "final"  # 最终回复


class IntentType(str, Enum):
    """意图类型 (Phase 14)

    用于区分用户输入的意图，决定是否需要 ReAct 循环。
    """

    CONVERSATION = "conversation"  # 普通对话（不需要 ReAct）
    WORKFLOW_MODIFICATION = "workflow_modification"  # 工作流修改（需要 ReAct）
    WORKFLOW_QUERY = "workflow_query"  # 查询工作流状态
    CLARIFICATION = "clarification"  # 澄清请求
    ERROR_RECOVERY_REQUEST = "error_recovery_request"  # 错误恢复请求


@dataclass
class ReActStep:
    """ReAct循环的单个步骤

    属性：
    - step_type: 步骤类型
    - thought: 思考内容
    - action: 行动内容
    - observation: 观察结果
    - timestamp: 时间戳
    """

    step_type: StepType
    thought: str | None = None
    action: dict[str, Any] | None = None
    observation: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ReActResult:
    """ReAct循环的最终结果

    属性：
    - completed: 是否完成
    - final_response: 最终回复
    - iterations: 迭代次数
    - terminated_by_limit: 是否因达到限制而终止
    - steps: 所有步骤历史
    - limit_type: 限制类型（阶段5新增）
    - total_tokens: 总 token 消耗（阶段5新增）
    - total_cost: 总成本（阶段5新增）
    - execution_time: 执行时间秒（阶段5新增）
    - alert_message: 告警消息（阶段5新增）
    """

    completed: bool = False
    final_response: str | None = None
    iterations: int = 0
    terminated_by_limit: bool = False
    steps: list[ReActStep] = field(default_factory=list)
    # 阶段5新增：循环控制相关字段
    limit_type: str | None = None
    total_tokens: int = 0
    total_cost: float = 0.0
    execution_time: float = 0.0
    alert_message: str | None = None


# =========================================================================
# Decision Type Mapping Helper (P1-7 Phase 6)
# =========================================================================

_DECISION_TYPE_MAP: dict[str, DecisionType] | None = None


def get_decision_type_map() -> dict[str, DecisionType]:
    """获取决策类型映射（延迟初始化）

    将action_type字符串映射到DecisionType枚举。
    此函数使用延迟初始化模式以避免模块导入时的额外开销。

    Returns:
        dict mapping action_type strings to DecisionType enums

    Example:
        >>> decision_map = get_decision_type_map()
        >>> decision_map["create_node"]
        <DecisionType.CREATE_NODE: 'create_node'>
    """
    global _DECISION_TYPE_MAP
    if _DECISION_TYPE_MAP is None:
        _DECISION_TYPE_MAP = {
            "create_node": DecisionType.CREATE_NODE,
            "create_workflow_plan": DecisionType.CREATE_WORKFLOW_PLAN,
            "execute_workflow": DecisionType.EXECUTE_WORKFLOW,
            "modify_node": DecisionType.MODIFY_NODE,
            "request_clarification": DecisionType.REQUEST_CLARIFICATION,
            "respond": DecisionType.RESPOND,
            "continue": DecisionType.CONTINUE,
            "error_recovery": DecisionType.ERROR_RECOVERY,
            "replan_workflow": DecisionType.REPLAN_WORKFLOW,
            "spawn_subagent": DecisionType.SPAWN_SUBAGENT,
        }
    return _DECISION_TYPE_MAP
