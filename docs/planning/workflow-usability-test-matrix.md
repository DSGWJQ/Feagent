# Workflow 补测矩阵（P0/P1/P2）

> 日期：2026-02-01
> 依据：`docs/planning/workflow-usability-capability-plan.md` §4
> 验收口径：以“编辑器工作流链路（体系 B）”为准：`NodeType + ExecutorRegistry + WorkflowSaveValidator + WorkflowEngine + UI`。
> 当前约束：**仅支持 sqlite**；模型类节点（`textModel/embeddingModel/imageGeneration/audio/structuredOutput`）当前仅承诺 **OpenAI provider**（fail-closed）。

## 0. 使用说明

- **优先级定义**
  - P0：阻塞可用性闭环（保存必失败 / 执行必失败 / 无法定位原因）
  - P1：不阻塞跑通，但影响边界结论/可用性体验（提示不清、边界未覆盖）
  - P2：结构性治理（减少硬编码与口径漂移）
- **覆盖标准**：至少存在 1 条可稳定回归的自动化测试（unit/integration/e2e/frontend 任一），并能断言“期望/失败模式/可解释性要求”。
- **可解释性最低要求**（fail-fast + 可定位）：
  - Save 阶段：`DomainValidationError.detail.errors[]` 必须包含 `code/message/path`（必要时 `meta`）。
  - Execute 阶段：SSE 的 `node_error` / `node_skipped` 必须至少包含 `node_id/node_type` 与可行动的 `hint/原因`（tool 相关错误必须包含分类字段）。

## 1. P0 补测矩阵（已覆盖/门禁）

| 维度 | 场景 | 期望 | 失败模式 | 可解释性要求 | 覆盖（测试入口） | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 配置 | structuredOutput.schema 必填 | 保存通过（schema 为 object 或 JSON string） | 缺 schema / schemaName | 返回 `missing_schema`/`missing_schema_name` + 字段 path | `tests/unit/domain/services/test_workflow_save_validator.py::test_validator_rejects_structured_output_missing_schema_fields` | DONE |
| 配置 | structuredOutput.schema JSON 解析 | schema 为 string 时可解析 | invalid JSON | 返回 `invalid_json` + 字段 path | `tests/unit/domain/services/test_workflow_save_validator.py::test_validator_rejects_structured_output_schema_when_json_is_invalid` | DONE |
| 依赖 | database 仅 sqlite | 非 sqlite 保存必拒绝 | mysql/postgres URL | 返回 `unsupported_database_url` + meta.supported_prefix | `tests/unit/domain/services/test_workflow_save_validator.py::test_validator_rejects_database_url_when_not_sqlite` | DONE |
| Drift | textModel provider 收敛 | 非 openai 保存必拒绝 | `google/*` / `anthropic/*` | 返回 `unsupported_model_provider` + meta.provider | `tests/unit/domain/services/test_workflow_save_validator.py::test_validator_rejects_text_model_when_provider_is_not_openai` | DONE |
| Drift | textModel 无前缀非 OpenAI | 识别明显非 OpenAI 的模型族并拒绝 | `claude-*` / `gemini-*` | 返回 `unsupported_model` | `tests/unit/domain/services/test_workflow_save_validator.py::test_validator_rejects_text_model_when_model_looks_like_non_openai_without_prefix` | DONE |
| Drift | embeddingModel provider 收敛 | 非 openai 保存必拒绝 | `cohere/*` 等 | 返回 `unsupported_model_provider` + meta.provider | `tests/unit/domain/services/test_workflow_save_validator.py::test_validator_rejects_embedding_model_when_provider_is_not_openai` | DONE |
| Drift | imageGeneration Gemini 防绕过 | Gemini 模型族保存必拒绝 | `gemini-*` | 返回 `unsupported_model` | `tests/unit/domain/services/test_workflow_save_validator.py::test_validator_rejects_image_generation_when_model_is_gemini_family` | DONE |
| Drift | structuredOutput provider 收敛 | 非 openai 保存必拒绝 | `anthropic/*` | 返回 `unsupported_model_provider` + meta.provider | `tests/unit/domain/services/test_workflow_save_validator.py::test_validator_rejects_structured_output_when_provider_is_not_openai` | DONE |
| 口径 | Chat supported nodes 与 UI 对齐 | prompt 必包含 UI 节点集合与 OpenAI-only 约束 | 对话可表达但不可生成 | prompt 规则明确列出支持节点 + 约束 | `tests/unit/domain/services/test_workflow_chat_service_enhanced.py::test_build_system_prompt_includes_ui_supported_node_types_and_model_constraints` | DONE |
| UI | textModel 模型下拉无误导项 | UI 不展示 anthropic/google 选项 | 误导用户保存必败配置 | UI 仅暴露 OpenAI 选项 | `web/src/features/workflows/components/__tests__/NodeConfigPanel.test.tsx` | DONE |
| UI | imageGeneration 无 Gemini 选项 | UI 不展示 Gemini 图片模型 | 误导用户保存必败配置 | UI 仅暴露 OpenAI 选项 | `web/src/features/workflows/components/__tests__/NodeConfigPanel.test.tsx` | DONE |
| 控制流 | conditional 分支 gating | 仅执行 true/false 对应分支 | 两分支都执行/都不执行 | execution_log 可证明执行路径 | `tests/integration/test_workflow_condition_gating.py` | DONE |
| 控制流 | edge.condition=false 时跳过节点并发事件 | 节点不执行且发出 `node_skipped` | 静默跳过导致不可解释 | `node_skipped` 含 reason + incoming_edge_conditions | `tests/integration/test_workflow_edge_condition_skip_event.py` | DONE |
| 渲染 | httpRequest 模板渲染 | request 前完成 `{input1.*}` 渲染 | 未渲染导致请求错 | assert 实际 url/headers/body 已渲染 | `tests/integration/test_workflow_engine_templating_http_stub.py` | DONE |
| API | 保存校验结构化错误 | 400.detail 为结构化 dict | 返回纯 string 导致 UI 无法定位 | `detail.code` + `detail.errors[]` | `tests/integration/api/workflows/test_workflow_validation_contract.py::test_drag_update_returns_structured_validation_error` | DONE |
| SSE | Tool 错误分类字段 | node_error 必含 classification fields | 前端无法判定 retry/hint | `error_level/error_type/retryable/hint/message` | `tests/integration/api/test_workflow_execution_error_classification.py` | DONE |
| SSE | error 后必须 [DONE] 结束 | ERROR 后 <1s 内发送 `[DONE]` 并结束连接 | 30s 超时/二次 SSE_ERROR | SSE event 序列可断言（包含 error + DONE） | `tests/integration/api/test_sse_emitter_handler_end_semantics.py; tests/integration/api/workflow_chat/test_chat_create_stream_api.py::test_llm_error_emits_sse_error_event_and_deletes_base_workflow` | DONE |
| Runs | Run 创建失败 fail-closed | Run 创建失败/缺 projectId 时不触发 execute/stream | UI 误导“降级”但后端 400 | 前端明确提示且 `executeWorkflowStreaming` 不被调用 | `web/src/features/workflows/pages/__tests__/WorkflowRunFailClosed.test.tsx` | DONE |
| Runs | Runs gate（后端一致性） | Runs 开启缺 run_id → 400；Runs 关闭 → legacy 不因缺 run_id 失败 | 缺 run_id 仍走 execute 导致 drift | 错误信息稳定可解释 | `tests/integration/api/workflows/test_execute_stream_validation_gate.py` | DONE |
| deterministic | enable_test_seed_api 下不触网 | 无 key 且 enable_test_seed_api=true → 必选 deterministic stub | 隐式触网/非 deterministic | 分支选择可测试断言 | `tests/unit/interfaces/api/test_workflow_chat_llm_selection.py` | DONE |
| 兼容 | legacy key normalize | 保存前 normalize 为 canonical shape | 历史数据导致 drift/执行必败 | 保存后 shape 稳定可预期 | `tests/unit/domain/services/test_workflow_save_validator.py::test_validator_normalizes_http_path_to_url_before_persisting_shape` | DONE |
| 兼容 | toolId -> tool_id normalize | 保存前 normalize | 旧字段落库 | 保存后只保留 `tool_id` | `tests/unit/domain/services/test_workflow_save_validator.py::test_validator_normalizes_tool_id_from_toolId_before_persisting_shape` | DONE |
| 兼容 | loop for/iterations normalize | 保存前 normalize 到 `range/end` | 旧 UI 导入执行必败 | 保存后只保留 canonical | `tests/unit/domain/services/test_workflow_save_validator.py::test_validator_normalizes_loop_for_to_range_and_moves_iterations_to_end` | DONE |

## 2. P1 补测矩阵（建议补齐）

| 维度 | 场景 | 期望 | 失败模式 | 可解释性要求 | 覆盖（测试入口） | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 体验 | textModel 多入边 promptSourceNodeId 不存在 | 保存必拒绝 | promptSourceNodeId 指向非入边 | 返回 `invalid_prompt_source` + meta.incoming_sources | `tests/unit/domain/services/test_workflow_save_validator.py::test_validator_rejects_text_model_when_prompt_source_node_id_not_in_incoming_sources` | DONE |
| 依赖 | tool_repository 未注入 | 保存必拒绝 | tool_repository=None | 返回 `tool_repository_unavailable` | `tests/unit/domain/services/test_workflow_save_validator.py::test_validator_rejects_tool_node_when_tool_repository_is_unavailable_fail_closed` | DONE |
| 节点 | notification(webhook/slack/email) 字段校验 | 保存必拒绝缺必填字段 | 缺 recipients/url 等 | 返回具体缺失字段 code + path | `tests/unit/domain/services/test_workflow_save_validator.py::test_validator_rejects_notification_webhook_missing_url_and_message; tests/unit/domain/services/test_workflow_save_validator.py::test_validator_rejects_notification_email_missing_required_fields` | DONE |
| 控制流 | loop(for_each) 空集合 | 执行成功并输出空列表 | 抛错/返回 None | execution_log 与 output 清晰可断言 | `tests/integration/test_workflow_p1_edge_cases.py::test_loop_for_each_empty_collection_returns_empty_list` | DONE |
| 文件 | file.read 不存在 | 执行失败且定位到 path | 静默返回空 | node_error 含 node_id/node_type，且 error 包含 path | `tests/integration/test_workflow_p1_edge_cases.py::test_file_read_missing_file_emits_node_error_event` | DONE |
| 口径 | draft 保存策略（非主连通子图） | 允许保存“进行中草稿”（非主子图节点不阻断保存） | 草稿被强校验阻断 | main start->end 子图仍 fail-closed；非主子图可 in-progress | `tests/unit/domain/services/test_workflow_save_validator.py::test_validator_allows_draft_to_contain_incomplete_tool_node_outside_main_subgraph` | DONE |
| UI | enum unknown value fail-closed | 节点已有 enum 值不在 allowed 时提示并禁止保存 | UI 变空/误导/静默保存失败 | 必须显式提示“unsupported”并阻止 onSave | `web/src/features/workflows/components/__tests__/NodeConfigPanel.test.tsx` | DONE |
| Domain | chat 防止孤立节点（新增未连通） | chat 修改不得产生不可达节点 | 新增节点未连通导致后续 chat 看不见/删不掉 | 返回 `workflow_modification_rejected` + nodes 列表 | `tests/unit/domain/services/test_workflow_chat_service_enhanced_modifications.py::test_apply_modifications_rejects_nodes_to_add_outside_main_subgraph` | DONE |
| UI | 一键清理未连通节点 | 删除非 start->end 主连通子图节点+相关边并保存 | 历史孤立节点无法修复 | 清理后调用 updateWorkflow 且 payload 不含孤立节点 | `web/src/features/workflows/pages/__tests__/WorkflowCleanupUnreachableNodes.test.tsx` | DONE |

## 3. P2（长期治理 / 防漂移）

| 维度 | 场景 | 目标 | 覆盖建议 | 状态 |
| --- | --- | --- | --- | --- |
| 架构 | capabilities endpoint | UI/对话/文档从同一份能力事实源渲染 | 新增 `/api/workflows/capabilities` + 合同测试（`tests/integration/api/workflows/test_workflow_capabilities_api.py`） | DONE |
