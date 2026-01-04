"""Tool call executor implementations for ConversationAgent (WFCORE-080).

Goal:
- Provide a real, offline-safe execution path for ReAct tool_call actions by bridging to ToolEngine.
- Ensure every tool_call yields a tool_result (success/error) and produces replayable audit records
  via ToolEngine knowledge_store (equivalent mechanism).

Design (KISS / DIP):
- ConversationAgent depends on a duck-typed `tool_call_executor.execute(...)` hook.
- The default implementation lives in Application layer and can be replaced by host apps.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from src.domain.entities.tool import Tool, ToolParameter
from src.domain.services.tool_engine import ToolEngine, ToolEngineConfig
from src.domain.services.tool_executor import EchoExecutor, NoOpExecutor, ToolExecutionContext
from src.domain.services.tool_knowledge_store import InMemoryToolKnowledgeStore, ToolKnowledgeStore
from src.domain.value_objects.tool_category import ToolCategory
from src.domain.value_objects.tool_status import ToolStatus


class ToolCallExecutor(Protocol):
    async def execute(
        self,
        *,
        tool_name: str,
        tool_call_id: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ToolCallExecutionPayload:
    success: bool
    result: dict[str, Any]
    error: str | None = None
    error_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "success": self.success,
            "result": self.result,
        }
        if self.error:
            payload["error"] = self.error
        if self.error_type:
            payload["error_type"] = self.error_type
        return payload


class ToolEngineToolCallExecutor:
    """Execute tool calls via ToolEngine and record audit trail in knowledge_store.

    Notes:
    - This is intentionally offline-safe: no network is used unless a registered tool executor does.
    - ToolEngine audit records (ToolCallRecord) are an equivalent replay mechanism to persisted RunEvent.
    """

    def __init__(
        self,
        *,
        conversation_id_provider: Callable[[], str | None],
        user_message_provider: Callable[[], str | None] | None = None,
        workflow_id_provider: Callable[[], str | None] | None = None,
        run_id_provider: Callable[[], str | None] | None = None,
        caller_id: str = "conversation_agent",
        tools_directory: str = "scripts/tools",
        tool_engine: ToolEngine | None = None,
        knowledge_store: ToolKnowledgeStore | None = None,
    ) -> None:
        self._conversation_id_provider = conversation_id_provider
        self._user_message_provider = user_message_provider
        self._workflow_id_provider = workflow_id_provider
        self._run_id_provider = run_id_provider
        self._caller_id = caller_id
        self._engine = tool_engine or ToolEngine(
            config=ToolEngineConfig(
                tools_directory=tools_directory,
                auto_reload=False,
            )
        )
        self._knowledge_store = knowledge_store or InMemoryToolKnowledgeStore()
        self._engine.set_knowledge_store(self._knowledge_store)

        # Minimal deterministic executors (no I/O).
        self._engine.register_executor("echo", EchoExecutor())
        self._engine.register_executor("noop", NoOpExecutor())

        self._load_lock = asyncio.Lock()
        self._loaded = False

    @property
    def engine(self) -> ToolEngine:
        return self._engine

    @property
    def knowledge_store(self) -> ToolKnowledgeStore:
        return self._knowledge_store

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        async with self._load_lock:
            if self._loaded:
                return
            await self._engine.load()
            self._register_minimal_builtin_tools()
            self._loaded = True

    def _register_minimal_builtin_tools(self) -> None:
        """Guarantee a minimal offline-safe toolset even if tools_directory is empty."""

        def _register_if_missing(tool: Tool) -> None:
            if self._engine.get(tool.name) is None:
                self._engine.register(tool)

        _register_if_missing(
            Tool(
                id="tool_echo_builtin",
                name="echo",
                description="Echo back the provided message (offline-safe).",
                category=ToolCategory.CUSTOM,
                status=ToolStatus.PUBLISHED,
                version="1.0.0",
                parameters=[
                    ToolParameter(
                        name="message",
                        type="string",
                        description="Message to echo.",
                        required=False,
                        default="",
                    )
                ],
                returns={},
                implementation_type="builtin",
                implementation_config={"handler": "echo"},
                author="system",
            )
        )
        _register_if_missing(
            Tool(
                id="tool_noop_builtin",
                name="noop",
                description="No-op tool (offline-safe).",
                category=ToolCategory.CUSTOM,
                status=ToolStatus.PUBLISHED,
                version="1.0.0",
                parameters=[],
                returns={},
                implementation_type="builtin",
                implementation_config={"handler": "noop"},
                author="system",
            )
        )

    async def execute(
        self,
        *,
        tool_name: str,
        tool_call_id: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        await self._ensure_loaded()

        tool_name_normalized = (tool_name or "").strip()
        if not tool_name_normalized:
            return ToolCallExecutionPayload(
                success=False,
                result={},
                error="tool_name is required",
                error_type="invalid_request",
            ).to_dict()

        if not isinstance(arguments, dict):
            return ToolCallExecutionPayload(
                success=False,
                result={},
                error="tool arguments must be an object",
                error_type="invalid_request",
            ).to_dict()

        conversation_id = self._conversation_id_provider()
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            return ToolCallExecutionPayload(
                success=False,
                result={},
                error="conversation_id is required",
                error_type="invalid_context",
            ).to_dict()

        workflow_id = None
        if self._workflow_id_provider is not None:
            workflow_id = self._workflow_id_provider()

        run_id = None
        if self._run_id_provider is not None:
            run_id = self._run_id_provider()

        user_message = None
        if self._user_message_provider is not None:
            user_message = self._user_message_provider()

        variables: dict[str, Any] = {
            "tool_call_id": tool_call_id,
        }
        if isinstance(run_id, str) and run_id.strip():
            variables["run_id"] = run_id.strip()

        context = ToolExecutionContext.for_conversation(
            agent_id=self._caller_id,
            conversation_id=conversation_id.strip(),
            user_message=user_message if isinstance(user_message, str) else None,
            timeout=30.0,
            workflow_id=workflow_id.strip()
            if isinstance(workflow_id, str) and workflow_id.strip()
            else None,
            trace_id=tool_call_id.strip() if isinstance(tool_call_id, str) else None,
            variables=variables,
        )

        try:
            result = await self._engine.execute(
                tool_name=tool_name_normalized,
                params=arguments,
                context=context,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - tool boundary
            return ToolCallExecutionPayload(
                success=False,
                result={},
                error=str(exc),
                error_type="execution_error",
            ).to_dict()

        if result.is_success:
            return ToolCallExecutionPayload(
                success=True,
                result=result.output
                if isinstance(result.output, dict)
                else {"value": result.output},
                error=None,
                error_type=None,
            ).to_dict()

        return ToolCallExecutionPayload(
            success=False,
            result={},
            error=str(result.error or "tool execution failed"),
            error_type=str(result.error_type or "execution_error"),
        ).to_dict()
