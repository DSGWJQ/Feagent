/**
 * 应用路由配置
 *
 * 为什么需要单独的路由文件？
 * - 集中管理所有路由
 * - 方便添加新路由
 * - 支持代码分割（lazy loading）
 * - 便于测试
 *
 * 路由结构：
 * - / - Home 页面
 * - /agents - Agent 列表页
 * - /agents/create - 创建 Agent 页面
 * - /workflows/:id/edit - 工作流编辑器
 */

import { createBrowserRouter } from 'react-router-dom';
import { HomePage } from '@/features/home/pages';
import { AgentListTest, CreateAgentPage, AgentDetailPage } from '@/features/agents/pages';
import { WorkflowEditorPage } from '@/features/workflows/pages';
import { TaskClassificationPage } from '@/features/classification/pages';
import { ScheduledWorkflowsPage, SchedulerMonitorPage } from '@/features/scheduler/pages';

/**
 * 路由配置
 *
 * 为什么使用 createBrowserRouter？
 * - React Router v6.4+ 推荐的方式
 * - 支持 data loading
 * - 支持 error boundaries
 * - 更好的类型支持
 */
export const router = createBrowserRouter([
  {
    path: '/',
    element: <HomePage />,
  },
  {
    path: '/agents',
    element: <AgentListTest />,
  },
  {
    path: '/agents/create',
    element: <CreateAgentPage />,
  },
  {
    path: '/agents/:id',
    element: <AgentDetailPage />,
  },
  {
    path: '/workflows/:id/edit',
    element: <WorkflowEditorPage />,
  },
  {
    path: '/classification',
    element: <TaskClassificationPage />,
  },
  {
    path: '/scheduled',
    element: <ScheduledWorkflowsPage />,
  },
  {
    path: '/monitor',
    element: <SchedulerMonitorPage />,
  },
]);

/**
 * 为什么使用 Navigate 组件？
 * - 自动重定向到默认页面
 * - replace 参数避免在历史记录中留下 /
 * - 提升用户体验
 *
 * 为什么 /agents/create 在 /agents 之后？
 * - React Router 按顺序匹配路由
 * - 更具体的路由应该在前面
 * - 但这里 /agents/create 不会被 /agents 匹配（因为没有通配符）
 *
 * 未来扩展：
 * - /agents/:id - Agent 详情页
 * - /agents/:id/edit - 编辑 Agent 页面
 * - /runs/:id - Run 详情页
 */
