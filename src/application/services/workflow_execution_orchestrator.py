"""WorkflowExecutionOrchestrator - 统一 workflow 执行入口（含 policy chain）

目标：
- Interface 层不直接编排 Use Case / Facade 的执行细节
- 将“执行前/执行后/事件回调”等治理逻辑抽象为可插拔的 policy chain
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncGenerator, Awaitable, Callable, Iterable
from typing import Any, Protocol

from src.application.services.coordinator_policy_chain import (
    CoordinatorPolicyChain,
    CoordinatorPort,
)
from src.application.services.idempotency_coordinator import IdempotencyCoordinator
from src.application.services.workflow_execution_facade import WorkflowExecutionFacade
from src.domain.services.event_bus import EventBus


def _supports_kwarg(callable_obj: Any, name: str) -> bool:
    """Best-effort check for whether a callable accepts a given keyword argument.

    Why:
    - Some tests inject a lightweight fake facade that doesn't accept newer keyword args
      (e.g. correlation_id / original_decision_id).
    - We keep the orchestrator defensive while still passing through the richer contract
      for the real facade implementation.
    """

    try:
        signature = inspect.signature(callable_obj)
    except (TypeError, ValueError):  # pragma: no cover - defensive fallback
        return False

    parameters = signature.parameters
    if name in parameters:
        return True

    # Accepts **kwargs
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values())


class WorkflowExecutionPolicy(Protocol):
    async def before_execute(
        self,
        *,
        workflow_id: str,
        input_data: Any,
        correlation_id: str | None,
        original_decision_id: str | None,
    ) -> None: ...

    async def after_execute(
        self,
        *,
        workflow_id: str,
        input_data: Any,
        result: dict[str, Any],
        correlation_id: str | None,
        original_decision_id: str | None,
    ) -> None: ...

    async def on_error(
        self,
        *,
        workflow_id: str,
        input_data: Any,
        error: Exception,
        correlation_id: str | None,
        original_decision_id: str | None,
    ) -> None: ...

    async def on_event(
        self,
        *,
        workflow_id: str,
        input_data: Any,
        event: dict[str, Any],
        correlation_id: str | None,
        original_decision_id: str | None,
    ) -> None: ...


class WorkflowExecutionOrchestrator:
    def __init__(
        self,
        *,
        facade: WorkflowExecutionFacade,
        policies: Iterable[WorkflowExecutionPolicy] = (),
        idempotency: IdempotencyCoordinator | None = None,
    ) -> None:
        self._facade = facade
        self._policies = list(policies)
        self._idempotency = idempotency

    async def execute(
        self,
        *,
        workflow_id: str,
        input_data: Any = None,
        idempotency_key: str | None = None,
        correlation_id: str | None = None,
        original_decision_id: str | None = None,
        after_gate: Callable[[], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        await self.gate_execute(
            workflow_id=workflow_id,
            input_data=input_data,
            correlation_id=correlation_id,
            original_decision_id=original_decision_id,
            after_gate=after_gate,
        )

        try:
            facade_kwargs: dict[str, Any] = {
                "workflow_id": workflow_id,
                "input_data": input_data,
            }
            if _supports_kwarg(self._facade.execute, "correlation_id"):
                facade_kwargs["correlation_id"] = correlation_id
            if _supports_kwarg(self._facade.execute, "original_decision_id"):
                facade_kwargs["original_decision_id"] = original_decision_id

            if idempotency_key is None:
                result = await self._facade.execute(**facade_kwargs)
            else:
                if self._idempotency is None:
                    raise RuntimeError("Idempotency requested but IdempotencyCoordinator not set")

                async def _work() -> dict[str, Any]:
                    return await self._facade.execute(**facade_kwargs)

                result = await self._idempotency.run(
                    idempotency_key=idempotency_key,
                    work=_work,
                )
        except Exception as exc:  # noqa: BLE001 - orchestrator is the central boundary
            for policy in self._policies:
                await policy.on_error(
                    workflow_id=workflow_id,
                    input_data=input_data,
                    error=exc,
                    correlation_id=correlation_id,
                    original_decision_id=original_decision_id,
                )
            raise

        for policy in reversed(self._policies):
            await policy.after_execute(
                workflow_id=workflow_id,
                input_data=input_data,
                result=result,
                correlation_id=correlation_id,
                original_decision_id=original_decision_id,
            )

        return result

    async def gate_execute(
        self,
        *,
        workflow_id: str,
        input_data: Any = None,
        correlation_id: str | None = None,
        original_decision_id: str | None = None,
        after_gate: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        for policy in self._policies:
            await policy.before_execute(
                workflow_id=workflow_id,
                input_data=input_data,
                correlation_id=correlation_id,
                original_decision_id=original_decision_id,
            )

        if after_gate is not None:
            await after_gate()

    async def stream_after_gate(
        self,
        *,
        workflow_id: str,
        input_data: Any = None,
        correlation_id: str | None = None,
        original_decision_id: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        try:
            facade_kwargs: dict[str, Any] = {
                "workflow_id": workflow_id,
                "input_data": input_data,
            }
            if _supports_kwarg(self._facade.execute_streaming, "correlation_id"):
                facade_kwargs["correlation_id"] = correlation_id
            if _supports_kwarg(self._facade.execute_streaming, "original_decision_id"):
                facade_kwargs["original_decision_id"] = original_decision_id

            async for event in self._facade.execute_streaming(
                **facade_kwargs,
            ):
                for policy in self._policies:
                    await policy.on_event(
                        workflow_id=workflow_id,
                        input_data=input_data,
                        event=event,
                        correlation_id=correlation_id,
                        original_decision_id=original_decision_id,
                    )
                yield event
        except Exception as exc:  # noqa: BLE001 - orchestrator is the central boundary
            for policy in self._policies:
                await policy.on_error(
                    workflow_id=workflow_id,
                    input_data=input_data,
                    error=exc,
                    correlation_id=correlation_id,
                    original_decision_id=original_decision_id,
                )
            raise

    async def execute_streaming(
        self,
        *,
        workflow_id: str,
        input_data: Any = None,
        correlation_id: str | None = None,
        original_decision_id: str | None = None,
        after_gate: Callable[[], Awaitable[None]] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        await self.gate_execute(
            workflow_id=workflow_id,
            input_data=input_data,
            correlation_id=correlation_id,
            original_decision_id=original_decision_id,
            after_gate=after_gate,
        )
        async for event in self.stream_after_gate(
            workflow_id=workflow_id,
            input_data=input_data,
            correlation_id=correlation_id,
            original_decision_id=original_decision_id,
        ):
            yield event


class NoopWorkflowExecutionPolicy:
    async def before_execute(
        self,
        *,
        workflow_id: str,
        input_data: Any,
        correlation_id: str | None,
        original_decision_id: str | None,
    ) -> None:
        return None

    async def after_execute(
        self,
        *,
        workflow_id: str,
        input_data: Any,
        result: dict[str, Any],
        correlation_id: str | None,
        original_decision_id: str | None,
    ) -> None:
        return None

    async def on_error(
        self,
        *,
        workflow_id: str,
        input_data: Any,
        error: Exception,
        correlation_id: str | None,
        original_decision_id: str | None,
    ) -> None:
        return None

    async def on_event(
        self,
        *,
        workflow_id: str,
        input_data: Any,
        event: dict[str, Any],
        correlation_id: str | None,
        original_decision_id: str | None,
    ) -> None:
        return None


class CoordinatorWorkflowExecutionPolicy:
    """将 workflow 执行的监督点下沉到 Application policy chain（WF-060）。

    注意：不把 input_data 透传给 coordinator，避免潜在敏感信息泄露。
    """

    def __init__(
        self,
        *,
        coordinator: CoordinatorPort | None,
        event_bus: EventBus | None,
        source: str,
        fail_closed: bool = True,
    ) -> None:
        self._policy = CoordinatorPolicyChain(
            coordinator=coordinator,
            event_bus=event_bus,
            source=source,
            fail_closed=fail_closed,
            supervised_decision_types={"api_request"},
        )

    async def before_execute(
        self,
        *,
        workflow_id: str,
        input_data: Any,
        correlation_id: str | None,
        original_decision_id: str | None,
    ) -> None:
        correlation = correlation_id or workflow_id
        original = original_decision_id or correlation
        await self._policy.enforce_action_or_raise(
            decision_type="api_request",
            decision={
                "decision_type": "api_request",
                "action": "execute_workflow",
                "workflow_id": workflow_id,
                "correlation_id": correlation,
            },
            correlation_id=correlation,
            original_decision_id=original,
        )

    async def after_execute(
        self,
        *,
        workflow_id: str,
        input_data: Any,
        result: dict[str, Any],
        correlation_id: str | None,
        original_decision_id: str | None,
    ) -> None:
        return None

    async def on_error(
        self,
        *,
        workflow_id: str,
        input_data: Any,
        error: Exception,
        correlation_id: str | None,
        original_decision_id: str | None,
    ) -> None:
        return None

    async def on_event(
        self,
        *,
        workflow_id: str,
        input_data: Any,
        event: dict[str, Any],
        correlation_id: str | None,
        original_decision_id: str | None,
    ) -> None:
        return None
