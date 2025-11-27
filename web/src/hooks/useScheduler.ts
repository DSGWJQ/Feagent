/**
 * useScheduler Hook
 * Manages scheduler and scheduled workflow operations
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../services/api';
import type { ScheduledWorkflow } from '../types/workflow';

export const useScheduler = () => {
  const queryClient = useQueryClient();

  // List all scheduled workflows
  const {
    data: scheduledWorkflows = [],
    isLoading: isLoadingScheduledWorkflows,
    error: scheduledWorkflowsError,
  } = useQuery({
    queryKey: ['scheduledWorkflows'],
    queryFn: async () => {
      const response = await apiClient.scheduledWorkflows.list();
      return response.data;
    },
  });

  // Get scheduled workflow details
  const useGetScheduledWorkflowDetails = (scheduledWorkflowId: string | null) => {
    return useQuery({
      queryKey: ['scheduledWorkflow', scheduledWorkflowId],
      queryFn: async () => {
        if (!scheduledWorkflowId) return null;
        const response = await apiClient.scheduledWorkflows.getById(scheduledWorkflowId);
        return response.data;
      },
      enabled: !!scheduledWorkflowId,
    });
  };

  // Get scheduler status
  const {
    data: schedulerStatus,
    isLoading: isLoadingSchedulerStatus,
    error: schedulerStatusError,
  } = useQuery({
    queryKey: ['schedulerStatus'],
    queryFn: async () => {
      const response = await apiClient.scheduler.getStatus();
      return response.data;
    },
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Get scheduler jobs
  const {
    data: schedulerJobs,
    isLoading: isLoadingSchedulerJobs,
    error: schedulerJobsError,
  } = useQuery({
    queryKey: ['schedulerJobs'],
    queryFn: async () => {
      const response = await apiClient.scheduler.getJobs();
      return response.data;
    },
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Create scheduled workflow
  const createScheduledWorkflow = useMutation({
    mutationFn: ({
      workflowId,
      cronExpression,
      maxRetries,
    }: {
      workflowId: string;
      cronExpression: string;
      maxRetries: number;
    }) =>
      apiClient.scheduledWorkflows
        .create(workflowId, { cronExpression, maxRetries })
        .then((res) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduledWorkflows'] });
      queryClient.invalidateQueries({ queryKey: ['schedulerJobs'] });
    },
  });

  // Update scheduled workflow
  const updateScheduledWorkflow = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: Partial<ScheduledWorkflow>;
    }) =>
      apiClient.scheduledWorkflows.update(id, data).then((res) => res.data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['scheduledWorkflows'] });
      queryClient.setQueryData(['scheduledWorkflow', data.id], data);
    },
  });

  // Trigger scheduled workflow execution
  const triggerExecution = useMutation({
    mutationFn: (scheduledWorkflowId: string) =>
      apiClient.scheduledWorkflows.trigger(scheduledWorkflowId).then((res) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduledWorkflows'] });
      queryClient.invalidateQueries({ queryKey: ['schedulerStatus'] });
    },
  });

  // Pause scheduled workflow
  const pauseScheduledWorkflow = useMutation({
    mutationFn: (scheduledWorkflowId: string) =>
      apiClient.scheduledWorkflows.pause(scheduledWorkflowId).then((res) => res.data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['scheduledWorkflows'] });
      queryClient.setQueryData(['scheduledWorkflow', data.id], data);
      queryClient.invalidateQueries({ queryKey: ['schedulerJobs'] });
    },
  });

  // Resume scheduled workflow
  const resumeScheduledWorkflow = useMutation({
    mutationFn: (scheduledWorkflowId: string) =>
      apiClient.scheduledWorkflows.resume(scheduledWorkflowId).then((res) => res.data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['scheduledWorkflows'] });
      queryClient.setQueryData(['scheduledWorkflow', data.id], data);
      queryClient.invalidateQueries({ queryKey: ['schedulerJobs'] });
    },
  });

  // Delete scheduled workflow
  const deleteScheduledWorkflow = useMutation({
    mutationFn: (scheduledWorkflowId: string) =>
      apiClient.scheduledWorkflows.delete(scheduledWorkflowId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduledWorkflows'] });
      queryClient.invalidateQueries({ queryKey: ['schedulerJobs'] });
    },
  });

  return {
    // Data
    scheduledWorkflows,
    schedulerStatus,
    schedulerJobs,
    // Loading states
    isLoadingScheduledWorkflows,
    isLoadingSchedulerStatus,
    isLoadingSchedulerJobs,
    // Error states
    scheduledWorkflowsError,
    schedulerStatusError,
    schedulerJobsError,
    // Hooks
    useGetScheduledWorkflowDetails,
    // Mutations
    createScheduledWorkflow,
    updateScheduledWorkflow,
    triggerExecution,
    pauseScheduledWorkflow,
    resumeScheduledWorkflow,
    deleteScheduledWorkflow,
  };
};

export default useScheduler;
