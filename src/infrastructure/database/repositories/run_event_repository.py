"""SQLAlchemy RunEvent Repository 实现

职责：
- RunEvent 领域实体 <-> RunEventModel ORM 模型转换
- append：追加事件并返回带自增 id 的实体
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.domain.entities.run_event import RunEvent
from src.infrastructure.database.models import RunEventModel


class SQLAlchemyRunEventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _to_entity(self, model: RunEventModel) -> RunEvent:
        created_at = (
            model.created_at.replace(tzinfo=UTC)
            if model.created_at.tzinfo is None
            else model.created_at
        )
        return RunEvent(
            id=model.id,
            run_id=model.run_id,
            type=model.type,
            channel=model.channel,
            payload=model.payload or {},
            created_at=created_at,
            sequence=model.sequence,
        )

    def _to_model(self, entity: RunEvent) -> RunEventModel:
        created_at: datetime = entity.created_at
        created_at_naive = created_at.replace(tzinfo=None)
        return RunEventModel(
            run_id=entity.run_id,
            type=entity.type,
            channel=entity.channel,
            payload=entity.payload or {},
            created_at=created_at_naive,
            sequence=entity.sequence,
        )

    def append(self, event: RunEvent) -> RunEvent:
        model = self._to_model(event)
        self.session.add(model)
        self.session.flush()
        return self._to_entity(model)


__all__ = ["SQLAlchemyRunEventRepository"]
