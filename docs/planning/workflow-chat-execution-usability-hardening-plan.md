# Workflow 对话生成 + 执行链路“完全修复”规划（严苛验收 / 分阶段审查）

> 日期：2026-02-02
> 范围：编辑器工作流链路（体系 B）中的 **对话生成/修改** 与 **执行（Runs API + SSE）** 可用性闭环
> 约束：**仅支持 sqlite**；环境变量以仓库 `.env*` 为准（不引入额外 DB / provider）
> 原则：Fail-Closed、KISS、SOLID、DRY；每阶段完成必须做“红队审查”并通过验收门禁才允许进入下一阶段

---

## 0. 背景与目标

### 0.1 背景（当前发现的 P0/P1 问题）

本规划聚焦以下“对话生成工作流 + 执行工作流”的高风险可用性缺陷（来源：近期对链路端到端审查 + 局部用例运行）：

**P0**
1) **SSE 终止语义缺陷（会导致 30s 卡死/尾部超时）**
`ConversationFlowEmitter.complete_with_error()`只发送 error，不发送 END，SSE handler 侧会等待直到 timeout（默认 30s）或出现二次异常。
涉及：`src/domain/services/conversation_flow_emitter.py`、`src/interfaces/api/services/sse_emitter_handler.py`

2) **Runs 执行链路“降级策略”前后端不一致（必然 400，且提示误导）**
后端在 run persistence 开启时强制 `run_id`；前端在 Run 创建失败时可能提示“降级 legacy 执行”，但仍会发送不带 `run_id` 的 execute/stream → 后端 400。
涉及：`src/interfaces/api/routes/workflows.py`、`web/src/features/workflows/pages/WorkflowEditorPageWithMutex.tsx`

**P1**
3) **离线/测试 deterministic 选择存在漂移风险**
`ENV=test` + 无 `OPENAI_API_KEY` 时优先使用 `LangChainWorkflowChatLLM(api_key="test")`，若未 patch 可能触网/非 deterministic；与 `enable_test_seed_api` 的“离线可复现”目标冲突。
涉及：`src/interfaces/api/routes/workflows.py:get_workflow_chat_llm`

4) **合同/文档/Stub 输出之间存在枚举漂移**
Capabilities 合同里 `textModel.model` enum 为 `openai/gpt-5|openai/gpt-4`，但：
- deterministic stub 使用 `openai/gpt-4o-mini`；
- 文档 `docs/planning/workflow-usability-acceptance-criteria-table.md` 示例也用 `openai/gpt-4o-mini`。
这会造成 UI 下拉与数据/示例不一致（可用性与可解释性下降）。

5) **main_subgraph 限制带来的“孤立节点陷阱”**
对话系统 prompt 仅暴露 start->end 主连通子图；若产生/导入孤立节点，后续 chat 无法“看到/删除/修复”（只能拖拽手工清理），在 Draft 策略下还可能长期存在而不阻断保存。
涉及：`src/domain/services/workflow_chat_service_enhanced.py`、`src/domain/services/workflow_save_validator.py`

6) **前端 fail-closed 单测自身当前无法运行**
`WorkflowRunFailClosed.test.tsx` mock 未导出 `getWorkflowCapabilities`，导致渲染直接崩溃，无法证明 fail-closed 行为。
涉及：`web/src/features/workflows/pages/__tests__/WorkflowRunFailClosed.test.tsx`

### 0.2 目标（必须全部达成）

1) 对话生成闭环可用：可创建（chat-create）→可修改（chat-stream）→可保存（强校验）→可解释失败（SSE error/结构化 detail）。
2) 执行闭环可用：可创建 Run（当 Runs 开启）→可执行（execute/stream）→可重放/可观测（run_id 贯穿）→可解释失败/可确认外部副作用。
3) 所有“已发现问题”必须被**代码修复 + 自动化测试覆盖 + 文档口径收敛**，并通过严格验收门禁。

---

## 1. 范围、非目标与约束

### 1.1 范围（本规划覆盖）
- 后端 API：
  - `POST /api/workflows/chat-create/stream`（SSE）
  - `POST /api/workflows/{workflow_id}/chat-stream`（SSE）
  - `POST /api/workflows/{workflow_id}/execute/stream`（SSE + Runs Gate）
  - `POST /api/projects/{project_id}/workflows/{workflow_id}/runs`（创建 Run）
  - `POST /api/runs/{run_id}/confirm`（副作用确认）
- Domain/UseCase：对话修改编排、保存前强校验、Runs gate 与 side-effect confirm。
- 前端：SSE 解析与状态机（chat-create 跳转、chat-stream 展示、execute/stream 日志与确认弹窗）。
- 文档：与 capabilities 合同、默认/示例配置一致性相关部分。

### 1.2 非目标（明确不做）
- 不新增对 MySQL/Postgres 的支持（保持 sqlite-only）。
- 不引入新的外部 LLM provider（保持 OpenAI-only 口径）。
- 不在本轮引入“大重构”（例如替换 SSE 协议、重做前端架构）；仅做**最小可证明修复**。

### 1.3 关键约束（Fail-Closed）
- **只要无法可靠判断，就拒绝执行**（例如 Runs 开启但无法创建 Run；或能力合同未知）。
- **每阶段只解决一类核心问题**，避免大杂烩导致回归难追溯（原子化）。

---

## 2. 总体策略（KISS + 可回滚）

1) **优先修 P0：停止“卡死/误导/必败”路径**（SSE 终止 + Runs 口径统一）。
2) **再修 P1：消除漂移源**（deterministic 选择、enum/文档/Stub 一致、孤立节点陷阱）。
3) **以 capabilities 为对外事实源**：必要时扩展 capabilities（例如补充 run_persistence 状态），让前端不再靠 build-time env 猜测后端行为。
4) **每阶段必须补测并回归**：用最少但高价值的测试覆盖住“失败模式”，并明确可观测信号（错误码、字段 path、SSE 事件序列）。

---

## 3. 分阶段计划（每阶段=交付物+验收+审查门禁）

> 说明：阶段编号用于执行顺序；任何阶段未通过验收与审查门禁，禁止进入下一阶段。

### 阶段 0：基线冻结与复现用例固化（必做）

**目标**
- 把“当前缺陷”固化为可复现脚本/测试，避免后续修复后无法证明“完全解决”。

**工作项**
1) 列出并确认“Runs 开关组合”基线：
   - 后端 `settings.disable_run_persistence` 的真实值与配置来源；
   - 前端 `VITE_DISABLE_RUN_PERSISTENCE` 当前值与其是否应继续存在。
2) 固化以下复现（至少记录到 planning 文档或新增测试）：
   - 触发 `complete_with_error()` 后 SSE 是否能在 1s 内终止；
   - Run 创建失败时前端是否会错误降级并导致后端 400；
   - `ENV=test + enable_test_seed_api=true` 时 chat 流是否可能触网。

**当前基线（以仓库文件为准，2026-02-02 校验）**

1) 后端 Runs 开关（SoT=后端 settings）
   - 配置加载：`src/config.py` 使用 `env_file=".env"`（`SettingsConfigDict`）加载环境变量。
   - 本仓库根目录 `.env` 当前值：`DISABLE_RUN_PERSISTENCE=true`（= `settings.disable_run_persistence=True`，Runs API/Run 落库路径被回滚禁用，execute/stream 走 legacy）。
   - deterministic e2e 示例 `.env.test.example` 当前值：`DISABLE_RUN_PERSISTENCE=false`（= Runs API 启用，execute/stream 要求 `run_id`）。

2) 前端 Runs 开关（现状=存在漂移风险）
   - 代码读取：`web/src/features/workflows/pages/WorkflowEditorPageWithMutex.tsx` 使用 `import.meta.env.VITE_DISABLE_RUN_PERSISTENCE`。
   - `web/.env.example` **未**包含 `VITE_DISABLE_RUN_PERSISTENCE`，因此默认情况下该值为 `undefined` → 代码 fallback 为 `'false'`。
   - 结论：前端与后端存在“各自开关/默认值”的漂移风险；将于阶段 2 以 capabilities 统一，并在不一致时 fail-closed。

**复现步骤（当前缺陷固化）**

- P0-1 SSE 终止语义缺陷（当前可静态确认）
  1) 触发 `ConversationFlowEmitter.complete_with_error()`（例如对话链路内部抛错并走错误完成）。
  2) 观察 `SSEEmitterHandler._generate_events()`：遇到 `StepKind.ERROR` 只发送 error 事件并 `continue`，直到收到 `StepKind.END` 才会发送 `[DONE]` 并结束。
  3) 由于 `complete_with_error()` 当前只发 error 不发 END（且直接标记 completed），SSE 将卡住直到超时（默认 30s）或外部断开。
  - 预期修复后：error 事件后 <1s 内必然出现 `[DONE]` 并结束（以自动化测试断言为准）。

- P0-2 Runs 执行口径不一致导致“误导降级 → 400”（需 Runs 开启）
  1) 后端设置 `DISABLE_RUN_PERSISTENCE=false`（例如使用 `.env.test.example`），使 execute/stream 强制要求 `run_id`。
  2) 前端触发 Run 创建失败（例如缺少 `projectId` 或 Runs API 返回非 2xx）。
  3) 现状：前端提示“将以 legacy 模式执行（无 run session）”，随后仍调用 execute/stream 且不带 `run_id`。
  4) 后端返回 400：`run_id is required (create run first, then execute/stream).`
  - 预期修复后：Runs 开启时，前端必须 fail-closed（Run 创建失败/缺 projectId 直接阻止执行并给出明确提示），不得发送无 `run_id` 的 execute/stream。

- P1-3 deterministic/测试模式选择漂移（可能触网）
  1) 配置 `ENV=test` 且 `ENABLE_TEST_SEED_API=true`，并确保无 `OPENAI_API_KEY`。
  2) 现状：`get_workflow_chat_llm()` 在 `env=test` 分支优先返回 `LangChainWorkflowChatLLM(api_key="test")`，未优先使用 deterministic stub。
  3) 若测试未显式 patch（或 patch 漂移），可能触发真实网络或产生非 deterministic 行为。
  - 预期修复后：`enable_test_seed_api=true` 且无 key 时必选 deterministic stub；并用组合测试覆盖三种分支（以测试断言为准）。

**交付物**
- 本文档更新：补充“基线值/复现步骤/预期行为”。

**验收标准（严格）**
- 每个 P0 问题都具备“可重复触发 + 可判断是否修复”的复现说明（或测试用例）。

**阶段审查门禁（红队）**
- 复现步骤必须“独立于个人环境猜测”（写清必要 env/前置条件）。
- 复现判定必须可自动化（能转成测试断言）。

---

### 阶段 1（P0）：修复 SSE 终止语义（不允许 30s 尾部卡死）

**目标**
- 任意错误/断连/cleanup 路径都能可靠终止 SSE（发 error 后紧跟 END / [DONE]）。

**核心改动建议（最小变更）**
1) 修改 `ConversationFlowEmitter.complete_with_error()`：
   - 发送 error 后 **必须**发送 END（可复用 `complete()`）。
2) 同步修复 `ReliableEmitter.complete_with_error()`（避免同类缺陷在其它流中复发）。
3) 复核 `SSEEmitterHandler`：确保 client_disconnected cleanup 不会造成“error 事件之后不结束”。

**测试补齐（必须）**
- 后端 unit：`complete_with_error()` 后迭代应能读到 `ERROR` + `END`。
- 后端 integration：模拟 client_disconnected 或 error 事件，断言 SSE 文本包含 `[DONE]` 且连接及时结束。

**验收标准（严格）**
1) 在默认 timeout=30s 情况下：触发 error 后 SSE **不允许**等待超时才结束（应在 <1s 内结束；以测试断言为准）。
2) 不出现 `SSE_ERROR` 二次错误事件（除非真实编码异常）。
3) 对 chat-create/chat-stream 两条 SSE 链路均验证通过（不可只测一个）。

**阶段审查门禁（红队）**
- 检查“重复结束/重复写入”风险：多次调用 cleanup 不应产生重复 END 或抛异常。
- 检查“已完成 emitter 再 emit”是否仍 fail-fast（EmitterClosedError 行为应保持）。

---

### 阶段 2（P0）：统一 Runs 执行口径（前后端必须一致，且 fail-closed）

**目标**
- 当 Runs 开启：execute/stream 必须具备 run_id 且 run 已创建成功；任何不满足条件都必须 **前端阻止** 或 **后端给出明确错误并前端可解释**。
- 当 Runs 关闭：前后端一致走 legacy（不依赖 run_id），且 UI 文案明确。

**核心决策（必须先定）**
- **决策 D2-1：前端不再“猜测降级”**。
  - 若 Runs 开启但 Run 创建失败：前端直接 fail-closed，不允许调用不带 run_id 的 execute/stream。
  - 若希望 legacy：只能通过后端 `disable_run_persistence=true`（并由 UI 感知该状态）实现。

**核心改动建议（最小变更）**
1) 扩展 capabilities：在 `constraints` 中新增 `run_persistence_enabled`（以及可选的 `execute_stream_requires_run_id`）
   - 后端填充：`run_persistence_enabled = (not settings.disable_run_persistence)`
   - 前端依据 capabilities 决定是否需要 run_id，不再依赖 `VITE_DISABLE_RUN_PERSISTENCE`（或至少做一致性校验并 fail-closed）。
2) 前端 `handleExecute`：
   - Runs 开启且缺 projectId → 明确提示“缺少 projectId，无法创建 Run，无法执行”，并不触发 execute。
   - Run 创建失败 → 明确提示并不触发 execute。
3) 更新/补齐前端单测：修复 mock 导出缺失，使 fail-closed 行为可被断言。

**测试补齐（必须）**
- 前端 unit：
  - Run 创建失败 → `executeWorkflowStreaming` 不被调用（恢复并通过 `WorkflowRunFailClosed`）。
  - Runs 开启但缺 projectId → 不执行 + 提示明确。
  - Runs 关闭 → 允许 legacy 执行（不带 run_id）且后端不报 400。
- 后端 integration：
  - Runs 开启且缺 run_id → 400 且错误信息稳定可解释；
  - Runs 关闭 → execute/stream 可正常返回 SSE（或至少不因 run_id 缺失而 400）。

**验收标准（严格）**
1) **不会出现“UI 提示已降级但实际 400”的误导**。
2) Runs 开启时：前端永不发送无 run_id 的 execute/stream 请求。
3) capabilities 与实际行为一致：前端根据 capabilities 自动适配，无需人工同步环境变量。

**阶段审查门禁（红队）**
- 检查“开关不一致”风险：若仍保留 `VITE_DISABLE_RUN_PERSISTENCE`，必须检测与 capabilities 冲突并 fail-closed。
- 检查“幂等/重入”风险：同一 run_id 重复点击执行必须被后端 gate（现有 duplicate claim）正确拒绝且可解释。

---

### 阶段 3（P1）：统一 deterministic/测试模式（避免隐式触网）

**目标**
- 在 `enable_test_seed_api=true` 的环境中，对话链路必须“离线可复现”，不依赖 OpenAI key，也不触网。

**核心改动建议**
1) 调整 `get_workflow_chat_llm()` 的分支优先级：
   - `enable_test_seed_api=true` 且无 `OPENAI_API_KEY` → 必须返回 deterministic stub；
   - `env=test` 的 LangChain dummy key 仅用于“明确需要 patch ChatOpenAI”的测试场景（并需要测试覆盖其不触网）。
2) 增加后端测试：覆盖三种组合
   - (test + enable_test_seed_api=true + no key) → deterministic；
   - (test + enable_test_seed_api=false + no key) → LangChain dummy；
   - (non-test + enable_test_seed_api=false + no key) → 503。

**验收标准（严格）**
- 在 `.env.test.example` 的配置下：chat-create/chat-stream 任何路径都不触发真实网络请求（通过测试或运行时拦截验证）。

**阶段审查门禁（红队）**
- 检查“测试被动依赖 patch”的风险：任何未 patch 的测试不应隐式触网。

---

### 阶段 4（P1）：消除 enum/文档/Stub 漂移（合同=事实源）

**目标**
- capabilities（SoT 合同）/deterministic stub/文档示例 三者必须一致；UI 展示/编辑不会出现“值不在枚举中”的不可解释状态。

**核心决策（必须先定）**
- **决策 D4-1：以 capabilities enum 为准，修正 stub 与文档**（优先 KISS）。
  - 将 deterministic stub 的 textModel/structuredOutput 默认 model 调整为 capabilities 允许集合中的值（例如 `openai/gpt-4`）。
  - 同步修正文档示例（`workflow-usability-acceptance-criteria-table.md` 等）中的模型值，避免诱导 drift。

**必要补测**
- 前端：当节点已有值不在 enum 中时的表现策略（建议 fail-closed：展示 “unknown value” + 禁止保存，或提供显式修复入口）。
- 后端：若选择进一步“强约束 enum”，则 SaveValidator 必须与合同一致（否则合同退化为“UI 建议”会再次漂移）。

**验收标准（严格）**
1) deterministic stub 生成的工作流：
   - UI 打开 config panel 时不出现空选项/不可展示；
   - 可保存（SaveValidator 不报 enum 冲突）。
2) 文档中的最小可执行配置示例可在 deterministic 回归中真实跑通（至少 1 条 e2e 或 integration）。

**阶段审查门禁（红队）**
- 检查“合同漂移复发点”：禁止在 UI/Stub/Docs 中硬编码与 capabilities 不一致的 enum 值。

---

### 阶段 5（P1）：解决“孤立节点陷阱”（对话可修复性）

**目标**
- 用户通过 chat 修改工作流时，不会生成“chat 无法再修复”的隐性垃圾节点；若历史数据已存在孤立节点，必须提供可操作的清理路径。

**方案（建议双管齐下，确保‘完全解决’）**
1) **预防（强约束）**：chat 修改成功时，新增节点必须进入 start->end 主连通子图；否则拒绝并返回结构化错误（含 node 名称/引用）。
2) **治理（修复入口）**：提供一键清理 unreachable 节点的能力（优先前端本地操作，或后端提供专用 endpoint）。
   - 最小实现：前端按钮“清理未连通节点”= 删除非主连通子图节点 + 相关边，然后保存（仍走 SaveValidator）。

**测试补齐（必须）**
- 后端 domain/unit：`_apply_modifications` 对“新增但未连通”应拒绝（返回 workflow_modification_rejected + 可定位信息）。
- 前端：清理按钮能移除孤立节点且保存成功（最少 1 个单测/集成测）。

**验收标准（严格）**
- 对话链路不会产生“看不见/删不掉”的节点；历史孤立节点可通过 UI 一键清理并持久化。

**阶段审查门禁（红队）**
- 检查“Draft 策略”与“chat UX”的冲突：即使 draft 允许非主子图存在，chat 也必须保证可修复性（否则就是 UX bug）。

---

### 阶段 6：测试矩阵补齐与回归门禁（收口）

**目标**
- 把本次修复纳入 `docs/planning/workflow-usability-test-matrix.md` 的 P0/P1 门禁，确保未来不回归。

**工作项**
1) 更新补测矩阵：新增 P0 条目
   - SSE：error 后必须 [DONE] 结束；
   - Runs：Run 创建失败必须 fail-closed，不得误导降级；
   - deterministic：enable_test_seed_api 下不触网。
2) 修复并运行前端 `WorkflowRunFailClosed`（保证测试真实覆盖到 UI 行为）。
3) 全量回归：
   - 后端：unit + integration；
   - 前端：vitest；
   - e2e：deterministic（至少跑通“chat-create → chat-stream → execute/stream”最短闭环）。

**验收标准（严格）**
- 相关测试全部通过；新增测试必须在 CI/本地可稳定通过（不 flaky）。

**阶段审查门禁（红队）**
- 检查测试“只测 happy path”的风险：P0 必须有负向断言（例如“绝不调用 execute”）。

---

## 4. 最终验收（Definition of Done）

当且仅当满足以下所有条件，才允许宣告“完全解决”：

1) SSE：任何 error/断连路径都能在 <1s 内结束（自动化测试断言）。
2) Runs：
   - Runs 开启：前端必须创建 run 并携带 run_id 执行；失败则 fail-closed；
   - Runs 关闭：前后端一致走 legacy，不因缺 run_id 而 400。
3) deterministic：`enable_test_seed_api=true` 时 chat 相关链路不触网。
4) enum/文档/Stub：不存在明显口径漂移；UI 能展示并保存 deterministic stub 输出。
5) 孤立节点：chat 不会制造不可修复垃圾；历史数据可一键清理。
6) 测试与文档：
   - 新增/修复的测试通过；
   - 相关 planning 文档（acceptance/test matrix）更新到最新口径。

---

## 5. 风险与回滚策略（必须提前写清）

1) **SSE 终止修复的回滚**：若出现流提前结束，可临时在 handler 侧增加“保证 END 发送”的兜底（但最终必须回到 emitter 层一致性）。
2) **Runs 策略回滚**：后端已有 `disable_run_persistence`，应作为唯一回滚开关；前端不得自行猜测降级。
3) **deterministic 策略回滚**：若调整 `get_workflow_chat_llm` 影响测试，可通过依赖注入 override（tests 已大量使用）过渡，但最终仍需明确优先级。

---

## 6. 阶段审查模板（每阶段必填）

> 执行每个阶段结束时，请在对应 PR/commit 或记录中补齐以下清单：

1) 变更清单：触及哪些文件/符号（列路径与关键函数）。
2) 负向测试：新增/更新哪些测试覆盖失败模式。
3) 回归结果：执行了哪些命令，结果是否稳定。
4) 红队复盘：是否存在新的 drift / 误导 / 隐式副作用路径；若有，必须在进入下一阶段前修复或记录为阻塞项。
