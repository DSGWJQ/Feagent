"""FastAPI 应用入口"""

import logging
import os
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import settings
from src.interfaces.api.routes import agents, runs, workflows


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    # Startup
    os.makedirs(os.path.dirname(settings.log_file), exist_ok=True)
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(log_level)
    formatter = logging.Formatter(
        fmt=(
            '{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s",'
            '"message":"%(message)s"}'
        )
    )
    fh = logging.FileHandler(settings.log_file, encoding="utf-8")
    fh.setLevel(log_level)
    fh.setFormatter(formatter)
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)
    logging.info(
        f"startup app={settings.app_name} version={settings.app_version} env={settings.env}"
    )
    logging.info(f"startup db={settings.database_url}")
    logging.info(f"startup host={settings.host} port={settings.port}")

    yield

    # Shutdown
    logging.info("shutdown")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="企业级 Agent 编排与执行平台",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logger(request: Request, call_next):
    trace_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
    request.state.trace_id = trace_id
    start = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = int((time.perf_counter() - start) * 1000)
    logging.info(
        f"request method={request.method} path={request.url.path} status={response.status_code} duration_ms={duration_ms} trace_id={trace_id}"
    )
    response.headers["X-Trace-Id"] = trace_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    trace_id = getattr(request.state, "trace_id", uuid.uuid4().hex)
    logging.warning(
        f"validation_error method={request.method} path={request.url.path} status=422 trace_id={trace_id} errors={exc.errors()}"
    )
    content: dict[str, Any] = {"detail": jsonable_encoder(exc.errors()), "trace_id": trace_id}
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=content)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    trace_id = getattr(request.state, "trace_id", uuid.uuid4().hex)
    logging.warning(
        f"http_exception method={request.method} path={request.url.path} status={exc.status_code} trace_id={trace_id} detail={exc.detail}"
    )
    content: dict[str, Any] = {"detail": exc.detail, "trace_id": trace_id}
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "trace_id", uuid.uuid4().hex)
    logging.error(
        f"unhandled_exception method={request.method} path={request.url.path} status=500 trace_id={trace_id} error={exc}"
    )
    content = {"detail": "服务器内部错误", "trace_id": trace_id}
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=content)


# 健康检查端点
@app.get("/health", tags=["Health"])
async def health_check() -> JSONResponse:
    """健康检查"""
    return JSONResponse(
        content={
            "status": "healthy",
            "app_name": settings.app_name,
            "version": settings.app_version,
            "env": settings.env,
        }
    )


# 根路径
@app.get("/", tags=["Root"])
async def root() -> JSONResponse:
    """根路径"""
    return JSONResponse(
        content={
            "message": f"欢迎使用 {settings.app_name}",
            "version": settings.app_version,
            "docs": f"http://{settings.host}:{settings.port}/docs",
        }
    )


# 注册路由
app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])
# Runs 路由有两个端点：
# 1. POST /api/agents/{agent_id}/runs - 触发 Run（需要 agent_id）
# 2. GET /api/runs/{run_id} - 获取 Run 详情（独立资源）
# 因此需要注册两次，使用不同的前缀
app.include_router(runs.router, prefix="/api/agents", tags=["Runs"])  # POST /{agent_id}/runs
app.include_router(runs.router, prefix="/api/runs", tags=["Runs"])  # GET /{run_id}
app.include_router(workflows.router, prefix="/api", tags=["Workflows"])  # /workflows/{workflow_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.interfaces.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )
