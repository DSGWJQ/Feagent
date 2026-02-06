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
        def _safe_int(value: Any, default: int = 0) -> int:
            if isinstance(value, bool):  # bool is a subclass of int
                return int(value)
            if isinstance(value, int):
                return value
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        return cls(
            id=entity.id,
            workflow_id=entity.workflow_id,
            cron_expression=entity.cron_expression,
            status=entity.status,
            next_execution_time=str(getattr(entity, "next_execution_time", "") or "")
            if getattr(entity, "next_execution_time", None)
            else None,
            max_retries=_safe_int(getattr(entity, "max_retries", 0), default=0),
            consecutive_failures=_safe_int(
                getattr(entity, "consecutive_failures", 0),
                default=0,
            ),
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
