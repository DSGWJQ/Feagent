"""ConversationTurnOrchestrator - 统一对话入口（含 policy chain）

目标：
- Interface 层不直接持有/调用 Domain Agent
- 将“执行前/执行后/错误治理”等逻辑抽象为可插拔的 policy chain
- 对流式输出通过 ConversationFlowEmitter 统一承载（SSE/WebSocket 均可复用）
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import Any, Protocol, cast

from src.application.services.coordinator_policy_chain import (
    CoordinatorPolicyChain,
    CoordinatorPort,
)
from src.domain.services.conversation_flow_emitter import (
    ConversationFlowEmitter,
    EmitterClosedError,
)
from src.domain.services.event_bus import EventBus

logger = logging.getLogger(__name__)


class ConversationAgentPort(Protocol):
    async def run_async(self, user_input: str) -> Any: ...


class ConversationTurnPolicy(Protocol):
    async def before_turn(
        self,
        *,
        session_id: str,
        message: str,
        context: dict[str, Any] | None,
    ) -> None: ...

    async def after_turn(
        self,
        *,
        session_id: str,
        message: str,
        context: dict[str, Any] | None,
        result: Any,
    ) -> None: ...

    async def on_error(
        self,
        *,
        session_id: str,
        message: str,
        context: dict[str, Any] | None,
        error: Exception,
    ) -> None: ...

    async def on_emit(
        self,
        *,
        session_id: str,
        message: str,
        kind: str,
        payload: Any,
    ) -> None: ...


class ConversationTurnOrchestrator:
    def __init__(
        self,
        *,
        conversation_agent: ConversationAgentPort,
        policies: Iterable[ConversationTurnPolicy] = (),
    ) -> None:
        self._conversation_agent = conversation_agent
        self._policies = list(policies)

    async def run_turn(
        self,
        *,
        session_id: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> Any:
        for policy in self._policies:
            await policy.before_turn(session_id=session_id, message=message, context=context)

        try:
            result = await self._conversation_agent.run_async(message)
        except Exception as exc:  # noqa: BLE001 - orchestrator is the central boundary
            for policy in self._policies:
                await policy.on_error(
                    session_id=session_id,
                    message=message,
                    context=context,
                    error=exc,
                )
            raise

        for policy in reversed(self._policies):
            await policy.after_turn(
                session_id=session_id,
                message=message,
                context=context,
                result=result,
            )

        return result

    async def start_streaming_turn(
        self,
        *,
        session_id: str,
        message: str,
        emitter: ConversationFlowEmitter,
        context: dict[str, Any] | None = None,
    ) -> asyncio.Task[None]:
        for policy in self._policies:
            await policy.before_turn(session_id=session_id, message=message, context=context)

        agent = self._conversation_agent
        if hasattr(agent, "emitter"):
            cast(Any, agent).emitter = emitter
        if hasattr(agent, "stream_emitter"):
            cast(Any, agent).stream_emitter = emitter
        if hasattr(agent, "session_context"):
            session_context = getattr(agent, "session_context", None)
            if session_context is not None and hasattr(session_context, "session_id"):
                session_context.session_id = session_id

        await self._safe_emit(
            session_id=session_id,
            message=message,
            emitter=emitter,
            kind="thinking",
            emit=lambda: emitter.emit_thinking(f"收到消息：{message[:50]}..."),
        )

        return asyncio.create_task(
            self._run_streaming_turn(
                session_id=session_id,
                message=message,
                context=context,
                emitter=emitter,
            )
        )

    async def _run_streaming_turn(
        self,
        *,
        session_id: str,
        message: str,
        context: dict[str, Any] | None,
        emitter: ConversationFlowEmitter,
    ) -> None:
        try:
            result = await self._conversation_agent.run_async(message)
            final_response = getattr(result, "final_response", None) or getattr(
                result, "response", None
            )
            if final_response is None:
                final_response = "处理完成"

            await self._safe_emit(
                session_id=session_id,
                message=message,
                emitter=emitter,
                kind="final",
                emit=lambda: emitter.emit_final_response(str(final_response)),
            )
            await self._safe_complete(emitter)

            for policy in reversed(self._policies):
                await policy.after_turn(
                    session_id=session_id,
                    message=message,
                    context=context,
                    result=result,
                )
        except asyncio.CancelledError:
            await self._safe_complete(emitter)
            raise
        except EmitterClosedError:
            return
        except Exception as exc:  # noqa: BLE001 - orchestrator is the central boundary
            logger.exception("Conversation streaming turn failed: session=%s", session_id)
            for policy in self._policies:
                await policy.on_error(
                    session_id=session_id,
                    message=message,
                    context=context,
                    error=exc,
                )

            error_message = str(exc)
            await self._safe_emit(
                session_id=session_id,
                message=message,
                emitter=emitter,
                kind="error",
                emit=lambda msg=error_message: emitter.emit_error(
                    msg, error_code="CONVERSATION_ERROR"
                ),
            )
            await self._safe_complete(emitter)

    async def _safe_emit(
        self,
        *,
        session_id: str,
        message: str,
        emitter: ConversationFlowEmitter,
        kind: str,
        emit: Any,
    ) -> None:
        try:
            await emit()
        except EmitterClosedError:
            return
        for policy in self._policies:
            await policy.on_emit(session_id=session_id, message=message, kind=kind, payload=None)

    async def _safe_complete(self, emitter: ConversationFlowEmitter) -> None:
        try:
            await emitter.complete()
        except EmitterClosedError:
            return


class NoopConversationTurnPolicy:
    async def before_turn(
        self, *, session_id: str, message: str, context: dict[str, Any] | None
    ) -> None:
        return None

    async def after_turn(
        self,
        *,
        session_id: str,
        message: str,
        context: dict[str, Any] | None,
        result: Any,
    ) -> None:
        return None

    async def on_error(
        self,
        *,
        session_id: str,
        message: str,
        context: dict[str, Any] | None,
        error: Exception,
    ) -> None:
        return None

    async def on_emit(self, *, session_id: str, message: str, kind: str, payload: Any) -> None:
        return None


class CoordinatorConversationTurnPolicy:
    """将对话入口的监督点下沉到 Application policy chain（WF-060）。

    注意：不把 message 明文透传给 coordinator，避免潜在敏感信息泄露。
    """

    def __init__(
        self,
        *,
        coordinator: CoordinatorPort | None,
        event_bus: EventBus | None,
        source: str,
        fail_closed: bool = True,
    ) -> None:
        self._policy = CoordinatorPolicyChain(
            coordinator=coordinator,
            event_bus=event_bus,
            source=source,
            fail_closed=fail_closed,
            supervised_decision_types={"api_request"},
        )

    async def before_turn(
        self,
        *,
        session_id: str,
        message: str,
        context: dict[str, Any] | None,
    ) -> None:
        workflow_id = None
        if isinstance(context, dict):
            workflow_id = context.get("workflow_id")

        await self._policy.enforce_action_or_raise(
            decision_type="api_request",
            decision={
                "decision_type": "api_request",
                "action": "conversation_turn",
                "session_id": session_id,
                "workflow_id": workflow_id,
                "message_len": len(message or ""),
            },
            correlation_id=session_id,
            original_decision_id=session_id,
        )

    async def after_turn(
        self,
        *,
        session_id: str,
        message: str,
        context: dict[str, Any] | None,
        result: Any,
    ) -> None:
        return None

    async def on_error(
        self,
        *,
        session_id: str,
        message: str,
        context: dict[str, Any] | None,
        error: Exception,
    ) -> None:
        return None

    async def on_emit(
        self,
        *,
        session_id: str,
        message: str,
        kind: str,
        payload: Any,
    ) -> None:
        return None
