import { useCallback, useEffect, useRef, useState } from 'react';
import type { Edge, Node } from '@xyflow/react';

type WorkflowSnapshot<N extends Node = Node, E extends Edge = Edge> = {
  nodes: N[];
  edges: E[];
};

type PushOptions = {
  immediate?: boolean;
};

export type UseWorkflowHistoryOptions = {
  maxHistorySize?: number;
  debounceMs?: number;
};

export function useWorkflowHistory<N extends Node = Node, E extends Edge = Edge>(
  options: UseWorkflowHistoryOptions = {}
) {
  const { maxHistorySize = 50, debounceMs = 300 } = options;

  const [past, setPast] = useState<Array<WorkflowSnapshot<N, E>>>([]);
  const [future, setFuture] = useState<Array<WorkflowSnapshot<N, E>>>([]);

  const pastRef = useRef(past);
  const futureRef = useRef(future);

  const pendingTimeoutRef = useRef<number | null>(null);
  const pendingSnapshotRef = useRef<WorkflowSnapshot<N, E> | null>(null);

  useEffect(() => {
    pastRef.current = past;
  }, [past]);
  useEffect(() => {
    futureRef.current = future;
  }, [future]);

  const clearPending = useCallback(() => {
    if (pendingTimeoutRef.current !== null) {
      window.clearTimeout(pendingTimeoutRef.current);
      pendingTimeoutRef.current = null;
    }
    pendingSnapshotRef.current = null;
  }, []);

  const commitSnapshot = useCallback(
    (snapshot: WorkflowSnapshot<N, E>) => {
      setPast((prevPast) => {
        const nextPast = [...prevPast, snapshot].slice(-maxHistorySize);
        pastRef.current = nextPast;
        return nextPast;
      });
      setFuture(() => {
        futureRef.current = [];
        return [];
      });
    },
    [maxHistorySize]
  );

  const flushPending = useCallback(() => {
    if (!pendingSnapshotRef.current) return;
    const snapshot = pendingSnapshotRef.current;
    clearPending();
    commitSnapshot(snapshot);
  }, [clearPending, commitSnapshot]);

  const pushSnapshot = useCallback(
    (nodes: N[], edges: E[], pushOptions: PushOptions = {}) => {
      const snapshot: WorkflowSnapshot<N, E> = { nodes, edges };

      if (pushOptions.immediate || debounceMs <= 0) {
        clearPending();
        commitSnapshot(snapshot);
        return;
      }

      pendingSnapshotRef.current = snapshot;
      if (pendingTimeoutRef.current !== null) {
        window.clearTimeout(pendingTimeoutRef.current);
      }
      pendingTimeoutRef.current = window.setTimeout(() => {
        pendingTimeoutRef.current = null;
        flushPending();
      }, debounceMs);
    },
    [clearPending, commitSnapshot, debounceMs, flushPending]
  );

  const undo = useCallback((): WorkflowSnapshot<N, E> | null => {
    flushPending();

    const currentPast = pastRef.current;
    if (currentPast.length <= 1) return null;

    const current = currentPast[currentPast.length - 1];
    const previous = currentPast[currentPast.length - 2];

    const nextPast = currentPast.slice(0, -1);
    const nextFuture = [current, ...futureRef.current].slice(0, maxHistorySize);

    pastRef.current = nextPast;
    futureRef.current = nextFuture;
    setPast(nextPast);
    setFuture(nextFuture);

    return previous;
  }, [flushPending, maxHistorySize]);

  const redo = useCallback((): WorkflowSnapshot<N, E> | null => {
    flushPending();

    const currentFuture = futureRef.current;
    if (currentFuture.length === 0) return null;

    const next = currentFuture[0];
    const nextFuture = currentFuture.slice(1);
    const nextPast = [...pastRef.current, next].slice(-maxHistorySize);

    pastRef.current = nextPast;
    futureRef.current = nextFuture;
    setPast(nextPast);
    setFuture(nextFuture);

    return next;
  }, [flushPending, maxHistorySize]);

  const clearHistory = useCallback(() => {
    clearPending();
    pastRef.current = [];
    futureRef.current = [];
    setPast([]);
    setFuture([]);
  }, [clearPending]);

  const canUndo = past.length > 1;
  const canRedo = future.length > 0;

  return {
    pushSnapshot,
    undo,
    redo,
    canUndo,
    canRedo,
    clearHistory,
  };
}
