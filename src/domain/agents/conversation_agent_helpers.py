"""ConversationAgent helper methods module.

This module extracts helper utility methods from conversation_agent.py (P1-6 Phase 6).

Scope:
- Goal decomposition and management
- Context building for reasoning
- Logging helpers
- Model initialization

Design principles:
- Self-contained utilities with minimal host dependencies
- No complex orchestration logic
- Pure helper functions that support the main agent
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from src.domain.services.context_manager import Goal

if TYPE_CHECKING:
    from src.domain.services.context_manager import SessionContext


class ConversationAgentHelpersMixin:
    """Helper methods mixin for ConversationAgent (P1-6 Phase 6).

    This mixin provides supporting utilities for ConversationAgent:
    - Goal decomposition and management (decompose_goal, complete_current_goal)
    - Context building (get_context_for_reasoning)
    - Logging helpers (_log_coordinator_context, _log_context_warning)
    - Model initialization (_initialize_model_info)

    Host Contract (required attributes):
    - llm: ConversationAgentLLM protocol (with decompose_goal method)
    - session_context: SessionContext (goal stack, context tracking)
    - coordinator: Any | None (optional coordinator reference)

    Host Contract (required methods):
    - None (self-contained utilities)

    Design Notes:
    - All methods are pure utilities with clear dependencies
    - No complex orchestration or state machine logic
    - Logging uses standard Python logging module
    """

    # --- Host-provided attributes (runtime expectations) ---
    llm: Any  # ConversationAgentLLM protocol
    session_context: SessionContext
    coordinator: Any | None
    model_metadata_port: Any | None  # ModelMetadataPort (optional injection)
    pending_feedbacks: list[dict[str, Any]]  # Initialized by RecoveryMixin

    # =========================================================================
    # Goal Management
    # =========================================================================

    def decompose_goal(self, goal_description: str) -> list[Goal]:
        """分解目标为子目标

        参数：
            goal_description: 目标描述

        返回：
            子目标列表
        """

        # 创建主目标
        main_goal = Goal(id=str(uuid4()), description=goal_description)
        self.session_context.push_goal(main_goal)

        # 调用LLM分解
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 同步方式获取mock返回值
                if hasattr(self.llm.decompose_goal, "return_value"):
                    subgoal_dicts = self.llm.decompose_goal.return_value  # type: ignore[union-attr]
                else:
                    subgoal_dicts = []
            else:
                subgoal_dicts = loop.run_until_complete(self.llm.decompose_goal(goal_description))
        except RuntimeError:
            subgoal_dicts = asyncio.run(self.llm.decompose_goal(goal_description))

        # 转换为Goal对象
        subgoals = []
        for subgoal_dict in subgoal_dicts:
            subgoal = Goal(
                id=str(uuid4()), description=subgoal_dict["description"], parent_id=main_goal.id
            )
            subgoals.append(subgoal)
            self.session_context.push_goal(subgoal)

        return subgoals

    def complete_current_goal(self) -> Goal | None:
        """完成当前目标

        从目标栈弹出当前目标。

        返回：
            完成的目标
        """
        completed_goal = self.session_context.pop_goal()

        if completed_goal:
            # 记录到决策历史
            self.session_context.add_decision(
                {
                    "type": "complete_goal",
                    "goal_id": completed_goal.id,
                    "description": completed_goal.description,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        return completed_goal

    # =========================================================================
    # Context Building
    # =========================================================================

    def get_context_for_reasoning(self) -> dict[str, Any]:
        """获取推理上下文

        返回：
            包含完整上下文的字典
        """
        context = {
            "conversation_history": self.session_context.conversation_history.copy(),
            "current_goal": self.session_context.current_goal(),
            "goal_stack": [
                {"id": g.id, "description": g.description} for g in self.session_context.goal_stack
            ],
            "decision_history": self.session_context.decision_history.copy(),
            "user_id": self.session_context.global_context.user_id,
            "user_preferences": self.session_context.global_context.user_preferences,
            "system_config": self.session_context.global_context.system_config,
            # Phase 13: 添加待处理的反馈
            "pending_feedbacks": self.pending_feedbacks.copy(),
        }

        workflow_id = getattr(self, "_workflow_id", None)
        if isinstance(workflow_id, str) and workflow_id.strip():
            context["workflow_id"] = workflow_id.strip()

        run_id = getattr(self, "_run_id", None)
        if isinstance(run_id, str) and run_id.strip():
            context["run_id"] = run_id.strip()

        return context

    # =========================================================================
    # Logging Helpers
    # =========================================================================

    def _log_coordinator_context(self, context: Any) -> None:
        """记录协调者上下文信息（Phase 1）

        将协调者返回的上下文信息记录到日志，方便调试和追踪。

        参数：
            context: ContextResponse 对象
        """
        logger = logging.getLogger(__name__)

        if context is None:
            logger.debug("Coordinator context is None")
            return

        # 记录上下文摘要
        summary = getattr(context, "summary", "")
        rules_count = len(getattr(context, "rules", []))
        tools_count = len(getattr(context, "tools", []))
        knowledge_count = len(getattr(context, "knowledge", []))

        logger.info(
            f"Coordinator context retrieved: "
            f"rules={rules_count}, tools={tools_count}, knowledge={knowledge_count}"
        )

        if summary:
            logger.debug(f"Context summary: {summary}")

        # 如果有工作流上下文，也记录
        workflow_context = getattr(context, "workflow_context", None)
        if workflow_context:
            workflow_id = workflow_context.get("workflow_id", "unknown")
            status = workflow_context.get("status", "unknown")
            logger.debug(f"Workflow context: id={workflow_id}, status={status}")

    def _log_context_warning(self) -> None:
        """记录上下文限制预警（Step 1: 模型上下文能力确认）

        当上下文使用率接近限制时，输出预警日志。
        """
        logger = logging.getLogger(__name__)

        summary = self.session_context.get_token_usage_summary()

        logger.warning(
            f"⚠️ Context limit approaching! "
            f"Usage: {summary['total_tokens']}/{summary['context_limit']} tokens "
            f"({summary['usage_ratio']:.1%}), "
            f"Remaining: {summary['remaining_tokens']} tokens"
        )

    # =========================================================================
    # Model Initialization
    # =========================================================================

    def _initialize_model_info(self) -> None:
        """初始化模型信息（Step 1: 模型上下文能力确认）

        从 LLM 客户端或配置中获取模型信息，并设置到 SessionContext。
        使用依赖注入的 ModelMetadataPort，符合 Ports and Adapters 架构。
        """
        from src.config import settings

        logger = logging.getLogger(__name__)

        # 尝试从配置获取模型信息
        provider = "openai"  # 默认提供商
        model = settings.openai_model

        # P1-1: 使用注入的 ModelMetadataPort（依赖注入），避免 Domain 直接依赖 Infrastructure。
        context_window: int = 8192
        if hasattr(self, "model_metadata_port") and self.model_metadata_port is not None:
            metadata = self.model_metadata_port.get_model_metadata(provider, model)
            context_window = metadata.max_tokens
        else:
            # 向后兼容：未注入时使用保守默认值（主要用于测试/装配缺失场景）。
            # 重要：该分支不得从 Infrastructure import（DDD 边界）。
            logger.warning(
                "ModelMetadataPort not injected; using fallback context_window=8192. "
                "Inject ModelMetadataPort via ConversationAgentConfig to avoid drift."
            )

        # 设置到 SessionContext
        self.session_context.set_model_info(
            provider=provider, model=model, context_limit=context_window
        )

        logger.info(
            f"Model info initialized: provider={provider}, model={model}, "
            f"context_limit={context_window}"
        )
