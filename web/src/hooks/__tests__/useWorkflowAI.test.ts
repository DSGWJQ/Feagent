import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import type { Workflow } from '@/types/workflow';
import { useWorkflowAI } from '../useWorkflowAI';

const mockChat = vi.fn();
const mockStream = vi.fn();
const mockHandleError = vi.fn((error: unknown) =>
  error instanceof Error ? error.message : 'unknown error'
);

vi.mock('@/services/api', () => ({
  apiClient: {
    workflows: {
      chat: (...args: unknown[]) => mockChat(...args),
      streamExecution: (...args: unknown[]) => mockStream(...args),
    },
    handleError: mockHandleError,
  },
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
    mockStream.mockResolvedValue(undefined);
  });

  it('should send message, call chat API and store pending workflow', async () => {
    const chatResponse = {
      workflow: { ...baseWorkflow, nodes: [{ id: 'node-1', type: 'http', data: {}, position: { x: 0, y: 0 } }] },
      ai_message: '已添加节点',
    };
    mockChat.mockResolvedValue({ data: chatResponse });

    const { result } = renderHook(() =>
      useWorkflowAI({
        workflowId,
      })
    );

    await act(async () => {
      await result.current.sendMessage('添加一个HTTP节点');
    });

    expect(mockChat).toHaveBeenCalledWith(workflowId, { message: '添加一个HTTP节点' });

    expect(result.current.messages.map((m) => m.role)).toEqual(['user', 'assistant']);
    expect(result.current.pendingWorkflow?.nodes).toHaveLength(1);
    expect(result.current.isProcessing).toBe(false);
  });

  it('should stream execution events into chat messages', async () => {
    const chatResponse = {
      workflow: baseWorkflow,
      ai_message: '尝试执行',
    };
    mockChat.mockResolvedValue({ data: chatResponse });

    mockStream.mockImplementation(async (_workflowId: string, _payload: Record<string, unknown>, onEvent: (evt: any) => void) => {
      onEvent({ type: 'node_start', data: { node: 'start' } });
      onEvent({ type: 'workflow_complete', data: { result: 'ok' } });
    });

    const { result } = renderHook(() =>
      useWorkflowAI({
        workflowId,
      })
    );

    await act(async () => {
      await result.current.sendMessage('执行一下');
    });

    const assistantMessages = result.current.messages.filter((m) => m.role === 'assistant');

    expect(assistantMessages).toHaveLength(3); // AI 回复 + 2 条流式日志
    expect(assistantMessages[1].content).toContain('node_start');
    expect(assistantMessages[2].content).toContain('workflow_complete');
  });

  it('should allow confirming pending workflow and clear it', async () => {
    const chatResponse = {
      workflow: { ...baseWorkflow, nodes: [{ id: 'node-new', type: 'end', data: {}, position: { x: 10, y: 10 } }] },
      ai_message: 'done',
    };
    mockChat.mockResolvedValue({ data: chatResponse });

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

    expect(onApply).toHaveBeenCalledWith(chatResponse.workflow);
    expect(result.current.pendingWorkflow).toBeNull();
  });
});
