# P1 补充文档：测试夹具、清理策略、失败归因与时间估算

---

## P1-1: 测试夹具示例（主子图 + 孤立子图）

### 完整 JSON Fixture

```json
{
  "workflow_id": "wf_fixture_isolated_nodes",
  "name": "[TEST] Workflow with Isolated Nodes",
  "project_id": "e2e_project",
  "nodes": [
    {
      "id": "start",
      "type": "START",
      "name": "Start",
      "position": { "x": 100, "y": 100 }
    },
    {
      "id": "node_A",
      "type": "PYTHON",
      "name": "Main Node A",
      "config": {
        "code": "result = {'value': input_data.get('value', 0) + 1}"
      },
      "position": { "x": 300, "y": 100 }
    },
    {
      "id": "end",
      "type": "END",
      "name": "End",
      "position": { "x": 500, "y": 100 }
    },
    {
      "id": "isolated_no_incoming",
      "type": "PYTHON",
      "name": "[ISOLATED] No Incoming Edges",
      "config": {
        "code": "result = {'isolated': True}"
      },
      "position": { "x": 300, "y": 300 }
    },
    {
      "id": "isolated_no_outgoing",
      "type": "PYTHON",
      "name": "[ISOLATED] No Outgoing Edges",
      "config": {
        "code": "result = {'isolated': True}"
      },
      "position": { "x": 300, "y": 500 }
    }
  ],
  "edges": [
    {
      "id": "edge_1",
      "source_node_id": "start",
      "target_node_id": "node_A"
    },
    {
      "id": "edge_2",
      "source_node_id": "node_A",
      "target_node_id": "end"
    },
    {
      "id": "orphan_edge_incoming_to_isolated",
      "source_node_id": "start",
      "target_node_id": "isolated_no_outgoing"
    }
  ],
  "metadata": {
    "test_seed": true,
    "fixture_type": "with_isolated_nodes",
    "main_subgraph": ["start", "node_A", "end"],
    "isolated_nodes": ["isolated_no_incoming"],
    "partially_connected": ["isolated_no_outgoing"]
  }
}
```

### 使用场景（UX-WF-101）

```python
# tests/e2e/test_isolated_nodes_restriction.py
def test_chat_modify_isolated_node_rejected(seed_workflow, chat_api):
    # 1. 创建包含孤立节点的 workflow
    wf = seed_workflow("with_isolated_nodes")

    # 2. 尝试通过 chat 修改孤立节点
    response = chat_api.send_message(
        workflow_id=wf["workflow_id"],
        message="请修改 isolated_no_incoming 节点的代码"
    )

    # 3. 断言被拒绝
    assert "workflow_modification_rejected" in response["error"]["code"]
    assert "仅允许操作 start->end 主连通子图" in response["error"]["message"]
    assert "isolated_no_incoming" in response["error"]["errors"][0]["ids"]
```

---

## P1-2: 副作用节点定义示例

### HTTP 副作用节点

```json
{
  "id": "http_side_effect",
  "type": "HTTP",
  "name": "External API Call",
  "config": {
    "url": "https://api.example.com/create",
    "method": "POST",
    "headers": {
      "Authorization": "Bearer <token>"
    },
    "body": {
      "data": "test"
    }
  },
  "metadata": {
    "has_side_effect": true,
    "side_effect_type": "external_write",
    "side_effect_description": "Creates a resource on external system"
  }
}
```

### DATABASE 副作用节点

```json
{
  "id": "db_side_effect",
  "type": "DATABASE",
  "name": "Insert Record",
  "config": {
    "connection_string": "postgresql://localhost/testdb",
    "query": "INSERT INTO users (name, email) VALUES ($1, $2)",
    "parameters": ["{{input.name}}", "{{input.email}}"]
  },
  "metadata": {
    "has_side_effect": true,
    "side_effect_type": "database_write"
  }
}
```

### TOOL 副作用节点（自定义工具）

```json
{
  "id": "tool_side_effect",
  "type": "TOOL",
  "name": "Send Email",
  "config": {
    "tool_id": "email_sender",
    "parameters": {
      "to": "user@example.com",
      "subject": "Test",
      "body": "This is a test email"
    }
  },
  "metadata": {
    "has_side_effect": true,
    "side_effect_type": "notification"
  }
}
```

### 副作用识别规则（后端）

```python
# src/application/services/workflow_run_execution_entry.py (已存在)
_SIDE_EFFECT_NODE_TYPES: frozenset[NodeType] = frozenset({
    NodeType.TOOL,
    NodeType.HTTP,
    NodeType.HTTP_REQUEST,
    NodeType.DATABASE,
    # 未来可扩展：NodeType.FILE_WRITE, NodeType.NOTIFICATION
})

def _find_first_side_effect_node_id(*, workflow: Any) -> str | None:
    """拓扑排序后找到第一个副作用节点"""
    node_map = {node.id: node for node in workflow.nodes}
    sorted_ids = topological_sort_ids(
        node_ids=node_map.keys(),
        edges=((e.source_node_id, e.target_node_id) for e in workflow.edges),
    )
    for node_id in sorted_ids:
        node = node_map.get(node_id)
        if node and node.type in _SIDE_EFFECT_NODE_TYPES:
            return node_id
    return None
```

---

## P1-3: DB Seed 清理策略

### 策略 A: Pytest Fixture Scope（推荐）

```python
# tests/e2e/conftest.py
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="function")
def clean_db():
    """每个测试用例独立的 DB 清理"""
    engine = create_engine("sqlite:///./test.db")
    SessionLocal = sessionmaker(bind=engine)

    # 测试前清理
    with SessionLocal() as session:
        session.execute(text("DELETE FROM workflows WHERE metadata LIKE '%test_seed%'"))
        session.execute(text("DELETE FROM workflow_runs WHERE project_id = 'e2e_project'"))
        session.commit()

    yield

    # 测试后清理（可选，取决于是否需要保留失败用例的数据）
    with SessionLocal() as session:
        session.execute(text("DELETE FROM workflows WHERE metadata LIKE '%test_seed%'"))
        session.execute(text("DELETE FROM workflow_runs WHERE project_id = 'e2e_project'"))
        session.commit()


def test_example(clean_db, seed_workflow):
    # 测试逻辑...
    pass
```

### 策略 B: Transaction Rollback（更快但限制多）

```python
@pytest.fixture(scope="function")
def db_transaction():
    """使用事务回滚实现测试隔离（仅适用于单数据库、无异步提交场景）"""
    engine = create_engine("sqlite:///./test.db")
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection)

    yield SessionLocal()

    transaction.rollback()
    connection.close()
```

### 策略 C: Cleanup API（最灵活）

```python
# 使用 Seed API 的 cleanup 端点
def cleanup_test_workflows(cleanup_tokens: list[str]):
    import requests
    resp = requests.delete(
        "http://localhost:8000/api/test/workflows/cleanup",
        headers={"X-Test-Mode": "true"},
        json={"cleanup_tokens": cleanup_tokens}
    )
    resp.raise_for_status()
```

### 清理时机对比

| 策略 | 清理时机 | 优点 | 缺点 |
|---|---|---|---|
| Fixture Scope | 测试前/后 | 灵活，支持异步 | 需手动管理 |
| Transaction Rollback | 测试后自动回滚 | 最快，无残留 | 不支持异步提交、跨数据库 |
| Cleanup API | 测试后调用 API | 语义清晰，跨服务 | 依赖后端 API 可用 |

---

## P1-4: 失败归因速查表（前端 + 性能场景补充）

### 前端特定失败场景

| 现象（用户看到的） | 可能出问题的层 | 优先排查点（证据） |
|---|---|---|
| 画布空白/节点不渲染 | React 渲染错误 | 浏览器 Console 是否有 React Error；`useWorkflow` hook 是否返回数据 |
| 点击保存无响应 | 前端状态管理 | Redux/Zustand state 是否更新；Network 是否发出请求 |
| SSE 事件丢失/乱序 | SSE 解析/状态更新 | `useWorkflowExecution` 是否正确处理事件；Network 是否持续接收事件 |
| WebSocket 断开后未重连 | WebSocket 生命周期 | `useWebSocket` 重连逻辑是否触发；Network 是否显示 `ws://` 连接 |
| 节点状态不更新 | React 状态未触发重渲染 | `nodeStatusMap` 是否更新但 UI 未刷新；检查 `React.memo` 依赖 |
| 确认弹窗不出现 | 事件监听缺失 | `useWorkflowExecutionWithCallback` 是否注册 `onConfirmRequired`；SSE 是否收到 `workflow_confirm_required` |
| Replay 进度条卡死 | 事件分页/cursor 问题 | 检查 `GET /runs/{run_id}/events` 的 `next_cursor`；是否进入无限循环 |

### 性能相关失败场景

| 现象（用户看到的） | 可能出问题的层 | 优先排查点（证据） |
|---|---|---|
| 画布渲染卡顿（大工作流） | 前端渲染性能 | React DevTools Profiler；是否渲染了不必要的组件 |
| SSE 事件积压（大量节点） | 后端事件生成过快 | Network 是否有大量未处理的 `data:` 行；前端是否做了节流 |
| 执行超时（复杂 LLM 调用） | LLM 响应慢/超时配置 | 检查 LLM API 调用时长；是否达到 `timeout` 配置 |
| 前端内存泄漏 | WebSocket/SSE 未清理 | Chrome DevTools Memory Profiler；检查 `useEffect` cleanup |
| 回放加载慢（大 run） | 数据库查询慢/分页失效 | 检查 `GET /runs/{run_id}/events` 响应时间；数据库索引是否生效 |

---

## P1-5: 调整后的里程碑时间估算

### 原始估算（codex 版本）

| 里程碑 | 原估算 | 风险 |
|---|---|---|
| M0 | 1-2 天 | 低估：需前后端协同 |
| M1 | 1-2 天 | 偏乐观：Playwright 学习曲线 |
| M2 | 1-2 天 | 合理 |
| M3 | 持续演进 | 无具体时间 |

### 调整后估算（保守版本）

| 里程碑 | 任务 | 调整后工作量 | 风险缓冲 |
|---|---|---|---|
| **M0：确定性基础** | 加 data-testid + Seed API 设计 | **2-3 天** | +1 天：前端改造涉及多个组件 |
| **M1：Playwright P0 Smoke** | 实现 UX-WF-001~005（A 模式） | **3-5 天** | +2 天：环境搭建 + 调试 flaky 测试 |
| **M2：Hybrid 覆盖 P1** | UX-WF-101/102 + Mock 依赖 | **2-3 天** | +1 天：WireMock 配置 + 录制回放 |
| **M3：Full-real Nightly** | 1-3 条真实用例 | **2-3 天** | +1 天：真实 LLM 波动处理 |

**总计（保守）**：9-14 天（约 2-3 周）

### 并行化建议

如果前后端可并行开发：

| 阶段 | 前端任务 | 后端任务 | 并行工作量 |
|---|---|---|---|
| M0 | 添加 data-testid | 实现 Seed API + Fixture Factory | 2-3 天 |
| M1 | 编写 Playwright 用例 | 实现模式切换（LLM/HTTP Adapters） | 3-5 天 |
| M2 | 调试 flaky 测试 | 配置 WireMock + CI Pipeline | 2-3 天 |

**并行总计**：7-11 天（约 1.5-2 周）

---

## 验收标准（综合）

### P0 验收标准（必须通过）

- [ ] Seed API 返回 4 种 fixture，每种都能成功执行
- [ ] Playwright P0 用例（UX-WF-001~005）通过率 100%（模式 A）
- [ ] 副作用确认流程触发 → deny → 明确失败（无静默）
- [ ] Replay 能正确回放至少 10 个事件
- [ ] 所有 P0 data-testid 已添加且可访问

### P1 验收标准（应该通过）

- [ ] 主子图约束测试通过（孤立节点修改被拒绝）
- [ ] 保存校验失败返回结构化错误（至少 3 个字段）
- [ ] 模式切换（A/B/C）能通过环境变量无缝切换
- [ ] 清理策略能删除测试数据（残留率 < 5%）
- [ ] 失败归因速查表覆盖至少 15 个常见场景

### P2 验收标准（可选）

- [ ] Full-real 模式能运行 nightly 并记录失败报告
- [ ] 性能基线：P0 用例执行时间 < 30 秒（模式 A）
- [ ] CI Pipeline 集成（PR 触发 A 模式，nightly 触发 C 模式）

---

## 附录：Playwright 最佳实践

1. **等待策略**：
   ```typescript
   // ❌ 错误：固定时间等待
   await page.waitForTimeout(5000);

   // ✅ 正确：等待条件
   await expect(page.getByTestId('workflow-execution-status')).toContainText('completed');
   ```

2. **选择器稳定性**：
   ```typescript
   // ❌ 错误：脆弱的 CSS 选择器
   await page.locator('.button.primary.large').click();

   // ✅ 正确：稳定的 testid
   await page.getByTestId('workflow-run-button').click();
   ```

3. **隔离性**：
   ```typescript
   // ✅ 每个测试独立创建 workflow
   test('test case', async ({ seedWorkflow }) => {
     const wf = await seedWorkflow('main_subgraph_only');
     // 测试逻辑...
     // cleanup 自动触发
   });
   ```

4. **断言明确性**：
   ```typescript
   // ❌ 错误：模糊断言
   await expect(page.locator('text=Success')).toBeVisible();

   // ✅ 正确：明确断言
   await expect(page.getByTestId('workflow-save-status')).toHaveText('工作流保存成功');
   ```
