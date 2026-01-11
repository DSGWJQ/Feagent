"""Scheduler service dependency registry."""

from fastapi import Depends

from src.domain.services.workflow_scheduler import ScheduleWorkflowService

_scheduler_service: ScheduleWorkflowService | None = None


class _NullScheduler:
    def get_jobs(self):  # noqa: ANN201
        return []


class _NullScheduleWorkflowService:
    """Fallback scheduler service for routers mounted without app lifespan."""

    def __init__(self) -> None:
        self.scheduler = _NullScheduler()
        self._is_running = False

    async def trigger_execution_async(self, scheduled_workflow_id: str):  # noqa: ANN201, ARG002
        return {"status": "SKIPPED", "reason": "scheduler_not_initialized"}

    def add_job(self, job_id: str, cron_expression: str, workflow_id: str) -> None:  # noqa: ARG002
        return None

    def remove_job(self, job_id: str) -> None:  # noqa: ARG002
        return None

    def pause_job(self, job_id: str) -> None:  # noqa: ARG002
        return None

    def resume_job(self, job_id: str) -> None:  # noqa: ARG002
        return None

    def get_scheduled_job(self, scheduled_workflow_id: str):  # noqa: ANN201, ARG002
        return None

    def pause_scheduled_workflow(self, scheduled_workflow_id: str) -> None:  # noqa: ARG002
        return None

    def resume_scheduled_workflow(self, scheduled_workflow_id: str) -> None:  # noqa: ARG002
        return None


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
        # Tests mount routers without app lifespan. Return a deterministic no-op service instead
        # of failing dependency injection at import time.
        return _NullScheduleWorkflowService()  # type: ignore[return-value]
    return _scheduler_service


def scheduler_service_dependency(
    scheduler: ScheduleWorkflowService = Depends(get_scheduler_service),
) -> ScheduleWorkflowService:
    """Expose as dependency for routers."""
    return scheduler
