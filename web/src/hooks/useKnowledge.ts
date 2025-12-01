/**
 * Knowledge Base Hook
 *
 * 提供知识库管理的 React Hook，包括：
 * - 文档上传（支持格式校验）
 * - 文档列表查询
 * - 文档删除
 * - 统计信息查询
 *
 * @example
 * ```tsx
 * const { uploadDocument, documents, deleteDocument, stats } = useKnowledge();
 *
 * // 上传文档
 * await uploadDocument({
 *   title: "用户手册",
 *   content: "...",
 *   workflowId: "wf_123"
 * });
 *
 * // 列表查询
 * await fetchDocuments({ workflowId: "wf_123" });
 *
 * // 删除文档
 * await deleteDocument("doc_456");
 * ```
 */

import { useState, useCallback } from 'react';
import { apiClient } from '@/services/api';
import type {
  KnowledgeDocument,
  KnowledgeUploadRequest,
  KnowledgeStatsResponse,
} from '@/types/workflow';

interface UseKnowledgeReturn {
  // 状态
  documents: KnowledgeDocument[];
  stats: KnowledgeStatsResponse | null;
  loading: boolean;
  error: string | null;

  // 操作
  uploadDocument: (request: KnowledgeUploadRequest) => Promise<{
    documentId: string;
    chunkCount: number;
    totalTokens: number;
  } | null>;
  fetchDocuments: (params?: {
    workflowId?: string;
    userId?: string;
    source?: string;
    limit?: number;
    offset?: number;
  }) => Promise<void>;
  deleteDocument: (docId: string) => Promise<boolean>;
  fetchStats: (workflowId?: string) => Promise<void>;
  clearError: () => void;
}

/**
 * 文件格式校验配置
 */
const VALIDATION_CONFIG = {
  // 支持的文件扩展名（用于前端文件上传校验）
  allowedExtensions: ['.txt', '.md', '.pdf', '.doc', '.docx'],

  // 最大文件大小（10MB）
  maxFileSize: 10 * 1024 * 1024,

  // 最大内容长度（100万字符）
  maxContentLength: 1000000,

  // 最小内容长度（10字符）
  minContentLength: 10,
};

/**
 * 校验文档内容
 */
function validateDocument(request: KnowledgeUploadRequest): { valid: boolean; error?: string } {
  // 校验标题
  if (!request.title || request.title.trim().length === 0) {
    return { valid: false, error: '文档标题不能为空' };
  }

  if (request.title.length > 200) {
    return { valid: false, error: '文档标题不能超过 200 个字符' };
  }

  // 校验内容
  if (!request.content || request.content.trim().length === 0) {
    return { valid: false, error: '文档内容不能为空' };
  }

  if (request.content.length < VALIDATION_CONFIG.minContentLength) {
    return { valid: false, error: `文档内容至少需要 ${VALIDATION_CONFIG.minContentLength} 个字符` };
  }

  if (request.content.length > VALIDATION_CONFIG.maxContentLength) {
    return { valid: false, error: `文档内容不能超过 ${VALIDATION_CONFIG.maxContentLength} 个字符` };
  }

  return { valid: true };
}

/**
 * 校验文件（用于前端文件上传）
 */
export function validateFile(file: File): { valid: boolean; error?: string } {
  // 校验文件大小
  if (file.size > VALIDATION_CONFIG.maxFileSize) {
    return {
      valid: false,
      error: `文件大小不能超过 ${VALIDATION_CONFIG.maxFileSize / (1024 * 1024)}MB`
    };
  }

  // 校验文件扩展名
  const extension = '.' + file.name.split('.').pop()?.toLowerCase();
  if (!VALIDATION_CONFIG.allowedExtensions.includes(extension)) {
    return {
      valid: false,
      error: `不支持的文件格式，支持的格式：${VALIDATION_CONFIG.allowedExtensions.join(', ')}`
    };
  }

  return { valid: true };
}

/**
 * 知识库管理 Hook
 */
export function useKnowledge(): UseKnowledgeReturn {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [stats, setStats] = useState<KnowledgeStatsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * 上传文档
   */
  const uploadDocument = useCallback(async (request: KnowledgeUploadRequest) => {
    // 前端校验
    const validation = validateDocument(request);
    if (!validation.valid) {
      setError(validation.error || '文档校验失败');
      return null;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.knowledge.upload(request);

      // 上传成功提示
      console.log(`✅ 文档上传成功：${response.data.title}`);
      console.log(`📦 分块数量：${response.data.chunk_count}`);
      console.log(`🔢 Token 统计：${response.data.total_tokens}`);

      return {
        documentId: response.data.document_id,
        chunkCount: response.data.chunk_count,
        totalTokens: response.data.total_tokens,
      };
    } catch (err) {
      const errorMsg = apiClient.handleError(err);
      setError(errorMsg);
      console.error('❌ 文档上传失败:', errorMsg);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * 获取文档列表
   */
  const fetchDocuments = useCallback(async (params?: {
    workflowId?: string;
    userId?: string;
    source?: string;
    limit?: number;
    offset?: number;
  }) => {
    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.knowledge.list(params);
      setDocuments(response.data.documents);

      console.log(`📚 获取文档列表成功：${response.data.total} 条记录`);
    } catch (err) {
      const errorMsg = apiClient.handleError(err);
      setError(errorMsg);
      console.error('❌ 获取文档列表失败:', errorMsg);
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * 删除文档
   */
  const deleteDocument = useCallback(async (docId: string): Promise<boolean> => {
    setLoading(true);
    setError(null);

    try {
      await apiClient.knowledge.delete(docId);

      // 从本地状态中移除
      setDocuments(prev => prev.filter(doc => doc.id !== docId));

      console.log(`🗑️ 文档删除成功：${docId}`);
      return true;
    } catch (err) {
      const errorMsg = apiClient.handleError(err);
      setError(errorMsg);
      console.error('❌ 文档删除失败:', errorMsg);
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * 获取统计信息
   */
  const fetchStats = useCallback(async (workflowId?: string) => {
    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.knowledge.getStats({ workflow_id: workflowId });
      setStats(response.data);

      console.log('📊 知识库统计:', response.data);
    } catch (err) {
      const errorMsg = apiClient.handleError(err);
      setError(errorMsg);
      console.error('❌ 获取统计信息失败:', errorMsg);
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * 清除错误
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    documents,
    stats,
    loading,
    error,
    uploadDocument,
    fetchDocuments,
    deleteDocument,
    fetchStats,
    clearError,
  };
}

export default useKnowledge;
