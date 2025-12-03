# 多Agent协作系统架构指南

> 版本: 2.0
> 更新日期: 2025-12-03
> 状态: 已实现 Phase 1-6

---

## 目录

1. [系统概述](#1-系统概述)
2. [Agent协作模式](#2-agent协作模式)
3. [WebSocket通信流程](#3-websocket通信流程)
4. [子任务机制](#4-子任务机制)
5. [八段压缩器系统](#5-八段压缩器系统)
6. [核心组件详解](#6-核心组件详解)
7. [数据流与事件](#7-数据流与事件)
8. [快速上手](#8-快速上手)

---

## 1. 系统概述

### 1.1 架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户交互层                                      │
│  ┌───────────────────────┐        ┌────────────────────────────────────┐   │
│  │   对话面板 (Chat)      │◄──────►│      工作流画布 (Canvas)            │   │
│  │   • 自然语言输入        │        │      • 节点可视化                   │   │
│  │   • 执行进度展示        │        │      • 实时状态更新                 │   │
│  └───────────────────────┘        └────────────────────────────────────┘   │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │ WebSocket
┌────────────────────────────────────▼────────────────────────────────────────┐
│                             Agent 协作层                                     │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    CoordinatorAgent (协调者)                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │   │
│  │  │ 规则引擎     │  │ 上下文服务   │  │ 压缩器服务   │                │   │
│  │  │ Rule Engine  │  │ Context Svc  │  │ Compressor   │                │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                │   │
│  └────────────────────────────┬────────────────────────────────────────┘   │
│                               │                                             │
│         ┌─────────────────────┼─────────────────────┐                      │
│         ▼                     ▼                     ▼                      │
│  ┌─────────────────┐   ┌─────────────┐   ┌─────────────────────┐          │
│  │ ConversationAgent│   │  EventBus  │   │   WorkflowAgent     │          │
│  │   (对话Agent)    │◄─►│  事件总线   │◄─►│   (工作流Agent)      │          │
│  │                 │   │             │   │                     │          │
│  │  • 意图分类     │   │  • 事件分发  │   │  • 节点执行          │          │
│  │  • ReAct推理    │   │  • 状态同步  │   │  • 结果反馈          │          │
│  │  • 决策生成     │   │  • 订阅管理  │   │  • 进度报告          │          │
│  └─────────────────┘   └─────────────┘   └─────────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────────┐
│                             基础设施层                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ 上下文压缩器  │  │ 执行总结器   │  │ 知识检索器   │  │ 子Agent调度   │    │
│  │ Compressor   │  │ Summarizer   │  │ Retriever    │  │ Scheduler    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心组件

| 组件 | 位置 | 职责 |
|------|------|------|
| **CoordinatorAgent** | `src/domain/agents/coordinator_agent.py` | 协调者，管理规则、上下文、压缩服务 |
| **ConversationAgent** | `src/domain/agents/conversation_agent.py` | 对话Agent，意图分类、ReAct推理 |
| **WorkflowAgent** | `src/domain/agents/workflow_agent.py` | 工作流Agent，节点执行、状态管理 |
| **EventBus** | `src/domain/services/event_bus.py` | 事件总线，异步通信 |
| **PowerCompressor** | `src/domain/services/power_compressor.py` | 八段压缩器 |
| **ExecutionSummary** | `src/domain/agents/execution_summary.py` | 执行总结器 |
| **AgentChannel** | `src/domain/agents/agent_channel.py` | WebSocket通信信道 |

---

## 2. Agent协作模式

### 2.1 三Agent协作架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     用户输入 "分析销售数据"                       │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ConversationAgent (大脑)                       │
│  1. 意图分类 → WORKFLOW_TASK                                     │
│  2. 生成计划 → [数据获取, 数据处理, 报告生成]                     │
│  3. 发布 DecisionMadeEvent                                       │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CoordinatorAgent (裁判)                        │
│  1. 验证决策合法性                                               │
│  2. 检查规则约束                                                 │
│  3. 发布 DecisionValidatedEvent                                  │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    WorkflowAgent (执行者)                        │
│  1. 创建工作流节点                                               │
│  2. 执行节点序列                                                 │
│  3. 发布 NodeExecutionEvent / WorkflowCompletedEvent             │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    执行结果 → 返回用户                           │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 消息流转示例

```python
# 1. 用户输入触发 ConversationAgent
user_input = "帮我分析上个月的销售数据"

# 2. ConversationAgent 分类意图
intent = await conversation_agent.classify_intent(user_input)
# → IntentType.WORKFLOW_TASK

# 3. 生成决策并发布事件
decision = await conversation_agent.generate_decision(user_input)
await event_bus.publish(DecisionMadeEvent(
    decision_type="create_workflow",
    payload={"plan": [...]}
))

# 4. CoordinatorAgent 中间件拦截验证
# (作为 EventBus 中间件自动执行)

# 5. WorkflowAgent 接收验证后的决策
@event_bus.subscribe(DecisionValidatedEvent)
async def handle_validated(event):
    await workflow_agent.execute_plan(event.payload)

# 6. 执行完成后反馈
await event_bus.publish(WorkflowExecutionCompletedEvent(
    workflow_id="wf_123",
    status="completed",
    result={...}
))
```

---

## 3. WebSocket通信流程

### 3.1 消息类型定义

```python
class AgentMessageType(str, Enum):
    # 客户端 → 服务器
    TASK_REQUEST = "task_request"       # 任务请求
    CANCEL_TASK = "cancel_task"         # 取消任务
    PLAN_APPROVED = "plan_approved"     # 计划批准

    # 服务器 → 客户端
    PLAN_PROPOSED = "plan_proposed"     # 计划提议
    EXECUTION_STARTED = "execution_started"    # 执行开始
    EXECUTION_PROGRESS = "execution_progress"  # 执行进度
    EXECUTION_COMPLETED = "execution_completed" # 执行完成
    EXECUTION_FAILED = "execution_failed"       # 执行失败
    EXECUTION_SUMMARY = "execution_summary"     # 执行总结

    # Agent间通信
    WORKFLOW_DISPATCH = "workflow_dispatch"     # 工作流分发
    WORKFLOW_RESULT = "workflow_result"         # 工作流结果
```

### 3.2 通信流程图

```
┌──────────┐                    ┌──────────┐                    ┌──────────┐
│  前端    │                    │  后端    │                    │  Agent   │
│ (Client) │                    │ (Server) │                    │  System  │
└────┬─────┘                    └────┬─────┘                    └────┬─────┘
     │                               │                               │
     │  1. WebSocket 连接            │                               │
     │ ─────────────────────────────>│                               │
     │                               │                               │
     │  2. TASK_REQUEST              │                               │
     │ ─────────────────────────────>│  3. 分发任务                  │
     │                               │──────────────────────────────>│
     │                               │                               │
     │  4. PLAN_PROPOSED             │<──────────────────────────────│
     │<─────────────────────────────│                               │
     │                               │                               │
     │  5. PLAN_APPROVED             │                               │
     │ ─────────────────────────────>│  6. 开始执行                  │
     │                               │──────────────────────────────>│
     │                               │                               │
     │  7. EXECUTION_STARTED         │<──────────────────────────────│
     │<─────────────────────────────│                               │
     │                               │                               │
     │  8. EXECUTION_PROGRESS (多次) │<──────────────────────────────│
     │<─────────────────────────────│                               │
     │                               │                               │
     │  9. EXECUTION_COMPLETED       │<──────────────────────────────│
     │<─────────────────────────────│                               │
     │                               │                               │
     │ 10. EXECUTION_SUMMARY         │<──────────────────────────────│
     │<─────────────────────────────│                               │
     │                               │                               │
```

### 3.3 使用示例

```python
from src.domain.agents.agent_channel import (
    AgentWebSocketChannel,
    AgentChannelBridge,
    AgentMessage,
    AgentMessageType
)

# 1. 初始化信道
channel = AgentWebSocketChannel()
bridge = AgentChannelBridge(channel=channel)

# 2. 注册会话
await channel.register_session("session_1", websocket, "user_1")

# 3. 推送执行进度
await bridge.report_progress(
    session_id="session_1",
    workflow_id="wf_123",
    current_node="node_2",
    progress=0.5,
    message="正在处理数据..."
)

# 4. 推送执行总结
await bridge.push_execution_summary(
    session_id="session_1",
    summary=execution_summary
)
```

---

## 4. 子任务机制

### 4.1 子Agent类型

```python
class SubAgentType(str, Enum):
    DATA_ANALYZER = "data_analyzer"       # 数据分析
    CODE_GENERATOR = "code_generator"     # 代码生成
    KNOWLEDGE_RETRIEVER = "knowledge"     # 知识检索
    API_CALLER = "api_caller"             # API调用
    VALIDATOR = "validator"               # 验证器
```

### 4.2 子Agent调度流程

```
┌─────────────────────────────────────────────────────────────────┐
│                   ConversationAgent                              │
│  1. 识别需要子任务                                               │
│  2. 发布 SpawnSubAgentEvent                                      │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   CoordinatorAgent                               │
│  1. 接收 SpawnSubAgentEvent                                      │
│  2. 从 SubAgentRegistry 创建实例                                 │
│  3. 调用 execute_subagent()                                      │
│  4. 发布 SubAgentCompletedEvent                                  │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ConversationAgent                              │
│  1. 接收 SubAgentCompletedEvent                                  │
│  2. 合并子任务结果                                               │
│  3. 继续主任务                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 代码示例

```python
from src.domain.services.sub_agent_scheduler import SubAgentType

# 1. 注册子Agent类型
coordinator.register_subagent_type(SubAgentType.DATA_ANALYZER, DataAnalyzerAgent)

# 2. 执行子任务
result = await coordinator.execute_subagent(
    subagent_type="data_analyzer",
    task_payload={"data": sales_data},
    context={"goal": "分析销售趋势"},
    session_id="session_1"
)

# 3. 获取会话的所有子Agent结果
results = coordinator.get_session_subagent_results("session_1")
```

---

## 5. 八段压缩器系统

### 5.1 八段压缩格式

```
[1.任务目标]
  分析销售数据并生成报告

[2.执行状态]
  状态: partial
  进度: 65%

[3.节点摘要]
  - data_fetch: completed
  - data_process: completed
  - report_gen: failed

[4.子任务错误]
  - [TIMEOUT] API请求超时 (可重试)
    参考: API错误处理指南

[5.未解决问题]
  - [high] 数据源不稳定
    阻塞节点: report_gen
    建议: 切换备用数据源

[6.决策历史]
  - 使用缓存数据
    原因: 主数据源超时

[7.后续计划]
  1. 重试失败节点
     理由: 可重试错误
  2. 验证最终结果
     理由: 确保数据完整

[8.知识来源]
  - 数据分析指南 (相关度: 92%)
    应用到: task_goal, next_plan
```

### 5.2 数据结构

```python
from src.domain.services.power_compressor import (
    PowerCompressor,
    PowerCompressedContext,
    SubtaskError,
    UnresolvedIssue,
    NextPlanItem,
    KnowledgeSource
)

# 创建压缩上下文
ctx = PowerCompressedContext(
    workflow_id="wf_123",
    session_id="session_1",
    task_goal="分析销售数据",
    execution_status={"status": "partial", "progress": 0.65},
    subtask_errors=[
        SubtaskError(
            subtask_id="api_call",
            error_type="TIMEOUT",
            error_message="请求超时",
            occurred_at=datetime.now(),
            retryable=True
        )
    ],
    unresolved_issues=[...],
    next_plan=[...],
    knowledge_sources=[...]
)

# 生成八段摘要
summary_text = ctx.to_eight_segment_summary()
```

### 5.3 协调者查询接口

```python
# 压缩并存储总结
compressed = await coordinator.compress_and_store(execution_summary)

# 查询接口
errors = coordinator.query_subtask_errors("wf_123")
issues = coordinator.query_unresolved_issues("wf_123")
plans = coordinator.query_next_plan("wf_123")

# 获取对话Agent可用的上下文
context = coordinator.get_context_for_conversation("wf_123")

# 获取知识引用
knowledge = coordinator.get_knowledge_for_conversation("wf_123")
```

---

## 6. 核心组件详解

### 6.1 CoordinatorAgent

**主要职责：**
- 规则验证：验证决策合法性
- 上下文管理：提供分层上下文
- 失败处理：重试、跳过、终止策略
- 压缩服务：八段压缩和查询
- 子Agent管理：调度和监控

**关键方法：**

```python
class CoordinatorAgent:
    # Phase 1: 上下文服务
    def get_context(user_input, workflow_id) -> ContextResponse
    async def get_context_async(user_input, workflow_id) -> ContextResponse

    # 规则管理
    def add_rule(rule: Rule) -> None
    def validate_decision(decision: dict) -> ValidationResult

    # Phase 5: 执行总结
    def record_execution_summary(summary) -> None
    async def record_and_push_summary(summary) -> None

    # Phase 6: 压缩器
    async def compress_and_store(summary) -> PowerCompressedContext
    def query_subtask_errors(workflow_id) -> list
    def query_unresolved_issues(workflow_id) -> list
    def query_next_plan(workflow_id) -> list
    def get_context_for_conversation(workflow_id) -> dict
```

### 6.2 ConversationAgent

**主要职责：**
- 意图分类：识别用户意图类型
- ReAct推理：思考-行动-观察循环
- 决策生成：生成结构化决策
- 状态管理：维护对话状态机

**状态机：**

```
┌─────────┐  用户输入  ┌─────────┐  分类成功  ┌─────────┐
│  IDLE   │───────────>│CLASSIFYING│─────────>│PROCESSING│
└─────────┘            └─────────┘            └─────────┘
     ▲                                              │
     │                                              │
     │              ┌─────────┐                     │
     └──────────────│COMPLETED│<────────────────────┘
                    └─────────┘
```

### 6.3 WorkflowAgent

**主要职责：**
- 节点管理：创建、执行、更新节点
- 执行控制：拓扑排序执行
- 状态报告：进度和结果反馈
- 反思机制：执行后评估

---

## 7. 数据流与事件

### 7.1 核心事件类型

| 事件 | 触发者 | 订阅者 | 用途 |
|------|--------|--------|------|
| `DecisionMadeEvent` | ConversationAgent | CoordinatorAgent | 决策验证 |
| `DecisionValidatedEvent` | CoordinatorAgent | WorkflowAgent | 执行授权 |
| `DecisionRejectedEvent` | CoordinatorAgent | ConversationAgent | 决策拒绝 |
| `WorkflowExecutionStartedEvent` | WorkflowAgent | CoordinatorAgent | 执行开始 |
| `NodeExecutionEvent` | WorkflowAgent | CoordinatorAgent | 节点状态 |
| `WorkflowExecutionCompletedEvent` | WorkflowAgent | ConversationAgent | 执行完成 |
| `SpawnSubAgentEvent` | ConversationAgent | CoordinatorAgent | 子任务派发 |
| `SubAgentCompletedEvent` | CoordinatorAgent | ConversationAgent | 子任务完成 |

### 7.2 事件订阅示例

```python
from src.domain.services.event_bus import EventBus

event_bus = EventBus()

# 订阅事件
event_bus.subscribe(WorkflowExecutionCompletedEvent, handle_completed)

# 发布事件
await event_bus.publish(WorkflowExecutionCompletedEvent(
    workflow_id="wf_123",
    status="completed",
    result={"output": "..."}
))

# 添加中间件（协调者验证）
event_bus.add_middleware(coordinator.as_middleware())
```

---

## 8. 快速上手

### 8.1 初始化系统

```python
from src.domain.services.event_bus import EventBus
from src.domain.agents.coordinator_agent import CoordinatorAgent
from src.domain.agents.conversation_agent import ConversationAgent
from src.domain.agents.workflow_agent import WorkflowAgent

# 1. 创建事件总线
event_bus = EventBus()

# 2. 创建协调者
coordinator = CoordinatorAgent(event_bus=event_bus)

# 3. 创建对话Agent
conversation_agent = ConversationAgent(
    coordinator=coordinator,
    event_bus=event_bus
)

# 4. 创建工作流Agent
workflow_agent = WorkflowAgent(event_bus=event_bus)

# 5. 启动监控
coordinator.start_monitoring()
coordinator.start_reflection_listening()
coordinator.start_context_compression()
```

### 8.2 处理用户请求

```python
async def handle_user_request(user_input: str, session_id: str):
    # 1. 获取上下文
    context = await coordinator.get_context_async(
        user_input=user_input,
        workflow_id=None
    )

    # 2. 处理消息
    result = await conversation_agent.process_message(
        user_input=user_input,
        session_id=session_id,
        context=context
    )

    # 3. 返回结果
    return result
```

### 8.3 查看执行总结

```python
# 获取执行总结
summary = coordinator.get_execution_summary("wf_123")

# 获取压缩上下文
ctx = coordinator.get_context_for_conversation("wf_123")

# 查看统计
stats = coordinator.get_summary_statistics()
compression_stats = coordinator.get_power_compression_statistics()
```

---

## 附录

### A. 文件位置索引

```
src/domain/agents/
├── coordinator_agent.py    # 协调者Agent
├── conversation_agent.py   # 对话Agent
├── workflow_agent.py       # 工作流Agent
├── agent_channel.py        # WebSocket信道
├── execution_summary.py    # 执行总结
├── node_definition.py      # 节点定义
└── container_executor.py   # 容器执行器

src/domain/services/
├── event_bus.py            # 事件总线
├── power_compressor.py     # 八段压缩器
├── context_compressor.py   # 上下文压缩
├── knowledge_reference.py  # 知识引用
├── sub_agent_scheduler.py  # 子Agent调度
└── execution_result.py     # 执行结果
```

### B. 测试文件

```
tests/unit/domain/agents/
├── test_coordinator_*.py   # 协调者测试
├── test_conversation_*.py  # 对话Agent测试
├── test_workflow_*.py      # 工作流测试
└── test_execution_summary.py

tests/unit/domain/services/
├── test_power_compressor.py  # 压缩器测试
└── test_context_compressor.py

tests/integration/
├── test_power_compressor_e2e.py  # 压缩器E2E
└── test_execution_summary_e2e.py # 总结E2E
```

### C. 版本历史

| 日期 | 版本 | 更新内容 |
|------|------|----------|
| 2025-12-01 | 1.0 | 初始架构设计 |
| 2025-12-03 | 2.0 | Phase 1-6 实现完成，添加八段压缩器、执行总结、WebSocket通信 |

---

**文档状态**: Phase 1-6 已实现
**下一步**: Phase 7 - 文档与运维
