"""ResearchPlan value object.

Minimal shape used by Application-layer events and mappers.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResearchPlan(BaseModel):
    """Structured research plan.

    This model is intentionally permissive (extra fields allowed) because
    its detailed schema is owned by the research subsystem.
    """

    model_config = ConfigDict(extra="allow")

    id: str = Field(default="", description="Research plan ID (optional)")
    goal: str = Field(default="", description="High-level research goal (optional)")
    steps: list[dict[str, Any]] = Field(default_factory=list, description="Plan steps (optional)")
