"""Factory for constructing CoordinatorAgent outside the Interface layer."""

from __future__ import annotations

from src.domain.agents.coordinator_agent import CoordinatorAgent
from src.domain.services.event_bus import EventBus


def create_coordinator_agent(*, event_bus: EventBus) -> CoordinatorAgent:
    coordinator = CoordinatorAgent(event_bus=event_bus)
    coordinator.start_monitoring()
    return coordinator
