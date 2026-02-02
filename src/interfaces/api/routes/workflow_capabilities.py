"""Workflow capabilities endpoint (editor workflow chain SoT)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.domain.services.workflow_node_contracts import (
    CAPABILITIES_SCHEMA_VERSION,
    SQLITE_DATABASE_URL_PREFIX,
    SUPPORTED_MODEL_PROVIDERS,
    get_editor_workflow_node_contracts,
)
from src.interfaces.api.container import ApiContainer
from src.interfaces.api.dependencies.container import get_container
from src.interfaces.api.dto.workflow_capabilities_dto import (
    AnyOfRequirementDto,
    ConditionalRequiredDto,
    DatabaseUrlContractDto,
    EnumFieldRequirementDto,
    FieldRequirementDto,
    JsonFieldRequirementDto,
    ModelProviderContractDto,
    RequiresInputOrIncomingEdgeContractDto,
    TextModelPromptContractDto,
    ToolNodeContractDto,
    WorkflowCapabilitiesConstraintsDto,
    WorkflowCapabilitiesResponse,
    WorkflowNodeCapabilityDto,
    WorkflowNodeValidationContractDto,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _to_validation_contract(contract) -> WorkflowNodeValidationContractDto:
    return WorkflowNodeValidationContractDto(
        required_fields=[
            FieldRequirementDto(
                key=req.key,
                kind=req.kind,
                code=req.code,
                message=req.message,
                path=req.path,
            )
            for req in contract.required_fields
        ],
        required_any_of=[
            AnyOfRequirementDto(
                keys=list(req.keys),
                code=req.code,
                message=req.message,
                path=req.path,
            )
            for req in contract.required_any_of
        ],
        enum_fields=[
            EnumFieldRequirementDto(
                key=req.key,
                allowed=list(req.allowed),
                code=req.code,
                message=req.message,
                path=req.path,
                normalize=req.normalize,
                meta=req.meta,
            )
            for req in contract.enum_fields
        ],
        json_fields=[
            JsonFieldRequirementDto(
                key=req.key,
                path=req.path,
                parsed_kind=req.parsed_kind,
                invalid_type_code=req.invalid_type_code,
                invalid_type_message=req.invalid_type_message,
                parse_when_startswith=list(req.parse_when_startswith)
                if req.parse_when_startswith
                else None,
            )
            for req in contract.json_fields
        ],
        conditional_required=[
            ConditionalRequiredDto(
                when_key=req.when_key,
                when_equals=req.when_equals,
                normalize=req.normalize,
                required_fields=[
                    FieldRequirementDto(
                        key=field.key,
                        kind=field.kind,
                        code=field.code,
                        message=field.message,
                        path=field.path,
                    )
                    for field in req.required_fields
                ],
            )
            for req in contract.conditional_required
        ],
        model_provider=ModelProviderContractDto(
            model_key=contract.model_provider.model_key,
            allowed_providers=list(contract.model_provider.allowed_providers),
            unsupported_provider_code=contract.model_provider.unsupported_provider_code,
            unsupported_provider_message=contract.model_provider.unsupported_provider_message,
            unsupported_model_code=contract.model_provider.unsupported_model_code,
            unsupported_model_message_template=contract.model_provider.unsupported_model_message_template,
            block_unprefixed_non_openai_families=contract.model_provider.block_unprefixed_non_openai_families,
            non_openai_tokens=list(contract.model_provider.non_openai_tokens),
            block_model_substrings_anywhere=list(
                contract.model_provider.block_model_substrings_anywhere
            ),
            model_optional=contract.model_provider.model_optional,
        )
        if contract.model_provider
        else None,
        requires_input_or_incoming_edge=RequiresInputOrIncomingEdgeContractDto(
            config_input_keys=list(contract.requires_input_or_incoming_edge.config_input_keys),
            code=contract.requires_input_or_incoming_edge.code,
            message=contract.requires_input_or_incoming_edge.message,
            path=contract.requires_input_or_incoming_edge.path,
        )
        if contract.requires_input_or_incoming_edge
        else None,
        text_model_prompt=TextModelPromptContractDto(
            prompt_keys=list(contract.text_model_prompt.prompt_keys),
            prompt_source_keys=list(contract.text_model_prompt.prompt_source_keys),
            missing_prompt_code=contract.text_model_prompt.missing_prompt_code,
            missing_prompt_message=contract.text_model_prompt.missing_prompt_message,
            ambiguous_source_code=contract.text_model_prompt.ambiguous_source_code,
            ambiguous_source_message=contract.text_model_prompt.ambiguous_source_message,
            invalid_source_code=contract.text_model_prompt.invalid_source_code,
            invalid_source_message_template=contract.text_model_prompt.invalid_source_message_template,
            prompt_path=contract.text_model_prompt.prompt_path,
            prompt_source_path=contract.text_model_prompt.prompt_source_path,
        )
        if contract.text_model_prompt
        else None,
        database_url=DatabaseUrlContractDto(
            key=contract.database_url.key,
            default_value=contract.database_url.default_value,
            supported_prefix=contract.database_url.supported_prefix,
            missing_code=contract.database_url.missing_code,
            missing_message=contract.database_url.missing_message,
            unsupported_code=contract.database_url.unsupported_code,
            unsupported_message=contract.database_url.unsupported_message,
            path=contract.database_url.path,
        )
        if contract.database_url
        else None,
        tool_node=ToolNodeContractDto(
            tool_id_keys=list(contract.tool_node.tool_id_keys),
            missing_tool_id_code=contract.tool_node.missing_tool_id_code,
            missing_tool_id_message=contract.tool_node.missing_tool_id_message,
            tool_id_path=contract.tool_node.tool_id_path,
            repository_unavailable_code=contract.tool_node.repository_unavailable_code,
            repository_unavailable_message=contract.tool_node.repository_unavailable_message,
            not_found_code=contract.tool_node.not_found_code,
            not_found_message_template=contract.tool_node.not_found_message_template,
            deprecated_code=contract.tool_node.deprecated_code,
            deprecated_message_template=contract.tool_node.deprecated_message_template,
        )
        if contract.tool_node
        else None,
    )


@router.get("/capabilities", response_model=WorkflowCapabilitiesResponse)
def get_workflow_capabilities(
    container: ApiContainer = Depends(get_container),
) -> WorkflowCapabilitiesResponse:
    contracts = get_editor_workflow_node_contracts()
    node_types = []
    for node_type, contract in contracts.items():
        node_types.append(
            WorkflowNodeCapabilityDto(
                type=node_type,
                aliases=list(contract.aliases),
                executor_available=container.executor_registry.has(node_type),
                validation_contract=_to_validation_contract(contract),
                runtime_notes=list(contract.runtime_notes),
            )
        )

    constraints = WorkflowCapabilitiesConstraintsDto(
        sqlite_only=True,
        sqlite_database_url_prefix=SQLITE_DATABASE_URL_PREFIX,
        model_providers_supported=list(SUPPORTED_MODEL_PROVIDERS),
        openai_only=(set(SUPPORTED_MODEL_PROVIDERS) == {"openai"}),
        draft_validation_scope="main_subgraph_only",
    )

    return WorkflowCapabilitiesResponse(
        schema_version=CAPABILITIES_SCHEMA_VERSION,
        constraints=constraints,
        node_types=node_types,
    )
