from __future__ import annotations

import logging
import re
from typing import Any

from src.domain.ports.llm_port import LLMPort

logger = logging.getLogger(__name__)

# Keywords that indicate the model is attempting to return a structured control payload
# (or to trigger privileged actions). We must fail-closed and return safe natural-language
# clarification instead of executing or echoing the payload.
_PRIVILEGED_MARKERS = (
    "action_type",
    "tool_call",
    "create_node",
    "execute_workflow",
    "create_workflow_plan",
    "modify_node",
    "spawn_subagent",
)

_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def _strip_code_fences(text: str) -> str:
    return _CODE_FENCE_RE.sub("", text).strip()


def _looks_like_json(text: str) -> bool:
    s = text.strip()
    if not s:
        return False
    if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
        return True
    return False


def _contains_privileged_markers(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _PRIVILEGED_MARKERS)


def _limit_questions(text: str, *, max_questions: int = 3) -> str:
    """Fail-safe: keep at most N question marks (Chinese/English)."""
    s = text.strip()
    if not s:
        return s

    count = 0
    for i, ch in enumerate(s):
        if ch in ("?", "？"):
            count += 1
            if count >= max_questions:
                return s[: i + 1].strip()
    return s


def _fallback_questions(_user_input: str) -> str:
    # Keep this deterministic for CI (stub LLM returns JSON by default).
    # Contract: 1–3 high-signal questions, natural language only.
    return (
        "1) 你希望最终产出什么（例如报告、表格、通知、API 响应）？\n"
        "2) 输入数据从哪里来（文件、数据库、接口、手动粘贴）？\n"
        "3) 有哪些约束（频率、权限、成本、时限）？"
    )


def _sanitize_or_fallback(model_text: str, *, user_input: str) -> str:
    text = _strip_code_fences(model_text or "")
    if not text:
        return _fallback_questions(user_input)

    # If the model returns a control payload (JSON) or hints at privileged actions,
    # never echo it back verbatim. Fail-closed to a safe clarification response.
    if _looks_like_json(text) or _contains_privileged_markers(text):
        logger.info(
            "conversation_clarifier_output_blocked",
            extra={
                "reason": "json_or_privileged_markers",
                "output_len": len(text),
                "message_len": len(user_input or ""),
            },
        )
        return _fallback_questions(user_input)

    limited = _limit_questions(text, max_questions=3)
    if not limited:
        return _fallback_questions(user_input)

    # Ensure at least one question to keep the clarifier loop useful.
    if "?" not in limited and "？" not in limited:
        limited = f"{limited.rstrip('。.!！')}\n1) 你希望最终产出什么？"
        limited = _limit_questions(limited, max_questions=3)

    return limited


class ClarifierConversationLLM:
    """ConversationAgentLLM implementation for the default (/) clarifier flow.

    Goals:
    - Natural-language only output (no JSON/code fences)
    - Respond-only (no tool_call/create_node/execute_workflow)
    - Ask 1–3 high-signal clarification questions per turn (at most 3)
    - Offline-safe fallback when no real LLM is available
    """

    def __init__(self, *, llm_port: LLMPort | None = None) -> None:
        self._llm_port = llm_port

    async def think(self, context: dict[str, Any]) -> str:
        # Do not generate chain-of-thought. This is intentionally blank.
        _ = context
        return ""

    async def decide_action(self, context: dict[str, Any]) -> dict[str, Any]:
        user_input = str(context.get("user_input", "") or "").strip()

        model_text = ""
        if self._llm_port is not None:
            prompt = (
                "你是一个需求澄清助手。你只能做一件事：通过 1-3 个高信号问题澄清用户目标。\n"
                "硬性要求：\n"
                "- 只输出纯文本（不要 JSON，不要代码块，不要 Markdown 代码围栏）\n"
                "- 最多 3 个问题，每个问题一行\n"
                "- 不要执行任何动作，不要提到工具调用，不要创建/执行工作流\n"
                "\n"
                f"用户输入：{user_input}\n"
                "\n"
                "请直接输出问题："
            )
            try:
                model_text = await self._llm_port.generate(
                    prompt,
                    temperature=0.2,
                    max_tokens=400,
                )
            except Exception as exc:  # noqa: BLE001 - must fail closed to deterministic fallback
                logger.info(
                    "conversation_clarifier_llm_unavailable",
                    extra={"error_type": type(exc).__name__},
                )
                model_text = ""

        response = _sanitize_or_fallback(model_text, user_input=user_input)
        response = _limit_questions(response, max_questions=3)

        return {
            "action_type": "respond",
            "response": response,
            "requires_followup": True,
            "confidence": 1.0,
            "intent": "conversation",
        }

    async def should_continue(self, context: dict[str, Any]) -> bool:
        _ = context
        # respond-only: single-turn output to avoid drift.
        return False

    # --- Methods required by ConversationAgentLLM protocol (unused in clarifier mode) ---
    async def decompose_goal(self, goal: str) -> list[dict[str, Any]]:
        _ = goal
        return []

    async def plan_workflow(self, goal: str, context: dict[str, Any]) -> dict[str, Any]:
        _ = goal
        _ = context
        return {"name": "clarifier_mode", "nodes": [], "edges": []}

    async def decompose_to_nodes(self, goal: str) -> list[dict[str, Any]]:
        _ = goal
        return []

    async def replan_workflow(
        self,
        goal: str,
        failed_node_id: str,
        failure_reason: str,
        execution_context: dict[str, Any],
    ) -> dict[str, Any]:
        _ = goal
        _ = failed_node_id
        _ = failure_reason
        _ = execution_context
        return {"name": "clarifier_replan", "nodes": [], "edges": []}
