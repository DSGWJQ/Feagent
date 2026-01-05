---
mode: plan
cwd: D:\My_Project\agent_data
task: 基于 Report.md 的工作流主链路修复方案（伪 ReAct / 创建副作用 / 多智能体闭环接线）
complexity: complex
planning_method: builtin
created_at: 2026-01-04T19:59:00
---

# Plan: 基于 Report.md 的工作流主链路修复方案

🎯 任务概述

当前 `Report.md` 的复审结论指出 3 个高优先级问题：
1) workflow 对话改图链路存在“伪 ReAct”（解释性回放被映射为 `tool_call/tool_result`，误导审计与 UI）。
2) chat-create 在 Coordinator gate 之前先落库创建 workflow（拒绝/断连时 best-effort 删除），若要求“拒绝=0副作用”则不满足。
3) HTTP 主链路未默认接线 validated decision → WorkflowAgent 执行，若把“三 Agent 执行闭环”当作主链路事实，会形成“架构幻觉”。

本计划目标：在不破坏现有主链路（chat-create / chat-stream / patch / execute/stream）的前提下，消除审计语义欺骗、收敛副作用边界，并明确（或接线）多智能体闭环在主链路中的角色；同时补齐全面验收标准与回归用例。

🧭 关键假设/需要你确认的口径

1) “Coordinator 是核心”是否覆盖拖拽修改（`PATCH /api/workflows/{id}`）？
   - A. 只监督对话链路（chat-create/chat-stream/conversation_stream），拖拽属于“显式用户操作”，可不 gate；
   - B. 所有 workflow 变更都必须 gate（包含拖拽），Coordinator 作为统一守门。
2) workflow 对话改图链路是否必须展示“ReAct-like steps”？
   - 若必须展示，是否接受将其标记为 `planning_step(simulated)`（非真实执行）？
3) 是否要让 HTTP 主链路也走“三 Agent 执行闭环”（ConversationAgent→Decision→Coordinator→WorkflowAgent）？
   - 若是：需要在 app 启动时接线执行桥；并定义对话入口如何产生可执行 decision（目前 workflow 修改主要走 UseCase+LLM）。
   - 若否：需要明确文档口径：workflow 主链路是“UseCase + Coordinator gate + SaveValidator + RunEntry”，而不是“多 Agent 执行闭环”。

---

📋 执行计划

## Phase 1：冻结契约与验收口径（先统一“什么叫对/错”）

1.1 梳理并冻结 3 类事件契约（对前端/审计都必须明确区分）
- planning（规划/解释/模拟）：允许包含 thought，但不能被当作真实 tool 执行证据
- tool_call（真实工具调用）：必须对应真实执行器与真实结果
- execution（工作流节点执行）：`node_start/node_complete/node_error/workflow_complete/workflow_error`

1.2 输出“事件语义表”（写入文档或作为代码常量/枚举），并标注每条链路应产出的事件集合：
- chat-create/stream：planning + workflow_updated（以及可选 simulated planning）
- chat-stream：planning + workflow_updated（以及可选 simulated planning）
- execute/stream：execution + lifecycle（由 RunEntry 驱动）

✅ 验收标准（Phase 1）
- 任意出现 `tool_call/tool_result` 的事件必须能追溯到真实执行（ConversationAgent tool executor 或真实 tool engine），不得来自 workflow chat 的 LLM 文本回放。
- `execute/stream` 事件只允许出现 execution 事件（node_*/workflow_*），不得混入 planning/tool_call。

---

## Phase 2：修复“伪 ReAct”事件语义（后端为主，前端适配）

2.1 后端：调整 workflow chat 的流式事件映射（避免 `tool_call/tool_result`）
- 保留 `react_step` 原始信息（thought/action/observation）但改为新事件类型：
  - 方案优先：`planning_step`（metadata: `simulated=true`, `source=workflow_chat_llm`）
  - 或：保留 `react_step` 但明确 `simulated=true`，并禁止映射为 tool_call/tool_result
- 保留 `workflow_updated` / `modifications_preview` 语义不变，避免破坏前端功能。

2.2 前端：SSE 解析与 UI 展示调整
- 新增对 `planning_step`（或 `react_step` + `simulated=true`）的解析与展示：
  - 展示为“AI 规划/解释步骤”，不可计入“工具执行日志”
- 仍保留现有 `tool_call/tool_result`（来自 ConversationAgent）展示为“真实工具调用”

✅ 验收标准（Phase 2）
- 后端：`POST /api/workflows/{id}/chat-stream` 返回流中不再出现 `tool_call/tool_result`（除非该链路明确集成了真实工具执行器并能证明真实性）。
- 前端：workflow 编辑页中，规划步骤与工具执行步骤可视化分区/标识清晰；规划步骤不触发任何“执行成功/失败”的统计。
- 回归：现有 workflow chat 仍可完成增删节点/边并落库（`workflow_updated` 正常返回）。

---

## Phase 3：chat-create 副作用收敛（满足“拒绝=0副作用”，或显式声明例外）

3.1 若要求“Coordinator 拒绝=0副作用”
- 引入 chat-create 的 coordinator preflight gate（在 DB commit 之前）：
  - decision_type: `api_request` / action: `workflow_create`
  - 不透传 message 明文，仅透传 message_len / project_id / run_id 等最小信息
- gate 通过后再创建 workflow 并 commit；gate 拒绝直接返回 403/SSE error，不应写库。

3.2 若不要求“拒绝=0副作用”
- 必须补充可观测性与清理保证：
  - 明确记录“创建后被拒绝/断连清理”的审计日志
  - 增加一致性修复脚本/后台 job（可选）清理“孤儿 workflow”

✅ 验收标准（Phase 3）
- gate 开启的情况下：Coordinator 拒绝 chat-create 时，数据库中不得出现 workflow 记录（或至少事务 rollback）。
- chat-create SSE 契约仍成立：第 1 个事件内包含 `metadata.workflow_id`（仅在 gate 通过后）。
- 断连场景：客户端断连不会导致半成品 workflow 长期残留（要么无副作用，要么可回收且可观测）。

---

## Phase 4：明确并收敛“执行链路唯一且与 WorkflowAgent 同语义”

4.1 固化“Run 级权威入口”作为唯一执行编排事实源
- 确认所有执行路径（API Run、调度器、WorkflowAgent）都通过 `WorkflowRunExecutionEntryPort` 走 gate + 事件落库 + 成功判定。
- 清点是否存在任何 bypass（例如直接调用 Facade.execute 无 run_id 的路径）并以 feature flag/策略明确允许范围（仅 rollback 场景）。

4.2 统一成功判定口径
- 对外统一输出：success = (terminal_event == workflow_complete) AND (RunStatus==COMPLETED)
- 前端 UI 的“Run 成功/失败”以该口径为准（与回放一致）。

✅ 验收标准（Phase 4）
- 后端：在 run persistence 开启时，不存在无需 run_id 的 workflow 执行入口可被正常业务链路调用。
- 前端：点击 Run 的成功/失败与 `GET /api/runs/{run_id}` / events 回放结果一致。

---

## Phase 5：多智能体闭环（“接线”或“显式不作为主链路”二选一）

5.1 选项 A：把“三 Agent 执行闭环”接入 workflow 主链路
- 在 app 启动时接线 validated decision → 执行（桥接器/编排器）：
  - 必须只消费 Coordinator 验证通过的事件
  - 必须使用 RunEntry 执行（禁止 WorkflowAgent 自行旁路）
- 定义对话入口如何产出可执行 decision（workflow 修改链路目前以 UseCase 为主，需要明确边界）。

5.2 选项 B：不把“三 Agent 执行闭环”作为 workflow 主链路事实
- 明确文档与运行时指标：workflow 主链路 = UseCase + Coordinator gate + SaveValidator + RunEntry
- 保留多智能体模块用于“独立对话系统/研究任务/Agent WebSocket”等实验入口
- 删除或显式标记未挂载/未完成链路，避免团队误用

✅ 验收标准（Phase 5）
- 选项 A：ConversationAgent 产生 `execute_workflow` 决策后，必须能观测到同一个 run_id 的执行事件流与最终 RunStatus；并能触发 WorkflowAgent 的 plan reachability feedback。
- 选项 B：文档/README/运行手册中不再把“三 Agent 执行闭环”描述为 workflow 主链路；并在代码中避免对外暴露未完成入口（或明确 404/disabled）。

---

## Phase 6：测试与回归（覆盖“全面验收标准”）

6.1 单测（建议）
- workflow chat 事件语义：确保不会产生 `tool_call/tool_result`
- SaveValidator：tool_id 规范化与 tool 存在性校验（包含 toolId→tool_id）
- RunEntry：success 判定逻辑（terminal_event + RunStatus）

6.2 集成/E2E（建议）
- chat-create：拒绝无副作用（若启用 preflight gate）
- execute/stream：run_id 缺失 fail-closed，且事件落库可回放
- 前端：Run 创建失败不触发 execute/stream（已有用例，需保持通过）

6.3 架构边界守门
- `python -m importlinter` 必须通过（不新增 DDD 越界）

✅ 验收标准（Phase 6）
- 所有新增/修改测试通过：
  - 后端：`pytest`
  - 边界：`python -m importlinter`
  - 前端（若涉及）：`pnpm test` 或 `vitest`
- 无新增高危 lint/type 错误（按现有仓库标准）。

---

## Phase 7：文档与运维回路（防止“团队认知漏洞”复发）

7.1 更新 `Report.md` 中的结论为“已修复/未修复”状态与验收链接（测试用例/日志关键字）
7.2 更新 docs/runbook：
- 事件语义表（planning vs tool_call vs execution）
- Coordinator gate 的覆盖范围与拒绝语义（是否 0 副作用）
- 多智能体闭环在 workflow 主链路中的定位（A 接线 / B 非主链路）

✅ 验收标准（Phase 7）
- 文档能够回答：哪个入口负责什么、哪些事件代表真实执行、出现争议时如何回放与追责。

---

⚠️ 风险与阻塞

- 语义兼容风险：改变 chat-stream 的事件类型可能影响现有前端解析；需要“后端兼容期”（同时输出旧字段但增加 simulated 标记）或前端同步发布。
- 产品口径风险：是否要求“拖拽也必须 Coordinator gate”会显著改变交互与权限模型，必须先确认。
- 主链路定位风险：如果同时存在“UseCase 驱动 workflow chat”和“ConversationAgent 驱动 decision”，容易出现双中心；需要明确谁是权威链路。
- 环境限制：当前环境中 `codebase-retrieval` 发生权限报错（EPERM），检索以本地 `rg` 为准；不影响实施但影响自动化检索体验。

📎 参考（与 Report.md 复审部分对齐的关键证据）
- `Report.md:1`
- `src/application/use_cases/update_workflow_by_chat.py:264`
- `src/interfaces/api/routes/workflows.py:563`
- `src/interfaces/api/routes/workflows.py:777`
- `src/interfaces/api/routes/workflows.py:427`
- `src/application/services/workflow_run_execution_entry.py:1`
- `src/application/services/workflow_run_execution_entry.py:316`
- `src/domain/services/workflow_save_validator.py:44`
- `src/domain/services/workflow_save_validator.py:140`
- `src/infrastructure/lc_adapters/workflow/langgraph_workflow_executor.py:16`
- `src/interfaces/api/services/event_bus_sse_bridge.py:13`

