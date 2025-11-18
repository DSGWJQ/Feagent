# 工作流 API 设计文档

## 📋 概述

本文档详细定义工作流相关的所有 API 接口。

---

## 🎯 API 列表

### 1. 工作流管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/workflows` | 创建工作流（表单输入） |
| GET | `/workflows` | 获取工作流列表 |
| GET | `/workflows/{id}` | 获取工作流详情 |
| PATCH | `/workflows/{id}` | 更新工作流（拖拽调整） |
| DELETE | `/workflows/{id}` | 删除工作流 |

### 2. 对话调整

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/workflows/{id}/chat` | 对话式调整工作流 |

### 3. 执行管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/workflows/{id}/runs` | 执行工作流 |
| GET | `/workflows/{id}/runs` | 获取执行记录列表 |
| GET | `/workflows/{id}/runs/{run_id}` | 获取执行记录详情 |
| GET | `/workflows/{id}/runs/{run_id}/events` | SSE 实时状态更新 |

---

## 📝 详细设计

### 1. POST /workflows - 创建工作流

**描述**：用户填写表单（起点 + 终点 + 描述），AI 生成最小可行工作流。

**Request**：
```json
{
  "start": "GitHub Issue 列表",
  "goal": "发送到钉钉群",
  "description": "每天定时获取 GitHub Issue 并发送到钉钉群"
}
```

**Response (200)**：
```json
{
  "workflow": {
    "id": "wf_abc123",
    "name": "GitHub Issue 通知",
    "description": "每天定时获取 GitHub Issue 并发送到钉钉群",
    "nodes": [
      {
        "id": "node_1",
        "type": "http",
        "name": "获取 GitHub Issue",
        "config": {
          "url": "https://api.github.com/repos/{owner}/{repo}/issues",
          "method": "GET",
          "headers": {
            "Accept": "application/vnd.github+json"
          }
        },
        "position": {
          "x": 100,
          "y": 100
        }
      },
      {
        "id": "node_2",
        "type": "transform",
        "name": "格式化消息",
        "config": {
          "mapping": {
            "title": "$.issue.title",
            "body": "$.issue.body",
            "url": "$.issue.html_url"
          }
        },
        "position": {
          "x": 100,
          "y": 250
        }
      },
      {
        "id": "node_3",
        "type": "http",
        "name": "发送钉钉通知",
        "config": {
          "url": "{webhook_url}",
          "method": "POST",
          "headers": {
            "Content-Type": "application/json"
          },
          "body": {
            "msgtype": "text",
            "text": {
              "content": "新 Issue: {title}\n{url}"
            }
          }
        },
        "position": {
          "x": 100,
          "y": 400
        }
      }
    ],
    "edges": [
      {
        "id": "edge_1",
        "source_node_id": "node_1",
        "target_node_id": "node_2",
        "condition": null
      },
      {
        "id": "edge_2",
        "source_node_id": "node_2",
        "target_node_id": "node_3",
        "condition": null
      }
    ],
    "status": "draft",
    "created_at": "2025-01-15T10:00:00Z",
    "updated_at": "2025-01-15T10:00:00Z"
  },
  "ai_message": "我为你创建了一个工作流，包含 3 个步骤：\n1. 从 GitHub 获取 Issue 列表\n2. 格式化为钉钉消息格式\n3. 发送到钉钉群\n\n你可以通过右侧的对话框调整工作流，或者直接拖拽节点。"
}
```

**Error (400)**：
```json
{
  "code": 4000,
  "message": "Validation error",
  "detail": {
    "start": "起点不能为空",
    "goal": "终点不能为空"
  },
  "trace_id": "abc123"
}
```

**Error (500)**：
```json
{
  "code": 5000,
  "message": "Failed to generate workflow",
  "detail": "LLM service is unavailable",
  "trace_id": "abc123"
}
```

---

### 2. GET /workflows - 获取工作流列表

**描述**：获取所有工作流列表（支持分页、筛选）。

**Query Parameters**：
- `page` (int, optional): 页码，默认 1
- `page_size` (int, optional): 每页数量，默认 20
- `status` (string, optional): 状态筛选（draft, active, archived）
- `search` (string, optional): 搜索关键词（匹配 name 或 description）

**Request**：
```
GET /workflows?page=1&page_size=20&status=active&search=GitHub
```

**Response (200)**：
```json
{
  "items": [
    {
      "id": "wf_abc123",
      "name": "GitHub Issue 通知",
      "description": "每天定时获取 GitHub Issue 并发送到钉钉群",
      "status": "active",
      "created_at": "2025-01-15T10:00:00Z",
      "updated_at": "2025-01-15T10:00:00Z"
    },
    {
      "id": "wf_def456",
      "name": "GitHub PR 通知",
      "description": "每天定时获取 GitHub PR 并发送到钉钉群",
      "status": "active",
      "created_at": "2025-01-14T10:00:00Z",
      "updated_at": "2025-01-14T10:00:00Z"
    }
  ],
  "total": 2,
  "page": 1,
  "page_size": 20
}
```

---

### 3. GET /workflows/{id} - 获取工作流详情

**描述**：获取指定工作流的详细信息。

**Request**：
```
GET /workflows/wf_abc123
```

**Response (200)**：
```json
{
  "id": "wf_abc123",
  "name": "GitHub Issue 通知",
  "description": "每天定时获取 GitHub Issue 并发送到钉钉群",
  "nodes": [...],
  "edges": [...],
  "status": "active",
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:00:00Z"
}
```

**Error (404)**：
```json
{
  "code": 4040,
  "message": "Workflow not found",
  "detail": "Workflow with id 'wf_abc123' does not exist",
  "trace_id": "abc123"
}
```

---

### 4. PATCH /workflows/{id} - 更新工作流（拖拽调整）

**描述**：用户通过拖拽调整工作流（添加/删除节点、修改连线、调整位置）。

**Request**：
```json
{
  "nodes": [
    {
      "id": "node_1",
      "type": "http",
      "name": "获取 GitHub Issue",
      "config": {...},
      "position": {
        "x": 150,
        "y": 100
      }
    },
    {
      "id": "node_2",
      "type": "transform",
      "name": "格式化消息",
      "config": {...},
      "position": {
        "x": 150,
        "y": 250
      }
    },
    {
      "id": "node_4",
      "type": "sql",
      "name": "保存到数据库",
      "config": {
        "connection_string": "postgresql://...",
        "sql": "INSERT INTO issues (title, body) VALUES (?, ?)"
      },
      "position": {
        "x": 150,
        "y": 325
      }
    },
    {
      "id": "node_3",
      "type": "http",
      "name": "发送钉钉通知",
      "config": {...},
      "position": {
        "x": 150,
        "y": 475
      }
    }
  ],
  "edges": [
    {
      "id": "edge_1",
      "source_node_id": "node_1",
      "target_node_id": "node_2"
    },
    {
      "id": "edge_4",
      "source_node_id": "node_2",
      "target_node_id": "node_4"
    },
    {
      "id": "edge_2",
      "source_node_id": "node_4",
      "target_node_id": "node_3"
    }
  ]
}
```

**Response (200)**：
```json
{
  "id": "wf_abc123",
  "name": "GitHub Issue 通知",
  "description": "每天定时获取 GitHub Issue 并发送到钉钉群",
  "nodes": [...],
  "edges": [...],
  "status": "draft",
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:05:00Z"
}
```

**Error (400)**：
```json
{
  "code": 4000,
  "message": "Invalid workflow",
  "detail": "Node 'node_5' referenced in edge does not exist",
  "trace_id": "abc123"
}
```

---

### 5. DELETE /workflows/{id} - 删除工作流

**描述**：删除指定工作流。

**Request**：
```
DELETE /workflows/wf_abc123
```

**Response (204)**：
```
No Content
```

**Error (404)**：
```json
{
  "code": 4040,
  "message": "Workflow not found",
  "detail": "Workflow with id 'wf_abc123' does not exist",
  "trace_id": "abc123"
}
```

---

### 6. POST /workflows/{id}/chat - 对话式调整工作流

**描述**：用户通过对话调整工作流，AI 理解意图并修改工作流。

**Request**：
```json
{
  "message": "在发送钉钉之前，先保存到数据库"
}
```

**Response (200)**：
```json
{
  "workflow": {
    "id": "wf_abc123",
    "name": "GitHub Issue 通知",
    "nodes": [
      {...},
      {
        "id": "node_4",
        "type": "sql",
        "name": "保存到数据库",
        "config": {
          "connection_string": "postgresql://...",
          "sql": "INSERT INTO issues (title, body) VALUES (?, ?)"
        },
        "position": {
          "x": 100,
          "y": 325
        }
      },
      {...}
    ],
    "edges": [
      {...},
      {
        "id": "edge_4",
        "source_node_id": "node_2",
        "target_node_id": "node_4"
      },
      {
        "id": "edge_2",
        "source_node_id": "node_4",
        "target_node_id": "node_3"
      }
    ],
    "status": "draft",
    "updated_at": "2025-01-15T10:05:00Z"
  },
  "ai_message": "好的，我在步骤 2 和 3 之间添加了"保存到数据库"节点：\n\n工作流更新：\n  1. [HTTP] 获取 GitHub Issue\n  2. [Transform] 格式化消息\n  3. [SQL] 保存 Issue 记录  ← 新增\n  4. [HTTP] 发送钉钉通知\n\n是否还需要调整？"
}
```

---

### 7. POST /workflows/{id}/runs - 执行工作流

**描述**：执行指定工作流。

**Request**：
```json
{
  "input_data": {
    "repo_owner": "facebook",
    "repo_name": "react",
    "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=xxx"
  }
}
```

**Response (200)**：
```json
{
  "run": {
    "id": "run_xyz789",
    "workflow_id": "wf_abc123",
    "status": "running",
    "input_data": {
      "repo_owner": "facebook",
      "repo_name": "react",
      "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=xxx"
    },
    "node_executions": [
      {
        "id": "ne_1",
        "node_id": "node_1",
        "status": "pending",
        "input_data": {},
        "output_data": null,
        "error_message": null,
        "started_at": null,
        "finished_at": null
      },
      {
        "id": "ne_2",
        "node_id": "node_2",
        "status": "pending",
        "input_data": {},
        "output_data": null,
        "error_message": null,
        "started_at": null,
        "finished_at": null
      },
      {
        "id": "ne_3",
        "node_id": "node_3",
        "status": "pending",
        "input_data": {},
        "output_data": null,
        "error_message": null,
        "started_at": null,
        "finished_at": null
      }
    ],
    "started_at": "2025-01-15T10:10:00Z",
    "finished_at": null
  }
}
```

---

### 8. GET /workflows/{id}/runs - 获取执行记录列表

**描述**：获取指定工作流的所有执行记录。

**Query Parameters**：
- `page` (int, optional): 页码，默认 1
- `page_size` (int, optional): 每页数量，默认 20
- `status` (string, optional): 状态筛选（running, succeeded, failed）

**Request**：
```
GET /workflows/wf_abc123/runs?page=1&page_size=20&status=succeeded
```

**Response (200)**：
```json
{
  "items": [
    {
      "id": "run_xyz789",
      "workflow_id": "wf_abc123",
      "status": "succeeded",
      "started_at": "2025-01-15T10:10:00Z",
      "finished_at": "2025-01-15T10:10:15Z"
    },
    {
      "id": "run_xyz788",
      "workflow_id": "wf_abc123",
      "status": "failed",
      "started_at": "2025-01-15T09:10:00Z",
      "finished_at": "2025-01-15T09:10:10Z"
    }
  ],
  "total": 2,
  "page": 1,
  "page_size": 20
}
```

---

### 9. GET /workflows/{id}/runs/{run_id} - 获取执行记录详情

**描述**：获取指定执行记录的详细信息。

**Request**：
```
GET /workflows/wf_abc123/runs/run_xyz789
```

**Response (200)**：
```json
{
  "id": "run_xyz789",
  "workflow_id": "wf_abc123",
  "status": "succeeded",
  "input_data": {...},
  "node_executions": [
    {
      "id": "ne_1",
      "node_id": "node_1",
      "status": "succeeded",
      "input_data": {...},
      "output_data": {...},
      "error_message": null,
      "started_at": "2025-01-15T10:10:00Z",
      "finished_at": "2025-01-15T10:10:05Z"
    },
    {
      "id": "ne_2",
      "node_id": "node_2",
      "status": "succeeded",
      "input_data": {...},
      "output_data": {...},
      "error_message": null,
      "started_at": "2025-01-15T10:10:05Z",
      "finished_at": "2025-01-15T10:10:10Z"
    },
    {
      "id": "ne_3",
      "node_id": "node_3",
      "status": "succeeded",
      "input_data": {...},
      "output_data": {...},
      "error_message": null,
      "started_at": "2025-01-15T10:10:10Z",
      "finished_at": "2025-01-15T10:10:15Z"
    }
  ],
  "started_at": "2025-01-15T10:10:00Z",
  "finished_at": "2025-01-15T10:10:15Z"
}
```

---

### 10. GET /workflows/{id}/runs/{run_id}/events - SSE 实时状态更新

**描述**：通过 Server-Sent Events (SSE) 实时推送执行状态。

**Request**：
```
GET /workflows/wf_abc123/runs/run_xyz789/events
Accept: text/event-stream
```

**Response (200)**：
```
Content-Type: text/event-stream

event: node_execution_started
data: {"node_id": "node_1", "status": "running", "started_at": "2025-01-15T10:10:00Z"}

event: node_execution_completed
data: {"node_id": "node_1", "status": "succeeded", "output_data": {...}, "finished_at": "2025-01-15T10:10:05Z"}

event: node_execution_started
data: {"node_id": "node_2", "status": "running", "started_at": "2025-01-15T10:10:05Z"}

event: node_execution_completed
data: {"node_id": "node_2", "status": "succeeded", "output_data": {...}, "finished_at": "2025-01-15T10:10:10Z"}

event: node_execution_started
data: {"node_id": "node_3", "status": "running", "started_at": "2025-01-15T10:10:10Z"}

event: node_execution_failed
data: {"node_id": "node_3", "status": "failed", "error_message": "Webhook URL is invalid", "finished_at": "2025-01-15T10:10:15Z"}

event: run_completed
data: {"run_id": "run_xyz789", "status": "failed", "finished_at": "2025-01-15T10:10:15Z"}
```

---

## 📊 数据模型

### WorkflowDTO
```python
class WorkflowDTO(BaseModel):
    id: str
    name: str
    description: str
    nodes: List[NodeDTO]
    edges: List[EdgeDTO]
    status: WorkflowStatus
    created_at: datetime
    updated_at: datetime
```

### NodeDTO
```python
class NodeDTO(BaseModel):
    id: str
    type: NodeType
    name: str
    config: Dict[str, Any]
    position: PositionDTO
```

### EdgeDTO
```python
class EdgeDTO(BaseModel):
    id: str
    source_node_id: str
    target_node_id: str
    condition: Optional[str] = None
```

### RunDTO
```python
class RunDTO(BaseModel):
    id: str
    workflow_id: str
    status: RunStatus
    input_data: Dict[str, Any]
    node_executions: List[NodeExecutionDTO]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
```

### NodeExecutionDTO
```python
class NodeExecutionDTO(BaseModel):
    id: str
    node_id: str
    status: NodeExecutionStatus
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
```

---

## ✅ 总结

本文档定义了工作流相关的所有 API 接口，包括：

1. ✅ 工作流管理（创建、查询、更新、删除）
2. ✅ 对话调整（对话式修改工作流）
3. ✅ 执行管理（执行工作流、查询执行记录）
4. ✅ SSE 实时状态更新（实时推送节点执行状态）

所有 API 遵循 RESTful 规范，使用统一的错误结构，支持分页和筛选。
