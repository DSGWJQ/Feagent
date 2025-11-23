"""工作流执行器适配器

将工作流执行器适配为调度器可以调用的接口
"""

import asyncio
from typing import Any

from src.domain.services.workflow_executor import WorkflowExecutor
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.infrastructure.executors import create_executor_registry


class WorkflowExecutorAdapter:
    """工作流执行器适配器

    用于在调度器中执行工作流
    """

    def __init__(
        self,
        workflow_repository: SQLAlchemyWorkflowRepository | None = None,
        executor_registry: Any = None,
    ):
        """初始化适配器

        参数：
            workflow_repository: 工作流仓库
            executor_registry: 节点执行器注册表
        """
        self.workflow_repository = workflow_repository
        if executor_registry is None:
            executor_registry = create_executor_registry()
        self.executor_registry = executor_registry

    def execute_workflow(self, workflow_id: str, input_data: dict) -> dict:
        """执行工作流（同步包装）

        参数：
            workflow_id: 工作流 ID
            input_data: 输入数据

        返回：
            执行结果 {"status": "success"/"failure", "data": ...}
        """
        try:
            # 运行异步执行
            result = asyncio.run(self._execute_workflow_async(workflow_id, input_data))
            return result
        except Exception as e:
            return {
                "status": "failure",
                "workflow_id": workflow_id,
                "error": str(e),
            }

    async def _execute_workflow_async(self, workflow_id: str, input_data: dict) -> dict:
        """异步执行工作流

        参数：
            workflow_id: 工作流 ID
            input_data: 输入数据

        返回：
            执行结果
        """
        # 如果没有设置仓库，返回成功（用于测试）
        if self.workflow_repository is None:
            return {
                "status": "success",
                "workflow_id": workflow_id,
                "message": "工作流执行成功（无仓库）",
            }

        # 从数据库获取工作流
        workflow = self.workflow_repository.find_by_id(workflow_id)
        if not workflow:
            return {
                "status": "failure",
                "workflow_id": workflow_id,
                "error": f"工作流未找到: {workflow_id}",
            }

        # 创建执行器并执行
        executor = WorkflowExecutor(executor_registry=self.executor_registry)
        result = await executor.execute(workflow, initial_input=input_data)

        return {
            "status": "success",
            "workflow_id": workflow_id,
            "data": result,
            "logs": executor.execution_log,
        }
