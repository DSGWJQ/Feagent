---
type: "quick_reference"
target: "frontend"
---

# 前端开发快速参考

> **项目**：Feagent
> **目标**：AI助手前端开发快速查询手册
> **详细规范**：查阅 `docs/开发规范/02-前端开发规范.md`

---

## 💻 技术栈速查

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 18.3+ | UI框架 |
| TypeScript | 5.9+ | 类型系统 |
| Vite | 5.x | 构建工具 |
| Ant Design | 5.x | UI组件库 |
| XYFlow (React Flow) | 11.x | 工作流可视化 |
| TanStack Query | 5.x | 远程状态管理 |
| EventSource | 原生API | SSE实时通信 |
| axios | 1.6+ | HTTP客户端 |

**为什么选XYFlow而非LogicFlow？**
- ✅ 原生React组件
- ✅ TypeScript支持完善
- ✅ 文档齐全（英文）
- ✅ 社区活跃（18k+ stars）

---

## 🗂️ 目录结构

```
web/src/
├── app/                     # 应用入口、全局配置
│   ├── App.tsx
│   ├── router.tsx           # 路由配置（集中）
│   └── providers/
├── layouts/                 # 布局组件
│   ├── BasicLayout.tsx
│   └── BlankLayout.tsx
├── features/                # 业务功能模块（按领域）
│   ├── agents/              # Agent管理
│   │   ├── pages/           # 页面组件
│   │   ├── components/      # 模块内组件
│   │   ├── hooks/           # 模块内Hooks
│   │   ├── types/           # 类型定义
│   │   └── api/             # API封装
│   ├── workflows/           # 工作流管理
│   └── runs/                # 运行管理
└── shared/                  # 共享资源
    ├── components/          # 通用组件
    ├── hooks/               # 通用Hooks
    ├── utils/               # 工具函数
    └── types/               # 全局类型
```

---

## 📝 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 组件 | PascalCase | `AgentList.tsx` |
| Hooks | camelCase + use前缀 | `useAgents.ts` |
| 函数/变量 | camelCase | `fetchAgents` |
| 常量 | UPPER_SNAKE_CASE | `API_BASE_URL` |
| 类型/接口 | PascalCase | `Agent`, `AgentDTO` |

---

## 🎨 核心组件

### 1. 工作流画布
```typescript
import ReactFlow, {
  Background,
  Controls,
  MiniMap
} from 'reactflow';

<ReactFlow
  nodes={nodes}
  edges={edges}
  onNodesChange={onNodesChange}
  onEdgesChange={onEdgesChange}
  nodeTypes={nodeTypes}
>
  <Background />
  <Controls />
  <MiniMap />
</ReactFlow>
```

### 2. 数据请求（TanStack Query）
```typescript
import { useQuery } from '@tanstack/react-query';

export function useAgents() {
  return useQuery({
    queryKey: ['agents'],
    queryFn: fetchAgents,
    staleTime: 5 * 60 * 1000  // 5分钟
  });
}
```

### 3. SSE实时通信
```typescript
const eventSource = new EventSource(`/api/runs/${runId}/stream`);

eventSource.onmessage = (e) => {
  if (e.data === '[DONE]') {
    eventSource.close();
    return;
  }

  const event = JSON.parse(e.data);
  // 处理事件
};
```

---

## 🎯 节点类型（工作流）

| 节点类型 | 颜色 | 图标 | 说明 |
|---------|------|------|------|
| HTTP | 蓝色 #1890ff | 🌐 | HTTP请求 |
| LLM | 紫色 #722ed1 | 🤖 | LLM处理 |
| JAVASCRIPT | 黄色 #faad14 | 📜 | JS脚本 |
| CONDITION | 橙色 #fa8c16 | 🔀 | 条件判断 |
| START | 绿色 #52c41a | ▶ | 开始 |
| END | 红色 #f5222d | ⏹ | 结束 |

---

## 🔄 状态管理策略

### 远程状态（TanStack Query）
- API数据
- 服务器状态
- 缓存管理

### 本地状态（React Hooks）
- UI状态（展开/折叠）
- 表单输入
- 临时数据

**❌ 避免**：引入Redux/Zustand（除非明确需要）

---

## 🔍 常见问题快速查询

### Q: 如何创建新页面？

```typescript
// web/src/features/workflows/pages/WorkflowList.tsx
export function WorkflowList() {
  const { data: workflows, isLoading } = useWorkflows();

  if (isLoading) return <Loading />;

  return (
    <div>
      {workflows.map(workflow => (
        <WorkflowCard key={workflow.id} workflow={workflow} />
      ))}
    </div>
  );
}
```

### Q: 如何添加API请求？

```typescript
// web/src/features/workflows/api/workflowApi.ts
export async function fetchWorkflows(): Promise<Workflow[]> {
  return request.get('/workflows');
}

// web/src/features/workflows/hooks/useWorkflows.ts
export function useWorkflows() {
  return useQuery({
    queryKey: ['workflows'],
    queryFn: fetchWorkflows
  });
}
```

### Q: 如何自定义节点？

```typescript
// web/src/features/workflows/components/nodes/CustomNode.tsx
import { Handle, Position, NodeProps } from 'reactflow';

export const CustomNode = ({ data }: NodeProps) => {
  return (
    <div>
      <Handle type="target" position={Position.Top} />
      <div>{data.label}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
};
```

---

## ⚠️ 常见错误

### ❌ 错误1：直接修改state
```typescript
nodes[0].data.label = "新标签";  // ❌ 禁止
setNodes(nodes);  // 不会触发重渲染
```

✅ **正确做法**：
```typescript
setNodes((nds) =>
  nds.map((node) =>
    node.id === id
      ? { ...node, data: { ...node.data, label: "新标签" } }
      : node
  )
);
```

### ❌ 错误2：硬编码API地址
```typescript
const url = "http://localhost:8000/agents";  // ❌ 禁止
```

✅ **正确做法**：
```typescript
const url = `${import.meta.env.VITE_API_BASE_URL}/agents`;
```

### ❌ 错误3：未处理加载和错误状态
```typescript
const { data } = useAgents();  // ❌ 缺少isLoading和error处理
return <div>{data.map(...)}</div>;
```

✅ **正确做法**：
```typescript
const { data, isLoading, error } = useAgents();

if (isLoading) return <Loading />;
if (error) return <Error message={error.message} />;
return <div>{data.map(...)}</div>;
```

---

## 📚 详细规范

完整规范请查阅：
- `docs/开发规范/02-前端开发规范.md`（详细内容）
- `docs/技术方案/02-工作流可视化方案.md`（XYFlow详解）
- `docs/开发规范/03-开发过程指导.md`（完整流程）
