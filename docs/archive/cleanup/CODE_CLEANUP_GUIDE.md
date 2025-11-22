# 代码整理指引

## 📋 概述

本文档帮助你理清哪些代码还有用，哪些代码不再需要（因为需求变更）。

---

## 🎯 核心变化

### 之前的需求（Agent 模式）

```
用户创建 Agent（start + goal）
    ↓
触发 Run
    ↓
LangChain Agent 自动生成 Task 并执行
```

**核心实体**：
- Agent
- Run
- Task

---

### 现在的需求（Workflow 模式）

```
用户创建 Workflow（start + goal + description）
    ↓
AI 生成 Workflow（包含 nodes 和 edges）
    ↓
用户调整 Workflow（对话或拖拽）
    ↓
触发 Run
    ↓
按拓扑排序执行 Workflow 的 nodes
```

**核心实体**：
- Workflow
- Node
- Edge
- Run
- NodeExecution

---

## 📊 代码分类

### ✅ 保留（仍然有用）

这些代码在新需求中仍然有用：

#### 1. Domain 层（部分保留）

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/domain/entities/run.py` | ⚠️ 需要修改 | 修改 `agent_id` 为 `workflow_id` |
| `src/domain/value_objects/` | ✅ 保留 | 值对象可以继续使用 |

**需要修改的地方**：
```python
# src/domain/entities/run.py

# 之前
@dataclass
class Run:
    agent_id: str  # ← 修改这里
    ...

# 现在
@dataclass
class Run:
    workflow_id: str  # ← 改为 workflow_id
    node_executions: List[NodeExecution] = field(default_factory=list)  # ← 新增
    ...
```

---

#### 2. Infrastructure 层（部分保留）

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/infrastructure/database/session.py` | ✅ 保留 | 数据库会话管理 |
| `src/infrastructure/database/base.py` | ✅ 保留 | ORM 基类 |
| `src/infrastructure/llm/` | ✅ 保留 | LLM 配置和客户端 |
| `src/infrastructure/database/models/run.py` | ⚠️ 需要修改 | 修改 `agent_id` 为 `workflow_id` |

---

#### 3. LangChain 层（部分保留）

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/lc/llm_factory.py` | ✅ 保留 | LLM 工厂 |
| `src/lc/tools/http_tool.py` | ✅ 保留 | HTTP 工具（可以用于 HTTP 节点） |
| `src/lc/tools/file_reader_tool.py` | ✅ 保留 | 文件读取工具 |

---

#### 4. API 层（部分保留）

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/interfaces/api/main.py` | ✅ 保留 | FastAPI 应用入口 |
| `src/interfaces/api/middleware/` | ✅ 保留 | 中间件（错误处理、日志等） |
| `src/interfaces/api/dependencies/` | ✅ 保留 | 依赖注入 |

---

#### 5. 配置和工具（全部保留）

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/config/` | ✅ 保留 | 配置管理 |
| `pyproject.toml` | ✅ 保留 | 项目配置 |
| `alembic/` | ✅ 保留 | 数据库迁移 |
| `tests/` | ⚠️ 部分保留 | 测试（需要更新） |

---

### 📦 归档（不再使用，但可能有参考价值）

这些代码在新需求中不再使用，但可能有参考价值：

#### 1. Domain 层（Agent 相关）

| 文件 | 状态 | 说明 | 参考价值 |
|------|------|------|---------|
| `src/domain/entities/agent.py` | 📦 归档 | Agent 实体 | ⚠️ 部分（实体设计参考） |
| `src/domain/entities/task.py` | 📦 归档 | Task 实体 | ⚠️ 部分（状态机参考） |
| `src/domain/ports/agent_repository.py` | 📦 归档 | Agent 仓储接口 | ✅ 有（Repository 设计参考） |
| `src/domain/ports/task_repository.py` | 📦 归档 | Task 仓储接口 | ✅ 有（Repository 设计参考） |

**建议操作**：
```bash
# 创建归档目录
mkdir -p src/archive/domain/entities
mkdir -p src/archive/domain/ports

# 移动文件
mv src/domain/entities/agent.py src/archive/domain/entities/
mv src/domain/entities/task.py src/archive/domain/entities/
mv src/domain/ports/agent_repository.py src/archive/domain/ports/
mv src/domain/ports/task_repository.py src/archive/domain/ports/
```

---

#### 2. Application 层（Agent 相关）

| 文件 | 状态 | 说明 | 参考价值 |
|------|------|------|---------|
| `src/application/use_cases/create_agent.py` | 📦 归档 | 创建 Agent | ✅ 有（Use Case 设计参考） |
| `src/application/use_cases/execute_run.py` | 📦 归档 | 执行 Run | ✅ 有（执行逻辑参考） |
| `src/application/use_cases/get_agent.py` | 📦 归档 | 获取 Agent | ✅ 有（查询逻辑参考） |
| `src/application/use_cases/update_agent.py` | 📦 归档 | 更新 Agent | ✅ 有（更新逻辑参考） |

**建议操作**：
```bash
# 创建归档目录
mkdir -p src/archive/application/use_cases

# 移动文件
mv src/application/use_cases/create_agent.py src/archive/application/use_cases/
mv src/application/use_cases/execute_run.py src/archive/application/use_cases/
mv src/application/use_cases/get_agent.py src/archive/application/use_cases/
mv src/application/use_cases/update_agent.py src/archive/application/use_cases/
```

---

#### 3. Infrastructure 层（Agent 相关）

| 文件 | 状态 | 说明 | 参考价值 |
|------|------|------|---------|
| `src/infrastructure/database/models/agent.py` | 📦 归档 | Agent ORM 模型 | ✅ 有（ORM 设计参考） |
| `src/infrastructure/database/models/task.py` | 📦 归档 | Task ORM 模型 | ✅ 有（ORM 设计参考） |
| `src/infrastructure/database/repositories/agent_repository.py` | 📦 归档 | Agent 仓储实现 | ✅ 有（Repository 实现参考） |
| `src/infrastructure/database/repositories/task_repository.py` | 📦 归档 | Task 仓储实现 | ✅ 有（Repository 实现参考） |

**建议操作**：
```bash
# 创建归档目录
mkdir -p src/archive/infrastructure/database/models
mkdir -p src/archive/infrastructure/database/repositories

# 移动文件
mv src/infrastructure/database/models/agent.py src/archive/infrastructure/database/models/
mv src/infrastructure/database/models/task.py src/archive/infrastructure/database/models/
mv src/infrastructure/database/repositories/agent_repository.py src/archive/infrastructure/database/repositories/
mv src/infrastructure/database/repositories/task_repository.py src/archive/infrastructure/database/repositories/
```

---

#### 4. LangChain 层（Agent 相关）

| 文件 | 状态 | 说明 | 参考价值 |
|------|------|------|---------|
| `src/lc/chains/plan_generator.py` | 📦 归档 | 计划生成器 | ✅ 有（LangChain Chain 设计参考） |
| `src/lc/agents/task_executor.py` | 📦 归档 | 任务执行器 | ✅ 有（LangChain Agent 设计参考） |

**建议操作**：
```bash
# 创建归档目录
mkdir -p src/archive/lc/chains
mkdir -p src/archive/lc/agents

# 移动文件
mv src/lc/chains/plan_generator.py src/archive/lc/chains/
mv src/lc/agents/task_executor.py src/archive/lc/agents/
```

---

#### 5. API 层（Agent 相关）

| 文件 | 状态 | 说明 | 参考价值 |
|------|------|------|---------|
| `src/interfaces/api/routes/agents.py` | 📦 归档 | Agent 路由 | ✅ 有（API 设计参考） |
| `src/interfaces/api/routes/runs.py` | ⚠️ 需要修改 | Run 路由 | ✅ 有（需要改为 Workflow Run） |
| `src/interfaces/api/dto/agent_dto.py` | 📦 归档 | Agent DTO | ✅ 有（DTO 设计参考） |

**建议操作**：
```bash
# 创建归档目录
mkdir -p src/archive/interfaces/api/routes
mkdir -p src/archive/interfaces/api/dto

# 移动文件
mv src/interfaces/api/routes/agents.py src/archive/interfaces/api/routes/
mv src/interfaces/api/dto/agent_dto.py src/archive/interfaces/api/dto/
```

---

#### 6. 测试（Agent 相关）

| 文件 | 状态 | 说明 | 参考价值 |
|------|------|------|---------|
| `tests/domain/entities/test_agent.py` | 📦 归档 | Agent 实体测试 | ✅ 有（测试设计参考） |
| `tests/domain/entities/test_task.py` | 📦 归档 | Task 实体测试 | ✅ 有（测试设计参考） |
| `tests/application/use_cases/test_create_agent.py` | 📦 归档 | 创建 Agent 测试 | ✅ 有（Use Case 测试参考） |
| `tests/application/use_cases/test_execute_run.py` | 📦 归档 | 执行 Run 测试 | ✅ 有（执行逻辑测试参考） |

**建议操作**：
```bash
# 创建归档目录
mkdir -p tests/archive/domain/entities
mkdir -p tests/archive/application/use_cases

# 移动文件
mv tests/domain/entities/test_agent.py tests/archive/domain/entities/
mv tests/domain/entities/test_task.py tests/archive/domain/entities/
mv tests/application/use_cases/test_create_agent.py tests/archive/application/use_cases/
mv tests/application/use_cases/test_execute_run.py tests/archive/application/use_cases/
```

---

### 🗑️ 可以删除（完全过时）

这些代码完全过时，可以直接删除：

| 文件 | 说明 |
|------|------|
| 暂无 | 建议先归档，确认不需要后再删除 |

---

## 📁 整理后的代码结构

```
src/
├── domain/
│   ├── entities/
│   │   ├── run.py                    ← 保留（需要修改）
│   │   └── ...
│   ├── ports/
│   │   ├── run_repository.py         ← 保留
│   │   └── ...
│   └── value_objects/                ← 保留
│
├── application/
│   └── use_cases/
│       └── ...                       ← 保留（需要新增 Workflow 相关）
│
├── infrastructure/
│   ├── database/
│   │   ├── session.py                ← 保留
│   │   ├── base.py                   ← 保留
│   │   ├── models/
│   │   │   ├── run.py                ← 保留（需要修改）
│   │   │   └── ...
│   │   └── repositories/
│   │       ├── run_repository.py     ← 保留
│   │       └── ...
│   └── llm/                          ← 保留
│
├── lc/
│   ├── llm_factory.py                ← 保留
│   └── tools/                        ← 保留
│
├── interfaces/
│   └── api/
│       ├── main.py                   ← 保留
│       ├── middleware/               ← 保留
│       ├── dependencies/             ← 保留
│       └── routes/
│           ├── runs.py               ← 保留（需要修改）
│           └── ...
│
├── config/                           ← 保留
│
└── archive/                          ← 归档目录
    ├── domain/
    │   ├── entities/
    │   │   ├── agent.py
    │   │   └── task.py
    │   └── ports/
    │       ├── agent_repository.py
    │       └── task_repository.py
    │
    ├── application/
    │   └── use_cases/
    │       ├── create_agent.py
    │       ├── execute_run.py
    │       ├── get_agent.py
    │       └── update_agent.py
    │
    ├── infrastructure/
    │   └── database/
    │       ├── models/
    │       │   ├── agent.py
    │       │   └── task.py
    │       └── repositories/
    │           ├── agent_repository.py
    │           └── task_repository.py
    │
    ├── lc/
    │   ├── chains/
    │   │   └── plan_generator.py
    │   └── agents/
    │       └── task_executor.py
    │
    └── interfaces/
        └── api/
            ├── routes/
            │   └── agents.py
            └── dto/
                └── agent_dto.py
```

---

## 🚀 快速整理脚本

### Windows PowerShell

```powershell
# 创建归档目录
New-Item -ItemType Directory -Force -Path "src/archive/domain/entities"
New-Item -ItemType Directory -Force -Path "src/archive/domain/ports"
New-Item -ItemType Directory -Force -Path "src/archive/application/use_cases"
New-Item -ItemType Directory -Force -Path "src/archive/infrastructure/database/models"
New-Item -ItemType Directory -Force -Path "src/archive/infrastructure/database/repositories"
New-Item -ItemType Directory -Force -Path "src/archive/lc/chains"
New-Item -ItemType Directory -Force -Path "src/archive/lc/agents"
New-Item -ItemType Directory -Force -Path "src/archive/interfaces/api/routes"
New-Item -ItemType Directory -Force -Path "src/archive/interfaces/api/dto"
New-Item -ItemType Directory -Force -Path "tests/archive/domain/entities"
New-Item -ItemType Directory -Force -Path "tests/archive/application/use_cases"

# 移动 Domain 层
Move-Item -Path "src/domain/entities/agent.py" -Destination "src/archive/domain/entities/" -ErrorAction SilentlyContinue
Move-Item -Path "src/domain/entities/task.py" -Destination "src/archive/domain/entities/" -ErrorAction SilentlyContinue
Move-Item -Path "src/domain/ports/agent_repository.py" -Destination "src/archive/domain/ports/" -ErrorAction SilentlyContinue
Move-Item -Path "src/domain/ports/task_repository.py" -Destination "src/archive/domain/ports/" -ErrorAction SilentlyContinue

# 移动 Application 层
Move-Item -Path "src/application/use_cases/create_agent.py" -Destination "src/archive/application/use_cases/" -ErrorAction SilentlyContinue
Move-Item -Path "src/application/use_cases/execute_run.py" -Destination "src/archive/application/use_cases/" -ErrorAction SilentlyContinue
Move-Item -Path "src/application/use_cases/get_agent.py" -Destination "src/archive/application/use_cases/" -ErrorAction SilentlyContinue
Move-Item -Path "src/application/use_cases/update_agent.py" -Destination "src/archive/application/use_cases/" -ErrorAction SilentlyContinue

# 移动 Infrastructure 层
Move-Item -Path "src/infrastructure/database/models/agent.py" -Destination "src/archive/infrastructure/database/models/" -ErrorAction SilentlyContinue
Move-Item -Path "src/infrastructure/database/models/task.py" -Destination "src/archive/infrastructure/database/models/" -ErrorAction SilentlyContinue
Move-Item -Path "src/infrastructure/database/repositories/agent_repository.py" -Destination "src/archive/infrastructure/database/repositories/" -ErrorAction SilentlyContinue
Move-Item -Path "src/infrastructure/database/repositories/task_repository.py" -Destination "src/archive/infrastructure/database/repositories/" -ErrorAction SilentlyContinue

# 移动 LangChain 层
Move-Item -Path "src/lc/chains/plan_generator.py" -Destination "src/archive/lc/chains/" -ErrorAction SilentlyContinue
Move-Item -Path "src/lc/agents/task_executor.py" -Destination "src/archive/lc/agents/" -ErrorAction SilentlyContinue

# 移动 API 层
Move-Item -Path "src/interfaces/api/routes/agents.py" -Destination "src/archive/interfaces/api/routes/" -ErrorAction SilentlyContinue
Move-Item -Path "src/interfaces/api/dto/agent_dto.py" -Destination "src/archive/interfaces/api/dto/" -ErrorAction SilentlyContinue

# 移动测试
Move-Item -Path "tests/domain/entities/test_agent.py" -Destination "tests/archive/domain/entities/" -ErrorAction SilentlyContinue
Move-Item -Path "tests/domain/entities/test_task.py" -Destination "tests/archive/domain/entities/" -ErrorAction SilentlyContinue
Move-Item -Path "tests/application/use_cases/test_create_agent.py" -Destination "tests/archive/application/use_cases/" -ErrorAction SilentlyContinue
Move-Item -Path "tests/application/use_cases/test_execute_run.py" -Destination "tests/archive/application/use_cases/" -ErrorAction SilentlyContinue

Write-Host "代码整理完成！" -ForegroundColor Green
```

---

## 📝 需要修改的文件清单

整理后，以下文件需要修改：

### 1. `src/domain/entities/run.py`

**修改内容**：
```python
# 修改前
@dataclass
class Run:
    agent_id: str
    ...

# 修改后
@dataclass
class Run:
    workflow_id: str
    node_executions: List[NodeExecution] = field(default_factory=list)
    ...
```

---

### 2. `src/infrastructure/database/models/run.py`

**修改内容**：
```python
# 修改前
class RunModel(Base):
    agent_id = Column(String, ForeignKey("agents.id"))
    ...

# 修改后
class RunModel(Base):
    workflow_id = Column(String, ForeignKey("workflows.id"))
    ...
```

---

### 3. `src/interfaces/api/routes/runs.py`

**修改内容**：
```python
# 修改前
@router.post("/agents/{agent_id}/runs")
async def create_run(agent_id: str):
    ...

# 修改后
@router.post("/workflows/{workflow_id}/runs")
async def create_run(workflow_id: str):
    ...
```

---

## ✅ 总结

- **保留**：基础设施代码（数据库、LLM、配置等）
- **归档**：Agent 相关代码（约 20+ 个文件）
- **删除**：暂无（建议先归档）
- **需要修改**：Run 相关代码（3 个文件）

**建议**：先归档，不要删除。如果后续确认不需要，再删除归档目录。
