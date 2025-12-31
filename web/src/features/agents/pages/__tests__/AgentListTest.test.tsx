/**
 * AgentListTest 组件测试
 *
 * 测试目标：
 * - 验证组件是否正确渲染
 * - 验证用户交互是否正常工作
 * - 验证不同状态下的显示
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/utils';
import AgentListTest from '../AgentListTest';
import { agentsApi } from '@/features/agents/api/agentsApi';
import type { Agent } from '@/shared/types';

// Mock agentsApi
vi.mock('@/features/agents/api/agentsApi', () => ({
  agentsApi: {
    getAgents: vi.fn(),
    createAgent: vi.fn(),
    deleteAgent: vi.fn(),
  },
}));

// Mock Ant Design message
vi.mock('antd', async () => {
  const actual = await vi.importActual('antd');
  return {
    ...actual,
    message: {
      success: vi.fn(),
      error: vi.fn(),
      loading: vi.fn(() => vi.fn()),
    },
  };
});

describe('AgentListTest', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('加载状态', () => {
    it('应该显示加载中状态', () => {
      // Arrange
      vi.mocked(agentsApi.getAgents).mockImplementation(
        () => new Promise(() => {}) // 永不 resolve，保持加载状态
      );

      // Act
      renderWithProviders(<AgentListTest />);

      // Assert
      expect(screen.getByText('加载中...')).toBeInTheDocument();
    });
  });

  describe('成功状态', () => {
    it('应该显示 Agent 列表', async () => {
      // Arrange
      const mockAgents: Agent[] = [
        {
          id: '1',
          name: '测试 Agent 1',
          start: '起始状态 1',
          goal: '目标状态 1',
          created_at: '2024-01-15T00:00:00Z',
          updated_at: '2024-01-15T00:00:00Z',
        },
        {
          id: '2',
          name: '测试 Agent 2',
          start: '起始状态 2',
          goal: '目标状态 2',
          created_at: '2024-01-15T00:00:00Z',
          updated_at: '2024-01-15T00:00:00Z',
        },
      ];
      vi.mocked(agentsApi.getAgents).mockResolvedValue(mockAgents);

      // Act
      renderWithProviders(<AgentListTest />);

      // Assert
      await waitFor(() => {
        expect(screen.getByText('测试 Agent 1')).toBeInTheDocument();
      });

      expect(screen.getByText('测试 Agent 1')).toBeInTheDocument();
      expect(screen.getByText('测试 Agent 2')).toBeInTheDocument();
      expect(screen.getByText('起始状态 1')).toBeInTheDocument();
      expect(screen.getByText('目标状态 1')).toBeInTheDocument();
    });

    it('应该显示空状态', async () => {
      // Arrange
      vi.mocked(agentsApi.getAgents).mockResolvedValue([]);

      // Act
      renderWithProviders(<AgentListTest />);

      // Assert
      await waitFor(() => {
        expect(screen.getByText('暂无 Agent')).toBeInTheDocument();
      });

      expect(
        screen.getByText('点击上方"创建测试 Agent"按钮创建一个测试数据')
      ).toBeInTheDocument();
    });
  });

  describe('错误状态', () => {
    it('应该显示错误信息', async () => {
      // Arrange
      const error = new Error('Network error');
      vi.mocked(agentsApi.getAgents).mockRejectedValue(error);

      // Act
      renderWithProviders(<AgentListTest />);

      // Assert
      await waitFor(() => {
        expect(screen.getByText('加载失败')).toBeInTheDocument();
      });

      expect(screen.getByText(/无法连接到后端 API/)).toBeInTheDocument();
    });
  });

  describe('用户交互', () => {
    it('应该能够创建测试 Agent', async () => {
      // Arrange
      const user = userEvent.setup();
      vi.mocked(agentsApi.getAgents).mockResolvedValue([]);
      const mockNewAgent: Agent = {
        id: '1',
        name: '测试 Agent',
        start: '有一个 CSV 文件需要分析',
        goal: '生成数据分析报告并发送邮件',
        created_at: '2024-01-15T00:00:00Z',
        updated_at: '2024-01-15T00:00:00Z',
      };
      vi.mocked(agentsApi.createAgent).mockResolvedValue(mockNewAgent);

      // Act
      renderWithProviders(<AgentListTest />);

      await waitFor(() => {
        expect(screen.getByText('暂无 Agent')).toBeInTheDocument();
      });

      const createButton = screen.getByRole('button', { name: /创建测试 Agent/ });
      await user.click(createButton);

      // Assert
      await waitFor(() => {
        expect(agentsApi.createAgent).toHaveBeenCalledWith(
          expect.objectContaining({
            start: '有一个 CSV 文件需要分析',
            goal: '生成数据分析报告并发送邮件',
          })
        );
      });
    });

    it('应该能够刷新列表', async () => {
      // Arrange
      const user = userEvent.setup();
      vi.mocked(agentsApi.getAgents).mockResolvedValue([]);

      // Act
      renderWithProviders(<AgentListTest />);

      await waitFor(() => {
        expect(screen.getByText('暂无 Agent')).toBeInTheDocument();
      });

      const refreshButton = screen.getByRole('button', { name: /刷新/ });
      await user.click(refreshButton);

      // Assert
      await waitFor(() => {
        expect(agentsApi.getAgents).toHaveBeenCalledTimes(2); // 初始加载 + 手动刷新
      });
    });

    it('应该能够删除 Agent', async () => {
      // Arrange
      const user = userEvent.setup();
      const mockAgents: Agent[] = [
        {
          id: '1',
          name: '测试 Agent',
          start: '起始状态',
          goal: '目标状态',
          created_at: '2024-01-15T00:00:00Z',
          updated_at: '2024-01-15T00:00:00Z',
        },
      ];
      vi.mocked(agentsApi.getAgents).mockResolvedValue(mockAgents);
      vi.mocked(agentsApi.deleteAgent).mockResolvedValue(undefined);

      // Mock window.confirm
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);

      // Act
      renderWithProviders(<AgentListTest />);

      await waitFor(() => {
        expect(screen.getByText('测试 Agent')).toBeInTheDocument();
      });

      const deleteButton = screen.getByRole('button', { name: /删\s*除/ }); // 匹配 "删除" 或 "删 除"
      await user.click(deleteButton);

      // Assert
      expect(confirmSpy).toHaveBeenCalledWith('确认删除这个 Agent 吗？');
      await waitFor(() => {
        expect(agentsApi.deleteAgent).toHaveBeenCalledWith('1');
      });

      confirmSpy.mockRestore();
    });
  });
});

/**
 * 测试总结：
 *
 * ✅ 测试了加载状态
 * ✅ 测试了成功状态（有数据、无数据）
 * ✅ 测试了错误状态
 * ✅ 测试了用户交互（创建、刷新、删除）
 *
 * 为什么要测试组件？
 * 1. 确保组件在不同状态下正确渲染
 * 2. 确保用户交互正常工作
 * 3. 防止重构时破坏功能
 * 4. 作为组件使用的文档
 */
