from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.config import settings
from src.infrastructure.llm.deterministic_workflow_chat_llm import DeterministicWorkflowChatLLM
from src.infrastructure.llm.langchain_workflow_chat_llm import LangChainWorkflowChatLLM
from src.interfaces.api.routes.workflows import get_workflow_chat_llm


def test_get_workflow_chat_llm_prefers_deterministic_when_test_seed_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "env", "test")
    monkeypatch.setattr(settings, "enable_test_seed_api", True)

    llm = get_workflow_chat_llm()
    assert isinstance(llm, DeterministicWorkflowChatLLM)


def test_get_workflow_chat_llm_uses_dummy_langchain_in_test_when_seed_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Defensive: LangChain/OpenAI client initialization may be unavailable/unstable in unit tests.
    # The adapter intentionally references `langchain_openai.ChatOpenAI` via module attribute so
    # tests can patch it and stay offline.
    import langchain_openai

    class _FakeChatOpenAI:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            return None

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", _FakeChatOpenAI)

    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "env", "test")
    monkeypatch.setattr(settings, "enable_test_seed_api", False)

    llm = get_workflow_chat_llm()
    assert isinstance(llm, LangChainWorkflowChatLLM)


def test_get_workflow_chat_llm_returns_503_without_key_outside_test_or_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "env", "development")
    monkeypatch.setattr(settings, "enable_test_seed_api", False)

    with pytest.raises(HTTPException) as excinfo:
        get_workflow_chat_llm()
    assert excinfo.value.status_code == 503
