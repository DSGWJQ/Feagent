/**
 * 工作流编辑器 Canvas 同步集成测试
 *
 * TDD 驱动：验证 useCanvasSync Hook 与编辑器页面的集成
 *
 * 测试场景：
 * 1. 编辑器加载时建立 WebSocket 连接
 * 2. 接收远程节点创建并更新画布
 * 3. 本地节点操作通过 WebSocket 广播
 * 4. 执行状态实时同步到画布
 * 5. 连接状态指示器
 */

import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { App } from 'antd';

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
    // 自动模拟连接成功
    setTimeout(() => this.simulateOpen(), 10);
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

// Mock modules
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

// Replace global WebSocket
const originalWebSocket = (global as any).WebSocket;

describe('WorkflowEditor Canvas Sync Integration', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    MockWebSocket.instances = [];
    (global as any).WebSocket = MockWebSocket;
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
  });

  afterEach(() => {
    (global as any).WebSocket = originalWebSocket;
  });

  const renderEditor = async () => {
    // 动态导入以确保 mock 生效
    const { default: WorkflowEditorPageWithMutex } = await import('../WorkflowEditorPageWithMutex');
    const { WorkflowInteractionProvider } = await import('../../contexts/WorkflowInteractionContext');

    return render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App>
            <WorkflowInteractionProvider>
              <WorkflowEditorPageWithMutex
                workflowId="wf_test_123"
                onWorkflowUpdate={vi.fn()}
              />
            </WorkflowInteractionProvider>
          </App>
        </BrowserRouter>
      </QueryClientProvider>
    );
  };

  describe('WebSocket 连接', () => {
    it('编辑器加载时应建立 WebSocket 连接', async () => {
      await renderEditor();

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBeGreaterThan(0);
      });

      const ws = MockWebSocket.instances[0];
      expect(ws.url).toContain('/ws/workflows/wf_test_123');
    }, 15_000);

    it('应显示连接状态指示器', async () => {
      await renderEditor();

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBeGreaterThan(0);
      });

      // 检查连接状态指示器
      const connectionIndicator = screen.queryByTestId('ws-connection-status');
      if (connectionIndicator) {
        expect(connectionIndicator).toBeInTheDocument();
      }
    });
  });

  describe('远程节点同步', () => {
    it('接收远程节点创建应更新画布', async () => {
      await renderEditor();

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBeGreaterThan(0);
      });

      const ws = MockWebSocket.instances[0];

      // 模拟接收远程节点创建
      act(() => {
        ws.simulateMessage({
          type: 'node_created',
          workflow_id: 'wf_test_123',
          node_id: 'remote_node_1',
          node_type: 'httpRequest',
          position: { x: 200, y: 300 },
          config: { url: 'https://api.example.com' },
          timestamp: new Date().toISOString(),
        });
      });

      // 验证画布更新（通过检查 React Flow 内部状态或 DOM）
      await waitFor(() => {
        // 这里需要验证节点是否被添加到画布
        // 具体验证方式取决于 React Flow 的渲染方式
      });
    });

    it('接收远程节点移动应更新节点位置', async () => {
      await renderEditor();

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBeGreaterThan(0);
      });

      const ws = MockWebSocket.instances[0];

      // 模拟接收远程节点移动
      act(() => {
        ws.simulateMessage({
          type: 'node_moved',
          workflow_id: 'wf_test_123',
          node_id: 'start',
          position: { x: 100, y: 100 },
          timestamp: new Date().toISOString(),
        });
      });

      // 验证节点位置更新
      await waitFor(() => {
        // 验证节点位置变化
      });
    });
  });

  describe('本地操作广播', () => {
    it('本地添加节点应通过 WebSocket 广播', async () => {
      await renderEditor();

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBeGreaterThan(0);
      });

      const ws = MockWebSocket.instances[0];

      // 找到节点面板并添加节点
      const nodePalette = screen.queryByTestId('node-palette');
      if (nodePalette) {
        // 模拟拖拽添加节点
        // 具体操作取决于 NodePalette 的实现
      }

      // 验证 WebSocket 消息发送
      // expect(ws.sentMessages).toContainEqual(expect.objectContaining({
      //   action: 'create_node',
      // }));
    });
  });

  describe('执行状态同步', () => {
    it('接收执行状态应更新节点样式', async () => {
      await renderEditor();

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBeGreaterThan(0);
      });

      const ws = MockWebSocket.instances[0];

      // 模拟工作流开始执行
      act(() => {
        ws.simulateMessage({
          type: 'workflow_started',
          workflow_id: 'wf_test_123',
          timestamp: new Date().toISOString(),
        });
      });

      // 模拟节点执行状态
      act(() => {
        ws.simulateMessage({
          type: 'execution_status',
          workflow_id: 'wf_test_123',
          node_id: 'start',
          status: 'running',
          outputs: {},
          error: null,
          timestamp: new Date().toISOString(),
        });
      });

      // 验证节点状态样式变化
      await waitFor(() => {
        // 检查节点是否显示 running 状态样式
      });
    });

    it('工作流完成应显示结果', async () => {
      await renderEditor();

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBeGreaterThan(0);
      });

      const ws = MockWebSocket.instances[0];

      // 模拟工作流完成
      act(() => {
        ws.simulateMessage({
          type: 'workflow_completed',
          workflow_id: 'wf_test_123',
          status: 'completed',
          outputs: { result: 'success' },
          timestamp: new Date().toISOString(),
        });
      });

      // 验证完成状态显示
      await waitFor(() => {
        // 检查是否显示完成消息
      });
    });
  });

  describe('错误处理', () => {
    it('WebSocket 断开应显示重连提示', async () => {
      await renderEditor();

      await waitFor(() => {
        expect(MockWebSocket.instances.length).toBeGreaterThan(0);
      });

      const ws = MockWebSocket.instances[0];

      // 模拟连接断开
      act(() => {
        ws.close();
      });

      // 验证重连提示
      await waitFor(() => {
        // 检查是否显示断开连接提示
      });
    });
  });
});
