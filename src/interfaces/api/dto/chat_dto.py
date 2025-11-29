"""Chat API DTOs - 对话相关的请求/响应对象"""

from pydantic import BaseModel, Field


class ChatMessageResponse(BaseModel):
    """聊天消息响应"""

    id: str
    content: str
    is_user: bool
    timestamp: str

    @classmethod
    def from_entity(cls, entity):
        """从 ChatMessage Entity 创建 DTO"""
        return cls(
            id=entity.id,
            content=entity.content,
            is_user=entity.is_user,
            timestamp=entity.timestamp.isoformat(),
        )


class SearchResultResponse(BaseModel):
    """搜索结果响应"""

    message: ChatMessageResponse
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="相关性分数（0-1）")


class CompressedContextResponse(BaseModel):
    """压缩上下文响应"""

    messages: list[ChatMessageResponse]
    total_tokens: int = Field(..., description="估计的总 token 数")
    compression_ratio: float = Field(..., description="压缩比例（原始数量/压缩后数量）")
