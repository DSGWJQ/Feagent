# 协调者（Coordinator）增强设计文档

> 版本：1.0
> 日期：2025-12-02
> 阶段：Phase 7 - 协调者核心能力增强

---

## 一、概述

### 1.1 业务背景

协调者（Coordinator）是多Agent协作系统的"守门人"，负责：
1. **规则管理**：维护完整的规则库，定义Agent行为边界
2. **流程监控**：维护工作流执行上下文，监控节点状态变更

### 1.2 核心职责

```
┌─────────────────────────────────────────────────────────────┐
│                     协调者核心职责                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐          ┌─────────────────┐          │
│  │   规则管理       │          │   流程监控       │          │
│  ├─────────────────┤          ├─────────────────┤          │
│  │ • 行为边界规则   │          │ • 已执行节点     │          │
│  │ • 工具使用约束   │          │ • 正在执行任务   │          │
│  │ • 数据访问权限   │          │ • 节点输入输出   │          │
│  │ • 执行策略规则   │          │ • 错误日志       │          │
│  │ • 目标对齐检测   │          │ • 执行指标       │          │
│  └─────────────────┘          └─────────────────┘          │
│           │                            │                    │
│           ▼                            ▼                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              决策验证与错误处理                       │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ • 拦截对话Agent的Action方案                          │   │
│  │ • 规则引擎匹配验证                                    │   │
│  │ • 批准/修正/拒绝决策                                  │   │
│  │ • 错误处理策略（重试/跳过/反馈/升级）                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、规则管理详细设计

### 2.1 规则分类

| 类别 | 说明 | 示例 |
|------|------|------|
| BEHAVIOR | 行为边界规则 | 最大迭代次数、Token预算 |
| TOOL | 工具使用约束 | 允许的工具列表、参数范围 |
| DATA | 数据访问权限 | 敏感字段过滤、查询限制 |
| EXECUTION | 执行策略规则 | 超时设置、并发限制 |
| GOAL | 目标对齐检测 | 偏离检测、相关性评分 |

### 2.2 规则来源

```
┌─────────────────────────────────────────────────────────────┐
│                       规则来源                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 用户输入（动态生成）                                      │
│     ├─ 起点（start）: "我有一份销售数据Excel"                 │
│     ├─ 终点（goal）: "生成月度销售分析报表"                   │
│     └─ 描述: "数据包含客户姓名，需要脱敏处理"                  │
│         │                                                   │
│         ▼                                                   │
│     RuleGenerator.generate_goal_rules()                     │
│         │                                                   │
│         ▼                                                   │
│     生成规则:                                                │
│     • goal_alignment: 检测是否偏离"销售分析"目标              │
│     • data_privacy: 客户姓名字段需脱敏                       │
│     • output_format: 输出必须是报表格式                      │
│                                                             │
│  2. 系统预设（静态规则）                                      │
│     ├─ max_iterations: 最大迭代10次                          │
│     ├─ token_budget: 单次任务最多10000 token                 │
│     ├─ timeout: 单节点执行超时60秒                           │
│     └─ circuit_breaker: 连续失败5次触发熔断                  │
│                                                             │
│  3. 工具配置（从工具注册信息生成）                            │
│     ├─ allowed_tools: ["database", "python", "http"]        │
│     ├─ tool_params: database.sql 不允许 DROP/DELETE         │
│     └─ rate_limit: http 每分钟最多10次请求                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 规则数据结构

```python
@dataclass
class EnhancedRule:
    """增强规则定义"""
    id: str                          # 规则唯一标识
    name: str                        # 规则名称
    category: RuleCategory           # 规则类别
    description: str                 # 规则描述
    condition: str | Callable        # 条件（表达式或函数）
    action: RuleAction               # 触发动作
    priority: int                    # 优先级（越小越高）
    enabled: bool                    # 是否启用
    source: RuleSource               # 来源（USER/SYSTEM/TOOL）
    metadata: dict                   # 元数据（用于修正建议）

class RuleCategory(Enum):
    BEHAVIOR = "behavior"
    TOOL = "tool"
    DATA = "data"
    EXECUTION = "execution"
    GOAL = "goal"

class RuleSource(Enum):
    USER = "user"          # 用户定义
    SYSTEM = "system"      # 系统预设
    TOOL = "tool"          # 工具配置
    GENERATED = "generated" # 动态生成
```

### 2.4 规则生成器

```python
class RuleGenerator:
    """从用户输入动态生成规则"""

    def generate_from_user_input(
        self,
        start: str,
        goal: str,
        description: str | None = None,
        constraints: dict | None = None
    ) -> list[EnhancedRule]:
        """
        从用户的起点/终点/描述生成规则

        示例输入:
            start: "我有一份包含客户信息的Excel"
            goal: "生成销售分析报表"
            description: "客户姓名需要脱敏，只看本月数据"

        生成规则:
            1. GoalAlignmentRule: 检测是否与"销售分析"相关
            2. DataPrivacyRule: 客户姓名字段脱敏
            3. DataFilterRule: 时间范围限制为本月
        """
        pass

    def generate_tool_rules(
        self,
        allowed_tools: list[str],
        tool_configs: dict | None = None
    ) -> list[EnhancedRule]:
        """生成工具约束规则"""
        pass
```

---

## 三、流程监控详细设计

### 3.1 执行上下文

```python
@dataclass
class ExecutionContext:
    """工作流执行上下文"""

    workflow_id: str
    started_at: datetime

    # 节点执行状态
    executed_nodes: list[str]           # 已完成节点
    running_nodes: list[str]            # 执行中节点
    pending_nodes: list[str]            # 待执行节点
    failed_nodes: list[str]             # 失败节点
    skipped_nodes: list[str]            # 跳过节点

    # 数据流
    node_inputs: dict[str, dict]        # 节点输入
    node_outputs: dict[str, dict]       # 节点输出

    # 错误记录
    error_log: list[ErrorEntry]

    # 执行指标
    metrics: ExecutionMetrics

@dataclass
class ErrorEntry:
    """错误记录"""
    node_id: str
    error_type: str
    error_message: str
    timestamp: datetime
    attempt: int                        # 第几次尝试
    action_taken: ErrorHandlingAction   # 采取的处理动作

@dataclass
class ExecutionMetrics:
    """执行指标"""
    total_nodes: int
    completed_nodes: int
    failed_nodes: int
    total_time_ms: int
    total_tokens: int
    total_cost: float
```

### 3.2 状态变更事件

```
节点执行生命周期:

    ┌──────────┐
    │ PENDING  │ ◄─── 初始状态
    └────┬─────┘
         │ on_node_start()
         ▼
    ┌──────────┐
    │ RUNNING  │ ◄─── 执行中
    └────┬─────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌──────┐  ┌──────┐
│COMPLETED│  │FAILED│
└──────┘  └──┬───┘
              │
         错误处理策略
              │
    ┌─────────┼─────────┬─────────┐
    ▼         ▼         ▼         ▼
  RETRY     SKIP    FEEDBACK  ESCALATE
    │         │         │         │
    ▼         ▼         ▼         ▼
 重新执行   标记跳过  通知Agent  人工介入
```

### 3.3 执行监控器

```python
class ExecutionMonitor:
    """执行监控器"""

    def __init__(self, coordinator: CoordinatorAgent):
        self.coordinator = coordinator
        self.contexts: dict[str, ExecutionContext] = {}
        self.error_handler: ErrorHandler = None

    async def on_workflow_start(
        self,
        workflow_id: str,
        node_ids: list[str]
    ) -> None:
        """工作流开始"""
        pass

    async def on_node_start(
        self,
        workflow_id: str,
        node_id: str,
        inputs: dict
    ) -> None:
        """节点开始执行"""
        pass

    async def on_node_complete(
        self,
        workflow_id: str,
        node_id: str,
        outputs: dict
    ) -> None:
        """节点执行完成"""
        pass

    async def on_node_error(
        self,
        workflow_id: str,
        node_id: str,
        error: Exception
    ) -> ErrorHandlingAction:
        """节点执行错误 - 返回处理动作"""
        pass

    def get_context(self, workflow_id: str) -> ExecutionContext | None:
        """获取执行上下文"""
        pass
```

---

## 四、决策验证流程

### 4.1 验证流程

```
对话Agent                协调者                    工作流Agent
    │                      │                          │
    │  DecisionRequest     │                          │
    │─────────────────────►│                          │
    │                      │                          │
    │                      │ 1. 规则引擎匹配           │
    │                      │    ├─ 行为边界检查        │
    │                      │    ├─ 工具权限检查        │
    │                      │    ├─ 数据访问检查        │
    │                      │    └─ 目标对齐检查        │
    │                      │                          │
    │                      │ 2. 生成验证结果           │
    │                      │                          │
    │  ValidationResult    │                          │
    │◄─────────────────────│                          │
    │                      │                          │
    │  [if APPROVED/MODIFIED]                         │
    │                      │  ExecuteDecision         │
    │                      │─────────────────────────►│
    │                      │                          │
    │  [if REJECTED]       │                          │
    │  重新规划             │                          │
    │                      │                          │
```

### 4.2 验证结果

```python
class ValidationStatus(Enum):
    APPROVED = "approved"       # 批准执行
    MODIFIED = "modified"       # 修正后批准
    REJECTED = "rejected"       # 拒绝
    ESCALATED = "escalated"     # 升级处理

@dataclass
class DecisionRequest:
    """决策请求"""
    decision_id: str
    decision_type: str          # create_node, execute_workflow, etc.
    payload: dict               # 决策内容
    context: dict               # 当前上下文
    requester: str              # 请求者标识

@dataclass
class ValidationResult:
    """验证结果"""
    status: ValidationStatus
    original_request: DecisionRequest
    modified_payload: dict | None    # 修正后的决策（仅MODIFIED时有值）
    violations: list[RuleViolation]  # 违规列表
    suggestions: list[str]           # 纠偏建议
    timestamp: datetime
```

### 4.3 决策验证器

```python
class DecisionValidator:
    """决策验证器"""

    def __init__(
        self,
        rule_repository: EnhancedRuleRepository,
        goal_checker: GoalAlignmentChecker
    ):
        self.rule_repository = rule_repository
        self.goal_checker = goal_checker

    def validate(self, request: DecisionRequest) -> ValidationResult:
        """
        验证决策

        流程:
        1. 获取适用的规则（按类别和优先级）
        2. 逐条检查规则
        3. 收集违规信息
        4. 尝试自动修正
        5. 生成验证结果
        """
        pass

    def _check_behavior_rules(self, request: DecisionRequest) -> list[RuleViolation]:
        """检查行为边界规则"""
        pass

    def _check_tool_rules(self, request: DecisionRequest) -> list[RuleViolation]:
        """检查工具使用规则"""
        pass

    def _check_data_rules(self, request: DecisionRequest) -> list[RuleViolation]:
        """检查数据访问规则"""
        pass

    def _check_goal_alignment(self, request: DecisionRequest) -> list[RuleViolation]:
        """检查目标对齐"""
        pass

    def _try_auto_correct(
        self,
        request: DecisionRequest,
        violations: list[RuleViolation]
    ) -> dict | None:
        """尝试自动修正决策"""
        pass
```

---

## 五、错误处理策略

### 5.1 处理动作

| 动作 | 说明 | 触发条件 |
|------|------|----------|
| RETRY | 重试执行 | 临时错误（网络、超时） |
| SKIP | 跳过节点 | 可选节点、非关键错误 |
| FEEDBACK | 反馈Agent | 需要重新规划 |
| ESCALATE | 升级处理 | 严重错误、需人工介入 |
| ABORT | 终止工作流 | 致命错误 |

### 5.2 错误处理策略

```python
@dataclass
class ErrorHandlingPolicy:
    """错误处理策略配置"""

    # 重试配置
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    backoff_factor: float = 2.0         # 指数退避因子

    # 可跳过的节点类型
    skippable_node_types: list[str] = field(default_factory=list)

    # 反馈阈值
    feedback_after_retries: int = 2     # 重试N次后反馈Agent

    # 可重试的错误类型
    retryable_errors: list[str] = field(default_factory=lambda: [
        "TimeoutError",
        "ConnectionError",
        "RateLimitError"
    ])

class ErrorHandler:
    """错误处理器"""

    def __init__(self, policy: ErrorHandlingPolicy):
        self.policy = policy
        self.retry_counts: dict[str, int] = {}  # node_id -> retry_count

    def determine_action(
        self,
        node_id: str,
        node_type: str,
        error: Exception,
        context: ExecutionContext
    ) -> ErrorHandlingAction:
        """
        确定错误处理动作

        决策逻辑:
        1. 如果是可重试错误且未超过重试次数 -> RETRY
        2. 如果重试次数达到feedback阈值 -> FEEDBACK
        3. 如果是可跳过节点 -> SKIP
        4. 如果是严重错误 -> ESCALATE
        5. 其他情况 -> ABORT
        """
        pass

    def create_retry_context(
        self,
        node_id: str,
        attempt: int
    ) -> dict:
        """创建重试上下文（包含延迟时间）"""
        pass

    def create_feedback_message(
        self,
        node_id: str,
        error: Exception,
        context: ExecutionContext
    ) -> dict:
        """
        创建反馈给对话Agent的消息

        消息格式:
        {
            "type": "execution_error",
            "node_id": "node_123",
            "error": "数据库连接超时",
            "context": {
                "executed_nodes": [...],
                "current_outputs": {...}
            },
            "suggestion": "请考虑使用缓存数据或调整查询条件"
        }
        """
        pass
```

---

## 六、实现阶段

### Phase 7.1: 规则库增强
- `EnhancedRule`, `RuleCategory`, `RuleSource` 数据类
- `EnhancedRuleRepository` 规则存储
- `RuleGenerator` 规则生成器
- `GoalAlignmentChecker` 目标对齐检测

### Phase 7.2: 决策验证流程
- `DecisionRequest`, `ValidationResult` 数据类
- `ValidationStatus` 枚举
- `DecisionValidator` 验证器
- 与CoordinatorAgent集成

### Phase 7.3: 执行监控增强
- `ExecutionContext`, `ErrorEntry`, `ExecutionMetrics` 数据类
- `ExecutionMonitor` 监控器
- 事件订阅与状态更新

### Phase 7.4: 错误处理策略
- `ErrorHandlingPolicy` 策略配置
- `ErrorHandlingAction` 动作枚举
- `ErrorHandler` 处理器
- 重试逻辑（指数退避）
- 反馈消息生成

### Phase 7.5: 集成测试
- 端到端场景测试
- 真实LLM集成测试
- 性能测试

---

## 七、测试用例设计

### 7.1 规则库测试

```python
# test_enhanced_rule_repository.py

def test_add_rule_should_store_by_category():
    """添加规则应按类别存储"""

def test_get_rules_by_category_should_return_sorted_by_priority():
    """按类别获取规则应按优先级排序"""

def test_rule_generator_should_create_goal_rules_from_user_input():
    """规则生成器应从用户输入创建目标规则"""

def test_goal_alignment_checker_should_detect_deviation():
    """目标对齐检测器应检测偏离"""
```

### 7.2 决策验证测试

```python
# test_decision_validator.py

def test_validate_should_approve_valid_decision():
    """验证应批准有效决策"""

def test_validate_should_reject_tool_not_allowed():
    """验证应拒绝未授权的工具"""

def test_validate_should_modify_sensitive_data_query():
    """验证应修正敏感数据查询"""

def test_validate_should_reject_goal_deviation():
    """验证应拒绝偏离目标的决策"""
```

### 7.3 执行监控测试

```python
# test_execution_monitor.py

def test_on_node_start_should_update_context():
    """节点开始应更新上下文"""

def test_on_node_complete_should_record_output():
    """节点完成应记录输出"""

def test_on_node_error_should_trigger_error_handler():
    """节点错误应触发错误处理器"""
```

### 7.4 错误处理测试

```python
# test_error_handler.py

def test_should_retry_on_timeout_error():
    """超时错误应重试"""

def test_should_skip_optional_node():
    """可选节点应跳过"""

def test_should_feedback_after_max_retries():
    """达到最大重试次数后应反馈Agent"""

def test_retry_delay_should_use_exponential_backoff():
    """重试延迟应使用指数退避"""
```

### 7.5 集成测试

```python
# test_coordinator_integration.py

async def test_full_workflow_with_rule_validation():
    """完整工作流应通过规则验证"""

async def test_workflow_with_error_retry_and_recovery():
    """工作流错误应重试并恢复"""

async def test_workflow_with_feedback_to_agent():
    """工作流失败应反馈给Agent重新规划"""
```

---

## 八、API设计

### 8.1 协调者状态API

```
GET /api/coordinator/status
响应:
{
    "decision_statistics": {
        "total": 100,
        "approved": 85,
        "modified": 10,
        "rejected": 5
    },
    "active_workflows": 3,
    "circuit_breaker_state": "closed"
}

GET /api/coordinator/rules
响应:
{
    "rules": [
        {
            "id": "rule_1",
            "name": "最大迭代次数",
            "category": "behavior",
            "enabled": true
        }
    ]
}

GET /api/coordinator/workflow/{workflow_id}/context
响应:
{
    "workflow_id": "wf_123",
    "status": "running",
    "executed_nodes": ["node_1", "node_2"],
    "running_nodes": ["node_3"],
    "metrics": {
        "total_time_ms": 5000,
        "total_tokens": 1500
    }
}
```

---

## 九、文件结构

```
src/domain/
├── agents/
│   └── coordinator_agent.py      # 增强现有协调者
├── services/
│   ├── rule_engine.py            # 现有规则引擎
│   ├── enhanced_rule_repository.py  # 新增：增强规则库
│   ├── rule_generator.py         # 新增：规则生成器
│   ├── goal_alignment_checker.py # 新增：目标对齐检测
│   ├── decision_validator.py     # 新增：决策验证器
│   ├── execution_monitor.py      # 新增：执行监控器
│   └── error_handler.py          # 新增：错误处理器

tests/unit/domain/services/
├── test_enhanced_rule_repository.py
├── test_rule_generator.py
├── test_goal_alignment_checker.py
├── test_decision_validator.py
├── test_execution_monitor.py
└── test_error_handler.py

tests/integration/
└── test_coordinator_integration.py
```

---

## 十、依赖关系

```
                    ┌─────────────────────┐
                    │  CoordinatorAgent   │
                    │     (增强)          │
                    └─────────┬───────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌─────────────────┐   ┌─────────────────┐
│DecisionValidator│   │ExecutionMonitor│   │  ErrorHandler   │
└───────┬───────┘   └────────┬────────┘   └────────┬────────┘
        │                    │                     │
        ▼                    │                     │
┌───────────────────┐        │                     │
│EnhancedRuleRepository│◄────┴─────────────────────┘
└───────┬───────────┘
        │
        ▼
┌───────────────┐   ┌─────────────────────┐
│ RuleGenerator │   │ GoalAlignmentChecker│
└───────────────┘   └─────────────────────┘
```

---

**文档版本历史**

| 版本 | 日期 | 修改内容 |
|------|------|----------|
| 1.0 | 2025-12-02 | 初始版本 |
