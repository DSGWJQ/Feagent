/**
 * FakeAIChat - 假AI聊天框组件
 *
 * 功能：
 * - 纯前端实现，不调用后端API
 * - 使用固定规则模拟AI回复
 * - 支持自定义回复规则
 * - 支持消息历史记录
 */

import { useState, useRef, useEffect } from 'react';
import { Input, Button, Card, Space } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined } from '@ant-design/icons';
import type { ChatMessage, AIReplyRule } from '@/shared/types/chat';
import './FakeAIChat.css';

const { TextArea } = Input;

/**
 * 默认AI回复规则
 */
const DEFAULT_RULES: AIReplyRule[] = [
  // 问候语
  {
    pattern: /^(你好|hi|hello|嗨)/i,
    reply: '你好！我是AI助手，有什么可以帮助你的吗？',
    priority: 10,
  },
  // 自我介绍
  {
    pattern: /你是谁|你叫什么/i,
    reply: '我是一个AI助手，可以帮你解答问题和完成任务。',
    priority: 10,
  },
  // 能力询问
  {
    pattern: /你能做什么|你会什么|你的功能/i,
    reply: '我可以回答问题、提供建议、帮助你完成各种任务。试着问我一些问题吧！',
    priority: 10,
  },
  // 天气相关
  {
    pattern: /天气/i,
    reply: '抱歉，我目前无法查询实时天气信息。你可以使用天气应用或网站查看。',
    priority: 8,
  },
  // 时间相关
  {
    pattern: /几点|时间/i,
    reply: () => `现在是 ${new Date().toLocaleTimeString('zh-CN')}`,
    priority: 8,
  },
  // 日期相关
  {
    pattern: /日期|今天|几号/i,
    reply: () => `今天是 ${new Date().toLocaleDateString('zh-CN')}`,
    priority: 8,
  },
  // 感谢
  {
    pattern: /谢谢|感谢/i,
    reply: '不客气！很高兴能帮到你。还有其他问题吗？',
    priority: 9,
  },
  // 再见
  {
    pattern: /再见|拜拜|bye/i,
    reply: '再见！祝你有美好的一天！',
    priority: 9,
  },
  // 帮助
  {
    pattern: /帮助|help/i,
    reply: '你可以问我任何问题，我会尽力回答。比如：\n- 你好\n- 你能做什么\n- 现在几点了',
    priority: 9,
  },
  // 默认回复（最低优先级）
  {
    pattern: /.*/,
    reply: '我理解你的意思了。不过我目前只是一个简单的演示版本，功能有限。你可以试试问我其他问题！',
    priority: 1,
  },
];

export interface FakeAIChatProps {
  /** 是否显示欢迎消息 */
  showWelcome?: boolean;
  /** 自定义欢迎消息内容 */
  welcomeMessage?: string;
  /** 自定义AI回复规则 */
  customRules?: AIReplyRule[];
  /** 消息发送回调 */
  onMessageSent?: (message: ChatMessage) => void;
  /** AI回复回调 */
  onAIReply?: (message: ChatMessage) => void;
  /** 自定义样式类名 */
  className?: string;
  /** 自定义高度 */
  height?: number | string;
}

export function FakeAIChat({
  showWelcome = false,
  welcomeMessage = '你好！我是AI助手，有什么可以帮助你的吗？',
  customRules = [],
  onMessageSent,
  onAIReply,
  className = '',
  height = 600,
}: FakeAIChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 合并自定义规则和默认规则，按优先级排序
  const rules = [...customRules, ...DEFAULT_RULES].sort(
    (a, b) => (b.priority || 0) - (a.priority || 0)
  );

  // 初始化欢迎消息
  useEffect(() => {
    if (showWelcome && messages.length === 0) {
      const welcomeMsg: ChatMessage = {
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: welcomeMessage,
        timestamp: Date.now(),
      };
      setMessages([welcomeMsg]);
    }
  }, [showWelcome, welcomeMessage, messages.length]);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  /**
   * 根据规则生成AI回复
   */
  const generateAIReply = (userMessage: string): string => {
    for (const rule of rules) {
      const pattern = typeof rule.pattern === 'string' ? new RegExp(rule.pattern) : rule.pattern;
      const match = userMessage.match(pattern);

      if (match) {
        if (typeof rule.reply === 'function') {
          return rule.reply(match, userMessage);
        }
        return rule.reply;
      }
    }

    // 如果没有匹配的规则，返回默认回复
    return '我不太明白你的意思，能换个方式问吗？';
  };

  /**
   * 发送消息
   */
  const handleSend = async () => {
    const trimmedInput = input.trim();
    if (!trimmedInput) return;

    // 创建用户消息
    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: trimmedInput,
      timestamp: Date.now(),
    };

    // 添加用户消息
    setMessages((prev) => [...prev, userMessage]);
    setInput('');

    // 触发回调
    onMessageSent?.(userMessage);

    // 模拟AI思考延迟
    setIsTyping(true);
    await new Promise((resolve) => setTimeout(resolve, 500 + Math.random() * 1000));

    // 生成AI回复
    const aiReplyContent = generateAIReply(trimmedInput);
    const aiMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: 'assistant',
      content: aiReplyContent,
      timestamp: Date.now(),
    };

    // 添加AI消息
    setMessages((prev) => [...prev, aiMessage]);
    setIsTyping(false);

    // 触发回调
    onAIReply?.(aiMessage);
  };

  /**
   * 处理Enter键发送
   */
  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <Card
      className={`fake-ai-chat ${className}`}
      style={{ height }}
      styles={{ body: { height: '100%', display: 'flex', flexDirection: 'column', padding: 0 } }}
    >
      {/* 消息列表 */}
      <div className="fake-ai-chat-messages" style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {messages.map((message) => (
            <div
              key={message.id}
              role="article"
              className={`fake-ai-chat-message fake-ai-chat-message-${message.role}`}
              style={{
                display: 'flex',
                justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
              }}
            >
              <div
                style={{
                  maxWidth: '70%',
                  display: 'flex',
                  gap: 8,
                  flexDirection: message.role === 'user' ? 'row-reverse' : 'row',
                }}
              >
                {/* 头像 */}
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: '50%',
                    backgroundColor: message.role === 'user' ? '#1890ff' : '#52c41a',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'white',
                    flexShrink: 0,
                  }}
                >
                  {message.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
                </div>

                {/* 消息内容 */}
                <div
                  style={{
                    padding: '8px 12px',
                    borderRadius: 8,
                    backgroundColor: message.role === 'user' ? '#e6f7ff' : '#f6ffed',
                    wordBreak: 'break-word',
                    whiteSpace: 'pre-wrap',
                  }}
                >
                  {message.content}
                </div>
              </div>
            </div>
          ))}

          {/* 正在输入提示 */}
          {isTyping && (
            <div className="fake-ai-chat-typing" style={{ display: 'flex', gap: 8 }}>
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  backgroundColor: '#52c41a',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white',
                }}
              >
                <RobotOutlined />
              </div>
              <div
                style={{
                  padding: '8px 12px',
                  borderRadius: 8,
                  backgroundColor: '#f6ffed',
                }}
              >
                正在输入...
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </Space>
      </div>

      {/* 输入区域 */}
      <div
        className="fake-ai-chat-input"
        style={{
          padding: 16,
          borderTop: '1px solid #f0f0f0',
          backgroundColor: '#fafafa',
        }}
      >
        <Space.Compact style={{ width: '100%' }}>
          <TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="输入消息... (按Enter发送，Shift+Enter换行)"
            autoSize={{ minRows: 1, maxRows: 4 }}
            disabled={isTyping}
            style={{ flex: 1 }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            disabled={!input.trim() || isTyping}
            loading={isTyping}
          >
            发送
          </Button>
        </Space.Compact>
      </div>
    </Card>
  );
}
