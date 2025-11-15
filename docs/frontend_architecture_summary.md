# 前端项目骨架设计总结

## 📋 概述

本文档总结了 Agent 中台系统前端项目的完整骨架设计，包括技术选型、目录结构、核心页面、路由配置和开发规范。

## 🎯 设计目标

1. **技术栈现代化**: 使用 Vite + React + TypeScript + Ant Design Pro Components
2. **结构清晰**: 按业务领域划分，模块自包含
3. **易于维护**: 组件化、类型安全、代码规范统一
4. **便于美化**: 使用 ProComponents，便于 V0 识别和美化
5. **可扩展性**: 支持后续功能迭代和演进

## 🏗️ 技术栈

### 核心技术
- **构建工具**: Vite 5.x（快速开发、HMR）
- **框架**: React 18.x + TypeScript 5.x
- **UI 组件库**: Ant Design 5.x + **Ant Design Pro Components**
- **路由**: React Router v6
- **状态管理**: TanStack Query v5（远程状态） + React Hooks（本地状态）
- **HTTP 客户端**: axios
- **实时通信**: EventSource（SSE）

### 开发工具
- **包管理器**: pnpm
- **代码规范**: ESLint + Prettier
- **类型检查**: TypeScript strict mode
- **Git Hooks**: husky + lint-staged

## 📁 目录结构

```
web/
├── src/
│   ├── app/                         # 应用入口与全局配置
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── router.tsx               # 路由配置
│   │   └── providers/               # 全局 Providers
│   │
│   ├── layouts/                     # 布局组件
│   │   ├── BasicLayout.tsx          # 基础布局（ProLayout）
│   │   ├── BlankLayout.tsx          # 空白布局
│   │   └── components/              # 布局相关组件
│   │
│   ├── features/                    # 业务功能模块（按领域划分）
│   │   ├── agents/                  # Agent 管理
│   │   │   ├── pages/               # 页面组件
│   │   │   ├── components/          # 模块内组件
│   │   │   ├── hooks/               # 模块内 Hooks
│   │   │   ├── types/               # 模块内类型
│   │   │   └── api/                 # 模块内 API
│   │   │
│   │   ├── runs/                    # 运行管理
│   │   │   ├── pages/
│   │   │   ├── components/
│   │   │   ├── hooks/
│   │   │   ├── types/
│   │   │   └── api/
│   │   │
│   │   └── settings/                # 设置
│   │
│   ├── shared/                      # 共享资源
│   │   ├── components/              # 通用组件
│   │   ├── hooks/                   # 通用 Hooks
│   │   ├── utils/                   # 工具函数
│   │   ├── types/                   # 全局类型
│   │   └── styles/                  # 全局样式
│   │
│   └── assets/                      # 资源文件
│
├── .env.development                 # 开发环境变量
├── .env.production                  # 生产环境变量
├── vite.config.ts                   # Vite 配置
├── tsconfig.json                    # TypeScript 配置
└── package.json                     # 依赖配置
```

## 🎨 核心页面设计

### Agent 管理模块

| 页面 | 路由 | 组件 | 职责 |
|-----|------|------|------|
| Agent 列表 | `/agents` | `AgentList.tsx` | 展示所有 Agent，使用 ProTable |
| 创建 Agent | `/agents/create` | `AgentCreate.tsx` | 输入 start+goal，使用 ProForm |
| Agent 详情 | `/agents/:id` | `AgentDetail.tsx` | 展示 Agent 信息，使用 ProDescriptions |
| 编辑 Agent | `/agents/:id/edit` | `AgentEdit.tsx` | 编辑 Agent 配置，使用 ProForm |

### 运行管理模块

| 页面 | 路由 | 组件 | 职责 |
|-----|------|------|------|
| 运行列表 | `/agents/:id/runs` | `RunList.tsx` | 展示运行历史，使用 ProTable |
| 运行详情 | `/agents/:id/runs/:runId` | `RunDetail.tsx` | 实时日志查看（SSE） |

## 🧩 ProComponents 使用

### 核心组件映射

| ProComponent | 使用场景 | 示例页面 |
|-------------|---------|---------|
| **ProTable** | 列表展示、数据表格 | AgentList, RunList |
| **ProForm** | 表单创建/编辑 | AgentCreate, AgentEdit |
| **ProLayout** | 整体布局框架 | BasicLayout |
| **ProCard** | 卡片展示 | AgentCard, RunCard |
| **ProDescriptions** | 详情展示 | AgentDetail, RunDetail |
| **ProSteps** | 步骤/时间线 | TaskTimeline |

### 为什么使用 ProComponents？

1. **简化开发**: 封装了常见的企业级场景，减少重复代码
2. **统一规范**: 提供一致的 UI 和交互体验
3. **便于识别**: 标准化的组件结构，便于 V0 等 AI 工具识别和美化
4. **功能丰富**: 内置搜索、筛选、分页、表单验证等功能

## 🛣️ 路由设计

```typescript
const router = createBrowserRouter([
  {
    path: '/',
    element: <BasicLayout />,
    children: [
      { index: true, element: <Navigate to="/agents" replace /> },
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
      { path: 'settings', element: <Settings /> },
    ],
  },
]);
```

**设计原则**:
- 嵌套路由，结构清晰
- 路径与业务领域对应
- 支持动态参数

## 📡 数据管理

### 远程状态（TanStack Query）

```typescript
// 查询
export function useAgents(params?: AgentQueryParams) {
  return useQuery({
    queryKey: ['agents', params],
    queryFn: () => fetchAgents(params),
    staleTime: 5 * 60 * 1000,
  });
}

// 变更
export function useCreateAgent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createAgent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
  });
}
```

### SSE 实时流

```typescript
export function useSSE(url: string, enabled: boolean = true) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  
  useEffect(() => {
    if (!enabled || !url) return;
    const eventSource = new EventSource(url);
    
    eventSource.onmessage = (e) => {
      if (e.data === '[DONE]') {
        eventSource.close();
        return;
      }
      const event = JSON.parse(e.data);
      setEvents((prev) => [...prev, event]);
    };
    
    return () => eventSource.close();
  }, [url, enabled]);
  
  return { events, isConnected };
}
```

## 🔧 开发规范

### 命名规范
- **组件**: PascalCase（`AgentList.tsx`）
- **Hooks**: camelCase，以 `use` 开头（`useAgents.ts`）
- **函数/变量**: camelCase（`fetchAgents`）
- **常量**: UPPER_SNAKE_CASE（`API_BASE_URL`）
- **类型**: PascalCase（`Agent`, `AgentDTO`）

### 路径别名
```typescript
import { Agent } from '@/features/agents/types/agent';
import { useAgents } from '@/features/agents/hooks/useAgents';
import request from '@/shared/utils/request';
```

### API 封装
```typescript
// 统一响应类型
export interface Result<T = any> {
  code: number;
  message: string;
  data?: T;
  trace_id?: string;
}

// API 方法
export async function fetchAgents(params?: any): Promise<PageResult<Agent>> {
  return request.get('/agents', { params });
}
```

## 🚀 快速开始

### 方式一：使用初始化脚本（推荐）

**Windows (PowerShell)**:
```powershell
.\scripts\init-frontend.ps1
```

**Linux/Mac (Bash)**:
```bash
chmod +x scripts/init-frontend.sh
./scripts/init-frontend.sh
```

### 方式二：手动初始化

```bash
# 1. 创建项目
pnpm create vite web --template react-ts

# 2. 安装依赖
cd web
pnpm add antd @ant-design/pro-components @ant-design/icons react-router-dom @tanstack/react-query axios
pnpm add -D @types/node eslint-config-prettier

# 3. 创建目录结构（参考脚本）

# 4. 配置文件（参考 docs/frontend_setup_guide.md）

# 5. 启动开发服务器
pnpm dev
```

## 📚 文档索引

| 文档 | 路径 | 用途 |
|-----|------|------|
| **前端结构规范** | `.augment/rules/frontend_structure.md` | 前端开发的强制规范 |
| **开发文档** | `docs/develop_document.md` | 完整的开发规范（前后端） |
| **初始化指南** | `docs/frontend_setup_guide.md` | 详细的初始化步骤和配置 |
| **架构总结** | `docs/frontend_architecture_summary.md` | 本文档 |

## 🎯 核心特性

### 1. 一句话创建 Agent
- 核心输入：起点（start）+ 目的（goal）
- 使用 ProForm 简化表单处理
- 符合项目核心需求

### 2. 实时日志查看
- 使用 SSE（EventSource）实现
- 自定义 `useSSE` Hook 封装
- 支持事件流解析和展示

### 3. 模块化设计
- 按业务领域划分（agents、runs、settings）
- 每个模块自包含（pages/components/hooks/types/api）
- 便于团队协作和代码维护

### 4. 类型安全
- TypeScript strict mode
- 完整的类型定义
- API 响应类型化

### 5. 便于美化
- 使用 ProComponents 标准组件
- 组件结构清晰
- 便于 V0 等 AI 工具识别

## 🔄 与后端对接

### API 基础配置
```typescript
// .env.development
VITE_API_BASE_URL=http://localhost:8000
```

### 请求拦截器
```typescript
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

### 响应拦截器
```typescript
request.interceptors.response.use(
  (response) => {
    const result: Result = response.data;
    if (result.code !== 2000) {
      message.error(result.message);
      return Promise.reject(new Error(result.message));
    }
    return result.data;
  },
  (error) => {
    // 统一错误处理
    message.error(error.message);
    return Promise.reject(error);
  }
);
```

## 📝 下一步工作

1. **实现布局组件**: 创建 `BasicLayout` 和 `BlankLayout`
2. **实现 Agent 模块**: 完成 Agent 相关的所有页面和组件
3. **实现 Run 模块**: 完成 Run 相关的所有页面和组件
4. **集成 SSE**: 实现实时日志查看功能
5. **编写测试**: 为核心 Hooks 和组件编写单元测试
6. **优化体验**: 添加加载状态、错误处理、空状态等

## 🤝 与 V0 美化的兼容性

### 组件化原则
- 所有页面拆分为小粒度组件
- 组件职责单一、可复用
- 使用 ProComponents 标准组件

### 样式规范
- 使用 Ant Design 主题系统
- CSS 变量统一管理
- 避免内联样式

### 代码结构
- 逻辑与 UI 分离（Hooks + Components）
- 类型定义完整
- 注释清晰

## 📞 支持

如有问题，请参考：
- [Vite 官方文档](https://vitejs.dev/)
- [React 官方文档](https://react.dev/)
- [Ant Design 官方文档](https://ant.design/)
- [Ant Design Pro Components](https://procomponents.ant.design/)
- [TanStack Query 文档](https://tanstack.com/query/latest)

---

**最后更新**: 2025-11-14
**版本**: 1.0.0

