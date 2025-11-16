"""Pytest 配置文件 - 全局 fixtures"""

import pytest
from fastapi.testclient import TestClient

from src.interfaces.api.main import app


@pytest.fixture
def client() -> TestClient:
    """FastAPI 测试客户端"""
    return TestClient(app)


@pytest.fixture
def sample_agent_data() -> dict:
    """示例 Agent 数据"""
    return {
        "start": "我有一个 CSV 文件包含销售数据",
        "goal": "生成销售趋势分析报告",
        "config": {
            "model": "gpt-4o-mini",
            "max_steps": 10,
            "timeout": 300,
        },
    }
