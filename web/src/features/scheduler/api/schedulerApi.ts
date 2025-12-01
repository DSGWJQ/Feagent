/**
 * Scheduler API
 *
 * Handles communication with scheduler monitoring endpoints
 */

import type { SchedulerStatus, SchedulerJobs } from '@/types/workflow';
import { axiosInstance } from '@/services/api';

/**
 * Get scheduler status
 */
export const getSchedulerStatus = async (): Promise<{ data: SchedulerStatus }> => {
  const response = await axiosInstance.get<SchedulerStatus>('/scheduler/status');
  return { data: response.data };
};

/**
 * Get scheduler jobs
 */
export const getSchedulerJobs = async (): Promise<{ data: SchedulerJobs }> => {
  const response = await axiosInstance.get<SchedulerJobs>('/scheduler/jobs');
  return { data: response.data };
};

export default {
  getSchedulerStatus,
  getSchedulerJobs,
};
