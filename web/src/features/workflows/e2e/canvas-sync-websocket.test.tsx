/**
 * WebSocket Canvas 同步端到端测试
 *
 * TDD 驱动：验证 WebSocket 集成的真实场景
 *
 * 测试场景：
 * 1. 连接 WebSocket 并接收初始状态
 * 2. 多客户端节点同步
 * 3. 执行状态实时更新
 * 4. 错误处理和重连
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { useCanvasSync } from '../hooks/useCanvasSync';
import type { WorkflowNode, WorkflowEdge } from '../types/workflow';

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

  simulateError() {
    if (this.onerror) {
      this.onerror(new Event('error'));
    }
  }
}

// Replace global WebSocket
const originalWebSocket = (global as any).WebSocket;

describe('WebSocket Canvas 同步端到端测试', () => {
  const workflowId = 'wf_e2e_test_123';

  beforeEach(() => {
    vi.clearAllMocks();
    MockWebSocket.instances = [];
    (global as any).WebSocket = MockWebSocket;
  });

  afterEach(() => {
    (global as any).WebSocket = originalWebSocket;
  });

  describe('场景1: 初始化同步', () => {
    it('客户端连接后应该接收到完整的画布状态', async () => {
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

      // 模拟服务器发送初始状态
      const initialState = {
        type: 'initial_state',
        workflow_id: workflowId,
        nodes: [
          { id: 'start', type: 'start', position: { x: 0, y: 0 }, data: {} },
          { id: 'llm', type: 'textModel', position: { x: 200, y: 0 }, data: { model: 'gpt-4' } },
          { id: 'end', type: 'end', position: { x: 400, y: 0 }, data: {} },
        ],
        edges: [
          { id: 'e1', source: 'start', target: 'llm' },
          { id: 'e2', source: 'llm', target: 'end' },
        ],
        timestamp: new Date().toISOString(),
      };

      act(() => {
        ws.simulateOpen();
        ws.simulateMessage(initialState);
      });

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
        expect(onNodesChange).toHaveBeenCalled();
        expect(onEdgesChange).toHaveBeenCalled();
      });

      // 验证节点变化包含所有初始节点
      const nodeChanges = onNodesChange.mock.calls[0][0];
      expect(nodeChanges.length).toBe(3);
      expect(nodeChanges.map((c: any) => c.item?.id)).toEqual(['start', 'llm', 'end']);
    });
  });

  describe('场景2: 多客户端协作', () => {
    it('客户端A创建节点，客户端B应该收到更新', async () => {
      // 客户端 A
      const onNodesChangeA = vi.fn();
      const { result: resultA } = renderHook(() =>
        useCanvasSync({
          workflowId,
          enabled: true,
          onNodesChange: onNodesChangeA,
        })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const wsA = MockWebSocket.instances[0];
      act(() => {
        wsA.simulateOpen();
      });

      // 客户端 A 创建节点
      const newNode: WorkflowNode = {
        id: 'new_node',
        type: 'httpRequest',
        position: { x: 300, y: 100 },
        data: { url: 'https://api.example.com' },
      };

      act(() => {
        resultA.current.createNode(newNode);
      });

      // 验证消息发送
      expect(wsA.sentMessages).toContainEqual({
        action: 'create_node',
        node: {
          id: 'new_node',
          type: 'httpRequest',
          position: { x: 300, y: 100 },
          config: { url: 'https://api.example.com' },
        },
      });

      // 模拟服务器广播给其他客户端
      const broadcastMessage = {
        type: 'node_created',
        workflow_id: workflowId,
        node_id: 'new_node',
        node_type: 'httpRequest',
        position: { x: 300, y: 100 },
        config: { url: 'https://api.example.com' },
        timestamp: new Date().toISOString(),
      };

      act(() => {
        wsA.simulateMessage(broadcastMessage);
      });

      await waitFor(() => {
        expect(onNodesChangeA).toHaveBeenCalled();
      });
    });

    it('节点移动应该广播给所有客户端', async () => {
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
      });

      // 移动节点
      act(() => {
        result.current.moveNode('node_1', { x: 500, y: 300 });
      });

      expect(ws.sentMessages).toContainEqual({
        action: 'move_node',
        node_id: 'node_1',
        position: { x: 500, y: 300 },
      });

      // 模拟服务器广播
      act(() => {
        ws.simulateMessage({
          type: 'node_moved',
          workflow_id: workflowId,
          node_id: 'node_1',
          position: { x: 500, y: 300 },
          timestamp: new Date().toISOString(),
        });
      });

      await waitFor(() => {
        expect(onNodesChange).toHaveBeenCalledWith(
          expect.arrayContaining([
            expect.objectContaining({
              type: 'position',
              id: 'node_1',
              position: { x: 500, y: 300 },
            }),
          ])
        );
      });
    });
  });

  describe('场景3: 执行状态同步', () => {
    it('工作流执行时应该实时更新节点状态', async () => {
      const onExecutionStatus = vi.fn();
      const onWorkflowStarted = vi.fn();
      const onWorkflowCompleted = vi.fn();

      const { result } = renderHook(() =>
        useCanvasSync({
          workflowId,
          enabled: true,
          onExecutionStatus,
          onWorkflowStarted,
          onWorkflowCompleted,
        })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];
      act(() => {
        ws.simulateOpen();
      });

      // 模拟执行流程
      act(() => {
        // 工作流开始
        ws.simulateMessage({
          type: 'workflow_started',
          workflow_id: workflowId,
          timestamp: new Date().toISOString(),
        });

        // 节点1 运行中
        ws.simulateMessage({
          type: 'execution_status',
          workflow_id: workflowId,
          node_id: 'start',
          status: 'running',
          outputs: {},
          error: null,
          timestamp: new Date().toISOString(),
        });
      });

      await waitFor(() => {
        expect(onWorkflowStarted).toHaveBeenCalled();
        expect(onExecutionStatus).toHaveBeenCalledWith({
          nodeId: 'start',
          status: 'running',
          outputs: {},
          error: null,
        });
      });

      // 模拟节点执行完成
      act(() => {
        ws.simulateMessage({
          type: 'execution_status',
          workflow_id: workflowId,
          node_id: 'start',
          status: 'completed',
          outputs: { result: 'success' },
          error: null,
          timestamp: new Date().toISOString(),
        });

        // 工作流完成
        ws.simulateMessage({
          type: 'workflow_completed',
          workflow_id: workflowId,
          status: 'completed',
          outputs: { final: 'result' },
          timestamp: new Date().toISOString(),
        });
      });

      await waitFor(() => {
        expect(onWorkflowCompleted).toHaveBeenCalledWith({
          status: 'completed',
          outputs: { final: 'result' },
        });
      });
    });

    it('节点执行错误应该正确处理', async () => {
      const onExecutionStatus = vi.fn();
      const onError = vi.fn();

      const { result } = renderHook(() =>
        useCanvasSync({
          workflowId,
          enabled: true,
          onExecutionStatus,
          onError,
        })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];
      act(() => {
        ws.simulateOpen();
      });

      // 模拟节点执行错误
      act(() => {
        ws.simulateMessage({
          type: 'execution_status',
          workflow_id: workflowId,
          node_id: 'http_node',
          status: 'error',
          outputs: {},
          error: 'Connection timeout',
          timestamp: new Date().toISOString(),
        });
      });

      await waitFor(() => {
        expect(onExecutionStatus).toHaveBeenCalledWith({
          nodeId: 'http_node',
          status: 'error',
          outputs: {},
          error: 'Connection timeout',
        });
      });
    });
  });

  describe('场景4: 边操作同步', () => {
    it('创建边应该广播给所有客户端', async () => {
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
      });

      // 创建边
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

      // 模拟服务器广播
      act(() => {
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

    it('删除边应该广播给所有客户端', async () => {
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
      });

      // 删除边
      act(() => {
        result.current.deleteEdge('edge_to_delete');
      });

      expect(ws.sentMessages).toContainEqual({
        action: 'delete_edge',
        edge_id: 'edge_to_delete',
      });
    });
  });

  describe('场景5: 错误处理', () => {
    it('WebSocket 连接错误应该触发 onError', async () => {
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
        ws.simulateError();
      });

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith('WebSocket connection error');
      });
    });

    it('服务器错误消息应该更新 error 状态', async () => {
      const { result } = renderHook(() =>
        useCanvasSync({
          workflowId,
          enabled: true,
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
          message: 'Permission denied',
          timestamp: new Date().toISOString(),
        });
      });

      await waitFor(() => {
        expect(result.current.error).toBe('Permission denied');
      });
    });
  });

  describe('场景6: 完整工作流程', () => {
    it('创建工作流 -> 添加节点 -> 连接边 -> 执行 -> 查看结果', async () => {
      const onNodesChange = vi.fn();
      const onEdgesChange = vi.fn();
      const onExecutionStatus = vi.fn();
      const onWorkflowCompleted = vi.fn();

      const { result } = renderHook(() =>
        useCanvasSync({
          workflowId,
          enabled: true,
          onNodesChange,
          onEdgesChange,
          onExecutionStatus,
          onWorkflowCompleted,
        })
      );

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBe(1);
      });

      const ws = MockWebSocket.instances[0];

      // Step 1: 连接
      act(() => {
        ws.simulateOpen();
      });
      expect(result.current.isConnected).toBe(true);

      // Step 2: 接收初始状态
      act(() => {
        ws.simulateMessage({
          type: 'initial_state',
          workflow_id: workflowId,
          nodes: [
            { id: 'start', type: 'start', position: { x: 0, y: 0 }, data: {} },
          ],
          edges: [],
          timestamp: new Date().toISOString(),
        });
      });

      await waitFor(() => {
        expect(onNodesChange).toHaveBeenCalled();
      });

      // Step 3: 创建 LLM 节点
      const llmNode: WorkflowNode = {
        id: 'llm_1',
        type: 'textModel',
        position: { x: 200, y: 0 },
        data: { model: 'gpt-4', prompt: 'Hello' },
      };

      act(() => {
        result.current.createNode(llmNode);
      });

      expect(ws.sentMessages).toContainEqual({
        action: 'create_node',
        node: {
          id: 'llm_1',
          type: 'textModel',
          position: { x: 200, y: 0 },
          config: { model: 'gpt-4', prompt: 'Hello' },
        },
      });

      // Step 4: 创建边连接
      const edge: WorkflowEdge = {
        id: 'e_start_llm',
        source: 'start',
        target: 'llm_1',
      };

      act(() => {
        result.current.createEdge(edge);
      });

      expect(ws.sentMessages).toContainEqual({
        action: 'create_edge',
        edge: { id: 'e_start_llm', source: 'start', target: 'llm_1' },
      });

      // Step 5: 执行工作流
      act(() => {
        result.current.startExecution();
      });

      expect(ws.sentMessages).toContainEqual({
        action: 'start_execution',
      });

      // Step 6: 接收执行状态
      act(() => {
        ws.simulateMessage({
          type: 'workflow_started',
          workflow_id: workflowId,
          timestamp: new Date().toISOString(),
        });

        ws.simulateMessage({
          type: 'execution_status',
          workflow_id: workflowId,
          node_id: 'start',
          status: 'completed',
          outputs: { input: 'ready' },
          error: null,
          timestamp: new Date().toISOString(),
        });

        ws.simulateMessage({
          type: 'execution_status',
          workflow_id: workflowId,
          node_id: 'llm_1',
          status: 'completed',
          outputs: { response: 'Hello from GPT!' },
          error: null,
          timestamp: new Date().toISOString(),
        });

        ws.simulateMessage({
          type: 'workflow_completed',
          workflow_id: workflowId,
          status: 'completed',
          outputs: { final_response: 'Hello from GPT!' },
          timestamp: new Date().toISOString(),
        });
      });

      await waitFor(() => {
        expect(onExecutionStatus).toHaveBeenCalledTimes(2);
        expect(onWorkflowCompleted).toHaveBeenCalledWith({
          status: 'completed',
          outputs: { final_response: 'Hello from GPT!' },
        });
      });
    });
  });
});
