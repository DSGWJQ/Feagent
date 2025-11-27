"""健康检查端点

提供系统和RAG功能的健康检查
"""

from fastapi import APIRouter

from src.interfaces.api.dependencies.rag import check_rag_health, get_rag_config, is_rag_enabled

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/")
async def health_check() -> dict[str, str]:
    """基本健康检查"""
    return {
        "status": "healthy",
        "service": "Agent Platform",
    }


@router.get("/rag")
async def rag_health_check() -> dict:
    """RAG系统健康检查"""
    if not is_rag_enabled():
        return {
            "status": "disabled",
            "message": "RAG功能未启用",
            "config": get_rag_config(),
        }

    health_status = await check_rag_health()
    health_status["config"] = get_rag_config()

    return health_status


@router.get("/rag/config")
async def rag_config() -> dict:
    """获取RAG配置信息"""
    config = get_rag_config()
    config["enabled"] = is_rag_enabled()
    return config


@router.get("/version")
async def version_info() -> dict[str, str]:
    """版本信息"""
    from src.config import settings

    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.env,
    }


@router.get("/env")
async def environment_info() -> dict[str, str]:
    """���境信息（仅开发环境）"""
    from src.config import settings

    if settings.env == "production":
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Not found")

    return {
        "environment": settings.env,
        "debug": settings.debug,
        "log_level": settings.log_level,
        "database_url": settings.database_url.split("@")[0] + "@***",  # 隐藏密码
        "vector_store_type": settings.vector_store_type,
        "embedding_model": settings.embedding_model,
    }
