"""WorkflowExecutionOrchestrator - 统一 workflow 执行入口（含 policy chain）

目标：
- Interface 层不直接编排 Use Case / Facade 的执行细节
- 将“执行前/执行后/事件回调”等治理逻辑抽象为可插拔的 policy chain
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterable
from typing import Any, Protocol

from src.application.services.workflow_execution_facade import WorkflowExecutionFacade


class WorkflowExecutionPolicy(Protocol):
    async def before_execute(self, *, workflow_id: str, input_data: Any) -> None: ...

    async def after_execute(
        self, *, workflow_id: str, input_data: Any, result: dict[str, Any]
    ) -> None: ...

    async def on_error(self, *, workflow_id: str, input_data: Any, error: Exception) -> None: ...

    async def on_event(
        self, *, workflow_id: str, input_data: Any, event: dict[str, Any]
    ) -> None: ...


class WorkflowExecutionOrchestrator:
    def __init__(
        self,
        *,
        facade: WorkflowExecutionFacade,
        policies: Iterable[WorkflowExecutionPolicy] = (),
    ) -> None:
        self._facade = facade
        self._policies = list(policies)

    async def execute(self, *, workflow_id: str, input_data: Any = None) -> dict[str, Any]:
        for policy in self._policies:
            await policy.before_execute(workflow_id=workflow_id, input_data=input_data)

        try:
            result = await self._facade.execute(workflow_id=workflow_id, input_data=input_data)
        except Exception as exc:  # noqa: BLE001 - orchestrator is the central boundary
            for policy in self._policies:
                await policy.on_error(workflow_id=workflow_id, input_data=input_data, error=exc)
            raise

        for policy in reversed(self._policies):
            await policy.after_execute(
                workflow_id=workflow_id, input_data=input_data, result=result
            )

        return result

    async def execute_streaming(
        self,
        *,
        workflow_id: str,
        input_data: Any = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        for policy in self._policies:
            await policy.before_execute(workflow_id=workflow_id, input_data=input_data)

        try:
            async for event in self._facade.execute_streaming(
                workflow_id=workflow_id,
                input_data=input_data,
            ):
                for policy in self._policies:
                    await policy.on_event(
                        workflow_id=workflow_id, input_data=input_data, event=event
                    )
                yield event
        except Exception as exc:  # noqa: BLE001 - orchestrator is the central boundary
            for policy in self._policies:
                await policy.on_error(workflow_id=workflow_id, input_data=input_data, error=exc)
            raise


class NoopWorkflowExecutionPolicy:
    async def before_execute(self, *, workflow_id: str, input_data: Any) -> None:
        return None

    async def after_execute(
        self, *, workflow_id: str, input_data: Any, result: dict[str, Any]
    ) -> None:
        return None

    async def on_error(self, *, workflow_id: str, input_data: Any, error: Exception) -> None:
        return None

    async def on_event(self, *, workflow_id: str, input_data: Any, event: dict[str, Any]) -> None:
        return None
