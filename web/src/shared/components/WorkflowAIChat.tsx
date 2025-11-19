/**
 * WorkflowAIChat - 工作流AI聊天组件
 *
 * 功能：
 * - 调用后端API进行工作流修改
 * - 实时更新工作流画布
 * - 显示AI回复和修改说明
 */

import { useState, useRef, useEffect } from 'react';
import { Input, Button, Card, Space, message as antMessage } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, LoadingOutlined } from '@ant-design/icons';
import type { ChatMessage } from '@/shared/types/chat';
import './FakeAIChat.css'; // 复用样式

const { TextArea } = Input;

interface WorkflowAIChatProps {
  workflowId: string;
  onWorkflowUpdate?: (workflow: any) => void;
  showWelcome?: boolean;
  apiBaseUrl?: string;
}

/**
 * WorkflowAIChat 组件
 */
export const WorkflowAIChat: React.FC<WorkflowAIChatProps> = ({
  workflowId,
  onWorkflowUpdate,
  showWelcome = true,
  apiBaseUrl = 'http://localhost:8000',
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 初始化欢迎消息
  useEffect(() => {
    if (showWelcome) {
      setMessages([
        {
          id: 'welcome',
          role: 'assistant',
          content: '你好！我是工作流AI助手。你可以告诉我如何修改工作流，例如：\n\n• "在HTTP节点之前添加一个条件判断"\n• "删除所有数据库节点"\n• "在开始和结束之间添加一个LLM节点"',
          timestamp: new Date(),
        },
      ]);
    }
  }, [showWelcome]);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  /**
   * 调用后端API修改工作流
   */
  const callWorkflowChatAPI = async (userMessage: string): Promise<{ workflow: any; ai_message: string }> => {
    const response = await fetch(`${apiBaseUrl}/api/workflows/${workflowId}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message: userMessage }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '请求失败');
    }

    return response.json();
  };

  /**
   * 发送消息
   */
  const handleSend = async () => {
    const trimmedInput = inputValue.trim();
    if (!trimmedInput || isLoading) {
      return;
    }

    // 添加用户消息
    const userMessage: ChatMessage = {
      id: `user_${Date.now()}`,
      role: 'user',
      content: trimmedInput,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      // 调用后端API
      const { workflow, ai_message } = await callWorkflowChatAPI(trimmedInput);

      // 添加AI回复
      const aiMessage: ChatMessage = {
        id: `ai_${Date.now()}`,
        role: 'assistant',
        content: ai_message,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, aiMessage]);

      // 通知父组件更新工作流
      if (onWorkflowUpdate) {
        onWorkflowUpdate(workflow);
      }

      antMessage.success('工作流已更新');
    } catch (error) {
      console.error('发送消息失败:', error);

      // 添加错误消息
      const errorMessage: ChatMessage = {
        id: `error_${Date.now()}`,
        role: 'assistant',
        content: `抱歉，处理您的请求时出错了：${error instanceof Error ? error.message : '未知错误'}`,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, errorMessage]);
      antMessage.error('处理失败，请重试');
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * 处理键盘事件
   */
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
          <RobotOutlined />
          <span>AI助手</span>
        </Space>
      }
      style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
      bodyStyle={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}
    >
      {/* 消息列表 */}
      <div className="fake-ai-chat__messages" style={{ flex: 1, overflowY: 'auto', marginBottom: 16 }}>
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`fake-ai-chat__message fake-ai-chat__message--${msg.role}`}
          >
            <div className="fake-ai-chat__message-icon">
              {msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
            </div>
            <div className="fake-ai-chat__message-content">
              <div className="fake-ai-chat__message-text">{msg.content}</div>
              <div className="fake-ai-chat__message-time">
                {msg.timestamp.toLocaleTimeString('zh-CN')}
              </div>
            </div>
          </div>
        ))}

        {/* 加载状态 */}
        {isLoading && (
          <div className="fake-ai-chat__message fake-ai-chat__message--assistant">
            <div className="fake-ai-chat__message-icon">
              <LoadingOutlined />
            </div>
            <div className="fake-ai-chat__message-content">
              <div className="fake-ai-chat__message-text">AI正在思考中...</div>
            </div>
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
          placeholder="输入消息... (Enter发送, Shift+Enter换行)"
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={isLoading}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          disabled={isLoading || !inputValue.trim()}
        >
          发送
        </Button>
      </Space.Compact>
    </Card>
  );
};

