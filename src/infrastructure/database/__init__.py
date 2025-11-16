"""数据库基础设施 - SQLAlchemy 配置和会话管理

为什么需要这个模块？
1. 集中管理数据库连接和会话
2. 提供异步数据库引擎（SQLAlchemy 2.0 + asyncio）
3. 导出 Base 供 ORM 模型使用
4. 导出 get_session 供依赖注入使用

设计原则：
- 使用异步引擎（async_engine）支持高并发
- 使用 AsyncSession 支持异步操作
- 使用 declarative_base 定义 ORM 模型基类
"""

from src.infrastructure.database.base import Base, get_session
from src.infrastructure.database.engine import (
    async_engine,
    get_db_session,
    get_engine,
    get_sync_engine,
    sync_engine,
)

__all__ = [
    "Base",
    "async_engine",
    "sync_engine",
    "get_engine",
    "get_sync_engine",
    "get_session",
    "get_db_session",
]
