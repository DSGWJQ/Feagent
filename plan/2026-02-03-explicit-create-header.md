# 规划文档：默认对话入口 + 显式创建（Header Gate）+ 全量测试（含 Playwright）

## 1) 决策（本次方案的事实源）

- 默认入口：`/` 只做“自然语言澄清对话”，**绝不创建 workflow**
- 显式创建入口：保留，采用单独路由：`/workflows/new`
- 显式创建门槛：调用 `POST /api/workflows/chat-create/stream` 时必须带 header：
  - `X-Workflow-Create: explicit`
- 安全策略：**fail-closed**（不满足条件就拒绝；拒绝前不得产生任何 DB side-effect）

---

## 2) 总体目标（必须同时满足）

G1. 默认入口（`/` + `/api/conversation/stream`）**0 workflow 创建**（数据库 `workflows` 表无新增）。
G2. 输出仅自然语言；信息不足时每轮最多 1–3 个高信号澄清问题。
G3. 接入真实 LLM（OpenAI-compatible）。
G4. 防御性：即使模型越权/注入/提示词失效，也不允许 tool_call/create_node/execute_workflow/workflow_create。
G5. 全量测试通过：`pytest` + `vitest` + `playwright`（deterministic 必须通过）。

---

## 3) 关键契约（Contract，必须固化到测试）

### 3.1 显式创建契约（后端）

- **当且仅当**请求包含 `X-Workflow-Create: explicit` 时，`/api/workflows/chat-create/stream` 才允许创建 workflow
- 缺少/不匹配 header 时：
  - 返回 `403`（或 `410`，二选一固定即可）
  - **不得**创建 workflow（包括不得 `Workflow.create_base`、不得写 `projects`、不得写 `workflows`）
  - 记录审计日志（不含 message 明文）

### 3.2 默认对话契约（前后端）

- `/` 不得触发 `/api/workflows/chat-create/stream`（Network 级证据）
- `/api/conversation/stream` 的对话仅自然语言输出（不输出 JSON/代码块；除非用户明确要求）
- 对话链路只允许 respond（见 3.3）

### 3.3 respond-only 契约（后端运行时硬约束）

- ConversationAgent 的 ReAct 执行过程中：
  - action_type 只能是 `"respond"`（包含追问也属于 respond）
  - `should_continue` 默认 false（单轮输出，避免漂移）
  - 若模型返回其它 action_type：必须 runtime guard 强制降级为 respond，并审计

---

## 4) 分阶段实施计划（每阶段完成后必须审查 Go/No-Go）

### Phase 0：基线与审计（先把“0 创建”变成可证明）

范围

- 固化 header 名与值
- 明确审计日志字段
- 增加最小可执行的验证手段（测试用例计划/骨架）

交付物

- 约定常量：
  - Header：`X-Workflow-Create`
  - Value：`explicit`
- 约定错误体（示例）：
  - `{"error":"explicit_create_required","required_header":"X-Workflow-Create","required_value":"explicit"}`
- 约定审计日志事件名（示例）：
  - `workflow_chat_create_blocked`
  - `workflow_chat_create_allowed`

阶段 DoD（必须全部满足）

- 文档中明确写出 3.1/3.2/3.3 契约
- 列出 Phase 1–4 的每条验收证据（命令级别）

审查清单（Go/No-Go）

- 是否存在“无 header 仍会创建”的可能（包括先写库再报错）
- 是否能用自动化测试证明“DB 行数不变”

---

### Phase 1：前端路由与页面拆分（默认不创建）

范围（KISS + SRP）

- 将 `/` 从 `WorkflowEditorPage` 改为 `ChatPage`
- 新增 `/workflows/new` → `WorkflowCreatePage`
- `WorkflowEditorPage` 只负责编辑（必须有 `:id`），不再承担“无 id 创建”

交付物（文件级）

- `web/src/app/router.tsx`：
  - `/` → `ChatPage`
  - `/workflows/new` → `WorkflowCreatePage`
  - `/workflows/:id/edit` → `WorkflowEditorPage`
- 新增 `ChatPage`（可复用现有 `useConversationStream`：`web/src/hooks/useConversationStream.ts`）
- 新增 `WorkflowCreatePage`（承载显式创建逻辑；成功后跳转 `/workflows/:id/edit`）
- 更新 vitest：
  - 删除/重写“根路由会创建 workflow”的测试（现有用例会失败）
  - 新增：
    - `/` 不调用 `chatCreateWorkflowStreaming`
    - `/workflows/new` 才调用创建并跳转

阶段 DoD（必须全部满足）

- 手工证据：
  - 访问 `/` 发送消息：Network 只出现 `/api/conversation/stream`
  - 访问 `/workflows/new` 点击创建：Network 出现 `/api/workflows/chat-create/stream`
- 自动化：
  - `pnpm -C web test` 通过
  - `pnpm -C web build` 通过

审查清单（Go/No-Go）

- `/` 是否还有任何地方 import/调用 chat-create API（必须没有）
- `WorkflowEditorPage` 是否还存在 “!workflowId => 创建” 分支（必须移除）
- 测试是否覆盖“默认不创建”行为（必须有）

回滚

- 如需临时回滚：仅回滚前端路由（但 Phase 2 会保证后端仍 fail-closed）

---

### Phase 2：后端 Header Gate（fail-closed，防误调用与回归）

范围

- 为 `/api/workflows/chat-create/stream` 增加显式 header 校验，并且必须发生在任何 DB side-effect 之前

实现要点（必须）

- 校验位置：在 `chat_create_stream(...)` 内**最开头**，在：
  - `ProjectModel` 自动创建之前
  - `Workflow.create_base(...)` 之前
- 校验逻辑：
  - `http_request.headers.get("X-Workflow-Create") == "explicit"`（大小写可做规范化）
  - 不满足 → `HTTPException(403, detail=...)`

交付物（测试必须有）

- 后端测试 1：无 header 调用 chat-create
  - 断言 status_code=403
  - 断言 `workflows` 表行数不变
- 后端测试 2：带 header 调用 chat-create
  - 断言不是 403
  - 断言创建成功（或至少能拿到早期 workflow_id 事件）

阶段 DoD（必须全部满足）

- `python -m pytest` 全量通过
- 人工验证：
  - curl 不带 header 调用 chat-create → 403 且 DB 无新增
  - curl 带 header → 允许创建

审查清单（Go/No-Go）

- 是否真正做到“先校验再创建”（任何写库前）
- 错误信息是否可定位（包含 required_header/value）
- 审计日志是否不包含 message 明文（必须）

回滚

- 仅允许通过一个明确开关关闭 gate（紧急恢复），但默认必须开启（fail-closed）

---

### Phase 3：Conversation 接真实 LLM + respond-only（智能澄清但不执行）

范围

- ConversationAgent 使用真实 LLM（替换 fallback）
- runtime 强制 respond-only（不依赖 prompt 自觉）

交付物

- `ClarifierConversationLLM`（实现 think/decide_action/should_continue 等，输出自然语言 + 追问）
- Prompt（版本化、可配置）
- respond-only guard（必须在运行时生效）
- 测试：
  - 模拟模型越权输出 tool_call/create_node/execute_workflow → guard 强制降级为 respond
  - 断言输出问题数量 <=3（或至少在 prompt 层 + 解析层限制）

阶段 DoD（必须全部满足）

- 配好 key 时：对话能理解并追问，不创建 workflow
- 未配 key 时：可降级提示 + 追问，仍不创建 workflow
- `python -m pytest` 全量通过

审查清单（Go/No-Go）

- 是否存在任一路径可触发 tool_call/create_node/execute_workflow（必须没有）
- thinking 事件是否泄露推理链（建议只输出安全进度语句）
- 日志不泄露敏感信息

回滚

- 允许切回 fallback，但 respond-only guard 不能回滚（安全底线）

---

### Phase 4：Playwright E2E 回归（deterministic 必过）

范围

- 调整/新增 e2e 用例以匹配新入口语义

必须覆盖的 e2e 用例（至少 3 条）

1) Home Chat (no workflow)

- `page.goto('/')`
- 发送消息
- 断言出现 assistant 自然语言输出
- 断言未跳转到 `/workflows/` 路径
- 断言**没有**请求 `/api/workflows/chat-create/stream`（用 `page.on('request')` 观察）

2) Explicit Create (header required)

- `page.goto('/workflows/new')`
- 点击创建
- 观察到请求 `/api/workflows/chat-create/stream`
- 断言该请求带 header：`x-workflow-create: explicit`
- 断言最终跳转 `/workflows/:id/edit`

3) Editor Direct

- 直达 `/workflows/:id/edit`（用 seed 或已有 id）
- 断言编辑器可渲染

阶段 DoD（必须全部满足）

- `pnpm -C web test:e2e:deterministic` 通过
- （如你把 hybrid/fullreal 也算发布门槛）对应命令通过

审查清单（Go/No-Go）

- e2e 是否仍依赖“首页自动创建”（必须移除）
- Header 断言是否真实检查到（不是假设）

回滚

- 若 fullreal 不稳定：允许将 fullreal 作为 nightly，但 deterministic 必须作为强制门槛

---

## 5) 最终全量测试门槛（Release Gate）

必须全部通过：

- 后端：`python -m pytest`
- 前端：`pnpm -C web test`
- 前端构建：`pnpm -C web build`
- e2e：`pnpm -C web test:e2e:deterministic`

---

## 6) 你已确认的选择（记录）

- 显式创建入口：保留
- 入口形态：`/workflows/new`
- 显式创建门槛：header（`X-Workflow-Create: explicit`）

---

## 7) 开放问题（若要进入实施阶段必须回答）

- chat-create 缺少 header 时返回码选 `403` 还是 `410`？（推荐 `403`）
- Playwright 需要跑到哪个档位作为“完整测试”门槛？
  - 必须：deterministic
  - 可选：hybrid/fullreal
