/**
 * useWorkflow Hook
 * Manages workflow-related API calls and state
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../services/api';
import { Workflow } from '../types/workflow';

export const useWorkflow = () => {
  const queryClient = useQueryClient();

  // List all workflows
  const {
    data: workflows = [],
    isLoading: isLoadingWorkflows,
    error: workflowsError,
  } = useQuery({
    queryKey: ['workflows'],
    queryFn: async () => {
      const response = await apiClient.workflows.list();
      return response.data;
    },
  });

  // Get workflow details
  const useGetWorkflowDetails = (workflowId: string | null) => {
    return useQuery({
      queryKey: ['workflow', workflowId],
      queryFn: async () => {
        if (!workflowId) return null;
        const response = await apiClient.workflows.getById(workflowId);
        return response.data;
      },
      enabled: !!workflowId,
    });
  };

  // Create workflow
  const createWorkflow = useMutation({
    mutationFn: (data: Partial<Workflow>) =>
      apiClient.workflows.create(data).then((res) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });

  // Update workflow
  const updateWorkflow = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: Partial<Workflow>;
    }) => apiClient.workflows.update(id, data).then((res) => res.data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      queryClient.setQueryData(['workflow', data.id], data);
    },
  });

  // Publish workflow
  const publishWorkflow = useMutation({
    mutationFn: (id: string) =>
      apiClient.workflows.publish(id).then((res) => res.data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      queryClient.setQueryData(['workflow', data.id], data);
    },
  });

  // Delete workflow
  const deleteWorkflow = useMutation({
    mutationFn: (id: string) =>
      apiClient.workflows.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    },
  });

  return {
    workflows,
    isLoadingWorkflows,
    workflowsError,
    useGetWorkflowDetails,
    createWorkflow,
    updateWorkflow,
    publishWorkflow,
    deleteWorkflow,
  };
};

export default useWorkflow;
