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

3) 前端 UI 的“可拖拽节点集合”目前为（17 个）：
   `start/end/httpRequest/textModel/conditional/javascript/python/transform/prompt/imageGeneration/audio/tool/embeddingModel/structuredOutput/database/file/notification/loop`
   - 事实源：`web/src/features/workflows/utils/nodeUtils.ts` + `web/src/features/workflows/pages/WorkflowEditorPageWithMutex.tsx`

4) 对话侧（真实链路）supported node list 目前未覆盖全部 UI 节点
   - `src/domain/services/workflow_chat_service_enhanced.py` prompt 仅列：
     `start/end/httpRequest/transform/database/conditional/loop/python/textModel/prompt/file/notification/tool`
   - 缺失：`javascript/embeddingModel/imageGeneration/audio/structuredOutput`

5) API（deprecated/internal）生成 prompt 的节点清单与 UI 不完全一致
   - `src/interfaces/api/routes/workflows.py:SimpleWorkflowLLMClient.generate_workflow` 支持列表包含 `javascript`，不包含 `tool`，并提示避免使用 tool（环境依赖）。

## 1. P0 阻塞项（零容忍：保存通过但必然执行失败 / 口径承诺但系统不可用）

### P0-1 textModel provider/密钥注入不一致

- 现状：
  - UI 允许选择：`openai/*`、`anthropic/*`、`google/*`
  - `LlmExecutor`：
    - `google` provider 未实现（必失败）
    - `anthropic` provider 需要 Anthropic key，但 `create_executor_registry()` 当前仅把 `openai_api_key` 注入 `LlmExecutor`（anthropic key 参数未使用）
  - SaveValidator 未对 provider 与依赖做 fail-closed 校验（因此“可保存但必失败”成立）
- 影响：用户可在 UI 配置并保存一个 textModel 节点，但执行阶段稳定失败。

### P0-2 imageGeneration provider 口径漂移（UI 提供 Gemini 选项但 runtime 仅支持 OpenAI）

- 现状：
  - UI `imageGeneration` 提供 `gemini-2.5-flash-image`（无 provider 前缀）
  - `ImageGenerationExecutor` 仅支持 OpenAI
  - SaveValidator 仅校验 model 非空，不限制 provider
- 影响：用户可保存，但执行必失败或调用 OpenAI 时 model 不合法。

### P0-3 database_url 未被 SaveValidator 限制（runtime 仅 sqlite）（已修复）

- 修复：
  - SaveValidator 现在 fail-closed：`database_url` 必须以 `sqlite:///` 开头，否则报 `unsupported_database_url`
- 覆盖测试：
  - `tests/unit/domain/services/test_workflow_save_validator.py::test_validator_rejects_database_url_when_not_sqlite`

### P0-4 “可表达→可生成”链路缺口（对话任务库/文档 vs 真实 chat prompt）

- 现状：
  - 任务库文档 `docs/planning/workflow-task-catalog.md` 已列出：`embeddingModel/imageGeneration/audio/structuredOutput/javascript/tool`
  - 真实 chat prompt 未列出 `embeddingModel/imageGeneration/audio/structuredOutput/javascript`
- 影响：用户按文档/任务库表达需求时，系统对话侧可能无法生成对应节点组合（口径漂移）。

## 2. P1 信息缺口（不影响基本跑通，但会影响边界结论/可用性验收）

1) 生产/测试环境的能力开关与依赖边界（需口径化）
   - `E2E_TEST_MODE`（deterministic/hybrid/fullreal）、`LLM_ADAPTER`、`HTTP_ADAPTER`
   - 是否配置 `OPENAI_API_KEY`、是否存在 `ANTHROPIC_API_KEY`（以及是否允许外部 HTTP/通知）
   - tool 节点依赖 DB 的 Tool 数据：prod/dev 是否一定存在可用 tool？tool 缺失时 UI/对话是否应该隐藏/降级？

2) Draft 可编辑性策略
   - SaveValidator 在 draft 时仍会对所有节点校验 “executor 是否存在”（而不仅仅是主连通子图），可能导致草稿阶段无法保存“进行中的”节点（需确认是否符合产品预期）。

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

## 4. 下一步（进入修复前的最小决策点）

请你先确认以下 3 点（我再进入第 2/3/4 阶段的代码修复与补测）：

1) textModel：是否要对外宣称支持 `anthropic/*` 与 `google/*`？（若否，UI/SaveValidator/文档需收敛到 openai）
2) imageGeneration：是否要保留 Gemini 选项？（若否，UI 需要移除；若是，需要补 executor/provider 支持与校验）
3) database：是否只支持 sqlite？（若是，SaveValidator/前端需要显式限制并给出清晰错误；若否，需要实现更多 executor）
