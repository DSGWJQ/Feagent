/**
 * WorkflowEditorPage smoke tests
 *
 * 目标：验证路由参数 wiring 与页面最小渲染不崩溃。
 * 说明：具体编辑器/聊天框交互由各自组件的单测/集成测试覆盖。
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Route, Routes } from 'react-router-dom';
import { renderWithProviders, screen } from '@/test/utils';
import { WorkflowEditorPage } from '../WorkflowEditorPage';

vi.mock('@/hooks/useWorkflow', () => ({
  useWorkflow: () => ({
    workflowData: {
      id: 'test-workflow',
      name: 'Test Workflow',
      description: 'Test Description',
      nodes: [],
      edges: [],
    },
    isLoadingWorkflow: false,
    workflowError: null,
  }),
}));

vi.mock('../WorkflowEditorPageWithMutex', () => ({
  default: ({ workflowId }: { workflowId: string }) => (
    <div data-testid="workflow-editor-inner">{workflowId}</div>
  ),
}));

describe('WorkflowEditorPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderRoute(workflowId = 'wf_test_123') {
    return renderWithProviders(
      <Routes>
        <Route path="/workflows/:id/edit" element={<WorkflowEditorPage />} />
      </Routes>,
      { initialEntries: [`/workflows/${workflowId}/edit`] }
    );
  }

  it('renders inner editor with workflow id from route params', () => {
    renderRoute('test-workflow-123');
    expect(screen.getByTestId('workflow-editor-inner')).toHaveTextContent(
      'test-workflow-123'
    );
  });
});
