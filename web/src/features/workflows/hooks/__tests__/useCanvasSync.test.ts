/**
 * useCanvasSync Hook 测试
 *
 * TDD 驱动：先写测试定义期望行为
 *
 * 测试场景：
 * 1. WebSocket 连接建立
 * 2. 接收初始状态
 * 3. 节点同步（创建、更新、删除、移动）
 * 4. 边同步（创建、删除）
 * 5. 执行状态同步
 * 6. 错误处理
 * 7. 重连机制
 */

import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { useCanvasSync } from '../useCanvasSync';
import type { WorkflowNode, WorkflowEdge } from '../../types/workflow';

// Mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  url: string;
  readyState: number = MockWebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  sentMessages: any[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sentMessages.push(JSON.parse(data));
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }

  // Helper methods for testing
  simulateOpen() {
    this.readyState = MockWebSocket.OPEN;
    if (this.onopen) {
      this.onopen(new Event('open'));
    }
  }

  simulateMessage(data: any) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }));
    }
  }

  simulateError(error?: string) {
    if (this.onerror) {
      this.onerror(new Event('error'));
    }
  }

  simulateClose() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }
}

// Replace global WebSocket
const originalWebSocket = global.WebSocket;

describe('useCanvasSync', () => {
  const workflowId = 'wf_test_123';

  beforeEach(() => {
    vi.clearAllMocks();
    MockWebSocket.instances = [];
    (global as any).WebSocket = MockWebSocket;
  });

  afterEach(() => {
    (global as any).WebSocket = originalWebSocket;
  });

  describe('Connection', () => {
    it('should connect to WebSocket on mount', async () => {
      const { result } = renderHook(() =>
        useCanvasSync({ workflowId, enabled: true })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];
      expect(ws.url).toContain(`/ws/workflows/${workflowId}`);
    });

    it('should not connect when disabled', async () => {
      const { result } = renderHook(() =>
        useCanvasSync({ workflowId, enabled: false })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(0);
      });
    });

    it('should update connection status', async () => {
      const { result } = renderHook(() =>
        useCanvasSync({ workflowId, enabled: true })
      );

      // Initially connecting
      expect(result.current.isConnected).toBe(false);

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];

      // Simulate open
      act(() => {
        ws.simulateOpen();
      });

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });
    });

    it('should receive initial state on connect', async () => {
      const onNodesChange = vi.fn();
      const onEdgesChange = vi.fn();

      const { result } = renderHook(() =>
        useCanvasSync({
          workflowId,
          enabled: true,
          onNodesChange,
          onEdgesChange,
        })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];

      act(() => {
        ws.simulateOpen();
        ws.simulateMessage({
          type: 'initial_state',
          workflow_id: workflowId,
          nodes: [
            { id: 'node_1', type: 'llm', position: { x: 100, y: 200 }, data: {} },
          ],
          edges: [
            { id: 'edge_1', source: 'node_1', target: 'node_2' },
          ],
          timestamp: new Date().toISOString(),
        });
      });

      await waitFor(() => {
        expect(onNodesChange).toHaveBeenCalled();
        expect(onEdgesChange).toHaveBeenCalled();
      });
    });
  });

  describe('Node Synchronization', () => {
    it('should handle node_created event', async () => {
      const onNodesChange = vi.fn();

      const { result } = renderHook(() =>
        useCanvasSync({
          workflowId,
          enabled: true,
          onNodesChange,
        })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];

      act(() => {
        ws.simulateOpen();
        ws.simulateMessage({
          type: 'node_created',
          workflow_id: workflowId,
          node_id: 'node_new',
          node_type: 'http',
          position: { x: 150, y: 250 },
          config: { url: 'https://api.example.com' },
          timestamp: new Date().toISOString(),
        });
      });

      await waitFor(() => {
        expect(onNodesChange).toHaveBeenCalledWith(
          expect.arrayContaining([
            expect.objectContaining({
              type: 'add',
              item: expect.objectContaining({
                id: 'node_new',
                type: 'http',
              }),
            }),
          ])
        );
      });
    });

    it('should handle node_updated event', async () => {
      const onNodesChange = vi.fn();

      const { result } = renderHook(() =>
        useCanvasSync({
          workflowId,
          enabled: true,
          onNodesChange,
        })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];

      act(() => {
        ws.simulateOpen();
        ws.simulateMessage({
          type: 'node_updated',
          workflow_id: workflowId,
          node_id: 'node_1',
          changes: { config: { model: 'gpt-4-turbo' } },
          timestamp: new Date().toISOString(),
        });
      });

      await waitFor(() => {
        expect(onNodesChange).toHaveBeenCalled();
      });
    });

    it('should handle node_deleted event', async () => {
      const onNodesChange = vi.fn();

      const { result } = renderHook(() =>
        useCanvasSync({
          workflowId,
          enabled: true,
          onNodesChange,
        })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];

      act(() => {
        ws.simulateOpen();
        ws.simulateMessage({
          type: 'node_deleted',
          workflow_id: workflowId,
          node_id: 'node_to_delete',
          timestamp: new Date().toISOString(),
        });
      });

      await waitFor(() => {
        expect(onNodesChange).toHaveBeenCalledWith(
          expect.arrayContaining([
            expect.objectContaining({
              type: 'remove',
              id: 'node_to_delete',
            }),
          ])
        );
      });
    });

    it('should handle node_moved event', async () => {
      const onNodesChange = vi.fn();

      const { result } = renderHook(() =>
        useCanvasSync({
          workflowId,
          enabled: true,
          onNodesChange,
        })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];

      act(() => {
        ws.simulateOpen();
        ws.simulateMessage({
          type: 'node_moved',
          workflow_id: workflowId,
          node_id: 'node_1',
          position: { x: 300, y: 400 },
          timestamp: new Date().toISOString(),
        });
      });

      await waitFor(() => {
        expect(onNodesChange).toHaveBeenCalledWith(
          expect.arrayContaining([
            expect.objectContaining({
              type: 'position',
              id: 'node_1',
              position: { x: 300, y: 400 },
            }),
          ])
        );
      });
    });

    it('should send create_node action', async () => {
      const { result } = renderHook(() =>
        useCanvasSync({ workflowId, enabled: true })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];
      act(() => {
        ws.simulateOpen();
      });

      const newNode: WorkflowNode = {
        id: 'node_new',
        type: 'llm',
        position: { x: 100, y: 200 },
        data: { model: 'gpt-4' },
      };

      act(() => {
        result.current.createNode(newNode);
      });

      expect(ws.sentMessages).toContainEqual({
        action: 'create_node',
        node: {
          id: 'node_new',
          type: 'llm',
          position: { x: 100, y: 200 },
          config: { model: 'gpt-4' },
        },
      });
    });

    it('should send update_node action', async () => {
      const { result } = renderHook(() =>
        useCanvasSync({ workflowId, enabled: true })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];
      act(() => {
        ws.simulateOpen();
      });

      act(() => {
        result.current.updateNode('node_1', { config: { model: 'gpt-4-turbo' } });
      });

      expect(ws.sentMessages).toContainEqual({
        action: 'update_node',
        node_id: 'node_1',
        changes: { config: { model: 'gpt-4-turbo' } },
      });
    });

    it('should send delete_node action', async () => {
      const { result } = renderHook(() =>
        useCanvasSync({ workflowId, enabled: true })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];
      act(() => {
        ws.simulateOpen();
      });

      act(() => {
        result.current.deleteNode('node_to_delete');
      });

      expect(ws.sentMessages).toContainEqual({
        action: 'delete_node',
        node_id: 'node_to_delete',
      });
    });

    it('should send move_node action', async () => {
      const { result } = renderHook(() =>
        useCanvasSync({ workflowId, enabled: true })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];
      act(() => {
        ws.simulateOpen();
      });

      act(() => {
        result.current.moveNode('node_1', { x: 300, y: 400 });
      });

      expect(ws.sentMessages).toContainEqual({
        action: 'move_node',
        node_id: 'node_1',
        position: { x: 300, y: 400 },
      });
    });
  });

  describe('Edge Synchronization', () => {
    it('should handle edge_created event', async () => {
      const onEdgesChange = vi.fn();

      const { result } = renderHook(() =>
        useCanvasSync({
          workflowId,
          enabled: true,
          onEdgesChange,
        })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];

      act(() => {
        ws.simulateOpen();
        ws.simulateMessage({
          type: 'edge_created',
          workflow_id: workflowId,
          edge_id: 'edge_new',
          source_id: 'node_a',
          target_id: 'node_b',
          timestamp: new Date().toISOString(),
        });
      });

      await waitFor(() => {
        expect(onEdgesChange).toHaveBeenCalledWith(
          expect.arrayContaining([
            expect.objectContaining({
              type: 'add',
              item: expect.objectContaining({
                id: 'edge_new',
                source: 'node_a',
                target: 'node_b',
              }),
            }),
          ])
        );
      });
    });

    it('should handle edge_deleted event', async () => {
      const onEdgesChange = vi.fn();

      const { result } = renderHook(() =>
        useCanvasSync({
          workflowId,
          enabled: true,
          onEdgesChange,
        })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];

      act(() => {
        ws.simulateOpen();
        ws.simulateMessage({
          type: 'edge_deleted',
          workflow_id: workflowId,
          edge_id: 'edge_to_delete',
          timestamp: new Date().toISOString(),
        });
      });

      await waitFor(() => {
        expect(onEdgesChange).toHaveBeenCalledWith(
          expect.arrayContaining([
            expect.objectContaining({
              type: 'remove',
              id: 'edge_to_delete',
            }),
          ])
        );
      });
    });

    it('should send create_edge action', async () => {
      const { result } = renderHook(() =>
        useCanvasSync({ workflowId, enabled: true })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];
      act(() => {
        ws.simulateOpen();
      });

      const newEdge: WorkflowEdge = {
        id: 'edge_new',
        source: 'node_a',
        target: 'node_b',
      };

      act(() => {
        result.current.createEdge(newEdge);
      });

      expect(ws.sentMessages).toContainEqual({
        action: 'create_edge',
        edge: {
          id: 'edge_new',
          source: 'node_a',
          target: 'node_b',
        },
      });
    });

    it('should send delete_edge action', async () => {
      const { result } = renderHook(() =>
        useCanvasSync({ workflowId, enabled: true })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];
      act(() => {
        ws.simulateOpen();
      });

      act(() => {
        result.current.deleteEdge('edge_to_delete');
      });

      expect(ws.sentMessages).toContainEqual({
        action: 'delete_edge',
        edge_id: 'edge_to_delete',
      });
    });
  });

  describe('Execution Status', () => {
    it('should handle execution_status event', async () => {
      const onExecutionStatus = vi.fn();

      const { result } = renderHook(() =>
        useCanvasSync({
          workflowId,
          enabled: true,
          onExecutionStatus,
        })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];

      act(() => {
        ws.simulateOpen();
        ws.simulateMessage({
          type: 'execution_status',
          workflow_id: workflowId,
          node_id: 'node_1',
          status: 'running',
          outputs: {},
          error: null,
          timestamp: new Date().toISOString(),
        });
      });

      await waitFor(() => {
        expect(onExecutionStatus).toHaveBeenCalledWith({
          nodeId: 'node_1',
          status: 'running',
          outputs: {},
          error: null,
        });
      });
    });

    it('should handle workflow_started event', async () => {
      const onWorkflowStarted = vi.fn();

      const { result } = renderHook(() =>
        useCanvasSync({
          workflowId,
          enabled: true,
          onWorkflowStarted,
        })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];

      act(() => {
        ws.simulateOpen();
        ws.simulateMessage({
          type: 'workflow_started',
          workflow_id: workflowId,
          timestamp: new Date().toISOString(),
        });
      });

      await waitFor(() => {
        expect(onWorkflowStarted).toHaveBeenCalled();
      });
    });

    it('should handle workflow_completed event', async () => {
      const onWorkflowCompleted = vi.fn();

      const { result } = renderHook(() =>
        useCanvasSync({
          workflowId,
          enabled: true,
          onWorkflowCompleted,
        })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];

      act(() => {
        ws.simulateOpen();
        ws.simulateMessage({
          type: 'workflow_completed',
          workflow_id: workflowId,
          status: 'completed',
          outputs: { result: 'success' },
          timestamp: new Date().toISOString(),
        });
      });

      await waitFor(() => {
        expect(onWorkflowCompleted).toHaveBeenCalledWith({
          status: 'completed',
          outputs: { result: 'success' },
        });
      });
    });
  });

  describe('Error Handling', () => {
    it('should handle error events', async () => {
      const onError = vi.fn();

      const { result } = renderHook(() =>
        useCanvasSync({
          workflowId,
          enabled: true,
          onError,
        })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];

      act(() => {
        ws.simulateOpen();
        ws.simulateMessage({
          type: 'error',
          message: 'Something went wrong',
          timestamp: new Date().toISOString(),
        });
      });

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith('Something went wrong');
      });
    });

    it('should expose error state', async () => {
      const { result } = renderHook(() =>
        useCanvasSync({ workflowId, enabled: true })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];

      expect(result.current.error).toBeNull();

      act(() => {
        ws.simulateOpen();
        ws.simulateMessage({
          type: 'error',
          message: 'Connection error',
          timestamp: new Date().toISOString(),
        });
      });

      await waitFor(() => {
        expect(result.current.error).toBe('Connection error');
      });
    });
  });

  describe('Cleanup', () => {
    it('should close WebSocket on unmount', async () => {
      const { result, unmount } = renderHook(() =>
        useCanvasSync({ workflowId, enabled: true })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];
      act(() => {
        ws.simulateOpen();
      });

      expect(ws.readyState).toBe(MockWebSocket.OPEN);

      unmount();

      expect(ws.readyState).toBe(MockWebSocket.CLOSED);
    });

    it('should reconnect when workflowId changes', async () => {
      const { result, rerender } = renderHook(
        ({ workflowId }) => useCanvasSync({ workflowId, enabled: true }),
        { initialProps: { workflowId: 'wf_1' } }
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws1 = MockWebSocket.instances[0];
      act(() => {
        ws1.simulateOpen();
      });

      rerender({ workflowId: 'wf_2' });

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(2);
      });

      expect(ws1.readyState).toBe(MockWebSocket.CLOSED);
      expect(MockWebSocket.instances[1].url).toContain('wf_2');
    });
  });
});
