# Workflow 能力事实源统一：三里程碑交付规划（严格验收）

> 目标：解决“经常做不出真正完成任务的 workflow”的根因：**能力口径漂移 + UI 缺少必要表达/防呆 + 缺少 deterministic 端到端回归**。
> 原则：所有能力对外口径以“编辑器工作流链路（NodeType/ExecutorRegistry/WorkflowSaveValidator/UI）”为准；对话与文档只能描述该事实源可证明的能力。

---

## 0. 背景：为什么经常做不出真正完成任务的 workflow

高频失败原因通常不是“执行器不够多”，而是以下三类系统性缺陷叠加：

1) **能力口径漂移（Contract Drift）**
   - 对话/文档/前端/后端各自维护节点清单与字段约束，且不同步；最终出现“保存通过但执行必失败”或“对话生成的图 UI 根本配不出来”的必败链路。
2) **关键节点缺少表达能力或防呆（尤其是多输入 textModel）**
   - runtime 对多入边的 prompt 来源有硬约束（必须指定 `promptSourceNodeId` 或先用 Prompt 节点合并输入），但 UI 未提供配置入口 → 用户/LLM 极易生成必败图。
3) **缺少 deterministic e2e 回归门禁**
   - 没有把“用户真实操作路径”固化为 Playwright 测试；靠人工点 UI 才能发现回归，漂移会反复出现。

---

## 1. 全局原则（必须遵守）

### 1.1 单一事实源（Source of Truth）

本规划的“能力事实源”定义为以下四项的交集（缺一不可）：

- `NodeType`（含兼容别名）：`src/domain/value_objects/node_type.py`
- 执行器注册：`src/infrastructure/executors/__init__.py:create_executor_registry`
- 保存前强校验：`src/domain/services/workflow_save_validator.py`
- UI 可拖拽节点集合与配置面板：`web/src/features/workflows/utils/nodeUtils.ts` + `web/src/features/workflows/components/NodeConfigPanel.tsx`

> 结论：对话 prompt、文档与 UI 展示 **必须从同一份结构化能力定义生成**；禁止再出现硬编码节点列表/字段规则。

### 1.2 P0 定义（零容忍）

只要出现任一情况，视为 P0，必须在合入前修复：

- **保存通过但执行必失败**（或“在 deterministic 环境必失败”）
- UI 允许用户生成/保存一个图，但 runtime 的硬约束必然拒绝/失败（例如多入边 textModel 无 promptSource）

### 1.3 验收与审查机制（每个里程碑都必须做）

每完成一个 Milestone，必须执行：

1) **严格测试门禁**（见各里程碑“测试要求”）全部通过
2) **架构/逻辑审查**：按“审查清单”逐项自检，确认没有引入新的漂移源或隐性耦合
3) **更新本文件的“执行记录”**（在对应里程碑末尾追加：完成日期、变更摘要、测试结果、遗留风险）

---

## 2. Milestone 1：能力矩阵/Schema 端点（能力事实源可机器消费）

### 2.1 目标

新增一个后端端点，输出“编辑器工作流能力矩阵/Schema”，供 UI 与对话 prompt 统一消费，彻底消除硬编码口径漂移。

### 2.2 交付物

- 新增 API：`GET /api/workflows/capabilities`（建议版本化：`schema_version` 字段）
- 新增“能力规则 spec”（一处定义，多处复用）：
  - 输出能力矩阵
  - 驱动 `WorkflowSaveValidator` 的必填/条件规则（至少覆盖：required 字段、条件必填、多输入约束、JSON 字段可解析）
- 单元测试：确保“能力矩阵 = 事实源输出”，且 spec 与 SaveValidator 不会分叉

### 2.3 实施步骤（建议顺序）

1) 定义能力矩阵返回结构（Pydantic Model），字段至少包含：
   - `schema_version`
   - `node_types[]`: `{ type, aliases[], executor_available, validation_contract, runtime_notes }`
2) 抽取可复用的 contract spec（例如 `workflow_node_contracts.py`），将 SaveValidator 的关键规则迁移到 spec（先抽“声明式规则”，保留现有校验代码结构，避免一次性大重构）。
3) 端点实现：从 `NodeType + executor_registry + contract spec` 动态生成能力矩阵（禁止手写节点列表）。
4) 将端点接入到 FastAPI（单独 router 文件，避免继续膨胀 `routes/workflows.py`）。

### 2.4 严格验收标准（必须全部满足）

- **SoT 一致性**：`/api/workflows/capabilities` 输出的 `node_types` 集合必须可由代码推导（NodeType/registry/spec），不得硬编码。
- **无第三套口径**：UI 与对话 prompt 后续改造必须只读该端点/同一 spec（M2 里完成接入）。
- **可解释性**：每个 node type 必须包含最小可执行约束（required/conditional/json fields/multi-input rules/tool env notes）。
- **回归安全**：修改任一节点的 required 字段，只需要改 spec 一处，并能通过测试证明 SaveValidator 与 capabilities 同步变化。

### 2.5 测试要求（必须通过）

- Python（单测）：
  - capabilities 端点返回结构与字段完整性测试
  - spec 与 SaveValidator 规则一致性测试（至少覆盖 3 类：required、conditional、multi-input）
  - 关键 P0 回归：保存通过但执行必失败（典型用例：http/path→url、loop for→range）
- 建议命令：
  - `python -m pytest -q --import-mode=importlib --ignore=tests/manual`

### 2.6 审查清单（完成后必须自检）

- 端点是否引入了新的硬编码节点列表？（必须为否）
- spec 是否成为唯一“字段约束事实源”？（必须为是）
- SaveValidator 是否仍存在“只校验一半字段”的漂移风险？（必须为否，至少覆盖 UI 暴露节点）

### 2.7 执行记录（完成后填写）

- 完成日期：2026-02-01
- 变更摘要：
  - 新增 editor workflow 单一能力/校验事实源：`src/domain/services/workflow_node_contracts.py`
  - 新增能力矩阵端点：`GET /api/workflows/capabilities`（`src/interfaces/api/routes/workflow_capabilities.py`）
  - `WorkflowSaveValidator` 改为读取同一份 contract spec（避免 required/conditional/json/multi-input 规则漂移）
  - 新增合同测试：`tests/integration/api/workflows/test_workflow_capabilities_api.py`
  - 更新补测矩阵：`docs/planning/workflow-usability-test-matrix.md`（P2 DONE）
- 测试结果：
  - `python -m pytest tests/unit/domain/services/test_workflow_save_validator.py -q --no-cov`
  - `python -m pytest tests/integration/api/workflows/test_workflow_capabilities_api.py -q --no-cov`
- 遗留风险：
  - loop 的 `invalid_end`/`invalid_max_iterations` 等数值约束仍在 SaveValidator 内部实现，尚未完全声明式化到 spec
  - UI/对话侧尚未接入 capabilities endpoint（将在 Milestone 2 完成）

---

## 3. Milestone 2：对话 prompt 统一 + textModel 多入边 UI 防呆

### 3.1 目标

让“对话生成/修改工作流”和“UI 配置/保存/运行”在关键约束上彻底一致，尤其是 textModel 多输入场景，避免生成必败图。

### 3.2 交付物

- 对话 prompt（WorkflowChat）不再硬编码 supported node list：
  - 改为从 M1 的能力矩阵（或同一 contract spec）生成
  - 至少包含：multi-input textModel 规则、tool 依赖与 tool_id 规则、loop/range 口径
- UI：textModel 节点在多入边时提供 `promptSourceNodeId` 配置能力，并在必要时强制用户选择或引导插入 Prompt 合并节点
- 对 deterministic LLM stub/策略：若生成多入边 textModel，必须同时生成合法的 `promptSourceNodeId` 或插入 Prompt 节点（避免测试/演示链路漂移）

### 3.3 实施步骤（建议顺序）

1) 对话 prompt 改造：
   - 由能力矩阵渲染“支持节点类型 + 关键约束”片段（不要重复维护）
2) UI 改造（最小可用版本）：
   - 当 textModel 入边数 > 1 且 prompt 为空时：
     - 在 NodeConfigPanel 展示 `promptSourceNodeId` 下拉框（候选：所有上游节点 id/name）
     - 保存前必须通过前端校验（否则禁止保存/运行）
3) UI 改造（可选增强）：
   - 一键插入 Prompt 合并节点：自动改图（插入 Prompt，并将多入边先连到 Prompt，再连到 textModel）
4) 后端保持 fail-closed：SaveValidator 对多入边规则继续作为最后防线（UI 只是第一道门）。

### 3.4 严格验收标准（必须全部满足）

- **无硬编码**：WorkflowChat 的 supported node list/关键规则必须来自能力矩阵/spec（必须为真）。
- **多入边 textModel 可用性**：
  - UI 能把多入边 textModel 配到可保存可执行状态（必须为真）
  - 用户无法保存一个“多入边 + 无 promptSource + 无 Prompt 合并”的必败图（必须为真）
- **回归兼容**：已有单入边 textModel / 已配置 prompt 的 workflow 不受影响（必须为真）。

### 3.5 测试要求（必须通过）

- Python（单测）：
  - SaveValidator 对 multi-input textModel 的拒绝/通过用例
  - WorkflowChat prompt 生成片段包含 multi-input 规则（防止回退到旧硬编码）
- Web（单测，Vitest）：
  - NodeConfigPanel 在多入边场景下显示 promptSource 选择器、并对空值阻止保存的测试

### 3.6 审查清单（完成后必须自检）

- UI 是否把“后端必需字段”变成“用户可表达字段”？（必须为是）
- UI/对话/SaveValidator 是否共用同一份约束来源？（必须为是）
- 是否新增了新的“隐藏规则/魔法字段”？（必须为否）

### 3.7 执行记录（完成后填写）

- 完成日期：2026-02-02
- 变更摘要：
  - 对话侧：`WorkflowChatServiceEnhanced` 的 system prompt 不再手写节点清单与关键约束，改为从能力事实源 spec 渲染（避免 contract drift）。
  - UI：`NodeConfigPanel` 在 `textModel` 多入边且无内置 prompt 时强制要求选择 `promptSourceNodeId`，并在保存节点配置前执行 `form.validateFields()` 阻止保存必败配置。
  - 前端调用方：`WorkflowEditorPageWithMutex` 传入 `nodes/edges` 供面板计算入边与候选上游节点。
  - 补齐前端单测：覆盖 OpenAI-only 选项暴露与多入边 promptSource 必填阻断。
- 测试结果：
  - `python -m pytest tests/unit/domain/services/test_workflow_save_validator.py -q --no-cov`
  - `python -m pytest tests/unit/domain/services/test_workflow_chat_service_enhanced.py -q --no-cov`
  - `npm --prefix web test -- src/features/workflows/components/__tests__/NodeConfigPanel.test.tsx`
- 遗留风险：
  - UI/对话目前直接读取后端同仓 spec（而非通过 `/api/workflows/capabilities`），仍需在 Milestone 3/后续阶段评估是否统一改为消费端点以隔离前后端发布节奏。
  - 多入边 textModel 若用户从未打开配置面板，仍可能在保存 workflow 时被后端 fail-closed 拒绝；需要确认 UI 对保存失败的错误展示是否足够可定位（节点 id/type + hint）。

---

## 4. Milestone 3：固化 deterministic Playwright e2e（语义完成度断言）

### 4.1 目标

把“真实用户操作路径”固化为 deterministic e2e，且断言“任务语义完成”（而不是只看 workflow_complete/文案），作为防漂移硬门禁。

### 4.2 交付物

- 新增 `web/tests/e2e/deterministic/workflow-data-cleaning.spec.ts`
  - 覆盖：chat-create → 进入编辑器 → 保存 → 设置 Input(JSON) → 运行 → 断言输出语义正确
- 必要的 `data-testid` 补齐（避免用文案/placeholder 作为选择器导致 flaky）

### 4.3 实施步骤（建议顺序）

1) 为关键 UI 元素补齐 testid（最小集合）：
   - chat-create 输入框/提交按钮
   - “同步到画布”按钮（当测试覆盖 chat-stream 修改时必需）
   - 执行结果容器（用于提取结构化 result）
2) 编写 deterministic e2e：
   - 输入固定 JSON（包含重复、空值、数字字符串/浮点字符串、不可转换值）
   - 断言：去重、去空、类型转换结果符合预期（语义断言）
3) 将 e2e 纳入日常回归（本地一键、CI 可选）。

### 4.4 严格验收标准（必须全部满足）

- deterministic e2e 必须 **离线可跑**（不依赖真实 LLM/真实外部 HTTP）
- 断言必须包含“语义完成度”：
  - 去重：重复记录合并/删除
  - 去空：空字符串/null 字段被剔除或归一
  - 类型转换：数字字符串转为 int/float；不可转换值策略明确且可断言
- e2e 失败时必须具备定位能力（至少：trace/screenshot + 对应 workflow_id 输出）。

### 4.5 测试要求（必须通过）

- `npm --prefix web run test:e2e:deterministic`
- 建议同时跑最小前端单测集（避免 e2e 掩盖基础回归）：
  - `npm --prefix web test`

### 4.6 审查清单（完成后必须自检）

- e2e 选择器是否全部使用 `data-testid` 或稳定语义定位？（必须为是）
- e2e 是否断言“结果语义”而非仅“执行成功”？（必须为是）
- 是否仍存在“手工点 UI 才能发现的漂移”？（必须为否，至少覆盖核心链路）

### 4.7 执行记录（完成后填写）

- 完成日期：2026-02-02
- 变更摘要：
  - 新增 deterministic UI e2e：`web/tests/e2e/deterministic/workflow-data-cleaning.spec.ts`（chat-create → 进入编辑器 → 保存 → 配置 Input(JSON) → Run → 断言输出语义：去重/去空/类型转换）。
  - 补齐稳定选择器与结果出口（避免用文案/placeholder 做选择器导致 flaky）：
    - `web/src/features/workflows/pages/WorkflowEditorPage.tsx`：为 chat-create 输入框/提交按钮补齐 `data-testid`，并将获取 `workflow_id` 的超时从 10s 放宽到 20s（Windows + SQLite 冷写入更慢）。
    - `web/src/features/workflows/pages/WorkflowEditorPageWithMutex.tsx`：暴露隐藏 DOM `data-testid="workflow-final-result"`（JSON.stringify(finalResult)）供 Playwright 断言；为 Input modal 的 OK/Cancel 补齐 `data-testid`。
  - 让 deterministic e2e 默认可跑通 Runs API 路径并降低超时误报：
    - `web/tests/e2e/helpers/backend.ts`：deterministic 模式下默认注入 `DISABLE_RUN_PERSISTENCE=false`（允许通过 `.env.test`/process.env 显式覆盖）。
    - `web/playwright.config.ts`：deterministic 项目单测超时上限调整为 120s；并对复杂用例提升单用例 timeout（007/008/009）。
    - 对历史 flaky 用例补齐 `page.goto(..., { waitUntil: 'domcontentloaded', timeout: 60_000 })` 等显式导航超时（001/006/102）。
  - 修复 chat-create SSE 序列化崩溃：`src/interfaces/api/services/sse_emitter_handler.py` 使用 `jsonable_encoder` 防止 `datetime/UUID` 等导致断流。
- 测试结果：
  - `npm --prefix web run test:e2e:deterministic`
- 遗留风险：
  - chat-create 当前未显式传入 `project_id`；当后端启用 Runs API 且 UI 未提供 projectId 时，执行路径可能无法创建 run（本次 e2e 通过 query param 注入 projectId 规避）。需要在后续阶段统一“workflow 归属 project”的默认策略与 UI 选择入口。
  - `web/tests/e2e/helpers/backend.ts` 仍会提示缺少 `.env.test`（目前 fallback 到 process.env，不阻塞）。

---

## 5. 总体验收（Release Gate）

当三里程碑全部完成后，才允许宣称“可用性闭环稳定”，需要满足：

- `/api/workflows/capabilities` 已成为 UI 与对话 prompt 的唯一能力来源（无硬编码回退）
- textModel 多入边在 UI 上可表达、可配置、可保存、可执行（fail-closed + UX 防呆）
- deterministic Playwright e2e 能稳定复现“任务完成”，并作为回归门禁

### 5.1 执行记录（完成后填写）

- 完成日期：2026-02-02
- 变更摘要：
  - Chat-create 默认归属 project（Runs API 可执行路径必需）：
    - 后端：`src/interfaces/api/routes/workflows.py` 在 chat-create 时 fail-closed 生成/归属 `project_id`，并确保 `projects` 表存在该行（避免 `runs.project_id` FK 失败）。
    - 前端：`web/src/features/workflows/pages/WorkflowEditorPage.tsx` chat-create 请求显式传 `project_id`，并导航携带 `?projectId=`（避免 editor 初始加载 race）。
  - Deterministic e2e env 降噪：
    - `web/tests/e2e/helpers/backend.ts` 自动回退读取 `.env.*.example`（`.env.test` 等缺失不再告警）；`.env.test.example` 提供 deterministic 最小默认值。
  - UI 统一消费 capabilities（无硬编码回退）：
    - `web/src/features/workflows/components/NodePalette.tsx` 与 `web/src/features/workflows/components/NodeConfigPanel.tsx` 通过 React Query 拉取 `GET /api/workflows/capabilities`；能力不可用时 fail-closed（不允许在未知能力边界下编辑/添加节点）。
    - `src/domain/services/workflow_node_contracts.py` 增补 UI 需要的 enum 元信息（如 model/voice/aspectRatio/outputFormat/method），由 capabilities 输出统一驱动 UI 下拉选项。
- 测试结果：
  - `python -m pytest tests/unit/domain/services/test_workflow_save_validator.py -q --no-cov`
  - `python -m pytest tests/unit/domain/services/test_workflow_chat_service_enhanced.py -q --no-cov`
  - `python -m pytest tests/integration/api/workflows/test_workflow_capabilities_api.py -q --no-cov`
  - `npm --prefix web test -- src/features/workflows/components/__tests__/NodeConfigPanel.test.tsx`
  - `npm --prefix web run test:e2e:deterministic`
- 遗留风险：
  - 目前 `nodeTypeConfigs` 仍为 UI 展示元数据（label/icon/color），但节点“可用性/可执行性/字段约束”已以 capabilities 为唯一事实源；后续如新增节点类型需补齐展示配置。
