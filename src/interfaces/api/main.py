"""FastAPI 应用入口"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import settings
from src.interfaces.api.routes import agents, runs


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    # Startup
    print(f"🚀 {settings.app_name} v{settings.app_version} 启动中...")
    print(f"📝 环境: {settings.env}")
    print(f"🔗 数据库: {settings.database_url}")
    print(f"🌐 服务地址: http://{settings.host}:{settings.port}")
    print(f"📚 API 文档: http://{settings.host}:{settings.port}/docs")

    yield

    # Shutdown
    print(f"👋 {settings.app_name} 关闭中...")


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.interfaces.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )
