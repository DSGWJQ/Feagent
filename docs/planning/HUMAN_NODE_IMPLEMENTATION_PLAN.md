# Human 节点实现规划文档

**文档版本**: 1.0.0
**创建日期**: 2026-01-12
**优先级**: P2 (中期任务)
**预计工期**: 2-3周
**负责人**: 待分配

---

## 一、背景与需求

### 1.1 业务场景

**典型用例**:

1. **客服知识助理** (已在 UX-WF-009 中规划):
   ```
   DB (拉取历史记录) → LLM (生成答复) → Human (人工审核) → Notification (发送给客户)
   ```

2. **财务审批流程**:
   ```
   File (读取报销单) → Python (计算金额) → Human (财务审核) → Database (记录审批)
   ```

3. **内容审核**:
   ```
   HTTP (拉取用户内容) → LLM (敏感词检测) → Human (人工复核) → API (发布/下架)
   ```

### 1.2 当前状态

| 组件 | 状态 | 说明 |
|------|------|------|
| **节点定义** | ❌ 缺失 | `definitions/nodes/human.yaml` 不存在 |
| **执行器** | ❌ 缺失 | `HumanExecutor` 未实现 |
| **前端组件** | ❌ 缺失 | `HumanNode.tsx` 未实现 |
| **审批 UI** | ❌ 缺失 | 人工审批界面未实现 |
| **Fixture** | ✅ 部分 | `knowledge_assistant` 预留了扩展点 |

### 1.3 技术挑战

| 挑战 | 描述 | 优先级 |
|------|------|--------|
| **异步等待** | 工作流需暂停，等待人工操作 | P0 |
| **超时处理** | 长时间无响应的降级策略 | P0 |
| **权限控制** | 谁可以审批？审批日志？ | P1 |
| **状态持久化** | 审批状态需持久化 | P0 |
| **通知机制** | 如何通知审批人？ | P1 |

---

## 二、目标与验收标准

### 2.1 核心目标

1. **基础功能**: 实现 Human 节点的创建、配置、执行、审批
2. **工作流集成**: 与现有工作流引擎无缝集成
3. **用户体验**: 提供友好的审批界面
4. **可扩展性**: 支持多种审批模式（串行/并行/投票）

### 2.2 验收标准

| 验收项 | 标准 | 验证方式 |
|--------|------|---------|
| **节点定义** | YAML schema 校验通过 | `python -m scripts.validate_node_definitions` |
| **执行器测试** | 单元测试覆盖率 > 80% | `pytest tests/unit/executors/test_human_executor.py` |
| **E2E 测试** | 知识助理场景测试通过 | 更新 UX-WF-009，添加 Human 节点 |
| **前端渲染** | 节点在画布上正确显示 | 手动测试 |
| **审批流程** | 提交审批 → 通过/拒绝 → 工作流继续/停止 | 集成测试 |

---

## 三、技术方案

### 3.1 节点定义 (YAML)

**文件**: `definitions/nodes/human.yaml`

```yaml
# Human Interaction 节点 - 人工审批/确认
name: human
kind: node
description: 人工审批或确认节点，工作流暂停等待人工操作
version: "1.0.0"
author: feagent
tags:
  - human
  - approval
  - interaction
category: workflow

executor_type: human

# 输入参数
parameters:
  - name: approval_type
    type: string
    description: 审批类型
    required: true
    default: "manual_review"
    enum:
      - manual_review      # 人工审核
      - approval           # 审批通过/拒绝
      - confirmation       # 确认操作
      - input_required     # 需要输入数据

  - name: title
    type: string
    description: 审批任务标题
    required: true

  - name: description
    type: string
    description: 审批任务描述
    required: false

  - name: assignees
    type: array
    description: 审批人列表（用户 ID 或角色）
    required: true
    default: []

  - name: timeout_seconds
    type: integer
    description: 超时时间（秒），超时后自动执行 fallback 策略
    required: false
    default: 86400  # 24小时
    constraints:
      min: 60
      max: 604800  # 7天

  - name: approval_mode
    type: string
    description: 审批模式
    required: false
    default: "any"
    enum:
      - any        # 任意一人通过即可
      - all        # 所有人都需通过
      - majority   # 多数通过

  - name: form_schema
    type: object
    description: 审批表单 JSON Schema（用于 input_required 类型）
    required: false

  - name: notification_channels
    type: array
    description: 通知渠道（email, webhook, in_app）
    required: false
    default: ["in_app"]

# 返回值
returns:
  type: object
  properties:
    approved:
      type: boolean
      description: 是否通过审批
    approver:
      type: string
      description: 审批人 ID
    approved_at:
      type: string
      description: 审批时间 (ISO 8601)
    comment:
      type: string
      description: 审批意见
    form_data:
      type: object
      description: 表单输入数据（仅 input_required）

# 错误处理策略
error_strategy:
  retry:
    max_attempts: 1
    delay_seconds: 0
  on_failure: abort
  fallback:
    on_timeout:
      action: auto_reject  # 或 auto_approve, notify_admin
      default_value:
        approved: false
        approver: "system"
        comment: "Timeout - auto rejected"

# 执行配置
execution:
  timeout_seconds: 604800  # 7天最大等待时间
  sandbox: false
  async: true  # 异步执行，不阻塞工作流引擎
```

### 3.2 执行器实现

**文件**: `src/infrastructure/executors/human_executor.py`

```python
"""Human Interaction Executor - 人工审批执行器"""

from datetime import datetime, timedelta
from typing import Any
from src.domain.entities.node import Node
from src.domain.services.base_executor import BaseNodeExecutor
from src.domain.services.event_bus import EventBus
from src.domain.events.human_approval_events import (
    HumanApprovalRequestedEvent,
    HumanApprovalCompletedEvent,
    HumanApprovalTimeoutEvent,
)

class HumanExecutor(BaseNodeExecutor):
    """人工审批执行器

    执行流程:
    1. 创建审批任务（持久化到 DB）
    2. 发布审批请求事件（触发通知）
    3. 返回 PENDING 状态（工作流暂停）
    4. 等待审批完成事件
    5. 返回审批结果
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        approval_repository: "HumanApprovalRepository" | None = None,
        notification_service: "NotificationService" | None = None,
    ):
        super().__init__(event_bus)
        self.approval_repo = approval_repository
        self.notification_service = notification_service

    async def _execute_impl(
        self,
        node: Node,
        inputs: dict[str, Any],
        context: dict[str, Any]
    ) -> Any:
        """创建审批任务并等待人工操作"""

        # 1. 解析配置
        config = node.config
        approval_type = config.get("approval_type", "manual_review")
        title = config["title"]
        description = config.get("description", "")
        assignees = config.get("assignees", [])
        timeout_seconds = config.get("timeout_seconds", 86400)
        approval_mode = config.get("approval_mode", "any")

        # 2. 创建审批任务
        approval_task = HumanApprovalTask.create(
            task_id=f"approval_{node.id}_{datetime.now().timestamp()}",
            node_id=node.id,
            run_id=context.get("run_id"),
            approval_type=approval_type,
            title=title,
            description=description,
            assignees=assignees,
            approval_mode=approval_mode,
            input_data=inputs,
            timeout_at=datetime.now() + timedelta(seconds=timeout_seconds),
            status="pending",
        )

        # 3. 持久化审批任务
        await self.approval_repo.save(approval_task)

        # 4. 发布审批请求事件（触发通知）
        if self.event_bus:
            await self.event_bus.publish(
                HumanApprovalRequestedEvent(
                    task_id=approval_task.task_id,
                    node_id=node.id,
                    run_id=context.get("run_id"),
                    assignees=assignees,
                    title=title,
                    description=description,
                    timeout_at=approval_task.timeout_at,
                )
            )

        # 5. 发送通知给审批人
        if self.notification_service:
            await self.notification_service.notify_approvers(
                assignees=assignees,
                task=approval_task,
                channels=config.get("notification_channels", ["in_app"]),
            )

        # 6. 返回 PENDING 状态（工作流引擎会暂停等待）
        return {
            "status": "PENDING",
            "task_id": approval_task.task_id,
            "message": f"Waiting for approval from: {', '.join(assignees)}",
        }

    async def resume_from_approval(
        self,
        task_id: str,
        approved: bool,
        approver: str,
        comment: str | None = None,
        form_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """恢复工作流执行（审批完成后调用）"""

        # 1. 更新审批任务状态
        task = await self.approval_repo.get_by_id(task_id)
        task.status = "approved" if approved else "rejected"
        task.approver = approver
        task.approved_at = datetime.now()
        task.comment = comment
        task.form_data = form_data
        await self.approval_repo.update(task)

        # 2. 发布审批完成事件
        if self.event_bus:
            await self.event_bus.publish(
                HumanApprovalCompletedEvent(
                    task_id=task_id,
                    node_id=task.node_id,
                    run_id=task.run_id,
                    approved=approved,
                    approver=approver,
                    approved_at=task.approved_at,
                    comment=comment,
                )
            )

        # 3. 返回审批结果
        return {
            "approved": approved,
            "approver": approver,
            "approved_at": task.approved_at.isoformat(),
            "comment": comment or "",
            "form_data": form_data or {},
        }
```

### 3.3 数据模型

**文件**: `src/domain/entities/human_approval_task.py`

```python
"""Human Approval Task - 审批任务实体"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

@dataclass
class HumanApprovalTask:
    """审批任务实体"""

    task_id: str
    node_id: str
    run_id: str
    approval_type: str
    title: str
    description: str
    assignees: list[str]
    approval_mode: str
    input_data: dict[str, Any]
    timeout_at: datetime
    status: str  # pending, approved, rejected, timeout
    approver: str | None = None
    approved_at: datetime | None = None
    comment: str | None = None
    form_data: dict[str, Any] | None = None
    created_at: datetime = None

    @staticmethod
    def create(
        task_id: str,
        node_id: str,
        run_id: str,
        approval_type: str,
        title: str,
        description: str,
        assignees: list[str],
        approval_mode: str,
        input_data: dict[str, Any],
        timeout_at: datetime,
        status: str = "pending",
    ) -> "HumanApprovalTask":
        return HumanApprovalTask(
            task_id=task_id,
            node_id=node_id,
            run_id=run_id,
            approval_type=approval_type,
            title=title,
            description=description,
            assignees=assignees,
            approval_mode=approval_mode,
            input_data=input_data,
            timeout_at=timeout_at,
            status=status,
            created_at=datetime.now(),
        )
```

### 3.4 前端组件

**文件**: `web/src/features/workflows/components/nodes/HumanNode.tsx`

```typescript
/**
 * Human Interaction Node - 人工审批节点
 */

import React from 'react';
import { Handle, Position } from '@xyflow/react';
import { UserOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { Card, Tag, Space } from 'antd';

interface HumanNodeProps {
  data: {
    label: string;
    config?: {
      approval_type?: string;
      assignees?: string[];
      timeout_seconds?: number;
      approval_mode?: string;
    };
  };
  selected?: boolean;
}

export const HumanNode: React.FC<HumanNodeProps> = ({ data, selected }) => {
  const { label, config } = data;
  const approvalType = config?.approval_type || 'manual_review';
  const assignees = config?.assignees || [];
  const timeoutHours = Math.floor((config?.timeout_seconds || 86400) / 3600);
  const approvalMode = config?.approval_mode || 'any';

  return (
    <>
      <Handle type="target" position={Position.Top} />
      <Card
        size="small"
        className={`human-node ${selected ? 'selected' : ''}`}
        style={{
          minWidth: 200,
          border: selected ? '2px solid #1890ff' : '1px solid #d9d9d9',
        }}
      >
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Space>
            <UserOutlined style={{ fontSize: 16, color: '#52c41a' }} />
            <strong>{label}</strong>
          </Space>

          <Tag color="green">{approvalType}</Tag>

          {assignees.length > 0 && (
            <div style={{ fontSize: 12, color: '#666' }}>
              审批人: {assignees.slice(0, 2).join(', ')}
              {assignees.length > 2 && ` +${assignees.length - 2}`}
            </div>
          )}

          <div style={{ fontSize: 12, color: '#999' }}>
            <ClockCircleOutlined /> {timeoutHours}h timeout
          </div>

          {approvalMode !== 'any' && (
            <Tag color="blue">{approvalMode}</Tag>
          )}
        </Space>
      </Card>
      <Handle type="source" position={Position.Bottom} />
    </>
  );
};
```

**审批界面**: `web/src/features/approvals/ApprovalPanel.tsx`

```typescript
/**
 * Approval Panel - 审批任务面板
 */

import React from 'react';
import { Card, Button, Space, Typography, Descriptions, Form, Input, message } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';

const { TextArea } = Input;
const { Title, Paragraph } = Typography;

interface ApprovalPanelProps {
  task: {
    task_id: string;
    title: string;
    description: string;
    input_data: any;
    timeout_at: string;
  };
  onApprove: (comment: string) => Promise<void>;
  onReject: (comment: string) => Promise<void>;
}

export const ApprovalPanel: React.FC<ApprovalPanelProps> = ({ task, onApprove, onReject }) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = React.useState(false);

  const handleSubmit = async (approved: boolean) => {
    setLoading(true);
    try {
      const values = await form.validateFields();
      const comment = values.comment || '';

      if (approved) {
        await onApprove(comment);
        message.success('审批通过');
      } else {
        await onReject(comment);
        message.warning('审批拒绝');
      }
    } catch (error) {
      message.error('审批失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <Title level={4}>{task.title}</Title>
      <Paragraph>{task.description}</Paragraph>

      <Descriptions bordered column={1} size="small">
        <Descriptions.Item label="输入数据">
          <pre>{JSON.stringify(task.input_data, null, 2)}</pre>
        </Descriptions.Item>
        <Descriptions.Item label="超时时间">
          {new Date(task.timeout_at).toLocaleString()}
        </Descriptions.Item>
      </Descriptions>

      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item name="comment" label="审批意见">
          <TextArea rows={4} placeholder="请输入审批意见（可选）" />
        </Form.Item>

        <Space>
          <Button
            type="primary"
            icon={<CheckCircleOutlined />}
            loading={loading}
            onClick={() => handleSubmit(true)}
          >
            通过
          </Button>
          <Button
            danger
            icon={<CloseCircleOutlined />}
            loading={loading}
            onClick={() => handleSubmit(false)}
          >
            拒绝
          </Button>
        </Space>
      </Form>
    </Card>
  );
};
```

---

## 四、工作流引擎集成

### 4.1 暂停/恢复机制

**挑战**: 工作流引擎需要支持长时间暂停（等待审批）

**解决方案**: 使用持久化状态机

```python
# src/domain/services/workflow_engine.py

class WorkflowEngine:
    async def execute_node(self, node: Node, inputs: dict, context: dict) -> Any:
        executor = self.executor_factory.get_executor(node.type)
        result = await executor.execute(node, inputs, context)

        # 检查是否为 PENDING 状态（Human 节点）
        if isinstance(result, dict) and result.get("status") == "PENDING":
            # 1. 持久化工作流状态
            await self._save_workflow_state(
                run_id=context["run_id"],
                current_node_id=node.id,
                status="paused_for_approval",
                pending_task_id=result["task_id"],
            )

            # 2. 返回 PENDING（不继续执行后续节点）
            return result

        return result

    async def resume_from_approval(self, run_id: str, task_id: str, approval_result: dict):
        """恢复工作流执行（审批完成后调用）"""

        # 1. 加载工作流状态
        state = await self._load_workflow_state(run_id)

        # 2. 恢复执行（从暂停的节点继续）
        await self.execute_from_node(
            run_id=run_id,
            start_node_id=state.current_node_id,
            initial_output=approval_result,
        )
```

### 4.2 超时处理

**定时任务**: 每分钟检查超时的审批任务

```python
# src/application/jobs/approval_timeout_checker.py

class ApprovalTimeoutChecker:
    """审批超时检查器（定时任务）"""

    async def check_timeouts(self):
        """检查并处理超时的审批任务"""

        # 1. 查询超时任务
        timeout_tasks = await self.approval_repo.find_timeout_tasks()

        for task in timeout_tasks:
            # 2. 执行 fallback 策略
            fallback_action = task.config.get("fallback", {}).get("on_timeout", {}).get("action", "auto_reject")

            if fallback_action == "auto_reject":
                await self.human_executor.resume_from_approval(
                    task_id=task.task_id,
                    approved=False,
                    approver="system",
                    comment="Timeout - auto rejected",
                )
            elif fallback_action == "auto_approve":
                await self.human_executor.resume_from_approval(
                    task_id=task.task_id,
                    approved=True,
                    approver="system",
                    comment="Timeout - auto approved",
                )
            elif fallback_action == "notify_admin":
                await self.notification_service.notify_admins(task)
```

---

## 五、实施计划

### 5.1 Phase 1: 基础设施 (Week 1)

| 任务 | 负责人 | 工期 | 交付物 |
|------|--------|------|--------|
| 节点定义 YAML | 待分配 | 1d | `definitions/nodes/human.yaml` |
| 数据模型 | 待分配 | 1d | `HumanApprovalTask` 实体 |
| Repository | 待分配 | 1d | `HumanApprovalRepository` |
| 单元测试 | 待分配 | 1d | `test_human_approval_task.py` |

### 5.2 Phase 2: 执行器实现 (Week 1-2)

| 任务 | 负责人 | 工期 | 交付物 |
|------|--------|------|--------|
| `HumanExecutor` | 待分配 | 2d | 核心执行逻辑 |
| 事件定义 | 待分配 | 1d | `HumanApprovalRequestedEvent` 等 |
| 通知服务集成 | 待分配 | 1d | Email/Webhook 通知 |
| 集成测试 | 待分配 | 1d | `test_human_executor.py` |

### 5.3 Phase 3: 工作流引擎集成 (Week 2)

| 任务 | 负责人 | 工期 | 交付物 |
|------|--------|------|--------|
| 暂停/恢复机制 | 待分配 | 2d | `WorkflowEngine` 修改 |
| 超时检查器 | 待分配 | 1d | `ApprovalTimeoutChecker` |
| API 端点 | 待分配 | 1d | `/api/approvals/{task_id}/approve` |

### 5.4 Phase 4: 前端实现 (Week 2-3)

| 任务 | 负责人 | 工期 | 交付物 |
|------|--------|------|--------|
| `HumanNode.tsx` | 待分配 | 1d | 节点组件 |
| `ApprovalPanel.tsx` | 待分配 | 2d | 审批界面 |
| API 集成 | 待分配 | 1d | 前端调用审批 API |
| E2E 测试 | 待分配 | 1d | 更新 UX-WF-009 |

---

## 六、风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **状态持久化失败** | 高 | 低 | 事务保证、备份机制 |
| **超时检查延迟** | 中 | 中 | 分布式锁、冗余检查 |
| **通知失败** | 中 | 中 | 重试队列、多通道通知 |
| **权限绕过** | 高 | 低 | 严格权限校验、审计日志 |

---

## 七、验收标准

### 7.1 功能测试

- [ ] 创建 Human 节点并配置
- [ ] 执行工作流，暂停在 Human 节点
- [ ] 审批人收到通知
- [ ] 提交审批（通过/拒绝）
- [ ] 工作流恢复执行
- [ ] 超时自动处理

### 7.2 性能测试

- [ ] 1000 个并发审批任务
- [ ] 审批响应时间 < 500ms
- [ ] 超时检查延迟 < 1 分钟

---

## 八、参考资料

- [知识助理 Fixture](../domain/services/workflow_fixtures.py#L509)
- [工作流引擎设计](../architecture/WORKFLOW_ENGINE_DESIGN.md)
- [EventBus 文档](../architecture/EVENTBUS_DESIGN.md)

---

**状态**: 📋 待启动
**依赖**: 事件系统修复（建议先完成）
**下次审查**: Kickoff Meeting
