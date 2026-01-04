from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Violation:
    rule: str
    file: Path
    line_number: int
    line: str


def _iter_python_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def _scan_tree(
    *,
    rule: str,
    root: Path,
    patterns: list[re.Pattern[str]],
    allowed_files: set[Path] | None = None,
) -> list[Violation]:
    violations: list[Violation] = []
    for file in _iter_python_files(root):
        if allowed_files and file in allowed_files:
            continue
        try:
            lines = file.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise RuntimeError(f"Failed to read {file}: {exc}") from exc

        for line_number, line in enumerate(lines, start=1):
            for pattern in patterns:
                if pattern.search(line):
                    violations.append(
                        Violation(
                            rule=rule,
                            file=file,
                            line_number=line_number,
                            line=line.rstrip(),
                        )
                    )
                    break
    return violations


def _resolve_allowlist(*, repo_root: Path, relative_paths: Iterable[str]) -> set[Path]:
    allowed_files: set[Path] = set()
    for relative_path in relative_paths:
        file = repo_root / relative_path
        if not file.exists():
            raise RuntimeError(f"Allowlist file does not exist: {relative_path}")
        allowed_files.add(file)
    return allowed_files


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]

    domain_yaml_pathlib_allowlist = _resolve_allowlist(
        repo_root=repo_root,
        relative_paths=[
            "src/domain/agents/node_definition.py",
            "src/domain/services/configurable_rule_engine.py",
            "src/domain/services/logging_metrics.py",
            "src/domain/services/node_code_generator.py",
            "src/domain/services/node_yaml_validator.py",
            "src/domain/services/parent_node_schema.py",
            "src/domain/services/prompt_template_system.py",
            "src/domain/services/rule_engine.py",
            "src/domain/services/sandbox_executor.py",
            "src/domain/services/scenario_prompt_system.py",
            "src/domain/services/self_describing_node.py",
            "src/domain/services/safety_guard/core.py",
            "src/domain/services/tool_config_loader.py",
            "src/domain/services/tool_engine.py",
            "src/domain/services/unified_definition.py",
            "src/domain/services/workflow_dependency_graph.py",
        ],
    )

    checks: list[tuple[str, Path, list[str], set[Path] | None]] = [
        (
            "interfaces_no_domain_agents",
            repo_root / "src" / "interfaces",
            [r"\bfrom\s+src\.domain\.agents\b", r"\bimport\s+src\.domain\.agents\b"],
            None,
        ),
        (
            "application_no_interfaces",
            repo_root / "src" / "application",
            [r"\bfrom\s+src\.interfaces\b", r"\bimport\s+src\.interfaces\b"],
            None,
        ),
        (
            "domain_no_interfaces",
            repo_root / "src" / "domain",
            [r"\bfrom\s+src\.interfaces\b", r"\bimport\s+src\.interfaces\b"],
            None,
        ),
        (
            "domain_no_infrastructure",
            repo_root / "src" / "domain",
            [r"\bfrom\s+src\.infrastructure\b", r"\bimport\s+src\.infrastructure\b"],
            None,
        ),
        (
            "domain_yaml_pathlib_allowlist",
            repo_root / "src" / "domain",
            [
                r"^\s*import\s+yaml\b",
                r"^\s*from\s+yaml\b",
                r"^\s*from\s+pathlib\s+import\s+Path\b",
                r"^\s*import\s+pathlib\b",
            ],
            domain_yaml_pathlib_allowlist,
        ),
    ]

    count_limited_checks: list[tuple[str, Path, str, int]] = [
        (
            "workflow_create_base_entry_unique",
            repo_root / "src" / "interfaces",
            r"\bWorkflow\.create_base\s*\(",
            1,
        ),
        (
            "internal_workflow_create_guard_max_2",
            repo_root / "src" / "interfaces",
            r"(?<!def )_require_internal_workflow_create_access\s*\(",
            2,
        ),
    ]

    all_violations: list[Violation] = []
    count_limit_summaries: dict[str, str] = {}

    for rule, root, pattern_string, max_count in count_limited_checks:
        if not root.exists():
            raise RuntimeError(f"Expected directory does not exist: {root}")
        matches = _scan_tree(
            rule=rule,
            root=root,
            patterns=[re.compile(pattern_string)],
        )
        if len(matches) > max_count:
            all_violations.extend(matches)
            count_limit_summaries[rule] = (
                f"Expected <= {max_count} matches, found {len(matches)}. "
                "If this is intentional, update the limit and document the new entrypoint."
            )

    for rule, root, pattern_strings, allowed_files in checks:
        if not root.exists():
            raise RuntimeError(f"Expected directory does not exist: {root}")
        patterns = [re.compile(p) for p in pattern_strings]
        all_violations.extend(
            _scan_tree(rule=rule, root=root, patterns=patterns, allowed_files=allowed_files)
        )

    if all_violations:
        for v in all_violations:
            relative = v.file.relative_to(repo_root)
            print(f"[FAIL] {v.rule}: {relative}:{v.line_number}: {v.line}")
        for rule, summary in count_limit_summaries.items():
            print(f"[FAIL] {rule}: {summary}")
        return 1

    print("[OK] DDD boundary checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
