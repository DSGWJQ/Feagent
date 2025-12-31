import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import type { Workflow } from '@/features/workflows/types/workflow';
import { useWorkflowAI } from '../useWorkflowAI';

const hoisted = vi.hoisted(() => ({
  mockChatWorkflowStreaming: vi.fn(),
  mockHandleError: vi.fn((error: unknown) =>
    error instanceof Error ? error.message : 'unknown error'
  ),
}));

vi.mock('@/services/api', () => ({
  apiClient: {
    handleError: hoisted.mockHandleError,
  },
}));

vi.mock('@/features/workflows/api/workflowsApi', () => ({
  chatWorkflowStreaming: (...args: unknown[]) => hoisted.mockChatWorkflowStreaming(...args),
}));

describe('useWorkflowAI', () => {
  const workflowId = 'wf_test';
  const baseWorkflow: Workflow = {
    id: workflowId,
    name: '测试工作流',
    description: '',
    status: 'draft',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    nodes: [],
    edges: [],
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should stream chat events and store pending workflow', async () => {
    hoisted.mockChatWorkflowStreaming.mockImplementation(
      (
        _workflowId: string,
        _request: { message: string },
        onEvent: (evt: any) => void
      ) => {
        const previewWorkflow = {
          ...baseWorkflow,
          nodes: [{ id: 'node-1', type: 'http', data: {}, position: { x: 0, y: 0 } }],
        };
        onEvent({ type: 'thinking', content: 'thinking...' });
        onEvent({
          type: 'patch',
          content: 'preview',
          metadata: {
            workflow: {
              ...previewWorkflow,
            },
          },
        });
        onEvent({
          type: 'final',
          content: 'done',
          is_final: true,
          metadata: { workflow: previewWorkflow },
        });
        return () => {};
      }
    );

    const { result } = renderHook(() =>
      useWorkflowAI({
        workflowId,
      })
    );

    await act(async () => {
      await result.current.startChatStream('添加一个HTTP节点');
    });

    expect(hoisted.mockChatWorkflowStreaming).toHaveBeenCalled();
    expect(result.current.pendingWorkflow?.nodes).toHaveLength(1);
  });

  it('should allow confirming pending workflow and clear it', async () => {
    const pending = {
      ...baseWorkflow,
      nodes: [{ id: 'node-new', type: 'end', data: {}, position: { x: 10, y: 10 } }],
    };

    hoisted.mockChatWorkflowStreaming.mockImplementation(
      (_workflowId: string, _request: { message: string }, onEvent: (evt: any) => void) => {
        onEvent({ type: 'final', content: 'done', is_final: true, metadata: { workflow: pending } });
        return () => {};
      }
    );

    const onApply = vi.fn();
    const { result } = renderHook(() =>
      useWorkflowAI({
        workflowId,
        onApplyWorkflow: onApply,
      })
    );

    await act(async () => {
      await result.current.sendMessage('添加节点');
    });

    expect(result.current.pendingWorkflow).not.toBeNull();

    await act(async () => {
      await result.current.confirmPendingWorkflow();
    });

    expect(onApply).toHaveBeenCalledWith(pending);
    expect(result.current.pendingWorkflow).toBeNull();
  });
});
