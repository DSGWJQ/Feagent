/**
 * 增强版工作流AI聊天组件（带RAG功能）
 *
 * 支持RAG知识库检索、文档上传和上下文管理
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Input,
  Button,
  Card,
  Space,
  Alert,
  Typography,
  Tag,
  Switch,
  Tabs,
  message
} from 'antd';
import {
  RobotOutlined,
  UserOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  PlayCircleOutlined,
  BookOutlined,
  FileTextOutlined,
  SearchOutlined,
  AppstoreOutlined,
} from '@ant-design/icons';
import type { TabsProps } from 'antd';

import { useWorkflowAI } from '@/hooks/useWorkflowAI';
import { useWorkflowInteraction } from '@/features/workflows/contexts/WorkflowInteractionContext';
import type { ChatMessage } from '@/shared/types/chat';
import type { Workflow } from '@/types/workflow';
import type { ExecutionLogEntry } from '@/features/workflows/types/workflow';
import { RAGContextPanel, DocumentUploadPanel } from '@/features/rag/components';
import './FakeAIChat.css';

const { TextArea } = Input;
const { Text } = Typography;

interface WorkflowAIChatWithRAGProps {
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

export const WorkflowAIChatWithRAG: React.FC<WorkflowAIChatWithRAGProps> = ({
  workflowId,
  onWorkflowUpdate,
  showWelcome = true,
  onExecutionSummary,
}) => {
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [executionSummary, setExecutionSummary] = useState<ExecutionSummaryMessage | null>(null);
  const [ragEnabled, setRagEnabled] = useState(false);
  const [ragContext, setRagContext] = useState<string>('');
  const [ragSources, setRagSources] = useState<any[]>([]);
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

    if (onExecutionSummary) {
      onExecutionSummary(summary);
    }
  };

  // 暴露添加执行总结的方法
  useEffect(() => {
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

    let welcomeText = '你好！我是工作流AI助手。告诉我你想如何修改工作流，比如"在HTTP节点前增加条件判断"或"删除所有数据库节点"。';

    if (ragEnabled) {
      welcomeText += '\n\n🔍 当前已启用知识库检索功能，我可以基于上传的文档回答问题。';
    }

    return {
      id: 'welcome',
      role: 'assistant',
      content: welcomeText,
      timestamp: Date.now(),
    };
  }, [showWelcome, ragEnabled]);

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

    // 添加RAG上下文信息
    if (ragContext && ragEnabled) {
      list.push({
        id: `rag_context_${Date.now()}`,
        role: 'assistant',
        content: `📚 已检索到相关知识库上下文 (${ragSources.length} 个来源):\n\n${ragContext}`,
        timestamp: Date.now(),
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
  }, [messages, welcomeMessage, errorMessage, executionSummary, ragContext, ragEnabled, ragSources]);

  const handleSend = async () => {
    const trimmed = inputValue.trim();
    if (!trimmed) return;

    // 如果启用RAG，先检索上下文
    let finalMessage = trimmed;

    if (ragEnabled && ragContext) {
      finalMessage = `基于以下知识库上下文回答用户问题：\n\n知识库上下文：\n${ragContext}\n\n用户问题：${trimmed}`;
    }

    await startChatStream(finalMessage);
    setInputValue('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleRAGContextUpdate = (context: string, sources: any[]) => {
    setRagContext(context);
    setRagSources(sources);
  };

  // Tab面板配置
  const tabItems: TabsProps['items'] = [
    {
      key: 'chat',
      label: (
        <span>
          <RobotOutlined />
          AI对话
        </span>
      ),
      children: (
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
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
              const isExecutionSummary = 'type' in msg && msg.type === 'execution_summary';
              const isRAGContext = msg.content.includes('知识库上下文');

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
                        backgroundColor: msg.role === 'user' ? '#1a1a1a' :
                                       isExecutionSummary ? '#1e3a8a' :
                                       isRAGContext ? '#1e3a8a' : '#262626',
                        color: '#fafafa',
                        padding: '12px',
                        borderRadius: '8px',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        border: (isExecutionSummary || isRAGContext) ? '1px solid #3b82f6' : 'none',
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
              placeholder={
                ragEnabled
                  ? (isCanvasMode ? "输入消息... (点击后将切换到聊天模式，已启用知识库检索)" : "输入消息... (Enter发送, Shift+Enter换行, 已启用知识库检索)")
                  : (isCanvasMode ? "输入消息... (点击后将切换到聊天模式)" : "输入消息... (Enter发送, Shift+Enter换行)")
              }
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
        </div>
      ),
    },
    {
      key: 'context',
      label: (
        <span>
          <SearchOutlined />
          上下文
        </span>
      ),
      children: (
        <RAGContextPanel
          workflowId={workflowId}
          onContextUpdate={handleRAGContextUpdate}
          visible={ragEnabled}
        />
      ),
    },
    {
      key: 'documents',
      label: (
        <span>
          <FileTextOutlined />
          文档
        </span>
      ),
      children: (
        <DocumentUploadPanel
          workflowId={workflowId}
          visible={ragEnabled}
        />
      ),
    },
  ];

  return (
    <Card
      className="fake-ai-chat"
      title={
        <Space size={6} wrap>
          <RobotOutlined style={{ color: '#8b5cf6' }} />
          <span style={{ color: '#fafafa' }}>AI助手</span>
          {ragEnabled && (
            <Tag color="purple" bordered={false} style={{ marginInlineEnd: 0 }}>
              知识库
            </Tag>
          )}
          {interactionMode !== 'idle' && (
            <Tag
              color={interactionMode === 'chat' ? 'magenta' : 'blue'}
              bordered={false}
              style={{ marginInlineEnd: 0 }}
            >
              {interactionMode === 'chat' ? '聊天模式' : '画布模式'}
            </Tag>
          )}
        </Space>
      }
      extra={
        <Space size={4} wrap align="center">
          <span style={{ color: '#8c8c8c', fontSize: '12px' }}>知识库</span>
          <Switch
            size="small"
            checked={ragEnabled}
            onChange={setRagEnabled}
            checkedChildren={<BookOutlined />}
            unCheckedChildren={<BookOutlined />}
          />
          {isCanvasMode && (
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
          )}
          {!isCanvasMode && (
            <Button
              type="text"
              size="small"
              icon={<AppstoreOutlined />}
              onClick={() => setInteractionMode('canvas')}
              style={{ color: '#8c8c8c' }}
              title={isProcessing ? 'AI 正在处理，请稍后' : '恢复画布编辑'}
              disabled={isProcessing}
            >
              画布
            </Button>
          )}
        </Space>
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
          padding: 0,
        },
      }}
    >
      <Tabs
        defaultActiveKey="chat"
        items={tabItems}
        style={{
          flex: 1,
          height: '100%',
          backgroundColor: '#141414',
        }}
        tabBarStyle={{
          backgroundColor: '#1a1a1a',
          borderBottom: '1px solid #262626',
          padding: '0 16px',
          margin: 0,
        }}
      />
    </Card>
  );
};

export default WorkflowAIChatWithRAG;
