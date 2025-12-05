# ToolEngine 架构文档

> 文档日期：2025-12-05
> 版本：1.0.0
> 状态：阶段 1-6 完成

---

## 1. 系统概览

### 1.1 ToolEngine 在系统中的位置

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ConversationAgent                                │
│                    "大脑" - 理解与决策                                │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ 需要调用工具时，创建 ToolSubAgent                            │    │
│  └─────────────────────────────────────────────────────────────┘    │
└───────────────────────────────┼─────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        ToolSubAgent                                  │
│                    "工具调用代理"                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ • 在隔离环境中执行工具调用                                    │    │
│  │ • 维护执行历史                                               │    │
│  │ • 生成调用摘要                                               │    │
│  └─────────────────────────────────────────────────────────────┘    │
└───────────────────────────────┼─────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         ToolEngine                                   │
│                    "工具执行引擎"                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ • 工具配置加载与索引                                         │    │
│  │ • 参数验证                                                   │    │
│  │ • 执行器调度                                                 │    │
│  │ • 并发控制                                                   │    │
│  │ • 知识库记录                                                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
└───────────────────────────────┼─────────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│   EchoExecutor   │ │  HTTPExecutor    │ │ CalculatorExec   │
│   (内置测试)      │ │  (HTTP 请求)     │ │  (数学计算)       │
└──────────────────┘ └──────────────────┘ └──────────────────┘
```

### 1.2 核心组件

| 组件 | 文件路径 | 职责 |
|------|---------|------|
| ToolEngine | `src/domain/services/tool_engine.py` | 工具加载、索引、执行调度 |
| ToolConfigLoader | `src/domain/services/tool_config_loader.py` | YAML 配置解析 |
| ToolParameterValidator | `src/domain/services/tool_parameter_validator.py` | 参数验证 |
| ToolExecutor | `src/domain/services/tool_executor.py` | 执行器协议、ToolSubAgent |
| ToolConcurrencyController | `src/domain/services/tool_concurrency_controller.py` | 并发控制 |
| ToolKnowledgeStore | `src/domain/services/tool_knowledge_store.py` | 调用记录存储 |

---

## 2. 工具定义（YAML 格式）

### 2.1 完整配置示例

```yaml
# tools/http_request.yaml
name: http_request
version: "1.0.0"
description: 发送 HTTP 请求并返回响应
category: http
tags:
  - network
  - api
  - request

# 参数定义
parameters:
  - name: url
    type: string
    required: true
    description: 请求 URL
    validation:
      pattern: "^https?://"

  - name: method
    type: string
    required: false
    default: "GET"
    description: HTTP 方法
    validation:
      enum: ["GET", "POST", "PUT", "DELETE", "PATCH"]

  - name: headers
    type: object
    required: false
    description: 请求头

  - name: body
    type: object
    required: false
    description: 请求体（POST/PUT/PATCH）

  - name: timeout
    type: number
    required: false
    default: 30
    description: 超时时间（秒）
    validation:
      min: 1
      max: 300

# 入口配置
entry:
  type: builtin          # builtin | external | custom
  handler: http_request  # 执行器名称

# 可选：输出定义
output:
  type: object
  properties:
    status_code: integer
    headers: object
    body: any
```

### 2.2 参数类型

| 类型 | 说明 | 验证选项 |
|------|------|---------|
| `string` | 字符串 | `pattern`, `min_length`, `max_length`, `enum` |
| `number` | 数字 | `min`, `max` |
| `integer` | 整数 | `min`, `max` |
| `boolean` | 布尔值 | - |
| `array` | 数组 | `items`, `min_items`, `max_items` |
| `object` | 对象 | `properties`, `required` |

### 2.3 工具分类（ToolCategory）

```python
class ToolCategory(str, Enum):
    HTTP = "http"              # HTTP 请求工具
    DATABASE = "database"      # 数据库操作工具
    FILE = "file"              # 文件处理工具
    AI = "ai"                  # AI 相关工具
    NOTIFICATION = "notification"  # 通知工具
    CUSTOM = "custom"          # 用户自定义工具
```

---

## 3. ToolSubAgent 调用流程

### 3.1 创建与执行

```python
from src.domain.services.tool_executor import ToolSubAgent
from src.domain.services.tool_engine import ToolEngine

# 1. 创建 ToolSubAgent
sub_agent = ToolSubAgent(
    agent_id="tool_sub_agent_001",
    tool_engine=tool_engine,
    parent_agent_id="conversation_agent_001",
    on_result_callback=handle_result,  # 可选回调
)

# 2. 执行单个工具
result = await sub_agent.execute(
    tool_name="http_request",
    params={"url": "https://api.example.com/data"},
    timeout=30.0,
)

# 3. 批量执行
results = await sub_agent.execute_batch([
    ("echo", {"message": "hello"}),
    ("calculator", {"expression": "1+2"}),
])

# 4. 获取执行摘要
summary = sub_agent.get_execution_summary()
# {
#     "agent_id": "tool_sub_agent_001",
#     "total_calls": 3,
#     "successful_calls": 3,
#     "success_rate": 100.0,
#     "tool_usage": {"http_request": 1, "echo": 1, "calculator": 1},
#     "call_details": [...]
# }

# 5. 获取简要摘要（给前端）
brief = sub_agent.get_brief_summary()
```

### 3.2 执行流程图

```
ToolSubAgent.execute(tool_name, params)
    │
    ▼
创建 ToolExecutionContext
    │ caller_id, caller_type, conversation_id
    ▼
ToolEngine.execute(tool_name, params, context)
    │
    ├─► 1. 检查工具是否存在
    │       └─► 不存在: 返回 tool_not_found 错误
    │
    ├─► 2. 验证参数
    │       └─► 验证失败: 返回 validation_error
    │
    ├─► 3. 获取执行器
    │       └─► 未找到: 返回 executor_not_found 错误
    │
    ├─► 4. 发送 EXECUTION_STARTED 事件
    │
    ├─► 5. 执行工具（带超时）
    │       ├─► 成功: 创建成功结果
    │       ├─► 超时: 创建 timeout 错误
    │       └─► 异常: 创建 execution_error
    │
    ├─► 6. 记录到知识库
    │
    └─► 7. 返回 ToolExecutionResult
            │
            ▼
    ToolSubAgent 记录到执行历史
            │
            ▼
    触发回调（如有）
```

### 3.3 执行上下文

```python
@dataclass
class ToolExecutionContext:
    # 调用者信息
    caller_id: str | None = None
    caller_type: str = "unknown"  # conversation_agent, workflow_node, direct
    conversation_id: str | None = None
    workflow_id: str | None = None

    # 执行配置
    timeout: float = 30.0
    retry_count: int = 0
    max_retries: int = 3

    # 共享变量
    variables: dict[str, Any] = field(default_factory=dict)

    # 工厂方法
    @classmethod
    def for_conversation(cls, agent_id, conversation_id, **kwargs)

    @classmethod
    def for_workflow(cls, workflow_id, node_id, **kwargs)
```

---

## 4. 并发控制策略

### 4.1 配置选项

```python
@dataclass
class ConcurrencyConfig:
    max_concurrent: int = 10       # 最大并发数
    queue_size: int = 100          # 队列大小
    default_timeout: float = 30.0  # 默认超时
    strategy: str = "fifo"         # fifo | priority | reject
    bucket_limits: dict[str, int] = field(default_factory=dict)
    # 例如: {"http": 5, "ai": 2} - 按工具类型限流
```

### 4.2 排队策略

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| `fifo` | 先进先出队列 | 默认策略，公平调度 |
| `priority` | 优先级队列 | 重要任务优先执行 |
| `reject` | 超限直接拒绝 | 高并发保护 |

### 4.3 负载均衡（分桶限流）

```python
# 配置不同工具类型的并发限制
config = ConcurrencyConfig(
    max_concurrent=10,
    bucket_limits={
        "http": 5,      # HTTP 工具最多 5 个并发
        "ai": 2,        # AI 工具最多 2 个并发
        "database": 3,  # 数据库工具最多 3 个并发
    }
)

controller = ToolConcurrencyController(config)
```

### 4.4 Workflow 节点绕过

```python
# Workflow 节点不受并发限制
# caller_type="workflow_node" 时自动绕过
context = ToolExecutionContext.for_workflow(
    workflow_id="wf_001",
    node_id="node_001",
)
# 此调用不计入并发数
```

### 4.5 监控指标

```python
metrics = controller.get_metrics()
# ConcurrencyMetrics(
#     current_concurrent=5,    # 当前并发数
#     queue_length=3,          # 队列长度
#     total_acquired=100,      # 总获取次数
#     total_rejected=2,        # 总拒绝次数
#     total_timeout=1,         # 总超时次数
#     avg_execution_time=0.5,  # 平均执行时间
# )

bucket_metrics = controller.get_bucket_metrics()
# {
#     "http": {"current": 3, "limit": 5, "queue": 1},
#     "ai": {"current": 2, "limit": 2, "queue": 5},
# }
```

---

## 5. 知识库集成

### 5.1 调用记录

```python
@dataclass
class ToolCallRecord:
    record_id: str
    tool_name: str
    params: dict[str, Any]
    result: dict[str, Any]
    execution_time: float
    is_success: bool
    error: str | None
    caller_id: str | None
    caller_type: str
    conversation_id: str | None
    workflow_id: str | None
    created_at: datetime
```

### 5.2 查询接口

```python
# 按会话查询
records = await engine.query_call_records(conversation_id="conv_001")

# 按工具名查询
records = await engine.query_call_records(tool_name="http_request")

# 获取会话摘要
summary = await engine.get_call_summary("conv_001")
# ToolCallSummary(
#     conversation_id="conv_001",
#     total_calls=10,
#     successful_calls=9,
#     failed_calls=1,
#     success_rate=90.0,
#     tool_usage={"http_request": 5, "echo": 3, "calculator": 2},
# )

# 获取全局统计
stats = await engine.get_call_statistics()
```

### 5.3 最终结果包含工具使用记录

```python
# ConversationAgent 完成任务时
summary = await engine.get_call_summary(conversation_id)

final_result = {
    "status": "completed",
    "answer": "任务已完成，结果是...",
    "tool_usage_summary": summary.to_brief(),
    # {
    #     "total_calls": 5,
    #     "success_rate": 100.0,
    #     "tool_usage": {"http_request": 2, "calculator": 3},
    #     "has_errors": False,
    # }
}
```

---

## 6. 事件系统

### 6.1 事件类型

```python
class ToolEngineEventType(str, Enum):
    TOOL_LOADED = "tool_loaded"           # 工具加载完成
    TOOL_ADDED = "tool_added"             # 工具添加
    TOOL_UPDATED = "tool_updated"         # 工具更新
    TOOL_REMOVED = "tool_removed"         # 工具移除
    RELOAD_STARTED = "reload_started"     # 重载开始
    RELOAD_COMPLETED = "reload_completed" # 重载完成
    LOAD_ERROR = "load_error"             # 加载错误
    VALIDATION_ERROR = "validation_error" # 参数验证错误
    EXECUTION_STARTED = "execution_started"   # 执行开始
    EXECUTION_COMPLETED = "execution_completed" # 执行完成
    EXECUTION_FAILED = "execution_failed"     # 执行失败
```

### 6.2 订阅事件

```python
def on_tool_event(event: ToolEngineEvent):
    if event.event_type == ToolEngineEventType.EXECUTION_COMPLETED:
        print(f"工具 {event.tool_name} 执行完成")
    elif event.event_type == ToolEngineEventType.EXECUTION_FAILED:
        print(f"工具 {event.tool_name} 执行失败: {event.error}")

engine.subscribe(on_tool_event)
```

---

## 7. 测试覆盖

### 7.1 单元测试

```bash
# 运行所有工具相关单元测试
pytest tests/unit/domain/services/test_tool_*.py -v

# 关键测试文件
tests/unit/domain/services/test_tool_config_loader.py      # 配置加载
tests/unit/domain/services/test_tool_parameter_validator.py # 参数验证
tests/unit/domain/services/test_tool_engine.py             # 引擎核心
tests/unit/domain/services/test_tool_executor.py           # 执行器
tests/unit/domain/services/test_tool_concurrency_controller.py # 并发控制
tests/unit/domain/services/test_tool_knowledge_store.py    # 知识库
```

### 7.2 集成测试

```bash
# 运行集成测试
pytest tests/integration/test_tool_*.py -v

# 关键测试文件
tests/integration/test_tool_engine_integration.py          # 引擎集成
tests/integration/test_tool_configs.py                     # 配置集成
tests/integration/test_tool_knowledge_integration.py       # 知识库集成
```

---

## 8. 配置参数汇总

### 8.1 ToolEngineConfig

```python
@dataclass
class ToolEngineConfig:
    tools_directory: str = "tools"      # 工具配置目录
    auto_reload: bool = True            # 是否支持自动重载
    reload_interval: float = 5.0        # 自动重载间隔（秒）
    watch_for_changes: bool = False     # 是否监听文件变化
    strict_validation: bool = False     # 是否启用严格参数验证
```

### 8.2 ConcurrencyConfig

```python
@dataclass
class ConcurrencyConfig:
    max_concurrent: int = 10            # 最大并发数
    queue_size: int = 100               # 队列大小
    default_timeout: float = 30.0       # 默认超时
    strategy: str = "fifo"              # 排队策略
    bucket_limits: dict[str, int] = {}  # 分桶限流
```

---

## 附录 A：完整类型定义

### A.1 ToolExecutionResult

```python
@dataclass
class ToolExecutionResult:
    is_success: bool
    tool_name: str
    output: dict[str, Any]
    error: str | None
    error_type: str | None  # validation_error, execution_error, timeout, tool_not_found
    validation_errors: list[dict]
    execution_time: float
    executed_at: datetime
    metadata: dict[str, Any]
```

### A.2 ValidationResult

```python
@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[ValidationError]
    validated_params: dict[str, Any]  # 包含默认值
```

### A.3 Tool Entity

```python
@dataclass
class Tool:
    id: str
    name: str
    version: str
    description: str
    category: ToolCategory
    tags: list[str]
    parameters: list[ToolParameter]
    implementation_config: dict[str, Any]
    status: str
```
