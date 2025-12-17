"""ExecuteRunUseCase - 执行 Run 用例

业务场景：
用户触发 Agent 执行，系统创建一个 Run 并执行

职责：
1. 验证 Agent 是否存在
2. 创建 Run 实体
3. 启动 Run（PENDING → RUNNING）
4. 执行 LangGraph 任务（内部多步推理与工具调用）
5. 完成 Run（RUNNING → SUCCEEDED/FAILED）
6. 持久化状态变化

第一性原则：
- 用例是业务逻辑的编排者，不包含业务规则
- 业务规则在 Domain 层（Run.start(), Run.succeed(), Run.fail()）
- 用例负责协调各个组件和管理事务边界

设计模式：
- Command 模式：用例是一个命令，封装了一次业务操作
- Dependency Injection：通过构造函数注入 Repository

为什么需要检查 Agent 是否存在？
- 业务规则：Run 必须属于一个存在的 Agent
- 数据完整性：防止创建孤儿 Run
- 用户体验：及早发现错误，提供清晰的错误信息

LangGraph 集成：
- 使用 StateGraph 执行器进行多步推理
- 不再显式创建 Task 实体（LangGraph 内部处理）
- 从 Agent 的 start 和 goal 构造初始消息
- 使用三层错误检测策略：显式信号、空结果、启发式匹配
"""

from dataclasses import dataclass

from langchain_core.messages import HumanMessage

from src.domain.entities.run import Run
from src.domain.exceptions import DomainError
from src.domain.ports.agent_repository import AgentRepository
from src.domain.ports.run_repository import RunRepository
from src.infrastructure.lc_adapters.agents.langgraph_task_executor import (
    AgentState,
    create_langgraph_task_executor,
)
from src.infrastructure.lc_adapters.agents.task_executor_adapter import extract_final_answer


@dataclass
class ExecuteRunInput:
    """执行 Run 的输入参数

    为什么使用 dataclass？
    1. 类型安全：明确定义输入参数类型
    2. 自动生成 __init__、__repr__ 等方法
    3. IDE 友好：自动补全和类型检查

    属性说明：
    - agent_id: 要执行的 Agent ID（必填）
    """

    agent_id: str


class ExecuteRunUseCase:
    """执行 Run 用例

    职责：
    1. 验证 Agent 是否存在
    2. 创建 Run 实体
    3. 启动 Run
    4. 执行 LangGraph 任务（多步推理与工具调用）
    5. 完成 Run
    6. 持久化状态变化

    依赖：
    - AgentRepository: Agent 仓储接口
    - RunRepository: Run 仓储接口

    为什么不再需要 TaskRepository？
    - LangGraph 内部处理多步推理，不需要显式创建 Task 实体
    - Run 成为唯一的执行跟踪单元
    - 简化了用例的职责和依赖关系
    """

    def __init__(
        self,
        agent_repository: AgentRepository,
        run_repository: RunRepository,
    ):
        """初始化用例

        参数：
            agent_repository: Agent 仓储接口
            run_repository: Run 仓储接口

        为什么通过构造函数注入？
        - 依赖注入：由外部管理依赖
        - 可测试性：测试时可以注入 Mock
        - 明确依赖：构造函数清晰表达依赖关系
        """
        self.agent_repository = agent_repository
        self.run_repository = run_repository

    def execute(self, input_data: ExecuteRunInput) -> Run:
        """执行用例：创建并执行 Run

        业务流程：
        1. 验证输入（agent_id 不能为空）
        2. 检查 Agent 是否存在
        3. 创建 Run 实体
        4. 保存 Run（PENDING 状态）
        5. 启动 Run（PENDING → RUNNING）
        6. 保存状态变化
        7. 执行业务逻辑（当前简化为直接成功）
        8. 完成 Run（RUNNING → SUCCEEDED）
        9. 保存最终状态
        10. 返回 Run

        参数：
            input_data: 执行 Run 的输入参数

        返回：
            执行的 Run 实体

        异常：
            DomainError: 当输入不符合业务规则时
            NotFoundError: 当 Agent 不存在时
            Exception: 当数据库操作失败时

        为什么不捕获异常？
        - 异常应该向上传播，由上层（API 层）统一处理
        - 用例不应该关心如何处理异常（关注点分离）
        - 保持用例简单，只负责业务逻辑编排

        示例：
        >>> agent_repo = SQLAlchemyAgentRepository(session)
        >>> run_repo = SQLAlchemyRunRepository(session)
        >>> use_case = ExecuteRunUseCase(
        ...     agent_repository=agent_repo,
        ...     run_repository=run_repo,
        ... )
        >>> input_data = ExecuteRunInput(agent_id="agent-123")
        >>> run = use_case.execute(input_data)
        >>> print(run.status)  # RunStatus.SUCCEEDED
        """
        # 步骤 1: 验证输入
        # 为什么在用例中验证？
        # - agent_id 是用例的输入参数，不是领域实体的属性
        # - 提前验证，避免无效的数据库查询
        # - 提供清晰的错误信息
        agent_id = input_data.agent_id.strip() if input_data.agent_id else ""
        if not agent_id:
            raise DomainError("agent_id 不能为空")

        # 步骤 2: 检查 Agent 是否存在
        # 为什么使用 get_by_id() 而不是 find_by_id()？
        # - get_by_id() 不存在时抛出 NotFoundError
        # - 符合业务语义：Agent 必须存在
        # - 避免手动检查 None
        agent = self.agent_repository.get_by_id(agent_id)

        # 步骤 3: 创建 Run 实体
        # 为什么调用 Run.create() 而不是 Run()?
        # - Run.create() 是工厂方法，封装了创建逻辑
        # - 自动生成 ID、设置默认值、验证业务规则
        # - 符合 DDD 聚合根创建模式
        run = Run.create(agent_id=agent.id)

        # 步骤 4: 保存 Run（PENDING 状态）
        # 为什么先保存？
        # - 记录 Run 的创建（审计需要）
        # - 如果后续步骤失败，可以看到 Run 的创建记录
        # - 符合事件溯源的思想
        self.run_repository.save(run)

        # 步骤 5: 启动 Run（PENDING → RUNNING）
        # 为什么调用 run.start() 而不是直接修改 status？
        # - run.start() 封装了状态转换逻辑
        # - 维护状态机不变式（只能从 PENDING 启动）
        # - 自动设置 started_at 时间戳
        run.start()

        # 步骤 6: 保存状态变化
        # 为什么再次保存？
        # - 持久化状态变化（PENDING → RUNNING）
        # - 如果后续步骤失败，可以看到 Run 已经启动
        # - 符合事件溯源的思想
        self.run_repository.save(run)

        # 步骤 7: 执行业务逻辑（LangGraph 集成）
        # - 不再创建/执行 Task 实体：LangGraph 内部完成多步推理与工具调用
        # - 用例只负责：构造初始消息 → 调用图执行 → 解析最终答案 → 更新 Run 状态
        try:
            executor = create_langgraph_task_executor()

            # LangGraph 以 messages 为核心状态；用 HumanMessage 作为输入
            input_message = HumanMessage(content=f"Start: {agent.start}\nGoal: {agent.goal}")
            initial_state: AgentState = {"messages": [input_message], "next": "reason"}  # type: ignore

            final_state = executor.invoke(initial_state)

            # 优先使用显式错误信号（若未来 LangGraph 状态加入 error 字段，可直接支持）
            explicit_error = final_state.get("error")
            if isinstance(explicit_error, str) and explicit_error.strip():
                run.fail(error=explicit_error)
            else:
                final_answer = extract_final_answer(final_state).strip()
                if not final_answer:
                    run.fail(error="执行失败：LangGraph 未返回有效结果")
                else:
                    # 兼容/启发式：LangGraph 内部节点目前会把错误写进 AIMessage.content
                    # 例如：推理过程出现错误: ... / 工具执行出现错误: ...
                    looks_like_error = (
                        final_answer.startswith("错误：")
                        or final_answer.startswith("执行失败")
                        or "出现错误" in final_answer
                    )
                    if looks_like_error:
                        run.fail(error=final_answer)
                    else:
                        run.succeed()
        except Exception as e:
            # invoke 抛异常：明确视为执行失败
            run.fail(error=f"执行失败：{str(e)}")

        # 步骤 8: 保存最终状态
        # 为什么再次保存？
        # - 持久化最终状态（RUNNING → SUCCEEDED/FAILED）
        # - 记录完成时间
        # - 确保数据一致性
        self.run_repository.save(run)

        # 步骤 9: 返回 Run
        # 为什么返回 Run 而不是 ID？
        # - 调用者可能需要 Run 的其他信息（如 started_at、finished_at）
        # - 避免调用者再次查询数据库
        # - 符合 CQRS 模式（Command 返回结果）
        return run
