# Workflow 反思/验收闭环 + 实验链路/实际链路统一规划（严格验收 / 分阶段审查）

> 日期：2026-02-04
> 范围：WorkflowAgent（EventBus 多 Agent 实验链路） + Runs（WorkflowRunExecutionEntry / Runs API 实际链路） + Session/对话侧验收
> 用户决策：criteria 缺失时 **自动推导并继续**；每次 REPLAN 后再次执行 **必须再次确认**（confirm 不复用）
> 总原则：Fail-Closed、KISS、SOLID、DRY；每阶段完成必须做“红队审查”并通过测试门禁，才允许进入下一阶段

---

## 0. 目标与结论（必须先对齐）

### 0.1 目标（必须全部达成）

1) **执行单一事实源（Execution SoT）= Runs**
   - 所有真实执行都必须产生 `run_id`，并落到 Runs 的事件/持久化/回放体系。
2) **验收单一事实源（Acceptance SoT）= Session/对话侧**
   - “执行完成”不等于“任务完成”；任务完成必须由 Session 基于证据判定。
3) **工作流执行后自动反思（Reflection）并闭环**
   - Runs 进入终态后自动触发 Reflection/验收；未通过则发布事件回规划 agent 重新规划。
4) **实验链路与实际链路统一体验（用户无感）**
   - 用户不需要理解“实验/实际”；无论入口来自对话或编辑器，最终都走同一套“run->验收->(必要时)replan->再 run”闭环。
5) **最终必须通过测试**
   - PASS 必须同时满足：criteria 全满足 + 证据可复查 + 测试门禁全绿。

### 0.2 一句话结论

将 WorkflowAgent 从“执行引擎”收敛为“决策/反思层”，将 Runs 固化为唯一执行 SoT；在 Session 侧新增严格 Acceptance Loop（证据驱动），把 Reflection 的输出对齐到现有 REPLAN 事件链路，形成可审计、可回放、可测试的闭环。

---

## 1. 术语与统一语义（零容忍漂移）

### 1.1 术语

- 实验链路：WorkflowAgent（EventBus 多 Agent）侧的计划/决策/反思与（历史上可能存在的）实验执行入口。
- 实际链路：Runs（Run 创建/执行/事件持久化/回放/确认门禁）。
- execution completed：Run 进入终态（success/failure/cancelled/timeout...）。
- acceptance passed：Session 验收判定 PASS（证据完备 + 测试通过 + criteria 全满足）。
- Reflection：对本次 run 的证据进行结构化验收与差距分析，产出 verdict（PASS/REPLAN/NEED_USER/BLOCKED）。

### 1.2 Fail-Closed 红线（P0）

出现任一情况，视为 P0（必须在合入前修复）：

- **真实执行未产生 `run_id`**（出现“无 Run 的事实执行”）。
- **无证据 PASS**（未能把每条 criteria 映射到可复查证据）。
- **测试未通过但 PASS**（任何形式的“侥幸通过/话术通过”）。
- **REPLAN 后复用旧 confirm**（必须再次确认）。
- **同一 run 触发多次 Reflection / 同一 Reflection 触发多次 REPLAN**（幂等缺失）。

---

## 2. 现状盘点：当前实验链路 vs 实际链路（用于统一入口）

### 2.1 用户操作与链路映射（现状）

- 对话页（Chat）：
  - 入口：`POST /api/conversation/stream`
  - UI 侧明确不创建 workflow（偏“对话任务”）
- 工作流创建（对话式创建）：
  - 入口：`POST /api/workflows/chat-create/stream`（创建后进入编辑器）
- 工作流编辑器内对话修改：
  - 入口：`POST /api/workflows/{workflow_id}/chat-stream`
- Runs（实际链路）：
  - 创建 run：`POST /api/projects/{project_id}/workflows/{workflow_id}/runs`
  - 执行：`POST /api/workflows/{workflow_id}/execute/stream`
  - 副作用确认：`POST /api/runs/{run_id}/confirm`
- 实验入口（需收敛）：
  - `POST /api/agents/{agent_id}/runs`（代码中标注实验入口）

### 2.2 现有可复用能力（关键落点）

1) **Runs 执行事实源**
   - `WorkflowRunExecutionEntry` 是实际执行与 RunEvents 持久化的关键入口。
2) **事件契约约束（必须遵守）**
   - 仅允许 `node_*` / `workflow_*` 事件；并要求关键字段（至少包括 `run_id`、`executor_id`）。
3) **REPLAN 链路已存在（复用）**
   - 失败编排器会发布 `WorkflowAdjustmentRequestedEvent`；对话/规划侧已存在订阅与 replan 入口。
4) **Reflection 能力已存在但未闭环**
   - `WorkflowAgent.reflect(...)` 会发布 `WorkflowReflectionCompletedEvent`，但目前缺少“每次 run 终态都必触发”的全局串联点。
5) **Decision -> Execution 桥接已存在（优先复用）**
   - `DecisionExecutionBridge` 在特定配置下，会把 validated decision（如 `execute_workflow`）落到 Runs 执行。

### 2.3 入口矩阵（代码扫描结果 / Phase 0 交付物）

> 目标：冻结“入口 → 是否产生 run_id → 是否真实执行”的现状，为 Phase 5 收敛做单一依据。
> 说明：本节仅盘点，不改行为；生产语义以 `disable_run_persistence=false` 为默认前提。

| 场景 | 入口（API） | 代码定位（后端） | 是否产生 run_id | 是否真实执行 | 备注 |
|---|---|---|---:|---:|---|
| 对话页（Chat） | `POST /api/conversation/stream` | `src/interfaces/api/routes/conversation_stream.py` | 否 | 否 | 仅对话/澄清；不创建 workflow，不触发 execute。 |
| 工作流创建（对话式创建） | `POST /api/workflows/chat-create/stream` | `src/interfaces/api/routes/workflows.py` | 否（可透传 `run_id` 作为 correlation） | 否 | 创建 workflow + planning 流；SSE 首事件包含 `workflow_id`。 |
| 编辑器内对话修改 | `POST /api/workflows/{workflow_id}/chat-stream` | `src/interfaces/api/routes/workflows.py` | 否 | 否 | 修改 workflow；`planning_step` 语义明确 `simulated=true`。 |
| 创建 Run（事实源） | `POST /api/projects/{project_id}/workflows/{workflow_id}/runs` | `src/interfaces/api/routes/runs.py` | 是 | 否 | 幂等支持 `Idempotency-Key`；返回 `run_id`。 |
| 执行（事实源） | `POST /api/workflows/{workflow_id}/execute/stream` | `src/interfaces/api/routes/workflows.py` + `src/application/services/workflow_run_execution_entry.py` | 是（要求请求提供） | 是 | `disable_run_persistence=false` 时强制要求 `run_id`；事件落库/回放在 Runs 体系。 |
| 副作用确认 | `POST /api/runs/{run_id}/confirm` | `src/interfaces/api/routes/runs.py` + `src/application/services/run_confirmation_store.py` | 否（消费现有 `run_id`） | 否（仅确认） | confirm 存储目前是 in-memory；证据以 RunEvents（confirm_required/confirmed）为准。 |
| 实验入口（需收敛） | `POST /api/agents/{agent_id}/runs` | `src/interfaces/api/routes/runs.py` + `src/application/use_cases/execute_run.py` | 是 | 是（Agent Run） | 兼容旧链路；与 Workflow/Runs 语义不同（agent run），Phase 5 需明确与 workflow runs 的边界或桥接策略。 |

### 2.4 “无 Run 的事实执行”清单（标红 / P0 现状冻结）

> 定义：发生“真实执行”但**未产生 `run_id`**（或未经过 Runs gate/persistence）的路径。
> 说明：以下均为当前代码中存在的回滚/兼容路径；Phase 0 仅记录，Phase 5 必须收敛或 fail-closed。

1) **Feature flag 回滚：`disable_run_persistence=true` 时允许无 run_id 执行**
   - API：`POST /api/workflows/{workflow_id}/execute/stream` 会走 legacy 执行（不要求 `run_id`，且不进入 Runs 事件/回放体系）
   - 代码：`src/interfaces/api/routes/workflows.py`（legacy 分支） + `src/application/use_cases/execute_workflow.py`
   - 后台/调度：`src/interfaces/api/services/workflow_executor_adapter.py` 同样在该 flag 下走 legacy（无 run_id）

2) **依赖注入缺失的兼容回退：WorkflowAgent 无 run entry 时落到 legacy 执行**
   - 场景：`WorkflowAgent.handle_decision({decision_type: execute_workflow, ...})` 在 `workflow_run_execution_entry` 未注入时，回退到 `execute_workflow()`（无 run_id）
   - 代码：`src/domain/agents/workflow_agent.py`

### 2.5 Reflection/验收闭环所依赖的证据来源（现状冻结）

当前可复用的强证据（按优先级）：

1) **Runs 状态（DB）**
   - `Run.status/created_at/finished_at`（API：`GET /api/runs/{run_id}`，代码：`src/interfaces/api/routes/runs.py`）
2) **RunEvents（DB，可回放）**
   - 回放 API：`GET /api/runs/{run_id}/events?channel=execution|lifecycle`（代码：`src/interfaces/api/routes/runs.py`）
   - 事件落库入口：`WorkflowRunExecutionEntry`（代码：`src/application/services/workflow_run_execution_entry.py`）
   - 事件契约校验：`validate_workflow_execution_sse_event(...)`（代码：`src/application/services/workflow_event_contract.py`）
3) **confirm 证据（RunEvents）**
   - `workflow_confirm_required` / `workflow_confirmed` 等事件会携带 `confirm_id`，可用于审计确认是否发生
   - 注意：确认存储当前为 in-memory（`RunConfirmationStore`），因此“事实证据”必须以 RunEvents 为准

当前缺口（Phase 2/6 需要补齐）：

- `artifact_refs[]`：当前未见统一的 artifacts 持久化/引用机制（需定义格式与存储位置）
- `test_report_ref`：当前未见“测试报告引用”的标准化落库（需与 deterministic E2E/CI 产物对齐）

---

## 3. 目标统一架构（职责清晰，避免双执行/双口径）

### 3.1 职责分层（必须遵守）

- Runs 层（Execution SoT）：
  - 负责：执行、确认门禁、事件持久化/回放、可观测性。
  - 不负责：决定“任务是否完成”（这是验收）。
- WorkflowAgent / 规划 agent（Decision/Reflection）：
  - 负责：决策（计划/工具选择/工作流生成）、基于证据的反思建议（结构化输出）。
  - 不负责：绕开 Runs 的事实执行；不允许“自称完成”。
- Session/对话侧（Acceptance SoT）：
  - 负责：criteria 管理、证据聚合、严格 verdict 判定、向用户追问、触发 REPLAN 事件闭环。

### 3.2 统一后的状态机（Session 视角）

1) 获取/推导 criteria（user/plan/system）
2) 规划 agent / WorkflowAgent 产出 validated decisions
3) 通过桥接层落到 Runs 执行（生成 `run_id`，必要时 confirm）
4) Run 进入终态 -> 自动触发 Reflection/验收（只读 evidence）
5) verdict 分流：
   - PASS：结束并生成 Acceptance Report
   - REPLAN：发布 `workflow_adjustment_requested`（复用现有 REPLAN 链路）
   - NEED_USER：向用户发送最小追问
   - BLOCKED：达到上限或环境阻断，输出阻断原因与证据

---

## 4. 数据模型与幂等/去重（闭环必须可重放）

### 4.1 Session 侧最小状态（建议）

- `attempt`：从 1 开始，每次 REPLAN +1
- `max_replan_attempts`：默认 3（建议可配置）
- `criteria_snapshot`：每次执行前冻结（含来源 user/inferred）
- `criteria_hash`：用于反思幂等
- `run_id`：每次执行一个新的（REPLAN 后必须新 run）
- `reflection_id`：`sha256(run_id + criteria_hash + "v1")`
- `reflection_status`：`pending|done`（防重复触发）

### 4.2 去重键（强制）

- `execution_completed_dedupe = run_id`
- `reflection_completed_dedupe = reflection_id`
- `adjustment_requested_dedupe = reflection_id`

---

## 5. 事件模型（统一链路的“胶水”）

> 约束：事件命名与字段必须满足现有事件契约（仅 `node_*` / `workflow_*`；包含 `run_id`、`executor_id` 等关键字段）。
> 目标：Runs 的事实证据与 Session 的验收结论在同一事件体系闭环。

### 5.1 最小事件集（推荐）

1) `workflow_execution_completed`
- 必填：`session_id`, `workflow_id`(或 `workflow_snapshot_id`), `run_id`, `attempt`, `status`, `started_at`, `ended_at`, `executor_id`
- 证据引用：`run_event_refs[]`, `artifact_refs[]`, `test_report_ref`
- 门禁：`confirm_required`

2) `workflow_reflection_requested`
- 必填：`reflection_id`, `run_id`, `attempt`, `criteria_hash`, `criteria_snapshot_ref`, `executor_id`

3) `workflow_reflection_completed`
- 必填：`reflection_id`, `run_id`, `attempt`, `verdict`, `executor_id`
- 严格字段（Fail-Closed）：
  - `unmet_criteria[]`
  - `evidence_map`（`{criteria_id: evidence_ref[]}`）
  - `missing_evidence[]`
- 分支字段：
  - verdict=NEED_USER：`user_questions[]`
  - verdict=REPLAN：`replan_constraints[]`

4) `workflow_adjustment_requested`（复用现有 REPLAN 机制）
- 必填：`from_reflection_id`, `next_attempt`, `unmet_criteria`, `missing_evidence`, `constraints`, `executor_id`

### 5.2 PASS 的硬约束

PASS 必须同时满足：

- `unmet_criteria` 为空
- `evidence_map` 覆盖所有 criteria（每条至少一个可复查 `evidence_ref`）
- `test_report_ref` 指向“已通过”的测试结果（或可复查的 deterministic e2e 报告）

---

## 6. Criteria 策略（用户输入 / 计划携带 / 系统推导）

### 6.1 来源优先级（必须）

user 显式 criteria > plan 中显式 criteria > system 自动推导

### 6.2 自动推导并继续（你已选定）

- 若用户未提供 criteria：系统从任务描述/计划/工作流结构推导“最小可验证集合”。
- 即使推导不完美，也允许继续执行；但验收必须 Fail-Closed：
  - 推导的 criteria 若不可验证/歧义 => verdict 只能是 NEED_USER/REPLAN（不可 PASS）。

### 6.3 NEED_USER 触发规则（必要才问）

仅在以下情况向用户提问（最多 1~3 个、可一行回答）：

- criteria 不可验证（例如“更好/更快/更漂亮”缺量化）
- criteria 存在冲突（互斥条件）
- 需要人工主观确认（例如“文案是否满意”）

---

## 7. Evidence 策略（以 Runs 证据为准）

### 7.1 证据优先级（从强到弱）

1) 确定性证据：测试结果、结构化断言、文件存在/内容 hash、返回码、可重放事件序列
2) 半确定性证据：关键日志摘要、事件统计（但必须可定位到 run_id）
3) LLM 解释：仅作为差距说明与 replan 建议，不计入“通过证据”

### 7.2 Evidence Collector 最小能力（必须）

给定 `run_id`，可生成幂等的 evidence snapshot：

- `run_event_refs[]`
- `artifact_refs[]`
- `test_report_ref`
- `execution_summary`（可选，仅用于解释）

---

## 8. Acceptance Evaluator（严格判定器）

### 8.1 verdict（四分支）定义

- PASS：全 criteria 满足 + 证据完备 + 测试通过
- REPLAN：存在 unmet criteria，但可自动修复（attempt < max）
- NEED_USER：缺标准/歧义/需人为确认，或 replan 不再有效
- BLOCKED：达到上限或环境/权限阻断

### 8.2 循环控制（防无限 REPLAN）

- `max_replan_attempts = 3`
- 若连续两次 REPLAN 的 `unmet_criteria` 集合没有严格变小 => 转 NEED_USER
- 达到上限 => BLOCKED（输出 unmet + 缺证据 + 建议用户动作）

### 8.3 再次确认（你已选定）

- 每次 REPLAN 后执行必须创建新 run（新 `run_id`）
- 若 `confirm_required=true`：必须要求用户对该 `run_id` 进行确认；确认不可跨 run 复用

---

## 9. 关键插入点（把“反思”串到真实执行终态）

> 原则：Reflection 的触发点必须绑定 Runs 终态；不得绑定“LLM 认为结束”。

推荐插入点（优先级从高到低）：

1) **Runs 执行入口统一回调点**：`WorkflowRunExecutionEntry.execute_with_results(...)` 完成后
   - 优点：执行 SoT；终态明确；证据齐全（run events 可用）。
2) **DecisionExecutionBridge**：decision 执行完成后（仅针对 `execute_workflow`）
   - 优点：天然连接 WorkflowAgent 决策与 Runs 执行；可作为实验链路收敛的最小改动点。
3) **SSE handler 终止处（仅作为补强，不作为 SoT）**
   - 只能用于“触发/转发事件”，不应成为“完成判定”的事实源。

---

## 10. 分阶段计划（每阶段 = 交付物 + 严格验收 + 红队审查 + 测试门禁）

> 任何阶段未通过验收与审查门禁，禁止进入下一阶段。

### Phase 0：现状冻结与红线清单（不改行为）

交付物：
- 入口矩阵（对话/编辑器/实验入口 → 是否产生 run_id → 是否真实执行）
- “无 Run 的真实执行”清单（标红）
- 本文档与现有规划文档的关系说明（避免口径漂移）

严格验收标准（必须全部满足）：
- 明确列出所有需要收敛到 Runs 的入口与调用路径
- 明确列出 Reflection 闭环要依赖的证据来源（run events / artifacts / tests）

红队审查清单：
- 是否仍存在“执行完成语义=LLM 输出”的路径？
- 是否存在任何绕开 `run_id` 的事实执行？

测试要求：
- 不新增，但现有测试不得回归

---

### Phase 1：Criteria Manager（Session 侧）

交付物：
- criteria schema（含来源 user/plan/inferred、verification_method、hash、快照）
- 合并/冲突检测规则
- NEED_USER 最小问题生成（1~3 个）

严格验收标准（必须全部满足）：
- 缺 criteria 时能自动推导并继续，但不会产生无证据 PASS
- criteria 冲突必触发 NEED_USER（Fail-Closed）

红队审查清单：
- 是否出现“不可验证 criteria 被当作已满足”？
- 是否出现“提问过多/不可回答”的交互？

测试要求（必须）：
- Unit：显式 criteria / 推导 / 冲突 -> NEED_USER

---

### Phase 2：Evidence Collector（对齐 Runs）

交付物：
- `run_id -> evidence snapshot`（幂等、可重放）
- evidence 引用格式规范（能定位到 run events / artifacts / test report）

严格验收标准（必须全部满足）：
- 同一 run 回放得到一致 evidence（顺序无关）
- evidence 全部可复查（不可只存“摘要文本”）

红队审查清单：
- 是否会因流式顺序导致 evidence 缺失？
- 是否会把“LLM 解释”当作证据？

测试要求（必须）：
- Integration：evidence 幂等 + 回放一致性

---

### Phase 3：Acceptance Evaluator（严格判定器）

交付物：
- verdict 引擎：PASS/REPLAN/NEED_USER/BLOCKED（结构化输出）
- 循环控制（unmet 不变则 NEED_USER、attempt 上限）
- PASS 硬约束：criteria 全满足 + evidence_map 覆盖 + 测试通过

严格验收标准（必须全部满足）：
- 无证据不可 PASS
- 测试未通过不可 PASS
- REPLAN 输出必须包含最小差异（unmet + 缺证据 + constraints）

红队审查清单：
- 是否存在“话术 PASS”绕过证据？
- 是否可能把 NEED_USER 误判为 REPLAN（导致无意义循环）？

测试要求（必须）：
- Unit：四分支 + 边界（缺证据/测试失败/冲突 criteria/attempt 上限）

---

### Phase 4：Acceptance Loop Orchestrator（闭环编排）

交付物：
- 自动链路：`workflow_execution_completed` -> `workflow_reflection_requested` -> `workflow_reflection_completed`
- REPLAN：发布 `workflow_adjustment_requested`（复用现有链路）
- 幂等/去重：同 run 只反思一次；同 reflection 只 replan 一次
- 再次确认：REPLAN 后新 run 必须再 confirm

严格验收标准（必须全部满足）：
- 同一 run 不会重复触发 reflection
- 同一 reflection 不会重复触发 adjustment
- attempt 增长正确；达到上限转 BLOCKED

红队审查清单：
- 是否可能双执行/重复副作用？
- 是否可能无限 replan？

测试要求（必须）：
- Integration/E2E：不通过 -> 自动 REPLAN -> attempt+1 -> 再次确认 -> 再执行 -> PASS/NEED_USER/BLOCKED

---

### Phase 5：实验链路与实际链路入口统一（用户无感）

交付物：
- 所有真实执行统一走 Runs（实验入口内部转发/桥接到 Runs）
- Session 只认 `run_id` 的证据；WorkflowAgent 不再自认完成
- 对话与编辑器入口的“执行→验收”事件序列一致（差异仅 workflow_id）

严格验收标准（必须全部满足）：
- 不存在“无 run_id 的真实执行”
- 入口不同但闭环一致（同样的 verdict 语义、同样的证据要求、同样的 confirm 策略）

红队审查清单：
- 是否仍存在旧路径绕开 Runs？
- 是否存在事件重复投递造成 UI/Session 状态错乱？

测试要求（必须）：
- E2E：对话入口与编辑器入口各跑一条闭环用例，结果一致

---

### Phase 6：最终测试门禁（Release Gate）

最终验收（Definition of Done，必须全部满足）：

1) 全测试通过（含新增 unit/integration/e2e）
2) 至少 1 条“REPLAN 后再次确认”的端到端用例全绿（可复现、可回放）
3) 任意 PASS 都能输出结构化 Acceptance Report（含 evidence_map 与 test_report_ref）
4) 事件契约合规（仅 `workflow_*`/`node_*`，且包含 `run_id`、`executor_id`）

---

## 11. 与现有规划文档的关系（避免口径漂移）

- 本文档解决：“执行完成后如何严格验收并自动闭环 replan”。
- 能力口径/节点事实源统一属于另一个维度，参考：
  - `docs/planning/workflow-capability-unification-milestones.md`
  - `docs/planning/workflow-usability-acceptance-criteria-table.md`
  - `docs/planning/workflow-usability-test-matrix.md`

---

## 12. 执行记录（每阶段完成必须追加）

> 规则：每完成一个 Phase，必须在此追加记录：完成日期、变更摘要、测试结果、遗留风险。

### Phase 0 记录
- 完成日期：2026-02-04
- 变更摘要：补充 Phase 0 交付物（入口矩阵 / “无 Run 的事实执行”清单 / 证据来源与缺口）；不改行为。
- 测试结果：`python -m pytest -q tests/unit/interfaces/api/test_runs_routes.py` 通过
- 遗留风险：
  - `disable_run_persistence=true` 仍允许无 `run_id` 的事实执行（回滚/兼容路径，Phase 5 需收敛或 fail-closed）
  - `WorkflowAgent` 仍存在无 `workflow_run_execution_entry` 时的 legacy 执行回退（Phase 5 需收敛或禁止）
  - `artifact_refs[]` / `test_report_ref` 尚未形成标准化落库与可复查引用（Phase 2/6 需补齐）

### Phase 1 记录
- 完成日期：2026-02-04
- 变更摘要：新增 Session 侧 CriteriaManager（schema/合并/冲突检测/最小追问），为后续 Acceptance Loop 提供可复用基元。
- 测试结果：`python -m pytest -q tests/unit/application/services/test_criteria_manager.py` 通过
- 遗留风险：
  - 当前为纯逻辑模块，尚未接入 Session/对话侧持久化与闭环编排（Phase 4/5 需接线）
  - 冲突/主观性识别为启发式实现，可能存在误报/漏报（需在真实用例上迭代，并限制 NEED_USER 噪声）

### Phase 2 记录
- 完成日期：2026-02-04
- 变更摘要：新增 Evidence Collector（`run_id -> evidence snapshot`），定义 `run_event:` 引用格式；提供幂等、顺序无关的证据快照生成逻辑。
- 测试结果：`python -m pytest -q tests/integration/test_run_evidence_collector_integration.py` 通过
- 遗留风险：
  - `artifact_refs[]` / `test_report_ref` 仍为占位（Phase 2/6 需补齐真正的引用与存储）
  - 当前 collector 直接依赖 ORM（用于读取 RunEvents）；后续若要严格分层，可引入读取型 repository port
  - 尚未接线到 “run 终态 -> reflection/验收” 的自动链路（Phase 4 处理）

### Phase 3 记录
- 完成日期：2026-02-04
- 变更摘要：新增 Acceptance Evaluator（PASS/REPLAN/NEED_USER/BLOCKED）与边界规则：PASS 硬约束、attempt 上限、unmet 不收敛转 NEED_USER。
- 测试结果：`python -m pytest -q tests/unit/application/services/test_acceptance_evaluator.py` 通过
- 遗留风险：
  - 当前仅对“baseline 成功标准”提供最小可用的 run-event 评估逻辑；其他标准会 fail-closed 进入 missing_evidence（后续需扩展映射规则）
  - `test_report_ref` 仍为外部输入/占位（Phase 6 需落库与引用标准化）
  - 尚未自动触发与事件闭环（Phase 4 需编排/去重/发布 workflow_* 事件）

### Phase 4 记录
- 完成日期：2026-02-04
- 变更摘要：新增 Acceptance Loop Orchestrator：Run 终态后自动生成 lifecycle 事件链（`workflow_execution_completed` -> `workflow_reflection_requested` -> `workflow_reflection_completed`），并在 verdict=REPLAN 时发布 `WorkflowAdjustmentRequestedEvent` 复用现有 REPLAN 链路；补齐幂等/去重（execution_completed/run_id、reflection/requested/reflection_id、adjustment/reflection_id），并对流式取消/断开场景做 fail-closed（未终态不触发）。
- 测试结果：`python -m pytest -q tests/integration/test_acceptance_loop_orchestrator_integration.py` 通过
- 遗留风险：
  - attempt 的“跨 run 增长”仍依赖 Session/对话侧接线与状态持久化（Phase 5 需打通）
  - `workflow_test_report` 目前为最小确定性门禁占位（Phase 6 需标准化 test_report_ref 的落库与引用）
  - 对话/编辑器入口尚未完全统一到“run->验收->replan->再 run”的端到端闭环用例（Phase 5/6 需补齐 E2E）

### Phase 5 记录
- 完成日期：2026-02-04
- 变更摘要：
  - Fail-Closed 统一入口：`disable_run_persistence=true` 时禁止任何 workflow 执行；`/api/workflows/{workflow_id}/execute/stream` 强制要求 `run_id`；移除“缺 entry 时回退 legacy 执行”的兼容路径（改为 500 misconfiguration）；后台/调度执行同样 fail-closed。
  - 禁止无 Run 的事实执行：WorkflowAgent `execute_workflow` 决策强制 `run_id` + `WorkflowRunExecutionEntryPort`（未注入则失败），确保所有真实执行都可审计（Runs SoT）。
  - 新增入口一致性覆盖：编辑器 execute/stream 与 validated decision 执行均生成一致的验收生命周期事件序列（workflow_execution_completed -> workflow_reflection_*）。
- 测试结果：
  - `python -m pytest -q tests/integration/api/workflows/test_execute_stream_validation_gate.py` 通过
  - `python -m pytest -q tests/unit/interfaces/api/test_workflow_executor_adapter.py` 通过
  - `python -m pytest -q tests/unit/domain/agents/test_workflow_agent.py` 通过
  - `python -m pytest -q tests/integration/api/workflows/test_execute_uses_orchestrator.py` 通过
  - `python -m pytest -q tests/integration/api/workflows/test_acceptance_loop_entry_parity.py` 通过
- 遗留风险：
  - attempt 的跨 run 持久化/自动递增仍未贯通；当前 orchestrator 入口默认 `attempt=1`，需由 Session/对话侧在 rerun 时传入 attempt。
  - `workflow_test_report` 仍为最小确定性门禁占位；尚未与 CI/真实测试报告产物（`test_report_ref`）对齐。

### Phase 6 记录
- 完成日期：2026-02-04
- 变更摘要：
  - Release Gate 用例补齐：新增“REPLAN 后新 run 必须再次确认（confirm_id 不复用）”集成用例；并验证 PASS 的 `workflow_reflection_completed` 输出包含结构化 `evidence_map` 与 `test_report_ref`。
  - 修复/适配 domain 集成场景对 Phase 5 新契约（`run_id` + RunEntry）的要求（保持测试 DB-free，通过 in-memory RunEntry 注入）。
  - 全量测试门禁通过。
- 测试结果：`python -m pytest -q` 全绿（7155 passed）。
- 遗留风险：
  - 自动 rerun（收到 `WorkflowAdjustmentRequestedEvent` 后自动创建新 run 并执行）仍依赖对话/Session 层编排；当前保证的是事件/证据闭环与幂等，但不强制“自动重跑”。
  - `artifact_refs[]` / `test_report_ref` 的真实存储与引用机制仍待落地（后续需与 deterministic E2E/CI 产物对齐）。
