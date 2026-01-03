"""SQLAlchemyTransactionManager - SQLAlchemy 事务控制适配器"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.application.ports.transaction_manager import TransactionManager


class SQLAlchemyTransactionManager(TransactionManager):
    def __init__(self, session: Session) -> None:
        self._session = session

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()


__all__ = ["SQLAlchemyTransactionManager"]
