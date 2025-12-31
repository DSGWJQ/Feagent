import { useEffect, useMemo, useRef, useState } from 'react';
import { Input, Button, Card, Space, Alert, Typography, Badge } from 'antd';
import { RobotOutlined, UserOutlined, LoadingOutlined, CheckCircleOutlined, EditOutlined } from '@ant-design/icons';

import { useWorkflowAI } from '@/hooks/useWorkflowAI';
import { useWorkflowInteraction } from '@/features/workflows/contexts/WorkflowInteractionContext';
import type { ChatMessage } from '@/shared/types/chat';
import type { Workflow } from '@/features/workflows/types/workflow';
import styles from './AIChat.module.css';

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
      className={styles.container}
      classNames={{
        header: styles.header,
        body: styles.body,
      }}
      title={
        <Space>
          <div className={`${styles.messageIcon} ${styles.iconAssistant}`} style={{ width: 24, height: 24, fontSize: 14 }}>
            <RobotOutlined />
          </div>
          <span style={{ color: 'var(--neo-text)' }}>AI助手</span>
          {interactionMode !== 'idle' && (
            <Badge
              status={interactionMode === 'chat' ? 'processing' : 'default'}
              text={
                <span style={{ color: interactionMode === 'chat' ? 'var(--neo-blue)' : 'var(--neo-text-2)', fontSize: '12px' }}>
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
            style={{ color: 'var(--neo-text-2)' }}
            title="切换到聊天模式"
          >
            编辑
          </Button>
        )
      }
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

      <div className={styles.messageList}>
        {displayedMessages.map((msg) => (
          <div
            key={msg.id}
            className={`${styles.message} ${msg.role === 'user' ? styles.messageUser : ''}`}
          >
            <div className={`${styles.messageIcon} ${msg.role === 'user' ? styles.iconUser : styles.iconAssistant}`}>
              {msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
            </div>
            <div className={styles.messageContent}>
              <div className={`${styles.messageText} ${msg.role === 'user' ? styles.textUser : styles.textAssistant}`}>
                {msg.content}
              </div>
              <div className={styles.messageTime}>
                {new Date(msg.timestamp).toLocaleTimeString('zh-CN')}
              </div>
            </div>
          </div>
        ))}

        {isProcessing && (
          <div className={styles.message}>
            <div className={`${styles.messageIcon} ${styles.iconAssistant}`}>
              <LoadingOutlined />
            </div>
            <div className={styles.messageContent}>
              <div className={`${styles.messageText} ${styles.textAssistant}`}>
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
          className={styles.textArea}
        />
        <Button
          type="primary"
          onClick={handleSend}
          disabled={isProcessing || !inputValue.trim()}
          className={styles.sendButton}
        >
          发送
        </Button>
      </Space.Compact>
    </Card>
  );
};
