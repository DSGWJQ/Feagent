# DDD 边界自检清单（Codebase-Specific）

> **用途**: 重构实施与 Code Review 时的 DDD 架构合规性检查
> **范围**: 工作流统一架构重构（五个 Phase）
> **审查者**: Codex / Claude / 人工
> **更新日期**: 2025-01-01

---

## 一、DDD 层依赖规则（Layer Dependency Rules）

### 1.1 Interface Layer（`src/interfaces/**`）

#### ✅ CAN import
- `src/application/**`（UseCase / Orchestrator / Application DTO）
- `pydantic`, `fastapi`, `sqlalchemy`（HTTP/DI/序列化/会话管理）
- （过渡期）`src/domain.exceptions` 仅用于 HTTP error mapping

#### ❌ CANNOT import
- `src/domain/agents/**`
  ```python
  # ❌ 违例（现存）
  from src.domain.agents.conversation_agent import ConversationAgent
  from src.domain.agents.workflow_agent import WorkflowAgent
  ```
- `src/domain/services/**`
  ```python
  # ❌ 违例
  from src.domain.services.workflow_executor import WorkflowExecutor
  from src.domain.services.event_bus import EventBus
  ```
- `src/infrastructure/**` 的业务实现
  ```python
  # ❌ 违例
  from src.infrastructure.executors import create_executor_registry
  from src.infrastructure.database.repositories.workflow_repository import SQLAlchemyWorkflowRepository
  ```

#### 🚨 Violation Patterns
- Route handler 内出现业务编排/分支/循环/重试/校验链
- 在 routes/dependencies 中实例化 Domain Agent/Service
- 以 EventBus middleware 作为治理边界

---

### 1.2 Application Layer（`src/application/**`）

#### ✅ CAN import
- `src/domain/**`（实体、值对象、domain services、domain ports）
- 标准库（`asyncio`, `dataclasses`, `typing`）

#### ❌ CANNOT import
- `src/infrastructure/**`
  ```python
  # ❌ 违例
  from src.infrastructure.executors import create_executor_registry
  from src.infrastructure.database.repositories.workflow_repository import SQLAlchemyWorkflowRepository
  ```
- `fastapi` / `pydantic` / `sqlalchemy.orm.Session`
- `src.interfaces.**`

#### 🎯 DI Rule
- Application 只接受 **Ports/Protocols**（在 Domain 定义）作为构造参数
- 对象实例化发生在 composition root（`src/interfaces/api/main.py`）

---

### 1.3 Domain Layer（`src/domain/**`）

#### ✅ CAN import
- 纯 Python 标准库
- Domain 内部模块：entities/value_objects/exceptions/services/ports

#### ❌ CANNOT import
- `src.infrastructure/**`, `src.interfaces/**`
- `fastapi`, `sqlalchemy`, `requests`, 具体 LLM SDK
- IO/格式解析库
  ```python
  # ❌ 违例（现存）
  import yaml
  from pathlib import Path

  # 文件位置: src/domain/services/workflow_dependency_graph.py
  # 文件位置: src/domain/agents/node_definition.py
  ```

#### 🚨 高风险现存问题
| 文件 | 问题 | 影响 |
|------|------|------|
| `src/domain/services/workflow_dependency_graph.py` | 使用 `yaml` + `Path` | Domain 混入文件/格式解析 |
| `src/domain/agents/node_definition.py` | 使用 `yaml` + `Path` | Domain Agent 包含 IO |
| `src/domain/services/workflow_executor.py` | 默认实现/模拟输出 fallback | Domain 混入执行细节 |

---

### 1.4 Infrastructure Layer（`src/infrastructure/**`）

#### ✅ CAN import
- `src/domain/**`（实现 domain ports、使用 domain entities）
- 第三方库：DB/HTTP/LLM/文件系统等
- 标准库

#### ❌ CANNOT import
- `src.interfaces/**`
- `src.application/**`（避免反向依赖）

---

## 二、Critical DDD Checkpoints by Phase

### Phase 1: 统一 Workflow 执行入口

#### 🔴 High-Risk Files
```
src/interfaces/api/routes/workflows.py
src/application/use_cases/execute_workflow.py
src/interfaces/api/main.py
src/interfaces/api/services/workflow_executor_adapter.py
```

#### ❌ Imports to Avoid
```python
# 在 src/interfaces/api/routes/workflows.py
from src.application.use_cases.execute_workflow import ExecuteWorkflowUseCase  # 如已改为 Orchestrator
from src.domain.services.workflow_executor import WorkflowExecutor

# 在 Application Orchestrator
from src.infrastructure.executors import create_executor_registry
from src.infrastructure.database.repositories.workflow_repository import SQLAlchemyWorkflowRepository
```

#### ✅ Correct DI Pattern
```python
# src/interfaces/api/main.py (composition root)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 创建 Infrastructure 适配器
    executor_registry = create_executor_registry()
    workflow_repo = SQLAlchemyWorkflowRepository(session_factory)

    # 注入到 Application Orchestrator
    orchestrator = WorkflowExecutionOrchestrator(
        workflow_repository=workflow_repo,  # Port
        executor_registry=executor_registry,  # Port
    )

    app.state.workflow_orchestrator = orchestrator
    yield

# src/interfaces/api/routes/workflows.py
@router.post("/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: str,
    request: ExecuteWorkflowRequest,
    orchestrator: WorkflowExecutionOrchestrator = Depends(get_orchestrator)
):
    return await orchestrator.execute(workflow_id, request)
```

---

### Phase 2: 移除 Duplicated DAG 执行

#### 🔴 High-Risk Files
```
src/domain/agents/workflow_agent.py
src/domain/services/workflow_executor.py
src/domain/services/workflow_dependency_graph.py
```

#### ❌ Imports to Avoid
```python
# 在 src/domain/agents/workflow_agent.py (瘦适配器)
from src.infrastructure...  # 任何 Infrastructure 导入
import yaml
from pathlib import Path

# 在新的 Domain Engine (src/domain/services/workflow_engine.py)
import yaml
import requests
import sqlalchemy
import fastapi
```

#### ✅ Correct Dependency Shape
```python
# Domain Engine: 只依赖 Ports
class WorkflowEngine:
    def __init__(
        self,
        executor_registry: NodeExecutorRegistry,  # Port
        event_sink: ExecutionEventSink,  # Port
    ):
        self.executor_registry = executor_registry
        self.event_sink = event_sink

    async def execute(self, workflow: Workflow, context: ExecutionContext):
        # 纯业务逻辑: 拓扑排序 + 节点执行
        ...
```

---

### Phase 3: Capabilities 单一事实来源

#### 🔴 High-Risk Files
```
src/domain/services/unified_definition.py
src/domain/services/tool_engine.py
src/infrastructure/executors/__init__.py
```

#### ❌ Imports to Avoid
```python
# 在 Domain registry/models
import yaml
from pathlib import Path

# ✅ YAML 加载必须在 Infrastructure
# src/infrastructure/definitions/yaml_capability_source.py
```

#### ✅ Correct DI Pattern
```python
# Application Layer
class CapabilityCatalogService:
    def __init__(
        self,
        sources: list[CapabilityDefinitionSource],  # Port
    ):
        self.sources = sources

    def load_all(self) -> list[CapabilityDefinition]:
        capabilities = []
        for source in self.sources:
            capabilities.extend(source.load())
        return capabilities

# Composition Root
yaml_source = YamlCapabilityDefinitionSource("definitions/")
db_tool_source = DatabaseToolSource(session_factory)
catalog = CapabilityCatalogService(sources=[yaml_source, db_tool_source])
```

---

### Phase 4: Coordinator 变为真正入口

#### 🔴 High-Risk Files
```
src/interfaces/api/routes/conversation_stream.py
src/interfaces/api/dependencies/agents.py
src/domain/agents/coordinator_agent.py
```

#### ❌ Imports to Avoid
```python
# Interface 中避免
from src.domain.agents.conversation_agent import ConversationAgent
from src.domain.agents.workflow_agent import WorkflowAgent
from src.domain.agents.coordinator_agent import CoordinatorAgent

# Application orchestrator 中避免
import fastapi
import sqlalchemy
from src.interfaces...
from src.infrastructure...
```

#### ✅ Correct DI Pattern
```python
# src/interfaces/api/main.py
conversation_orchestrator = ConversationTurnOrchestrator(
    conversation_agent=conversation_agent,  # Domain
    workflow_orchestrator=workflow_orchestrator,  # Application
    policy_chain=policy_chain,  # Application
    event_emitter=sse_emitter,  # Port
)

# src/interfaces/api/routes/conversation_stream.py
@router.post("/conversation/stream")
async def conversation_stream(
    orchestrator: ConversationTurnOrchestrator = Depends(get_conversation_orchestrator)
):
    async for event in orchestrator.process_turn(user_message):
        yield event
```

---

### Phase 5: 并发/幂等/一致性加固

#### 🔴 High-Risk Files
```
src/interfaces/api/main.py
src/application/services/*
tests/integration/api/*
```

#### ❌ Imports to Avoid
```python
# Application 层避免
from specific_queue_client import RabbitMQ  # 具体 broker 实现
from redis import Redis  # 具体缓存实现

# 测试里避免
# ❌ 为了方便从 Interface 直接 import Domain 并执行
from src.domain.agents.workflow_agent import WorkflowAgent
agent = WorkflowAgent(...)
agent.execute_workflow(...)  # 绕过 Application
```

#### ✅ Correct Patterns
```python
# 并发: Application 只使用标准库
async with asyncio.TaskGroup() as tg:
    task1 = tg.create_task(subagent.run())
    task2 = tg.create_task(subagent.run())

# 幂等: 通过 Port
class WorkflowExecutionOrchestrator:
    def __init__(self, idempotency_store: IdempotencyStore):
        self.idempotency_store = idempotency_store

    async def execute(self, request: RunWorkflowRequest):
        if await self.idempotency_store.exists(request.idempotency_key):
            return await self.idempotency_store.get_result(request.idempotency_key)
        # ... 执行并存储
```

---

## 三、Common Anti-Patterns（本仓库已出现的反模式）

### 1. Interface 直连 Domain Agent（绕过 Application）

#### ❌ 反例
```python
# src/interfaces/api/dependencies/agents.py
from src.domain.agents.conversation_agent import ConversationAgent

def get_conversation_agent() -> ConversationAgent:
    return ConversationAgent(...)

# src/interfaces/api/routes/conversation_stream.py
async def stream(agent: ConversationAgent = Depends(get_conversation_agent)):
    await agent.run_async(...)
```

#### ✅ 修复
```python
# src/application/use_cases/orchestrate_conversation_turn.py
class OrchestrateConversationTurnUseCase:
    def __init__(self, conversation_agent: ConversationAgent, policy_chain: PolicyChain):
        self.agent = conversation_agent
        self.policy = policy_chain

# src/interfaces/api/routes/conversation_stream.py
async def stream(use_case: OrchestrateConversationTurnUseCase = Depends(...)):
    await use_case.execute(...)
```

**为什么违反 DDD**: Interface 不应承载业务入口；治理/策略无法统一应用

---

### 2. 双执行路径（重复的 DAG 逻辑）

#### ❌ 反例
```python
# src/domain/agents/workflow_agent.py
class WorkflowAgent:
    async def execute_workflow(self, workflow_id: str):
        # 拓扑排序 + 节点执行（实现1）
        ...

# src/domain/services/workflow_executor.py
class WorkflowExecutor:
    async def execute(self, workflow: Workflow):
        # 拓扑排序 + 节点执行（实现2）
        ...
```

#### ✅ 修复
```python
# src/domain/services/workflow_engine.py (唯一实现)
class WorkflowEngine:
    async def execute(self, workflow: Workflow, context: ExecutionContext):
        # 唯一的拓扑排序 + 节点执行逻辑
        ...

# src/application/orchestrators/workflow_execution_orchestrator.py
class WorkflowExecutionOrchestrator:
    def __init__(self, engine: WorkflowEngine):
        self.engine = engine

    async def execute(self, workflow_id: str, request: RunWorkflowRequest):
        # 策略链 + 委托给唯一 Engine
        workflow = await self.load_workflow(workflow_id)
        await self.policy_chain.validate(workflow)
        return await self.engine.execute(workflow, context)
```

**为什么违反 DDD**: 业务语义出现两个"真相来源"，策略链无法复用

---

### 3. Domain 混入 IO/解析（YAML/Path）

#### ❌ 反例
```python
# src/domain/services/workflow_dependency_graph.py
import yaml
from pathlib import Path

class WorkflowDependencyGraph:
    def load_from_file(self, path: Path):
        content = yaml.safe_load(path.read_text())
        ...
```

#### ✅ 修复
```python
# src/infrastructure/definitions/yaml_capability_source.py
import yaml
from pathlib import Path

class YamlCapabilityDefinitionSource:
    def load(self) -> list[CapabilityDefinition]:
        # Infrastructure 负责 IO 和解析
        ...

# src/domain/services/workflow_dependency_graph.py (纯业务)
class WorkflowDependencyGraph:
    def build(self, definitions: list[CapabilityDefinition]):
        # 只处理已加载的数据结构
        ...
```

**为什么违反 DDD**: Domain 不应依赖文件系统与序列化格式；会导致不可测/不可替换

---

### 4. Domain Service 含"默认模拟执行" fallback

#### ❌ 反例
```python
# src/domain/services/workflow_executor.py
async def _execute_node(self, node: Node):
    executor = self.registry.get(node.type)
    if not executor:
        # ❌ Domain 混入模拟逻辑
        if node.type == "http":
            return {"status": 200, "data": "mocked"}
        return {}
    return await executor.execute(node)
```

#### ✅ 修复
```python
# src/domain/services/workflow_engine.py
async def _execute_node(self, node: Node):
    executor = self.registry.get(node.type)
    if not executor:
        raise DomainError(f"No executor for node type: {node.type}")
    return await executor.execute(node)

# 启动时校验 (src/interfaces/api/main.py)
@asynccontextmanager
async def lifespan(app: FastAPI):
    registry = create_executor_registry()
    catalog = load_capability_catalog()

    # 启动时校验完整性
    for definition in catalog.get_all():
        if definition.kind == "node" and not registry.has(definition.type):
            raise StartupError(f"Missing executor for node: {definition.type}")
```

**为什么违反 DDD**: Domain 不应决定执行实现细节；会隐藏缺 executor 的系统错误

---

### 5. EventBus Middleware 当治理边界

#### ❌ 反例
```python
# src/domain/agents/coordinator_agent.py
def as_middleware(self):
    def middleware(event: Event):
        if isinstance(event, DecisionMadeEvent):
            validation = self.validate_decision(event)
            if not validation.passed:
                return DecisionRejectedEvent(...)
        return event
    return middleware

# 问题: REST API 不发布事件就能绕过
```

#### ✅ 修复
```python
# src/application/orchestrators/workflow_policy_chain.py
class WorkflowPolicyChain:
    def __init__(self, rule_engine: RuleEngineFacade):
        self.rule_engine = rule_engine

    async def validate(self, workflow: Workflow, context: ExecutionContext):
        validation = await self.rule_engine.validate(workflow, context)
        if not validation.passed:
            raise PolicyViolationError(validation.errors)

# src/application/orchestrators/workflow_execution_orchestrator.py
async def execute(self, workflow_id: str, request: RunWorkflowRequest):
    workflow = await self.load_workflow(workflow_id)
    await self.policy_chain.validate(workflow, context)  # 强制执行
    return await self.engine.execute(workflow, context)
```

**为什么违反 DDD**: 任何不走 EventBus 的入口都能绕过治理；治理应在 Application 强制执行

---

## 四、Port/Adapter Pattern Enforcement

### 4.1 Port 定义位置

```
src/domain/ports/
├── workflow_repository.py
├── node_executor.py
├── capability_definition_source.py  # 新增
├── human_interaction_port.py         # 新增
├── file_safety_port.py               # 新增
├── execution_event_sink.py           # 新增
├── idempotency_store.py              # 新增
└── subagent_runner_port.py           # 新增
```

#### 规则
- 只包含 `Protocol/ABC` + domain 级数据结构
- ❌ 不允许出现：`sqlalchemy`, `fastapi`, `requests`, `yaml`

---

### 4.2 Adapter 实现位置

```
src/infrastructure/
├── database/
│   └── repositories/
│       └── workflow_repository.py  # 实现 WorkflowRepository Port
├── executors/
│   ├── __init__.py  # create_executor_registry()
│   ├── http_executor.py
│   └── ...
├── definitions/
│   └── yaml_capability_source.py  # 实现 CapabilityDefinitionSource Port
└── events/
    └── sse_event_sink.py  # 实现 ExecutionEventSink Port
```

---

### 4.3 依赖注入示例

```python
# ✅ Correct: Composition Root (src/interfaces/api/main.py)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Infrastructure 适配器
    workflow_repo = SQLAlchemyWorkflowRepository(session_factory)
    executor_registry = create_executor_registry()
    event_sink = SSEEventSink()

    # Domain 服务
    workflow_engine = WorkflowEngine(
        executor_registry=executor_registry,
        event_sink=event_sink,
    )

    # Application 编排器
    orchestrator = WorkflowExecutionOrchestrator(
        workflow_repository=workflow_repo,
        engine=workflow_engine,
        policy_chain=policy_chain,
    )

    app.state.orchestrator = orchestrator
    yield

# ❌ Incorrect: Route 内直接实例化
@router.post("/execute")
async def execute(workflow_id: str):
    repo = SQLAlchemyWorkflowRepository(...)  # ❌
    orchestrator = WorkflowExecutionOrchestrator(repo)  # ❌
    ...
```

---

## 五、Code Review Checklist（逐步勾选）

### A. 结构与入口
- [ ] Interface 是否只调用 Application UseCase/Orchestrator（无 Domain Agent 直连）
- [ ] 是否存在新的"第二入口"执行工作流（除 Orchestrator 外）
- [ ] REST `/api/workflows/{id}/execute` 与 agent-driven 执行是否共享同一 orchestrator

### B. Import 边界（最重要）
- [ ] `src/interfaces/**` 中 `from src.domain.agents...` 出现次数 = 0
- [ ] `src/application/**` 中 `from src.infrastructure...` 出现次数 = 0
- [ ] `src/application/**` 中 `import fastapi` / `import sqlalchemy` 出现次数 = 0
- [ ] `src/domain/**` 中 `from src.infrastructure...` / `from src.interfaces...` 出现次数 = 0
- [ ] `src/domain/**` 中 `import yaml` / `from pathlib import Path` 出现次数 = 0（除迁移残留）

**快速检查命令**:
```bash
# Interface 越界检查
rg -n "from src\.domain\.agents" src/interfaces/

# Application 越界检查
rg -n "from src\.infrastructure|import fastapi|import sqlalchemy" src/application/

# Domain 越界检查
rg -n "from src\.infrastructure|from src\.interfaces|import yaml|from pathlib import Path" src/domain/
```

### C. 依赖注入与组装
- [ ] 只有 `src/interfaces/api/main.py` 负责实例化 adapters/registries
- [ ] routes/dependencies 只是"取已组装对象"，不 new repository/registry
- [ ] Application Orchestrator 构造函数参数全部是 ports/protocols

### D. Domain 纯度
- [ ] Domain Engine 不包含 mock fallback（缺 executor 直接报错）
- [ ] Domain events/models 不携带 Interface DTO / DB model
- [ ] Workflow 执行语义（拓扑排序/条件/循环）只有一个实现

### E. Capabilities 一致性
- [ ] `definitions/nodes/*.yaml` 能在启动时全部映射到 `NodeExecutorRegistry`
- [ ] `definitions/tools/*.yaml` 能被 Catalog/ToolEngine 发现
- [ ] "定义 → 执行器"缺失在启动阶段 fail fast

### F. 测试与文档
- [ ] 每新增 Orchestrator/Port/Domain Service 同时新增 unit test
- [ ] Integration tests 覆盖统一入口与校验链
- [ ] 文档（`docs/architecture/*`, `CLAUDE.md`）与代码同步更新

---

## 六、自动化检查（可选）

使用 `import-linter` 定义规则：

```toml
# .import-linter.toml
[importlinter]
root_package = "src"

[[importlinter.contracts]]
name = "Interface 不能依赖 Domain Agents"
type = "forbidden"
source_modules = ["src.interfaces"]
forbidden_modules = ["src.domain.agents"]

[[importlinter.contracts]]
name = "Application 不能依赖 Infrastructure"
type = "forbidden"
source_modules = ["src.application"]
forbidden_modules = ["src.infrastructure"]

[[importlinter.contracts]]
name = "Domain 不能依赖 Infrastructure/Interface"
type = "forbidden"
source_modules = ["src.domain"]
forbidden_modules = ["src.infrastructure", "src.interfaces"]
```

运行检查：
```bash
lint-imports
```

---

**审查完成标准**: 所有 checklist 项勾选完毕 + 自动化检查通过 + 回归测试全部通过
