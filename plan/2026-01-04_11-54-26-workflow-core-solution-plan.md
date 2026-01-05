---
mode: plan
cwd: D:\My_Project\agent_data
task: 基于Report.md与解决方案：收敛工作流核心业务到10条不变式（创建唯一、修改双链路、执行唯一=WorkflowAgent、tool/node统一可识别、Coordinator监督、严格ReAct、Run一致+回放、workflow强制LangGraph、计划互验、DDD不越界）
complexity: complex
planning_method: builtin
created_at: 2026-01-04T11:54:26.4052691+08:00
---

# Plan: Workflow 核心业务收敛（基于 Report.md）

🎯 任务概述
本计划把当前实现收敛到你定义的 10 条系统不变式，并以“CoordinatorAgent 为核心监督者”作为总架构中心。
核心策略：建立唯一真源（Run+事件+状态机+成功判定+执行引擎），让 REST 执行与 WorkflowAgent 执行完全同源；并补齐 tool/node 统一能力、严格 ReAct（真实工具执行+可审计）以及 DDD 边界强制。

📌 关键前置决策（必须在 Phase 1 结束前落定，否则后续会左右摇摆）
1) 是否保留 `POST /api/workflows/import` 与 `POST /api/workflows/generate-from-form`（已选方案A）：
   - 保留为“内部工具入口”，对产品流量默认不可达（403/410），仅内部权限 + feature flag 可用。
   - 约束（必须结构性强制）：默认 feature flag=OFF；仅内部角色/权限可调用；写审计日志；前端产品路径禁止引用这两个入口。
2) LangGraph 是否“默认强制”执行 workflow（已选方案A）：
   - 默认强制 `enable_langgraph_workflow_executor=true`；legacy engine 仅作为紧急回滚路径。
   - 约束（必须可审计）：回滚开关仅紧急使用且记录启用人/时间/范围；LangGraph/回滚对外事件契约必须同构。
3) tool/node 统一真源（已锁定）：`tool_id` 为唯一引用与审计主键；工具资产真源=`ToolRepository`（DB），节点执行真源=`NodeExecutorRegistry`；Tool 节点由 `ToolNodeExecutor` 执行并对接 ToolEngine/运行时；对话修改必须输出 tool_id（基于允许候选列表），禁止 name-based 引用。

📋 执行计划（Phase 1~8，按里程碑交付）

Phase 1：冻结合同与入口治理（保证不变式1/2/10的“边界合同”）
- 1.1 入口清单核对：列出所有会“创建 workflow”的 API/入口（含 import、generate-from-form、chat-create）。
- 1.2 对非 chat-create 创建入口实施治理（按已选方案A）：默认对产品流量不可达（403/410）；仅内部权限 + feature flag 可达；必须写审计日志；前端产品路径禁止引用。
- 1.3 明确并锁定对外契约：
  - 创建：只允许 chat-create（SSE 首事件包含 workflow_id）。
  - 修改：拖拽 PATCH 与 chat-stream 均必须 fail-closed 校验。
  - 执行：execute/stream 必须先 create run，再携带 run_id 执行。
- 1.4 DDD 守门：确认 `.import-linter.toml` 在 CI 中启用（至少阻断新增越界），并约定“监督/策略链只在 Application”。

Phase 2：Run 事实源一致性闭环（保证不变式7：点击Run一致、可回放、终态可靠）
- 2.1 Run 创建与幂等：确认/补齐 `POST /api/projects/{project_id}/workflows/{workflow_id}/runs` 幂等语义（Idempotency-Key）。
- 2.2 执行门禁：execute/stream 强制 run_id，校验 run 存在/归属 workflow/status=CREATED，失败返回结构化 400/409。
- 2.3 终态唯一：消除终态事件重复落库风险（路由同步落库 vs 异步录制器落库二选一，保证回放不重复/不乱序）。
- 2.4 断连/取消收敛：定义断连/超时/取消的终态策略（FAILED/CANCELLED）并确保不会长期 RUNNING 悬挂。
- 2.5 回放闭环：确保 `GET /api/runs/{run_id}/events` 的稳定顺序与分页契约；前端 useRunReplay 必须消费回放 API 并可 Stop/Replay。

Phase 3：执行链路唯一化且与 WorkflowAgent 同源（保证不变式3）
- 3.1 建立“权威执行编排入口”（Application 层）：把 run 门禁、状态机、事件落库、成功判定抽出，形成单实现（REST 与 WorkflowAgent 共用）。
- 3.2 REST execute/stream 只做：参数/DTO/错误映射 + 调用权威入口，不再在路由层散落持久化与判定逻辑。
- 3.3 WorkflowAgent execute_workflow 只做：plan validation + 调用同一权威入口（不得绕过 run 门禁/落库/状态机）。

Phase 4：workflow 默认 LangGraph 执行（保证不变式8）
- 4.1 将 LangGraphWorkflowExecutorAdapter 作为默认执行引擎（已选方案A：默认强制 enable_langgraph_workflow_executor=true），legacy engine 仅保留为紧急回滚路径。
- 4.2 事件契约对齐：LangGraph 产生的 node_* / workflow_* 事件字段与现有 SSE/回放完全同构（run_id/workflow_id/executor_id 等）。
- 4.3 灰度/回滚策略：提供可观测开关与回滚路径（仅紧急），并确保回滚不改变外部契约。

Phase 5：Tool/Node 统一可执行（保证不变式4，且与保存校验对齐）
- 5.1 落地 ToolNodeExecutor：在 NodeExecutorRegistry 注册 tool executor（当前缺口），并以 tool_id 作为唯一引用。
- 5.2 对话修改“工具识别”机制：在 chat 修改链路中引入“工具候选集合/解析约束”，确保 LLM 输出稳定 tool_id（禁止 name-based 漂移）。
- 5.3 统一能力真源（已锁定）：tool_id 真源=ToolRepository（DB）；执行真源=ToolNodeExecutor/ToolEngine；工具废弃/删除必须触发 fail-closed（保存/执行均拒绝）。

Phase 6：Coordinator 核心监督闭环（保证不变式5，且不可绕过）
- 6.1 监督点下沉 Application policy chain：对话 turn、workflow 执行、workflow 修改都必须生成可审计的 DecisionValidated/Rejected 事件。
- 6.2 tool_call 监督补齐：ReAct 的 tool_call 必须在“执行前”进入可拦截决策（fail-closed），否则视为漏洞。
- 6.3 监督一致性：禁止 Interface 层临时 new CoordinatorPolicyChain 形成重复语义；统一在 Application 层实现。

Phase 7：严格 ReAct + 计划互验（保证不变式6/9）
- 7.1 ReAct 真实执行：为 ConversationAgent 注入 tool_call_executor，使 Observation 来自真实工具执行（而非仅内置离线工具）。
- 7.2 Observation 可审计：将 tool_call/tool_result 与 run 关联（RunEvent channel=planning/execution 之一），支持回放复现。
- 7.3 WorkflowAgent 计划可达成性验证：对 ConversationAgent 的计划输出进行验证（工具存在、executor 存在、资源约束、run 门禁），失败则要求 replanning 并记录原因。

Phase 8：DDD 合规与验收测试集（保证不变式10 + 持续验证）
- 8.1 分层清理：按 import-linter 合同修复关键链路越界（优先入口/执行/监督相关）。
- 8.2 自动化测试补齐（不依赖外网）：
  - Run：创建幂等、execute/stream gate、状态机、终态唯一、断连收敛、回放顺序。
  - 执行同源：REST 与 WorkflowAgent 事件/成功判定一致。
  - LangGraph：默认路径覆盖正常/异常；回滚开关不改变外部契约。
  - Tool/Node：tool executor 可执行；chat 修改产出 tool_id；保存校验一致。
  - Coordinator：tool_call 可拦截；拒绝后无副作用（不落库、不变更状态）。

✅ 详细验收标准（对等覆盖10条不变式，尽可能全面）

A. 创建唯一（不变式1）
- A1：除 `POST /api/workflows/chat-create/stream` 外，不存在对产品流量可达的创建入口；import/generate-from-form 若保留，必须默认 403/410 且需要内部权限/开关。
- A2：chat-create 首个 SSE 事件（≤1条）必须包含 `workflow_id`（metadata），且创建失败必须清理残留 workflow。

B. 修改双链路一致（不变式2）
- B1：拖拽 PATCH 与 chat 修改（chat-stream/chat）落库前必须调用同一 `WorkflowSaveValidator`，fail-closed。
- B2：对同一非法输入（缺 node、成环、缺 tool_id、缺 executor 等）两链路返回同一错误 code/path 集合。

C. 执行唯一且=WorkflowAgent（不变式3）
- C1：REST execute/stream 与 WorkflowAgent 执行必须调用同一“权威执行编排入口”，共享同一 run 门禁、事件落库、状态机、成功判定。
- C2：同一 workflow_id + run_id + input_data：两入口产生的事件序列类型集合一致（node_* 与 workflow_*），终态一致，Run.status 一致。

D. Tool/Node 统一且可识别（不变式4）
- D1：Tool 节点落库必须包含 `config.tool_id`（允许 toolId 输入但持久化归一化）。
- D2：chat 修改生成的工具引用必须是 tool_id（禁止 name-based）；工具重命名不影响引用。
- D3：tool executor 已注册且可执行：包含 tool 节点的 workflow 在 LangGraph 执行路径可跑通。

E. Coordinator 核心监督（不变式5）
- E1：对话入口、修改入口、执行入口都必须有可审计的 DecisionValidated/DecisionRejected 事件。
- E2：tool_call 必须在执行前可被 Coordinator 拦截（fail-closed）；被拒绝时返回结构化 403 且无副作用。

F. 严格 ReAct（不变式6）
- F1：每个 Action 都必须产出对应 Observation（tool_result 或 error），且 Observation 来自真实执行。
- F2：Observation 必须可回放复现（与 run 关联，RunEvent 或等价审计记录）。

G. Run 点击一致 + 回放（不变式7）
- G1：点击 Run：必须先 create run，再 execute/stream；UI 展示 run_id 必须来自后端响应。
- G2：状态机：CREATED→RUNNING→COMPLETED/FAILED（或 CANCELLED），终态唯一且 finished_at 写入。
- G3：回放：`GET /api/runs/{run_id}/events` 返回稳定顺序（cursor 分页），事件不重复、不乱序；刷新后 UI 可复原同一结论。

H. workflow 必须 LangGraph（不变式8）
- H1：默认配置下 workflow 执行必须走 LangGraph adapter；若存在回滚开关，仅允许紧急使用且有日志/审计。
- H2：LangGraph 与回滚路径对外事件契约完全一致。

I. 计划互验（不变式9）
- I1：WorkflowAgent 在执行前必须验证对话计划可达成（tool_id 存在、executor 存在、run 门禁、资源约束）。
- I2：验证失败必须触发 replanning 并可审计（记录拒绝原因/错误码）。

J. DDD 不越界（不变式10）
- J1：import-linter 在 CI 中阻断新增越界；关键链路（对话/修改/执行/监督）不出现 Interface→Domain Agents 的直接依赖。
- J2：监督/策略链不在 Interface 层重复实现，统一在 Application policy chain。

⚠️ 风险与注意事项
- 变更面大：需按 Phase 灰度交付，任何“语义不一致”都必须通过测试锁定。
- 外部依赖：LLM/外部工具不稳定，测试必须 mock（无网也可跑），但 run/事件/状态机必须强一致。
- 并发/断连：Run 状态机与事件落库必须处理并发启动、断连收敛、终态唯一性。

📎 参考（关键定位）
- `Report.md:1`
- 创建入口：`src/interfaces/api/routes/workflows.py:614`、`src/interfaces/api/routes/workflows.py:1089`、`src/interfaces/api/routes/workflows.py:1122`
- 执行入口：`src/interfaces/api/routes/workflows.py:359`
- Run create/replay：`src/interfaces/api/routes/runs.py:153`、`src/interfaces/api/routes/runs.py:93`
- Run 状态机：`src/application/use_cases/append_run_event.py:53`
- 异步事件录制：`src/application/services/async_run_event_recorder.py:256`
- LangGraph workflow executor：`src/infrastructure/lc_adapters/workflow/langgraph_workflow_executor.py:1`
- tool 校验与归一化：`src/domain/services/workflow_save_validator.py:44`
- tool executor 缺口：`src/infrastructure/executors/__init__.py:103`
- ReAct：`src/domain/agents/conversation_agent_react_core.py:435`
- Coordinator middleware：`src/domain/agents/coordinator_agent.py:2141`
