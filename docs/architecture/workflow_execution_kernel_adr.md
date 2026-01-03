# ADR: Workflow 执行内核唯一化（选择 A）

## 背景 / 问题

代码库中存在多套“可能用于执行 workflow”的实现与入口，容易出现同一 `workflow_id` 的执行状态与事件语义不一致，甚至产生“双内核并行执行”的重复事件/双写风险。

为了把执行语义收敛为唯一真源，需要明确并落地一个**权威执行内核（kernel）**，并冻结/移除其它分叉调用点。

## 备选方案

### 方案 A（选择）：WorkflowExecutionOrchestrator / ExecuteWorkflowUseCase / WorkflowEngine

- 入口：`WorkflowExecutionOrchestrator` → `WorkflowExecutionFacade` → `ExecuteWorkflowUseCase`
- 内核：`WorkflowExecutor` → `WorkflowEngine`（Domain）
- 特点：当前 FastAPI `POST /api/workflows/{workflow_id}/execute` 与调度器复用该路径；事件结构稳定，易于扩展。

### 方案 B：LangGraphWorkflowExecutor（或 WorkflowAgent 内核）

- 入口/实现存在，但目前未形成稳定的端到端可用链路，且与现有事件语义存在分叉风险。

## 决策

选择 **方案 A** 作为唯一权威 workflow 执行内核（single source of truth）。

## 落地变更（与追溯点）

1) **统一执行器标识**
- 在 `ExecuteWorkflowUseCase` 的返回值与流式事件中追加 `executor_id=workflow_engine_v1`，用于日志/事件侧的“执行内核唯一化”可观测。
- 代码：`src/application/use_cases/execute_workflow.py`

2) **冻结分叉调用点（WorkflowAgent）**
- `WorkflowAgent.handle_decision` 对 `decision_type == "execute_workflow"` 返回 `not_supported`，并提示使用 `POST /api/workflows/{workflow_id}/execute`。
- 目的：避免 WorkflowAgent 以其独立的 in-memory DAG 语义执行 workflow，造成与 `WorkflowEngine` 分叉。
- 代码：`src/domain/agents/workflow_agent.py`

## 被冻结/处理的调用点清单

- `src/domain/agents/workflow_agent.py`：`handle_decision(... decision_type == "execute_workflow")`

## 影响与后续

- 若后续需要启用 LangGraph 作为执行内核，应新增独立 ADR 并进行一次性切换（避免“按请求分流”导致双语义）。
- 若确实需要 Agent 侧触发执行，应通过 API/Facade 的单一入口触发，并保持事件/状态语义一致。
