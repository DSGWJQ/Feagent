/**
 * WorkflowAIChat 组件测试
 * 
 * 测试真实AI聊天组件，调用后端API修改工作流
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { WorkflowAIChat } from '../WorkflowAIChat';

// Mock fetch
global.fetch = vi.fn();

describe('WorkflowAIChat', () => {
  const mockWorkflowId = 'wf_test123';
  const mockOnWorkflowUpdate = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('渲染测试', () => {
    it('应该渲染聊天框', () => {
      render(
        <WorkflowAIChat
          workflowId={mockWorkflowId}
          onWorkflowUpdate={mockOnWorkflowUpdate}
        />
      );

      expect(screen.getByPlaceholderText(/输入消息/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /发送/i })).toBeInTheDocument();
    });

    it('应该显示欢迎消息', () => {
      render(
        <WorkflowAIChat
          workflowId={mockWorkflowId}
          onWorkflowUpdate={mockOnWorkflowUpdate}
          showWelcome={true}
        />
      );

      expect(screen.getByText(/你好！我是工作流AI助手/i)).toBeInTheDocument();
    });
  });

  describe('消息发送测试', () => {
    it('应该能发送消息并调用API', async () => {
      const user = userEvent.setup();
      const mockResponse = {
        workflow: {
          id: mockWorkflowId,
          name: '测试工作流',
          nodes: [
            { id: 'node1', type: 'start', name: '开始', data: {}, position: { x: 0, y: 0 } },
            { id: 'node2', type: 'http', name: 'HTTP节点', data: {}, position: { x: 100, y: 0 } },
          ],
          edges: [
            { id: 'edge1', source: 'node1', target: 'node2' },
          ],
        },
        ai_message: '我已经添加了一个HTTP节点',
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      render(
        <WorkflowAIChat
          workflowId={mockWorkflowId}
          onWorkflowUpdate={mockOnWorkflowUpdate}
        />
      );

      const input = screen.getByPlaceholderText(/输入消息/i);
      const sendButton = screen.getByRole('button', { name: /发送/i });

      await user.type(input, '添加一个HTTP节点');
      await user.click(sendButton);

      // 验证API调用
      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          `http://localhost:8000/api/workflows/${mockWorkflowId}/chat`,
          expect.objectContaining({
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: '添加一个HTTP节点' }),
          })
        );
      });

      // 验证回调被调用
      await waitFor(() => {
        expect(mockOnWorkflowUpdate).toHaveBeenCalledWith(mockResponse.workflow);
      });

      // 验证AI消息显示
      await waitFor(() => {
        expect(screen.getByText('我已经添加了一个HTTP节点')).toBeInTheDocument();
      });
    });

    it('应该在发送时禁用输入框和按钮', async () => {
      const user = userEvent.setup();

      let resolvePromise: any;
      (global.fetch as any).mockImplementation(() =>
        new Promise(resolve => {
          resolvePromise = resolve;
        })
      );

      render(
        <WorkflowAIChat
          workflowId={mockWorkflowId}
          onWorkflowUpdate={mockOnWorkflowUpdate}
        />
      );

      const input = screen.getByPlaceholderText(/输入消息/i);
      const sendButton = screen.getByRole('button', { name: /发送/i });

      await user.type(input, '测试消息');
      await user.click(sendButton);

      // 验证禁用状态
      await waitFor(() => {
        expect(input).toBeDisabled();
        expect(sendButton).toBeDisabled();
      });

      // 完成请求
      resolvePromise({
        ok: true,
        json: async () => ({ workflow: { nodes: [], edges: [] }, ai_message: 'OK' }),
      });

      // 等待AI消息显示（说明请求已完成）
      await waitFor(() => {
        expect(screen.getByText('OK')).toBeInTheDocument();
      }, { timeout: 3000 });
    });

    it('应该显示加载状态', async () => {
      const user = userEvent.setup();
      
      (global.fetch as any).mockImplementation(() => 
        new Promise(resolve => setTimeout(() => resolve({
          ok: true,
          json: async () => ({ workflow: {}, ai_message: 'OK' }),
        }), 100))
      );

      render(
        <WorkflowAIChat
          workflowId={mockWorkflowId}
          onWorkflowUpdate={mockOnWorkflowUpdate}
        />
      );

      const input = screen.getByPlaceholderText(/输入消息/i);
      const sendButton = screen.getByRole('button', { name: /发送/i });

      await user.type(input, '测试消息');
      await user.click(sendButton);

      // 验证加载状态
      expect(screen.getByText(/AI正在思考/i)).toBeInTheDocument();

      // 等待请求完成
      await waitFor(() => {
        expect(screen.queryByText(/AI正在思考/i)).not.toBeInTheDocument();
      }, { timeout: 2000 });
    });
  });

  describe('错误处理测试', () => {
    it('应该处理API错误', async () => {
      const user = userEvent.setup();
      
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ detail: '服务器错误' }),
      });

      render(
        <WorkflowAIChat
          workflowId={mockWorkflowId}
          onWorkflowUpdate={mockOnWorkflowUpdate}
        />
      );

      const input = screen.getByPlaceholderText(/输入消息/i);
      const sendButton = screen.getByRole('button', { name: /发送/i });

      await user.type(input, '测试消息');
      await user.click(sendButton);

      // 验证错误消息显示
      await waitFor(() => {
        expect(screen.getByText(/抱歉，处理您的请求时出错了/i)).toBeInTheDocument();
      });

      // 验证回调未被调用
      expect(mockOnWorkflowUpdate).not.toHaveBeenCalled();
    });

    it('应该处理网络错误', async () => {
      const user = userEvent.setup();
      
      (global.fetch as any).mockRejectedValueOnce(new Error('Network error'));

      render(
        <WorkflowAIChat
          workflowId={mockWorkflowId}
          onWorkflowUpdate={mockOnWorkflowUpdate}
        />
      );

      const input = screen.getByPlaceholderText(/输入消息/i);
      const sendButton = screen.getByRole('button', { name: /发送/i });

      await user.type(input, '测试消息');
      await user.click(sendButton);

      // 验证错误消息显示
      await waitFor(() => {
        expect(screen.getByText(/抱歉，处理您的请求时出错了/i)).toBeInTheDocument();
      });
    });

    it('应该阻止发送空消息', async () => {
      const user = userEvent.setup();

      render(
        <WorkflowAIChat
          workflowId={mockWorkflowId}
          onWorkflowUpdate={mockOnWorkflowUpdate}
        />
      );

      const sendButton = screen.getByRole('button', { name: /发送/i });

      await user.click(sendButton);

      // 验证API未被调用
      expect(global.fetch).not.toHaveBeenCalled();
    });
  });

  describe('消息历史测试', () => {
    it('应该显示消息历史', async () => {
      const user = userEvent.setup();
      
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          workflow: {},
          ai_message: 'AI回复1',
        }),
      });

      render(
        <WorkflowAIChat
          workflowId={mockWorkflowId}
          onWorkflowUpdate={mockOnWorkflowUpdate}
        />
      );

      const input = screen.getByPlaceholderText(/输入消息/i);
      const sendButton = screen.getByRole('button', { name: /发送/i });

      await user.type(input, '用户消息1');
      await user.click(sendButton);

      await waitFor(() => {
        expect(screen.getByText('用户消息1')).toBeInTheDocument();
        expect(screen.getByText('AI回复1')).toBeInTheDocument();
      });
    });
  });

  describe('键盘快捷键测试', () => {
    it('应该支持Enter发送消息', async () => {
      const user = userEvent.setup();
      
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          workflow: {},
          ai_message: 'OK',
        }),
      });

      render(
        <WorkflowAIChat
          workflowId={mockWorkflowId}
          onWorkflowUpdate={mockOnWorkflowUpdate}
        />
      );

      const input = screen.getByPlaceholderText(/输入消息/i);

      await user.type(input, '测试消息{Enter}');

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalled();
      });
    });

    it('应该支持Shift+Enter换行', async () => {
      const user = userEvent.setup();

      render(
        <WorkflowAIChat
          workflowId={mockWorkflowId}
          onWorkflowUpdate={mockOnWorkflowUpdate}
        />
      );

      const input = screen.getByPlaceholderText(/输入消息/i) as HTMLTextAreaElement;

      await user.type(input, '第一行{Shift>}{Enter}{/Shift}第二行');

      expect(input.value).toContain('\n');
      expect(global.fetch).not.toHaveBeenCalled();
    });
  });
});

