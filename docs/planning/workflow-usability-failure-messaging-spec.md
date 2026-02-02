# Workflow 可用性失败提示规范（V0）

> 日期：2026-02-01
> 依据：`docs/planning/workflow-usability-capability-plan.md` §4（可解释性盲区）
> 目标：对齐“保存校验 / 执行事件 / 对话澄清”三条链路的失败提示，保证**可定位、可行动、可回归**。

## 0. 适用范围与非目标

**适用范围**
- Save 阶段：workflow 创建/拖拽保存/对话更新（`WorkflowSaveValidator.validate_or_raise()`）。
- Execute 阶段：执行流转（legacy engine / Runs SSE streaming）。
- Chat 阶段：无法生成可保存配置时的澄清（`intent=ask_clarification`）。

**非目标（避免过度设计）**
- 不做国际化/i18n（当前以稳定 contract 为先）。
- 不强制统一所有 DomainError 为结构化错误（先定义“应该怎么做”，逐步收敛）。

## 1. 总体原则（红队视角）

1) **Fail-closed**：宁可保存阶段拒绝，也不要让“保存通过但执行必失败”进入系统。
2) **可定位**：错误必须能定位到 `node_id/node_type`（以及具体字段 `path`）。
3) **可行动**：错误必须给出用户下一步动作（修哪个字段/提供什么依赖）。
4) **可回归**：每类错误至少有 1 条自动化测试覆盖（避免回归为“静默失败/不可解释”）。

## 2. Save 阶段（HTTP 400）结构化错误规范

### 2.1 错误载荷格式（contract）

当保存校验失败时，API 必须返回：
- HTTP status：`400`
- `detail`：结构化 dict（来自 `DomainValidationError.to_dict()`）

示例（概念结构）：

```json
{
  "detail": {
    "code": "workflow_invalid",
    "message": "Workflow validation failed",
    "errors": [
      {
        "code": "missing_model",
        "message": "model is required for textModel nodes",
        "path": "nodes[3].config.model",
        "meta": { "provider": "google" }
      }
    ]
  }
}
```

参考实现：
- `src/domain/exceptions.py:DomainValidationError`
- `src/interfaces/api/routes/workflows.py`（捕获 `DomainValidationError` → `HTTPException(detail=exc.to_dict())`）

### 2.2 `errors[]` 字段规则

- `code`：机器可读，`snake_case`，稳定不随文案变化。
- `message`：用户可读（面向 UI 展示），避免泄露内部实现细节（如堆栈、SQLAlchemy error）。
- `path`：可选但**强烈建议**；用于 UI 定位到具体表单字段。
  - 推荐路径风格：`nodes[{index}].config.{field}` / `edges[{index}].condition` / `nodes[{index}].type`
- `meta`：可选；用于“同一类错误的补充上下文”，例如：
  - `meta.provider`（unsupported provider）
  - `meta.supported_prefix`（sqlite-only）
  - `meta.incoming_sources`（多入边 promptSourceNodeId 选择）

### 2.3 UI 展示要求（最小闭环）

- **节点级聚合**：同一节点的错误需要聚合展示，并支持“一键定位/高亮该节点”。
- **字段级定位**：能解析 `path` 的错误应绑定到对应表单字段。
- **多错误展示**：一次保存可能返回多个错误；UI 不应只展示第一条。

## 3. Execute 阶段（SSE / 事件）错误与跳过规范

### 3.1 事件类型（最小集合）

执行过程至少包含：
- `node_start`
- `node_complete`
- `node_error`
- `node_skipped`（当 `edge.condition` 不满足导致跳过）

其中 `node_skipped` 的推荐 payload（与 `WorkflowEngine` 现状一致）：

```json
{
  "type": "node_skipped",
  "node_id": "node_x",
  "node_type": "httpRequest",
  "reason": "incoming_edge_conditions_not_met",
  "incoming_edge_conditions": [
    { "source_node_id": "node_cond", "condition": "false", "evaluated_to": false }
  ]
}
```

参考实现：
- `src/domain/services/workflow_engine.py`（`node_skipped`）
- 覆盖：`tests/integration/test_workflow_edge_condition_skip_event.py`

### 3.2 `node_error` 分类字段（tool 错误强制）

对于 tool 类错误（以及未来可扩展到更多 executor），SSE 的 `node_error` 必须包含：
- `error_level`（例如：`user_action_required` / `retryable` / `system_error`）
- `error_type`（例如：`tool_not_found` / `tool_deprecated` / `timeout` / `execution_error`）
- `retryable`（bool）
- `hint`（用户下一步动作）
- `message`（简要描述）

参考实现与合同测试：
- `src/domain/exceptions.py:ToolNotFoundError/ToolDeprecatedError/ToolExecutionError`
- `tests/integration/api/test_workflow_execution_error_classification.py`

兼容性要求：
- 历史事件可能没有分类字段；前端必须降级显示（至少展示 `error` 字段）。

## 4. Chat 阶段（ask_clarification）规范

当对话侧无法生成“可保存且可执行（或可解释失败）”的配置时：
- 必须返回 `intent=ask_clarification`
- `ai_message` 必须明确提出**缺失的最小信息**（不要问开放式大问题）

工具节点（tool）强制规则：
- 严禁根据工具 name 猜测 `tool_id`
- 若用户未提供可确定的 `tool_id`，必须 ask clarification

参考实现：
- `src/domain/services/workflow_chat_service_enhanced.py`（system prompt 规则）
- 覆盖：`tests/unit/domain/services/test_workflow_chat_service_enhanced.py::test_build_system_prompt_includes_tool_id_constraints_and_candidates`

## 5. 落地检查清单（用于 Code Review / 回归门禁）

- 新增/修改节点配置字段时：
  - SaveValidator 必须新增对应 `code/message/path` 校验（fail-closed）
  - 至少补 1 条 unit test 覆盖
- 新增执行语义（控制流/事件）时：
  - 必须发出可解释事件（至少包含 node_id/node_type/reason）
  - 至少补 1 条 integration test 覆盖
