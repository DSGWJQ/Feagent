"""Agent DTO（Data Transfer Objects）

定义 Agent 相关的请求和响应模型
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskResponse(BaseModel):
    """Task 响应 DTO

    业务场景：API 返回 Task 信息给前端

    字段：
    - id: Task ID
    - agent_id: 关联的 Agent ID
    - name: 任务名称
    - description: 任务描述（可选）
    - status: 任务状态（pending/running/succeeded/failed）
    - created_at: 创建时间

    为什么需要 TaskResponse？
    1. 前端需要展示生成的工作流（任务列表）
    2. 用户可以查看每个任务的详情
    3. 便于前端渲染任务卡片

    示例：
    >>> from src.domain.entities import Task
    >>> task = Task.create(agent_id="agent-123", name="读取 CSV 文件")
    >>> response = TaskResponse.from_entity(task)
    >>> print(response.name)
    读取 CSV 文件
    """

    id: str
    agent_id: str
    name: str
    description: str | None
    status: str
    created_at: datetime

    @classmethod
    def from_entity(cls, task) -> "TaskResponse":
        """从 Domain 实体创建响应 DTO

        参数：
            task: Task 实体

        返回：
            TaskResponse DTO
        """
        return cls(
            id=task.id,
            agent_id=task.agent_id,
            name=task.name,
            description=task.description,
            status=task.status.value,  # TaskStatus enum → str
            created_at=task.created_at,
        )

    model_config = ConfigDict(
        from_attributes=True,
    )


class CreateAgentRequest(BaseModel):
    """创建 Agent 请求 DTO

    业务场景：用户通过 API 创建 Agent

    字段：
    - start: 任务起点描述（必填，10-500 字符）
    - goal: 任务目的描述（必填，10-500 字符）
    - name: Agent 名称（可选，不提供时自动生成，最大 100 字符）

    验证规则：
    - start 和 goal 不能为空或纯空格
    - start 和 goal 长度在 10-500 字符之间
    - name 最大长度 100 字符
    - 自动去除首尾空格

    为什么使用 Pydantic？
    1. 自动数据验证：类型检查、必填字段检查、长度限制
    2. 自动文档生成：FastAPI 自动生成 OpenAPI 文档
    3. IDE 友好：类型提示、自动补全
    4. 性能优秀：Pydantic v2 使用 Rust 实现，性能极佳

    示例：
    >>> request = CreateAgentRequest(
    ...     start="我有一个 CSV 文件，包含过去一年的销售数据",
    ...     goal="分析销售数据，找出销售趋势和热门产品，生成可视化报告",
    ...     name="销售分析 Agent"
    ... )
    >>> print(request.start)
    我有一个 CSV 文件，包含过去一年的销售数据
    """

    # 注意：这里不使用 min_length 和 max_length
    # 因为 Pydantic 的验证在 strip() 之前执行
    # 我们在 field_validator 中手动验证长度
    start: str = Field(
        ...,
        description="任务起点描述：描述当前的状态或拥有的资源（10-500 字符）",
        examples=["我有一个 CSV 文件，包含过去一年的销售数据"],
    )
    goal: str = Field(
        ...,
        description="任务目的描述：描述期望达到的目标或结果（10-500 字符）",
        examples=["分析销售数据，找出销售趋势和热门产品，生成可视化报告"],
    )
    name: str | None = Field(
        default=None,
        description="Agent 名称（可选，不提供时自动生成，最大 100 字符）",
        examples=["销售分析 Agent"],
    )

    @field_validator("start", "goal")
    @classmethod
    def validate_not_empty(cls, v: str, info) -> str:
        """验证字段不能为空或纯空格

        为什么需要这个验证器？
        - Pydantic 的 min_length 会在 strip 之前检查
        - 我们需要先 strip，再检查长度
        - 业务规则：start 和 goal 必须有实际内容
        - 提前验证，避免传递到 Domain 层

        参数：
            v: 字段值
            info: 字段信息（包含字段名）

        返回：
            去除首尾空格后的字符串

        异常：
            ValueError: 当字段为空或纯空格时
        """
        # 获取字段名
        field_name = info.field_name
        field_name_cn = "起点描述" if field_name == "start" else "目的描述"

        # 去除首尾空格
        v = v.strip()

        # 验证不能为空
        if not v:
            raise ValueError(f"{field_name_cn}不能为空")

        # 验证长度（在 strip 之后）
        if len(v) < 10:
            raise ValueError(f"{field_name_cn}至少需要 10 个字符，当前只有 {len(v)} 个字符")

        if len(v) > 500:
            raise ValueError(f"{field_name_cn}最多 500 个字符，当前有 {len(v)} 个字符")

        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        """验证 name 字段

        规则：
        - name 是可选的（None 表示自动生成）
        - 如果提供了 name，去除首尾空格
        - 如果 name 为空字符串或纯空格，视为 None
        - name 最大长度 100 字符

        为什么这样处理？
        - 前端可能发送空字符串表示"不提供 name"
        - 统一处理为 None，由 Domain 层自动生成
        """
        if v is None:
            return None

        # 去除首尾空格
        v = v.strip()

        # 空字符串视为 None
        if not v:
            return None

        # 验证长度
        if len(v) > 100:
            raise ValueError(f"Agent 名称最多 100 个字符，当前有 {len(v)} 个字符")

        return v


class AgentResponse(BaseModel):
    """Agent 响应 DTO

    业务场景：API 返回 Agent 信息给前端

    字段：
    - id: Agent ID
    - start: 任务起点描述
    - goal: 任务目的描述
    - name: Agent 名称
    - status: Agent 状态（active/archived）
    - created_at: 创建时间
    - tasks: 关联的 Tasks（可选，用于展示生成的工作流）

    为什么需要单独的响应 DTO？
    1. 关注点分离：响应结构可能与 Domain 实体不同
    2. 版本兼容：可以添加/删除字段而不影响 Domain 层
    3. 安全性：只暴露需要的字段，隐藏敏感信息
    4. 文档生成：清晰的 API 文档

    为什么添加 tasks 字段？
    - MVP 功能：用户创建 Agent 后，立即看到生成的工作流
    - 前端可以直接展示任务列表，无需额外请求

    示例：
    >>> from src.domain.entities import Agent
    >>> agent = Agent.create(start="起点", goal="目的")
    >>> response = AgentResponse.from_entity(agent)
    >>> print(response.id)
    agent-123
    """

    id: str
    start: str
    goal: str
    name: str
    status: str
    created_at: datetime
    tasks: list[TaskResponse] = Field(default_factory=list)

    @classmethod
    def from_entity(cls, agent, tasks: list | None = None) -> "AgentResponse":
        """从 Domain 实体创建响应 DTO

        这是 Assembler 模式的实现：
        - Domain Entity → DTO
        - 负责数据转换和映射

        为什么需要这个方法？
        1. 封装转换逻辑：集中管理 Entity → DTO 的转换
        2. 类型安全：明确的转换接口
        3. 易于维护：转换逻辑集中在一处
        4. 解耦：Domain 层不需要知道 DTO 的存在

        参数：
            agent: Agent 实体
            tasks: Task 实体列表（可选）

        返回：
            AgentResponse DTO

        示例：
        >>> agent = Agent.create(start="起点", goal="目的")
        >>> response = AgentResponse.from_entity(agent)
        >>> # 或者包含 tasks
        >>> response = AgentResponse.from_entity(agent, tasks=[task1, task2])
        """
        task_responses = []
        if tasks:
            task_responses = [TaskResponse.from_entity(task) for task in tasks]

        return cls(
            id=agent.id,
            start=agent.start,
            goal=agent.goal,
            name=agent.name,
            status=agent.status,
            created_at=agent.created_at,
            tasks=task_responses,
        )

    # Pydantic v2 配置
    # 注意：Pydantic v2 会自动将 datetime 序列化为 ISO 8601 格式
    # 不需要手动配置 json_encoders
    model_config = ConfigDict(
        # 允许从 ORM 模型创建（未来可能需要）
        from_attributes=True,
    )
