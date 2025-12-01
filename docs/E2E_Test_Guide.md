# E2E 测试指南：Agent → Workflow 自动转换

## 测试目标

验证从创建 Agent 到自动生成 Workflow 并跳转到编辑器的完整用户流程。

---

## 前置条件

### 1. 环境检查

- ✅ 后端服务运行在 `http://localhost:8000`
- ✅ 前端服务运行在 `http://127.0.0.1:5174`
- ✅ 数据库已初始化（alembic upgrade head）
- ✅ 环境变量已配置（.env 文件）

### 2. 检查服务状态

```bash
# 后端健康检查
curl http://localhost:8000/api/health

# 前端访问测试
# 浏览器打开 http://127.0.0.1:5174
```

---

## 测试场景 1：基本流程 - 创建销售分析 Agent

### 测试步骤

#### Step 1: 打开创建 Agent 页面

1. 浏览器访问：`http://127.0.0.1:5174`
2. 导航到"创建 Agent"页面

**预期结果：**
- ✅ 页面加载成功
- ✅ 显示三个表单字段：起点、目的、名称（可选）
- ✅ 显示"创建 Agent"按钮

#### Step 2: 填写表单

输入以下测试数据：

```
起点（当前状态）：
我有一个CSV文件，包含过去一年的销售数据，包括日期、产品名称、销售额、销售地区等字段

目的（期望结果）：
分析销售数据，找出销售趋势和热门产品，生成可视化报告并导出为PDF

名称（可选）：
销售数据分析Agent
```

**预期结果：**
- ✅ 表单接受输入
- ✅ 字符计数器正常显示
- ✅ 必填字段验证（长度 10-500）

#### Step 3: 提交表单

1. 点击"创建 Agent"按钮

**预期结果（Loading阶段）：**
- ✅ 按钮变为 Loading 状态（禁用）
- ✅ 显示加载消息：`"AI 正在为您生成智能工作流，请稍候..."`
- ✅ 消息不会自动关闭（duration: 0）

#### Step 4: 观察响应

**预期结果（成功响应）：**
- ✅ Loading 消息关闭
- ✅ 显示成功消息：`"Agent 创建成功！已自动生成 X 个任务节点，正在跳转到编辑器..."`
- ✅ 成功消息显示 2 秒后自动关闭
- ✅ 表单重置（所有字段清空）

#### Step 5: 自动跳转

**预期结果（500ms后）：**
- ✅ 页面自动跳转到 `/workflows/{workflow_id}/edit`
- ✅ URL 包含有效的 workflow_id（UUID格式）

#### Step 6: 验证 Workflow 编辑器

**预期结果（编辑器页面）：**
- ✅ ReactFlow 画布加载成功
- ✅ 显示自动生成的节点：
  - 1 个 START 节点（名称："开始"）
  - N 个 Task 节点（根据 LLM 生成）
  - 1 个 END 节点（名称："结束"）
- ✅ 节点水平排列（间距 200px）
- ✅ 所有节点垂直居中（y=250）
- ✅ 节点之间有边连接（START → Task1 → Task2 → ... → END）

#### Step 7: 检查节点类型推断

**预期节点类型（基于关键词）：**

根据测试数据，LLM 可能生成以下任务：

| 任务名称示例 | 预期节点类型 | 推断规则 |
|------------|------------|---------|
| 读取CSV文件 | FILE | 包含"读取"关键词 |
| 分析销售趋势 | LLM | 包含"分析"关键词 |
| 提取热门产品 | LLM | 包含"提取"关键词 |
| 生成可视化图表 | PROMPT | 包含"生成"关键词 |
| 导出PDF报告 | FILE | 包含"导出"关键词 |

**验证方法：**
1. 点击每个节点
2. 查看节点配置面板
3. 确认节点类型与任务描述匹配

#### Step 8: 检查节点配置

**LLM 节点配置示例：**
```json
{
  "model": "kimi",
  "temperature": 0.7,
  "prompt": "分析销售数据，找出销售趋势"
}
```

**FILE 节点配置示例：**
```json
{
  "path": "",
  "operation": "read"
}
```

**HTTP 节点配置示例：**
```json
{
  "method": "GET",
  "url": "",
  "headers": {}
}
```

---

## 测试场景 2：错误处理 - 空字段提交

### 测试步骤

1. 打开创建 Agent 页面
2. 只填写"起点"字段（10+ 字符）
3. 点击"创建 Agent"

**预期结果：**
- ✅ 表单阻止提交
- ✅ "目的"字段显示错误：`"目的描述是必填项"`
- ✅ 错误字段高亮显示
- ✅ 不发送 API 请求

---

## 测试场景 3：错误处理 - 后端错误

### 模拟步骤

1. 停止后端服务
2. 填写有效表单数据
3. 提交表单

**预期结果：**
- ✅ 显示 Loading 消息
- ✅ Loading 消息关闭
- ✅ 显示错误消息：`"创建失败：{错误详情}"`
- ✅ 错误消息持续 5 秒
- ✅ 表单不重置（用户可以重试）
- ✅ 不跳转页面

---

## 测试场景 4：Workflow 生成失败降级处理

### 模拟步骤

（需要修改后端代码模拟 workflow_id 为 null）

**预期结果：**
- ✅ 显示警告消息：`"Agent 已创建，但工作流生成失败。您可以稍后手动创建工作流。"`
- ✅ 警告消息持续 5 秒
- ✅ 不跳转到编辑器
- ✅ 表单重置

---

## 测试场景 5：复杂场景 - 多类型任务

### 测试数据

```
起点：
我有一个需要监控的API接口，需要每小时调用一次获取数据

目的：
调用天气API获取数据，使用AI分析数据趋势，存储到数据库，并发送邮件通知

名称：
天气监控Agent
```

**预期生成节点：**
1. START 节点
2. HTTP 节点（"调用天气API"）
3. LLM 节点（"分析数据趋势"）
4. DATABASE 节点（"存储到数据库"）
5. NOTIFICATION 节点（"发送邮件通知"）
6. END 节点

**验证点：**
- ✅ 6 个节点 = 5 条边
- ✅ 边正确连接：START → HTTP → LLM → DATABASE → NOTIFICATION → END
- ✅ 每个节点类型正确
- ✅ 节点间距均匀（200px）

---

## API 层测试（可选）

### 使用 curl 测试后端

```bash
# 创建 Agent（应返回 workflow_id）
curl -X POST http://localhost:8000/api/agents \
  -H "Content-Type: application/json" \
  -d @test_create_agent.json

# 预期响应
{
  "id": "agent-xxx",
  "start": "...",
  "goal": "...",
  "name": "...",
  "workflow_id": "workflow-xxx",  # 关键：不应为 null
  "tasks": [
    {
      "id": "task-1",
      "name": "...",
      "description": "...",
      ...
    }
  ],
  "created_at": "...",
  "updated_at": "..."
}

# 验证 Workflow 已保存
curl http://localhost:8000/api/workflows/{workflow_id}

# 预期响应
{
  "id": "workflow-xxx",
  "name": "Agent-销售数据分析Agent",
  "description": "起点：... 目的：...",
  "nodes": [...],  # 应包含多个节点
  "edges": [...],  # 应包含多条边
  "source": "feagent",
  "source_id": "agent-xxx"
}
```

---

## 数据库验证（可选）

### 查询数据库确认数据持久化

```bash
# 连接 SQLite
sqlite3 agent_data.db

# 查询 Agent
SELECT id, name, start, goal FROM agents ORDER BY created_at DESC LIMIT 1;

# 查询关联的 Tasks
SELECT id, name, description, agent_id FROM tasks WHERE agent_id = 'agent-xxx';

# 查询 Workflow
SELECT id, name, source, source_id FROM workflows WHERE source_id = 'agent-xxx';

# 查询 Workflow Nodes
SELECT id, name, type, workflow_id FROM workflow_nodes WHERE workflow_id = 'workflow-xxx';

# 查询 Workflow Edges
SELECT id, source_node_id, target_node_id FROM workflow_edges WHERE workflow_id = 'workflow-xxx';
```

**预期结果：**
- ✅ Agent 记录存在
- ✅ Tasks 记录存在（多条）
- ✅ Workflow 记录存在
- ✅ Workflow Nodes 记录存在（数量 = Tasks数量 + 2）
- ✅ Workflow Edges 记录存在（数量 = Nodes数量 - 1）

---

## 性能测试

### 测试创建时间

记录从提交表单到跳转编辑器的总时间：

- **目标时间：< 5 秒**（包括 LLM 调用）
- **可接受时间：< 10 秒**

**测量方法：**
1. 打开浏览器开发者工具（F12）
2. 切换到 Network 标签
3. 提交表单
4. 记录 POST /api/agents 请求的响应时间

**优化建议（如果超时）：**
- [ ] 将 Workflow 生成改为异步任务
- [ ] 使用后台任务队列（Celery/RQ）
- [ ] 前端轮询或 SSE 更新状态

---

## 兼容性测试

### 浏览器测试

测试以下浏览器：
- [ ] Chrome（最新版）
- [ ] Firefox（最新版）
- [ ] Safari（最新版）
- [ ] Edge（最新版）

### 移动端测试

- [ ] 响应式布局是否正常
- [ ] 表单输入是否流畅
- [ ] 跳转是否正常

---

## 测试报告模板

### 测试记录表

| 测试场景 | 测试时间 | 状态 | 响应时间 | 备注 |
|---------|---------|------|---------|------|
| 场景1：基本流程 | 2025-12-01 10:00 | ✅ PASS | 3.2s | 生成5个节点 |
| 场景2：空字段错误 | 2025-12-01 10:05 | ✅ PASS | N/A | 表单验证正常 |
| 场景3：后端错误 | 2025-12-01 10:10 | ✅ PASS | N/A | 错误提示正确 |
| 场景4：Workflow失败 | 2025-12-01 10:15 | ⚠️ SKIP | N/A | 需修改代码模拟 |
| 场景5：多类型任务 | 2025-12-01 10:20 | ✅ PASS | 4.5s | 生成6个节点 |

### 缺陷记录

| 缺陷ID | 严重性 | 描述 | 复现步骤 | 状态 |
|-------|-------|------|---------|------|
| BUG-001 | 高 | Workflow 未保存到数据库 | ... | ✅ 已修复 |
| BUG-002 | 中 | 成功消息显示时间过短 | ... | ✅ 已优化 |

---

## 自动化测试（下一步）

### 使用 Playwright 编写 E2E 测试

```typescript
// e2e/create-agent-workflow.spec.ts
import { test, expect } from '@playwright/test';

test('创建 Agent 并自动跳转到 Workflow 编辑器', async ({ page }) => {
  // 1. 打开创建页面
  await page.goto('http://127.0.0.1:5174/agents/create');

  // 2. 填写表单
  await page.fill('[name="start"]', '我有一个CSV文件，包含销售数据');
  await page.fill('[name="goal"]', '分析数据并生成报告');
  await page.fill('[name="name"]', '销售分析Agent');

  // 3. 提交表单
  await page.click('button[type="submit"]');

  // 4. 等待 Loading 消息出现
  await expect(page.locator('text=AI 正在为您生成智能工作流')).toBeVisible();

  // 5. 等待成功消息
  await expect(page.locator('text=Agent 创建成功')).toBeVisible({ timeout: 10000 });

  // 6. 等待跳转
  await page.waitForURL(/\/workflows\/.*\/edit/, { timeout: 5000 });

  // 7. 验证 Workflow 编辑器加载
  await expect(page.locator('.react-flow')).toBeVisible();

  // 8. 验证节点存在
  const nodes = await page.locator('.react-flow__node').count();
  expect(nodes).toBeGreaterThan(2); // 至少有 START 和 END
});
```

---

## 测试清单（Checklist）

### 功能测试
- [ ] Agent 创建成功
- [ ] Workflow 自动生成
- [ ] workflow_id 正确返回
- [ ] Tasks 正确保存
- [ ] 页面自动跳转
- [ ] 节点正确显示
- [ ] 边正确连接
- [ ] 节点类型推断准确

### UI/UX 测试
- [ ] Loading 消息显示
- [ ] 成功消息显示任务数量
- [ ] 错误消息详细且友好
- [ ] 表单验证提示清晰
- [ ] 跳转延迟适当（500ms）

### 数据持久化测试
- [ ] Agent 保存到数据库
- [ ] Tasks 保存到数据库
- [ ] Workflow 保存到数据库
- [ ] Nodes 保存到数据库
- [ ] Edges 保存到数据库

### 错误处理测试
- [ ] 表单验证错误
- [ ] 网络错误
- [ ] 后端错误
- [ ] Workflow 生成失败降级

### 性能测试
- [ ] 响应时间 < 10s
- [ ] 页面无卡顿
- [ ] 内存无泄漏

---

## 测试结论

### 通过标准

所有以下条件必须满足：
1. ✅ 所有核心场景测试通过（场景 1, 2, 3, 5）
2. ✅ 数据正确持久化到数据库
3. ✅ 无严重性缺陷（P0, P1）
4. ✅ 响应时间在可接受范围内

### 下一步行动

- [ ] 补充自动化测试脚本
- [ ] 性能优化（如需要）
- [ ] 功能增强（更多节点类型）
- [ ] 用户体验优化（根据反馈）

---

**文档版本：** 1.0
**创建日期：** 2025-12-01
**最后更新：** 2025-12-01
**测试负责人：** Claude Code
