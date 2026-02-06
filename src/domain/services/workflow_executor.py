"""WorkflowExecutor（工作流执行器）

DDD-030：该类仅保留对外执行接口，将 DAG 执行主逻辑委托给 `WorkflowEngine`，
确保只有一个权威实现。
"""

from typing import Any

from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.services.event_bus import EventBus
from src.domain.services.workflow_engine import WorkflowEngine


class WorkflowExecutor:
    """工作流执行器

    使用拓扑排序执行工作流节点

    属性：
        execution_log: 执行日志（记录每个节点的执行结果）
        executor_registry: 节点执行器注册表
    """

    def __init__(
        self,
        executor_registry: NodeExecutorRegistry | None = None,
        *,
        event_bus: EventBus | None = None,
    ):
        self.execution_log: list[dict[str, Any]] = []
        self._engine = WorkflowEngine(executor_registry=executor_registry)
        self._event_bus = event_bus

    async def execute(
        self,
        workflow: Workflow,
        initial_input: Any = None,
        *,
        correlation_id: str | None = None,
    ) -> Any:
        """执行工作流

        参数：
            workflow: 工作流实体
            initial_input: 初始输入（传递给 Start 节点）
            correlation_id: 事件关联 ID（用于 EventBus 订阅隔离）

        返回：
            工作流执行结果（End 节点的输出）

        异常：
            DomainError: 工作流包含环或其他执行错误
        """
        final_result, execution_log = await self._engine.execute(
            workflow=workflow,
            initial_input=initial_input,
            event_bus=self._event_bus,
            correlation_id=correlation_id,
        )
        self.execution_log = execution_log
        return final_result

    def _topological_sort(self, workflow: Workflow) -> list[Node]:
        return self._engine.topological_sort(workflow)
