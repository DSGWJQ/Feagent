# 后端修改分析：从 Agent 到 Workflow

## 📋 概述

本文档分析从"Agent 执行"模式切换到"Workflow 工作流"模式所需的后端修改。

---

## 🔄 核心变化

### 之前的模型

```
Agent（智能体）
  ├── start: str（起点）
  ├── goal: str（目的）
  └── config: Dict（配置）

Run（执行记录）
  ├── agent_id: str
  ├── status: RunStatus
  └── tasks: List[Task]

Task（任务）
  ├── run_id: str
  ├── tool_name: str
  └── status: TaskStatus
```

**执行流程**：
1. 用户创建 Agent（填写 start + goal）
2. 触发 Run
3. LangChain Agent 自动生成 Task 并执行

---

### 现在的模型

```
Workflow（工作流）
  ├── name: str
  ├── description: str
  ├── nodes: List[Node]（节点列表）
  └── edges: List[Edge]（边列表）

Node（节点）
  ├── id: str
  ├── type: NodeType（HTTP, SQL, Script, Transform）
  ├── config: Dict（节点配置）
  └── position: Position（画布位置）

Edge（边）
  ├── source_node_id: str
  ├── target_node_id: str
  └── condition: Optional[str]（条件）

Run（执行记录）
  ├── workflow_id: str
  ├── status: RunStatus
  └── node_executions: List[NodeExecution]

NodeExecution（节点执行记录）
  ├── node_id: str
  ├── status: NodeExecutionStatus
  ├── input_data: Dict
  └── output_data: Dict
```

**执行流程**：
1. 用户通过对话创建 Workflow
2. AI 生成 Workflow（包含 nodes 和 edges）
3. 用户通过对话或拖拽调整 Workflow
4. 触发 Run
5. 按拓扑排序执行 Workflow 的 nodes

---

## 📊 需要修改的部分

### 1. Domain 层（新增）

#### 新增实体

**Workflow（工作流）**：
```python
# src/domain/entities/workflow.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

class WorkflowStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"

@dataclass
class Position:
    """节点在画布上的位置"""
    x: float
    y: float

class NodeType(str, Enum):
    HTTP = "http"
    SQL = "sql"
    SCRIPT = "script"
    TRANSFORM = "transform"
    CONDITION = "condition"

@dataclass
class Node:
    """工作流节点"""
    id: str
    type: NodeType
    name: str
    config: Dict[str, Any]
    position: Position

    @staticmethod
    def create(
        type: NodeType,
        name: str,
        config: Dict[str, Any],
        position: Position
    ) -> "Node":
        import uuid
        return Node(
            id=f"node_{uuid.uuid4().hex[:8]}",
            type=type,
            name=name,
            config=config,
            position=position
        )

@dataclass
class Edge:
    """工作流边（连接）"""
    id: str
    source_node_id: str
    target_node_id: str
    condition: Optional[str] = None

    @staticmethod
    def create(
        source_node_id: str,
        target_node_id: str,
        condition: Optional[str] = None
    ) -> "Edge":
        import uuid
        return Edge(
            id=f"edge_{uuid.uuid4().hex[:8]}",
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            condition=condition
        )

@dataclass
class Workflow:
    """工作流聚合根"""
    id: str
    name: str
    description: str
    nodes: List[Node]
    edges: List[Edge]
    status: WorkflowStatus
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def create(
        name: str,
        description: str,
        nodes: List[Node],
        edges: List[Edge]
    ) -> "Workflow":
        import uuid
        from datetime import datetime

        workflow = Workflow(
            id=f"wf_{uuid.uuid4().hex[:8]}",
            name=name,
            description=description,
            nodes=nodes,
            edges=edges,
            status=WorkflowStatus.DRAFT,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        # 验证工作流有效性
        workflow._validate()

        return workflow

    def _validate(self):
        """验证工作流有效性"""
        # 1. 检查是否有节点
        if not self.nodes:
            raise ValueError("Workflow must have at least one node")

        # 2. 检查边的节点是否存在
        node_ids = {node.id for node in self.nodes}
        for edge in self.edges:
            if edge.source_node_id not in node_ids:
                raise ValueError(f"Source node {edge.source_node_id} not found")
            if edge.target_node_id not in node_ids:
                raise ValueError(f"Target node {edge.target_node_id} not found")

        # 3. 检查是否有环（简单检查）
        # TODO: 实现拓扑排序检查

    def add_node(self, node: Node):
        """添加节点"""
        self.nodes.append(node)
        self.updated_at = datetime.now()

    def remove_node(self, node_id: str):
        """删除节点"""
        self.nodes = [n for n in self.nodes if n.id != node_id]
        # 删除相关的边
        self.edges = [
            e for e in self.edges
            if e.source_node_id != node_id and e.target_node_id != node_id
        ]
        self.updated_at = datetime.now()

    def add_edge(self, edge: Edge):
        """添加边"""
        self.edges.append(edge)
        self.updated_at = datetime.now()

    def remove_edge(self, edge_id: str):
        """删除边"""
        self.edges = [e for e in self.edges if e.id != edge_id]
        self.updated_at = datetime.now()

    def activate(self):
        """激活工作流"""
        self._validate()
        self.status = WorkflowStatus.ACTIVE
        self.updated_at = datetime.now()

    def archive(self):
        """归档工作流"""
        self.status = WorkflowStatus.ARCHIVED
        self.updated_at = datetime.now()
```

---

**NodeExecution（节点执行记录）**：
```python
# src/domain/entities/node_execution.py

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum

class NodeExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class NodeExecution:
    """节点执行记录"""
    id: str
    run_id: str
    node_id: str
    status: NodeExecutionStatus
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]

    @staticmethod
    def create(
        run_id: str,
        node_id: str,
        input_data: Dict[str, Any]
    ) -> "NodeExecution":
        import uuid
        return NodeExecution(
            id=f"ne_{uuid.uuid4().hex[:8]}",
            run_id=run_id,
            node_id=node_id,
            status=NodeExecutionStatus.PENDING,
            input_data=input_data,
            output_data=None,
            error_message=None,
            started_at=None,
            finished_at=None
        )

    def start(self):
        """开始执行"""
        self.status = NodeExecutionStatus.RUNNING
        self.started_at = datetime.now()

    def succeed(self, output_data: Dict[str, Any]):
        """执行成功"""
        self.status = NodeExecutionStatus.SUCCEEDED
        self.output_data = output_data
        self.finished_at = datetime.now()

    def fail(self, error_message: str):
        """执行失败"""
        self.status = NodeExecutionStatus.FAILED
        self.error_message = error_message
        self.finished_at = datetime.now()

    def skip(self):
        """跳过执行"""
        self.status = NodeExecutionStatus.SKIPPED
        self.finished_at = datetime.now()
```

---

#### 修改现有实体

**Run（执行记录）**：
```python
# src/domain/entities/run.py

# 之前
@dataclass
class Run:
    agent_id: str  # ← 修改为 workflow_id
    ...

# 现在
@dataclass
class Run:
    workflow_id: str  # ← 改为 workflow_id
    node_executions: List[NodeExecution] = field(default_factory=list)  # ← 新增
    ...

    @staticmethod
    def create(workflow_id: str, input_data: Dict[str, Any]) -> "Run":
        ...
```

---

### 2. Application 层（新增）

#### 新增 Use Cases

**CreateWorkflowByChatUseCase**：
```python
# src/application/use_cases/create_workflow_by_chat.py

from dataclasses import dataclass
from typing import Dict, Any
from src.domain.entities.workflow import Workflow
from src.lc.chains.workflow_generator import WorkflowGeneratorChain

@dataclass
class CreateWorkflowByChatCommand:
    user_message: str

class CreateWorkflowByChatUseCase:
    def __init__(
        self,
        workflow_generator: WorkflowGeneratorChain,
        workflow_repo: WorkflowRepository
    ):
        self.workflow_generator = workflow_generator
        self.workflow_repo = workflow_repo

    async def execute(self, command: CreateWorkflowByChatCommand) -> Workflow:
        # 1. 使用 LangChain 生成工作流
        workflow_data = await self.workflow_generator.generate(
            command.user_message
        )

        # 2. 创建 Workflow 实体
        workflow = Workflow.create(
            name=workflow_data["name"],
            description=workflow_data["description"],
            nodes=workflow_data["nodes"],
            edges=workflow_data["edges"]
        )

        # 3. 保存工作流
        await self.workflow_repo.save(workflow)

        return workflow
```

**UpdateWorkflowByChatUseCase**：
```python
# src/application/use_cases/update_workflow_by_chat.py

@dataclass
class UpdateWorkflowByChatCommand:
    workflow_id: str
    user_message: str

class UpdateWorkflowByChatUseCase:
    def __init__(
        self,
        workflow_modifier: WorkflowModifierChain,
        workflow_repo: WorkflowRepository
    ):
        self.workflow_modifier = workflow_modifier
        self.workflow_repo = workflow_repo

    async def execute(self, command: UpdateWorkflowByChatCommand) -> Workflow:
        # 1. 获取现有工作流
        workflow = await self.workflow_repo.get(command.workflow_id)

        # 2. 使用 LangChain 理解修改意图
        modifications = await self.workflow_modifier.parse(
            command.user_message,
            workflow
        )

        # 3. 应用修改
        for mod in modifications:
            if mod["action"] == "add_node":
                workflow.add_node(mod["node"])
            elif mod["action"] == "remove_node":
                workflow.remove_node(mod["node_id"])
            elif mod["action"] == "add_edge":
                workflow.add_edge(mod["edge"])
            # ... 其他修改

        # 4. 保存更新
        await self.workflow_repo.update(workflow)

        return workflow
```

**ExecuteWorkflowUseCase**：
```python
# src/application/use_cases/execute_workflow.py

@dataclass
class ExecuteWorkflowCommand:
    workflow_id: str
    input_data: Dict[str, Any]

class ExecuteWorkflowUseCase:
    def __init__(
        self,
        workflow_repo: WorkflowRepository,
        run_repo: RunRepository,
        workflow_executor: WorkflowExecutor
    ):
        self.workflow_repo = workflow_repo
        self.run_repo = run_repo
        self.workflow_executor = workflow_executor

    async def execute(self, command: ExecuteWorkflowCommand) -> Run:
        # 1. 获取工作流
        workflow = await self.workflow_repo.get(command.workflow_id)

        # 2. 创建 Run
        run = Run.create(
            workflow_id=command.workflow_id,
            input_data=command.input_data
        )
        await self.run_repo.save(run)

        # 3. 执行工作流
        await self.workflow_executor.execute(workflow, run)

        return run
```

---

### 3. LangChain 层（新增）

**WorkflowGeneratorChain**：
```python
# src/lc/chains/workflow_generator.py

from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List

class NodeSchema(BaseModel):
    type: str = Field(description="节点类型：http, sql, script, transform")
    name: str = Field(description="节点名称")
    config: dict = Field(description="节点配置")

class EdgeSchema(BaseModel):
    source_node_id: str
    target_node_id: str

class WorkflowSchema(BaseModel):
    name: str = Field(description="工作流名称")
    description: str = Field(description="工作流描述")
    nodes: List[NodeSchema]
    edges: List[EdgeSchema]

class WorkflowGeneratorChain:
    def __init__(self, llm):
        self.llm = llm
        self.parser = PydanticOutputParser(pydantic_object=WorkflowSchema)

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个工作流生成助手。
根据用户的需求，生成一个最小可行的工作流。

工作流包含：
- nodes: 节点列表（每个节点有 type, name, config）
- edges: 边列表（连接节点）

节点类型：
- http: HTTP 请求
- sql: SQL 查询
- script: Python 脚本
- transform: 数据转换

{format_instructions}
"""),
            ("user", "{user_message}")
        ])

    async def generate(self, user_message: str) -> dict:
        chain = self.prompt | self.llm | self.parser
        result = await chain.ainvoke({
            "user_message": user_message,
            "format_instructions": self.parser.get_format_instructions()
        })
        return result.dict()
```

---

### 4. Infrastructure 层（新增）

**WorkflowRepository**：
```python
# src/infrastructure/database/repositories/workflow_repository.py

from src.domain.entities.workflow import Workflow
from src.infrastructure.database.models import WorkflowModel

class WorkflowRepository:
    async def save(self, workflow: Workflow):
        model = WorkflowModel.from_entity(workflow)
        # 保存到数据库

    async def get(self, workflow_id: str) -> Workflow:
        model = await WorkflowModel.get(workflow_id)
        return model.to_entity()

    async def update(self, workflow: Workflow):
        # 更新数据库
```

---

### 5. API 层（新增）

**Workflows Router**：
```python
# src/interfaces/api/routes/workflows.py

from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/workflows", tags=["workflows"])

class CreateWorkflowByChatRequest(BaseModel):
    message: str

@router.post("/chat")
async def create_workflow_by_chat(
    request: CreateWorkflowByChatRequest,
    use_case: CreateWorkflowByChatUseCase = Depends()
):
    workflow = await use_case.execute(
        CreateWorkflowByChatCommand(user_message=request.message)
    )
    return {"workflow": workflow}

@router.post("/{workflow_id}/chat")
async def update_workflow_by_chat(
    workflow_id: str,
    request: CreateWorkflowByChatRequest,
    use_case: UpdateWorkflowByChatUseCase = Depends()
):
    workflow = await use_case.execute(
        UpdateWorkflowByChatCommand(
            workflow_id=workflow_id,
            user_message=request.message
        )
    )
    return {"workflow": workflow}
```

---

## 📝 总结

### 需要新增的文件

**Domain 层**：
- `src/domain/entities/workflow.py` - Workflow, Node, Edge
- `src/domain/entities/node_execution.py` - NodeExecution

**Application 层**：
- `src/application/use_cases/create_workflow_by_chat.py`
- `src/application/use_cases/update_workflow_by_chat.py`
- `src/application/use_cases/execute_workflow.py`

**LangChain 层**：
- `src/lc/chains/workflow_generator.py`
- `src/lc/chains/workflow_modifier.py`
- `src/lc/executors/workflow_executor.py`

**Infrastructure 层**：
- `src/infrastructure/database/models/workflow.py`
- `src/infrastructure/database/repositories/workflow_repository.py`

**API 层**：
- `src/interfaces/api/routes/workflows.py`

---

### 需要修改的文件

**Domain 层**：
- `src/domain/entities/run.py` - 修改 `agent_id` 为 `workflow_id`

**Application 层**：
- `src/application/use_cases/execute_run.py` - 修改为使用 Workflow

---

### 数据库迁移

**新增表**：
- `workflows` - 工作流表
- `nodes` - 节点表
- `edges` - 边表
- `node_executions` - 节点执行记录表

**修改表**：
- `runs` - 修改 `agent_id` 为 `workflow_id`
