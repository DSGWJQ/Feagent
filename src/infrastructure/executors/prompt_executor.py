"""Prompt executor implementation."""

from typing import Any

from src.domain.entities.node import Node
from src.domain.ports.node_executor import NodeExecutor


class PromptExecutor(NodeExecutor):
    """Simple executor that returns the prompt text from node config."""

    async def execute(
        self,
        node: Node,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> Any:
        """Return prompt content after simple variable replacement."""

        content = node.config.get("content", "")

        # Support placeholder replacement such as {input1}
        for i, (_key, value) in enumerate(inputs.items(), 1):
            placeholder = f"{{input{i}}}"
            if placeholder in content:
                content = content.replace(placeholder, str(value))

        return content
