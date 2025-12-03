# 现状审计：多 Agent 协作系统架构

> 文档日期：2025-12-03
> 审计范围：ConversationAgent / WorkflowAgent / CoordinatorAgent
> 状态：Phase 5 完成，知识库集成已实现

---

## 1. 系统概览

### 1.1 三 Agent 架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         用户交互层                                    │
│                    (FastAPI + WebSocket)                             │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     ConversationAgent                                │
│                    "大脑" - 理解与决策                                │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ ReAct 循环: Thought → Action → Observation                  │    │
│  │ 目标分解: 复杂目标 → 子目标栈                                  │    │
│  │ 意图分类: greeting/simple_query/complex_task                │    │
│  │ 工作流规划: 生成节点和边的定义                                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                               │ DecisionMadeEvent                    │
└───────────────────────────────┼─────────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        EventBus                                      │
│              (发布/订阅 + 中间件机制)                                 │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Coordinator 中间件: 拦截 DecisionMadeEvent                   │    │
│  │ 规则验证 → 通过/拒绝                                          │    │
│  └─────────────────────────────────────────────────────────────┘    │
└───────────────────────────────┼─────────────────────────────────────┘
                    ┌───────────┴───────────┐
                    ▼                       ▼
     DecisionValidatedEvent          DecisionRejectedEvent
                    │                       │
                    ▼                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     WorkflowAgent                                    │
│                  "执行者" - 节点执行                                  │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ 节点管理: 创建、配置、连接节点                                 │    │
│  │ 工作流执行: DAG 拓扑排序 → 顺序执行                           │    │
│  │ 状态同步: 发布执行事件                                        │    │
│  │ 反思机制: 执行后评估和建议                                     │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    CoordinatorAgent                                  │
│                  "守门人" - 验证与监控                                │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ 规则引擎: 动态规则验证                                        │    │
│  │ 工作流监控: 状态跟踪、统计                                     │    │
│  │ 失败处理: RETRY/SKIP/ABORT/REPLAN                           │    │
│  │ 子Agent管理: 生成、调度、结果收集                              │    │
│  │ 上下文压缩: 知识检索、上下文注入                               │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心文件位置

| 组件 | 文件路径 | 行数 | 职责 |
|------|---------|------|------|
| ConversationAgent | `src/domain/agents/conversation_agent.py` | ~800 | ReAct循环、目标分解、决策生成 |
| WorkflowAgent | `src/domain/agents/workflow_agent.py` | ~600 | 节点管理、工作流执行、状态同步 |
| CoordinatorAgent | `src/domain/agents/coordinator_agent.py` | ~2200 | 规则验证、监控、失败处理、知识集成 |
| EventBus | `src/domain/services/event_bus.py` | ~280 | 发布/订阅、中间件链 |
| NodeDefinition | `src/domain/agents/node_definition.py` | ~520 | 节点类型定义、层次化结构 |

---

## 2. ConversationAgent 能力分析

### 2.1 已实现功能

#### ReAct 循环 (Phase 1)
```python
# 位置: conversation_agent.py:38-75
class StepType(str, Enum):
    REASONING = "reasoning"      # 推理步骤
    ACTION = "action"            # 执行动作
    OBSERVATION = "observation"  # 观察结果

class ReActStep:
    step_type: StepType
    thought: str | None        # 思考内容
    action: dict | None        # 动作定义
    observation: str | None    # 观察结果
```

**核心方法：**
- `execute_step(user_input)` - 执行单步 ReAct
- `run(user_input)` - 运行完整 ReAct 循环直到完成
- `max_iterations` - 防止无限循环

#### 目标分解 (Phase 2)
```python
# 位置: conversation_agent.py:120-180
def push_goal(goal_id, description, parent_id=None)
def pop_goal() -> Goal | None
def current_goal() -> Goal | None
def decompose_goal(goal) -> list[Goal]
```

#### 意图分类 (Phase 14)
```python
# 位置: conversation_agent.py
class IntentType(str, Enum):
    GREETING = "greeting"              # 问候
    SIMPLE_QUERY = "simple_query"      # 简单查询
    COMPLEX_TASK = "complex_task"      # 复杂任务
    WORKFLOW_REQUEST = "workflow"      # 工作流请求
    UNKNOWN = "unknown"

async def classify_intent(user_input) -> IntentClassification
```

#### 决策发布 (Phase 8)
```python
# 位置: conversation_agent.py
class DecisionMadeEvent(Event):
    decision_type: str      # create_node, execute_workflow, etc.
    payload: dict           # 决策详情

class DecisionType(str, Enum):
    CREATE_NODE = "create_node"
    CREATE_WORKFLOW_PLAN = "create_workflow_plan"
    EXECUTE_WORKFLOW = "execute_workflow"
    RESPOND = "respond"
```

#### 简单消息处理 (Phase 15)
```python
# 位置: conversation_agent.py
class SimpleMessageEvent(Event):
    user_input: str
    response: str
    intent: str
    confidence: float
    session_id: str
```

### 2.2 状态机 (Phase 13)
```
IDLE ──user_input──▶ CLASSIFYING ──intent──▶ PROCESSING
  ▲                                              │
  │                                              ▼
  └──────────────────────────────────────── RESPONDING
```

---

## 3. WorkflowAgent 能力分析

### 3.1 已实现功能

#### 节点管理
```python
# 位置: workflow_agent.py
def create_node(decision: dict) -> Node
def add_node(node: Node)
def get_node(node_id: str) -> Node | None
def connect_nodes(source_id: str, target_id: str)
```

#### 支持的节点类型 (NodeType)
| 类型 | 用途 | 必填字段 |
|------|------|---------|
| START | 起始节点 | - |
| END | 结束节点 | - |
| PYTHON | Python代码执行 | code |
| LLM | LLM调用 | prompt |
| HTTP | HTTP请求 | url |
| DATABASE | 数据库查询 | query |
| CONDITION | 条件分支 | - |
| LOOP | 循环 | - |
| PARALLEL | 并行执行 | - |
| CONTAINER | 容器执行 (Phase 4) | code, image |

#### 工作流执行
```python
# 位置: workflow_agent.py
async def execute_workflow() -> dict
async def execute_node_with_result(node_id) -> ExecutionResult

# 发布的事件
class WorkflowExecutionStartedEvent(Event)
class WorkflowExecutionCompletedEvent(Event)
class NodeExecutionEvent(Event)
```

#### 反思机制 (Phase 16)
```python
class WorkflowReflectionCompletedEvent(Event):
    workflow_id: str
    assessment: str         # 评估内容
    should_retry: bool      # 是否需要重试
    confidence: float       # 置信度
    recommendations: list   # 建议列表
```

---

## 4. CoordinatorAgent 能力分析

### 4.1 规则引擎
```python
# 位置: coordinator_agent.py:47-83
@dataclass
class Rule:
    id: str
    name: str
    condition: Callable[[dict], bool]  # 验证条件
    priority: int = 10                 # 优先级
    error_message: str = "验证失败"
    correction: Callable | None = None # 修正函数

# 使用示例
coordinator.add_rule(Rule(
    id="safe_nodes",
    name="只允许安全节点",
    condition=lambda d: d.get("node_type") in ["LLM", "API"],
    priority=1
))
```

### 4.2 失败处理策略 (Phase 12)
```python
class FailureHandlingStrategy(str, Enum):
    RETRY = "retry"      # 重试执行
    SKIP = "skip"        # 跳过节点
    ABORT = "abort"      # 终止工作流
    REPLAN = "replan"    # 请求重新规划

# 配置
failure_strategy_config = {
    "default_strategy": FailureHandlingStrategy.RETRY,
    "max_retries": 3,
    "retry_delay": 1.0
}
```

### 4.3 子Agent管理 (Phase 3)
```python
# 注册子Agent类型
coordinator.register_subagent_type(SubAgentType.RESEARCHER, ResearcherAgent)
coordinator.register_subagent_type(SubAgentType.CODER, CoderAgent)

# 执行子Agent
result = await coordinator.execute_subagent(
    subagent_type="researcher",
    task_payload={"query": "search something"},
    context={"session_id": "..."},
    session_id="session_001"
)
```

### 4.4 上下文压缩 (Phase 5 阶段2-4)
```python
# 启用压缩
coordinator.start_context_compression()

# 获取压缩上下文
ctx = coordinator.get_compressed_context(workflow_id)

# 知识检索和注入
refs = await coordinator.retrieve_knowledge("Python 异常处理")
await coordinator.inject_knowledge_to_context(workflow_id, goal="处理错误")

# 获取对话Agent可用的上下文
agent_ctx = coordinator.get_context_for_conversation_agent(workflow_id)
```

### 4.5 容器执行监控 (Phase 4)
```python
coordinator.start_container_execution_listening()
executions = coordinator.get_workflow_container_executions(workflow_id)
logs = coordinator.get_container_logs(container_id)
stats = coordinator.get_container_execution_statistics()
```

---

## 5. 事件流分析

### 5.1 核心事件类型

| 事件 | 发布者 | 订阅者 | 用途 |
|------|--------|--------|------|
| DecisionMadeEvent | ConversationAgent | Coordinator (中间件) | 决策发布 |
| DecisionValidatedEvent | Coordinator | WorkflowAgent | 决策验证通过 |
| DecisionRejectedEvent | Coordinator | ConversationAgent | 决策被拒绝 |
| WorkflowExecutionStartedEvent | WorkflowAgent | Coordinator | 工作流开始 |
| WorkflowExecutionCompletedEvent | WorkflowAgent | Coordinator | 工作流完成 |
| NodeExecutionEvent | WorkflowAgent | Coordinator | 节点执行状态 |
| WorkflowReflectionCompletedEvent | WorkflowAgent | Coordinator | 反思完成 |
| SimpleMessageEvent | ConversationAgent | Coordinator | 简单消息处理 |
| SubAgentCompletedEvent | Coordinator | ConversationAgent | 子Agent完成 |
| SpawnSubAgentEvent | ConversationAgent | Coordinator | 请求生成子Agent |

### 5.2 典型事件流

**场景：用户请求创建工作流**
```
用户输入 "分析销售数据"
    │
    ▼
ConversationAgent.classify_intent()
    │ IntentType.COMPLEX_TASK
    ▼
ConversationAgent.execute_step()
    │ 生成工作流规划
    ▼
发布 DecisionMadeEvent(create_workflow_plan)
    │
    ▼
Coordinator 中间件拦截
    │ validate_decision()
    ▼
发布 DecisionValidatedEvent
    │
    ▼
WorkflowAgent.handle_decision()
    │ 创建节点、连接边
    ▼
发布 WorkflowExecutionStartedEvent
    │
    ▼
WorkflowAgent.execute_workflow()
    │ 执行每个节点
    │ 发布 NodeExecutionEvent (每个节点)
    ▼
发布 WorkflowExecutionCompletedEvent
    │
    ▼
Coordinator._handle_workflow_completed()
    │ 更新状态、压缩上下文
    ▼
发布 WorkflowReflectionCompletedEvent (如果启用)
```

---

## 6. 当前能力总结

### 6.1 已完成的能力

| 阶段 | 能力 | 状态 | 测试覆盖 |
|------|------|------|---------|
| Phase 1 | ReAct 循环 | ✅ 完成 | ✅ |
| Phase 2 | 目标分解 | ✅ 完成 | ✅ |
| Phase 3 | 子Agent调度 | ✅ 完成 | ✅ |
| Phase 4 | 容器执行/层次化节点 | ✅ 完成 | ✅ |
| Phase 5 | 知识库集成 | ✅ 完成 | ✅ |
| Phase 8 | 决策执行桥接 | ✅ 完成 | ✅ |
| Phase 11 | 执行结果标准化 | ✅ 完成 | ✅ |
| Phase 12 | 失败处理策略 | ✅ 完成 | ✅ |
| Phase 13 | 状态机 | ✅ 完成 | ✅ |
| Phase 14 | 意图分类 | ✅ 完成 | ✅ |
| Phase 15 | 简单消息处理 | ✅ 完成 | ✅ |
| Phase 16 | 反思机制 | ✅ 完成 | ✅ |

### 6.2 识别的缺口

| 缺口 | 描述 | 优先级 | 影响 |
|------|------|--------|------|
| 真实 LLM 集成测试 | 当前测试使用 Mock LLM | 中 | 无法验证实际 LLM 行为 |
| 端到端工作流测试 | 缺少完整的用户场景测试 | 高 | 无法验证完整链路 |
| 错误恢复测试 | REPLAN 策略缺少真实测试 | 中 | 失败恢复可能不完整 |
| 性能基准 | 无性能测试和基准数据 | 低 | 无法评估系统性能 |
| WebSocket 同步测试 | 画布同步缺少端到端测试 | 中 | 前端同步可能有问题 |

---

## 7. 测试覆盖情况

### 7.1 单元测试

```bash
# 运行所有 Agent 单元测试
pytest tests/unit/domain/agents/ -v

# 关键测试文件
tests/unit/domain/agents/test_conversation_agent.py      # ~20 tests
tests/unit/domain/agents/test_workflow_agent.py          # ~15 tests
tests/unit/domain/agents/test_coordinator_agent.py       # ~25 tests
tests/unit/domain/agents/test_spawn_subagent.py          # ~10 tests
tests/unit/domain/agents/test_subagent_result_handling.py # ~8 tests
```

### 7.2 集成测试

```bash
# 运行 Agent 协作集成测试
pytest tests/integration/domain/agents/test_agent_collaboration.py -v

# 关键测试
test_setup_agent_collaboration_system        # 系统设置
test_valid_decision_flows_through_system     # 有效决策流转
test_invalid_decision_is_rejected            # 无效决策拒绝
test_user_request_creates_workflow           # 用户请求创建工作流
test_conversation_agent_receives_rejection_feedback  # 反馈循环
test_execute_workflow_with_status_updates    # 工作流执行
test_complete_user_interaction_flow          # 完整用户交互
test_decision_rejection_and_retry            # 拒绝后重试
```

### 7.3 端到端测试

```bash
# 运行端到端测试
pytest tests/integration/test_decision_to_execution_e2e.py -v

# 关键测试
test_full_pipeline_from_user_input_to_execution  # 完整管道
test_complex_workflow_with_parallel_branches     # 复杂工作流
```

---

## 8. 运行验证脚本

### 8.1 验证 ReAct 执行链路

```bash
# 运行 Agent 协作测试
pytest tests/integration/domain/agents/test_agent_collaboration.py::TestRealWorldScenario::test_complete_user_interaction_flow -v

# 运行端到端决策执行测试
pytest tests/integration/test_decision_to_execution_e2e.py::TestEndToEndDecisionExecution::test_full_pipeline_from_user_input_to_execution -v
```

### 8.2 验证知识库集成

```bash
# 运行知识库集成测试
pytest tests/unit/domain/services/test_coordinator_knowledge_integration.py -v
pytest tests/unit/domain/services/test_knowledge_injection.py -v
pytest tests/unit/domain/services/test_knowledge_compression_integration.py -v
```

---

## 9. 架构建议

### 9.1 短期改进

1. **添加真实场景端到端测试**：创建使用真实 LLM 的集成测试（可选跳过）
2. **补充错误恢复测试**：测试 REPLAN 策略的完整流程
3. **添加性能基准**：测量关键路径的延迟

### 9.2 中期改进

1. **事件溯源**：持久化事件日志，支持回放和审计
2. **分布式支持**：考虑 Agent 分布式部署场景
3. **监控仪表盘**：实时展示 Agent 状态和事件流

### 9.3 长期演进

1. **插件化 Agent**：支持动态加载新 Agent 类型
2. **多租户隔离**：支持多用户/多组织的 Agent 隔离
3. **自动扩缩容**：根据负载自动调整 Agent 实例

---

## 附录 A：关键类型定义

### A.1 ExecutionResult
```python
@dataclass
class ExecutionResult:
    success: bool
    output: dict
    error: str | None
    error_code: ErrorCode | None
    execution_time: float
    retryable: bool
```

### A.2 CompressedContext
```python
@dataclass
class CompressedContext:
    workflow_id: str
    task_goal: str
    execution_status: dict
    node_summary: list
    error_log: list
    knowledge_references: list
    reflection_summary: dict
    next_actions: list
    conversation_summary: str
```

### A.3 KnowledgeReference
```python
@dataclass
class KnowledgeReference:
    source_id: str
    title: str
    content_preview: str
    relevance_score: float
    document_id: str | None
    source_type: str
```

---

## 附录 B：配置参数

### B.1 CoordinatorAgent
```python
CoordinatorAgent(
    event_bus=event_bus,
    rejection_rate_threshold=0.5,      # 拒绝率告警阈值
    circuit_breaker_config={...},      # 熔断器配置
    context_bridge=context_bridge,     # 上下文桥接器
    failure_strategy_config={          # 失败处理配置
        "default_strategy": FailureHandlingStrategy.RETRY,
        "max_retries": 3,
        "retry_delay": 1.0,
    },
    context_compressor=compressor,     # 上下文压缩器
    snapshot_manager=snapshot_mgr,     # 快照管理器
    knowledge_retriever=retriever,     # 知识检索器
)
```

### B.2 ConversationAgent
```python
ConversationAgent(
    session_context=session_ctx,
    llm=llm,                          # LLM 实例
    event_bus=event_bus,
    max_iterations=10,                 # 最大 ReAct 迭代次数
)
```

### B.3 WorkflowAgent
```python
WorkflowAgent(
    workflow_context=workflow_ctx,
    node_factory=factory,
    node_executor=executor,           # 节点执行器
    event_bus=event_bus,
)
```
