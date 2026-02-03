/**
 * 工作流 AI 聊天组件（带执行结果）
 *
 * 支持接收并显示执行总结信息
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Input, Button, Card, Space, Alert, Typography, Badge } from 'antd';
import { RobotOutlined, UserOutlined, LoadingOutlined, CheckCircleOutlined, PlayCircleOutlined } from '@ant-design/icons';

import { useWorkflowAI } from '@/hooks/useWorkflowAI';
import { useWorkflowInteraction } from '@/features/workflows/contexts/WorkflowInteractionContext';
import type { ChatMessage } from '@/shared/types/chat';
import type { Workflow } from '@/features/workflows/types/workflow';
import WorkflowDiffSummaryView from '@/features/workflows/components/WorkflowDiffSummary';
import { diffWorkflowGraphs } from '@/features/workflows/utils/workflowDiff';
import styles from './AIChat.module.css';

const { TextArea } = Input;
const { Text } = Typography;

interface WorkflowAIChatWithExecutionProps {
  workflowId: string;
  onWorkflowUpdate?: (workflow: Workflow) => void;
  showWelcome?: boolean;
  diffBaselineWorkflow?: Workflow | null;
  onExecutionSummary?: (summary: {
    success: boolean;
    totalNodes: number;
    successNodes: number;
    errorNodes: number;
    duration?: number;
    result?: unknown;
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
    result?: unknown;
  };
}

type ExecutionSummaryPayload = ExecutionSummaryMessage['data'];

type ExtendedChatMessage = ChatMessage & {
  type?: 'execution_summary';
};

declare global {
  interface Window {
    addExecutionSummary?: (summary: ExecutionSummaryPayload) => void;
  }
}

export const WorkflowAIChatWithExecution: React.FC<WorkflowAIChatWithExecutionProps> = ({
  workflowId,
  onWorkflowUpdate,
  showWelcome = true,
  diffBaselineWorkflow = null,
  onExecutionSummary,
}) => {
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [executionSummary, setExecutionSummary] = useState<ExecutionSummaryMessage | null>(null);
  const { interactionMode, setInteractionMode, isCanvasMode } = useWorkflowInteraction();
  const wasProcessingRef = useRef(false);

  const {
    messages,
    isProcessing,
    pendingWorkflow,
    streamingMessage,
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

  /**
   * 添加执行总结消息
   */
  const addExecutionSummary = useCallback((summary: ExecutionSummaryPayload) => {
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
  }, [onExecutionSummary]);

  // 暴露添加执行总结的方法
  useEffect(() => {
    // 将方法挂载到全局，供父组件调用
    window.addExecutionSummary = addExecutionSummary;

    return () => {
      delete window.addExecutionSummary;
    };
  }, [addExecutionSummary]);

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
    const list: ExtendedChatMessage[] = [];
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
        type: 'execution_summary',
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

  const diffSummary = useMemo(() => {
    if (!pendingWorkflow || !diffBaselineWorkflow) return null;
    return diffWorkflowGraphs(
      {
        nodes: diffBaselineWorkflow.nodes ?? [],
        edges: diffBaselineWorkflow.edges ?? [],
      },
      {
        nodes: pendingWorkflow.nodes ?? [],
        edges: pendingWorkflow.edges ?? [],
      }
    );
  }, [pendingWorkflow, diffBaselineWorkflow]);

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
            icon={<PlayCircleOutlined />}
            onClick={() => setInteractionMode('chat')}
            style={{ color: 'var(--neo-text-2)' }}
            title="切换到聊天模式"
          >
            对话
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
              {diffSummary ? (
                <WorkflowDiffSummaryView summary={diffSummary} />
              ) : (
                <Text type="secondary">
                  节点数：{pendingWorkflow?.nodes?.length ?? 0} · 边数：{pendingWorkflow?.edges?.length ?? 0}
                </Text>
              )}
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
        {displayedMessages.map((msg) => {
          // 处理执行总结消息的特殊样式
          const isExecutionSummary = 'type' in msg && msg.type === 'execution_summary';
          const isUser = msg.role === 'user';
          const isSystem = msg.role === 'system';
          const iconClassName = isUser
            ? styles.iconUser
            : isSystem
              ? styles.iconSystem
              : styles.iconAssistant;
          const textClassName = isUser
            ? styles.textUser
            : isExecutionSummary
              ? styles.textExecutionSummary
              : isSystem
                ? styles.textSystem
                : styles.textAssistant;

          return (
            <div
              key={msg.id}
              className={`${styles.message} ${msg.role === 'user' ? styles.messageUser : ''}`}
            >
              <div className={`${styles.messageIcon} ${iconClassName}`}>
                {msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
              </div>
              <div className={styles.messageContent}>
                <div className={`${styles.messageText} ${textClassName}`}>{msg.content}</div>
                <div className={styles.messageTime}>
                  {new Date(msg.timestamp).toLocaleTimeString('zh-CN')}
                </div>
              </div>
            </div>
          );
        })}

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

export default WorkflowAIChatWithExecution;
