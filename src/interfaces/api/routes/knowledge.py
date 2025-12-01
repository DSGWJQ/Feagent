"""Knowledge Base API Routes

提供知识库文档管理的 REST API 接口
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.services.rag_service import RAGService
from src.domain.exceptions import DomainError
from src.domain.value_objects.document_source import DocumentSource
from src.interfaces.api.dependencies.rag import get_rag_service
from src.interfaces.api.dto.knowledge_dto import (
    DeleteDocumentResponse,
    DocumentResponse,
    KnowledgeStatsResponse,
    ListDocumentsResponse,
    UploadDocumentRequest,
    UploadDocumentResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.post("/upload", response_model=UploadDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: UploadDocumentRequest,
    rag_service: RAGService = Depends(get_rag_service),
):
    """上传文档到知识库

    业务场景：用户上传文档到个人知识库或工作流知识库

    请求参数：
    - title: 文档标题
    - content: 文档内容
    - workflow_id: 工作流 ID（可选，为空则为个人知识库）
    - source: 文档来源（upload|import|crawl）
    - metadata: 元数据（可选）
    - file_path: 文件路径（可选）

    返回：
    - document_id: 文档 ID
    - chunk_count: 分块数量
    - total_tokens: 总 token 数（估算）

    错误码：
    - 400: 请求参数无效
    - 500: 服务器内部错误
    """
    try:
        # 验证文档来源
        try:
            source = DocumentSource(request.source)
        except ValueError:
            source = DocumentSource.UPLOAD

        # 导入文档到知识库
        document_id = await rag_service.ingest_document(
            title=request.title,
            content=request.content,
            source=source,
            workflow_id=request.workflow_id,
            metadata=request.metadata,
            file_path=request.file_path,
        )

        # 获取文档信息
        document = await rag_service.repository.find_document_by_id(document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="文档上传成功，但无法获取文档信息",
            )

        # 获取分块数量
        chunks = await rag_service.repository.find_chunks_by_document_id(document_id)
        chunk_count = len(chunks)

        # 估算 token 数（简化计算：字符数 / 2）
        total_tokens = len(request.content) // 2

        logger.info(
            f"Document uploaded: {document_id}, chunks: {chunk_count}, tokens: ~{total_tokens}"
        )

        return UploadDocumentResponse(
            document_id=document_id,
            title=request.title,
            chunk_count=chunk_count,
            total_tokens=total_tokens,
            message=f"文档上传成功，已切分为 {chunk_count} 个块",
        )

    except DomainError as exc:
        logger.error(f"Domain error during document upload: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error(f"Unexpected error during document upload: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文档上传失败: {exc}",
        ) from exc


@router.get("", response_model=ListDocumentsResponse)
async def list_documents(
    workflow_id: str | None = None,
    user_id: str | None = None,
    source: str | None = None,
    limit: int = 50,
    offset: int = 0,
    rag_service: RAGService = Depends(get_rag_service),
):
    """获取文档列表

    业务场景：用户查询文档列表（支持过滤）

    查询参数：
    - workflow_id: 工作流 ID（可选，过滤特定工作流的文档）
    - user_id: 用户 ID（可选，过滤特定用户的文档）
    - source: 文档来源（可选，过滤特定来源）
    - limit: 数量限制（默认 50，最大 100）
    - offset: 偏移量（默认 0）

    返回：
    - documents: 文档列表
    - total: 总数量
    - limit: 数量限制
    - offset: 偏移量

    错误码：
    - 400: 请求参数无效
    - 500: 服务器内部错误
    """
    try:
        # 根据过滤条件查询文档
        if workflow_id:
            documents = await rag_service.repository.find_documents_by_workflow_id(workflow_id)
        else:
            # TODO: 实现全局文档列表查询（需要在仓储中添加方法）
            # 目前返回空列表
            documents = []

        # 应用分页
        total = len(documents)
        documents = documents[offset : offset + limit]

        # 转换为响应 DTO
        document_responses = []
        for doc in documents:
            chunks = await rag_service.repository.find_chunks_by_document_id(doc.id)
            chunk_count = len(chunks)
            total_tokens = len(doc.content) // 2  # 估算

            document_responses.append(
                DocumentResponse(
                    id=doc.id,
                    title=doc.title,
                    workflow_id=doc.workflow_id,
                    source=doc.source.value,
                    status=doc.status.value,
                    chunk_count=chunk_count,
                    total_tokens=total_tokens,
                    created_at=doc.created_at,
                    updated_at=doc.updated_at,
                )
            )

        logger.info(f"Listed {len(document_responses)} documents (total: {total})")

        return ListDocumentsResponse(
            documents=document_responses,
            total=total,
            limit=limit,
            offset=offset,
        )

    except Exception as exc:
        logger.error(f"Error listing documents: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文档列表失败: {exc}",
        ) from exc


@router.delete("/{document_id}", response_model=DeleteDocumentResponse)
async def delete_document(
    document_id: str,
    rag_service: RAGService = Depends(get_rag_service),
):
    """删除文档

    业务场景：用户删除知识库中的文档

    路径参数：
    - document_id: 文档 ID

    返回：
    - document_id: 文档 ID
    - status: 删除状态
    - message: 提示消息

    错误码：
    - 404: 文档不存在
    - 500: 服务器内部错误
    """
    try:
        # 验证文档是否存在
        document = await rag_service.repository.find_document_by_id(document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"文档 {document_id} 不存在",
            )

        # 删除文档
        success = await rag_service.delete_document(document_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="文档删除失败",
            )

        logger.info(f"Document deleted: {document_id}")

        return DeleteDocumentResponse(
            document_id=document_id,
            status="deleted",
            message="文档删除成功",
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error deleting document {document_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除文档失败: {exc}",
        ) from exc


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    rag_service: RAGService = Depends(get_rag_service),
):
    """获取文档详情

    业务场景：用户查看文档详细信息

    路径参数：
    - document_id: 文档 ID

    返回：
    - 文档详情

    错误码：
    - 404: 文档不存在
    - 500: 服务器内部错误
    """
    try:
        # 查询文档
        document = await rag_service.repository.find_document_by_id(document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"文档 {document_id} 不存在",
            )

        # 获取分块数量
        chunks = await rag_service.repository.find_chunks_by_document_id(document_id)
        chunk_count = len(chunks)

        # 估算 token 数
        total_tokens = len(document.content) // 2

        logger.info(f"Retrieved document: {document_id}")

        return DocumentResponse(
            id=document.id,
            title=document.title,
            workflow_id=document.workflow_id,
            source=document.source.value,
            status=document.status.value,
            chunk_count=chunk_count,
            total_tokens=total_tokens,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error retrieving document {document_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文档失败: {exc}",
        ) from exc


@router.get("/stats/summary", response_model=KnowledgeStatsResponse)
async def get_knowledge_stats(
    workflow_id: str | None = None,
    rag_service: RAGService = Depends(get_rag_service),
):
    """获取知识库统计信息

    业务场景：用户查看知识库统计数据

    查询参数：
    - workflow_id: 工作流 ID（可选，统计特定工作流）

    返回：
    - total_documents: 总文档数
    - total_chunks: 总分块数
    - total_tokens: 总 token 数（估算）
    - by_workflow: 按工作流统计
    - by_source: 按来源统计

    错误码：
    - 500: 服务器内部错误
    """
    try:
        stats = await rag_service.get_document_stats(workflow_id=workflow_id)

        logger.info(f"Retrieved knowledge stats: {stats}")

        return KnowledgeStatsResponse(
            total_documents=stats.get("total_documents", 0),
            total_chunks=stats.get("total_chunks", 0),
            total_tokens=0,  # TODO: 实现 token 统计
            by_workflow=stats.get("by_workflow", {}),
            by_source=stats.get("by_source", {}),
        )

    except Exception as exc:
        logger.error(f"Error retrieving knowledge stats: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计信息失败: {exc}",
        ) from exc
