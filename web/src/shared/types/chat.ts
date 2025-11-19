/**
 * 聊天消息相关类型定义
 */

/**
 * 消息角色
 */
export type MessageRole = 'user' | 'assistant' | 'system';

/**
 * 聊天消息
 */
export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
}

/**
 * AI 回复规则
 */
export interface AIReplyRule {
  // 匹配关键词（支持正则表达式字符串）
  pattern: string | RegExp;
  // 回复内容（可以是字符串或函数）
  reply: string | ((match: RegExpMatchArray | null, userMessage: string) => string);
  // 优先级（数字越大优先级越高）
  priority?: number;
}

