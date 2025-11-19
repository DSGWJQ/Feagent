/**
 * Code Export Modal - 代码导出对话框
 * 
 * 支持导出工作流为 Python 或 TypeScript 代码
 */

import { useState } from 'react';
import { Modal, Radio, Button, message } from 'antd';
import { CopyOutlined, DownloadOutlined } from '@ant-design/icons';
import type { Node, Edge } from '@xyflow/react';
import { generatePythonCode, generateTypeScriptCode } from '../utils/codeGenerator';

interface CodeExportModalProps {
  open: boolean;
  nodes: Node[];
  edges: Edge[];
  onClose: () => void;
}

export default function CodeExportModal({
  open,
  nodes,
  edges,
  onClose,
}: CodeExportModalProps) {
  const [language, setLanguage] = useState<'python' | 'typescript'>('python');

  const code =
    language === 'python'
      ? generatePythonCode(nodes, edges)
      : generateTypeScriptCode(nodes, edges);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    message.success('代码已复制到剪贴板');
  };

  const handleDownload = () => {
    const filename = language === 'python' ? 'workflow.py' : 'workflow.ts';
    const blob = new Blob([code], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    message.success(`代码已下载为 ${filename}`);
  };

  return (
    <Modal
      title="导出代码"
      open={open}
      onCancel={onClose}
      width={800}
      footer={[
        <Button key="copy" icon={<CopyOutlined />} onClick={handleCopy}>
          复制代码
        </Button>,
        <Button
          key="download"
          type="primary"
          icon={<DownloadOutlined />}
          onClick={handleDownload}
        >
          下载文件
        </Button>,
        <Button key="close" onClick={onClose}>
          关闭
        </Button>,
      ]}
    >
      <div style={{ marginBottom: 16 }}>
        <Radio.Group
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
        >
          <Radio.Button value="python">Python</Radio.Button>
          <Radio.Button value="typescript">TypeScript</Radio.Button>
        </Radio.Group>
      </div>

      <div
        style={{
          backgroundColor: '#f5f5f5',
          padding: 16,
          borderRadius: 4,
          maxHeight: 500,
          overflow: 'auto',
        }}
      >
        <pre
          style={{
            margin: 0,
            fontSize: 12,
            fontFamily: 'monospace',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {code}
        </pre>
      </div>
    </Modal>
  );
}

