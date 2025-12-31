"""Dependency helper for retrieving the API container from app.state."""

from __future__ import annotations

from fastapi import Request

from src.interfaces.api.container import ApiContainer


def get_container(request: Request) -> ApiContainer:
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise RuntimeError("API container is not initialized (lifespan not executed).")
    return container
