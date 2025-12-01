import { useEffect, useMemo, useRef, useState } from 'react';
import { Input, Button, Card, Space, Alert, Typography, Badge } from 'antd';
import { RobotOutlined, UserOutlined, LoadingOutlined, CheckCircleOutlined, EditOutlined } from '@ant-design/icons';

import { useWorkflowAI } from '@/hooks/useWorkflowAI';
import { useWorkflowInteraction } from '@/features/workflows/contexts/WorkflowInteractionContext';
import type { ChatMessage } from '@/shared/types/chat';
import type { Workflow } from '@/types/workflow';
import './FakeAIChat.css';

const { TextArea } = Input;
const { Text } = Typography;

interface WorkflowAIChatProps {
  workflowId: string;
  onWorkflowUpdate?: (workflow: unknown) => void;
  showWelcome?: boolean;
}

export const WorkflowAIChat: React.FC<WorkflowAIChatProps> = ({
  workflowId,
  onWorkflowUpdate,
  showWelcome = true,
}) => {
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { interactionMode, setInteractionMode, isCanvasMode } = useWorkflowInteraction();
  const wasProcessingRef = useRef(false);

  const {
    messages,
    isProcessing,
    pendingWorkflow,
    streamingMessage,
    sendMessage,
    confirmPendingWorkflow,
    startChatStream,
    errorMessage,
  } = useWorkflowAI({
    workflowId,
    onApplyWorkflow: onWorkflowUpdate,
    onPreviewWorkflow: (workflow: Workflow, message: string) => {
      console.log('Preview workflow:', workflow);
      console.log('Message:', message);
    }
  });

  // 当开始处理时，切换到聊天模式
  useEffect(() => {
    if (isProcessing && interactionMode !== 'chat') {
      setInteractionMode('chat');
    }
  }, [isProcessing, interactionMode, setInteractionMode]);

  useEffect(() => {
    if (wasProcessingRef.current && !isProcessing && interactionMode === 'chat') {
      setInteractionMode('canvas');
    }
    wasProcessingRef.current = isProcessing;
  }, [isProcessing, interactionMode, setInteractionMode]);

  // 当输入框聚焦时，切换到聊天模式
  const handleInputFocus = () => {
    if (interactionMode !== 'chat') {
      setInteractionMode('chat');
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, errorMessage, pendingWorkflow]);

  const welcomeMessage = useMemo<ChatMessage | null>(() => {
    if (!showWelcome) return null;
    return {
      id: 'welcome',
      role: 'assistant',
      content:
        '你好！我是工作流AI助手。告诉我你想如何修改工作流，比如“在HTTP节点前增加条件判断”或“删除所有数据库节点”。',
      timestamp: Date.now(),
    };
  }, [showWelcome]);

  const displayedMessages = useMemo(() => {
    const list: ChatMessage[] = [];
    if (welcomeMessage) {
      list.push(welcomeMessage);
    }
    list.push(...messages);
    if (errorMessage) {
      list.push({
        id: `error_${Date.now()}`,
        role: 'assistant',
        content: errorMessage,
        timestamp: Date.now(),
      });
    }
    return list;
  }, [messages, welcomeMessage, errorMessage]);

  const handleSend = async () => {
    const trimmed = inputValue.trim();
    if (!trimmed) return;
    await startChatStream(trimmed);
    setInputValue('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <Card
      className="fake-ai-chat"
      title={
        <Space>
          <RobotOutlined style={{ color: '#8b5cf6' }} />
          <span style={{ color: '#fafafa' }}>AI助手</span>
          {interactionMode !== 'idle' && (
            <Badge
              status={interactionMode === 'chat' ? 'processing' : 'default'}
              text={
                <span style={{ color: interactionMode === 'chat' ? '#8b5cf6' : '#8c8c8c', fontSize: '12px' }}>
                  {interactionMode === 'chat' ? '聊天模式' : '画布模式'}
                </span>
              }
            />
          )}
        </Space>
      }
      extra={
        isCanvasMode && (
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => setInteractionMode('chat')}
            style={{ color: '#8c8c8c' }}
            title="切换到聊天模式"
          >
            编辑
          </Button>
        )
      }
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#141414',
        borderColor: '#262626',
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
        },
      }}
    >
      {pendingWorkflow && (
        <Alert
          style={{ marginBottom: 12 }}
          type="info"
          message="AI 已生成新的工作流"
          description={
            <Space direction="vertical">
              <Text type="secondary">
                节点数：{pendingWorkflow?.nodes?.length ?? 0} · 边数：{pendingWorkflow?.edges?.length ?? 0}
              </Text>
              <Button
                size="small"
                type="primary"
                icon={<CheckCircleOutlined />}
                onClick={confirmPendingWorkflow}
              >
                同步到画布
              </Button>
            </Space>
          }
          showIcon
        />
      )}

      <div
        className="fake-ai-chat__messages"
        style={{ flex: 1, overflowY: 'auto', marginBottom: 16, padding: '16px' }}
      >
        {displayedMessages.map((msg) => (
          <div
            key={msg.id}
            className={`fake-ai-chat__message fake-ai-chat__message--${msg.role}`}
            style={{ display: 'flex', gap: '12px', marginBottom: '16px' }}
          >
            <div
              className="fake-ai-chat__message-icon"
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: msg.role === 'user' ? '#3b82f6' : '#8b5cf6',
                color: '#fff',
              }}
            >
              {msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
            </div>
            <div className="fake-ai-chat__message-content" style={{ flex: 1 }}>
              <div
                className="fake-ai-chat__message-text"
                style={{
                  backgroundColor: msg.role === 'user' ? '#1a1a1a' : '#262626',
                  color: '#fafafa',
                  padding: '12px',
                  borderRadius: '8px',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {msg.content}
              </div>
              <div
                className="fake-ai-chat__message-time"
                style={{ fontSize: '12px', color: '#8c8c8c', marginTop: '4px' }}
              >
                {new Date(msg.timestamp).toLocaleTimeString('zh-CN')}
              </div>
            </div>
          </div>
        ))}

        {isProcessing && (
          <div
            className="fake-ai-chat__message fake-ai-chat__message--assistant"
            style={{ display: 'flex', gap: '12px', marginBottom: '16px' }}
          >
            <div
              className="fake-ai-chat__message-icon"
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
              <LoadingOutlined />
            </div>
            <div className="fake-ai-chat__message-content">
              <div
                className="fake-ai-chat__message-text"
                style={{ backgroundColor: '#262626', color: '#fafafa', padding: '12px', borderRadius: '8px' }}
              >
                {streamingMessage || 'AI正在思考中...'}
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <Space.Compact style={{ width: '100%' }}>
        <TextArea
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={handleInputFocus}
          placeholder={isCanvasMode ? "输入消息... (点击后将切换到聊天模式)" : "输入消息... (Enter发送, Shift+Enter换行)"}
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={isProcessing}
          style={{ backgroundColor: '#1a1a1a', borderColor: '#434343', color: '#fafafa' }}
        />
        <Button
          type="primary"
          onClick={handleSend}
          disabled={isProcessing || !inputValue.trim()}
          style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', borderColor: 'transparent' }}
        >
          发送
        </Button>
      </Space.Compact>
    </Card>
  );
};
