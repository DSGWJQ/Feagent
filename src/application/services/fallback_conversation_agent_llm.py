from __future__ import annotations

from typing import Any


class FallbackConversationAgentLLM:
    """
    Offline-safe fallback implementation for ConversationAgentLLM.

    - KISS: deterministic, no network calls.
    - Defensive: always returns minimally valid shapes for the agent mixins.
    """

    async def think(self, context: dict[str, Any]) -> str:
        user_input = str(context.get("user_input", "")).strip()
        if not user_input:
            return "收到空输入，等待有效消息。"
        return "收到请求，开始处理并生成响应。"

    async def decide_action(self, context: dict[str, Any]) -> dict[str, Any]:
        user_input = str(context.get("user_input", "")).lower()

        # Allow an explicit local trigger to exercise coordinator deny path.
        if "deny" in user_input or "reject" in user_input:
            return {
                "action_type": "create_node",
                "node_type": "HTTP",
                "node_name": "invalid_node_for_validation",
                "config": {},
                "description": "intentionally invalid to exercise coordinator rejection",
                "response": "已触发拒绝路径（deny/reject）。",
            }

        return {
            "action_type": "respond",
            "response": "（fallback）服务已启动，但未配置真实 LLM；当前为离线降级回复。",
            "intent": "simple_query",
            "confidence": 1.0,
            "requires_followup": False,
        }

    async def should_continue(self, context: dict[str, Any]) -> bool:
        return False

    async def decompose_goal(self, goal: str) -> list[dict[str, Any]]:
        goal = goal.strip()
        if not goal:
            return []
        return [{"name": "理解目标", "description": goal}]

    async def plan_workflow(self, goal: str, context: dict[str, Any]) -> dict[str, Any]:
        return {"name": "fallback_plan", "description": goal.strip(), "nodes": [], "edges": []}

    async def replan_workflow(
        self, goal: str, context: dict[str, Any], failure_reason: str | None = None
    ) -> dict[str, Any]:
        return {
            "name": "fallback_replan",
            "description": goal.strip(),
            "failure_reason": failure_reason or "",
            "nodes": [],
            "edges": [],
        }

    async def classify_intent(self, user_input: str, context: dict[str, Any]) -> dict[str, Any]:
        text = (user_input or "").strip()
        if not text:
            return {"intent": "conversation", "confidence": 1.0, "reasoning": "empty input"}
        return {"intent": "conversation", "confidence": 1.0, "reasoning": "fallback deterministic"}

    async def generate_response(self, user_input: str, context: dict[str, Any]) -> str:
        _ = context
        return f"（fallback）{(user_input or '').strip()}"
