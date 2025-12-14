/**
 * Phase 4: 集成流式消息的聊天组件
 *
 * 实时展示不同类型消息：thought/tool_call/tool_result/final
 */

import React, { useEffect, useRef, useState } from 'react';
import { Input, Button, Space, Typography, Badge, Tooltip } from 'antd';
import {
  RobotOutlined,
  UserOutlined,
  LoadingOutlined,
  SendOutlined,
  ClearOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
} from '@ant-design/icons';

import { useConversationStream } from '@/hooks/useConversationStream';
import { StreamingMessageList } from './StreamingMessageDisplay';
import styles from './AIChat.module.css';

const { TextArea } = Input;
const { Text } = Typography;

interface StreamingChatProps {
  /** 工作流 ID（可选） */
  workflowId?: string;
  /** 显示欢迎消息 */
  showWelcome?: boolean;
  /** 显示中间步骤 */
  showIntermediateSteps?: boolean;
  /** 收到最终响应时的回调 */
  onFinalResponse?: (content: string) => void;
  /** 样式 */
  style?: React.CSSProperties;
  /** 自定义类名 */
  className?: string;
}

/**
 * 流式聊天组件
 *
 * 实时展示 AI 思考过程、工具调用和最终响应。
 */
export const StreamingChat: React.FC<StreamingChatProps> = ({
  workflowId,
  showWelcome = true,
  showIntermediateSteps: initialShowSteps = true,
  onFinalResponse,
  style,
  className,
}) => {
  const [inputValue, setInputValue] = useState('');
  const [showSteps, setShowSteps] = useState(initialShowSteps);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    messages,
    chatMessages,
    isStreaming,
    sessionId,
    error,
    sendMessage,
    cancel,
    clearMessages,
  } = useConversationStream({
    workflowId,
    onComplete: (msgs) => {
      // 找到最终响应
      const finalMsg = msgs.find((m) => m.type === 'final');
      if (finalMsg) {
        onFinalResponse?.(finalMsg.content);
      }
    },
  });

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, chatMessages]);

  // 发送消息
  const handleSend = async () => {
    const trimmed = inputValue.trim();
    if (!trimmed || isStreaming) return;
    await sendMessage(trimmed);
    setInputValue('');
  };

  // 按键处理
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={className ? `${styles.container} ${className}` : styles.container} style={style}>
      <div className={styles.header}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <div className={`${styles.messageIcon} ${styles.iconAssistant}`} style={{ width: 24, height: 24, fontSize: 14 }}>
              <RobotOutlined />
            </div>
            <span style={{ color: 'var(--neo-text)' }}>AI 助手</span>
            {isStreaming && (
              <Badge status="processing" text={<Text type="secondary" style={{ fontSize: '12px' }}>流式传输中</Text>} />
            )}
            {sessionId && (
              <Tooltip title={`Session: ${sessionId}`}>
                <Text type="secondary" style={{ fontSize: '10px' }}>
                  #{sessionId.slice(-8)}
                </Text>
              </Tooltip>
            )}
          </Space>
          <Space>
            <Tooltip title={showSteps ? '隐藏中间步骤' : '显示中间步骤'}>
              <Button
                type="text"
                size="small"
                icon={showSteps ? <EyeOutlined /> : <EyeInvisibleOutlined />}
                onClick={() => setShowSteps(!showSteps)}
                style={{ color: 'var(--neo-text-2)' }}
              />
            </Tooltip>
            <Tooltip title="清空消息">
              <Button
                type="text"
                size="small"
                icon={<ClearOutlined />}
                onClick={clearMessages}
                style={{ color: 'var(--neo-text-2)' }}
              />
            </Tooltip>
          </Space>
        </div>
      </div>

      {/* 消息区域 */}
      <div className={styles.messageList}>
        {/* 欢迎消息 */}
        {showWelcome && messages.length === 0 && chatMessages.length === 0 && (
          <div className={`${styles.message} ${styles.messageAssistant}`}>
            <div className={`${styles.messageIcon} ${styles.iconAssistant}`}>
              <RobotOutlined />
            </div>
            <div className={styles.messageContent}>
              <div className={`${styles.messageText} ${styles.textAssistant}`}>
                <Text style={{ color: 'var(--neo-text)' }}>
                  你好！我是 AI 助手。告诉我你想做什么，我会实时展示我的思考过程和工具调用。
                </Text>
              </div>
            </div>
          </div>
        )}

        {/* 用户消息 */}
        {chatMessages
          .filter((m) => m.role === 'user')
          .map((msg) => (
            <div
              key={msg.id}
              className={`${styles.message} ${styles.messageUser}`}
            >
              <div className={`${styles.messageIcon} ${styles.iconUser}`}>
                <UserOutlined />
              </div>
              <div className={styles.messageContent}>
                <div className={`${styles.messageText} ${styles.textUser}`}>
                  {msg.content}
                </div>
              </div>
            </div>
          ))}

        {/* 流式消息（中间步骤） */}
        {messages.length > 0 && (
          <div className={`${styles.message} ${styles.messageAssistant}`}>
            <div
              className={`${styles.messageIcon} ${styles.iconAssistant}`}
              style={{ flexShrink: 0 }}
            >
              {isStreaming ? <LoadingOutlined /> : <RobotOutlined />}
            </div>
            <div className={styles.messageContent} style={{ flex: 1, maxWidth: '100%' }}>
              <StreamingMessageList
                messages={messages}
                showIntermediateSteps={showSteps}
                showDetails={true}
                compact={false}
              />
            </div>
          </div>
        )}

        {/* 错误显示 */}
        {error && (
          <div
            style={{
              backgroundColor: 'rgba(220, 38, 38, 0.1)',
              color: 'var(--color-error)',
              padding: '12px',
              borderRadius: '8px',
              marginBottom: '16px',
            }}
          >
            ❌ {error}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 */}
      <Space.Compact style={{ width: '100%' }}>
        <TextArea
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={isStreaming}
          className={styles.textArea}
        />
        {isStreaming ? (
          <Button
            danger
            onClick={cancel}
            style={{ width: '80px' }}
          >
            取消
          </Button>
        ) : (
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            disabled={!inputValue.trim()}
            className={styles.sendButton}
          >
            发送
          </Button>
        )}
      </Space.Compact>
    </div>
  );
};

export default StreamingChat;
