# SaveRequest System Architecture

## Overview

SaveRequest 是 Feagent 平台的文件持久化系统，提供安全、可审计、基于事件驱动的文件写入机制。

### 核心设计原则

- **事件驱动**: 所有保存请求通过 EventBus 发布，不直接执行文件I/O
- **异步安全**: 支持同步和异步两种调用方式
- **优雅降级**: 队列满时返回 None 而非抛异常，保证系统可用性
- **Fail-Fast**: 验证错误立即抛异常，便于快速调试

---

## API 参考

### Primary API: `send_save_request()` ✅ (稳定)

**位置**: `ConversationAgent.send_save_request()`

**状态**: 生产就绪，推荐使用

**异步安全**: ✅ 支持同步和异步上下文

**方法签名**:
```python
def send_save_request(
    target_path: str,
    content: str | bytes,
    reason: str | None = None,
    priority: "SaveRequestPriority | None" = None,
    is_binary: bool = False,
) -> str | None:
```

**使用示例**:
```python
# 同步上下文
request_id = agent.send_save_request(
    target_path="/output/results.txt",
    content="Analysis results",
    reason="保存分析结果",
    priority=SaveRequestPriority.HIGH,
)

# Async 上下文
async def process():
    request_id = agent.send_save_request(
        target_path="/output/results.txt",
        content="Analysis results",
        reason="保存分析结果",
    )
```

---

### Legacy API: `request_save()` ⚠️ (已弃用)

**位置**: `ConversationAgent.request_save()`

**状态**: ⚠️ **已弃用**，请使用 `send_save_request()` 替代

**计划移除**: v2.0 主版本

**迁移指南**:
```python
# ❌ 旧代码 (deprecated)
agent.request_save(
    target_path="/output/results.txt",
    content="data",
    reason="保存",  # 参数必填
)

# ✅ 新代码 (recommended)
agent.send_save_request(
    target_path="/output/results.txt",
    content="data",
    reason="保存",  # 参数可选
)
```

**弃用原因**:
- 缺乏异步安全保证
- 重复的 API 增加维护负担
- 新的 `send_save_request()` 更加灵活

---

## 错误处理契约

| 错误类型 | 异常/返回值 | 含义 | 处理方式 |
|---------|-----------|------|---------|
| `SaveRequestValidationError` | **抛异常** | 编程错误（empty target_path/session_id） | fail-fast，快速定位bug |
| `SaveRequestQueueFullError` | **返回 None** | 临时资源问题（队列已满） | 优雅降级，可重试 |
| 通道禁用 | **返回 None** | 功能未启用 | 预期行为 |
| 无 EventBus | **返回 None** | 依赖未配置 | 预期行为 |

**示例**:
```python
from src.domain.services.save_request_channel import SaveRequestValidationError

try:
    # 有效调用
    request_id = agent.send_save_request(
        target_path="/output/result.txt",
        content="data",
    )
except SaveRequestValidationError as e:
    # target_path 或 session_id 为空
    logger.error(f"保存请求验证失败: {e}")
    # 修复代码，重新尝试

if request_id is None:
    # 可能原因：
    # 1. 通道未启用
    # 2. 没有 event_bus
    # 3. 队列已满
    logger.warning("保存请求未能发送，可能需要重试")
```

---

## 配置指南

### 启用 SaveRequest 通道

通过 `ConversationAgentConfig` 启用：

```python
from src.domain.agents.conversation_agent_config import (
    ConversationAgentConfig,
    StreamingConfig,
)
from src.domain.services.event_bus import EventBus

# 创建 event_bus
event_bus = EventBus()

# 配置 SaveRequest 通道
streaming_config = StreamingConfig(
    enable_save_request_channel=True,  # ✅ 启用通道
)

config = ConversationAgentConfig(
    session_context=session_context,
    llm=LLMConfig(llm=llm_instance),
    event_bus=event_bus,  # ✅ 必需！
    streaming=streaming_config,
)

# 初始化 Agent
agent = ConversationAgent(config=config)

# 现在可以使用 SaveRequest 功能
request_id = agent.send_save_request(
    target_path="/output/result.txt",
    content="data",
)
```

### 配置验证

**默认模式** (strict=False):
```python
# 仅发出警告，不抛异常
config.validate(strict=False)
# "enable_save_request_channel=True requires event_bus" (UserWarning)
```

**严格模式** (strict=True):
```python
# 启用时必须有 event_bus，否则抛异常
config.validate(strict=True)
# ValueError: enable_save_request_channel=True requires event_bus
```

---

## 内部实现

### 关键文件

| 文件 | 用途 |
|------|------|
| `src/domain/agents/conversation_agent.py` | Agent API 集成（send_save_request / request_save） |
| `src/domain/agents/conversation_agent_config.py` | 配置管理（StreamingConfig.validate） |
| `src/domain/services/save_request_channel.py` | SaveRequest 核心定义和验证 |
| `src/domain/services/save_request_orchestrator.py` | 完整生命周期管理 |
| `src/domain/services/save_request_receipt.py` | 结果收据 |

### 异步安全设计

```python
# send_save_request 内部实现
if not self._save_request_channel_enabled or self.event_bus is None:
    return None

# 异常处理
try:
    event = SaveRequest(...)  # 可能抛 ValidationError / QueueFullError
except SaveRequestValidationError:
    raise  # Fail-fast
except SaveRequestQueueFullError:
    return None  # 优雅降级

# 异步安全发布
try:
    asyncio.get_running_loop()  # 有运行循环？
except RuntimeError:
    asyncio.run(publish_coro)  # 无循环：直接运行
else:
    self._create_tracked_task(publish_coro)  # 有循环：调度任务
```

---

## 常见问题

### Q: SaveRequest 与 sync-write 的区别？

**SaveRequest** (推荐):
- 异步、事件驱动
- 支持审计日志
- 优雅降级（队列满返回None）

**Sync-write** (已弃用):
- 同步、直接写入
- 无审计能力
- 可能阻塞主线程

### Q: 为什么 send_save_request() 在同步上下文中使用 asyncio.run()?

EventBus 的 publish 是异步的（async def）。在同步上下文中，我们需要运行异步代码，所以使用 `asyncio.run()`。在异步上下文中，直接调度为后台任务避免阻塞。

### Q: 队列满时为什么返回 None 而不是抛异常?

这是优雅降级的设计。队列满是临时资源问题，不应该导致整个请求失败。调用者可以：
1. 记录日志
2. 重试（稍后）
3. 降级为内存存储
4. 继续处理其他任务

---

## 版本历史

| 版本 | 变更 | 日期 |
|------|------|------|
| v1.0 | 初始实现（send_save_request + request_save） | 2025-12 |
| v1.1 | Phase-P2: 错误处理、配置验证、API弃用 | 2025-12 |
| v2.0 (计划) | 移除 request_save()，完全采用 send_save_request() | TBD |

---

**最后更新**: 2025-12-17 (Phase-P2: SaveRequest系统架构改进)
