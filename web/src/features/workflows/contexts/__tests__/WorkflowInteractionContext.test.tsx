import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { WorkflowInteractionProvider, useWorkflowInteraction } from '../WorkflowInteractionContext';

// Test component to consume the context
const TestComponent: React.FC = () => {
  const { interactionMode, setInteractionMode, isCanvasMode, isChatMode } = useWorkflowInteraction();

  return (
    <div>
      <div data-testid="mode">{interactionMode}</div>
      <div data-testid="is-canvas">{isCanvasMode.toString()}</div>
      <div data-testid="is-chat">{isChatMode.toString()}</div>
      <button onClick={() => setInteractionMode('canvas')}>Canvas Mode</button>
      <button onClick={() => setInteractionMode('chat')}>Chat Mode</button>
      <button onClick={() => setInteractionMode('idle')}>Idle Mode</button>
    </div>
  );
};

describe('WorkflowInteractionContext', () => {
  it('should initialize with idle mode', () => {
    render(
      <WorkflowInteractionProvider>
        <TestComponent />
      </WorkflowInteractionProvider>
    );

    expect(screen.getByTestId('mode').textContent).toBe('idle');
    expect(screen.getByTestId('is-canvas').textContent).toBe('false');
    expect(screen.getByTestId('is-chat').textContent).toBe('false');
  });

  it('should switch to canvas mode', () => {
    render(
      <WorkflowInteractionProvider>
        <TestComponent />
      </WorkflowInteractionProvider>
    );

    fireEvent.click(screen.getByText('Canvas Mode'));

    expect(screen.getByTestId('mode').textContent).toBe('canvas');
    expect(screen.getByTestId('is-canvas').textContent).toBe('true');
    expect(screen.getByTestId('is-chat').textContent).toBe('false');
  });

  it('should switch to chat mode', () => {
    render(
      <WorkflowInteractionProvider>
        <TestComponent />
      </WorkflowInteractionProvider>
    );

    fireEvent.click(screen.getByText('Chat Mode'));

    expect(screen.getByTestId('mode').textContent).toBe('chat');
    expect(screen.getByTestId('is-canvas').textContent).toBe('false');
    expect(screen.getByTestId('is-chat').textContent).toBe('true');
  });

  it('should throw error when used outside provider', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => {
      render(<TestComponent />);
    }).toThrow('useWorkflowInteraction must be used within WorkflowInteractionProvider');

    consoleError.mockRestore();
  });
});
