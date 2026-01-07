import { useCallback, useEffect, useRef, useState } from 'react';

import { API_BASE_URL } from '@/services/api';

const MIN_REPLAY_UI_MS = 500;

export type RunEvent = {
  type: string;
  run_id: string;
  [key: string]: any;
};

export type UseRunReplayOptions = {
  runId: string;
  pageSize?: number;
  onEvent?: (event: RunEvent) => void;
  onComplete?: () => void;
  onError?: (error: Error) => void;
};

export function useRunReplay(options: UseRunReplayOptions) {
  const { runId, pageSize = 200, onEvent, onComplete, onError } = options;
  const [isReplaying, setIsReplaying] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

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
    abortRef.current?.abort();
    abortRef.current = null;
    setIsReplaying(false);
  }, []);

  const startReplay = useCallback(async () => {
    if (!runId) return;
    const replayStartAt = Date.now();
    let aborted = false;
    try {
      abortRef.current?.abort();
      const abortController = new AbortController();
      abortRef.current = abortController;
      setIsReplaying(true);

      let cursor: number | undefined;
      while (true) {
        const params = new URLSearchParams();
        params.set('limit', String(pageSize));
        if (cursor !== undefined) params.set('cursor', String(cursor));

        const token = localStorage.getItem('authToken');
        const headers: HeadersInit = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const res = await fetch(`${API_BASE_URL}/runs/${runId}/events?${params.toString()}`, {
          method: 'GET',
          headers,
          signal: abortController.signal,
        });

        if (!res.ok) {
          const detail = await res.json().catch(() => ({}));
          const msg =
            typeof detail?.detail === 'string'
              ? detail.detail
              : `HTTP error! status: ${res.status}`;
          throw new Error(msg);
        }

        const data = (await res.json()) as {
          run_id: string;
          events: RunEvent[];
          next_cursor: number | null;
          has_more: boolean;
        };

        for (const evt of data.events || []) {
          onEventRef.current?.(evt);
        }

        if (!data.has_more || data.next_cursor == null) break;
        cursor = data.next_cursor;
      }

      onCompleteRef.current?.();
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') {
        aborted = true;
        return;
      }
      const err = e instanceof Error ? e : new Error(String(e));
      onErrorRef.current?.(err);
    } finally {
      abortRef.current = null;
      if (!aborted) {
        const elapsedMs = Date.now() - replayStartAt;
        const remainingMs = MIN_REPLAY_UI_MS - elapsedMs;
        if (remainingMs > 0) {
          await new Promise((resolve) => setTimeout(resolve, remainingMs));
        }
      }
      setIsReplaying(false);
    }
  }, [pageSize, runId]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  return {
    isReplaying,
    startReplay,
    stopReplay,
  };
}
