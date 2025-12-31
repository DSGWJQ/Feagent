import { useCallback, useMemo, useRef, useState } from 'react';

export type ResearchPlanTask = {
  id: string;
  type: string;
  dependencies: string[];
};

export type ResearchPlanDTO = {
  tasks: ResearchPlanTask[];
  parallel_points: string[];
  risk_points: string[];
};

export type CompileResponse = {
  id: string;
  name: string;
  description: string | null;
  nodes: any[];
  edges: any[];
  warnings: string[];
};

export type UseResearchPlanOptions = {
  workflowId: string;
  projectId: string | null;
  onPlanGenerated?: (plan: ResearchPlanDTO) => void;
  onCompiled?: (response: CompileResponse) => void;
  onError?: (error: Error) => void;
};

export function useResearchPlan(options: UseResearchPlanOptions) {
  const { workflowId, projectId, onPlanGenerated, onCompiled, onError } = options;

  const [plan, setPlan] = useState<ResearchPlanDTO | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isCompiling, setIsCompiling] = useState(false);
  const [thinkingContent, setThinkingContent] = useState<string>('');
  const [error, setError] = useState<Error | null>(null);

  const onPlanGeneratedRef = useRef(onPlanGenerated);
  const onCompiledRef = useRef(onCompiled);
  const onErrorRef = useRef(onError);

  onPlanGeneratedRef.current = onPlanGenerated;
  onCompiledRef.current = onCompiled;
  onErrorRef.current = onError;

  const createRun = useCallback(async () => {
    // Placeholder: real implementation should create a persistent run on backend.
    if (!projectId) return null;
    return `run_${Date.now()}`;
  }, [projectId]);

  const generatePlan = useCallback(
    async (goal: string, _runId: string | null) => {
      if (!goal.trim()) return;
      setIsGenerating(true);
      setError(null);
      setThinkingContent('Generating plan...');

      try {
        // Placeholder: keep UI stable even when planning backend is unavailable.
        const nextPlan: ResearchPlanDTO = {
          tasks: [],
          parallel_points: [],
          risk_points: [],
        };
        setPlan(nextPlan);
        onPlanGeneratedRef.current?.(nextPlan);
      } catch (e) {
        const err = e instanceof Error ? e : new Error(String(e));
        setError(err);
        onErrorRef.current?.(err);
      } finally {
        setThinkingContent('');
        setIsGenerating(false);
      }
    },
    []
  );

  const compilePlan = useCallback(
    async (_plan: ResearchPlanDTO, _runId: string | null) => {
      setIsCompiling(true);
      setError(null);
      try {
        const response: CompileResponse = {
          id: workflowId,
          name: 'Workflow',
          description: null,
          nodes: [],
          edges: [],
          warnings: [],
        };
        onCompiledRef.current?.(response);
      } catch (e) {
        const err = e instanceof Error ? e : new Error(String(e));
        setError(err);
        onErrorRef.current?.(err);
      } finally {
        setIsCompiling(false);
      }
    },
    [workflowId]
  );

  const cancelGeneration = useCallback(() => {
    // Placeholder: without backend streaming, this is a local state reset.
    setIsGenerating(false);
    setThinkingContent('');
  }, []);

  const reset = useCallback(() => {
    setPlan(null);
    setIsGenerating(false);
    setIsCompiling(false);
    setThinkingContent('');
    setError(null);
  }, []);

  return useMemo(
    () => ({
      createRun,
      generatePlan,
      compilePlan,
      cancelGeneration,
      reset,
      plan,
      isGenerating,
      isCompiling,
      thinkingContent,
      error,
      workflowId,
      projectId,
    }),
    [
      createRun,
      generatePlan,
      compilePlan,
      cancelGeneration,
      reset,
      plan,
      isGenerating,
      isCompiling,
      thinkingContent,
      error,
      workflowId,
      projectId,
    ]
  );
}
