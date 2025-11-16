"""CreateAgentUseCase - 创建 Agent 用例

业务场景：
用户输入"起点 + 目的"，系统创建一个 Agent

职责：
1. 接收输入参数（start, goal, name）
2. 调用 Agent.create() 创建领域实体
3. 调用 Repository.save() 持久化实体
4. 返回创建的 Agent

第一性原则：
- 用例是业务逻辑的编排者，不包含业务规则
- 业务规则在 Domain 层（Agent.create() 中）
- 用例只负责协调各个组件

设计模式：
- Command 模式：用例是一个命令，封装了一次业务操作
- Dependency Injection：通过构造函数注入 Repository

为什么不在用例中验证输入？
- 验证逻辑在 Domain 层（Agent.create()）
- 用例只负责编排，不重复验证
- 遵循 DRY 原则（Don't Repeat Yourself）
"""

from dataclasses import dataclass

from src.domain.entities.agent import Agent
from src.domain.ports.agent_repository import AgentRepository


@dataclass
class CreateAgentInput:
    """创建 Agent 的输入参数

    为什么使用 dataclass？
    1. 类型安全：明确定义输入参数类型
    2. 不可变性：使用 frozen=False 允许修改（如果需要）
    3. 自动生成 __init__、__repr__ 等方法
    4. IDE 友好：自动补全和类型检查

    为什么不使用 Pydantic？
    - Pydantic 是 API 层的 DTO（Data Transfer Object）
    - 这里是 Application 层的输入对象
    - 保持层次分离：API DTO → Application Input → Domain Entity

    属性说明：
    - start: 任务起点描述（必填）
    - goal: 任务目的描述（必填）
    - name: Agent 名称（可选，不提供则自动生成）
    """

    start: str
    goal: str
    name: str | None = None


class CreateAgentUseCase:
    """创建 Agent 用例

    职责：
    1. 接收 CreateAgentInput 输入
    2. 调用 Agent.create() 创建领域实体
    3. 调用 Repository.save() 持久化实体
    4. 返回创建的 Agent

    依赖：
    - AgentRepository: Agent 仓储接口（通过构造函数注入）

    为什么使用依赖注入？
    1. 解耦：用例不依赖具体的 Repository 实现
    2. 可测试性：测试时可以注入 Mock Repository
    3. 灵活性：可以轻松切换不同的 Repository 实现

    为什么不使用异步？
    - 当前简化实现，使用同步方法
    - 未来可以改为异步（async def execute）
    - Repository 接口也需要改为异步
    """

    def __init__(self, agent_repository: AgentRepository):
        """初始化用例

        参数：
            agent_repository: Agent 仓储接口

        为什么通过构造函数注入？
        - 依赖注入：由外部管理依赖
        - 可测试性：测试时可以注入 Mock
        - 明确依赖：构造函数清晰表达依赖关系
        """
        self.agent_repository = agent_repository

    def execute(self, input_data: CreateAgentInput) -> Agent:
        """执行用例：创建 Agent

        业务流程：
        1. 调用 Agent.create() 创建领域实体
           - 验证输入（start、goal 不能为空）
           - 生成 ID、设置默认值
           - 返回 Agent 实体
        2. 调用 Repository.save() 持久化实体
           - 保存到数据库
           - 处理数据库异常
        3. 返回创建的 Agent

        参数：
            input_data: 创建 Agent 的输入参数

        返回：
            创建的 Agent 实体

        异常：
            DomainError: 当输入不符合业务规则时（由 Agent.create() 抛出）
            Exception: 当数据库操作失败时（由 Repository.save() 抛出）

        为什么不捕获异常？
        - 异常应该向上传播，由上层（API 层）统一处理
        - 用例不应该关心如何处理异常（关注点分离）
        - 保持用例简单，只负责业务逻辑编排

        示例：
        >>> repo = SQLAlchemyAgentRepository(session)
        >>> use_case = CreateAgentUseCase(agent_repository=repo)
        >>> input_data = CreateAgentInput(
        ...     start="我有一个 CSV 文件",
        ...     goal="分析销售数据",
        ...     name="销售分析 Agent"
        ... )
        >>> agent = use_case.execute(input_data)
        >>> print(agent.id)  # UUID
        >>> print(agent.status)  # "active"
        """
        # 步骤 1: 创建领域实体
        # 为什么调用 Agent.create() 而不是 Agent()?
        # - Agent.create() 是工厂方法，封装了创建逻辑
        # - 自动生成 ID、设置默认值、验证业务规则
        # - 符合 DDD 聚合根创建模式
        agent = Agent.create(
            start=input_data.start,
            goal=input_data.goal,
            name=input_data.name,
        )

        # 步骤 2: 持久化实体
        # 为什么调用 save() 而不是 create()?
        # - Repository 模式使用 save() 统一处理新增和更新
        # - 由 Repository 判断是新增还是更新（通过 ID 查询）
        # - 符合 Repository 模式的最佳实践
        self.agent_repository.save(agent)

        # 步骤 3: 返回创建的 Agent
        # 为什么返回 Agent 而不是 ID？
        # - 调用者可能需要 Agent 的其他信息（如 created_at）
        # - 避免调用者再次查询数据库
        # - 符合 CQRS 模式（Command 返回结果）
        return agent
