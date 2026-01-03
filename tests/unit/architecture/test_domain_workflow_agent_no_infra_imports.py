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
                ), f"{path}: import from Infrastructure is forbidden in Domain (WorkflowAgent scope): {name}"
                assert not name.startswith(
                    "src.interfaces"
                ), f"{path}: import from Interface is forbidden in Domain (WorkflowAgent scope): {name}"
        if isinstance(node, ast.ImportFrom) and node.module:
            module = node.module
            assert not module.startswith(
                "src.infrastructure"
            ), f"{path}: import from Infrastructure is forbidden in Domain (WorkflowAgent scope): {module}"
            assert not module.startswith(
                "src.interfaces"
            ), f"{path}: import from Interface is forbidden in Domain (WorkflowAgent scope): {module}"


def test_workflow_agent_domain_files_do_not_import_infra_or_interface() -> None:
    # Scope: WorkflowAgent 相关 Domain 模块（WFCONV3-040）
    root = Path(__file__).resolve().parents[3]

    files = [
        root / "src/domain/agents/workflow_agent.py",
        root / "src/domain/agents/container_executor.py",
    ]

    missing = [str(p) for p in files if not p.exists()]
    assert not missing, f"expected files missing: {missing}"

    for path in files:
        _assert_no_infra_or_interface_imports(path)
