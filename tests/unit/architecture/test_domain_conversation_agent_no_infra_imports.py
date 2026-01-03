from __future__ import annotations

import ast
from pathlib import Path


def _assert_no_infra_or_interface_imports(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                assert not name.startswith(
                    "src.infrastructure"
                ), f"{path}: import from Infrastructure is forbidden in Domain (ConversationAgent scope): {name}"
                assert not name.startswith(
                    "src.interfaces"
                ), f"{path}: import from Interface is forbidden in Domain (ConversationAgent scope): {name}"
        if isinstance(node, ast.ImportFrom) and node.module:
            module = node.module
            assert not module.startswith(
                "src.infrastructure"
            ), f"{path}: import from Infrastructure is forbidden in Domain (ConversationAgent scope): {module}"
            assert not module.startswith(
                "src.interfaces"
            ), f"{path}: import from Interface is forbidden in Domain (ConversationAgent scope): {module}"


def test_conversation_agent_domain_files_do_not_import_infra_or_interface() -> None:
    # Scope: ConversationAgent 相关 Domain 模块（WFCONV3-030）
    root = Path(__file__).resolve().parents[3]

    files = [
        root / "src/domain/agents/conversation_agent.py",
        root / "src/domain/agents/conversation_agent_helpers.py",
        root / "src/domain/agents/conversation_agent_react_core.py",
        root / "src/domain/agents/conversation_agent_config.py",
    ]

    missing = [str(p) for p in files if not p.exists()]
    assert not missing, f"expected files missing: {missing}"

    for path in files:
        _assert_no_infra_or_interface_imports(path)
