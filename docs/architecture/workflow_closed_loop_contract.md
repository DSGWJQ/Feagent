# Workflow 闭环合同（Closed Loop Contract）

> 文档版本：v1.0
> 创建日期：2026-01-04
> 目的：将 `Report.md` / `plan/2026-01-04_22-20-30-workflow-closed-loop.md` 的“硬前提”冻结为可验证的系统合同（tests/scripts），作为后续实现与回归的验收口径来源。

## 1. Scope / Out of scope

### Scope（本合同覆盖）

- 统一 `run_id` 作为执行事实源（SSE 执行流 + RunEvents 持久化 + 回放一致性）。
- “validated decision” 的允许/拒绝边界（Coordinator 监督域的 allow 才允许进入执行链路）。
- 执行事件（execution stream）的最小语义合同：允许的 event types、必填字段、fail-closed 行为。
- “缺失 Coordinator 时必须拒绝且无副作用”的入口合同（定义与验收口径）。

### Out of scope（本合同不做）

- 大规模 DDD 重构/分层重排。
- 更换事件总线实现或引入新的异步基础设施。
- 更改已有对外 API 的路径/参数（除非后续 issue 明确要求并提供兼容策略）。

## 2. 关键术语（冻结定义）

### 2.1 `run_id`

- 定义：一次 workflow 执行的唯一标识，作为执行事实源的关联键。
- 规则：
  - 任一执行入口（REST / agent / replay）必须显式携带 `run_id`，禁止隐式生成不可追踪的 `run_id`。
  - execution SSE 事件必须包含 `run_id`（见 3.2）。

### 2.2 `validated decision`

- 定义：由 Coordinator 监督域验证并给出 allow/deny 结论的决策载荷（decision payload）。
- 规则：
  - 只有 allow 的 validated decision 允许进入执行链路（bridge/entry）。
  - deny/无法验证/缺字段：必须 fail-closed（拒绝执行且无副作用），并产出可审计记录。

### 2.3 “终态（terminal state）”

- 定义：一次执行的最终结果事件，至少包含：
  - `workflow_complete`（成功终态）
  - `workflow_error`（失败终态）
- 规则：同一 `run_id` 的事件序列必须出现且仅出现一次终态（幂等与去重由后续 issue 固化）。

## 3. 事件与执行合同（可测试）

### 3.1 执行事件类型（execution event types）

执行流（execution stream）在 API 边界的最小合同冻结在代码中：

- `src/application/services/workflow_event_contract.py`
  - 允许：仅 `node_*` 与 `workflow_*`
  - 禁止：`planning`、`tool_call`、`tool_result`

### 3.2 执行事件必填字段（execution SSE required fields）

- 每条 execution SSE 事件必须包含：
  - `type`（符合 3.1）
  - `run_id`
  - `executor_id`
- 违反合同必须 fail-closed：不得向客户端输出“伪装的成功事件”；应转为 `workflow_error`（见 `src/application/services/workflow_run_execution_entry.py` 的异常分支）。

## 4. 入口 fail-closed 合同（定义）

> 本节定义“应当如此”的合同；具体实现与回归由后续 WFCL-* issue 落地并在测试中固化。

- 在 Coordinator 缺失/未配置/不可用时：所有新增/修改的对话入口必须拒绝请求（fail-closed）。
- 拒绝时不得产生副作用：不创建 workflow、不创建 run、不写入 RunEvents（除非是显式、可控的审计拒绝事件）。

## 5. 可执行验收清单（绑定到 tests/scripts）

### 5.1 当前可执行且应为绿色（本仓库基线）

1) 执行事件合同（type/run_id/executor_id）
   - `python -m pytest -q tests/unit/application/services/test_workflow_event_contract.py`

2) 工作流核心检查（本地聚合脚本）
   - `powershell -ExecutionPolicy Bypass -File scripts/workflow_core_checks.ps1`
   - 其中 `python scripts/ddd_boundary_checks.py` 包含 CI 静态门禁（WFCL-070）：
     - `workflow_create_base_entry_unique`：禁止新增未批准的 `Workflow.create_base(...)` 创建入口（最多 1 个）
     - `internal_workflow_create_guard_max_2`：限制内部 workflow create guard 的入口扩散（最多 2 个）

3) 内部创建入口默认不可达（WFCL-060）
   - `python -m pytest -q tests/integration/api/workflows/test_internal_create_endpoints_access.py`

4) 灰度/回滚开关（WFCL-100）
   - `ENABLE_DECISION_EXECUTION_BRIDGE=false`（默认关闭；需要灰度时开启）
   - 回滚优先级：先关 `ENABLE_DECISION_EXECUTION_BRIDGE`，必要时再关 `ENABLE_LANGGRAPH_WORKFLOW_EXECUTOR` 或启用 `DISABLE_RUN_PERSISTENCE`

### 5.2 将在后续 issue 固化为绿色（当前可能未完全满足）

- Coordinator 缺失时 chat-create 必须 fail-closed 且无副作用（WFCL-050）
  - `pytest -q tests/integration/api/workflow_chat/test_chat_create_stream_api.py`

- validated decision → RunEvents → replay 一致性（WFCL-080）
  - `pytest -q tests/integration/api/workflows/test_run_event_persistence.py`
  - `pytest -q tests/integration/api/runs/test_run_events_replay_api.py`
