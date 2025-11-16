"""ORM 模型 - 数据库表映射

为什么需要 ORM 模型？
1. 数据库表映射：定义表结构、字段类型、约束
2. 关系定义：外键、一对多、多对多
3. 索引优化：提高查询性能
4. 与领域实体分离：关注点分离

ORM 模型 vs 领域实体：
- ORM 模型：数据库表映射，关注持久化（Infrastructure 层）
- 领域实体：业务逻辑，关注不变式（Domain 层）
- 通过 Assembler 转换：ORM ⇄ Entity

设计原则：
- 使用 SQLAlchemy 2.0 风格（Mapped、mapped_column）
- 主键使用 UUID 字符串（与领域实体一致）
- 外键使用级联删除（CASCADE）
- 添加索引优化查询（agent_id、status、created_at）
- 时间戳字段用于审计（created_at、updated_at）
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.base import Base


class AgentModel(Base):
    """Agent ORM 模型

    表名：agents

    字段说明：
    - id: 主键（UUID 字符串，36 字符）
    - start: 任务起点描述（Text，无长度限制）
    - goal: 任务目的描述（Text，无长度限制）
    - status: Agent 状态（active/archived，20 字符）
    - name: Agent 名称（255 字符）
    - created_at: 创建时间（自动设置）

    关系：
    - runs: 一对多关系（一个 Agent 有多个 Run）

    索引：
    - idx_agents_status: status 字段索引（查询活跃 Agent）
    - idx_agents_created_at: created_at 字段索引（按时间排序）

    为什么使用 Mapped 和 mapped_column？
    - SQLAlchemy 2.0 推荐的类型提示方式
    - IDE 友好（自动补全、类型检查）
    - 更清晰的字段定义
    """

    __tablename__ = "agents"

    # 主键
    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="Agent ID（UUID）")

    # 业务字段
    start: Mapped[str] = mapped_column(Text, nullable=False, comment="任务起点描述")
    goal: Mapped[str] = mapped_column(Text, nullable=False, comment="任务目的描述")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", comment="Agent 状态"
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Agent 名称")

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="创建时间"
    )

    # 关系（一对多：一个 Agent 有多个 Run）
    # cascade="all, delete-orphan": 删除 Agent 时级联删除所有 Run
    # back_populates: 双向关系（RunModel.agent）
    runs: Mapped[list["RunModel"]] = relationship(
        "RunModel", back_populates="agent", cascade="all, delete-orphan", lazy="selectin"
    )

    # 索引
    __table_args__ = (
        Index("idx_agents_status", "status"),  # 查询活跃 Agent
        Index("idx_agents_created_at", "created_at"),  # 按时间排序
    )

    def __repr__(self) -> str:
        return f"<AgentModel(id={self.id}, name={self.name}, status={self.status})>"


class RunModel(Base):
    """Run ORM 模型

    表名：runs

    字段说明：
    - id: 主键（UUID 字符串，36 字符）
    - agent_id: 外键（关联 Agent，级联删除）
    - status: Run 状态（pending/running/succeeded/failed，20 字符）
    - created_at: 创建时间（自动设置）
    - started_at: 开始执行时间（可选）
    - finished_at: 完成时间（可选）
    - error: 错误信息（可选，Text）

    关系：
    - agent: 多对一关系（多个 Run 属于一个 Agent）

    索引：
    - idx_runs_agent_id: agent_id 字段索引（查询 Agent 的所有 Run）
    - idx_runs_status: status 字段索引（查询特定状态的 Run）
    - idx_runs_created_at: created_at 字段索引（按时间排序）

    外键约束：
    - agent_id → agents.id（级联删除）
    - 删除 Agent 时，自动删除所有关联的 Run
    """

    __tablename__ = "runs"

    # 主键
    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="Run ID（UUID）")

    # 外键
    agent_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agents.id", ondelete="CASCADE"),  # 级联删除
        nullable=False,
        comment="关联的 Agent ID",
    )

    # 业务字段
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", comment="Run 状态"
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="创建时间"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="开始执行时间"
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="完成时间"
    )

    # 错误信息
    error: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")

    # 关系（多对一：多个 Run 属于一个 Agent）
    # back_populates: 双向关系（AgentModel.runs）
    agent: Mapped["AgentModel"] = relationship("AgentModel", back_populates="runs")

    # 关系（一对多：一个 Run 有多个 Task）
    # cascade="all, delete-orphan": 删除 Run 时级联删除所有 Task
    # back_populates: 双向关系（TaskModel.run）
    tasks: Mapped[list["TaskModel"]] = relationship(
        "TaskModel", back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )

    # 索引
    __table_args__ = (
        Index("idx_runs_agent_id", "agent_id"),  # 查询 Agent 的所有 Run
        Index("idx_runs_status", "status"),  # 查询特定状态的 Run
        Index("idx_runs_created_at", "created_at"),  # 按时间排序
    )

    def __repr__(self) -> str:
        return f"<RunModel(id={self.id}, agent_id={self.agent_id}, status={self.status})>"


class TaskModel(Base):
    """Task ORM 模型

    表名：tasks

    字段说明：
    - id: 主键（UUID 字符串，36 字符）
    - run_id: 外键（关联 Run，级联删除）
    - name: Task 名称（255 字符）
    - input_data: 输入数据（JSON 格式）
    - output_data: 输出数据（JSON 格式，可选）
    - status: Task 状态（pending/running/succeeded/failed，20 字符）
    - error: 错误信息（可选，Text）
    - retry_count: 重试次数（整数，默认 0）
    - created_at: 创建时间（自动设置）
    - started_at: 开始执行时间（可选）
    - finished_at: 完成时间（可选）
    - events: TaskEvent 列表（JSON 格式，存储为 JSON 数组）

    关系：
    - run: 多对一关系（多个 Task 属于一个 Run）

    索引：
    - idx_tasks_run_id: run_id 字段索引（查询 Run 的所有 Task）
    - idx_tasks_status: status 字段索引（查询特定状态的 Task）
    - idx_tasks_created_at: created_at 字段索引（按时间排序）

    外键约束：
    - run_id → runs.id（级联删除）
    - 删除 Run 时，自动删除所有关联的 Task

    TaskEvent 的持久化：
    - TaskEvent 是值对象，属于 Task 聚合
    - 使用 JSON 字段存储 TaskEvent 列表
    - 格式：[{"timestamp": "2025-11-16T10:00:00Z", "message": "事件消息"}, ...]
    - 为什么用 JSON？
      1. TaskEvent 是值对象，没有独立的生命周期
      2. TaskEvent 总是和 Task 一起查询，不需要单独查询
      3. 简化数据库设计，避免额外的表和 JOIN
      4. 符合聚合的完整性（Task 和 TaskEvent 作为一个整体）
    """

    __tablename__ = "tasks"

    # 主键
    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="Task ID（UUID）")

    # 外键
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("runs.id", ondelete="CASCADE"),  # 级联删除
        nullable=False,
        comment="关联的 Run ID",
    )

    # 业务字段
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Task 名称")
    input_data: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="输入数据（JSON 格式）"
    )
    output_data: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="输出数据（JSON 格式）"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", comment="Task 状态"
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="重试次数")

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="创建时间"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="开始执行时间"
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="完成时间"
    )

    # TaskEvent 列表（JSON 格式）
    # 存储格式：[{"timestamp": "2025-11-16T10:00:00Z", "message": "事件消息"}, ...]
    events: Mapped[list[dict] | None] = mapped_column(
        JSON, nullable=True, default=list, comment="TaskEvent 列表（JSON 格式）"
    )

    # 关系（多对一：多个 Task 属于一个 Run）
    # back_populates: 双向关系（RunModel.tasks）
    run: Mapped["RunModel"] = relationship("RunModel", back_populates="tasks")

    # 索引
    __table_args__ = (
        Index("idx_tasks_run_id", "run_id"),  # 查询 Run 的所有 Task
        Index("idx_tasks_status", "status"),  # 查询特定状态的 Task
        Index("idx_tasks_created_at", "created_at"),  # 按时间排序
    )

    def __repr__(self) -> str:
        return f"<TaskModel(id={self.id}, run_id={self.run_id}, name={self.name}, status={self.status})>"
