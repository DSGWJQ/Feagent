/**
 * Phase 4: 流式消息显示组件
 *
 * 根据消息类型（thought/tool_call/tool_result/final）差异化展示。
 * 使用CSS Module + 设计Token系统
 */

import React, { useMemo } from 'react';
import { Tag, Typography, Space, Collapse, Spin, Alert } from 'antd';
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
import { getMessageTypeLabel } from '@/shared/types/streaming';
import styles from './StreamingMessageDisplay.module.css';

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
  <div className={`${styles.thoughtMessage} ${compact ? styles.compact : ''}`}>
    <Space align="start">
      <BulbOutlined className={styles.thoughtIcon} />
      <div>
        <Text type="secondary" className={styles.thoughtLabel}>
          💭 思考中
        </Text>
        <Text className={styles.thoughtContent}>{content}</Text>
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
    <div className={`${styles.toolCallMessage} ${compact ? styles.compact : ''}`}>
      <Space direction="vertical" style={{ width: '100%' }}>
        <Space>
          <ToolOutlined className={styles.toolIcon} />
          <Text strong className={styles.toolName}>
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
              <pre className={styles.argsPanel}>
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
      className={`${styles.toolResultMessage} ${compact ? styles.compact : ''} ${
        success ? styles.success : styles.error
      }`}
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        <Space>
          {success ? (
            <CheckCircleOutlined className={styles.successIcon} />
          ) : (
            <CloseCircleOutlined className={styles.errorIcon} />
          )}
          <Text strong className={success ? styles.successText : styles.errorText}>
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

        {showDetails && result != null && (
          <Collapse ghost size="small">
            <Panel
              header={<Text type="secondary" style={{ fontSize: '12px' }}>结果详情</Text>}
              key="result"
            >
              <pre className={styles.argsPanel}>
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
  <div className={`${styles.finalMessage} ${compact ? styles.compact : ''}`}>
    <Space align="start">
      <MessageOutlined className={styles.finalIcon} />
      <div>
        <Text type="secondary" className={styles.finalLabel}>
          ✅ AI 回复
        </Text>
        <Paragraph className={styles.finalContent}>
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
    className={styles.errorMessage}
  />
);

/**
 * 流式加载指示器
 */
const StreamingIndicator: React.FC<{ type: StreamingMessageType }> = ({ type }) => (
  <div className={styles.streamingIndicator}>
    <Spin indicator={<LoadingOutlined className={styles.streamingSpinner} spin />} />
    <Text type="secondary" className={styles.streamingLabel}>
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
        <div className={styles.statusMessage}>
          <Text type="secondary" className={styles.statusText}>
            📊 {content}
          </Text>
        </div>
      );

    case 'delta':
      return (
        <Text className={styles.deltaText}>
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
    <div className={styles.messageList}>
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
