from __future__ import annotations

import pytest


class _FakeLLMPort:
    def __init__(self, response: str) -> None:
        self._response = response
        self.prompts: list[str] = []

    async def generate(self, prompt: str, *args, **kwargs) -> str:  # noqa: ANN001, D401
        self.prompts.append(prompt)
        return self._response

    async def generate_streaming(self, prompt: str, *args, **kwargs):  # noqa: ANN001
        self.prompts.append(prompt)
        yield self._response


@pytest.mark.asyncio
async def test_clarifier_conversation_llm_sanitizes_json_and_blocks_privileged_actions() -> None:
    from src.application.services.clarifier_conversation_llm import ClarifierConversationLLM

    llm_port = _FakeLLMPort('{"action_type":"tool_call","tool_name":"echo"}')
    llm = ClarifierConversationLLM(llm_port=llm_port)

    action = await llm.decide_action({"user_input": "帮我做一个自动化流程"})

    assert action.get("action_type") == "respond"
    response = str(action.get("response", ""))

    # Must not leak structured control payloads to the user.
    assert "action_type" not in response
    assert "tool_call" not in response

    # Contract: at most 3 questions per turn.
    assert response.count("?") + response.count("？") <= 3


@pytest.mark.asyncio
async def test_clarifier_conversation_llm_limits_questions_to_three() -> None:
    from src.application.services.clarifier_conversation_llm import ClarifierConversationLLM

    llm_port = _FakeLLMPort("1) Q1?\n2) Q2?\n3) Q3?\n4) Q4?\n5) Q5?")
    llm = ClarifierConversationLLM(llm_port=llm_port)

    action = await llm.decide_action({"user_input": "do something"})
    assert action.get("action_type") == "respond"

    response = str(action.get("response", ""))
    assert response.count("?") + response.count("？") <= 3
