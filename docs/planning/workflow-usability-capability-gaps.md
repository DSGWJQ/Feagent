# Workflow 可用性：信息缺口与阻塞项列表（基于事实源审计）

> 日期：2026-02-01
> 目标：在进入“修复/补测/边界探索”前，把会导致口径漂移或必败链路的缺口列清楚（并按 P0/P1 分级）。

## 0. 已确认事实（代码口径）

1) tool 节点在 API 主入口是“可执行能力”的一部分
   - `src/interfaces/api/main.py` 调用 `create_executor_registry(..., session_factory=_create_session)` → registry 会注册 `tool` executor。
   - 但 `create_executor_registry()` 默认不注册 tool（session_factory=None 时），因此在某些测试/离线场景 tool 可能天然不可用。

2) SaveValidator 已做部分“口径归一化”（减少 drift）
   - HTTP: legacy `path` 会被 normalize 到 `url`
   - Tool: legacy `toolId` 会被 normalize 到 `tool_id`
   - Loop: legacy `type=for + iterations` 会被 normalize 到 `type=range + end`

3) 前端 UI 的“可拖拽节点集合”目前为（18 个）：
   `start/end/httpRequest/textModel/conditional/javascript/python/transform/prompt/imageGeneration/audio/tool/embeddingModel/structuredOutput/database/file/notification/loop`
   - 事实源：`web/src/features/workflows/utils/nodeUtils.ts` + `web/src/features/workflows/pages/WorkflowEditorPageWithMutex.tsx`

4) 对话侧（真实链路）supported node list 已与 UI 节点集合对齐（已修复）
   - `src/domain/services/workflow_chat_service_enhanced.py` prompt 已覆盖 UI 节点，并补充模型类节点 provider 约束（OpenAI-only）。

5) API（deprecated/internal）生成 prompt 的节点清单与 UI 不完全一致
   - `src/interfaces/api/routes/workflows.py:SimpleWorkflowLLMClient.generate_workflow` 支持列表包含 `javascript`，不包含 `tool`，并提示避免使用 tool（环境依赖）。

## 1. P0 阻塞项（零容忍：保存通过但必然执行失败 / 口径承诺但系统不可用）

### P0-1 textModel provider/密钥注入不一致（已修复：OpenAI-only）

- 现状：
  - `LlmExecutor`：
    - `google` provider 未实现（必失败）
  - SaveValidator 现已对 textModel 做 provider fail-closed 校验（拒绝非 OpenAI provider）。
  - UI 现已移除 `anthropic/*`、`google/*` 模型选项，避免生成必败配置。
- 影响（修复后）：用户无法保存一个当前实现必败的 provider 配置。

### P0-2 imageGeneration provider 口径漂移（已修复：移除 Gemini + fail-closed）

- 现状：
  - `ImageGenerationExecutor` 仅支持 OpenAI
  - SaveValidator 现已 fail-closed：拒绝非 OpenAI provider，且拒绝 `gemini*` 模型族（即使缺 provider 前缀）。
  - UI 现已移除 Gemini 选项。
- 影响（修复后）：imageGeneration 不再允许保存明显必败的模型配置。

### P0-3 database_url 未被 SaveValidator 限制（runtime 仅 sqlite）（已修复）

- 修复：
  - SaveValidator 现在 fail-closed：`database_url` 必须以 `sqlite:///` 开头，否则报 `unsupported_database_url`
- 覆盖测试：
  - `tests/unit/domain/services/test_workflow_save_validator.py::test_validator_rejects_database_url_when_not_sqlite`

### P0-4 “可表达→可生成”链路缺口（已修复：对话 supported node list 对齐 UI）

- 现状：
  - 任务库文档 `docs/planning/workflow-task-catalog.md` 已列出：`embeddingModel/imageGeneration/audio/structuredOutput/javascript/tool`
  - 真实 chat prompt 已列出 `embeddingModel/imageGeneration/audio/structuredOutput/javascript`
- 影响（修复后）：对话侧可生成 UI 支持节点组合，减少口径漂移。

## 2. P1 信息缺口（不影响基本跑通，但会影响边界结论/可用性验收）

1) 生产/测试环境的能力开关与依赖边界（需口径化）
   - `E2E_TEST_MODE`（deterministic/hybrid/fullreal）、`LLM_ADAPTER`、`HTTP_ADAPTER`
   - 是否配置 `OPENAI_API_KEY`、是否存在 `ANTHROPIC_API_KEY`（以及是否允许外部 HTTP/通知）
   - tool 节点依赖 DB 的 Tool 数据：prod/dev 是否一定存在可用 tool？tool 缺失时 UI/对话是否应该隐藏/降级？

2) Draft 可编辑性策略（已对齐）
   - SaveValidator 在 draft 时仅对 **start->end 主连通子图**做 executability 校验；非主子图节点允许 in-progress（不会因缺 executor / tool 未配置而阻断保存）。
   - 覆盖测试：`tests/unit/domain/services/test_workflow_save_validator.py::test_validator_allows_draft_to_contain_incomplete_tool_node_outside_main_subgraph`

3) 多模态节点的“最小可执行配置”定义
   - embeddingModel/imageGeneration/audio/structuredOutput 的输入来源：靠入边还是允许 config 直接填写？
   - structuredOutput 的 schema 是否需要更强校验（例如必须是 object schema / required 字段等）？

## 3. 需要你提供的信息（对应 workflow-usability-capability-plan.md §9）

1) 已测试的场景/节点清单（按：节点类型/依赖/是否 deterministic 端到端跑通）
2) 你当前环境可用依赖：
   - LLM（是否允许真实调用？用哪家 provider？）
   - DB（仅 sqlite 还是也要支持其他？）
   - 外部 HTTP、通知（webhook/email/slack）是否允许出网？
   - MCP/知识库（RAG）是否启用？
3) “对话成功标准”：
   - 只要生成并可保存就算成功？
   - 还是必须执行成功并产出结果？
   - deterministic 环境下是否要求语义断言（例如 ETL 结果正确）？

## 4. 决策记录（已确认）

1) database：仅支持 sqlite（已落地 SaveValidator fail-closed：拒绝非 `sqlite:///`）
2) 模型类节点：当前版本仅承诺 OpenAI provider（已落地：UI 收敛 + SaveValidator fail-closed + chat prompt 规则）
