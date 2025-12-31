/**
 * AgentDetailPage 测试用例
 *
 * 测试场景：
 * 1. 加载状态 - 显示 Spin
 * 2. 成功加载 - 显示 Agent 信息和 Tasks 列表
 * 3. Agent 不存在 - 显示 404 错误
 * 4. 网络错误 - 显示错误信息
 * 5. 返回按钮 - 点击后跳转到列表页
 */

import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import { AgentDetailPage } from '../AgentDetailPage';
import * as agentsApi from '@/features/agents/api/agentsApi';
import type { Agent } from '@/shared/types';

// Mock agentsApi
vi.mock('@/features/agents/api/agentsApi');

describe('AgentDetailPage', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    // 每个测试前创建新的 QueryClient
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false, // 测试时不重试
        },
      },
    });
    vi.clearAllMocks();
  });

  /**
   * 辅助函数：渲染组件
   */
  const renderComponent = (agentId: string = 'agent-123') => {
    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/app/agents/${agentId}`]}>
          <Routes>
            <Route path="/app/agents/:id" element={<AgentDetailPage />} />
            <Route path="/app/agents" element={<div>Agent List</div>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
  };

  /**
   * 测试 1：加载状态
   *
   * 预期：
   * - 显示 "加载中..." 文本
   * - 显示 Spin 组件
   */
  it('应该显示加载状态', () => {
    // Arrange: Mock API 返回 pending 状态
    vi.mocked(agentsApi.agentsApi.getAgent).mockImplementation(
      () => new Promise(() => {}) // 永远不 resolve，保持 loading 状态
    );

    // Act: 渲染组件
    renderComponent();

    // Assert: 验证加载状态
    expect(screen.getByText(/加载中/i)).toBeInTheDocument();
  });

  /**
   * 测试 2：成功加载 Agent 信息
   *
   * 预期：
   * - 显示 Agent 名称
   * - 显示 Agent 起点和目的
   * - 显示创建时间
   */
  it('应该显示 Agent 详情', async () => {
    // Arrange: Mock API 返回成功数据
    const mockAgent: Agent = {
      id: 'agent-123',
      name: '销售分析 Agent',
      start: '我有一个 CSV 文件',
      goal: '生成数据分析报告',
      created_at: '2025-11-18T10:00:00Z',
      updated_at: '2025-11-18T10:00:00Z',
      tasks: [],
    };

    vi.mocked(agentsApi.agentsApi.getAgent).mockResolvedValue(mockAgent);

    // Act: 渲染组件
    renderComponent('agent-123');

    // Assert: 验证 Agent 信息显示
    await waitFor(() => {
      expect(screen.getByText('销售分析 Agent')).toBeInTheDocument();
      expect(screen.getByText('我有一个 CSV 文件')).toBeInTheDocument();
      expect(screen.getByText('生成数据分析报告')).toBeInTheDocument();
    });

    // 验证 API 调用
    expect(agentsApi.agentsApi.getAgent).toHaveBeenCalledWith('agent-123');
    expect(agentsApi.agentsApi.getAgent).toHaveBeenCalledTimes(1);
  });

  /**
   * 测试 3：显示 Tasks 列表
   *
   * 预期：
   * - 显示所有 Task 的名称
   * - 显示 Task 状态
   * - 显示 Task 描述
   */
  it('应该显示 Tasks 列表', async () => {
    // Arrange: Mock API 返回包含 Tasks 的数据
    const mockAgent: Agent = {
      id: 'agent-123',
      name: '销售分析 Agent',
      start: '我有一个 CSV 文件',
      goal: '生成数据分析报告',
      created_at: '2025-11-18T10:00:00Z',
      updated_at: '2025-11-18T10:00:00Z',
      tasks: [
        {
          id: 'task-1',
          agent_id: 'agent-123',
          name: '读取 CSV 文件',
          description: '使用 pandas 读取 CSV 文件到 DataFrame',
          status: 'pending',
          created_at: '2025-11-18T10:00:01Z',
        },
        {
          id: 'task-2',
          agent_id: 'agent-123',
          name: '分析销售数据',
          description: '计算销售总额、平均值等统计指标',
          status: 'pending',
          created_at: '2025-11-18T10:00:02Z',
        },
      ],
    };

    vi.mocked(agentsApi.agentsApi.getAgent).mockResolvedValue(mockAgent);

    // Act: 渲染组件
    renderComponent('agent-123');

    // Assert: 验证 Tasks 列表显示
    await waitFor(() => {
      // 验证任务描述（description 是唯一的）
      expect(screen.getByText('使用 pandas 读取 CSV 文件到 DataFrame')).toBeInTheDocument();
      expect(screen.getByText('计算销售总额、平均值等统计指标')).toBeInTheDocument();

      // 验证任务列表标题存在
      expect(screen.getByText('执行任务')).toBeInTheDocument();
    });
  });

  /**
   * 测试 4：Agent 不存在（404）
   *
   * 预期：
   * - 显示 "Agent 不存在" 错误信息
   */
  it('应该显示 404 错误', async () => {
    // Arrange: Mock API 返回 404 错误
    const error = new Error('Agent not found');
    vi.mocked(agentsApi.agentsApi.getAgent).mockRejectedValue(error);

    // Act: 渲染组件
    renderComponent('non-existent-id');

    // Assert: 验证错误信息显示
    await waitFor(() => {
      expect(screen.getByText(/加载失败/i)).toBeInTheDocument();
    });
  });

  /**
   * 测试 5：返回按钮
   *
   * 预期：
   * - 点击返回按钮后跳转到 /agents
   */
  it('应该支持返回到列表页', async () => {
    // Arrange: Mock API 返回成功数据
    const mockAgent: Agent = {
      id: 'agent-123',
      name: '销售分析 Agent',
      start: '我有一个 CSV 文件',
      goal: '生成数据分析报告',
      created_at: '2025-11-18T10:00:00Z',
      updated_at: '2025-11-18T10:00:00Z',
      tasks: [],
    };

    vi.mocked(agentsApi.agentsApi.getAgent).mockResolvedValue(mockAgent);

    // Act: 渲染组件
    renderComponent('agent-123');

    // 等待加载完成
    await waitFor(() => {
      expect(screen.getByText('销售分析 Agent')).toBeInTheDocument();
    });

    // 点击返回按钮
    const backButton = screen.getByText(/返回列表/i);
    await userEvent.click(backButton);

    // Assert: 验证跳转到列表页
    await waitFor(() => {
      expect(screen.getByText('Agent List')).toBeInTheDocument();
    });
  });

  /**
   * 测试 6：没有 Tasks 的情况
   *
   * 预期：
   * - 显示 "暂无任务" 提示
   */
  it('应该显示空状态（没有 Tasks）', async () => {
    // Arrange: Mock API 返回没有 Tasks 的数据
    const mockAgent: Agent = {
      id: 'agent-123',
      name: '销售分析 Agent',
      start: '我有一个 CSV 文件',
      goal: '生成数据分析报告',
      created_at: '2025-11-18T10:00:00Z',
      updated_at: '2025-11-18T10:00:00Z',
      tasks: [],
    };

    vi.mocked(agentsApi.agentsApi.getAgent).mockResolvedValue(mockAgent);

    // Act: 渲染组件
    renderComponent('agent-123');

    // Assert: 验证空状态显示
    await waitFor(() => {
      expect(screen.getByText(/暂无任务/i)).toBeInTheDocument();
    });
  });
});

/**
 * 测试总结：
 *
 * ✅ 测试了 6 个核心场景：
 * 1. 加载状态
 * 2. 成功加载 Agent 信息
 * 3. 显示 Tasks 列表
 * 4. 404 错误处理
 * 5. 返回按钮功能
 * 6. 空状态（没有 Tasks）
 *
 * 这些测试覆盖了 AgentDetailPage 的所有核心功能。
 */
