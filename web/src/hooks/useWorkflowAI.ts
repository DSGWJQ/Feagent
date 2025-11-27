import { useCallback, useState } from 'react';

import { apiClient } from '@/services/api';
import type { Workflow } from '@/types/workflow';
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

const formatStreamEvent = (event: Record<string, unknown>): string => {
  const { type = 'event', ...rest } = event;
  const detail = Object.keys(rest).length ? JSON.stringify(rest) : '';
  return `【${String(type)}】${detail}`;
};

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

  const sendMessage = useCallback(
    async (rawContent: string) => {
      const content = rawContent.trim();
      if (!content || isProcessing) {
        return;
      }

      appendMessage(createMessage(content, 'user'));
      setIsProcessing(true);
      setErrorMessage(null);

      try {
        const { data } = await apiClient.workflows.chat(workflowId, { message: content });
        setPendingWorkflow(data.workflow as Workflow);
        appendMessage(createMessage(data.ai_message, 'assistant'));

        await apiClient.workflows.streamExecution(
          workflowId,
          { initial_input: { message: content } },
          (event) => {
            appendMessage(createMessage(formatStreamEvent(event), 'assistant'));
          }
        );
      } catch (error) {
        const friendlyMessage = apiClient.handleError(error);
        setErrorMessage(friendlyMessage);
        appendMessage(createMessage(`处理失败：${friendlyMessage}`, 'assistant'));
      } finally {
        setIsProcessing(false);
      }
    },
    [appendMessage, isProcessing, workflowId]
  );

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
        const response = await fetch(`/api/workflows/${workflowId}/chat-stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ message: content }),
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        if (!response.body) {
          throw new Error('No response body');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();

          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.trim() || !line.startsWith('data: ')) continue;

            try {
              const data = JSON.parse(line.substring(6));

              // Handle different event types
              switch (data.event || data.type) {
                case 'llm_thinking':
                  setStreamingMessage(data.message);
                  break;
                case 'preview_changes':
                  // Create workflow object from preview data
                  const previewWorkflow: Workflow = {
                    id: workflowId,
                    name: 'Preview Workflow',
                    nodes: data.nodes,
                    edges: data.edges,
                    status: 'draft' as any,
                    created_at: new Date().toISOString(),
                    updated_at: new Date().toISOString(),
                  };
                  setPendingWorkflow(previewWorkflow);
                  onPreviewWorkflow?.(previewWorkflow, data.message);
                  appendMessage(createMessage(data.message, 'assistant'));
                  setStreamingMessage(null);
                  break;
                case 'workflow_updated':
                  // Update final workflow
                  const finalWorkflow: Workflow = {
                    id: workflowId,
                    name: data.workflow.name,
                    nodes: data.workflow.nodes,
                    edges: data.workflow.edges,
                    status: 'draft' as any,
                    created_at: new Date().toISOString(),
                    updated_at: new Date().toISOString(),
                  };
                  setPendingWorkflow(finalWorkflow);
                  appendMessage(createMessage(data.message, 'assistant'));
                  setStreamingMessage(null);
                  break;
                case 'error':
                  throw new Error(data.message);
              }
            } catch (error) {
              console.error('Failed to parse SSE event:', error);
            }
          }
        }
      } catch (error) {
        const friendlyMessage = error instanceof Error ? error.message : '处理失败';
        setErrorMessage(friendlyMessage);
        appendMessage(createMessage(`处理失败：${friendlyMessage}`, 'assistant'));
      } finally {
        setIsProcessing(false);
        setStreamingMessage(null);
      }
    },
    [appendMessage, isProcessing, workflowId, onPreviewWorkflow]
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
