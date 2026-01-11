from __future__ import annotations

from src.infrastructure.lc_adapters.agents.task_executor_adapter import *  # noqa: F403


def create_langgraph_task_executor():
    """Public wrapper for tests to patch.

    Delegates to `src.lc.agents.langgraph_task_executor.create_langgraph_task_executor`.
    """
    from src.lc.agents.langgraph_task_executor import create_langgraph_task_executor

    return create_langgraph_task_executor()
