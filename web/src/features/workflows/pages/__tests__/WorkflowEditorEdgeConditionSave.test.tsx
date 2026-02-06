import { render, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { App } from 'antd';

const updateWorkflowMock = vi.fn().mockResolvedValue({});

vi.mock('@/hooks/useWorkflow', () => ({
  useWorkflow: vi.fn(() => ({
    workflowData: {
      id: 'wf_test_123',
      name: 'Test Workflow',
      nodes: [
        { id: 'start', type: 'start', position: { x: 50, y: 250 }, data: {} },
        { id: 'end', type: 'end', position: { x: 350, y: 250 }, data: {} },
      ],
      edges: [{ id: 'e1', source: 'start', target: 'end', condition: 'score > 0.8' }],
    },
    isLoadingWorkflow: false,
    workflowError: null,
    refetchWorkflow: vi.fn(),
  })),
}));

vi.mock('../../api/workflowsApi', () => ({
  updateWorkflow: updateWorkflowMock,
  executeWorkflowStreaming: vi.fn(() => () => {}),
  confirmRunSideEffect: vi.fn().mockResolvedValue({ ok: true }),
  getWorkflowCapabilities: vi.fn().mockResolvedValue({
    schema_version: 'test',
    constraints: {
      sqlite_only: true,
      sqlite_database_url_prefix: 'sqlite:///',
      model_providers_supported: ['openai'],
      openai_only: true,
      run_persistence_enabled: false,
      execute_stream_requires_run_id: false,
      draft_validation_scope: 'main_subgraph_only',
    },
    node_types: [],
  }),
}));

describe('Workflow editor edge.condition persistence', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('includes edge.condition in updateWorkflow payload on save', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    const { default: WorkflowEditorPageWithMutex } = await import('../WorkflowEditorPageWithMutex');
    const { WorkflowInteractionProvider } = await import('../../contexts/WorkflowInteractionContext');

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App>
            <WorkflowInteractionProvider>
              <WorkflowEditorPageWithMutex workflowId="wf_test_123" onWorkflowUpdate={vi.fn()} />
            </WorkflowInteractionProvider>
          </App>
        </BrowserRouter>
      </QueryClientProvider>
    );

    fireEvent.click(document.querySelector('[data-testid="workflow-save-button"]') as Element);

    await waitFor(() => {
      expect(updateWorkflowMock).toHaveBeenCalledTimes(1);
    });

    const [, payload] = updateWorkflowMock.mock.calls[0];
    expect(payload.edges).toHaveLength(1);
    expect(payload.edges[0].condition).toBe('score > 0.8');
  }, 30000);
});
