import { useCallback, useState } from 'react';

import { apiClient } from '@/services/api';
import {
  chatWorkflowStreaming,
  type PlanningSseEvent,
} from '@/features/workflows/api/workflowsApi';
import type { Workflow } from '@/features/workflows/types/workflow';
import type { ChatMessage } from '@/shared/types/chat';

interface UseWorkflowAIOptions {
  workflowId: string;
  onApplyWorkflow?: (workflow: Workflow) => void;
  onPreviewWorkflow?: (workflow: Workflow, message: string) => void;
}

interface UseWorkflowAIResult {
  messages: ChatMessage[];
  isProcessing: boolean;
  pendingWorkflow: Workflow | null;
  streamingMessage: string | null;
  sendMessage: (content: string) => Promise<void>;
  confirmPendingWorkflow: () => Promise<void>;
  startChatStream: (content: string) => Promise<void>;
  errorMessage: string | null;
}

const createMessage = (content: string, role: ChatMessage['role']): ChatMessage => ({
  id: `${role}_${Date.now()}_${Math.random().toString(16).slice(2)}`,
  role,
  content,
  timestamp: Date.now(),
});

export const useWorkflowAI = ({
  workflowId,
  onApplyWorkflow,
  onPreviewWorkflow,
}: UseWorkflowAIOptions): UseWorkflowAIResult => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pendingWorkflow, setPendingWorkflow] = useState<Workflow | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [streamingMessage, setStreamingMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const appendMessage = useCallback((message: ChatMessage) => {
    setMessages((prev) => [...prev, message]);
  }, []);

  const confirmPendingWorkflow = useCallback(async () => {
    if (!pendingWorkflow) {
      return;
    }
    onApplyWorkflow?.(pendingWorkflow);
    setPendingWorkflow(null);
  }, [onApplyWorkflow, pendingWorkflow]);

  const startChatStream = useCallback(
    async (rawContent: string) => {
      const content = rawContent.trim();
      if (!content || isProcessing) {
        return;
      }

      appendMessage(createMessage(content, 'user'));
      setIsProcessing(true);
      setErrorMessage(null);
      setStreamingMessage(null);

      try {
        await new Promise<void>((resolve, reject) => {
          const cancel = chatWorkflowStreaming(
            workflowId,
            { message: content },
            (event: PlanningSseEvent) => {
              if (event.type === 'thinking') {
                setStreamingMessage(event.content ?? null);
                return;
              }

              if (event.type === 'patch') {
                const previewWorkflow = event.metadata?.workflow as Workflow | undefined;
                if (previewWorkflow) {
                  setPendingWorkflow(previewWorkflow);
                  onPreviewWorkflow?.(previewWorkflow, event.content ?? '');
                }
                if (event.content) {
                  appendMessage(createMessage(event.content, 'assistant'));
                }
                setStreamingMessage(null);
              }

              if (event.type === 'final') {
                const finalWorkflow = event.metadata?.workflow as Workflow | undefined;
                if (finalWorkflow) {
                  setPendingWorkflow(finalWorkflow);
                }
                if (event.content) {
                  appendMessage(createMessage(event.content, 'assistant'));
                }
                setStreamingMessage(null);
              }

              if (event.type === 'error') {
                setStreamingMessage(null);
                reject(new Error(event.content || 'chat-stream failed'));
                cancel();
                return;
              }

              if (event.is_final) {
                cancel();
                resolve();
              }
            },
            (error) => {
              reject(error);
            }
          );
        });
      } catch (error) {
        const friendlyMessage =
          error instanceof Error ? apiClient.handleError(error) : '处理失败';
        setErrorMessage(friendlyMessage);
        appendMessage(createMessage(`处理失败：${friendlyMessage}`, 'assistant'));
      } finally {
        setIsProcessing(false);
        setStreamingMessage(null);
      }
    },
    [appendMessage, isProcessing, workflowId, onPreviewWorkflow]
  );

  const sendMessage = useCallback(
    async (content: string) => {
      await startChatStream(content);
    },
    [startChatStream]
  );

  return {
    messages,
    isProcessing,
    pendingWorkflow,
    streamingMessage,
    sendMessage,
    confirmPendingWorkflow,
    startChatStream,
    errorMessage,
  };
};

export default useWorkflowAI;
