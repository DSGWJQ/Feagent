/**
 * 应用路由配置
 *
 * 路由结构：
 * - / - 着陆页（Landing Page，无布局）
 * - /workflows/:id/edit - 工作流编辑器（全屏，无布局）
 * - /app/* - 应用页面（使用 MainLayout）
 *   - /app/agents - Agent 列表页
 *   - /app/agents/create - 创建 Agent 页面
 *   - /app/agents/:id - Agent 详情页
 *   - /app/scheduled - 定时任务
 *   - /app/monitor - 调度器监控
 *   - /app/providers - LLM 提供商
 *
 * 为什么分离不同类型的页面？
 * - 着陆页：营销/介绍页面，无需导航菜单
 * - 工作流编辑器：全屏编辑器，需要完整画布空间
 * - 应用页面：管理页面，使用统一的侧边栏导航
 */

import { createBrowserRouter, Navigate } from 'react-router-dom';
import { MainLayout } from '@/layouts';
import { HomePage } from '@/features/home/pages';
import { AgentListTest, CreateAgentPage, AgentDetailPage } from '@/features/agents/pages';
import { WorkflowEditorPage } from '@/features/workflows/pages';
// import { TaskClassificationPage } from '@/features/classification/pages';
import { ScheduledWorkflowsPage, SchedulerMonitorPage } from '@/features/scheduler/pages';
// import { ToolsLibraryPage } from '@/features/tools/pages';
import { LLMProvidersPage } from '@/features/llm/pages';

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
  // 着陆页（无布局）
  {
    path: '/',
    element: <HomePage />,
  },

  // 工作流编辑器（全屏，无布局）
  {
    path: '/workflows/:id/edit',
    element: <WorkflowEditorPage />,
  },

  // 应用页面（使用 MainLayout）
  {
    path: '/app',
    element: <MainLayout />,
    children: [
      // 默认重定向到 agents
      {
        index: true,
        element: <Navigate to="/app/agents" replace />,
      },

      // Agent 管理
      {
        path: 'agents',
        element: <AgentListTest />,
      },
      {
        path: 'agents/create',
        element: <CreateAgentPage />,
      },
      {
        path: 'agents/:id',
        element: <AgentDetailPage />,
      },

      // 智能分类（已禁用 - V2 实验性功能）
      // {
      //   path: 'classification',
      //   element: <TaskClassificationPage />,
      // },

      // 调度器
      {
        path: 'scheduled',
        element: <ScheduledWorkflowsPage />,
      },
      {
        path: 'monitor',
        element: <SchedulerMonitorPage />,
      },

      // 工具库（已禁用 - 底层管理功能）
      // {
      //   path: 'tools',
      //   element: <ToolsLibraryPage />,
      // },

      // LLM 管理
      {
        path: 'providers',
        element: <LLMProvidersPage />,
      },
    ],
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
