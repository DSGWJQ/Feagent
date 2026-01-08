# WFCTRL-070 回归：完整真实测试记录

目标：按项目约定口径执行回归，并对“无法全量 pytest -q”的原因做失败分流说明，避免误归因到 workflow 改动。

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

## pytest 全量现状（失败分流）

执行 `pytest -q --collect-only` 当前在收集阶段失败（exit `1`），共 `11` 个 collection errors：

- `tests/integration/api/test_workflow_execution_error_classification.py`
- `tests/integration/api/workflow_chat/test_react_orchestrator_real_scenarios.py`
- `tests/integration/api/workflow_chat/test_react_orchestrator_workflow_chat.py`
- `tests/integration/llm/test_llm_classification_integration.py`
- `tests/integration/platform/test_format_constraints_real_scenarios.py`
- `tests/integration/task_executor/test_langgraph_task_executor_integration.py`
- `tests/integration/task_executor/test_langgraph_workflow_executor_refactor.py`
- `tests/integration/task_executor/test_task_executor_adapter_refactor.py`
- `tests/integration/task_executor/test_task_executor_agent_enhanced.py`
- `tests/integration/test_memory_distillation_pipeline.py`
- `tests/integration/test_saturation_flow_integration.py`

判定：这些错误为**收集阶段导入失败**（缺失 `src.lc` / `ShortTermSaturatedEvent` 等），与本次 workflow 条件门控/模板渲染/对话增量编辑的代码路径无直接关联。建议后续单独立项处理缺失模块与集成测试链路。
