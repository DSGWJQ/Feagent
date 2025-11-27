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

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.base import Base


class UserModel(Base):
    """User ORM 模型

    表名：users

    字段说明：
    - id: 主键（UUID 字符串，36 字符）
    - github_id: GitHub用户ID（唯一，整数）
    - github_username: GitHub用户名（255 字符）
    - email: 用户邮箱（唯一，255 字符）
    - name: 用户姓名（255 字符，可选）
    - github_avatar_url: GitHub头像URL（Text，可选）
    - github_profile_url: GitHub个人主页URL（Text，可选）
    - is_active: 是否激活（布尔值，默认True）
    - role: 用户角色（20 字符，默认user）
    - created_at: 创建时间（自动设置）
    - updated_at: 更新时间（可选）
    - last_login_at: 最后登录时间（可选）

    关系：
    - workflows: 一对多关系（一个User有多个Workflow）
    - tools: 一对多关系（一个User有多个Tool）

    索引：
    - idx_users_github_id: github_id字段索引（唯一，快速查找）
    - idx_users_email: email字段索引（唯一，快速查找）
    - idx_users_created_at: created_at字段索引（按时间排序）
    """

    __tablename__ = "users"

    # 主键
    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="User ID（UUID）")

    # GitHub OAuth信息
    github_id: Mapped[int] = mapped_column(
        Integer, nullable=False, unique=True, comment="GitHub用户ID"
    )
    github_username: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="GitHub用户名"
    )
    github_avatar_url: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="GitHub头像URL"
    )
    github_profile_url: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="GitHub个人主页"
    )

    # 用户基本信息
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, comment="用户邮箱")
    name: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="用户姓名")

    # 账户状态
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否激活"
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user", comment="用户角色（user/admin）"
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="创建时间"
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, onupdate=datetime.now, comment="更新时间"
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最后登录时间"
    )

    # 关系（一对多：一个User有多个Workflow）
    workflows: Mapped[list["WorkflowModel"]] = relationship(
        "WorkflowModel", back_populates="user", cascade="all, delete-orphan"
    )

    # 关系（一对多：一个User有多个Tool）
    tools: Mapped[list["ToolModel"]] = relationship(
        "ToolModel", back_populates="user", cascade="all, delete-orphan"
    )

    # 索引
    __table_args__ = (
        Index("idx_users_github_id", "github_id", unique=True),  # 唯一索引
        Index("idx_users_email", "email", unique=True),  # 唯一索引
        Index("idx_users_created_at", "created_at"),  # 按时间排序
    )

    def __repr__(self) -> str:
        return (
            f"<UserModel(id={self.id}, github_username={self.github_username}, email={self.email})>"
        )


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

    # 关系（一对多：一个 Agent 有多个 Task）
    # cascade="all, delete-orphan": 删除 Agent 时级联删除所有 Task
    # back_populates: 双向关系（TaskModel.agent）
    tasks: Mapped[list["TaskModel"]] = relationship(
        "TaskModel", back_populates="agent", cascade="all, delete-orphan", lazy="selectin"
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
    - agent_id: 外键（关联 Agent，级联删除）
    - run_id: 外键（关联 Run，级联删除，可选）
    - name: Task 名称（255 字符）
    - description: Task 描述（Text，可选）
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
    - agent: 多对一关系（多个 Task 属于一个 Agent）
    - run: 多对一关系（多个 Task 属于一个 Run，可选）

    索引：
    - idx_tasks_agent_id: agent_id 字段索引（查询 Agent 的所有 Task）
    - idx_tasks_run_id: run_id 字段索引（查询 Run 的所有 Task）
    - idx_tasks_status: status 字段索引（查询特定状态的 Task）
    - idx_tasks_created_at: created_at 字段索引（按时间排序）

    外键约束：
    - agent_id → agents.id（级联删除）
    - run_id → runs.id（级联删除，可选）
    - 删除 Agent 时，自动删除所有关联的 Task
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

    为什么添加 agent_id？
    - Task 可以在创建 Agent 时生成（作为计划任务）
    - Task 也可以在执行 Run 时创建（作为执行步骤）
    - agent_id 表示这个 Task 属于哪个 Agent

    为什么 run_id 改为可选？
    - 创建 Agent 时生成的 Task，run_id 为 None（还没执行）
    - 执行 Run 时，设置 run_id（表示在哪次执行中运行）

    为什么添加 description？
    - name 是简短的任务名称（如"读取 CSV 文件"）
    - description 是详细的任务描述（如"使用 pandas 读取 CSV 文件到 DataFrame"）
    - 提供更好的用户体验和可读性
    """

    __tablename__ = "tasks"

    # 主键
    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="Task ID（UUID）")

    # 外键
    agent_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agents.id", ondelete="CASCADE"),  # 级联删除
        nullable=False,
        comment="关联的 Agent ID",
    )
    run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("runs.id", ondelete="CASCADE"),  # 级联删除
        nullable=True,  # 可选
        comment="关联的 Run ID（可选）",
    )

    # 业务字段
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="Task 名称")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Task 描述")
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

    # 关系（多对一：多个 Task 属于一个 Agent）
    # back_populates: 双向关系（AgentModel.tasks）
    agent: Mapped["AgentModel"] = relationship("AgentModel", back_populates="tasks")

    # 关系（多对一：多个 Task 属于一个 Run，可选）
    # back_populates: 双向关系（RunModel.tasks）
    run: Mapped["RunModel"] = relationship("RunModel", back_populates="tasks")

    # 索引
    __table_args__ = (
        Index("idx_tasks_agent_id", "agent_id"),  # 查询 Agent 的所有 Task
        Index("idx_tasks_run_id", "run_id"),  # 查询 Run 的所有 Task
        Index("idx_tasks_status", "status"),  # 查询特定状态的 Task
        Index("idx_tasks_created_at", "created_at"),  # 按时间排序
    )

    def __repr__(self) -> str:
        return f"<TaskModel(id={self.id}, run_id={self.run_id}, name={self.name}, status={self.status})>"


class WorkflowModel(Base):
    """Workflow ORM 模型

    表名：workflows

    字段说明：
    - id: 主键（UUID 字符串，wf_ 前缀）
    - name: 工作流名称（255 字符）
    - description: 工作流描述（Text，无长度限制）
    - status: 工作流状态（draft/published/archived，20 字符）
    - created_at: 创建时间（自动设置）
    - updated_at: 更新时间（自动更新）

    关系：
    - nodes: 一对多关系（一个 Workflow 有多个 Node）
    - edges: 一对多关系（一个 Workflow 有多个 Edge）

    索引：
    - idx_workflows_status: status 字段索引（查询特定状态的工作流）
    - idx_workflows_created_at: created_at 字段索引（按时间排序）
    """

    __tablename__ = "workflows"

    # 主键
    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="Workflow ID（wf_ 前缀）")

    # 外键（用户关联）
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,  # 兼容现有数据和未登录用户
        comment="创建者ID",
    )

    # 业务字段
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="工作流名称")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="工作流描述")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", comment="工作流状态"
    )
    # V2新增：工作流来源追踪
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="feagent", comment="工作流来源（feagent/coze/user等）"
    )
    source_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="原始来源的ID（如Coze workflow_id）"
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )

    # 关系（多对一：多个Workflow属于一个User）
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="workflows")

    # 关系（一对多：一个 Workflow 有多个 Node）
    # cascade="all, delete-orphan": 删除 Workflow 时级联删除所有 Node
    # back_populates: 双向关系（NodeModel.workflow）
    nodes: Mapped[list["NodeModel"]] = relationship(
        "NodeModel", back_populates="workflow", cascade="all, delete-orphan", lazy="selectin"
    )

    # 关系（一对多：一个 Workflow 有多个 Edge）
    # cascade="all, delete-orphan": 删除 Workflow 时级联删除所有 Edge
    # back_populates: 双向关系（EdgeModel.workflow）
    edges: Mapped[list["EdgeModel"]] = relationship(
        "EdgeModel", back_populates="workflow", cascade="all, delete-orphan", lazy="selectin"
    )

    # 索引
    __table_args__ = (
        Index("idx_workflows_status", "status"),  # 查询特定状态的工作流
        Index("idx_workflows_created_at", "created_at"),  # 按时间排序
    )

    def __repr__(self) -> str:
        return f"<WorkflowModel(id={self.id}, name={self.name}, status={self.status})>"


class NodeModel(Base):
    """Node ORM 模型

    表名：nodes

    字段说明：
    - id: 主键（UUID 字符串，node_ 前缀）
    - workflow_id: 外键（关联 Workflow）
    - type: 节点类型（http/transform/database 等，20 字符）
    - name: 节点名称（255 字符）
    - config: 节点配置（JSON 格式）
    - position_x: 节点 X 坐标（浮点数）
    - position_y: 节点 Y 坐标（浮点数）

    关系：
    - workflow: 多对一关系（多个 Node 属于一个 Workflow）

    索引：
    - idx_nodes_workflow_id: workflow_id 字段索引（查询 Workflow 的所有 Node）
    """

    __tablename__ = "nodes"

    # 主键
    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="Node ID（node_ 前缀）")

    # 外键
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        comment="Workflow ID",
    )

    # 业务字段
    type: Mapped[str] = mapped_column(String(20), nullable=False, comment="节点类型")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="节点名称")
    config: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, comment="节点配置（JSON）"
    )
    position_x: Mapped[float] = mapped_column(nullable=False, comment="节点 X 坐标")
    position_y: Mapped[float] = mapped_column(nullable=False, comment="节点 Y 坐标")

    # 关系（多对一：多个 Node 属于一个 Workflow）
    # back_populates: 双向关系（WorkflowModel.nodes）
    workflow: Mapped["WorkflowModel"] = relationship("WorkflowModel", back_populates="nodes")

    # 索引
    __table_args__ = (Index("idx_nodes_workflow_id", "workflow_id"),)  # 查询 Workflow 的所有 Node

    def __repr__(self) -> str:
        return f"<NodeModel(id={self.id}, workflow_id={self.workflow_id}, name={self.name}, type={self.type})>"


class EdgeModel(Base):
    """Edge ORM 模型

    表名：edges

    字段说明：
    - id: 主键（UUID 字符串，edge_ 前缀）
    - workflow_id: 外键（关联 Workflow）
    - source_node_id: 源节点 ID（36 字符）
    - target_node_id: 目标节点 ID（36 字符）
    - condition: 条件表达式（Text，可选）

    关系：
    - workflow: 多对一关系（多个 Edge 属于一个 Workflow）

    索引：
    - idx_edges_workflow_id: workflow_id 字段索引（查询 Workflow 的所有 Edge）
    """

    __tablename__ = "edges"

    # 主键
    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="Edge ID（edge_ 前缀）")

    # 外键
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        comment="Workflow ID",
    )

    # 业务字段
    source_node_id: Mapped[str] = mapped_column(String(36), nullable=False, comment="源节点 ID")
    target_node_id: Mapped[str] = mapped_column(String(36), nullable=False, comment="目标节点 ID")
    condition: Mapped[str | None] = mapped_column(Text, nullable=True, comment="条件表达式")

    # 关系（多对一：多个 Edge 属于一个 Workflow）
    # back_populates: 双向关系（WorkflowModel.edges）
    workflow: Mapped["WorkflowModel"] = relationship("WorkflowModel", back_populates="edges")

    # 索引
    __table_args__ = (Index("idx_edges_workflow_id", "workflow_id"),)  # 查询 Workflow 的所有 Edge

    def __repr__(self) -> str:
        return f"<EdgeModel(id={self.id}, workflow_id={self.workflow_id}, source={self.source_node_id}, target={self.target_node_id})>"


class ToolModel(Base):
    """Tool ORM 模型

    表名：tools

    字段说明：
    - id: 主键（tool_ 前缀）
    - name: 工具名称（255 字符）
    - description: 工具描述（Text）
    - category: 工具分类（http, database, file等，50 字符）
    - status: 工具状态（draft, testing, published, deprecated，20 字符）
    - version: 语义化版本号（50 字符）
    - parameters: 工具参数列表（JSON 格式）
    - returns: 返回值 schema（JSON 格式）
    - implementation_type: 实现类型（builtin, http, javascript, python，50 字符）
    - implementation_config: 实现配置（JSON 格式）
    - author: 工具创建者（255 字符）
    - tags: 工具标签（JSON 格式的字符串列表）
    - icon: 工具图标 URL（Text，可选）
    - usage_count: 使用次数（整数，默认 0）
    - last_used_at: 最后使用时间（可选）
    - created_at: 创建时间（自动设置）
    - updated_at: 更新时间（可选）
    - published_at: 发布时间（可选）

    参数持久化说明：
    - ToolParameter 是值对象，属于 Tool 聚合
    - 使用 JSON 字段存储参数列表
    - 格式：[{"name": "url", "type": "string", "description": "...", "required": true, ...}, ...]

    索引：
    - idx_tools_status: status 字段索引（查询特定状态的工具）
    - idx_tools_category: category 字段索引（按分类查询）
    - idx_tools_created_at: created_at 字段索引（按时间排序）
    """

    __tablename__ = "tools"

    # 主键
    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="Tool ID（tool_ 前缀）")

    # 外键（用户关联）
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,  # 兼容现有数据和未登录用户
        comment="创建者ID",
    )

    # 业务字段
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="工具名称")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="工具描述")
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="工具分类（http, database, file等）"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", comment="工具状态"
    )
    version: Mapped[str] = mapped_column(
        String(50), nullable=False, default="0.1.0", comment="版本号"
    )

    # 工具定义
    parameters: Mapped[list[dict] | None] = mapped_column(
        JSON, nullable=True, default=list, comment="参数列表（JSON）"
    )
    returns: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict, comment="返回值 schema（JSON）"
    )

    # 实现方式
    implementation_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="builtin", comment="实现类型"
    )
    implementation_config: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict, comment="实现配置（JSON）"
    )

    # 元数据
    author: Mapped[str] = mapped_column(String(255), nullable=False, default="", comment="创建者")
    tags: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True, default=list, comment="标签列表（JSON）"
    )
    icon: Mapped[str | None] = mapped_column(Text, nullable=True, comment="图标 URL")

    # 使用统计
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="使用次数")
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最后使用时间"
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="创建时间"
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="更新时间")
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="发布时间"
    )

    # 关系（多对一：多个Tool属于一个User）
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="tools")

    # 索引
    __table_args__ = (
        Index("idx_tools_status", "status"),  # 查询特定状态的工具
        Index("idx_tools_category", "category"),  # 按分类查询
        Index("idx_tools_created_at", "created_at"),  # 按时间排序
    )

    def __repr__(self) -> str:
        return f"<ToolModel(id={self.id}, name={self.name}, status={self.status})>"


class LLMProviderModel(Base):
    """LLMProvider ORM 模型

    表名：llm_providers

    字段说明：
    - id: 主键（llm_provider_ 前缀）
    - name: 提供商标识（openai, deepseek, qwen等，50 字符）
    - display_name: 显示名称（255 字符）
    - api_base: API 基础 URL（Text）
    - api_key: API 密钥（Text，可选）
    - models: 支持的模型列表（JSON 格式的字符串列表）
    - enabled: 是否启用（布尔值，默认 True）
    - config: 额外配置（JSON 格式）
    - created_at: 创建时间（自动设置）
    - updated_at: 更新时间（可选）

    索引：
    - idx_llm_providers_name: name 字段索引（按名称查询）
    - idx_llm_providers_enabled: enabled 字段索引（查询已启用的提供商）
    """

    __tablename__ = "llm_providers"

    # 主键
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, comment="LLMProvider ID（llm_provider_ 前缀）"
    )

    # 业务字段
    name: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, comment="提供商标识（openai, deepseek等）"
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="显示名称")
    api_base: Mapped[str] = mapped_column(Text, nullable=False, comment="API 基础 URL")
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True, comment="API 密钥")
    models: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=False, default=list, comment="支持的模型列表（JSON）"
    )
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True, comment="是否启用")
    config: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict, comment="额外配置（JSON）"
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="创建时间"
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="更新时间")

    # 索引
    __table_args__ = (
        Index("idx_llm_providers_name", "name"),  # 按名称查询
        Index("idx_llm_providers_enabled", "enabled"),  # 查询已启用的提供商
    )

    def __repr__(self) -> str:
        return f"<LLMProviderModel(id={self.id}, name={self.name}, enabled={self.enabled})>"


class ScheduledWorkflowModel(Base):
    """ScheduledWorkflow ORM 模型

    表名：scheduled_workflows

    字段说明：
    - id: 主键（scheduled_workflow_ 前缀）
    - workflow_id: 关联的工作流 ID（外键）
    - cron_expression: Cron 表达式（255 字符）
    - status: 定时任务状态（active/disabled/paused，20 字符）
    - max_retries: 最大重试次数（整数）
    - consecutive_failures: 连续失败次数（整数）
    - next_execution_time: 下一次执行时间（可选）
    - last_execution_time: 最后执行时间（可选）
    - created_at: 创建时间（自动设置）
    - updated_at: 更新时间（可选）

    关系：
    - workflow: 多对一关系（一个工作流有多个定时任务）

    索引：
    - idx_scheduled_workflows_workflow_id: workflow_id 字段索引（查询工作流的定时任务）
    - idx_scheduled_workflows_status: status 字段索引（查询活跃的定时任务）
    - idx_scheduled_workflows_created_at: created_at 字段索引（按时间排序）
    """

    __tablename__ = "scheduled_workflows"

    # 主键
    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="ScheduledWorkflow ID")

    # 外键和关系
    workflow_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联的工作流 ID",
    )

    # 业务字段
    cron_expression: Mapped[str] = mapped_column(String(255), nullable=False, comment="Cron 表达式")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", comment="定时任务状态"
    )
    max_retries: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, comment="最大重试次数"
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="连续失败次数"
    )

    # 执行时间
    last_execution_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最后执行时间"
    )
    last_execution_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="最后执行状态"
    )
    last_error_message: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="最后执行的错误消息"
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, comment="创建时间"
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="更新时间")

    # 索引
    __table_args__ = (
        Index("idx_scheduled_workflows_workflow_id", "workflow_id"),
        Index("idx_scheduled_workflows_status", "status"),
        Index("idx_scheduled_workflows_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ScheduledWorkflowModel(id={self.id}, workflow_id={self.workflow_id}, status={self.status})>"
