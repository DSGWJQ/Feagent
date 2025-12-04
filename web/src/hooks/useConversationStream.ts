/**
 * Phase 4: 流式对话 Hook
 *
 * 连接到 /api/conversation/stream 端点，实时接收并展示消息。
 */

import { useCallback, useRef, useState } from 'react';

import type {
  StreamingMessage,
  StreamingMessageType,
  ChatMessageWithStreaming,
} from '@/shared/types/streaming';
import { parseSSELine, isTerminalMessage } from '@/shared/types/streaming';

interface UseConversationStreamOptions {
  /** 工作流 ID（可选） */
  workflowId?: string;
  /** 收到新消息时的回调 */
  onMessage?: (message: StreamingMessage) => void;
  /** 流结束时的回调 */
  onComplete?: (messages: StreamingMessage[]) => void;
  /** 错误回调 */
  onError?: (error: string) => void;
}

interface UseConversationStreamResult {
  /** 所有消息 */
  messages: StreamingMessage[];
  /** 聊天格式的消息（用于聊天 UI） */
  chatMessages: ChatMessageWithStreaming[];
  /** 是否正在流式传输 */
  isStreaming: boolean;
  /** 当前会话 ID */
  sessionId: string | null;
  /** 错误信息 */
  error: string | null;
  /** 发送消息 */
  sendMessage: (content: string) => Promise<void>;
  /** 取消当前流 */
  cancel: () => void;
  /** 清空消息 */
  clearMessages: () => void;
}

/**
 * 流式对话 Hook
 *
 * @example
 * ```tsx
 * const { messages, isStreaming, sendMessage } = useConversationStream({
 *   workflowId: 'wf_001',
 *   onMessage: (msg) => console.log('收到:', msg),
 * });
 *
 * // 发送消息
 * await sendMessage('分析这个工作流');
 *
 * // 显示消息
 * messages.map(m => <StreamingMessageDisplay message={m} />)
 * ```
 */
export const useConversationStream = (
  options: UseConversationStreamOptions = {}
): UseConversationStreamResult => {
  const { workflowId, onMessage, onComplete, onError } = options;

  const [messages, setMessages] = useState<StreamingMessage[]>([]);
  const [chatMessages, setChatMessages] = useState<ChatMessageWithStreaming[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesRef = useRef<StreamingMessage[]>([]);

  /**
   * 添加流式消息
   */
  const addStreamingMessage = useCallback((message: StreamingMessage) => {
    messagesRef.current = [...messagesRef.current, message];
    setMessages([...messagesRef.current]);
    onMessage?.(message);
  }, [onMessage]);

  /**
   * 转换为聊天消息格式
   */
  const convertToChatMessage = useCallback(
    (content: string, role: 'user' | 'assistant', streamingType?: StreamingMessageType): ChatMessageWithStreaming => ({
      id: `${role}_${Date.now()}_${Math.random().toString(16).slice(2)}`,
      role,
      content,
      timestamp: Date.now(),
      streamingType,
    }),
    []
  );

  /**
   * 发送消息并开始流式接收
   */
  const sendMessage = useCallback(
    async (content: string) => {
      const trimmed = content.trim();
      if (!trimmed || isStreaming) return;

      // 重置状态
      setError(null);
      setIsStreaming(true);
      messagesRef.current = [];
      setMessages([]);

      // 添加用户消息到聊天
      const userMessage = convertToChatMessage(trimmed, 'user');
      setChatMessages((prev) => [...prev, userMessage]);

      // 创建 AbortController
      abortControllerRef.current = new AbortController();

      try {
        const response = await fetch('/api/conversation/stream', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'text/event-stream',
          },
          body: JSON.stringify({
            message: trimmed,
            workflow_id: workflowId,
          }),
          signal: abortControllerRef.current.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        // 获取 session ID
        const newSessionId = response.headers.get('X-Session-ID');
        if (newSessionId) {
          setSessionId(newSessionId);
        }

        if (!response.body) {
          throw new Error('No response body');
        }

        // 读取流
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalContent = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.trim()) continue;

            if (line.startsWith('data: ')) {
              const data = line.substring(6);

              if (data === '[DONE]') {
                // 流结束
                break;
              }

              const message = parseSSELine(line);
              if (message) {
                addStreamingMessage(message);

                // 收集最终响应内容
                if (message.type === 'final') {
                  finalContent = message.content;
                }

                // 检查是否为终止消息
                if (isTerminalMessage(message.type)) {
                  // 添加 AI 回复到聊天消息
                  if (finalContent) {
                    const aiMessage = convertToChatMessage(finalContent, 'assistant', 'final');
                    setChatMessages((prev) => [...prev, aiMessage]);
                  }
                }
              }
            }
          }
        }

        // 完成回调
        onComplete?.(messagesRef.current);
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          // 用户取消，不算错误
          return;
        }

        const errorMessage = err instanceof Error ? err.message : '连接失败';
        setError(errorMessage);
        onError?.(errorMessage);

        // 添加错误消息到聊天
        const errorChatMessage = convertToChatMessage(`错误: ${errorMessage}`, 'assistant', 'error');
        setChatMessages((prev) => [...prev, errorChatMessage]);
      } finally {
        setIsStreaming(false);
        abortControllerRef.current = null;
      }
    },
    [isStreaming, workflowId, convertToChatMessage, addStreamingMessage, onComplete, onError]
  );

  /**
   * 取消当前流
   */
  const cancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  /**
   * 清空消息
   */
  const clearMessages = useCallback(() => {
    setMessages([]);
    setChatMessages([]);
    messagesRef.current = [];
    setError(null);
  }, []);

  return {
    messages,
    chatMessages,
    isStreaming,
    sessionId,
    error,
    sendMessage,
    cancel,
    clearMessages,
  };
};

export default useConversationStream;
