---
mode: plan
cwd: D:\My_Project\agent_data
task: PRD MVP验收标准与落地执行计划（详细全面）
complexity: complex
planning_method: builtin
created_at: 2026-01-05T21:16:50.6966515+08:00
---

# Plan: PRD MVP 验收标准与落地执行计划

🎯 任务概述
本计划用于：在“以代码与测试为事实源”的前提下，对齐 `PRD.md` 的 MVP 验收口径，补齐当前端到端缺口，并产出可追踪的交付物（契约/测试/检查清单）。

当前审计结论（基线）：
- 已具备：Chat-create / Chat-stream / 执行 SSE / Tools / Runs 回放 / Coordinator SSE / 前端 Timeline 与下载。
- 仍缺：①“只改 start→end 主连通子图”的双层防御（prompt 裁剪 + 落地拒绝）；②“外部副作用必须确认”的 confirm 交互协议；③“执行失败→ReAct 自动修正闭环”的主链路接线与验收。

---

## ✅ 验收标准（总表：PRD MVP）

> 说明：每条验收标准都要求至少一种“证据”：
> 1) 自动化测试（pytest/vitest）✅；或
> 2) 可复现的手工验证脚本/步骤 ✅；
> 3) 与协议契约一致（SSE payload/schema）✅。

### A. Chat → Workflow（创建）
A1. `POST /api/workflows/chat-create/stream` 可用，且 **SSE 前 1 个事件内包含 `metadata.workflow_id`**。
- 证据：`tests/integration/api/workflow_chat/test_chat_create_stream_api.py`（已存在并应持续通过）。
- 参考：`src/interfaces/api/routes/workflows.py:563`

A2. 生成 workflow 在前端可见，并支持“预览/确认同步到画布”。
- 证据：前端 `pendingWorkflow` + “同步到画布” CTA 可用；增加 Vitest 覆盖“确认同步后 nodes/edges 更新”。
- 参考：`web/src/hooks/useWorkflowAI.ts`、`web/src/shared/components/WorkflowAIChat.tsx`

### B. Chat 增删改 Workflow（Canvas 为 Master，且只改主连通子图）
B1. Chat 修改必须读取“当前画布状态”为事实源（含用户拖拽后的结构）。
- 证据：后端 chat use case 读取 repository 最新 workflow；前端每次保存后再 chat 不出现漂移（加集成测试）。
- 参考：`src/application/use_cases/update_workflow_by_chat.py`、`src/interfaces/api/routes/workflows.py:814`

B2. **只对 start→end 主连通子图做修改**：孤立节点/孤立子图必须不可被 chat 修改影响（Fail-Closed）。
- 证据（双层防御，二选一不够）：
  - Prompt 层：构造给 LLM 的 workflow_state 必须被裁剪到主连通子图；
  - 落地层：即使 LLM 返回对孤立节点的修改，也必须被拒绝并返回结构化错误（禁止“静默跳过”）。
- 关键边界：
  - 缺 start 或缺 end → 返回空集并要求用户先补齐/连通；
  - 有 start/end 但无 start→end 路径 → 返回空集并报错；
  - 多 start/end：明确策略（建议：任意 start 可达任意 end 的交集/并集，需测试锁死）。
- 参考：`src/domain/services/workflow_chat_service_enhanced.py:32`（已有 `extract_main_subgraph` 但需接线）。

B3. 增量 patch：chat 修改应是“局部变更”，避免重建整图导致漂移。
- 证据：返回的 modifications_count、react_steps 可解释；新增“变更摘要”字段（节点/边 add/delete/update 计数）。
- 参考：`src/application/use_cases/update_workflow_by_chat.py`

### C. Tool = Node（一致性与可执行性）
C1. 左侧工具面板展示所有可用 Tools；拖拽某 Tool 到画布应创建可执行 Tool 节点并预填 `tool_id`。
- 证据：Vitest 覆盖 tool 列表渲染 + drag/drop 创建节点（已存在测试应持续通过）。
- 参考：`web/src/features/workflows/components/NodePalette.tsx`、`web/src/features/workflows/pages/__tests__/WorkflowEditorPageWithMutex.tool-drag-drop.test.tsx`

C2. 保存前强校验：Tool 节点 `tool_id` 必须存在且非 deprecated；否则 fail-closed。
- 证据：后端 `WorkflowSaveValidator` 相关测试。
- 参考：`src/domain/services/workflow_save_validator.py`

### D. RUN 执行（节点级进度/报错/反馈）
D1. `POST /api/workflows/{workflow_id}/execute/stream` 必须：
- 强制 `run_id`（缺失返回 400）；
- 若关闭 run 持久化返回 410；
- 执行事件只允许 `node_*` / `workflow_*`（违约 fail-closed 并输出 `workflow_error`）。
- 证据：pytest 集成测试 + 事件合同测试。
- 参考：`src/interfaces/api/routes/workflows.py:427`、`src/application/services/workflow_event_contract.py`

D2. “RUN 成功”定义：每个节点都执行成功；失败必须定位到节点。
- 证据：执行 SSE 中 node_error 必携带 node_id/node_type；前端节点状态 UI 有对应展示。

D3. **错误分级（必达）**：任何 node_error / workflow_error 必须包含：
- `error_level`（user_action_required|retryable|bug）
- `error_type`（可枚举：tool_not_found/tool_deprecated/timeout/validation/...）
- `retryable`（bool）
- `hint`（面向用户的下一步动作）
- `message`（简短可读；不泄露敏感信息）
- 证据：后端 unit tests（已存在）+ 修复 execute/stream 的集成测试基架，确保契约可回归。
- 参考：`src/application/services/workflow_run_execution_entry.py:130`、`src/domain/utils/error_payload.py`

### E. 三 Agent 可观测（同屏日志窗口）
E1. 前端同屏可查看三路事件：
- CA：chat-stream planning/thinking/error（simulated=true 的 planning_step 不可伪装真实执行）
- WA：execute/stream node_* / workflow_*
- CO：coordinator/workflows/{workflow_id}/stream status_update/node_*
- 证据：Timeline 聚合 hook/component 的单测 + coordinator SSE 合约测试。
- 参考：`web/src/features/workflows/hooks/useWorkflowAgentTimeline.ts`、`web/src/features/workflows/hooks/useCoordinatorStream.ts`

E2. Timeline 具备 fail-closed 的资源边界：最多保留 2000 条，超出提示用户下载。
- 证据：Vitest 覆盖 FIFO 淘汰与提示文案。
- 参考：`web/src/features/workflows/components/AgentTimeline.tsx`

### F. 下载本次 Run 的事件与结果（不做长期持久化之外的补充能力）
F1. 一键下载 `run_id` 对应事件 JSON（分页拉取直到 has_more=false），并可用于回放。
- 证据：Vitest 覆盖分页聚合、错误处理；后端 replay 顺序稳定。
- 参考：`web/src/hooks/useRunEventsDownload.ts`、`src/interfaces/api/routes/runs.py:95`

---

## 📋 执行计划（8 个 Phase，可追踪交付物）

### Phase 1：冻结验收合同与基线（1–2 天）
交付物：
- 《PRD-MVP Contract Checklist》：把上述 A–F 的验收点变成勾选清单（在本文件内维护即可）。
- 跑通最小回归命令并记录：`pytest -q`（后端）、`pnpm -C web test`（前端）。

验收标准：
- chat-create 集成测试持续通过（A1）。
- 错误分级 unit tests 持续通过（D3）。

《PRD-MVP Contract Checklist》（Phase 1 基线）
- [ ] 后端：`pytest -q tests/integration/api/workflow_chat/test_chat_create_stream_api.py`
- [ ] 后端：`pytest -q tests/unit/infrastructure/executors/test_tool_node_executor.py`
- [ ] 后端：`pytest -q tests/integration/api/test_workflow_execution_error_classification.py`
- [ ] 前端：`pnpm -C web test`
- [ ] SSE 合同：chat-create 前 1 个事件包含 `metadata.workflow_id`
- [ ] SSE 合同：`node_error` 事件包含 `error_level/error_type/retryable/hint/message`

### Phase 2：主连通子图“双层防御”落地（P0，2–4 天）
实现要点：
- Prompt 层：在构造 workflow_state 时裁剪到主连通子图（只给 LLM 看允许修改的 nodes/edges）。
- 落地层：对 modifications 的 node_id/edge_id 做 allowlist 校验，触发即报错（不允许静默跳过）。

验收标准：
- B2 全部边界用例都有 unit tests；并新增 1 条 integration：当画布存在孤立节点时，chat 修改不会影响孤立节点（即便 LLM 输出试图修改它）。

### Phase 3：外部副作用 confirm 协议（P0，2–5 天）
实现要点（建议最小协议，不扩容）：
- 后端：CoordinatorPolicyChain 在检测到“外部副作用工具/节点”时返回 `confirm_required` 事件，并阻断执行继续。
- 前端：收到 confirm_required 后弹窗；用户选择 allow/deny；allow 后通过一个明确 API（如 POST confirm）继续同一 run。

验收标准：
- D1 的 gate 行为可回归：未确认前不产生副作用节点执行事件；确认后继续执行。
- Coordinator stream 中能看到 allow/deny/confirm 的理由（可观测 + 可操作）。

### Phase 4：失败→ReAct 自动修正闭环接线（P0，3–7 天）
实现要点：
- 让“失败事件”能被 ConversationAgent/WorkflowAgent 消费并产生 patch（或参数修正），再触发下一次 RUN。
- 固化停止条件（PRD 默认）：最大 6 轮/连续失败 3 轮/10 分钟/20 次 LLM 调用。

验收标准：
- 对固定 demo workflow，构造可控失败（如 tool_not_found/timeout）能进入修正循环并在达到上限时给出可下载的终止报告（包含失败节点列表/错误分级统计/最后一轮 patch 摘要/下一步建议）。

### Phase 5：变更预览（diff/preview）可读化（P1，1–3 天）
实现要点：
- 把“pendingWorkflow”升级为“变更摘要（diff）”：节点/边新增/删除/修改计数 + 关键字段差异。

验收标准：
- 前端单测覆盖：diff 计算与渲染不因未知字段崩溃；用户确认后画布与摘要一致。

### Phase 6：指标验证基准（6/10）测试化（P1，2–5 天）
实现要点：
- 定义 10 条固定 scenario（以“自动化数据清洗”为核心），记录输入/期望输出/允许的降级。
- 离线优先：mock LLM + 可重复的 deterministic tools；真实 LLM 回归用 key 时可选运行。

验收标准：
- 每个 scenario 都能生成完整事件流并可下载；真实回归时统计成功率 ≥ 6/10（非 CI gate）。

### Phase 7：补齐 execute/stream 错误分级集成测试基架（P1，0.5–1 天）
问题说明：
- 现有 `tests/integration/api/test_workflow_execution_error_classification.py` 使用 `patch("src.interfaces.api.routes.workflows.get_container")` 方式，无法覆盖 FastAPI `Depends(get_container)`（依赖在路由注册时已绑定），导致测试走真实 DB 查询 workflow 而 404。

验收标准：
- 用 FastAPI 官方方式覆盖依赖（`app.dependency_overrides[...] = ...`）后，该集成测试可稳定通过并真正验证 SSE payload 契约（D3）。

### Phase 8：发布前检查清单（0.5–1 天）
验收标准：
- 后端：关键 pytest 通过；import-linter 通过；接口契约未破坏。
- 前端：关键 vitest 通过；SSE 解析容错测试通过；Timeline 内存边界通过。
- 文档：仅更新必要文档（如 `API.md`、`docs/architecture/agents-and-protocols.md`）以反映 confirm 协议与闭环。

---

## ⚠️ 风险与注意事项
- “主连通子图”是 PRD 的硬约束：只做 prompt 裁剪不够，必须有落地拒绝，否则 LLM 输出仍可能被应用到孤立节点。
- confirm 协议若做得过重（引入复杂状态机/长连接），会违反 KISS；建议最小可用握手与可观测事件。
- 闭环接线涉及多个子系统（Agent/Execution/RunEvents/UI），需要先把合同与停止条件测试化，否则容易出现“看似会动但不可回归”。

## 📎 参考（关键代码与合同）
- `PRD.md:40`
- `src/interfaces/api/routes/workflows.py:563`（chat-create/stream）
- `src/interfaces/api/routes/workflows.py:427`（execute/stream）
- `src/interfaces/api/routes/workflows.py:814`（chat-stream）
- `src/domain/services/workflow_chat_service_enhanced.py:32`（extract_main_subgraph，需接线）
- `src/application/services/workflow_run_execution_entry.py:130`（错误分级映射）
- `src/interfaces/api/routes/runs.py:95`（run events 回放）
- `src/interfaces/api/routes/coordinator_status.py:160`（coordinator SSE）
- `web/src/features/workflows/components/AgentTimeline.tsx:1`
- `web/src/hooks/useRunEventsDownload.ts:1`
