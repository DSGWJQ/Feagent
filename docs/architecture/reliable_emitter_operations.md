# ReliableEmitter 运维指南

## 概述

`ReliableEmitter` 是基于 `ConversationFlowEmitter` 的可靠扩展版本，提供：
- 有界队列防止内存溢出
- 多种溢出策略
- 消息持久化
- 背压控制
- 高性能负载处理

## 配置参数

### 核心参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `session_id` | str | 必填 | 会话唯一标识 |
| `max_size` | int | 1000 | 队列最大容量 |
| `overflow_policy` | BufferOverflowPolicy | BLOCK | 溢出策略 |
| `message_store` | MessageStore | None | 消息存储后端 |
| `max_retries` | int | 3 | 最大重试次数 |
| `timeout` | float | None | 迭代超时时间（秒） |

### 溢出策略选择

```python
from src.domain.services.reliable_emitter import BufferOverflowPolicy

# 1. BLOCK - 阻塞等待（适合需要保证消息不丢失的场景）
emitter = ReliableEmitter(
    session_id="important_session",
    overflow_policy=BufferOverflowPolicy.BLOCK,
)

# 2. DROP_OLDEST - 丢弃最旧消息（适合实时性要求高的场景）
emitter = ReliableEmitter(
    session_id="realtime_session",
    overflow_policy=BufferOverflowPolicy.DROP_OLDEST,
)

# 3. DROP_NEWEST - 丢弃新消息（适合保护历史消息的场景）
emitter = ReliableEmitter(
    session_id="history_session",
    overflow_policy=BufferOverflowPolicy.DROP_NEWEST,
)

# 4. RAISE - 抛出异常（适合需要明确处理溢出的场景）
emitter = ReliableEmitter(
    session_id="strict_session",
    overflow_policy=BufferOverflowPolicy.RAISE,
)
```

## 性能指标

### 测试环境结果

| 指标 | 结果 |
|------|------|
| 单线程 QPS | > 10,000 msg/s |
| 10 并发生产者 | 稳定运行 |
| 持久化 QPS | > 5,000 msg/s |
| 查询延迟 | < 100ms |

### 推荐配置

**低负载场景（< 100 msg/s）**：
```python
emitter = ReliableEmitter(
    session_id="low_load",
    max_size=100,
    overflow_policy=BufferOverflowPolicy.BLOCK,
)
```

**中等负载场景（100-1000 msg/s）**：
```python
emitter = ReliableEmitter(
    session_id="medium_load",
    max_size=500,
    overflow_policy=BufferOverflowPolicy.DROP_OLDEST,
)
```

**高负载场景（> 1000 msg/s）**：
```python
emitter = ReliableEmitter(
    session_id="high_load",
    max_size=2000,
    overflow_policy=BufferOverflowPolicy.DROP_OLDEST,
    message_store=InMemoryMessageStore(max_messages_per_session=10000),
)
```

## 监控与告警

### 关键指标

```python
# 获取统计信息
stats = emitter.get_statistics()

# 关键指标
total_steps = stats["total_steps"]      # 总发送数
dropped_count = stats["dropped_count"]  # 丢弃数量
retry_count = stats["retry_count"]      # 重试次数
queue_size = stats["queue_size"]        # 当前队列大小
```

### 告警阈值建议

| 指标 | 警告阈值 | 严重阈值 |
|------|----------|----------|
| 队列使用率 | > 70% | > 90% |
| 丢弃率 | > 1% | > 5% |
| 重试率 | > 5% | > 10% |

### 监控示例

```python
async def monitor_emitter(emitter: ReliableEmitter):
    """监控 emitter 健康状态"""
    stats = emitter.get_statistics()

    queue_usage = stats["queue_size"] / stats["max_size"]
    drop_rate = stats["dropped_count"] / max(stats["total_steps"], 1)

    if queue_usage > 0.9:
        logger.warning(f"队列使用率过高: {queue_usage:.1%}")

    if drop_rate > 0.05:
        logger.error(f"消息丢弃率过高: {drop_rate:.1%}")
```

## 消息持久化

### 内存存储（开发/测试）

```python
from src.domain.services.reliable_emitter import InMemoryMessageStore

store = InMemoryMessageStore(max_messages_per_session=10000)
emitter = ReliableEmitter(
    session_id="dev_session",
    message_store=store,
)
```

### 协调者查询示例

```python
# 获取会话摘要
summary = await store.get_session_summary("session_id")
print(f"总消息数: {summary['total_messages']}")
print(f"工具调用: {summary['tool_calls_count']}")
print(f"是否完成: {summary['has_final_response']}")

# 按类型查询
thinking_msgs = await store.get_by_kind("session_id", StepKind.THINKING)

# 按时间范围查询
from datetime import datetime, timedelta
recent = await store.get_by_time_range(
    "session_id",
    datetime.now() - timedelta(hours=1),
    datetime.now(),
)

# 列出所有会话
sessions = await store.list_sessions()
```

## 故障处理

### 常见问题

**1. 队列溢出频繁**

原因：消费者处理速度慢于生产者

解决：
- 增加 `max_size`
- 使用 `DROP_OLDEST` 策略
- 优化消费者处理逻辑

**2. 生产者阻塞**

原因：使用 `BLOCK` 策略且队列满

解决：
- 增加消费者并发
- 设置合理的 `timeout`
- 切换到 `DROP_*` 策略

**3. 内存增长**

原因：消息持久化累积

解决：
- 设置 `max_messages_per_session`
- 定期清理旧会话
- 使用外部存储（Redis/DB）

### 紧急恢复

```python
# 清空存储
store.clear()

# 重置 emitter（创建新实例）
emitter = ReliableEmitter(
    session_id=f"{old_session_id}_recovery_{timestamp}",
    ...
)
```

## 最佳实践

### 1. 会话 ID 设计

```python
# 推荐：包含时间戳和唯一标识
session_id = f"workflow_{workflow_id}_{timestamp}_{uuid4().hex[:8]}"
```

### 2. 资源清理

```python
async def cleanup_session(emitter: ReliableEmitter, store: MessageStore):
    """会话结束时清理资源"""
    if not emitter.is_completed:
        await emitter.complete()

    # 可选：归档或删除历史消息
```

### 3. 错误处理

```python
try:
    await emitter.emit_thinking("处理中...")
except BufferFullError:
    logger.warning("缓冲区满，使用降级策略")
    # 降级处理
except asyncio.TimeoutError:
    logger.error("发送超时，可能需要检查消费者")
```

### 4. 与 ConversationAgent 集成

```python
class ConversationAgent:
    def __init__(self, emitter: ReliableEmitter):
        self._emitter = emitter

    async def process(self, user_input: str):
        try:
            await self._emitter.emit_thinking("分析用户输入...")
            # 处理逻辑
            await self._emitter.emit_final_response(result)
        except Exception as e:
            await self._emitter.emit_error(str(e))
        finally:
            await self._emitter.complete()
```

## 扩展：自定义存储后端

```python
from src.domain.services.reliable_emitter import MessageStore

class RedisMessageStore:
    """Redis 存储后端实现"""

    def __init__(self, redis_client):
        self._redis = redis_client

    async def save(self, session_id: str, step: ConversationStep) -> None:
        key = f"emitter:messages:{session_id}"
        await self._redis.rpush(key, step.to_dict())

    async def get_by_session_id(self, session_id: str) -> list[ConversationStep]:
        key = f"emitter:messages:{session_id}"
        data = await self._redis.lrange(key, 0, -1)
        return [ConversationStep(**json.loads(d)) for d in data]

    # 实现其他方法...
```

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2025-01 | Phase 5 初始实现 |
