---
type: "quick_reference"
target: "backend"
---

# 后端开发快速参考

> **项目**：Feagent
> **目标**：AI助手后端开发快速查询手册
> **详细规范**：查阅 `docs/开发规范/01-后端开发规范.md`

---

## 🏗️ 四层架构（强制遵守）

### 依赖方向（单向）
```
Interface → Application → Domain ← Infrastructure
          (仅通过Ports)
```

### 开发顺序（强制）
```
需求分析 → Domain实体 → Ports接口 → Infrastructure实现 → Application用例 → Interface API
```

**❌ 禁止**：Domain层导入SQLAlchemy/FastAPI/LangChain

---

## 💻 技术栈速查

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 编程语言 |
| FastAPI | 0.104+ | Web框架 |
| Pydantic | v2.5+ | 数据校验 |
| SQLAlchemy | 2.0+ | ORM |
| PostgreSQL | 14+ | 数据库 |
| LangChain | 1.0+ | AI编排 |

---

## 📝 命名约定

| 模式 | 含义 | 示例 |
|------|------|------|
| `get_xxx` | 必须存在，否则抛异常 | `get_agent(id)` |
| `find_xxx` | 允许返回None | `find_agent(id)` |
| `check_xxx_exist` | 校验存在性，抛异常 | `check_agent_exist(id)` |
| `exists_xxx` | 返回bool | `exists_agent(id)` |
| `XxxUseCase` | 用例类 | `CreateAgentUseCase` |
| `XxxInput` | 用例输入 | `CreateAgentInput` |
| `XxxRequest` | API请求DTO | `CreateAgentRequest` |
| `XxxResponse` | API响应DTO | `AgentResponse` |

---

## 🧪 TDD流程（强制）

```
1. 编写测试（Red）   → 失败
2. 实现功能（Green） → 通过
3. 重构（Refactor）  → 优化
4. 验证覆盖率        → 达标
```

**覆盖率要求**：
- Domain层 ≥ 80%
- Application层 ≥ 70%
- Infrastructure层 ≥ 60%

---

## 🗂️ 目录结构

```
src/
├── domain/
│   ├── entities/          # 实体（@dataclass，纯Python）
│   ├── value_objects/     # 值对象
│   ├── services/          # 领域服务
│   └── ports/            # 端口接口（Protocol）
├── application/
│   └── use_cases/        # 用例（XxxUseCase）
├── infrastructure/
│   ├── database/         # ORM模型、Repository实现
│   └── external/         # 外部服务适配器
└── interfaces/
    └── api/              # FastAPI路由、DTO
```

---

## 🔍 常见问题快速查询

### Q: 如何创建新的实体？

```python
# src/domain/entities/workflow.py
from dataclasses import dataclass

@dataclass
class Workflow:
    id: str
    name: str

    @staticmethod
    def create(name: str) -> "Workflow":
        if not name:
            raise DomainError("name不能为空")
        return Workflow(id=generate_id(), name=name)
```

### Q: 如何定义端口？

```python
# src/domain/ports/workflow_repository.py
from typing import Protocol

class WorkflowRepository(Protocol):
    def save(self, workflow: Workflow) -> None: ...
    def find_by_id(self, id: str) -> Workflow | None: ...
```

### Q: 如何实现用例？

```python
# src/application/use_cases/create_workflow_use_case.py
class CreateWorkflowUseCase:
    def __init__(self, repo: WorkflowRepository):
        self.repo = repo

    def execute(self, input_data: CreateWorkflowInput) -> Workflow:
        workflow = Workflow.create(name=input_data.name)
        self.repo.save(workflow)
        return workflow
```

### Q: 如何创建API端点？

```python
# src/interfaces/api/routes/workflows.py
@router.post("/", response_model=WorkflowResponse)
async def create_workflow(request: CreateWorkflowRequest):
    use_case = CreateWorkflowUseCase(repo=get_repo())
    workflow = use_case.execute(CreateWorkflowInput(**request.dict()))
    return WorkflowResponse.from_entity(workflow)
```

---

## ⚠️ 常见错误

### ❌ 错误1：Domain层导入框架
```python
from sqlalchemy import Column, String  # ❌ 禁止
```

### ❌ 错误2：跳过TDD
```
实现功能 → 补充测试  # ❌ 禁止
```

### ❌ 错误3：Application依赖实现
```python
from src.infrastructure.database.repositories import XXX  # ❌ 禁止
# 应该依赖 src.domain.ports.XXX
```

---

## 📚 详细规范

完整规范请查阅：
- `docs/开发规范/01-后端开发规范.md`（详细内容）
- `docs/开发规范/00-总体开发规范.md`（架构总览）
- `docs/开发规范/03-开发过程指导.md`（完整流程）
