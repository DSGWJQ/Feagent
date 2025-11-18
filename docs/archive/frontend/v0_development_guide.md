# V0 前端开发指南

## 📋 概述

本指南说明如何使用 V0 (v0.dev) 生成 UI 组件，并集成到项目中。

---

## 🎯 开发策略

### **V0 负责**：
- ✅ UI 组件设计和实现
- ✅ 样式和布局
- ✅ 基础交互逻辑
- ✅ Mock 数据展示

### **你负责**：
- ✅ API 集成（替换 Mock 数据）
- ✅ 状态管理（TanStack Query）
- ✅ 路由配置
- ✅ 错误处理
- ✅ 业务逻辑

---

## 📝 V0 Prompt 模板

### **1. Agent 列表页**

```
我需要一个 Agent 管理列表页面。

技术栈：
- React 19 + TypeScript
- Ant Design 5.28.1
- Ant Design Pro Components 2.8.10 (使用 ProTable)

数据结构（TypeScript）：
interface Agent {
  id: string;           // UUID
  name: string;         // Agent 名称
  start: string;        // 起始状态
  goal: string;         // 目标状态
  created_at: string;   // ISO 8601 格式
  updated_at: string;   // ISO 8601 格式
}

功能需求：
1. 使用 ProTable 展示 Agent 列表
2. 列配置：
   - 名称（name）- 可搜索
   - 起始状态（start）- 显示前 50 字符
   - 目标状态（goal）- 显示前 50 字符
   - 创建时间（created_at）- 格式化显示
   - 操作列：查看详情按钮、删除按钮
3. 顶部工具栏：
   - 左侧：标题 "Agent 列表"
   - 右侧："创建 Agent" 按钮（primary 类型）
4. 支持分页（每页 10 条）
5. 删除时弹出确认对话框

样式要求：
- 使用 Ant Design 默认主题
- 表格紧凑模式
- 操作按钮使用 link 类型

请生成完整的 React 组件代码。
```

---

### **2. Agent 创建表单页**

```
我需要一个创建 Agent 的表单页面。

技术栈：
- React 19 + TypeScript
- Ant Design 5.28.1
- Ant Design Pro Components 2.8.10 (使用 ProForm)

表单字段：
1. name (必填)
   - 类型：文本输入
   - 标签："Agent 名称"
   - 占位符："请输入 Agent 名称"
   - 验证：必填，最大长度 100

2. start (必填)
   - 类型：文本域
   - 标签："起始状态"
   - 占位符："描述当前的起始状态，例如：有一个 CSV 文件"
   - 验证：必填，最大长度 500
   - 行数：4

3. goal (必填)
   - 类型：文本域
   - 标签："目标状态"
   - 占位符："描述期望达到的目标，例如：生成数据分析报告"
   - 验证：必填，最大长度 500
   - 行数：4

功能需求：
1. 使用 ProForm 实现表单
2. 提交按钮文本："创建 Agent"
3. 重置按钮文本："重置"
4. 表单布局：垂直布局，标签宽度 120px
5. 提交成功后显示成功提示
6. 提交失败显示错误提示

样式要求：
- 表单最大宽度 600px
- 居中显示
- 卡片样式包裹

请生成完整的 React 组件代码。
```

---

### **3. Agent 详情页**

```
我需要一个 Agent 详情页面。

技术栈：
- React 19 + TypeScript
- Ant Design 5.28.1
- Ant Design Pro Components 2.8.10 (使用 ProDescriptions)

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
1. 使用 ProDescriptions 展示 Agent 详情
2. 字段配置：
   - ID（id）- 可复制
   - 名称（name）
   - 起始状态（start）- 多行显示
   - 目标状态（goal）- 多行显示
   - 创建时间（created_at）- 格式化显示
   - 更新时间（updated_at）- 格式化显示
3. 顶部操作栏：
   - 左侧：返回按钮
   - 右侧："执行 Run" 按钮（primary 类型）
4. 底部：Run 历史列表（使用 ProTable）

Run 数据结构：
interface Run {
  id: string;
  status: 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED';
  result: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

Run 列表配置：
- 状态（status）- 使用 Badge 显示不同颜色
- 结果（result）- 显示前 100 字符
- 错误（error）- 红色显示
- 创建时间（created_at）
- 操作：查看详情按钮

样式要求：
- 卡片样式
- 详情和列表之间有分隔

请生成完整的 React 组件代码。
```

---

### **4. Run 列表页**

```
我需要一个 Run 历史列表页面。

技术栈：
- React 19 + TypeScript
- Ant Design 5.28.1
- Ant Design Pro Components 2.8.10 (使用 ProTable)

数据结构：
interface Run {
  id: string;
  agent_id: string;
  status: 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED';
  result: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

功能需求：
1. 使用 ProTable 展示 Run 列表
2. 列配置：
   - ID（id）- 显示前 8 位
   - 状态（status）- 使用 Badge 组件：
     * PENDING: 默认（灰色）
     * RUNNING: 处理中（蓝色）
     * SUCCEEDED: 成功（绿色）
     * FAILED: 失败（红色）
   - 结果（result）- 显示前 100 字符，为空显示 "-"
   - 错误（error）- 红色文本，为空显示 "-"
   - 创建时间（created_at）- 格式化显示
   - 操作：查看详情按钮
3. 支持按状态筛选
4. 支持分页（每页 10 条）
5. 自动刷新（RUNNING 状态时每 3 秒刷新一次）

样式要求：
- 紧凑模式
- 状态列宽度固定 100px
- 操作列宽度固定 80px

请生成完整的 React 组件代码。
```

---

## 🔄 从 V0 迁移代码的步骤

### **步骤 1：复制组件代码**

从 V0 复制生成的组件代码到项目：

```bash
# Agent 列表页
web/src/features/agents/pages/AgentList.tsx

# Agent 创建页
web/src/features/agents/pages/AgentCreate.tsx

# Agent 详情页
web/src/features/agents/pages/AgentDetail.tsx

# Run 列表页
web/src/features/runs/pages/RunList.tsx
```

---

### **步骤 2：调整导入路径**

V0 生成的代码可能使用相对路径，需要调整为项目路径：

```typescript
// V0 生成的代码（可能）
import { ProTable } from '@ant-design/pro-components';

// 保持不变（已在项目中安装）
import { ProTable } from '@ant-design/pro-components';
```

---

### **步骤 3：集成 API 调用**

替换 V0 的 Mock 数据为真实 API 调用：

**V0 生成的代码（Mock 数据）**：
```typescript
const [dataSource, setDataSource] = useState<Agent[]>([
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
  const { data: agents, isLoading } = useAgents();

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

### **步骤 4：添加路由配置**

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

---

## ✅ 检查清单

在从 V0 迁移代码后，确保：

- [ ] 所有导入路径正确
- [ ] 替换 Mock 数据为 API 调用
- [ ] 添加错误处理
- [ ] 添加加载状态
- [ ] 配置路由
- [ ] 测试所有功能
- [ ] 检查响应式布局
- [ ] 检查无障碍性（a11y）

---

## 🎨 样式定制

如果需要定制样式，在 `web/src/styles/` 目录下创建 CSS 模块：

```css
/* web/src/features/agents/pages/AgentList.module.css */
.container {
  padding: 24px;
}

.table {
  background: white;
  border-radius: 8px;
}
```

然后在组件中导入：

```typescript
import styles from './AgentList.module.css';

function AgentList() {
  return (
    <div className={styles.container}>
      <ProTable className={styles.table} />
    </div>
  );
}
```

---

## 📚 参考资源

- **V0 官网**: https://v0.dev
- **Ant Design**: https://ant.design
- **Ant Design Pro Components**: https://procomponents.ant.design
- **API 文档**: `docs/api_reference.md`
- **前端架构**: `docs/frontend_architecture_summary.md`
