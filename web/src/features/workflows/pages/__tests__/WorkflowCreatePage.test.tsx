/**
 * WorkflowCreatePage tests
 *
 * Contract:
 * - /workflows/new 才触发 chat-create workflow 并跳转到 editor
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Route, Routes } from 'react-router-dom';
import { renderWithProviders, screen, waitFor, userEvent } from '@/test/utils';

import { WorkflowCreatePage } from '../WorkflowCreatePage';
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

describe('WorkflowCreatePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('creates workflow and navigates to editor when workflow_id arrives', async () => {
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
        <Route path="/workflows/new" element={<WorkflowCreatePage />} />
        <Route path="/workflows/:id/edit" element={<WorkflowEditorPage />} />
      </Routes>,
      { initialEntries: ['/workflows/new'] }
    );

    await user.type(
      screen.getByPlaceholderText('例如：帮我生成一个“用户注册与欢迎邮件”工作流'),
      '创建一个示例工作流'
    );
    await user.click(screen.getByRole('button', { name: '创建并进入编辑器' }));

    await waitFor(() => {
      expect(mocks.chatCreateWorkflowStreaming).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId('workflow-editor-inner')).toHaveTextContent('wf_created_123');
    });
  });
});
