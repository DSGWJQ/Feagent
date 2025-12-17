"""ReAct Orchestrator 端口（领域层依赖）

该端口用于隔离领域层与具体 ReAct / LangChain 实现，避免 Domain 直接依赖基础设施细节。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from src.domain.entities.workflow import Workflow


@dataclass
class ReActEvent:
    """ReAct 事件（由编排器发出）"""

    event_type: str
    timestamp: datetime = field(default_factory=datetime.now)
    data: dict[str, Any] = field(default_factory=dict)


class ReActLoopState(Protocol):
    """ReAct 循环状态（领域层最小视图）"""

    workflow_id: str
    workflow_name: str
    iteration_count: int
    loop_status: str
    messages: list[Any]
    executed_actions: list[Any]
    executed_nodes: dict[str, Any]


@runtime_checkable
class ReActOrchestratorPort(Protocol):
    """ReAct 编排器端口。"""

    def on_event(self, callback: Callable[[ReActEvent], None]) -> None:
        """注册事件处理器。"""
        ...

    def run(self, workflow: Workflow) -> ReActLoopState:
        """运行完整 ReAct 循环并返回最终状态。"""
        ...

    def get_final_state(self) -> ReActLoopState | None:
        """获取最近一次运行的最终状态。"""
        ...
