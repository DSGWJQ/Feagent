# 工作流文档索引

## 📋 概述

本文档索引了所有工作流相关的文档，方便快速查找。

---

## 🎯 核心文档

### 1. 项目规则

| 文档 | 说明 | 路径 |
|------|------|------|
| **工作流项目规则** | 核心规则、技术栈、架构、开发优先级 | `.augment/rules/workflow_rules.md` |
| **原项目规则** | 原 Agent 项目规则（参考） | `.augment/rules/rule_name.md` |

---

### 2. 需求文档

| 文档 | 说明 | 路径 |
|------|------|------|
| **工作流需求变更说明** | 新需求详细说明、对比、核心功能 | `docs/workflow_requirements.md` |
| **原需求分析** | 原 Agent 需求分析（参考） | `docs/需求分析.md` |

---

### 3. 设计文档

| 文档 | 说明 | 路径 |
|------|------|------|
| **后端修改分析** | 后端需要修改的地方、新增实体、Use Cases | `docs/backend_changes_for_workflow.md` |
| **API 设计** | 所有 API 接口详细设计 | `docs/workflow_api_design.md` |
| **前端设计** | 所有前端组件、页面、Hooks、类型定义 | `docs/workflow_frontend_design.md` |

---

### 4. 实施文档

| 文档 | 说明 | 路径 |
|------|------|------|
| **实现计划** | 分阶段实现计划、TDD 步骤、验收标准 | `docs/workflow_implementation_plan.md` |
| **开发规范** | 原开发规范（参考） | `docs/develop_document.md` |

---

## 📊 文档关系图

```
工作流项目规则 (.augment/rules/workflow_rules.md)
    ↓
    ├─→ 工作流需求变更说明 (docs/workflow_requirements.md)
    │       ↓
    │       ├─→ 后端修改分析 (docs/backend_changes_for_workflow.md)
    │       │       ↓
    │       │       └─→ API 设计 (docs/workflow_api_design.md)
    │       │
    │       └─→ 前端设计 (docs/workflow_frontend_design.md)
    │
    └─→ 实现计划 (docs/workflow_implementation_plan.md)
            ↓
            └─→ 开始开发
```

---

## 🎯 快速导航

### 我想了解...

#### 1. **核心需求是什么？**
→ 阅读 `docs/workflow_requirements.md`

**核心内容**：
- 表单创建工作流（起点 + 终点 + 描述）
- AI 生成最小可行工作流
- 对话/拖拽调整工作流
- 执行工作流 + 状态可视化

---

#### 2. **技术栈是什么？**
→ 阅读 `.augment/rules/workflow_rules.md` 第 2 节

**核心技术**：
- **后端**：Python 3.11+ + FastAPI + SQLAlchemy + LangChain
- **前端**：React 19 + TypeScript + Ant Design + React Flow
- **开发模式**：TDD + DDD

---

#### 3. **后端需要修改哪些地方？**
→ 阅读 `docs/backend_changes_for_workflow.md`

**核心修改**：
- **新增实体**：Workflow, Node, Edge, NodeExecution
- **新增 Use Cases**：CreateWorkflowUseCase, UpdateWorkflowByChatUseCase, ExecuteWorkflowUseCase
- **新增 LangChain 组件**：WorkflowGeneratorChain, WorkflowModifierChain, WorkflowExecutor

---

#### 4. **API 接口有哪些？**
→ 阅读 `docs/workflow_api_design.md`

**核心接口**：
- `POST /workflows` - 创建工作流
- `POST /workflows/{id}/chat` - 对话式调整工作流
- `PATCH /workflows/{id}` - 拖拽式调整工作流
- `POST /workflows/{id}/runs` - 执行工作流
- `GET /workflows/{id}/runs/{run_id}/events` - SSE 实时状态更新

---

#### 5. **前端有哪些组件？**
→ 阅读 `docs/workflow_frontend_design.md`

**核心组件**：
- **CreateWorkflowModal** - 创建工作流弹窗
- **WorkflowCanvas** - 工作流画布（React Flow）
- **NodeWithStatus** - 带状态的节点
- **WorkflowChat** - 对话框
- **WorkflowEditor** - 工作流编辑器

---

#### 6. **如何开始开发？**
→ 阅读 `docs/workflow_implementation_plan.md`

**开发步骤**：
1. **第一阶段**：表单创建 + 工作流生成（1-2 天）
   - Domain 层（TDD）
   - LangChain 层
   - Application 层（TDD）
   - API 层
   - 前端

2. **第二阶段**：对话/拖拽调整（1-2 天）
3. **第三阶段**：执行工作流 + 状态可视化（1-2 天）

---

## 📝 核心概念速查

### 工作流（Workflow）
```
用户填写表单（起点 + 终点 + 描述）
    ↓
AI 生成工作流（包含 nodes 和 edges）
    ↓
用户通过对话或拖拽调整工作流
    ↓
执行工作流
    ↓
实时显示每个节点的状态
```

---

### 节点类型（NodeType）
- **HTTP**：HTTP 请求
- **SQL**：SQL 查询
- **Script**：Python 脚本
- **Transform**：数据转换

---

### 节点状态（NodeExecutionStatus）
- **pending**：未执行（灰色 ⏸️）
- **running**：运行中（黄色 ⏳）
- **succeeded**：成功（绿色 ✅）
- **failed**：失败（红色 ❌）
- **skipped**：跳过

---

### 工作流状态（WorkflowStatus）
- **draft**：草稿
- **active**：激活
- **archived**：归档

---

## 🎯 开发检查清单

### 第一阶段：表单创建 + 工作流生成

**后端**：
- [ ] Workflow 实体（TDD）
- [ ] Node 实体（TDD）
- [ ] Edge 实体（TDD）
- [ ] WorkflowRepository（Port + Infrastructure）
- [ ] WorkflowGeneratorChain（LangChain）
- [ ] CreateWorkflowUseCase（TDD）
- [ ] API 接口（POST /workflows）
- [ ] 数据库迁移（Alembic）

**前端**：
- [ ] TypeScript 类型定义（workflow.ts）
- [ ] API 客户端（workflowsApi.ts）
- [ ] TanStack Query Hooks（useWorkflows.ts）
- [ ] CreateWorkflowModal 组件
- [ ] WorkflowViewer 组件（只读）
- [ ] 测试（API、Hooks、组件）

---

### 第二阶段：对话/拖拽调整

**后端**：
- [ ] UpdateWorkflowByChatUseCase（TDD）
- [ ] UpdateWorkflowByDragUseCase（TDD）
- [ ] WorkflowModifierChain（LangChain）
- [ ] API 接口（POST /workflows/{id}/chat, PATCH /workflows/{id}）

**前端**：
- [ ] WorkflowEditor 组件
- [ ] WorkflowCanvas 组件（React Flow）
- [ ] WorkflowChat 组件
- [ ] 节点拖拽功能
- [ ] 连线功能
- [ ] 测试

---

### 第三阶段：执行工作流 + 状态可视化

**后端**：
- [ ] NodeExecution 实体（TDD）
- [ ] ExecuteWorkflowUseCase（TDD）
- [ ] WorkflowExecutor（拓扑排序 + 节点执行）
- [ ] SSE 实时推送
- [ ] API 接口（POST /workflows/{id}/runs, GET /workflows/{id}/runs/{run_id}/events）

**前端**：
- [ ] NodeWithStatus 组件
- [ ] SSE 客户端（useWorkflowRun Hook）
- [ ] 实时更新节点状态
- [ ] 测试

---

## 📚 参考资料

### 技术文档
- **React Flow**：https://reactflow.dev/
- **LangChain**：https://python.langchain.com/
- **FastAPI**：https://fastapi.tiangolo.com/
- **TanStack Query**：https://tanstack.com/query/latest

### 类似产品
- **扣子（Coze）**：https://www.coze.com/
- **Dify**：https://dify.ai/
- **n8n**：https://n8n.io/

---

## ✅ 总结

本文档索引了所有工作流相关的文档，包括：

1. ✅ **核心规则**：`.augment/rules/workflow_rules.md`
2. ✅ **需求文档**：`docs/workflow_requirements.md`
3. ✅ **设计文档**：
   - `docs/backend_changes_for_workflow.md`
   - `docs/workflow_api_design.md`
   - `docs/workflow_frontend_design.md`
4. ✅ **实施文档**：`docs/workflow_implementation_plan.md`

所有文档已准备就绪，可以开始开发！

---

## 🚀 下一步

**准备好开始开发了吗？**

请按照以下顺序阅读文档：

1. **先读**：`docs/workflow_requirements.md`（了解需求）
2. **再读**：`.augment/rules/workflow_rules.md`（了解规则）
3. **然后读**：`docs/workflow_implementation_plan.md`（了解开发步骤）
4. **开始开发**：按照实现计划，从第一阶段开始

**祝开发顺利！** 🎉
