"""WFCORE-100: Offline invariants regression manifest.

This file is a lightweight guardrail to keep the key invariant tests discoverable.
It does not replace behavior tests; it prevents accidental removal/renaming of the
invariant coverage entrypoints and DDD guardrails.
"""

from __future__ import annotations

from pathlib import Path


def test_invariants_manifest_files_exist() -> None:
    required_paths = [
        # Invariant 1/2/3/4: API contract guardrails (create/modify/execute/chat-stream).
        "tests/integration/api/workflows/test_route_guardrails.py",
        # Invariant 1: chat-create stream creates workflow and returns workflow_id.
        "tests/integration/api/workflow_chat/test_chat_create_stream_api.py",
        # Invariant 3/7: REST execute/stream and WorkflowAgent execution share one entry.
        "tests/integration/api/workflows/test_workflow_agent_execution_kernel_unification.py",
        # Invariant 7: Run creation/gate/replay coverage.
        "tests/integration/api/workflows/test_run_event_persistence.py",
        # Invariant 5: Coordinator intercept coverage.
        "tests/integration/api/workflows/test_workflows.py",
        # Invariant 6: Strict ReAct tool_call execution + observation.
        "tests/unit/domain/agents/test_conversation_agent_react_core.py",
        # Invariant 9: Plan mutual validation feedback.
        "tests/unit/domain/agents/test_workflow_agent_plan_validation_feedback.py",
        # Invariant 10: DDD guardrails config.
        ".import-linter.toml",
    ]

    for rel in required_paths:
        assert Path(rel).exists(), f"missing invariant coverage file: {rel}"


def test_interfaces_do_not_import_domain_agents_directly() -> None:
    """Invariant 10 (DDD): Interface layer must not directly import Domain agents."""
    interfaces_root = Path("src/interfaces")
    assert interfaces_root.exists()

    forbidden_snippets = (
        "from src.domain.agents",
        "import src.domain.agents",
        "src.domain.agents.",
    )

    offenders: list[str] = []
    for path in interfaces_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(snippet in text for snippet in forbidden_snippets):
            offenders.append(str(path))

    assert not offenders, f"Interface directly imports Domain agents: {offenders}"
