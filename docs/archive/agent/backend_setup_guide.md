# 后端项目初始化指南

本文档提供 Agent 中台系统后端项目的完整初始化步骤。

---

## 环境要求

- **Python**: 3.11+ （推荐 3.11 或 3.12）
- **包管理器**: pip（内置）或 uv（推荐）
- **数据库**: PostgreSQL 14+（生产环境）或 SQLite（开发环境）
- **操作系统**: Windows / Linux / macOS

---

## 初始化步骤

### 步骤 1: 检查 Python 版本

```bash
python --version
# 输出应为: Python 3.11.x 或更高版本
```

如果版本不符合要求，请从 [Python 官网](https://www.python.org/downloads/) 下载安装。

---

### 步骤 2: 创建虚拟环境（推荐）

```bash
# 在项目根目录下创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows PowerShell:
.\venv\Scripts\Activate.ps1

# Windows CMD:
.\venv\Scripts\activate.bat

# Linux/macOS:
source venv/bin/activate
```

---

### 步骤 3: 安装依赖

```bash
# 安装核心依赖和开发依赖
pip install -e ".[dev]"

# 或者只安装核心依赖（不包含测试、代码质量工具）
pip install -e .
```

**依赖说明**：
- **核心依赖**：FastAPI、SQLAlchemy、LangChain、Pydantic、structlog 等
- **开发依赖**：pytest、ruff、black、mypy、pyright、pre-commit 等

---

### 步骤 4: 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，配置必要的环境变量
```

**必须配置的环境变量**：

```env
# 数据库连接（开发环境使用 SQLite）
DATABASE_URL=sqlite+aiosqlite:///./agent_platform.db

# 或使用 PostgreSQL（生产环境推荐）
# DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/agent_platform

# OpenAI API Key（必须）
OPENAI_API_KEY=your-openai-api-key-here

# 安全密钥（生产环境必须修改）
SECRET_KEY=your-secret-key-change-this-in-production
```

**可选配置**：
- `OPENAI_BASE_URL`: 自定义 OpenAI API 地址（如使用代理）
- `OPENAI_MODEL`: 默认使用的模型（默认: gpt-4o-mini）
- `CORS_ORIGINS`: 允许的跨域源（默认: http://localhost:3000）
- `LOG_LEVEL`: 日志级别（默认: INFO）

---

### 步骤 5: 初始化数据库

```bash
# 运行数据库迁移（创建表结构）
alembic upgrade head
```

**注意**：
- 首次运行时，如果没有迁移文件，需要先创建迁移：
  ```bash
  alembic revision --autogenerate -m "Initial migration"
  alembic upgrade head
  ```
- 开发环境使用 SQLite，数据库文件会自动创建在项目根目录
- 生产环境使用 PostgreSQL，需要先创建数据库

---

### 步骤 6: 启动开发服务器

```bash
# 方式 1: 使用 uvicorn 命令（推荐）
uvicorn src.interfaces.api.main:app --reload --port 8000

# 方式 2: 直接运行 main.py
python -m src.interfaces.api.main

# 方式 3: 使用 fastapi CLI（需要安装 fastapi-cli）
fastapi dev src/interfaces/api/main.py
```

**启动成功后**：
- 服务地址: http://localhost:8000
- API 文档 (Swagger UI): http://localhost:8000/docs
- API 文档 (ReDoc): http://localhost:8000/redoc
- 健康检查: http://localhost:8000/health

---

### 步骤 7: 验证安装

```bash
# 测试健康检查端点
curl http://localhost:8000/health

# 预期输出:
# {
#   "status": "healthy",
#   "app_name": "Agent Platform",
#   "version": "0.1.0",
#   "env": "development"
# }
```

---

## 开发工具配置

### 代码格式化与检查

```bash
# 使用 Ruff 检查代码
ruff check src tests

# 使用 Ruff 自动修复
ruff check --fix src tests

# 使用 Black 格式化代码
black src tests

# 使用 Pyright 进行类型检查
pyright src
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit

# 运行集成测试
pytest tests/integration

# 生成覆盖率报告
pytest --cov=src --cov-report=html
# 查看报告: 打开 htmlcov/index.html
```

---

## 故障排查与日志

```text
日志文件: logs/app.log
日志格式: 简化 JSON（包含 time、level、message）
Trace ID: 响应头 X-Trace-Id，用于关联请求与日志
```

```bash
# 常见排查步骤
# 1) 触发问题后，根据响应头中的 X-Trace-Id 在日志中检索
# 2) 查看最近的 500/422 记录，定位具体方法、路径与错误信息
# 3) 若为参数校验错误（422），响应体的 detail 字段包含具体校验信息
# 4) 若为服务器错误（500），结合日志与依赖服务状态进一步分析
```

### 配置 Pre-commit（可选）

```bash
# 安装 pre-commit hooks
pre-commit install

# 手动运行所有 hooks
pre-commit run --all-files
```

---

## 项目结构说明

```
agent_data/
├── src/                        # 后端源码
│   ├── __init__.py
│   ├── config.py              # 配置管理（Pydantic Settings）
│   ├── domain/                # 领域层
│   │   ├── __init__.py
│   │   ├── entities/          # 实体（Agent, Run, Task）
│   │   ├── value_objects/     # 值对象
│   │   ├── services/          # 领域服务
│   │   └── ports/             # Port 接口（Protocol/ABC）
│   ├── application/           # 应用层
│   │   ├── __init__.py
│   │   ├── use_cases/         # 用例（创建 Agent、执行 Run）
│   │   └── services/          # 应用服务
│   ├── interfaces/            # 接口层
│   │   └── api/
│   │       ├── __init__.py
│   │       ├── main.py        # FastAPI 应用入口
│   │       ├── routes/        # 路由（agents, runs）
│   │       ├── dto/           # 数据传输对象（Pydantic）
│   │       └── middleware/    # 中间件
│   ├── lc/                    # LangChain 层
│   │   ├── __init__.py
│   │   ├── chains/            # 链（计划生成、执行）
│   │   ├── agents/            # Agent 实现
│   │   ├── tools/             # 工具（HTTP、SQL、脚本）
│   │   └── memory/            # 记忆管理
│   └── infrastructure/        # 基础设施层
│       ├── __init__.py
│       ├── database/          # 数据库（SQLAlchemy）
│       │   ├── models.py      # ORM 模型
│       │   └── repositories/  # 仓储实现
│       ├── llm/               # LLM 客户端
│       ├── queue/             # 任务队列
│       └── logging/           # 日志配置
├── tests/                     # 测试
│   ├── __init__.py
│   ├── conftest.py           # Pytest 配置
│   ├── unit/                 # 单元测试
│   └── integration/          # 集成测试
├── alembic/                   # 数据库迁移
│   ├── env.py                # Alembic 环境配置
│   ├── script.py.mako        # 迁移脚本模板
│   └── versions/             # 迁移版本
├── docs/                      # 文档
├── logs/                      # 日志文件（自动创建）
├── .env                       # 环境变量（不提交到 Git）
├── .env.example              # 环境变量模板
├── .gitignore                # Git 忽略文件
├── alembic.ini               # Alembic 配置
├── pyproject.toml            # 项目配置（依赖、工具配置）
└── README.md                 # 项目说明
```

---

## 常见问题

### 1. 数据库连接失败

**问题**：启动时报错 `sqlalchemy.exc.OperationalError`

**解决方案**：
- 检查 `.env` 文件中的 `DATABASE_URL` 是否正确
- 如果使用 PostgreSQL，确保数据库已创建且服务正在运行
- 如果使用 SQLite，确保有写入权限

### 2. OpenAI API Key 未配置

**问题**：调用 LLM 时报错 `openai.error.AuthenticationError`

**解决方案**：
- 在 `.env` 文件中配置 `OPENAI_API_KEY`
- 确保 API Key 有效且有足够的配额

### 3. 端口被占用

**问题**：启动时报错 `OSError: [Errno 48] Address already in use`

**解决方案**：
```bash
# 方式 1: 使用其他端口
uvicorn src.interfaces.api.main:app --reload --port 8001

# 方式 2: 杀死占用端口的进程
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/macOS:
lsof -ti:8000 | xargs kill -9
```

### 4. 依赖安装失败

**问题**：`pip install` 时报错

**解决方案**：
```bash
# 升级 pip
python -m pip install --upgrade pip

# 使用国内镜像源（加速）
pip install -e ".[dev]" -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## 下一步

1. **实现领域模型**：在 `src/domain/entities/` 中定义 Agent、Run、Task 实体
2. **实现数据库模型**：在 `src/infrastructure/database/models.py` 中定义 ORM 模型
3. **创建数据库迁移**：使用 `alembic revision --autogenerate` 生成迁移文件
4. **实现 API 路由**：在 `src/interfaces/api/routes/` 中实现 agents 和 runs 路由
5. **集成 LangChain**：在 `src/lc/` 中实现 Agent 编排逻辑
6. **编写测试**：在 `tests/` 中编写单元测试和集成测试

---

## 参考资源

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 文档](https://docs.sqlalchemy.org/en/20/)
- [LangChain 官方文档](https://python.langchain.com/)
- [Pydantic 官方文档](https://docs.pydantic.dev/)
- [Alembic 官方文档](https://alembic.sqlalchemy.org/)
- [项目开发规范](./develop_document.md)
