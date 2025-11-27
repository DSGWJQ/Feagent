/**
 * 工作流 AI 聊天组件（带执行结果）
 *
 * 支持接收并显示执行总结信息
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { Input, Button, Card, Space, Alert, Typography, Badge } from 'antd';
import { RobotOutlined, UserOutlined, LoadingOutlined, CheckCircleOutlined, PlayCircleOutlined } from '@ant-design/icons';

import { useWorkflowAI } from '@/hooks/useWorkflowAI';
import { useWorkflowInteraction } from '@/features/workflows/contexts/WorkflowInteractionContext';
import type { ChatMessage } from '@/shared/types/chat';
import type { Workflow } from '@/types/workflow';
import type { ExecutionLogEntry } from '@/features/workflows/types/workflow';
import './FakeAIChat.css';

const { TextArea } = Input;
const { Text } = Typography;

interface WorkflowAIChatWithExecutionProps {
  workflowId: string;
  onWorkflowUpdate?: (workflow: unknown) => void;
  showWelcome?: boolean;
  onExecutionSummary?: (summary: {
    success: boolean;
    totalNodes: number;
    successNodes: number;
    errorNodes: number;
    duration?: number;
    result?: any;
  }) => void;
}

interface ExecutionSummaryMessage {
  id: string;
  type: 'execution_summary';
  timestamp: number;
  data: {
    success: boolean;
    totalNodes: number;
    successNodes: number;
    errorNodes: number;
    duration?: number;
    result?: any;
  };
}

export const WorkflowAIChatWithExecution: React.FC<WorkflowAIChatWithExecutionProps> = ({
  workflowId,
  onWorkflowUpdate,
  showWelcome = true,
  onExecutionSummary,
}) => {
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [executionSummary, setExecutionSummary] = useState<ExecutionSummaryMessage | null>(null);
  const { interactionMode, setInteractionMode, isCanvasMode } = useWorkflowInteraction();

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

  // 当输入框聚焦时，切换到聊天模式
  const handleInputFocus = () => {
    if (interactionMode !== 'chat') {
      setInteractionMode('chat');
    }
  };

  /**
   * 添加执行总结消息
   */
  const addExecutionSummary = (summary: {
    success: boolean;
    totalNodes: number;
    successNodes: number;
    errorNodes: number;
    duration?: number;
    result?: any;
  }) => {
    const summaryMessage: ExecutionSummaryMessage = {
      id: `exec_summary_${Date.now()}`,
      type: 'execution_summary',
      timestamp: Date.now(),
      data: summary,
    };

    setExecutionSummary(summaryMessage);

    // 调用外部回调
    if (onExecutionSummary) {
      onExecutionSummary(summary);
    }
  };

  // 暴露添加执行总结的方法
  useEffect(() => {
    // 将方法挂载到全局，供父组件调用
    (window as any).addExecutionSummary = addExecutionSummary;

    return () => {
      delete (window as any).addExecutionSummary;
    };
  }, [onExecutionSummary]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, errorMessage, pendingWorkflow, executionSummary]);

  const welcomeMessage = useMemo<ChatMessage | null>(() => {
    if (!showWelcome) return null;
    return {
      id: 'welcome',
      role: 'assistant',
      content:
        '你好！我是工作流AI助手。告诉我你想如何修改工作流，比如"在HTTP节点前增加条件判断"或"删除所有数据库节点"。',
      timestamp: Date.now(),
    };
  }, [showWelcome]);

  const displayedMessages = useMemo(() => {
    const list: ChatMessage[] = [];
    if (welcomeMessage) {
      list.push(welcomeMessage);
    }
    list.push(...messages);

    // 添加执行总结
    if (executionSummary) {
      const { data } = executionSummary;
      const successText = data.success ? '执行成功' : '执行失败';
      const icon = data.success ? '✅' : '❌';

      list.push({
        id: executionSummary.id,
        role: 'assistant',
        content: `${icon} ${successText}\n\n` +
          `📊 执行统计：\n` +
          `• 总节点数：${data.totalNodes}\n` +
          `• 成功节点：${data.successNodes}\n` +
          `• 失败节点：${data.errorNodes}\n` +
          (data.duration ? `• 执行时长：${(data.duration / 1000).toFixed(2)}秒\n` : '') +
          (data.result ? `\n📋 执行结果：\n${JSON.stringify(data.result, null, 2)}` : ''),
        timestamp: executionSummary.timestamp,
      });
    }

    if (errorMessage) {
      list.push({
        id: `error_${Date.now()}`,
        role: 'assistant',
        content: errorMessage,
        timestamp: Date.now(),
      });
    }
    return list;
  }, [messages, welcomeMessage, errorMessage, executionSummary]);

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
            icon={<PlayCircleOutlined />}
            onClick={() => setInteractionMode('chat')}
            style={{ color: '#8c8c8c' }}
            title="切换到聊天模式"
          >
            对话
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
      headStyle={{
        backgroundColor: '#1a1a1a',
        borderBottom: '1px solid #262626',
        color: '#fafafa',
      }}
      bodyStyle={{
        flex: 1,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#141414',
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
        {displayedMessages.map((msg) => {
          // 处理执行总结消息的特殊样式
          const isExecutionSummary = 'type' in msg && msg.type === 'execution_summary';

          return (
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
                    backgroundColor: msg.role === 'user' ? '#1a1a1a' : isExecutionSummary ? '#1e3a8a' : '#262626',
                    color: '#fafafa',
                    padding: '12px',
                    borderRadius: '8px',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    border: isExecutionSummary ? '1px solid #3b82f6' : 'none',
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
          );
        })}

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

export default WorkflowAIChatWithExecution;
