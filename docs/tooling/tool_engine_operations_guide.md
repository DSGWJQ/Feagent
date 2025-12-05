# ToolEngine 运维指南

> 文档日期：2025-12-05
> 版本：1.0.0
> 适用范围：开发、测试、生产环境

---

## 目录

1. [添加新工具](#1-添加新工具)
2. [热更新工具](#2-热更新工具)
3. [监控并发](#3-监控并发)
4. [故障排查](#4-故障排查)
5. [性能调优](#5-性能调优)

---

## 1. 添加新工具

### 1.1 步骤概览

```
1. 创建 YAML 配置文件
2. 实现执行器（如需要）
3. 注册执行器到 ToolEngine
4. 验证工具加载
5. 测试工具执行
```

### 1.2 创建 YAML 配置文件

在 `tools/` 目录下创建新的 YAML 文件：

```yaml
# tools/my_new_tool.yaml
name: my_new_tool
version: "1.0.0"
description: 我的新工具描述
category: custom
tags:
  - custom
  - example

parameters:
  - name: input_text
    type: string
    required: true
    description: 输入文本

  - name: options
    type: object
    required: false
    description: 可选配置

entry:
  type: builtin
  handler: my_new_tool  # 执行器名称
```

### 1.3 实现执行器

```python
# src/domain/services/executors/my_new_tool_executor.py

class MyNewToolExecutor:
    """我的新工具执行器"""

    async def execute(
        self,
        tool: Tool,
        params: dict[str, Any],
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        """执行工具

        参数：
            tool: 工具定义
            params: 调用参数（已验证）
            context: 执行上下文

        返回：
            执行结果字典
        """
        input_text = params["input_text"]
        options = params.get("options", {})

        # 实现工具逻辑
        result = await self._process(input_text, options)

        return {"result": result}

    async def _process(self, text: str, options: dict) -> str:
        # 具体处理逻辑
        return f"Processed: {text}"
```

### 1.4 注册执行器

```python
# 在应用启动时注册
from src.domain.services.tool_engine import ToolEngine
from src.domain.services.executors.my_new_tool_executor import MyNewToolExecutor

engine = ToolEngine(config)
await engine.load()

# 注册执行器
engine.register_executor("my_new_tool", MyNewToolExecutor())
```

### 1.5 验证工具加载

```python
# 检查工具是否加载成功
tool = engine.get("my_new_tool")
if tool:
    print(f"工具已加载: {tool.name} v{tool.version}")
else:
    print("工具加载失败")

# 检查加载错误
for name, error in engine.load_errors:
    print(f"加载错误 - {name}: {error}")
```

### 1.6 测试工具执行

```python
from src.domain.services.tool_executor import ToolExecutionContext

context = ToolExecutionContext(
    caller_id="test",
    caller_type="direct",
)

result = await engine.execute(
    tool_name="my_new_tool",
    params={"input_text": "Hello World"},
    context=context,
)

if result.is_success:
    print(f"执行成功: {result.output}")
else:
    print(f"执行失败: {result.error}")
```

---

## 2. 热更新工具

### 2.1 手动触发重载

```python
# 重载所有工具
changes = await engine.reload()

print(f"新增工具: {changes['added']}")
print(f"更新工具: {changes['modified']}")
print(f"删除工具: {changes['removed']}")
```

### 2.2 自动重载配置

```python
from src.domain.services.tool_engine import ToolEngine, ToolEngineConfig

config = ToolEngineConfig(
    tools_directory="tools",
    auto_reload=True,           # 启用自动重载
    reload_interval=5.0,        # 每 5 秒检查一次
    watch_for_changes=False,    # 是否使用文件监听
)

engine = ToolEngine(config)
```

### 2.3 热更新操作步骤

#### 添加新工具

```bash
# 1. 创建新的 YAML 文件
echo "name: new_tool
version: '1.0.0'
description: New tool
category: custom
parameters: []
entry:
  type: builtin
  handler: new_tool" > tools/new_tool.yaml

# 2. 触发重载（或等待自动重载）
# Python: await engine.reload()

# 3. 验证
# Python: assert engine.get("new_tool") is not None
```

#### 更新现有工具

```bash
# 1. 修改 YAML 文件（更新版本号）
# 修改 tools/existing_tool.yaml 中的 version 或 description

# 2. 触发重载
# Python: changes = await engine.reload()
# Python: assert "existing_tool" in changes["modified"]
```

#### 删除工具

```bash
# 1. 删除 YAML 文件
rm tools/old_tool.yaml

# 2. 触发重载
# Python: changes = await engine.reload()
# Python: assert "old_tool" in changes["removed"]
```

### 2.4 监听重载事件

```python
def on_reload_event(event: ToolEngineEvent):
    if event.event_type == ToolEngineEventType.RELOAD_STARTED:
        print("开始重载工具...")
    elif event.event_type == ToolEngineEventType.RELOAD_COMPLETED:
        print("工具重载完成")
    elif event.event_type == ToolEngineEventType.TOOL_ADDED:
        print(f"新增工具: {event.tool_name}")
    elif event.event_type == ToolEngineEventType.TOOL_UPDATED:
        print(f"更新工具: {event.tool_name}")
    elif event.event_type == ToolEngineEventType.TOOL_REMOVED:
        print(f"删除工具: {event.tool_name}")

engine.subscribe(on_reload_event)
```

---

## 3. 监控并发

### 3.1 获取并发指标

```python
from src.domain.services.tool_concurrency_controller import (
    ToolConcurrencyController,
    ConcurrencyConfig,
)

# 创建并发控制器
config = ConcurrencyConfig(
    max_concurrent=10,
    queue_size=100,
    strategy="fifo",
)
controller = ToolConcurrencyController(config)

# 获取当前指标
metrics = controller.get_metrics()
print(f"当前并发数: {metrics.current_concurrent}")
print(f"队列长度: {metrics.queue_length}")
print(f"总获取次数: {metrics.total_acquired}")
print(f"总拒绝次数: {metrics.total_rejected}")
print(f"总超时次数: {metrics.total_timeout}")
print(f"平均执行时间: {metrics.avg_execution_time:.3f}s")
```

### 3.2 分桶监控

```python
# 配置分桶限流
config = ConcurrencyConfig(
    max_concurrent=10,
    bucket_limits={
        "http": 5,
        "ai": 2,
        "database": 3,
    }
)

# 获取分桶指标
bucket_metrics = controller.get_bucket_metrics()
for bucket, stats in bucket_metrics.items():
    print(f"[{bucket}] 当前: {stats['current']}/{stats['limit']}, 队列: {stats['queue']}")
```

### 3.3 监控告警阈值

```python
# 定期检查并发状态
async def check_concurrency_health():
    metrics = controller.get_metrics()

    # 并发数告警
    if metrics.current_concurrent > config.max_concurrent * 0.8:
        print(f"⚠️ 并发数接近上限: {metrics.current_concurrent}/{config.max_concurrent}")

    # 队列长度告警
    if metrics.queue_length > config.queue_size * 0.5:
        print(f"⚠️ 队列积压: {metrics.queue_length}/{config.queue_size}")

    # 拒绝率告警
    if metrics.total_acquired > 0:
        reject_rate = metrics.total_rejected / metrics.total_acquired
        if reject_rate > 0.1:
            print(f"⚠️ 拒绝率过高: {reject_rate:.1%}")

    # 超时率告警
    if metrics.total_acquired > 0:
        timeout_rate = metrics.total_timeout / metrics.total_acquired
        if timeout_rate > 0.05:
            print(f"⚠️ 超时率过高: {timeout_rate:.1%}")
```

### 3.4 超时槽位清理

```python
# 获取超时的执行槽位
timeout_slots = controller.get_timeout_slots()
for slot in timeout_slots:
    print(f"超时槽位: {slot.slot_id}, 工具: {slot.tool_name}, 已运行: {slot.elapsed_time():.1f}s")

# 取消超时槽位
cancelled = await controller.cancel_timeout_slots()
print(f"已取消 {len(cancelled)} 个超时槽位")
```

### 3.5 Prometheus 指标导出（示例）

```python
from prometheus_client import Gauge, Counter

# 定义指标
tool_concurrent_gauge = Gauge('tool_concurrent_count', 'Current concurrent tool executions')
tool_queue_gauge = Gauge('tool_queue_length', 'Tool execution queue length')
tool_execution_counter = Counter('tool_executions_total', 'Total tool executions', ['tool_name', 'status'])

# 更新指标
def update_prometheus_metrics():
    metrics = controller.get_metrics()
    tool_concurrent_gauge.set(metrics.current_concurrent)
    tool_queue_gauge.set(metrics.queue_length)

# 在执行完成时记录
def on_execution_complete(result: ToolExecutionResult):
    status = "success" if result.is_success else "failure"
    tool_execution_counter.labels(tool_name=result.tool_name, status=status).inc()
```

---

## 4. 故障排查

### 4.1 常见问题

#### 工具加载失败

```python
# 检查加载错误
for name, error in engine.load_errors:
    print(f"❌ {name}: {error}")

# 常见原因：
# 1. YAML 语法错误
# 2. 必填字段缺失（name, version, description, category）
# 3. 参数类型不支持
# 4. 文件编码问题（应使用 UTF-8）
```

#### 参数验证失败

```python
result = engine.validate_params("my_tool", {"invalid": "params"})
if not result.is_valid:
    for error in result.errors:
        print(f"❌ 参数 {error.parameter_name}: {error.message}")
```

#### 执行器未找到

```python
# 检查已注册的执行器
print(f"已注册执行器: {list(engine._executors.keys())}")

# 检查工具的 handler 配置
tool = engine.get("my_tool")
if tool:
    handler = tool.implementation_config.get("handler", tool.name)
    print(f"工具 handler: {handler}")
    if handler not in engine._executors:
        print(f"❌ 执行器 {handler} 未注册")
```

#### 执行超时

```python
# 检查超时配置
print(f"默认超时: {context.timeout}s")

# 增加超时时间
context = ToolExecutionContext(
    caller_id="test",
    timeout=60.0,  # 增加到 60 秒
)
```

### 4.2 日志配置

```python
import logging

# 启用 ToolEngine 调试日志
logging.getLogger("src.domain.services.tool_engine").setLevel(logging.DEBUG)
logging.getLogger("src.domain.services.tool_executor").setLevel(logging.DEBUG)
logging.getLogger("src.domain.services.tool_concurrency_controller").setLevel(logging.DEBUG)
```

### 4.3 查询调用记录

```python
# 查询失败的调用
failed_records = await knowledge_store.query_failed(limit=10)
for record in failed_records:
    print(f"❌ {record.tool_name} @ {record.created_at}")
    print(f"   错误: {record.error}")
    print(f"   参数: {record.params}")

# 查询特定会话的调用
records = await knowledge_store.query_by_conversation("conv_001")
for record in records:
    status = "✅" if record.is_success else "❌"
    print(f"{status} {record.tool_name} ({record.execution_time:.3f}s)")
```

---

## 5. 性能调优

### 5.1 并发配置优化

```python
# 根据系统资源调整并发数
import os

cpu_count = os.cpu_count() or 4

config = ConcurrencyConfig(
    max_concurrent=cpu_count * 2,  # CPU 核心数的 2 倍
    queue_size=cpu_count * 10,     # 队列大小
    default_timeout=30.0,
)
```

### 5.2 分桶限流优化

```python
# 根据工具特性配置分桶
config = ConcurrencyConfig(
    max_concurrent=20,
    bucket_limits={
        "http": 10,      # HTTP 工具：IO 密集，可以多并发
        "ai": 2,         # AI 工具：资源密集，限制并发
        "database": 5,   # 数据库工具：连接池限制
        "file": 3,       # 文件工具：磁盘 IO 限制
    }
)
```

### 5.3 超时配置

```python
# 根据工具类型设置不同超时
TOOL_TIMEOUTS = {
    "http_request": 30.0,    # HTTP 请求 30 秒
    "ai_completion": 120.0,  # AI 生成 2 分钟
    "database_query": 60.0,  # 数据库查询 1 分钟
    "file_process": 300.0,   # 文件处理 5 分钟
}

def get_timeout(tool_name: str) -> float:
    return TOOL_TIMEOUTS.get(tool_name, 30.0)
```

### 5.4 知识库清理

```python
# 定期清理旧记录
from datetime import datetime, timedelta

async def cleanup_old_records():
    cutoff = datetime.now(UTC) - timedelta(days=7)
    records = await knowledge_store.query_by_time_range(end_time=cutoff)

    for record in records:
        await knowledge_store.delete(record.record_id)

    print(f"已清理 {len(records)} 条旧记录")
```

---

## 附录 A：运维检查清单

### 日常检查

- [ ] 检查工具加载错误 (`engine.load_errors`)
- [ ] 检查并发指标 (`controller.get_metrics()`)
- [ ] 检查队列积压情况
- [ ] 检查失败调用记录

### 部署前检查

- [ ] 验证所有 YAML 配置文件语法正确
- [ ] 验证所有执行器已注册
- [ ] 运行工具单元测试
- [ ] 运行工具集成测试

### 故障恢复

- [ ] 检查日志定位问题
- [ ] 查询知识库中的失败记录
- [ ] 检查并发控制器状态
- [ ] 必要时重启服务并重新加载工具

---

## 附录 B：命令速查

```bash
# 运行工具相关测试
pytest tests/unit/domain/services/test_tool_*.py -v
pytest tests/integration/test_tool_*.py -v

# 验证工具配置
python -m scripts.validate_tool_configs

# 查看工具统计
python -c "
from src.domain.services.tool_engine import ToolEngine, ToolEngineConfig
import asyncio

async def main():
    engine = ToolEngine(ToolEngineConfig())
    await engine.load()
    stats = engine.get_statistics()
    print(f'总工具数: {stats[\"total_tools\"]}')
    print(f'按分类: {stats[\"by_category\"]}')
    print(f'加载错误: {stats[\"load_errors\"]}')

asyncio.run(main())
"
```
