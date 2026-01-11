"""Legacy-compatible LangGraph-style workflow executor (shim).

Tests and older callers expect the `src.lc.workflow.langgraph_workflow_executor` API.
The production workflow execution path is implemented elsewhere (WorkflowEngine / adapters).

This module provides a minimal, deterministic implementation that:
- accepts a `Workflow` entity (nodes + edges)
- executes nodes in topological order
- records results and preserves message history
- never raises on node execution failure (fail-soft, marks status=failed)
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage

from src.domain.entities.workflow import Workflow
from src.domain.services.workflow_engine import topological_sort_ids


class WorkflowExecutorState(TypedDict, total=False):
    messages: list[Any]
    results: dict[str, Any]
    current_node: str | None
    status: str
    errors: list[dict[str, Any]]


def get_node_executor(node_type: Any):  # pragma: no cover - patched by tests
    """Return a node executor for the given node type.

    This is intentionally a thin hook for unit tests to patch.
    Production code should use NodeExecutorRegistry-based execution.
    """
    raise RuntimeError("get_node_executor is not configured (tests should patch this)")


def _call_executor(
    executor: Any, *, node: Any, inputs: dict[str, Any], context: dict[str, Any]
) -> Any:
    """Call executor.execute with a tolerant signature.

    Tests patch executors with differing call signatures (2 args vs 3 args).
    We attempt (node, inputs, context) first and fall back to fewer args.
    """
    if not hasattr(executor, "execute"):
        raise TypeError("executor must provide .execute(...)")

    try:
        return executor.execute(node, inputs, context)
    except TypeError:
        try:
            return executor.execute(node, inputs)
        except TypeError:
            return executor.execute(node, node.config if hasattr(node, "config") else {})


def _build_incoming_edges(workflow: Workflow) -> dict[str, list[str]]:
    incoming: dict[str, list[str]] = defaultdict(list)
    for edge in workflow.edges:
        incoming[edge.target_node_id].append(edge.source_node_id)
    return dict(incoming)


@dataclass(frozen=True)
class _ExecutorGraph:
    workflow: Workflow
    on_event: Callable[[str, dict[str, Any]], None] | None = None

    def invoke(self, state: WorkflowExecutorState) -> WorkflowExecutorState:
        messages = list(state.get("messages") or [])
        results = dict(state.get("results") or {})
        errors: list[dict[str, Any]] = list(state.get("errors") or [])

        state_out: WorkflowExecutorState = {
            "messages": messages,
            "results": results,
            "current_node": None,
            "status": "running",
            "errors": errors,
        }

        node_map = {node.id: node for node in self.workflow.nodes}
        sorted_ids = topological_sort_ids(
            node_ids=node_map.keys(),
            edges=((e.source_node_id, e.target_node_id) for e in self.workflow.edges),
        )
        incoming = _build_incoming_edges(self.workflow)

        for node_id in sorted_ids:
            node = node_map[node_id]
            state_out["current_node"] = node_id
            if self.on_event:
                self.on_event("node_start", {"node_id": node_id, "node_type": node.type.value})
            messages.append(AIMessage(content=f"节点开始: {node.name}"))

            inputs = {src_id: results.get(src_id) for src_id in incoming.get(node_id, [])}
            context = {"workflow_id": self.workflow.id}

            try:
                executor = get_node_executor(node.type)
                output = _call_executor(executor, node=node, inputs=inputs, context=context)
                results[node_id] = output
                if self.on_event:
                    self.on_event(
                        "node_complete",
                        {"node_id": node_id, "node_type": node.type.value, "output": output},
                    )
                messages.append(AIMessage(content=f"节点完成: {node.name}"))
            except Exception as exc:  # noqa: BLE001 - fail-soft for legacy behavior
                errors.append({"node_id": node_id, "error": str(exc)})
                if self.on_event:
                    self.on_event(
                        "node_error",
                        {"node_id": node_id, "node_type": node.type.value, "error": str(exc)},
                    )
                messages.append(AIMessage(content=f"节点错误: {node.name}: {exc}"))

        state_out["current_node"] = None
        state_out["status"] = "failed" if errors else "completed"
        return state_out


def create_langgraph_workflow_executor(
    workflow: Workflow,
    *,
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
) -> _ExecutorGraph:
    return _ExecutorGraph(workflow=workflow, on_event=on_event)


def execute_workflow(workflow: Workflow) -> WorkflowExecutorState:
    executor = create_langgraph_workflow_executor(workflow)
    initial_state: WorkflowExecutorState = {
        "messages": [HumanMessage(content="execute_workflow")],
        "results": {},
        "current_node": None,
        "status": "running",
    }
    return executor.invoke(initial_state)


__all__ = [
    "WorkflowExecutorState",
    "create_langgraph_workflow_executor",
    "execute_workflow",
    "get_node_executor",
]
