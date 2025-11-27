/**
 * Scheduler API
 *
 * Handles communication with scheduler monitoring endpoints
 */

import axios from 'axios';
import type { SchedulerStatus, SchedulerJobs } from '@/types/workflow';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

/**
 * Get scheduler status
 */
export const getSchedulerStatus = async (): Promise<{ data: SchedulerStatus }> => {
  const response = await axios.get<SchedulerStatus>(
    `${API_BASE_URL}/scheduler/status`
  );
  return { data: response.data };
};

/**
 * Get scheduler jobs
 */
export const getSchedulerJobs = async (): Promise<{ data: SchedulerJobs }> => {
  const response = await axios.get<SchedulerJobs>(
    `${API_BASE_URL}/scheduler/jobs`
  );
  return { data: response.data };
};

export default {
  getSchedulerStatus,
  getSchedulerJobs,
};
