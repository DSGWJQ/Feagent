/**
 * useClassification Hook
 * Manages task classification API operations
 */

import { useMutation } from '@tanstack/react-query';
import { apiClient } from '../services/api';
import { ClassificationResult } from '../types/workflow';

export const useClassification = () => {
  // Classify task
  const classifyTask = useMutation({
    mutationFn: (data: {
      start: string;
      goal: string;
      context?: Record<string, unknown>;
    }) =>
      apiClient.classification
        .classify(data)
        .then((res) => res.data as ClassificationResult),
  });

  return {
    classifyTask,
    isClassifying: classifyTask.isPending,
    classificationError: classifyTask.error,
    classificationData: classifyTask.data,
  };
};

export default useClassification;
