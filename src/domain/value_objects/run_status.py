"""RunStatus 枚举 - Run 生命周期状态

兼容两条链路：
- Workflow Runs（主链路 /api/workflows/*）：created → running → completed/failed
- Agent Runs（实验入口 /api/agents/*）：pending → running → succeeded/failed

说明：
- 为兼容历史/现有数据，保留 created/completed 值；同时提供 pending/succeeded。
- 状态机允许 created/pending 均可进入 running；running 可进入 completed/succeeded/failed。
"""

from __future__ import annotations

from enum import Enum


class RunStatus(str, Enum):
    CREATED = "created"
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

    def can_transition_to(self, target: RunStatus) -> bool:
        allowed: dict[RunStatus, set[RunStatus]] = {
            RunStatus.CREATED: {RunStatus.RUNNING},
            RunStatus.PENDING: {RunStatus.RUNNING},
            RunStatus.RUNNING: {RunStatus.COMPLETED, RunStatus.SUCCEEDED, RunStatus.FAILED},
            RunStatus.COMPLETED: set(),
            RunStatus.SUCCEEDED: set(),
            RunStatus.FAILED: set(),
        }
        return target in allowed[self]

    def is_terminal(self) -> bool:
        return self in {RunStatus.COMPLETED, RunStatus.SUCCEEDED, RunStatus.FAILED}
