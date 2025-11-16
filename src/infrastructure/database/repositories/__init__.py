"""Repository 实现 - 数据访问层

为什么需要 Repository？
1. 隔离数据访问逻辑：领域层不关心数据如何存储
2. 实现 Port 接口：基础设施层实现领域层定义的接口
3. 转换对象：ORM 模型 ⇄ 领域实体

设计原则：
- 实现领域层定义的 Port 接口
- 使用 Assembler 模式进行对象转换
- 处理数据库异常并转换为领域异常
- 保持事务一致性
"""

from src.infrastructure.database.repositories.agent_repository import (
    SQLAlchemyAgentRepository,
)
from src.infrastructure.database.repositories.run_repository import (
    SQLAlchemyRunRepository,
)

__all__ = ["SQLAlchemyAgentRepository", "SQLAlchemyRunRepository"]
