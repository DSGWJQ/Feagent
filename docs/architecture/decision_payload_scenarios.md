# 决策载荷场景映射与约定

> **文档版本**: v1.0
> **创建日期**: 2025-01-22
> **适用阶段**: 需求蓝图（第一步）
> **关联**: ConversationAgent DecisionType → CoordinatorAgent 验证规则

---

## 1. 场景概览

本文档定义了 ConversationAgent 的 10 种决策类型（DecisionType）在真实用户场景中的应用，明确每种决策需要携带的 payload 字段及其与 Coordinator 的验证规则。

---

## 2. 典型用户场景与决策映射

### 场景 1: 简单问候与查询

**用户输入**: "你好"、"今天天气怎么样？"、"什么是Python？"

**场景特征**:
- 不需要复杂推理
- 不需要工具调用
- 可以直接回复

**决策类型**: `RESPOND`

**Payload Schema**:
```python
{
    "action_type": "respond",
    "response": str,              # 必填：回复内容
    "intent": str,                # 必填：意图类型（greeting/simple_query）
    "confidence": float,          # 必填：置信度 (0-1)
    "requires_followup": bool     # 可选：是否需要后续对话
}
```

**Coordinator 验证规则**:
- `response` 不能为空
- `confidence` 范围 0-1
- `intent` 必须是 greeting/simple_query

**示例**:
```python
payload = {
    "action_type": "respond",
    "response": "您好！我是智能助手，很高兴为您服务。",
    "intent": "greeting",
    "confidence": 1.0,
    "requires_followup": False
}
```

---

### 场景 2: 创建单个工具节点

**用户输入**: "帮我调用天气API获取北京的天气"

**场景特征**:
- 需要单个工具/节点
- 参数明确
- 不需要多步编排

**决策类型**: `CREATE_NODE`

**Payload Schema**:
```python
{
    "action_type": "create_node",
    "node_type": str,             # 必填：节点类型（LLM/HTTP/PYTHON/DATABASE等）
    "node_name": str,             # 必填：节点名称
    "config": dict,               # 必填：节点配置
    "description": str,           # 可选：节点描述
    "retry_config": dict | None   # 可选：重试配置
}
```

**Coordinator 验证规则**:
- `node_type` 必须在允许的类型列表中：LLM, HTTP, PYTHON, DATABASE, CONDITION, LOOP
- `config` 必须包含该节点类型所需的必填字段
- HTTP 节点：必须有 url, method
- LLM 节点：必须有 prompt 或 messages
- PYTHON 节点：必须有 code
- DATABASE 节点：必须有 query

**示例 - HTTP 节点**:
```python
payload = {
    "action_type": "create_node",
    "node_type": "HTTP",
    "node_name": "获取北京天气",
    "config": {
        "url": "https://api.weather.com/v1/current",
        "method": "GET",
        "params": {
            "city": "北京",
            "key": "${WEATHER_API_KEY}"
        },
        "timeout": 10
    },
    "description": "调用天气API获取北京实时天气数据",
    "retry_config": {
        "max_retries": 3,
        "retry_delay": 1.0
    }
}
```

**示例 - LLM 节点**:
```python
payload = {
    "action_type": "create_node",
    "node_type": "LLM",
    "node_name": "数据分析",
    "config": {
        "model": "gpt-4",
        "prompt": "请分析以下数据：${input_data}",
        "temperature": 0.7,
        "max_tokens": 1000
    }
}
```

---

### 场景 3: 复杂多步任务（工作流规划）

**用户输入**: "分析最近三个月的销售数据并生成趋势图，然后发送给我"

**场景特征**:
- 需要多个步骤
- 步骤之间有依赖关系
- 需要数据流转

**决策类型**: `CREATE_WORKFLOW_PLAN`

**Payload Schema**:
```python
{
    "action_type": "create_workflow_plan",
    "name": str,                  # 必填：工作流名称
    "description": str,           # 必填：工作流描述
    "nodes": list[dict],          # 必填：节点列表
    "edges": list[dict],          # 必填：边列表
    "global_config": dict | None  # 可选：全局配置（超时、环境变量等）
}
```

**Node Schema**:
```python
{
    "node_id": str,               # 必填：节点唯一ID
    "type": str,                  # 必填：节点类型
    "name": str,                  # 必填：节点名称
    "config": dict,               # 必填：节点配置
    "input_mapping": dict | None, # 可选：输入映射
    "output_mapping": dict | None # 可选：输出映射
}
```

**Edge Schema**:
```python
{
    "source": str,                # 必填：源节点ID
    "target": str,                # 必填：目标节点ID
    "condition": str | None       # 可选：条件表达式
}
```

**Coordinator 验证规则**:
- `nodes` 至少包含 1 个节点
- `edges` 必须形成有效的 DAG（无环）
- 每个 node 的 `type` 必须合法
- 每个 edge 的 source/target 必须存在于 nodes 中
- 不能有孤立节点（除了 START/END）
- 每个 node 的 config 必须符合其类型的要求

**示例**:
```python
payload = {
    "action_type": "create_workflow_plan",
    "name": "销售数据分析工作流",
    "description": "获取销售数据、分析趋势、生成图表、发送报告",
    "nodes": [
        {
            "node_id": "node_1",
            "type": "DATABASE",
            "name": "获取销售数据",
            "config": {
                "query": "SELECT * FROM sales WHERE date >= DATE_SUB(NOW(), INTERVAL 3 MONTH)",
                "connection": "sales_db"
            }
        },
        {
            "node_id": "node_2",
            "type": "PYTHON",
            "name": "计算趋势",
            "config": {
                "code": "import pandas as pd\ndf = pd.DataFrame(input_data)\ntrend = df.groupby('month')['amount'].sum()\nreturn {'trend': trend.to_dict()}"
            },
            "input_mapping": {
                "input_data": "${node_1.output.data}"
            }
        },
        {
            "node_id": "node_3",
            "type": "PYTHON",
            "name": "生成趋势图",
            "config": {
                "code": "import matplotlib.pyplot as plt\nplt.plot(trend.keys(), trend.values())\nplt.savefig('trend.png')\nreturn {'chart_path': 'trend.png'}"
            },
            "input_mapping": {
                "trend": "${node_2.output.trend}"
            }
        },
        {
            "node_id": "node_4",
            "type": "HTTP",
            "name": "发送邮件",
            "config": {
                "url": "https://api.email.com/send",
                "method": "POST",
                "body": {
                    "to": "user@example.com",
                    "subject": "销售趋势报告",
                    "attachments": ["${node_3.output.chart_path}"]
                }
            }
        }
    ],
    "edges": [
        {"source": "node_1", "target": "node_2"},
        {"source": "node_2", "target": "node_3"},
        {"source": "node_3", "target": "node_4"}
    ],
    "global_config": {
        "timeout": 300,
        "env": {
            "SALES_DB_URL": "postgresql://...",
            "EMAIL_API_KEY": "..."
        }
    }
}
```

---

### 场景 4: 执行已有工作流

**用户输入**: "执行刚才创建的销售分析流程"

**场景特征**:
- 工作流已经创建
- 直接执行
- 可能需要传递运行时参数

**决策类型**: `EXECUTE_WORKFLOW`

**Payload Schema**:
```python
{
    "action_type": "execute_workflow",
    "workflow_id": str,           # 必填：工作流ID
    "input_params": dict | None,  # 可选：运行时参数
    "execution_mode": str,        # 可选：执行模式（sync/async）
    "notify_on_completion": bool  # 可选：是否在完成时通知
}
```

**Coordinator 验证规则**:
- `workflow_id` 必须存在
- 工作流状态必须是 READY 或 COMPLETED
- `execution_mode` 必须是 sync 或 async
- `input_params` 中的参数必须与工作流定义的输入参数匹配

**示例**:
```python
payload = {
    "action_type": "execute_workflow",
    "workflow_id": "workflow_123",
    "input_params": {
        "date_range": "last_3_months",
        "recipient_email": "manager@example.com"
    },
    "execution_mode": "async",
    "notify_on_completion": True
}
```

---

### 场景 5: 请求澄清

**用户输入**: "帮我分析数据"（未指定数据源）

**场景特征**:
- 需求不明确
- 缺少关键信息
- 需要用户选择或补充

**决策类型**: `REQUEST_CLARIFICATION`

**Payload Schema**:
```python
{
    "action_type": "request_clarification",
    "question": str,              # 必填：澄清问题
    "options": list[str] | None,  # 可选：选项列表
    "required_fields": list[str], # 可选：必填字段列表
    "context": dict | None        # 可选：上下文信息
}
```

**Coordinator 验证规则**:
- `question` 不能为空
- 如果提供 `options`，列表不能为空
- `required_fields` 中的字段名必须合法

**示例**:
```python
payload = {
    "action_type": "request_clarification",
    "question": "您想分析哪个数据源？",
    "options": [
        "销售数据库",
        "用户行为日志",
        "财务报表",
        "其他（请说明）"
    ],
    "required_fields": ["data_source", "time_range"],
    "context": {
        "partial_intent": "data_analysis",
        "missing_info": ["data_source", "analysis_type"]
    }
}
```

---

### 场景 6: 继续推理

**用户输入**: （内部决策）需要更多思考

**场景特征**:
- Agent 内部状态
- 继续 ReAct 循环
- 不需要外部交互

**决策类型**: `CONTINUE`

**Payload Schema**:
```python
{
    "action_type": "continue",
    "thought": str,               # 必填：当前思考内容
    "next_step": str | None,      # 可选：下一步计划
    "progress": float             # 可选：进度（0-1）
}
```

**Coordinator 验证规则**:
- `thought` 不能为空
- `progress` 范围 0-1
- 不需要发布到外部

**示例**:
```python
payload = {
    "action_type": "continue",
    "thought": "用户需要分析销售数据，我需要先确定数据的时间范围和分析维度",
    "next_step": "询问用户时间范围",
    "progress": 0.3
}
```

---

### 场景 7: 修改节点

**用户输入**: "把LLM的温度参数调整为 0.9"

**场景特征**:
- 工作流已创建
- 需要修改某个节点配置
- 不需要重新规划

**决策类型**: `MODIFY_NODE`

**Payload Schema**:
```python
{
    "action_type": "modify_node",
    "node_id": str,               # 必填：节点ID
    "updates": dict,              # 必填：更新内容
    "reason": str | None          # 可选：修改原因
}
```

**Coordinator 验证规则**:
- `node_id` 必须存在
- `updates` 不能为空
- `updates` 中的字段必须是节点配置的有效字段
- 修改后的配置必须仍然合法

**示例**:
```python
payload = {
    "action_type": "modify_node",
    "node_id": "node_2",
    "updates": {
        "config.temperature": 0.9,
        "config.max_tokens": 2000
    },
    "reason": "用户要求提高创造性并增加输出长度"
}
```

---

### 场景 8: 错误恢复

**用户输入**: （系统触发）"节点执行失败，API 超时"

**场景特征**:
- 工作流执行失败
- 需要决定恢复策略
- 可能需要重试、跳过或调整

**决策类型**: `ERROR_RECOVERY`

**Payload Schema**:
```python
{
    "action_type": "error_recovery",
    "workflow_id": str,           # 必填：工作流ID
    "failed_node_id": str,        # 必填：失败节点ID
    "failure_reason": str,        # 必填：失败原因
    "error_code": str | None,     # 可选：错误代码
    "recovery_plan": dict,        # 必填：恢复计划
    "execution_context": dict     # 必填：执行上下文
}
```

**Recovery Plan Schema**:
```python
{
    "action": str,                # 必填：RETRY/SKIP/ABORT/MODIFY
    "delay": float | None,        # 可选：重试延迟（秒）
    "max_attempts": int | None,   # 可选：最大重试次数
    "modifications": dict | None, # 可选：节点修改
    "alternative_node": str | None# 可选：替代节点
}
```

**Coordinator 验证规则**:
- `workflow_id` 和 `failed_node_id` 必须存在
- `failure_reason` 不能为空
- `recovery_plan.action` 必须是 RETRY/SKIP/ABORT/MODIFY 之一
- 如果 action=RETRY，必须提供 max_attempts
- 如果 action=MODIFY，必须提供 modifications

**示例**:
```python
payload = {
    "action_type": "error_recovery",
    "workflow_id": "workflow_123",
    "failed_node_id": "node_1",
    "failure_reason": "HTTP request timeout after 30s",
    "error_code": "TIMEOUT",
    "recovery_plan": {
        "action": "RETRY",
        "delay": 5.0,
        "max_attempts": 3,
        "modifications": {
            "config.timeout": 60
        }
    },
    "execution_context": {
        "executed_nodes": ["node_1"],
        "node_outputs": {},
        "retry_count": 1
    }
}
```

---

### 场景 9: 重新规划工作流

**用户输入**: （系统触发）"当前方案不可行，需要调整"

**场景特征**:
- 工作流执行多次失败
- 需要重新设计流程
- 可能需要添加/删除节点

**决策类型**: `REPLAN_WORKFLOW`

**Payload Schema**:
```python
{
    "action_type": "replan_workflow",
    "workflow_id": str,           # 必填：原工作流ID
    "reason": str,                # 必填：重新规划原因
    "execution_context": dict,    # 必填：执行上下文
    "suggested_changes": dict | None, # 可选：建议的修改
    "preserve_nodes": list[str] | None # 可选：保留的节点
}
```

**Coordinator 验证规则**:
- `workflow_id` 必须存在
- `reason` 不能为空
- `execution_context` 必须包含失败信息
- 如果提供 `preserve_nodes`，节点必须存在

**示例**:
```python
payload = {
    "action_type": "replan_workflow",
    "workflow_id": "workflow_123",
    "reason": "API节点持续超时，建议改用备用数据源",
    "execution_context": {
        "executed_nodes": ["node_1", "node_2"],
        "node_outputs": {
            "node_1": {"status": "failed", "error": "timeout"}
        },
        "failed_attempts": 3
    },
    "suggested_changes": {
        "remove_nodes": ["node_1"],
        "add_nodes": [
            {
                "type": "DATABASE",
                "name": "从本地数据库获取数据",
                "config": {"query": "..."}
            }
        ],
        "update_edges": [
            {"source": "node_0", "target": "node_2"}
        ]
    },
    "preserve_nodes": ["node_2", "node_3", "node_4"]
}
```

---

### 场景 10: 生成子 Agent

**用户输入**: "帮我搜索最新的机器学习论文"

**场景特征**:
- 需要专门的能力（如搜索、编程、分析）
- 子任务相对独立
- 需要等待子 Agent 完成

**决策类型**: `SPAWN_SUBAGENT`

**Payload Schema**:
```python
{
    "action_type": "spawn_subagent",
    "subagent_type": str,         # 必填：子Agent类型
    "task_payload": dict,         # 必填：子任务载荷
    "priority": int,              # 可选：优先级（0-10）
    "timeout": float | None,      # 可选：超时时间（秒）
    "context_snapshot": dict | None # 可选：上下文快照
}
```

**Coordinator 验证规则**:
- `subagent_type` 必须在已注册的类型中
- `task_payload` 必须符合子 Agent 的输入要求
- `priority` 范围 0-10
- `timeout` 必须 > 0

**示例**:
```python
payload = {
    "action_type": "spawn_subagent",
    "subagent_type": "researcher",
    "task_payload": {
        "query": "machine learning papers 2024",
        "sources": ["arxiv", "google_scholar"],
        "max_results": 10,
        "filters": {
            "year": ">=2024",
            "citations": ">=10"
        }
    },
    "priority": 8,
    "timeout": 120.0,
    "context_snapshot": {
        "conversation_history": [...],
        "current_goal": "研究最新ML技术",
        "session_id": "session_001"
    }
}
```

---

## 3. Coordinator 通用验证规则

### 3.1 强制规则（所有决策）

1. **Payload 必须包含 `action_type`**
   - 值必须与 DecisionType 匹配

2. **禁止危险操作**
   - 不允许任意代码执行（除非在沙箱中）
   - 不允许访问敏感环境变量
   - 不允许修改系统文件

3. **资源限制**
   - 单个节点执行时间 ≤ 300s
   - 工作流总节点数 ≤ 50
   - payload 大小 ≤ 1MB

### 3.2 可选规则（可配置）

1. **节点类型白名单**
   - 默认允许：LLM, HTTP, PYTHON, DATABASE
   - 可配置禁用某些类型

2. **API 调用限制**
   - 限制外部 API 域名
   - 限制请求频率

3. **成本控制**
   - LLM 节点 token 限制
   - API 调用次数限制

### 3.3 修正规则（Correction）

如果决策不合法但可修正，Coordinator 可以：
1. 添加缺失的必填字段（使用默认值）
2. 修正超出范围的参数
3. 移除不支持的字段

修正后重新验证，如果仍然失败则拒绝。

---

## 4. 决策类型优先级与冲突解决

### 4.1 优先级排序

| 优先级 | DecisionType | 说明 |
|--------|-------------|------|
| 1 | ERROR_RECOVERY | 最高优先级，立即处理 |
| 2 | REQUEST_CLARIFICATION | 阻塞后续决策，等待用户输入 |
| 3 | REPLAN_WORKFLOW | 高优先级，影响后续执行 |
| 4 | SPAWN_SUBAGENT | 高优先级，可能需要等待 |
| 5 | EXECUTE_WORKFLOW | 正常优先级 |
| 6 | CREATE_WORKFLOW_PLAN | 正常优先级 |
| 7 | MODIFY_NODE | 正常优先级 |
| 8 | CREATE_NODE | 正常优先级 |
| 9 | RESPOND | 低优先级，直接返回 |
| 10 | CONTINUE | 内部决策，不影响外部 |

### 4.2 冲突场景

**场景**: ConversationAgent 同时产生多个决策

**解决方案**:
1. 按优先级排序
2. 高优先级决策阻塞低优先级
3. ERROR_RECOVERY 会中断当前所有决策
4. REQUEST_CLARIFICATION 会暂停当前任务，等待用户输入

---

## 5. Intent → Decision 映射规则

| Intent | 可能的 Decision | 条件 |
|--------|----------------|------|
| GREETING | RESPOND | 直接回复 |
| SIMPLE_QUERY | RESPOND | 不需要工具 |
| SIMPLE_QUERY | CREATE_NODE | 需要单个工具 |
| COMPLEX_TASK | CREATE_NODE | 单步任务 |
| COMPLEX_TASK | CREATE_WORKFLOW_PLAN | 多步任务 |
| COMPLEX_TASK | SPAWN_SUBAGENT | 需要专门能力 |
| WORKFLOW_REQUEST | EXECUTE_WORKFLOW | 工作流已存在 |
| WORKFLOW_REQUEST | CREATE_WORKFLOW_PLAN | 工作流不存在，需创建 |
| UNKNOWN | REQUEST_CLARIFICATION | 需求不明确 |

---

## 6. EventBus 事件流程

### 6.1 正常流程

```
ConversationAgent
    │ make_decision()
    ▼
DecisionMadeEvent
    │ {decision_type, payload, confidence}
    ▼
EventBus → Coordinator Middleware
    │ validate_decision(payload)
    ▼
    ├─ Valid → DecisionValidatedEvent
    │           ↓
    │       WorkflowAgent / Executor
    │
    └─ Invalid → DecisionRejectedEvent
                ↓
            ConversationAgent (retry)
```

### 6.2 错误流程

```
WorkflowAgent
    │ node execution failed
    ▼
NodeExecutionFailedEvent
    │
    ▼
CoordinatorAgent
    │ determine recovery strategy
    ▼
DecisionMadeEvent (ERROR_RECOVERY)
    │
    ▼
EventBus → Coordinator Middleware
    │ validate recovery plan
    ▼
    ├─ Valid → Execute recovery
    └─ Invalid → REPLAN_WORKFLOW
```

---

## 7. 测试用例设计指南

### 7.1 单元测试（TDD）

为每种 DecisionType 编写测试：

```python
def test_create_node_decision_with_valid_payload_should_pass_validation():
    """测试：有效的 CREATE_NODE payload 应该通过验证"""
    payload = {
        "action_type": "create_node",
        "node_type": "HTTP",
        "node_name": "获取天气",
        "config": {"url": "https://api.weather.com", "method": "GET"}
    }

    decision = Decision(type=DecisionType.CREATE_NODE, payload=payload)
    result = coordinator.validate_decision(decision)

    assert result.is_valid is True
    assert len(result.errors) == 0

def test_create_node_without_required_config_should_fail():
    """测试：缺少必填配置的 CREATE_NODE 应该失败"""
    payload = {
        "action_type": "create_node",
        "node_type": "HTTP",
        "node_name": "获取天气",
        "config": {}  # 缺少 url 和 method
    }

    decision = Decision(type=DecisionType.CREATE_NODE, payload=payload)
    result = coordinator.validate_decision(decision)

    assert result.is_valid is False
    assert "url" in result.errors[0].lower()
```

### 7.2 集成测试（EventBus）

测试完整事件流程：

```python
async def test_decision_made_event_should_trigger_validation():
    """测试：DecisionMadeEvent 应该触发 Coordinator 验证"""
    event_bus = EventBus()
    coordinator = CoordinatorAgent(event_bus=event_bus)
    event_bus.add_middleware(coordinator.as_middleware())

    received_events = []

    async def handler(event):
        received_events.append(event)

    event_bus.subscribe(DecisionValidatedEvent, handler)

    # 发布决策事件
    decision_event = DecisionMadeEvent(
        decision_type="create_node",
        payload={"action_type": "create_node", "node_type": "LLM", ...}
    )

    await event_bus.publish(decision_event)

    # 断言验证通过事件被发布
    assert len(received_events) == 1
    assert isinstance(received_events[0], DecisionValidatedEvent)
```

---

## 8. 文档维护说明

### 8.1 更新时机

- 新增 DecisionType 时，必须添加对应场景
- 修改 payload schema 时，必须更新示例
- 修改验证规则时，必须更新测试用例

### 8.2 版本控制

- 每次重大修改增加版本号
- 保留历史版本的兼容性说明
- 记录 breaking changes

---

**文档状态**: ✅ 已完成
**下一步**: 实现 Pydantic Schema + TDD 测试
