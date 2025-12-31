"""FastAPI 应用入口"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.application.services.async_run_event_recorder import AsyncRunEventRecorder
from src.application.services.coordinator_agent_factory import create_coordinator_agent
from src.config import settings
from src.domain.ports.node_executor import NodeExecutorRegistry
from src.domain.services.event_bus import EventBus
from src.domain.services.workflow_scheduler import ScheduleWorkflowService
from src.infrastructure.database.engine import SessionLocal
from src.infrastructure.database.schema import ensure_sqlite_schema
from src.infrastructure.executors import create_executor_registry
from src.interfaces.api.container import ApiContainer
from src.interfaces.api.dependencies.agents import set_event_bus
from src.interfaces.api.dependencies.scheduler import (
    clear_scheduler_service,
    set_scheduler_service,
)
from src.interfaces.api.routes import (
    auth,
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
from src.interfaces.api.routes import chat_workflows as chat_workflows_routes
from src.interfaces.api.routes import workflows as workflows_routes
from src.interfaces.api.routes import workflows_rag as workflows_rag_routes
from src.interfaces.api.services.workflow_executor_adapter import WorkflowExecutorAdapter

SchedulerInstance = ScheduleWorkflowService | None
_scheduler_service: SchedulerInstance = None


def _create_session():
    return SessionLocal()


def _build_container(executor_registry: NodeExecutorRegistry, event_bus: EventBus) -> ApiContainer:
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

    def workflow_execution_orchestrator(session: Session) -> WorkflowExecutionOrchestrator:
        repo = workflow_repository(session)
        facade = WorkflowExecutionFacade(
            workflow_repository=repo,
            executor_registry=executor_registry,
        )
        return WorkflowExecutionOrchestrator(
            facade=facade,
            policies=[NoopWorkflowExecutionPolicy()],
            idempotency=_idempotency,
        )

    _idempotency = IdempotencyCoordinator(store=InMemoryIdempotencyStore())

    conversation_agent = create_conversation_agent(
        event_bus=event_bus,
        model_metadata_port=create_model_metadata_adapter(),
    )

    def conversation_turn_orchestrator() -> ConversationTurnOrchestrator:
        return ConversationTurnOrchestrator(
            conversation_agent=conversation_agent,
            policies=[NoopConversationTurnPolicy()],
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
        workflow_execution_orchestrator=workflow_execution_orchestrator,
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


def _init_scheduler(executor_registry: NodeExecutorRegistry) -> ScheduleWorkflowService:
    from src.infrastructure.database.repositories.scheduled_workflow_repository import (
        SQLAlchemyScheduledWorkflowRepository,
    )

    workflow_executor = WorkflowExecutorAdapter(
        session_factory=_create_session,
        executor_registry=executor_registry,
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
    print("[EVENTBUS] 统一事件总线已初始化")

    try:
        ensure_sqlite_schema()
    except Exception as exc:  # pragma: no cover - best effort startup helper
        print(f"[DB] 数据库初始化失败（请运行 Alembic 迁移）: {exc}")

    executor_registry = create_executor_registry(
        openai_api_key=settings.openai_api_key or None,
        anthropic_api_key=getattr(settings, "anthropic_api_key", None),
    )
    app.state.container = _build_container(executor_registry, event_bus)

    try:
        _scheduler_service = _init_scheduler(executor_registry)
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


app.include_router(workflows_routes.router, prefix="/api", tags=["Workflows"])
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(chat_workflows_routes.router, prefix="/api", tags=["Chat Workflows"])
app.include_router(workflows_rag_routes.router, prefix="/api", tags=["Workflows RAG"])

app.include_router(tools.router, prefix="/api", tags=["Tools"])
app.include_router(llm_providers.router, prefix="/api", tags=["LLM Providers"])
app.include_router(scheduled_workflows.router, prefix="/api", tags=["Scheduled Workflows"])
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(coordinator_status.router, prefix="/api/coordinator", tags=["Coordinator"])
app.include_router(conversation_stream.router, prefix="/api")
app.include_router(memory_metrics.router, tags=["Memory"])
app.include_router(knowledge.router, tags=["Knowledge"])
app.include_router(runs.router, prefix="/api", tags=["Runs"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.interfaces.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )
