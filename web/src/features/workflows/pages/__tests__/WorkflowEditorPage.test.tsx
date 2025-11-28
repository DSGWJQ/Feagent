/**
 * WorkflowEditorPage 集成测试
 *
 * 测试工作流编辑器页面的布局和假AI聊天框集成
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { WorkflowEditorPage } from '../WorkflowEditorPage';

// Mock API
vi.mock('../../api/workflowsApi', () => ({
  updateWorkflow: vi.fn().mockResolvedValue({}),
}));

// Mock useWorkflowExecution hook
vi.mock('../../hooks/useWorkflowExecution', () => ({
  useWorkflowExecution: () => ({
    isExecuting: false,
    executionLog: [],
    error: null,
    currentNodeId: null,
    nodeStatusMap: {},
    nodeOutputMap: {},
    execute: vi.fn(),
  }),
}));

/**
 * 渲染带路由的组件
 */
function renderWithRouter(workflowId = '123') {
  return render(
    <MemoryRouter initialEntries={[`/workflows/${workflowId}/edit`]}>
      <Routes>
        <Route path="/workflows/:id/edit" element={<WorkflowEditorPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('WorkflowEditorPage - 布局和聊天框集成', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('页面布局测试', () => {
    it('应该渲染三栏布局：左侧调色板、中间画布、右侧聊天框', () => {
      renderWithRouter();

      // 左侧节点调色板
      expect(screen.getByText('Node Palette')).toBeInTheDocument();

      // 中间画布（React Flow）
      const canvas = document.querySelector('.react-flow');
      expect(canvas).toBeInTheDocument();

      // 右侧聊天框
      expect(screen.getByText('AI 助手')).toBeInTheDocument();
    });

    it('应该显示页面标题和工作流ID', () => {
      renderWithRouter('test-workflow-123');

      expect(screen.getByText(/工作流编辑器/i)).toBeInTheDocument();
      expect(screen.getByText(/test-workflow-123/i)).toBeInTheDocument();
    });

    it('应该显示工具栏按钮', () => {
      renderWithRouter();

      expect(screen.getByRole('button', { name: /保存/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /执行/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /导出代码/i })).toBeInTheDocument();
    });
  });

  describe('聊天框显示测试', () => {
    it('应该显示聊天框标题', () => {
      renderWithRouter();

      expect(screen.getByText('AI 助手')).toBeInTheDocument();
    });

    it('应该显示聊天框输入区域', () => {
      renderWithRouter();

      const input = screen.getByPlaceholderText(/输入消息/i);
      expect(input).toBeInTheDocument();
    });

    it('应该显示欢迎消息', () => {
      renderWithRouter();

      expect(
        screen.getByText(/你好！我是工作流AI助手/i)
      ).toBeInTheDocument();
    });
  });

  describe('聊天框交互测试', () => {
    it('应该能在聊天框中发送消息', async () => {
      const user = userEvent.setup();
      renderWithRouter();

      const input = screen.getByPlaceholderText(/输入消息/i);
      const sendButton = screen.getByRole('button', { name: /发送/i });

      // 发送消息
      await user.type(input, '你好');
      await user.click(sendButton);

      // 应该显示用户消息
      await waitFor(() => {
        expect(screen.getByText('你好')).toBeInTheDocument();
      });
    });

    it('应该在发送消息后收到AI回复', async () => {
      const user = userEvent.setup();
      renderWithRouter();

      const input = screen.getByPlaceholderText(/输入消息/i);
      const sendButton = screen.getByRole('button', { name: /发送/i });

      // 发送消息
      await user.type(input, '你好');
      await user.click(sendButton);

      // 等待AI回复
      await waitFor(
        () => {
          expect(screen.queryByText('正在输入...')).not.toBeInTheDocument();
        },
        { timeout: 3000 }
      );

      // 应该有AI回复
      const messages = screen.getAllByRole('article');
      expect(messages.length).toBeGreaterThanOrEqual(2); // 至少有用户消息和AI回复
    });
  });

  describe('聊天框折叠功能测试', () => {
    it('应该显示折叠/展开按钮', () => {
      renderWithRouter();

      const toggleButton = screen.getByRole('button', { name: /折叠|展开/i });
      expect(toggleButton).toBeInTheDocument();
    });

    it('应该能折叠聊天框', async () => {
      const user = userEvent.setup();
      renderWithRouter();

      const toggleButton = screen.getByRole('button', { name: /折叠/i });
      await user.click(toggleButton);

      // 聊天框应该被折叠（只显示标题栏）
      await waitFor(() => {
        const chatPanel = screen.getByTestId('ai-chat-panel');
        expect(chatPanel).toHaveStyle({ width: '48px' }); // 折叠后的宽度
      });
    });

    it('应该能展开已折叠的聊天框', async () => {
      const user = userEvent.setup();
      renderWithRouter();

      // 先折叠
      const collapseButton = screen.getByRole('button', { name: /折叠/i });
      await user.click(collapseButton);

      // 再展开
      const expandButton = await screen.findByRole('button', { name: /展开/i });
      await user.click(expandButton);

      // 聊天框应该展开
      await waitFor(() => {
        const chatPanel = screen.getByTestId('ai-chat-panel');
        expect(chatPanel).toHaveStyle({ width: '400px' }); // 展开后的宽度
      });
    });
  });

  describe('聊天框与工作流交互测试', () => {
    it('聊天框应该能询问工作流相关问题', async () => {
      const user = userEvent.setup();
      renderWithRouter();

      const input = screen.getByPlaceholderText(/输入消息/i);
      const sendButton = screen.getByRole('button', { name: /发送/i });

      // 询问工作流相关问题
      await user.type(input, '如何添加节点？');
      await user.click(sendButton);

      // 等待AI回复
      await waitFor(
        () => {
          expect(screen.queryByText('正在输入...')).not.toBeInTheDocument();
        },
        { timeout: 3000 }
      );

      // 应该有相关回复
      const messages = screen.getAllByRole('article');
      expect(messages.length).toBeGreaterThanOrEqual(2);
    });

    it('聊天框应该能回答节点类型相关问题', async () => {
      const user = userEvent.setup();
      renderWithRouter();

      const input = screen.getByPlaceholderText(/输入消息/i);
      const sendButton = screen.getByRole('button', { name: /发送/i });

      // 询问节点类型
      await user.type(input, '有哪些节点类型？');
      await user.click(sendButton);

      // 等待AI回复
      await waitFor(
        () => {
          expect(screen.queryByText('正在输入...')).not.toBeInTheDocument();
        },
        { timeout: 3000 }
      );

      // 应该有相关回复
      const messages = screen.getAllByRole('article');
      expect(messages.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('响应式布局测试', () => {
    it('聊天框应该有固定宽度', () => {
      renderWithRouter();

      const chatPanel = screen.getByTestId('ai-chat-panel');
      expect(chatPanel).toHaveStyle({ width: '400px' });
    });

    it('画布应该占据剩余空间', () => {
      renderWithRouter();

      const canvas = document.querySelector('.react-flow');
      const canvasWrapper = canvas?.parentElement;

      expect(canvasWrapper).toHaveStyle({ flex: '1' });
    });
  });

  describe('聊天框样式测试', () => {
    it('聊天框应该有边框分隔', () => {
      renderWithRouter();

      const chatPanel = screen.getByTestId('ai-chat-panel');
      expect(chatPanel).toHaveStyle({ borderLeft: '1px solid #f0f0f0' });
    });

    it('聊天框应该有正确的高度', () => {
      renderWithRouter();

      const chatPanel = screen.getByTestId('ai-chat-panel');
      expect(chatPanel).toHaveStyle({ height: '100%' });
    });
  });
});
