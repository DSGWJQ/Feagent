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
import time
from collections.abc import AsyncGenerator, Callable, Mapping
from typing import Any

from src.application.services.run_confirmation_store import run_confirmation_store
from src.application.services.workflow_event_contract import (
    ExecutionEventContractError,
    validate_workflow_execution_sse_event,
)
from src.application.use_cases.append_run_event import AppendRunEventInput, AppendRunEventUseCase
from src.config import settings
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

_REACT_MAX_ATTEMPTS = 6
_REACT_MAX_CONSECUTIVE_FAILURES = 3
_REACT_MAX_SECONDS = 600.0
_REACT_MAX_LLM_CALLS = 20


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

    def _record_execution_event(
        self,
        *,
        run_id: str,
        sse_event: Mapping[str, Any],
        execution_event_sink: Callable[[str, Mapping[str, Any]], None] | None = None,
        record_execution_events: bool = False,
    ) -> None:
        """统一的事件记录入口 - 根据 E2E 模式选择策略

        在 deterministic E2E 模式下，强制使用同步落库以保证测试稳定性；
        在其他模式下，使用 best-effort 异步策略以保证生产性能。

        Args:
            run_id: Run ID
            sse_event: SSE 事件字典
            execution_event_sink: 可选的外部事件接收器（仅在非 deterministic 模式使用）
            record_execution_events: 是否记录事件（仅在非 deterministic 模式有效）
        """
        if settings.e2e_test_mode == "deterministic":
            # deterministic 模式：强制同步落库，保证测试稳定
            self._record_execution_event_sync(run_id=run_id, sse_event=sse_event)
        else:
            # 生产/混合模式：保持原有 best-effort 异步策略
            self._record_execution_event_best_effort(
                run_id=run_id,
                sse_event=sse_event,
                execution_event_sink=execution_event_sink,
                record_execution_events=record_execution_events,
            )

    def _validate_workflow_or_raise(self, *, workflow_id: str) -> None:
        workflow = self._workflow_repository.get_by_id(workflow_id)
        # Execution gate is stricter than save: missing END must be rejected even for drafts.
        self._save_validator.validate_for_execution_or_raise(workflow)

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
                self._record_execution_event(
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
                self._record_execution_event(
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
                    self._record_execution_event(
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

            started_at = time.monotonic()
            react_started = False
            attempt = 1
            consecutive_failures = 0
            llm_calls = 0
            patches: list[dict[str, Any]] = []

            def _should_stop(
                *, attempt: int, consecutive_failures: int, llm_calls: int
            ) -> str | None:
                if attempt >= _REACT_MAX_ATTEMPTS:
                    return "max_attempts"
                if consecutive_failures >= _REACT_MAX_CONSECUTIVE_FAILURES:
                    return "consecutive_failures"
                if llm_calls >= _REACT_MAX_LLM_CALLS:
                    return "max_llm_calls"
                if (time.monotonic() - started_at) >= _REACT_MAX_SECONDS:
                    return "max_elapsed"
                return None

            def _emit_execution_event(event: dict[str, Any]) -> None:
                validate_workflow_execution_sse_event(event)
                self._record_execution_event(
                    run_id=run_id,
                    sse_event={**event, "channel": "execution"},
                    execution_event_sink=execution_event_sink,
                    record_execution_events=record_execution_events,
                )

            def _build_termination_report(
                *,
                stop_reason: str,
                stop_condition: str,
                last_error: Mapping[str, Any] | None,
            ) -> dict[str, Any]:
                elapsed_ms = int((time.monotonic() - started_at) * 1000)
                last_error_payload: dict[str, Any] = {}
                if isinstance(last_error, Mapping):
                    for key in (
                        "type",
                        "node_id",
                        "node_type",
                        "error",
                        "error_type",
                        "error_level",
                        "retryable",
                        "hint",
                        "message",
                        "attempt",
                    ):
                        value = last_error.get(key)
                        if value is not None:
                            last_error_payload[key] = value

                return {
                    "type": "workflow_termination_report",
                    "workflow_id": workflow_id,
                    "patch_scope": "config-only",
                    "stop_reason": stop_reason,
                    "stop_condition": stop_condition,
                    "attempts_total": attempt,
                    "consecutive_failures": consecutive_failures,
                    "llm_calls": llm_calls,
                    "elapsed_ms": elapsed_ms,
                    "last_error": last_error_payload,
                    "patches": list(patches),
                }

            while True:
                last_node_error: dict[str, Any] | None = None
                terminal_error: dict[str, Any] | None = None

                async for raw_event in self._kernel.stream_after_gate(
                    workflow_id=workflow_id,
                    input_data=input_data,
                    correlation_id=correlation_id,
                    original_decision_id=original_decision_id,
                ):
                    event = self._normalize_sse_event(raw_event=raw_event, run_id=run_id)
                    event.setdefault("attempt", attempt)

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
                                "attempt": attempt,
                            },
                            run_id=run_id,
                        )
                        _emit_execution_event(violation_event)
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

                    event_type = event.get("type", "")
                    if event_type == "node_error":
                        last_node_error = event

                    if event_type == "workflow_complete":
                        self._record_execution_event(
                            run_id=run_id,
                            sse_event={**event, "channel": "execution"},
                            execution_event_sink=execution_event_sink,
                            record_execution_events=record_execution_events,
                        )
                        if not terminal_persisted:
                            self._append_lifecycle_event(
                                run_id=run_id,
                                event_type="workflow_complete",
                                workflow_id=workflow_id,
                            )
                            logger.info(
                                "run_execution_terminal_persisted",
                                extra={
                                    "workflow_id": workflow_id,
                                    "run_id": run_id,
                                    "event_type": "workflow_complete",
                                },
                            )
                            terminal_persisted = True
                        yield event
                        return

                    if event_type == "workflow_error":
                        terminal_error = event
                        break

                    self._record_execution_event(
                        run_id=run_id,
                        sse_event={**event, "channel": "execution"},
                        execution_event_sink=execution_event_sink,
                        record_execution_events=record_execution_events,
                    )
                    yield event

                if terminal_error is None:
                    # Defensive close: kernel ended without terminal event.
                    missing_terminal = self._normalize_sse_event(
                        raw_event={
                            "type": "workflow_error",
                            "error": "missing_terminal_event",
                            "attempt": attempt,
                        },
                        run_id=run_id,
                    )
                    _emit_execution_event(missing_terminal)
                    if not terminal_persisted:
                        self._append_lifecycle_event(
                            run_id=run_id,
                            event_type="workflow_error",
                            workflow_id=workflow_id,
                            payload={"error": "missing_terminal_event"},
                        )
                        terminal_persisted = True
                    yield missing_terminal
                    return

                # Attempt failed. Enter ReAct-style repair loop (config-only).
                consecutive_failures += 1
                last_error = last_node_error or terminal_error

                if not react_started:
                    react_started = True
                    react_started_event = self._normalize_sse_event(
                        raw_event={
                            "type": "workflow_react_loop_started",
                            "workflow_id": workflow_id,
                            "patch_scope": "config-only",
                            "max_attempts": _REACT_MAX_ATTEMPTS,
                            "max_consecutive_failures": _REACT_MAX_CONSECUTIVE_FAILURES,
                            "max_seconds": _REACT_MAX_SECONDS,
                            "max_llm_calls": _REACT_MAX_LLM_CALLS,
                            "attempt": attempt,
                        },
                        run_id=run_id,
                    )
                    _emit_execution_event(react_started_event)
                    yield react_started_event

                attempt_failed_event = self._normalize_sse_event(
                    raw_event={
                        "type": "workflow_attempt_failed",
                        "workflow_id": workflow_id,
                        "attempt": attempt,
                        "error": terminal_error.get("error"),
                        "error_type": last_error.get("error_type"),
                        "retryable": last_error.get("retryable"),
                        "node_id": last_error.get("node_id"),
                    },
                    run_id=run_id,
                )
                _emit_execution_event(attempt_failed_event)
                yield attempt_failed_event

                stop_reason = _should_stop(
                    attempt=attempt,
                    consecutive_failures=consecutive_failures,
                    llm_calls=llm_calls,
                )
                if stop_reason is not None:
                    report_event = self._normalize_sse_event(
                        raw_event=_build_termination_report(
                            stop_reason=stop_reason,
                            stop_condition=stop_reason,
                            last_error=last_error,
                        ),
                        run_id=run_id,
                    )
                    _emit_execution_event(report_event)
                    yield report_event

                    if not terminal_persisted:
                        self._append_lifecycle_event(
                            run_id=run_id,
                            event_type="workflow_error",
                            workflow_id=workflow_id,
                            payload={"error": "react_stop", "reason": stop_reason},
                        )
                        terminal_persisted = True

                    final_error = terminal_error
                    final_error.setdefault("attempt", attempt)
                    _emit_execution_event(final_error)
                    yield final_error
                    return

                patch_applied, patch_info = self._apply_react_config_only_patch(
                    workflow_id=workflow_id,
                    error_event=last_error,
                )
                if not patch_applied:
                    report_event = self._normalize_sse_event(
                        raw_event=_build_termination_report(
                            stop_reason="unrepairable_error",
                            stop_condition="no_applicable_patch",
                            last_error=last_error,
                        ),
                        run_id=run_id,
                    )
                    _emit_execution_event(report_event)
                    yield report_event

                    final_error = terminal_error
                    _emit_execution_event(final_error)
                    if not terminal_persisted:
                        self._append_lifecycle_event(
                            run_id=run_id,
                            event_type="workflow_error",
                            workflow_id=workflow_id,
                            payload={"error": "react_unrepairable"},
                        )
                        terminal_persisted = True
                    yield final_error
                    return

                patches.append({**patch_info, "attempt": attempt})
                patch_event = self._normalize_sse_event(
                    raw_event={
                        "type": "workflow_react_patch_applied",
                        "workflow_id": workflow_id,
                        "attempt": attempt,
                        "patch": patch_info,
                        "patch_scope": "config-only",
                    },
                    run_id=run_id,
                )
                _emit_execution_event(patch_event)
                yield patch_event

                attempt += 1
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
            self._record_execution_event(
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
            self._record_execution_event(
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

    def _apply_react_config_only_patch(
        self,
        *,
        workflow_id: str,
        error_event: Mapping[str, Any],
    ) -> tuple[bool, dict[str, Any]]:
        """Best-effort config-only patching for PRD-040.

        Constraints:
        - Must not add/remove nodes or edges (config-only).
        - Must fail-closed when uncertain.
        """
        node_id = error_event.get("node_id")
        if not isinstance(node_id, str) or not node_id.strip():
            return False, {"reason": "missing_node_id"}

        error_type = error_event.get("error_type")
        if not isinstance(error_type, str):
            error_type = ""
        error_type = error_type.strip()

        workflow = self._workflow_repository.get_by_id(workflow_id)
        node_ids_before = [n.id for n in getattr(workflow, "nodes", []) or []]
        edge_ids_before = [e.id for e in getattr(workflow, "edges", []) or []]

        node = next((n for n in workflow.nodes if n.id == node_id), None)
        if node is None:
            return False, {"reason": "node_not_found", "node_id": node_id}

        if not isinstance(node.config, dict):
            node_config: dict[str, Any] = {}
        else:
            node_config = dict(node.config)

        patch: dict[str, Any] = {"node_id": node_id, "error_type": error_type, "changes": {}}

        if error_type == "timeout" or bool(error_event.get("retryable")):
            before = node_config.get("timeout")
            current = float(before) if isinstance(before, int | float) else 30.0
            target = current * 2.0
            if target < 10.0:
                target = 10.0
            if target > 300.0:
                target = 300.0
            node_config["timeout"] = target
            patch["changes"]["timeout"] = {"from": before, "to": target}
        elif error_type == "tool_not_found":
            if getattr(node, "type", None) is not NodeType.TOOL:
                return False, {"reason": "tool_not_found_non_tool_node", "node_id": node_id}
            repository = getattr(self._save_validator, "tool_repository", None)
            if repository is None:
                return False, {"reason": "tool_repository_unavailable"}
            tools = []
            if hasattr(repository, "find_published"):
                tools = list(repository.find_published())  # type: ignore[no-untyped-call]
            elif hasattr(repository, "find_all"):
                tools = list(repository.find_all())  # type: ignore[no-untyped-call]
            if not tools:
                return False, {"reason": "no_fallback_tools"}

            from src.domain.value_objects.tool_status import ToolStatus

            candidates = [t for t in tools if getattr(t, "status", None) != ToolStatus.DEPRECATED]
            if not candidates:
                return False, {"reason": "no_non_deprecated_tools"}

            before = node_config.get("tool_id") or node_config.get("toolId")
            fallback = next(
                (t for t in candidates if getattr(t, "id", None) != before), candidates[0]
            )
            node_config["tool_id"] = fallback.id
            node_config.pop("toolId", None)
            patch["changes"]["tool_id"] = {"from": before, "to": fallback.id}
        else:
            return False, {"reason": "unsupported_error_type", "error_type": error_type}

        node.update_config(node_config)

        # Defensive: verify config-only (no node/edge topology change).
        node_ids_after = [n.id for n in getattr(workflow, "nodes", []) or []]
        edge_ids_after = [e.id for e in getattr(workflow, "edges", []) or []]
        if node_ids_after != node_ids_before or edge_ids_after != edge_ids_before:
            return False, {"reason": "patch_scope_violation"}

        # Fail-closed: patched workflow must still be executable.
        self._save_validator.validate_for_execution_or_raise(workflow)
        self._workflow_repository.save(workflow)
        return True, patch

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
