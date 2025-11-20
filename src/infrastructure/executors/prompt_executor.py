"""Prompt Executor（提示词执行器）

Infrastructure 层：实现 Prompt 节点执行器
"""

from typing import Any

from src.domain.entities.node import Node
from src.domain.ports.node_executor import NodeExecutor


class PromptExecutor(NodeExecutor):
    """Prompt 节点执行器

    Prompt 节点简单地返回配置的文本内容
    """

    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        """执行 Prompt 节点

        配置参数：
            content: 提示词内容
        """
        content = node.config.get("content", "")

        # 可以支持模板变量替换
        # 例如：将 {input1} 替换为实际输入
        for i, (key, value) in enumerate(inputs.items(), 1):
            placeholder = f"{{input{i}}}"
            if placeholder in content:
                content = content.replace(placeholder, str(value))

        return content
