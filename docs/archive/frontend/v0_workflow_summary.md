# V0 前端开发工作流程总结

## 🎯 核心策略

**V0 只负责 UI 设计和组件实现，你负责业务逻辑和数据集成**

---

## ✅ 可以直接移植到 V0 的内容

### 1. **完全可以移植** ✅

以下内容可以直接让 V0 生成，无需修改：

- ✅ **UI 组件结构** - ProTable、ProForm、ProDescriptions 等
- ✅ **样式和布局** - Ant Design 组件样式
- ✅ **基础交互** - 按钮点击、表单验证、对话框等
- ✅ **Mock 数据展示** - 用于预览 UI 效果

### 2. **需要你手动集成** 🔧

以下内容需要你在 V0 生成的代码基础上添加：

- 🔧 **API 调用** - 替换 Mock 数据为真实 API
- 🔧 **状态管理** - 使用 TanStack Query
- 🔧 **路由跳转** - 使用 React Router
- 🔧 **错误处理** - 添加 try-catch 和错误提示
- 🔧 **权限控制** - 添加权限判断逻辑

---

## 📋 推荐的开发流程

### **阶段 1：准备工作（你现在的状态）** ✅

**已完成**：
- ✅ 后端 API 已实现并测试（5 个核心端点）
- ✅ 前端项目骨架已搭建（Vite + React + TypeScript + Ant Design）
- ✅ API 文档已创建（`docs/api_reference.md`）

**需要完成**：
- 🔧 创建 API 客户端（`web/src/features/agents/api/agentsApi.ts`）
- 🔧 创建 TanStack Query Hooks（`web/src/shared/hooks/useAgents.ts`）

---

### **阶段 2：使用 V0 生成 UI 组件** 🎨

#### **步骤 1：访问 V0**

打开 https://v0.dev

#### **步骤 2：使用 Prompt 生成组件**

参考 `docs/v0_development_guide.md` 中的 Prompt 模板，例如：

**Agent 列表页 Prompt**：
```
我需要一个 Agent 管理列表页面。

技术栈：
- React 19 + TypeScript
- Ant Design 5.28.1
- Ant Design Pro Components 2.8.10 (使用 ProTable)

数据结构（TypeScript）：
interface Agent {
  id: string;
  name: string;
  start: string;
  goal: string;
  created_at: string;
  updated_at: string;
}

功能需求：
1. 使用 ProTable 展示 Agent 列表
2. 列配置：名称、起始状态、目标状态、创建时间、操作列
3. 顶部工具栏："创建 Agent" 按钮
4. 支持分页（每页 10 条）
5. 删除时弹出确认对话框

请生成完整的 React 组件代码。
```

#### **步骤 3：预览和调整**

在 V0 中预览生成的组件，如果不满意可以：
- 点击 "Edit" 修改 Prompt
- 点击 "Regenerate" 重新生成
- 手动调整代码

#### **步骤 4：复制代码**

满意后，点击 "Copy Code" 复制组件代码。

---

### **阶段 3：集成到项目** 🔧

#### **步骤 1：创建组件文件**

将 V0 生成的代码粘贴到项目中：

```bash
# Agent 列表页
web/src/features/agents/pages/AgentList.tsx

# Agent 创建页
web/src/features/agents/pages/AgentCreate.tsx

# Agent 详情页
web/src/features/agents/pages/AgentDetail.tsx
```

#### **步骤 2：调整导入路径**

V0 可能使用不同的导入路径，需要调整：

```typescript
// V0 生成的代码
import { ProTable } from '@ant-design/pro-components';
import { Button } from 'antd';

// 保持不变（项目中已安装）
import { ProTable } from '@ant-design/pro-components';
import { Button } from 'antd';
```

#### **步骤 3：替换 Mock 数据为 API 调用**

**V0 生成的代码（Mock 数据）**：
```typescript
const [agents, setAgents] = useState<Agent[]>([
  {
    id: '1',
    name: '示例 Agent',
    start: '起始状态',
    goal: '目标状态',
    created_at: '2024-01-15T10:30:00Z',
    updated_at: '2024-01-15T10:30:00Z',
  },
]);
```

**替换为真实 API**：
```typescript
import { useAgents } from '@/shared/hooks/useAgents';

function AgentList() {
  const { data: agents, isLoading, error } = useAgents();

  if (error) {
    return <div>加载失败</div>;
  }

  return (
    <ProTable
      dataSource={agents}
      loading={isLoading}
      // ... 其他配置
    />
  );
}
```

#### **步骤 4：添加路由**

在 `web/src/App.tsx` 中添加路由：

```typescript
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import AgentList from '@/features/agents/pages/AgentList';
import AgentCreate from '@/features/agents/pages/AgentCreate';
import AgentDetail from '@/features/agents/pages/AgentDetail';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/agents" element={<AgentList />} />
        <Route path="/agents/create" element={<AgentCreate />} />
        <Route path="/agents/:id" element={<AgentDetail />} />
      </Routes>
    </BrowserRouter>
  );
}
```

#### **步骤 5：测试功能**

```bash
cd web
pnpm dev
```

访问 http://localhost:3000/agents 测试功能。

---

## 🎯 你需要先做的准备工作

在使用 V0 之前，建议先完成以下基础设施：

### **1. 创建 API 客户端** 📦

**文件**: `web/src/features/agents/api/agentsApi.ts`

```typescript
import request from '@/shared/utils/request';
import type { Agent, CreateAgentDto } from '@/shared/types/agent';

export const agentsApi = {
  // 获取 Agent 列表
  getAgents: (params?: { skip?: number; limit?: number }) => {
    return request.get<Agent[]>('/agents', { params });
  },

  // 创建 Agent
  createAgent: (data: CreateAgentDto) => {
    return request.post<Agent>('/agents', data);
  },

  // 获取 Agent 详情
  getAgent: (id: string) => {
    return request.get<Agent>(`/agents/${id}`);
  },

  // 删除 Agent
  deleteAgent: (id: string) => {
    return request.delete(`/agents/${id}`);
  },
};
```

### **2. 创建 TypeScript 类型** 📝

**文件**: `web/src/shared/types/agent.ts`

```typescript
export interface Agent {
  id: string;
  name: string;
  start: string;
  goal: string;
  created_at: string;
  updated_at: string;
}

export interface CreateAgentDto {
  name: string;
  start: string;
  goal: string;
}
```

### **3. 创建 TanStack Query Hooks** 🪝

**文件**: `web/src/shared/hooks/useAgents.ts`

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { agentsApi } from '@/features/agents/api/agentsApi';
import type { CreateAgentDto } from '@/shared/types/agent';
import { message } from 'antd';

// 获取 Agent 列表
export const useAgents = () => {
  return useQuery({
    queryKey: ['agents'],
    queryFn: () => agentsApi.getAgents(),
  });
};

// 获取单个 Agent
export const useAgent = (id: string) => {
  return useQuery({
    queryKey: ['agents', id],
    queryFn: () => agentsApi.getAgent(id),
    enabled: !!id,
  });
};

// 创建 Agent
export const useCreateAgent = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateAgentDto) => agentsApi.createAgent(data),
    onSuccess: () => {
      message.success('创建成功');
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
    onError: () => {
      message.error('创建失败');
    },
  });
};

// 删除 Agent
export const useDeleteAgent = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => agentsApi.deleteAgent(id),
    onSuccess: () => {
      message.success('删除成功');
      queryClient.invalidateQueries({ queryKey: ['agents'] });
    },
    onError: () => {
      message.error('删除失败');
    },
  });
};
```

---

## 📊 工作量对比

### **使用 V0 的优势**：

| 任务 | 手动开发 | 使用 V0 | 节省时间 |
|------|---------|---------|---------|
| Agent 列表页 UI | 2-3 小时 | 5 分钟 | 95% ⬇️ |
| Agent 创建表单 | 1-2 小时 | 5 分钟 | 95% ⬇️ |
| Agent 详情页 | 1-2 小时 | 5 分钟 | 95% ⬇️ |
| Run 列表页 | 2-3 小时 | 5 分钟 | 95% ⬇️ |
| **UI 总计** | **6-10 小时** | **20 分钟** | **95% ⬇️** |
| API 集成 | 2-3 小时 | 2-3 小时 | 0% |
| 路由配置 | 30 分钟 | 30 分钟 | 0% |
| 测试调试 | 2-3 小时 | 2-3 小时 | 0% |
| **总计** | **10-16 小时** | **5-7 小时** | **50% ⬇️** |

---

## ✅ 总结

### **V0 能做什么**：
- ✅ 快速生成 UI 组件（节省 95% UI 开发时间）
- ✅ 提供美观的默认样式
- ✅ 生成符合最佳实践的代码结构

### **V0 不能做什么**：
- ❌ 不能直接连接你的后端 API
- ❌ 不能生成状态管理逻辑
- ❌ 不能配置路由
- ❌ 不能处理复杂的业务逻辑

### **你需要做什么**：
1. ✅ **准备工作**（1-2 小时）：
   - 创建 API 客户端
   - 创建 TypeScript 类型
   - 创建 TanStack Query Hooks

2. ✅ **使用 V0**（20 分钟）：
   - 生成 4 个页面的 UI 组件

3. ✅ **集成工作**（3-4 小时）：
   - 替换 Mock 数据为 API 调用
   - 配置路由
   - 测试和调试

### **总工作量**：
- **不使用 V0**：10-16 小时
- **使用 V0**：5-7 小时
- **节省时间**：50%

---

## 🚀 下一步行动

### **立即开始**：

1. **创建基础设施**（我可以帮你）：
   - `web/src/features/agents/api/agentsApi.ts`
   - `web/src/shared/types/agent.ts`
   - `web/src/shared/hooks/useAgents.ts`

2. **访问 V0**：
   - 打开 https://v0.dev
   - 使用 `docs/v0_development_guide.md` 中的 Prompt

3. **集成代码**：
   - 复制 V0 生成的代码
   - 替换 Mock 数据为 API 调用
   - 配置路由

---

**需要我帮你创建基础设施代码吗？** 🤔
