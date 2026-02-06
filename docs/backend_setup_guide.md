# 后端初始化指南（Backend Setup Guide）

本文件用于修复 README 的历史链接，并给出**最小可用**的后端启动步骤。

## 环境要求

- Python 3.11+

## 安装与启动（开发）

```bash
# 1) 安装依赖
pip install -e ".[dev]"

# 2) 配置环境变量
cp .env.example .env

# 3) 初始化数据库（SQLite/PG 均可；按实际 DATABASE_URL）
alembic upgrade head

# 4) 启动服务
python -m uvicorn src.interfaces.api.main:app --reload --port 8000
```

> Windows 说明：推荐使用 `python -m uvicorn ...` 以确保仓库根目录加入 `PYTHONPATH`。
