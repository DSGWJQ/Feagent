/**
 * Task Classification API
 *
 * Handles communication with backend task classification endpoints
 */

import type { ClassificationResult } from '@/types/workflow';
import { axiosInstance } from '@/services/api';

export interface ClassifyTaskRequest {
  start: string;
  goal: string;
  context?: Record<string, unknown>;
}

/**
 * Classify a task based on start point and goal
 */
export const classifyTask = async (
  data: ClassifyTaskRequest
): Promise<{ data: ClassificationResult }> => {
  const response = await axiosInstance.post<ClassificationResult>(
    '/classification',
    data
  );
  return { data: response.data };
};

export default {
  classifyTask,
};
