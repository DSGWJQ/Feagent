"""Workflow planning use-case events.

These are Application-layer events (NOT Domain Events) used for:
1. Streaming workflow planning progress to clients via SSE
2. Recording planning steps for Run replay

Events do NOT contain SSE-specific fields (sequence, channel, timestamp).
Those are added by PlanningEventMapper during serialization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.domain.entities.workflow import Workflow
    from src.domain.value_objects.research_plan import ResearchPlan


@dataclass(frozen=True)
class WorkflowPlanningStarted:
    """Emitted when planning begins.

    Attributes:
        workflow_id: ID of the workflow being modified
        user_message: Original user request
    """

    workflow_id: str
    user_message: str


@dataclass(frozen=True)
class ReActStepCompleted:
    """Emitted after each ReAct reasoning step.

    A single ReActStepCompleted may produce multiple PlanningEvents:
    - thinking (from thought)
    - tool_call (from action)
    - tool_result (from observation)

    Attributes:
        step_number: 1-based step number (first step is 1)
        thought: AI's reasoning process
        action: Tool call details (type, arguments)
        observation: Result of action execution
    """

    step_number: int
    thought: str = ""
    action: dict[str, Any] = field(default_factory=dict)
    observation: str = ""


@dataclass(frozen=True)
class WorkflowPatchGenerated:
    """Emitted when workflow modifications are ready for preview.

    Attributes:
        modifications_count: Number of changes made
        intent: Detected user intent (add_node, delete_node, etc.)
        confidence: AI confidence score (0.0-1.0)
        workflow_preview: Optional preview of modified workflow
    """

    modifications_count: int = 0
    intent: str = ""
    confidence: float = 0.0
    workflow_preview: Workflow | None = None


@dataclass(frozen=True)
class WorkflowPlanningCompleted:
    """Emitted when planning succeeds and workflow is persisted.

    This is a terminal event - no more events follow.

    Attributes:
        workflow: The modified workflow entity
        ai_message: AI's response message to user
        rag_sources: Retrieved documents used for planning
    """

    workflow: Workflow
    ai_message: str
    rag_sources: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class WorkflowPlanningFailed:
    """Emitted when planning fails.

    This is a terminal event - no more events follow.

    Attributes:
        error_code: Machine-readable error code
        detail: Human-readable error message
        details: Additional error details (optional)
    """

    error_code: str
    detail: str
    details: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ResearchPlanGenerated:
    """Emitted when a research plan is ready for preview.

    Attributes:
        plan: Structured ResearchPlan (validated separately by ResearchPlanValidator)
    """

    plan: ResearchPlan


@dataclass(frozen=True)
class ResearchPlanCompiled:
    """Emitted when a research plan is compiled into workflow nodes/edges.

    Attributes:
        workflow_id: ID of the target workflow
        plan_id: ID of the compiled research plan
        nodes_count: Number of nodes generated
        edges_count: Number of edges generated
        warnings: Compilation warnings (non-fatal issues)
    """

    workflow_id: str
    plan_id: str
    nodes_count: int
    edges_count: int
    warnings: list[str] = field(default_factory=list)


# Type union for all planning events
WorkflowPlanningEvent = (
    WorkflowPlanningStarted
    | ReActStepCompleted
    | WorkflowPatchGenerated
    | WorkflowPlanningCompleted
    | WorkflowPlanningFailed
    | ResearchPlanGenerated
    | ResearchPlanCompiled
)
