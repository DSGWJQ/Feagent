"""TransactionManager Port - 事务控制抽象

目标：
- UseCase 依赖抽象事务控制，避免直接耦合数据库实现（DIP）
- 基础设施层提供 SQLAlchemy 等具体实现
"""

from __future__ import annotations

from typing import Protocol


class TransactionManager(Protocol):
    def commit(self) -> None: ...

    def rollback(self) -> None: ...
