"""Deterministic execution mode helpers."""

from __future__ import annotations

import os

from src.config import settings


def is_deterministic_mode() -> bool:
    """Return True when running in deterministic E2E mode."""
    env_value = os.getenv("E2E_TEST_MODE", "").strip().lower()
    if env_value:
        return env_value == "deterministic"
    return settings.e2e_test_mode == "deterministic"
