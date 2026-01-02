"""WorkflowExecutor（工作流执行器）

DDD-030：该类保留对外接口与 event callback 语义，但将 DAG 执行主逻辑委托给
`WorkflowEngine`，确保只有一个权威实现。
"""

from collections.abc import Callable
from typing import Any

from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.services.workflow_engine import WorkflowEngine


class WorkflowExecutor:
    """工作流执行器

    使用拓扑排序执行工作流节点

    属性：
        execution_log: 执行日志（记录每个节点的执行结果）
        executor_registry: 节点执行器注册表
    """

    def __init__(self, executor_registry: NodeExecutorRegistry | None = None):
        self.execution_log: list[dict[str, Any]] = []
        self._engine = WorkflowEngine(executor_registry=executor_registry)
        self._event_callback: Callable[[str, dict[str, Any]], None] | None = None

    def set_event_callback(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        """设置事件回调函数

        用于 SSE 流式返回执行状态

        参数：
            callback: 回调函数，接收事件类型和数据
        """
        self._event_callback = callback

    async def execute(self, workflow: Workflow, initial_input: Any = None) -> Any:
        """执行工作流

        参数：
            workflow: 工作流实体
            initial_input: 初始输入（传递给 Start 节点）

        返回：
            工作流执行结果（End 节点的输出）

        异常：
            DomainError: 工作流包含环或其他执行错误
        """
        final_result, execution_log = await self._engine.execute(
            workflow=workflow,
            initial_input=initial_input,
            event_callback=self._event_callback,
        )
        self.execution_log = execution_log
        return final_result

    def _topological_sort(self, workflow: Workflow) -> list[Node]:
        return self._engine.topological_sort(workflow)
