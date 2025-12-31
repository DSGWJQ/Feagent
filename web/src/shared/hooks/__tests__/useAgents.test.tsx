/**
 * useAgents Hooks 测试
 *
 * 测试目标：
 * - 验证 Hooks 是否正确调用 API
 * - 验证缓存机制是否正常工作
 * - 验证 Mutation 后是否正确刷新缓存
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAgents, useAgent, useCreateAgent, useDeleteAgent } from '../useAgents';
import { agentsApi } from '@/features/agents/api/agentsApi';
import type { Agent, CreateAgentDto } from '@/shared/types';

// Mock agentsApi
vi.mock('@/features/agents/api/agentsApi', () => ({
  agentsApi: {
    getAgents: vi.fn(),
    getAgent: vi.fn(),
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

// 创建测试用的 QueryClient
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
    logger: {
      log: console.log,
      warn: console.warn,
      error: () => {},
    },
  });
}

// 创建 Wrapper
function createWrapper() {
  const queryClient = createTestQueryClient();
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useAgents', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('useAgents', () => {
    it('应该成功获取 Agent 列表', async () => {
      // Arrange
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

      // Act
      const { result } = renderHook(() => useAgents(), {
        wrapper: createWrapper(),
      });

      // Assert
      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockAgents);
      expect(agentsApi.getAgents).toHaveBeenCalledTimes(1);
    });

    it('应该传递查询参数', async () => {
      // Arrange
      const params = { skip: 0, limit: 10 };
      vi.mocked(agentsApi.getAgents).mockResolvedValue([]);

      // Act
      renderHook(() => useAgents(params), {
        wrapper: createWrapper(),
      });

      // Assert
      await waitFor(() => {
        expect(agentsApi.getAgents).toHaveBeenCalledWith(params);
      });
    });

    it('应该处理错误', async () => {
      // Arrange
      const error = new Error('Network error');
      vi.mocked(agentsApi.getAgents).mockRejectedValue(error);

      // Act
      const { result } = renderHook(() => useAgents(), {
        wrapper: createWrapper(),
      });

      // Assert
      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error).toEqual(error);
    });
  });

  describe('useAgent', () => {
    it('应该成功获取单个 Agent', async () => {
      // Arrange
      const mockAgent: Agent = {
        id: '1',
        name: '测试 Agent',
        start: '起始状态',
        goal: '目标状态',
        created_at: '2024-01-15T00:00:00Z',
        updated_at: '2024-01-15T00:00:00Z',
      };
      vi.mocked(agentsApi.getAgent).mockResolvedValue(mockAgent);

      // Act
      const { result } = renderHook(() => useAgent('1'), {
        wrapper: createWrapper(),
      });

      // Assert
      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockAgent);
      expect(agentsApi.getAgent).toHaveBeenCalledWith('1');
    });

    it('当 id 为空时不应该发起请求', async () => {
      // Act
      const { result } = renderHook(() => useAgent(''), {
        wrapper: createWrapper(),
      });

      // Assert
      expect(result.current.fetchStatus).toBe('idle');
      expect(agentsApi.getAgent).not.toHaveBeenCalled();
    });
  });

  describe('useCreateAgent', () => {
    it('应该成功创建 Agent', async () => {
      // Arrange
      const createData: CreateAgentDto = {
        name: '新 Agent',
        start: '起始状态',
        goal: '目标状态',
      };
      const mockAgent: Agent = {
        id: '1',
        ...createData,
        created_at: '2024-01-15T00:00:00Z',
        updated_at: '2024-01-15T00:00:00Z',
      };
      vi.mocked(agentsApi.createAgent).mockResolvedValue(mockAgent);

      // Act
      const { result } = renderHook(() => useCreateAgent(), {
        wrapper: createWrapper(),
      });

      result.current.mutate(createData);

      // Assert
      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockAgent);
      expect(agentsApi.createAgent).toHaveBeenCalledWith(createData);
    });
  });

  describe('useDeleteAgent', () => {
    it('应该成功删除 Agent', async () => {
      // Arrange
      vi.mocked(agentsApi.deleteAgent).mockResolvedValue(undefined);

      // Act
      const { result } = renderHook(() => useDeleteAgent(), {
        wrapper: createWrapper(),
      });

      result.current.mutate('1');

      // Assert
      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(agentsApi.deleteAgent).toHaveBeenCalledWith('1');
    });
  });
});

/**
 * 测试总结：
 *
 * ✅ 测试了所有主要的 Hooks
 * ✅ 验证了数据获取的正确性
 * ✅ 验证了错误处理
 * ✅ 验证了参数传递
 * ✅ 验证了条件查询（enabled）
 *
 * 为什么要测试 Hooks？
 * 1. Hooks 包含业务逻辑（缓存、刷新等）
 * 2. 确保 Mutation 后缓存正确更新
 * 3. 作为 Hooks 使用的文档
 */
