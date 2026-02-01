"""WorkflowSaveValidator - 保存前强校验可执行性（Domain Service）

目标（WF-030）：
- 在 workflow 落库前做强校验，避免“保存成功但必然执行失败”
- 复用同一套校验逻辑（拖拽更新 / 对话更新 / 创建 workflow）
- 错误信息前端友好（结构化 + 不泄露内部细节）
"""

from __future__ import annotations

import json
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
from src.domain.value_objects.workflow_status import WorkflowStatus

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
            # Canonicalize legacy config keys before applying fail-closed validation so that
            # drag-save and chat-modify persist a single stable shape (KISS/DRY).
            if node.type in {NodeType.HTTP, NodeType.HTTP_REQUEST} and isinstance(
                node.config, dict
            ):
                url = node.config.get("url")
                if isinstance(url, str) and url.strip():
                    node.config["url"] = url.strip()
                    node.config.pop("path", None)
                else:
                    path_value = node.config.get("path")
                    if isinstance(path_value, str):
                        normalized = path_value.strip()
                        if normalized:
                            node.config["url"] = normalized
                            node.config.pop("path", None)

            if node.type == NodeType.TOOL and isinstance(node.config, dict):
                tool_id = _extract_tool_id(node.config)
                if tool_id is None:
                    continue
                node.config["tool_id"] = tool_id
                node.config.pop("toolId", None)

            if node.type == NodeType.LOOP and isinstance(node.config, dict):
                loop_type = node.config.get("type")
                normalized_type = loop_type.strip() if isinstance(loop_type, str) else None
                if normalized_type == "for":
                    normalized_type = "range"
                if normalized_type == "range":
                    node.config["type"] = "range"
                    if "end" not in node.config and "iterations" in node.config:
                        node.config["end"] = node.config.get("iterations")
                    node.config.pop("iterations", None)

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
        status_value = getattr(workflow, "status", None)
        status_str = getattr(status_value, "value", status_value)
        is_draft = status_value == WorkflowStatus.DRAFT or status_str == WorkflowStatus.DRAFT.value
        main_node_ids: set[str] | None = None
        if is_draft:
            # Draft workflows may contain in-progress nodes. We still fail-closed for the
            # main start->end subgraph because those nodes are runnable.
            main_node_ids = _extract_main_subgraph_node_ids(workflow) or None

        builtin_types: set[NodeType] = {
            NodeType.INPUT,
            NodeType.START,
            NodeType.DEFAULT,
            NodeType.END,
            NodeType.OUTPUT,
        }

        incoming_sources: dict[str, list[str]] = {}
        for edge in workflow.edges:
            incoming_sources.setdefault(edge.target_node_id, []).append(edge.source_node_id)

        for idx, node in enumerate(workflow.nodes):
            if node.type in builtin_types:
                continue

            if not self.executor_registry.has(node.type.value):
                _append_error(
                    errors,
                    code="missing_executor",
                    message=f"missing executor for node_type: {node.type.value}",
                    path=f"nodes[{idx}].type",
                )

            if node.type == NodeType.TOOL:
                self._validate_tool_node(node_index=idx, node_config=node.config, errors=errors)

            # Draft workflows may be incomplete, but nodes on the main subgraph must be runnable.
            if is_draft and main_node_ids is not None and node.id not in main_node_ids:
                continue

            if node.type in {NodeType.JAVASCRIPT, NodeType.PYTHON}:
                self._validate_code_node(node_index=idx, node_config=node.config, errors=errors)

            if node.type in {NodeType.TEXT_MODEL, NodeType.LLM}:
                self._validate_text_model_node(
                    node_index=idx,
                    node_config=node.config,
                    incoming_source_node_ids=incoming_sources.get(node.id, []),
                    errors=errors,
                )

            if node.type == NodeType.PROMPT:
                self._validate_prompt_node(node_index=idx, node_config=node.config, errors=errors)

            if node.type == NodeType.TRANSFORM:
                self._validate_transform_node(
                    node_index=idx,
                    node_config=node.config,
                    errors=errors,
                )

            if node.type in {NodeType.HTTP, NodeType.HTTP_REQUEST}:
                self._validate_http_request_node(
                    node_index=idx, node_config=node.config, errors=errors
                )

            if node.type in {NodeType.CONDITIONAL, NodeType.CONDITION}:
                self._validate_conditional_node(
                    node_index=idx, node_config=node.config, errors=errors
                )

            if node.type == NodeType.LOOP:
                self._validate_loop_node(node_index=idx, node_config=node.config, errors=errors)

            if node.type == NodeType.DATABASE:
                self._validate_database_node(
                    node_index=idx,
                    node_config=node.config,
                    errors=errors,
                )

            if node.type == NodeType.FILE:
                self._validate_file_node(node_index=idx, node_config=node.config, errors=errors)

            if node.type == NodeType.NOTIFICATION:
                self._validate_notification_node(
                    node_index=idx,
                    node_config=node.config,
                    errors=errors,
                )

            if node.type == NodeType.EMBEDDING:
                self._validate_embedding_node(
                    node_index=idx, node_config=node.config, errors=errors
                )
                self._validate_requires_text_input_or_incoming_edge(
                    node_index=idx,
                    node_config=node.config,
                    node_label="embedding",
                    config_input_keys=("input", "text", "prompt", "content"),
                    incoming_source_node_ids=incoming_sources.get(node.id, []),
                    errors=errors,
                )

            if node.type == NodeType.IMAGE:
                self._validate_image_generation_node(
                    node_index=idx, node_config=node.config, errors=errors
                )
                self._validate_requires_text_input_or_incoming_edge(
                    node_index=idx,
                    node_config=node.config,
                    node_label="imageGeneration",
                    config_input_keys=("prompt", "text", "input", "content"),
                    incoming_source_node_ids=incoming_sources.get(node.id, []),
                    errors=errors,
                )

            if node.type == NodeType.AUDIO:
                self._validate_audio_node(node_index=idx, node_config=node.config, errors=errors)
                self._validate_requires_text_input_or_incoming_edge(
                    node_index=idx,
                    node_config=node.config,
                    node_label="audio",
                    config_input_keys=("text", "input", "prompt", "content"),
                    incoming_source_node_ids=incoming_sources.get(node.id, []),
                    errors=errors,
                )

            if node.type == NodeType.STRUCTURED_OUTPUT:
                self._validate_structured_output_node(
                    node_index=idx, node_config=node.config, errors=errors
                )
                self._validate_requires_text_input_or_incoming_edge(
                    node_index=idx,
                    node_config=node.config,
                    node_label="structuredOutput",
                    config_input_keys=("prompt", "text", "input", "content"),
                    incoming_source_node_ids=incoming_sources.get(node.id, []),
                    errors=errors,
                )

    def _validate_main_subgraph(self, workflow: Workflow, *, errors: list[dict[str, Any]]) -> None:
        if not workflow.nodes:
            _append_error(
                errors,
                code="empty_workflow",
                message="workflow must contain at least one start->end path",
                path="nodes",
            )
            return

        status_value = getattr(workflow, "status", None)
        status_str = getattr(status_value, "value", status_value)
        is_draft = status_value == WorkflowStatus.DRAFT or status_str == WorkflowStatus.DRAFT.value

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
            if not is_draft:
                _append_error(
                    errors,
                    code="missing_end",
                    message="missing end node",
                    path="nodes",
                )
            return
        if not start_ids:
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

    def _validate_transform_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for transform nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        transform_type = node_config.get("type")
        if not isinstance(transform_type, str) or not transform_type.strip():
            _append_error(
                errors,
                code="missing_transform_type",
                message="type is required for transform nodes",
                path=f"nodes[{node_index}].config.type",
            )
            return

        transform_type = transform_type.strip()
        if transform_type == "field_mapping":
            mapping = node_config.get("mapping")
            if not isinstance(mapping, dict) or not mapping:
                _append_error(
                    errors,
                    code="missing_mapping",
                    message="mapping is required for field_mapping transform",
                    path=f"nodes[{node_index}].config.mapping",
                )
        elif transform_type == "type_conversion":
            conversions = node_config.get("conversions")
            if not isinstance(conversions, dict) or not conversions:
                _append_error(
                    errors,
                    code="missing_conversions",
                    message="conversions is required for type_conversion transform",
                    path=f"nodes[{node_index}].config.conversions",
                )
        elif transform_type == "field_extraction":
            path_value = node_config.get("path")
            if not isinstance(path_value, str) or not path_value.strip():
                _append_error(
                    errors,
                    code="missing_path",
                    message="path is required for field_extraction transform",
                    path=f"nodes[{node_index}].config.path",
                )
        elif transform_type == "array_mapping":
            field_value = node_config.get("field")
            mapping = node_config.get("mapping")
            if not isinstance(field_value, str) or not field_value.strip():
                _append_error(
                    errors,
                    code="missing_field",
                    message="field is required for array_mapping transform",
                    path=f"nodes[{node_index}].config.field",
                )
            if not isinstance(mapping, dict) or not mapping:
                _append_error(
                    errors,
                    code="missing_mapping",
                    message="mapping is required for array_mapping transform",
                    path=f"nodes[{node_index}].config.mapping",
                )
        elif transform_type == "filtering":
            field_value = node_config.get("field")
            condition = node_config.get("condition")
            if not isinstance(field_value, str) or not field_value.strip():
                _append_error(
                    errors,
                    code="missing_field",
                    message="field is required for filtering transform",
                    path=f"nodes[{node_index}].config.field",
                )
            if not isinstance(condition, str) or not condition.strip():
                _append_error(
                    errors,
                    code="missing_condition",
                    message="condition is required for filtering transform",
                    path=f"nodes[{node_index}].config.condition",
                )
        elif transform_type == "aggregation":
            field_value = node_config.get("field")
            operations = node_config.get("operations")
            if not isinstance(field_value, str) or not field_value.strip():
                _append_error(
                    errors,
                    code="missing_field",
                    message="field is required for aggregation transform",
                    path=f"nodes[{node_index}].config.field",
                )
            if not isinstance(operations, list) or not operations:
                _append_error(
                    errors,
                    code="missing_operations",
                    message="operations is required for aggregation transform",
                    path=f"nodes[{node_index}].config.operations",
                )
        elif transform_type == "custom":
            function_name = node_config.get("function")
            if not isinstance(function_name, str) or not function_name.strip():
                _append_error(
                    errors,
                    code="missing_function",
                    message="function is required for custom transform",
                    path=f"nodes[{node_index}].config.function",
                )
        else:
            _append_error(
                errors,
                code="unsupported_transform_type",
                message=f"unsupported transform type: {transform_type}",
                path=f"nodes[{node_index}].config.type",
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
        path_value = node_config.get("path")
        has_url = isinstance(url, str) and url.strip()
        has_path = isinstance(path_value, str) and path_value.strip()
        if not has_url and not has_path:
            _append_error(
                errors,
                code="missing_url",
                message="url (or path) is required for http nodes",
                path=f"nodes[{node_index}].config",
            )

        method = node_config.get("method")
        if not isinstance(method, str) or not method.strip():
            _append_error(
                errors,
                code="missing_method",
                message="method is required for http nodes",
                path=f"nodes[{node_index}].config.method",
            )

        # Validate JSON fields early to avoid “save ok but executor必失败” drift.
        headers_value = node_config.get("headers")
        if isinstance(headers_value, str) and headers_value.strip():
            parsed = self._try_parse_json(
                headers_value, errors=errors, path=f"nodes[{node_index}].config.headers"
            )
            if parsed is not None and not isinstance(parsed, dict):
                _append_error(
                    errors,
                    code="invalid_headers",
                    message="headers must be a JSON object",
                    path=f"nodes[{node_index}].config.headers",
                )

        body_value = node_config.get("body")
        if isinstance(body_value, str) and body_value.strip():
            self._try_parse_json(body_value, errors=errors, path=f"nodes[{node_index}].config.body")

        mock_response_value = node_config.get("mock_response")
        if isinstance(mock_response_value, str) and mock_response_value.strip():
            self._try_parse_json(
                mock_response_value,
                errors=errors,
                path=f"nodes[{node_index}].config.mock_response",
            )

    def _validate_embedding_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for embedding nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        model = node_config.get("model")
        if not isinstance(model, str) or not model.strip():
            _append_error(
                errors,
                code="missing_model",
                message="model is required for embedding nodes",
                path=f"nodes[{node_index}].config.model",
            )

    def _validate_image_generation_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for image nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        model = node_config.get("model")
        if not isinstance(model, str) or not model.strip():
            _append_error(
                errors,
                code="missing_model",
                message="model is required for image nodes",
                path=f"nodes[{node_index}].config.model",
            )

    def _validate_audio_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for audio nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        model = node_config.get("model")
        if not isinstance(model, str) or not model.strip():
            _append_error(
                errors,
                code="missing_model",
                message="model is required for audio nodes",
                path=f"nodes[{node_index}].config.model",
            )

    def _validate_structured_output_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for structured output nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        schema_name = node_config.get("schemaName")
        if not isinstance(schema_name, str) or not schema_name.strip():
            _append_error(
                errors,
                code="missing_schema_name",
                message="schemaName is required for structured output nodes",
                path=f"nodes[{node_index}].config.schemaName",
            )

        schema_value = node_config.get("schema")
        if isinstance(schema_value, str):
            has_schema = bool(schema_value.strip())
        else:
            has_schema = isinstance(schema_value, dict) and bool(schema_value)
        if not has_schema:
            _append_error(
                errors,
                code="missing_schema",
                message="schema is required for structured output nodes",
                path=f"nodes[{node_index}].config.schema",
            )
        elif isinstance(schema_value, str) and schema_value.strip():
            parsed = self._try_parse_json(
                schema_value,
                errors=errors,
                path=f"nodes[{node_index}].config.schema",
            )
            if parsed is not None and not isinstance(parsed, dict):
                _append_error(
                    errors,
                    code="invalid_schema",
                    message="schema must be a JSON object",
                    path=f"nodes[{node_index}].config.schema",
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

    def _validate_text_model_node(
        self,
        *,
        node_index: int,
        node_config: dict[str, Any],
        incoming_source_node_ids: list[str],
        errors: list[dict[str, Any]],
    ) -> None:
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for textModel nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        model = node_config.get("model")
        if not isinstance(model, str) or not model.strip():
            _append_error(
                errors,
                code="missing_model",
                message="model is required for textModel nodes",
                path=f"nodes[{node_index}].config.model",
            )

        prompt = node_config.get("prompt") or node_config.get("user_prompt")
        has_prompt = isinstance(prompt, str) and prompt.strip()
        if has_prompt:
            return

        incoming_count = len(incoming_source_node_ids)
        if incoming_count == 0:
            _append_error(
                errors,
                code="missing_prompt",
                message="textModel nodes must have prompt or at least one incoming edge",
                path=f"nodes[{node_index}].config.prompt",
            )
            return

        if incoming_count == 1:
            return

        prompt_source = node_config.get("promptSourceNodeId") or node_config.get("promptSource")
        if not isinstance(prompt_source, str) or not prompt_source.strip():
            _append_error(
                errors,
                code="ambiguous_prompt_source",
                message=(
                    "textModel nodes with multiple inputs require promptSourceNodeId "
                    "or a Prompt node to merge inputs"
                ),
                path=f"nodes[{node_index}].config.promptSourceNodeId",
                meta={"incoming_sources": incoming_source_node_ids},
            )
            return

        normalized_source = prompt_source.strip()
        if normalized_source not in set(incoming_source_node_ids):
            _append_error(
                errors,
                code="invalid_prompt_source",
                message=f"promptSourceNodeId not found in incoming sources: {normalized_source}",
                path=f"nodes[{node_index}].config.promptSourceNodeId",
                meta={"incoming_sources": incoming_source_node_ids},
            )

    def _validate_prompt_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for prompt nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        content = node_config.get("content")
        if not isinstance(content, str) or not content.strip():
            _append_error(
                errors,
                code="missing_content",
                message="content is required for prompt nodes",
                path=f"nodes[{node_index}].config.content",
            )

    def _validate_conditional_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for conditional nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        condition = node_config.get("condition")
        if not isinstance(condition, str) or not condition.strip():
            _append_error(
                errors,
                code="missing_condition",
                message="condition is required for conditional nodes",
                path=f"nodes[{node_index}].config.condition",
            )

    def _validate_loop_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for loop nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        loop_type = node_config.get("type")
        if not isinstance(loop_type, str) or not loop_type.strip():
            _append_error(
                errors,
                code="missing_type",
                message="type is required for loop nodes",
                path=f"nodes[{node_index}].config.type",
            )
            return

        normalized_type = loop_type.strip()
        # Back-compat: UI 曾使用 `for`，runtime 以 `range` 为准。
        if normalized_type == "for":
            normalized_type = "range"

        supported_types = {"for_each", "range", "while"}
        if normalized_type not in supported_types:
            _append_error(
                errors,
                code="unsupported_loop_type",
                message=f"unsupported loop type: {loop_type}",
                path=f"nodes[{node_index}].config.type",
            )
            return

        if normalized_type == "for_each":
            array_field = node_config.get("array")
            if not isinstance(array_field, str) or not array_field.strip():
                _append_error(
                    errors,
                    code="missing_array",
                    message="array is required for for_each loop",
                    path=f"nodes[{node_index}].config.array",
                )

        if normalized_type == "range":
            end_value = node_config.get("end")
            if end_value is None:
                end_value = node_config.get("iterations")
            if end_value is None:
                _append_error(
                    errors,
                    code="missing_end",
                    message="end (or iterations) is required for range loop",
                    path=f"nodes[{node_index}].config.end",
                )
            elif not (
                (isinstance(end_value, int) and not isinstance(end_value, bool))
                or (isinstance(end_value, str) and end_value.strip().isdigit())
            ):
                _append_error(
                    errors,
                    code="invalid_end",
                    message="end (or iterations) must be an integer",
                    path=f"nodes[{node_index}].config.end",
                )
            code = node_config.get("code")
            if not isinstance(code, str) or not code.strip():
                _append_error(
                    errors,
                    code="missing_code",
                    message="code is required for range loop",
                    path=f"nodes[{node_index}].config.code",
                )

        if normalized_type == "while":
            condition = node_config.get("condition")
            if not isinstance(condition, str) or not condition.strip():
                _append_error(
                    errors,
                    code="missing_condition",
                    message="condition is required for while loop",
                    path=f"nodes[{node_index}].config.condition",
                )
            code = node_config.get("code")
            if not isinstance(code, str) or not code.strip():
                _append_error(
                    errors,
                    code="missing_code",
                    message="code is required for while loop",
                    path=f"nodes[{node_index}].config.code",
                )
            max_iterations = node_config.get("max_iterations")
            if max_iterations is not None and (
                not isinstance(max_iterations, int)
                or isinstance(max_iterations, bool)
                or max_iterations <= 0
            ):
                _append_error(
                    errors,
                    code="invalid_max_iterations",
                    message="max_iterations must be a positive integer",
                    path=f"nodes[{node_index}].config.max_iterations",
                )

    def _validate_database_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for database nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        sql = node_config.get("sql")
        if not isinstance(sql, str) or not sql.strip():
            _append_error(
                errors,
                code="missing_sql",
                message="sql is required for database nodes",
                path=f"nodes[{node_index}].config.sql",
            )

        database_url = node_config.get("database_url")
        if database_url is None:
            # Keep executor default but persist a canonical value to avoid drift.
            node_config["database_url"] = "sqlite:///agent_data.db"
        elif not isinstance(database_url, str) or not database_url.strip():
            _append_error(
                errors,
                code="missing_database_url",
                message="database_url is required for database nodes",
                path=f"nodes[{node_index}].config.database_url",
            )
        else:
            normalized_url = database_url.strip()
            node_config["database_url"] = normalized_url
            # Fail-closed: runtime currently only supports sqlite.
            if not normalized_url.startswith("sqlite:///"):
                _append_error(
                    errors,
                    code="unsupported_database_url",
                    message="only sqlite:/// database_url is supported",
                    path=f"nodes[{node_index}].config.database_url",
                    meta={"supported_prefix": "sqlite:///"},
                )

        params_value = node_config.get("params")
        if isinstance(params_value, str) and params_value.strip():
            parsed = self._try_parse_json(
                params_value,
                errors=errors,
                path=f"nodes[{node_index}].config.params",
            )
            if parsed is not None and not isinstance(parsed, dict | list):
                _append_error(
                    errors,
                    code="invalid_params",
                    message="params must be a JSON object or array",
                    path=f"nodes[{node_index}].config.params",
                )

    def _validate_file_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for file nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        operation = node_config.get("operation")
        if not isinstance(operation, str) or not operation.strip():
            _append_error(
                errors,
                code="missing_operation",
                message="operation is required for file nodes",
                path=f"nodes[{node_index}].config.operation",
            )
            return

        allowed = {"read", "write", "append", "delete", "list"}
        normalized_operation = operation.strip().lower()
        if normalized_operation not in allowed:
            _append_error(
                errors,
                code="unsupported_operation",
                message=f"unsupported file operation: {operation}",
                path=f"nodes[{node_index}].config.operation",
                meta={"allowed": sorted(allowed)},
            )

        path_value = node_config.get("path")
        if not isinstance(path_value, str) or not path_value.strip():
            _append_error(
                errors,
                code="missing_path",
                message="path is required for file nodes",
                path=f"nodes[{node_index}].config.path",
            )

    def _validate_notification_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for notification nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        notification_type = node_config.get("type")
        if not isinstance(notification_type, str) or not notification_type.strip():
            _append_error(
                errors,
                code="missing_type",
                message="type is required for notification nodes",
                path=f"nodes[{node_index}].config.type",
            )
            return

        message_value = node_config.get("message")
        if not isinstance(message_value, str) or not message_value.strip():
            _append_error(
                errors,
                code="missing_message",
                message="message is required for notification nodes",
                path=f"nodes[{node_index}].config.message",
            )

        # Optional JSON fields
        headers_value = node_config.get("headers")
        if isinstance(headers_value, str) and headers_value.strip():
            parsed = self._try_parse_json(
                headers_value,
                errors=errors,
                path=f"nodes[{node_index}].config.headers",
            )
            if parsed is not None and not isinstance(parsed, dict):
                _append_error(
                    errors,
                    code="invalid_headers",
                    message="headers must be a JSON object",
                    path=f"nodes[{node_index}].config.headers",
                )

        normalized_type = notification_type.strip().lower()
        if normalized_type == "webhook":
            url = node_config.get("url")
            if not isinstance(url, str) or not url.strip():
                _append_error(
                    errors,
                    code="missing_url",
                    message="url is required for webhook notification",
                    path=f"nodes[{node_index}].config.url",
                )
        elif normalized_type == "slack":
            webhook_url = node_config.get("webhook_url")
            if not isinstance(webhook_url, str) or not webhook_url.strip():
                _append_error(
                    errors,
                    code="missing_webhook_url",
                    message="webhook_url is required for slack notification",
                    path=f"nodes[{node_index}].config.webhook_url",
                )
        elif normalized_type == "email":
            smtp_host = node_config.get("smtp_host")
            sender = node_config.get("sender")
            sender_password = node_config.get("sender_password")
            if not isinstance(smtp_host, str) or not smtp_host.strip():
                _append_error(
                    errors,
                    code="missing_smtp_host",
                    message="smtp_host is required for email notification",
                    path=f"nodes[{node_index}].config.smtp_host",
                )
            if not isinstance(sender, str) or not sender.strip():
                _append_error(
                    errors,
                    code="missing_sender",
                    message="sender is required for email notification",
                    path=f"nodes[{node_index}].config.sender",
                )
            if not isinstance(sender_password, str) or not sender_password.strip():
                _append_error(
                    errors,
                    code="missing_sender_password",
                    message="sender_password is required for email notification",
                    path=f"nodes[{node_index}].config.sender_password",
                )

            recipients = node_config.get("recipients")
            if recipients is None:
                _append_error(
                    errors,
                    code="missing_recipients",
                    message="recipients is required for email notification",
                    path=f"nodes[{node_index}].config.recipients",
                )
            elif isinstance(recipients, str):
                if not recipients.strip():
                    _append_error(
                        errors,
                        code="missing_recipients",
                        message="recipients is required for email notification",
                        path=f"nodes[{node_index}].config.recipients",
                    )
                else:
                    # If user provides JSON, validate it; otherwise treat as a single email.
                    raw = recipients.strip()
                    if raw.startswith("[") or raw.startswith('"'):
                        parsed = self._try_parse_json(
                            raw,
                            errors=errors,
                            path=f"nodes[{node_index}].config.recipients",
                        )
                        if parsed is not None and not isinstance(parsed, list | str):
                            _append_error(
                                errors,
                                code="invalid_recipients",
                                message="recipients must be a JSON array or string",
                                path=f"nodes[{node_index}].config.recipients",
                            )
            elif isinstance(recipients, list):
                if not recipients:
                    _append_error(
                        errors,
                        code="missing_recipients",
                        message="recipients is required for email notification",
                        path=f"nodes[{node_index}].config.recipients",
                    )
            else:
                _append_error(
                    errors,
                    code="invalid_recipients",
                    message="recipients must be a JSON array or string",
                    path=f"nodes[{node_index}].config.recipients",
                )
        else:
            _append_error(
                errors,
                code="unsupported_notification_type",
                message=f"unsupported notification type: {notification_type}",
                path=f"nodes[{node_index}].config.type",
            )

    def _validate_requires_text_input_or_incoming_edge(
        self,
        *,
        node_index: int,
        node_config: dict[str, Any],
        node_label: str,
        config_input_keys: tuple[str, ...],
        incoming_source_node_ids: list[str],
        errors: list[dict[str, Any]],
    ) -> None:
        if not isinstance(node_config, dict):
            return

        for key in config_input_keys:
            value = node_config.get(key)
            if isinstance(value, str) and value.strip():
                return
            if isinstance(value, list) and value:
                return
            if value is not None and not isinstance(value, str | list):
                # Non-string inputs (e.g. dict) are acceptable, executor will stringify them.
                return

        if not incoming_source_node_ids:
            _append_error(
                errors,
                code="missing_input",
                message=f"{node_label} nodes must have config input or at least one incoming edge",
                path=f"nodes[{node_index}].config",
            )

    def _try_parse_json(self, raw: str, *, errors: list[dict[str, Any]], path: str) -> Any | None:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            _append_error(
                errors,
                code="invalid_json",
                message="invalid JSON",
                path=path,
            )
            return None
