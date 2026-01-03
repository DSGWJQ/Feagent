"""ExecuteWorkflowUseCase - 执行工作流

业务场景：
- 用户触发工作流执行
- 按拓扑顺序执行节点
- 支持流式返回（SSE）实时推送执行状态

设计原则：
- 单一职责：只负责业务编排，不包含执行逻辑
- 依赖倒置：依赖 Repository 接口，不依赖具体实现
- 输入输出明确：使用 Input/Output 对象
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from src.domain.exceptions import DomainError
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.ports.workflow_repository import WorkflowRepository
from src.domain.services.workflow_executor import WorkflowExecutor

WORKFLOW_EXECUTION_KERNEL_ID = "workflow_engine_v1"


@dataclass
class ExecuteWorkflowInput:
    """ExecuteWorkflow 输入参数

    为什么需要 Input 对象？
    1. 类型安全：明确输入参数类型
    2. 验证集中：可以在 Input 对象中验证参数
    3. 可测试性：测试时容易构造输入
    4. 文档化：清晰表达 Use Case 需要什么输入

    属性说明：
    - workflow_id: 工作流 ID
    - initial_input: 初始输入（传递给 Start 节点）
    """

    workflow_id: str
    initial_input: Any = None


class ExecuteWorkflowUseCase:
    """ExecuteWorkflow Use Case

    职责：
    1. 获取工作流
    2. 调用 WorkflowExecutor 执行工作流
    3. 返回执行结果（支持流式返回）

    为什么不在这里实现执行逻辑？
    - 执行逻辑在 Domain 层（WorkflowExecutor 服务）
    - Use Case 只负责编排（获取 → 执行 → 返回）
    - 符合单一职责原则

    依赖：
    - WorkflowRepository: 工作流仓储接口
    - NodeExecutorRegistry: 节点执行器注册表
    """

    def __init__(
        self,
        workflow_repository: WorkflowRepository,
        executor_registry: NodeExecutorRegistry | None = None,
    ):
        """初始化 Use Case

        参数：
            workflow_repository: 工作流仓储接口
            executor_registry: 节点执行器注册表

        为什么通过构造函数注入依赖？
        - 依赖倒置：Use Case 依赖接口，不依赖具体实现
        - 可测试性：测试时可以注入 Mock Repository
        - 灵活性：可以轻松切换不同的 Repository 实现
        """
        self.workflow_repository = workflow_repository
        self.executor_registry = executor_registry

    async def execute(self, input_data: ExecuteWorkflowInput) -> dict[str, Any]:
        """执行工作流（非流式）

        业务流程：
        1. 获取工作流（不存在抛出 NotFoundError）
        2. 创建 WorkflowExecutor
        3. 执行工作流
        4. 返回执行结果

        参数：
            input_data: 输入参数

        返回：
            执行结果字典：
            - execution_log: 执行日志（每个节点的执行记录）
            - final_result: 最终结果（End 节点的输出）

        异常：
            NotFoundError: 工作流不存在
            DomainError: 工作流执行失败（例如包含环）
        """
        # 1. 获取工作流
        workflow = self.workflow_repository.get_by_id(input_data.workflow_id)

        # 2. 创建执行器
        executor = WorkflowExecutor(executor_registry=self.executor_registry)

        # 3. 执行工作流
        final_result = await executor.execute(workflow, input_data.initial_input)

        # 4. 返回结果
        return {
            "execution_log": executor.execution_log,
            "final_result": final_result,
            "executor_id": WORKFLOW_EXECUTION_KERNEL_ID,
        }

    async def execute_streaming(
        self, input_data: ExecuteWorkflowInput
    ) -> AsyncGenerator[dict[str, Any], None]:
        """执行工作流（流式返回）

        业务流程：
        1. 获取工作流
        2. 创建 WorkflowExecutor
        3. 设置事件回调
        4. 执行工作流，通过回调生成事件
        5. 生成最终完成事件

        参数：
            input_data: 输入参数

        生成：
            事件字典（SSE 格式）：
            - node_start: 节点开始执行
            - node_complete: 节点执行完成
            - node_error: 节点执行失败
            - workflow_complete: 工作流执行完成
            - workflow_error: 工作流执行失败

        异常：
            NotFoundError: 工作流不存在
        """
        # 1. 获取工作流
        workflow = self.workflow_repository.get_by_id(input_data.workflow_id)

        # 2. 创建执行器
        executor = WorkflowExecutor(executor_registry=self.executor_registry)

        # 3. 创建事件队列
        events: list[dict[str, Any]] = []

        def event_callback(event_type: str, data: dict[str, Any]) -> None:
            events.append({"type": event_type, "executor_id": WORKFLOW_EXECUTION_KERNEL_ID, **data})

        # 4. 设置事件回调
        executor.set_event_callback(event_callback)

        try:
            # 5. 执行工作流
            final_result = await executor.execute(workflow, input_data.initial_input)
        except DomainError as exc:
            for event in events:
                yield event
            yield {
                "type": "workflow_error",
                "error": str(exc),
                "executor_id": WORKFLOW_EXECUTION_KERNEL_ID,
            }
            return

        # 6. 生成所有事件
        for event in events:
            yield event

        # 7. 生成 workflow_complete 事件
        yield {
            "type": "workflow_complete",
            "result": final_result,
            "execution_log": executor.execution_log,
            "executor_id": WORKFLOW_EXECUTION_KERNEL_ID,
        }
