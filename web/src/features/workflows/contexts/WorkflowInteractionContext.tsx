import React, { createContext, useContext, useState, ReactNode } from 'react';

export type InteractionMode = 'canvas' | 'chat' | 'idle';

interface WorkflowInteractionContextType {
  interactionMode: InteractionMode;
  setInteractionMode: (mode: InteractionMode) => void;
  isCanvasMode: boolean;
  isChatMode: boolean;
}

const WorkflowInteractionContext = createContext<WorkflowInteractionContextType | undefined>(
  undefined
);

export const useWorkflowInteraction = () => {
  const context = useContext(WorkflowInteractionContext);
  if (!context) {
    throw new Error('useWorkflowInteraction must be used within WorkflowInteractionProvider');
  }
  return context;
};

interface WorkflowInteractionProviderProps {
  children: ReactNode;
}

export const WorkflowInteractionProvider: React.FC<WorkflowInteractionProviderProps> = ({
  children,
}) => {
  const [interactionMode, setInteractionMode] = useState<InteractionMode>('idle');

  const isCanvasMode = interactionMode === 'canvas';
  const isChatMode = interactionMode === 'chat';

  return (
    <WorkflowInteractionContext.Provider
      value={{
        interactionMode,
        setInteractionMode,
        isCanvasMode,
        isChatMode,
      }}
    >
      {children}
    </WorkflowInteractionContext.Provider>
  );
};

// 添加默认导出
export default WorkflowInteractionProvider;
