"""测试：WorkflowRunExecutionEntry 并发去重（WFCL-040）

目的：
- 当多个请求并发通过 pre-gate（run.status == CREATED）时，必须只有一个能“claim”该 run
- 重复请求必须 fail-closed：不追加 workflow_start，不产生 RunEvents 污染
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.application.services.workflow_run_execution_entry import WorkflowRunExecutionEntry
from src.domain.exceptions import RunGateError
from src.domain.value_objects.run_status import RunStatus


class _Run:
    def __init__(self, *, workflow_id: str, status: RunStatus) -> None:
        self.workflow_id = workflow_id
        self.status = status


class _Kernel:
    async def gate_execute(
        self,
        *,
        workflow_id: str,
        input_data=None,
        correlation_id: str | None = None,
        original_decision_id: str | None = None,
        after_gate=None,
    ) -> None:
        if after_gate is not None:
            await after_gate()


class TestWorkflowRunExecutionEntryDedup:
    @pytest.mark.asyncio
    async def test_prepare_rejects_duplicate_claim_and_does_not_append_workflow_start(self) -> None:
        workflow_repo = MagicMock()
        workflow_repo.get_by_id.return_value = object()

        save_validator = MagicMock()
        save_validator.validate_or_raise.return_value = None

        run_repo = MagicMock()
        run_repo.get_by_id.return_value = _Run(workflow_id="wf_1", status=RunStatus.CREATED)
        run_repo.update_status_if_current.return_value = False

        run_event_use_case = MagicMock()

        entry = WorkflowRunExecutionEntry(
            workflow_repository=workflow_repo,
            run_repository=run_repo,
            save_validator=save_validator,
            run_event_use_case=run_event_use_case,
            kernel=_Kernel(),
            executor_id="executor_test",
        )

        with pytest.raises(RunGateError) as exc:
            await entry.prepare(
                workflow_id="wf_1",
                run_id="run_1",
                correlation_id="run_1",
                original_decision_id="dec_1",
            )

        assert exc.value.code == "duplicate_execution"
        run_event_use_case.execute.assert_not_called()
