/**
 * Workflow capabilities (machine-consumable SoT from backend).
 *
 * Source: GET /api/workflows/capabilities
 * NOTE: Keys are snake_case to match FastAPI/Pydantic responses (no client-side transform).
 */

export type FieldRequirement = {
  key: string;
  kind: string;
  code: string;
  message: string;
  path: string;
};

export type AnyOfRequirement = {
  keys: string[];
  code: string;
  message: string;
  path: string;
};

export type EnumFieldRequirement = {
  key: string;
  allowed: string[];
  code: string;
  message: string;
  path: string;
  normalize: string;
  meta?: Record<string, unknown> | null;
};

export type JsonFieldRequirement = {
  key: string;
  path: string;
  parsed_kind: string;
  invalid_type_code?: string | null;
  invalid_type_message?: string | null;
  parse_when_startswith?: string[] | null;
};

export type ConditionalRequired = {
  when_key: string;
  when_equals: string;
  normalize: string;
  required_fields: FieldRequirement[];
};

export type ModelProviderContract = {
  model_key: string;
  allowed_providers: string[];
  unsupported_provider_code: string;
  unsupported_provider_message: string;
  unsupported_model_code: string;
  unsupported_model_message_template: string;
  block_unprefixed_non_openai_families: boolean;
  non_openai_tokens: string[];
  block_model_substrings_anywhere: string[];
  model_optional: boolean;
};

export type RequiresInputOrIncomingEdgeContract = {
  config_input_keys: string[];
  code: string;
  message: string;
  path: string;
};

export type TextModelPromptContract = {
  prompt_keys: string[];
  prompt_source_keys: string[];
  missing_prompt_code: string;
  missing_prompt_message: string;
  ambiguous_source_code: string;
  ambiguous_source_message: string;
  invalid_source_code: string;
  invalid_source_message_template: string;
  prompt_path: string;
  prompt_source_path: string;
};

export type DatabaseUrlContract = {
  key: string;
  default_value: string;
  supported_prefix: string;
  missing_code: string;
  missing_message: string;
  unsupported_code: string;
  unsupported_message: string;
  path: string;
};

export type ToolNodeContract = {
  tool_id_keys: string[];
  missing_tool_id_code: string;
  missing_tool_id_message: string;
  tool_id_path: string;
  repository_unavailable_code: string;
  repository_unavailable_message: string;
  not_found_code: string;
  not_found_message_template: string;
  deprecated_code: string;
  deprecated_message_template: string;
};

export type WorkflowNodeValidationContract = {
  required_fields: FieldRequirement[];
  required_any_of: AnyOfRequirement[];
  enum_fields: EnumFieldRequirement[];
  json_fields: JsonFieldRequirement[];
  conditional_required: ConditionalRequired[];
  model_provider?: ModelProviderContract | null;
  requires_input_or_incoming_edge?: RequiresInputOrIncomingEdgeContract | null;
  text_model_prompt?: TextModelPromptContract | null;
  database_url?: DatabaseUrlContract | null;
  tool_node?: ToolNodeContract | null;
};

export type WorkflowNodeCapability = {
  type: string;
  aliases: string[];
  executor_available: boolean;
  validation_contract: WorkflowNodeValidationContract;
  runtime_notes: string[];
};

export type WorkflowCapabilitiesConstraints = {
  sqlite_only: boolean;
  sqlite_database_url_prefix: string;
  model_providers_supported: string[];
  openai_only: boolean;
  run_persistence_enabled: boolean;
  execute_stream_requires_run_id: boolean;
  draft_validation_scope: string;
};

export type WorkflowCapabilitiesResponse = {
  schema_version: string;
  constraints: WorkflowCapabilitiesConstraints;
  node_types: WorkflowNodeCapability[];
};
