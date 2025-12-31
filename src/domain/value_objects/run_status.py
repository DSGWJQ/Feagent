"""RunStatus 枚举 - Run 生命周期状态

业务定义：
- Run 表示一次 workflow 执行实例
- 状态流转：CREATED → RUNNING → (COMPLETED | FAILED)

设计原则：
- 继承 str：序列化/数据库存储友好
- 通过 can_transition_to() 固化状态机不变式
"""

from __future__ import annotations

from enum import Enum


class RunStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

    def can_transition_to(self, target: RunStatus) -> bool:
        allowed: dict[RunStatus, set[RunStatus]] = {
            RunStatus.CREATED: {RunStatus.RUNNING},
            RunStatus.RUNNING: {RunStatus.COMPLETED, RunStatus.FAILED},
            RunStatus.COMPLETED: set(),
            RunStatus.FAILED: set(),
        }
        return target in allowed[self]

    def is_terminal(self) -> bool:
        return self in {RunStatus.COMPLETED, RunStatus.FAILED}
