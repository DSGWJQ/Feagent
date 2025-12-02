# Multi-Agent Orchestration Architecture

## 概述

本文档定义了 Feagent 多Agent协作系统的架构，包括三个核心Agent的职责、事件流、数据源和上下文对象。

## 架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Multi-Agent Orchestration                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐        ┌──────────────────┐        ┌────────────────┐ │
│  │  Conversation    │        │   Coordinator    │        │   Workflow     │ │
│  │     Agent        │        │     Agent        │        │     Agent      │ │
│  │                  │        │                  │        │                │ │
│  │  • ReAct 推理    │        │  • 规则验证      │        │  • 节点执行    │ │
│  │  • 目标分解      │        │  • 决策拦截      │        │  • 工作流管理  │ │
│  │  • 决策生成      │        │  • 纠偏机制      │        │  • 状态同步    │ │
│  └────────┬─────────┘        └────────┬─────────┘        └───────┬────────┘ │
│           │                          │                          │          │
│           │  DecisionMadeEvent       │ as_middleware()          │          │
│           │                          │                          │          │
│           ▼                          ▼                          │          │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                           EventBus                                      │ │
│  │                                                                         │ │
│  │  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐ │ │
│  │  │ Middlewares │→ │   Event Log     │→ │     Subscribers             │ │ │
│  │  │ (Coordinator│  │                 │  │  (WorkflowAgent,            │ │ │
│  │  │  Validation)│  │                 │  │   CanvasSynchronizer, etc.) │ │ │
│  │  └─────────────┘  └─────────────────┘  └─────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│           │                                                      │          │
│           │                                                      │          │
│           ▼                                                      ▼          │
│  ┌────────────────────┐                              ┌────────────────────┐ │
│  │   画布 (Canvas)     │                              │    对话 (Chat)      │ │
│  │   数据源            │                              │    数据源           │ │
│  │                    │                              │                    │ │
│  │  • 节点/边状态      │                              │  • 会话历史         │ │
│  │  • 执行状态         │                              │  • 目标栈           │ │
│  │  • 实时同步         │                              │  • 决策历史         │ │
│  └────────────────────┘                              └────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Agent 职责定义

### 1. ConversationAgent (对话Agent)

**核心职责**: 作为用户交互的主入口，执行ReAct推理循环。

| 能力 | 描述 |
|------|------|
| ReAct 推理 | Thought → Action → Observation 循环 |
| 目标分解 | 将复杂目标分解为可执行的子目标 |
| 决策生成 | 生成 CREATE_NODE、EXECUTE_WORKFLOW 等决策 |
| 上下文感知 | 利用 SessionContext 进行推理 |

**发布的事件**:
- `DecisionMadeEvent`: 当做出决策时发布

**数据源**: 对话 (Chat)
- `SessionContext.conversation_history`: 会话历史
- `SessionContext.goal_stack`: 目标栈
- `SessionContext.decision_history`: 决策历史

### 2. CoordinatorAgent (协调者Agent)

**核心职责**: 作为EventBus中间件，验证和拦截决策。

| 能力 | 描述 |
|------|------|
| 规则验证 | 通过 RuleEngine 检查决策合法性 |
| 决策拦截 | 作为中间件阻止不合法的决策 |
| 纠偏机制 | 拒绝或修正违规决策 |
| 流量监控 | 统计决策通过率和异常模式 |

**发布的事件**:
- `DecisionValidatedEvent`: 决策验证通过时发布
- `DecisionRejectedEvent`: 决策被拒绝时发布

**运行模式**: 中间件 (通过 `as_middleware()` 注入 EventBus)

### 3. WorkflowAgent (工作流Agent)

**核心职责**: 执行工作流，管理节点生命周期。

| 能力 | 描述 |
|------|------|
| 节点管理 | 创建、配置、连接节点 |
| 工作流执行 | 按 DAG 拓扑顺序执行节点 |
| 状态同步 | 将执行状态同步到画布 |
| 结果汇报 | 向对话Agent反馈执行结果 |

**发布的事件**:
- `WorkflowExecutionStartedEvent`: 工作流开始执行
- `WorkflowExecutionCompletedEvent`: 工作流执行完成
- `NodeExecutionEvent`: 节点执行状态变化

**数据源**: 画布 (Canvas)
- `WorkflowContext.node_outputs`: 节点输出数据
- `WorkflowContext.variables`: 工作流变量
- 实时同步到前端 Canvas

## 事件顺序图

```
┌─────────┐          ┌─────────┐          ┌───────────┐          ┌──────────┐
│  User   │          │Conversa-│          │Coordinator│          │ Workflow │
│         │          │tionAgent│          │   Agent   │          │  Agent   │
└────┬────┘          └────┬────┘          └─────┬─────┘          └────┬─────┘
     │                    │                     │                     │
     │ 1. 用户输入        │                     │                     │
     │───────────────────>│                     │                     │
     │                    │                     │                     │
     │                    │ 2. ReAct 推理       │                     │
     │                    │─────────────────────│                     │
     │                    │                     │                     │
     │                    │ 3. 发布 DecisionMadeEvent                 │
     │                    │────────────────────>│                     │
     │                    │                     │                     │
     │                    │                     │ 4. 规则验证         │
     │                    │                     │─────────────────────│
     │                    │                     │                     │
     │                    │                     │ 5a. 验证通过:       │
     │                    │                     │    发布 DecisionValidatedEvent
     │                    │                     │────────────────────>│
     │                    │                     │                     │
     │                    │                     │                     │ 6. 处理决策
     │                    │                     │                     │────────────
     │                    │                     │                     │
     │                    │                     │                     │ 7. 发布 NodeExecutionEvent
     │                    │                     │<────────────────────│
     │                    │                     │                     │
     │                    │                     │                     │ 8. 发布 WorkflowExecutionCompletedEvent
     │                    │<───────────────────────────────────────────│
     │                    │                     │                     │
     │ 9. 返回结果        │                     │                     │
     │<───────────────────│                     │                     │
     │                    │                     │                     │
     │                    │ 5b. 验证失败 (Alternative Flow):          │
     │                    │                     │                     │
     │                    │                     │ 发布 DecisionRejectedEvent
     │                    │<────────────────────│                     │
     │                    │                     │                     │
     │ 通知用户决策被拒绝 │                     │                     │
     │<───────────────────│                     │                     │
     │                    │                     │                     │
```

## 上下文对象

### GlobalContext (全局上下文)

```python
@dataclass
class GlobalContext:
    user_id: str                           # 用户ID
    user_preferences: dict[str, Any]       # 用户偏好
    system_config: dict[str, Any]          # 系统配置
```

### SessionContext (会话上下文)

```python
@dataclass
class SessionContext:
    id: str                                # 会话ID
    global_context: GlobalContext          # 全局上下文引用
    conversation_history: list[dict]       # 对话历史
    goal_stack: list[Goal]                 # 目标栈
    decision_history: list[dict]           # 决策历史
```

### WorkflowContext (工作流上下文)

```python
@dataclass
class WorkflowContext:
    id: str                                # 上下文ID
    workflow_id: str                       # 工作流ID
    session_context: SessionContext        # 会话上下文引用
    node_outputs: dict[str, Any]           # 节点输出
    variables: dict[str, Any]              # 工作流变量
```

### NodeContext (节点上下文)

```python
@dataclass
class NodeContext:
    id: str                                # 上下文ID
    node_id: str                           # 节点ID
    workflow_context: WorkflowContext      # 工作流上下文引用
    local_variables: dict[str, Any]        # 节点局部变量
```

## 事件类型定义

### 决策事件 (来自 ConversationAgent)

```python
@dataclass
class DecisionMadeEvent(Event):
    decision_type: str           # create_node, execute_workflow, etc.
    decision_id: str             # 决策唯一ID
    payload: dict[str, Any]      # 决策详情
    confidence: float            # 置信度
```

### 验证事件 (来自 CoordinatorAgent)

```python
@dataclass
class DecisionValidatedEvent(Event):
    original_decision_id: str    # 原始决策ID
    decision_type: str           # 决策类型
    payload: dict[str, Any]      # 经验证的决策内容

@dataclass
class DecisionRejectedEvent(Event):
    original_decision_id: str    # 原始决策ID
    decision_type: str           # 决策类型
    reason: str                  # 拒绝原因
    errors: list[str]            # 错误详情
```

### 执行事件 (来自 WorkflowAgent)

```python
@dataclass
class WorkflowExecutionStartedEvent(Event):
    workflow_id: str             # 工作流ID
    node_count: int              # 节点数量

@dataclass
class WorkflowExecutionCompletedEvent(Event):
    workflow_id: str             # 工作流ID
    status: str                  # completed, failed
    result: dict[str, Any]       # 执行结果

@dataclass
class NodeExecutionEvent(Event):
    node_id: str                 # 节点ID
    node_type: str               # 节点类型
    status: str                  # running, completed, failed
    result: dict[str, Any]       # 执行结果
    error: str | None            # 错误信息
```

## 数据源说明

### 画布 (Canvas) 数据源

画布数据源由 WorkflowAgent 管理，包括：

| 数据项 | 描述 | 同步方式 |
|--------|------|----------|
| 节点状态 | 节点类型、配置、位置 | WebSocket 实时同步 |
| 边状态 | 节点连接关系 | WebSocket 实时同步 |
| 执行状态 | 节点运行状态 | 通过 NodeExecutionEvent |

**同步机制**: `CanvasSynchronizer` 订阅 WorkflowAgent 的事件，通过 WebSocket 推送到前端。

### 对话 (Chat) 数据源

对话数据源由 ConversationAgent 管理，包括：

| 数据项 | 描述 | 存储位置 |
|--------|------|----------|
| 会话历史 | 用户与系统的对话记录 | SessionContext |
| 目标栈 | 当前活跃的目标层级 | SessionContext |
| 决策历史 | 所有已做出的决策 | SessionContext |

**访问方式**: 通过 `ConversationAgent.get_context_for_reasoning()` 获取完整上下文。

## 完成定义 (Definition of Done)

### 阶段 1 完成标准

1. **文档完成**
   - [x] 架构图清晰展示三个 Agent 的职责和通信关系
   - [x] 事件顺序图展示完整的决策流程
   - [x] 上下文对象定义完整

2. **代码实现**
   - [ ] EventBus 正确注册三个 Agent
   - [ ] Conversation 可发布 DecisionMadeEvent
   - [ ] Coordinator 中间件可验证决策
   - [ ] Workflow 可订阅经验证的决策并执行

3. **测试覆盖**
   - [ ] 最小示例可触发完整链路：对话决策→协调验证→工作流执行
   - [ ] 日志中可见三个事件
   - [ ] 集成测试覆盖主链路

### 验收标准

```python
# 验收示例代码
async def test_full_orchestration_flow():
    """验收测试：完整的 Agent 协作流程"""
    # 1. 创建 EventBus
    event_bus = EventBus()

    # 2. 注册 Coordinator 中间件
    coordinator = CoordinatorAgent(event_bus=event_bus)
    event_bus.add_middleware(coordinator.as_middleware())

    # 3. 创建 WorkflowAgent 并订阅事件
    workflow_agent = WorkflowAgent(...)
    event_bus.subscribe(DecisionValidatedEvent, workflow_agent.handle_decision)

    # 4. 创建 ConversationAgent
    conversation_agent = ConversationAgent(event_bus=event_bus, ...)

    # 5. 触发决策
    result = await conversation_agent.run_async("创建一个 HTTP 节点")

    # 6. 验证事件日志
    assert any(isinstance(e, DecisionMadeEvent) for e in event_bus.event_log)
    assert any(isinstance(e, DecisionValidatedEvent) for e in event_bus.event_log)
    assert any(isinstance(e, NodeExecutionEvent) for e in event_bus.event_log)
```

## 文件位置

| 组件 | 文件路径 |
|------|----------|
| EventBus | `src/domain/services/event_bus.py` |
| ConversationAgent | `src/domain/agents/conversation_agent.py` |
| CoordinatorAgent | `src/domain/agents/coordinator_agent.py` |
| WorkflowAgent | `src/domain/agents/workflow_agent.py` |
| BidirectionalSyncProtocol | `src/domain/services/bidirectional_sync.py` |
| CanvasSynchronizer | `src/domain/services/canvas_synchronizer.py` |
| ContextManager | `src/domain/services/context_manager.py` |

## 阶段 3：画布与对话的双向同步

### 数据源原则

**画布 (Canvas) 为 Master（单一数据源）**

| 原则 | 说明 |
|------|------|
| 权威性 | 画布状态是工作流的权威数据源 |
| 实时性 | 用户直接操作画布，状态即时生效 |
| 同步方向 | 画布变更 → 通知对话 Agent 更新上下文 |

**理由**：
1. 用户直接在画布上操作节点/边
2. 画布状态是可视化的、用户可感知的
3. 对话 Agent 的上下文应该反映画布的真实状态

### 同步流程

```
┌──────────────┐     ┌───────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│   前端画布    │     │  WebSocket    │     │ BidirectionalSync    │     │ ConversationAgent│
│   (Canvas)   │     │   Handler     │     │     Service          │     │  SessionContext  │
└──────┬───────┘     └───────┬───────┘     └──────────┬───────────┘     └────────┬────────┘
       │                     │                        │                          │
       │ 1. 用户操作节点      │                        │                          │
       │────────────────────>│                        │                          │
       │                     │                        │                          │
       │                     │ 2. CanvasChangeEvent   │                          │
       │                     │───────────────────────>│                          │
       │                     │                        │                          │
       │                     │                        │ 3. 验证变更合法性         │
       │                     │                        │──────────────────────────│
       │                     │                        │                          │
       │                     │                        │ 4. 更新 SessionContext   │
       │                     │                        │─────────────────────────>│
       │                     │                        │                          │
       │                     │ 5. ACK/通知            │                          │
       │<────────────────────│──────────────────────<─│                          │
       │                     │                        │                          │
```

### 画布变更事件 (CanvasChangeEvent)

```python
@dataclass
class CanvasChangeEvent(Event):
    """画布变更事件 - 从前端到后端的反向同步

    当用户在画布上进行操作时，前端通过 WebSocket 发送此事件。
    """
    workflow_id: str                    # 工作流ID
    change_type: str                    # 变更类型: node_added, node_updated, node_deleted,
                                        #          edge_added, edge_deleted, node_moved
    change_data: dict[str, Any]         # 变更数据
    client_id: str                      # 客户端ID（用于排除回显）
    version: int = 0                    # 版本号（用于冲突检测）
    timestamp: datetime                 # 客户端时间戳
```

### 冲突处理策略

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| **Last Write Wins (LWW)** | 最后写入的状态为准 | 默认策略 |
| **版本号检测** | 基于版本号检测冲突 | 并发编辑场景 |
| **服务端优先** | 冲突时服务端状态优先 | 执行中的工作流 |

**冲突解决流程**：

```
1. 客户端发送变更请求（附带 version）
2. 服务端检查 version 是否匹配当前状态
3. 如果匹配：
   - 应用变更
   - 增加 version
   - 广播给其他客户端
4. 如果不匹配：
   - 返回冲突错误
   - 发送当前状态给客户端
   - 客户端合并后重试
```

### 用户手动修改 → 逆向同步 → 冲突解决 步骤

#### 步骤 1：用户手动修改

用户在画布上执行操作：
- 拖拽节点改变位置
- 修改节点配置
- 添加/删除节点
- 连接/断开边

#### 步骤 2：逆向同步

1. 前端捕获变更，构造 `CanvasChangeEvent`
2. 通过 WebSocket 发送到后端
3. `BidirectionalSyncService` 接收并处理：
   - 验证变更合法性
   - 更新 `ConversationAgent.SessionContext.canvas_state`
   - 通知 `ConversationAgent` 上下文已变更

#### 步骤 3：冲突解决

```python
async def handle_canvas_change(event: CanvasChangeEvent) -> SyncResult:
    """处理画布变更"""
    current_state = self.get_canvas_state(event.workflow_id)

    # 版本检查
    if event.version < current_state.version:
        return SyncResult(
            success=False,
            conflict=True,
            current_state=current_state,
            message="版本冲突，请基于最新状态重试"
        )

    # 应用变更
    new_state = self.apply_change(current_state, event)
    new_state.version += 1

    # 更新 ConversationAgent 上下文
    await self.notify_conversation_agent(event.workflow_id, new_state)

    # 广播给其他客户端
    await self.broadcast_to_others(event.workflow_id, new_state, exclude=event.client_id)

    return SyncResult(success=True, new_version=new_state.version)
```

### 验收标准

```python
async def test_canvas_to_conversation_sync():
    """验收测试：画布变更同步到对话上下文"""
    # 1. 设置环境
    event_bus = EventBus()
    sync_service = BidirectionalSyncService(event_bus)
    conversation_agent = ConversationAgent(session_context=session_ctx, ...)

    # 2. 模拟画布添加节点
    canvas_event = CanvasChangeEvent(
        workflow_id="wf_123",
        change_type="node_added",
        change_data={
            "node_id": "node_1",
            "node_type": "HTTP",
            "position": {"x": 100, "y": 200},
            "config": {"url": "https://api.example.com"}
        },
        client_id="client_1",
        version=1
    )

    # 3. 发布事件
    await event_bus.publish(canvas_event)

    # 4. 验证对话上下文已更新
    context = conversation_agent.get_context_for_reasoning()
    assert "node_1" in context.get("canvas_state", {}).get("nodes", {})

    # 5. 验证日志
    print(f"对话 Agent 上下文获取到节点: {context['canvas_state']['nodes']}")
```

## 更新历史

| 日期 | 版本 | 变更 |
|------|------|------|
| 2025-12-02 | 1.0 | 初始版本 - 阶段1架构定义 |
| 2025-12-02 | 1.1 | 阶段3 - 添加画布与对话双向同步架构 |
