---
mode: plan
cwd: D:\My_Project\agent_data
task: 工作流核心业务“彻底收敛”实施（V3）执行计划（含验收标准）
complexity: complex
planning_method: builtin
created_at: 2026-01-03T16:08:34.2297923+08:00
---

# Plan: Workflow Convergence V3（落地执行计划）

本计划用于把当前实现收敛为**单一业务真相（Single Source of Truth）**：创建/修改/执行链路唯一化、监督 fail-closed、执行内核单一权威、Tool/Node 强约束、以及 DDD 边界不越界。计划以 `docs/architecture/workflow_convergence_v3_plan.md` 的目标与不变式为主，以 `Report.md` 的“事实镜像”作为当前差距与证据基线。

---

## 0. 输入与约束（必须先确认）

### 0.1 输入文档（计划依据）
- 解决方案/交付清单：`docs/architecture/workflow_convergence_v3_plan.md`
- 事实镜像/差距证据：`Report.md`

### 0.2 总体不变式（必须全部满足）
> 直接复用 `docs/architecture/workflow_convergence_v3_plan.md` 的 I-1 ~ I-7，作为最终验收的“硬门”。

- I-1 只有一个创建入口：`POST /api/workflows/chat-create/stream`
- I-2 修改只有两个入口：`PATCH /api/workflows/{id}` 与 `POST /api/workflows/{id}/chat-stream`
- I-3 执行只有一个入口：`POST /api/workflows/{id}/execute/stream`
- I-4 执行内核单一权威：API 与 WorkflowAgent 共享同一个 kernel port
- I-5 Coordinator 监督强制且 fail-closed：所有副作用 action 先 allow 再执行
- I-6 TOOL 节点强约束：`node.type=TOOL` ⇒ `config.tool_id` 存在且可用且非 deprecated
- I-7 DDD：Domain 不依赖 Interface/Infrastructure；实现通过 Port 注入

### 0.3 “不做什么”（Out of scope，防止计划膨胀 / YAGNI）
- 不新增新的业务能力（例如：新的 Workflow 类型、新的执行器能力），仅收敛、删链路、统一语义与强化校验。
- 不在本阶段引入复杂灰度发布系统（如需灰度，仅使用现有 feature flags/配置）。
- 不改变前端核心交互（画布拖拽/对话修改/Run），仅收敛其调用链路与失败语义为 fail-closed。

---

## 1. 里程碑与交付节奏（可回滚、可验证）

> 原则：每个 Milestone 结束都必须满足对应验收标准（AC），并输出可验证证据（日志/测试记录/路由清单）。不跨阶段堆叠不确定改动。

### Milestone 列表（建议顺序）
1. M0：基线锁定（路由/契约/测试护栏）
2. M1：删除 WebSocket 画布修改链路（方案一：彻底删除）
3. M2：DDD 越界清理（Domain → Infrastructure/Interface）
4. M3：Coordinator 监督统一入口（policy chain，fail-closed）
5. M4：对话修改端点收敛（仅保留 `/chat-stream`，统一 SSE 协议与监督）
6. M5：创建端点收敛（仅保留 `/chat-create/stream`，删除 legacy create）
7. M6：Run 强一致 + 执行入口唯一化（仅保留 `/execute/stream`，强制 run_id）
8. M7：执行内核单一权威（Kernel Port + LangGraph 实现对齐事件粒度）
9. M8：计划验证闭环（WorkflowAgent 验证计划可达性 + 纳入监督）

---

## 2. 验收总体方法（如何证明“彻底收敛”）

### 2.1 验收证据类型（每个 AC 必须至少一种）
- 路由表/OpenAPI 证据：目标端点存在、被删端点不存在/404
- 自动化测试：pytest/vitest/import-linter（或等价静态检查）
- 行为证据：SSE 事件序列与错误码、事务回滚、Run 事件落库
- 前端网络行为：浏览器 Network 面板或单测断言（例如无 WebSocket 连接）

### 2.2 必须产出的“验收记录”文件（建议新增）
- `docs/architecture/workflow_convergence_v3_acceptance.md`（或 `issues/` 下的可追踪记录）：记录每条 AC 的证据链接（日志/截图/测试命令输出）。

> 注：上述文件为建议交付物；如项目已有统一的验收记录规范，按现有规范落地即可。

---

## 3. 执行计划（Action Items，逐步可落地）

> 每步都包含：目标、改动范围、验证/验收、回滚点。执行时严格遵循 KISS（最小改动）、DRY（避免多实现并存）、SOLID（用 Port/Policy 解耦）。

### 3.1 Phase 1（M0）：基线锁定（防回归护栏）

**目标**
- 把“允许存在的路由集合/协议集合”固化为可执行护栏，避免边改边回归。

**主要工作项**
- 产出“允许路由清单”与“禁止路由清单”（直接来源于 I-1/I-2/I-3）。
- 新增/改造后端路由存在性测试（OpenAPI 或 route table）：
  - T-ROUTE-1：只允许目标集合；所有被删端点必须 404/不存在。
- 固化关键契约测试：
  - T-SSE-1：`chat-create/stream` 首事件必须含 `metadata.workflow_id`
  - T-SSE-CHAT-1：`chat-stream` 事件类型只允许 `thinking/tool_call/tool_result/final/error`
- 对现有测试进行“预期更新清单”梳理（哪些会因删链路变成 404/移除）。

**验收标准（AC-M0-*）**
- AC-M0-1：存在一组自动化测试能证明“当前路由集合”与“目标路由集合”的差异（至少能在收敛过程中防止目标端点被误删/误增）。
- AC-M0-2：在未开始删链路前，现有测试可在本地稳定执行（或明确标注哪些因环境缺依赖暂不可跑，并给出替代验证方式）。

**回滚/降级**
- 若测试护栏导致大面积失败且短期无法修复：先将护栏测试标注为 xfail/skip（带 TODO + 触发条件），但必须保留“路由清单”文本作为人工验收依据。

---

### 3.2 Phase 2（M1）：删除 WebSocket 画布修改链路（方案一）

**目标**
- 彻底移除“WS 作为修改链路/画布同步链路”的可能性，消除死链路带来的认知偏差与误用风险。

**主要工作项**
- 前端：删除 `useCanvasSync` 及其所有引用；移除任何 `new WebSocket('/ws/workflows/...')` 的调用入口。
- 后端：删除 websocket 路由文件或确保不可达并清理引用。
- 更新/删除相关测试：
  - 删除 websocket e2e（若其覆盖的是 workflow canvas sync）
  - 新增前端单测：T-FE-WS-1（mock WebSocket，断言未实例化）

**验收标准（直接复用 AC-WS-* 并补充证据要求）**
- AC-WS-1：前端构建/运行不再发起 `/ws/workflows/{id}` 连接尝试（浏览器网络面板/单测证据）。
- AC-WS-2：后端 OpenAPI 中不存在任何 websocket 路由，仓库中无 websocket route 文件或引用（静态检索证据）。
- AC-WS-3：删除后不影响“拖拽保存”和“对话修改”核心路径（跑通 drag PATCH 与 chat-stream 的集成测试）。
- AC-WS-4（补充）：前端不再出现“失败重连/回退到 WS”的隐式逻辑（全局搜索 `ws/workflows` 为 0）。

**回滚/降级**
- 若删除前端 hook 影响编辑页加载：允许短期以 no-op stub 替代，但必须保证不会创建 WebSocket（仍满足 AC-WS-1）。

---

### 3.3 Phase 3（M2）：DDD 越界清理（Domain → Infrastructure/Interface）

**目标**
- 先把边界拉正，避免后续重构把越界扩散；符合 I-7。

**主要工作项**
- 识别并移除 Domain 层直接 import Infrastructure 的路径（`Report.md` 已给出至少两处事实证据）。
- 用 Port + Application 装配替代：
  - 在 Domain 侧只定义接口（Port）与纯业务规则
  - 在 Infrastructure 提供实现
  - 在 Application/Interface 做依赖注入/装配
- 强化边界检查：
  - 优先启用 `python -m importlinter`（确保 dev 依赖可用）
  - 若环境不可用：增加替代静态检查（脚本/pytest）禁止 `src/domain` import `src/infrastructure` / `src/interfaces`

**验收标准**
- AC-DDD-1：`src/domain` 中不存在 `import src.infrastructure`（包括延迟导入/fallback）。
- AC-DDD-2：import-linter（或替代静态检查）可在本地/CI 执行并通过。
- AC-DDD-3（补充）：新增的 Port 命名与职责满足 SOLID（单一职责、依赖倒置），且不引入“服务定位器式”反模式。

**回滚/降级**
- 若一次性清理影响面过大：按模块拆分（ConversationAgent 相关、WorkflowAgent 相关），每次只替换一处越界并配套测试通过。

---

### 3.4 Phase 4（M3）：Coordinator 监督统一入口（Policy Chain，fail-closed）

**目标**
- 消除“路由层手工 validate / 端点绕过监督”的碎片化，达成 I-5。

**主要工作项**
- 将监督收敛为 Application 层的统一 policy chain（建议复用/接入 `ConversationTurnOrchestrator` 的模式）。
- 将所有可能产生副作用的动作（尤其 tool_call）显式映射为可监督的 decision：
  - 统一 publish `DecisionMadeEvent`（或等价事件）
  - Coordinator middleware 能稳定 allow/deny 并可观测
- 删除/迁移路由层的手工 coordinator.validate_decision 分支（避免双逻辑）。

**验收标准**
- AC-SUP-1：所有副作用 action 都能被 Coordinator 拦截（allow/deny 可观测）。
- AC-SUP-2：不存在绕过 supervisor 的入口（workflow chat 端点与通用 conversation 端点一致策略）。
- AC-SUP-3：拒绝必须 fail-closed：被拒绝 action 不产生任何持久化或外部副作用（事务回滚 + 可验证）。
- AC-SUP-4（补充）：监督拒绝的错误码/事件类型统一（例如 `COORDINATOR_REJECTED`），前端可稳定识别并给出可操作提示。

**回滚/降级**
- 若统一 policy chain 影响所有对话链路：可先只覆盖 workflow chat 链路（收敛目标域），但必须保证不存在 workflow 端点绕过监督。

---

### 3.5 Phase 5（M4）：对话修改端点收敛（仅保留 `/chat-stream`）

**目标**
- 对话修改严格只保留一个端点形态，统一 SSE 协议与监督策略，符合 I-2。

**主要工作项**
- 合并 `chat-stream-react` 能力进入 `chat-stream`（在 use case/服务层统一，而非路由层拼逻辑）。
- 删除 `POST /api/workflows/{id}/chat-stream-react` 与 `src/interfaces/api/routes/chat_workflows.py`（避免重复实现）。
- 统一 SSE 事件：`thinking/tool_call/tool_result/final/error`（及其 payload schema）。
- 对话修改后的保存校验作为硬门（DAG 可执行性、tool_id、executor 等）。

**验收标准**
- AC-CHAT-1：OpenAPI 中仅存在一个对话修改端点 `POST /api/workflows/{id}/chat-stream`；`chat-stream-react` 不存在/404。
- AC-CHAT-2：对话 SSE 事件只出现五类事件名；不再出现历史冲突事件名。
- AC-CHAT-3：任何副作用 action 必须先 Coordinator allow；deny 时 SSE 返回 `COORDINATOR_REJECTED`（或等价）并终止 stream。
- AC-CHAT-4：保存校验失败则回滚，且 SSE 明确错误（可定位到 tool_id/DAG/配置项）。
- AC-CHAT-5（补充）：前端不再包含对“react 端点”的调用逻辑（全局检索为 0）。

**回滚/降级**
- 若合并期间需要短暂兼容：允许保留旧端点但必须不可达（feature flag 默认关闭且测试证明默认 404），并限定移除期限。

---

### 3.6 Phase 6（M5）：创建端点收敛（仅保留 `chat-create/stream`）

**目标**
- 删除 legacy create，保证创建语义单一且 fail-closed，符合 I-1。

**主要工作项**
- 后端删除 `POST /api/workflows`（deprecated 但可达）路由与 handler。
- 前端删除 legacy create mode（query/env 开关）与 legacy 分支调用。
- 契约：首个 SSE 事件必须含 `metadata.workflow_id`，用于前端跳转/初始化编辑页。
- 创建失败必须不产生“半成品 workflow”（事务/回滚策略明确）。

**验收标准**
- AC-CREATE-1：OpenAPI 中仅存在 `POST /api/workflows/chat-create/stream`，不存在 `POST /api/workflows`。
- AC-CREATE-2：前端无任何路径触发 legacy create（无 query/env 分支）。
- AC-CREATE-3：chat-create 首事件稳定包含 `metadata.workflow_id`，并有契约测试覆盖（T-SSE-1）。
- AC-CREATE-4：创建失败 fail-closed：无半成品数据（以 DB 事务与回滚证据为准）。

**回滚/降级**
- 若线上依赖 legacy create：需要先做调用方盘点与迁移窗口（日志统计 + 兼容期），再删除；但“兼容期”必须严格不可默认启用。

---

### 3.7 Phase 7（M6）：Run 强一致 + 执行入口唯一化（仅 streaming + 强制 run_id）

**目标**
- 点击 Run 的语义与“可追踪/可回放”一致，执行入口唯一化，符合 I-3，并补齐 Run 强一致。

**主要工作项**
- 删除非流式执行：`POST /api/workflows/{id}/execute`。
- 保留并强化 `POST /api/workflows/{id}/execute/stream` 作为唯一入口。
- 强制 run_id：
  - 前端：Run 创建失败则不执行（不允许降级“无 run_id 执行”）
  - 后端：缺 run_id 直接拒绝（400/409），禁止静默降级
- Run 关键事件强一致落库（至少 start/complete/error 不可丢）：
  - 若现有 recorder 为 best-effort：需要把“关键事件”走同步/事务路径或引入可证明不丢的机制（注意 KISS：只对关键事件强一致）。

**验收标准**
- AC-RUN-1：执行时 run_id 必填；缺失必拒绝且错误明确。
- AC-RUN-2：Run 关键事件强一致落库（start/complete/error 不丢），并可通过测试/查询验证。
- AC-RUN-3：一个 run_id 只能对应一次执行上下文（workflow_id、输入快照、executor/kernel_id）。
- AC-RUN-4：前端 UX 与语义一致：Run 创建失败则不执行且提示可操作原因。
- AC-RUN-5（补充）：移除/禁止“Runs API 全局禁用仍允许执行但无 run”的路径；若必须保留禁用模式，则应整体 fail-closed（Run 功能禁用 ⇒ 禁止执行入口，或提供替代一致性方案）。

**回滚/降级**
- 若强制 run_id 影响紧急执行需求：只能通过显式开关降级（默认关闭），且降级时必须有替代追踪机制或明确告警；不得 silent。

---

### 3.8 Phase 8（M7）：执行内核单一权威（Kernel Port + LangGraph）

**目标**
- API 执行与 WorkflowAgent 执行共用同一套 kernel port，实现单一权威（I-4），并保证 streaming 事件粒度不退化。

**主要工作项**
- 在 Domain 定义 `WorkflowExecutionKernelPort`（或等价命名）：
  - `execute(...)`
  - `execute_streaming(...)`
- API 执行路径与 WorkflowAgent 执行路径都只依赖该 port。
- LangGraph 成为该 port 的 Infrastructure 实现（并补齐 node 级 streaming 事件）。
- 移除“双内核”可达路径（feature flag 造成的语义分裂需要彻底收敛）。

**验收标准**
- AC-KERNEL-1：仓库中不存在两套“可达的 workflow 执行语义”；所有执行都通过同一 kernel port。
- AC-KERNEL-2：API 执行与 WorkflowAgent 执行的事件序列语义一致（至少 node_start/node_complete/node_error/workflow_complete/workflow_error）。
- AC-KERNEL-3：LangGraph streaming 粒度等价或更强（不能退化为仅 start/complete/error）。
- AC-KERNEL-4（补充）：kernel_id/executor_id 在 Run 记录中可追踪且与实际执行一致（便于回放与问题定位）。

**回滚/降级**
- 若 LangGraph 事件补齐风险较大：允许先实现 kernel port，并让现有引擎作为 port 的实现；再切换到 LangGraph（但必须保证“单一 port”与“单一可达语义”先成立）。

---

### 3.9 Phase 9（M8）：计划验证闭环（WorkflowAgent 验证计划可达性）

**目标**
- 将“计划验证”变成硬门：generate_plan → validate → commit → execute；并纳入 Coordinator 监督（fail-closed）。

**主要工作项**
- 明确计划结构与验证输入（workflow 当前状态、目标、约束、可用工具集合）。
- WorkflowAgent 作为验证者输出可证伪结果：
  - pass：允许 commit/execute
  - fail：给出最小可行动的修正建议（例如缺 tool_id/不可达 DAG）
- 验证事件/结果进入可观测体系（SSE/日志/Run 记录）。

**验收标准**
- AC-PLAN-1：对话生成的计划在执行前一定经过 validate；失败必阻断（fail-closed）。
- AC-PLAN-2：validate 结果可观测（事件/错误码/日志），且前端能提示下一步。
- AC-PLAN-3：验证覆盖关键失败模式：缺 tool、DAG 不可达、执行器不可用、权限/监督拒绝。

**回滚/降级**
- 若短期无法在所有场景引入 validate：至少在 workflow chat 修改与 workflow execute 入口强制 validate（关键链路优先），并清晰标注未覆盖场景。

---

## 4. 测试与验证（强制执行顺序）

### 4.1 后端（pytest）建议执行序列
1) 快速回归：`pytest -q`
2) workflow API：`tests/integration/api/workflows/`（重点：路由唯一性、execute/stream、legacy 404）
3) coordinator：`tests/integration/test_coordinator_integration.py` 与 `tests/integration/api/coordinator/`
4) SSE：`tests/integration/api/test_conversation_stream_api.py`、`tests/integration/api/test_sse_disconnect_reconnect.py`
5) DDD：`python -m importlinter`（或替代静态检查）

### 4.2 前端（Vite/Vitest）建议执行序列
- `npm test`
- `npm run build`
- `npm run lint`
- `npm run type-check`

### 4.3 必须新增/改造的测试类型（最小集合）
- T-ROUTE-1：路由存在性（只允许 I-1/I-2/I-3 规定的集合）
- T-SSE-1：chat-create 首事件 workflow_id 契约
- T-SUP-1：coordinator deny ⇒ 事务回滚 + `COORDINATOR_REJECTED`
- T-RUN-1：execute/stream 缺 run_id ⇒ 拒绝；关键事件落库可验证
- T-FE-WS-1：不再创建 WebSocket
- T-FE-CREATE-1：前端无 legacy create 分支
- T-FE-RUN-1：Run 创建失败 ⇒ execute API 不被调用

---

## 5. 可追踪性（交付物清单 + 验收矩阵）

### 5.1 交付物清单（DoD 必备）
- 代码：删除多余链路、收敛端点、统一监督、统一 kernel port、DDD 清理
- 文档：
  - `docs/architecture/workflow_convergence_v3_plan.md`（若需补齐：SSE schema/错误码/回滚策略/验收记录模板）
  - `docs/architecture/workflow_convergence_v3_acceptance.md`（或等价验收记录）
- 测试：
  - 新增/改造的 pytest/vitest 用例（见 §4.3）
  - import-linter 或替代静态检查

### 5.2 验收矩阵（Invariants → AC → Tests）
| Invariant | 关键 AC | 主要测试/证据 |
|---|---|---|
| I-1 创建唯一 | AC-CREATE-1/2/3/4 | T-ROUTE-1, T-SSE-1, FE 创建路径测试 |
| I-2 修改仅两入口 | AC-CHAT-1/2/3/4, drag PATCH 现有用例 | T-ROUTE-1, workflow chat 集成测试 |
| I-3 执行唯一 | AC-RUN-1, 删除 /execute | T-ROUTE-1, T-RUN-1 |
| I-4 内核单一权威 | AC-KERNEL-1/2/3/4 | kernel port 单测/集成测试 + 事件序列对比 |
| I-5 监督强制 | AC-SUP-1/2/3/4 | T-SUP-1 + 端到端 deny 回滚证据 |
| I-6 TOOL 可识别 | AC-TOOL-1/2（方案文档） | 保存校验测试 + 对话生成 tool_id 的契约测试 |
| I-7 DDD 不越界 | AC-DDD-1/2/3 | import-linter / 静态扫描 |

---

## 6. 风险与阻塞（红队视角）

### 6.1 主要风险
- **回归面大**：删除端点/链路会导致前后端调用路径与测试同时变更（需以 M0 护栏锁住）。
- **监督边界不清**：tool_call 若未统一映射为 supervised decision，会留下 I-5 缺口（必须作为硬门）。
- **Run 强一致与性能权衡**：关键事件强一致可能带来阻塞写入；需限定“关键事件集合”而非所有事件。
- **LangGraph 事件粒度补齐**：实现复杂度高，易出现事件语义不一致（必须用 AC-KERNEL-2/3 做约束）。
- **环境依赖**：import-linter 未安装、前端/后端依赖未就绪会阻塞验证（需准备替代静态检查与最小可跑命令集）。

### 6.2 典型阻塞与应对
- 阻塞：CI/本地无法运行 `python -m importlinter` → 应对：先落地替代静态扫描（脚本/pytest），并把 import-linter 纳入依赖修复任务。
- 阻塞：现网仍调用 legacy create/execute → 应对：日志盘点 + 迁移窗口 + 明确切换日；默认仍以“删除可达入口”为最终目标。

---

## 7. Definition of Done（最终完成定义）

只有当以下全部满足，才视为“彻底收敛完成”（与解决方案文档一致，补充了证据要求）：

1) 路由面：Create/Modify/Execute 入口数量满足 I-1/I-2/I-3，被删端点不可达（404/不存在），有 T-ROUTE-1 证明。
2) 监督面：所有副作用 action 在执行前都必须被 Coordinator allow（I-5），deny 可观测且 fail-closed（T-SUP-1 证明）。
3) 执行面：执行内核单一权威（I-4），API 与 WorkflowAgent 共享 kernel port；事件序列语义一致（AC-KERNEL-2 证明）。
4) 工具面：TOOL 节点强约束成立（I-6），对话修改能产出可保存且可执行的 tool_id（AC-TOOL-* 证明）。
5) Run 面：run_id 强制且关键事件强一致落库（AC-RUN-*），点击 Run 语义与可追踪性一致。
6) 架构面：DDD 不越界（I-7），并由 import-linter/替代静态检查证明。
7) 测试面：后端 pytest + 前端 vitest + lint/type-check 全绿，且新增的“路由唯一性/契约/监督/Run 强一致”测试覆盖到位。

---

## 8. 参考（关键事实证据入口）
- `docs/architecture/workflow_convergence_v3_plan.md`
- `Report.md`
- 路由注册位置（用于验证可达性）：`src/interfaces/api/main.py`（见 `Report.md` 证据段落）

