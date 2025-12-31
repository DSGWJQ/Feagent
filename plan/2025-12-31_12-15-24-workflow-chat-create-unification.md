---
mode: plan
cwd: D:\My_Project\agent_data
task: unify workflow creation to chat-create only
complexity: complex
planning_method: builtin
created_at: 2025-12-31T12:15:39.2560557+08:00
---

# Plan: Unify Workflow Creation to Chat-Create Only


8. 测试与回归：
   - 后端：为 chat-create/stream 增加路由/事件契约测试（至少覆盖：成功创建、输入为空、LLM 不可用/报错、run_id 落库可选）。
   - 前端：补齐首页“对话创建→跳转编辑器”e2e 或集成测试；确保不再依赖不存在的模板组件。
   - 回归关键链路：创建→对话改图→拖拽保存→执行（SSE）。
9. 清理与文档：
   - 删除/隔离未注册或乱码的遗留路由文件（例如 `chat_workflows_complete.py`）或明确其不可达状态，避免维护误用。
   - 更新 README/架构文档，记录唯一创建链路与 API 契约。
10. 发布与回滚策略：
   - 先灰度：保留旧 `POST /api/workflows`，前端切到 chat-create；观察日志/监控后再决定下线旧端点。
   - 回滚：前端入口可临时切回旧 create（若保留），后端 chat-create 可关闭但不影响既有 workflow 编🎯 任务概述
当前“创建工作流”存在多条链路与契约漂移（创建 API 与 Domain 约束冲突、前端多套 API client、模板入口遗留引用、对话只能修改不能创建）。目标是将“创建”统一收敛为“对话创建”一条链路：前端只提供一个入口，后端提供一个 chat-create 端点，负责创建基底 workflow 并立即进入对话规划/补全。

📋 执行计划
1. 固化目标契约与 DoD：确定“对话创建”交互（输入目标→返回 workflow_id→进入编辑器）与事件契约（SSE 事件中尽早返回 workflow_id）。
   - chat-create/stream 输入：`{ message: string, project_id?: string, run_id?: string }`
     - message 必填；服务端以 `strip()` 后判空（空/全空白视为无效）
     - project_id 可选；缺省表示“未绑定项目”
     - run_id 可选；空字符串/全空白视为未提供
   - SSE 契约：第一条（或前 2 条）事件内必须包含 `metadata.workflow_id`（run_id 可选）
   - 兼容策略：`POST /api/workflows` 暂保留用于兼容/内部调用；前端不得依赖；按灰度策略明确 deprecate 周期与回滚路径后再下线
2. 修复前端阻断入口：移除/替换根路由对 `TemplateSelector` 的引用，确保首页可进入“对话创建”入口页面；同时清理菜单中已失效的“项目规则”入口（若仍存在）。
3. 收敛前端 API client：在 `web/src` 内统一使用一套与后端对齐的 workflow client（保留 `PATCH /api/workflows/{id}` 与 `POST /api/workflows/{id}/chat-stream`；删除或改造 `web/src/services/api.ts` 里与后端不匹配的 `list/update/delete/publish` 调用）。
4. 设计并实现后端 Chat-Create SSE 端点：
   - 新增 `POST /api/workflows/chat-create/stream`（或等价命名），输入 `{ message, project_id?, run_id? }`。
   - 端点在事务内创建“基底 workflow”（至少 1 个合法 node），然后复用现有 `UpdateWorkflowByChatUseCase.execute_streaming_with_context(...)` 走首次对话规划。
   - 在事件流中尽早发出包含 `workflow_id` 的事件（便于前端立即跳转）。
5. 统一“基底 workflow”形状：明确默认 nodes/edges（建议 `start`→`end`，并提供默认 position/config），保证满足 `Workflow.create()` 的 “至少一个节点” 约束，并减少后续 chat 规划的修复成本。
6. 前端接入 Chat-Create：实现首页“对话创建”表单（输入目标，调用 chat-create/stream），拿到 workflow_id 后导航到 `/workflows/{id}/edit`，编辑器内继续使用现有 `chat-stream` 增量修改。
7. 逐步下线旧创建链路：
   - UI 层移除“表单创建工作流”入口（若存在），或将其标注为内部调试功能并默认隐藏。
   - 后端 `POST /api/workflows` 保留与否按 Step 1 决策执行：保留则限制用途并补齐默认 nodes；下线则在文档与前端彻底移除引用，并提供迁移期兼容提示。辑/执行。

🧠 关键取舍/假设
- 优先选择“新增 chat-create 端点”而不是放宽 Domain 规则（允许空 nodes），以避免牵连执行器/编辑器/校验链路的广泛假设。
- 前端 API client 必须收敛到与后端路由一致，否则会持续出现 404/405 和数据结构漂移。
- “模板入口”已移除，应彻底从路由与页面依赖中剔除，避免阻断创建入口。

⚠️ 风险与注意事项
- SSE 事件契约变更风险：前端需要兼容新增的“包含 workflow_id 的早期事件”，避免解析失败导致创建卡死。
- 事务与落库边界：chat-create 同时包含“创建 workflow”与“对话规划更新 workflow”，需要明确失败回滚语义（创建成功但规划失败时是否保留草稿）。
- 兼容性：若外部仍调用 `POST /api/workflows`，贸然下线会破坏集成；建议灰度与明确 deprecate 周期。
- 多处遗留入口：菜单/测试/Mock API 可能仍引用旧链路，需要系统性 grep 清理并补齐测试。

📎 参考
- `Report.md:1`
- `src/interfaces/api/routes/workflows.py:322`
- `src/domain/entities/workflow.py:101`
- `src/interfaces/api/routes/chat_workflows.py:43`
- `src/application/use_cases/update_workflow_by_chat.py:1`
- `web/src/features/workflows/pages/WorkflowEditorPage.tsx:18`
- `web/src/services/api.ts:119`
