/**
 * Scheduled Workflows API
 *
 * Handles communication with backend scheduled workflow endpoints
 */

import type { ScheduledWorkflow } from '@/types/workflow';
import { axiosInstance } from '@/services/api';

export interface CreateScheduledWorkflowRequest {
  cronExpression: string;
  maxRetries: number;
}

export interface ScheduledWorkflowResponse {
  scheduledWorkflowId: string;
  executionStatus: string;
  executionTimestamp: string;
  message: string;
}

/**
 * List all scheduled workflows
 */
export const listScheduledWorkflows = async (): Promise<{ data: ScheduledWorkflow[] }> => {
  const response = await axiosInstance.get<ScheduledWorkflow[]>('/scheduled-workflows');
  return { data: response.data };
};

/**
 * Get scheduled workflow details
 */
export const getScheduledWorkflowDetails = async (
  id: string
): Promise<{ data: ScheduledWorkflow }> => {
  const response = await axiosInstance.get<ScheduledWorkflow>(
    `/scheduled-workflows/${id}`
  );
  return { data: response.data };
};

/**
 * Create a new scheduled workflow
 */
export const createScheduledWorkflow = async (
  workflowId: string,
  data: CreateScheduledWorkflowRequest
): Promise<{ data: ScheduledWorkflow }> => {
  const response = await axiosInstance.post<ScheduledWorkflow>(
    `/workflows/${workflowId}/schedule`,
    data
  );
  return { data: response.data };
};

/**
 * Update scheduled workflow
 */
export const updateScheduledWorkflow = async (
  id: string,
  data: Partial<ScheduledWorkflow>
): Promise<{ data: ScheduledWorkflow }> => {
  const response = await axiosInstance.put<ScheduledWorkflow>(
    `/scheduled-workflows/${id}`,
    data
  );
  return { data: response.data };
};

/**
 * Delete scheduled workflow
 */
export const deleteScheduledWorkflow = async (id: string): Promise<{ data: null }> => {
  await axiosInstance.delete(`/scheduled-workflows/${id}`);
  return { data: null };
};

/**
 * Trigger scheduled workflow execution
 */
export const triggerExecution = async (
  id: string
): Promise<{ data: ScheduledWorkflowResponse }> => {
  const response = await axiosInstance.post<ScheduledWorkflowResponse>(
    `/scheduled-workflows/${id}/trigger`,
    {}
  );
  return { data: response.data };
};

/**
 * Pause scheduled workflow
 */
export const pauseScheduledWorkflow = async (id: string): Promise<{ data: ScheduledWorkflow }> => {
  const response = await axiosInstance.post<ScheduledWorkflow>(
    `/scheduled-workflows/${id}/pause`,
    {}
  );
  return { data: response.data };
};

/**
 * Resume scheduled workflow
 */
export const resumeScheduledWorkflow = async (
  id: string
): Promise<{ data: ScheduledWorkflow }> => {
  const response = await axiosInstance.post<ScheduledWorkflow>(
    `/scheduled-workflows/${id}/resume`,
    {}
  );
  return { data: response.data };
};

export default {
  listScheduledWorkflows,
  getScheduledWorkflowDetails,
  createScheduledWorkflow,
  updateScheduledWorkflow,
  deleteScheduledWorkflow,
  triggerExecution,
  pauseScheduledWorkflow,
  resumeScheduledWorkflow,
};
