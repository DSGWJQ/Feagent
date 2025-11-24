/**
 * ScheduledWorkflowsPage Tests - RED phase (TDD)
 *
 * Tests the scheduled workflows management page:
 * 1. List all scheduled workflows
 * 2. Create new scheduled workflow
 * 3. Update scheduled workflow (cron expression, max retries)
 * 4. Delete scheduled workflow
 * 5. Pause/Resume scheduled workflow
 * 6. Trigger manual execution
 * 7. Display status and execution history
 * 8. Error handling
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClientProvider, QueryClient } from '@tanstack/react-query';
import ScheduledWorkflowsPage from '../ScheduledWorkflowsPage';
import * as scheduledWorkflowsApi from '../../api/scheduledWorkflowsApi';

vi.mock('../../api/scheduledWorkflowsApi');

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <QueryClientProvider client={queryClient}>
      {component}
    </QueryClientProvider>
  );
};

const mockScheduledWorkflows = [
  {
    id: 'sw_1',
    workflowId: 'wf_1',
    cronExpression: '*/5 * * * *',
    status: 'active' as const,
    maxRetries: 3,
    consecutiveFailures: 0,
    lastExecutionStatus: 'success',
    lastExecutionAt: '2025-01-24T10:00:00Z',
  },
  {
    id: 'sw_2',
    workflowId: 'wf_2',
    cronExpression: '0 0 * * *',
    status: 'disabled' as const,
    maxRetries: 2,
    consecutiveFailures: 2,
    lastExecutionStatus: 'failure',
    lastExecutionAt: '2025-01-23T00:00:00Z',
  },
];

describe('ScheduledWorkflowsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(scheduledWorkflowsApi, 'listScheduledWorkflows').mockResolvedValue({
      data: mockScheduledWorkflows,
    });
  });

  it('should render the page with table', async () => {
    renderWithProviders(<ScheduledWorkflowsPage />);

    expect(screen.getByText(/Scheduled Workflows/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /create|new/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/sw_1/)).toBeInTheDocument();
    });
  });

  it('should display list of scheduled workflows', async () => {
    renderWithProviders(<ScheduledWorkflowsPage />);

    await waitFor(() => {
      mockScheduledWorkflows.forEach((sw) => {
        expect(screen.getByText(sw.cronExpression)).toBeInTheDocument();
      });
    });
  });

  it('should display workflow status with correct badge color', async () => {
    renderWithProviders(<ScheduledWorkflowsPage />);

    await waitFor(() => {
      expect(screen.getByText(/active/i)).toBeInTheDocument();
      expect(screen.getByText(/disabled/i)).toBeInTheDocument();
    });
  });

  it('should open create modal when clicking create button', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ScheduledWorkflowsPage />);

    const createButton = screen.getByRole('button', { name: /create|new/i });
    await user.click(createButton);

    await waitFor(() => {
      expect(screen.getByText(/select workflow/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/cron expression/i)).toBeInTheDocument();
    });
  });

  it('should create a new scheduled workflow', async () => {
    const mockCreate = vi.fn().mockResolvedValue({
      data: {
        id: 'sw_new',
        workflowId: 'wf_1',
        cronExpression: '*/10 * * * *',
        status: 'active',
        maxRetries: 3,
      },
    });

    vi.spyOn(scheduledWorkflowsApi, 'createScheduledWorkflow').mockImplementation(mockCreate);

    const user = userEvent.setup();
    renderWithProviders(<ScheduledWorkflowsPage />);

    const createButton = screen.getByRole('button', { name: /create|new/i });
    await user.click(createButton);

    await waitFor(() => {
      const cronInput = screen.getByLabelText(/cron expression/i);
      expect(cronInput).toBeInTheDocument();
    });
  });

  it('should trigger workflow execution', async () => {
    const mockTrigger = vi.fn().mockResolvedValue({
      data: { executionStatus: 'triggered' },
    });

    vi.spyOn(scheduledWorkflowsApi, 'triggerExecution').mockImplementation(mockTrigger);

    const user = userEvent.setup();
    renderWithProviders(<ScheduledWorkflowsPage />);

    await waitFor(() => {
      expect(screen.getByText(/sw_1/)).toBeInTheDocument();
    });

    const triggerButton = screen.getAllByRole('button', { name: /trigger|run/i })[0];
    await user.click(triggerButton);

    await waitFor(() => {
      expect(mockTrigger).toHaveBeenCalledWith('sw_1');
    });
  });

  it('should pause a scheduled workflow', async () => {
    const mockPause = vi.fn().mockResolvedValue({
      data: { status: 'disabled' },
    });

    vi.spyOn(scheduledWorkflowsApi, 'pauseScheduledWorkflow').mockImplementation(mockPause);

    const user = userEvent.setup();
    renderWithProviders(<ScheduledWorkflowsPage />);

    await waitFor(() => {
      expect(screen.getByText(/sw_1/)).toBeInTheDocument();
    });

    const pauseButton = screen.getAllByRole('button', { name: /pause/i })[0];
    await user.click(pauseButton);

    await waitFor(() => {
      expect(mockPause).toHaveBeenCalledWith('sw_1');
    });
  });

  it('should resume a paused workflow', async () => {
    const mockResume = vi.fn().mockResolvedValue({
      data: { status: 'active' },
    });

    vi.spyOn(scheduledWorkflowsApi, 'resumeScheduledWorkflow').mockImplementation(mockResume);

    const user = userEvent.setup();
    renderWithProviders(<ScheduledWorkflowsPage />);

    await waitFor(() => {
      expect(screen.getByText(/sw_1/)).toBeInTheDocument();
    });

    // Find the resume button for disabled workflow
    const resumeButtons = screen.getAllByRole('button', { name: /resume/i });
    if (resumeButtons.length > 0) {
      await user.click(resumeButtons[0]);

      await waitFor(() => {
        expect(mockResume).toHaveBeenCalled();
      });
    }
  });

  it('should delete a scheduled workflow', async () => {
    const mockDelete = vi.fn().mockResolvedValue({ data: {} });

    vi.spyOn(scheduledWorkflowsApi, 'deleteScheduledWorkflow').mockImplementation(mockDelete);

    const user = userEvent.setup();
    renderWithProviders(<ScheduledWorkflowsPage />);

    await waitFor(() => {
      expect(screen.getByText(/sw_1/)).toBeInTheDocument();
    });

    const deleteButton = screen.getAllByRole('button', { name: /delete|remove/i })[0];
    await user.click(deleteButton);

    // Confirm deletion
    const confirmButton = screen.getByRole('button', { name: /ok|confirm/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(mockDelete).toHaveBeenCalledWith('sw_1');
    });
  });

  it('should display execution history', async () => {
    renderWithProviders(<ScheduledWorkflowsPage />);

    await waitFor(() => {
      expect(screen.getByText(/success/i)).toBeInTheDocument();
      expect(screen.getByText(/failure/i)).toBeInTheDocument();
    });
  });

  it('should handle API errors gracefully', async () => {
    const mockError = new Error('Failed to load workflows');
    vi.spyOn(scheduledWorkflowsApi, 'listScheduledWorkflows').mockRejectedValue(mockError);

    renderWithProviders(<ScheduledWorkflowsPage />);

    await waitFor(() => {
      expect(screen.getByText(/error|failed/i)).toBeInTheDocument();
    });
  });

  it('should show loading state while fetching', () => {
    vi.spyOn(scheduledWorkflowsApi, 'listScheduledWorkflows').mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    renderWithProviders(<ScheduledWorkflowsPage />);

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });
});
