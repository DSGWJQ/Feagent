---
mode: plan
cwd: D:\My_Project\agent_data
task: run方案1（workflow runs落库）+其余前提不变：协调者为核心、workflow执行=WorkflowAgent、tool/node统一、workflow使用LangGraph、严格ReAct、DDD不越界；并补充/更新Report.md验收标准
complexity: complex
planning_method: builtin
created_at: 2026-01-03T21:29:29.6613081+08:00
---

# Plan: Workflow 核心业务闭环落地（Run 方案1 + 其余一致）

🎯 任务概述
本计划将系统收敛到你要求的 10 条不变式：唯一 chat-create 创建、拖拽/对话修改、唯一执行链路且等同 WorkflowAgent、tool/node 统一并可识别、Coordinator 作为核心入口监督、严格 ReAct、Run 点击与执行成功同一事实源（Run 方案1：落库+回放）、workflow 执行使用 LangGraph、WorkflowAgent 验证计划可达成、DDD 分层不越界。

本计划以当前代码中已存在的基础设施为起点（Run/RunEvent 模型、AppendRunEventUseCase、WorkflowSaveValidator、CoordinatorPolicyChain、WorkflowExecutionKernelPort），补齐缺失入口并统一各条链路，最终通过验收测试与文档（Report.md）锁定不变式。

---

📋 执行计划（按 Phase 交付，可追踪/可回滚）

1) Phase 1：冻结契约与“唯一真源”声明（Architecture Gate）
   - 交付物：ADR（架构决策记录）1 份 + 统一契约文档更新（Report.md/README/docs）。
   - 内容：
     - 唯一创建入口：POST /api/workflows/chat-create/stream。
     - 唯一执行入口：POST /api/workflows/{workflow_id}/execute/stream（要求 run_id）。
     - Run 方案1：必须先创建 Run（POST /api/projects/{project_id}/workflows/{workflow_id}/runs），再执行。
     - 事件语义：node_start/node_complete/node_error/workflow_complete/workflow_error；SSE 必含 run_id。
     - Coordinator 强制点：所有“创建/修改/执行/工具调用”必须 fail-closed 进入监督链。
     - tool/node 统一字段：Tool 节点必须包含 config.tool_id（或 toolId 兼容），并可追溯到 ToolRepository。

2) Phase 2：Run 方案1落地（补齐创建 Run 的 API + 幂等与状态机）
   - 后端：新增/补齐 POST /api/projects/{project_id}/workflows/{workflow_id}/runs。
     - 使用 Run.create_with_idempotency(project_id, workflow_id, idempotency_key)（Header: Idempotency-Key）实现幂等创建。
     - 返回 Run DTO（id/status/created_at），并保证写操作只 flush，commit 在路由/用例。
   - 后端：完善 Run 状态流转：
     - 执行开始：CREATED → RUNNING（CAS：update_status_if_current），失败则返回 409（run 已被并发启动）。
     - 终态：RUNNING → COMPLETED/FAILED，必须落库 finished_at。
   - 后端：补齐 runs API：
     - GET /api/projects/{project_id}/workflows/{workflow_id}/runs 已有（确认分页/排序契约）。
     - 新增 GET /api/runs/{run_id}/events（若已有则对齐）用于回放（cursor 分页）。
   - 前端：统一 Run 入口：
     - Run 按钮：先创建 Run（带幂等键，可复用“本次会话 run_id”），再调用 execute/stream 传 run_id。
     - UI：Run ID 展示必须来自后端创建返回，禁止本地伪造。

3) Phase 3：执行链路唯一化（/execute/stream 为权威，/execute 去分叉）
   - 后端：
     - 明确 /execute/stream 为唯一权威执行入口：
       - 强制 run_id 必填；验证 run 归属 workflow；验证 run 状态可执行。
       - 执行前落库 workflow_start RunEvent，并原子更新 run 状态为 RUNNING。
       - 执行中：所有 SSE 事件必须 append 为 RunEvent（至少 node_* + workflow_*），并在 payload 中包含 executor_id。
       - 执行后：终态事件必须与 Run.status 对齐（成功=COMPLETED，失败=FAILED）。
     - /execute（非流式）处理策略（推荐）：标记 deprecated 并内部调用 kernel 收集事件返回（保持单一真源）。

4) Phase 4：WorkflowExecutionKernelPort 成为单一执行面（对齐 WorkflowAgent）
   - 目标：满足“执行链路与 WorkflowAgent 一样”。
   - 动作：
     - 将 ApiContainer.workflow_execution_kernel 的实现替换为真正的“Kernel 实现”，并同时注入到 WorkflowAgent 的执行路径（WorkflowAgent 只能调用 kernel）。
     - WorkflowAgent 内部执行逻辑必须收敛：禁止保留另一套 DAG 执行；其职责改为“验证计划 + 调用 kernel + 发布执行事件/回馈对话”。

5) Phase 5：workflow 使用 LangGraph（替换 workflow kernel 的执行引擎）
   - 目标：满足“workflow 执行必须使用 LangGraph”。
   - 动作：实现 LangGraphWorkflowExecutorAdapter（不再 NotImplemented），并将其作为 kernel 的执行引擎：
     - Graph State：包含 workflow、run_id、node_outputs、current_node、events。
     - Node 执行：通过 NodeExecutorRegistry/ToolExecutor 调度具体节点。
     - 事件：在 LangGraph 节点边界产生 node_start/node_complete/node_error；终态产生 workflow_complete/workflow_error。
   - 兼容：保留 executor_id（如 workflow_langgraph_v1）用于观测与回滚。

6) Phase 6：tool/node 统一与“修改时可识别工具”（落库前强校验全面覆盖）
   - 目标：拖拽与对话两条修改链路都在保存前通过同一套 WorkflowSaveValidator，且 tool 节点可执行。
   - 动作：
     - 在拖拽更新用例与对话更新用例落库前统一调用 WorkflowSaveValidator（fail-closed）。
     - 补齐 NodeExecutorRegistry 的 tool executor：
       - tool 节点执行时读取 config.tool_id，从 ToolRepository 获取 Tool 实体并执行其 implementation；并写入 node output。
       - 拒绝 deprecated tool（与 validator 对齐）。
     - 前端 Tool 节点配置：强制选择/填写 tool_id（从 /api/tools 查询），并保持字段名一致（tool_id/toolId）。
     - 对话修改产物：禁止自由输出 tool_name；必须输出 tool_id（或 capability_id），服务端应用修改前校验存在性。

7) Phase 7：Coordinator 为核心入口监督（对话/修改/执行全覆盖，fail-closed）
   - 目标：任何链路都不可绕过 Coordinator。
   - 动作：
     - Conversation 入口：在 ConversationTurnOrchestrator 的 policy chain 中引入 CoordinatorPolicyChain：
       - before_turn：校验 conversation_request（包含 session_id/workflow_id/run_id/goal）。
       - on_emit：对 tool_call/human_interaction/file_operation 做二次监督。
     - Workflow 修改入口：chat-create/chat-stream/drag-save 都必须执行 coordinator enforcement（api_request/workflow_modify/tool_reference）。
     - Workflow 执行入口：execute/stream 已接入 coordinator policy（补齐覆盖面与审计字段）。

8) Phase 8：严格 ReAct（LangGraph 化 + 真实 Observation）
   - 目标：ConversationAgent 的 ReAct 达到“可执行/可审计/可回放”。
   - 动作：
     - ReAct 用 LangGraph StateGraph 表达：Reason→Act→Observe，Action 只能产出结构化 Decision（Pydantic schema）。
     - tool_call 必须执行并产生 ToolResult 写回 Observation；workflow_execute 必须走 kernel 并写回结果。
     - 每一步写入 RunEvent（planning/execution channel 区分），用于回放。

9) Phase 9：DDD 边界修复（消除越界 import，形成结构性强制）
   - 目标：Interface/Application/Domain/Infrastructure 依赖方向正确。
   - 动作：
     - Application 不再 import Infrastructure：用 Ports + DI 装配。
     - Domain 不再 import Application/Infrastructure：IO（文件扫描/网络/LLM SDK）下沉到 Infrastructure adapter。
     - Infrastructure 不再 import Application：把跨层解析/校验逻辑移动到 Domain service 或 Infrastructure 内聚。
     - import-linter 在 CI 中阻断新增越界。

10) Phase 10：更新 Report.md（详细验收标准 + 证据索引）
   - 目标：Report.md 成为“真实系统契约”。
   - 动作：把下方“详细验收标准”逐条写入 Report.md，并附最新文件路径与行号。

---

✅ 详细验收标准（必须尽可能全面，按不变式逐条验收）

A. 创建（唯一 chat-create）
- A1（API 唯一性）：除 POST /api/workflows/chat-create/stream 外，不存在可被产品流量使用的 workflow create 写入口；legacy POST /api/workflows 必须返回 410 或仅 internal flag 可用。
- A2（SSE 契约）：SSE 第 1 条事件内必须包含 metadata.workflow_id；如提供 run_id，必须同时包含并落库为 planning channel 的 RunEvent。
- A3（Coordinator 监督）：chat-create 在任何落库/状态变更前必须执行 coordinator enforcement；被拒绝时返回 403 且产生 DecisionRejectedEvent。

B. 修改（拖拽 + 对话，两链路一致）
- B1（强校验）：拖拽保存与对话修改在落库前都必须调用同一 WorkflowSaveValidator；任何 missing_executor/missing_tool_id/tool_not_found/tool_deprecated/cycle_detected 必须阻止保存并返回结构化错误。
- B2（Tool 可识别）：Tool 节点必须包含 config.tool_id（允许 toolId 兼容）；ToolRepository.exists(tool_id)=true；tool status != deprecated。
- B3（回归一致）：同一组变更无论通过拖拽还是对话，都得到同样的校验结果与错误码。

C. Run 方案1（落库 + 回放 + 一致性）
- C1（创建 Run）：POST /api/projects/{project_id}/workflows/{workflow_id}/runs 成功返回 Run（status=CREATED）；支持 Idempotency-Key 幂等，重复请求返回同一 run_id。
- C2（执行绑定 Run）：POST /api/workflows/{workflow_id}/execute/stream 必须要求 run_id；run 不存在→409；run.workflow_id 不匹配→409；run.status != CREATED→409。
- C3（状态机）：执行开始必须原子更新 run CREATED→RUNNING（CAS）；执行终态必须更新为 COMPLETED/FAILED 并写入 finished_at。
- C4（RunEvent 事件流）：执行前写入 workflow_start；执行中写入 node_*；终态写入 workflow_complete/workflow_error；所有事件 payload 必须包含 workflow_id/run_id/executor_id。
- C5（前端一致）：UI 展示的 run_id 必须来自后端 create run 返回；SSE 每条 event 必须回带同一 run_id；最终 UI 的“成功/失败”与 Run.status 一致。
- C6（回放）：存在可查询的 run events（GET /api/runs/{run_id}/events 或等价）；回放事件顺序与执行期间一致（序列号单调）。

D. 执行（唯一链路=WorkflowAgent=Kernel）
- D1（唯一执行面）：任何 workflow 执行（REST、scheduler、agent）必须调用同一 WorkflowExecutionKernelPort 实现。
- D2（WorkflowAgent 一致性）：WorkflowAgent 不允许存在独立 DAG 执行逻辑；其执行必须委托 kernel；对外事件语义与 REST 完全一致。
- D3（事件语义）：严格只使用 node_start/node_complete/node_error/workflow_complete/workflow_error；字段命名一致，前端 SSE 解析无需特殊分支。

E. LangGraph（workflow 必须用）
- E1（不再占位）：LangGraphWorkflowExecutorAdapter 不允许抛 NotImplemented；必须可运行。
- E2（事件一致）：LangGraph 执行产生的事件与 D3 完全一致；executor_id 为固定值（例如 workflow_langgraph_v1）。
- E3（回滚）：存在紧急回滚开关（feature flag），关闭后仍可运行（仅用于紧急），并有明确观测指标。

F. Coordinator（核心监督，fail-closed）
- F1（对话入口）：/api/conversation/stream 的 before_turn 必须经过 coordinator enforcement；缺失 coordinator/event_bus 必须 fail-closed 拒绝。
- F2（修改入口）：chat-create/chat-stream/drag-save 必须经过 coordinator enforcement（至少 api_request/workflow_modify/tool_reference）。
- F3（执行入口）：execute/stream 在任何 run 状态变更与事件落库前必须经过 coordinator enforcement。
- F4（可观测）：DecisionValidated/DecisionRejectedEvent 可在 event_log 或持久化事件中查询。

G. 严格 ReAct（可执行 + 可审计）
- G1（闭环）：每次 Action 都必须产生对应 Observation（tool_result/node_result/error）。
- G2（结构化）：Action/Decision 必须通过 Pydantic schema 校验（错误必须结构化返回）。
- G3（偏航防护）：Coordinator 可拒绝与目标无关 action；ConversationAgent 必须据此 replan 或请求澄清。

H. DDD 不越界（结构性强制）
- H1（依赖规则）：Interface 不 import Domain agents；Application 不 import Interface；Domain 不 import Interface/Infrastructure；Infrastructure 不 import Application。
- H2（CI 门槛）：import-linter 在 CI 中阻断新增越界；新增越界视为 P0。

---

⚠️ 风险与注意事项
- 改动面大：涉及前后端协议、run状态机、执行内核、LangGraph、工具执行与 DDD 分层，必须按 Phase 逐步交付并保持可回滚开关。
- 外部依赖：LLM/工具执行可能受网络/密钥限制，测试必须 mock；但 Run/事件/校验/状态机必须可在无网络下验证。
- 并发与幂等：Run 的创建与状态变更必须使用幂等键与 CAS 更新，避免重复执行与竞态。

📎 参考（关键文件）
- Report 基线：`Report.md:1`
- execute/stream：`src/interfaces/api/routes/workflows.py:340`
- Run：`src/domain/entities/run.py:1`
- WorkflowSaveValidator：`src/domain/services/workflow_save_validator.py:54`
- CoordinatorPolicyChain：`src/application/services/coordinator_policy_chain.py:33`
- WorkflowExecutionKernelPort：`src/domain/ports/workflow_execution_kernel.py:1`
- LangGraph workflow adapter：`src/infrastructure/lc_adapters/workflow/langgraph_workflow_executor_adapter.py:1`
- 统一架构计划：`docs/architecture/WORKFLOW_UNIFIED_ARCHITECTURE_PLAN.md:1`