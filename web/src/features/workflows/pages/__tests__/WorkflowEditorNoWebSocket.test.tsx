/**
 * T-FE-WS-1: 前端不应创建 canvas sync WebSocket 连接。
 *
 * 目标：编辑器页面渲染时不应实例化 WebSocket（删掉旧的画布同步链路）。
 */

import { render } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { App } from 'antd';

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

vi.mock('../api/workflowsApi', () => ({
  updateWorkflow: vi.fn().mockResolvedValue({}),
  executeWorkflowStreaming: vi.fn(() => () => {}),
}));

describe('Workflow editor should not create WebSocket', () => {
  const originalWebSocket = (global as any).WebSocket;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    (global as any).WebSocket = originalWebSocket;
  });

  it('does not instantiate WebSocket on render', async () => {
    const webSocketCtor = vi.fn();
    (global as any).WebSocket = webSocketCtor;

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
      </QueryClientProvider>,
    );

    expect(webSocketCtor).not.toHaveBeenCalled();
  });
});
