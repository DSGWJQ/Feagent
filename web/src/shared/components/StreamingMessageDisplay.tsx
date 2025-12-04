/**
 * Phase 4: 流式消息显示组件
 *
 * 根据消息类型（thought/tool_call/tool_result/final）差异化展示。
 */

import React, { useMemo } from 'react';
import { Card, Tag, Typography, Space, Collapse, Spin, Alert } from 'antd';
import {
  BulbOutlined,
  ToolOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  MessageOutlined,
  LoadingOutlined,
  WarningOutlined,
} from '@ant-design/icons';

import type {
  StreamingMessage,
  StreamingMessageType,
  ToolCallMetadata,
  ToolResultMetadata,
} from '@/shared/types/streaming';
import { getMessageTypeLabel, isIntermediateStep } from '@/shared/types/streaming';

const { Text, Paragraph } = Typography;
const { Panel } = Collapse;

interface StreamingMessageDisplayProps {
  message: StreamingMessage;
  showDetails?: boolean;
  compact?: boolean;
}

/**
 * 思考消息组件
 */
const ThoughtMessage: React.FC<{ content: string; compact?: boolean }> = ({
  content,
  compact,
}) => (
  <div
    style={{
      padding: compact ? '8px 12px' : '12px 16px',
      backgroundColor: '#2a2a3d',
      borderLeft: '3px solid #8b5cf6',
      borderRadius: '4px',
      marginBottom: '8px',
    }}
  >
    <Space align="start">
      <BulbOutlined style={{ color: '#8b5cf6', fontSize: '16px' }} />
      <div>
        <Text
          type="secondary"
          style={{ fontSize: '12px', display: 'block', marginBottom: '4px' }}
        >
          💭 思考中
        </Text>
        <Text style={{ color: '#d1d5db', whiteSpace: 'pre-wrap' }}>{content}</Text>
      </div>
    </Space>
  </div>
);

/**
 * 工具调用消息组件
 */
const ToolCallMessage: React.FC<{
  metadata: ToolCallMetadata;
  showDetails?: boolean;
  compact?: boolean;
}> = ({ metadata, showDetails, compact }) => {
  const { tool, tool_id, arguments: args } = metadata;

  return (
    <div
      style={{
        padding: compact ? '8px 12px' : '12px 16px',
        backgroundColor: '#1a2744',
        borderLeft: '3px solid #3b82f6',
        borderRadius: '4px',
        marginBottom: '8px',
      }}
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        <Space>
          <ToolOutlined style={{ color: '#3b82f6', fontSize: '16px' }} />
          <Text strong style={{ color: '#60a5fa' }}>
            🔧 调用工具: {tool}
          </Text>
          <Tag color="blue" style={{ fontSize: '10px' }}>
            {tool_id}
          </Tag>
        </Space>

        {showDetails && args && Object.keys(args).length > 0 && (
          <Collapse ghost size="small">
            <Panel
              header={<Text type="secondary" style={{ fontSize: '12px' }}>参数详情</Text>}
              key="args"
            >
              <pre
                style={{
                  backgroundColor: '#0d1117',
                  padding: '8px',
                  borderRadius: '4px',
                  fontSize: '11px',
                  color: '#8b949e',
                  overflow: 'auto',
                  maxHeight: '150px',
                }}
              >
                {JSON.stringify(args, null, 2)}
              </pre>
            </Panel>
          </Collapse>
        )}
      </Space>
    </div>
  );
};

/**
 * 工具结果消息组件
 */
const ToolResultMessage: React.FC<{
  metadata: ToolResultMetadata;
  showDetails?: boolean;
  compact?: boolean;
}> = ({ metadata, showDetails, compact }) => {
  const { tool_id, result, success, error } = metadata;

  return (
    <div
      style={{
        padding: compact ? '8px 12px' : '12px 16px',
        backgroundColor: success ? '#1a2e1a' : '#2e1a1a',
        borderLeft: `3px solid ${success ? '#22c55e' : '#ef4444'}`,
        borderRadius: '4px',
        marginBottom: '8px',
      }}
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        <Space>
          {success ? (
            <CheckCircleOutlined style={{ color: '#22c55e', fontSize: '16px' }} />
          ) : (
            <CloseCircleOutlined style={{ color: '#ef4444', fontSize: '16px' }} />
          )}
          <Text strong style={{ color: success ? '#4ade80' : '#f87171' }}>
            📋 {success ? '工具执行成功' : '工具执行失败'}
          </Text>
          <Tag color={success ? 'green' : 'red'} style={{ fontSize: '10px' }}>
            {tool_id}
          </Tag>
        </Space>

        {!success && error && (
          <Text type="danger" style={{ fontSize: '12px' }}>
            错误: {error}
          </Text>
        )}

        {showDetails && result && (
          <Collapse ghost size="small">
            <Panel
              header={<Text type="secondary" style={{ fontSize: '12px' }}>结果详情</Text>}
              key="result"
            >
              <pre
                style={{
                  backgroundColor: '#0d1117',
                  padding: '8px',
                  borderRadius: '4px',
                  fontSize: '11px',
                  color: '#8b949e',
                  overflow: 'auto',
                  maxHeight: '150px',
                }}
              >
                {typeof result === 'string' ? result : JSON.stringify(result, null, 2)}
              </pre>
            </Panel>
          </Collapse>
        )}
      </Space>
    </div>
  );
};

/**
 * 最终响应消息组件
 */
const FinalMessage: React.FC<{ content: string; compact?: boolean }> = ({
  content,
  compact,
}) => (
  <div
    style={{
      padding: compact ? '12px 16px' : '16px 20px',
      backgroundColor: '#1f2937',
      borderRadius: '8px',
      marginBottom: '8px',
    }}
  >
    <Space align="start">
      <MessageOutlined style={{ color: '#10b981', fontSize: '18px' }} />
      <div>
        <Text
          type="secondary"
          style={{ fontSize: '12px', display: 'block', marginBottom: '8px' }}
        >
          ✅ AI 回复
        </Text>
        <Paragraph
          style={{
            color: '#f3f4f6',
            whiteSpace: 'pre-wrap',
            margin: 0,
            fontSize: '14px',
          }}
        >
          {content}
        </Paragraph>
      </div>
    </Space>
  </div>
);

/**
 * 错误消息组件
 */
const ErrorMessage: React.FC<{
  content: string;
  metadata: { error_code?: string; recoverable?: boolean };
}> = ({ content, metadata }) => (
  <Alert
    type="error"
    showIcon
    icon={<WarningOutlined />}
    message={
      <Space>
        <span>❌ 错误</span>
        {metadata.error_code && (
          <Tag color="red" style={{ fontSize: '10px' }}>
            {metadata.error_code}
          </Tag>
        )}
      </Space>
    }
    description={content}
    style={{ marginBottom: '8px' }}
  />
);

/**
 * 流式加载指示器
 */
const StreamingIndicator: React.FC<{ type: StreamingMessageType }> = ({ type }) => (
  <div
    style={{
      padding: '8px 12px',
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
    }}
  >
    <Spin indicator={<LoadingOutlined style={{ fontSize: 14, color: '#8b5cf6' }} spin />} />
    <Text type="secondary" style={{ fontSize: '12px' }}>
      {getMessageTypeLabel(type)}中...
    </Text>
  </div>
);

/**
 * 主组件：流式消息显示
 */
export const StreamingMessageDisplay: React.FC<StreamingMessageDisplayProps> = ({
  message,
  showDetails = true,
  compact = false,
}) => {
  const { type, content, metadata, is_streaming } = message;

  // 如果正在流式传输，显示加载指示器
  if (is_streaming && !content) {
    return <StreamingIndicator type={type} />;
  }

  // 根据类型渲染不同组件
  switch (type) {
    case 'thought':
      return <ThoughtMessage content={content} compact={compact} />;

    case 'tool_call':
      return (
        <ToolCallMessage
          metadata={metadata as ToolCallMetadata}
          showDetails={showDetails}
          compact={compact}
        />
      );

    case 'tool_result':
      return (
        <ToolResultMessage
          metadata={metadata as ToolResultMetadata}
          showDetails={showDetails}
          compact={compact}
        />
      );

    case 'final':
      return <FinalMessage content={content} compact={compact} />;

    case 'error':
      return (
        <ErrorMessage
          content={content}
          metadata={metadata as { error_code?: string; recoverable?: boolean }}
        />
      );

    case 'status':
      return (
        <div style={{ padding: '4px 8px', marginBottom: '4px' }}>
          <Text type="secondary" style={{ fontSize: '12px' }}>
            📊 {content}
          </Text>
        </div>
      );

    case 'delta':
      return (
        <Text style={{ color: '#d1d5db' }}>
          {content}
        </Text>
      );

    default:
      return null;
  }
};

/**
 * 流式消息列表组件
 */
interface StreamingMessageListProps {
  messages: StreamingMessage[];
  showIntermediateSteps?: boolean;
  showDetails?: boolean;
  compact?: boolean;
}

export const StreamingMessageList: React.FC<StreamingMessageListProps> = ({
  messages,
  showIntermediateSteps = true,
  showDetails = true,
  compact = false,
}) => {
  const filteredMessages = useMemo(() => {
    if (showIntermediateSteps) {
      return messages;
    }
    // 只显示 final 和 error
    return messages.filter((m) => m.type === 'final' || m.type === 'error');
  }, [messages, showIntermediateSteps]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      {filteredMessages.map((message) => (
        <StreamingMessageDisplay
          key={message.message_id || `${message.type}_${message.sequence}`}
          message={message}
          showDetails={showDetails}
          compact={compact}
        />
      ))}
    </div>
  );
};

export default StreamingMessageDisplay;
