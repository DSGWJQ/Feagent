# 工作流核心业务与多智能体协作模式审计报告（严格版，围绕 CoordinatorAgent）

> 报告目的：在“完全理解项目既定前提”的前提下，对照你提出的业务约束逐条验收当前实现，识别逻辑漏洞/架构漂移/DDD 越界，并给出可落地的收敛建议与验收标准。

---

## 1. 项目既定前提（你要求必须成立的系统不变式）

1) **创建 Workflow**：只有一条链路——对话创建工作流（chat-create）。
2) **修改 Workflow**：两条链路——拖拽修改与对话修改（包含增删节点/边/工具节点）。
3) **执行 Workflow**：只有一条链路——并且这条链路与 **WorkflowAgent** 完全一致（语义、状态、事件、成功判定一致）。
4) **Tool 与 Node 统一**：工具是节点的一种能力表达；对话修改工作流时必须能识别并引用工具；保存前必须保证可执行性。
5) **CoordinatorAgent 是核心**：所有对话入口必须进入 Coordinator 的监督域；Coordinator 能阻断/纠偏对话 Agent 的偏航。
6) **严格审查 ConversationAgent 的 ReAct 范式**：Thought→Action→Observation 必须闭环且 Observation 来自真实执行。
7) **“执行成功”与用户点击 Run 一致**：前后端对 Run 的事实源一致，可追踪可回放。
8) **必须使用 LangGraph**：尤其是 Workflow 执行链路（不是只在 Agent Run 用例里使用）。
9) **WorkflowAgent ↔ ConversationAgent 协作**：WFPLAN-050 选择 OptionB（不作为 workflow 主链路验收项）；保留为 Agent 子系统能力审计与实验入口。
10) **DDD 分层不越界**：Interface/Application/Domain/Infrastructure 依赖方向正确，入口唯一性可被强制。

---

## 2. 审计基线：仓库“设计前提”与“实现现状”的来源

本报告同时参考：
- **统一架构重构计划**：明确指出“REST 执行绕过 Coordinator、Tool/Node 分离、Coordinator 被动”等，并给出目标架构与实施顺序。
  证据：`docs/architecture/WORKFLOW_UNIFIED_ARCHITECTURE_PLAN.md:1`
- **多 Agent 协作架构**：描述了 Coordinator 作为 EventBus 中间件拦截决策、WorkflowAgent 执行并回馈事件的闭环。
  证据：`docs/architecture/multi_agent_orchestration.md:1`、`docs/architecture/multi_agent_collaboration_guide.md:1`
- **DDD 边界约束**：`.import-linter.toml` 明确 Interface 不能依赖 Domain Agents 等合同约束。
  证据：`.import-linter.toml:1`

重要补充：仓库部分文档与代码存在漂移（例如 chat 功能实现状态），这本身会制造“团队认知漏洞”。
证据：`docs/WORKFLOW_CHAT_GUIDE.md:1`、`src/interfaces/api/routes/chat_workflows.py:1`

---

## 3. 逐条验收结论（Compliance Matrix）

| 前提条款 | 期望实现 | 当前验收 | 关键证据（可点击定位） |
|---|---|---|---|
| 创建只有对话创建 | 仅保留 chat-create | ✅ 满足：仅保留 `POST /api/workflows/chat-create/stream`；并在落库前执行 coordinator preflight gate（拒绝=0 副作用边界）。 | `src/interfaces/api/routes/workflows.py:563`、`tests/integration/api/workflow_chat/test_chat_create_stream_api.py:1` |
| 修改两条链路（拖拽+对话） | 拖拽 + 对话均可增删节点/边 | ✅ 满足：拖拽 `PATCH` 与对话 `chat/chat-stream` 均存在；落库前统一走 `WorkflowSaveValidator`（fail-closed）。 | `src/interfaces/api/routes/workflows.py:301`、`src/interfaces/api/routes/chat_workflows.py:24`、`src/domain/services/workflow_save_validator.py:65`、`tests/integration/api/workflows/test_workflow_validation_contract.py:108` |
| 执行只有一条且=WorkflowAgent | 所有执行入口复用 WorkflowAgent | ❌ 未满足：`/execute/stream` 走 `workflow_execution_kernel`，但尚无证据证明与 `WorkflowAgent` 执行语义/事件/成功判定同源。 | `src/interfaces/api/routes/workflows.py:359`、`src/interfaces/api/main.py:102`、`src/domain/agents/workflow_agent.py:2348` |
| Tool 与 Node 统一且可识别 | 单一能力注册中心；tool_id 可解析 | ⚠️ 部分满足：保存/执行已强制 `tool_id` + executor 存在性校验（fail-closed），但能力真源仍多套并存，未形成“唯一映射”。 | `src/domain/services/workflow_save_validator.py:152`、`src/domain/services/tool_engine.py:248`、`src/interfaces/api/routes/tools.py:1` |
| Coordinator 是核心入口并监督 | 所有对话进入监督域 | ✅ 满足：chat-create/chat-stream/execute/stream 均有 `CoordinatorPolicyChain`；拒绝语义统一为 `403 detail.error=coordinator_rejected` 或 SSE `error_code=COORDINATOR_REJECTED`，且 chat-create 拒绝不落库。 | `src/interfaces/api/routes/workflows.py:427`、`src/interfaces/api/routes/workflows.py:563`、`src/application/use_cases/update_workflow_by_chat.py:110`、`src/interfaces/api/services/event_bus_sse_bridge.py:1` |
| 严格 ReAct（对话） | Action 可执行；Observation 来自真实执行 | ✅ 满足：`tool_call` 会触发真实执行并 emit `tool_result`（success/failed 均闭环）；Observation 可审计。 | `src/domain/agents/conversation_agent_react_core.py:436`、`src/domain/services/conversation_flow_emitter.py:308`、`tests/unit/domain/agents/test_conversation_agent_react_core.py:216` |
| Run 一致（点击 Run=事实源） | run_id 落库/回放一致 | ✅ 满足：已提供 Run 创建（幂等）+ `/execute/stream` 强制 `run_id` 并落库关键事件 + `/api/runs/{run_id}/events` 回放 API。 | `src/interfaces/api/routes/runs.py:93`、`src/interfaces/api/routes/runs.py:238`、`tests/integration/api/runs/test_run_events_replay_api.py:76` |
| workflow 必须使用 LangGraph | workflow 执行由 LangGraph 驱动 | ⚠️ 未默认满足：LangGraph workflow executor 现为 feature-flag 路径（可开关），默认仍走 Domain workflow engine kernel。 | `src/infrastructure/lc_adapters/workflow/langgraph_workflow_executor_adapter.py:1`、`src/config.py:138` |
| WorkflowAgent 验证计划可达成 | plan validation + 反馈闭环 | ⚠️ 非主链路：WFPLAN-050 选择 OptionB（多智能体闭环不作为 workflow 主链路验收项）；保留为 Agent 子系统能力审计与实验入口。 | `docs/architecture/current_agents.md:1`、`src/domain/services/decision_execution_bridge.py:1` |
| DDD 不越界 | 单向依赖可强制 | ⚠️ 存量未清：仍存在跨层 import（需用 CI/contract 强制收敛），当前仅能保证“不新增越界”而非“已合规”。 | `.import-linter.toml:1`、`src/domain/services/workflow_chat_service_enhanced.py:247` |

> **P0 结论（基于当前代码/测试证据）**：已落地 “保存前 fail-closed 校验 / 事件语义契约（execute/stream 仅允许 node_*/workflow_*）/ chat-stream 伪 ReAct 纠正（planning_step simulated）/ chat-create 前置 coordinator gate（拒绝=0 副作用）/ Run 创建 + run_id 强制 + 关键事件落库 + 回放 API”；同时 WFPLAN-050 选择 OptionB（多智能体闭环不作为 workflow 主链路）。但 “workflow 执行链路与 WorkflowAgent 同源 / workflow 默认 LangGraph / DDD 边界存量清零” 仍未闭环。

### 3.0 修复状态索引（WFPLAN）

- ✅ `WFPLAN-010`：冻结 execute/stream 事件契约（仅 `node_*`/`workflow_*`），违约 fail-closed 输出 `workflow_error`（`error=invalid_execution_event_type`）并终态落库；测试：`tests/integration/api/workflows/test_run_event_persistence.py:304`
- ✅ `WFPLAN-020`：workflow chat 的 “react_steps” 统一走 `planning_step`（`metadata.simulated=true`），不再伪装 `tool_call/tool_result`；关键词：`planning_step`；测试：`tests/integration/api/workflow_chat/test_chat_stream_react_api.py:1`
- ✅ `WFPLAN-030`：chat-create 在落库前执行 coordinator preflight gate（拒绝=0 副作用，不落库，不透传 message 明文）；关键词：`coordinator_allow`/`coordinator_deny`、`COORDINATOR_REJECTED`；测试：`tests/integration/api/workflow_chat/test_chat_create_stream_api.py:1`
- ✅ `WFPLAN-040`：legacy bypass（`disable_run_persistence=true`）必须审计日志（`run_persistence_rollback_active`）；测试：`tests/unit/interfaces/api/test_workflow_executor_adapter.py:1`
- ✅ `WFPLAN-050`：明确多智能体闭环不作为 workflow 主链路（OptionB）；主链路以 `/api/workflows/*` + `/api/runs/*` 为准（文档已更新：`README.md:1`、`docs/architecture/current_agents.md:1`）
- ✅ `WFPLAN-060`：补齐 guardrails 测试与本地检查脚本（`scripts/workflow_core_checks.ps1`）；注意：`pytest tests/unit` 目前存在大量存量失败，详见 issue notes

### 3.1 不变式验收合同（入口/契约/实现/错误码/测试点）

> 目的：把每条不变式收敛为“可验证合同”，避免报告只剩观点而无证据。

#### 3.1.1 事件语义表（三类）

1) **Workflow Chat SSE（/chat-create/stream 与 /chat-stream）**
   - `thinking`：系统侧过程提示（可用于前端占位/跳转）
   - `planning_step`：解释性回放（`metadata.simulated=true`），不得伪装为真实 `tool_call/tool_result`
   - `final`：最终结果（含 workflow 结构）
   - `error`：可诊断失败（不泄露敏感信息）

2) **Workflow Execute SSE（/execute/stream）与 RunEvent 落库**
   - `execute/stream` 的事件契约：仅允许 `node_*` / `workflow_*`（违约 fail-closed：输出 `workflow_error` 并终态落库）
   - 回放事实源：`GET /api/runs/{run_id}/events`（以事件序列还原执行过程与终态）

3) **Coordinator 拒绝语义（监督与 0 副作用边界）**
   - HTTP：`403 detail.error=coordinator_rejected`
   - SSE：`error_code=COORDINATOR_REJECTED`（由 `EventBus -> SSE bridge` 转发给活跃会话）
   - chat-create：拒绝发生在 DB commit 前（0 副作用边界）；execute/stream：拒绝发生在 Run 写入前（不产生执行副作用）

1) **创建 Workflow（chat-create，唯一入口）**
   - 入口：`POST /api/workflows/chat-create/stream`
   - 契约：首个 SSE 事件必须包含 `metadata.workflow_id`；在写入 DB 前执行 coordinator preflight gate（拒绝=0 副作用边界，不落库）。
   - 实现位置：`src/interfaces/api/routes/workflows.py:563`
   - 错误码/结构：HTTP `400`（`DomainValidationError.to_dict()`）；SSE error `DOMAIN_ERROR`/`SERVER_ERROR`。
   - 测试点：`tests/integration/api/workflow_chat/test_chat_create_stream_api.py:1`（含 coordinator 拒绝=0 副作用 + 不泄露 message 明文）；`web/src/features/workflows/api/workflowsApi.ts:164`。

2) **修改 Workflow（拖拽 + 对话，两条链路，落库前同校验）**
   - 入口：`PATCH /api/workflows/{workflow_id}`；`POST /api/workflows/{workflow_id}/chat`；`POST /api/workflows/{workflow_id}/chat-stream`
   - 契约：任何落库变更必须先通过 `WorkflowSaveValidator.validate_or_raise()`（fail-closed）。
   - 实现位置：`src/application/use_cases/update_workflow_by_drag.py:115`、`src/application/use_cases/update_workflow_by_chat.py:131`
   - 错误码/结构：HTTP `400`，`detail.code=workflow_invalid`，`detail.errors[].code` 包含 `missing_executor/missing_tool_id/cycle_detected/...`。
   - 测试点：`tests/integration/api/workflows/test_workflow_validation_contract.py:108`、`tests/unit/domain/services/test_workflow_save_validator.py:64`

3) **执行 Workflow（run_id 强制 + 可审计事件落库）**
   - 入口：`POST /api/workflows/{workflow_id}/execute/stream`
   - 契约：必须先创建 Run；`run_id` 缺失直接 `400`；`run_id` 不存在或不属于 workflow 直接 `409`；SSE 事件需携带 `run_id`。
   - 实现位置：`src/interfaces/api/routes/workflows.py:359`
   - 错误码/结构：`400 run_id is required`；`409 run_id not found / does not belong / not executable`。
   - 测试点：`tests/integration/api/workflows/test_workflows.py:323`

4) **Tool 与 Node 统一（最小合同：tool_id + executor 可解析）**
   - 入口：保存前校验（拖拽/对话/创建）与执行前校验（`/execute/stream`）。
   - 契约：Tool node 必须携带 `tool_id`（兼容 `toolId`），且 tool 存在且非 deprecated；node_type 必须有 executor。
   - 实现位置：`src/domain/services/workflow_save_validator.py:44`、`src/domain/services/workflow_save_validator.py:152`
   - 错误码/结构：`missing_executor/missing_tool_id/tool_not_found/tool_deprecated/cycle_detected/...`。
   - 测试点：`tests/unit/domain/services/test_workflow_save_validator.py:64`

5) **Coordinator 监督（fail-closed）**
   - 入口：EventBus middleware + `/execute/stream` 执行前策略链。
   - 契约：在写入 Run 状态与事件前必须经过监督；被拒绝返回 `403` 且结构化错误（`coordinator_rejected`）。
   - 实现位置：`src/interfaces/api/main.py:224`、`src/interfaces/api/routes/workflows.py:415`
   - 错误码/结构：HTTP `403 detail.error=coordinator_rejected`。
   - 测试点：`tests/integration/api/workflows/test_workflows.py:409`、`tests/integration/api/workflow_chat/test_chat_stream_react_api.py:475`

6) **严格 ReAct（Action→真实执行→Observation）**
   - 入口：对话 Agent ReAct core
   - 契约：每次 `tool_call` 必须产生来自真实执行的 `tool_result`（Observation 可信）。
   - 实现位置：`src/domain/agents/conversation_agent_react_core.py:436`
   - 错误码/结构：SSE `tool_result.metadata={tool_id,result,success,error}`；未知工具会产生失败的 `tool_result`（fail-closed）。
   - 测试点：`tests/unit/domain/agents/test_conversation_agent_react_core.py:216`、`tests/integration/api/workflow_chat/test_chat_stream_react_api.py:260`

7) **Run 一致（点击 Run=事实源，可追踪）**
   - 入口：`POST /api/projects/{project_id}/workflows/{workflow_id}/runs` → `POST /api/workflows/{workflow_id}/execute/stream`
   - 契约：Run 创建失败则不执行（fail-closed）；执行关键事件写入 RunEvent（至少 start + terminal）。
   - 实现位置：`src/interfaces/api/routes/runs.py:93`、`src/interfaces/api/routes/runs.py:238`、`src/interfaces/api/routes/workflows.py:446`
   - 错误码/结构：Run 创建 `410`（feature flag 关闭）或 `400/404/500`；执行 `400/409`（run_id 相关）。
   - 测试点：`tests/integration/api/runs/test_run_events_replay_api.py:133`、`tests/integration/api/runs/test_run_events_replay_api.py:76`、`tests/integration/api/workflows/test_run_event_persistence.py:1`、`web/src/features/workflows/pages/__tests__/WorkflowRunFailClosed.test.tsx:50`

8) **LangGraph（workflow 执行）**
   - 入口：LangGraphWorkflowExecutorAdapter（feature flag）
   - 契约：关闭时不得走 NotImplemented；必须可一键回滚到 legacy workflow engine。
   - 实现位置：`src/infrastructure/lc_adapters/workflow/langgraph_workflow_executor_adapter.py:1`
   - 错误码/结构：关闭时抛 `feature_disabled: ...`（DomainError）。
   - 测试点：`tests/unit/lc/workflow/test_langgraph_workflow_executor_adapter.py:13`、`tests/unit/application/services/test_workflow_execution_facade_langgraph_toggle.py:14`

9) **WorkflowAgent 协作（计划可达成性验证 + 反馈闭环）**
   - 入口：AgentOrchestrator / SubAgentOrchestrator
   - 契约：主链路必须启动编排器并把 validated decision 落到执行反馈闭环。
   - 实现位置：`src/domain/services/agent_orchestrator.py:1`
   - 错误码/结构：当前缺少“主链路已启动”的证据。
   - 测试点：暂无（需补 API 端到端协作测试）。

10) **DDD 边界（依赖方向可强制）**
   - 入口：import-linter 合同
   - 契约：Interface/Application/Domain/Infrastructure 依赖方向受约束且 CI 可守门。
   - 实现位置：`.import-linter.toml:1`
   - 错误码/结构：CI 失败（import-linter 报告）。
   - 测试点：CI / 本地运行 import-linter（见后续 issue WF-080）。

### 3.2 不变式 → 测试/手工验收映射（DoD）

> 目标：让每条不变式都能被“持续验证”（优先自动化；无法自动化的部分给出可执行的手工步骤）。

1) 创建（chat-create，唯一入口）
   - 自动化：`pytest -q tests/integration/api/workflow_chat/test_chat_create_stream_api.py`
   - 手工：`curl -N -H "Accept: text/event-stream" -X POST http://localhost:8000/api/workflows/chat-create/stream -d "{\"message\":\"hi\"}"`，首个事件应包含 `metadata.workflow_id`

2) 修改（拖拽 + 对话，两条链路，落库前同校验）
   - 自动化：`pytest -q tests/integration/api/workflows/test_workflow_validation_contract.py tests/unit/domain/services/test_workflow_save_validator.py`
   - 手工：分别用拖拽与对话修改触发保存失败，错误应为结构化 `detail.errors[].code`（例如 `missing_tool_id/missing_executor/...`）

3) 执行（execute/stream gate）
   - 自动化：`pytest -q tests/integration/api/workflows/test_execute_stream_validation_gate.py`
   - 手工：`curl -N -H "Accept: text/event-stream" -X POST http://localhost:8000/api/workflows/<workflow_id>/execute/stream -d "{\"initial_input\":{},\"run_id\":\"\"}"` 应 `400`

4) Tool/Node 统一（tool_id + executor 可解析）
   - 自动化：`pytest -q tests/unit/domain/services/test_workflow_save_validator.py`
   - 手工：保存含 Tool 节点但缺少 `tool_id` 的 workflow，应被 fail-closed 拒绝（`missing_tool_id`）

5) Coordinator reject（fail-closed）
   - 自动化：`pytest -q tests/integration/api/workflows/test_workflows.py tests/integration/api/workflow_chat/test_chat_stream_react_api.py`
   - 手工：制造被 policy chain 拒绝的 decision，HTTP 应 `403 detail.error=coordinator_rejected` 或 SSE `error_code=COORDINATOR_REJECTED`

6) 严格 ReAct（Action→真实执行→Observation）
   - 自动化：`pytest -q tests/unit/domain/agents/test_conversation_agent_react_core.py tests/integration/api/workflow_chat/test_chat_stream_react_api.py`
   - 手工：对话触发工具调用，SSE 中应出现可配对的 `tool_call/tool_result`（相同 `metadata.tool_id`）

7) Run 一致（创建幂等 + 事件落库 + 回放）
   - 自动化：`pytest -q tests/integration/api/runs/test_run_events_replay_api.py tests/integration/api/workflows/test_run_event_persistence.py`
   - 手工：先 `POST /api/projects/<project_id>/workflows/<workflow_id>/runs -H "Idempotency-Key: k"`，再用返回 `run_id` 执行 `/execute/stream`，最后 `GET /api/runs/<run_id>/events`

8) LangGraph（workflow 执行）
   - 自动化：`pytest -q tests/unit/lc/workflow/test_langgraph_workflow_executor_adapter.py tests/unit/application/services/test_workflow_execution_facade_langgraph_toggle.py`
   - 手工：设置 `ENABLE_LANGGRAPH_WORKFLOW_EXECUTOR=true/false` 重启服务，确认可在 LangGraph/legacy 两条路径间切换且不会走 NotImplemented

9) WorkflowAgent 协作（计划可达成性验证 + 反馈闭环）
   - 自动化：暂无（需要主链路接线后补端到端用例）
   - 手工：确认 API 主链路确实启动编排器并能将 validated decision → 执行反馈闭环（否则标记为未满足）

10) DDD 边界（依赖方向可强制）
   - 自动化：`import-linter`（或 `python -m importlinter`）
   - 手工：在变更前后运行 import-linter，确保“不新增越界”且 CI 守门有效

---

## 4. 关键链路剖析（按你的目标口径逐项展开）

### 4.1 创建工作流：是否真的“只有 chat-create 一条链路”

- ✅ chat-create 入口存在且具备“首事件包含 workflow_id”的合同：`POST /api/workflows/chat-create/stream`。
  证据：`src/interfaces/api/routes/workflows.py:618`
- ✅ 未发现 legacy `POST /api/workflows` 创建端点（避免旁路创建）。
  证据：`src/interfaces/api/routes/workflows.py:1`

严格验收结论：**满足“唯一链路（创建）”**。

### 4.2 修改工作流：拖拽 + 对话链路是否都能正确“识别工具”

现状：
- 拖拽修改：`PATCH /api/workflows/{workflow_id}` 在落库前强制 `WorkflowSaveValidator`（可执行性 / DAG / 引用完整性 / 工具存在性）。
  证据：`src/interfaces/api/routes/workflows.py:301`、`src/application/use_cases/update_workflow_by_drag.py:115`
- 对话修改：`chat/chat-stream` 同样在落库前强制 `WorkflowSaveValidator`（fail-closed）。
  证据：`src/interfaces/api/routes/workflows.py:776`、`src/application/use_cases/update_workflow_by_chat.py:131`

工具识别裂缝：
- Domain 有 ToolEngine（扫描 tools/、索引、参数验证）：`src/domain/services/tool_engine.py:248`
- 平台也有 DB Tool API：`src/interfaces/api/routes/tools.py:1`
- 当前最小合同已明确：Tool node 必须持久化 `tool_id`（兼容 `toolId`），否则保存直接被拒绝（结构化错误码 `missing_tool_id`）。
  证据：`src/domain/services/workflow_save_validator.py:44`

严格验收结论：**部分满足**：已能 fail-closed 阻断“不可执行但可保存”，但能力真源仍多套并存（尚未收敛为单一映射）。

### 4.3 执行工作流：是否只有一条链路且与 WorkflowAgent 一致

当前 API 执行链路：
- `POST /api/workflows/{workflow_id}/execute/stream` → `container.workflow_execution_kernel()` → `WorkflowExecutionOrchestrator/Facade` → Domain workflow engine kernel
  证据：`src/interfaces/api/routes/workflows.py:359`、`src/interfaces/api/routes/workflows.py:502`、`src/interfaces/api/main.py:102`

并行存在的 WorkflowAgent：
- `src/domain/agents/workflow_agent.py` 定义了事件驱动、状态同步、反思等另一套执行/协作语义。
  证据：`src/domain/agents/workflow_agent.py:1`

严格验收结论：**不满足“执行链路=WorkflowAgent 链路”**，存在“双内核/双语义”。

### 4.4 CoordinatorAgent 是否是“入口 + 监督者”

你要求的关键点：**对话必须从协调者进入**，并由协调者监督不偏离。

现状：
- ✅ Coordinator 会在 API lifespan 被创建，并注册到 EventBus middleware（避免旁路决策）。
  证据：`src/interfaces/api/main.py:224`
- ✅ `/execute/stream` 在写入 Run 状态与事件前强制 `CoordinatorPolicyChain`（fail-closed）。
  证据：`src/interfaces/api/routes/workflows.py:415`
- ⚠️ 对话入口的 `ConversationTurnOrchestrator` 仍挂 `NoopConversationTurnPolicy`（策略链未落地为“可证明合同”）。
  证据：`src/interfaces/api/main.py:116`、`src/application/services/conversation_turn_orchestrator.py:227`

严格验收结论：**部分满足**：执行链路已具备监督合同，但“所有对话入口都不可绕过”的证明仍不足。

### 4.5 对话 Agent ReAct 范式是否严格

严格 ReAct 要求：Thought→Action→Observation 闭环；Observation 来自真实执行（工具/节点）。

现状：
- ✅ `tool_call` 会触发真实执行并 emit `tool_result`（fail-closed：未知工具也会产生失败的 tool_result）。
  证据：`src/domain/agents/conversation_agent_react_core.py:436`、`src/domain/services/conversation_flow_emitter.py:308`
- ✅ SSE 流中 `tool_call` 与 `tool_result` 可按 `tool_id` 配对，具备可审计性。
  证据：`tests/integration/api/workflow_chat/test_chat_stream_react_api.py:260`

严格验收结论：**满足严格 ReAct**（Action→真实执行→Observation 闭环，且 Observation 可审计）。

### 4.6 “执行成功”是否与用户点击 Run 一致

当前事实源（已收敛为 fail-closed 合同）：
- ✅ 后端提供 Run 创建：`POST /api/projects/{project_id}/workflows/{workflow_id}/runs`（支持 Idempotency-Key 幂等）。
  证据：`src/interfaces/api/routes/runs.py:153`
- ✅ 后端执行强制 `run_id`：`POST /api/workflows/{workflow_id}/execute/stream`（缺失直接 400）。
  证据：`src/interfaces/api/routes/workflows.py:359`、`tests/integration/api/workflows/test_workflows.py:356`
- ✅ 执行过程中会落库关键事件（至少 start + terminal），并把 `run_id` 注入到 SSE 事件，保证“点击 Run=事实源”可追踪。
  证据：`src/interfaces/api/routes/workflows.py:446`、`tests/integration/api/workflows/test_workflows.py:323`
- ✅ 前端具备“创建 Run 失败则不执行”的 fail-closed 行为与用例。
  证据：`web/src/features/workflows/pages/__tests__/WorkflowRunFailClosed.test.tsx:50`

当前缺口：
- ❌ 缺少 `GET /api/runs/{run_id}/events`（回放闭环未完成，见 issue WF-020）。

严格验收结论：**部分满足“一致性/可追踪”**，但**未满足“可回放”**。

### 4.7 LangGraph：是否用于 workflow 执行链路

现状（从 “NotImplemented 占位” 修订为 “可控开关”）：
- LangGraph workflow executor 现为 feature-flag 路径，关闭时 fail-closed（不会走占位执行）。
  证据：`src/infrastructure/lc_adapters/workflow/langgraph_workflow_executor_adapter.py:1`、`src/config.py:138`

严格验收结论：**未默认满足“workflow 必须使用 LangGraph”**（需要明确开关策略与回归覆盖）。

### 4.8 WorkflowAgent ↔ ConversationAgent 协作与“计划可达成性验证”

仓库中存在符合你设想的雏形：
- `AgentOrchestrator`：注册 Coordinator middleware、订阅 validated decision、转发 WorkflowAgent。
  证据：`src/domain/services/agent_orchestrator.py:1`

但该雏形没有在 API composition root 启动，导致“计划验证/执行反馈闭环”没有落地到主业务路径。

严格验收结论：**协作模型“在代码里存在”，但未在主链路生效**。

---

## 5. 红队视角漏洞清单（可被触发的失败模式）

1) **绕过监督（Bypass Coordinator）**：任何不经 middleware/policy chain 的直接执行路径都能绕过 Coordinator；当前 workflow REST 执行就是典型。
2) **回放缺口（Replay is feature-gated）**：回放 API 已实现，但受 feature flag `disable_run_persistence` 影响（关闭时 410），回归必须覆盖开关。
3) **不可执行但可保存（Poisoned Graph）**：已被保存前强校验（fail-closed）显著缓解，但仍需防止新增旁路写入口绕过校验。
4) **ReAct 假闭环（No real Observation）**：已修复为真实执行 + `tool_result`；仍需确保生产工具执行器可注入并审计。
5) **文档漂移（Human-process漏洞）**：开发者按文档推进会走错入口/错配协议（例如 chat 501），引入“影子实现”。

---

## 6. DDD 边界审计（是否满足“接口层/应用层/领域层不越界”）

明确越界（证据级）：
- Application 依赖 Infrastructure：`src/application/use_cases/execute_run.py:43`
- Domain 依赖 Application：`src/domain/services/workflow_chat_service_enhanced.py:247`
- Infrastructure 依赖 Application：`src/infrastructure/lc_adapters/workflow/react_orchestrator.py:34`
- Domain 依赖 Infrastructure：`src/domain/agents/workflow_agent.py:70`

结论：**当前不满足 DDD 边界不越界**；这会直接破坏你希望强制的“不变式”（入口唯一、监督不可绕过、能力注册单一真源）。

---

## 7. 满足你“项目既定前提”的必要整改（验收型要求）

> 这里强调“必须做到什么”，不展开大段实现细节。

### 7.1 链路与入口（Coordinator 为核心）
- 对话入口必须统一到 Application 层入口（ConversationTurnOrchestrator + policy chain），并强制经过 Coordinator 验证（middleware 或 policy 方式二选一，但必须不可绕过）。
- REST/调度/后台任务等所有入口必须进入同一“执行管道”，禁止出现绕过 Coordinator 的捷径。

### 7.2 执行链路唯一化（与 WorkflowAgent 一致）
- 你要求“执行链路=WorkflowAgent 链路”：则 API 的 `/execute` 必须复用 WorkflowAgent 的执行语义与事件模型，或 WorkflowAgent 被瘦化为对同一权威执行引擎的薄适配（但对外行为必须一致、可证明一致）。

### 7.3 Tool/Node 统一（修改时可识别 + 保存即保证可执行）
- 建立单一能力注册中心（CapabilityRegistry/ToolRegistry），把 definitions/nodes、ToolEngine、DB Tools、NodeExecutors 统一映射。
- 节点 schema 必须有稳定的引用字段（如 `tool_id`/`capability_id`），对话修改必须产出该字段而不是自由文本工具名。
- 在拖拽与对话修改落库前强制校验：能力存在、executor 存在、DAG 无环、边引用正确、资源限制可满足。

### 7.4 Run 一致性
二选一（必须做决策，否则永远不一致）：
- A) 实现 workflow runs 的事实源（POST + 绑定 run_id + 查询/回放），并让 `/execute` 接收并落库 run_id；
- B) 移除 workflow-run 概念：前端不再创建/展示 run_id，执行事实仅以 workflow SSE 事件为准。

### 7.5 LangGraph（workflow 必须用）
二选一（同样必须决策）：
- A) workflow 执行迁移到 LangGraph（实现 workflow LangGraph executor 并成为权威执行路径）；
- B) 明确 workflow 不使用 LangGraph：移除 NotImplemented adapter 注入与相关宣称，避免架构漂移。

### 7.6 DDD 边界恢复
- 通过 Ports/Adapters 消除跨层 import，使“入口唯一、真源唯一、监督不可绕过”能够被结构性强制。

---

## 8. 建议验收标准（DoD，覆盖你的前提）

1) **唯一创建链路**：除 chat-create 外的 workflow create endpoint 不可被产品流量调用（移除/强制拒绝/仅内部开关）。
2) **修改链路一致**：拖拽与对话修改都必须在落库前通过同一套“能力/可执行性校验”。
3) **执行链路唯一且等同 WorkflowAgent**：任意入口执行同一管道；对外事件序列一致；成功判定一致；并可通过测试证明。
4) **Tool 识别**：对话修改能稳定引用工具（tool_id/capability_id），且工具变更不会导致 prompt 硬编码漂移。
5) **Coordinator 监督**：决策事件在 Coordinator 可观测、可拦截、可纠偏；且无法被绕过。
6) **严格 ReAct**：每次 Action 都有对应 Observation（工具/节点真实结果），支持回放与审计。
7) **Run 一致性**：UI 展示的 run 与后端事实一致（或 UI 不再展示 run）；可回放。
8) **LangGraph 对齐**：workflow 执行路径确实使用 LangGraph（或明确不使用并清理）。
9) **DDD 合规**：依赖方向检查通过（至少不新增越界，逐步消除存量越界）。

---

## 9. 关键证据索引（便于复核）

- 统一架构与问题定义：`docs/architecture/WORKFLOW_UNIFIED_ARCHITECTURE_PLAN.md:1`
- 多 Agent 协作预期闭环：`docs/architecture/multi_agent_orchestration.md:1`、`docs/architecture/multi_agent_collaboration_guide.md:1`
- Coordinator middleware 已接线：`src/interfaces/api/main.py:224`
- chat-create（唯一创建入口）：`src/interfaces/api/routes/workflows.py:618`
- 拖拽修改 + 校验合同：`src/interfaces/api/routes/workflows.py:301`、`tests/integration/api/workflows/test_workflow_validation_contract.py:108`
- 对话修改（REST + stream）：`src/interfaces/api/routes/workflows.py:776`、`src/interfaces/api/routes/workflows.py:820`
- WorkflowSaveValidator（错误码合同）：`src/domain/services/workflow_save_validator.py:65`、`tests/unit/domain/services/test_workflow_save_validator.py:64`
- Run 创建（幂等）+ run_id 强制执行：`src/interfaces/api/routes/runs.py:153`、`src/interfaces/api/routes/workflows.py:376`
- SSE 事件携带 run_id（集成测试）：`tests/integration/api/workflows/test_workflows.py:323`
- 前端执行 fail-closed（Run 创建失败不执行）：`web/src/features/workflows/pages/__tests__/WorkflowRunFailClosed.test.tsx:50`
- LangGraph workflow executor（feature flag）：`src/infrastructure/lc_adapters/workflow/langgraph_workflow_executor_adapter.py:1`、`src/config.py:138`
- 对话 ReAct（tool_call 仅 emit）：`src/domain/agents/conversation_agent_react_core.py:431`
- ConversationAgent 工厂装配（fallback）：`src/application/services/conversation_agent_factory.py:17`
- DDD 合同：`.import-linter.toml:1`
