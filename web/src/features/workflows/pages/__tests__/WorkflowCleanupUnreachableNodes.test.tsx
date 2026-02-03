/**
 * T-FE-CLEAN-1: 清理未连通节点（start->end 主连通子图之外的节点）
 *
 * 目标：
 * - 点击“清理未连通节点”后，应删除孤立节点及相关边，并立即保存
 * - Fail-closed：不依赖后端跑起来即可验证前端行为（mock updateWorkflow）
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderWithProviders, screen, waitFor, userEvent } from '@/test/utils';

const DEFAULT_CAPABILITIES = {
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
        //孤立节点：不在 start->end 主连通子图
        { id: 'isolated', type: 'httpRequest', position: { x: 200, y: 80 }, data: {} },
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

describe('Workflow cleanup unreachable nodes', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.updateWorkflow.mockResolvedValue({});
    mocks.executeWorkflowStreaming.mockImplementation(() => () => {});
    mocks.confirmRunSideEffect.mockResolvedValue({ ok: true });
    mocks.getWorkflowCapabilities.mockResolvedValue(DEFAULT_CAPABILITIES);
  });

  it('removes unreachable nodes and saves cleaned graph', async () => {
    const user = userEvent.setup();

    const { default: WorkflowEditorPageWithMutex } = await import('../WorkflowEditorPageWithMutex');

    renderWithProviders(
      <WorkflowEditorPageWithMutex workflowId="wf_test_123" onWorkflowUpdate={vi.fn()} />,
      { initialEntries: ['/workflows/wf_test_123/edit'] }
    );

    await waitFor(() => {
      expect(screen.getByTestId('workflow-clean-unreachable-button')).toBeEnabled();
    });

    await user.click(screen.getByTestId('workflow-clean-unreachable-button'));

    await waitFor(() => {
      expect(mocks.updateWorkflow).toHaveBeenCalledTimes(1);
    });

    const [, payload] = mocks.updateWorkflow.mock.calls[0] as any;
    expect(payload.nodes).toHaveLength(2);
    expect(payload.nodes.map((n: any) => n.id)).not.toContain('isolated');
    expect(payload.edges).toHaveLength(1);
  });
});
