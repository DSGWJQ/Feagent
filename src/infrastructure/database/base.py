"""数据库 Base 模型和会话管理

为什么需要 Base？
- SQLAlchemy 的 declarative_base 提供 ORM 模型基类
- 所有 ORM 模型都继承自 Base
- Base.metadata 包含所有表的元数据（用于 Alembic 迁移）

为什么需要 get_session？
- 提供异步会话（AsyncSession）
- 用于依赖注入（FastAPI Depends）
- 自动管理会话生命周期（打开、提交、关闭）
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from src.infrastructure.database.engine import engine


class Base(DeclarativeBase):
    """ORM 模型基类

    为什么使用 DeclarativeBase？
    - SQLAlchemy 2.0 推荐的方式（替代 declarative_base()）
    - 支持类型提示（IDE 友好）
    - 支持自定义类型映射

    所有 ORM 模型都继承自这个类：
    - class AgentModel(Base): ...
    - class RunModel(Base): ...
    """

    pass


# 创建异步会话工厂
# 为什么使用 async_sessionmaker？
# - 创建会话的工厂函数
# - 配置会话参数（expire_on_commit、autoflush 等）
# - 每次调用返回新的会话实例
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # 提交后不过期对象（避免额外查询）
    autoflush=False,  # 不自动 flush（手动控制）
    autocommit=False,  # 不自动提交（手动控制事务）
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（用于依赖注入）

    为什么使用 AsyncGenerator？
    - FastAPI 的 Depends 支持异步生成器
    - 自动管理会话生命周期（打开、提交、关闭）
    - 异常时自动回滚

    使用示例：
        @app.get("/agents")
        async def get_agents(session: AsyncSession = Depends(get_session)):
            result = await session.execute(select(AgentModel))
            return result.scalars().all()

    生命周期：
    1. 请求开始：创建会话
    2. 请求处理：使用会话
    3. 请求结束：关闭会话
    4. 异常时：自动回滚

    Yields:
        AsyncSession: 异步数据库会话
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
