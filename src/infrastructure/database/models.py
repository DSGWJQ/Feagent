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

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
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
        "RunModel", back_populates="agent", cascade="all, delete-orphan"
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

    # 索引
    __table_args__ = (
        Index("idx_runs_agent_id", "agent_id"),  # 查询 Agent 的所有 Run
        Index("idx_runs_status", "status"),  # 查询特定状态的 Run
        Index("idx_runs_created_at", "created_at"),  # 按时间排序
    )

    def __repr__(self) -> str:
        return f"<RunModel(id={self.id}, agent_id={self.agent_id}, status={self.status})>"
