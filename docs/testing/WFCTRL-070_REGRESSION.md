# WFCTRL-070 回归：完整真实测试记录

目标：按项目约定口径执行回归，并对“无法全量 pytest -q”的原因做失败分流说明，避免误归因到 workflow 改动。

更新（2026-02-05）：当前仓库已可全量执行 `pytest -q` 并通过；本文件保留为历史记录参考。

## 口径清单（退出码必须为 0）

- ✅ `python scripts/validate_node_definitions.py --strict`（exit `0`）
- ✅ `pnpm -C web type-check`（exit `0`）
- ✅ `pnpm -C web test`（exit `0`）

## 后端：与本需求相关的 unit + integration

说明：仅覆盖本次需求链路（条件门控 / 对话增量编辑 / 配置模板化）相关测试，确保回归无漂移。

- ✅ `pytest -q tests/unit/domain/services/test_workflow_executor.py`
- ✅ `pytest -q tests/unit/domain/services/test_workflow_engine_templating.py`
- ✅ `pytest -q tests/unit/domain/services/test_workflow_engine_edge_condition_semantics.py`
- ✅ `pytest -q tests/unit/domain/services/test_workflow_chat_service_enhanced_modifications.py`
- ✅ `pytest -q tests/integration/test_workflow_engine_templating_http_stub.py`（场景 A）
- ✅ `pytest -q tests/integration/test_workflow_condition_gating.py`（场景 B）
- ✅ `pytest -q tests/integration/test_workflow_chat_incremental_update.py`
- ✅ `pytest -q tests/integration/test_workflow_chat_update_changes_execution.py`（场景 C）

## pytest 全量现状

更新（2026-02-06）：`pytest -q` 可全量执行并通过（exit `0`）。本文早期记录的 collection errors 清单已不再适用，已移除。
