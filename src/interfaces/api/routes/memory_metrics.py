"""
Memory Metrics API

内存系统性能监控端点。

Author: Claude Code
Date: 2025-11-30
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.application.services.composite_memory_service import CompositeMemoryService
from src.interfaces.api.dependencies.memory import get_composite_memory_service

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryMetricsResponse(BaseModel):
    """内存性能指标响应"""

    cache_hit_rate: float
    fallback_count: int
    compression_ratio: float
    avg_fallback_time_ms: float
    last_updated: str

    class Config:
        json_schema_extra = {
            "example": {
                "cache_hit_rate": 0.75,
                "fallback_count": 10,
                "compression_ratio": 0.6,
                "avg_fallback_time_ms": 125.5,
                "last_updated": "2025-11-30T10:30:00Z",
            }
        }


class CacheInvalidateResponse(BaseModel):
    """缓存失效响应"""

    status: str
    workflow_id: str


@router.get("/metrics", response_model=MemoryMetricsResponse)
async def get_memory_metrics(
    memory_service: CompositeMemoryService = Depends(get_composite_memory_service),
):
    """
    获取内存系统性能指标

    Returns:
        - cache_hit_rate: 缓存命中率（0-1）
        - fallback_count: 回溯到数据库的次数
        - compression_ratio: 平均压缩比
        - avg_fallback_time_ms: 平均回溯耗时（毫秒）
    """
    metrics = memory_service.get_metrics()

    return MemoryMetricsResponse(
        cache_hit_rate=metrics.cache_hit_rate,
        fallback_count=metrics.fallback_count,
        compression_ratio=metrics.compression_ratio,
        avg_fallback_time_ms=metrics.avg_fallback_time_ms,
        last_updated=metrics.last_updated.isoformat(),
    )


@router.post("/cache/invalidate/{workflow_id}", response_model=CacheInvalidateResponse)
async def invalidate_cache(
    workflow_id: str,
    memory_service: CompositeMemoryService = Depends(get_composite_memory_service),
):
    """
    手动失效指定 workflow 的缓存

    Args:
        workflow_id: 工作流 ID

    Returns:
        操作状态
    """
    memory_service._cache.invalidate(workflow_id)

    return CacheInvalidateResponse(status="invalidated", workflow_id=workflow_id)
