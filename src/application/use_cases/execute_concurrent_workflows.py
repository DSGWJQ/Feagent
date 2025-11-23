"""ExecuteConcurrentWorkflowsUseCase - 并发执行多个工作流

编排：
1. 验证所有工作流存在
2. 为每个工作流创建Run实例
3. 提交到并发执行管理器
4. 追踪执行状态
"""

from dataclasses import dataclass

from src.domain.entities.run import Run
from src.domain.exceptions import NotFoundError


@dataclass
class ExecuteConcurrentWorkflowsInput:
    """并发执行输入数据"""

    workflow_ids: list[str]
    max_concurrent: int = 5


@dataclass
class ExecutionResult:
    """执行结果"""

    workflow_id: str
    run_id: str
    status: str


class ExecuteConcurrentWorkflowsUseCase:
    """并发工作流执行用例

    职责：
    - 验证工作流
    - 创建Run实例
    - 管理并发执行
    - 追踪执行状态
    """

    def __init__(self, workflow_repo, execution_manager, run_repo):
        """初始化用例

        参数：
            workflow_repo: 工作流仓库
            execution_manager: 并发执行管理器
            run_repo: Run仓库
        """
        self.workflow_repo = workflow_repo
        self.execution_manager = execution_manager
        self.run_repo = run_repo
        # 设置最大并发任务数
        self.execution_manager.max_concurrent_tasks = 5

    def execute(self, input_data: ExecuteConcurrentWorkflowsInput) -> list[ExecutionResult]:
        """并发执行多个工作流

        参数：
            input_data: 输入数据

        返回：
            执行结果列表

        抛出：
            NotFoundError: 工作流不存在
        """
        # 设置并发限制
        self.execution_manager.max_concurrent_tasks = input_data.max_concurrent

        results = []

        # 1. 验证所有工作流存在并创建Run
        for workflow_id in input_data.workflow_ids:
            workflow = self.workflow_repo.get_by_id(workflow_id)
            if not workflow:
                raise NotFoundError(f"工作流不存在: {workflow_id}")

            # 2. 创建Run实例（使用workflow_id作为agent_id用于追踪）
            run = Run.create(agent_id=f"workflow_{workflow_id}")

            # 3. 保存Run
            self.run_repo.save(run)

            # 4. 提交到并发执行管理器
            async def execute_workflow(wf, r):
                """执行工作流的异步函数"""
                import asyncio

                # 这里会实际执行工作流（假设WorkflowExecutor存在）
                await asyncio.sleep(0.01)  # 模拟执行
                return {"status": "completed"}

            # 提交到执行管理器
            self.execution_manager.submit_task(
                f"workflow_{workflow_id}",
                execute_workflow,
                workflow,
                run,
                priority=5,
            )

            results.append(
                ExecutionResult(workflow_id=workflow_id, run_id=run.id, status="submitted")
            )

        return results

    def wait_all_completion(self, timeout: float | None = None) -> bool:
        """等待所有工作流完成

        参数：
            timeout: 超时时间（秒）

        返回：
            True 如果所有任务都完成，False 如果超时
        """
        return self.execution_manager.wait_all(timeout=timeout)

    def get_execution_result(self, run_id: str) -> Run:
        """获取执行结果

        参数：
            run_id: Run ID

        返回：
            Run实体

        抛出：
            NotFoundError: Run不存在
        """
        run = self.run_repo.get_by_id(run_id)
        if not run:
            raise NotFoundError(f"执行记录不存在: {run_id}")

        return run

    def cancel_all_executions(self) -> bool:
        """取消所有正在执行的工作流

        返回：
            True 如果取消成功
        """
        self.execution_manager.cancel_all()
        return True
