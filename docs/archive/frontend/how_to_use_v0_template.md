# 如何使用 V0 模板

## 📋 概述

本文档详细说明如何使用 V0 (https://v0.dev) 生成的模板，并集成到我们的项目中。

---

## 🎯 使用 V0 的完整流程

### 步骤 1: 在 V0 找到合适的模板

1. **访问 V0**: https://v0.dev
2. **浏览模板**: 在首页或搜索框中查找 "table"、"list"、"form" 等关键词
3. **预览模板**: 点击模板查看效果
4. **选择模板**: 找到符合需求的模板

**你提到你看上了一个模板，那么：**

---

### 步骤 2: 复制 V0 生成的代码

#### 方法 A: 直接复制代码（如果 V0 提供了代码）

1. 在 V0 页面点击 "View Code" 或 "Copy Code"
2. 复制整个组件代码
3. 跳到步骤 3

#### 方法 B: 使用 Prompt 生成代码（推荐）

如果模板不完全符合需求，可以修改 Prompt：

**示例 Prompt**:
```
基于这个模板，帮我生成一个 Agent 管理列表页面。

技术栈：
- React 19 + TypeScript
- Ant Design 5.28.1
- Ant Design Pro Components 2.8.10

数据结构：
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
5. 支持搜索（按名称）
6. 操作列：查看详情、编辑、删除
7. 删除时弹出确认对话框

请生成完整的 React 组件代码。
```

---

### 步骤 3: 创建新的组件文件

**不要直接替换 AgentListTest.tsx！** 而是创建一个新文件：

```bash
# 在项目中创建新文件
web/src/features/agents/pages/AgentList.tsx
```

**告诉我**:
1. 把 V0 生成的代码发给我
2. 或者把 V0 的链接发给我
3. 或者描述一下模板的样子

**我会帮你**:
1. 创建 `AgentList.tsx` 文件
2. 集成我们的 API 调用（useAgents, useCreateAgent, useDeleteAgent）
3. 替换 Mock 数据为真实数据
4. 添加错误处理和加载状态
5. 配置路由

---

### 步骤 4: 集成 API 调用（我来做）

V0 生成的代码通常使用 Mock 数据，我会帮你替换为真实的 API 调用：

**V0 生成的代码（Mock 数据）**:
```typescript
function AgentList() {
  const [agents, setAgents] = useState([
    { id: '1', name: 'Mock Agent', start: '...', goal: '...' }
  ]);

  return <ProTable dataSource={agents} />;
}
```

**集成后的代码（真实 API）**:
```typescript
import { useAgents, useCreateAgent, useDeleteAgent } from '@/shared/hooks';

function AgentList() {
  const { data: agents, isLoading, error } = useAgents();
  const createAgent = useCreateAgent();
  const deleteAgent = useDeleteAgent();

  return (
    <ProTable
      dataSource={agents}
      loading={isLoading}
      // ... 其他配置
    />
  );
}
```

---

### 步骤 5: 配置路由（我来做）

我会帮你配置路由，让新页面可以访问：

**修改 `web/src/app/App.tsx`**:
```typescript
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import AgentList from '@/features/agents/pages/AgentList';
import AgentDetail from '@/features/agents/pages/AgentDetail';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AgentList />} />
        <Route path="/agents/:id" element={<AgentDetail />} />
      </Routes>
    </BrowserRouter>
  );
}
```

---

### 步骤 6: 测试新页面

1. **启动前端**:
   ```bash
   cd web
   pnpm dev
   ```

2. **启动后端**:
   ```bash
   python -m uvicorn src.interfaces.api.main:app --reload
   ```

3. **访问页面**: http://localhost:3000

4. **测试功能**:
   - ✅ 列表是否正确显示
   - ✅ 创建功能是否正常
   - ✅ 删除功能是否正常
   - ✅ 分页是否正常
   - ✅ 搜索是否正常

---

## 🎨 V0 模板的常见类型

### 1. 列表页面（Table/List）

**适用场景**: Agent 列表、Run 列表

**关键组件**:
- ProTable（Ant Design Pro）
- Table（Ant Design）
- DataGrid（Material-UI）

**需要集成的 Hooks**:
- `useAgents()` - 获取列表
- `useCreateAgent()` - 创建
- `useDeleteAgent()` - 删除

---

### 2. 详情页面（Detail）

**适用场景**: Agent 详情、Run 详情

**关键组件**:
- ProDescriptions（Ant Design Pro）
- Descriptions（Ant Design）
- Card（Ant Design）

**需要集成的 Hooks**:
- `useAgent(id)` - 获取详情
- `useUpdateAgent()` - 更新

---

### 3. 表单页面（Form）

**适用场景**: 创建 Agent、编辑 Agent

**关键组件**:
- ProForm（Ant Design Pro）
- Form（Ant Design）
- Modal + Form（对话框表单）

**需要集成的 Hooks**:
- `useCreateAgent()` - 创建
- `useUpdateAgent()` - 更新

---

### 4. 仪表板页面（Dashboard）

**适用场景**: 首页、统计页面

**关键组件**:
- Card + Statistic（统计卡片）
- Chart（图表）
- Timeline（时间线）

**需要集成的 Hooks**:
- `useAgents()` - 获取统计数据
- `useRuns()` - 获取执行记录

---

## 📝 告诉我你的需求

### 方式 1: 发送 V0 链接

**示例**:
```
我在 V0 看上了这个模板：https://v0.dev/t/xxxxx
```

**我会**:
1. 查看模板
2. 复制代码
3. 集成到项目中
4. 配置路由
5. 测试功能

---

### 方式 2: 发送 V0 代码

**示例**:
```
V0 生成的代码：

```typescript
export default function AgentList() {
  // ... V0 生成的代码
}
```
```

**我会**:
1. 创建新文件
2. 集成 API 调用
3. 配置路由
4. 测试功能

---

### 方式 3: 描述模板样子

**示例**:
```
我想要一个这样的页面：
- 顶部有搜索框和"创建"按钮
- 中间是一个表格，显示 Agent 列表
- 每行有"查看"、"编辑"、"删除"按钮
- 底部有分页
- 整体风格是现代简洁的
```

**我会**:
1. 去 V0 找类似的模板
2. 或者手动创建符合需求的组件
3. 集成 API 调用
4. 配置路由
5. 测试功能

---

## 🔧 集成步骤详解

### 1. 替换 Mock 数据

**V0 代码**:
```typescript
const [agents, setAgents] = useState([
  { id: '1', name: 'Mock Agent' }
]);
```

**集成后**:
```typescript
const { data: agents, isLoading } = useAgents();
```

---

### 2. 添加加载状态

**V0 代码**:
```typescript
<ProTable dataSource={agents} />
```

**集成后**:
```typescript
<ProTable
  dataSource={agents}
  loading={isLoading}
/>
```

---

### 3. 添加错误处理

**V0 代码**:
```typescript
// 通常没有错误处理
```

**集成后**:
```typescript
const { data: agents, isLoading, error } = useAgents();

if (error) {
  return <Alert type="error" message="加载失败" />;
}
```

---

### 4. 集成创建功能

**V0 代码**:
```typescript
const handleCreate = () => {
  // Mock 实现
  setAgents([...agents, newAgent]);
};
```

**集成后**:
```typescript
const createAgent = useCreateAgent();

const handleCreate = (values) => {
  createAgent.mutate(values);
};
```

---

### 5. 集成删除功能

**V0 代码**:
```typescript
const handleDelete = (id) => {
  setAgents(agents.filter(a => a.id !== id));
};
```

**集成后**:
```typescript
const deleteAgent = useDeleteAgent();

const handleDelete = (id) => {
  if (window.confirm('确认删除？')) {
    deleteAgent.mutate(id);
  }
};
```

---

## ✅ 检查清单

在集成 V0 模板后，确保：

- [ ] 导入了正确的 Hooks（useAgents, useCreateAgent 等）
- [ ] 替换了所有 Mock 数据为真实 API 调用
- [ ] 添加了加载状态（loading）
- [ ] 添加了错误处理（error）
- [ ] 配置了路由
- [ ] 测试了所有功能（列表、创建、删除等）
- [ ] 样式正常显示
- [ ] 响应式布局正常

---

## 🚀 现在开始

**请告诉我**:

1. **V0 链接**: 如果你有 V0 模板的链接
2. **V0 代码**: 如果你已经复制了代码
3. **需求描述**: 如果你想让我帮你找模板

**我会立即帮你**:
1. 创建新的组件文件
2. 集成 API 调用
3. 配置路由
4. 测试功能

**准备好了吗？把 V0 模板发给我吧！** 🎨
