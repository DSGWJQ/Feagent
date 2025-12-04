/**
 * Phase 4: 集成流式消息的聊天组件
 *
 * 实时展示不同类型消息：thought/tool_call/tool_result/final
 */

import React, { useEffect, useRef, useState } from 'react';
import { Input, Button, Card, Space, Typography, Switch, Badge, Tooltip } from 'antd';
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
import type { StreamingMessage, ChatMessageWithStreaming } from '@/shared/types/streaming';

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
    <Card
      title={
        <Space>
          <RobotOutlined style={{ color: '#8b5cf6' }} />
          <span style={{ color: '#fafafa' }}>AI 助手</span>
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
      }
      extra={
        <Space>
          <Tooltip title={showSteps ? '隐藏中间步骤' : '显示中间步骤'}>
            <Button
              type="text"
              size="small"
              icon={showSteps ? <EyeOutlined /> : <EyeInvisibleOutlined />}
              onClick={() => setShowSteps(!showSteps)}
              style={{ color: '#8c8c8c' }}
            />
          </Tooltip>
          <Tooltip title="清空消息">
            <Button
              type="text"
              size="small"
              icon={<ClearOutlined />}
              onClick={clearMessages}
              style={{ color: '#8c8c8c' }}
            />
          </Tooltip>
        </Space>
      }
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#141414',
        borderColor: '#262626',
        ...style,
      }}
      styles={{
        header: {
          backgroundColor: '#1a1a1a',
          borderBottom: '1px solid #262626',
          color: '#fafafa',
        },
        body: {
          flex: 1,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: '#141414',
          padding: '12px',
        },
      }}
    >
      {/* 消息区域 */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          marginBottom: 16,
          padding: '8px',
        }}
      >
        {/* 欢迎消息 */}
        {showWelcome && messages.length === 0 && chatMessages.length === 0 && (
          <div
            style={{
              display: 'flex',
              gap: '12px',
              marginBottom: '16px',
            }}
          >
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: '#8b5cf6',
                color: '#fff',
              }}
            >
              <RobotOutlined />
            </div>
            <div
              style={{
                backgroundColor: '#262626',
                color: '#fafafa',
                padding: '12px',
                borderRadius: '8px',
                flex: 1,
              }}
            >
              <Text style={{ color: '#d1d5db' }}>
                你好！我是 AI 助手。告诉我你想做什么，我会实时展示我的思考过程和工具调用。
              </Text>
            </div>
          </div>
        )}

        {/* 用户消息 */}
        {chatMessages
          .filter((m) => m.role === 'user')
          .map((msg) => (
            <div
              key={msg.id}
              style={{
                display: 'flex',
                gap: '12px',
                marginBottom: '16px',
                justifyContent: 'flex-end',
              }}
            >
              <div
                style={{
                  backgroundColor: '#3b82f6',
                  color: '#fff',
                  padding: '12px',
                  borderRadius: '8px',
                  maxWidth: '70%',
                }}
              >
                {msg.content}
              </div>
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  backgroundColor: '#3b82f6',
                  color: '#fff',
                }}
              >
                <UserOutlined />
              </div>
            </div>
          ))}

        {/* 流式消息（中间步骤） */}
        {messages.length > 0 && (
          <div
            style={{
              display: 'flex',
              gap: '12px',
              marginBottom: '16px',
            }}
          >
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: '#8b5cf6',
                color: '#fff',
                flexShrink: 0,
              }}
            >
              {isStreaming ? <LoadingOutlined /> : <RobotOutlined />}
            </div>
            <div style={{ flex: 1 }}>
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
              backgroundColor: '#2e1a1a',
              color: '#f87171',
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
          style={{
            backgroundColor: '#1a1a1a',
            borderColor: '#434343',
            color: '#fafafa',
          }}
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
            style={{
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              borderColor: 'transparent',
            }}
          >
            发送
          </Button>
        )}
      </Space.Compact>
    </Card>
  );
};

export default StreamingChat;
