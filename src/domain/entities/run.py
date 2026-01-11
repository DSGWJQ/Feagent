"""Run 实体 - 可追踪的工作流执行记录

业务定义:
    - Run 表示一次可追踪的执行实例（workflow / agent 兼容）
    - workflow run 生命周期: created → running → completed/failed
    - agent run 生命周期: pending → running → succeeded/failed
    - Run 作为可追踪/可复用的执行容器，关联事件流 (RunEvent)

设计原则:
    - 纯 Python 实现，不依赖任何框架 (DDD 要求)
    - 使用 dataclass 简化样板代码
    - 通过工厂方法 create() 封装创建逻辑
    - 维护状态流转不变式 (生命周期合法性)

关联:
    - Run 属于一个 Project (project_id)
    - Run 执行一个 Workflow (workflow_id)
    - Run 包含多个 RunEvent (事件流)
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from src.domain.exceptions import DomainError
from src.domain.value_objects.run_status import RunStatus


@dataclass
class Run:
    """Run 实体

    Attributes:
        id: 运行 ID (run_ 前缀，8位 hex)
        project_id: 关联的项目 ID（workflow run 用）
        workflow_id: 关联的工作流 ID（workflow run 用）
        agent_id: 关联的 Agent ID（agent run 用）
        status: 运行状态 (RunStatus 枚举)
        created_at: 创建时间 (UTC aware)
        started_at: 开始时间 (UTC aware, 可选)
        finished_at: 结束时间 (仅终态时有值，UTC aware)
        error: 错误信息（可选）
    """

    id: str
    project_id: str | None = None
    workflow_id: str | None = None
    agent_id: str | None = None
    status: RunStatus = RunStatus.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None

    @classmethod
    def create(
        cls,
        project_id: str | None = None,
        workflow_id: str | None = None,
        *,
        agent_id: str | None = None,
    ) -> "Run":
        """创建 Run 的工厂方法

        Args:
            project_id: 项目 ID（workflow run）
            workflow_id: 工作流 ID（workflow run）
            agent_id: Agent ID（agent run）

        Returns:
            Run 实例：workflow run 默认 CREATED；agent run 默认 PENDING

        Raises:
            DomainError: 当参数不满足任一创建模式时
        """
        if agent_id is not None:
            normalized_agent_id = agent_id.strip() if isinstance(agent_id, str) else ""
            if not normalized_agent_id:
                raise DomainError("agent_id 不能为空")
            # Agent runs: allow creation without a concrete workflow binding.
            # Persistence may still require project/workflow ids; keep minimal placeholders.
            normalized_project_id = (
                project_id.strip()
                if isinstance(project_id, str) and project_id.strip()
                else "proj_agent"
            )
            normalized_workflow_id = (
                workflow_id.strip()
                if isinstance(workflow_id, str) and workflow_id.strip()
                else f"wf_agent_{uuid4().hex[:8]}"
            )
            now = datetime.now(UTC)
            return cls(
                id=f"run_{uuid4().hex[:8]}",
                project_id=normalized_project_id,
                workflow_id=normalized_workflow_id,
                agent_id=normalized_agent_id,
                status=RunStatus.PENDING,
                created_at=now,
                started_at=None,
                finished_at=None,
                error=None,
            )

        if not project_id or not project_id.strip():
            raise DomainError("project_id 不能为空")
        if not workflow_id or not workflow_id.strip():
            raise DomainError("workflow_id 不能为空")

        now = datetime.now(UTC)
        return cls(
            id=f"run_{uuid4().hex[:8]}",
            project_id=project_id.strip(),
            workflow_id=workflow_id.strip(),
            agent_id=None,
            status=RunStatus.CREATED,
            created_at=now,
            started_at=None,
            finished_at=None,
            error=None,
        )

    @classmethod
    def create_with_idempotency(
        cls,
        *,
        project_id: str,
        workflow_id: str,
        idempotency_key: str,
    ) -> "Run":
        """创建幂等 Run（由 idempotency_key 派生稳定 run_id）。

        约束：
        - 不引入额外 DB 字段（KISS），通过稳定主键实现幂等。
        - run_id 取 sha256 前 16 hex，降低碰撞概率。
        """
        if not idempotency_key or not idempotency_key.strip():
            raise DomainError("idempotency_key 不能为空")

        if not project_id or not project_id.strip():
            raise DomainError("project_id 不能为空")
        if not workflow_id or not workflow_id.strip():
            raise DomainError("workflow_id 不能为空")

        key_material = (
            f"{project_id.strip()}|{workflow_id.strip()}|{idempotency_key.strip()}".encode()
        )
        digest = sha256(key_material).hexdigest()
        run_id = f"run_{digest[:16]}"
        now = datetime.now(UTC)
        return cls(
            id=run_id,
            project_id=project_id.strip(),
            workflow_id=workflow_id.strip(),
            agent_id=None,
            status=RunStatus.CREATED,
            created_at=now,
            started_at=None,
            finished_at=None,
            error=None,
        )

    def _assert_can_transition(self, target: RunStatus) -> None:
        """断言状态流转合法性"""
        if not self.status.can_transition_to(target):
            raise DomainError(f"非法状态流转: {self.status.value} → {target.value}")

    def start(self) -> None:
        """启动 Run (CREATED/PENDING → RUNNING)

        Raises:
            DomainError: 当前状态不是 CREATED/PENDING
        """
        if self.status not in {RunStatus.CREATED, RunStatus.PENDING}:
            raise DomainError(
                "只能从 PENDING 状态启动（workflow runs may also start from CREATED）"
            )
        self._assert_can_transition(RunStatus.RUNNING)
        self.status = RunStatus.RUNNING
        if self.started_at is None:
            self.started_at = datetime.now(UTC)

    def complete(self) -> None:
        """完成 Run (RUNNING → COMPLETED)

        Raises:
            DomainError: 当前状态不是 RUNNING
        """
        self._assert_can_transition(RunStatus.COMPLETED)
        self.status = RunStatus.COMPLETED
        self.finished_at = datetime.now(UTC)
        self.error = None

    def succeed(self) -> None:
        """完成 Run (RUNNING → SUCCEEDED) - agent runs 默认终态。

        Raises:
            DomainError: 当前状态不是 RUNNING
        """
        if self.status is not RunStatus.RUNNING:
            raise DomainError("只能从 RUNNING 状态完成")
        self._assert_can_transition(RunStatus.SUCCEEDED)
        self.status = RunStatus.SUCCEEDED
        self.finished_at = datetime.now(UTC)
        self.error = None

    def fail(self, *, error: str | None = None) -> None:
        """失败 Run (RUNNING → FAILED)

        Raises:
            DomainError: 当前状态不是 RUNNING
        """
        if self.status is not RunStatus.RUNNING:
            raise DomainError("只能从 RUNNING 状态失败")
        self._assert_can_transition(RunStatus.FAILED)
        self.status = RunStatus.FAILED
        self.finished_at = datetime.now(UTC)
        if isinstance(error, str) and error.strip():
            self.error = error.strip()

    @property
    def is_terminal(self) -> bool:
        """是否处于终态"""
        return self.status.is_terminal()

    @property
    def duration_seconds(self) -> float | None:
        """执行时长 (秒)，仅终态有值"""
        if self.finished_at is None:
            return None
        return (self.finished_at - self.created_at).total_seconds()
