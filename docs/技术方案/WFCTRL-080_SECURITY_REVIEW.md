# WFCTRL-080 红队复审与文档同步（安全/语义）

目标：对本轮落地的三项关键能力做红队复审（fail-safe / fail-closed / 越界拒绝），并给出可回归的证据（测试与代码入口）。

## 复审结论（Checklist）

1) ✅ 条件表达式 `edge.condition`：**safe evaluator + fail-closed**
- 实现入口：`src/domain/services/workflow_engine.py`（`_evaluate_edge_condition` / `_should_execute_node` / `_get_node_inputs`）
- 证据（测试）：
  - 非法表达式触发 fail-closed：`tests/unit/domain/services/test_workflow_executor.py`
  - 语义 truth table：`tests/unit/domain/services/test_workflow_engine_edge_condition_semantics.py`

2) ✅ 模板渲染：**仅替换，不执行表达式**（fail-soft）
- 实现入口：`src/domain/services/workflow_engine.py`（`_render_config_templates` / `_render_string_templates`）
- 约束：
  - 仅支持 `{context...}` / `{initial_input...}` / `{inputN...}` 的路径替换 + 数组下标
  - 路径不存在保持原样（不抛错），并输出 debug 日志便于定位
- 证据（测试）：
  - 占位符缺失保持原样：`tests/unit/domain/services/test_workflow_engine_templating.py`
  - HTTP stub 验证渲染后 URL 命中：`tests/integration/test_workflow_engine_templating_http_stub.py`

3) ✅ 对话增量编辑：**不可越界主子图**（结构化拒绝）
- 实现入口：`src/domain/services/workflow_chat_service_enhanced.py`（`_apply_modifications`）
- 约束：
  - 仅允许 `name/position/config(_patch)/condition` 等白名单字段
  - start→end 主连通子图之外的 node/edge 更新统一拒绝，并返回 machine-readable `errors`
- 证据（测试）：
  - 越界更新拒绝：`tests/unit/domain/services/test_workflow_chat_service_enhanced_modifications.py`
  - chat update 改 config/condition 后执行结果变化：`tests/integration/test_workflow_chat_update_changes_execution.py`

## “坏输入”注入回归（fail-safe）

- 表达式非法：走 fail-closed 跳过节点（不执行风险路径）
  - `tests/unit/domain/services/test_workflow_executor.py`
- 占位符缺失：走 fail-soft 保留原样（不崩溃、不执行代码）
  - `tests/unit/domain/services/test_workflow_engine_templating.py`
