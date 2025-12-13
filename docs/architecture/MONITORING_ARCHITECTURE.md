# 监控系统架构说明 (P1-3)

**创建日期**: 2025-12-13
**状态**: Active
**最后更新**: 2025-12-13 (P1-8 清理更新)
**分析报告**: `tmp/p1_3_supervision_analysis.md`

---

## 概述

Agent_data项目包含**6个专用监控文件**，每个服务于不同的监控场景。它们按**关注点分离**原则设计，类似微服务架构中的独立服务。

**核心原则**: 不同抽象层级的监控需求，使用不同的专用监控器，而非单一通用监控系统。

**P1-8 清理结论**: 经生产代码分析，2个文件标记为deprecated（从未被集成使用），4个文件保持active。

---

## 监控文件总览

| 文件 | 场景 | 核心组件 | 生产调用 | 测试覆盖 | 状态 |
|------|------|----------|----------|----------|------|
| `dynamic_node_monitoring.py` | 动态节点生命周期 | DynamicNodeMetricsCollector<br>WorkflowRollbackManager<br>SystemRecoveryManager<br>HealthChecker<br>AlertManager | ✅ CoordinatorBootstrap | 14个测试 | ✅ Active |
| `execution_monitor.py` | 工作流执行编排 | ExecutionMonitor<br>ExecutionMetrics<br>ErrorHandlingPolicy | ❌ 未被集成 | 4个测试 | ⚠️ **DEPRECATED** |
| `container_execution_monitor.py` | 容器生命周期 | ContainerExecutionMonitor | ✅ CoordinatorBootstrap | 0个单元测试 | ✅ Active |
| `monitoring.py` | 通用监控基础设施 | MetricsCollector<br>Tracer<br>HealthChecker<br>AlertManager | ❌ 未被集成 | 0个测试 | ⚠️ **DEPRECATED** |
| `monitoring_knowledge_bridge.py` | 监控↔知识库桥接 | MonitoringKnowledgeBridge<br>AlertKnowledgeHandler | ✅ 内部依赖 | 7个测试 | ✅ Active |
| `prompt_stability_monitor.py` | 提示词稳定性 | PromptUsageLog<br>DriftDetector<br>OutputFormatValidator<br>StabilityMonitor | ⚠️ 仅E2E测试 | 1个测试 | ✅ Active |

**关键发现 (P1-8更新)**:
- ✅ 4个文件active使用（dynamic_node, container, knowledge_bridge, prompt_stability）
- ⚠️ **2个文件已标记deprecated**（execution_monitor, monitoring.py）- 从未被生产代码集成
- ❌ **无冗余** - 每个文件服务于不同监控维度

**沙箱执行监控**:
- `sandbox_executor.py:SandboxExecutionMonitor` - 沙箱执行回调（已从 ExecutionMonitor 重命名避免冲突）

---

## 详细说明

### 1. dynamic_node_monitoring.py

**场景**: 动态节点创建、沙箱执行、工作流回滚与恢复

**Phase**: 9 (动态节点监控、回滚与系统恢复)

**核心组件**:

#### 1.1 DynamicNodeMetricsCollector
监控指标收集器，跟踪动态节点的创建和执行统计。

```python
from src.domain.services.dynamic_node_monitoring import DynamicNodeMetricsCollector

collector = DynamicNodeMetricsCollector()

# 记录节点创建
collector.record_node_creation(node_name="http_node", success=True)

# 记录沙箱执行
collector.record_sandbox_execution(
    node_name="http_node",
    success=True,
    duration_ms=125.3
)

# 记录工作流执行
collector.record_workflow_execution(
    workflow_name="data_pipeline",
    success=True,
    duration_ms=5432.1,
    extra={"nodes": 5}
)

# 导出Prometheus格式指标
metrics = collector.export_prometheus()
```

**使用场景**:
- 生产监控Dashboard (Grafana + Prometheus)
- 性能分析（沙箱执行耗时趋势）
- 容量规划（节点创建频率）

---

#### 1.2 WorkflowRollbackManager
失败工作流的回滚管理器，支持快照创建与状态恢复。

```python
from src.domain.services.dynamic_node_monitoring import WorkflowRollbackManager

rollback_mgr = WorkflowRollbackManager()

# 创建快照
snapshot_id = rollback_mgr.create_snapshot(
    workflow_id="wf_123",
    state={"current_node": "node_2", "data": {...}},
    reason="Before risky operation"
)

# 回滚到快照
restored_state = rollback_mgr.rollback_to_snapshot(
    workflow_id="wf_123",
    snapshot_id=snapshot_id
)

# 清理旧快照
rollback_mgr.cleanup_old_snapshots(max_age_seconds=3600)
```

**使用场景**:
- 节点执行失败自动回滚
- 用户手动触发回滚（UI操作）
- 灾难恢复演练

---

#### 1.3 SystemRecoveryManager
系统级恢复管理器，处理崩溃重启后的状态恢复。

```python
from src.domain.services.dynamic_node_monitoring import SystemRecoveryManager

recovery_mgr = SystemRecoveryManager()

# 标记工作流为待恢复
recovery_mgr.mark_for_recovery(
    workflow_id="wf_123",
    reason="Container crashed"
)

# 系统重启后恢复
workflows = recovery_mgr.get_pending_workflows()
for wf_id in workflows:
    recovery_mgr.attempt_recovery(workflow_id=wf_id)
```

**使用场景**:
- 容器/进程崩溃后恢复未完成工作流
- 定时健康检查触发恢复
- 运维人员手动恢复

---

#### 1.4 HealthChecker
健康检查器，定期检查系统组件状态。

```python
from src.domain.services.dynamic_node_monitoring import HealthChecker

checker = HealthChecker()

# 注册健康检查
checker.register_check(
    name="database",
    check_fn=lambda: db.ping()
)

# 执行所有检查
health_status = checker.run_all_checks()  # {"database": True, ...}

# 获取不健康组件
unhealthy = checker.get_unhealthy_components()
```

**使用场景**:
- Kubernetes liveness/readiness probes
- 运维监控Dashboard
- 自动告警触发

---

#### 1.5 AlertManager
告警管理器，创建和管理系统告警。

```python
from src.domain.services.dynamic_node_monitoring import AlertManager, Alert

alert_mgr = AlertManager()

# 创建告警
alert = alert_mgr.create_alert(
    type="node_failure",
    message="Node http_node failed 3 times",
    severity="critical"
)

# 解决告警
alert_mgr.resolve_alert(alert_id=alert.id)

# 获取未解决告警
active_alerts = alert_mgr.get_active_alerts()
```

**使用场景**:
- PagerDuty/Slack通知集成
- 运维告警Dashboard
- 自动化事件响应

---

**何时使用 dynamic_node_monitoring.py**:
- ✅ 需要监控动态节点创建/执行统计
- ✅ 需要工作流回滚能力
- ✅ 需要系统崩溃后自动恢复
- ✅ 需要健康检查和告警功能
- ❌ 仅需要通用指标收集（用monitoring.py）
- ❌ 仅需要容器事件监听（用container_execution_monitor.py）

---

### 2. execution_monitor.py

> ⚠️ **DEPRECATED (2025-12-13)**: 此模块已实现但从未被生产代码集成使用。
> 当前工作流执行监控由以下组件提供：
> - `container_execution_monitor.py` - 容器执行监控 (Active)
> - `sandbox_executor.py:SandboxExecutionMonitor` - 沙箱执行回调
>
> 本模块的 ExecutionMetrics 和 ErrorHandlingPolicy 可作为未来统一执行监控的参考设计。

**场景**: 工作流执行的观察者模式监控

**Phase**: 7.3 (执行监控器)

**核心组件**:

#### 2.1 ExecutionMonitor
工作流执行上下文管理器，跟踪节点执行状态和数据流。

```python
from src.domain.services.execution_monitor import ExecutionMonitor

monitor = ExecutionMonitor()

# 工作流开始
monitor.on_workflow_start(
    workflow_id="wf_123",
    nodes=["node_1", "node_2", "node_3"]
)

# 节点开始
monitor.on_node_start(
    workflow_id="wf_123",
    node_id="node_1",
    input_data={"param": "value"}
)

# 节点完成
monitor.on_node_complete(
    workflow_id="wf_123",
    node_id="node_1",
    output_data={"result": "success"}
)

# 节点失败
monitor.on_node_error(
    workflow_id="wf_123",
    node_id="node_2",
    error="Connection timeout",
    error_type="NetworkError"
)

# 获取执行上下文
context = monitor.get_execution_context("wf_123")
print(f"Completed: {context.completed_nodes}, Failed: {context.failed_nodes}")
```

**使用场景**:
- 实时工作流执行追踪
- 调试节点输入输出数据
- 错误处理策略决策

---

#### 2.2 ErrorHandlingPolicy
错误处理策略配置，定义不同错误类型的处理方式。

```python
from src.domain.services.execution_monitor import (
    ErrorHandlingPolicy,
    ErrorHandlingAction
)

policy = ErrorHandlingPolicy(
    max_retries=3,
    retry_delay_seconds=1.0,
    backoff_factor=2.0,
    skippable_node_types=["optional_notification"],
    feedback_after_retries=2,
    retryable_errors=["NetworkError", "TimeoutError"]
)

# 应用策略
monitor = ExecutionMonitor(error_policy=policy)
```

**使用场景**:
- 配置化错误处理（不同环境不同策略）
- 特定节点类型的容错配置
- 重试/跳过/升级决策自动化

---

**何时使用 execution_monitor.py**:
- ✅ 需要观察者模式监控工作流执行
- ✅ 需要记录节点输入输出数据流
- ✅ 需要配置化错误处理策略
- ✅ 需要执行指标统计（完成率/失败率/总耗时）
- ❌ 仅需要容器级监控（用container_execution_monitor.py）
- ❌ 需要回滚能力（用dynamic_node_monitoring.py）

**⚠️ 当前状态**: 仅集成测试使用，生产调用不明确。建议评估是否启用。

---

### 3. container_execution_monitor.py

**场景**: Docker容器执行事件订阅与统计

**Phase**: 从CoordinatorAgent提取的独立服务

**核心组件**:

#### 3.1 ContainerExecutionMonitor
监听容器开始/完成/日志事件，记录工作流级别的容器执行信息。

```python
from src.domain.services.container_execution_monitor import ContainerExecutionMonitor
from src.domain.services.event_bus import EventBus

bus = EventBus()
monitor = ContainerExecutionMonitor(event_bus=bus, max_log_size=500)

# 启动监听
monitor.start_container_execution_listening()

# 容器执行完成后查询
executions = monitor.get_workflow_container_executions("wf_123")
for exec in executions:
    print(f"Container: {exec['container_id']}, Status: {exec['status']}")

# 获取单容器日志
logs = monitor.get_container_logs("container_abc")

# 统计
stats = monitor.get_container_execution_statistics()
print(f"Total: {stats['total']}, Success: {stats['success']}, Failed: {stats['failed']}")

# 停止监听
monitor.stop_container_execution_listening()
```

**事件订阅**:
- `ContainerExecutionStartedEvent`
- `ContainerExecutionCompletedEvent`
- `ContainerLogEvent`

**数据结构**:
```python
execution = {
    "container_id": "abc123",
    "workflow_id": "wf_123",
    "node_id": "http_node",
    "status": "success",  # or "failed"
    "start_time": 1234567890.0,
    "end_time": 1234567895.5,
    "duration_ms": 5500,
    "error": None  # or error message
}
```

**防内存泄漏**:
- `max_log_size=500` - 单容器日志最多保留500条
- 有界列表自动淘汰旧日志

**使用场景**:
- 容器化节点执行追踪
- Docker容器日志聚合
- 容器执行成功率统计
- 容器故障排查（查看历史日志）

**何时使用 container_execution_monitor.py**:
- ✅ 使用Docker容器执行节点
- ✅ 需要容器日志聚合展示
- ✅ 需要容器级执行统计
- ❌ 不使用容器化执行
- ❌ 需要工作流级监控（用execution_monitor.py）

---

### 4. monitoring.py

> ⚠️ **DEPRECATED (2025-12-13)**: 此模块已创建但从未被生产代码集成使用。
> 建议使用以下替代方案：
> - 动态节点监控: `dynamic_node_monitoring.py`
> - 容器执行监控: `container_execution_monitor.py`
> - 监督系统: `supervision/` 子包
>
> 此文件保留供未来参考，但不建议在新代码中使用。

**场景**: 通用监控基础设施（类似logging库）

**Phase**: 4.2 (监控)

**核心组件**:

#### 4.1 MetricsCollector
通用指标收集器，支持计数器/仪表盘/直方图。

```python
from src.domain.services.monitoring import MetricsCollector

collector = MetricsCollector()

# 计数器（Counter）
collector.increment("api_calls", labels={"endpoint": "/workflows"})
collector.increment("api_calls", value=5, labels={"endpoint": "/agents"})

# 仪表盘（Gauge）
collector.set_gauge("active_workflows", value=10)
collector.set_gauge("memory_usage_mb", value=512.5)

# 直方图（Histogram）- 记录响应时间分布
collector.observe("request_duration_ms", value=125.3)
collector.observe("request_duration_ms", value=230.1)

# 导出指标
metrics = collector.export()
# {"api_calls": {"endpoint=/workflows": 1, "endpoint=/agents": 5}, ...}
```

**使用场景**:
- Prometheus集成
- 自定义业务指标
- 性能趋势分析

---

#### 4.2 Tracer
分布式链路追踪器，记录跨组件调用路径。

```python
from src.domain.services.monitoring import Tracer

tracer = Tracer()

# 开始追踪
span_id = tracer.start_span(
    name="process_workflow",
    tags={"workflow_id": "wf_123"}
)

# 记录事件
tracer.log_event(span_id, "node_started", {"node_id": "node_1"})

# 结束追踪
tracer.end_span(span_id)

# 导出追踪数据（Jaeger格式）
traces = tracer.export_traces()
```

**使用场景**:
- Jaeger/Zipkin集成
- 多Agent调用链分析
- 性能瓶颈定位

---

#### 4.3 HealthChecker
通用健康检查器（与dynamic_node_monitoring.py的HealthChecker类似但更通用）。

#### 4.4 AlertManager
通用告警管理器（与dynamic_node_monitoring.py的AlertManager类似但更通用）。

---

**何时使用 monitoring.py**:
- ✅ 需要通用指标收集（不限于节点/容器）
- ✅ 需要分布式链路追踪
- ✅ 需要自定义业务指标
- ✅ 需要Prometheus/Jaeger集成
- ❌ 需要节点专用监控（用dynamic_node_monitoring.py）
- ❌ 需要容器专用监控（用container_execution_monitor.py）

**⚠️ 当前状态**: Grep未发现生产调用，可能是基础设施层（待启用）或未使用。

**建议**: 评估是否启用。如启用，可作为其他监控文件的底层基础（如DynamicNodeMetricsCollector内部使用MetricsCollector）。

---

### 5. monitoring_knowledge_bridge.py

**场景**: 监控系统与知识库的桥接层

**核心组件**:

#### 5.1 MonitoringKnowledgeBridge
协调器，连接监控告警与知识库写入。

```python
from src.domain.services.monitoring_knowledge_bridge import (
    MonitoringKnowledgeBridge,
    AlertKnowledgeHandler
)
from src.domain.services.dynamic_node_monitoring import AlertManager

alert_mgr = AlertManager()
knowledge_handler = AlertKnowledgeHandler(knowledge_service=...)

bridge = MonitoringKnowledgeBridge(
    alert_manager=alert_mgr,
    knowledge_handler=knowledge_handler
)

# 自动将告警写入知识库
bridge.sync_alerts_to_knowledge()

# 查询历史告警模式
patterns = bridge.get_alert_patterns(time_window_hours=24)
```

**使用场景**:
- 告警历史存档到知识库
- 告警模式分析（频繁告警节点/时间段）
- AI Agent学习历史告警处理经验

**何时使用 monitoring_knowledge_bridge.py**:
- ✅ 需要告警数据持久化到知识库
- ✅ 需要告警模式分析
- ✅ 需要AI Agent访问历史告警
- ❌ 仅需要实时告警展示（用AlertManager直接查询）

---

### 6. prompt_stability_monitor.py

**场景**: 提示词版本管理与输出格式验证

**核心组件**:

#### 6.1 PromptUsageLog
提示词使用日志记录。

```python
from src.domain.services.prompt_stability_monitor import PromptUsageLog

log = PromptUsageLog(
    session_id="session_123",
    prompt_version="v2.3.1",
    module_combination=["context", "tools", "examples"],
    scenario="workflow_planning",
    task_prompt="请帮我规划一个数据处理流程",
    expected_output_format="json"
)

# 记录实际输出
log.actual_output = '{"workflow": [...], "estimated_time": 300}'
log.output_valid = True
```

---

#### 6.2 DriftDetector
漂移检测器，识别提示词版本/模块/场景/输出格式的变化。

```python
from src.domain.services.prompt_stability_monitor import (
    DriftDetector,
    DriftType
)

detector = DriftDetector()

# 添加使用日志
detector.add_log(log1)
detector.add_log(log2)

# 检测漂移
drifts = detector.detect_drift()
for drift in drifts:
    if drift.drift_type == DriftType.VERSION:
        print(f"版本漂移: {drift.old_value} -> {drift.new_value}")
```

**漂移类型**:
- VERSION: 提示词版本变化
- MODULE: 模块组合变化
- SCENARIO: 使用场景变化
- OUTPUT_FORMAT: 输出格式变化

---

#### 6.3 OutputFormatValidator
输出格式验证器，检查LLM输出是否符合预期格式。

```python
from src.domain.services.prompt_stability_monitor import OutputFormatValidator

validator = OutputFormatValidator()

# JSON格式验证
validation = validator.validate_json_output(
    output='{"workflow": [...]}',
    required_fields=["workflow", "estimated_time"],
    max_depth=5,
    max_size_kb=50
)

if not validation.passed:
    for error in validation.errors:
        print(f"{error.error_type}: {error.message}")
```

---

#### 6.4 StabilityMonitor
稳定性监控器，生成提示词稳定性报表。

```python
from src.domain.services.prompt_stability_monitor import StabilityMonitor

monitor = StabilityMonitor()

# 添加使用日志
monitor.add_usage_log(log)

# 生成报表
report = monitor.generate_stability_report(session_id="session_123")
print(f"稳定性状态: {report.status}")  # STABLE/DEGRADED/UNSTABLE
print(f"格式错误率: {report.format_error_rate}")
print(f"漂移次数: {report.drift_count}")
```

---

**何时使用 prompt_stability_monitor.py**:
- ✅ 需要提示词版本管理
- ✅ 需要检测提示词漂移（版本升级影响）
- ✅ 需要LLM输出格式验证
- ✅ 需要提示词稳定性报表
- ❌ 不使用LLM Agent
- ❌ 提示词固定不变

**使用场景**:
- 提示词A/B测试
- LLM输出质量监控
- 提示词版本回滚决策
- AI Agent输出格式异常告警

---

## 监控文件对比矩阵

| 维度 | dynamic_node | execution | container | monitoring.py | knowledge_bridge | prompt_stability |
|------|--------------|-----------|-----------|---------------|------------------|------------------|
| **监控对象** | 动态节点 | 工作流编排 | 容器 | 通用 | 告警归档 | 提示词 |
| **抽象层级** | 业务层 | 业务层 | 基础设施层 | 基础设施层 | 集成层 | 业务层 |
| **生产调用** | ✅ | ⚠️ **DEPRECATED** | ✅ | ⚠️ **DEPRECATED** | ✅ | ⚠️ |
| **测试覆盖** | 14 | 4 | 0 | 0 | 7 | 1 |
| **主要功能** | 指标/回滚/恢复/健康检查/告警 | 执行追踪/错误策略 | 事件订阅/日志聚合 | 指标/追踪/健康检查 | 告警→知识库 | 版本管理/漂移检测/格式验证 |
| **状态** | ✅ Active | ⚠️ DEPRECATED | ✅ Active | ⚠️ DEPRECATED | ✅ Active | ✅ Active |

**P1-8 清理结果**:
- `monitoring.py` - 标记为deprecated，Phase 4.2创建但从未集成
- `execution_monitor.py` - 标记为deprecated，Phase 7.3创建但从未集成
- `sandbox_executor.py:ExecutionMonitor` - 重命名为 `SandboxExecutionMonitor` 避免冲突

---

## 选择指南

### 决策树

```
需要监控什么？
│
├─ 动态节点创建/执行/回滚？
│   └─ 使用 dynamic_node_monitoring.py
│
├─ 工作流执行状态/数据流？
│   └─ 使用 execution_monitor.py
│
├─ Docker容器生命周期？
│   └─ 使用 container_execution_monitor.py
│
├─ 提示词版本/输出格式？
│   └─ 使用 prompt_stability_monitor.py
│
├─ 告警数据归档到知识库？
│   └─ 使用 monitoring_knowledge_bridge.py
│
└─ 通用指标/链路追踪？
    └─ 使用 monitoring.py
```

### 使用场景矩阵

| 场景 | 推荐文件 | 理由 |
|------|----------|------|
| 生产监控Dashboard (Grafana) | dynamic_node_monitoring.py | Prometheus指标导出 |
| 工作流执行失败自动回滚 | dynamic_node_monitoring.py | WorkflowRollbackManager |
| 调试节点输入输出数据 | execution_monitor.py | 记录数据流 |
| 容器日志聚合展示 | container_execution_monitor.py | 容器日志收集 |
| 提示词A/B测试 | prompt_stability_monitor.py | 版本管理+稳定性报表 |
| 告警历史模式分析 | monitoring_knowledge_bridge.py | 知识库查询 |
| 自定义业务指标 | monitoring.py | 通用MetricsCollector |

---

## 架构建议

### 推荐架构模式

**分层监控架构**:

```
┌─────────────────────────────────────────────────────┐
│              业务层监控（高级）                      │
│  dynamic_node_monitoring.py (节点)                  │
│  execution_monitor.py (工作流)                      │
│  prompt_stability_monitor.py (提示词)               │
└──────────────────────┬──────────────────────────────┘
                       │ 使用
┌──────────────────────▼──────────────────────────────┐
│           基础设施层监控（底层）                     │
│  monitoring.py (通用指标/追踪)                      │
│  container_execution_monitor.py (容器)              │
└──────────────────────┬──────────────────────────────┘
                       │ 集成
┌──────────────────────▼──────────────────────────────┐
│               集成层（桥接）                         │
│  monitoring_knowledge_bridge.py (告警归档)          │
└─────────────────────────────────────────────────────┘
```

### 未来优化方向

#### 选项1: 保持现状（推荐）✅
- **理由**: 各文件职责清晰，无真冗余
- **行动**: 仅添加文档澄清使用场景
- **成本**: 0小时代码改动 + 2小时文档

#### 选项2: 启用monitoring.py作为底层基础
- **理由**: 统一指标收集底层实现
- **行动**:
  - 修改DynamicNodeMetricsCollector内部使用monitoring.py的MetricsCollector
  - 修改AlertManager内部使用monitoring.py的AlertManager
- **成本**: 8小时重构 + 4小时测试
- **风险**: 可能引入性能回退（增加抽象层）

#### 选项3: 创建MonitoringFacade统一入口
- **理由**: 类似SupervisionFacade模式
- **行动**: 创建Facade包装6个监控文件
- **成本**: 12小时开发 + 6小时测试
- **风险**: 过度工程化（监控文件已按场景分离）

**推荐**: **选项1** - 保持现状，仅文档澄清

---

## 常见问题 (FAQ)

### Q1: 为什么有6个监控文件而不是1个？

**A**: **关注点分离原则**。不同监控场景需求差异大：
- 动态节点需要回滚/恢复能力
- 工作流执行需要数据流追踪
- 容器监控需要事件订阅
- 提示词监控需要版本管理

单一文件会变成"上帝类"（1000+ 行），难以维护和测试。

### Q2: dynamic_node_monitoring.py和monitoring.py的AlertManager有何区别？

**A**:
- **dynamic_node_monitoring.AlertManager**: 业务层告警（节点失败/沙箱超时等）
- **monitoring.py.AlertManager**: 基础设施层告警（通用告警规则引擎）

**关系**: dynamic_node可以内部使用monitoring.py的AlertManager作为底层（目前未实现）。

### Q3: execution_monitor.py和container_execution_monitor.py有何区别？

**A**:
- **execution_monitor.py**: 工作流/节点执行的**观察者模式**监控，记录输入输出数据
- **container_execution_monitor.py**: Docker容器的**事件订阅**监控，聚合容器日志

**场景区分**: execution监控业务逻辑，container监控基础设施。

### Q4: 是否应该创建MonitoringFacade？

**A**: **不推荐**。监控文件已按场景分离，Facade会增加不必要的抽象层。

SupervisionFacade必要的原因：
- 监督逻辑耦合在CoordinatorAgent中（需提取）
- 监督模块间有强依赖（SupervisionModule → SupervisionLogger → SupervisionCoordinator）

监控文件不需要Facade的原因：
- 各监控文件独立使用（无强依赖）
- 已在CoordinatorBootstrap中按需初始化
- 使用场景完全不同（不需要统一入口）

### Q5: monitoring.py应该删除吗？

**A**: **不应该删除，但已标记为deprecated**。P1-8分析确认：
1. **从未被生产代码集成** - Grep验证无调用
2. **保留供参考** - Phase 4.2设计可作为未来统一监控的参考
3. **无紧迫删除需求** - 不占用运行时资源

**P1-8决策**: 添加deprecation notice，保留代码供未来参考。如需通用监控功能，优先使用已active的专用监控模块。

### Q6: execution_monitor.py 和 sandbox_executor.py 的 ExecutionMonitor 有什么关系？

**A**: **完全不同的组件**，P1-8已重命名避免混淆：
- `execution_monitor.py:ExecutionMonitor` - 工作流执行编排监控（**DEPRECATED**，未被使用）
- `sandbox_executor.py:SandboxExecutionMonitor` - 沙箱代码执行回调（**Active**，被workflow_agent使用）

**P1-8行动**: `sandbox_executor.py`中的类已重命名为`SandboxExecutionMonitor`，提供向后兼容别名。

---

## 扩展阅读

- [P1-3 Supervision分析报告](../../tmp/p1_3_supervision_analysis.md) - 监督系统完整分析
- [Supervision迁移指南](./SUPERVISION_MIGRATION_GUIDE.md) - SupervisionFacade使用指南
- [动态节点Runbook](../operations/dynamic_node_runbook.md) - 节点监控运维手册
- [current_agents.md](./current_agents.md) - 三Agent系统架构审计

---

**文档版本**: 1.0
**最后更新**: 2025-12-13
**维护者**: Architecture Team
