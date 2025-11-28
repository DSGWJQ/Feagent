/**
 * Code Export Modal - 代码导出对话框
 *
 * 支持导出工作流为 Python 或 TypeScript 代码
 */

import { useState } from 'react';
import { Modal, Radio, Button, message, ConfigProvider, theme } from 'antd';
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
    <ConfigProvider
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorBgContainer: '#141414',
          colorBgElevated: '#1a1a1a',
          colorBorder: '#262626',
          colorText: '#fafafa',
          colorTextSecondary: '#8c8c8c',
          colorPrimary: '#8b5cf6',
        },
      }}
    >
      <Modal
        title="导出代码"
        open={open}
        onCancel={onClose}
        width={800}
        styles={{
          header: {
            backgroundColor: '#1a1a1a',
            borderBottom: '1px solid #262626',
            color: '#fafafa',
          },
          body: {
            backgroundColor: '#141414',
            color: '#fafafa',
          },
          footer: {
            backgroundColor: '#1a1a1a',
            borderTop: '1px solid #262626',
          },
        }}
        footer={[
          <Button
            key="copy"
            icon={<CopyOutlined />}
            onClick={handleCopy}
            style={{
              backgroundColor: '#262626',
              borderColor: '#434343',
              color: '#fafafa',
            }}
          >
            复制代码
          </Button>,
          <Button
            key="download"
            type="primary"
            icon={<DownloadOutlined />}
            onClick={handleDownload}
            style={{
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              borderColor: 'transparent',
            }}
          >
            下载文件
          </Button>,
          <Button
            key="close"
            onClick={onClose}
            style={{
              backgroundColor: '#262626',
              borderColor: '#434343',
              color: '#fafafa',
            }}
          >
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
            backgroundColor: '#1a1a1a',
            padding: 16,
            borderRadius: 4,
            maxHeight: 500,
            overflow: 'auto',
            border: '1px solid #262626',
          }}
        >
          <pre
            style={{
              margin: 0,
              fontSize: 12,
              fontFamily: 'monospace',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              color: '#fafafa',
            }}
          >
            {code}
          </pre>
        </div>
      </Modal>
    </ConfigProvider>
  );
}
