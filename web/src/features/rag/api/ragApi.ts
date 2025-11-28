/**
 * RAG API Client
 *
 * 提供与后端RAG服务的API交互功能
 */

import { axiosInstance } from '@/services/api';

// RAG相关类型定义
export interface ChatContextRequest {
  query: string;
  max_context_length?: number;
  top_k?: number;
}

export interface ChatContextResponse {
  query: string;
  context: string;
  sources: Array<{
    document_id: string;
    title: string;
    source: string;
    relevance_score: number;
    preview: string;
  }>;
  total_chunks: number;
  total_tokens: number;
}

export interface DocumentUploadRequest {
  title: string;
  content: string;
  source?: string;
}

export interface DocumentUploadResponse {
  document_id: string;
  message: string;
  chunks_count: number;
}

export interface DocumentListResponse {
  documents: Array<{
    id: string;
    title: string;
    source: string;
    status: string;
    created_at: string;
    updated_at?: string;
    metadata?: Record<string, any>;
  }>;
  total: number;
}

export interface SearchDocumentsRequest {
  query: string;
  limit?: number;
  threshold?: number;
}

export interface SearchDocumentsResponse {
  query: string;
  documents: Array<{
    id: string;
    title: string;
    source: string;
    status: string;
    created_at: string;
    updated_at?: string;
    metadata?: Record<string, any>;
  }>;
  total: number;
}

export interface DocumentStatsResponse {
  total_documents: number;
  total_chunks: number;
  workflow_id?: string;
}

export interface DeleteDocumentResponse {
  success: boolean;
  message: string;
}

// RAG API 方法
export const ragApi = {
  /**
   * 获取工作流的对话上下文
   */
  async getChatContext(
    workflowId: string,
    params: ChatContextRequest
  ): Promise<ChatContextResponse> {
    const response = await axiosInstance.get(`/workflows/${workflowId}/chat-context`, {
      params: {
        query: params.query,
        max_context_length: params.max_context_length || 4000,
        top_k: params.top_k || 5,
      },
    });
    return response.data;
  },

  /**
   * 上传文档到工作流知识库
   */
  async uploadDocument(
    workflowId: string,
    document: DocumentUploadRequest
  ): Promise<DocumentUploadResponse> {
    const response = await axiosInstance.post(`/workflows/${workflowId}/documents`, document);
    return response.data;
  },

  /**
   * 获取工作流的所有文档
   */
  async getDocuments(workflowId: string): Promise<DocumentListResponse> {
    const response = await axiosInstance.get(`/workflows/${workflowId}/documents`);
    return response.data;
  },

  /**
   * 搜索工作流文档
   */
  async searchDocuments(
    workflowId: string,
    searchParams: SearchDocumentsRequest
  ): Promise<SearchDocumentsResponse> {
    const response = await axiosInstance.post(`/workflows/${workflowId}/documents/search`, searchParams);
    return response.data;
  },

  /**
   * 删除工作流文档
   */
  async deleteDocument(
    workflowId: string,
    documentId: string
  ): Promise<DeleteDocumentResponse> {
    const response = await axiosInstance.delete(`/workflows/${workflowId}/documents/${documentId}`);
    return response.data;
  },

  /**
   * 获取文档统计信息
   */
  async getDocumentStats(workflowId?: string): Promise<DocumentStatsResponse> {
    const url = workflowId
      ? `/workflows/${workflowId}/documents/stats`
      : '/workflows/documents/stats';

    const response = await axiosInstance.get(url);
    return response.data;
  },
};
