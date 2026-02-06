# 事件系统修复规划文档

**文档版本**: 1.0.0
**创建日期**: 2026-01-12
**优先级**: P1 (中期任务)
**预计工期**: 2-3周
**负责人**: 待分配

> 更新（2026-02-06）：本规划中描述的“事件缺失 / callback 双轨”问题，已在主链路通过 **EventBus 单轨**收敛：
> - `WorkflowEngine` 直接发布 `NodeExecutionEvent`（`src/domain/events/workflow_execution_events.py`）
> - `WorkflowEngine.event_callback` 已移除
> - `src/domain/events/node_execution_events.py` 不再存在（避免同名不同义）
>
> 本文件保留为历史规划参考，不应再作为实施依据；请以 `docs/planning/PROJECT_SIMPLIFICATION_DEDUP_PLAN.md` 与当前代码为准。

---

## 一、背景与问题陈述

### 1.1 当前问题

**现象**:
- UX-WF-007 (reconcile_sync) 和 UX-WF-008 (code_assistant) 测试无法从 execution channel 获取 node_complete 事件
- 工作流执行成功，但节点级事件缺失，影响可观测性和调试能力

**根本原因**:
```
执行器 (7个) 不发布事件
    ↓
依赖 WorkflowEngine.event_callback
    ↓
callback 仅在流式执行中设置
    ↓
非流式路径/测试路径缺失 callback
    ↓
❌ node_complete 事件未记录到 execution channel
```

**受影响组件**:
| 执行器 | 文件路径 | 当前状态 |
|--------|---------|---------|
| HttpExecutor | `src/infrastructure/executors/http_executor.py` | ❌ 无事件 |
| NotificationExecutor | `src/infrastructure/executors/notification_executor.py` | ❌ 无事件 |
| FileExecutor | `src/infrastructure/executors/file_executor.py` | ❌ 无事件 |
| LlmExecutor | `src/infrastructure/executors/llm_executor.py` | ❌ 无事件 |
| PythonExecutor | `src/infrastructure/executors/python_executor.py` | ❌ 无事件 |
| DatabaseExecutor | `src/infrastructure/executors/database_executor.py` | ❌ 无事件 |
| TransformExecutor | `src/infrastructure/executors/transform_executor.py` | ❌ 无事件 |

### 1.2 架构缺陷

**违反的设计原则**:
1. **单一职责原则 (SRP)**: WorkflowEngine 既负责编排又负责事件发布
2. **依赖倒置原则 (DIP)**: Domain 层依赖 Application 层注入的 callback
3. **开闭原则 (OCP)**: 新增执行路径容易遗漏事件配置

---

## 二、目标与验收标准

### 2.1 核心目标

1. **完整的事件覆盖**: 所有节点执行都发布 node_start、node_complete、node_error 事件
2. **架构符合 DDD**: 执行器对自身生命周期负责，无需外部 callback
3. **向后兼容**: 不破坏现有 API 和测试
4. **可观测性提升**: execution channel 完整记录所有节点事件

### 2.2 验收标准

| 验收项 | 标准 | 验证方式 |
|--------|------|---------|
| **事件完整性** | 100% 节点执行发布事件 | 运行 UX-WF-007/008，验证 events API 返回完整事件 |
| **测试通过** | 所有 E2E 测试通过 | `pnpm test:e2e:deterministic` 全部 PASS |
| **回归测试** | 现有功能无破坏 | 运行完整测试套件 (unit + integration + e2e) |
| **性能影响** | 事件发布延迟 < 10ms | 性能测试 (benchmark) |
| **代码质量** | Lint/Type 检查通过 | `ruff check`, `pyright`, `eslint` |

---

## 三、技术方案（方案 A：执行器发布事件）

### 3.1 方案概述

**核心思路**: 让每个执行器注入 EventBus，在执行前后发布标准事件

**优点**:
- ✅ 符合 DDD（执行器对生命周期负责）
- ✅ 架构解耦（无需依赖 callback）
- ✅ 完整覆盖（所有执行路径生效）
- ✅ 易于扩展（新增执行器自动生效）

**缺点**:
- ⚠️ 需修改 7 个执行器文件
- ⚠️ 需要依赖注入改造

### 3.2 事件定义

**标准事件类型**:
```python
# src/domain/events/node_execution_events.py

@dataclass
class NodeExecutionStartedEvent:
    """节点开始执行事件"""
    node_id: str
    node_type: str
    node_name: str
    inputs: dict[str, Any]
    timestamp: datetime
    run_id: str | None = None

@dataclass
class NodeExecutionCompletedEvent:
    """节点执行完成事件"""
    node_id: str
    node_type: str
    node_name: str
    output: Any
    duration_ms: float
    timestamp: datetime
    run_id: str | None = None

@dataclass
class NodeExecutionFailedEvent:
    """节点执行失败事件"""
    node_id: str
    node_type: str
    node_name: str
    error: str
    error_type: str
    timestamp: datetime
    run_id: str | None = None
```

### 3.3 执行器基类改造

**步骤 1: 定义抽象基类**
```python
# src/domain/services/base_executor.py

from abc import ABC, abstractmethod
from src.domain.services.event_bus import EventBus
from src.domain.events.node_execution_events import *

class BaseNodeExecutor(ABC):
    """节点执行器基类（增强事件支持）"""

    def __init__(self, event_bus: EventBus | None = None):
        self.event_bus = event_bus

    async def execute_with_events(
        self,
        node: Node,
        inputs: dict[str, Any],
        context: dict[str, Any]
    ) -> Any:
        """执行节点并发布事件（模板方法）"""

        start_time = time.time()

        # 1. 发布开始事件
        if self.event_bus:
            await self.event_bus.publish(
                NodeExecutionStartedEvent(
                    node_id=node.id,
                    node_type=node.type.value,
                    node_name=node.name,
                    inputs=inputs,
                    timestamp=datetime.now(),
                    run_id=context.get("run_id"),
                )
            )

        try:
            # 2. 执行核心逻辑（由子类实现）
            result = await self._execute_impl(node, inputs, context)

            # 3. 发布完成事件
            if self.event_bus:
                duration_ms = (time.time() - start_time) * 1000
                await self.event_bus.publish(
                    NodeExecutionCompletedEvent(
                        node_id=node.id,
                        node_type=node.type.value,
                        node_name=node.name,
                        output=result,
                        duration_ms=duration_ms,
                        timestamp=datetime.now(),
                        run_id=context.get("run_id"),
                    )
                )

            return result

        except Exception as e:
            # 4. 发布失败事件
            if self.event_bus:
                await self.event_bus.publish(
                    NodeExecutionFailedEvent(
                        node_id=node.id,
                        node_type=node.type.value,
                        node_name=node.name,
                        error=str(e),
                        error_type=type(e).__name__,
                        timestamp=datetime.now(),
                        run_id=context.get("run_id"),
                    )
                )
            raise

    @abstractmethod
    async def _execute_impl(
        self,
        node: Node,
        inputs: dict[str, Any],
        context: dict[str, Any]
    ) -> Any:
        """核心执行逻辑（子类实现）"""
        pass
```

### 3.4 执行器改造示例

**步骤 2: 改造 HttpExecutor**
```python
# src/infrastructure/executors/http_executor.py

from src.domain.services.base_executor import BaseNodeExecutor

class HttpExecutor(BaseNodeExecutor):  # 继承 BaseNodeExecutor
    """HTTP 请求执行器（增强事件支持）"""

    def __init__(self, event_bus: EventBus | None = None):
        super().__init__(event_bus)
        self.session = aiohttp.ClientSession()

    async def execute(
        self,
        node: Node,
        inputs: dict[str, Any],
        context: dict[str, Any]
    ) -> Any:
        # 委托给基类的事件包装方法
        return await self.execute_with_events(node, inputs, context)

    async def _execute_impl(  # 实现抽象方法
        self,
        node: Node,
        inputs: dict[str, Any],
        context: dict[str, Any]
    ) -> Any:
        """HTTP 请求核心逻辑（原有代码）"""
        url = node.config.get("url")
        method = node.config.get("method", "GET")
        # ... 原有实现 ...
        return response_data
```

**类似改造其他 6 个执行器**:
- NotificationExecutor
- FileExecutor
- LlmExecutor
- PythonExecutor
- DatabaseExecutor
- TransformExecutor

### 3.5 依赖注入改造

**步骤 3: 在 ExecutorFactory 中注入 EventBus**
```python
# src/infrastructure/executors/executor_factory.py

class ExecutorFactory:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._executors = {
            NodeType.HTTP: HttpExecutor(event_bus),
            NodeType.DATABASE: DatabaseExecutor(event_bus),
            NodeType.FILE: FileExecutor(event_bus),
            NodeType.LLM: LlmExecutor(event_bus),
            NodeType.PYTHON: PythonExecutor(event_bus),
            NodeType.TRANSFORM: TransformExecutor(event_bus),
            NodeType.NOTIFICATION: NotificationExecutor(event_bus),
        }
```

### 3.6 事件订阅与记录

**步骤 4: 订阅事件并记录到 execution channel**
```python
# src/application/services/workflow_run_execution_entry.py

class WorkflowRunExecutionEntry:
    def __init__(self, event_bus: EventBus, ...):
        self.event_bus = event_bus
        self._subscribe_to_node_events()

    def _subscribe_to_node_events(self):
        """订阅节点执行事件"""
        self.event_bus.subscribe(
            NodeExecutionStartedEvent,
            self._handle_node_started
        )
        self.event_bus.subscribe(
            NodeExecutionCompletedEvent,
            self._handle_node_completed
        )
        self.event_bus.subscribe(
            NodeExecutionFailedEvent,
            self._handle_node_failed
        )

    async def _handle_node_completed(self, event: NodeExecutionCompletedEvent):
        """记录节点完成事件到 execution channel"""
        if event.run_id:
            await self._run_event_use_case.execute(
                AppendRunEventInput(
                    run_id=event.run_id,
                    event_type="node_complete",
                    channel="execution",
                    payload={
                        "node_id": event.node_id,
                        "node_type": event.node_type,
                        "output": event.output,
                        "duration_ms": event.duration_ms,
                    },
                )
            )
```

---

## 四、实施计划

### 4.1 Phase 1: 基础设施 (Week 1)

| 任务 | 负责人 | 工期 | 依赖 |
|------|--------|------|------|
| 定义事件类型 (`node_execution_events.py`) | 待分配 | 1d | - |
| 实现 `BaseNodeExecutor` | 待分配 | 2d | 事件定义 |
| 单元测试 (基类) | 待分配 | 1d | 基类实现 |
| Code Review | Tech Lead | 0.5d | 单元测试 |

**交付物**:
- `src/domain/events/node_execution_events.py`
- `src/domain/services/base_executor.py`
- `tests/unit/domain/services/test_base_executor.py`

### 4.2 Phase 2: 执行器改造 (Week 2)

| 执行器 | 负责人 | 工期 | 备注 |
|--------|--------|------|------|
| HttpExecutor | 待分配 | 0.5d | 参考实现 |
| DatabaseExecutor | 待分配 | 0.5d | - |
| FileExecutor | 待分配 | 0.5d | - |
| LlmExecutor | 待分配 | 0.5d | - |
| PythonExecutor | 待分配 | 0.5d | - |
| TransformExecutor | 待分配 | 0.5d | - |
| NotificationExecutor | 待分配 | 0.5d | - |
| 集成测试 | 待分配 | 1d | 所有执行器 |

**交付物**:
- 7 个执行器文件修改
- `tests/integration/executors/test_executor_events.py`

### 4.3 Phase 3: 依赖注入与订阅 (Week 2-3)

| 任务 | 负责人 | 工期 | 依赖 |
|------|--------|------|------|
| ExecutorFactory 改造 | 待分配 | 1d | 执行器改造 |
| WorkflowRunExecutionEntry 事件订阅 | 待分配 | 1d | Factory |
| 端到端测试修复 | 待分配 | 2d | 订阅逻辑 |
| 性能测试 | 待分配 | 1d | E2E 通过 |

**交付物**:
- `src/infrastructure/executors/executor_factory.py` (修改)
- `src/application/services/workflow_run_execution_entry.py` (修改)
- 更新 UX-WF-007/008 测试（恢复事件验证）

### 4.4 Phase 4: 文档与发布 (Week 3)

| 任务 | 负责人 | 工期 |
|------|--------|------|
| 更新架构文档 | 待分配 | 0.5d |
| 编写迁移指南 | 待分配 | 0.5d |
| 性能基准报告 | 待分配 | 0.5d |
| Code Review (Final) | Tech Lead | 1d |
| 合并主分支 | Tech Lead | 0.5d |

---

## 五、风险与缓解

### 5.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **EventBus 性能瓶颈** | 高 | 中 | 异步发布、批量处理、性能测试 |
| **事件丢失** | 高 | 低 | 持久化队列、重试机制 |
| **向后兼容性破坏** | 中 | 低 | 保留旧 callback，逐步迁移 |
| **依赖注入复杂度** | 中 | 中 | 使用 DI 容器（如 dependency-injector） |

### 5.2 进度风险

| 风险 | 缓解措施 |
|------|---------|
| 人力不足 | 优先改造核心执行器（HTTP/DB/LLM） |
| 测试覆盖不足 | 强制 TDD，覆盖率 > 80% |
| Code Review 延迟 | 分阶段 Review，避免积压 |

---

## 六、回滚计划

### 6.1 回滚条件

触发回滚的情况:
1. E2E 测试失败率 > 10%
2. 性能下降 > 20%
3. 生产环境出现严重 Bug

### 6.2 回滚步骤

1. **立即**: 切换到上一个稳定分支
2. **24h 内**: 分析失败原因，修复或放弃
3. **48h 内**: 恢复所有测试通过

### 6.3 Feature Flag

使用 Feature Flag 控制事件发布:
```python
ENABLE_EXECUTOR_EVENTS = os.getenv("ENABLE_EXECUTOR_EVENTS", "false") == "true"

if ENABLE_EXECUTOR_EVENTS and self.event_bus:
    await self.event_bus.publish(event)
```

---

## 七、成功指标

### 7.1 技术指标

| 指标 | 目标值 | 测量方式 |
|------|--------|---------|
| 事件覆盖率 | 100% | 所有节点执行都有事件 |
| 测试通过率 | 100% | CI/CD 绿色 |
| 性能影响 | < 5% | Benchmark 对比 |
| 代码质量 | A 级 | SonarQube |

### 7.2 业务指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 调试效率提升 | 30% | 通过事件快速定位问题 |
| 可观测性覆盖 | 100% | 所有工作流可追踪 |
| Bug 修复时间 | -20% | 更好的事件日志 |

---

## 八、参考资料

### 8.1 相关文档

- [Agent 3 技术报告 - 事件缺失根因分析](./AGENT3_EVENT_INVESTIGATION_REPORT.md)
- [DDD 架构规范](../architecture/DDD_ARCHITECTURE.md)
- [EventBus 设计文档](../architecture/EVENTBUS_DESIGN.md)

### 8.2 代码参考

- 成功的执行器模式: `src/infrastructure/executors/http_executor.py`
- EventBus 实现: `src/domain/services/event_bus.py`
- 事件订阅示例: `src/application/services/workflow_run_execution_entry.py`

---

**状态**: 📋 待启动
**下次审查**: 启动前 Kickoff Meeting
**问题反馈**: [项目 Issue Tracker]
