"""ExecutionEngine - 执行引擎

职责：
1. 协调整个 Run 的执行流程
2. 管理 Run 生命周期（PENDING → RUNNING → SUCCEEDED/FAILED）
3. 按顺序执行 Tasks
4. 处理错误和异常
5. 更新执行状态到数据库

设计原则：
- 领域服务：不属于任何实体，但包含重要的业务逻辑
- 依赖注入：通过构造函数注入 Repository 和 TaskExecutor
- 单一职责：只负责执行流程编排，不包含具体的任务执行逻辑
- 错误处理：捕获所有异常，确保 Run 状态正确更新

为什么需要 ExecutionEngine？
- Run 和 Task 的执行流程是复杂的业务逻辑
- 不适合放在 Use Case 中（Use Case 应该简单）
- 不适合放在 Entity 中（Entity 应该只包含状态和简单的业务规则）
- 领域服务是最合适的位置
"""

from typing import Any

from src.domain.entities.run import Run
from src.domain.entities.task import Task
from src.domain.ports.run_repository import RunRepository
from src.domain.ports.task_repository import TaskRepository


class TaskExecutor:
    """TaskExecutor 接口（临时定义，后续会实现）

    职责：执行单个 Task
    """

    def execute(self, task: Task, context: dict[str, Any]) -> dict[str, Any]:
        """执行 Task

        参数：
            task: 要执行的 Task
            context: 执行上下文（包含前置任务的结果）

        返回：
            Task 执行结果

        异常：
            可能抛出任何异常（由 ExecutionEngine 捕获）
        """
        raise NotImplementedError


class ExecutionEngine:
    """执行引擎

    职责：
    1. 加载 Run 和 Tasks
    2. 启动 Run（PENDING → RUNNING）
    3. 按顺序执行 Tasks
    4. 处理 Task 执行结果
    5. 完成 Run（RUNNING → SUCCEEDED/FAILED）
    6. 持久化所有状态变化
    """

    def __init__(
        self,
        run_repository: RunRepository,
        task_repository: TaskRepository,
        task_executor: TaskExecutor,
    ):
        """初始化执行引擎

        参数：
            run_repository: Run 仓储
            task_repository: Task 仓储
            task_executor: Task 执行器
        """
        self.run_repository = run_repository
        self.task_repository = task_repository
        self.task_executor = task_executor

    def execute_run(self, run_id: str) -> None:
        """执行 Run

        执行流程：
        1. 加载 Run（如果不存在，抛出 NotFoundError）
        2. 加载 Tasks（按创建时间排序）
        3. 启动 Run（PENDING → RUNNING）
        4. 逐个执行 Tasks
        5. 完成 Run（RUNNING → SUCCEEDED/FAILED）

        参数：
            run_id: Run ID

        异常：
            NotFoundError: Run 不存在

        注意：
        - 所有异常都会被捕获，Run 状态会更新为 FAILED
        - Task 失败不会中断执行，会继续执行后续 Tasks
        - 只要有一个 Task 失败，Run 就会失败
        """
        run: Run | None = None

        try:
            # 步骤 1: 加载 Run
            run = self.run_repository.get_by_id(run_id)

            # 步骤 2: 加载 Tasks
            tasks = self.task_repository.find_by_run_id(run_id)

            # 步骤 3: 启动 Run
            run.start()
            self.run_repository.save(run)

            # 步骤 4: 执行 Tasks
            has_failed_task = False
            context: dict[str, Any] = {}  # 执行上下文，用于在 Task 之间传递数据

            for task in tasks:
                try:
                    # 启动 Task
                    task.start()
                    self.task_repository.save(task)

                    # 执行 Task
                    result = self.task_executor.execute(task, context)

                    # Task 成功
                    task.succeed(output_data=result)
                    self.task_repository.save(task)

                    # 更新上下文（后续 Task 可以使用前面 Task 的结果）
                    context[task.name] = result

                except Exception as e:
                    # Task 失败
                    task.fail(error=str(e))
                    self.task_repository.save(task)
                    has_failed_task = True

                    # 继续执行后续 Tasks（不中断）
                    # 这样可以看到所有 Tasks 的执行结果

            # 步骤 5: 完成 Run
            if has_failed_task:
                # 有 Task 失败，Run 失败
                run.fail(error="一个或多个 Task 执行失败")
            else:
                # 所有 Task 成功，Run 成功
                run.succeed()

            self.run_repository.save(run)

        except Exception as e:
            # 执行过程中发生异常（如 Run 不存在、数据库错误等）
            # 如果 Run 已加载，更新状态为 FAILED
            try:
                if run is not None:
                    run.fail(error=f"执行失败: {str(e)}")
                    self.run_repository.save(run)
            except Exception:
                # 保存失败，忽略（避免异常嵌套）
                pass

            # 重新抛出异常（让调用方知道发生了什么）
            raise

    def execute_task(
        self,
        task_id: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """执行单个 Task（独立执行，不依赖 Run）

        这个方法用于单独执行某个 Task，不需要完整的 Run 流程。
        适用场景：
        - 重试失败的 Task
        - 测试单个 Task
        - 手动触发 Task

        参数：
            task_id: Task ID
            context: 执行上下文（可选）

        返回：
            Task 执行结果

        异常：
            NotFoundError: Task 不存在
            Exception: Task 执行失败
        """
        # 加载 Task
        task = self.task_repository.get_by_id(task_id)

        # 启动 Task
        task.start()
        self.task_repository.save(task)

        try:
            # 执行 Task
            result = self.task_executor.execute(task, context or {})

            # Task 成功
            task.succeed(output_data=result)
            self.task_repository.save(task)

            return result

        except Exception as e:
            # Task 失败
            task.fail(error=str(e))
            self.task_repository.save(task)
            raise
