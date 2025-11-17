"""ExecuteRunUseCase - 执行 Run 用例

业务场景：
用户触发 Agent 执行，系统创建一个 Run 并执行

职责：
1. 验证 Agent 是否存在
2. 创建 Run 实体
3. 启动 Run（PENDING → RUNNING）
4. 生成执行计划（使用 PlanGeneratorChain）
5. 创建 Task 实体
6. 执行 Task（使用 TaskExecutorAgent）
7. 完成 Run（RUNNING → SUCCEEDED/FAILED）
8. 持久化状态变化

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

LangChain 集成：
- 使用 PlanGeneratorChain 生成执行计划
- 使用 TaskExecutorAgent 执行每个任务
- 处理错误和重试
- 记录任务执行日志
"""

from dataclasses import dataclass

from src.domain.entities.run import Run
from src.domain.entities.task import Task
from src.domain.exceptions import DomainError
from src.domain.ports.agent_repository import AgentRepository
from src.domain.ports.run_repository import RunRepository
from src.domain.ports.task_repository import TaskRepository
from src.lc import create_plan_generator_chain, execute_task


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
    4. 生成执行计划（LangChain）
    5. 创建和执行 Task
    6. 完成 Run
    7. 持久化状态变化

    依赖：
    - AgentRepository: Agent 仓储接口
    - RunRepository: Run 仓储接口
    - TaskRepository: Task 仓储接口

    为什么需要三个 Repository？
    - Agent、Run、Task 是不同的聚合根
    - 每个聚合根有自己的 Repository
    - 符合 DDD 聚合设计原则
    """

    def __init__(
        self,
        agent_repository: AgentRepository,
        run_repository: RunRepository,
        task_repository: TaskRepository,
    ):
        """初始化用例

        参数：
            agent_repository: Agent 仓储接口
            run_repository: Run 仓储接口
            task_repository: Task 仓储接口

        为什么通过构造函数注入？
        - 依赖注入：由外部管理依赖
        - 可测试性：测试时可以注入 Mock
        - 明确依赖：构造函数清晰表达依赖关系
        """
        self.agent_repository = agent_repository
        self.run_repository = run_repository
        self.task_repository = task_repository

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

        # 步骤 7: 执行业务逻辑（LangChain 集成）
        # 7.1 生成执行计划
        # 7.2 创建 Task
        # 7.3 执行 Task
        # 7.4 处理错误
        try:
            # 7.1: 生成执行计划
            # 为什么使用 PlanGeneratorChain？
            # - 使用 LLM 自动生成执行计划
            # - 根据 Agent 的 start 和 goal 生成任务列表
            # - 返回 JSON 格式的计划
            plan_chain = create_plan_generator_chain()
            plan = plan_chain.invoke(
                {
                    "start": agent.start,
                    "goal": agent.goal,
                }
            )

            # 7.2: 创建 Task 实体
            # 为什么要创建 Task？
            # - Task 是执行的最小单元
            # - 记录每个步骤的执行状态
            # - 便于追踪和调试
            tasks = []
            for task_data in plan:
                task = Task.create(
                    run_id=run.id,
                    name=task_data["name"],
                    input_data={"description": task_data["description"]},
                )
                tasks.append(task)
                # 保存 Task（PENDING 状态）
                self.task_repository.save(task)

            # 7.3: 执行每个 Task
            # 为什么要逐个执行？
            # - 任务之间可能有依赖关系
            # - 前一个任务的输出可能是后一个任务的输入
            # - 便于错误处理和重试
            has_failed_task = False
            for task in tasks:
                # 启动 Task（PENDING → RUNNING）
                task.start()
                self.task_repository.save(task)

                # 执行 Task（使用 TaskExecutorAgent）
                # 为什么使用 execute_task？
                # - 封装了 Agent 的创建和调用
                # - 自动处理异常
                # - 返回清晰的结果
                result = execute_task(
                    task_name=task.name,
                    task_description=task.input_data.get("description", ""),
                )

                # 检查执行结果
                # 为什么检查 "错误："？
                # - execute_task 在失败时返回 "错误：..." 格式的字符串
                # - 简单的错误检测机制
                if result.startswith("错误："):
                    # Task 执行失败
                    task.fail(error=result)
                    has_failed_task = True
                else:
                    # Task 执行成功
                    task.succeed(output_data={"result": result})

                # 保存 Task 状态
                self.task_repository.save(task)

            # 7.4: 根据 Task 执行结果更新 Run 状态
            # 为什么要检查 has_failed_task？
            # - 如果有任何 Task 失败，Run 应该标记为失败
            # - 符合业务语义：只有所有 Task 成功，Run 才成功
            if has_failed_task:
                run.fail(error="部分任务执行失败")
            else:
                run.succeed()

        except Exception as e:
            # 捕获所有异常（计划生成失败、Task 创建失败等）
            # 为什么捕获异常？
            # - 确保 Run 状态被正确更新为 FAILED
            # - 记录错误信息，便于调试
            # - 避免 Run 一直处于 RUNNING 状态
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
