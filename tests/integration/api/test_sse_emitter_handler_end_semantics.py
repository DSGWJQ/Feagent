"""Integration test: SSEEmitterHandler must terminate streams after complete_with_error().

Regression target (P0):
- ConversationFlowEmitter.complete_with_error() used to emit ERROR without END, so the SSE handler
  would keep waiting until the emitter timeout (default 30s) and then emit a secondary SSE_ERROR.
"""

from __future__ import annotations

import asyncio
import json
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.domain.services.conversation_flow_emitter import ConversationFlowEmitter
from src.interfaces.api.services.sse_emitter_handler import SSEEmitterHandler


def _parse_sse_payloads(text: str) -> list[object]:
    payloads: list[object] = []
    for line in text.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload == "[DONE]":
            payloads.append("[DONE]")
            continue
        payloads.append(json.loads(payload))
    return payloads


def test_complete_with_error_emits_done_and_does_not_timeout():
    """ERROR must be followed by [DONE] without waiting for emitter timeout."""

    app = FastAPI()

    @app.get("/error-end")
    async def error_end():
        emitter = ConversationFlowEmitter(session_id="test", timeout=0.2)
        handler = SSEEmitterHandler(emitter, request=None)

        async def _producer():
            await emitter.complete_with_error("boom")

        asyncio.create_task(_producer())
        return handler.create_response()

    client = TestClient(app)
    started = time.perf_counter()
    response = client.get("/error-end")
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert elapsed < 1.0, f"SSE should terminate quickly, took {elapsed:.3f}s"

    payloads = _parse_sse_payloads(response.text)
    assert any(isinstance(p, dict) and p.get("type") == "error" for p in payloads)
    assert payloads[-1] == "[DONE]"

    # The old bug would produce a secondary SSE_ERROR (timeout) event instead of [DONE].
    assert not any(
        isinstance(p, dict) and p.get("error_code") == "SSE_ERROR" for p in payloads
    ), "should not emit secondary SSE_ERROR after complete_with_error()"
