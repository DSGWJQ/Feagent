"""契约测试：Workflow execution SSE event contract（最小可执行合同）

目的：
- 固化 execution stream 的最小边界：只允许 node_*/workflow_* 事件类型
- 强制 execution event 必填字段：type/run_id/executor_id
- 防止 planning/tool_call/tool_result 语义混入执行流
"""

import pytest

from src.application.services.workflow_event_contract import (
    ExecutionEventContractError,
    is_execution_event_type,
    validate_workflow_execution_sse_event,
)


class TestWorkflowEventContract:
    def test_is_execution_event_type_allows_node_and_workflow_prefixes(self) -> None:
        assert is_execution_event_type("node_started") is True
        assert is_execution_event_type("node_complete") is True
        assert is_execution_event_type("workflow_complete") is True
        assert is_execution_event_type("workflow_error") is True

    def test_is_execution_event_type_rejects_reserved_and_unknown_types(self) -> None:
        assert is_execution_event_type("") is False
        assert is_execution_event_type("planning") is False
        assert is_execution_event_type("tool_call") is False
        assert is_execution_event_type("tool_result") is False
        assert is_execution_event_type("message") is False
        assert is_execution_event_type("chat_message") is False

    def test_validate_workflow_execution_sse_event_accepts_valid_event(self) -> None:
        validate_workflow_execution_sse_event(
            {
                "type": "node_started",
                "run_id": "run_123",
                "executor_id": "executor_1",
            }
        )

    def test_validate_workflow_execution_sse_event_requires_run_id(self) -> None:
        with pytest.raises(ExecutionEventContractError, match="run_id"):
            validate_workflow_execution_sse_event(
                {"type": "workflow_complete", "executor_id": "executor_1"}
            )

    def test_validate_workflow_execution_sse_event_requires_executor_id(self) -> None:
        with pytest.raises(ExecutionEventContractError, match="executor_id"):
            validate_workflow_execution_sse_event({"type": "workflow_complete", "run_id": "run_1"})

    def test_validate_workflow_execution_sse_event_rejects_invalid_type(self) -> None:
        with pytest.raises(ExecutionEventContractError, match="invalid execution event type"):
            validate_workflow_execution_sse_event(
                {"type": "planning", "run_id": "run_1", "executor_id": "executor_1"}
            )
