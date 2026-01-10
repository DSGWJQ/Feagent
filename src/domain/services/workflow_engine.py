"""WorkflowEngine - 单一权威的 DAG 执行引擎（Domain）

目标（DDD-030）：
- 拓扑排序与节点执行语义只保留一个权威实现
- 缺少 executor 时不做 mock fallback，而是抛出明确 DomainError
"""

from __future__ import annotations

import logging
import re
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import replace
from typing import Any

from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.services.expression_evaluator import ExpressionEvaluator
from src.domain.value_objects.node_type import NodeType

EventCallback = Callable[[str, dict[str, Any]], None]

logger = logging.getLogger(__name__)


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
        incoming_edges = _build_incoming_edges(workflow)
        # Edge conditions in repo definitions and UI commonly use helper functions like `len(...)`.
        # "advanced" still enforces AST-based safety and a strict function allowlist.
        evaluator = ExpressionEvaluator(mode="advanced")

        for node in sorted_nodes:
            if node.type not in {NodeType.INPUT, NodeType.START}:
                if not _should_execute_node(
                    node_id=node.id,
                    incoming_edges=incoming_edges.get(node.id, []),
                    outputs=node_outputs,
                    evaluator=evaluator,
                    context=context,
                ):
                    if event_callback:
                        event_callback(
                            "node_skipped",
                            {
                                "node_id": node.id,
                                "node_type": node.type.value,
                                "reason": "incoming_edge_conditions_not_met",
                            },
                        )
                    continue

            if event_callback:
                event_callback(
                    "node_start",
                    {"node_id": node.id, "node_type": node.type.value},
                )

            inputs = _get_node_inputs(
                node_id=node.id,
                incoming_edges=incoming_edges.get(node.id, []),
                outputs=node_outputs,
                evaluator=evaluator,
                context=context,
            )
            try:
                rendered_node = replace(
                    node,
                    config=_render_config_templates(
                        node.config,
                        inputs=inputs,
                        context=context,
                        logger_extra={
                            "node_id": node.id,
                            "node_type": node.type.value,
                        },
                    ),
                )
                output = await self._execute_node(
                    node=rendered_node, inputs=inputs, context=context
                )
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


def _build_incoming_edges(workflow: Workflow) -> dict[str, list[Any]]:
    incoming: dict[str, list[Any]] = {}
    for edge in workflow.edges:
        incoming.setdefault(edge.target_node_id, []).append(edge)
    return incoming


def _should_execute_node(
    *,
    node_id: str,
    incoming_edges: list[Any],
    outputs: dict[str, Any],
    evaluator: ExpressionEvaluator,
    context: dict[str, Any],
) -> bool:
    # No incoming edges: treat as a root node (START/INPUT already handled upstream).
    if not incoming_edges:
        return True

    for edge in incoming_edges:
        source_id = getattr(edge, "source_node_id", None)
        if not isinstance(source_id, str) or source_id not in outputs:
            continue

        condition = getattr(edge, "condition", None)
        if condition is None or (isinstance(condition, str) and condition.strip() == ""):
            return True

        if not isinstance(condition, str):
            continue

        if _evaluate_edge_condition(
            condition=condition,
            source_output=outputs.get(source_id),
            evaluator=evaluator,
            context=context,
        ):
            return True

    return False


def _get_node_inputs(
    *,
    node_id: str,
    incoming_edges: list[Any],
    outputs: dict[str, Any],
    evaluator: ExpressionEvaluator,
    context: dict[str, Any],
) -> dict[str, Any]:
    inputs: dict[str, Any] = {}
    for edge in incoming_edges:
        source_id = getattr(edge, "source_node_id", None)
        if not isinstance(source_id, str) or source_id not in outputs:
            continue

        condition = getattr(edge, "condition", None)
        if condition is None or (isinstance(condition, str) and condition.strip() == ""):
            inputs[source_id] = outputs.get(source_id)
            continue

        if not isinstance(condition, str):
            continue

        if _evaluate_edge_condition(
            condition=condition,
            source_output=outputs.get(source_id),
            evaluator=evaluator,
            context=context,
        ):
            inputs[source_id] = outputs.get(source_id)

    return inputs


def _evaluate_edge_condition(
    *,
    condition: str,
    source_output: Any,
    evaluator: ExpressionEvaluator,
    context: dict[str, Any],
) -> bool:
    raw_lower = condition.strip().lower()
    if raw_lower in {"true", "false"} and isinstance(source_output, dict):
        expected = raw_lower
        branch = source_output.get("branch")
        if isinstance(branch, str) and branch.strip().lower() in {"true", "false"}:
            return branch.strip().lower() == expected

        result = source_output.get("result")
        if isinstance(result, bool):
            return result if expected == "true" else not result
        if isinstance(result, int | float):
            return bool(result) if expected == "true" else not bool(result)

    expression = _normalize_condition_expression(condition)
    evaluation_context: dict[str, Any] = {}

    # Initial input variables (optional): allow expressions like `threshold >= 0.7`.
    initial_input = context.get("initial_input")
    if isinstance(initial_input, dict):
        evaluation_context.update(initial_input)

    # Source output variables: promote dict keys to top-level, matching WorkflowAgent semantics.
    if (
        isinstance(source_output, dict)
        and "output" in source_output
        and isinstance(source_output.get("output"), dict)
    ):
        evaluation_context.update(source_output.get("output") or {})
    elif isinstance(source_output, dict):
        evaluation_context.update(source_output)
    else:
        evaluation_context["value"] = source_output
        evaluation_context["output"] = source_output

    evaluation_context["context"] = context
    evaluation_context["node_output"] = source_output

    try:
        return bool(evaluator.evaluate(expression, evaluation_context))
    except Exception as exc:  # noqa: BLE001 - fail-soft for edge conditions
        logger.warning(
            "edge_condition_evaluation_failed",
            extra={
                "expression": condition,
                "normalized": expression,
                "error": str(exc),
            },
        )
        return False


def _normalize_condition_expression(condition: str) -> str:
    raw = condition.strip()
    # JS-ish compatibility.
    raw = raw.replace("===", "==").replace("!==", "!=")
    raw = raw.replace("&&", " and ").replace("||", " or ")
    # Lowercase booleans
    raw = re.sub(r"\btrue\b", "True", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\bfalse\b", "False", raw, flags=re.IGNORECASE)
    return raw


_PLACEHOLDER_RE = re.compile(r"\{(?P<path>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+|\[[0-9]+\])*)\}")


def _render_config_templates(
    config: Any,
    *,
    inputs: dict[str, Any],
    context: dict[str, Any],
    logger_extra: dict[str, Any] | None = None,
) -> Any:
    if isinstance(config, dict):
        return {
            k: _render_config_templates(
                v, inputs=inputs, context=context, logger_extra=logger_extra
            )
            for k, v in config.items()
        }
    if isinstance(config, list):
        return [
            _render_config_templates(v, inputs=inputs, context=context, logger_extra=logger_extra)
            for v in config
        ]
    if isinstance(config, str):
        return _render_string_templates(
            config, inputs=inputs, context=context, logger_extra=logger_extra
        )
    return config


def _render_string_templates(
    value: str,
    *,
    inputs: dict[str, Any],
    context: dict[str, Any],
    logger_extra: dict[str, Any] | None = None,
) -> str:
    if "{" not in value or "}" not in value:
        return value

    variables: dict[str, Any] = {
        "context": context,
        "initial_input": context.get("initial_input"),
    }
    for idx, (_key, val) in enumerate(inputs.items(), 1):
        variables[f"input{idx}"] = val

    def _replace(match: re.Match[str]) -> str:
        path = match.group("path")
        resolved = _resolve_path(variables, path)
        if resolved is None:
            logger.debug(
                "config_template_placeholder_unresolved",
                extra={
                    "placeholder": match.group(0),
                    "path": path,
                    "value": value,
                    **(logger_extra or {}),
                },
            )
            return match.group(0)
        if isinstance(resolved, dict | list):
            try:
                import json

                return json.dumps(resolved, ensure_ascii=False)
            except Exception:
                return str(resolved)
        return str(resolved)

    return _PLACEHOLDER_RE.sub(_replace, value)


def _resolve_path(variables: dict[str, Any], path: str) -> Any:
    current: Any = variables

    for part in path.split("."):
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)(\[[0-9]+\])*", part)
        if not match:
            return None

        name = match.group(1)
        if not isinstance(current, dict):
            return None
        current = current.get(name)
        if current is None:
            return None

        for idx_str in re.findall(r"\[([0-9]+)\]", part):
            if not isinstance(current, list):
                return None
            idx = int(idx_str)
            if idx < 0 or idx >= len(current):
                return None
            current = current[idx]

    return current
