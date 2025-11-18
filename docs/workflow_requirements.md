# 工作流需求变更说明

## 📋 需求变更概述

**变更日期**: 2025-01-15
**变更类型**: 核心功能重大调整

---

## 🎯 新需求：表单创建 + 对话/拖拽调整工作流

### 核心理念

**类似扣子（Coze）的 Agent 创建平台**：
- **第一步**：用户填写表单（起点 + 终点 + 描述）
- **第二步**：AI 自动生成最小可行工作流（Workflow）
- **第三步**：用户通过对话或拖拽调整工作流
- **第四步**：执行工作流，实时显示每个节点的状态

---

## 🔄 需求对比

### 之前的设计

```
用户填写表单（起点 + 目的）
    ↓
系统创建 Agent
    ↓
执行 Agent
```

**问题**：
- ❌ 无法看到执行流程
- ❌ 无法灵活调整执行流程
- ❌ 缺少可视化反馈

---

### 现在的设计

```
用户填写表单（起点 + 终点 + 描述）
    ↓
AI 生成最小可行工作流（Workflow）
    ↓
用户通过对话或拖拽调整工作流
    ↓
执行工作流
    ↓
实时显示每个节点的状态（成功/失败/运行中/未执行）
```

**优势**：
- ✅ 表单引导，降低首次使用门槛
- ✅ 可视化工作流，用户能看到执行流程
- ✅ 灵活调整，支持对话和拖拽两种方式
- ✅ 状态可视化，方便调试和优化
- ✅ 符合现代 Agent 平台的设计理念（扣子、Dify）

---

## 📊 核心功能

### 1. 表单创建工作流

**用户操作**：
1. 点击"创建工作流"按钮
2. 弹出表单（Modal）
3. 填写表单：
   - **起点**（start）：`GitHub Issue 列表`
   - **终点**（goal）：`发送到钉钉群`
   - **描述**（description）：`每天定时获取 GitHub Issue 并发送到钉钉群`
4. 点击"提交"

**AI 生成工作流**：
```
工作流名称：GitHub Issue 通知
节点：
  1. [HTTP] 获取 GitHub Issue
     - URL: https://api.github.com/repos/{owner}/{repo}/issues
     - Method: GET
     - 位置: (100, 100)

  2. [Transform] 格式化消息
     - 输入：Issue 列表
     - 输出：钉钉消息格式
     - 位置: (100, 250)

  3. [HTTP] 发送钉钉通知
     - URL: {webhook_url}
     - Method: POST
     - 位置: (100, 400)

边：
  1 → 2 → 3
```

**AI 回复消息**：
```
我为你创建了一个工作流，包含 3 个步骤：
1. 从 GitHub 获取 Issue 列表
2. 格式化为钉钉消息格式
3. 发送到钉钉群

你可以通过右侧的对话框调整工作流，或者直接拖拽节点。
```

---

### 2. 对话式调整工作流

**用户输入**（在右侧对话框）：
```
用户: 在发送钉钉之前，先保存到数据库
```

**AI 回复**：
```
AI: 好的，我在步骤 2 和 3 之间添加了"保存到数据库"节点：

工作流更新：
  1. [HTTP] 获取 GitHub Issue
  2. [Transform] 格式化消息
  3. [SQL] 保存 Issue 记录  ← 新增
     - SQL: INSERT INTO issues (title, body) VALUES (?, ?)
     - 位置: (100, 325)
  4. [HTTP] 发送钉钉通知

边：
  1 → 2 → 3 → 4

是否还需要调整？
```

**工作流图表自动更新**：
- 新增节点 3（SQL）
- 自动调整节点位置
- 更新连线

---

### 3. 可视化拖拽调整

**界面**：
```
┌─────────────────────────────────────────────────────────────┐
│  工作流编辑器                                                │
├──────────────────────────────────┬──────────────────────────┤
│  工作流画布（React Flow）         │  对话框                   │
│                                  │                          │
│   ┌──────────┐                   │  用户: 在发送钉钉之前，   │
│   │ GitHub   │  ✅ 成功          │  先保存到数据库           │
│   │ API      │                   │                          │
│   └────┬─────┘                   │  AI: 好的，我在步骤 2    │
│        │                         │  和 3 之间添加了...       │
│        ▼                         │                          │
│   ┌──────────┐                   │  [输入框]                │
│   │ 数据转换  │  ⏳ 运行中        │  [发送]                  │
│   └────┬─────┘                   │                          │
│        │                         │                          │
│        ▼                         │                          │
│   ┌──────────┐                   │                          │
│   │ 保存数据库│  ⏸️ 未执行        │                          │
│   └────┬─────┘                   │                          │
│        │                         │                          │
│        ▼                         │                          │
│   ┌──────────┐                   │                          │
│   │ 钉钉通知  │  ❌ 失败          │                          │
│   └──────────┘                   │                          │
│                                  │                          │
│  [执行工作流] [保存]              │                          │
└──────────────────────────────────┴──────────────────────────┘
```

**功能**：
- ✅ 拖拽节点位置
- ✅ 连接节点（创建边）
- ✅ 编辑节点属性（双击节点）
- ✅ 删除节点（选中后按 Delete）
- ✅ 添加新节点（从左侧工具栏拖拽）
- ✅ 实时显示节点状态（成功/失败/运行中/未执行）

---

## 🏗️ 技术架构

### 后端架构

#### 核心实体

**Workflow（工作流）**：
```python
@dataclass
class Workflow:
    id: str
    name: str
    description: str
    nodes: List[Node]  # 节点列表
    edges: List[Edge]  # 边列表
    created_at: datetime
    updated_at: datetime
```

**Node（节点）**：
```python
@dataclass
class Node:
    id: str
    type: NodeType  # HTTP, SQL, Script, Transform, etc.
    name: str
    config: Dict[str, Any]  # 节点配置
    position: Position  # 在画布上的位置
```

**Edge（边）**：
```python
@dataclass
class Edge:
    id: str
    source_node_id: str
    target_node_id: str
    condition: Optional[str]  # 条件表达式（可选）
```

---

#### Use Cases

**1. CreateWorkflowByChatUseCase**：
```python
class CreateWorkflowByChatUseCase:
    """通过对话创建工作流"""

    async def execute(self, user_message: str) -> Workflow:
        # 1. 使用 LangChain Agent 理解用户意图
        intent = await self.intent_parser.parse(user_message)

        # 2. 生成工作流结构
        workflow = await self.workflow_generator.generate(intent)

        # 3. 保存工作流
        await self.workflow_repo.save(workflow)

        return workflow
```

**2. UpdateWorkflowByChatUseCase**：
```python
class UpdateWorkflowByChatUseCase:
    """通过对话调整工作流"""

    async def execute(
        self,
        workflow_id: str,
        user_message: str
    ) -> Workflow:
        # 1. 获取现有工作流
        workflow = await self.workflow_repo.get(workflow_id)

        # 2. 使用 LangChain Agent 理解调整意图
        modification = await self.modification_parser.parse(
            user_message,
            workflow
        )

        # 3. 应用修改
        updated_workflow = await self.workflow_modifier.apply(
            workflow,
            modification
        )

        # 4. 保存更新
        await self.workflow_repo.update(updated_workflow)

        return updated_workflow
```

**3. UpdateWorkflowByDragUseCase**：
```python
class UpdateWorkflowByDragUseCase:
    """通过拖拽调整工作流"""

    async def execute(
        self,
        workflow_id: str,
        changes: WorkflowChanges
    ) -> Workflow:
        # 1. 获取现有工作流
        workflow = await self.workflow_repo.get(workflow_id)

        # 2. 应用拖拽修改
        workflow.apply_changes(changes)

        # 3. 验证工作流有效性
        self.workflow_validator.validate(workflow)

        # 4. 保存更新
        await self.workflow_repo.update(workflow)

        return workflow
```

**4. ExecuteWorkflowUseCase**：
```python
class ExecuteWorkflowUseCase:
    """执行工作流"""

    async def execute(
        self,
        workflow_id: str,
        input_data: Dict[str, Any]
    ) -> Run:
        # 1. 获取工作流
        workflow = await self.workflow_repo.get(workflow_id)

        # 2. 创建 Run
        run = Run.create(workflow_id=workflow_id, input_data=input_data)

        # 3. 执行工作流（按拓扑排序执行节点）
        await self.workflow_executor.execute(workflow, run)

        return run
```

---

### 前端架构

#### 核心组件

**1. WorkflowChat（对话界面）**：
```typescript
// 对话式创建和调整工作流
<WorkflowChat
  workflowId={workflowId}
  onWorkflowCreated={(workflow) => {
    // 跳转到工作流编辑器
    navigate(`/workflows/${workflow.id}/edit`);
  }}
  onWorkflowUpdated={(workflow) => {
    // 刷新工作流显示
    refetch();
  }}
/>
```

**2. WorkflowEditor（拖拽编辑器）**：
```typescript
// 使用 React Flow 实现
import ReactFlow from 'reactflow';

<WorkflowEditor
  workflow={workflow}
  onSave={(updatedWorkflow) => {
    updateWorkflow.mutate(updatedWorkflow);
  }}
/>
```

**3. WorkflowViewer（只读查看器）**：
```typescript
// 只读的工作流可视化
<WorkflowViewer
  workflow={workflow}
  readOnly={true}
/>
```

---

## 🚀 开发优先级

### 第一阶段：对话式创建和调整（P0）

**目标**：实现核心的对话式交互

**后端**：
- ✅ Workflow、Node、Edge 实体
- ✅ CreateWorkflowByChatUseCase
- ✅ UpdateWorkflowByChatUseCase
- ✅ ExecuteWorkflowUseCase
- ✅ LangChain Agent（理解用户意图）
- ✅ API 接口

**前端**：
- ✅ TypeScript 类型定义
- ✅ API 客户端
- ✅ TanStack Query Hooks
- ✅ WorkflowChat 组件（使用 V0 模板）
- ✅ WorkflowViewer 组件（只读，使用 React Flow）

**时间**：1-2 周

---

### 第二阶段：可视化拖拽调整（P1）

**目标**：实现拖拽编辑功能

**后端**：
- ✅ UpdateWorkflowByDragUseCase
- ✅ 工作流验证逻辑

**前端**：
- ✅ WorkflowEditor 组件（使用 React Flow + V0 模板）
- ✅ 节点拖拽
- ✅ 连线
- ✅ 节点属性编辑

**时间**：1 周

---

### 第三阶段：优化和增强（P2）

**目标**：提升用户体验

**功能**：
- ✅ 工作流模板库
- ✅ 工作流版本管理
- ✅ 工作流分享
- ✅ 工作流市场

**时间**：2-3 周

---

## 📝 API 设计

### 1. 创建工作流（表单式）

```http
POST /workflows

Request:
{
  "start": "GitHub Issue 列表",
  "goal": "发送到钉钉群",
  "description": "每天定时获取 GitHub Issue 并发送到钉钉群"
}

Response:
{
  "workflow": {
    "id": "wf_123",
    "name": "GitHub Issue 通知",
    "description": "每天定时获取 GitHub Issue 并发送到钉钉群",
    "nodes": [
      {
        "id": "node_1",
        "type": "http",
        "name": "获取 GitHub Issue",
        "config": {
          "url": "https://api.github.com/repos/{owner}/{repo}/issues",
          "method": "GET"
        },
        "position": { "x": 100, "y": 100 }
      },
      {
        "id": "node_2",
        "type": "transform",
        "name": "格式化消息",
        "config": {
          "script": "..."
        },
        "position": { "x": 100, "y": 250 }
      },
      {
        "id": "node_3",
        "type": "http",
        "name": "发送钉钉通知",
        "config": {
          "url": "{webhook_url}",
          "method": "POST"
        },
        "position": { "x": 100, "y": 400 }
      }
    ],
    "edges": [
      { "id": "edge_1", "source_node_id": "node_1", "target_node_id": "node_2" },
      { "id": "edge_2", "source_node_id": "node_2", "target_node_id": "node_3" }
    ],
    "status": "draft",
    "created_at": "2025-01-15T10:00:00Z",
    "updated_at": "2025-01-15T10:00:00Z"
  },
  "ai_message": "我为你创建了一个工作流，包含 3 个步骤：\n1. 从 GitHub 获取 Issue 列表\n2. 格式化为钉钉消息格式\n3. 发送到钉钉群\n\n你可以通过右侧的对话框调整工作流，或者直接拖拽节点。"
}
```

---

### 2. 调整工作流（对话式）

```http
POST /workflows/{workflow_id}/chat

Request:
{
  "message": "在发送钉钉之前，先保存到数据库"
}

Response:
{
  "workflow": {
    "id": "wf_123",
    "nodes": [...],  // 更新后的节点
    "edges": [...]   // 更新后的边
  },
  "ai_response": "好的，我在步骤 2 和 3 之间添加了..."
}
```

---

### 3. 调整工作流（拖拽式）

```http
PATCH /workflows/{workflow_id}

Request:
{
  "nodes": [...],  // 更新后的节点
  "edges": [...]   // 更新后的边
}

Response:
{
  "workflow": {
    "id": "wf_123",
    "nodes": [...],
    "edges": [...]
  }
}
```

---

### 4. 执行工作流

```http
POST /workflows/{workflow_id}/runs

Request:
{
  "input_data": {
    "repo_owner": "facebook",
    "repo_name": "react",
    "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=xxx"
  }
}

Response:
{
  "run": {
    "id": "run_456",
    "workflow_id": "wf_123",
    "status": "running",
    "node_executions": [
      {
        "id": "ne_1",
        "node_id": "node_1",
        "status": "pending",
        "input_data": {},
        "output_data": null
      },
      {
        "id": "ne_2",
        "node_id": "node_2",
        "status": "pending",
        "input_data": {},
        "output_data": null
      },
      {
        "id": "ne_3",
        "node_id": "node_3",
        "status": "pending",
        "input_data": {},
        "output_data": null
      }
    ],
    "started_at": "2025-01-15T10:05:00Z",
    "finished_at": null
  }
}
```

### 5. 获取执行状态（SSE）

```http
GET /workflows/{workflow_id}/runs/{run_id}/events

Response (Server-Sent Events):
event: node_execution_started
data: {"node_id": "node_1", "status": "running"}

event: node_execution_completed
data: {"node_id": "node_1", "status": "succeeded", "output_data": {...}}

event: node_execution_started
data: {"node_id": "node_2", "status": "running"}

event: node_execution_completed
data: {"node_id": "node_2", "status": "succeeded", "output_data": {...}}

event: node_execution_started
data: {"node_id": "node_3", "status": "running"}

event: node_execution_failed
data: {"node_id": "node_3", "status": "failed", "error_message": "Webhook URL is invalid"}

event: run_completed
data: {"run_id": "run_456", "status": "failed"}
```

---

## 🔧 技术选型

### 后端

- **LangChain Agent**：理解用户意图，生成工作流
- **工作流引擎**：执行工作流（拓扑排序 + 节点执行）
- **数据结构**：Workflow、Node、Edge

### 前端

- **React Flow**：工作流可视化和拖拽编辑
  - 官网：https://reactflow.dev/
  - 特点：最流行的 React 工作流库
  - 使用场景：扣子、Dify 等都基于类似的库

- **V0 模板**：
  - 聊天界面模板
  - 工作流编辑器模板

---

## ✅ 总结

### 核心变更

1. **从表单创建 → 对话创建**
2. **从 Agent → Workflow**
3. **新增可视化编辑器**

### 开发策略

1. **先对话，后拖拽**（验证核心价值）
2. **使用 V0 模板**（快速实现 UI）
3. **使用 React Flow**（专业的工作流库）

### 预期效果

- ✅ 降低使用门槛（自然语言交互）
- ✅ 提升用户体验（可视化反馈）
- ✅ 增强灵活性（对话 + 拖拽两种调整方式）
- ✅ 符合行业标准（类似扣子、Dify）
