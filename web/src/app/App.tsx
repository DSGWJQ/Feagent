/**
 * 主应用组件
 *
 * 修改记录：
 * - 2024-01-15: 添加 AgentListTest 测试页面，验证 API 连接
 * - 2024-01-15: 添加路由系统，支持多页面导航
 */

import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { RouterProvider } from 'react-router-dom';
import QueryProvider from './providers/QueryProvider';
import { router } from './router';
import { theme } from '@/shared/styles/theme';
import '@/shared/styles/global.css';

/**
 * 主应用组件
 *
 * 结构：
 * 1. ConfigProvider - Ant Design 配置（语言、主题）
 * 2. QueryProvider - TanStack Query 配置（数据缓存）
 * 3. RouterProvider - React Router 配置（路由）
 *
 * 为什么这样嵌套？
 * - ConfigProvider 在最外层：所有组件都需要主题和语言配置
 * - QueryProvider 在中间：所有页面都需要数据缓存
 * - RouterProvider 在最内层：负责渲染不同的页面
 */
function App() {
  return (
    <ConfigProvider locale={zhCN} theme={theme}>
      <QueryProvider>
        <RouterProvider router={router} />
      </QueryProvider>
    </ConfigProvider>
  );
}

export default App;
