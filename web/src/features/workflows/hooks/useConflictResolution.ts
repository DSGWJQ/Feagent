import { useCallback, useMemo, useState } from 'react';

export type ConflictStrategy = 'ask' | 'local' | 'remote' | 'merge';
export type ConflictResolutionStrategy = Exclude<ConflictStrategy, 'ask'>;

export type ConflictType =
  | 'node_modified'
  | 'node_deleted'
  | 'edge_modified'
  | 'edge_deleted';

export type ConflictElementType = 'node' | 'edge';

export type Conflict<T = unknown> = {
  id: string;
  type: ConflictType;
  elementType: ConflictElementType;
  elementId: string;
  local?: T | null;
  remote?: T | null;
  detectedAt?: string;
};

type ResolveResult<T = unknown> = {
  conflictId: string;
  strategy: ConflictResolutionStrategy;
  result: T | null;
};

export type UseConflictResolutionOptions<T = unknown> = {
  defaultStrategy?: ConflictStrategy;
  onConflictDetected?: (conflict: Conflict<T>) => void;
};

function mergeValues<T>(local: T | null | undefined, remote: T | null | undefined): T | null {
  if (local == null && remote == null) return null;
  if (local == null) return remote ?? null;
  if (remote == null) return local ?? null;

  if (typeof local === 'object' && typeof remote === 'object') {
    return { ...(remote as Record<string, unknown>), ...(local as Record<string, unknown>) } as T;
  }

  return local;
}

export function useConflictResolution<T = unknown>(options: UseConflictResolutionOptions<T> = {}) {
  const { defaultStrategy = 'ask', onConflictDetected } = options;
  const [conflicts, setConflicts] = useState<Array<Conflict<T>>>([]);

  const hasConflicts = conflicts.length > 0;

  const detectConflict = useCallback(
    (conflict: Conflict<T>) => {
      setConflicts((prev) => {
        if (prev.some((c) => c.id === conflict.id)) return prev;
        return [...prev, conflict];
      });
      onConflictDetected?.(conflict);
    },
    [onConflictDetected]
  );

  const resolveConflict = useCallback(
    (conflictId: string, strategy: ConflictResolutionStrategy): ResolveResult<T> | null => {
      const conflict = conflicts.find((c) => c.id === conflictId);
      if (!conflict) return null;

      let result: T | null = null;
      if (strategy === 'local') {
        result = (conflict.local ?? null) as T | null;
      } else if (strategy === 'remote') {
        result = (conflict.remote ?? null) as T | null;
      } else {
        result = mergeValues(conflict.local ?? null, conflict.remote ?? null);
      }

      setConflicts((prev) => prev.filter((c) => c.id !== conflictId));
      return { conflictId, strategy, result };
    },
    [conflicts]
  );

  const resolveAllConflicts = useCallback(
    (strategy: ConflictResolutionStrategy) => {
      // For now, we just clear the list; callers can treat "keep local/merge" as "dismiss all".
      // Actual element-level application is handled by the editor based on per-conflict resolution.
      setConflicts([]);
      return strategy;
    },
    []
  );

  const clearConflicts = useCallback(() => {
    setConflicts([]);
  }, []);

  const api = useMemo(
    () => ({
      conflicts,
      hasConflicts,
      detectConflict,
      resolveConflict,
      resolveAllConflicts,
      clearConflicts,
      defaultStrategy,
    }),
    [
      conflicts,
      hasConflicts,
      detectConflict,
      resolveConflict,
      resolveAllConflicts,
      clearConflicts,
      defaultStrategy,
    ]
  );

  return api;
}
