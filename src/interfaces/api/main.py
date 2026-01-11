"""FastAPI 应用入口"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.application.services.async_run_event_recorder import AsyncRunEventRecorder
from src.application.services.capability_catalog_service import CapabilityCatalogService
from src.application.services.coordinator_agent_factory import create_coordinator_agent
from src.application.services.coordinator_policy_chain import CoordinatorPort
from src.config import settings
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.services.event_bus import EventBus
from src.domain.services.workflow_scheduler import ScheduleWorkflowService
from src.infrastructure.database.engine import SessionLocal
from src.infrastructure.database.schema import ensure_sqlite_schema
from src.infrastructure.definitions.yaml_node_definition_source import YamlNodeDefinitionSource
from src.infrastructure.executors import create_executor_registry
from src.interfaces.api.container import ApiContainer
from src.interfaces.api.dependencies.agents import set_event_bus
from src.interfaces.api.dependencies.scheduler import (
    clear_scheduler_service,
    set_scheduler_service,
)
from src.interfaces.api.routes import (
    agents,
    auth,
    concurrent_workflows,
    conversation_stream,
    coordinator_status,
    health,
    knowledge,
    llm_providers,
    memory_metrics,
    runs,
    scheduled_workflows,
    tools,
)
from src.interfaces.api.routes import workflows as workflows_routes
from src.interfaces.api.routes import workflows_rag as workflows_rag_routes
from src.interfaces.api.services.workflow_executor_adapter import WorkflowExecutorAdapter

SchedulerInstance = ScheduleWorkflowService | None
_scheduler_service: SchedulerInstance = None
logger = logging.getLogger(__name__)


def _create_session():
    return SessionLocal()


def _build_container(
    executor_registry: NodeExecutorRegistry,
    event_bus: EventBus,
    coordinator: CoordinatorPort,
) -> ApiContainer:
    from src.application.services.conversation_agent_factory import create_conversation_agent
    from src.application.services.conversation_turn_orchestrator import (
        ConversationTurnOrchestrator,
        NoopConversationTurnPolicy,
    )
    from src.application.services.idempotency_coordinator import IdempotencyCoordinator
    from src.application.services.workflow_execution_facade import WorkflowExecutionFacade
    from src.application.services.workflow_execution_orchestrator import (
        NoopWorkflowExecutionPolicy,
        WorkflowExecutionOrchestrator,
    )
    from src.infrastructure.adapters.in_memory_idempotency_store import InMemoryIdempotencyStore
    from src.infrastructure.adapters.model_metadata_adapter import create_model_metadata_adapter

    def user_repository(session: Session):
        from src.infrastructure.database.repositories.user_repository import (
            SQLAlchemyUserRepository,
        )

        return SQLAlchemyUserRepository(session)

    def agent_repository(session: Session):
        from src.infrastructure.database.repositories.agent_repository import (
            SQLAlchemyAgentRepository,
        )

        return SQLAlchemyAgentRepository(session)

    def task_repository(session: Session):
        from src.infrastructure.database.repositories.task_repository import (
            SQLAlchemyTaskRepository,
        )

        return SQLAlchemyTaskRepository(session)

    def workflow_repository(session: Session):
        from src.infrastructure.database.repositories.workflow_repository import (
            SQLAlchemyWorkflowRepository,
        )

        return SQLAlchemyWorkflowRepository(session)

    def workflow_execution_kernel(session: Session) -> WorkflowExecutionOrchestrator:
        repo = workflow_repository(session)
        facade = WorkflowExecutionFacade(
            workflow_repository=repo,
            executor_registry=executor_registry,
        )
        from src.application.services.workflow_execution_orchestrator import (
            CoordinatorWorkflowExecutionPolicy,
        )

        return WorkflowExecutionOrchestrator(
            facade=facade,
            policies=[
                CoordinatorWorkflowExecutionPolicy(
                    coordinator=coordinator,
                    event_bus=event_bus,
                    source="workflow_execute_stream",
                    fail_closed=True,
                ),
                NoopWorkflowExecutionPolicy(),
            ],
            idempotency=_idempotency,
        )

    _idempotency = IdempotencyCoordinator(store=InMemoryIdempotencyStore())

    def workflow_run_execution_entry(session: Session):
        from src.application.services.workflow_run_execution_entry import (
            WorkflowRunExecutionEntry,
        )
        from src.application.use_cases.append_run_event import AppendRunEventUseCase
        from src.application.use_cases.execute_workflow import WORKFLOW_EXECUTION_KERNEL_ID
        from src.domain.services.workflow_save_validator import WorkflowSaveValidator
        from src.infrastructure.database.repositories.run_event_repository import (
            SQLAlchemyRunEventRepository,
        )
        from src.infrastructure.database.transaction_manager import SQLAlchemyTransactionManager

        run_repo = run_repository(session)
        run_event_use_case = AppendRunEventUseCase(
            run_repository=run_repo,
            run_event_repository=SQLAlchemyRunEventRepository(session),
            transaction_manager=SQLAlchemyTransactionManager(session),
        )
        save_validator = WorkflowSaveValidator(
            executor_registry=executor_registry,
            tool_repository=tool_repository(session),
        )
        return WorkflowRunExecutionEntry(
            workflow_repository=workflow_repository(session),
            run_repository=run_repo,
            save_validator=save_validator,
            run_event_use_case=run_event_use_case,
            kernel=workflow_execution_kernel(session),
            executor_id=WORKFLOW_EXECUTION_KERNEL_ID,
        )

    def conversation_turn_orchestrator() -> ConversationTurnOrchestrator:
        conversation_agent = create_conversation_agent(
            event_bus=event_bus,
            model_metadata_port=create_model_metadata_adapter(),
            coordinator=coordinator,
        )
        from src.application.services.conversation_turn_orchestrator import (
            CoordinatorConversationTurnPolicy,
        )

        return ConversationTurnOrchestrator(
            conversation_agent=conversation_agent,
            policies=[
                CoordinatorConversationTurnPolicy(
                    coordinator=coordinator,
                    event_bus=event_bus,
                    source="conversation_stream",
                    fail_closed=True,
                ),
                NoopConversationTurnPolicy(),
            ],
        )

    def chat_message_repository(session: Session):
        from src.infrastructure.database.repositories.chat_message_repository import (
            SQLAlchemyChatMessageRepository,
        )

        return SQLAlchemyChatMessageRepository(session)

    def llm_provider_repository(session: Session):
        from src.infrastructure.database.repositories.llm_provider_repository import (
            SQLAlchemyLLMProviderRepository,
        )

        return SQLAlchemyLLMProviderRepository(session)

    def tool_repository(session: Session):
        from src.infrastructure.database.repositories.tool_repository import (
            SQLAlchemyToolRepository,
        )

        return SQLAlchemyToolRepository(session)

    def run_repository(session: Session):
        from src.infrastructure.database.repositories.run_repository import SQLAlchemyRunRepository

        return SQLAlchemyRunRepository(session)

    def scheduled_workflow_repository(session: Session):
        from src.infrastructure.database.repositories.scheduled_workflow_repository import (
            SQLAlchemyScheduledWorkflowRepository,
        )

        return SQLAlchemyScheduledWorkflowRepository(session)

    return ApiContainer(
        executor_registry=executor_registry,
        workflow_execution_kernel=workflow_execution_kernel,
        workflow_run_execution_entry=workflow_run_execution_entry,
        conversation_turn_orchestrator=conversation_turn_orchestrator,
        user_repository=user_repository,
        agent_repository=agent_repository,
        task_repository=task_repository,
        workflow_repository=workflow_repository,
        chat_message_repository=chat_message_repository,
        llm_provider_repository=llm_provider_repository,
        tool_repository=tool_repository,
        run_repository=run_repository,
        scheduled_workflow_repository=scheduled_workflow_repository,
    )


def _init_scheduler(container: ApiContainer) -> ScheduleWorkflowService:
    from src.infrastructure.database.repositories.scheduled_workflow_repository import (
        SQLAlchemyScheduledWorkflowRepository,
    )

    workflow_executor = WorkflowExecutorAdapter(
        session_factory=_create_session,
        executor_registry=container.executor_registry,
        workflow_run_execution_entry_factory=container.workflow_run_execution_entry,
        workflow_repository_factory=container.workflow_repository,
        run_repository_factory=container.run_repository,
    )

    # Create repository instance for scheduler (用于启动时加载任务)
    session = _create_session()
    scheduled_workflow_repo = SQLAlchemyScheduledWorkflowRepository(session)

    # 定义 repo_factory 用于调度器执行时创建独立事务
    def repo_factory(s):
        return SQLAlchemyScheduledWorkflowRepository(s)

    return ScheduleWorkflowService(
        scheduled_workflow_repo=scheduled_workflow_repo,
        workflow_executor=workflow_executor,
        session_factory=_create_session,
        repo_factory=repo_factory,
    )


def _get_display_host() -> str:
    """Return a host suitable for displaying in links."""
    if settings.host in {"0.0.0.0", "::"}:
        return "127.0.0.1"
    return settings.host


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _scheduler_service
    display_host = _get_display_host()
    print(f"[*] {settings.app_name} v{settings.app_version} 启动中...")
    print(f"[ENV] 环境: {settings.env}")
    print(f"[DB] 数据库: {settings.database_url}")
    print(f"[URL] 服务地址: http://{display_host}:{settings.port}")
    print(f"[DOCS] API 文档: http://{display_host}:{settings.port}/docs")

    # Step 1: 统一 EventBus 单例 - 应用启动时创建唯一实例
    event_bus = EventBus()
    app.state.event_bus = event_bus
    # 向后兼容：供非 Request 上下文的调用路径复用同一实例
    set_event_bus(event_bus)
    # 初始化 Coordinator（使用同一 EventBus）
    app.state.coordinator = create_coordinator_agent(event_bus=event_bus)
    if not getattr(event_bus, "_coordinator_middleware_attached", False):
        event_bus.add_middleware(app.state.coordinator.as_middleware())
        cast(Any, event_bus)._coordinator_middleware_attached = True
    from src.interfaces.api.services.event_bus_sse_bridge import attach_event_bus_sse_bridge

    attach_event_bus_sse_bridge(event_bus)
    print("[EVENTBUS] 统一事件总线已初始化")

    try:
        ensure_sqlite_schema()
    except Exception as exc:  # pragma: no cover - best effort startup helper
        print(f"[DB] 数据库初始化失败（请运行 Alembic 迁移）: {exc}")

    executor_registry = create_executor_registry(
        openai_api_key=settings.openai_api_key or None,
        anthropic_api_key=getattr(settings, "anthropic_api_key", None),
        session_factory=_create_session,
    )

    catalog = CapabilityCatalogService(
        sources=[
            YamlNodeDefinitionSource(
                definitions_dir=Path("definitions/nodes"),
                schema_path=Path("definitions/schemas/node_definition_schema.json"),
            )
        ]
    )
    app.state.capability_definitions = catalog.load_and_validate_startup()
    app.state.container = _build_container(
        executor_registry,
        event_bus,
        cast(CoordinatorPort, app.state.coordinator),
    )
    # DecisionExecutionBridge: validated decision (allow) -> WorkflowAgent execution.
    #
    # Red-team note:
    # - We wire only `execute_workflow` here to avoid implicit side effects for plan/create decisions.
    # - CoordinatorAgent middleware is already attached to EventBus; denied decisions won't reach subscribers.
    if settings.enable_decision_execution_bridge and not settings.disable_run_persistence:
        try:
            from src.domain.services.decision_execution_bridge import DecisionExecutionBridge

            if not getattr(event_bus, "_coordinator_middleware_attached", False):
                raise RuntimeError(
                    "coordinator middleware not attached; refuse to start DecisionExecutionBridge"
                )

            async def _handle_workflow_decision(decision: dict[str, Any]) -> dict[str, Any]:
                decision_type = decision.get("decision_type")
                if decision_type != "execute_workflow":
                    return {
                        "success": False,
                        "status": "ignored",
                        "error": "unsupported decision_type",
                    }

                workflow_id = decision.get("workflow_id")
                run_id = decision.get("run_id")
                if not isinstance(workflow_id, str) or not workflow_id.strip():
                    return {
                        "success": False,
                        "status": "failed",
                        "error": "workflow_id is required for execute_workflow",
                    }
                if not isinstance(run_id, str) or not run_id.strip():
                    return {"success": False, "status": "failed", "error": "run_id is required"}

                input_data = decision.get("initial_input", decision.get("input_data"))

                session = _create_session()
                try:
                    entry = app.state.container.workflow_run_execution_entry(session)
                    return await entry.execute_with_results(
                        workflow_id=workflow_id.strip(),
                        run_id=run_id.strip(),
                        input_data=input_data,
                        correlation_id=run_id.strip(),
                        original_decision_id=run_id.strip(),
                        record_execution_events=True,
                    )
                finally:
                    session.close()

            decision_bridge = DecisionExecutionBridge(
                event_bus=event_bus,
                workflow_decision_handler=_handle_workflow_decision,
                actionable_decision_types={"execute_workflow"},
            )
            await decision_bridge.start()
            app.state.decision_execution_bridge = decision_bridge
            logger.info(
                "decision_execution_bridge_enabled",
                extra={"actionable_decision_types": ["execute_workflow"]},
            )
            print("[BRIDGE] DecisionExecutionBridge 已启动（execute_workflow only）")
        except Exception as exc:  # pragma: no cover - best effort startup wiring
            logger.error(
                "decision_execution_bridge_start_failed",
                extra={"error_type": type(exc).__name__},
            )
            print(f"[BRIDGE] DecisionExecutionBridge 启动失败（已禁用）: {exc}")
    else:
        reason = (
            "disable_run_persistence" if settings.disable_run_persistence else "feature_flag_off"
        )
        logger.info("decision_execution_bridge_disabled", extra={"reason": reason})
        print(f"[BRIDGE] DecisionExecutionBridge 已禁用（{reason}）")

    try:
        _scheduler_service = _init_scheduler(app.state.container)
        _scheduler_service.start()
        set_scheduler_service(_scheduler_service)
    except SQLAlchemyError as exc:
        _scheduler_service = None
        clear_scheduler_service()
        print(f"[SCHEDULER] 启动失败，已禁用调度器: {exc}")

    # 启动异步事件录制器（非阻塞落库）
    event_recorder = AsyncRunEventRecorder(session_factory=_create_session)
    await event_recorder.start()
    app.state.event_recorder = event_recorder
    print("[RECORDER] 异步事件录制器已启动")

    try:
        yield
    finally:
        # Stop DecisionExecutionBridge (if enabled).
        bridge = getattr(app.state, "decision_execution_bridge", None)
        if bridge is not None:
            try:
                await bridge.stop()
            except Exception:
                pass
        # 停止异步事件录制器
        if hasattr(app.state, "event_recorder"):
            await app.state.event_recorder.stop()
            print(f"[RECORDER] 统计: {app.state.event_recorder.stats}")
        # 停止 Coordinator 监控
        coordinator = getattr(app.state, "coordinator", None)
        if coordinator is not None:
            coordinator.stop_monitoring()
        if _scheduler_service is not None:
            _scheduler_service.stop()
        clear_scheduler_service()
        # Avoid emojis so Windows consoles (GBK codepage) don't raise UnicodeEncodeError.
        print(f"[SHUTDOWN] {settings.app_name} 关闭中...")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="企业级 Agent 编排与执行平台",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
async def health_check() -> JSONResponse:
    return JSONResponse(
        content={
            "status": "healthy",
            "app_name": settings.app_name,
            "version": settings.app_version,
            "env": settings.env,
        }
    )


@app.get("/", tags=["Root"])
async def root() -> JSONResponse:
    display_host = _get_display_host()
    return JSONResponse(
        content={
            "message": f"欢迎使用 {settings.app_name}",
            "version": settings.app_version,
            "docs": f"http://{display_host}:{settings.port}/docs",
        }
    )


# NOTE: include "fixed" workflow subpaths before the catch-all `/{workflow_id}` routes,
# otherwise Starlette will match `/{workflow_id}` first and return 405 for POST endpoints.
app.include_router(concurrent_workflows.router, prefix="/api")
app.include_router(workflows_routes.router, prefix="/api", tags=["Workflows"])
app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(workflows_rag_routes.router, prefix="/api", tags=["Workflows RAG"])

app.include_router(tools.router, prefix="/api", tags=["Tools"])
app.include_router(llm_providers.router, prefix="/api", tags=["LLM Providers"])
app.include_router(scheduled_workflows.router, prefix="/api", tags=["Scheduled Workflows"])
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(coordinator_status.router, prefix="/api/coordinator", tags=["Coordinator"])

# Note (WFPLAN-050 / OptionB): conversation stream is an Agent-side experimental entrypoint,
# not the Workflow main chain (which lives under /api/workflows/* and /api/runs/*).
app.include_router(conversation_stream.router, prefix="/api")
app.include_router(memory_metrics.router, tags=["Memory"])
app.include_router(knowledge.router, tags=["Knowledge"])
app.include_router(runs.router, prefix="/api", tags=["Runs"])

# Test Seed API（仅测试/开发环境启用）
if settings.enable_test_seed_api:
    from src.interfaces.api.routes import test_seeds

    app.include_router(test_seeds.router, prefix="/api", tags=["Test Seeds"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.interfaces.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )
