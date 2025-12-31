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


def _scan_tree(*, rule: str, root: Path, patterns: list[re.Pattern[str]]) -> list[Violation]:
    violations: list[Violation] = []
    for file in _iter_python_files(root):
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


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]

    checks: list[tuple[str, Path, list[str]]] = [
        (
            "interfaces_no_domain_agents",
            repo_root / "src" / "interfaces",
            [r"\bfrom\s+src\.domain\.agents\b", r"\bimport\s+src\.domain\.agents\b"],
        ),
        (
            "application_no_interfaces",
            repo_root / "src" / "application",
            [r"\bfrom\s+src\.interfaces\b", r"\bimport\s+src\.interfaces\b"],
        ),
        (
            "domain_no_interfaces",
            repo_root / "src" / "domain",
            [r"\bfrom\s+src\.interfaces\b", r"\bimport\s+src\.interfaces\b"],
        ),
    ]

    all_violations: list[Violation] = []
    for rule, root, pattern_strings in checks:
        if not root.exists():
            raise RuntimeError(f"Expected directory does not exist: {root}")
        patterns = [re.compile(p) for p in pattern_strings]
        all_violations.extend(_scan_tree(rule=rule, root=root, patterns=patterns))

    if all_violations:
        for v in all_violations:
            relative = v.file.relative_to(repo_root)
            print(f"[FAIL] {v.rule}: {relative}:{v.line_number}: {v.line}")
        return 1

    print("[OK] DDD boundary checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
