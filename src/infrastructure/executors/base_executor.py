"""Base Executor（基础执行器）

Infrastructure 层：实现基础节点执行器

包括：
- StartExecutor: 开始节点
- EndExecutor: 结束节点
"""

from typing import Any

from src.domain.entities.node import Node
from src.domain.ports.node_executor import NodeExecutor


class StartExecutor(NodeExecutor):
    """Start 节点执行器"""

    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        """执行 Start 节点

        Start 节点返回初始输入
        """
        return context.get("initial_input", {})


class EndExecutor(NodeExecutor):
    """End 节点执行器"""

    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        """执行 End 节点

        End 节点返回第一个输入
        """
        if inputs:
            # 返回第一个输入
            first_key = next(iter(inputs))
            return inputs[first_key]
        return None
