/**
 * T-FE-RUN-1: Run 创建失败则不执行（前端 fail-closed）
 *
 * 目标：
 * - Run 创建失败时，不应触发 execute/stream 调用
 * - 给出可操作的错误提示
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderWithProviders, screen, waitFor, userEvent } from '@/test/utils';

const mocks = vi.hoisted(() => ({
  updateWorkflow: vi.fn().mockResolvedValue({}),
  executeWorkflowStreaming: vi.fn(() => () => {}),
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

vi.mock('../../api/workflowsApi', () => ({
  updateWorkflow: mocks.updateWorkflow,
  executeWorkflowStreaming: mocks.executeWorkflowStreaming,
}));

describe('Workflow execution run_id fail-closed', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.clearAllMocks();
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

    await user.click(screen.getByRole('button', { name: /Run/ }));

    await waitFor(() => {
      expect(mocks.executeWorkflowStreaming).not.toHaveBeenCalled();
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/projects/proj_1/workflows/wf_test_123/runs'),
        expect.objectContaining({ method: 'POST' })
      );
      expect(screen.getByText('无法创建 Run，请稍后重试')).toBeInTheDocument();
    });
  }, 15000);
});
