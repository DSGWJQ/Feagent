---
type: "manual"
---

## 前端项目骨架规范（Vite + React + TypeScript + Ant Design Pro Components）

### 1. 技术栈锁定

#### 1.1 核心技术
- **构建工具**: Vite 5.x（快速开发、HMR）
- **框架**: React 18.x + TypeScript 5.x
- **UI 组件库**: Ant Design 5.x + Ant Design Pro Components
- **路由**: React Router v6
- **状态管理**: TanStack Query v5（远程状态） + React Hooks（本地状态）
- **HTTP 客户端**: axios（统一封装）
- **实时通信**: EventSource（SSE 优先）、WebSocket（可选）

#### 1.2 开发工具
- **包管理器**: pnpm（推荐）或 npm
- **代码规范**: ESLint + Prettier
- **类型检查**: TypeScript strict mode
- **测试**: Vitest（单元测试）+ Testing Library
- **Git Hooks**: husky + lint-staged

### 2. 目录结构规范

```
web/
├── public/                          # 静态资源（不经过构建）
│   └── favicon.ico
├── src/
│   ├── app/                         # 应用入口与全局配置
│   │   ├── App.tsx                  # 根组件
│   │   ├── main.tsx                 # 应用入口
│   │   ├── router.tsx               # 路由配置（集中管理）
│   │   └── providers/               # 全局 Providers
│   │       ├── QueryProvider.tsx    # TanStack Query 配置
│   │       └── ThemeProvider.tsx    # Ant Design 主题配置
│   │
│   ├── layouts/                     # 布局组件（ProLayout）
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

### 3. 命名规范

#### 3.1 文件命名
- **组件文件**: PascalCase（如 `AgentList.tsx`）
- **Hooks 文件**: camelCase，以 `use` 开头（如 `useAgents.ts`）
- **工具函数文件**: camelCase（如 `request.ts`）
- **类型文件**: camelCase（如 `agent.ts`）
- **样式文件**: kebab-case 或与组件同名（如 `agent-list.module.css`）

#### 3.2 代码命名
- **组件**: PascalCase（如 `AgentCard`）
- **函数/变量**: camelCase（如 `fetchAgents`）
- **常量**: UPPER_SNAKE_CASE（如 `API_BASE_URL`）
- **类型/接口**: PascalCase（如 `Agent`, `AgentDTO`）
- **枚举**: PascalCase，成员 UPPER_SNAKE_CASE（如 `RunStatus.RUNNING`）

#### 3.3 导入路径别名
```typescript
// tsconfig.json 配置
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"],
      "@/app/*": ["./src/app/*"],
      "@/layouts/*": ["./src/layouts/*"],
      "@/features/*": ["./src/features/*"],
      "@/shared/*": ["./src/shared/*"],
      "@/assets/*": ["./src/assets/*"]
    }
  }
}
```

### 4. 核心页面与职责

#### 4.1 Agent 管理
- **AgentList.tsx**: Agent 列表页
  - 使用 ProTable 展示 Agent 列表
  - 支持搜索、筛选、排序
  - 快速创建入口
  
- **AgentCreate.tsx**: 创建 Agent 页
  - 核心输入：起点（start）+ 目的（goal）
  - 使用 ProForm 简化表单处理
  - 一句话创建 Agent（符合核心需求）
  
- **AgentDetail.tsx**: Agent 详情页
  - 使用 ProDescriptions 展示 Agent 信息
  - 展示 start、goal、config
  - 触发运行入口
  
- **AgentEdit.tsx**: 编辑 Agent 配置页
  - 使用 ProForm 编辑 Agent 参数
  - 支持调整行为与配置

#### 4.2 运行管理
- **RunList.tsx**: 运行历史列表页
  - 使用 ProTable 展示运行记录
  - 状态筛选（PENDING/RUNNING/SUCCEEDED/FAILED/CANCELLED）
  - 跳转到运行详情
  
- **RunDetail.tsx**: 运行详情页
  - 实时日志查看（SSE）
  - 任务时间线（ProSteps）
  - 运行状态与结果展示
  
- **RunMonitor.tsx**: 运行监控页（可选）
  - 实时监控所有运行状态
  - 统计图表展示

#### 4.3 设置
- **Settings.tsx**: 设置页
  - 系统配置
  - 用户偏好设置

### 5. 路由配置规范

```typescript
// src/app/router.tsx
import { createBrowserRouter, Navigate } from 'react-router-dom';
import BasicLayout from '@/layouts/BasicLayout';
import BlankLayout from '@/layouts/BlankLayout';

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

### 6. ProComponents 集成规范

#### 6.1 核心组件使用场景

| ProComponent | 使用场景 | 示例页面 |
|-------------|---------|---------|
| **ProTable** | 列表展示、数据表格 | AgentList, RunList |
| **ProForm** | 表单创建/编辑 | AgentCreate, AgentEdit |
| **ProLayout** | 整体布局框架 | BasicLayout |
| **ProCard** | 卡片展示 | AgentCard, RunCard |
| **ProDescriptions** | 详情展示 | AgentDetail, RunDetail |
| **ProSteps** | 步骤/时间线 | TaskTimeline |
| **ProList** | 列表展示（卡片模式） | 可选的 Agent 列表视图 |

#### 6.2 ProTable 使用规范
```typescript
// 示例：AgentList.tsx
import { ProTable } from '@ant-design/pro-components';
import type { ProColumns } from '@ant-design/pro-components';

const columns: ProColumns<Agent>[] = [
  { title: 'ID', dataIndex: 'id', width: 80 },
  { title: '名称', dataIndex: 'name', ellipsis: true },
  { title: '起点', dataIndex: 'start', ellipsis: true },
  { title: '目的', dataIndex: 'goal', ellipsis: true },
  { title: '创建时间', dataIndex: 'created_at', valueType: 'dateTime' },
  { title: '操作', valueType: 'option', render: (_, record) => [...] },
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

#### 6.3 ProForm 使用规范
```typescript
// 示例：AgentCreate.tsx
import { ProForm, ProFormText, ProFormTextArea } from '@ant-design/pro-components';

<ProForm<AgentCreateDTO>
  onFinish={async (values) => {
    await createAgent(values);
    message.success('创建成功');
  }}
>
  <ProFormText name="name" label="Agent 名称" rules={[{ required: true }]} />
  <ProFormTextArea name="start" label="起点（当前状态）" rules={[{ required: true }]} />
  <ProFormTextArea name="goal" label="目的（期望结果）" rules={[{ required: true }]} />
  <ProFormTextArea name="description" label="描述" />
</ProForm>
```

### 7. API 封装规范

#### 7.1 统一响应类型
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

#### 7.2 HTTP 客户端封装
```typescript
// src/shared/utils/request.ts
import axios from 'axios';

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000,
});

// 请求拦截器
request.interceptors.request.use((config) => {
  // 添加 token 等
  return config;
});

// 响应拦截器
request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    // 统一错误处理
    return Promise.reject(error);
  }
);

export default request;
```

### 8. SSE 实时流规范

#### 8.1 useSSE Hook 封装
```typescript
// src/features/runs/hooks/useSSE.ts
import { useEffect, useState } from 'react';

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

  useEffect(() => {
    if (!enabled || !url) return;

    const eventSource = new EventSource(url);

    eventSource.onopen = () => setIsConnected(true);
    
    eventSource.onmessage = (e) => {
      if (e.data === '[DONE]') {
        eventSource.close();
        return;
      }
      const event = JSON.parse(e.data);
      setEvents((prev) => [...prev, event]);
    };

    eventSource.onerror = (e) => {
      setError(new Error('SSE connection error'));
      setIsConnected(false);
      eventSource.close();
    };

    return () => eventSource.close();
  }, [url, enabled]);

  return { events, isConnected, error };
}
```

### 9. 环境变量规范

```bash
# .env.development
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_TITLE=Agent 中台系统

# .env.production
VITE_API_BASE_URL=https://api.example.com
VITE_APP_TITLE=Agent 中台系统
```

### 10. 与 V0 美化的兼容性

#### 10.1 组件化原则
- 所有页面拆分为小粒度组件
- 组件职责单一、可复用
- 使用 ProComponents 标准组件，便于 V0 识别

#### 10.2 样式规范
- 使用 Ant Design 主题系统
- CSS 变量统一管理
- 避免内联样式，使用 CSS Modules 或 styled-components

#### 10.3 代码结构清晰
- 逻辑与 UI 分离（Hooks + Components）
- 类型定义完整
- 注释清晰，便于 AI 理解

### 11. 质量保证

#### 11.1 类型安全
- 所有 API 响应定义类型
- 组件 Props 定义类型
- 避免使用 `any`

#### 11.2 错误处理
- 使用 ErrorBoundary 捕获组件错误
- API 错误统一处理
- 用户友好的错误提示

#### 11.3 性能优化
- 路由懒加载
- 组件按需加载
- 列表虚拟滚动（长列表）

### 12. 变更控制

- 任何违反本规范的目录结构、命名、技术选型变更，必须走变更申请流程
- 本文件为前端开发的单一事实来源
- 与其他文档冲突时，以本文件为准

