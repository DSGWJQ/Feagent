/**
 * useClassification Hook
 * 负责管理任务分类相关的 API 调用
 */

import { useMutation } from '@tanstack/react-query';
import { apiClient } from '../services/api';
import type { ClassificationResult } from '@/types/workflow';

export const useClassification = () => {
  // 触发任务分类
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
