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
from typing import Any, cast

from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError, DomainValidationError
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.ports.tool_repository import ToolRepository
from src.domain.services.workflow_engine import topological_sort_ids
from src.domain.services.workflow_node_contracts import (
    DEFAULT_SQLITE_DATABASE_URL,
    SQLITE_DATABASE_URL_PREFIX,
    get_editor_workflow_node_contracts,
)
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.tool_status import ToolStatus
from src.domain.value_objects.workflow_status import WorkflowStatus

logger = logging.getLogger(__name__)

_EDITOR_WORKFLOW_NODE_CONTRACTS = get_editor_workflow_node_contracts()


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


def _node_path(node_index: int, relative_path: str) -> str:
    return f"nodes[{node_index}].{relative_path}"


def _is_non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_non_empty_dict(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


def _is_non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def _normalize_string(value: Any, *, normalize: str) -> str | None:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return ""
    if normalize == "lower_strip":
        return raw.lower()
    return raw


def _validate_model_provider_contract(
    *,
    node_index: int,
    node_config: dict[str, Any],
    contract,
    errors: list[dict[str, Any]],
) -> None:
    """Validate model provider constraints using the shared contract spec.

    KISS: Missing-model is handled by required-field checks; this helper only validates when a
    non-empty model string is present.
    """

    if contract is None:
        return

    model_value = node_config.get(contract.model_key)
    if not _is_non_empty_str(model_value):
        return

    raw_model = cast(str, model_value).strip()
    provider = _parse_model_provider(raw_model)
    if provider not in set(contract.allowed_providers):
        _append_error(
            errors,
            code=contract.unsupported_provider_code,
            message=contract.unsupported_provider_message,
            path=_node_path(node_index, f"config.{contract.model_key}"),
            meta={"provider": provider},
        )
        return

    lowered = raw_model.lower()
    if contract.block_model_substrings_anywhere and any(
        token in lowered for token in contract.block_model_substrings_anywhere
    ):
        _append_error(
            errors,
            code=contract.unsupported_model_code,
            message=contract.unsupported_model_message_template.format(model=raw_model),
            path=_node_path(node_index, f"config.{contract.model_key}"),
        )
        return

    if (
        contract.block_unprefixed_non_openai_families
        and _looks_like_non_openai_model(raw_model, tokens=contract.non_openai_tokens)
        and not lowered.startswith("openai/")
    ):
        _append_error(
            errors,
            code=contract.unsupported_model_code,
            message=contract.unsupported_model_message_template.format(model=raw_model),
            path=_node_path(node_index, f"config.{contract.model_key}"),
        )


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


def _parse_model_provider(model: Any) -> str:
    """Extract provider prefix from model strings like 'openai/gpt-4o-mini'.

    KISS: For models without an explicit provider prefix, default to 'openai'
    to match executor behavior.
    """

    if not isinstance(model, str):
        return "openai"
    raw = model.strip()
    if not raw:
        return "openai"
    if "/" in raw:
        provider, _name = raw.split("/", 1)
        provider = provider.strip().lower()
        return provider or "openai"
    return "openai"


def _looks_like_non_openai_model(
    model: str, *, tokens: tuple[str, ...] = ("claude", "anthropic", "gemini", "google", "cohere")
) -> bool:
    """Heuristic guard to avoid 'save ok but execute will 100% fail' drift.

    Rationale:
    - We currently allow models without an explicit provider prefix and default them to OpenAI
      to preserve backward compatibility.
    - However, users/LLMs may supply non-OpenAI model names without a prefix (e.g. 'claude-*', 'gemini-*'),
      which would otherwise be treated as OpenAI and fail at runtime.
    """

    raw = (model or "").strip().lower()
    if not raw:
        return False
    # Keep this list intentionally small and high-signal.
    return any(token in raw for token in tokens)


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

            # Draft workflows may be incomplete, but nodes on the main subgraph must be runnable.
            if is_draft and main_node_ids is not None and node.id not in main_node_ids:
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

            if node.type in {NodeType.JAVASCRIPT, NodeType.PYTHON}:
                self._validate_code_node(
                    node_index=idx, node_type=node.type, node_config=node.config, errors=errors
                )

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
                input_contract = None
                embedding_contract = _EDITOR_WORKFLOW_NODE_CONTRACTS.get(NodeType.EMBEDDING.value)
                if embedding_contract is not None:
                    input_contract = embedding_contract.requires_input_or_incoming_edge
                self._validate_requires_text_input_or_incoming_edge(
                    node_index=idx,
                    node_config=node.config,
                    config_input_keys=input_contract.config_input_keys
                    if input_contract
                    else ("input", "text", "prompt", "content"),
                    incoming_source_node_ids=incoming_sources.get(node.id, []),
                    errors=errors,
                    code=input_contract.code if input_contract else "missing_input",
                    message=input_contract.message
                    if input_contract
                    else "embedding nodes must have config input or at least one incoming edge",
                )

            if node.type == NodeType.IMAGE:
                self._validate_image_generation_node(
                    node_index=idx, node_config=node.config, errors=errors
                )
                input_contract = None
                image_contract = _EDITOR_WORKFLOW_NODE_CONTRACTS.get(NodeType.IMAGE.value)
                if image_contract is not None:
                    input_contract = image_contract.requires_input_or_incoming_edge
                self._validate_requires_text_input_or_incoming_edge(
                    node_index=idx,
                    node_config=node.config,
                    config_input_keys=input_contract.config_input_keys
                    if input_contract
                    else ("prompt", "text", "input", "content"),
                    incoming_source_node_ids=incoming_sources.get(node.id, []),
                    errors=errors,
                    code=input_contract.code if input_contract else "missing_input",
                    message=input_contract.message
                    if input_contract
                    else "imageGeneration nodes must have config input or at least one incoming edge",
                )

            if node.type == NodeType.AUDIO:
                self._validate_audio_node(node_index=idx, node_config=node.config, errors=errors)
                input_contract = None
                audio_contract = _EDITOR_WORKFLOW_NODE_CONTRACTS.get(NodeType.AUDIO.value)
                if audio_contract is not None:
                    input_contract = audio_contract.requires_input_or_incoming_edge
                self._validate_requires_text_input_or_incoming_edge(
                    node_index=idx,
                    node_config=node.config,
                    config_input_keys=input_contract.config_input_keys
                    if input_contract
                    else ("text", "input", "prompt", "content"),
                    incoming_source_node_ids=incoming_sources.get(node.id, []),
                    errors=errors,
                    code=input_contract.code if input_contract else "missing_input",
                    message=input_contract.message
                    if input_contract
                    else "audio nodes must have config input or at least one incoming edge",
                )

            if node.type == NodeType.STRUCTURED_OUTPUT:
                self._validate_structured_output_node(
                    node_index=idx, node_config=node.config, errors=errors
                )
                input_contract = None
                structured_contract = _EDITOR_WORKFLOW_NODE_CONTRACTS.get(
                    NodeType.STRUCTURED_OUTPUT.value
                )
                if structured_contract is not None:
                    input_contract = structured_contract.requires_input_or_incoming_edge
                self._validate_requires_text_input_or_incoming_edge(
                    node_index=idx,
                    node_config=node.config,
                    config_input_keys=input_contract.config_input_keys
                    if input_contract
                    else ("prompt", "text", "input", "content"),
                    incoming_source_node_ids=incoming_sources.get(node.id, []),
                    errors=errors,
                    code=input_contract.code if input_contract else "missing_input",
                    message=input_contract.message
                    if input_contract
                    else "structuredOutput nodes must have config input or at least one incoming edge",
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
        self,
        *,
        node_index: int,
        node_type: NodeType,
        node_config: dict[str, Any],
        errors: list[dict[str, Any]],
    ) -> None:
        contract = _EDITOR_WORKFLOW_NODE_CONTRACTS.get(node_type.value)
        requirement = None
        if contract is not None:
            requirement = next((req for req in contract.required_fields if req.key == "code"), None)

        code_value = node_config.get("code") if isinstance(node_config, dict) else None
        if not isinstance(code_value, str) or not code_value.strip():
            _append_error(
                errors,
                code=requirement.code if requirement else "missing_code",
                message=requirement.message if requirement else "code is required for code nodes",
                path=_node_path(node_index, requirement.path if requirement else "config.code"),
            )

    def _validate_transform_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        contract = _EDITOR_WORKFLOW_NODE_CONTRACTS.get(NodeType.TRANSFORM.value)
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for transform nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        # Required: transform `type`
        required_type = (
            contract.required_fields[0] if contract and contract.required_fields else None
        )
        raw_type = node_config.get("type")
        transform_type = raw_type.strip() if isinstance(raw_type, str) else ""
        if not transform_type:
            _append_error(
                errors,
                code=required_type.code if required_type else "missing_transform_type",
                message=required_type.message
                if required_type
                else "type is required for transform nodes",
                path=_node_path(node_index, required_type.path if required_type else "config.type"),
            )
            return

        # Allowed types
        enum_spec = None
        if contract:
            enum_spec = next((spec for spec in contract.enum_fields if spec.key == "type"), None)
        allowed = set(enum_spec.allowed) if enum_spec else set()
        if allowed and transform_type not in allowed:
            _append_error(
                errors,
                code=enum_spec.code if enum_spec else "unsupported_transform_type",
                message=(
                    enum_spec.message.format(value=transform_type)
                    if enum_spec
                    else f"unsupported transform type: {transform_type}"
                ),
                path=_node_path(node_index, enum_spec.path if enum_spec else "config.type"),
            )
            return

        # Conditional required fields per transform type
        for conditional in contract.conditional_required if contract else ():
            normalized = _normalize_string(raw_type, normalize=conditional.normalize)
            if normalized != conditional.when_equals:
                continue
            for requirement in conditional.required_fields:
                value = node_config.get(requirement.key)
                ok = False
                if requirement.kind == "string":
                    ok = _is_non_empty_str(value)
                elif requirement.kind == "object":
                    ok = _is_non_empty_dict(value)
                elif requirement.kind == "array":
                    ok = _is_non_empty_list(value)
                if not ok:
                    _append_error(
                        errors,
                        code=requirement.code,
                        message=requirement.message,
                        path=_node_path(node_index, requirement.path),
                    )

    def _validate_http_request_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        contract = _EDITOR_WORKFLOW_NODE_CONTRACTS.get(NodeType.HTTP_REQUEST.value)
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for http nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        any_of = None
        if contract and contract.required_any_of:
            any_of = contract.required_any_of[0]

        has_url = _is_non_empty_str(node_config.get("url"))
        has_path = _is_non_empty_str(node_config.get("path"))
        if not has_url and not has_path:
            _append_error(
                errors,
                code=any_of.code if any_of else "missing_url",
                message=any_of.message if any_of else "url (or path) is required for http nodes",
                path=_node_path(node_index, any_of.path if any_of else "config"),
            )

        method_req = None
        if contract:
            method_req = next(
                (req for req in contract.required_fields if req.key == "method"), None
            )
        if not _is_non_empty_str(node_config.get("method")):
            _append_error(
                errors,
                code=method_req.code if method_req else "missing_method",
                message=method_req.message if method_req else "method is required for http nodes",
                path=_node_path(node_index, method_req.path if method_req else "config.method"),
            )

        # Validate JSON fields early to avoid “save ok but executor必失败” drift.
        for field in contract.json_fields if contract else ():
            raw = node_config.get(field.key)
            if not _is_non_empty_str(raw):
                continue

            parsed = self._try_parse_json(
                cast(str, raw).strip(),
                errors=errors,
                path=_node_path(node_index, field.path),
            )
            if parsed is None or field.parsed_kind == "any":
                continue

            ok = True
            if field.parsed_kind == "object":
                ok = isinstance(parsed, dict)
            elif field.parsed_kind == "array":
                ok = isinstance(parsed, list)
            elif field.parsed_kind == "object_or_array":
                ok = isinstance(parsed, dict | list)
            elif field.parsed_kind == "array_or_string":
                ok = isinstance(parsed, list | str)
            if not ok and field.invalid_type_code and field.invalid_type_message:
                _append_error(
                    errors,
                    code=field.invalid_type_code,
                    message=field.invalid_type_message,
                    path=_node_path(node_index, field.path),
                )

    def _validate_embedding_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        contract = _EDITOR_WORKFLOW_NODE_CONTRACTS.get(NodeType.EMBEDDING.value)
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for embedding nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        model_req = None
        if contract:
            model_req = next((req for req in contract.required_fields if req.key == "model"), None)
        if not _is_non_empty_str(node_config.get("model")):
            _append_error(
                errors,
                code=model_req.code if model_req else "missing_model",
                message=model_req.message if model_req else "model is required for embedding nodes",
                path=_node_path(node_index, model_req.path if model_req else "config.model"),
            )
            return

        _validate_model_provider_contract(
            node_index=node_index,
            node_config=node_config,
            contract=contract.model_provider if contract else None,
            errors=errors,
        )

    def _validate_image_generation_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        contract = _EDITOR_WORKFLOW_NODE_CONTRACTS.get(NodeType.IMAGE.value)
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for image nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        model_req = None
        if contract:
            model_req = next((req for req in contract.required_fields if req.key == "model"), None)
        if not _is_non_empty_str(node_config.get("model")):
            _append_error(
                errors,
                code=model_req.code if model_req else "missing_model",
                message=model_req.message if model_req else "model is required for image nodes",
                path=_node_path(node_index, model_req.path if model_req else "config.model"),
            )
            return

        _validate_model_provider_contract(
            node_index=node_index,
            node_config=node_config,
            contract=contract.model_provider if contract else None,
            errors=errors,
        )

    def _validate_audio_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        contract = _EDITOR_WORKFLOW_NODE_CONTRACTS.get(NodeType.AUDIO.value)
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for audio nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        model_req = None
        if contract:
            model_req = next((req for req in contract.required_fields if req.key == "model"), None)
        if not _is_non_empty_str(node_config.get("model")):
            _append_error(
                errors,
                code=model_req.code if model_req else "missing_model",
                message=model_req.message if model_req else "model is required for audio nodes",
                path=_node_path(node_index, model_req.path if model_req else "config.model"),
            )
            return

        _validate_model_provider_contract(
            node_index=node_index,
            node_config=node_config,
            contract=contract.model_provider if contract else None,
            errors=errors,
        )

    def _validate_structured_output_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        contract = _EDITOR_WORKFLOW_NODE_CONTRACTS.get(NodeType.STRUCTURED_OUTPUT.value)
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for structured output nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        schema_name_req = None
        schema_req = None
        schema_json = None
        if contract:
            schema_name_req = next(
                (req for req in contract.required_fields if req.key == "schemaName"), None
            )
            schema_req = next(
                (req for req in contract.required_fields if req.key == "schema"), None
            )
            schema_json = next((f for f in contract.json_fields if f.key == "schema"), None)

        if schema_name_req and not _is_non_empty_str(node_config.get("schemaName")):
            _append_error(
                errors,
                code=schema_name_req.code,
                message=schema_name_req.message,
                path=_node_path(node_index, schema_name_req.path),
            )

        _validate_model_provider_contract(
            node_index=node_index,
            node_config=node_config,
            contract=contract.model_provider if contract else None,
            errors=errors,
        )

        schema_value = node_config.get("schema")
        has_schema = False
        if _is_non_empty_str(schema_value):
            has_schema = True
        elif _is_non_empty_dict(schema_value):
            has_schema = True
        if not has_schema:
            _append_error(
                errors,
                code=schema_req.code if schema_req else "missing_schema",
                message=schema_req.message
                if schema_req
                else "schema is required for structured output nodes",
                path=_node_path(node_index, schema_req.path if schema_req else "config.schema"),
            )
            return

        if _is_non_empty_str(schema_value):
            parsed = self._try_parse_json(
                cast(str, schema_value).strip(),
                errors=errors,
                path=_node_path(node_index, schema_json.path if schema_json else "config.schema"),
            )
            if (
                parsed is not None
                and schema_json is not None
                and schema_json.parsed_kind == "object"
                and not isinstance(parsed, dict)
            ):
                _append_error(
                    errors,
                    code=schema_json.invalid_type_code or "invalid_schema",
                    message=schema_json.invalid_type_message or "schema must be a JSON object",
                    path=_node_path(node_index, schema_json.path),
                )

    def _validate_tool_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        contract = _EDITOR_WORKFLOW_NODE_CONTRACTS.get(NodeType.TOOL.value)
        tool_spec = contract.tool_node if contract else None

        tool_id = _extract_tool_id(node_config)
        if tool_id is None:
            _append_error(
                errors,
                code=tool_spec.missing_tool_id_code if tool_spec else "missing_tool_id",
                message=tool_spec.missing_tool_id_message
                if tool_spec
                else "tool_id is required for tool nodes",
                path=_node_path(
                    node_index, tool_spec.tool_id_path if tool_spec else "config.tool_id"
                ),
            )
            return

        repository = self.tool_repository
        if repository is None:
            _append_error(
                errors,
                code=tool_spec.repository_unavailable_code
                if tool_spec
                else "tool_repository_unavailable",
                message=tool_spec.repository_unavailable_message
                if tool_spec
                else "tool repository is unavailable",
                path=_node_path(
                    node_index, tool_spec.tool_id_path if tool_spec else "config.tool_id"
                ),
            )
            return

        if not repository.exists(tool_id):
            _append_error(
                errors,
                code=tool_spec.not_found_code if tool_spec else "tool_not_found",
                message=(
                    tool_spec.not_found_message_template.format(tool_id=tool_id)
                    if tool_spec
                    else f"tool not found: {tool_id}"
                ),
                path=_node_path(
                    node_index, tool_spec.tool_id_path if tool_spec else "config.tool_id"
                ),
            )
            return

        tool = repository.find_by_id(tool_id)
        if tool is not None and tool.status == ToolStatus.DEPRECATED:
            _append_error(
                errors,
                code=tool_spec.deprecated_code if tool_spec else "tool_deprecated",
                message=(
                    tool_spec.deprecated_message_template.format(tool_id=tool_id)
                    if tool_spec
                    else f"tool is deprecated: {tool_id}"
                ),
                path=_node_path(
                    node_index, tool_spec.tool_id_path if tool_spec else "config.tool_id"
                ),
            )

    def _validate_text_model_node(
        self,
        *,
        node_index: int,
        node_config: dict[str, Any],
        incoming_source_node_ids: list[str],
        errors: list[dict[str, Any]],
    ) -> None:
        contract = _EDITOR_WORKFLOW_NODE_CONTRACTS.get(NodeType.TEXT_MODEL.value)
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for textModel nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        model_req = None
        if contract:
            model_req = next((req for req in contract.required_fields if req.key == "model"), None)
        if not _is_non_empty_str(node_config.get("model")):
            _append_error(
                errors,
                code=model_req.code if model_req else "missing_model",
                message=model_req.message if model_req else "model is required for textModel nodes",
                path=_node_path(node_index, model_req.path if model_req else "config.model"),
            )
        _validate_model_provider_contract(
            node_index=node_index,
            node_config=node_config,
            contract=contract.model_provider if contract else None,
            errors=errors,
        )

        prompt_contract = contract.text_model_prompt if contract else None
        prompt_value = None
        if prompt_contract:
            for key in prompt_contract.prompt_keys:
                candidate = node_config.get(key)
                if _is_non_empty_str(candidate):
                    prompt_value = candidate
                    break
        else:
            prompt_value = node_config.get("prompt") or node_config.get("user_prompt")
        has_prompt = _is_non_empty_str(prompt_value)
        if has_prompt:
            return

        incoming_count = len(incoming_source_node_ids)
        if incoming_count == 0:
            _append_error(
                errors,
                code=prompt_contract.missing_prompt_code if prompt_contract else "missing_prompt",
                message=prompt_contract.missing_prompt_message
                if prompt_contract
                else "textModel nodes must have prompt or at least one incoming edge",
                path=_node_path(
                    node_index, prompt_contract.prompt_path if prompt_contract else "config.prompt"
                ),
            )
            return

        if incoming_count == 1:
            return

        prompt_source = None
        if prompt_contract:
            for key in prompt_contract.prompt_source_keys:
                candidate = node_config.get(key)
                if _is_non_empty_str(candidate):
                    prompt_source = candidate
                    break
        else:
            prompt_source = node_config.get("promptSourceNodeId") or node_config.get("promptSource")

        if not _is_non_empty_str(prompt_source):
            _append_error(
                errors,
                code=prompt_contract.ambiguous_source_code
                if prompt_contract
                else "ambiguous_prompt_source",
                message=prompt_contract.ambiguous_source_message
                if prompt_contract
                else (
                    "textModel nodes with multiple inputs require promptSourceNodeId or a Prompt node to merge inputs"
                ),
                path=_node_path(
                    node_index,
                    prompt_contract.prompt_source_path
                    if prompt_contract
                    else "config.promptSourceNodeId",
                ),
                meta={"incoming_sources": incoming_source_node_ids},
            )
            return

        normalized_source = cast(str, prompt_source).strip()
        if normalized_source not in set(incoming_source_node_ids):
            _append_error(
                errors,
                code=prompt_contract.invalid_source_code
                if prompt_contract
                else "invalid_prompt_source",
                message=(
                    prompt_contract.invalid_source_message_template.format(source=normalized_source)
                    if prompt_contract
                    else f"promptSourceNodeId not found in incoming sources: {normalized_source}"
                ),
                path=_node_path(
                    node_index,
                    prompt_contract.prompt_source_path
                    if prompt_contract
                    else "config.promptSourceNodeId",
                ),
                meta={"incoming_sources": incoming_source_node_ids},
            )

    def _validate_prompt_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        contract = _EDITOR_WORKFLOW_NODE_CONTRACTS.get(NodeType.PROMPT.value)
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for prompt nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        content_req = None
        if contract:
            content_req = next(
                (req for req in contract.required_fields if req.key == "content"), None
            )
        if not _is_non_empty_str(node_config.get("content")):
            _append_error(
                errors,
                code=content_req.code if content_req else "missing_content",
                message=content_req.message
                if content_req
                else "content is required for prompt nodes",
                path=_node_path(node_index, content_req.path if content_req else "config.content"),
            )

    def _validate_conditional_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        contract = _EDITOR_WORKFLOW_NODE_CONTRACTS.get(NodeType.CONDITIONAL.value)
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for conditional nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        condition_req = None
        if contract:
            condition_req = next(
                (req for req in contract.required_fields if req.key == "condition"), None
            )
        if not _is_non_empty_str(node_config.get("condition")):
            _append_error(
                errors,
                code=condition_req.code if condition_req else "missing_condition",
                message=condition_req.message
                if condition_req
                else "condition is required for conditional nodes",
                path=_node_path(
                    node_index, condition_req.path if condition_req else "config.condition"
                ),
            )

    def _validate_loop_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        contract = _EDITOR_WORKFLOW_NODE_CONTRACTS.get(NodeType.LOOP.value)
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for loop nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        type_req = contract.required_fields[0] if contract and contract.required_fields else None
        raw_type = node_config.get("type")
        if not _is_non_empty_str(raw_type):
            _append_error(
                errors,
                code=type_req.code if type_req else "missing_type",
                message=type_req.message if type_req else "type is required for loop nodes",
                path=_node_path(node_index, type_req.path if type_req else "config.type"),
            )
            return

        normalized_type = cast(str, raw_type).strip()
        # Back-compat: UI 曾使用 `for`，runtime 以 `range` 为准。
        if normalized_type == "for":
            normalized_type = "range"

        enum_spec = None
        if contract:
            enum_spec = next((spec for spec in contract.enum_fields if spec.key == "type"), None)
        supported_types = {"for_each", "range", "while"}
        if normalized_type not in supported_types:
            _append_error(
                errors,
                code=enum_spec.code if enum_spec else "unsupported_loop_type",
                message=(
                    enum_spec.message.format(value=raw_type)
                    if enum_spec
                    else f"unsupported loop type: {raw_type}"
                ),
                path=_node_path(node_index, enum_spec.path if enum_spec else "config.type"),
            )
            return

        conditional_map = (
            {c.when_equals: c for c in contract.conditional_required} if contract else {}
        )

        if normalized_type == "for_each":
            for_each_cond = conditional_map.get("for_each")
            reqs = for_each_cond.required_fields if for_each_cond else ()
            for req in reqs:
                if req.kind == "string" and not _is_non_empty_str(node_config.get(req.key)):
                    _append_error(
                        errors,
                        code=req.code,
                        message=req.message,
                        path=_node_path(node_index, req.path),
                    )

        if normalized_type == "range":
            range_cond = conditional_map.get("range")
            reqs = range_cond.required_fields if range_cond else ()
            end_req = next((r for r in reqs if r.key == "end"), None)
            code_req = next((r for r in reqs if r.key == "code"), None)

            end_value = node_config.get("end")
            if end_value is None:
                end_value = node_config.get("iterations")
            if end_value is None:
                _append_error(
                    errors,
                    code=end_req.code if end_req else "missing_end",
                    message=end_req.message
                    if end_req
                    else "end (or iterations) is required for range loop",
                    path=_node_path(node_index, end_req.path if end_req else "config.end"),
                )
            elif not (
                (isinstance(end_value, int) and not isinstance(end_value, bool))
                or (isinstance(end_value, str) and end_value.strip().isdigit())
            ):
                _append_error(
                    errors,
                    code="invalid_end",
                    message="end (or iterations) must be an integer",
                    path=_node_path(node_index, "config.end"),
                )

            if code_req and not _is_non_empty_str(node_config.get("code")):
                _append_error(
                    errors,
                    code=code_req.code,
                    message=code_req.message,
                    path=_node_path(node_index, code_req.path),
                )

        if normalized_type == "while":
            while_cond = conditional_map.get("while")
            reqs = while_cond.required_fields if while_cond else ()
            for req in reqs:
                if req.kind == "string" and not _is_non_empty_str(node_config.get(req.key)):
                    _append_error(
                        errors,
                        code=req.code,
                        message=req.message,
                        path=_node_path(node_index, req.path),
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
                    path=_node_path(node_index, "config.max_iterations"),
                )

    def _validate_database_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        contract = _EDITOR_WORKFLOW_NODE_CONTRACTS.get(NodeType.DATABASE.value)
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for database nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        sql_req = None
        if contract:
            sql_req = next((req for req in contract.required_fields if req.key == "sql"), None)
        if not _is_non_empty_str(node_config.get("sql")):
            _append_error(
                errors,
                code=sql_req.code if sql_req else "missing_sql",
                message=sql_req.message if sql_req else "sql is required for database nodes",
                path=_node_path(node_index, sql_req.path if sql_req else "config.sql"),
            )

        db_url_spec = contract.database_url if contract else None
        database_url = node_config.get(db_url_spec.key if db_url_spec else "database_url")
        if database_url is None:
            # Keep executor default but persist a canonical value to avoid drift.
            node_config[db_url_spec.key if db_url_spec else "database_url"] = (
                db_url_spec.default_value if db_url_spec else DEFAULT_SQLITE_DATABASE_URL
            )
        elif not _is_non_empty_str(database_url):
            _append_error(
                errors,
                code=db_url_spec.missing_code if db_url_spec else "missing_database_url",
                message=db_url_spec.missing_message
                if db_url_spec
                else "database_url is required for database nodes",
                path=_node_path(
                    node_index, db_url_spec.path if db_url_spec else "config.database_url"
                ),
            )
        else:
            normalized_url = database_url.strip()
            node_config[db_url_spec.key if db_url_spec else "database_url"] = normalized_url
            supported_prefix = (
                db_url_spec.supported_prefix if db_url_spec else SQLITE_DATABASE_URL_PREFIX
            )
            if not normalized_url.startswith(supported_prefix):
                _append_error(
                    errors,
                    code=db_url_spec.unsupported_code
                    if db_url_spec
                    else "unsupported_database_url",
                    message=db_url_spec.unsupported_message
                    if db_url_spec
                    else "only sqlite:/// database_url is supported",
                    path=_node_path(
                        node_index, db_url_spec.path if db_url_spec else "config.database_url"
                    ),
                    meta={"supported_prefix": supported_prefix},
                )

        params_spec = None
        if contract:
            params_spec = next((f for f in contract.json_fields if f.key == "params"), None)
        params_value = node_config.get("params")
        if _is_non_empty_str(params_value):
            parsed = self._try_parse_json(
                cast(str, params_value).strip(),
                errors=errors,
                path=_node_path(node_index, params_spec.path if params_spec else "config.params"),
            )
            if (
                parsed is not None
                and params_spec is not None
                and params_spec.parsed_kind == "object_or_array"
                and not isinstance(parsed, dict | list)
            ):
                _append_error(
                    errors,
                    code=params_spec.invalid_type_code or "invalid_params",
                    message=params_spec.invalid_type_message
                    or "params must be a JSON object or array",
                    path=_node_path(node_index, params_spec.path),
                )

    def _validate_file_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        contract = _EDITOR_WORKFLOW_NODE_CONTRACTS.get(NodeType.FILE.value)
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for file nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        op_req = None
        path_req = None
        enum_spec = None
        if contract:
            op_req = next((req for req in contract.required_fields if req.key == "operation"), None)
            path_req = next((req for req in contract.required_fields if req.key == "path"), None)
            enum_spec = next(
                (spec for spec in contract.enum_fields if spec.key == "operation"), None
            )

        operation = node_config.get("operation")
        if not _is_non_empty_str(operation):
            _append_error(
                errors,
                code=op_req.code if op_req else "missing_operation",
                message=op_req.message if op_req else "operation is required for file nodes",
                path=_node_path(node_index, op_req.path if op_req else "config.operation"),
            )
            return

        normalized_operation = _normalize_string(
            operation, normalize=enum_spec.normalize if enum_spec else "lower_strip"
        )
        allowed = set(enum_spec.allowed) if enum_spec else set()
        if normalized_operation is not None and allowed and normalized_operation not in allowed:
            _append_error(
                errors,
                code=enum_spec.code if enum_spec else "unsupported_operation",
                message=(
                    enum_spec.message.format(value=operation)
                    if enum_spec
                    else f"unsupported file operation: {operation}"
                ),
                path=_node_path(node_index, enum_spec.path if enum_spec else "config.operation"),
                meta=enum_spec.meta if enum_spec else None,
            )

        if not _is_non_empty_str(node_config.get("path")):
            _append_error(
                errors,
                code=path_req.code if path_req else "missing_path",
                message=path_req.message if path_req else "path is required for file nodes",
                path=_node_path(node_index, path_req.path if path_req else "config.path"),
            )

    def _validate_notification_node(
        self, *, node_index: int, node_config: dict[str, Any], errors: list[dict[str, Any]]
    ) -> None:
        contract = _EDITOR_WORKFLOW_NODE_CONTRACTS.get(NodeType.NOTIFICATION.value)
        if not isinstance(node_config, dict):
            _append_error(
                errors,
                code="invalid_config",
                message="config must be an object for notification nodes",
                path=f"nodes[{node_index}].config",
            )
            return

        type_req = None
        message_req = None
        type_enum = None
        headers_json = None
        recipients_json = None
        webhook_req = None
        slack_req = None
        email_reqs: dict[str, Any] = {}
        if contract:
            type_req = next((req for req in contract.required_fields if req.key == "type"), None)
            message_req = next(
                (req for req in contract.required_fields if req.key == "message"), None
            )
            type_enum = next((spec for spec in contract.enum_fields if spec.key == "type"), None)
            headers_json = next(
                (spec for spec in contract.json_fields if spec.key == "headers"), None
            )
            recipients_json = next(
                (spec for spec in contract.json_fields if spec.key == "recipients"), None
            )
            for conditional in contract.conditional_required:
                if conditional.when_equals == "webhook":
                    webhook_req = next(iter(conditional.required_fields), None)
                if conditional.when_equals == "slack":
                    slack_req = next(iter(conditional.required_fields), None)
                if conditional.when_equals == "email":
                    email_reqs = {req.key: req for req in conditional.required_fields}

        notification_type = node_config.get("type")
        if not _is_non_empty_str(notification_type):
            _append_error(
                errors,
                code=type_req.code if type_req else "missing_type",
                message=type_req.message if type_req else "type is required for notification nodes",
                path=_node_path(node_index, type_req.path if type_req else "config.type"),
            )
            return

        if not _is_non_empty_str(node_config.get("message")):
            _append_error(
                errors,
                code=message_req.code if message_req else "missing_message",
                message=message_req.message
                if message_req
                else "message is required for notification nodes",
                path=_node_path(node_index, message_req.path if message_req else "config.message"),
            )

        # Optional JSON fields
        headers_value = node_config.get("headers")
        if _is_non_empty_str(headers_value):
            parsed = self._try_parse_json(
                cast(str, headers_value).strip(),
                errors=errors,
                path=_node_path(
                    node_index, headers_json.path if headers_json else "config.headers"
                ),
            )
            if (
                parsed is not None
                and headers_json is not None
                and headers_json.parsed_kind == "object"
                and not isinstance(parsed, dict)
            ):
                _append_error(
                    errors,
                    code=headers_json.invalid_type_code or "invalid_headers",
                    message=headers_json.invalid_type_message or "headers must be a JSON object",
                    path=_node_path(node_index, headers_json.path),
                )

        normalized_type = cast(str, notification_type).strip().lower()
        allowed_types = set(type_enum.allowed) if type_enum else {"webhook", "slack", "email"}
        if normalized_type not in allowed_types:
            _append_error(
                errors,
                code=type_enum.code if type_enum else "unsupported_notification_type",
                message=(
                    type_enum.message.format(value=notification_type)
                    if type_enum
                    else f"unsupported notification type: {notification_type}"
                ),
                path=_node_path(node_index, type_enum.path if type_enum else "config.type"),
            )
            return

        if normalized_type == "webhook":
            if webhook_req and not _is_non_empty_str(node_config.get(webhook_req.key)):
                _append_error(
                    errors,
                    code=webhook_req.code,
                    message=webhook_req.message,
                    path=_node_path(node_index, webhook_req.path),
                )
            return

        if normalized_type == "slack":
            if slack_req and not _is_non_empty_str(node_config.get(slack_req.key)):
                _append_error(
                    errors,
                    code=slack_req.code,
                    message=slack_req.message,
                    path=_node_path(node_index, slack_req.path),
                )
            return

        # email
        for key in ("smtp_host", "sender", "sender_password"):
            req = email_reqs.get(key)
            if req and not _is_non_empty_str(node_config.get(key)):
                _append_error(
                    errors,
                    code=req.code,
                    message=req.message,
                    path=_node_path(node_index, req.path),
                )

        recipients = node_config.get("recipients")
        recipients_req = email_reqs.get("recipients")
        if recipients is None:
            if recipients_req:
                _append_error(
                    errors,
                    code=recipients_req.code,
                    message=recipients_req.message,
                    path=_node_path(node_index, recipients_req.path),
                )
            return

        if isinstance(recipients, str):
            raw = recipients.strip()
            if not raw:
                if recipients_req:
                    _append_error(
                        errors,
                        code=recipients_req.code,
                        message=recipients_req.message,
                        path=_node_path(node_index, recipients_req.path),
                    )
                return

            if (
                recipients_json
                and recipients_json.parse_when_startswith
                and raw.startswith(recipients_json.parse_when_startswith)
            ):
                parsed = self._try_parse_json(
                    raw,
                    errors=errors,
                    path=_node_path(node_index, recipients_json.path),
                )
                if parsed is not None and not isinstance(parsed, list | str):
                    _append_error(
                        errors,
                        code=recipients_json.invalid_type_code or "invalid_recipients",
                        message=recipients_json.invalid_type_message
                        or "recipients must be a JSON array or string",
                        path=_node_path(node_index, recipients_json.path),
                    )
            return

        if isinstance(recipients, list):
            if not recipients and recipients_req:
                _append_error(
                    errors,
                    code=recipients_req.code,
                    message=recipients_req.message,
                    path=_node_path(node_index, recipients_req.path),
                )
            return

        if recipients_json:
            _append_error(
                errors,
                code=recipients_json.invalid_type_code or "invalid_recipients",
                message=recipients_json.invalid_type_message
                or "recipients must be a JSON array or string",
                path=_node_path(node_index, recipients_json.path),
            )

    def _validate_requires_text_input_or_incoming_edge(
        self,
        *,
        node_index: int,
        node_config: dict[str, Any],
        config_input_keys: tuple[str, ...],
        incoming_source_node_ids: list[str],
        errors: list[dict[str, Any]],
        code: str = "missing_input",
        message: str = "node must have config input or at least one incoming edge",
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
                code=code,
                message=message,
                path=_node_path(node_index, "config"),
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
