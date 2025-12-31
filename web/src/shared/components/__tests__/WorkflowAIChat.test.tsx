import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ChatMessage } from '@/shared/types/chat';
import { WorkflowAIChat } from '../WorkflowAIChat';
import { renderWithProviders } from '@/test/utils';

const mockSendMessage = vi.fn();
const mockConfirmPending = vi.fn();
const mockStartChatStream = vi.fn();
const mockUseWorkflowAI = vi.fn();

vi.mock('@/hooks/useWorkflowAI', () => ({
  useWorkflowAI: (...args: unknown[]) => mockUseWorkflowAI(...args),
}));

const createDefaultHookReturn = () => ({
  messages: baseMessages,
  isProcessing: false,
  pendingWorkflow: null,
  streamingMessage: null as string | null,
  sendMessage: mockSendMessage,
  confirmPendingWorkflow: mockConfirmPending,
  startChatStream: mockStartChatStream,
  errorMessage: null as string | null,
});

const baseMessages: ChatMessage[] = [
  { id: 'user-1', role: 'user', content: 'hello', timestamp: Date.now() },
  { id: 'assistant-1', role: 'assistant', content: 'hi there', timestamp: Date.now() },
];

const setupHookReturn = (overrides: Partial<ReturnType<typeof createDefaultHookReturn>> = {}) => {
  const result = { ...createDefaultHookReturn(), ...overrides };
  mockUseWorkflowAI.mockReturnValue(result);
  return result;
};

describe('WorkflowAIChat', () => {
  const workflowId = 'wf_test123';
  const onWorkflowUpdate = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    setupHookReturn();
  });

  it('renders chat UI and messages from hook', () => {
    renderWithProviders(
      <WorkflowAIChat workflowId={workflowId} onWorkflowUpdate={onWorkflowUpdate} />
    );

    expect(screen.getByPlaceholderText(/输入消息/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /发\s*送/i })).toBeInTheDocument();
    expect(screen.getByText('hello')).toBeInTheDocument();
    expect(screen.getByText('hi there')).toBeInTheDocument();
  });

  it('sends message when user clicks button', async () => {
    const user = userEvent.setup();
    mockStartChatStream.mockResolvedValue(undefined);

    renderWithProviders(
      <WorkflowAIChat workflowId={workflowId} onWorkflowUpdate={onWorkflowUpdate} />
    );

    const input = screen.getByPlaceholderText(/输入消息/i);
    await user.type(input, '添加节点');
    await user.click(screen.getByRole('button', { name: /发\s*送/i }));

    await waitFor(() => {
      expect(mockStartChatStream).toHaveBeenCalledWith('添加节点');
    });
  });

  it('disables input while processing', () => {
    setupHookReturn({ isProcessing: true });

    renderWithProviders(
      <WorkflowAIChat workflowId={workflowId} onWorkflowUpdate={onWorkflowUpdate} />
    );

    expect(screen.getByPlaceholderText(/输入消息/i)).toBeDisabled();
    expect(screen.getByRole('button', { name: /发\s*送/i })).toBeDisabled();
    expect(screen.getByText(/AI正在思考/i)).toBeInTheDocument();
  });

  it('shows pending workflow confirmation CTA', async () => {
    const user = userEvent.setup();
    setupHookReturn({ pendingWorkflow: { id: workflowId } });

    renderWithProviders(
      <WorkflowAIChat workflowId={workflowId} onWorkflowUpdate={onWorkflowUpdate} />
    );

    await user.click(screen.getByRole('button', { name: /同步到画布/i }));

    expect(mockConfirmPending).toHaveBeenCalled();
  });

  it('displays error message from hook', () => {
    setupHookReturn({ errorMessage: '请求失败', messages: [] });

    renderWithProviders(
      <WorkflowAIChat workflowId={workflowId} onWorkflowUpdate={onWorkflowUpdate} />
    );

    expect(screen.getByText(/请求失败/)).toBeInTheDocument();
  });
});
