# Phase 8: 决策执行落地系统 (Decision Execution System)

## 1. 问题分析

### 1.1 当前缺陷

| 缺陷 | 现状 | 影响 |
|------|------|------|
| 单一决策 | ConversationAgent 每次只能产生一个 `create_node` 决策 | 无法规划完整工作流 |
| 无功能定义 | 决策只包含 `node_type` 和简单 `config` | Agent 无法定义节点执行什么代码 |
| 无执行桥接 | `DecisionMadeEvent` 发布后没有处理逻辑 | 决策停留在事件层，无法落地 |

### 1.2 目标

1. **批量节点规划**: ConversationAgent 可以一次性规划多个节点及其连接关系
2. **节点功能定义**: Agent 可以为每个节点定义具体执行逻辑（代码、Prompt、配置）
3. **决策执行桥接**: DecisionMadeEvent → WorkflowAgent 自动执行

---

## 2. 架构设计

### 2.1 核心组件

```
┌─────────────────────────────────────────────────────────────────┐
│                    ConversationAgent                             │
│  - 产生 WorkflowPlan (多节点 + 边 + 节点定义)                     │
│  - 发布 WorkflowPlanDecision                                     │
└───────────────────────────┬─────────────────────────────────────┘
                            │ DecisionMadeEvent
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   DecisionExecutionBridge                        │
│  - 订阅 DecisionMadeEvent                                        │
│  - 验证决策 (通过 CoordinatorAgent)                              │
│  - 转发给 WorkflowAgent 执行                                     │
└───────────────────────────┬─────────────────────────────────────┘
                            │ 验证通过
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      WorkflowAgent                               │
│  - 批量创建节点 (create_nodes_batch)                            │
│  - 创建边连接                                                    │
│  - 执行工作流                                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 新增数据结构

```python
@dataclass
class NodeDefinition:
    """节点定义 - Agent可自定义的节点配置"""
    node_type: str              # 节点类型: python, http, database, llm, etc.
    name: str                   # 节点名称
    description: str            # 节点描述
    # 功能定义（根据类型不同使用不同字段）
    code: str | None = None           # Python 节点的代码
    prompt: str | None = None         # LLM 节点的 Prompt
    url: str | None = None            # HTTP 节点的 URL
    query: str | None = None          # Database 节点的 SQL
    # 通用配置
    config: dict = field(default_factory=dict)
    inputs: list[str] = field(default_factory=list)   # 输入参数名
    outputs: list[str] = field(default_factory=list)  # 输出参数名

@dataclass
class EdgeDefinition:
    """边定义"""
    source_node: str    # 源节点名称
    target_node: str    # 目标节点名称
    condition: str | None = None  # 可选条件

@dataclass
class WorkflowPlan:
    """工作流规划 - ConversationAgent 产出的完整规划"""
    id: str
    name: str
    description: str
    nodes: list[NodeDefinition]
    edges: list[EdgeDefinition]
    goal: str                    # 对应的用户目标
    estimated_steps: int         # 预估步骤数
```

### 2.3 决策类型扩展

```python
class DecisionType(str, Enum):
    CREATE_NODE = "create_node"              # 创建单个节点（保留兼容）
    CREATE_WORKFLOW_PLAN = "create_workflow_plan"  # 创建完整工作流规划（新增）
    EXECUTE_WORKFLOW = "execute_workflow"    # 执行工作流
    MODIFY_NODE = "modify_node"              # 修改节点定义（新增）
    REQUEST_CLARIFICATION = "request_clarification"
    RESPOND = "respond"
    CONTINUE = "continue"
```

---

## 3. TDD 分阶段实施

### Phase 8.1: 节点定义增强 (NodeDefinition)

**测试优先**:
```python
# tests/unit/domain/agents/test_node_definition.py

def test_create_python_node_definition_with_code():
    """Python 节点应包含可执行代码"""

def test_create_llm_node_definition_with_prompt():
    """LLM 节点应包含 Prompt 模板"""

def test_create_http_node_definition_with_url():
    """HTTP 节点应包含 URL 和方法"""

def test_create_database_node_definition_with_query():
    """Database 节点应包含 SQL 查询"""

def test_node_definition_validates_required_fields():
    """节点定义应验证必填字段"""
```

### Phase 8.2: 工作流规划 (WorkflowPlan)

**测试优先**:
```python
# tests/unit/domain/agents/test_workflow_plan.py

def test_create_workflow_plan_with_multiple_nodes():
    """应支持创建包含多个节点的工作流规划"""

def test_workflow_plan_validates_edge_references():
    """边引用的节点必须存在"""

def test_workflow_plan_detects_circular_dependency():
    """应检测循环依赖"""

def test_workflow_plan_topological_order():
    """应返回正确的拓扑执行顺序"""
```

### Phase 8.3: ConversationAgent 增强

**测试优先**:
```python
# tests/unit/domain/agents/test_conversation_agent_planning.py

def test_conversation_agent_creates_workflow_plan():
    """ConversationAgent 应能创建完整工作流规划"""

def test_conversation_agent_decomposes_goal_to_nodes():
    """应将目标分解为具体节点定义"""

def test_conversation_agent_publishes_workflow_plan_decision():
    """应发布 WorkflowPlanDecision 事件"""

def test_conversation_agent_handles_complex_goal():
    """应处理复杂目标（如：分析数据并生成报表）"""
```

### Phase 8.4: 决策执行桥接 (DecisionExecutionBridge)

**测试优先**:
```python
# tests/unit/domain/services/test_decision_execution_bridge.py

def test_bridge_subscribes_to_decision_events():
    """桥接器应订阅决策事件"""

def test_bridge_validates_decision_before_execution():
    """执行前应验证决策"""

def test_bridge_forwards_to_workflow_agent():
    """验证通过后转发给 WorkflowAgent"""

def test_bridge_handles_validation_rejection():
    """处理验证拒绝情况"""

def test_bridge_publishes_execution_result():
    """应发布执行结果事件"""
```

### Phase 8.5: WorkflowAgent 批量操作

**测试优先**:
```python
# tests/unit/domain/agents/test_workflow_agent_batch.py

def test_workflow_agent_creates_nodes_batch():
    """应支持批量创建节点"""

def test_workflow_agent_creates_edges_from_plan():
    """应根据规划创建边"""

def test_workflow_agent_executes_from_plan():
    """应执行完整工作流规划"""

def test_workflow_agent_reports_progress():
    """应报告执行进度"""
```

### Phase 8.6: 真实场景端到端测试

**测试优先**:
```python
# tests/integration/test_decision_execution_e2e.py

def test_e2e_data_analysis_workflow():
    """端到端：用户要求分析数据 → 自动创建工作流 → 执行 → 返回结果"""
    # 1. 用户输入："分析这份销售数据，生成趋势图"
    # 2. ConversationAgent 规划：
    #    - Node1(python): 读取数据
    #    - Node2(python): 计算趋势
    #    - Node3(python): 生成图表
    # 3. 验证规划
    # 4. 执行工作流
    # 5. 返回结果

def test_e2e_http_api_integration():
    """端到端：调用外部 API 并处理结果"""

def test_e2e_database_query_workflow():
    """端到端：查询数据库并生成报表"""

def test_e2e_multi_step_llm_workflow():
    """端到端：多步骤 LLM 处理流程"""
```

---

## 4. 详细实现计划

### Phase 8.1: NodeDefinition (预计 15 个测试)

| 文件 | 内容 |
|------|------|
| `src/domain/agents/node_definition.py` | NodeDefinition, NodeDefinitionFactory |
| `tests/unit/domain/agents/test_node_definition.py` | 单元测试 |

**核心代码结构**:
```python
@dataclass
class NodeDefinition:
    """节点定义"""
    id: str = field(default_factory=lambda: str(uuid4()))
    node_type: NodeType
    name: str
    description: str = ""
    # 类型特定配置
    code: str | None = None           # PYTHON
    prompt: str | None = None         # LLM
    url: str | None = None            # HTTP
    method: str = "GET"               # HTTP
    query: str | None = None          # DATABASE
    # 通用
    config: dict[str, Any] = field(default_factory=dict)
    input_schema: dict[str, str] = field(default_factory=dict)
    output_schema: dict[str, str] = field(default_factory=dict)

    def validate(self) -> list[str]:
        """验证必填字段"""
        errors = []
        if self.node_type == NodeType.PYTHON and not self.code:
            errors.append("Python 节点需要 code 字段")
        if self.node_type == NodeType.LLM and not self.prompt:
            errors.append("LLM 节点需要 prompt 字段")
        # ...
        return errors

class NodeDefinitionFactory:
    """节点定义工厂"""

    @staticmethod
    def create_python_node(name: str, code: str, **kwargs) -> NodeDefinition:
        """创建 Python 节点定义"""

    @staticmethod
    def create_llm_node(name: str, prompt: str, **kwargs) -> NodeDefinition:
        """创建 LLM 节点定义"""
```

### Phase 8.2: WorkflowPlan (预计 12 个测试)

| 文件 | 内容 |
|------|------|
| `src/domain/agents/workflow_plan.py` | WorkflowPlan, EdgeDefinition |
| `tests/unit/domain/agents/test_workflow_plan.py` | 单元测试 |

**核心代码结构**:
```python
@dataclass
class WorkflowPlan:
    """工作流规划"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    goal: str = ""
    nodes: list[NodeDefinition] = field(default_factory=list)
    edges: list[EdgeDefinition] = field(default_factory=list)

    def validate(self) -> list[str]:
        """验证规划完整性"""

    def get_execution_order(self) -> list[str]:
        """获取拓扑执行顺序"""

    def has_circular_dependency(self) -> bool:
        """检测循环依赖"""
```

### Phase 8.3: ConversationAgent 增强 (预计 10 个测试)

| 文件 | 内容 |
|------|------|
| `src/domain/agents/conversation_agent.py` | 扩展现有类 |
| `tests/unit/domain/agents/test_conversation_agent_planning.py` | 新增测试 |

**新增方法**:
```python
class ConversationAgent:
    # 新增方法
    async def create_workflow_plan(self, goal: str) -> WorkflowPlan:
        """根据目标创建工作流规划"""

    async def decompose_to_nodes(self, goal: str) -> list[NodeDefinition]:
        """将目标分解为节点定义列表"""

# LLM 接口扩展
class ConversationAgentLLM(Protocol):
    # 新增方法
    async def plan_workflow(self, goal: str, context: dict) -> dict[str, Any]:
        """规划工作流结构"""
```

### Phase 8.4: DecisionExecutionBridge (预计 15 个测试)

| 文件 | 内容 |
|------|------|
| `src/domain/services/decision_execution_bridge.py` | 桥接服务 |
| `tests/unit/domain/services/test_decision_execution_bridge.py` | 单元测试 |

**核心代码结构**:
```python
class DecisionExecutionBridge:
    """决策执行桥接器

    职责：
    1. 订阅 DecisionMadeEvent
    2. 验证决策（通过 DecisionValidator）
    3. 转发给 WorkflowAgent 执行
    4. 发布执行结果
    """

    def __init__(
        self,
        event_bus: EventBus,
        decision_validator: DecisionValidator,
        workflow_agent_factory: Callable[[], WorkflowAgent],
    ):
        self.event_bus = event_bus
        self.validator = decision_validator
        self.workflow_agent_factory = workflow_agent_factory

    async def start(self) -> None:
        """启动桥接器，订阅事件"""
        self.event_bus.subscribe(DecisionMadeEvent, self._handle_decision)

    async def _handle_decision(self, event: DecisionMadeEvent) -> None:
        """处理决策事件"""
        # 1. 验证决策
        validation_result = self.validator.validate(...)
        if validation_result.status == ValidationStatus.REJECTED:
            await self._publish_rejection(event, validation_result)
            return

        # 2. 执行决策
        workflow_agent = self.workflow_agent_factory()
        result = await workflow_agent.handle_decision(event.payload)

        # 3. 发布结果
        await self._publish_result(event, result)
```

### Phase 8.5: WorkflowAgent 批量操作 (预计 12 个测试)

| 文件 | 内容 |
|------|------|
| `src/domain/agents/workflow_agent.py` | 扩展现有类 |
| `tests/unit/domain/agents/test_workflow_agent_batch.py` | 新增测试 |

**新增方法**:
```python
class WorkflowAgent:
    # 新增方法
    def create_nodes_batch(self, definitions: list[NodeDefinition]) -> list[Node]:
        """批量创建节点"""

    def create_edges_batch(self, edges: list[EdgeDefinition]) -> list[Edge]:
        """批量创建边"""

    async def execute_plan(self, plan: WorkflowPlan) -> dict[str, Any]:
        """执行完整工作流规划"""
```

### Phase 8.6: 端到端测试 (预计 8 个测试)

| 文件 | 内容 |
|------|------|
| `tests/integration/test_decision_execution_e2e.py` | 真实场景测试 |

---

## 5. 测试总览

| 阶段 | 测试文件 | 预计测试数 |
|------|----------|------------|
| 8.1 | test_node_definition.py | 15 |
| 8.2 | test_workflow_plan.py | 12 |
| 8.3 | test_conversation_agent_planning.py | 10 |
| 8.4 | test_decision_execution_bridge.py | 15 |
| 8.5 | test_workflow_agent_batch.py | 12 |
| 8.6 | test_decision_execution_e2e.py | 8 |
| **总计** | | **~72** |

---

## 6. 真实场景测试用例

### 场景 1: 销售数据分析

**用户输入**: "分析这份销售数据，找出销量最高的产品，并生成趋势图"

**期望输出**:
1. ConversationAgent 规划:
   ```yaml
   WorkflowPlan:
     nodes:
       - name: "读取数据"
         type: python
         code: |
           import pandas as pd
           df = pd.read_csv(input_file)
           return {"data": df.to_dict()}
       - name: "计算Top产品"
         type: python
         code: |
           df = pd.DataFrame(inputs["读取数据"]["data"])
           top = df.groupby("product")["sales"].sum().nlargest(10)
           return {"top_products": top.to_dict()}
       - name: "生成趋势图"
         type: python
         code: |
           import matplotlib.pyplot as plt
           # ... 生成图表代码
     edges:
       - source: "读取数据" → target: "计算Top产品"
       - source: "计算Top产品" → target: "生成趋势图"
   ```

2. 验证通过
3. WorkflowAgent 创建节点和边
4. 执行工作流
5. 返回结果（趋势图路径）

### 场景 2: API 数据整合

**用户输入**: "调用天气 API 获取北京天气，然后生成一份天气报告"

**期望输出**:
1. WorkflowPlan with HTTP + LLM nodes
2. 执行并返回报告

---

## 7. 风险与对策

| 风险 | 对策 |
|------|------|
| LLM 生成的代码不安全 | 代码沙箱执行 + 白名单验证 |
| 工作流规划过于复杂 | 限制最大节点数 + 复杂度检查 |
| 执行超时 | 复用 Phase 7 的 ExecutionMonitor |
| 节点间数据传递问题 | 明确的 input/output schema 验证 |

---

## 8. 依赖关系

Phase 8 依赖:
- ✅ Phase 7.1: EnhancedRuleRepository (规则验证)
- ✅ Phase 7.2: DecisionValidator (决策验证)
- ✅ Phase 7.3: ExecutionMonitor (执行监控)
- ✅ Phase 7.5: 集成测试基础

---

**预计总工作量**: ~72 个测试，分 6 个子阶段实施
**开始日期**: 2025-12-02
