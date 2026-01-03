# ADR: Run 一致性（选择方案 A：后端为真源）

## 背景 / 症状

前端在“点击 Run”时会尝试创建 `run_id` 并将其传入执行请求，用于会话追踪与后续回放。然而后端此前缺少与之对应的创建入口与落库链路，导致：

- 前端展示 “Session started (run_...)”，但后端无法查询该 Run（事实脱钩）
- 执行事件无法持久化到 `run_events`，Run 生命周期无法被可靠驱动

## 方案对比

### 方案 A（选择）：Run 由后端创建并持久化，执行/流式事件关联 run_id

- 新增/补齐：
  - `POST /api/projects/{project_id}/workflows/{workflow_id}/runs`：创建 Run（支持 `Idempotency-Key`）
  - `/api/workflows/{workflow_id}/execute` 与 `/execute/stream`：接收 `run_id`，并写入 `run_events`（best-effort 非阻塞）
- 真源：后端数据库 `workflow_runs` / `run_events`

### 方案 B：移除前端 run_id 概念，仅以 SSE 事件为准

- 需要改动前端状态与契约，且会影响既有“会话/回放”设计路径（变更面较大）。

## 决策

选择 **方案 A**：Run 由后端持久化作为事实真源，执行链路仅“引用并关联”该 run_id。

## 落地实现（关键点）

1) **幂等创建 Run**
- 若客户端提供 `Idempotency-Key`，后端用稳定主键派生 `run_id`，重复请求返回同一 Run（避免重复创建）。
- 代码：`src/interfaces/api/routes/runs.py`
- 领域支撑：`src/domain/entities/run.py`

2) **执行事件落库（RunEvent）并驱动生命周期**
- `AsyncRunEventRecorder` 通过后台 worker 将事件写入 `run_events`，并使用 CAS 驱动 `workflow_runs.status`（created → running → completed/failed）。
- 代码：
  - `src/application/services/async_run_event_recorder.py`
  - `src/application/use_cases/append_run_event.py`
  - `src/infrastructure/database/repositories/run_event_repository.py`
  - `src/infrastructure/database/transaction_manager.py`

3) **执行端点接收 run_id 并关联事件**
- `POST /api/workflows/{workflow_id}/execute/stream`：对每个 SSE event 进行 best-effort enqueue 落库；同时将 `run_id` 回传到 SSE payload（便于诊断/对齐）。
- `POST /api/workflows/{workflow_id}/execute`：追加终止事件（best-effort），保证最小可追踪性。
- 代码：`src/interfaces/api/routes/workflows.py`

## 风险与边界

- 未引入新的 DB 字段来存储幂等键，幂等通过“稳定主键”实现；若发生极低概率哈希碰撞，需要通过 409/排查处理。
- 事件落库为 best-effort：落库失败不会阻塞 SSE；诊断依赖后端日志与 `run_events` 观测。
