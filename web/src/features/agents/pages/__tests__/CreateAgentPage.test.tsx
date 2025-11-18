/**
 * CreateAgentPage 页面测试
 *
 * 测试策略：
 * 1. 渲染测试：页面能正常渲染
 * 2. 表单测试：包含 CreateAgentForm 组件
 * 3. 导航测试：创建成功后跳转到详情页
 * 4. 返回按钮测试：点击返回按钮跳转到列表页
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { CreateAgentPage } from '../CreateAgentPage';
import { agentsApi } from '@/features/agents/api/agentsApi';

// 创建测试用的 QueryClient
const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

// Mock navigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// 包装组件（提供 QueryClient 和 Router）
const renderWithProviders = (ui: React.ReactElement) => {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/agents/create']}>
        <Routes>
          <Route path="/agents/create" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
};

describe('CreateAgentPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock createAgent API
    vi.spyOn(agentsApi, 'createAgent').mockResolvedValue({
      id: 'test-agent-id',
      name: '测试 Agent',
      start: '我有一个 CSV 文件，包含过去一年的销售数据',
      goal: '分析销售数据，找出销售趋势和热门产品，生成可视化报告',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  });

  it('应该渲染页面标题', () => {
    renderWithProviders(<CreateAgentPage />);

    // 验证页面标题存在（使用 role 查询更精确）
    expect(screen.getByRole('heading', { name: /创建.*Agent/i })).toBeInTheDocument();
  });

  it('应该渲染表单组件', () => {
    renderWithProviders(<CreateAgentPage />);

    // 验证表单字段存在（说明 CreateAgentForm 组件被渲染了）
    expect(screen.getByLabelText(/起点/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/目的/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/名称/i)).toBeInTheDocument();
  });

  it('应该有返回按钮', () => {
    renderWithProviders(<CreateAgentPage />);

    // 验证返回按钮存在
    expect(screen.getByRole('button', { name: /返回/i })).toBeInTheDocument();
  });

  it('点击返回按钮应该跳转到列表页', async () => {
    const user = userEvent.setup();
    renderWithProviders(<CreateAgentPage />);

    // 点击返回按钮
    const backButton = screen.getByRole('button', { name: /返回/i });
    await user.click(backButton);

    // 应该调用 navigate('/agents')
    expect(mockNavigate).toHaveBeenCalledWith('/agents');
  });

  it('创建成功后应该跳转到详情页', async () => {
    const user = userEvent.setup();
    renderWithProviders(<CreateAgentPage />);

    // 填写表单
    const startInput = screen.getByLabelText(/起点/i);
    await user.type(startInput, '我有一个 CSV 文件，包含过去一年的销售数据');

    const goalInput = screen.getByLabelText(/目的/i);
    await user.type(goalInput, '分析销售数据，找出销售趋势和热门产品，生成可视化报告');

    // 提交表单
    const submitButton = screen.getByRole('button', { name: /创建/i });
    await user.click(submitButton);

    // 应该跳转到详情页（包含 Agent ID）
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith(expect.stringMatching(/^\/agents\/.+$/));
    });
  });

  it('应该显示页面描述', () => {
    renderWithProviders(<CreateAgentPage />);

    // 验证页面描述存在（帮助用户理解这个页面的作用）
    expect(screen.getByText(/填写.*信息/i)).toBeInTheDocument();
  });
});
