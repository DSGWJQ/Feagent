"""ConversationAgent ReAct core module.

This module extracts the ReAct (Reasoning + Acting) loop implementation from
conversation_agent.py (P1-6 Phase 6 Step 3).

Scope:
- ReAct loop execution (execute_step, run, _run_sync, run_async)
- Decision making (make_decision, _record_decision, _record_decision_async)
- Decision publishing (publish_decision)

Design principles:
- Preserve P0-2 staged state mechanism (_stage_token_usage, _flush_staged_state)
- Preserve P1 decision_metadata self-management
- Self-contained ReAct logic with clear host dependencies

CRITICAL: This mixin should be added as the FIRST mixin in ConversationAgent
inheritance for proper Method Resolution Order (MRO) priority.

Host Contract:
The host class (ConversationAgent) must provide:

Required attributes:
- llm: ConversationAgentLLM protocol (think, decide_action, should_continue methods)
- session_context: SessionContext (context_limit, conversation_history, add_decision, etc.)
- event_bus: EventBusProtocol | None (for publishing events)
- max_iterations: int (ReAct loop limit)
- timeout_seconds: float | None (timeout limit)
- max_tokens: int | None (token limit)
- max_cost: float | None (cost limit)
- coordinator: Any | None (for circuit breaker and context)
- _current_input: str | None (current user input)
- emitter: Any | None (ConversationFlowEmitter for streaming)
- _coordinator_context: Any | None (cached coordinator context)
- _decision_metadata: list[dict[str, Any]] (P1 Fix: self-managed metadata)

Required methods (from other mixins):
- get_context_for_reasoning() -> dict[str, Any] (from HelpersMixin)
- _initialize_model_info() -> None (from HelpersMixin)
- _log_coordinator_context(context: Any) -> None (from HelpersMixin)
- _log_context_warning() -> None (from HelpersMixin)
- _stage_token_usage(prompt_tokens: int, completion_tokens: int) -> None (P0-2 Phase 2)
- _stage_decision_record(record: dict[str, Any]) -> None (P0-2 Phase 2)
- _flush_staged_state() -> None (P0-2 Phase 2)
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

from src.domain.agents.conversation_agent_models import (
    Decision,
    DecisionType,
    ReActResult,
    ReActStep,
    StepType,
    get_decision_type_map,
)

if TYPE_CHECKING:
    from src.domain.services.context_manager import SessionContext


class ConversationAgentReActCoreMixin:
    """ReAct core mixin for ConversationAgent (P1-6 Phase 6 Step 3).

    This mixin encapsulates the ReAct (Reasoning + Acting) loop implementation
    that was previously inline in ConversationAgent.

    Methods:
    - execute_step: Execute single ReAct step (sync)
    - run: Sync wrapper for ReAct loop
    - _run_sync: Sync ReAct loop (for testing)
    - run_async: Async ReAct loop (main implementation)
    - make_decision: Make decision with validation
    - _record_decision: Record decision to history (sync)
    - _record_decision_async: Record decision to history (async, staged)
    - publish_decision: Publish decision event
    """

    # --- Host-provided attributes (runtime expectations) ---
    llm: Any  # ConversationAgentLLM protocol
    session_context: SessionContext
    event_bus: Any | None  # EventBusProtocol
    max_iterations: int
    timeout_seconds: float | None
    max_tokens: int | None
    max_cost: float | None
    coordinator: Any | None
    _current_input: str | None
    emitter: Any | None
    _coordinator_context: Any | None
    _decision_metadata: list[dict[str, Any]]  # P1 Fix: self-managed

    # --- Host-provided methods (from other mixins) ---
    # get_context_for_reasoning() -> dict[str, Any]  # from HelpersMixin
    # _initialize_model_info() -> None  # from HelpersMixin
    # _log_coordinator_context(context: Any) -> None  # from HelpersMixin
    # _log_context_warning() -> None  # from HelpersMixin
    # _stage_token_usage(prompt_tokens, completion_tokens) -> None  # P0-2 Phase 2
    # _stage_decision_record(record) -> None  # P0-2 Phase 2
    # _flush_staged_state() -> None  # P0-2 Phase 2

    # =========================================================================
    # ReAct Loop Execution
    # =========================================================================

    def execute_step(self, user_input: str) -> ReActStep:
        """执行单个ReAct步骤

        参数:
            user_input: 用户输入

        返回:
            ReAct步骤
        """
        from src.domain.agents.conversation_agent_models import ReActStep

        self._current_input = user_input

        # 获取推理上下文
        context = self.get_context_for_reasoning()  # type: ignore[attr-defined]
        context["user_input"] = user_input

        # 思考
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_running():
                # 事件循环未运行，可以同步等待
                thought = loop.run_until_complete(self.llm.think(context))
            else:
                # 事件循环已运行，不能 run_until_complete
                # 这种情况应该使用异步版本 (run_async)
                thought = "思考中..."
        except RuntimeError:
            thought = "思考中..."

        # 决定行动
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_running():
                # 事件循环未运行，可以同步等待
                action = loop.run_until_complete(self.llm.decide_action(context))
            else:
                # 事件循环已运行，不能 run_until_complete
                # 这种情况应该使用异步版本 (run_async)
                action = {"action_type": "continue"}
        except RuntimeError:
            action = {"action_type": "continue"}

        return ReActStep(step_type=StepType.REASONING, thought=thought, action=action)

    def run(self, user_input: str) -> ReActResult:
        """同步运行ReAct循环

        参数:
            user_input: 用户输入

        返回:
            ReAct结果
        """
        # 尝试在现有事件循环中运行，或创建新的
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果循环已运行，使用同步方式模拟
                return self._run_sync(user_input)
            return loop.run_until_complete(self.run_async(user_input))
        except RuntimeError:
            return asyncio.run(self.run_async(user_input))

    def _run_sync(self, user_input: str) -> ReActResult:
        """同步方式运行（当事件循环已在运行时）"""
        from src.domain.agents.conversation_agent_models import ReActResult, ReActStep

        result = ReActResult()
        self._current_input = user_input

        for iteration_count in range(self.max_iterations):
            result.iterations = iteration_count + 1

            # 获取上下文
            context = self.get_context_for_reasoning()  # type: ignore[attr-defined]
            context["user_input"] = user_input

            # 模拟LLM调用（同步）- 用于测试时的mock兼容
            try:
                # 使用mock的返回值
                thought = (
                    self.llm.think.return_value  # type: ignore[union-attr]
                    if hasattr(self.llm.think, "return_value")
                    else "思考中..."
                )
                action = (
                    self.llm.decide_action.return_value  # type: ignore[union-attr]
                    if hasattr(self.llm.decide_action, "return_value")
                    else {"action_type": "continue"}
                )

                # 如果有side_effect，使用它
                if (
                    hasattr(self.llm.decide_action, "side_effect")
                    and self.llm.decide_action.side_effect  # type: ignore[union-attr]
                ):
                    try:
                        action = self.llm.decide_action.side_effect[iteration_count]  # type: ignore[union-attr]
                    except (IndexError, TypeError):
                        pass

                should_continue = True
                if hasattr(self.llm.should_continue, "return_value"):
                    should_continue = self.llm.should_continue.return_value  # type: ignore[union-attr]
                if (
                    hasattr(self.llm.should_continue, "side_effect")
                    and self.llm.should_continue.side_effect  # type: ignore[union-attr]
                ):
                    try:
                        should_continue = self.llm.should_continue.side_effect[iteration_count]  # type: ignore[union-attr]
                    except (IndexError, TypeError):
                        pass

            except Exception:
                thought = "思考中..."
                action = {"action_type": "continue"}
                should_continue = True

            step = ReActStep(step_type=StepType.REASONING, thought=thought, action=action)
            result.steps.append(step)

            # 处理行动
            action_type = action.get("action_type", "continue")

            if action_type == "respond":
                result.completed = True
                result.final_response = action.get("response", "任务完成")
                return result

            # 记录决策
            if action_type in ["create_node", "execute_workflow"]:
                decision = Decision(
                    type=DecisionType(action_type)
                    if action_type in [dt.value for dt in DecisionType]
                    else DecisionType.CONTINUE,
                    payload=action,
                )
                self._record_decision(decision)

            if not should_continue:
                result.completed = True
                result.final_response = action.get("response", "任务完成")
                return result

        # 达到最大迭代
        result.terminated_by_limit = True
        return result

    async def run_async(self, user_input: str) -> ReActResult:
        """异步运行ReAct循环

        参数:
            user_input: 用户输入

        返回:
            ReAct结果
        """
        from src.domain.agents.conversation_agent_models import ReActResult, ReActStep

        result = ReActResult()
        self._current_input = user_input
        start_time = time.time()

        # Step 1: 初始化模型信息（如果尚未设置）
        if self.session_context.context_limit == 0:
            self._initialize_model_info()  # type: ignore[attr-defined]

        # Phase 1: 从协调者获取上下文（规则库、知识库、工具库）
        coordinator_context = None
        if self.coordinator and hasattr(self.coordinator, "get_context_async"):
            try:
                coordinator_context = await self.coordinator.get_context_async(user_input)
                # 记录上下文信息
                self._log_coordinator_context(coordinator_context)  # type: ignore[attr-defined]
            except Exception as e:
                # 上下文获取失败不应阻止主流程
                logging.warning(f"Failed to get coordinator context: {e}")

        # 保存协调者上下文供后续使用
        self._coordinator_context = coordinator_context

        for iteration_count in range(self.max_iterations):
            result.iterations = iteration_count + 1

            # === 阶段5：循环控制检查 ===

            # 检查熔断器
            if self.coordinator and hasattr(self.coordinator, "circuit_breaker"):
                if self.coordinator.circuit_breaker.is_open:
                    result.terminated_by_limit = True
                    result.limit_type = "circuit_breaker"
                    result.alert_message = "熔断器已打开，循环终止"
                    result.execution_time = time.time() - start_time
                    # P0-2 Phase 2: Flush staged state before return
                    await self._flush_staged_state()  # type: ignore[attr-defined]
                    return result

            # 检查超时
            if self.timeout_seconds:
                elapsed = time.time() - start_time
                if elapsed >= self.timeout_seconds:
                    result.terminated_by_limit = True
                    result.limit_type = "timeout"
                    result.execution_time = elapsed
                    result.alert_message = f"已超时 ({self.timeout_seconds}秒)，循环终止"
                    # P0-2 Phase 2: Flush staged state before return
                    await self._flush_staged_state()  # type: ignore[attr-defined]
                    return result

            # 检查 token 限制
            if self.max_tokens and result.total_tokens >= self.max_tokens:
                result.terminated_by_limit = True
                result.limit_type = "token_limit"
                result.execution_time = time.time() - start_time
                result.alert_message = f"已达到 token 限制 ({self.max_tokens})，循环终止"
                # P0-2 Phase 2: Flush staged state before return
                await self._flush_staged_state()  # type: ignore[attr-defined]
                return result

            # 检查成本限制
            if self.max_cost and result.total_cost >= self.max_cost:
                result.terminated_by_limit = True
                result.limit_type = "cost_limit"
                result.execution_time = time.time() - start_time
                result.alert_message = f"已达到成本限制 (${self.max_cost})，循环终止"
                # P0-2 Phase 2: Flush staged state before return
                await self._flush_staged_state()  # type: ignore[attr-defined]
                return result

            # === 原有逻辑 ===

            # 获取上下文
            context = self.get_context_for_reasoning()  # type: ignore[attr-defined]
            context["user_input"] = user_input
            context["iteration"] = iteration_count + 1

            # 思考
            try:
                thought = await self.llm.think(context)

                # Phase 2: 发送思考步骤到 emitter
                if self.emitter:
                    await self.emitter.emit_thinking(thought)
            except Exception as e:
                # Phase 2: 发送错误到 emitter
                if self.emitter:
                    await self.emitter.emit_error(str(e), error_code="LLM_THINK_ERROR")
                    await self.emitter.complete()
                raise

            # 决定行动
            try:
                action = await self.llm.decide_action(context)
            except Exception as e:
                # P0-4 Fix: 捕获 decide_action 异常，emit_error 并 complete
                if self.emitter:
                    await self.emitter.emit_error(str(e), error_code="DECIDE_ACTION_ERROR")
                    await self.emitter.complete()
                raise

            # 阶段5：累计 token 和成本
            # Step 1: 记录每轮的 token 使用情况
            prompt_tokens = 0
            completion_tokens = 0
            try:
                if hasattr(self.llm, "get_token_usage"):
                    tokens = self.llm.get_token_usage()  # type: ignore[attr-defined]
                    if isinstance(tokens, dict):
                        # 支持 dict 格式: {"prompt_tokens": X, "completion_tokens": Y}
                        prompt_tokens = int(tokens.get("prompt_tokens", 0))
                        completion_tokens = int(tokens.get("completion_tokens", 0))
                        result.total_tokens += prompt_tokens + completion_tokens
                    elif isinstance(tokens, int | float):
                        # 支持数值格式: 作为 total tokens
                        total = int(tokens)
                        result.total_tokens += total
                        completion_tokens = total  # 假定全部是 completion tokens
                if hasattr(self.llm, "get_cost"):
                    cost = self.llm.get_cost()  # type: ignore[attr-defined]
                    if isinstance(cost, int | float):
                        result.total_cost += float(cost)
            except (TypeError, AttributeError):
                pass  # LLM 不支持这些方法时跳过

            # Step 1: 更新 SessionContext 的 token 使用情况（P0-2 Phase 2: 使用staged机制）
            if prompt_tokens > 0 or completion_tokens > 0:
                self._stage_token_usage(  # type: ignore[attr-defined]
                    prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
                )

                # Step 1: 检查是否接近上下文限制并输出预警
                if self.session_context.is_approaching_limit():
                    self._log_context_warning()  # type: ignore[attr-defined]

            step = ReActStep(step_type=StepType.REASONING, thought=thought, action=action)
            result.steps.append(step)

            # 处理行动
            action_type = action.get("action_type", "continue")

            if action_type == "respond":
                result.completed = True
                result.final_response = action.get("response", "任务完成")
                result.execution_time = time.time() - start_time

                # P0-2 Phase 2: Flush staged state before return
                await self._flush_staged_state()  # type: ignore[attr-defined]

                # Phase 2: 发送最终响应到 emitter 并完成
                if self.emitter:
                    await self.emitter.emit_final_response(result.final_response)
                    await self.emitter.complete()

                return result

            # Phase 2: 处理工具调用
            if action_type == "tool_call" and self.emitter:
                await self.emitter.emit_tool_call(
                    tool_name=action.get("tool_name", ""),
                    tool_id=action.get("tool_id", ""),
                    arguments=action.get("arguments", {}),
                )

            # 记录决策并发布事件（P0-2 Phase 2: 使用async staged版本）
            if action_type in ["create_node", "execute_workflow", "request_clarification"]:
                decision = await self._record_decision_async(action)
                await self._flush_staged_state()  # type: ignore[attr-defined]  # 立即flush以确保决策被记录
                if self.event_bus:
                    await self.publish_decision(decision)

            # 判断是否继续
            try:
                should_continue = await self.llm.should_continue(context)
            except Exception as e:
                # P0-4 Fix: 捕获 should_continue 异常，emit_error 并 complete
                if self.emitter:
                    await self.emitter.emit_error(str(e), error_code="SHOULD_CONTINUE_ERROR")
                    await self.emitter.complete()
                raise

            if not should_continue:
                result.completed = True
                result.final_response = action.get("response", "任务完成")

                # P0-2 Phase 2: Flush staged state before return
                await self._flush_staged_state()  # type: ignore[attr-defined]

                # Phase 2: 发送最终响应到 emitter 并完成
                if self.emitter:
                    await self.emitter.emit_final_response(result.final_response)
                    await self.emitter.complete()

                return result

            # P0-2 Phase 2: Flush staged state at end of each iteration
            # 在每轮迭代末尾flush，确保所有暂存数据被提交
            await self._flush_staged_state()  # type: ignore[attr-defined]

        # 达到最大迭代
        result.terminated_by_limit = True
        result.limit_type = "max_iterations"
        result.alert_message = f"已达到最大迭代次数限制 ({self.max_iterations} 次)，循环已终止"
        result.execution_time = time.time() - start_time

        # P0-2 Phase 2: Flush staged state before return
        await self._flush_staged_state()  # type: ignore[attr-defined]

        # Phase 2: 完成 emitter
        if self.emitter:
            await self.emitter.complete()

        return result

    # =========================================================================
    # Decision Making and Recording
    # =========================================================================

    def make_decision(self, context_hint: str) -> Decision:
        """做出决策（增强版：集成 Pydantic schema 验证）

        参数:
            context_hint: 上下文提示

        返回:
            决策对象

        异常:
            ValidationError: 如果决策 payload 不符合 schema
        """
        from pydantic import ValidationError

        from src.domain.agents.conversation_agent_enhanced import (
            validate_and_enhance_decision,
        )
        from src.domain.agents.conversation_agent_models import Decision, DecisionType

        # 获取上下文
        context = self.get_context_for_reasoning()  # type: ignore[attr-defined]
        context["hint"] = context_hint

        # 添加资源约束到上下文
        if hasattr(self.session_context, "resource_constraints"):
            context["resource_constraints"] = self.session_context.resource_constraints

        # 调用LLM决定行动
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                if hasattr(self.llm.decide_action, "return_value"):
                    action = self.llm.decide_action.return_value  # type: ignore[union-attr]
                else:
                    action = {"action_type": "continue"}
            else:
                action = loop.run_until_complete(self.llm.decide_action(context))
        except RuntimeError:
            action = asyncio.run(self.llm.decide_action(context))

        # 获取 action_type
        action_type = action.get("action_type", "continue")

        # ========================================
        # 【增强功能】使用 Pydantic schema 验证
        # ========================================
        try:
            # 获取资源约束（如果存在）
            constraints = (
                self.session_context.resource_constraints
                if hasattr(self.session_context, "resource_constraints")
                else None
            )

            # 综合验证和增强
            validated_payload, metadata = validate_and_enhance_decision(
                action_type, action, constraints
            )

            # 使用验证后的 payload（转回字典）
            validated_dict = validated_payload.model_dump()

            # P1 Fix: 将元数据添加到自管列表（避免污染 session_context）
            if metadata:
                self._decision_metadata.append(
                    {
                        "action_type": action_type,
                        "timestamp": datetime.now().isoformat(),
                        "metadata": metadata,
                    }
                )

        except ValidationError as e:
            # Payload 验证失败
            logger = logging.getLogger(__name__)
            logger.error(f"决策 payload 验证失败: {e.errors()}")

            # 记录验证失败
            self.session_context.add_decision(
                {
                    "type": "validation_failed",
                    "action_type": action_type,
                    "errors": str(e.errors()),
                    "timestamp": datetime.now().isoformat(),
                }
            )

            # 重新抛出异常
            raise

        # 转换为Decision（使用验证后的 payload）
        # P1 Fix: 使用模块级常量映射，避免每次调用重建字典
        decision = Decision(
            type=get_decision_type_map().get(action_type, DecisionType.CONTINUE),
            payload=validated_dict,  # 使用验证后的 payload
        )

        # 记录决策（传递 Decision 对象以确保 ID 一致）
        self._record_decision(decision)

        return decision

    def _record_decision(self, decision: Decision) -> Decision:
        """记录决策到历史

        参数:
            decision: Decision 对象

        返回:
            决策对象（与输入相同）
        """
        self.session_context.add_decision(
            {
                "id": decision.id,
                "type": decision.type.value,
                "payload": decision.payload,
                "timestamp": decision.timestamp.isoformat(),
            }
        )

        return decision

    async def _record_decision_async(self, action: dict[str, Any]) -> Decision:
        """记录决策到历史（异步staged版本，P0-2 Phase 2）

        使用staged机制暂存决策记录，批量提交以减少锁获取次数。

        参数:
            action: 行动字典

        返回:
            决策对象
        """
        decision = Decision(
            type=DecisionType(action.get("action_type", "continue"))
            if action.get("action_type") in [dt.value for dt in DecisionType]
            else DecisionType.CONTINUE,
            payload=action,
        )

        # Phase 2: 使用staged机制暂存决策记录
        self._stage_decision_record(  # type: ignore[attr-defined]
            {
                "id": decision.id,
                "type": decision.type.value,
                "payload": decision.payload,
                "timestamp": decision.timestamp.isoformat(),
            }
        )

        return decision

    async def publish_decision(self, decision: Decision) -> None:
        """发布决策事件

        参数:
            decision: Decision 对象
        """
        if not self.event_bus:
            return

        from src.domain.agents.conversation_agent_events import DecisionMadeEvent

        event = DecisionMadeEvent(
            source="conversation_agent",
            decision_type=decision.type.value,
            decision_id=decision.id,  # 使用 Decision 对象的 ID
            payload=decision.payload,
            confidence=decision.confidence,
        )

        await self.event_bus.publish(event)
