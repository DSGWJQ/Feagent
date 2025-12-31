"""Database schema bootstrap helpers.

This project primarily relies on Alembic migrations for production databases.
For SQLite-based development and some local workflows, we provide a best-effort
helper to ensure tables exist at startup.
"""

from __future__ import annotations

from src.infrastructure.database.base import Base
from src.infrastructure.database.engine import sync_engine


def ensure_sqlite_schema() -> None:
    """Best-effort schema creation for SQLite.

    Notes:
    - Only runs for SQLite URLs.
    - For other databases, migrations (Alembic) should be used.
    """

    # Ensure ORM models are imported so they are registered on Base.metadata
    from src.infrastructure.database import models as _models  # noqa: F401

    url = str(sync_engine.url)
    if url.startswith("sqlite"):
        Base.metadata.create_all(bind=sync_engine)
