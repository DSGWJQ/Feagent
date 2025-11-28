"""Workflow feature DTOs."""

from typing import Any

from pydantic import BaseModel, Field


class ScheduleWorkflowRequest(BaseModel):
    """Request payload for creating a scheduled workflow."""

    cron_expression: str = Field(..., description="Cron expression", examples=["0 9 * * MON-FRI"])
    max_retries: int = Field(default=3, description="Maximum retry count", ge=0)


class ScheduledWorkflowResponse(BaseModel):
    """Response describing a scheduled workflow."""

    id: str
    workflow_id: str
    cron_expression: str
    status: str = Field(description="Status: active/disabled/paused")
    next_execution_time: str | None = None
    max_retries: int = 0
    consecutive_failures: int = 0

    @classmethod
    def from_entity(cls, entity: Any) -> "ScheduledWorkflowResponse":
        return cls(
            id=entity.id,
            workflow_id=entity.workflow_id,
            cron_expression=entity.cron_expression,
            status=entity.status,
            next_execution_time=str(getattr(entity, "next_execution_time", "") or "")
            if getattr(entity, "next_execution_time", None)
            else None,
            max_retries=entity.max_retries,
            consecutive_failures=entity.consecutive_failures,
        )


class ExecuteConcurrentWorkflowsRequest(BaseModel):
    """Request body for executing workflows concurrently."""

    workflow_ids: list[str] = Field(..., description="Workflow IDs")
    max_concurrent: int = Field(default=5, description="Maximum concurrent executions", ge=1)


class ExecutionResultResponse(BaseModel):
    """Execution result response."""

    workflow_id: str
    run_id: str
    status: str = Field(description="submitted/running/succeeded/failed")

    @classmethod
    def from_entity(cls, entity: Any) -> "ExecutionResultResponse":
        return cls(workflow_id=entity.workflow_id, run_id=entity.run_id, status=entity.status)


class ChatMessageRequest(BaseModel):
    """Chat workflow message request."""

    message: str = Field(..., description="User message", min_length=1)


class ChatMessageResponse(BaseModel):
    """Chat workflow message response."""

    role: str = Field(description="user/assistant")
    content: str = Field(description="Message content")


class EnhancedChatWorkflowResponse(BaseModel):
    """LLM-assisted workflow editing response."""

    success: bool
    response: str | None = None
    error_message: str | None = None
    modified_workflow: dict | None = None

    @classmethod
    def from_entity(cls, entity: Any) -> "EnhancedChatWorkflowResponse":
        return cls(
            success=entity.success,
            response=getattr(entity, "response", None),
            error_message=getattr(entity, "error_message", None),
            modified_workflow=getattr(entity, "modified_workflow", None),
        )
