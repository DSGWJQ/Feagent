"""LLMProviders 路由

定义 LLMProvider 相关的 API 端点：
- POST /api/llm-providers - 注册提供商
- GET /api/llm-providers - 列出所有提供商
- GET /api/llm-providers/{provider_id} - 获取提供商详情
- PUT /api/llm-providers/{provider_id} - 更新提供商
- DELETE /api/llm-providers/{provider_id} - 删除提供商
- POST /api/llm-providers/{provider_id}/enable - 启用提供商
- POST /api/llm-providers/{provider_id}/disable - 禁用提供商

设计原则：
1. 路由只负责 HTTP 层的事情
2. 不包含业务逻辑
3. 依赖注入
4. 异常处理
5. API 密钥掩码显示
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.domain.entities.llm_provider import LLMProvider
from src.domain.exceptions import DomainError, NotFoundError
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories.llm_provider_repository import (
    SQLAlchemyLLMProviderRepository,
)
from src.interfaces.api.dto import (
    DisableLLMProviderRequest,
    EnableLLMProviderRequest,
    LLMProviderListResponse,
    LLMProviderResponse,
    RegisterLLMProviderRequest,
    UpdateLLMProviderRequest,
)

# 创建路由器
router = APIRouter(prefix="/llm-providers", tags=["llm-providers"])


def get_llm_provider_repository(
    session: Session = Depends(get_db_session),
) -> SQLAlchemyLLMProviderRepository:
    """获取 LLMProvider Repository - 依赖注入函数"""
    return SQLAlchemyLLMProviderRepository(session)


def _mask_api_key(api_key: str | None) -> str | None:
    """掩码 API 密钥

    显示格式：sk-***（保留前3个字符，后面用***代替）

    参数：
        api_key: 原始 API 密钥

    返回：
        掩码后的 API 密钥
    """
    if not api_key:
        return None

    if len(api_key) <= 3:
        return "***"

    return f"{api_key[:3]}***"


def _provider_to_response(provider: LLMProvider) -> LLMProviderResponse:
    """将 LLMProvider 实体转换为 Response DTO

    注意：API 密钥会被掩码处理
    """
    return LLMProviderResponse(
        id=provider.id,
        name=provider.name,
        display_name=provider.display_name,
        api_base=provider.api_base,
        api_key=_mask_api_key(provider.api_key),  # 掩码显示
        models=provider.models,
        enabled=provider.enabled,
        config=provider.config,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


@router.post("", response_model=LLMProviderResponse, status_code=status.HTTP_201_CREATED)
def register_llm_provider(
    request: RegisterLLMProviderRequest,
    provider_repository: SQLAlchemyLLMProviderRepository = Depends(get_llm_provider_repository),
    session: Session = Depends(get_db_session),
) -> LLMProviderResponse:
    """注册 LLM 提供商

    业务流程：
    1. 验证输入数据（Pydantic 自动验证）
    2. 创建 LLMProvider 实体（验证业务规则）
    3. 保存到数据库
    4. 返回提供商信息（API 密钥掩码）

    异常处理：
    - 400: 业务规则违反（name 为空、models 为空等）
    - 500: 数据库错误
    """
    try:
        # 创建 LLMProvider 实体
        provider = LLMProvider.create(
            name=request.name,
            display_name=request.display_name,
            api_base=request.api_base,
            api_key=request.api_key,
            models=request.models,
        )

        # 保存到数据库
        provider_repository.save(provider)
        session.commit()

        return _provider_to_response(provider)

    except DomainError as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("", response_model=LLMProviderListResponse)
def list_llm_providers(
    enabled_only: bool = False,
    provider_repository: SQLAlchemyLLMProviderRepository = Depends(get_llm_provider_repository),
) -> LLMProviderListResponse:
    """列出所有 LLM 提供商

    查询参数：
    - enabled_only: 只返回已启用的提供商（默认 False）

    返回：
    - providers: 提供商列表
    - total: 总数量
    """
    try:
        if enabled_only:
            providers = provider_repository.find_enabled()
        else:
            providers = provider_repository.find_all()

        return LLMProviderListResponse(
            providers=[_provider_to_response(provider) for provider in providers],
            total=len(providers),
        )

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{provider_id}", response_model=LLMProviderResponse)
def get_llm_provider(
    provider_id: str,
    provider_repository: SQLAlchemyLLMProviderRepository = Depends(get_llm_provider_repository),
) -> LLMProviderResponse:
    """获取 LLM 提供商详情"""
    try:
        provider = provider_repository.get_by_id(provider_id)
        return _provider_to_response(provider)

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{provider_id}", response_model=LLMProviderResponse)
def update_llm_provider(
    provider_id: str,
    request: UpdateLLMProviderRequest,
    provider_repository: SQLAlchemyLLMProviderRepository = Depends(get_llm_provider_repository),
    session: Session = Depends(get_db_session),
) -> LLMProviderResponse:
    """更新 LLM 提供商

    允许更新：
    - api_key: API 密钥
    - api_base: API 基础 URL
    """
    try:
        provider = provider_repository.get_by_id(provider_id)

        # 更新字段
        if request.api_key is not None:
            provider.update_api_key(request.api_key)
        if request.api_base is not None:
            provider.api_base = request.api_base

        # 更新时间戳
        from datetime import UTC, datetime

        provider.updated_at = datetime.now(UTC)

        # 保存到数据库
        provider_repository.save(provider)
        session.commit()

        return _provider_to_response(provider)

    except NotFoundError as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DomainError as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_llm_provider(
    provider_id: str,
    provider_repository: SQLAlchemyLLMProviderRepository = Depends(get_llm_provider_repository),
    session: Session = Depends(get_db_session),
) -> None:
    """删除 LLM 提供商"""
    try:
        # 验证提供商存在
        provider_repository.get_by_id(provider_id)

        # 删除
        provider_repository.delete(provider_id)
        session.commit()

    except NotFoundError as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{provider_id}/enable", response_model=LLMProviderResponse)
def enable_llm_provider(
    provider_id: str,
    request: EnableLLMProviderRequest,
    provider_repository: SQLAlchemyLLMProviderRepository = Depends(get_llm_provider_repository),
    session: Session = Depends(get_db_session),
) -> LLMProviderResponse:
    """启用 LLM 提供商"""
    try:
        provider = provider_repository.get_by_id(provider_id)

        # 启用
        provider.enable()

        # 保存到数据库
        provider_repository.save(provider)
        session.commit()

        return _provider_to_response(provider)

    except NotFoundError as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{provider_id}/disable", response_model=LLMProviderResponse)
def disable_llm_provider(
    provider_id: str,
    request: DisableLLMProviderRequest,
    provider_repository: SQLAlchemyLLMProviderRepository = Depends(get_llm_provider_repository),
    session: Session = Depends(get_db_session),
) -> LLMProviderResponse:
    """禁用 LLM 提供商"""
    try:
        provider = provider_repository.get_by_id(provider_id)

        # 禁用
        provider.disable()

        # 保存到数据库
        provider_repository.save(provider)
        session.commit()

        return _provider_to_response(provider)

    except NotFoundError as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
