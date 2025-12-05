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
| NodeDefinition | `src/domain/agents/node_definition.py` | ~990 | 节点类型定义、层次化结构、场景化模板（数据采集/指标计算/图表生成/数据分析） |

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

### 2.3 上下文容量感知 (Step 1: 模型上下文能力确认)

#### 功能概述
ConversationAgent 现在具备完整的上下文容量感知能力，能够：
- 自动识别 LLM 模型的上下文窗口限制
- 实时跟踪每轮对话的 token 使用情况
- 计算当前上下文使用率（usage_ratio）
- 在接近限制时输出预警日志
- 支持多种 LLM 提供商（OpenAI、DeepSeek、Qwen、Ollama）

#### 核心组件

**1. 模型元数据系统** (`src/lc/model_metadata.py`)
```python
# 获取模型元数据
metadata = get_model_metadata("openai", "gpt-4")
# metadata.context_window = 8192
# metadata.max_input_tokens = 6144
# metadata.max_output_tokens = 2048

# 支持的模型
- OpenAI: gpt-4 (8K), gpt-4-turbo (128K), gpt-4o (128K), gpt-4o-mini (128K)
- DeepSeek: deepseek-chat (32K), deepseek-coder (32K)
- Qwen: qwen-turbo (8K), qwen-plus (32K), qwen-max (8K)
- Ollama: llama2 (4K), mistral (8K), codellama (16K)

# 动态注册新模型
register_model_metadata(
    provider="custom",
    model="custom-model",
    context_window=16384
)

# 探针调用（运行时检测实际限额）
result = await probe_model_context_limit(llm, "openai", "gpt-4")
```

**2. Token 计数工具** (`src/lc/token_counter.py`)
```python
# 创建计数器
counter = TokenCounter(provider="openai", model="gpt-4")

# 计算消息列表的 token 数
messages = [
    {"role": "user", "content": "Hello!"},
    {"role": "assistant", "content": "Hi there!"}
]
token_count = counter.count_messages(messages)

# 计算文本 token 数
text_tokens = counter.count_text("This is a test message.")

# 计算使用率
usage_ratio = counter.calculate_usage_ratio(used_tokens=4096)
# usage_ratio = 0.5 (对于 gpt-4 的 8K 上下文)

# 检查是否接近限制
is_approaching = counter.is_approaching_limit(
    used_tokens=7000,
    threshold=0.8  # 默认 80%
)

# 获取剩余 token 数
remaining = counter.get_remaining_tokens(used_tokens=4096)
# remaining = 4096
```

**3. SessionContext 扩展** (`src/domain/services/context_manager.py`)
```python
# SessionContext 新增字段
@dataclass
class SessionContext:
    # Token 使用跟踪
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    usage_ratio: float = 0.0

    # 模型信息
    llm_provider: str | None = None
    llm_model: str | None = None
    context_limit: int = 0

# 使用示例
session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)

# 设置模型信息
session_ctx.set_model_info(
    provider="openai",
    model="gpt-4",
    context_limit=8192
)

# 更新 token 使用（每轮对话后调用）
session_ctx.update_token_usage(
    prompt_tokens=100,
    completion_tokens=50
)

# 获取使用率
ratio = session_ctx.get_usage_ratio()  # 0.018 (150/8192)

# 检查是否接近限制
if session_ctx.is_approaching_limit(threshold=0.8):
    print("⚠️ 上下文即将达到限制！")

# 获取剩余 token 数
remaining = session_ctx.get_remaining_tokens()  # 8042

# 获取完整摘要
summary = session_ctx.get_token_usage_summary()
# {
#     "total_prompt_tokens": 100,
#     "total_completion_tokens": 50,
#     "total_tokens": 150,
#     "usage_ratio": 0.018,
#     "context_limit": 8192,
#     "remaining_tokens": 8042,
#     "llm_provider": "openai",
#     "llm_model": "gpt-4"
# }
```

**4. ConversationAgent 集成** (`src/domain/agents/conversation_agent.py`)
```python
# 位置: conversation_agent.py:865-867, 964-972, 1249-1294

# 初始化时自动设置模型信息
async def run_async(self, user_input: str) -> ReActResult:
    # Step 1: 初始化模型信息（如果尚未设置）
    if self.session_context.context_limit == 0:
        self._initialize_model_info()

    # ReAct 循环中记录每轮 token 使用
    for i in range(self.max_iterations):
        # ... 执行 LLM 调用 ...

        # Step 1: 更新 SessionContext 的 token 使用情况
        if prompt_tokens > 0 or completion_tokens > 0:
            self.session_context.update_token_usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens
            )

            # Step 1: 检查是否接近上下文限制并输出预警
            if self.session_context.is_approaching_limit():
                self._log_context_warning()

# 辅助方法
def _initialize_model_info(self) -> None:
    """从配置获取模型信息并设置到 SessionContext"""
    from src.config import settings
    from src.lc.model_metadata import get_model_metadata

    provider = "openai"
    model = settings.openai_model
    metadata = get_model_metadata(provider, model)

    self.session_context.set_model_info(
        provider=provider,
        model=model,
        context_limit=metadata.context_window
    )

def _log_context_warning(self) -> None:
    """记录上下文限制预警"""
    summary = self.session_context.get_token_usage_summary()

    logger.warning(
        f"⚠️ Context limit approaching! "
        f"Usage: {summary['total_tokens']}/{summary['context_limit']} tokens "
        f"({summary['usage_ratio']:.1%}), "
        f"Remaining: {summary['remaining_tokens']} tokens"
    )
```

#### 工作流程

```
用户输入
    │
    ▼
ConversationAgent.run_async()
    │
    ├─ (1) 初始化模型信息（首次）
    │      └─ 从配置读取 provider/model
    │      └─ 获取模型元数据（context_limit）
    │      └─ 设置到 SessionContext
    │
    ├─ (2) ReAct 循环
    │      │
    │      ├─ LLM.think() → 获取 thought
    │      ├─ LLM.decide_action() → 获取 action
    │      │
    │      ├─ (3) 记录 token 使用
    │      │      └─ 从 LLM 获取 prompt_tokens/completion_tokens
    │      │      └─ SessionContext.update_token_usage()
    │      │      └─ 自动计算 usage_ratio
    │      │
    │      └─ (4) 检查上下文限制
    │             └─ SessionContext.is_approaching_limit(threshold=0.8)
    │             └─ 如果接近限制 → _log_context_warning()
    │             └─ 输出预警日志到控制台
    │
    └─ (5) 返回结果
           └─ 包含完整的 token 使用统计
```

#### 预警机制

**触发条件：**
- 默认阈值：80% (可配置)
- 计算公式：`usage_ratio = total_tokens / context_limit`
- 当 `usage_ratio >= 0.8` 时触发预警

**预警日志示例：**
```
WARNING - ⚠️ Context limit approaching!
Usage: 6800/8192 tokens (83.0%), Remaining: 1392 tokens
```

**Fallback 方案：**
1. **未知模型**：使用默认值（4K 上下文窗口）
2. **Token 计数失败**：使用估算方法（英文 4 字符/token，中文 1.5 字符/token）
3. **LLM 不支持 token 统计**：跳过记录，不影响主流程
4. **上下文超限**：继续执行，但会持续输出预警日志

#### 依赖关系

```
ConversationAgent
    │
    ├─ depends on → SessionContext (存储 token 使用数据)
    │                   │
    │                   └─ 字段: total_tokens, usage_ratio, context_limit
    │
    ├─ depends on → ModelMetadata (获取模型上下文限制)
    │                   │
    │                   └─ 函数: get_model_metadata(), register_model_metadata()
    │
    └─ depends on → TokenCounter (计算 token 数，可选)
                        │
                        └─ 函数: count_messages(), count_text()
```

#### 测试覆盖

```bash
# 模型元数据测试
pytest tests/unit/lc/test_model_metadata.py -v
# 14 tests passed ✅

# Token 计数器测试
pytest tests/unit/lc/test_token_counter.py -v
# 23 tests passed ✅

# SessionContext usage_ratio 测试
pytest tests/unit/domain/services/test_context_manager_usage_ratio.py -v
# 16 tests passed ✅

# 总计：53 个测试全部通过 ✅
```

#### 配置示例

```python
# 在 ConversationAgent 初始化时
conversation_agent = ConversationAgent(
    session_context=session_ctx,
    llm=llm,
    event_bus=event_bus,
    max_iterations=10,
    # 上下文容量感知会自动启用
)

# 运行时可以查看 token 使用情况
result = await conversation_agent.run_async("分析销售数据")

# 获取 token 使用摘要
summary = conversation_agent.session_context.get_token_usage_summary()
print(f"Total tokens used: {summary['total_tokens']}")
print(f"Usage ratio: {summary['usage_ratio']:.1%}")
print(f"Remaining tokens: {summary['remaining_tokens']}")
```

#### 注意事项

1. **精确计数 vs 估算**：
   - OpenAI 模型使用 tiktoken 进行精确计数
   - 其他模型使用启发式估算（可能有 ±20% 误差）

2. **性能影响**：
   - Token 计数开销很小（< 1ms）
   - 不会影响 ReAct 循环性能

3. **多会话隔离**：
   - 每个 SessionContext 独立跟踪 token 使用
   - 不同会话之间互不影响

4. **持久化**：
   - 当前 token 使用数据仅存储在内存中
   - 会话结束后数据会丢失
   - 如需持久化，可扩展 SessionContext 的存储层

---

### 2.4 短期记忆缓冲与饱和事件 (Step 2)

#### 功能概述

ConversationAgent 现在具备短期记忆管理和饱和检测能力：
- 使用 ShortTermBuffer 存储对话轮次信息
- 当 usage_ratio ≥ 0.92 时自动触发 ShortTermSaturatedEvent
- 通过 ConversationFlowEmitter 发送系统通知
- 事件只触发一次，防止重复通知
- 支持自定义饱和阈值

#### 核心组件

**1. ShortTermBuffer 数据结构** (`src/domain/services/short_term_buffer.py`)

```python
@dataclass
class ShortTermBuffer:
    """短期记忆缓冲区

    属性：
    - turn_id: 轮次唯一标识
    - role: 角色（user/assistant/system）
    - content: 内容文本
    - tool_refs: 工具调用引用列表
    - token_usage: token 使用统计
    - timestamp: 创建时间戳
    """
    turn_id: str
    role: TurnRole
    content: str
    tool_refs: list[str] = field(default_factory=list)
    token_usage: dict[str, int] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

# 使用示例
buffer = ShortTermBuffer(
    turn_id="turn_001",
    role=TurnRole.USER,
    content="请分析销售数据",
    tool_refs=["tool_call_123"],
    token_usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
)

# 获取总 token 数
total = buffer.get_total_tokens()  # 150

# 序列化
data = buffer.to_dict()

# 反序列化
buffer = ShortTermBuffer.from_dict(data)
```

**2. ShortTermSaturatedEvent 事件** (`src/domain/services/context_manager.py`)

```python
@dataclass
class ShortTermSaturatedEvent:
    """短期记忆饱和事件

    当 SessionContext 的 usage_ratio 达到阈值（默认 0.92）时触发。

    属性：
    - source: 事件源（"session_context"）
    - session_id: 会话ID
    - usage_ratio: 当前使用率
    - total_tokens: 总 token 数
    - context_limit: 上下文限制
    - buffer_size: 短期缓冲区大小
    - timestamp: 事件时间戳
    - id: 事件唯一标识
    """
    source: str
    session_id: str
    usage_ratio: float
    total_tokens: int
    context_limit: int
    buffer_size: int
    timestamp: datetime = field(default_factory=datetime.now)
    id: str = field(default_factory=lambda: f"saturated_{datetime.now().timestamp()}")

    @property
    def event_type(self) -> str:
        return "short_term_saturated"
```

**3. SessionContext 扩展** (`src/domain/services/context_manager.py`)

```python
@dataclass
class SessionContext:
    # Step 2: 短期记忆缓冲区
    short_term_buffer: list[ShortTermBuffer] = field(default_factory=list)
    is_saturated: bool = False
    saturation_threshold: float = 0.92
    _event_bus: EventBus | None = field(default=None, repr=False)

# 使用示例
session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
event_bus = EventBus()

# 设置事件总线
session_ctx.set_event_bus(event_bus)

# 设置模型信息
session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

# 添加对话轮次
buffer = ShortTermBuffer(
    turn_id="turn_001",
    role=TurnRole.USER,
    content="Hello",
    tool_refs=[],
    token_usage={"total_tokens": 100}
)

# 更新 token 使用并添加轮次
session_ctx.update_token_usage(prompt_tokens=100, completion_tokens=0)
session_ctx.add_turn(buffer)

# 检查是否饱和
if session_ctx.is_saturated:
    print("⚠️ 短期记忆已饱和")

# 重置饱和状态（压缩完成后）
session_ctx.reset_saturation()
```

**4. ConversationFlowEmitter 集成** (`src/domain/services/conversation_flow_emitter.py`)

```python
# 新增方法：emit_system_notice
async def emit_system_notice(self, content: str, **metadata: Any) -> None:
    """发送系统通知

    用于发送系统级别的通知消息，例如上下文压缩提示。
    """
    step = ConversationStep(
        kind=StepKind.ACTION,
        content=content,
        metadata={"notice_type": "system", **metadata}
    )
    await self.emit_step(step)

# 使用示例：订阅饱和事件并发送通知
async def handle_saturation(event: ShortTermSaturatedEvent):
    await emitter.emit_system_notice(
        f"⚠️ 上下文压缩即将执行 - 当前使用率: {event.usage_ratio:.1%}, "
        f"已使用 {event.total_tokens}/{event.context_limit} tokens"
    )

event_bus.subscribe(ShortTermSaturatedEvent, handle_saturation)
```

#### 工作流程与状态机

```
用户输入
    │
    ▼
ConversationAgent.run_async()
    │
    ├─ (1) 初始化模型信息（Step 1）
    │      └─ 设置 context_limit
    │
    ├─ (2) ReAct 循环
    │      │
    │      ├─ LLM 调用
    │      │
    │      ├─ (3) 记录 token 使用（Step 1）
    │      │      └─ SessionContext.update_token_usage()
    │      │      └─ 计算 usage_ratio
    │      │
    │      ├─ (4) 添加对话轮次（Step 2）
    │      │      └─ 创建 ShortTermBuffer
    │      │      └─ SessionContext.add_turn(buffer)
    │      │      └─ 检测饱和：usage_ratio >= 0.92?
    │      │             │
    │      │             ├─ YES → 触发饱和事件
    │      │             │         │
    │      │             │         ├─ 设置 is_saturated = True
    │      │             │         ├─ 发布 ShortTermSaturatedEvent
    │      │             │         └─ 输出日志：🔴 Short-term memory saturated!
    │      │             │
    │      │             └─ NO → 继续执行
    │      │
    │      └─ (5) 事件处理器（异步）
    │             └─ 订阅者接收 ShortTermSaturatedEvent
    │             └─ ConversationFlowEmitter.emit_system_notice()
    │             └─ 流式输出："⚠️ 上下文压缩即将执行"
    │
    └─ (6) 返回结果
```

#### 状态机转移

```
[NORMAL] ──usage_ratio < 0.92──▶ [NORMAL]
    │
    │ usage_ratio >= 0.92
    │ (首次)
    ▼
[SATURATED] ──add_turn()──▶ [SATURATED]
    │                         (不再触发事件)
    │
    │ reset_saturation()
    ▼
[NORMAL]
```

**状态说明：**
- **NORMAL**：正常状态，is_saturated = False
- **SATURATED**：饱和状态，is_saturated = True
- 饱和状态下继续添加轮次不会重复触发事件
- 调用 `reset_saturation()` 可重置为正常状态

#### 事件字段完整说明

**ShortTermSaturatedEvent 字段：**

| 字段 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `source` | str | 事件源 | "session_context" |
| `session_id` | str | 会话ID | "session_001" |
| `usage_ratio` | float | 当前使用率 | 0.92 |
| `total_tokens` | int | 总 token 数 | 7537 |
| `context_limit` | int | 上下文限制 | 8192 |
| `buffer_size` | int | 缓冲区大小 | 10 |
| `timestamp` | datetime | 事件时间戳 | 2025-01-22T10:30:00 |
| `id` | str | 事件唯一标识 | "saturated_1737532200.123" |
| `event_type` | str | 事件类型（属性） | "short_term_saturated" |

#### 与 SessionFlowGenerator 的接口

**事件订阅模式：**

```python
# 在应用层或接口层订阅事件
from src.domain.services.context_manager import ShortTermSaturatedEvent
from src.domain.services.conversation_flow_emitter import ConversationFlowEmitter

# 创建事件处理器
async def handle_saturation_event(event: ShortTermSaturatedEvent):
    """处理饱和事件

    当短期记忆饱和时：
    1. 通过流式输出通知用户
    2. 触发上下文压缩流程（未来实现）
    3. 记录日志和指标
    """
    # 获取对应会话的 emitter
    emitter = get_emitter_for_session(event.session_id)

    # 发送系统通知
    await emitter.emit_system_notice(
        f"⚠️ 上下文压缩即将执行\n"
        f"当前使用率: {event.usage_ratio:.1%}\n"
        f"已使用: {event.total_tokens}/{event.context_limit} tokens\n"
        f"缓冲区大小: {event.buffer_size} 轮次"
    )

    # 记录指标
    logger.warning(
        f"Session {event.session_id} saturated: "
        f"ratio={event.usage_ratio:.2%}, "
        f"tokens={event.total_tokens}/{event.context_limit}"
    )

    # TODO: 触发上下文压缩（Step 3）
    # await trigger_context_compression(event.session_id)

# 注册事件处理器
event_bus.subscribe(ShortTermSaturatedEvent, handle_saturation_event)
```

**流式输出示例：**

```
用户: 请分析这份销售数据...
助手: 好的，我来分析...
[多轮对话...]
系统: ⚠️ 上下文压缩即将执行
      当前使用率: 92.0%
      已使用: 7537/8192 tokens
      缓冲区大小: 10 轮次
助手: [继续回复...]
```

#### 测试覆盖

```bash
# ShortTermBuffer 测试
pytest tests/unit/domain/services/test_short_term_buffer.py -v
# 12 tests passed ✅

# 饱和检测测试
pytest tests/unit/domain/services/test_short_term_saturation.py -v
# 12 tests passed ✅

# 集成测试（饱和事件 + 流式输出）
pytest tests/integration/test_saturation_flow_integration.py -v
# 5 tests passed ✅

# Step 1 + Step 2 总计：82 个测试全部通过 ✅
```

#### 配置示例

```python
# 完整的饱和检测配置
from src.domain.services.context_manager import GlobalContext, SessionContext
from src.domain.services.event_bus import EventBus
from src.domain.services.conversation_flow_emitter import ConversationFlowEmitter

# 1. 创建上下文和事件总线
global_ctx = GlobalContext(user_id="user_123")
session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
event_bus = EventBus()

# 2. 设置事件总线和模型信息
session_ctx.set_event_bus(event_bus)
session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

# 3. 自定义饱和阈值（可选，默认 0.92）
session_ctx.saturation_threshold = 0.85  # 85% 时触发

# 4. 创建流式发射器
emitter = ConversationFlowEmitter(session_id="session_001")

# 5. 订阅饱和事件
async def handle_saturation(event):
    await emitter.emit_system_notice(
        f"⚠️ 上下文压缩即将执行 - 使用率: {event.usage_ratio:.1%}"
    )

event_bus.subscribe(ShortTermSaturatedEvent, handle_saturation)

# 6. 在对话循环中使用
for turn in conversation_turns:
    # 更新 token 使用
    session_ctx.update_token_usage(
        prompt_tokens=turn.prompt_tokens,
        completion_tokens=turn.completion_tokens
    )

    # 添加轮次到缓冲区
    buffer = ShortTermBuffer(
        turn_id=turn.id,
        role=turn.role,
        content=turn.content,
        tool_refs=turn.tool_refs,
        token_usage=turn.token_usage
    )
    session_ctx.add_turn(buffer)

    # 饱和事件会自动触发（如果达到阈值）
```

#### 注意事项

1. **事件只触发一次**：
   - 使用 `is_saturated` 标志防止重复触发
   - 压缩完成后需调用 `reset_saturation()` 重置状态

2. **异步事件处理**：
   - 事件发布是异步的，不会阻塞主流程
   - 事件处理器应该快速执行，避免影响性能

3. **缓冲区管理**：
   - ShortTermBuffer 仅存储在内存中
   - 会话结束后自动清理
   - 如需持久化，可扩展存储层

4. **阈值配置**：
   - 默认阈值 0.92（92%）
   - 可通过 `saturation_threshold` 属性自定义
   - 建议范围：0.8 - 0.95

5. **多会话隔离**：
   - 每个 SessionContext 独立检测饱和
   - 不同会话的饱和事件互不影响

6. **与 Step 3 的衔接**：
   - 饱和事件触发后，Step 3 将实现上下文压缩
   - 压缩完成后调用 `reset_saturation()` 允许再次触发

---

### 2.5 中期记忆蒸馏流水线 (Step 3)

#### 功能概述

实现完整的中期记忆蒸馏流水线，将短期记忆压缩为结构化摘要：
- 使用八段结构摘要（StructuredDialogueSummary）
- 监听饱和事件并触发压缩流水线
- 冻结会话、运行压缩器、生成摘要
- 用摘要替换旧 buffer，保留最近两轮 delta
- 压缩失败时自动回滚到原状态

#### 核心组件

**1. StructuredDialogueSummary（八段结构摘要）** (`src/domain/services/structured_dialogue_summary.py`)

```python
@dataclass
class StructuredDialogueSummary:
    """结构化对话摘要（八段结构）

    八段结构：
    1. core_goal: 核心目标 - 对话的主要目标和意图
    2. key_decisions: 关键决策 - 已做出的重要决策和选择
    3. important_facts: 重要事实 - 需要记住的关键事实和数据
    4. pending_tasks: 待办事项 - 未完成的任务和行动项
    5. user_preferences: 用户偏好 - 用户的偏好、习惯和要求
    6. context_clues: 上下文线索 - 有助于理解对话的背景信息
    7. unresolved_issues: 未解问题 - 尚未解决的问题和疑问
    8. next_steps: 下一步计划 - 接下来要做的事情和行动
    """

    session_id: str
    summary_id: str
    created_at: datetime

    # 八段结构
    core_goal: str = ""
    key_decisions: list[str] = field(default_factory=list)
    important_facts: list[str] = field(default_factory=list)
    pending_tasks: list[str] = field(default_factory=list)
    user_preferences: list[str] = field(default_factory=list)
    context_clues: list[str] = field(default_factory=list)
    unresolved_issues: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)

    # 压缩元数据
    compressed_from_turns: int = 0
    original_token_count: int = 0
    summary_token_count: int = 0

# 使用示例
summary = StructuredDialogueSummary(
    session_id="session_001",
    core_goal="分析销售数据并生成报告",
    key_decisions=["使用 Q4 数据", "按地区分组"],
    important_facts=["总销售额增长 15%", "华东地区表现最佳"],
    pending_tasks=["生成详细报告", "发送给管理层"],
    user_preferences=["喜欢图表展示", "需要中文报告"],
    context_clues=["用户是销售总监", "关注季度对比"],
    unresolved_issues=["部分数据缺失", "需要确认统计口径"],
    next_steps=["补充缺失数据", "生成最终报告"],
    compressed_from_turns=10,
    original_token_count=5000,
    summary_token_count=500,
)

# 获取压缩率
ratio = summary.get_compression_ratio()  # 0.1 (500/5000)

# 转换为文本格式（用于 LLM 上下文）
text = summary.to_text()
```

**2. SessionContext 会话管理扩展** (`src/domain/services/context_manager.py`)

```python
@dataclass
class SessionContext:
    # Step 3: 会话冻结与备份
    _is_frozen: bool = False
    _backup: dict[str, Any] | None = None

# 冻结与解冻
session_ctx.freeze()           # 冻结会话，防止并发修改
session_ctx.unfreeze()         # 解冻会话
is_frozen = session_ctx.is_frozen()  # 检查冻结状态

# 备份与恢复
backup = session_ctx.create_backup()           # 创建备份
session_ctx.restore_from_backup(backup)        # 恢复备份

# 压缩 buffer
session_ctx.compress_buffer_with_summary(
    summary=summary,
    keep_recent_turns=2  # 保留最近 2 轮
)
```

**3. 压缩流水线完整流程**

```python
async def handle_saturation_event(event: ShortTermSaturatedEvent):
    """处理饱和事件并执行压缩流水线"""

    # 1. 冻结会话
    session_ctx.freeze()

    try:
        # 2. 创建备份
        backup = session_ctx.create_backup()

        try:
            # 3. 生成摘要（使用 LLM 或压缩器）
            summary = await generate_summary(
                session_id=event.session_id,
                buffer=session_ctx.short_term_buffer,
                total_tokens=event.total_tokens
            )

            # 4. 压缩 buffer（保留最近 2 轮）
            session_ctx.compress_buffer_with_summary(
                summary=summary,
                keep_recent_turns=2
            )

            # 5. 重置饱和状态
            session_ctx.reset_saturation()

        except Exception as e:
            # 压缩失败，回滚到备份
            session_ctx.restore_from_backup(backup)
            raise e

    finally:
        # 6. 解冻会话
        session_ctx.unfreeze()
```

#### 压缩流水线流程图

```
ShortTermSaturatedEvent (usage_ratio >= 0.92)
    │
    ▼
handle_saturation_event()
    │
    ├─ (1) 冻结会话
    │      └─ session_ctx.freeze()
    │      └─ 阻止并发修改
    │
    ├─ (2) 创建备份
    │      └─ backup = session_ctx.create_backup()
    │      └─ 保存当前状态（用于回滚）
    │
    ├─ (3) 生成摘要
    │      └─ 调用 LLM 或压缩器
    │      └─ 分析对话历史
    │      └─ 提取八段结构信息
    │      └─ 生成 StructuredDialogueSummary
    │
    ├─ (4) 压缩 buffer
    │      └─ 保留最近 2 轮对话
    │      └─ 删除旧的轮次
    │      └─ 存储摘要到 conversation_summary
    │
    ├─ (5) 重置饱和状态
    │      └─ session_ctx.reset_saturation()
    │      └─ is_saturated = False
    │
    ├─ (6) 解冻会话
    │      └─ session_ctx.unfreeze()
    │      └─ 允许继续添加轮次
    │
    └─ 异常处理
           └─ 捕获任何错误
           └─ 回滚到备份状态
           └─ session_ctx.restore_from_backup(backup)
           └─ 解冻会话
```

#### 状态机转移

```
[NORMAL] ──usage_ratio >= 0.92──▶ [SATURATED]
    │                                    │
    │                                    │ 触发压缩流水线
    │                                    ▼
    │                              [FROZEN]
    │                                    │
    │                                    ├─ 创建备份
    │                                    ├─ 生成摘要
    │                                    ├─ 压缩 buffer
    │                                    ├─ 重置饱和
    │                                    │
    │                                    ├─ 成功 ──▶ [UNFROZEN] ──▶ [NORMAL]
    │                                    │
    │                                    └─ 失败 ──▶ [ROLLBACK] ──▶ [UNFROZEN] ──▶ [SATURATED]
    │
    └──────────────────────────────────────────────────────────────────────────┘
```

**状态说明：**
- **NORMAL**：正常状态，可以添加轮次
- **SATURATED**：饱和状态，触发压缩流水线
- **FROZEN**：冻结状态，不允许修改
- **ROLLBACK**：回滚状态，恢复备份
- **UNFROZEN**：解冻状态，恢复正常

#### 数据 Schema

**StructuredDialogueSummary Schema:**

```json
{
  "session_id": "session_001",
  "summary_id": "summary_abc123",
  "created_at": "2025-01-22T10:30:00",

  "core_goal": "分析销售数据并生成报告",
  "key_decisions": [
    "使用 Q4 数据",
    "按地区分组"
  ],
  "important_facts": [
    "总销售额增长 15%",
    "华东地区表现最佳"
  ],
  "pending_tasks": [
    "生成详细报告",
    "发送给管理层"
  ],
  "user_preferences": [
    "喜欢图表展示",
    "需要中文报告"
  ],
  "context_clues": [
    "用户是销售总监",
    "关注季度对比"
  ],
  "unresolved_issues": [
    "部分数据缺失",
    "需要确认统计口径"
  ],
  "next_steps": [
    "补充缺失数据",
    "生成最终报告"
  ],

  "compressed_from_turns": 10,
  "original_token_count": 5000,
  "summary_token_count": 500
}
```

**SessionContext Backup Schema:**

```json
{
  "total_prompt_tokens": 3000,
  "total_completion_tokens": 1500,
  "total_tokens": 4500,
  "usage_ratio": 0.55,
  "short_term_buffer": [
    {
      "turn_id": "turn_001",
      "role": "user",
      "content": "请分析销售数据",
      "tool_refs": [],
      "token_usage": {"total_tokens": 100},
      "timestamp": "2025-01-22T10:00:00"
    }
  ],
  "conversation_summary": "【核心目标】分析销售数据...",
  "is_saturated": false
}
```

#### 测试覆盖

```bash
# StructuredDialogueSummary 测试
pytest tests/unit/domain/services/test_structured_dialogue_summary.py -v
# 14 tests passed ✅

# 压缩流水线集成测试
pytest tests/integration/test_memory_distillation_pipeline.py -v
# 8 tests passed ✅

# Step 1 + Step 2 + Step 3 总计：104 个测试全部通过 ✅
```

#### 配置示例

```python
# 完整的压缩流水线配置
from src.domain.services.context_manager import (
    GlobalContext,
    SessionContext,
    ShortTermSaturatedEvent,
)
from src.domain.services.event_bus import EventBus
from src.domain.services.structured_dialogue_summary import StructuredDialogueSummary

# 1. 创建上下文和事件总线
global_ctx = GlobalContext(user_id="user_123")
session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)
event_bus = EventBus()

# 2. 设置事件总线和模型信息
session_ctx.set_event_bus(event_bus)
session_ctx.set_model_info(provider="openai", model="gpt-4", context_limit=8192)

# 3. 订阅饱和事件并实现压缩流水线
async def handle_saturation_with_compression(event: ShortTermSaturatedEvent):
    """完整的压缩流水线"""

    # 冻结会话
    session_ctx.freeze()

    try:
        # 创建备份
        backup = session_ctx.create_backup()

        try:
            # 生成摘要（这里简化为手动创建）
            summary = StructuredDialogueSummary(
                session_id=event.session_id,
                core_goal="从对话中提取的核心目标",
                key_decisions=["决策1", "决策2"],
                important_facts=["事实1", "事实2"],
                compressed_from_turns=event.buffer_size,
                original_token_count=event.total_tokens,
                summary_token_count=500,
            )

            # 压缩 buffer
            session_ctx.compress_buffer_with_summary(summary, keep_recent_turns=2)

            # 重置饱和状态
            session_ctx.reset_saturation()

        except Exception as e:
            # 回滚
            session_ctx.restore_from_backup(backup)
            raise e

    finally:
        # 解冻
        session_ctx.unfreeze()

event_bus.subscribe(ShortTermSaturatedEvent, handle_saturation_with_compression)

# 4. 正常使用（压缩会自动触发）
for turn in conversation_turns:
    session_ctx.update_token_usage(
        prompt_tokens=turn.prompt_tokens,
        completion_tokens=turn.completion_tokens
    )

    buffer = ShortTermBuffer(
        turn_id=turn.id,
        role=turn.role,
        content=turn.content,
        tool_refs=turn.tool_refs,
        token_usage=turn.token_usage
    )

    session_ctx.add_turn(buffer)

    # 当 usage_ratio >= 0.92 时，压缩流水线会自动触发
```

#### 注意事项

1. **会话冻结**：
   - 冻结期间不允许添加新轮次
   - 防止并发修改导致数据不一致
   - 压缩完成后必须解冻

2. **备份与回滚**：
   - 压缩前必须创建备份
   - 任何异常都会触发回滚
   - 回滚后会话状态完全恢复

3. **保留最近轮次**：
   - 默认保留最近 2 轮对话
   - 保留的轮次称为 "delta"
   - 可以根据需要调整保留数量

4. **摘要生成**：
   - 当前示例中手动创建摘要
   - 实际应用中应使用 LLM 生成
   - 可以集成 PowerCompressor 或其他压缩器

5. **压缩率**：
   - 典型压缩率：10-20%（5000 tokens → 500-1000 tokens）
   - 八段结构确保关键信息不丢失
   - 压缩后仍可继续对话

6. **与 CoordinatorAgent 的集成**：
   - CoordinatorAgent 应订阅 ShortTermSaturatedEvent
   - 实现完整的压缩流水线逻辑
   - 可以调用 PowerCompressor 生成摘要
   - 摘要可以存储到知识库或数据库

---

### 2.6 长期知识库治理 (Step 4)

#### 功能概述

实现完整的知识库治理系统，支持笔记的创建、审批、归档和巡检：
- 定义五种笔记类型（progress/conclusion/blocker/next_action/reference）
- 实现四状态生命周期（draft → pending_user → approved → archived）
- 记录用户确认流程（审批人、审批时间）
- 协调者定期巡检，自动转换已解决的 blocker 和归档过期计划
- 完整的审计日志记录所有操作

#### 核心组件

**1. KnowledgeNote（知识笔记）** (`src/domain/services/knowledge_note.py`)

```python
class NoteType(str, Enum):
    """笔记类型枚举"""
    PROGRESS = "progress"        # 进展记录
    CONCLUSION = "conclusion"    # 结论总结
    BLOCKER = "blocker"         # 阻塞问题
    NEXT_ACTION = "next_action" # 下一步计划
    REFERENCE = "reference"     # 参考资料

class NoteStatus(str, Enum):
    """笔记状态枚举"""
    DRAFT = "draft"                 # 草稿
    PENDING_USER = "pending_user"   # 待用户确认
    APPROVED = "approved"           # 已批准
    ARCHIVED = "archived"           # 已归档

@dataclass
class KnowledgeNote:
    """知识笔记

    属性：
    - note_id: 笔记唯一标识
    - type: 笔记类型
    - status: 笔记状态
    - content: 笔记内容
    - owner: 创建者
    - version: 版本号
    - tags: 标签列表
    - approved_by: 批准人
    - approved_at: 批准时间
    """
    note_id: str
    type: NoteType
    status: NoteStatus
    content: str
    owner: str
    version: int = 1
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    approved_at: datetime | None = None
    approved_by: str | None = None

# 使用示例
note = KnowledgeNote.create(
    type=NoteType.BLOCKER,
    content="数据库连接失败，需要配置正确的连接字符串",
    owner="user_123",
    tags=["database", "urgent"]
)
```

**2. NoteLifecycleManager（生命周期管理器）** (`src/domain/services/knowledge_note_lifecycle.py`)

```python
class NoteLifecycleManager:
    """笔记生命周期管理器

    职责：
    - 管理笔记状态转换
    - 验证状态转换合法性
    - 记录用户确认信息
    - 确保已批准笔记的不可变性
    """

    # 合法的状态转换
    VALID_TRANSITIONS = {
        NoteStatus.DRAFT: [NoteStatus.PENDING_USER],
        NoteStatus.PENDING_USER: [NoteStatus.APPROVED, NoteStatus.DRAFT],
        NoteStatus.APPROVED: [NoteStatus.ARCHIVED],
        NoteStatus.ARCHIVED: [],
    }

    def submit_for_approval(self, note: KnowledgeNote) -> None:
        """提交审批"""
        self._validate_transition(note.status, NoteStatus.PENDING_USER)
        note.status = NoteStatus.PENDING_USER
        note.updated_at = datetime.now()

    def approve_note(self, note: KnowledgeNote, approved_by: str) -> None:
        """批准笔记"""
        self._validate_transition(note.status, NoteStatus.APPROVED)
        note.status = NoteStatus.APPROVED
        note.approved_by = approved_by
        note.approved_at = datetime.now()
        note.updated_at = datetime.now()

    def archive_note(self, note: KnowledgeNote) -> None:
        """归档笔记"""
        self._validate_transition(note.status, NoteStatus.ARCHIVED)
        note.status = NoteStatus.ARCHIVED
        note.updated_at = datetime.now()
```

**3. AuditLogManager（审计日志管理器）** (`src/domain/services/knowledge_audit_log.py`)

```python
class AuditAction(str, Enum):
    """审计操作类型"""
    CREATED = "created"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    UPDATED = "updated"

@dataclass
class AuditLog:
    """审计日志

    属性：
    - log_id: 日志唯一标识
    - note_id: 笔记ID
    - action: 操作类型
    - actor: 操作者
    - timestamp: 操作时间
    - metadata: 额外元数据
    """
    log_id: str
    note_id: str
    action: AuditAction
    actor: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

class AuditLogManager:
    """审计日志管理器

    职责：
    - 记录所有笔记操作
    - 提供多维度查询接口
    - 支持审批历史追溯
    """

    def log_note_approval(self, note: KnowledgeNote, approved_by: str) -> AuditLog:
        """记录笔记批准"""
        log = AuditLog.create(
            note_id=note.note_id,
            action=AuditAction.APPROVED,
            actor=approved_by,
        )
        self._logs.append(log)
        return log

    def get_approval_history(self, note_id: str) -> list[dict[str, Any]]:
        """获取批准历史"""
        approval_logs = [
            log for log in self._logs
            if log.note_id == note_id and log.action == AuditAction.APPROVED
        ]
        return [
            {
                "actor": log.actor,
                "action": log.action.value,
                "timestamp": log.timestamp
            }
            for log in approval_logs
        ]
```

**4. CoordinatorInspector（协调者巡检器）** (`src/domain/services/knowledge_coordinator_inspector.py`)

```python
class InspectionAction(str, Enum):
    """巡检操作类型"""
    KEEP = "keep"                           # 保持不变
    CONVERT_TO_CONCLUSION = "convert_to_conclusion"  # 转为结论
    ARCHIVE = "archive"                     # 归档
    UPDATE = "update"                       # 更新

class CoordinatorInspector:
    """协调者巡检器

    职责：
    - 巡检 blocker 笔记，识别已解决的问题
    - 巡检 next_action 笔记，识别过期计划
    - 执行巡检操作（转换、归档等）
    - 记录巡检日志
    """

    # 解决关键词列表
    RESOLUTION_KEYWORDS = [
        "已解决", "已修复", "解决方案", "完成",
        "solved", "resolved", "fixed", "completed"
    ]

    def inspect_blocker(self, note: KnowledgeNote) -> InspectionResult:
        """巡检 blocker 笔记"""
        if self.is_blocker_resolved(note):
            return InspectionResult(
                note_id=note.note_id,
                action=InspectionAction.CONVERT_TO_CONCLUSION,
                reason="Blocker 已解决，建议转为 conclusion"
            )
        return InspectionResult(
            note_id=note.note_id,
            action=InspectionAction.KEEP,
            reason="Blocker 未解决，保持不变"
        )

    def inspect_next_action(self, note: KnowledgeNote) -> InspectionResult:
        """巡检 next_action 笔记"""
        if self.is_plan_expired(note, days=30):
            return InspectionResult(
                note_id=note.note_id,
                action=InspectionAction.ARCHIVE,
                reason="计划已过期（超过 30 天），建议归档"
            )
        return InspectionResult(
            note_id=note.note_id,
            action=InspectionAction.KEEP,
            reason="计划未过期，保持不变"
        )

    def convert_blocker_to_conclusion(self, blocker: KnowledgeNote) -> KnowledgeNote:
        """将 blocker 转为 conclusion"""
        conclusion_content = f"【从 Blocker 转换】{blocker.content}"
        conclusion = KnowledgeNote.create(
            type=NoteType.CONCLUSION,
            content=conclusion_content,
            owner=blocker.owner,
            tags=blocker.tags.copy()
        )
        return conclusion
```

#### 生命周期状态机

```
[DRAFT] ──submit_for_approval()──▶ [PENDING_USER]
                                          │
                                          ├─ approve_note() ──▶ [APPROVED]
                                          │                          │
                                          │                          │ archive_note()
                                          │                          ▼
                                          │                    [ARCHIVED]
                                          │
                                          └─ reject_note() ──▶ [DRAFT]
```

**状态说明：**
- **DRAFT**：草稿状态，可以编辑和删除
- **PENDING_USER**：待用户确认，等待审批
- **APPROVED**：已批准，不可修改（immutable）
- **ARCHIVED**：已归档，不再使用

#### 用户确认流程

```
1. Agent 创建笔记
   └─ note = KnowledgeNote.create(type=NoteType.BLOCKER, ...)
   └─ audit_manager.log_note_creation(note)

2. 提交审批
   └─ lifecycle_manager.submit_for_approval(note)
   └─ audit_manager.log_note_submission(note)
   └─ 通知用户审批

3. 用户审批
   └─ lifecycle_manager.approve_note(note, approved_by="user_123")
   └─ audit_manager.log_note_approval(note, approved_by="user_123")
   └─ 记录 approved_by 和 approved_at

4. 协调者巡检（定期执行）
   └─ inspector.inspect_all_notes(notes)
   └─ 检测已解决的 blocker
   └─ 检测过期的 next_action
   └─ 执行转换或归档操作
   └─ 记录巡检日志
```

#### 测试覆盖

```bash
# KnowledgeNote 测试
pytest tests/unit/domain/services/test_knowledge_note.py -v
# 21 tests passed ✅

# NoteLifecycleManager 测试
pytest tests/unit/domain/services/test_knowledge_note_lifecycle.py -v
# 22 tests passed ✅

# AuditLogManager 测试
pytest tests/unit/domain/services/test_knowledge_audit_log.py -v
# 20 tests passed ✅

# CoordinatorInspector 测试
pytest tests/unit/domain/services/test_knowledge_coordinator_inspector.py -v
# 17 tests passed ✅

# Step 4 总计：80 个测试全部通过 ✅
```

#### 配置示例

```python
# 完整的知识库治理配置
from src.domain.services.knowledge_note import KnowledgeNote, NoteType
from src.domain.services.knowledge_note_lifecycle import NoteLifecycleManager
from src.domain.services.knowledge_audit_log import AuditLogManager
from src.domain.services.knowledge_coordinator_inspector import CoordinatorInspector

# 1. 创建管理器
lifecycle_manager = NoteLifecycleManager()
audit_manager = AuditLogManager()
inspector = CoordinatorInspector(expiration_days=30)

# 2. 创建笔记
blocker = KnowledgeNote.create(
    type=NoteType.BLOCKER,
    content="数据库连接失败",
    owner="agent_001",
    tags=["database", "urgent"]
)
audit_manager.log_note_creation(blocker)

# 3. 提交审批
lifecycle_manager.submit_for_approval(blocker)
audit_manager.log_note_submission(blocker)

# 4. 用户批准
lifecycle_manager.approve_note(blocker, approved_by="user_123")
audit_manager.log_note_approval(blocker, approved_by="user_123")

# 5. 协调者巡检
results = inspector.inspect_all_notes([blocker])
for result in results:
    if result.action == InspectionAction.CONVERT_TO_CONCLUSION:
        conclusion = inspector.convert_blocker_to_conclusion(blocker)
        audit_manager.log_note_creation(conclusion)

# 6. 查询审批历史
history = audit_manager.get_approval_history(blocker.note_id)
print(f"批准人: {history[0]['actor']}")
print(f"批准时间: {history[0]['timestamp']}")
```

---

### 2.7 Schema 强制与依赖敏感规划 (Phase 8.2)

#### 功能概述

ConversationAgent 现已实现强制性 Pydantic schema 验证和依赖敏感的工作流规划：
- **Schema 强制验证**：所有决策 payload 必须通过 Pydantic schema 验证
- **依赖关系识别**：识别数据依赖、顺序依赖、条件依赖
- **资源约束感知**：考虑时间限制、API 调用限制、并发限制
- **循环检测**：使用 Kahn's 算法检测工作流中的循环依赖
- **并行机会分析**：自动识别可并行执行的节点

#### 核心组件

**1. Schema 验证集成** (`src/domain/agents/conversation_agent.py:1094-1210`)

```python
def make_decision(self, context_hint: str) -> Decision:
    """做出决策（增强版：集成 Pydantic schema 验证）

    流程：
    1. 调用 LLM 获取决策
    2. 使用 Pydantic schema 验证 payload
    3. 检测循环依赖（针对工作流规划）
    4. 分析并行机会和资源约束
    5. 记录验证元数据到 session context

    异常：
        ValidationError: 如果决策 payload 不符合 schema
    """
    from pydantic import ValidationError
    from src.domain.agents.conversation_agent_enhanced import validate_and_enhance_decision

    # 获取上下文
    context = self.get_context_for_reasoning()
    context["hint"] = context_hint

    # 添加资源约束（如果存在）
    if hasattr(self.session_context, "resource_constraints"):
        context["resource_constraints"] = self.session_context.resource_constraints

    # 调用 LLM 获取决策
    action = self._call_llm_decide(context)
    action_type = action.get("action_type", "continue")

    # ✨ 使用 Pydantic schema 验证 ✨
    try:
        constraints = (
            self.session_context.resource_constraints
            if hasattr(self.session_context, "resource_constraints")
            else None
        )

        # 综合验证：Schema + 依赖关系 + 资源约束
        validated_payload, metadata = validate_and_enhance_decision(
            action_type, action, constraints
        )

        # 记录验证元数据
        if metadata:
            if not hasattr(self.session_context, "_decision_metadata"):
                self.session_context._decision_metadata = []
            self.session_context._decision_metadata.append({
                "action_type": action_type,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata,
            })

        # 使用验证后的 payload
        validated_dict = validated_payload.model_dump()

    except ValidationError as e:
        logger.error(f"决策 payload 验证失败: {e.errors()}")
        self.session_context.add_decision({
            "type": "validation_failed",
            "action_type": action_type,
            "errors": str(e.errors()),
            "timestamp": datetime.now().isoformat(),
        })
        raise

    # 转换为 Decision
    decision = Decision(
        type=decision_type_mapping.get(action_type, DecisionType.CONTINUE),
        payload=validated_dict,
    )

    return decision
```

**2. 验证与增强函数** (`src/domain/agents/conversation_agent_enhanced.py`)

```python
def validate_and_enhance_decision(
    action_type: str,
    payload: dict[str, Any],
    constraints: dict[str, Any] | None = None
) -> tuple[Any, dict[str, Any]]:
    """综合验证和增强决策

    验证流程：
    1. Pydantic schema 验证
    2. 依赖关系验证（针对工作流）
    3. 并行机会分析
    4. 资源约束检查
    5. 执行时间估算

    Args:
        action_type: 动作类型
        payload: payload 字典
        constraints: 资源约束

    Returns:
        (validated_payload, metadata)
        - validated_payload: 验证后的 Pydantic 对象
        - metadata: 包含依赖分析、资源检查、时间估算的元数据

    Raises:
        ValidationError: Pydantic 验证失败
        ValueError: 循环依赖检测失败
    """
    metadata: dict[str, Any] = {}

    # 1. Schema 验证
    validated = validate_decision_payload(action_type, payload)

    # 2. 工作流规划特殊处理
    if isinstance(validated, CreateWorkflowPlanPayload):
        # 验证依赖关系
        validate_workflow_dependencies(validated)
        metadata["dependencies_valid"] = True

        # 分析并行机会
        parallel_analysis = analyze_parallel_opportunities(
            validated.nodes, validated.edges
        )
        metadata["parallel_analysis"] = parallel_analysis

        # 检查资源约束
        if constraints:
            resource_check = check_resource_constraints(validated, constraints)
            metadata["resource_check"] = resource_check

        # 估算执行时间
        time_estimate = estimate_execution_time(validated)
        metadata["time_estimate"] = time_estimate

    return validated, metadata


def detect_cyclic_dependencies(
    nodes: list[WorkflowNode],
    edges: list[WorkflowEdge]
) -> tuple[bool, list[str] | None]:
    """检测工作流中的循环依赖

    使用 Kahn's 算法进行拓扑排序：
    1. 构建邻接表和入度表
    2. 从入度为 0 的节点开始处理
    3. 逐步移除边并更新入度
    4. 如果所有节点都被访问，则无循环
    5. 否则存在循环，返回未访问节点列表

    Args:
        nodes: 节点列表
        edges: 边列表

    Returns:
        (has_cycle, cycle_path)
        - has_cycle: 是否存在循环
        - cycle_path: 如果存在循环，返回涉及的节点 ID
    """
    # 构建邻接表
    graph: dict[str, list[str]] = {node.node_id: [] for node in nodes}
    in_degree: dict[str, int] = {node.node_id: 0 for node in nodes}

    for edge in edges:
        graph[edge.source].append(edge.target)
        in_degree[edge.target] += 1

    # Kahn's 拓扑排序
    queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
    visited = []

    while queue:
        node_id = queue.pop(0)
        visited.append(node_id)

        for neighbor in graph[node_id]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # 检查循环
    has_cycle = len(visited) != len(nodes)
    if has_cycle:
        unvisited = [n.node_id for n in nodes if n.node_id not in visited]
        return True, unvisited

    return False, None


def analyze_parallel_opportunities(
    nodes: list[WorkflowNode],
    edges: list[WorkflowEdge]
) -> dict[str, Any]:
    """分析并行执行机会

    将节点按依赖层级分组：
    - 第 0 层：无依赖的起始节点
    - 第 1 层：仅依赖第 0 层的节点
    - 第 n 层：依赖前 n-1 层的节点

    同一层级的节点可以并行执行。

    Returns:
        {
            "total_nodes": 节点总数,
            "parallel_levels": 层级数量,
            "levels": 每层的节点列表,
            "max_parallel_in_level": 单层最大并行数
        }
    """
    # 构建依赖关系
    dependencies: dict[str, list[str]] = {node.node_id: [] for node in nodes}
    for edge in edges:
        dependencies[edge.target].append(edge.source)

    # 按依赖层级分组
    levels: list[list[str]] = []
    processed = set()

    while len(processed) < len(nodes):
        # 当前层级：所有依赖都已处理的节点
        current_level = [
            node_id
            for node_id, deps in dependencies.items()
            if node_id not in processed and all(d in processed for d in deps)
        ]

        if not current_level:
            break

        levels.append(current_level)
        processed.update(current_level)

    return {
        "total_nodes": len(nodes),
        "parallel_levels": len(levels),
        "levels": levels,
        "max_parallel_in_level": max(len(level) for level in levels) if levels else 0,
    }


def check_resource_constraints(
    payload: CreateWorkflowPlanPayload,
    constraints: dict[str, Any] | None = None
) -> dict[str, Any]:
    """检查资源约束

    验证工作流是否满足：
    - 时间约束：全局超时不超过限制
    - 并发限制：并行节点数不超过阈值
    - API 限制：各类型 API 调用次数不超过配额

    Returns:
        {
            "constraints_met": bool,
            "warnings": list[str],
            "violations": list[str],
            "api_calls": dict[str, int]
        }
    """
    if constraints is None:
        constraints = {}

    result = {
        "constraints_met": True,
        "warnings": [],
        "violations": [],
    }

    # 检查时间约束
    time_limit = constraints.get("time_limit", 300)
    global_timeout = payload.global_config.get("timeout", 0) if payload.global_config else 0

    if global_timeout > time_limit:
        result["constraints_met"] = False
        result["violations"].append(
            f"全局超时 ({global_timeout}s) 超过时间限制 ({time_limit}s)"
        )

    # 检查并发限制
    max_parallel = constraints.get("max_parallel", 3)
    parallel_analysis = analyze_parallel_opportunities(payload.nodes, payload.edges)
    max_parallel_in_level = parallel_analysis["max_parallel_in_level"]

    if max_parallel_in_level > max_parallel:
        result["warnings"].append(
            f"某些并行层级有 {max_parallel_in_level} 个节点，超过限制 ({max_parallel})"
        )

    # 统计 API 调用
    api_calls = {"HTTP": 0, "LLM": 0, "DATABASE": 0}
    for node in payload.nodes:
        if node.type in api_calls:
            api_calls[node.type] += 1

    result["api_calls"] = api_calls

    return result
```

**3. ReAct Prompt 模板** (`src/domain/agents/react_prompts.py`)

```python
REACT_SYSTEM_PROMPT = """你是一个智能任务规划助手，擅长将复杂任务分解为可执行的工作流。

你的核心能力：
1. **依赖关系识别**：理解任务之间的先后顺序和数据流
   - 数据依赖：任务 B 需要任务 A 的输出数据
   - 顺序依赖：任务 B 必须在任务 A 完成后执行
   - 条件依赖：任务 B 的执行取决于任务 A 的结果

2. **资源约束感知**：考虑实际执行环境的限制
   - 时间约束：任务总执行时间限制（默认5分钟）
   - API限制：外部API调用次数限制
   - 并发限制：同时执行的任务数量限制（默认3个）
   - 成本约束：LLM token 使用成本估算

3. **结构化决策**：生成符合规范的 JSON 格式决策
   - 所有决策必须包含 action_type
   - 决策 payload 必须符合 Pydantic schema
   - 工作流规划必须是有效的 DAG（无循环）
"""

WORKFLOW_PLANNING_PROMPT = """# 任务规划

## 规划要求

### 1. 依赖关系分析
识别任务之间的依赖关系：
- **数据依赖**：任务 B 需要任务 A 的输出数据
  - 示例：分析数据（B）依赖获取数据（A）的输出
  - 表示方法：在节点 B 的 input_mapping 中引用 ${node_A.output.field}

- **顺序依赖**：任务 B 必须在任务 A 完成后执行
  - 示例：发送报告（B）必须在生成报告（A）之后
  - 表示方法：在 edges 中添加 {source: "A", target: "B"}

- **条件依赖**：任务 B 的执行取决于任务 A 的结果
  - 示例：重试任务（B）仅在失败时执行
  - 表示方法：使用 CONDITION 节点判断

### 2. 资源约束考虑
评估以下资源约束：
- **时间约束**：任务总执行时间限制（默认5分钟）
  - 估算每个节点的执行时间
  - 考虑并行执行的时间节省
  - 设置合理的超时时间

- **API限制**：外部API调用次数限制
  - HTTP 请求：通常有 rate limit
  - LLM 调用：有 token 和费用限制
  - DATABASE 查询：避免过度查询

- **并发限制**：同时执行的任务数量限制（默认3个）
  - 识别可并行执行的节点
  - 避免资源竞争
  - 合理安排执行顺序

### 3. 工作流结构
生成的工作流必须：
- 是有效的 DAG（无循环依赖）
- 节点 ID 必须唯一
- 所有边的 source/target 必须存在
- 每个节点的 config 必须包含必填字段
"""

DEPENDENCY_ANALYSIS_PROMPT = """# 依赖关系分析

## 分析步骤

1. **识别数据流**：
   - 哪些任务产生数据？
   - 哪些任务消费数据？
   - 数据如何在任务间传递？

2. **识别执行顺序**：
   - 哪些任务必须先执行？
   - 哪些任务可以并行执行？
   - 是否存在条件分支？

3. **标注依赖关系**：
   - 使用 edges 表示顺序依赖
   - 使用 input_mapping 表示数据依赖
   - 使用 CONDITION 节点表示条件依赖

## 示例

### 场景：分析销售数据并生成报告

**任务分解**：
1. 获取销售数据（DATABASE）
2. 计算统计指标（PYTHON）
3. 生成图表（PYTHON）
4. 发送报告（HTTP）

**依赖分析**：
- 任务2 数据依赖 任务1（需要销售数据）
- 任务3 数据依赖 任务2（需要统计指标）
- 任务4 顺序依赖 任务3（必须在图表生成后）

**工作流定义**：
```json
{
  "name": "销售数据分析",
  "nodes": [
    {
      "node_id": "fetch_data",
      "type": "DATABASE",
      "name": "获取销售数据",
      "config": {"query": "SELECT * FROM sales"}
    },
    {
      "node_id": "calc_stats",
      "type": "PYTHON",
      "name": "计算统计",
      "config": {"code": "stats = calculate(data)"},
      "input_mapping": {"data": "${fetch_data.output.data}"}
    },
    {
      "node_id": "gen_chart",
      "type": "PYTHON",
      "name": "生成图表",
      "config": {"code": "chart = plot(stats)"},
      "input_mapping": {"stats": "${calc_stats.output.stats}"}
    },
    {
      "node_id": "send_report",
      "type": "HTTP",
      "name": "发送报告",
      "config": {
        "url": "https://api.email.com/send",
        "method": "POST",
        "body": {"chart": "${gen_chart.output.chart}"}
      }
    }
  ],
  "edges": [
    {"source": "fetch_data", "target": "calc_stats"},
    {"source": "calc_stats", "target": "gen_chart"},
    {"source": "gen_chart", "target": "send_report"}
  ]
}
```
"""

RESOURCE_CONSTRAINT_PROMPT = """# 资源约束评估

## 约束类型

### 1. 时间约束
- **全局超时**：整个工作流的最大执行时间
- **节点超时**：单个节点的最大执行时间
- **建议**：
  - HTTP 请求：30-60 秒
  - LLM 调用：60-120 秒
  - DATABASE 查询：10-30 秒
  - PYTHON 执行：5-60 秒

### 2. 并发约束
- **最大并发数**：同时执行的节点数量（默认3个）
- **并行机会**：识别可以并行执行的节点
- **建议**：
  - 独立的 HTTP 请求可以并行
  - 数据依赖的节点必须串行
  - 考虑系统资源限制

### 3. API 限制
- **Rate Limit**：API 调用频率限制
- **Token Limit**：LLM token 使用限制
- **成本限制**：付费 API 的预算限制
- **建议**：
  - 缓存 API 响应避免重复调用
  - 批量请求减少调用次数
  - 监控 token 使用量

## 评估结果格式

```json
{
  "global_config": {
    "timeout": 300,        // 5 分钟全局超时
    "max_parallel": 3,     // 最多 3 个并行
    "max_retries": 2       // 最多重试 2 次
  },
  "estimated_time": 120,   // 预计执行时间（秒）
  "api_calls": {
    "HTTP": 2,
    "LLM": 1,
    "DATABASE": 1
  },
  "parallel_levels": 3,    // 3 个执行层级
  "max_parallel_in_level": 2  // 最大层级有 2 个并行节点
}
```
"""


def format_planning_context(context: dict[str, Any]) -> str:
    """格式化规划上下文

    将会话上下文格式化为适合 LLM 理解的字符串，包含：
    - 当前目标
    - 目标栈（父目标链）
    - 对话历史
    - 已执行决策
    - 资源约束

    Args:
        context: 包含会话信息的字典

    Returns:
        格式化后的上下文字符串
    """
    lines = []

    # 当前目标
    if current_goal := context.get("current_goal"):
        lines.append(f"**当前目标**: {current_goal.get('description', 'N/A')}")
        if parent_id := current_goal.get("parent_id"):
            lines.append(f"**父目标**: {parent_id}")

    # 对话历史
    if conversation_history := context.get("conversation_history"):
        lines.append("\n**对话历史**:")
        for msg in conversation_history[-5:]:  # 最近 5 条
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:100]  # 截断
            lines.append(f"- {role}: {content}")

    # 已执行决策
    if decision_history := context.get("decision_history"):
        lines.append("\n**已执行决策**:")
        for decision in decision_history[-3:]:  # 最近 3 条
            dtype = decision.get("type", "unknown")
            lines.append(f"- {dtype}")

    # 资源约束
    if resource_constraints := context.get("resource_constraints"):
        lines.append("\n**资源约束**:")
        for key, value in resource_constraints.items():
            lines.append(f"- {key}: {value}")

    return "\n".join(lines) if lines else "无上下文信息"
```

#### Pydantic Schema 引用

所有决策 payload 现在使用 Pydantic schema 进行验证，确保数据结构正确性：

```python
# 文件位置: src/domain/agents/decision_payload.py

from pydantic import BaseModel, Field, field_validator

class CreateWorkflowPlanPayload(BaseModel):
    """创建工作流规划 payload

    必填字段：
    - action_type: "create_workflow_plan"
    - name: 工作流名称
    - description: 工作流描述
    - nodes: 节点列表（至少 1 个）
    - edges: 边列表（可为空）

    可选字段：
    - global_config: 全局配置（超时、并发限制等）
    """
    action_type: str = "create_workflow_plan"
    name: str = Field(..., min_length=1, description="工作流名称")
    description: str = Field(..., min_length=1, description="工作流描述")
    nodes: list[WorkflowNode] = Field(..., min_items=1, description="节点列表")
    edges: list[WorkflowEdge] = Field(default_factory=list, description="边列表")
    global_config: dict[str, Any] | None = Field(default=None, description="全局配置")

    @field_validator("nodes")
    @classmethod
    def validate_unique_node_ids(cls, nodes: list[WorkflowNode]) -> list[WorkflowNode]:
        """验证节点 ID 唯一性"""
        node_ids = [node.node_id for node in nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("节点 ID 必须唯一")
        return nodes

    @field_validator("edges")
    @classmethod
    def validate_edges_reference_existing_nodes(
        cls, edges: list[WorkflowEdge], values: dict
    ) -> list[WorkflowEdge]:
        """验证边引用的节点存在"""
        if "nodes" not in values:
            return edges

        node_ids = {node.node_id for node in values["nodes"]}
        for edge in edges:
            if edge.source not in node_ids:
                raise ValueError(f"边的源节点 {edge.source} 不存在")
            if edge.target not in node_ids:
                raise ValueError(f"边的目标节点 {edge.target} 不存在")

        return edges


class WorkflowNode(BaseModel):
    """工作流节点定义"""
    node_id: str = Field(..., min_length=1, description="节点唯一标识")
    type: str = Field(..., description="节点类型（HTTP/LLM/PYTHON/DATABASE/CONDITION）")
    name: str = Field(..., min_length=1, description="节点名称")
    config: dict[str, Any] = Field(..., description="节点配置")
    input_mapping: dict[str, str] | None = Field(default=None, description="输入映射")

    @field_validator("type")
    @classmethod
    def validate_node_type(cls, v: str) -> str:
        """验证节点类型合法性"""
        allowed_types = ["HTTP", "LLM", "PYTHON", "DATABASE", "CONDITION", "START", "END"]
        if v not in allowed_types:
            raise ValueError(f"不支持的节点类型: {v}")
        return v


class WorkflowEdge(BaseModel):
    """工作流边定义"""
    source: str = Field(..., min_length=1, description="源节点 ID")
    target: str = Field(..., min_length=1, description="目标节点 ID")
    condition: str | None = Field(default=None, description="条件表达式（可选）")
```

完整的 schema 定义涵盖所有 10 种决策类型：
- `RespondPayload` - 简单回复
- `CreateNodePayload` - 创建单个节点
- `CreateWorkflowPlanPayload` - 创建工作流规划
- `ExecuteWorkflowPayload` - 执行工作流
- `RequestClarificationPayload` - 请求澄清
- `ContinuePayload` - 继续推理
- `ModifyNodePayload` - 修改节点
- `ErrorRecoveryPayload` - 错误恢复
- `ReplanWorkflowPayload` - 重新规划
- `SpawnSubagentPayload` - 生成子Agent

#### 测试覆盖

```bash
# Schema 验证测试
pytest tests/unit/domain/agents/test_conversation_agent_enhanced.py::TestSchemaEnforcement -v
# 4 tests passed ✅

# 依赖关系测试
pytest tests/unit/domain/agents/test_conversation_agent_enhanced.py::TestDependencyAwarePlanning -v
# 3 tests passed ✅

# 资源约束测试
pytest tests/unit/domain/agents/test_conversation_agent_enhanced.py::TestResourceConstraintAwareness -v
# 3 tests passed ✅

# 真实场景测试
pytest tests/unit/domain/agents/test_conversation_agent_enhanced.py::TestRealWorldScenario -v
# 1 test passed ✅

# 验证与增强函数测试
pytest tests/unit/domain/agents/ -k "conversation_agent_enhanced" -v
# 覆盖率：83% (conversation_agent_enhanced.py)

# Phase 8.2 总计：12 个测试全部通过 ✅
```

**关键测试示例**：

```python
# 测试：循环依赖检测
def test_plan_workflow_should_detect_cyclic_dependencies():
    """验证循环依赖检测"""
    mock_llm.decide_action.return_value = {
        "action_type": "create_workflow_plan",
        "name": "循环工作流",
        "description": "测试循环检测",
        "nodes": [
            {"node_id": "node_1", "type": "HTTP", "name": "节点1", "config": {...}},
            {"node_id": "node_2", "type": "HTTP", "name": "节点2", "config": {...}},
        ],
        "edges": [
            {"source": "node_1", "target": "node_2"},
            {"source": "node_2", "target": "node_1"}  # 循环！
        ]
    }

    # 应该抛出 ValueError
    with pytest.raises(ValueError) as exc_info:
        decision = conversation_agent.make_decision(context_hint="")

    assert "循环" in str(exc_info.value) or "cycle" in str(exc_info.value).lower()


# 测试：并行机会识别
def test_plan_workflow_should_identify_parallel_opportunities():
    """验证并行执行分析"""
    mock_llm.decide_action.return_value = {
        "action_type": "create_workflow_plan",
        "name": "并行数据收集",
        "description": "同时从多个来源收集数据",
        "nodes": [
            {"node_id": "node_1", "type": "HTTP", "name": "获取天气", "config": {...}},
            {"node_id": "node_2", "type": "HTTP", "name": "获取股票", "config": {...}},
            {"node_id": "node_3", "type": "LLM", "name": "综合分析", "config": {...}},
        ],
        "edges": [
            {"source": "node_1", "target": "node_3"},
            {"source": "node_2", "target": "node_3"},
            # node_1 和 node_2 没有直接依赖，可以并行
        ]
    }

    decision = conversation_agent.make_decision(context_hint="")
    payload = CreateWorkflowPlanPayload(**decision.payload)

    # 验证并行结构
    edges_between_1_2 = [
        e for e in payload.edges
        if (e.source == "node_1" and e.target == "node_2") or
           (e.source == "node_2" and e.target == "node_1")
    ]
    assert len(edges_between_1_2) == 0  # node_1 和 node_2 无直接依赖

    # node_3 依赖 node_1 和 node_2
    node_3_deps = [e for e in payload.edges if e.target == "node_3"]
    assert len(node_3_deps) == 2


# 测试：资源约束检查
def test_plan_workflow_should_respect_time_constraint():
    """验证时间约束配置"""
    conversation_agent.session_context.resource_constraints = {
        "time_limit": 300,
        "max_parallel": 3,
    }

    mock_llm.decide_action.return_value = {
        "action_type": "create_workflow_plan",
        "name": "限时任务",
        "description": "需要在 5 分钟内完成",
        "nodes": [...],
        "edges": [],
        "global_config": {"timeout": 300, "max_parallel": 3}
    }

    decision = conversation_agent.make_decision(context_hint="")
    payload = CreateWorkflowPlanPayload(**decision.payload)

    # 验证时间约束
    assert payload.global_config is not None
    assert payload.global_config.get("timeout") == 300
```

#### 使用示例

**创建依赖敏感的工作流规划**：

```python
from src.domain.agents.conversation_agent import ConversationAgent
from src.domain.services.context_manager import GlobalContext, SessionContext

# 设置会话上下文和资源约束
global_ctx = GlobalContext(user_id="user_123")
session_ctx = SessionContext(session_id="session_001", global_context=global_ctx)

# 设置资源约束
session_ctx.resource_constraints = {
    "time_limit": 300,      # 5 分钟时间限制
    "max_parallel": 3,      # 最多 3 个并行任务
    "api_limits": {
        "HTTP": 10,         # 最多 10 次 HTTP 调用
        "LLM": 5,           # 最多 5 次 LLM 调用
    }
}

# 创建 ConversationAgent
agent = ConversationAgent(
    session_context=session_ctx,
    llm=llm,
    event_bus=event_bus
)

# 生成决策（自动进行 schema 验证和依赖分析）
decision = agent.make_decision(context_hint="分析三个月销售数据并生成趋势图")

# 决策 payload 已通过 Pydantic 验证
# 元数据包含依赖分析和资源检查结果
metadata = session_ctx._decision_metadata[-1]["metadata"]

print(f"依赖验证: {metadata['dependencies_valid']}")
print(f"并行层级: {metadata['parallel_analysis']['parallel_levels']}")
print(f"最大并行数: {metadata['parallel_analysis']['max_parallel_in_level']}")
print(f"资源约束检查: {metadata['resource_check']['constraints_met']}")
print(f"API 调用统计: {metadata['resource_check']['api_calls']}")
print(f"预计执行时间: {metadata['time_estimate']['estimated_total_time']}s")
```

#### 验证元数据结构

```python
# 验证元数据示例
{
    "action_type": "create_workflow_plan",
    "timestamp": "2025-12-05T10:30:00",
    "metadata": {
        "dependencies_valid": True,
        "parallel_analysis": {
            "total_nodes": 4,
            "parallel_levels": 4,
            "levels": [
                ["fetch_data"],
                ["calculate_trend"],
                ["generate_chart"],
                ["send_report"]
            ],
            "max_parallel_in_level": 1
        },
        "resource_check": {
            "constraints_met": True,
            "warnings": [],
            "violations": [],
            "api_calls": {
                "HTTP": 1,
                "LLM": 0,
                "DATABASE": 1,
                "PYTHON": 2
            }
        },
        "time_estimate": {
            "estimated_total_time": 20,
            "level_times": [3, 2, 2, 5],
            "parallel_levels": 4,
            "sequential_time": 12
        }
    }
}
```

#### 注意事项

1. **Schema 验证是强制性的**：
   - 所有决策必须通过 Pydantic 验证
   - 验证失败会抛出 ValidationError
   - Coordinator 会拒绝无效的决策

2. **循环依赖检测**：
   - 使用 Kahn's 算法保证工作流是 DAG
   - 检测到循环会立即拒绝决策
   - 返回涉及循环的节点列表便于调试

3. **资源约束是建议性的**：
   - 超过资源限制会生成警告，不会阻止执行
   - 严重违规（如超时 10 倍）会被拒绝
   - 约束配置可通过 SessionContext 动态调整

4. **并行分析提供优化建议**：
   - 自动识别可并行执行的节点
   - 估算执行时间考虑并行效果
   - 元数据可用于工作流可视化

5. **与现有系统兼容**：
   - 不影响现有决策类型的功能
   - 仅在 create_workflow_plan 时进行深度分析
   - 其他决策类型仅做基础 schema 验证

---

### 2.8 检索与监督整合 (Step 5)

#### 功能概述

实现知识库检索和偏离监督机制，确保 ConversationAgent 能够获取相关知识并遵循高优先级笔记的指导：
- 使用 VaultRetriever 检索相关笔记并按优先级排序
- 加权评分：blocker (3.0) > next_action (2.0) > conclusion (1.0)
- 限制注入 ≤6 条笔记，避免上下文过载
- 使用 DeviationDetector 检测 agent 是否忽视高优先级笔记
- 分级告警：blocker 被忽视 → REPLAN_REQUIRED，next_action 被忽视 → WARNING
- 记录注入历史和偏离历史

#### 核心组件

**1. VaultRetriever（知识库检索器）** (`src/domain/services/knowledge_vault_retriever.py`)

```python
class VaultRetriever:
    """知识库检索器

    职责：
    - 从知识库中检索相关笔记
    - 计算加权得分
    - 限制注入数量
    - 提供检索结果
    """

    # 类型权重配置
    TYPE_WEIGHTS = {
        NoteType.BLOCKER: 3.0,      # 最高优先级
        NoteType.NEXT_ACTION: 2.0,  # 中等优先级
        NoteType.CONCLUSION: 1.0,   # 基础优先级
        NoteType.PROGRESS: 0.8,
        NoteType.REFERENCE: 0.5,
    }

    def fetch(
        self,
        query: str,
        notes: list[KnowledgeNote],
        limit_per_type: int | None = None,
        max_total: int | None = None,
        only_approved: bool = False,
    ) -> RetrievalResult:
        """检索相关笔记

        评分公式：
        final_score = relevance_score × type_weight
        normalized_score = min(final_score / max_possible_score, 1.0)

        相关性计算：
        - 内容完全匹配: +0.5
        - 标签匹配: +0.3
        - 部分词语匹配: 每个词 +0.1
        """
        # 计算得分并排序
        scored_notes = []
        for note in notes:
            score = self.calculate_score(note, query)
            scored_notes.append(ScoredNote(note=note, score=score))

        scored_notes.sort(key=lambda x: x.score, reverse=True)

        # 限制总数（默认 6 条）
        limited_notes = scored_notes[:max_total or 6]

        return RetrievalResult(
            notes=[sn.note for sn in limited_notes],
            total_found=len(scored_notes),
            total_returned=len(limited_notes),
            query=query
        )
```

**2. DeviationAlert（偏离告警）** (`src/domain/services/knowledge_deviation_alert.py`)

```python
class AlertType(str, Enum):
    """告警类型"""
    WARNING = "warning"                      # 警告
    REPLAN_REQUIRED = "replan_required"      # 需要重新规划

class AlertSeverity(str, Enum):
    """告警严重程度"""
    LOW = "low"       # 低
    MEDIUM = "medium" # 中
    HIGH = "high"     # 高

@dataclass
class DeviationAlert:
    """偏离告警

    属性：
    - alert_type: 告警类型
    - ignored_notes: 被忽视的笔记列表
    - reason: 告警原因
    - severity: 严重程度
    - timestamp: 告警时间戳
    """
    alert_type: AlertType
    ignored_notes: list[KnowledgeNote]
    reason: str
    severity: AlertSeverity = AlertSeverity.MEDIUM
    timestamp: datetime = field(default_factory=datetime.now)

class DeviationDetector:
    """偏离检测器

    职责：
    - 检测 ConversationAgent 是否忽视了注入的笔记
    - 判断被忽视笔记的严重程度
    - 生成相应的告警
    """

    # 笔记类型对应的严重程度
    TYPE_SEVERITY_MAP = {
        NoteType.BLOCKER: AlertSeverity.HIGH,
        NoteType.NEXT_ACTION: AlertSeverity.MEDIUM,
        NoteType.CONCLUSION: AlertSeverity.LOW,
    }

    def detect_deviation(
        self,
        injected_notes: list[KnowledgeNote],
        agent_actions: list[dict[str, Any]],
    ) -> DeviationAlert | None:
        """检测偏离

        检测规则：
        - blocker 被忽视 → REPLAN_REQUIRED + HIGH
        - next_action 被忽视 → WARNING + MEDIUM
        - conclusion 被忽视 → WARNING + LOW
        """
        # 检查哪些笔记被忽视了
        ignored_notes = []
        for note in injected_notes:
            if self.is_note_ignored(note, agent_actions):
                ignored_notes.append(note)

        if not ignored_notes:
            return None

        # 计算严重程度和告警类型
        severity = self.calculate_severity(ignored_notes)
        alert_type = self._determine_alert_type(ignored_notes)

        return DeviationAlert.create(
            alert_type=alert_type,
            ignored_notes=ignored_notes,
            reason=self._generate_reason(ignored_notes),
            severity=severity
        )
```

**3. KnowledgeCoordinator（知识协调器）** (`src/domain/services/knowledge_coordinator_integration.py`)

```python
class KnowledgeCoordinator:
    """知识协调器

    职责：
    - 检索并注入笔记
    - 记录注入历史
    - 检测 agent 是否忽视高优先级笔记
    - 记录偏离历史
    - 提供查询和统计接口
    """

    def __init__(self, max_injection: int = 6):
        self.retriever = VaultRetriever(default_max_total=max_injection)
        self.detector = DeviationDetector()
        self._injection_history: dict[str, list[InjectionRecord]] = {}
        self._deviation_history: dict[str, list[DeviationRecord]] = {}

    def inject_notes(
        self,
        query: str,
        available_notes: list[KnowledgeNote],
        session_id: str,
        max_total: int | None = None,
    ) -> RetrievalResult:
        """检索并注入笔记"""
        # 使用 VaultRetriever 检索笔记
        result = self.retriever.fetch(
            query=query,
            notes=available_notes,
            max_total=max_total
        )

        # 记录注入历史
        record = InjectionRecord.create(
            session_id=session_id,
            query=query,
            injected_notes=result.notes
        )

        if session_id not in self._injection_history:
            self._injection_history[session_id] = []
        self._injection_history[session_id].append(record)

        return result

    def check_deviation(
        self,
        session_id: str,
        agent_actions: list[dict[str, Any]],
    ) -> DeviationAlert | None:
        """检查偏离"""
        # 获取最近一次注入的笔记
        if session_id not in self._injection_history:
            return None

        latest_injection = self._injection_history[session_id][-1]
        injected_notes = latest_injection.injected_notes

        # 使用 DeviationDetector 检测偏离
        alert = self.detector.detect_deviation(
            injected_notes=injected_notes,
            agent_actions=agent_actions
        )

        # 如果检测到偏离，记录到历史
        if alert is not None:
            record = DeviationRecord.create(
                session_id=session_id,
                alert=alert
            )

            if session_id not in self._deviation_history:
                self._deviation_history[session_id] = []
            self._deviation_history[session_id].append(record)

        return alert

    def get_session_summary(self, session_id: str) -> dict[str, Any]:
        """获取会话摘要"""
        injection_records = self.get_injection_history(session_id)
        deviation_records = self.get_deviation_history(session_id)

        return {
            "session_id": session_id,
            "total_injections": len(injection_records),
            "total_deviations": len(deviation_records),
            "deviation_rate": (
                len(deviation_records) / len(injection_records)
                if injection_records else 0.0
            )
        }
```

#### 检索与监督流程

```
1. 注入阶段：
   Query → VaultRetriever → 加权评分 → 排序 → 限制数量 → 注入笔记
                                                            ↓
                                                    InjectionRecord
                                                    (记录到历史)

2. Agent 执行：
   ConversationAgent → 执行决策 → 生成 agent_actions

3. 监督阶段：
   Agent Actions + Injected Notes → DeviationDetector → 检测忽视
                                                            ↓
                                                    DeviationAlert?
                                                            ↓
                                                    DeviationRecord
                                                    (记录到历史)

4. 告警处理：
   DeviationAlert → 判断 alert_type
                    ├─ REPLAN_REQUIRED → 触发重新规划
                    └─ WARNING → 记录警告日志
```

#### 测试覆盖

```bash
# VaultRetriever 测试
pytest tests/unit/domain/services/test_knowledge_vault_retriever.py -v
# 21 tests passed ✅ (99% 覆盖率)

# DeviationAlert 测试
pytest tests/unit/domain/services/test_knowledge_deviation_alert.py -v
# 18 tests passed ✅ (98% 覆盖率)

# KnowledgeCoordinator 测试
pytest tests/unit/domain/services/test_knowledge_coordinator_integration.py -v
# 14 tests passed ✅ (91% 覆盖率)

# Step 5 总计：53 个测试全部通过 ✅
```

#### 配置示例

```python
# 完整的检索与监督配置
from src.domain.services.knowledge_coordinator_integration import KnowledgeCoordinator
from src.domain.services.knowledge_deviation_alert import AlertType

# 1. 创建协调器
coordinator = KnowledgeCoordinator(max_injection=6)

# 2. 注入笔记
result = coordinator.inject_notes(
    query="database connection",
    available_notes=all_notes,
    session_id="session_001"
)
print(f"注入了 {len(result.notes)} 条笔记")

# 3. Agent 执行行动
agent_actions = [
    {"type": "decision", "content": "实现用户认证功能"},
]

# 4. 检查偏离
alert = coordinator.check_deviation(
    session_id="session_001",
    agent_actions=agent_actions
)

if alert:
    if alert.alert_type == AlertType.REPLAN_REQUIRED:
        print("⚠️ 检测到严重偏离，需要重新规划!")
        # 触发重新规划流程
    else:
        print("ℹ️ 检测到轻微偏离，建议关注")

# 5. 查询统计
summary = coordinator.get_session_summary("session_001")
print(f"偏离率: {summary['deviation_rate']:.2%}")
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

### 4.6 Payload 校验与依赖验证 (Phase 8.4)

**功能概述：** 在事件流中间件层增强决策校验，确保工作流规划的完整性和依赖合法性。

#### 4.6.1 Payload 完整性校验

**目标：** 验证 `DecisionMadeEvent` 的 payload 包含必需字段，防止下游执行失败。

**校验规则：**
```python
# create_node 决策必需字段
required_fields = {
    "create_node": ["node_type", "config"],
    "execute_workflow": ["workflow_id"],
    "create_workflow_plan": ["goal", "nodes", "edges"],
    "modify_node": ["node_id", "config"]
}

# 使用示例
from src.domain.agents.coordinator_agent import PayloadValidationRule

rule = PayloadValidationRule(
    required_fields=["node_type", "config"],
    decision_type="create_node"
)
coordinator.add_rule(rule)
```

**校验流程：**
1. Coordinator 中间件拦截 `DecisionMadeEvent`
2. 根据 `decision_type` 检查 payload 必需字段
3. 缺失字段 → 发布 `DecisionRejectedEvent`，返回 ConversationAgent 重新规划
4. 完整 → 发布 `DecisionValidatedEvent`，继续执行

**测试覆盖：** 9 个单元测试（`test_coordinator_payload_validation.py`）
- ✅ 必需字段存在时通过校验
- ✅ 缺失字段时拒绝决策
- ✅ 多个决策类型的字段验证
- ✅ 嵌套字段校验（如 `config.url`）

#### 4.6.2 DAG 依赖顺序校验

**目标：** 检测工作流规划中的循环依赖，防止执行死锁。

**校验算法：** Kahn 拓扑排序 + 环检测
```python
# 使用示例
from src.domain.agents.coordinator_agent import DependencyValidationRule

rule = DependencyValidationRule()
coordinator.add_rule(rule)

# 检测循环依赖示例
workflow_plan = {
    "nodes": [
        {"id": "A", "type": "llm"},
        {"id": "B", "type": "api"},
        {"id": "C", "type": "code"}
    ],
    "edges": [
        {"source": "A", "target": "B"},
        {"source": "B", "target": "C"},
        {"source": "C", "target": "A"}  # ❌ 循环依赖
    ]
}

# 校验结果
validation_result = coordinator.validate_decision({
    "decision_type": "create_workflow_plan",
    "payload": workflow_plan
})
# → 返回错误: "工作流存在循环依赖 (Circular dependency detected)"
```

**检测步骤：**
1. 构建邻接表和入度表
2. 使用 Kahn 算法进行拓扑排序
3. 如果排序后节点数 < 总节点数 → 存在环
4. 拒绝决策并返回详细错误信息

**测试覆盖：** 9 个单元测试（`test_coordinator_dependency_validation.py`）
- ✅ 无环 DAG 通过校验
- ✅ 简单循环（A→B→A）检测
- ✅ 复杂循环（A→B→C→A）检测
- ✅ 多个独立子图场景
- ✅ 单节点工作流通过

#### 4.6.3 ExecutionProgressEvent 流程 (Phase 8.4)

**目标：** 实现工作流执行过程的流式进度反馈，支持用户实时查看执行状态。

**事件结构：**
```python
@dataclass
class ExecutionProgressEvent(Event):
    workflow_id: str          # 工作流ID
    node_id: str              # 当前执行节点ID
    status: str               # started/running/completed/failed
    progress: float           # 进度百分比 (0.0-1.0)
    message: str              # 用户可读消息
    metadata: dict[str, Any]  # 可选元数据（重试次数、耗时等）
```

**发布者：** `WorkflowAgent`（在节点执行过程中）

**订阅者：** `ConversationAgent`（转发到前端流式输出）

**完整流程：**
```
WorkflowAgent.execute_node_with_progress(node_id)
    │
    ├─ 发布 ExecutionProgressEvent(status="started", progress=0.0)
    │       ↓
    │   EventBus.publish() → ConversationAgent._handle_progress_event_async()
    │       ↓
    │   ConversationAgent.progress_events.append(event)  # 存储历史
    │       ↓
    │   ConversationAgent.forward_progress_event(event)  # 转发到前端
    │       ↓
    │   stream_emitter.emit({
    │       "type": "progress",
    │       "message": "[开始] 正在执行节点 node_1",
    │       "node_id": "node_1",
    │       "status": "started",
    │       "progress": 0.0
    │   })
    │
    ├─ 执行节点逻辑...
    │
    ├─ 发布 ExecutionProgressEvent(status="running", progress=0.5)
    │       ↓ (同上流程)
    │
    └─ 发布 ExecutionProgressEvent(status="completed", progress=1.0)
            ↓ (同上流程)
```

**多格式支持：**
```python
# 1. 人类可读格式（内部日志）
message = conversation_agent.format_progress_message(event)
# → "[执行中 50%] 正在处理数据"

# 2. WebSocket JSON 格式（前端实时通信）
ws_msg = conversation_agent.format_progress_for_websocket(event)
# → {"type": "progress", "data": {"node_id": "...", "progress": 0.5, ...}}

# 3. SSE 格式（Server-Sent Events）
sse_msg = conversation_agent.format_progress_for_sse(event)
# → "data: {\"node_id\": \"...\", \"progress\": 0.5}\n\n"
```

**错误容错机制：**
```python
# WorkflowAgent._publish_progress_event() 内部实现
try:
    await self.event_bus.publish(ExecutionProgressEvent(...))
except Exception:
    # 事件发布失败不应阻塞执行
    pass
```

**测试覆盖：** 27 个测试（Phase 8.4 完整测试套件）
- ✅ WorkflowAgent 进度事件发布（9 tests）
- ✅ ConversationAgent 进度转发（9 tests）
- ✅ 端到端集成测试（9 tests）
- **测试结果：** 27/27 通过 (100%)
- **覆盖率提升：** ConversationAgent 30%→32%, WorkflowAgent 37%→38%

**查询接口：**
```python
# 获取某个工作流的所有进度事件
events = conversation_agent.get_progress_events_by_workflow("workflow_001")

# 获取所有进度事件历史
all_events = conversation_agent.progress_events
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
| **ExecutionProgressEvent** | **WorkflowAgent** | **ConversationAgent** | **流式进度反馈 (Phase 8.4)** |
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
    │ ├─ Payload 完整性校验 (Phase 8.4)
    │ └─ DAG 循环依赖校验 (Phase 8.4)
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
WorkflowAgent.execute_workflow_with_progress()
    │ 执行每个节点
    │
    │ ┌─ 对每个节点 (Phase 8.4 进度事件流) ─┐
    │ │                                          │
    │ ├─ 发布 ExecutionProgressEvent(status="started", progress=0.0)
    │ │       ↓
    │ │   ConversationAgent 订阅并转发到前端
    │ │       ↓
    │ │   前端显示: "[开始] 正在执行节点..."
    │ │
    │ ├─ 执行节点逻辑...
    │ │       ↓
    │ ├─ 发布 ExecutionProgressEvent(status="running", progress=0.5)
    │ │       ↓
    │ │   前端显示: "[执行中 50%] 处理数据中..."
    │ │
    │ ├─ 完成节点执行
    │ │       ↓
    │ └─ 发布 ExecutionProgressEvent(status="completed", progress=1.0)
    │         ↓
    │     前端显示: "[完成 100%] 节点执行完成"
    │
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
| **Phase 8.4** | **Payload校验/DAG校验/进度事件** | **✅ 完成** | **✅ 27/27 (100%)** |
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

## 9. 决策载荷约定（Decision Payload Contract）

> **文档版本**: v1.0
> **创建日期**: 2025-01-22
> **关联文档**: `docs/architecture/decision_payload_scenarios.md`
> **代码位置**: `src/domain/agents/decision_payload.py`

### 9.1 概述

本章节定义了 ConversationAgent 的 10 种决策类型（DecisionType）与 CoordinatorAgent 验证规则之间的契约，确保决策数据的结构正确性和一致性。

### 9.2 核心原则

1. **强类型验证**: 使用 Pydantic 进行 payload 验证
2. **场景驱动**: 每种决策类型对应明确的用户场景
3. **可测试性**: 每种 payload 都有完整的单元测试
4. **向前兼容**: 支持可选字段扩展，不破坏现有功能

### 9.3 决策类型与场景映射

| DecisionType | 用户场景示例 | 必填字段 | 可选字段 |
|-------------|-------------|---------|---------|
| `RESPOND` | "你好"、"今天天气怎么样？" | response, intent, confidence | requires_followup |
| `CREATE_NODE` | "帮我调用天气API" | node_type, node_name, config | description, retry_config |
| `CREATE_WORKFLOW_PLAN` | "分析三个月销售数据并生成趋势图" | name, description, nodes, edges | global_config |
| `EXECUTE_WORKFLOW` | "执行刚才创建的流程" | workflow_id | input_params, execution_mode |
| `REQUEST_CLARIFICATION` | "帮我分析数据"（未指定数据源） | question | options, required_fields, context |
| `CONTINUE` | （内部决策）继续推理 | thought | next_step, progress |
| `MODIFY_NODE` | "把LLM温度调整为0.9" | node_id, updates | reason |
| `ERROR_RECOVERY` | "节点执行失败，API超时" | workflow_id, failed_node_id, failure_reason, recovery_plan, execution_context | error_code |
| `REPLAN_WORKFLOW` | "当前方案不可行，需要调整" | workflow_id, reason, execution_context | suggested_changes, preserve_nodes |
| `SPAWN_SUBAGENT` | "搜索最新的机器学习论文" | subagent_type, task_payload | priority, timeout, context_snapshot |

### 9.4 Payload Schema 定义

#### 9.4.1 RESPOND

```python
from src.domain.agents.decision_payload import RespondPayload

payload = RespondPayload(
    action_type="respond",
    response="您好！我是智能助手。",
    intent="greeting",
    confidence=1.0,
    requires_followup=False
)
```

**验证规则**:
- `response` 不能为空
- `confidence` 范围 [0, 1]
- `intent` 必须是 IntentType 枚举值

#### 9.4.2 CREATE_NODE

```python
from src.domain.agents.decision_payload import CreateNodePayload

# HTTP 节点示例
payload = CreateNodePayload(
    action_type="create_node",
    node_type="HTTP",
    node_name="获取天气",
    config={
        "url": "https://api.weather.com/v1/current",
        "method": "GET",
        "params": {"city": "北京"}
    },
    retry_config={"max_retries": 3, "retry_delay": 1.0}
)
```

**验证规则**:
- `node_type` 必须在允许的类型列表中
- `config` 必须包含该节点类型所需的必填字段
- HTTP 节点：必须有 `url`, `method`
- LLM 节点：必须有 `prompt` 或 `messages`
- PYTHON 节点：必须有 `code`
- DATABASE 节点：必须有 `query`

#### 9.4.3 CREATE_WORKFLOW_PLAN

```python
from src.domain.agents.decision_payload import (
    CreateWorkflowPlanPayload,
    WorkflowNode,
    WorkflowEdge
)

payload = CreateWorkflowPlanPayload(
    action_type="create_workflow_plan",
    name="销售数据分析工作流",
    description="获取数据、分析趋势、生成图表",
    nodes=[
        WorkflowNode(
            node_id="node_1",
            type="DATABASE",
            name="获取销售数据",
            config={"query": "SELECT * FROM sales WHERE ..."}
        ),
        WorkflowNode(
            node_id="node_2",
            type="LLM",
            name="分析数据",
            config={"model": "gpt-4", "prompt": "..."}
        )
    ],
    edges=[
        WorkflowEdge(source="node_1", target="node_2")
    ]
)
```

**验证规则**:
- `nodes` 至少包含 1 个节点
- 节点 ID 必须唯一
- `edges` 必须形成有效的 DAG（无环）
- 边的 source/target 必须存在于 nodes 中
- 不能有孤立节点（除了 START/END）

#### 9.4.4 ERROR_RECOVERY

```python
from src.domain.agents.decision_payload import (
    ErrorRecoveryPayload,
    RecoveryPlan,
    RecoveryAction
)

payload = ErrorRecoveryPayload(
    action_type="error_recovery",
    workflow_id="workflow_123",
    failed_node_id="node_1",
    failure_reason="HTTP request timeout after 30s",
    error_code="TIMEOUT",
    recovery_plan=RecoveryPlan(
        action=RecoveryAction.RETRY,
        delay=5.0,
        max_attempts=3,
        modifications={"config.timeout": 60}
    ),
    execution_context={"retry_count": 1}
)
```

**验证规则**:
- `recovery_plan.action` 必须是 RETRY/SKIP/ABORT/MODIFY 之一
- 如果 action=RETRY，必须提供 `max_attempts`
- 如果 action=MODIFY，必须提供 `modifications`

### 9.5 Coordinator 验证规则

#### 9.5.1 强制规则（所有决策）

```python
# 文件位置: src/domain/agents/coordinator_agent.py

# 规则 1: Payload 必须包含 action_type
Rule(
    id="action_type_required",
    name="payload 必须包含 action_type",
    condition=lambda d: "action_type" in d and d["action_type"] is not None,
    error_message="payload 缺少 action_type 字段"
)

# 规则 2: 禁止危险操作
Rule(
    id="no_arbitrary_code",
    name="禁止任意代码执行",
    condition=lambda d: not is_dangerous_operation(d),
    error_message="检测到危险操作"
)

# 规则 3: 资源限制
Rule(
    id="resource_limits",
    name="payload 大小限制",
    condition=lambda d: calculate_payload_size(d) <= 1024 * 1024,  # 1MB
    error_message="payload 超过 1MB 限制"
)
```

#### 9.5.2 类型特定规则

```python
# CREATE_NODE 规则
Rule(
    id="create_node_valid_type",
    name="节点类型必须合法",
    condition=lambda d: (
        d.get("action_type") != "create_node" or
        d.get("node_type") in ALLOWED_NODE_TYPES
    ),
    error_message="不支持的节点类型"
)

# CREATE_WORKFLOW_PLAN 规则
Rule(
    id="workflow_dag_valid",
    name="工作流必须是有效的 DAG",
    condition=lambda d: (
        d.get("action_type") != "create_workflow_plan" or
        is_valid_dag(d.get("nodes", []), d.get("edges", []))
    ),
    error_message="工作流包含循环依赖"
)

# ERROR_RECOVERY 规则
Rule(
    id="recovery_plan_valid",
    name="恢复计划必须完整",
    condition=lambda d: (
        d.get("action_type") != "error_recovery" or
        validate_recovery_plan(d.get("recovery_plan", {}))
    ),
    error_message="恢复计划不完整"
)
```

### 9.6 Intent → Decision 映射规则

```python
# 文件位置: src/domain/agents/conversation_agent.py

def map_intent_to_decision(intent: IntentType, context: dict) -> DecisionType:
    """根据意图和上下文映射到决策类型"""

    mapping = {
        IntentType.GREETING: [DecisionType.RESPOND],
        IntentType.SIMPLE_QUERY: [
            DecisionType.RESPOND,      # 不需要工具
            DecisionType.CREATE_NODE   # 需要单个工具
        ],
        IntentType.COMPLEX_TASK: [
            DecisionType.CREATE_NODE,           # 单步任务
            DecisionType.CREATE_WORKFLOW_PLAN,  # 多步任务
            DecisionType.SPAWN_SUBAGENT        # 需要专门能力
        ],
        IntentType.WORKFLOW_REQUEST: [
            DecisionType.EXECUTE_WORKFLOW,      # 工作流已存在
            DecisionType.CREATE_WORKFLOW_PLAN   # 工作流不存在
        ],
        IntentType.UNKNOWN: [DecisionType.REQUEST_CLARIFICATION]
    }

    candidates = mapping.get(intent, [])

    # 根据上下文选择最合适的决策类型
    if len(candidates) == 1:
        return candidates[0]

    # 多候选决策，需要进一步判断
    return select_best_decision(candidates, context)
```

### 9.7 事件流程

```
用户输入: "分析销售数据并生成趋势图"
    │
    ▼
ConversationAgent.classify_intent()
    │ → IntentType.COMPLEX_TASK
    ▼
ConversationAgent.execute_step()
    │ → 生成 CREATE_WORKFLOW_PLAN 决策
    │ → 构造 CreateWorkflowPlanPayload
    ▼
发布 DecisionMadeEvent
    │ decision_type="create_workflow_plan"
    │ payload={...}  # CreateWorkflowPlanPayload.model_dump()
    │ confidence=0.9
    ▼
EventBus → Coordinator.as_middleware()
    │
    ├─ 验证 action_type 存在
    ├─ 使用 Pydantic 验证 payload 结构
    ├─ 检查 DAG 有效性
    ├─ 检查节点类型合法性
    └─ 检查资源限制
    │
    ▼
    ├─ ✅ 验证通过 → DecisionValidatedEvent
    │                    ↓
    │                WorkflowAgent.handle_decision()
    │                    ↓
    │                创建节点、执行工作流
    │
    └─ ❌ 验证失败 → DecisionRejectedEvent
                         ↓
                    ConversationAgent.handle_rejection()
                         ↓
                    重新思考、调整决策
```

### 9.8 测试覆盖

#### 9.8.1 单元测试

```bash
# 运行 payload 验证测试
pytest tests/unit/domain/agents/test_decision_payload.py -v

# 测试统计
# - 38 个测试用例
# - 覆盖所有 10 种 DecisionType
# - 包括正向测试（有效 payload）和负向测试（无效 payload）
# - 测试边界条件和错误处理
```

**测试示例**:

```python
def test_create_workflow_plan_with_duplicate_node_ids_should_fail():
    """测试：节点 ID 重复应该失败"""
    with pytest.raises(ValidationError) as exc_info:
        CreateWorkflowPlanPayload(
            name="工作流",
            description="测试",
            nodes=[
                WorkflowNode(node_id="node_1", ...),
                WorkflowNode(node_id="node_1", ...)  # 重复 ID
            ],
            edges=[]
        )

    assert "唯一" in str(exc_info.value)
```

#### 9.8.2 集成测试

```bash
# 运行 EventBus 集成测试
pytest tests/integration/domain/agents/test_decision_event_flow.py -v

# 测试场景：
# - DecisionMadeEvent → Coordinator 验证 → DecisionValidatedEvent
# - 无效决策被拒绝 → DecisionRejectedEvent
# - 验证规则按优先级执行
# - 修正规则自动修复可修正的错误
```

### 9.9 工厂函数使用

```python
from src.domain.agents.decision_payload import create_payload_from_dict

# 从字典创建 payload
payload_dict = {
    "action_type": "respond",
    "response": "您好！",
    "intent": "greeting",
    "confidence": 1.0
}

# 自动推断类型并验证
payload = create_payload_from_dict("respond", payload_dict)

# 转换回字典（用于事件发布）
event_payload = payload.model_dump()
```

### 9.10 最佳实践

1. **始终使用 Pydantic Schema**: 不要手动构造 payload 字典，使用对应的 Pydantic 类
2. **验证优先**: 在发布 DecisionMadeEvent 之前，先用 Pydantic 验证 payload
3. **错误处理**: 捕获 ValidationError 并转换为用户友好的错误消息
4. **日志记录**: 记录所有决策和验证结果，便于调试和审计
5. **测试驱动**: 为每种决策类型编写完整的测试用例

### 9.11 扩展指南

#### 添加新的决策类型

1. 在 `DecisionType` 枚举中添加新类型
2. 在 `decision_payload.py` 中定义 Pydantic schema
3. 在 `decision_payload_scenarios.md` 中添加场景描述
4. 编写单元测试（至少 5 个测试用例）
5. 在 Coordinator 中添加验证规则
6. 更新 Intent → Decision 映射规则
7. 编写集成测试验证完整流程

#### 修改现有 Payload

1. **向后兼容**: 只添加可选字段，不修改必填字段
2. **版本管理**: 如需破坏性修改，增加版本号（如 RespondPayloadV2）
3. **测试更新**: 更新相关测试用例
4. **文档更新**: 同步更新文档和示例

### 9.12 常见问题

**Q: 如何处理 payload 验证失败？**

A: Pydantic 会抛出 `ValidationError`，包含详细的错误信息。Coordinator 应捕获此异常并发布 `DecisionRejectedEvent`，包含错误详情。

```python
try:
    payload = CreateNodePayload(**payload_dict)
except ValidationError as e:
    errors = [error["msg"] for error in e.errors()]
    event_bus.publish(DecisionRejectedEvent(
        decision_id=decision.id,
        errors=errors
    ))
```

**Q: 如何支持自定义节点类型？**

A: 扩展 `NodeType` 枚举，并在 Coordinator 的节点类型白名单中添加。同时需要实现对应的节点执行器。

**Q: 如何处理大型 payload（如包含大量节点的工作流）？**

A: 使用流式传输或分块传输。对于超大工作流，可以先创建工作流骨架，然后逐步添加节点。

### 9.13 相关文档

- 详细场景说明: `docs/architecture/decision_payload_scenarios.md`
- 代码实现: `src/domain/agents/decision_payload.py`
- 单元测试: `tests/unit/domain/agents/test_decision_payload.py`
- Coordinator 验证规则: `src/domain/agents/coordinator_agent.py`
- ConversationAgent 决策生成: `src/domain/agents/conversation_agent.py`

---

## 10. 架构建议

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

---

## 10. 会话流生成器（SessionFlowGenerator）设计

> 目标：让 ConversationAgent 能够把推理过程、工具调用和最终答案以流式方式主动推送给用户层，即便没有 Claude Code 那样的消息队列，也能满足前端渲染协议。

### 10.1 背景与目标
- **现状痛点**：ConversationAgent 只能通过 EventBus 间接通知，前端要等待 Workflow 结束才能看到结果，缺少对“思考链路”的实时可视化。
- **建设目标**：提供一个被 ConversationAgent 直接驱动的“会话流生成器”，ReAct 的每一步（Thought/Action/Observation）以及工具调用、最终回答都能即时推送。
- **技术约束**：当前仍是单体/轻量服务，没有外部 MQ；需要在本进程内实现可靠、可追溯的流式管道。

### 10.2 项目审批要点
| 维度 | 审批结论 | 关键说明 |
|------|----------|---------|
| 业务必要性 | ✅ 通过 | 解决“用户看不到 Agent 思考过程”的核心诉求 |
| 技术可行性 | ✅ 通过 | 复用 SessionContext + EventBus，新增内存 Broker，改动面可控 |
| 交互成本 | ✅ 通过 | 前端已有 SSE/WS 能力，只需遵循统一消息协议 |
| 风险等级 | 🟡 中 | 新增流式管道需处理背压与故障隔离，规划里写明缓解方案 |

### 10.3 体系结构概览
```
ConversationAgent
    │ (1) SessionFlowCommand（会话流指令）
    ▼
SessionFlowGenerator（领域服务）
    ├─ FlowStateTracker（状态追踪器）        # 维护会话上下文、序号
    ├─ FlowFormatter（格式化器）             # 输出标准化消息（type/schema/version）
    ├─ FlowBroker（异步队列）               # 内存流，提供背压与重放
    └─ FlowDispatcher（分发器）             # 推送至接口层（SSE/WebSocket）
            │ (4) 推送 SessionFlowMessage
            ▼
用户交互层（FastAPI 流式接口 → 前端渲染）
```

### 10.4 关键职责
1. **指令接收**：提供 `emit_thought/emit_action/emit_observation/emit_final` 等 API，ConversationAgent 在 ReAct 各阶段显式调用。
2. **统一格式化**：将原始 payload 规范化为 `SessionFlowMessage`，包含 type、timestamp、content、tool_call 等字段，前端一次解析即可展示。
3. **顺序与补偿**：FlowStateTracker 记录步骤序号与工具调用上下文，支持局部重放、补齐缺失步骤。
4. **推送与背压**：FlowBroker 以 session 维度的 `asyncio.Queue` 存放消息，FlowDispatcher 监听并推送至 SSE/WS；若队列过长可返回背压信号并暂存 N 条。
5. **事件类型覆盖**：支持 `THOUGHT`、`ACTION`、`OBSERVATION`、`TOOL_REQUEST`、`TOOL_RESULT`、`FINAL_ANSWER`、`SYSTEM_NOTICE` 等类型。

### 10.5 数据模型
```python
class SessionFlowType(str, Enum):
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    TOOL_REQUEST = "tool_request"
    TOOL_RESULT = "tool_result"
    FINAL_ANSWER = "final_answer"
    SYSTEM_NOTICE = "system_notice"

@dataclass
class SessionFlowCommand:
    session_id: str
    step_id: str                     # 例如 "goal-3.step-1"
    flow_type: SessionFlowType
    payload: dict                    # 原始数据
    routing_hint: dict | None        # 是否需要高亮/提醒

@dataclass
class SessionFlowMessage:
    session_id: str
    stream_seq: int                  # 流式递增序号
    displayed_at: datetime
    flow_type: SessionFlowType
    content: dict                    # 标题/正文/元数据
    raw_payload: dict | None
```

### 10.6 交互流程（一步一步）
1. **生成思考**：ConversationAgent 在 ReAct 的 Thought 阶段调用 `emit_thought` 发送 SessionFlowCommand。
2. **状态入栈**：FlowStateTracker 记录 `step_id`、当前目标、父节点，生成 `stream_seq` 与时间轴。
3. **格式化输出**：FlowFormatter 根据 `flow_type` 套用模板（工具调用展示名称+参数，最终回答支持 Markdown）。
4. **排队与背压**：消息写入对应 session 的 FlowBroker 队列；若接近阈值触发慢速告警并向 Agent 返回背压提示。
5. **分发推送**：FlowDispatcher 监听队列 → FastAPI `SessionFlowStreamEndpoint`（SSE/WS）→ 前端 `StreamAdapter` 逐条渲染。
6. **状态同步**：如需用户确认（例如“请确认工具调用”），可透过现有 WebSocket 回传给 ConversationAgent 继续流程。

### 10.7 推送机制（无消息队列）
- **SessionFlowBroker**：基于 `asyncio.Queue` 或 `MemoryChannel`，以 `session_id` 作为 key，支持 `max_queue_size`、过载丢弃策略与磁盘持久化钩子。
- **接口层适配**：新增 `/api/v1/sessions/{session_id}/flow/stream` SSE 端点，复用现有 `StreamManager` 管理连接。
- **断线恢复**：用户重连时可调用 `GET /api/v1/sessions/{session_id}/flow?after_seq=xxx` 拉取缺失片段，保证体验连续。

### 10.8 设计评判与风险缓解
- **格式一致性**：Formatter 层隔离前端差异，未来切换 UI 仅需新增 formatter。
- **资源占用**：大量并发会话会放大内存队列，需要指标（队列长度、延迟）与自动裁剪策略。
- **耦合度**：ConversationAgent 直接驱动组件，避免额外 Coordinator 跳转；WorkflowAgent 产生的工具结果通过 EventBus 转换为 SessionFlowCommand 注入。
- **失效场景**：Dispatcher 故障不会影响核心执行，FlowGenerator 只负责展示；最终答案仍通过原通道返回用户。

### 10.9 迭代规划（调整后）
1. **阶段 A：MVP（最小可行版本）**
   - 实现 SessionFlowGenerator、基础 Markdown FlowFormatter、内存型 FlowBroker；
   - ConversationAgent 接入 `emit_*` API，前端以 SSE 即时显示推理链路。
2. **阶段 B：工具可视化**
   - 订阅 WorkflowAgent/Coordinator 事件并映射为 TOOL_REQUEST/RESULT；
   - 增加 `system_notice`，用于安全告警、重试提醒等系统提示。
3. **阶段 C：可靠性增强**
   - 持久化最近 N 条消息并提供拉取接口；
   - 建立指标与告警（处理延迟、丢包率）。
4. **阶段 D：可插拔传输层**
   - FlowDispatcher 支持 SSE / WebSocket / gRPC Stream 多种输出；
   - 如未来引入消息队列，仅需将 FlowBroker 替换为 Kafka/Redis Stream 适配器。
