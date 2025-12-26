# Deep Research 修复→收敛→演进规划（带完成标准）

> 版本：v5 (2025-12-26)
> 基于 v4 审查后修订：Step 7 完成（节点体系收敛 + alias → canonical 映射 + 验证绕过修复）
> 目标：以 **Deep Research** 为终局目标，在不"脑补现状"的前提下，按 `Interface → Application → Domain` 的基本流程修复当前链路问题，并逐步收敛/删除不需要的部分。

---

## 0) 以仓库事实为准：当前系统"真实存在"的主链路

### 0.1 后端入口（FastAPI 已挂载）

入口文件：`src/interfaces/api/main.py`

- Project
  - `POST /api/projects`（`src/interfaces/api/routes/projects.py`）
  - `PATCH /api/projects/{project_id}`（同上，包含 `rules_text`）
- Workflow
  - `POST /api/workflows`（`src/interfaces/api/routes/workflows.py`）
  - `PATCH /api/workflows/{workflow_id}`（拖拽更新，仍在 `workflows.py`）
  - `POST /api/workflows/{workflow_id}/import`（导入，`workflows.py`）
  - `POST /api/workflows/{workflow_id}/execute/stream`（SSE 执行，`workflows.py`）
- Workflow Chat（对话改图）
  - `POST /api/workflows/{workflow_id}/chat-stream`（SSE 规划流，`src/interfaces/api/routes/chat_workflows.py`）
- Run（追踪/回放）
  - `POST /api/projects/{project_id}/workflows/{workflow_id}/runs`
  - `GET /api/runs/{run_id}/events/stream?after=...`
  - 文档：`.claude/docs/step10-run-event-wiring.md`
- Scheduler（定时）
  - `POST /api/workflows/{workflow_id}/schedule`
  - `GET /api/scheduled-workflows`
  - `DELETE /api/scheduled-workflows/{scheduled_workflow_id}`
  - 文件：`src/interfaces/api/routes/scheduled_workflows.py`
- Conversation Stream（单独的对话 SSE 端点，**Deep Research 目标下将删除**）
  - `POST /api/conversation/stream`（`src/interfaces/api/routes/conversation_stream.py`，待移除）

### 0.2 后端"存在但当前未挂载/可能是遗留"的入口

这些文件存在，但在 `src/interfaces/api/main.py` 当前没有 `include_router(...)`：

- WebSocket：`src/interfaces/api/routes/agent_websocket.py`（已删除）
- 旧 Chat Workflows：`src/interfaces/api/routes/chat_workflows_complete.py`（文件内编码异常，且未挂载）

### 0.3 当前执行引擎现状（代码事实）

- `ExecuteWorkflowInput.mode` 默认 `"langgraph"`：`src/application/use_cases/execute_workflow.py:44`
- 执行统一入口：`WorkflowExecutionFacade`（Domain/Agent/LangGraph 三模式）：`src/application/services/workflow_execution_facade.py`
- LangGraph Runtime：`src/infrastructure/lc_adapters/workflow/langgraph_workflow_executor.py`
- RunEvent 落库：`RunEventRecorder` + `AppendRunEventUseCase`：`src/application/services/run_event_recorder.py`
- **[Step 6 已实现] Domain Port 定义**：`WorkflowExecutorPort` 在 `src/domain/ports/workflow_executor_port.py`
  - `LangGraphWorkflowExecutorAdapter` 实现该 Port：`src/infrastructure/lc_adapters/workflow/langgraph_workflow_executor_adapter.py`
  - `WorkflowExecutionFacade` 通过注入使用，不直接依赖 LangGraph

### 0.4 当前对话改图（chat-stream）现状（Step 5 完成后）

`/api/workflows/{workflow_id}/chat-stream` 的事件链路已重构：

- UseCase streaming 产出用例事件（Application Events）：
  - `WorkflowPlanningStarted`、`ReActStepCompleted`、`WorkflowPatchGenerated`、`WorkflowPlanningCompleted`、`WorkflowPlanningFailed`
  - `src/application/events/workflow_planning_events.py`
- `PlanningEventMapper` 将用例事件转换为 `PlanningEvent(type=thinking/tool_call/patch/final/error, channel=planning)`：
  - `src/application/services/planning_event_mapper.py`
- 路由层 `chat_workflows.py` 只做透传 + SSE 编码 + RunEvent 录制：
  - `src/interfaces/api/routes/chat_workflows.py`（156 行）
- **[已存在] PlanningEvent 定义在 Application 层**：`src/application/services/planning_event.py`

### 0.5 前端新增组件（需纳入收敛考虑）

以下 hooks 是新增的，需在 Step 9 前端收敛时评估去留：

- `web/src/features/workflows/hooks/useConflictResolution.ts`（冲突解决，WS 删除后可能需调整）
- `web/src/features/workflows/hooks/useWorkflowHistory.ts`（历史记录）
- `web/src/features/workflows/hooks/useKeyboardShortcuts.ts`（快捷键）

### 0.6 节点体系现状（用于 Step 7 工作量估算）

- **NodeType 枚举**：`src/domain/value_objects/node_type.py` 包含 **35 种类型**
- **YAML 节点定义**：`definitions/nodes/*.yaml` 包含 **20 个文件**
- **GenericNode 体系**：`src/domain/services/generic_node.py`
- Deep Research 预估需要 6-10 种 → **需删除/合并约 25 种**（工作量较大）

### 0.7 执行架构现状（Step 6 完成后）

```
Interface 层（依赖注入点）
  └─ workflows.py / workflow_executor_adapter.py
       ├─ 创建 LangGraphWorkflowExecutorAdapter (Infrastructure)
       └─ 注入 WorkflowExecutionFacade (Application)

Application 层（编排）
  └─ WorkflowExecutionFacade
       ├─ 依赖 WorkflowExecutorPort (Domain 抽象)
       ├─ DOMAIN 模式 → WorkflowExecutor (Domain)
       ├─ AGENT 模式 → WorkflowAgent (Domain, 实验性)
       └─ LANGGRAPH 模式 → 注入的 langgraph_executor (Port)

Infrastructure 层（实现）
  └─ LangGraphWorkflowExecutorAdapter
       ├─ 实现 WorkflowExecutorPort
       ├─ 封装 LangGraph 执行逻辑
       └─ 转换 LangGraphExecutionEvent → SSE dict
```

**关键隔离点**：
- Application 层不直接 import LangGraph（仅 `TYPE_CHECKING` 下的类型提示）
- `WorkflowExecutorPort` 是 Domain 层抽象，Infrastructure 提供具体实现
- 依赖注入在 Interface 层完成，Application 层通过构造函数接收

---

## 1) 终局目标（Deep Research 的最小闭环）

### 1.1 目标能力

给定一个 Project（包含 `rules_text`）、一个 Workflow（可视化图）、一次 Run（可回放事件），系统能够：

1. 用对话生成/修改 Deep Research 工作流（生成 patch，支持人工审核）
2. 以 LangGraph 并行执行工作流（尤其是"并行拆解/并行分析/汇总"）
3. 全过程只用 SSE（规划 + 执行 + 回放）
4. Run 事件可落库、可断点续传、可回放
5. 失败后可复用：同类研究问题复用 workflow 模板/图结构

### 1.2 约束（必须遵守）

- **分层职责不变**：
  - Domain 返回实体
  - Application 编排业务流程 + 事件转换
  - Interface 做 DTO/异常映射 + SSE 编码（不做业务逻辑）
- **事务边界唯一**：UseCase/应用服务控制 commit/rollback；路由层只做 DTO/异常映射
- **"执行链路唯一"**：对外 API 执行与对话内部触发执行都必须走同一套应用层用例（不能有第二条私链路）
- **SSE-only**：不新增 WebSocket；遗留 WS 视为删除对象

---

## 2) 总体策略：先修复"闭环正确性"，再删减"非目标功能"

开发顺序（适配未来几天的节奏）：

1. 先把深度研究最小闭环需要的链路修复到"可验证、可回放、可复用"
2. 再删除：创建 agent 多模式、表单创建工作流、WS 协作、重复入口等非目标能力
3. 全程 TDD：每一步都给出"完成标准 + 要跑的测试 + 允许暂时跳过的测试"

---

## 3) 分步规划（每一步都有完成标准）

> 说明：每一步都按 "先测后改（TDD）" 写，且每一步都尽量只改变一个方向（便于回滚）。

### Step 1 — 建立"可跑的最小测试门禁"（为后续删减护航）

**目标**：把测试分成三类：必须绿灯 / 可选绿灯 / 暂时隔离，保证我们"敢改、改得动"。

**工作清单**
- [x] 定义一个"后端最小门禁集合"（只覆盖 Deep Research 主链路）
- [x] 定义一个"前端最小门禁集合"（先覆盖 workflows 的 hooks/utils；UI/E2E 后续逐步纳入）
- [ ] 标注需要隔离的测试（不是删，先隔离：标记/移动/单独 job）

**完成标准（DoD）**
- 后端最小门禁执行命令明确，并覆盖：
  - `/api/workflows/{id}/execute/stream`（含 `run_id` 可选）
  - `/api/workflows/{id}/chat-stream`（planning 契约 + `run_id` 可选）
  - `/api/runs/{run_id}/events/stream`（回放）
- 前端最小门禁执行命令明确，并至少覆盖：
  - workflow editor 能加载/保存（REST）
  - 能发起执行 SSE 并渲染事件（无需真实模型）
- 被隔离的测试列表明确，且每个都写出"为什么与 Deep Research 当前闭环无关/或现状不一致"

**最小门禁命令（已在本机跑通）**
- 后端（50 passed）
  - `pytest -q tests/unit/application/services/test_run_event_recorder.py tests/integration/api/runs/test_run_events_from_execution.py tests/integration/api/runs/test_planning_events_from_chat_stream.py tests/integration/api/workflows/test_chat_stream_contract.py tests/integration/api/workflows/test_execute_stream_contract.py tests/integration/api/test_websocket_removed.py`
- 前端（58 passed）
  - `cd web && pnpm vitest run src/features/workflows/hooks src/features/workflows/utils`

**允许暂时跳过（候选）**
- [ ] `tests/integration/test_agent_websocket_e2e.py`（当前 WS 路由未挂载，且目标是 SSE-only）
- [ ] `tests/integration/api/test_conversation_stream_api.py`（目标删除 `/api/conversation/stream`，避免为将删除的端点维持测试）
- [ ] `web/src/features/agents/components/__tests__/CreateAgentForm.test.tsx`（Deep Research 目标将移除 agents；当前也存在未 mock 的 UI 副作用导致失败）
- [ ] `web/src/features/agents/pages/__tests__/AgentDetailPage.test.tsx`（同上）
- [ ] `web/src/features/agents/pages/__tests__/AgentListTest.test.tsx`（同上）
- [ ] `web/src/features/agents/pages/__tests__/CreateAgentPage.test.tsx`（同上）
- [ ] `web/src/shared/hooks/__tests__/useAgents.test.tsx`（依赖 agents 体系；后续前端收敛时一并处理）
- [ ] `web/src/features/workflows/components/nodes/__tests__/DatabaseNode.test.tsx`（UI class 断言与当前样式不一致）
- [ ] `web/src/features/workflows/components/nodes/__tests__/FileNode.test.tsx`（同上）
- [ ] `web/src/features/workflows/components/nodes/__tests__/LoopNode.test.tsx`（同上）
- [ ] `web/src/features/workflows/components/nodes/__tests__/NotificationNode.test.tsx`（同上）

---

### Step 1.5 — 删除/下线 WebSocket 相关残留（SSE-only 真收敛）✅ 已完成

> **调整说明**：原 Step 5 提前到 Step 1.5，理由：WS 删除是低风险操作，提前完成可减少后续步骤的干扰因素。
> **完成日期**：2025-12-26

**目标**：仓库中不再保留"可执行的 WS 路由/前端调用/测试依赖"，避免后续维护分叉。

**工作清单**
- [x] 明确 WS 当前是否"仅未挂载"还是"仍被前端调用"
  - 后端：`src/interfaces/api/routes/agent_websocket.py` 已删除
  - 前端：无 `new WebSocket(` / `/ws/` 调用
- [x] 决策：Deep Research 阶段直接删除（推荐）→ 已执行
- [x] 删除后修复/替换相关测试

**完成标准（DoD）**
- ✅ 后端路由层不再存在任何 `@router.websocket(...)`
- ✅ 前端无 `WebSocket(...)` 调用
- ✅ 有明确的回归测试证明"WS 不存在是预期"（仓库已有：`tests/integration/api/test_websocket_removed.py`）

---

### Step 2 — 修复 Project→Workflow 关联（让 rules_text 能真正影响工作流规划） ✅ 已完成

> **完成日期**：2025-12-26

**目标**：Deep Research 的入口是一等对象 Project，但当前 workflow 创建流程没有 project_id，导致：

- Project 下 workflow 列表可能为空（`WorkflowModel.project_id` 未被写入）
- Project rules_text 无法可靠注入 planner/system prompt

**工作清单**
- [x] 决策：**B 兼容**（Workflow 可独立 `project_id=None`，但 Deep Research 场景必须绑定到 Project）
- [x] 修改后端创建/导入工作流的输入 DTO + UseCase，使其能写入 `workflow.project_id`
  - DTO: `CreateWorkflowRequest.project_id`, `ImportWorkflowRequest.project_id`, `WorkflowResponse.project_id`
  - Input: `CreateWorkflowInput.project_id`, `ImportWorkflowInput.project_id`
  - UseCase: `create_workflow.py` 和 `import_workflow.py` 均设置 `workflow.project_id`
  - 路由: `workflows.py` 传递 `request.project_id`
- [x] 保持接口层返回仍是 `WorkflowResponse`（DTO），不直接返回实体

**测试覆盖**（15 passed）
- `test_create_workflow_should_set_project_id`
- `test_create_workflow_without_project_id_should_be_none`
- `test_import_workflow_should_set_project_id`
- `test_import_workflow_without_project_id_should_be_none`

**Codex 审查反馈 #1（2025-12-26 初版）**
- ✅ 实现符合需求，分层架构原则保持
- ⚠️ `ImportWorkflowResponse` 未返回 `project_id`（待评估是否需要）
- ⚠️ `project_id` 未做 `strip()` 规范化（与 `user_id` 处理方式不一致）→ **已修复**
- ⚠️ `project_id` 存在性未校验（不存在的 project 会在 DB 外键层失败变成 500）

**Codex 审查反馈 #2（2025-12-26 修复后）**
- ✅ 分层原则：依赖方向正确 (Interface → Application → Domain)
- ✅ 事务边界：UseCase 统一控制 commit/rollback，Route 不再调用
- ✅ 数据规范化：`project_id` 的 strip() 处理与 `user_id` 一致
- ✅ 向后兼容：不提供 project_id 时正确处理为 None
- ✅ 测试完整性：覆盖正常和边界情况
- ⚠️ 测试断言语法：建议改用 `assert_called_once()` 而非逗号表达式
- ⚠️ 建议增补 strip 边界测试（空白字符串）
- ⚠️ Run 归属校验已有完整测试覆盖（5/5 passed）

**后续改进（可选）**
- 考虑在 Application 层校验 `project_id` 存在性（返回 404 而非 500）
- 统一依赖注入方式（`get_transaction_manager()` vs 直接构造）

**完成标准（DoD）**
- ✅ `GET /api/projects/{project_id}/workflows` 能返回刚创建/导入的 workflow
- ✅ 创建 Run 时，`CreateRunUseCase` 的 project/workflow 归属校验仍正确（`src/application/use_cases/create_run.py`）
- ✅ 新增测试覆盖 project_id 设置逻辑

---

### Step 3 — 统一"工作流更新"链路与返回结构（防止 DTO/实体混用）✅ 已完成

> **调整说明**：原 Step 4 提前，作为 Step 3 的前置依赖。
> **完成日期**：2025-12-26

**目标**：彻底消灭"接口层直接连领域层"的旁路，避免出现：

- 可视化更新绕过应用层导致事务边界错误
- 应用层返回实体被接口层直接透传（DTO/实体混用）

**工作清单**
- [x] 盘点所有 workflow 更新入口（至少包括）：
  - `PATCH /api/workflows/{workflow_id}`（拖拽更新）→ 通过 `UpdateWorkflowByDragUseCase`
  - `POST /api/workflows/{workflow_id}/chat-stream`（对话改图）→ 通过 `UpdateWorkflowByChatUseCase`
- [x] 当前不存在"可视化更新直连 Domain"的旁路（所有更新都走 UseCase）
- [x] 统一返回：接口层统一返回 `WorkflowResponse`（DTO）
  - `workflows.py` 第 277/336/376 行：`-> WorkflowResponse`
  - 所有返回都通过 `WorkflowResponse.from_entity(workflow)`

**完成标准（DoD）**
- ✅ 任意更新入口都不会直接返回 Domain `Workflow` 实体（必须 DTO）
- ✅ 任意更新入口的写操作都由 UseCase 控制事务（路由层无 commit/rollback）
- ✅ `tests/unit/application/use_cases/test_update_workflow_by_drag.py` 通过（4/4）
- ✅ `tests/integration/api/workflows/test_workflows.py` 中与更新相关用例通过（18/18）

---

### Step 4 — 精简"多 Agent 协作体系" + 依赖分析（为 Step 5 做准备）✅ 已完成

> **调整说明**：原 Step 6 提前，因为 Step 5（planning 契约下沉）依赖于明确 Agent 边界。
> **完成日期**：2025-12-26

**目标**：先搞清楚"谁负责什么"，再决定如何收敛事件契约。

**现状事实（用于裁剪）**
- Coordinator 在启动时初始化：`src/interfaces/api/main.py:101`（`app.state.coordinator`）
- ConversationAgent 主要出现在：
  - 依赖注入：`src/interfaces/api/dependencies/agents.py`
  - ~~SSE 对话端点：`src/interfaces/api/routes/conversation_stream.py`~~（已删除）
- WorkflowAgent 在 Domain 中存在，但执行主链路已由 `WorkflowExecutionFacade` + LangGraph 接管：
  - `src/domain/agents/workflow_agent.py`
  - `src/application/services/workflow_execution_facade.py`

**工作清单**
- [x] **[前置] 依赖调用链分析**（必须先完成，再做删除决策）：
  - 分析 `CoordinatorAgent` 的调用方 → **必须保留**，核心控制枢纽
  - 分析 `ConversationAgent` 的调用方 → **必须保留**，推理和决策核心
  - 分析 `WorkflowAgent` 的调用方 → **部分保留**，AGENT 模式标记为实验性
  - 输出：`.claude/docs/agent-dependency-analysis.md`
- [x] 明确 Deep Research 的三角色（只保留必要角色）：
  - Coordinator：规则/守门（与 project rules 强绑定）→ ✅ CoordinatorAgent
  - Planner：对话→patch（对应 chat-stream）→ ✅ UpdateWorkflowByChatUseCase
  - Runtime：workflow→事件流（对应 execute/stream）→ ✅ WorkflowExecutionFacade → LangGraph
- [x] 删除/冻结"非主链路 agent"：
  - [x] 决策：删除 `Conversation Stream`（与 chat-stream 重叠，且不进入 Run 回放闭环）
  - [x] `WorkflowAgent` 保留但标记为实验性（AGENT 模式）
- [x] 把所有"内部执行链路"统一走应用层（已确认：`WorkflowExecutionFacade` 是唯一入口）

**完成标准（DoD）**
- ✅ 产出依赖分析报告：`.claude/docs/agent-dependency-analysis.md`
- ✅ 项目内存在且仅存在一条"工作流执行"应用层入口（`WorkflowExecutionFacade`）
- ✅ Coordinator 的决策/规则可以被证明"真的影响 planning 或 runtime"
- ✅ `Conversation Stream` 已删除：后端路由不再挂载、相关测试/前端调用同步删除
- ✅ 最小门禁测试验证（26/26 通过）

**Codex 审查反馈（2025-12-26）**
- ✅ 删除完整性：运行时代码侧已干净，无 conversation_stream 残留引用
- ✅ 分层架构：删除后接口层路由挂载结构保持一致
- ⚠️ 前端 `useWorkflowAI.ts` 事件处理与后端 `PlanningEvent` 不完全匹配 → Step 5 统一
- ⚠️ `chat_workflows.py` 接口层→基础设施耦合 → Step 5 下沉到 Application 层

---

### Step 5 — 收敛对话改图的"规划事件契约"到 Application（分层重构）✅ 已完成

> **调整说明**：原 Step 3，重新设计架构以保持分层原则。
> **完成日期**：2025-12-26

**目标**：让 planning 事件成为应用层稳定产出，路由层只做透传 + SSE 编码 + RunEvent 录制。

**架构设计（保持分层原则）**

```
当前（问题）:
  UseCase → raw 事件 → 路由层转换 → PlanningEvent → SSE

目标（重构后）:
  UseCase → 用例事件 → Application Service（EventMapper）→ PlanningEvent → 路由层透传 → SSE
```

**为什么不让 UseCase 直接产出 PlanningEvent？**
- `PlanningEvent` 是 SSE 表现层契约（包含 `channel`、`sequence` 等 SSE 专属字段）
- UseCase 应产出用例事件（如 `WorkflowPlanningStarted`、`ReActStepCompleted`）
- Application Service（如 `PlanningEventMapper`）负责 用例事件 → PlanningEvent 转换
- 路由层只做透传 + SSE 编码

**工作清单**
- [x] 定义用例事件（Application Events）：
  - `WorkflowPlanningStarted`
  - `ReActStepCompleted`（含 thought/action/observation）
  - `WorkflowPatchGenerated`
  - `WorkflowPlanningCompleted`
  - `WorkflowPlanningFailed`
- [x] 创建 Application Service：`src/application/services/planning_event_mapper.py`
  - 输入：用例事件流
  - 输出：`PlanningEvent` 流
  - 负责：sequence 分配、timestamp 生成、metadata 组装
- [x] 创建 Workflow 映射器：`src/application/services/workflow_public_mapper.py`
  - 负责：Workflow 实体 → 公开 dict 格式（避免 Interface DTO 依赖）
- [x] 修改 `UpdateWorkflowByChatUseCase.execute_streaming()` 产出用例事件
- [x] 路由层 `chat_workflows.py` 简化为：
  - 归一化/校验 `run_id`
  - 调用 UseCase → 通过 EventMapper 转换 → `yield sse(event)` + `recorder.record_best_effort(...)`
- [x] 保持向后兼容：不破坏现有 `tests/integration/api/workflows/test_chat_stream_contract.py`

**新增/修改文件**
- `src/application/events/__init__.py`（新增）
- `src/application/events/workflow_planning_events.py`（新增，5 种事件类型）
- `src/application/services/workflow_public_mapper.py`（新增）
- `src/application/services/planning_event_mapper.py`（新增）
- `src/application/use_cases/update_workflow_by_chat.py`（修改）
- `src/interfaces/api/routes/chat_workflows.py`（简化 ~40%，294→156 行）
- `tests/unit/application/use_cases/test_update_workflow_by_chat.py`（修改）
- `tests/integration/api/workflows/test_chat_stream_contract.py`（修改）

**Codex 审查反馈（2025-12-26）**
- ✅ 分层正确性：Application Events 放在 Application 层合理
- ✅ 职责分离：UseCase/Mapper/Router 边界清晰
- ✅ 事务边界：commit 在 yield completed 前执行正确
- ✅ 事件设计：5 种事件覆盖完整
- ⚠️ 封装泄漏：Router 调用 mapper 私有 `_next_sequence()` → **已修复**（添加 `create_initial_event()`/`create_error_event()` 公开 API）
- ⚠️ 注释不一致：`step_number` 注释写 0-based 但实际用 1-based → **已修复**
- ⚠️ Docstring 过时：`execute_streaming()` 说抛异常但实际 yield Failed → **已修复**
- ⚠️ 建议：添加 PlanningEventMapper 单测、处理 asyncio.CancelledError → 记录为后续改进

**完成标准（DoD）**
- ✅ 规划 SSE 的每条事件都包含 `type` + `channel="planning"`
- ✅ planning 事件落库后的回放与实时输出"逐条一致"（同一份 dict）
- ✅ UseCase 不再输出 `processing_started/react_step/...` 这类"内部事件"，改为用例事件
- ✅ Application Service（EventMapper）存在且路由层使用公开 API
- ✅ 路由层代码行数减少 ~40%（294→156 行，去除转换逻辑）
- ✅ 所有 29 个测试通过（20 单元 + 9 集成）

---

### Step 6 — 用 LangGraph 统一 Planner/Runtime 的"Port"边界（为动态生成工作流做准备）✅ 已完成

> **完成日期**：2025-12-26

**目标**：不是"把某模块改成 LangGraph"，而是把 LangGraph 定位为统一运行时，并通过 Port 隔离，避免未来替换困难。

**现状**
- `WorkflowExecutorPort` 已存在：`src/domain/ports/workflow_executor_port.py`
- `WorkflowChatServicePort` 已存在：`src/domain/ports/workflow_chat_service.py`

**工作清单**
- [x] 评估现有 Port 是否足够：
  - `WorkflowExecutorPort` 覆盖 Runtime 需求 ✅
  - `WorkflowChatServicePort` 覆盖 Planner 需求 ✅
- [x] 新增 `LangGraphWorkflowExecutorAdapter`（Infrastructure 层）实现 `WorkflowExecutorPort`
- [x] 重构 `WorkflowExecutionFacade`：移除直接 LangGraph 依赖，通过注入使用
- [x] 更新依赖注入点：`workflows.py` 和 `workflow_executor_adapter.py`
- [x] Application UseCase 只依赖 Port，不直接依赖 LangGraph ✅

**新增/修改文件**
- `src/infrastructure/lc_adapters/workflow/langgraph_workflow_executor_adapter.py`（新增）
- `src/application/services/workflow_execution_facade.py`（修改）
- `src/interfaces/api/routes/workflows.py`（修改）
- `src/interfaces/api/services/workflow_executor_adapter.py`（修改）

**Codex 审查反馈（2025-12-26）**
- ✅ DoD1（Application 不直接依赖 LangGraph）：满足
- ✅ DoD2（Port 替换能力）：基本满足，`/execute/stream` 已切到 Port
- ✅ DoD3（事件落库和回放）：落库链路具备
- ⚠️ 回放端点输出格式与原 SSE dict 不完全一致（`RunEventResponse` 含 `payload` 嵌套）
- ⚠️ `RunEventRecorder` 在 Application 层直接 import Infrastructure 仓储（与 Step 6 无关但值得注意）

**测试结果**
- pyright 类型检查：0 errors, 0 warnings
- 最小门禁测试：53 passed
- Facade 和 LangGraph 测试：36 passed

**完成标准（DoD）**
- ✅ Application 层在类型依赖上不直接 import LangGraph（LangGraph 仅出现在 infrastructure）
- ✅ `/chat-stream` 与 `/execute/stream` 都能通过 Port 实现替换（至少有一条路径已切到 Port）
- ✅ 规划与执行事件都能落库到 `run_events`，并能回放

---

### Step 7 — 节点体系为 Deep Research 收敛（定义"画布上到底是什么"）✅ 已完成

> **完成日期**：2025-12-26
> **最后更新**：2025-12-26（完成所有改进项）

**目标**：画布节点必须有清晰定义（输入/输出/副作用/可并行性），并能映射到 LangGraph runtime。

**现状事实（工作量估算）**
- NodeType 枚举：`src/domain/value_objects/node_type.py` 包含 **35 种类型**
- YAML 节点定义：`definitions/nodes/*.yaml` 包含 **20 个文件**
- GenericNode 体系：`src/domain/services/generic_node.py`
- Deep Research 预估需要 6-10 种 → **收敛为 11 种核心 + 6 种扩展**

**工作清单**
- [x] **[前置] 节点使用率分析**：
  - 扫描现有代码库，统计各 NodeType 使用频率
  - 输出：使用率报告 `.claude/docs/node-usage-analysis.md`
- [x] 定义 Deep Research 最小节点集合（11 种核心）
  - `START`, `END`, `LLM`, `KNOWLEDGE`, `HTTP`, `FILE`, `HUMAN`, `CONDITIONAL`, `LOOP`, `PARALLEL`, `TRANSFORM`
- [x] 明确"通用节点（generic）"的去留策略：
  - 决策：**内部保留**，不对外暴露，仅用于迁移/插件
  - `CONTAINER` 保留为结构/编排节点
- [x] 分批收敛策略：
  - Phase 0：定义 canonical 11 种 + extended 6 种 ✅
  - Phase 1：实现 alias → canonical 映射层 ✅
  - Phase 2：迁移存量（待后续执行）
  - Phase 3：删除废弃类型（待后续执行）
- [x] 左侧拖拽面板决策：
  - 保留，但只展示 canonical + extended 节点集合

**新增/修改文件**
- `src/domain/value_objects/node_type.py`：添加 `CANONICAL_NODE_TYPES`, `NODE_TYPE_ALIASES`, `canonicalize()` 等
- `src/domain/services/node_type_validator.py`：支持归一化验证、`canonicalize_planner_output()`
- `src/domain/services/node_registry.py`：注册 `CONDITIONAL` schema、`Node.from_dict()` 使用 canonicalize
- `tests/unit/domain/services/test_node_type_validator.py`：52 个测试（Step 7 新增）
- `tests/unit/domain/services/test_node_registry.py`：27 个测试（含 4 个 Node.from_dict 归一化测试）
- `.claude/docs/node-usage-analysis.md`：节点分析报告

**Codex 审查反馈（2025-12-26 初版 + 改进版）**

初版反馈：
- ✅ 分层原则：别名映射放在 Domain 层合理
- ✅ 向后兼容：废弃类型通过归一化后仍能通过验证
- ✅ 测试覆盖：NodeType 枚举输入、废弃类型、边界情况
- ⚠️ 验证绕过风险：`nodes=[]` + `nodes_to_add=[unknown]` 可绕过验证

改进后反馈：
- ✅ 验证绕过风险已消除：同时验证 `nodes` 和 `nodes_to_add`
- ✅ 归一化一致性：移除 `str()` 调用，直接支持 NodeType 枚举
- ✅ 双键归一化：同时存在 `type` 和 `node_type` 时都会归一化
- ✅ 外部 Enum 支持：带 value 属性的外部 Enum 也能正确标记 `was_deprecated`
- ✅ Node.from_dict() 已引入 canonicalize（反序列化时自动归一化废弃类型）

**测试结果**
- `test_node_type_validator.py`：52 passed
- `test_node_registry.py`：27 passed（含 4 个 Node.from_dict 归一化测试）
- 总计：75 passed

**完成标准（DoD）**
- ✅ 产出节点使用率分析报告：`.claude/docs/node-usage-analysis.md`
- ✅ 画布上每个节点都有：名称、类型、输入 schema、输出 schema（在 `NodeRegistry.PREDEFINED_SCHEMAS` 中定义）
- ✅ Runtime 能执行该节点集合（最小门禁测试通过）
- ✅ Planner 生成的 patch 只能使用该节点集合（由 `NodeTypeValidator.canonicalize_planner_output()` 校验保证）
- ✅ `Node.from_dict()` 反序列化时自动归一化废弃类型

---

### Step 8 — 前端收敛到"只保留 Workflow 编辑 + Project rules"（与后端契约一致）✅ 已完成

> **完成日期**：2025-12-26

**目标**：只留下编辑工作流一个页面 + 项目规则输入，前端要和后端契约对齐，避免"前端有 Agent 页面但后端无 /agents"。

**工作清单**
- [x] 盘点前端路由与菜单：
  - `web/src/layouts/MainLayout.tsx`（已移除 Agent 管理菜单项，添加 Project rules）
- [x] 删除/隐藏 Agent 相关页面与 API client（后端无对应端点）
  - 删除：`web/src/features/agents/`、`web/src/features/runs/`、`web/src/features/home/`
  - 删除：`web/src/shared/hooks/useAgents.ts`、`useRuns.ts`
  - 删除：`web/src/shared/types/agent.ts`、`run.ts`、`task.ts`
  - 删除：`web/src/shared/utils/request.ts`
- [x] 增加/强化 Project rules 编辑入口（对应后端 `PATCH /api/projects/{project_id}` 的 `rules_text`）
  - 新增：`web/src/features/projects/pages/ProjectRulesPage.tsx`
  - 路由：`/project/rules`
  - API：`apiClient.projects.{list,getById,update,create}`
- [x] workflow editor 页面只保留：
  - 保存（drag update）
  - chat-stream（规划）
  - execute/stream（执行）
  - run 回放（runs events stream）
  - 项目规则入口按钮（`WorkflowEditorPageWithMutex.tsx`）
- [x] 评估新增 hooks 的去留：
  - `useConflictResolution.ts`：✅ 保留（无 WS 依赖，纯状态管理）
  - `useWorkflowHistory.ts`：✅ 保留（支持 undo/redo）
  - `useKeyboardShortcuts.ts`：✅ 保留（提升 UX）
- [x] 清理残留文字引用：
  - `SimReplicaPage.tsx`：Agent → LLM/Workflow
  - `cors-test.html`：/api/agents → /api/workflows

**新增/修改文件**
- `web/src/features/projects/pages/ProjectRulesPage.tsx`（新增）
- `web/src/features/projects/pages/ProjectRulesPage.module.css`（新增）
- `web/src/features/projects/pages/index.ts`（新增）
- `web/src/services/api.ts`（添加 projects API）
- `web/src/app/router.tsx`（添加 `/project/rules` 路由）
- `web/src/layouts/MainLayout.tsx`（移除 Agent 菜单，添加 Project rules）
- `web/src/shared/hooks/index.ts`（清理导出，修复路径）
- `web/src/shared/types/index.ts`（清理导出）
- `web/src/features/workflows/pages/WorkflowEditorPageWithMutex.tsx`（添加项目规则按钮）
- `web/src/features/sim-replica/pages/SimReplicaPage.tsx`（Agent → LLM）
- `web/public/cors-test.html`（/api/agents → /api/workflows）

**Codex 审查反馈（2025-12-26）**
- ✅ 运行时代码无 `/api/agents` 调用
- ✅ Project API 契约与后端一致（`ProjectListResponse`、`Project` 类型匹配）
- ✅ 路由配置正确（编辑器 + Project rules）
- ✅ hooks 导出路径已修复（`@/hooks/useWorkflowAI`）
- ✅ 残留文字已清理

**测试结果**
- TypeScript 类型检查：✅ 通过
- 前端最小门禁测试：58 passed
- 后端最小门禁测试：53 passed

**完成标准（DoD）**
- ✅ 前端不会请求不存在的 `/agents/*` API
- ✅ 能在 UI 完成：编辑 rules_text → 对话改图 → 执行 → Run 回放
- ✅ `web` 的 vitest 能跑通最小门禁集合（Step 1 定义）

---

### Step 9 — 性能与一致性补强（事件落库与并发边界）✅ 已完成

> **完成日期**：2025-12-26

**目标**：在 Deep Research 场景里事件量大（并行拆解），必须明确写入策略与竞态风险。

**工作清单**
- [x] 处理 `AppendRunEventUseCase.count_by_run_id()` 的并发竞态风险
  - 实现 CAS (Compare-And-Swap) 条件更新：`update_status_if_current()`
  - 移除 TOCTOU 风险的 `count_by_run_id()` 判断
- [x] 事件落库从"同步 best-effort"演进为"非阻塞 best-effort"
  - 新增 `AsyncRunEventRecorder`：`asyncio.Queue` + 后台 worker
  - 集成到 FastAPI lifespan (`app.state.event_recorder`)
  - SQLite 配置 `check_same_thread=False` 支持跨线程
- [ ] SSE 标准化：考虑补 `id:` 行 + `Last-Event-ID`（可选，作为后续改进）

**新增/修改文件**
- `src/domain/ports/run_repository.py`：添加 `update_status_if_current()` Port
- `src/infrastructure/database/repositories/run_repository.py`：实现 CAS 条件更新
- `src/application/use_cases/append_run_event.py`：重构使用 CAS，移除 count_by_run_id
- `src/application/services/async_run_event_recorder.py`：新增异步录制器
- `src/infrastructure/database/engine.py`：添加 SQLite 跨线程支持
- `src/interfaces/api/main.py`：集成异步录制器
- `tests/unit/application/use_cases/test_append_run_event.py`：更新测试适配 CAS

**Codex 审查反馈（2025-12-26）**
- ✅ CAS 实现正确：防止终态被覆盖回 running
- ✅ 分层架构合理：Port/Infra/UseCase 职责清晰
- ✅ 异步录制器满足非阻塞 best-effort 需求
- ⚠️ 去重优化：终止事件里重复的 `created→running` CAS 已修复
- ⚠️ SQLite 跨线程：已添加 `check_same_thread=False`

**测试结果**
- 最小门禁测试：61 passed
- 单元测试：22 passed (8 AppendRunEvent + 14 RunEventRecorder)

**完成标准（DoD）**
- ✅ 并发执行（LangGraph 并行）下，Run 状态与首事件判定不会出现明显错乱
  - CAS 保证只有一个事务能成功 `created → running`
  - 终态 `completed/failed` 不会被覆盖回 `running`
- ✅ 即使数据库慢，SSE 仍可持续输出
  - `AsyncRunEventRecorder` 使用非阻塞 `enqueue()`
  - 队列满时丢弃（best-effort），不阻塞 SSE

---

## 4) 执行顺序（调整后）

> **调整理由**：
> - Step 1.5（删 WS）提前，减少干扰
> - Step 4（Agent 精简 + 依赖分析）前置于 Step 5（planning 契约下沉）
> - Step 7（节点收敛）工作量大，需分批进行

```
Phase A（基础护航）✅ 已完成:
  Step 1 ✅ → Step 1.5（删 WS）✅

Phase B（关联修复）✅ 已完成:
  Step 2 ✅ → Step 3 ✅

Phase C（核心重构）✅ 已完成:
  Step 4 ✅ → Step 5 ✅ → Step 6 ✅

Phase D（收敛清理）✅ 已完成:
  Step 7（分批收敛）✅ → Step 8 ✅

Phase E（性能优化）✅ 已完成:
  Step 9 ✅
```

**实际进度**：
- Phase A: ✅ 2025-12-26 完成
- Phase B: ✅ 2025-12-26 完成
- Phase C: ✅ 2025-12-26 完成（Step 4、Step 5、Step 6）
- Phase D: ✅ 2025-12-26 完成（Step 7、Step 8）
- Phase E: ✅ 2025-12-26 完成（Step 9）

---

## 5) 已确认的"关键决策点"

以下决策点已确认，用于锁定后续实现方向：

### 原有决策点

| # | 决策点 | 选项 | 建议 |
|---|--------|------|------|
| 1 | Workflow 是否必须绑定 Project？ | A 强制 / B 兼容 | **B 兼容**（先兼容，Deep Research 场景强制）|
| 2 | `/api/conversation/stream` 是否要保留？ | 保留 / 删除 | **删除**（与 chat-stream 功能重叠）|
| 3 | 通用节点 generic 是否要保留？ | 保留 / 删除 | **保留但强监管**（Deep Research 可能需要代码执行后门）|

### 新增决策点

| # | 决策点 | 选项 | 建议 |
|---|--------|------|------|
| 4 | Step 5 事件转换位置？ | A. UseCase 直接产出 PlanningEvent / B. Application Service 转换 | **B 已实现**（保持分层原则）|
| 5 | Step 6 Port 策略？ | A. 新增 Port / B. 复用现有 `WorkflowExecutorPort` + Adapter | **B 已实现**（`LangGraphWorkflowExecutorAdapter`）|

---

## 6) 审查记录

| 版本 | 日期 | 审查人 | 主要变更 |
|------|------|--------|----------|
| v1 | 2025-12-26 | codex | 初始版本 |
| v2 | 2025-12-26 | Claude | 补充遗漏现状（0.3-0.6）、调整 Step 3 架构设计、细化 Step 4/7 依赖分析要求、修正执行顺序、新增决策点 4/5 |
| v3 | 2025-12-26 | Claude + Codex | Step 5 完成：Application Events + PlanningEventMapper + 路由层简化 |
| v4 | 2025-12-26 | Claude + Codex | Step 6 完成：LangGraphWorkflowExecutorAdapter + WorkflowExecutionFacade 重构 + Port 边界隔离 |
| v5 | 2025-12-26 | Claude + Codex | Step 7 完成：节点收敛（11 canonical + 6 extended）、alias → canonical 映射、Node.from_dict() canonicalize、验证绕过修复、双键归一化、外部 Enum 支持（75 tests） |
| v6 | 2025-12-26 | Claude + Codex | Step 9 完成：CAS 并发安全（update_status_if_current）、AsyncRunEventRecorder 非阻塞落库、SQLite 跨线程支持、去除重复 CAS 调用（61 tests） |
