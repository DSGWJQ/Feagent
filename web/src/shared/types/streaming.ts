/**
 * Phase 4: 流式消息类型定义
 *
 * 与后端 StreamMessageFormatter 输出格式保持一致。
 */

/**
 * 前端消息类型枚举
 */
export type StreamingMessageType =
  | 'thought'       // 思考过程
  | 'tool_call'     // 工具调用
  | 'tool_result'   // 工具结果
  | 'final'         // 最终响应
  | 'error'         // 错误
  | 'status'        // 状态更新
  | 'delta'         // 增量内容
  | 'stream_start'  // 流开始
  | 'stream_end';   // 流结束

/**
 * 工具调用元数据
 */
export interface ToolCallMetadata {
  tool: string;
  tool_id: string;
  arguments: Record<string, unknown>;
}

/**
 * 工具结果元数据
 */
export interface ToolResultMetadata {
  tool_id: string;
  result: unknown;
  success: boolean;
  error?: string;
}

/**
 * 错误元数据
 */
export interface ErrorMetadata {
  error_code: string;
  recoverable: boolean;
}

/**
 * 流式消息元数据（联合类型）
 */
export type StreamingMessageMetadata =
  | ToolCallMetadata
  | ToolResultMetadata
  | ErrorMetadata
  | { is_final?: boolean; delta_index?: number; session_id?: string }
  | Record<string, unknown>;

/**
 * 流式消息接口
 *
 * 这是从后端 SSE 接收的标准消息格式。
 */
export interface StreamingMessage {
  /** 消息类型 */
  type: StreamingMessageType;
  /** 消息内容 */
  content: string;
  /** 附加元数据 */
  metadata: StreamingMessageMetadata;
  /** ISO 格式时间戳 */
  timestamp: string;
  /** 消息序列号 */
  sequence: number;
  /** 是否为流式消息（增量） */
  is_streaming: boolean;
  /** 消息唯一标识 */
  message_id: string;
}

/**
 * 聊天消息（带流式信息）
 */
export interface ChatMessageWithStreaming {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  /** 流式消息类型（可选） */
  streamingType?: StreamingMessageType;
  /** 流式消息元数据（可选） */
  streamingMetadata?: StreamingMessageMetadata;
  /** 是否正在流式传输 */
  isStreaming?: boolean;
}

/**
 * 流式消息事件
 */
export interface StreamingEvent {
  message: StreamingMessage;
  raw: string;
}

/**
 * 流式会话状态
 */
export interface StreamingSessionState {
  isConnected: boolean;
  isStreaming: boolean;
  sessionId: string | null;
  messages: StreamingMessage[];
  error: string | null;
}

/**
 * 解析 SSE 数据行
 */
export function parseSSELine(line: string): StreamingMessage | null {
  if (!line.startsWith('data: ')) return null;

  const data = line.substring(6);
  if (data === '[DONE]') return null;

  try {
    return JSON.parse(data) as StreamingMessage;
  } catch {
    return null;
  }
}

/**
 * 获取消息类型的显示名称
 */
export function getMessageTypeLabel(type: StreamingMessageType): string {
  const labels: Record<StreamingMessageType, string> = {
    thought: '思考',
    tool_call: '工具调用',
    tool_result: '工具结果',
    final: '回复',
    error: '错误',
    status: '状态',
    delta: '内容',
    stream_start: '开始',
    stream_end: '结束',
  };
  return labels[type] || type;
}

/**
 * 获取消息类型的图标
 */
export function getMessageTypeIcon(type: StreamingMessageType): string {
  const icons: Record<StreamingMessageType, string> = {
    thought: '💭',
    tool_call: '🔧',
    tool_result: '📋',
    final: '✅',
    error: '❌',
    status: '📊',
    delta: '📝',
    stream_start: '🚀',
    stream_end: '🏁',
  };
  return icons[type] || '📌';
}

/**
 * 检查是否为中间步骤（thought/tool_call/tool_result）
 */
export function isIntermediateStep(type: StreamingMessageType): boolean {
  return ['thought', 'tool_call', 'tool_result', 'status'].includes(type);
}

/**
 * 检查是否为终止消息
 */
export function isTerminalMessage(type: StreamingMessageType): boolean {
  return ['final', 'error', 'stream_end'].includes(type);
}
