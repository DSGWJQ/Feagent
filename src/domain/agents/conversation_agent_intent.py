"""ConversationAgent intent classification module.

This module extracts intent classification and routing logic from conversation_agent.py
(P1-6 Phase 6 Step 2).

Scope:
- Intent classification (classify_intent)
- Intent-based routing (process_with_intent)
- Conversation handling (_handle_conversation)
- Workflow query handling (_handle_workflow_query)

Design principles:
- Self-contained intent processing with clear host dependencies
- Minimal coupling to ReAct core logic
- Type-safe intent classification

Host Contract:
The host class (ConversationAgent) must provide:

Required attributes:
- llm: ConversationAgentLLM protocol (classify_intent, generate_response methods)
- session_context: SessionContext (session_id, conversation_history)
- enable_intent_classification: bool (feature flag)
- intent_confidence_threshold: float (confidence threshold)
- event_bus: EventBusProtocol | None (for publishing events)
- emitter: Any | None (ConversationFlowEmitter for streaming)
- _current_input: str | None (current user input)

Required methods (from other mixins):
- get_context_for_reasoning() -> dict[str, Any] (from HelpersMixin)
- run_async(user_input: str) -> ReActResult (from ReActCoreMixin, available during runtime)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.domain.agents.conversation_agent_events import IntentClassificationResult
    from src.domain.agents.conversation_agent_models import ReActResult
    from src.domain.services.context_manager import SessionContext


class ConversationAgentIntentMixin:
    """Intent classification mixin for ConversationAgent (P1-6 Phase 6 Step 2).

    This mixin encapsulates intent classification and routing logic that was
    previously inline in ConversationAgent.

    Methods:
    - classify_intent: Classify user input intent
    - process_with_intent: Route based on intent classification
    - _handle_conversation: Handle normal conversation intents
    - _handle_workflow_query: Handle workflow query intents
    """

    # --- Host-provided attributes (runtime expectations) ---
    llm: Any  # ConversationAgentLLM protocol
    session_context: SessionContext
    enable_intent_classification: bool
    intent_confidence_threshold: float
    event_bus: Any | None  # EventBusProtocol
    emitter: Any | None  # ConversationFlowEmitter
    _current_input: str | None

    # --- Host-provided methods (from other mixins) ---
    # get_context_for_reasoning() -> dict[str, Any]  # from HelpersMixin
    # run_async(user_input: str) -> ReActResult  # from ReActCoreMixin

    # =========================================================================
    # Phase 14: Intent Classification and Routing
    # =========================================================================

    async def classify_intent(self, user_input: str) -> IntentClassificationResult:
        """分类用户输入的意图

        参数:
            user_input: 用户输入

        返回:
            IntentClassificationResult 意图分类结果
        """
        from src.domain.agents.conversation_agent_events import IntentClassificationResult
        from src.domain.agents.conversation_agent_models import IntentType

        # 获取上下文
        context = self.get_context_for_reasoning()  # type: ignore[attr-defined]
        context["user_input"] = user_input

        # 调用 LLM 分类意图
        result_dict = await self.llm.classify_intent(user_input, context)

        # 转换意图类型
        intent_str = result_dict.get("intent", "conversation")
        try:
            intent = IntentType(intent_str)
        except ValueError:
            intent = IntentType.CONVERSATION

        return IntentClassificationResult(
            intent=intent,
            confidence=result_dict.get("confidence", 1.0),
            reasoning=result_dict.get("reasoning", ""),
            extracted_entities=result_dict.get("extracted_entities", {}),
        )

    async def process_with_intent(self, user_input: str) -> ReActResult:
        """基于意图分类处理用户输入

        如果启用意图分类且置信度足够高：
        - 普通对话：直接生成回复，跳过 ReAct 循环
        - 工作流查询：查询状态并返回
        - 工作流修改/错误恢复：使用 ReAct 循环

        参数:
            user_input: 用户输入

        返回:
            ReActResult 处理结果
        """
        from src.domain.agents.conversation_agent_models import IntentType

        self._current_input = user_input

        # 如果未启用意图分类，直接使用 ReAct 循环
        if not self.enable_intent_classification:
            return await self.run_async(user_input)  # type: ignore[attr-defined]

        # 分类意图
        classification = await self.classify_intent(user_input)

        # 如果置信度低于阈值，回退到 ReAct 循环
        if classification.confidence < self.intent_confidence_threshold:
            return await self.run_async(user_input)  # type: ignore[attr-defined]

        # 根据意图类型分流处理
        if classification.intent == IntentType.CONVERSATION:
            # 普通对话：直接生成回复
            return await self._handle_conversation(user_input, classification)

        elif classification.intent == IntentType.WORKFLOW_QUERY:
            # 工作流查询：返回状态信息
            return await self._handle_workflow_query(user_input, classification)

        else:
            # 工作流修改、澄清请求、错误恢复：使用 ReAct 循环
            return await self.run_async(user_input)  # type: ignore[attr-defined]

    async def _handle_conversation(
        self, user_input: str, classification: IntentClassificationResult
    ) -> ReActResult:
        """处理普通对话意图

        直接生成回复，不使用 ReAct 循环。

        参数:
            user_input: 用户输入
            classification: 意图分类结果

        返回:
            ReActResult
        """
        from src.domain.agents.conversation_agent_events import SimpleMessageEvent
        from src.domain.agents.conversation_agent_models import ReActResult

        context = self.get_context_for_reasoning()  # type: ignore[attr-defined]
        context["user_input"] = user_input
        context["intent_classification"] = {
            "intent": classification.intent.value,
            "confidence": classification.confidence,
            "reasoning": classification.reasoning,
        }

        # 直接生成回复
        response = await self.llm.generate_response(user_input, context)

        # 构建结果
        result = ReActResult(
            completed=True,
            final_response=response,
            iterations=0,  # 没有 ReAct 迭代
        )

        # 添加到对话历史
        self.session_context.conversation_history.append({"role": "user", "content": user_input})
        self.session_context.conversation_history.append({"role": "assistant", "content": response})

        # Phase 15: 发布简单消息事件
        if self.event_bus:
            event = SimpleMessageEvent(
                source="conversation_agent",
                user_input=user_input,
                response=response,
                intent=classification.intent.value,
                confidence=classification.confidence,
                session_id=self.session_context.session_id,
            )
            await self.event_bus.publish(event)

        # Phase 2: 发送最终响应到 emitter 并完成（普通对话跳过思考）
        if self.emitter:
            await self.emitter.emit_final_response(response)
            await self.emitter.complete()

        return result

    async def _handle_workflow_query(
        self, user_input: str, classification: IntentClassificationResult
    ) -> ReActResult:
        """处理工作流查询意图

        参数:
            user_input: 用户输入
            classification: 意图分类结果

        返回:
            ReActResult
        """
        from src.domain.agents.conversation_agent_events import SimpleMessageEvent
        from src.domain.agents.conversation_agent_models import ReActResult

        context = self.get_context_for_reasoning()  # type: ignore[attr-defined]
        context["user_input"] = user_input
        context["extracted_entities"] = classification.extracted_entities

        # 如果有专门的工作流状态查询方法
        if hasattr(self.llm, "generate_workflow_status"):
            response = await self.llm.generate_workflow_status(  # type: ignore[attr-defined]
                user_input, context
            )
        else:
            # 回退到通用回复生成
            response = await self.llm.generate_response(user_input, context)

        result = ReActResult(
            completed=True,
            final_response=response,
            iterations=0,
        )

        # Phase 15: 发布简单消息事件
        if self.event_bus:
            event = SimpleMessageEvent(
                source="conversation_agent",
                user_input=user_input,
                response=response,
                intent=classification.intent.value,
                confidence=classification.confidence,
                session_id=self.session_context.session_id,
            )
            await self.event_bus.publish(event)

        # Phase 2: 发送最终响应到 emitter 并完成
        if self.emitter:
            await self.emitter.emit_final_response(response)
            await self.emitter.complete()

        return result
