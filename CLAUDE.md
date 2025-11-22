# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

**Feagent** is an enterprise-grade AI Agent orchestration and execution platform built with FastAPI, LangChain, and a clean DDD-lite architecture. The project is currently in **V2 stage** (智能任务识别与Coze集成).

---

## Critical Rules (MUST READ FIRST)

### 📚 Documentation Hierarchy

**ALWAYS consult documentation in this order:**

1. **Behavior Rules** → `.augment/rules/rule_name.md` (AI development discipline)
2. **Architecture** → `docs/开发规范/00-总体开发规范.md` (4-layer architecture)
3. **Backend Details** → `docs/开发规范/01-后端开发规范.md`
4. **Frontend Details** → `docs/开发规范/02-前端开发规范.md`
5. **Development Process** → `docs/开发规范/03-开发过程指导.md`
6. **Business Context** → `docs/需求分析.md`

Quick references:
- Backend: `.augment/rules/backend_specification.md`
- Frontend: `.augment/rules/frontend_specification.md`

### 🚨 Absolute Development Constraints

1. **Development Rhythm**:
   - Modify **maximum 2 files at a time**
   - Wait for user confirmation after each step
   - No batch operations without approval

2. **TDD is Mandatory**:
   - Red → Green → Refactor cycle
   - Domain layer coverage ≥ 80%
   - Application layer coverage ≥ 70%

3. **Architecture Order (STRICT)**:
   ```
   需求分析 → Domain → Ports → Infrastructure → Application → Interface
   ```
   **NEVER** start with database design!

4. **Dependency Direction (ONE-WAY ONLY)**:
   ```
   Interface → Application → Domain ← Infrastructure
   ```
   **Domain layer MUST NOT import**: SQLAlchemy, FastAPI, LangChain, or ANY framework

---

## Development Commands

### Backend

```bash
# Install dependencies
pip install -e ".[dev]"

# Database migrations
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1

# Run backend server
uvicorn src.interfaces.api.main:app --reload --port 8000

# Testing
pytest                                    # All tests
pytest tests/unit                         # Unit tests only
pytest tests/integration                  # Integration tests only
pytest tests/unit/domain/entities/test_agent.py -v  # Single file
pytest -k "test_create_agent"            # Single test by name
pytest --cov=src --cov-report=html       # Coverage report

# Code quality
ruff check .                             # Lint
ruff format .                            # Format
pyright src/                             # Type check
pre-commit run --all-files              # Run all pre-commit hooks
```

### Frontend

```bash
cd web

# Install dependencies
pnpm install

# Run dev server
pnpm dev

# Build
pnpm build

# Lint & format
pnpm lint
pnpm format
```

---

## Architecture Deep Dive

### Four-Layer Architecture

```
┌─────────────────────────────────────────────────┐
│              Interface Layer (接口层)             │
│  FastAPI Routes + DTO (Pydantic)                │
└────────────────┬────────────────────────────────┘
                 │ Request → Input
┌────────────────▼────────────────────────────────┐
│          Application Layer (应用层)               │
│  UseCases: 用例编排、事务边界                      │
│  - CreateAgentUseCase                           │
│  - ExecuteRunUseCase                            │
└────────────────┬────────────────────────────────┘
                 │ Ports (Protocol/ABC)
┌────────────────▼────────────────────────────────┐
│            Domain Layer (领域层)                  │
│  Entities: Agent, Run, Task, Workflow           │
│  ❌ NO FRAMEWORK IMPORTS ALLOWED                 │
└────────────────┬────────────────────────────────┘
                 │ Adapters implement Ports
┌────────────────▼────────────────────────────────┐
│       Infrastructure Layer (基础设施层)           │
│  ORM Models + Repository Implementations        │
└─────────────────────────────────────────────────┘
```

### Key Entities & Their Relationships

```
Agent (聚合根)
  ├─ id: str
  ├─ start: str (起点)
  ├─ goal: str (目标)
  └─ status: str

Run (聚合根)
  ├─ id: str
  ├─ agent_id: str → Agent
  ├─ status: RunStatus (PENDING/RUNNING/SUCCEEDED/FAILED)
  └─ tasks: List[Task]

Task
  ├─ id: str
  ├─ run_id: str → Run
  ├─ type: TaskType (HTTP/LLM/JAVASCRIPT/PROMPT)
  ├─ status: TaskStatus
  └─ input_data: dict

Workflow (V2新增)
  ├─ id: str
  ├─ name: str
  ├─ nodes: List[Node]
  └─ edges: List[Edge]
```

### Naming Conventions

| Pattern | Meaning | Example |
|---------|---------|---------|
| `get_xxx` | Must exist, else raise exception | `get_agent(id)` |
| `find_xxx` | Can return None | `find_agent(id)` |
| `check_xxx_exist` | Validate existence, raise on failure | `check_agent_exist(id)` |
| `exists_xxx` | Return bool | `exists_agent(id)` |
| `XxxUseCase` | Application use case | `CreateAgentUseCase` |
| `XxxInput` | Use case input | `CreateAgentInput` |
| `XxxRequest` | API request DTO | `CreateAgentRequest` |
| `XxxResponse` | API response DTO | `AgentResponse` |

---

## Common Development Patterns

### Creating a New Feature (Complete Flow)

**Example: Adding a new "Tool" entity**

```python
# Step 1: Domain Layer - Define Entity (src/domain/entities/tool.py)
from dataclasses import dataclass

@dataclass
class Tool:
    id: str
    name: str

    @staticmethod
    def create(name: str) -> "Tool":
        if not name:
            raise DomainError("name不能为空")
        return Tool(id=generate_id(), name=name)

# Step 2: Domain Layer - Define Port (src/domain/ports/tool_repository.py)
from typing import Protocol

class ToolRepository(Protocol):
    def save(self, tool: Tool) -> None: ...
    def find_by_id(self, id: str) -> Tool | None: ...

# Step 3: Infrastructure - Implement Repository
class SQLAlchemyToolRepository(ToolRepository):
    def __init__(self, session: Session):
        self.session = session

    def save(self, tool: Tool) -> None:
        model = ToolModel(id=tool.id, name=tool.name)
        self.session.add(model)
        self.session.commit()

# Step 4: Application - Create UseCase
class CreateToolUseCase:
    def __init__(self, repo: ToolRepository):
        self.repo = repo

    def execute(self, input_data: CreateToolInput) -> Tool:
        tool = Tool.create(name=input_data.name)
        self.repo.save(tool)
        return tool

# Step 5: Interface - Add API Endpoint
@router.post("/", response_model=ToolResponse)
async def create_tool(request: CreateToolRequest):
    use_case = CreateToolUseCase(repo=get_tool_repository())
    tool = use_case.execute(CreateToolInput(**request.dict()))
    return ToolResponse.from_entity(tool)
```

### SSE (Server-Sent Events) Pattern

```python
# Backend: Streaming execution status
@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str):
    async def event_generator():
        # Send events
        yield f"data: {json.dumps({'event': 'task_started', 'task_id': '...'})}\n\n"
        yield f"data: {json.dumps({'event': 'log', 'msg': '...'})}\n\n"
        yield "data: [DONE]\n\n"

    return EventSourceResponse(event_generator())

# Frontend: Consuming SSE
const eventSource = new EventSource(`/api/runs/${runId}/stream`);
eventSource.onmessage = (e) => {
  if (e.data === '[DONE]') {
    eventSource.close();
    return;
  }
  const event = JSON.parse(e.data);
  // Handle event
};
```

---

## Project-Specific Patterns

### LangChain Integration

```python
# Located in: src/lc/
# Example: LLM node executor
from langchain_openai import ChatOpenAI

class LLMNodeExecutor:
    def execute(self, config: dict, input_data: dict) -> dict:
        llm = ChatOpenAI(
            model=config["model"],
            temperature=config.get("temperature", 0.7)
        )
        messages = config["messages"]
        result = llm.invoke(messages)
        return {"content": result.content}
```

### State Machine Pattern

```python
# Run status transitions
class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

# Valid transitions
VALID_TRANSITIONS = {
    RunStatus.PENDING: [RunStatus.RUNNING, RunStatus.CANCELLED],
    RunStatus.RUNNING: [RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED],
}

def transition_to(self, new_status: RunStatus) -> None:
    if new_status not in VALID_TRANSITIONS.get(self.status, []):
        raise DomainError(f"Invalid transition: {self.status} → {new_status}")
    self.status = new_status
```

### Workflow Visualization (Frontend)

```typescript
// Located in: web/src/features/workflows/
import ReactFlow, { Node, Edge } from 'reactflow';

// Node types
const nodeTypes = {
  HTTP: HTTPNode,
  LLM: LLMNode,
  JAVASCRIPT: JavaScriptNode,
  CONDITION: ConditionNode,
};

// Usage
<ReactFlow
  nodes={nodes}
  edges={edges}
  nodeTypes={nodeTypes}
  onNodesChange={onNodesChange}
/>
```

---

## Testing Patterns

### Domain Layer Test Example

```python
# tests/unit/domain/entities/test_agent.py
def test_create_agent_with_valid_inputs_should_succeed():
    """测试：使用有效输入创建Agent应该成功"""
    agent = Agent.create(start="起点", goal="目标")

    assert agent.id is not None
    assert agent.start == "起点"
    assert agent.goal == "目标"
    assert agent.status == "active"

def test_create_agent_without_goal_should_raise_domain_error():
    """测试：创建Agent时缺少goal应该抛出DomainError"""
    with pytest.raises(DomainError, match="goal不能为空"):
        Agent.create(start="起点", goal="")
```

### API Layer Test Example

```python
# tests/integration/test_api.py
def test_create_agent_api(client: TestClient):
    """测试：POST /agents API"""
    response = client.post("/api/agents", json={
        "start": "起点",
        "goal": "目标"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["start"] == "起点"
    assert data["goal"] == "目标"
```

---

## Common Pitfalls & How to Avoid

### ❌ DON'T: Import frameworks in Domain layer
```python
# src/domain/entities/agent.py
from sqlalchemy import Column, String  # ❌ FORBIDDEN!
```

### ✅ DO: Keep Domain pure Python
```python
# src/domain/entities/agent.py
from dataclasses import dataclass  # ✅ CORRECT
```

### ❌ DON'T: Skip TDD
```
Implement → Write tests  # ❌ WRONG ORDER
```

### ✅ DO: Follow TDD cycle
```
Write test (Red) → Implement (Green) → Refactor  # ✅ CORRECT
```

### ❌ DON'T: Start with database design
```
Create DB tables → Design entities  # ❌ WRONG
```

### ✅ DO: Domain-first approach
```
Design entities → Define Ports → Implement ORM  # ✅ CORRECT
```

---

## Environment Variables

Required in `.env`:

```bash
# Database
DATABASE_URL=sqlite:///./agent_data.db  # or postgresql://...

# LLM
OPENAI_API_KEY=sk-...

# Application
LOG_LEVEL=INFO
CORS_ORIGINS=["http://localhost:5173"]
```

---

## Current Development Stage: V2

**Focus Areas:**
- [ ] Smart task classification (ClassifyTaskUseCase)
- [ ] Coze workflow import (Workflow entity + API)
- [ ] Tool lifecycle management (Tool entity + executors)
- [ ] Multi-LLM provider support (LLMProvider management)
- [ ] Frontend enhancements (NodePalette, ConfigPanel)

**Key Files for V2:**
- `src/application/use_cases/classify_task_use_case.py` (planned)
- `src/domain/entities/workflow.py` (planned)
- `src/domain/entities/tool.py` (planned)
- `docs/技术方案/03-Agent分阶段实施计划.md` (roadmap)

---

## Additional Resources

- **Full Documentation**: `docs/README.md`
- **Architecture Guide**: `docs/开发规范/00-总体开发规范.md`
- **Development Process**: `docs/开发规范/03-开发过程指导.md`
- **Technical Specs**: `docs/技术方案/` (5 detailed design docs)
- **Project Planning**: `docs/项目规划/` (roadmap + risk assessment)

---

**Last Updated**: 2025-01-22
**Project Stage**: V2 - 智能任务识别与Coze集成
**Total Documentation**: 100k+ words of enterprise-grade technical documentation
