# 项目开发规范（小规模 / Python / LangChain + DDD-lite + 六边形 + 单体）

本规范在参考 AgentX 的《后端开发规范》基础上，面向小规模数据分析 + 对话能力的 Python 技术栈进行了裁剪与替换，采用 LangChain 作为编排核心，强调“轻量、可测试、可替换”。

---

## 0. 总览
- 架构定位：企业内部中台系统（学习型、渐进式实现），DDD‑lite + 六边形，单体，前后端分离
- 对外宣传：高可用性、稳定性（企业级标准）
- 内部实现：最小复杂度优先，先保证核心流程可用，按需演进
- 核心能力：
  - 以结果为导向：用户输入“起点 + 目的”，系统自动创建 Agent，过程不设限
  - 任务编排与执行：用例编排、任务队列/执行器、运行状态与日志
  - 可配置：创建后可调整 Agent 行为与参数
- 主要技术：
  - 后端：Python 3.11+、FastAPI、Pydantic v2、SQLAlchemy 2.0、PostgreSQL/SQLite、structlog、tenacity、pytest、uv/Poetry
  - 编排/执行：LangChain（LCEL/Runnable/Agents），可选 LangGraph；轻量调度（asyncio + APScheduler）
  - 前端：Vite + React + TypeScript、Ant Design、TanStack Query、EventSource/WebSocket
  - 运维：Docker Compose（web + db）、pre-commit、Ruff、Pyright

---

## 1. 目录与依赖指向

```
project/
  docs/
    develop_document.md        # 本规范
  src/
    domain/                    # 领域层：实体、值对象、领域服务、Port(Protocol/ABC)
    application/               # 应用层：用例/编排、事务边界、UoW（协调 LangChain 链）
    interfaces/
      api/                     # 接口层：FastAPI 路由、DTO（Pydantic）、异常映射
    lc/                        # LangChain：chains/agents/tools/memory/retrievers
    infrastructure/            # 基础设施适配器：ORM、队列/调度、缓存/文件、外部 LLM、消息等
  web/                         # 前端（Vite + React + TS）
```

依赖方向：API/Infra → Application → Domain（Domain 不依赖框架；Ports 在 Domain/App，Adapters 在 Infra）。

---

## 2. 后端开发规范

### 2.0 开发模式：TDD（测试驱动开发）
**强烈推荐采用 TDD 开发流程：**

#### 2.0.1 TDD 核心流程
1. **编写测试用例**（Red）：
   - 先写失败的测试，明确需求与验收标准
   - 测试即文档，描述业务行为

2. **实现功能**（Green）：
   - 编写最小代码使测试通过
   - 优先实现 Domain 层（纯逻辑，易测试）

3. **重构优化**（Refactor）：
   - 测试通过后重构代码
   - 测试保证不破坏业务逻辑

#### 2.0.2 TDD + DDD 最佳实践
- **Domain 层**：
  - 纯 Python 类型，无框架依赖 → 单元测试极简
  - 测试实体/值对象的不变式、状态流转
  - 示例：`test_agent_creation()`, `test_run_state_machine()`

- **Application 层**：
  - 通过 Ports（Protocol/ABC）→ 易于 Mock 依赖
  - 测试用例编排、事务边界、幂等性
  - 示例：`test_create_agent_use_case()`, `test_idempotent_run()`

- **Infrastructure 层**：
  - 集成测试（使用测试数据库/内存队列）
  - 测试适配器实现（Repository、外部服务）

- **API 层**：
  - E2E 测试（FastAPI TestClient）
  - 测试请求/响应、错误码、SSE 流

#### 2.0.3 TDD 与 DDD 的关系
| 维度 | DDD（领域驱动设计） | TDD（测试驱动开发） |
|------|-------------------|-------------------|
| **关注点** | 设计什么（架构、领域模型） | 如何开发（开发流程、质量） |
| **层次** | 战略层面（分层、聚合边界） | 战术层面（编码实践） |
| **目标** | 模型与业务一致，降低复杂度 | 代码质量、可测试性、需求覆盖 |
| **关系** | **互补**：DDD 的分层使 TDD 更容易；TDD 验证 DDD 设计 |

#### 2.0.4 测试覆盖率要求
- **Domain 层**：≥ 80%（核心业务逻辑必须覆盖）
- **Application 层**：≥ 70%（用例编排与事务）
- **Infrastructure 层**：≥ 60%（适配器实现）
- **API 层**：核心路径 100%（创建 Agent、触发运行、SSE 流）

#### 2.0.5 测试命名规范
```python
# 测试文件：test_<module_name>.py
# 测试类：Test<ClassName>
# 测试方法：test_<scenario>_<expected_behavior>

# 示例
def test_create_agent_with_valid_start_goal_should_succeed():
    """测试：使用有效的 start 和 goal 创建 Agent 应该成功"""
    pass

def test_run_state_transition_from_pending_to_running_should_succeed():
    """测试：Run 状态从 PENDING 转换到 RUNNING 应该成功"""
    pass

def test_create_agent_without_goal_should_raise_domain_error():
    """测试：创建 Agent 时缺少 goal 应该抛出 DomainError"""
    pass
```

### 2.1 代码与风格
- 语言/工具：Python 3.11+；uv 或 Poetry 管理依赖；Ruff+Black 统一风格；Pyright 做类型检查；pytest 做单元与集成测试；pre-commit 执行 ruff/pyright/pytest 快速校验。
- 命名：模块/函数/变量使用 snake_case；类使用 PascalCase；常量 UPPER_SNAKE_CASE。
- 语义前缀：
  - get_xxx：必须存在，不存在抛 DomainError
  - find_xxx：可能返回 None
  - check_xxx_exist：仅校验，违反抛错
  - exists_xxx：返回 bool
- 文档：公开类/函数必须包含 docstring（描述、参数、返回、异常、用例）。

### 2.2 分层职责
- Domain：
  - 纯 Python 类型；实体/值对象/聚合根；在构造/方法中维护不变式（抛 DomainError）。
  - 定义 Ports（Protocol/ABC）：仓储、外部服务接口。
- Application：
  - 用例编排、权限与存在性校验、幂等键、事务边界（Unit of Work）。
  - 通过 Ports 调用基础设施，不直接依赖实现。
- Interfaces(API)：
  - FastAPI 路由；请求响应 DTO 使用 Pydantic v2；统一异常与错误码。
- Infrastructure：
  - 适配器实现 Ports：SQLAlchemy 仓储、任务队列/调度器、缓存/文件存储、LLM 客户端、消息等。

### 2.3 对象转换（Assembler）
- 规则：API ⇄ DTO(Pydantic) ⇄ Domain 实体/值对象。
- DTO 不进入 Domain；Assembler 提供 to_domain()/to_dto() 显式转换。

### 2.4 数据层规范
- 事务与元数据：PostgreSQL（或开发期 SQLite）+ SQLAlchemy 2.0；迁移使用 Alembic。
  - 严格区分 get/find/exists；通过唯一键/外键/检查约束保证一致性。
  - 建议的核心表/聚合：Agent、AgentConfig、Goal、Run、Task、TaskLog/Event（可合并为事件表）。
- 状态与日志：
  - Run/Task 采用有限状态机（PENDING → RUNNING → SUCCEEDED/FAILED/CANCELLED）
  - 事件日志采用追加写，便于追踪与重放；大字段分离存储（如文本/JSON）。

### 2.5 事务、幂等与一致性
- 事务仅在 Application 层开启/提交/回滚；Domain 侧禁止感知事务。
- 对外部调用使用重试/超时/幂等等价键；避免“先查后改”的竞争窗口，倾向直接更新 + 受影响行数判断。

### 2.6 校验（3 层 + 配置）
- API：Pydantic v2 校验格式/必填；请求体大小限制；节流与鉴权（如需）。
- Application：业务规则/权限/存在性/幂等等价键校验。
- Domain：不变式（枚举/范围/状态流转）与构造期约束。
- 配置：Pydantic Settings 校验环境变量与 Agent 参数（默认值、范围、白名单）。

### 2.7 日志、配置与安全
- 日志：structlog JSON；字段包含 trace_id、user_id、session_id、elapsed_ms；敏感信息脱敏（***）。
- 配置：Pydantic Settings；所有机密来自环境变量/密钥管理；禁止明文落库/代码库。
- 审计：对话与重要操作落审计表（时间、主体、操作、哈希）。

### 2.8 API 设计与错误
- 资源路由（示例）：
  - POST /agents            创建 Agent（输入：起点 start 与 目的 goal）
  - PATCH /agents/{id}      调整 Agent 参数/行为
  - POST /agents/{id}/runs  触发一次运行；返回 run_id
  - GET  /agents/{id}/runs  列出运行历史；GET /agents/{id}/runs/{run_id}
  - GET  /agents/{id}/runs/{run_id}/stream  SSE 推送进度/日志/[DONE]
- 错误：统一结构 {code, message, detail, trace_id}；DomainError→4xx，InfraError→5xx。

### 2.9 测试（TDD 实践）
- **测试金字塔**：Domain 单元 > Application 集成 > API/E2E；以 Run/Task/Event 为断言基准（状态流转、事件序列、SSE 终止信号）。
- **覆盖率要求**：
  - Domain 层 ≥ 80%（核心业务逻辑）
  - Application 层 ≥ 70%（用例编排）
  - Infrastructure 层 ≥ 60%（适配器）
  - API 层核心路径 100%
- **TDD 流程**：
  1. 先编写测试用例（描述需求与验收标准）
  2. 实现功能（最小代码使测试通过）
  3. 重构优化（测试保证不破坏逻辑）
- **测试类型**：
  - 单元测试：Domain 实体/值对象/领域服务
  - 集成测试：Application 用例 + Mock Ports
  - E2E 测试：FastAPI TestClient + 测试数据库
  - SSE 测试：验证事件序列、终止信号、重连
- **CI 门禁**：ruff → pyright → pytest（未通过不得合入）。

### 2.10 Git/分支/CI
- 分支：main（稳定）/dev（集成）/feature/<date>-<name>。
- Commit：type(scope): subject（feat/fix/chore/docs/refactor/test/build）。
- CI：lint → type-check → unit/integration tests → 构建镜像（可选）。

---

## 3. 前端开发规范

### 3.1 技术栈
- **构建工具**: Vite 5.x + React 18.x + TypeScript 5.x
- **UI 组件库**: Ant Design 5.x + **Ant Design Pro Components**（ProTable、ProForm、ProLayout 等）
- **路由**: React Router v6
- **数据管理**: TanStack Query v5（远程状态），React Hooks（本地状态）
- **HTTP 客户端**: axios（统一封装）
- **实时通信**: EventSource（SSE 优先）/WebSocket（可选）
- **质量工具**: ESLint + Prettier + Vitest

**重要**: 使用 Ant Design Pro Components 是为了：
1. 简化表格、表单、布局等复杂组件的开发
2. 提供统一的企业级 UI 规范
3. 便于后续使用 V0 进行识别和美化

### 3.2 目录结构（完整版）
```
web/
├── public/                          # 静态资源
│   └── favicon.ico
├── src/
│   ├── app/                         # 应用入口与全局配置
│   │   ├── App.tsx                  # 根组件
│   │   ├── main.tsx                 # 应用入口
│   │   ├── router.tsx               # 路由配置（集中管理）
│   │   └── providers/               # 全局 Providers
│   │       ├── QueryProvider.tsx    # TanStack Query Provider
│   │       └── ThemeProvider.tsx    # Ant Design 主题配置
│   │
│   ├── layouts/                     # 布局组件（使用 ProLayout）
│   │   ├── BasicLayout.tsx          # 基础布局（侧边栏+头部+内容）
│   │   ├── BlankLayout.tsx          # 空白布局（登录页等）
│   │   └── components/              # 布局相关组件
│   │       ├── Header.tsx           # 顶部导航栏
│   │       ├── Sidebar.tsx          # 侧边栏菜单
│   │       └── Footer.tsx           # 页脚
│   │
│   ├── features/                    # 业务功能模块（按领域划分）
│   │   ├── agents/                  # Agent 管理模块
│   │   │   ├── pages/               # 页面组件
│   │   │   │   ├── AgentList.tsx    # Agent 列表页（ProTable）
│   │   │   │   ├── AgentCreate.tsx  # 创建 Agent（ProForm）
│   │   │   │   ├── AgentDetail.tsx  # Agent 详情（ProDescriptions）
│   │   │   │   └── AgentEdit.tsx    # 编辑 Agent 配置
│   │   │   ├── components/          # 模块内组件
│   │   │   │   ├── AgentCard.tsx    # Agent 卡片（ProCard）
│   │   │   │   ├── AgentForm.tsx    # Agent 表单
│   │   │   │   └── StartGoalInput.tsx # 起点+目的输入组件
│   │   │   ├── hooks/               # 模块内 Hooks
│   │   │   │   ├── useAgents.ts     # Agent 列表查询
│   │   │   │   ├── useAgent.ts      # 单个 Agent 查询
│   │   │   │   ├── useCreateAgent.ts # 创建 Agent
│   │   │   │   └── useUpdateAgent.ts # 更新 Agent
│   │   │   ├── types/               # 模块内类型定义
│   │   │   │   └── agent.ts         # Agent 相关类型
│   │   │   └── api/                 # 模块内 API 封装
│   │   │       └── agentApi.ts      # Agent API 方法
│   │   │
│   │   ├── runs/                    # 运行管理模块
│   │   │   ├── pages/
│   │   │   │   ├── RunList.tsx      # 运行历史列表（ProTable）
│   │   │   │   ├── RunDetail.tsx    # 运行详情（含实时日志）
│   │   │   │   └── RunMonitor.tsx   # 运行监控页
│   │   │   ├── components/
│   │   │   │   ├── RunCard.tsx      # 运行卡片
│   │   │   │   ├── RunStatus.tsx    # 运行状态标签
│   │   │   │   ├── LogViewer.tsx    # 日志查看器（SSE）
│   │   │   │   └── TaskTimeline.tsx # 任务时间线（ProSteps）
│   │   │   ├── hooks/
│   │   │   │   ├── useRuns.ts       # 运行列表查询
│   │   │   │   ├── useRun.ts        # 单个运行查询
│   │   │   │   ├── useCreateRun.ts  # 触发运行
│   │   │   │   └── useSSE.ts        # SSE 实时流封装
│   │   │   ├── types/
│   │   │   │   └── run.ts           # Run 相关类型
│   │   │   └── api/
│   │   │       └── runApi.ts        # Run API 方法
│   │   │
│   │   └── settings/                # 设置模块
│   │       ├── pages/
│   │       │   └── Settings.tsx     # 设置页
│   │       └── components/
│   │           └── SettingsForm.tsx # 设置表单
│   │
│   ├── shared/                      # 共享资源（跨模块复用）
│   │   ├── components/              # 通用业务组件
│   │   │   ├── ErrorBoundary.tsx    # 错误边界
│   │   │   ├── Loading.tsx          # 加载组件
│   │   │   ├── Empty.tsx            # 空状态
│   │   │   └── PageHeader.tsx       # 页面头部
│   │   │
│   │   ├── hooks/                   # 通用 Hooks
│   │   │   ├── useRequest.ts        # 请求封装（基于 TanStack Query）
│   │   │   ├── useDebounce.ts       # 防抖 Hook
│   │   │   ├── useLocalStorage.ts   # 本地存储 Hook
│   │   │   └── useWebSocket.ts      # WebSocket 封装（可选）
│   │   │
│   │   ├── utils/                   # 工具函数
│   │   │   ├── request.ts           # HTTP 客户端（axios 封装）
│   │   │   ├── format.ts            # 格式化工具（日期、数字等）
│   │   │   ├── validation.ts        # 验证工具
│   │   │   └── constants.ts         # 常量定义
│   │   │
│   │   ├── types/                   # 全局类型定义
│   │   │   ├── api.ts               # API 响应类型（Result<T>）
│   │   │   ├── common.ts            # 通用类型
│   │   │   └── index.ts             # 类型导出
│   │   │
│   │   └── styles/                  # 全局样式
│   │       ├── global.css           # 全局样式
│   │       ├── variables.css        # CSS 变量
│   │       └── theme.ts             # Ant Design 主题配置
│   │
│   └── assets/                      # 资源文件
│       ├── images/                  # 图片资源
│       └── icons/                   # 图标资源
│
├── .env.development                 # 开发环境变量
├── .env.production                  # 生产环境变量
├── .eslintrc.cjs                    # ESLint 配置
├── .prettierrc                      # Prettier 配置
├── tsconfig.json                    # TypeScript 配置
├── tsconfig.node.json               # Node TypeScript 配置
├── vite.config.ts                   # Vite 配置
├── package.json                     # 依赖配置
└── README.md                        # 项目说明
```

**目录设计原则**：
- `app/`: 应用级配置，全局唯一
- `layouts/`: 布局组件，定义页面框架
- `features/`: 按业务领域划分，每个 feature 自包含（pages/components/hooks/types/api）
- `shared/`: 跨 feature 复用的资源
- `assets/`: 静态资源文件

### 3.3 代码与命名规范
- **组件**: PascalCase（如 `AgentList.tsx`）；文件与默认导出同名
- **Hooks**: camelCase，以 `use` 开头（如 `useAgents.ts`）
- **函数/变量**: camelCase（如 `fetchAgents`）
- **常量**: UPPER_SNAKE_CASE（如 `API_BASE_URL`）
- **类型/接口**: PascalCase（如 `Agent`, `AgentDTO`）
- **环境变量**: 以 `VITE_` 前缀导入；禁止在代码中硬编码密钥

**路径别名配置**：
```typescript
// tsconfig.json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"],
      "@/app/*": ["./src/app/*"],
      "@/layouts/*": ["./src/layouts/*"],
      "@/features/*": ["./src/features/*"],
      "@/shared/*": ["./src/shared/*"]
    }
  }
}
```

### 3.4 核心页面与职责

#### 3.4.1 Agent 管理
- **AgentList.tsx**: Agent 列表页
  - 使用 `ProTable` 展示 Agent 列表
  - 支持搜索、筛选、排序
  - 快速创建入口

- **AgentCreate.tsx**: 创建 Agent 页
  - **核心输入**: 起点（start）+ 目的（goal）
  - 使用 `ProForm` 简化表单处理
  - 一句话创建 Agent（符合核心需求）

- **AgentDetail.tsx**: Agent 详情页
  - 使用 `ProDescriptions` 展示 Agent 信息
  - 展示 start、goal、config
  - 触发运行入口

- **AgentEdit.tsx**: 编辑 Agent 配置页
  - 使用 `ProForm` 编辑 Agent 参数
  - 支持调整行为与配置

#### 3.4.2 运行管理
- **RunList.tsx**: 运行历史列表页
  - 使用 `ProTable` 展示运行记录
  - 状态筛选（PENDING/RUNNING/SUCCEEDED/FAILED/CANCELLED）
  - 跳转到运行详情

- **RunDetail.tsx**: 运行详情页
  - 实时日志查看（SSE）
  - 任务时间线（`ProSteps`）
  - 运行状态与结果展示

### 3.5 路由配置规范

```typescript
// src/app/router.tsx
import { createBrowserRouter, Navigate } from 'react-router-dom';
import BasicLayout from '@/layouts/BasicLayout';

// Agent 相关页面
import AgentList from '@/features/agents/pages/AgentList';
import AgentCreate from '@/features/agents/pages/AgentCreate';
import AgentDetail from '@/features/agents/pages/AgentDetail';
import AgentEdit from '@/features/agents/pages/AgentEdit';

// Run 相关页面
import RunList from '@/features/runs/pages/RunList';
import RunDetail from '@/features/runs/pages/RunDetail';

// 设置页面
import Settings from '@/features/settings/pages/Settings';

const router = createBrowserRouter([
  {
    path: '/',
    element: <BasicLayout />,
    children: [
      {
        index: true,
        element: <Navigate to="/agents" replace />,
      },
      {
        path: 'agents',
        children: [
          { index: true, element: <AgentList /> },
          { path: 'create', element: <AgentCreate /> },
          { path: ':id', element: <AgentDetail /> },
          { path: ':id/edit', element: <AgentEdit /> },
          {
            path: ':id/runs',
            children: [
              { index: true, element: <RunList /> },
              { path: ':runId', element: <RunDetail /> },
            ],
          },
        ],
      },
      {
        path: 'settings',
        element: <Settings />,
      },
    ],
  },
]);

export default router;
```

**路由设计原则**：
- 使用嵌套路由，结构清晰
- 路径与业务领域对应
- 支持动态参数（`:id`, `:runId`）

### 3.6 ProComponents 集成规范

#### 3.6.1 核心组件使用场景

| ProComponent | 使用场景 | 示例页面 |
|-------------|---------|---------|
| **ProTable** | 列表展示、数据表格 | AgentList, RunList |
| **ProForm** | 表单创建/编辑 | AgentCreate, AgentEdit |
| **ProLayout** | 整体布局框架 | BasicLayout |
| **ProCard** | 卡片展示 | AgentCard, RunCard |
| **ProDescriptions** | 详情展示 | AgentDetail, RunDetail |
| **ProSteps** | 步骤/时间线 | TaskTimeline |

#### 3.6.2 ProTable 使用示例
```typescript
// AgentList.tsx
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';

const columns: ProColumns<Agent>[] = [
  { title: 'ID', dataIndex: 'id', width: 80 },
  { title: '名称', dataIndex: 'name', ellipsis: true },
  { title: '起点', dataIndex: 'start', ellipsis: true },
  { title: '目的', dataIndex: 'goal', ellipsis: true },
  { title: '创建时间', dataIndex: 'created_at', valueType: 'dateTime' },
  {
    title: '操作',
    valueType: 'option',
    render: (_, record) => [
      <a key="view" href={`/agents/${record.id}`}>查看</a>,
      <a key="edit" href={`/agents/${record.id}/edit`}>编辑</a>,
    ]
  },
];

<ProTable<Agent>
  columns={columns}
  request={async (params) => {
    const data = await fetchAgents(params);
    return { data: data.items, total: data.total, success: true };
  }}
  rowKey="id"
  search={{ labelWidth: 'auto' }}
  pagination={{ pageSize: 10 }}
/>
```

#### 3.6.3 ProForm 使用示例
```typescript
// AgentCreate.tsx
import { ProForm, ProFormText, ProFormTextArea } from '@ant-design/pro-components';

<ProForm<AgentCreateDTO>
  onFinish={async (values) => {
    await createAgent(values);
    message.success('创建成功');
    navigate('/agents');
  }}
>
  <ProFormText
    name="name"
    label="Agent 名称"
    rules={[{ required: true, message: '请输入 Agent 名称' }]}
  />
  <ProFormTextArea
    name="start"
    label="起点（当前状态）"
    placeholder="描述当前的起点状态..."
    rules={[{ required: true, message: '请输入起点' }]}
  />
  <ProFormTextArea
    name="goal"
    label="目的（期望结果）"
    placeholder="描述期望达到的目标..."
    rules={[{ required: true, message: '请输入目的' }]}
  />
  <ProFormTextArea
    name="description"
    label="描述"
    placeholder="可选的补充描述..."
  />
</ProForm>
```

### 3.7 数据与状态管理

#### 3.7.1 远程状态（TanStack Query）
```typescript
// src/features/agents/hooks/useAgents.ts
import { useQuery } from '@tanstack/react-query';
import { fetchAgents } from '../api/agentApi';

export function useAgents(params?: AgentQueryParams) {
  return useQuery({
    queryKey: ['agents', params],
    queryFn: () => fetchAgents(params),
    staleTime: 5 * 60 * 1000, // 5 分钟
  });
}

// src/features/agents/hooks/useCreateAgent.ts
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createAgent } from '../api/agentApi';

export function useCreateAgent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createAgent,
    onSuccess: () => {
      // 刷新 Agent 列表
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });
}
```

#### 3.7.2 本地状态（React Hooks）
- 组件内使用 `useState`/`useReducer`
- 避免引入全局状态库（Redux/Zustand），除非明确需要
- 状态提升到最近的共同父组件

### 3.8 API 封装规范

#### 3.8.1 统一响应类型
```typescript
// src/shared/types/api.ts
export interface Result<T = any> {
  code: number;
  message: string;
  data?: T;
  detail?: string;
  trace_id?: string;
}

export interface PageResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
```

#### 3.8.2 HTTP 客户端封装
```typescript
// src/shared/utils/request.ts
import axios from 'axios';
import type { Result } from '@/shared/types/api';

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000,
});

// 请求拦截器
request.interceptors.request.use((config) => {
  // 添加 token 等
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器
request.interceptors.response.use(
  (response) => {
    const result: Result = response.data;
    if (result.code !== 2000) {
      // 统一错误处理
      message.error(result.message || '请求失败');
      return Promise.reject(new Error(result.message));
    }
    return result.data;
  },
  (error) => {
    // 网络错误处理
    message.error(error.message || '网络错误');
    return Promise.reject(error);
  }
);

export default request;
```

#### 3.8.3 API 方法封装
```typescript
// src/features/agents/api/agentApi.ts
import request from '@/shared/utils/request';
import type { Agent, AgentCreateDTO, AgentUpdateDTO } from '../types/agent';
import type { PageResult } from '@/shared/types/api';

export async function fetchAgents(params?: any): Promise<PageResult<Agent>> {
  return request.get('/agents', { params });
}

export async function fetchAgent(id: string): Promise<Agent> {
  return request.get(`/agents/${id}`);
}

export async function createAgent(data: AgentCreateDTO): Promise<Agent> {
  return request.post('/agents', data);
}

export async function updateAgent(id: string, data: AgentUpdateDTO): Promise<Agent> {
  return request.patch(`/agents/${id}`, data);
}
```

### 3.9 SSE 实时流规范

#### 3.9.1 useSSE Hook 封装
```typescript
// src/features/runs/hooks/useSSE.ts
import { useEffect, useState, useRef } from 'react';

export interface SSEEvent {
  event: string;
  data: any;
  ts: string;
  run_id: string;
  seq: number;
}

export function useSSE(url: string, enabled: boolean = true) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!enabled || !url) return;

    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    eventSource.onmessage = (e) => {
      if (e.data === '[DONE]') {
        eventSource.close();
        setIsConnected(false);
        return;
      }

      try {
        const event: SSEEvent = JSON.parse(e.data);
        setEvents((prev) => [...prev, event]);
      } catch (err) {
        console.error('Failed to parse SSE event:', err);
      }
    };

    eventSource.onerror = (e) => {
      setError(new Error('SSE connection error'));
      setIsConnected(false);
      eventSource.close();
    };

    return () => {
      eventSource.close();
      eventSourceRef.current = null;
    };
  }, [url, enabled]);

  const close = () => {
    eventSourceRef.current?.close();
    setIsConnected(false);
  };

  return { events, isConnected, error, close };
}
```

#### 3.9.2 LogViewer 组件示例
```typescript
// src/features/runs/components/LogViewer.tsx
import { useSSE } from '../hooks/useSSE';

export function LogViewer({ runId }: { runId: string }) {
  const { events, isConnected, error } = useSSE(
    `/agents/${agentId}/runs/${runId}/stream`,
    true
  );

  return (
    <div>
      <div>状态: {isConnected ? '连接中' : '已断开'}</div>
      {error && <div>错误: {error.message}</div>}
      <div>
        {events.map((event, index) => (
          <div key={index}>
            [{event.ts}] {event.event}: {JSON.stringify(event.data)}
          </div>
        ))}
      </div>
    </div>
  );
}
```

### 3.10 环境变量规范

```bash
# .env.development
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_TITLE=Agent 中台系统

# .env.production
VITE_API_BASE_URL=https://api.example.com
VITE_APP_TITLE=Agent 中台系统
```

**使用方式**：
```typescript
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;
```

### 3.11 与 V0 美化的兼容性

为了便于后续使用 V0 进行识别和美化，需要遵循以下原则：

#### 3.11.1 组件化原则
- 所有页面拆分为小粒度组件
- 组件职责单一、可复用
- 使用 ProComponents 标准组件，便于 V0 识别

#### 3.11.2 样式规范
- 使用 Ant Design 主题系统
- CSS 变量统一管理
- 避免内联样式，使用 CSS Modules 或 styled-components

#### 3.11.3 代码结构清晰
- 逻辑与 UI 分离（Hooks + Components）
- 类型定义完整
- 注释清晰，便于 AI 理解

### 3.12 测试与构建
- 单测覆盖关键 hooks/组件（mock SSE/WS）
- E2E 可用 Playwright（可选）
- 构建产物通过 Nginx 或 Vite preview 提供静态资源
- 与后端在 Docker Compose 联调

---

## 4. Agent 协议与接口约定

### 4.1 核心约束
- 用户必须提供：起点 start（当前状态/输入）与 目的 goal（期望结果）
- 结果导向：不限制过程，系统基于 start+goal 自动生成初始 Agent
- 创建后可调整：用户可编辑 Agent 行为与参数（工具开关、并发、重试等）

### 4.2 REST
- POST /agents
  - 请求：{ name?, start: {...}, goal: {...}, description? }
  - 响应：{ id, name, start, goal, config, created_at }
- PATCH /agents/{id}
  - 请求：{ config 部分字段更新 }
- POST /agents/{id}/runs
  - 请求：{ input? }（可选运行时输入）
  - 响应：{ run_id, status }
- GET  /agents/{id}/runs/{run_id}
  - 响应：{ status, result?, error?, started_at, finished_at }

### 4.3 SSE（推荐）
- GET /agents/{id}/runs/{run_id}/stream
  - 头：text/event-stream
  - data: {"event":"task_started","task_id": "..."} / {"event":"log","msg":"..."} / {"event":"done"}

### 4.4 WebSocket（可选）
- /ws/agents/{id}/runs/{run_id}
  - 心跳 ping/pong；消息体同 SSE 事件

### 4.4 错误码（示例）
- 2000 OK；4001 参数错误；4004 资源不存在；4090 幂等冲突；5000 系统错误；5001 依赖异常。

---

## 5. 高可用与稳定性（简化）
- 架构：API 无状态；数据库为事实来源；执行器与 API 解耦（同进程优先，后续可外置）
- 重试与超时：tenacity 指数退避；外部依赖设置超时
- 幂等：以 agent_id/run_id/请求幂等等价键避免重复执行
- 限流与并发：按 Agent/全局维度限流与并发上限
- 健康检查：/healthz；/readiness
- 可观测性：结构化日志 + trace_id；核心指标（执行数、成功率、P95 时延）

---

## 6. 安全与合规
- 所有机密通过环境变量/密钥管理注入；日志与数据库中敏感字段脱敏/哈希。
- 统一 CORS 策略；请求速率限制（如需公开服务）。

---

## 7. 里程碑与验收
1) 初始化骨架与 CI（后端/前端）
2) 核心闭环：创建 Agent（start+goal）→ Application 调用 LangChain 链执行 → SSE 实时输出 → 保存状态与结果
3) 配置界面：前端可视化调整 Agent 行为与参数
4) 稳定性基线：重试/超时/幂等/限流/健康检查
5) 文档与对外表述：企业级能力对外宣传，内部采用渐进式实现路线

---

## 8. 附：命名词汇映射（Java → Python）
- Controller → Router (FastAPI)
- Service(App) → Application UseCase
- Entity/Aggregate → dataclass/typing + 领域服务
- Repository (Port) → Protocol/ABC；Adapter 用 SQLAlchemy/队列/缓存 实现
- DTO → Pydantic Model
- @Validated → Pydantic 校验
- Wrapper/MyBatis → SQLAlchemy ORM/Core



---

## 9. 设计准则（与《需求分析.md》一致）

### 9.1 是否通过对话构造工作流？
- 默认不采用对话式构造；采用“自动计划 + 最小澄清”（仅在不确定时触发）。
- 何时启用：目标复杂/信息不足/失败多次、用户希望介入、需额外权限/验收。
- 产出形态：优先线性计划（3–7 步），必要时微型 DAG；执行前可选“计划确认”。

### 9.2 当前模型能力与护栏
- 能力：结构化提取 start/goal/config（严格 JSON）、轻量计划、有限工具调用（HTTP/SQL/脚本）、状态与日志、基于验收标准判定。
- 护栏：严格 JSON+schema、工具白名单、超时/重试（tenacity）、幂等等价键、预算早停、统一错误码、SSE 结构化事件（trace_id）。

### 9.3 开源 Agent 方法对比（何时使用）
- ReAct+Tools：MVP/少量工具/快速试验。
- Plan-and-Execute：可控性更好，成本较高。
- 图/状态机编排（LangGraph/CrewAI）：条件/并行/回溯/循环场景。
- 多 Agent 协作：不作为起步方案。
- 本项目：start+goal → 线性计划 → 执行 → 可调整配置（优势：门槛低、易测、可渐进升级；劣势：高级能力需后续演进）。

### 9.4 改进建议与演进路径
- 澄清器（1–3 个关键问题）、验收标准、线性计划+小步重试（限制上限）。
- 人在回路（可选计划确认/禁用工具/预算）、工具收敛（3–5 稳定工具）。
- 安全网：幂等、超时/重试/限流、健康检查、结构化日志+trace_id、统一错误码。
- 升级路径：线性 → 条件/并行 → 简易图（LangGraph 思路） → 可视化编排器。
