"""Database schema bootstrap helpers.

This project primarily relies on Alembic migrations for production databases.
For SQLite-based development and some local workflows, we provide a best-effort
helper to ensure tables exist at startup.
"""

from __future__ import annotations

from sqlalchemy import text

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
    if not url.startswith("sqlite"):
        return

    Base.metadata.create_all(bind=sync_engine)

    # Best-effort additive migrations for SQLite (create_all won't add columns).
    # Keep this minimal and fail-closed: if anything goes wrong, surface the error.
    with sync_engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(runs)")).fetchall()
        existing = {row[1] for row in rows}

        if "agent_id" not in existing:
            conn.execute(text("ALTER TABLE runs ADD COLUMN agent_id VARCHAR(36)"))
        if "started_at" not in existing:
            conn.execute(text("ALTER TABLE runs ADD COLUMN started_at DATETIME"))
        if "error" not in existing:
            conn.execute(text("ALTER TABLE runs ADD COLUMN error TEXT"))
