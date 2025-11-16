"""数据库引擎配置

为什么需要单独的 engine 模块？
1. 分离关注点：引擎配置独立于模型定义
2. 避免循环导入：Base 和 engine 分开定义
3. 便于测试：可以轻松创建测试引擎

设计说明：
- 使用 create_async_engine 创建异步引擎（未来使用）
- 使用 create_engine 创建同步引擎（当前使用）
- 从配置文件读取 database_url
- 配置连接池参数（pool_size、max_overflow）
- 配置 echo 参数（开发环境打印 SQL）
"""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings


def get_engine() -> AsyncEngine:
    """创建数据库引擎

    为什么使用工厂函数？
    - 延迟初始化：只在需要时创建引擎
    - 便于测试：可以传入不同的配置
    - 便于管理：可以在应用启动时创建，关闭时销毁

    配置说明：
    - echo: 是否打印 SQL（开发环境开启，生产环境关闭）
    - pool_size: 连接池大小（默认 5）
    - max_overflow: 最大溢出连接数（默认 10）
    - pool_pre_ping: 连接前检查（避免使用失效连接）

    返回：
        AsyncEngine: 异步数据库引擎
    """
    return create_async_engine(
        settings.database_url,
        echo=settings.debug,  # 开发环境打印 SQL
        pool_size=5,  # 连接池大小
        max_overflow=10,  # 最大溢出连接数
        pool_pre_ping=True,  # 连接前检查（避免使用失效连接）
    )


# 全局异步引擎实例（未来使用）
async_engine = get_engine()


def get_sync_engine() -> Engine:
    """创建同步数据库引擎

    为什么需要同步引擎？
    - 当前的 Repository 实现是同步的
    - FastAPI 路由可以使用同步或异步
    - 同步代码更简单，易于理解和调试

    未来迁移到异步：
    - 修改 Repository 为异步
    - 修改路由为异步
    - 使用 async_engine

    配置说明：
    - echo: 是否打印 SQL
    - pool_size: 连接池大小
    - max_overflow: 最大溢出连接数
    - pool_pre_ping: 连接前检查

    返回：
        Engine: 同步数据库引擎
    """
    # 将异步 URL 转换为同步 URL
    # sqlite+aiosqlite:///... → sqlite:///...
    sync_url = settings.database_url.replace("+aiosqlite", "")

    return create_engine(
        sync_url,
        echo=settings.debug,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )


# 全局同步引擎实例
sync_engine = get_sync_engine()

# 创建 Session 工厂
SessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db_session() -> Generator[Session, None, None]:
    """获取数据库会话

    这是 FastAPI 依赖注入函数：
    - 为每个请求创建新的 Session
    - 请求结束后自动关闭 Session
    - 使用 yield 确保资源正确释放

    为什么使用 Generator？
    - FastAPI 支持 Generator 作为依赖
    - yield 前的代码在请求开始时执行
    - yield 后的代码在请求结束时执行
    - 确保 Session 总是被关闭

    使用示例：
    >>> @app.get("/api/agents")
    >>> def list_agents(session: Session = Depends(get_db_session)):
    >>>     repo = SQLAlchemyAgentRepository(session)
    >>>     return repo.find_all()

    生命周期：
    1. 请求开始：创建 Session
    2. 执行路由：使用 Session
    3. 请求结束：关闭 Session（无论成功还是失败）

    Yields:
        Session: 数据库会话
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
