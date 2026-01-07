#!/usr/bin/env python3
"""
Collect M4 E2E verification metrics from `m4-verify.sh` artifacts and update a dashboard JSON.

Inputs (expected in --run-dir):
  - meta.json
  - seed-results.json
  - playwright-run-<N>.json (Playwright JSON reporter output)
  - playwright-run-<N>.exitcode

Outputs:
  - summary.json (structured metrics)
  - report.md (human readable)
  - metrics.json (append-only, for dashboard)
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import platform
import re
import subprocess
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected object JSON at {path}")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _find_repo_root(start: Path) -> Path | None:
    cur = start.resolve()
    for _ in range(20):
        if (cur / ".git").exists():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent
    return None


def _run_cmd(cmd: list[str], *, cwd: Path | None = None, timeout_s: int = 5) -> str | None:
    try:
        out = subprocess.check_output(cmd, cwd=str(cwd) if cwd else None, timeout=timeout_s)
        return out.decode("utf-8", errors="replace").strip()
    except Exception:
        return None


def _env_snapshot(run_dir: Path) -> dict[str, Any]:
    repo_root = _find_repo_root(run_dir) or run_dir
    return {
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "python": {"version": platform.python_version(), "executable": sys.executable},
        "node": {"version": _run_cmd(["node", "-v"], cwd=repo_root)},
        "playwright": {"version": _run_cmd(["npx", "playwright", "--version"], cwd=repo_root)},
        "git": {
            "commit": _run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_root),
            "branch": _run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root),
            "dirty": _run_cmd(["git", "status", "--porcelain"], cwd=repo_root),
        },
        "captured_at": _utc_now_iso(),
    }


def _classify_error(message: str) -> str:
    m = message.lower()
    if "timeout" in m or "timed out" in m:
        return "timeout"
    if "net::" in m or "econn" in m or "socket" in m or "connection" in m:
        return "network"
    if "expect(" in m or "tohave" in m or "tobe" in m or "assert" in m:
        return "assertion"
    if "http" in m and re.search(r"\b(4\d\d|5\d\d)\b", m):
        return "http_error"
    if "strict mode violation" in m:
        return "locator_strict"
    return "other"


@dataclasses.dataclass(frozen=True)
class ParsedTest:
    key: str
    file: str | None
    project: str | None
    status: str
    attempts: int
    retries_used: int
    duration_ms: int
    error_message: str | None
    error_category: str | None


def _walk_playwright_suites(report: dict[str, Any]) -> Iterable[dict[str, Any]]:
    suites = report.get("suites") or []
    if not isinstance(suites, list):
        return []
    return suites


def _parse_playwright_report(report: dict[str, Any]) -> list[ParsedTest]:
    parsed: list[ParsedTest] = []

    def walk_suite(suite: dict[str, Any], parent_titles: list[str]) -> None:
        title = suite.get("title")
        titles = parent_titles + ([title] if isinstance(title, str) and title else [])

        for spec in suite.get("specs") or []:
            if isinstance(spec, dict):
                walk_spec(spec, titles)

        for child in suite.get("suites") or []:
            if isinstance(child, dict):
                walk_suite(child, titles)

    def walk_spec(spec: dict[str, Any], parent_titles: list[str]) -> None:
        spec_title = spec.get("title")
        spec_file = spec.get("file")
        for test in spec.get("tests") or []:
            if not isinstance(test, dict):
                continue

            title_path = test.get("titlePath")
            if not isinstance(title_path, list) or not all(isinstance(x, str) for x in title_path):
                title_path = [t for t in parent_titles if t]
                if isinstance(spec_title, str) and spec_title:
                    title_path.append(spec_title)
                t_title = test.get("title")
                if isinstance(t_title, str) and t_title:
                    title_path.append(t_title)

            results = test.get("results") or []
            if not isinstance(results, list):
                results = []

            attempts = max(1, len(results))
            final_status = None
            duration_ms = 0
            last_error_message: str | None = None

            for _idx, res in enumerate(results):
                if not isinstance(res, dict):
                    continue
                status = res.get("status")
                if isinstance(status, str):
                    final_status = status
                dur = res.get("duration")
                if isinstance(dur, int):
                    duration_ms += max(0, dur)
                errors = res.get("errors") or []
                if isinstance(errors, list) and errors:
                    last = errors[-1]
                    if isinstance(last, dict):
                        msg = last.get("message")
                        if isinstance(msg, str) and msg.strip():
                            last_error_message = msg.strip()

            if not isinstance(final_status, str) or not final_status:
                status = test.get("status")
                final_status = status if isinstance(status, str) else "unknown"

            retries_used = max(0, attempts - 1)
            project = test.get("projectName") if isinstance(test.get("projectName"), str) else None

            error_category = None
            if last_error_message and final_status != "passed":
                error_category = _classify_error(last_error_message)

            key = " :: ".join([p for p in title_path if p]) or "<unknown>"
            if isinstance(spec_file, str) and spec_file:
                key = f"{spec_file} :: {key}"

            parsed.append(
                ParsedTest(
                    key=key,
                    file=spec_file if isinstance(spec_file, str) else None,
                    project=project,
                    status=final_status,
                    attempts=attempts,
                    retries_used=retries_used,
                    duration_ms=duration_ms,
                    error_message=last_error_message,
                    error_category=error_category,
                )
            )

    for suite in _walk_playwright_suites(report):
        if isinstance(suite, dict):
            walk_suite(suite, [])

    return parsed


def _summarize_iteration(iteration: int, report_path: Path) -> dict[str, Any]:
    try:
        report = _read_json(report_path)
    except Exception as exc:
        return {
            "iteration": iteration,
            "report_file": str(report_path),
            "parse_error": str(exc),
            "executed": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "flaky": 0,
            "exit_code": _read_exit_code(report_path),
        }

    tests = _parse_playwright_report(report)
    status_counts = Counter(t.status for t in tests)

    executed_statuses = {"passed", "failed", "timedOut", "interrupted"}
    executed = sum(count for st, count in status_counts.items() if st in executed_statuses)
    passed = status_counts.get("passed", 0)
    skipped = status_counts.get("skipped", 0)
    failed = executed - passed
    flaky = sum(1 for t in tests if t.status == "passed" and t.retries_used > 0)

    return {
        "iteration": iteration,
        "report_file": str(report_path),
        "executed": executed,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "flaky": flaky,
        "exit_code": _read_exit_code(report_path),
        "tests": [dataclasses.asdict(t) for t in tests],
    }


def _read_exit_code(report_path: Path) -> int | None:
    p = report_path.with_suffix(".exitcode")
    if not p.exists():
        return None
    try:
        raw = p.read_text(encoding="utf-8").strip()
        return int(raw)
    except Exception:
        return None


def _collect_iterations(run_dir: Path) -> list[dict[str, Any]]:
    run_files = sorted(run_dir.glob("playwright-run-*.json"))
    iterations: list[dict[str, Any]] = []
    for path in run_files:
        m = re.search(r"playwright-run-(\d+)\.json$", path.name)
        if not m:
            continue
        idx = int(m.group(1))
        iterations.append(_summarize_iteration(idx, path))
    iterations.sort(key=lambda x: x["iteration"])
    return iterations


def _overall_summary(iterations: list[dict[str, Any]]) -> dict[str, Any]:
    executed = sum(it["executed"] for it in iterations)
    passed = sum(it["passed"] for it in iterations)
    failed = sum(it["failed"] for it in iterations)
    skipped = sum(it["skipped"] for it in iterations)
    flaky = sum(it["flaky"] for it in iterations)

    pass_rate = (passed / executed) if executed else 0.0
    flaky_rate = (flaky / executed) if executed else 0.0

    # Flaky / failure aggregation across all iterations
    flaky_by_test: dict[str, int] = defaultdict(int)
    max_retries_by_test: dict[str, int] = defaultdict(int)
    failures: list[dict[str, Any]] = []
    failure_categories: Counter[str] = Counter()

    for it in iterations:
        for t in it.get("tests") or []:
            if not isinstance(t, dict):
                continue
            key = t.get("key")
            if not isinstance(key, str):
                continue
            status = t.get("status")
            retries_used = t.get("retries_used")
            if status == "passed" and isinstance(retries_used, int) and retries_used > 0:
                flaky_by_test[key] += 1
                max_retries_by_test[key] = max(max_retries_by_test[key], retries_used)
            if status != "passed" and status != "skipped":
                msg = t.get("error_message") if isinstance(t.get("error_message"), str) else None
                cat = t.get("error_category") if isinstance(t.get("error_category"), str) else None
                if cat:
                    failure_categories[cat] += 1
                failures.append(
                    {
                        "key": key,
                        "status": status,
                        "error_category": cat,
                        "error_message": (msg[:2000] if msg else None),
                    }
                )

    flaky_tests_sorted = sorted(
        flaky_by_test.items(),
        key=lambda kv: (kv[1], max_retries_by_test.get(kv[0], 0)),
        reverse=True,
    )
    flaky_tests = [
        {"key": k, "flaky_occurrences": n, "max_retries_used": max_retries_by_test.get(k, 0)}
        for k, n in flaky_tests_sorted
    ]

    failures_by_test: Counter[str] = Counter(
        f["key"] for f in failures if isinstance(f.get("key"), str)
    )
    top_failures = [
        {
            "key": key,
            "failures": count,
            "sample_error_category": next(
                (f.get("error_category") for f in failures if f.get("key") == key), None
            ),
            "sample_error_message": next(
                (f.get("error_message") for f in failures if f.get("key") == key), None
            ),
        }
        for key, count in failures_by_test.most_common(20)
    ]

    return {
        "executed": executed,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "pass_rate": pass_rate,
        "flaky": flaky,
        "flaky_rate": flaky_rate,
        "failure_categories": dict(failure_categories),
        "flaky_tests": flaky_tests[:50],
        "top_failures": top_failures,
    }


def _render_report_md(summary: dict[str, Any]) -> str:
    run_id = summary.get("run_id") or "<unknown>"
    meta = summary.get("meta") or {}
    api = meta.get("api_base_url") or ""
    web = meta.get("web_base_url") or ""
    min_pass_rate = meta.get("min_pass_rate")

    seed = summary.get("seed_verification") or {}
    seed_passed = seed.get("passed")

    overall = summary.get("deterministic_overall") or {}
    pass_rate = overall.get("pass_rate", 0.0)
    flaky_rate = overall.get("flaky_rate", 0.0)

    lines: list[str] = []
    lines.append("# M4 E2E 验证报告")
    lines.append("")
    lines.append(f"- run_id: `{run_id}`")
    lines.append(f"- generated_at: `{summary.get('generated_at')}`")
    if api:
        lines.append(f"- api_base_url: `{api}`")
    if web:
        lines.append(f"- web_base_url: `{web}`")
    lines.append("")

    lines.append("## Seed API 验证 (M4.2)")
    lines.append("")
    lines.append(f"- passed: `{seed_passed}`")
    lines.append("")
    lines.append("| fixture_type | seed | get_before | cleanup | get_after | passed |")
    lines.append("|---|---:|---:|---:|---:|---|")
    for fx in seed.get("fixtures") or []:
        if not isinstance(fx, dict):
            continue
        lines.append(
            "| {fixture} | {seed} | {gb} | {cl} | {ga} | {passed} |".format(
                fixture=fx.get("fixture_type", ""),
                seed=fx.get("seed_http_status", ""),
                gb=fx.get("get_before_http_status", ""),
                cl=fx.get("cleanup_http_status", ""),
                ga=fx.get("get_after_http_status", ""),
                passed=fx.get("passed", ""),
            )
        )
    lines.append("")

    if seed.get("checks"):
        lines.append("### 额外检查")
        lines.append("")
        for chk in seed.get("checks") or []:
            if not isinstance(chk, dict):
                continue
            lines.append(f"- {chk.get('name')}: HTTP {chk.get('http_status')}")
        lines.append("")

    lines.append("## Deterministic 稳定性验证 (M4.3)")
    lines.append("")
    lines.append(f"- min_pass_rate: `{min_pass_rate}`")
    lines.append(f"- executed: `{overall.get('executed')}`")
    lines.append(f"- passed: `{overall.get('passed')}`")
    lines.append(f"- failed: `{overall.get('failed')}`")
    lines.append(f"- pass_rate: `{pass_rate:.2%}`")
    lines.append(f"- flaky: `{overall.get('flaky')}`")
    lines.append(f"- flaky_rate: `{flaky_rate:.2%}`")
    lines.append("")

    lines.append("| iteration | executed | passed | failed | skipped | flaky | exit_code |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|")
    for it in summary.get("deterministic_iterations") or []:
        if not isinstance(it, dict):
            continue
        lines.append(
            "| {i} | {e} | {p} | {f} | {s} | {fl} | {c} |".format(
                i=it.get("iteration"),
                e=it.get("executed"),
                p=it.get("passed"),
                f=it.get("failed"),
                s=it.get("skipped"),
                fl=it.get("flaky"),
                c=it.get("exit_code"),
            )
        )
    lines.append("")

    lines.append("### Flaky Tests (Top)")
    lines.append("")
    flaky_tests = (overall.get("flaky_tests") or [])[:20]
    if not flaky_tests:
        lines.append("- (none)")
    else:
        for t in flaky_tests:
            if not isinstance(t, dict):
                continue
            lines.append(
                f"- `{t.get('key')}` occurrences={t.get('flaky_occurrences')} max_retries={t.get('max_retries_used')}"
            )
    lines.append("")

    lines.append("### Failures (Top)")
    lines.append("")
    top_failures = (overall.get("top_failures") or [])[:20]
    if not top_failures:
        lines.append("- (none)")
    else:
        for f in top_failures:
            if not isinstance(f, dict):
                continue
            lines.append(
                f"- `{f.get('key')}` failures={f.get('failures')} category={f.get('sample_error_category')}"
            )
    lines.append("")

    cats = overall.get("failure_categories") or {}
    if isinstance(cats, dict) and cats:
        lines.append("### Failure Categories")
        lines.append("")
        for k, v in sorted(cats.items(), key=lambda kv: kv[1], reverse=True):
            lines.append(f"- {k}: {v}")
        lines.append("")

    return "\n".join(lines)


def _load_seed_results(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "seed-results.json"
    if not path.exists():
        return {"passed": False, "missing": True, "fixtures": []}
    try:
        return _read_json(path)
    except Exception as exc:
        return {"passed": False, "parse_error": str(exc), "fixtures": []}


def _update_metrics_file(metrics_file: Path, run_summary: dict[str, Any]) -> None:
    data: dict[str, Any] = {"schema_version": "1.0", "updated_at": _utc_now_iso(), "runs": []}
    if metrics_file.exists():
        try:
            loaded = _read_json(metrics_file)
            if isinstance(loaded.get("runs"), list):
                data = loaded
        except Exception:
            pass

    runs = data.get("runs")
    if not isinstance(runs, list):
        runs = []

    runs.append(run_summary)
    data["runs"] = runs
    data["updated_at"] = _utc_now_iso()
    _write_json(metrics_file, data)


def cmd_summarize(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()
    if not run_dir.exists():
        raise SystemExit(f"--run-dir not found: {run_dir}")

    meta_path = run_dir / "meta.json"
    meta = _read_json(meta_path) if meta_path.exists() else {}
    run_id = meta.get("run_id") or run_dir.name

    iterations = _collect_iterations(run_dir)
    overall = _overall_summary(iterations)

    seed = _load_seed_results(run_dir)
    seed_passed = bool(seed.get("passed")) and not bool(seed.get("skipped"))

    summary: dict[str, Any] = {
        "schema_version": "1.0",
        "run_id": run_id,
        "generated_at": _utc_now_iso(),
        "meta": meta,
        "environment": _env_snapshot(run_dir),
        "seed_verification": seed,
        "deterministic_iterations": [
            {
                k: it.get(k)
                for k in (
                    "iteration",
                    "executed",
                    "passed",
                    "failed",
                    "skipped",
                    "flaky",
                    "exit_code",
                )
            }
            for it in iterations
        ],
        "deterministic_overall": overall,
        "artifacts": {
            "run_dir": str(run_dir),
            "report_md": str(Path(args.out_report).resolve()) if args.out_report else None,
            "summary_json": str(Path(args.out_summary).resolve()) if args.out_summary else None,
        },
    }

    if args.out_summary:
        _write_json(Path(args.out_summary), summary)
    if args.out_report:
        _write_text(Path(args.out_report), _render_report_md(summary))

    if args.metrics_file:
        metrics_path = Path(args.metrics_file).resolve()
        run_record = {
            "run_id": summary["run_id"],
            "generated_at": summary["generated_at"],
            "meta": summary["meta"],
            "seed_passed": seed_passed,
            "deterministic_overall": overall,
            "artifacts": {"run_dir": str(run_dir)},
        }
        _update_metrics_file(metrics_path, run_record)

    min_pass_rate = float(args.min_pass_rate)
    pass_rate = float(overall.get("pass_rate", 0.0))
    ok = seed_passed and pass_rate >= min_pass_rate

    print(f"[collect-metrics] run_id={run_id} seed_passed={seed_passed} pass_rate={pass_rate:.2%}")
    if not ok:
        print(
            f"[collect-metrics] FAIL threshold min_pass_rate={min_pass_rate:.2%}", file=sys.stderr
        )
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("summarize", help="Summarize m4-verify artifacts and update metrics.json")
    s.add_argument("--run-dir", required=True)
    s.add_argument("--min-pass-rate", default="0.95")
    s.add_argument("--out-summary", required=True)
    s.add_argument("--out-report", required=True)
    s.add_argument(
        "--schema", required=False, help="Path to metrics JSON schema (stored for reference)"
    )
    s.add_argument(
        "--metrics-file", required=False, help="Append run summary into this metrics.json"
    )
    s.set_defaults(func=cmd_summarize)

    return p


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
