from __future__ import annotations

from contextlib import contextmanager

import pytest

from src.config import settings
from src.domain.exceptions import DomainError
from src.interfaces.api.services import workflow_executor_adapter as adapter_module
from src.interfaces.api.services.workflow_executor_adapter import WorkflowExecutorAdapter


class _DummySession:
    def close(self) -> None:  # pragma: no cover - placeholder
        return None


class _FakeFacade:
    async def execute(self, *, workflow_id: str, input_data=None) -> dict:
        return {"workflow_id": workflow_id, "executor_id": "fake"}


@contextmanager
def _fake_facade_cm():
    yield _FakeFacade()


@pytest.mark.asyncio
async def test_audit_log_emitted_when_run_persistence_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "disable_run_persistence", True)

    captured: list[tuple[str, dict]] = []

    def _warning(message: str, *, extra: dict | None = None, **_kwargs) -> None:
        captured.append((message, dict(extra or {})))

    monkeypatch.setattr(adapter_module.logger, "warning", _warning)

    adapter = WorkflowExecutorAdapter(session_factory=_DummySession, executor_registry=object())
    with pytest.raises(DomainError):
        await adapter.execute("wf_1", input_data={"secret": "should_not_leak"})

    assert captured, "should emit an audit log when run persistence rollback is active"
    msg, extra = captured[0]
    assert msg == "run_persistence_rollback_active"
    assert extra.get("feature_flag") == "disable_run_persistence"
    assert extra.get("scope") == "workflow_id=wf_1"
    assert extra.get("mode") == "execute"
    assert "secret" not in str(extra), "audit log must not include input_data"


@pytest.mark.asyncio
async def test_run_persistence_enabled_requires_run_entry_factories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "disable_run_persistence", False)

    adapter = WorkflowExecutorAdapter(
        session_factory=lambda: _DummySession(), executor_registry=object()
    )

    with pytest.raises(DomainError):
        await adapter.execute("wf_1", input_data=None)
