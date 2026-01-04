"""Compatibility wrapper for CoordinatorPolicyChain.

WFCORE-080:
- Keep `src.application.services.*` import paths stable for Application/Interface users.
- Actual implementation lives in `src.domain.services.coordinator_policy_chain` so Domain does
  not import Application (DDD boundary).
"""

from __future__ import annotations

from src.domain.services.coordinator_policy_chain import (  # noqa: F401
    CoordinatorPolicyChain,
    CoordinatorPort,
    CoordinatorRejectedError,
)

__all__ = [
    "CoordinatorPolicyChain",
    "CoordinatorPort",
    "CoordinatorRejectedError",
]
