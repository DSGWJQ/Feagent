/**
 * 主应用组件
 *
 * 修改记录：
 * - 2024-01-15: 添加 AgentListTest 测试页面，验证 API 连接
 * - 2024-01-15: 添加路由系统，支持多页面导航
 * - 2025-12-14: 添加 ThemeProvider，支持 Dark/Light 主题切换
 */

import { App as AntdApp, ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { RouterProvider } from 'react-router-dom';
import QueryProvider from './providers/QueryProvider';
import { router } from './router';
import { theme } from '@/shared/styles/theme';
import { ThemeProvider } from '@/shared/contexts/ThemeContext';
import '@/shared/styles/global.css';
import '@/shared/styles/components.css';  /* Gemini's System 01 Component Library */
import '@/shared/styles/neoclassical.css';

/**
 * 主应用组件
 *
 * 结构：
 * 1. ThemeProvider - 主题管理（Dark/Light切换）
 * 2. ConfigProvider - Ant Design 配置（语言、主题）
 * 3. QueryProvider - TanStack Query 配置（数据缓存）
 * 4. RouterProvider - React Router 配置（路由）
 *
 * 为什么这样嵌套？
 * - ThemeProvider 在最外层：管理全局主题状态和CSS Variables
 * - ConfigProvider 在其下：所有组件都需要主题和语言配置
 * - QueryProvider 在中间：所有页面都需要数据缓存
 * - RouterProvider 在最内层：负责渲染不同的页面
 */
function App() {
  return (
    <ThemeProvider>
      <ConfigProvider locale={zhCN} theme={theme}>
        <AntdApp>
          <QueryProvider>
            <RouterProvider router={router} />
          </QueryProvider>
        </AntdApp>
      </ConfigProvider>
    </ThemeProvider>
  );
}

export default App;
