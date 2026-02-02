# Workflow 能力对齐矩阵（草案）

> 版本：draft（用于“口径对齐/阻塞项识别”，非最终对外文档）
> 日期：2026-02-01
> 范围：以“编辑器工作流链路（体系 B）”为唯一验收口径；对齐对话/文档/UI/API 与运行时能力。

## 0. 事实源（Source of Truth）

- 节点类型（含兼容别名）：`src/domain/value_objects/node_type.py`
- 执行器注册（node_type → executor）：`src/infrastructure/executors/__init__.py:create_executor_registry`
- 保存前强校验（fail-closed）：`src/domain/services/workflow_save_validator.py`
- 执行语义（DAG / edge.condition / config template / 事件）：`src/domain/services/workflow_engine.py`
- 前端节点白名单（可拖拽集合 + ReactFlow nodeTypes）：`web/src/features/workflows/utils/nodeUtils.ts` + `web/src/features/workflows/pages/WorkflowEditorPageWithMutex.tsx`
- 前端配置面板：`web/src/features/workflows/components/NodeConfigPanel.tsx`
- 对话侧（真实链路 prompt）：`src/domain/services/workflow_chat_service_enhanced.py`
- 对话侧（deterministic stub，离线可复现）：`src/infrastructure/llm/deterministic_workflow_chat_llm.py`
- API（deprecated/internal 的 generate prompt 口径）：`src/interfaces/api/routes/workflows.py:SimpleWorkflowLLMClient.generate_workflow`

## 1. Canonical 节点对齐（以 UI 拖拽节点为主）

> 说明：本节的 “Canonical” 指 UI 当前使用的 node.type 值；兼容别名仅用于历史数据/导入，不建议出现在新文档/新示例/新 prompt 中。

### 1.1 start

- Canonical: `start`
- Aliases: 无
- ExecutorRegistry: `StartExecutor`（固定注册）
- SaveValidator: builtin type（跳过）
- Runtime（Engine）语义：返回 `initial_input`（同 `input`）
- UI: 可拖拽；无配置
- Chat prompt（真实链路）：支持
- Chat stub（deterministic）：不显式生成 start（由其他链路创建基底 workflow）
- API generate-from-form（deprecated）：支持

### 1.2 end

- Canonical: `end`
- Aliases: 无
- ExecutorRegistry: `EndExecutor`（固定注册）
- SaveValidator: builtin type（跳过）
- Runtime（Engine）语义：返回第一个输入（同 `output/default`）
- UI: 可拖拽；无配置
- Chat prompt（真实链路）：支持
- Chat stub（deterministic）：不显式生成 end（由其他链路创建基底 workflow）
- API generate-from-form（deprecated）：支持

### 1.3 httpRequest

- Canonical: `httpRequest`
- Aliases: `http`（历史兼容）
- ExecutorRegistry: `HttpExecutor`（固定注册：`httpRequest` + `http`）
- SaveValidator:
  - 必填：`method`；`url`（或 legacy `path`）
  - JSON 字段：`headers/body/mock_response` 若为 string，会尝试 parse（避免 executor 100%失败）
  - 保存前 normalize：`path -> url`（trim），并移除 `path`
- Runtime（Executor）约束：必须存在 `url`（或 `path`）；headers/body 允许 dict 或 JSON string；deterministic 模式可用 `mock_response`
- UI:
  - 可拖拽
  - 配置面板：URL（必填）、Method（必填）、Headers/Body（可选 string）
- Chat prompt（真实链路）：支持
- Chat stub（deterministic）：支持
- API generate-from-form（deprecated）：支持

### 1.4 textModel

- Canonical: `textModel`
- Aliases: `llm`（历史兼容）
- ExecutorRegistry: `LlmExecutor`（固定注册：`textModel` + `llm`）
- SaveValidator:
  - 必填：`model`
  - prompt 规则（与 runtime 对齐）：
    - 若 config 有 `prompt`/`user_prompt`（非空）→ 通过
    - 若无 prompt：必须至少 1 条入边；若入边 > 1，必须配置 `promptSourceNodeId`（或 `promptSource`）
- Runtime（Executor）约束：
  - 代码路径包含 provider=`openai`/`anthropic`/`google` 分支，但当前对外 contract 已收敛为 OpenAI-only（保存阶段 fail-closed 拒绝非 openai）
  - google provider 未实现；anthropic provider 目前未接入 Settings（不可配置）
  - 多入边 + 无 promptSourceNodeId → 必失败（抛 DomainError）
- UI:
  - 可拖拽
  - 配置面板：Model（必填）、Temperature、MaxTokens、Structured Output（bool）+ Schema（可选）
- Chat prompt（真实链路）：支持（已对齐 UI 节点集合）
- Chat stub（deterministic）：支持
- API generate-from-form（deprecated）：支持

### 1.5 conditional

- Canonical: `conditional`
- Aliases: `condition`（历史兼容/Coze 导入）
- ExecutorRegistry: `ConditionalExecutor`（固定注册：`conditional` + `condition`）
- SaveValidator: 必填 `condition`（string）
- Runtime（Executor）语义：返回 `{result: bool, branch: "true"|"false"}`
- Runtime（Engine）edge.condition 语义：
  - `edge.condition` 若为 `"true"/"false"`，且 source 输出含 `branch`/`result`，则走分支匹配
  - 否则按表达式求值（ExpressionEvaluator，AST + allowlist）
- UI: 可拖拽；配置面板 condition 必填（string）
- Chat prompt（真实链路）：支持
- Chat stub（deterministic）：支持
- API generate-from-form（deprecated）：支持

### 1.6 loop

- Canonical: `loop`
- Aliases: 无（但历史兼容 `type="for" + iterations`）
- ExecutorRegistry: `LoopExecutor`（固定注册）
- SaveValidator:
  - 必填：`type`（for_each / range / while）
  - for_each：必填 `array`
  - range：必填 `end`（或 legacy `iterations`）+ 必填 `code`
  - while：必填 `condition` + 必填 `code`；`max_iterations` 必须为正整数（若提供）
  - 保存前 normalize：`type="for" -> "range"`；`iterations -> end`
- Runtime（Executor）约束：与 SaveValidator 一致；range/end/step 需可转 int
- UI:
  - 可拖拽
  - 配置面板：Type（必填）；各类型的必填字段与 SaveValidator 基本一致
- Chat prompt（真实链路）：支持
- Chat stub（deterministic）：支持
- API generate-from-form（deprecated）：支持

### 1.7 python

- Canonical: `python`
- Aliases: 无
- ExecutorRegistry: `PythonExecutor`（固定注册）
- SaveValidator: 必填 `code`
- Runtime（Executor）约束：限制 SAFE_BUILTINS；禁止部分关键字；通过 `exec` 执行并读取 `result`
- UI: 可拖拽；配置面板 code 必填
- Chat prompt（真实链路）：支持
- Chat stub（deterministic）：支持
- API generate-from-form（deprecated）：支持

### 1.8 javascript

- Canonical: `javascript`
- Aliases: 无
- ExecutorRegistry: `JavaScriptExecutor`（固定注册）
- SaveValidator: 必填 `code`
- Runtime（Executor）语义：将输入映射为 `input1...`；以 python `exec` 近似运行（非真实 JS 引擎）
- UI: 可拖拽；配置面板 code 必填
- Chat prompt（真实链路）：未列入支持节点类型（当前链路大概率不会生成）
- Chat stub（deterministic）：支持
- API generate-from-form（deprecated）：支持

### 1.9 transform

- Canonical: `transform`
- Aliases: 无
- ExecutorRegistry: `TransformExecutor`（固定注册）
- SaveValidator: 依据 `type` 分支校验（field_mapping/type_conversion/field_extraction/array_mapping/filtering/aggregation/custom），必填字段与 runtime 对齐
- UI: 可拖拽；配置面板支持多种 JSON 字段（会尝试 JSON.parse）
- Chat prompt（真实链路）：支持
- Chat stub（deterministic）：支持
- API generate-from-form（deprecated）：支持

### 1.10 database

- Canonical: `database`
- Aliases: 无
- ExecutorRegistry: `DatabaseExecutor`（固定注册）
- SaveValidator:
  - 必填：`sql`
  - `database_url` 缺省时会写入默认值 `sqlite:///agent_data.db`（避免 drift）
  - `params` 若为 string，会尝试 parse（仅允许 object/array）
  - 约束：仅允许 `sqlite:///` 前缀（fail-closed，与 runtime 对齐）
- Runtime（Executor）约束：仅支持 `sqlite:///`；会创建目录；会执行 SQL（返回 rows 或 rows_affected）
- UI: 可拖拽；配置面板中 params 若非 string 会 stringify
- Chat prompt（真实链路）：支持
- Chat stub（deterministic）：支持
- API generate-from-form（deprecated）：支持

### 1.11 file

- Canonical: `file`
- Aliases: 无
- ExecutorRegistry: `FileExecutor`（固定注册）
- SaveValidator: 必填 `operation`（read/write/append/delete/list）+ `path`
- Runtime（Executor）约束：与 SaveValidator 一致；write/append 的 content 可为空（但可能不符合业务预期）
- UI: 可拖拽；配置面板与 SaveValidator 一致
- Chat prompt（真实链路）：支持
- Chat stub（deterministic）：支持
- API generate-from-form（deprecated）：支持

### 1.12 notification

- Canonical: `notification`
- Aliases: 无
- ExecutorRegistry: `NotificationExecutor`（固定注册）
- SaveValidator:
  - 必填：`type` + `message`
  - webhook：必填 `url`
  - slack：必填 `webhook_url`
  - email：必填 `smtp_host/sender/sender_password/recipients`（recipients 支持 string 或 JSON array）
  - headers 若为 string，会尝试 parse（仅允许 object）
- Runtime（Executor）约束：与 SaveValidator 一致；deterministic 模式不发外部请求
- UI: 可拖拽；配置面板与 SaveValidator 基本一致
- Chat prompt（真实链路）：支持
- Chat stub（deterministic）：支持
- API generate-from-form（deprecated）：支持

### 1.13 prompt

- Canonical: `prompt`
- Aliases: 无
- ExecutorRegistry: `PromptExecutor`（固定注册）
- SaveValidator: 必填 `content`
- Runtime（Executor）语义：仅做简单 `{input1}` 字符串替换（与 engine 的更通用 template 渲染并存）
- UI: 可拖拽；配置面板 content 必填
- Chat prompt（真实链路）：支持
- Chat stub（deterministic）：支持
- API generate-from-form（deprecated）：支持

### 1.14 embeddingModel

- Canonical: `embeddingModel`
- Aliases: 无
- ExecutorRegistry: `EmbeddingExecutor`（固定注册）
- SaveValidator:
  - 必填：`model`
  - 输入规则：config 需包含 `input/text/prompt/content` 之一，或至少 1 条入边
- 约束：仅支持 OpenAI provider（保存阶段 fail-closed）
- Runtime（Executor）约束：仅支持 OpenAI；provider!=openai 会抛 DomainError
- UI: 可拖拽；配置面板仅提供 model/dimensions（依赖入边提供 input）
- Chat prompt（真实链路）：支持
- Chat stub（deterministic）：支持
- API generate-from-form（deprecated）：支持

### 1.15 imageGeneration

- Canonical: `imageGeneration`
- Aliases: 无
- ExecutorRegistry: `ImageGenerationExecutor`（固定注册）
- SaveValidator:
  - 必填：`model`
  - 输入规则：config 需包含 `prompt/text/input/content` 之一，或至少 1 条入边
- 约束：仅支持 OpenAI provider（保存阶段 fail-closed）
- Runtime（Executor）约束：仅支持 OpenAI；provider!=openai 会抛 DomainError
- UI:
  - 可拖拽
  - 配置面板：仅提供 OpenAI 图像模型选项
- Chat prompt（真实链路）：支持
- Chat stub（deterministic）：支持
- API generate-from-form（deprecated）：支持

### 1.16 audio

- Canonical: `audio`
- Aliases: 无
- ExecutorRegistry: `AudioExecutor`（固定注册）
- SaveValidator:
  - 必填：`model`
  - 输入规则：config 需包含 `text/input/prompt/content` 之一，或至少 1 条入边
- 约束：仅支持 OpenAI provider（保存阶段 fail-closed）
- Runtime（Executor）约束：仅支持 OpenAI；provider!=openai 会抛 DomainError
- UI: 可拖拽；配置面板提供 openai 模型/voice/speed（依赖入边提供 text）
- Chat prompt（真实链路）：支持
- Chat stub（deterministic）：支持
- API generate-from-form（deprecated）：支持

### 1.17 structuredOutput

- Canonical: `structuredOutput`
- Aliases: 无
- ExecutorRegistry: `StructuredOutputExecutor`（固定注册）
- SaveValidator:
  - 必填：`schemaName` + `schema`（schema 支持 dict 或 JSON string）
  - 输入规则：config 需包含 `prompt/text/input/content` 之一，或至少 1 条入边
- 约束：若显式提供 `model`，则仅支持 OpenAI provider（保存阶段 fail-closed）
- Runtime（Executor）约束：仅支持 OpenAI；schema 必须可解析为 JSON schema；prompt 缺省时会从输入推导
- UI: 可拖拽；配置面板要求 schemaName/schema（依赖入边提供 input 或用户填 prompt）
- Chat prompt（真实链路）：支持
- Chat stub（deterministic）：支持
- API generate-from-form（deprecated）：支持

### 1.18 tool

- Canonical: `tool`
- Aliases: 无
- ExecutorRegistry: `ToolNodeExecutor`
  - 仅当 `create_executor_registry(session_factory=...)` 传入 `session_factory` 时注册（否则 registry 无 tool executor）
- SaveValidator:
  - 必填：`tool_id`（接受 legacy `toolId` 并 normalize）
  - 依赖：必须注入 `tool_repository` 且 tool_id 存在且不为 deprecated
- Runtime（Executor）约束：通过 DB 加载 Tool 并用 ToolEngine 执行；tool 不存在/废弃/失败则抛 DomainError
- UI: 可拖拽；配置面板通过 `/tools` 下拉选择，保存使用 `tool_id`
- Chat prompt（真实链路）：支持（并会列出允许工具列表；要求无法确定 tool_id 时必须 ask_clarification）
- Chat stub（deterministic）：不支持（stub 不会规划/映射 tool 节点）
- API generate-from-form（deprecated）：不在 node type 列表中（并显式提示避免使用 tool）

## 2. 已识别的 Contract Drift（P0：已修复/已对齐）

> 定义：出现“保存通过但在当前实现下必然执行失败”或“UI/对话承诺了能力但事实源不支持”。

1) textModel provider drift（已修复）
   - UI 已收敛为 OpenAI-only；SaveValidator 已 fail-closed 拒绝非 openai provider。
2) imageGeneration Gemini drift（已修复）
   - UI 已移除 Gemini 选项；SaveValidator 已 fail-closed（拒绝非 openai provider，并拒绝 gemini 模型族）。
3) database sqlite-only（已对齐）
   - SaveValidator 已 fail-closed：仅允许 `sqlite:///`。
4) chat supported node list drift（已修复）
   - 对话 prompt 已与 UI 节点集合对齐（补齐 `javascript/embeddingModel/imageGeneration/audio/structuredOutput`）。

## 3. 备注：非本矩阵范围（并存体系）

- `src/domain/services/node_registry.py` + `src/domain/services/node_schema.py` 属于 WorkflowAgent/扩展定义体系，与编辑器工作流（NodeType/ExecutorRegistry/SaveValidator/UI）并存；本矩阵以编辑器工作流为准，后续如需统一需要显式映射表。
