"""RAG workflow helper routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.interfaces.api.dependencies.rag import (
    check_rag_health,
    get_rag_config,
    get_rag_service,
    is_rag_enabled,
)

router = APIRouter(prefix="/workflows/rag", tags=["Workflows RAG"])


@router.get("/health")
async def rag_health() -> dict:
    """Return the latest RAG subsystem health status."""

    return await check_rag_health()


@router.get("/config")
async def rag_config() -> dict:
    """Return the current RAG configuration."""

    return get_rag_config()


@router.get("/enabled")
async def rag_enabled() -> dict[str, bool]:
    """Return whether RAG features are enabled."""

    return {"enabled": is_rag_enabled()}


@router.get("/service/ping")
async def rag_service_ping(rag_service=Depends(get_rag_service)) -> dict[str, str]:
    """Simple endpoint to verify that the RAG service dependency resolves."""

    _ = rag_service  # dependency evaluation is enough
    return {"status": "ready"}
