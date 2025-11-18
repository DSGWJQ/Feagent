from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from src.interfaces.api.main import app

    return TestClient(app)


def test_422_response_contains_trace_id_header_and_detail(client):
    response = client.post(
        "/api/agents",
        json={
            "goal": "分析数据",
        },
    )

    assert response.status_code == 422
    assert "X-Trace-Id" in response.headers
    data = response.json()
    assert "detail" in data
    assert "trace_id" in data


@patch("src.interfaces.api.routes.agents.CreateAgentUseCase")
def test_500_response_contains_trace_id_header(mock_use_case_class, client):
    mock_use_case = Mock()
    mock_use_case.execute.side_effect = Exception("数据库错误")
    mock_use_case_class.return_value = mock_use_case

    response = client.post(
        "/api/agents",
        json={
            "start": "我有一个 CSV 文件，包含销售数据",
            "goal": "分析销售数据并生成报告",
        },
    )

    assert response.status_code == 500
    assert "X-Trace-Id" in response.headers
    data = response.json()
    assert "detail" in data
    assert "trace_id" in data
