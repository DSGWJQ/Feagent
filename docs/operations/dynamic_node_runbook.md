# 动态节点运维 Runbook

## 概述

本 Runbook 覆盖动态节点的完整生命周期管理，包括：需求识别 → 节点生成 → 沙箱验证 → 接入工作流 → 监控 → 回滚。

---

## 1. 动态节点生命周期

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  需求识别   │ ──> │  节点生成   │ ──> │  沙箱验证   │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               v
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    回滚     │ <── │    监控     │ <── │ 接入工作流  │
└─────────────┘     └─────────────┘     └─────────────┘
```

---

## 2. 需求识别

### 2.1 触发条件

- 用户自然语言描述新功能需求
- CoordinatorAgent 规则引擎触发 `NeedsDynamicNode` 决策
- 现有节点无法满足功能需求

### 2.2 检查项

| 检查项 | 说明 | 通过条件 |
|--------|------|----------|
| 需求完整性 | 用户需求描述是否包含输入/输出定义 | 有明确的输入输出描述 |
| 功能边界 | 需求是否可用单个节点实现 | 功能范围清晰可控 |
| 安全评估 | 需求是否需要敏感权限 | 不涉及文件系统、网络外部访问 |

### 2.3 命令

```python
from src.domain.agents.coordinator_agent import CoordinatorAgent

coordinator = CoordinatorAgent()
decision = await coordinator.make_decision({
    "user_request": "需要一个计算销售增长率的节点",
    "context": workflow_context
})

print(decision.action)  # 'create_dynamic_node' or 'use_existing'
```

---

## 3. 节点生成

### 3.1 前置条件

- CoordinatorAgent 决策为 `create_dynamic_node`
- ConversationAgent 已提取节点元数据

### 3.2 生成流程

```python
from src.domain.services.self_describing_node import YamlNodeLoader, SelfDescribingNodeExecutor

# 1. 加载 YAML 定义
loader = YamlNodeLoader(definitions_path="definitions/nodes/")
node_def = loader.load("sales_growth_calculator")

# 2. 验证定义
from src.domain.services.self_describing_node_validator import SelfDescribingNodeValidator
validator = SelfDescribingNodeValidator()
result = validator.validate_with_logging(node_def)

if not result.valid:
    print(f"验证失败: {result.errors}")
    # 触发回滚流程
```

### 3.3 检查项

| 检查项 | 说明 | 通过条件 |
|--------|------|----------|
| 必需字段 | name, version, executor_type | 全部存在 |
| 输入对齐 | 输入参数与预期匹配 | 类型和必需性匹配 |
| 沙箱许可 | executor_type 是否需要沙箱 | code 类型必须启用沙箱 |

---

## 4. 沙箱验证

### 4.1 验证目的

- 确保代码不会造成系统损害
- 验证输入/输出格式正确
- 检测运行时错误

### 4.2 执行沙箱测试

```python
from src.domain.services.sandbox_executor import PythonSandbox

sandbox = PythonSandbox(timeout_seconds=30)

# 使用测试数据执行
test_input = {"sales_current": 100, "sales_previous": 80}
result = sandbox.execute(
    code=node_def.code,
    input_data=test_input
)

if not result.success:
    print(f"沙箱执行失败: {result.error}")
    # 记录指标并回滚
```

### 4.3 检查项

| 检查项 | 说明 | 通过条件 |
|--------|------|----------|
| 执行成功 | 代码无运行时错误 | exit_code == 0 |
| 超时检查 | 执行时间在限制内 | < 30 秒 |
| 输出格式 | 输出符合预期 schema | 可解析为预期类型 |
| 资源限制 | 内存使用在限制内 | < 100MB |

---

## 5. 接入工作流

### 5.1 依赖图更新

```python
from src.domain.services.workflow_dependency_graph import (
    DependencyGraphBuilder,
    WorkflowDependencyExecutor
)

# 1. 构建依赖图
builder = DependencyGraphBuilder()
edges = builder.create_edges(workflow.nodes)

# 2. 验证无循环依赖
executor = WorkflowDependencyExecutor(builder=builder)
try:
    sorted_nodes = builder.topological_sort(workflow.nodes, edges)
except ValueError as e:
    print(f"循环依赖检测: {e}")
    # 回滚
```

### 5.2 自动连接

```python
# 解析输入引用
for node in workflow.nodes:
    refs = builder.parse_input_references(node.definition)
    for param, source in refs.items():
        print(f"节点 {node.name} 参数 {param} 依赖 {source}")
```

### 5.3 检查项

| 检查项 | 说明 | 通过条件 |
|--------|------|----------|
| DAG 有效性 | 无循环依赖 | 拓扑排序成功 |
| 引用完整 | 所有输入引用可解析 | 无未解析的引用 |
| 类型兼容 | 输入/输出类型匹配 | 类型一致或可转换 |

---

## 6. 监控指标

### 6.1 核心指标

```python
from src.domain.services.dynamic_node_monitoring import DynamicNodeMetricsCollector

metrics = DynamicNodeMetricsCollector()

# 获取统计信息
stats = metrics.get_statistics()
print(f"节点创建总数: {stats['total_creations']}")
print(f"沙箱失败率: {stats['sandbox_failure_rate']:.2%}")
print(f"工作流执行成功: {stats['workflow_successes']}")
```

### 6.2 Prometheus 指标导出

```python
# 导出 Prometheus 格式
prometheus_output = metrics.export_prometheus()

# 示例输出:
# dynamic_node_creations_total{status="success"} 42
# dynamic_node_creations_total{status="failure"} 3
# sandbox_executions_total{status="success"} 156
# sandbox_failure_rate 0.0345
```

### 6.3 指标阈值

| 指标名称 | 正常范围 | 警告阈值 | 严重阈值 |
|----------|----------|----------|----------|
| sandbox_failure_rate | < 5% | 5-20% | > 20% |
| node_creation_failure_rate | < 2% | 2-10% | > 10% |
| workflow_execution_time_avg | < 5s | 5-30s | > 30s |
| workflow_failure_rate | < 1% | 1-5% | > 5% |

### 6.4 告警配置

```python
from src.domain.services.dynamic_node_monitoring import AlertManager

alert_manager = AlertManager()

# 设置阈值
alert_manager.set_threshold("sandbox_failure_rate", 0.2)  # 20%

# 设置通知回调
def send_alert(alert):
    print(f"[{alert.severity}] {alert.message}")
    # 发送到钉钉/Slack/邮件等

alert_manager.set_notification_callback(send_alert)

# 检查并触发告警
alert_manager.check_failure_rate(metrics.get_sandbox_failure_rate())
```

---

## 7. 回滚流程

### 7.1 回滚触发条件

- 沙箱验证失败
- 工作流执行失败
- 节点创建异常
- 手动回滚请求

### 7.2 快照与回滚

```python
from src.domain.services.dynamic_node_monitoring import WorkflowRollbackManager

rollback = WorkflowRollbackManager()

# 1. 变更前创建快照
snapshot_id = rollback.create_snapshot(
    workflow_id="sales_pipeline",
    state=current_workflow_state,
    reason="添加 sales_growth_calculator 节点"
)

# 2. 执行变更...

# 3. 如果失败，执行回滚
if operation_failed:
    restored_state = rollback.rollback("sales_pipeline")
    print("工作流已回滚到变更前状态")
```

### 7.3 删除无效节点

```python
# 清理无效节点和相关边
cleaned_state = rollback.remove_invalid_nodes(workflow_state)
```

### 7.4 回滚检查项

| 检查项 | 说明 | 验证方法 |
|--------|------|----------|
| 快照存在 | 有可用的回滚点 | `rollback.has_snapshot(workflow_id)` |
| 状态恢复 | 工作流恢复到正常状态 | 比较节点数量和边 |
| 边清理 | 无效边已删除 | 检查边的 source/target |
| 指标记录 | 回滚事件已记录 | 检查 metrics |

---

## 8. 健康检查

### 8.1 系统健康检查

```python
from src.domain.services.dynamic_node_monitoring import HealthChecker

health = HealthChecker()

# 整体健康状态
status = health.check_health()
print(f"系统状态: {status['status']}")  # healthy/degraded/unhealthy

# 组件健康
for component, info in status['components'].items():
    print(f"  {component}: {info}")
```

### 8.2 健康检查端点

```python
# API 端点实现
@app.get("/health/dynamic-nodes")
async def health_check():
    checker = HealthChecker()
    return checker.check_health()
```

### 8.3 健康状态定义

| 状态 | 含义 | 处理建议 |
|------|------|----------|
| healthy | 所有组件正常 | 无需处理 |
| degraded | 部分功能受限 | 监控并准备干预 |
| unhealthy | 核心功能不可用 | 立即处理 |

---

## 9. 故障排查

### 9.1 常见问题

#### 问题 1: 节点创建失败

**症状**: `validate_node` 返回 `{"valid": False}`

**排查步骤**:
1. 检查必需字段是否完整
2. 验证 executor_type 是否有效
3. 检查输入/输出 schema 格式

**解决方案**:
```python
validator = SelfDescribingNodeValidator()
result = validator.validate_required_fields(node_def)
print(result.errors)  # 查看具体错误
```

#### 问题 2: 沙箱执行超时

**症状**: 沙箱执行时间超过 30 秒

**排查步骤**:
1. 检查代码是否有无限循环
2. 验证输入数据量是否过大
3. 检查是否有阻塞操作

**解决方案**:
```python
# 增加超时时间（临时）
sandbox = PythonSandbox(timeout_seconds=60)

# 或优化代码逻辑
```

#### 问题 3: 依赖循环检测

**症状**: `topological_sort` 抛出 ValueError

**排查步骤**:
1. 打印所有边的 source/target
2. 使用可视化工具检查图结构
3. 检查动态生成的边

**解决方案**:
```python
builder = DependencyGraphBuilder()
deps = builder.resolve_dependencies(nodes)
for node, parents in deps.items():
    print(f"{node} <- {parents}")
```

### 9.2 日志位置

| 组件 | 日志路径 | 说明 |
|------|----------|------|
| CoordinatorAgent | `logs/coordinator.log` | 决策和审批日志 |
| WorkflowAgent | `logs/workflow.log` | 执行和调度日志 |
| SandboxExecutor | `logs/sandbox.log` | 沙箱执行日志 |
| Metrics | `logs/metrics.log` | 指标收集日志 |

---

## 10. 紧急操作

### 10.1 紧急停止动态节点创建

```python
# 设置全局开关
from src.config import settings
settings.DYNAMIC_NODE_CREATION_ENABLED = False
```

### 10.2 批量回滚

```python
# 回滚最近 1 小时内创建的所有动态节点
rollback = WorkflowRollbackManager()
for workflow_id in affected_workflows:
    if rollback.has_snapshot(workflow_id):
        rollback.rollback(workflow_id)
```

### 10.3 清除所有告警

```python
alert_manager = AlertManager()
count = alert_manager.clear_all_alerts()
print(f"已清除 {count} 个告警")
```

---

## 11. 维护任务

### 11.1 定期任务

| 任务 | 频率 | 命令 |
|------|------|------|
| 清理过期快照 | 每日 | `rollback.cleanup_old_snapshots(days=7)` |
| 导出指标报告 | 每周 | `metrics.export_weekly_report()` |
| 健康检查 | 每分钟 | `health.check_health()` |
| 告警检查 | 每 5 分钟 | `alert_manager.check_all_thresholds()` |

### 11.2 容量规划

| 指标 | 当前值 | 阈值 | 扩容建议 |
|------|--------|------|----------|
| 快照存储 | - | 10GB | 增加存储或清理旧快照 |
| 指标记录数 | - | 1M | 启用时间窗口聚合 |
| 活跃工作流 | - | 1000 | 水平扩展 |

---

## 12. 联系方式

| 角色 | 联系方式 | 职责 |
|------|----------|------|
| 值班运维 | oncall@example.com | 日常运维和告警处理 |
| 平台负责人 | platform@example.com | 架构和重大变更 |
| 安全团队 | security@example.com | 沙箱安全问题 |

---

**最后更新**: 2025-12-06
**版本**: 1.0.0
