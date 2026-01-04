from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QueryContext:
    """QueryContext - shared value object for RAG retrieval (DDD-safe).

    Note: Domain code may construct this without importing Application services.
    """

    query: str
    workflow_id: str | None = None
    max_context_length: int = 4000
    top_k: int = 5
    filters: dict[str, str] | None = None
