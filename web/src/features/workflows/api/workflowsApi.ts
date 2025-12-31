/**
 * 工作流 API 客户端
 *
 * 提供工作流相关的 API 调用方法
 */

import { API_BASE_URL, axiosInstance } from '@/services/api';
import type {
  Workflow,
  UpdateWorkflowRequest,
  ExecuteWorkflowRequest,
  ExecuteWorkflowResponse,
  SSEEvent,
} from '../types/workflow';

export interface PlanningSseEvent {
  type: string;
  channel?: string;
  content?: string;
  sequence?: number;
  timestamp?: string;
  is_final?: boolean;
  metadata?: Record<string, any>;
}

/**
 * 列出所有工作流
 */
export async function listWorkflows(): Promise<Workflow[]> {
  // 当前后端未提供 `GET /api/workflows` 列表端点；避免产生 404/405。
  return [];
}

/**
 * 创建工作流
 */
export async function createWorkflow(request: {
  name: string;
  description?: string;
  nodes?: any[];
  edges?: any[];
}): Promise<Workflow> {
  const response = await axiosInstance.post<Workflow>('/workflows', request);
  return response.data;
}

/**
 * 获取工作流详情
 */
export async function getWorkflow(workflowId: string): Promise<Workflow> {
  const response = await axiosInstance.get<Workflow>(`/workflows/${workflowId}`);
  return response.data;
}

/**
 * 更新工作流（拖拽调整）
 */
export async function updateWorkflow(
  workflowId: string,
  request: UpdateWorkflowRequest
): Promise<Workflow> {
  const response = await axiosInstance.patch<Workflow>(`/workflows/${workflowId}`, request);
  return response.data;
}

/**
 * 执行工作流（非流式）
 */
export async function executeWorkflow(
  workflowId: string,
  request: ExecuteWorkflowRequest
): Promise<ExecuteWorkflowResponse> {
  const response = await axiosInstance.post<ExecuteWorkflowResponse>(
    `/workflows/${workflowId}/execute`,
    request
  );
  return response.data;
}

/**
 * Chat-stream（流式 SSE，planning channel）
 *
 * @returns 取消函数
 */
export function chatWorkflowStreaming(
  workflowId: string,
  request: { message: string; run_id?: string },
  onEvent: (event: PlanningSseEvent) => void,
  onError?: (error: Error) => void
): () => void {
  const abortController = new AbortController();

  fetch(`${API_BASE_URL}/workflows/${workflowId}/chat-stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
    signal: abortController.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      if (!response.body) {
        throw new Error('No response body');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        let boundary = buffer.indexOf('\n\n');
        while (boundary !== -1) {
          const chunk = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          boundary = buffer.indexOf('\n\n');

          if (!chunk.startsWith('data:')) {
            continue;
          }

          const data = chunk.replace(/^data:\s*/, '').trim();
          if (!data || data === '[DONE]') {
            continue;
          }

          try {
            onEvent(JSON.parse(data) as PlanningSseEvent);
          } catch (error) {
            console.warn('Failed to parse chat-stream SSE event:', error);
          }
        }
      }
    })
    .catch((error) => {
      if (error?.name === 'AbortError') {
        return;
      }
      if (onError) {
        onError(error);
      } else {
        console.error('chat-stream error:', error);
      }
    });

  return () => {
    abortController.abort();
  };
}

/**
 * 执行工作流（流式 SSE）
 *
 * 注意：由于 EventSource 不支持 POST 请求，我们使用 fetch + ReadableStream
 *
 * @param workflowId 工作流 ID
 * @param request 执行请求
 * @param onEvent SSE 事件回调
 * @param onError 错误回调
 * @returns 取消函数
 */
export function executeWorkflowStreaming(
  workflowId: string,
  request: ExecuteWorkflowRequest,
  onEvent: (event: SSEEvent) => void,
  onError?: (error: Error) => void
): () => void {
  const abortController = new AbortController();

  // 使用 fetch 发送 POST 请求
  fetch(`${API_BASE_URL}/workflows/${workflowId}/execute/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
    signal: abortController.signal,
  })
    .then(async (response) => {
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
            const data: SSEEvent = JSON.parse(line.substring(6)); // 去掉 "data: " 前缀
            onEvent(data);

            // 如果收到完成或错误事件，停止读取
            if (data.type === 'workflow_complete' || data.type === 'workflow_error') {
              reader.cancel();
              return;
            }
          } catch (error) {
            console.error('Failed to parse SSE event:', error);
          }
        }
      }
    })
    .catch((error) => {
      if (error.name === 'AbortError') {
        console.log('SSE request aborted');
        return;
      }
      console.error('SSE connection error:', error);
      if (onError) {
        onError(error);
      }
    });

  // 返回取消函数
  return () => {
    abortController.abort();
  };
}
