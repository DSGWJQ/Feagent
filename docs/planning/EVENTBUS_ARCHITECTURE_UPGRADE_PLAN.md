# EventBus 统一架构升级规划文档

**文档版本**: 1.0.0
**创建日期**: 2026-01-12
**优先级**: P3 (长期任务)
**预计工期**: 2-3个月
**负责人**: Tech Lead + Architecture Team

> 更新（2026-02-06）：主链路已完成“快速收敛”版本（EventBus 单轨 + SSE 订阅 + RunEvents 落库）：
> - `WorkflowEngine` 发布 `NodeExecutionEvent`（`src/domain/events/workflow_execution_events.py`）
> - callback 语义已从执行主链路移除（避免双轨）
>
> 本文件保留为“长期升级”备选方案（EventStore/CQRS/Saga）。在精简目标下，除非出现明确的业务/规模触发条件，否则不建议推进，以免引入不必要复杂度（YAGNI）。

---

## 一、背景与战略意义

### 1.1 当前架构问题

**现状分析**:

| 维度 | 当前状态 | 问题 |
|------|---------|------|
| **事件发布** | Callback + EventBus 并存 | 机制不统一，责任分散 |
| **事件记录** | 手动调用 `_record_execution_event_sync` | 容易遗漏，耦合度高 |
| **事件溯源** | 部分事件未持久化 | 无法完整回溯工作流历史 |
| **消息可靠性** | 内存队列，无持久化 | 重启后事件丢失 |
| **水平扩展** | 单机 EventBus | 无法跨实例通信 |

**技术债务**:
1. `WorkflowEngine.event_callback` 脆弱的回调机制
2. `ExecuteWorkflowUseCase.execute_streaming` 中的事件处理逻辑重复
3. 缺少统一的事件溯源（Event Sourcing）能力
4. 无法支持 CQRS（Command Query Responsibility Segregation）模式

### 1.2 架构愿景

**目标架构**: 基于 EventBus 的事件驱动架构（EDA）

```
┌─────────────────────────────────────────────────────┐
│              Domain Layer (领域层)                   │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐   │
│  │ Executors  │  │  Entities  │  │  Services  │   │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘   │
│        │                │                │          │
│        └────────────────┴────────────────┘          │
│                         ▼                           │
│                   ┌──────────┐                      │
│                   │ EventBus │ ← 统一事件总线       │
│                   └────┬─────┘                      │
└────────────────────────┼──────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │ Handlers │  │ Sagas    │  │ Projections│
    │ (同步)    │  │ (编排)    │  │ (读模型)  │
    └──────────┘  └──────────┘  └──────────┘
          │              │              │
          ▼              ▼              ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │ 通知服务  │  │ 工作流恢复 │  │ 查询缓存  │
    └──────────┘  └──────────┘  └──────────┘
```

**核心价值**:
1. **统一事件模型**: 所有领域事件通过 EventBus 发布
2. **事件溯源**: 完整记录系统状态变化历史
3. **CQRS 支持**: 命令（写）和查询（读）模型分离
4. **可扩展性**: 支持分布式部署（RabbitMQ/Kafka）
5. **可观测性**: 完整的事件日志和审计跟踪

---

## 二、目标与验收标准

### 2.1 核心目标

| 目标 | 说明 | 优先级 |
|------|------|--------|
| **废弃 Callback** | 移除所有 `event_callback` 机制 | P0 |
| **事件溯源** | 实现 Event Store (事件存储) | P0 |
| **CQRS 模式** | 分离命令和查询模型 | P1 |
| **分布式支持** | 接入 RabbitMQ/Kafka | P2 |
| **Saga 编排** | 支持长事务和补偿机制 | P2 |

### 2.2 验收标准

| 验收项 | 标准 | 测量方式 |
|--------|------|---------|
| **事件完整性** | 100% 领域事件发布到 EventBus | 审计所有 Domain 层代码 |
| **Callback 清除** | 0 处使用 `event_callback` | 代码扫描 |
| **事件持久化** | 100% 事件写入 Event Store | 检查数据库记录 |
| **性能影响** | 延迟增加 < 10%, 吞吐量不降低 | 性能测试对比 |
| **向后兼容** | API 无破坏性变更 | 回归测试全部通过 |

---

## 三、技术方案

### 3.1 Event Store 设计

**目的**: 持久化所有领域事件，支持事件回溯和状态重建

**表结构**:
```sql
-- Event Store 表（事件存储）
CREATE TABLE event_store (
    id BIGSERIAL PRIMARY KEY,
    event_id UUID UNIQUE NOT NULL,
    event_type VARCHAR(255) NOT NULL,
    aggregate_type VARCHAR(255) NOT NULL,  -- 聚合根类型 (e.g., Workflow, Run)
    aggregate_id VARCHAR(255) NOT NULL,     -- 聚合根 ID
    event_version INT NOT NULL,              -- 事件版本（乐观锁）
    event_data JSONB NOT NULL,               -- 事件负载
    metadata JSONB,                          -- 元数据（user_id, ip, etc.）
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- 索引优化
    INDEX idx_aggregate (aggregate_type, aggregate_id),
    INDEX idx_event_type (event_type),
    INDEX idx_created_at (created_at)
);

-- 快照表（性能优化）
CREATE TABLE snapshots (
    id BIGSERIAL PRIMARY KEY,
    aggregate_type VARCHAR(255) NOT NULL,
    aggregate_id VARCHAR(255) NOT NULL,
    snapshot_version INT NOT NULL,
    snapshot_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE (aggregate_type, aggregate_id, snapshot_version)
);
```

**事件存储接口**:
```python
# src/domain/ports/event_store.py

from abc import ABC, abstractmethod
from typing import List, Type
from src.domain.events.base_event import DomainEvent

class EventStore(ABC):
    """事件存储接口"""

    @abstractmethod
    async def append(
        self,
        aggregate_type: str,
        aggregate_id: str,
        events: List[DomainEvent],
        expected_version: int | None = None,
    ) -> None:
        """追加事件（支持乐观锁）"""
        pass

    @abstractmethod
    async def get_events(
        self,
        aggregate_type: str,
        aggregate_id: str,
        from_version: int = 0,
        to_version: int | None = None,
    ) -> List[DomainEvent]:
        """获取聚合根的事件历史"""
        pass

    @abstractmethod
    async def get_events_by_type(
        self,
        event_type: Type[DomainEvent],
        from_timestamp: datetime | None = None,
        limit: int = 100,
    ) -> List[DomainEvent]:
        """按事件类型查询"""
        pass
```

### 3.2 EventBus 增强

**当前 EventBus** (`src/domain/services/event_bus.py`):
- ✅ 支持发布/订阅
- ✅ 支持中间件
- ❌ 无持久化
- ❌ 无分布式支持

**升级后 EventBus**:
```python
# src/domain/services/enhanced_event_bus.py

from typing import Type, Callable, List
from src.domain.events.base_event import DomainEvent
from src.domain.ports.event_store import EventStore
from src.domain.ports.message_queue import MessageQueue

class EnhancedEventBus:
    """增强型事件总线（支持持久化和分布式）"""

    def __init__(
        self,
        event_store: EventStore | None = None,
        message_queue: MessageQueue | None = None,
    ):
        self.event_store = event_store
        self.message_queue = message_queue
        self._handlers: dict[Type[DomainEvent], List[Callable]] = {}
        self._middlewares: List[Callable] = []

    async def publish(self, event: DomainEvent) -> None:
        """发布事件（持久化 + 分发）"""

        # 1. 持久化到 Event Store
        if self.event_store:
            await self.event_store.append(
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                events=[event],
            )

        # 2. 发布到消息队列（分布式）
        if self.message_queue:
            await self.message_queue.publish(
                topic=event.__class__.__name__,
                message=event.to_dict(),
            )

        # 3. 调用本地订阅者（同步）
        handlers = self._handlers.get(type(event), [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                # 记录错误但不中断其他 handler
                logger.error(f"Handler failed for {event}: {e}")

    async def publish_batch(self, events: List[DomainEvent]) -> None:
        """批量发布（性能优化）"""
        if self.event_store:
            # 按聚合根分组
            grouped = self._group_by_aggregate(events)
            for (agg_type, agg_id), event_list in grouped.items():
                await self.event_store.append(agg_type, agg_id, event_list)

        # 分发事件
        for event in events:
            if self.message_queue:
                await self.message_queue.publish(
                    topic=event.__class__.__name__,
                    message=event.to_dict(),
                )
            await self._dispatch_local(event)

    def subscribe(
        self,
        event_type: Type[DomainEvent],
        handler: Callable[[DomainEvent], None],
    ) -> None:
        """订阅事件"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
```

### 3.3 CQRS 模式

**命令模型 (Write)**: 通过领域模型执行
```python
# src/application/commands/create_workflow_command.py

@dataclass
class CreateWorkflowCommand:
    name: str
    description: str
    nodes: List[dict]
    edges: List[dict]

class CreateWorkflowHandler:
    def __init__(self, event_bus: EnhancedEventBus):
        self.event_bus = event_bus

    async def handle(self, command: CreateWorkflowCommand) -> str:
        # 1. 创建聚合根
        workflow = Workflow.create(
            name=command.name,
            description=command.description,
        )

        # 2. 添加节点和边
        for node_data in command.nodes:
            workflow.add_node(Node.create(**node_data))

        for edge_data in command.edges:
            workflow.add_edge(Edge.create(**edge_data))

        # 3. 发布领域事件
        for event in workflow.domain_events:
            await self.event_bus.publish(event)

        # 4. 清空领域事件（已发布）
        workflow.clear_events()

        return workflow.id
```

**查询模型 (Read)**: 通过投影（Projection）构建
```python
# src/application/projections/workflow_read_model.py

class WorkflowReadModel:
    """工作流查询模型（投影）"""

    def __init__(self, event_bus: EnhancedEventBus):
        self.event_bus = event_bus
        self._subscribe_to_events()

    def _subscribe_to_events(self):
        """订阅工作流相关事件"""
        self.event_bus.subscribe(WorkflowCreatedEvent, self._on_workflow_created)
        self.event_bus.subscribe(NodeAddedEvent, self._on_node_added)
        self.event_bus.subscribe(WorkflowExecutedEvent, self._on_workflow_executed)

    async def _on_workflow_created(self, event: WorkflowCreatedEvent):
        """更新查询缓存"""
        await self.cache.set(
            key=f"workflow:{event.workflow_id}",
            value={
                "id": event.workflow_id,
                "name": event.name,
                "description": event.description,
                "created_at": event.timestamp,
            },
        )

    async def _on_node_added(self, event: NodeAddedEvent):
        """增量更新节点列表"""
        workflow = await self.cache.get(f"workflow:{event.workflow_id}")
        workflow["nodes"].append(event.node)
        await self.cache.set(f"workflow:{event.workflow_id}", workflow)

    async def get_workflow(self, workflow_id: str) -> dict:
        """查询工作流（从缓存）"""
        return await self.cache.get(f"workflow:{workflow_id}")
```

### 3.4 Saga 编排

**目的**: 支持长事务和分布式事务的补偿机制

**示例**: 工作流执行 Saga
```python
# src/domain/sagas/workflow_execution_saga.py

class WorkflowExecutionSaga:
    """工作流执行 Saga（编排多节点执行）"""

    def __init__(self, event_bus: EnhancedEventBus):
        self.event_bus = event_bus
        self._subscribe_to_events()

    def _subscribe_to_events(self):
        self.event_bus.subscribe(WorkflowStartedEvent, self._on_workflow_started)
        self.event_bus.subscribe(NodeExecutionCompletedEvent, self._on_node_completed)
        self.event_bus.subscribe(NodeExecutionFailedEvent, self._on_node_failed)

    async def _on_workflow_started(self, event: WorkflowStartedEvent):
        """工作流开始 → 执行第一个节点"""
        first_node = event.workflow.get_start_node()
        await self._execute_node(first_node, event.initial_input)

    async def _on_node_completed(self, event: NodeExecutionCompletedEvent):
        """节点完成 → 执行下一个节点"""
        next_nodes = event.workflow.get_next_nodes(event.node_id)

        if not next_nodes:
            # 工作流完成
            await self.event_bus.publish(WorkflowCompletedEvent(...))
        else:
            # 执行下一个节点
            for next_node in next_nodes:
                await self._execute_node(next_node, event.output)

    async def _on_node_failed(self, event: NodeExecutionFailedEvent):
        """节点失败 → 触发补偿（Rollback）"""
        executed_nodes = event.workflow.get_executed_nodes()

        # 逆序执行补偿操作
        for node in reversed(executed_nodes):
            if hasattr(node, "compensate"):
                await node.compensate()

        # 发布工作流失败事件
        await self.event_bus.publish(WorkflowFailedEvent(...))
```

---

## 四、实施计划

### 4.1 Phase 1: Event Store 实现 (Month 1)

| Week | 任务 | 负责人 | 交付物 |
|------|------|--------|--------|
| W1 | Event Store 接口定义 | Architect | `src/domain/ports/event_store.py` |
| W1-W2 | PostgreSQL 实现 | Backend | `PostgresEventStore` |
| W2 | 单元测试 | Backend | `test_event_store.py` |
| W3 | 集成测试（事件回溯） | Backend | 验证事件溯源能力 |
| W4 | 性能测试（1M 事件） | QA | 基准报告 |

### 4.2 Phase 2: EventBus 升级 (Month 1-2)

| Week | 任务 | 负责人 | 交付物 |
|------|------|--------|--------|
| W1 | 增强 EventBus（持久化） | Backend | `EnhancedEventBus` |
| W2 | 消息队列抽象（RabbitMQ） | Backend | `MessageQueue` 接口 |
| W3 | 迁移现有事件发布逻辑 | Backend | 移除 Callback |
| W4 | 集成测试 | Backend | 所有测试通过 |

### 4.3 Phase 3: CQRS 实现 (Month 2)

| Week | 任务 | 负责人 | 交付物 |
|------|------|--------|--------|
| W1 | 命令模型定义 | Architect | Commands + Handlers |
| W2 | 查询模型（投影） | Backend | Read Models |
| W3 | API 重构（CQRS） | Backend | 分离读写端点 |
| W4 | 端到端测试 | QA | E2E 通过 |

### 4.4 Phase 4: Saga 编排 (Month 3)

| Week | 任务 | 负责人 | 交付物 |
|------|------|--------|--------|
| W1-W2 | Saga 基础设施 | Backend | `SagaOrchestrator` |
| W2-W3 | 工作流执行 Saga | Backend | `WorkflowExecutionSaga` |
| W3 | 补偿机制 | Backend | Rollback 逻辑 |
| W4 | 集成测试 + 文档 | All | 完整交付 |

---

## 五、迁移策略

### 5.1 分阶段迁移

**阶段 0: 并行运行** (Week 1-2)
- EventBus 和 Callback 同时存在
- 新功能使用 EventBus，旧功能保持不变
- Feature Flag 控制切换

**阶段 1: 逐步替换** (Week 3-8)
- 按模块迁移（Workflow → Run → Task）
- 每个模块迁移后运行回归测试
- 监控性能和错误率

**阶段 2: 清理 Callback** (Week 9-12)
- 所有代码迁移完成
- 删除 Callback 相关代码
- 更新文档

### 5.2 Feature Flag

```python
# config/feature_flags.py

FEATURE_FLAGS = {
    "ENABLE_EVENT_STORE": os.getenv("ENABLE_EVENT_STORE", "false") == "true",
    "ENABLE_CQRS": os.getenv("ENABLE_CQRS", "false") == "true",
    "ENABLE_SAGA": os.getenv("ENABLE_SAGA", "false") == "true",
}

# 使用示例
if FEATURE_FLAGS["ENABLE_EVENT_STORE"]:
    await event_bus.publish(event)
else:
    # 旧逻辑
    if event_callback:
        event_callback(event)
```

---

## 六、风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **Event Store 性能瓶颈** | 高 | 中 | 批量写入、快照优化、分库分表 |
| **数据一致性问题** | 高 | 中 | 事务保证、最终一致性、幂等处理 |
| **迁移导致 Bug** | 高 | 中 | 充分测试、灰度发布、快速回滚 |
| **学习曲线陡峭** | 中 | 高 | 培训、文档、代码示例 |
| **分布式复杂度** | 中 | 中 | 先单机，后分布式，逐步演进 |

---

## 七、成功指标

### 7.1 技术指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 事件溯源覆盖率 | 100% | 所有领域事件可回溯 |
| Callback 清除率 | 100% | 代码中无 `event_callback` |
| 性能影响 | < 10% | 延迟和吞吐量 |
| 测试通过率 | 100% | 无回归 |

### 7.2 业务指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 故障诊断时间 | -50% | 事件日志加速定位 |
| 系统可扩展性 | +100% | 支持水平扩展 |
| 功能交付速度 | +30% | CQRS 加速开发 |

---

## 八、参考资料

### 8.1 理论基础

- [Event Sourcing Pattern](https://martinfowler.com/eaaDev/EventSourcing.html)
- [CQRS Pattern](https://martinfowler.com/bliki/CQRS.html)
- [Saga Pattern](https://microservices.io/patterns/data/saga.html)

### 8.2 技术实现

- [PostgreSQL Event Store](https://github.com/eventstore/eventstore)
- [RabbitMQ Messaging](https://www.rabbitmq.com/tutorials/tutorial-one-python.html)
- [Axon Framework (Java 参考)](https://axoniq.io/)

---

**状态**: 📋 待启动（长期规划）
**依赖**: 事件系统修复（Phase 1 基础）
**下次审查**: 架构评审会议
**预期收益**: 可维护性 +40%, 可扩展性 +100%, 可观测性 +60%
