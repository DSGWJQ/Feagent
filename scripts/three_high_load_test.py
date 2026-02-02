import argparse
import asyncio
import json
import random
import subprocess
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

DEFAULT_DB_DIR = Path(tempfile.gettempdir()).as_posix().rstrip("/")


@dataclass
class AttemptResult:
    profile: str
    stage: str
    workflow_class: str
    workflow_id: str
    start_ts: float
    end_ts: float
    duration_ms: float
    ttfb_ms: float | None
    events_count: int
    bytes_count: int
    terminal_type: str
    http_status: int
    run_id: str | None
    error_type: str | None


@dataclass
class StageStats:
    stage: str
    concurrency: int
    duration_s: int
    total_attempts: int
    error_rate: float
    incomplete_rate: float
    error_counts: dict[str, int]
    p95_by_class: dict[str, float]


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    values_sorted = sorted(values)
    k = (len(values_sorted) - 1) * pct
    f = int(k)
    c = min(f + 1, len(values_sorted) - 1)
    if f == c:
        return values_sorted[f]
    d0 = values_sorted[f] * (c - k)
    d1 = values_sorted[c] * (k - f)
    return d0 + d1


def _sample_process(pid: int | None) -> dict[str, Any] | None:
    if not pid:
        return None
    try:
        output = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    f"Get-Process -Id {pid} | "
                    "Select-Object CPU,WorkingSet,Handles,Threads | ConvertTo-Json"
                ),
            ],
            text=True,
            timeout=5,
        ).strip()
        return json.loads(output) if output else None
    except Exception:
        return None


def _count_connections(port: int) -> int | None:
    try:
        output = subprocess.check_output(
            ["cmd.exe", "/c", f"netstat -ano | findstr :{port}"],
            text=True,
            timeout=5,
        )
        count = 0
        for line in output.splitlines():
            if "ESTABLISHED" in line:
                count += 1
        return count
    except Exception:
        return None


async def _confirm_run_side_effect(
    client: httpx.AsyncClient,
    base_url: str,
    run_id: str | None,
    confirm_id: str | None,
) -> bool:
    if not run_id or not confirm_id:
        return False
    try:
        resp = await client.post(
            f"{base_url}/api/runs/{run_id}/confirm",
            json={"confirm_id": confirm_id, "decision": "allow"},
        )
        if resp.status_code != 200:
            return False
        data = resp.json()
        return bool(data.get("ok"))
    except Exception:
        return False


async def _stream_workflow(
    client: httpx.AsyncClient,
    base_url: str,
    url: str,
    payload: dict[str, Any],
    max_wait_s: int,
    run_id: str | None,
) -> tuple[str, int, int, int, float | None, str | None]:
    status_code = 0
    events_count = 0
    bytes_count = 0
    terminal_type = "disconnect"
    error_type = None
    first_event_at = None

    async def _consume_stream() -> None:
        nonlocal status_code, events_count, bytes_count, terminal_type, first_event_at, error_type
        async with client.stream(
            "POST",
            url,
            json=payload,
            headers={"Accept": "text/event-stream"},
        ) as response:
            status_code = response.status_code
            if status_code != 200:
                terminal_type = "http_error"
                error_type = f"http_{status_code}"
                return

            async for line in response.aiter_lines():
                if not line:
                    continue
                bytes_count += len(line)
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    payload_data = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if first_event_at is None:
                    first_event_at = time.perf_counter()
                events_count += 1
                event_type = payload_data.get("type")
                if event_type == "workflow_confirm_required":
                    confirm_ok = await _confirm_run_side_effect(
                        client,
                        base_url,
                        run_id,
                        payload_data.get("confirm_id"),
                    )
                    if not confirm_ok and not error_type:
                        error_type = "confirm_failed"
                    continue
                if event_type in {"workflow_complete", "workflow_error"}:
                    terminal_type = event_type
                    break

    try:
        await asyncio.wait_for(_consume_stream(), timeout=max_wait_s)
    except TimeoutError:
        terminal_type = "timeout"
        error_type = "timeout"
    except httpx.HTTPError as exc:
        terminal_type = "disconnect"
        error_type = f"httpx_{exc.__class__.__name__}"

    return terminal_type, status_code, events_count, bytes_count, first_event_at, error_type


async def _run_attempt(
    client: httpx.AsyncClient,
    profile: str,
    base_url: str,
    project_id: str,
    workflow_class: str,
    workflow_id: str,
    max_wait_s: int,
) -> AttemptResult:
    start = time.perf_counter()
    run_id = None
    error_type = None

    if profile == "A":
        run_url = f"{base_url}/api/projects/{project_id}/workflows/{workflow_id}/runs"
        try:
            run_resp = await client.post(run_url, json={})
            if run_resp.status_code not in {200, 201}:
                error_type = f"run_create_{run_resp.status_code}"
                end = time.perf_counter()
                return AttemptResult(
                    profile=profile,
                    stage="",
                    workflow_class=workflow_class,
                    workflow_id=workflow_id,
                    start_ts=start,
                    end_ts=end,
                    duration_ms=(end - start) * 1000,
                    ttfb_ms=None,
                    events_count=0,
                    bytes_count=0,
                    terminal_type="http_error",
                    http_status=run_resp.status_code,
                    run_id=None,
                    error_type=error_type,
                )
            run_id = run_resp.json().get("id")
        except Exception as exc:
            end = time.perf_counter()
            return AttemptResult(
                profile=profile,
                stage="",
                workflow_class=workflow_class,
                workflow_id=workflow_id,
                start_ts=start,
                end_ts=end,
                duration_ms=(end - start) * 1000,
                ttfb_ms=None,
                events_count=0,
                bytes_count=0,
                terminal_type="exception",
                http_status=0,
                run_id=None,
                error_type=f"run_create_exception:{exc}",
            )

    exec_url = f"{base_url}/api/workflows/{workflow_id}/execute/stream"
    initial_input = {
        "run_id": run_id or f"legacy_{uuid.uuid4().hex}",
        "db_dir": DEFAULT_DB_DIR,
    }
    payload: dict[str, Any] = {"initial_input": initial_input}
    if run_id:
        payload["run_id"] = run_id

    (
        terminal_type,
        status_code,
        events_count,
        bytes_count,
        first_event_at,
        error_type_exec,
    ) = await _stream_workflow(client, base_url, exec_url, payload, max_wait_s, run_id)

    end = time.perf_counter()
    ttfb_ms = (first_event_at - start) * 1000 if first_event_at else None
    error_type = error_type or error_type_exec

    return AttemptResult(
        profile=profile,
        stage="",
        workflow_class=workflow_class,
        workflow_id=workflow_id,
        start_ts=start,
        end_ts=end,
        duration_ms=(end - start) * 1000,
        ttfb_ms=ttfb_ms,
        events_count=events_count,
        bytes_count=bytes_count,
        terminal_type=terminal_type,
        http_status=status_code,
        run_id=run_id,
        error_type=error_type,
    )


async def _run_stage(
    profile: str,
    base_url: str,
    project_id: str,
    stage_name: str,
    concurrency: int,
    duration_s: int,
    workflow_map: dict[str, str],
    weights: dict[str, int],
    max_wait_s: int,
    results: list[AttemptResult],
) -> list[dict[str, Any]]:
    end_at = time.perf_counter() + duration_s
    classes = list(workflow_map.keys())
    weight_values = [weights[c] for c in classes]

    async def worker() -> None:
        async with httpx.AsyncClient(timeout=None) as client:
            while time.perf_counter() < end_at:
                workflow_class = random.choices(classes, weights=weight_values, k=1)[0]
                workflow_id = workflow_map[workflow_class]
                attempt = await _run_attempt(
                    client,
                    profile,
                    base_url,
                    project_id,
                    workflow_class,
                    workflow_id,
                    max_wait_s,
                )
                attempt.stage = stage_name
                results.append(attempt)

    tasks = [asyncio.create_task(worker()) for _ in range(concurrency)]
    await asyncio.gather(*tasks)
    return [asdict(r) for r in results if r.stage == stage_name]


def _summarize_stage(
    stage: str, concurrency: int, duration_s: int, results: list[AttemptResult]
) -> StageStats:
    total = len(results)
    error_counts: dict[str, int] = {
        "http_5xx": 0,
        "timeout": 0,
        "disconnect": 0,
        "workflow_error": 0,
    }
    incomplete = 0

    durations_by_class: dict[str, list[float]] = {}

    for res in results:
        durations_by_class.setdefault(res.workflow_class, []).append(res.duration_ms)
        if res.terminal_type in {"timeout", "disconnect"}:
            incomplete += 1
        if res.http_status >= 500:
            error_counts["http_5xx"] += 1
        if res.terminal_type == "timeout":
            error_counts["timeout"] += 1
        if res.terminal_type == "disconnect":
            error_counts["disconnect"] += 1
        if res.terminal_type == "workflow_error":
            error_counts["workflow_error"] += 1

    errors = sum(error_counts.values())
    error_rate = errors / total if total else 0.0
    incomplete_rate = incomplete / total if total else 0.0

    p95_by_class = {
        cls: round(_percentile(values, 0.95), 2) for cls, values in durations_by_class.items()
    }

    return StageStats(
        stage=stage,
        concurrency=concurrency,
        duration_s=duration_s,
        total_attempts=total,
        error_rate=round(error_rate, 4),
        incomplete_rate=round(incomplete_rate, 4),
        error_counts=error_counts,
        p95_by_class=p95_by_class,
    )


def _select_stable_and_knee(
    stages: list[StageStats], baseline_p95: dict[str, float]
) -> tuple[str | None, str | None]:
    stable = None
    knee = None
    for stat in stages:
        violated = False
        if stat.error_rate >= 0.01:
            violated = True
        for cls, p95 in stat.p95_by_class.items():
            base = baseline_p95.get(cls, 0.0)
            if base and p95 > 2 * base:
                violated = True
                break
        if not violated:
            stable = stat.stage
        elif knee is None:
            knee = stat.stage
    return stable, knee


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Three-high load test runner")
    parser.add_argument("--profile", choices=["A", "B"], required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--project-id", default="e2e_test_project")
    parser.add_argument("--output", required=True)
    parser.add_argument("--server-pid", type=int, default=0)
    parser.add_argument("--server-port", type=int, default=0)
    parser.add_argument("--baseline-concurrency", type=int, default=10)
    parser.add_argument("--baseline-duration", type=int, default=120)
    parser.add_argument("--stages", default="25:120,40:120")
    parser.add_argument("--max-wait", type=int, default=120)

    args = parser.parse_args()

    workflow_map = {
        "W1": "wf_d63e074d",
        "W2": "wf_bd0ea003",
        "W3": "wf_b8b02e10",
        "W4": "wf_daddf5b1",
    }
    weights = {"W1": 30, "W2": 40, "W3": 20, "W4": 10}

    stage_defs = [("baseline", args.baseline_concurrency, args.baseline_duration)]
    for stage in args.stages.split(","):
        if not stage.strip():
            continue
        conc, dur = stage.split(":")
        stage_defs.append((f"c{conc}", int(conc), int(dur)))

    results: list[AttemptResult] = []
    stage_stats: list[StageStats] = []
    stage_snapshots: list[dict[str, Any]] = []

    for name, conc, duration_s in stage_defs:
        proc_before = _sample_process(args.server_pid)
        conn_before = _count_connections(args.server_port) if args.server_port else None

        asyncio.run(
            _run_stage(
                args.profile,
                args.base_url,
                args.project_id,
                name,
                conc,
                duration_s,
                workflow_map,
                weights,
                args.max_wait,
                results,
            )
        )

        proc_after = _sample_process(args.server_pid)
        conn_after = _count_connections(args.server_port) if args.server_port else None
        stage_results = [r for r in results if r.stage == name]
        stats = _summarize_stage(name, conc, duration_s, stage_results)
        stage_stats.append(stats)
        stage_snapshots.append(
            {
                "stage": name,
                "concurrency": conc,
                "duration_s": duration_s,
                "process_before": proc_before,
                "process_after": proc_after,
                "connections_before": conn_before,
                "connections_after": conn_after,
            }
        )

    baseline_p95 = stage_stats[0].p95_by_class if stage_stats else {}
    stable, knee = _select_stable_and_knee(stage_stats, baseline_p95)

    output = {
        "profile": args.profile,
        "base_url": args.base_url,
        "project_id": args.project_id,
        "workflow_map": workflow_map,
        "weights": weights,
        "stages": [asdict(stat) for stat in stage_stats],
        "stage_snapshots": stage_snapshots,
        "baseline_p95": baseline_p95,
        "stable_stage": stable,
        "knee_stage": knee,
        "attempts": [asdict(r) for r in results],
    }

    _write_json(Path(args.output), output)


if __name__ == "__main__":
    main()
