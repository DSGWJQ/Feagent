# 工作流核心业务与多智能体协作模式审计报告（严格版 / Coordinator-centric）

> 基线：仓库状态 `aa68c7e`（2026-01-04）。
> 范围：围绕 **Workflow 核心业务**（创建/修改/执行/Run/事件回放/工具节点）与 **CoordinatorAgent 监督闭环**（对话、工具调用、执行门禁）。
> 方法：只依据仓库可验证事实（代码/测试/配置/边界合同），并对关键假设做“红队”反证。

---

## 0. 结论摘要（给决策者）

### 0.1 你的“项目前提”与当前实现的匹配度

| 前提（你要求必须成立） | 当前结论 | 关键证据 |
|---|---|---|
| 创建 Workflow 只有一条链路：chat-create | **部分满足（产品链路唯一）**：`chat-create/stream` 是唯一对外推荐链路；但仓库仍存在 **内部创建入口**（feature flag + admin 才可用） | `src/interfaces/api/routes/workflows.py:70`、`src/interfaces/api/routes/workflows.py:563` |
| 修改 Workflow 两条链路：拖拽 + 对话（含增删节点/边/工具节点） | **满足（fail-closed）**：两条链路均在落库前强制 `WorkflowSaveValidator` | `src/application/use_cases/update_workflow_by_drag.py:115`、`src/application/use_cases/update_workflow_by_chat.py:235`、`src/domain/services/workflow_save_validator.py:108` |
| 执行 Workflow 只有一条链路且“与 WorkflowAgent 完全一致” | **未满足（同源目标已写入代码，但未接线）**：API 主链路走 `WorkflowRunExecutionEntry -> WorkflowExecutionKernel`；WorkflowAgent 只有在被注入 `WorkflowRunExecutionEntryPort` 且被桥接事件驱动时才会同源，但当前仓库未启动该桥接器 | `src/interfaces/api/routes/workflows.py:427`、`src/application/services/workflow_run_execution_entry.py:1`、`src/domain/agents/workflow_agent.py:2361`、`src/domain/services/decision_execution_bridge.py:1` |
| Tool 与 Node 统一，修改时工具必须能被识别 | **基本满足（防御式）**：LLM 侧明确要求使用 `tool_id` 且提供候选列表；保存前强制校验 tool 存在/非 deprecated；并兼容 `toolId -> tool_id` | `src/domain/services/workflow_chat_service_enhanced.py:260`、`src/domain/services/workflow_save_validator.py:108`、`tests/unit/domain/services/test_workflow_save_validator.py:118` |
| CoordinatorAgent 是核心：对话入口必须进入监督域，能阻断/纠偏偏航 | **部分满足**：`conversation_stream`、`workflow chat`、`execute/stream` 都有 policy chain；但 `chat-create` 的 preflight gate 目前是 **fail-open（当 coordinator 未配置时）**，在“绝对必须有 coordinator”的前提下是漏洞 | `src/application/services/conversation_turn_orchestrator.py:269`、`src/application/use_cases/update_workflow_by_chat.py:110`、`src/interfaces/api/routes/workflows.py:563` |
| 严格审查 ConversationAgent 的 ReAct（Action→真实执行→Observation） | **满足（对 ConversationAgent）/ 不适用（对 workflow chat）**：ConversationAgent 的 `tool_call` 会真实执行并产出 `tool_result`；workflow chat 的 `react_steps` 已被定义为解释性回放（`planning_step simulated=true`），不再伪装真实 tool execution | `src/domain/agents/conversation_agent_react_core.py:436`、`src/application/services/tool_call_executor.py:57`、`web/src/hooks/useWorkflowAI.ts:81` |
| “执行成功”与用户点击 Run 一致（事实源一致、可追踪可回放） | **部分满足**：前端 run 创建失败会 fail-closed 不触发执行；后端以 Run + RunEvents 作为事实源；但存在 rollback flag `disable_run_persistence` 会关闭 Runs API/执行入口（需按你的产品要求界定） | `web/src/features/workflows/pages/__tests__/WorkflowRunFailClosed.test.tsx:50`、`src/interfaces/api/routes/runs.py:93`、`src/application/services/workflow_run_execution_entry.py:353` |
| workflow 执行必须使用 LangGraph | **满足（默认启用）**：`enable_langgraph_workflow_executor` 默认 `true`，执行门面优先走 LangGraph adapter；关闭时会审计并回滚到 legacy | `src/config.py:145`、`src/application/services/workflow_execution_facade.py:46`、`src/infrastructure/lc_adapters/workflow/langgraph_workflow_executor_adapter.py:39` |
| WorkflowAgent 与 ConversationAgent 必须闭环协作：WorkflowAgent 校验计划可达成并回馈纠偏 | **未满足（能力存在但未成为 workflow 主链路）**：存在反馈事件与 recovery mixin，但缺少“validated decision → 执行 → 反馈 → replanning”的主链路接线与端到端验收 | `src/domain/agents/conversation_agent_recovery.py:117`、`src/domain/agents/workflow_agent.py:2399`、`src/domain/services/decision_execution_bridge.py:1` |
| DDD 分层不越界 | **部分满足**：通过 import-linter 强制 Domain 不依赖 Application/Infrastructure/Interfaces；但并未强制“Interface 只能依赖 Application”，且部分接口层直接使用 Domain service（这是否违规取决于你对 DDD-lite 的定义） | `.import-linter.toml:1`、`src/interfaces/api/routes/workflows.py:41` |

### 0.2 红队结论（最危险的 3 个漏洞）

1) **“执行链路=WorkflowAgent”尚未成立**：现有 workflow 执行是 kernel/orchestrator 事实源；WorkflowAgent 与其同源的设计目标存在，但没有事件桥接与注入，导致“你以为的闭环”在生产链路上并未发生。
2) **chat-create 的 coordinator 监督不是绝对 fail-closed**：当前实现对缺失 coordinator 的环境是 fail-open；这会在测试/最小化部署/误配置时形成监督旁路。
3) **边界合同只覆盖“依赖方向”，未覆盖“入口唯一性”**：仓库仍保留内部创建/生成入口（虽然默认关闭），需要在产品/运维层明确“可启用条件、审计、隔离策略”，否则会在压力下成为旁路。

---

## 1. 你的项目前提（审计基准）

本报告以你明确提出的前提为“必须成立”的验收口径：

1) 创建 Workflow：只有一条链路（对话创建 chat-create）。
2) 修改 Workflow：两条链路（拖拽 + 对话），且包含增删节点/边/工具节点。
3) 执行 Workflow：只有一条链路，并且与 WorkflowAgent 的执行语义/事件/成功判定完全一致。
4) Tool 与 Node 统一：工具是节点能力表达；对话修改时必须识别工具；保存前必须保证可执行性。
5) CoordinatorAgent 是核心：所有对话入口进入监督域，能阻断/纠偏偏航。
6) ConversationAgent 严格 ReAct：Action→真实执行→Observation 闭环。
7) “执行成功”与用户点击 Run 一致：Run 为事实源，可追踪可回放。
8) workflow 执行必须使用 LangGraph。
9) WorkflowAgent ↔ ConversationAgent 协作：WorkflowAgent 验证计划可达成并回馈，ConversationAgent 能基于反馈恢复/重规划。
10) DDD：Interface/Application/Domain/Infrastructure 边界不越界。

---

## 2. 仓库事实：入口、事实源与关键合同（可验证）

### 2.1 “创建/修改/执行”的对外入口（Workflow 核心）

- 创建（推荐链路）：`POST /api/workflows/chat-create/stream`（SSE；首个事件含 `metadata.workflow_id`）
  - 实现：`src/interfaces/api/routes/workflows.py:563`
  - 测试：`tests/integration/api/workflow_chat/test_chat_create_stream_api.py:128`
- 修改（拖拽）：`PATCH /api/workflows/{workflow_id}`
  - 实现：`src/interfaces/api/routes/workflows.py:359`
- 修改（对话）：`POST /api/workflows/{workflow_id}/chat-stream`（SSE）
  - 实现：`src/interfaces/api/routes/workflows.py:814`
  - 监督：`src/application/use_cases/update_workflow_by_chat.py:235`
- 执行（唯一执行入口）：`POST /api/workflows/{workflow_id}/execute/stream`（SSE）
  - 强制 `run_id`：`src/interfaces/api/routes/workflows.py:444`

### 2.2 Run 事实源与回放

- 创建 Run（幂等）：`POST /api/projects/{project_id}/workflows/{workflow_id}/runs`
- 回放 RunEvents：`GET /api/runs/{run_id}/events`（稳定分页）
- 关键实现：`src/interfaces/api/routes/runs.py:93`

### 2.3 事件语义合同（边界冻结）

1) **Workflow execute/stream（执行事件）**
   - 合同：仅允许 `node_*` / `workflow_*`；违约 fail-closed 产出 `workflow_error` 并终态落库
   - 实现：`src/application/services/workflow_event_contract.py:1`、`src/application/services/workflow_run_execution_entry.py:186`

2) **ConversationAgent ReAct（工具执行事件）**
   - 合同：每次 `tool_call` 必须产出可配对 `tool_result`（无论 success/failure）
   - 实现：`src/domain/agents/conversation_agent_react_core.py:436`

3) **workflow chat 的 react_steps**
   - 定位：解释性回放（simulated），不能伪装为真实 tool execution（已在前端/后端作协议隔离）
   - 证据：`src/interfaces/api/routes/workflows.py:652`、`src/domain/services/conversation_flow_emitter.py:267`、`web/src/hooks/useWorkflowAI.ts:81`

---

## 3. 逐条验收（严格对照你的前提）

### 3.1 创建：是否真的只有 chat-create 一条链路？

**结论：产品链路“基本满足”，但系统层面存在旁路入口（默认关闭）**。

- ✅ 推荐/对外：chat-create 是唯一对外链路（SSE 合同明确且有测试）
  - `src/interfaces/api/routes/workflows.py:563`
  - `tests/integration/api/workflow_chat/test_chat_create_stream_api.py:128`
- ⚠️ 仍存在“内部创建入口”（Import/Generate），属于创建旁路
  - 默认关闭 + admin 才可用（410 / 403），但它们仍是 code-level create chain
  - `src/interfaces/api/routes/workflows.py:70`、`src/config.py:138`

**红队风险**：当压力下开启 `enable_internal_workflow_create_endpoints=true`，你将不再满足“唯一创建链路”，并且该旁路未必经过与你主链路一致的 Coordinator 监督/事件合同（需额外审计）。

### 3.2 修改：拖拽 + 对话两条链路（含 Tool）

**结论：满足（以 fail-closed 校验为硬门禁）**。

- ✅ 两条链路都在落库前强制 `WorkflowSaveValidator.validate_or_raise()`：
  - 拖拽：`src/application/use_cases/update_workflow_by_drag.py:115`
  - 对话：`src/application/use_cases/update_workflow_by_chat.py:235`
- ✅ Tool 节点校验覆盖：
  - `toolId -> tool_id` 归一化：`src/domain/services/workflow_save_validator.py:108`
  - tool 存在性 / deprecated：`src/domain/services/workflow_save_validator.py:194`
  - executor 存在性：`src/domain/services/workflow_save_validator.py:168`

**红队风险**：工具“可识别”依赖 LLM 输出 `tool_id` 的正确性。当前策略是“提示约束 + fail-closed 校验”，不会把错误落库，但可能导致用户体验上的反复澄清/失败（这是正确的安全取舍，但需要在产品层可观测）。

### 3.3 执行：唯一执行入口 & 与 WorkflowAgent 完全一致？

**结论：唯一入口“满足”，但“与 WorkflowAgent 完全一致”未满足（缺主链路接线）**。

- ✅ 唯一执行入口（API 侧）：`POST /api/workflows/{workflow_id}/execute/stream`
  - `src/interfaces/api/routes/workflows.py:427`
- ✅ 执行事实源收敛：`WorkflowRunExecutionEntry` 将 run 门禁 / 事件落库 / 成功判定集中在 Application
  - `src/application/services/workflow_run_execution_entry.py:1`
- ⚠️ WorkflowAgent 的“同源执行”仅在被注入 `WorkflowRunExecutionEntryPort` 时成立
  - `src/domain/agents/workflow_agent.py:2361`
- ❌ 当前仓库未启动 `DecisionExecutionBridge`，也未见 API 主链路把 validated decision 转发给 WorkflowAgent
  - `src/domain/services/decision_execution_bridge.py:1`

**红队判断**：你要求的“执行=WorkflowAgent”不是一句口号，它要求“单一权威入口 + 事件桥接 + 同一 run_id + 同一事件合同 + 同一成功判定”。目前仓库已经把“单一权威入口”做成了 `WorkflowRunExecutionEntry`，但 **WorkflowAgent 没有成为主链路的执行者**，因此你的前提 3) 与 9)（协作闭环）在实现层面都不成立。

### 3.4 CoordinatorAgent：是否真的能监督所有对话入口、阻断偏航？

**结论：大部分入口已接入监督域，但存在一个“绝对性”漏洞**。

- ✅ conversation_stream 入口（/api/conversation/stream）在 Application policy chain 做 `api_request` 监督，且不透传 message 明文
  - `src/application/services/conversation_turn_orchestrator.py:269`
  - `src/interfaces/api/routes/conversation_stream.py:66`
- ✅ workflow chat 修改（chat / chat-stream）在 UseCase 层做 `api_request` 监督（fail-closed）
  - `src/application/use_cases/update_workflow_by_chat.py:110`
- ✅ workflow execute/stream 在 Orchestrator policy chain 做监督（fail-closed）
  - `src/interfaces/api/main.py:103`
- ⚠️ chat-create 的 preflight gate 当前是 `fail_closed=False`
  - `src/interfaces/api/routes/workflows.py:563`
  - 在主应用中 coordinator 确实存在（`src/interfaces/api/main.py:285`），但在“误配置/最小化部署/测试 app”时会变成监督旁路

**建议（若你坚持“Coordinator 必须永远存在”）**：把 chat-create 的 gate 调整为 fail-closed，并让测试显式注入 coordinator（否则测试环境会被当作“无监督运行”的反例）。

### 3.5 ConversationAgent ReAct：是否严格 Action→真实执行→Observation？

**结论：ConversationAgent 侧满足；workflow chat 侧已被明确降级为解释性回放（避免伪闭环）**。

- ✅ ConversationAgent 的 `tool_call`：
  - 会先经过 CoordinatorPolicyChain（只发送 args keys/types，不发送明文参数）
  - 然后 emit `tool_call`
  - 然后真实执行（ToolEngineToolCallExecutor）
  - 然后 emit `tool_result`（success/failed 均闭环）
  - `src/domain/agents/conversation_agent_react_core.py:436`
  - `src/application/services/tool_call_executor.py:57`
- ✅ workflow chat 的 `react_steps` 被前后端定义为 `planning_step simulated=true`，不再伪装 tool execution
  - `src/interfaces/api/routes/workflows.py:652`

**红队风险**：如果你把 workflow chat 的 planning_step 当作“可审计的真实执行”，那就是逻辑缺陷。当前实现是正确的：它把“解释性回放”和“真实执行”协议层隔离。

### 3.6 Run 一致性：是否与“用户点击 Run”一致？

**结论：机制上基本成立，但仍需一条端到端证据链（以及明确 rollback flag 的产品语义）**。

- ✅ 前端 fail-closed：Run 创建失败则不触发 execute/stream
  - `web/src/features/workflows/pages/__tests__/WorkflowRunFailClosed.test.tsx:50`
- ✅ 后端事实源：execute/stream 强制 run_id，且事件落库 + 回放 API
  - `src/interfaces/api/routes/workflows.py:427`
  - `src/interfaces/api/routes/runs.py:93`
- ⚠️ rollback flag：`disable_run_persistence=true` 会使 Runs API/execute/stream 返回 410（这是“回滚策略”，但会破坏你对一致性的强前提）
  - `src/config.py:133`

---

## 4. 多智能体协作模式（围绕 CoordinatorAgent）的漏洞审计

### 4.1 你想要的闭环是什么（必要链路）

你描述的正确闭环应至少包含：

1) ConversationAgent 产生 DecisionMadeEvent（含 correlation/run_id）
2) CoordinatorAgent 监督决策（allow/deny；有审计事件/可观测）
3) allow 的 decision 被桥接到 WorkflowAgent（或单一执行入口）
4) WorkflowAgent 执行时使用 **同一 run_id**，并将执行事件写入 RunEvents
5) WorkflowAgent 对“不可达/失败”产生结构化反馈事件（plan_validation / node_failure）
6) ConversationAgent 收到反馈（recovery），触发澄清/重规划/纠偏

### 4.2 现状：缺了哪几段“硬接线”

- CoordinatorAgent 在 EventBus 上已启用 middleware：`src/interfaces/api/main.py:285`
- ConversationAgent 的工具调用与会话入口已有 policy chain + 真实执行闭环：`src/domain/agents/conversation_agent_react_core.py:436`
- WorkflowAgent 已实现“如果注入 WorkflowRunExecutionEntryPort 则同源执行”的路径：`src/domain/agents/workflow_agent.py:2361`
- ConversationAgent recovery mixin 已能订阅反馈事件：`src/domain/agents/conversation_agent_recovery.py:117`

但：

- **DecisionExecutionBridge 未被启动**（没有把 validated decision 接线到 WorkflowAgent）
  - `src/domain/services/decision_execution_bridge.py:1`
- API workflow 主链路也未见“把对话决策转成 workflow 执行”的接线
  - 结果是：工作流执行仍是“API 驱动”，不是“Agent 驱动”

**这就是核心漏洞**：你“以为系统在闭环”，但生产主链路实际上并未闭环；CoordinatorAgent 的监督更多体现在“入口门禁”，而非“全链路决策监督 + 纠偏回路”。

---

## 5. DDD 边界审计（以可执行合同为准）

### 5.1 已被强制的边界（Import Linter）

当前强制合同：

- Domain 不能依赖 Application：`.import-linter.toml:21`
- Domain 不能依赖 Infrastructure：`.import-linter.toml:26`
- Domain 不能依赖 Interfaces：`.import-linter.toml:16`
- Application 不能依赖 Interfaces：`.import-linter.toml:10`

这确保了依赖方向“不会倒灌”。

### 5.2 未被合同覆盖但与你前提相关的边界风险

- Interface 层当前直接引用 Domain service（例如 `WorkflowSaveValidator`、`EnhancedWorkflowChatService`）：
  - `src/interfaces/api/routes/workflows.py:41`
  - 若你的 DDD-lite 定义允许 Interface 直接使用 Domain（而不把所有业务入口都放 Application UseCase），这不一定违规；但如果你要更严格的“Interface→Application→Domain”，则需要额外合同/重构。

---

## 6. 建议：如果你坚持“所有前提必须全部成立”，需要补的最小闭环

按影响优先级（P0→P2）：

### P0：让“执行链路=WorkflowAgent”真正成立（不是口头）

1) 启动 `DecisionExecutionBridge`（或等价桥接），只消费 coordinator validated 的 decision
2) WorkflowAgent 必须注入 `WorkflowRunExecutionEntryPort`，并以 run_id 为事实源执行
3) 用端到端测试证明：validated decision → 同 run_id 的 RunEvents → 回放一致

### P0：把 chat-create 监督从“配置依赖”提升为“硬前提”

- 将 chat-create preflight gate 调整为 fail-closed（coordinator 缺失直接拒绝）
- 测试必须显式注入 coordinator（否则测试环境就是监督旁路的反例）

### P1：把“入口唯一性”也纳入可执行合同

- 明确并测试：内部创建入口默认不可达（410），且任何启用都必须有审计/隔离/回滚预案
- 增补 import-linter 或自定义脚本：阻止新增 Workflow 创建旁路（例如新增新的 POST /workflows* 未经批准）

---

## 7. 验证清单（你可以复核的命令）

后端（核心链路）：

- `pytest -q tests/integration/api/workflow_chat/test_chat_create_stream_api.py`
- `pytest -q tests/integration/api/workflow_chat/test_chat_stream_react_api.py`
- `pytest -q tests/integration/api/workflows/test_run_event_persistence.py`
- `pytest -q tests/integration/api/runs/test_run_events_replay_api.py`
- `lint-imports --config .import-linter.toml`

前端（Run 一致性与协议消费）：

- `cd web && npm test`

一键（本仓库提供的本地脚本）：

- `powershell -ExecutionPolicy Bypass -File scripts/workflow_core_checks.ps1`
