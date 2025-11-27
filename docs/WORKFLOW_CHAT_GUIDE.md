# 工作流 AI 聊天功能使用指南

## 功能说明

工作流 AI 聊天允许您通过自然语言描述来创建和修改工作流，AI 会自动生成对应的节点和连线。

## 使用方式

### 方式 1：Mock 模式（推荐用于前端开发）

**优点**：无需启动后端，立即体验功能

1. 修改 `web/.env.development` 文件：
   ```bash
   VITE_USE_MOCK=true
   ```

2. 重启前端开发服务器：
   ```bash
   cd web
   pnpm dev
   ```

3. 打开工作流编辑器，在右侧 AI 聊天框中输入：
   - "创建 HTTP 请求" → 生成 HTTP 请求工作流
   - "添加 LLM 节点" → 生成 LLM 文本生成工作流
   - "数据库查询" → 生成数据库查询工作流

### 方式 2：真实后端（生产环境）

**优点**：使用真实的 AI 能力，支持复杂的工作流生成

1. 确保 `web/.env.development` 中：
   ```bash
   VITE_USE_MOCK=false
   ```

2. 启动后端服务器：
   ```bash
   # 在项目根目录
   uvicorn src.interfaces.api.main:app --reload --port 8000
   ```

3. 启动前端服务器：
   ```bash
   cd web
   pnpm dev
   ```

4. 在工作流编辑器的 AI 聊天框中输入自然语言描述

## 错误处理

### 错误 1：ERR_CONNECTION_REFUSED

**原因**：后端服务器未启动

**解决方案**：
- 选项 A：启动后端服务器（见上文"方式 2"）
- 选项 B：启用 Mock 模式（见上文"方式 1"）

### 错误 2：501 Not Implemented

**原因**：后端 Chat 功能被禁用

**解决方案**：
1. 临时使用 Mock 模式
2. 联系开发团队启用后端 Chat 功能
3. 修改后端代码 `src/interfaces/api/routes/chat_workflows.py`：
   ```python
   # 将 get_enhanced_chat_use_case() 函数改为返回实际的 use case
   ```

## Mock 模式支持的命令

| 用户输入 | 生成的工作流 |
|---------|------------|
| "HTTP"、"API"、"请求" | HTTP 请求工作流 |
| "LLM"、"AI"、"模型" | LLM 文本生成工作流 |
| "数据库"、"SQL" | 数据库查询工作流 |
| 其他文本 | 基础 JavaScript 处理工作流 |

## 技术实现

### 前端改进

1. **健康检查**：自动检测后端是否可用（2秒超时）
2. **Mock 模式**：基于关键词匹配生成模拟工作流
3. **友好错误**：提供详细的错误信息和解决方案
4. **环境变量**：通过 `VITE_USE_MOCK` 控制模式切换

### 后端状态

- ✅ API 路由已实现：`POST /api/workflows/{id}/chat`
- ⚠️ Chat 功能被禁用：返回 501 错误
- 📝 需要实现：`EnhancedChatWorkflowUseCase`

## 开发计划

- [ ] 实现后端 Chat Use Case
- [ ] 集成真实的 LLM（OpenAI/Claude）
- [ ] 支持更复杂的工作流修改
- [ ] 添加对话历史记录
- [ ] 支持工作流版本控制

## 常见问题

**Q: Mock 模式下生成的工作流可以保存吗？**
A: 可以！Mock 模式只是模拟聊天功能，生成的工作流结构与真实 API 一致，可以正常保存和执行。

**Q: 如何切换回真实 API？**
A: 修改 `.env.development` 中 `VITE_USE_MOCK=false`，并重启前端服务器。

**Q: 后端 API 什么时候会启用？**
A: 需要开发团队实现 `EnhancedChatWorkflowUseCase` 并启用功能。

## 相关文件

- 前端组件：`web/src/shared/components/WorkflowAIChat.tsx`
- 后端路由：`src/interfaces/api/routes/chat_workflows.py`
- 环境配置：`web/.env.development`
- 工作流编辑器：`web/src/features/workflows/pages/WorkflowEditorPage.tsx`
