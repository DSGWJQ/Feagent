/**
 * 应用路由配置
 *
 * 单页面应用模式：只保留工作流编辑器
 */

import { createBrowserRouter, Navigate } from 'react-router-dom';
import { WorkflowEditorPage } from '@/features/workflows/pages';

export const router = createBrowserRouter([
  // 根路径直达编辑器（Editor组件内部会自动处理新建/重定向）
  {
    path: '/',
    element: <WorkflowEditorPage />,
  },

  // 编辑器具体路径
  {
    path: '/workflows/:id/edit',
    element: <WorkflowEditorPage />,
  },

  // 任何其他路径重定向到首页
  {
    path: '*',
    element: <Navigate to="/" replace />,
  }
]);
