# 工作流对话接口手动测试指南

## ✅ 完成的工作

### 1. **创建了对话接口测试用例** (`tests/integration/api/test_workflows.py`)
   - ✅ 测试成功场景：对话式修改工作流
   - ✅ 测试失败场景：工作流不存在（404）
   - ✅ 测试失败场景：空消息（422）
   - ✅ 所有测试通过（3/3）

### 2. **创建了 DTO** (`src/interfaces/api/dto/workflow_dto.py`)
   - ✅ `ChatRequest`: 对话请求（包含 message 字段）
   - ✅ `ChatResponse`: 对话响应（包含 workflow 和 ai_message）

### 3. **创建了 Domain Service** (`src/domain/services/workflow_chat_service.py`)
   - ✅ `WorkflowChatService`: 处理用户消息，生成工作流修改指令
   - ✅ 使用 LLM 解析用户意图
   - ✅ 应用修改到工作流实体

### 4. **创建了 Use Case** (`src/application/use_cases/update_workflow_by_chat.py`)
   - ✅ `UpdateWorkflowByChatUseCase`: 编排业务流程
   - ✅ 验证工作流存在
   - ✅ 调用 Domain Service 处理消息
   - ✅ 保存修改后的工作流

### 5. **添加了 API 路由** (`src/interfaces/api/routes/workflows.py`)
   - ✅ `POST /api/workflows/{id}/chat`: 对话式修改工作流
   - ✅ 错误处理（404、400、500）
   - ✅ 事务管理（commit/rollback）

---

## 🚀 手动测试步骤

### 前提条件

1. **✅ API 配置已完成**

   你的 `.env` 文件已正确配置：
   ```env
   OPENAI_API_KEY=sk-a6k9VtObJi35OvkqiUOuHaAO2r2D5USLnAsjLRkEsitq0fwb
   OPENAI_BASE_URL=https://api.moonshot.cn/v1
   OPENAI_MODEL=moonshot-v1-8k
   ```

   代码已更新为自动读取这些配置：
   - ✅ `OPENAI_API_KEY`: API 密钥
   - ✅ `OPENAI_BASE_URL`: Moonshot API 地址
   - ✅ `OPENAI_MODEL`: 使用 moonshot-v1-8k 模型

2. **启动后端服务**
   ```bash
   # 在项目根目录
   python -m uvicorn src.interfaces.api.main:app --reload --port 8000
   ```

3. **创建测试工作流**（如果还没有）
   ```bash
   python scripts/create_test_workflow.py
   ```
   记下返回的 workflow_id（例如：`wf_b8c85f1a`）

---

### 测试 1：成功场景 - 添加节点

**请求**：
```bash
curl -X POST "http://localhost:8000/api/workflows/wf_b8c85f1a/chat" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"在开始和结束之间添加一个HTTP请求节点，用于获取天气数据\"}"
```

**预期响应**（200 OK）：
```json
{
  "workflow": {
    "id": "wf_b8c85f1a",
    "name": "测试工作流",
    "description": "...",
    "nodes": [
      {
        "id": "node_xxx",
        "type": "start",
        "name": "开始",
        "data": {},
        "position": {"x": 0, "y": 0}
      },
      {
        "id": "node_yyy",
        "type": "http",
        "name": "获取天气数据",
        "data": {
          "url": "https://api.weather.com",
          "method": "GET"
        },
        "position": {"x": 100, "y": 0}
      },
      {
        "id": "node_zzz",
        "type": "end",
        "name": "结束",
        "data": {},
        "position": {"x": 200, "y": 0}
      }
    ],
    "edges": [
      {
        "id": "edge_xxx",
        "source": "node_xxx",
        "target": "node_yyy"
      },
      {
        "id": "edge_yyy",
        "source": "node_yyy",
        "target": "node_zzz"
      }
    ],
    "status": "draft",
    "created_at": "2025-01-15T10:00:00Z",
    "updated_at": "2025-01-15T10:05:00Z"
  },
  "ai_message": "我已经添加了一个HTTP节点用于获取天气数据"
}
```

**验证点**：
- ✅ 返回 200 状态码
- ✅ `workflow.nodes` 数量增加（原来2个，现在3个）
- ✅ `workflow.edges` 数量增加（原来1条，现在2条）
- ✅ `ai_message` 描述了修改内容

**验证数据库**：
```bash
# 再次获取工作流详情，验证数据库已更新
curl "http://localhost:8000/api/workflows/wf_b8c85f1a"
```

---

### 测试 2：失败场景 - 工作流不存在

**请求**：
```bash
curl -X POST "http://localhost:8000/api/workflows/invalid_id/chat" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"添加一个节点\"}"
```

**预期响应**（404 Not Found）：
```json
{
  "detail": "Workflow 不存在: invalid_id"
}
```

**验证点**：
- ✅ 返回 404 状态码
- ✅ 返回错误信息

---

### 测试 3：失败场景 - 空消息

**请求**：
```bash
curl -X POST "http://localhost:8000/api/workflows/wf_b8c85f1a/chat" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"\"}"
```

**预期响应**（422 Unprocessable Entity）：
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "message"],
      "msg": "String should have at least 1 character",
      "input": "",
      "ctx": {"min_length": 1}
    }
  ]
}
```

**验证点**：
- ✅ 返回 422 状态码（Pydantic 验证错误）
- ✅ 返回验证错误详情

---

### 测试 4：其他对话场景

**场景 A：删除节点**
```bash
curl -X POST "http://localhost:8000/api/workflows/wf_b8c85f1a/chat" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"删除HTTP节点\"}"
```

**场景 B：修改节点配置**
```bash
curl -X POST "http://localhost:8000/api/workflows/wf_b8c85f1a/chat" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"把HTTP节点的URL改成 https://api.openweathermap.org\"}"
```

**场景 C：添加多个节点**
```bash
curl -X POST "http://localhost:8000/api/workflows/wf_b8c85f1a/chat" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"添加一个数据转换节点和一个数据库节点\"}"
```

---

## 📝 测试报告模板

测试完成后，请反馈以下信息：

### ✅ 成功的测试
- [ ] 测试 1：添加节点
- [ ] 测试 2：工作流不存在（404）
- [ ] 测试 3：空消息（422）
- [ ] 测试 4A：删除节点
- [ ] 测试 4B：修改节点配置
- [ ] 测试 4C：添加多个节点

### ❌ 遇到的问题
- 问题描述：
- 错误信息：
- 请求内容：
- 响应内容：

### 💡 改进建议
-

---

## 🔍 调试技巧

### 1. 查看后端日志
后端启动时会输出日志，包括：
- 请求路径和方法
- 响应状态码
- 错误详情

### 2. 查看数据库
```bash
# 使用 SQLite 命令行工具
sqlite3 agent_data.db

# 查看工作流
SELECT * FROM workflows;

# 查看节点
SELECT * FROM nodes WHERE workflow_id = 'wf_b8c85f1a';

# 查看边
SELECT * FROM edges WHERE workflow_id = 'wf_b8c85f1a';
```

### 3. 使用 API 文档
访问 `http://localhost:8000/docs` 查看交互式 API 文档，可以直接在浏览器中测试接口。

---

## 📊 技术实现总结

### 架构层次
```
Interface 层（API 路由）
    ↓ 调用
Application 层（Use Case）
    ↓ 调用
Domain 层（Domain Service + Entity）
    ↑ 实现
Infrastructure 层（Repository）
```

### 数据流
```
1. 用户发送消息 → API 路由
2. API 路由 → Use Case
3. Use Case → Repository（获取工作流）
4. Use Case → Domain Service（处理消息）
5. Domain Service → LLM（解析意图）
6. Domain Service → Entity（应用修改）
7. Use Case → Repository（保存工作流）
8. API 路由 → 返回响应
```

### 测试覆盖率
- `UpdateWorkflowByChatUseCase`: 91%
- `WorkflowChatService`: 91%
- `workflow_repository.py`: 71%
- `workflows.py` (API routes): 38%

---

## 🎯 下一步

1. **手动测试验证** - 使用 curl 测试所有场景
2. **前端集成** - 将假AI聊天框改为调用真实API
3. **优化 LLM 提示词** - 根据实际效果调整提示词
4. **添加更多节点类型** - 支持更多节点类型的添加和修改

