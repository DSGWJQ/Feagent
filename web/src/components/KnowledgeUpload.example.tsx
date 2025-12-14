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
import styles from '../features/knowledge/styles/knowledge.module.css';

interface KnowledgeUploadProps {
  workflowId?: string;
  onUploadSuccess?: (documentId: string) => void;
  className?: string;
}

export function KnowledgeUpload({ workflowId, onUploadSuccess, className }: KnowledgeUploadProps) {
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
    <div className={className}>
      {/* 文件拖拽区域 */}
      <div
        className={`${styles.dropZone} ${selectedFile ? styles.dropZoneActive : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
      >
        {selectedFile ? (
          <div>
            <div className={styles.uploadIcon}>✅</div>
            <div className={styles.uploadText}>{selectedFile.name}</div>
            <div className={styles.uploadHint}>{(selectedFile.size / 1024).toFixed(2)} KB</div>
          </div>
        ) : (
          <div>
            <div className={styles.uploadIcon}>📤</div>
            <div className={styles.uploadText}>Drop Document Here</div>
            <div className={styles.uploadHint}>
              Supports .txt, .md, .pdf, .doc (Max 10MB)
            </div>
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
              backgroundColor: 'var(--neo-blue)',
              color: '#fff',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              cursor: 'pointer',
              fontFamily: 'var(--font-family-base)',
            }}
          >
            Select File manually
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
              backgroundColor: loading ? 'var(--neo-bg)' : 'var(--color-success)',
              color: '#fff',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: '16px',
            }}
          >
            {loading ? 'Transcribing...' : '🚀 Ingest Document'}
          </button>
        </div>
      )}

      {/* 错误提示 */}
      {error && (
        <div className={styles.errorBox}>
          <strong>❌ Upload Failed:</strong> {error}
        </div>
      )}

      {/* 上传成功结果 */}
      {uploadResult && (
        <div className={styles.resultBox}>
          <h3>✅ Ingestion Complete</h3>
          <div style={{ marginTop: '10px', fontSize: 'var(--font-size-sm)' }}>
            <p><strong>Document ID:</strong> {uploadResult.documentId}</p>
            <p><strong>Chunks:</strong> {uploadResult.chunkCount}</p>
            <p><strong>Tokens:</strong> ~{uploadResult.totalTokens}</p>
            <p style={{ marginTop: '10px', fontSize: '12px', color: 'var(--neo-text-2)' }}>
              💡 Document indexed and ready for retrieval.
            </p>
          </div>
        </div>
      )}

      {/* 使用说明 */}
      <div className={styles.instructions}>
        <h4>📖 Archive Protocols</h4>
        <ul className={styles.instructionList}>
          <li>Supported formats: TXT, Markdown, PDF, Word</li>
          <li>Max file size: 10MB</li>
          <li>Documents are automatically chunked and vectorized</li>
          <li>Private silos created per workflow ID</li>
        </ul>
      </div>
    </div>
  );
}

export default KnowledgeUpload;
