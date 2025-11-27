/**
 * useWorkflow Hook
 * 拉取单个工作流的详情，供编辑器使用
 */

import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import type { Workflow } from '@/types/workflow';

interface UseWorkflowResult {
  workflowData: Workflow | null;
  isLoadingWorkflow: boolean;
  workflowError: unknown;
  refetchWorkflow: UseQueryResult<Workflow | null, unknown>['refetch'];
}

export const useWorkflow = (workflowId?: string | null): UseWorkflowResult => {
  const query = useQuery<Workflow | null>({
    queryKey: ['workflow', workflowId],
    queryFn: async () => {
      if (!workflowId) {
        return null;
      }
      const response = await apiClient.workflows.getById(workflowId);
      return response.data;
    },
    enabled: Boolean(workflowId),
    retry: 1,
    staleTime: 30_000,
  });

  return {
    workflowData: query.data ?? null,
    isLoadingWorkflow: query.isLoading,
    workflowError: query.error ?? null,
    refetchWorkflow: query.refetch,
  };
};

export default useWorkflow;
