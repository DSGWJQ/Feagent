from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.domain.exceptions import DomainError
from src.infrastructure.lc_adapters.workflow.langgraph_workflow_executor_adapter import (
    LangGraphWorkflowExecutorAdapter,
)


@pytest.mark.asyncio
async def test_langgraph_workflow_executor_adapter_execute_is_feature_disabled():
    adapter = LangGraphWorkflowExecutorAdapter(
        workflow_repository=Mock(),
        executor_registry=Mock(),
    )
    with pytest.raises(DomainError, match=r"feature_disabled"):
        await adapter.execute(workflow_id="wf_1", input_data={})


@pytest.mark.asyncio
async def test_langgraph_workflow_executor_adapter_execute_streaming_is_feature_disabled():
    adapter = LangGraphWorkflowExecutorAdapter(
        workflow_repository=Mock(),
        executor_registry=Mock(),
    )
    with pytest.raises(DomainError, match=r"feature_disabled"):
        async for _ in adapter.execute_streaming(workflow_id="wf_1", input_data={}):
            pass
