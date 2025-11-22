# 工作流实现计划

## 📋 概述

本文档详细规划工作流功能的实现步骤，遵循 TDD + DDD 开发模式。

---

## 🎯 开发原则

1. **TDD（测试驱动开发）**：先写测试，再写实现
2. **DDD（领域驱动设计）**：从业务出发，设计实体和用例
3. **分层开发**：Domain → Ports → Infrastructure → Application → API
4. **增量交付**：每个阶段都能独立运行和测试

---

## 📊 开发阶段

### 第一阶段：表单创建 + 工作流生成（P0）

**目标**：用户填写表单，AI 生成最小可行工作流

**时间**：1-2 天

---

#### 1.1 Domain 层（TDD）

**文件**：
- `src/domain/entities/workflow.py`
- `src/domain/entities/node.py`
- `src/domain/entities/edge.py`

**测试文件**：
- `tests/domain/entities/test_workflow.py`
- `tests/domain/entities/test_node.py`
- `tests/domain/entities/test_edge.py`

**开发步骤**：

1. **编写测试**（Red）：
```python
# tests/domain/entities/test_workflow.py

def test_create_workflow():
    """测试创建工作流"""
    nodes = [
        Node.create(
            type=NodeType.HTTP,
            name="获取 GitHub Issue",
            config={"url": "..."},
            position=Position(x=100, y=100)
        )
    ]
    edges = []

    workflow = Workflow.create(
        name="GitHub Issue 通知",
        description="...",
        nodes=nodes,
        edges=edges
    )

    assert workflow.id.startswith("wf_")
    assert workflow.name == "GitHub Issue 通知"
    assert workflow.status == WorkflowStatus.DRAFT
    assert len(workflow.nodes) == 1

def test_workflow_validation_no_nodes():
    """测试工作流验证：没有节点"""
    with pytest.raises(ValueError, match="must have at least one node"):
        Workflow.create(
            name="Test",
            description="",
            nodes=[],
            edges=[]
        )

def test_workflow_validation_invalid_edge():
    """测试工作流验证：边引用不存在的节点"""
    nodes = [Node.create(...)]
    edges = [Edge.create(
        source_node_id="node_1",
        target_node_id="node_999"  # 不存在
    )]

    with pytest.raises(ValueError, match="not found"):
        Workflow.create(
            name="Test",
            description="",
            nodes=nodes,
            edges=edges
        )

def test_add_node():
    """测试添加节点"""
    workflow = Workflow.create(...)
    new_node = Node.create(...)

    workflow.add_node(new_node)

    assert len(workflow.nodes) == 2
    assert workflow.updated_at > workflow.created_at

def test_remove_node():
    """测试删除节点"""
    workflow = Workflow.create(...)

    workflow.remove_node("node_1")

    assert len(workflow.nodes) == 0
    # 相关的边也应该被删除
    assert len(workflow.edges) == 0
```

2. **实现功能**（Green）：
```python
# src/domain/entities/workflow.py

@dataclass
class Workflow:
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

        workflow._validate()

        return workflow

    def _validate(self):
        if not self.nodes:
            raise ValueError("Workflow must have at least one node")

        node_ids = {node.id for node in self.nodes}
        for edge in self.edges:
            if edge.source_node_id not in node_ids:
                raise ValueError(f"Source node {edge.source_node_id} not found")
            if edge.target_node_id not in node_ids:
                raise ValueError(f"Target node {edge.target_node_id} not found")

    def add_node(self, node: Node):
        self.nodes.append(node)
        self.updated_at = datetime.now()

    def remove_node(self, node_id: str):
        self.nodes = [n for n in self.nodes if n.id != node_id]
        self.edges = [
            e for e in self.edges
            if e.source_node_id != node_id and e.target_node_id != node_id
        ]
        self.updated_at = datetime.now()
```

3. **运行测试**（验证）：
```bash
pytest tests/domain/entities/test_workflow.py -v
```

---

#### 1.2 Ports 层

**文件**：
- `src/domain/ports/workflow_repository.py`

**内容**：
```python
# src/domain/ports/workflow_repository.py

from abc import ABC, abstractmethod
from typing import Optional, List
from src.domain.entities.workflow import Workflow

class WorkflowRepository(ABC):
    @abstractmethod
    async def save(self, workflow: Workflow) -> None:
        pass

    @abstractmethod
    async def get(self, workflow_id: str) -> Optional[Workflow]:
        pass

    @abstractmethod
    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None
    ) -> tuple[List[Workflow], int]:
        pass

    @abstractmethod
    async def update(self, workflow: Workflow) -> None:
        pass

    @abstractmethod
    async def delete(self, workflow_id: str) -> None:
        pass
```

---

#### 1.3 Infrastructure 层

**文件**：
- `src/infrastructure/database/models/workflow.py`
- `src/infrastructure/database/repositories/workflow_repository.py`

**数据库迁移**：
```bash
# 创建迁移脚本
alembic revision --autogenerate -m "Add workflow tables"

# 执行迁移
alembic upgrade head
```

---

#### 1.4 LangChain 层

**文件**：
- `src/lc/chains/workflow_generator.py`

**测试文件**：
- `tests/lc/chains/test_workflow_generator.py`

**开发步骤**：

1. **编写测试**：
```python
# tests/lc/chains/test_workflow_generator.py

@pytest.mark.asyncio
async def test_generate_workflow():
    """测试生成工作流"""
    llm = FakeLLM(responses=[
        json.dumps({
            "name": "GitHub Issue 通知",
            "description": "...",
            "nodes": [
                {
                    "type": "http",
                    "name": "获取 GitHub Issue",
                    "config": {...}
                }
            ],
            "edges": []
        })
    ])

    generator = WorkflowGeneratorChain(llm)

    result = await generator.generate(
        start="GitHub Issue 列表",
        goal="发送到钉钉群",
        description="..."
    )

    assert result["name"] == "GitHub Issue 通知"
    assert len(result["nodes"]) > 0
```

2. **实现功能**：
```python
# src/lc/chains/workflow_generator.py

class WorkflowGeneratorChain:
    def __init__(self, llm):
        self.llm = llm
        self.parser = PydanticOutputParser(pydantic_object=WorkflowSchema)

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个工作流生成助手。
根据用户的起点、终点和描述，生成一个最小可行的工作流。

工作流包含：
- nodes: 节点列表（每个节点有 type, name, config, position）
- edges: 边列表（连接节点）

节点类型：
- http: HTTP 请求
- sql: SQL 查询
- script: Python 脚本
- transform: 数据转换

节点位置：
- 第一个节点：(100, 100)
- 后续节点：y 坐标每次增加 150

{format_instructions}
"""),
            ("user", """起点：{start}
终点：{goal}
描述：{description}

请生成工作流。""")
        ])

    async def generate(
        self,
        start: str,
        goal: str,
        description: str
    ) -> dict:
        chain = self.prompt | self.llm | self.parser
        result = await chain.ainvoke({
            "start": start,
            "goal": goal,
            "description": description,
            "format_instructions": self.parser.get_format_instructions()
        })
        return result.dict()
```

---

#### 1.5 Application 层（TDD）

**文件**：
- `src/application/use_cases/create_workflow.py`

**测试文件**：
- `tests/application/use_cases/test_create_workflow.py`

**开发步骤**：

1. **编写测试**：
```python
# tests/application/use_cases/test_create_workflow.py

@pytest.mark.asyncio
async def test_create_workflow():
    """测试创建工作流"""
    # Arrange
    workflow_repo = FakeWorkflowRepository()
    workflow_generator = FakeWorkflowGenerator()
    use_case = CreateWorkflowUseCase(workflow_generator, workflow_repo)

    command = CreateWorkflowCommand(
        start="GitHub Issue 列表",
        goal="发送到钉钉群",
        description="..."
    )

    # Act
    result = await use_case.execute(command)

    # Assert
    assert result.workflow.name == "GitHub Issue 通知"
    assert len(result.workflow.nodes) > 0
    assert result.ai_message != ""

    # 验证工作流已保存
    saved_workflow = await workflow_repo.get(result.workflow.id)
    assert saved_workflow is not None
```

2. **实现功能**：
```python
# src/application/use_cases/create_workflow.py

@dataclass
class CreateWorkflowCommand:
    start: str
    goal: str
    description: str

@dataclass
class CreateWorkflowResult:
    workflow: Workflow
    ai_message: str

class CreateWorkflowUseCase:
    def __init__(
        self,
        workflow_generator: WorkflowGeneratorChain,
        workflow_repo: WorkflowRepository
    ):
        self.workflow_generator = workflow_generator
        self.workflow_repo = workflow_repo

    async def execute(
        self,
        command: CreateWorkflowCommand
    ) -> CreateWorkflowResult:
        # 1. 使用 LangChain 生成工作流
        workflow_data = await self.workflow_generator.generate(
            start=command.start,
            goal=command.goal,
            description=command.description
        )

        # 2. 创建 Workflow 实体
        nodes = [
            Node(
                id=f"node_{i+1}",
                type=NodeType(node_data["type"]),
                name=node_data["name"],
                config=node_data["config"],
                position=Position(**node_data["position"])
            )
            for i, node_data in enumerate(workflow_data["nodes"])
        ]

        edges = [
            Edge(
                id=f"edge_{i+1}",
                source_node_id=edge_data["source_node_id"],
                target_node_id=edge_data["target_node_id"]
            )
            for i, edge_data in enumerate(workflow_data["edges"])
        ]

        workflow = Workflow.create(
            name=workflow_data["name"],
            description=workflow_data["description"],
            nodes=nodes,
            edges=edges
        )

        # 3. 保存工作流
        await self.workflow_repo.save(workflow)

        # 4. 生成 AI 回复消息
        ai_message = f"""我为你创建了一个工作流，包含 {len(nodes)} 个步骤：
{chr(10).join(f"{i+1}. {node.name}" for i, node in enumerate(nodes))}

你可以通过右侧的对话框调整工作流，或者直接拖拽节点。"""

        return CreateWorkflowResult(
            workflow=workflow,
            ai_message=ai_message
        )
```

---

#### 1.6 API 层

**文件**：
- `src/interfaces/api/routes/workflows.py`
- `src/interfaces/api/dto/workflow_dto.py`

**内容**：
```python
# src/interfaces/api/routes/workflows.py

from fastapi import APIRouter, Depends
from src.application.use_cases.create_workflow import (
    CreateWorkflowUseCase,
    CreateWorkflowCommand
)
from src.interfaces.api.dto.workflow_dto import (
    CreateWorkflowRequest,
    CreateWorkflowResponse
)

router = APIRouter(prefix="/workflows", tags=["workflows"])

@router.post("", response_model=CreateWorkflowResponse)
async def create_workflow(
    request: CreateWorkflowRequest,
    use_case: CreateWorkflowUseCase = Depends()
):
    """创建工作流"""
    command = CreateWorkflowCommand(
        start=request.start,
        goal=request.goal,
        description=request.description or ""
    )

    result = await use_case.execute(command)

    return CreateWorkflowResponse(
        workflow=WorkflowDTO.from_entity(result.workflow),
        ai_message=result.ai_message
    )
```

---

#### 1.7 前端（TypeScript + React）

**文件**：
- `web/src/shared/types/workflow.ts`
- `web/src/features/workflows/api/workflowsApi.ts`
- `web/src/shared/hooks/useWorkflows.ts`
- `web/src/features/workflows/components/CreateWorkflowModal.tsx`

**测试文件**：
- `web/src/features/workflows/api/__tests__/workflowsApi.test.ts`
- `web/src/shared/hooks/__tests__/useWorkflows.test.tsx`
- `web/src/features/workflows/components/__tests__/CreateWorkflowModal.test.tsx`

---

### 第二阶段：对话/拖拽调整（P1）

**目标**：用户通过对话或拖拽调整工作流

**时间**：1-2 天

**开发步骤**：
1. UpdateWorkflowByChatUseCase（TDD）
2. UpdateWorkflowByDragUseCase（TDD）
3. WorkflowModifierChain（LangChain）
4. API 接口
5. 前端组件（WorkflowEditor, WorkflowChat, WorkflowCanvas）

---

### 第三阶段：执行工作流 + 状态可视化（P0）

**目标**：执行工作流，实时显示每个节点的状态

**时间**：1-2 天

**开发步骤**：
1. NodeExecution 实体（TDD）
2. ExecuteWorkflowUseCase（TDD）
3. WorkflowExecutor（拓扑排序 + 节点执行）
4. SSE 实时推送
5. 前端 SSE 客户端 + 状态更新

---

## ✅ 验收标准

### 第一阶段
- [ ] 所有 Domain 层测试通过（100% 覆盖率）
- [ ] 所有 Application 层测试通过（90%+ 覆盖率）
- [ ] API 接口可以正常调用
- [ ] 前端可以创建工作流并跳转到编辑页面

### 第二阶段
- [ ] 对话调整功能正常
- [ ] 拖拽调整功能正常
- [ ] 工作流图表正确显示

### 第三阶段
- [ ] 工作流可以正常执行
- [ ] SSE 实时推送状态
- [ ] 前端正确显示节点状态（成功/失败/运行中/未执行）

---

## 📝 总结

本实现计划遵循 TDD + DDD 开发模式，分三个阶段增量交付：

1. **第一阶段**：表单创建 + 工作流生成（1-2 天）
2. **第二阶段**：对话/拖拽调整（1-2 天）
3. **第三阶段**：执行工作流 + 状态可视化（1-2 天）

每个阶段都有明确的验收标准，确保质量和进度。
