/**
 * ChatPage - 默认入口（/）
 *
 * Contract:
 * - 仅走 /api/conversation/stream 做自然语言澄清对话
 * - 绝不创建 workflow；创建必须显式跳转到 /workflows/new
 *
 * SOLID:
 * - SRP: 本页面只负责对话 UI 与路由跳转，不承载 workflow 创建逻辑
 */

import React, { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Input, Space, Typography } from 'antd';

import { useConversationStream } from '@/hooks/useConversationStream';

export const ChatPage: React.FC = () => {
  const navigate = useNavigate();
  const [inputValue, setInputValue] = useState('');

  const { chatMessages, isStreaming, sendMessage, clearMessages } =
    useConversationStream();

  const hasMessages = chatMessages.length > 0;

  const handleSend = useCallback(async () => {
    const trimmed = inputValue.trim();
    if (!trimmed || isStreaming) return;
    await sendMessage(trimmed);
    setInputValue('');
  }, [inputValue, isStreaming, sendMessage]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  const messageList = useMemo(() => {
    if (chatMessages.length === 0) {
      return (
        <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
          描述你的目标。我会先问 1–3 个高信号澄清问题，再协助你进入下一步。
        </Typography.Paragraph>
      );
    }

    return (
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        {chatMessages.map((msg) => (
          <div
            key={msg.id}
            style={{ width: '100%' }}
            data-testid={
              msg.role === 'assistant'
                ? 'conversation-message-assistant'
                : 'conversation-message-user'
            }
          >
            <Card
              size="small"
              style={{
                background: msg.role === 'user' ? '#f6ffed' : '#fafafa',
                borderColor: msg.role === 'user' ? '#b7eb8f' : undefined,
              }}
            >
              <Typography.Text strong>
                {msg.role === 'user' ? '你' : '助手'}
              </Typography.Text>
              <div
                style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}
                data-testid={
                  msg.role === 'assistant'
                    ? 'conversation-message-content-assistant'
                    : 'conversation-message-content-user'
                }
              >
                {msg.content}
              </div>
            </Card>
          </div>
        ))}
      </Space>
    );
  }, [chatMessages]);

  return (
    <div
      style={{
        width: '100vw',
        height: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#0a0a0a',
        color: '#fafafa',
        padding: 16,
      }}
    >
      <Card style={{ maxWidth: 920, width: '100%' }}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div>
            <Typography.Title level={3} style={{ margin: 0 }}>
              澄清对话
            </Typography.Title>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
              默认入口仅用于自然语言澄清，不会创建 workflow。需要创建时请使用显式创建入口。
            </Typography.Paragraph>
          </div>

          <Space wrap>
            <Button type="primary" onClick={() => navigate('/workflows/new')}>
              显式创建工作流
            </Button>
            <Button onClick={clearMessages} disabled={!hasMessages || isStreaming}>
              清空对话
            </Button>
          </Space>

          <div
            style={{ maxHeight: 420, overflowY: 'auto', paddingRight: 8 }}
            data-testid="conversation-message-list"
          >
            {messageList}
          </div>

          <Input.TextArea
            data-testid="conversation-textarea"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="描述你想做的事（Enter 发送，Shift+Enter 换行）"
            autoSize={{ minRows: 3, maxRows: 6 }}
            disabled={isStreaming}
          />

          <Space>
            <Button
              type="primary"
              onClick={() => void handleSend()}
              disabled={!inputValue.trim() || isStreaming}
              data-testid="conversation-send"
            >
              {isStreaming ? '处理中...' : '发送'}
            </Button>
          </Space>
        </Space>
      </Card>
    </div>
  );
};

export default ChatPage;
