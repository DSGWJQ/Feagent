# 工作流创建链路一致性调查报告

## 结论（TL;DR）

当前代码库并不存在“纯对话创建工作流”的闭环链路：对话链路（`chat-stream`）只能**在已存在的 workflow 上做增量修改**；而“表单/接口创建工作流”链路在前后端两侧又出现了**多套客户端/路由/默认值不一致**的问题，导致“创建→编辑→对话”经常需要依赖缺失的模板入口或传入不满足 Domain 规则的 payload。

当前已将“创建”收敛为一个后端入口：**Chat-Create**（创建基底 workflow + 立即走对话规划/补全），并在前端只暴露一个入口（输入目标 → 后端返回 workflow_id → 进入编辑器/继续对话）。

---

## 现状盘点：有哪些入口/链路？

### 后端（FastAPI）

1) **表单/接口创建**：`POST /api/workflows`
- 路由：`src/interfaces/api/routes/workflows.py:322`
- UseCase：`src/application/use_cases/create_workflow.py:1`
- Domain 约束：`Workflow.create()` 要求 `nodes` 至少 1 个
  - 证据：`src/domain/entities/workflow.py:101`

2) **对话修改（SSE 流式）**：`POST /api/workflows/{workflow_id}/chat-stream`
- 路由：`src/interfaces/api/routes/chat_workflows.py:43`
- UseCase：`src/application/use_cases/update_workflow_by_chat.py:1`
- Domain Service：`src/domain/services/workflow_chat_service_enhanced.py:1`

3) **历史对话/搜索等（遗留）**：`chat_workflows_complete.py`（已移除）
- 现象：该文件定义了 `router = APIRouter(prefix="/api/workflows", ...)`，但主应用实际 include 的是 `chat_workflows.py`（见 `src/interfaces/api/main.py:196`），因此这份“Complete API”很可能**未被注册/不可达**，同时文件存在明显编码/注释乱码，属于维护风险源。

### 前端（React）

前端同时存在**两套 workflow API 客户端**，并且与后端真实路由不一致：

1) `web/src/features/workflows/api/workflowsApi.ts:28`
- 有 `createWorkflow()`（POST `/api/workflows`）
- 有 `updateWorkflow()`（PATCH `/api/workflows/{id}`）——与后端一致（`src/interfaces/api/routes/workflows.py:415`）

2) `web/src/services/api.ts:119`
- `workflows.create/list/update/delete/publish`
- 其中 `list`（GET `/workflows`）、`update`（PUT `/workflows/{id}`）、`delete`、`publish` 在后端路由层面**并不存在或方法不匹配**（后端目前只有 `GET /workflows/{id}`、`POST /workflows`、`PATCH /workflows/{id}` 等）。

此外，工作流编辑器根路由仍引用已移除的模板入口组件：
- `web/src/features/workflows/pages/WorkflowEditorPage.tsx:18` 引用 `TemplateSelector`
- 但仓库中不存在 `web/src/features/workflows/components/TemplateSelector.*`
- 这与“模板系统移除计划”文档中要求“删除 TemplateSelector 并移除引用”相矛盾：`docs/REMOVAL_PLAN_TEMPLATES_AND_PROJECT_RULES.md:1`

---

## 链路 A：表单/接口创建工作流（现状与问题）

### A1. 后端契约与 Domain 约束

- `POST /api/workflows` 会调用 `Workflow.create()` 创建实体：`src/interfaces/api/routes/workflows.py:322`
- `Workflow.create()` 明确要求 `nodes` 非空，否则抛出 `DomainError("至少需要一个节点")`
  - 证据：`src/domain/entities/workflow.py:101`

### A2. 前端请求默认值与后端约束冲突

- API DTO 中 `CreateWorkflowRequest.nodes` 默认是空列表：`src/interfaces/api/dto/workflow_dto.py:201`
- 前端 `createWorkflow()` 的入参将 `nodes/edges` 设计为可选：`web/src/features/workflows/api/workflowsApi.ts:28`
- 这意味着“表单只填 name/description”这种常见创建方式在 Domain 约束下会直接失败（除非前端显式传入至少 1 个 node）。

### A3. 多套 API 客户端导致行为漂移

- `web/src/services/api.ts:119` 这套 client 还提供 `list/update/delete/publish`，但后端未实现 → 任何依赖这套 client 的页面/功能都会出现“运行时 404/405”或“数据模型不一致”的问题。

---

## 链路 B：对话创建/修改工作流（现状与问题）

### B1. 对话链路实际上是“修改链路”

- `chat-stream` 的输入是 `{workflow_id}` + `message`：`src/interfaces/api/routes/chat_workflows.py:43`
- `UpdateWorkflowByChatUseCase` 首先 `get_by_id(workflow_id)`，不存在则 NotFound：`src/application/use_cases/update_workflow_by_chat.py:96`
- 因此对话链路无法从 0→1 创建 workflow，只能在已有 workflow 上增量改。

### B2. Domain/Agent 层具备“规划创建整张图”的能力，但仍需要载体 workflow

- Agent 决策类型包含 `create_workflow_plan`（会批量创建节点/边）：`src/domain/agents/workflow_agent.py:2297`
- 这更像“在某个现有 workflow 上一次性生成完整工作流”，仍然需要一个可保存的 workflow 实体与 workflow_id。

---

## 核心不一致点（导致“链路不一致”的根因）

1) **对话链路缺少“创建入口”**
- 对话只能修改已有 workflow；“对话创建 workflow”在产品语义上成立，但工程上缺少起点。

2) **创建契约（nodes 必须非空）与前端默认（nodes 可选/可空）冲突**
- Domain 规则强制 `nodes >= 1`，但 API/前端都允许 empty → 常见创建方式天然失败。

3) **前端存在两套 workflow API client，且与后端路由不对齐**
- `web/src/services/api.ts:119` 与后端当前实现明显漂移。

4) **模板系统移除后遗留引用**
- `WorkflowEditorPage` 根路由仍引用 `TemplateSelector`（文件不存在），导致“创建入口”在 UI 侧失效。

5) **遗留/重复路由文件增加维护成本**
- `chat_workflows_complete.py` 为旧版“Complete API”，未被 include_router；已移除以避免维护误用。

---

## 目标状态：只保留“对话创建工作流”一条链路（当前实现）

### 方案建议（推荐）

已引入“Chat-Create”入口（后端负责创建基底 workflow，并立即走对话规划）：

**API（示例契约）**
- `POST /api/workflows/chat-create/stream`
  - 入参：`{ message: string, project_id?: string, run_id?: string }`
    - `message`: 必填；服务端以 `strip()` 后判空（空/全空白视为无效）
    - `project_id`: 可选；缺省表示“未绑定项目”
    - `run_id`: 可选；空字符串/全空白视为未提供；如提供需与后续创建的 workflow 关联用于事件落库/回放
  - 行为：
     1) 在事务内创建一个“基底 workflow”（包含 start/end + 默认位置 + start->end 连接）
     2) 复用 `UpdateWorkflowByChatUseCase.execute_streaming_with_context(...)` 或等价路径，把 message 当作首次对话规划
     3) SSE 事件流中尽早返回 `workflow_id`（前端可立即路由跳转到 `/workflows/{id}/edit`）
        - 约束：第一条（或前 2 条）事件内必须包含 `metadata.workflow_id`

**前端（单一入口）**
- 首页只显示一个输入框：“描述你要的工作流”
- 提交后调用 `chat-create/stream`，拿到 workflow_id 后跳转编辑器；编辑器内继续使用 `chat-stream` 做增量修改。

### Domain 约束的处理策略（已采用）

为了让“从 0 创建”自然成立，建议选择其一（需要全局一致）：
- A) 保持 Domain 规则不变（nodes 必须非空），由 Chat-Create 在后端创建默认节点集（已采用）。

---

## 迁移路线图（建议按优先级）

1) 修复前端创建入口（阻断式问题）
- 移除 `TemplateSelector` 引用或恢复同名组件：`web/src/features/workflows/pages/WorkflowEditorPage.tsx:18`

2) 收敛前端 workflow API client
- 仅保留一套与后端对齐的 client（建议保留 `workflowsApi.ts`，淘汰/重构 `web/src/services/api.ts:119` 的 workflows 段）

3) 引入 Chat-Create 后端端点并在前端接入
- 让“创建”只发生在 chat-create；UI 删除表单创建入口（或只作为内部/测试工具保留）

4) 明确并固化“默认基底 workflow”的 shape
- 至少 1 个 node 的选择（start-only vs start+end）会影响执行器/验证器/编辑器体验，需要写入契约与测试。

---

## 建议的验收标准（DoD）

- 前端只有一个创建入口：输入目标 → 自动创建 workflow → 进入编辑器。
- 新建 workflow 无需用户填写 nodes/edges，也不会触发 “至少需要一个节点” 的 400。
- `web/src/services/api.ts` 中 workflows 相关调用不会再指向不存在的后端路由（或该 client 被移除）。
- 根路由不再引用缺失的 `TemplateSelector`，前端可正常构建/运行。
- SSE 契约：最早的 thinking 事件包含 `metadata.workflow_id`（run_id 可选），可作为 UI 跳转依据。
- 兼容/灰度：`POST /api/workflows` 暂保留用于兼容/内部调用；前端不得依赖；下线需明确 deprecate 周期与回滚路径。
- 契约测试（后端）：至少 1 条可在 CI 运行的测试覆盖「早期 workflow_id 事件」与输入校验的核心约束。
