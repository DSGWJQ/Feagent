"""WorkflowRunExecutionEntry - Run 级权威执行编排入口（WFCORE-030）

目标：
- 将 run 门禁 / 事件落库 / 状态机驱动 / 成功判定 收敛到 Application 层
- REST execute/stream 与 WorkflowAgent execute_workflow 复用同一编排入口

原则（KISS / SRP）：
- 仅负责“编排与治理”，不实现实际执行逻辑（由 WorkflowExecutionKernelPort 承担）
- Interface 层仅做 DTO + 协议输出（SSE），不直接落库或做门禁
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Callable, Mapping
from typing import Any

from src.application.services.run_confirmation_store import run_confirmation_store
from src.application.services.workflow_event_contract import (
    ExecutionEventContractError,
    validate_workflow_execution_sse_event,
)
from src.application.use_cases.append_run_event import AppendRunEventInput, AppendRunEventUseCase
from src.domain.exceptions import DomainValidationError, NotFoundError, RunGateError
from src.domain.ports.run_repository import RunRepository
from src.domain.ports.workflow_execution_kernel import WorkflowExecutionKernelPort
from src.domain.ports.workflow_repository import WorkflowRepository
from src.domain.services.workflow_engine import topological_sort_ids
from src.domain.services.workflow_save_validator import WorkflowSaveValidator
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.run_status import RunStatus

logger = logging.getLogger(__name__)

_SIDE_EFFECT_NODE_TYPES: frozenset[NodeType] = frozenset(
    {
        NodeType.TOOL,
        NodeType.HTTP,
        NodeType.HTTP_REQUEST,
        NodeType.DATABASE,
        NodeType.FILE,
        NodeType.NOTIFICATION,
    }
)
_CONFIRM_TIMEOUT_S = 300.0


def _find_first_side_effect_node_id(*, workflow: Any) -> str | None:
    node_map = {node.id: node for node in getattr(workflow, "nodes", []) or []}
    if not node_map:
        return None

    sorted_ids = topological_sort_ids(
        node_ids=node_map.keys(),
        edges=((e.source_node_id, e.target_node_id) for e in getattr(workflow, "edges", []) or []),
    )
    for node_id in sorted_ids:
        node = node_map.get(node_id)
        if node is None:
            continue
        node_type = getattr(node, "type", None)
        if node_type in _SIDE_EFFECT_NODE_TYPES:
            return node_id
    return None


class WorkflowRunExecutionEntry:
    """Run 级权威执行编排入口（同源：REST/WorkflowAgent）。"""

    def __init__(
        self,
        *,
        workflow_repository: WorkflowRepository,
        run_repository: RunRepository,
        save_validator: WorkflowSaveValidator,
        run_event_use_case: AppendRunEventUseCase,
        kernel: WorkflowExecutionKernelPort,
        executor_id: str,
    ) -> None:
        self._workflow_repository = workflow_repository
        self._run_repository = run_repository
        self._save_validator = save_validator
        self._run_event_use_case = run_event_use_case
        self._kernel = kernel
        self._executor_id = executor_id

    def _normalize_ids(self, *, workflow_id: str, run_id: str) -> tuple[str, str]:
        if not workflow_id or not workflow_id.strip():
            raise DomainValidationError("workflow_id is required")
        if not run_id or not run_id.strip():
            raise DomainValidationError("run_id is required")
        return workflow_id.strip(), run_id.strip()

    def _normalize_sse_event(self, *, raw_event: Mapping[str, Any], run_id: str) -> dict[str, Any]:
        return {
            **dict(raw_event),
            "run_id": run_id,
            "executor_id": raw_event.get("executor_id", self._executor_id),
        }

    def _append_lifecycle_event(
        self,
        *,
        run_id: str,
        event_type: str,
        workflow_id: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        merged_payload: dict[str, Any] = {
            "workflow_id": workflow_id,
            "executor_id": self._executor_id,
        }
        if payload:
            merged_payload.update(payload)
        self._run_event_use_case.execute(
            AppendRunEventInput(
                run_id=run_id,
                event_type=event_type,
                channel="lifecycle",
                payload=merged_payload,
            )
        )

    def _record_execution_event_sync(self, *, run_id: str, sse_event: Mapping[str, Any]) -> None:
        event_type = sse_event.get("type")
        if not event_type:
            return

        payload = dict(sse_event)
        payload.pop("type", None)
        payload.pop("channel", None)
        self._run_event_use_case.execute(
            AppendRunEventInput(
                run_id=run_id,
                event_type=str(event_type),
                channel="execution",
                payload=payload,
            )
        )

    def _record_execution_event_best_effort(
        self,
        *,
        run_id: str,
        sse_event: Mapping[str, Any],
        execution_event_sink: Callable[[str, Mapping[str, Any]], None] | None,
        record_execution_events: bool,
    ) -> None:
        if execution_event_sink is not None:
            try:
                execution_event_sink(run_id, sse_event)
            except Exception:
                return
            return

        if record_execution_events:
            try:
                self._record_execution_event_sync(run_id=run_id, sse_event=sse_event)
            except Exception:
                return

    def _validate_workflow_or_raise(self, *, workflow_id: str) -> None:
        workflow = self._workflow_repository.get_by_id(workflow_id)
        self._save_validator.validate_or_raise(workflow)

    def _validate_run_gate_or_raise(self, *, workflow_id: str, run_id: str) -> None:
        try:
            run = self._run_repository.get_by_id(run_id)
        except NotFoundError as exc:
            raise RunGateError(
                f"run_id not found: {exc.entity_id}",
                code="run_not_found",
                details={"run_id": run_id},
            ) from exc

        if run.workflow_id != workflow_id:
            raise RunGateError(
                "run_id does not belong to this workflow",
                code="run_wrong_workflow",
                details={"run_id": run_id, "workflow_id": workflow_id},
            )

        if run.status is not RunStatus.CREATED:
            raise RunGateError(
                f"run is not executable (status={run.status.value})",
                code="run_not_executable",
                details={"run_id": run_id, "status": run.status.value},
            )

    async def prepare(
        self,
        *,
        workflow_id: str,
        run_id: str,
        input_data: Any = None,
        correlation_id: str | None = None,
        original_decision_id: str | None = None,
    ) -> None:
        workflow_id, run_id = self._normalize_ids(workflow_id=workflow_id, run_id=run_id)

        # Hard gate: validate workflow executability before any side effects (fail-closed).
        self._validate_workflow_or_raise(workflow_id=workflow_id)
        # Fail-closed: ensure run exists before any state transitions.
        self._validate_run_gate_or_raise(workflow_id=workflow_id, run_id=run_id)

        # Gate must run before persisting any run events to keep rejection paths side-effect free.
        async def _after_gate() -> None:
            # Concurrency-safe claim (WFCL-040):
            # - Duplicate requests may pass the pre-gate status check concurrently.
            # - Claim the run atomically (CAS) after gate, before persisting any events.
            claimed = self._run_repository.update_status_if_current(
                run_id,
                current_status=RunStatus.CREATED,
                target_status=RunStatus.RUNNING,
            )
            if not claimed:
                logger.info(
                    "run_execution_duplicate_dropped",
                    extra={
                        "workflow_id": workflow_id,
                        "run_id": run_id,
                        "correlation_id": correlation_id,
                        "original_decision_id": original_decision_id,
                    },
                )
                raise RunGateError(
                    "duplicate execution dropped (run already claimed)",
                    code="duplicate_execution",
                    details={
                        "workflow_id": workflow_id,
                        "run_id": run_id,
                        "original_decision_id": original_decision_id,
                    },
                )
            self._append_lifecycle_event(
                run_id=run_id,
                event_type="workflow_start",
                workflow_id=workflow_id,
            )

        await self._kernel.gate_execute(
            workflow_id=workflow_id,
            input_data=input_data,
            correlation_id=correlation_id,
            original_decision_id=original_decision_id,
            after_gate=_after_gate,
        )

    async def stream_after_gate(
        self,
        *,
        workflow_id: str,
        run_id: str,
        input_data: Any = None,
        correlation_id: str | None = None,
        original_decision_id: str | None = None,
        execution_event_sink: Callable[[str, Mapping[str, Any]], None] | None = None,
        record_execution_events: bool = False,
    ) -> AsyncGenerator[dict[str, Any], None]:
        workflow_id, run_id = self._normalize_ids(workflow_id=workflow_id, run_id=run_id)

        terminal_persisted = False
        try:
            side_effect_node_id = _find_first_side_effect_node_id(
                workflow=self._workflow_repository.get_by_id(workflow_id)
            )
            if side_effect_node_id:
                pending = await run_confirmation_store.create_or_get_pending(
                    run_id=run_id,
                    workflow_id=workflow_id,
                    node_id=side_effect_node_id,
                )
                confirm_required = self._normalize_sse_event(
                    raw_event={
                        "type": "workflow_confirm_required",
                        "workflow_id": workflow_id,
                        "node_id": side_effect_node_id,
                        "confirm_id": pending.confirm_id,
                        "default_decision": "deny",
                    },
                    run_id=run_id,
                )
                validate_workflow_execution_sse_event(confirm_required)
                self._record_execution_event_best_effort(
                    run_id=run_id,
                    sse_event={**confirm_required, "channel": "execution"},
                    execution_event_sink=execution_event_sink,
                    record_execution_events=record_execution_events,
                )
                yield confirm_required

                try:
                    decision = await run_confirmation_store.wait_for_decision(
                        confirm_id=pending.confirm_id,
                        timeout_s=_CONFIRM_TIMEOUT_S,
                    )
                except TimeoutError:
                    decision = "deny"
                    deny_reason = "confirm_timeout"
                except asyncio.CancelledError:
                    decision = "deny"
                    deny_reason = "stream_cancelled"
                    self._append_lifecycle_event(
                        run_id=run_id,
                        event_type="workflow_error",
                        workflow_id=workflow_id,
                        payload={"error": deny_reason},
                    )
                    terminal_persisted = True
                    raise
                else:
                    deny_reason = "user_denied"

                confirmed_event = self._normalize_sse_event(
                    raw_event={
                        "type": "workflow_confirmed",
                        "workflow_id": workflow_id,
                        "node_id": side_effect_node_id,
                        "confirm_id": pending.confirm_id,
                        "decision": decision,
                    },
                    run_id=run_id,
                )
                validate_workflow_execution_sse_event(confirmed_event)
                self._record_execution_event_best_effort(
                    run_id=run_id,
                    sse_event={**confirmed_event, "channel": "execution"},
                    execution_event_sink=execution_event_sink,
                    record_execution_events=record_execution_events,
                )
                yield confirmed_event

                if decision != "allow":
                    denied = self._normalize_sse_event(
                        raw_event={
                            "type": "workflow_error",
                            "error": "side_effect_confirm_denied",
                            "reason": deny_reason,
                            "confirm_id": pending.confirm_id,
                        },
                        run_id=run_id,
                    )
                    validate_workflow_execution_sse_event(denied)
                    self._record_execution_event_best_effort(
                        run_id=run_id,
                        sse_event={**denied, "channel": "execution"},
                        execution_event_sink=execution_event_sink,
                        record_execution_events=record_execution_events,
                    )
                    self._append_lifecycle_event(
                        run_id=run_id,
                        event_type="workflow_error",
                        workflow_id=workflow_id,
                        payload={
                            "error": "side_effect_confirm_denied",
                            "reason": deny_reason,
                            "confirm_id": pending.confirm_id,
                        },
                    )
                    terminal_persisted = True
                    yield denied
                    return

            async for raw_event in self._kernel.stream_after_gate(
                workflow_id=workflow_id,
                input_data=input_data,
                correlation_id=correlation_id,
                original_decision_id=original_decision_id,
            ):
                event = self._normalize_sse_event(raw_event=raw_event, run_id=run_id)

                try:
                    validate_workflow_execution_sse_event(event)
                except ExecutionEventContractError:
                    invalid_type = event.get("type")
                    logger.warning(
                        "run_execution_event_contract_violation",
                        extra={
                            "workflow_id": workflow_id,
                            "run_id": run_id,
                            "invalid_type": str(invalid_type),
                        },
                    )
                    violation_event = self._normalize_sse_event(
                        raw_event={
                            "type": "workflow_error",
                            "error": "invalid_execution_event_type",
                            "invalid_type": invalid_type,
                        },
                        run_id=run_id,
                    )
                    self._record_execution_event_best_effort(
                        run_id=run_id,
                        sse_event={**violation_event, "channel": "execution"},
                        execution_event_sink=execution_event_sink,
                        record_execution_events=record_execution_events,
                    )
                    if not terminal_persisted:
                        self._append_lifecycle_event(
                            run_id=run_id,
                            event_type="workflow_error",
                            workflow_id=workflow_id,
                            payload={
                                "error": "invalid_execution_event_type",
                                "invalid_type": str(invalid_type),
                            },
                        )
                        logger.info(
                            "run_execution_terminal_persisted",
                            extra={
                                "workflow_id": workflow_id,
                                "run_id": run_id,
                                "event_type": "workflow_error",
                                "reason": "invalid_execution_event_type",
                            },
                        )
                        terminal_persisted = True
                    yield violation_event
                    return

                self._record_execution_event_best_effort(
                    run_id=run_id,
                    sse_event={**event, "channel": "execution"},
                    execution_event_sink=execution_event_sink,
                    record_execution_events=record_execution_events,
                )

                event_type = event.get("type", "")
                if not terminal_persisted and event_type in {"workflow_complete", "workflow_error"}:
                    self._append_lifecycle_event(
                        run_id=run_id,
                        event_type=event_type,
                        workflow_id=workflow_id,
                    )
                    logger.info(
                        "run_execution_terminal_persisted",
                        extra={
                            "workflow_id": workflow_id,
                            "run_id": run_id,
                            "event_type": event_type,
                        },
                    )
                    terminal_persisted = True
                yield event
        except asyncio.CancelledError:
            if not terminal_persisted:
                self._append_lifecycle_event(
                    run_id=run_id,
                    event_type="workflow_error",
                    workflow_id=workflow_id,
                    payload={"error": "client_disconnected"},
                )
                terminal_persisted = True
            raise
        except NotFoundError as exc:
            if terminal_persisted:
                return
            error_event = {
                "type": "workflow_error",
                "error": f"{exc.entity_type} not found: {exc.entity_id}",
            }
            event = self._normalize_sse_event(raw_event=error_event, run_id=run_id)
            self._record_execution_event_best_effort(
                run_id=run_id,
                sse_event={**event, "channel": "execution"},
                execution_event_sink=execution_event_sink,
                record_execution_events=record_execution_events,
            )
            self._append_lifecycle_event(
                run_id=run_id,
                event_type="workflow_error",
                workflow_id=workflow_id,
                payload={"error": error_event["error"]},
            )
            terminal_persisted = True
            yield event
        except Exception as exc:  # pragma: no cover - best-effort error reporting
            if terminal_persisted:
                return
            error_event = {
                "type": "workflow_error",
                "error": f"Workflow execution failed: {exc}",
            }
            event = self._normalize_sse_event(raw_event=error_event, run_id=run_id)
            self._record_execution_event_best_effort(
                run_id=run_id,
                sse_event={**event, "channel": "execution"},
                execution_event_sink=execution_event_sink,
                record_execution_events=record_execution_events,
            )
            self._append_lifecycle_event(
                run_id=run_id,
                event_type="workflow_error",
                workflow_id=workflow_id,
                payload={"error": "workflow execution failed"},
            )
            terminal_persisted = True
            yield event
        finally:
            if not terminal_persisted:
                # Defensive close: avoid leaving runs in RUNNING when kernel ends unexpectedly.
                try:
                    self._append_lifecycle_event(
                        run_id=run_id,
                        event_type="workflow_error",
                        workflow_id=workflow_id,
                        payload={"error": "missing_terminal_event"},
                    )
                except Exception:
                    pass

    async def execute_streaming(
        self,
        *,
        workflow_id: str,
        run_id: str,
        input_data: Any = None,
        correlation_id: str | None = None,
        original_decision_id: str | None = None,
        execution_event_sink: Callable[[str, Mapping[str, Any]], None] | None = None,
        record_execution_events: bool = False,
    ) -> AsyncGenerator[dict[str, Any], None]:
        await self.prepare(
            workflow_id=workflow_id,
            run_id=run_id,
            input_data=input_data,
            correlation_id=correlation_id,
            original_decision_id=original_decision_id,
        )
        async for event in self.stream_after_gate(
            workflow_id=workflow_id,
            run_id=run_id,
            input_data=input_data,
            correlation_id=correlation_id,
            original_decision_id=original_decision_id,
            execution_event_sink=execution_event_sink,
            record_execution_events=record_execution_events,
        ):
            yield event

    async def execute_with_results(
        self,
        *,
        workflow_id: str,
        run_id: str,
        input_data: Any = None,
        correlation_id: str | None = None,
        original_decision_id: str | None = None,
        execution_event_sink: Callable[[str, Mapping[str, Any]], None] | None = None,
        record_execution_events: bool = False,
    ) -> dict[str, Any]:
        await self.prepare(
            workflow_id=workflow_id,
            run_id=run_id,
            input_data=input_data,
            correlation_id=correlation_id,
            original_decision_id=original_decision_id,
        )
        events: list[dict[str, Any]] = []
        async for event in self.stream_after_gate(
            workflow_id=workflow_id,
            run_id=run_id,
            input_data=input_data,
            correlation_id=correlation_id,
            original_decision_id=original_decision_id,
            execution_event_sink=execution_event_sink,
            record_execution_events=record_execution_events,
        ):
            events.append(event)

        terminal_type = events[-1].get("type") if events else None
        try:
            run = self._run_repository.get_by_id(run_id.strip())
            run_status_value = run.status.value
            run_status_is_success = run.status is RunStatus.COMPLETED
        except Exception:
            run_status_value = "unknown"
            run_status_is_success = False

        return {
            "success": terminal_type == "workflow_complete" and run_status_is_success,
            "status": run_status_value,
            "workflow_id": workflow_id.strip() if isinstance(workflow_id, str) else workflow_id,
            "run_id": run_id.strip() if isinstance(run_id, str) else run_id,
            "executor_id": (events[-1].get("executor_id") if events else self._executor_id),
            "events": events,
        }
