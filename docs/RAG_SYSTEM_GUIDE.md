# RAG系统部署和使用指南

## 概述

本文档介绍如何在Agent Platform中部署和使用RAG（Retrieval-Augmented Generation）功能。RAG系统允许用户上传文档到知识库，并在AI对话中使用这些文档进行智能问答。

## 系统架构

### 后端架构

```
┌─────────────────────────────────────────────────┐
│              Interface Layer (接口层)             │
│  FastAPI Routes + RAG API Endpoints                │
└────────────────┬────────────────────────────────┘
                 │ HTTP Request → Input
┌────────────────▼────────────────────────────────┐
│          Application Layer (应用层)               │
│  RAGService: 文档处理、检索编排                    │
└────────────────┬────────────────────────────────┘
                 │ Ports (Protocol/ABC)
┌────────────────▼────────────────────────────────┐
│            Domain Layer (领域层)                  │
│  Entities: Document, DocumentChunk               │
│  ❌ NO FRAMEWORK IMPORTS ALLOWED                 │
└────────────────┬────────────────────────────────┘
                 │ Adapters implement Ports
┌────────────────▼────────────────────────────────┐
│       Infrastructure Layer (基础设施层)           │
│  SQLite (元数据) + ChromaDB (向量存储)             │
└─────────────────────────────────────────────────┘
```

### 前端架构

```
┌─────────────────────────────────────────────────┐
│              React + TypeScript                 │
├─────────────────────────────────────────────────┤
│  WorkflowEditorPageWithMutex                    │
│  ├── NodePalette (节点面板)                      │
│  ├── ReactFlow Canvas (画布)                     │
│  └── WorkflowAIChatWithRAG (AI聊天 + RAG)        │
│      ├── Chat Tab (对话标签)                     │
│      ├── Context Tab (上下文检索)                 │
│      └── Documents Tab (文档管理)                 │
└─────────────────────────────────────────────────┘
```

## 部署步骤

### 1. 后端部署

#### 1.1 环境变量配置

确保 `.env` 文件包含以下RAG配置：

```bash
# RAG / Knowledge Base Configuration
VECTOR_STORE_TYPE=chroma
CHROMA_PATH=data/chroma_db
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
KB_GLOBAL_ENABLED=true
KB_PER_WORKFLOW_ENABLED=true
RAG_TOP_K=5
RAG_SIMILARITY_THRESHOLD=0.7
UPLOAD_DIR=uploads

# OpenAI配置
OPENAI_API_KEY=your-openai-api-key
OPENAI_BASE_URL=https://api.openai.com/v1  # 或其他兼容API
```

#### 1.2 安装依赖

```bash
pip install -e ".[dev]"
```

#### 1.3 数据库迁移

```bash
# 创建数据库表
alembic upgrade head
```

#### 1.4 启动后端服务

```bash
uvicorn src.interfaces.api.main:app --reload --port 8000
```

### 2. 前端部署

#### 2.1 安装依赖

```bash
cd web
pnpm install
```

#### 2.2 启动前端服务

```bash
pnpm dev
```

#### 2.3 访问应用

打开浏览器访问: `http://localhost:5173`

## 功能使用指南

### 1. 访问RAG功能

1. 创建或选择一个工作流
2. 在右侧面板找到AI助手
3. 点击右上角的"RAG"开关启用RAG功能

### 2. 文档管理

#### 2.1 上传文档

- 点击"文档"标签页
- 点击"上传文档"按钮或"手动添加"按钮
- 支持的格式：`.txt`, `.md`, `.doc`, `.docx`
- 填写文档标题和内容
- 系统自动分块并生成向量嵌入

#### 2.2 查看文档列表

- 文档列表显示所有上传的文档
- 显示文档状态：已处理、处理中、处理失败
- 可以查看文档内容、删除文档

#### 2.3 文档状态

- **处理中**：文档正在被分块和向量化
- **已处理**：文档已成功处理，可用于检索
- **处理失败**：文档处理失败，需要重新上传

### 3. 上下文检索

#### 3.1 搜索配置

- 点击"上下文"标签页
- 设置检索参数：
  - 返回文档块数量（3/5/10条）
  - 最大上下文长度（2000/4000/8000 tokens）

#### 3.2 执行检索

- 在搜索框输入查询关键词
- 点击"检索"按钮
- 系统返回相关文档块和来源信息
- 显示相似度分数和文档预览

#### 3.3 检索结果

- **文档块统计**：显示检索到的文档块数量
- **Token统计**：显示上下文的Token数量
- **来源信息**：显示相关文档及其相似度分数
- **格式化上下文**：可直接用于AI回答的格式化文本

### 4. AI对话增强

#### 4.1 RAG对话

- 启用RAG后，AI会基于知识库回答问题
- 对话历史中会显示检索到的上下文信息
- AI回答更加准确和具体

#### 4.2 对话模式切换

- **画布模式**：编辑工作流节点
- **聊天模式**：与AI对话并修改工作流
- RAG功能在聊天模式下工作最佳

## API接口说明

### 上下文检索

```http
GET /api/workflows/{workflow_id}/chat-context
```

参数：
- `query` (string): 查询关键词
- `max_context_length` (int): 最大上下文长度，默认4000
- `top_k` (int): 返回文档块数量，默认5

### 文档上传

```http
POST /api/workflows/{workflow_id}/documents
```

请求体：
```json
{
  "title": "文档标题",
  "content": "文档内容",
  "source": "upload"
}
```

### 文档列表

```http
GET /api/workflows/{workflow_id}/documents
```

### 文档搜索

```http
POST /api/workflows/{workflow_id}/documents/search
```

请求体：
```json
{
  "query": "搜索关键词",
  "limit": 10,
  "threshold": 0.7
}
```

### 删除文档

```http
DELETE /api/workflows/{workflow_id}/documents/{document_id}
```

## 技术细节

### 向量存储

- **默认存储**: ChromaDB
- **向量维度**: 1536 (OpenAI text-embedding-3-small)
- **相似度计算**: 余弦相似度
- **分块大小**: 1000 tokens，重叠200 tokens

### 文档处理

1. **文本提取**: 支持纯文本和Markdown
2. **文本分块**: 使用递归字符分割器
3. **向量生成**: 调用OpenAI嵌入API
4. **存储**: 元数据存储在SQLite，向量存储在ChromaDB

### 检索优化

- **混合检索**: 语义搜索 + 关键词匹配
- **重排序**: 基于相关性的二次排序
- **上下文构建**: Token限制下的智能截断

## 监控和维护

### 健康检查

```bash
# 检查RAG系统状态
curl http://localhost:8000/api/health

# 检查RAG配置
curl http://localhost:8000/api/rag/config
```

### 日志监控

RAG相关的日志标记：
- `[RAG]` - RAG相关操作
- `[ChromaDB]` - 向量数据库操作
- `[Embedding]` - 嵌入生成操作

### 性能优化

- **向量存储**: 考虑使用专业向量数据库（如Pinecone）
- **嵌入缓存**: 缓存常用文档的向量
- **异步处理**: 文档处理使用异步任务队列
- **批量操作**: 支持批量文档上传和处理

## 故障排除

### 常见问题

#### 1. 文档上传失败

**问题**: 文档上传后显示"处理失败"

**解决方案**:
- 检查OpenAI API密钥是否正确
- 确认网络连接正常
- 查看后端日志中的详细错误信息

#### 2. 上下文检索无结果

**问题**: 检索时返回空结果

**解决方案**:
- 确认文档已成功处理（状态为"已处理"）
- 降低相似度阈值
- 尝试不同的查询关键词

#### 3. RAG开关无响应

**问题**: 启用RAG开关后功能无效

**解决方案**:
- 刷新页面重试
- 检查浏览器控制台是否有JavaScript错误
- 确认后端RAG服务正常运行

### 调试工具

#### 后端调试

```python
# 检查RAG配置
python test_rag_simple.py

# 检查向量存储
python test_chromadb.py
```

#### 前端调试

打开浏览器开发者工具，查看：
- Network标签页中的API请求
- Console标签页中的错误信息
- Components标签页中的组件状态

## 扩展开发

### 添加新文档格式

1. 在 `scripts/ingest_docs.py` 中添加新的文档处理器
2. 更新前端上传组件的文件类型限制
3. 测试新格式的处理流程

### 集成其他向量存储

1. 在 `src/config.py` 中添加新的向量存储配置
2. 实现对应的RetrieverService
3. 更新RAGConfigManager支持新的存储类型

### 自定义嵌入模型

1. 实现新的EmbeddingProvider
2. 更新ChromaRetrieverService支持新模型
3. 添加相关的配置选项

## 总结

RAG系统现已成功集成到Agent Platform中，提供了完整的文档管理、上下文检索和AI对话增强功能。用户可以：

1. **上传和管理文档**到知识库
2. **检索相关上下文**用于AI回答
3. **享受更智能的对话体验**，基于实际文档内容

系统采用了模块化设计，易于扩展和维护，为后续的功能增强奠定了坚实基础。