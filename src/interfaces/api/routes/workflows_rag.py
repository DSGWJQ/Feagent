"""RAG相关的API端点

为避免文件过大，将RAG相关端点单独放在这个文件中
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.application.services.rag_service import QueryContext, RAGService
from src.domain.value_objects.document_source import DocumentSource
from src.interfaces.api.dependencies.rag import get_rag_service

router = APIRouter(prefix="/workflows", tags=["workflows", "rag"])


class ChatContextRequest(BaseModel):
    """查询工作流上下文的请求"""

    query: str  # 用户查询
    max_context_length: int = 4000  # 最大上下文长度
    top_k: int = 5  # 返回的最相关块数量


class ChatContextResponse(BaseModel):
    """工作流上下文查询响应"""

    query: str
    context: str  # 格式化后的上下文
    sources: list[dict]  # 来源信息
    total_chunks: int
    total_tokens: int


@router.get("/{workflow_id}/chat-context", response_model=ChatContextResponse)
async def get_workflow_chat_context(
    workflow_id: str,
    query: str,
    max_context_length: int = 4000,
    top_k: int = 5,
    rag_service: RAGService = Depends(get_rag_service),
) -> ChatContextResponse:
    """获取工作流对话的上下文信息

    这个端点先检索相关的知识，返回检索到的上下文，
    前端可以展示这些上下文，然后再开始聊天，提高透明度。

    参数：
        workflow_id: 工作流ID
        query: 用户查询
        max_context_length: 最大上下文长度（token数）
        top_k: 返回的相关文档块数量

    返回：
        包含检索到的上下文和来源信息的响应
    """
    try:
        # 构建查询上下文
        query_context = QueryContext(
            query=query,
            workflow_id=workflow_id,
            max_context_length=max_context_length,
            top_k=top_k,
        )

        # 检索上下文
        retrieved_context = await rag_service.retrieve_context(query_context)

        # 返回结果
        return ChatContextResponse(
            query=query,
            context=retrieved_context.formatted_context,
            sources=[
                {
                    "document_id": source["document_id"],
                    "title": source["title"],
                    "source": source["source"],
                    "relevance_score": source["relevance_score"],
                    "preview": source["chunk_preview"],
                }
                for source in retrieved_context.sources
            ],
            total_chunks=len(retrieved_context.chunks),
            total_tokens=retrieved_context.total_tokens,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取上下文失败: {str(e)}",
        )


class DocumentUploadRequest(BaseModel):
    """文档上传请求"""

    title: str  # 文档标题
    content: str  # 文档内容
    source: str = "upload"  # 文档来源


class DocumentUploadResponse(BaseModel):
    """文档上传响应"""

    document_id: str
    message: str
    chunks_count: int


@router.post("/{workflow_id}/documents", response_model=DocumentUploadResponse)
async def upload_document_to_workflow(
    workflow_id: str,
    request: DocumentUploadRequest,
    rag_service: RAGService = Depends(get_rag_service),
) -> DocumentUploadResponse:
    """上传文档到工作流知识库

    参数：
        workflow_id: 工作流ID
        request: 文档上传请求

    返回：
        上传结果和文档ID
    """
    try:
        # 导入文档
        document_id = await rag_service.ingest_document(
            title=request.title,
            content=request.content,
            source=DocumentSource.UPLOAD,
            workflow_id=workflow_id,
            metadata={
                "upload_time": datetime.now().isoformat(),
                "source": request.source,
            },
        )

        # 获取文档块数量
        # TODO: 需要在RAGService中添加获取文档块数量的方法

        return DocumentUploadResponse(
            document_id=document_id,
            message="文档上传成功",
            chunks_count=0,  # 暂时返回0
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文档上传失败: {str(e)}",
        )


class DocumentListResponse(BaseModel):
    """文档列表响应"""

    documents: list[dict]
    total: int


@router.get("/{workflow_id}/documents", response_model=DocumentListResponse)
async def get_workflow_documents(
    workflow_id: str,
    rag_service: RAGService = Depends(get_rag_service),
) -> DocumentListResponse:
    """获取工作流的所有文档

    参数：
        workflow_id: 工作流ID

    返回：
        文档列表
    """
    try:
        # 搜索所有文档来获取完整列表
        documents = await rag_service.search_documents(
            query="",  # 空查询获取所有文档
            workflow_id=workflow_id,
            limit=100,
            threshold=0.0,  # 最低阈值获取所有文档
        )

        # 转换为字典格式
        document_dicts = [
            {
                "id": doc.id,
                "title": doc.title,
                "source": doc.source.value,
                "status": doc.status.value,
                "created_at": doc.created_at.isoformat(),
                "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
                "metadata": doc.metadata,
                "content": doc.content,  # 添加内容字段
            }
            for doc in documents
        ]

        return DocumentListResponse(
            documents=document_dicts,
            total=len(document_dicts),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文档列表失败: {str(e)}",
        )


@router.delete("/{workflow_id}/documents/{document_id}")
async def delete_workflow_document(
    workflow_id: str,
    document_id: str,
    rag_service: RAGService = Depends(get_rag_service),
) -> dict:
    """删除工作流文档

    参数：
        workflow_id: 工作流ID
        document_id: 文档ID

    返回：
        删除结果
    """
    try:
        success = await rag_service.delete_document(document_id)

        return {"success": success, "message": "文档删除成功" if success else "文档删除失败"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除文档失败: {str(e)}",
        )


class SearchDocumentsRequest(BaseModel):
    """搜索文档请求"""

    query: str
    limit: int = 10
    threshold: float = 0.7


class SearchDocumentsResponse(BaseModel):
    """搜索文档响应"""

    query: str
    documents: list[dict]
    total: int


@router.post("/{workflow_id}/documents/search", response_model=SearchDocumentsResponse)
async def search_workflow_documents(
    workflow_id: str,
    request: SearchDocumentsRequest,
    rag_service: RAGService = Depends(get_rag_service),
) -> SearchDocumentsResponse:
    """搜索工作流文档

    参数：
        workflow_id: 工作流ID
        request: 搜索请求

    返回：
        搜索结果
    """
    try:
        # 搜索文档
        documents = await rag_service.search_documents(
            query=request.query,
            workflow_id=workflow_id,
            limit=request.limit,
            threshold=request.threshold,
        )

        # 转换为字典格式
        document_dicts = [
            {
                "id": doc.id,
                "title": doc.title,
                "source": doc.source.value,
                "status": doc.status.value,
                "created_at": doc.created_at.isoformat(),
                "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
                "metadata": doc.metadata,
            }
            for doc in documents
        ]

        return SearchDocumentsResponse(
            query=request.query,
            documents=document_dicts,
            total=len(documents),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索文档失败: {str(e)}",
        )
