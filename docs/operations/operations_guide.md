# Feagent 多 Agent 系统运维指南

> 版本: 1.0.0
> 更新日期: 2025-01-22
> 适用于: Feagent V2 多 Agent 协作系统

---

## 目录

1. [系统启动与停止](#1-系统启动与停止)
2. [健康检查与监控](#2-健康检查与监控)
3. [任务管理](#3-任务管理)
4. [日志查看与分析](#4-日志查看与分析)
5. [执行总结查询](#5-执行总结查询)
6. [故障恢复](#6-故障恢复)
7. [常见问题排查](#7-常见问题排查)

---

## 1. 系统启动与停止

### 1.1 启动系统

```bash
# 启动后端服务
uvicorn src.interfaces.api.main:app --host 0.0.0.0 --port 8000

# 生产环境（多 worker）
uvicorn src.interfaces.api.main:app --host 0.0.0.0 --port 8000 --workers 4

# 开发环境（热重载）
uvicorn src.interfaces.api.main:app --reload --port 8000
```

### 1.2 停止系统

```bash
# 优雅停止（等待当前任务完成）
kill -SIGTERM <pid>

# 强制停止
kill -SIGKILL <pid>
```

### 1.3 服务状态检查

```bash
# 检查进程
ps aux | grep uvicorn

# 检查端口
netstat -tlnp | grep 8000
```

---

## 2. 健康检查与监控

### 2.1 健康检查端点

```bash
# 基础健康检查
curl http://localhost:8000/health

# Coordinator 状态
curl http://localhost:8000/api/coordinator/status

# 详细系统状态
curl http://localhost:8000/api/coordinator/status/detail
```

### 2.2 监控指标

系统提供以下监控指标：

| 指标 | 端点 | 说明 |
|------|------|------|
| 活跃会话数 | `/api/coordinator/status` | 当前活跃的 WebSocket 会话 |
| 运行中工作流 | `/api/coordinator/status` | 正在执行的工作流数量 |
| 总压缩次数 | `/api/coordinator/status/detail` | 八段压缩器执行次数 |
| 存储上下文数 | `/api/coordinator/status/detail` | 已存储的压缩上下文数 |

### 2.3 健康检查脚本

```python
#!/usr/bin/env python
"""健康检查脚本"""
import httpx
import sys

def check_health():
    try:
        resp = httpx.get("http://localhost:8000/health", timeout=5)
        if resp.status_code == 200:
            print("✅ 系统健康")
            return 0
        else:
            print(f"⚠️ 系统异常: {resp.status_code}")
            return 1
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return 2

if __name__ == "__main__":
    sys.exit(check_health())
```

---

## 3. 任务管理

### 3.1 查看活跃任务

```bash
# 获取所有活跃工作流
curl http://localhost:8000/api/workflows/active

# 获取特定会话的任务
curl http://localhost:8000/api/sessions/{session_id}/workflows
```

### 3.2 取消任务

```bash
# 取消指定工作流
curl -X POST http://localhost:8000/api/workflows/{workflow_id}/cancel

# 取消会话的所有任务
curl -X POST http://localhost:8000/api/sessions/{session_id}/cancel-all
```

### 3.3 任务状态查询

```python
# Python API 示例
from src.domain.agents.coordinator_agent import CoordinatorAgent

coordinator = CoordinatorAgent()

# 查询工作流状态
status = coordinator.get_workflow_status("workflow_123")
print(f"状态: {status['status']}")
print(f"进度: {status['progress']}")
print(f"当前节点: {status['current_node']}")
```

---

## 4. 日志查看与分析

### 4.1 日志配置

日志配置在 `src/interfaces/api/main.py`:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/agent.log"),
        logging.StreamHandler()
    ]
)
```

### 4.2 日志级别说明

| 级别 | 说明 | 使用场景 |
|------|------|----------|
| DEBUG | 调试信息 | 开发环境详细跟踪 |
| INFO | 一般信息 | 正常操作记录 |
| WARNING | 警告信息 | 潜在问题提示 |
| ERROR | 错误信息 | 执行失败记录 |

### 4.3 关键日志模式

```bash
# 查看 Agent 通信日志
grep "AgentChannelBridge" logs/agent.log

# 查看工作流执行日志
grep "WorkflowAgent" logs/agent.log

# 查看执行总结日志
grep "ExecutionSummary" logs/agent.log

# 查看压缩器日志
grep "PowerCompressor" logs/agent.log

# 查看错误日志
grep "ERROR" logs/agent.log | tail -50
```

### 4.4 实时日志监控

```bash
# 实时查看所有日志
tail -f logs/agent.log

# 只看错误
tail -f logs/agent.log | grep --line-buffered "ERROR"

# 查看特定工作流
tail -f logs/agent.log | grep --line-buffered "workflow_id=xxx"
```

---

## 5. 执行总结查询

### 5.1 查询压缩后的上下文

```python
from src.domain.agents.coordinator_agent import CoordinatorAgent

coordinator = CoordinatorAgent()

# 查询完整压缩上下文
context = coordinator.query_compressed_context("workflow_123")
if context:
    print(f"工作流: {context['workflow_id']}")
    print(f"压缩时间: {context['compressed_at']}")
    print(f"段数: {len(context['segments'])}")
```

### 5.2 查询子任务错误

```python
# 查询特定工作流的错误
errors = coordinator.query_subtask_errors("workflow_123")
for error in errors:
    print(f"错误类型: {error['error_type']}")
    print(f"节点: {error['node_id']}")
    print(f"消息: {error['message']}")
    print(f"发生时间: {error['occurred_at']}")
    print("---")
```

### 5.3 查询未解决问题

```python
# 查询待处理问题
issues = coordinator.query_unresolved_issues("workflow_123")
for issue in issues:
    print(f"问题: {issue['description']}")
    print(f"来源: {issue['source_node']}")
    print(f"严重程度: {issue['severity']}")
    print("---")
```

### 5.4 查询下一步计划

```python
# 查询建议的下一步
next_steps = coordinator.query_next_plan("workflow_123")
for step in next_steps:
    print(f"步骤: {step['description']}")
    print(f"优先级: {step['priority']}")
    print(f"依赖: {step['dependencies']}")
    print("---")
```

### 5.5 REST API 查询

```bash
# 查询压缩上下文
curl http://localhost:8000/api/coordinator/context/{workflow_id}

# 查询错误列表
curl http://localhost:8000/api/coordinator/context/{workflow_id}/errors

# 查询未解决问题
curl http://localhost:8000/api/coordinator/context/{workflow_id}/issues

# 查询下一步计划
curl http://localhost:8000/api/coordinator/context/{workflow_id}/next-plan
```

---

## 6. 故障恢复

### 6.1 任务中断恢复

当工作流执行中断时（如系统重启、网络故障），可以通过以下方式恢复：

#### 方式一：自动恢复（推荐）

系统启动时会自动检查未完成的工作流：

```python
# coordinator_agent.py 启动时自动执行
async def recover_interrupted_workflows(self):
    """恢复中断的工作流"""
    # 查找状态为 RUNNING 的工作流
    interrupted = self._find_interrupted_workflows()

    for workflow_id in interrupted:
        try:
            await self._resume_workflow(workflow_id)
            logger.info(f"已恢复工作流: {workflow_id}")
        except Exception as e:
            logger.error(f"恢复失败: {workflow_id}, {e}")
```

#### 方式二：手动恢复

```bash
# 1. 查询中断的工作流
curl http://localhost:8000/api/workflows?status=interrupted

# 2. 手动触发恢复
curl -X POST http://localhost:8000/api/workflows/{workflow_id}/resume

# 3. 从特定节点重新开始
curl -X POST http://localhost:8000/api/workflows/{workflow_id}/resume \
  -H "Content-Type: application/json" \
  -d '{"from_node": "node_3"}'
```

#### 方式三：Python API 恢复

```python
from src.domain.agents.coordinator_agent import CoordinatorAgent

coordinator = CoordinatorAgent()

# 恢复中断的工作流
async def manual_recover(workflow_id: str):
    # 获取最后状态
    last_state = coordinator.get_workflow_checkpoint(workflow_id)

    if last_state:
        # 从检查点恢复
        await coordinator.resume_workflow(
            workflow_id=workflow_id,
            from_node=last_state["last_completed_node"],
            context=last_state["context"]
        )
```

### 6.2 数据一致性修复

```python
# 修复不一致的状态
async def repair_workflow_state(workflow_id: str):
    coordinator = CoordinatorAgent()

    # 获取实际执行状态
    actual_state = await coordinator._get_actual_node_states(workflow_id)

    # 更新存储的状态
    coordinator._sync_workflow_state(workflow_id, actual_state)
```

### 6.3 会话重连

WebSocket 断开后重连处理：

```python
# 客户端重连逻辑
async def reconnect_session(session_id: str, user_id: str):
    channel = AgentWebSocketChannel()

    # 检查是否有未完成的工作流
    pending_workflows = coordinator.get_session_workflows(session_id)

    # 重新订阅事件
    for wf_id in pending_workflows:
        await channel.subscribe_workflow_events(session_id, wf_id)

    # 发送最新状态
    for wf_id in pending_workflows:
        status = coordinator.get_workflow_status(wf_id)
        await channel.send_status_update(session_id, status)
```

---

## 7. 常见问题排查

### 7.1 WebSocket 连接失败

**症状**: 客户端无法建立 WebSocket 连接

**检查步骤**:
```bash
# 1. 确认服务运行
curl http://localhost:8000/health

# 2. 检查 WebSocket 端点
wscat -c ws://localhost:8000/ws

# 3. 检查防火墙/代理配置
# 确保 WebSocket 升级请求未被拦截
```

**解决方案**:
- 确保 nginx/代理正确配置 WebSocket 支持
- 检查 CORS 配置是否允许 WebSocket

### 7.2 工作流执行超时

**症状**: 工作流长时间处于 RUNNING 状态

**检查步骤**:
```bash
# 1. 查看当前节点
curl http://localhost:8000/api/workflows/{workflow_id}/status

# 2. 检查节点日志
grep "workflow_id={workflow_id}" logs/agent.log | tail -100

# 3. 检查外部依赖
# 如 LLM API、数据库连接等
```

**解决方案**:
```python
# 强制超时处理
coordinator.force_timeout_workflow(workflow_id, reason="手动超时")

# 或跳过当前节点
coordinator.skip_current_node(workflow_id, reason="节点无响应")
```

### 7.3 压缩上下文丢失

**症状**: 查询 compressed_context 返回 None

**检查步骤**:
```python
# 1. 检查压缩是否执行
stats = coordinator.get_power_compression_statistics()
print(f"总压缩次数: {stats['total_compressions']}")

# 2. 检查存储
stored = list(coordinator._compressed_contexts.keys())
print(f"已存储的工作流: {stored}")
```

**解决方案**:
```python
# 手动触发压缩
summary = coordinator.get_workflow_summary(workflow_id)
if summary:
    await coordinator.compress_and_store(summary)
```

### 7.4 Agent 间通信异常

**症状**: ConversationAgent 与 WorkflowAgent 消息传递失败

**检查步骤**:
```bash
# 1. 查看通信日志
grep "AgentChannelBridge" logs/agent.log | tail -50

# 2. 检查消息队列状态
curl http://localhost:8000/api/coordinator/message-queue/status
```

**解决方案**:
```python
# 重置通信桥接
bridge = coordinator._channel_bridge
await bridge.reset_connection(session_id)

# 重新注册消息处理器
coordinator._register_message_handlers()
```

### 7.5 内存使用过高

**症状**: 服务内存持续增长

**检查步骤**:
```bash
# 1. 检查进程内存
ps -o pid,rss,vsz,comm -p <pid>

# 2. 检查上下文存储
curl http://localhost:8000/api/coordinator/status/detail
```

**解决方案**:
```python
# 清理过期上下文
coordinator.cleanup_expired_contexts(max_age_hours=24)

# 限制存储数量
coordinator.set_max_stored_contexts(100)
```

---

## 附录 A: 配置参考

### 环境变量

```bash
# 基础配置
LOG_LEVEL=INFO
DATABASE_URL=sqlite:///./agent_data.db

# Agent 配置
AGENT_TIMEOUT_SECONDS=300
MAX_CONCURRENT_WORKFLOWS=10
COMPRESSION_ENABLED=true

# WebSocket 配置
WS_HEARTBEAT_INTERVAL=30
WS_CONNECTION_TIMEOUT=60
```

### 日志级别配置

```python
# 按模块配置日志级别
LOGGING_CONFIG = {
    "coordinator_agent": "INFO",
    "workflow_agent": "INFO",
    "conversation_agent": "INFO",
    "power_compressor": "DEBUG",
    "agent_channel": "WARNING",
}
```

---

## 附录 B: 运维检查清单

### 日常检查

- [ ] 检查服务健康状态
- [ ] 查看错误日志
- [ ] 检查活跃工作流数量
- [ ] 确认内存使用正常

### 周期性维护

- [ ] 清理过期的压缩上下文
- [ ] 归档历史日志
- [ ] 检查数据库大小
- [ ] 更新安全补丁

### 发布前检查

- [ ] 运行完整测试套件
- [ ] 检查配置变更
- [ ] 验证回滚方案
- [ ] 通知相关团队

---

## 联系与支持

- **技术文档**: `docs/architecture/multi_agent_collaboration_guide.md`
- **API 文档**: `http://localhost:8000/docs`
- **问题反馈**: 提交 Issue 到项目仓库
