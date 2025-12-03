# ConversationEngine 生命周期文档

## 概述

`ConversationEngine` 是一个异步生成器（Async Generator），负责管理对话 Agent 的完整执行周期。它位于 `ConversationAgent` 外层，提供：

- **流式事件输出**：通过 `async for` 消费执行事件
- **暂停/恢复支持**：随时暂停和恢复任务执行
- **状态快照**：支持持久化和恢复引擎状态
- **错误处理**：优雅处理各类异常

---

## 生命周期阶段

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│    IDLE     │────▶│    RECEIVING     │────▶│ CONTEXT_FETCHING│
└─────────────┘     └──────────────────┘     └─────────────────┘
                                                      │
                                                      ▼
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  COMPLETED  │◀────│    EXECUTING     │◀────│   DECOMPOSING   │
└─────────────┘     └──────────────────┘     └─────────────────┘
       ▲                    │                        │
       │                    ▼                        ▼
       │            ┌──────────────────┐     ┌─────────────────┐
       └────────────│    SCHEDULING    │◀────│    PAUSED       │
                    └──────────────────┘     └─────────────────┘
```

### 1. 接收阶段 (RECEIVING)

引擎接收用户输入，初始化执行上下文。

```python
async def run(self, user_input: str) -> AsyncIterator[EngineEvent]:
    # 状态变更: IDLE → RECEIVING
    yield EngineEvent(
        event_type=EngineEventType.STATE_CHANGED,
        data={"from": "idle", "to": "receiving"}
    )
```

**事件输出**：
- `STATE_CHANGED`: 状态从 IDLE 变为 RECEIVING

---

### 2. 上下文获取阶段 (CONTEXT_FETCHING)

从 CoordinatorAgent 获取规则、知识、工具等上下文信息。

```python
# 状态变更: RECEIVING → CONTEXT_FETCHING
context = await self._coordinator.get_context_async(user_input)

yield EngineEvent(
    event_type=EngineEventType.CONTEXT_RECEIVED,
    data={
        "rules_count": len(context.rules),
        "tools_count": len(context.tools),
        "knowledge_count": len(context.knowledge)
    }
)
```

**事件输出**：
- `STATE_CHANGED`: 状态从 RECEIVING 变为 CONTEXT_FETCHING
- `CONTEXT_RECEIVED`: 包含规则、工具、知识的数量统计

---

### 3. 分解阶段 (DECOMPOSING)

使用 LLM 将用户目标分解为可执行的子任务列表。

```python
# 状态变更: CONTEXT_FETCHING → DECOMPOSING
tasks = await self._llm.decompose_goal(user_input)

yield EngineEvent(
    event_type=EngineEventType.TASK_DECOMPOSED,
    data={
        "task_count": len(tasks),
        "tasks": [{"id": t["id"], "description": t["description"]} for t in tasks]
    }
)
```

**事件输出**：
- `STATE_CHANGED`: 状态从 CONTEXT_FETCHING 变为 DECOMPOSING
- `TASK_DECOMPOSED`: 包含分解后的任务数量和任务列表

---

### 4. 调度阶段 (SCHEDULING)

按优先级对任务进行排序和调度。

```python
# 状态变更: DECOMPOSING → SCHEDULING
sorted_tasks = sorted(self._tasks, key=lambda t: t.priority)

for task in sorted_tasks:
    yield EngineEvent(
        event_type=EngineEventType.TASK_SCHEDULED,
        data={"task_id": task.id, "priority": task.priority}
    )
```

**事件输出**：
- `STATE_CHANGED`: 状态从 DECOMPOSING 变为 SCHEDULING
- `TASK_SCHEDULED`: 每个任务调度时触发，包含任务 ID 和优先级

---

### 5. 执行阶段 (EXECUTING)

依次执行调度好的任务，支持暂停检查。

```python
# 状态变更: SCHEDULING → EXECUTING
for task in sorted_tasks:
    # 暂停检查点
    await self._pause_event.wait()

    yield EngineEvent(
        event_type=EngineEventType.TASK_STARTED,
        data={"task_id": task.id}
    )

    # 执行任务...

    yield EngineEvent(
        event_type=EngineEventType.TASK_COMPLETED,
        data={
            "task_id": task.id,
            "result": result,
            "progress": completed / total
        }
    )
```

**事件输出**：
- `STATE_CHANGED`: 状态从 SCHEDULING 变为 EXECUTING
- `TASK_STARTED`: 任务开始执行
- `TASK_COMPLETED`: 任务完成，包含结果和进度

---

### 6. 完成阶段 (COMPLETED)

所有任务执行完毕。

```python
# 状态变更: EXECUTING → COMPLETED
yield EngineEvent(
    event_type=EngineEventType.ENGINE_COMPLETED,
    data={
        "total_tasks": self.total_tasks,
        "completed_tasks": self.completed_tasks
    }
)
```

**事件输出**：
- `STATE_CHANGED`: 状态变为 COMPLETED
- `ENGINE_COMPLETED`: 引擎完成，包含任务统计

---

## 暂停/恢复机制

### 暂停 (pause)

```python
def pause(self) -> bool:
    """暂停引擎执行"""
    if self._state not in [EngineState.EXECUTING, EngineState.SCHEDULING]:
        return False

    self._pause_event.clear()  # 阻塞执行
    self._state = EngineState.PAUSED
    return True
```

**注意事项**：
- 只能在 EXECUTING 或 SCHEDULING 状态下暂停
- 暂停后进度保持不变

### 恢复 (resume)

```python
def resume(self) -> bool:
    """恢复引擎执行"""
    if self._state != EngineState.PAUSED:
        return False

    self._state = EngineState.EXECUTING
    self._pause_event.set()  # 释放阻塞
    return True
```

**注意事项**：
- 只能在 PAUSED 状态下恢复
- 恢复后从暂停点继续执行

---

## 状态快照

### 创建快照

```python
def create_snapshot(self) -> dict[str, Any]:
    """创建引擎状态快照"""
    return {
        "state": self._state.value,
        "progress": self.current_progress,
        "tasks": [
            {
                "id": t.id,
                "description": t.description,
                "status": t.status,
                "priority": t.priority
            }
            for t in self._tasks
        ],
        "completed_tasks": self._completed_tasks,
        "total_tasks": self._total_tasks
    }
```

### 恢复快照

```python
def restore_from_snapshot(self, snapshot: dict[str, Any]) -> bool:
    """从快照恢复引擎状态"""
    self._state = EngineState(snapshot["state"])
    self._completed_tasks = snapshot["completed_tasks"]
    self._total_tasks = snapshot["total_tasks"]
    self._tasks = [SubTask(**t) for t in snapshot["tasks"]]
    return True
```

---

## 错误处理

### 协调者错误

```python
try:
    context = await self._coordinator.get_context_async(user_input)
except Exception as e:
    self._state = EngineState.ERROR
    yield EngineEvent(
        event_type=EngineEventType.ENGINE_ERROR,
        data={"error": str(e), "phase": "context_fetching"}
    )
```

### 重置

```python
def reset(self) -> None:
    """重置引擎到初始状态"""
    self._state = EngineState.IDLE
    self._tasks.clear()
    self._completed_tasks = 0
    self._total_tasks = 0
    self._pause_event.set()
```

---

## 使用示例

### 基本使用

```python
engine = ConversationEngine(coordinator=coordinator, llm=llm)

async for event in engine.run("帮我分析销售数据"):
    print(f"[{event.event_type}] {event.data}")
```

### 暂停/恢复

```python
import asyncio

async def main():
    engine = ConversationEngine(coordinator=coordinator, llm=llm)
    gen = engine.run("复杂任务")

    # 获取前几个事件
    for _ in range(5):
        event = await gen.__anext__()
        print(event)

    # 暂停
    engine.pause()
    print(f"进度: {engine.current_progress}")

    # 稍后恢复
    await asyncio.sleep(1)
    engine.resume()

    # 继续处理
    async for event in gen:
        print(event)
```

### 快照持久化

```python
# 保存状态
snapshot = engine.create_snapshot()
with open("engine_state.json", "w") as f:
    json.dump(snapshot, f)

# 恢复状态
with open("engine_state.json", "r") as f:
    snapshot = json.load(f)

new_engine = ConversationEngine()
new_engine.restore_from_snapshot(snapshot)
```

---

## 事件类型汇总

| 事件类型 | 触发时机 | 数据内容 |
|---------|---------|---------|
| `STATE_CHANGED` | 状态转换时 | `{from, to}` |
| `CONTEXT_RECEIVED` | 上下文获取完成 | `{rules_count, tools_count, knowledge_count}` |
| `TASK_DECOMPOSED` | 任务分解完成 | `{task_count, tasks}` |
| `TASK_SCHEDULED` | 任务被调度 | `{task_id, priority}` |
| `TASK_STARTED` | 任务开始执行 | `{task_id}` |
| `TASK_COMPLETED` | 任务执行完成 | `{task_id, result, progress}` |
| `ENGINE_PAUSED` | 引擎暂停 | `{progress}` |
| `ENGINE_RESUMED` | 引擎恢复 | `{progress}` |
| `ENGINE_COMPLETED` | 引擎完成 | `{total_tasks, completed_tasks}` |
| `ENGINE_ERROR` | 发生错误 | `{error, phase}` |

---

## 状态转换规则

```python
VALID_STATE_TRANSITIONS = {
    EngineState.IDLE: [EngineState.RECEIVING],
    EngineState.RECEIVING: [EngineState.CONTEXT_FETCHING, EngineState.ERROR],
    EngineState.CONTEXT_FETCHING: [EngineState.DECOMPOSING, EngineState.ERROR],
    EngineState.DECOMPOSING: [EngineState.SCHEDULING, EngineState.ERROR],
    EngineState.SCHEDULING: [EngineState.EXECUTING, EngineState.PAUSED, EngineState.ERROR],
    EngineState.EXECUTING: [EngineState.COMPLETED, EngineState.PAUSED, EngineState.ERROR],
    EngineState.PAUSED: [EngineState.EXECUTING, EngineState.SCHEDULING],
    EngineState.COMPLETED: [EngineState.IDLE],
    EngineState.ERROR: [EngineState.IDLE],
}
```

---

## 文件位置

- **实现**: `src/domain/agents/conversation_engine.py`
- **单元测试**: `tests/unit/domain/agents/test_conversation_engine.py` (26 tests)
- **集成测试**: `tests/integration/test_conversation_engine_e2e.py` (11 tests)

---

**最后更新**: 2025-12-03
**Phase**: 2 - 对话 Agent 主循环引擎
