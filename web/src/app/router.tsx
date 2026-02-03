/**
 * 应用路由配置
 *
 * Contract:
 * - `/` 只做自然语言澄清对话（绝不创建 workflow）
 * - 显式创建入口：`/workflows/new`
 * - 编辑器只接受显式 workflow id：`/workflows/:id/edit`
 */

import { createBrowserRouter, Navigate } from 'react-router-dom';
import { ChatPage } from '@/features/chat/pages';
import { WorkflowCreatePage, WorkflowEditorPage } from '@/features/workflows/pages';

export const router = createBrowserRouter([
  // 默认入口：仅澄清对话，不创建 workflow
  { path: '/', element: <ChatPage /> },

  // 显式创建入口
  { path: '/workflows/new', element: <WorkflowCreatePage /> },

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
