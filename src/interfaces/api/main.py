"""FastAPI 应用入口"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import settings
from src.domain.services.workflow_scheduler import ScheduleWorkflowService
from src.infrastructure.database.engine import SessionLocal
from src.infrastructure.executors import create_executor_registry
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
    websocket,
)
from src.interfaces.api.routes import chat_workflows as chat_workflows_routes
from src.interfaces.api.routes import workflows as workflows_routes
from src.interfaces.api.routes import workflows_rag as workflows_rag_routes
from src.interfaces.api.services.workflow_executor_adapter import WorkflowExecutorAdapter

SchedulerInstance = ScheduleWorkflowService | None
_scheduler_service: SchedulerInstance = None


def _create_session():
    return SessionLocal()


def _init_scheduler() -> ScheduleWorkflowService:
    from src.infrastructure.database.repositories.scheduled_workflow_repository import (
        SQLAlchemyScheduledWorkflowRepository,
    )

    executor_registry = create_executor_registry(
        openai_api_key=settings.openai_api_key or None,
        anthropic_api_key=getattr(settings, "anthropic_api_key", None),
    )
    workflow_executor = WorkflowExecutorAdapter(
        session_factory=_create_session,
        executor_registry=executor_registry,
    )

    # Create repository instance for scheduler
    session = _create_session()
    scheduled_workflow_repo = SQLAlchemyScheduledWorkflowRepository(session)

    return ScheduleWorkflowService(
        scheduled_workflow_repo=scheduled_workflow_repo,
        workflow_executor=workflow_executor,
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

    _scheduler_service = _init_scheduler()
    _scheduler_service.start()
    set_scheduler_service(_scheduler_service)

    try:
        yield
    finally:
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


app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])
app.include_router(runs.create_router, prefix="/api/agents", tags=["Runs"])
app.include_router(runs.query_router, prefix="/api/runs", tags=["Runs"])
app.include_router(workflows_routes.router, prefix="/api", tags=["Workflows"])
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(chat_workflows_routes.router, prefix="/api", tags=["Chat Workflows"])
app.include_router(workflows_rag_routes.router, prefix="/api", tags=["Workflows RAG"])

app.include_router(tools.router, prefix="/api", tags=["Tools"])
app.include_router(llm_providers.router, prefix="/api", tags=["LLM Providers"])
app.include_router(scheduled_workflows.router, prefix="/api", tags=["Scheduled Workflows"])
app.include_router(concurrent_workflows.router, prefix="/api", tags=["Concurrent Workflows"])
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(coordinator_status.router, prefix="/api/coordinator", tags=["Coordinator"])
app.include_router(memory_metrics.router, tags=["Memory"])
app.include_router(knowledge.router, tags=["Knowledge"])
app.include_router(websocket.router, tags=["WebSocket"])
app.include_router(conversation_stream.router, prefix="/api", tags=["Conversation Stream"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.interfaces.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )
