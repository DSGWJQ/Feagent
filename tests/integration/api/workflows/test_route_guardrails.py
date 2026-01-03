"""T-ROUTE-1：工作流收敛（V3）路由/契约护栏测试。

目标：
- OpenAPI 中 Create/Execute 的“目标入口”必须是非 deprecated。
- legacy 入口若存在，必须明确标记 deprecated（避免协议漂移/误用）。
- WebSocket 画布同步入口必须不可达（不应被挂载到 API app）。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.interfaces.api.routes import workflows as workflows_routes


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(workflows_routes.router, prefix="/api")
    return TestClient(app)


def _get_openapi_paths(client: TestClient) -> dict:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    body = response.json()
    return body["paths"]


def _assert_deprecated(paths: dict, path: str, method: str, expected: bool) -> None:
    assert path in paths, f"missing path in OpenAPI: {path}"
    assert method in paths[path], f"missing method in OpenAPI: {method} {path}"
    operation = paths[path][method]
    assert operation.get("deprecated", False) is expected


def _assert_path_absent(paths: dict, path: str) -> None:
    assert path not in paths, f"unexpected path in OpenAPI: {path}"


def test_t_route_1_openapi_create_execute_guardrails(client: TestClient) -> None:
    paths = _get_openapi_paths(client)

    # I-1：目标创建入口（非 deprecated）
    _assert_deprecated(paths, "/api/workflows/chat-create/stream", "post", False)

    # legacy create：兼容期存在，但必须 deprecated
    _assert_deprecated(paths, "/api/workflows", "post", True)

    # I-3：目标执行入口（非 deprecated）
    _assert_deprecated(paths, "/api/workflows/{workflow_id}/execute/stream", "post", False)

    # legacy execute：兼容期存在，但必须 deprecated
    _assert_deprecated(paths, "/api/workflows/{workflow_id}/execute", "post", True)

    # I-2（PATCH）：目标修改入口（非 deprecated）
    _assert_deprecated(paths, "/api/workflows/{workflow_id}", "patch", False)

    # I-4：目标对话修改入口（非 deprecated）
    _assert_deprecated(paths, "/api/workflows/{workflow_id}/chat-stream", "post", False)

    # legacy react-stream：必须不存在（404 / not mounted）
    _assert_path_absent(paths, "/api/workflows/{workflow_id}/chat-stream-react")


def test_t_route_1_canvas_websocket_route_is_unavailable(client: TestClient) -> None:
    # WebSocket 画布同步端点不应被 API app 挂载（应当 404/不存在）
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/workflows/wf_test"):
            pass
