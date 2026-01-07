"""WorkflowSaveValidator - 保存前强校验可执行性（Domain Service）

目标（WF-030）：
- 在 workflow 落库前做强校验，避免“保存成功但必然执行失败”
- 复用同一套校验逻辑（拖拽更新 / 对话更新 / 创建 workflow）
- 错误信息前端友好（结构化 + 不泄露内部细节）
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any

from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError, DomainValidationError
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.ports.tool_repository import ToolRepository
from src.domain.services.workflow_engine import topological_sort_ids
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.tool_status import ToolStatus

logger = logging.getLogger(__name__)


def _append_error(
    errors: list[dict[str, Any]],
    *,
    code: str,
    message: str,
    path: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {"code": code, "message": message}
    if path:
        payload["path"] = path
    if meta:
        payload["meta"] = meta
    errors.append(payload)


def _extract_tool_id(config: dict[str, Any]) -> str | None:
    # Accept legacy keys but always normalize to `tool_id` for persistence.
    # KISS: keep the contract minimal and explicit; avoid name-based matching.
    for key in ("tool_id", "toolId"):
        raw = config.get(key)
        if isinstance(raw, str):
            value = raw.strip()
            if value:
                return value
    return None


def _extract_main_subgraph_node_ids(workflow: Workflow) -> set[str]:
    start_ids = {node.id for node in workflow.nodes if node.type == NodeType.START}
    end_ids = {node.id for node in workflow.nodes if node.type == NodeType.END}
    if not start_ids or not end_ids:
        return set()

    forward: dict[str, list[str]] = {}
    backward: dict[str, list[str]] = {}
    for edge in workflow.edges:
        forward.setdefault(edge.source_node_id, []).append(edge.target_node_id)
        backward.setdefault(edge.target_node_id, []).append(edge.source_node_id)

    from collections import deque

    forward_reachable = set(start_ids)
    queue = deque(start_ids)
    while queue:
        current = queue.popleft()
        for nxt in forward.get(current, []):
            if nxt not in forward_reachable:
                forward_reachable.add(nxt)
                queue.append(nxt)

    backward_reachable = set(end_ids)
    queue = deque(end_ids)
    while queue:
        current = queue.popleft()
        for prev in backward.get(current, []):
            if prev not in backward_reachable:
                backward_reachable.add(prev)
                queue.append(prev)

    return forward_reachable & backward_reachable


@dataclass(frozen=True, slots=True)
class WorkflowSaveValidator:
    """校验 workflow 在当前能力集合下是否“可执行”。

    说明：
    - 能力集合由 NodeExecutorRegistry + ToolRepository 共同提供
    - 仅做“保存前强校验”，不负责执行
    """

    executor_registry: NodeExecutorRegistry
    tool_repository: ToolRepository | None = None

    def validate_or_raise(self, workflow: Workflow) -> None:
        started = time.perf_counter()
        errors: list[dict[str, Any]] = []

        # Normalize configs before validation so both drag-save and chat-modify
        # persist the same canonical shape (fail-closed: still validates after).
        self._normalize_workflow_node_configs(workflow)

        self._validate_main_subgraph(workflow, errors=errors)

        node_ids = [node.id for node in workflow.nodes]
        if not node_ids and workflow.edges:
            _append_error(
                errors,
                code="invalid_edges",
                message="edges must be empty when nodes is empty",
                path="edges",
            )
        else:
            self._validate_unique_node_ids(node_ids, errors=errors)
            self._validate_edges_reference_nodes(workflow, errors=errors)
            self._validate_acyclic(workflow, errors=errors)

        self._validate_node_executability(workflow, errors=errors)

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "workflow_save_validation",
            extra={
                "workflow_id": workflow.id,
                "validation_ms": elapsed_ms,
                "error_count": len(errors),
            },
        )

        if errors:
            raise DomainValidationError(
                "Workflow validation failed",
                code="workflow_invalid",
                errors=errors,
            )

    def _normalize_workflow_node_configs(self, workflow: Workflow) -> None:
        for node in workflow.nodes:
            if node.type == NodeType.TOOL and isinstance(node.config, dict):
                tool_id = _extract_tool_id(node.config)
                if tool_id is None:
                    continue
                node.config["tool_id"] = tool_id
                node.config.pop("toolId", None)

    def _validate_unique_node_ids(
        self, node_ids: list[str], *, errors: list[dict[str, Any]]
    ) -> None:
        duplicates = [node_id for node_id, count in Counter(node_ids).items() if count > 1]
        if duplicates:
            _append_error(
                errors,
                code="duplicate_node_id",
                message="duplicate node id",
                path="nodes",
                meta={"duplicates": duplicates},
            )

    def _validate_edges_reference_nodes(
        self, workflow: Workflow, *, errors: list[dict[str, Any]]
    ) -> None:
        node_ids = {node.id for node in workflow.nodes}
        for idx, edge in enumerate(workflow.edges):
            if edge.source_node_id not in node_ids:
                _append_error(
                    errors,
                    code="missing_node",
                    message=f"source node not found: {edge.source_node_id}",
                    path=f"edges[{idx}].source_node_id",
                )
            if edge.target_node_id not in node_ids:
                _append_error(
                    errors,
                    code="missing_node",
                    message=f"target node not found: {edge.target_node_id}",
                    path=f"edges[{idx}].target_node_id",
                )

    def _validate_acyclic(self, workflow: Workflow, *, errors: list[dict[str, Any]]) -> None:
        if not workflow.nodes:
            return
        if any(err.get("code") == "missing_node" for err in errors):
            return
        try:
            topological_sort_ids(
                node_ids=(node.id for node in workflow.nodes),
                edges=((e.source_node_id, e.target_node_id) for e in workflow.edges),
            )
        except DomainError as exc:
            _append_error(
                errors,
                code="cycle_detected",
                message=str(exc),
                path="edges",
            )

    def _validate_node_executability(
        self, workflow: Workflow, *, errors: list[dict[str, Any]]
    ) -> None:
        builtin_types: set[NodeType] = {
            NodeType.INPUT,
            NodeType.START,
            NodeType.DEFAULT,
            NodeType.END,
            NodeType.OUTPUT,
        }

        for idx, node in enumerate(workflow.nodes):
            if node.type in builtin_types:
                continue

            if node.type in {NodeType.JAVASCRIPT, NodeType.PYTHON, NodeType.TRANSFORM}:
                self._validate_code_node(node_index=idx, node_config=node.config, errors=errors)

            if node.type in {NodeType.HTTP, NodeType.HTTP_REQUEST}:
                self._validate_http_request_node(
                    node_index=idx, node_config=node.config, errors=errors
                )

            if not self.executor_registry.has(node.type.value):
                _append_error(
                    errors,
                    code="missing_executor",
                    message=f"missing executor for node_type: {node.type.value}",
                    path=f"nodes[{idx}].type",
                )

            if node.type == NodeType.TOOL:
                self._validate_tool_node(node_index=idx, node_config=node.config, errors=errors)

    def _validate_main_subgraph(self, workflow: Workflow, *, errors: list[dict[str, Any]]) -> None:
        if not workflow.nodes:
            _append_error(
                errors,
                code="empty_workflow",
                message="workflow must contain at least one start->end path",
                path="nodes",
            )
            return

        start_ids = {node.id for node in workflow.nodes if node.type == NodeType.START}
        end_ids = {node.id for node in workflow.nodes if node.type == NodeType.END}
        if not start_ids:
            _append_error(
                errors,
                code="missing_start",
                message="missing start node",
                path="nodes",
            )
        if not end_ids:
            _append_error(
                errors,
                code="missing_end",
                message="missing end node",
                path="nodes",
            )
        if not start_ids or not end_ids:
            return

        main_node_ids = _extract_main_subgraph_node_ids(workflow)
        if not main_node_ids:
            _append_error(
                errors,
                code="no_start_to_end_path",
                message="no path from start to end",
                path="edges",
            )
            return

        intermediate = main_node_ids - start_ids - end_ids
        if not intermediate:
            _append_error(
                errors,
                code="missing_intermediate_nodes",
                message="workflow must include at least one node between start and end",
                path="nodes",
            )

    def _validate_code_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        code = node_config.get("code") if isinstance(node_config, dict) else None
        if not isinstance(code, str) or not code.strip():
            _append_error(
                errors,
                code="missing_code",
                message="code is required for code nodes",
                path=f"nodes[{node_index}].config.code",
            )

    def _validate_http_request_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for http nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        url = node_config.get("url")
        if not isinstance(url, str) or not url.strip():
            _append_error(
                errors,
                code="missing_url",
                message="url is required for http nodes",
                path=f"nodes[{node_index}].config.url",
            )

        method = node_config.get("method")
        if not isinstance(method, str) or not method.strip():
            _append_error(
                errors,
                code="missing_method",
                message="method is required for http nodes",
                path=f"nodes[{node_index}].config.method",
            )

    def _validate_tool_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        tool_id = _extract_tool_id(node_config)
        if tool_id is None:
            _append_error(
                errors,
                code="missing_tool_id",
                message="tool_id is required for tool nodes",
                path=f"nodes[{node_index}].config.tool_id",
            )
            return

        repository = self.tool_repository
        if repository is None:
            _append_error(
                errors,
                code="tool_repository_unavailable",
                message="tool repository is unavailable",
                path=f"nodes[{node_index}].config.tool_id",
            )
            return

        if not repository.exists(tool_id):
            _append_error(
                errors,
                code="tool_not_found",
                message=f"tool not found: {tool_id}",
                path=f"nodes[{node_index}].config.tool_id",
            )
            return

        tool = repository.find_by_id(tool_id)
        if tool is not None and tool.status == ToolStatus.DEPRECATED:
            _append_error(
                errors,
                code="tool_deprecated",
                message=f"tool is deprecated: {tool_id}",
                path=f"nodes[{node_index}].config.tool_id",
            )
