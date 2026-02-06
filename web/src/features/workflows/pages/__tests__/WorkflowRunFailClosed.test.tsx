/**
 * T-FE-RUN-1: Run 创建失败则不执行（前端 fail-closed）
 *
 * 目标：
 * - Run 创建失败时，不应触发 execute/stream 调用
 * - 给出可操作的错误提示
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderWithProviders, screen, waitFor, userEvent } from '@/test/utils';

const DEFAULT_CAPABILITIES = {
  schema_version: 'test',
  constraints: {
    sqlite_only: true,
    sqlite_database_url_prefix: 'sqlite:///',
    model_providers_supported: ['openai'],
    openai_only: true,
    run_persistence_enabled: true,
    execute_stream_requires_run_id: true,
    draft_validation_scope: 'main_subgraph_only',
  },
  node_types: [],
};

const mocks = vi.hoisted(() => ({
  updateWorkflow: vi.fn(),
  executeWorkflowStreaming: vi.fn(),
  confirmRunSideEffect: vi.fn(),
  getWorkflowCapabilities: vi.fn(),
}));

vi.mock('@/hooks/useWorkflow', () => ({
  useWorkflow: vi.fn(() => ({
    workflowData: {
      id: 'wf_test_123',
      name: 'Test Workflow',
      nodes: [
        { id: 'start', type: 'start', position: { x: 50, y: 250 }, data: {} },
        { id: 'end', type: 'end', position: { x: 350, y: 250 }, data: {} },
      ],
      edges: [{ id: 'e1', source: 'start', target: 'end' }],
    },
    isLoadingWorkflow: false,
    workflowError: null,
    refetchWorkflow: vi.fn(),
  })),
}));

vi.mock('@/features/workflows/api/workflowsApi', () => ({
  updateWorkflow: mocks.updateWorkflow,
  executeWorkflowStreaming: mocks.executeWorkflowStreaming,
  confirmRunSideEffect: mocks.confirmRunSideEffect,
  getWorkflowCapabilities: mocks.getWorkflowCapabilities,
}));

describe('Workflow execution run_id fail-closed', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.clearAllMocks();
    mocks.updateWorkflow.mockResolvedValue({});
    mocks.executeWorkflowStreaming.mockImplementation(() => () => {});
    mocks.confirmRunSideEffect.mockResolvedValue({ ok: true });
    mocks.getWorkflowCapabilities.mockResolvedValue(DEFAULT_CAPABILITIES);
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('does not call execute when run creation fails', async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      if (url.includes('/projects/proj_1/workflows/wf_test_123/runs')) {
        return {
          ok: false,
          status: 500,
          json: async () => ({ detail: 'run create failed' }),
        } as any;
      }
      throw new Error(`unexpected fetch: ${url}`);
    }) as any;

    const user = userEvent.setup();

    const { default: WorkflowEditorPageWithMutex } = await import('../WorkflowEditorPageWithMutex');

    renderWithProviders(<WorkflowEditorPageWithMutex workflowId="wf_test_123" onWorkflowUpdate={vi.fn()} />, {
      initialEntries: ['/workflows/wf_test_123/edit?projectId=proj_1'],
    });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Run/ })).toBeEnabled();
    });

    await user.click(screen.getByRole('button', { name: /Run/ }));

    await waitFor(() => {
      expect(mocks.executeWorkflowStreaming).not.toHaveBeenCalled();
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj_1/workflows/wf_test_123/runs'),
        expect.objectContaining({ method: 'POST' })
      );
      expect(screen.getByText('无法创建 Run，请稍后重试')).toBeInTheDocument();
    });
  }, 30000);

  it('does not call execute when projectId is missing and Runs are enabled', async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      throw new Error(`unexpected fetch: ${url}`);
    }) as any;

    const user = userEvent.setup();

    const { default: WorkflowEditorPageWithMutex } = await import('../WorkflowEditorPageWithMutex');

    renderWithProviders(<WorkflowEditorPageWithMutex workflowId="wf_test_123" onWorkflowUpdate={vi.fn()} />, {
      initialEntries: ['/workflows/wf_test_123/edit'],
    });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Run/ })).toBeEnabled();
    });

    await user.click(screen.getByRole('button', { name: /Run/ }));

    await waitFor(() => {
      expect(mocks.executeWorkflowStreaming).not.toHaveBeenCalled();
      expect(globalThis.fetch).not.toHaveBeenCalled();
      expect(screen.getByText('缺少 projectId，无法创建 Run，无法执行')).toBeInTheDocument();
    });
  }, 30000);

  it('allows legacy execute without run_id when Runs are disabled', async () => {
    mocks.getWorkflowCapabilities.mockResolvedValueOnce({
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
    });

    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      throw new Error(`unexpected fetch: ${url}`);
    }) as any;

    const user = userEvent.setup();

    const { default: WorkflowEditorPageWithMutex } = await import('../WorkflowEditorPageWithMutex');

    renderWithProviders(<WorkflowEditorPageWithMutex workflowId="wf_test_123" onWorkflowUpdate={vi.fn()} />, {
      initialEntries: ['/workflows/wf_test_123/edit'],
    });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Run/ })).toBeEnabled();
    });

    await user.click(screen.getByRole('button', { name: /Run/ }));

    await waitFor(() => {
      expect(globalThis.fetch).not.toHaveBeenCalled();
      expect(mocks.executeWorkflowStreaming).toHaveBeenCalled();
      expect(mocks.executeWorkflowStreaming.mock.calls[0]?.[1]).toMatchObject({
        initial_input: expect.anything(),
      });
      // Fail-closed: should not attach run_id in legacy mode.
      expect(mocks.executeWorkflowStreaming.mock.calls[0]?.[1]).not.toMatchObject({
        run_id: expect.any(String),
      });
    });
  }, 30000);
});
