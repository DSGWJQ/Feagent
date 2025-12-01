# Agent→Workflow 自动转换实施计划

## 🎯 目标

实现 Agent 创建成功后自动生成 Workflow 并跳转到编辑器的完整流程。

## 📐 架构设计

### 1. 转换规则（Task → Node）

#### 1.1 节点类型推断规则

```python
TASK_TYPE_INFERENCE_RULES = {
    # 关键词 → NodeType 的映射
    "读取|加载|获取|下载": NodeType.FILE,
    "调用|请求|API|HTTP": NodeType.HTTP,
    "分析|理解|总结|提取": NodeType.LLM,
    "转换|处理|格式化": NodeType.TRANSFORM,
    "查询|数据库|SQL": NodeType.DATABASE,
    "判断|条件|如果": NodeType.CONDITIONAL,
    "循环|遍历|重复": NodeType.LOOP,
    "通知|发送|邮件": NodeType.NOTIFICATION,
}

# 默认类型（无法推断时使用）
DEFAULT_NODE_TYPE = NodeType.PROMPT
```

#### 1.2 节点配置生成规则

```python
def generate_node_config(task: Task, node_type: NodeType) -> dict:
    """根据任务和节点类型生成配置"""

    if node_type == NodeType.LLM:
        return {
            "model": "kimi",
            "temperature": 0.7,
            "prompt": task.description or task.name,
        }
    elif node_type == NodeType.PROMPT:
        return {
            "template": task.description or task.name,
        }
    elif node_type == NodeType.HTTP:
        return {
            "method": "GET",
            "url": "",  # 需要用户填写
            "headers": {},
        }
    # ... 其他类型
    else:
        return {}
```

#### 1.3 节点位置计算规则

```python
def calculate_node_position(index: int, total: int) -> Position:
    """计算节点位置（水平排列）"""

    # START 节点：(50, 250)
    # Task 节点：每个间隔 200px
    # END 节点：最后

    x = 50 + (index + 1) * 200  # +1 因为 START 占用第一个位置
    y = 250

    return Position(x=x, y=y)
```

### 2. Workflow 结构

```json
{
  "id": "wf_abc123",
  "name": "Agent-销售分析",
  "description": "从起点到目标的自动生成工作流",
  "source": "feagent",
  "source_id": "agent_xyz",
  "nodes": [
    {
      "id": "node_start",
      "type": "start",
      "name": "开始",
      "config": {},
      "position": {"x": 50, "y": 250}
    },
    {
      "id": "node_1",
      "type": "llm",
      "name": "分析销售数据",
      "config": {
        "model": "kimi",
        "prompt": "使用 pandas 分析销售数据..."
      },
      "position": {"x": 250, "y": 250}
    },
    {
      "id": "node_end",
      "type": "end",
      "name": "结束",
      "config": {},
      "position": {"x": 450, "y": 250}
    }
  ],
  "edges": [
    {
      "id": "edge_1",
      "source": "node_start",
      "target": "node_1"
    },
    {
      "id": "edge_2",
      "source": "node_1",
      "target": "node_end"
    }
  ]
}
```

## 🔧 实施步骤

### 步骤 1：Domain 层 - 创建 AgentToWorkflowConverter

**文件**：`src/domain/services/agent_to_workflow_converter.py`

**职责**：
- 接收 Agent 和 Tasks
- 推断每个 Task 的节点类型
- 生成节点配置
- 计算节点位置
- 创建 Workflow 实体

**关键方法**：
```python
class AgentToWorkflowConverter:
    def convert(self, agent: Agent, tasks: list[Task]) -> Workflow:
        """将 Agent 和 Tasks 转换为 Workflow"""
        pass

    def infer_node_type(self, task: Task) -> NodeType:
        """推断任务的节点类型"""
        pass

    def generate_node_config(self, task: Task, node_type: NodeType) -> dict:
        """生成节点配置"""
        pass
```

### 步骤 2：Application 层 - 改造 CreateAgentUseCase

**文件**：`src/application/use_cases/create_agent.py`

**改动**：
1. 注入 WorkflowRepository
2. 注入 AgentToWorkflowConverter
3. 在保存 Tasks 后立即生成 Workflow
4. 保存 Workflow 到数据库
5. 返回 Agent 和 workflow_id

**代码示例**：
```python
class CreateAgentUseCase:
    def __init__(
        self,
        agent_repository: AgentRepository,
        task_repository: TaskRepository,
        workflow_repository: WorkflowRepository,
        converter: AgentToWorkflowConverter,
    ):
        self.agent_repository = agent_repository
        self.task_repository = task_repository
        self.workflow_repository = workflow_repository
        self.converter = converter

    def execute(self, input_data: CreateAgentInput) -> tuple[Agent, str | None]:
        # 1. 创建 Agent
        agent = Agent.create(...)
        self.agent_repository.save(agent)

        # 2. 生成 Tasks
        tasks = []
        if self.task_repository:
            plan = plan_chain.invoke(...)
            for task_data in plan:
                task = Task.create(...)
                self.task_repository.save(task)
                tasks.append(task)

        # 3. 生成 Workflow
        workflow_id = None
        if tasks and self.workflow_repository:
            workflow = self.converter.convert(agent, tasks)
            self.workflow_repository.save(workflow)
            workflow_id = workflow.id

        return agent, workflow_id
```

### 步骤 3：Interface 层 - 修改 API 响应

**文件**：`src/interfaces/api/routes/agents.py`

**改动**：
1. CreateAgentResponse 添加 workflow_id 字段
2. 返回 workflow_id 给前端

**代码示例**：
```python
@dataclass
class CreateAgentResponse:
    id: str
    start: str
    goal: str
    name: str
    status: str
    created_at: str
    workflow_id: str | None  # 新增字段

@router.post("/", response_model=CreateAgentResponse)
async def create_agent(request: CreateAgentRequest):
    # 注入所有依赖
    use_case = CreateAgentUseCase(
        agent_repository=get_agent_repository(),
        task_repository=get_task_repository(),
        workflow_repository=get_workflow_repository(),
        converter=AgentToWorkflowConverter(),
    )

    agent, workflow_id = use_case.execute(...)

    return CreateAgentResponse(
        id=agent.id,
        start=agent.start,
        goal=agent.goal,
        name=agent.name,
        status=agent.status,
        created_at=agent.created_at.isoformat(),
        workflow_id=workflow_id,
    )
```

### 步骤 4：前端 - 改造 CreateAgentForm

**文件**：`web/src/features/agents/components/CreateAgentForm.tsx`

**改动**：
```tsx
const handleSubmit = async (values: FormValues) => {
  try {
    // 1. 创建 Agent
    const agent = await createAgent.mutateAsync(values);

    // 2. 检查是否有 workflow_id
    if (agent.workflow_id) {
      // 跳转到 Workflow 编辑器
      navigate(`/workflows/${agent.workflow_id}/edit`);
      message.success('Agent 已创建，工作流已自动生成');
    } else {
      // 降级：跳转到 Agent 详情页
      navigate(`/app/agents/${agent.id}`);
      message.success('Agent 已创建');
    }

    form.resetFields();
    onSuccess?.(agent);
  } catch (error) {
    // 错误处理...
  }
};
```

### 步骤 5：前端 - WorkflowEditor 已支持（无需修改）

**文件**：`web/src/features/workflows/pages/WorkflowEditorPage.tsx`

- ✅ 已支持通过 URL 参数加载工作流：`/workflows/:id/edit`
- ✅ 已支持通过 useWorkflow hook 加载数据
- ✅ 已支持 ReactFlow 渲染节点和边

## 📊 数据流

```
用户填写表单（start, goal, name）
    ↓
CreateAgentForm.handleSubmit()
    ↓
POST /api/agents （前端）
    ↓
CreateAgentUseCase.execute() （后端）
    ├─ 创建 Agent
    ├─ 生成 Tasks（通过 LLM）
    └─ 生成 Workflow（通过 Converter）
        ├─ 推断节点类型
        ├─ 生成节点配置
        ├─ 计算节点位置
        ├─ 创建 START/END 节点
        └─ 创建边
    ↓
返回 Agent + workflow_id
    ↓
前端跳转：navigate(`/workflows/${workflow_id}/edit`)
    ↓
WorkflowEditorPage 加载并渲染 Workflow
```

## 🧪 测试计划

### 1. 单元测试

**测试文件**：`tests/unit/domain/services/test_agent_to_workflow_converter.py`

```python
def test_convert_agent_with_tasks_to_workflow():
    """测试：将 Agent 和 Tasks 转换为 Workflow"""
    agent = Agent.create(...)
    tasks = [Task.create(...), Task.create(...)]

    converter = AgentToWorkflowConverter()
    workflow = converter.convert(agent, tasks)

    # 验证 Workflow
    assert workflow.name == f"Agent-{agent.name}"
    assert workflow.source == "feagent"
    assert workflow.source_id == agent.id

    # 验证节点数量：START + Tasks + END
    assert len(workflow.nodes) == len(tasks) + 2

    # 验证边数量：len(nodes) - 1
    assert len(workflow.edges) == len(workflow.nodes) - 1

def test_infer_node_type_from_task():
    """测试：从任务名称推断节点类型"""
    converter = AgentToWorkflowConverter()

    task1 = Task.create(agent_id="...", name="读取 CSV 文件")
    assert converter.infer_node_type(task1) == NodeType.FILE

    task2 = Task.create(agent_id="...", name="调用天气 API")
    assert converter.infer_node_type(task2) == NodeType.HTTP

    task3 = Task.create(agent_id="...", name="分析销售数据")
    assert converter.infer_node_type(task3) == NodeType.LLM
```

### 2. 集成测试

**测试文件**：`tests/integration/test_create_agent_with_workflow.py`

```python
def test_create_agent_generates_workflow(client: TestClient):
    """测试：创建 Agent 时自动生成 Workflow"""
    response = client.post("/api/agents", json={
        "start": "我有一个 CSV 文件",
        "goal": "分析销售数据",
    })

    assert response.status_code == 200
    data = response.json()

    # 验证返回了 workflow_id
    assert data["workflow_id"] is not None

    # 验证 Workflow 存在
    workflow_response = client.get(f"/api/workflows/{data['workflow_id']}")
    assert workflow_response.status_code == 200

    workflow = workflow_response.json()
    assert workflow["source"] == "feagent"
    assert workflow["source_id"] == data["id"]
```

### 3. E2E 测试（手动）

1. 打开前端：http://localhost:5173
2. 进入创建 Agent 页面
3. 填写表单：
   - 起点：我有一个 CSV 文件，包含销售数据
   - 目的：分析数据并生成可视化报告
4. 点击"创建 Agent"
5. 验证：
   - ✅ 自动跳转到 Workflow 编辑器
   - ✅ 工作流包含 START、Tasks、END 节点
   - ✅ 节点按顺序连接
   - ✅ 可以拖拽调整节点位置
   - ✅ 可以编辑节点配置

## 📝 注意事项

### 1. 向后兼容

- 如果 task_repository 为 None，不生成 Workflow
- 如果 workflow_repository 为 None，不生成 Workflow
- 前端检查 workflow_id 是否存在，决定跳转目标

### 2. 错误处理

- Workflow 生成失败不影响 Agent 创建
- 前端优雅降级：跳转到 Agent 详情页
- 记录错误日志，便于调试

### 3. 性能考虑

- Workflow 生成是同步操作（未来可异步化）
- Task 类型推断使用启发式规则（快速）
- 避免额外的 LLM 调用

## 🚀 部署计划

### 阶段 1：后端核心逻辑（2 个文件）
1. `src/domain/services/agent_to_workflow_converter.py`
2. `src/application/use_cases/create_agent.py`

### 阶段 2：后端 API 接口（1 个文件）
3. `src/interfaces/api/routes/agents.py`

### 阶段 3：前端集成（1 个文件）
4. `web/src/features/agents/components/CreateAgentForm.tsx`

### 阶段 4：测试和优化
5. 单元测试
6. 集成测试
7. E2E 测试

## ✅ 验收标准

- [ ] Agent 创建成功后自动生成 Workflow
- [ ] Workflow 包含 START、Tasks、END 节点
- [ ] 节点类型推断准确率 > 80%
- [ ] 前端成功跳转到 Workflow 编辑器
- [ ] Workflow 可编辑、可执行
- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试通过
- [ ] E2E 测试通过

---

**创建时间**：2025-12-01
**负责人**：Claude Code
**状态**：等待用户确认
