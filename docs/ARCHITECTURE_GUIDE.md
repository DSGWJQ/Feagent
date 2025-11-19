# 四层架构开发指南（核心精简版）

> **用途**：开发时快速查阅，防止偏离架构规范
> **完整规范**：详见 [DEVELOPMENT_GUIDE.md](./DEVELOPMENT_GUIDE.md)

---

## 📐 四层架构图

```
┌──────────────────────────────────────────────────────────────┐
│                  Interface 层（API 入口）                      │
│  路径：src/interfaces/api/                                    │
│  职责：接收外部请求，返回响应                                  │
│  包含：routes/（路由）、dto/（DTO）、main.py（FastAPI 入口）   │
└──────────────────────────────────────────────────────────────┘
                           ↓ 调用
┌──────────────────────────────────────────────────────────────┐
│                 Application 层（业务编排）                     │
│  路径：src/application/use_cases/                             │
│  职责：业务流程编排，调用 Domain 服务和 Repository             │
│  命名：所有类以 UseCase 结尾（如 CreateAgentUseCase）          │
└──────────────────────────────────────────────────────────────┘
                           ↓ 调用
┌──────────────────────────────────────────────────────────────┐
│                   Domain 层（领域核心）                        │
│  路径：src/domain/                                            │
│  职责：领域逻辑核心，不依赖任何框架                            │
│  包含：entities/、value_objects/、services/、ports/           │
│  约束：❌ 禁止导入 SQLAlchemy、FastAPI、LangChain            │
└──────────────────────────────────────────────────────────────┘
                           ↑ 实现
┌──────────────────────────────────────────────────────────────┐
│                Infrastructure 层（基础设施）                   │
│  路径：src/infrastructure/                                    │
│  职责：实现 Domain 层的 Ports 接口                            │
│  包含：database/（ORM、Repository）、外部服务适配器            │
└──────────────────────────────────────────────────────────────┘
```

---

## 🎯 各层职责说明

### 1. Interface 层（API 入口）

**职责**：
- 接收所有外部请求（HTTP、WebSocket、SSE）
- 调用 Application 层的 Use Cases
- 将 Domain 异常映射为 HTTP 错误码

**包含**：
- `routes/`：FastAPI 路由（agents.py、runs.py）
- `dto/`：数据传输对象（Request/Response）
- `main.py`：FastAPI 应用入口

**示例**：
```python
# src/interfaces/api/routes/agents.py
@router.post("/", response_model=AgentResponse)
async def create_agent(request: CreateAgentRequest):
    # 1. 调用 Use Case
    use_case = CreateAgentUseCase(agent_repository=repo)
    agent = use_case.execute(CreateAgentInput(...))

    # 2. 转换为 DTO 返回
    return AgentResponse.from_entity(agent)
```

---

### 2. Application 层（业务编排）

**职责**：
- 业务流程编排（调用 Domain 服务、Repository）
- 事务边界管理
- DTO ⇄ Entity 转换
- 业务规则校验（如数据是否存在）

**命名规范**：
- 所有类以 `UseCase` 结尾（如 `CreateAgentUseCase`）
- 输入参数类以 `Input` 结尾（如 `CreateAgentInput`）

**示例**：
```python
# src/application/use_cases/create_agent.py
class CreateAgentUseCase:
    def __init__(self, agent_repository: AgentRepository):
        self.agent_repository = agent_repository

    def execute(self, input_data: CreateAgentInput) -> Agent:
        # 1. 业务规则校验
        if not input_data.goal:
            raise DomainError("goal 不能为空")

        # 2. 创建 Domain 实体
        agent = Agent.create(
            start=input_data.start,
            goal=input_data.goal,
            name=input_data.name
        )

        # 3. 保存到数据库
        self.agent_repository.save(agent)

        return agent
```

---

### 3. Domain 层（领域核心）

**职责**：
- 领域逻辑核心（业务规则、不变式）
- 实体状态管理（状态机）
- 定义 Ports 接口（Repository、外部服务）

**包含**：
- `entities/`：实体（Agent、Run、Task）
- `value_objects/`：值对象（ExecutionContext、TaskEvent）
- `services/`：领域服务（ExecutionEngine、TaskExecutor）
- `ports/`：Ports 接口（AgentRepository、RunRepository）

**约束**：
- ❌ **禁止导入任何框架**（SQLAlchemy、FastAPI、LangChain）
- ❌ **禁止直接调用其他领域服务**（须通过 Application 层协调）
- ✅ **只能定义 Ports 接口**，由 Infrastructure 层实现

**示例**：
```python
# src/domain/entities/agent.py
@dataclass
class Agent:
    id: str
    start: str
    goal: str
    name: str | None

    @staticmethod
    def create(start: str, goal: str, name: str | None = None) -> "Agent":
        # 业务规则校验
        if not goal:
            raise DomainError("goal 不能为空")

        return Agent(
            id=str(uuid.uuid4()),
            start=start,
            goal=goal,
            name=name or f"Agent-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )
```

---

### 4. Infrastructure 层（基础设施）

**职责**：
- 实现 Domain 层定义的 Ports 接口
- 提供基础设施支持（数据库、缓存、外部服务）
- 配置类、用户鉴权、BaseEntity 等抽象组件

**包含**：
- `database/models.py`：ORM 模型（SQLAlchemy）
- `database/repositories/`：Repository 实现
- 外部服务适配器：LLM 客户端、消息队列、缓存等

**示例**：
```python
# src/infrastructure/database/repositories/agent_repository.py
class SQLAlchemyAgentRepository(AgentRepository):
    def __init__(self, session: Session):
        self.session = session

    def save(self, agent: Agent) -> None:
        # 将 Domain 实体转换为 ORM 模型
        model = AgentModel(
            id=agent.id,
            start=agent.start,
            goal=agent.goal,
            name=agent.name
        )
        self.session.add(model)
        self.session.commit()
```

---

## 🔄 DTO 转换机制

### 数据流向

```
前端请求
  ↓
CreateAgentRequest (DTO)  ← Interface 层接收
  ↓
CreateAgentInput          ← Application 层转换
  ↓
Agent (Entity)            ← Domain 层创建
  ↓
AgentModel (ORM)          ← Infrastructure 层保存
  ↓
Agent (Entity)            ← Infrastructure 层返回
  ↓
AgentResponse (DTO)       ← Interface 层转换
  ↓
前端响应
```

### 转换规则

1. **Request → Input**（Interface → Application）
   ```python
   input_data = CreateAgentInput(
       start=request.start,
       goal=request.goal,
       name=request.name
   )
   ```

2. **Input → Entity**（Application → Domain）
   ```python
   agent = Agent.create(
       start=input_data.start,
       goal=input_data.goal,
       name=input_data.name
   )
   ```

3. **Entity → ORM**（Domain → Infrastructure）
   ```python
   model = AgentModel(
       id=agent.id,
       start=agent.start,
       goal=agent.goal,
       name=agent.name
   )
   ```

4. **Entity → Response**（Domain → Interface）
   ```python
   return AgentResponse(
       id=agent.id,
       start=agent.start,
       goal=agent.goal,
       name=agent.name,
       created_at=agent.created_at
   )
   ```

---

## ✅ 三层校验机制

### 1. API 层校验（Interface 层）
- **职责**：基本数据校验（非空、类型、范围）
- **工具**：Pydantic 自动校验
- **示例**：
  ```python
  class CreateAgentRequest(BaseModel):
      start: str = Field(..., min_length=1, max_length=500)
      goal: str = Field(..., min_length=1, max_length=500)
      name: str | None = Field(None, max_length=100)
  ```

### 2. Application 层校验
- **职责**：业务规则校验（如数据是否存在）
- **示例**：
  ```python
  # 检查 Agent 是否存在
  agent = self.agent_repository.find_by_id(agent_id)
  if not agent:
      raise NotFoundError(f"Agent {agent_id} 不存在")
  ```

### 3. Domain 层校验
- **职责**：领域不变式校验（实体一致性）
- **示例**：
  ```python
  @staticmethod
  def create(start: str, goal: str) -> "Agent":
      if not goal:
          raise DomainError("goal 不能为空")
      if len(goal) > 500:
          raise DomainError("goal 长度不能超过 500 字符")
      return Agent(...)
  ```

---

## 🏗️ 聚合根概念

### 什么是聚合根？
当两个表存在包含关系时（如 Agent 与其下属 Tasks），需构建聚合根将多个实体打包返回。

### 示例场景
查询 Agent 时，同时返回 Agent 信息及其关联的 Tasks 列表。

### 实现方式
```python
# src/interfaces/api/dto/agent_dto.py
class AgentResponse(BaseModel):
    id: str
    start: str
    goal: str
    name: str
    tasks: list[TaskResponse]  # 聚合根：包含关联的 Tasks

    @classmethod
    def from_entity(cls, agent: Agent, tasks: list[Task]) -> "AgentResponse":
        return cls(
            id=agent.id,
            start=agent.start,
            goal=agent.goal,
            name=agent.name,
            tasks=[TaskResponse.from_entity(task) for task in tasks]
        )
```

---

## 🚫 常见错误

### ❌ 错误 1：Domain 层导入框架
```python
# ❌ 错误
from sqlalchemy import Column, String
from src.domain.entities.agent import Agent
```

### ✅ 正确做法
```python
# ✅ 正确：Domain 层只用纯 Python
from dataclasses import dataclass

@dataclass
class Agent:
    id: str
    start: str
    goal: str
```

### ❌ 错误 2：先设计数据库
```
❌ 数据库设计 → Domain 层 → ORM 模型
```

### ✅ 正确做法
```
✅ 需求分析 → Domain 层 → Ports → Infrastructure → 数据库迁移
```

### ❌ 错误 3：Application 层直接导入 Infrastructure
```python
# ❌ 错误
from src.infrastructure.database.repositories import SQLAlchemyAgentRepository

class CreateAgentUseCase:
    def __init__(self):
        self.repo = SQLAlchemyAgentRepository()  # 直接依赖具体实现
```

### ✅ 正确做法
```python
# ✅ 正确：依赖 Ports 接口
from src.domain.ports import AgentRepository

class CreateAgentUseCase:
    def __init__(self, agent_repository: AgentRepository):  # 依赖接口
        self.agent_repository = agent_repository
```

---

## 📚 快速参考

| 层次 | 路径 | 职责 | 命名规范 | 禁止事项 |
|------|------|------|----------|----------|
| **Interface** | `src/interfaces/api/` | 接收请求，返回响应 | Request/Response | 不能包含业务逻辑 |
| **Application** | `src/application/use_cases/` | 业务编排 | XxxUseCase | 不能直接导入 Infrastructure |
| **Domain** | `src/domain/` | 领域逻辑 | Entity/ValueObject | 不能导入任何框架 |
| **Infrastructure** | `src/infrastructure/` | 基础设施 | XxxRepository | 不能被 Domain 导入 |

---

**最后更新**：2025-11-19
