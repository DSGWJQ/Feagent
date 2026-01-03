"""WorkflowEngine - 单一权威的 DAG 执行引擎（Domain）

目标（DDD-030）：
- 拓扑排序与节点执行语义只保留一个权威实现
- 缺少 executor 时不做 mock fallback，而是抛出明确 DomainError
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable
from typing import Any

from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.value_objects.node_type import NodeType

EventCallback = Callable[[str, dict[str, Any]], None]


def topological_sort_ids(
    *,
    node_ids: Iterable[str],
    edges: Iterable[tuple[str, str]],
) -> list[str]:
    """Kahn 拓扑排序（id 级别）"""

    in_degree = {node_id: 0 for node_id in node_ids}
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in in_degree}

    for source_id, target_id in edges:
        if source_id in adjacency and target_id in in_degree:
            adjacency[source_id].append(target_id)
            in_degree[target_id] += 1

    queue: deque[str] = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
    result: list[str] = []

    while queue:
        node_id = queue.popleft()
        result.append(node_id)

        for neighbor in adjacency[node_id]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(in_degree):
        raise DomainError("工作流包含环，无法执行")

    return result


class WorkflowEngine:
    def __init__(self, *, executor_registry: NodeExecutorRegistry | None = None) -> None:
        self._executor_registry = executor_registry

    def topological_sort(self, workflow: Workflow) -> list[Node]:
        node_map = {node.id: node for node in workflow.nodes}
        sorted_ids = topological_sort_ids(
            node_ids=node_map.keys(),
            edges=((e.source_node_id, e.target_node_id) for e in workflow.edges),
        )
        return [node_map[node_id] for node_id in sorted_ids]

    async def execute(
        self,
        *,
        workflow: Workflow,
        initial_input: Any = None,
        event_callback: EventCallback | None = None,
    ) -> tuple[Any, list[dict[str, Any]]]:
        sorted_nodes = self.topological_sort(workflow)
        node_outputs: dict[str, Any] = {}
        execution_log: list[dict[str, Any]] = []

        context = {"initial_input": initial_input}

        for node in sorted_nodes:
            if event_callback:
                event_callback(
                    "node_start",
                    {"node_id": node.id, "node_type": node.type.value},
                )

            inputs = _get_node_inputs(node_id=node.id, edges=workflow.edges, outputs=node_outputs)
            try:
                output = await self._execute_node(node=node, inputs=inputs, context=context)
            except Exception as exc:  # noqa: BLE001 - Domain boundary for execution errors
                if event_callback:
                    event_callback(
                        "node_error",
                        {
                            "node_id": node.id,
                            "node_type": node.type.value,
                            "error": str(exc),
                        },
                    )
                raise DomainError(
                    f"Node execution failed: node_id={node.id} node_type={node.type.value}"
                ) from exc

            node_outputs[node.id] = output
            execution_log.append(
                {"node_id": node.id, "node_type": node.type.value, "output": output}
            )

            if event_callback:
                event_callback(
                    "node_complete",
                    {"node_id": node.id, "node_type": node.type.value, "output": output},
                )

        end_node = next(
            (n for n in sorted_nodes if n.type in {NodeType.END, NodeType.OUTPUT}), None
        )
        final_result = node_outputs.get(end_node.id) if end_node else None
        return final_result, execution_log

    async def _execute_node(
        self, *, node: Node, inputs: dict[str, Any], context: dict[str, Any]
    ) -> Any:
        # Built-in semantics (not a mock fallback).
        if node.type in {NodeType.INPUT, NodeType.START}:
            return context.get("initial_input")

        if node.type in {NodeType.DEFAULT, NodeType.END, NodeType.OUTPUT}:
            return next(iter(inputs.values())) if inputs else None

        registry = self._executor_registry
        if registry is None:
            raise DomainError(f"Missing executor registry for node_type={node.type.value}")

        executor = registry.get(node.type.value)
        if executor is None:
            raise DomainError(f"Missing executor for node_type={node.type.value}")

        return await executor.execute(node, inputs, context)


def _get_node_inputs(*, node_id: str, edges: list[Any], outputs: dict[str, Any]) -> dict[str, Any]:
    inputs: dict[str, Any] = {}
    for edge in edges:
        if edge.target_node_id != node_id:
            continue
        inputs[edge.source_node_id] = outputs.get(edge.source_node_id)
    return inputs
