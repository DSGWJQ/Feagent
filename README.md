# Agent 中台系统

企业级 Agent 编排与执行平台 - 基于 FastAPI + LangChain + DDD-lite 架构

## 项目简介

Agent 中台系统是一个企业级的 AI Agent 编排与执行平台，支持用户通过"起点 + 目的"一句话创建 Agent，系统自动生成执行计划并完成任务。

### 核心特性

- 🚀 **一句话创建 Agent**：输入 start + goal，自动创建并执行
- 🎯 **结果导向**：以目标为导向，不限制执行过程
- 🔧 **可配置**：创建后可调整 Agent 行为与参数
- 📊 **实时监控**：SSE 实时推送执行进度与日志
- 🏗️ **企业级架构**：DDD-lite + 六边形架构，模块化、可测试、易扩展

## 技术栈

### 后端
- **Web 框架**：FastAPI + Pydantic v2
- **数据库**：SQLAlchemy 2.0 + Alembic（PostgreSQL/SQLite）
- **AI 编排**：LangChain（LCEL/Runnable/Agents）
- **任务调度**：asyncio + APScheduler
- **日志**：structlog（JSON 格式 + trace_id）
- **稳定性**：tenacity（重试）、超时、幂等、限流
- **测试**：pytest + pytest-asyncio

### 前端
- **框架**：Vite + React + TypeScript
- **UI 组件**：Ant Design + Pro Components
- **状态管理**：TanStack Query
- **实时通信**：EventSource（SSE）

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- pnpm 8+
- PostgreSQL 14+（可选，开发环境可使用 SQLite）

### 后端初始化

详细步骤请参考：[后端初始化指南](docs/backend_setup_guide.md)

```bash
# 1. 安装依赖
pip install -e ".[dev]"

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置数据库和 API Key

# 3. 初始化数据库
alembic upgrade head

# 4. 启动开发服务器
uvicorn src.interfaces.api.main:app --reload --port 8000
```

### 前端初始化

详细步骤请参考：[前端初始化指南](docs/frontend_setup_guide.md)

```bash
cd web

# 1. 安装依赖
pnpm install

# 2. 启动开发服务器
pnpm dev
```

## 项目结构

```
agent_data/
├── src/                        # 后端源码
│   ├── domain/                # 领域层（实体、值对象、领域服务）
│   ├── application/           # 应用层（用例编排、事务边界）
│   ├── interfaces/            # 接口层（FastAPI 路由、DTO）
│   │   └── api/
│   ├── lc/                    # LangChain（chains/agents/tools）
│   └── infrastructure/        # 基础设施（ORM、队列、缓存）
├── web/                       # 前端源码
│   └── src/
│       ├── app/              # 应用级配置
│       ├── layouts/          # 布局组件
│       ├── features/         # 业务功能模块
│       └── shared/           # 共享资源
├── tests/                     # 测试
│   ├── unit/                 # 单元测试
│   └── integration/          # 集成测试
├── alembic/                   # 数据库迁移
├── docs/                      # 文档
└── scripts/                   # 脚本

```

## 开发规范

- [完整开发规范](docs/develop_document.md)
- [前端架构总结](docs/frontend_architecture_summary.md)
- [需求分析](docs/需求分析.md)

## 核心概念

### Agent
用户通过"起点 + 目的"创建的智能代理，包含配置、工具、执行策略等。

### Run
Agent 的一次执行实例，包含执行状态、日志、结果等。

### Task
Run 中的单个执行步骤，支持重试、超时、幂等。

## API 文档

启动后端服务后，访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 测试

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit

# 运行集成测试
pytest tests/integration

# 生成覆盖率报告
pytest --cov=src --cov-report=html
```

## 部署

### Docker Compose

```bash
docker-compose up -d
```

### 生产环境

详细部署指南请参考：[部署文档](docs/deployment.md)

## 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 许可证

MIT License

## 联系方式

- 项目主页：[GitHub](https://github.com/yourusername/agent-platform)
- 问题反馈：[Issues](https://github.com/yourusername/agent-platform/issues)

