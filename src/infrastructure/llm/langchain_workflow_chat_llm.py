"""LangChain adapter that satisfies the WorkflowChatLLM protocol."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from src.domain.ports.workflow_chat_llm import WorkflowChatLLM


class LangChainWorkflowChatLLM(WorkflowChatLLM):
    """Workflow chat LLM adapter backed by LangChain ChatOpenAI."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        temperature: float = 0.0,
    ) -> None:
        if not api_key:
            raise ValueError("OpenAI API Key is required for chat workflow features.")

        self._llm = ChatOpenAI(
            api_key=SecretStr(api_key),
            model=model,
            temperature=temperature,
            base_url=base_url,
        )
        self._parser = JsonOutputParser()

    @staticmethod
    def _build_messages(system_prompt: str, user_prompt: str) -> list[SystemMessage | HumanMessage]:
        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

    def generate_modifications(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Return structured modifications suggested by the LLM."""

        response = self._llm.invoke(self._build_messages(system_prompt, user_prompt))
        content = getattr(response, "content", str(response))
        return self._parser.parse(content)

    async def generate_modifications_async(
        self, system_prompt: str, user_prompt: str
    ) -> dict[str, Any]:
        """Async variant for callers that prefer awaitable workflows."""

        response = await self._llm.ainvoke(self._build_messages(system_prompt, user_prompt))
        content = getattr(response, "content", str(response))
        return self._parser.parse(content)
