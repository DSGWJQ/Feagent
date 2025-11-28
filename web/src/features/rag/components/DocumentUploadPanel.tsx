/**
 * 文档上传面板组件
 *
 * 提供文档上传、管理功能
 */

import React, { useState } from 'react';
import {
  Card,
  Upload,
  Button,
  List,
  Typography,
  Space,
  Tag,
  Popconfirm,
  message,
  Modal,
  Input,
  Alert,
  Spin,
  Empty,
  Divider,
  Tooltip,
} from 'antd';
import {
  UploadOutlined,
  FileTextOutlined,
  DeleteOutlined,
  EyeOutlined,
  InfoCircleOutlined,
  CloudUploadOutlined,
} from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { ragApi, type DocumentListResponse } from '../api/ragApi';

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

interface DocumentUploadPanelProps {
  workflowId: string;
  visible: boolean;
}

export const DocumentUploadPanel: React.FC<DocumentUploadPanelProps> = ({
  workflowId,
  visible,
}) => {
  const [documents, setDocuments] = useState<DocumentListResponse['documents']>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [documentTitle, setDocumentTitle] = useState('');
  const [documentContent, setDocumentContent] = useState('');
  const [error, setError] = useState<string | null>(null);

  // 加载文档列表
  const loadDocuments = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await ragApi.getDocuments(workflowId);
      setDocuments(response.documents);
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || '加载失败';
      setError(errorMessage);
      message.error(`加载文档失败: ${errorMessage}`);
    } finally {
      setIsLoading(false);
    }
  };

  React.useEffect(() => {
    if (visible && workflowId) {
      loadDocuments();
    }
  }, [visible, workflowId]);

  // 处理文件上传
  const handleFileUpload: UploadProps['beforeUpload'] = (file) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      setDocumentContent(content);
      setDocumentTitle(file.name);
      setUploadModalVisible(true);
    };

    reader.onerror = () => {
      message.error('文件读取失败');
    };

    reader.readAsText(file);
    return false; // 阻止默认上传行为
  };

  // 手动上传文档
  const handleManualUpload = () => {
    setDocumentContent('');
    setDocumentTitle('');
    setUploadModalVisible(true);
  };

  // 确认上传文档
  const handleConfirmUpload = async () => {
    if (!documentTitle.trim() || !documentContent.trim()) {
      message.warning('请填写文档标题和内容');
      return;
    }

    setIsUploading(true);
    setError(null);

    try {
      const response = await ragApi.uploadDocument(workflowId, {
        title: documentTitle.trim(),
        content: documentContent.trim(),
        source: 'upload',
      });

      message.success(`文档上传成功，生成 ${response.chunks_count} 个文档块`);
      setUploadModalVisible(false);
      setDocumentTitle('');
      setDocumentContent('');
      loadDocuments(); // 重新加载文档列表
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || '上传失败';
      setError(errorMessage);
      message.error(`文档上传失败: ${errorMessage}`);
    } finally {
      setIsUploading(false);
    }
  };

  // 删除文档
  const handleDeleteDocument = async (documentId: string) => {
    try {
      const response = await ragApi.deleteDocument(workflowId, documentId);

      if (response.success) {
        message.success('文档删除成功');
        loadDocuments(); // 重新加载文档列表
      } else {
        message.error(response.message);
      }
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || '删除失败';
      message.error(`文档删除失败: ${errorMessage}`);
    }
  };

  // 查看文档内容
  const handleViewDocument = (content: string) => {
    Modal.info({
      title: '文档内容',
      content: (
        <div style={{ maxHeight: '400px', overflow: 'auto' }}>
          <Paragraph style={{ margin: 0 }}>
            {content}
          </Paragraph>
        </div>
      ),
      width: 600,
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'processed': return 'success';
      case 'processing': return 'processing';
      case 'failed': return 'error';
      default: return 'default';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'processed': return '已处理';
      case 'processing': return '处理中';
      case 'failed': return '处理失败';
      case 'pending': return '等待处理';
      default: return status;
    }
  };

  if (!visible) return null;

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <Card
        title={
          <Space>
            <FileTextOutlined style={{ color: '#8b5cf6' }} />
            <span style={{ color: '#fafafa' }}>知识库文档</span>
          </Space>
        }
        size="small"
        style={{
          backgroundColor: '#141414',
          borderColor: '#262626',
        }}
        headStyle={{
          backgroundColor: '#1a1a1a',
          borderBottom: '1px solid #262626',
          color: '#fafafa',
        }}
        bodyStyle={{
          backgroundColor: '#141414',
          padding: '12px',
        }}
        extra={
          <Space>
            <Button
              size="small"
              icon={<UploadOutlined />}
              onClick={handleManualUpload}
              style={{ backgroundColor: '#262626', borderColor: '#434343', color: '#fafafa' }}
            >
              手动添加
            </Button>
          </Space>
        }
      >
        <Upload
          accept=".txt,.md,.doc,.docx"
          beforeUpload={handleFileUpload}
          showUploadList={false}
        >
          <Button
            icon={<CloudUploadOutlined />}
            style={{ backgroundColor: '#262626', borderColor: '#434343', color: '#fafafa' }}
          >
            上传文档
          </Button>
        </Upload>
        <div style={{ fontSize: '12px', color: '#8c8c8c', marginTop: '4px' }}>
          支持 .txt, .md, .doc, .docx 格式
        </div>
      </Card>

      {/* 文档列表 */}
      <Card
        title={`文档列表 (${documents.length})`}
        size="small"
        style={{
          flex: 1,
          backgroundColor: '#141414',
          borderColor: '#262626',
          overflow: 'hidden',
        }}
        headStyle={{
          backgroundColor: '#1a1a1a',
          borderBottom: '1px solid #262626',
          color: '#fafafa',
        }}
        bodyStyle={{
          backgroundColor: '#141414',
          padding: '12px',
          height: 'calc(100% - 48px)',
          overflow: 'auto',
        }}
      >
        {isLoading ? (
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <Spin size="large" />
            <div style={{ marginTop: '16px', color: '#8c8c8c' }}>加载文档列表...</div>
          </div>
        ) : error ? (
          <Alert
            message="加载失败"
            description={error}
            type="error"
            closable
            onClose={() => setError(null)}
          />
        ) : documents.length > 0 ? (
          <List
            dataSource={documents}
            renderItem={(doc) => (
              <List.Item
                actions={[
                  <Tooltip title="查看内容">
                    <Button
                      type="text"
                      size="small"
                      icon={<EyeOutlined />}
                      onClick={() => handleViewDocument(doc.content || '暂无内容')}
                      style={{ color: '#8c8c8c' }}
                    />
                  </Tooltip>,
                  <Popconfirm
                    title="确定要删除这个文档吗？"
                    onConfirm={() => handleDeleteDocument(doc.id)}
                    okText="删除"
                    cancelText="取消"
                  >
                    <Tooltip title="删除文档">
                      <Button
                        type="text"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        style={{ color: '#ff4d4f' }}
                      />
                    </Tooltip>
                  </Popconfirm>,
                ]}
                style={{
                  padding: '8px 0',
                  borderBottom: '1px solid #262626',
                }}
              >
                <List.Item.Meta
                  title={
                    <Space>
                      <Text style={{ color: '#fafafa' }}>{doc.title}</Text>
                      <Tag color={getStatusColor(doc.status)}>
                        {getStatusText(doc.status)}
                      </Tag>
                    </Space>
                  }
                  description={
                    <Space direction="vertical" style={{ width: '100%' }}>
                      <Text style={{ color: '#8c8c8c', fontSize: '12px' }}>
                        来源: {doc.source}
                      </Text>
                      <Text style={{ color: '#8c8c8c', fontSize: '12px' }}>
                        创建时间: {new Date(doc.created_at).toLocaleString('zh-CN')}
                      </Text>
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        ) : (
          <Empty
            description={
              <div style={{ color: '#8c8c8c' }}>
                暂无文档，点击上方按钮上传文档
              </div>
            }
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        )}
      </Card>

      {/* 文档上传/编辑模态框 */}
      <Modal
        title="添加文档"
        open={uploadModalVisible}
        onOk={handleConfirmUpload}
        onCancel={() => {
          setUploadModalVisible(false);
          setDocumentTitle('');
          setDocumentContent('');
        }}
        confirmLoading={isUploading}
        okText="上传"
        cancelText="取消"
        style={{
          backgroundColor: '#141414',
        }}
        styles={{
          body: { backgroundColor: '#141414' },
          header: { backgroundColor: '#1a1a1a', color: '#fafafa' },
        }}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Text style={{ color: '#fafafa' }}>文档标题 *</Text>
            <Input
              value={documentTitle}
              onChange={(e) => setDocumentTitle(e.target.value)}
              placeholder="请输入文档标题"
              style={{
                marginTop: '8px',
                backgroundColor: '#1a1a1a',
                borderColor: '#434343',
                color: '#fafafa'
              }}
            />
          </div>
          <div>
            <Text style={{ color: '#fafafa' }}>文档内容 *</Text>
            <TextArea
              value={documentContent}
              onChange={(e) => setDocumentContent(e.target.value)}
              placeholder="请输入文档内容（支持Markdown格式）"
              autoSize={{ minRows: 6, maxRows: 12 }}
              style={{
                marginTop: '8px',
                backgroundColor: '#1a1a1a',
                borderColor: '#434343',
                color: '#fafafa'
              }}
            />
          </div>
          <div style={{ fontSize: '12px', color: '#8c8c8c' }}>
            <InfoCircleOutlined /> 提示：支持纯文本和Markdown格式，文档将被分块并生成向量嵌入
          </div>
        </Space>
      </Modal>
    </div>
  );
};

export default DocumentUploadPanel;
