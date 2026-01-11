"""API Container (composition root state holder).

This module only defines types/structure for objects created in the real
composition root (`src/interfaces/api/main.py`).

Additionally, it provides AdapterFactory for E2E test mode switching.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from src.application.services.conversation_turn_orchestrator import ConversationTurnOrchestrator
from src.config import settings
from src.domain.ports.agent_repository import AgentRepository
from src.domain.ports.chat_message_repository import ChatMessageRepository
from src.domain.ports.http_client_port import HTTPClientPort
from src.domain.ports.llm_port import LLMPort
from src.domain.ports.llm_provider_repository import LLMProviderRepository
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.ports.task_repository import TaskRepository
from src.domain.ports.tool_repository import ToolRepository
from src.domain.ports.user_repository import UserRepository
from src.domain.ports.workflow_execution_kernel import WorkflowExecutionKernelPort
from src.domain.ports.workflow_repository import WorkflowRepository
from src.domain.ports.workflow_run_execution_entry import WorkflowRunExecutionEntryPort


def _missing_workflow_run_execution_entry(_: Session) -> WorkflowRunExecutionEntryPort:
    raise RuntimeError(
        "ApiContainer.workflow_run_execution_entry is not configured. "
        "Provide workflow_run_execution_entry when building ApiContainer."
    )


@dataclass(frozen=True, slots=True)
class ApiContainer:
    """Typed container attached to `app.state.container`."""

    executor_registry: NodeExecutorRegistry
    workflow_execution_kernel: Callable[[Session], WorkflowExecutionKernelPort]
    conversation_turn_orchestrator: Callable[[], ConversationTurnOrchestrator]

    user_repository: Callable[[Session], UserRepository]
    agent_repository: Callable[[Session], AgentRepository]
    task_repository: Callable[[Session], TaskRepository]
    workflow_repository: Callable[[Session], WorkflowRepository]
    chat_message_repository: Callable[[Session], ChatMessageRepository]
    llm_provider_repository: Callable[[Session], LLMProviderRepository]
    tool_repository: Callable[[Session], ToolRepository]

    # Adapters without a corresponding Domain Port yet (keep typing loose).
    run_repository: Callable[[Session], Any]
    scheduled_workflow_repository: Callable[[Session], Any]

    # Optional: Some tests build minimal ApiContainer instances; provide a safe default.
    workflow_run_execution_entry: Callable[[Session], WorkflowRunExecutionEntryPort] = (
        _missing_workflow_run_execution_entry
    )


class AdapterFactory:
    """Adapter工厂 - 根据环境变量选择实现.

    职责:
    - 基于配置创建LLM/HTTP Adapter
    - 实现E2E测试模式切换(Deterministic/Hybrid/Full-real)
    - 配置验证和错误提示

    设计原则:
    - 延迟导入: 避免未使用的Adapter加载依赖
    - 配置验证: 提供清晰的错误消息
    - 失败安全: 未定义的adapter类型抛出明确异常
    """

    @staticmethod
    def create_llm_adapter() -> LLMPort:
        """创建LLM Adapter实例.

        返回:
            LLMPort实现(Stub/Replay/OpenAI)

        异常:
            ValueError: adapter类型未定义或配置缺失
        """
        mode = settings.e2e_test_mode
        adapter_type = settings.llm_adapter

        # 模式门禁：避免 deterministic/hybrid 误走真实依赖
        if mode == "deterministic" and adapter_type != "stub":
            raise ValueError(
                "E2E_TEST_MODE=deterministic requires LLM_ADAPTER=stub (no real LLM calls).\n"
                f"Current: LLM_ADAPTER={adapter_type}"
            )
        if mode == "hybrid" and adapter_type != "replay":
            raise ValueError(
                "E2E_TEST_MODE=hybrid requires LLM_ADAPTER=replay.\n"
                f"Current: LLM_ADAPTER={adapter_type}"
            )
        if mode == "fullreal" and adapter_type != "openai":
            raise ValueError(
                "E2E_TEST_MODE=fullreal requires LLM_ADAPTER=openai.\n"
                f"Current: LLM_ADAPTER={adapter_type}"
            )

        if adapter_type == "stub":
            # 模式A: Deterministic - 固定响应
            from src.infrastructure.adapters.llm_stub_adapter import LLMStubAdapter

            return LLMStubAdapter()

        elif adapter_type == "replay":
            # 模式B: Hybrid - 回放录制
            if not settings.llm_replay_file:
                raise ValueError(
                    "LLM_REPLAY_FILE is required when LLM_ADAPTER=replay.\n"
                    "Please set it in your .env file (e.g., LLM_REPLAY_FILE=tests/fixtures/llm_recordings.json)"
                )

            from src.infrastructure.adapters.llm_replay_adapter import LLMReplayAdapter

            return LLMReplayAdapter(replay_file=settings.llm_replay_file)

        elif adapter_type == "openai":
            # 模式C: Full-real - 真实API
            if not settings.openai_api_key:
                raise ValueError(
                    "OPENAI_API_KEY is required when LLM_ADAPTER=openai.\n"
                    "Please set it in your .env file or environment variables."
                )

            from src.infrastructure.adapters.llm_openai_adapter import LLMOpenAIAdapter

            return LLMOpenAIAdapter(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                base_url=settings.openai_base_url,
            )

        else:
            raise ValueError(
                f"Unknown llm_adapter: {adapter_type}\n"
                f"Supported adapters: stub, replay, openai\n"
                f"Please set LLM_ADAPTER in your .env file."
            )

    @staticmethod
    def create_http_adapter() -> HTTPClientPort:
        """创建HTTP Adapter实例.

        返回:
            HTTPClientPort实现(Mock/WireMock/Httpx)

        异常:
            ValueError: adapter类型未定义或配置缺失
        """
        mode = settings.e2e_test_mode
        adapter_type = settings.http_adapter

        # 模式门禁：避免 deterministic/hybrid 误走真实 HTTP
        if mode == "deterministic" and adapter_type != "mock":
            raise ValueError(
                "E2E_TEST_MODE=deterministic requires HTTP_ADAPTER=mock (no real HTTP calls).\n"
                f"Current: HTTP_ADAPTER={adapter_type}"
            )
        if mode == "hybrid" and adapter_type != "wiremock":
            raise ValueError(
                "E2E_TEST_MODE=hybrid requires HTTP_ADAPTER=wiremock.\n"
                f"Current: HTTP_ADAPTER={adapter_type}"
            )
        if mode == "fullreal" and adapter_type != "httpx":
            raise ValueError(
                "E2E_TEST_MODE=fullreal requires HTTP_ADAPTER=httpx.\n"
                f"Current: HTTP_ADAPTER={adapter_type}"
            )

        if adapter_type == "mock":
            # 模式A: Deterministic - 本地mock
            from src.infrastructure.adapters.http_mock_adapter import HTTPMockAdapter

            return HTTPMockAdapter()

        elif adapter_type == "wiremock":
            # 模式B: Hybrid - WireMock服务器
            if not settings.wiremock_url:
                raise ValueError(
                    "WIREMOCK_URL is required when HTTP_ADAPTER=wiremock.\n"
                    "Please set it in your .env file (e.g., WIREMOCK_URL=http://localhost:8080)"
                )

            from src.infrastructure.adapters.http_wiremock_adapter import HTTPWireMockAdapter

            return HTTPWireMockAdapter(wiremock_url=settings.wiremock_url)

        elif adapter_type == "httpx":
            # 模式C: Full-real - 真实HTTP
            from src.infrastructure.adapters.http_httpx_adapter import HTTPHttpxAdapter

            return HTTPHttpxAdapter()

        else:
            raise ValueError(
                f"Unknown http_adapter: {adapter_type}\n"
                f"Supported adapters: mock, wiremock, httpx\n"
                f"Please set HTTP_ADAPTER in your .env file."
            )


# 依赖注入函数 (用于FastAPI Depends)
def get_llm_client() -> LLMPort:
    """获取LLM客户端实例 (依赖注入).

    用法:
        @app.post("/api/chat")
        async def chat(llm: LLMPort = Depends(get_llm_client)):
            response = await llm.generate(prompt="...")
            return {"response": response}

    返回:
        LLMPort实现(根据配置自动选择)
    """
    return AdapterFactory.create_llm_adapter()


def get_http_client() -> HTTPClientPort:
    """获取HTTP客户端实例 (依赖注入).

    用法:
        @app.post("/api/proxy")
        async def proxy(http: HTTPClientPort = Depends(get_http_client)):
            data = await http.request("GET", "https://api.example.com/data")
            return data

    返回:
        HTTPClientPort实现(根据配置自动选择)
    """
    return AdapterFactory.create_http_adapter()
