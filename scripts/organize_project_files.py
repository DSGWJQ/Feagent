from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import os
import re
import shutil
import sys
from collections.abc import Iterable
from pathlib import Path


@dataclasses.dataclass(frozen=True)
class Action:
    kind: str  # mkdir | move | copy | rmdir
    src: Path | None = None
    dst: Path | None = None
    reason: str = ""
    risk: bool = False


@dataclasses.dataclass(frozen=True)
class Rules:
    protected_dirs: set[str]
    high_dirs: set[str]
    merge_dirs: dict[str, Path]  # source dir name (root) -> destination dir (root-relative)
    htmlcov_dst: Path
    test_reports_dir: Path
    coverage_dir: Path
    docs_integration_dir: Path
    docs_plans_dir: Path
    docs_testing_dir: Path
    docs_analysis_dir: Path
    docs_summaries_dir: Path
    docs_references_dir: Path
    data_databases_dir: Path
    data_test_databases_dir: Path
    data_test_data_dir: Path
    data_metrics_dir: Path
    logs_test_coverage_dir: Path
    logs_agent_traces_dir: Path
    tmp_empty_dir: Path
    backup_dir: str
    tmp_dir: str
    stale_dir: Path
    root_keep_files: set[str]
    root_keep_prefixes: tuple[str, ...]
    type_map: dict[str, str]  # extension -> top-level dir


def _now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _ts() -> str:
    return dt.datetime.now().strftime("%H:%M:%S")


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _top_dir(root: Path, path: Path) -> str | None:
    rel = path.relative_to(root)
    parts = rel.parts
    if not parts:
        return None
    return parts[0]


def _safe_rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)


def _ensure_unique_path(dst: Path) -> Path:
    if not dst.exists():
        return dst
    stem = dst.stem
    suffix = dst.suffix
    parent = dst.parent
    for i in range(1, 10_000):
        candidate = parent / f"{stem}__conflict{i}{suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"无法为目标路径生成不冲突名称：{dst}")


def _looks_like_log_text(path: Path) -> bool:
    try:
        if path.stat().st_size > 1_000_000:
            return False
        sample = path.read_text(encoding="utf-8", errors="ignore")[:4096]
    except Exception:
        return False
    patterns = [
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{2}:\d{2}:\d{2}\b",
        r"\[\d{2}:\d{2}:\d{2}\]",
    ]
    return any(re.search(p, sample) for p in patterns)


def _is_root_keep(rules: Rules, root: Path, path: Path) -> bool:
    rel = path.relative_to(root)
    if len(rel.parts) != 1:
        return False
    name = rel.name
    if name in rules.root_keep_files:
        return True
    if name.startswith("."):
        return True
    return any(name.startswith(prefix) for prefix in rules.root_keep_prefixes)


def _is_protected(rules: Rules, root: Path, path: Path) -> bool:
    top = _top_dir(root, path)
    return top is not None and top in rules.protected_dirs


def _is_high_importance(rules: Rules, root: Path, path: Path) -> bool:
    top = _top_dir(root, path)
    return top is not None and top in rules.high_dirs


def _iter_tree(root: Path, rules: Rules) -> Iterable[Path]:
    for current_dir, dirnames, filenames in os.walk(root):
        current = Path(current_dir)
        if current == root:
            pass
        else:
            top = _top_dir(root, current)
            if top in rules.protected_dirs:
                dirnames[:] = []
                continue

        dirnames[:] = [d for d in dirnames if d not in rules.protected_dirs and d != "__pycache__"]
        for name in filenames:
            yield current / name


def _classify_root_file(
    root: Path, rules: Rules, path: Path, mode: str
) -> tuple[Path | None, str] | None:
    if mode == "safe":
        return None
    if not path.is_file():
        return None
    if _is_root_keep(rules, root, path):
        return None

    name_lower = path.name.lower()

    # 工具/工程根目录约定：保持原位
    if path.name == "pyrightconfig.json":
        return None

    # 根目录“散落文件”仅做有限归位：以你给的清单为准
    if name_lower == ".coverage":
        return (root / rules.stale_dir / path.name, "临时覆盖率")
    if name_lower in {"coverage_output.txt", "full_coverage.txt", "test_coverage_output.txt"}:
        return (root / rules.logs_test_coverage_dir / path.name, "覆盖率日志")
    if name_lower == "coverage.json":
        return (root / rules.data_metrics_dir / path.name, "覆盖率数据")
    if name_lower == "agent_data.db":
        return (root / rules.data_databases_dir / path.name, "数据库文件")
    if name_lower == "test_integration.db":
        return (root / rules.data_test_databases_dir / path.name, "测试数据库")
    if name_lower == "test_create_agent.json":
        return (root / rules.data_test_data_dir / path.name, "测试数据")
    if name_lower == "leaf":
        return (root / rules.logs_agent_traces_dir / "Leaf.jsonl", "运行追踪")
    if name_lower == "nul":
        # Windows 保留名：落盘时改名避免后续无法访问
        return (root / rules.tmp_empty_dir / "nul.zero", "空文件")

    # 其它根目录 md/txt 由“固定映射表”处理（见 build_plan）

    return None


def _stale_candidate(rules: Rules, root: Path, path: Path, stale_days: int) -> bool:
    if _is_protected(rules, root, path):
        return False
    if path.is_dir():
        return False

    # 仅对 tmp/ 内、或根目录明显临时文件做“过时”判定，避免误伤高重要度目录
    rel = path.relative_to(root)
    in_tmp = rel.parts and rel.parts[0] == rules.tmp_dir
    in_root = len(rel.parts) == 1

    name_lower = path.name.lower()
    if in_root and not re.search(r"\.(tmp|cache|swp)$", name_lower):
        return False

    if not (in_tmp or in_root):
        return False

    if _is_under(path, root / rules.stale_dir):
        return False

    try:
        st = path.stat()
    except Exception:
        return False

    now = dt.datetime.now().timestamp()
    mtime_days = (now - st.st_mtime) / 86400
    atime_days = (now - st.st_atime) / 86400

    name_hit = any(token in name_lower for token in ("tmp", "temp", "~$", "cache_", "old_"))
    zero_size = st.st_size == 0 and path.name not in {".gitkeep"}
    time_hit = (mtime_days > stale_days) and (atime_days > 30)

    return time_hit or name_hit or zero_size


def _plan_merge_dir(root: Path, src_dirname: str, dst_dir: Path) -> list[Action]:
    src_dir = root / src_dirname
    if not src_dir.exists() or not src_dir.is_dir():
        return []

    actions: list[Action] = []
    for item in src_dir.rglob("*"):
        if item.is_dir():
            continue
        rel = item.relative_to(src_dir)
        dst = root / dst_dir / rel
        actions.append(Action(kind="move", src=item, dst=dst, reason="目录合并"))

    return actions


def _plan_htmlcov(root: Path, rules: Rules) -> list[Action]:
    src_dir = root / "htmlcov"
    if not src_dir.exists() or not src_dir.is_dir():
        return []
    actions: list[Action] = []
    for item in src_dir.rglob("*"):
        if item.is_dir():
            continue
        rel = item.relative_to(src_dir)
        dst = root / rules.htmlcov_dst / rel
        actions.append(Action(kind="move", src=item, dst=dst, reason="覆盖率报告"))
    return actions


def _plan_type_mapping(root: Path, rules: Rules, mode: str) -> list[Action]:
    if mode == "safe":
        return []

    actions: list[Action] = []
    for path in _iter_tree(root, rules):
        if _is_protected(rules, root, path):
            continue
        if path.is_dir():
            continue
        if _is_root_keep(rules, root, path):
            continue
        if _top_dir(root, path) in rules.merge_dirs:
            continue
        if _top_dir(root, path) == "htmlcov":
            continue

        ext = path.suffix.lower()
        target_top = None
        if ext == ".txt" and mode == "aggressive" and _looks_like_log_text(path):
            # 极少数情况下，.txt 可能是结构化日志；仅在 aggressive 模式启用
            target_top = "logs"
        elif ext:
            target_top = rules.type_map.get(ext)
        if not target_top:
            continue

        # 保守：避免把 .py 随意挪出工程结构
        if ext == ".py" and mode != "aggressive":
            continue

        # 避免把 docs 里的文档再挪来挪去
        if _top_dir(root, path) in {
            "docs",
            "scripts",
            "tests",
            "config",
            "data",
            "logs",
            "uploads",
            "backup",
        }:
            continue

        rel = path.relative_to(root)
        dst = root / target_top / rel.name
        risk = target_top in rules.high_dirs
        actions.append(Action(kind="move", src=path, dst=dst, reason="类型映射", risk=risk))

    return actions


def _apply_actions(
    root: Path,
    rules: Rules,
    actions: list[Action],
    *,
    dry_run: bool,
    prune_empty: bool,
    log_file: Path | None,
    make_rollback: bool,
    verbose: bool,
) -> dict[str, int]:
    counts = {"move": 0, "mkdir": 0, "copy": 0, "rmdir": 0, "skip": 0, "conflict_rename": 0}
    moved_pairs: list[tuple[Path, Path]] = []

    log_fp = None
    if log_file is not None:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_fp = log_file.open("a", encoding="utf-8")
        except Exception:
            log_fp = None

    def log(line: str, *, to_console: bool = False) -> None:
        if to_console:
            print(line)
        if log_fp is not None:
            try:
                log_fp.write(line + "\n")
                log_fp.flush()
            except Exception:
                pass

    def note_action(action: Action, src: Path, dst: Path) -> None:
        warn = "⚠️ " if action.risk else ""
        line = f"[{_ts()}] {warn}{_safe_rel(root, src)} → {_safe_rel(root, dst)} ({action.reason})"
        # 控制台默认精简：仅输出风险项/冲突项；完整明细写入日志文件
        log(line, to_console=verbose or action.risk)

    def maybe_backup_config(src: Path, dst: Path) -> None:
        if dry_run:
            return
        # 触及 config 的移动：无论源在 root 还是 config/，都在 config/backup/ 留一份
        if _top_dir(root, src) != "config" and _top_dir(root, dst) != "config":
            return
        try:
            if _top_dir(root, src) == "config":
                rel_in_config = src.relative_to(root / "config")
            else:
                rel_in_config = Path("root") / src.name
        except Exception:
            rel_in_config = Path("root") / src.name
        backup_root = root / "config" / "backup"
        stamp = _now_stamp()
        backup_path = backup_root / rel_in_config
        backup_path = backup_path.with_name(f"{backup_path.name}.{stamp}.bak")
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(backup_path))

    for action in actions:
        if action.kind == "move":
            assert action.src is not None and action.dst is not None
            src = action.src
            dst = action.dst

            src_str = str(src)
            dst_str = str(dst)
            # Windows 保留文件名（如 nul）需要 \\?\ 前缀才能访问
            if os.name == "nt" and src.name.lower() in {"nul"}:
                src_str = f"\\\\?\\{str(src.resolve())}"

            if not os.path.exists(src_str):
                counts["skip"] += 1
                continue

            if action.risk and action.dst is not None:
                maybe_backup_config(src, action.dst)

            dst.parent.mkdir(parents=True, exist_ok=True) if not dry_run else None
            resolved = dst
            if dst.exists():
                resolved = _ensure_unique_path(dst)
                counts["conflict_rename"] += 1
                log(
                    f"[{_ts()}] ⚠️ 目标冲突：{_safe_rel(root, dst)} → {_safe_rel(root, resolved)} (自动重命名)",
                    to_console=True,
                )
                dst_str = str(resolved)

            note_action(action, src, resolved)
            if not dry_run:
                shutil.move(src_str, dst_str)
            counts["move"] += 1
            moved_pairs.append((src, resolved))

        elif action.kind == "mkdir":
            assert action.dst is not None
            if action.dst.exists():
                counts["skip"] += 1
                continue
            log(f"[{_ts()}] {_safe_rel(root, action.dst)} (创建目录)", to_console=verbose)
            if not dry_run:
                action.dst.mkdir(parents=True, exist_ok=True)
            counts["mkdir"] += 1

        elif action.kind == "copy":
            assert action.src is not None and action.dst is not None
            if not action.src.exists():
                counts["skip"] += 1
                continue
            action.dst.parent.mkdir(parents=True, exist_ok=True) if not dry_run else None
            log(
                f"[{_ts()}] {_safe_rel(root, action.src)} → {_safe_rel(root, action.dst)} ({action.reason})",
                to_console=verbose,
            )
            if not dry_run:
                shutil.copy2(str(action.src), str(action.dst))
            counts["copy"] += 1

        elif action.kind == "rmdir":
            assert action.src is not None
            if not action.src.exists():
                counts["skip"] += 1
                continue
            log(f"[{_ts()}] {_safe_rel(root, action.src)} (移除空目录)", to_console=verbose)
            if not dry_run:
                try:
                    action.src.rmdir()
                except OSError:
                    counts["skip"] += 1
                    continue
            counts["rmdir"] += 1

    if log_fp is not None:
        try:
            log_fp.close()
        except Exception:
            pass

    if make_rollback:
        _write_rollback_scripts(root, moved_pairs, dry_run=dry_run)

    if prune_empty and not dry_run:
        _prune_empty_dirs(root, rules, log=print)

    return counts


def _write_rollback_scripts(
    root: Path, moved_pairs: list[tuple[Path, Path]], *, dry_run: bool
) -> None:
    stamp = _now_stamp()
    sh_path = root / "logs" / f"undo_organization_{stamp}.sh"
    ps_path = root / "logs" / f"undo_organization_{stamp}.ps1"

    # 反向执行：从 dst 移回 src。按逆序更安全。
    lines_sh = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    lines_ps = ["Set-StrictMode -Version Latest", "$ErrorActionPreference = 'Stop'", ""]
    for src, dst in reversed(moved_pairs):
        lines_sh.append(f"mkdir -p {shlex_quote(str(src.parent))}")
        lines_sh.append(f"mv {shlex_quote(str(dst))} {shlex_quote(str(src))}")
        lines_ps.append(
            f"New-Item -ItemType Directory -Force -Path {ps_quote(str(src.parent))} | Out-Null"
        )
        lines_ps.append(
            f"Move-Item -Force -Path {ps_quote(str(dst))} -Destination {ps_quote(str(src))}"
        )

    if dry_run:
        return

    sh_path.parent.mkdir(parents=True, exist_ok=True)
    sh_path.write_text("\n".join(lines_sh) + "\n", encoding="utf-8")
    ps_path.write_text("\n".join(lines_ps) + "\n", encoding="utf-8")


def shlex_quote(s: str) -> str:
    if not s:
        return "''"
    if re.fullmatch(r"[A-Za-z0-9_./:-]+", s):
        return s
    return "'" + s.replace("'", "'\"'\"'") + "'"


def ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _prune_empty_dirs(root: Path, rules: Rules, *, log) -> None:
    protected = {root / d for d in rules.protected_dirs}
    protected |= {root / d for d in rules.high_dirs}
    # 注意：merge 源目录与 htmlcov/ 若已变空，允许在 prune-empty 中清理
    protected |= {root / rules.tmp_dir, root / rules.backup_dir}
    protected |= {root}

    for dirpath, _dirnames, _ in os.walk(root, topdown=False):
        p = Path(dirpath)
        if p in protected:
            continue
        if _is_protected(rules, root, p):
            continue
        try:
            if not any(p.iterdir()):
                log(f"[{_ts()}] {_safe_rel(root, p)} (移除空目录)")
                p.rmdir()
        except Exception:
            continue


def _build_rules() -> Rules:
    protected = {
        "src",
        "web",
        "definitions",
        "typings",
        ".git",
        ".venv",
        "venv",
        "node_modules",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".pre-commit-cache",
        ".obsidian",
        ".vscode",
    }
    high = {"config", "data", "logs", "uploads", "scripts", "tests", "backup"}
    merge = {
        "tools": Path("scripts") / "tools",
        "notebooks": Path("docs") / "notebooks",
        "reports": Path("docs") / "reports",
    }
    htmlcov_dst = Path("docs") / "test_reports" / "coverage"
    test_reports_dir = Path("docs") / "test_reports"
    coverage_dir = Path("docs") / "test_reports" / "coverage"
    docs_integration_dir = Path("docs") / "integration"
    docs_plans_dir = Path("docs") / "plans"
    docs_testing_dir = Path("docs") / "testing"
    docs_analysis_dir = Path("docs") / "analysis"
    docs_summaries_dir = Path("docs") / "summaries"
    docs_references_dir = Path("docs") / "references"
    data_databases_dir = Path("data") / "databases"
    data_test_databases_dir = Path("data") / "test_databases"
    data_test_data_dir = Path("data") / "test_data"
    data_metrics_dir = Path("data") / "metrics"
    logs_test_coverage_dir = Path("logs") / "test_coverage"
    logs_agent_traces_dir = Path("logs") / "agent_traces"
    tmp_empty_dir = Path("tmp") / "_empty"
    root_keep = {
        "pyproject.toml",
        "README.md",
        "LICENSE",
        ".gitignore",
        ".env",
        ".env.example",
        "alembic.ini",
        "pyrightconfig.json",
        "CLAUDE.md",
    }
    root_keep_prefixes: tuple[str, ...] = ()

    type_map = {}
    for ext in (".yml", ".yaml", ".json", ".ini", ".toml", ".env", ".cfg", ".conf", ".properties"):
        type_map[ext] = "config"
    for ext in (".sh", ".bat", ".ps1", ".py"):
        type_map[ext] = "scripts"
    for ext in (".csv", ".jsonl", ".parquet", ".db", ".sqlite", ".xlsx", ".h5", ".feather"):
        type_map[ext] = "data"
    for ext in (".md", ".pdf", ".docx", ".pptx", ".ipynb", ".html", ".rst", ".tex"):
        type_map[ext] = "docs"
    for ext in (".log",):
        type_map[ext] = "logs"

    return Rules(
        protected_dirs=protected,
        high_dirs=high,
        merge_dirs=merge,
        htmlcov_dst=htmlcov_dst,
        test_reports_dir=test_reports_dir,
        coverage_dir=coverage_dir,
        docs_integration_dir=docs_integration_dir,
        docs_plans_dir=docs_plans_dir,
        docs_testing_dir=docs_testing_dir,
        docs_analysis_dir=docs_analysis_dir,
        docs_summaries_dir=docs_summaries_dir,
        docs_references_dir=docs_references_dir,
        data_databases_dir=data_databases_dir,
        data_test_databases_dir=data_test_databases_dir,
        data_test_data_dir=data_test_data_dir,
        data_metrics_dir=data_metrics_dir,
        logs_test_coverage_dir=logs_test_coverage_dir,
        logs_agent_traces_dir=logs_agent_traces_dir,
        tmp_empty_dir=tmp_empty_dir,
        backup_dir="backup",
        tmp_dir="tmp",
        stale_dir=Path("tmp") / "_stale",
        root_keep_files=root_keep,
        root_keep_prefixes=root_keep_prefixes,
        type_map=type_map,
    )


def _summarize(
    root: Path,
    rules: Rules,
    actions: list[Action],
    counts: dict[str, int] | None,
    *,
    dry_run: bool,
    log_file: Path | None,
) -> None:
    merge_items = []
    for src, dst in rules.merge_dirs.items():
        if (root / src).exists():
            merge_items.append((src, str(dst)))
    if (root / "htmlcov").exists():
        merge_items.append(("htmlcov", str(rules.htmlcov_dst)))

    print()
    title = "文件整理预览" if dry_run else "文件整理完成"
    print(f"📁 {title} | 项目：{root.name}")
    print("├── 🧩 结构优化")
    if merge_items:
        for src, dst in merge_items:
            print(f"│ ├── {src}/ → {dst}/")
    else:
        print("│ └── （无）")

    total_actions = len([a for a in actions if a.kind == "move"])
    print("├── 📊 统计摘要")
    print(f"│ ├─ 计划变更：{total_actions} 项")
    if counts:
        print(
            "│ ├─ 执行计数："
            f"move={counts['move']} mkdir={counts['mkdir']} copy={counts['copy']} "
            f"conflict_rename={counts['conflict_rename']} skip={counts['skip']}"
        )
    print(f"│ └─ 跳过保护：{', '.join(sorted({'src','web','definitions','typings'}))}")

    important = [a for a in actions if a.risk]
    if important:
        print("├── ⚠️ 重要提示")
        print(f"│ └─ 高重要度相关操作：{len(important)} 项（建议先 dry-run 检查）")

    if log_file is not None:
        print(f"└── 🧾 详细日志：{_safe_rel(root, log_file)}")
    else:
        print("└── 🧾 详细日志：未写入文件（仅控制台）")


def build_plan(root: Path, rules: Rules, *, mode: str, stale_days: int) -> list[Action]:
    actions: list[Action] = []

    # 目录合并（保持结构）：tools→scripts/tools, notebooks/reports→docs/*
    for src, dst in rules.merge_dirs.items():
        actions.extend(_plan_merge_dir(root, src, dst))

    # htmlcov 特殊处理：迁移到 docs/test_reports/coverage/
    actions.extend(_plan_htmlcov(root, rules))

    def add_fixed_move(src: Path, dst: Path, reason: str) -> None:
        if not src.exists():
            return
        actions.append(Action(kind="move", src=src, dst=dst, reason=reason))

    def add_fixed_move_from_candidates(
        candidates: list[Path],
        dst: Path,
        reason: str,
    ) -> None:
        for c in candidates:
            if c.exists():
                actions.append(Action(kind="move", src=c, dst=dst, reason=reason))
                return

    # 目录结构（docs/*、data/*、logs/*、tmp/*）按移动目标自动创建
    # 1) 根目录散落文件（按清单归位）
    # 根目录散落文件：markdown/json/txt 等归位
    for item in root.iterdir():
        if not item.is_file():
            continue
        classified = _classify_root_file(root, rules, item, mode)
        if not classified:
            continue
        dst, reason = classified
        if dst is None:
            continue
        actions.append(Action(kind="move", src=item, dst=dst, reason=reason))

    # 2) 之前已归档到 docs/test_reports/coverage 的覆盖率输出：按新规则挪到 data/logs
    add_fixed_move_from_candidates(
        [root / rules.coverage_dir / "coverage.json", root / "coverage.json"],
        root / rules.data_metrics_dir / "coverage.json",
        "覆盖率数据",
    )
    for name in ("coverage_output.txt", "full_coverage.txt", "test_coverage_output.txt"):
        add_fixed_move_from_candidates(
            [root / rules.coverage_dir / name, root / name],
            root / rules.logs_test_coverage_dir / name,
            "覆盖率日志",
        )

    # 2.1) root 下的 .coverage：即使是 dotfile，也按规则移到 tmp/_stale/
    add_fixed_move(root / ".coverage", root / rules.stale_dir / ".coverage", "临时覆盖率")

    # 2.2) Windows 保留名文件 nul：用 \\?\ 才能访问的情况也按规则移到 tmp/_empty/
    if os.name == "nt":
        nul_path = root / "nul"
        nul_alt = f"\\\\?\\{str(nul_path.resolve())}"
        if os.path.exists(nul_alt):
            actions.append(
                Action(
                    kind="move",
                    src=nul_path,
                    dst=root / rules.tmp_empty_dir / "nul.zero",
                    reason="空文件",
                )
            )

    # 3) 文档固定映射（按你给的表）
    # 注意：CLAUDE.md 明确不动（已在 root_keep_files）
    add_fixed_move(
        root / "FRONTEND_INTEGRATION_SUMMARY.md",
        root / rules.docs_integration_dir / "FRONTEND_INTEGRATION_SUMMARY.md",
        "集成文档",
    )
    add_fixed_move(
        root / "MEMORY_RAG_IMPLEMENTATION_PLAN.md",
        root / rules.docs_plans_dir / "MEMORY_RAG_IMPLEMENTATION_PLAN.md",
        "实施计划",
    )
    add_fixed_move(
        root / "next_actions_plan.md",
        root / rules.docs_plans_dir / "next_actions_plan.md",
        "行动计划",
    )
    add_fixed_move(
        root / "phase2_conversation_agent_plan.md",
        root / rules.docs_plans_dir / "phase2_conversation_agent_plan.md",
        "阶段计划",
    )
    add_fixed_move(
        root / "MOCK_CODE_PATCHES.md",
        root / rules.docs_testing_dir / "MOCK_CODE_PATCHES.md",
        "测试文档",
    )
    add_fixed_move(
        root / "MOCK_EXTERNAL_SERVICES_ANALYSIS.md",
        root / rules.docs_analysis_dir / "MOCK_EXTERNAL_SERVICES_ANALYSIS.md",
        "分析报告",
    )
    add_fixed_move(
        root / "MOCK_EXTERNAL_SERVICES_SUMMARY.md",
        root / rules.docs_summaries_dir / "MOCK_EXTERNAL_SERVICES_SUMMARY.md",
        "总结报告",
    )
    add_fixed_move(
        root / "MOCK_QUICK_REFERENCE.md",
        root / rules.docs_references_dir / "MOCK_QUICK_REFERENCE.md",
        "快速参考",
    )
    add_fixed_move(
        root / "PROJECT_RAG_COMPLETION_SUMMARY.md",
        root / rules.docs_summaries_dir / "PROJECT_RAG_COMPLETION_SUMMARY.md",
        "项目总结",
    )
    add_fixed_move(
        root / "TESTING_ANALYSIS_SUMMARY.md",
        root / rules.docs_testing_dir / "TESTING_ANALYSIS_SUMMARY.md",
        "测试分析",
    )
    add_fixed_move(
        root / "TESTING_DOCUMENTATION_INDEX.md",
        root / rules.docs_testing_dir / "TESTING_DOCUMENTATION_INDEX.md",
        "测试索引",
    )
    add_fixed_move(
        root / "TESTING_DOCUMENTS_MANIFEST.txt",
        root / rules.docs_testing_dir / "TESTING_DOCUMENTS_MANIFEST.txt",
        "测试清单",
    )
    add_fixed_move(
        root / "TESTING_EXECUTION_CHECKLIST.md",
        root / rules.docs_testing_dir / "TESTING_EXECUTION_CHECKLIST.md",
        "执行清单",
    )
    add_fixed_move(
        root / "TESTING_FINAL_REPORT.md",
        root / rules.docs_testing_dir / "TESTING_FINAL_REPORT.md",
        "最终报告",
    )
    add_fixed_move(
        root / "TESTING_QUICK_REFERENCE.md",
        root / rules.docs_references_dir / "TESTING_QUICK_REFERENCE.md",
        "测试参考",
    )
    add_fixed_move_from_candidates(
        [root / "WORKFLOW_CHAT_API_TEST.md", root / "docs" / "misc" / "WORKFLOW_CHAT_API_TEST.md"],
        root / rules.docs_testing_dir / "WORKFLOW_CHAT_API_TEST.md",
        "API测试",
    )

    # 4) test_create_agent.json 若已移到 docs/examples，则按新规则挪到 data/test_data
    add_fixed_move_from_candidates(
        [root / "docs" / "examples" / "test_create_agent.json", root / "test_create_agent.json"],
        root / rules.data_test_data_dir / "test_create_agent.json",
        "测试数据",
    )

    # 类型映射（全盘）：仅在 aggressive 模式启用，避免误伤仓库内部结构
    if mode == "aggressive":
        actions.extend(_plan_type_mapping(root, rules, mode))

    # 过时/临时文件：移至 tmp/_stale/
    for path in _iter_tree(root, rules):
        if _stale_candidate(rules, root, path, stale_days):
            rel = path.relative_to(root)
            dst = root / rules.stale_dir / rel.name
            actions.append(Action(kind="move", src=path, dst=dst, reason="过期临时"))

    # 风险标记：涉及高重要度目录（源或目标）
    marked: list[Action] = []
    for a in actions:
        if a.kind != "move" or a.src is None or a.dst is None:
            marked.append(a)
            continue
        # 额外安全闸：任何触及保护目录的动作直接丢弃
        if (
            _top_dir(root, a.src) in rules.protected_dirs
            or _top_dir(root, a.dst) in rules.protected_dirs
        ):
            continue
        risk = _is_high_importance(rules, root, a.src) or _is_high_importance(rules, root, a.dst)
        marked.append(dataclasses.replace(a, risk=risk or a.risk))

    # 去重：同一 src 只保留第一条动作（前面的规则优先级更高）
    seen_src: set[str] = set()
    uniq: list[Action] = []
    for a in marked:
        if a.kind == "move" and a.src is not None and a.dst is not None:
            key = str(a.src)
            if key in seen_src:
                continue
            seen_src.add(key)
        uniq.append(a)

    return uniq


def main(argv: list[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="智能整理项目文件结构（支持 dry-run / 回滚）")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="项目根目录（默认当前目录）")
    parser.add_argument(
        "--mode",
        choices=["safe", "standard", "aggressive"],
        default="standard",
        help="整理力度：safe=仅合并/特殊目录，standard=加少量类型映射，aggressive=更积极类型映射",
    )
    parser.add_argument("--stale-days", type=int, default=60, help="过时文件阈值（默认60天）")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不执行（建议默认先跑一次）")
    parser.add_argument("--apply", action="store_true", help="实际执行移动/创建/回滚脚本生成")
    parser.add_argument("--yes", action="store_true", help="配合 --apply 使用：确认执行文件移动")
    parser.add_argument("--prune-empty", action="store_true", help="执行后清理空目录（谨慎）")
    parser.add_argument(
        "--log-file",
        type=str,
        default="",
        help="日志文件路径；留空=默认写入 logs/；传 '-'=不写文件",
    )
    parser.add_argument("--no-rollback", action="store_true", help="不生成回滚脚本")
    parser.add_argument("--verbose", action="store_true", help="控制台输出每个操作明细（默认精简）")

    args = parser.parse_args(argv)

    root = args.root.resolve()
    rules = _build_rules()

    if args.apply and args.dry_run:
        print("参数冲突：--apply 与 --dry-run 不能同时使用。")
        return 2
    if args.apply and not args.yes:
        print("安全保护：实际执行需要同时传入 --apply --yes。")
        return 2
    dry_run = not args.apply
    if args.dry_run:
        dry_run = True

    if not root.exists() or not root.is_dir():
        print(f"根目录不存在：{root}")
        return 2

    if args.log_file.strip() == "-":
        log_file = None
    elif args.log_file.strip():
        log_file = (root / args.log_file).resolve()
    else:
        log_file = root / "logs" / f"file_organize_{_now_stamp()}.log"

    print(f"[{_ts()}] 阶段1/6：扫描与规则加载…")
    print(
        f"[{_ts()}] 保护目录：{', '.join(sorted({'src','web','definitions','typings'}))}（不移动、不扫描内容）"
    )
    print(f"[{_ts()}] 阶段2/6：分类决策矩阵…")
    actions = build_plan(root, rules, mode=args.mode, stale_days=args.stale_days)

    print(f"[{_ts()}] 阶段3/6：智能合并与特殊目录处理…")
    # 这里的动作已包含合并/htmlcov

    print(f"[{_ts()}] 阶段4/6：冲突检测与清理规划…")
    # 冲突在执行阶段处理（自动重命名）

    print(f"[{_ts()}] 阶段5/6：执行…({'dry-run' if dry_run else 'apply'})")
    counts = _apply_actions(
        root,
        rules,
        actions,
        dry_run=dry_run,
        prune_empty=args.prune_empty,
        log_file=log_file,
        make_rollback=not args.no_rollback,
        verbose=args.verbose,
    )

    print(f"[{_ts()}] 阶段6/6：验证与报告…")
    _summarize(root, rules, actions, counts, dry_run=dry_run, log_file=log_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
