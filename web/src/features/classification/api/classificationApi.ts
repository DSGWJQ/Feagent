/**
 * Task Classification API
 *
 * Handles communication with backend task classification endpoints
 */

import axios from 'axios';
import type { ClassificationResult } from '@/types/workflow';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

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
  const response = await axios.post<ClassificationResult>(
    `${API_BASE_URL}/classification`,
    data
  );
  return { data: response.data };
};

export default {
  classifyTask,
};
