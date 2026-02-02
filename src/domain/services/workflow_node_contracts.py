"""Workflow node contracts for the *editor workflow* chain (SoT).

Single source of truth for:
- Save-time fail-closed validation (`WorkflowSaveValidator`)
- Machine-consumable capabilities output (`GET /api/workflows/capabilities`)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from src.domain.value_objects.node_type import NodeType

# Endpoint schema versioning (independent from app version).
CAPABILITIES_SCHEMA_VERSION = "2026-02-01/v1"

SQLITE_DATABASE_URL_PREFIX = "sqlite:///"
DEFAULT_SQLITE_DATABASE_URL = "sqlite:///agent_data.db"

# Model provider contract: currently fail-closed to OpenAI only.
SUPPORTED_MODEL_PROVIDERS: tuple[str, ...] = ("openai",)
# High-signal tokens for “unprefixed but clearly non-OpenAI model families”.
NON_OPENAI_MODEL_TOKENS: tuple[str, ...] = ("claude", "anthropic", "gemini", "google", "cohere")

FieldKind = Literal[
    "string",  # non-empty str
    "object",  # non-empty dict
    "array",  # non-empty list
    "string_or_object",  # str or dict, non-empty
    "string_or_array",  # str or list, non-empty
    "int_or_string_digits",  # int (not bool) or str digits
]

JsonParsedKind = Literal[
    "any",
    "object",
    "array",
    "object_or_array",
    "array_or_string",
]

NormalizeStrategy = Literal["strip", "lower_strip"]


@dataclass(frozen=True, slots=True)
class FieldRequirement:
    key: str
    kind: FieldKind
    code: str
    message: str
    # Relative to `nodes[{i}].` (e.g. "config.model", "config").
    path: str


@dataclass(frozen=True, slots=True)
class AnyOfRequirement:
    keys: tuple[str, ...]
    code: str
    message: str
    path: str


@dataclass(frozen=True, slots=True)
class EnumFieldRequirement:
    key: str
    allowed: tuple[str, ...]
    code: str
    message: str
    path: str
    normalize: NormalizeStrategy = "strip"
    meta: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class JsonFieldRequirement:
    key: str
    path: str
    parsed_kind: JsonParsedKind = "any"
    invalid_type_code: str | None = None
    invalid_type_message: str | None = None
    # Some fields only parse JSON when the string looks like JSON (e.g. recipients).
    parse_when_startswith: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class ConditionalRequired:
    when_key: str
    when_equals: str
    normalize: NormalizeStrategy = "strip"
    required_fields: tuple[FieldRequirement, ...] = ()


@dataclass(frozen=True, slots=True)
class ModelProviderContract:
    model_key: str = "model"
    allowed_providers: tuple[str, ...] = SUPPORTED_MODEL_PROVIDERS
    unsupported_provider_code: str = "unsupported_model_provider"
    unsupported_provider_message: str = "only openai provider is supported"
    unsupported_model_code: str = "unsupported_model"
    unsupported_model_message_template: str = "unsupported model: {model}"
    # If a model string has no explicit provider prefix, block clearly non-OpenAI families.
    block_unprefixed_non_openai_families: bool = True
    non_openai_tokens: tuple[str, ...] = NON_OPENAI_MODEL_TOKENS
    # Always-block substrings (even if provider prefix is present).
    block_model_substrings_anywhere: tuple[str, ...] = ()
    model_optional: bool = False


@dataclass(frozen=True, slots=True)
class RequiresInputOrIncomingEdgeContract:
    config_input_keys: tuple[str, ...]
    code: str
    message: str
    path: str = "config"


@dataclass(frozen=True, slots=True)
class TextModelPromptContract:
    prompt_keys: tuple[str, ...] = ("prompt", "user_prompt")
    prompt_source_keys: tuple[str, ...] = ("promptSourceNodeId", "promptSource")
    missing_prompt_code: str = "missing_prompt"
    missing_prompt_message: str = "textModel nodes must have prompt or at least one incoming edge"
    ambiguous_source_code: str = "ambiguous_prompt_source"
    ambiguous_source_message: str = (
        "textModel nodes with multiple inputs require promptSourceNodeId "
        "or a Prompt node to merge inputs"
    )
    invalid_source_code: str = "invalid_prompt_source"
    invalid_source_message_template: str = (
        "promptSourceNodeId not found in incoming sources: {source}"
    )
    prompt_path: str = "config.prompt"
    prompt_source_path: str = "config.promptSourceNodeId"


@dataclass(frozen=True, slots=True)
class DatabaseUrlContract:
    key: str = "database_url"
    default_value: str = DEFAULT_SQLITE_DATABASE_URL
    supported_prefix: str = SQLITE_DATABASE_URL_PREFIX
    missing_code: str = "missing_database_url"
    missing_message: str = "database_url is required for database nodes"
    unsupported_code: str = "unsupported_database_url"
    unsupported_message: str = "only sqlite:/// database_url is supported"
    path: str = "config.database_url"


@dataclass(frozen=True, slots=True)
class ToolNodeContract:
    tool_id_keys: tuple[str, ...] = ("tool_id", "toolId")
    missing_tool_id_code: str = "missing_tool_id"
    missing_tool_id_message: str = "tool_id is required for tool nodes"
    tool_id_path: str = "config.tool_id"
    repository_unavailable_code: str = "tool_repository_unavailable"
    repository_unavailable_message: str = "tool repository is unavailable"
    not_found_code: str = "tool_not_found"
    not_found_message_template: str = "tool not found: {tool_id}"
    deprecated_code: str = "tool_deprecated"
    deprecated_message_template: str = "tool is deprecated: {tool_id}"


@dataclass(frozen=True, slots=True)
class NodeContract:
    type: str
    aliases: tuple[str, ...] = ()

    # Generic validation contract (capabilities + validator share these).
    required_fields: tuple[FieldRequirement, ...] = ()
    required_any_of: tuple[AnyOfRequirement, ...] = ()
    enum_fields: tuple[EnumFieldRequirement, ...] = ()
    json_fields: tuple[JsonFieldRequirement, ...] = ()
    conditional_required: tuple[ConditionalRequired, ...] = ()

    model_provider: ModelProviderContract | None = None
    requires_input_or_incoming_edge: RequiresInputOrIncomingEdgeContract | None = None
    text_model_prompt: TextModelPromptContract | None = None
    database_url: DatabaseUrlContract | None = None
    tool_node: ToolNodeContract | None = None

    runtime_notes: tuple[str, ...] = ()


def _editor_workflow_contracts() -> dict[str, NodeContract]:
    """Return canonical editor-workflow contracts (UI palette SoT)."""

    # Canonical types must match UI palette (web/src/features/workflows/utils/nodeUtils.ts).
    return {
        NodeType.START.value: NodeContract(type=NodeType.START.value),
        NodeType.END.value: NodeContract(type=NodeType.END.value),
        NodeType.HTTP_REQUEST.value: NodeContract(
            type=NodeType.HTTP_REQUEST.value,
            aliases=(NodeType.HTTP.value,),
            required_fields=(
                FieldRequirement(
                    key="method",
                    kind="string",
                    code="missing_method",
                    message="method is required for http nodes",
                    path="config.method",
                ),
            ),
            enum_fields=(
                EnumFieldRequirement(
                    key="method",
                    allowed=("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"),
                    code="unsupported_method",
                    message="unsupported http method: {value}",
                    path="config.method",
                    normalize="strip",
                    meta={
                        "labels": {
                            "GET": "GET",
                            "POST": "POST",
                            "PUT": "PUT",
                            "DELETE": "DELETE",
                            "PATCH": "PATCH",
                            "HEAD": "HEAD",
                            "OPTIONS": "OPTIONS",
                        }
                    },
                ),
            ),
            required_any_of=(
                AnyOfRequirement(
                    keys=("url", "path"),
                    code="missing_url",
                    message="url (or path) is required for http nodes",
                    path="config",
                ),
            ),
            json_fields=(
                JsonFieldRequirement(
                    key="headers",
                    path="config.headers",
                    parsed_kind="object",
                    invalid_type_code="invalid_headers",
                    invalid_type_message="headers must be a JSON object",
                ),
                JsonFieldRequirement(key="body", path="config.body", parsed_kind="any"),
                JsonFieldRequirement(
                    key="mock_response",
                    path="config.mock_response",
                    parsed_kind="any",
                ),
            ),
            runtime_notes=(
                "Accepts legacy `path`, but it is normalized to `url` before persisting.",
                "`headers/body/mock_response` may be provided as JSON strings; invalid JSON is rejected.",
            ),
        ),
        NodeType.TEXT_MODEL.value: NodeContract(
            type=NodeType.TEXT_MODEL.value,
            aliases=(NodeType.LLM.value,),
            required_fields=(
                FieldRequirement(
                    key="model",
                    kind="string",
                    code="missing_model",
                    message="model is required for textModel nodes",
                    path="config.model",
                ),
            ),
            enum_fields=(
                EnumFieldRequirement(
                    key="model",
                    allowed=("openai/gpt-5", "openai/gpt-4"),
                    code="unsupported_model",
                    message="unsupported textModel model: {value}",
                    path="config.model",
                    normalize="strip",
                    meta={
                        "labels": {
                            "openai/gpt-5": "OpenAI GPT-5",
                            "openai/gpt-4": "OpenAI GPT-4",
                        }
                    },
                ),
            ),
            model_provider=ModelProviderContract(
                unsupported_provider_message="only openai provider is supported for textModel",
                unsupported_model_message_template="unsupported textModel model: {model}",
            ),
            text_model_prompt=TextModelPromptContract(),
            runtime_notes=(
                "If `prompt`/`user_prompt` is empty, at least 1 incoming edge is required.",
                "If incoming edges > 1, `promptSourceNodeId` must point to one incoming source.",
            ),
        ),
        NodeType.CONDITIONAL.value: NodeContract(
            type=NodeType.CONDITIONAL.value,
            aliases=(NodeType.CONDITION.value,),
            required_fields=(
                FieldRequirement(
                    key="condition",
                    kind="string",
                    code="missing_condition",
                    message="condition is required for conditional nodes",
                    path="config.condition",
                ),
            ),
        ),
        NodeType.JAVASCRIPT.value: NodeContract(
            type=NodeType.JAVASCRIPT.value,
            required_fields=(
                FieldRequirement(
                    key="code",
                    kind="string",
                    code="missing_code",
                    message="code is required for code nodes",
                    path="config.code",
                ),
            ),
        ),
        NodeType.PYTHON.value: NodeContract(
            type=NodeType.PYTHON.value,
            required_fields=(
                FieldRequirement(
                    key="code",
                    kind="string",
                    code="missing_code",
                    message="code is required for code nodes",
                    path="config.code",
                ),
            ),
        ),
        NodeType.PROMPT.value: NodeContract(
            type=NodeType.PROMPT.value,
            required_fields=(
                FieldRequirement(
                    key="content",
                    kind="string",
                    code="missing_content",
                    message="content is required for prompt nodes",
                    path="config.content",
                ),
            ),
        ),
        NodeType.TRANSFORM.value: NodeContract(
            type=NodeType.TRANSFORM.value,
            required_fields=(
                FieldRequirement(
                    key="type",
                    kind="string",
                    code="missing_transform_type",
                    message="type is required for transform nodes",
                    path="config.type",
                ),
            ),
            enum_fields=(
                EnumFieldRequirement(
                    key="type",
                    allowed=(
                        "field_mapping",
                        "type_conversion",
                        "field_extraction",
                        "array_mapping",
                        "filtering",
                        "aggregation",
                        "custom",
                    ),
                    code="unsupported_transform_type",
                    message="unsupported transform type: {value}",
                    path="config.type",
                    normalize="strip",
                ),
            ),
            conditional_required=(
                ConditionalRequired(
                    when_key="type",
                    when_equals="field_mapping",
                    required_fields=(
                        FieldRequirement(
                            key="mapping",
                            kind="object",
                            code="missing_mapping",
                            message="mapping is required for field_mapping transform",
                            path="config.mapping",
                        ),
                    ),
                ),
                ConditionalRequired(
                    when_key="type",
                    when_equals="type_conversion",
                    required_fields=(
                        FieldRequirement(
                            key="conversions",
                            kind="object",
                            code="missing_conversions",
                            message="conversions is required for type_conversion transform",
                            path="config.conversions",
                        ),
                    ),
                ),
                ConditionalRequired(
                    when_key="type",
                    when_equals="field_extraction",
                    required_fields=(
                        FieldRequirement(
                            key="path",
                            kind="string",
                            code="missing_path",
                            message="path is required for field_extraction transform",
                            path="config.path",
                        ),
                    ),
                ),
                ConditionalRequired(
                    when_key="type",
                    when_equals="array_mapping",
                    required_fields=(
                        FieldRequirement(
                            key="field",
                            kind="string",
                            code="missing_field",
                            message="field is required for array_mapping transform",
                            path="config.field",
                        ),
                        FieldRequirement(
                            key="mapping",
                            kind="object",
                            code="missing_mapping",
                            message="mapping is required for array_mapping transform",
                            path="config.mapping",
                        ),
                    ),
                ),
                ConditionalRequired(
                    when_key="type",
                    when_equals="filtering",
                    required_fields=(
                        FieldRequirement(
                            key="field",
                            kind="string",
                            code="missing_field",
                            message="field is required for filtering transform",
                            path="config.field",
                        ),
                        FieldRequirement(
                            key="condition",
                            kind="string",
                            code="missing_condition",
                            message="condition is required for filtering transform",
                            path="config.condition",
                        ),
                    ),
                ),
                ConditionalRequired(
                    when_key="type",
                    when_equals="aggregation",
                    required_fields=(
                        FieldRequirement(
                            key="field",
                            kind="string",
                            code="missing_field",
                            message="field is required for aggregation transform",
                            path="config.field",
                        ),
                        FieldRequirement(
                            key="operations",
                            kind="array",
                            code="missing_operations",
                            message="operations is required for aggregation transform",
                            path="config.operations",
                        ),
                    ),
                ),
                ConditionalRequired(
                    when_key="type",
                    when_equals="custom",
                    required_fields=(
                        FieldRequirement(
                            key="function",
                            kind="string",
                            code="missing_function",
                            message="function is required for custom transform",
                            path="config.function",
                        ),
                    ),
                ),
            ),
        ),
        NodeType.LOOP.value: NodeContract(
            type=NodeType.LOOP.value,
            required_fields=(
                FieldRequirement(
                    key="type",
                    kind="string",
                    code="missing_type",
                    message="type is required for loop nodes",
                    path="config.type",
                ),
            ),
            enum_fields=(
                EnumFieldRequirement(
                    key="type",
                    allowed=("for_each", "range", "while", "for"),
                    code="unsupported_loop_type",
                    message="unsupported loop type: {value}",
                    path="config.type",
                    normalize="strip",
                ),
            ),
            conditional_required=(
                ConditionalRequired(
                    when_key="type",
                    when_equals="for_each",
                    required_fields=(
                        FieldRequirement(
                            key="array",
                            kind="string",
                            code="missing_array",
                            message="array is required for for_each loop",
                            path="config.array",
                        ),
                    ),
                ),
                # Note: `for` is normalized to `range` in save normalization; validator still treats it as range.
                ConditionalRequired(
                    when_key="type",
                    when_equals="range",
                    required_fields=(
                        FieldRequirement(
                            key="end",
                            kind="int_or_string_digits",
                            code="missing_end",
                            message="end (or iterations) is required for range loop",
                            path="config.end",
                        ),
                        FieldRequirement(
                            key="code",
                            kind="string",
                            code="missing_code",
                            message="code is required for range loop",
                            path="config.code",
                        ),
                    ),
                ),
                ConditionalRequired(
                    when_key="type",
                    when_equals="while",
                    required_fields=(
                        FieldRequirement(
                            key="condition",
                            kind="string",
                            code="missing_condition",
                            message="condition is required for while loop",
                            path="config.condition",
                        ),
                        FieldRequirement(
                            key="code",
                            kind="string",
                            code="missing_code",
                            message="code is required for while loop",
                            path="config.code",
                        ),
                    ),
                ),
            ),
            runtime_notes=(
                'Back-compat: `type="for"` is normalized to `type="range"`.',
                "Back-compat: `iterations` is normalized to `end` for range loops.",
            ),
        ),
        NodeType.DATABASE.value: NodeContract(
            type=NodeType.DATABASE.value,
            required_fields=(
                FieldRequirement(
                    key="sql",
                    kind="string",
                    code="missing_sql",
                    message="sql is required for database nodes",
                    path="config.sql",
                ),
            ),
            database_url=DatabaseUrlContract(),
            json_fields=(
                JsonFieldRequirement(
                    key="params",
                    path="config.params",
                    parsed_kind="object_or_array",
                    invalid_type_code="invalid_params",
                    invalid_type_message="params must be a JSON object or array",
                ),
            ),
            runtime_notes=(
                f"Only `{SQLITE_DATABASE_URL_PREFIX}` database_url is supported (fail-closed).",
                f"If database_url is missing, it is normalized to `{DEFAULT_SQLITE_DATABASE_URL}`.",
            ),
        ),
        NodeType.FILE.value: NodeContract(
            type=NodeType.FILE.value,
            required_fields=(
                FieldRequirement(
                    key="operation",
                    kind="string",
                    code="missing_operation",
                    message="operation is required for file nodes",
                    path="config.operation",
                ),
                FieldRequirement(
                    key="path",
                    kind="string",
                    code="missing_path",
                    message="path is required for file nodes",
                    path="config.path",
                ),
            ),
            enum_fields=(
                EnumFieldRequirement(
                    key="operation",
                    allowed=("read", "write", "append", "delete", "list"),
                    code="unsupported_operation",
                    message="unsupported file operation: {value}",
                    path="config.operation",
                    normalize="lower_strip",
                    meta={"allowed": ["append", "delete", "list", "read", "write"]},
                ),
            ),
        ),
        NodeType.NOTIFICATION.value: NodeContract(
            type=NodeType.NOTIFICATION.value,
            required_fields=(
                FieldRequirement(
                    key="type",
                    kind="string",
                    code="missing_type",
                    message="type is required for notification nodes",
                    path="config.type",
                ),
                FieldRequirement(
                    key="message",
                    kind="string",
                    code="missing_message",
                    message="message is required for notification nodes",
                    path="config.message",
                ),
            ),
            enum_fields=(
                EnumFieldRequirement(
                    key="type",
                    allowed=("webhook", "slack", "email"),
                    code="unsupported_notification_type",
                    message="unsupported notification type: {value}",
                    path="config.type",
                    normalize="lower_strip",
                ),
            ),
            conditional_required=(
                ConditionalRequired(
                    when_key="type",
                    when_equals="webhook",
                    normalize="lower_strip",
                    required_fields=(
                        FieldRequirement(
                            key="url",
                            kind="string",
                            code="missing_url",
                            message="url is required for webhook notification",
                            path="config.url",
                        ),
                    ),
                ),
                ConditionalRequired(
                    when_key="type",
                    when_equals="slack",
                    normalize="lower_strip",
                    required_fields=(
                        FieldRequirement(
                            key="webhook_url",
                            kind="string",
                            code="missing_webhook_url",
                            message="webhook_url is required for slack notification",
                            path="config.webhook_url",
                        ),
                    ),
                ),
                ConditionalRequired(
                    when_key="type",
                    when_equals="email",
                    normalize="lower_strip",
                    required_fields=(
                        FieldRequirement(
                            key="smtp_host",
                            kind="string",
                            code="missing_smtp_host",
                            message="smtp_host is required for email notification",
                            path="config.smtp_host",
                        ),
                        FieldRequirement(
                            key="sender",
                            kind="string",
                            code="missing_sender",
                            message="sender is required for email notification",
                            path="config.sender",
                        ),
                        FieldRequirement(
                            key="sender_password",
                            kind="string",
                            code="missing_sender_password",
                            message="sender_password is required for email notification",
                            path="config.sender_password",
                        ),
                        FieldRequirement(
                            key="recipients",
                            kind="string_or_array",
                            code="missing_recipients",
                            message="recipients is required for email notification",
                            path="config.recipients",
                        ),
                    ),
                ),
            ),
            json_fields=(
                JsonFieldRequirement(
                    key="headers",
                    path="config.headers",
                    parsed_kind="object",
                    invalid_type_code="invalid_headers",
                    invalid_type_message="headers must be a JSON object",
                ),
                JsonFieldRequirement(
                    key="recipients",
                    path="config.recipients",
                    parsed_kind="array_or_string",
                    invalid_type_code="invalid_recipients",
                    invalid_type_message="recipients must be a JSON array or string",
                    parse_when_startswith=("[", '"'),
                ),
            ),
        ),
        NodeType.TOOL.value: NodeContract(
            type=NodeType.TOOL.value,
            required_fields=(
                FieldRequirement(
                    key="tool_id",
                    kind="string",
                    code="missing_tool_id",
                    message="tool_id is required for tool nodes",
                    path="config.tool_id",
                ),
            ),
            tool_node=ToolNodeContract(),
            runtime_notes=(
                "Requires tool repository + a persisted Tool referenced by stable `tool_id`.",
                "Save-time validation fail-closed: missing tool repository or unknown tool_id is rejected.",
            ),
        ),
        NodeType.EMBEDDING.value: NodeContract(
            type=NodeType.EMBEDDING.value,
            required_fields=(
                FieldRequirement(
                    key="model",
                    kind="string",
                    code="missing_model",
                    message="model is required for embedding nodes",
                    path="config.model",
                ),
            ),
            enum_fields=(
                EnumFieldRequirement(
                    key="model",
                    allowed=("openai/text-embedding-3-small", "openai/text-embedding-3-large"),
                    code="unsupported_model",
                    message="unsupported embeddingModel model: {value}",
                    path="config.model",
                    normalize="strip",
                    meta={
                        "labels": {
                            "openai/text-embedding-3-small": "OpenAI Text Embedding 3 Small",
                            "openai/text-embedding-3-large": "OpenAI Text Embedding 3 Large",
                        }
                    },
                ),
            ),
            model_provider=ModelProviderContract(
                unsupported_provider_message="only openai provider is supported for embeddingModel",
                unsupported_model_message_template="unsupported embeddingModel model: {model}",
            ),
            requires_input_or_incoming_edge=RequiresInputOrIncomingEdgeContract(
                config_input_keys=("input", "text", "prompt", "content"),
                code="missing_input",
                message="embedding nodes must have config input or at least one incoming edge",
            ),
        ),
        NodeType.IMAGE.value: NodeContract(
            type=NodeType.IMAGE.value,
            required_fields=(
                FieldRequirement(
                    key="model",
                    kind="string",
                    code="missing_model",
                    message="model is required for image nodes",
                    path="config.model",
                ),
            ),
            enum_fields=(
                EnumFieldRequirement(
                    key="model",
                    allowed=("openai/dall-e-3",),
                    code="unsupported_model",
                    message="unsupported imageGeneration model: {value}",
                    path="config.model",
                    normalize="strip",
                    meta={"labels": {"openai/dall-e-3": "DALL-E 3"}},
                ),
                EnumFieldRequirement(
                    key="aspectRatio",
                    allowed=("1:1", "16:9", "9:16"),
                    code="unsupported_aspect_ratio",
                    message="unsupported aspectRatio: {value}",
                    path="config.aspectRatio",
                    normalize="strip",
                    meta={
                        "labels": {
                            "1:1": "1:1 (Square)",
                            "16:9": "16:9 (Landscape)",
                            "9:16": "9:16 (Portrait)",
                        }
                    },
                ),
                EnumFieldRequirement(
                    key="outputFormat",
                    allowed=("png", "jpg", "webp"),
                    code="unsupported_output_format",
                    message="unsupported outputFormat: {value}",
                    path="config.outputFormat",
                    normalize="lower_strip",
                    meta={"labels": {"png": "PNG", "jpg": "JPG", "webp": "WebP"}},
                ),
            ),
            model_provider=ModelProviderContract(
                unsupported_provider_message="only openai provider is supported for imageGeneration",
                unsupported_model_message_template="unsupported imageGeneration model: {model}",
                # Keep behavior consistent with current save validator: only block gemini for image nodes.
                block_unprefixed_non_openai_families=False,
                block_model_substrings_anywhere=("gemini",),
            ),
            requires_input_or_incoming_edge=RequiresInputOrIncomingEdgeContract(
                config_input_keys=("prompt", "text", "input", "content"),
                code="missing_input",
                message="imageGeneration nodes must have config input or at least one incoming edge",
            ),
        ),
        NodeType.AUDIO.value: NodeContract(
            type=NodeType.AUDIO.value,
            required_fields=(
                FieldRequirement(
                    key="model",
                    kind="string",
                    code="missing_model",
                    message="model is required for audio nodes",
                    path="config.model",
                ),
            ),
            enum_fields=(
                EnumFieldRequirement(
                    key="model",
                    allowed=("openai/tts-1", "openai/tts-1-hd"),
                    code="unsupported_model",
                    message="unsupported audio model: {value}",
                    path="config.model",
                    normalize="strip",
                    meta={
                        "labels": {
                            "openai/tts-1": "OpenAI TTS-1",
                            "openai/tts-1-hd": "OpenAI TTS-1 HD",
                        }
                    },
                ),
                EnumFieldRequirement(
                    key="voice",
                    allowed=("alloy", "echo", "fable", "onyx", "nova", "shimmer"),
                    code="unsupported_voice",
                    message="unsupported voice: {value}",
                    path="config.voice",
                    normalize="lower_strip",
                    meta={
                        "labels": {
                            "alloy": "Alloy",
                            "echo": "Echo",
                            "fable": "Fable",
                            "onyx": "Onyx",
                            "nova": "Nova",
                            "shimmer": "Shimmer",
                        }
                    },
                ),
            ),
            model_provider=ModelProviderContract(
                unsupported_provider_message="only openai provider is supported for audio",
                unsupported_model_message_template="unsupported audio model: {model}",
            ),
            requires_input_or_incoming_edge=RequiresInputOrIncomingEdgeContract(
                config_input_keys=("text", "input", "prompt", "content"),
                code="missing_input",
                message="audio nodes must have config input or at least one incoming edge",
            ),
        ),
        NodeType.STRUCTURED_OUTPUT.value: NodeContract(
            type=NodeType.STRUCTURED_OUTPUT.value,
            required_fields=(
                FieldRequirement(
                    key="schemaName",
                    kind="string",
                    code="missing_schema_name",
                    message="schemaName is required for structured output nodes",
                    path="config.schemaName",
                ),
                FieldRequirement(
                    key="schema",
                    kind="string_or_object",
                    code="missing_schema",
                    message="schema is required for structured output nodes",
                    path="config.schema",
                ),
            ),
            enum_fields=(
                EnumFieldRequirement(
                    key="mode",
                    allowed=("object", "array"),
                    code="unsupported_mode",
                    message="unsupported mode: {value}",
                    path="config.mode",
                    normalize="lower_strip",
                    meta={"labels": {"object": "Object", "array": "Array"}},
                ),
            ),
            model_provider=ModelProviderContract(
                unsupported_provider_message="only openai provider is supported for structuredOutput",
                unsupported_model_message_template="unsupported structuredOutput model: {model}",
                model_optional=True,
            ),
            json_fields=(
                JsonFieldRequirement(
                    key="schema",
                    path="config.schema",
                    parsed_kind="object",
                    invalid_type_code="invalid_schema",
                    invalid_type_message="schema must be a JSON object",
                ),
            ),
            requires_input_or_incoming_edge=RequiresInputOrIncomingEdgeContract(
                config_input_keys=("prompt", "text", "input", "content"),
                code="missing_input",
                message="structuredOutput nodes must have config input or at least one incoming edge",
            ),
        ),
    }


_EDITOR_WORKFLOW_CONTRACTS = _editor_workflow_contracts()

# Alias/compat types (NodeType enum) that should validate against canonical contracts.
_NODE_TYPE_TO_CONTRACT_TYPE: dict[NodeType, str] = {
    NodeType.HTTP: NodeType.HTTP_REQUEST.value,
    NodeType.HTTP_REQUEST: NodeType.HTTP_REQUEST.value,
    NodeType.LLM: NodeType.TEXT_MODEL.value,
    NodeType.TEXT_MODEL: NodeType.TEXT_MODEL.value,
    NodeType.CONDITION: NodeType.CONDITIONAL.value,
    NodeType.CONDITIONAL: NodeType.CONDITIONAL.value,
    # Canonical types map to themselves.
    NodeType.START: NodeType.START.value,
    NodeType.END: NodeType.END.value,
    NodeType.JAVASCRIPT: NodeType.JAVASCRIPT.value,
    NodeType.PYTHON: NodeType.PYTHON.value,
    NodeType.TRANSFORM: NodeType.TRANSFORM.value,
    NodeType.PROMPT: NodeType.PROMPT.value,
    NodeType.IMAGE: NodeType.IMAGE.value,
    NodeType.AUDIO: NodeType.AUDIO.value,
    NodeType.TOOL: NodeType.TOOL.value,
    NodeType.EMBEDDING: NodeType.EMBEDDING.value,
    NodeType.STRUCTURED_OUTPUT: NodeType.STRUCTURED_OUTPUT.value,
    NodeType.DATABASE: NodeType.DATABASE.value,
    NodeType.FILE: NodeType.FILE.value,
    NodeType.NOTIFICATION: NodeType.NOTIFICATION.value,
    NodeType.LOOP: NodeType.LOOP.value,
}


def get_editor_workflow_node_contracts() -> dict[str, NodeContract]:
    """Contracts keyed by *canonical* node.type (UI palette contract)."""

    return _EDITOR_WORKFLOW_CONTRACTS


def resolve_editor_workflow_node_contract(node_type: NodeType) -> NodeContract | None:
    """Resolve a NodeType (including legacy aliases) to its canonical editor contract.

    Returns None for non-editor/builtin React Flow node types.
    """

    if node_type in {NodeType.INPUT, NodeType.DEFAULT, NodeType.OUTPUT}:
        return None
    contract_type = _NODE_TYPE_TO_CONTRACT_TYPE.get(node_type)
    if contract_type is None:
        return None
    return _EDITOR_WORKFLOW_CONTRACTS.get(contract_type)
