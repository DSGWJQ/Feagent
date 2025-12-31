/**
 * 测试工具函数
 *
 * 提供常用的测试辅助函数，如自定义渲染、Mock 数据等
 */

import { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { App, ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { MemoryRouter } from 'react-router-dom';
import { theme } from '@/shared/styles/theme';
import { WorkflowInteractionProvider } from '@/features/workflows/contexts/WorkflowInteractionContext';

/**
 * 创建测试用的 QueryClient
 *
 * 为什么需要这个？
 * - 测试时不需要重试（retry: false）
 * - 测试时不需要缓存（gcTime: 0）
 * - 避免测试之间的缓存污染
 */
export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
    logger: {
      log: console.log,
      warn: console.warn,
      error: () => {}, // 测试时不显示错误日志
    },
  });
}

/**
 * 自定义渲染函数
 *
 * 为什么需要这个？
 * - 自动包装 QueryClientProvider、ConfigProvider 和 Router
 * - 避免每个测试都要手动包装
 * - 提供统一的测试环境
 *
 * 使用示例：
 * ```typescript
 * const { getByText } = renderWithProviders(<MyComponent />);
 * ```
 */
interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  queryClient?: QueryClient;
  initialEntries?: string[];
}

export function renderWithProviders(
  ui: ReactElement,
  options?: CustomRenderOptions
) {
  const {
    queryClient = createTestQueryClient(),
    initialEntries = ['/'],
    ...renderOptions
  } = options || {};

  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <MemoryRouter initialEntries={initialEntries}>
        <ConfigProvider locale={zhCN} theme={theme}>
          <App>
            <QueryClientProvider client={queryClient}>
              <WorkflowInteractionProvider>{children}</WorkflowInteractionProvider>
            </QueryClientProvider>
          </App>
        </ConfigProvider>
      </MemoryRouter>
    );
  }

  return {
    ...render(ui, { wrapper: Wrapper, ...renderOptions }),
    queryClient,
  };
}

/**
 * 等待异步操作完成
 *
 * 使用示例：
 * ```typescript
 * await waitFor(() => {
 *   expect(screen.getByText('加载完成')).toBeInTheDocument();
 * });
 * ```
 */
export { waitFor, screen } from '@testing-library/react';

/**
 * 用户交互模拟
 *
 * 使用示例：
 * ```typescript
 * await userEvent.click(screen.getByRole('button'));
 * await userEvent.type(screen.getByRole('textbox'), 'Hello');
 * ```
 */
export { default as userEvent } from '@testing-library/user-event';
