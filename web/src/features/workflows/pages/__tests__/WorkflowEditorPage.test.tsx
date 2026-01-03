/**
 * WorkflowEditorPage smoke tests
 *
 * 目标：验证路由参数 wiring 与页面最小渲染不崩溃。
 * 说明：具体编辑器/聊天框交互由各自组件的单测/集成测试覆盖。
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Route, Routes } from 'react-router-dom';
import { renderWithProviders, screen, waitFor, userEvent } from '@/test/utils';
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

const mocks = vi.hoisted(() => ({
  chatCreateWorkflowStreaming: vi.fn(),
}));

vi.mock('../../api/workflowsApi', () => ({
  chatCreateWorkflowStreaming: mocks.chatCreateWorkflowStreaming,
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

  it('creates workflow from root route and navigates to editor when workflow_id arrives', async () => {
    mocks.chatCreateWorkflowStreaming.mockImplementation((_request: any, onEvent: any) => {
      onEvent({
        type: 'thinking',
        content: 'creating...',
        is_final: false,
        metadata: { workflow_id: 'wf_created_123' },
      });
      return () => {};
    });

    const user = userEvent.setup();

    renderWithProviders(
      <Routes>
        <Route path="/" element={<WorkflowEditorPage />} />
        <Route path="/workflows/:id/edit" element={<WorkflowEditorPage />} />
      </Routes>,
      { initialEntries: ['/'] }
    );

    await user.type(
      screen.getByPlaceholderText('例如：帮我生成一个“用户注册与欢迎邮件”工作流'),
      '创建一个示例工作流'
    );
    await user.click(screen.getByRole('button', { name: '创建并进入编辑器' }));

    await waitFor(() => {
      expect(screen.getByTestId('workflow-editor-inner')).toHaveTextContent('wf_created_123');
    });
  });

});
