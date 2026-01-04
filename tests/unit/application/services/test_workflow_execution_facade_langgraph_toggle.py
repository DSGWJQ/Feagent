from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import Mock

import pytest

from src.application.services.workflow_execution_facade import WorkflowExecutionFacade
from src.application.use_cases.execute_workflow import WORKFLOW_EXECUTION_KERNEL_ID
from src.config import settings


@pytest.mark.asyncio
async def test_invariant_8_facade_uses_langgraph_adapter_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INV-8: enable_langgraph_workflow_executor=True routes to LangGraph adapter."""

    monkeypatch.setattr(settings, "enable_langgraph_workflow_executor", True)

    created: list[tuple[object, object]] = []

    class FakeLangGraphAdapter:
        def __init__(self, *, workflow_repository, executor_registry) -> None:
            created.append((workflow_repository, executor_registry))

        async def execute(self, *, workflow_id: str, input_data) -> dict:
            return {"ok": True, "workflow_id": workflow_id, "input_data": input_data}

    import src.infrastructure.lc_adapters.workflow.langgraph_workflow_executor_adapter as lg_module

    monkeypatch.setattr(lg_module, "LangGraphWorkflowExecutorAdapter", FakeLangGraphAdapter)

    workflow_repository = Mock()
    executor_registry = Mock()

    facade = WorkflowExecutionFacade(
        workflow_repository=workflow_repository,
        executor_registry=executor_registry,
    )
    result = await facade.execute(workflow_id="wf_1", input_data={"k": "v"})

    assert created == [(workflow_repository, executor_registry)]
    assert result["ok"] is True
    assert result["workflow_id"] == "wf_1"
    assert result["input_data"] == {"k": "v"}
    assert result["executor_id"] == WORKFLOW_EXECUTION_KERNEL_ID


@pytest.mark.asyncio
async def test_invariant_8_facade_streaming_preserves_or_default_executor_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INV-8: streaming uses adapter and always emits executor_id."""

    monkeypatch.setattr(settings, "enable_langgraph_workflow_executor", True)

    class FakeLangGraphAdapter:
        def __init__(self, *, workflow_repository, executor_registry) -> None:
            pass

        async def execute_streaming(
            self, *, workflow_id: str, input_data
        ) -> AsyncGenerator[dict, None]:
            yield {"type": "node_start", "metadata": {"workflow_id": workflow_id}}
            yield {"type": "workflow_complete", "executor_id": "langgraph"}

    import src.infrastructure.lc_adapters.workflow.langgraph_workflow_executor_adapter as lg_module

    monkeypatch.setattr(lg_module, "LangGraphWorkflowExecutorAdapter", FakeLangGraphAdapter)

    facade = WorkflowExecutionFacade(workflow_repository=Mock(), executor_registry=Mock())
    events = [e async for e in facade.execute_streaming(workflow_id="wf_1", input_data=None)]

    assert events[0]["type"] == "node_start"
    assert events[0]["executor_id"] == WORKFLOW_EXECUTION_KERNEL_ID
    assert events[1]["type"] == "workflow_complete"
    assert events[1]["executor_id"] == "langgraph"
