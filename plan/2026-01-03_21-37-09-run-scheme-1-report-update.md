---
mode: plan
cwd: D:\My_Project\agent_data
task: run方案1其余一致：基于当前实现修订Report.md并制定闭环落地计划（Run事实源/回放、执行链路=WorkflowAgent、workflow用LangGraph、tool/node统一、Coordinator监督、严格ReAct、DDD不越界）
complexity: complex
planning_method: builtin
created_at: 2026-01-03T21:37:09.6419275+08:00
---

# Plan: Run方案1其余一致（含Report.md修订与验收标准）

🎯 任务概述
- 目标：在不改变你已声明的10条系统不变式前提下，以“Run方案1（workflow runs 落库）”作为点击 Run 的唯一事实源，补齐“可回放/可审计/一致性”，并修订 `Report.md` 使其与当前代码证据一致。
- 原则：KISS + DDD 边界明确（Interface 只承载HTTP/DTO；Application 编排与 policy；Domain 规则与 Ports；Infrastructure 适配 DB/LangGraph/LLM）。

📋 执行计划

- Phase 1：重新审计并修订 Report.md（防止过期结论误导）
  1. 复核三条关键链路现状：chat-create 创建、拖拽/对话修改、execute/stream 执行（含 run_id gate）。
  2. 更新 `Report.md` 的 Compliance Matrix：把“已实现/部分/缺失”基于当前代码逐条纠正，并补齐证据索引到具体文件行。
  3. 将“run方案1”定为唯一真源：在 `Report.md` 明确 Run/RunEvent/RunStatus 的事实语义、前后端契约与回放要求（避免并存两套真源）。

- Phase 2：Run方案1闭环补齐（回放能力 + 事件契约一致）
  4. 补齐/确认 RunEvent 查询 API：提供 `GET /api/runs/{run_id}/events`（支持 limit/cursor 或 offset，保证稳定顺序）。
  5. 前端接入真实回放：将 `web/src/hooks/useRunReplay.ts` 从 placeholder 改为调用回放 API，并用同一套事件渲染逻辑回放到 UI。
  6. 统一事件字段契约：对外 SSE 与回放事件保持同构（字段命名、executor_id/run_id/workflow_id、终态事件类型集合一致）。

- Phase 3：执行链路“唯一且等同 WorkflowAgent”（语义一致可证明）
  7. 确认 WorkflowAgent 与 REST execute/stream 是否调用同一 Kernel（WorkflowExecutionKernelPort/Orchestrator/Facade）。若不一致：收敛为“WorkflowAgent 只做 plan validation + 委托同一 kernel”。
  8. 统一成功判定：定义“成功=workflow_complete 终态事件且 RunStatus=COMPLETED”，失败同理；保证 UI 点击 Run 的最终状态与 Run.status、终态事件一致。

- Phase 4：workflow 执行强制使用 LangGraph（不是仅 Run 用例）
  9. 落地 workflow LangGraph executor adapter（移除 NotImplemented），并作为 workflow kernel 的执行引擎（可保留紧急 feature flag 回滚，但默认启用）。

- Phase 5：Tool/Node 统一与修改链路校验一致（拖拽 + 对话）
  10. 统一能力引用：规定 Tool 节点必须持久化 `tool_id`/`capability_id`（允许兼容字段但落库归一），对话修改必须产出该字段而非自由文本。
  11. 落库前统一校验：拖拽保存与对话修改都走同一 `WorkflowSaveValidator`（missing_executor/missing_tool_id/tool_not_found/tool_deprecated/cycle_detected fail-closed）。

- Phase 6：Coordinator监督 + 严格ReAct（可纠偏、可审计）
  12. 在 Application policy chain 中补齐 Coordinator 强制点：对话 turn、workflow 修改、workflow 执行、工具引用决策均必须产生可拦截的决策事件；缺失依赖时 fail-closed。
  13. 严格 ReAct：ConversationAgent 的 Action 必须触发真实 tool/node 执行并写入 Observation（RunEvent 或等价审计记录），禁止“只 emit tool_call”。
  14. WorkflowAgent plan validation：对 ConversationAgent 的计划输出做可达成性校验（引用工具存在、节点可执行、资源约束满足），不通过则要求 replanning。

- Phase 7：DDD 边界治理与自动化守门
  15. 基于 `.import-linter.toml` 收敛跨层依赖：修复关键越界路径（优先入口链路相关），并在 CI 中启用阻断新增越界。

- Phase 8：验收与回归（以不变式为中心）
  16. 新增/补齐自动化测试：覆盖 run 创建幂等、execute/stream gate、RunEvent 落库、回放顺序、Coordinator reject、ReAct 闭环、LangGraph workflow 执行。
  17. 形成最终 DoD：`Report.md` 中写明每条不变式对应的 API/事件/状态/测试用例，并提供“如何手工验收”的步骤。

✅ 详细验收标准（尽可能全面）

A. Report.md（证据一致性）
- A1：`Report.md` 的每个“当前验收”结论都能被代码或测试直接佐证；禁止出现已修复但仍标为缺失的条目。
- A2：每条不变式至少包含：入口/契约/关键实现位置/测试用例/失败时的错误码与响应结构。

B. Run方案1（事实源与一致性）
- B1（创建）：`POST /api/projects/{project_id}/workflows/{workflow_id}/runs` 返回 `id/status/created_at`，初始 `status=CREATED`。
- B2（幂等）：带 `Idempotency-Key` 重复请求返回同一 `run_id`；不同 key 返回不同 `run_id`；无 key 时不保证幂等但不得破坏一致性。
- B3（执行门禁）：`/execute/stream` 缺 `run_id` 必须 400；run 不存在/归属不匹配/状态不可执行必须 409 且错误结构化。
- B4（状态机）：执行开始后 `CREATED -> RUNNING`；终态事件后 `RUNNING -> COMPLETED/FAILED` 且设置 `finished_at`；CAS 不允许 COMPLETED 回退。
- B5（事件落库）：至少保证 `workflow_start` 与终态事件持久化；若采用异步录制，需保证 node_* 事件最终可回放且顺序稳定。
- B6（点击Run一致）：UI “成功/失败” 判定与 `Run.status`、终态事件一致；刷新页面后仍可通过回放恢复同一结论。

C. 回放（Replay）
- C1：提供 `GET /api/runs/{run_id}/events`（或等价）返回事件序列（含 event_type/payload/created_at/序列字段）。
- C2：顺序稳定：同一 run 的回放顺序与执行期间发送顺序一致（允许最终一致，但不得乱序/丢终态）。
- C3：前端 `useRunReplay` 真正消费回放接口并把事件投递到现有渲染逻辑；支持停止/重放。

D. 执行链路唯一化（=WorkflowAgent）
- D1：REST 执行、WorkflowAgent 执行均走同一 kernel/engine；对外事件类型集合与字段一致，不允许两套语义。
- D2：任何“执行成功”都必须由同一终态事件与同一 RunStatus 事实源决定。

E. LangGraph（workflow 必须用）
- E1：workflow 执行路径由 LangGraph 驱动（adapter 可运行，不允许 NotImplemented）。
- E2：LangGraph 执行产生的事件语义与 D1 完全一致；executor_id 可区分版本但字段不变。
- E3：存在紧急回滚开关（feature flag）且回滚不改变外部契约（仅更换内部引擎）。

F. Tool/Node 统一（修改时可识别）
- F1：Tool 节点落库必须包含稳定标识（tool_id/capability_id）；对话修改必须输出该字段；工具重命名不影响引用。
- F2：拖拽保存与对话修改落库前使用同一校验器；错误返回结构化并可在 UI 呈现。

G. Coordinator（核心监督、fail-closed）
- G1：对话入口、workflow 修改入口、workflow 执行入口均触发可拦截决策事件；被拒绝时返回 403 且含可审计 reason。
- G2：Supervisor 能检测并阻断 ConversationAgent 偏航（例如无关工具调用、越权数据访问）。

H. 严格 ReAct（闭环与审计）
- H1：每次 Action 都有对应 Observation（真实执行结果/错误），并可被持久化（RunEvent 或等价）用于审计与复现。
- H2：禁止“只 emit tool_call 不执行”的伪 ReAct；测试用例能证明 tool_result 被记录。

I. DDD 分层不越界
- I1：通过 import-linter/静态检查阻断新增越界；关键链路（对话/执行/修改）不允许跨层直接依赖。

⚠️ 风险与阻塞
- Report 与代码漂移会导致决策错误：必须 Phase 1 先校准证据。
- LangGraph 引入会影响事件顺序/异常语义：需用 golden tests 锁定契约。
- 工具执行依赖外部服务：测试需 mock，避免网络/密钥成为阻塞。

📎 参考（优先复核）
- `Report.md:1`
- `src/interfaces/api/routes/workflows.py:352`
- `src/interfaces/api/routes/runs.py:153`
- `src/application/use_cases/append_run_event.py:53`
- `src/application/services/workflow_execution_orchestrator.py:31`
- `web/src/hooks/useRunReplay.ts:1`