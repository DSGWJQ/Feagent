import { useCallback, useEffect, useRef, useState } from 'react';

export type RunEvent = {
  event_type: string;
  payload: Record<string, any>;
};

export type UseRunReplayOptions = {
  runId: string;
  onEvent?: (event: RunEvent) => void;
  onComplete?: () => void;
  onError?: (error: Error) => void;
};

export function useRunReplay(options: UseRunReplayOptions) {
  const { runId, onEvent, onComplete, onError } = options;
  const [isReplaying, setIsReplaying] = useState(false);

  const onEventRef = useRef(onEvent);
  const onCompleteRef = useRef(onComplete);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);
  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  const stopReplay = useCallback(() => {
    setIsReplaying(false);
  }, []);

  const startReplay = useCallback(async () => {
    if (!runId) return;
    try {
      setIsReplaying(true);

      // Minimal placeholder: real replay should stream persisted run events.
      // Keep this hook stable for tests/build even when backend replay is unavailable.
      onEventRef.current?.({
        event_type: 'replay_started',
        payload: { run_id: runId },
      });
    } catch (e) {
      const err = e instanceof Error ? e : new Error(String(e));
      onErrorRef.current?.(err);
      setIsReplaying(false);
    }
  }, [runId]);

  useEffect(() => {
    if (!isReplaying) return;
    return () => {
      onCompleteRef.current?.();
    };
  }, [isReplaying]);

  return {
    isReplaying,
    startReplay,
    stopReplay,
  };
}
