# API 接口文档

## 基础信息

- **Base URL**: `http://localhost:8000`
- **Content-Type**: `application/json`

---

## Agent 相关接口

### 1. 获取 Agent 列表

**GET** `/agents`

**Query Parameters**:
- `skip` (可选): 跳过的记录数，默认 0
- `limit` (可选): 返回的记录数，默认 100

**Response 200**:
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "数据分析助手",
    "start": "有一个 CSV 文件",
    "goal": "生成数据分析报告",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
]
```

---

### 2. 创建 Agent

**POST** `/agents`

**Request Body**:
```json
{
  "name": "数据分析助手",
  "start": "有一个 CSV 文件",
  "goal": "生成数据分析报告"
}
```

**Response 200**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "数据分析助手",
  "start": "有一个 CSV 文件",
  "goal": "生成数据分析报告",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

---

### 3. 获取 Agent 详情

**GET** `/agents/{agent_id}`

**Path Parameters**:
- `agent_id`: Agent ID (UUID)

**Response 200**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "数据分析助手",
  "start": "有一个 CSV 文件",
  "goal": "生成数据分析报告",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Response 404**:
```json
{
  "detail": "Agent not found"
}
```

---

### 4. 删除 Agent

**DELETE** `/agents/{agent_id}`

**Path Parameters**:
- `agent_id`: Agent ID (UUID)

**Response 204**: No Content

**Response 404**:
```json
{
  "detail": "Agent not found"
}
```

---

## Run 相关接口

### 5. 获取 Agent 的 Run 列表

**GET** `/agents/{agent_id}/runs`

**Path Parameters**:
- `agent_id`: Agent ID (UUID)

**Query Parameters**:
- `skip` (可选): 跳过的记录数，默认 0
- `limit` (可选): 返回的记录数，默认 100

**Response 200**:
```json
[
  {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "agent_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "SUCCEEDED",
    "result": "分析报告已生成",
    "error": null,
    "created_at": "2024-01-15T10:35:00Z",
    "updated_at": "2024-01-15T10:40:00Z"
  }
]
```

---

### 6. 创建并执行 Run

**POST** `/agents/{agent_id}/runs`

**Path Parameters**:
- `agent_id`: Agent ID (UUID)

**Request Body**:
```json
{
  "agent_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response 200**:
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "RUNNING",
  "result": null,
  "error": null,
  "created_at": "2024-01-15T10:35:00Z",
  "updated_at": "2024-01-15T10:35:00Z"
}
```

---

### 7. 获取 Run 详情

**GET** `/runs/{run_id}`

**Path Parameters**:
- `run_id`: Run ID (UUID)

**Response 200**:
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "SUCCEEDED",
  "result": "分析报告已生成",
  "error": null,
  "created_at": "2024-01-15T10:35:00Z",
  "updated_at": "2024-01-15T10:40:00Z"
}
```

---

## 数据类型说明

### Agent

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string (UUID) | Agent 唯一标识 |
| name | string | Agent 名称 |
| start | string | 起始状态描述 |
| goal | string | 目标状态描述 |
| created_at | string (ISO 8601) | 创建时间 |
| updated_at | string (ISO 8601) | 更新时间 |

### Run

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string (UUID) | Run 唯一标识 |
| agent_id | string (UUID) | 关联的 Agent ID |
| status | string | 运行状态：PENDING, RUNNING, SUCCEEDED, FAILED |
| result | string \| null | 执行结果（成功时） |
| error | string \| null | 错误信息（失败时） |
| created_at | string (ISO 8601) | 创建时间 |
| updated_at | string (ISO 8601) | 更新时间 |

### RunStatus 枚举

- `PENDING`: 等待执行
- `RUNNING`: 执行中
- `SUCCEEDED`: 执行成功
- `FAILED`: 执行失败

---

## 错误响应格式

所有错误响应都遵循以下格式：

```json
{
  "detail": "错误描述信息"
}
```

常见 HTTP 状态码：
- `200`: 成功
- `201`: 创建成功
- `204`: 删除成功（无内容）
- `400`: 请求参数错误
- `404`: 资源不存在
- `500`: 服务器内部错误
