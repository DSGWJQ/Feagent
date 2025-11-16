"""Alembic 环境配置"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 导入配置
from src.config import settings

# 导入所有模型（确保 Alembic 能检测到所有表）
from src.infrastructure.database.base import Base

# 必须导入所有模型，否则 Alembic 无法检测到表
# 即使没有直接使用，也要导入（让 SQLAlchemy 注册模型）
from src.infrastructure.database.models import AgentModel, RunModel  # noqa: F401

# Alembic Config 对象
config = context.config

# 从环境变量设置数据库 URL
config.set_main_option("sqlalchemy.url", settings.database_url)

# 配置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 元数据对象（用于自动生成迁移）
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """在离线模式下运行迁移（生成 SQL 脚本）"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """执行迁移"""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """异步运行迁移"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """在在线模式下运行迁移（连接数据库）"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
