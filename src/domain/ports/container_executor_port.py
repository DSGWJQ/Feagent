from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.domain.agents.container_executor import ContainerConfig, ContainerExecutionResult


@runtime_checkable
class ContainerExecutorPort(Protocol):
    """容器执行器端口（Domain）"""

    def is_available(self) -> bool: ...

    def execute(
        self,
        code: str,
        config: ContainerConfig | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> ContainerExecutionResult: ...

    async def execute_async(
        self,
        code: str,
        config: ContainerConfig | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> ContainerExecutionResult: ...
