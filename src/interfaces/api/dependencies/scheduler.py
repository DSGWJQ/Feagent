"""Scheduler service dependency registry."""

from typing import Optional

from fastapi import Depends, HTTPException, status

from src.domain.services.workflow_scheduler import ScheduleWorkflowService

_scheduler_service: Optional[ScheduleWorkflowService] = None


def set_scheduler_service(service: ScheduleWorkflowService) -> None:
    """Register global scheduler service instance."""
    global _scheduler_service
    _scheduler_service = service


def clear_scheduler_service() -> None:
    """Reset scheduler service (used on shutdown/tests)."""
    global _scheduler_service
    _scheduler_service = None


def get_scheduler_service() -> ScheduleWorkflowService:
    """FastAPI dependency to fetch scheduler service."""
    if _scheduler_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler service has not been initialized.",
        )
    return _scheduler_service


def scheduler_service_dependency(
    scheduler: ScheduleWorkflowService = Depends(get_scheduler_service),
) -> ScheduleWorkflowService:
    """Expose as dependency for routers."""
    return scheduler
