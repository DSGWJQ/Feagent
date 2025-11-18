---
type: "manual"
---

## 工作流项目规则（核心要求，防偏航）

### 1. 定位与范围

- **定位**：企业内部 Agent 中台系统（对外宣传"高可用/稳定"，内部渐进式实现）。

- **核心目标**：**表单创建 + 对话/拖拽调整工作流**
  - **第一步**：用户填写表单（起点 + 终点 + 描述）
  - **第二步**：AI 自动生成最小可行工作流（Workflow）
  - **第三步**：用户通过对话或拖拽调整工作流
  - **第四步**：执行工作流，实时显示每个节点的状态

- **核心流程**：
  ```
  表单创建 → AI 生成工作流 → 对话/拖拽调整 → 执行工作流 → 状态可视化
  ```

- **非目标**：不引入多 Agent 协作（MVP 阶段）。

---

### 2. 技术栈锁定

#### 后端
- **Python 3.11+**
- **FastAPI + Pydantic v2**
- **SQLAlchemy 2.0**
- **PostgreSQL（生产）/ SQLite（开发）**
- **Alembic**（数据库迁移）
- **LangChain 1.0.5**（工作流生成、对话理解）
- **httpx**（HTTP 客户端）
- **structlog**（JSON 日志 + trace_id）
- **tenacity**（重试/超时）
- **uv**（依赖管理）
- **Ruff/Black、Pyright、pytest、pre-commit**

#### 前端
- **Vite 7.2.2**
- **React 19.2.0**
- **TypeScript 5.9.3**
- **Ant Design 5.28.1**
- **Ant Design Pro Components 2.8.10**
- **React Router v7.9.6**
- **TanStack Query v5.90.9**
- **Axios 1.13.2**
- **React Flow**（工作流可视化和拖拽编辑）
- **SSE（EventSource）**（实时状态更新）

#### 开发模式
- **强制采用 TDD（测试驱动开发）**
  - 流程：先编写测试用例 → 实现功能 → 通过测试验证需求覆盖
  - TDD + DDD 互补：DDD 定义"设计什么"，TDD 定义"如何开发"
  - Domain 层纯逻辑易测试；Application 层通过 Ports 易 Mock

---

### 3. 架构与分层（DDD-lite + 六边形 + 单体）

#### 开发顺序（强制）

1. **需求分析** → 理解业务需求（`docs/需求分析.md`）
2. **Domain 层设计** → 从业务出发，设计实体、值对象、领域服务（TDD 驱动）
3. **Ports 定义** → 定义 Repository、外部服务接口（Protocol/ABC）
4. **Infrastructure 层** → 实现 ORM 模型、Repository、外部服务适配器
5. **数据库迁移** → 使用 Alembic 生成迁移脚本
6. **Application 层** → 用例编排、事务边界
7. **API 层** → FastAPI 路由、DTO、异常映射

#### 依赖方向
- **API/Infra → Application → Domain**
- **Domain 不依赖任何框架**

#### 禁止
- ❌ 先设计数据库再设计 Domain 层（违反 DDD 原则）

#### 其他规则
- **Assembler**：DTO(Pydantic) ⇄ Domain 显式转换；DTO 不进入 Domain
- **事务边界**：仅在 Application 层开启/提交/回滚；Domain 禁止感知事务
- **命名语义**：get_/find_/exists_/check_ 含义必须遵循规范文档

---

### 4. 核心域模型与状态

#### 聚合/实体

**Workflow（工作流）**：
- `id: str`
- `name: str`
- `description: str`
- `nodes: List[Node]`
- `edges: List[Edge]`
- `status: WorkflowStatus` (draft, active, archived)
- `created_at: datetime`
- `updated_at: datetime`

**Node（节点）**：
- `id: str`
- `type: NodeType` (http, sql, script, transform)
- `name: str`
- `config: Dict[str, Any]`
- `position: Position` (x, y)

**Edge（边）**：
- `id: str`
- `source_node_id: str`
- `target_node_id: str`
- `condition: Optional[str]`

**Run（执行记录）**：
- `id: str`
- `workflow_id: str`
- `status: RunStatus` (pending, running, succeeded, failed, cancelled)
- `node_executions: List[NodeExecution]`
- `input_data: Dict[str, Any]`
- `started_at: Optional[datetime]`
- `finished_at: Optional[datetime]`

**NodeExecution（节点执行记录）**：
- `id: str`
- `run_id: str`
- `node_id: str`
- `status: NodeExecutionStatus` (pending, running, succeeded, failed, skipped)
- `input_data: Dict[str, Any]`
- `output_data: Optional[Dict[str, Any]]`
- `error_message: Optional[str]`
- `started_at: Optional[datetime]`
- `finished_at: Optional[datetime]`

#### 状态机

**WorkflowStatus**：
```
draft → active → archived
```

**RunStatus**：
```
pending → running → succeeded | failed | cancelled
```

**NodeExecutionStatus**：
```
pending → running → succeeded | failed | skipped
```

---

### 5. API 契约（强制）

#### 统一错误结构
```json
{
  "code": 4000,
  "message": "Validation error",
  "detail": {...},
  "trace_id": "abc123"
}
```

- **DomainError → 4xx**
- **InfraError → 5xx**

#### 路由

**工作流管理**：
- `POST /workflows` - 创建工作流（表单输入：start + goal + description）
- `GET /workflows` - 获取工作流列表
- `GET /workflows/{id}` - 获取工作流详情
- `PATCH /workflows/{id}` - 更新工作流（拖拽调整）
- `DELETE /workflows/{id}` - 删除工作流

**对话调整**：
- `POST /workflows/{id}/chat` - 对话式调整工作流

**执行管理**：
- `POST /workflows/{id}/runs` - 执行工作流
- `GET /workflows/{id}/runs` - 获取执行记录列表
- `GET /workflows/{id}/runs/{run_id}` - 获取执行记录详情
- `GET /workflows/{id}/runs/{run_id}/events` - SSE 实时状态更新

---

### 6. SSE 协议（实时状态更新）

#### 事件类型

**node_execution_started**：
```json
{
  "node_id": "node_1",
  "status": "running",
  "started_at": "2025-01-15T10:05:00Z"
}
```

**node_execution_completed**：
```json
{
  "node_id": "node_1",
  "status": "succeeded",
  "output_data": {...},
  "finished_at": "2025-01-15T10:05:05Z"
}
```

**node_execution_failed**：
```json
{
  "node_id": "node_1",
  "status": "failed",
  "error_message": "Connection timeout",
  "finished_at": "2025-01-15T10:05:05Z"
}
```

**run_completed**：
```json
{
  "run_id": "run_456",
  "status": "succeeded",
  "finished_at": "2025-01-15T10:05:10Z"
}
```

---

### 7. 工作流节点类型（MVP）

#### HTTP 节点
```json
{
  "type": "http",
  "config": {
    "url": "https://api.github.com/repos/{owner}/{repo}/issues",
    "method": "GET",
    "headers": {...},
    "body": {...}
  }
}
```

#### SQL 节点
```json
{
  "type": "sql",
  "config": {
    "connection_string": "postgresql://...",
    "sql": "INSERT INTO issues (title, body) VALUES (?, ?)",
    "params": [...]
  }
}
```

#### Script 节点
```json
{
  "type": "script",
  "config": {
    "language": "python",
    "code": "def transform(data): ..."
  }
}
```

#### Transform 节点
```json
{
  "type": "transform",
  "config": {
    "mapping": {
      "title": "$.issue.title",
      "body": "$.issue.body"
    }
  }
}
```

---

### 8. 前端组件规范

#### CreateWorkflowModal（创建工作流弹窗）
- **表单字段**：
  - 起点（start）：必填
  - 终点（goal）：必填
  - 描述（description）：可选
- **提交后**：跳转到工作流编辑页面

#### WorkflowEditor（工作流编辑器）
- **左侧**：工作流画布（React Flow）
  - 显示节点和边
  - 支持拖拽调整
  - 实时显示节点状态（成功/失败/运行中/未执行）
- **右侧**：对话框
  - 用户输入调整需求
  - AI 回复并更新工作流

#### NodeWithStatus（带状态的节点）
- **状态颜色**：
  - 成功：绿色 ✅
  - 失败：红色 ❌
  - 运行中：黄色 ⏳
  - 未执行：灰色 ⏸️

---

### 9. 开发优先级

#### 第一阶段：表单创建 + 工作流生成（P0）

**后端**：
- ✅ Workflow、Node、Edge 实体（TDD）
- ✅ CreateWorkflowUseCase（表单输入）
- ✅ WorkflowGeneratorChain（LangChain）
- ✅ WorkflowRepository
- ✅ API 接口

**前端**：
- ✅ TypeScript 类型定义
- ✅ API 客户端
- ✅ TanStack Query Hooks
- ✅ CreateWorkflowModal 组件
- ✅ WorkflowViewer 组件（只读，使用 React Flow）

**时间**：1-2 天

---

#### 第二阶段：对话/拖拽调整（P1）

**后端**：
- ✅ UpdateWorkflowByChatUseCase
- ✅ UpdateWorkflowByDragUseCase
- ✅ WorkflowModifierChain（LangChain）

**前端**：
- ✅ WorkflowEditor 组件（React Flow + 对话框）
- ✅ 节点拖拽
- ✅ 连线
- ✅ 节点属性编辑

**时间**：1-2 天

---

#### 第三阶段：执行工作流 + 状态可视化（P0）

**后端**：
- ✅ ExecuteWorkflowUseCase
- ✅ WorkflowExecutor（拓扑排序 + 节点执行）
- ✅ SSE 实时推送

**前端**：
- ✅ NodeWithStatus 组件
- ✅ SSE 客户端
- ✅ 实时更新节点状态

**时间**：1-2 天

---

### 10. 质量要求

#### 测试覆盖率
- **Domain 层**：100%
- **Application 层**：90%+
- **Infrastructure 层**：80%+
- **API 层**：80%+

#### 代码规范
- **Ruff/Black**：代码格式化
- **Pyright**：类型检查
- **pre-commit**：提交前检查

#### 文档要求
- **每个 Use Case**：必须有文档说明
- **每个 API**：必须有 OpenAPI 文档
- **每个组件**：必须有 JSDoc 注释

---

### 11. 禁止事项

- ❌ 不要在 Domain 层引入框架依赖
- ❌ 不要在 Application 层直接操作数据库
- ❌ 不要在 API 层编写业务逻辑
- ❌ 不要跳过测试直接实现功能
- ❌ 不要手动编辑数据库，必须使用 Alembic 迁移
- ❌ 不要在前端直接调用多个 API，使用 TanStack Query 管理
- ❌ 不要在组件中编写复杂逻辑，抽取到 Hooks 或工具函数

---

### 12. 参考文档

- `docs/需求分析.md` - 需求分析
- `docs/develop_document.md` - 开发规范
- `docs/workflow_requirements.md` - 工作流需求
- `docs/backend_changes_for_workflow.md` - 后端修改分析
- `docs/workflow_api_design.md` - API 设计（待创建）
- `docs/workflow_frontend_design.md` - 前端设计（待创建）
- `docs/workflow_implementation_plan.md` - 实现计划（待创建）
