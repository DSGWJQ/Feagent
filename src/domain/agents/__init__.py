"""Agent模块

包含多Agent协作系统的核心Agent实现：
- ConversationAgent: 对话Agent，基于ReAct循环
- WorkflowAgent: 工作流Agent，负责执行
- CoordinatorAgent: 协调者Agent，负责验证
"""

from src.domain.agents.conversation_agent import (
    ConversationAgent,
    Decision,
    DecisionMadeEvent,
    DecisionType,
    ReActResult,
    ReActStep,
    StepType,
)
from src.domain.agents.coordinator_agent import (
    CoordinatorAgent,
    DecisionRejectedEvent,
    DecisionValidatedEvent,
    Rule,
    ValidationResult,
)
from src.domain.agents.workflow_agent import (
    Edge,
    ExecutionStatus,
    NodeExecutionEvent,
    WorkflowAgent,
    WorkflowExecutionCompletedEvent,
    WorkflowExecutionStartedEvent,
)

__all__ = [
    # ConversationAgent
    "ConversationAgent",
    "Decision",
    "DecisionType",
    "DecisionMadeEvent",
    "ReActStep",
    "StepType",
    "ReActResult",
    # WorkflowAgent
    "WorkflowAgent",
    "ExecutionStatus",
    "Edge",
    "WorkflowExecutionStartedEvent",
    "WorkflowExecutionCompletedEvent",
    "NodeExecutionEvent",
    # CoordinatorAgent
    "CoordinatorAgent",
    "Rule",
    "ValidationResult",
    "DecisionValidatedEvent",
    "DecisionRejectedEvent",
]
