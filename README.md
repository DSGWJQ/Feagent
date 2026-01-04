# Agent 中台系统

企业级 Agent 编排与执行平台 - 基于 FastAPI + LangChain + DDD-lite 架构

---

## ⚠️ 开发前必读

**在开始任何开发任务前，请先查看：**

📐 **[四层架构规范](./docs/ARCHITECTURE_GUIDE.md)** ⭐⭐⭐

- **用途**：5 分钟快速了解四层架构，防止开发偏离规范
- **内容**：Interface → Application → Domain → Infrastructure
- **包含**：各层职责、DTO 转换、三层校验、聚合根、常见错误

📚 **[完整开发规范](./docs/DEVELOPMENT_GUIDE.md)**

- **用途**：详细的开发规范（TDD、编码规范、测试规范等）
- **何时查看**：需要了解完整规范时

📋 **[文档索引](./docs/README.md)**

- **用途**：查找所有项目文档

---

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
python -m uvicorn src.interfaces.api.main:app --reload --port 8000
```

> 注意（Windows）：
> - 请使用 `python -m uvicorn ...`（而不是直接运行 `uvicorn ...`），这样可以确保仓库根目录加入 `PYTHONPATH` 并加载项目提供的 `watchfiles` shim。
> - 该 shim 会强制 Uvicorn 回退到更稳定的 `StatReload`，避免 `watchfiles` 在部分 Windows 终端向子进程发送异常的 Ctrl+C 信号，导致刚启动就退出或报 `KeyboardInterrupt`。
> - 如需恢复原生 `watchfiles`，可在启动命令前设置 `AGENT_ENABLE_WATCHFILES=1`。

### 前端初始化

详细步骤请参考：[前端初始化指南](docs/frontend_setup_guide.md)

```bash
cd web

# 1. 安装依赖
pnpm install

# 2. 启动开发服务器
pnpm dev
```

## Workflow 创建与对话（推荐链路）

- **创建并首次规划（SSE）**：`POST /api/workflows/chat-create/stream`
  - Body：`{ message: string, project_id?: string, run_id?: string }`
  - 契约：SSE 前 1 个事件内包含 `metadata.workflow_id`（用于前端跳转到 `/workflows/{id}/edit`）
- **增量修改（SSE）**：`POST /api/workflows/{workflow_id}/chat-stream`
- **内部创建（Deprecated）**：`POST /api/workflows/import`、`POST /api/workflows/generate-from-form`（仅内部/受控使用；对外推荐使用 chat-create）

## 主链路声明（Workflow vs Agent 实验入口）

- **Workflow 主链路**：以 `UseCase + gate + validator + RunEntry` 为事实源（对应 `/api/workflows/*` 与 `/api/runs/*`）。
- **多 Agent 闭环**（ConversationAgent / WorkflowAgent / CoordinatorAgent）：属于 Agent 子系统能力审计与实验入口，不作为 Workflow 主链路；相关文档以“现状审计/实验”口径解读。
- **可观测性区分**：API 级指标以路由路径维度区分（例如 `/api/workflows/*` vs `/api/conversation/*`），避免将实验入口误判为 Workflow 主链路故障。

## 灰度发布与回滚（Chat-Create）

### 观测项与阈值（示例）

- **错误率**：`/api/workflows/chat-create/stream` 5xx < 1%
- **创建耗时**：P95 < 3s（以首个含 `metadata.workflow_id` 的 SSE 事件为准）
- **兼容期流量**：日志事件 `legacy_create_workflow_called` 持续下降且无异常峰值

### 回滚开关

- **默认**：使用 chat-create（无需配置）
- **前端回滚（发布级）**：设置 `VITE_WORKFLOW_CREATE_MODE=legacy` 后重新发布前端
- **前端回滚（紧急/临时）**：访问根路由时追加 `?create=legacy`（仅影响该次访问）

## 项目结构

```
agent_data/
├── src/                        # 后端源码
│   ├── domain/                # 领域层（实体、值对象、领域服务）
│   ├── application/           # 应用层（用例编排、事务边界）
│   ├── interfaces/            # 接口层（FastAPI 路由、DTO）
│   │   └── api/
│   └── infrastructure/        # 基础设施（ORM、队列、缓存）
├── web/                       # 前端源码
│   └── src/
│       ├── app/              # 应用级配置
│       ├── layouts/          # 布局组件
│       ├── features/         # 业务功能模块
│       └── shared/           # 共享资源
├── definitions/               # 节点定义（YAML 规范）
│   ├── nodes/                # 节点定义文件
│   └── schemas/              # JSON Schema 校验文件
├── tests/                     # 测试
│   ├── unit/                 # 单元测试
│   └── integration/          # 集成测试
├── alembic/                   # 数据库迁移
├── docs/                      # 文档
└── scripts/                   # 脚本（含 validate_node_definitions.py）

```

## 开发文档

### 核心文档（必读）
- 📐 [四层架构规范](docs/ARCHITECTURE_GUIDE.md) ⭐⭐⭐ - 开发前必读（5 分钟）
- 📚 [完整开发规范](docs/DEVELOPMENT_GUIDE.md) - TDD、编码规范、测试规范
- 📋 [需求分析](docs/需求分析.md) - 项目需求与技术选型

### 架构与运维
- 🏗️ [多Agent协作架构](docs/architecture/current_agents.md) - Agent 子系统现状审计（不作为 Workflow 主链路）
- 📖 [复杂分析任务 Runbook](docs/architecture/current_agents.md#11-复杂分析任务运行手册runbook) - Agent 实验链路运行手册（不作为 Workflow 主链路）
- 🔧 [运维操作手册](docs/architecture/current_agents.md#118-运维操作手册) - 常见问题排查与手动干预
- 📋 [Coordinator 运维 Runbook](docs/architecture/current_agents.md#23-coordinator-运维-runbook) - 模块配置、指标观测、异常干预、知识库维护、告警追溯
- 📄 [通用节点 YAML 规范](docs/architecture/current_agents.md#14-通用节点-yaml-规范node-definition-specification) - 自描述节点定义、Schema 校验、示例模板
- 📊 [动态节点运维 Runbook](docs/operations/dynamic_node_runbook.md) - 监控指标、回滚流程、健康检查、故障排查
- 📝 [Prompt & Context 运维 Runbook](docs/architecture/current_agents.md#33-运维手册与回归测试-step-10) - 模板更新、版本切换、A/B 测试、上下文调试、回归测试

### 其他文档
- [前端架构总结](docs/frontend_architecture_summary.md)
- [文档索引](docs/README.md) - 查找所有文档

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
