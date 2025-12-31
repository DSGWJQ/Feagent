/**
 * TaskClassificationPage Tests - RED phase (TDD)
 *
 * Tests the task classification page component:
 * 1. Page renders successfully with initial form
 * 2. User can input task start and goal
 * 3. Classification API is called with correct data
 * 4. Results are displayed after classification
 * 5. Error handling for API failures
 * 6. Loading state during classification
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClientProvider, QueryClient } from '@tanstack/react-query';
import TaskClassificationPage from '../TaskClassificationPage';
import * as classificationApi from '../../api/classificationApi';

// Mock the API
vi.mock('../../api/classificationApi');

const renderWithProviders = (component: React.ReactElement) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      {component}
    </QueryClientProvider>
  );
};

describe('TaskClassificationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render the page with form inputs', () => {
    renderWithProviders(<TaskClassificationPage />);

    expect(screen.getByText(/Task Classification/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/start/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/goal/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /classify/i })).toBeInTheDocument();
  });

  it('should require start and goal inputs', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TaskClassificationPage />);

    const classifyButton = screen.getByRole('button', { name: /classify/i });
    await user.click(classifyButton);

    // Should show validation errors
    await waitFor(() => {
      expect(
        screen.getByText(/Please describe the current state or starting point/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Please describe the goal or desired outcome/i)
      ).toBeInTheDocument();
    });
  });

  it('should call classification API with form data', async () => {
    const mockClassify = vi.fn().mockResolvedValue({
      data: {
        taskType: 'data_analysis',
        confidence: 0.95,
        reasoning: 'This is a data analysis task',
        suggestedTools: ['database', 'visualization'],
      },
    });

    vi.spyOn(classificationApi, 'classifyTask').mockImplementation(mockClassify);

    const user = userEvent.setup();
    renderWithProviders(<TaskClassificationPage />);

    const startInput = screen.getByLabelText(/start/i);
    const goalInput = screen.getByLabelText(/goal/i);
    const classifyButton = screen.getByRole('button', { name: /classify/i });

    await user.type(startInput, 'I have CSV data');
    await user.type(goalInput, 'Analyze sales trends');
    await user.click(classifyButton);

    await waitFor(() => {
      expect(mockClassify).toHaveBeenCalledWith({
        start: 'I have CSV data',
        goal: 'Analyze sales trends',
      });
    });
  });

  it('should display classification results', async () => {
    const mockResult = {
      data: {
        taskType: 'data_analysis',
        confidence: 0.95,
        reasoning: 'This is a data analysis task because it involves CSV data and trend analysis',
        suggestedTools: ['database', 'visualization', 'statistical_analysis'],
      },
    };

    vi.spyOn(classificationApi, 'classifyTask').mockResolvedValue(mockResult);

    const user = userEvent.setup();
    renderWithProviders(<TaskClassificationPage />);

    const startInput = screen.getByLabelText(/start/i);
    const goalInput = screen.getByLabelText(/goal/i);
    const classifyButton = screen.getByRole('button', { name: /classify/i });

    await user.type(startInput, 'I have CSV data');
    await user.type(goalInput, 'Analyze sales trends');
    await user.click(classifyButton);

    await waitFor(() => {
      expect(screen.getAllByText(/Data Analysis/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/95\.00%/)).toBeInTheDocument();
      expect(screen.getByText(/This is a data analysis task/)).toBeInTheDocument();
    });
  });

  it('should show loading state during classification', async () => {
    const mockClassify = vi.fn().mockImplementation(
      () => new Promise((resolve) => {
        setTimeout(() => {
          resolve({
            data: {
              taskType: 'data_analysis',
              confidence: 0.95,
              reasoning: 'Test',
              suggestedTools: [],
            },
          });
        }, 100);
      })
    );

    vi.spyOn(classificationApi, 'classifyTask').mockImplementation(mockClassify);

    const user = userEvent.setup();
    renderWithProviders(<TaskClassificationPage />);

    const startInput = screen.getByLabelText(/start/i);
    const goalInput = screen.getByLabelText(/goal/i);
    const classifyButton = screen.getByRole('button', { name: /classify/i });

    await user.type(startInput, 'Start1');
    await user.type(goalInput, 'Goal1');
    await user.click(classifyButton);

    expect(screen.getByRole('button', { name: /classifying/i })).toBeInTheDocument();
  });

  it('should handle API errors gracefully', async () => {
    const mockError = new Error('Classification failed');
    vi.spyOn(classificationApi, 'classifyTask').mockRejectedValue(mockError);

    const user = userEvent.setup();
    renderWithProviders(<TaskClassificationPage />);

    const startInput = screen.getByLabelText(/start/i);
    const goalInput = screen.getByLabelText(/goal/i);
    const classifyButton = screen.getByRole('button', { name: /classify/i });

    await user.type(startInput, 'Start1');
    await user.type(goalInput, 'Goal1');
    await user.click(classifyButton);

    await waitFor(() => {
      expect(screen.getByText(/Classification Error/i)).toBeInTheDocument();
    });
  });

  it('should display suggested tools', async () => {
    const mockResult = {
      data: {
        taskType: 'content_creation',
        confidence: 0.85,
        reasoning: 'Content creation task',
        suggestedTools: ['text_editor', 'spell_checker', 'grammar_checker'],
      },
    };

    vi.spyOn(classificationApi, 'classifyTask').mockResolvedValue(mockResult);

    const user = userEvent.setup();
    renderWithProviders(<TaskClassificationPage />);

    const startInput = screen.getByLabelText(/start/i);
    const goalInput = screen.getByLabelText(/goal/i);
    const classifyButton = screen.getByRole('button', { name: /classify/i });

    await user.type(startInput, 'Write content');
    await user.type(goalInput, 'Create marketing copy');
    await user.click(classifyButton);

    await waitFor(() => {
      expect(screen.getByText(/text_editor/)).toBeInTheDocument();
      expect(screen.getByText(/spell_checker/)).toBeInTheDocument();
    });
  });

  it('should allow clearing classification results', async () => {
    const mockResult = {
      data: {
        taskType: 'data_analysis',
        confidence: 0.95,
        reasoning: 'Test reasoning',
        suggestedTools: ['tool1'],
      },
    };

    vi.spyOn(classificationApi, 'classifyTask').mockResolvedValue(mockResult);

    const user = userEvent.setup();
    renderWithProviders(<TaskClassificationPage />);

    const startInput = screen.getByLabelText(/start/i);
    const goalInput = screen.getByLabelText(/goal/i);
    const classifyButton = screen.getByRole('button', { name: /classify/i });

    await user.type(startInput, 'Start1');
    await user.type(goalInput, 'Goal1');
    await user.click(classifyButton);

    await waitFor(() => {
      expect(screen.getByText(/Data Analysis/i)).toBeInTheDocument();
    });

    const clearButton = screen.getByRole('button', { name: /clear|reset/i });
    await user.click(clearButton);

    await waitFor(() => {
      expect(screen.getByText(/Waiting for Input/i)).toBeInTheDocument();
    });
  });
});
