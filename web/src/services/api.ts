/**
 * API Client - Unified interface to all backend endpoints
 *
 * Architecture:
 * - Uses axios for HTTP requests
 * - Organized by feature (workflows, classification, scheduler, etc.)
 * - Includes request/response interceptors for auth and error handling
 * - Type-safe with TypeScript interfaces
 */

import axios, {
  AxiosInstance,
  AxiosError,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from 'axios';
import {
  Workflow,
  Task,
  Run,
  ClassificationResult,
  ScheduledWorkflow,
  Tool,
  LLMProvider,
  SchedulerStatus,
  SchedulerJobs,
  TaskType,
} from '../types/workflow';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

// ==================== Axios Instance ====================
const axiosInstance: AxiosInstance = axios.create({
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

// Workflow Management
const workflows = {
  create: (data: Partial<Workflow>) =>
    axiosInstance.post<Workflow>('/workflows', data),
  list: () =>
    axiosInstance.get<Workflow[]>('/workflows'),
  getById: (id: string) =>
    axiosInstance.get<Workflow>(`/workflows/${id}`),
  update: (id: string, data: Partial<Workflow>) =>
    axiosInstance.put<Workflow>(`/workflows/${id}`, data),
  delete: (id: string) =>
    axiosInstance.delete(`/workflows/${id}`),
  publish: (id: string) =>
    axiosInstance.post<Workflow>(`/workflows/${id}/publish`, {}),
};

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
    const message = error.response?.data?.detail || error.message;
    console.error('API Error:', message);
    return message as string;
  }
  console.error('Unexpected error:', error);
  return 'An unexpected error occurred';
};

// Export API client
export const apiClient = {
  workflows,
  classification,
  scheduledWorkflows,
  scheduler,
  tools,
  llmProviders,
  handleError,
  instance: axiosInstance,
};

export default apiClient;
