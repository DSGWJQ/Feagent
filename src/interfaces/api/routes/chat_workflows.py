"""Chat Workflows 路由

定义增强对话工作流相关的 API 端点：
- POST /api/workflows/{workflow_id}/chat - 处理用户消息
- GET /api/workflows/{workflow_id}/chat-history - 获取对话历史
- GET /api/workflows/{workflow_id}/chat-search - 搜索对话历史
- GET /api/workflows/{workflow_id}/suggestions - 获取工作流建议
- DELETE /api/workflows/{workflow_id}/chat-history - 清空对话历史
- GET /api/workflows/{workflow_id}/chat-context - 获取压缩后的上下文
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.application.use_cases.enhanced_chat_workflow import (
    EnhancedChatWorkflowInput,
    EnhancedChatWorkflowUseCase,
)
from src.domain.exceptions import DomainError, NotFoundError
from src.infrastructure.database.engine import get_db_session
from src.infrastructure.database.repositories.workflow_repository import (
    SQLAlchemyWorkflowRepository,
)
from src.interfaces.api.dto.workflow_features_dto import (
    ChatMessageRequest,
    ChatMessageResponse,
    EnhancedChatWorkflowResponse,
)

# 创建路由器
router = APIRouter(tags=["Chat Workflows"])


def get_enhanced_chat_use_case(
    session: Session = Depends(get_db_session),
) -> EnhancedChatWorkflowUseCase:
    """获取 EnhancedChatWorkflowUseCase - 依赖注入函数"""
    workflow_repo = SQLAlchemyWorkflowRepository(session)
    # TODO: 注入真实的 chat_service
    from unittest.mock import Mock
    chat_service = Mock()
    return EnhancedChatWorkflowUseCase(
        workflow_repo=workflow_repo,
        chat_service=chat_service,
    )


@router.post(
    "/workflows/{workflow_id}/chat",
    status_code=status.HTTP_200_OK,
    response_model=EnhancedChatWorkflowResponse,
)
async def chat_workflow(
    workflow_id: str,
    request: ChatMessageRequest,
    use_case: EnhancedChatWorkflowUseCase = Depends(get_enhanced_chat_use_case),
) -> EnhancedChatWorkflowResponse:
    """处理用户消息并更新工作流"""
    try:
        input_data = EnhancedChatWorkflowInput(
            workflow_id=workflow_id,
            user_message=request.message,
        )
        result = use_case.execute(input_data)

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error_message,
            )

        return EnhancedChatWorkflowResponse.from_entity(result)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except DomainError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


@router.get(
    "/workflows/{workflow_id}/chat-history",
    status_code=status.HTTP_200_OK,
    response_model=list[ChatMessageResponse],
)
async def get_chat_history(
    workflow_id: str,
    use_case: EnhancedChatWorkflowUseCase = Depends(get_enhanced_chat_use_case),
) -> list[ChatMessageResponse]:
    """获取对话历史"""
    try:
        history = use_case.get_chat_history()
        return [ChatMessageResponse(**msg) for msg in history]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


@router.get(
    "/workflows/{workflow_id}/chat-search",
    status_code=status.HTTP_200_OK,
)
async def search_conversation_history(
    workflow_id: str,
    keyword: str,
    threshold: float = 0.5,
    use_case: EnhancedChatWorkflowUseCase = Depends(get_enhanced_chat_use_case),
) -> list:
    """搜索对话历史"""
    try:
        results = use_case.search_conversation_history(keyword, threshold)
        return [
            {"content": content, "relevance": relevance}
            for content, relevance in results
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


@router.get(
    "/workflows/{workflow_id}/suggestions",
    status_code=status.HTTP_200_OK,
)
async def get_workflow_suggestions(
    workflow_id: str,
    use_case: EnhancedChatWorkflowUseCase = Depends(get_enhanced_chat_use_case),
) -> list[str]:
    """获取工作流建议"""
    try:
        suggestions = use_case.get_workflow_suggestions(workflow_id)
        return suggestions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


@router.delete(
    "/workflows/{workflow_id}/chat-history",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def clear_conversation_history(
    workflow_id: str,
    use_case: EnhancedChatWorkflowUseCase = Depends(get_enhanced_chat_use_case),
) -> None:
    """清空对话历史"""
    try:
        use_case.clear_conversation_history()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


@router.get(
    "/workflows/{workflow_id}/chat-context",
    status_code=status.HTTP_200_OK,
    response_model=list[ChatMessageResponse],
)
async def get_compressed_context(
    workflow_id: str,
    max_tokens: int = 2000,
    use_case: EnhancedChatWorkflowUseCase = Depends(get_enhanced_chat_use_case),
) -> list[ChatMessageResponse]:
    """获取压缩后的上下文"""
    try:
        context = use_case.get_compressed_context(max_tokens)
        return [ChatMessageResponse(**msg) for msg in context]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )
