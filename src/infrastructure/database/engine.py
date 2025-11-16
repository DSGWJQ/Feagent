"""数据库引擎配置

为什么需要单独的 engine 模块？
1. 分离关注点：引擎配置独立于模型定义
2. 避免循环导入：Base 和 engine 分开定义
3. 便于测试：可以轻松创建测试引擎

设计说明：
- 使用 create_async_engine 创建异步引擎
- 从配置文件读取 database_url
- 配置连接池参数（pool_size、max_overflow）
- 配置 echo 参数（开发环境打印 SQL）
"""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

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


# 全局引擎实例（应用启动时创建）
engine = get_engine()
