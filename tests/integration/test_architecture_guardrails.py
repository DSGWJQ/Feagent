"""Architecture guardrails (anti-regression).

These tests intentionally enforce the project's "single-path / single-SoT" decisions.
They are cheap string scans, but they prevent accidental reintroduction of removed
runtime chains and dual-track semantics.
"""

from __future__ import annotations

from pathlib import Path


def _scan_text_files(*, root: Path, pattern: str) -> list[str]:
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if pattern in text:
            offenders.append(str(path))
    return offenders


def test_no_websocket_routes_in_interfaces() -> None:
    """SSE-only: runtime WebSocket routes must not exist in the API interface layer."""
    offenders = _scan_text_files(root=Path("src/interfaces"), pattern="@router.websocket")
    assert not offenders, f"WebSocket routes reintroduced in Interface layer: {offenders}"


def test_no_event_callback_dual_track_in_src() -> None:
    """EventBus single-track: callback injection must not return."""
    offenders = _scan_text_files(root=Path("src"), pattern="event_callback")
    assert not offenders, f"event_callback reintroduced (dual-track risk): {offenders}"


def test_no_langgraph_workflow_executor_reintroduction() -> None:
    """Workflow execution SoT: LangGraph workflow executor path must not return."""
    offenders = _scan_text_files(root=Path("src"), pattern="langgraph_workflow_executor")
    assert not offenders, f"LangGraph workflow executor path reintroduced: {offenders}"
