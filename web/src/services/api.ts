/**
 * API Client - Unified interface to all backend endpoints
 *
 * Architecture:
 * - Uses axios for HTTP requests
 * - Organized by feature (workflows, classification, scheduler, etc.)
 * - Includes request/response interceptors for auth and error handling
 * - Type-safe with TypeScript interfaces
 */

import axios from 'axios';
import type {
  AxiosInstance,
  AxiosError,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from 'axios';
import type {
  Task,
  Run,
  ClassificationResult,
  ScheduledWorkflow,
  Tool,
  LLMProvider,
  SchedulerStatus,
  SchedulerJobs,
} from '@/types/workflow';

const DEFAULT_API_BASE_URL = '/api';
const rawApiBase = (import.meta.env.VITE_API_URL ?? '').trim();

/**
 * Normalized API base URL. Falls back to the dev proxy (`/api`) so the browser
 * talks to Vite, which then forwards requests to FastAPI without hitting CORS.
 */
export const API_BASE_URL =
  rawApiBase.length > 0 ? rawApiBase.replace(/\/$/, '') : DEFAULT_API_BASE_URL;

// ==================== Axios Instance ====================
export const axiosInstance: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
axiosInstance.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Add auth token if available
    const token = localStorage.getItem('authToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// Response interceptor
axiosInstance.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // Handle common errors
    if (error.response?.status === 401) {
      // Unauthorized - redirect to login
      localStorage.removeItem('authToken');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ==================== API Client Methods ====================

// Task Classification
const classification = {
  classify: (data: { start: string; goal: string; context?: Record<string, unknown> }) =>
    axiosInstance.post<ClassificationResult>('/classification', data),
};

// Scheduled Workflows
const scheduledWorkflows = {
  create: (workflowId: string, data: { cronExpression: string; maxRetries: number }) =>
    axiosInstance.post<ScheduledWorkflow>(
      `/workflows/${workflowId}/schedule`,
      data
    ),
  list: () =>
    axiosInstance.get<ScheduledWorkflow[]>('/scheduled-workflows'),
  getById: (id: string) =>
    axiosInstance.get<ScheduledWorkflow>(`/scheduled-workflows/${id}`),
  update: (id: string, data: Partial<ScheduledWorkflow>) =>
    axiosInstance.put<ScheduledWorkflow>(`/scheduled-workflows/${id}`, data),
  delete: (id: string) =>
    axiosInstance.delete(`/scheduled-workflows/${id}`),
  trigger: (id: string) =>
    axiosInstance.post<{
      scheduledWorkflowId: string;
      executionStatus: string;
      executionTimestamp: string;
      message: string
    }>(`/scheduled-workflows/${id}/trigger`, {}),
  pause: (id: string) =>
    axiosInstance.post<ScheduledWorkflow>(`/scheduled-workflows/${id}/pause`, {}),
  resume: (id: string) =>
    axiosInstance.post<ScheduledWorkflow>(`/scheduled-workflows/${id}/resume`, {}),
};

// Scheduler Monitoring
const scheduler = {
  getStatus: () =>
    axiosInstance.get<SchedulerStatus>('/scheduler/status'),
  getJobs: () =>
    axiosInstance.get<SchedulerJobs>('/scheduler/jobs'),
};

// Tool Management
const tools = {
  create: (data: Partial<Tool>) =>
    axiosInstance.post<Tool>('/tools', data),
  list: (params?: { category?: string }) =>
    axiosInstance.get<Tool[]>('/tools', { params }),
  getById: (id: string) =>
    axiosInstance.get<Tool>(`/tools/${id}`),
  update: (id: string, data: Partial<Tool>) =>
    axiosInstance.put<Tool>(`/tools/${id}`, data),
  delete: (id: string) =>
    axiosInstance.delete(`/tools/${id}`),
  publish: (id: string) =>
    axiosInstance.post<Tool>(`/tools/${id}/publish`, {}),
  deprecate: (id: string) =>
    axiosInstance.post<Tool>(`/tools/${id}/deprecate`, {}),
};

// Knowledge Base Management
const knowledge = {
  upload: (data: {
    title: string;
    content: string;
    workflow_id?: string;
    source?: string;
    metadata?: Record<string, unknown>;
    file_path?: string;
  }) =>
    axiosInstance.post<{
      document_id: string;
      title: string;
      chunk_count: number;
      total_tokens: number;
      message: string;
    }>('/knowledge/upload', data),
  list: (params?: {
    workflow_id?: string;
    user_id?: string;
    source?: string;
    limit?: number;
    offset?: number;
  }) =>
    axiosInstance.get<{
      documents: Array<{
        id: string;
        title: string;
        workflow_id?: string;
        source: string;
        status: string;
        chunk_count: number;
        total_tokens: number;
        created_at: string;
        updated_at: string;
      }>;
      total: number;
      limit: number;
      offset: number;
    }>('/knowledge', { params }),
  getById: (docId: string) =>
    axiosInstance.get<{
      id: string;
      title: string;
      workflow_id?: string;
      source: string;
      status: string;
      chunk_count: number;
      total_tokens: number;
      created_at: string;
      updated_at: string;
    }>(`/knowledge/${docId}`),
  delete: (docId: string) =>
    axiosInstance.delete<{
      document_id: string;
      status: string;
      message: string;
    }>(`/knowledge/${docId}`),
  getStats: (params?: { workflow_id?: string }) =>
    axiosInstance.get<{
      total_documents: number;
      total_chunks: number;
      total_tokens: number;
      by_workflow: Record<string, number>;
      by_source: Record<string, number>;
    }>('/knowledge/stats/summary', { params }),
};

// Memory Metrics
const memory = {
  getMetrics: () =>
    axiosInstance.get<{
      cache_hit_rate: number;
      fallback_count: number;
      compression_ratio: number;
      avg_fallback_time_ms: number;
      last_updated: string;
    }>('/memory/metrics'),
  invalidateCache: (workflowId: string) =>
    axiosInstance.post<{
      status: string;
      workflow_id: string;
    }>(`/memory/cache/invalidate/${workflowId}`, {}),
};

// LLM Provider Management
const llmProviders = {
  register: (data: Partial<LLMProvider>) =>
    axiosInstance.post<LLMProvider>('/llm-providers', data),
  list: (params?: { enabledOnly?: boolean }) =>
    axiosInstance.get<LLMProvider[]>('/llm-providers', { params }),
  getById: (id: string) =>
    axiosInstance.get<LLMProvider>(`/llm-providers/${id}`),
  update: (id: string, data: Partial<LLMProvider>) =>
    axiosInstance.put<LLMProvider>(`/llm-providers/${id}`, data),
  delete: (id: string) =>
    axiosInstance.delete(`/llm-providers/${id}`),
  enable: (id: string) =>
    axiosInstance.post<LLMProvider>(`/llm-providers/${id}/enable`, {}),
  disable: (id: string) =>
    axiosInstance.post<LLMProvider>(`/llm-providers/${id}/disable`, {}),
};

// Error handling utility
const handleError = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status;
    const message = error.response?.data?.detail || error.message;

    console.error('API Error:', { status, message });

    // Provide friendly messages for common errors
    if (status === 404) {
      if (message.includes('Workflow') && message.includes('不存在')) {
        return '工作流不存在，系统将为您创建新的工作流';
      }
      if (message.includes('not found')) {
        return '请求的资源不存在，请检查路径是否正确';
      }
      return '资源未找到，可能已被删除';
    }

    if (status === 403) {
      return '没有权限访问该资源';
    }

    if (status === 401) {
      return '请先登录后再访问';
    }

    if (status === 500) {
      return '服务器内部错误，请稍后重试';
    }

    if (status >= 500) {
      return '服务暂时不可用，请稍后重试';
    }

    if (status >= 400) {
      return '请求失败，请检查输入信息';
    }

    return message as string;
  }
  console.error('Unexpected error:', error);
  return '发生未知错误，请联系技术支持';
};

// Export API client
export const apiClient = {
  classification,
  scheduledWorkflows,
  scheduler,
  tools,
  llmProviders,
  knowledge,
  memory,
  handleError,
  instance: axiosInstance,
};

export default apiClient;
