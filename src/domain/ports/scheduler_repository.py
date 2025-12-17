"""SchedulerRepository Port - 定时工作流持久化端口

Domain 通过端口依赖抽象，不直接依赖 ORM/基础设施实现。
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Protocol, TypeAlias

from src.domain.entities.scheduled_workflow import ScheduledWorkflow


class SchedulerRepository(Protocol):
    def save(self, entity: ScheduledWorkflow) -> None: ...

    def get_by_id(self, scheduled_workflow_id: str) -> ScheduledWorkflow: ...

    def find_all(self) -> list[ScheduledWorkflow]: ...

    def find_active(self) -> list[ScheduledWorkflow]: ...

    def delete(self, scheduled_workflow_id: str) -> None: ...


SchedulerRepositoryProvider: TypeAlias = Callable[
    [], AbstractContextManager[SchedulerRepository]
]
