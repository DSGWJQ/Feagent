/**
 * 统一导出所有类型定义
 *
 * 为什么需要这个文件？
 * - 提供统一的导入入口
 * - 简化导入语句：import { Agent, Run } from '@/shared/types'
 */

// Agent 相关类型
export type {
  Agent,
  CreateAgentDto,
  UpdateAgentDto,
  AgentListParams,
} from './agent';

// Run 相关类型
export type {
  Run,
  CreateRunDto,
  RunListParams,
} from './run';

export {
  RunStatus,
  RUN_STATUS_CONFIG,
} from './run';

// Task 相关类型
export type {
  Task,
} from './task';

export {
  TaskStatus,
  TASK_STATUS_CONFIG,
} from './task';

// API 相关类型（如果存在）
export type {
  Result,
} from './api';

// Chat 相关类型
export type {
  ChatMessage,
  MessageRole,
  AIReplyRule,
} from './chat';

// Streaming 相关类型
export type {
  StreamingMessage,
  StreamingMessageType,
  StreamingMessageMetadata,
  ChatMessageWithStreaming,
  StreamingEvent,
  StreamingSessionState,
  ToolCallMetadata,
  ToolResultMetadata,
  ErrorMetadata,
} from './streaming';

export {
  parseSSELine,
  getMessageTypeLabel,
  getMessageTypeIcon,
  isIntermediateStep,
  isTerminalMessage,
} from './streaming';
