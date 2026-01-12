# Workflow 主链路稳定性与模板落地路线图（方案 A：Project 必选）

状态：Draft（以 deterministic E2E 为门禁）

## 0. 摘要（一句话）

先把 Workflow 主链路做成“可用且 fail-closed”的产品闭环（创建→编辑→保存→Run→执行→回放/确认），再把节点配置从“只读摘要”升级为“Schema 驱动可编辑模板”，最后补齐 `python/human/parallel/sequential` 等 executor_type 并固化为可复用蓝图库。

本方案选择 **方案 A：创建 Workflow 时 Project 必选**，从源头消灭 “缺少 projectId，无法创建 Run”。

---

## 1. 背景与现状（基于用户旅程的证据）

### 1.1 已观测到的 P0 阻断

1) **chat-create 早期跳转导致“workflow 不存在”**
- 现象：前端拿到 `workflow_id` 后跳转编辑器，但后端后续失败触发清理删除，导致 `GET /api/workflows/{id}` 404/500，UI 提示“工作流加载失败”。
- 影响：用户第一步就失败；无法进入后续编辑/运行闭环。

2) **project_id 缺失导致 Run 无法创建**
- 现象：workflow 的 `project_id=null` 时，前端直接提示“缺少 projectId，无法创建 Run”。
- 影响：主链路执行不可达；也无法验证回放/告警/人工确认。

3) **Run 创建稳定 400（integrity error）**
- 现象：`POST /api/projects/{project_id}/workflows/{workflow_id}/runs` 返回 400，错误被统一包装为 “failed to create run (integrity error)”。
- 影响：即便 workflow 有 project_id，也无法进入执行链路。

4) **deterministic 下 chat-stream 仍尝试真实 LLM**
- 现象：对话改图出现 “Connection error/401”。
- 影响：多智能体协作入口不可用；无法用对话来增量修改 workflow。

5) **模板层未落地：节点参数 readonly**
- 现象：`database/file/notification` 等节点表单字段只读（UI 仅显示默认值摘要）。
- 影响：用户无法按业务需要配置 DB/HTTP/File/告警参数，系统只能“画出来”，不能“跑起来”。

---

## 2. 目标 / 非目标

### 2.1 目标（按优先级）

**G0（P0）：主链路可用且 fail-closed**
- 创建 workflow 后不会跳到不存在的编辑页。
- 任一可运行 workflow：可保存、可创建 Run、可触发 execute/stream（或 Runs API 替代路径），并产生可观测结果。
- deterministic 模式下全流程不触网、不依赖真实密钥。

**G1（P1）：模板可编辑 + 前后端一致校验**
- 节点配置从“只读摘要”升级为“Schema 驱动表单”，可编辑、可保存、可回显、可校验。

**G2（P2）：能力扩展与蓝图库**
- 补齐 `python/human/parallel/sequential` executor_type 的模板与执行器对。
- 把 `kind: workflow` 固化为可复用“蓝图（Blueprint）”，支持实例化、参数化、版本化、灰度/回滚。

### 2.2 非目标（本期不做）
- 不在 Phase 0 引入复杂的分布式调度、多租户权限体系全量化、跨集群状态一致性等。
- 不在 deterministic 门禁期承诺真实外部系统对接（fullreal 只作为 Nightly/灰度）。

---

## 3. 关键决策：方案 A（Project 必选）

### 3.1 决策内容

在用户创建 workflow 的入口（首页对话创建、其他创建入口）要求必须提供 `project_id`：
- UI 提供 Project 选择器（默认选中最近使用/个人默认项目）。
- `chat-create/stream`、`seed`、内部导入等入口都必须确保 workflow 具有 `project_id`。

### 3.2 为什么是 A（而不是后端兜底）
- **fail-closed**：把“归属/权限边界”放到产品入口最可控，避免后端兜底引入隐性默认行为。
- **可审计**：每次创建都有明确 project 归属，运行/告警/回放可按 project 聚合与隔离。
- **更少隐患**：后端兜底会制造隐性数据（默认 project），需要额外清理与权限策略。

---

## 4. 分层与事实源（DRY）

### 4.1 分层定义
- **Definition**：节点能力定义（建议以 `definitions/nodes/*.yaml` + JSON Schema 作为事实源）。
- **Template**：节点模板（可编辑字段、默认值、版本号、side-effect 标注）。
- **Executor**：运行时执行器（DB/HTTP/File/Notification/LLM/Python/Human/ControlFlow）。
- **UI Form**：由 Schema 生成的表单，仅做展示与基础校验；最终安全判定在后端。
- **RunEvent**：运行事件流（用于回放、审计、告警追溯）。

### 4.2 不变量（必须被校验）
- Workflow：
  - 必须有 `project_id`（方案 A）。
  - `nodes/edges` 必须满足保存前拓扑校验（无孤岛/无非法边/side-effect 节点可追踪）。
- Run：
  - 必须绑定 `project_id/workflow_id/agent_id` 且满足 FK 约束。
  - Run 创建必须幂等（Idempotency-Key）且不会因为内部双写造成 integrity error。

---

## 5. 主链路契约（产品视角，fail-closed）

### 5.1 chat-create/stream（创建）

**目标**：前端永远不会跳转到不存在的 workflow。

建议契约（SSE 事件 metadata）：
- `workflow_id`：可在首事件给出（用于 UI “创建中”占位）。
- `workflow_status`：`creating | ready | failed`
- `project_id`：必须存在（方案 A）。

前端行为：
- `creating`：显示创建进度，不跳转。
- `ready`：跳转编辑器 `/workflows/{workflow_id}/edit`。
- `failed`：停留在创建页显示错误（可重试），不跳转。

### 5.2 编辑器（保存）

**目标**：用户可编辑配置并保存一致回读（Phase 1 完成）。

规则：
- 保存必须走后端强校验（语义校验 + 安全校验）。
- 保存失败要返回结构化错误（字段级 errors），前端可定位到节点/字段。

### 5.3 Run（创建与执行）

**目标**：点击 Run 的行为稳定可控且可观测。

规则：
- “创建 Run”与“补齐 Agent”必须由单一职责组件完成（路由 or repository 二选一），禁止双写。
- 创建 Run 失败时，前端必须 fail-closed：不触发 execute/stream。

### 5.4 side-effect（人工确认）

**目标**：任何外部副作用 fail-closed 且可审计。

规则：
- side-effect 节点运行到副作用前必须进入 `confirm_required`（或同义事件）。
- UI 必须给出 allow/deny；后端通过 `POST /api/runs/{run_id}/confirm` 接收决策。

---

## 6. 里程碑计划（Phase 0/1/2）

### 6.1 Phase 0（P0）：主链路可用性（门禁：5 个 deterministic E2E 全绿）

交付项：
1) chat-create 不再“先跳转再清理”
2) 创建入口 Project 必选（方案 A）
3) Run 创建不再出现 integrity error
4) deterministic 下 chat-stream 强制 stub/replay，不触网

验收（Definition of Done）：
- 下列 5 个 Playwright deterministic 用例全部通过（且可重复执行）：
  - `web/tests/e2e/deterministic/ux-wf-001-open-editor.spec.ts`
  - `web/tests/e2e/deterministic/ux-wf-002-save-workflow.spec.ts`
  - `web/tests/e2e/deterministic/ux-wf-003-run-workflow.spec.ts`
  - `web/tests/e2e/deterministic/ux-wf-004-side-effect-deny.spec.ts`
  - `web/tests/e2e/deterministic/ux-wf-005-replay-events.spec.ts`

建议执行命令（Windows PowerShell，示例）：
1) 后端（deterministic）：
   - `ENABLE_TEST_SEED_API=true`
   - `E2E_TEST_MODE=deterministic`
   - `LLM_ADAPTER=stub`
   - `HTTP_ADAPTER=mock`
   - 启动：`python -m uvicorn src.interfaces.api.main:app --host 127.0.0.1 --port 8000`
2) 前端：
   - `cd web && npm run dev -- --host 127.0.0.1 --port 5173`
3) 运行 E2E：
   - `cd web && npm run test:e2e:deterministic -- --reporter=list`

### 6.2 Phase 1（P1）：模板层可编辑（Schema 驱动表单）

交付项（MVP 节点集）：
- `database/http/file/notification/textModel/javascript`：
  - 可编辑字段定义（schema）
  - 默认值与版本策略
  - 保存前校验（字段级错误定位）

验收：
- 用户可修改 DB conn/SQL、HTTP URL/method、File path/op、Notification webhook/topic/body、TextModel 参数并保存回显一致。
- 非法配置 fail-closed，错误可定位到节点与字段。

### 6.3 Phase 2（P2）：能力扩展与蓝图库

交付项：
- `python`：用于数据处理与指标计算（限制内置能力、CPU/内存/超时、I/O 规则）。
- `human`：产品化人工确认节点（与 Runs confirm API 对齐）。
- `parallel/sequential`：作为编排原语（明确语义：并行分支、汇合策略、失败策略）。
- `kind: workflow` 蓝图库：模板库→实例化→参数化→版本化→灰度/回滚。

验收：
- 每个 executor_type 至少 1 条端到端用例 + 1 条失败闭环用例（重试/告警/人工确认）。

---

## 7. 多智能体协作体系（落地到工程与运维）

将“多智能体协作”从概念落到可交付边界（每个 Agent 对应一个稳定职责域）：

1) **Policy / Coordinator Agent**
- 职责：所有外部动作的审批（fail-closed）、审计、策略灰度。
- 产物：decision 日志、拒绝原因结构化、策略版本。

2) **Template Agent**
- 职责：定义/模板/Schema 的事实源维护与版本兼容。
- 产物：模板库、schema 校验、变更影响分析。

3) **Execution Agent**
- 职责：执行与资源隔离（超时、幂等、限流、重试框架）。
- 产物：RunEvent、执行结果快照、失败原因归因。

4) **Recovery / Notification Agent**
- 职责：失败闭环（重试→告警→人工确认→死信）。
- 产物：告警模板、通知通道策略、死信回放与重放。

5) **Observability Agent**
- 职责：把 RunEvent/日志聚合为可检索报告；SLO/告警溯源。
- 产物：Run 报告、关键指标仪表盘、回放入口。

---

## 8. 风险与回滚

### 8.1 风险
- 模板可编辑带来的安全风险（SQL/文件路径/HTTP SSRF）：必须后端强校验 + allowlist + sandbox。
- chat-create 契约调整可能影响前端跳转：需要 `workflow_status` 兼容期。
- 新增 executor_type（human/parallel）会引入状态机复杂度：先限定 MVP 语义与可观测性，再扩展。

### 8.2 回滚策略
- 任何阶段都必须保留 deterministic 门禁可跑。
- Runs API 与 execute/stream 的切换必须由 feature flag 控制，出现故障可回滚到稳定路径。
