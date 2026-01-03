"""LangGraph WorkflowExecutor - 工作流级 LangGraph 编排（可回滚）

目标（WF-040）：
- workflow 执行路径可由 LangGraph 驱动（adapter 落地），但对外事件契约保持一致
- 支持紧急回滚：由上层根据 feature flag 切换到 legacy DAG engine

注意：
- NodeExecutor 是 async 接口，因此这里使用 LangGraph 的 async 执行能力（ainvoke）。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.services.workflow_engine import topological_sort_ids
from src.domain.value_objects.node_type import NodeType

EventCallback = Callable[[str, dict[str, Any]], None]


class WorkflowExecutorState(TypedDict):
    results: dict[str, Any]
    execution_log: list[dict[str, Any]]
    initial_input: Any


def _get_node_inputs(
    *, node_id: str, workflow: Workflow, outputs: dict[str, Any]
) -> dict[str, Any]:
    inputs: dict[str, Any] = {}
    for edge in workflow.edges:
        if edge.target_node_id != node_id:
            continue
        inputs[edge.source_node_id] = outputs.get(edge.source_node_id)
    return inputs


async def _execute_workflow_node(
    *,
    node_id: str,
    workflow: Workflow,
    node_map: dict[str, Any],
    state: WorkflowExecutorState,
    executor_registry: NodeExecutorRegistry | None,
    event_callback: EventCallback | None,
) -> dict[str, Any]:
    node = node_map.get(node_id)
    if node is None:
        raise DomainError(f"workflow node not found: node_id={node_id}")

    if event_callback:
        event_callback("node_start", {"node_id": node.id, "node_type": node.type.value})

    results = dict(state.get("results", {}))
    execution_log = list(state.get("execution_log", []))
    inputs = _get_node_inputs(node_id=node.id, workflow=workflow, outputs=results)
    context = {"initial_input": state.get("initial_input")}

    try:
        if node.type in {NodeType.INPUT, NodeType.START}:
            output = context.get("initial_input")
        elif node.type in {NodeType.DEFAULT, NodeType.END, NodeType.OUTPUT}:
            output = next(iter(inputs.values())) if inputs else None
        else:
            if executor_registry is None:
                raise DomainError(f"Missing executor registry for node_type={node.type.value}")
            executor = executor_registry.get(node.type.value)
            if executor is None:
                raise DomainError(f"Missing executor for node_type={node.type.value}")
            output = await executor.execute(node, inputs, context)
    except Exception as exc:  # noqa: BLE001 - Domain boundary for execution errors
        if event_callback:
            event_callback(
                "node_error",
                {"node_id": node.id, "node_type": node.type.value, "error": str(exc)},
            )
        raise DomainError(
            f"Node execution failed: node_id={node.id} node_type={node.type.value}"
        ) from exc

    results[node.id] = output
    execution_log.append({"node_id": node.id, "node_type": node.type.value, "output": output})

    if event_callback:
        event_callback(
            "node_complete",
            {"node_id": node.id, "node_type": node.type.value, "output": output},
        )

    return {"results": results, "execution_log": execution_log}


def create_langgraph_workflow_executor(
    workflow: Workflow,
    executor_registry: NodeExecutorRegistry | None = None,
    *,
    event_callback: EventCallback | None = None,
):
    node_map = {node.id: node for node in workflow.nodes}
    sorted_ids = topological_sort_ids(
        node_ids=[node.id for node in workflow.nodes],
        edges=[(e.source_node_id, e.target_node_id) for e in workflow.edges],
    )

    workflow_graph = StateGraph(WorkflowExecutorState)

    for node_id in sorted_ids:

        async def _node_fn(
            state: WorkflowExecutorState,
            *,
            _node_id: str = node_id,
        ) -> dict[str, Any]:
            return await _execute_workflow_node(
                node_id=_node_id,
                workflow=workflow,
                node_map=node_map,
                state=state,
                executor_registry=executor_registry,
                event_callback=event_callback,
            )

        workflow_graph.add_node(node_id, _node_fn)

    if not sorted_ids:
        workflow_graph.set_entry_point(END)
    else:
        workflow_graph.set_entry_point(sorted_ids[0])
        for left, right in zip(sorted_ids, sorted_ids[1:], strict=False):
            workflow_graph.add_edge(left, right)
        workflow_graph.add_edge(sorted_ids[-1], END)

    return workflow_graph.compile()


async def execute_workflow_async(
    workflow: Workflow,
    *,
    initial_input: Any = None,
    executor_registry: NodeExecutorRegistry | None = None,
    event_callback: EventCallback | None = None,
) -> tuple[Any, list[dict[str, Any]]]:
    app = create_langgraph_workflow_executor(
        workflow, executor_registry, event_callback=event_callback
    )

    initial_state: WorkflowExecutorState = {
        "results": {},
        "execution_log": [],
        "initial_input": initial_input,
    }

    final_state = await app.ainvoke(initial_state)
    results = final_state.get("results", {})
    execution_log = final_state.get("execution_log", [])

    end_node = next((n for n in workflow.nodes if n.type in {NodeType.END, NodeType.OUTPUT}), None)
    final_result = results.get(end_node.id) if end_node else None
    return final_result, execution_log
