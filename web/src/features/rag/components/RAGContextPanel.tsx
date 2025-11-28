/**
 * RAG上下文面板组件
 *
 * 显示检索到的文档上下文和相关来源
 */

import React, { useState } from 'react';
import {
  Card,
  Typography,
  Space,
  Tag,
  Collapse,
  Button,
  Input,
  Select,
  Spin,
  Alert,
  Empty,
  Divider,
  Tooltip,
  message,
} from 'antd';
import {
  SearchOutlined,
  FileTextOutlined,
  InfoCircleOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import { ragApi, type ChatContextResponse } from '../api/ragApi';

const { Text, Paragraph } = Typography;
const { Panel } = Collapse;
const { TextArea } = Input;

interface RAGContextPanelProps {
  workflowId: string;
  onContextUpdate?: (context: string, sources: any[]) => void;
  visible: boolean;
  onClose?: () => void;
}

export const RAGContextPanel: React.FC<RAGContextPanelProps> = ({
  workflowId,
  onContextUpdate,
  visible,
  onClose,
}) => {
  const [query, setQuery] = useState('');
  const [maxContextLength, setMaxContextLength] = useState(4000);
  const [topK, setTopK] = useState(5);
  const [context, setContext] = useState<ChatContextResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearchContext = async () => {
    if (!query.trim()) {
      message.warning('请输入查询内容');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await ragApi.getChatContext(workflowId, {
        query: query.trim(),
        max_context_length: maxContextLength,
        top_k: topK,
      });

      setContext(response);
      onContextUpdate?.(response.context, response.sources);
      message.success('上下文检索完成');
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || '检索失败';
      setError(errorMessage);
      message.error(`上下文检索失败: ${errorMessage}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearContext = () => {
    setContext(null);
    setQuery('');
    onContextUpdate?.('', []);
  };

  const formatScore = (score: number) => {
    return (score * 100).toFixed(1);
  };

  const getSourceColor = (score: number) => {
    if (score >= 0.8) return '#52c41a';
    if (score >= 0.6) return '#faad14';
    return '#ff4d4f';
  };

  if (!visible) return null;

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <Card
        title={
          <Space>
            <FileTextOutlined style={{ color: '#8b5cf6' }} />
            <span style={{ color: '#fafafa' }}>知识库上下文</span>
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
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          {/* 搜索输入框 */}
          <Space.Compact style={{ width: '100%' }}>
            <Input
              placeholder="输入查询内容..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onPressEnter={handleSearchContext}
              style={{ backgroundColor: '#1a1a1a', borderColor: '#434343', color: '#fafafa' }}
            />
            <Button
              type="primary"
              icon={<SearchOutlined />}
              onClick={handleSearchContext}
              loading={isLoading}
              disabled={!query.trim()}
              style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', borderColor: 'transparent' }}
            >
              检索
            </Button>
            <Button
              icon={<DeleteOutlined />}
              onClick={handleClearContext}
              disabled={!context}
              style={{ backgroundColor: '#262626', borderColor: '#434343', color: '#fafafa' }}
            >
              清除
            </Button>
          </Space.Compact>

          {/* 搜索参数配置 */}
          <div style={{ display: 'flex', gap: '12px' }}>
            <Select
              value={topK}
              onChange={setTopK}
              style={{ width: 100 }}
              options={[
                { label: '3条', value: 3 },
                { label: '5条', value: 5 },
                { label: '10条', value: 10 },
              ]}
            />
            <Select
              value={maxContextLength}
              onChange={setMaxContextLength}
              style={{ width: 120 }}
              options={[
                { label: '2000 tokens', value: 2000 },
                { label: '4000 tokens', value: 4000 },
                { label: '8000 tokens', value: 8000 },
              ]}
            />
          </div>

          {/* 错误信息 */}
          {error && (
            <Alert
              message="检索失败"
              description={error}
              type="error"
              closable
              onClose={() => setError(null)}
            />
          )}
        </Space>
      </Card>

      {/* 上下文内容 */}
      <Card
        title="检索结果"
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
            <div style={{ marginTop: '16px', color: '#8c8c8c' }}>正在检索知识库...</div>
          </div>
        ) : context ? (
          <Space direction="vertical" style={{ width: '100%' }}>
            {/* 检索统计 */}
            <div style={{
              padding: '8px 12px',
              backgroundColor: '#1a1a1a',
              borderRadius: '6px',
              border: '1px solid #262626'
            }}>
              <Space split={<Divider type="vertical" />}>
                <Text style={{ color: '#8c8c8c' }}>
                  <span style={{ color: '#fafafa' }}>{context.total_chunks}</span> 个文档块
                </Text>
                <Text style={{ color: '#8c8c8c' }}>
                  <span style={{ color: '#fafafa' }}>{context.total_tokens}</span> tokens
                </Text>
                <Text style={{ color: '#8c8c8c' }}>
                  <span style={{ color: '#fafafa' }}>{context.sources.length}</span> 个来源
                </Text>
              </Space>
            </div>

            {/* 来源信息 */}
            <Collapse
              ghost
              size="small"
              items={context.sources.map((source, index) => ({
                key: source.document_id,
                label: (
                  <Space>
                    <Text style={{ color: '#fafafa' }}>{index + 1}. {source.title}</Text>
                    <Tag
                      color={getSourceColor(source.relevance_score)}
                      style={{ margin: 0 }}
                    >
                      {formatScore(source.relevance_score)}%
                    </Tag>
                  </Space>
                ),
                children: (
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Text style={{ color: '#8c8c8c' }}>来源: {source.source}</Text>
                      <Tooltip title="相关性分数">
                        <InfoCircleOutlined style={{ color: '#8c8c8c' }} />
                      </Tooltip>
                    </div>
                    <div style={{
                      padding: '8px',
                      backgroundColor: '#1a1a1a',
                      borderRadius: '4px',
                      border: '1px solid #262626'
                    }}>
                      <Text style={{ color: '#fafafa', fontSize: '12px' }}>
                        {source.preview}
                      </Text>
                    </div>
                  </Space>
                ),
              }))}
            />

            {/* 完整上下文 */}
            <div style={{
              padding: '12px',
              backgroundColor: '#1a1a1a',
              borderRadius: '6px',
              border: '1px solid #262626'
            }}>
              <Text strong style={{ color: '#fafafa', display: 'block', marginBottom: '8px' }}>
                格式化上下文:
              </Text>
              <Paragraph
                style={{
                  margin: 0,
                  color: '#fafafa',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  fontSize: '12px',
                  lineHeight: '1.5'
                }}
              >
                {context.context}
              </Paragraph>
            </div>
          </Space>
        ) : (
          <Empty
            description={
              <div style={{ color: '#8c8c8c' }}>
                输入查询内容后，系统将检索相关知识库并显示相关上下文
              </div>
            }
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        )}
      </Card>
    </div>
  );
};

export default RAGContextPanel;
