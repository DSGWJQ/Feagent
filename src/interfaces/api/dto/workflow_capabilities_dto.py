"""Workflow capabilities DTOs (editor workflow chain)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FieldRequirementDto(BaseModel):
    key: str
    kind: str
    code: str
    message: str
    path: str


class AnyOfRequirementDto(BaseModel):
    keys: list[str]
    code: str
    message: str
    path: str


class EnumFieldRequirementDto(BaseModel):
    key: str
    allowed: list[str]
    code: str
    message: str
    path: str
    normalize: str = "strip"
    meta: dict[str, Any] | None = None


class JsonFieldRequirementDto(BaseModel):
    key: str
    path: str
    parsed_kind: str = "any"
    invalid_type_code: str | None = None
    invalid_type_message: str | None = None
    parse_when_startswith: list[str] | None = None


class ConditionalRequiredDto(BaseModel):
    when_key: str
    when_equals: str
    normalize: str = "strip"
    required_fields: list[FieldRequirementDto] = Field(default_factory=list)


class ModelProviderContractDto(BaseModel):
    model_key: str = "model"
    allowed_providers: list[str] = Field(default_factory=list)
    unsupported_provider_code: str
    unsupported_provider_message: str
    unsupported_model_code: str
    unsupported_model_message_template: str
    block_unprefixed_non_openai_families: bool = True
    non_openai_tokens: list[str] = Field(default_factory=list)
    block_model_substrings_anywhere: list[str] = Field(default_factory=list)
    model_optional: bool = False


class RequiresInputOrIncomingEdgeContractDto(BaseModel):
    config_input_keys: list[str]
    code: str
    message: str
    path: str = "config"


class TextModelPromptContractDto(BaseModel):
    prompt_keys: list[str] = Field(default_factory=list)
    prompt_source_keys: list[str] = Field(default_factory=list)
    missing_prompt_code: str
    missing_prompt_message: str
    ambiguous_source_code: str
    ambiguous_source_message: str
    invalid_source_code: str
    invalid_source_message_template: str
    prompt_path: str
    prompt_source_path: str


class DatabaseUrlContractDto(BaseModel):
    key: str = "database_url"
    default_value: str
    supported_prefix: str
    missing_code: str
    missing_message: str
    unsupported_code: str
    unsupported_message: str
    path: str


class ToolNodeContractDto(BaseModel):
    tool_id_keys: list[str] = Field(default_factory=list)
    missing_tool_id_code: str
    missing_tool_id_message: str
    tool_id_path: str
    repository_unavailable_code: str
    repository_unavailable_message: str
    not_found_code: str
    not_found_message_template: str
    deprecated_code: str
    deprecated_message_template: str


class WorkflowNodeValidationContractDto(BaseModel):
    required_fields: list[FieldRequirementDto] = Field(default_factory=list)
    required_any_of: list[AnyOfRequirementDto] = Field(default_factory=list)
    enum_fields: list[EnumFieldRequirementDto] = Field(default_factory=list)
    json_fields: list[JsonFieldRequirementDto] = Field(default_factory=list)
    conditional_required: list[ConditionalRequiredDto] = Field(default_factory=list)

    model_provider: ModelProviderContractDto | None = None
    requires_input_or_incoming_edge: RequiresInputOrIncomingEdgeContractDto | None = None
    text_model_prompt: TextModelPromptContractDto | None = None
    database_url: DatabaseUrlContractDto | None = None
    tool_node: ToolNodeContractDto | None = None


class WorkflowNodeCapabilityDto(BaseModel):
    type: str
    aliases: list[str] = Field(default_factory=list)
    executor_available: bool
    validation_contract: WorkflowNodeValidationContractDto
    runtime_notes: list[str] = Field(default_factory=list)


class WorkflowCapabilitiesConstraintsDto(BaseModel):
    sqlite_only: bool = True
    sqlite_database_url_prefix: str
    model_providers_supported: list[str] = Field(default_factory=list)
    openai_only: bool = True
    draft_validation_scope: str = Field(
        default="main_subgraph_only",
        description="Draft workflows are fail-closed only for the main start->end subgraph",
    )


class WorkflowCapabilitiesResponse(BaseModel):
    schema_version: str
    constraints: WorkflowCapabilitiesConstraintsDto
    node_types: list[WorkflowNodeCapabilityDto]
