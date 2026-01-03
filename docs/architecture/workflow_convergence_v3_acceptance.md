# Workflow Convergence V3 — 验收记录（Evidence Log）

本文件用于记录 workflow_convergence_v3 的“可验证证据”，只收录可复现的命令、输出路径与提交点（不写推测）。

## 运行环境（本地）

- OS: Windows
- Shell: PowerShell
- Repo 根目录: `D:\My_Project\agent_data`

## 证据索引（按里程碑）

### M0 基线锁定（WFCONV3-000）

- 代码提交: `c35eac3` (`[WFCONV3-000] M0 基线锁定：路由/契约测试护栏`)
- 验收命令:
  - `pytest -q tests/integration/api/workflows/test_route_guardrails.py`
- 证据说明:
  - OpenAPI 路由护栏（Create/Execute/Chat/WS）以测试断言形式固化，避免协议漂移。

### M5 创建收敛（WFCONV3-070）

- 代码提交: `351dd7e` (`[WFCONV3-070] M5 创建收敛：删除 legacy create（后端+前端）`)
- 验收命令（示例）:
  - `pytest -q tests/integration/api/workflow_chat/test_chat_create_stream_api.py`
  - `pytest -q tests/integration/api/workflows/test_route_guardrails.py tests/integration/api/workflows/test_legacy_create_workflow_api.py`
  - `npm test -- src/features/workflows/pages/__tests__/WorkflowEditorPage.test.tsx`（在 `web/` 目录）
- 证据说明:
  - legacy create 入口移除；失败路径 fail-closed，避免半成品 workflow 残留。

### M6 Run 强一致（后端，WFCONV3-080）

- 代码提交: `bdcf848` (`[WFCONV3-080] M6 Run 强一致：执行入口唯一化 + 强制 run_id（后端）`)
- 验收命令（示例）:
  - `pytest -q tests/integration/api/workflows/test_workflows.py`
  - `pytest -q tests/integration/api/workflows/test_run_event_persistence.py`
- 证据说明:
  - `/execute` 入口移除；`/execute/stream` 强制 `run_id` 且校验归属；关键事件可落库验证。

### M6 Run 强一致（前端，WFCONV3-090）

- 代码提交: `14cb98b` (`[WFCONV3-090] M6 Run 强一致：Run 创建失败则不执行（前端）`)
- 验收命令（示例）:
  - `npm test -- src/features/workflows/pages/__tests__/WorkflowRunFailClosed.test.tsx`（在 `web/` 目录）
- 证据说明:
  - Run 创建失败时不触发 execute/stream；前端给出可操作错误提示。

### M2 DDD 护栏（WFCONV3-120）

- 代码提交: `e791633` (`[WFCONV3-120] M2 DDD 护栏：引入 import-linter 或替代静态检查`)
- 静态检查命令（示例）:
  - `python scripts/ddd_boundary_checks.py`
  - `lint-imports --config .import-linter.toml`

## 如何追加证据（后续里程碑）

- 每完成一条 issue，对应增加一节（含 commit hash + 可复现命令）。
- 若证据包含文件输出（日志/截图），优先记录相对路径（例如 `logs/...`、`tmp/...`）。
