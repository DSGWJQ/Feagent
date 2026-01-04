"""ToolNodeExecutor - 工具节点执行器（WFCORE-050）

职责：
- 以 `tool_id` 作为唯一权威引用，从 ToolRepository 获取 Tool
- 通过 ToolEngine 执行工具（fail-closed：工具不存在/已废弃/执行失败则抛 DomainError）

KISS：
- 不在此处做复杂的参数映射/模板渲染；仅读取 node.config.params
- ToolEngine 的 executor 映射遵循其既有契约：tool.implementation_config["handler"]
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError, NotFoundError
from src.domain.ports.node_executor import NodeExecutor
from src.domain.services.tool_engine import ToolEngine
from src.domain.services.tool_executor import EchoExecutor, NoOpExecutor, ToolExecutionContext
from src.domain.value_objects.tool_status import ToolStatus


def _extract_tool_id(config: dict[str, Any]) -> str | None:
    for key in ("tool_id", "toolId"):
        raw = config.get(key)
        if isinstance(raw, str):
            value = raw.strip()
            if value:
                return value
    return None


class ToolNodeExecutor(NodeExecutor):
    """工具节点执行器：tool_id -> ToolRepository -> ToolEngine.execute()."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any],
        tool_engine: ToolEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._tool_engine = tool_engine or ToolEngine()

        # Minimal built-in executors for deterministic execution in workflows/tests.
        self._tool_engine.register_executor("echo", EchoExecutor())
        self._tool_engine.register_executor("noop", NoOpExecutor())

    async def execute(self, node: Node, inputs: dict[str, Any], context: dict[str, Any]) -> Any:
        config = node.config if isinstance(node.config, dict) else {}
        tool_id = _extract_tool_id(config)
        if tool_id is None:
            raise DomainError("tool node requires config.tool_id")

        params_raw = config.get("params", config.get("args", config.get("arguments", {})))
        if params_raw is None:
            params: dict[str, Any] = {}
        elif isinstance(params_raw, dict):
            params = params_raw
        else:
            raise DomainError("tool node config.params must be an object")

        timeout_raw = config.get("timeout")
        timeout = float(timeout_raw) if isinstance(timeout_raw, int | float) else 30.0
        if timeout <= 0:
            timeout = 30.0

        # Load tool by ID (authoritative), then execute via ToolEngine.
        session = self._session_factory()
        try:
            from src.infrastructure.database.repositories.tool_repository import (
                SQLAlchemyToolRepository,
            )

            tool = SQLAlchemyToolRepository(session).get_by_id(tool_id)
        except NotFoundError as exc:
            raise DomainError(f"tool not found: {tool_id}") from exc
        finally:
            try:
                session.close()
            except Exception:
                pass

        if tool.status is ToolStatus.DEPRECATED:
            raise DomainError(f"tool is deprecated: {tool_id}")

        # ToolEngine indexes by tool.name; we register the fetched Tool every time to ensure freshness.
        self._tool_engine.register(tool)

        tool_context = ToolExecutionContext(
            caller_type="workflow_node",
            workflow_id=context.get("workflow_id")
            if isinstance(context.get("workflow_id"), str)
            else None,
            timeout=timeout,
            variables={
                "node_id": node.id,
                "inputs": inputs,
                "initial_input": context.get("initial_input"),
            },
        )

        result = await self._tool_engine.execute(
            tool_name=tool.name,
            params=params,
            context=tool_context,
        )
        if not result.is_success:
            raise DomainError(
                f"tool execution failed: tool_id={tool_id} type={result.error_type} error={result.error}"
            )
        return result.output
