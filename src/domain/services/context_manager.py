"""上下文管理器 (Context Manager) - 多Agent协作系统的上下文管理

业务定义：
- 管理多层上下文：Global → Session → Workflow → Node
- 各层有不同的生命周期和访问权限
- 支持上下文继承和数据桥接

设计原则：
- 全局上下文只读，保护系统配置
- 会话上下文管理目标栈和对话历史
- 工作流上下文相互隔离，支持并发
- 节点上下文临时存在，执行完销毁

层级关系：
    GlobalContext (只读，整个会话)
        ↓ 继承
    SessionContext (读写，单次会话)
        ↓ 派生
    WorkflowContext (隔离，单个工作流)
        ↓ 临时
    NodeContext (临时，单个节点执行)
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

# 从统一定义导入（避免重复定义）
from src.domain.entities.session_context import (
    GlobalContext,
    Goal,
    SessionContext,
    ShortTermSaturatedEvent,  # noqa: F401
)

if TYPE_CHECKING:
    pass


# Goal, GlobalContext, SessionContext, ShortTermSaturatedEvent 现在从 src.domain.entities.session_context 导入
# 以下类保留在本文件中：WorkflowContext, NodeContext, ContextBridge

# 注：原有的 Goal, GlobalContext, SessionContext 定义已移至 src/domain/entities/session_context.py
# 本文件通过 re-export 保持向后兼容，现有导入路径仍然有效


@dataclass
class WorkflowContext:
    """工作流上下文

    职责：
    - 引用会话上下文（只读）
    - 存储节点输出数据
    - 管理工作流变量
    - 记录执行历史

    设计特点：
    - 每个工作流有独立的上下文，相互隔离
    - 支持并发执行多个工作流
    - 节点间通过此上下文传递数据

    生命周期：单个工作流执行

    使用示例：
        workflow_ctx = WorkflowContext(
            workflow_id="workflow_xyz",
            session_context=session_ctx
        )
        workflow_ctx.set_node_output("node_1", {"result": "success"})
        output = workflow_ctx.get_node_output("node_1", "result")
    """

    workflow_id: str
    session_context: SessionContext

    # 节点输出数据: node_id -> outputs
    node_data: dict[str, dict[str, Any]] = field(default_factory=dict)

    # 工作流变量
    variables: dict[str, Any] = field(default_factory=dict)

    # 执行历史
    execution_history: list[dict[str, Any]] = field(default_factory=list)

    # 边条件求值结果: edge_id -> {result, expression, evaluated_at, error?}
    edge_conditions: dict[str, dict[str, Any]] = field(default_factory=dict)

    def set_node_output(self, node_id: str, outputs: dict[str, Any]) -> None:
        """设置节点输出

        参数：
            node_id: 节点ID
            outputs: 输出数据字典
        """
        self.node_data[node_id] = outputs

    def get_node_output(self, node_id: str, key: str | None = None) -> Any:
        """获取节点输出

        参数：
            node_id: 节点ID
            key: 可选，获取特定的输出key

        返回：
            如果指定key，返回该key的值
            否则返回整个输出字典
        """
        outputs = self.node_data.get(node_id, {})
        if key is not None:
            return outputs.get(key)
        return outputs

    def set_variable(self, name: str, value: Any) -> None:
        """设置工作流变量

        参数：
            name: 变量名
            value: 变量值
        """
        self.variables[name] = value

    def get_variable(self, name: str, default: Any = None) -> Any:
        """获取工作流变量

        参数：
            name: 变量名
            default: 默认值（变量不存在时返回）

        返回：
            变量值，或默认值
        """
        return self.variables.get(name, default)


@dataclass
class NodeContext:
    """节点上下文

    职责：
    - 引用工作流上下文
    - 存储节点输入
    - 跟踪执行状态
    - 存储节点输出

    生命周期：单个节点执行（最短）

    使用示例：
        node_ctx = NodeContext(
            node_id="node_llm_1",
            workflow_context=workflow_ctx,
            inputs={"prompt": "分析数据"}
        )
        node_ctx.set_state("running")
        node_ctx.set_output("result", "分析完成")
        node_ctx.set_state("completed")
    """

    node_id: str
    workflow_context: WorkflowContext

    # 节点输入
    inputs: dict[str, Any] = field(default_factory=dict)

    # 节点输出
    outputs: dict[str, Any] = field(default_factory=dict)

    # 执行状态: pending | running | completed | failed
    execution_state: str = "pending"

    # 错误信息（如果失败）
    error: str | None = None

    # 时间戳
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def set_state(self, state: str) -> None:
        """设置执行状态

        参数：
            state: 状态值 (pending/running/completed/failed)
        """
        self.execution_state = state

        if state == "running":
            self.started_at = datetime.now()
        elif state in ("completed", "failed"):
            self.completed_at = datetime.now()

    def set_output(self, key: str, value: Any) -> None:
        """设置输出值

        参数：
            key: 输出key
            value: 输出值
        """
        self.outputs[key] = value


class ContextBridge:
    """上下文桥接器

    职责：
    - 在工作流上下文之间传递数据
    - 支持选择性传递（只传递需要的数据）
    - 支持数据摘要（减少token消耗）

    使用场景：
    - 目标分解后，子工作流之间传递结果
    - 工作流完成后，结果传递给下一个工作流

    使用示例：
        bridge = ContextBridge()
        bridge.transfer(source_workflow, target_workflow, keys=["result"])
    """

    def transfer(
        self, source: WorkflowContext, target: WorkflowContext, keys: list[str] | None = None
    ) -> dict[str, Any]:
        """传递数据

        参数：
            source: 源工作流上下文
            target: 目标工作流上下文
            keys: 要传递的key列表，None表示传递所有

        返回：
            传递的数据
        """
        # 收集要传递的数据
        transferred_data = {}

        # 从节点输出收集
        for _node_id, outputs in source.node_data.items():
            for key, value in outputs.items():
                if keys is None or key in keys:
                    transferred_data[key] = value

        # 从变量收集
        for var_name, var_value in source.variables.items():
            if keys is None or var_name in keys:
                transferred_data[var_name] = var_value

        # 注入到目标上下文
        target.set_variable("__transferred__", transferred_data)

        return transferred_data

    def transfer_with_summary(
        self,
        source: WorkflowContext,
        target: WorkflowContext,
        summary_fn: Callable[[Any], dict[str, Any]],
    ) -> dict[str, Any]:
        """传递数据并摘要

        参数：
            source: 源工作流上下文
            target: 目标工作流上下文
            summary_fn: 摘要函数，接收原始数据，返回摘要

        返回：
            摘要后的数据
        """
        # 收集所有数据
        all_data = []
        for _node_id, outputs in source.node_data.items():
            all_data.extend(outputs.values())

        for var_value in source.variables.values():
            all_data.append(var_value)

        # 应用摘要函数
        if all_data:
            # 如果数据是列表，展开传递
            if len(all_data) == 1:
                summarized = summary_fn(all_data[0])
            else:
                summarized = summary_fn(all_data)
        else:
            summarized = {}

        # 注入到目标上下文
        target.set_variable("__transferred__", summarized)

        return summarized


# 导出
__all__ = [
    "Goal",
    "GlobalContext",
    "SessionContext",
    "WorkflowContext",
    "NodeContext",
    "ContextBridge",
]
