# UX-WF-005: 回放事件测试说明

## 测试目标
验证工作流执行完成后,能够正确回放事件序列,确保事件记录的完整性和回放功能的可用性。

## 测试场景

### 场景 1: 成功执行工作流并回放事件序列
**步骤**:
1. 使用 `seedWorkflow` fixture 创建 `main_subgraph_only` 类型的测试工作流
2. 打开工作流编辑器
3. 点击 RUN 按钮执行工作流
4. 等待执行完成 (监听执行状态变化)
5. 捕获 `run_id`
6. 调用 `GET /api/runs/{run_id}/events?channel=execution` API
7. 验证返回事件序列 (≥ 10 个事件)
8. 验证事件类型完整性 (包含 workflow_start, node_start, node_complete, workflow_complete)
9. 点击回放按钮 (`replay-run-button`)
10. 验证回放界面显示事件列表

**验收标准**:
- ✅ 成功捕获 run_id
- ✅ Events API 返回 200 OK
- ✅ 事件数量 ≥ 10
- ✅ 包含关键事件类型 (workflow_start, node_start, node_complete, workflow_complete/error)
- ✅ 回放按钮可点击并启动回放
- ✅ 事件列表正确显示

### 场景 2: 回放按钮在无执行记录时被禁用
**步骤**:
1. 创建测试工作流但不执行
2. 验证回放按钮存在但被禁用

**验收标准**:
- ✅ 回放按钮为 disabled 状态

### 场景 3: 事件分页功能验证
**步骤**:
1. 执行工作流并等待完成
2. 使用 `limit=5` 参数获取第一页事件
3. 使用 `cursor` 参数获取第二页事件
4. 验证分页逻辑正确 (无重复,顺序正确)

**验收标准**:
- ✅ 分页参数正确工作
- ✅ cursor 分页无重复
- ✅ 事件顺序稳定

## 技术要点

### API 端点
```
GET /api/runs/{run_id}/events?channel=execution&limit=200
```

**响应结构**:
```json
{
  "run_id": "run_xxx",
  "events": [
    {
      "type": "workflow_start",
      "run_id": "run_xxx",
      ...
    },
    {
      "type": "node_start",
      "run_id": "run_xxx",
      "node_id": "node_xxx",
      ...
    },
    ...
  ],
  "next_cursor": 123,
  "has_more": false
}
```

### data-testid 选择器
- `workflow-run-button` - RUN 按钮
- `workflow-execution-status` - 执行状态指示器
- `replay-run-button` - 回放按钮
- `replay-event-list` - 回放事件列表 (可选)
- `execution-log-entry-{index}` - 执行日志项

### 关键事件类型
1. `workflow_start` - 工作流开始
2. `node_start` - 节点开始执行
3. `node_complete` - 节点执行完成
4. `workflow_complete` - 工作流完成
5. `workflow_error` - 工作流错误

## 运行测试

### 单独运行 UX-WF-005
```bash
cd web
npx playwright test ux-wf-005 --project=deterministic
```

### 带 UI 模式运行
```bash
npx playwright test ux-wf-005 --project=deterministic --headed
```

### 调试模式
```bash
npx playwright test ux-wf-005 --project=deterministic --debug
```

## 故障排查

### 常见问题 1: run_id 未被捕获
**原因**: 响应拦截器未正确匹配 URL
**解决**: 检查 API 端点路径是否正确: `/api/projects/{project_id}/workflows/{workflow_id}/runs`

### 常见问题 2: 事件数量不足 10 个
**原因**:
- 工作流执行失败
- 事件录制未启用 (`disable_run_persistence=true`)
- 数据库未正确写入

**解决**:
- 检查执行日志
- 确认后端配置 `disable_run_persistence=false`
- 检查数据库事务提交

### 常见问题 3: 回放按钮一直被禁用
**原因**:
- 前端未正确捕获 `lastRunId`
- 执行未完成

**解决**:
- 检查前端状态管理
- 验证执行状态为 completed

### 常见问题 4: Events API 返回 410 Gone
**原因**: 后端配置了 `disable_run_persistence=true`
**解决**: 使用 `.env.test` 配置启动后端,确保事件持久化启用

## 依赖项

### 后端依赖
- ✅ Run 持久化启用 (`disable_run_persistence=false`)
- ✅ RunEvent 录制器启用
- ✅ `GET /api/runs/{run_id}/events` 端点实现
- ✅ Deterministic 模式配置 (LLM Stub + HTTP Mock)

### 前端依赖
- ✅ `replay-run-button` data-testid 已添加
- ✅ `useRunReplay` hook 实现
- ✅ 执行状态管理 (lastRunId 捕获)
- ✅ 执行日志面板 (可选: replay-event-list 组件)

## 测试覆盖率

| 功能点 | 覆盖状态 |
|--------|----------|
| 工作流执行 | ✅ |
| Run ID 捕获 | ✅ |
| Events API 调用 | ✅ |
| 事件序列验证 | ✅ |
| 事件类型验证 | ✅ |
| 回放按钮交互 | ✅ |
| 事件列表显示 | ✅ |
| 分页功能 | ✅ |
| 边界条件 (无 run) | ✅ |

## 里程碑
- [x] M0: 测试文件创建
- [x] M1: 核心场景实现 (执行 + 回放)
- [x] M2: 边界场景实现 (禁用状态 + 分页)
- [ ] M3: 首次运行验证
- [ ] M4: CI 集成验证

## 作者信息
- 实现者: Claude Sonnet 4.5
- 创建日期: 2025-01-06
- 测试框架: Playwright + TypeScript
- 测试模式: Deterministic (Stub LLM + Mock HTTP)
