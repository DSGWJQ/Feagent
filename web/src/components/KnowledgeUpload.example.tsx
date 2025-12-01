/**
 * 知识库上传组件示例
 *
 * 展示如何使用 useKnowledge Hook 实现文档上传功能
 *
 * 功能特性：
 * - 文件拖拽上传
 * - 格式校验（文件大小、扩展名）
 * - 上传进度显示
 * - Chunk 数量和 Token 统计展示
 * - 错误提示
 *
 * @example
 * ```tsx
 * <KnowledgeUpload workflowId="wf_123" />
 * ```
 */

import React, { useState, useCallback } from 'react';
import { useKnowledge, validateFile } from '@/hooks/useKnowledge';

interface KnowledgeUploadProps {
  workflowId?: string;
  onUploadSuccess?: (documentId: string) => void;
}

export function KnowledgeUpload({ workflowId, onUploadSuccess }: KnowledgeUploadProps) {
  const { uploadDocument, loading, error, clearError } = useKnowledge();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<{
    documentId: string;
    chunkCount: number;
    totalTokens: number;
  } | null>(null);

  /**
   * 文件选择处理
   */
  const handleFileSelect = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // 前端文件校验
    const validation = validateFile(file);
    if (!validation.valid) {
      alert(validation.error);
      return;
    }

    setSelectedFile(file);
    setUploadResult(null);
    clearError();
  }, [clearError]);

  /**
   * 文件上传处理
   */
  const handleUpload = useCallback(async () => {
    if (!selectedFile) {
      alert('请先选择文件');
      return;
    }

    try {
      // 读取文件内容
      const content = await selectedFile.text();

      // 上传文档
      const result = await uploadDocument({
        title: selectedFile.name,
        content,
        workflowId,
        source: 'upload',
        metadata: {
          filename: selectedFile.name,
          fileSize: selectedFile.size,
          mimeType: selectedFile.type,
        },
      });

      if (result) {
        setUploadResult(result);
        onUploadSuccess?.(result.documentId);
      }
    } catch (err) {
      console.error('文件读取失败:', err);
      alert('文件读取失败，请重试');
    }
  }, [selectedFile, uploadDocument, workflowId, onUploadSuccess]);

  /**
   * 拖拽上传处理
   */
  const handleDrop = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const file = event.dataTransfer.files?.[0];
    if (!file) return;

    // 前端文件校验
    const validation = validateFile(file);
    if (!validation.valid) {
      alert(validation.error);
      return;
    }

    setSelectedFile(file);
    setUploadResult(null);
    clearError();
  }, [clearError]);

  const handleDragOver = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
  }, []);

  return (
    <div className="knowledge-upload-container">
      <h2>📚 知识库上传</h2>

      {/* 文件拖拽区域 */}
      <div
        className="drop-zone"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        style={{
          border: '2px dashed #ccc',
          borderRadius: '8px',
          padding: '40px',
          textAlign: 'center',
          cursor: 'pointer',
          backgroundColor: selectedFile ? '#f0f0f0' : '#fff',
        }}
      >
        {selectedFile ? (
          <div>
            <p>✅ 已选择文件：{selectedFile.name}</p>
            <p>📦 文件大小：{(selectedFile.size / 1024).toFixed(2)} KB</p>
          </div>
        ) : (
          <div>
            <p>拖拽文件到此处，或点击选择文件</p>
            <p style={{ color: '#999', fontSize: '12px' }}>
              支持格式：.txt, .md, .pdf, .doc, .docx（最大 10MB）
            </p>
          </div>
        )}

        <input
          type="file"
          accept=".txt,.md,.pdf,.doc,.docx"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
          id="file-input"
        />
        <label htmlFor="file-input" style={{ cursor: 'pointer' }}>
          <button
            type="button"
            onClick={() => document.getElementById('file-input')?.click()}
            style={{
              marginTop: '20px',
              padding: '10px 20px',
              backgroundColor: '#007bff',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            选择文件
          </button>
        </label>
      </div>

      {/* 上传按钮 */}
      {selectedFile && (
        <div style={{ marginTop: '20px', textAlign: 'center' }}>
          <button
            onClick={handleUpload}
            disabled={loading}
            style={{
              padding: '12px 30px',
              backgroundColor: loading ? '#ccc' : '#28a745',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: '16px',
            }}
          >
            {loading ? '上传中...' : '🚀 上传文档'}
          </button>
        </div>
      )}

      {/* 错误提示 */}
      {error && (
        <div
          style={{
            marginTop: '20px',
            padding: '15px',
            backgroundColor: '#f8d7da',
            color: '#721c24',
            borderRadius: '4px',
            border: '1px solid #f5c6cb',
          }}
        >
          <strong>❌ 上传失败：</strong>{error}
        </div>
      )}

      {/* 上传成功结果 */}
      {uploadResult && (
        <div
          style={{
            marginTop: '20px',
            padding: '20px',
            backgroundColor: '#d4edda',
            color: '#155724',
            borderRadius: '4px',
            border: '1px solid #c3e6cb',
          }}
        >
          <h3>✅ 上传成功！</h3>
          <div style={{ marginTop: '10px' }}>
            <p><strong>文档 ID：</strong>{uploadResult.documentId}</p>
            <p><strong>分块数量：</strong>{uploadResult.chunkCount} 个</p>
            <p><strong>Token 统计：</strong>~{uploadResult.totalTokens} tokens</p>
            <p style={{ marginTop: '10px', fontSize: '12px', color: '#666' }}>
              💡 提示：文档已成功切分并向量化，可用于 RAG 检索
            </p>
          </div>
        </div>
      )}

      {/* 使用说明 */}
      <div
        style={{
          marginTop: '30px',
          padding: '15px',
          backgroundColor: '#e7f3ff',
          borderRadius: '4px',
          fontSize: '14px',
        }}
      >
        <h4>📖 使用说明</h4>
        <ul style={{ marginLeft: '20px' }}>
          <li>支持 TXT、Markdown、PDF、Word 等格式</li>
          <li>文件大小限制：10MB</li>
          <li>文档会自动切分为多个 chunk，便于检索</li>
          <li>上传后可在对话中使用 RAG 功能获取文档内容</li>
          <li>每个 workflow 可以有独立的知识库</li>
        </ul>
      </div>
    </div>
  );
}

export default KnowledgeUpload;
