"""E2E test mode switching tests (AdapterFactory + adapters).

目标：
- deterministic：默认不走真实依赖（Stub LLM + Mock HTTP）
- hybrid：验证 replay 链路与 WireMock URL 映射（不触发外网）
- fullreal：缺少 OPENAI_API_KEY 时 fail-closed
"""

from __future__ import annotations

import importlib
import json

import pytest


def _reload_container():
    import src.config as config
    import src.interfaces.api.container as container

    importlib.reload(config)
    importlib.reload(container)
    return container


@pytest.mark.asyncio
async def test_deterministic_llm_stub_adapter(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("E2E_TEST_MODE", "deterministic")
    monkeypatch.setenv("LLM_ADAPTER", "stub")

    container = _reload_container()
    llm = container.AdapterFactory.create_llm_adapter()

    response = await llm.generate(prompt="创建一个简单的工作流")
    assert isinstance(response, str)
    assert response


@pytest.mark.asyncio
async def test_deterministic_http_mock_adapter(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("E2E_TEST_MODE", "deterministic")
    monkeypatch.setenv("HTTP_ADAPTER", "mock")

    container = _reload_container()
    http = container.AdapterFactory.create_http_adapter()

    response = await http.request("GET", "https://httpbin.org/get")
    assert response["mock"] is True
    assert response["_mock_meta"]["matched_pattern"]


def test_hybrid_llm_replay_requires_file(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("E2E_TEST_MODE", "hybrid")
    monkeypatch.setenv("LLM_ADAPTER", "replay")
    monkeypatch.delenv("LLM_REPLAY_FILE", raising=False)

    container = _reload_container()
    with pytest.raises(ValueError, match="LLM_REPLAY_FILE is required"):
        container.AdapterFactory.create_llm_adapter()


@pytest.mark.asyncio
async def test_hybrid_llm_replay_works(monkeypatch: pytest.MonkeyPatch, tmp_path):
    replay_file = tmp_path / "recordings.json"
    replay_file.write_text(
        json.dumps([{"prompt": "hello", "response": "world"}], ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setenv("E2E_TEST_MODE", "hybrid")
    monkeypatch.setenv("LLM_ADAPTER", "replay")
    monkeypatch.setenv("LLM_REPLAY_FILE", str(replay_file))

    container = _reload_container()
    llm = container.AdapterFactory.create_llm_adapter()
    assert await llm.generate(prompt="hello") == "world"


def test_fullreal_openai_requires_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("E2E_TEST_MODE", "fullreal")
    monkeypatch.setenv("LLM_ADAPTER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "")

    container = _reload_container()
    with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
        container.AdapterFactory.create_llm_adapter()


def test_wiremock_url_mapping_is_local(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("E2E_TEST_MODE", "hybrid")
    monkeypatch.setenv("HTTP_ADAPTER", "wiremock")
    monkeypatch.setenv("WIREMOCK_URL", "http://127.0.0.1:8080")

    container = _reload_container()
    http = container.AdapterFactory.create_http_adapter()

    mapped = http._map_to_wiremock("https://example.com/foo/bar?x=1")  # type: ignore[attr-defined]
    assert mapped == "http://127.0.0.1:8080/foo/bar?x=1"
