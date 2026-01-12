# Playwright MCP 用户模拟落地规划（Workflow Studio）

## 1. 目标与边界

**目标**：用 Playwright（测试套件）+ Playwright MCP（交互式浏览器操作）模拟真实用户，从“打开编辑器 → 配置节点 → 保存/运行 → 处理确认/错误 → 导出/回放”形成可回归闭环，支撑以下业务蓝图逐步落地：

- 数据/报表自动化：`database(data_collection)` → `transform(data_process)` → `python(metric_calculation)` → `llm_analysis` → `file(export)`
- 外部系统对账/同步：`api(http)` → `transform(mapping)` → `database(upsert)` → `notification(retry/alert)`
- 运营/客服知识助理：`http/db` → `llm(answer)` →（下一阶段）`human(confirm)`
- 代码/研发助手（内网）：`file(read)` → `llm(review/suggest)` → `python(static_checks)`
- 订单/风控类流水线：固化 `kind: workflow` 模板蓝图，并补齐 `parallel/sequential/human` 模板落地与执行器契约

**边界（KISS/YAGNI）**：
- deterministic E2E：不访问外网/真实 LLM；所有不确定性必须可被 stub/fixture 控制。
- “真实用户模拟”的最低标准：只通过 UI（含确认弹窗 Allow/Deny）驱动；不把后端改成默认自动 allow（除非作为可选开关）。

---

## 2. 多智能体协作拆分（可并行但交付串行）

- **QA/Automation Agent**：定义可回归用户旅程、稳定选择器与等待条件；产出 Playwright E2E 与 MCP 操作脚本。
- **Frontend Agent**：补齐节点渲染/配置面板、data-testid、弹窗一致性与可观测性（data-status）。
- **Backend Agent**：补齐 fixture/seed、deterministic stub、模板/执行器契约一致；保证状态机可达终态。
- **Architect Agent**：统一“副作用确认”契约（何时触发、一次 run 可能触发次数、Allow/Deny 的幂等语义）。

交付顺序建议：Backend(契约/fixture) → Frontend(testid/可观测性) → QA(E2E/MCP)。

---

## 3. 稳定选择器与 UI 可观测性

**核心 data-testid（必须稳定）**：
- 画布：`workflow-canvas`
- 节点：`workflow-node-{nodeId}`（后端提供 nodeId，E2E 从 workflow JSON 读取）
- 运行：`workflow-run-button`
- 保存：`workflow-save-button`
- 执行状态：`workflow-execution-status`（读取 `data-status`：`idle|running|completed`）
- 副作用确认弹窗：`side-effect-confirm-modal`
  - `confirm-allow-button`
  - `confirm-deny-button`
  - `confirm-id-hidden`（仅测试用）

**等待策略（Fail-Closed）**：
- 不依赖动画/时序：统一等待 `data-status` 进入终态（`completed|idle`）作为收敛条件。
- 遇到副作用确认：测试与 MCP 操作都要支持“一次 run 多次确认”的循环处理。

---

## 4. 场景化 E2E 用例蓝图（deterministic 优先）

### 4.1 数据/报表自动化（UX-WF-006）

**固定链路**：`database` → `transform` → `python` → `textModel(llm)` → `file`

**验收点**：
- 画布存在以上关键节点（通过 `workflow-node-{id}` 校验）
- 点击 Run 后能通过副作用确认并到达终态
- `file` 输出可在执行日志/输出面板中被观察（若 UI 暂未展示，至少保证 run 终态达成）

**提示词模板（生产/非 deterministic）**：
- `llm_analysis`：`“根据输入指标，用 5 条要点总结本期变化，并给出 2 条行动建议。输出 JSON: {summary:string, highlights:string[], actions:string[]}”`

### 4.2 对账/同步（API→Transform→DB upsert→Notification）

**固定链路**：`api` → `transform` → `database(upsert)` → `notification`

**验收点**：
- upsert 节点在 deterministic 下写入 mock DB（或 test sqlite）
- 失败场景触发 retry/notification（notification 模板可渲染、执行器可被调用）

**提示词模板（可选）**：
- `llm`：`“把以下对账差异转换成面向运营的中文解释（<=120字），并给出是否需要人工介入（yes/no）。输出 JSON。”`

### 4.3 运营/客服知识助理（HTTP/DB→LLM→Human）

**现阶段**：`human` 仅规划，不进入 deterministic 回归门禁（避免引入交互依赖）。

**提示词模板**：
- `llm`：`“基于上下文回答用户问题；若上下文不足，明确提出需要的补充信息。输出结构化：{answer, followups[]}”`

### 4.4 代码/研发助手（File→LLM→Python）

**固定链路**：`file(read)` → `llm(review)` → `python(static_checks)`

**提示词模板**：
- `llm`：`“审查以下 diff，指出潜在 bug/可维护性问题，按严重级别排序，给出最小改动建议。”`

---

## 5. Playwright MCP（交互式）操作脚本约定

> 目标：把 E2E 的稳定选择器复用到 MCP 浏览器操作，做到“同一套定位策略，两种执行形态（自动回归/人工演示）”。

**推荐最小操作序列**：
1. `browser_navigate` 打开编辑器：`/workflows/{workflow_id}/edit`
2. 等待 `workflow-canvas` 可见
3. 点击 `workflow-run-button`
4. 循环：若 `side-effect-confirm-modal` 可见，则点击 `confirm-allow-button`，等待弹窗隐藏
5. 轮询 `workflow-execution-status[data-status]`，直到 `completed|idle`

**诊断信息（必须可观测）**：
- 控制台日志：确认是否触发 confirm API、是否有异常
- 网络请求：确认 Allow 点击是否调用 confirm endpoint（按 run_id/confirm_id）

---

## 6. 风险清单与对策（Red Team）

- **风险：一次 run 多次副作用确认导致卡死**
  对策：测试与 MCP 都实现“循环确认 + 最大次数 + 属于同一 run 的校验”。

- **风险：状态指示器更新滞后导致误判超时**
  对策：以 `data-status` 为准，使用 `toPass` 轮询；必要时增加 `data-last-run-id` 之类更强信号（仅在需要时引入）。

- **风险：deterministic stub 与生产语义漂移**
  对策：stub 仅对外部依赖（LLM/HTTP）生效；副作用确认语义保持真实（默认 deny）。
