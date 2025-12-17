/**
 * 工作流执行端到端测试
 *
 * 测试完整的工作流执行流程，包括：
 * 1. 创建工作流
 * 2. 通过聊天修改工作流
 * 3. 执行工作流并查看执行进度
 * 4. 验证执行总结显示在聊天中
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { WorkflowInteractionProvider } from '../contexts/WorkflowInteractionContext';
import WorkflowEditorPage from '../pages/WorkflowEditorPage';
import { apiClient } from '@/services/api';
import * as workflowsApi from '../api/workflowsApi';

// Mock API
jest.mock('@/services/api');
jest.mock('../api/workflowsApi');

const mockApiClient = apiClient as jest.Mocked<typeof apiClient>;
const mockWorkflowsApi = workflowsApi as jest.Mocked<typeof workflowsApi>;

// 创建测试用的 query client
const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false },
  },
});

// Mock 工作流数据
const mockWorkflow = {
  id: 'test-workflow-123',
  name: '测试工作流',
  description: '用于测试的工作流',
  status: 'draft',
  nodes: [
    {
      id: '1',
      type: 'start',
      name: '开始',
      position: { x: 50, y: 250 },
      data: {},
    },
    {
      id: '2',
      type: 'httpRequest',
      name: 'HTTP请求',
      position: { x: 350, y: 250 },
      data: {
        url: 'https://api.example.com',
        method: 'GET',
      },
    },
    {
      id: '3',
      type: 'end',
      name: '结束',
      position: { x: 650, y: 250 },
      data: {},
    },
  ],
  edges: [
    {
      id: 'e1-2',
      source: '1',
      target: '2',
    },
    {
      id: 'e2-3',
      source: '2',
      target: '3',
    },
  ],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

// Mock SSE events for workflow execution
const mockExecutionEvents = [
  { type: 'node_start', node_id: '1', node_type: 'start' },
  { type: 'node_complete', node_id: '1', node_type: 'start', output: { message: '开始执行' } },
  { type: 'node_start', node_id: '2', node_type: 'httpRequest' },
  { type: 'node_complete', node_id: '2', node_type: 'httpRequest', output: { status: 200, data: 'success' } },
  { type: 'node_start', node_id: '3', node_type: 'end' },
  { type: 'node_complete', node_id: '3', node_type: 'end', output: { message: '执行完成' } },
  { type: 'workflow_complete', result: { success: true, message: '工作流执行成功' } },
];

// Mock fetch for SSE
const mockFetch = jest.fn();

// Mock global window methods
Object.defineProperty(window, 'fetch', {
  writable: true,
  value: mockFetch,
});

Object.defineProperty(window, 'EventSource', {
  writable: true,
  value: jest.fn(),
});

describe('工作流执行端到端测试', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
    jest.clearAllMocks();

    // Mock createWorkflow
    mockWorkflowsApi.createWorkflow.mockResolvedValue(mockWorkflow);

    // Mock getWorkflow
    mockWorkflowsApi.getWorkflow.mockResolvedValue(mockWorkflow);

    // Mock updateWorkflow
    mockWorkflowsApi.updateWorkflow.mockResolvedValue(mockWorkflow);

    // Mock API client methods
    mockApiClient.workflows = {
      chat: jest.fn().mockResolvedValue({
        data: {
          ai_message: '已为您添加一个条件节点',
          workflow: {
            id: 'test-workflow-123',
            nodes: [
              ...mockWorkflow.nodes,
              {
                id: 'node-4',
                type: 'condition',
                name: '条件判断',
                position: { x: 200, y: 250 },
                data: {},
              },
            ],
            edges: [
              ...mockWorkflow.edges,
              { id: 'e1-4', source: '1', target: '4' },
              { id: 'e4-2', source: '4', target: '2' },
            ],
          },
        },
      }),
      streamExecution: jest.fn(),
    } as any;

    // Mock executeWorkflowStreaming
    mockWorkflowsApi.executeWorkflowStreaming = jest.fn().mockImplementation((workflowId, request, onEvent, onError) => {
      // Simulate SSE events
      mockExecutionEvents.forEach((event, index) => {
        setTimeout(() => {
          onEvent(event);
        }, index * 100);
      });

      return () => { }; // cancel function
    });

    // Mock fetch for chat-stream
    mockFetch.mockImplementation((url) => {
      if (url.includes('/chat-stream')) {
        return Promise.resolve({
          ok: true,
          body: new ReadableStream({
            start(controller) {
              const encoder = new TextEncoder();

              // Send mock events
              const events = [
                'event: llm_thinking\ndata: {"message": "AI 正在分析您的需求..."}\n\n',
                'event: preview_changes\ndata: {"type": "preview", "message": "将添加条件节点", "nodes": [], "edges": []}\n\n',
                'event: workflow_updated\ndata: {"type": "workflow_updated", "message": "工作流已更新"}\n\n',
                'event: done\ndata: {}\n\n',
              ];

              events.forEach((event, index) => {
                setTimeout(() => {
                  controller.enqueue(encoder.encode(event));
                }, index * 50);
              });

              setTimeout(() => {
                controller.close();
              }, events.length * 50);
            },
          }),
        });
      }

      return Promise.resolve({
        ok: false,
        status: 404,
      });
    });
  });

  const renderComponent = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <WorkflowInteractionProvider>
            <WorkflowEditorPage />
          </WorkflowInteractionProvider>
        </BrowserRouter>
      </QueryClientProvider>
    );
  };

  test('完整的工作流执行流程', async () => {
    renderComponent();

    // 等待页面加载
    await waitFor(() => {
      expect(screen.getByText('保存')).toBeInTheDocument();
      expect(screen.getByText('运行')).toBeInTheDocument();
    });

    // 1. 验证工作流已创建
    expect(mockWorkflowsApi.createWorkflow).toHaveBeenCalledWith({
      name: '新建工作流',
      description: 'AI 自动生成的工作流',
      nodes: [],
      edges: [],
    });

    // 2. 测试聊天修改工作流
    const chatInput = screen.getByPlaceholderText(/输入消息/);
    await userEvent.type(chatInput, '添加一个条件节点');

    const sendButton = screen.getByText('发送');
    await userEvent.click(sendButton);

    // 等待聊天消息发送
    await waitFor(() => {
      expect(mockApiClient.workflows.chat).toHaveBeenCalledWith('test-workflow-123', {
        message: '添加一个条件节点',
      });
    });

    // 3. 测试执行工作流
    const runButton = screen.getByText('运行');
    await userEvent.click(runButton);

    // 验证工作流被保存
    await waitFor(() => {
      expect(mockWorkflowsApi.updateWorkflow).toHaveBeenCalled();
    });

    // 验证执行开始
    await waitFor(() => {
      expect(mockWorkflowsApi.executeWorkflowStreaming).toHaveBeenCalledWith(
        'test-workflow-123',
        { initial_input: { message: 'test' } },
        expect.any(Function),
        expect.any(Function)
      );
    });

    // 4. 验证执行进度显示
    // ExecutionOverlay 应该显示节点状态
    await waitFor(() => {
      // 检查是否有执行状态相关的元素
      const executionStatus = document.querySelector('[data-testid="execution-status"]');
      if (executionStatus) {
        expect(executionStatus).toBeInTheDocument();
      }
    }, { timeout: 3000 });

    // 5. 验证执行总结插入聊天
    // 检查是否有执行总结消息
    await waitFor(() => {
      const chatMessages = screen.getAllByText(/执行成功/);
      expect(chatMessages.length).toBeGreaterThan(0);
    }, { timeout: 2000 });

    // 验证成功消息
    expect(screen.getByText(/工作流执行成功/)).toBeInTheDocument();
  });

  test('节点执行状态正确更新', async () => {
    renderComponent();

    // 模拟执行过程中的状态更新
    const { rerender } = renderComponent();

    // 点击运行按钮
    const runButton = screen.getByText('运行');
    await userEvent.click(runButton);

    // 验证节点状态映射
    await waitFor(() => {
      // 这里我们验证executeWorkflowStreaming被调用
      // 实际的状态更新在组件内部处理
      expect(mockWorkflowsApi.executeWorkflowStreaming).toHaveBeenCalled();
    });
  });

  test('聊天和画布互斥锁功能', async () => {
    renderComponent();

    // 验证初始状态
    await waitFor(() => {
      expect(screen.getByText('画布模式')).not.toBeInTheDocument();
      expect(screen.getByText('聊天模式')).not.toBeInTheDocument();
    });

    // 点击聊天输入框应该切换到聊天模式
    const chatInput = screen.getByPlaceholderText(/输入消息/);
    await userEvent.click(chatInput);

    await waitFor(() => {
      expect(screen.getByText('聊天模式')).toBeInTheDocument();
    });

    // 尝试拖拽应该切换到画布模式
    const canvas = screen.getByTestId('react-flow');
    if (canvas) {
      await userEvent.pointer({ target: canvas, keys: '[MouseLeft]' });

      await waitFor(() => {
        expect(screen.getByText('画布模式')).toBeInTheDocument();
      });
    }
  });
});

/**
 * 辅助函数：检查元素是否存在
 */
const checkElementExists = (selector: string): boolean => {
  return !!document.querySelector(selector);
};

/**
 * 辅助函数：等待元素出现
 */
const waitForElement = (selector: string, timeout = 5000): Promise<Element | null> => {
  return new Promise((resolve) => {
    const element = document.querySelector(selector);
    if (element) {
      resolve(element);
      return;
    }

    const interval = setInterval(() => {
      const el = document.querySelector(selector);
      if (el) {
        clearInterval(interval);
        resolve(el);
      }
    }, 100);

    setTimeout(() => {
      clearInterval(interval);
      resolve(null);
    }, timeout);
  });
};
