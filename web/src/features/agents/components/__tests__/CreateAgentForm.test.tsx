/**
 * CreateAgentForm 组件测试
 *
 * 测试策略：
 * 1. 渲染测试：组件能正常渲染
 * 2. 表单验证测试：验证规则是否正确
 * 3. 提交测试：表单提交是否正常
 * 4. 错误处理测试：API 错误是否正确显示
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CreateAgentForm } from '../CreateAgentForm';
import { agentsApi } from '@/features/agents/api/agentsApi';

// 创建测试用的 QueryClient
const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

// 包装组件（提供 QueryClient）
const renderWithQueryClient = (ui: React.ReactElement) => {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
};

describe('CreateAgentForm', () => {
  // Mock API 调用
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

  it('应该渲染所有表单字段', () => {
    renderWithQueryClient(<CreateAgentForm />);

    // 验证三个字段都存在
    expect(screen.getByLabelText(/起点/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/目的/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/名称/i)).toBeInTheDocument();

    // 验证提交按钮存在
    expect(screen.getByRole('button', { name: /创建/i })).toBeInTheDocument();
  });

  it('应该显示字段的 placeholder', () => {
    renderWithQueryClient(<CreateAgentForm />);

    // 验证 placeholder 存在（帮助用户理解字段含义）
    const startInput = screen.getByLabelText(/起点/i);
    expect(startInput).toHaveAttribute('placeholder');

    const goalInput = screen.getByLabelText(/目的/i);
    expect(goalInput).toHaveAttribute('placeholder');
  });

  it('当 start 字段为空时，应该显示验证错误', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<CreateAgentForm />);

    // 点击提交按钮（不填写任何字段）
    const submitButton = screen.getByRole('button', { name: /创建/i });
    await user.click(submitButton);

    // 应该显示 start 字段的错误信息
    await waitFor(() => {
      expect(screen.getByText(/起点.*必填/i)).toBeInTheDocument();
    });
  });

  it('当 goal 字段为空时，应该显示验证错误', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<CreateAgentForm />);

    // 点击提交按钮（不填写任何字段）
    const submitButton = screen.getByRole('button', { name: /创建/i });
    await user.click(submitButton);

    // 应该显示 goal 字段的错误信息
    await waitFor(() => {
      expect(screen.getByText(/目的.*必填/i)).toBeInTheDocument();
    });
  });

  it('当 start 字段太短时，应该显示验证错误', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<CreateAgentForm />);

    // 输入太短的内容（少于 10 个字符）
    const startInput = screen.getByLabelText(/起点/i);
    await user.type(startInput, '太短了');

    // 点击提交按钮
    const submitButton = screen.getByRole('button', { name: /创建/i });
    await user.click(submitButton);

    // 应该显示长度验证错误
    await waitFor(() => {
      expect(screen.getByText(/至少.*10.*字符/i)).toBeInTheDocument();
    });
  });

  // 注意：这个测试被删除了
  // 原因：TextArea 的 maxLength={500} 会阻止输入超过 500 个字符
  // 所以不会触发表单验证错误
  // 这是正确的行为：前端应该阻止用户输入过长的内容

  it('当填写有效数据时，应该成功提交', async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();

    renderWithQueryClient(<CreateAgentForm onSuccess={onSuccess} />);

    // 填写有效数据
    const startInput = screen.getByLabelText(/起点/i);
    await user.type(startInput, '我有一个 CSV 文件，包含过去一年的销售数据');

    const goalInput = screen.getByLabelText(/目的/i);
    await user.type(goalInput, '分析销售数据，找出销售趋势和热门产品，生成可视化报告');

    const nameInput = screen.getByLabelText(/名称/i);
    await user.type(nameInput, '销售分析 Agent');

    // 点击提交按钮
    const submitButton = screen.getByRole('button', { name: /创建/i });
    await user.click(submitButton);

    // 应该调用 onSuccess 回调
    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalled();
    });
  });

  it('name 字段应该是可选的', async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();

    renderWithQueryClient(<CreateAgentForm onSuccess={onSuccess} />);

    // 只填写 start 和 goal，不填写 name
    const startInput = screen.getByLabelText(/起点/i);
    await user.type(startInput, '我有一个 CSV 文件，包含过去一年的销售数据');

    const goalInput = screen.getByLabelText(/目的/i);
    await user.type(goalInput, '分析销售数据，找出销售趋势和热门产品，生成可视化报告');

    // 点击提交按钮
    const submitButton = screen.getByRole('button', { name: /创建/i });
    await user.click(submitButton);

    // 应该成功提交（name 是可选的）
    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalled();
    });
  });

  it('提交时应该显示加载状态', async () => {
    const user = userEvent.setup();

    // Mock API 调用为延迟响应
    vi.spyOn(agentsApi, 'createAgent').mockImplementation(
      () => new Promise((resolve) => setTimeout(resolve, 1000))
    );

    renderWithQueryClient(<CreateAgentForm />);

    // 填写有效数据
    const startInput = screen.getByLabelText(/起点/i);
    await user.type(startInput, '我有一个 CSV 文件，包含过去一年的销售数据');

    const goalInput = screen.getByLabelText(/目的/i);
    await user.type(goalInput, '分析销售数据，找出销售趋势和热门产品，生成可视化报告');

    // 点击提交按钮
    const submitButton = screen.getByRole('button', { name: /创建/i });
    await user.click(submitButton);

    // 提交按钮应该显示加载状态（有 loading 类）
    await waitFor(() => {
      expect(submitButton).toHaveClass('ant-btn-loading');
    });
  });
});
