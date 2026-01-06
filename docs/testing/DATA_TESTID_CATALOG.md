# E2E 测试完整 data-testid 列表

> 目标：为 Playwright 选择器提供稳定的 `data-testid` 属性，覆盖所有 P0/P1 用例交互点。

---

## 1. 全局布局（所有页面共用）

| 元素 | data-testid | 位置 | 用途 |
|---|---|---|---|
| 顶部导航栏 | `global-nav` | 全局 Header | 导航定位 |
| 用户菜单按钮 | `user-menu-button` | Header 右侧 | 用户操作入口 |
| 通知图标 | `notification-icon` | Header 右侧 | 通知中心 |
| 全局加载遮罩 | `global-loading-mask` | Body 覆盖层 | 等待全局加载完成 |
| 错误提示容器 | `global-error-toast` | Toast 组件 | 断言错误消息 |
| 成功提示容器 | `global-success-toast` | Toast 组件 | 断言成功消息 |

---

## 2. 工作流编辑器页面 (`/workflows/:id/edit`)

### 2.1 控制栏（顶部）

| 元素 | data-testid | 位置 | 用途 |
|---|---|---|---|
| 工作流名称输入框 | `workflow-name-input` | 控制栏左侧 | 编辑工作流名称 |
| 保存按钮 | `workflow-save-button` | 控制栏中部 | 触发保存 |
| 保存状态指示器 | `workflow-save-status` | 保存按钮旁 | 断言"已保存"/"保存中" |
| RUN 按钮 | `workflow-run-button` | 控制栏右侧 | 触发执行 |
| 执行状态指示器 | `workflow-execution-status` | RUN 按钮旁 | 断言"运行中"/"已完成" |
| Run ID 显示（如有） | `workflow-run-id-badge` | 控制栏右侧 | 验证 run_id 存在 |
| 更多操作菜单 | `workflow-actions-menu` | 控制栏右侧 | 导入/导出/删除 |

### 2.2 画布区域（中部）

| 元素 | data-testid | 位置 | 用途 |
|---|---|---|---|
| 画布容器 | `workflow-canvas` | 中部主区域 | 拖拽节点/连线 |
| 节点（通用） | `workflow-node-{node_id}` | 画布内 | 点击/拖拽节点 |
| 节点状态指示器 | `node-status-{node_id}` | 节点内部 | 断言"running"/"completed"/"error" |
| 节点输出预览 | `node-output-{node_id}` | 节点悬浮/侧边栏 | 验证节点输出 |
| 连线（通用） | `workflow-edge-{edge_id}` | 画布内 | 点击/删除连线 |
| 开始节点（固定） | `workflow-node-start` | 画布内 | 定位 start 节点 |
| 结束节点（固定） | `workflow-node-end` | 画布内 | 定位 end 节点 |
| 孤立节点标记 | `isolated-node-indicator-{node_id}` | 节点角标 | 验证孤立节点检测 |

### 2.3 节点编辑面板（右侧/弹窗）

| 元素 | data-testid | 位置 | 用途 |
|---|---|---|---|
| 节点编辑面板容器 | `node-edit-panel` | 右侧抽屉 | 等待面板打开 |
| 节点类型选择器 | `node-type-selector` | 面板顶部 | 选择节点类型 |
| 节点名称输入框 | `node-name-input` | 面板内 | 编辑节点名称 |
| 节点配置区域 | `node-config-section` | 面板内 | 配置节点参数 |
| Python 代码编辑器 | `node-code-editor` | 面板内（PYTHON 节点） | 编辑代码 |
| HTTP URL 输入框 | `node-http-url-input` | 面板内（HTTP 节点） | 编辑 URL |
| HTTP Method 选择器 | `node-http-method-select` | 面板内（HTTP 节点） | 选择 GET/POST |
| 节点删除按钮 | `node-delete-button` | 面板底部 | 删除节点 |
| 节点保存按钮 | `node-save-button` | 面板底部 | 保存节点配置 |

### 2.4 执行日志区域（底部/侧边）

| 元素 | data-testid | 位置 | 用途 |
|---|---|---|---|
| 执行日志容器 | `execution-log-panel` | 底部抽屉 | 查看执行历史 |
| 日志项（通用） | `execution-log-entry-{index}` | 日志列表内 | 定位具体日志行 |
| 日志节点名称 | `log-node-name-{index}` | 日志项内 | 验证节点名称 |
| 日志节点状态 | `log-node-status-{index}` | 日志项内 | 验证状态 |
| 日志节点输出 | `log-node-output-{index}` | 日志项内 | 验证输出数据 |
| 清空日志按钮 | `execution-log-clear-button` | 日志面板顶部 | 清空日志 |
| 日志导出按钮 | `execution-log-export-button` | 日志面板顶部 | 导出日志 |

### 2.5 对话/Chat 区域（左侧/弹窗）

| 元素 | data-testid | 位置 | 用途 |
|---|---|---|---|
| Chat 输入框 | `chat-input` | Chat 面板底部 | 输入对话内容 |
| Chat 发送按钮 | `chat-send-button` | Chat 输入框旁 | 发送消息 |
| Chat 消息列表 | `chat-message-list` | Chat 面板内 | 查看对话历史 |
| Chat 消息项 | `chat-message-{index}` | 消息列表内 | 定位具体消息 |
| Chat 加载指示器 | `chat-loading-indicator` | 消息列表内 | 等待 AI 响应 |
| Planning Step 项 | `planning-step-{index}` | SSE 流式输出 | 验证规划步骤 |

---

## 3. 副作用确认弹窗（PRD-030）

| 元素 | data-testid | 位置 | 用途 |
|---|---|---|---|
| 确认弹窗容器 | `side-effect-confirm-modal` | Modal 覆盖层 | 等待弹窗出现 |
| 弹窗标题 | `confirm-modal-title` | Modal 头部 | 验证标题文案 |
| 弹窗描述 | `confirm-modal-description` | Modal 内容 | 验证副作用描述 |
| 节点信息展示 | `confirm-node-info` | Modal 内容 | 验证节点 ID/类型 |
| Allow 按钮 | `confirm-allow-button` | Modal 底部 | 允许执行 |
| Deny 按钮 | `confirm-deny-button` | Modal 底部 | 拒绝执行 |
| 取消按钮 | `confirm-cancel-button` | Modal 底部 | 关闭弹窗 |
| 确认 ID 隐藏字段 | `confirm-id-hidden` | Modal（data 属性） | 获取 confirm_id |

---

## 4. Replay/回放页面（可选）

| 元素 | data-testid | 位置 | 用途 |
|---|---|---|---|
| Replay 触发按钮 | `replay-run-button` | 控制栏/执行日志 | 触发回放 |
| Replay 事件列表 | `replay-event-list` | Replay 面板 | 查看事件序列 |
| Replay 事件项 | `replay-event-{index}` | 事件列表内 | 定位具体事件 |
| Replay 进度条 | `replay-progress-bar` | Replay 面板顶部 | 验证回放进度 |
| Replay 完成提示 | `replay-complete-message` | Replay 面板底部 | 断言回放完成 |

---

## 5. 保存校验错误弹窗（UX-WF-102）

| 元素 | data-testid | 位置 | 用途 |
|---|---|---|---|
| 校验错误弹窗 | `validation-error-modal` | Modal 覆盖层 | 等待错误弹窗 |
| 错误列表容器 | `validation-error-list` | Modal 内容 | 查看错误列表 |
| 错误项（通用） | `validation-error-{index}` | 错误列表内 | 定位具体错误 |
| 错误字段路径 | `error-field-path-{index}` | 错误项内 | 验证字段路径 |
| 错误原因描述 | `error-reason-{index}` | 错误项内 | 验证错误原因 |
| 错误关闭按钮 | `validation-error-close-button` | Modal 底部 | 关闭错误弹窗 |

---

## 6. 首页/工作流列表（`/`）

| 元素 | data-testid | 位置 | 用途 |
|---|---|---|---|
| 创建工作流按钮 | `create-workflow-button` | 页面顶部/右上角 | 触发创建流程 |
| 工作流列表容器 | `workflow-list` | 页面主区域 | 查看工作流列表 |
| 工作流卡片（通用） | `workflow-card-{workflow_id}` | 列表内 | 点击进入编辑器 |
| 工作流名称（卡片内） | `workflow-name-{workflow_id}` | 卡片内 | 验证名称 |
| 工作流更新时间 | `workflow-updated-{workflow_id}` | 卡片内 | 验证时间 |
| 工作流删除按钮 | `workflow-delete-{workflow_id}` | 卡片操作区 | 删除工作流 |

---

## 7. 实施建议

### 7.1 前端组件改造（优先级）

**P0（必须添加）**：
- `workflow-run-button`
- `workflow-save-button`
- `workflow-execution-status`
- `workflow-canvas`
- `workflow-node-{node_id}`
- `side-effect-confirm-modal`
- `confirm-allow-button`
- `confirm-deny-button`

**P1（应该添加）**：
- `node-edit-panel`
- `node-save-button`
- `execution-log-panel`
- `replay-run-button`
- `validation-error-modal`

**P2（可选添加）**：
- `chat-input`
- `planning-step-{index}`
- `global-error-toast`

### 7.2 React 组件示例

```tsx
// web/src/features/workflows/components/WorkflowCanvas.tsx
export function WorkflowCanvas({ workflow }: Props) {
  return (
    <div data-testid="workflow-canvas">
      {workflow.nodes.map(node => (
        <WorkflowNode
          key={node.id}
          data-testid={`workflow-node-${node.id}`}
          node={node}
        />
      ))}
    </div>
  );
}
```

### 7.3 Playwright 使用示例

```typescript
// tests/e2e/ux-wf-003-run-workflow.spec.ts
import { test, expect } from '@playwright/test';

test('UX-WF-003: 运行工作流并看到终态', async ({ page, seedWorkflow }) => {
  const { workflow_id, project_id } = await seedWorkflow('main_subgraph_only');

  // 1. 打开编辑器
  await page.goto(`/workflows/${workflow_id}/edit?projectId=${project_id}`);

  // 2. 等待画布加载
  await expect(page.getByTestId('workflow-canvas')).toBeVisible();
  await expect(page.getByTestId('workflow-node-start')).toBeVisible();

  // 3. 点击 RUN
  await page.getByTestId('workflow-run-button').click();

  // 4. 等待执行完成
  await expect(page.getByTestId('workflow-execution-status')).toContainText(
    'completed',
    { timeout: 30000 }
  );

  // 5. 验证节点状态
  await expect(page.getByTestId('node-status-process_data')).toHaveAttribute(
    'data-status',
    'completed'
  );
});
```

---

## 8. 里程碑

| 里程碑 | 任务 | 工作量 |
|---|---|---|
| M0 | 为 P0 控件添加 data-testid（7 个） | 0.5 天 |
| M1 | 为 P1 控件添加 data-testid（10 个） | 0.5 天 |
| M2 | 编写 Playwright 选择器 helper 函数 | 0.5 天 |
| M3 | 验证所有 testid 可访问性 | 0.5 天 |

**总计**：2 天

---

## 9. 验收标准

- [ ] 所有 P0 testid 在前端代码中已添加
- [ ] Playwright 能通过 testid 定位所有关键控件
- [ ] 无需使用 CSS 选择器或 XPath（除非元素动态生成）
- [ ] testid 命名遵循 `{domain}-{element}-{qualifier}` 规范
- [ ] 冲突测试：同一页面不存在重复 testid
